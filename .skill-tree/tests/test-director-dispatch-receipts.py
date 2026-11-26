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

    def test_full_cycle_partition_is_frozen_in_the_canonical_intake_receipt(self):
        child = self.child()
        original = self.pending()
        template = {key: original[key] for key in ('title', 'description', 'expected_behavior')}
        items = [
            {**template, 'key':'follow-up', 'title':'Check the deferred fixture', 'priority':300, 'topic':'later-work'},
            {**template, 'key':'primary', 'title':'Change the selected fixture', 'priority':125, 'topic':'main-work'},
            {**template, 'key':'handoff', 'title':'Record the deferred handoff', 'priority':250,
             'topic':'later-work', 'pending_depends_on':['@primary']},
        ]
        partition = {'primary':['primary'], 'deferred':['follow-up','handoff']}
        request = {'director_dispatch':self.area, 'expected_source_hash':original['expected_source_hash'],
                   'intake_batch_id':WF.identity('IB'), 'items':items, 'full_cycle_partition':partition}
        before = child.future.read_bytes(), child.state.read_bytes()
        for invalid in ({'primary':['primary']}, {'primary':['primary'], 'deferred':['primary','follow-up','handoff']},
                        {'primary':['foreign'], 'deferred':['follow-up','handoff']},
                        {'primary':['primary'], 'deferred':['handoff','follow-up']}):
            with self.subTest(partition=invalid):
                with self.assertRaisesRegex(WF.WorkflowError, 'Full Cycle'):
                    WF.intake(self.child(), {**request,'full_cycle_partition':invalid})
                self.assertEqual((child.future.read_bytes(), child.state.read_bytes()), before)
        converted = [items[0], {**items[1], 'pending_depends_on':['@follow-up']}, items[2]]
        with self.assertRaisesRegex(WF.WorkflowError, 'cannot require a deferred intake'):
            WF.intake(self.child(), {**request,'items':converted})
        self.assertEqual((child.future.read_bytes(), child.state.read_bytes()), before)
        saved = WF.Store.save

        def interrupted(store, *args, **kwargs):
            saved(store, *args, **kwargs)
            raise RuntimeError('Lost after durable partitioned intake')

        with patch.object(WF.Store, 'save', interrupted), self.assertRaisesRegex(RuntimeError, 'Lost after'):
            WF.intake(self.child(), request)
        observed = self.observe('intake')
        receipt = observed['observed_result']
        follow_up, primary, handoff = (item['id'] for item in receipt['items'])
        self.assertEqual(receipt['full_cycle_partition'], {'primary':[primary], 'deferred':[follow_up,handoff]})
        before = child.future.read_bytes(), child.state.read_bytes()
        self.assertEqual(WF.intake(self.child(),request), receipt)
        with self.assertRaisesRegex(WF.WorkflowError, 'different semantic request'):
            WF.intake(self.child(), {key:value for key,value in request.items() if key != 'full_cycle_partition'})
        self.assertEqual((child.future.read_bytes(), child.state.read_bytes()), before)
        unbound = self.process_request(primary)
        with self.assertRaisesRegex(WF.WorkflowError, 'Original canonical intake batch receipt'):
            WF.process(self.child(), unbound)
        companion=self.root/DISPATCH.CHILD_RECEIPTS/(observed['receipt']['dispatch_key']+'.json')
        companion_bytes=companion.read_bytes()
        companion.unlink()
        try:
            self.assertEqual(WF.read_intake_receipt(self.child(),receipt['id']),receipt)
            for member in (primary,follow_up):
                with self.assertRaisesRegex(WF.WorkflowError,'exact Director partition authority'):
                    WF.process(self.child(),self.process_request(member))
            self.assertEqual((child.future.read_bytes(),child.state.read_bytes()),before)
        finally:
            companion.write_bytes(companion_bytes)
        guarded = {'director_batch_intake_sha256':observed['receipt']['receipt_sha256']}
        with self.assertRaisesRegex(WF.WorkflowError, 'selection differs'):
            WF.process(self.child(), {**self.process_request(follow_up), **guarded})
        self.assertEqual((child.future.read_bytes(), child.state.read_bytes()), before)
        done = WF.process(self.child(), {**unbound, **guarded})
        self.assertEqual(done['selected_ids'],[primary])
        self.assertEqual(WF.process(self.child(), {**unbound, **guarded}), done)
        tasks = {item['id']:item for item in self.child().load()['tasks']}
        self.assertEqual([(tasks[pid]['status'],tasks[pid]['priority'],tasks[pid]['topic'])
                          for pid in (follow_up,handoff)],
                         [('Pending',300,'later-work'),('Pending',250,'later-work')])
        self.assertEqual(tasks[handoff]['pending_depends_on'],[primary])
        independent=self.process_request(follow_up)
        independent.pop('director_dispatch')
        independent['tasks'][0]['title']='Qualify the separately selected follow-up'
        self.assertEqual(WF.process(self.child(),independent)['selected_ids'],[follow_up])

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
                marker = WS.linked_registration(self.root, Path(request['worktree']))/'skill-tree-owner.json'
                self.assertEqual(json.loads(marker.read_bytes()), ready['workspace']['cleanup_owner'])
                self.assertEqual(ready['workspace']['cleanup_owner']['token'], observed['workspace']['dispatch_owner_token'])
                self.assertEqual(self.observe('start')['observed_result']['workspace_state'], 'ready')
                self.assertEqual(WF.start(self.child(), 'next', task, workspace=request)['id'], observed['id'])
                self.assertEqual((self.root / 'source.txt').read_text(), 'Preserve unrelated bytes.\n')

    def test_interruption_after_git_before_marker_does_not_claim_existing_work(self):
        task = self.task()
        request = self.start_request()
        path = Path(request['worktree'])
        with patch.object(WS, 'directed_owner', side_effect=RuntimeError('Lost before marker')):
            with self.assertRaisesRegex(RuntimeError, 'Lost before marker'):
                WF.start(self.child(), 'next', task, workspace=request)
        marker = WS.linked_registration(self.root, path)/'skill-tree-owner.json'
        state = self.child().load()['run_registry']
        rid = next(iter(state['runs']))
        frozen = self.child().state.read_bytes()
        (path/'keep.txt').write_text('Local work')
        for contents in (None, '{"token": "different"}'):
            with self.subTest(contents=contents):
                if contents is not None:
                    marker.write_text(contents)
                with self.assertRaisesRegex(WS.RunError, 'ownership marker'):
                    self.observe('start')
                with self.assertRaisesRegex(WS.RunError, 'ownership marker'):
                    WS.recover_workspace(WF.Store(self.root, rid), {'resolution': 'Investigate interrupted Git add'})
                self.assertEqual(self.child().state.read_bytes(), frozen)
                self.assertEqual(marker.read_text() if marker.exists() else None, contents)
                self.assertEqual((path/'keep.txt').read_text(), 'Local work')

    def test_ready_directed_checkout_recreation_keeps_original_owner_and_refuses_conflicts(self):
        WS.git(self.root, 'config', 'worktree.useRelativePaths', 'true')
        task = self.task()
        request = self.start_request()
        run = WF.start(self.child(), 'next', task, workspace=request)
        path = Path(request['worktree'])
        marker = WS.linked_registration(self.root, path)/'skill-tree-owner.json'
        owner = run['workspace']['cleanup_owner']
        frozen = self.child().state.read_bytes()
        marker.unlink()
        for tamper in ('absent', 'changed', 'symlink'):
            with self.subTest(tamper=tamper):
                if tamper == 'changed':
                    marker.write_text(json.dumps(owner | {'token': 'other'}))
                if tamper == 'symlink':
                    marker.unlink()
                    target = self.base/'foreign-marker'
                    target.write_text(json.dumps(owner))
                    marker.symlink_to(target)
                with self.assertRaisesRegex(WF.WorkflowError, 'Original Director run reservation'):
                    self.observe('start')
                with self.assertRaisesRegex(WS.RunError, 'ownership marker'):
                    WS.recover_workspace(WF.Store(self.root, run['id']), {'resolution': 'Verify existing registration'})
                self.assertEqual(frozen, self.child().state.read_bytes())
                if tamper == 'absent':
                    self.assertFalse(marker.exists())
                elif tamper == 'changed':
                    self.assertEqual(json.loads(marker.read_bytes())['token'], 'other')
                else:
                    self.assertTrue(marker.is_symlink())
        with self.assertRaisesRegex(WS.RunError, 'original exact worktree path'):
            WS.recover_workspace(WF.Store(self.root, run['id']), {'worktree': str(self.base/'other'), 'resolution': 'Recover'})
        WS.git(self.root, 'worktree', 'remove', path)
        recovered = WS.recover_workspace(WF.Store(self.root, run['id']), {'resolution': 'Recreate the removed clean checkout'})
        self.assertEqual(recovered['workspace']['cleanup_owner'], owner)
        self.assertEqual(json.loads(marker.read_bytes()), owner)
        self.assertEqual(self.observe('start')['observed_result']['id'], run['id'])

    def test_already_ready_legacy_reservations_keep_their_original_ownership_checks(self):
        task = self.task()
        request = self.start_request()
        run = WF.start(self.child(), 'next', task, workspace=request)
        child = self.child()
        registry = json.loads(child.state.read_bytes())
        current = registry['run_registry']['runs'][run['id']]['workspace']
        owner = current.pop('cleanup_owner')
        child.state.write_text(WF.dump(registry))
        with self.assertRaisesRegex(WF.WorkflowError, 'Original Director run reservation'):
            self.observe('start')

        # Reproduce serialized reservations from before tokens were frozen at start.
        receipt_path = next(path for path in (self.root/DISPATCH.CHILD_RECEIPTS).glob('*.json')
                            if json.loads(path.read_bytes())['identity']['operation'] == 'start')
        receipt = json.loads(receipt_path.read_bytes())
        receipt['result']['workspace'].pop('dispatch_owner_token')
        receipt.pop('receipt_sha256')
        receipt['receipt_sha256'] = DISPATCH._digest(receipt)
        receipt_path.write_text(WF.dump(receipt))
        current.pop('dispatch_owner_token')
        current['cleanup_owner'] = owner
        child.state.write_text(WF.dump(registry))
        self.assertEqual(self.observe('start')['observed_result']['workspace']['cleanup_owner'], owner)

        marker = WS.linked_registration(self.root, Path(request['worktree']))/'skill-tree-owner.json'
        marker.unlink()
        with self.assertRaisesRegex(WF.WorkflowError, 'Original Director run reservation'):
            self.observe('start')
        current.pop('cleanup_owner')
        child.state.write_text(WF.dump(registry))
        self.assertEqual(self.observe('start')['observed_result']['workspace_state'], 'ready')
        recovered = WS.recover_workspace(WF.Store(self.root, run['id']), {'resolution': 'Verify legacy workspace'})
        self.assertNotIn('cleanup_owner', recovered['workspace'])
        self.assertFalse(marker.exists())
        self.assertEqual(WF.start(self.child(), 'next', task, workspace=request)['id'], run['id'])


if __name__ == '__main__':
    unittest.main()
