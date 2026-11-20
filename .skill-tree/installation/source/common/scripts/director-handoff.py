#!/usr/bin/env python3
"""Review exact Director producer and consumer evidence and scope changes."""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess


def _director():
    path = Path(__file__).with_name('director-state.py')
    spec = importlib.util.spec_from_file_location('handoff_director_state', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = _director()
O = D._objective_helper()
AREA_ID = ('id', 'scope', 'queue_id', 'repo_id')
SELECTOR = {'objective_id', 'plan_id', 'plan_revision', 'plan_sha256'}
PIN_KEYS = {'area_id', 'adapter', 'record_id', 'role'}
ARCHIVE = '.skill-tree/director/handoffs'
RUNS = '.skill-tree/director/runs'


def _matches_pin(pin, identity):
    return all(pin.get(key) == value for key, value in identity.items())


def _pin_identity(pin):
    return tuple(pin[key] for key in sorted(PIN_KEYS))


def _plan_identity(record):
    return {key: record[key] for key in SELECTOR - {'objective_id'}}


def _replacements(older, newer, changed):
    blockers = []
    for name in changed:
        if name not in older:
            continue
        replacement = newer.get(name, {})
        pins = replacement.get('pins', [])
        for prior in older[name]['pins']:
            if prior['strength'] != 'provisional':
                continue
            replacements = [pin for pin in pins if (pin['area_id'], pin['role']) == (prior['area_id'], prior['role'])]
            if any(pin['strength'] == 'provisional' for pin in replacements):
                continue
            final = [pin for pin in replacements if pin['strength'] == 'required'
                     and pin['sha256'] != prior['sha256'] and pin['status'] == 'verified']
            if len(final) != 1 or replacement.get('check') != prior['replacement_gate']:
                blockers.append({'assignment_id': name, 'reason': 'provisional-replacement-gate-unmet',
                                 'pin': prior, 'replacement_check': prior['replacement_gate']})
    return blockers


def _reverse(older, newer, changed):
    edges = {}
    for assignment in (*older.values(), *newer.values()):
        for dependency in assignment['depends_on']:
            edges.setdefault(dependency, set()).add(assignment['id'])
    paths = {name: [[name]] for name in sorted(changed)}
    pending = sorted(changed)
    while pending:
        current = pending.pop(0)
        for consumer in sorted(edges.get(current, ())):
            if consumer not in paths:
                paths[consumer] = [paths[current][0] + [consumer]]
                pending.append(consumer)
    return {name: paths[name] for name in sorted(paths)}


class DirectorHandoffs:
    def __init__(self, registry, planner):
        self.registry = registry
        self.planner = planner
        self.root = registry.root
        self.store = D.WF.Store(self.root, route_queue=False, neutral=True)

    def _load(self, selector):
        D._object(selector, SELECTOR)
        plan, sha = self.planner.frozen({key: selector[key] for key in SELECTOR - {'plan_sha256'}})
        D._require(sha == selector['plan_sha256'], 'Select the exact immutable plan revision and digest')
        ledger, registry, bindings, basis = self.planner.ledger._load(selector['objective_id'])
        return plan, ledger, registry, bindings, basis

    def _archive_record(self, record, archive_id):
        D._object(record, {'schema', 'recorded_at', 'archive_id', 'owner_ref', 'request_sha256', 'request', 'observation'})
        observation = record['observation']
        kind = observation.get('kind')
        command = {'director-handoff-review': 'review-apply', 'director-handoff-amendment': 'amend-apply'}.get(kind)
        D._require(record['schema'] == 1 and record['archive_id'] == archive_id and command is not None
                   and observation.get('preview_sha256') == archive_id
                   and D._digest({key: value for key, value in observation.items() if key != 'preview_sha256'}) == archive_id
                   and D._digest({'kind': command, 'sha256': D._digest({
                       'request': record['request'], 'expected_preview_sha256': archive_id,
                       'owner_ref': record['owner_ref']})}) == record['request_sha256'],
                   'Archived handoff identity or content changed')
        return record

    def _amendments(self, selector, *, endpoint='previous'):
        directory = D._safe_path(self.root, ARCHIVE)
        for path in sorted(directory.glob('*.json')):
            record, _ = D._read(self.root, f'{ARCHIVE}/{path.name}')
            observation = self._archive_record(record, path.stem)['observation']
            if observation['kind'] == 'director-handoff-amendment' and observation[endpoint] == selector:
                yield observation

    def _amendment_chain(self, selector, *, endpoint='previous'):
        opposite = 'next' if endpoint == 'previous' else 'previous'
        while True:
            amendments = list(self._amendments(selector, endpoint=endpoint))
            D._require(len(amendments) <= 1, 'Frozen plan has conflicting approved amendment receipts')
            if not amendments:
                return
            amendment = amendments[0]
            yield amendment
            selector = amendment[opposite]

    def superseded_assignments(self, selector):
        """Find the first approved amendment affecting each prior assignment."""
        superseded = {}
        for amendment in self._amendment_chain(selector):
            for name in amendment['affected']:
                superseded.setdefault(name, {'previous': amendment['previous'], 'next': amendment['next'],
                                             'amendment': amendment['preview_sha256']})
        return superseded

    def _check_record(self, links, link_id, assignment, selector, registry, bindings):
        if link_id is None:
            return None
        D._require(D._sha(link_id) and link_id in links, 'Select an exact recorded child outcome link')
        record = links[link_id]
        D._require(_plan_identity(record) == _plan_identity(selector)
                   and record['assignment_id'] == assignment['id']
                   and all(record['area'][field] == assignment['area'][field] for field in AREA_ID),
                   'Child outcome link is outside the exact plan assignment')
        return O._view_link({'link_id': link_id, **record}, registry, bindings)

    def _edge(self, item, assignments, selector, ledger, registry, bindings, prior):
        D._object(item, {'edge_id', 'producer', 'consumer', 'pin', 'artifact_id', 'consumed_path'},
                  {'producer_link', 'consumer_link'})
        D._require(all(D._token(item[key]) for key in ('edge_id', 'producer', 'consumer', 'artifact_id'))
                   and item['producer'] in assignments and item['consumer'] in assignments,
                   'Handoff names an unknown assignment or artifact')
        D._object(item['pin'], PIN_KEYS)
        producer, consumer = assignments[item['producer']], assignments[item['consumer']]
        D._require(producer['id'] in consumer['depends_on'] and producer['area']['id'] != consumer['area']['id']
                   and item['pin']['area_id'] == producer['area']['id'], 'Handoff requires an exact cross-area dependency')
        pins = [pin for pin in consumer['pins'] if _matches_pin(pin, item['pin'])]
        D._require(len(pins) == 1, 'Exact accepted consumer input pin is unavailable or ambiguous')
        pin = pins[0]
        path = D._scope(item['consumed_path'])
        D._require(path.as_posix() != '.' and path.is_relative_to(D._scope(consumer['area']['scope'])),
                   'Consumed artifact path escapes the exact consumer area')
        links = ledger['outcomes']

        def verified_link(field, assignment):
            link_id = item.get(field)
            record = links.get(link_id)
            if (prior and assignment['id'] in prior['unaffected'] and record
                    and _plan_identity(record) == _plan_identity(prior['previous'])):
                return self._check_record(links, link_id, assignment, prior['previous'], registry, bindings)
            return self._check_record(links, link_id, assignment, selector, registry, bindings)

        produced = verified_link('producer_link', producer)
        # An affected consumer can use an unchanged producer's approved bytes, but requires its own new check.
        used = verified_link('consumer_link', consumer)
        producer_state, consumer_state = 'unrecorded', 'unrecorded'
        artifact = check = None
        preliminary = pin['strength'] == 'provisional'
        required_check = pin['preliminary_check'] if preliminary else consumer['check']
        if produced:
            matches = [value for value in produced['artifacts'] if value['artifact_id'] == item['artifact_id']]
            D._require(len(matches) == 1 and matches[0]['sha256'] == pin['sha256'],
                       'Accepted producer artifact does not match the exact pinned revision digest')
            artifact = matches[0]
            artifact_path = D._scope(artifact['path'])
            D._require(artifact_path != D._scope('.') and artifact_path.is_relative_to(D._scope(producer['area']['scope'])),
                       'Accepted artifact path escapes the exact producer area')
            producer_state = 'accepted' if (produced['completion'] == 'completed' and produced['link_state'] == 'verified'
                                            and produced['evidence_availability'] == 'available'
                                            and produced['source_freshness'] == 'current') else 'unavailable-or-stale'
        if used:
            matches = [value for value in used['checks'] if value['check_id'] == required_check]
            if matches:
                check = matches[0]
                D._require(check['source_fingerprints'].get(str(path)) == pin['sha256'],
                           'The exact consumer check did not fingerprint the accepted artifact bytes')
                if check['verdict'] != 'pass':
                    consumer_state = 'failed'
                elif (used['link_state'] == 'verified' and check['source_freshness'] == 'current'
                      and check['evidence_availability'] == 'available'):
                    consumer_state = 'verified'
                else:
                    consumer_state = 'unavailable-or-stale'
            else:
                consumer_state = 'missing-check'
        passed = producer_state == 'accepted' and consumer_state == 'verified' and pin['status'] == 'verified'
        if passed:
            integration = 'preliminary' if preliminary else 'verified'
        else:
            integration = 'optional-unverified' if pin['strength'] == 'optional' else 'held'
        references = {role: {field: record[field] for field in ('link_id', 'task_id', 'run_id', 'outcome_id', 'outcome_sha256',
                                                                  'plan_id', 'plan_revision', 'plan_sha256')}
                      for role, record in (('producer', produced), ('consumer', used)) if record is not None}
        return {'edge_id': item['edge_id'], 'producer': producer['id'], 'consumer': consumer['id'],
                'pin': pin, 'producer_owner': {field: producer['area'][field] for field in AREA_ID},
                'artifact': artifact, 'consumed_path': str(path), 'check': check, 'required_check': required_check,
                'outcomes': references,
                'producer_state': producer_state, 'consumer_state': consumer_state, 'integration': integration,
                'delivery': {'producer': produced['delivery'] if produced else 'unknown',
                             'consumer': used['delivery'] if used else 'unknown'}}

    def review_preview(self, request):
        D._object(request, {'plan', 'edges'})
        plan, ledger, registry, bindings, _ = self._load(request['plan'])
        D._require(isinstance(request['edges'], list), 'Handoff review requires exact selected edges')
        assignments = {item['id']: item for item in plan['assignments']}
        amendments_in = list(self._amendments(request['plan'], endpoint='next'))
        D._require(len(amendments_in) <= 1, 'Current plan has conflicting approved amendment receipts')
        prior = amendments_in[0] if amendments_in else None
        rows = [self._edge(item, assignments, request['plan'], ledger, registry, bindings, prior)
                for item in request['edges']]
        keys = [(row['consumer'], _pin_identity(row['pin'])) for row in rows]
        D._require(len(set(keys)) == len(rows) and len({row['edge_id'] for row in rows}) == len(rows), 'Duplicate handoff edge')
        covered = set(keys)
        missing = [{'consumer': item['id'], 'pin': pin} for item in assignments.values() for pin in item['pins']
                   if pin['area_id'] != item['area']['id'] and pin['strength'] != 'optional'
                   and (item['id'], _pin_identity(pin)) not in covered]
        amendments = list(self._amendments(request['plan']))
        for row in rows:
            superseded = [amendment['preview_sha256'] for amendment in amendments
                          if row['consumer'] in amendment['affected'] or row['producer'] in amendment['affected']]
            if superseded:
                row['integration'] = 'superseded'
                row['superseded_by'] = superseded
        gates = [row for row in rows if row['pin']['strength'] != 'optional']
        ready = bool(gates) and not missing and all(row['integration'] == 'verified' for row in gates)
        current = ledger['current'] == {'revision': plan['objective']['objective_revision'],
                                        'sha256': plan['objective']['objective_sha256']}
        predecessor = f"{plan['plan_id']}/{plan['plan_revision'] - 1}"
        amend_ready = prior is not None or predecessor not in ledger['plans']
        result = {'schema': 1, 'kind': 'director-handoff-review', 'plan': request['plan'],
                  'edges': sorted(rows, key=lambda row: row['edge_id']), 'missing_coverage': missing,
                  'objective_current': current, 'amendment_current': amend_ready,
                  'parent_acceptance': 'eligible' if ready and current and amend_ready else 'held'}
        return {**result, 'preview_sha256': D._digest(result)}

    def impact_preview(self, request):
        D._object(request, {'previous', 'next'})
        older, _, _, _, _ = self._load(request['previous'])
        newer, ledger, registry, bindings, _ = self._load(request['next'])
        D._require(older['plan_id'] == newer['plan_id'] and older['objective']['objective_id'] == newer['objective']['objective_id']
                   and newer['plan_revision'] == older['plan_revision'] + 1, 'An amendment requires consecutive exact revisions of one plan')
        D._require(ledger['current'] == {'revision': newer['objective']['objective_revision'],
                                        'sha256': newer['objective']['objective_sha256']}, 'Next frozen objective is not current')
        left = {item['id']: item for item in older['assignments']}
        right = {item['id']: item for item in newer['assignments']}
        direct = sorted(name for name in left.keys() | right.keys() if left.get(name) != right.get(name))
        affected = _reverse(left, right, direct)
        blockers = [{'reason': 'previous-plan-already-amended', 'archive_id': amendment['preview_sha256']}
                    for amendment in self._amendments(request['previous'])]
        observations, writer_blockers = self._writers(left, right, affected, registry, bindings, request)
        blockers.extend(writer_blockers)
        blockers.extend(_replacements(left, right, direct))
        changes = []
        for name in direct:
            before = {_pin_identity(pin): pin for pin in left.get(name, {}).get('pins', [])}
            after = {_pin_identity(pin): pin for pin in right.get(name, {}).get('pins', [])}
            changes.extend({'assignment_id': name, 'previous': before.get(key), 'next': after.get(key)}
                           for key in sorted(before.keys() | after.keys()) if before.get(key) != after.get(key))
        result = {'schema': 1, 'kind': 'director-handoff-amendment', 'previous': request['previous'], 'next': request['next'],
                  'direct_changes': direct, 'pin_changes': changes, 'affected': affected,
                  'unaffected': sorted((left.keys() & right.keys()) - affected.keys()),
                  'writer_observations': observations, 'blockers': blockers}
        return {**result, 'preview_sha256': D._digest(result)}

    def _dispatch_blockers(self, child, spec, director_id, plan_sha):
        task = spec['child'].get('task_id', '')
        effects = set(spec.get('effects', ()))
        intake = not task and 'intake' in effects
        process = (task.startswith('P-') or intake) and 'process' in effects
        start = (task.startswith('T-') or process) and 'launch' in effects and spec['workspace'] == 'recorded-worktree'
        if not (intake or process or start):
            return []
        helper = D.WF.director_dispatch_helper()
        envelope = {'schema': 1, 'director_id': director_id, 'assignment_id': spec['id'],
                    'queue_id': spec['area']['queue_id'], 'plan_sha256': plan_sha}
        blockers = []
        for operation, reachable in (('intake', intake), ('process', process), ('start', start)):
            if reachable:
                claim = helper.conflicting_plan_claim(self.store, child, operation, envelope)
                if claim:
                    blockers.append({'assignment_id': spec['id'], 'operation': operation,
                                     'queue_id': envelope['queue_id'], 'reason': 'dispatch-identity-already-claimed',
                                     **claim})
        return blockers

    def _writers(self, left, right, affected, registry, bindings, request):
        targets = {}
        blockers = []
        previous = request['previous']
        inherited = set(affected)
        affected_by_plan = {previous['plan_sha256']: inherited}
        for amendment in self._amendment_chain(previous, endpoint='next'):
            inherited = inherited.intersection(amendment['unaffected'])
            if not inherited:
                break
            affected_by_plan[amendment['previous']['plan_sha256']] = inherited
        directory = D._safe_path(self.root, RUNS)
        for path in sorted(directory.glob('dr-*.json')):
            record, _ = D._read(self.root, f'{RUNS}/{path.name}')
            for name in sorted(affected_by_plan.get(record['plan_sha256'], set()) & record['assignments'].keys()):
                state = record['assignments'][name]
                if not state.get('completed') and record['phase'] not in {'paused', 'cancelled'}:
                    blockers.append({'assignment_id': name, 'reason': 'director-writer-requires-pause',
                                     'director_run_id': record['director_run_id']})
                for operation, launch in sorted(state['dispatches'].items()):
                    if launch.get('status') in {'prepared', 'invoking'}:
                        blockers.append({'assignment_id': name, 'reason': 'dispatch-awaits-reconciliation',
                                         'operation': operation, 'director_run_id': record['director_run_id']})
                    if operation == 'start' and launch.get('status') == 'recorded':
                        key = (name, left[name]['area']['id'])
                        targets.setdefault(key, set()).add(launch['result']['id'])
        observations = []
        for name in affected:
            by_area = {}
            for spec in (left.get(name), right.get(name)):
                if spec:
                    by_area.setdefault(spec['area']['id'], set()).add(spec['child'].get('task_id'))
            for area_id, task_ids in sorted(by_area.items()):
                try:
                    root = O._child_root(registry, bindings, area_id)
                    child_store = D.WF.Store(root, route_queue=False, neutral=True)
                    child = child_store.load()
                    claims = ['.skill-tree/.transaction.json', '.skill-tree/installation/.install-lock']
                    if root != self.root or not getattr(self.store, '_writer_active', False):
                        claims.append('.skill-tree/.writer-lock')
                    if any(D._safe_path(root, path).exists() for path in claims):
                        blockers.append({'assignment_id': name, 'area_id': area_id, 'reason': 'child-writer-in-progress'})
                    next_spec = right.get(name)
                    if next_spec and next_spec['area']['id'] == area_id:
                        D._require(child['run_registry']['queue_id'] == next_spec['area']['queue_id'],
                                   'Replacement child queue changed')
                        blockers.extend(self._dispatch_blockers(child_store, next_spec, registry['director_id'],
                                                                request['next']['plan_sha256']))
                    runs = child['run_registry']['runs']
                    launched = targets.get((name, area_id), set())
                    for unknown in sorted(launched - runs.keys()):
                        blockers.append({'assignment_id': name, 'run_id': unknown, 'reason': 'child-writer-state-unknown'})
                    for run_id, run_record in sorted(runs.items()):
                        if not (task_ids.intersection(run_record['admitted_task_ids']) or run_id in launched):
                            continue
                        if D.WS.delivery_finished(run_record):
                            continue
                        active_checks = any(D.WF.pending_check_attempt(slot) for tid in run_record['admitted_task_ids']
                                            for slot in child['task_progress'].get(tid, {}).get('checks', {}).values())
                        workspace = O._read_run_root(root, run_record)
                        stopped = bool(workspace and run_record.get('stop_reason') and not run_record.get('maintenance')
                                       and not active_checks)
                        observations.append({'assignment_id': name, 'area_id': area_id, 'run_id': run_id, 'stopped': stopped,
                                             'checkpoint_sha256': D._digest(run_record)})
                        if not stopped:
                            blockers.append({'assignment_id': name, 'run_id': run_id, 'reason': 'child-writer-requires-handoff'})
                except (KeyError, ValueError, OSError, subprocess.TimeoutExpired):
                    blockers.append({'assignment_id': name, 'area_id': area_id, 'reason': 'child-writer-state-unknown'})
        return observations, blockers

    def _archive(self, command, payload, preview):
        D._object(payload, {'request', 'expected_preview_sha256', 'owner_ref'})
        guard, owner = payload['expected_preview_sha256'], payload['owner_ref']
        D._require(D._sha(guard) and D._token(owner), 'Archive requires an exact reviewed preview and owner reference')
        relative = f'{ARCHIVE}/{guard}.json'
        operation = {'kind': command, 'sha256': D._digest(payload)}
        request_sha = D._digest(operation)
        with self.store.lock(local_delivery=operation):
            archived, prior = D._read(self.root, relative)
            if archived is not None:
                D._require(archived['request_sha256'] == request_sha, 'Existing review has a different request or owner')
                return self._archive_record(archived, guard)
            report = preview(payload['request'])
            D._require(report['preview_sha256'] == guard, 'Handoff inputs or writer observations changed since preview')
            D._require(not report.get('blockers'), 'Affected writers must reach a verified stopped handoff and amendment gates must pass')
            record = {'schema': 1, 'recorded_at': D.WF.now(), 'archive_id': guard, 'owner_ref': owner,
                      'request_sha256': request_sha, 'request': deepcopy(payload['request']), 'observation': report}
            self.store.expect_unchanged(relative, prior)
            self.store.commit({relative: D.WF.dump(record)})
            return record

    def run(self, command, payload):
        if command == 'review-preview':
            return self.review_preview(payload)
        if command == 'impact-preview':
            return self.impact_preview(payload)
        if command == 'review-read':
            D._object(payload, {'archive_id'})
            D._require(D._sha(payload['archive_id']), 'Read requires one exact archived review identity')
            record, _ = D._read(self.root, f'{ARCHIVE}/{payload["archive_id"]}.json')
            D._require(record is not None and record['archive_id'] == payload['archive_id'], 'Archived review is unavailable')
            return self._archive_record(record, payload['archive_id'])
        return self._archive(command, payload, self.review_preview if command == 'review-apply' else self.impact_preview)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('review-preview', 'review-apply', 'review-read', 'impact-preview', 'amend-apply'))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', required=True, type=Path)
    args = parser.parse_args()
    registry = D.DirectorRegistry(args.root)
    try:
        result = DirectorHandoffs(registry, D._plan_helper(registry)).run(args.command, json.loads(args.input.read_text()))
    except (KeyError, ValueError, OSError, TypeError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f'{error}\n')
    print(D.WF.dump(result), end='')


if __name__ == '__main__':
    main()
