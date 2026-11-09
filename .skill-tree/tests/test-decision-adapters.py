"""Behavioral workflow/review decision adapter controls; actor inputs are unit fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

fixture = load('decision_adapter_fixture', CORE / 'tests/test-task-clarification.py')
wf = fixture.wf
pr = load('decision_adapter_review', CORE / 'common/scripts/pr-review-state.py')
sha = lambda value: hashlib.sha256(value.encode()).hexdigest()

def context(kind='request', identity='request-one', **extra):
    return {'kind': kind, 'id': identity, 'semantic_fingerprint': sha('selected meaning'),
            'content_fingerprint': sha('selected content'), **extra}

def authority(identity):
    return {'id': 'bounded-fixture-grant', 'revision': 1, 'context_id': identity,
            'allowed_kinds': ['product', 'technical', 'specification-acceptance'],
            'constraints': ['Preserve the exact selected scope and required checks.'],
            'evidence': {'kind': 'owner-message', 'reference': 'Synthetic unit fixture grant; no live owner consent.'}}

def request(ctx, mode='manual'):
    return {'request_id': 'unit-decision', 'context': ctx, 'mode': mode,
            'question': {'id': 'choice', 'kind': 'technical', 'text': 'Choose bounded behavior.',
                         'options': [{'id': 'keep', 'text': 'Retain bounded behavior.'}],
                         'recommendation': 'keep', 'significance': 'routine'},
            'authority': authority(ctx['id']), 'executor': {'id': 'executor', 'context_id': 'executor-context'}}

class DecisionAdapterTests(unittest.TestCase):
    setUp = fixture.TaskClarificationTests.setUp
    body = fixture.TaskClarificationTests.body
    task = fixture.TaskClarificationTests.task
    call = fixture.TaskClarificationTests.call
    source_hash = fixture.TaskClarificationTests.source_hash
    start = fixture.TaskClarificationTests.start
    question = fixture.TaskClarificationTests.question
    clarity = fixture.TaskClarificationTests.clarity
    answer = fixture.TaskClarificationTests.answer
    snapshot = fixture.TaskClarificationTests.snapshot

    def mutate(self, command, session, ok=True, **extra):
        return self.call(command, {'session_id': session['id'], 'expected_source_hash': self.source_hash(),
                                  'expected_session_hash': session['session_hash'],
                                  'expected_session_revision': session['revision'], **extra}, ok=ok)

    def auto_options(self):
        return {'decision_mode': 'auto', 'decision_authority': authority('task-scope:' + self.a),
                'decision_executor': {'id': 'executor', 'context_id': 'executor-context'}}

    def decision_change(self, record, command, **extra):
        return wf.decision_action(self.store, 'decision-' + command,
                                  {'decision_id': record['id'], 'expected_decision_hash': record['decision_hash'],
                                   'expected_decision_revision': record['revision'], 'expected_mode_epoch': record['mode_epoch'],
                                   'expected_context_fingerprint': record['context']['content_fingerprint'],
                                   'expected_source_hash': self.source_hash(), **extra})

    def delegated_decision(self, ctx, question=None, grant=None, executor=None, pending=False):
        self.decision_count = getattr(self, 'decision_count', 0) + 1
        payload = request(ctx, 'auto')
        payload.update(request_id='fixture-decision-' + str(self.decision_count),
                       authority=grant or authority(ctx['id']), expected_source_hash=self.source_hash())
        if executor is not None:
            payload['executor'] = executor
        if question is not None:
            payload['question'].update(question)
        record = wf.decision_action(self.store, 'decision-start', payload)
        self.assertRegex(record.get('id', ''), r'^DG-[a-f0-9-]{36}$')
        actor = {'id': 'synthetic-resolver-' + str(self.decision_count), 'context_id': 'synthetic-context-' + str(self.decision_count)}
        record = self.decision_change(record, 'prepare', role='resolver', actor=actor)
        if pending:
            return record
        record = self.decision_change(record, 'record', attempt_id=record['prepared_attempt_id'],
                                      result={'status': 'answered', 'answer': 'keep', 'rationale': 'Synthetic bounded unit decision.'},
                                      evidence={'kind': 'delegated-agent', 'reference': 'Synthetic unit actor input; no actual host observation.',
                                                'actor_id': actor['id'], 'actor_context_id': actor['context_id']})
        return self.decision_change(record, 'accept')

    def clarification_decision(self, session, purpose='answer', pending=False):
        key = 'choice' if purpose == 'answer' else None
        ctx = wf.clarification_decision_context(session, purpose, key)
        question = wf.clarification_decision_question(session, purpose, key)
        return self.delegated_decision(ctx, question, session['decision_authority'], session['decision_executor'], pending)

    def reference(self, record):
        self.assertIsNotNone(record.get('acceptance'))
        return {'decision_id': record['id'], 'acceptance_digest': record['acceptance']['digest']}

    def test_runnable_workflow_and_review_adapter_interfaces(self):
        for function in [wf.decision_action, wf.clarification_decision_mode,
                         wf.clarification_decision_context, pr.decision_context, pr.decision_acceptance]:
            self.assertTrue(callable(function))

    def test_task_free_cli_creates_only_a_decision_without_future_or_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = root / 'input.json'
            payload.write_text(json.dumps(request(context())))
            result = subprocess.run(['python3', str(fixture.HELPER), 'decision-start', str(root), '--input', str(payload)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(result.stdout)
            self.assertRegex(record.get('id', ''), r'^DG-[a-f0-9-]{36}$')
            self.assertEqual(len(list((root / '.skill-tree/decisions').glob('dg-*.json'))), 1)
            for path in ['.skill-tree/documents/future.md', '.skill-tree/documents/future.json', '.git']:
                self.assertFalse((root / path).exists(), path)

    def test_typed_task_scope_rejects_a_nonexistent_identity_atomically(self):
        before = self.snapshot()
        ctx = context('task', 'task-scope:missing', task_ids=[wf.identity('T')])
        with self.assertRaises(wf.WorkflowError):
            wf.decision_action(self.store, 'decision-start', request(ctx) | {'expected_source_hash': self.source_hash()})
        self.assertEqual(self.snapshot(), before)

    def test_pre_promotion_decision_uses_real_pending_and_preserves_queue_state(self):
        pending = wf.intake(self.store, {'title': 'Unresolved intake', 'description': 'A bounded choice remains open.', 'expected_behavior': 'The request remains Pending until processing.'})
        before = self.snapshot()
        ctx = context('pending', 'pending-scope:' + pending['id'], pending_ids=[pending['id']])
        record = wf.decision_action(self.store, 'decision-start', request(ctx) | {'expected_source_hash': self.source_hash()})
        self.assertEqual(record.get('context'), ctx)
        self.assertNotIn('task_ids', record['context'])
        self.assertEqual(before, {k: v for k, v in self.snapshot().items() if not k.startswith('decisions/')})

    def test_new_clarification_defaults_manual_before_auto_orchestration_activation(self):
        session = self.start()
        self.assertEqual(session.get('decision_mode'), 'manual')
        self.assertEqual(session.get('decision_mode_epoch'), 0)
        self.assertEqual(session['mode'], 'explicit')

    def test_legacy_owner_only_session_reads_manual_without_rewriting_history(self):
        session = self.start()
        path = wf.clarification_path(self.store, session['id'])
        raw = json.loads(path.read_text())
        for key in list(raw):
            if key.startswith('decision_'):
                raw.pop(key)
        path.write_text(wf.dump(raw))
        before = path.read_bytes()
        loaded = wf.clarification_read(self.store, session['id'])
        self.assertEqual(wf.clarification_decision_mode(loaded), 'manual')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(loaded['mode'], 'explicit')

    def test_auto_clarification_requires_and_freezes_bounded_authority(self):
        self.call('clarify-start', {'task_ids': [self.a], 'expected_source_hash': self.source_hash(), 'decision_mode': 'auto'}, ok=False)
        session = self.start(**self.auto_options())
        self.assertEqual(session.get('decision_mode'), 'auto')
        self.assertEqual(session.get('decision_authority'), self.auto_options()['decision_authority'])
        self.assertEqual(session.get('decision_mode_epoch'), 0)

    def test_clarification_context_binds_session_question_purpose_and_real_semantics(self):
        session = self.start()
        session = self.mutate('clarify-round', session, questions=[self.question()])
        answer = wf.clarification_decision_context(session, 'answer', 'choice')
        final = wf.clarification_decision_context(session, 'confirmation')
        self.assertEqual(answer.get('task_ids'), [self.a])
        self.assertEqual(answer.get('session_id'), session['id'])
        self.assertEqual(answer.get('question_id'), 'choice')
        self.assertEqual(answer.get('question_revision'), 1)
        self.assertEqual(answer.get('parent_mode_epoch'), 0)
        self.assertNotEqual(answer.get('semantic_fingerprint'), final.get('semantic_fingerprint'))
        self.assertRegex(answer.get('semantic_fingerprint', ''), r'^[a-f0-9]{64}$')

    def test_auto_final_acceptance_cannot_use_legacy_owner_evidence(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'owner-message', 'reference': 'Synthetic unit input, not a delegated Auto result.'}, ok=False)

    def test_explicit_switch_reopens_current_confirmation_and_preserves_owner_history(self):
        session = self.start()
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'owner-message', 'reference': 'Synthetic current Manual confirmation.'})
        original = copy.deepcopy(session['confirmation'])
        session = self.mutate('clarify-switch-mode', session, decision_mode='auto', decision_authority=self.auto_options()['decision_authority'], decision_executor=self.auto_options()['decision_executor'], evidence={'kind': 'owner-message', 'reference': 'Synthetic explicit mode-switch input.'})
        self.assertEqual(session.get('decision_mode'), 'auto')
        self.assertEqual(session.get('decision_mode_epoch'), 1)
        self.assertIsNone(session['confirmation'])
        self.assertNotEqual(session['state'], 'complete')
        self.assertTrue(any(item.get('previous_confirmation') == original for item in session.get('decision_mode_history', [])))

    def test_decision_files_participate_in_existing_writer_compare_and_swap(self):
        relative = '.skill-tree/decisions/dg-11111111-1111-4111-8111-111111111111.json'
        path = self.root / relative
        path.parent.mkdir()
        path.write_text('{"original":true}\n')
        with self.store.lock():
            path.write_text('{"concurrent":true}\n')
            with self.assertRaises(wf.WorkflowError):
                self.store.commit({relative: '{"overwritten":true}\n'})
        self.assertEqual(path.read_text(), '{"concurrent":true}\n')

    def test_review_context_changes_with_current_head_base_and_required_checks(self):
        snapshot = {'head': 'a' * 40, 'base_oid': 'b' * 40, 'target_branch': 'codex/next-version',
                    'repo_id': 'repo-one', 'changed_files': ['source.py'], 'checks_known': True,
                    'checks': [{'name': 'unit', 'required': True, 'status': 'pending'}]}
        current = pr.decision_context(snapshot)
        self.assertEqual(current.get('kind'), 'review')
        self.assertEqual(current.get('head'), snapshot['head'])
        self.assertEqual(current.get('base_oid'), snapshot['base_oid'])
        self.assertNotEqual(current.get('semantic_fingerprint'), pr.decision_context(snapshot | {'head': 'c' * 40}).get('semantic_fingerprint'))
        self.assertNotEqual(current.get('semantic_fingerprint'), pr.decision_context(snapshot | {'checks': []}).get('semantic_fingerprint'))

    def test_every_workflow_or_review_package_carries_the_shared_helper(self):
        resources = json.loads((CORE / 'config/resource-map.json').read_text())
        required = []
        for operation, item in resources.items():
            if set(item.get('scripts', {})) & {'workflow-state.py', 'pr-review-state.py'}:
                required.append(operation)
                self.assertEqual(item['scripts'].get('decision-governance.py'), 'common/scripts/decision-governance.py', operation)
        self.assertTrue(required)

    def test_auto_answer_and_separate_current_final_acceptance_use_live_receipts(self):
        before = self.snapshot()
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session)
        answer_ref = self.reference(decision)
        session = self.mutate('clarify-answer', session, round_id=session['rounds'][-1]['id'],
                              question_id='choice', question_revision=1, answer='keep', decision_receipt=answer_ref)
        self.assertEqual(session['answers']['choice']['evidence']['kind'], 'delegated-agent')
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], decision_receipt=answer_ref, ok=False)
        acceptance = self.clarification_decision(session, 'confirmation')
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], decision_receipt=self.reference(acceptance))
        self.assertEqual(session['state'], 'complete')
        self.assertEqual(session['confirmation']['evidence']['kind'], 'delegated-agent')
        self.assertEqual(session['confirmation']['decision_mode'], 'auto')
        self.assertEqual(before, {k: v for k, v in self.snapshot().items() if not k.startswith(('decisions/', 'clarifications/'))})

    def test_receipt_cannot_answer_another_session_or_a_later_mode_epoch(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session)
        reference = self.reference(decision)
        other_options = self.auto_options()
        other_options['decision_authority'] = authority('task-scope:' + self.b)
        other = self.start([self.b], **other_options)
        other = self.mutate('clarify-round', other, questions=[self.question(task=self.b)])
        self.mutate('clarify-answer', other, round_id=other['rounds'][-1]['id'], question_id='choice', question_revision=1, answer='keep', decision_receipt=reference, ok=False)
        evidence = {'kind': 'owner-message', 'reference': 'Synthetic explicit mode switch.'}
        session = self.mutate('clarify-switch-mode', session, decision_mode='manual', evidence=evidence)
        session = self.mutate('clarify-switch-mode', session, **self.auto_options(), evidence=evidence)
        session = self.mutate('clarify-round', session)
        self.assertEqual(session['decision_mode_epoch'], 2)
        self.mutate('clarify-answer', session, round_id=session['rounds'][-1]['id'], question_id='choice', question_revision=1, answer='keep', decision_receipt=reference, ok=False)

    def test_mode_switch_requires_original_pending_actor_reconciliation(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session, pending=True)
        evidence = {'kind': 'owner-message', 'reference': 'Synthetic explicit Manual selection.'}
        self.mutate('clarify-switch-mode', session, decision_mode='manual', evidence=evidence, ok=False)
        decision = self.decision_change(decision, 'reconcile', attempt_id=decision['active_attempt_id'], status='cancelled',
                                        evidence={'kind': 'actor-reconciliation', 'reference': 'Synthetic original actor cancellation.'})
        session = self.mutate('clarify-switch-mode', session, decision_mode='manual', evidence=evidence)
        self.assertEqual(session['decision_mode'], 'manual')
        self.assertEqual(decision['attempts'][decision['prepared_attempt_id']]['status'], 'cancelled')

    def test_review_receipt_preserves_publication_checks_approvals_and_exact_revision(self):
        snapshot = {'repo_id': 'repo-one', 'remote': 'origin', 'source_branch': 'codex/source', 'target_branch': 'codex/next-version',
                    'head': 'a' * 40, 'base_oid': 'b' * 40, 'changed_files': ['source.py'], 'checks_known': True,
                    'checks': [{'name': 'unit', 'required': True, 'status': 'pending'}], 'approved': False}
        ctx = pr.decision_context(snapshot)
        decision = self.delegated_decision(ctx)
        expected = {'context': ctx, 'mode': 'auto', 'mode_epoch': decision['mode_epoch'],
                    'authority_digest': decision['authority_digest'], 'kind': 'technical'}
        record = {'identity': pr.identity(snapshot), 'authorization': {'pr': False, 'merge': False, 'origin': 'owner'},
                  'status': 'review-in-progress', 'ci': 'pending', 'review': None, 'rounds': []}
        before = copy.deepcopy(record)
        accepted = pr.decision_acceptance(self.store, record, snapshot, self.reference(decision), expected)
        self.assertTrue(accepted.get('decision_receipts'))
        self.assertEqual({k: v for k, v in accepted.items() if k != 'decision_receipts'}, before)
        self.assertEqual(record, before)
        for changed in [snapshot | {'head': 'c' * 40}, snapshot | {'checks': []}]:
            with self.assertRaises(pr.ReviewError):
                pr.decision_acceptance(self.store, record, changed, self.reference(decision), expected)
        with self.assertRaises(pr.ReviewError):
            pr.decision_acceptance(self.store, record, snapshot, self.reference(decision), expected | {'kind': 'merge'})

    def test_auto_formatting_preserves_acceptance_and_semantic_edits_reopen_affected_answers(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        answer = self.clarification_decision(session)
        session = self.mutate('clarify-answer', session, round_id=session['rounds'][-1]['id'], question_id='choice', question_revision=1, answer='keep', decision_receipt=self.reference(answer))
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        final = self.clarification_decision(session, 'confirmation')
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], decision_receipt=self.reference(final))
        accepted = copy.deepcopy(session['confirmation'])
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body().replace('Goal:\n', 'Goal:\n\n')}])
        self.assertEqual(session['confirmation'], accepted)
        wf.clarification_admission(self.store, self.a)
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body('Select another behavior.')}])
        self.assertIsNone(session['confirmation'])
        self.assertFalse(session['answers']['choice']['valid'])
        self.assertEqual(session['answers']['choice']['evidence']['kind'], 'delegated-agent')
        with self.assertRaises(wf.WorkflowError):
            wf.clarification_admission(self.store, self.a)

    def test_admission_revalidates_current_receipt_instead_of_trusting_completed_flag(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        final = self.clarification_decision(session, 'confirmation')
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], decision_receipt=self.reference(final))
        wf.clarification_admission(self.store, self.a)
        # Controlled direct ledger revocation tests the consumer's live evidence
        # guard independently from the parent adapter's stricter switch policy.
        helper = wf.decision_helper()
        helper.mutate(self.store, 'decision-switch', {'decision_id': final['id'], 'expected_decision_hash': final['decision_hash'],
                      'expected_decision_revision': final['revision'], 'expected_mode_epoch': final['mode_epoch'],
                      'expected_context_fingerprint': final['context']['content_fingerprint'], 'mode': 'manual'})
        with self.assertRaises(wf.WorkflowError):
            wf.clarification_admission(self.store, self.a)
        self.assertEqual(wf.clarification_read(self.store, session['id'])['confirmation'], session['confirmation'])

    def test_bound_decision_resume_cannot_substitute_another_question(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session)
        before = self.snapshot()
        with self.assertRaises(wf.WorkflowError):
            self.decision_change(decision, 'resume', context=decision['context'], question=decision['question'] | {'text': 'An unrelated decision.'})
        self.assertEqual(self.snapshot(), before)

    def test_controller_decision_requires_an_existing_recorded_run(self):
        before = self.snapshot()
        ctx = context('controller', 'unknown-controller', run_id=wf.identity('WR'))
        with self.assertRaises(wf.WorkflowError):
            wf.decision_action(self.store, 'decision-start', request(ctx) | {'expected_source_hash': self.source_hash()})
        self.assertEqual(before, self.snapshot())

    def test_copied_workflow_and_review_packages_bootstrap_decisions_in_all_flavors(self):
        names = ['skill-tree-clarify-tasks', 'skill-tree-pr-review-cycle']
        for flavor in ['general', 'web', 'unity']:
            with self.subTest(flavor=flavor), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root = base / 'project'
                root.mkdir()
                (root / 'package.json').write_text(json.dumps({'scripts': {'test': 'node --test'}}))
                if flavor == 'unity':
                    (root / 'ProjectSettings').mkdir()
                    (root / 'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.3.27f2\n')
                    (root / 'Packages').mkdir()
                    (root / 'Packages/manifest.json').write_text(json.dumps({'dependencies': {'com.unity.test-framework': '1.6.0'}}))
                    (root / 'Packages/packages-lock.json').write_text(json.dumps({'dependencies': {'com.unity.test-framework': {'version': '1.6.0'}}}))
                result = subprocess.run(['node', str(CORE / 'bin/install.js'), '--target', str(root), '--only', 'codex',
                                         '--flavor', flavor, '--copy', '--skills', *names], text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                for name in names:
                    shutil.copytree(root / '.agents/skills' / name, base / name)
                shutil.rmtree(root / '.agents')
                shutil.rmtree(root / '.skill-tree/installation')
                for name in names:
                    scripts = base / name / 'scripts'
                    self.assertTrue((scripts / 'decision-governance.py').is_file())
                    payload = request(context(identity=name))
                    payload['request_id'] = name
                    path = base / 'input.json'
                    path.write_text(json.dumps(payload))
                    result = subprocess.run(['python3', str(scripts / 'workflow-state.py'), 'decision-start', str(root), '--input', str(path)], text=True, capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout)['context']['id'], name)
                self.assertFalse((root / '.skill-tree/documents').exists())
                self.assertFalse((root / '.git').exists())
                self.assertEqual(len(list((root / '.skill-tree/decisions').glob('dg-*.json'))), 2)

    def test_cancellation_waits_for_original_actor_and_rejects_late_results(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session, pending=True)
        self.mutate('clarify-cancel', session, reason='Synthetic cancellation request.', ok=False)
        decision = self.decision_change(decision, 'reconcile', attempt_id=decision['active_attempt_id'], status='cancelled',
                                        evidence={'kind': 'actor-reconciliation', 'reference': 'Synthetic original actor cancellation.'})
        session = self.mutate('clarify-cancel', session, reason='The original actor is reconciled.')
        self.assertEqual(session['state'], 'cancelled')
        wf.clarification_admission(self.store, self.a)
        before = self.snapshot()
        with self.assertRaises(wf.WorkflowError):
            self.decision_change(decision, 'prepare', role='resolver', actor={'id': 'late-actor', 'context_id': 'late-context'})
        with self.assertRaises(wf.WorkflowError):
            self.decision_change(decision, 'record', attempt_id=decision['prepared_attempt_id'],
                                 result={'status': 'answered', 'answer': 'keep', 'rationale': 'Late result cannot revive cancellation.'},
                                 evidence={'kind': 'delegated-agent', 'reference': 'Synthetic late delivery.',
                                           'actor_id': 'synthetic-resolver-1', 'actor_context_id': 'synthetic-context-1'})
        self.assertEqual(self.snapshot(), before)

    def test_original_actor_cleanup_survives_missing_former_queue_without_recreation(self):
        session = self.start(**self.auto_options())
        session = self.mutate('clarify-round', session, questions=[self.question()])
        decision = self.clarification_decision(session, pending=True)
        # Controlled missing-scope damage cannot strand cleanup or authorize a
        # successful answer. Normal decision mutations still require live scope.
        checkpoint = self.store.state.read_bytes()
        self.store.future.unlink()
        decision = self.decision_change(decision, 'reconcile', attempt_id=decision['active_attempt_id'], status='cancelled',
                                        evidence={'kind': 'actor-reconciliation', 'reference': 'Synthetic cleanup after scope removal.'})
        self.assertIsNone(decision['active_attempt_id'])
        self.assertFalse(self.store.future.exists())
        self.assertEqual(self.store.state.read_bytes(), checkpoint)

if __name__ == '__main__':
    unittest.main()
