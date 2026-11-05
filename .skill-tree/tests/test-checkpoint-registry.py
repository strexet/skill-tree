"""Schema-3 validation and intake retain canonical queues and terminal history."""
import importlib.util
import json
from pathlib import Path
import unittest

CORE = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixtures = load('registry_workspace_fixtures', CORE/'tests/test-run-workspaces.py')
validator = load('registry_validator', CORE/'common/scripts/validate-repository-documentation.py')
wf = fixtures.wf


class CheckpointRegistryTests(unittest.TestCase):
    setUp = fixtures.RunWorkspaceTests.setUp
    call = fixtures.RunWorkspaceTests.call
    task = fixtures.RunWorkspaceTests.task
    start = fixtures.RunWorkspaceTests.start
    location = fixtures.RunWorkspaceTests.location
    finish_run = fixtures.RunWorkspaceTests.finish_run

    def metadata(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in (self.root/'.skill-tree').rglob('*') if p.is_file()}

    def test_validation_and_read_only_index_preserve_completed_runs_events_and_pending(self):
        run = self.start(self.task())
        self.finish_run(run)
        before_state = json.loads(self.store.state.read_text())
        history = {key: value for key, value in self.metadata().items()
                   if key.startswith('.skill-tree/history/')}
        pending = wf.intake(wf.Store(self.root), {
            'title': 'Deferred feature request',
            'description': 'Capture the feature without implementation.',
            'expected_behavior': 'Preserve Pending status and terminal history.'})
        state = json.loads(self.store.state.read_text())
        self.assertEqual(state['schema'], 3)
        self.assertIsNone(state['active_run'])
        self.assertEqual(state['run_registry'], before_state['run_registry'])
        self.assertEqual(state['tasks'][0]['id'], pending['id'])
        self.assertEqual(state['tasks'][0]['status'], 'Pending')
        self.assertEqual(history, {key: value for key, value in self.metadata().items()
                                   if key.startswith('.skill-tree/history/')})
        before = self.metadata()
        result = validator.validate_manifest(self.root)
        self.assertTrue(result['ok'], result)
        wf.Store(self.root, allow_unselected=True).load()
        self.assertEqual(before, self.metadata())

    def test_missing_registry_is_rejected_without_checkpoint_reset(self):
        state = json.loads(self.store.state.read_text())
        state.pop('run_registry')
        self.store.state.write_text(wf.dump(state))
        before = self.metadata()
        result = validator.validate_manifest(self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any('requires a run registry' in error for error in result['errors']), result)
        with self.assertRaisesRegex(wf.WorkflowError, 'requires the run registry'):
            self.store.load()
        self.assertEqual(before, self.metadata())

    def test_registry_claim_conflict_is_reported_without_rewriting_history(self):
        run = self.start(self.task())
        self.finish_run(run)
        state = json.loads(self.store.state.read_text())
        state['run_registry']['claims'][wf.identity('T')] = wf.identity('WR')
        self.store.state.write_text(wf.dump(state))
        before = self.metadata()
        result = validator.validate_manifest(self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any('Task claim identity conflict' in error for error in result['errors']), result)
        self.assertEqual(before, self.metadata())


if __name__ == '__main__':
    unittest.main()
