#!/usr/bin/env python3
"""Suggest parallel Ready tasks using recorded project scope and validation."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys
import unicodedata


def load_workflow():
    spec = importlib.util.spec_from_file_location(
        'parallel_preview_workflow', Path(__file__).with_name('workflow-state.py')
    )
    module = importlib.util.module_from_spec(spec)
    # Execute the bundled source without reading or creating a bytecode cache.
    exec(compile(Path(spec.origin).read_bytes(), spec.origin, 'exec'), module.__dict__)
    return module


workflow = load_workflow()
workspaces = workflow.workspaces
READY_QUEUE = 'Prioritized Next Changes'
RESOURCE_MAP = '.skill-tree/config/resource-map.json'
FLAVORS = '.skill-tree/config/flavors.json'
BINDINGS = 'references/plugin-bindings.json'
COMPOSITION_INPUTS = (
    '.skill-tree/bin/compose.js', '.skill-tree/lib/composer.js',
    '.skill-tree/lib/installation.js', '.skill-tree/templates', '.skill-tree/config',
)


def normalized(path):
    return unicodedata.normalize('NFC', path).casefold()


def overlap(left, right):
    return workspaces.local_overlap(normalized(left), normalized(right))


def checked_path(root, path):
    if (not isinstance(path, str) or path != path.strip()
            or re.search(r'[\\:*?\[\]{}<>`|#\x00-\x1f]', path)
            or any(part in {'', '.', '..', '.git'} for part in path.split('/'))):
        raise ValueError('Scope requires concrete repository-relative paths')
    local = root / path
    if local.resolve() != local:
        raise ValueError('Scope contains a symbolic link or filesystem alias: ' + path)
    return path


def touch_paths(root, task):
    lines = workflow.section_body(task['body'], 'Touch').strip().splitlines()
    paths = []
    for line in lines:
        if not line.strip():
            continue
        match = re.fullmatch(r'- (?:`([^`]+)`|([^\s`]+))', line.strip())
        if not match:
            raise ValueError('Touch contains an unstructured path')
        paths.append(checked_path(root, match[1] or match[2]))
    if not paths:
        raise ValueError('Touch has no concrete paths')
    return sorted(set(paths))


def generated_outputs(root):
    mapping = root / RESOURCE_MAP
    if not mapping.is_file():
        return {}
    packages = root / '.skill-tree/skills'
    outputs = {}
    resources = json.loads(mapping.read_text())
    flavors_file = root / FLAVORS
    flavors = json.loads(flavors_file.read_text()).get('flavors', {}) if flavors_file.is_file() else {}
    for target in packages.glob('*/*'):
        if not target.is_dir():
            continue
        groups = resources.get(target.name, {})
        for group, entries in groups.items():
            for destination, source in entries.items():
                relative = (target / group / destination).relative_to(root).as_posix()
                outputs.setdefault('.skill-tree/' + source, set()).add(relative)
        flavor = flavors.get(target.parent.name, {})
        resource_sets = [flavor.get('resources', {})]
        resource_sets.extend(option['resources'] for option in flavor.get('conditional_resources', []))
        for entries in resource_sets:
            for destination, source in entries.items():
                if (target / destination).is_file():
                    relative = (target / destination).relative_to(root).as_posix()
                    outputs.setdefault('.skill-tree/' + source, set()).add(relative)
    return outputs


def validation_scope(store, task, resources):
    checks, reads, exclusive = [], set(), set()
    for check in workflow.check_specs(task):
        recipe, _ = workflow.recipe_for(store, check)
        paths = check['sources'] + recipe.get('input_paths', [])
        reads.update(checked_path(store.source_root, path) for path in paths)
        lane = recipe['lane']
        check_resources = []
        if lane in workflow.PRODUCT_LANES or recipe.get('execution_binding'):
            if not resources:
                raise ValueError('Check requires an explicit exclusive-resource policy: ' + check['id'])
            check_resources = sorted(set(resources))
            exclusive.update(resources)
        checks.append({
            'task_id': task['id'], 'id': check['id'], 'recipe_id': check['recipe_id'],
            'lane': lane, 'inputs': sorted(set(paths)), 'timing': check['timing'],
            'assertion': check['assertion'], 'exclusive_resources': check_resources,
        })
    return checks, sorted(reads), sorted(exclusive)


def named_resources(root):
    path = root / '.skill-tree/worktree-profile.json'
    if not path.is_file():
        return []
    installed = root / '.skill-tree/installation/profile.json'
    if installed.is_file():
        inputs = json.loads(installed.read_text()).get('inputs', {})
        if inputs.get('.skill-tree/worktree-profile.json') != workflow.file_hash(path):
            return []
    profile = json.loads(path.read_text())
    resources = profile.get('exclusive_resources', [])
    if (profile.get('schema') != 1 or not isinstance(resources, list)
            or any(not isinstance(name, str) or not name.strip() for name in resources)):
        raise ValueError('Invalid worktree exclusive-resource policy')
    return resources


def describe(store, task, outputs, resources, declared_resources=()):
    result = {
        'id': task['id'], 'title': task['title'], 'priority': task['priority'],
        'status': task['status'], 'dependencies': task['depends_on'],
        'touch': [], 'generated_consumers': {}, 'check_inputs': [], 'prerequisite_inputs': [],
        'exclusive_resources': [], 'checks': [], 'binding_manifests': [], 'reasons': [],
    }
    try:
        touch = touch_paths(store.source_root, task)
        result['touch'] = touch
        result['generated_consumers'] = {
            source: sorted(consumers) for source, consumers in sorted(outputs.items())
            if any(overlap(source, path) for path in touch)
        }
        packages = set()
        for path in writes(result):
            parts = Path(path).parts
            if len(parts) >= 4 and parts[:2] == ('.skill-tree', 'skills'):
                manifest = Path(*parts[:4]) / BINDINGS
                if (store.source_root / manifest).is_file():
                    packages.add(manifest.as_posix())
        result['binding_manifests'] = sorted(packages)
    except ValueError as error:
        result['reasons'].append({'kind': 'unknown-touch', 'detail': str(error)})
    try:
        result['checks'], result['check_inputs'], result['exclusive_resources'] = validation_scope(
            store, task, resources
        )
        result['exclusive_resources'] = sorted(set(result['exclusive_resources']).union(declared_resources))
    except (ValueError, OSError) as error:
        result['reasons'].append({'kind': 'unverified-checks', 'detail': str(error)})
    return result


def writes(candidate):
    return candidate['touch'] + sorted({
        path for group in candidate['generated_consumers'].values() for path in group
    })


def conflicts(left, right):
    left_writes, right_writes = writes(left), writes(right)
    left_reads = sorted(set(left['check_inputs'] + left['prerequisite_inputs']))
    right_reads = sorted(set(right['check_inputs'] + right['prerequisite_inputs']))
    groups = [
        ('write-overlap', left_writes, right_writes),
        ('write-input-overlap', left_writes, right_reads),
        ('input-write-overlap', left_reads, right_writes),
    ]
    reasons = []
    for kind, first, second in groups:
        for a in first:
            for b in second:
                if overlap(a, b):
                    reasons.append({'kind': kind, 'task_id': right['id'], 'paths': [a, b]})
    for resource in sorted(set(left['exclusive_resources']) & set(right['exclusive_resources'])):
        reasons.append({'kind': 'exclusive-resource', 'task_id': right['id'], 'resource': resource})
    return reasons


def dependency_holds(store, candidate, completed, progress, claims):
    reasons = []
    inputs = set()
    for dependency in candidate['dependencies']:
        expected = completed.get(dependency, {}).get('source_fingerprints')
        if dependency not in completed:
            kind = 'dependency-incomplete'
        elif dependency in claims or progress.get(dependency, {}).get('revalidation'):
            kind = 'dependency-revalidating'
        else:
            current = {}
            if expected and None not in expected.values():
                try:
                    current = workflow.fingerprints(store, expected)
                except (OSError, ValueError):
                    pass
            if current and current == expected:
                inputs.update(current)
                continue
            kind = 'dependency-source-unverified'
        reasons.append({'kind': kind, 'task_id': dependency})
    candidate['prerequisite_inputs'] = sorted(inputs)
    return reasons


def snapshot(store):
    if any((store.base / name).exists() for name in ('.writer-lock', '.transaction.json')):
        raise ValueError('Queue writer or recovery in progress. Retry the preview after reconciliation.')
    root = store.source_root
    source_inputs = (
        RESOURCE_MAP, FLAVORS, '.skill-tree/installation/profile.json', '.skill-tree/config/repository.json',
        '.skill-tree/worktree-profile.json',
    )
    head = workspaces.git(root, 'rev-parse', 'HEAD') if workspaces.common_dir(root) else None
    return {
        'source_root': str(root), 'source_head': head, 'queue_root': str(store.root),
        'queue_sha256': workflow.file_hash(store.future), 'state_sha256': workflow.file_hash(store.state),
        'outcomes_sha256': workflow.file_hash(store.owned(workflow.OUTCOME_LEDGER)),
        'navigation_sha256': workflow.file_hash(store.owned(workflow.NAVIGATION)),
        'source_inputs': {name: workflow.file_hash(root / name) for name in source_inputs},
    }


def preview(store, workers, selectors=(), *, declared_resources=None):
    declared_resources = declared_resources or {}
    before = snapshot(store)
    store.verify_future_integrity()
    text = store.text()
    if workflow.digest(text.encode()) != before['queue_sha256']:
        raise ValueError('Queue changed while reading the preview. Retry.')
    state = store.load(text)
    tasks = workflow.parse(text)
    by_id = {task['id']: task for task in tasks}
    prioritized = [task for task in tasks if task['queue'] == READY_QUEUE]
    exact = set(selectors)
    if missing := exact - {task['id'] for task in prioritized}:
        raise ValueError('Exact task IDs must belong to the prioritized queue: ' + ', '.join(sorted(missing)))
    candidates = sorted((task for task in prioritized if not exact or task['id'] in exact),
                        key=lambda task: -task['priority'])
    outputs = generated_outputs(store.source_root)
    resources = named_resources(store.source_root)
    completed = {record['task_id']: record for record in store.outcomes()
                 if record['disposition'] == 'completed'}
    registry = state.get('run_registry', {})
    claims = dict(registry.get('claims', {}))
    progress = state['task_progress']
    for task_id, entry in progress.items():
        claims.setdefault(task_id, entry.get('run_id'))
    legacy = state['active_run']
    if legacy and not registry:
        for field in ('admitted_task_ids', 'required_ids', 'snapshot_ids'):
            for task_id in legacy.get(field, []):
                if task_id not in completed:
                    claims.setdefault(task_id, legacy['id'])
    pending_holds = {}
    for task in tasks:
        if task['queue'] == 'Pending Queue' and task['relation'] in {'blocker', 'subtask'}:
            for parent in {task['root_task_id'], task['related_task_id']}:
                pending_holds.setdefault(parent, []).append(task['id'])
    active = {}
    for task_id in sorted(claims):
        scope = describe(store, by_id[task_id], outputs, resources, declared_resources.get(task_id, ())) if task_id in by_id else None
        if scope:
            dependency_holds(store, scope, completed, progress, claims)
        active[task_id] = scope
    has_clarifications = any((store.base / 'clarifications').glob('*.json'))
    selected, deferred = [], []
    for task in candidates:
        item = describe(store, task, outputs, resources, declared_resources.get(task['id'], ()))
        reasons = item['reasons']
        task_id = item['id']
        if item['status'] != 'Ready':
            reasons.append({'kind': 'readiness', 'status': item['status']})
        elif has_clarifications:
            try:
                workflow.clarification_admission(store, task_id, hook_gate=False)
            except (OSError, ValueError) as error:
                reasons.append({'kind': 'clarification-hold', 'detail': str(error)})
        if task_id in claims:
            reasons.append({'kind': 'active-task-claim', 'run_id': claims[task_id]})
        if pending_holds.get(task_id):
            reasons.append({'kind': 'required-pending-work', 'pending_ids': pending_holds[task_id]})
        reasons.extend(dependency_holds(store, item, completed, progress, claims))
        for name in item['exclusive_resources']:
            claim = registry.get('resources', {}).get(name)
            if claim:
                reasons.append({'kind': 'active-resource-claim', 'resource': name, 'run_id': claim['run_id']})
        for active_id, scope in active.items():
            if active_id == task_id:
                continue
            if scope is None or scope['reasons']:
                reasons.append({'kind': 'active-scope-unverified', 'task_id': active_id})
            else:
                reasons.extend(conflicts(item, scope))
        for other in selected:
            reasons.extend(conflicts(item, other))
        if not reasons and len(selected) == workers:
            reasons.append({'kind': 'worker-limit', 'workers': workers})
        (deferred if reasons else selected).append(item)
    for item in deferred:
        for other in selected:
            item['reasons'].extend(reason for reason in conflicts(item, other) if reason not in item['reasons'])
    combined = [check for item in selected for check in item['checks']]
    manifests = {}
    for item in selected:
        for name in item['binding_manifests']:
            manifests.setdefault(name, []).append(item['id'])
    regeneration = [item['id'] for item in selected if item['generated_consumers'] or any(
        overlap(path, common) for path in item['touch'] for common in COMPOSITION_INPUTS
    )] if (store.source_root / RESOURCE_MAP).is_file() else []
    if snapshot(store) != before:
        raise ValueError('Queue or source planning inputs changed during preview. Retry.')
    return {
        'snapshot': before, 'workers': workers, 'selected_ids': [item['id'] for item in selected],
        'selected': selected, 'deferred': deferred,
        'after_merge': {
            'checks': combined, 'regenerate_packages_for': regeneration,
            'shared_generated_outputs': {name: ids for name, ids in sorted(manifests.items()) if len(ids) > 1},
        },
        'limitations': [
            'Scope uses declared paths, recorded check inputs and available package mappings.',
            'Undeclared consumers, generators and shared runtime effects require workload review.',
            'The recommendation reflects one priority-ordered snapshot and grants no execution authority.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--id', action='append', default=[], help='Exact prioritized T-ID. Repeat for a targeted preview.')
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error('--workers must be positive')
    try:
        store = workflow.Store(args.root, allow_unselected=True, neutral=True)
        result = preview(store, args.workers, args.id)
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
