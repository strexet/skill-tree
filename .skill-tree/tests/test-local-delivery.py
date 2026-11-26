"""Resumable, verified local Git delivery fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import unittest
from unittest.mock import patch

CORE = next(parent for parent in Path(__file__).resolve().parents if parent.name == '.skill-tree')
spec = importlib.util.spec_from_file_location('existing_workspace_fixture', CORE / 'tests/test-run-workspaces.py')
workspace_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace_fixture)
wf = workspace_fixture.wf
ws = workspace_fixture.ws
fixture = workspace_fixture.RunWorkspaceTests
fixture_set_up = fixture.setUp
GENERATION = '.skill-tree/src/delivery-fixture-generation.txt'
OWNED_FILE = '.agents/skills/skill-tree-implement-all/SKILL.md'


class LocalDeliveryTests(unittest.TestCase):
    # Reuse real controller intake, check, completion and Git setup without
    # inheriting unrelated unittest methods.
    def setUp(self):
        fixture_set_up(self)
        self.git(self.root, 'config', 'commit.gpgSign', 'false')
        self.git(self.root, 'config', 'merge.verifySignatures', 'false')

    call = fixture.call
    task = fixture.task
    start = fixture.start
    location = fixture.location

    def git(self, root, *args):
        return self.call(root, *args)

    def accept_source(self, task_id):
        criterion = 'Preserve scoped source behavior.'
        store = self.selected
        wf.begin_task(store, {'task_id': task_id})
        (self.source / 'report.json').write_text('{"assertion":"scoped fixture passed"}')
        attempt = wf.prepare_check(store, {'task_id': task_id, 'check_id': 'behavior'})
        wf.record_check(store, {
            'task_id': task_id,
            'check_id': 'behavior',
            'attempt_id': attempt['attempt_id'],
            'result': 'pass',
            'classification': 'executed-control',
            'actual_lane': 'static',
            'environment_identity': attempt['environment_identity'],
            'assertions': [{'assertion': criterion, 'result': 'pass'}],
            'cleanup': 'The fixture starts no product process.',
            'evidence': ['report.json'],
        })
        wf.mark_implemented(store, {'task_id': task_id})
        wf.complete(store, {
            'task_id': task_id,
            'outcome': 'Scoped source behavior remains intact.',
            'acceptance': [{'criterion': criterion, 'result': 'pass', 'evidence': ['report.json']}],
            'source_fingerprints': wf.fingerprints(store, ['source.py']),
        })

    def run_local(self, *, retain=False, real_installer=False, incoming=None, owned_dirty=False, baseline_target=False, finish=True):
        if real_installer or owned_dirty:
            self.copy_source_generation()
        if owned_dirty:
            placeholder = self.root / OWNED_FILE
            placeholder.parent.mkdir(parents=True)
            placeholder.write_text('old tracked snapshot\n')
            self.git(self.root, 'add', '-f', OWNED_FILE)
            self.git(self.root, 'commit', '-m', 'Fixture tracks old owned package bytes')
            shutil.rmtree(placeholder.parent)
            self.install_target()

        if baseline_target:
            self.install_target()
        retained = None
        if retain:
            retained_task = self.task('Retained task')
            self.git(self.root, 'add', '.skill-tree/documents/future.md')
            self.git(self.root, 'commit', '-m', 'Fixture retained canonical queue baseline')
            retained = self.start(retained_task, base_branch='main', local_base=True,
                                  local_base_authorization='Synthetic retained fixture local main base.')
            retained_store = wf.Store(self.location(retained))
            if ws.initial_profile_pending(retained):
                wf.prepare_worktree_profile(retained_store)
            wf.checkpoint(retained_store, {'phase': 'blocked', 'stop_reason': 'Independent retained prerequisite'})
            # Exercise retention of stopped run content and working copy.
            (self.location(retained) / 'source.py').write_text('value = 9\n')
        task_id = self.task('Deliver selected implementation')
        self.run = self.start(
            task_id,
            base_branch='main',
            local_base=True,
            local_base_authorization='Synthetic fixture authorizes the exact local main base.',
            delivery_authorization={
                'pr': False,
                'merge': True,
                'mode': 'local-merge',
                'target_branch': 'main',
                'owner_instruction': 'Synthetic fixture authorizes a local merge into main.'
            },
        )
        self.source = self.location(self.run)
        self.selected = wf.Store(self.source, self.run['id'])
        if owned_dirty:
            shutil.rmtree((self.source / OWNED_FILE).parent)
        if ws.initial_profile_pending(self.run):
            wf.prepare_worktree_profile(self.selected)
        (self.source / 'source.py').write_text('value = 2\n')
        if real_installer:
            (self.source / GENERATION).write_text('merged generation\n')
        for relative, content in (incoming or {}).items():
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
        self.accept_source(task_id)
        self.git(self.source, 'add', 'source.py', 'report.json',
                 *([GENERATION] if real_installer else []), *(incoming or ()))
        self.git(self.source, 'commit', '-m', 'Fixture accepted source')
        # Generated fixture records stay visible to workflow-state while Git
        # sees a clean working copy when the preparation contract requires it.
        # Future is tracked and committed separately only if the fixture changed
        # its exact whitespace after completing the selected task.
        exclude = self.root / '.git/info/exclude'
        with exclude.open('a') as stream:
            stream.write('\n/.skill-tree/documents/future.json\n/.skill-tree/skill-tree.json\n/.skill-tree/history/\n/.skill-tree/installation/\n/.agents/\n')
        self.retained = retained
        self.implementation = wf.finish(self.selected) if finish else None
        return self.implementation

    def start_reviewed_controller(self, mode, *, merges=False, remote=False, deps=False, partial_recipe=False):
        launch=self.base/'launch'
        self.git(self.root,'worktree','add',launch,'release/example')
        (launch/'local-tip.txt').write_text('local-only start branch commit\n')
        self.git(launch,'add','local-tip.txt')
        self.git(launch,'commit','-m','Unpushed launch tip')
        if partial_recipe:
            config = launch/'.skill-tree/config/repository.json'
            data = json.loads(config.read_text())
            data['recipes'] = {'static-inspection':{'lane':'unit','argv':['python3','test_partial.py'],
                                                    'input_paths':['test_partial.py']}}
            config.write_text(json.dumps(data))
            (launch/'test_partial.py').write_text(
                'import unittest\nfrom pathlib import Path\nclass TestCandidate(unittest.TestCase):\n'
                '    def test_expected_source(self):\n'
                '        self.assertIn("value = 1", Path("source.py").read_text())\n'
                'unittest.main()\n')
            self.git(launch,'add','.skill-tree/config/repository.json','test_partial.py')
            self.git(launch,'commit','-m','Declare a runnable check for partial delivery')
        self.start_head=self.git(launch,'rev-parse','HEAD')
        self.launch=launch
        self.remote_before=self.git(self.remote,'show-ref')
        self.dependency=self.task('Required source unit') if deps else None
        self.tid=self.task('Selected local delivery',deps=[self.dependency] if deps else [])
        operation='implement-all' if mode=='all' else 'work-through-next'
        order={'implementation_operation':operation}
        if merges:
            order['delivery_authorization']={'pr':False,'merge':True,'target_branch':'release/example',
                'owner_instruction':'Merge after this local review.'}
        if remote:
            order['delivery_authorization']={'pr':True,'merge':True,'target_branch':'develop'}
        self.run=wf.start(wf.Store(launch,allow_unselected=True,neutral=True),mode,
            self.tid if mode=='next' else None,workspace=order)
        self.source=self.location(self.run)
        self.selected=wf.Store(self.source,self.run['id'])
        return self.run

    def accept_scoped_source(self,task_id, *, commit_evidence=False, relative=None, extra=None):
        criterion='Preserve scoped source behavior.'
        store=self.selected
        wf.begin_task(store,{'task_id':task_id})
        relative=relative or ('consumer.py' if self.dependency and task_id==self.tid else 'source.py')
        path=self.source/relative
        baseline=path.read_text() if path.exists() else ''
        path.write_text((extra or {}).get(relative,baseline+'# '+task_id+'\n'))
        for name,content in (extra or {}).items():(self.source/name).write_text(content)
        (self.source/'report.json').write_text('{}')
        paths = list(dict.fromkeys([relative,*(extra or {}),*(['report.json'] if commit_evidence else [])]))
        info=wf.mark_implemented(store,{'task_id':task_id,'changed_files':paths})
        attempt=wf.prepare_check(store,{'task_id':task_id,'check_id':'behavior'})
        lane=attempt['recipe']['lane']
        wf.record_check(store,{'task_id':task_id,'check_id':'behavior','attempt_id':attempt['attempt_id'],
            'result':'pass','classification':'executed-control','actual_lane':lane,
            'environment_identity':attempt['environment_identity'],
            'assertions':[{'assertion':criterion,'result':'pass'}],
            **({'counts':{'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0}} if lane=='unit' else {}),
            'cleanup':'No product process was launched.','evidence':['report.json']})
        task_review=wf.identity('DO')
        expected=info['git_review_identity']
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'b'*64}) as check:
            result=wf.complete(store,{'task_id':task_id,'review_id':task_review,
                'outcome':'Accepted scoped fixture source.','source_fingerprints':wf.fingerprints(store,['source.py',relative]),
                'acceptance':[{'criterion':criterion,'result':'pass','evidence':['report.json']}]})
        check.assert_called_once_with(store,task_review,expected,{'kind':'task','task_ids':[task_id]})
        return result

    def finish_reviewed_fixture(self):
        wf.advance(self.selected)
        preview=wf.controller_review_identity(self.selected)
        review_id=wf.identity('DO')
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}) as check:
            result=wf.finish(self.selected,{'review_id':review_id})
        expected=(self.selected,review_id,preview['identity'],
            {'kind':'controller','run_id':self.run['id'],'task_ids':self.run['admitted_task_ids']})
        self.assertEqual(check.call_args_list,[unittest.mock.call(*expected)]*
            (2 if self.run['reviewed_local_delivery']['merge_at_finish'] else 1))
        return result

    def test_cleanup_removes_only_owned_clean_worktree_and_preserves_evidence(self):
        self.start_reviewed_controller('all')
        outcome = self.accept_scoped_source(self.tid, commit_evidence=True)
        result = self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'], 'merged')
        self.assertEqual(result['delivery']['worktree_cleanup']['status'], 'removed')
        self.assertFalse(self.source.exists())
        self.assertTrue(self.launch.is_dir())
        self.assertEqual(self.git(self.root, 'rev-parse', self.run['workspace']['branch']), outcome['commits'][0])
        history, = wf.history(wf.Store(self.root), self.tid)
        self.assertTrue(history['acceptance'][0]['evidence'][0]['available'])
        retry = wf.cleanup_controller_worktree(wf.Store(self.root, self.run['id']))
        self.assertEqual(retry, result['delivery']['worktree_cleanup'])

    def test_cleanup_accepts_verified_same_owner_git_move(self):
        self.start_reviewed_controller('all')
        outcome = self.accept_scoped_source(self.tid,commit_evidence=True)
        original_owner = self.run['workspace']['cleanup_owner']
        self.git(self.root,'worktree','lock',self.source)
        closed = self.finish_reviewed_fixture()
        self.assertEqual(closed['delivery']['worktree_cleanup']['status'],'deferred')
        self.git(self.root,'worktree','unlock',self.source)
        moved = self.base/'verified-worktree-move'
        self.git(self.root,'worktree','move',self.source,moved)
        canonical = wf.Store(self.root,self.run['id'])
        request = {'worktree':str(moved),'resolution':'Verify the same native Git worktree relocation.'}
        save = canonical.save

        def persist_and_change_branch(*args, **kwargs):
            save(*args, **kwargs)
            self.git(moved,'switch','-c','fixture-conflicting-branch')

        with patch.object(canonical,'save',side_effect=persist_and_change_branch):
            with self.assertRaisesRegex(ws.RunError,'branch changed before locator activation'):
                ws.recover_workspace(canonical,request)
        self.git(moved,'switch',self.run['workspace']['branch'])
        with self.assertRaisesRegex(ws.RunError,'exact recorded relocation destination'):
            ws.recover_workspace(canonical,{'resolution':'Fixture retry without the moved directory.'})
        with patch.object(ws,'activate_worktree_locator',side_effect=OSError('Fixture interruption before activation')):
            with self.assertRaisesRegex(OSError,'before activation'):
                ws.recover_workspace(canonical,request)
        self.assertEqual(ws.runtime(self.root)['worktrees'][self.run['id']],str(self.source))
        queue_id = ws.runtime(self.root)['queue_id']
        projection = wf.Store(self.root,route_queue=False,allow_unselected=True,neutral=True)
        ws.recover_locator(projection,{'queue_id':queue_id,'worktrees':{}})
        self.assertEqual(ws.runtime(self.root)['worktrees'][self.run['id']],str(self.source))
        with self.assertRaisesRegex(ws.RunError,'previous locator'):
            ws.recover_locator(projection,{'queue_id':queue_id,'worktrees':{self.run['id']:str(moved)}})
        ws.runtime_file(self.root).unlink()
        with self.assertRaisesRegex(ws.RunError,'previous locator'):
            ws.recover_locator(projection,{'queue_id':queue_id,'worktrees':{self.run['id']:str(moved)}})
        ws.recover_locator(projection,{'queue_id':queue_id,'worktrees':{self.run['id']:str(self.source)}})
        pending = canonical.load()['active_run']['workspace_recoveries']
        self.assertEqual(len(pending),1)
        held = wf.cleanup_controller_worktree(wf.Store(self.root,self.run['id']))
        self.assertEqual(held['status'],'deferred')
        moved_run = ws.recover_workspace(canonical,request)
        self.assertEqual(moved_run['workspace_recoveries'],pending)
        self.assertEqual(ws.recover_workspace(canonical,request)['workspace_recoveries'],pending)
        dirty = moved/'retained-local.txt'
        dirty.write_text('Preserve local work at the moved location.')
        held = wf.cleanup_controller_worktree(wf.Store(self.root,self.run['id']))
        self.assertEqual(held['status'],'deferred')
        self.assertEqual(dirty.read_text(),'Preserve local work at the moved location.')
        dirty.unlink()
        cleanup = wf.cleanup_controller_worktree(wf.Store(self.root,self.run['id']))
        if cleanup['status'] != 'removed':
            self.fail('Verified same-owner move was deferred')
        self.assertEqual(moved_run['workspace']['cleanup_owner'],original_owner)
        self.assertEqual(moved_run['workspace_recoveries'][-1]['kind'],'verified-worktree-move')
        self.assertFalse(self.source.exists())
        self.assertFalse(moved.exists())
        self.assertEqual(self.git(self.root,'rev-parse',self.run['workspace']['branch']),outcome['commits'][0])

    def test_cleanup_acknowledges_verified_external_removal_without_deleting_files(self):
        self.start_reviewed_controller('all')
        outcome = self.accept_scoped_source(self.tid,commit_evidence=True)
        self.git(self.root,'worktree','lock',self.source)
        closed = self.finish_reviewed_fixture()
        self.assertEqual(closed['delivery']['worktree_cleanup']['status'],'deferred')
        self.git(self.root,'worktree','unlock',self.source)
        run_id = self.run['id']
        evidence = {'external_removal':{'worktree':str(self.source),
                    'reference':'Fixture observed an ordinary external Git worktree removal.'}}
        live = wf.cleanup_controller_worktree(wf.Store(self.root,run_id),evidence)
        self.assertEqual(live['status'],'deferred')
        self.assertTrue(self.source.is_dir())
        self.git(self.root,'worktree','remove',self.source)
        without = wf.cleanup_controller_worktree(wf.Store(self.root,run_id))
        self.assertEqual(without['status'],'deferred')
        ref = 'refs/heads/'+self.run['workspace']['branch']
        head = outcome['commits'][0]
        base = self.run['workspace']['base_commit']
        self.git(self.root,'update-ref',ref,base,head)
        stale = wf.cleanup_controller_worktree(wf.Store(self.root,run_id),evidence)
        self.assertEqual(stale['status'],'deferred')
        self.git(self.root,'update-ref',ref,head,base)
        with patch.object(ws,'remove_controller_worktree',side_effect=AssertionError('Unexpected deletion')):
            observed = wf.cleanup_controller_worktree(wf.Store(self.root,run_id),evidence)
        self.assertEqual(observed['status'],'removed')
        self.assertEqual(observed['removal'],'external')
        self.assertEqual(wf.cleanup_controller_worktree(wf.Store(self.root,run_id),evidence),observed)
        self.assertFalse(self.source.exists())


    def test_cleanup_holds_a_locator_rebound_without_verified_relocation(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid,commit_evidence=True)
        self.git(self.root,'worktree','lock',self.source)
        self.finish_reviewed_fixture()
        self.git(self.root,'worktree','unlock',self.source)
        moved = self.base/'unproved-rebound-worktree'
        self.git(self.root,'worktree','move',self.source,moved)
        registry = ws.runtime(self.root)
        run_id = self.run['id']
        projection = wf.Store(self.root,route_queue=False,allow_unselected=True,neutral=True)
        ws.recover_locator(projection,{'queue_id':registry['queue_id'],'worktrees':{run_id:str(moved)}})
        with patch.object(ws,'remove_controller_worktree',side_effect=AssertionError('Unexpected deletion')):
            held = wf.cleanup_controller_worktree(wf.Store(self.root,run_id))
        self.assertEqual(held['status'],'deferred')
        self.assertIn('verified worktree relocation',held['reason'])
        self.assertTrue(moved.is_dir())
        scoped = wf.Store(self.root,run_id)
        request = {'worktree':str(moved),'resolution':'Verify the actual prior native worktree.',
                   'previous_worktree':str(self.source)}
        with self.assertRaisesRegex(ws.RunError,'previous worktree differs'):
            ws.recover_workspace(scoped,{**request,'previous_worktree':str(self.base/'another-checkout')})
        verified = ws.recover_workspace(scoped,request)['workspace_recoveries']
        replay = ws.recover_workspace(scoped,request)['workspace_recoveries']
        self.assertEqual(replay,verified)
        self.assertEqual(wf.cleanup_controller_worktree(wf.Store(self.root,run_id))['status'],'removed')

    def test_cleanup_origin_pins_interrupted_ordinary_reservation(self):
        requested = {}

        def interrupt(store,run,path):
            requested.update(run_id=run['id'],path=path)
            raise OSError('Fixture interruption before Git worktree creation')

        with patch.object(ws,'create_reserved',side_effect=interrupt):
            with self.assertRaisesRegex(OSError,'before Git worktree creation'):
                self.start_reviewed_controller('all')
        run_id, original = requested['run_id'], requested['path']
        wrong = self.base/'unapproved-reserved-path'
        selected = wf.Store(self.root,run_id)
        local = ws.runtime(self.root)
        locator = ws.runtime_file(self.root)
        before = locator.read_bytes()
        with self.assertRaisesRegex(ws.RunError,'original exact reserved worktree path'):
            ws.recover_workspace(selected,{'worktree':str(wrong),'resolution':'Fixture wrong path.'})
        projection = wf.Store(self.root,route_queue=False,allow_unselected=True,neutral=True)
        with self.assertRaisesRegex(ws.RunError,'original exact reserved worktree path'):
            ws.recover_locator(projection,{'queue_id':local['queue_id'],'worktrees':{run_id:str(wrong)}})
        self.assertEqual(locator.read_bytes(),before)
        self.assertFalse(wrong.exists())
        continued = ws.recover_workspace(selected,{'worktree':str(original),'resolution':'Restore exact reservation.'})
        self.assertEqual(continued['workspace_state'],'ready')
        self.assertTrue(original.is_dir())

    def test_cleanup_defers_for_ignored_data_and_reconciles_a_lost_removal_response(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        exclude = Path(self.git(self.root, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
        with exclude.open('a') as rules:
            rules.write('\nlocal-recovery.dat\n')
        protected = self.source / 'local-recovery.dat'
        protected.write_text('private fixture')
        result = self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'], 'merged')
        self.assertEqual(result['delivery']['worktree_cleanup']['status'], 'deferred')
        self.assertEqual(protected.read_text(), 'private fixture')
        protected.unlink()
        run_store = wf.Store(self.root, self.run['id'])
        remove = ws.remove_controller_worktree

        def lose_response(root, path):
            remove(root, path)
            self.source.mkdir()
            (self.source/'new-owner.dat').write_text('New content at the old path')
            raise subprocess.TimeoutExpired('git worktree remove', 45)

        with patch.object(ws, 'remove_controller_worktree', side_effect=lose_response):
            first = wf.cleanup_controller_worktree(run_store)
        self.assertTrue((self.source/'new-owner.dat').is_file())
        self.assertEqual(first['status'], 'deferred')
        retry = wf.cleanup_controller_worktree(run_store)
        self.assertEqual(retry['status'], 'removed')
        self.assertEqual(retry['attempt'], first['attempt'])
        self.assertTrue((self.source/'new-owner.dat').is_file())
        self.assertEqual(run_store.load()['active_run']['delivery']['status'], 'merged')

    def test_cleanup_preserves_files_created_after_preparation(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        exclude = Path(self.git(self.root, 'rev-parse', '--path-format=absolute', '--git-path', 'info/exclude'))
        with exclude.open('a') as rules:
            rules.write('\nraced.dat\n')
        stage = ws.stage_controller_worktree

        def add_ignored_file(root, path, attempt):
            (path/'raced.dat').write_text('Local evidence created after preflight')
            return stage(root, path, attempt)

        with patch.object(ws, 'stage_controller_worktree', side_effect=add_ignored_file):
            result = self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['worktree_cleanup']['status'], 'deferred')
        self.assertEqual((self.source/'raced.dat').read_text(), 'Local evidence created after preflight')

    def test_cleanup_defers_when_the_target_changes_during_preparation(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        stage = ws.stage_controller_worktree

        def move_target(root, path, attempt):
            self.git(root, 'update-ref', 'refs/heads/release/example', self.start_head)
            return stage(root, path, attempt)

        with patch.object(ws, 'stage_controller_worktree', side_effect=move_target):
            result = self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'], 'merged')
        self.assertEqual(result['delivery']['worktree_cleanup']['status'], 'deferred')
        self.assertIn('current target', result['delivery']['worktree_cleanup']['reason'])
        self.assertTrue(self.source.is_dir())

    def test_cleanup_retains_locked_worktree_until_exact_retry(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        self.git(self.root, 'worktree', 'lock', self.source)
        result = self.finish_reviewed_fixture()
        self.assertIn('locked', result['delivery']['worktree_cleanup']['reason'])
        self.assertTrue(self.source.is_dir())
        self.git(self.root, 'worktree', 'unlock', self.source)
        self.assertEqual(wf.cleanup_controller_worktree(wf.Store(self.root, self.run['id']))['status'], 'removed')

    def test_cleanup_detects_timestamp_preserving_local_modifications(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        self.git(self.root, 'config', 'core.trustctime', 'false')
        path = self.source/'local-tip.txt'
        current = path.stat()
        os.utime(path, ns=(current.st_atime_ns, current.st_mtime_ns - 2_000_000_000))
        self.git(self.source, 'update-index', '--really-refresh')
        original = path.stat()
        modified = b'x' * original.st_size
        path.write_bytes(modified)
        os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
        self.assertEqual(self.git(self.source, 'status', '--porcelain'), '')
        result = self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['worktree_cleanup']['status'], 'deferred')
        self.assertEqual(path.read_bytes(), modified)

    def test_cleanup_retains_worktree_git_configuration_and_references(self):
        self.start_reviewed_controller('all')
        self.accept_scoped_source(self.tid, commit_evidence=True)
        self.git(self.root, 'config', 'extensions.worktreeConfig', 'true')
        self.git(self.source, 'config', '--worktree', 'user.name', 'Local fixture name')
        self.git(self.source, 'update-ref', 'refs/worktree/recovery', 'HEAD')
        result = self.finish_reviewed_fixture()
        self.assertIn('local Git configuration', result['delivery']['worktree_cleanup']['reason'])
        self.git(self.source, 'config', '--worktree', '--unset', 'user.name')
        retry = wf.cleanup_controller_worktree(wf.Store(self.root, self.run['id']))
        self.assertIn('private Git references', retry['reason'])
        self.assertTrue(self.source.is_dir())

    def test_policy_work_through_next_reviews_then_merges_on_exact_later_request(self):
        self.start_reviewed_controller('next')
        self.assertEqual(self.run['workspace']['base_commit'],self.start_head)
        self.assertEqual(self.run['workspace']['base_branch'],'release/example')
        self.assertEqual(self.git(self.root,'branch','--show-current'),'main')
        task=self.accept_scoped_source(self.tid)
        self.assertEqual(len(task['commits']),1)
        result=self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'],'review-ready')
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),self.start_head)
        self.assertTrue(ws.delivery_finished(result))
        own=self.launch/'target-dirt.txt'
        own.write_text('staged target work\n')
        self.git(self.launch,'add','target-dirt.txt')
        own.write_text('unstaged target work\n')
        before=self.git(self.launch,'diff','--cached','--','target-dirt.txt')
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            merged=wf.merge_reviewed_controller(self.selected,{'owner_instruction':'Merge the reviewed run locally.'})
        self.assertEqual(merged['delivery']['status'],'merged')
        self.assertEqual(self.git(self.launch,'show','-s','--format=%P','HEAD').split(),
            [self.start_head,task['commits'][0]])
        self.assertEqual(self.git(self.launch,'diff','--cached','--','target-dirt.txt'),before)
        self.assertEqual(own.read_text(),'unstaged target work\n')
        self.assertEqual(self.git(self.remote,'show-ref'),self.remote_before)

    def test_policy_implement_all_merges_only_the_reviewed_scope_by_default(self):
        self.start_reviewed_controller('all',deps=True)
        first=self.accept_scoped_source(self.dependency)
        accepted=self.accept_scoped_source(self.tid)
        result=self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'],'merged')
        self.assertEqual(self.git(self.launch,'show','-s','--format=%P','HEAD').split(),
            [self.start_head,accepted['commits'][0]])
        self.assertEqual(self.git(self.source,'rev-parse','HEAD^'),first['commits'][0])
        self.assertEqual(self.git(self.remote,'show-ref'),self.remote_before)

    def test_policy_reviewed_merge_repairs_owned_index_after_lost_acknowledgement(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        self.git(self.source,'rm','local-tip.txt')
        self.git(self.source,'commit','-m','Reviewed removal')
        self.finish_reviewed_fixture()
        index=ws.task_index_path(self.launch)
        original=ws.os.replace
        def fail_index_move(source, target):
            if Path(target)==index:
                raise OSError('Fixture lost target index acknowledgement')
            return original(source,target)
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            with patch.object(ws.os,'replace',side_effect=fail_index_move):
                with self.assertRaisesRegex(OSError,'lost target index'):
                    wf.merge_reviewed_controller(self.selected,{'owner_instruction':'Merge the reviewed run locally.'})
        merged_head=self.git(self.launch,'rev-parse','HEAD')
        self.assertNotEqual(merged_head,self.start_head)
        self.assertIn('source.py',self.git(self.launch,'status','--porcelain'))
        (self.launch/'added-after-merge.txt').write_text('Keep the staged user changes.\n')
        self.git(self.launch,'add','added-after-merge.txt')
        later=self.source/'source.py'
        later.write_text('Independent new source work.\n')
        result=wf.merge_reviewed_controller(self.selected)
        self.assertEqual(later.read_text(),'Independent new source work.\n')
        self.assertEqual(result['delivery']['reviewed_merge']['commit'],merged_head)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),merged_head)
        self.assertEqual(self.git(self.launch,'diff','--cached','--name-only'),'added-after-merge.txt')
        self.assertEqual(self.git(self.launch,'diff','--name-only','--','source.py'),'')
        self.assertFalse((self.launch/'local-tip.txt').exists())

    def test_policy_late_merge_rejects_changed_review_and_moved_target(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        self.finish_reviewed_fixture()
        order={'owner_instruction':'Merge the reviewed run locally.'}
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'c'*64}):
            with self.assertRaisesRegex(wf.WorkflowError,'review acceptance changed'):
                wf.merge_reviewed_controller(self.selected,order)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),self.start_head)
        self.git(self.launch,'commit','--allow-empty','-m','Target advanced')
        advanced=self.git(self.launch,'rev-parse','HEAD')
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            with self.assertRaisesRegex(ws.RunError,'target moved'):
                wf.merge_reviewed_controller(self.selected,order)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        self.assertEqual(self.selected.load()['active_run']['delivery']['status'],'review-ready')

    def prepare_two_current_target_sources(self, *, relative_runner=False):
        output='.skill-tree/skills/general/skill-tree-fixture/references/plugin-bindings.json'
        self.launch=self.base/'launch'
        self.git(self.root,'worktree','add',self.launch,'release/example')
        config=self.launch/'.skill-tree/config/repository.json'
        command = ['python3','test_combined.py']
        inputs = ['test_combined.py', output]
        if relative_runner:
            runner = self.launch/'run-combined'
            runner.write_text('#!/bin/sh\nexec python3 "$@"\n')
            runner.chmod(0o755)
            command[0] = './run-combined'
            inputs.append('run-combined')
        config.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'combined-unit':{'lane':'unit','argv':command,'input_paths':inputs}}}))
        (self.launch/'peer.py').write_text('peer = 1\n')
        (self.launch/output).parent.mkdir(parents=True)
        (self.launch/output).write_text('value = 1\npeer = 1\n')
        composer=self.launch/'.skill-tree/bin/compose.js';composer.parent.mkdir()
        composer.write_text("const fs = require('node:fs');\n"
            f"process.stdout.write(JSON.stringify({{{json.dumps(output.removeprefix('.skill-tree/'))}: "
            "fs.readFileSync('source.py', 'utf8') + fs.readFileSync('peer.py', 'utf8')}));\n")
        (self.launch/'test_combined.py').write_text('import os\nimport unittest\nfrom pathlib import Path\n'
            'class Fixture(unittest.TestCase):\n    def test_combined(self):\n'
            '        self.assertNotEqual(os.getenv("SKILL_TREE_TEST_MODE"), "fail")\n'
            f'        self.assertEqual(Path({output!r}).read_text(), "value = 2\\npeer = 3\\n")\n'
            'if __name__ == "__main__" and os.getenv("SKILL_TREE_TEST_MODE") != "no-discovery":\n    unittest.main()\n')
        self.git(self.launch,'add','.');self.git(self.launch,'commit','-m','Both scoped plans share this baseline')
        self.start_head=self.git(self.launch,'rev-parse','HEAD')
        self.remote_before=self.git(self.remote,'show-ref');self.dependency=None
        ids=[self.task('First scoped candidate'),self.task('Second scoped candidate',touch='peer.py')]
        self.store.future.write_text(self.store.text().replace('static-inspection','combined-unit'))
        states=[]
        for tid,changed,contents in zip(ids,('source.py','peer.py'),('value = 2\n','peer = 3\n')):
            self.tid=tid
            self.run=wf.start(wf.Store(self.launch,allow_unselected=True,neutral=True),'next',tid,
                              workspace={'implementation_operation':'work-through-next'})
            self.source=self.location(self.run);self.selected=wf.Store(self.source,self.run['id'])
            self.accept_scoped_source(tid,relative=changed,extra={changed:contents,output:'worker '+str(tid)+'\n'})
            result=self.finish_reviewed_fixture()
            states.append((self.tid,self.run,self.source,self.selected,result['delivery']['reviewed_source']))
        first,second=states
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            first_merge=wf.merge_reviewed_controller(first[3],{'owner_instruction':'Merge the first verified fixture result.'})
        self.tid,self.run,self.source,self.selected,reviewed=second
        return output,first_merge['delivery']['reviewed_merge']['commit'],reviewed

    def current_target(self,action,**payload):
        return wf.current_target_delivery(self.selected,'current-target-'+action,{'integrator_id':'fixture-integrator',**payload})

    def test_current_target_rebuilds_generated_conflict_runs_both_checks_and_reconciles_lost_ack(self):
        output,advanced,original=self.prepare_two_current_target_sources(relative_runner=True)
        original_receipt=self.store.owned(wf._delivery_receipt_path(self.run));frozen=original_receipt.read_bytes()
        owner='Merge the second fixture on top of the first fixture result.'
        attempt=self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced)
        self.assertEqual(attempt['generated_conflicts'],[output]);self.assertEqual(attempt['conflicting_paths'],[])
        self.assertEqual(self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced,generated_paths=[output]),attempt)
        aid=attempt['id'];area=Path(attempt['worktree'])
        original_outputs=wf.current_target_outputs
        def interrupted_regeneration(*args):
            original_outputs(*args)
            raise OSError('Fixture interrupted package regeneration')
        with patch.object(wf,'current_target_outputs',side_effect=interrupted_regeneration):
            with self.assertRaisesRegex(OSError,'interrupted package regeneration'):
                self.current_target('seal',attempt_id=aid)
        authored=area/'source.py';authored_bytes=authored.read_bytes();authored.write_text('Unrelated fixture change.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'unrelated changes'):
            self.current_target('seal',attempt_id=aid)
        authored.write_bytes(authored_bytes)
        sealed=self.current_target('seal',attempt_id=aid)
        self.assertEqual((area/output).read_text(),'value = 2\npeer = 3\n')
        self.assertEqual(len(sealed['required_check_ids']),2)
        review_id=wf.identity('DO')
        with self.assertRaisesRegex(wf.WorkflowError,'Fresh executed current-target evidence'):
            self.current_target('merge',attempt_id=aid,review_id=review_id)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        for mode in ('no-discovery','fail'):
            with patch.dict(os.environ,{'SKILL_TREE_TEST_MODE':mode}):
                failed=self.current_target('checks',attempt_id=aid)
                self.assertEqual(failed['status'],'sealed')
                self.assertTrue(all(not row['qualified'] for row in failed['checks'].values()))
                with self.assertRaisesRegex(wf.WorkflowError,'Fresh executed current-target evidence'):
                    self.current_target('merge',attempt_id=aid,review_id=review_id)
                self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        original_subprocess=subprocess.run
        def independent_writer(argv,*args,**kwargs):
            if list(argv)[-1:]==['test_combined.py']:
                with wf.Store(self.root,allow_unselected=True,neutral=True).lock():
                    self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
            return original_subprocess(argv,*args,**kwargs)
        with patch.object(wf.subprocess,'run',side_effect=independent_writer):
            checked=self.current_target('checks',attempt_id=aid)
        self.assertEqual(checked['status'],'checked')
        self.assertTrue(all(row['inputs']['executable']==str(area/'run-combined') for row in checked['checks'].values()))
        evidence=self.store.owned(next(iter(checked['checks'].values()))['artifact']['path']);saved=evidence.read_bytes()
        evidence.write_text('arbitrary result reference')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence is missing, failed or changed'):
            self.current_target('merge',attempt_id=aid,review_id=review_id)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        evidence.write_bytes(saved)
        original_merge=ws.run_local_merge
        def lost_ack(*args,**kwargs):
            original_merge(*args,**kwargs)
            raise OSError('Fixture lost merge acknowledgement')
        review={'orchestration_hash':'f'*64,'plan':{'required_checks':sealed['required_check_ids']},
                'checks':{'results':[{'id':cid,'status':'passed','reference':check['review_reference']}
                                    for cid,check in checked['checks'].items()]}}
        wrong=wf.deepcopy(review);wrong['checks']['results'][0]['reference']='Unrelated passing output.'
        with patch.object(wf,'verified_implementation_review',return_value=wrong):
            with self.assertRaisesRegex(wf.WorkflowError,'every exact executed check receipt'):
                self.current_target('merge',attempt_id=aid,review_id=review_id)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        with patch.object(wf,'verified_implementation_review',return_value=review) as verify:
            with patch.object(ws,'run_local_merge',side_effect=lost_ack):
                with self.assertRaisesRegex(OSError,'lost merge acknowledgement'):
                    self.current_target('merge',attempt_id=aid,review_id=review_id)
            args=verify.call_args.args
            self.assertEqual(args[0].source_root,area)
            self.assertEqual(args[1:],(review_id,sealed['identity'],sealed['review_scope']))
        self.git(self.launch,'commit','--allow-empty','-m','Advance the target after the applied review')
        later=self.git(self.launch,'rev-parse','HEAD')
        (self.launch/'peer.py').write_text('Local modification after the later commit.\n')
        self.git(self.launch,'add','peer.py')
        staged=self.git(self.launch,'diff','--cached')
        merged=self.current_target('merge',attempt_id=aid,review_id=review_id)
        self.assertEqual(merged['merge']['parents'],[advanced,original['source']['source_head']])
        self.assertEqual(merged['merge']['commit'],sealed['identity']['head'])
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),later)
        self.assertEqual(self.git(self.launch,'diff','--cached'),staged)
        self.assertEqual(self.current_target('merge',attempt_id=aid,review_id=review_id)['merge'],merged['merge'])
        self.assertEqual(original_receipt.read_bytes(),frozen)
        self.assertEqual(self.git(self.remote,'show-ref'),self.remote_before)

    def test_current_target_rejects_apply_time_ref_movement_then_allows_new_candidate(self):
        _,advanced,_=self.prepare_two_current_target_sources()
        owner='Integrate the exact fixture against the current local branch.'
        attempt=self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced)
        aid=attempt['id'];sealed=self.current_target('seal',attempt_id=aid)
        checked=self.current_target('checks',attempt_id=aid)
        original_transaction=ws.local_ref_transaction
        moved=self.git(self.launch,'commit-tree',advanced+'^{tree}','-p',advanced,'-m','Concurrent ref advancement')
        def move_before_cas(*args):
            self.git(self.source,'update-ref',attempt['target_ref'],moved,advanced)
            return original_transaction(*args)
        review={'orchestration_hash':'f'*64,'plan':{'required_checks':sealed['required_check_ids']},
                'checks':{'results':[{'id':cid,'status':'passed','reference':check['review_reference']}
                                    for cid,check in checked['checks'].items()]}}
        with patch.object(wf,'verified_implementation_review',return_value=review):
            with patch.object(ws,'local_ref_transaction',side_effect=move_before_cas):
                with self.assertRaisesRegex(ws.LocalRefRejected,'exact local source or target ref'):
                    self.current_target('merge',attempt_id=aid,review_id=wf.identity('DO'))
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),moved)
        self.assertEqual((self.launch/'peer.py').read_text(),'peer = 1\n')
        stale=self.selected.load()['active_run']['delivery']['current_target_attempts'][aid]
        self.assertEqual(stale['status'],'stale')
        replacement=self.current_target('prepare',owner_instruction=owner,expected_target_head=moved)
        self.assertNotEqual(replacement['id'],aid)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),moved)

    def test_current_target_retires_interrupted_attempt_excluded_by_advanced_target(self):
        _,advanced,_=self.prepare_two_current_target_sources()
        owner='Integrate the exact fixture against the current local branch.'
        attempt=self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced)
        aid=attempt['id'];sealed=self.current_target('seal',attempt_id=aid)
        checked=self.current_target('checks',attempt_id=aid)
        review={'orchestration_hash':'f'*64,'plan':{'required_checks':sealed['required_check_ids']},
                'checks':{'results':[{'id':cid,'status':'passed','reference':check['review_reference']}
                                    for cid,check in checked['checks'].items()]}}
        review_id=wf.identity('DO')
        with patch.object(wf,'verified_implementation_review',return_value=review):
            with patch.object(ws,'run_local_merge',side_effect=OSError('Interrupted before applying')):
                with self.assertRaisesRegex(OSError,'Interrupted before applying'):
                    self.current_target('merge',attempt_id=aid,review_id=review_id)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        self.git(self.launch,'commit','--allow-empty','-m','Advance without the candidate')
        later=self.git(self.launch,'rev-parse','HEAD')
        with self.assertRaisesRegex(wf.WorkflowError,'exact prepared current-target review'):
            self.current_target('merge',attempt_id=aid,review_id=wf.identity('DO'))
        with self.assertRaisesRegex(wf.WorkflowError,'already has an active integration owner'):
            self.current_target('prepare',owner_instruction=owner,expected_target_head=later)
        with self.assertRaisesRegex(wf.WorkflowError,'target advanced without it'):
            self.current_target('merge',attempt_id=aid,review_id=review_id)
        stale=self.selected.load()['active_run']['delivery']['current_target_attempts'][aid]
        self.assertEqual(stale['status'],'stale')
        replacement=self.current_target('prepare',owner_instruction=owner,expected_target_head=later)
        self.assertNotEqual(replacement['id'],aid)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),later)

    def test_current_target_reports_authored_conflict_and_preserves_original_refs(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid,extra={'source.py':'value = 2\n'})
        frozen=self.finish_reviewed_fixture()['delivery']['reviewed_source']
        (self.launch/'source.py').write_text('value = 3\n')
        self.git(self.launch,'add','source.py');self.git(self.launch,'commit','-m','Competing authored change')
        advanced=self.git(self.launch,'rev-parse','HEAD')
        owner='Integrate the approved fixture into this current local target.'
        with self.assertRaisesRegex(wf.WorkflowError,'Only exact known'):
            self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced,generated_paths=['source.py'])
        conflict=self.current_target('prepare',owner_instruction=owner,expected_target_head=advanced)
        self.assertEqual(conflict['status'],'conflicted')
        self.assertEqual(conflict['conflicting_paths'],['source.py'])
        self.assertNotIn('worktree',conflict)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)
        self.assertEqual(self.git(self.source,'rev-parse','HEAD'),frozen['source']['source_head'])

    def test_current_target_moves_again_without_reusing_stale_candidate(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        self.finish_reviewed_fixture()
        self.git(self.launch,'commit','--allow-empty','-m','First target advance')
        first=self.git(self.launch,'rev-parse','HEAD')
        owner='Integrate the approved fixture into this current local target.'
        attempt=self.current_target('prepare',owner_instruction=owner,expected_target_head=first)
        with self.assertRaisesRegex(wf.WorkflowError,'already has an active integration owner'):
            wf.current_target_delivery(self.selected,'current-target-prepare',{
                'integrator_id':'other-integrator','owner_instruction':owner,'expected_target_head':first})
        self.git(self.launch,'commit','--allow-empty','-m','Second target advance')
        second=self.git(self.launch,'rev-parse','HEAD')
        with self.assertRaisesRegex(wf.WorkflowError,'target moved'):
            self.current_target('seal',attempt_id=attempt['id'])
        retry=self.current_target('prepare',owner_instruction=owner,expected_target_head=second)
        self.assertNotEqual(retry['id'],attempt['id']);self.assertNotEqual(retry['worktree'],attempt['worktree'])
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),second)

    def test_policy_optional_merge_at_launch_and_explicit_remote_delivery(self):
        self.start_reviewed_controller('next',merges=True)
        self.accept_scoped_source(self.tid)
        result=self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'],'merged')
        self.assertEqual(self.git(self.remote,'show-ref'),self.remote_before)

    def test_policy_explicit_remote_order_retains_separate_publication(self):
        run=self.start_reviewed_controller('next',remote=True)
        self.assertNotIn('reviewed_local_delivery',run)
        self.assertEqual(run['workspace']['base_branch'],'develop')
        self.accept_scoped_source(self.tid)
        self.assertEqual(wf.finish(self.selected)['delivery']['status'],'implementation-completed')
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),self.start_head)
        self.assertEqual(self.git(self.remote,'show-ref'),self.remote_before)

    def test_policy_review_ready_requires_hook_preflight_outside_writer(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        chain=wf.identity('HC')
        with self.selected.lock():
            text=self.selected.text()
            state=self.selected.load(text)
            state['active_run']['hook_chains']=[chain]
            self.selected.save(text,state)
        observed=[]
        def prepare(store,scope=None,chain_ids=None):
            if chain_ids:
                self.assertFalse(getattr(store,'_writer_active',False))
                observed.append(('prepare',chain_ids))
        def guard(store,scope=None,chain_ids=None,**options):
            if chain_ids:
                self.assertTrue(store._writer_active)
                self.assertEqual(observed[-1],('prepare',[chain]))
                observed.append(('guard',chain_ids))
        with patch.object(wf,'prepare_hook_admission',side_effect=prepare), patch.object(wf,'hook_admission',side_effect=guard):
            result=self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'],'review-ready')
        self.assertEqual(observed,[('prepare',[chain]),('guard',[chain])])

    def test_policy_merge_accepts_a_tracked_file_with_a_new_ignore_rule(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        (self.source/'later-ignored.txt').write_text('Tracked accepted data.\n')
        self.git(self.source,'add','later-ignored.txt')
        (self.source/'.gitignore').write_text('later-ignored.txt\n')
        self.git(self.source,'add','.gitignore')
        self.git(self.source,'commit','-m','Scoped final review correction')
        self.finish_reviewed_fixture()
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            merged=wf.merge_reviewed_controller(self.selected,{'owner_instruction':'Merge the reviewed run locally.'})
        self.assertEqual(merged['delivery']['status'],'merged')
        self.assertEqual(self.git(self.launch,'status','--porcelain'),'')
        self.assertEqual(self.git(self.launch,'show','HEAD:later-ignored.txt'),'Tracked accepted data.')

    def test_policy_review_ready_uses_original_base_after_launch_branch_advances(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        self.git(self.launch,'commit','--allow-empty','-m','Independent target change')
        advanced=self.git(self.launch,'rev-parse','HEAD')
        wf.advance(self.selected)
        self.assertEqual(wf.controller_review_identity(self.selected)['identity']['base_oid'],self.start_head)
        result=self.finish_reviewed_fixture()
        self.assertEqual(result['delivery']['status'],'review-ready')
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            with self.assertRaisesRegex(ws.RunError,'target moved'):
                wf.merge_reviewed_controller(self.selected,{'owner_instruction':'Merge the reviewed run locally.'})
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),advanced)

    def test_policy_merge_reconciles_reviewed_executable_mode_with_filemode_disabled(self):
        self.start_reviewed_controller('next')
        self.accept_scoped_source(self.tid)
        self.git(self.source,'config','core.fileMode','false')
        self.git(self.source,'update-index','--chmod=+x','source.py')
        self.git(self.source,'commit','-m','Reviewed executable mode')
        self.finish_reviewed_fixture()
        with patch.object(wf,'verified_implementation_review',return_value={'orchestration_hash':'a'*64}):
            result=wf.merge_reviewed_controller(self.selected,{'owner_instruction':'Merge the reviewed run locally.'})
        self.assertEqual(result['delivery']['status'],'merged')
        self.assertEqual(self.git(self.launch,'status','--porcelain'),'')
        self.assertTrue(self.git(self.launch,'ls-tree','HEAD','source.py').startswith('100755 '))

    def copy_source_generation(self):
        target = self.root / '.skill-tree'
        for directory in ('common', 'domains', 'templates', 'config', 'lib', 'src', 'bin',
                          'tests/fixtures/director'):
            shutil.copytree(CORE / directory, target / directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for entry in (CORE / 'skills/general').glob('*/SKILL.md'):
            destination = target / entry.relative_to(CORE)
            destination.parent.mkdir(parents=True)
            shutil.copyfile(entry, destination)
        self.git(self.root, 'add', '.skill-tree/common', '.skill-tree/domains',
                 '.skill-tree/templates', '.skill-tree/config', '.skill-tree/lib',
                 '.skill-tree/src', '.skill-tree/bin', '.skill-tree/skills',
                 '.skill-tree/tests/fixtures/director')
        self.git(self.root, 'commit', '-m', 'Fixture owned source generation')

    def registry_run(self, run_id=None):
        return wf.Store(self.root, neutral=True).load()['run_registry']['runs'][run_id or self.run['id']]

    def action(self, command, **payload):
        return wf.local_delivery_action(self.selected, command, payload)

    def assert_pending(self):
        delivery = self.registry_run()['delivery']
        self.assertFalse(delivery['order_completed'])
        self.assertEqual(delivery['publication'], 'not-requested')
        return delivery

    def install_target(self, flavor='general', provider='codex', root=None):
        root = root or self.root
        result = subprocess.run(
            ['node', str(root / '.skill-tree/bin/install.js'),
             '--only', provider, '--target', str(root), '--flavor', flavor, '--yes'],
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads((root / '.skill-tree/installation/profile.json').read_text())

    def verify_target(self):
        result = subprocess.run(
            ['node', str(self.root / '.skill-tree/installation/manager.js'), '--verify'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def merge(self, fast_forward=False):
        self.git(self.root, 'merge', '--ff-only' if fast_forward else '--no-ff',
                 *([] if fast_forward else ['--no-edit', '--no-overwrite-ignore']), self.git(self.source, 'rev-parse', 'HEAD'))
        return self.git(self.root, 'rev-parse', 'HEAD')

    def test_finish_does_not_close_authorized_local_merge(self):
        result = self.run_local()
        self.assertEqual(result['delivery']['implementation'], 'completed')
        self.assertEqual(result['delivery']['publication'], 'not-requested')
        self.assertFalse(result['delivery']['order_completed'])
        self.assertNotEqual(result['delivery']['status'], 'local-result')
        self.assertFalse(ws.delivery_finished(result))
        self.assertEqual(self.registry_run()['completed_ids'], [self.run['root_task_id']])
        self.assertEqual(wf.Store(self.root, neutral=True).load()['run_registry']['claims'], {})

    def test_repeated_finish_preserves_original_reviewed_source_after_ref_moves(self):
        result = self.run_local()
        frozen_head = self.git(self.source, 'rev-parse', 'HEAD')
        completion_path = self.root / '.skill-tree/history/runs' / ('run-' + self.run['id'].lower() + '.json')
        original_completion = completion_path.read_bytes()
        original_state = self.selected.state.read_bytes()
        self.git(self.source, 'commit', '--allow-empty', '-m', 'Unreviewed source movement')
        repeated = wf.finish(wf.Store(self.source, self.run['id']))
        self.assertEqual(repeated, result)
        self.assertEqual(completion_path.read_bytes(), original_completion)
        self.assertEqual(self.selected.state.read_bytes(), original_state)
        self.assertIn(frozen_head, original_completion.decode())
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'source|head'):
            self.action('prepare')
        self.assert_pending()

    def test_diverged_target_never_rebases_the_frozen_order(self):
        self.run_local()
        self.git(self.root, 'commit', '--allow-empty', '-m', 'Unapproved target movement')
        moved_head = self.git(self.root, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'target|diverg|base'):
            self.action('prepare')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), moved_head)
        self.assert_pending()

    def test_preparation_binds_exact_heads_and_reconciles_original_git_merge(self):
        self.run_local()
        source = self.git(self.source, 'rev-parse', 'HEAD')
        target = self.git(self.root, 'rev-parse', 'HEAD')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        prepared = self.action('prepare')['local_integration']['preparation']
        self.assertEqual(prepared['source_head'], source)
        self.assertEqual(prepared['target_head'], target)
        self.assertEqual(self.action('prepare')['local_integration']['preparation'], prepared)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('reconcile')
        commit = self.merge()
        self.assertEqual(self.git(self.root, 'show', '-s', '--format=%P', commit).split(), [target, source])
        # New Store instance models interruption after Git and before recording.
        self.selected = wf.Store(self.root, self.run['id'])
        first = self.action('reconcile')['local_integration']['merge']
        self.assertEqual(first['commit'], commit)
        self.assertEqual(self.action('reconcile')['local_integration']['merge'], first)
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), commit)
        self.assert_pending()

    def test_merge_action_preserves_ignored_collision_added_after_prepare(self):
        relative = '.ignored late\nsource'
        self.run_local(incoming={relative: 'incoming bytes\n'})
        self.action('prepare')
        original_head = self.git(self.root, 'rev-parse', 'HEAD')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.ignored*\n')
        (self.root / relative).write_text('ignored target bytes\n')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), original_head)
        self.assertEqual((self.root / relative).read_text(), 'ignored target bytes\n')
        self.assert_pending()

    def test_target_checkout_change_between_preflight_and_merge_never_writes_another_branch(self):
        self.run_local()
        prepared = self.action('prepare')['local_integration']['preparation']
        original_policy = ws.local_git_policy

        def switch_before_git_locks(root):
            original_policy(root)
            self.git(root, 'switch', '-c', 'other')

        with patch.object(ws, 'local_git_policy', side_effect=switch_before_git_locks):
            with self.assertRaisesRegex(ws.RunError, 'prepared target branch or head changed'):
                self.action('merge')
        self.assertEqual(self.git(self.root, 'branch', '--show-current'), 'other')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), prepared['target_head'])
        self.assertEqual((self.root / 'source.py').read_text(), 'value = 1\n')
        self.assertFalse((self.root / '.git/index.lock').exists())
        self.assert_pending()

    def test_target_ref_movement_after_locked_preflight_fails_before_checkout(self):
        self.run_local()
        prepared = self.action('prepare')['local_integration']['preparation']
        original_transaction = ws.local_ref_transaction
        moved = self.git(self.root, 'commit-tree', prepared['target_head'] + '^{tree}',
                         '-p', prepared['target_head'], '-m', 'Competing exact ref update')

        def move_before_ref_lock(*args):
            self.git(self.source, 'update-ref', prepared['target_ref'], moved, prepared['target_head'])
            return original_transaction(*args)

        with patch.object(ws, 'local_ref_transaction', side_effect=move_before_ref_lock):
            with self.assertRaisesRegex(ws.RunError, 'exact local source or target ref'):
                self.action('merge')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), moved)
        self.assertEqual((self.root / 'source.py').read_text(), 'value = 1\n')
        self.assertFalse((self.root / '.git/index.lock').exists())
        self.assert_pending()

    def test_symbolic_target_alias_at_same_tip_fails_before_checkout(self):
        self.run_local()
        prepared = self.action('prepare')['local_integration']['preparation']
        original_transaction = ws.local_ref_transaction
        alias = 'refs/heads/alias-tip'
        self.git(self.source, 'update-ref', alias, prepared['target_head'])

        def alias_before_ref_lock(*args):
            self.git(self.source, 'symbolic-ref', prepared['target_ref'], alias)
            return original_transaction(*args)

        with patch.object(ws, 'local_ref_transaction', side_effect=alias_before_ref_lock):
            with self.assertRaisesRegex(ws.RunError, 'direct prepared Git branch refs'):
                self.action('merge')
        self.assertEqual(self.git(self.root, 'symbolic-ref', prepared['target_ref']), alias)
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), prepared['target_head'])
        self.assertEqual((self.root / 'source.py').read_text(), 'value = 1\n')
        self.assertFalse((self.root / '.git/index.lock').exists())
        self.assert_pending()

    def test_owned_merge_disables_autostash_and_preserves_owned_dirt(self):
        self.run_local(owned_dirty=True)
        owned = (self.root / OWNED_FILE).read_bytes()
        self.git(self.root, 'config', 'merge.autostash', 'true')
        self.action('prepare')
        first = self.action('merge')['local_integration']['merge']
        self.assertEqual(self.action('merge')['local_integration']['merge'], first)
        self.assertEqual(self.git(self.root, 'config', 'merge.autostash'), 'true')
        self.assertEqual(self.git(self.root, 'for-each-ref', 'refs/stash'), '')
        self.assertEqual((self.root / OWNED_FILE).read_bytes(), owned)
        self.assert_pending()

    def synchronization_fixture(self,*,checked_out=False):
        delivery=wf.owned_module('fixture_fast_forward',CORE/'common/scripts/pr-review-state.py')
        target='main' if checked_out else 'develop'
        if checked_out:
            destination=self.base/'sync-source'
            self.git(self.root,'worktree','add','--detach','--',destination,'HEAD')
        else:
            destination=self.root
        target_ref='refs/heads/'+target
        before=self.git(self.root,'rev-parse',target_ref)
        (destination/'source.py').write_text('value = 2\n')
        self.git(destination,'commit','-am','Fixture target update')
        tip=self.git(destination,'rev-parse','HEAD')
        if checked_out:
            self.git(self.root,'worktree','remove','--',destination)
        tracking='refs/remotes/origin/'+target
        self.git(self.root,'update-ref',tracking,tip)
        return delivery,target_ref,before,tracking,tip

    def install_delivery_fixture_hook(self,name):
        marker=self.base/(name+'-executed')
        hook=self.root/'.git/hooks'/name
        hook.write_text('#!/bin/sh\nprintf invoked > '+shlex.quote(str(marker))+'\n')
        hook.chmod(0o700)
        return marker

    def test_unchecked_fast_forward_accepts_dormant_commit_hook(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture()
        marker=self.install_delivery_fixture_hook('pre-commit')
        owner=self.root/'local-only.txt'
        owner.write_text('staged owner content\n')
        self.git(self.root,'add',owner.name)
        owner.write_text('working owner content\n')
        status=self.git(self.root,'status','--short')
        current=self.git(self.root,'rev-parse','HEAD')
        try:
            delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        except delivery.ws.RunError as error:
            self.fail(str(error))
        self.assertEqual(self.git(self.root,'rev-parse',target),tip)
        self.assertEqual(self.git(self.root,'rev-parse','HEAD'),current)
        self.assertEqual(self.git(self.root,'status','--short'),status)
        self.assertFalse(marker.exists())

    def test_unchecked_fast_forward_reports_reference_hook_without_running_it(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture()
        marker=self.install_delivery_fixture_hook('reference-transaction')
        with self.assertRaisesRegex(delivery.ws.RunError,'executable Git hook: reference-transaction'):
            delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),before)
        self.assertFalse(marker.exists())

    def test_synchronization_preflights_reference_hook_before_remote_tracking_update(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture()
        self.git(self.root,'push','origin',tip+':'+target)
        self.git(self.root,'update-ref',tracking,before)
        marker=self.install_delivery_fixture_hook('reference-transaction')
        url=self.git(self.root,'remote','get-url','origin')
        record={'identity':{'target_branch':'develop','remote':'origin','remote_id':wf.digest(url.encode()),
                            'repo_id':delivery.ws.repo_id(self.root)},'merge_commit':tip}
        blocked=delivery.synchronize_local_target(self.root,record)
        self.assertEqual(blocked['status'],'pending')
        self.assertIn('executable Git hook: reference-transaction',blocked['reason'])
        self.assertEqual(self.git(self.root,'rev-parse',tracking),before)
        self.assertEqual(self.git(self.root,'rev-parse',target),before)
        self.assertFalse(marker.exists())
        hook=self.root/'.git/hooks/reference-transaction'
        hook.unlink()
        guard=delivery.ws.require_local_git_hooks
        def install_after_preflight(root,names):
            guard(root,names)
            self.install_delivery_fixture_hook('reference-transaction')
        with patch.object(delivery.ws,'require_local_git_hooks',side_effect=install_after_preflight):
            interrupted=delivery.synchronize_local_target(self.root,record)
        self.assertEqual(interrupted['status'],'pending')
        self.assertIn('executable Git hook: reference-transaction',interrupted['reason'])
        self.assertEqual(self.git(self.root,'rev-parse',tracking),tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),before)
        self.assertFalse(marker.exists())
        hook.unlink()
        retried=delivery.synchronize_local_target(self.root,record)
        self.assertEqual(retried['status'],'synchronized')
        self.assertEqual(retried['local_head'],tip)
        self.assertEqual(self.git(self.root,'rev-parse',tracking),tip)
        self.assertFalse(marker.exists())

    def test_unchecked_fast_forward_isolates_hooks_created_after_preflight(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture()
        marker=self.base/'reference-transaction-executed'
        guard=delivery.ws.require_local_git_hooks
        def install_after_preflight(root,names):
            guard(root,names)
            self.install_delivery_fixture_hook('reference-transaction')
        with patch.object(delivery.ws,'require_local_git_hooks',side_effect=install_after_preflight):
            delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),tip)
        self.assertFalse(marker.exists())

    def test_checked_target_preflights_index_hook_before_private_writer_setup(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture(checked_out=True)
        marker=self.install_delivery_fixture_hook('post-index-change')
        registrations=self.git(self.root,'worktree','list','--porcelain')
        with self.assertRaisesRegex(delivery.ws.RunError,'executable Git hook: post-index-change'):
            delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),before)
        self.assertEqual(self.git(self.root,'worktree','list','--porcelain'),registrations)
        self.assertFalse(marker.exists())

    def test_checked_target_preserves_incoming_collision_and_unrelated_dirt(self):
        delivery,target,before,tracking,tip=self.synchronization_fixture(checked_out=True)
        owner=self.root/'local-only.txt'
        owner.write_text('staged owner content\n')
        self.git(self.root,'add',owner.name)
        owner.write_text('working owner content\n')
        incoming=self.root/'source.py'
        incoming.write_text('incoming collision\n')
        with self.assertRaisesRegex(delivery.ws.RunError,'overlap|collision'):
            delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),before)
        self.assertEqual(incoming.read_text(),'incoming collision\n')
        self.git(self.root,'restore','--',incoming.name)
        dormant=self.install_delivery_fixture_hook('post-merge')
        delivery.fast_forward_local_target(self.root,target,before,tracking,tip)
        self.assertEqual(self.git(self.root,'rev-parse',target),tip)
        self.assertEqual(incoming.read_text(),'value = 2\n')
        self.assertEqual(owner.read_text(),'working owner content\n')
        self.assertEqual(self.git(self.root,'show',':'+owner.name),'staged owner content')
        self.assertFalse(dormant.exists())

    def test_executable_git_hook_is_reported_without_running_it(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        directory = self.base / 'custom-hooks'
        directory.mkdir()
        hook = directory / 'post-merge'
        hook.write_text('#!/bin/sh\nprintf invoked > hook-was-executed\n')
        hook.chmod(0o700)
        self.git(self.root, 'config', 'core.hooksPath', str(directory))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'executable Git hook'):
            self.action('merge')
        self.assertFalse((self.root / 'hook-was-executed').exists())
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)
        self.assert_pending()

    def test_preflight_never_refreshes_git_index_and_calls_hook(self):
        self.run_local()
        hook = self.root / '.git/hooks/post-index-change'
        hook.write_text('#!/bin/sh\nprintf invoked > post-index-executed\n')
        hook.chmod(0o700)
        source = self.root / 'source.py'
        previous = source.stat()
        os.utime(source, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
        self.action('prepare')
        self.assertFalse((self.root / 'post-index-executed').exists())
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'post-index-change'):
            self.action('merge')
        self.assertFalse((self.root / 'post-index-executed').exists())

    def test_branch_merge_options_cannot_create_a_wrong_tree(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'config', 'branch.main.mergeOptions', '--strategy=ours')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'branch-specific'):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'config', 'branch.main.mergeOptions'), '--strategy=ours')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)

    def test_enabled_git_signing_policy_stops_without_mutating_target(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'config', 'commit.gpgSign', 'true')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'signing policy'):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'config', 'commit.gpgSign'), 'true')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)
        self.assert_pending()

    def test_fast_forward_does_not_satisfy_prepared_two_parent_merge(self):
        self.run_local()
        self.action('prepare')
        commit = self.merge(fast_forward=True)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('reconcile')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), commit)
        self.assert_pending()

    def test_exact_merge_parents_without_incoming_tree_do_not_complete(self):
        self.run_local()
        prep = self.action('prepare')['local_integration']['preparation']
        self.git(self.root, 'merge', '--no-ff', '--no-edit', '-s', 'ours', prep['source_head'])
        commit = self.git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(self.git(self.root, 'show', '-s', '--format=%P', commit).split(),
                         [prep['target_head'], prep['source_head']])
        self.assertEqual((self.root / 'source.py').read_text(), 'value = 1\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'tree|incoming'):
            self.action('reconcile')
        self.assert_pending()

    def changed_verifier(self):
        path = self.source / '.skill-tree/lib/installation.js'
        marker = self.source / 'unreviewed-verifier-was-executed'
        path.write_text("require('node:fs').writeFileSync(" + json.dumps(str(marker)) + ", 'unexpected');\n")
        self.git(self.source, 'add', '.skill-tree/lib/installation.js')
        return marker

    def test_moved_source_verifier_is_never_executed(self):
        self.run_local(real_installer=True)
        marker = self.changed_verifier()
        self.git(self.source, 'commit', '-m', 'Unreviewed verifier movement')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'source head|tree'):
            self.action('prepare')
        self.assertFalse(marker.exists())
        self.assert_pending()

    def test_finish_checks_stale_required_source_before_loading_verifier(self):
        self.run_local(real_installer=True, finish=False)
        marker = self.changed_verifier()
        (self.source / 'source.py').write_text('value = 3\n')
        self.git(self.source, 'add', 'source.py')
        self.git(self.source, 'commit', '-m', 'Unaccepted implementation movement')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'stale'):
            wf.finish(self.selected)
        self.assertFalse(marker.exists())

    def test_git_index_override_is_rejected(self):
        self.run_local()
        with patch.dict(os.environ, {'GIT_INDEX_FILE': str(self.base / 'other-index')}):
            with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'index overrides'):
                self.action('prepare')
        self.assert_pending()

    def test_source_movement_keeps_original_preparation_pending(self):
        self.run_local()
        original = self.action('prepare')['local_integration']['preparation']
        self.git(self.source, 'commit', '--allow-empty', '-m', 'Unreviewed source movement')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('prepare')
        self.assertEqual(self.assert_pending()['local_integration']['preparation'], original)

    def test_target_source_overlap_and_writer_lock_reject_preparation(self):
        self.run_local()
        original = (self.root / 'source.py').read_text()
        (self.root / 'source.py').write_text('local target edit\n')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('prepare')
        self.assertEqual((self.root / 'source.py').read_text(), 'local target edit\n')
        (self.root / 'source.py').write_text(original)
        with wf.Store(self.root, neutral=True).lock():
            with self.assertRaises((wf.WorkflowError, ws.RunError)):
                self.action('prepare')
        self.assert_pending()

    def test_receipt_owned_tracked_dirt_is_distinct_from_owned_path_edit(self):
        self.run_local(owned_dirty=True)
        for root in (self.root, self.source):
            self.assertIn(OWNED_FILE, self.git(root, 'status', '--porcelain', '--', OWNED_FILE))
        original = (self.root / OWNED_FILE).read_bytes()
        (self.root / OWNED_FILE).write_bytes(original + b'fixture unauthorized edit\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'owned|modified|dirty'):
            self.action('prepare')
        (self.root / OWNED_FILE).write_bytes(original)
        self.action('prepare')
        self.assertEqual((self.root / OWNED_FILE).read_bytes(), original)
        self.assert_pending()

    def test_ignored_nul_delimited_obstruction_is_never_overwritten(self):
        relative = '.ignored new\nname'
        self.run_local(incoming={relative: 'incoming source\n'})
        target = self.root / relative
        target.write_text('ignored target owner bytes\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.ignored*\n')
        self.assertIn('.ignored', self.git(self.root, 'check-ignore', '--', relative))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'ignored target owner bytes\n')
        self.assert_pending()

    def test_ignored_file_prefix_is_an_incoming_directory_collision(self):
        self.run_local(incoming={'.collision/nested.txt': 'incoming file\n'})
        target = self.root / '.collision'
        target.write_text('retained file\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.collision\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'retained file\n')
        self.assert_pending()

    def test_ignored_directory_prefix_is_an_incoming_file_collision(self):
        self.run_local(incoming={'.collision': 'incoming file\n'})
        target = self.root / '.collision' / 'retained.txt'
        target.parent.mkdir()
        target.write_text('retained file\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.collision/\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'retained file\n')
        self.assert_pending()

    def test_unrelated_workflow_journal_is_not_recovered_by_delivery(self):
        self.run_local()
        transaction = self.root / '.skill-tree/.transaction.json'
        original = b'{"format":"skill-tree-transaction","writes":[]}\n'
        transaction.write_bytes(original)
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'journal|transaction'):
            self.action('prepare')
        self.assertEqual(transaction.read_bytes(), original)
        transaction.unlink()
        self.assert_pending()

    def test_retained_admission_does_not_recover_another_action_target(self):
        self.run_local()
        transaction = self.root / '.skill-tree/.transaction.json'
        first, second = wf.identity('WR'), wf.identity('WR')
        journal = {
            'format': 'skill-tree-transaction',
            'writes': [],
            'local_delivery': {'run_id': self.run['id'], 'action': 'admit-retained', 'retained_run_id': first},
        }
        transaction.write_text(json.dumps(journal))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'journal|transaction'):
            self.action('admit-retained', run_id=second)
        self.assertEqual(json.loads(transaction.read_text()), journal)
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'Prepare'):
            self.action('admit-retained', run_id=first)
        self.assertFalse(transaction.exists())
        self.assert_pending()

    def test_activation_rejects_verified_old_owned_generation_and_requires_admission(self):
        self.run_local(real_installer=True)
        old = self.install_target()
        self.verify_target()
        self.action('prepare')
        commit = self.merge()
        self.action('reconcile')
        # The old installed manager verifies its own bundle even after the merge.
        self.verify_target()
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('admit-target')
        self.install_target(flavor='web')
        self.verify_target()
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'flavor|scope|destination'):
            self.action('admit-target')
        current = self.install_target()
        self.assertNotEqual(current['identity'], old['identity'])
        self.assertIn('src/delivery-fixture-generation.txt', current['source_digests'])
        self.verify_target()
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        admission = self.action('admit-target')['local_integration']['target_admission']
        self.assertEqual(admission['profile_identity'], current['identity'])
        self.assertEqual(admission['merge_commit'], commit)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        self.assert_pending()

    def test_re_admission_is_exactly_scoped_to_retained_stopped_run(self):
        self.run_local(retain=True, real_installer=True, baseline_target=True)
        retained_id = self.retained['id']
        retained_before = self.registry_run(retained_id)
        self.action('prepare')
        self.merge()
        self.action('reconcile')
        self.install_target()
        self.action('admit-target')
        self.assertTrue(self.registry_run(retained_id)['profile_refresh_required'])
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('admit-retained', run_id=self.run['id'])
        self.action('admit-retained', run_id=retained_id)
        retained_after = self.registry_run(retained_id)
        self.assertFalse(retained_after.get('profile_refresh_required', False))
        for key in ('snapshot', 'admitted_task_ids', 'limits', 'phase', 'stop_reason', 'next_action'):
            self.assertEqual(retained_after[key], retained_before[key])
        self.assertEqual((self.location(self.retained) / 'source.py').read_text(), 'value = 9\n')
        self.assert_pending()

    def test_final_current_validation_closes_only_local_order(self):
        self.run_local(real_installer=True)
        self.install_target()
        self.action('prepare')
        commit = self.merge()
        self.action('reconcile')
        current = self.install_target()
        self.action('admit-target')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('validate-target', checks=[{'id': 'untrusted', 'exit_code': 0}])
        # Production selects and actually executes known commands in the target
        # checkout. The test must never hand an asserted pass to the action.
        fixture_commands = (
            ('owned-installation', ('node', '.skill-tree/installation/manager.js', '--verify')),
            ('incoming-diff', ('git', 'diff', '--check', commit + '^1', commit, '--')),
        )
        with patch.object(wf, '_local_delivery_commands', return_value=fixture_commands):
            record = self.action('validate-target')['local_integration']['validation']
        self.assertEqual([check['id'] for check in record['checks']], ['owned-installation', 'incoming-diff'])
        self.assertEqual(record['merge_commit'], commit)
        self.assertEqual(record['profile_identity'], current['identity'])
        artifact = self.root / record['evidence'][0]['path']
        original_report = artifact.read_bytes()
        artifact.write_text('{}')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        artifact.write_bytes(original_report)
        delivery = self.action('complete')
        self.assertTrue(delivery['order_completed'])
        self.assertEqual(delivery['publication'], 'not-requested')
        self.assertEqual(delivery['local_integration']['merge']['commit'], commit)
        self.assertTrue(ws.delivery_finished(self.registry_run()))
        self.assertEqual(delivery['worktree_cleanup']['status'], 'removed')
        self.assertFalse(self.source.exists())
        self.assertEqual(self.action('complete')['local_integration'], delivery['local_integration'])

    def test_canonical_queue_drift_after_merge_preserves_other_run_and_blocks_completion(self):
        self.run_local(retain=True)
        state = self.registry_run(self.retained['id'])
        self.action('prepare')
        self.merge()
        queue = self.root / '.skill-tree/documents/future.md'
        before = queue.read_bytes()
        queue.write_bytes(before + b'\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'preserv|queue|dirty'):
            self.action('reconcile')
        self.assertEqual(queue.read_bytes(), before + b'\n')
        self.assertEqual(self.registry_run(self.retained['id']), state)
        self.assertEqual((self.location(self.retained) / 'source.py').read_text(), 'value = 9\n')
        self.assert_pending()


    def partially_accepted_delivery_fixture(self):
        self.start_reviewed_controller('all', deps=True, partial_recipe=True)
        wf.advance(self.selected)
        accepted = self.accept_scoped_source(self.dependency, commit_evidence=True)
        wf.advance(self.selected)
        wf.checkpoint(self.selected, {'phase':'stopped','stop_reason':'Owner paused after the first accepted task.'})
        fresh = lambda: wf.Store(self.root,self.run['id'])
        preview = wf.partial_finish(fresh(),'partial-finish-preview',{})
        closed = wf.partial_finish(fresh(),'partial-finish', {
            'expected_preview_sha256':preview['preview_sha256'],
            'owner_instruction':'Close the exact paused fixture.'})
        return fresh, accepted['task_git_commit']['commit'], closed

    def test_partial_delivery_observes_already_integrated_without_second_merge(self):
        fresh, tip, closed = self.partially_accepted_delivery_fixture()
        self.git(self.launch,'merge','--ff-only',tip)
        target_head = self.git(self.launch,'rev-parse','HEAD')
        config = {'target_branch':'release/example','target_worktree':str(self.launch)}
        observation = wf.partial_delivery(fresh(),'partial-delivery-preview',config)
        self.assertEqual((observation['status'],observation['accepted_tip']),('already-integrated',tip))
        request = {**config,'expected_preview_sha256':observation['preview_sha256'],
                   'owner_instruction':'Record the exact already-integrated target.'}
        result = wf.partial_delivery(fresh(),'partial-delivery',request)
        self.assertEqual(result['status'],'already-integrated')
        self.assertNotIn('review_id',result)
        self.assertEqual(wf.partial_delivery(fresh(),'partial-delivery',request),result)
        with self.assertRaisesRegex(wf.WorkflowError,'original completed partial delivery'):
            wf.partial_delivery(fresh(),'partial-delivery',{**request,'owner_instruction':'A later request.'})
        self.assertEqual(wf.partial_delivery(fresh(),'partial-delivery-preview',config)['attempt'], result)
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),target_head)
        self.assertEqual(wf.partial_finish(fresh(),'partial-finish-preview',{}),closed)

    def test_partial_delivery_reviews_current_target_and_recovers_lost_merge_acknowledgement(self):
        fresh, tip, closed = self.partially_accepted_delivery_fixture()
        (self.launch/'target-only.txt').write_text('Retain the independent target change.\n')
        self.git(self.launch,'add','target-only.txt')
        self.git(self.launch,'commit','-m','Advance the target with disjoint content')
        target_head = self.git(self.launch,'rev-parse','HEAD')
        worktree = self.base/'partial-candidate'
        self.git(self.root,'worktree','add','-b','partial-candidate',worktree,tip)
        config = {'target_branch':'release/example','target_worktree':str(self.launch),'candidate_worktree':str(worktree)}
        behind = self.base/'partial-behind-base'
        self.git(self.root,'worktree','add','-b','partial-behind-base',behind,self.start_head+'~2')
        behind_request = {**config,'target_branch':'partial-behind-base','target_worktree':str(behind)}
        self.assertIn('does not contain the accepted range base',
                      wf.partial_delivery(fresh(),'partial-delivery-preview',behind_request)['reason'])
        blocked = wf.partial_delivery(fresh(),'partial-delivery-preview',config)
        self.assertEqual(blocked['status'],'blocked')
        self.assertIn('exact live target',blocked['reason'])
        self.git(worktree,'reset','--hard',target_head)
        self.git(worktree,'merge','--no-ff','--no-edit',tip)
        (worktree/'source.py').write_text((worktree/'source.py').read_text()+'# Independently reviewed fix\n')
        self.git(worktree,'add','source.py')
        self.git(worktree,'commit','-m','Fix the scoped review finding')
        reviewed_head = self.git(worktree,'rev-parse','HEAD')
        preview = wf.partial_delivery(fresh(),'partial-delivery-preview',config)
        self.assertEqual(preview['status'],'review-required')
        no_authority = {**config,'expected_preview_sha256':preview['preview_sha256']}
        with self.assertRaisesRegex(wf.WorkflowError,'explicit owner authority'):
            wf.partial_delivery(fresh(),'partial-delivery',no_authority)
        request = {**no_authority,'owner_instruction':'Review and merge only accepted work.',
                   'review_id':wf.identity('DO')}
        real_merge = ws.run_local_merge
        def lose_response(*args, **kwargs):
            real_merge(*args, **kwargs)
            raise OSError('Injected loss after partial merge ref update')
        checked = wf.partial_delivery(fresh(),'partial-delivery-checks',{
            **no_authority,'owner_instruction':'Execute the accepted candidate checks.'})
        self.assertEqual(checked['status'],'checked')
        frame = {'orchestration_hash':'a'*64,
                 'plan':{'required_checks':preview['required_checks']},
                 'checks':{'results':[{'id':cid,'status':'passed','reference':check['review_reference']}
                                     for cid,check in checked['checks'].items()]}}
        forged = {**frame,'checks':{'results':[{'id':cid,'status':'passed','reference':'Unverified check text'}
                                              for cid in preview['required_checks']]}}
        with patch.object(wf,'verified_implementation_review',return_value=forged):
            self.assertEqual(wf.partial_delivery(fresh(),'partial-delivery',request)['status'],'blocked')
        self.assertEqual(self.git(self.launch,'rev-parse','HEAD'),target_head)
        with patch.object(wf,'verified_implementation_review',return_value=frame), \
                patch.object(ws,'run_local_merge',side_effect=OSError('Injected loss before Git')):
            with self.assertRaisesRegex(OSError,'Injected loss before Git'):
                wf.partial_delivery(fresh(),'partial-delivery',request)
        with self.assertRaisesRegex(wf.WorkflowError,'before running replacement checks'):
            wf.partial_delivery(fresh(),'partial-delivery-checks',{
                **no_authority,'owner_instruction':'Retry check with a different request.'})
        with patch.object(wf,'verified_implementation_review',return_value=frame) as review, \
                patch.object(ws,'run_local_merge',side_effect=lose_response):
            with self.assertRaisesRegex(OSError,'Injected loss'):
                wf.partial_delivery(fresh(),'partial-delivery',request)
        self.assertEqual(review.call_args.args[2:],(preview['identity'],preview['review_scope']))
        self.assertEqual(wf.partial_delivery(fresh(),'partial-delivery-preview',config)['status'],'prepared')
        receipt, = (self.root/'.skill-tree/history/runs').glob('run-*-partial-delivery-????????????????.json')
        original = receipt.read_bytes()
        receipt.unlink()
        with self.assertRaisesRegex(wf.WorkflowError,'canonical partial delivery record is missing'):
            wf.partial_delivery(fresh(),'partial-delivery-preview',config)
        receipt.write_bytes(original)
        edited = json.loads(original)
        edited['preview']['preparation']['source_tree'] = 'Falsified merge tree'
        receipt.write_text(wf.dump(edited))
        with self.assertRaisesRegex(wf.WorkflowError,'canonical recorded result'):
            wf.partial_delivery(fresh(),'partial-delivery',request)
        receipt.write_bytes(original)
        (self.launch/'further.txt').write_text('Retain the later independent target commit.\n')
        self.git(self.launch,'add','further.txt')
        self.git(self.launch,'commit','-m','Advance after the lost acknowledgement')
        result = wf.partial_delivery(fresh(),'partial-delivery',request)
        self.assertEqual(result['status'],'merged')
        self.assertEqual(result['merge']['parents'],[target_head,reviewed_head])
        self.assertEqual((self.launch/'target-only.txt').read_text(),'Retain the independent target change.\n')
        self.assertIn('Independently reviewed fix',(self.launch/'source.py').read_text())
        self.assertTrue((self.launch/'further.txt').is_file())
        self.assertEqual(wf.partial_finish(fresh(),'partial-finish-preview',{}),closed)


del fixture


if __name__ == '__main__':
    unittest.main()
