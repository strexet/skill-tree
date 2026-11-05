"""Reviewed semantic decisions drive deterministic intake priority and state guards."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('priority_boundary_fixture', CORE/'tests/test-pending-intake-boundary.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
wf = fixtures.wf


class PendingPriorityTests(unittest.TestCase):
    setUp = fixtures.PendingIntakeBoundaryTests.setUp

    def intake(self, title='Defect report', **extra):
        return wf.intake(self.store, {'title':title, 'description':'Preserve the requested observable behavior.',
            'expected_behavior':'The queue retains exact task identities.',
            'classification':{'kind':'defect','reason':'The owner reports existing behavior failing.'}, **extra})

    def existing(self, queue, priority, status=None):
        prefix = {'Pending Queue':'P', 'Prioritized Next Changes':'T', 'Backlog':'B'}[queue]
        tid = wf.identity(prefix)
        meta = {'id':tid,'priority':priority,'status':status or {'P':'Pending','T':'Ready','B':'Backlog'}[prefix],
            'parent_pending_ids':[wf.identity('P')] if prefix == 'T' else [],
            'processing_run_id':wf.identity('PR') if prefix == 'T' else None,
            'root_task_id':tid if prefix == 'T' else None,
            'related_task_id':None,'relation':'main','depends_on':[]}
        body = 'Description:\n- Preserve the existing task.\n'
        if prefix == 'T':
            criterion = 'Preserve existing work.'
            check = {'id':'existing','recipe_id':'static-inspection','criteria':[criterion],
                'sources':['existing-version.txt'],'parameters':{},'assertion':criterion,'timing':'immediate'}
            body = ('Goal:\n- '+criterion+'\n\nTouch:\n- existing-version.txt\n\nValidation:\n```json\n'
                    +json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- '+criterion+'\n')
            if status == 'Blocked pending answers':
                body += '\nQuestions:\n- [Unresolved - blocks implementation] Confirm the fixture source decision.\n'
        with self.store.lock():
            text = wf.insert(self.store.text(), queue, wf.render('Existing '+tid, meta, body))
            self.store.save(text, self.store.load())
        return tid

    def test_reviewed_semantic_decisions_cover_languages_typos_and_feature_negatives(self):
        cases = json.loads((CORE/'tests/fixtures/pending-intake/classification.json').read_text())
        observed = []
        expected_priorities = []
        for index, case in enumerate(cases):
            before = wf.parse(self.store.text())
            pending = self.intake('Classification case '+str(index), source='`'+case['request']+'`',
                classification={'kind':case['kind'],'reason':'The reviewed request meaning determines the intake category.'})
            expected_priorities.append(max((task['priority'] for task in before), default=100)+1 if case['kind'] == 'defect' else 100)
            observed.append(pending['priority'])
            body = wf.resolve(wf.parse(self.store.text()), [pending['id']])[0]['body']
            self.assertIn(case['request'], body)
        self.assertEqual(observed, expected_priorities)

    def test_empty_open_queue_uses_the_existing_default_baseline_plus_one(self):
        self.assertEqual(self.intake()['priority'], 101)

    def test_open_maximum_includes_all_queues_and_blocked_tasks(self):
        self.existing('Pending Queue', 600)
        self.existing('Prioritized Next Changes', 800, 'Blocked pending answers')
        self.existing('Backlog', 900)
        self.assertEqual(self.intake()['priority'], 901)

    def test_negative_open_priorities_are_not_clamped_to_default_100(self):
        self.existing('Pending Queue', -30)
        self.existing('Backlog', -10)
        self.assertEqual(self.intake()['priority'], -9)

    def test_terminal_history_does_not_supply_open_priority(self):
        history = self.store.base/'history/task-outcomes.jsonl'
        history.parent.mkdir(parents=True)
        history.write_text(json.dumps({'id':wf.identity('O'),'task_id':wf.identity('T'),'disposition':'completed','priority':9999})+'\n')
        self.assertEqual(self.intake()['priority'], 101)

    def test_numeric_owner_priorities_override_defect_and_low_defaults(self):
        for number in [0, -20, 25, 1234]:
            with self.subTest(number=number):
                self.assertEqual(self.intake('Numeric '+str(number), priority=number, low_priority=True)['priority'], number)

    def test_explicit_low_priority_overrides_the_defect_default(self):
        self.existing('Backlog', 900)
        self.assertEqual(self.intake(low_priority=True)['priority'], 25)

    def test_relative_owner_priority_resolves_above_and_below_an_exact_open_id(self):
        anchor = self.existing('Backlog', 50)
        self.existing('Pending Queue', 900)
        observed = [self.intake('Relative '+direction, relative_priority={'direction':direction,'task_id':anchor})['priority']
                    for direction in ['above', 'below']]
        self.assertEqual(observed, [51, 49])

    def test_relative_conflicts_and_missing_anchors_leave_the_queue_unchanged(self):
        anchor = self.existing('Backlog', 50)
        cases = [dict(priority=7, relative_priority={'direction':'above','task_id':anchor}),
                 dict(relative_priority={'direction':'above','task_id':wf.identity('T')}),
                 dict(relative_priority={'direction':'near','task_id':anchor}),
                 dict(relative_priority={'direction':[],'task_id':anchor}), dict(relative_priority=[])]
        for extra in cases:
            before = self.store.future.read_bytes()
            with self.assertRaises(wf.WorkflowError, msg=str(extra)):
                self.intake(**extra)
            self.assertEqual(before, self.store.future.read_bytes())

    def test_invalid_semantic_decisions_fail_before_writing(self):
        for classification in [True, [], {}, {'kind':[],'reason':'Invalid category.'}, {'kind':'unknown','reason':'Invalid category.'}, {'kind':'defect'}, {'kind':'defect','reason':''}]:
            before = self.store.future.read_bytes()
            with self.assertRaises(wf.WorkflowError, msg=str(classification)):
                self.intake(classification=classification)
            self.assertEqual(before, self.store.future.read_bytes())

    def test_ordinary_feature_defaults_and_legacy_payloads_are_unchanged(self):
        self.assertEqual(self.intake('Feature', classification={'kind':'other','reason':'The owner requests a new capability.'})['priority'], 100)
        self.assertEqual(self.intake('Low feature', classification={'kind':'other','reason':'The owner requests a new capability.'}, low_priority=True)['priority'], 25)
        self.assertEqual(wf.intake(self.store, {'title':'Existing caller','description':'Add an export option.','expected_behavior':'Offer the new export format.'})['priority'], 100)

    def test_feature_relationship_defaults_survive_and_defects_take_top_priority(self):
        root = self.existing('Prioritized Next Changes', 150)
        self.assertEqual(self.intake('Feature followup', classification={'kind':'other','reason':'The owner requests an additional capability.'}, relation='followup', root_task_id=root, related_task_id=root)['priority'], 149)
        self.assertEqual(self.intake('Feature blocker', classification={'kind':'other','reason':'Required scoped work.'}, relation='blocker', root_task_id=root, related_task_id=root)['priority'], 151)
        self.assertEqual(self.intake('Defect followup', relation='followup', root_task_id=root, related_task_id=root)['priority'], 152)

    def test_schema_3_registry_and_history_survive_classified_intake(self):
        subprocess.run(['git','init','-b','main',str(self.root)], check=True, capture_output=True)
        wf.workspaces.setup(self.store, {})
        before = self.store.load()['run_registry']
        pending = self.intake()
        state = self.store.load()
        self.assertEqual(pending['priority'], 101)
        self.assertIn('defect: The owner reports existing behavior failing.', self.store.text())
        self.assertEqual(state['run_registry'], before)
        self.assertEqual(state['task_progress'], {})
        self.assertIsNone(state['active_run'])


if __name__ == '__main__':
    unittest.main()
