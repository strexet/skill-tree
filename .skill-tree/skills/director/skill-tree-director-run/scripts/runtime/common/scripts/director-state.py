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


RUN_COMMANDS = {'run-start', 'run-status', 'run-dispatch', 'run-pause', 'run-resume', 'run-cancel',
                'run-complete-assignment', 'decide-open', 'decide-answer'}
RUN_PATH = re.compile(r'\.skill-tree/director/runs/dr-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json\Z')
REGISTRY = '.skill-tree/director/registry.json'
BINDINGS = '.skill-tree/artifacts/director/local-bindings.json'
OBJECTIVE_PATH = re.compile(r'\.skill-tree/director/objectives/ob-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json\Z')
DISPATCH_INTENT_PATH = re.compile(r'\.skill-tree/director/dispatch-intents/[a-f0-9]{64}\.json\Z')
PLAN_COMMANDS = {'plan-preview', 'plan-freeze', 'plan-context', 'plan-impact', 'context-search'}
OBJECTIVE_COMMANDS = {'objective-preview', 'objective-apply', 'objective-read', 'plan-pin', 'outcome-link'}
AREA_FIELDS = {'id', 'role', 'scope', 'capabilities', 'interface', 'allowed_effects'}
READ_EFFECTS = {'status', 'preview', 'audit', 'review'}
WRITE_EFFECTS = {'intake', 'process', 'launch', 'adopt', 'install', 'commit', 'publish', 'schedule'}
TOKEN = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')


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


def _validate_scopes(areas, queues):
    records = list(areas.values())
    _require(sum(area['role'] == 'source-maintenance' for area in records) == 1,
             'Register one canonical Skill Tree source-maintenance area')
    observed = [(area, Path(queues[area['queue_id']]['root']) / _scope(area['scope']))
                for area in records if area['queue_id'] in queues]
    for index, (first, a) in enumerate(observed):
        for second, b in observed[index + 1:]:
            both_write = bool(WRITE_EFFECTS.intersection(first['allowed_effects'])
                              and WRITE_EFFECTS.intersection(second['allowed_effects']))
            _require(a != b and not (both_write and (a.is_relative_to(b) or b.is_relative_to(a))),
                     f'Areas have overlapping scopes: {first["id"]}, {second["id"]}')


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
        _validate_scopes(areas, queues)
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
        _validate_scopes(registry['areas'], queues)
        profile_proof = _inspect_profile(Path(owner['root']))
        public = {'schema': 1, 'operation': 'rebind', 'director_id': registry['director_id'], 'queue_id': queue_id,
                  'areas': sorted(sibling['id'] for sibling in area_siblings), 'changed': previous != owner,
                  'profile_proof': profile_proof}
        return public, registry, {**bindings, 'queues': queues}, expected

    def _plan(self, payload, rebind):
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
        _object(payload, set(), {'assignments'})
        requests = payload.get('assignments', [])
        _require(isinstance(requests, list), 'Assignments require an exact list')
        registry, bindings, _ = self._load()
        _require(registry is not None, 'Register Director areas before requesting status')
        owners = (bindings or {}).get('queues', {})
        queues = {queue_id: _status_queue(queue_id, binding) for queue_id, binding in owners.items()}
        areas = registry['areas']
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
            'available_independent': [entry['id'] for entry in projections
                                      if entry['state'] == 'ready' and not entry['prerequisites']],
        }

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
    return sorted({item[3:].decode('utf-8') for item in raw.split(b'\0') if item})


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
    parser.add_argument('command', choices=sorted({'setup-preview', 'setup-apply', 'rebind-preview', 'rebind', 'status', 'dispatch-intent'} | OBJECTIVE_COMMANDS | PLAN_COMMANDS | RUN_COMMANDS))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', type=Path)
    args = parser.parse_args(argv)
    try:
        director = DirectorRegistry(args.root)
        payload = json.loads(args.input.read_text()) if args.input else None
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
