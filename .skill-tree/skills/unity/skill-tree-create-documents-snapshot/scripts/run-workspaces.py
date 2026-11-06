#!/usr/bin/env python3
"""Git workspaces, canonical queue routing and compatible multi-run metadata."""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import uuid

class RunError(ValueError):
    pass

TERMINAL = {'local-result', 'merged'}

def delivery_finished(run):
    delivery=run.get('delivery',{})
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

def validate_registry(registry):
    if not isinstance(registry, dict) or registry.get('schema') != 1 or not re.fullmatch(r'Q-[a-f0-9-]{36}', registry.get('queue_id', '')):
        raise RunError('Unsupported run registry; explicit recovery required')
    if any(not isinstance(registry.get(k), dict) for k in ['runs', 'claims', 'resources']):
        raise RunError('Corrupt run registry collections')
    for rid, run in registry['runs'].items():
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
