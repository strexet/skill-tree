#!/usr/bin/env python3
"""Git workspaces, canonical queue routing and compatible multi-run metadata."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import tempfile
from threading import Timer
import uuid

class RunError(ValueError):
    pass

TERMINAL = {'local-result', 'merged'}

def delivery_finished(run):
    delivery=run.get('delivery',{})
    if local_merge_order(run):
        integration = delivery.get('local_integration')
        if not isinstance(integration, dict):
            return False
        merge, admission, validation = (integration.get(key) for key in ('merge', 'target_admission', 'validation'))
        if not all(isinstance(item, dict) for item in (merge, admission, validation)):
            return False
        def git_object(value):
            return isinstance(value, str) and re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', value) is not None

        def sha256(value):
            return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None

        parents, checks, evidence = merge.get('parents'), validation.get('checks'), validation.get('evidence')
        return (delivery.get('implementation') == 'completed' and delivery.get('status') == 'merged'
                and delivery.get('order_completed') is True
                and git_object(merge.get('commit')) and git_object(merge.get('tree'))
                and isinstance(parents, list) and len(parents) == 2 and all(map(git_object, parents))
                and admission.get('merge_commit') == validation.get('merge_commit') == merge['commit']
                and sha256(admission.get('profile_identity'))
                and validation.get('profile_identity') == admission['profile_identity']
                and isinstance(checks, list) and bool(checks)
                and all(isinstance(item, dict) and type(item.get('exit_code')) is int and item['exit_code'] == 0 for item in checks)
                and isinstance(evidence, list) and len(evidence) == 1 and isinstance(evidence[0], dict)
                and isinstance(evidence[0].get('path'), str) and sha256(evidence[0].get('sha256')))
    return delivery.get('status') in TERMINAL or (delivery.get('status')=='pr-ready' and not delivery.get('authorization',{}).get('merge'))

def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *map(str, args)], capture_output=True, text=True, timeout=45)
    if result.returncode:
        # Remote errors can contain credentials. Keep diagnostics deliberately bounded.
        raise RunError('Git operation failed: ' + ' '.join(str(a) for a in args[:2]))
    return result.stdout.strip()

def common_dir(root):
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'], capture_output=True, text=True, timeout=5)
    return (Path(root)/result.stdout.strip()).resolve() if result.returncode == 0 else None

def runtime_file(root):
    common = common_dir(root)
    return common/'skill-tree-runtime.json' if common else None

def runtime(root):
    path = runtime_file(root)
    if not path or not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or not isinstance(data.get('worktrees'), dict):
        raise RunError('Unsupported machine-local run locator; explicit recovery required')
    return data

def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='skill-tree-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def canonical(root):
    root = Path(root).resolve()
    data = runtime(root)
    if not data:
        return root
    owner = Path(data['canonical_root'])
    if not owner.is_dir() or common_dir(owner) != common_dir(root):
        raise RunError('Canonical queue identity is unavailable; explicit locator recovery required')
    if git(root, 'rev-parse', '--show-toplevel') != str(root):
        raise RunError('Select the exact repository/worktree root')
    return owner

def setup(store, payload):
    """Explicit schema-2 extension; preserve the complete single-run record."""
    if not common_dir(store.root):raise RunError('Workspace setup requires a Git repository')
    if store.root != store.source_root:
        raise RunError('Run setup requires the canonical checkout')
    with store.lock():
        text = store.text()
        raw=json.loads(store.state.read_text()) if store.state.exists() else {}
        if raw.get('run_registry'):
            if payload.get('confirm_queue_id')!=raw['run_registry']['queue_id']:raise RunError('Run registry exists; use resume or explicit locator recovery')
            raw['schema']=3;store.commit({'.skill-tree/documents/future.json':json.dumps(raw,indent=2,sort_keys=True)+'\n'});return raw['run_registry']
        state = store.load(text)
        old = deepcopy(state['active_run'])
        if old and payload.get('adopt_run_id') != old['id']:
            raise RunError('Existing checkpoint requires explicit adopt_run_id and workspace identity')
        registry = {'schema': 1, 'queue_id': 'Q-'+str(uuid.uuid4()), 'runs': {}, 'claims': {}, 'resources': {}}
        if old:
            registry['runs'][old['id']] = old
            old['workspace'] = workspace_identity(store, old['id'], payload, existing=True)
            old['delivery'] = {'implementation': 'in-progress', 'publication': 'not-requested', 'status': 'implementation-in-progress', 'authorization': {}}
        state['active_run'] = None; state['run_registry'] = registry
        store.save(text, state)
        locator = {'schema': 1, 'queue_id': registry['queue_id'], 'canonical_root': str(store.root), 'worktrees': {}}
        if old:
            locator['worktrees'][old['id']] = str(Path(payload['worktree']).resolve())
        atomic(runtime_file(store.root), locator)
        return registry

def validate_hook_references(run):
    values=run.get('hook_chains',[])
    if not isinstance(values,list) or any(not isinstance(value,str) or not re.fullmatch(r'HC-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value) for value in values) or len(values)!=len(set(values)):raise RunError('Controller hook references require exact distinct chain identities')
    return values

def register_hook_reference(run,chain_id,task_ids=()):
    validate_hook_references(run)
    if not isinstance(chain_id,str) or not re.fullmatch(r'HC-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',chain_id):raise RunError('An exact hook chain identity is required')
    scope=set(run.get('admitted_task_ids',run.get('snapshot',[])))|set(run.get('required_ids',[]))
    if set(task_ids)-scope:raise RunError('Hook registration exceeds the recorded controller task scope')
    result=deepcopy(run);refs=result.setdefault('hook_chains',[])
    if chain_id not in refs:refs.append(chain_id)
    return result

def validate_registry(registry):
    if not isinstance(registry, dict) or registry.get('schema') != 1 or not re.fullmatch(r'Q-[a-f0-9-]{36}', registry.get('queue_id', '')):
        raise RunError('Unsupported run registry; explicit recovery required')
    if any(not isinstance(registry.get(k), dict) for k in ['runs', 'claims', 'resources']):
        raise RunError('Corrupt run registry collections')
    for rid, run in registry['runs'].items():
        validate_hook_references(run)
        if run.get('id') != rid:
            raise RunError('Run registry identity conflict')
    for tid, rid in registry['claims'].items():
        if rid not in registry['runs'] or tid not in registry['runs'][rid]['admitted_task_ids']:
            raise RunError('Task claim identity conflict')

def project(store, state):
    registry = state.get('run_registry')
    if not registry:
        return state
    validate_registry(registry)
    locator = runtime(store.root)
    if not locator or locator['queue_id'] != registry['queue_id']:
        raise RunError('Run registry locator mismatch; explicit recover-locator required')
    rid = store.run_id
    if not rid and store.source_root != store.root:
        matches = [key for key, path in locator['worktrees'].items() if Path(path).resolve() == store.source_root]
        if len(matches) != 1:
            raise RunError('Worktree identity is absent or ambiguous; explicit recovery required')
        rid = matches[0]
    if not rid:
        choices = [key for key, run in registry['runs'].items() if not delivery_finished(run)]
        if len(choices) > 1 and not store.allow_unselected:
            raise RunError('Multiple runs exist; select --run-id explicitly')
        rid = choices[0] if len(choices) == 1 else None
    if rid and rid not in registry['runs']:
        raise RunError('Unknown run ID')
    store.selected_run_id = rid
    state['active_run'] = registry['runs'].get(rid)
    if rid:
        path = locator['worktrees'].get(rid)
        if path:
            store.source_root = Path(path).resolve()
    return state

def persist(store, state):
    result = deepcopy(state)
    registry = result.get('run_registry')
    if not registry:
        return result
    result['schema']=3
    selected = result.get('active_run')
    if selected:
        registry['runs'][selected['id']] = selected
    result['active_run'] = None
    done = {o['task_id'] for o in store.outcomes() if o['disposition'] == 'completed'}
    claims = {}
    for rid, run in registry['runs'].items():
        if run.get('delivery', {}).get('implementation') == 'completed':
            continue
        for tid in run['admitted_task_ids']:
            if tid in done:
                continue
            if tid in claims and claims[tid] != rid:
                raise RunError('Task claimed by another run: '+tid)
            claims[tid] = rid
    registry['claims'] = claims
    validate_registry(registry)
    return result

def ensure_workspace(store, run, allow_dirty=True):
    spec = run.get('workspace')
    if not spec:
        if common_dir(store.root):
            raise RunError('Git controller requires an explicitly adopted workspace; run workspace-setup')
        return
    data = runtime(store.root); path = data['worktrees'].get(run['id']) if data else None
    if not path or not Path(path).is_dir():
        raise RunError('Recorded worktree missing; explicit recover-workspace required')
    if spec['repo_id'] != repo_id(store.root) or common_dir(path) != common_dir(store.root):
        raise RunError('Worktree repository identity conflict')
    if git(path, 'symbolic-ref', '--quiet', '--short', 'HEAD') != spec['branch']:
        raise RunError('Worktree branch identity conflict')
    actual_remote=git(store.root, 'remote', 'get-url', spec['remote'])
    if hashlib.sha256(actual_remote.encode()).hexdigest() != spec.get('remote_id',hashlib.sha256(spec.get('remote_url','').encode()).hexdigest()):
        raise RunError('Remote identity changed; explicit recovery required')
    unfinished(path)
    if not allow_dirty and git(path, 'status', '--porcelain'):
        raise RunError('Dirty worktree; preserve changes and checkpoint before publication')
    store.source_root = Path(path).resolve()

def repo_id(root):
    # Stable across checkout moves; no machine paths in portable records.
    return hashlib.sha256(git(root, 'rev-list', '--max-parents=0', 'HEAD').encode()).hexdigest()

def unfinished(root):
    for item in ['MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-apply', 'rebase-merge', 'BISECT_START']:
        location = Path(git(root, 'rev-parse', '--git-path', item))
        if not location.is_absolute():
            location = Path(root)/location
        if location.exists():
            raise RunError('Unfinished Git operation: '+item)

def branch(root, name):
    if not isinstance(name, str) or name.startswith('-'):
        raise RunError('Invalid branch name')
    git(root, 'check-ref-format', '--branch', name)
    return name

def workspace_identity(store, rid, payload, existing=False):
    remote = payload.get('remote', 'origin'); base = branch(store.root, payload.get('base_branch', 'develop'))
    if remote.startswith('-') or remote not in git(store.root, 'remote').splitlines():
        raise RunError('Unknown remote')
    url = git(store.root, 'remote', 'get-url', remote)
    if re.search(r'://[^/@]+:[^/@]+@', url) or '?' in url:
        raise RunError('Credential-bearing remote URL cannot enter metadata')
    unfinished(store.root)
    if payload.get('local_base'):
        if not payload.get('local_base_authorization'):
            raise RunError('A local-only base requires explicit owner scope')
        ref = 'refs/heads/'+base
    else:
        git(store.root, 'fetch', '--no-tags', remote)
        ref = 'refs/remotes/'+remote+'/'+base
    commit = git(store.root, 'rev-parse', '--verify', ref+'^{commit}')
    working = branch(store.root, payload.get('branch', payload.get('branch_prefix', 'codex/')+rid.lower()))
    if working == base:
        raise RunError('Working branch differs from base_branch')
    if existing:
        path = Path(payload['worktree']).resolve()
        if common_dir(path) != common_dir(store.root) or git(path, 'symbolic-ref', '--short', 'HEAD') != working:
            raise RunError('Adopted worktree/branch identity mismatch')
        if git(path, 'merge-base', '--is-ancestor', commit, 'HEAD'):
            raise RunError('Adopted workspace lacks the declared base')
    return {'repo_id': repo_id(store.root), 'remote': remote, 'remote_id': hashlib.sha256(url.encode()).hexdigest(), 'base_branch': base, 'base_commit': commit, 'branch': working, 'worktree_id': rid, 'local_base': bool(payload.get('local_base')), **({'local_base_authorization':payload['local_base_authorization']} if payload.get('local_base') else {})}

def provision(store, run, payload):
    """Reserve claims first; interrupted provisioning retains the same run ID."""
    spec = workspace_identity(store, run['id'], payload)
    common = common_dir(store.root)
    path = Path(payload.get('worktree', str(common/'skill-tree-worktrees'/run['id'].lower()))).resolve()
    if path.exists():
        raise RunError('Worktree destination exists; explicit recovery required')
    if git(store.root,'for-each-ref','--format=%(refname)','refs/heads/'+spec['branch']):raise RunError('Working branch already exists; select the retained run or explicit recovery')
    run['workspace'] = spec
    run['delivery'] = {'implementation': 'in-progress', 'publication': 'not-requested', 'status': 'implementation-in-progress', 'authorization': payload.get('delivery_authorization', {})}
    run['workspace_state'] = 'reserved'
    return path

def create_reserved(store, run, path):
    data = runtime(store.root)
    data['worktrees'][run['id']] = str(path); atomic(runtime_file(store.root), data)
    git(store.root, 'worktree', 'add', '-b', run['workspace']['branch'], path, run['workspace']['base_commit'])
    run['workspace_state'] = 'ready'
    store.source_root = path

def recover_locator(store, payload):
    """Explicitly repair local paths only; never rewrite portable checkpoints."""
    with store.lock():
        state = json.loads(store.state.read_text()); registry = state.get('run_registry'); validate_registry(registry)
        if payload.get('queue_id') != registry['queue_id']:
            raise RunError('Recovery requires the exact queue ID')
        mapping = payload.get('worktrees', {})
        required={rid for rid,run in registry['runs'].items() if not delivery_finished(run)}
        if not isinstance(mapping,dict) or not required.issubset(mapping) or set(mapping)-set(registry['runs']):
            raise RunError('Recovery requires every unfinished retained run locator and rejects unknown run IDs')
        for rid, value in mapping.items():
            path = Path(value).resolve(); run = registry['runs'][rid]
            if common_dir(path) != common_dir(store.root) or git(path, 'symbolic-ref', '--short', 'HEAD') != run['workspace']['branch']:
                raise RunError('Recovery workspace identity mismatch')
        atomic(runtime_file(store.root), {'schema': 1, 'queue_id': registry['queue_id'], 'canonical_root': str(store.root), 'worktrees': mapping})
        return {'recovered': registry['queue_id']}

def resource(store, payload):
    with store.lock():
        text = store.text(); state = store.load(text); run = state['active_run']; registry = state.get('run_registry')
        if not registry or not run:
            raise RunError('A selected registered run is required')
        key = payload.get('resource')
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9:/._-]*', key):
            raise RunError('Explicit stable resource identity required')
        previous = registry['resources'].get(key)
        if payload.get('release'):
            if not previous or previous['run_id'] != run['id'] or previous['token'] != payload.get('token'):
                raise RunError('Resource release requires the owning run and token')
            del registry['resources'][key]; result = {'released': key}
        else:
            if previous:
                raise RunError('Resource already claimed; inspect owner and cleanup before explicit release')
            result = {'run_id': run['id'], 'token': str(uuid.uuid4()), 'pid': os.getpid(), 'host': socket.gethostname(), 'purpose': payload.get('purpose', key)}
            registry['resources'][key] = result
        store.save(text, state); return result

@contextmanager
def publication_lock(root, remote, target):
    path = common_dir(root)/('skill-tree-publication-'+hashlib.sha256((remote+'\0'+target).encode()).hexdigest()+'.lock')
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RunError('Publication/merge lock exists; inspect owner before explicit recovery') from exc
    try:
        os.write(fd, json.dumps({'pid': os.getpid(), 'host': socket.gethostname()}).encode()); os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)

def local_merge_order(run):
    authorization = run.get('delivery', {}).get('authorization', {})
    return authorization.get('pr') is False and authorization.get('merge') is True


def local_merge_target(root, run):
    authorization = run.get('delivery', {}).get('authorization', {})
    workspace = run.get('workspace', {})
    if authorization.get('mode', 'local-merge') != 'local-merge':
        raise RunError('Local merge requires the recorded local-merge delivery order')
    target = branch(root, authorization.get('target_branch'))
    if workspace.get('base_branch') != target or workspace.get('branch') == target:
        raise RunError('Local merge requires the exact authorized base target and separate source branch')
    return target


def local_git_environment():
    overrides = {'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY',
                 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT'}
    if overrides.intersection(os.environ):
        raise RunError('Local delivery requires the recorded Git environment without repository or index overrides')


def local_git_args(root, *args):
    local_git_environment()
    return ['git', '--no-replace-objects', '--no-optional-locks', '--literal-pathspecs', '-C', str(root),
            '-c', 'core.fsmonitor=false', '-c', 'diff.autoRefreshIndex=false', *map(str, args)]


def local_git(root, *args, accepted=(0,), index=None):
    environment = None if index is None else {**os.environ, 'GIT_INDEX_FILE': str(index)}
    result = subprocess.run(local_git_args(root, *args), env=environment, capture_output=True, timeout=45)
    if result.returncode not in accepted:
        raise RunError('Local Git operation failed: ' + str(args[0]))
    return result


def local_git_text(root, *args):
    return local_git(root, *args).stdout.decode('utf-8').strip()


def local_git_paths(root, *args):
    raw = local_git(root, *args).stdout
    try:
        return set(raw.decode('utf-8').split('\0')[:-1])
    except UnicodeError as exc:
        raise RunError('Local integration requires unambiguous UTF-8 Git paths') from exc


def local_overlap(left, right):
    return left == right or left.startswith(right + '/') or right.startswith(left + '/')


def local_source_identity(store, run):
    local_git_environment()
    ensure_workspace(store, run)
    workspace = run['workspace']
    root = store.source_root
    head = local_git_text(root, 'rev-parse', '--verify', 'HEAD^{commit}')
    reference = 'refs/heads/' + workspace['branch']
    if local_git_text(root, 'symbolic-ref', 'HEAD') != reference or local_git_text(root, 'rev-parse', '--verify', reference) != head:
        raise RunError('Local integration source branch or head changed')
    return {
        'repository': workspace['repo_id'], 'source_ref': reference, 'source_head': head,
        'source_tree': local_git_text(root, 'rev-parse', head + '^{tree}'),
    }


def local_target_head(store, run):
    target = local_merge_target(store.root, run)
    if store.root == store.source_root or common_dir(store.root) != common_dir(store.source_root):
        raise RunError('The canonical target and registered source must be distinct worktrees of one repository')
    unfinished(store.root)
    ref = 'refs/heads/' + target
    if local_git_text(store.root, 'symbolic-ref', 'HEAD') != ref:
        raise RunError('The canonical worktree does not have the authorized target branch checked out')
    head = local_git_text(store.root, 'rev-parse', '--verify', ref + '^{commit}')
    if local_git_text(store.root, 'rev-parse', '--verify', 'HEAD^{commit}') != head:
        raise RunError('The canonical target HEAD and branch ref disagree')
    return ref, head


def local_worktree_dirt(root):
    staged = local_git_paths(root, 'diff', '--cached', '--name-only', '--no-renames', '-z', '--')
    hidden = local_git(root, 'ls-files', '-v', '-z').stdout.split(b'\0')
    if staged or any(item and (item[:1].islower() or item.startswith(b'S ')) for item in hidden):
        raise RunError('Local integration requires a clean, fully visible Git index')
    changed = local_git_paths(root, 'diff', '--name-only', '--no-renames', '-z', '--')
    others = local_git_paths(root, 'ls-files', '--others', '--exclude-standard', '-z')
    return changed | others


def local_unchanged_file(root, relative):
    path = root / relative
    if path.is_symlink() or not path.is_file():
        return False
    entries = local_git(root, 'ls-files', '--stage', '-z', '--', relative).stdout.split(b'\0')[:-1]
    if len(entries) != 1:
        return False
    details, _ = entries[0].split(b'\t', 1)
    mode, indexed, stage = details.split()
    expected_mode = b'100755' if path.stat().st_mode & stat.S_IXUSR else b'100644'
    if stage != b'0' or mode != expected_mode:
        return False
    # The index stat cache may be stale even when the file bytes are unchanged.
    # Read the blob identity without refreshing the index or running Git filters.
    current = local_git(root, 'hash-object', '--no-filters', '--', relative).stdout.strip()
    return current == indexed


def local_incoming(root, target_head, source_head):
    return local_git_paths(root, 'diff', '--name-only', '--no-renames', '-z', target_head, source_head, '--')


def local_preflight_collisions(root, incoming, dirt):
    ignored = local_git_paths(root, 'ls-files', '--others', '--ignored', '--exclude-standard', '-z')
    paths = dirt | ignored
    # An empty ignored directory is absent from ls-files, and a symlink
    # ancestor must not be followed during preflight.
    tracked = local_git_paths(root, 'ls-files', '-z')
    for relative in incoming:
        if any(local_overlap(relative, path) for path in paths):
            raise RunError('Incoming path has a tracked or untracked worktree collision: ' + repr(relative))
        parts = relative.split('/')
        for index in range(1, len(parts) + 1):
            component = '/'.join(parts[:index])
            actual = root / component
            if actual.is_symlink():
                raise RunError('Incoming path has a symlink obstruction: ' + repr(component))
            if index == len(parts) and component not in tracked and actual.exists():
                if not actual.is_dir() or not any(path.startswith(component + '/') for path in tracked):
                    raise RunError('Incoming path has an untracked obstruction: ' + repr(component))


def local_merge_base(store, run, source, target_head):
    if target_head != run['workspace']['base_commit'] or target_head == source['source_head']:
        raise RunError('The authorized target moved, diverged or has no incoming source commit')
    result = local_git(store.root, 'merge-base', '--is-ancestor', target_head, source['source_head'], accepted=(0, 1))
    if result.returncode:
        raise RunError('The authorized target must be an ancestor of the reviewed source')


def local_merge_receipt(root, preparation, current_head):
    if current_head == preparation['target_head']:
        raise RunError('The exact prepared local merge has not occurred')
    parents = local_git_text(root, 'show', '-s', '--format=%P', current_head).split()
    if parents != [preparation['target_head'], preparation['source_head']]:
        raise RunError('The target does not have the exact prepared two-parent local merge')
    tree = local_git_text(root, 'rev-parse', current_head + '^{tree}')
    if tree != preparation['source_tree']:
        raise RunError('The local merge tree does not match the reviewed incoming source tree')
    return {'commit': current_head, 'parents': parents, 'tree': tree}


def local_git_policy(root):
    for key in ('commit.gpgSign', 'merge.verifySignatures'):
        result = local_git(root, 'config', '--type=bool', '--get', key, accepted=(0, 1))
        if result.returncode == 0 and result.stdout.strip() != b'false':
            raise RunError('Local merge requires separate handling of the enabled Git signing policy: ' + key)
    target = local_git_text(root, 'symbolic-ref', '--short', 'HEAD')
    options = local_git(root, 'config', '--get-all', 'branch.' + target + '.mergeOptions', accepted=(0, 1))
    if options.stdout.strip():
        raise RunError('Local merge is blocked by branch-specific Git merge options')
    configured = local_git(root, 'config', '--path', '--get', 'core.hooksPath', accepted=(0, 1))
    if configured.returncode == 0:
        value = configured.stdout.decode('utf-8').rstrip('\n')
        if not value:
            raise RunError('Local merge requires an unambiguous Git hook directory')
        hooks = root / value
    else:
        hooks = Path(local_git_text(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks'))
    for name in ('pre-merge-commit', 'prepare-commit-msg', 'commit-msg', 'post-commit',
                 'post-merge', 'reference-transaction', 'post-index-change'):
        location = hooks / name
        if location.is_file() and os.access(location, os.X_OK):
            raise RunError('Local merge is blocked by an executable Git hook: ' + name)


@contextmanager
def local_git_lock(path):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise RunError('An existing Git lock requires an idle checkout: ' + path.name) from error
    os.close(fd)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


@contextmanager
def local_ref_transaction(root, hooks, source_ref, source_head, target_ref, target_head, merge):
    args = local_git_args(root, '-c', f'core.hooksPath={hooks}', 'update-ref', '-m',
                          'Skill Tree local merge', '--stdin')
    with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True) as process:
        timer = Timer(45, process.terminate)
        timer.daemon = True
        timer.start()
        try:
            commands = ('start\noption no-deref\n'
                        f'verify {source_ref} {source_head}\noption no-deref\n'
                        f'update {target_ref} {merge} {target_head}\nprepare\n')
            process.stdin.write(commands)
            process.stdin.flush()
            if process.stdout.readline() != 'start: ok\n' or process.stdout.readline() != 'prepare: ok\n':
                raise RunError('The exact local source or target ref could not be locked for integration')
        finally:
            timer.cancel()
        try:
            yield process
        finally:
            if not process.stdin.closed:
                # EOF aborts an uncommitted prepared transaction and releases its locks.
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)


def run_local_merge(root, source_root, preparation):
    source_ref, source_head = preparation['source_ref'], preparation['source_head']
    target_ref, target_head = preparation['target_ref'], preparation['target_head']
    local_git_policy(root)
    if any(Path(local_git_text(path, 'rev-parse', '--show-toplevel')).resolve() != path
           for path in (root, source_root)):
        raise RunError('Protected local merge requires the recorded source and target Git worktrees')
    storage = local_git(root, 'config', '--get', 'extensions.refStorage', accepted=(0, 1)).stdout.strip()
    if storage not in (b'', b'files'):
        raise RunError('Protected local merge requires a files-backed Git ref store')
    head_path = Path(local_git_text(root, 'rev-parse', '--path-format=absolute', '--git-path', 'HEAD'))
    index_path = Path(local_git_text(root, 'rev-parse', '--path-format=absolute', '--git-path', 'index'))
    if head_path.is_symlink() or index_path.is_symlink() or not index_path.is_file():
        raise RunError('Protected local merge requires ordinary Git HEAD and index paths')
    with local_git_lock(index_path.with_suffix('.lock')), local_git_lock(head_path.with_suffix('.lock')):
        if (local_git_text(root, 'symbolic-ref', '--no-recurse', 'HEAD') != target_ref
                or local_git_text(root, 'rev-parse', '--verify', target_ref) != target_head):
            raise RunError('The exact prepared target branch or head changed before integration')
        unfinished(root)
        local_git_policy(root)
        dirt = {path for path in local_worktree_dirt(root) if not local_unchanged_file(root, path)}
        local_preflight_collisions(root, preparation['incoming'], dirt)
        with tempfile.TemporaryDirectory(prefix='skill-tree-local-merge-', dir=index_path.parent) as workspace:
            hooks = Path(workspace) / 'hooks'
            hooks.mkdir()
            index = Path(workspace) / 'index'
            shutil.copy2(index_path, index)
            merge = local_git_text(root, 'commit-tree', preparation['source_tree'], '--no-gpg-sign',
                                   '-p', target_head, '-p', source_head, '-m', f'Merge {source_ref} into {target_ref}')
            # Run the ref transaction from the distinct source worktree so Git
            # does not try to acquire the canonical worktree's protected HEAD lock.
            with local_ref_transaction(source_root, hooks, source_ref, source_head, target_ref, target_head, merge) as process:
                if any(local_git(root, 'symbolic-ref', '--quiet', '--no-recurse', ref, accepted=(0, 1)).returncode == 0
                       for ref in (source_ref, target_ref)):
                    raise RunError('Protected local merge requires direct prepared Git branch refs')
                checkout = ('--work-tree', root, '-c', f'core.hooksPath={hooks}', 'read-tree', '-u', '-m')
                local_git(root, *checkout, '-n', target_head, merge, index=index)
                local_git(root, *checkout, target_head, merge, index=index)
                try:
                    output, _ = process.communicate('commit\n', timeout=45)
                    if process.returncode or output != 'commit: ok\n':
                        raise RunError('The exact prepared Git ref transaction did not confirm the merge')
                except (OSError, subprocess.SubprocessError, RunError, KeyboardInterrupt):
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=5)
                    observed = local_git_text(root, 'rev-parse', '--verify', target_ref)
                    if observed == merge:
                        os.replace(index, index_path)
                    elif observed == target_head:
                        local_git(root, *checkout, merge, target_head, index=index)
                    raise
                os.replace(index, index_path)


def environment(store, payload=None):
    """Inspect prerequisites without reading secret contents or launching processes."""
    payload = payload or {}; root = store.source_root
    state = store.load(); run = state['active_run']; registry = state.get('run_registry')
    if run:ensure_workspace(store,run)
    profile_path=root/'.skill-tree/installation/profile.json'
    profile=json.loads(profile_path.read_text()) if profile_path.exists() else {'flavor':run.get('admission',{}).get('flavor','general') if run else 'general','facts':{}}
    declaration=root/'.skill-tree/worktree-profile.json'
    policy=json.loads(declaration.read_text()) if declaration.exists() else {'schema':1}
    actual=hashlib.sha256(declaration.read_bytes()).hexdigest() if declaration.exists() else None
    if profile_path.exists() and profile.get('inputs',{}).get('.skill-tree/worktree-profile.json')!=actual:raise RunError('Worktree environment declaration changed; review and refresh the exact worktree profile')
    if policy.get('schema')!=1:raise RunError('Unsupported worktree environment profile')
    flavor=profile['flavor'];defaults={'general':['build','dist','.cache'],'web':['node_modules','dist','build','.next','.cache'],'unity':['Library','Temp','Logs','obj','Builds']}
    missing=[]
    for rel in policy.get('required_files',[]):
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise RunError('Environment prerequisites require repository-relative paths')
        if not (root/path).is_file():missing.append(rel)
    directories=list(dict.fromkeys(defaults[flavor]+policy.get('isolated_directories',[])))
    for rel in directories:
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise RunError('Mutable directories require repository-relative paths')
        actual=root/path
        if actual.exists() and not actual.resolve().is_relative_to(root):raise RunError('Concurrent mutable directory sharing lacks verified support: '+rel)
    required_resources=list(policy.get('exclusive_resources',[]))
    if payload.get('runtime') and flavor=='unity' and not required_resources:
        raise RunError('Unity runtime requires an explicit Editor/MCP/save/fixture resource policy')
    for key in required_resources if payload.get('runtime') else []:
        claim=registry['resources'].get(key) if registry else None
        if not claim or not run or claim['run_id']!=run['id']:raise RunError('Runtime prerequisite requires exclusive resource: '+key)
    if missing:raise RunError('Missing environment prerequisites: '+', '.join(missing))
    return {'flavor':flavor,'project_root':str(root),'isolated_directories':directories,'required_files':policy.get('required_files',[]),'exclusive_resources':required_resources,'editor_version':profile.get('facts',{}).get('editor'),'secrets_read':False,'runtime_qualified':False}

def recover_workspace(store,payload):
    if not payload.get('resolution'):
        raise RunError('Explicit recovery requires preserved-work evidence and the resolved condition')
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run or not run.get('workspace'):raise RunError('Select the retained run before workspace recovery')
        data=runtime(store.root);rid=run['id'];spec=run['workspace']
        requested=payload.get('worktree') or data['worktrees'].get(rid)
        if not requested:raise RunError('Recovery requires the recorded or explicitly relocated worktree path')
        path=Path(requested).resolve()
        if path.exists():
            if common_dir(path)!=common_dir(store.root) or git(path,'symbolic-ref','--short','HEAD')!=spec['branch']:
                raise RunError('Recovery never switches a conflicting worktree branch')
        else:
            # Prune never runs automatically; stale Git registrations require an explicit Git repair.
            refs=git(store.root,'for-each-ref','--format=%(refname)','refs/heads/'+spec['branch']).splitlines()
            if 'refs/heads/'+spec['branch'] in refs:
                git(store.root,'worktree','add',path,spec['branch'])
            else:
                if run.get('workspace_state')!='reserved':raise RunError('Recorded source branch is missing; recover commits/dirty work before reconstruction')
                git(store.root,'worktree','add','-b',spec['branch'],path,spec['base_commit'])
        data['worktrees'][rid]=str(path);atomic(runtime_file(store.root),data)
        run['workspace_state']='ready';run.setdefault('workspace_recoveries',[]).append({'resolution':payload['resolution'],'branch':spec['branch']})
        ensure_workspace(store,run);store.save(text,state);return run

def portable_envelope(value,run_root,queue_root):
    """Replace machine paths with explicit logical roots or opaque locator references."""
    references=set();local_values=set()
    def visit(item):
        if isinstance(item,dict):
            result={}
            for key,value in item.items():
                if key=='remote_url' and isinstance(value,str):
                    token=hashlib.sha256(value.encode()).hexdigest();local_values.add(token);result[key]='{local_value:'+token+'}'
                else:result[key]=visit(value)
            return result
        if isinstance(item,list):return [visit(value) for value in item]
        if not isinstance(item,str):return item
        for path,label in [(str(run_root),'{run_root}'),(str(queue_root),'{canonical_root}')]:
            if item==path or item.startswith(path+'/'):return label+item[len(path):]
        if Path(item).is_absolute():
            key=hashlib.sha256(item.encode()).hexdigest();references.add(key);return '{local_path:'+key+'}'
        return item
    result=visit(value);result['local_path_references']=sorted(references);result['local_value_references']=sorted(local_values);return result

def restore_envelope(value,run_root,queue_root,local_paths=None):
    local_paths=local_paths or {}
    def visit(item):
        if isinstance(item,dict):return {key:visit(value) for key,value in item.items()}
        if isinstance(item,list):return [visit(value) for value in item]
        if not isinstance(item,str):return item
        for marker,path in [('{run_root}',run_root),('{canonical_root}',queue_root)]:
            if item==marker or item.startswith(marker+'/'):return str(path)+item[len(marker):]
        value_match=re.fullmatch(r'\{local_value:([a-f0-9]{64})\}',item)
        if value_match:
            value=local_paths.get(value_match[1])
            if not isinstance(value,str) or not value:raise RunError('Portable checkpoint requires an explicitly reviewed local value mapping: '+value_match[1])
            return value
        match=re.fullmatch(r'\{local_path:([a-f0-9]{64})\}',item)
        if match:
            path=local_paths.get(match[1])
            if not path or not Path(path).is_absolute():raise RunError('Portable execution receipt requires an explicitly reviewed local path mapping: '+match[1])
            return path
        return item
    return visit(value)
