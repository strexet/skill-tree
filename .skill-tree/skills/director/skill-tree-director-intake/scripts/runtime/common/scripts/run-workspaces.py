#!/usr/bin/env python3
"""Git workspaces, canonical queue routing and compatible multi-run metadata."""
from collections import deque
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
import unicodedata
import uuid

class RunError(ValueError):
    pass

class LocalRefRejected(RunError):
    """The protected ref gate rejected the write before touching the target checkout."""

TERMINAL = {'local-result', 'merged'}

def delivery_finished(run):
    delivery=run.get('delivery',{})
    if run.get('reviewed_local_delivery') and delivery.get('publication')=='not-requested':
        return (delivery.get('implementation')=='completed'
                and delivery.get('order_completed') is True and delivery.get('status') in {'review-ready','merged'})
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

def git(root, *args, git_options=()):
    result = subprocess.run(['git', '-C', str(root), *map(str, git_options), *map(str, args)],
                            capture_output=True, text=True, timeout=45)
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
    pending = data.get('pending_worktrees', {})
    unverified = data.get('unverified_worktrees', [])
    if (data.get('schema') != 1 or not isinstance(data.get('worktrees'), dict)
            or not isinstance(unverified,list) or any(not isinstance(rid,str) or rid not in data['worktrees'] for rid in unverified)
            or len(set(unverified)) != len(unverified)
            or not isinstance(pending,dict) or any(not re.fullmatch(r'WR-[a-f0-9-]{36}',rid)
                or not isinstance(path,str) or not Path(path).is_absolute() for rid,path in pending.items())):
        raise RunError('Unsupported machine-local run locator; explicit recovery required')
    return data

def atomic(path, data, *, exclusive=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='skill-tree-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, indent=2, sort_keys=True); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        if exclusive:
            os.link(name, path)
        else:
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

def setup(store, payload, *, bootstrap_id=None, expected_state_sha256=None, expected_queue_sha256=None, update_navigation=True):
    """Explicit schema-2 extension; preserve the complete single-run record."""
    if not common_dir(store.root):raise RunError('Workspace setup requires a Git repository')
    if store.root != store.source_root:
        raise RunError('Run setup requires the canonical checkout')
    with store.lock():
        text = store.text()
        raw=json.loads(store.state.read_text()) if store.state.exists() else {}
        if bootstrap_id is not None:
            actual = hashlib.sha256(store.state.read_bytes()).hexdigest() if store.state.exists() else None
            locator = runtime_file(store.root)
            if (actual != expected_state_sha256 or hashlib.sha256(store.future.read_bytes()).hexdigest() != expected_queue_sha256
                    or raw.get('run_registry') or locator.exists() or locator.is_symlink()):
                raise RunError('Core queue or state changed before the approved bootstrap')
        if raw.get('run_registry'):
            if payload.get('confirm_queue_id')!=raw['run_registry']['queue_id']:raise RunError('Run registry exists; use resume or explicit locator recovery')
            raw['schema']=3;store.commit({'.skill-tree/documents/future.json':json.dumps(raw,indent=2,sort_keys=True)+'\n'});return raw['run_registry']
        state = store.load(text)
        old = deepcopy(state['active_run'])
        if old and payload.get('adopt_run_id') != old['id']:
            raise RunError('Existing checkpoint requires explicit adopt_run_id and workspace identity')
        registry = {'schema': 1, 'queue_id': bootstrap_id or 'Q-'+str(uuid.uuid4()), 'runs': {}, 'claims': {}, 'resources': {}}
        if old:
            registry['runs'][old['id']] = old
            old['workspace'] = workspace_identity(store, old['id'], payload, existing=True)
            old['delivery'] = {'implementation': 'in-progress', 'publication': 'not-requested', 'status': 'implementation-in-progress', 'authorization': {}}
        state['active_run'] = None; state['run_registry'] = registry
        store.save(text, state, update_navigation=update_navigation)
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
    archived = registry.get('archived_runs', {})
    if not isinstance(archived, dict) or set(archived) & set(registry['runs']):
        raise RunError('Historical partial finishes must remain outside the live run registry')
    for rid, entry in archived.items():
        if (not isinstance(entry, dict) or entry.get('status') != 'partially-completed'
                or not isinstance(entry.get('checkpoint'), dict) or entry['checkpoint'].get('id') != rid
                or not re.fullmatch(r'[a-f0-9]{64}', entry.get('receipt_sha256', ''))):
            raise RunError('Invalid historical partial finish reference')
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
    if rid in registry.get('archived_runs', {}):
        raise RunError('The selected run is partially closed; inspect the historical result')
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
    if not run.get('reviewed_local_delivery'):
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

def workspace_identity(store, rid, payload, existing=False, launch=None):
    if launch is not None:
        base = launch['ref'].removeprefix('refs/heads/')
        if payload.get('base_branch', base) != base:
            raise RunError('Reviewed local delivery starts from the checked-out launch branch')
        working = branch(store.root, payload.get('branch', payload.get('branch_prefix', 'codex/')+rid.lower()))
        if working == base:
            raise RunError('The run branch must differ from the checked-out launch branch')
        return {'repo_id':repo_id(store.root),'remote':None,'remote_id':None,'base_branch':base,
                'base_commit':launch['head'],'branch':working,'worktree_id':rid,'local_base':True}

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

def within_directory(path, directory):
    if path.is_relative_to(directory):
        return True
    if not directory.exists():
        return False
    identity = directory.stat()
    return any(parent.exists() and os.path.samestat(parent.stat(),identity) for parent in (path,*path.parents))


def default_web_checkout(root, common, queue_id, run_id):
    location = root.parent/'.skill-tree-worktrees'/queue_id.lower()/run_id.lower()
    resolved = location.resolve()
    if resolved != location or within_directory(resolved,root) or within_directory(resolved,common):
        raise RunError('The default Web worktree requires an unaliased path outside the canonical checkout and Git administrative storage')
    return resolved


def accepts_case_aliases(directory):
    device = directory.stat().st_dev
    for ancestor in (directory,*directory.parents):
        if ancestor.stat().st_dev != device:
            break
        if not ancestor.name or ancestor.name.swapcase() == ancestor.name:
            continue
        try:
            return ancestor.samefile(ancestor.with_name(ancestor.name.swapcase()))
        except FileNotFoundError:
            return False
    return False


def worktree_paths_overlap(left, right):
    if within_directory(left,right) or within_directory(right,left):
        return True
    # A new directory has no inode to compare. Detect case aliases on the
    # containing filesystem before accepting distinct unresolved spellings.
    def normalized(path):
        return tuple(unicodedata.normalize('NFD',part.casefold()) for part in path.parts)
    left_key, right_key = normalized(left), normalized(right)
    if left_key[:len(right_key)] != right_key and right_key[:len(left_key)] != left_key:
        return False
    left_parent = next(parent for parent in (left,*left.parents) if parent.is_dir())
    right_parent = next(parent for parent in (right,*right.parents) if parent.is_dir())
    return (left_parent.stat().st_dev == right_parent.stat().st_dev
            and accepts_case_aliases(left_parent) and accepts_case_aliases(right_parent))


def guard_web_destination(data, recorded, run_id, path):
    for rid, location in {**data.get('pending_worktrees',{}),**data['worktrees']}.items():
        if rid==run_id or rid not in recorded or delivery_finished(recorded[rid]):
            continue
        other = Path(location).resolve()
        if worktree_paths_overlap(path,other):
            raise RunError('The selected Web path overlaps another retained run worktree: '+str(other))


def retain_web_destination(store, run, path):
    data = runtime(store.root)
    recorded = json.loads(store.state.read_bytes())['run_registry']['runs']
    guard_web_destination(data,recorded,run['id'],path)
    data.setdefault('pending_worktrees',{})[run['id']] = str(path)
    atomic(runtime_file(store.root),data)


def activate_worktree_locator(root, data, run_id, path):
    pending = data.get('pending_worktrees',{})
    if run_id in pending and pending[run_id] != str(path):
        raise RunError('Recovery requires the original exact worktree path')
    data['worktrees'][run_id] = str(path)
    pending.pop(run_id,None)
    if not pending:
        data.pop('pending_worktrees',None)
    atomic(runtime_file(root),data)


def provision(store, run, payload):
    """Reserve claims first; interrupted provisioning retains the same run ID."""
    policy = run.get('reviewed_local_delivery')
    spec = workspace_identity(store, run['id'], payload, launch=policy['launch'] if policy else None)
    common = common_dir(store.root)
    if 'worktree' not in payload and run['admission']['flavor']=='web':
        path = default_web_checkout(store.root,common,runtime(store.root)['queue_id'],run['id'])
    else:
        path = Path(payload.get('worktree', str(common/'skill-tree-worktrees'/run['id'].lower()))).resolve()
    if path.exists():
        raise RunError('Worktree destination exists; explicit recovery required')
    if git(store.root,'for-each-ref','--format=%(refname)','refs/heads/'+spec['branch']):raise RunError('Working branch already exists; select the retained run or explicit recovery')
    run['workspace'] = spec
    run['cleanup_origin_sha256'] = locator_path_sha256(path)
    run['delivery'] = {'implementation': 'in-progress', 'publication': 'not-requested', 'status': 'implementation-in-progress', 'authorization': payload.get('delivery_authorization', {})}
    run['workspace_state'] = 'reserved'
    return path

INITIAL_PROFILE_STOP = 'Initial worktree profile requires verified admission'
PROFILE_FILE = '.skill-tree/installation/profile.json'


def initial_profile_pending(run):
    return bool(run and run.get('initial_profile', {}).get('status') == 'pending')


def reserve_initial_profile(store, run, path, done):
    """Bind the setup to the verified canonical generation before writing Git."""
    if run['admission']['identity'] == 'repository-local':
        return
    profile = store.root/PROFILE_FILE
    if not profile.is_file() or profile.is_symlink():
        raise RunError('Restore the verified canonical profile before reserving a worktree')
    content = profile.read_bytes()
    receipt = json.loads(content)
    if (receipt.get('identity') != run['admission']['identity']
            or receipt.get('project_root') != str(store.root)):
        raise RunError('The canonical profile differs from the admitted source generation')
    manager_relative = '.skill-tree/installation/source/lib/installation.js'
    manager = store.root/manager_relative
    installed = manager.read_bytes() if manager.is_file() and not manager.is_symlink() else b''
    exports = installed.partition(b'module.exports=')[2]
    if (not re.search(rb'\binitialWorktreeProfile\b',exports)
            or hashlib.sha256(installed).hexdigest() != receipt.get('bundle_digests',{}).get(manager_relative)):
        raise RunError('Update the verified canonical installation from current source before reserving an initial worktree profile')
    run['initial_profile'] = {
        'status': 'pending', 'source_profile_sha256': hashlib.sha256(content).hexdigest(),
        'worktree_path_sha256': hashlib.sha256(str(path).encode()).hexdigest(),
        'claimed_task_ids': sorted(set(run['admitted_task_ids']) - done),
    }
    run.update(phase='refresh-profile', stop_reason=INITIAL_PROFILE_STOP,
               next_action='Prepare the owned worktree profile with prepare-worktree-profile')
    if run['admission']['flavor']=='web':
        retain_web_destination(store,run,path)


def initial_profile_context(store, state, caller, *, replay=False):
    run = state.get('active_run') or {}
    expected_status = 'admitted' if replay else 'pending'
    if run.get('initial_profile',{}).get('status') != expected_status or run.get('workspace_state') != 'ready':
        raise RunError('Select the retained initial profile and exact registered worktree')
    if not replay and (run['phase'] != 'refresh-profile' or run.get('stop_reason') != INITIAL_PROFILE_STOP):
        raise RunError('Restore the original stopped initial-profile handoff before setup')
    ensure_workspace(store, run)
    target = store.source_root
    if caller not in (store.root, target):
        raise RunError('Select the canonical checkout or the exact reserved worktree for profile setup')
    if (hashlib.sha256(str(target).encode()).hexdigest() != run['initial_profile']['worktree_path_sha256']
            or local_git_text(target, 'rev-parse', '--verify', 'HEAD') != run['workspace']['base_commit']):
        raise RunError('Initial profile setup requires the original exact worktree and Git base')
    registration = linked_registration(store.root, target)
    owner = run['workspace'].get('cleanup_owner')
    if owner:
        directed_owner(store.root, target, run, state['run_registry']['queue_id'])
    elif not run.get('workspace_recoveries'):
        raise RunError('Initial profile setup requires the owned or explicitly recovered linked checkout')
    claimed = sorted(tid for tid, rid in state['run_registry']['claims'].items() if rid == run['id'])
    if claimed != run['initial_profile']['claimed_task_ids']:
        raise RunError('Initial profile setup requires the original reserved task claims')
    return {
        'run_id': run['id'], 'queue_id': state['run_registry']['queue_id'], 'worktree': str(target),
        'locator_sha256': hashlib.sha256(runtime_file(store.root).read_bytes()).hexdigest(),
        'state_sha256': hashlib.sha256(store.state.read_bytes()).hexdigest(),
        'registration': registration.name, 'owner': owner,
        'source_profile_sha256': run['initial_profile']['source_profile_sha256'],
    }


def create_reserved(store, run, path):
    if run['admission']['flavor']=='web' and path.resolve()!=path:
        raise RunError('The original Web worktree path changed before Git creation')
    data = runtime(store.root)
    activate_worktree_locator(store.root,data,run['id'],path)
    git(store.root, 'worktree', 'add', '-b', run['workspace']['branch'], path, run['workspace']['base_commit'])
    run['workspace']['cleanup_owner'] = directed_owner(store.root, path, run, data['queue_id'], created=True)
    run['workspace_state'] = 'ready'
    store.source_root = path


def linked_registration(root, path):
    common = common_dir(root)
    if not common or common_dir(path) != common:
        raise RunError('The registered source belongs to a different Git repository')
    location = Path(local_git_text(path, 'rev-parse', '--absolute-git-dir'))
    if location.is_symlink() or location.parent != common/'worktrees' or location.parent.is_symlink():
        raise RunError('The source is not an ordinary linked Git worktree')
    backlink = location/'gitdir'
    if (not backlink.is_file() or backlink.is_symlink() or not (path/'.git').is_file() or (path/'.git').is_symlink()
            or (location/backlink.read_text().rstrip('\n')).resolve() != path/'.git'):
        raise RunError('The linked Git registration does not point back to the exact worktree')
    return location


def cleanup_quarantine(root, attempt):
    attempt_id = attempt['id']
    if not re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', attempt_id):
        raise RunError('The original cleanup attempt identity is invalid')
    directory = common_dir(root)/('skill-tree-cleanup-'+attempt_id)
    if directory.is_symlink():
        raise RunError('The original cleanup directory is ambiguous')
    return directory/'checkout'


def locator_path_sha256(path):
    return hashlib.sha256(os.fsencode(path)).hexdigest()


def cleanup_worktree_owner(root, registry, run):
    locator = runtime(root)
    workspace = run['workspace']
    owner = workspace.get('cleanup_owner')
    if (not isinstance(owner,dict) or owner.get('run_id') != run['id']
            or owner.get('queue_id') != registry['queue_id']
            or not isinstance(owner.get('token'),str) or not owner['token']):
        raise RunError('The worktree has no current controller creation proof')
    if run.get('workspace_state') != 'ready':
        raise RunError('An unfinished worktree requires separate ownership inspection')
    if not locator or locator['queue_id'] != registry['queue_id'] or run['id'] not in locator['worktrees']:
        raise RunError('The exact controller worktree locator is unavailable')
    name = owner.get('registration')
    if not isinstance(name,str) or name in {'','.','..'} or Path(name).name != name:
        raise RunError('The Git administrative identity is invalid')
    origin = Path(locator['worktrees'][run['id']])
    if not origin.is_absolute() or root.is_relative_to(origin):
        raise RunError('The worktree locator is ambiguous or contains the canonical checkout')
    return locator, owner, origin, common_dir(root)/'worktrees'/name


def cleanup_origin_sha256(run):
    candidates = [run.get('cleanup_origin_sha256'), run.get('dispatch_workspace_sha256'),
                  (run.get('initial_profile') or {}).get('worktree_path_sha256')]
    known = [value for value in candidates if value is not None]
    if (any(not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{64}',value) for value in known)
            or len(set(known)) > 1):
        raise RunError('Conflicting original worktree location proofs')
    return known[0] if known else None


def verified_move_chain(run, owner):
    anchor = cleanup_origin_sha256(run)
    prior = None
    for receipt in run.get('workspace_recoveries',[]):
        if (not isinstance(receipt,dict) or receipt.get('kind') != 'verified-worktree-move'
                or receipt.get('owner') != owner
                or receipt.get('branch') != run['workspace']['branch']
                or any(not isinstance(receipt.get(key),str) or not re.fullmatch(r'[a-f0-9]{64}',receipt[key])
                       for key in ('from_locator_sha256','to_locator_sha256'))
                or receipt['from_locator_sha256'] == receipt['to_locator_sha256']
                or receipt['from_locator_sha256'] != (prior['to_locator_sha256'] if prior else anchor)):
            raise RunError('A recovered worktree requires separate ownership inspection')
        prior = receipt
    return prior


def path_absent(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return True
    return False


def latest_verified_move(run):
    history = run.get('workspace_recoveries',[])
    last = history[-1] if history else None
    return last if isinstance(last,dict) and last.get('kind') == 'verified-worktree-move' else None


def pending_verified_move(run, locator):
    last = latest_verified_move(run)
    return bool(last and locator and last.get('from_locator_sha256') == locator_path_sha256(locator)
                and last.get('to_locator_sha256') != last.get('from_locator_sha256'))


def registered_worktrees(root):
    records = local_git(root, 'worktree', 'list', '--porcelain', '-z').stdout.split(b'\0\0')
    registrations = {}
    for record in records:
        row, *fields = record.split(b'\0')
        if row.startswith(b'worktree '):
            registered = Path(os.fsdecode(row[len(b'worktree '):])).resolve()
            if registered in registrations:
                raise RunError('Git reports an ambiguous worktree registration')
            registrations[registered] = fields
    return registrations


def cleanup_checkout(root, registry, run, original):
    locator, owner, origin, registration = cleanup_worktree_owner(root,registry,run)
    move = verified_move_chain(run,owner)
    current_path_sha = locator_path_sha256(origin)
    anchor = move['to_locator_sha256'] if move else cleanup_origin_sha256(run)
    if anchor is not None and anchor != current_path_sha:
        raise RunError('Activate the exact verified worktree relocation before cleanup')
    if anchor is None and run['id'] in locator.get('unverified_worktrees',[]):
        raise RunError('The recovered legacy locator lacks original worktree location evidence')
    if original and original['locator_sha256'] != current_path_sha:
        raise RunError('The original worktree locator changed after removal preparation')
    registrations = registered_worktrees(root)
    quarantine = cleanup_quarantine(root, original) if original else None
    if quarantine and quarantine.is_symlink():
        raise RunError('The staged worktree path is ambiguous')
    registration_absent = path_absent(registration)
    if original and original.get('external_removal') and registration_absent and origin not in registrations:
        return None
    if original and original.get('staged') and registration_absent and path_absent(quarantine) and quarantine not in registrations:
        # A newly created directory at the original path does not belong to the removed registration.
        return None
    if origin.resolve() != origin:
        raise RunError('The original worktree location changed')
    path = quarantine if quarantine and (quarantine.exists() or quarantine in registrations) else origin
    if path_absent(path) and registration_absent and path not in registrations:
        if original:
            return None
        raise RunError('The selected worktree disappeared before a cleanup attempt was prepared')
    if any(other != path and other.is_relative_to(path) for other in registrations):
        raise RunError('The selected path contains another Git worktree')
    if any(rid != run['id'] and Path(other).resolve().is_relative_to(path)
           for rid, other in locator['worktrees'].items()):
        raise RunError('Another controller locates a worktree at or below the selected path')
    if path not in registrations or not path.is_dir() or linked_registration(root, path) != registration:
        raise RunError('The locator and original Git worktree registration no longer match')
    marker = registration/'skill-tree-owner.json'
    if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != owner:
        raise RunError('The original Git worktree ownership marker is unavailable or changed')
    if any(field == b'locked' or field.startswith(b'locked ') for field in registrations[path]):
        raise RunError('The selected Git worktree is locked')
    if Path.cwd().resolve().is_relative_to(path):
        raise RunError('Retry cleanup from outside the selected worktree')
    return path


def verify_external_worktree_removal(root, registry, run, requested, attempt):
    _, owner, origin, registration = cleanup_worktree_owner(root,registry,run)
    move = verified_move_chain(run,owner)
    anchor = move['to_locator_sha256'] if move else cleanup_origin_sha256(run)
    if anchor != locator_path_sha256(origin):
        raise RunError('External acknowledgement requires verified original worktree location evidence')
    if requested != str(origin) or origin.resolve() != origin:
        raise RunError('External removal acknowledgement requires the original exact worktree location')
    worktrees = registered_worktrees(root)
    staged = cleanup_quarantine(root,attempt) if attempt else None
    if (not path_absent(origin) or not path_absent(registration) or origin in worktrees
            or staged and (not path_absent(staged) or staged in worktrees)):
        raise RunError('The old worktree, staged checkout or Git registration is still present')
    return locator_path_sha256(origin)


def cleanup_source_guard(path, source_ref, source_head):
    current = checked_out_branch(path)
    if (current['ref'], current['head']) != (source_ref, source_head):
        raise RunError('The worktree branch or head changed after delivery')
    admin = task_index_path(path).parent
    if any(admin.rglob('*.lock')) or (admin/'sequencer').exists():
        raise RunError('The selected worktree has a Git lock or an unfinished sequencer operation')
    config = admin/'config.worktree'
    if config.is_symlink() or config.exists() and (not config.is_file() or config.stat().st_size):
        raise RunError('The selected worktree has local Git configuration')
    if local_git(path, 'for-each-ref', 'refs/worktree/', 'refs/bisect/', 'refs/rewritten/').stdout:
        raise RunError('The selected worktree has private Git references')
    recovery_heads = set(local_git_text(path, 'reflog', 'show', '--format=%H', 'HEAD').splitlines())
    for ref in ('ORIG_HEAD', 'AUTO_MERGE', 'MERGE_AUTOSTASH'):
        if (admin/ref).exists():
            recovery_heads.add(local_git_text(path, 'rev-parse', '--verify', ref))
    if any(local_git(path, 'merge-base', '--is-ancestor', head, source_head, accepted=(0, 1, 128)).returncode
           for head in recovery_heads - {source_head}):
        raise RunError('The selected worktree has recovery objects outside the delivered source history')
    if local_worktree_dirt(path, allow_staged=True):
        raise RunError('The selected worktree contains local, untracked or ignored content')
    # A checkout index can consider same-size, timestamp-preserving writes clean.
    with tempfile.TemporaryDirectory(prefix='skill-tree-cleanup-index-') as temporary:
        index = Path(temporary)/'index'
        local_git(path, 'read-tree', source_head, index=index)
        if local_git(path, '-c', 'core.filemode=true', 'status', '--porcelain', '-z',
                '--ignore-submodules=none', '--untracked-files=all', '--ignored=matching', index=index).stdout:
            raise RunError('The selected worktree contains local, untracked or ignored content')


def remove_controller_worktree(root, path):
    local_git(root, 'worktree', 'remove', '--', path)


def stage_controller_worktree(root, origin, attempt):
    quarantine = cleanup_quarantine(root, attempt)
    if origin != quarantine:
        quarantine.parent.mkdir(mode=0o700, exist_ok=True)
        if quarantine.parent.stat().st_mode & 0o077:
            raise RunError('The worktree cleanup directory is accessible to other users')
        local_git(root, 'worktree', 'move', '--', origin, quarantine)
    return quarantine


def restore_staged_worktree(root, registry, run, attempt):
    path = cleanup_checkout(root, registry, run, attempt)
    if path != cleanup_quarantine(root, attempt):
        return
    origin = Path(runtime(root)['worktrees'][run['id']])
    if origin.exists() or origin.is_symlink():
        raise RunError('The original worktree path is occupied')
    local_git(root, 'worktree', 'move', '--', path, origin)


def cleanup_target_head(root, target_ref, remote=None, remote_id=None):
    if remote is None:
        return local_git_text(root, 'rev-parse', '--verify', target_ref+'^{commit}')
    if remote not in git(root, 'remote').splitlines() or remote.startswith('-'):
        raise RunError('The recorded publication remote is unavailable')
    url = git(root, 'remote', 'get-url', remote)
    if hashlib.sha256(url.encode()).hexdigest() != remote_id:
        raise RunError('The recorded publication remote identity changed')
    environment = {**os.environ, 'GIT_TERMINAL_PROMPT':'0', 'GCM_INTERACTIVE':'never'}
    arguments = local_git_args(root, 'ls-remote', '--exit-code', '--refs', '--', remote, target_ref)
    result = subprocess.run(arguments, capture_output=True, env=environment, stdin=subprocess.DEVNULL, timeout=8)
    fields = result.stdout.split()
    if result.returncode or len(fields) != 2 or fields[1] != target_ref.encode():
        raise RunError('The live publication target could not be verified')
    return fields[0].decode('ascii')


def committed_file_hash(root, head, relative):
    if (not isinstance(head, str) or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', head)
            or not isinstance(relative, str) or Path(relative).is_absolute()
            or any(part in {'', '.', '..'} for part in relative.split('/')) or '\0' in relative):
        return None
    entry = local_git(root, 'ls-tree', '-z', head, '--', relative, accepted=(0, 128))
    details, separator, name = entry.stdout.partition(b'\t')
    if not separator or name != os.fsencode(relative)+b'\0' or not details.startswith((b'100644 blob ', b'100755 blob ')):
        return None
    blob = details.split()[-1].decode('ascii')
    return hashlib.sha256(local_git(root, 'cat-file', 'blob', blob).stdout).hexdigest()


def directed_owner(root, path, run, queue_id, *, created=False):
    """Bind only a checkout just created here or an already authenticated registration."""
    registration = linked_registration(root, path)
    spec = run['workspace']
    retained = spec.get('cleanup_owner')
    token = spec.get('dispatch_owner_token')
    if retained is not None:
        if not isinstance(retained, dict) or not retained.get('token'):
            raise RunError('Invalid recorded Director workspace ownership')
        token = token or retained['token']
    if not token and not created:
        raise RunError('Existing Director worktree lacks a verifiable ownership token; preserve it for explicit repair')
    owner = {'run_id': run['id'], 'queue_id': queue_id, 'registration': registration.name,
             'token': token or str(uuid.uuid4())}
    if retained is not None and retained != owner:
        raise RunError('Recorded Director owner conflicts with the linked worktree registration')
    marker = registration/'skill-tree-owner.json'
    if created:
        try:
            atomic(marker, owner, exclusive=True)
        except FileExistsError:
            pass  # Validate the existing marker without replacing its bytes.
    try:
        matches = marker.is_file() and not marker.is_symlink() and json.loads(marker.read_bytes()) == owner
    except (OSError, ValueError):
        matches = False
    if not matches:
        raise RunError('Director workspace ownership marker is missing or conflicting; preserve the worktree for explicit repair')
    return owner


def inspect_directed_reservation(store, run, requested=None):
    """Check lost-acknowledgement inputs without creating or switching a checkout."""
    expected = run.get('dispatch_workspace_sha256')
    if expected is None or delivery_finished(run):
        return
    if run.get('workspace_state') != 'reserved':
        view = deepcopy(store)
        ensure_workspace(view, run)
        if ((run['workspace'].get('cleanup_owner') or run['workspace'].get('dispatch_owner_token'))
                and hashlib.sha256(str(view.source_root).encode()).hexdigest() != expected):
            raise RunError('Director reservation requires the original exact worktree path')
        if local_git_text(view.source_root, 'rev-parse', '--show-toplevel') != str(view.source_root):
            raise RunError('Recorded Director worktree is not the exact Git checkout root')
        return
    locator = runtime(store.root)
    recorded = locator['worktrees'].get(run['id']) if locator else None
    spec = run['workspace']
    ref = 'refs/heads/' + spec['branch']
    branch_tip = local_git(store.root, 'rev-parse', '--verify', '--quiet', ref, accepted=(0, 1)).stdout.decode().strip()
    if branch_tip and branch_tip != spec['base_commit']:
        raise RunError('Reserved Director source branch differs from the recorded Git base')
    if requested is None and recorded is None:
        return  # Reservation predates locator write. Recovery requires the original path.
    path = Path(requested or recorded).resolve()
    if hashlib.sha256(str(path).encode()).hexdigest() != expected or recorded and Path(recorded).resolve() != path:
        raise RunError('Director reservation requires the original exact worktree path')
    if path.exists() and (not path.is_dir() or common_dir(path) != common_dir(store.root)
                          or local_git_text(path, 'rev-parse', '--show-toplevel') != str(path)
                          or local_git_text(path, 'symbolic-ref', '--quiet', '--short', 'HEAD') != spec['branch']):
        raise RunError('Reserved Director worktree has a conflicting ownership or branch')
    if path.exists() and spec.get('dispatch_owner_token'):
        directed_owner(store.root, path, run, locator['queue_id'])

def recover_locator(store, payload, *, bootstrap_state_sha256=None):
    """Explicitly repair local paths only; never rewrite portable checkpoints."""
    with store.lock():
        content = store.state.read_bytes()
        if bootstrap_state_sha256 is not None:
            locator = runtime_file(store.root)
            if hashlib.sha256(content).hexdigest() != bootstrap_state_sha256 or locator.exists() or locator.is_symlink():
                raise RunError('Core state or locator changed before bootstrap recovery')
        state = json.loads(content); registry = state.get('run_registry'); validate_registry(registry)
        if payload.get('queue_id') != registry['queue_id']:
            raise RunError('Recovery requires the exact queue ID')
        mapping = payload.get('worktrees', {})
        required={rid for rid,run in registry['runs'].items() if not delivery_finished(run)}
        if not isinstance(mapping,dict) or not required.issubset(mapping) or set(mapping)-set(registry['runs']):
            raise RunError('Recovery requires every unfinished retained run locator and rejects unknown run IDs')
        restored, pending = {}, {}
        unverified = []
        try:
            previous = runtime(store.root) or {}
        except (OSError,ValueError):
            previous = {}
        previous_paths = previous.get('worktrees',{})
        for rid, run in registry['runs'].items():
            bound = previous_paths.get(rid)
            if pending_verified_move(run,bound):
                restored[rid] = bound
        for rid, value in mapping.items():
            path = Path(value).resolve(); run = registry['runs'][rid]
            bound = previous_paths.get(rid)
            move = latest_verified_move(run)
            if pending_verified_move(run,bound) or move and not bound:
                if locator_path_sha256(path) != move['from_locator_sha256']:
                    raise RunError('Restore the previous locator before activating the exact recorded relocation')
                restored[rid] = str(path)
                continue
            anchor = cleanup_origin_sha256(run)
            if run.get('workspace_state') == 'reserved' and anchor is not None:
                if locator_path_sha256(path) != anchor:
                    raise RunError('Locator recovery requires the original exact reserved worktree path')
                if not path.exists():
                    pending[rid] = str(path)
                    continue
            if common_dir(path) != common_dir(store.root) or git(path, 'symbolic-ref', '--short', 'HEAD') != run['workspace']['branch']:
                raise RunError('Recovery workspace identity mismatch')
            restored[rid] = str(path)
            if cleanup_origin_sha256(run) is None and (
                    previous.get('worktrees',{}).get(rid) != str(path)
                    or rid in previous.get('unverified_worktrees',[])):
                unverified.append(rid)
        data = {'schema':1,'queue_id':registry['queue_id'],'canonical_root':str(store.root),'worktrees':restored}
        if previous.get('archived_worktrees'):
            data['archived_worktrees'] = {rid: entry for rid, entry in previous['archived_worktrees'].items()
                                         if rid in registry.get('archived_runs', {})}
        if unverified:
            data['unverified_worktrees'] = sorted(unverified)
        if pending:
            data['pending_worktrees']=pending
        atomic(runtime_file(store.root),data)
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
    return not run.get('reviewed_local_delivery') and authorization.get('pr') is False and authorization.get('merge') is True


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
                 'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE', 'GIT_CONFIG_PARAMETERS',
                 'GIT_CONFIG'}
    config_files = ('GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM')
    blocked = sorted(overrides.intersection(os.environ) |
                     {key for key in config_files if key in os.environ and os.environ[key] != os.devnull})
    if blocked:
        raise RunError('Local delivery requires the recorded Git environment without repository or index overrides. '
                       'Clear the inherited setting ' + blocked[0])
    env = os.environ.copy()
    count = env.pop('GIT_CONFIG_COUNT', '0')
    if not re.fullmatch(r'0|[1-9][0-9]{0,2}', count):
        raise RunError('Invalid inherited Git configuration count')
    # Desktop clients may install URL-scoped authentication or display settings.
    # Local inspection and ref updates never need their values.
    for index in range(int(count)):
        key = env.pop(f'GIT_CONFIG_KEY_{index}', '').lower()
        value = env.pop(f'GIT_CONFIG_VALUE_{index}', None)
        presentation = re.fullmatch(r'color\.(?:ui|branch|diff|status)', key)
        remote_only = re.fullmatch(r'(?:credential\.https?://[^\s]+\.(?:helper|usehttppath)|'
                                   r'http\.https?://[^\s]+\.(?:proactiveauth|followredirects|extraheader))', key)
        if value is None or not (presentation or remote_only):
            raise RunError(f'Unsupported inherited Git setting at index {index}. Clear it for local delivery.')
    if any(key.startswith(('GIT_CONFIG_KEY_', 'GIT_CONFIG_VALUE_')) for key in env):
        raise RunError('Unexpected inherited Git configuration entries outside GIT_CONFIG_COUNT')
    return env


def local_git_args(root, *args, literal_pathspecs=True):
    pathspec_mode = ['--literal-pathspecs'] if literal_pathspecs else []
    return ['git', '--no-replace-objects', '--no-optional-locks', *pathspec_mode, '-C', str(root),
            '-c', 'core.fsmonitor=false', '-c', 'diff.autoRefreshIndex=false', *map(str, args)]


def local_git(root, *args, accepted=(0,), index=None, literal_pathspecs=True, git_options=()):
    environment = local_git_environment()
    if index is not None:
        environment['GIT_INDEX_FILE'] = str(index)
    if not literal_pathspecs:
        for name in ('LITERAL', 'GLOB', 'NOGLOB', 'ICASE'):
            environment.pop('GIT_' + name + '_PATHSPECS', None)
    result = subprocess.run(local_git_args(root, *git_options, *args, literal_pathspecs=literal_pathspecs),
                            env=environment, capture_output=True, timeout=45)
    if result.returncode not in accepted:
        raise RunError('Local Git operation failed: ' + str(args[0]))
    return result


def local_git_text(root, *args):
    return local_git(root, *args).stdout.decode('utf-8').strip()


def local_git_paths(root, *args, literal_pathspecs=True):
    raw = local_git(root, *args, literal_pathspecs=literal_pathspecs).stdout
    try:
        return set(raw.decode('utf-8').split('\0')[:-1])
    except UnicodeError as exc:
        raise RunError('Local integration requires unambiguous UTF-8 Git paths') from exc


def local_overlap(left, right):
    return left == right or left.startswith(right + '/') or right.startswith(left + '/')


def ignored_unversioned_directories(root):
    versioned = None

    def whole_directory(path):
        nonlocal versioned
        relative = path.relative_to(root).as_posix()
        checkout = local_git(path, 'rev-parse', '--show-toplevel', accepted=(0, 128))
        if checkout.returncode or Path(os.fsdecode(checkout.stdout).rstrip('\n')).resolve() != root:
            return False
        ignored = local_git_paths(root, 'ls-files', '--others', '--ignored', '--exclude-standard',
                                  '--directory', '-z', '--', relative)
        if relative + '/' not in ignored:
            return False
        if versioned is None:
            indexed = local_git_paths(root, 'ls-files', '-z')
            head = local_git(root, 'rev-parse', '--verify', '--quiet', 'HEAD', accepted=(0, 1))
            committed = local_git_paths(root, 'ls-tree', '-r', '--name-only', '-z', 'HEAD') if not head.returncode else set()
            versioned = {unicodedata.normalize('NFC', item).casefold() for item in indexed | committed}
        key = unicodedata.normalize('NFC', relative).casefold()
        return not any(local_overlap(key, item) for item in versioned)

    return whole_directory


def worker_path(value):
    if (not isinstance(value, str) or not value or '\\' in value
            or any(ord(char) < 32 for char in value)
            or any(part.casefold() in {'', '.', '..', '.git'} for part in value.split('/'))):
        raise RunError('Worker paths must be exact repository-relative paths')
    return value


def worker_paths(values):
    if not isinstance(values, list):
        raise RunError('Worker scope requires a list of paths')
    paths = [worker_path(value) for value in values]
    if len(set(paths)) != len(paths):
        raise RunError('Worker paths must be distinct')
    return sorted(paths)


def worker_checkout(coordinator, supplied):
    if not isinstance(supplied, str) or not supplied:
        raise RunError('Worker scope requires an exact linked checkout')
    path = Path(supplied)
    if not path.is_absolute() or path.resolve() != path or path == coordinator:
        raise RunError('Worker scope requires a distinct exact linked checkout')
    root = Path(local_git_text(path, 'rev-parse', '--show-toplevel'))
    common = common_dir(coordinator)
    git_dir = Path(local_git_text(path, 'rev-parse', '--absolute-git-dir')).resolve()
    if root != path or common is None or git_dir.parent != common / 'worktrees' or common_dir(path) != common:
        raise RunError('Worker checkout must be an isolated worktree of the coordinator repository')
    if str(path) in (runtime(coordinator) or {}).get('worktrees', {}).values():
        raise RunError('A registered controller checkout cannot serve as a worker checkout')
    unfinished(path)
    identity = git_dir.stat()
    checkout = hashlib.sha256(
        f'{git_dir.relative_to(common).as_posix()}:{identity.st_dev}:{identity.st_ino}'.encode()
    ).hexdigest()
    return path, checkout


def worker_head(root):
    return local_git_text(root, 'rev-parse', '--verify', 'HEAD^{commit}')


def require_clean_worker(root, artifacts=()):
    entries = local_git(root, 'ls-files', '-v', '-z', '--').stdout.split(b'\0')
    if any(entry and (entry[:1].islower() or entry.startswith(b'S ')) for entry in entries):
        raise RunError('Worker checkout must have a fully visible Git index')
    if local_git_paths(root, 'diff', 'HEAD', '--name-only', '--no-renames', '-z', '--'):
        raise RunError('Worker checkout has uncommitted tracked changes')
    if local_git_paths(root, 'ls-files', '--others', '--exclude-standard', '-z') - set(artifacts):
        raise RunError('Worker checkout has unsubmitted untracked paths')


def worker_candidate(root, base, head, allowed, artifacts):
    if not isinstance(head, str) or head != worker_head(root):
        raise RunError('Worker candidate must match the exact checked-out commit')
    require_clean_worker(root, artifacts)
    if head == base or local_git(root, 'merge-base', '--is-ancestor', base, head, accepted=(0, 1)).returncode:
        raise RunError('Worker candidate must extend the recorded source base')
    paths = sorted(local_git_paths(root, 'diff', '--name-only', '--no-renames', '-z', base, head, '--'))
    if not paths or any(not any(path == scope or path.startswith(scope + '/') for scope in allowed)
                        for path in worker_paths(paths)):
        raise RunError('Worker candidate changed paths outside the assigned scope or has no changes')
    tree = local_git_text(root, 'rev-parse', '--verify', head + '^{tree}')
    return {'head': head, 'tree': tree, 'paths': paths}


def checked_out_branch(root):
    unfinished(root)
    if Path(local_git_text(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise RunError('Select the exact Git worktree root')
    ref = local_git(root, 'symbolic-ref', '--quiet', '--no-recurse', 'HEAD', accepted=(0, 1)).stdout.decode().strip()
    if not ref.startswith('refs/heads/'):
        raise RunError('Select a checked-out local branch')
    if local_git(root, 'symbolic-ref', '--quiet', ref, accepted=(0, 1)).returncode == 0:
        raise RunError('The selected task requires a direct Git branch ref')
    head = local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}')
    gitdir = Path(local_git_text(root, 'rev-parse', '--absolute-git-dir'))
    checkout = hashlib.sha256(gitdir.resolve().relative_to(common_dir(root)).as_posix().encode()).hexdigest()
    return {'ref': ref, 'head': head, 'checkout': checkout}


def verified_pr_source_worktree(canonical_root, selected, source_branch, head):
    local_git_environment()
    if not isinstance(selected,str):
        raise RunError('PR resume requires an exact source checkout path')
    path = Path(selected)
    common = common_dir(canonical_root)
    if (not common or not path.is_absolute() or path.resolve() != path or not path.is_dir()
            or common_dir(path) != common):
        raise RunError('Select an exact source worktree in the original Git repository')
    if path != canonical_root:
        linked_registration(canonical_root,path)
    identity = checked_out_branch(path)
    if identity['ref'] != 'refs/heads/'+source_branch or identity['head'] != head:
        raise RunError('Selected PR source worktree differs from the original branch or head')
    entries = local_git(path,'ls-files','-v','-z','--').stdout.split(b'\0')
    if any(entry[:1] == b'S' or entry[:1].islower() for entry in entries):
        raise RunError('The selected PR source index must expose every tracked file')
    if local_git(path,'status','--porcelain','-z').stdout:
        raise RunError('The selected PR source worktree has uncommitted changes')
    return path,identity


def task_commit_baseline(root):
    identity = checked_out_branch(root)
    dirt = set()
    for args in (('diff', '--cached', '--name-only', '--no-renames', '-z', '--'),
                 ('diff', '--name-only', '--no-renames', '-z', '--'),
                 ('ls-files', '--others', '--exclude-standard', '-z')):
        dirt.update(local_git_paths(root, *args))
    return {**identity, 'dirty': sorted(dirt)}


def task_index_path(root):
    index = Path(local_git_text(root, 'rev-parse', '--path-format=absolute', '--git-path', 'index'))
    if index.is_symlink() or not index.is_file():
        raise RunError('Scoped task commit requires an ordinary Git index')
    return index


def task_index_selection(root, paths, index=None):
    entries = local_git(root, 'ls-files', '--stage', '-z', '--', *paths, index=index).stdout
    return hashlib.sha256(entries).hexdigest()


def validation_input_paths(root, source, directory_entry):
    relative = Path(source)
    error = 'Task validation inputs must resolve inside the selected worktree'
    if relative.is_absolute() or '..' in relative.parts:
        raise RunError(error)
    paths = {relative.as_posix()}
    remaining = deque(relative.parts)
    parent = root
    hops = 0
    # A later change to any link in the chain can change the validated bytes.
    while remaining:
        name = remaining.popleft()
        if name == '..':
            if parent == root:
                raise RunError(error)
            parent = parent.parent
            continue
        entry = directory_entry(parent, name)
        if not entry.is_symlink():
            parent = entry
            continue
        paths.add(entry.relative_to(root).as_posix())
        target = entry.readlink()
        hops += 1
        if hops > 40:
            raise RunError('Task validation input has too many symbolic links')
        if target.is_absolute():
            if not target.is_relative_to(root):
                raise RunError(error)
            target = target.relative_to(root)
            parent = root
        remaining.extendleft(reversed(target.parts))
    paths.add(parent.relative_to(root).as_posix())
    return paths


def require_committed_check_inputs(root, owned, sources, *, ignored_directories=()):
    if not sources:
        return
    root = root.resolve()
    ignore_case = local_git_bool(root, 'core.ignoreCase')
    precompose = local_git_bool(root, 'core.precomposeUnicode')

    def git_spelling(path):
        return unicodedata.normalize('NFC', path) if precompose else path

    def match_key(path):
        path = git_spelling(path)
        return path.casefold() if ignore_case else path

    directories = {}

    def directory_entry(parent, name):
        entry = parent / name
        if not (ignore_case or precompose) or not os.path.lexists(entry):
            return entry
        if parent not in directories:
            directories[parent] = set(os.listdir(parent))
        names = directories[parent]
        if name not in names:
            info = entry.lstat()
            for actual in sorted(names):
                if match_key(actual) == match_key(name) and os.path.samestat((parent / actual).lstat(), info):
                    return parent / actual
        return entry

    aliases = set()
    for source in sources:
        aliases.update(validation_input_paths(root, source, directory_entry))
    scope = {match_key(path) for path in aliases}

    def overlaps(path):
        path = match_key(path)
        return '.' in scope or any(local_overlap(path, source) for source in scope)

    indexed = local_git(root, 'ls-files', '-v', '-z').stdout.split(b'\0')
    hidden = (entry[2:].decode('utf-8') for entry in indexed if entry[:1].islower() or entry.startswith(b'S '))
    if any(overlaps(path) for path in hidden):
        raise RunError('Task validation inputs must be visible in the checked-out Git index')
    dirty = set(task_commit_baseline(root)['dirty'])
    pathspecs = sorted({git_spelling(path) for path in aliases})
    exclusions = []
    for path in sorted(ignored_directories):
        key = match_key(path)
        if not any(source == key or source.startswith(key + '/') for source in scope):
            exclusions.append(':(exclude,literal)' + git_spelling(path))
    if exclusions:
        pathspecs = [':(literal)' + path for path in pathspecs] + exclusions
    dirty.update(local_git_paths(root, 'ls-files', '--others', '--ignored', '--exclude-standard',
                                 '-z', '--', *pathspecs, literal_pathspecs=not exclusions))
    for path in sorted(dirty):
        if path not in owned and overlaps(path):
            raise RunError('The scoped candidate excludes a changed validation input: '+repr(path))


def require_task_checkout(root, baseline, recovery_head=None):
    identity=checked_out_branch(root)
    if (identity['ref']!=baseline['ref'] or identity['checkout']!=baseline['checkout']
            or identity['head'] not in {baseline['head'],recovery_head}):
        raise RunError('The scoped task checkout, branch or original head changed')


def task_commit_candidate(root, baseline, paths, *, recovery_head=None):
    require_task_checkout(root,baseline,recovery_head)
    if not isinstance(paths, list) or not paths or not all(isinstance(path,str) and path for path in paths) or len(set(paths)) != len(paths):
        raise RunError('A scoped task commit requires distinct owned file paths')
    for path in paths:
        relative = Path(path)
        if (relative.is_absolute() or relative.as_posix() != path or '..' in relative.parts
                or not relative.parts or relative.parts[0] == '.git' or '\0' in path
                or any((root / parent).is_symlink() for parent in relative.parents)
                or (root / relative).is_dir()):
            raise RunError('A scoped task commit requires exact repository-relative file paths')
        if any(local_overlap(path, previous) for previous in baseline['dirty']):
            raise RunError('Owned task files overlap changes present before implementation: ' + repr(path))
    hidden = local_git(root, 'ls-files', '-v', '-z', '--', *paths).stdout.split(b'\0')
    if any(entry and (entry[:1].islower() or entry.startswith(b'S ')) for entry in hidden):
        raise RunError('Scoped task files must be visible in the checked-out Git index')
    paths = sorted(paths)
    parent = baseline['head']
    local_git_policy(root, merge=False, signed=True)
    with tempfile.TemporaryDirectory(prefix='skill-tree-task-index-', dir=task_index_path(root).parent) as temporary:
        index = Path(temporary) / 'index'
        hooks=Path(temporary)/'hooks'
        hooks.mkdir()
        no_hooks=f'core.hooksPath={hooks}'
        local_git(root, '-c', no_hooks, 'read-tree', parent, index=index)
        before = task_index_selection(root, paths, index)
        local_git(root, '-c', no_hooks, 'add', '-A', '--', *paths, index=index)
        after = task_index_selection(root, paths, index)
        delta = local_git(root, 'diff', '--cached', '--name-only', '--no-renames', '-z', parent, '--', index=index).stdout
        actual = set(delta.decode().split('\0')[:-1])
        if not actual or not actual.issubset(paths):
            raise RunError('The task needs an actual file-scoped change set')
        tree = local_git(root, '-c', no_hooks, 'write-tree', index=index).stdout.decode().strip()
    current = task_index_selection(root, paths)
    if current != before and (not recovery_head or current != after):
        raise RunError('Staged changes overlap owned task files')
    return {'paths': paths, 'tree': tree, 'index_before': before, 'index_after': after}


def task_review_identity(baseline, candidate, task_content):
    head = baseline['head']
    return {'head': head, 'base_oid': head,
            'source_digest': hashlib.sha256((candidate['tree']+'\n'+task_content).encode()).hexdigest()}


def create_task_commit(root, baseline, candidate, task_id, title):
    signing=local_git_policy(root, merge=False, signed=True)
    message = f'{title}\n\nSkill-Tree-Task: {task_id}'
    return local_git_text(root, 'commit-tree', candidate['tree'], signing, '-p', baseline['head'], '-m', message)


@contextmanager
def prepare_ref_update(root, source_head, commit, hooks):
    args = local_git_args(root, '-c', f'core.hooksPath={hooks}', 'update-ref', '-m', 'Skill Tree task commit', '--stdin')
    with subprocess.Popen(args, env=local_git_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True) as process:
        timer = Timer(45, process.terminate)
        timer.daemon = True
        timer.start()
        try:
            process.stdin.write(f'start\nupdate HEAD {commit} {source_head}\nprepare\n')
            process.stdin.flush()
            if process.stdout.readline() != 'start: ok\n' or process.stdout.readline() != 'prepare: ok\n':
                raise RunError('The scoped Git task ref could not be locked')
            yield process
        finally:
            timer.cancel()
            if not process.stdin.closed:
                process.stdin.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)


def apply_task_commit(root, baseline, candidate, commit):
    index_path = task_index_path(root)
    with local_git_lock(index_path.with_name(index_path.name + '.lock')):
        signing=local_git_policy(root, merge=False, signed=True)
        observed = task_commit_candidate(root, baseline, candidate['paths'], recovery_head=commit)
        if observed != candidate:
            raise RunError('The task source changed after scoped review')
        head = checked_out_branch(root)['head']
        parents = local_git_text(root, 'show', '-s', '--format=%P', commit)
        tree = local_git_text(root, 'rev-parse', commit + '^{tree}')
        if parents != baseline['head'] or tree != candidate['tree']:
            raise RunError('Prepared task commit has a different parent or scoped tree')
        if head!=commit and signing=='-S':
            header=local_git(root,'cat-file','commit',commit).stdout.split(b"\n\n",1)[0]
            if not any(line.startswith((b'gpgsig ',b'gpgsig-sha256 ')) for line in header.splitlines()):
                raise RunError('The original prepared commit lacks the signature required by the current Git policy')
        with tempfile.TemporaryDirectory(prefix='skill-tree-task-index-', dir=index_path.parent) as temporary:
            index = Path(temporary) / 'index'
            hooks=Path(temporary)/'hooks'
            hooks.mkdir()
            shutil.copy2(index_path, index)
            local_git(root, '-c', f'core.hooksPath={hooks}', 'reset', '-q', commit, '--', *candidate['paths'], index=index)
            if task_index_selection(root, candidate['paths'], index) != candidate['index_after']:
                raise RunError('The prepared task index differs from the reviewed tree')
            if head != commit:
                with prepare_ref_update(root, baseline['head'], commit, hooks) as process:
                    if checked_out_branch(root)['ref'] != baseline['ref']:
                        raise RunError('The exact Git task branch changed before commit')
                    output, _ = process.communicate('commit\n', timeout=45)
                    if process.returncode or output != 'commit: ok\n':
                        raise RunError('Recover the original prepared task commit before retry')
            os.replace(index, index_path)


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


def reviewed_launch_target(store, run):
    launch = run['reviewed_local_delivery']['launch']
    raw = local_git(store.root, 'worktree', 'list', '--porcelain', '-z').stdout.decode()
    for record in raw.split('\0\0'):
        first, *fields = record.split('\0')
        if first.startswith('worktree ') and 'branch ' + launch['ref'] in fields:
            target = Path(first.removeprefix('worktree ')).resolve()
            if target != store.source_root and common_dir(target) == common_dir(store.root):
                actual = checked_out_branch(target)
                if (actual['ref'], actual['checkout']) == (launch['ref'], launch['checkout']):
                    return target, actual['head']
    raise RunError('The recorded launch branch must be checked out in its original Git worktree')


def local_worktree_dirt(root, *, allow_staged=False):
    staged = local_git_paths(root, 'diff', '--cached', '--name-only', '--no-renames', '-z', '--')
    hidden = local_git(root, 'ls-files', '-v', '-z').stdout.split(b'\0')
    if (staged and not allow_staged) or any(
            item and (item[:1].islower() or item.startswith(b'S ')) for item in hidden):
        raise RunError('Local integration requires a fully visible Git index and an unambiguous incoming scope')
    changed = local_git_paths(root, 'diff', '--name-only', '--no-renames', '-z', '--')
    others = local_git_paths(root, 'ls-files', '--others', '--exclude-standard', '-z')
    return staged | changed | others


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


def current_target_merge_tree(root, target_head, source_head):
    result = local_git(root, 'merge-tree', '--write-tree', '--name-only', '--no-messages', '-z',
                       target_head, source_head, accepted=(0, 1))
    tree, *paths = result.stdout.decode('utf-8').split('\0')
    if not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', tree):
        raise RunError('Git could not prepare an unambiguous current-target merge tree')
    paths = sorted({worker_path(path) for path in paths if path})
    if bool(paths) != bool(result.returncode):
        raise RunError('Git did not identify the exact conflicting paths')
    return tree, paths


def current_target_area(root, attempt):
    return common_dir(root)/('skill-tree-integration-'+attempt['id'].lower())/'checkout'


def current_target_checkout(root, attempt, *, create=False):
    area = current_target_area(root, attempt)
    if area.is_symlink() or area.parent.is_symlink():
        raise RunError('The current-target worktree path is ambiguous')
    if create and not area.exists():
        area.parent.mkdir(mode=0o700, exist_ok=True)
        if area.parent.stat().st_mode & 0o077:
            raise RunError('The integration checkout directory is accessible to other users')
        local_git_policy(root, merge=False, signed=True)
        with tempfile.TemporaryDirectory(dir=area.parent, prefix='hooks-') as hooks:
            local_git(root, '-c', f'core.hooksPath={hooks}', 'worktree', 'add', '-b',
                      attempt['candidate_ref'].removeprefix('refs/heads/'), area, attempt['draft_head'])
    linked_registration(root, area)
    actual = checked_out_branch(area)
    if actual['ref'] != attempt['candidate_ref'] or (attempt.get('checkout') and actual['checkout'] != attempt['checkout']):
        raise RunError('The exact current-target integration checkout changed')
    return area, actual


def current_target_commit(root, attempt, tree):
    signing = local_git_policy(root, merge=False, signed=True)
    return local_git_text(root, 'commit-tree', tree, signing, '-p', attempt['target_head'],
                          '-p', attempt['source']['source_head'], '-m', 'Skill Tree integration '+attempt['id'])


def current_target_dirt(area):
    dirty = local_worktree_dirt(area, allow_staged=True)
    staged = local_git_paths(area,'diff','--cached','--name-only','--no-renames','-z','--')
    return staged | {path for path in dirty if not local_unchanged_file(area,path)}


def apply_current_target_candidate(area, attempt, candidate):
    index = task_index_path(area)
    with local_git_lock(index.with_name(index.name+'.lock')):
        actual = checked_out_branch(area)
        if (actual['checkout'] != attempt['checkout'] or actual['ref'] != attempt['candidate_ref']
                or actual['head'] not in {candidate['commit'], attempt['draft_head']}
                or local_git(area,'diff','--cached','--quiet',candidate['commit'],'--',accepted=(0,1)).returncode
                or any(not local_unchanged_file(area,path) for path in
                       local_git_paths(area,'diff','--name-only','--no-renames','-z','--'))
                or local_git_paths(area, 'ls-files', '--others', '--exclude-standard', '-z')):
            raise RunError('The current-target candidate changed before sealing')
        if actual['head'] != candidate['commit']:
            with tempfile.TemporaryDirectory(dir=index.parent, prefix='integration-seal-') as hooks:
                with prepare_ref_update(area, actual['head'], candidate['commit'], hooks) as process:
                    output, _ = process.communicate('commit\n', timeout=45)
                    if process.returncode or output != 'commit: ok\n':
                        raise RunError('Recover the exact prepared integration candidate before retry')


def reconcile_reviewed_merge_index(root, attempt, merge):
    paths=attempt['incoming']
    if not paths:
        return
    index_path=task_index_path(root)
    head_path=Path(local_git_text(root,'rev-parse','--path-format=absolute','--git-path','HEAD'))
    with local_git_lock(index_path.with_name(index_path.name+'.lock')), local_git_lock(head_path.with_name(head_path.name+'.lock')):
        identity=checked_out_branch(root)
        if identity['ref']!=attempt['target_ref'] or identity['head']!=merge['commit']:
            raise RunError('The exact merged target changed before index reconciliation')
        with tempfile.TemporaryDirectory(prefix='skill-tree-merge-index-',dir=index_path.parent) as work:
            temporary=Path(work)
            hooks=temporary/'hooks'
            hooks.mkdir()
            no_hooks=f'core.hooksPath={hooks}'
            probe=temporary/'probe'
            local_git(root,'-c',no_hooks,'read-tree',merge['commit'],index=probe)
            expected=task_index_selection(root,paths,probe)
            observed=task_index_selection(root,paths)
            if observed==expected:
                return
            tracked=set(local_git(root,'ls-files','-z','--',*paths,index=probe).stdout.decode().split('\0')[:-1])
            live=[path for path in paths if path in tracked or os.path.lexists(root/path)]
            if live:
                local_git(root,'-c',no_hooks,'add','-f','-A','--',*live,index=probe)
            tree=local_git(root,'-c',no_hooks,'write-tree',index=probe).stdout.decode().strip()
            if tree!=merge['tree']:
                raise RunError('The incoming worktree files differ from the exact prepared merge tree')
            local_git(root,'-c',no_hooks,'read-tree',attempt['target_head'],index=probe)
            previous=task_index_selection(root,paths,probe)
            if observed!=previous:
                raise RunError('Preserve the changed incoming index entries before reconciling local merge')
            updated=temporary/'index'
            shutil.copy2(index_path,updated)
            local_git(root,'-c',no_hooks,'reset','-q',merge['commit'],'--',*paths,index=updated)
            if task_index_selection(root,paths,updated)!=expected or checked_out_branch(root)!=identity:
                raise RunError('The exact merged target changed before index reconciliation')
            os.replace(updated,index_path)


def local_git_bool(root, key):
    result=local_git(root,'config','--type=bool','--get',key,accepted=(0,1))
    return result.returncode==0 and result.stdout.strip()==b'true'


def local_git_policy(root, *, merge=True, signed=False, fast_forward=False):
    sign_commit=local_git_bool(root,'commit.gpgSign')
    if sign_commit and not signed:
        raise RunError('Local Git delivery requires handling of the enabled signing policy: commit.gpgSign')
    if merge:
        if local_git_bool(root,'merge.verifySignatures') and not signed:
            raise RunError('Local Git delivery requires handling of the enabled signing policy: merge.verifySignatures')
        target = local_git_text(root, 'symbolic-ref', '--short', 'HEAD')
        options = local_git(root, 'config', '--get-all', 'branch.' + target + '.mergeOptions', accepted=(0, 1))
        if options.stdout.strip():
            raise RunError('Local merge is blocked by branch-specific Git merge options')
    names = ('reference-transaction', 'post-index-change')
    if not fast_forward:
        names = ('prepare-commit-msg', 'commit-msg', 'post-commit') + names
        names += ('pre-merge-commit', 'post-merge') if merge else ('pre-commit',)
    require_local_git_hooks(root, names)
    return '-S' if sign_commit else '--no-gpg-sign'


def require_local_git_hooks(root, names):
    configured = local_git(root, 'config', '--path', '--get', 'core.hooksPath', accepted=(0, 1))
    if configured.returncode == 0:
        value = configured.stdout.decode('utf-8').rstrip('\n')
        if not value:
            raise RunError('Local merge requires an unambiguous Git hook directory')
        hooks = root / value
    else:
        hooks = Path(local_git_text(root, 'rev-parse', '--path-format=absolute', '--git-path', 'hooks'))
    for name in names:
        location = hooks / name
        if location.is_file() and os.access(location, os.X_OK):
            raise RunError('Local Git delivery is blocked by an executable Git hook: ' + name)


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
def local_ref_transaction(root, hooks, source_ref, source_head, target_ref, target_head, merge, verify_refs=()):
    args = local_git_args(root, '-c', f'core.hooksPath={hooks}', 'update-ref', '-m',
                          'Skill Tree local merge', '--stdin')
    with subprocess.Popen(args, env=local_git_environment(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True) as process:
        timer = Timer(45, process.terminate)
        timer.daemon = True
        timer.start()
        try:
            extra = ''.join(f'option no-deref\nverify {ref} {head}\n' for ref, head in verify_refs)
            commands = ('start\noption no-deref\n'
                        f'verify {source_ref} {source_head}\n{extra}option no-deref\n'
                        f'update {target_ref} {merge} {target_head}\nprepare\n')
            process.stdin.write(commands)
            process.stdin.flush()
            if process.stdout.readline() != 'start: ok\n' or process.stdout.readline() != 'prepare: ok\n':
                raise LocalRefRejected('The exact local source or target ref could not be locked for integration')
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


def run_local_merge(root, source_root, preparation, *, fast_forward=False):
    source_ref, source_head = preparation['source_ref'], preparation['source_head']
    target_ref, target_head = preparation['target_ref'], preparation['target_head']
    reviewed=preparation.get('allow_unrelated_staged',False)
    policy_options={'signed':True} if reviewed else {}
    if fast_forward:
        policy_options['fast_forward']=True
    local_git_policy(root,**policy_options)
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
            raise LocalRefRejected('The exact prepared target branch or head changed before integration')
        unfinished(root)
        signing=local_git_policy(root,**policy_options)
        if reviewed and local_git_bool(root,'merge.verifySignatures'):
            trust=local_git(root,'config','--get','gpg.minTrustLevel',accepted=(0,1))
            # Native Git merge requires marginal trust when no override is configured.
            defaults=('-c','gpg.minTrustLevel=marginal') if trust.returncode else ()
            local_git(root,*defaults,'verify-commit',source_head)
            signature=local_git_text(root,*defaults,'show','-s','--format=%G?',source_head)
            if signature not in {'G','U'}:
                raise RunError('The reviewed merge source does not have a current valid Git signature')
        allow_staged = preparation.get('allow_unrelated_staged', False)
        dirt = {path for path in local_worktree_dirt(root, allow_staged=allow_staged)
                if not local_unchanged_file(root, path)}
        if allow_staged:
            dirt.update(local_git_paths(root, 'diff', '--cached', '--name-only', '--no-renames', '-z', '--'))
        local_preflight_collisions(root, preparation['incoming'], dirt)
        with tempfile.TemporaryDirectory(prefix='skill-tree-local-merge-', dir=index_path.parent) as workspace:
            hooks = Path(workspace) / 'hooks'
            hooks.mkdir()
            index = Path(workspace) / 'index'
            shutil.copy2(index_path, index)
            merge = source_head if fast_forward else local_git_text(
                root, 'commit-tree', preparation['source_tree'], signing, '-p', target_head,
                '-p', source_head, '-m', f'Merge {source_ref} into {target_ref}')
            # Run the ref transaction from the distinct source worktree so Git
            # does not try to acquire the canonical worktree's protected HEAD lock.
            verify_refs = preparation.get('verify_refs', ())
            with local_ref_transaction(source_root, hooks, source_ref, source_head, target_ref, target_head, merge, verify_refs) as process:
                if any(local_git(root, 'symbolic-ref', '--quiet', '--no-recurse', ref, accepted=(0, 1)).returncode == 0
                       for ref in (source_ref, target_ref, *(ref for ref, _ in verify_refs))):
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
    payload = payload or {}
    state = store.load(); run = state['active_run']; registry = state.get('run_registry')
    if run:ensure_workspace(store,run)
    root = store.source_root
    profile_path=root/'.skill-tree/installation/profile.json'
    profile=json.loads(profile_path.read_text()) if profile_path.exists() else {'flavor':run.get('admission',{}).get('flavor','general') if run else 'general','facts':{}}
    declaration=root/'.skill-tree/worktree-profile.json'
    policy=json.loads(declaration.read_text()) if declaration.exists() else {'schema':1}
    actual=hashlib.sha256(declaration.read_bytes()).hexdigest() if declaration.exists() else None
    if profile_path.exists() and profile.get('inputs',{}).get('.skill-tree/worktree-profile.json')!=actual:raise RunError('Worktree environment declaration changed; review and refresh the exact worktree profile')
    if policy.get('schema')!=1:raise RunError('Unsupported worktree environment profile')
    flavor=profile['flavor'];defaults={'general':['build','dist','.cache'],'web':['node_modules','dist','build','.next','.cache'],'unity':['Library','Temp','Logs','obj','Builds']}
    layout=('unity' if profile.get('facts',{}).get('editor') else 'general') if flavor=='director' else flavor
    web_runtime_path = None
    if layout=='web':
        common = common_dir(root)
        storage = None if common is None else next((directory for directory in (
            common, Path(local_git_text(root,'rev-parse','--absolute-git-dir')).resolve())
            if within_directory(root,directory)),None)
        prerequisite = (f'Web runtime requires a checkout outside Git administrative storage. '
                        f'Selected checkout {root} lies inside {storage}.' if storage else None)
        web_runtime_path = {'checkout':str(root),'prerequisite':prerequisite}
        if prerequisite and payload.get('runtime'):
            raise RunError(prerequisite)
    missing=[]
    for rel in policy.get('required_files',[]):
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise RunError('Environment prerequisites require repository-relative paths')
        if not (root/path).is_file():missing.append(rel)
    directories=list(dict.fromkeys(defaults[layout]+policy.get('isolated_directories',[])))
    for rel in directories:
        path=Path(rel)
        if path.is_absolute() or '..' in path.parts:raise RunError('Mutable directories require repository-relative paths')
        actual=root/path
        if actual.exists() and not actual.resolve().is_relative_to(root):raise RunError('Concurrent mutable directory sharing lacks verified support: '+rel)
    required_resources=list(policy.get('exclusive_resources',[]))
    if payload.get('runtime') and layout=='unity' and not required_resources:
        raise RunError('Unity runtime requires an explicit Editor/MCP/save/fixture resource policy')
    claims = (registry or {}).get('resources',{})
    resource_claims = []
    for key in required_resources:
        holder = claims.get(key,{}).get('run_id')
        owned = bool(run and holder == run['id'])
        resource_claims.append({'resource':key,'holder_run_id':holder,
                                'status':'owned' if owned else 'occupied' if holder else 'unclaimed'})
        if payload.get('runtime') and not owned:
            raise RunError('Runtime prerequisite requires exclusive resource: '+key)
    if missing:raise RunError('Missing environment prerequisites: '+', '.join(missing))
    result = {'flavor':flavor,'project_root':str(root),'isolated_directories':directories,'required_files':policy.get('required_files',[]),'exclusive_resources':required_resources,'editor_version':profile.get('facts',{}).get('editor'),'secrets_read':False,'runtime_qualified':False}
    if resource_claims:
        result['runtime_resource_claims'] = resource_claims
    if web_runtime_path is not None:
        result['web_runtime_path'] = web_runtime_path
    return result

def native_move_matches(root,run,data,owner,registration,origin,path):
    if runtime(root) != data:
        raise RunError('Worktree locators changed during relocation')
    if not path.is_dir() or path.resolve() != path or root.is_relative_to(path):
        return False
    retained = {**data.get('pending_worktrees',{}), **data['worktrees']}
    if any(rid != run['id'] and worktree_paths_overlap(Path(other).resolve(),path) for rid,other in retained.items()):
        raise RunError('Another controller locates a worktree overlapping the moved destination')
    registered = registered_worktrees(root)
    if path not in registered or origin != path and origin in registered:
        return False
    if linked_registration(root,path) != registration:
        return False
    if checked_out_branch(path)['ref'] != 'refs/heads/'+run['workspace']['branch']:
        return False
    return directed_owner(root,path,run,data['queue_id']) == owner


def recover_verified_move(store, text, state, run, path, resolution, previous_worktree=None):
    registry = state['run_registry']
    try:
        data, owner, locator, registration = cleanup_worktree_owner(store.root,registry,run)
        prior = verified_move_chain(run,owner)
    except RunError:
        return False
    anchor = cleanup_origin_sha256(run)
    if anchor is None:
        return False
    locator_sha, target_sha = locator_path_sha256(locator),locator_path_sha256(path)
    verified_sha = prior['to_locator_sha256'] if prior else anchor
    pending = (prior and prior['from_locator_sha256'] == locator_sha
               and prior['to_locator_sha256'] != locator_sha)
    origin = locator
    if pending:
        if target_sha != verified_sha or previous_worktree is not None:
            raise RunError('Recovery must activate the original recorded relocation destination')
    elif locator_sha != verified_sha:
        if not isinstance(previous_worktree,str) or path != locator:
            raise RunError('The locally recovered worktree location requires the exact previously verified worktree path')
        origin = Path(previous_worktree)
        if (not origin.is_absolute() or origin.resolve() != origin
                or locator_path_sha256(origin) != verified_sha):
            raise RunError('The supplied previous worktree differs from the exact verified location')
    elif previous_worktree is not None:
        previous = Path(previous_worktree) if isinstance(previous_worktree,str) else None
        if (not prior or path != locator or previous is None or not previous.is_absolute()
                or previous.resolve() != previous or locator_path_sha256(previous) != prior['from_locator_sha256']):
            raise RunError('Previous worktree evidence differs from the recorded relocation')
    if path == origin and not prior:
        return False
    if path != origin and run.get('delivery',{}).get('worktree_cleanup',{}).get('attempt'):
        raise RunError('Reconcile the original prepared cleanup before changing the worktree locator')
    if run.get('dispatch_workspace_sha256') and run.get('delivery',{}).get('status') != 'merged':
        return False
    if not native_move_matches(store.root,run,data,owner,registration,origin,path):
        return False
    if path != origin and not pending:
        receipt = {'kind':'verified-worktree-move','owner':owner,
                   'from_locator_sha256':locator_path_sha256(origin),'to_locator_sha256':target_sha,
                   'branch':run['workspace']['branch'],'resolution':resolution}
        run.setdefault('workspace_recoveries',[]).append(receipt)
        store.save(text,state,update_navigation=False)
    if path != locator:
        if not native_move_matches(store.root,run,data,owner,registration,origin,path):
            raise RunError('The original native worktree or branch changed before locator activation')
        activate_worktree_locator(store.root,data,run['id'],path)
    ensure_workspace(store,run)
    return True

def recover_workspace(store,payload):
    if not payload.get('resolution'):
        raise RunError('Explicit recovery requires preserved-work evidence and the resolved condition')
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run or not run.get('workspace'):raise RunError('Select the retained run before workspace recovery')
        data=runtime(store.root);rid=run['id'];spec=run['workspace']
        reserved = run.get('workspace_state') == 'reserved'
        pending = data.get('pending_worktrees',{}).get(rid) if reserved else None
        requested=payload.get('worktree') or data['worktrees'].get(rid) or pending
        if not requested:raise RunError('Recovery requires the recorded or explicitly relocated worktree path')
        path=Path(requested).resolve()
        directed = run.get('dispatch_workspace_sha256')
        if pending is not None and pending != str(path):
            raise RunError('Recovery requires the original exact worktree path')
        if (initial_profile_pending(run)
                and hashlib.sha256(str(path).encode()).hexdigest() != run['initial_profile']['worktree_path_sha256']):
            raise RunError('Initial profile recovery requires the original exact worktree path')
        if reserved:
            anchor = cleanup_origin_sha256(run)
            if anchor is not None and locator_path_sha256(path) != anchor:
                if directed:
                    raise RunError('Director reservation requires the original exact worktree path')
                raise RunError('Recovery requires the original exact reserved worktree path')
        if reserved and run['admission']['flavor']=='web':
            guard_web_destination(data,state['run_registry']['runs'],rid,path)
            tip = git(store.root,'for-each-ref','--format=%(objectname)','refs/heads/'+spec['branch'])
            if tip and tip != spec['base_commit']:
                raise RunError('The reserved Web branch no longer points to the original Git base')
        relocation_pending = pending_verified_move(run,data['worktrees'].get(rid))
        if relocation_pending and not payload.get('worktree'):
            raise RunError('Recovery requires the exact recorded relocation destination')
        if not reserved and payload.get('worktree') and recover_verified_move(
                store,text,state,run,path,payload['resolution'],payload.get('previous_worktree')):
            return run
        if relocation_pending:
            raise RunError('The original recorded relocation awaits the verified native worktree')
        if 'previous_worktree' in payload:
            raise RunError('Previous worktree evidence requires a verified existing native worktree move')
        owned = directed and (reserved or spec.get('dispatch_owner_token') or spec.get('cleanup_owner'))
        if owned and hashlib.sha256(str(path).encode()).hexdigest() != directed:
            raise RunError('Director reservation requires the original exact worktree path')
        if reserved:inspect_directed_reservation(store,run,path)
        created = not path.exists()
        if not created:
            if common_dir(path)!=common_dir(store.root) or git(path,'symbolic-ref','--short','HEAD')!=spec['branch']:
                raise RunError('Recovery never switches a conflicting worktree branch')
        else:
            # Prune never runs automatically; stale Git registrations require an explicit Git repair.
            refs=git(store.root,'for-each-ref','--format=%(refname)','refs/heads/'+spec['branch']).splitlines()
            if 'refs/heads/'+spec['branch'] in refs:
                if directed and reserved:
                    raise RunError('Reserved Director branch has no verifiable worktree registration; preserve it for explicit repair')
                git(store.root,'worktree','add',path,spec['branch'])
            else:
                if run.get('workspace_state')!='reserved':raise RunError('Recorded source branch is missing; recover commits/dirty work before reconstruction')
                git(store.root,'worktree','add','-b',spec['branch'],path,spec['base_commit'])
        if owned:
            spec['cleanup_owner'] = directed_owner(store.root, path, run, data['queue_id'], created=created)
        activate_worktree_locator(store.root,data,rid,path)
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
