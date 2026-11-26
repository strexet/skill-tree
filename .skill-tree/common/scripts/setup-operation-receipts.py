"""Read and record bounded setup observations separately from effect journals."""

from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import json
import os
import re
import stat
from subprocess import TimeoutExpired


DIRECTORY = '.skill-tree/artifacts/setup-operations'
SIZE_LIMIT = 16 * 1024 * 1024
RECEIPT_LIMIT = 4096
INSTALL_PROOF = {'profile_sha256', 'core_journal_sha256', 'core_last_sha256',
                 'plugins_journal_sha256', 'plugins_last_sha256'}
DIRECTOR_PROOF = {'profile_sha256', 'preparation_sha256', 'registration_sha256'}
FIELDS = {'schema', 'operation_id', 'kind', 'request_sha256', 'stage', 'status',
          'started_at', 'observed_at', 'attempts', 'before', 'observed'}


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return False
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is not None
    except ValueError:
        return False


def _bounded(path, limit):
    try:
        expected = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(expected.st_mode) or expected.st_size > limit:
        raise ValueError('Expected a bounded regular setup evidence file')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)
    with os.fdopen(os.open(path, flags), 'rb') as stream:
        actual = os.fstat(stream.fileno())
        if not stat.S_ISREG(actual.st_mode) or not os.path.samestat(expected, actual):
            raise ValueError('Setup evidence file identity changed')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        if len(raw) > limit or len(raw) != actual.st_size or after.st_mtime_ns != actual.st_mtime_ns:
            raise ValueError('Setup evidence file size or content changed')
    return raw


def receipt(D, root, operation_id, *, required=True):
    D._require(D.WF.valid_id(operation_id, 'OP'), 'Select the exact setup operation ID')
    path = D._safe_path(root, f'{DIRECTORY}/{operation_id}.json')
    try:
        raw = _bounded(path, RECEIPT_LIMIT)
        if raw is None and not required:
            return None
    except (OSError, ValueError) as error:
        raise D.DirectorError('The selected setup operation receipt is malformed') from error
    D._require(raw is not None, 'The exact setup operation receipt is unavailable')
    try:
        data = json.loads(raw)
    except (UnicodeError, ValueError) as error:
        raise D.DirectorError('The selected setup operation receipt is malformed') from error
    invalid = 'The selected setup operation receipt is malformed'
    D._require(isinstance(data, dict) and FIELDS <= set(data) <= FIELDS | {'activation_journal_sha256'}
               and type(data['schema']) is int
               and data['schema'] == 1 and data['operation_id'] == operation_id
               and data['kind'] in ('install', 'recover', 'director-init', 'director-setup')
               and data['stage'] in ('recover', 'install', 'setup', 'complete')
               and data['status'] in ('pending', 'completed', 'failed')
               and (data['stage'] == 'complete') == (data['status'] == 'completed')
               and _hash(data['request_sha256']) and type(data['attempts']) is int and data['attempts'] > 0
               and _timestamp(data['started_at']) and _timestamp(data['observed_at']), invalid)
    if 'activation_journal_sha256' in data:
        activation = data['activation_journal_sha256']
        D._require(data['kind'] in ('install', 'recover') and (activation is None or
                   data['kind'] == 'install' and _hash(activation)), invalid)
    expected = INSTALL_PROOF if data['kind'] in ('install', 'recover') else DIRECTOR_PROOF
    for key in ('before', 'observed'):
        proof = data[key]
        D._require(isinstance(proof, dict) and set(proof) == expected
                   and all(value is None or value == 'unavailable' or _hash(value)
                           for value in proof.values()), invalid)
    return data


def _observe(D, paths):
    values = {}
    for key, (root, relative) in paths.items():
        value = None
        if relative:
            try:
                raw = _bounded(D._safe_path(root, relative), SIZE_LIMIT)
                value = sha256(raw).hexdigest() if raw is not None else None
            except (OSError, ValueError):
                value = 'unavailable'
        values[key] = value
    return values


@contextmanager
def observe_director_setup(D, root, kind, request, paths, operation_id=None):
    current = _observe(D, paths)
    request_hash = D._digest({'kind':kind, 'request':request})
    operation_id = operation_id if operation_id is not None else D.WF.identity('OP')
    previous = receipt(D, root, operation_id, required=False)
    D._require(not previous or (previous['kind'], previous['request_sha256']) == (kind, request_hash),
               'Setup operation ID belongs to a different request')
    if previous and previous['status'] == 'completed':
        D._require(previous['observed'] == current and 'unavailable' not in current.values(),
                   'The completed setup operation no longer covers the current evidence')
        yield operation_id, True
        return
    path = D._safe_path(root, f'{DIRECTORY}/{operation_id}.json')
    now = D.WF.now()
    record = {'schema':1, 'operation_id':operation_id, 'kind':kind, 'request_sha256':request_hash,
              'stage':'setup', 'status':'pending', 'started_at':previous['started_at'] if previous else now,
              'observed_at':now, 'attempts':previous['attempts'] + 1 if previous else 1,
              'before':previous['before'] if previous else current, 'observed':current}
    D.WS.atomic(path, record, exclusive=previous is None)
    try:
        yield operation_id, False
    except (ValueError, OSError, TimeoutExpired) as error:
        error.operation_id = operation_id
        record.update(status='failed', observed_at=D.WF.now(), observed=_observe(D, paths))
        try:
            D.WS.atomic(path, record)
        except OSError:
            pass
        raise
    else:
        record.update(status='completed', stage='complete', observed_at=D.WF.now(), observed=_observe(D, paths))
        try:
            D.WS.atomic(path, record)
        except OSError as error:
            error.operation_id = operation_id
            raise
