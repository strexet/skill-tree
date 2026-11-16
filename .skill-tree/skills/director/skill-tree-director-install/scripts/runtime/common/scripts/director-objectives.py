"""Record parent objectives and references to immutable child outcomes."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


DIRECTORY = '.skill-tree/director/objectives/'
COMMANDS = {'objective-preview', 'objective-apply', 'objective-read', 'plan-pin', 'outcome-link'}
OUTCOME_LEDGER = '.skill-tree/history/task-outcomes.jsonl'


def objective_path(objective_id):
    D._require(D.WF.valid_id(objective_id, 'OB'), 'Select an exact Director objective ID')
    return DIRECTORY + objective_id.lower() + '.json'


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def _intent(intent):
    D._object(intent, {'owner_ref', 'title', 'description', 'acceptance'})
    D._require(D._token(intent['owner_ref']) and _text(intent['title']) and _text(intent['description']),
               'Objective requires a portable owner reference, title and original description')
    criteria = intent['acceptance']
    D._require(isinstance(criteria, list) and criteria, 'Objective requires observable acceptance criteria')
    ids = set()
    for record in criteria:
        D._object(record, {'id', 'criterion'})
        D._require(D._token(record['id']) and _text(record['criterion']) and record['id'] not in ids,
                   'Acceptance criteria require unique portable IDs and observable text')
        ids.add(record['id'])
    return intent


def _positive(value):
    return type(value) is int and value > 0


def _stored_ledger(ledger, director_id, objective_id):
    D._object(ledger, {'schema', 'director_id', 'objective_id', 'current', 'revisions', 'plans', 'outcomes', 'receipts'})
    D._require(ledger['schema'] == 1 and ledger['director_id'] == director_id and ledger['objective_id'] == objective_id
               and isinstance(ledger['revisions'], list) and ledger['revisions']
               and isinstance(ledger['plans'], dict) and isinstance(ledger['outcomes'], dict)
               and isinstance(ledger['receipts'], dict), 'Unsupported Director objective ledger')
    for expected, revision in enumerate(ledger['revisions'], start=1):
        D._object(revision, {'revision', 'sha256', 'recorded_at', 'intent'})
        D._require(type(revision['revision']) is int and revision['revision'] == expected
                   and revision['sha256'] == _revision_digest(expected, _intent(revision['intent'])),
                   'Recorded objective revision digest changed')
    latest = ledger['revisions'][-1]
    D._require(ledger['current'] == _revision_pin(latest), 'Current objective revision differs from history')
    return ledger


def _revision_digest(number, intent):
    return D._digest({'revision': number, 'intent': intent})


def _revision_pin(revision):
    return {key: revision[key] for key in ('revision', 'sha256')}


def _plan_key(plan_id, plan_revision):
    D._require(D.WF.valid_id(plan_id, 'PL') and _positive(plan_revision), 'Select an exact versioned plan')
    return f'{plan_id}/{plan_revision}'


def _area_identity(area):
    return {key: area[key] for key in ('id', 'queue_id', 'repo_id', 'scope')}


def _child_root(registry, bindings, area_id):
    area = registry['areas'].get(area_id)
    D._require(area is not None and bindings is not None, 'Child area or local queue binding unavailable')
    binding = bindings['queues'].get(area['queue_id'])
    D._require(binding is not None, 'Child area or local queue binding unavailable')
    queue_id, repo_id, observed = D._inspect_owner(D._root(binding['root']))
    D._require(observed == binding and (queue_id, repo_id) == (area['queue_id'], area['repo_id']),
               'Current child queue binding does not match the registered owner')
    root = Path(observed['root'])
    D._area_path(root, area['scope'])
    return root


def _exact_outcome(root, task_id, outcome_id, run_id):
    path = D._safe_path(root, OUTCOME_LEDGER)
    D._require(path.is_file(), 'Canonical child outcome ledger unavailable')
    outcomes = [json.loads(line) for line in path.read_bytes().splitlines() if line.strip()]
    matches = [outcome for outcome in outcomes if outcome.get('id') == outcome_id or outcome.get('task_id') == task_id]
    D._require(len(matches) == 1 and matches[0].get('id') == outcome_id and matches[0].get('task_id') == task_id
               and matches[0].get('run_id') == run_id, 'Canonical child outcome identity is absent or ambiguous')
    outcome = matches[0]
    state = D.WF.Store(root, route_queue=False, neutral=True).load()
    run = state['run_registry']['runs'].get(run_id)
    D._require(run is not None and run.get('completion_refs', {}).get(task_id) == outcome_id,
               'Canonical child run does not name the outcome')
    return outcome, run


def _read_run_root(root, run):
    locator = D.WS.runtime(root)
    location = locator['worktrees'].get(run['id']) if locator else None
    if not location:
        return None
    try:
        worktree = D._root(location)
        workspace = run.get('workspace', {})
        if (D.WS.common_dir(worktree) == D.WS.common_dir(root)
                and D.WS.local_git_text(worktree, 'rev-parse', '--show-toplevel') == str(worktree)
                and D.WS.local_git_text(worktree, 'symbolic-ref', '--quiet', '--short', 'HEAD') == workspace.get('branch')
                and D.WS.repo_id(worktree) == workspace.get('repo_id')):
            return worktree
    except (ValueError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def _evidence_pointer(reference):
    return isinstance(reference, dict) and D._sha(reference.get('sha256')) and _text(reference.get('path'))


def _current_hash(root, relative):
    if root is None:
        return None
    path = D._safe_path(root, relative)
    if path.is_dir():
        return D.WF.binding_snapshot(root, [relative])
    return D.WF.file_hash(path) if path.is_file() else None


def _record_checks(outcome, check_ids):
    observed = []
    for check_id in check_ids:
        matches = [entry for entry in outcome.get('check_results', []) if entry.get('check', {}).get('id') == check_id]
        D._require(len(matches) == 1, 'Exact child check is unavailable or ambiguous')
        result = matches[0].get('result', {})
        evidence = result.get('evidence')
        D._require(D._sha(result.get('key')) and _text(result.get('result')) and _text(result.get('actual_lane'))
                   and isinstance(evidence, list) and evidence and all(_evidence_pointer(item) for item in evidence)
                   and isinstance(result.get('sources'), dict), 'Exact child check lacks recorded result evidence')
        observed.append({'check_id': check_id, 'check_key': result['key'], 'verdict': result['result'],
                         'lane': result['actual_lane'], 'source_fingerprints': result['sources'],
                         'evidence': [{key: item[key] for key in ('path', 'sha256')} for item in evidence]})
    return observed


def _record_artifacts(outcome, artifacts):
    accepted = {(item['path'], item['sha256']) for criterion in outcome.get('acceptance', [])
                if criterion.get('result') == 'pass' for item in criterion.get('evidence', []) if _evidence_pointer(item)}
    D._require(isinstance(artifacts, list), 'Artifact references require a list')
    ids = set()
    for item in artifacts:
        D._object(item, {'artifact_id', 'path', 'sha256'})
        D._require(D._token(item['artifact_id']) and item['artifact_id'] not in ids
                   and _evidence_pointer(item) and (item['path'], item['sha256']) in accepted,
                   'Artifact reference does not match exact child acceptance evidence')
        D._scope(item['path'])
        ids.add(item['artifact_id'])
    return artifacts


def _evidence_states(root, references):
    values = []
    for item in references:
        try:
            actual = _current_hash(root, item['path'])
        except (OSError, ValueError):
            actual = None
        values.append('unavailable' if actual is None else 'available' if actual == item['sha256'] else 'changed')
    return ('unavailable' if 'unavailable' in values else 'changed' if 'changed' in values else
            'available' if values else 'unrecorded')


def _freshness(root, fingerprints):
    if root is None or not fingerprints:
        return 'unknown'
    try:
        actual = {relative: _current_hash(root, relative) for relative in fingerprints}
    except (OSError, ValueError):
        return 'unknown'
    if any(value is None for value in actual.values()):
        return 'unknown'
    return 'current' if actual == fingerprints else 'stale'


def _view_link(record, registry, bindings):
    result = {**record, 'link_state': 'unavailable', 'evidence_availability': 'unavailable',
              'source_freshness': 'unknown', 'integration': 'unverified', 'delivery': 'unknown'}
    try:
        area_id = record['area']['id']
        if _area_identity(registry['areas'][area_id]) != record['area']:
            return {**result, 'link_state': 'changed'}
        root = _child_root(registry, bindings, area_id)
        outcome, run = _exact_outcome(root, record['task_id'], record['outcome_id'], record['run_id'])
        if D._digest(outcome) != record['outcome_sha256']:
            return {**result, 'link_state': 'changed'}
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
        return result
    worktree = _read_run_root(root, run)
    evidence = [*record['artifacts'], *(item for check in record['checks'] for item in check['evidence'])]
    result.update(link_state='verified', evidence_availability=_evidence_states(worktree, evidence),
                  source_freshness=_freshness(worktree, record['source_fingerprints']),
                  delivery=run.get('delivery', {}).get('status', 'unknown'))
    result['checks'] = [{**check, 'evidence_availability': _evidence_states(worktree, check['evidence']),
                         'source_freshness': _freshness(worktree, check['source_fingerprints'])}
                        for check in record['checks']]
    return result


class ObjectiveLedger:
    """The Director parent is the only writer of objective history and indexes."""

    def __init__(self, registry):
        self.registry = registry
        self.root = registry.root
        self.store = registry.store

    def _load(self, objective_id, *, create=False):
        relative = objective_path(objective_id)
        registry, bindings, basis = self.registry._load()
        D._require(registry is not None, 'Register the Director before recording objectives')
        ledger, ledger_sha = D._read(self.root, relative)
        if ledger is None:
            D._require(create, 'Exact Director objective is unavailable')
            ledger = {'schema': 1, 'director_id': registry['director_id'], 'objective_id': objective_id,
                      'current': None, 'revisions': [], 'plans': {}, 'outcomes': {}, 'receipts': {}}
        else:
            _stored_ledger(ledger, registry['director_id'], objective_id)
        return ledger, registry, bindings, {**basis, relative: ledger_sha}

    def _preview(self, request, ledger, basis):
        D._object(request, {'objective_id', 'expected_current_sha256', 'intent'})
        expected = request['expected_current_sha256']
        D._require(expected is None or D._sha(expected), 'Objective update requires the exact current digest')
        current = ledger['current']
        D._require(expected == (current or {}).get('sha256'), 'Objective basis changed since inspection')
        intent = _intent(request['intent'])
        changed = not current or ledger['revisions'][-1]['intent'] != intent
        number = (current or {}).get('revision', 0) + changed
        proposed = {'revision': number, 'sha256': _revision_digest(number, intent)}
        report = {'schema': 1, 'director_id': ledger['director_id'], 'objective_id': ledger['objective_id'],
                  'current': current, 'proposed': proposed, 'intent': intent, 'changed': changed}
        return {**report, 'preview_sha256': D._digest({'report': report, 'basis': basis})}

    def preview(self, request):
        D._object(request, {'objective_id', 'expected_current_sha256', 'intent'})
        ledger, _, _, basis = self._load(request['objective_id'], create=True)
        return self._preview(request, ledger, basis)

    def _write(self, operation, request, reconcile):
        relative = objective_path(request['objective_id'])
        request_sha = D._digest({'operation': operation, 'request': request})
        owner = {'kind': 'director-objective', 'objective_id': request['objective_id'], 'request_sha256': request_sha}
        with self.store.lock(local_delivery=owner):
            ledger, registry, bindings, basis = self._load(request['objective_id'], create=operation == 'objective-apply')
            previous = ledger['receipts'].get(request_sha)
            if previous is not None:
                return {**previous, 'status': 'replayed', 'ledger_sha256': basis[relative]}
            result = reconcile(ledger, registry, bindings, basis)
            report = {'objective_id': request['objective_id'], 'current': ledger['current'], **result}
            if result['status'] == 'unchanged':
                return {**report, 'ledger_sha256': basis[relative]}
            for path, sha in basis.items():
                self.store.expect_unchanged(path, sha)
            ledger['receipts'][request_sha] = report
            content = D.WF.dump(ledger)
            self.store.commit({relative: content})
            return {**report, 'ledger_sha256': D.WF.digest(content.encode())}

    def apply(self, payload):
        D._object(payload, {'objective_id', 'expected_current_sha256', 'intent', 'expected_preview_sha256'})
        D._require(D._sha(payload['expected_preview_sha256']), 'Objective apply requires a reviewed preview digest')
        request = {key: value for key, value in payload.items() if key != 'expected_preview_sha256'}

        def revise(ledger, _registry, _bindings, basis):
            preview = self._preview(request, ledger, basis)
            D._require(preview['preview_sha256'] == payload['expected_preview_sha256'], 'Objective preview changed')
            if not preview['changed']:
                return {'status': 'unchanged'}
            ledger['current'] = preview['proposed']
            ledger['revisions'].append({**ledger['current'], 'recorded_at': D.WF.now(), 'intent': preview['intent']})
            return {'status': 'applied', 'preview_sha256': preview['preview_sha256']}

        return self._write('objective-apply', payload, revise)

    def pin_plan(self, payload):
        D._object(payload, {'objective_id', 'expected_ledger_sha256', 'plan_id', 'plan_revision', 'plan_sha256',
                            'objective_revision', 'objective_sha256', 'assignments'})
        key = _plan_key(payload['plan_id'], payload['plan_revision'])
        D._require(all(D._sha(payload[field]) for field in ('expected_ledger_sha256', 'plan_sha256', 'objective_sha256'))
                   and _positive(payload['objective_revision']), 'Plan pin requires exact objective and ledger digests')

        def record(ledger, registry, bindings, basis):
            D._require(basis[objective_path(payload['objective_id'])] == payload['expected_ledger_sha256'],
                       'Objective ledger basis changed since inspection')
            expected = {'revision': payload['objective_revision'], 'sha256': payload['objective_sha256']}
            D._require(ledger['current'] == expected, 'Plan pin requires the current exact objective revision')
            assignments = payload['assignments']
            D._require(isinstance(assignments, dict) and assignments, 'Plan pin requires exact assignment references')
            pinned = {}
            for assignment, reference in assignments.items():
                D._require(D._token(assignment), 'Assignment ID requires a portable token')
                D._object(reference, {'area_id', 'task_ids'})
                area_id = reference['area_id']
                D._require(D._token(area_id) and area_id in registry['areas'], 'Assignment names an unregistered area')
                _child_root(registry, bindings, area_id)
                tids = reference['task_ids']
                D._require(isinstance(tids, list) and all(D.WF.valid_id(task, 'T') for task in tids)
                           and len(set(tids)) == len(tids), 'Assignment references require exact unique T IDs')
                pinned[assignment] = {'area': _area_identity(registry['areas'][area_id]), 'task_ids': tids}
            pin = {field: payload[field] for field in ('plan_id', 'plan_revision', 'plan_sha256')}
            pin.update(objective_revision=expected['revision'], objective_sha256=expected['sha256'], assignments=pinned)
            if key in ledger['plans']:
                D._require(ledger['plans'][key] == pin, 'Plan identity already pins different content')
                return {'status': 'unchanged', 'plan': pin}
            ledger['plans'][key] = pin
            return {'status': 'pinned', 'plan': pin}

        return self._write('plan-pin', payload, record)

    def link_outcome(self, payload):
        D._object(payload, {'objective_id', 'expected_ledger_sha256', 'plan_id', 'plan_revision', 'plan_sha256',
                            'assignment_id', 'area_id', 'task_id', 'run_id', 'outcome_id', 'artifacts', 'check_ids'})
        plan_key = _plan_key(payload['plan_id'], payload['plan_revision'])
        D._require(D._sha(payload['expected_ledger_sha256']) and D._sha(payload['plan_sha256'])
                   and D._token(payload['assignment_id']) and D._token(payload['area_id'])
                   and all(D.WF.valid_id(payload[field], prefix) for field, prefix in
                           (('task_id', 'T'), ('run_id', 'WR'), ('outcome_id', 'O'))), 'Outcome link requires exact identities')
        check_ids = D._tokens(payload['check_ids'], 'Outcome check IDs')

        def record(ledger, registry, bindings, basis):
            D._require(basis[objective_path(payload['objective_id'])] == payload['expected_ledger_sha256'],
                       'Objective ledger basis changed since inspection')
            plan = ledger['plans'].get(plan_key)
            D._require(plan is not None and plan['plan_sha256'] == payload['plan_sha256'], 'Exact plan pin is unavailable')
            assignment = plan['assignments'].get(payload['assignment_id'])
            area_id = payload['area_id']
            D._require(assignment is not None and assignment['area']['id'] == area_id
                       and payload['task_id'] in assignment['task_ids'], 'Child task is not pinned to this assignment')
            D._require(assignment['area'] == _area_identity(registry['areas'][area_id]), 'Plan area owner changed')
            root = _child_root(registry, bindings, area_id)
            outcome, run = _exact_outcome(root, payload['task_id'], payload['outcome_id'], payload['run_id'])
            D._require(outcome.get('disposition') == 'completed' and payload['task_id'] in run['completed_ids'],
                       'Child outcome does not establish completion')
            artifact_refs = _record_artifacts(outcome, payload['artifacts'])
            checks = _record_checks(outcome, check_ids)
            pins = outcome.get('source_fingerprints')
            D._require(isinstance(pins, dict) and pins and all(D._sha(sha) for sha in pins.values()),
                       'Child outcome lacks immutable source fingerprints')
            for relative in [*pins, *(path for check in checks for path in check['source_fingerprints']),
                             *(ref['path'] for check in checks for ref in check['evidence'])]:
                D._scope(relative)
            link = {field: payload[field] for field in ('plan_id', 'plan_revision', 'plan_sha256', 'assignment_id',
                                                       'task_id', 'run_id', 'outcome_id')}
            link.update(area=assignment['area'], outcome_sha256=D._digest(outcome), completion='completed',
                        artifacts=artifact_refs, checks=checks, source_fingerprints=pins,
                        objective_revision=plan['objective_revision'], objective_sha256=plan['objective_sha256'])
            link_id = D._digest({'plan': plan_key, 'assignment': link['assignment_id'], 'task': link['task_id'],
                                 'run': link['run_id'], 'outcome': link['outcome_id']})
            previous = ledger['outcomes'].get(link_id)
            if previous is not None:
                D._require(previous == link, 'The outcome link already pins different evidence')
                return {'status': 'unchanged', 'link_id': link_id}
            ledger['outcomes'][link_id] = link
            return {'status': 'linked', 'link_id': link_id}

        return self._write('outcome-link', payload, record)

    def read(self, payload):
        D._object(payload, {'objective_id'}, {'revision'})
        ledger, registry, bindings, basis = self._load(payload['objective_id'])
        revision = payload.get('revision', ledger['current']['revision'])
        D._require(_positive(revision) and revision <= len(ledger['revisions']), 'Exact objective revision is unavailable')
        plans = [plan for plan in ledger['plans'].values() if plan['objective_revision'] == revision]
        outcomes = [_view_link({'link_id': link_id, **link}, registry, bindings) for link_id, link in
                    ledger['outcomes'].items() if link['objective_revision'] == revision]
        return {'schema': 1, 'director_id': ledger['director_id'], 'objective_id': ledger['objective_id'],
                'current': ledger['current'], 'revision': ledger['revisions'][revision - 1],
                'plans': plans, 'outcomes': outcomes, 'ledger_sha256': basis[objective_path(payload['objective_id'])]}


def run(registry, command, payload):
    ledger = ObjectiveLedger(registry)
    methods = {'objective-preview': ledger.preview, 'objective-apply': ledger.apply, 'objective-read': ledger.read,
               'plan-pin': ledger.pin_plan, 'outcome-link': ledger.link_outcome}
    return methods[command](payload)
