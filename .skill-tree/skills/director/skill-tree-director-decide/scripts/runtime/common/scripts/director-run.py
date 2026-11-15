"""Coordinate one explicitly authorized Director run and its Manual questions."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from subprocess import TimeoutExpired


DIRECTORY = '.skill-tree/director/runs/'
COMMANDS = {'run-start', 'run-status', 'run-dispatch', 'run-pause', 'run-resume', 'run-cancel',
            'run-complete-assignment', 'decide-open', 'decide-answer'}
EFFECTS = {'intake': 'intake', 'process': 'process', 'start': 'launch'}
SELECTOR = {'objective_id', 'plan_id', 'plan_revision'}
GUARD = {'director_run_id', 'expected_run_sha256'}
START_OPTIONS = {'expected_source_hash', 'base_branch', 'branch', 'worktree', 'remote', 'local_base',
                 'local_base_authorization', 'branch_prefix'}
RECOVERABLE_EFFECT_ERRORS = (ValueError, OSError, TimeoutExpired)


def run_path(run_id):
    D._require(D.WF.valid_id(run_id, 'DR'), 'Select an exact Director run ID')
    return DIRECTORY + run_id.lower() + '.json'


def _host_owner(evidence):
    D._object(evidence, {'actor', 'reference', 'kind'})
    D._require(D._token(evidence['actor']) and D._token(evidence['reference']), 'Actual owner input evidence required')
    D.WF.clarification_evidence({key: evidence[key] for key in ('kind', 'reference')})
    return evidence


def _body(work):
    return {'title': work['title'], 'description': work['description'],
            'expected_behavior': '\n'.join(work['acceptance'])}


def _same_guard(record, expected):
    D._require(D._sha(expected) and record == expected, 'Director run changed since inspection')


def _object_identity(record):
    return {field: record[field] for field in SELECTOR}


def _check_before_deadline(question):
    D._require(datetime.now(timezone.utc) < _deadline(question['deadline']), 'Director question attempt expired')


def _deadline(value):
    D._require(isinstance(value, str), 'Director question requires a UTC deadline')
    when = datetime.fromisoformat(value)
    D._require(when.tzinfo is not None and when.utcoffset().total_seconds() == 0,
               'Director question requires a UTC deadline')
    return when


def _event(run, event, **fields):
    timeline = run.setdefault('timeline', [])
    timeline.append({'sequence': len(timeline) + 1, 'recorded_at': D.WF.now(), 'event': event, **fields})


def _failure_reason(error):
    if isinstance(error, TimeoutExpired):
        return 'process-timeout'
    if isinstance(error, ConnectionError):
        return 'transport-error'
    if isinstance(error, OSError):
        return 'io-error'
    return 'guard-rejected'


def _question_event(run, event, assignment_id, question, **fields):
    identity = {key: question[key] for key in ('question_id', 'attempt_id', 'child_run_id', 'task_id', 'phase')}
    _event(run, event, assignment_id=assignment_id, **identity, **fields)


class DirectorRun:
    def __init__(self, registry, frozen_plan, check_area, current_plan=None, verify_pin=None):
        self.registry = registry
        self.store = registry.store
        self.frozen_plan = frozen_plan
        self.check_area = check_area
        self.current_plan = current_plan or (lambda plan: None)
        self.verify_pin = verify_pin or (lambda pin: False)

    def _load(self, run_id):
        relative = run_path(run_id)
        state, sha = D._read(self.registry.root, relative)
        D._require(isinstance(state, dict) and state.get('schema') == 1 and state.get('director_run_id') == run_id,
                   'Exact Director run is unavailable')
        return relative, state, sha

    def _plan(self, selector, sha):
        plan, actual_sha = self.frozen_plan(selector)
        D._require(D._sha(sha) and actual_sha == sha, 'Exact frozen Director plan changed')
        return plan

    def _plan_for(self, state):
        return self._plan(_object_identity(state), state['plan_sha256'])

    def _assignment(self, state, selection, *, check_current=True):
        plan = self._plan_for(state)
        if check_current:
            self.current_plan(plan)
        D._require(selection in state['assignments'], 'Select one exact in-scope assignment')
        return next(item for item in plan['assignments'] if item['id'] == selection)

    def _write(self, relative, state, sha):
        self.store.expect_unchanged(relative, sha)
        content = D.WF.dump(state)
        self.store.commit({relative: content})
        return D.WF.digest(content.encode())

    def start(self, payload):
        D._object(payload, SELECTOR | {'director_run_id', 'plan_sha256', 'assignment_ids', 'owner', 'authority',
                                      'approved_defaults'}, {'process_spec_sha256'})
        owner = _host_owner(payload['owner'])
        relative = run_path(payload['director_run_id'])
        plan = self._plan(_object_identity(payload), payload['plan_sha256'])
        chosen = D._tokens(payload['assignment_ids'], 'Director assignment IDs')
        assignments = {item['id']: item for item in plan['assignments']}
        D._require(chosen and set(chosen) <= assignments.keys() and isinstance(payload['authority'], dict)
                   and set(payload['authority']) == set(chosen), 'Director launch requires exact selected scope and authority')
        D._require(all(set(assignments[aid]['depends_on']) <= set(chosen) for aid in chosen),
                   'Director launch requires the complete selected dependency scope')
        authority = {}
        for name in chosen:
            authority[name] = D._tokens(payload['authority'][name], 'Director run effects')
            D._require(set(authority[name]) <= set(assignments[name]['effects']).intersection(EFFECTS.values()),
                       'Director launch authority exceeds the selected assignment scope')
        defaults = self._defaults(payload['approved_defaults'], chosen, assignments)
        process_specs = payload.get('process_spec_sha256', {})
        D._require(isinstance(process_specs, dict) and set(process_specs) == {name for name in chosen if 'process' in authority[name]}
                   and all(D._sha(digest) for digest in process_specs.values()),
                   'Each authorized process effect requires one exact owner-approved task specification digest')
        operation = {'kind': 'director-run-start', 'run_id': payload['director_run_id'], 'sha256': D._digest(payload)}
        self.current_plan(plan)
        for name in chosen:
            self.check_area(assignments[name])
        with self.store.lock(local_delivery=operation):
            old, old_sha = D._read(self.registry.root, relative)
            if old is not None:
                D._require(old['start_sha256'] == operation['sha256'], 'Director run already owns a different launch')
                return self._view(old, old_sha, plan)
            # One Director run owns one exact plan and assignment dispatch identity.
            directory = D._safe_path(self.registry.root, DIRECTORY.rstrip('/'))
            for p in directory.glob('dr-*.json'):
                record, _ = D._read(self.registry.root, DIRECTORY + p.name)
                D._require(record['plan_sha256'] != payload['plan_sha256']
                           or not set(chosen).intersection(record['assignments']),
                           'A selected assignment already owns a Director run for this plan')
            state = {**_object_identity(payload), 'schema': 1, 'phase': 'running', 'owner': owner,
                     'director_run_id': payload['director_run_id'], 'director_id': plan['director_id'],
                     'plan_sha256': payload['plan_sha256'], 'authority': authority, 'approved_defaults': defaults,
                     'process_spec_sha256': process_specs,
                     'assignments': {aid: {'dispatches': {}, 'questions': {}, 'blocker': None} for aid in chosen},
                     'start_sha256': operation['sha256']}
            _event(state, 'run-started', phase=state['phase'])
            return self._view(state, self._write(relative, state, None), plan)

    def _defaults(self, source, chosen, assignments):
        D._require(isinstance(source, list), 'Approved defaults require exact source pin references')
        result = {}
        for item in source:
            D._object(item, {'assignment_id', 'key', 'choice', 'pin'})
            name, key = item['assignment_id'], item['key']
            D._require(name in chosen and D._token(key) and D._token(item['choice']), 'Default lies outside selected scope')
            pin = item['pin']
            D._require(pin in assignments[name]['pins'] and pin.get('status') == 'verified',
                       'Default requires an exact previously accepted fact pin')
            values = result.setdefault(name, {})
            D._require(key not in values, 'Duplicate approved default')
            values[key] = item
        return result

    def _view(self, state, sha, plan):
        status = {}
        for spec in plan['assignments']:
            name = spec['id']
            if name not in state['assignments']:
                continue
            current = state['assignments'][name]
            waits = [question for question in current['questions'].values() if question['phase'] != 'delivered']
            deps = [aid for aid in spec['depends_on'] if not state['assignments'][aid].get('completed')]
            operations = current['dispatches']
            task = spec['child'].get('task_id', '')
            effect = None
            reserved = {resource for item in plan['assignments'] if item['id'] != name and
                        item['id'] in state['assignments'] and not state['assignments'][item['id']].get('completed')
                        and state['assignments'][item['id']]['dispatches'].get('start')
                        for resource in item['resources']}
            resource_waits = sorted(reserved.intersection(spec['resources']))
            recorded = {operation for operation, entry in operations.items() if entry['status'] == 'recorded'}
            can_process = task.startswith('P-') or (not task and 'intake' in recorded)
            can_start = task.startswith('T-') or 'process' in recorded
            for operation, prerequisite in (('intake', not task), ('process', can_process), ('start', can_start)):
                if (prerequisite and EFFECTS[operation] in state['authority'][name]
                        and operations.get(operation, {}).get('status') != 'recorded'):
                    effect = operation
                    break
            status[name] = {**deepcopy(current), 'waiting': bool(waits), 'dependencies': deps,
                            'resource_waits': resource_waits,
                            'next': effect if state['phase'] == 'running' and not (waits or deps or current['blocker']
                                                                                or current.get('completed')
                                                                                or (effect == 'start' and resource_waits)) else None}
        return {'director_run_id': state['director_run_id'], 'plan_sha256': state['plan_sha256'], 'phase': state['phase'],
                'run_sha256': sha, 'assignments': status}

    def status(self, payload):
        D._object(payload, {'director_run_id'})
        _, state, sha = self._load(payload['director_run_id'])
        return self._view(state, sha, self._plan_for(state))

    def lifecycle(self, command, payload):
        D._object(payload, GUARD)
        target = {'run-pause': 'paused', 'run-resume': 'running', 'run-cancel': 'cancelled'}[command]
        owner = {'kind': command, 'sha256': D._digest(payload)}
        with self.store.lock(local_delivery=owner):
            relative, state, sha = self._load(payload['director_run_id'])
            _same_guard(sha, payload['expected_run_sha256'])
            D._require(state['phase'] != 'cancelled' and (target != 'running' or state['phase'] == 'paused'),
                       'Director run is not in a resumable phase')
            plan = self._plan_for(state)
            if target == 'running':
                self.current_plan(plan)
            if state['phase'] == target:
                return self._view(state, sha, plan)
            state['phase'] = target
            event = {'run-pause': 'run-paused', 'run-resume': 'run-resumed', 'run-cancel': 'run-cancelled'}[command]
            _event(state, event, phase=target)
            return self._view(state, self._write(relative, state, sha), plan)

    def _envelope(self, state, assignment):
        return {'schema': 1, 'director_id': state['director_id'], 'assignment_id': assignment['id'],
                'queue_id': assignment['area']['queue_id'], 'plan_sha256': state['plan_sha256']}

    def _check_resources(self, spec, child):
        requested = set(spec['resources'])
        if not requested:
            return
        _, bindings, _ = self.registry._load()
        roots = {Path(binding['root']) for binding in (bindings or {}).get('queues', {}).values()} | {child.root}
        for root in roots:
            state = D.WF.Store(root, route_queue=False, neutral=True).load()
            claims = state.get('run_registry', {}).get('resources', {})
            D._require(not requested.intersection(claims), 'A requested exclusive child resource is already claimed')

    def _child_task(self, spec, record, operation):
        if operation == 'intake':
            return None
        pinned = spec['child'].get('task_id', '')
        if operation == 'process':
            return pinned if pinned.startswith('P-') else record['dispatches']['intake']['result']['id']
        return pinned if pinned.startswith('T-') else record['dispatches']['process']['result']['created_ids'][0]

    def _scope_processed_task(self, item, spec, expected):
        D._object(item, {'title', 'body', 'parent_pending_ids'}, {'priority'})
        D._require(D._digest({key: item[key] for key in item if key != 'parent_pending_ids'}) == expected,
                   'The promoted child specification differs from the owner-approved body')
        body = item['body']
        D._require(isinstance(body, str), 'The approved task specification requires a text body')
        allowed = [D._scope(spec['area']['scope']) / D._scope(path) for path in spec['write_paths']]
        pinned = {D._scope(pin['path']) for pin in spec['pins'] if 'path' in pin}
        def within(path):
            return any(path.is_relative_to(parent) for parent in allowed)
        touch = [line[2:].strip().strip('`') for line in D.WF.section_body(body, 'Touch').splitlines() if line.strip()]
        touch_lines = [line for line in D.WF.section_body(body, 'Touch').splitlines() if line.strip()]
        D._require(touch and all(line.startswith('- ') for line in touch_lines) and all(within(D._scope(path)) for path in touch),
                   'Promoted task touches a path outside the frozen assignment scope')
        checks = D.WF.check_specs({'body': body})
        D._require({check['id'] for check in checks} == {spec['check']} and all(
            within(D._scope(path)) or D._scope(path) in pinned for check in checks for path in check['sources']),
                   'Promoted task checks a source outside the frozen assignment scope')

    def _dispatch_request(self, operation, requested, spec, record, child, original_exists, process_sha):
        D._require(isinstance(requested, dict) and D._sha(requested.get('expected_source_hash')), 'Dispatch requires the inspected child queue digest')
        child_id = self._child_task(spec, record, operation)
        if operation == 'intake':
            D._object(requested, {'expected_source_hash'})
            D._require('task_id' not in spec['child'], 'The frozen assignment already owns an existing child task')
            return {**requested, **_body(spec['child'])}, None
        candidate = next((task for task in D.WF.parse(child.text()) if task['id'] == child_id), None)
        if not original_exists:
            D._require(candidate is not None, 'The exact selected child task is unavailable')
            if child_id == spec['child'].get('task_id'):
                expected_task = spec['child']['body_sha256']
            elif operation == 'start':
                expected_task = record['dispatches']['process']['result']['task_sha256']
            else:
                expected_task = record['dispatches']['intake']['result']['task_sha256']
            D._require(D.WF.digest(candidate['body'].encode()) == expected_task, 'The exact child task definition changed')
        if operation == 'process':
            D._object(requested, {'expected_source_hash', 'selectors', 'dispositions', 'tasks'})
            D._require(requested['selectors'] == [child_id] and set(requested['dispositions']) == {child_id}
                       and requested['dispositions'][child_id].get('status') == 'promoted'
                       and isinstance(requested['tasks'], list) and len(requested['tasks']) == 1,
                       'Director processes exactly one selected child task')
            item = requested['tasks'][0]
            D._require(isinstance(item, dict) and item.get('parent_pending_ids') == [child_id],
                       'Director process cannot expand assignment scope')
            self._scope_processed_task(item, spec, process_sha)
            return requested, None
        D._require(spec['workspace'] == 'recorded-worktree' and set(requested) <= START_OPTIONS,
                   'Directed start requires the planned owned worktree and bounded launch options')
        if candidate is not None:
            D._require(not candidate['depends_on'], 'Child start requires separate review of dependencies outside the exact assignment')
        return requested, {'mode': 'next', 'selector': child_id, 'limits': None}

    def dispatch(self, payload):
        D._object(payload, GUARD | {'assignment_id', 'operation', 'request'})
        operation = payload['operation']
        D._require(operation in EFFECTS, 'Director run dispatch does not grant the requested effect')
        run_id, name = payload['director_run_id'], payload['assignment_id']
        rel, before, sha = self._load(run_id)
        spec = self._assignment(before, name)
        child = D.WF.Store(self.check_area(spec), neutral=True)
        helper = D.WF.director_dispatch_helper()
        existing = before['assignments'][name]['dispatches'].get(operation)
        envelope = self._envelope(before, spec)
        observed = helper.observe(child, {'operation': operation, 'director_dispatch': envelope})
        recovering = observed['receipt'] is not None
        if existing and existing['status'] == 'recorded':
            D._require(observed['receipt'] is not None and observed['receipt']['receipt_sha256'] == existing['receipt_sha256'],
                       'Original directed child result became unavailable or changed')
            D._require(existing['request_sha256'] == D._digest({key: val for key, val in payload['request'].items()
                                                                if key != 'expected_source_hash'}),
                       'Director dispatch request differs from the original')
            return {'status': 'replayed', 'result': observed['observed_result'], 'run_sha256': sha}
        D._require(before['phase'] == 'running' and EFFECTS[operation] in before['authority'][name],
                   'Director run lacks current exact execution authority for this effect')
        if operation == 'start' and observed['receipt'] is None:
            self._check_resources(spec, child)
        eligible = self._view(before, sha, self._plan_for(before))['assignments'][name]
        D._require(eligible['next'] == operation, 'The assignment is not eligible for this exact effect')
        request, start = self._dispatch_request(operation, payload['request'], spec, before['assignments'][name], child,
                                                observed['receipt'] is not None, before['process_spec_sha256'].get(name))
        request = {**request, 'director_dispatch': envelope}
        effect_sha = D._digest({key: value for key, value in payload['request'].items() if key != 'expected_source_hash'})
        effect = {'kind': 'director-run-dispatch', 'run_id': run_id, 'assignment_id': name,
                  'operation': operation, 'sha256': effect_sha}
        directed = helper.ChildDispatch(operation, request, start)
        with self.store.lock(local_delivery=effect):
            rel, current, current_sha = self._load(run_id)
            _same_guard(current_sha, sha)
            if existing is None:
                _same_guard(current_sha, payload['expected_run_sha256'])
                current['assignments'][name]['dispatches'][operation] = {'status': 'prepared', 'request_sha256': effect_sha,
                                                                        'semantic_sha256': directed.semantic_sha256,
                                                                        'failure_key': None, 'failures': 0}
                _event(current, 'dispatch-prepared', assignment_id=name, operation=operation)
                self._write(rel, current, current_sha)
            else:
                D._require(existing['semantic_sha256'] == directed.semantic_sha256, 'The original in-flight dispatch changed')
        try:
            helper.retain_intent(D.WF.Store(self.registry.root, route_queue=False, neutral=True), operation, request, start_context=start)
        except RECOVERABLE_EFFECT_ERRORS as error:
            self._dispatch_failure(run_id, name, operation, effect, 'retain-intent', error)
            raise
        if not recovering:
            with self.store.lock(local_delivery=effect):
                rel, current, current_sha = self._load(run_id)
                D._require(current['phase'] == 'running', 'Paused or cancelled Director run cannot dispatch a new effect')
                pending = current['assignments'][name]['dispatches'][operation]
                D._require(pending['semantic_sha256'] == directed.semantic_sha256, 'The prepared effect changed')
                if pending['status'] in {'prepared', 'invoking'}:
                    pending['status'] = 'invoking'
                    _event(current, 'dispatch-invoking', assignment_id=name, operation=operation)
                    self._write(rel, current, current_sha)
        stage = 'observe-child' if recovering else 'invoke-child'
        try:
            if recovering:
                D._require(observed['receipt']['semantic_sha256'] == directed.semantic_sha256, 'The recorded child dispatch differs from the authorized request')
            else:
                helper.apply(child, {'operation': operation, 'request': request,
                                     **({'start': start} if start is not None else {})})
            stage = 'observe-child'
            observed = helper.observe(D.WF.Store(child.root, neutral=True), {'operation': operation, 'director_dispatch': envelope})
            D._require(observed['receipt'] is not None and observed['receipt']['semantic_sha256'] == directed.semantic_sha256,
                       'Child effect lacks the original exact acknowledgement')
            stage = 'reconcile-child-task'
            result = observed['observed_result']
            result_ids = {key: result[key] for key in ('id', 'created_ids', 'workspace_state') if key in result}
            if operation in {'intake', 'process'}:
                created = result['id'] if operation == 'intake' else result['created_ids'][0]
                current_child = D.WF.Store(child.root, neutral=True)
                task = next((candidate for candidate in D.WF.parse(current_child.text()) if candidate['id'] == created), None)
                D._require(task is not None, 'Original dispatched child task requires reconciliation')
                if operation == 'process':
                    expected_body = request['tasks'][0]['body'].strip()
                    actual = D.WF.clarification_semantics(task)
                    baseline = D.WF.clarification_semantics({**task, 'body': expected_body})
                    D._require(task['title'] == request['tasks'][0]['title'] and actual == baseline,
                               'The dispatched task differs from the approved processed specification')
                result_ids['task_sha256'] = D.WF.digest(task['body'].encode())
        except RECOVERABLE_EFFECT_ERRORS as error:
            self._dispatch_failure(run_id, name, operation, effect, stage, error)
            raise
        with self.store.lock(local_delivery=effect):
            rel, current, current_sha = self._load(run_id)
            pending = current['assignments'][name]['dispatches'][operation]
            D._require(pending['semantic_sha256'] == directed.semantic_sha256, 'Director intent changed before finalization')
            if pending['status'] != 'recorded':
                receipt = observed['receipt']['receipt_sha256']
                pending.update(status='recorded', receipt_sha256=receipt, result=result_ids)
                if operation == 'intake':
                    child_ids = {'pending_id': result['id']}
                elif operation == 'process':
                    child_ids = {'pending_id': request['selectors'][0], 'processing_run_id': result['id'],
                                 'task_id': result['created_ids'][0]}
                else:
                    child_ids = {'task_id': start['selector'], 'child_run_id': result['id']}
                _event(current, 'dispatch-recorded', assignment_id=name, operation=operation, receipt_sha256=receipt,
                       stage='recover-child-receipt' if recovering else 'acknowledge-child', **child_ids)
                current_sha = self._write(rel, current, current_sha)
            return {'status': 'recorded', 'result': result, 'run_sha256': current_sha}

    def complete_assignment(self, payload):
        D._object(payload, GUARD | {'assignment_id', 'outcome_id'})
        run_id, name = payload['director_run_id'], payload['assignment_id']
        _, state, sha = self._load(run_id)
        _same_guard(sha, payload['expected_run_sha256'])
        spec = self._assignment(state, name)
        assignment = state['assignments'][name]
        D._require(state['phase'] == 'running' and not any(q['phase'] != 'delivered' for q in assignment['questions'].values()),
                   'Resolve the assignment before recording completion')
        D._require(D.WF.valid_id(payload['outcome_id'], 'O'), 'Completion requires an exact child outcome ID')
        root = self.check_area(spec)
        child = D.WF.Store(root, neutral=True)
        observed = D.WF.director_dispatch_helper().observe(child, {'operation': 'start', 'director_dispatch': self._envelope(state, spec)})
        recorded = assignment['dispatches'].get('start', {})
        actual = observed['observed_result']
        task_id = self._child_task(spec, assignment, 'start')
        D._require(recorded.get('status') == 'recorded' and observed['receipt'] is not None
                   and recorded['receipt_sha256'] == observed['receipt']['receipt_sha256']
                   and actual['id'] == recorded['result']['id'] and actual['phase'] == 'completed'
                   and actual.get('completion_refs', {}).get(task_id) == payload['outcome_id'],
                   'Completion requires the current exact terminal child run and outcome')
        matches = [entry for entry in child.outcomes() if (entry.get('id'), entry.get('task_id'), entry.get('run_id'))
                   == (payload['outcome_id'], task_id, actual['id']) and entry.get('disposition') == 'completed']
        D._require(len(matches) == 1, 'Actual completed child outcome is unavailable')
        check = [entry['result'] for entry in matches[0].get('check_results', [])
                 if entry.get('check', {}).get('id') == spec['check'] and entry.get('result', {}).get('result') == 'pass']
        D._require(len(check) == 1 and check[0].get('evidence'), 'The assignment check lacks passing child evidence')
        evidence_store = D.WF.Store(root, run_id=actual['id'])
        D.WS.ensure_workspace(evidence_store, actual)
        D._require(all(D.WF.evidence_pointer(evidence_store, item)['available'] for item in check[0]['evidence'])
                   and check[0].get('sources') and D.WF.fingerprints(evidence_store, list(check[0]['sources'])) == check[0]['sources'],
                   'The matching child check evidence is no longer current')
        completed = {'outcome_id': payload['outcome_id'], 'task_id': task_id, 'child_run_id': actual['id'],
                     'outcome_sha256': D._digest(matches[0]), 'check_key': check[0]['key']}
        with self.store.lock(local_delivery={'kind': 'director-run-assignment-complete', 'sha256': D._digest(payload)}):
            rel, state, sha = self._load(run_id)
            _same_guard(sha, payload['expected_run_sha256'])
            target = state['assignments'][name]
            previous = target.get('completed')
            D._require(previous is None or previous == completed, 'Child completion identity changed')
            if previous is None:
                target['completed'] = completed
                _event(state, 'assignment-completed', assignment_id=name, child_run_id=actual['id'],
                       task_id=task_id, outcome_id=payload['outcome_id'])
                sha = self._write(rel, state, sha)
            return {'status': 'completed', 'receipt': completed, 'run_sha256': sha}

    def _dispatch_failure(self, run_id, assignment, operation, effect, stage, error):
        with self.store.lock(local_delivery=effect):
            rel, state, sha = self._load(run_id)
            current = state['assignments'][assignment]
            pending = current['dispatches'][operation]
            if pending['status'] == 'recorded':
                return
            failure = {}
            if stage in {'invoke-child', 'observe-child'} and isinstance(error, ValueError):
                failure_key = D._digest({'error': str(error), 'type': type(error).__name__})
                count = pending['failures'] + 1 if pending['failure_key'] == failure_key else 1
                failure = {'failure_key': failure_key, 'failures': count}
                pending.update(failure)
                if count >= 2:
                    current['blocker'] = 'The same child dispatch failure repeated. Reconcile the original effect before choosing a next action.'
            _event(state, 'dispatch-failed', assignment_id=assignment, operation=operation,
                   stage=stage, reason=_failure_reason(error), **failure)
            self._write(rel, state, sha)

    def _question_context(self, state, spec, question):
        fields = ('question_id', 'attempt_id', 'child_run_id', 'task_id', 'start_receipt_sha256', 'question_sha256')
        return {**{key: question[key] for key in fields}, 'director_run_id': state['director_run_id'],
                'director_dispatch': self._envelope(state, spec)}

    def _verify_parent_answer(self, context, answer):
        _, state, _ = self._load(context['director_run_id'])
        name = context['director_dispatch']['assignment_id']
        spec = self._assignment(state, name)
        question = state['assignments'][name]['questions'].get(context['question_id'])
        D._require(state['phase'] == 'running' and question and question['phase'] == 'answer-recorded'
                   and question['answer'] == answer and self._question_context(state, spec, question) == context,
                   'Exact durable parent answer or current Director authority is unavailable')

    def _question_call(self, root, context, command, answer=None):
        store = D.WF.Store(root, run_id=context['child_run_id'])
        return QUESTIONS.handle(store, command, {**context, **({'answer': answer} if answer is not None else {})},
                                verify_parent=self._verify_parent_answer)

    def _question_handoff(self, state, spec, question, root, command, answer=None):
        context = self._question_context(state, spec, question)
        try:
            return self._question_call(root, context, command, answer)
        except RECOVERABLE_EFFECT_ERRORS as error:
            phase, stage = {'director-question-hold': ('preparing', 'hold-child'),
                            'director-question-release': ('answer-recorded', 'release-child')}[command]
            effect = {'kind': command, 'question_sha256': context['question_sha256']}
            with self.store.lock(local_delivery=effect):
                relative, latest, sha = self._load(context['director_run_id'])
                current = latest['assignments'][spec['id']]['questions'][context['question_id']]
                if current['question_sha256'] == question['question_sha256'] and current['phase'] == phase:
                    _question_event(latest, 'question-failed', spec['id'], current, stage=stage, reason=_failure_reason(error))
                    self._write(relative, latest, sha)
            raise

    def open_question(self, payload):
        fields = {'assignment_id', 'question_id', 'attempt_id', 'child_run_id', 'task_id', 'start_receipt_sha256',
                  'recipient', 'requester', 'key', 'options', 'recommendation', 'affected_areas', 'blocked_action', 'deadline'}
        D._object(payload, GUARD | fields)
        question = {key: payload[key] for key in fields}
        for key, kind in (('question_id', 'DQ'), ('attempt_id', 'DA'), ('child_run_id', 'WR'), ('task_id', 'T')):
            D._require(D.WF.valid_id(question[key], kind), 'Use the exact question, attempt and child identities')
        option_ids = self._option_ids(question['options'])
        D._require(question['recommendation'] in option_ids and all(D._token(question[key]) for key in ('recipient', 'requester', 'key'))
                   and D._sha(question['start_receipt_sha256']) and isinstance(question['blocked_action'], str)
                   and question['blocked_action'].strip(), 'Question requires options, recommendation and exact scope')
        affected = D._tokens(question['affected_areas'], 'Question affected areas')
        run_id, name, qid = (payload[key] for key in ('director_run_id', 'assignment_id', 'question_id'))
        rel, state, sha = self._load(run_id)
        spec = self._assignment(state, name)
        root = self.check_area(spec)
        D._require(state['phase'] == 'running' and state['owner']['actor'] == question['recipient'],
                   'A running Director session requires the original owner recipient')
        known_areas = {item['area']['id'] for item in self._plan_for(state)['assignments'] if item['id'] in state['assignments']}
        D._require(spec['area']['id'] in affected and set(affected) <= known_areas, 'Question affects an area outside the selected scope')
        assignment = state['assignments'][name]
        launched = assignment['dispatches'].get('start', {})
        D._require(launched.get('status') == 'recorded' and launched['receipt_sha256'] == question['start_receipt_sha256']
                   and launched['result']['id'] == question['child_run_id'] and question['task_id'] == self._child_task(spec, assignment, 'start'),
                   'Question requires the original exact child start receipt and task')
        context = {'plan_sha256': state['plan_sha256'], 'authority_ref': spec['authority_ref'],
                   'director_run_id': run_id, **question}
        question['question_sha256'] = D._digest(context)
        found = assignment['questions'].get(qid)
        if found:
            D._require(found['question_sha256'] == question['question_sha256'], 'The question already owns a different attempt')
            if found['phase'] == 'waiting' and found.get('default') and self.verify_pin(found['default']['pin']):
                return self._deliver(run_id, name, qid, sha, spec, root, self._default_answer(state, spec, found['default']))
            if found['phase'] in {'waiting', 'delivered'}:
                return {'status': found['phase'], 'question': found, 'run_sha256': sha, **({'delivery': found['delivery']} if 'delivery' in found else {})}
        else:
            _check_before_deadline(question)
            D._require(all(entry['phase'] == 'delivered' for entry in assignment['questions'].values()),
                       'Resolve the one open question before adding another')
            _same_guard(sha, payload['expected_run_sha256'])
            self._question_call(root, self._question_context(state, spec, question), 'director-question-preflight')
            default = state['approved_defaults'].get(name, {}).get(question['key'])
            if default and (default['choice'] not in option_ids or not self.verify_pin(default['pin'])):
                default = None
            question.update(phase='preparing', authority_ref=spec['authority_ref'], default=default)
            owner = {'kind': 'director-question-open', 'question_sha256': question['question_sha256']}
            with self.store.lock(local_delivery=owner):
                rel, state, sha = self._load(run_id)
                _same_guard(sha, payload['expected_run_sha256'])
                state['assignments'][name]['questions'][qid] = question
                _question_event(state, 'question-prepared', name, question)
                self._write(rel, state, sha)
        hold = self._question_handoff(state, spec, question, root, 'director-question-hold')
        with self.store.lock(local_delivery={'kind': 'director-question-held', 'question_sha256': question['question_sha256']}):
            rel, state, sha = self._load(run_id)
            current = state['assignments'][name]['questions'][qid]
            D._require(current['question_sha256'] == question['question_sha256'], 'Original Director question changed')
            if current['phase'] == 'preparing':
                current.update(phase='waiting', hold=hold)
                _question_event(state, 'question-held', name, current, receipt_sha256=hold['receipt_sha256'])
                sha = self._write(rel, state, sha)
        if current.get('default') and state['phase'] == 'running':
            default = current['default']
            if self.verify_pin(default['pin']):
                return self._deliver(run_id, name, qid, sha, spec, root, self._default_answer(state, spec, default))
        return {'status': current['phase'], 'question': current, 'run_sha256': sha}

    def _default_answer(self, state, spec, default):
        return {'choice': default['choice'], 'origin': 'approved-default', 'actor': state['director_id'],
                'authority_ref': spec['authority_ref'], 'evidence_sha256': D._digest(default['pin'])}

    def _option_ids(self, entries):
        D._require(isinstance(entries, list) and len(entries) >= 2, 'Provide at least two meaningful options')
        ids = set()
        for row in entries:
            D._object(row, {'id', 'label'})
            D._require(D._token(row['id']) and row['id'] not in ids and isinstance(row['label'], str)
                       and row['label'].strip(), 'Question options require distinct IDs and labels')
            ids.add(row['id'])
        return ids

    def answer(self, payload):
        fields = {'assignment_id', 'question_id', 'question_sha256', 'attempt_id', 'child_run_id', 'choice', 'disposition', 'owner'}
        D._object(payload, GUARD | fields)
        run_id, name, qid = (payload[key] for key in ('director_run_id', 'assignment_id', 'question_id'))
        _, state, sha = self._load(run_id)
        spec = self._assignment(state, name)
        root = self.check_area(spec)
        owner = _host_owner(payload['owner'])
        question = state['assignments'][name]['questions'].get(qid)
        D._require(question is not None and all(question[key] == payload[key] for key in
                   ('question_sha256', 'attempt_id', 'child_run_id')),
                   'Use the exact original question, attempt and child run')
        D._require(owner['actor'] == question['recipient'] == state['owner']['actor'],
                   'Answer did not come from the addressed owner recipient')
        if question['phase'] not in {'answer-recorded', 'delivered'}:
            _same_guard(sha, payload['expected_run_sha256'])
            D._require(state['phase'] == 'running', 'Director run must be running before accepting an answer')
            D._require(question['phase'] == 'waiting', 'The exact child hold has not been observed')
            _check_before_deadline(question)
        if payload['disposition'] == 'decline' and payload['choice'] is None:
            D._require(question['phase'] == 'waiting', 'The original question already has an answer')
            return {'status': 'waiting', 'question': question, 'run_sha256': sha}
        D._require(payload['disposition'] == 'answer' and payload['choice'] in self._option_ids(question['options']),
                   'Choose exactly one of the recorded question options')
        answer = {'choice': payload['choice'], 'origin': 'owner', 'actor': owner['actor'],
                  'authority_ref': spec['authority_ref'], 'evidence_sha256': D._digest(owner)}
        return self._deliver(run_id, name, qid, sha, spec, root, answer, owner)

    def _deliver(self, run_id, name, qid, expected, spec, root, answer, owner=None):
        _, inspected, checked = self._load(run_id)
        _same_guard(checked, expected)
        waiting = inspected['assignments'][name]['questions'][qid]
        if waiting['phase'] == 'waiting':
            self._question_call(root, self._question_context(inspected, spec, waiting), 'director-question-check')
        effect = {'kind': 'director-question-answer', 'question_id': qid, 'sha256': D._digest(answer)}
        with self.store.lock(local_delivery=effect):
            rel, state, sha = self._load(run_id)
            _same_guard(sha, expected)
            question = state['assignments'][name]['questions'][qid]
            if question['phase'] in {'answer-recorded', 'delivered'}:
                D._require(question['answer'] == answer, 'The original question already owns a different answer')
                if question['phase'] == 'delivered':
                    return {'status': 'delivered', 'question': question, 'delivery': question['delivery'], 'run_sha256': sha}
                D._require(state['phase'] == 'running', 'Director run must be running before delivering an answer')
            else:
                D._require(state['phase'] == 'running' and question['phase'] == 'waiting', 'The exact question is not waiting in a running Director session')
                _check_before_deadline(question)
                question.update(phase='answer-recorded', answer=answer, answered_at=D.WF.now())
                if owner is not None:
                    question['owner_evidence'] = owner
                _question_event(state, 'answer-recorded', name, question, origin=answer['origin'])
                sha = self._write(rel, state, sha)
        delivery = self._question_handoff(state, spec, question, root, 'director-question-release', answer)
        with self.store.lock(local_delivery=effect):
            rel, state, sha = self._load(run_id)
            question = state['assignments'][name]['questions'][qid]
            D._require(question['answer'] == answer, 'Original Director answer changed before acknowledgement')
            if question['phase'] != 'delivered':
                question.update(phase='delivered', delivery=delivery)
                _question_event(state, 'answer-delivered', name, question,
                                origin=answer['origin'], receipt_sha256=delivery['receipt_sha256'])
                sha = self._write(rel, state, sha)
            return {'status': 'delivered', 'question': question, 'delivery': delivery, 'run_sha256': sha}


def run(registry, planner, command, payload):
    """Production bindings reuse registered plan and canonical owner sources."""
    source_adapter = D.WF.owned_module('director_plan_runtime', Path(__file__).with_name('director-plan-adapters.py'))
    def registered():
        current_registry, bindings, _ = registry._load()
        return current_registry, bindings, source_adapter.PlanSources(D, planner.O, planner.C, current_registry, bindings)

    def check_current(plan):
        ledger, _, _, _ = planner.ledger._load(plan['objective']['objective_id'])
        current = {'revision': plan['objective']['objective_revision'], 'sha256': plan['objective']['objective_sha256']}
        D._require(ledger['current'] == current, 'The frozen Director objective is no longer current')

    def check_area(assignment):
        areas, bindings, sources = registered()
        identity = assignment['area']
        area = areas['areas'].get(identity['id'])
        D._require(area and all(area.get(key) == identity[key] for key in ('id', 'scope', 'repo_id', 'queue_id')),
                   'The planned Director area identity changed')
        D._require(sources.qualify(area, assignment['capability']) == identity['qualification'],
                   'The planned child source, profile or capability qualification changed')
        D._require(set(assignment['effects']) <= set(area['allowed_effects']), 'Registered area effect authority changed')
        for pin in assignment['pins']:
            if pin['strength'] != 'optional':
                D._require(verify_pin(pin), 'A required Director source pin is no longer current')
        return planner.O._child_root(areas, bindings, area['id'])

    def verify_pin(pin):
        areas, _, sources = registered()
        area = areas['areas'].get(pin['area_id'])
        if not area:
            return False
        expected = {key: pin[key] for key in ('revision', 'sha256')}
        observed = sources.pin(area, {key: value for key, value in pin.items() if key != 'status'})
        return observed == {'status': 'verified', **expected}

    engine = DirectorRun(registry, planner.frozen, check_area, check_current, verify_pin)
    methods = {'run-start': engine.start, 'run-status': engine.status, 'run-dispatch': engine.dispatch,
               'run-complete-assignment': engine.complete_assignment,
               'decide-open': engine.open_question, 'decide-answer': engine.answer}
    return methods[command](payload) if command in methods else engine.lifecycle(command, payload)
