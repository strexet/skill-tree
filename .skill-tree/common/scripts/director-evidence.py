"""Adopt scoped existing evidence and retain reproducible product milestones."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys


def _handoff_module():
    path = Path(__file__).with_name('director-handoff.py')
    spec = importlib.util.spec_from_file_location('director_evidence_handoff', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


H = _handoff_module()
D, O = H.D, H.O
ARCHIVE = '.skill-tree/director/evidence'
SELECTOR = {'objective_id', 'plan_id', 'plan_revision', 'plan_sha256'}
CANDIDATES = {'child-run': set(), 'artifact': {'artifact'}, 'commit': {'commit'},
              'owner-decision': {'decision', 'actor'}}
COMMANDS = {'adopt-preview', 'adopt-apply', 'adopt-read', 'milestone-preview', 'milestone-apply', 'milestone-read'}
ROLES = {'story': {'story', 'narrative'}, 'art': {'art', '3d'}, 'game': {'game', 'unity'},
         'public': {'public', 'web', 'website', 'blog'}}


class DirectorEvidence:
    def __init__(self, root):
        self.registry = D.DirectorRegistry(root)
        self.root = self.registry.root
        self.planner = D._plan_helper(self.registry)
        self.handoffs = H.DirectorHandoffs(self.registry, self.planner)

    def selection(self, selected):
        D._object(selected, SELECTOR)
        plan, digest = self.planner.frozen({key: selected[key] for key in SELECTOR - {'plan_sha256'}})
        D._require(digest == selected['plan_sha256'], 'Select the exact frozen plan digest')
        ledger, areas, bindings, _ = self.planner.ledger._load(selected['objective_id'])
        current = ledger['current'] == {'revision': plan['objective']['objective_revision'],
                                       'sha256': plan['objective']['objective_sha256']}
        return plan, current, ledger, areas, bindings

    def _inflight(self, plan, selected, assignment):
        queue_id = assignment['area']['queue_id']
        selector = {'director_id': plan['director_id'], 'assignment_id': assignment['id'],
                    'queue_id': queue_id, 'plan_sha256': selected['plan_sha256'], 'schema': 1}
        dispatch = D.WF.director_dispatch_helper()
        for operation in ('intake', 'process', 'start'):
            _, key = dispatch.envelope(operation, selector)
            existing, _ = D._read(self.root, f'{dispatch.PARENT_INTENTS}/{key}.json')
            if existing is not None and existing['plan_sha256'] == selected['plan_sha256']:
                return True
        directory = D._safe_path(self.root, '.skill-tree/director/runs')
        for path in sorted(directory.glob('dr-*.json')):
            record, _ = D._read(self.root, f'.skill-tree/director/runs/{path.name}')
            if record['plan_sha256'] == selected['plan_sha256']:
                if record['assignments'].get(assignment['id'], {}).get('dispatches'):
                    return True
        return False

    def _pins(self, assignment, areas, bindings, check=None):
        adapter = D.WF.owned_module('director_evidence_sources', Path(__file__).with_name('director-plan-adapters.py'))
        sources = adapter.PlanSources(D, O, self.planner.C, areas, bindings)
        confirmed, missing = [], []
        for pin in assignment['pins']:
            info = sources.pin(areas['areas'][pin['area_id']], {name: value for name, value in pin.items() if name != 'status'})
            if info == {'status': 'verified', 'revision': pin['revision'], 'sha256': pin['sha256']}:
                if (check is None or pin['adapter'] != adapter.GDD_FIXTURE
                        or self._check_gdd_fixture_input(assignment, check, pin['sha256'])):
                    confirmed.append(pin)
                    continue
                info = {'status': 'consumer-input-mismatch'}
            if pin['strength'] != 'optional':
                missing.append({'record_id': pin['record_id'], 'status': info['status']})
        return confirmed, missing

    @staticmethod
    def _check_covers_area(assignment, check):
        scope = D._scope(assignment['area']['scope'])
        return any(D._scope(path).is_relative_to(scope) for path in check['source_fingerprints'])

    @staticmethod
    def _check_gdd_fixture_input(assignment, check, sha256):
        scope = D._scope(assignment['area']['scope'])
        scoped_inputs = [digest for path, digest in check['source_fingerprints'].items()
                         if D._scope(path).is_relative_to(scope)]
        # A supplemental copy cannot stand in for the rule the check actually observes.
        return scoped_inputs == [sha256]

    def _write_paths(self, assignment, paths):
        allowed = [D._scope(assignment['area']['scope']) / D._scope(value) for value in assignment['write_paths']]
        return bool(paths and allowed and all(any(path.is_relative_to(scope) for scope in allowed) for path in paths))

    def _check_commit(self, root, candidate, outcome, run, assignment):
        oid = candidate['commit']
        D._require(isinstance(oid, str) and re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', oid),
                   'Adoption requires a full immutable commit object ID')
        commits = {item.get('commit', item.get('oid')) if isinstance(item, dict) else item
                   for item in outcome.get('commits', [])}
        D._require(oid in commits and D.WS.local_git_text(root, 'rev-parse', '--verify', oid + '^{commit}') == oid,
                   'Commit is not recorded by the exact adopted outcome')
        worktree = O._read_run_root(root, run)
        D._require(worktree and D.WS.local_git(worktree, 'merge-base', '--is-ancestor', oid, 'HEAD', accepted=(0, 1)).returncode == 0,
                   'Commit is unavailable in the original child worktree')
        raw = D.WS.local_git(root, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', oid).stdout
        changed = [D._scope(value.decode()) for value in raw.split(b'\0') if value]
        D._require(self._write_paths(assignment, changed),
                   'Commit changes are missing or outside the approved assignment write paths')
        return {'commit': oid, 'paths': sorted(path.as_posix() for path in changed)}

    def _check_decision(self, root, candidate, outcome):
        proof = candidate['decision']
        D._object(proof, {'decision_id', 'acceptance_digest'})
        actor = candidate['actor']
        D._require(D._token(actor), 'Select the exact owner actor')
        store = D.WF.Store(root, route_queue=False, neutral=True)
        helper = D.WF.decision_helper()
        record = helper.read(store, proof['decision_id'])
        ctx = record['context']
        task = outcome['task_context']
        D._require(ctx['task_ids'] == [outcome['task_id']] and ctx['content_fingerprint'] == task['content_fingerprint']
                   and ctx['semantic_fingerprint'] == task['semantic_fingerprint'], 'Owner decision scope or authority changed')
        acceptance = helper.acceptance_reference(store, proof, {'context': ctx, 'mode': 'manual',
            'kind': record['question']['kind'], 'authority_digest': record['authority_digest']})
        D._require(acceptance['actor']['id'] == actor and acceptance['origin']['kind'] in {'owner-message', 'submitted-answer'},
                   'Decision lacks the matching accepted owner input')
        return {'decision': proof, 'actor': actor, 'answer': acceptance['answer']}

    def adopt_preview(self, request):
        D._object(request, {'plan', 'assignment_id', 'candidate'})
        candidate = request['candidate']
        D._require(isinstance(candidate, dict) and candidate.get('kind') in CANDIDATES, 'Select a supported evidence candidate')
        D._object(candidate, {'kind', 'task_id', 'run_id', 'outcome_id'} | CANDIDATES[candidate['kind']])
        D._require(all(D.WF.valid_id(candidate[name], prefix) for name, prefix in
                       (('task_id', 'T'), ('run_id', 'WR'), ('outcome_id', 'O'))), 'Select exact canonical outcome identities')
        selected = request['plan']
        plan, current, _, areas, bindings = self.selection(selected)
        matches = [value for value in plan['assignments'] if value['id'] == request['assignment_id']]
        D._require(len(matches) == 1, 'Select an assignment in the exact frozen plan')
        spec, = matches
        source = spec['child']
        D._require(source.get('task_id') == candidate['task_id'] and D._sha(source.get('body_sha256')),
                   'Candidate task is outside the exact approved assignment')
        barriers, details = [], None
        if not current:
            barriers.append('objective-revision-is-superseded')
        if self._inflight(plan, selected, spec):
            barriers.append('reconcile-existing-director-dispatch')
        check = None
        area_id = spec['area']['id']
        try:
            root = O._child_root(areas, bindings, area_id)
            identity = O._area_identity(areas['areas'][area_id])
            D._require(all(spec['area'][key] == value for key, value in identity.items()),
                       'The original area identity changed')
            outcome, run = O._exact_outcome(root, candidate['task_id'], candidate['outcome_id'], candidate['run_id'])
            D._require(outcome['disposition'] == 'completed' and candidate['task_id'] in run['completed_ids']
                       and outcome.get('task_context', {}).get('content_fingerprint') == source['body_sha256'],
                       'The recorded result does not match the exact child scope')
            check, = O._record_checks(outcome, [spec['check']])
            D._require(self._check_covers_area(spec, check),
                       'Required check has no coverage in the exact owning area')
            artifacts = O._record_artifacts(outcome, [candidate['artifact']]) if candidate['kind'] == 'artifact' else []
            D._require(not artifacts or self._write_paths(spec, [D._scope(artifact['path']) for artifact in artifacts]),
                       'Artifact lies outside the exact approved assignment write paths')
            record = {'area': identity, 'task_id': candidate['task_id'],
                      'run_id': candidate['run_id'], 'outcome_id': candidate['outcome_id'],
                      'outcome_sha256': D._digest(outcome), 'checks': [check], 'artifacts': artifacts,
                      'source_fingerprints': outcome['source_fingerprints']}
            observed = O._view_link(record, areas, bindings)
            check, = observed['checks']
            D._require(observed['link_state'] == 'verified' and observed['source_freshness'] == 'current'
                       and observed['evidence_availability'] == 'available' and check['verdict'] == 'pass'
                       and check['source_freshness'] == 'current', 'Required current check or artifact evidence is unavailable')
            confirmed, missing = self._pins(spec, areas, bindings, check)
            if missing:
                barriers.append({'required_pins': missing})
            secondary = {'artifact': artifacts[0]} if artifacts else {}
            if candidate['kind'] == 'commit':
                secondary = self._check_commit(root, candidate, outcome, run, spec)
            elif candidate['kind'] == 'owner-decision':
                secondary = self._check_decision(root, candidate, outcome)
            details = {'area': record['area'], 'outcome_sha256': record['outcome_sha256'], 'checks': [check],
                       'current_pins': confirmed, 'integration': observed['integration'], 'delivery': observed['delivery'],
                       **secondary}
        except (KeyError, ValueError, OSError, subprocess.TimeoutExpired) as error:
            barriers.append({'candidate_evidence': str(error)})
        result = {'schema': 1, 'kind': 'director-adoption', 'plan': selected, 'assignment_id': spec['id'],
                  'authority_ref': spec['authority_ref'], 'candidate': candidate, 'details': details, 'blockers': barriers,
                  'state': 'held' if barriers else 'eligible'}
        return {**result, 'preview_sha256': D._digest(result)}

    def _milestone_source(self, role, part, plan, ledger, areas, bindings):
        D._require(isinstance(part, dict) and part.get('kind') in {'result', 'adoption', 'pin'},
                   'Select exact role evidence')
        kind = part['kind']
        assignment = next((row for row in plan['assignments'] if row['id'] == part.get('assignment_id')), None)
        D._require(assignment, 'Milestone names an unknown frozen assignment')
        if kind == 'pin':
            D._object(part, {'kind', 'assignment_id', 'pin'})
            pin = part['pin']
            D._require(role == 'story' and pin['adapter'] in {'narrative-canon', 'fixture-narrative'}
                       and pin in assignment['pins'] and pin['strength'] != 'provisional'
                       and areas['areas'][pin['area_id']]['role'] in ROLES[role], 'Milestone role or final pin differs')
            observed, _ = self._pins(assignment, areas, bindings)
            return {'state': 'verified' if pin in observed else 'stale', 'pin': pin}
        D._require(areas['areas'][assignment['area']['id']]['role'] in ROLES[role], 'Exact milestone role differs')
        if kind == 'adoption':
            D._object(part, {'kind', 'assignment_id', 'id'})
            accepted = self.read('adopt', part['id'])
            exact = accepted['evidence']
            active = self.adopt_preview(accepted['request'])
            D._require(exact['plan']['plan_sha256'] == self.planner.C.digest(plan) and exact['assignment_id'] == assignment['id'],
                       'Adopted result belongs to another plan or assignment')
            return {'state': 'verified' if active['state'] == 'eligible' else 'stale', 'id': part['id'],
                    'outcome': exact['candidate']['outcome_id'], 'evidence': exact['details']}
        D._object(part, {'kind', 'assignment_id', 'link_id'})
        link = ledger['outcomes'].get(part['link_id'])
        D._require(link and link['plan_sha256'] == self.planner.C.digest(plan) and link['assignment_id'] == assignment['id']
                   and link['area'] == O._area_identity(assignment['area']),
                   'Outcome link does not cover the exact milestone role')
        current = O._view_link(link, areas, bindings)
        checks = [check for check in current['checks'] if check['check_id'] == assignment['check']]
        if role in {'art', 'game'}:
            D._require(len(checks) == 1 and self._check_covers_area(assignment, checks[0]),
                       'Required check has no coverage in the exact owning area')
            artifacts = link['artifacts']
            D._require(not artifacts or self._write_paths(assignment, [D._scope(item['path']) for item in artifacts]),
                       'Artifact lies outside the exact approved assignment write paths')
        _, missing = self._pins(assignment, areas, bindings, checks[0] if len(checks) == 1 else None)
        ready = (not missing and current['link_state'] == 'verified' and current['source_freshness'] == 'current'
                 and current['evidence_availability'] == 'available' and len(checks) == 1 and checks[0]['verdict'] == 'pass'
                 and checks[0].get('source_freshness') == 'current')
        return {'state': 'verified' if ready else 'stale', 'link_id': part['link_id'], 'outcome': link['outcome_id'],
                'run_id': link['run_id'], 'task_id': link['task_id'], 'artifacts': link['artifacts'],
                'checks': checks, 'delivery': current['delivery']}

    def milestone_preview(self, request):
        D._object(request, {'plan', 'name', 'roles'}, {'handoff_id'})
        parts = request['roles']
        required_roles = {'story', 'art', 'game'}
        D._require(D._token(request['name']) and isinstance(parts, dict) and required_roles <= parts.keys()
                   and parts.keys() <= ROLES.keys(), 'Select required story, art and game evidence')
        plan, current, ledger, areas, bindings = self.selection(request['plan'])
        roles = {}
        for name, part in sorted(parts.items()):
            try:
                roles[name] = self._milestone_source(name, part, plan, ledger, areas, bindings)
            except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
                roles[name] = {'state': 'unavailable'}
        provisional = [{'assignment_id': assignment['id'], 'pin': pin} for assignment in plan['assignments']
                       for pin in assignment['pins'] if pin['strength'] == 'provisional']
        required_handoff = any(pin['area_id'] != assignment['area']['id'] and pin['strength'] != 'optional'
                               for assignment in plan['assignments'] for pin in assignment['pins'])
        handoff = 'unreviewed' if required_handoff else 'not-required'
        if request.get('handoff_id'):
            handoff = self._milestone_handoff(request)
        superseded = {}
        for amendment in self.handoffs._amendments(request['plan']):
            for name, part in sorted(parts.items()):
                assignment_id = part.get('assignment_id') if isinstance(part, dict) else None
                if D._token(assignment_id) and assignment_id in amendment['affected']:
                    superseded.setdefault(name, []).append(amendment['preview_sha256'])
        ready = (current and all(roles[name]['state'] == 'verified' for name in required_roles)
                 and not provisional and not (required_roles & superseded.keys())
                 and handoff in {'eligible', 'not-required'})
        revision = plan['objective']['objective_revision']
        result = {'schema': 1, 'kind': 'director-milestone', 'plan': request['plan'], 'name': request['name'],
                  'authority_ref': ledger['revisions'][revision - 1]['intent']['owner_ref'], 'roles': roles,
                  'handoff': handoff, 'state': 'eligible' if ready else 'held', 'release': 'requires-delivery-authority',
                  'objective_current': current, 'objective_revision': revision,
                  'current_objective_revision': ledger['current']['revision'], 'provisional_requirements': provisional,
                  'superseded_roles': superseded}
        return {**result, 'preview_sha256': D._digest(result)}

    def _milestone_handoff(self, request):
        try:
            archived = self.handoffs.run('review-read', {'archive_id': request['handoff_id']})
            reviewed = archived['observation']
            D._require(reviewed['kind'] == 'director-handoff-review' and reviewed['plan'] == request['plan'],
                       'Handoff archive scope differs')
            if reviewed['parent_acceptance'] != 'eligible':
                return 'held'
            observed = self.handoffs.review_preview(archived['request'])
        except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired):
            return 'unavailable'

        def required(report):
            return [{key: value for key, value in row.items() if key != 'delivery'} for row in report['edges']
                    if row['pin']['strength'] != 'optional']

        return 'eligible' if observed['parent_acceptance'] == 'eligible' and required(observed) == required(reviewed) else 'stale'

    def _archive(self, kind, request):
        D._object(request, {'request', 'expected_preview_sha256', 'owner_ref'})
        expected = request['expected_preview_sha256']
        D._require(D._sha(expected) and D._token(request['owner_ref']), 'Current reviewed approval is required')
        preview = self.adopt_preview if kind == 'adopt' else self.milestone_preview
        store = D.WF.Store(self.root, route_queue=False, neutral=True)
        relative = f'{ARCHIVE}/{kind}-{expected}.json'
        digest = D._digest(request)
        with store.lock(local_delivery={'kind': kind, 'request_sha256': digest}):
            old, old_sha = D._read(self.root, relative)
            if old is not None:
                self._verify_record(kind, expected, old)
                D._require(old['request_sha256'] == digest, 'The original archived approval differs')
                return old
            observed = preview(request['request'])
            D._require(observed['preview_sha256'] == expected and observed['state'] == 'eligible',
                       'Exact reviewed evidence is blocked or changed')
            D._require(observed['authority_ref'] == request['owner_ref'], 'The approval does not match the exact plan authority')
            value = {'schema': 1, 'id': expected, 'kind': kind, 'request_sha256': digest, 'owner_ref': request['owner_ref'],
                     'request': deepcopy(request['request']), 'evidence': observed, 'recorded_at': D.WF.now()}
            store.expect_unchanged(relative, old_sha)
            store.commit({relative: D.WF.dump(value)})
            return value

    def read(self, kind, identity):
        D._require(D._sha(identity), 'Select the exact archived evidence identity')
        value, _ = D._read(self.root, f'{ARCHIVE}/{kind}-{identity}.json')
        self._verify_record(kind, identity, value)
        return value

    def _verify_record(self, kind, identity, value):
        D._require(isinstance(value, dict), 'Archived evidence is unavailable')
        D._object(value, {'schema', 'id', 'kind', 'request_sha256', 'owner_ref', 'request', 'evidence', 'recorded_at'})
        D._require(value['schema'] == 1 and value['kind'] == kind and value['id'] == identity
                   and value['evidence']['preview_sha256'] == identity
                   and value['owner_ref'] == value['evidence']['authority_ref'], 'Archived evidence identity is invalid')
        envelope = {'request': value['request'], 'expected_preview_sha256': identity, 'owner_ref': value['owner_ref']}
        D._require(D._digest(envelope) == value['request_sha256'], 'Archived approval or request changed')
        D._require(D._digest({name: item for name, item in value['evidence'].items() if name != 'preview_sha256'}) == identity,
                   'Archived evidence digest changed')

    def run(self, command, payload):
        D._require(command in COMMANDS, 'Unknown Director evidence operation')
        kind, verb = command.split('-')
        if verb == 'preview':
            return self.adopt_preview(payload) if kind == 'adopt' else self.milestone_preview(payload)
        if verb == 'apply':
            return self._archive(kind, payload)
        D._object(payload, {'id'})
        original = self.read(kind, payload['id'])
        preview = self.adopt_preview if kind == 'adopt' else self.milestone_preview
        try:
            current = preview(original['request'])
        except (KeyError, ValueError, OSError, subprocess.TimeoutExpired):
            current = {'state': 'unavailable'}
        return {'archive': original, 'current': current}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=sorted(COMMANDS))
    parser.add_argument('root', type=Path)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(D.WF.dump(DirectorEvidence(args.root).run(args.command, json.loads(args.input.read_bytes()))), end='')
    except (KeyError, TypeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), end='\n')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
