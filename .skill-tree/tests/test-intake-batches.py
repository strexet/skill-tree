"""Regression checks for atomic intake and replay receipts."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('intake_fixtures', Path(__file__).with_name('test-pending-intake-boundary.py'))
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
wf = fixtures.wf


class IntakeBatchTests(unittest.TestCase):
    setUp = fixtures.PendingIntakeBoundaryTests.setUp

    def batch(self, *titles):
        return {
            'items': [{'title': title, 'description': 'Capture scoped work.',
                       'expected_behavior': 'Preserve the intake receipt.', 'topic': 'director'}
                      for title in titles],
            'intake_batch_id': wf.identity('IB'),
            'expected_source_hash': wf.file_hash(self.store.future),
        }

    def test_replay_after_sources_leave_pending(self):
        payload = self.batch('First intake', 'Second intake')
        original = wf.intake(self.store, payload)
        ids = [entry['id'] for entry in original['items']]
        self.assertEqual(len(set(ids)), 2)
        self.assertTrue(original['created_at'].endswith('+00:00'))
        wf.process(self.store, {'selectors': ids, 'dispositions': {
            item: {'status': 'resolved', 'reason': 'Existing source resolves the fixture.'} for item in ids}})
        before = self.store.future.read_bytes()
        self.assertEqual(wf.intake(self.store, payload), original)
        self.assertEqual(self.store.future.read_bytes(), before)
        with self.assertRaisesRegex(wf.WorkflowError, 'different request'):
            wf.intake(self.store, {**payload, 'items': payload['items'][:1]})
        self.assertEqual(self.store.future.read_bytes(), before)

    def test_grouped_intake_stops_before_writing_to_a_legacy_owned_queue(self):
        payload = self.batch('Compatible generation required')
        profile = self.store.owned('.skill-tree/installation/profile.json')
        profile.parent.mkdir()
        profile.write_text(wf.dump({'project_root': str(self.store.root)}))
        before = self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError, 'compatible owned canonical installation'):
            wf.intake(self.store, payload)
        self.assertEqual(self.store.future.read_bytes(), before)
        self.assertFalse(self.store.owned(wf.intake_receipt_path(payload['intake_batch_id'])).exists())

    def test_invalid_later_item_does_not_write_earlier_items(self):
        payload = self.batch('Repeated', 'Repeated')
        before = self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError, 'duplicate'):
            wf.intake(self.store, payload)
        self.assertEqual(self.store.future.read_bytes(), before)
        self.assertFalse(self.store.owned(wf.intake_receipt_path(payload['intake_batch_id'])).exists())

    def test_missing_ack_recovers_navigation_without_duplicate_tasks(self):
        payload = self.batch('Recoverable work')
        commit = self.store.commit

        def interrupted(writes):
            if set(writes) == {'.skill-tree/skill-tree.json'}:
                raise OSError('Simulated lost acknowledgement before navigation')
            return commit(writes)

        with patch.object(self.store, 'commit', side_effect=interrupted):
            with self.assertRaises(OSError):
                wf.intake(self.store, payload)
        replayed = wf.intake(self.store, payload)
        self.assertEqual([task['id'] for task in self.store.load()['tasks']],
                         [replayed['items'][0]['id']])
        self.assertTrue((self.store.base / 'skill-tree.json').is_file())

    def test_single_result_shape_and_distinct_batch_ids(self):
        first = self.batch('Single work')
        item = dict(first['items'][0], intake_batch_id=first['intake_batch_id'],
                    expected_source_hash=first['expected_source_hash'])
        actual = wf.intake(self.store, item)
        self.assertEqual(actual['intake_batch_ids'], [first['intake_batch_id']])
        self.assertEqual(wf.intake(self.store, item), actual)
        next_payload = self.batch('Adjacent work')
        self.assertNotEqual(wf.intake(self.store, next_payload)['id'], first['intake_batch_id'])


if __name__ == '__main__':
    unittest.main()
