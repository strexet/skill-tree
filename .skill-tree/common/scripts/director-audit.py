#!/usr/bin/env python3
"""Read selected Director and Core receipts and report bounded findings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from math import isfinite
from pathlib import Path
import re
import subprocess


HERE = Path(__file__).resolve().parent
RUNS = '.skill-tree/director/runs/'
HISTORY = '.skill-tree/history/run-events/'
PROFILE = '.skill-tree/installation/profile.json'
CLAIMS = ('.skill-tree/.writer-lock', '.skill-tree/.transaction.json', '.skill-tree/installation/.install-lock',
          '.skill-tree/installation/.journal.json')
SNAPSHOT = 'skill-tree-create-documents-snapshot'
SOURCE = '.skill-tree/common/scripts/create-documentation-snapshot.py'
DESTINATION = '.agents/skills/' + SNAPSHOT
RESOURCE = 'scripts/create-documentation-snapshot.py'
INSTALLED = DESTINATION + '/' + RESOURCE
CHECK = 'snapshot-scope-preserves-markdown-extension'
RECIPE = 'director-snapshot-canary'
SYMPTOM = 'markdown-extension-omitted'
SIGNATURE = 'documentation-snapshot:' + SYMPTOM
RESULT = '.skill-tree/artifacts/director/snapshot-canary-result.json'
OBSERVED_RESULT = {'schema': 1, 'kind': 'director-snapshot-canary-result', 'assertion_id': CHECK,
                   'observed': SYMPTOM, 'exit_code': 0, 'selected_count': 1}
RUNTIME = {'prerequisite-wait', 'transport-uncertainty', 'host-policy-rejection'}
CORE_PHASES = {'admit', 'awaiting-validation', 'blocked', 'capture-findings', 'completed', 'deferred-processing',
               'dependencies', 'implement', 'process-required', 'refresh-profile', 'resume-parent', 'revalidated',
               'review', 'start', 'stopped', 'validate', 'validation-blocked'}
CHECK_LANES = {'static', 'unit', 'integration', 'browser', 'server', 'unity-editmode', 'unity-playmode',
               'visual', 'player', 'device', 'native'}
TIMING_FIELDS = ('active_controller_seconds', 'tool_wall_seconds', 'prerequisite_wait_seconds')
COUNTS = ('expected', 'discovered', 'passed', 'failed', 'skipped')
UNITY_SEVERITIES = ('warning', 'error', 'exception', 'assertion', 'info')
EXPECTED_DIAGNOSTIC_FIELDS = ('case_id', 'severity', 'signature_sha256', 'expectation_sha256')


def _load_director():
    path = HERE / 'director-state.py'
    spec = importlib.util.spec_from_file_location('audit_director_state', path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


D = _load_director()
O = D._objective_helper()


def source_finding_digest(finding):
    fields = ('classification', 'component', 'symptom', 'conditions', 'generation')
    if finding.get('reproduction', {}).get('kind') == 'director-resource-check':
        fields += ('scope', 'expected', 'reproduction')
    return D._digest({field: finding[field] for field in fields})


def _json(root, relative, limit=16 * 1024 * 1024):
    path = D._safe_path(root, relative)
    if not path.exists():
        return None, None
    D._require(path.is_file() and 0 < path.stat().st_size <= limit, 'Selected audit record has invalid size or format')
    content = path.read_bytes()
    return json.loads(content), D.WF.digest(content)


def _quiet(root):
    D._require(not any(D._safe_path(root, name).exists() for name in CLAIMS),
               'An owned writer or installer requires a stable audit handoff')


def _identities(items, prefix):
    D._require(isinstance(items, list) and all(D.WF.valid_id(item, prefix) for item in items)
               and len(set(items)) == len(items), 'Select distinct exact audit evidence identities')
    return set(items)


def _time(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return instant.astimezone(timezone.utc).isoformat() if instant.tzinfo is not None else None
    except (OverflowError, ValueError):
        return None


def _checkpoint(record, task_ids):
    if not record:
        return None
    phase = record.get('phase')
    current = {'phase': phase if phase in CORE_PHASES else 'other'}
    task = record.get('stop_task_id') or record.get('current_task_id')
    if task in task_ids:
        current['task_id'] = task
    hold = record.get('director_question_hold') or {}
    reason = record.get('stop_reason')
    if D.WF.valid_id(hold.get('question_id'), 'DQ'):
        current.update(hold='director-question', question_id=hold['question_id'])
    elif record.get('profile_refresh_required') or phase == 'refresh-profile':
        current['hold'] = 'profile-refresh'
    elif reason:
        kind = 'stopped'
        if reason == 'Two unchanged executed failures':
            kind = 'repeated-check-failure'
        elif reason.startswith('Host policy rejected the operation: '):
            kind = 'host-policy-rejection'
        current.update(hold=kind, stop_reason_sha256=D.WF.digest(reason.encode()))
    admission = (record.get('admission') or {}).get('identity')
    if D._sha(admission):
        current['profile_identity'] = admission
    for counter in ('retry_used', 'repair_used', 'reload_used'):
        value = (record.get('limits') or {}).get(counter)
        if type(value) is int and value >= 0:
            current[counter] = value
    return current


def _check_attempt(task_id, check_id, attempt):
    attempt_id = attempt.get('attempt_id')
    D._require(D.WF.valid_id(attempt_id, 'C'), 'Canonical audit attempt lacks its exact identity')
    details = {'task_id': task_id, 'check_id': check_id, 'attempt_id': attempt_id}
    recipe = attempt.get('recipe') or {}
    if recipe.get('lane') in CHECK_LANES:
        details['lane'] = recipe['lane']
    prepared = _time(attempt.get('prepared_at'))
    if prepared:
        details['prepared_at'] = prepared
    deadline = _time((attempt.get('launch') or {}).get('deadline_utc'))
    if deadline:
        details['deadline_utc'] = deadline
    return details


def _check_diagnostics(record):
    details = {}
    recorded = _time(record.get('recorded_at'))
    if recorded:
        details['recorded_at'] = recorded
    lane = record.get('actual_lane')
    if lane in CHECK_LANES:
        details['lane'] = lane
    diagnostic = record.get('diagnostic_key')
    if D._sha(diagnostic):
        details['diagnostic_key'] = diagnostic
    times = record.get('timing', {})
    timings = {key: times[key] for key in TIMING_FIELDS if key in times
               and type(times[key]) in {int, float} and times[key] >= 0
               and (type(times[key]) is int or isfinite(times[key]))}
    if timings:
        details['timing'] = timings
    counts = record.get('counts', {})
    if all(type(counts.get(key)) is int and counts[key] >= 0 for key in COUNTS):
        details['counts'] = {key: counts[key] for key in COUNTS}
    evidence = [item['sha256'] for item in record.get('evidence', [])
                if item.get('available') is True and D._sha(item.get('sha256'))]
    if evidence:
        details['recorded_evidence_sha256'] = evidence
    return details


def _expected_diagnostic_key(item):
    return tuple(item.get(field) for field in EXPECTED_DIAGNOSTIC_FIELDS)


def _unity_selection(selection):
    reviewed = selection.get('unity_receipt')
    if reviewed is None:
        return None
    D._object(reviewed, {'attempt_id', 'path', 'sha256', 'required_cases', 'capture_identity'},
              {'expected_diagnostics'})
    identity = reviewed['capture_identity']
    D._object(identity, {'kind', 'sha256'})
    cases = reviewed['required_cases']
    D._require(D.WF.valid_id(reviewed['attempt_id'], 'C') and D._sha(reviewed['sha256'])
               and identity['kind'] in ('editor-session', 'player-build') and D._sha(identity['sha256'])
               and isinstance(cases, list) and 0 < len(cases) <= 256
               and all(isinstance(case, str) and re.fullmatch(r'[a-z][a-z0-9-]{0,63}', case) for case in cases)
               and len(cases) == len(set(cases)), 'Select an exact Unity evidence pointer and reviewed case ids')
    D._scope(reviewed['path'])
    diagnostics = reviewed.get('expected_diagnostics', [])
    D._require(isinstance(diagnostics, list) and len(diagnostics) <= 128, 'Select bounded reviewed Unity expectations')
    for item in diagnostics:
        D._object(item, set(EXPECTED_DIAGNOSTIC_FIELDS))
        D._require(item['case_id'] in cases and item['severity'] in UNITY_SEVERITIES
                   and D._sha(item['signature_sha256']) and D._sha(item['expectation_sha256']),
                   'Select an exact reviewed Unity expectation for a required case')
    D._require(len({_expected_diagnostic_key(item) for item in diagnostics}) == len(diagnostics),
               'Select distinct reviewed Unity expectations')
    return reviewed


def _unity_capture(summary, attempt, record):
    capture = summary.get('capture')
    if not isinstance(capture, dict) or capture.get('available') is not True:
        return None, 'unity-capture-unavailable'
    start, end = (_time(capture.get(field)) for field in ('start_utc', 'end_utc'))
    if capture.get('complete') is not True or not start or not end or start >= end:
        return None, 'unity-capture-incomplete'
    prepared, recorded = _time(attempt.get('prepared_at')), _time(record.get('recorded_at'))
    if not prepared or not recorded or not prepared <= start < end <= recorded:
        return None, 'unity-capture-outside-attempt'
    if not D._sha(capture.get('sha256')):
        return None, 'unity-capture-unverified'
    return {'available': True, 'complete': True, 'start_utc': start, 'end_utc': end, 'sha256': capture['sha256']}, None


def _unique_object(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError('Unity receipt contains duplicate JSON keys')
    return result


def _unity_receipt(worktree, reviewed, scope, record, attempt):
    pointer = {'path': reviewed['path'], 'sha256': reviewed['sha256'], 'available': True}
    evidence = record.get('evidence', [])
    if (worktree is None or attempt.get('attempt_id') != scope['attempt_id']
            or record.get('classification') != 'executed-control'
            or record.get('result') not in ('pass', 'fail')
            or not any(all(item.get(key) == value for key, value in pointer.items()) for item in evidence)):
        return None, 'unity-receipt-unavailable'
    try:
        path = D._safe_path(worktree, reviewed['path'])
        if not path.is_file():
            return None, 'unity-receipt-unavailable'
        limit = 256 * 1024
        with path.open('rb') as stream:
            content = stream.read(limit + 1)
        if not 0 < len(content) <= limit or D.WF.digest(content) != reviewed['sha256']:
            return None, 'unity-receipt-unavailable'
        summary = json.loads(content, object_pairs_hook=_unique_object)
    except (OSError, TypeError, ValueError, RecursionError):
        return None, 'unity-receipt-unavailable'
    if not isinstance(summary, dict) or type(summary.get('schema')) is not int or summary['schema'] != 1:
        return None, 'unity-receipt-unsupported'
    expected = {key: scope[key] for key in ('assignment_id', 'run_id', 'attempt_id')}
    expected.update(lane=record.get('actual_lane'), environment_identity=record.get('environment_identity'),
                    capture_identity=reviewed['capture_identity'])
    if (expected['lane'] not in CHECK_LANES or not D._sha(expected['environment_identity'])
            or any(summary.get(key) != value for key, value in expected.items())):
        return None, 'unity-receipt-foreign'
    capture, gap = _unity_capture(summary, attempt, record)
    if gap:
        return None, gap
    returned, groups = summary.get('cases'), summary.get('message_groups')
    if (not isinstance(returned, dict) or len(returned) > 256 or not isinstance(groups, list) or len(groups) > 128
            or any(not isinstance(case, str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', case)
                   or result not in ('pass', 'fail', 'skipped', 'unreached') for case, result in returned.items())):
        return None, 'unity-receipt-unsupported'
    required = set(reviewed['required_cases'])
    projected = {case: {'functional': returned.get(case, 'missing'),
                        'verdict': 'eligible' if returned.get(case) == 'pass' else 'open'}
                 for case in sorted(required)}
    gaps = [{'reason': 'unity-required-case-unavailable', 'case_id': case}
            for case in sorted(required) if returned.get(case) in (None, 'skipped', 'unreached')]
    observations = {}
    expectations = {_expected_diagnostic_key(item) for item in reviewed.get('expected_diagnostics', [])}
    uncertain = set()
    for group in groups:
        if not isinstance(group, dict):
            return None, 'unity-receipt-unsupported'
        case, signature, severity, classification, count = (
            group.get(key) for key in ('case_id', 'signature_sha256', 'severity', 'classification', 'count'))
        if (not D._sha(signature) or severity not in UNITY_SEVERITIES
                or classification not in ('fresh', 'expected', 'prior-session', 'out-of-window')
                or type(count) is not int or not 0 < count <= 1000000
                or (case is not None and (not isinstance(case, str) or case not in returned and case not in required))):
            return None, 'unity-receipt-unsupported'
        if case is not None and case not in required:
            continue
        key = D._digest([scope['queue_id'], scope['run_id'], scope['assignment_id'], scope['attempt_id'],
                         case, classification, severity, signature])
        if key in observations:
            return None, 'unity-receipt-unsupported'
        projected_group = {'id': key, 'signature_sha256': signature, 'severity': severity,
                           'classification': classification, 'count': count}
        if case in required:
            projected_group['case_id'] = case
        if classification == 'expected':
            if (returned.get(case) in ('pass', 'fail') and D._sha(group.get('expectation_sha256'))
                    and _expected_diagnostic_key(group) in expectations):
                projected_group['expectation_sha256'] = group['expectation_sha256']
            else:
                gap = {'reason': 'unity-expected-diagnostic-unverified'}
                if case in required:
                    gap['case_id'] = case
                gaps.append(gap)
                uncertain.update(required if case is None else (case,))
                projected_group['classification'] = 'expected-unverified'
        elif classification == 'fresh':
            if case is None:
                gaps.append({'reason': 'unity-message-case-unavailable'})
                uncertain.update(required)
            elif severity in ('error', 'exception', 'assertion'):
                projected[case].update(verdict='held', next_owner='unity')
            elif projected[case]['verdict'] == 'eligible':
                projected[case]['verdict'] = 'review'
        observations[key] = projected_group
    for case in uncertain:
        if projected[case]['verdict'] != 'held':
            projected[case]['verdict'] = 'open'
    return {'evidence_sha256': reviewed['sha256'], 'lane': expected['lane'],
            'environment_identity': expected['environment_identity'], 'capture_identity': expected['capture_identity'],
            'capture': capture, 'cases': projected, 'message_groups': list(observations.values()), 'gaps': gaps}, None


def _progress_slots(event, task_ids):
    for delta in event.get('progress_changes', []):
        task_id = delta['task_id']
        D._require(task_id in task_ids, 'Canonical audit progress escapes the selected run task scope')
        before = (delta['before'] or {}).get('checks', {})
        for check_id, slot in (delta['after'] or {}).get('checks', {}).items():
            D._require(isinstance(check_id, str) and re.fullmatch(r'[a-z][a-z0-9-]*', check_id),
                       'Canonical audit check lacks a portable check ID')
            yield task_id, check_id, before.get(check_id, {}), slot


def _progress_checks(slots):
    for task_id, check_id, previous_slot, slot in slots:
        previous = previous_slot.get('receipts', {})
        for attempt_id, record in slot.get('receipts', {}).items():
            D._require(D.WF.valid_id(attempt_id, 'C') and record.get('attempt_id') == attempt_id,
                       'Canonical audit receipt has a different attempt identity')
            if attempt_id in previous:
                D._require(previous[attempt_id] == record, 'Previously recorded audit check receipt changed')
                continue
            yield task_id, check_id, attempt_id, record, slot.get('attempt', {})


def _event(entry, digest, source, queue_id, run_id, registry):
    D._require(entry['schema'] == 1 and entry['queue_id'] == queue_id and entry['run_id'] == run_id
               and D.WF.valid_id(entry['id'], 'E') and entry['id'] in registry['applied_events']
               and type(entry['sequence']) is int and 0 < entry['sequence'] <= registry['event_sequences'][run_id],
               'Selected event is outside the canonical child queue and run')
    identity = {'event_id': entry['id'], 'event_sha256': digest, 'event_source': source,
                'event_sequence': entry['sequence']}
    identity['event_path'] = (HISTORY + run_id.lower() + '/' + entry['id'].lower() + '.json' if source == 'canonical'
                              else '.skill-tree/run-evidence/' + run_id.lower() + '/events.json')
    timestamp = D.WF.run_event_recorded_at(entry)
    if timestamp:
        identity['event_recorded_at'] = timestamp
    return entry, identity


def _events(root, worktree, selection, queue_id, run_id, registry):
    selected = _identities(selection.get('event_ids', []), 'E')
    directory = HISTORY + run_id.lower()
    result = {}
    canonical = D._safe_path(root, directory)
    for path in sorted(canonical.glob('e-*.json')):
        event_id = 'E-' + path.stem[2:]
        if selected and event_id not in selected:
            continue
        entry, digest = _json(root, directory + '/' + path.name)
        D._require(entry is not None and entry['id'] == event_id, 'Canonical event identity and filename differ')
        result[event_id] = _event(entry, digest, 'canonical', queue_id, run_id, registry)
    reviewed = selection.get('journal_export_sha256')
    if reviewed is not None:
        D._require(D._sha(reviewed) and worktree is not None, 'Reviewed journal export requires the exact owned worktree')
        relative = '.skill-tree/run-evidence/' + run_id.lower() + '/events.json'
        archive, digest = _json(worktree, relative)
        D._require(digest == reviewed and archive['schema'] == 1 and archive['queue_id'] == queue_id
                   and archive['run_id'] == run_id, 'Existing reviewed journal export is unavailable or changed')
        for entry in archive['events']:
            if not selected or entry['id'] in selected:
                saved = _event(entry, D._digest(entry), 'reviewed-export', queue_id, run_id, registry)
                result.setdefault(entry['id'], (saved[0], {**saved[1], 'export_sha256': reviewed}))
    D._require(len({event[0]['sequence'] for event in result.values()}) == len(result),
               'Duplicate canonical audit sequence')
    return (sorted(result.values(), key=lambda entry: entry[0]['sequence']), sorted(selected - result.keys()))


def _missing_sequences(events, last_sequence):
    expected = 1
    for sequence in [entry['sequence'] for entry, _ in events] + [last_sequence + 1]:
        if expected < sequence:
            yield {'reason': 'native-event-sequence-unavailable', 'first_event_sequence': expected,
                   'last_event_sequence': sequence - 1}
        expected = sequence + 1


def _pending_attempts(state, run_id, task_ids):
    for task_id in sorted(task_ids):
        record = state['task_progress'].get(task_id, {})
        if record.get('run_id', run_id) != run_id:
            continue
        for check_id, slot in sorted(record.get('checks', {}).items()):
            if D.WF.pending_check_attempt(slot):
                D._require(re.fullmatch(r'[a-z][a-z0-9-]*', check_id), 'Canonical audit check lacks a portable check ID')
                yield _check_attempt(task_id, check_id, slot['attempt'])


def _parent_timeline(director):
    events = {'run-started', 'run-paused', 'run-resumed', 'run-cancelled', 'dispatch-prepared', 'dispatch-invoking',
              'dispatch-recorded', 'dispatch-failed', 'question-prepared', 'question-held', 'answer-recorded',
              'answer-delivered', 'question-failed', 'assignment-completed'}
    codes = {'operation': {'intake', 'process', 'start'}, 'origin': {'owner', 'approved-default'},
             'phase': {'running', 'paused', 'cancelled', 'preparing', 'waiting', 'answer-recorded', 'delivered'},
             'reason': {'guard-rejected', 'transport-error', 'io-error', 'process-timeout'},
             'stage': {'retain-intent', 'invoke-child', 'observe-child', 'reconcile-child-task', 'acknowledge-child',
                       'recover-child-receipt', 'hold-child', 'release-child'}}
    identities = {'task_id': 'T', 'pending_id': 'P', 'processing_run_id': 'PR', 'child_run_id': 'WR',
                  'question_id': 'DQ', 'attempt_id': 'DA', 'outcome_id': 'O'}
    for sequence, event in enumerate(director.get('timeline', []), 1):
        timestamp = _time(event.get('recorded_at'))
        D._require(type(event.get('sequence')) is int and event['sequence'] == sequence
                   and event.get('event') in events and timestamp,
                   'Director timeline contains an invalid event identity')
        detail = {'sequence': sequence, 'event': event['event'], 'recorded_at': timestamp}
        assignment_id = event.get('assignment_id')
        if assignment_id in director['assignments']:
            detail['assignment_id'] = assignment_id
        detail.update({key: event[key] for key, prefix in identities.items() if D.WF.valid_id(event.get(key), prefix)})
        detail.update({key: event[key] for key, allowed in codes.items() if event.get(key) in allowed})
        detail.update({key: event[key] for key in ('receipt_sha256', 'failure_key') if D._sha(event.get(key))})
        if type(event.get('failures')) is int and event['failures'] > 0:
            detail['failures'] = event['failures']
        yield detail


def _parent_assignment_status(state):
    dispatches, failures, questions = {}, {}, []
    for operation, record in sorted(state['dispatches'].items()):
        if operation in {'intake', 'process', 'start'} and record.get('status') in {'prepared', 'invoking', 'recorded'}:
            dispatches[operation] = record['status']
            if type(record.get('failures')) is int and record['failures'] > 0 and D._sha(record.get('failure_key')):
                failures[operation] = {'failures': record['failures'], 'failure_key': record['failure_key']}
    for question_id, question in sorted(state['questions'].items()):
        phase = question.get('phase')
        if phase in {'preparing', 'waiting', 'answer-recorded'} and D.WF.valid_id(question_id, 'DQ'):
            questions.append({'question_id': question_id, 'phase': phase})
    return {'dispatches': dispatches, 'dispatch_failures': failures, 'open_questions': questions,
            'waiting': sum(item['phase'] == 'waiting' for item in questions),
            'blocked': bool(state.get('blocker')), 'completed': bool(state.get('completed'))}


def _generation(worktree):
    if worktree is None:
        return None
    try:
        observed = D._inspect_profile(worktree)
        profile, digest = _json(worktree, PROFILE)
        D._require(observed['kind'] == 'owned-profile' and observed['sha256'] == digest
                   and profile['identity'] == observed['identity'], 'No exact verified installed generation')
        package = profile['destinations'][DESTINATION]
        source = profile['source_digests'][SOURCE.removeprefix('.skill-tree/')]
        artifact = package['files'][RESOURCE]
        bundle_path = '.skill-tree/installation/source/' + SOURCE.removeprefix('.skill-tree/')
        D._require('codex' in package.get('providers', [package['provider']]) and package['name'] == SNAPSHOT
                   and D._sha(source) and D._sha(artifact) and D._sha(package['identity'])
                   and profile['bundle_digests'][bundle_path] == source
                   and D.WF.file_hash(D._safe_path(worktree, bundle_path)) == source
                   and D.WF.file_hash(D._safe_path(worktree, INSTALLED)) == artifact
                   and profile['recipes'][RECIPE]['lane'] == 'unit', 'Profile lacks the exact checked helper and recipe')
    except (KeyError, TypeError, OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return {'source_sha256': source, 'installed_sha256': artifact}, {'profile_sha256': digest,
                                                                      'package_sha256': package['identity']}


def _source_check(check_id, record, attempt, checks, worktree, verified):
    if (check_id != CHECK or record.get('result') != 'fail' or record.get('classification') != 'executed-control'
            or record.get('actual_lane') != 'unit' or record.get('failure_signature') != SIGNATURE):
        return False
    if verified is None or (checks.get(check_id) or {}).get('recipe_id') != RECIPE:
        return False
    generation, _ = verified
    pointer = next((item for item in record.get('evidence', []) if item.get('path') == RESULT), {})
    try:
        proof, digest = _json(worktree, RESULT, limit=65536)
    except (OSError, ValueError):
        return False
    matched = (attempt.get('attempt_id') == record['attempt_id'] and attempt.get('key') == record['key']
            and attempt.get('recipe', {}).get('lane') == 'unit' and attempt.get('sources') == record['sources']
            and record['sources'].get(INSTALLED) == generation['installed_sha256'] and proof == OBSERVED_RESULT
            and pointer.get('available') is True and digest == pointer.get('sha256'))
    return {'result_path': RESULT, 'result_sha256': digest} if matched else None


def _finding(generation):
    finding = {
        'schema': 1, 'classification': 'source-defect', 'component': 'documentation-snapshot', 'symptom': SYMPTOM,
        'conditions': {'recipe_id': RECIPE, 'lane': 'unit', 'assertion_id': CHECK}, 'generation': generation,
        'expected': 'The selected Markdown path retains the .md extension in the dry-run listing.',
        'observed': 'The verified installed helper omitted the selected Markdown extension.',
        'reproduction': {'operation': SNAPSHOT, 'args': ['--dry-run', '--include', 'README.md']},
        'impact': 'The dry-run listing cannot be used to verify the exact selected document path.',
        'suggested_fix': 'Preserve the original repository-relative path in the snapshot report and replay the same check.',
        'scope': {'source_path': SOURCE, 'operation': SNAPSHOT}, 'evidence': [],
    }
    return {**finding, 'finding_sha256': source_finding_digest(finding)}


def _diagnostic_finding(worktree, check_id, check, record, attempt):
    """Attribute a structured expected/observed result to one verified packaged resource."""
    recipe = (check or {}).get('recipe_id')
    if (worktree is None or not recipe or record.get('classification') != 'executed-control'
            or record.get('result') != 'fail' or record.get('failure_category') != 'expected-behavior'
            or record.get('actual_lane') != 'unit' or not isinstance(attempt, dict)
            or attempt.get('attempt_id') != record.get('attempt_id') or attempt.get('key') != record.get('key')
            or attempt.get('sources') != record.get('sources') or attempt.get('recipe', {}).get('lane') != 'unit'):
        return None
    result_path = f'.skill-tree/artifacts/director/{check_id}.json'
    refs = [ref for ref in record['evidence'] if ref.get('available') and ref.get('path') == result_path]
    if len(refs) != 1:
        return None
    try:
        proof, result_hash = _json(worktree, result_path, limit=65536)
        D._object(proof, {'schema', 'kind', 'assertion_id', 'installed_path', 'expected', 'observed'})
        expected, observed = proof['expected'], proof['observed']
        D._require(proof['schema'] == 1 and proof['kind'] == 'director-resource-check'
                   and proof['assertion_id'] == check_id and all(D._token(v) and len(v) <= 96 for v in (expected, observed))
                   and expected != observed and refs[0]['sha256'] == result_hash, 'Inconclusive resource result')
        installed = D._scope(proof['installed_path']).as_posix()
        profile_state = D._inspect_profile(worktree)
        profile, profile_hash = _json(worktree, PROFILE)
        D._require(profile_state['kind'] == 'owned-profile' and profile_state['sha256'] == profile_hash
                   and profile['recipes'][recipe]['lane'] == 'unit', 'Unverified diagnostic profile')
        matches = [(rel, pkg) for rel, pkg in profile['destinations'].items() if installed.startswith(rel + '/')]
        D._require(len(matches) == 1, 'Unowned diagnostic resource')
        dest, package = matches[0]
        resource = installed[len(dest) + 1:]
        group, name = resource.split('/', 1)
        mapping, mapping_hash = _json(worktree, '.skill-tree/installation/source/config/resource-map.json')
        D._require(profile['source_digests']['config/resource-map.json'] == mapping_hash, 'Resource map changed')
        source = mapping[package['name']][group][name]
        D._scope(source)
        generation = package['files'][resource]
        D._require(D._sha(generation) and record['sources'][installed] == profile['source_digests'][source] == generation
                   and D.WF.file_hash(D._safe_path(worktree, installed)) == generation, 'Resource generation changed')
        fixtures = {path: digest for path, digest in record['sources'].items() if path != installed}
        D._require(all(D._scope(path) and D._sha(digest) for path, digest in fixtures.items()), 'Invalid fixture')
        params = {}
        for key, value in check['parameters'].items():
            D._require(isinstance(value, str) and (value in record['sources'] or D._token(value))
                       and key not in {'project_root', 'execution_checkout', 'queue_root'}, 'Unsupported reproduction input')
            params[key] = '.skill-tree/' + source if value == installed else value
        finding = {'schema': 1, 'classification': 'source-defect', 'component': package['name'], 'symptom': observed,
                   'conditions': {'recipe_id': recipe, 'lane': 'unit', 'assertion_id': check_id},
                   'generation': {'source_sha256': generation, 'installed_sha256': generation}, 'expected': expected,
                   'observed': observed, 'scope': {'source_path': '.skill-tree/' + source, 'operation': package['name']},
                   'reproduction': {'kind': 'director-resource-check', 'resource': resource, 'fixtures': fixtures, 'parameters': params},
                   'evidence': []}
        return {**finding, 'finding_sha256': source_finding_digest(finding)}, {
            'result_path': result_path, 'result_sha256': result_hash, 'profile_sha256': profile_hash,
            'package_sha256': package['identity']}
    except (OSError, KeyError, TypeError, ValueError, subprocess.TimeoutExpired):
        return None


def _classification(area, record, check_id):
    category = record.get('classification')
    if category in RUNTIME:
        return 'runtime-prerequisite', category
    if record.get('result') == 'fail' and category == 'executed-control':
        if check_id == CHECK or area['role'] == 'source-maintenance':
            return 'unclassified-failure', 'source-proof-unavailable'
        return 'product', 'checked-failure'
    if record.get('status') == 'cancelled-no-result':
        return 'runtime-prerequisite', 'cancelled-no-result'
    return 'check', record.get('result') if record.get('result') in {'fail', 'pass', 'red', 'unavailable'} else 'unknown'


class DirectorAudit:
    def __init__(self, registry):
        self.registry = registry
        self.root = registry.root
        self.plans = D._plan_helper(registry)

    def _audit_selection(self, selection, assignments, director, registry, bindings):
        D._object(selection, {'assignment_id', 'run_id'}, {'event_ids', 'journal_export_sha256', 'unity_receipt'})
        unity_selection = _unity_selection(selection)
        name, run_id = selection['assignment_id'], selection['run_id']
        D._require(D._token(name) and name in assignments and name in director['assignments']
                   and D.WF.valid_id(run_id, 'WR'), 'Select an exact admitted Director assignment and child run')
        spec, state = assignments[name], director['assignments'][name]
        area = registry['areas'][spec['area']['id']]
        D._require(O._area_identity(area) == O._area_identity(spec['area']) and 'audit' in area['allowed_effects'],
                   'The selected area does not authorize this exact read-only audit')
        root = O._child_root(registry, bindings, area['id'])
        _quiet(root)
        store = D.WF.Store(root, route_queue=False, neutral=True)
        queue_before = D.WF.file_hash(store.state)
        child = store.load()
        run_registry = child['run_registry']
        run = run_registry['runs'].get(run_id)
        start = state['dispatches'].get('start', {})
        D._require(run is not None and start.get('status') == 'recorded' and start['result']['id'] == run_id,
                   'The child run is outside the recorded Director start')
        envelope = {'schema': 1, 'director_id': director['director_id'], 'assignment_id': name,
                    'queue_id': area['queue_id'], 'plan_sha256': director['plan_sha256']}
        observed = D.WF.director_dispatch_helper().observe(store, {'operation': 'start', 'director_dispatch': envelope})
        D._require(observed['receipt'] is not None and observed['receipt']['receipt_sha256'] == start['receipt_sha256']
                   and observed['observed_result'] == run, 'The canonical child start receipt differs from the Director record')
        worktree = O._read_run_root(root, run)
        task_ids = set(run['admitted_task_ids'])
        queue_tasks = {task['id']: task for task in D.WF.parse(store.text()) if task['id'] in task_ids}
        outcomes = {item['id']: item for item in store.outcomes() if item.get('run_id') == run_id and item.get('task_id') in task_ids}
        checks = {task_id: {check['id']: check for check in D.WF.check_specs(task)}
                  for task_id, task in queue_tasks.items()}
        for outcome in outcomes.values():
            if outcome.get('disposition') == 'completed' and outcome.get('validation_plan'):
                checks.setdefault(outcome['task_id'], {check['id']: check for check in outcome['validation_plan']})
        events, missing = _events(root, worktree, selection, area['queue_id'], run_id, run_registry)
        base = {'area_id': area['id'], 'queue_id': area['queue_id'], 'run_id': run_id, 'assignment_id': name,
                'start_receipt_sha256': start['receipt_sha256']}
        gaps = [{**base, 'event_id': event_id, 'reason': 'native-event-unavailable'} for event_id in missing]
        if not events:
            gaps.append({**base, 'reason': 'run-events-unavailable'})
        last_sequence = run_registry.get('event_sequences', {}).get(run_id, 0)
        if not selection.get('event_ids'):
            gaps.extend({**base, **gap} for gap in _missing_sequences(events, last_sequence))
        status = {**base, 'checkpoint': _checkpoint(run, task_ids),
                  'open_check_attempts': list(_pending_attempts(child, run_id, task_ids)),
                  'event_scope': 'selected' if selection.get('event_ids') else 'all',
                  'observed_events': len(events), 'last_recorded_sequence': last_sequence,
                  'undated_events': sum('event_recorded_at' not in source for _, source in events)}
        verified = None
        checked_generation = False
        observations, findings, timeline = [], {}, []
        duplicate_receipts = set()
        terminal_ids = set()
        unity_attempts = []
        for event, source in events:
            before = _checkpoint(event.get('checkpoint_before'), task_ids)
            after = _checkpoint(event.get('checkpoint_after'), task_ids)
            if before != after:
                timeline.append({**base, **source, 'event': 'checkpoint', 'before': before, 'after': after})
            slots = list(_progress_slots(event, task_ids))
            for task_id, check_id, previous, slot in slots:
                attempt = slot.get('attempt')
                if attempt and attempt['attempt_id'] != (previous.get('attempt') or {}).get('attempt_id'):
                    timeline.append({**base, **source, 'event': 'check-prepared', **_check_attempt(task_id, check_id, attempt)})
            for task_id, check_id, attempt_id, record, attempt in _progress_checks(slots):
                identity = (task_id, check_id, attempt_id)
                D._require(identity not in duplicate_receipts, 'The same check receipt first appears in two scoped events')
                duplicate_receipts.add(identity)
                evidence = {**base, **source, 'task_id': task_id, 'check_id': check_id, 'attempt_id': attempt_id,
                            'record_sha256': D._digest(record)}
                if unity_selection and attempt_id == unity_selection['attempt_id']:
                    unity_attempts.append((evidence, record, attempt))
                if check_id == CHECK and not checked_generation:
                    verified = _generation(worktree)
                    checked_generation = True
                proof = _source_check(check_id, record, attempt, checks.get(task_id, {}), worktree, verified)
                diagnostics = _check_diagnostics(record)
                diagnostic = None if proof else _diagnostic_finding(
                    worktree, check_id, checks.get(task_id, {}).get(check_id), record, attempt)
                if proof or diagnostic:
                    if diagnostic:
                        finding, proof = diagnostic
                        profile = {}
                    else:
                        generation, profile = verified
                        finding = _finding(generation)
                    identity = finding['finding_sha256']
                    findings.setdefault(identity, finding)['evidence'].append({**evidence, **profile, **proof})
                    category, symptom = finding['classification'], finding['symptom']
                else:
                    category, symptom = _classification(area, record, check_id)
                    observations.append({**evidence, **diagnostics, 'classification': category, 'symptom': symptom})
                outcome = record.get('result', record.get('status'))
                timeline.append({**evidence, **diagnostics, 'event': 'check-recorded',
                                 'classification': category, 'symptom': symptom,
                                 'status': outcome if outcome in {'pass', 'fail', 'red', 'unavailable', 'cancelled-no-result'}
                                 else 'unknown'})
            for outcome in event.get('outcomes', []):
                outcome_id, task_id = outcome['id'], outcome['task_id']
                D._require(D.WF.valid_id(outcome_id, 'O') and D.WF.valid_id(task_id, 'T') and task_id in task_ids
                           and outcome['run_id'] == run_id and outcome_id not in terminal_ids,
                           'Canonical event outcome differs from selected child run or task')
                terminal_ids.add(outcome_id)
                retained = outcomes.get(outcome_id)
                if retained is None or run.get('completion_refs', {}).get(task_id) != outcome_id:
                    gaps.append({**base, **source, 'task_id': task_id, 'outcome_id': outcome_id, 'reason': 'outcome-unavailable'})
                else:
                    terminal = {**base, **source, 'task_id': task_id, 'outcome_id': outcome_id,
                                'record_sha256': D._digest(retained),
                                'status': 'completed' if retained['disposition'] == 'completed' else 'closed'}
                    observations.append({**terminal, 'classification': 'outcome'})
                    timeline.append({**terminal, 'event': 'outcome-recorded'})
        if unity_selection:
            if len(unity_attempts) != 1:
                reason = 'unity-attempt-unavailable' if not unity_attempts else 'unity-attempt-ambiguous'
                gaps.append({**base, 'attempt_id': unity_selection['attempt_id'], 'reason': reason})
            else:
                evidence, record, attempt = unity_attempts[0]
                receipt, reason = _unity_receipt(worktree, unity_selection, evidence, record, attempt)
                identifiers = {key: evidence[key] for key in ('task_id', 'check_id', 'attempt_id', 'record_sha256')}
                if reason:
                    gaps.append({**base, **identifiers, 'reason': reason})
                else:
                    gaps.extend({**base, **identifiers, **gap} for gap in receipt.pop('gaps'))
                    status['unity_receipt'] = {**identifiers, **receipt,
                                               'functional_counts': _check_diagnostics(record).get('counts')}
        for question_id, question in sorted(state['questions'].items()):
            if question.get('child_run_id') == run_id and question.get('phase') == 'waiting':
                hold = run.get('director_question_hold') or {}
                valid = D.WF.valid_id(question_id, 'DQ') and D.WF.valid_id(question['attempt_id'], 'DA')
                D._require(valid and question['task_id'] in task_ids and question['start_receipt_sha256'] == start['receipt_sha256'],
                           'Recorded owner wait is outside the selected child scope')
                expected = {'director_run_id': director['director_run_id'], 'question_id': question_id,
                            'attempt_id': question['attempt_id'], 'question_sha256': question['question_sha256']}
                if any(hold.get(key) != value for key, value in expected.items()):
                    gaps.append({**base, 'question_id': question_id, 'reason': 'owner-wait-hold-mismatch'})
                else:
                    observations.append({**base, 'question_id': question_id, 'attempt_id': question['attempt_id'],
                                         'classification': 'owner-wait', 'task_id': question['task_id']})
        _quiet(root)
        D._require(queue_before == D.WF.file_hash(store.state), 'Canonical child queue changed during audit')
        return findings, observations, gaps, status, timeline

    def read(self, request):
        D._object(request, {'director_run_id', 'selections'})
        run_id = request['director_run_id']
        selections = request['selections']
        D._require(D.WF.valid_id(run_id, 'DR') and isinstance(selections, list),
                   'Audit requires an exact Director run and child selection list')
        _quiet(self.root)
        run_path = RUNS + run_id.lower() + '.json'
        director, run_sha = _json(self.root, run_path)
        registry, bindings, basis = self.registry._load()
        D._require(director is not None and registry is not None and director['schema'] == 1
                   and director['director_run_id'] == run_id and director['director_id'] == registry['director_id']
                   and director['phase'] in {'running', 'paused', 'cancelled'},
                   'Exact Director run or registry is unavailable')
        plan, plan_sha = self.plans.frozen({key: director[key] for key in ('objective_id', 'plan_id', 'plan_revision')})
        D._require(plan_sha == director['plan_sha256'], 'Exact Director audit plan changed')
        assignments = {item['id']: item for item in plan['assignments']}
        all_findings, all_observations, all_gaps, children, child_timeline = {}, [], [], [], []
        seen = set()
        for selection in selections:
            findings, observations, gaps, status, timeline = self._audit_selection(selection, assignments, director, registry, bindings)
            name = selection['assignment_id']
            D._require(name not in seen, 'Select a Director assignment once')
            seen.add(name)
            for identity, finding in findings.items():
                retained = all_findings.setdefault(identity, {**finding, 'evidence': []})
                retained['evidence'].extend(finding['evidence'])
            all_observations.extend(observations)
            all_gaps.extend(gaps)
            children.append(status)
            child_timeline.extend(timeline)
        parent_scope = {name: _parent_assignment_status(state) for name, state in sorted(director['assignments'].items())}
        parent_timeline = list(_parent_timeline(director))
        if not parent_timeline or parent_timeline[0]['event'] != 'run-started':
            all_gaps.append({'director_run_id': run_id, 'reason': 'director-timeline-start-unavailable'})
        _quiet(self.root)
        D._require(run_sha == D.WF.file_hash(D._safe_path(self.root, run_path))
                   and all(sha == D.WF.file_hash(D._safe_path(self.root, path)) for path, sha in basis.items()),
                   'Director audit scope changed during observation')
        order = lambda row: (row.get('queue_id', ''), row.get('run_id', ''), row.get('event_sequence', 0),
                             row.get('task_id', ''), row.get('check_id', ''), row.get('attempt_id', ''))
        for finding in all_findings.values():
            finding['evidence'].sort(key=order)
        result = {'schema': 1, 'director_run_id': run_id, 'plan_sha256': plan_sha,
                  'director_status': {'phase': director['phase'], 'run_sha256': run_sha, 'run_path': run_path,
                                      'assignments': parent_scope},
                  'director_timeline': parent_timeline, 'child_status': sorted(children, key=order),
                  'child_timeline': sorted(child_timeline, key=order),
                  'findings': [all_findings[key] for key in sorted(all_findings)],
                  'observations': sorted(all_observations, key=order), 'coverage_gaps': sorted(all_gaps, key=order)}
        return {**result, 'audit_sha256': D._digest(result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('audit',))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    try:
        request = json.loads(args.input.read_text())
        report = DirectorAudit(D.DirectorRegistry(args.root)).read(request)
    except (KeyError, TypeError, AttributeError, OSError, subprocess.TimeoutExpired):
        parser.exit(2, 'Exact selected audit metadata is unavailable or malformed.\n')
    except ValueError as error:
        parser.exit(2, f'{error}\n')
    print(D.WF.dump(report), end='')


if __name__ == '__main__':
    main()
