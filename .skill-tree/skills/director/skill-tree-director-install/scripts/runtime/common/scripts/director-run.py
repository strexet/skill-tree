"""Coordinate one explicitly authorized Director run and its Manual questions."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import socket
from subprocess import TimeoutExpired
import sys
from time import monotonic, sleep


DIRECTORY = '.skill-tree/director/runs/'
COMMANDS = {'run-start', 'run-status', 'run-dispatch', 'run-pause', 'run-resume', 'run-cancel',
            'run-complete-assignment', 'run-supervise', 'run-advance-all', 'decide-open', 'decide-answer'}
EFFECTS = {'intake': 'intake', 'process': 'process', 'start': 'launch'}
SELECTOR = {'objective_id', 'plan_id', 'plan_revision'}
GUARD = {'director_run_id', 'expected_run_sha256'}
START_OPTIONS = {'expected_source_hash', 'base_branch', 'branch', 'worktree', 'remote', 'local_base',
                 'local_base_authorization', 'branch_prefix'}
RECOVERABLE_EFFECT_ERRORS = (ValueError, OSError, TimeoutExpired)
SUPERVISED_LIVE = {'assigned', 'running', 'stalled'}
COHERENT_WORKER_ACTIONS = {'heartbeat', 'progress', 'submit'}
SUPERVISION_LOCK_WAIT_SECONDS = 5
SUPERVISION_FRONTIER_LIMIT = 16
ATTEMPT_FIELDS = {'unit_id', 'generation', 'actor_id'}
SUPERVISION_ACTIONS = {
    'assign': (ATTEMPT_FIELDS | {'assignment_id', 'role', 'child_run_id', 'task_id'},
               {'parent_unit_id', 'worktree', 'base', 'paths', 'resources', 'depends_on'}),
    'pickup': (ATTEMPT_FIELDS | {'process'}, set()),
    'heartbeat': (ATTEMPT_FIELDS, set()),
    'progress': (ATTEMPT_FIELDS | {'reference'}, set()),
    'wait': (ATTEMPT_FIELDS | {'reason', 'reference'}, set()),
    'sweep': (set(), set()),
    'recover': (ATTEMPT_FIELDS | {'stop_observation'}, set()),
    'submit': (ATTEMPT_FIELDS, {'result'}),
}


def _supervision_identity(value):
    return isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_:/.-]{1,180}', value) is not None


def _supervision_text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 2000


def _supervision_process(process):
    D._object(process, {'pid', 'pgid'})
    pid, pgid = process['pid'], process['pgid']
    D._require(type(pid) is int and type(pgid) is int and 1 < pid == pgid < 2**31
               and pid not in {os.getpid(), os.getpgrp()}, 'Supervision requires a distinct local process group leader')
    if sys.platform == 'darwin':
        import ctypes

        class ProcBsdInfo(ctypes.Structure):
            # macOS proc_info.h, PROC_PIDTBSDINFO. Retain the microsecond birth identity.
            _fields_ = [('identity', ctypes.c_uint32 * 12), ('comm', ctypes.c_char * 16),
                        ('name', ctypes.c_char * 32), ('group', ctypes.c_uint32 * 6),
                        ('started_seconds', ctypes.c_uint64), ('started_microseconds', ctypes.c_uint64)]

        info = ProcBsdInfo()
        read_info = ctypes.CDLL('/usr/lib/libproc.dylib').proc_pidinfo
        read_info.argtypes = (ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int)
        read_info.restype = ctypes.c_int
        size = ctypes.sizeof(info)
        observed = read_info(pid, 3, ctypes.c_uint64(0), ctypes.byref(info), size)
        uid = info.identity[5]
        D._require(observed == size and info.identity[3] == pid and info.group[1] == pgid
                   and uid == os.getuid() and info.started_seconds,
                   'The exact same-user local process group leader is unavailable')
        birth = {'clock': 'darwin-proc-bsdinfo', 'seconds': info.started_seconds, 'microseconds': info.started_microseconds}
    elif sys.platform.startswith('linux'):
        directory = Path('/proc') / str(pid)
        stat = directory / 'stat'
        before = stat.read_text().rpartition(') ')[2].split()
        uid = directory.stat().st_uid
        after = stat.read_text().rpartition(') ')[2].split()
        D._require(len(before) > 19 and len(after) > 19 and before[19] == after[19]
                   and before[2] == after[2] == str(pgid) and uid == os.getuid(),
                   'The exact same-user local process group leader is unavailable')
        birth = {'clock': 'linux-proc-stat', 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                 'ticks': int(after[19])}
    else:
        raise D.DirectorError('Exact local process identity is unavailable on this host')
    return {'pid': pid, 'pgid': pgid, 'uid': uid, 'birth': birth}


def _group_gone(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


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


class ResourceUnavailable(ValueError):
    """A pre-dispatch check found a held resource."""


class DirectorRun:
    def __init__(self, registry, frozen_plan, check_area, current_plan=None, verify_pin=None,
                 superseded_assignments=None):
        self.registry = registry
        self.store = registry.store
        self.frozen_plan = frozen_plan
        self.check_area = check_area
        self.current_plan = current_plan or (lambda plan: None)
        self.verify_pin = verify_pin or (lambda pin: False)
        self.superseded_assignments = superseded_assignments or (lambda selector: {})

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

    def _write(self, relative, state, sha, *, retain_worker_frontier=False):
        supervision = state.get('supervision')
        if isinstance(supervision, dict) and not retain_worker_frontier:
            supervision.pop('worker_frontier', None)
        self.store.expect_unchanged(relative, sha)
        content = D.WF.dump(state)
        self.store.commit({relative: content})
        return D.WF.digest(content.encode())

    def _supervised_payload_digest(self, state):
        policy = {key: value for key, value in state['supervision'].items() if key != 'worker_frontier'}
        return D._digest({**state, 'supervision': policy})

    def _supervised_worker_frontier(self, state, sha):
        frontier = state['supervision'].get('worker_frontier')
        if not isinstance(frontier, dict):
            return []
        digests = frontier.get('digests')
        if (not isinstance(digests, list) or len(digests) > SUPERVISION_FRONTIER_LIMIT
                or not all(D._sha(value) for value in digests)
                or frontier.get('payload_sha256') != self._supervised_payload_digest(state)
                or sha != D.WF.digest(D.WF.dump(state).encode())):
            return []
        return digests

    def start(self, payload):
        D._object(payload, SELECTOR | {'director_run_id', 'plan_sha256', 'assignment_ids', 'owner', 'authority',
                                      'approved_defaults'}, {'process_spec_sha256', 'supervision', 'implement_all'})
        owner = _host_owner(payload['owner'])
        supervision = payload.get('supervision')
        if 'supervision' in payload:
            D._object(supervision, {'host', 'progress_timeout_seconds', 'heartbeat_timeout_seconds'})
            D._require(supervision['host'] == socket.gethostname() and all(type(supervision[key]) is int
                       and 0 < supervision[key] <= 86400 for key in ('progress_timeout_seconds', 'heartbeat_timeout_seconds')),
                       'Supervision requires the actual local host and bounded positive timeouts')
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
        old, old_sha = D._read(self.registry.root, relative)
        if old is not None:
            D._require(old['start_sha256'] == operation['sha256'], 'Director run already owns a different launch')
            return self._view(old, old_sha, plan)
        self.current_plan(plan)
        for name in chosen:
            self.check_area(assignments[name])
        managed = self._freeze_managed_scope(payload['implement_all'], assignments, chosen, authority) if 'implement_all' in payload else None
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
            if managed is not None:
                state['implement_all'] = managed
            if supervision:
                state['supervision'] = {**supervision, 'units': {}, 'requests': {}}
            _event(state, 'run-started', phase=state['phase'])
            return self._view(state, self._write(relative, state, None), plan)

    def _freeze_managed_scope(self, options, assignments, chosen, authority):
        D._object(options, {'expected_source_hash', 'workers'}, {'snapshot_ids'})
        workers = options['workers']
        D._require(type(workers) is int and workers > 0 and D._sha(options['expected_source_hash']),
                   'Implement All requires a positive worker limit and the inspected queue digest')
        selected = {key: assignments[key] for key in chosen}
        owners = {self.check_area(spec) for spec in selected.values()}
        D._require(len(owners) == 1 and len({spec['area']['queue_id'] for spec in selected.values()}) == 1,
                   'Managed Implement All requires one canonical project queue')
        root = owners.pop()
        child = D.WF.Store(root, neutral=True)
        text = child.text()
        D._require(D.WF.digest(text.encode()) == options['expected_source_hash'],
                   'The inspected Implement All queue has changed')
        prioritized = {task['id']: task for task in D.WF.parse(text) if task['queue'] == 'Prioritized Next Changes'}
        roots = options.get('snapshot_ids', list(prioritized))
        D._require(isinstance(roots, list) and roots and all(isinstance(tid, str) for tid in roots)
                   and len(set(roots)) == len(roots) and set(roots) <= prioritized.keys(),
                   'Implement All roots must be exact prioritized tasks')
        roots = sorted(roots, key=lambda tid: (-prioritized[tid]['priority'], prioritized[tid]['line']))
        closure = D.WF.dependency_scope(prioritized.values(), {'snapshot': roots})
        task_assignments = {spec['child'].get('task_id'): key for key, spec in selected.items()}
        D._require(len(task_assignments) == len(selected) and set(task_assignments) == closure & prioritized.keys(),
                   'The frozen Director assignment set differs from the required Implement All tasks')
        previous = {outcome['task_id']: outcome for outcome in child.outcomes() if outcome['disposition'] == 'completed'}
        D._require(closure - prioritized.keys() <= previous.keys(),
                   'Implement All has dependencies without canonical completion evidence')
        for task_id, key in task_assignments.items():
            task, spec = prioritized[task_id], selected[key]
            needs = {task_assignments[tid] for tid in task['depends_on'] if tid in task_assignments}
            D._require(needs <= set(spec['depends_on']) and authority[key] == ['launch']
                       and spec['workspace'] == 'recorded-worktree'
                       and spec['child']['body_sha256'] == D.WF.digest(task['body'].encode()),
                       'A managed assignment must authorize the exact task and preserve the Core dependency edges')
        target = D.WS.checked_out_branch(root)
        D._require(all(spec['area']['qualification']['head'] == target['head'] for spec in selected.values()),
                   'The original managed target moved after plan qualification')
        return {'snapshot_ids': roots, 'required_ids': sorted(closure), 'task_assignments': task_assignments,
                'target': target, 'workers': workers,
                'remaining_ids': sorted(task_assignments), 'frontier': {}}

    def _managed_incorporation(self, state, root):
        managed = state['implement_all']
        original = managed['target']
        current = D.WS.checked_out_branch(root)
        D._require((current['ref'], current['checkout']) == (original['ref'], original['checkout']),
                   'The managed Implement All target checkout or branch changed')
        child = D.WF.Store(root, neutral=True)
        runs = child.load()['run_registry']['runs']
        outcomes = {record['id']: record for record in child.outcomes()}
        steps = {}
        for name, entry in state['assignments'].items():
            accepted = entry.get('completed')
            if not accepted:
                continue
            result = runs.get(accepted['child_run_id'], {})
            if result.get('delivery', {}).get('status') != 'merged':
                continue
            outcome = outcomes.get(accepted['outcome_id'])
            D._require(outcome and D._digest(outcome) == accepted['outcome_sha256']
                       and outcome['task_id'] == accepted['task_id'] and outcome['run_id'] == result['id']
                       and result.get('completion_refs', {}).get(accepted['task_id']) == outcome['id'],
                       'The exact accepted child outcome has changed')
            scope = D.WF.cleanup_delivery_scope(child, result)
            commit = scope['merge_commit']
            parents = D.WS.local_git_text(root, 'show', '-s', '--format=%P', commit).split()
            D._require(scope['target_ref'] == original['ref'] and len(parents) == 2
                       and parents[1] == scope['source_head'] and commit not in steps,
                       'Managed integration does not match an original checked child result')
            steps[commit] = (parents[0], name)
        integrated = set()
        cursor = current['head']
        while cursor != original['head']:
            D._require(cursor in steps, 'Target advanced outside the checked Implement All child receipts')
            cursor, name = steps[cursor]
            integrated.add(name)
        D._require(len(integrated) == len(steps), 'A checked managed child is outside the current target history')
        return current['head'], integrated, child, runs

    def _area_for_run(self, state, spec):
        if 'implement_all' not in state:
            return self.check_area(spec)
        return self.check_area(spec, approved_head=lambda root: self._managed_incorporation(state, root)[0])

    @staticmethod
    def _managed_assignment_paths(spec, child, task):
        owned = [Path(spec['area']['scope']) / relative for relative in spec['write_paths']]
        if task is not None:
            preview = D.WF.owned_module('director_ready_preview', Path(__file__).with_name('parallel-preview.py'))
            declared = [Path(relative) for relative in preview.touch_paths(child.source_root, task)]
            D._require(all(any(relative.is_relative_to(scope) for scope in owned) for relative in declared)
                       and all(any(scope.is_relative_to(relative) for relative in declared) for scope in owned),
                       'Managed task Touch differs from the frozen assignment write scope: ' + task['id'])
        return owned

    def _advance_managed_frontier(self, state, plan, *, resource_holds=None):
        resource_holds = resource_holds or {}
        managed = state['implement_all']
        specs = {spec['id']: spec for spec in plan['assignments'] if spec['id'] in state['assignments']}
        root = self._area_for_run(state, next(iter(specs.values())))
        child = D.WF.Store(root, neutral=True)
        preview = D.WF.owned_module('director_ready_preview', Path(__file__).with_name('parallel-preview.py'))
        snapshot = preview.snapshot(child)
        _, integrated, _, child_runs = self._managed_incorporation(state, root)
        remaining = [tid for tid, name in managed['task_assignments'].items() if name not in integrated]
        status = self._view(state, '', plan)['assignments']
        holds, candidates, retry, occupied = {}, [], [], 0
        for task_id in remaining:
            name = managed['task_assignments'][task_id]
            assignment = status[name]
            launch = assignment['dispatches'].get('start')
            if launch:
                if launch['status'] == 'recorded':
                    run = child_runs.get(launch['result']['id'], {})
                    local_wait = assignment['waiting'] or run.get('phase') in {'blocked', 'paused', 'waiting'}
                    live = any(unit['assignment_id'] == name and self._current_attempt(unit)['status'] in SUPERVISED_LIVE
                               for unit in state.get('supervision', {}).get('units', {}).values())
                    if not assignment.get('completed') and (live or not local_wait):
                        occupied += 1
                    holds[task_id] = 'awaiting-checked-incorporation' if assignment.get('completed') else 'child-held' if local_wait else 'child-running'
                else:
                    occupied += 1
                    if assignment['next'] == 'start':
                        retry.append(name)
                    else:
                        holds[task_id] = 'original-dispatch-unresolved'
                continue
            if assignment['next'] != 'start':
                holds[task_id] = {'reason': 'director-hold', 'dependencies': assignment['dependencies'],
                                  'resources': assignment['resource_waits'], 'blocker': assignment['blocker']}
            elif set(specs[name]['depends_on']) - integrated:
                holds[task_id] = 'predecessor-incorporation-required'
            elif task_id in resource_holds:
                holds[task_id] = resource_holds[task_id]
            else:
                candidates.append(task_id)
        free = managed['workers'] - occupied
        ready = []
        if candidates and free > 0:
            available = {task['id']: task for task in D.WF.parse(child.text()) if task['queue'] == 'Prioritized Next Changes'}
            for missing in set(candidates) - available.keys():
                holds[missing] = 'original-task-unavailable'
            candidates = [tid for tid in candidates if tid in available]
            if candidates:
                for tid in candidates:
                    name = managed['task_assignments'][tid]
                    try:
                        self._managed_assignment_paths(specs[name], child, available[tid])
                        self._check_resources(specs[name], child)
                    except (ValueError, OSError) as error:
                        holds[tid] = str(error)
                admissible = [tid for tid in candidates if tid not in holds]
                if admissible:
                    declared = {tid: specs[name]['resources'] for tid, name in managed['task_assignments'].items()}
                    planned = preview.preview(child, free, admissible, declared_resources=declared)
                    ready = [managed['task_assignments'][tid] for tid in planned['selected_ids']]
                    D._require(planned['snapshot'] == snapshot, 'Managed batch inputs changed during selection')
                    holds.update({row['id']: row['reasons'] for row in planned['deferred']})
        elif candidates:
            holds.update({task_id: 'worker-limit' for task_id in candidates})
        D._require(preview.snapshot(child) == snapshot, 'Managed batch inputs changed during selection')
        guard = {key: snapshot[key] for key in ('queue_sha256', 'state_sha256', 'outcomes_sha256')}
        return remaining, holds, retry + ready, guard

    def advance_all(self, payload):
        D._object(payload, GUARD)
        run_id = payload['director_run_id']
        relative, state, sha = self._load(run_id)
        _same_guard(sha, payload['expected_run_sha256'])
        D._require('implement_all' in state and state['phase'] in {'running', 'completed'},
                   'Select the current running managed Implement All controller')
        plan = self._plan_for(state)
        launches, resource_holds = [], {}
        remaining = state['implement_all']['remaining_ids']
        holds = state['implement_all']['frontier']
        gate = None
        try:
            self.current_plan(plan)
            remaining, holds, eligible, guard = self._advance_managed_frontier(state, plan)
            attempted = set()
            while eligible:
                name = next((candidate for candidate in eligible if candidate not in attempted), None)
                if name is None:
                    break
                attempted.add(name)
                target = state['implement_all']['target']['ref'].removeprefix('refs/heads/')
                request = {'expected_source_hash': guard['queue_sha256'], 'base_branch': target,
                           'local_base': True, 'local_base_authorization': state['owner']['reference']}
                try:
                    launch = self.dispatch({'director_run_id': run_id, 'expected_run_sha256': sha,
                                            'assignment_id': name, 'operation': 'start', 'request': request},
                                           managed_guard=guard)
                except ResourceUnavailable as error:
                    task_id = next(tid for tid, assignment in state['implement_all']['task_assignments'].items()
                                   if assignment == name)
                    resource_holds[task_id] = str(error)
                else:
                    launches.append({'assignment_id': name, **launch})
                    sha = launch['run_sha256']
                relative, state, sha = self._load(run_id)
                remaining, holds, eligible, guard = self._advance_managed_frontier(
                    state, plan, resource_holds=resource_holds)
            for task_id, reason in resource_holds.items():
                holds.setdefault(task_id, reason)
        except RECOVERABLE_EFFECT_ERRORS as error:
            # Dispatch retains any prepared effect separately. A later advance reads that original effect.
            relative, current, current_sha = self._load(run_id)
            if current['phase'] != 'running':
                raise
            state, sha = current, current_sha
            gate = str(error)
        with self.store.lock(local_delivery={'kind': 'director-implement-all-advance', 'run_id': run_id}):
            relative, state, current_sha = self._load(run_id)
            _same_guard(current_sha, sha)
            frontier = state['implement_all']
            updated = {'remaining_ids': remaining, 'frontier': holds, 'gate': gate}
            if any(frontier.get(key) != value for key, value in updated.items()):
                frontier.update(updated)
                if gate is None and not remaining:
                    state['phase'] = 'completed'
                _event(state, 'implement-all-frontier', remaining_ids=remaining, gate=gate)
                sha = self._write(relative, state, current_sha)
        return {**self._profile_setup_view(state, self._view(state, sha, plan), plan), 'launches': launches}

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

    def _superseded(self, state):
        return self.superseded_assignments({**_object_identity(state), 'plan_sha256': state['plan_sha256']})

    def _view(self, state, sha, plan, *, check_supersession=True):
        status = {}
        superseded = self._superseded(state) if check_supersession else {}
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
            if name in superseded:
                status[name]['supersession'] = {**superseded[name], 'withheld_effect': status[name]['next']}
                status[name]['next'] = None
        result = {'director_run_id': state['director_run_id'], 'plan_sha256': state['plan_sha256'], 'phase': state['phase'],
                  'run_sha256': sha, 'assignments': status}
        if 'supervision' in state:
            result['supervision'] = self._supervision_view(state)
        if 'implement_all' in state:
            result['implement_all'] = deepcopy(state['implement_all'])
        return result

    def _profile_setup_view(self, state, view, plan):
        for spec in plan['assignments']:
            assignment = view['assignments'].get(spec['id'])
            if not assignment or assignment.get('completed'):
                continue
            start = assignment['dispatches'].get('start', {})
            if not start.get('result', {}).get('initial_profile_required'):
                continue
            try:
                child = D.WF.Store(self._area_for_run(state, spec), neutral=True)
                receipt, run = self._supervised_start_receipt(child, self._envelope(state, spec))
                D._require(receipt and receipt['receipt_sha256'] == start['receipt_sha256'],
                           'Original directed child start requires reconciliation')
            except RECOVERABLE_EFFECT_ERRORS as error:
                assignment['profile_setup_prerequisite'] = str(error)
                continue
            if D.WF.workspaces.initial_profile_pending(run):
                if 'profile_handoff' in run:
                    assignment['profile_handoff'] = run['profile_handoff']
                else:
                    assignment['profile_setup_prerequisite'] = 'Recover the original child Git workspace before profile setup'
        return view

    def status(self, payload):
        D._object(payload, {'director_run_id'})
        _, state, sha = self._load(payload['director_run_id'])
        plan = self._plan_for(state)
        return self._profile_setup_view(state, self._view(state, sha, plan), plan)

    def _supervise_now(self):
        return datetime.now(timezone.utc)

    @staticmethod
    def _supervision_view(state):
        return {**deepcopy(state['supervision']),
                'timeline': [deepcopy(row) for row in state.get('timeline', []) if row['event'].startswith('supervision-')]}

    @staticmethod
    def _current_attempt(unit):
        return unit['attempts'][str(unit['current_generation'])]

    def _supervised_start_receipt(self, child, envelope):
        helper = D.WF.director_dispatch_helper()
        if child.root == self.store.root and getattr(self.store, '_writer_active', False):
            # The shared canonical writer has already recovered its transaction.
            # Preserve all receipt and queue checks without mistaking this lock for a foreign writer.
            identity, key = helper.envelope('start', envelope)
            helper.canonical_owner(child, identity['queue_id'])
            _, receipt = helper._receipt(child, identity, key)
            if not receipt:
                return None, None
            D._require(receipt['plan_sha256'] == envelope['plan_sha256'],
                       'Existing Director dispatch belongs to a different plan')
            return receipt, helper.reconcile(child, receipt)
        observed = helper.observe(child, {'operation': 'start', 'director_dispatch': envelope})
        return observed['receipt'], observed['observed_result']

    def _supervised_child(self, state, name, child_run_id, task_id):
        spec = self._assignment(state, name)
        current = state['assignments'][name]
        D._require(state['phase'] == 'running' and name not in self._superseded(state)
                   and not current.get('completed') and not current.get('blocker')
                   and not any(question['phase'] != 'delivered' for question in current['questions'].values()),
                   'The exact Director assignment is paused, completed, superseded or otherwise ineligible')
        D._require(all(state['assignments'][dependency].get('completed') for dependency in spec['depends_on']),
                   'The Director assignment has an unresolved prerequisite')
        start = current['dispatches'].get('start', {})
        D._require('launch' in state['authority'][name] and start.get('status') == 'recorded'
                   and start['result']['id'] == child_run_id and self._child_task(spec, current, 'start') == task_id,
                   'Supervision requires the exact recorded ordinary child start and task')
        root = self._area_for_run(state, spec)
        child = D.WF.Store(root, neutral=True)
        receipt, run = self._supervised_start_receipt(child, self._envelope(state, spec))
        receipt = receipt or {}; run = run or {}
        D._require(not D.WF.workspaces.initial_profile_pending(run),
                   'Prepare the exact initial child worktree profile before assigning a worker')
        D._require(receipt.get('receipt_sha256') == start['receipt_sha256'] and run.get('id') == child_run_id
                   and run.get('workspace_state') == 'ready' and run.get('implementation_operation') == 'work-through-next'
                   and run.get('reviewed_local_delivery', {}).get('merge_at_finish') is False
                   and run.get('phase') not in {'completed', 'paused', 'cancelled', 'blocked'}
                   and run.get('delivery', {}).get('publication') == 'not-requested'
                   and set(run.get('admitted_task_ids', [])) >= {task_id} and run.get('root_task_id') == task_id,
                   'Supervision requires the exact eligible local child controller and admitted task')
        scoped = D.WF.Store(root, run_id=child_run_id)
        child_state = scoped.load()
        tasks = D.WF.parse(scoped.text())
        task = D.WF.resolve(tasks, [task_id], 'Prioritized Next Changes')[0]
        admitted = set(run['admitted_task_ids'])
        if 'implement_all' in state:
            expected = D.WF.dependency_scope(tasks, {'snapshot': [task_id]})
            D._require(admitted == expected and expected <= set(state['implement_all']['required_ids'])
                       and all(D.WF.completed_dependency_integrated(scoped, child_state, dependency)
                               for dependency in admitted - {task_id}),
                       'A supervised child may retain only verified historical prerequisites')
        else:
            D._require(admitted == {task_id}, 'A supervised assignment requires one exact admitted task')
        D._require(task['id'] == task_id and task['status'] == 'Ready', 'Supervision requires the exact Ready child task')
        frozen_task = (spec['child']['body_sha256'] if spec['child'].get('task_id') == task_id
                       else current['dispatches']['process']['result']['task_sha256'])
        D._require(D.WF.digest(task['body'].encode()) == frozen_task, 'The exact frozen Ready task definition changed')
        D.WF.assert_scope(scoped, child_state, tasks, task_id)
        return spec, scoped, task, receipt['receipt_sha256'], run['workspace']['base_commit']

    def _supervised_parent(self, units, parent_id, assignment):
        if parent_id is None:
            return
        parent = units.get(parent_id)
        D._require(parent and parent['assignment_id'] == assignment and parent['role'] == 'supervisor'
                   and self._current_attempt(parent)['status'] == 'running',
                   'A nested supervised worker requires its active in-scope parent at depth one')

    def _supervised_timeout(self, attempt, policy, now):
        if attempt['status'] == 'assigned':
            delay = timedelta(seconds=policy['progress_timeout_seconds'])
            return 'pickup-timeout' if now >= _deadline(attempt['assigned_at']) + delay else None
        if attempt['status'] != 'running':
            return None
        progress = now >= _deadline(attempt['last_progress_at']) + timedelta(seconds=policy['progress_timeout_seconds'])
        heartbeat = now >= _deadline(attempt['last_heartbeat_at']) + timedelta(seconds=policy['heartbeat_timeout_seconds'])
        if attempt['role'] == 'supervisor' and attempt.get('wait') and any(
                unit.get('parent_unit_id') == attempt['unit_id'] and self._current_attempt(unit)['status'] != 'completed'
                for unit in policy['units'].values()):
            return 'heartbeat-timeout' if heartbeat else None
        if progress:
            return 'progress-timeout'
        if heartbeat:
            return 'heartbeat-timeout'
        return None

    def _supervised_checkout(self, child, attempt):
        worktree, checkout = D.WS.worker_checkout(child.source_root, attempt['worktree'])
        D._require(checkout == attempt['checkout'], 'The exact supervised worker checkout changed')
        worker = D.WF.Store(worktree, route_queue=False)
        shared = attempt['shared_inputs']
        D._require(D.WF.fingerprints(child, shared) == shared == D.WF.fingerprints(worker, shared),
                   'Supervised shared validation inputs changed')
        return worktree, worker

    def _supervised_marker(self, units, unit, attempt, child):
        if unit['role'] == 'supervisor':
            children = {}
            for key, candidate in units.items():
                if candidate.get('parent_unit_id') == attempt['unit_id']:
                    current = self._current_attempt(candidate)
                    children[key] = {field: current.get(field) for field in ('generation', 'status', 'progress_marker', 'receipt_sha256')}
            return D._digest(children)
        worktree, worker = self._supervised_checkout(child, attempt)
        return D._digest({'head': D.WS.worker_head(worktree), 'paths': D.WF.fingerprints(worker, attempt['paths'])})

    def _supervised_assign(self, state, policy, payload, now):
        name, unit_id, role = (payload[key] for key in ('assignment_id', 'unit_id', 'role'))
        child_run_id, task_id = (payload[key] for key in ('child_run_id', 'task_id'))
        units = policy['units']; parent_id = payload.get('parent_unit_id')
        D._require(D._token(name) and isinstance(role, str) and role in {'supervisor', 'worker'}
                   and (parent_id is None or D._token(parent_id))
                   and D.WF.valid_id(child_run_id, 'WR') and D.WF.valid_id(task_id, 'T'),
                   'An exact Director assignment, role, child controller and task are required')
        spec, child, task, launch, launched_base = self._supervised_child(state, name, child_run_id, task_id)
        generation = payload['generation']; previous_unit = units.get(unit_id)
        unit = {'assignment_id': name, 'role': role, 'parent_unit_id': parent_id,
                'child_run_id': child_run_id, 'task_id': task_id}
        if previous_unit:
            previous = self._current_attempt(previous_unit)
            D._require(previous['status'] == 'stopped' and generation == previous_unit['current_generation'] + 1
                       and all(previous_unit.get(key) == value for key, value in unit.items()),
                       'Retired or stale supervised generation or frozen unit scope')
        else:
            D._require(generation == 1, 'A new supervised unit starts at generation one')
        prerequisites = D._tokens(payload.get('depends_on', []), 'Supervised prerequisites')
        D._require(all(key in units and self._current_attempt(units[key])['status'] == 'completed' for key in prerequisites),
                   'Supervised unit has an unresolved prerequisite')
        self._supervised_parent(units, parent_id, name)
        active = [(other, self._current_attempt(other)) for other in units.values()
                  if self._current_attempt(other)['status'] in SUPERVISED_LIVE]
        D._require(all(item['actor_id'] != payload['actor_id'] for _, item in active),
                   'Supervised assignments require distinct live actors')
        resource_keys = payload.get('resources', spec['resources'] if role == 'worker' else [])
        D._require(isinstance(resource_keys, list) and all(_supervision_identity(key) for key in resource_keys)
                   and len(set(resource_keys)) == len(resource_keys), 'Supervised resources require exact distinct identities')
        resources = sorted(resource_keys)
        attempt = {**unit, 'unit_id': unit_id, 'generation': generation, 'actor_id': payload['actor_id'],
                   'assigned_at': now, 'status': 'assigned', 'resources': resources, 'depends_on': prerequisites,
                   'launch_receipt_sha256': launch, 'task_sha256': D.WF.digest(task['body'].encode())}
        if role == 'supervisor':
            D._require(not parent_id and not resources and not ({'worktree', 'base', 'paths'} & payload.keys())
                       and not any(other['role'] == 'supervisor' for other, _ in active),
                       'A supervised run has one non-writing supervisory parent')
        else:
            D._require(set(resources) == set(spec['resources']), 'A worker must claim the frozen exclusive resource scope')
            D._require(sum(other['role'] == 'worker' for other, _ in active) < 2,
                       'The supervised run has no free implementation slot')
            D._require(all(not set(other['resources']).intersection(resources) for _, other in active),
                       'A requested supervised exclusive resource is already held')
            self._check_resources(spec, child, owner_run_id=child_run_id)
            paths = D.WS.worker_paths(payload.get('paths'))
            lines = [line for line in D.WF.section_body(task['body'], 'Touch').splitlines() if line.strip()]
            touch = [line[2:].strip().strip('`') for line in lines if line.startswith('- ')]
            frozen = [(D._scope(spec['area']['scope']) / D._scope(path)).as_posix() for path in spec['write_paths']]
            D._require(lines and len(touch) == len(lines) and paths and all(
                any(path == allowed or path.startswith(allowed + '/') for allowed in scopes)
                for path in paths for scopes in (touch, frozen)),
                'Supervised workspace paths exceed the frozen Director write scope or Ready task Touch')
            worktree, checkout = D.WS.worker_checkout(child.source_root, payload.get('worktree'))
            base = payload.get('base')
            D._require(base == launched_base == D.WS.worker_head(child.source_root) == D.WS.worker_head(worktree),
                       'Supervised checkout does not begin at the exact current child controller base')
            D.WS.require_clean_worker(worktree)
            repo = str(D.WS.common_dir(child.source_root))
            for other, live in active:
                if other['role'] != 'worker' or live['repository'] != repo:
                    continue
                D._require(checkout != live['checkout'], 'Supervised assignments require distinct live worker checkouts')
                D._require(not any(D.WS.local_overlap(first.casefold(), second.casefold())
                                   for first in paths for second in live['paths']), 'Found overlapping supervised write scope')
            checks = [check for check in D.WF.check_specs(task) if check['id'] == spec['check']]
            D._require(len(checks) == 1, 'Supervision requires the frozen child check contract')
            recipe = D.WF.recipe_for(child, checks[0])[0]
            inputs = [path for path in checks[0]['sources'] + recipe.get('input_paths', []) if not
                      any(D.WS.local_overlap(path.casefold(), owned.casefold()) for owned in paths)]
            shared = D.WF.fingerprints(child, inputs)
            worker = D.WF.Store(worktree, route_queue=False)
            D._require(None not in shared.values() and D.WF.fingerprints(worker, shared) == shared,
                       'Supervised worker check inputs are unavailable or differ from the child controller')
            for other, live in active:
                if other['role'] == 'worker' and live['repository'] == repo:
                    D._require(not any(D.WS.local_overlap(left.casefold(), right.casefold())
                        for ours, theirs in ((paths, live['shared_inputs']), (shared, live['paths']))
                        for left in ours for right in theirs), 'Supervised writes overlap another worker check input')
            attempt.update(worktree=str(worktree), checkout=checkout, base=base, paths=paths, repository=repo, shared_inputs=shared)
        if previous_unit:
            if role == 'worker':
                D._require(previous['paths'] == attempt['paths'], 'A replacement must preserve the frozen write scope')
                D._require(previous['checkout'] != attempt['checkout'], 'A replacement requires a new isolated worker checkout')
            D._require(previous['depends_on'] == prerequisites and previous['task_sha256'] == attempt['task_sha256']
                       and previous['launch_receipt_sha256'] == launch, 'A replacement must preserve its exact assignment and prerequisites')
            unit['attempts'] = previous_unit['attempts']
        else:
            unit['attempts'] = {}
        unit['current_generation'] = generation
        unit['attempts'][str(generation)] = attempt
        attempt['assignment_sha256'] = D._digest(attempt)
        attempt['progress_marker'] = self._supervised_marker(units, unit, attempt, child)
        units[unit_id] = unit
        return attempt

    def _supervised_submission(self, units, unit, attempt, child, spec, payload, now):
        D._require(_group_gone(attempt['process']['pgid']), 'The original supervised process group still exists')
        if unit['role'] == 'supervisor':
            D._require('result' not in payload, 'A non-writing supervisor cannot submit a source result')
            children = [self._current_attempt(item) for item in units.values() if item.get('parent_unit_id') == attempt['unit_id']]
            D._require(children and all(item['status'] == 'completed' for item in children),
                       'Supervisory completion requires all exact nested worker results')
            proof = {'children': {item['unit_id']: item['receipt_sha256'] for item in children}}
        else:
            result = payload.get('result')
            D._object(result, {'head', 'checks'})
            worktree, _ = self._supervised_checkout(child, attempt)
            D._require(isinstance(result['checks'], list) and len(result['checks']) == 1,
                       'Supervised worker result requires the exact frozen check artifact')
            check = result['checks'][0]
            D._object(check, {'id', 'path', 'sha256'})
            relative = D.WS.worker_path(check['path'])
            artifact = D._safe_path(worktree, relative)
            D._require(check['id'] == spec['check'] and D._sha(check['sha256']) and artifact.is_file()
                       and D.WF.file_hash(artifact) == check['sha256']
                       and D.WS.committed_file_hash(worktree, attempt['base'], relative) != check['sha256'],
                       'Supervised check artifact is missing, aliased, stale or changed')
            candidate = D.WS.worker_candidate(worktree, attempt['base'], result['head'], attempt['paths'], [relative])
            D._require(D.WF.file_hash(artifact) == check['sha256'], 'Supervised check artifact changed during verification')
            proof = {'candidate': candidate, 'candidate_sha256': D._digest(candidate), 'checks': deepcopy(result['checks'])}
        attempt.update(status='completed', verified_at=now, wait=None, **proof)
        attempt['receipt_sha256'] = D._digest({key: attempt[key] for key in (
            'assignment_sha256', 'unit_id', 'generation', 'actor_id', 'launch_receipt_sha256', 'task_sha256',
            'picked_up_at', 'verified_at', 'process')} | proof)
        if unit['parent_unit_id'] is not None:
            parent = self._current_attempt(units[unit['parent_unit_id']])
            if parent.get('wait'):
                parent.update(last_progress_at=now,
                              progress_reference='Verified nested worker receipt '+attempt['receipt_sha256'])

    @contextmanager
    def _supervision_writer(self, owner, *, may_wait):
        deadline = monotonic() + SUPERVISION_LOCK_WAIT_SECONDS
        with ExitStack() as locks:
            while True:
                try:
                    locks.enter_context(self.store.lock(local_delivery=owner))
                    break
                except D.WF.WorkflowError as error:
                    remaining = deadline - monotonic()
                    if (not may_wait or remaining <= 0 or not isinstance(error.__cause__, FileExistsError)
                            or not str(error).startswith('Writer lock exists;')):
                        raise
                    sleep(min(0.05, remaining))
                    if monotonic() >= deadline:
                        raise
            yield

    def supervise(self, payload):
        D._require(isinstance(payload, dict) and isinstance(payload.get('action'), str), 'Select a supervised run action')
        action = payload['action']
        if action == 'status':
            D._object(payload, {'action', 'director_run_id'})
            _, state, sha = self._load(payload['director_run_id'])
            D._require('supervision' in state, 'This Director run did not opt into supervision')
            return {'status': 'ok', 'run_sha256': sha, 'supervision': self._supervision_view(state)}
        D._require(action in SUPERVISION_ACTIONS, 'Unknown supervised run action')
        required, optional = SUPERVISION_ACTIONS[action]
        D._object(payload, GUARD | {'action', 'request_id'} | required, optional)
        D._require(_supervision_identity(payload['request_id']), 'Supervision requires an exact request identity')
        if action != 'sweep':
            D._require(D._token(payload['unit_id']) and _supervision_identity(payload['actor_id'])
                       and type(payload['generation']) is int and payload['generation'] > 0,
                       'Supervision requires the exact unit, actor and positive generation')
        request = D._digest({key: value for key, value in payload.items() if key != 'expected_run_sha256'})
        owner = {'kind': 'director-run-supervision', 'request': request}
        compatible = action in COHERENT_WORKER_ACTIONS
        with self._supervision_writer(owner, may_wait=compatible):
            relative, state, sha = self._load(payload['director_run_id'])
            policy = state.get('supervision')
            D._require(policy and policy['host'] == socket.gethostname(), 'Supervision requires the original local host and opt-in run')
            replay = policy['requests'].get(payload['request_id'])
            prior = policy['units'].get(payload.get('unit_id'))
            if action not in {'assign', 'sweep'}:
                D._require(prior and prior['current_generation'] == payload['generation']
                           and self._current_attempt(prior)['actor_id'] == payload['actor_id'],
                           'Retired or stale supervised generation or actor')
            if replay:
                D._require(replay['sha256'] == request, 'Supervision request ID was reused with different input')
                if action == 'assign':
                    D._require(prior and prior['current_generation'] == payload['generation'],
                               'Retired or stale supervised generation or actor')
                return {**deepcopy(replay['result']), 'status': 'replayed', 'run_sha256': sha}
            expected = payload['expected_run_sha256']
            frontier = self._supervised_worker_frontier(state, sha) if compatible else []
            rebased = compatible and expected != sha and D._sha(expected) and expected in frontier
            if not rebased:
                _same_guard(sha, expected)
            now = self._supervise_now(); stamp = now.isoformat(); units = policy['units']
            if action == 'sweep':
                stalled = []
                for unit in units.values():
                    attempt = self._current_attempt(unit)
                    reason = self._supervised_timeout(attempt, policy, now)
                    if reason:
                        attempt.update(status='stalled', stalled_at=stamp, stalled_reason=reason)
                        stalled.append(attempt['unit_id'])
                        _event(state, 'supervision-stalled', unit_id=attempt['unit_id'], generation=attempt['generation'], reason=reason)
                result = {'status': 'observed', 'stalled': sorted(stalled)}
            else:
                if action == 'assign':
                    attempt = self._supervised_assign(state, policy, payload, stamp)
                else:
                    attempt = self._current_attempt(prior)
                    self._supervised_transition(state, policy, prior, attempt, payload, now, rebased=rebased)
                _event(state, 'supervision-'+action, unit_id=attempt['unit_id'], generation=attempt['generation'],
                       actor_id=attempt['actor_id'], status=attempt['status'])
                result = {'status': attempt['status'], 'attempt': deepcopy(attempt)}
            policy['requests'][payload['request_id']] = {'sha256': request, 'result': result}
            if compatible:
                policy['worker_frontier'] = {
                    'digests': [*frontier, sha][-SUPERVISION_FRONTIER_LIMIT:],
                    'payload_sha256': self._supervised_payload_digest(state),
                }
            return {**result, 'run_sha256': self._write(relative, state, sha, retain_worker_frontier=compatible)}

    def _supervised_transition(self, state, policy, unit, attempt, payload, now, *, rebased=False):
        action = payload['action']; stamp = now.isoformat()
        if action == 'recover':
            observation = payload['stop_observation']; process = attempt.get('process')
            fields = {'kind', 'host', 'actor_id', 'reference'}
            D._object(observation, fields | ({'pid', 'pgid'} if process else {'process_groups'}))
            D._require(attempt['status'] == 'stalled'
                       and observation['host'] == policy['host'] and observation['actor_id'] == attempt['actor_id']
                       and _supervision_text(observation['reference']), 'Recovery requires the exact stalled local host-stop observation')
            if process:
                D._require(observation['kind'] == 'host-stopped'
                           and all(type(observation[key]) is int and observation[key] == process[key]
                                   for key in ('pid', 'pgid')),
                           'Recovery requires the exact stalled local host-stop observation')
                groups = [process['pgid']]
            else:
                groups = observation['process_groups']
                D._require(attempt.get('stalled_reason') == 'pickup-timeout'
                           and observation['kind'] == 'host-stopped-unbound' and isinstance(groups, list)
                           and all(type(group) is int and 1 < group < 2**31 for group in groups)
                           and len(set(groups)) == len(groups),
                           'Recovery requires the local host observation for the unbound pickup timeout')
            D._require(all(_group_gone(group) for group in groups), 'The original supervised process group still exists')
            attempt.update(status='stopped', stopped_at=stamp, stop_observation=deepcopy(observation), wait=None)
            return
        expected = 'assigned' if action == 'pickup' else 'running'
        D._require(attempt['status'] == expected and not self._supervised_timeout(attempt, policy, now),
                   'Retired or stale supervised attempt; observe timeouts before recovery')
        spec, child, task, launch, _ = self._supervised_child(state, unit['assignment_id'], unit['child_run_id'], unit['task_id'])
        D._require(launch == attempt['launch_receipt_sha256'] and D.WF.digest(task['body'].encode()) == attempt['task_sha256'],
                   'The exact supervised launch or Ready task definition changed')
        self._supervised_parent(policy['units'], unit['parent_unit_id'], unit['assignment_id'])
        if unit['role'] == 'worker' and (action in {'pickup', 'submit'} or rebased):
            self._check_resources(spec, child, owner_run_id=unit['child_run_id'])
        if action == 'pickup':
            process = _supervision_process(payload['process'])
            D._require(all(item.get('process', {}).get('pgid') != process['pgid'] for other in policy['units'].values()
                           for item in other['attempts'].values() if item['status'] in SUPERVISED_LIVE),
                       'The local process group is already bound to a supervised attempt')
            D._require(self._supervised_marker(policy['units'], unit, attempt, child) == attempt['progress_marker'],
                       'The supervised checkout changed before its actual pickup')
            attempt.update(status='running', picked_up_at=stamp, last_heartbeat_at=stamp, last_progress_at=stamp, process=process)
        elif action == 'heartbeat':
            D._require(_supervision_process({key: attempt['process'][key] for key in ('pid', 'pgid')}) == attempt['process'],
                       'The original supervised process group identity changed')
            attempt['last_heartbeat_at'] = stamp
        elif action == 'progress':
            if rebased:
                D._require(_supervision_process({key: attempt['process'][key] for key in ('pid', 'pgid')}) == attempt['process'],
                           'The original supervised process group identity changed')
            marker = self._supervised_marker(policy['units'], unit, attempt, child)
            D._require(_supervision_text(payload['reference']) and marker != attempt['progress_marker'],
                       'Supervised progress requires a changed native observation')
            attempt.update(progress_marker=marker, progress_reference=payload['reference'], last_progress_at=stamp, wait=None)
        elif action == 'wait':
            D._require(_supervision_text(payload['reason']) and _supervision_text(payload['reference']),
                       'Supervised wait requires a named cause and observation')
            attempt['wait'] = {'reason': payload['reason'], 'reference': payload['reference'], 'recorded_at': stamp}
        elif action == 'submit':
            self._supervised_submission(policy['units'], unit, attempt, child, spec, payload, stamp)

    def verify_intake(self, payload):
        D._object(payload, {'director_run_id', 'assignment_id'})
        _, state, _ = self._load(payload['director_run_id'])
        name = payload['assignment_id']
        spec = self._assignment(state, name)
        root = self._area_for_run(state, spec)
        selected = spec['area']
        result = {**payload, 'area_id': selected['id'], 'repo_id': selected['repo_id'],
                  'scope': selected['scope'], 'queue_id': selected['queue_id'], 'status': 'unverified'}
        recorded = state['assignments'][name]['dispatches'].get('intake')
        if not recorded or recorded['status'] != 'recorded':
            return result
        D._require('intake' in state['authority'][name] and 'intake' in spec['effects'],
                   'Original Director intake lacks exact authorization')
        child = D.WF.Store(root, neutral=True)
        observed = D.WF.director_dispatch_helper().observe(
            child, {'operation': 'intake', 'director_dispatch': self._envelope(state, spec)})
        receipt = observed['receipt']
        D._require(receipt and receipt['receipt_sha256'] == recorded['receipt_sha256']
                   and receipt['semantic_sha256'] == recorded['semantic_sha256']
                   and observed['observed_result']['id'] == recorded['result']['id'],
                   'Original canonical intake receipt is unavailable or changed')
        return {**result, 'status': 'verified', 'plan_sha256': state['plan_sha256'],
                'pending_id': recorded['result']['id'], 'receipt_sha256': receipt['receipt_sha256']}

    def lifecycle(self, command, payload):
        D._object(payload, GUARD)
        target = {'run-pause': 'paused', 'run-resume': 'running', 'run-cancel': 'cancelled'}[command]
        owner = {'kind': command, 'sha256': D._digest(payload)}
        with self.store.lock(local_delivery=owner):
            relative, state, sha = self._load(payload['director_run_id'])
            _same_guard(sha, payload['expected_run_sha256'])
            D._require(state['phase'] not in {'completed', 'cancelled'} and (target != 'running' or state['phase'] == 'paused'),
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

    def _check_resources(self, spec, child, *, owner_run_id=None):
        requested = set(spec['resources'])
        if not requested:
            return
        _, bindings, _ = self.registry._load()
        roots = {Path(binding['root']) for binding in (bindings or {}).get('queues', {}).values()} | {child.root}
        for root in roots:
            state = D.WF.Store(root, route_queue=False, neutral=True).load()
            claims = state.get('run_registry', {}).get('resources', {})
            conflicts = {key for key in requested.intersection(claims) if not
                         (owner_run_id is not None and root == child.root and claims[key]['run_id'] == owner_run_id)}
            if conflicts:
                raise ResourceUnavailable('A requested exclusive child resource is already claimed: '+', '.join(sorted(conflicts)))

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

    def _dispatch_request(self, operation, requested, spec, record, child, original_exists, process_sha, *, managed=False):
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
            if managed:
                self._managed_assignment_paths(spec, child, candidate)
                outcomes = {entry['task_id']: entry for entry in child.outcomes() if entry['disposition'] == 'completed'}
                for dependency in candidate['depends_on']:
                    proof = outcomes.get(dependency, {}).get('source_fingerprints')
                    D._require(proof and D.WF.fingerprints(child, proof) == proof,
                               'Managed child prerequisite evidence is unavailable or stale: ' + dependency)
            else:
                D._require(not candidate['depends_on'], 'Child start requires separate review of dependencies outside the exact assignment')
        return requested, {'mode': 'next', 'selector': child_id, 'limits': None}

    def _reject_superseded(self, relative, state, sha, effect):
        name = effect['assignment_id']
        supersession = self._superseded(state).get(name)
        if supersession is None:
            return
        denial = {'assignment_id': name, 'operation': effect['operation'], 'reason': 'guard-rejected',
                  'superseded_by': supersession['amendment'], 'request_sha256': effect['sha256']}
        if not any(event['event'] == 'dispatch-failed' and all(event.get(key) == value for key, value in denial.items())
                   for event in state.get('timeline', [])):
            _event(state, 'dispatch-failed', **denial)
            self._write(relative, state, sha)
        raise D.DirectorError(f"Assignment {name} was superseded by accepted plan revision "
                              f"{supersession['next']['plan_revision']}; fresh child effects are held")

    def dispatch(self, payload, *, managed_guard=None):
        managed = managed_guard is not None
        D._object(payload, GUARD | {'assignment_id', 'operation', 'request'})
        operation = payload['operation']
        D._require(operation in EFFECTS, 'Director run dispatch does not grant the requested effect')
        D._require(isinstance(payload['request'], dict), 'Director dispatch requires an exact effect request')
        run_id, name = payload['director_run_id'], payload['assignment_id']
        rel, before, sha = self._load(run_id)
        spec = self._assignment(before, name)
        child = D.WF.Store(self._area_for_run(before, spec), neutral=True)
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
        D._require('implement_all' not in before or managed, 'Advance the managed Implement All run for fresh dispatch')
        D._require(before['phase'] == 'running' and EFFECTS[operation] in before['authority'][name],
                   'Director run lacks current exact execution authority for this effect')
        effect_sha = D._digest({key: value for key, value in payload['request'].items() if key != 'expected_source_hash'})
        effect = {'kind': 'director-run-dispatch', 'run_id': run_id, 'assignment_id': name,
                  'operation': operation, 'sha256': effect_sha}
        with self.store.lock(local_delivery=effect):
            rel, current, current_sha = self._load(run_id)
            _same_guard(current_sha, sha)
            if existing is None:
                _same_guard(current_sha, payload['expected_run_sha256'])
            if not recovering:
                self._reject_superseded(rel, current, current_sha, effect)
                if operation == 'start':
                    self._check_resources(spec, child)
            eligible = self._view(current, current_sha, self._plan_for(current), check_supersession=False)['assignments'][name]
            D._require(eligible['next'] == operation, 'The assignment is not eligible for this exact effect')
            request, start = self._dispatch_request(operation, payload['request'], spec, current['assignments'][name],
                                                    child, recovering, current['process_spec_sha256'].get(name),
                                                    managed=managed)
            if managed:
                head, integrated, _, _ = self._managed_incorporation(current, child.root)
                D._require(set(spec['depends_on']) <= integrated,
                           'Managed child prerequisites require checked incorporation')
                expected_launch = {**current['implement_all']['target'], 'head': head}
                if existing is not None:
                    expected_launch = existing['managed_expected_launch']
                request = {**request, 'managed_expected_launch': expected_launch}
            reviewed_directed = operation == 'start' and ('supervision' in current or managed)
            if reviewed_directed:
                D._require(request.get('local_base') is True and _supervision_text(request.get('base_branch'))
                           and _supervision_text(request.get('local_base_authorization')),
                           'A supervised directed launch requires an explicit authorized local base')
                request = {**request, 'implementation_operation': 'work-through-next'}
            request = {**request, 'director_dispatch': envelope}
            directed = helper.ChildDispatch(operation, request, start)
            if existing is None:
                current['assignments'][name]['dispatches'][operation] = {'status': 'prepared', 'request_sha256': effect_sha,
                                                                        'semantic_sha256': directed.semantic_sha256,
                                                                        'failure_key': None, 'failures': 0}
                if managed:
                    current['assignments'][name]['dispatches'][operation]['managed_expected_launch'] = expected_launch
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
                self._reject_superseded(rel, current, current_sha, effect)
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
            elif reviewed_directed:
                D.WF.start(child, start['mode'], start['selector'], start['limits'], request,
                           reviewed_directed=True, managed_queue_guard=managed_guard)
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
            if operation == 'start' and D.WF.workspaces.initial_profile_pending(result):
                result_ids['initial_profile_required'] = True
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
        root = self._area_for_run(state, spec)
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
        if 'implement_all' in state:
            reviewed = actual['delivery'].get('reviewed_source')
            D._require(reviewed, 'Managed assignment requires the exact reviewed child source')
            owned = self._managed_assignment_paths(spec, child, None)
            changed = D.WS.local_incoming(root, actual['workspace']['base_commit'], reviewed['source']['source_head'])
            evidence_root = Path('.skill-tree/run-evidence') / actual['id'].lower()
            evidence = {item['path'] for item in D.WF.cleanup_evidence_records(matches[0])
                        if Path(item['path']).is_relative_to(evidence_root)}
            D._require(changed and all(path in evidence or any(Path(path).is_relative_to(scope) for scope in owned)
                                      for path in changed),
                       'The reviewed child commit writes outside the frozen assignment scope')
        completed = {'outcome_id': payload['outcome_id'], 'task_id': task_id, 'child_run_id': actual['id'],
                     'outcome_sha256': D._digest(matches[0]), 'check_key': check[0]['key']}
        with self.store.lock(local_delivery={'kind': 'director-run-assignment-complete', 'sha256': D._digest(payload)}):
            rel, state, sha = self._load(run_id)
            _same_guard(sha, payload['expected_run_sha256'])
            target = state['assignments'][name]
            previous = target.get('completed')
            D._require(previous is None or previous == completed, 'Child completion identity changed')
            if previous is None:
                if 'supervision' in state:
                    units = [self._current_attempt(unit) for unit in state['supervision']['units'].values()
                             if unit['assignment_id'] == name]
                    workers = [attempt for attempt in units if attempt['role'] == 'worker'
                               and attempt.get('receipt_sha256') and attempt.get('candidate')]
                    D._require(all(attempt['status'] == 'completed' for attempt in units)
                               and workers,
                               'Confirm every started supervised unit and a verified worker result before closing the assignment')
                    accepted = (matches[0].get('task_git_commit') or {}).get('commit')
                    D._require(isinstance(accepted, str) and re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', accepted)
                               and all(D.WS.local_git(root, 'diff', '--quiet', attempt['candidate']['head'], accepted,
                                      '--', *attempt['candidate']['paths'], accepted=(0, 1)).returncode == 0 for attempt in workers),
                               'The scoped Core commit does not contain the exact verified worker changes')
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
        root = self._area_for_run(state, spec)
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
        root = self._area_for_run(state, spec)
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
    handoff_adapter = D.WF.owned_module('director_handoff_runtime', Path(__file__).with_name('director-handoff.py'))
    handoffs = handoff_adapter.DirectorHandoffs(registry, planner)
    def registered():
        current_registry, bindings, _ = registry._load()
        return current_registry, bindings, source_adapter.PlanSources(D, planner.O, planner.C, current_registry, bindings)

    def check_current(plan):
        ledger, _, _, _ = planner.ledger._load(plan['objective']['objective_id'])
        current = {'revision': plan['objective']['objective_revision'], 'sha256': plan['objective']['objective_sha256']}
        D._require(ledger['current'] == current, 'The frozen Director objective is no longer current')

    def check_area(assignment, *, approved_head=None):
        areas, bindings, sources = registered()
        identity = assignment['area']
        area = areas['areas'].get(identity['id'])
        D._require(area and all(area.get(key) == identity[key] for key in ('id', 'scope', 'repo_id', 'queue_id')),
                   'The planned Director area identity changed')
        root = planner.O._child_root(areas, bindings, area['id'])
        if approved_head is None:
            qualification = sources.qualify(area, assignment['capability'])
        else:
            current = approved_head(root)
            D._require(D.WS.checked_out_branch(root)['head'] == current, 'Managed target changed after incorporation inspection')
            qualification = sources.qualify(area, assignment['capability'], qualified_head=identity['qualification']['head'])
        D._require(qualification == identity['qualification'],
                   'The planned child source, profile or capability qualification changed')
        D._require(set(assignment['effects']) <= set(area['allowed_effects']), 'Registered area effect authority changed')
        for pin in assignment['pins']:
            if pin['strength'] != 'optional':
                D._require(verify_pin(pin), 'A required Director source pin is no longer current')
        return root

    def verify_pin(pin):
        areas, _, sources = registered()
        area = areas['areas'].get(pin['area_id'])
        if not area:
            return False
        expected = {key: pin[key] for key in ('revision', 'sha256')}
        observed = sources.pin(area, {key: value for key, value in pin.items() if key != 'status'})
        return observed == {'status': 'verified', **expected}

    engine = DirectorRun(registry, planner.frozen, check_area, check_current, verify_pin, handoffs.superseded_assignments)
    methods = {'run-start': engine.start, 'run-status': engine.status, 'run-dispatch': engine.dispatch, 'verify-intake': engine.verify_intake,
               'run-complete-assignment': engine.complete_assignment, 'run-supervise': engine.supervise,
               'run-advance-all': engine.advance_all,
               'decide-open': engine.open_question, 'decide-answer': engine.answer}
    return methods[command](payload) if command in methods else engine.lifecycle(command, payload)
