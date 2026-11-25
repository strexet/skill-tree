"""Public project choices for an installed, dedicated Director workspace."""
import os
import sys
from pathlib import Path


def descriptor(root):
    D._require(root.is_dir() and D.director_workspace(root) is not None, 'Open the installed Director service workspace')
    data, _ = D._read(root, 'workspace.json')
    profile, _ = D._read(root, '.skill-tree/installation/profile.json')
    D._require(isinstance(data, dict) and data.get('schema') == 1 and data.get('kind') == 'director-workspace'
               and isinstance(profile, dict) and profile.get('flavor') == 'director', 'Director workspace installation is unavailable')
    hosts = data.get('providers')
    actual = {host for record in profile['destinations'].values() if record['name'] == 'skill-tree-director-setup'
              for host in record.get('providers', [record.get('provider')])}
    D._require(isinstance(hosts, list) and hosts and len(set(hosts)) == len(hosts) and set(hosts) == actual,
               'Director hosts differ from the installed Setup receipt')
    entries = [path + '/scripts/director-entry.py' for path, record in profile['destinations'].items()
               if record['name'] == 'skill-tree-director-setup'
               and hosts[0] in record.get('providers', [record.get('provider')])]
    D._require(entries == [data.get('setup_entry')], 'Workspace Setup entry differs from the owned host destination')
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
    workspace = D.director_workspace(root)
    path = Path(supplied) if supplied else workspace/name
    if not path.is_absolute():
        path = workspace/path
    D._require(not {'..', '.git'}.intersection(path.parts) and not any(p.is_symlink() for p in (path, *path.parents)),
               'Select a canonical project directory outside Git administration')
    D._require(not path.is_relative_to(root) and (not root.is_relative_to(path) or path == workspace),
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
        if name == 'coordinator':
            checkout = D._setup_checkout_proof(path)
            if checkout is None or not checkout['head']:
                B.initialize_git(path, D._digest(['director', str(root)]), checkout)
        info = D._setup_project(path, kind, flavor, {'input_sha256': D._digest(pkg['source_digests'])})
        item = {**info, 'path':str(path), 'destination_proof':proof, 'providers':hosts}
    project_journal(B, root, path, item, hosts, source, record)


def registration_area(name, role, path, effects):
    return {'id': name, 'role':role, 'scope':'.', 'checkout':str(path), 'capabilities':['core-task'],
            'allowed_effects':effects, 'interface':{'kind':'skill-tree','version':1}}


def storage_location(workspace, home=None):
    product = D._setup_git_root(workspace)
    if product is None:
        return None
    relative = (workspace / (home or D.DIRECTOR_HOME)).relative_to(product).as_posix()
    D._require('\r' not in relative and '\n' not in relative, 'Unsupported Git path for Director storage')
    return product, relative


def protect_storage(workspace, *, apply=True, home=None):
    location = storage_location(workspace, home)
    if location is not None:
        product, relative = location
        D._bootstrap_helper().protect_git_storage(product, (relative + '/',), apply=apply)


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
                or b'\nSHARED_WORKSPACE_ROUTING = 2\n' not in helper.read_bytes()):
            return 'upgrade-project-installation'
    return 'guarded' if locations else 'upgrade-project-installation'


def projects(root):
    registry, bindings, _ = D.DirectorRegistry(root)._load()
    if not registry:
        return []
    O = D._objective_helper()
    workspace = D.director_workspace(root)
    workspace_owner = D.WS.canonical(workspace) if D._setup_git_root(workspace) == workspace else workspace
    products = []
    for area in sorted(registry['areas'].values(), key=lambda item: item['id']):
        if area['role'] == 'source-maintenance' or area['scope'] != '.':
            continue
        item = {'id':area['id'], 'role':area['role'], 'queue_id':area['queue_id'],
                'allowed_effects':area['allowed_effects'], 'state':'available'}
        try:
            checkout = O._child_root(registry, bindings, area['id'])
            item['checkout'] = str(checkout)
            if checkout == workspace_owner:
                if checkout != workspace:
                    item['workspace_checkout'] = str(workspace)
                item['core_routing'] = shared_routing(workspace)
        except (ValueError, OSError):
            item['state'] = 'unavailable'
        products.append(item)
    return products


def require_coordinator(root, expected_profile, *, allow_uninitialized=False):
    owner = D._inspect_setup_owner(root, expected_profile.get('project_root'), allow_uninitialized)
    proof = D._inspect_profile(root, report_setup_prerequisites=True)
    receipt, digest = D._read(root, '.skill-tree/installation/profile.json')
    D._require(proof['kind'] == 'owned-profile' and proof['sha256'] == digest and receipt == expected_profile,
               'Director coordinator profile changed during setup preflight')
    return owner


def has_interrupted_coordinator_preparation(root, B, coordinator):
    relative = '.skill-tree/artifacts/director/project-preparation/coordinator.json'
    journal, _ = D._read(root, relative)
    if journal is None:
        return False
    D._require(isinstance(journal, dict) and journal.get('schema') == 1 and isinstance(journal.get('item'), dict)
               and isinstance(journal.get('units'), dict), 'Inspect the retained coordinator setup journal')
    item = journal['item']
    path = item.get('path')
    D._require(isinstance(path, str), 'Inspect the retained coordinator setup journal')
    step = journal['units'].get(path, {})
    D._require(isinstance(step, dict) and isinstance(step.get('completed'), list),
               'Inspect the retained coordinator setup progress')
    completed = step['completed']
    stages = ['directory', 'git', 'installation', 'documents', 'core', 'manifest']
    if completed == stages and not step.get('pending'):
        return False
    D._require(path == item.get('queue_root') == str(root)
               and journal.get('root') == B.safe_directory(root)
               and isinstance(journal.get('plan'), dict) and journal['plan'].get('preview_sha256') == D._digest(item)
               and item.get('flavor') == 'director'
               and ((completed == stages[:4] and step.get('pending') == 'core') or
                    (completed == stages[:5] and step.get('pending') in (None, 'manifest'))),
               'Reconcile the retained coordinator setup journal before retrying')
    queue_id, repo_id, owner = coordinator['owner']
    proof = step.get('proof')
    D._require(isinstance(proof, dict) and proof.get('checkout') == D._setup_checkout_proof(root),
               'The retained coordinator preparation belongs to a different Git checkout')
    if step.get('pending') == 'core':
        D._require(step.get('queue_id') == queue_id and proof.get('owner') is None,
                   'The retained coordinator preparation belongs to a different Core queue')
    else:
        binding = {'queue_id': queue_id, 'repo_id': repo_id, 'proof': owner,
                   'locator_sha256': coordinator['locator_sha256']}
        D._require(proof.get('owner') == binding,
                   'The retained coordinator preparation belongs to a different Core owner')
    return True


def require_prepared_coordinator(root, settings, B, owner):
    if has_interrupted_coordinator_preparation(root, B, owner):
        raise D.DirectorPrerequisite(
            'Finish the retained Director coordinator preparation with project-init before project setup.',
            'director-coordinator-preparation', root,
            argv=[sys.executable, '-B', str(root / settings['setup_entry']), 'project-init', str(root)],
        )


def run(raw_root, command, request):
    root = Path(os.path.abspath(raw_root))
    D._require(not any(part.is_symlink() for part in (root, *root.parents)), 'Select the canonical Director workspace')
    if command in ('project-storage-prepare', 'project-storage-verify'):
        protect_storage(D._root(str(root)), apply=command == 'project-storage-prepare')
        return {'status':'ready'}
    settings, pkg = descriptor(root)
    owner = require_coordinator(root, pkg, allow_uninitialized=command == 'project-init')
    B = D._bootstrap_helper()
    if command != 'project-init':
        require_prepared_coordinator(root, settings, B, owner)
    workspace = D.director_workspace(root)
    hosts = settings['providers']
    if command in ('project-menu', 'project-route'):
        products = projects(root)
        if command == 'project-route':
            routing = D.WF.owned_module('director_workspace_routing', Path(__file__).with_name('director-project-routing.py'))
            return routing.preview(D, root, workspace, settings, pkg, products, request)
        return {'director':str(root), 'workspace':str(workspace), 'providers':hosts, 'projects':products,
                'choices':['intake','status','audit','setup'] if products else ['existing','new','later']}
    if command == 'project-init':
        with B.lock(root):
            D._require(descriptor(root) == (settings, pkg), 'Director workspace descriptor changed during setup')
            D._require(require_coordinator(root, pkg, allow_uninitialized=True) == owner,
                       'Director coordinator ownership changed before setup')
            if 'owner' not in owner or has_interrupted_coordinator_preparation(root, B, owner):
                ensure_project(root, root, 'existing', 'director', 'coordinator', hosts, pkg, B)
            else:
                B.protect_coordinator_storage(root)
            D._inspect_owner(root)
            protect_storage(workspace, home=root.relative_to(workspace))
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
        D._require(descriptor(root) == (settings, pkg), 'Director workspace descriptor changed during setup')
        D._require(require_coordinator(root, pkg) == owner, 'Director coordinator ownership changed before setup')
        require_prepared_coordinator(root, settings, B, owner)
        B.protect_coordinator_storage(root)
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
        if path == workspace:
            protect_storage(path, home=root.relative_to(path))
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
