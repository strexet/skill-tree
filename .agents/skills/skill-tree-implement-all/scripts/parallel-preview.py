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
REVIEW_INPUTS = (RESOURCE_MAP, FLAVORS, '.skill-tree/installation/profile.json',
                 '.skill-tree/config/repository.json', '.skill-tree/validation-recipes.json',
                 '.skill-tree/worktree-profile.json')


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


def validation_scope(store, task, resources, checked_recipes=None):
    checks, reads, exclusive = [], set(), set()
    for check in workflow.check_specs(task):
        recipe = (workflow.recipe_for(store, check)[0] if checked_recipes is None
                  else checked_recipes[check['id']])
        paths = check['sources'] + recipe.get('input_paths', [])
        reads.update(checked_path(store.source_root, path) for path in paths)
        lane = recipe['lane']
        check_resources = []
        if checked_recipes is None and (lane in workflow.PRODUCT_LANES or recipe.get('execution_binding')):
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


def describe(store, task, outputs, resources, declared_resources=(), *, checked_recipes=None):
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
            store, task, resources, checked_recipes
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


def controller_review_tasks(state, completed, claims):
    registry = state.get('run_registry') or {}
    runs = registry.get('runs', {})
    if not registry and state.get('active_run'):
        legacy = state['active_run']
        runs = {legacy['id']: legacy}
    selected = {}
    for run_id, run in runs.items():
        finished = (workspaces.delivery_finished(run) if run.get('delivery')
                    else run.get('phase') == 'completed')
        recorded = set(run.get('completed_ids', []))
        recorded.update(task_id for task_id, reference in run.get('completion_refs', {}).items()
                        if completed.get(task_id, {}).get('id') == reference)
        task_ids = sorted(task_id for task_id in recorded if not finished or claims.get(task_id) == run_id)
        if task_ids:
            selected[run_id] = (run, task_ids, finished)
    return selected


def controller_review_inputs(store, state, selected):
    if not selected:
        return {}, {}
    registry = state.get('run_registry') or {}
    applied = set(registry.get('applied_events', []))
    locator = workspaces.runtime_file(store.root)
    observed = {'locator': workflow.file_hash(locator) if locator else None, 'runs': {}}
    checkouts = {}
    for run_id, (run, _, _) in selected.items():
        inputs = observed['runs'][run_id] = {}
        try:
            if not workflow.valid_id(run_id, 'WR'):
                raise ValueError('Invalid completed controller identity')
            events = workflow.binding_path(store.root, '.skill-tree/history/run-events/' + run_id.lower())
            inputs['events'] = {
                path.name: 'symlink' if path.is_symlink() else workflow.file_hash(path)
                for path in sorted(events.glob('e-*.json')) if 'E-' + path.stem[2:] in applied
            }
            view = workflow.Store(store.root, allow_unselected=True, neutral=True)
            workspaces.ensure_workspace(view, run)
            checkout = workspaces.checked_out_branch(view.source_root)
            inputs['checkout'] = checkout
            inputs['path'] = str(view.source_root)
            inputs['source'] = {path: workflow.file_hash(view.source_root / path) for path in REVIEW_INPUTS}
            inputs['outputs'] = generated_outputs(view.source_root)
            checkouts[run_id] = (view, checkout)
        except (OSError, ValueError) as error:
            inputs['error'] = str(error)
    return observed, checkouts


def completed_check_recipe(view, run, task, check, result):
    recipe, environment = workflow.recipe_for(view, check)
    sources = workflow.fingerprints(view, check['sources'])
    if any(value is None for value in sources.values()):
        raise ValueError('Completed validation source inputs are unavailable: ' + check['id'])
    if recipe['lane'] in workflow.PRODUCT_LANES:
        # Reconstruct the accepted check identity from its recorded session and artifacts.
        session = result.get('execution_sessions', {}).get(environment)
        if not session:
            raise ValueError('The current recipe and inputs do not match completed validation session: ' + check['id'])
        fields = ('tool_identity', 'fixture_identity', 'build_identity', 'save_service_isolation', 'editor_version')
        identity = {field: session[field] for field in fields if field in session}
        identity['evidence'] = [workflow.evidence_pointer(view, ref, required=True)
                                for ref in session['identity_evidence']]
        environment = workflow.digest(workflow.dump({'recipe_environment': environment, 'execution': identity}).encode())
    executable = {name: check[name] for name in ('recipe_id', 'sources', 'parameters', 'assertion')}
    key = workflow.digest(workflow.dump({'check': executable, 'recipe': recipe, 'sources': sources,
        'environment': environment, 'group': workflow.group_fingerprint(view, task, {'active_run': run})}).encode())
    if (key, workflow.task_signature(task)) != (result['key'], result['definition']):
        raise ValueError('The current recipe and inputs do not match completed validation: ' + check['id'])
    return recipe


def completed_review_scope(store, run, outcome, view, checkout, outputs):
    receipt = outcome.get('task_git_commit')
    if not isinstance(receipt, dict):
        raise ValueError('The completed outcome has no scoped Git receipt')
    if (receipt.get('ref') != checkout['ref'] or receipt.get('checkout') != checkout['checkout']
            or any(not isinstance(receipt.get(key), str)
                   or not re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', receipt[key])
                   for key in ('commit', 'parent', 'tree'))):
        raise ValueError('The scoped Git receipt differs from the registered review checkout')
    root = view.source_root
    commit, parent = receipt['commit'], receipt['parent']
    commit_identity = workspaces.local_git_text(root, 'show', '-s', '--format=%T%n%P', commit).split()
    if (commit_identity != [receipt['tree'], parent]
            or workspaces.local_git(root, 'merge-base', '--is-ancestor', commit, checkout['head'],
                                    accepted=(0, 1, 128)).returncode):
        raise ValueError('The registered review checkout does not contain the exact scoped Git commit')
    actual = workspaces.local_git_paths(root, 'diff', '--name-only', '--no-renames', '-z', parent, commit, '--')
    recorded = workspaces.worker_paths(receipt['paths'])
    if not actual or not actual.issubset(recorded):
        raise ValueError('Changed Git paths differ from the verified completion scope')
    body = workflow.completed_task_body(store, outcome)
    if body is None:
        raise ValueError('The applied completion event does not verify the removed task definition')
    task = {'id': outcome['task_id'], 'title': outcome['title'], 'priority': 0, 'status': 'Ready',
            'body': body, 'depends_on': outcome['depends_on'], 'validation_group_id': outcome.get('validation_group_id'),
            'boundary_validation': outcome.get('boundary_validation', 'not-required')}
    checks = workflow.check_specs(task)
    if (workflow.task_signature(task) != outcome.get('validation_signature')
            or checks != outcome.get('validation_plan')):
        raise ValueError('The removed task validation contract differs from the completed outcome')
    results = outcome.get('check_results', [])
    registered = {item['check']['id']: item for item in results}
    if len(results) != len(checks) or registered.keys() != {check['id'] for check in checks}:
        raise ValueError('The completed outcome lacks exact validation results for the review scope')
    checked_recipes = {}
    for check in checks:
        item = registered[check['id']]
        result = item['result']
        if item['check'] != check or result['result'] != 'pass':
            raise ValueError('The completed outcome lacks a matching passing validation result')
        checked_recipes[check['id']] = completed_check_recipe(view, run, task, check, result)
    scope = describe(view, task, outputs, (), checked_recipes=checked_recipes)
    if scope['reasons']:
        raise ValueError(scope['reasons'][0]['detail'])
    scope['touch'] = sorted(set(scope['touch']) | {checked_path(root, path) for path in actual})
    scope['check_inputs'] = sorted(set(scope['check_inputs']) | {
        checked_path(root, path) for path in outcome['source_fingerprints']
    })
    scope['generated_consumers'] = {
        source: sorted(consumers) for source, consumers in sorted(outputs.items())
        if any(overlap(source, path) for path in scope['touch'])
    }
    return scope, task


def snapshot(store):
    if any((store.base / name).exists() for name in ('.writer-lock', '.transaction.json')):
        raise ValueError('Queue writer or recovery in progress. Retry the preview after reconciliation.')
    root = store.source_root
    head = workspaces.git(root, 'rev-parse', 'HEAD') if workspaces.common_dir(root) else None
    return {
        'source_root': str(root), 'source_head': head, 'queue_root': str(store.root),
        'queue_sha256': workflow.file_hash(store.future), 'state_sha256': workflow.file_hash(store.state),
        'outcomes_sha256': workflow.file_hash(store.owned(workflow.OUTCOME_LEDGER)),
        'navigation_sha256': workflow.file_hash(store.owned(workflow.NAVIGATION)),
        'source_inputs': {name: workflow.file_hash(root / name) for name in REVIEW_INPUTS},
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
    reviewing = controller_review_tasks(state, completed, claims)
    review_inputs, review_checkouts = controller_review_inputs(store, state, reviewing)
    review_scopes = []
    review_checks = []
    for run_id, (run, task_ids, finished) in reviewing.items():
        for task_id in task_ids:
            outcome = completed.get(task_id, {})
            try:
                if (task_id not in run.get('completed_ids', []) or task_id in by_id
                        or outcome.get('run_id') != run_id or not outcome.get('id')
                        or run.get('completion_refs', {}).get(task_id) != outcome['id']):
                    raise ValueError('The owning run does not reference the exact completed task outcome')
                if run_id not in review_checkouts:
                    raise ValueError(review_inputs['runs'][run_id]['error'])
                view, found_checkout = review_checkouts[run_id]
                relevant = review_inputs['runs'][run_id]
                peer_outputs = relevant['outputs']
                combined_outputs = {path: outputs.get(path, set()) | peer_outputs.get(path, set())
                                    for path in outputs.keys() | peer_outputs.keys()}
                scope, task = completed_review_scope(store, run, outcome, view, found_checkout, combined_outputs)
                review_checks.append((view, run, task, outcome['check_results']))
                if claims.get(task_id) == run_id and task_id not in progress:
                    del claims[task_id]
                if not finished:
                    review_scopes.append((run_id, task_id, scope, None))
            except (KeyError, OSError, ValueError) as error:
                if not finished:
                    review_scopes.append((run_id, task_id, None, str(error)))
    for _, _, scope, _ in review_scopes:
        if scope is not None:
            dependency_holds(store, scope, completed, progress, claims)
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
        for review_run, review_task, scope, error in review_scopes:
            if scope is None:
                reasons.append({'kind': 'review-scope-unverified', 'task_id': review_task,
                                'run_id': review_run, 'detail': error})
            elif review_task != task_id:
                reasons.extend({**reason, 'run_id': review_run} for reason in conflicts(item, scope))
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
    try:
        for view, run, task, results in review_checks:
            for item in results:
                completed_check_recipe(view, run, task, item['check'], item['result'])
    except (KeyError, OSError, ValueError) as error:
        raise ValueError('Controller review validation inputs changed during preview. Retry.') from error
    if controller_review_inputs(store, state, reviewing)[0] != review_inputs:
        raise ValueError('Controller review proof changed during preview. Retry.')
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
