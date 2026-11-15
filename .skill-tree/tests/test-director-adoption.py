"""Verify explicit adoption of exact work completed by standalone Core controllers."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = load('director_evidence_for_adoption', HERE.parent / 'common/scripts/director-evidence.py')
HANDOFF = load('director_handoff_for_adoption', HERE / 'test-director-handoff.py')
D, O, WF, WS = E.D, E.O, E.D.WF, E.D.WS
FIXTURES = HERE / 'fixtures/director'
CRITERION = 'The exact local lantern result passes the selected check.'


class EvidenceFixture:
    def __init__(self, cleanup, scopes=('art',), *, cross_area=False):
        base = HANDOFF.HandoffTests()
        base.add_child = lambda *_: None
        base.setUp()
        cleanup(base.doCleanups)
        self.base, self.parent, self.child = base.base, base.parent, base.child
        WS.local_git_text(self.child, 'remote', 'add', 'origin', str(self.base / 'unused-local-fixture.git'))
        self.registry, self.ledger, self.objective = base.registry, base.ledger, base.objective
        self.objective_id, self.plan_id = base.objective_id, base.plan_id
        self.evidence = E.DirectorEvidence(self.parent)
        self.proof = {}
        self.compact = json.loads((FIXTURES / 'fixture-manifest.json').read_bytes())
        model_path = self.compact['artifact']['path']
        self.payload = (FIXTURES / model_path).read_bytes()
        story_path = self.compact['story']['accepted']['path']
        (self.child / 'story').mkdir()
        (self.child / 'story/source.txt').write_text('Accepted cave story fixture.\n')
        (self.child / story_path).write_bytes((FIXTURES / story_path).read_bytes())
        (self.child / model_path).write_bytes(self.payload)
        WS.local_git_text(self.child, 'add', 'story', model_path)
        self.commit(self.child, 'Fixture story and selected artifact pins')
        registration = {'director_id': 'handoff-fixture', 'areas': [base.area('story', 'story', 'narrative')]}
        self.registry.apply({**registration, 'expected_preview_sha256': self.registry.preview(registration)['preview_sha256']})
        for name in scopes:
            self.prepare_task(name)
        self.plan = self.freeze(cross_area=cross_area)
        for name in scopes:
            self.standalone(name)

    @staticmethod
    def commit(root, message):
        WS.local_git_text(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                          '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', message)
        return WS.local_git_text(root, 'rev-parse', 'HEAD')

    @staticmethod
    def files(root):
        return {item.relative_to(root).as_posix(): item.read_bytes() for item in root.rglob('*') if item.is_file()}

    def prepare_task(self, name):
        root = WF.Store(self.child, route_queue=False, neutral=True)
        title = f'Local {name} result'
        output = f'{name}/lantern.bin'
        pending = WF.intake(root, {'title': title, 'description': 'Check exact exported bytes.',
                                   'expected_behavior': CRITERION})['id']
        spec = {'id': 'verify-carry', 'recipe_id': 'static-inspection', 'criteria': [CRITERION],
                'sources': [output], 'parameters': {}, 'assertion': CRITERION, 'timing': 'immediate'}
        body = ('Goal:\n- Check the exact local result.\n\nTouch:\n- ' + output + '\n\nValidation:\n```json\n'
                + WF.dump({'checks': [spec]}) + '```\n\nAcceptance:\n- ' + CRITERION + '\n')
        task_id = WF.process(root, {'selectors': [pending], 'tasks': [{'title': title, 'body': body,
                             'parent_pending_ids': [pending]}], 'dispositions': {pending: {'status': 'promoted',
                             'reason': 'The fixture supplies bounded exact evidence.'}}})['created_ids'][0]
        task = next(item for item in WF.parse(root.text()) if item['id'] == task_id)
        self.proof[name] = {'task_id': task_id, 'body_sha256': WF.digest(task['body'].encode())}

    def standalone(self, name):
        root = WF.Store(self.child, route_queue=False, neutral=True)
        task_id = self.proof[name]['task_id']
        output, source = f'{name}/lantern.bin', f'{name}/source.txt'
        worktree = self.base / (name + '-standalone')
        run = WF.start(root, 'next', selector=task_id, workspace={'local_base': True,
                       'local_base_authorization': 'Disposable local Director evidence fixture only.',
                       'base_branch': 'develop', 'branch': f'fixture/{name}-existing', 'worktree': str(worktree)})
        store = WF.Store(worktree, run_id=run['id'])
        (worktree / output).write_bytes(self.payload)
        log = f'{name}/review.txt'
        (worktree / log).write_text('Observed the local fixture model.\n')
        foreign = 'game/unapproved-sibling-output.bin'
        if name == 'art':
            (worktree / foreign).write_bytes(b'Separate legitimate evidence with the wrong routing scope.')
        WS.local_git_text(worktree, 'add', output)
        commit = self.commit(worktree, f'Record local {name} fixture output')
        WF.advance(store)
        WF.begin_task(store, {'task_id': task_id})
        check_id = 'verify-carry'
        check = WF.prepare_check(store, {'task_id': task_id, 'check_id': check_id})
        if (worktree / output).read_bytes() != self.payload:
            raise AssertionError('The standalone observed bytes differ from the exact local fixture payload')
        WF.record_check(store, {'task_id': task_id, 'check_id': check_id, 'attempt_id': check['attempt_id'],
            'classification': 'executed-control', 'result': 'pass', 'actual_lane': 'static',
            'environment_identity': check['environment_identity'], 'cleanup': 'No product process started.',
            'assertions': [{'assertion': CRITERION, 'result': 'pass'}], 'evidence': [log]})
        WF.mark_implemented(store, {'task_id': task_id})
        accepted = [output, log] + ([foreign] if name == 'art' else [])
        outcome = WF.complete(store, {'task_id': task_id, 'outcome': 'The local result matches the selected fixture bytes.',
            'acceptance': [{'criterion': CRITERION, 'result': 'pass', 'evidence': accepted}],
            'source_fingerprints': WF.fingerprints(store, [source]), 'commits': [commit]})
        stopped = WF.finish(store)
        if stopped['delivery']['status'] != 'local-result' or outcome['task_context']['content_fingerprint'] != self.proof[name]['body_sha256']:
            raise AssertionError('The standalone controller did not retain the exact local task result')
        artifact = {'artifact_id': 'lantern-model', 'path': output, 'sha256': WF.file_hash(worktree / output)}
        self.proof[name].update(run_id=run['id'], outcome_id=outcome['id'], commit=commit, outcome=outcome,
                                artifact=artifact, worktree=worktree,
                                foreign={'artifact_id': 'sibling-output', 'path': foreign,
                                         'sha256': WF.file_hash(worktree / foreign)})

    def pin(self, area):
        row = self.compact['story']['accepted'] if area == 'story' else self.compact['artifact']
        return {'area_id': area, 'adapter': 'fixture-narrative' if area == 'story' else 'fixture-artworkshop',
                'record_id': self.compact['story']['id'] if area == 'story' else row['id'], 'revision': row['revision'],
                'sha256': row['sha256'], 'path': row['path'], 'role': 'story-canon' if area == 'story' else 'accepted-artifact',
                'strength': 'required', 'status': 'verified'}

    def freeze(self, revision=1, *, cross_area=False, body_sha=None):
        ledger, registry, _, basis = self.ledger._load(self.objective_id)
        allowed = ('story', 'art', 'game', 'website')
        identities = [name for name in allowed if name in self.proof]
        assignments = []
        for name in identities:
            proof = self.proof[name]
            pins, dependencies = [], []
            if name in {'story', 'art'}:
                pins = [self.pin(name)]
            if cross_area and name == 'game':
                pins, dependencies = [self.pin('art')], ['art']
            assignments.append({'id': name, 'area': O._area_identity(registry['areas'][name]),
                'child': {'task_id': proof['task_id'], 'body_sha256': body_sha if name == 'art' and body_sha else proof['body_sha256']},
                'pins': pins, 'authority_ref': 'fixture-owner', 'check': 'verify-carry', 'depends_on': dependencies,
                'workspace': 'recorded-worktree', 'write_paths': ['lantern.bin']})
        selection = {'objective_id': self.objective_id, 'plan_id': self.plan_id, 'plan_revision': revision}
        objective = {'objective_id': self.objective_id, 'objective_revision': self.objective['revision'],
                     'objective_sha256': self.objective['sha256']}
        plan = {**selection, 'director_id': 'handoff-fixture', 'objective': objective, 'assignments': assignments}
        sha = self.evidence.planner.C.digest(plan)
        ledger['plans'][O._plan_key(self.plan_id, revision)] = {'frozen': plan, 'plan_sha256': sha,
            'objective_revision': objective['objective_revision'], 'objective_sha256': objective['objective_sha256'],
            'assignments': {row['id']: {'area': row['area'], 'task_ids': [row['child']['task_id']]} for row in assignments}}
        relative = O.objective_path(self.objective_id)
        with self.registry.store.lock(local_delivery={'kind': 'fixture-plan'}):
            self.registry.store.expect_unchanged(relative, basis[relative])
            self.registry.store.commit({relative: WF.dump(ledger)})
        return {**selection, 'plan_sha256': sha}

    def adoption(self, area='art', kind='child-run', *, plan=None, **candidate):
        proof = self.proof[area]
        return {'plan': plan or self.plan, 'assignment_id': area, 'candidate': {'kind': kind,
                **{key: proof[key] for key in ('task_id', 'run_id', 'outcome_id')}, **candidate}}

    def apply(self, kind, request, preview, owner='fixture-owner'):
        return self.evidence.run(kind + '-apply', {'request': request, 'expected_preview_sha256': preview['preview_sha256'],
                                                  'owner_ref': owner})

    def link(self, name):
        proof = self.proof[name]
        ledger = self.ledger.read({'objective_id': self.objective_id})
        return self.ledger.link_outcome({**self.plan, 'expected_ledger_sha256': ledger['ledger_sha256'],
            'area_id': name, 'assignment_id': name, **{field: proof[field] for field in ('task_id', 'run_id', 'outcome_id')},
            'artifacts': [proof['artifact']], 'check_ids': ['verify-carry']})['link_id']

    def manual_decision(self, area='art'):
        proof = self.proof[area]
        task_id = proof['task_id']
        store = WF.Store(self.child, route_queue=False, neutral=True)
        helper = WF.decision_helper()
        context = {'kind': 'task', 'id': 'task-scope:' + task_id, 'task_ids': [task_id], **proof['outcome']['task_context']}
        actor = {'id': 'fixture-owner', 'context_id': 'controlled-owner-context'}
        record = helper.start(store, {'request_id': 'fixture-adopt-owner', 'mode': 'manual', 'context': context,
            'question': {'id': 'choose-fixture', 'kind': 'technical', 'text': 'Keep the fixture result?',
                         'options': [{'id': 'keep', 'text': 'Retain the exact fixture result.'}],
                         'recommendation': 'keep', 'significance': 'routine'},
            'authority': {'id': 'local-fixture-approval', 'revision': 1, 'context_id': context['id'],
                'allowed_kinds': ['technical'], 'constraints': ['Only the disposable evidence fixture.'],
                'evidence': {'kind': 'owner-message', 'reference': 'Controlled fixture owner authority.'}},
            'executor': {'id': 'fixture-executor', 'context_id': 'fixture-executor-context'}})

        def change(command, **values):
            return helper.mutate(store, command, {'decision_id': record['id'], 'expected_decision_hash': record['decision_hash'],
                'expected_decision_revision': record['revision'], 'expected_mode_epoch': record['mode_epoch'],
                'expected_context_fingerprint': context['content_fingerprint'], **values})

        record = change('prepare', role='owner', actor=actor)
        record = change('record', attempt_id=record['prepared_attempt_id'],
                        result={'status': 'answered', 'answer': 'keep', 'rationale': 'Observe a controlled fixture acceptance.'},
                        evidence={'kind': 'submitted-answer', 'reference': 'Controlled fixture input.',
                                  'actor_id': actor['id'], 'actor_context_id': actor['context_id']})
        record = change('accept')
        return {'decision_id': record['id'], 'acceptance_digest': record['acceptance']['digest']}


class DirectorAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.f = EvidenceFixture(self.addCleanup)

    def test_standalone_result_and_commit_accept_exact_scope_without_queue_effects(self):
        expected = self.f.proof['art']
        request = self.f.adoption()
        child_before = self.f.files(self.f.child)
        worktree_before = self.f.files(expected['worktree'])
        preview = self.f.evidence.run('adopt-preview', request)
        self.assertEqual(preview['state'], 'eligible')
        self.assertEqual(preview['details']['delivery'], 'local-result')
        self.assertEqual(preview['details']['integration'], 'unverified')
        self.assertEqual(preview['details']['current_pins'], [self.f.pin('art')])
        commit = self.f.evidence.adopt_preview(self.f.adoption(kind='commit', commit=expected['commit']))
        self.assertEqual((commit['state'], commit['details']['paths']), ('eligible', ['art/lantern.bin']))
        missing_commit = self.f.evidence.adopt_preview(self.f.adoption(kind='commit', commit='0' * 40))
        self.assertEqual(missing_commit['state'], 'held')
        archive = self.f.apply('adopt', request, preview)
        self.assertEqual(self.f.apply('adopt', request, preview), archive)
        with self.assertRaisesRegex(ValueError, 'approval|authority'):
            self.f.apply('adopt', request, preview, owner='wrong-owner')
        self.assertEqual(self.f.files(self.f.child), child_before)
        self.assertEqual(self.f.files(expected['worktree']), worktree_before)

    def test_artifact_scope_and_live_evidence_drift_hold(self):
        proof = self.f.proof['art']
        request = self.f.adoption(kind='artifact', artifact=proof['artifact'])
        preview = self.f.evidence.adopt_preview(request)
        self.assertEqual(preview['state'], 'eligible')
        sibling = self.f.adoption(kind='artifact', artifact=proof['foreign'])
        self.assertEqual(self.f.evidence.adopt_preview(sibling)['state'], 'held')
        archive = self.f.apply('adopt', request, preview)
        pin = self.f.pin('art')
        path = self.f.child / pin['path']
        original = path.read_bytes()
        path.write_bytes(b'Changed approved art pin while the standalone proof stays byte-identical.')
        pinned = self.f.evidence.run('adopt-read', {'id': archive['id']})
        self.assertEqual(pinned['archive'], archive)
        self.assertEqual(pinned['current']['state'], 'held')
        self.assertIn({'required_pins': [{'record_id': pin['record_id'], 'status': 'changed'}]},
                      pinned['current']['blockers'])
        path.write_bytes(original)
        (proof['worktree'] / proof['artifact']['path']).write_bytes(b'Changed exact prior check input.')
        observed = self.f.evidence.run('adopt-read', {'id': archive['id']})
        self.assertEqual(observed['archive'], archive)
        self.assertEqual(observed['current']['state'], 'held')
        wrong_frozen_plan = self.f.freeze(2, body_sha='d' * 64)
        wrong = self.f.evidence.adopt_preview(self.f.adoption(plan=wrong_frozen_plan))
        self.assertEqual(wrong['state'], 'held')
        wrong_task = self.f.adoption(task_id=WF.identity('T'))
        with self.assertRaisesRegex(ValueError, 'approved assignment'):
            self.f.evidence.adopt_preview(wrong_task)

    def test_owner_scope_and_existing_dispatch_remain_distinct(self):
        decision = self.f.manual_decision()
        request = self.f.adoption(kind='owner-decision', decision=decision, actor='fixture-owner')
        self.assertEqual(self.f.evidence.adopt_preview(request)['state'], 'eligible')
        other = self.f.adoption(kind='owner-decision', decision=decision, actor='unrelated')
        self.assertEqual(self.f.evidence.adopt_preview(other)['state'], 'held')
        read_only = WF.Store(self.f.parent, route_queue=False, neutral=True)
        area = self.f.registry._load()[0]['areas']['art']
        request = {'director_dispatch': {'schema': 1, 'director_id': 'handoff-fixture', 'assignment_id': 'art',
                    'queue_id': area['queue_id'], 'plan_sha256': self.f.plan['plan_sha256']},
                   'expected_source_hash': WF.file_hash(self.f.child / '.skill-tree/documents/future.md'),
                   'title': 'Reserved effect', 'description': 'Recorded before a hypothetical lost response.',
                   'expected_behavior': 'Reconcile the exact existing intent separately.'}
        WF.director_dispatch_helper().retain_intent(read_only, 'intake', request)
        held = self.f.evidence.adopt_preview(self.f.adoption())
        self.assertIn('reconcile-existing-director-dispatch', held['blockers'])
        unrelated_plan = self.f.freeze(2)
        self.assertEqual(self.f.evidence.adopt_preview(self.f.adoption(plan=unrelated_plan))['state'], 'eligible')

    def test_new_plan_can_resolve_exact_already_completed_external_task(self):
        proof = self.f.proof['art']
        root = WF.Store(self.f.child, route_queue=False, neutral=True)
        self.assertNotIn(proof['task_id'], {item['id'] for item in WF.parse(root.text())})
        registry, bindings, _ = self.f.registry._load()
        source = load('director_completed_plan_sources', HERE.parent / 'common/scripts/director-plan-adapters.py')
        resolver = source.PlanSources(D, O, self.f.evidence.planner.C, registry, bindings)
        requested = {field: proof[field] for field in ('task_id', 'body_sha256')}
        actual = resolver.child_task(registry['areas']['art'], requested)
        self.assertEqual(actual, requested)
        observed = resolver.child_task(registry['areas']['art'], {**requested, 'body_sha256': 'f' * 64})
        self.assertNotEqual(observed, {**requested, 'body_sha256': 'f' * 64})

    def test_archive_rejects_changed_review_request_and_evidence_on_read_and_replay(self):
        request = self.f.adoption()
        preview = self.f.evidence.adopt_preview(request)
        archive = self.f.apply('adopt', request, preview)
        path = self.f.parent / E.ARCHIVE / ('adopt-' + archive['id'] + '.json')
        wrong = deepcopy(archive)
        wrong['request']['candidate']['run_id'] = WF.identity('WR')
        path.write_text(WF.dump(wrong))
        with self.assertRaisesRegex(ValueError, 'archive|Archive'):
            self.f.evidence.run('adopt-read', {'id': archive['id']})
        wrong = deepcopy(archive)
        wrong['evidence']['state'] = 'held'
        path.write_text(WF.dump(wrong))
        with self.assertRaisesRegex(ValueError, 'archive|Archive'):
            self.f.apply('adopt', request, preview)


if __name__ == '__main__':
    unittest.main()
