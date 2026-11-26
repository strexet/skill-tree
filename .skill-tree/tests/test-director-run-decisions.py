"""Portable Director question and child checkpoint controls."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch
import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest


CORE = Path(__file__).resolve().parents[1] / 'common/scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIRECTOR = load('director_state_fixture', CORE / 'director-state.py')
RUN = load('director_run_fixture', CORE / 'director-run.py')
QUESTIONS = load('director_questions_fixture', CORE / 'director-questions.py')
RUN.D = DIRECTOR
RUN.QUESTIONS = QUESTIONS
QUESTIONS.wf = DIRECTOR.WF
WF = DIRECTOR.WF
DISPATCH = WF.director_dispatch_helper()
FIXTURE = load('director_dispatch_fixture', Path(__file__).with_name('test-director-dispatch-receipts.py'))


class RunDecisionTests(unittest.TestCase):
    def setUp(self):
        fixture = FIXTURE.DispatchTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.core_source = '.skill-tree/common/scripts/workflow-state.py'
        helper = fixture.root / self.core_source
        helper.parent.mkdir(parents=True)
        helper.write_bytes(Path(WF.__file__).read_bytes())
        WS = WF.workspaces
        WS.local_git_text(fixture.root, 'add', self.core_source)
        WS.git(fixture.root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
               '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture Core helper')
        self.task_id = fixture.task()
        self.worktree = Path(fixture.start_request()['worktree'])
        self.registry = DIRECTOR.DirectorRegistry(fixture.parent)
        self.objective = {'objective_id': WF.identity('OB'), 'objective_revision': 1, 'objective_sha256': 'c' * 64}
        area = {'id': 'art', 'queue_id': fixture.queue, 'repo_id': WF.workspaces.repo_id(fixture.root), 'scope': '.'}
        self.plan = {'schema': 1, 'director_id': 'pilot', 'objective': self.objective,
                     'plan_id': WF.identity('PL'), 'plan_revision': 1, 'assignments': [
                         {'id': 'lantern', 'area': area, 'authority_ref': 'owner-grant', 'depends_on': [],
                          'resources': [], 'pins': [], 'effects': ['launch'], 'workspace': 'recorded-worktree', 'check': 'contract',
                          'child': {'task_id': self.task_id, 'body_sha256': self.task_hash()}},
                         {'id': 'independent', 'area': area, 'authority_ref': 'owner-grant', 'depends_on': [],
                          'resources': [], 'pins': [], 'effects': ['intake'],
                          'child': {'title': 'Independent check', 'description': 'Check a separate object.',
                                    'acceptance': ['Record result.']}},
                     ]}
        self.sha = DIRECTOR._digest(self.plan)
        fixture.area['plan_sha256'] = self.sha
        self.run = RUN.DirectorRun(self.registry, self.read_plan, self.check_area)
        self.parent_id = WF.identity('DR')
        self.launch = {'director_run_id': self.parent_id,
                       'plan_id': self.plan['plan_id'], 'plan_revision': 1,
                       'objective_id': self.objective['objective_id'], 'plan_sha256': self.sha,
                       'assignment_ids': ['lantern', 'independent'],
                       'owner': {'actor': 'petr', 'reference': 'owner-start-1', 'kind': 'owner-message'},
                       'authority': {'lantern': ['launch'], 'independent': ['intake']},
                       'approved_defaults': []}

    def read_plan(self, selector):
        self.assertEqual(selector['plan_id'], self.plan['plan_id'])
        return deepcopy(self.plan), self.sha

    def check_area(self, assignment):
        return self.fixture.root

    def task_hash(self):
        task = WF.resolve(WF.parse(self.fixture.child().text()), [self.task_id])[0]
        return WF.digest(task['body'].encode())

    def child(self):
        return WF.Store(self.fixture.root, neutral=True)

    def start_parent(self):
        return self.run.start(self.launch)

    def start_child(self):
        parent = self.start_parent()
        args = {key: value for key, value in self.fixture.start_request().items() if key != 'director_dispatch'}
        self.run.dispatch({'director_run_id': self.parent_id, 'expected_run_sha256': parent['run_sha256'],
                           'assignment_id': 'lantern', 'operation': 'start', 'request': args})
        observed = DISPATCH.observe(self.child(), {'operation': 'start', 'director_dispatch': self.fixture.area})
        self.child_run = observed['observed_result']['id']
        self.start_receipt = observed['receipt']['receipt_sha256']
        return observed['observed_result']

    def ask(self, **changes):
        parent = self.run.status({'director_run_id': self.parent_id})
        return self.run.open_question({'director_run_id': self.parent_id, 'expected_run_sha256': parent['run_sha256'],
                                       'assignment_id': 'lantern', 'question_id': WF.identity('DQ'),
                                       'attempt_id': WF.identity('DA'), 'child_run_id': self.child_run,
                                       'task_id': self.task_id, 'start_receipt_sha256': self.start_receipt,
                                       'recipient': 'petr', 'requester': 'art-worker', 'key': 'grip-choice',
                                       'options': [{'id': 'hand', 'label': 'Hand grip'}, {'id': 'belt', 'label': 'Belt socket'}],
                                       'recommendation': 'hand', 'affected_areas': ['art'], 'blocked_action': 'Finalize attachment',
                                       'deadline': '2099-01-01T00:00:00+00:00', **changes})

    def response(self, question, **changes):
        status = self.run.status({'director_run_id': self.parent_id})
        return {'director_run_id': self.parent_id, 'expected_run_sha256': status['run_sha256'],
                'assignment_id': 'lantern', 'question_id': question['question_id'],
                'question_sha256': question['question_sha256'], 'attempt_id': question['attempt_id'],
                'child_run_id': self.child_run, 'choice': 'hand', 'disposition': 'answer',
                'owner': {'actor': 'petr', 'reference': 'owner-answer-1', 'kind': 'owner-message'}, **changes}

    def child_checkpoint(self):
        return self.child().load()['run_registry']['runs'][self.child_run]

    def timeline(self):
        _, state, _ = self.run._load(self.parent_id)
        records = state['timeline']
        self.assertEqual([row['sequence'] for row in records], list(range(1, len(records) + 1)))
        for row in records:
            self.assertEqual(datetime.fromisoformat(row['recorded_at']).tzinfo, timezone.utc)
        return records

    def test_answer_replays_and_releases_only_same_child_workspace(self):
        started = self.start_child()
        dirty = self.worktree / 'owned-edits.txt'
        dirty.write_bytes(b'Keep partial work.')
        question = self.ask()['question']
        waiting = self.child_checkpoint()
        self.assertEqual(waiting['director_question_hold']['question_id'], question['question_id'])
        status = self.run.status({'director_run_id': self.parent_id})
        self.assertEqual(status['assignments']['independent']['next'], 'intake')
        sibling = self.run.dispatch({'director_run_id': self.parent_id, 'expected_run_sha256': status['run_sha256'],
                                     'assignment_id': 'independent', 'operation': 'intake',
                                     'request': {'expected_source_hash': WF.file_hash(self.child().future)}})
        self.assertTrue(WF.valid_id(sibling['result']['id'], 'P'))
        self.assertEqual(self.child_checkpoint(), waiting)
        payload = self.response(question)
        result = self.run.answer(payload)
        captured = self.timeline()
        self.assertEqual(self.run.answer(payload)['delivery'], result['delivery'])
        self.assertEqual(self.timeline(), captured)
        resumed = self.child_checkpoint()
        self.assertEqual(resumed['id'], self.child_run)
        self.assertEqual(resumed['workspace'], started['workspace'])
        self.assertEqual(resumed['phase'], started['phase'])
        self.assertIsNone(resumed['stop_reason'])
        self.assertEqual(dirty.read_bytes(), b'Keep partial work.')

    def test_wrong_actor_attempt_and_child_run_leave_checkpoint_and_owner_wait(self):
        self.start_child()
        question = self.ask()['question']
        before = self.child_checkpoint()
        for changed in ({'attempt_id': WF.identity('DA')}, {'child_run_id': WF.identity('WR')},
                        {'owner': {'actor': 'other', 'reference': 'wrong-sender', 'kind': 'owner-message'}}):
            with self.assertRaisesRegex(ValueError, 'exact|recipient'):
                self.run.answer(self.response(question, **changed))
        self.assertEqual(self.child_checkpoint(), before)
        declined = self.run.answer(self.response(question, choice=None, disposition='decline'))
        self.assertEqual(declined['status'], 'waiting')
        self.assertEqual(self.child_checkpoint(), before)

    def test_stale_core_in_original_worktree_never_opens_question(self):
        original = self.start_child()
        parent = self.run.status({'director_run_id': self.parent_id})
        helper = self.worktree / self.core_source
        helper.write_text('# Older Core helper without the Director hold guard.\n')
        self.assertEqual((self.fixture.root / self.core_source).read_bytes(), Path(WF.__file__).read_bytes())
        with self.assertRaisesRegex(ValueError, 'Original child worktree requires the exact current Core'):
            self.ask()
        self.assertEqual(self.run.status({'director_run_id': self.parent_id}), parent)
        self.assertEqual(self.child_checkpoint(), original)

    def test_shared_workflow_profile_preserves_directed_question_hold_and_release(self):
        source = CORE.parent.parent
        installed = subprocess.run(
            ['node',str(source/'bin/install.js'),'--target',str(self.fixture.root),'--project',
             '--flavor','general','--only','codex','--skills','skill-tree-work-through-next','--shared-runtime'],
            capture_output=True,text=True,timeout=90)
        self.assertEqual(installed.returncode,0,installed.stdout+installed.stderr)
        self.start_child()
        store = WF.Store(self.worktree,run_id=self.child_run)
        self.assertEqual(WF.prepare_worktree_profile(store)['status'],'admitted')
        self.assertEqual(WF.advance(store)['phase'],'implement')
        self.assertEqual(DIRECTOR._project_setup_helper().shared_routing(self.worktree),'guarded')
        wrapper = self.worktree/'.agents/skills/skill-tree-work-through-next/scripts/workflow-state.py'
        body = store.source_root/'.skill-tree/installation/source/common/scripts/workflow-state.py'
        before = self.child_checkpoint()
        original_body = body.read_bytes()
        try:
            body.write_bytes(original_body+b'\n# edited shared runtime\n')
            with self.assertRaisesRegex(ValueError,'Original child worktree requires the exact current Core'):
                self.ask()
            self.assertEqual(self.child_checkpoint(),before)
        finally:
            body.write_bytes(original_body)
        question = self.ask()['question']
        waiting = self.child_checkpoint()
        self.assertIn('director_question_hold',waiting)
        _, director, _ = self.run._load(self.parent_id)
        context = self.run._question_context(director,self.plan['assignments'][0],question)
        request = self.fixture.base/'inspect-shared-hold.json'
        request.write_text(WF.dump(context))
        check = """
import importlib.util, json, runpy, sys
from pathlib import Path
from types import SimpleNamespace
entry, questions, checkout, run_id, request = sys.argv[1:]
spec = importlib.util.spec_from_file_location('child_question_check', questions)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.wf = SimpleNamespace(**runpy.run_path(entry))
store = module.wf.Store(Path(checkout), run_id=run_id)
module.handle(store, 'director-question-check', json.loads(Path(request).read_text()))
"""
        inspected = subprocess.run(
            [sys.executable,'-B','-c',check,str(wrapper),str(CORE/'director-questions.py'),
             str(self.worktree),self.child_run,str(request)],
            capture_output=True,text=True,timeout=90)
        self.assertEqual(inspected.returncode,0,inspected.stdout+inspected.stderr)
        original_wrapper = wrapper.read_bytes()
        try:
            wrapper.write_bytes(original_wrapper+b'\n# edited workflow entrypoint\n')
            with self.assertRaisesRegex(ValueError,'Original child worktree requires the exact current Core'):
                self.run.answer(self.response(question))
            self.assertEqual(self.child_checkpoint(),waiting)
        finally:
            wrapper.write_bytes(original_wrapper)
        self.run.answer(self.response(question))
        self.assertNotIn('director_question_hold',self.child_checkpoint())

    def test_changed_child_admission_never_releases_existing_hold(self):
        self.start_child()
        question = self.ask()['question']
        child = self.child()
        state = child.load()
        state['run_registry']['runs'][self.child_run]['admission'] = {'identity': 'unexpected'}
        child.state.write_text(WF.dump(state))
        with self.assertRaisesRegex(ValueError, 'admission|original hold'):
            self.run.answer(self.response(question))
        self.assertTrue(self.child_checkpoint()['director_question_hold'])

    def test_parent_pause_and_cancel_preserve_child_and_reject_late_answer(self):
        self.start_child()
        question = self.ask()['question']
        before = self.child_checkpoint()
        view = self.run.status({'director_run_id': self.parent_id})
        guard = {'director_run_id': self.parent_id, 'expected_run_sha256': view['run_sha256']}
        paused = self.run.lifecycle('run-pause', guard)
        self.assertEqual(paused['phase'], 'paused')
        self.assertEqual(self.child_checkpoint(), before)
        resumed = self.run.lifecycle('run-resume', {**guard, 'expected_run_sha256': paused['run_sha256']})
        self.assertEqual(resumed['phase'], 'running')
        self.run.lifecycle('run-cancel', {**guard, 'expected_run_sha256': resumed['run_sha256']})
        with self.assertRaisesRegex(ValueError, 'running'):
            self.run.answer(self.response(question))
        self.assertEqual(self.child_checkpoint(), before)
        self.assertEqual([(event['event'], event['phase']) for event in self.timeline() if event['event'].startswith('run-')],
                         [('run-started', 'running'), ('run-paused', 'paused'), ('run-resumed', 'running'),
                          ('run-cancelled', 'cancelled')])

    def test_approved_default_uses_exact_fact_and_no_owner_question(self):
        pin = {'area_id': 'art', 'record_id': 'approved-grip', 'revision': 'r1',
               'sha256': 'a' * 64, 'role': 'attachment', 'status': 'verified'}
        self.plan['assignments'][0]['pins'] = [pin]
        self.sha = DIRECTOR._digest(self.plan)
        self.fixture.area['plan_sha256'] = self.sha
        self.launch['plan_sha256'] = self.sha
        self.launch['approved_defaults'] = [{'assignment_id': 'lantern', 'key': 'grip-choice', 'choice': 'hand', 'pin': pin}]
        self.run.verify_pin = lambda observed: observed == pin
        self.start_child()
        response = self.ask()
        self.assertEqual(response['status'], 'delivered')
        self.assertEqual(response['delivery']['answer']['origin'], 'approved-default')
        self.assertEqual(response['delivery']['child_run_id'], self.child_run)
        self.assertIsNone(self.child_checkpoint()['stop_reason'])

    def test_late_owner_answer_leaves_same_hold(self):
        self.start_child()
        question = self.ask()['question']
        real_checkpoint = self.child_checkpoint()
        with patch.object(RUN, 'datetime') as clock:
            clock.now.return_value = datetime(2100, 1, 1, tzinfo=timezone.utc)
            clock.fromisoformat.side_effect = datetime.fromisoformat
            with self.assertRaisesRegex(ValueError, 'expired'):
                self.run.answer(self.response(question))
        self.assertEqual(self.child_checkpoint(), real_checkpoint)

    def test_lost_child_answer_acknowledgement_reconciles_original_delivery(self):
        self.start_child()
        question = self.ask()['question']
        response = self.response(question)
        deliver = self.run._question_call
        def lose_receipt(root, context, command, answer=None):
            result = deliver(root, context, command, answer)
            if command == 'director-question-release':
                raise ConnectionError('Lost reply after child commit')
            return result
        with patch.object(self.run, '_question_call', side_effect=lose_receipt):
            with self.assertRaisesRegex(ConnectionError, 'Lost reply'):
                self.run.answer(response)
        child_before_replay = self.child_checkpoint()
        result = self.run.answer(response)
        self.assertEqual(result['delivery']['child_run_id'], self.child_run)
        self.assertEqual(child_before_replay, self.child_checkpoint())
        timeline = self.timeline()
        decisions = [entry for entry in timeline if entry.get('question_id') == question['question_id']]
        self.assertEqual([entry['event'] for entry in decisions],
                         ['question-prepared', 'question-held', 'answer-recorded', 'question-failed', 'answer-delivered'])
        self.assertEqual((decisions[-2]['phase'], decisions[-2]['stage'], decisions[-2]['reason']),
                         ('answer-recorded', 'release-child', 'transport-error'))
        self.assertEqual(decisions[-1]['receipt_sha256'], result['delivery']['receipt_sha256'])
        self.assertTrue(all(entry['attempt_id'] == question['attempt_id'] and entry['child_run_id'] == self.child_run
                            and entry['task_id'] == self.task_id for entry in decisions))
        for private in ('Lost reply after child commit', 'owner-answer-1', 'petr', 'owner-grant', 'Hand grip',
                        'Finalize attachment', str(self.fixture.root)):
            self.assertNotIn(private, WF.dump(timeline))
        self.run.answer(response)
        self.assertEqual(self.timeline(), timeline)

    def test_lost_dispatch_acknowledgement_logs_and_reconciles_original_receipt(self):
        parent = self.start_parent()
        request = {'director_run_id': self.parent_id, 'expected_run_sha256': parent['run_sha256'],
                   'assignment_id': 'independent', 'operation': 'intake',
                   'request': {'expected_source_hash': WF.file_hash(self.child().future)}}
        helper = WF.director_dispatch_helper()
        apply = helper.apply
        def lose_receipt(*args):
            apply(*args)
            raise ConnectionError('Private child response path')
        with patch.object(WF, 'director_dispatch_helper', return_value=helper), patch.object(helper, 'apply', side_effect=lose_receipt):
            with self.assertRaisesRegex(ConnectionError, 'Private child response path'):
                self.run.dispatch(request)
        recovered = self.run.dispatch(request)
        captured = self.timeline()
        self.assertEqual([entry['event'] for entry in captured],
                         ['run-started', 'dispatch-prepared', 'dispatch-invoking', 'dispatch-failed', 'dispatch-recorded'])
        self.assertEqual((captured[-2]['stage'], captured[-2]['reason']), ('invoke-child', 'transport-error'))
        self.assertEqual((captured[-1]['stage'], captured[-1]['pending_id']), ('recover-child-receipt', recovered['result']['id']))
        self.assertNotIn('Private child response path', WF.dump(captured))
        self.assertEqual(self.run.dispatch(request)['status'], 'replayed')
        self.assertEqual(self.timeline(), captured)

    def test_unapproved_processed_body_and_forged_child_release_fail_closed(self):
        body = ('Goal:\n- Stay in scope.\n\nTouch:\n- source.txt\n\nValidation:\n```json\n'
                '{"checks":[{"id":"contract","recipe_id":"static-inspection","criteria":["Stay in scope."],'
                '"sources":["source.txt"],"parameters":{},"assertion":"Stay in scope.","timing":"immediate"}]}\n```\n\n'
                'Acceptance:\n- Stay in scope.\n')
        item = {'title': 'Exact processed task', 'body': body}
        assignment = {**self.plan['assignments'][0], 'write_paths': ['source.txt']}
        expected = DIRECTOR._digest(item)
        self.run._scope_processed_task({**item, 'parent_pending_ids': [WF.identity('P')]}, assignment, expected=expected)
        with self.assertRaisesRegex(ValueError, 'owner-approved body'):
            self.run._scope_processed_task({**item, 'parent_pending_ids': [WF.identity('P')], 'body': body + 'Unreviewed.\n'}, assignment, expected=expected)
        self.start_child()
        question = self.ask()['question']
        _, state, _ = self.run._load(self.parent_id)
        context = self.run._question_context(state, self.plan['assignments'][0], question)
        forged = {'choice': 'hand', 'origin': 'owner', 'actor': 'petr', 'authority_ref': 'owner-grant', 'evidence_sha256': 'b' * 64}
        with self.assertRaisesRegex(ValueError, 'parent answer verifier'):
            QUESTIONS.handle(WF.Store(self.fixture.root, run_id=self.child_run), 'director-question-release', {**context, 'answer': forged})
        with self.assertRaisesRegex(ValueError, 'durable parent answer'):
            self.run._question_call(self.fixture.root, context, 'director-question-release', forged)
        self.assertTrue(self.child_checkpoint()['director_question_hold'])

    def test_pause_before_child_invocation_and_core_checkpoint_cannot_bypass_hold(self):
        self.start_child()
        question = self.ask()['question']
        selected = WF.Store(self.fixture.root, run_id=self.child_run)
        with self.assertRaisesRegex(ValueError, 'exact Director answer handoff'):
            WF.checkpoint(selected, {'stop_reason': None, 'phase': 'implement'})
        WF.resume_admission(selected)
        self.assertEqual(self.child_checkpoint()['director_question_hold']['question_id'], question['question_id'])
        ready = self.run.status({'director_run_id': self.parent_id})
        helper = WF.director_dispatch_helper()
        retain = helper.retain_intent
        def pause_after_intent(*args, **kwargs):
            result = retain(*args, **kwargs)
            latest = self.run.status({'director_run_id': self.parent_id})
            self.run.lifecycle('run-pause', {'director_run_id': self.parent_id, 'expected_run_sha256': latest['run_sha256']})
            return result
        dispatch = {'director_run_id': self.parent_id, 'expected_run_sha256': ready['run_sha256'],
                    'assignment_id': 'independent', 'operation': 'intake',
                    'request': {'expected_source_hash': WF.file_hash(self.child().future)}}
        with patch.object(WF, 'director_dispatch_helper', return_value=helper), patch.object(helper, 'retain_intent', side_effect=pause_after_intent):
            with self.assertRaisesRegex(ValueError, 'cannot dispatch'):
                self.run.dispatch(dispatch)
        envelope = {**self.fixture.area, 'assignment_id': 'independent'}
        self.assertEqual(DISPATCH.observe(self.child(), {'operation': 'intake', 'director_dispatch': envelope})['status'], 'absent')
        self.assertEqual(self.child_checkpoint()['director_question_hold']['question_id'], question['question_id'])

    def test_plan_and_owner_limits_disallow_extra_effects(self):
        view = self.start_parent()
        with self.assertRaisesRegex(ValueError, 'scope'):
            self.run.start({**self.launch, 'director_run_id': WF.identity('DR'),
                            'authority': {**self.launch['authority'], 'lantern': ['launch', 'commit']}})
        with self.assertRaisesRegex(ValueError, 'effect'):
            self.run.dispatch({'director_run_id': self.parent_id, 'expected_run_sha256': view['run_sha256'],
                               'assignment_id': 'independent', 'operation': 'install', 'request': {}})


if __name__ == '__main__':
    unittest.main()
