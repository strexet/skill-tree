"""Relocate the one byte-owned legacy Director service without recreating its Git repositories."""
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import runpy
import socket
import sys
import uuid
from types import SimpleNamespace


D = SimpleNamespace(**runpy.run_path(str(Path(__file__).with_name('director-state.py'))))
B = D._bootstrap_helper()
JOURNAL = '.director-relocation.json'
MAINTENANCE = 'sources/skill-tree'
MAINTENANCE_MARKER = '.git/skill-tree-director-maintenance.json'
LOCATOR = '.git/skill-tree-runtime.json'
FUTURE = '.skill-tree/documents/future.json'


def relocated(path, old, new):
    path = Path(path)
    return new / path.relative_to(old) if path.is_relative_to(old) else path


def owned_path(root, relative):
    if relative == '.git' or relative.startswith('.git/'):
        admin = root / '.git'
        D._require(not admin.is_symlink(), 'The retained Git administration path is a symlink')
        return admin if relative == '.git' else D._safe_path(admin, relative.removeprefix('.git/'))
    return D._safe_path(root, relative)


def current_json(root, relative):
    path = owned_path(root, relative)
    return json.loads(path.read_bytes()) if path.is_file() else None


def worktrees(root):
    rows = D.WS.local_git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split(b'\0')
    return [Path(os.fsdecode(row.removeprefix(b'worktree '))) for row in rows if row.startswith(b'worktree ')]


def relocation_lock(relocation_id):
    return {'kind':'director-relocation', 'relocation_id':relocation_id,
            'pid':os.getpid(), 'host':socket.gethostname()}


def ensure_idle(root, relocation_id=None):
    paths = ['.setup-lock', '.skill-tree/.transaction.json',
             '.skill-tree/installation/.install-lock', '.skill-tree/installation/.journal.json',
             '.skill-tree/installation/.plugin-journal.json', '.skill-tree/installation/.staging',
             '.skill-tree/installation/.plugin-staging']
    writer = '.skill-tree/.writer-lock'
    if relocation_id is None:
        paths.append(writer)
    else:
        D._require(current_json(root, writer) == relocation_lock(relocation_id),
                   'The Director relocation no longer owns the writer barrier')
    D._require(all(not os.path.lexists(root / item) for item in paths),
               f'Finish or recover the existing operation before moving Director storage: {root}')
    state = current_json(root, FUTURE)
    D._require(isinstance(state, dict) and state.get('schema') == 3 and state.get('active_run') is None,
               'A verified schema-3 Director queue is required for relocation')
    registry = state.get('run_registry')
    D.WS.validate_registry(registry)
    D._require(all(D.WS.delivery_finished(run) for run in registry['runs'].values()) and not registry['claims']
               and not registry['resources'] and not state.get('task_progress'),
               f'Finish the retained Core work before moving Director storage: {root}')
    records = (
        ('.skill-tree/decisions/dg-*.json', {'accepted'}),
        ('.skill-tree/decisions/do-*.json', {'ready'}),
        ('.skill-tree/invocations/hc-*.json', {'complete', 'superseded'}),
    )
    for pattern, terminal in records:
        for file in root.glob(pattern):
            record = current_json(root, file.relative_to(root).as_posix())
            D._require(isinstance(record, dict) and record.get('phase', record.get('state')) in terminal,
                       'Reconcile the retained decision, orchestration or plugin invocation before relocation')


def inspect_repository(root, old, relocation_id):
    ensure_idle(root, relocation_id)
    queue, repo, owner = D._inspect_owner(root)
    D._require(Path(owner['git_common_dir']) == root / '.git', 'Relocate an ordinary owned Git repository')
    configured = D.WS.local_git(root, 'config', '--local', '--get', 'core.worktree', accepted=(0, 1))
    D._require(configured.returncode == 1, 'Resolve the custom Git worktree path before relocation')
    locator = current_json(root, LOCATOR)
    D._require(locator['canonical_root'] == str(root) and locator['queue_id'] == queue,
               'Director queue locator does not identify the inspected repository')
    head = D.WS.local_git_text(root, 'rev-parse', 'HEAD')
    paths = worktrees(root)
    D._require(paths and paths[0] == root and len(set(paths)) == len(paths), 'Unexpected Git worktree inventory')
    linked = []
    for path in paths[1:]:
        D._root(str(path))
        registration = D.WS.linked_registration(root, path)
        linked.append({'path': str(path), 'registration': registration.name,
                       'head': D.WS.local_git_text(path, 'rev-parse', 'HEAD')})
    return {'path': str(root.relative_to(old)), 'repo_id': repo, 'owner': owner, 'head': head,
            'locator': locator, 'linked': linked, 'future_sha256': D.WF.file_hash(root / FUTURE)}


def inspect_service(old, new, relocation_id=None):
    D._require(B.safe_directory(old) is not None and B.safe_directory(new) is None,
               'The old and new Director storage locations must not overlap existing data')
    product = D._setup_git_root(old.parent)
    if product is not None:
        tracked = D.WS.local_git(product, 'ls-files', '-z', '--', old.relative_to(product).as_posix())
        D._require(not tracked.stdout, 'Legacy Director storage overlaps tracked product files')
    settings = current_json(old, 'workspace.json')
    profile = current_json(old, '.skill-tree/installation/profile.json')
    D._require(isinstance(settings, dict) and settings.get('schema') == 1 and settings.get('kind') == 'director-workspace'
               and isinstance(profile, dict) and profile.get('flavor') == 'director' and profile.get('project_root') == str(old),
               'Inspect the owned Director workspace before relocation')
    for path in D._safe_path(old, '.skill-tree/director/runs').glob('dr-*.json'):
        run = current_json(old, path.relative_to(old).as_posix())
        D._require(all(dispatch.get('status') == 'recorded' for assignment in run['assignments'].values()
                       for dispatch in assignment['dispatches'].values()),
                   'Reconcile the original Director dispatch before relocation')
        D._require(not any(question.get('phase') in {'preparing', 'answer-recorded'}
                           for assignment in run['assignments'].values()
                           for question in assignment.get('questions', {}).values()),
                   'Reconcile the in-flight Director question delivery before relocation')
    repositories = [inspect_repository(old, old, relocation_id)]
    source = D._safe_path(old, MAINTENANCE)
    marker = None
    if source.exists():
        item = inspect_repository(source, old, relocation_id)
        marker = current_json(source, MAINTENANCE_MARKER)
        D._require(isinstance(marker, dict) and marker.get('schema') == 1 and marker.get('checkout') == str(source)
                   and marker.get('queue_id') == item['locator']['queue_id'] and marker.get('revision') == item['head'],
                   'Verify the original maintenance source identity before relocation')
        repositories.append(item)
    registry, bindings, _ = D.DirectorRegistry(old)._load()
    D._require(not registry or bindings is not None, 'Restore the original Director project bindings first')
    bound_roots = {}
    if bindings:
        areas = {item['queue_id']: item for item in registry['areas'].values()}
        sources = {item['locator']['queue_id']: item for item in repositories}
        for queue_id, owner in bindings['queues'].items():
            path = Path(owner['root'])
            if path.is_relative_to(old):
                D._require(queue_id in sources and sources[queue_id]['owner'] == owner
                           and sources[queue_id]['repo_id'] == areas[queue_id]['repo_id'],
                           'Director contains an unrecognized relocated queue binding')
                bound_roots[queue_id] = owner
    workspace = old.parent
    workspace_owner = D.WS.canonical(workspace) if registry and D._setup_git_root(workspace) == workspace else workspace
    co_located = False
    for area in registry['areas'].values() if registry else ():
        owner = bindings['queues'].get(area['queue_id'], {})
        if area['role'] != 'source-maintenance' and area['scope'] == '.' and owner.get('root') == str(workspace_owner):
            queue, repo, observed = D._inspect_owner(workspace)
            D._require(queue == area['queue_id'] and repo == area['repo_id'] and observed == owner,
                       'The original co-located project binding changed')
            co_located = True
    return {'schema': 1, 'old': str(old), 'new': str(new), 'identity': B.safe_directory(old),
            'co_located': co_located, 'repositories': repositories, 'maintenance': marker, 'bound_roots': bound_roots}


@contextmanager
def writer_barrier(root, old, new, relocation_id):
    writer = root / '.skill-tree/.writer-lock'
    fd = os.open(writer, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        identity = os.fstat(fd)
        os.write(fd, D.WF.dump(relocation_lock(relocation_id)).encode())
        os.fsync(fd)
        D._require(not os.path.lexists(root / '.skill-tree/installation/.install-lock'),
                   'Finish the original installation transaction before relocation')
        yield
    finally:
        os.close(fd)
        for candidate in (writer, relocated(writer, old, new)):
            if candidate.is_file() and not candidate.is_symlink() and os.path.samestat(identity, candidate.stat()):
                candidate.unlink()
                break


def reconcile_writer_locks(home, plan):
    for item in plan['repositories']:
        writer = owned_path(home / item['path'], '.skill-tree/.writer-lock')
        if not writer.exists():
            continue
        D._require(writer.is_file(), 'The retained writer lock is not an ordinary file')
        identity = writer.stat()
        ownership = json.loads(writer.read_bytes())
        D._require(isinstance(ownership, dict), 'Inspect the incomplete writer lock before resuming relocation')
        pid = ownership.get('pid')
        D._require(ownership.get('kind') == 'director-relocation' and ownership.get('relocation_id') == plan['relocation_id']
                   and ownership.get('host') == socket.gethostname() and type(pid) is int and pid > 0,
                   'Inspect the other workflow writer lock before resuming Director relocation')
        D._require(os.name != 'nt', f'Confirm the original relocation process {pid} has exited before clearing {writer}')
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            D._require(os.path.samestat(identity, writer.stat()), 'The retained relocation lock changed')
            writer.unlink()
        else:
            raise ValueError('The original Director relocation process still owns the writer lock')


def checked_journal(home, old, new):
    data = current_json(home, JOURNAL)
    if data is not None:
        D._require(isinstance(data, dict) and data.get('schema') == 1 and data.get('old') == str(old)
                   and data.get('new') == str(new) and data.get('identity') == B.safe_directory(home)
                   and isinstance(data.get('relocation_id'), str)
                   and str(uuid.UUID(data['relocation_id'])) == data['relocation_id'],
                   'The retained Director relocation identity changed')
        paths = [item['path'] for item in data['repositories']]
        D._require(paths in (['.'], ['.', MAINTENANCE]), 'The relocation includes an unknown repository')
    return data


def guarded_update(root, relative, before, after):
    actual = current_json(root, relative)
    D._require(actual in (before, after), f'Retained Director relocation record changed: {relative}')
    if actual != after:
        D.WS.atomic(owned_path(root, relative), after)


def repaired_repository(item, old, new):
    root = new / item['path']
    original = old / item['path']
    owner = item['owner']
    common = owned_path(root, '.git')
    D._require(B.safe_directory(common) == {key: owner[key] for key in ('device', 'inode')}
               and D.WF.file_hash(root / FUTURE) == item['future_sha256']
               and D.WS.local_git_text(root, 'rev-parse', 'HEAD') == item['head'],
               'The retained repository, Git head or canonical state changed during relocation')
    changed_paths = []
    for recorded in item['linked']:
        before = Path(recorded['path'])
        after = relocated(before, old, new)
        registration = recorded['registration']
        D._require(Path(registration).name == registration and registration not in ('', '..'),
                   'Unexpected Git worktree registration')
        registered = owned_path(root, f'.git/worktrees/{registration}')
        backlink = D._safe_path(registered, 'gitdir')
        checkout_marker = owned_path(D._root(str(after)), '.git')
        D._require((registered / backlink.read_text().strip()).resolve() in {before / '.git', after / '.git'}
                   and (checkout_marker.read_text().strip().startswith('gitdir: ')),
                   'The linked worktree changed before relocation repair')
        target = (after / checkout_marker.read_text().strip().removeprefix('gitdir: ')).resolve()
        D._require(target in {original / '.git/worktrees' / registration, registered},
                   'The linked checkout points outside the retained Git registration')
        changed_paths.append(after)
    if changed_paths:
        D.WS.local_git(root, 'worktree', 'repair', *changed_paths)
    D._require(worktrees(root) == [root, *changed_paths], 'Git worktree identities changed during relocation')
    for observed, recorded in zip(changed_paths, item['linked']):
        D._require(D.WS.linked_registration(root, observed).name == recorded['registration']
                   and D.WS.local_git_text(observed, 'rev-parse', 'HEAD') == recorded['head'],
                   'The relocated Git worktree no longer matches its original registration')
    locator = item['locator']
    destination = {**locator, 'canonical_root': str(root),
                   'worktrees': {key: str(relocated(value, old, new)) for key, value in locator['worktrees'].items()}}
    guarded_update(root, LOCATOR, locator, destination)
    queue, repo, _ = D._inspect_owner(root)
    D._require(queue == locator['queue_id'] and repo == item['repo_id'],
               'Relocation did not preserve the canonical queue and repository identities')


def repair(new, old, plan):
    for item in plan['repositories']:
        repaired_repository(item, old, new)
    if plan['maintenance'] is not None:
        root = new / MAINTENANCE
        marker = plan['maintenance']
        guarded_update(root, MAINTENANCE_MARKER, marker, {**marker, 'checkout': str(root)})
    if plan['bound_roots']:
        bindings = current_json(new, D.BINDINGS)
        current = bindings['queues']
        for queue, owner in plan['bound_roots'].items():
            root = relocated(owner['root'], old, new)
            got, _, observed = D._inspect_owner(root)
            expected = {**owner, 'root': str(root), 'git_common_dir': str(root / '.git')}
            D._require(got == queue and observed == expected and current.get(queue) in (owner, expected),
                       'The retained canonical queue binding changed')
            current[queue] = expected
        if current_json(new, D.BINDINGS) != bindings:
            D.WS.atomic(D._safe_path(new, D.BINDINGS), bindings)


def run(mode, workspace):
    workspace = D._root(workspace)
    old = D._safe_path(workspace, D.LEGACY_DIRECTOR_HOME.as_posix())
    new = D._safe_path(workspace, D.DIRECTOR_HOME.as_posix())
    D._require(not (old.exists() and new.exists()), 'Resolve the conflicting Director storage locations before relocation')
    home = old if old.is_dir() else new
    D._require(home.is_dir(), 'An existing Director workspace is required for relocation')
    if mode == 'inspect':
        return (checked_journal(home, old, new) or inspect_service(old, new))['co_located']
    with B.lock(home):
        plan = checked_journal(home, old, new)
        if mode == 'finish':
            D._require(home == new and plan is not None, 'The original relocation journal is unavailable')
        if plan is not None:
            reconcile_writer_locks(home, plan)
        if home == old:
            observed = inspect_service(old, new)
            if plan is None:
                plan = {**observed, 'relocation_id': str(uuid.uuid4())}
                D.WS.atomic(old / JOURNAL, plan, exclusive=True)
            else:
                D._require(plan == {**observed, 'relocation_id': plan['relocation_id']},
                           'The prepared Director relocation inputs changed')
        else:
            D._require(plan is not None, 'The original relocation journal is unavailable')
        with ExitStack() as barriers:
            for item in plan['repositories']:
                barriers.enter_context(writer_barrier(home / item['path'], old, new, plan['relocation_id']))
            if home == old:
                try:
                    locked = inspect_service(old, new, plan['relocation_id'])
                    D._require(plan == {**locked, 'relocation_id':plan['relocation_id']},
                               'The Director relocation inputs changed while acquiring writer barriers')
                except (ValueError, OSError, KeyError, TypeError):
                    if checked_journal(old, old, new) == plan:
                        (old / JOURNAL).unlink()
                    raise
                old.rename(new)
            repair(new, old, plan)
            if mode == 'finish':
                (new / JOURNAL).unlink()
    return plan['co_located']


if __name__ == '__main__':
    try:
        mode, workspace = sys.argv[1:]
        D._require(mode in ('inspect', 'move', 'finish'), 'Select a supported Director relocation phase')
        print(json.dumps({'co_located': run(mode, workspace)}))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'Director storage relocation: {error}', file=sys.stderr)
        raise SystemExit(2)
