"""Read advisory context from committed Git trees."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import re
import runpy
import signal
import subprocess
from threading import Event, Lock, Timer


COMMIT = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
WORD = re.compile(r'\w+(?:[-./]\w+)*')
GREP_LINE = re.compile(rb'([^\x00]+)\x00([0-9]+)\x00([^\n]*)\n')
DEFAULT_LIMIT = 8
GREP_BYTES = 4 * 1024 * 1024
BLOB_BYTES = 2 * 1024 * 1024
GIT_TIMEOUT = 45


def query_terms(query, limit):
    if not isinstance(query, str) or len(query) > 240:
        raise ValueError('Context query must be text of at most 240 characters')
    terms = tuple(dict.fromkeys(WORD.findall(query.casefold())))
    if not 1 <= len(terms) <= 16 or type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError('Context search requires 1–16 terms and a result limit of 1–25')
    return terms


def relative_path(value):
    if not isinstance(value, str) or not value or any(char in value for char in '\x00\\'):
        raise ValueError('Context scope requires a relative Git path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or path.as_posix() != value:
        raise ValueError('Context scope requires a normalized relative Git path')
    return path


def git_output(git_args, root, *args, accepted=(0,), max_bytes=GREP_BYTES):
    command = git_args(root, *args)
    environment = {**os.environ, 'GIT_NO_LAZY_FETCH': '1', 'GIT_ALLOW_PROTOCOL': ''}
    timed_out = Event()
    own_group = os.name == 'posix'
    with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          start_new_session=own_group) as process:
        stop_lock = Lock()
        stop_requested = False

        def stop():
            nonlocal stop_requested
            with stop_lock:
                if stop_requested:
                    return
                stop_requested = True
                try:
                    if own_group:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                except PermissionError:
                    process.kill()

        def expire():
            timed_out.set()
            stop()

        timer = Timer(GIT_TIMEOUT, expire)
        timer.start()
        try:
            output = process.stdout.read(max_bytes + 1)
            if len(output) > max_bytes:
                stop()
                raise ValueError(f'Context Git {args[0]} output exceeds the byte limit')
            status = process.wait()
        finally:
            timer.cancel()
            if process.poll() is None:
                stop()
        if timed_out.is_set():
            raise subprocess.TimeoutExpired(command, GIT_TIMEOUT)
        if status not in accepted:
            raise ValueError(f'Context Git {args[0]} could not read the committed source')
    return output


def search(git_args, root, commit, scope, terms, limit, *, expected_sha256=None):
    """Rank exact text matches across source files in one commit and scope."""
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        raise ValueError('Context search requires a full Git commit ID')
    boundary = relative_path(scope)
    if git_output(git_args, root, 'cat-file', '-t', commit, max_bytes=64).strip() != b'commit':
        raise ValueError('Context search requires a Git commit')
    pinned = None
    if expected_sha256 is not None:
        pinned = git_output(git_args, root, 'cat-file', 'blob', f'{commit}:{scope}', max_bytes=BLOB_BYTES)
        if sha256(pinned).hexdigest() != expected_sha256:
            raise ValueError('Committed source bytes differ from the selected pin')

    patterns = [argument for term in terms for argument in ('-e', term)]
    result = git_output(git_args, root, 'grep', '-z', '-n', '-i', '-I', '-F', '-m', '24', '--no-color',
                        '--no-column', '--no-textconv', '--no-recurse-submodules', *patterns, commit, '--',
                        *([] if scope == '.' else [scope]), accepted=(0, 1))
    files = {}
    prefix = (commit + ':').encode()
    for match in GREP_LINE.finditer(result):
        source, number, content = match.groups()
        if not source.startswith(prefix):
            continue
        try:
            path = source[len(prefix):].decode()
            relative = relative_path(path)
        except ValueError:
            continue
        if not relative.is_relative_to(boundary) or (expected_sha256 is not None and path != scope):
            continue
        excerpt = content.decode('utf-8', errors='replace').strip()
        folded = excerpt.casefold()
        hits = {term for term in terms if term in folded}
        if not hits:
            continue
        candidate = files.setdefault(path, {'terms': set(), 'excerpt': '', 'line': 0, 'line_hits': 0})
        candidate['terms'].update(hits)
        if len(hits) > candidate['line_hits']:
            # Include the matching text even on a long minified or generated line.
            offset = max(0, min(folded.index(term) for term in hits) - 60)
            candidate.update(excerpt=excerpt[offset:offset + 260], line=int(number), line_hits=len(hits))
    ordered = sorted(files.items(), key=lambda pair: (-len(pair[1]['terms']), -pair[1]['line_hits'], pair[0]))
    matches = []
    for path, candidate in ordered[:limit]:
        content = pinned if pinned is not None else git_output(
            git_args, root, 'cat-file', 'blob', f'{commit}:{path}', max_bytes=BLOB_BYTES)
        offset = candidate['line'] - 1
        lines = content.decode('utf-8', errors='replace').split('\n')
        first = max(0, offset - 1)
        snippet = [{'line': index + 1, 'text': lines[index][:260]}
                   for index in range(first, min(len(lines), offset + 3))]
        matches.append({'path': path, 'commit': commit, 'sha256': sha256(content).hexdigest(),
                        'line': candidate['line'], 'excerpt': candidate['excerpt'],
                        'context': snippet, 'matched_terms': sorted(candidate['terms'])})
    return matches


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['search'])
    parser.add_argument('root', type=Path)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--scope', required=True)
    parser.add_argument('--query', required=True)
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args(argv)
    workspaces = runpy.run_path(str(Path(__file__).with_name('run-workspaces.py')))
    try:
        root = args.root.resolve(strict=True)
        if workspaces['local_git_text'](root, 'rev-parse', '--show-toplevel') != str(root):
            raise ValueError('Select the Git checkout root')
        matches = search(workspaces['local_git_args'], root, args.commit, args.scope,
                         query_terms(args.query, args.limit), args.limit)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps({'matches': matches}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
