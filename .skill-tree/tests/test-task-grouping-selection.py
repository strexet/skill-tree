import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('group_selection_workflow', CORE/'common/scripts/workflow-state.py')
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)


class TaskGroupingSelectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text(
            '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n'
            '## Prioritized Next Changes\n\n## Backlog\n'
        )

    def item(self, title, **metadata):
        return {
            'title': title,
            'description': 'Capture grouped fixture work.',
            'expected_behavior': 'Keep selection scoped.',
            **metadata,
        }

    def batch(self, *items):
        return wf.intake(self.store, {
            'items': list(items),
            'intake_batch_id': wf.identity('IB'),
            'expected_source_hash': wf.file_hash(self.store.future),
        })

    def payload(self, preview):
        criterion = 'Keep the exact selection.'
        check = {
            'id': 'scope',
            'recipe_id': 'static-inspection',
            'criteria': [criterion],
            'sources': ['.skill-tree/documents/future.md'],
            'parameters': {},
            'assertion': criterion,
            'timing': 'immediate',
        }
        body = (
            'Goal:\n- Preserve the original selection.\n\n'
            'Touch:\n- The selected fixture.\n\n'
            'Validation:\n```json\n'+json.dumps({'checks': [check]})+'\n```\n\n'
            'Acceptance:\n- '+criterion
        )
        return {
            'selectors': preview['ids'],
            'expected_source_hash': preview['source_hash'],
            'dispositions': {
                tid: {'status': 'promoted', 'reason': 'The fixture is ready for promotion.'}
                for tid in preview['ids']
            },
            'tasks': [
                {
                    'title': task['title'],
                    'body': body,
                    'parent_pending_ids': [task['id']],
                }
                for task in preview['tasks']
            ],
        }

    def snapshot(self):
        return {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob('*') if path.is_file()
        }

    def test_explicit_batch_union_and_topic_intersection_keep_document_order(self):
        earlier = self.batch(
            self.item('First director task', topic='director', priority=110),
            self.item('Related topic', topic='director-review', priority=120),
        )
        later = self.batch(
            self.item('Later director task', topic='director', priority=110),
            self.item('Ungrouped topic in the batch', priority=100),
        )
        omitted = self.batch(self.item('Adjacent director task', topic='director', priority=130))
        legacy = wf.intake(self.store, self.item('Legacy task', priority=140))
        first, related = [task['id'] for task in earlier['items']]
        second, no_topic = [task['id'] for task in later['items']]
        adjacent = omitted['items'][0]['id']
        before = self.snapshot()

        selection = {'queue': 'pending', 'intake_batch_ids': [earlier['id'], later['id']]}
        union = wf.group_selection(self.store, selection)
        self.assertEqual(union['ids'], [related, second, first, no_topic])
        self.assertEqual([task['id'] for task in union['tasks']], union['ids'])
        self.assertEqual(union['source_hash'], wf.file_hash(self.store.future))
        self.assertEqual(union['outside_dependencies'], [])
        self.assertEqual(wf.group_selection(self.store, {**selection, 'topic': 'director'})['ids'], [second, first])
        self.assertEqual(wf.group_selection(self.store, {'queue': 'pending', 'topic': 'director'})['ids'],
                         [adjacent, second, first])
        self.assertEqual(wf.resolve(wf.parse(self.store.text()), [legacy['id']])[0]['id'], legacy['id'])
        self.assertEqual(self.snapshot(), before)

    def test_invalid_or_empty_group_does_not_fall_back_to_the_queue(self):
        known = self.batch(self.item('Selected director task', topic='director'))
        wf.intake(self.store, self.item('Unrelated legacy task'))
        batch = known['id']
        bad_selections = [
            {},
            {'topic': 'director', 'queue': 'backlog'},
            {'topic': 'Director'},
            {'topic': None},
            {'topic': 'director-re'},
            {'intake_batch_ids': []},
            {'intake_batch_ids': batch},
            {'intake_batch_ids': [batch, batch]},
            {'intake_batch_ids': [known['items'][0]['id']]},
            {'intake_batch_ids': [batch, wf.identity('IB')]},
            {'topic': 'unrelated', 'intake_batch_ids': [batch]},
        ]
        before = self.snapshot()
        for query in bad_selections:
            with self.subTest(query=query), self.assertRaises(wf.WorkflowError):
                wf.group_selection(self.store, {'queue': 'pending', **query})
        self.assertEqual(self.snapshot(), before)

    def test_processing_requires_current_preview_and_promotes_only_the_exact_selection(self):
        batch = self.batch(self.item('First director task', topic='director'))
        selection = {'queue': 'pending', 'topic': 'director', 'intake_batch_ids': [batch['id']]}
        original = wf.group_selection(self.store, selection)
        later = self.batch(self.item('Later director task', topic='director'))
        legacy = wf.intake(self.store, self.item('Unrelated legacy task'))
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'Source changed'):
            wf.process(self.store, self.payload(original))
        with self.assertRaisesRegex(wf.WorkflowError, 'Resolve group filters'):
            wf.process(self.store, {'topic': 'director', 'dispositions': {}, 'tasks': []})
        self.assertEqual(self.snapshot(), before)

        refreshed = wf.group_selection(self.store, selection)
        self.assertEqual(refreshed['ids'], original['ids'])
        result = wf.process(self.store, self.payload(refreshed))
        self.assertEqual(result['selected_ids'], original['ids'])
        pending = wf.resolve(wf.parse(self.store.text()), [], 'Pending Queue')
        self.assertEqual({task['id'] for task in pending}, {later['items'][0]['id'], legacy['id']})
        prioritized = wf.group_selection(self.store, {**selection, 'queue': 'prioritized'})
        self.assertEqual(prioritized['ids'], result['created_ids'])
        with self.assertRaises(wf.WorkflowError):
            wf.group_selection(self.store, selection)

    def test_batch_preview_rejects_unrelated_header_with_real_batch_id(self):
        original = self.batch(self.item('Recorded task'))
        unrelated = wf.intake(self.store, self.item('Other work'))
        text = wf.rewrite_meta(self.store.text(), unrelated['id'], {'intake_batch_ids': [original['id']]})
        self.store.future.write_text(text)
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'original Pending provenance'):
            wf.group_selection(self.store, {'queue': 'pending', 'intake_batch_ids': [original['id']]})
        self.assertEqual(self.snapshot(), before)

    def test_recent_cli_lists_only_recorded_batches_by_utc_time(self):
        older = '2026-11-01T12:00:00+00:00'
        newer = '2026-11-02T12:00:00+00:00'
        with patch.object(wf, 'now', return_value=newer):
            latest = self.batch(self.item('Latest fixture', topic='director'))
        with patch.object(wf, 'now', return_value=older):
            first = self.batch(self.item('First recorded fixture', topic='director'))
        wf.intake(self.store, self.item('Legacy unbatched fixture'))
        query = self.root/'group-query.json'
        query.write_text(json.dumps({'limit': 2}))
        before = self.snapshot()
        command = ['python3', '-B', str(CORE/'common/scripts/workflow-state.py')]
        result = subprocess.run(
            [*command, 'recent-batches', str(self.root), '--input', str(query)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout), [
            {'id': latest['id'], 'created_at': newer, 'pending_ids': [latest['items'][0]['id']]},
            {'id': first['id'], 'created_at': older, 'pending_ids': [first['items'][0]['id']]},
        ])
        self.assertEqual(self.snapshot(), before)

        query.write_text(json.dumps({'queue': 'pending', 'intake_batch_ids': [latest['id']]}))
        before = self.snapshot()
        result = subprocess.run(
            [*command, 'group-selection', str(self.root), '--input', str(query)],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(json.loads(result.stdout)['ids'], [latest['items'][0]['id']])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
