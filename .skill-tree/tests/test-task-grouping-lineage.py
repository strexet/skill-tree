"""Regression coverage for grouped provenance and portable intake receipts."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('lineage_fixtures', Path(__file__).with_name('test-workflow-state.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
wf = fixtures.wf


class GroupingLineageTests(unittest.TestCase):
    setUp = fixtures.WorkflowStateTests.setUp
    pending = fixtures.WorkflowStateTests.pending
    body = fixtures.WorkflowStateTests.body
    complete = fixtures.WorkflowStateTests.complete

    def grouped(self, title, topic='director'):
        return self.pending(title, topic=topic, intake_batch_id=wf.identity('IB'),
                            expected_source_hash=wf.file_hash(self.store.future))

    def process(self, parents, *specs):
        ids = [parent['id'] for parent in parents]
        return wf.process(self.store, {'selectors': ids, 'dispositions': {
            identity: {'status': 'promoted', 'reason': 'Research confirms the outcome.'} for identity in ids},
            'tasks': [{'parent_pending_ids': ids, 'body': self.body(), **item} for item in specs]})

    def test_split_merge_reuse_and_completion_preserve_lineage(self):
        a, b = self.grouped('First origin'), self.grouped('Second origin')
        legacy = self.pending('Legacy origin')
        result = self.process([a], {'title': 'First unit'}, {'title': 'Second unit'})
        first, second = wf.resolve(wf.parse(self.store.text()), result['created_ids'])
        for task in [first, second]:
            self.assertEqual(wf.grouping_fields(task), wf.grouping_fields(a))
        self.process([b, legacy], {'reuse_id': first['id']})
        merged = wf.resolve(wf.parse(self.store.text()), [first['id']])[0]
        self.assertEqual(merged['parent_pending_ids'], [a['id'], b['id'], legacy['id']])
        self.assertEqual(merged['topic'], 'director')
        self.assertEqual(merged['intake_batch_ids'], a['intake_batch_ids'] + b['intake_batch_ids'])
        self.assertEqual(wf.grouping_fields(self.complete(merged)), wf.grouping_fields(merged))
        remaining = self.process([self.pending('Unclassified origin')], {'title': 'Unclassified task'})
        self.assertEqual(wf.grouping_fields(wf.resolve(wf.parse(self.store.text()), remaining['created_ids'])[0]), {})

    def test_conflicting_topics_or_supplied_lineage_do_not_mutate(self):
        a, b = self.grouped('First topic'), self.grouped('Another topic', 'tooling')
        before = self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError, 'topic'):
            self.process([a, b], {'title': 'Conflicting result'})
        with self.assertRaisesRegex(wf.WorkflowError, 'origins'):
            self.process([a], {'title': 'Invented topic', 'topic': 'tooling'})
        self.assertEqual(self.store.future.read_bytes(), before)

    def test_portable_receipt_replay_is_guarded_and_idempotent(self):
        run_id, queue_id = wf.identity('WR'), wf.identity('Q')
        origin = self.grouped('Portable origin')
        task = wf.resolve(wf.parse(self.store.text()), [origin['id']])[0]
        batch_id = origin['intake_batch_ids'][0]
        receipt = wf.read_intake_receipt(self.store, batch_id)
        receipt_path = self.store.owned(wf.intake_receipt_path(batch_id))
        receipt_path.unlink()
        with patch.object(wf.workspaces, 'runtime', return_value={'worktrees': {run_id: self.root}}):
            with patch.object(self.store, 'load', return_value={'active_run': None, 'task_progress': {}, 'run_registry': {'queue_id': queue_id, 'runs': {}}}):
                event = {'id': wf.identity('E'), 'queue_id': queue_id, 'run_id': run_id,
                         'changes': [{'task_id': task['id'], 'before': None,
                                      'after': {'queue': task['queue'], 'body': task['body']}}],
                         'outcomes': [], 'checkpoint_before': None, 'checkpoint_after': None,
                         'intake_receipts': [receipt]}
                payload = {'schema': 1, 'queue_id': queue_id, 'run_id': run_id, 'events': [event]}
                def persist(text, state, writes):
                    self.store.commit(writes)
                with patch.object(self.store, 'save', side_effect=persist):
                    wf.replay_events(self.store, payload)
                    self.assertEqual(wf.read_intake_receipt(self.store, batch_id), receipt)
                    wf.replay_events(self.store, payload)
                    conflict = {**receipt, 'request_sha256': '0' * 64}
                    event['intake_receipts'] = [conflict]
                    with self.assertRaisesRegex(wf.WorkflowError, 'receipt conflict'):
                        wf.replay_events(self.store, payload)
                    event['id'] = wf.identity('E')
                    with self.assertRaisesRegex(wf.WorkflowError, 'receipt conflict'):
                        wf.replay_events(self.store, payload)
                    self.assertEqual(wf.read_intake_receipt(self.store, batch_id), receipt)


if __name__ == '__main__':
    unittest.main()
