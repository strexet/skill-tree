"""Public project choices for an installed, dedicated Director workspace."""
import os
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


def run(raw_root, command, request):
    root = Path(os.path.abspath(raw_root))
    D._require(not any(part.is_symlink() for part in (root, *root.parents)), 'Select the canonical Director workspace')
    settings, pkg = descriptor(root)
    hosts = settings['providers']
    if command == 'project-menu':
        return {'director':str(root), 'workspace':str(root.parent), 'providers':hosts, 'choices':['existing','new','later']}
    B = D._bootstrap_helper()
    if command == 'project-init':
        with B.lock(root):
            if not D.WS.runtime_file(root) or not D.WS.runtime_file(root).is_file() or not (root/'.git').is_dir():
                ensure_project(root, root, 'existing', 'director', 'coordinator', hosts, pkg, B)
            D._inspect_owner(root)
        return {'status':'ready', 'director':str(root), 'providers':hosts}
    D._require(isinstance(request, dict), 'Supply a project choice using --input')
    name, path, flavor = locations(root, request)
    record = f'.skill-tree/artifacts/director/projects/{name}.json'
    previous, _ = D._read(root, record)
    plan = {'project_id':name,'checkout':str(path),'flavor':flavor,'providers':hosts,'kind':request['kind']}
    prep = f'.skill-tree/artifacts/director/project-preparation/{name}.json'
    if not previous and D._read(root, prep)[0] is None:
        D._setup_target(str(path), request['kind'])
    if previous:
        D._require(all(previous.get(key) == value for key, value in plan.items()), 'The project ID is already bound to another project')
    if command == 'project-preview':
        return {**plan, 'status':'preview'}
    with B.lock(root):
        previous, _ = D._read(root, record)
        if previous:
            D._require(all(previous.get(key) == value for key, value in plan.items()), 'The project ID is already in use')
        maintenance = D.WF.owned_module('director_maintenance', Path(__file__).with_name('director-maintenance.py'))
        source = maintenance.prepare(root, name)
        if not previous:
            ensure_project(root, path, request['kind'], flavor, name, hosts, pkg, B)
        else:
            D._require(D._inspect_owner(path)[0] == previous.get('queue_id') and D._inspect_profile(path)['flavor'] == flavor,
                       'Registered project identity changed')
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
