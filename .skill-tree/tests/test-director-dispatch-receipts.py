"""Disposable controls for exact parent and child dispatch receipts."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'common/scripts'
SPEC = importlib.util.spec_from_file_location('director_dispatch_workflow', SCRIPTS / 'workflow-state.py')
WF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WF)
WS = WF.workspaces
DISPATCH = WF.director_dispatch_helper()


class DispatchTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.parent = self.base / 'director'
        self.parent.mkdir()
        self.root, self.queue = self.fixture('queue')
        self.area = {'schema': 1, 'director_id': 'pilot', 'assignment_id': 'lantern',
                     'queue_id': self.queue, 'plan_sha256': '1' * 64}

    def fixture(self, name):
        root = self.base / name
        root.mkdir()
        WS.local_git_text(root, 'init', '-b', 'develop')
        docs = root / '.skill-tree/documents'
        docs.mkdir(parents=True)
        (docs / 'future.md').write_text('# Future Work\n\n## Pending Task Format\n\nParser fixture.\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        conf = root / '.skill-tree/config'
        conf.mkdir()
        (conf / 'repository.json').write_text('{"schema":1,"role":"source"}\n')
        (root / 'source.txt').write_text('Preserve unrelated bytes.\n')
        WS.local_git_text(root, 'add', '.')
        WS.git(root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
               '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture source')
        WS.local_git_text(root, 'remote', 'add', 'origin', str(self.base / 'unused-local-remote.git'))
        return root, WS.setup(WF.Store(root), {})['queue_id']

    def child(self, root=None):
        return WF.Store(root or self.root, neutral=True)

    def pending(self):
        return {'director_dispatch': self.area, 'expected_source_hash': WF.file_hash(self.child().future),
                'title': 'Specify lantern hand carry', 'description': 'Record the selected lantern requirement.',
                'expected_behavior': 'Record the approved acquisition and carry scope.'}

    def process_request(self, pending):
        body = ('Goal:\n- Confirm the required lane.\n\nTouch:\n- source.txt\n\n'
                'Validation:\n```json\n{"checks":[{"id":"contract","recipe_id":"static-inspection",'
                '"criteria":["Confirm the required lane."],"sources":["source.txt"],"parameters":{},'
                '"assertion":"Confirm the required lane.","timing":"immediate"}]}\n```\n\n'
                'Acceptance:\n- Confirm the required lane.\n')
        return {'director_dispatch': self.area, 'expected_source_hash': WF.file_hash(self.child().future),
                'selectors': [pending], 'dispositions': {pending: {'status': 'promoted', 'reason': 'The fixture defines scope.'}},
                'tasks': [{'title': 'Qualify lantern hand carry', 'body': body, 'parent_pending_ids': [pending]}]}

    def task(self):
        pending = WF.intake(self.child(), self.pending())['id']
        return WF.process(self.child(), self.process_request(pending))['created_ids'][0]

    def start_request(self, suffix='lantern'):
        return {'director_dispatch': self.area, 'expected_source_hash': WF.file_hash(self.child().future),
                'local_base': True, 'local_base_authorization': 'Disposable local fixture only.',
                'base_branch': 'develop', 'branch': 'fixture/' + suffix, 'worktree': str(self.base / suffix)}

    def observe(self, operation):
        return DISPATCH.observe(self.child(), {'operation': operation, 'director_dispatch': self.area})

    def test_parent_retains_exact_intent_before_effect_without_writing_child(self):
        parent = WF.Store(self.parent, route_queue=False, neutral=True)
        before = self.child().future.read_bytes()
        request = self.pending()
        origin = DISPATCH.retain_intent(parent, 'intake', request)
        self.assertEqual(self.observe('intake')['status'], 'absent')
        self.assertEqual(self.child().future.read_bytes(), before)
        self.assertEqual(DISPATCH.retain_intent(parent, 'intake', {**request, 'expected_source_hash': '0' * 64}), origin)
        with self.assertRaisesRegex(WF.WorkflowError, 'different semantic request'):
            DISPATCH.retain_intent(parent, 'intake', {**request, 'title': 'Replace original request'})
        child = WF.intake(self.child(), request)
        receipt = self.observe('intake')['receipt']
        self.assertEqual(receipt['semantic_sha256'], origin['semantic_sha256'])
        self.assertEqual(receipt['dispatch_key'], origin['dispatch_key'])
        self.assertEqual(receipt['result']['id'], child['id'])

    def test_explicit_receiver_never_interprets_absent_protocol_as_ordinary_intake(self):
        missing_protocol = {key: value for key, value in self.pending().items() if key != 'director_dispatch'}
        with self.assertRaisesRegex(WF.WorkflowError, 'requires protocol metadata'):
            DISPATCH.apply(self.child(), {'operation': 'intake', 'request': missing_protocol})
        self.assertEqual(self.observe('intake')['status'], 'absent')
        request = {'operation': 'intake', 'request': self.pending()}
        actual = DISPATCH.apply(self.child(), request)
        self.assertEqual(DISPATCH.apply(self.child(), request), actual)

    def test_wrong_owner_and_new_stale_digest_never_write(self):
        other, _ = self.fixture('outside')
        request = self.pending()
        with self.assertRaisesRegex(WF.WorkflowError, 'not the selected canonical child queue'):
            WF.intake(self.child(other), request)
        continuing = {**request, 'expected_source_hash': '0' * 64}
        with self.assertRaisesRegex(WF.WorkflowError, 'Source changed'):
            WF.intake(self.child(), continuing)
        self.assertEqual(self.observe('intake')['status'], 'absent')

    def test_direct_api_rejects_noncanonical_root_even_with_copied_queue(self):
        linked = self.base / 'linked-owner'
        WS.git(self.root, 'worktree', 'add', '-b', 'fixture/linked-owner', linked, 'develop')
        store = WF.Store(linked, route_queue=False, neutral=True)
        before = store.future.read_bytes()
        store.state.write_bytes(self.child().state.read_bytes())
        with self.assertRaisesRegex(WF.WorkflowError, 'exact canonical child root'):
            DISPATCH.apply(store, {'operation': 'intake', 'request': self.pending()})
        self.assertEqual(store.future.read_bytes(), before)
        self.assertEqual(self.observe('intake')['status'], 'absent')

    def test_receipt_probe_parks_when_child_writer_appears_during_read(self):
        request = self.pending()
        WF.intake(self.child(), request)
        before = self.child().future.read_bytes()
        actual_read = DISPATCH._receipt
        marker = self.child().base / '.transaction.json'

        def read_while_writer_begins(*args):
            result = actual_read(*args)
            marker.symlink_to(self.base / 'absent-journal-target')
            return result

        try:
            with patch.object(DISPATCH, '_receipt', side_effect=read_while_writer_begins):
                with self.assertRaisesRegex(WF.WorkflowError, 'requires recovery'):
                    self.observe('intake')
        finally:
            marker.unlink(missing_ok=True)
        self.assertEqual(self.child().future.read_bytes(), before)
        self.assertEqual(self.observe('intake')['status'], 'recorded')

    def test_intake_journal_crash_recovers_original_receipt_and_scope(self):
        request = self.pending()
        old_recover = WF.Store.recover

        def interrupted(store):
            journal = store.base / '.transaction.json'
            if journal.is_file() and DISPATCH.CHILD_RECEIPTS in journal.read_text():
                raise RuntimeError('Lost before first durable child write')
            return old_recover(store)

        with patch.object(WF.Store, 'recover', interrupted), self.assertRaisesRegex(RuntimeError, 'Lost before'):
            WF.intake(self.child(), request)
        with self.assertRaisesRegex(WF.WorkflowError, 'requires recovery'):
            self.observe('intake')
        result = WF.intake(self.child(), request)
        self.assertEqual(WF.intake(self.child(), request), result)
        self.assertEqual(self.observe('intake')['observed_result'], result)
        self.assertEqual(len(self.child().load()['tasks']), 1)

    def test_processing_replay_precedes_missing_pending_and_hooks(self):
        original = WF.intake(self.child(), self.pending())
        request = self.process_request(original['id'])
        old_save = WF.Store.save

        def interrupted(store, *args, **kwargs):
            old_save(store, *args, **kwargs)
            raise RuntimeError('Lost after durable processing')

        with patch.object(WF.Store, 'save', interrupted), self.assertRaisesRegex(RuntimeError, 'Lost after'):
            WF.process(self.child(), request)
        result = self.observe('process')['observed_result']
        self.assertEqual(WF.process(self.child(), request), result)
        self.assertEqual(WF.intake(self.child(), {**self.pending(), 'expected_source_hash': '0' * 64}), original)
        changed = deepcopy(request)
        changed['tasks'][0]['title'] += ' Changed'
        with self.assertRaisesRegex(WF.WorkflowError, 'different semantic request'):
            WF.process(self.child(), changed)
        self.assertEqual(len(self.child().load()['tasks']), 1)

    def test_legacy_batch_without_dispatch_receipt_remains_unclaimed(self):
        request = self.pending() | {'intake_batch_id': 'IB-00000000-0000-4000-8000-000000000001'}
        existing = WF.intake(self.child(), {key: value for key, value in request.items() if key != 'director_dispatch'})
        with self.assertRaisesRegex(WF.WorkflowError, 'review original provenance'):
            WF.intake(self.child(), request)
        self.assertEqual(self.observe('intake')['status'], 'absent')
        self.assertEqual([row['id'] for row in self.child().load()['tasks']], [existing['id']])

    def test_start_reconciles_original_reserved_and_built_workspace(self):
        for fail_after in (False, True):
            with self.subTest(fail_after=fail_after):
                if fail_after:
                    self.root, self.queue = self.fixture('second')
                    self.area['queue_id'] = self.queue
                task = self.task()
                request = self.start_request('created' if fail_after else 'reserved')
                create = WS.create_reserved

                def interrupted(store, run, path):
                    if fail_after:
                        create(store, run, path)
                    raise RuntimeError('Lost workspace acknowledgement')

                with patch.object(WS, 'create_reserved', interrupted), self.assertRaisesRegex(RuntimeError, 'Lost workspace'):
                    WF.start(self.child(), 'next', task, workspace=request)
                observed = self.observe('start')['observed_result']
                self.assertEqual(observed['workspace_state'], 'reserved')
                self.assertEqual(Path(request['worktree']).is_dir(), fail_after)
                self.assertEqual(WF.start(self.child(), 'next', task, workspace=request)['id'], observed['id'])
                self.assertEqual(len(self.child().load()['run_registry']['runs']), 1)
                with self.assertRaisesRegex(WS.RunError, 'original exact worktree path'):
                    WS.recover_workspace(WF.Store(self.root, observed['id']), {'resolution': 'Controlled fixture', 'worktree': str(self.base / 'wrong')})
                ready = WS.recover_workspace(WF.Store(self.root, observed['id']), {'resolution': 'Controlled fixture', 'worktree': request['worktree']})
                self.assertEqual(ready['id'], observed['id'])
                self.assertEqual(self.observe('start')['observed_result']['workspace_state'], 'ready')
                self.assertEqual(WF.start(self.child(), 'next', task, workspace=request)['id'], observed['id'])
                self.assertEqual((self.root / 'source.txt').read_text(), 'Preserve unrelated bytes.\n')


if __name__ == '__main__':
    unittest.main()
