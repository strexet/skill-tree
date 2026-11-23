"""Checkpoints and delivery receipts for exact Director questions in child queues."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re


HOLD = 'director_question_hold'
RECEIPTS = '.skill-tree/history/director-questions'
CORE_SOURCE = 'common/scripts/workflow-state.py'
CORE_BUNDLE = '.skill-tree/installation/source/' + CORE_SOURCE
CORE_PACKAGE = 'scripts/workflow-state.py'
PROFILE = '.skill-tree/installation/profile.json'
COMMANDS = {'director-question-preflight', 'director-question-observe', 'director-question-check',
            'director-question-hold', 'director-question-release'}
SHA = re.compile(r'[a-f0-9]{64}\Z')
FIELDS = {'director_dispatch', 'director_run_id', 'child_run_id', 'task_id', 'start_receipt_sha256',
          'question_id', 'attempt_id', 'question_sha256'}


def require(test, message):
    if not test:
        raise wf.WorkflowError(message)


def digest(value):
    return wf.digest(wf.dump(value).encode())


def sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _context(command, payload):
    extra = {'answer'} if command == 'director-question-release' else set()
    require(isinstance(payload, dict) and set(payload) == FIELDS | extra,
            'Director child handoff requires the exact context fields')
    for field, prefix in (('director_run_id', 'DR'), ('child_run_id', 'WR'), ('task_id', 'T'),
                          ('question_id', 'DQ'), ('attempt_id', 'DA')):
        require(wf.valid_id(payload[field], prefix), 'Director child handoff requires exact ' + field)
    require(sha(payload['question_sha256']) and sha(payload['start_receipt_sha256']),
            'Director child handoff requires exact receipt and question digests')
    if extra:
        answer = payload['answer']
        require(isinstance(answer, dict) and set(answer) == {'choice', 'origin', 'actor', 'authority_ref', 'evidence_sha256'}
                and answer['origin'] in {'owner', 'approved-default'} and sha(answer['evidence_sha256'])
                and all(isinstance(answer[key], str) and answer[key] and '\0' not in answer[key]
                        for key in ('choice', 'actor', 'authority_ref')), 'Director child release requires verified answer metadata')
    return {field: payload[field] for field in FIELDS}


def _selected(store, context):
    dispatch = wf.director_dispatch_helper()
    identity, key = dispatch.envelope('start', context['director_dispatch'])
    require(not store.neutral and store.run_id == context['child_run_id'], 'Select the exact directed child run')
    _, start = dispatch._receipt(store, identity, key)
    require(start is not None and start['receipt_sha256'] == context['start_receipt_sha256']
            and start['plan_sha256'] == context['director_dispatch']['plan_sha256']
            and start['result']['id'] == context['child_run_id'], 'Original directed child start receipt is unavailable or changed')
    text = store.text()
    state = store.load(text)
    registry = state.get('run_registry')
    run = state['active_run']
    require(registry is not None and registry['queue_id'] == identity['queue_id'] and run
            and dispatch.matches_start_workspace(store, run, start), 'Original child run identity changed')
    wf.workspaces.ensure_workspace(store, run)
    return dispatch, text, state, run


def _verify_worktree_core(store):
    root = store.source_root
    current = wf.file_hash(Path(wf.__file__))
    profile_path = wf.binding_path(root, PROFILE)
    error = 'Original child worktree requires the exact current Core workflow helper in every installed package'

    def matches(relative):
        path = wf.binding_path(root, relative)
        return path.is_file() and wf.file_hash(path) == current

    discovered = set()
    for package in wf.installed_catalog(root):
        relative = (Path(package['entrypoint']).parent / CORE_PACKAGE).as_posix()
        if relative in package['resources']:
            discovered.add(relative)
    if not profile_path.is_file():
        source = '.skill-tree/' + CORE_SOURCE
        require(matches(source) and not discovered, error)
        wf.workspaces.local_git_text(root, 'ls-files', '--error-unmatch', '--', source)
        return

    profile = json.loads(profile_path.read_text())
    require(profile.get('project_root') == str(root)
            and profile.get('source_digests', {}).get(CORE_SOURCE) == current
            and profile.get('bundle_digests', {}).get(CORE_BUNDLE) == current
            and matches(CORE_BUNDLE), error)
    helpers = {destination + '/' + CORE_PACKAGE: record['files'][CORE_PACKAGE]
               for destination, record in profile.get('destinations', {}).items() if CORE_PACKAGE in record.get('files', {})}
    require(helpers and discovered <= helpers.keys()
            and all(expected == current and matches(relative) for relative, expected in helpers.items()), error)


def _basis(store, text, state, run, task_id):
    task = next((entry for entry in wf.parse(text) if entry['id'] == task_id), None)
    require(task is not None and run['current_task_id'] == task_id
            and task_id in run['admitted_task_ids'] and not run.get('maintenance')
            and not run.get('profile_refresh_required'), 'The original active child task or admission changed')
    checks = state['task_progress'].get(task_id, {}).get('checks', {})
    require(not any(wf.pending_check_attempt(slot) for slot in checks.values()),
            'Reconcile the child check before a Director question handoff')
    wf.assert_admission(store, state, task_id)
    _verify_worktree_core(store)
    return {
        'task_sha256': wf.digest(task['body'].encode()),
        'admission_sha256': digest(run['admission']),
        'profile_sha256': wf.file_hash(store.source_root / PROFILE),
        'workspace_sha256': digest(run['workspace']),
        'scope_sha256': digest({key: run[key] for key in ('snapshot', 'required_ids', 'admitted_task_ids')}),
    }


def _receipt_path(context, command):
    return RECEIPTS + '/' + digest({'context': context, 'effect': command}) + '.json'


def _read(dispatch, store, context, command, request=None):
    relative = _receipt_path(context, command)
    record, receipt_sha = dispatch._read(store, relative)
    if record is not None:
        require(record.get('schema') == 1 and record.get('context_sha256') == digest(context)
                and record.get('effect') == command and sha(record.get('request_sha256'))
                and digest({key: value for key, value in record.items() if key != 'receipt_sha256'}) == record.get('receipt_sha256'),
                'Invalid Director child question receipt')
        if request is not None:
            require(record['request_sha256'] == digest(request), 'Director child question request has a conflicting replay')
    return relative, record, receipt_sha


def _require_hold(run, marker, context, current):
    require(marker and all(marker.get(field) == context[field] for field in
                           ('director_run_id', 'question_id', 'attempt_id', 'question_sha256'))
            and run['phase'] == 'blocked' and run['stop_reason'] == marker['stop_reason']
            and all(marker.get(field) == value for field, value in current.items()),
            'Child checkpoint, admission or original hold changed')


def handle(store, command, payload, *, verify_parent=None):
    context = _context(command, payload)
    if command == 'director-question-release':
        require(callable(verify_parent), 'Director release requires the durable parent answer verifier')
    if command == 'director-question-preflight':
        _, _, _, run = _selected(store, context)
        _verify_worktree_core(store)
        require(wf.admit_profile(store) == run['admission'], 'Current child admission differs from the original run')
        return
    if command == 'director-question-observe':
        dispatch, _, _, run = _selected(store, context)
        _, hold, _ = _read(dispatch, store, context, 'director-question-hold')
        _, release, _ = _read(dispatch, store, context, 'director-question-release')
        marker = run.get(HOLD)
        return {'hold': hold, 'release': release,
                'waiting': bool(marker and marker['question_sha256'] == context['question_sha256'])}
    if command == 'director-question-check':
        _, text, state, run = _selected(store, context)
        current = _basis(store, text, state, run, context['task_id'])
        _require_hold(run, run.get(HOLD), context, current)
        require(wf.admit_profile(store) == run['admission'], 'Current child admission differs from the original run')
        return current
    owner = {'kind': command, 'question_sha256': context['question_sha256'], 'request_sha256': digest(payload)}
    # Inspect the actual installed worktree before taking its canonical writer.
    # Reconciliation of an already completed effect uses its immutable receipt.
    if not (store.base / '.transaction.json').exists():
        dispatch, _, _, run = _selected(store, context)
        _, observed, _ = _read(dispatch, store, context, command, payload)
        if observed is not None:
            return observed
        profile_file = store.source_root / PROFILE
        profile_sha = wf.file_hash(profile_file)
        clean_profile = wf.admit_profile(store)
        require(wf.file_hash(profile_file) == profile_sha, 'Current child profile changed during verification')
        require(clean_profile == run['admission'], 'Current child admission differs from the original run')
    else:
        clean_profile = None
    with store.lock(local_delivery=owner):
        dispatch, text, state, run = _selected(store, context)
        relative, old, expected = _read(dispatch, store, context, command, payload)
        if old is not None:
            return old
        require(clean_profile is not None and clean_profile == run['admission'],
                'Director child handoff requires the original current admission')
        current = _basis(store, text, state, run, context['task_id'])
        require(current['profile_sha256'] == profile_sha, 'Current child profile changed before handoff')
        marker = run.get(HOLD)
        if command == 'director-question-hold':
            require(not marker and run['stop_reason'] is None and run['phase'] in {'implement', 'validate'},
                    'An unrelated child stop or active hold must remain intact')
            prior = {key: deepcopy(run[key]) for key in ('phase', 'stop_reason', 'next_action')}
            stop = 'Waiting for Director decision ' + context['question_id']
            run[HOLD] = {**current, 'prior': prior, 'stop_reason': stop,
                         **{field: context[field] for field in ('director_run_id', 'question_id', 'attempt_id', 'question_sha256')}}
            run.update(phase='blocked', stop_reason=stop, next_action='Wait for the exact directed answer')
        else:
            _require_hold(run, marker, context, current)
            verify_parent(context, payload['answer'])
            run.update(marker['prior'])
            del run[HOLD]
        evidence = {'schema': 1, 'effect': command, 'context_sha256': digest(context),
                    'request_sha256': digest(payload), 'child_run_id': run['id'], 'task_id': context['task_id'],
                    'workspace_sha256': current['workspace_sha256'], 'recorded_at': wf.now()}
        if command == 'director-question-release':
            evidence['answer'] = payload['answer']
        evidence['receipt_sha256'] = digest(evidence)
        store.expect_unchanged(relative, expected)
        wf.validate_run(run)
        store.save(text, state, {relative: wf.dump(evidence)}, update_navigation=False)
        return evidence
