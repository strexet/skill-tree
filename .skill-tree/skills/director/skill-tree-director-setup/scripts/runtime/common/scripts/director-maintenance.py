"""Prepare the Director's independent source repository and persistent project branches."""
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
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
COMPACT_LAYOUT = 'source-only-v1'
INSTALLED = '.skill-tree/installation'
PROFILE = INSTALLED + '/profile.json'
CODEX_PACKAGE = re.compile(r'\.agents/skills/skill-tree-[a-z0-9-]+\Z')
BUNDLE_FILE = re.compile(r'\.skill-tree/installation/(?:[a-zA-Z0-9_.-]+/)*[a-zA-Z0-9_.-]+\Z')
CLIENT_UNAVAILABLE = re.compile(
    r"^fatal: unable to access '[^'\n]+': (?:Could not resolve host:|Failed to connect to |"
    r"Connection timed out|Network is unreachable|Operation timed out)[^\n]*$"
    r"|^ssh: (?:Could not resolve hostname |connect to host [^\n]+: Connection (?:refused|timed out))[^\n]*$",
    re.MULTILINE,
)


class TransportUnavailable(ValueError):
    """The selected upstream could not be reached."""


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


def git(root, *args, materialize=False):
    """Git output and failure text are bounded to avoid exposing transport credentials."""
    environment = D.WS.local_git_environment()
    transport = args[0] in ('clone', 'fetch') or materialize
    if materialize:
        verify_materialization_remote(root)
    if transport:
        # An explicitly selected upstream may use the host's validated, URL-scoped credentials.
        environment = {**os.environ, 'LC_ALL':'C'}
    else:
        environment.update(GIT_NO_LAZY_FETCH='1', GIT_ALLOW_PROTOCOL='')
    # The canonical URL already names the repository endpoint. Keep the HTTP
    # request on that endpoint even if unrelated host defaults allow redirects.
    http = ('-c', 'http.followRedirects=false', '-c', 'http.' + UPSTREAM + '.followRedirects=false') if transport else ()
    command = D.WS.local_git_args(root, '-c', 'core.hooksPath=' + os.devnull, *http, *args)
    try:
        result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=240 if transport else 45)
    except subprocess.TimeoutExpired as error:
        stderr = error.stderr.decode('utf-8',errors='replace') if isinstance(error.stderr,bytes) else error.stderr or ''
        failure = TransportUnavailable if transport and CLIENT_UNAVAILABLE.search(stderr) else ValueError
        raise failure('The maintenance Git operation timed out: ' + args[0]) from error
    if result.returncode:
        unavailable = transport and CLIENT_UNAVAILABLE.search(result.stderr)
        failure = TransportUnavailable if unavailable else ValueError
        raise failure('Maintenance Git operation failed: ' + args[0])
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
    verify_endpoints(root)
    if 'checkout_layout' in state:
        excluded = state.get('excluded_deployments')
        D._require(state['checkout_layout'] == COMPACT_LAYOUT and excluded == deployment_paths(root),
                   'The recorded deployment exclusions differ from the pinned source')
        verify_compact_inventory(root, excluded)
    return state


def verify_endpoints(repository):
    for mode in ((), ('--push',)):
        effective = git(repository, 'remote', 'get-url', '--all', *mode, REMOTE).splitlines()
        D._require(effective == [UPSTREAM], 'The effective upstream URL differs from the registered Skill Tree repository')


def verify_materialization_remote(root):
    verify_endpoints(root)
    partial = git(root, 'config', '--default', '', '--get', 'extensions.partialClone')
    D._require(partial in ('', REMOTE), 'The maintenance checkout has a different partial-clone remote')
    for remote in git(root, 'remote').splitlines():
        promised = git(root, 'config', '--type=bool', '--default=false', '--get', 'remote.' + remote + '.promisor')
        D._require(remote == REMOTE or promised == 'false', 'Another remote can supply maintenance objects')


def tracked_digests(root, objects):
    """Hash exact local Git blobs without fetching or exposing the contents."""
    if not objects or sum(objects.values()) > 64 * 1024 * 1024:
        return {}
    environment = {**D.WS.local_git_environment(),'GIT_NO_LAZY_FETCH':'1','GIT_ALLOW_PROTOCOL':''}
    try:
        result = subprocess.run(D.WS.local_git_args(root,'cat-file','--batch'),
            input=('\n'.join(objects)+'\n').encode('ascii'),env=environment,capture_output=True,timeout=45)
    except subprocess.TimeoutExpired as error:
        raise ValueError('The tracked deployment proof timed out') from error
    if result.returncode:
        return {}
    position = 0
    digests = {}
    for oid,size in objects.items():
        header = f'{oid} blob {size}\n'.encode('ascii')
        if not result.stdout.startswith(header,position):
            return {}
        start = position + len(header)
        end = start + size
        if result.stdout[end:end+1] != b'\n':
            return {}
        digests[oid] = hashlib.sha256(result.stdout[start:end]).hexdigest()
        position = end + 1
    return digests


def tracked_profile(root, *, materialize=False):
    entry = git(root,'ls-tree','HEAD','--',PROFILE).split('\t',1)[0].split()
    if not entry:
        return None
    message = 'The tracked installation profile is outside the compact source ownership contract'
    D._require(len(entry) == 3 and entry[0] in ('100644','100755') and entry[1] == 'blob',message)
    size = git(root,'cat-file','-s',entry[2],materialize=materialize)
    D._require(size.isdigit() and 0 < int(size) <= 16*1024*1024,message)
    try:
        profile = json.loads(git(root,'show',entry[2]))
    except json.JSONDecodeError as error:
        raise ValueError(message) from error
    D._require(isinstance(profile,dict) and profile.get('format') == 'skill-tree-profile'
               and type(profile.get('schema')) is int and profile['schema'] == 1
               and isinstance(profile.get('destinations'),dict) and isinstance(profile.get('bundle_digests'),dict)
               and isinstance(profile.get('project_root'),str)
               and (Path(profile['project_root']).is_absolute() or PureWindowsPath(profile['project_root']).is_absolute()),
               message)
    return profile


def deployment_paths(root):
    """Read the exact pinned install receipt to identify redundant provider packages."""
    profile = tracked_profile(root)
    if profile is None:
        return []
    destinations, bundles = profile['destinations'], profile['bundle_digests']
    packages = {relative:record['files'] for relative, record in destinations.items()
                if CODEX_PACKAGE.fullmatch(relative) and isinstance(record,dict)
                and record.get('name') == relative.rsplit('/',1)[1] and record.get('provider') == 'codex'
                and isinstance(record.get('files'),dict) and D._sha(record['files'].get('SKILL.md'))}
    bundles = {relative:digest for relative,digest in bundles.items()
               if relative != PROFILE and BUNDLE_FILE.fullmatch(relative)
               and not {'.','..'}.intersection(relative.split('/')) and D._sha(digest)}
    if not packages and not bundles:
        return [PROFILE]
    tree = {}
    for row in git(root,'ls-tree','-r','-l','-z','HEAD','--',*packages,*bundles).split('\0'):
        if row:
            metadata, relative = row.split('\t',1)
            mode, kind, oid, size = metadata.split()
            tree[relative] = (oid,int(size)) if kind == 'blob' and mode in ('100644','100755') else None
    digests = tracked_digests(root,dict(value for value in tree.values() if value is not None))
    def matches(relative, expected):
        item = tree.get(relative)
        return item is not None and D._sha(expected) and digests.get(item[0]) == expected
    excluded = [relative for relative,expected in bundles.items() if matches(relative,expected)]
    for package, files in packages.items():
        prefix = package + '/'
        tracked = {name.removeprefix(prefix) for name in tree if name.startswith(prefix)}
        if tracked == set(files) and all(matches(prefix+name,expected) for name,expected in files.items()):
            excluded.append(package)
    return [PROFILE, *sorted(excluded)]


def verify_compact_inventory(root, excluded):
    D._require(not D._safe_path(root, PROFILE).exists(), 'A live installation is present in the source-only checkout')
    for relative in excluded:
        D._require(not D._safe_path(root,relative).exists(),
                   'A redundant installation is present in the source-only checkout')
    for item in git(root,'ls-files','-v','-z','--').split('\0'):
        if not item:
            continue
        flag, relative = item.split(' ',1)
        expected = relative in excluded or any(relative.startswith(prefix+'/') for prefix in excluded
                                                if CODEX_PACKAGE.fullmatch(prefix))
        D._require((flag == 'S') == expected and not flag.islower(),
                   'The maintenance checkout sparsity differs from the owned source inventory')


def full_project_index(project):
    entries = git(project,'ls-files','-v','-z','--').split('\0')
    D._require(any(entries) and not any(entry[:1] == 'S' or entry[:1].islower() for entry in entries),
               'The registered project source checkout requires a fully visible index')


def qualify(root, state):
    declaration, _ = D._read(root, '.skill-tree/config/repository.json')
    D._require(isinstance(declaration, dict) and declaration.get('role') == 'source',
               'The upstream revision must contain canonical Skill Tree source')
    store = D.WF.Store(root, route_queue=False, neutral=True)
    state_path = '.skill-tree/documents/future.json'
    raw, _ = D._read(root, state_path)
    locator = D.WS.runtime_file(root)
    compact = state.get('checkout_layout') == COMPACT_LAYOUT
    if compact:
        D._require(not git(root,'status','--porcelain','--untracked-files=no'),
                   'Compact source qualification requires unchanged tracked source')
    if not locator.exists():
        if raw and raw.get('run_registry'):
            D.WS.recover_locator(store, {'queue_id': raw['run_registry']['queue_id']})
        else:
            D._require(not compact or not store.state.exists(),
                       'The tracked source checkpoint requires compatible portable registration before compact setup')
            D.WS.setup(store, {}, update_navigation=not compact)
    queue, _, _ = D._inspect_owner(root)
    receipt = D._safe_path(root, '.skill-tree/installation/profile.json')
    if receipt.is_file() and not compact:
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
    if compact:
        D._require(not git(root,'status','--porcelain','--untracked-files=no'),
                   'Portable source changed during compact qualification')
    state['queue_id'] = queue
    D.WS.atomic(root / '.git' / MARKER, state)


def provision(root):
    if not root.exists():
        effective = git(root.parent, 'ls-remote', '--get-url', '--', UPSTREAM)
        D._require(effective == UPSTREAM, 'The effective upstream URL differs from the canonical Skill Tree repository')
        with tempfile.TemporaryDirectory(prefix='.maintenance-', dir=root.parent) as directory:
            # Resolve the push endpoint in a fresh local repository before any
            # transfer. Git applies pushInsteadOf independently of fetch rewrites.
            probe = Path(directory) / 'probe.git'
            git(root.parent, 'init', '--bare', '--template=', str(probe))
            git(probe, 'remote', 'add', REMOTE, UPSTREAM)
            verify_endpoints(probe)
            staged = Path(directory) / 'clone'
            git(root.parent, 'clone', '--no-local', '--no-tags', '--no-checkout', '--filter=blob:none',
                '--single-branch', '--branch', BASE,
                '--origin', REMOTE, '--', UPSTREAM, str(staged))
            verify_endpoints(staged)
            profile = tracked_profile(staged, materialize=True)
            initial = ['!/'+PROFILE] if profile is not None else []
            git(staged, 'sparse-checkout','set','--no-cone','/*',*initial, materialize=True)
            git(staged, 'read-tree','-mu','HEAD', materialize=True)
            excluded = deployment_paths(staged)
            if len(excluded) > 1:
                patterns = ['!/'+relative+('/' if CODEX_PACKAGE.fullmatch(relative) else '') for relative in excluded]
                git(staged,'sparse-checkout','set','--no-cone','/*',*patterns,materialize=True)
            verify_compact_inventory(staged, excluded)
            state = {'schema': 1, 'upstream': UPSTREAM, 'checkout': str(root),
                     'revision': git(staged, 'rev-parse', 'HEAD'), 'projects': {},
                     'checkout_layout':COMPACT_LAYOUT,'excluded_deployments':excluded}
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
    if state.get('checkout_layout') == COMPACT_LAYOUT:
        full_project_index(project)
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
        compact = state.get('checkout_layout') == COMPACT_LAYOUT
        record = state['projects'].get(project_id)
        retained = None
        if record is not None and project.exists():
            # Check provenance before fetching or exposing an existing local branch.
            retained = inspect(director_root, project_id)
        target = 'refs/remotes/' + REMOTE + '/' + BASE
        offline = (compact and retained is not None and record['ready']
                   and not git(project,'status','--porcelain=v1','--untracked-files=all'))
        if offline:
            original_tip = git(root,'rev-parse',target)
            original_head = git(project,'rev-parse','HEAD')
        flags = ('--no-tags','--no-write-fetch-head') if compact else ('--no-tags',)
        if compact:
            verify_materialization_remote(root)
        try:
            git(root, 'fetch', *flags, REMOTE, 'refs/heads/' + BASE + ':' + target)
        except TransportUnavailable:
            if not offline:
                raise
            D._require(git(root,'rev-parse',target) == original_tip and git(project,'rev-parse','HEAD') == original_head
                       and not git(project,'status','--porcelain=v1','--untracked-files=all')
                       and inspect(director_root, project_id) == retained, 'Retained maintenance source changed during fetch')
            return {**retained,'source_sync':'retained-local'}
        base = git(root, 'rev-parse', '--verify', 'refs/remotes/' + REMOTE + '/' + BASE + '^{commit}')
        branch = 'skill-tree/' + project_id
        ref = 'refs/heads/' + branch
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
            prefix = ('-c','core.sparseCheckout=false') if compact else ()
            git(root, *prefix, 'worktree', 'add', '--', str(project), branch, materialize=compact)
        if compact and not record['ready']:
            git(project,'config','--worktree','core.sparseCheckout','false')
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
    D.WS.local_git_environment()
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
