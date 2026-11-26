import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workspace_workflow',CORE/'common/scripts/workflow-state.py');wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf);ws=wf.workspaces

class RunWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name).resolve();self.root=self.base/'queue';self.root.mkdir()
        self.remote=self.base/'remote.git';self.call(self.base,'init','--bare',self.remote)
        self.call(self.root,'init','-b','main');self.call(self.root,'config','user.name','Fixture');self.call(self.root,'config','user.email','fixture@example.invalid')
        docs=self.root/'.skill-tree/documents';docs.mkdir(parents=True)
        (docs/'future.md').write_text('# Future Work\n\n## Pending Task Format\n\nFixed task headers.\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config=self.root/'.skill-tree/config';config.mkdir();(config/'repository.json').write_text('{"schema":1,"role":"source"}')
        (self.root/'source.py').write_text('value = 1\n');self.call(self.root,'add','.');self.call(self.root,'commit','-m','Fixture base');self.call(self.root,'branch','develop');self.call(self.root,'branch','release/example');self.call(self.root,'remote','add','origin',self.remote);self.call(self.root,'push','origin','main','develop','release/example');self.call(self.remote,'symbolic-ref','HEAD','refs/heads/main')
        self.store=wf.Store(self.root);ws.setup(self.store,{})
    def call(self,root,*args):
        result=subprocess.run(['git','-C',str(root),*map(str,args)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr);return result.stdout.strip()
    def task(self,title='Task',deps=(),topic=None,priority=100,touch='source.py'):
        store=wf.Store(self.root,allow_unselected=True)
        payload={'title':title,'description':'Preserve scoped source behavior.','expected_behavior':'Preserve scoped source behavior.','priority':priority}
        if topic is not None:
            payload.update(topic=topic,intake_batch_id=wf.identity('IB'),expected_source_hash=wf.file_hash(store.future))
        p=wf.intake(store,payload)
        body='Goal:\n- Preserve scoped source behavior.\n\nTouch:\n- '+touch+'\n\nValidation:\n```json\n'+json.dumps({'checks':[{'id':'behavior','recipe_id':'static-inspection','criteria':['Preserve scoped source behavior.'],'sources':[touch],'parameters':{},'assertion':'Preserve scoped source behavior.','timing':'immediate'}]})+'\n```\n\nAcceptance:\n- Preserve scoped source behavior.\n'
        return wf.process(store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'The fixture establishes the required source boundary.'}},'tasks':[{'title':title,'body':body,'depends_on':list(deps),'parent_pending_ids':[p['id']]}]})['created_ids'][0]
    def start(self,tid,**options):
        return wf.start(wf.Store(self.root,allow_unselected=True),'next',tid,workspace=options)
    def location(self,run):return Path(ws.runtime(self.root)['worktrees'][run['id']])
    def installed_web_profile_fixture(self, interrupt=False, legacy=False, location='explicit', flavor='web'):
        self.call(self.root, 'rm', '.skill-tree/config/repository.json')
        (self.root/'package.json').write_text('{"name":"web-profile-fixture","type":"module"}\n')
        (self.root/'.gitignore').write_text('.skill-tree/installation/\n.agents/\n.env.fixture\n')
        self.call(self.root, 'add', '--', 'package.json', '.gitignore')
        self.call(self.root, 'commit', '-m', 'Use an ignored project installation')
        (self.root/'.env.fixture').write_text('FIXTURE_ONLY=unchanged\n')
        command = ['node', str(CORE/'bin/install.js'), '--target', str(self.root), '--only', 'codex',
                   '--project', '--flavor', flavor, '--skills', 'skill-tree-work-through-next']
        if legacy:
            fallback = self.base/'retained-profile-source'
            for name in ('common','config','domains','lib','src','templates','tests/fixtures/director'):
                shutil.copytree(CORE/name,fallback/name)
            manager = fallback/'lib/installation.js'
            script = manager.read_text()
            start = script.index('function initialWorktreeProfile(')
            end = script.index('function packageMetadataAtDelivery(',start)
            manager.write_text((script[:start]+script[end:]).replace('install,initialWorktreeProfile,verify','install,verify'))
            command.extend(('--source',str(fallback)))
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        profile = self.root/'.skill-tree/installation/profile.json'
        before_profile = profile.read_bytes()
        self.call(self.root, 'check-ignore', profile.relative_to(self.root))
        task = self.task('Prepare exact linked profile')
        branch = self.call(self.root, 'symbolic-ref', '--short', 'HEAD')
        path = ws.common_dir(self.root)/'explicit-web' if location=='administrative' else self.base/'profile-target'
        options = {'implementation_operation':'work-through-next'}
        if location not in {'default','aliased-default'}:
            options['worktree']=str(path)
        start = lambda: wf.start(wf.Store(self.root, neutral=True), 'next', task, workspace=options)
        if location=='aliased-default':
            before = self.store.state.read_bytes()
            (self.base/'.skill-tree-worktrees').symlink_to(ws.common_dir(self.root),target_is_directory=True)
            with self.assertRaisesRegex(ws.RunError,'outside the canonical checkout and Git administrative storage'):
                start()
            self.assertEqual(self.store.state.read_bytes(),before)
            self.assertEqual(ws.runtime(self.root)['worktrees'],{})
            return
        if legacy:
            before = self.store.state.read_bytes()
            with self.assertRaisesRegex(ws.RunError,'Update the verified canonical installation'):
                start()
            self.assertEqual(self.store.state.read_bytes(),before)
            self.assertEqual(ws.runtime(self.root)['worktrees'],{})
            self.assertFalse(path.exists())
            self.assertEqual(profile.read_bytes(),before_profile)
            return
        if interrupt:
            actual_git = ws.git
            def fail_git(root, *args):
                if args[:2] == ('worktree','add'):
                    raise ws.RunError('fixture Git creation interrupted')
                return actual_git(root, *args)
            cut = (patch.object(ws,'create_reserved',side_effect=ws.RunError('fixture Git creation interrupted'))
                   if interrupt in {'before-locator','lost-locator'} else patch.object(ws,'git',side_effect=fail_git))
            with cut:
                with self.assertRaisesRegex(ws.RunError,'fixture Git creation interrupted'):
                    start()
            state = self.store.load()
            self.assertEqual(len(state['run_registry']['runs']),1)
            run = state['active_run']
            self.assertEqual(run['workspace_state'],'reserved')
            self.assertEqual(run['phase'],'refresh-profile')
            self.assertEqual(state['run_registry']['claims'],{task:run['id']})
            selected = wf.Store(self.root,run['id'])
            with self.assertRaisesRegex(ws.RunError,'original exact worktree'):
                ws.recover_workspace(selected,{'worktree':str(self.base/'wrong-profile-target'),'resolution':'Fixture checks rejected path.'})
            if interrupt in {'before-locator','lost-locator'}:
                local = ws.runtime(self.root)
                self.assertNotIn(run['id'],local['worktrees'])
                self.assertIn(run['id'],local['pending_worktrees'])
                if interrupt=='lost-locator':
                    staged = local['pending_worktrees'][run['id']]
                    ws.runtime_file(self.root).unlink()
                    recovery = wf.Store(self.root,route_queue=False,neutral=True)
                    with self.assertRaisesRegex(ws.RunError,'original exact reserved worktree'):
                        ws.recover_locator(recovery,{'queue_id':local['queue_id'],
                            'worktrees':{run['id']:str(self.base/'wrong-replacement-locator')}})
                    ws.recover_locator(recovery,{'queue_id':local['queue_id'],'worktrees':{run['id']:staged}})
                    self.assertEqual(ws.runtime(self.root)['pending_worktrees'],{run['id']:staged})
            ws.recover_workspace(selected,{'resolution':'Recover exact interrupted Git operation.'})
            path = self.location(run)
            handoff = wf.advance(selected)['profile_handoff']
            run = {**selected.load()['active_run'],'profile_handoff':handoff}
        else:
            run = start()
            handoff = run.get('profile_handoff')
            if location=='default':
                path = self.location(run)
        self.assertIsNotNone(handoff, 'New Web worktrees with ignored profiles must expose the guarded profile setup handoff')
        self.assertEqual(handoff['run_id'], run['id'])
        self.assertEqual(handoff['worktree'], str(path))
        self.assertEqual(handoff['queue_id'], ws.runtime(self.root)['queue_id'])
        self.assertIn('prepare-worktree-profile', handoff['argv'])
        self.assertFalse((path/'.skill-tree/installation/profile.json').exists())
        return run, task, path, profile, before_profile, branch

    def test_new_web_worktree_reaches_owned_profile_admission(self):
        run, task, path, canonical_profile, original, canonical_branch = self.installed_web_profile_fixture()
        selected = wf.Store(path,run['id'])
        self.assertEqual(selected.load()['active_run']['phase'], 'refresh-profile')
        with self.assertRaisesRegex(wf.WorkflowError, 'profile|stopped'):
            wf.begin_task(selected, {'task_id':task})
        with self.assertRaisesRegex(wf.WorkflowError, 'profile'):
            wf.checkpoint(selected,{'phase':'implement','stop_reason':None})
        with self.assertRaisesRegex(wf.WorkflowError, 'profile'):
            wf.resume_admission(selected)
        with self.assertRaisesRegex(wf.WorkflowError, 'profile'):
            wf.focus_maintenance(selected,{'task_id':task,'instruction':'Fixture cannot bypass the initial hold.'})
        command = run['profile_handoff']['argv']
        prepared = subprocess.run(command,capture_output=True,text=True,timeout=60)
        self.assertEqual(prepared.returncode,0,prepared.stdout+prepared.stderr)
        result = json.loads(prepared.stdout)
        self.assertEqual(result['run_id'],run['id'])
        self.assertEqual(result['status'],'admitted')
        replay = subprocess.run(command,capture_output=True,text=True,timeout=60)
        self.assertEqual(replay.returncode,0,replay.stdout+replay.stderr)
        self.assertEqual(json.loads(replay.stdout),result)
        operation = path/'.agents/skills/skill-tree-work-through-next/SKILL.md'
        original_skill = operation.read_bytes()
        try:
            operation.write_bytes(original_skill+b'\nEdited outside the receipt.\n')
            with self.assertRaisesRegex(wf.WorkflowError,'Unowned or locally modified'):
                wf.prepare_worktree_profile(selected)
        finally:
            operation.write_bytes(original_skill)
        state = selected.load()
        self.assertEqual(state['active_run']['phase'],'implement')
        self.assertIsNone(state['active_run']['stop_reason'])
        self.assertEqual(state['run_registry']['claims'],{task:run['id']})
        self.assertFalse((path/'.env.fixture').exists())
        self.assertEqual(canonical_profile.read_bytes(),original)
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)
        self.assertEqual(wf.begin_task(selected,{'task_id':task})['phase'],'implement')

    def test_initial_profile_admits_another_parked_worktree_while_a_run_executes(self):
        first, first_task, first_path, canonical_profile, original, _ = self.installed_web_profile_fixture()
        second_task = self.task('Prepare a second isolated profile')
        second = wf.start(wf.Store(self.root, neutral=True), 'next', second_task, workspace={
            'implementation_operation':'work-through-next',
            'worktree':str(self.base/'second-profile-target'),
        })
        first_store = wf.Store(first_path, first['id'])
        self.assertEqual(wf.prepare_worktree_profile(first_store)['status'], 'admitted')
        self.assertEqual(wf.begin_task(first_store, {'task_id':first_task})['phase'], 'implement')
        before = first_store.load()
        second_path = self.location(second)
        second_store = wf.Store(second_path, second['id'])
        self.assertEqual(second_store.load()['active_run']['phase'], 'refresh-profile')
        self.assertEqual(wf.prepare_worktree_profile(second_store)['status'], 'admitted')
        after = second_store.load()
        self.assertEqual(after['active_run']['phase'], 'implement')
        self.assertEqual(after['run_registry']['runs'][first['id']], before['active_run'])
        self.assertEqual(after['task_progress'][first_task], before['task_progress'][first_task])
        self.assertEqual(after['run_registry']['claims'], {first_task:first['id'], second_task:second['id']})
        self.assertEqual(canonical_profile.read_bytes(), original)
        refresh = subprocess.run(['node', str(canonical_profile.with_name('manager.js')),
                                  '--refresh-profile', '--dry-run'], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(refresh.returncode, 0)
        self.assertIn('Active controller must checkpoint', refresh.stderr)
        self.assertEqual(canonical_profile.read_bytes(), original)

    def test_initial_profile_keeps_the_install_barrier_for_overlapping_general_worktrees(self):
        first, first_task, first_path, canonical_profile, original, _ = self.installed_web_profile_fixture(flavor='general')
        peer_registration = ws.linked_registration(self.root,first_path)
        overlaps = [first_path/'nested-profile-target', peer_registration/'nested-profile-target']
        siblings = []
        for index, nested in enumerate(overlaps,1):
            task_id = self.task('Preserve active sibling boundary '+str(index))
            run = wf.start(wf.Store(self.root, neutral=True), 'next', task_id, workspace={
                'implementation_operation':'work-through-next', 'worktree':str(nested),
            })
            siblings.append((nested,run['id']))
        first_store = wf.Store(first_path, first['id'])
        self.assertEqual(wf.prepare_worktree_profile(first_store)['status'], 'admitted')
        self.assertEqual(wf.begin_task(first_store, {'task_id':first_task})['phase'], 'implement')
        before = self.store.state.read_bytes()
        for nested,run_id in siblings:
            with self.subTest(checkout=nested.parent.name):
                with self.assertRaisesRegex(wf.WorkflowError, 'Active controller must checkpoint'):
                    wf.prepare_worktree_profile(wf.Store(nested, run_id))
                self.assertFalse((nested/'.skill-tree/installation/profile.json').exists())
        self.assertEqual(self.store.state.read_bytes(), before)
        self.assertEqual(canonical_profile.read_bytes(), original)

    def test_rejected_and_interrupted_profile_setup_keep_the_exact_run(self):
        run, task, path, canonical_profile, original, canonical_branch = self.installed_web_profile_fixture()
        store = wf.Store(path,run['id'])
        unexpected = path/'.agents/skills/skill-tree-work-through-next/owner.txt'
        unexpected.parent.mkdir(parents=True)
        unexpected.write_text('Existing owner file.\n')
        before = self.store.state.read_bytes()
        try:
            canonical_profile.write_bytes(original+b'\n')
            with self.assertRaisesRegex(wf.WorkflowError, 'original canonical profile'):
                wf.prepare_worktree_profile(store)
            self.assertEqual(self.store.state.read_bytes(),before)
        finally:
            canonical_profile.write_bytes(original)
        with self.assertRaisesRegex(wf.WorkflowError, 'Unowned|profile|conflict'):
            wf.prepare_worktree_profile(store)
        self.assertEqual(self.store.state.read_bytes(),before)
        self.assertEqual(unexpected.read_text(),'Existing owner file.\n')
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        unexpected.unlink()
        unexpected.parent.rmdir()
        with patch.object(wf,'resume_admission',side_effect=wf.WorkflowError('fixture acknowledgement lost')):
            with self.assertRaisesRegex(wf.WorkflowError,'fixture acknowledgement lost'):
                wf.prepare_worktree_profile(store)
        self.assertTrue((path/'.skill-tree/installation/profile.json').is_file())
        self.assertEqual(self.store.state.read_bytes(),before)
        self.assertEqual(wf.prepare_worktree_profile(store)['status'],'admitted')
        state=store.load()
        self.assertEqual(state['run_registry']['claims'],{task:run['id']})
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        self.assertEqual(state['active_run']['workspace']['cleanup_owner'],run['workspace']['cleanup_owner'])
        self.assertEqual(canonical_profile.read_bytes(),original)
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_legacy_installer_update_is_required_before_reservation(self):
        self.installed_web_profile_fixture(legacy=True)

    def test_initial_profile_handoff_survives_git_reservation_recovery(self):
        run, task, path, canonical_profile, original, canonical_branch = self.installed_web_profile_fixture(interrupt=True)
        selected = wf.Store(path, run['id'])
        self.assertEqual(wf.prepare_worktree_profile(selected)['status'],'admitted')
        state = selected.load()
        self.assertEqual(state['run_registry']['claims'],{task:run['id']})
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        self.assertEqual(canonical_profile.read_bytes(),original)
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_web_default_worktree_and_runtime_use_a_sibling_checkout(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(location='default')
        common = ws.common_dir(self.root)
        self.assertFalse(path.is_relative_to(common), 'The default Web worktree must be outside Git administrative storage')
        self.assertFalse(path.is_relative_to(self.root))
        self.assertEqual(path,self.location(run))
        self.assertEqual(self.call(path,'symbolic-ref','--short','HEAD'),run['workspace']['branch'])
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)
        view = ws.environment(wf.Store(self.root,run['id']),{'runtime':True})
        self.assertEqual(view['project_root'],str(path))
        self.assertFalse(view['runtime_qualified'])
        other = self.task('Another isolated Web root')
        with self.assertRaisesRegex(ws.RunError,'overlaps another retained run worktree'):
            wf.start(wf.Store(self.root,neutral=True),'next',other,workspace={
                'implementation_operation':'work-through-next','worktree':str(path/'unadmitted-nested')})
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])

    def test_default_web_worktree_rejects_an_alias_into_git_storage(self):
        self.installed_web_profile_fixture(location='aliased-default')

    def test_explicit_web_worktree_in_git_requires_an_outside_runtime_path(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(location='administrative')
        self.assertEqual(path,ws.common_dir(self.root)/'explicit-web')
        self.assertEqual(self.call(path,'symbolic-ref','--short','HEAD'),run['workspace']['branch'])
        store = wf.Store(self.root,run['id'])
        view = ws.environment(store)
        self.assertEqual(view['project_root'],str(path))
        self.assertIn(str(path),view['web_runtime_path']['prerequisite'])
        request = self.base/'web-runtime-request.json'
        request.write_text('{"runtime":true}')
        command = [sys.executable,'-B',str(CORE/'common/scripts/workflow-state.py'),'environment',str(self.root),
                   '--run-id',run['id'],'--input',str(request)]
        probe = subprocess.run(command,capture_output=True,text=True,timeout=15)
        self.assertNotEqual(probe.returncode,0)
        self.assertIn('outside Git administrative storage',probe.stdout+probe.stderr)
        self.assertIn(str(path),probe.stdout+probe.stderr)
        self.assertEqual(self.location(run),path)
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_pending_web_reservations_reject_case_aliases(self):
        case_probe = self.base/'CaseProbe'
        case_probe.mkdir()
        alternative = self.base/'caseprobe'
        if not alternative.is_dir() or not alternative.samefile(case_probe):
            return  # Distinct spellings are safe on a case-sensitive filesystem.
        self.installed_web_profile_fixture(location='default')
        first = self.task('Retain first Web destination')
        second = self.task('Reject case-alias Web destination')
        reserved = self.base/'ReservedWeb'
        def launch(tid,path):
            return wf.start(wf.Store(self.root,neutral=True),'next',tid,workspace={
                'implementation_operation':'work-through-next','worktree':str(path)})
        with patch.object(ws,'create_reserved',side_effect=ws.RunError('fixture before Git creation')):
            with self.assertRaisesRegex(ws.RunError,'fixture before Git creation'):
                launch(first,reserved)
        with self.assertRaisesRegex(ws.RunError,'overlaps another retained run worktree'):
            launch(second,self.base/'reservedweb'/'child')
        state = wf.Store(self.root,neutral=True).load()
        active = state['run_registry']['claims'][first]
        self.assertNotIn(second,state['run_registry']['claims'])
        self.assertEqual(ws.runtime(self.root)['pending_worktrees'],{active:str(reserved)})
        self.assertFalse(reserved.exists())

    def test_default_web_reservation_recovers_before_locator_write(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(interrupt='before-locator',location='default')
        self.assertFalse(path.is_relative_to(ws.common_dir(self.root)))
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        state = wf.Store(path,run['id']).load()
        self.assertEqual(state['run_registry']['claims'],{task:run['id']})
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_explicit_web_reservation_recovers_before_locator_write(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(interrupt='before-locator')
        self.assertEqual(path,self.base/'profile-target')
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        self.assertEqual(wf.Store(path,run['id']).load()['run_registry']['claims'],{task:run['id']})
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_explicit_web_reservation_restores_a_lost_local_locator(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(interrupt='lost-locator')
        self.assertEqual(path,self.base/'profile-target')
        self.assertEqual(wf.Store(path,run['id']).load()['run_registry']['claims'],{task:run['id']})
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_default_web_reservation_recovers_after_locator_write(self):
        run, task, path, _, _, canonical_branch = self.installed_web_profile_fixture(interrupt=True,location='default')
        self.assertFalse(path.is_relative_to(ws.common_dir(self.root)))
        self.assertEqual(list(ws.runtime(self.root)['worktrees']),[run['id']])
        self.assertEqual(wf.Store(path,run['id']).load()['run_registry']['claims'],{task:run['id']})
        self.assertEqual(self.call(self.root,'symbolic-ref','--short','HEAD'),canonical_branch)

    def test_two_worker_handoffs_preserve_scope_evidence_and_controller_state(self):
        (self.root/'second.py').write_text('value = 1\n')
        (self.root/'shared.txt').write_text('shared input\n')
        self.call(self.root,'add','second.py','shared.txt')
        self.call(self.root,'commit','-m','Two worker sources')
        self.call(self.root,'push','origin','HEAD:develop')
        first=self.task('First worker source')
        second=self.task('Second worker source',touch='second.py')
        run=wf.start(wf.Store(self.root,allow_unselected=True),'all',workspace={'snapshot_ids':[first,second]})
        coordinator=self.location(run)
        store=lambda root=coordinator:wf.Store(root,run['id'])
        base=self.call(coordinator,'rev-parse','HEAD')
        left=self.base/'worker-left'
        right=self.base/'worker-right'
        for path in (left,right):
            self.call(coordinator,'worktree','add','--detach',path,base)
        queue_before=self.store.future.read_bytes()
        state_before=self.store.state.read_bytes()

        def assignment(slot, generation, path, task, source):
            return {'action':'assign','slot':slot,'generation':generation,'worker_id':'worker-'+str(slot),
                    'task_id':task,'worktree':str(path),'base':base,'paths':[source],'shared_inputs':['shared.txt']}
        assign_left=assignment(1,1,left,first,'source.py')
        assign_right=assignment(2,1,right,second,'second.py')
        with patch.object(wf.Store,'recover',side_effect=AssertionError('Wrong caller reached the writer lock')):
            with self.assertRaisesRegex(wf.WorkflowError,'coordinator worktree'):
                wf.worker_handoff(store(left),assign_left)
        with self.assertRaisesRegex(wf.WorkflowError,'source base'):
            wf.worker_handoff(store(),{**assign_left,'base':'0'*40})
        left_receipt=wf.worker_handoff(store(),assign_left)
        self.assertEqual(wf.worker_handoff(store(),assign_left),left_receipt)
        with self.assertRaisesRegex(wf.WorkflowError,'overlaps another write scope'):
            wf.worker_handoff(store(),assignment(2,1,right,first,'source.py'))
        wf.worker_handoff(store(),assign_right)

        def candidate(slot, path, source):
            (path/source).write_text('value = 2\n')
            self.call(path,'add',source)
            self.call(path,'commit','-m','Scoped worker candidate')
            artifact=path/'check.txt'
            artifact.write_text('Verified fixture behavior.\n')
            return {'action':'record','slot':slot,'generation':1,'worker_id':'worker-'+str(slot),
                    'head':self.call(path,'rev-parse','HEAD'),'checks':[
                    {'id':'behavior','result':'pass','path':'check.txt','sha256':wf.file_hash(artifact)}]}

        left_result=candidate(1,left,'source.py')
        right_result=candidate(2,right,'second.py')
        self.store.future.write_text(queue_before.decode().replace('Touch:\n- second.py','Touch:\n- other.py'))
        with self.assertRaisesRegex(wf.WorkflowError,'assignment task contract changed'):
            wf.worker_handoff(store(),right_result)
        self.store.future.write_bytes(queue_before)
        self.assertEqual(wf.worker_handoff(store(),left_result)['candidate']['paths'],['source.py'])
        accepted=wf.worker_handoff(store(),{'action':'status'})
        with self.assertRaisesRegex(ws.RunError,'checked-out commit'):
            wf.worker_handoff(store(),{**right_result,'head':base})
        with self.assertRaisesRegex(wf.WorkflowError,'artifact is missing, aliased or changed'):
            wf.worker_handoff(store(),{**right_result,'checks':[{
                **right_result['checks'][0],'sha256':'0'*64}]})
        (coordinator/'shared.txt').write_text('changed input\n')
        with self.assertRaisesRegex(wf.WorkflowError,'shared validation inputs drifted'):
            wf.worker_handoff(store(),right_result)
        self.call(coordinator,'restore','shared.txt')
        (right/'source.py').write_text('escaped scope\n')
        self.call(right,'add','source.py')
        self.call(right,'commit','-m','Outside worker scope')
        with self.assertRaisesRegex(ws.RunError,'outside the assigned scope'):
            wf.worker_handoff(store(),{**right_result,'head':self.call(right,'rev-parse','HEAD')})
        self.call(right,'checkout','--detach',right_result['head'])
        self.assertEqual(wf.worker_handoff(store(),{'action':'status'}),accepted)
        result=wf.worker_handoff(store(),right_result)
        self.assertEqual(wf.worker_handoff(store(),right_result),result)
        with self.assertRaisesRegex(wf.WorkflowError,'retry differs'):
            wf.worker_handoff(store(),{**right_result,'checks':[{
                **right_result['checks'][0],'result':'fail'}]})
        reread=wf.worker_handoff(store(self.root),{'action':'status'})
        self.assertEqual(reread['slots']['1'][0]['result']['candidate']['head'],left_result['head'])
        self.assertEqual(reread['slots']['2'][0]['result']['checks'],right_result['checks'])

        replacement=self.base/'worker-replacement'
        self.call(coordinator,'worktree','add','--detach',replacement,base)
        wf.worker_handoff(store(),assignment(2,2,replacement,second,'second.py'))
        with self.assertRaisesRegex(wf.WorkflowError,'current assignment generation'):
            wf.worker_handoff(store(),right_result)
        after=wf.worker_handoff(store(),{'action':'status'})
        self.assertEqual(after['slots']['2'][0]['result'],result)
        self.assertEqual(after['slots']['2'][1]['generation'],2)
        self.assertEqual(self.store.future.read_bytes(),queue_before)
        self.assertEqual(self.store.state.read_bytes(),state_before)
        self.assertFalse(self.store.owned(wf.OUTCOME_LEDGER).exists())
        self.assertEqual(self.call(coordinator,'rev-parse','HEAD'),base)

    def test_worker_checkout_refuses_another_registered_controller(self):
        first=self.start(self.task('First controller'))
        second=self.start(self.task('Second controller'))
        with self.assertRaisesRegex(ws.RunError,'registered controller checkout'):
            ws.worker_checkout(self.location(first),str(self.location(second)))
    def test_default_workspace_uses_remote_develop_and_stable_run_branch(self):
        tid=self.task();run=self.start(tid);path=self.location(run)
        self.assertEqual(run['workspace']['base_branch'],'develop');self.assertTrue(run['workspace']['branch'].startswith('codex/wr-'));self.assertNotEqual(path,self.root)
        self.assertEqual(run['workspace']['base_commit'],self.call(self.root,'rev-parse','origin/develop'))
        state=wf.Store(path).load();self.assertEqual(state['active_run']['id'],run['id']);self.assertEqual(state['run_registry']['claims'][tid],run['id'])
        self.assertEqual(wf.Store(path).root,self.root)
    def test_registered_schema_is_rejected_by_single_run_only_helpers(self):
        raw=json.loads(self.store.state.read_text());self.assertEqual(raw['schema'],3);self.assertIsNone(raw['active_run'])
        self.assertNotEqual(raw['schema'],2)
    def test_two_runs_different_bases_and_explicit_selection(self):
        a=self.task('First');b=self.task('Second');first=self.start(a);second=self.start(b,base_branch='release/example',branch='host/second',worktree=str(self.base/'second'))
        registry=wf.Store(self.root,allow_unselected=True).load()['run_registry'];self.assertEqual(len(registry['runs']),2);self.assertEqual(second['workspace']['base_branch'],'release/example')
        with self.assertRaisesRegex(ws.RunError,'Multiple runs'):wf.Store(self.root).load()
        self.assertEqual(wf.Store(self.root,first['id']).load()['active_run']['id'],first['id'])
        self.assertEqual(wf.Store(self.location(second)).load()['active_run']['id'],second['id'])
    def test_standalone_capture_and_processing_preserve_an_existing_controller(self):
        new_root=self.task('Explicit next root')
        existing=self.start(self.task('Existing controller root'))

        def standalone(command,payload,*options):
            request=self.base/'standalone.json'
            request.write_text(json.dumps(payload))
            result=subprocess.check_output([sys.executable,str(CORE/'common/scripts/workflow-state.py'),
                command,str(self.root),'--standalone','--input',str(request),*options],text=True)
            return json.loads(result)

        request={'title':'Separate request','description':'Inspect existing behavior.',
                 'expected_behavior':'Record existing behavior.'}
        batch=standalone('intake',{'items':[request],'intake_batch_id':wf.identity('IB'),
                                   'expected_source_hash':wf.file_hash(self.store.future)})
        pending=batch['items'][0]['id']
        processed=standalone('process',{'selectors':[pending],'expected_source_hash':wf.file_hash(self.store.future),
            'dispositions':{pending:{'status':'resolved','reason':'The requested behavior is already present.'}}})
        self.assertEqual(processed['selected_ids'],[pending])
        started=standalone('start',{'expected_source_hash':wf.file_hash(self.store.future)},'--id',new_root)
        self.assertEqual(started['snapshot'],[new_root])
        self.assertEqual(wf.Store(self.root,existing['id']).load()['active_run'],existing)
    def test_overlapping_claims_and_dependency_claims_are_atomic(self):
        shared=self.task('Shared');a=self.task('First',[shared]);b=self.task('Second',[shared]);first=self.start(a);before=self.store.state.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'claims conflict'):self.start(b)
        self.assertEqual(before,self.store.state.read_bytes());self.assertEqual(len(ws.runtime(self.root)['worktrees']),1)
        self.assertIn(shared,wf.Store(self.root,first['id']).load()['run_registry']['claims'])
    def test_implement_all_has_one_workspace_for_the_snapshot(self):
        a=self.task('First');b=self.task('Second');run=wf.start(wf.Store(self.root,allow_unselected=True),'all',workspace={})
        self.assertEqual(set(run['snapshot']),{a,b});self.assertEqual(len(ws.runtime(self.root)['worktrees']),1)
    def test_selected_snapshot_claims_only_selected_roots_and_dependencies(self):
        outside=self.task('Unrelated root');other=self.task('Another unrelated root');dep=self.task('Shared prerequisite')
        a=self.task('Selected root',[dep]);b=self.task('Second selected root',[dep])
        run=wf.start(wf.Store(self.root,allow_unselected=True),'all',workspace={'snapshot_ids':[a,b]})
        self.assertEqual(set(run['snapshot']),{a,b});self.assertEqual(set(run['admitted_task_ids']),{a,b,dep})
        claims=wf.Store(self.location(run)).load()['run_registry']['claims']
        self.assertEqual(claims,{tid:run['id'] for tid in [a,b,dep]})
        self.assertNotIn(outside,claims);self.assertNotIn(other,claims)
        self.assertEqual(len(ws.runtime(self.root)['worktrees']),1)
        later=self.task('Later unrelated root');wf.resume_admission(wf.Store(self.location(run)))
        resumed=wf.Store(self.location(run)).load()['active_run']
        self.assertEqual(resumed['snapshot'],run['snapshot']);self.assertEqual(resumed['admitted_task_ids'],run['admitted_task_ids'])
        self.assertNotIn(later,resumed['required_ids'])
        # Unselected work remains independently claimable without changing the selected run.
        second=self.start(outside)
        self.assertNotEqual(second['id'],run['id']);self.assertEqual(len(ws.runtime(self.root)['worktrees']),2)
    def test_invalid_selected_group_never_reserves_claims_or_workspace(self):
        chosen=self.task('Selected root');before=self.store.state.read_bytes();locator=ws.runtime(self.root)
        with patch.object(ws,'provision') as provision:
            with self.assertRaises(wf.WorkflowError):
                wf.start(wf.Store(self.root,allow_unselected=True),'all',workspace={'snapshot_ids':[chosen,wf.identity('T')]})
            provision.assert_not_called()
        self.assertEqual(before,self.store.state.read_bytes());self.assertEqual(locator,ws.runtime(self.root))
    def test_group_preview_from_linked_checkout_uses_canonical_queue_and_frozen_scope(self):
        dep = self.task('Outside prerequisite', topic='infrastructure', priority=130)
        first = self.task('First grouped root', [dep], topic='director')
        second = self.task('Later equal priority root', [dep], topic='director')
        unrelated = self.task('Unrelated root', topic='other')
        linked = self.base/'group-preview'
        self.call(self.root, 'worktree', 'add', '-b', 'fixture/group-preview', linked, 'develop')
        (linked/'.skill-tree/documents/future.md').write_text('Stale noncanonical queue copy.\n')

        selection = {'queue':'prioritized','topic':'director'}
        preview = wf.group_selection(wf.Store(linked), selection)
        self.assertEqual(preview['ids'], [second, first])
        self.assertEqual(preview['outside_dependencies'], [dep])
        self.assertEqual(preview['source_hash'], wf.file_hash(self.store.future))
        self.assertNotEqual(preview['source_hash'], wf.file_hash(linked/'.skill-tree/documents/future.md'))
        run = wf.start(wf.Store(self.root, allow_unselected=True), 'all', workspace={
            'snapshot_ids':preview['ids'],
            'expected_source_hash':preview['source_hash'],
        })
        self.assertEqual(run['snapshot'], [second, first])
        self.assertEqual(set(run['admitted_task_ids']), {first, second, dep})

        with self.store.lock():
            queue = self.store.text()
            queue = wf.rewrite_meta(queue, first, {'topic':'other'})
            queue = wf.rewrite_meta(queue, unrelated, {'topic':'director'})
            self.store.save(queue, self.store.load())
        self.assertEqual(wf.group_selection(wf.Store(linked), selection)['ids'], [unrelated, second])
        resumed = wf.Store(self.location(run)).load()['active_run']
        self.assertEqual(resumed['snapshot'], run['snapshot'])
        self.assertEqual(resumed['admitted_task_ids'], run['admitted_task_ids'])
        self.assertEqual(wf.Store(self.location(run)).load()['run_registry']['claims'],
                         {tid:run['id'] for tid in (first, second, dep)})
    def test_stale_group_preview_never_reserves_a_run(self):
        self.task('Originally selected root', topic='director')
        preview = wf.group_selection(self.store, {'queue':'prioritized','topic':'director'})
        self.task('New root after preview', topic='director')
        before = self.store.state.read_bytes()
        before_queue = self.store.future.read_bytes()
        locator = ws.runtime(self.root)
        with patch.object(ws, 'provision') as provision:
            with self.assertRaisesRegex(wf.WorkflowError, 'Source changed'):
                wf.start(wf.Store(self.root, allow_unselected=True), 'all', workspace={
                    'snapshot_ids':preview['ids'],
                    'expected_source_hash':preview['source_hash'],
                })
            with self.assertRaisesRegex(wf.WorkflowError, 'Resolve group filters'):
                wf.start(wf.Store(self.root, allow_unselected=True), 'all', workspace={'topic':'director'})
            provision.assert_not_called()
        self.assertEqual(self.store.state.read_bytes(), before)
        self.assertEqual(self.store.future.read_bytes(), before_queue)
        self.assertEqual(ws.runtime(self.root), locator)
    def test_missing_default_base_stops_without_a_reserved_run(self):
        tid=self.task();self.call(self.root,'push','origin',':develop');self.call(self.root,'update-ref','-d','refs/remotes/origin/develop')
        with self.assertRaises(ws.RunError):self.start(tid)
        self.assertFalse(wf.Store(self.root).load()['run_registry']['runs'])
    def test_dirty_old_workspace_never_contaminates_a_new_run(self):
        a=self.task('First');b=self.task('Second');first=self.start(a);(self.location(first)/'source.py').write_text('owned unfinished work\n');second=self.start(b)
        self.assertEqual((self.location(second)/'source.py').read_text(),'value = 1\n')
        self.assertEqual((self.location(first)/'source.py').read_text(),'owned unfinished work\n')
    def test_resume_preserves_dirty_work_budget_stop_and_failure_counters(self):
        run=self.start(self.task());store=wf.Store(self.location(run));wf.checkpoint(store,{'partial_work':['source.py'],'stop_reason':'Fixture prerequisite','validation_consumed':{'repair_used':2},'next_action':'Inspect the preserved prerequisite'})
        (store.source_root/'source.py').write_text('dirty owned source\n');again=wf.Store(store.source_root).load()['active_run']
        self.assertEqual(again['partial_work'],['source.py']);self.assertEqual(again['limits']['repair_used'],2)
        self.assertEqual(again['stop_reason'],'Fixture prerequisite');self.assertEqual(again['id'],run['id'])
    def test_missing_worktree_and_wrong_branch_require_explicit_recovery(self):
        run=self.start(self.task());path=self.location(run);self.call(path,'switch','-c','wrong-identity')
        with self.assertRaisesRegex(ws.RunError,'branch identity'):wf.next_task(wf.Store(path))
        self.call(path,'switch',run['workspace']['branch']);shutil.rmtree(path)
        with self.assertRaisesRegex(ws.RunError,'missing'):wf.next_task(wf.Store(self.root,run['id']))
    def test_queue_copy_edits_never_become_authority(self):
        tid=self.task();run=self.start(tid);path=self.location(run);(path/'.skill-tree/documents/future.md').write_text('Invalid independent queue')
        self.assertEqual(wf.next_task(wf.Store(path))['task_id'],tid);self.assertIn(tid,wf.Store(path).text())

    def test_linked_refresh_rejects_canonical_loss_and_source_drift(self):
        run = self.start(self.task())
        linked = self.location(run)
        queue_copy = linked/'.skill-tree/documents/future.md'
        queue_copy_bytes = queue_copy.read_bytes()
        canonical = self.store.future.read_bytes()
        checkpoint = self.store.state.read_bytes()
        manifest = self.store.base/'skill-tree.json'
        navigation = manifest.read_bytes()

        def refresh(*options):
            result = subprocess.run([sys.executable, '-B', str(CORE/'common/scripts/workflow-state.py'),
                                     'refresh', str(linked), '--run-id', run['id'], *options],
                                    capture_output=True, text=True, timeout=20)
            return result.returncode, json.loads(result.stdout)

        self.store.future.write_bytes(queue_copy_bytes)
        status, response = refresh()
        self.assertEqual(status, 2, response)
        self.assertIn('.skill-tree/documents/future.md', response['error'])
        self.assertEqual(self.store.future.read_bytes(), queue_copy_bytes)
        self.assertEqual(self.store.state.read_bytes(), checkpoint)
        self.assertEqual(manifest.read_bytes(), navigation)

        self.store.future.write_bytes(canonical)
        inspected = wf.file_hash(self.store.future)
        changed = canonical.replace(b'Fixed task headers.', b'Current task headers.')
        self.assertNotEqual(changed, canonical)
        self.store.future.write_bytes(changed)
        status, response = refresh('--expected-source-hash', inspected)
        self.assertEqual(status, 2, response)
        self.assertIn('changed', response['error'].lower())
        self.assertEqual(self.store.future.read_bytes(), changed)
        self.assertEqual(self.store.state.read_bytes(), checkpoint)
        self.assertEqual(manifest.read_bytes(), navigation)
        self.assertEqual(queue_copy.read_bytes(), queue_copy_bytes)
    def test_task_claim_blocks_standalone_mutation_from_another_run(self):
        a=self.task('First');b=self.task('Second');first=self.start(a);second=self.start(b)
        with self.assertRaisesRegex(wf.WorkflowError,'claimed'):wf.begin_task(wf.Store(self.location(second)),{'task_id':a})
    def test_exclusive_resource_release_requires_owner_token(self):
        a=self.task('First');b=self.task('Second');first=self.start(a);second=self.start(b);one=wf.Store(self.location(first));two=wf.Store(self.location(second))
        token=ws.resource(one,{'resource':'runtime:single-editor'})
        with self.assertRaisesRegex(ws.RunError,'already claimed'):ws.resource(two,{'resource':'runtime:single-editor'})
        with self.assertRaises(ws.RunError):ws.resource(one,{'resource':'runtime:single-editor','release':True,'token':'wrong'})
        ws.resource(one,{'resource':'runtime:single-editor','release':True,'token':token['token']});self.assertTrue(ws.resource(two,{'resource':'runtime:single-editor'}))
    def test_secret_prerequisites_do_not_copy_or_read_secret_values(self):
        run=self.start(self.task());path=self.location(run);policy=path/'.skill-tree/worktree-profile.json';policy.write_text(json.dumps({'schema':1,'required_files':['.env.local'],'exclusive_resources':['service:fixture']}))
        store=wf.Store(path)
        with self.assertRaisesRegex(ws.RunError,'Missing environment prerequisites'):ws.environment(store)
        (path/'.env.local').write_text('SECRET_TOKEN=fixture-private-value')
        inspected=ws.environment(store);self.assertFalse(inspected['secrets_read']);self.assertNotIn('fixture-private-value',json.dumps(inspected))
        with self.assertRaisesRegex(ws.RunError,'exclusive resource'):ws.environment(store,{'runtime':True})
        ws.resource(store,{'resource':'service:fixture'});ws.environment(store,{'runtime':True})
    def test_mutable_shared_directory_is_rejected(self):
        run=self.start(self.task());path=self.location(run);shared=self.base/'shared';shared.mkdir();(path/'dist').symlink_to(shared,target_is_directory=True)
        with self.assertRaisesRegex(ws.RunError,'mutable directory sharing'):ws.environment(wf.Store(path))
    def test_publication_lock_serializes_worktrees_and_recovers_without_deletion(self):
        a=self.task('First');b=self.task('Second');first=self.start(a);second=self.start(b)
        with ws.publication_lock(self.location(first),'origin','develop'):
            with self.assertRaisesRegex(ws.RunError,'Publication/merge lock'):
                with ws.publication_lock(self.location(second),'origin','develop'):pass
        with ws.publication_lock(self.location(second),'origin','develop'):pass
    def test_old_checkpoint_requires_explicit_adoption_and_preserves_record(self):
        # An independent unbound repository exercises the single-checkpoint setup boundary.
        other=self.base/'old';self.call(self.base,'clone',self.remote,other);self.call(other,'switch','main')
        docs=other/'.skill-tree/documents';state=wf.Store(other)
        tid=self.task();canonical_task=wf.resolve(wf.parse(self.store.text()),[tid])[0]
        with state.lock():text=wf.insert(state.text(),'Prioritized Next Changes',canonical_task['body']);state.save(text,state.load(text))
        with patch.object(wf.workspaces,'common_dir',return_value=None):old=wf.start(state,'next',tid,{'repair_used':3})
        with self.assertRaisesRegex(ws.RunError,'adopt_run_id'):ws.setup(state,{})
        raw=json.loads(state.state.read_text());self.assertEqual(raw['active_run']['id'],old['id'])
        # Source==base cannot be adopted as a working branch.
        self.call(other,'switch','-c','codex/adopt')
        adopted=ws.setup(state,{'adopt_run_id':old['id'],'base_branch':'main','branch':'codex/adopt','worktree':str(other)})
        preserved=adopted['runs'][old['id']];self.assertEqual(preserved['limits'],old['limits']);self.assertEqual(preserved['snapshot'],old['snapshot'])
    def test_interrupted_provision_preserves_reservation_and_claims(self):
        tid=self.task()
        with patch.object(ws,'create_reserved',side_effect=ws.RunError('Synthetic interruption')):
            with self.assertRaises(ws.RunError):self.start(tid)
        state=wf.Store(self.root).load();run=state['active_run'];self.assertEqual(run['workspace_state'],'reserved');self.assertEqual(state['run_registry']['claims'][tid],run['id'])
        with self.assertRaises(wf.WorkflowError):self.start(tid)
    def test_semantic_event_export_has_no_absolute_workspace_locator(self):
        run=self.start(self.task());store=wf.Store(self.location(run));wf.checkpoint(store,{'partial_work':['source.py']});result=wf.export_run(store);data=json.loads((store.source_root/result['path']).read_text())
        self.assertEqual(data['run_id'],run['id']);self.assertTrue(data['events']);self.assertNotIn(str(self.base),json.dumps(data));self.assertEqual(data['checkpoint']['partial_work'],['source.py'])
        for event in data['events']:
            recorded=datetime.fromisoformat(event['recorded_at'])
            self.assertEqual(recorded.utcoffset(),timedelta(0))
            path=self.store.base/'history/run-events'/run['id'].lower()/(event['id'].lower()+'.json')
            self.assertEqual(json.loads(path.read_text())['recorded_at'],event['recorded_at'])
    def test_reserved_workspace_recovery_keeps_run_id_and_original_claims(self):
        tid=self.task()
        reserved_path=self.base/'reserved-checkout'
        with patch.object(ws,'create_reserved',side_effect=ws.RunError('Synthetic interruption')):
            with self.assertRaises(ws.RunError):
                self.start(tid,worktree=str(reserved_path))
        store=wf.Store(self.root)
        run=store.load()['active_run']
        recovered=ws.recover_workspace(store,{'worktree':str(reserved_path),'resolution':'The synthetic interruption leaves no source changes.'})
        self.assertEqual(recovered['id'],run['id'])
        self.assertEqual(recovered['workspace_state'],'ready')
        self.assertEqual(wf.Store(reserved_path).load()['run_registry']['claims'][tid],run['id'])
    def test_export_replay_is_idempotent_on_the_canonical_owner(self):
        run=self.start(self.task());store=wf.Store(self.location(run));wf.checkpoint(store,{'partial_work':['source.py']});export=wf.export_run(store)
        envelope=json.loads((store.source_root/export['path']).read_text())
        first=wf.replay_events(store,envelope);second=wf.replay_events(store,envelope)
        self.assertEqual(first,second);self.assertEqual(wf.Store(self.location(run)).load()['active_run']['partial_work'],['source.py'])
        legacy=[{key:value for key,value in event.items() if key!='recorded_at'} for event in envelope['events']]
        self.assertEqual(wf.replay_events(store,{**envelope,'events':legacy}),first)
        before=self.store.state.read_bytes()
        for invalid in (None, 'malformed', '2026-11-15T10:00:00', '2026-11-15T10:00:00+01:00'):
            event={**envelope['events'][-1],'recorded_at':invalid}
            with self.subTest(recorded_at=invalid), self.assertRaisesRegex(wf.WorkflowError,'valid UTC timestamp'):
                wf.replay_events(store,{**envelope,'events':[event]})
        self.assertEqual(self.store.state.read_bytes(),before)
    def test_export_preserves_pending_check_attempts_owned_by_the_selected_run(self):
        tid=self.task();run=self.start(tid);store=wf.Store(self.location(run));wf.begin_task(store,{'task_id':tid})
        attempt=wf.prepare_check(store,{'task_id':tid,'check_id':'behavior'});export=wf.export_run(store);envelope=json.loads((store.source_root/export['path']).read_text())
        self.assertEqual(envelope['task_progress'][tid]['checks']['behavior']['attempt']['attempt_id'],attempt['attempt_id'])
        self.assertTrue(any(event.get('progress_changes') for event in envelope['events']))
        wf.replay_events(store,envelope)
        self.assertEqual(wf.Store(self.location(run)).load()['task_progress'][tid]['checks']['behavior']['attempt']['attempt_id'],attempt['attempt_id'])
    def test_event_task_conflict_rolls_back_all_queue_changes(self):
        run=self.start(self.task());store=wf.Store(self.location(run));registry=store.load()['run_registry'];text=store.text()
        task=wf.resolve(wf.parse(text),[run['root_task_id']])[0]
        event={'schema':1,'id':wf.identity('E'),'queue_id':registry['queue_id'],'run_id':run['id'],'changes':[{'task_id':task['id'],'before':{'queue':task['queue'],'body':'Conflicting prior definition'},'after':None}],'outcomes':[],'checkpoint_before':run,'checkpoint_after':run}
        with self.assertRaisesRegex(wf.WorkflowError,'canonical task'):wf.replay_events(store,{'schema':1,'queue_id':registry['queue_id'],'run_id':run['id'],'events':[event]})
        self.assertEqual(store.text(),text)
    def test_git_preflight_uses_the_current_remote_target_and_preserves_dirty_source(self):
        spec=importlib.util.spec_from_file_location('workspace_pr',CORE/'common/scripts/pr-review-state.py');pr=importlib.util.module_from_spec(spec);spec.loader.exec_module(pr)
        run=self.start(self.task());path=self.location(run)
        with self.assertRaisesRegex(pr.ReviewError,'No changes'):pr.preflight(path,{})
        (path/'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(pr.ReviewError,'Dirty worktree'):pr.preflight(path,{})
        self.call(path,'add','source.py');self.call(path,'commit','-m','Fixture scoped fix')
        context=pr.preflight(path,{'target_branch':'release/example'})
        self.assertEqual(context['source_branch'],run['workspace']['branch']);self.assertEqual(context['target_branch'],'release/example');self.assertEqual(context['changed_files'],['source.py'])
    def finish_run(self,run):
        store=wf.Store(self.location(run));tid=run['root_task_id'];wf.begin_task(store,{'task_id':tid})
        (store.source_root/'report.json').write_text('{"assertion":"scoped fixture passed"}')
        attempt=wf.prepare_check(store,{'task_id':tid,'check_id':'behavior'})
        wf.record_check(store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','classification':'executed-control','actual_lane':'static','environment_identity':attempt['environment_identity'],'assertions':[{'assertion':'Preserve scoped source behavior.','result':'pass'}],'cleanup':'The fixture starts no product process.','evidence':['report.json']})
        wf.mark_implemented(store,{'task_id':tid});wf.complete(store,{'task_id':tid,'outcome':'Scoped source behavior remains intact.','acceptance':[{'criterion':'Preserve scoped source behavior.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(store,['source.py'])})
        return wf.finish(store)
    def test_finish_preserves_implementation_acceptance_and_local_handoff(self):
        run=self.start(self.task());result=self.finish_run(run)
        self.assertEqual(result['delivery']['implementation'],'completed');self.assertEqual(result['delivery']['status'],'local-result');self.assertTrue(result['delivery']['order_completed'])
        state=wf.Store(self.root,allow_unselected=True).load();self.assertEqual(state['run_registry']['claims'],{});self.assertEqual(len(wf.Store(self.root).outcomes()),1)
        history=wf.history(wf.Store(self.root,allow_unselected=True));self.assertTrue(history[0]['acceptance'][0]['evidence'][0]['available'])
    def test_promised_merge_stays_open_after_implementation_acceptance(self):
        run=self.start(self.task(),delivery_authorization={'pr':True,'merge':True,'source':'Explicit synthetic owner full-path instruction'})
        result=self.finish_run(run);self.assertFalse(result['delivery']['order_completed']);self.assertEqual(result['delivery']['status'],'implementation-completed')
        self.assertEqual(wf.Store(self.root).load()['active_run']['id'],run['id'])
    def test_completed_dependency_from_another_run_requires_source_integration(self):
        dependency=self.task('Dependency');first=self.start(dependency);(self.location(first)/'source.py').write_text('value = 2\n');self.finish_run(first)
        consumer=self.task('Consumer',[dependency]);second=self.start(consumer);store=wf.Store(self.location(second))
        with self.assertRaisesRegex(wf.WorkflowError,'source integration'):wf.begin_task(store,{'task_id':consumer})
        (store.source_root/'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(wf.WorkflowError,'source integration'):
            wf.begin_task(store,{'task_id':consumer})
        (store.source_root/'report.json').write_bytes((self.location(first)/'report.json').read_bytes())
        self.assertEqual(wf.begin_task(store,{'task_id':consumer})['phase'],'implement')
    def test_portable_execution_path_references_require_explicit_recovery(self):
        original={'session':{'project_root':str(self.root/'src'),'external_root':'/external/fixture','remote_url':'git@fixture-local-alias:owner/repo.git'}}
        portable=ws.portable_envelope(original,self.root,self.base);self.assertNotIn('/external/fixture',json.dumps(portable));key=portable['local_path_references'][0];value_key=portable['local_value_references'][0];self.assertNotIn('fixture-local-alias',json.dumps(portable))
        with self.assertRaises(ws.RunError):ws.restore_envelope(portable,self.root,self.base)
        recovered=ws.restore_envelope(portable,self.root,self.base,{key:'/external/fixture',value_key:'git@fixture-local-alias:owner/repo.git'});self.assertEqual(recovered['session'],original['session'])
    def test_unfinished_git_operation_stops_resume(self):
        run=self.start(self.task());path=self.location(run);head=Path(self.call(path,'rev-parse','--git-path','MERGE_HEAD'));head.write_text(self.call(path,'rev-parse','HEAD'))
        with self.assertRaisesRegex(ws.RunError,'Unfinished Git operation'):wf.next_task(wf.Store(path))
    def test_changed_remote_identity_stops_resume(self):
        run=self.start(self.task());self.call(self.root,'remote','set-url','origin',str(self.base/'other.git'))
        with self.assertRaisesRegex(ws.RunError,'Remote identity'):wf.next_task(wf.Store(self.location(run)))
    def test_unrelated_queue_updates_survive_run_mutation(self):
        run=self.start(self.task());other=self.task('Unrelated');wf.checkpoint(wf.Store(self.location(run)),{'partial_work':['source.py']})
        self.assertIn(other,{t['id'] for t in wf.parse(self.store.text())})

    def partial_finish_fixture(self, accepted_count=20, total=35):
        tasks = [self.task('Partial snapshot task '+str(i+1)) for i in range(total)]
        run = wf.start(wf.Store(self.root, neutral=True), 'all', workspace={
            'implementation_operation':'implement-all', 'snapshot_ids': tasks})
        source = self.location(run)
        selected = wf.Store(self.root, run['id'])
        checkout = ws.checked_out_branch(source)
        accepted_rows = []
        with (ws.common_dir(self.root)/'info/exclude').open('a') as output:
            output.write('\npartial-observation.log\n')
        artifact = source/'partial-observation.log'
        artifact.write_text('Original noncommitted check artifact.\n')
        chosen = run['snapshot'][:accepted_count]
        for seq, tid in enumerate(chosen, 1):
            (source/'source.py').write_text('value = '+str(seq+1)+'\n')
            self.call(source,'add','source.py')
            self.call(source,'commit','-m','Accepted fixture task '+tid)
            commit = self.call(source,'rev-parse','HEAD')
            parent = self.call(source,'rev-parse','HEAD^')
            tree = self.call(source,'rev-parse','HEAD^{tree}')
            row = {'id':wf.identity('O'), 'run_id':run['id'], 'task_id':tid,
                   'disposition':'completed', 'title':'Accepted fixture task',
                   'evidence':[{'path':artifact.name,'sha256':wf.file_hash(artifact)}],
                   'task_git_commit': {'commit':commit,'parent':parent,'tree':tree,
                                       'checkout':checkout['checkout'],'ref':checkout['ref']}}
            accepted_rows.append(row)
            with selected.lock():
                text = selected.text()
                state = selected.load(text)
                task, = wf.resolve(wf.parse(text), [tid], 'Prioritized Next Changes')
                row['task_context'] = {'content_fingerprint':wf.digest(task['body'].encode())}
                state['active_run']['completed_ids'].append(tid)
                state['active_run'].setdefault('completion_refs', {})[tid] = row['id']
                selected.save(wf.remove(text,{tid}),state,{wf.OUTCOME_LEDGER:''.join(wf.dump(item).replace('\n', '')+'\n' for item in accepted_rows)})
        with selected.lock():
            state = selected.load()
            state['active_run'].update(phase='stopped',stop_reason='Owner paused the partial fixture.',
                                       profile_refresh_required=True)
            selected.save(selected.text(), state)
        return selected, source, run['snapshot'][accepted_count:]

    def test_partial_finish_keeps_twenty_outcomes_and_releases_only_selected_claims(self):
        selected, source, remaining = self.partial_finish_fixture()
        sibling_task = self.task('Sibling retained task')
        sibling = self.start(sibling_task,worktree=str(self.base/'sibling'))
        sibling_store = wf.Store(self.root,sibling['id'])
        lease = ws.resource(sibling_store, {'resource':'memory:sibling'})
        old_queue = selected.future.read_bytes()
        old_ledger = selected.owned(wf.OUTCOME_LEDGER).read_bytes()
        old_head = self.call(source, 'rev-parse', 'HEAD')
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id), 'partial-finish-preview', {})
        self.assertEqual(preview['preview']['remaining_ids'], remaining)
        original = json.loads(selected.state.read_bytes())['run_registry']['runs'][selected.run_id]
        self.assertEqual(preview['preview']['snapshot'], original['snapshot'])
        self.assertEqual(preview['preview']['required_ids'], original['required_ids'])
        self.assertEqual(len(preview['preview']['accepted']), 20)
        self.assertFalse(preview['preview']['requires_preservation'])
        request = {'expected_preview_sha256':preview['preview_sha256'],
                   'owner_instruction':'Close the exact partial fixture.'}
        closed = wf.partial_finish(wf.Store(self.root, selected.run_id), 'partial-finish', request)
        self.assertEqual(closed['status'], 'partially-completed')
        self.assertTrue(closed['checkpoint']['profile_refresh_required'])
        self.assertEqual(closed, wf.partial_finish(wf.Store(self.root, selected.run_id), 'partial-finish', request))
        with self.assertRaisesRegex(wf.WorkflowError,'original partial finish'):
            wf.partial_finish(wf.Store(self.root, selected.run_id), 'partial-finish', {**request,'owner_instruction':'Changed request.'})
        self.assertEqual(selected.future.read_bytes(), old_queue)
        self.assertEqual(selected.owned(wf.OUTCOME_LEDGER).read_bytes(), old_ledger)
        self.assertEqual(self.call(source, 'rev-parse', 'HEAD'), old_head)
        registry = json.loads(selected.state.read_bytes())['run_registry']
        self.assertEqual(registry['claims'], {sibling_task:sibling['id']})
        self.assertEqual(registry['resources'], {'memory:sibling':lease})
        self.assertIn(selected.run_id, registry['archived_runs'])
        self.assertNotIn(selected.run_id, ws.runtime(self.root)['worktrees'])
        locator = ws.runtime(self.root)
        locator.pop('archived_worktrees')
        ws.atomic(ws.runtime_file(self.root), locator)
        first = closed['preview']['accepted'][0]['task_id']
        self.assertTrue(wf.history(wf.Store(self.root, neutral=True), first)[0]['evidence'][0]['available'])
        (source/'partial-observation.log').write_text('Changed fixture evidence.\n')
        self.assertFalse(wf.history(wf.Store(self.root, neutral=True), first)[0]['evidence'][0]['available'])
        with self.assertRaisesRegex(ws.RunError,'Unknown run ID|partially closed'):
            selected.load()
        fresh = self.start(remaining[0],worktree=str(self.base/'fresh'))
        self.assertEqual(wf.Store(self.root,fresh['id']).load()['active_run']['id'],fresh['id'])

    def test_partial_finish_retries_original_fenced_transaction_after_locator_retirement(self):
        selected, source, _ = self.partial_finish_fixture(2, 3)
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id), 'partial-finish-preview', {})
        request = {'expected_preview_sha256':preview['preview_sha256'],
                   'owner_instruction':'Close after interrupted locator retirement.'}
        retire = wf.partial_retire_locator
        def lose_response(store, journal):
            retire(store, journal)
            raise OSError('Injected loss after archive locator transition')
        with patch.object(wf,'partial_retire_locator',side_effect=lose_response):
            with self.assertRaisesRegex(OSError,'Injected loss'):
                wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',request)
        self.assertNotIn(selected.run_id, ws.runtime(self.root)['worktrees'])
        with self.assertRaisesRegex(wf.WorkflowError,'exact original local delivery'):
            wf.checkpoint(selected, {'next_action':'Retained writer attempt'})
        with self.assertRaisesRegex(wf.WorkflowError,'exact original local delivery'):
            ws.recover_locator(wf.Store(self.root, neutral=True), {})
        changed = source/'unaccepted-after-interruption.txt'
        changed.write_text('Late bytes must leave the exact recovery held.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence changed'):
            wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',request)
        changed.unlink()
        marker = ws.linked_registration(self.root,source)/'skill-tree-owner.json'
        original_marker = marker.read_bytes()
        marker.unlink()
        with self.assertRaises(ws.RunError):
            wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',request)
        marker.write_bytes(original_marker)
        result = wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',request)
        self.assertEqual(result['status'],'partially-completed')
        self.assertFalse((selected.base/'.transaction.json').exists())

    def test_partial_finish_holds_scoped_lease_and_binds_unaccepted_changes(self):
        selected, source, _ = self.partial_finish_fixture(2, 3)
        key = 'memory:partial'
        lease = ws.resource(selected, {'resource':key})
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish-preview',{})
        self.assertEqual(preview['status'],'blocked')
        self.assertIn({'kind':'original-resource','resource':key},preview['preview']['blockers'])
        ws.resource(selected, {'resource':key,'release':True,'token':lease['token']})
        accepted = preview['preview']['accepted'][0]['task_id']
        worker = self.root/'.skill-tree/history/worker-handoffs'/(selected.run_id.lower()+'.json')
        worker.parent.mkdir(parents=True, exist_ok=True)
        worker.write_text(wf.dump({'schema':1,'run_id':selected.run_id,'slots':{'1':[{'task_id':accepted}]}}))
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish-preview',{})
        self.assertIn({'kind':'original-worker','task_id':accepted},preview['preview']['blockers'])
        worker.unlink()
        unaccepted = source/'unfinished.txt'
        unaccepted.write_text('Preserve original unfinished bytes.\n')
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish-preview',{})
        request = {'expected_preview_sha256':preview['preview_sha256'],
                   'owner_instruction':'Close while preserving unaccepted work.'}
        with self.assertRaisesRegex(wf.WorkflowError,'explicit preservation'):
            wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',request)
        unaccepted.write_text('Preserve changed unfinished bytes.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'preview changed'):
            wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',{**request,'preserve_unaccepted':True})
        preview = wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish-preview',{})
        request['expected_preview_sha256'] = preview['preview_sha256']
        wf.partial_finish(wf.Store(self.root, selected.run_id),'partial-finish',{**request,'preserve_unaccepted':True})
        self.assertEqual(unaccepted.read_text(),'Preserve changed unfinished bytes.\n')


if __name__=='__main__':unittest.main()
