"""Prepare the exact destinations approved by guided Director setup."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid


JOURNAL = '.skill-tree/artifacts/director/setup-bootstrap.json'
FUTURE = '.skill-tree/documents/future.md'
STATE = '.skill-tree/documents/future.json'
PROFILE = '.skill-tree/installation/profile.json'
MANIFEST = '.skill-tree/skill-tree.json'
BRANCH = 'refs/heads/develop'
CORE_TRANSACTION = '.skill-tree/.transaction.json'

DOCUMENTS = {
    'project.md': ('Project', 'This workspace was prepared for Director. Project-specific requirements are recorded here.'),
    'technical.md': ('Technical Architecture', 'The project owns the Git checkout and the Core workflow state recorded by setup.'),
    'features.md': ('Features', 'Project feature evidence is pending.'),
    'future.md': ('Future Work', '## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog'),
    'rules.md': ('Project Rules', 'Follow repository instructions and the approved area scope.'),
    'repository-map.md': ('Repository Map', 'The Skill Tree manifest indexes project documents and installed operations.'),
    'build-and-release.md': ('Build and Release', 'Project build and release commands require project evidence.'),
    'testing.md': ('Testing', 'Project test commands require project evidence.'),
    'dependencies.md': ('Dependencies', 'The owned installation profile records the selected Skill Tree flavor and source inputs.'),
}


def identity(path):
    stat = path.stat()
    return {'device': stat.st_dev, 'inode': stat.st_ino}


def safe_directory(path):
    D._require(not any(part.is_symlink() for part in (path, *path.parents)),
               f'Symlink in approved setup destination: {path}')
    if path.exists():
        D._require(path.is_dir(), f'Expected a setup directory: {path}')
        return identity(path)
    return None


def confirm_anchor(proof):
    anchor = Path(proof['anchor'])
    expected = {key: proof[key] for key in ('device', 'inode')}
    D._require(safe_directory(anchor) == expected, f'Approved directory anchor changed: {anchor}')


def make_directory(path, proof, created, save=lambda: None):
    confirm_anchor(proof)
    current = Path(proof['anchor'])
    for part in path.relative_to(current).parts:
        current = current/part
        observed = safe_directory(current)
        if observed is None:
            current.mkdir()
            created[str(current)] = safe_directory(current)
            save()
        else:
            D._require(observed == created.get(str(current)),
                       f'Unverified setup directory: {current}. Review the destination before applying a new preview.')
    return created[str(path)]


@contextmanager
def lock(root):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        opened = os.fstat(fd)
        D._require(safe_directory(root) == {'device': opened.st_dev, 'inode': opened.st_ino},
                   'Coordinator changed while acquiring the setup lock')
        yield
    finally:
        os.close(fd)


def document_bytes(relative):
    title, body = DOCUMENTS[Path(relative).name]
    return f'# {title}\n\n{body}\n'.encode()


def create_file(path, content):
    """Publish complete bytes, exclusively, without replacing an existing file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.director-setup-', dir=path.parent)
    scratch = Path(temporary)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(scratch, path)
    finally:
        scratch.unlink(missing_ok=True)


def project_proof(item):
    checkout = Path(item['path'])
    root = Path(item['queue_root'])
    D._require(safe_directory(root) is not None, f'Canonical project directory is missing: {root}')
    if item['queue_root_proof']:
        confirm_anchor(item['queue_root_proof'])
    git = D._setup_checkout_proof(checkout)
    locator = D.WS.runtime_file(checkout) if git else None
    owner = None
    if locator and (locator.exists() or locator.is_symlink()):
        queue, repository, details = D._inspect_owner(checkout)
        owner = {'queue_id': queue, 'repo_id': repository, 'proof': details,
                 'locator_sha256': D.WF.file_hash(locator)}
    canonical_git = git if root == checkout else D._setup_checkout_proof(root)
    return {'checkout': git, 'canonical_checkout': canonical_git, 'files': D._setup_file_proofs(root), 'owner': owner}


def expected_project(item):
    owner = None
    if item['queue_id']:
        owner = {'queue_id': item['queue_id'], 'repo_id': item['repo_id'], 'proof': item['queue_owner_proof'],
                 'locator_sha256': item['queue_locator_sha256']}
    return {'checkout': item['checkout_proof'], 'canonical_checkout': item['canonical_checkout_proof'],
            'files': item['file_proofs'], 'owner': owner}


def approved_project(item, actual, expected):
    D._require(actual == expected, f'Approved Git, Core or setup file identity changed: {item["path"]}')


def git_input(root, *args, content):
    result = subprocess.run(D.WS.local_git_args(root, *args), input=content, capture_output=True, timeout=45)
    D._require(result.returncode == 0, f'Git bootstrap operation failed in {root}: {args[0]}')
    return result.stdout.decode('ascii').strip()


def initialize_git(root, marker, checkout):
    if checkout is None:
        D.WS.local_git(root, 'init', '--initial-branch=develop', '--template=')
        checkout = D._setup_checkout_proof(root)
    D._require(checkout['ref'] == BRANCH and checkout['common'] == str(root/'.git'),
               f'Git bootstrap has a conflicting branch or owner: {root}')
    refs = D.WS.local_git_text(root, 'for-each-ref', '--format=%(refname)')
    D._require(refs in ('', BRANCH) and not D.WS.local_git(root, 'ls-files', '-z').stdout,
               f'Git bootstrap has existing refs or staged project files: {root}')
    tree = git_input(root, 'hash-object', '-w', '-t', 'tree', '--stdin', content=b'')
    author = 'Skill Tree <skill-tree@localhost> 0 +0000'
    content = (f'tree {tree}\nauthor {author}\ncommitter {author}\n\n'
               f'Initialize Director project\n\nSetup identity: {marker}\n').encode()
    commit = git_input(root, 'hash-object', '-t', 'commit', '--stdin', content=content)
    D._require(checkout['head'] in ('', commit), f'Git bootstrap has an unrelated initial commit: {root}')
    if not checkout['head']:
        git_input(root, 'hash-object', '-w', '-t', 'commit', '--stdin', content=content)
        D.WS.local_git(root, 'update-ref', BRANCH, commit, '')


INSTALL = r"""
const fs = require('node:fs');
const path = require('node:path');
const [library, source, root, flavor, before, state, mode] = process.argv.slice(1);
const manager = require(path.join(library, 'installation.js'));
const composer = require(path.join(library, 'composer.js'));
const provider = composer.readJson(source, 'config/providers.json').providers.find(item => item.id === 'codex');
try {
  if (provider?.projectPath !== '.agents/skills') throw Error('Selected source has an unsupported Codex destination');
  const names = composer.operationNames(source, flavor);
  const selections = names.map(name => ({name, provider: 'codex', rel: path.posix.join(provider.projectPath, name)}));
  function digest(relative) {
    const file = path.join(root, relative);
    return fs.existsSync(file) ? composer.hash(fs.readFileSync(file)) : '';
  }
  if (mode === 'install') {
    manager.install(root, source, flavor, selections, {
      recoverPending: false,
      recoverPluginPending: false,
      guardPlan(plan) {
        if (digest(manager.PROFILE) !== before || digest('.skill-tree/documents/future.json') !== state) {
          throw Error('Installation profile or Core state changed before setup');
        }
        if (Object.hasOwn(plan.changes, '.skill-tree/documents/future.json')) {
          throw Error('Installation would modify an unfinished Core run; finish that run before changing its profile');
        }
      }
    });
  }
  const receipt = manager.verify(root, source);
  const current = receipt.flavor === flavor &&
    composer.json(receipt.source_digests) === composer.json(composer.sourceInputs(source)) &&
    selections.every(({rel, name}) => {
      const record = receipt.destinations[rel];
      return record?.name === name && (record.providers || [record.provider]).includes('codex');
    });
  process.exitCode = current ? 0 : 3;
} catch (error) {
  process.stderr.write(error.message);
  process.exitCode = 2;
}
"""


def installation(root, item, source, baseline, *, apply):
    library = Path(__file__).resolve().parents[2]/'lib'
    env = {key: value for key, value in os.environ.items() if key not in {'NODE_OPTIONS', 'NODE_PATH'}}
    result = subprocess.run(
        ['node', '-e', INSTALL, str(library), str(source), str(root), item['flavor'],
         baseline[PROFILE] or '', baseline[STATE] or '', 'install' if apply else 'verify'],
        capture_output=True, text=True, timeout=120, env=env)
    if apply:
        D._require(result.returncode == 0, result.stderr.strip() or 'Selected installed package failed verification')
    return result.returncode == 0


def guarded_store(root, scope=None):
    class BootstrapStore(D.WF.Store):
        def lock(self):
            return super().lock(local_delivery=scope)

        def recover(self):
            transaction, _ = D._read(root, CORE_TRANSACTION)
            if transaction is not None:
                writes = transaction.get('writes') if isinstance(transaction, dict) else None
                D._require(scope is not None and isinstance(writes, list) and len(writes) == 1
                           and isinstance(writes[0], dict) and writes[0].get('path') == STATE
                           and transaction.get('local_delivery') == scope,
                           f'Reconcile the existing Core transaction before bootstrap: {root}')
            super().recover()

    return BootstrapStore(root, route_queue=False, neutral=True)


class Bootstrap:
    def __init__(self, root, journal):
        self.root, self.journal, self.units = root, journal, journal['units']
        self.current = None
        self.verified = set()

    def save(self):
        D._require(safe_directory(self.root) == self.journal['root'], 'Coordinator directory identity changed')
        path = D._safe_path(self.root, JOURNAL)
        record = {**self.journal, 'integrity_sha256': D._digest(self.journal)}
        D.WS.atomic(path, record)

    def directory(self, item):
        path, proof = Path(item['path']), item['destination_proof']
        self.current = item['path']
        step = self.units.setdefault(item['path'], {'completed': []})
        confirm_anchor(proof)
        if 'destination' not in step:
            actual = safe_directory(path)
            if not proof['exists']:
                actual = make_directory(path, proof, self.journal['created_directories'], self.save)
            D._require(actual == {key: proof[key] for key in ('device', 'inode')} or not proof['exists'],
                       f'Approved project identity changed: {path}')
            step['destination'] = actual
            step['completed'].append('directory')
            self.save()
        D._require(safe_directory(path) == step['destination'], f'Approved destination moved or changed: {path}')
        return step

    def project(self, item, source):
        step = self.directory(item)
        root = Path(item['queue_root'])
        D._require(step.get('pending') == 'core' or not D._safe_path(root, CORE_TRANSACTION).exists(),
                   f'Reconcile the existing Core transaction before bootstrap: {root}')
        if root != Path(item['path']):
            D._require(item['queue_owner_proof'] is not None, 'A separate canonical owner needs prior Core identity')
        proof = step.setdefault('proof', expected_project(item))
        for stage in ('git', 'installation', 'documents', 'core', 'manifest'):
            actual = project_proof(item)
            if stage in step['completed']:
                continue
            self.current = f'{item["path"]} ({stage})'
            pending = step.get('pending')
            if pending:
                D._require(pending == stage, 'Unexpected retained setup step')
                self.reconcile(stage, item, proof, actual, source, step)
            else:
                approved_project(item, actual, proof)
                step['pending'] = stage
                if stage == 'core' and proof['owner'] is None:
                    step['queue_id'] = 'Q-'+str(uuid.uuid4())
                self.save()
                self.reconcile(stage, item, proof, actual, source, step)
            proof = step['proof'] = project_proof(item)
            step['completed'].append(stage)
            del step['pending']
            self.save()
        approved_project(item, project_proof(item), proof)
        D._require(installation(root, item, source, proof['files'], apply=False),
                   f'Owned installation no longer matches the selected source and flavor: {root}')
        self.verified.add(item['path'])
        return proof

    def reconcile(self, stage, item, before, actual, source, step):
        checkout, root = Path(item['path']), Path(item['queue_root'])
        files, observed = before['files'], actual['files']
        changed = {key for key in files if files[key] != observed[key]}
        docs = {key for key in files if key.endswith('.md') and files[key] is None}
        allowed = {'git': set(), 'installation': {PROFILE}, 'documents': docs,
                   'core': {STATE} if before['owner'] is None else set(), 'manifest': {MANIFEST} if files[MANIFEST] is None else set()}
        git_fields = ('checkout', 'canonical_checkout')
        same_git = all(actual[key] == before[key] for key in git_fields)
        new_git = stage == 'git' and all(before[key] is None for key in git_fields)
        D._require(changed <= allowed[stage] and (same_git or new_git),
                   f'Git or setup files changed during {stage}: {root}')
        D._require(actual['owner'] == before['owner'] or (stage == 'core' and before['owner'] is None),
                   f'Canonical Core owner changed during {stage}: {root}')
        if stage == 'git' and before['checkout'] is None:
            initialize_git(checkout, D._digest([self.journal['plan']['preview_sha256'], item['path']]), actual['checkout'])
        elif stage == 'installation':
            if observed[PROFILE] is not None and installation(root, item, source, files, apply=False):
                return
            D._require(observed[PROFILE] == files[PROFILE], f'Installed profile drift: {root}')
            installation(root, item, source, files, apply=True)
        elif stage == 'documents':
            store = guarded_store(root)
            with store.lock():
                D._require(D._setup_file_proofs(root) == observed, f'Setup documents changed before creation: {root}')
                for relative in sorted(docs):
                    data = document_bytes(relative)
                    if relative in changed:
                        D._require(observed[relative] == hashlib.sha256(data).hexdigest(),
                                   f'Bootstrap document differs from the retained intent: {relative}')
                    else:
                        create_file(D._safe_path(root, relative), data)
        elif stage == 'core' and before['owner'] is None:
            self.initialize_core(item, before, actual, step['queue_id'])
        elif stage == 'manifest' and files[MANIFEST] is None:
            store = guarded_store(root)
            with store.lock():
                data = D.WF.dump(D.WF.manifest(store)).encode()
                target = D._safe_path(root, MANIFEST)
                if target.exists():
                    D._require(target.read_bytes() == data, f'Bootstrap manifest changed: {root}')
                else:
                    create_file(target, data)

    def initialize_core(self, item, before, actual, queue):
        root = Path(item['queue_root'])
        scope = {'operation': 'director-bootstrap', 'preview_sha256': self.journal['plan']['preview_sha256'],
                 'project': str(root), 'queue_id': queue}
        store = guarded_store(root, scope)
        if D._safe_path(root, CORE_TRANSACTION).exists():
            with store.lock():
                pass
            actual = project_proof(item)
        if actual['files'][STATE] == before['files'][STATE]:
            D.WS.setup(store, {}, bootstrap_id=queue, expected_state_sha256=before['files'][STATE],
                       expected_queue_sha256=before['files'][FUTURE], update_navigation=False)
        else:
            raw, digest = D._read(root, STATE)
            expected = {'schema': 1, 'queue_id': queue, 'runs': {}, 'claims': {}, 'resources': {}}
            D._require(digest == actual['files'][STATE] and raw.get('schema') == 3
                       and raw.get('run_registry') == expected and raw.get('active_run') is None
                       and raw.get('source_hash') == D.WF.digest(store.text().encode()),
                       f'Interrupted Core initialization conflicts with retained state: {root}')
            if actual['owner'] is None:
                D.WS.recover_locator(store, {'queue_id': queue}, bootstrap_state_sha256=digest)
        got, _, owner = D._inspect_owner(root)
        D._require(got == queue and owner['root'] == str(root), f'Core ownership verification failed: {root}')

    def report(self, status, error=None):
        result = {'status': status, 'preview_sha256': self.journal['plan']['preview_sha256'],
                  'director_id': self.journal['plan']['director_id'],
                  'completed': {path: step['completed'] for path, step in self.units.items()},
                  'verified_projects': sorted(self.verified)}
        if error:
            result.update(prerequisite=self.current, error=str(error))
        else:
            result['workspace'] = self.journal['plan']['workspace']['path']
            result['projects'] = {path: {'queue': step['proof']['owner'], 'profile_sha256': step['proof']['files'][PROFILE]}
                                  for path, step in self.units.items() if 'proof' in step}
            result['areas'] = {}
            for area_id, area in self.journal['plan']['areas'].items():
                path = result['workspace'] if area['topology'] == 'shared' else area['path']
                project = result['projects'][path]
                selected = ('id', 'role', 'capabilities', 'interface', 'allowed_effects', 'path', 'scope', 'flavor', 'topology')
                result['areas'][area_id] = {**{key: area[key] for key in selected}, **project}
        return result

    def apply(self):
        plan = self.journal['plan']
        areas = [plan['areas'][key] for key in sorted(plan['areas'])]
        projects = [plan['workspace'], *(area for area in areas if area['topology'] == 'separate')]
        shared = [area for area in areas if area['topology'] == 'shared']
        snapshots, finished = {}, {}
        try:
            with tempfile.TemporaryDirectory(prefix='skill-tree-director-source-') as staging:
                for item in projects:
                    self.current = f'{item["path"]} (package source)'
                    source = item['source']
                    key = D._digest(source)
                    if key not in snapshots:
                        target = Path(staging)/key/'.skill-tree'
                        actual = D._setup_source({name: source[name] for name in ('checkout', 'revision')},
                                                 item['flavor'], target)
                        D._require(actual == source, 'Approved package source identity changed')
                        snapshots[key] = target
                for item in projects:
                    root = item['queue_root']
                    if root in finished:
                        previous, proof = finished[root]
                        D._require((item['source'], item['flavor']) == (previous['source'], previous['flavor']),
                                   f'Conflicting installations at the same canonical project: {root}')
                        step = self.directory(item)
                        actual = project_proof(item)
                        D._require(actual['owner'] == proof['owner'] and actual['files'] == proof['files']
                                   and actual['canonical_checkout'] == proof['canonical_checkout'],
                                   f'Canonical project identity changed: {root}')
                        if 'proof' in step:
                            approved_project(item, actual, step['proof'])
                        else:
                            D._require(actual['checkout'] == item['checkout_proof']
                                       and actual['canonical_checkout'] == item['canonical_checkout_proof'],
                                       f'Approved linked checkout changed: {item["path"]}')
                            step['proof'] = actual
                            if 'canonical-project' not in step['completed']:
                                step['completed'].append('canonical-project')
                            self.save()
                        self.verified.add(item['path'])
                    else:
                        proof = self.project(item, snapshots[D._digest(item['source'])])
                        finished[root] = (item, proof)
                    if item.get('scope'):
                        D._area_path(Path(root), item['scope'])
                owner = Path(plan['workspace']['queue_root'])
                for area in shared:
                    path = Path(area['path'])
                    self.current = str(path)
                    nearest = next(part for part in (path, *path.parents) if safe_directory(part) is not None)
                    D._require(D._setup_git_root(nearest) == owner, f'Approved shared area has a different Git owner: {path}')
                    self.directory(area)
                    actual = D._area_path(owner, area['scope'])
                    D._require(str(actual) == area['path'], 'Prepared shared area must be in the approved canonical workspace')
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            return self.report('deferred', error)
        return self.report('prepared')


def read_journal(root, expected):
    journal, _ = D._read(root, JOURNAL)
    if journal is None:
        return None
    D._require(isinstance(journal, dict), 'Invalid bootstrap journal')
    integrity = journal.pop('integrity_sha256', None)
    plan = journal.get('plan')
    D._require(integrity == D._digest(journal) and journal.get('schema') == 1
               and journal.get('root') == safe_directory(root)
               and isinstance(plan, dict) and plan.get('preview_sha256') == expected
               and D._digest({key: value for key, value in plan.items() if key != 'preview_sha256'}) == expected,
               'Bootstrap journal conflicts with the exact approved preview or directory')
    return journal


def registration_inputs(root, director_id, expected):
    D._require(D._sha(expected), 'Select the exact prepared bootstrap preview SHA-256')
    journal = read_journal(root, expected)
    D._require(journal is not None and journal['plan']['director_id'] == director_id,
               'An exact prepared Director bootstrap is required')
    plan = journal['plan']
    profiles, owners = {}, {}

    def destination(item):
        path = Path(item['path'])
        step = journal['units'].get(item['path'], {})
        confirm_anchor(item['destination_proof'])
        actual = safe_directory(path)
        D._require(actual is not None and actual == step.get('destination'),
                   f'Prepared setup destination is missing or moved: {path}')
        return path, step

    def project(item):
        path, step = destination(item)
        stages = set(step['completed'])
        D._require('pending' not in step and ({'directory', 'git', 'installation', 'documents',
                   'core', 'manifest'} <= stages or {'directory', 'canonical-project'} <= stages),
                   f'Director bootstrap is incomplete: {path}')
        proof = step['proof']
        canonical = Path(item['queue_root'])
        if item['queue_root_proof']:
            confirm_anchor(item['queue_root_proof'])
        queue, repository, owner = D._inspect_owner(path)
        recorded = proof['owner']
        D._require((queue, repository, owner) == (recorded['queue_id'], recorded['repo_id'], recorded['proof'])
                   and owner['root'] == str(canonical), f'Prepared canonical queue identity changed: {path}')
        if queue not in profiles:
            profiles[queue] = D._inspect_profile(canonical)
        profile = profiles[queue]
        D._require(profile.get('sha256') == proof['files'][PROFILE] and profile.get('flavor') == item['flavor'],
                   f'Prepared installed profile changed: {path}')
        owners[queue] = owner
        return path, queue, repository

    workspace = project(plan['workspace'])
    declared = []
    for area in plan['areas'].values():
        if area['topology'] == 'shared':
            path, _ = destination(area)
            checkout, queue, repository = workspace
            D._require(str(D._area_path(Path(owners[queue]['root']), area['scope'])) == str(path),
                       'Prepared shared scope differs from the approved path')
        else:
            checkout, queue, repository = project(area)
        declared.append({**{key: area[key] for key in D.AREA_FIELDS}, 'checkout': str(checkout),
                         'expected_queue_id': queue, 'expected_repo_id': repository})
    return {'director_id': director_id, 'areas': declared}, profiles, owners


def bootstrap(root, payload):
    D._require(root.is_absolute() and '..' not in root.parts, 'Select the exact absolute setup destination')
    D._object(payload, {'request', 'expected_preview_sha256'})
    expected = payload['expected_preview_sha256']
    D._require(D._sha(expected), 'Bootstrap requires the exact reviewed setup preview SHA-256')
    request = D._digest(payload['request'])
    original = safe_directory(root)
    plan, created = None, {}
    # Missing roots are created only after matching the complete, read-only preview.
    if original is None:
        plan = D._guided_setup_preview(root, payload['request'])
        D._require(plan['preview_sha256'] == expected, 'Approved setup preview changed; review the current preview')
        original = make_directory(root, plan['workspace']['destination_proof'], created)
    with lock(root):
        journal = read_journal(root, expected)
        if journal is not None:
            D._require(journal.get('request_sha256') == request,
                       'Bootstrap journal conflicts with the exact approved request')
        else:
            if plan is None:
                plan = D._guided_setup_preview(root, payload['request'])
            D._require(plan['preview_sha256'] == expected, 'Approved setup preview changed; review the current preview')
            step = {'destination': original, 'completed': ['directory']}
            journal = {'schema': 1, 'root': original, 'request_sha256': request, 'plan': plan,
                       'units': {str(root): step}, 'created_directories': created}
            Bootstrap(root, journal).save()
        D._require(D._read(root, D.REGISTRY)[0] is None and D._read(root, D.BINDINGS)[0] is None,
                   'An existing Director registry or local bindings require the ordinary registration workflow')
        return Bootstrap(root, journal).apply()
