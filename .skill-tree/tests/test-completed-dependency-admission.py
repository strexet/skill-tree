"""Cross-run dependency controls use real temporary queues, checks and artifacts."""
import importlib.util
import json
from pathlib import Path
import unittest

CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dependency_workspace_fixtures', CORE/'tests/test-run-workspaces.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
wf = fixtures.wf

class CompletedDependencyAdmissionTests(unittest.TestCase):
    setUp = fixtures.RunWorkspaceTests.setUp
    call = fixtures.RunWorkspaceTests.call
    task = fixtures.RunWorkspaceTests.task
    start = fixtures.RunWorkspaceTests.start
    location = fixtures.RunWorkspaceTests.location
    finish_run = fixtures.RunWorkspaceTests.finish_run

    def dependency(self):
        child = self.task('Completed prerequisite')
        first = self.start(child)
        (self.location(first)/'source.py').write_text('value = 2\n')
        self.finish_run(first)
        parent = self.task('Current consumer', [child])
        second = self.start(parent)
        store = wf.Store(self.location(second))
        (store.source_root/'source.py').write_text('value = 3\n')
        return child, parent, store

    def revalidate(self, store, child, accept=True):
        handoff = wf.advance(store)
        self.assertEqual((handoff['phase'], handoff['task_id']), ('validate', child))
        (store.source_root/'current-report.json').write_text('Current dependency assertion passed.\n')
        attempt = wf.prepare_check(store, {'task_id':child,'check_id':'behavior'})
        wf.record_check(store, {'task_id':child,'check_id':'behavior','attempt_id':attempt['attempt_id'],
            'result':'pass','classification':'executed-control','actual_lane':'static',
            'environment_identity':attempt['environment_identity'],
            'assertions':[{'assertion':'Preserve scoped source behavior.','result':'pass'}],
            'evidence':['current-report.json'],'cleanup':'Temporary fixtures execute no product process.'})
        if accept:
            wf.accept_revalidation(store, {'task_id':child})
        return attempt

    def test_next_selects_changed_completed_dependency_before_consumer_without_writes(self):
        child, parent, store = self.dependency()
        before = store.state.read_bytes()
        handoff = wf.next_task(store)
        self.assertEqual((handoff['phase'], handoff['task_id'], handoff['root_task_id']), ('validate',child,parent))
        self.assertTrue(handoff['completed_contract'])
        self.assertEqual(before, store.state.read_bytes())

    def test_advance_establishes_selected_revalidation_without_a_prepared_attempt(self):
        child, parent, store = self.dependency()
        ledger = (store.base/'history/task-outcomes.jsonl').read_bytes()
        wf.advance(store)
        entry = store.load()['task_progress'][child]
        self.assertEqual(entry['checks'], {})
        wf.assert_scope(store, store.load(), wf.parse(store.text()), child)
        self.revalidate(store, child, accept=False)
        state = store.load()
        self.assertEqual(state['active_run']['current_task_id'], child)
        self.assertEqual(state['active_run']['snapshot'], [parent])
        self.assertTrue(state['task_progress'][child]['revalidation'])
        self.assertEqual((store.base/'history/task-outcomes.jsonl').read_bytes(), ledger)
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})

    def test_fresh_accepted_contract_allows_consumer_without_rewriting_terminal_outcomes(self):
        child, parent, store = self.dependency()
        ledger = (store.base/'history/task-outcomes.jsonl').read_bytes()
        self.revalidate(store, child)
        self.assertEqual(wf.advance(store)['task_id'], parent)
        self.assertEqual(wf.begin_task(store, {'task_id':parent})['phase'], 'implement')
        self.assertEqual((store.base/'history/task-outcomes.jsonl').read_bytes(), ledger)

    def test_changed_source_after_acceptance_returns_to_the_same_contract(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        (store.source_root/'source.py').write_text('value = 4\n')
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})
        self.assertEqual(wf.next_task(store)['task_id'], child)

    def test_missing_or_changed_artifact_never_admits_consumer(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        artifact = store.source_root/'current-report.json'
        for mode in ['changed','missing']:
            with self.subTest(mode=mode):
                if mode == 'missing': artifact.unlink()
                else: artifact.write_text('Unverified replacement.\n')
                with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
                    wf.begin_task(store, {'task_id':parent})

    def test_required_pending_still_precedes_completed_dependency_validation(self):
        child, parent, store = self.dependency()
        pending = wf.intake(store, {'title':'Required infrastructure repair',
            'description':'Repair the source admission contract.', 'expected_behavior':'Preserve the required verification.',
            'root_task_id':parent,'related_task_id':parent,'relation':'blocker'})
        handoff = wf.next_task(store)
        self.assertEqual(handoff['phase'], 'process-required')
        self.assertEqual(handoff['pending_ids'], [pending['id']])

    def test_incomplete_source_coverage_never_establishes_integration(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        self.add_completion_output(store, child)
        with self.assertRaisesRegex(wf.WorkflowError, 'does not cover'):
            wf.begin_task(store, {'task_id':parent})

    def add_completion_output(self, store, child):
        extra = store.source_root/'output.txt'
        extra.write_text('Recorded output not covered by the check.\n')
        # Model an original completion with an additional output fingerprint.
        outcomes = store.outcomes()
        record = next(o for o in outcomes if o['task_id']==child)
        record['source_fingerprints'].update(wf.fingerprints(store, ['output.txt']))
        (store.base/'history/task-outcomes.jsonl').write_text(''.join(json.dumps(o)+'\n' for o in outcomes))
        return extra

    def test_source_review_supplements_accepted_checks_and_expires_on_drift(self):
        child, parent, store = self.dependency()
        extra = self.add_completion_output(store, child)
        extra.write_text('Current reviewed output.\n')
        self.revalidate(store, child)
        cycle_before = wf.record_cycle(store)['cycle_signature']
        ledger = (store.base/'history/task-outcomes.jsonl').read_bytes()
        accepted = store.load()['active_run']['revalidated_checks'][child]
        payload = self.source_review_payload(store, child)
        review = payload['source_review']
        evidence = store.source_root/review['evidence']['path']
        with self.assertRaisesRegex(wf.WorkflowError, 'exact current uncovered'):
            wf.accept_revalidation(store, {'task_id':child, 'source_review':{
                **review, 'sources':wf.fingerprints(store, ['output.txt', 'source.py'])}})
        inspected = evidence.read_bytes()
        evidence.write_text('Changed before acceptance.\n')
        with self.assertRaisesRegex(wf.WorkflowError, 'evidence missing or mismatched'):
            wf.accept_revalidation(store, {'task_id':child, 'source_review':review})
        evidence.write_bytes(inspected)
        wf.accept_revalidation(store, payload)
        self.assertNotEqual(wf.record_cycle(store)['cycle_signature'], cycle_before)
        self.assertEqual(wf.advance(store)['task_id'], parent)
        wf.begin_task(store, {'task_id':parent})
        self.assertEqual(store.load()['active_run']['revalidated_checks'][child], accepted)
        self.assertEqual((store.base/'history/task-outcomes.jsonl').read_bytes(), ledger)
        extra.write_text('Changed after review.\n')
        with self.assertRaisesRegex(wf.WorkflowError, 'does not cover'):
            wf.begin_task(store, {'task_id':parent})
        extra.write_text('Current reviewed output.\n')
        evidence.write_text('Changed after review.\n')
        with self.assertRaisesRegex(wf.WorkflowError, 'does not cover'):
            wf.complete(store, {'task_id':parent, 'outcome':'The consumer is ready.'})
        (store.source_root/'source.py').write_text('value = 4\n')
        self.revalidate(store, child)
        self.assertNotIn(child, store.load()['active_run']['revalidation_source_reviews'])
        payload = self.source_review_payload(store, child)
        wf.accept_revalidation(store, payload)
        self.assertIsNone(wf.record_cycle(store)['stop_reason'])
        report = json.loads(evidence.read_text())
        evidence.write_text(wf.dump({**report,'summary':'The same review with a wording change.'}))
        payload['source_review']['evidence']['sha256'] = wf.file_hash(evidence)
        wf.accept_revalidation(store, payload)
        self.assertIn('without task/dependency progress', wf.record_cycle(store)['stop_reason'])

    def complete_unit(self, store, tid, paths):
        wf.begin_task(store, {'task_id':tid})
        wf.mark_implemented(store, {'task_id':tid})
        artifact = store.source_root / f'{tid}-check.json'
        artifact.write_text('Current fixture assertion passed.\n')
        attempt = wf.prepare_check(store, {'task_id':tid,'check_id':'behavior'})
        wf.record_check(store, {'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],
            'result':'pass','classification':'executed-control','actual_lane':'static',
            'environment_identity':attempt['environment_identity'],
            'assertions':[{'assertion':'Preserve scoped source behavior.','result':'pass'}],
            'evidence':[artifact.name],'cleanup':'Static inspection only.'})
        wf.complete(store, {'task_id':tid,'outcome':'Scoped source behavior remains intact.',
            'acceptance':[{'criterion':'Preserve scoped source behavior.','result':'pass','evidence':[artifact.name]}],
            'source_fingerprints':wf.fingerprints(store,paths)})

    def source_review_payload(self, store, tid):
        handoff = wf.next_task(store)
        self.assertEqual((handoff['task_id'],handoff['checks']), (tid,[]))
        claims = handoff['source_review']
        report = store.source_root / 'source-review.json'
        report.write_text(wf.dump(claims))
        return {'task_id':tid,'source_review':{'sources':claims['sources'],
                'evidence':{'path':report.name,'sha256':wf.file_hash(report)}}}

    def test_review_artifact_cannot_attest_to_a_different_source_revision(self):
        child, parent, store = self.dependency()
        output = self.add_completion_output(store, child)
        output.write_text('Reviewed revision.\n')
        self.revalidate(store, child)
        payload = self.source_review_payload(store, child)
        wf.accept_revalidation(store, payload)
        output.write_text('Unreviewed revision.\n')
        payload['source_review']['sources'] = wf.fingerprints(store,[output.name])
        with self.assertRaisesRegex(wf.WorkflowError, 'review artifact.*match'):
            wf.accept_revalidation(store, payload)
        with self.assertRaisesRegex(wf.WorkflowError, 'does not cover'):
            wf.begin_task(store, {'task_id':parent})

    def test_finish_selects_dependency_output_drift_without_prior_revalidation(self):
        child = self.task('Prerequisite')
        parent = self.task('Consumer', [child])
        store = wf.Store(self.location(self.start(parent)))
        output = store.source_root / 'output.txt'
        output.write_text('Original output.\n')
        self.complete_unit(store, child, ['source.py',output.name])
        self.complete_unit(store, parent, ['source.py'])
        output.write_text('Changed outside the check contract.\n')
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.finish(store)
        self.revalidate(store, child)
        handoff = wf.advance(store)
        self.assertEqual((handoff['phase'],handoff['task_id'],handoff['checks']), ('validate',child,[]))
        self.assertEqual(handoff['source_review']['sources'],wf.fingerprints(store,[output.name]))
        self.assertNotIn(child,store.load()['task_progress'])
        wf.accept_revalidation(store, self.source_review_payload(store, child))
        self.assertEqual(wf.finish(store)['phase'], 'completed')

    def test_finish_keeps_root_coverage_due_after_replacing_checks(self):
        root = self.task('Root contract')
        store = wf.Store(self.location(self.start(root)))
        output = store.source_root / 'output.txt'
        output.write_text('Original output.\n')
        self.complete_unit(store, root, ['source.py',output.name])
        output.write_text('Current output.\n')
        (store.source_root/'source.py').write_text('value = 2\n')
        self.revalidate(store, root)
        first_review = self.source_review_payload(store, root)
        wf.accept_revalidation(store, first_review)
        (store.source_root/'source.py').write_text('value = 3\n')
        self.revalidate(store, root)
        with self.assertRaisesRegex(wf.WorkflowError, 'does not cover'):
            wf.finish(store)
        with self.assertRaisesRegex(wf.WorkflowError, 'review artifact.*match'):
            wf.accept_revalidation(store, first_review)
        handoff = wf.advance(store)
        self.assertEqual((handoff['task_id'],handoff['checks']), (root,[]))
        wf.accept_revalidation(store, self.source_review_payload(store, root))
        self.assertEqual(wf.finish(store)['phase'], 'completed')

    def test_pending_attempt_invalidates_prior_accepted_dependency(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        wf.prepare_check(store, {'task_id':child,'check_id':'behavior'})
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})

    def test_changed_recipe_invalidates_accepted_dependency(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        config = store.source_root/'.skill-tree/config/repository.json'
        config.write_text(json.dumps({'role':'source','schema':1,'recipes':{'static-inspection':{
            'lane':'static','input_paths':[],'assertion_contract':'Changed recipe contract'}}}))
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})

    def test_foreign_receipt_and_missing_check_do_not_establish_current_acceptance(self):
        child, parent, store = self.dependency()
        record = next(o for o in store.outcomes() if o['task_id']==child)
        with store.lock():
            state = store.load()
            state['active_run']['revalidated_checks'] = {child:record['check_results']}
            store.save(store.text(), state)
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})
        with store.lock():
            state = store.load();state['active_run']['revalidated_checks'][child] = []
            store.save(store.text(), state)
        with self.assertRaisesRegex(wf.WorkflowError, 'source integration'):
            wf.begin_task(store, {'task_id':parent})

    def test_execution_stop_remains_binding_after_current_acceptance(self):
        child, parent, store = self.dependency()
        self.revalidate(store, child)
        wf.checkpoint(store, {'phase':'blocked','stop_reason':'Owner decision remains unresolved','next_action':'Wait for the owner decision.'})
        with self.assertRaisesRegex(wf.WorkflowError, 'Run stopped'):
            wf.begin_task(store, {'task_id':parent})

if __name__ == '__main__': unittest.main()
