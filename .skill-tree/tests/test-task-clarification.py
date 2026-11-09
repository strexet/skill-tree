import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

CORE = Path(__file__).resolve().parents[1]
HELPER = CORE / 'common/scripts/workflow-state.py'
spec = importlib.util.spec_from_file_location('clarification_workflow', HELPER)
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)


class TaskClarificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = self.store.base / 'config'
        config.mkdir()
        (config / 'repository.json').write_text(json.dumps({'schema': 1, 'role': 'source'}))
        (self.root / 'source.py').write_text('VALUE = 1\n')
        self.a = self.task('Selected task', 100)
        self.b = self.task('Unrelated task', 200)

    def body(self, goal='Preserve selected behavior.'):
        criterion = 'Preserve selected behavior.'
        check = {'id': 'behavior', 'recipe_id': 'static-inspection', 'criteria': [criterion], 'sources': ['source.py'], 'parameters': {}, 'assertion': criterion, 'timing': 'immediate'}
        return 'Goal:\n- ' + goal + '\n\nScope:\n- The selected counter.\n\nOut of scope:\n- Remote services.\n\nTouch:\n- source.py\n\nValidation:\n```json\n' + json.dumps({'checks': [check]}) + '\n```\n\nAcceptance:\n- ' + criterion + '\n'

    def task(self, title, priority=100):
        pending = wf.intake(self.store, {'title': title, 'description': 'Preserve bounded behavior.', 'expected_behavior': 'The selected behavior remains explicit.', 'priority': priority})
        return wf.process(self.store, {'selectors': [pending['id']], 'dispositions': {pending['id']: {'status': 'promoted', 'reason': 'Source research identifies bounded behavior.'}}, 'tasks': [{'title': title, 'body': self.body(), 'parent_pending_ids': [pending['id']]}]})['created_ids'][0]

    def call(self, command, payload=None, ok=True):
        request = self.root / 'request.json'
        request.write_text(json.dumps(payload or {}))
        result = subprocess.run(['python3', str(HELPER), command, str(self.root), '--input', str(request)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if ok else 2, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip(), 'The CLI returns a structured result.')
        value = json.loads(result.stdout)
        if not ok:
            self.assertFalse(value['ok'])
        return value

    def source_hash(self):
        return wf.file_hash(self.store.future)

    def start(self, ids=None, **extra):
        return self.call('clarify-start', {'task_ids': ids or [self.a], 'expected_source_hash': self.source_hash(), **extra})

    def mutate(self, command, session, **extra):
        return self.call(command, {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], **extra})

    def question(self, key='choice', fields=None, prerequisites=None, task=None):
        return {'id': key, 'text': 'Choose the observable behavior.', 'recommendation': 'Retain the explicit selected behavior.', 'prerequisites': prerequisites or [], 'bindings': {task or self.a: fields or ['goal']}}

    def clarity(self):
        return {key: True for key in ['goals', 'scope', 'exclusions', 'dependencies', 'acceptance', 'validation', 'decisions'] } | {'evidence': ['The selected task and source.py define feasible observable behavior.']}

    def answer(self, session, question='choice', text='Retain the selected behavior.'):
        return self.mutate('clarify-answer', session, round_id=session['rounds'][-1]['id'], question_id=question, question_revision=session['questions'][question]['revision'], answer=text, evidence={'kind': 'owner-message', 'reference': 'Owner message: ' + text})

    def snapshot(self):
        return {p.relative_to(self.store.base).as_posix(): p.read_bytes() for p in self.store.base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def finish_task(self, tid):
        wf.begin_task(self.store, {'task_id': tid})
        attempt = wf.prepare_check(self.store, {'task_id': tid, 'check_id': 'behavior'})
        (self.root / 'completion-evidence.txt').write_text('The source assertion preserves selected behavior.\n')
        wf.record_check(self.store, {'task_id': tid, 'check_id': 'behavior', 'attempt_id': attempt['attempt_id'], 'result': 'pass', 'classification': 'executed-control', 'actual_lane': 'static', 'environment_identity': attempt['environment_identity'], 'assertions': [{'assertion': 'Preserve selected behavior.', 'result': 'pass'}], 'cleanup': 'No runtime process remains.', 'evidence': ['completion-evidence.txt']})
        wf.mark_implemented(self.store, {'task_id': tid})
        return wf.complete(self.store, {'task_id': tid, 'outcome': 'The selected source behavior is accepted.', 'acceptance': [{'criterion': 'Preserve selected behavior.', 'result': 'pass', 'evidence': ['completion-evidence.txt']}], 'source_fingerprints': wf.fingerprints(self.store, ['source.py'])})

    def test_cli_round_answer_recheck_confirmation_never_implements(self):
        before = self.snapshot()
        session = self.start()
        self.assertEqual(session['task_ids'], [self.a])
        session = self.mutate('clarify-round', session, questions=[self.question()])
        self.assertEqual(session['state'], 'awaiting-answers')
        session = self.answer(session)
        self.assertEqual(session['state'], 'revising')
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        self.assertEqual(session['state'], 'awaiting-confirmation')
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'owner-message', 'reference': 'Owner confirms the displayed current task summary.'})
        self.assertEqual(session['state'], 'complete')
        self.assertIsNone(self.store.load()['active_run'])
        self.assertEqual(self.store.load()['task_progress'], {})
        self.assertEqual(self.store.outcomes(), [])
        self.assertEqual(before, {k: v for k, v in self.snapshot().items() if not k.startswith('clarifications/')})

    def test_exact_unique_scope_and_invalid_start_are_atomic(self):
        missing = wf.identity('T')
        self.task(missing)
        for ids in [[], [self.a, self.a], [missing], [wf.identity('P')], [self.a, wf.identity('T')]]:
            before = self.snapshot()
            self.call('clarify-start', {'task_ids': ids, 'expected_source_hash': self.source_hash()}, ok=False)
            self.assertEqual(before, self.snapshot())
        self.assertEqual(self.start([self.a, self.b])['task_ids'], [self.b, self.a])

    def test_required_source_and_session_guards_reject_stale_writes(self):
        self.call('clarify-start', {'task_ids': [self.a]}, ok=False)
        session = self.start()
        for change in [{'expected_source_hash': 'stale'}, {'expected_session_hash': 'stale'}, {'expected_session_revision': 0}]:
            before = self.snapshot()
            self.call('clarify-round', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], **change}, ok=False)
            self.assertEqual(before, self.snapshot())

    def test_open_hold_blocks_only_selected_task_and_cancellation_releases_explicit_hold(self):
        session = self.start()
        self.call('select', {}, ok=True)
        with self.assertRaises(wf.WorkflowError):
            wf.begin_task(self.store, {'task_id': self.a})
        self.assertEqual(wf.start(self.store, 'all', workspace={'snapshot_ids': [self.b]})['snapshot'], [self.b])
        before = self.store.state.read_bytes()
        session = self.mutate('clarify-cancel', session, reason='The owner ends this discussion.')
        self.assertEqual(session['state'], 'cancelled')
        self.assertEqual(before, self.store.state.read_bytes())
        self.assertEqual(self.call('select', {})['id'], self.b)

    def test_dependent_questions_wait_for_actual_answer_and_replay_conflicts(self):
        session = self.start()
        session = self.mutate('clarify-round', session, questions=[self.question(), self.question('dependent', ['scope'], ['choice'])])
        self.assertEqual(session['rounds'][-1]['question_ids'], ['choice'])
        before = self.snapshot()
        self.call('clarify-answer', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'round_id': session['rounds'][-1]['id'], 'question_id': 'dependent', 'question_revision': 1, 'answer': 'An inferred default.', 'evidence': {'kind': 'recommendation', 'reference': 'Agent default.'}}, ok=False)
        self.assertEqual(before, self.snapshot())
        session = self.answer(session)
        repeated = self.answer(session)
        self.assertEqual(repeated, session)
        before = self.snapshot()
        self.call('clarify-answer', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'round_id': session['rounds'][-1]['id'], 'question_id': 'choice', 'question_revision': 1, 'answer': 'A conflicting answer.', 'evidence': {'kind': 'owner-message', 'reference': 'Changed replay.'}}, ok=False)
        self.assertEqual(before, self.snapshot())
        session = self.mutate('clarify-round', session)
        self.assertEqual(session['rounds'][-1]['question_ids'], ['dependent'])

    def test_revision_preserves_provenance_and_reopens_only_affected_answers(self):
        session = self.start([self.a, self.b])
        session = self.mutate('clarify-round', session, questions=[self.question(), self.question('other', ['scope'], task=self.b)])
        session = self.answer(session)
        session = self.answer(session, 'other')
        before_task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}])
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        for field in wf.FIELDS:
            self.assertEqual(task[field], before_task[field])
        self.assertFalse(session['answers']['choice']['valid'])
        self.assertTrue(session['answers']['other']['valid'])
        self.assertIsNone(session['confirmation'])

    def test_resume_preserves_scope_and_formatting_confirmation_but_reopens_semantic_drift(self):
        session = self.start()
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        session = self.mutate('clarify-confirm', session, task_ids=[self.a], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'submitted-answer', 'reference': 'Owner confirmed current exact scope.'})
        self.task('Later higher priority', 999)
        self.store.future.write_text(self.store.text().replace('- Preserve selected behavior.', '-   Preserve selected behavior.'))
        session = self.mutate('clarify-resume', session)
        self.assertEqual(session['state'], 'complete')
        self.assertEqual(session['task_ids'], [self.a])
        self.store.future.write_text(self.store.text().replace('The selected counter.', 'The selected Counter.'))
        session = self.mutate('clarify-resume', session)
        self.assertEqual(session['state'], 'researching')
        self.assertIsNone(session['confirmation'])

    def test_revision_rejects_invalid_dependencies_and_unowned_tasks_atomically(self):
        session = self.start()
        for tasks in [[{'task_id': self.b, 'body': self.body()}], [{'task_id': self.a, 'depends_on': [self.a]}], [{'task_id': self.a, 'depends_on': [wf.identity('T')]}], [{'task_id': self.a, 'parent_pending_ids': []}]]:
            before = self.snapshot()
            self.call('clarify-revise', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'tasks': tasks}, ok=False)
            self.assertEqual(before, self.snapshot())
        before = self.snapshot()
        invalid = self.body().replace('Acceptance:\n- Preserve selected behavior.', 'Acceptance:\n- A different acceptance criterion.')
        self.call('clarify-revise', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'tasks': [{'task_id': self.a, 'body': invalid}]}, ok=False)
        self.assertEqual(before, self.snapshot())

    def test_repeated_rounds_without_progress_stop_and_read_is_read_only(self):
        session = self.start()
        session = self.mutate('clarify-round', session)
        session = self.mutate('clarify-round', session)
        session = self.mutate('clarify-round', session)
        self.assertEqual(session['state'], 'blocked')
        before = self.snapshot()
        result = subprocess.run(['python3', str(HELPER), 'clarify-read', str(self.root), '--id', session['id']], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout), session)
        self.assertEqual(before, self.snapshot())

    def test_parked_registry_and_progress_remain_exact_through_revision(self):
        run = wf.start(self.store, 'next', self.a, limits={'retry_used': 2})
        wf.begin_task(self.store, {'task_id': self.a})
        wf.checkpoint(self.store, {'phase': 'blocked', 'stop_reason': 'A required runtime remains unavailable.', 'partial_work': ['source.py']})
        raw = json.loads(self.store.state.read_text())
        parked = raw['active_run']
        raw['schema'] = 3
        raw['run_registry'] = {'schema': 1, 'queue_id': wf.identity('Q'), 'runs': {run['id']: parked}, 'claims': {self.a: run['id']}, 'resources': {'runtime:fixture': {'run_id': run['id']}}}
        raw['active_run'] = None
        self.store.state.write_text(wf.dump(raw))
        before = json.loads(self.store.state.read_text())
        session = self.start()
        self.assertEqual(before, json.loads(self.store.state.read_text()))
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}])
        after = json.loads(self.store.state.read_text())
        for field in ['active_run', 'run_registry', 'task_progress']:
            self.assertEqual(before[field], after[field])
        self.assertEqual(session['task_ids'], [self.a])
        self.assertEqual(list((self.store.base / 'history/run-events').glob('**/*.json')), [])

    def test_revision_preserves_optional_headers_and_rejects_pending_attempt(self):
        text = self.store.text().replace('id: ' + self.a + '\n', 'id: ' + self.a + '\nvalidation_group_id: ' + wf.identity('VG') + '\nboundary_validation: group-end\n', 1)
        self.store.future.write_text(text)
        before_task = wf.resolve(wf.parse(text), [self.a])[0]
        wf.begin_task(self.store, {'task_id': self.a})
        attempt = wf.prepare_check(self.store, {'task_id': self.a, 'check_id': 'behavior'})
        session = self.start()
        before = self.snapshot()
        self.call('clarify-revise', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'tasks': [{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}]}, ok=False)
        self.assertEqual(before, self.snapshot())
        (self.root / 'check-evidence.txt').write_text('The pending attempt ended before source revision.\n')
        wf.record_check(self.store, {'task_id': self.a, 'check_id': 'behavior', 'attempt_id': attempt['attempt_id'], 'result': 'pass', 'classification': 'executed-control', 'actual_lane': 'static', 'environment_identity': attempt['environment_identity'], 'assertions': [{'assertion': 'Preserve selected behavior.', 'result': 'pass'}], 'cleanup': 'No runtime process remains.', 'evidence': ['check-evidence.txt']})
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}])
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        for field in wf.OPTIONAL_FIELDS:
            self.assertEqual(task[field], before_task[field])

    def test_required_interview_cancellation_keeps_hold_without_global_block(self):
        session = self.start(mode='required-interview')
        session = self.mutate('clarify-cancel', session, reason='The owner ends the current interview.')
        with self.assertRaises(wf.WorkflowError):
            wf.start(self.store, 'all', workspace={'snapshot_ids': [self.a]})
        self.assertEqual(wf.start(self.store, 'all', workspace={'snapshot_ids': [self.b]})['snapshot'], [self.b])

    def test_recoverable_revision_and_external_session_conflict(self):
        session = self.start()
        payload = {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'tasks': [{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}]}
        original = self.store.replace
        def crash(path, content):
            if path == self.store.state:
                raise OSError('Injected interrupted index write')
            original(path, content)
        with patch.object(self.store, 'replace', side_effect=crash):
            with self.assertRaises(OSError):
                wf.clarification_mutate(self.store, 'clarify-revise', payload)
        self.assertTrue((self.store.base / '.transaction.json').exists())
        with self.store.lock():
            pass
        recovered = wf.clarification_read(self.store, session['id'])
        self.assertEqual(recovered['revision'], session['revision'] + 1)
        self.assertIn('Preserve revised selected behavior.', self.store.text())
        path = wf.clarification_path(self.store, session['id'])
        with self.store.lock():
            path.write_text(path.read_text() + '\n')
            with self.assertRaisesRegex(wf.WorkflowError, 'changed during'):
                self.store.commit({path.relative_to(self.store.root).as_posix(): wf.dump({k: v for k, v in recovered.items() if k != 'session_hash'})})
        self.assertTrue(path.read_text().endswith('\n\n'))

    def test_semantic_projection_covers_every_dimension_and_preserves_literal_case(self):
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        original = wf.clarification_semantics(task)
        variants = {'title': {'title': 'Changed title'}, 'dependencies': {'depends_on': [self.b]}, 'goal': {'body': task['body'].replace('Goal:\n- Preserve selected behavior.', 'Goal:\n- Preserve revised behavior.')}, 'scope': {'body': task['body'].replace('The selected counter.', 'The selected Counter.')}, 'exclusions': {'body': task['body'].replace('Remote services.', 'Local services.')}, 'acceptance': {'body': task['body'].replace('Acceptance:\n- Preserve selected behavior.', 'Acceptance:\n- Preserve revised behavior.')}, 'validation': {'body': task['body'].replace('"recipe_id": "static-inspection"', '"recipe_id": "other-recipe"')}, 'required_plugin_policy': {'body': task['body'] + '\nRequired plugin policy:\n- Required pinned interview.\n'}, 'content': {'body': task['body'] + '\nImplementation constraints:\n- Preserve `CaseSensitive` identities.\n'}}
        for field, changes in variants.items():
            self.assertNotEqual(original[field], wf.clarification_semantics(task | changes)[field], field)
        formatted = task['body'].replace('- Preserve selected behavior.', '-   **Preserve selected behavior.**')
        self.assertEqual(original, wf.clarification_semantics(task | {'body': formatted}))
        code = task | {'body': task['body'] + '\nCode constraint:\n- Preserve `A  B`.\n'}
        self.assertNotEqual(wf.clarification_semantics(code), wf.clarification_semantics(code | {'body': code['body'].replace('`A  B`', '`A B`')}))
        self.assertNotEqual(original['validation'], wf.clarification_semantics(task | {'validation_group_id': wf.identity('VG')})['validation'])
        self.assertNotEqual(original['validation'], wf.clarification_semantics(task | {'boundary_validation': 'group-end'})['validation'])

    def test_saved_source_facts_require_current_origin_and_matching_bytes(self):
        session = self.start()
        fact = {'id': 'counter-source', 'observation': 'The counter defines the selected value.', 'sources': [{'path': 'source.py', 'sha256': wf.file_hash(self.root / 'source.py')}], 'limitations': ['No runtime execution.']}
        session = self.mutate('clarify-round', session, facts=[fact], clarity=self.clarity())
        self.assertEqual(session['state'], 'awaiting-confirmation')
        (self.root / 'source.py').write_text('VALUE = 2\n')
        before = self.snapshot()
        self.call('clarify-confirm', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'task_ids': session['task_ids'], 'semantic_fingerprints': session['semantic_fingerprints'], 'evidence': {'kind': 'owner-message', 'reference': 'The owner confirmed an outdated source summary.'}}, ok=False)
        self.assertEqual(before, self.snapshot())
        session = self.mutate('clarify-resume', session)
        self.assertEqual(session['state'], 'blocked')
        self.assertEqual(session['stale_facts'], ['counter-source'])
        fact['sources'][0]['sha256'] = wf.file_hash(self.root / 'source.py')
        session = self.mutate('clarify-round', session, facts=[fact], clarity=self.clarity())
        self.assertEqual(session['state'], 'awaiting-confirmation')

    def test_open_session_blocks_terminalization_of_already_begun_task(self):
        wf.begin_task(self.store, {'task_id': self.a})
        self.start()
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'clarification hold'):
            wf.complete(self.store, {'task_id': self.a, 'disposition': 'cancelled', 'outcome': 'The selected task is withdrawn.'})
        self.assertEqual(before, self.snapshot())

    def test_protected_identity_drift_rejects_resume_without_overwriting_external_edit(self):
        session = self.start()
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        text = self.store.text().replace(task['body'], task['body'].replace('parent_pending_ids: [', 'parent_pending_ids: ["' + wf.identity('P') + '", ', 1))
        self.store.future.write_text(text)
        before = self.snapshot()
        self.call('clarify-resume', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision']}, ok=False)
        self.assertEqual(before, self.snapshot())

    def test_external_queue_edit_during_session_only_mutation_is_preserved(self):
        session = self.start()
        session_path = wf.clarification_path(self.store, session['id'])
        before = session_path.read_bytes()
        original = wf.clarification_round
        def external_edit(store, record, payload):
            original(store, record, payload)
            store.future.write_text(store.text() + '\nExternal developer queue note.\n')
        payload = {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision']}
        with patch.object(wf, 'clarification_round', side_effect=external_edit):
            with self.assertRaisesRegex(wf.WorkflowError, 'Source changed'):
                wf.clarification_mutate(self.store, 'clarify-round', payload)
        self.assertEqual(before, session_path.read_bytes())
        self.assertIn('External developer queue note.', self.store.text())

    def test_invalidated_answer_cannot_reuse_pre_revision_round_context(self):
        session = self.start()
        session = self.mutate('clarify-round', session, questions=[self.question()])
        session = self.answer(session)
        old_round = session['rounds'][-1]['id']
        session = self.mutate('clarify-revise', session, tasks=[{'task_id': self.a, 'body': self.body('Preserve revised selected behavior.')}])
        self.assertFalse(session['answers']['choice']['valid'])
        before = self.snapshot()
        self.call('clarify-answer', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'round_id': old_round, 'question_id': 'choice', 'question_revision': 1, 'answer': 'Retain the selected behavior.', 'evidence': {'kind': 'owner-message', 'reference': 'Owner message: Retain the selected behavior.'}}, ok=False)
        self.assertEqual(before, self.snapshot())
        session = self.mutate('clarify-round', session)
        self.assertNotEqual(old_round, session['rounds'][-1]['id'])
        self.assertEqual(session['rounds'][-1]['question_ids'], ['choice'])
        session = self.answer(session, text='Retain the revised selected behavior.')
        self.assertTrue(session['answers']['choice']['valid'])

    def test_replacement_body_cannot_inject_tasks_or_move_queue_boundaries(self):
        session = self.start()
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        meta = {key: task[key] for key in wf.FIELDS}
        meta['id'] = wf.identity('T')
        meta['root_task_id'] = meta['id']
        injected = wf.render('Injected unselected task', meta, self.body())
        for body in [self.body() + injected, self.body() + '\n## Backlog\n' + injected, self.body() + '\n## Outside section\nRemoved selected task boundary.\n']:
            before = self.snapshot()
            self.call('clarify-revise', {'session_id': session['id'], 'expected_source_hash': self.source_hash(), 'expected_session_hash': session['session_hash'], 'expected_session_revision': session['revision'], 'tasks': [{'task_id': self.a, 'body': body}]}, ok=False)
            self.assertEqual(before, self.snapshot())

    def test_group_confirmation_freshness_blocks_every_member_before_and_after_resume(self):
        outside = self.task('Outside selected group', 300)
        session = self.start([self.a, self.b])
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        session = self.mutate('clarify-confirm', session, task_ids=session['task_ids'], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'owner-message', 'reference': 'The owner confirms the current exact task group.'})
        for tid in [self.a, self.b, outside]:
            wf.clarification_admission(self.store, tid)
        task = wf.resolve(wf.parse(self.store.text()), [self.a])[0]
        self.store.future.write_text(self.store.text().replace(task['body'], task['body'].replace('The selected counter.', 'The revised selected counter.')))
        for tid in [self.a, self.b]:
            with self.assertRaisesRegex(wf.WorkflowError, 'clarification hold'):
                wf.clarification_admission(self.store, tid)
        wf.clarification_admission(self.store, outside)
        session = self.mutate('clarify-resume', session)
        for tid in [self.a, self.b]:
            with self.assertRaisesRegex(wf.WorkflowError, 'clarification hold'):
                wf.clarification_admission(self.store, tid)
        wf.clarification_admission(self.store, outside)

    def test_group_end_handoff_rechecks_final_candidate_clarification_hold(self):
        group = wf.identity('VG')
        for tid in [self.a, self.b]:
            task = wf.resolve(wf.parse(self.store.text()), [tid])[0]
            meta = {key: task[key] for key in wf.FIELDS}
            meta.update(validation_group_id=group, boundary_validation='group-end')
            body = self.body().replace('"timing": "immediate"', '"timing": "group-end"')
            self.store.future.write_text(self.store.text().replace(task['body'], wf.render(task['title'], meta, body)))
        wf.start(self.store, 'all', workspace={'snapshot_ids': [self.a, self.b]})
        wf.begin_task(self.store, {'task_id': self.b})
        wf.mark_implemented(self.store, {'task_id': self.b})
        self.assertEqual(wf.next_task(self.store)['task_id'], self.a)
        self.start([self.a])
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'clarification hold'):
            wf.next_task(self.store)
        self.assertEqual(before, self.snapshot())

    def test_completed_member_preserves_confirmed_group_admission_by_exact_outcome(self):
        session = self.start([self.a, self.b])
        session = self.mutate('clarify-round', session, clarity=self.clarity())
        session = self.mutate('clarify-confirm', session, task_ids=session['task_ids'], semantic_fingerprints=session['semantic_fingerprints'], evidence={'kind': 'owner-message', 'reference': 'The owner confirms the current exact task group.'})
        outcome = self.finish_task(self.a)
        self.assertEqual(outcome['task_id'], self.a)
        self.assertGreaterEqual(outcome['recorded_at'], session['confirmation']['recorded_at'])
        wf.clarification_admission(self.store, self.b)
        self.assertEqual(wf.begin_task(self.store, {'task_id': self.b})['task_id'], self.b)

    def test_cancelled_explicit_group_allows_remaining_member_after_completion(self):
        session = self.start([self.a, self.b])
        session = self.mutate('clarify-cancel', session, reason='The owner ends this optional group discussion.')
        self.assertIsNone(session['confirmation'])
        self.finish_task(self.a)
        wf.clarification_admission(self.store, self.b)
        self.assertEqual(wf.begin_task(self.store, {'task_id': self.b})['task_id'], self.b)


if __name__ == '__main__':
    unittest.main()
