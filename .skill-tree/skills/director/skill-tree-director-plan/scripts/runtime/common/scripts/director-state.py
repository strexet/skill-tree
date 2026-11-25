#!/usr/bin/env python3
"""Manage the parent Director registry without changing child queues."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import unicodedata


RUN_COMMANDS = {'run-start', 'run-status', 'run-dispatch', 'run-pause', 'run-resume', 'run-cancel',
                'run-complete-assignment', 'run-supervise', 'decide-open', 'decide-answer'}
RUN_PATH = re.compile(r'\.skill-tree/director/runs/dr-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json\Z')
REGISTRY = '.skill-tree/director/registry.json'
BINDINGS = '.skill-tree/artifacts/director/local-bindings.json'
DIRECTOR_HOME = Path('.skill-tree/.director')
LEGACY_DIRECTOR_HOME = Path('.skill-tree-director')
OBJECTIVE_PATH = re.compile(r'\.skill-tree/director/objectives/ob-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json\Z')
DISPATCH_INTENT_PATH = re.compile(r'\.skill-tree/director/dispatch-intents/[a-f0-9]{64}\.json\Z')
PLAN_COMMANDS = {'plan-preview', 'plan-freeze', 'plan-context', 'plan-impact', 'context-search'}
OBJECTIVE_COMMANDS = {'objective-preview', 'objective-apply', 'objective-read', 'plan-pin', 'outcome-link'}
AREA_FIELDS = {'id', 'role', 'scope', 'capabilities', 'interface', 'allowed_effects'}
READ_EFFECTS = {'status', 'preview', 'audit', 'review'}
WRITE_EFFECTS = {'intake', 'process', 'launch', 'adopt', 'install', 'commit', 'publish', 'schedule'}
TOKEN = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
SETUP_FILES = tuple('.skill-tree/documents/'+name for name in (
    'project.md', 'technical.md', 'features.md', 'future.md', 'rules.md',
    'repository-map.md', 'build-and-release.md', 'testing.md', 'dependencies.md',
)) + ('.skill-tree/documents/future.json', '.skill-tree/skill-tree.json', '.skill-tree/installation/profile.json')
SETUP_COMPOSER_DIRS = {'common', 'domains', 'templates', 'config', 'lib', 'src'}


class DirectorError(ValueError):
    pass


def _core():
    path = Path(__file__).resolve().with_name('workflow-state.py')
    spec = importlib.util.spec_from_file_location('director_workflow', path)
    if spec is None:
        raise DirectorError('The reviewed core workflow helper is unavailable')
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


WF = _core()
WS = WF.workspaces


def _require(condition, message):
    if not condition:
        raise DirectorError(message)


def _digest(value):
    return hashlib.sha256(WF.dump(value).encode()).hexdigest()


def _portable_recipe(root, queue, recipe, resource, source_path):
    """Fingerprint an executed recipe, replacing only verified path relocations."""
    _require(recipe.get('lane') == 'unit' and isinstance(recipe.get('argv'), list)
             and recipe['argv'] and not recipe.get('execution_binding'), 'Unsupported source reproduction recipe')

    def operand(value):
        _require(isinstance(value, str), 'Invalid recipe operand')
        for directory, label in ((root, '{project_root}'), (queue, '{queue_root}')):
            if value == str(directory):
                return label
            if value.startswith(str(directory) + '/'):
                relative = value[len(str(directory)) + 1:]
                return label + '/' + (source_path if relative == resource else relative)
        return source_path if value == resource else value

    # Installed profiles include the declaring registry as their first input.
    # The Core environment receipt proves the exact registry bytes; the portable
    # comparison covers the selected recipe and its actual supporting files.
    names = list(recipe.get('input_paths', []))
    portable = dict(recipe)
    if (portable.get('qualification') == 'owner-declared static recipe; runner unqualified' and names
            and names[0] in {'.skill-tree/config/repository.json', '.skill-tree/validation-recipes.json'}):
        names.pop(0)
        portable.pop('qualification')
    inputs = {}
    for relative in names:
        path = _safe_path(root, relative)
        _require(path.is_file(), 'Missing reproduction recipe input')
        # The repaired resource itself has separate before/after generation proofs.
        inputs[operand(relative)] = '{checked-resource}' if relative == resource else WF.file_hash(path)
    portable.update(argv=[operand(arg) for arg in recipe['argv']], input_paths=[operand(path) for path in names])
    return _digest({'recipe': portable, 'inputs': inputs})


def _sha(value):
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


def _token(value):
    return isinstance(value, str) and TOKEN.fullmatch(value) is not None


def _scope(value):
    _require(isinstance(value, str) and value and '\\' not in value and '\x00' not in value,
             'Area scope requires a normalized relative path')
    if value == '.':
        return PurePosixPath('.')
    parts = value.split('/')
    _require(all(part not in {'', '.', '..', '.git'} for part in parts) and ':' not in parts[0],
             'Area scope requires a normalized relative path')
    return PurePosixPath(value)


def _tokens(values, name):
    _require(isinstance(values, list) and all(_token(value) for value in values),
             f'{name} require portable tokens')
    _require(len(set(values)) == len(values), f'{name} require distinct entries')
    return sorted(values)


def _object(payload, required, optional=()):
    _require(isinstance(payload, dict) and set(required) <= set(payload)
             and not set(payload) - set(required) - set(optional), 'Unexpected Director input fields')


def _root(value):
    _require(isinstance(value, str) and '\x00' not in value, 'A checkout needs a local absolute path')
    path = Path(value)
    _require(path.is_absolute() and not path.is_symlink(), 'A checkout needs a local absolute directory')
    resolved = path.resolve(strict=True)
    _require(resolved == path, 'Select the canonical absolute checkout path without a symlink')
    _require(path.is_dir(), 'A checkout needs a local absolute directory')
    return path


def _safe_path(root, relative):
    path = root
    for part in _scope(relative).parts:
        path = path / part
        _require(not path.is_symlink(), f'Symlink in Director path: {relative}')
    return path


def _read(root, relative):
    path = _safe_path(root, relative)
    if not path.exists():
        return None, None
    _require(path.is_file(), f'Invalid Director metadata file: {relative}')
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _area_path(root, scope):
    path = root
    for part in _scope(scope).parts:
        _require(path.is_dir() and any(entry.name == part for entry in path.iterdir()),
                 'Area scope is unavailable in the canonical checkout')
        path = path / part
        _require(not path.is_symlink(), f'Symlink in Director path: {scope}')
    _require(path.is_dir(), 'Area scope is unavailable in the canonical checkout')
    _require(WS.local_git_text(path, 'rev-parse', '--show-toplevel') == str(root),
             'Area scope belongs to a separate checkout')
    return path


def _inspect_owner(checkout):
    """Read the canonical owner through existing Git and queue identity guards."""
    _require(WS.local_git_text(checkout, 'rev-parse', '--show-toplevel') == str(checkout),
             'Select the exact Git checkout root')
    locator_file = WS.runtime_file(checkout)
    _require(locator_file is not None and locator_file.is_file() and not locator_file.is_symlink(),
             'A stable canonical queue ID requires explicit Core workspace setup')
    canonical = WS.canonical(checkout).resolve()
    common = WS.common_dir(checkout)
    _require(common is not None and WS.common_dir(canonical) == common,
             'Canonical Git ownership could not be verified')
    _require(WS.local_git_text(canonical, 'rev-parse', '--show-toplevel') == str(canonical),
             'The canonical locator must name an exact Git checkout root')
    locator = WS.runtime(checkout)
    raw, _ = _read(canonical, '.skill-tree/documents/future.json')
    _safe_path(canonical, '.skill-tree/documents/future.md')
    _safe_path(canonical, '.skill-tree/history/task-outcomes.jsonl')
    _require(isinstance(raw, dict) and raw.get('schema') == 3,
             'A stable canonical queue ID requires a schema-3 Core queue')
    state = WF.Store(canonical, route_queue=False, neutral=True).load()
    _require(state['schema'] == 3 and state['active_run'] is None, 'Canonically inconsistent Core workspace registry')
    queue_id = state['run_registry']['queue_id']
    _require(WF.valid_id(queue_id, 'Q') and locator.get('queue_id') == queue_id,
             'Canonical queue and local locator identities differ')
    repo_id = WS.repo_id(canonical)
    root_stat = common.stat()
    return queue_id, repo_id, {
        'root': str(canonical),
        'git_common_dir': str(common),
        'device': root_stat.st_dev,
        'inode': root_stat.st_ino,
    }


def _inspect_profile(root):
    relative = '.skill-tree/installation/profile.json'
    receipt, digest = _read(root, relative)
    if receipt is None:
        source, _ = _read(root, '.skill-tree/config/repository.json')
        _require(isinstance(source, dict) and source.get('role') == 'source',
                 'Area requires a current owned Skill Tree installation')
        return {'kind': 'repository-local-source'}
    library = Path(__file__).resolve().parents[2] / 'lib/installation.js'
    _require(library.is_file() and not library.is_symlink(), 'The reviewed profile verifier is unavailable')
    script = r"""
const {join} = require('node:path');
const [library, root] = process.argv.slice(1);
try {
  const core = require(library);
  const receipt = core.verify(root, join(root, '.skill-tree/installation/source'));
  process.stdout.write(JSON.stringify({identity: receipt.identity, flavor: receipt.flavor}));
} catch (error) {
  process.exitCode = 2;
}
"""
    environment = {key: value for key, value in os.environ.items() if key not in {'NODE_OPTIONS', 'NODE_PATH'}}
    result = subprocess.run(['node', '-e', script, str(library), str(root)], capture_output=True,
                            text=True, timeout=30, env=environment)
    _require(result.returncode == 0, 'Area requires a current owned Skill Tree installation')
    _require(WF.file_hash(root / relative) == digest, 'Area profile changed during verification')
    return {'kind': 'owned-profile', **json.loads(result.stdout), 'sha256': digest}


def _area(request):
    _object(request, AREA_FIELDS | {'checkout'}, {'expected_queue_id', 'expected_repo_id'})
    area_id = request['id']
    role = request['role']
    _require(_token(area_id) and _token(role), 'Area ID and role require portable tokens')
    scope = _scope(request['scope']).as_posix()
    _object(request['interface'], {'kind', 'version'})
    _require(request['interface']['kind'] == 'skill-tree' and type(request['interface']['version']) is int
             and request['interface']['version'] == 1, 'Unsupported area interface generation')
    capabilities = _tokens(request['capabilities'], 'Area capabilities')
    effects = _tokens(request['allowed_effects'], 'Area effects')
    _require(set(effects) <= READ_EFFECTS | WRITE_EFFECTS, 'Unsupported area effect')
    queue_id, repo_id, owner = _inspect_owner(_root(request['checkout']))
    _require(request.get('expected_queue_id', queue_id) == queue_id, 'Selected checkout has the wrong queue identity')
    _require(request.get('expected_repo_id', repo_id) == repo_id, 'Selected checkout has the wrong repository identity')
    root = Path(owner['root'])
    _area_path(root, scope)
    if role == 'source-maintenance':
        source, _ = _read(root, '.skill-tree/config/repository.json')
        _require(isinstance(source, dict) and source.get('role') == 'source',
                 'The source-maintenance area requires a canonical Skill Tree source checkout')
    return {
        'id': area_id, 'role': role, 'queue_id': queue_id, 'repo_id': repo_id,
        'scope': scope, 'capabilities': capabilities,
        'interface': request['interface'], 'allowed_effects': effects,
    }, owner


def director_workspace(root):
    if root.name == DIRECTOR_HOME.name and root.parent.name == DIRECTOR_HOME.parent.name:
        return root.parent.parent
    if root.name == LEGACY_DIRECTOR_HOME.name:
        return root.parent
    return None


def _validate_scope_paths(areas, observed, service=None):
    _require(sum(area['role'] == 'source-maintenance' for area in areas) == 1,
             'Register one canonical Skill Tree source-maintenance area')
    workspace = director_workspace(service) if service and (service / 'workspace.json').is_file() else None
    for index, (first, a) in enumerate(observed):
        for second, b in observed[index + 1:]:
            both_write = bool(WRITE_EFFECTS.intersection(first['allowed_effects'])
                              and WRITE_EFFECTS.intersection(second['allowed_effects']))
            if workspace is not None:
                # A colocated product may contain independent registered Git roots.
                # Write-path admission excludes those roots from the parent's scope.
                if (first['queue_id'] != second['queue_id'] and first['repo_id'] != second['repo_id']
                        and first['scope'] == second['scope'] == '.'
                        and (a == workspace and b != a and b.is_relative_to(a)
                             or b == workspace and a != b and a.is_relative_to(b))):
                    continue
            _require(a != b and not (both_write and (a.is_relative_to(b) or b.is_relative_to(a))),
                     f'Areas have overlapping scopes: {first["id"]}, {second["id"]}')


def _validate_scopes(areas, queues, service=None):
    _validate_scope_paths(areas.values(), [(area, Path(queues[area['queue_id']]['root']) / _scope(area['scope']))
                                         for area in areas.values() if area['queue_id'] in queues], service)


def _setup_location_key(path):
    return Path(*(unicodedata.normalize('NFD', part.casefold()) for part in path.parts))


def _setup_target(value, kind):
    _require(kind in ('new', 'existing') and isinstance(value, str) and '\x00' not in value,
             'Setup requires an explicit existing or new local destination')
    path = Path(value)
    _require(path.is_absolute() and not {'..', '.git'}.intersection(_setup_location_key(path).parts),
             'Setup requires an absolute destination outside Git administration')
    _require(not any(part.is_symlink() for part in (path, *path.parents)), 'Symlink in Director setup destination')
    anchor = next(part for part in (path, *path.parents) if part.exists())
    _require(anchor.is_dir(), 'A Director setup destination requires a directory parent')
    if kind == 'existing':
        _require(path.is_dir(), 'Select an existing project directory')
    else:
        _require(not path.exists() or not any(path.iterdir()), 'A new project destination must be empty or absent')
    state = anchor.stat()
    return path, {'exists': path.exists(), 'anchor': str(anchor), 'device': state.st_dev, 'inode': state.st_ino}


def _setup_git_root(path):
    result = WS.local_git(path, 'rev-parse', '--show-toplevel', accepted=(0, 128))
    return Path(os.fsdecode(result.stdout).strip()) if not result.returncode else None


def _setup_source(request, flavor, snapshot=None):
    _object(request, {'checkout', 'revision'})
    root = _root(request['checkout'])
    role, _ = _read(root, '.skill-tree/config/repository.json')
    versions, _ = _read(root, '.skill-tree/config/flavors.json')
    _require(_setup_git_root(root) == root and isinstance(role, dict) and role.get('role') == 'source',
             'Select an exact local Skill Tree package source checkout')
    _require(_token(flavor) and isinstance(versions, dict) and flavor in versions.get('flavors', {}),
             'The selected flavor is unavailable from the package source')
    revision = request['revision']
    _require(isinstance(revision, str) and revision and '\x00' not in revision,
             'Select an exact local package source revision')
    commit = WS.local_git_text(root, 'rev-parse', '--verify', '--end-of-options', revision+'^{commit}')
    _require(commit == WS.local_git_text(root, 'rev-parse', 'HEAD'),
             'The package source checkout must already be at the selected revision')

    # Use the reviewed composer inventory, which includes ignored inputs read by installation.
    composer = Path(__file__).resolve().parents[2] / 'lib/composer.js'
    _require(composer.is_file() and not composer.is_symlink(), 'The reviewed package source inspector is unavailable')
    command = ('const [module,root]=process.argv.slice(1);'
               'process.stdout.write(JSON.stringify(require(module).sourceInputs(root)));')
    environment = {key: value for key, value in os.environ.items() if key not in {'NODE_OPTIONS', 'NODE_PATH'}}
    scan = subprocess.run(['node', '-e', command, str(composer), str(root/'.skill-tree')],
                          capture_output=True, text=True, timeout=30, env=environment)
    _require(scan.returncode == 0, 'The selected package source inventory is unavailable')
    files = json.loads(scan.stdout)
    installer = _safe_path(root, '.skill-tree/bin/install.js')
    _require(installer.is_file(), 'The selected package source installer is unavailable')
    paths = ['.skill-tree/'+name for name in files] + ['.skill-tree/bin/install.js']
    _require(all('\n' not in path and '\r' not in path for path in paths),
             'The package source contains an unsupported path')
    entries = WS.local_git(root, 'ls-tree', '-rz', '--full-tree', commit, '--', '.skill-tree').stdout
    tree = {}
    committed_inputs = set()
    for entry in entries.split(b'\0'):
        if entry:
            metadata, name = entry.split(b'\t', 1)
            mode, kind, oid = metadata.split()
            name = os.fsdecode(name)
            parts = PurePosixPath(name).parts
            if parts[1] in SETUP_COMPOSER_DIRS and '__pycache__' not in parts:
                committed_inputs.add(name)
            if kind == b'blob' and mode in (b'100644', b'100755'):
                tree[name] = oid.decode('ascii')
    _require(committed_inputs.issubset(paths), 'The package source is missing committed composer inputs')
    current = subprocess.run(WS.local_git_args(root, 'hash-object', '--no-filters', '--stdin-paths'),
                             input='\n'.join(paths)+'\n', capture_output=True, text=True, timeout=30)
    _require(current.returncode == 0 and current.stdout.splitlines() == [tree.get(path) for path in paths],
             'The package source contains inputs outside the exact selected commit')
    _require(commit == WS.local_git_text(root, 'rev-parse', 'HEAD'), 'The package source moved during preview')
    installer_blob = WS.local_git(root, 'cat-file', 'blob', tree['.skill-tree/bin/install.js']).stdout
    proof = {'checkout':str(root), 'revision':revision, 'commit':commit, 'input_sha256':_digest(files),
             'installer_sha256':hashlib.sha256(installer_blob).hexdigest()}
    if snapshot is not None:
        for name, expected in {**files, 'bin/install.js':proof['installer_sha256']}.items():
            _require(isinstance(expected, str), 'The package source changed during snapshot')
            content = _safe_path(root, '.skill-tree/'+name).read_bytes()
            _require(hashlib.sha256(content).hexdigest() == expected, 'The package source changed during snapshot')
            destination = snapshot/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        copied = subprocess.run(WS.local_git_args(root, 'hash-object', '--no-filters', '--stdin-paths'),
                                input='\n'.join(str(snapshot/name.removeprefix('.skill-tree/')) for name in paths)+'\n',
                                capture_output=True, text=True, timeout=30)
        _require(copied.returncode == 0 and copied.stdout.splitlines() == [tree[path] for path in paths],
                 'The package snapshot differs from the exact selected commit')
    return proof


def _setup_checkout_proof(path):
    _require(not (path/'.git').is_symlink(), 'Symlink in Git setup identity')
    if not (path/'.git').exists():
        return None
    _require(_setup_git_root(path) == path, 'Git checkout identity changed during setup')
    common = WS.common_dir(path)
    state = common.stat()
    ref = WS.local_git(path, 'symbolic-ref', '--quiet', 'HEAD', accepted=(0, 1))
    head = WS.local_git(path, 'rev-parse', '--verify', 'HEAD', accepted=(0, 128))
    return {'common':str(common), 'device':state.st_dev, 'inode':state.st_ino,
            'head':head.stdout.decode().strip(), 'ref':ref.stdout.decode().strip()}


def _setup_file_proofs(root):
    proofs = {}
    for relative in SETUP_FILES:
        path = _safe_path(root, relative)
        _require(not path.exists() or path.is_file(), f'Conflicting setup destination: {relative}')
        proofs[relative] = WF.file_hash(path)
    return proofs


def _setup_project(path, kind, flavor, source, *, checkout_required=False):
    actions = ['create-directory'] if not path.exists() else []
    root, queue_id, repo_id = path, None, None
    marker = path/'.git'
    _require(not marker.is_symlink(), 'Restore the existing Git checkout identity before setup')
    git_root = _setup_git_root(path) if kind == 'existing' else None
    _require(not marker.exists() or git_root == path, 'Restore the existing Git checkout identity before setup')
    if kind == 'existing' and not git_root:
        bare = WS.local_git(path, 'rev-parse', '--is-bare-repository', accepted=(0, 128))
        _require(bare.stdout.strip() != b'true', 'Director setup requires a worktree for an existing bare Git repository')
    _require(not checkout_required or git_root == path, 'An existing separate area requires an exact Git checkout')
    _require(git_root in (None, path), 'Select the exact coordinator checkout or a new destination')
    locator = WS.runtime_file(path) if git_root else None
    proof, owner, locator_sha = None, None, None
    if locator and (locator.exists() or locator.is_symlink()):
        queue_id, repo_id, owner = _inspect_owner(path)
        root = Path(owner['root'])
        locator_sha = WF.file_hash(locator)
    else:
        state, _ = _read(path, '.skill-tree/documents/future.json')
        _require(state is None or isinstance(state, dict) and state.get('schema') != 3 and not state.get('run_registry'),
                 'Restore the existing canonical queue locator before setup')
        if path.is_dir():
            store = WF.Store(path, route_queue=False, neutral=True)
            store.verify_future_integrity()
            if state is not None:
                _require(store.load()['active_run'] is None, 'Adopt the existing Core checkpoint before setup')
        if not git_root:
            actions.append('initialize-git')
        else:
            worktrees = WS.local_git(path, 'worktree', 'list', '--porcelain', '-z').stdout
            first_entry = worktrees.split(b'\0', 1)[0]
            _require(first_entry == b'worktree ' + os.fsencode(path),
                     'Select the primary Git checkout before initializing the canonical Core queue')
            repo_id = WS.repo_id(path)
        actions.append('register-core-queue')
    missing = []
    for relative in SETUP_FILES:
        destination = _safe_path(root, relative)
        if not destination.exists():
            missing.append(relative)
        else:
            _require(destination.is_file(), f'Conflicting setup destination: {relative}')
    if any(relative.endswith('.md') or relative == '.skill-tree/skill-tree.json' for relative in missing):
        actions.append('initialize-missing-documents')
    profile, _ = _read(root, '.skill-tree/installation/profile.json')
    if profile is not None:
        proof = _inspect_profile(root)
        _require(proof['flavor'] == flavor, 'The existing installed flavor differs from the selected flavor')
        if _digest(profile['source_digests']) != source['input_sha256']:
            actions.append('refresh-owned-installation')
    else:
        _require(not _safe_path(root, '.skill-tree/installation/source').exists(),
                 'Restore the existing owned installation receipt before setup')
        actions.append('install-skill-tree')
    checkout_proof = _setup_checkout_proof(path)
    return {'queue_root':str(root), 'queue_id':queue_id, 'repo_id':repo_id, 'flavor':flavor,
            'source':source, 'profile_proof':proof, 'required_files':list(SETUP_FILES), 'missing_files':missing,
            'queue_sha256':WF.file_hash(root/'.skill-tree/documents/future.md'), 'prerequisites':actions,
            'file_proofs':_setup_file_proofs(root), 'checkout_proof':checkout_proof,
            'canonical_checkout_proof':checkout_proof if root == path else _setup_checkout_proof(root),
            'queue_owner_proof':owner, 'queue_locator_sha256':locator_sha,
            'queue_root_proof':_setup_target(str(root), 'existing')[1] if root.exists() else None}


def _guided_setup_preview(root, request):
    _object(request, {'director_id', 'workspace', 'areas'})
    _require(_token(request['director_id']) and isinstance(request['areas'], list) and request['areas'],
             'Guided Director setup requires an exact Director and selected areas')
    workspace = request['workspace']
    _object(workspace, {'kind', 'source'}, {'providers'})
    root, root_proof = _setup_target(str(root), workspace['kind'])
    root_key = _setup_location_key(root)
    _require(_read(root, REGISTRY)[0] is None, 'An existing Director registry uses the ordinary area registration flow')
    _require(_read(root, BINDINGS)[0] is None, 'Reconcile existing local Director bindings before setup')
    source = _setup_source(workspace['source'], 'director')
    parent = _setup_project(root, workspace['kind'], 'director', source)
    prior, _ = _read(root, '.skill-tree/installation/profile.json')
    observed_hosts = {host for record in (prior or {}).get('destinations', {}).values()
                      for host in record.get('providers', [record.get('provider')])}
    providers = _tokens(workspace.get('providers', sorted(observed_hosts) or ['codex']), 'Setup hosts')
    matrix, _ = _read(Path(source['checkout']), '.skill-tree/config/providers.json')
    _require(isinstance(matrix, dict) and isinstance(matrix.get('providers'), list),
             'The selected package source must include a provider matrix')
    _require(providers and set(providers) <= {host['id'] for host in matrix['providers']}, 'Choose supported Setup hosts')
    parent['providers'] = providers
    areas, observed = {}, []
    for request_area in request['areas']:
        _object(request_area, {'id', 'role', 'capabilities', 'allowed_effects', 'project'}, {'flavor', 'source'})
        area_id, role = request_area['id'], request_area['role']
        _require(_token(area_id) and _token(role) and area_id not in areas, 'Area IDs and roles require distinct portable identities')
        effects = _tokens(request_area['allowed_effects'], 'Area effects')
        _require(set(effects) <= READ_EFFECTS | WRITE_EFFECTS, 'Unsupported area effect')
        project = request_area['project']
        _object(project, {'kind', 'topology', 'path'}, {'placement', 'scope'})
        kind, topology = project['kind'], project['topology']
        _require(topology in ('shared', 'separate'), 'Select shared folder or separate repository topology')
        if kind == 'new':
            _object(project, {'kind', 'topology', 'path', 'placement'})
            placement = project['placement']
            _require(placement in ('inside', 'alongside', 'custom'), 'Select inside, alongside or custom placement')
            value = project['path'] if placement == 'custom' else str(
                (root if placement == 'inside' else root.parent) / _scope(project['path']))
        else:
            _object(project, {'kind', 'topology', 'path'}, {'scope'})
            placement, value = 'existing', project['path']
        path, proof = _setup_target(value, kind)
        path_key = _setup_location_key(path)
        _require(placement != 'alongside' or not path_key.is_relative_to(root_key),
                 'An alongside destination must be outside the coordinator root')
        scope = _scope(project.get('scope', '.'))
        if topology == 'shared':
            _require(root == Path(parent['queue_root']),
                     'Select the canonical coordinator checkout for shared folders')
            _require(path != root and path.is_relative_to(root) and 'scope' not in project,
                     'A shared folder must be an exact scope inside the coordinator')
            _require(not {'source', 'flavor'}.intersection(request_area), 'Shared areas inherit the coordinator package source and flavor')
            existing_git = _setup_git_root(Path(proof['anchor']))
            _require(not existing_git or existing_git == root or not existing_git.is_relative_to(root),
                     'The shared folder belongs to a separate checkout')
            scope = path.relative_to(root)
            prepared = {**parent, 'required_files':[], 'missing_files':[],
                        'prerequisites':['create-directory'] if not proof['exists'] else []}
        else:
            _require(not root_key.is_relative_to(path_key), 'A separate area cannot contain the coordinator root')
            _require({'flavor', 'source'} <= set(request_area), 'A separate area needs a selected flavor and package source')
            flavor = request_area['flavor']
            prepared = _setup_project(path, kind, flavor, _setup_source(request_area['source'], flavor),
                                      checkout_required=kind == 'existing')
            owner = _setup_location_key(Path(prepared['queue_root']))
            _require(not root_key.is_relative_to(owner)
                     and not _setup_location_key(Path(parent['queue_root'])).is_relative_to(owner),
                     'A separate area requires a canonical checkout outside the coordinator queue')
            if kind == 'existing':
                _area_path(Path(prepared['queue_root']), str(scope))
        if role == 'source-maintenance':
            source_record, _ = _read(Path(prepared['queue_root']), '.skill-tree/config/repository.json')
            _require(kind == 'existing' and topology == 'separate' and isinstance(source_record, dict)
                     and source_record.get('role') == 'source',
                     'Select an existing canonical Skill Tree source-maintenance area')
        area = {**prepared, 'providers':providers, 'id':area_id, 'role':role, 'kind':kind, 'path':str(path), 'topology':topology,
                'placement':placement, 'scope':str(scope), 'destination_proof':proof,
                'capabilities':_tokens(request_area['capabilities'], 'Area capabilities'),
                'interface':{'kind':'skill-tree', 'version':1}, 'allowed_effects':effects}
        areas[area_id] = area
        observed.append((area, _setup_location_key(Path(area['queue_root']) / scope)))
    _validate_scope_paths(areas.values(), observed)
    project_roots = {root_key, _setup_location_key(Path(parent['queue_root']))}
    project_roots.update(_setup_location_key(Path(area['queue_root'])) for area in areas.values()
                         if area['topology'] == 'separate')
    separate_checkouts = {_setup_location_key(Path(area[key])) for area in areas.values()
                          if area['topology'] == 'separate' for key in ('path', 'queue_root')}
    for area in areas.values():
        path = _setup_location_key(Path(area['path']))
        if area['topology'] == 'shared':
            _require(not any(path.is_relative_to(checkout) for checkout in separate_checkouts),
                     'A shared folder cannot belong to a planned separate checkout')
        for project_root in project_roots:
            if path != project_root and path.is_relative_to(project_root):
                first = path.relative_to(project_root).parts[0]
                _require(first not in ('.skill-tree', '.agents', 'agents.md'),
                         'An area destination overlaps an owned setup path')
    queue_roots = {}
    for item in (parent, *areas.values()):
        queue = item['queue_id']
        if queue:
            _require(queue_roots.setdefault(queue, item['queue_root']) == item['queue_root'],
                     'An existing queue cannot have multiple local writers')
    installations = {}
    for item in (parent, *(area for area in areas.values() if area['topology'] == 'separate')):
        selected = (item['flavor'], item['source'])
        _require(installations.setdefault(item['queue_root'], selected) == selected,
                 'Conflicting installations at the same canonical project')
    report = {'schema':1, 'operation':'guided-setup-preview', 'director_id':request['director_id'],
              'workspace':{**parent, 'kind':workspace['kind'], 'path':str(root), 'destination_proof':root_proof},
              'areas':areas}
    return {**report, 'preview_sha256':_digest(report)}


class DirectorStore(WF.Store):
    def recover(self):
        transaction, _ = _read(self.root, '.skill-tree/.transaction.json')
        if transaction is not None:
            _require(isinstance(transaction, dict) and isinstance(transaction.get('writes'), list)
                     and transaction['writes'] and all(isinstance(entry, dict) and isinstance(entry.get('path'), str)
                                                       and (entry['path'] in {REGISTRY, BINDINGS} or OBJECTIVE_PATH.fullmatch(entry['path'])
                                                            or DISPATCH_INTENT_PATH.fullmatch(entry['path']) or RUN_PATH.fullmatch(entry['path']))
                                                       for entry in transaction['writes']),
                     'Recover the existing Core transaction before Director setup')
            for entry in transaction['writes']:
                _safe_path(self.root, entry['path'])
        super().recover()


class DirectorRegistry:
    """Keep portable declarations and machine-local queue bindings in the parent writer."""

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.store = DirectorStore(self.root, route_queue=False, neutral=True)

    def _load(self):
        registry, registry_hash = _read(self.root, REGISTRY)
        bindings, bindings_hash = _read(self.root, BINDINGS)
        if registry is not None:
            _require(isinstance(registry, dict) and registry.get('schema') == 1 and _token(registry.get('director_id'))
                     and type(registry.get('revision')) is int and isinstance(registry.get('areas'), dict),
                     'Unsupported portable Director registry')
        if bindings is not None:
            _require(registry is not None and isinstance(bindings, dict) and bindings.get('schema') == 1
                     and bindings.get('director_id') == registry['director_id']
                     and isinstance(bindings.get('queues'), dict), 'Local Director bindings do not match the registry')
        return registry, bindings, {REGISTRY: registry_hash, BINDINGS: bindings_hash}

    def _setup_plan(self, payload):
        _object(payload, {'director_id', 'areas'})
        director_id = payload['director_id']
        requests = payload['areas']
        _require(_token(director_id), 'Director ID requires a portable token')
        _require(isinstance(requests, list) and requests, 'Select one or more exact areas')
        registry, bindings, expected = self._load()
        if registry is None:
            registry = {'schema': 1, 'director_id': director_id, 'revision': 0, 'areas': {}}
        _require(registry['director_id'] == director_id, 'Selected Director identity changed')
        _require(bindings is not None or not registry['areas'], 'Restore missing local bindings through explicit rebind')
        if bindings is None:
            bindings = {'schema': 1, 'director_id': director_id, 'queues': {}}
        areas = deepcopy(registry['areas'])
        queues = deepcopy(bindings['queues'])
        selected = set()
        profile_proofs = {}
        added = []
        for request in requests:
            area, owner = _area(request)
            key = area['id']
            queue_id = area['queue_id']
            _require(key not in selected, f'Duplicate selected area ID: {key}')
            selected.add(key)
            if key in areas:
                _require(area == areas[key], f'Area identity already has a different declaration: {key}')
            else:
                areas[key] = area
                added.append(key)
            previous = queues.get(queue_id)
            _require(previous is None or previous == owner,
                     f'Queue already has a different local writer: {queue_id}. Use explicit rebind for a move.')
            _require(all(existing_id == queue_id or value['git_common_dir'] != owner['git_common_dir']
                         for existing_id, value in queues.items()), 'One Git common directory cannot own two queue identities')
            queues[queue_id] = owner
            if queue_id not in profile_proofs:
                profile_proofs[queue_id] = _inspect_profile(Path(owner['root']))
        _validate_scopes(areas, queues, self.root)
        next_registry = {**registry, 'revision': registry['revision'] + bool(added), 'areas': areas}
        next_bindings = {**bindings, 'queues': queues}
        public = {'schema': 1, 'operation': 'setup', 'registry': next_registry,
                  'added_areas': sorted(added), 'profile_proofs': profile_proofs}
        return public, next_registry, next_bindings, expected

    def _rebind_plan(self, payload):
        _object(payload, {'director_id', 'area_id', 'checkout'})
        registry, bindings, expected = self._load()
        _require(registry is not None and _token(payload['area_id']) and payload['director_id'] == registry['director_id'],
                 'Choose an exact registered Director area for rebind')
        area = registry['areas'].get(payload['area_id'])
        _require(area is not None, 'Choose an exact registered Director area for rebind')
        queue_id, repo_id, owner = _inspect_owner(_root(payload['checkout']))
        _require((queue_id, repo_id) == (area['queue_id'], area['repo_id']),
                 'Rebind requires identical canonical queue and repository identities')
        area_siblings = [entry for entry in registry['areas'].values() if entry['queue_id'] == queue_id]
        for sibling in area_siblings:
            _area_path(Path(owner['root']), sibling['scope'])
        if bindings is None:
            bindings = {'schema': 1, 'director_id': registry['director_id'], 'queues': {}}
        queues = deepcopy(bindings['queues'])
        previous = queues.get(queue_id)
        if previous is not None and previous != owner:
            paths_moved = (previous['root'], previous['git_common_dir']) != (owner['root'], owner['git_common_dir'])
            common_moved = previous['git_common_dir'] != owner['git_common_dir']
            _require(paths_moved and not Path(previous['root']).exists()
                     and (not common_moved or not Path(previous['git_common_dir']).exists()),
                     'The previous canonical writer still exists or has changed identity')
            _require((previous['device'], previous['inode']) == (owner['device'], owner['inode']),
                     'Rebind requires proof of the same moved Git common directory')
        _require(all(existing_id == queue_id or value['git_common_dir'] != owner['git_common_dir']
                     for existing_id, value in queues.items()), 'One Git common directory cannot own two queue identities')
        queues[queue_id] = owner
        _validate_scopes(registry['areas'], queues, self.root)
        profile_proof = _inspect_profile(Path(owner['root']))
        public = {'schema': 1, 'operation': 'rebind', 'director_id': registry['director_id'], 'queue_id': queue_id,
                  'areas': sorted(sibling['id'] for sibling in area_siblings), 'changed': previous != owner,
                  'profile_proof': profile_proof}
        return public, registry, {**bindings, 'queues': queues}, expected

    def _plan(self, payload, rebind):
        if not rebind and isinstance(payload, dict) and 'prepared_preview_sha256' in payload:
            _object(payload, {'director_id', 'prepared_preview_sha256'})
            prepared = payload['prepared_preview_sha256']
            request, profiles, owners = _bootstrap_helper().registration_inputs(self.root, payload['director_id'], prepared)
            public, registry, bindings, expected = self._setup_plan(request)
            _require(all(proof == profiles.get(queue) and bindings['queues'][queue] == owners[queue]
                         for queue, proof in public['profile_proofs'].items()),
                     'Prepared queue or installation changed during registration')
            public['prepared_preview_sha256'] = prepared
        else:
            public, registry, bindings, expected = self._rebind_plan(payload) if rebind else self._setup_plan(payload)
        preview = {**public, 'preview_sha256': _digest({'report': public, 'bindings': bindings, 'baseline': expected})}
        return preview, registry, bindings, expected

    def preview(self, payload, *, rebind=False):
        return self._plan(payload, rebind)[0]

    def apply(self, payload, *, rebind=False):
        _require(isinstance(payload, dict) and _sha(payload.get('expected_preview_sha256')),
                 'Apply requires the reviewed preview SHA-256')
        review_sha = payload['expected_preview_sha256']
        request = {key: value for key, value in payload.items() if key != 'expected_preview_sha256'}
        with self.store.lock():
            preview, registry, bindings, expected = self._plan(request, rebind)
            _require(preview['preview_sha256'] == review_sha, 'Director registry or canonical binding changed since preview')
            for path, digest in expected.items():
                self.store.expect_unchanged(path, digest)
            writes = {REGISTRY: WF.dump(registry), BINDINGS: WF.dump(bindings)}
            changes = {path: value for path, value in writes.items()
                       if hashlib.sha256(value.encode()).hexdigest() != expected[path]}
            if changes:
                self.store.commit(changes)
            return {**preview, 'changed_files': sorted(changes)}


    def setup_status(self, payload):
        _object(payload, {'director_id', 'prepared_preview_sha256'}, {'routing'})
        prepared = payload['prepared_preview_sha256']
        request, profiles, owners = _bootstrap_helper().registration_inputs(self.root, payload['director_id'], prepared)
        registry, bindings, _ = self._load()
        bound = registry is not None and bindings is not None and registry['director_id'] == payload['director_id']
        areas = {}
        for item in request['areas']:
            area, owner = _area(item)
            queue = area['queue_id']
            _require(owner == owners[queue] and _inspect_profile(Path(owner['root'])) == profiles[queue],
                     'Prepared queue or installation changed during status inspection')
            recorded = (registry or {}).get('areas', {}).get(area['id'])
            registration = 'unregistered'
            if recorded is not None:
                matches = bound and recorded == area and bindings['queues'].get(queue) == owner
                registration = 'registered' if matches else 'stale'
            areas[area['id']] = {**area, 'profile': profiles[queue], 'preparation': 'prepared',
                                 'registration': registration, 'routing': {'status': 'unverified', 'receipts': []}}
        routing = payload.get('routing', [])
        _require(isinstance(routing, list), 'Routing status requires exact run and assignment selections')
        seen = set()
        for selection in routing:
            _object(selection, {'director_run_id', 'assignment_id'})
            _require(WF.valid_id(selection['director_run_id'], 'DR') and _token(selection['assignment_id']),
                     'Routing status requires an exact Director run and assignment')
            key = (selection['director_run_id'], selection['assignment_id'])
            _require(key not in seen, 'Routing status selections require distinct assignments')
            seen.add(key)
            observed = _run_helper(self, 'verify-intake', selection)
            area = areas.get(observed['area_id'])
            _require(area and area['registration'] == 'registered'
                     and (area['queue_id'], area['repo_id'], area['scope']) == (observed['queue_id'], observed['repo_id'], observed['scope']),
                     'The observed route is outside the currently registered prepared area')
            area['routing']['receipts'].append(observed)
            if observed['status'] == 'verified':
                area['routing']['status'] = 'verified'
        return {'director_id': payload['director_id'], 'prepared_preview_sha256': prepared, 'areas': areas}

    def retain_dispatch_intent(self, payload):
        _object(payload, {'operation', 'request'}, {'start'})
        request = payload['request']
        _require(isinstance(request, dict) and isinstance(request.get('director_dispatch'), dict),
                 'Director intent requires an exact protocol envelope')
        envelope = request['director_dispatch']
        registry, bindings, _ = self._load()
        _require(registry is not None and bindings is not None
                 and envelope.get('director_id') == registry['director_id']
                 and envelope.get('queue_id') in bindings['queues'], 'Director intent requires a registered child queue')
        helper = WF.director_dispatch_helper()
        return helper.retain_intent(self.store, payload['operation'], request, start_context=payload.get('start'))

    def status(self, payload=None):
        """Project current areas and explicit assignment references without taking any writer lock."""
        payload = {} if payload is None else payload
        _object(payload, set(), {'assignments', 'project_work', 'area_ids'})
        requests = payload.get('assignments', [])
        _require(isinstance(requests, list), 'Assignments require an exact list')
        registry, bindings, _ = self._load()
        _require(registry is not None, 'Register Director areas before requesting status')
        areas = registry['areas']
        owners = (bindings or {}).get('queues', {})
        if 'area_ids' in payload:
            scope = _tokens(payload['area_ids'], 'Status area IDs')
            _require(all(name in areas and 'status' in areas[name]['allowed_effects'] for name in scope),
                     'Select exact status-enabled areas')
            areas = {name: areas[name] for name in scope}
            queue_ids = {area['queue_id'] for area in areas.values()}
            owners = {queue_id: binding for queue_id, binding in owners.items() if queue_id in queue_ids}
        queues = {queue_id: _status_queue(queue_id, binding) for queue_id, binding in owners.items()}
        result_areas = [_status_area(area, queues.get(area['queue_id']))
                        for area in sorted(areas.values(), key=lambda entry: entry['id'])]
        area_states = {entry['id']: entry for entry in result_areas}
        resources = _status_resources(queues)
        selected = set()
        projections = []
        write_scopes = {}
        requested_resources = {}
        for request in requests:
            _assignment_request(request)
            identifier = request['id']
            _require(identifier not in selected, f'Duplicate assignment ID: {identifier}')
            selected.add(identifier)
            area = areas.get(request['area_id'])
            _require(area is not None, 'Select an exact registered assignment area')
            queue = queues.get(area['queue_id'])
            projection, paths = self._status_assignment(area, area_states[area['id']], queue, resources, request)
            projections.append(projection)
            write_scopes[identifier] = paths
            requested_resources[identifier] = set(request.get('resources', []))
        for projection in projections:
            identifier = projection['id']
            if projection['state'] != 'ready':
                continue
            paths = write_scopes[identifier]
            others = [other for other in projections
                      if other['id'] != identifier and other['state'] in {'ready', 'running', 'blocked'}]
            overlap = sorted(other['id'] for other in others
                             if any(_overlap(a, b) for a in paths for b in write_scopes[other['id']]))
            if overlap:
                projection['overlapping_assignments'] = overlap
                projection['prerequisites'].append('assignment-write-overlap')
            child = projection['child']
            if child['task_id'] is not None and any(
                    (child['queue_id'], child['task_id']) == (other['child']['queue_id'], other['child']['task_id'])
                    for other in others):
                projection['prerequisites'].append('duplicate-child-task')
            shared = sorted(other['id'] for other in others
                            if requested_resources[identifier] & requested_resources[other['id']])
            if shared:
                projection['overlapping_resource_assignments'] = shared
                projection['prerequisites'].append('assignment-resource-overlap')
        return {
            'schema': 1, 'director_id': registry['director_id'], 'registry_revision': registry['revision'],
            'areas': result_areas, 'assignments': projections, 'resource_holders': resources,
            'project_work': self._project_work({**registry, 'areas':areas}, queues, payload.get('project_work')),
            'available_independent': [entry['id'] for entry in projections
                                      if entry['state'] == 'ready' and not entry['prerequisites']],
        }

    def _project_work(self, registry, queues, selection):
        whole = {area['id']: area for area in registry['areas'].values()
                 if area['scope'] == '.' and area['role'] != 'source-maintenance'
                 and 'status' in area['allowed_effects']}
        selected_run = None
        if selection is not None:
            _object(selection, {'area_id'}, {'run_id'})
            _require(_token(selection['area_id']) and selection['area_id'] in whole,
                     'Select an exact status-enabled whole project')
            selected_run = selection.get('run_id')
            _require(selected_run is None or WF.valid_id(selected_run, 'WR'), 'Select an exact project run')
            whole = {selection['area_id']: whole[selection['area_id']]}
        projected, directed = [], {}
        for queue_id in sorted({area['queue_id'] for area in whole.values()}):
            queue = queues.get(queue_id, {'status':'unbound'})
            area_ids = sorted(key for key, area in whole.items() if area['queue_id'] == queue_id)
            row = {'queue_id':queue_id, 'area_ids':area_ids, 'state':queue['status'],
                   'runs':[], 'standalone_outcomes':[]}
            projected.append(row)
            if queue['status'] != 'ready':
                continue
            runs = queue['state']['run_registry']['runs']
            row['total_runs'] = len(runs)
            if selected_run:
                _require(selected_run in runs, 'The selected run is outside the project queue')
                selected = [runs[selected_run]]
            else:
                selected = sorted(runs.values(), key=lambda item: (item.get('started_at', ''), item['id']),
                                  reverse=True)[:20]
                tasks = queue['state'].get('tasks', [])
                row['tasks'] = [
                    {key: task[key] for key in ('id', 'title', 'queue', 'status', 'priority', 'depends_on')}
                    for task in tasks[:50]
                ]
                row['total_tasks'] = len(tasks)
            for run in selected:
                owned_dispatch = bool(run.get('dispatch_workspace_sha256') or
                                      (run.get('workspace') or {}).get('dispatch_owner_token'))
                outcomes = [{'task_id':task, 'outcome_id':receipt['id'], 'disposition':receipt['disposition']}
                            for task, receipt in sorted(queue['outcomes'].items())
                            if receipt.get('run_id') == run['id']
                            and run.get('completion_refs', {}).get(task) == receipt['id']]
                entry = {'run_id':run['id'], 'phase':run['phase'], 'task_ids':run['admitted_task_ids'],
                         'route':'director-dispatch' if owned_dispatch else 'direct-project',
                         'audit_coverage':'director-start-unverified' if owned_dispatch else 'outside-director-assignment',
                         'outcomes':outcomes}
                if owned_dispatch:
                    directed[(queue_id, run['id'])] = (queue['root'], run, entry)
                elif any(item['disposition'] == 'completed' for item in outcomes):
                    entry['adoption'] = {'command':'adopt-preview', 'requires':'exact-frozen-assignment-and-outcome'}
                row['runs'].append(entry)
            if selected_run is None:
                standalone = [
                    {'task_id':record['task_id'], 'outcome_id':record['id'], 'run_id':None,
                     'disposition':record['disposition'], 'route':'direct-project',
                     'audit_coverage':'outside-director-assignment'}
                    for record in list(queue['outcomes'].values())[::-1] if record.get('run_id') is None
                ]
                row['standalone_outcomes'] = standalone[:20]
                row['total_standalone_outcomes'] = len(standalone)
        if directed:
            self._project_start_links(registry, directed)
        return projected

    def _project_start_links(self, registry, directed):
        plans = _plan_helper(self)
        dispatch = WF.director_dispatch_helper()
        directory = '.skill-tree/director/runs'
        run_ids = {run_id for _, run_id in directed}
        unavailable = (ValueError, OSError, KeyError, TypeError, AttributeError, subprocess.TimeoutExpired)
        for path in sorted(_safe_path(self.root, directory).glob('dr-*.json')):
            try:
                parent, _ = _read(self.root, f'{directory}/{path.name}')
                parent_id = parent['director_run_id']
                if (parent['schema'] != 1 or not WF.valid_id(parent_id, 'DR') or path.stem != parent_id.lower()
                        or parent['director_id'] != registry['director_id']
                        or parent['phase'] not in {'running', 'paused', 'cancelled'}):
                    continue
                matching = [(name, start) for name, state in parent['assignments'].items()
                            if (start := state['dispatches'].get('start', {})).get('status') == 'recorded'
                            and start.get('result', {}).get('id') in run_ids]
                if not matching:
                    continue
                plan, sha = plans.frozen({key:parent[key] for key in ('objective_id', 'plan_id', 'plan_revision')})
                if sha != parent['plan_sha256']:
                    continue
                specs = {spec['id']:spec for spec in plan['assignments']}
            except unavailable:
                continue
            for name, start in matching:
                try:
                    spec = specs[name]['area']
                    queue_id = spec['queue_id']
                    candidate = directed.get((queue_id, start['result']['id']))
                    area = registry['areas'].get(spec['id'])
                    if (not candidate or not area or 'audit' not in area['allowed_effects']
                            or any(area[key] != spec[key] for key in ('queue_id','repo_id','scope'))):
                        continue
                    root, child, entry = candidate
                    envelope = {'schema':1, 'director_id':parent['director_id'], 'queue_id':queue_id,
                                'assignment_id':name, 'plan_sha256':sha}
                    store = WF.Store(root, route_queue=False, neutral=True)
                    observed = dispatch.observe(store, {'operation':'start', 'director_dispatch':envelope})
                    if observed['observed_result'] == child and observed['receipt']['receipt_sha256'] == start['receipt_sha256']:
                        entry.update(audit_coverage='director-assignment',
                                     audit={'director_run_id':parent_id, 'assignment_id':name, 'run_id':child['id']})
                except unavailable:
                    continue

    def _status_assignment(self, area, area_status, queue, resources, request):
        source = area_status['source']
        task_id = request.get('task_id')
        run_id = request.get('run_id')
        child = {'queue_id': area['queue_id'], 'task_id': task_id, 'run_id': run_id}
        workspace = {'requested': request.get('workspace'), 'selected': None, 'source_isolation': 'unknown',
                     'runtime_isolation': 'requires-separate-proof' if request.get('resources') else 'not-requested'}
        projection = {'id': request['id'], 'area_id': area['id'], 'state': 'unavailable', 'source': source,
                      'child': child, 'workspace': workspace, 'prerequisites': []}
        prerequisites = projection['prerequisites']
        if area_status['state'] not in {'ready', 'dirty', 'overlapping'}:
            prerequisites.append(area_status['state'] + '-area')
            return projection, ()
        if 'profile' in area_status['prerequisites']:
            prerequisites.append('current-owned-profile')
        if queue['local_claims']:
            prerequisites.append('canonical-queue-held')
        status, run = _status_child(queue, child)
        projection['state'] = status
        if status in {'unavailable', 'mismatched'}:
            prerequisites.append(status + '-child-reference')
        if status == 'blocked':
            prerequisites.append('recorded-child-stop')
        holders = {resource: [owner for owner in resources.get(resource, [])
                              if (owner['queue_id'], owner['run_id']) != (area['queue_id'], child['run_id'])]
                   for resource in request.get('resources', [])}
        projection['resource_conflicts'] = {key: value for key, value in holders.items() if value}
        if projection['resource_conflicts']:
            prerequisites.append('runtime-resource-claimed')
        requested = workspace['requested']
        paths = ()
        if requested == 'artifact':
            candidate = '.skill-tree/artifacts/director/candidates/' + request['id']
            try:
                if _safe_path(self.root, candidate).exists():
                    prerequisites.append('candidate-directory-already-present')
                workspace.update(selected='artifact-directory', source_isolation='parent-artifact-directory',
                                 artifact_relative_path=candidate)
            except (DirectorError, OSError):
                prerequisites.append('candidate-path-unavailable')
        elif requested in {'separate-clone', 'separate-runtime'}:
            workspace['selected'] = requested
            prerequisites.append(requested + '-required')
        elif requested in {'existing-checkout', 'recorded-worktree'}:
            paths = tuple(queue['root'] / _scope(area['scope']) / _scope(relative)
                          for relative in request.get('write_paths', []))
            root = queue['root']
            dirty = queue['dirty']
            if requested == 'recorded-worktree':
                try:
                    _require(run and request.get('run_id'), 'Name the exact recorded run for worktree status')
                    selected = WF.Store(root, route_queue=False, neutral=True)
                    WS.ensure_workspace(selected, run)
                    root = selected.source_root
                    _area_path(root, area['scope'])
                    dirty = _dirty_paths(root)
                    workspace.update(selected='recorded-worktree', source_isolation='recorded-worktree',
                                     worktree_id=run['workspace']['worktree_id'],
                                     head=WS.local_git_text(root, 'rev-parse', 'HEAD'))
                except (ValueError, OSError, subprocess.TimeoutExpired):
                    prerequisites.append('recorded-worktree-unavailable')
            else:
                workspace.update(selected='existing-checkout', source_isolation='serial-checkout')
            try:
                for relative in request.get('write_paths', []):
                    _safe_path(root, (_scope(area['scope']) / _scope(relative)).as_posix())
            except (DirectorError, OSError):
                prerequisites.append('write-path-unavailable')
            scoped_dirty = [value for value in dirty
                            if any(_overlap(root / _scope(value), root / _scope(area['scope']) / _scope(relative))
                                   for relative in request.get('write_paths', []))]
            if scoped_dirty:
                prerequisites.append('overlapping-dirty-paths')
                workspace['overlapping_dirty_paths'] = scoped_dirty
            if 'write_paths' not in request:
                prerequisites.append('exact-write-paths-required')
        else:
            prerequisites.append('workspace-selection-required')
        return projection, paths


def _dirty_paths(root):
    raw = WS.local_git(root, 'status', '--porcelain=v1', '-z', '--no-renames', '--untracked-files=all').stdout
    return sorted({item[3:].decode('utf-8').removesuffix('/') for item in raw.split(b'\0') if item})


def _overlap(first, second):
    return first.is_relative_to(second) or second.is_relative_to(first)


def _status_queue(queue_id, binding):
    root = Path(binding['root'])
    if not root.is_dir():
        return {'status': 'unavailable', 'prerequisite': 'restore-canonical-local-path'}
    try:
        observed_queue, repo_id, owner = _inspect_owner(root)
        _require((observed_queue, owner) == (queue_id, binding), 'Stored canonical binding changed')
        store = WF.Store(root, route_queue=False, neutral=True)
        state = store.load()
        _require(state['run_registry']['queue_id'] == queue_id, 'Canonical queue changed during status')
        branch = WS.local_git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', accepted=(0, 1))
        head = WS.local_git_text(root, 'rev-parse', 'HEAD')
        dirty = _dirty_paths(root)
        outcomes = {record['task_id']: record for record in store.outcomes()}
        try:
            profile = _inspect_profile(root)
        except (ValueError, OSError, subprocess.TimeoutExpired):
            profile = None
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return {'status': 'mismatched', 'prerequisite': 'verify-canonical-owner-or-explicitly-rebind'}
    other_claims = [relative for relative in ('.skill-tree/.writer-lock', '.skill-tree/.transaction.json',
                                             '.skill-tree/installation/.install-lock')
                    if (root / relative).exists() or (root / relative).is_symlink()]
    return {'status': 'ready', 'root': root, 'repo_id': repo_id, 'state': state, 'profile': profile,
            'branch': branch.stdout.decode('utf-8').strip() or None, 'head': head,
            'dirty': dirty, 'outcomes': outcomes, 'free_bytes': shutil.disk_usage(root).free,
            'local_claims': other_claims}


def _status_area(area, queue):
    source = {'repo_id': area['repo_id'], 'scope': area['scope'], 'branch': None, 'head': None}
    result = {'id': area['id'], 'role': area['role'], 'queue_id': area['queue_id'], 'source': source,
              'state': 'unbound', 'prerequisites': [], 'dirty_paths': []}
    if queue is None:
        result['prerequisites'].append('explicit-local-bind')
        return result
    if queue['status'] != 'ready':
        result.update(state=queue['status'], prerequisites=[queue['prerequisite']])
        return result
    try:
        _require(queue['repo_id'] == area['repo_id'], 'Canonical repository changed')
        _area_path(queue['root'], area['scope'])
    except (ValueError, OSError, subprocess.TimeoutExpired):
        result.update(state='mismatched', prerequisites=['verify-canonical-area-scope'])
        return result
    source.update(branch=queue['branch'], head=queue['head'])
    scope = _scope(area['scope'])
    dirty = [path for path in queue['dirty'] if _overlap(scope, _scope(path))]
    result.update(state='dirty' if dirty else 'ready', dirty_paths=dirty, profile=queue['profile'],
                  observations={'queue_schema': queue['state']['schema'],
                                'observed_queue_sha256': queue['state']['source_hash'],
                                'free_bytes': queue['free_bytes'], 'local_claims': queue['local_claims']})
    if queue['profile'] is None:
        result['prerequisites'].append('profile')
    return result


def _status_resources(queues):
    result = {}
    for queue_id, view in sorted(queues.items()):
        if view['status'] == 'ready':
            for key, resource in sorted(view['state']['run_registry']['resources'].items()):
                holder = {'queue_id': queue_id, 'run_id': resource.get('run_id')}
                result.setdefault(key, []).append(holder)
    return result


def _assignment_request(request):
    _object(request, {'id', 'area_id'}, {'task_id', 'run_id', 'workspace', 'write_paths', 'resources'})
    _require(_token(request['id']) and _token(request['area_id']), 'Assignment and area IDs require exact portable identities')
    if 'task_id' in request:
        value = request['task_id']
        _require(any(WF.valid_id(value, kind) for kind in ('P', 'T')), 'Assignment task requires an exact P or T identity')
    if 'run_id' in request:
        _require(WF.valid_id(request['run_id'], 'WR'), 'Assignment run requires an exact WR identity')
    if 'workspace' in request:
        _require(isinstance(request['workspace'], str) and request['workspace'] in {'existing-checkout', 'artifact',
                'recorded-worktree', 'separate-clone', 'separate-runtime'}, 'Unsupported assignment workspace choice')
    if 'write_paths' in request:
        paths = request['write_paths']
        _require(isinstance(paths, list), 'Assignment writes require an explicit relative path list')
        normalized = [_scope(path) for path in paths]
        _require(len(set(normalized)) == len(normalized), 'Assignment write paths must be distinct')
    if 'resources' in request:
        resources = request['resources']
        _require(isinstance(resources, list) and all(isinstance(key, str) and re.fullmatch(r'[a-z0-9][a-z0-9:/._-]*', key)
                 for key in resources) and len(set(resources)) == len(resources), 'Assignment resources require exact distinct keys')


def _status_child(queue, child):
    state = queue['state']
    registry = state['run_registry']
    task_id = child['task_id']
    run_id = child['run_id']
    task = next((item for item in state['tasks'] if item['id'] == task_id), None)
    outcome = queue['outcomes'].get(task_id)
    claim = registry['claims'].get(task_id)
    if run_id is None and (claim or outcome and outcome.get('run_id')):
        run_id = claim or outcome['run_id']
        child['run_id'] = run_id
    run = registry['runs'].get(run_id)
    child.update(task_ref='.skill-tree/documents/future.md' if task else None,
                 run_ref='.skill-tree/documents/future.json' if run else None,
                 outcome={'id': outcome.get('id'), 'path': '.skill-tree/history/task-outcomes.jsonl'} if outcome else None)
    if run_id is not None and run is None:
        return 'unavailable', None
    if run and task_id:
        scope = {run.get('root_task_id'), *run.get('admitted_task_ids', []), *run.get('pending_ids', []),
                 *run.get('completed_ids', [])}
        if task_id not in scope or (claim and claim != run_id):
            return 'mismatched', None
    if run:
        child.update(phase=run.get('phase'), workspace_state=run.get('workspace_state'),
                     processing_rounds=len(run.get('processing_results', [])),
                     completed_units=len(run.get('completed_ids', [])),
                     workspace_recoveries=len(run.get('workspace_recoveries', [])))
    if outcome:
        if outcome.get('run_id') != run_id or (run and run.get('completion_refs', {}).get(task_id) != outcome['id']):
            return 'mismatched', None
        return outcome.get('disposition', 'unavailable'), run
    if run and run.get('stop_reason'):
        return 'blocked', run
    if run and not WS.delivery_finished(run):
        return 'running', run
    if not task:
        return ('completed' if run and run.get('phase') == 'completed' and task_id is None else 'unavailable'), run
    return {'Pending Queue': 'pending', 'Prioritized Next Changes': 'ready' if task['status'] == 'Ready' else 'blocked',
            'Backlog': 'backlog'}[task['queue']], run


def _objective_helper():
    from types import SimpleNamespace
    helper = WF.owned_module('director_objectives', Path(__file__).with_name('director-objectives.py'))
    helper.D = SimpleNamespace(**globals())
    return helper


def _plan_helper(director):
    path = Path(__file__)
    compiler = WF.owned_module('director_plans', path.with_name('director-plans.py'))
    adapters = WF.owned_module('director_plan_adapters', path.with_name('director-plan-adapters.py'))
    objectives = _objective_helper()
    return adapters.DirectorPlans(director, objectives.D, objectives, compiler)


def _bootstrap_helper():
    from types import SimpleNamespace
    helper = WF.owned_module('director_bootstrap', Path(__file__).with_name('director-bootstrap.py'))
    helper.D = SimpleNamespace(**globals())
    return helper


def _run_helper(director, command, payload):
    from types import SimpleNamespace
    path = Path(__file__)
    questions = WF.owned_module('director_questions', path.with_name('director-questions.py'))
    questions.wf = WF
    runner = WF.owned_module('director_run', path.with_name('director-run.py'))
    runner.D = SimpleNamespace(**globals())
    runner.QUESTIONS = questions
    return runner.run(director, _plan_helper(director), command, payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=sorted({'project-menu', 'project-route', 'project-storage-prepare', 'project-storage-verify', 'project-init', 'project-preview', 'project-setup', 'setup-preview', 'setup-apply', 'setup-bootstrap', 'setup-status', 'rebind-preview', 'rebind', 'status', 'dispatch-intent'} | OBJECTIVE_COMMANDS | PLAN_COMMANDS | RUN_COMMANDS))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', type=Path)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.input.read_text()) if args.input else None
        if args.command.startswith('project-'):
            from types import SimpleNamespace
            app = WF.owned_module('director_project_setup', Path(__file__).with_name('director-project-setup.py'))
            app.D = SimpleNamespace(**globals())
            result = app.run(args.root, args.command, payload)
            print(WF.dump(result), end='')
            return 0
        if args.command == 'setup-preview' and isinstance(payload, dict) and 'workspace' in payload:
            print(WF.dump(_guided_setup_preview(args.root, payload)), end='')
            return 0
        if args.command == 'setup-bootstrap':
            result = _bootstrap_helper().bootstrap(args.root, payload)
            print(WF.dump(result), end='')
            return 0 if result['status'] == 'prepared' else 2
        director = DirectorRegistry(args.root)
        if args.command in OBJECTIVE_COMMANDS:
            _require(args.input is not None, '--input is required for Director objective operations')
            result = _objective_helper().run(director, args.command, payload)
        elif args.command in PLAN_COMMANDS:
            _require(args.input is not None, '--input is required for Director plan operations')
            result = _plan_helper(director).run(args.command, payload)
        elif args.command in RUN_COMMANDS:
            _require(args.input is not None, '--input is required for Director run and decision operations')
            result = _run_helper(director, args.command, payload)
        elif args.command == 'dispatch-intent':
            _require(args.input is not None, '--input is required for Director dispatch intent')
            result = director.retain_dispatch_intent(payload)
        elif args.command == 'setup-status':
            result = director.setup_status(payload)
        elif args.command == 'status':
            if isinstance(payload, dict) and 'plan_context' in payload:
                selector = payload.pop('plan_context')
                result = director.status(payload)
                result['plan_context'] = _plan_helper(director).context(selector)
            else:
                result = director.status(payload)
        else:
            _require(args.input is not None, '--input is required for Director setup and rebind')
            rebind = args.command.startswith('rebind')
            method = director.preview if args.command.endswith('-preview') else director.apply
            result = method(payload, rebind=rebind)
    except (ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(WF.dump({'ok': False, 'error': str(error)}), end='')
        return 2
    print(WF.dump(result), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
