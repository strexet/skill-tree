"""Preview and apply additive task grouping through the canonical workflow writer."""

import json
import os
from pathlib import Path
import re
import subprocess


PREVIEW = 'task-grouping-preview'
APPLY = 'task-grouping-apply'
QUEUE = '.skill-tree/documents/future.md'
STATE = '.skill-tree/documents/future.json'
MANIFEST = '.skill-tree/skill-tree.json'
PROFILE = '.skill-tree/installation/profile.json'
INSTALLATION = '.skill-tree/installation/'
HEADER = re.compile(r'^###[^\n]+\n\s*```yaml\n(.*?)\n```', re.S)
DIGEST = re.compile('[a-f0-9]{64}')


def checksum(value):
    return wf.digest(wf.dump(value).encode())


def is_digest(value):
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def selection(command, payload):
    required = {'expected_source_hash', 'assignments'}
    if command == APPLY:
        required.add('expected_preview_sha256')
    if command not in {PREVIEW, APPLY} or not isinstance(payload, dict) or set(payload) != required:
        raise wf.WorkflowError('Grouping migration requires exact assignments and current preview guards')
    if not all(is_digest(payload[key]) for key in required - {'assignments'}):
        raise wf.WorkflowError('Grouping migration requires exact queue and preview digests')
    assignments = payload['assignments']
    if not isinstance(assignments, dict) or not assignments:
        raise wf.WorkflowError('Grouping migration requires a nonempty assignment map')
    for task_id, values in assignments.items():
        if not any(wf.valid_id(task_id, kind) for kind in ('P', 'T', 'B')):
            raise wf.WorkflowError('Grouping migration requires exact P, T or B task IDs')
        if not isinstance(values, dict) or not values or set(values) - set(wf.GROUPING_FIELDS):
            raise wf.WorkflowError('Grouping migration permits only topic and intake batch IDs')
        wf.validate_grouping(values, 'Pending Queue' if task_id.startswith('P-') else 'Backlog')
    return assignments


def current_queue(store):
    raw = store.owned(QUEUE).read_bytes()
    text = raw.decode('utf-8')
    # The fixed-header parser and transaction writer use LF. Reject files the
    # generic text reader would silently normalize.
    if '\r' in text:
        raise wf.WorkflowError('Grouping migration requires a canonical LF queue')
    return text, wf.digest(raw)


def raw_state(store, text):
    validated = store.load(text)
    state = json.loads(store.owned(STATE).read_text()) if store.state.is_file() else validated
    if state['schema'] == 3:
        locator = wf.workspaces.runtime(store.root)
        if not locator or locator['queue_id'] != state['run_registry']['queue_id']:
            raise wf.WorkflowError('Run registry locator mismatch; explicit recover-locator required')
        if state['active_run'] is not None:
            raise wf.WorkflowError('Ambiguous workflow run authority; explicit recovery required')
    return state


def workspace_path(store, locator, run):
    location = locator['worktrees'].get(run['id'])
    if not location:
        raise wf.WorkflowError('Unfinished run workspace locator unavailable: ' + run['id'])
    worktree = Path(location).resolve()
    if (not worktree.is_dir() or wf.workspaces.common_dir(worktree) != wf.workspaces.common_dir(store.root)
            or wf.workspaces.git(worktree, 'rev-parse', '--show-toplevel') != str(worktree)
            or wf.workspaces.git(worktree, 'symbolic-ref', '--quiet', '--short', 'HEAD') != run.get('workspace', {}).get('branch')):
        raise wf.WorkflowError('Unfinished run workspace identity changed: ' + run['id'])
    wf.workspaces.unfinished(worktree)
    return worktree


def advertises_grouping(worktree):
    path = worktree / PROFILE
    if any(part.is_symlink() for part in (path, path.parent, path.parent.parent)):
        raise wf.WorkflowError('Owned installation profile cannot use symlinks')
    return path.is_file() and 'task_grouping' in json.loads(path.read_text())


def stopped_record(run):
    return {key: run[key] for key in ('id', 'phase', 'stop_reason', 'next_action')} | {
        'profile_refresh_required': run.get('profile_refresh_required', False),
        'branch': run.get('workspace', {}).get('branch'),
        'checkpoint_sha256': checksum(run),
    }


def workflow_handoff(store, state, assignments, profiles, stopped, excluded):
    locator = wf.workspaces.runtime(store.root) if state.get('run_registry') else None
    runs = state['run_registry']['runs'].values() if locator else [state.get('active_run')]
    profiles['canonical'] = store.root
    if wf.workspaces.common_dir(store.root):
        wf.workspaces.unfinished(store.root)
    if store.source_root != store.root:
        profiles['invoking-worktree'] = store.source_root
        owners = [run for run in runs if run and locator and locator['worktrees'].get(run['id'])
                  and Path(locator['worktrees'][run['id']]).resolve() == store.source_root]
        if len(owners) != 1 or workspace_path(store, locator, owners[0]) != store.source_root:
            raise wf.WorkflowError('Invoking worktree is not registered with the canonical queue')
    for run in runs:
        if not run or wf.workspaces.delivery_finished(run) or (not locator and run.get('phase') == 'completed'):
            continue
        if not run.get('stop_reason') or run.get('maintenance'):
            raise wf.WorkflowError('Grouping migration requires a stopped cleanup/handoff: ' + run['id'])
        evidence = stopped_record(run)
        stopped.append(evidence)
        if not locator:
            continue  # The standalone checkpoint executes at the verified canonical root.
        worktree = workspace_path(store, locator, run)
        scope = set(run['admitted_task_ids']) | set(run['required_ids']) | set(run['pending_ids'])
        if worktree in profiles.values() or scope.intersection(assignments) or advertises_grouping(worktree):
            profiles[run['id']] = worktree
        else:
            if run.get('profile_refresh_required') is not True:
                raise wf.WorkflowError('Excluded stopped worktree requires a pending profile re-admission: ' + run['id'])
            excluded.append(evidence)


def verified_profiles(store, profiles):
    source = Path(__file__).resolve().parents[2]
    library = source / 'lib/installation.js'
    if not library.is_file():
        library = store.source_root / INSTALLATION / 'source/lib/installation.js'
        profile = json.loads((store.source_root / PROFILE).read_text())
        lib_prefix = INSTALLATION + 'source/lib/'
        expected = {name: digest for name, digest in profile.get('bundle_digests', {}).items() if name.startswith(lib_prefix)}
        actual = {path.relative_to(store.source_root).as_posix(): wf.file_hash(path)
                  for path in library.parent.glob('*.js') if path.is_file() and not path.is_symlink()}
        if profile.get('project_root') != str(store.source_root) or not expected or actual != expected:
            raise wf.WorkflowError('Owned installation verifier does not match the invoking profile')
    if not library.is_file() or library.is_symlink() or library.parent.is_symlink():
        raise wf.WorkflowError('Reviewed owned installation verifier unavailable')
    for root in dict.fromkeys(profiles.values()):
        wf._delivery_install_barrier(root)
    script = r'''
const core = require(process.argv[1]);
const roots = process.argv.slice(2);
try {
  if (core.hasActiveOperation(roots[0])) throw Error('Grouping migration requires a stopped cleanup/handoff');
  console.log(JSON.stringify({proofs: roots.map(root => core.verifyTaskGroupingProfile(root))}));
} catch (error) { console.log(JSON.stringify({error: error.message})); process.exitCode = 2; }
'''
    roots = list(dict.fromkeys(profiles.values()))
    environment = {key: value for key, value in os.environ.items() if key not in {'NODE_OPTIONS', 'NODE_PATH'}}
    try:
        result = subprocess.run(['node', '-e', script, str(library), *map(str, roots)],
                                capture_output=True, text=True, timeout=60, env=environment)
        data = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise wf.WorkflowError('Owned grouping profile verification unavailable') from exc
    if result.returncode:
        raise wf.WorkflowError(data.get('error', 'Owned grouping profile verification failed'))
    proofs = {}
    for root, proof in zip(roots, data['proofs'], strict=True):
        if (proof['project_root'] != str(root) or proof.get('schema') != 1
                or not all(is_digest(proof.get(key)) for key in ('profile_identity', 'profile_sha256', 'source_helper_sha256'))
                or not proof.get('package_helpers') or wf.file_hash(root / PROFILE) != proof['profile_sha256']):
            raise wf.WorkflowError('Owned grouping profile proof changed during verification')
        proofs[root] = {key: value for key, value in proof.items() if key != 'project_root'}
    return {role: proofs[root] for role, root in profiles.items()}


def batch_evidence(store, task, assignments, observed):
    batch_ids = assignments.get('intake_batch_ids', [])
    if not batch_ids or task.get('intake_batch_ids') == batch_ids:
        return
    origins = {task['id']} if task['queue'] == 'Pending Queue' else set(task['parent_pending_ids'])
    for batch_id in batch_ids:
        relative = wf.intake_receipt_path(batch_id)
        path = store.owned(relative)
        before = wf.file_hash(path)
        receipt = wf.read_intake_receipt(store, batch_id)
        if not receipt:
            raise wf.WorkflowError('Historical intake batch receipt unavailable: ' + batch_id)
        matches = sorted(origins.intersection(item['id'] for item in receipt['items']))
        if not matches or not before or before != wf.file_hash(path):
            raise wf.WorkflowError('Historical intake batch evidence does not match task provenance: ' + batch_id)
        evidence = observed.setdefault(batch_id, {'path': relative, 'sha256': before, 'created_at': receipt['created_at'],
                                                  'matched_pending_ids': {}})
        if evidence['sha256'] != before:
            raise wf.WorkflowError('Historical intake batch receipt changed during inspection: ' + batch_id)
        evidence['matched_pending_ids'][task['id']] = matches


def preview(store, text, source_hash, state, assignments):
    tasks = wf.parse(text)
    current = {task['id']: task for task in tasks}
    missing = sorted(set(assignments) - set(current))
    rows, conflicts, observed = [], [], {}
    for task in tasks:
        task_id = task['id']
        if task_id not in assignments:
            continue
        requested = assignments[task_id]
        existing = wf.grouping_fields(task)
        additions = {key: value for key, value in requested.items() if key not in existing}
        row = {'task_id': task_id, 'queue': task['queue'], 'existing': existing,
               'requested': requested, 'additions': additions}
        rows.append(row)
        conflicts.extend({'task_id': task_id, 'field': key, 'reason': 'Existing value differs'}
                         for key in requested.keys() & existing.keys() if requested[key] != existing[key])
        try:
            batch_evidence(store, task, additions, observed)
        except (wf.WorkflowError, ValueError, OSError) as exc:
            conflicts.append({'task_id': task_id, 'field': 'intake_batch_ids', 'reason': str(exc)})
    profiles, stopped, excluded, proof = {}, [], [], {}
    blocked_reason = None
    try:
        workflow_handoff(store, state, assignments, profiles, stopped, excluded)
        proof = verified_profiles(store, profiles)
    except (wf.WorkflowError, wf.workspaces.RunError, ValueError, OSError) as exc:
        blocked_reason = str(exc)
    report = {'schema': 1, 'source_hash': source_hash, 'assignments_sha256': checksum(assignments),
              'selected_ids': [row['task_id'] for row in rows],
              'queue_id': state.get('run_registry', {}).get('queue_id'),
              'changes': rows, 'missing_ids': missing, 'conflicts': sorted(conflicts, key=lambda item: (item['task_id'], item['field'])),
              'batch_evidence': observed, 'verified_profiles': proof, 'stopped_runs': stopped,
              'excluded_stopped_runs': excluded,
              'blocked_reason': blocked_reason, 'applicable': not (missing or conflicts or blocked_reason)}
    return report | {'preview_sha256': checksum(report)}, profiles


def add_grouping(text, report):
    additions = {row['task_id']: row['additions'] for row in report['changes'] if row['additions']}
    lines = text.splitlines(keepends=True)
    for task in reversed(wf.parse(text)):
        values = additions.get(task['id'])
        if values is None:
            continue
        body = task['body']
        end = HEADER.match(body).end(1)
        fields = ''.join('\n' + key + ': ' + json.dumps(values[key], ensure_ascii=False)
                         for key in wf.GROUPING_FIELDS if key in values)
        lines[task['start']:task['end']] = [body[:end] + fields + body[end:]]
    return ''.join(lines), list(additions)


def navigation(store, result_hash):
    path = store.owned(MANIFEST)
    value = json.loads(path.read_text()) if path.is_file() else wf.manifest(store)
    if not any(entry['path'] == STATE for entry in value['files']):
        value['files'].append({'path': STATE, 'role': 'generated-index-and-active-state', 'owner': 'skill-tree'})
    value['state'] = STATE
    value['source_digests'][QUEUE] = result_hash
    return value


def receipt_path(preview_sha):
    return '.skill-tree/history/task-grouping-migrations/' + preview_sha + '.json'


def verify_current_index(store, text, state):
    current = wf.digest(text.encode())
    if state.get('source_hash') != current or state.get('tasks') != wf.index(text):
        raise wf.WorkflowError('Canonical queue index does not match current task definitions')
    manifest = store.owned(MANIFEST)
    if manifest.is_file() and json.loads(manifest.read_text()).get('source_digests', {}).get(QUEUE) != current:
        raise wf.WorkflowError('Canonical queue navigation does not match the current queue')


def replay(store, relative, payload, report):
    path = store.owned(relative)
    if not path.is_file():
        return None
    record = json.loads(path.read_text())
    digest = record.pop('receipt_sha256', None)
    if checksum(record) != digest:
        raise wf.WorkflowError('Grouping migration receipt identity changed')
    record['receipt_sha256'] = digest
    earlier = record['preview']
    expected = payload['expected_preview_sha256']
    if (earlier.get('preview_sha256') != expected or checksum({k: v for k, v in earlier.items() if k != 'preview_sha256'}) != expected
            or earlier['source_hash'] != payload['expected_source_hash']
            or earlier['assignments_sha256'] != report['assignments_sha256']
            or record['result_source_hash'] != report['source_hash'] or not report['applicable']
            or any(row['additions'] for row in report['changes'])
            or earlier['verified_profiles'] != report['verified_profiles']
            or earlier['queue_id'] != report['queue_id'] or earlier['stopped_runs'] != report['stopped_runs']
            or earlier['excluded_stopped_runs'] != report['excluded_stopped_runs']
            or any(wf.file_hash(store.owned(item['path'])) != item['sha256'] for item in earlier['batch_evidence'].values())):
        raise wf.WorkflowError('The earlier grouping migration receipt conflicts with the current preview')
    return {'status': 'replayed', 'receipt_path': relative, 'receipt': record}


def migrate(store, command, payload):
    """Apply an explicitly reviewed metadata map without selecting a run."""
    if not store.neutral or store.run_id or store.selected_run_id:
        raise wf.WorkflowError('Grouping migration requires the neutral canonical queue writer')
    assignments = selection(command, payload)
    if command == PREVIEW:
        text, source_hash = current_queue(store)
        store.guard(payload['expected_source_hash'])
        report, _ = preview(store, text, source_hash, raw_state(store, text), assignments)
        return report

    operation = {'kind': 'task-grouping-migration', 'preview_sha256': payload['expected_preview_sha256']}
    with store.lock(local_delivery=operation):
        text, source_hash = current_queue(store)
        state = raw_state(store, text)
        relative = receipt_path(payload['expected_preview_sha256'])
        if source_hash != payload['expected_source_hash']:
            if store.owned(relative).is_file():
                report, _ = preview(store, text, source_hash, state, assignments)
                verify_current_index(store, text, state)
                recovered = replay(store, relative, payload, report)
                if recovered:
                    return recovered
            store.guard(payload['expected_source_hash'])
        report, profiles = preview(store, text, source_hash, state, assignments)
        if not report['applicable']:
            raise wf.WorkflowError(report['blocked_reason'] or 'Grouping migration contains missing or conflicting assignments')
        if report['preview_sha256'] != payload['expected_preview_sha256']:
            raise wf.WorkflowError('Grouping migration preview changed; inspect the current result')
        updated, applied = add_grouping(text, report)
        if not applied:
            verify_current_index(store, text, state)
            return {'status': 'unchanged', 'preview': report}
        result_hash = wf.digest(updated.encode())
        updated_tasks = wf.index(updated)
        result_grouping = {task['id']: wf.grouping_fields(task) for task in updated_tasks if task['id'] in assignments}
        record = {'schema': 1, 'preview': report, 'applied_ids': applied, 'recorded_at': wf.now(),
                  'result_source_hash': result_hash, 'batch_evidence': report['batch_evidence'],
                  'result_grouping': result_grouping}
        record['receipt_sha256'] = checksum(record)
        state.update(source_hash=result_hash, tasks=updated_tasks)
        writes = {QUEUE: updated, STATE: wf.dump(state), MANIFEST: wf.dump(navigation(store, result_hash)),
                  relative: wf.dump(record)}
        store.expect_unchanged(relative, None)
        for proof in report['batch_evidence'].values():
            store.expect_unchanged(proof['path'], proof['sha256'])
        current_profiles, stopped, excluded = {}, [], []
        workflow_handoff(store, state, assignments, current_profiles, stopped, excluded)
        if (current_profiles != profiles or stopped != report['stopped_runs'] or excluded != report['excluded_stopped_runs']
                or verified_profiles(store, current_profiles) != report['verified_profiles']):
            raise wf.WorkflowError('Grouping migration handoff or profile changed before canonical write')
        if any(wf.file_hash(store.owned(item['path'])) != item['sha256'] for item in report['batch_evidence'].values()):
            raise wf.WorkflowError('Historical intake batch evidence changed before canonical write')
        store.commit(writes)
        return {'status': 'applied', 'receipt_path': relative, 'receipt': record}
