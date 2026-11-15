"""Correlate exact Director operations through their canonical child transaction."""
from __future__ import annotations

import hashlib
import json
import re


OPERATIONS = {'intake', 'process', 'start'}
KEY_FIELDS = {'schema', 'director_id', 'assignment_id', 'queue_id', 'plan_sha256'}
CHILD_RECEIPTS = '.skill-tree/history/director-dispatch'
PARENT_INTENTS = '.skill-tree/director/dispatch-intents'
TOKEN = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def _require(condition, message):
    if not condition:
        raise wf.WorkflowError(message)


def _sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _digest(record):
    return hashlib.sha256(wf.dump(record).encode()).hexdigest()


def envelope(operation, value):
    _require(isinstance(operation, str) and operation in OPERATIONS and isinstance(value, dict)
             and set(value) == KEY_FIELDS and type(value['schema']) is int and value['schema'] == 1,
             'Director dispatch requires a supported operation and exact protocol envelope')
    _require(all(isinstance(value[key], str) and TOKEN.fullmatch(value[key]) is not None
                 for key in ('director_id', 'assignment_id')) and wf.valid_id(value['queue_id'], 'Q')
             and _sha(value['plan_sha256']), 'Director dispatch requires exact stable identities and a plan digest')
    identity = {key: value[key] for key in ('director_id', 'assignment_id', 'queue_id')}
    identity['operation'] = operation
    return identity, _digest(identity)


def _read(store, relative):
    path = store.owned(relative)
    _require(not any(part.is_symlink() for part in (path, *path.parents) if part.is_relative_to(store.base)),
             'Director metadata cannot use a symlink')
    if not path.exists():
        return None, None
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _receipt(store, identity, key):
    path = f'{CHILD_RECEIPTS}/{key}.json'
    value, _ = _read(store, path)
    if value is None:
        return path, None
    _require(isinstance(value, dict) and value.get('schema') == 1 and value.get('dispatch_key') == key
             and value.get('identity') == identity and _sha(value.get('semantic_sha256'))
             and _sha(value.get('plan_sha256')) and _sha(value.get('source_hash_before'))
             and isinstance(value.get('result'), dict)
             and _digest({name: part for name, part in value.items() if name != 'receipt_sha256'}) == value.get('receipt_sha256'),
             'Invalid canonical Director dispatch receipt')
    return path, value


def canonical_owner(store, queue_id):
    _require(store.neutral and store.source_root == store.root and not store.run_id and not store.selected_run_id,
             'Directed dispatch requires the exact canonical child root without implicit run selection')
    _require(wf.workspaces.canonical(store.root) == store.root,
             'Director dispatch requires the exact canonical child root')
    state = store.load()
    registry = state.get('run_registry')
    locator = wf.workspaces.runtime(store.root)
    _require(state['schema'] == 3 and registry and locator and registry['queue_id'] == locator['queue_id'] == queue_id,
             'Director dispatch destination is not the selected canonical child queue')
    return registry


def reconcile(store, receipt):
    if receipt['identity']['operation'] != 'start':
        return receipt['result']
    registry = canonical_owner(store, receipt['identity']['queue_id'])
    run = registry['runs'].get(receipt['result']['id'])
    _require(run is not None and run.get('workspace') == receipt['result'].get('workspace'),
             'Original Director run reservation is unavailable or changed')
    wf.workspaces.inspect_directed_reservation(store, run)
    return run


class ChildDispatch:
    """Bind a producer request to one result without granting operation authority."""

    def __init__(self, operation, request, start_context=None):
        self.identity, self.key = envelope(operation, request['director_dispatch'])
        self.plan_sha256 = request['director_dispatch']['plan_sha256']
        self.payload = {name: part for name, part in request.items() if name != 'director_dispatch'}
        self.semantic_sha256 = _digest({'plan_sha256': self.plan_sha256, 'operation': operation,
                                        'command': {name: part for name, part in self.payload.items()
                                                    if name != 'expected_source_hash'},
                                        **({'start': start_context} if start_context is not None else {})})
        _require(_sha(self.payload.get('expected_source_hash')), 'Director dispatch requires an inspected queue digest')
        if operation == 'process':
            ids = self.payload.get('selectors')
            _require(isinstance(ids, list) and ids and all(wf.valid_id(item, 'P') for item in ids)
                     and len(set(ids)) == len(ids), 'Directed processing requires exact distinct Pending IDs')
        if operation == 'start':
            _require(isinstance(start_context, dict) and set(start_context) == {'mode', 'selector', 'limits'},
                     'Directed start requires a frozen mode, selector and limits')
            mode, selector = start_context['mode'], start_context['selector']
            exact = wf.valid_id(selector, 'T') if mode == 'next' else bool(self.payload.get('snapshot_ids'))
            _require(exact and not self.payload.get('delivery_authorization'),
                     'Directed start requires exact task scope and no automatic delivery authority')

    def observed(self, store):
        canonical_owner(store, self.identity['queue_id'])
        _, receipt = _receipt(store, self.identity, self.key)
        if receipt is None:
            return None
        _require(receipt['semantic_sha256'] == self.semantic_sha256,
                 'Director dispatch key already belongs to a different semantic request')
        return reconcile(store, receipt)

    def extras(self, store, result):
        relative = f'{CHILD_RECEIPTS}/{self.key}.json'
        store.expect_unchanged(relative, None)
        record = {'schema': 1, 'dispatch_key': self.key, 'identity': self.identity,
                  'plan_sha256': self.plan_sha256, 'semantic_sha256': self.semantic_sha256,
                  'source_hash_before': self.payload['expected_source_hash'], 'recorded_at': wf.now(),
                  'result': result}
        record['receipt_sha256'] = _digest(record)
        return {relative: wf.dump(record)}


def _require_read_handoff(store):
    for relative in ('.writer-lock', '.transaction.json'):
        path = store.base / relative
        _require(not path.exists() and not path.is_symlink(),
                 'Canonical child mutation is in progress or requires recovery')


def observe(store, payload):
    _require(isinstance(payload, dict) and set(payload) == {'operation', 'director_dispatch'},
             'Director dispatch lookup requires one exact operation and envelope')
    identity, key = envelope(payload['operation'], payload['director_dispatch'])
    _require_read_handoff(store)
    canonical_owner(store, identity['queue_id'])
    _, receipt = _receipt(store, identity, key)
    result = None
    if receipt:
        _require(receipt['plan_sha256'] == payload['director_dispatch']['plan_sha256'],
                 'Existing Director dispatch belongs to a different plan')
        result = reconcile(store, receipt)
    _require_read_handoff(store)
    return {'schema': 1, 'dispatch_key': key, 'status': 'recorded' if receipt else 'absent',
            'receipt': receipt, 'observed_result': result}


def apply(store, payload):
    """Offer an explicit new command that older receivers cannot treat as ordinary intake."""
    _require(isinstance(payload, dict) and set(payload) in ({'operation', 'request'}, {'operation', 'request', 'start'}),
             'Director child dispatch requires an exact operation request')
    operation, request = payload['operation'], payload['request']
    _require(isinstance(request, dict) and 'director_dispatch' in request, 'Director child dispatch requires protocol metadata')
    envelope(operation, request['director_dispatch'])
    if operation == 'start':
        context = payload.get('start')
        _require(isinstance(context, dict) and set(context) == {'mode', 'selector', 'limits'},
                 'Directed start requires a frozen mode, selector and limits')
        return wf.start(store, context['mode'], context['selector'], context['limits'], request)
    _require('start' not in payload, 'Start context is valid only for directed start')
    return wf.intake(store, request) if operation == 'intake' else wf.process(store, request)


def retain_intent(store, operation, request, *, start_context=None):
    """Record the reviewed intent on the Director before invoking its child effect."""
    dispatch = ChildDispatch(operation, request, start_context)
    _require(store.source_root == store.root and store.neutral and store.run_id is None,
             'Director intent requires the exact parent metadata writer')
    relative = f'{PARENT_INTENTS}/{dispatch.key}.json'
    operation_owner = {'kind': 'director-dispatch-intent', 'dispatch_key': dispatch.key}
    with store.lock(local_delivery=operation_owner):
        current, baseline = _read(store, relative)
        if current is not None:
            _require(current.get('identity') == dispatch.identity and current.get('semantic_sha256') == dispatch.semantic_sha256
                     and current.get('plan_sha256') == dispatch.plan_sha256,
                     'Director intent already belongs to a different semantic request')
            return current
        store.expect_unchanged(relative, baseline)
        proposed = {'schema': 1, 'dispatch_key': dispatch.key, 'identity': dispatch.identity,
                    'plan_sha256': dispatch.plan_sha256, 'semantic_sha256': dispatch.semantic_sha256,
                    'source_hash_before': dispatch.payload['expected_source_hash'], 'recorded_at': wf.now()}
        store.commit({relative: wf.dump(proposed)})
        return proposed
