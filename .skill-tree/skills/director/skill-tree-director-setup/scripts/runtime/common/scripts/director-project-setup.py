"""Public project choices for an installed, dedicated Director workspace."""
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path


def descriptor(root):
    D._require(root.is_dir() and root.name == '.skill-tree-director', 'Open the installed .skill-tree-director workspace')
    data, _ = D._read(root, 'workspace.json')
    profile, _ = D._read(root, '.skill-tree/installation/profile.json')
    D._require(isinstance(data, dict) and data.get('schema') == 1 and data.get('kind') == 'director-workspace'
               and isinstance(profile, dict) and profile.get('flavor') == 'director', 'Director workspace installation is unavailable')
    hosts = data.get('providers')
    actual = {host for record in profile['destinations'].values() if record['name'] == 'skill-tree-director-setup'
              for host in record.get('providers', [record.get('provider')])}
    D._require(isinstance(hosts, list) and hosts and len(set(hosts)) == len(hosts) and set(hosts) == actual,
               'Director hosts differ from the installed Setup receipt')
    return data, profile


def flavor_for(path):
    prior, _ = D._read(path, '.skill-tree/installation/profile.json')
    if prior:
        return prior['flavor']
    if (path/'ProjectSettings/ProjectVersion.txt').is_file() and (path/'Packages/manifest.json').is_file():
        return 'unity'
    package, _ = D._read(path, 'package.json')
    packages = set((package or {}).get('dependencies', {})) | set((package or {}).get('devDependencies', {}))
    if packages & {'next', 'react', 'vue', 'vite', 'astro', 'svelte', '@angular/core', '@sveltejs/kit'} or (path/'index.html').is_file():
        return 'web'
    return 'general'


def locations(root, request):
    D._object(request, {'kind', 'name'}, {'flavor', 'path'})
    name, kind = request['name'], request['kind']
    D._require(D._token(name) and len(name) <= 64 and name not in ('skill-tree-source', 'coordinator'),
               'Use a lowercase project ID beginning with a letter and containing letters, numbers or hyphens')
    D._require(kind in ('existing', 'new'), 'Choose an existing or new project')
    supplied = request.get('path')
    D._require(supplied is None or isinstance(supplied, str) and supplied and '\x00' not in supplied,
               'Select a project directory')
    D._require(kind == 'new' or supplied, 'Select the existing project directory')
    path = Path(supplied) if supplied else root.parent/name
    if not path.is_absolute():
        path = root.parent/path
    D._require(not {'..', '.git'}.intersection(path.parts) and not any(p.is_symlink() for p in (path, *path.parents)),
               'Select a canonical project directory outside Git administration')
    D._require(not path.is_relative_to(root) and (not root.is_relative_to(path) or path == root.parent),
               'Select a project outside Director storage or select the workspace itself')
    flavor = request.get('flavor', flavor_for(path))
    D._require(flavor in ('general', 'web', 'unity'), 'Choose general, web or unity for the working project')
    prior, _ = D._read(path, '.skill-tree/installation/profile.json')
    D._require(not prior or prior.get('flavor') == flavor, 'Selected flavor differs from the existing project installation')
    return name, path, flavor


def project_journal(B, root, path, item, hosts, source, record):
    class ProjectBootstrap(B.Bootstrap):
        def save(self):
            D._require(B.safe_directory(root) == self.journal['root'], 'Director workspace moved during setup')
            D.WS.atomic(record, self.journal)

    journal, _ = D._read(root, record.relative_to(root).as_posix())
    if journal is None:
        journal = {'schema': 1, 'root': B.safe_directory(root), 'created_directories': {}, 'units': {},
                   'plan': {'preview_sha256': D._digest(item)}, 'item': item}
        worker = ProjectBootstrap(root, journal)
        worker.save()
    else:
        item = journal['item']
        D._require(item['path'] == str(path) and item['providers'] == hosts,
                   'A different project setup is already recorded at this location')
        worker = ProjectBootstrap(root, journal)
    worker.project(item, source)


def ensure_project(root, path, kind, flavor, name, hosts, pkg, B):
    source = root/'.skill-tree/installation/source'
    record = D._safe_path(root, f'.skill-tree/artifacts/director/project-preparation/{name}.json')
    record.parent.mkdir(parents=True, exist_ok=True)
    retained, _ = D._read(root, record.relative_to(root).as_posix())
    if retained:
        item = retained['item']
        D._require(item['path'] == str(path) and item['flavor'] == flavor, 'The selected project changed on retry')
    else:
        _, proof = D._setup_target(str(path), kind)
        # The independent coordinator can live inside an existing product checkout.
        # Its own Git identity is established before probing the canonical Core owner.
        if name == 'coordinator' and not (path/'.git').exists():
            B.initialize_git(path, D._digest(['director', str(root)]), None)
        info = D._setup_project(path, kind, flavor, {'input_sha256': D._digest(pkg['source_digests'])})
        item = {**info, 'path':str(path), 'destination_proof':proof, 'providers':hosts}
    project_journal(B, root, path, item, hosts, source, record)


def registration_area(name, role, path, effects):
    return {'id': name, 'role':role, 'scope':'.', 'checkout':str(path), 'capabilities':['core-task'],
            'allowed_effects':effects, 'interface':{'kind':'skill-tree','version':1}}


def storage_location(workspace):
    product = D._setup_git_root(workspace)
    if product is None:
        return None
    relative = (workspace / '.skill-tree-director').relative_to(product).as_posix()
    D._require('\r' not in relative and '\n' not in relative, 'Unsupported Git path for Director storage')
    tracked = D.WS.local_git(product, 'ls-files', '-z', '--', relative)
    D._require(not tracked.stdout, 'Director storage overlaps tracked product files')
    return product, relative


def protect_storage(workspace, *, apply=True):
    location = storage_location(workspace)
    if location is None:
        return
    product, relative = location
    common = D.WS.common_dir(product)
    exclude = Path(D.WS.local_git_text(product, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
    D._require(exclude == common / 'info/exclude' and not exclude.is_symlink()
               and not exclude.parent.is_symlink(), 'Select the ordinary Git local exclude file')
    command = D.WS.local_git_args(product, 'check-ignore', '-q', '--no-index', '--', './' + relative + '/')
    command.remove('--literal-pathspecs')  # check-ignore treats the operand as a pathname.
    def ignored():
        result = subprocess.run(command, env=D.WS.local_git_environment(), capture_output=True, timeout=45)
        D._require(result.returncode in (0, 1), 'Could not verify the Director storage exclusion')
        return result.returncode == 0

    def replace(content, mode):
        with tempfile.NamedTemporaryFile(dir=exclude.parent, delete=False) as handle:
            staged = Path(handle.name)
            try:
                handle.write(content)
                handle.flush()
                os.chmod(staged, mode)
                os.replace(staged, exclude)
            finally:
                staged.unlink(missing_ok=True)

    if not apply:
        D._require(ignored(), 'Director storage needs a local Git exclusion. Reapply the Director installation.')
        return
    exclude.parent.mkdir(exist_ok=True)
    with D.WS.local_git_lock(exclude.with_name('exclude.skill-tree.lock')):
        if ignored():
            return
        present = exclude.exists()
        D._require(not exclude.is_symlink() and (not present or exclude.is_file()), 'Unsafe Git local exclude file')
        original = exclude.read_bytes() if present else b''
        mode = stat.S_IMODE(exclude.stat().st_mode) if present else 0o644
        separator = b'\n' if original and not original.endswith(b'\n') else b''
        escaped = re.sub(r'([\\*?\[\] ])', r'\\\1', relative)
        replace(original + separator + os.fsencode('/' + escaped + '/\n'), mode)
        if not ignored():
            if present:
                replace(original, mode)
            else:
                exclude.unlink()
            raise ValueError('Product Git ignore rules expose Director storage. Keep the service directory ignored.')



def shared_routing(checkout):
    profile, _ = D._read(checkout, '.skill-tree/installation/profile.json')
    if not profile:
        return 'upgrade-project-installation'
    locations = [f'{path}/scripts/workflow-state.py' for path, record in profile['destinations'].items()
                 if record['name'] in {'skill-tree-add-pending-task', 'skill-tree-process-future-pending',
                                       'skill-tree-implement-all', 'skill-tree-work-through-next',
                                       'skill-tree-implement-next-future-task'}]
    for relative in locations:
        helper = D._safe_path(checkout, relative)
        package = profile['destinations'][relative.removesuffix('/scripts/workflow-state.py')]
        if (not helper.is_file() or D.WF.file_hash(helper) != package['files'].get('scripts/workflow-state.py')
                or b'\nSHARED_WORKSPACE_ROUTING = 1\n' not in helper.read_bytes()):
            return 'upgrade-project-installation'
    return 'guarded' if locations else 'upgrade-project-installation'


def projects(root):
    registry, bindings, _ = D.DirectorRegistry(root)._load()
    if not registry:
        return []
    O = D._objective_helper()
    products = []
    for area in sorted(registry['areas'].values(), key=lambda item: item['id']):
        if area['role'] == 'source-maintenance' or area['scope'] != '.':
            continue
        item = {'id':area['id'], 'role':area['role'], 'queue_id':area['queue_id'],
                'allowed_effects':area['allowed_effects'], 'state':'available'}
        try:
            checkout = O._child_root(registry, bindings, area['id'])
            item['checkout'] = str(checkout)
            if checkout == root.parent:
                item['core_routing'] = shared_routing(checkout)
        except (ValueError, OSError):
            item['state'] = 'unavailable'
        products.append(item)
    return products


def route(root, products, request):
    D._object(request, {'operation'}, {'project_id', 'route', 'task_ids'})
    operation, mode = request['operation'], request.get('route', 'director')
    queues = {'intake':None, 'process':'Pending Queue', 'implement-next':'Prioritized Next Changes',
              'implement-all':'Prioritized Next Changes'}
    D._require(isinstance(operation, str) and operation in queues and mode in ('director', 'direct'),
               'Select intake, process, implement-next or implement-all and a supported route')
    if 'project_id' in request:
        candidates = [item for item in products if item['id'] == request['project_id']]
    else:
        candidates = [item for item in products if item.get('checkout') == str(root.parent)] or products
    D._require(len(candidates) == 1 and candidates[0]['state'] == 'available',
               'Select an exact available project from project-menu')
    project = candidates[0]
    queue = queues[operation]
    summary = {'route':mode, 'project':project, 'operation':operation, 'queue':queue or 'Pending Queue'}
    if 'preview' not in project['allowed_effects']:
        return {**summary, 'status':'prerequisite', 'task_ids':[], 'limitations':['project-preview-not-authorized']}
    store = D.WF.Store(Path(project['checkout']), route_queue=False, neutral=True)
    text = store.text()
    all_tasks = D.WF.parse(text)
    tasks = [task for task in all_tasks if task['queue'] == queue]
    requested = request.get('task_ids')
    if requested is not None:
        D._require(queue is not None and isinstance(requested, list) and requested
                   and all(isinstance(item, str) for item in requested) and len(set(requested)) == len(requested),
                   'Select distinct exact task identities for this operation')
        D._require(set(requested) <= {task['id'] for task in tasks}, 'A selected task is outside the receiving queue')
        tasks = [task for task in tasks if task['id'] in requested]
    if operation == 'implement-next':
        D._require(requested is None or len(requested) == 1, 'Implement Next selects one exact task')
        tasks = sorted(tasks, key=lambda task: -task['priority'])[:1]
    if operation.startswith('implement-'):
        tasks = sorted(tasks, key=lambda task: -task['priority'])
    limitations = []
    if project.get('core_routing') == 'upgrade-project-installation':
        limitations.append('upgrade-co-located-project-installation-through-project-setup')
    if mode == 'director':
        required_effect = {'intake':'intake', 'process':'process'}.get(operation, 'launch')
        if required_effect not in project['allowed_effects']:
            limitations.append(f'director-{required_effect}-not-authorized')
        if operation != 'intake':
            limitations.append('director-dispatch-requires-one-exact-task-per-assignment')
    task_ids = [task['id'] for task in tasks]
    required = D.WF.dependency_scope(all_tasks, {'snapshot':task_ids}) if operation.startswith('implement-') else set()
    return {**summary, 'status':'preview', 'queue_sha256':D.WF.digest(text.encode()),
            'task_ids':task_ids, 'required_dependency_ids':sorted(required - set(task_ids)),
            'tasks':[{'id':task['id'], 'status':task['status'], 'depends_on':task['depends_on']} for task in tasks],
            'limitations':limitations}



def run(raw_root, command, request):
    root = Path(os.path.abspath(raw_root))
    D._require(not any(part.is_symlink() for part in (root, *root.parents)), 'Select the canonical Director workspace')
    if command in ('project-storage-prepare', 'project-storage-verify'):
        protect_storage(D._root(str(root)), apply=command == 'project-storage-prepare')
        return {'status':'ready'}
    settings, pkg = descriptor(root)
    hosts = settings['providers']
    if command in ('project-menu', 'project-route'):
        products = projects(root)
        if command == 'project-route':
            return route(root, products, request)
        return {'director':str(root), 'workspace':str(root.parent), 'providers':hosts, 'projects':products,
                'choices':['intake','status','audit','setup'] if products else ['existing','new','later']}
    B = D._bootstrap_helper()
    if command == 'project-init':
        with B.lock(root):
            if not D.WS.runtime_file(root) or not D.WS.runtime_file(root).is_file() or not (root/'.git').is_dir():
                ensure_project(root, root, 'existing', 'director', 'coordinator', hosts, pkg, B)
            D._inspect_owner(root)
            protect_storage(root.parent)
        return {'status':'ready', 'director':str(root), 'providers':hosts}
    D._require(isinstance(request, dict), 'Supply a project choice using --input')
    name, path, flavor = locations(root, request)
    record = f'.skill-tree/artifacts/director/projects/{name}.json'
    previous, _ = D._read(root, record)
    plan = {'project_id':name,'checkout':str(path),'flavor':flavor,'providers':hosts,'kind':request['kind']}
    prep = f'.skill-tree/artifacts/director/project-preparation/{name}.json'
    if not previous and D._read(root, prep)[0] is None:
        D._setup_target(str(path), request['kind'])
    def verify_choice(prior):
        stable = ('project_id', 'checkout', 'flavor', 'kind')
        D._require(all(prior.get(key) == plan[key] for key in stable),
                   'The project ID is already bound to another project')
    if previous:
        verify_choice(previous)
    if command == 'project-preview':
        return {**plan, 'status':'preview'}
    with B.lock(root):
        previous, _ = D._read(root, record)
        if previous:
            verify_choice(previous)
        maintenance = D.WF.owned_module('director_maintenance', Path(__file__).with_name('director-maintenance.py'))
        source = maintenance.prepare(root, name)
        if not previous:
            ensure_project(root, path, request['kind'], flavor, name, hosts, pkg, B)
        else:
            D._require(D._inspect_owner(path)[0] == previous.get('queue_id') and D._inspect_profile(path)['flavor'] == flavor,
                       'Registered project identity changed')
            # Reuse the verified project and add newly chosen host destinations in
            # one owned installation transaction. Existing host packages stay owned.
            installed = {'flavor':flavor, 'providers':hosts}
            source_bundle = root / '.skill-tree/installation/source'
            baseline = D._setup_file_proofs(path)
            if not B.installation(path, installed, source_bundle, baseline, apply=False):
                B.installation(path, installed, source_bundle, baseline, apply=True)
        if path == root.parent:
            protect_storage(path)
        child = registration_area(name, flavor, path, ['status','preview','audit','review','intake','process','launch'])
        canonical_source = registration_area('skill-tree-source', 'source-maintenance', source['checkout'],
                                            ['status','preview','audit','review','intake','process','launch'])
        registry = D.DirectorRegistry(root)
        declaration = {'director_id':'workspace-director', 'areas':[child, canonical_source]}
        preview = registry.preview(declaration)
        result = registry.apply({**declaration, 'expected_preview_sha256':preview['preview_sha256']})
        area = result['registry']['areas'][name]
        verified = {**plan,'status':'registered','queue_id':area['queue_id'],'repo_id':area['repo_id'],'maintenance':source}
        D.WS.atomic(D._safe_path(root, record), verified)
        return verified
