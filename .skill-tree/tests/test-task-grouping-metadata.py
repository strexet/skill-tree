import importlib.util
from pathlib import Path
import unittest

source = Path(__file__).resolve().parents[2]
module = source / '.skill-tree/common/scripts/workflow-state.py'
spec = importlib.util.spec_from_file_location('source_grouping_baseline', module)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)

class GroupingContract(unittest.TestCase):
    def test_legacy_and_grouped_pending_coexist(self):
        header = {
            'id': 'P-42682dba-9032-4d04-9949-67a88063c8d3',
            'priority': 101, 'status': 'Pending', 'parent_pending_ids': [],
            'processing_run_id': None, 'root_task_id': None, 'related_task_id': None,
            'relation': 'main', 'depends_on': [],
        }
        second = {**header, 'id':'P-50e1dcc9-0f78-4b20-8325-3ac71590cf53'}
        prefix = '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n'
        legacy = workflow.render('Legacy work', header, 'Description:\n- Preserve legacy intake.')
        grouped = workflow.render('Grouped work', second, 'Description:\n- Preserve grouped intake.')
        grouped = grouped.replace('depends_on: []', 'depends_on: []\ntopic: director\nintake_batch_ids: ["IB-1c402db8-e8bc-4c77-8587-51b0277cf1c7"]')
        tasks = workflow.parse(prefix+legacy+grouped+'## Prioritized Next Changes\n\n## Backlog\n')
        self.assertNotIn('topic', tasks[0])
        self.assertEqual(tasks[1]['topic'], 'director')
        self.assertEqual(tasks[1]['intake_batch_ids'], ['IB-1c402db8-e8bc-4c77-8587-51b0277cf1c7'])

    def test_roundtrip_and_metadata_neutral_fingerprints(self):
        queue = '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n'
        suffix = '## Prioritized Next Changes\n\n## Backlog\n'
        meta = dict(id=workflow.identity('P'), priority=100, status='Pending',
                    parent_pending_ids=[], processing_run_id=None, root_task_id=None,
                    related_task_id=None, relation='main', depends_on=[])
        legacy = queue + workflow.render('Legacy', meta, 'Description:\n- Preserve existing work.') + suffix
        before = workflow.parse(legacy)[0]
        grouped = workflow.rewrite_meta(legacy, meta['id'], {
            'topic': 'null', 'intake_batch_ids': [workflow.identity('IB')],
        })
        after = workflow.parse(grouped)[0]
        self.assertEqual(after['topic'], 'null')
        self.assertEqual(workflow.index(grouped)[0]['intake_batch_ids'], after['intake_batch_ids'])
        self.assertEqual(workflow.clarification_semantics(before), workflow.clarification_semantics(after))
        old_validation = [('metadata', {'validation_group_id': None, 'boundary_validation': None})]
        self.assertEqual(workflow.clarification_semantics(before)['validation'],
                         workflow.digest(workflow.dump(old_validation).encode()))

    def test_invalid_grouping_values(self):
        meta = dict(id=workflow.identity('P'), priority=100, status='Pending',
                    parent_pending_ids=[], processing_run_id=None, root_task_id=None,
                    related_task_id=None, relation='main', depends_on=[])
        batch = workflow.identity('IB')
        for fields in ({'topic': None}, {'topic': 'Director'}, {'topic': '3d'},
                       {'intake_batch_ids': []}, {'intake_batch_ids': [batch, batch]},
                       {'intake_batch_ids': [batch, workflow.identity('IB')]},
                       {'intake_batch_ids': [workflow.identity('P')]}, {'intake_batch_ids': [None]}):
            with self.subTest(fields=fields), self.assertRaises(workflow.WorkflowError):
                workflow.validate_metadata({**meta, **fields}, 'Pending Queue')


if __name__=='__main__':
    unittest.main()
