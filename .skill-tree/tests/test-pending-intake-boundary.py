"""Characterize actual Pending capture independently of instruction interpretation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boundary_workflow', CORE/'common/scripts/workflow-state.py')
wf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wf)

FIGMA_DESCRIPTION = 'Find the corresponding Figma node and inspect the current version.'
FIGMA_EXPECTED = ('Stop and report when the node is absent. When the node is found, '
                  'implement the design and correct the existing version.')


class PendingIntakeBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = self.store.base/'config'
        config.mkdir()
        (config/'repository.json').write_text('{"schema":1,"role":"source"}')
        self.marker = self.root/'existing-version.txt'
        self.marker.write_text('Existing product version.\n')

    def payload(self, title='Conditional Figma request', **extra):
        return {'title':title, 'description':FIGMA_DESCRIPTION,
                'expected_behavior':FIGMA_EXPECTED, **extra}

    def test_imperatives_and_both_conditions_survive_without_implementation(self):
        pending = wf.intake(self.store, self.payload())
        state = self.store.load()
        self.assertEqual([(task['id'], task['status']) for task in state['tasks']], [(pending['id'], 'Pending')])
        self.assertIsNone(state['active_run'])
        self.assertEqual(state['task_progress'], {})
        task = wf.parse(self.store.text())[0]
        self.assertIn(FIGMA_DESCRIPTION, task['body'])
        self.assertIn(FIGMA_EXPECTED, task['body'])
        self.assertEqual(self.marker.read_text(), 'Existing product version.\n')
        self.assertFalse((self.store.base/'history/task-outcomes.jsonl').exists())

    def test_separate_explicit_execution_instruction_is_preserved_but_intake_never_dispatches(self):
        instruction = 'Create Pending, then process and implement the task.'
        pending = wf.intake(self.store, self.payload(source=instruction))
        self.assertIn(instruction, self.store.text())
        self.assertEqual(pending['status'], 'Pending')
        self.assertIsNone(self.store.load()['active_run'])
        self.assertEqual(self.store.load()['task_progress'], {})

    def test_registered_queue_retains_unrelated_work_and_history(self):
        subprocess.run(['git', 'init', '-b', 'main', str(self.root)], check=True, capture_output=True)
        wf.workspaces.setup(self.store, {})
        other = wf.intake(self.store, self.payload('Unrelated pending'))
        history = self.store.base/'history/owner-note.json'
        history.parent.mkdir(parents=True, exist_ok=True)
        history.write_text('{"scope":"retained owner evidence"}\n')
        before_registry = self.store.load()['run_registry']
        before_history = history.read_bytes()
        pending = wf.intake(self.store, self.payload())
        state = self.store.load()
        self.assertEqual(state['schema'], 3)
        self.assertEqual(state['run_registry'], before_registry)
        self.assertEqual(history.read_bytes(), before_history)
        self.assertEqual({task['id'] for task in state['tasks']}, {other['id'], pending['id']})
        self.assertTrue(all(task['status'] == 'Pending' for task in state['tasks']))
        self.assertEqual(state['task_progress'], {})


if __name__ == '__main__':
    unittest.main()
