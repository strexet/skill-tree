"""Prepare the Director's independent source repository and persistent project branches."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


spec = importlib.util.spec_from_file_location('maintenance_director', Path(__file__).with_name('director-state.py'))
D = importlib.util.module_from_spec(spec)
exec(compile(Path(spec.origin).read_bytes(), spec.origin, 'exec'), D.__dict__)
UPSTREAM = 'https://github.com/strexet/skill-tree.git'
REMOTE = 'upstream'
BASE = 'develop'
MARKER = 'skill-tree-director-maintenance.json'


@contextmanager
def writer(path):
    """An OS lock is released even when an interrupted setup leaves the file behind."""
    if path.is_symlink():
        raise ValueError('The source setup lock must be an ordinary file')
    with path.open('a+b') as output:
        if os.name == 'nt':
            import msvcrt
            if output.tell() == 0:
                output.write(b'0')
                output.flush()
            output.seek(0)
            msvcrt.locking(output.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(output, fcntl.LOCK_EX)
        yield


def git(root, *args):
    """Git output and failure text are bounded to avoid exposing transport credentials."""
    command = D.WS.local_git_args(root, '-c', 'core.hooksPath=' + os.devnull, *args)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240 if args[0] in ('clone','fetch') else 45)
    except subprocess.TimeoutExpired as error:
        raise ValueError('The maintenance Git operation timed out: ' + args[0]) from error
    if result.returncode:
        raise ValueError('Maintenance Git operation failed: ' + args[0])
    return result.stdout.strip()


def paths(director_root, project_id):
    root = D._root(str(director_root))
    D._require(D._token(project_id) and len(project_id) <= 100, 'Select a stable project ID for source maintenance')
    owner = D._safe_path(root, 'sources/skill-tree')
    project = D._safe_path(root, 'sources/projects/' + project_id)
    return owner, project


def owned(root):
    vcs = root / '.git'
    marker = vcs / MARKER
    D._require(vcs.is_dir() and not vcs.is_symlink() and marker.is_file() and not marker.is_symlink(),
               'The source destination belongs to another checkout; choose an unoccupied Director home')
    state = json.loads(marker.read_text())
    D._require(state.get('schema') == 1 and state.get('upstream') == UPSTREAM
               and state.get('checkout') == str(root) and isinstance(state.get('projects'), dict)
               and git(root, 'rev-parse', '--absolute-git-dir') == str(vcs)
               and git(root, 'symbolic-ref', '--short', 'HEAD') == BASE
               and git(root, 'rev-parse', 'HEAD') == state.get('revision')
               and git(root, 'config', '--local', '--get-all', 'remote.' + REMOTE + '.url') == UPSTREAM,
               'The registered maintenance checkout or upstream changed')
    return state


def qualify(root, state):
    declaration, _ = D._read(root, '.skill-tree/config/repository.json')
    D._require(isinstance(declaration, dict) and declaration.get('role') == 'source',
               'The upstream revision must contain canonical Skill Tree source')
    store = D.WF.Store(root, route_queue=False, neutral=True)
    state_path = '.skill-tree/documents/future.json'
    raw, _ = D._read(root, state_path)
    locator = D.WS.runtime_file(root)
    if not locator.exists():
        if raw and raw.get('run_registry'):
            D.WS.recover_locator(store, {'queue_id': raw['run_registry']['queue_id']})
        else:
            D.WS.setup(store, {})
    queue, _, _ = D._inspect_owner(root)
    receipt = D._safe_path(root, '.skill-tree/installation/profile.json')
    if receipt.is_file():
        library = Path(__file__).resolve().parents[2] / 'lib/installation.js'
        # A clean upstream release may carry another host's resolved profile. Rebind and
        # refresh only the byte-owned generation in this new, independently owned clone.
        js = """
const fs = require('node:fs'), path = require('node:path');
const [lib, root] = process.argv.slice(1);
const manager = require(lib), composer = require(path.join(path.dirname(lib), 'composer.js'));
const source = path.join(root, '.skill-tree/installation/source');
const receipt = manager.receipt(root, true, true);
manager.verifyOwned(root, receipt);
if (receipt.project_root !== root) {
  if (manager.hasActiveOperation(root)) throw Error('Settle unfinished source operations before rebind');
  const destination = path.join(root, manager.PROFILE);
  const scratch = fs.mkdtempSync(path.join(path.dirname(destination), '.rebind-'));
  try {
    const candidate = path.join(scratch, 'profile.json');
    fs.writeFileSync(candidate, composer.json({...receipt, project_root:root}));
    fs.renameSync(candidate, destination);
  } finally { fs.rmSync(scratch, {recursive:true,force:true}); }
}
try { manager.verify(root, source); }
catch { manager.refresh(root, source); manager.verify(root, source); }
"""
        result = subprocess.run(['node', '-e', js, str(library), str(root)], capture_output=True, timeout=120)
        D._require(result.returncode == 0, 'The byte-owned upstream installation could not be rebound and verified')
    D._inspect_profile(root)
    state['queue_id'] = queue
    D.WS.atomic(root / '.git' / MARKER, state)


def provision(root):
    if not root.exists():
        with tempfile.TemporaryDirectory(prefix='.maintenance-', dir=root.parent) as directory:
            staged = Path(directory) / 'clone'
            git(root.parent, 'clone', '--no-local', '--no-tags', '--single-branch', '--branch', BASE,
                '--origin', REMOTE, '--', UPSTREAM, str(staged))
            state = {'schema': 1, 'upstream': UPSTREAM, 'checkout': str(root),
                     'revision': git(staged, 'rev-parse', 'HEAD'), 'projects': {}}
            D.WS.atomic(staged / '.git' / MARKER, state)
            staged.rename(root)
    state = owned(root)
    if 'queue_id' not in state:
        qualify(root, state)
    return state


def inspect(director_root, project_id):
    root, project = paths(director_root, project_id)
    state = owned(root)
    record = state['projects'].get(project_id)
    branch = 'skill-tree/' + project_id
    D._require(record and record.get('branch') == branch and project.is_dir()
               and D.WS.common_dir(project) == root / '.git'
               and git(project, 'rev-parse', '--show-toplevel') == str(project)
               and git(project, 'symbolic-ref', '--short', 'HEAD') == branch,
               'The registered project source branch or worktree changed')
    git(project, 'merge-base', '--is-ancestor', record['base_commit'], 'HEAD')
    base = git(root, 'rev-parse', '--verify', 'refs/remotes/' + REMOTE + '/' + BASE + '^{commit}')
    git(root, 'merge-base', '--is-ancestor', record['base_commit'], base)
    queue, _, _ = D._inspect_owner(root)
    D._require(queue == state.get('queue_id'), 'The maintenance queue identity changed')
    return {'checkout': str(root), 'revision': git(root, 'rev-parse', 'HEAD'), 'project_checkout': str(project),
            'branch': branch, 'remote': REMOTE, 'base_branch': BASE, 'base_commit': record['base_commit'], 'queue_id': queue}


def prepare(director_root, project_id):
    root, project = paths(director_root, project_id)
    D.WS.local_git_environment()
    root.parent.mkdir(exist_ok=True)
    with writer(root.parent / '.maintenance.lock'):
        state = provision(root)
        if project_id in state['projects'] and project.exists():
            # Check provenance before fetching or exposing an existing local branch.
            inspect(director_root, project_id)
        git(root, 'fetch', '--no-tags', REMOTE, 'refs/heads/' + BASE + ':refs/remotes/' + REMOTE + '/' + BASE)
        base = git(root, 'rev-parse', '--verify', 'refs/remotes/' + REMOTE + '/' + BASE + '^{commit}')
        branch = 'skill-tree/' + project_id
        ref = 'refs/heads/' + branch
        record = state['projects'].get(project_id)
        exists = bool(git(root, 'for-each-ref', '--format=%(refname)', ref))
        if record is None:
            D._require(not project.exists() and not exists, 'Another checkout or branch occupies the project source destination')
            record = {'branch': branch, 'base_commit': base, 'ready': False}
            state['projects'][project_id] = record
            D.WS.atomic(root / '.git' / MARKER, state)
        if not project.exists():
            D._require(not record['ready'] and record['branch'] == branch,
                       'Restore the registered project source worktree before continuing')
            if not exists:
                git(root, 'update-ref', ref, record['base_commit'], '')
            D._require(git(root, 'rev-parse', ref) == record['base_commit'],
                       'The reserved project branch changed before checkout')
            project.parent.mkdir(exist_ok=True)
            git(root, 'worktree', 'add', '--', str(project), branch)
        result = inspect(director_root, project_id)
        if not record['ready']:
            record['ready'] = True
            D.WS.atomic(root / '.git' / MARKER, state)
        return result


def checked_paths(root, before, after, reviewed):
    changed = D.WS.local_git(root, 'diff', '--no-renames', '--name-only', '-z', before, after, '--').stdout
    names = {os.fsdecode(name) for name in changed.split(b'\0') if name}
    D._require(isinstance(reviewed, dict) and names and names == set(reviewed),
               'The source commit changes paths outside the exact reviewed correction')
    # Do not integrate an unreviewed intermediate tree by merging its descendant.
    ancestry = git(root, 'rev-list', '--parents', '-1', after).split()
    D._require(ancestry == [after, before], 'Select one reviewed source commit directly based on the project head')
    for name, expected in reviewed.items():
        D._require(str(D._scope(name)) == name and name != '.', 'Select an exact repository-relative source file')
        entry = D.WS.local_git(root, 'ls-tree', '-z', after, '--', name).stdout
        if expected is None:
            D._require(not entry, 'The reviewed removal is still present in the source commit')
            continue
        D._require(D._sha(expected) and entry.startswith((b'100644 blob ', b'100755 blob ')),
                   'The correction requires the reviewed ordinary file and SHA-256')
        content = D.WS.local_git(root, 'cat-file', 'blob', after + ':' + name).stdout
        D._require(hashlib.sha256(content).hexdigest() == expected, 'The source commit differs from its reviewed bytes')


def integrate(director_root, project_id, *, expected_head, candidate_commit, reviewed_paths, owner):
    """Land one approved source correction in the persistent project branch without publishing."""
    D._object(owner, {'actor', 'kind', 'reference'})
    D._require(D._token(owner['actor']) and D._token(owner['reference']), 'Select the exact local integration authority')
    D.WF.clarification_evidence({'kind': owner['kind'], 'reference': owner['reference']})
    for oid in (expected_head, candidate_commit):
        D._require(isinstance(oid, str) and re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', oid),
                   'Select exact full Git object IDs for the original branch and reviewed source commit')
    root, project = paths(director_root, project_id)
    with writer(root.parent / '.maintenance.lock'):
        scope = inspect(director_root, project_id)
        checked_paths(root, expected_head, candidate_commit, reviewed_paths)
        state = owned(root)
        record = state['projects'][project_id]
        receipts = record.setdefault('integrations', {})
        request = {'branch': scope['branch'], 'base_commit': expected_head, 'commit': candidate_commit,
                   'reviewed_paths': reviewed_paths, 'owner': owner}
        digest = D._digest(request)
        retained = receipts.get(candidate_commit)
        if retained:
            D._require(retained['request_sha256'] == digest, 'The original source integration scope or authority differs')
            if retained['applied']:
                git(project, 'merge-base', '--is-ancestor', candidate_commit, 'HEAD')
                return retained
        current = git(project, 'rev-parse', 'HEAD')
        if current != candidate_commit:
            D._require(current == expected_head, 'The project branch moved after source review')
            D.WS.unfinished(project)
            D._require(not git(project, 'status', '--porcelain=v1', '--untracked-files=all'),
                       'The project source worktree has local edits; preserve them before integrating the correction')
        else:
            D._require(retained, 'The project branch changed outside the reviewed integration')
        if retained is None:
            retained = {'request_sha256': digest, **request, 'applied': False}
            receipts[candidate_commit] = retained
            D.WS.atomic(root / '.git' / MARKER, state)
        if current != candidate_commit:
            git(project, '-c', 'merge.autoStash=false', 'merge', '--ff-only', '--no-autostash',
                '--no-overwrite-ignore', '--', candidate_commit)
        D._require(git(project, 'rev-parse', 'HEAD') == candidate_commit
                   and git(project, 'symbolic-ref', '--short', 'HEAD') == scope['branch'],
                   'Recheck the project branch before completing the source integration')
        retained['applied'] = True
        D.WS.atomic(root / '.git' / MARKER, state)
        return retained
