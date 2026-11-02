import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('isolated_wf',CORE/'common/scripts/workflow-state.py');wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)

class IsolatedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name).resolve()
        self.root=base/'queue';self.workspace=base/'workspace';self.execution=self.workspace/'scratch/pilot'
        for root in [self.root,self.execution]:
            self.write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2')
            self.write(root,'Packages/manifest.json',{'dependencies':{'com.unity.test-framework':'1.6.0'}})
            self.write(root,'Packages/packages-lock.json',{'dependencies':{'com.unity.test-framework':{'version':'1.6.0'},'com.unity.pipeline':{'version':'0.7.0-exp.1'}}})
            self.write(root,'Assets/main.cs','same source')
        self.write(self.execution,'Assets/fixture.cs','fixture')
        self.write(self.workspace,'scripts/runner.py','raise RuntimeError("No execution")')
        self.binding={'locator':'.skill-tree/local/pilot.json','execution_subdir':'scratch/pilot','source_paths':['Assets','Packages','ProjectSettings'],'workspace_paths':['scripts/runner.py'],'review_path':'.skill-tree/validation/review.json','pins':{'editor_version':'6000.3.27f2','cli_version':'1.0.0-beta.10','pipeline_version':'0.7.0-exp.1','utf_version':'1.6.0'}}
        self.write(self.root,self.binding['locator'],{'schema':1,'queue_root':str(self.root),'workspace_root':str(self.workspace)})
        self.write(self.root,self.binding['review_path'],{'schema':1,'queue_digest':wf.binding_snapshot(self.root,self.binding['source_paths']),'execution_digest':wf.binding_snapshot(self.execution,self.binding['source_paths']),'workspace_digest':wf.binding_snapshot(self.workspace,self.binding['workspace_paths']),'differences':[{'path':'Assets/fixture.cs','queue':None,'execution':wf.file_hash(self.execution/'Assets/fixture.cs'),'classification':'fixture','reason':'Offline fixture source.'}]})
        self.recipe={'lane':'unity-playmode','execution_binding':'pilot','editor_version':'6000.3.27f2','argv':['python3','{binding_workspace}/scripts/runner.py','--project','{project_root}','--queue','{queue_root}'],'input_paths':[]}
        self.write(self.root,'.skill-tree/validation-recipes.json',{'schema':1,'execution_bindings':{'pilot':self.binding},'recipes':{'isolated':self.recipe}})
        script="const c=require(process.argv[1]);process.stdout.write(JSON.stringify(c.resolveProfile(process.argv[2],process.argv[3],'unity')));"
        result=subprocess.run(['node','-e',script,str(CORE/'lib/composer.js'),str(CORE),str(self.root)],capture_output=True,text=True,timeout=30,check=True)
        self.profile=json.loads(result.stdout);self.profile['identity']='fixture-profile';self.write(self.root,'.skill-tree/installation/profile.json',self.profile);self.store=wf.Store(self.root)
        self.check={'id':'test','recipe_id':'isolated','parameters':{'project_root':'/wrong','execution_checkout':str(self.execution)},'sources':['Assets/main.cs'],'assertion':'A named isolated assertion passes.'}
    def write(self,root,relative,value):
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value if isinstance(value,str) else json.dumps(value));return path
    def test_cross_language_snapshots_and_reserved_roots_match(self):
        recipe,_=wf.recipe_for(self.store,self.check)
        self.assertEqual(recipe['argv'][-3:], [str(self.execution),'--queue',str(self.root)])
        self.assertEqual(recipe['execution_context']['execution_digest'],wf.binding_snapshot(self.execution,self.binding['source_paths']))
        self.check['parameters']['execution_checkout']=str(self.root)
        with self.assertRaisesRegex(wf.WorkflowError,'Check checkout'):wf.recipe_for(self.store,self.check)
    def test_changed_sources_locator_runner_and_review_are_rejected(self):
        cases=[(self.execution,'Assets/fixture.cs'),(self.root,'Assets/main.cs'),(self.workspace,'scripts/runner.py'),(self.root,self.binding['review_path']),(self.root,self.binding['locator'])]
        for root,relative in cases:
            with self.subTest(relative=relative,root=root):
                path=root/relative;before=path.read_bytes();path.write_bytes(before+b' ')
                with self.assertRaises(wf.WorkflowError):wf.recipe_for(self.store,self.check)
                path.write_bytes(before)
    def test_product_session_requires_matching_binding_toolchain_source_and_isolation(self):
        recipe,env=wf.recipe_for(self.store,self.check);self.write(self.root,'identity.json',{'checkout':str(self.execution)})
        session={'project_root':str(self.execution),'queue_root':str(self.root),'binding_id':'pilot','source_identity':recipe['execution_context']['execution_digest'],'authorization':'owner exact scoped request','profile_id':'reviewed-profile','deadline_utc':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),'cleanup_seconds':5,'tool_identity':{'cli_version':'1.0.0-beta.10','pipeline_version':'0.7.0-exp.1'},'session_identity':'owned-process','fixture_identity':'isolated-fixture','build_identity':'compiled-source','identity_evidence':['identity.json'],'editor_version':'6000.3.27f2','save_service_isolation':'verified'}
        wf.execution_session(self.store,recipe,env,{},session,True)
        for key,value in [('project_root',str(self.root)),('queue_root','/wrong'),('source_identity','changed'),('editor_version','6000.0.83f1'),('save_service_isolation',None),('tool_identity',{'cli_version':'1.0.0-beta.14','pipeline_version':'0.7.0-exp.1'})]:
            invalid={**session,key:value}
            with self.subTest(key=key),self.assertRaises(wf.WorkflowError):wf.execution_session(self.store,recipe,env,{},invalid,True)
    def test_source_blockers_never_become_product_passes_and_symlinks_fail(self):
        self.profile['execution_bindings']['pilot']['blockers']=['Assets/fixture.cs'];self.write(self.root,'.skill-tree/installation/profile.json',self.profile)
        with self.assertRaisesRegex(wf.WorkflowError,'unqualified'):wf.recipe_for(self.store,self.check)
        self.assertEqual(wf.binding_context(self.store,self.recipe,True)['blockers'],['Assets/fixture.cs'])
        (self.execution/'Assets/link.cs').symlink_to(self.execution/'Assets/main.cs')
        with self.assertRaisesRegex(wf.WorkflowError,'symlink'):wf.binding_context(self.store,self.recipe,True)

    def prepare_bound_task(self):
        self.store.future.parent.mkdir(parents=True,exist_ok=True);self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        p=wf.intake(self.store,{'title':'Synthetic bound check','description':'Verify source-bound receipt behavior.','expected_behavior':'Reject stale source.'})
        check={**self.check,'criteria':['Reject stale source.'],'timing':'immediate'}
        body='Goal:\n- Reject stale source.\n\nTouch:\n- Assets/main.cs\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Reject stale source.\n'
        tid=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Synthetic source fixture supplies the oracle.'}},'tasks':[{'title':'Synthetic bound check','body':body,'parent_pending_ids':[p['id']]}]})['created_ids'][0]
        with patch.object(wf,'admit_profile',return_value={'identity':'fixture-profile'}):wf.begin_task(self.store,{'task_id':tid})
        self.write(self.root,'identity.json',{})
        session={'project_root':str(self.execution),'queue_root':str(self.root),'binding_id':'pilot','source_identity':wf.binding_snapshot(self.execution,self.binding['source_paths']),'authorization':'synthetic fixture only','profile_id':'fixture','deadline_utc':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),'cleanup_seconds':5,'tool_identity':{'cli_version':'1.0.0-beta.10','pipeline_version':'0.7.0-exp.1'},'session_identity':'synthetic-process','fixture_identity':'synthetic-fixture','build_identity':'synthetic-build','identity_evidence':['identity.json'],'editor_version':'6000.3.27f2','save_service_isolation':'synthetic fixture only'}
        return tid,session

    def test_bound_prepared_receipt_rejects_external_fixture_mutation(self):
        tid,session=self.prepare_bound_task();attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'test','execution':session})
        (self.execution/'Assets/fixture.cs').write_text('changed fixture')
        with self.assertRaisesRegex(wf.WorkflowError,'source identity changed'):
            wf.record_check(self.store,{'task_id':tid,'check_id':'test','attempt_id':attempt['attempt_id'],'result':'pass','classification':'executed-control','actual_lane':'unity-playmode','environment_identity':attempt['environment_identity'],'cleanup':'Synthetic fixture only.'})

    def test_bound_launch_requires_execution_root_and_retains_the_original_attempt(self):
        tid,session=self.prepare_bound_task();launch={'assertion':'A named isolated assertion passes.','cheaper_evidence_insufficient':'Synthetic launch-root fixture verifies the product session boundary.','authorization':'synthetic fixture only','deadline_utc':session['deadline_utc'],'cleanup_seconds':5,'project_root':str(self.root),'execution_profile':'synthetic-only'}
        with self.assertRaisesRegex(wf.WorkflowError,'Launch checkout'):
            wf.prepare_check(self.store,{'task_id':tid,'check_id':'test','execution':session,'launch':launch})
        launch['project_root']=str(self.execution)
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'test','execution':session,'launch':launch})
        self.assertEqual(attempt['launch']['project_root'],str(self.execution))
        with self.assertRaisesRegex(wf.WorkflowError,'original pending'):
            wf.prepare_check(self.store,{'task_id':tid,'check_id':'test','execution':session,'launch':launch})

class MaintenanceScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True);self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        (self.root/'source.py').write_text('value=1');(self.root/'report.json').write_text('{}')
        config=self.store.base/'config';config.mkdir();(config/'repository.json').write_text(json.dumps({'role':'source'}))
        self.root_id=self.task('Parked game controller')
        wf.start(self.store,'next',self.root_id)
        self.child=self.task('Bounded infrastructure',self.root_id)
        wf.checkpoint(self.store,{'phase':'blocked-host-prerequisite','stop_reason':'Preserved host prerequisite','next_action':'Remain stopped.','partial_work':['Retained game evidence.']})
        self.before=copy.deepcopy(self.store.load()['active_run'])
    def task(self,title,parent=None):
        intake={'title':title,'description':'Preserve scoped behavior.','expected_behavior':'Preserve the value.'}
        if parent:intake.update({'root_task_id':self.root_id,'related_task_id':parent,'relation':'blocker'})
        p=wf.intake(self.store,intake)
        check={'id':'static','recipe_id':'static-inspection','criteria':['Preserve the value.'],'sources':['source.py'],'parameters':{},'assertion':'The value remains preserved.','timing':'immediate'}
        body='Goal:\n- Preserve the value.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Preserve the value.\n'
        return wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Source research confirms the contract.'}},'tasks':[{'title':title,'body':body,'parent_pending_ids':[p['id']]}]})['created_ids'][0]
    def focus(self):return wf.focus_maintenance(self.store,{'task_id':self.child,'instruction':'Owner requests only infrastructure; game execution remains stopped.'})
    def test_focus_completes_exact_unit_without_resuming_or_replacing_parked_controller(self):
        self.focus();self.assertEqual(wf.advance(self.store)['task_id'],self.child)
        wf.begin_task(self.store,{'task_id':self.child});wf.mark_implemented(self.store,{'task_id':self.child})
        attempt=wf.prepare_check(self.store,{'task_id':self.child,'check_id':'static'})
        wf.record_check(self.store,{'task_id':self.child,'check_id':'static','attempt_id':attempt['attempt_id'],'result':'pass','classification':'executed-control','actual_lane':'static','environment_identity':attempt['environment_identity'],'assertions':[{'assertion':'The value remains preserved.','result':'pass'}],'evidence':['report.json'],'cleanup':'No product process was launched.'})
        wf.complete(self.store,{'task_id':self.child,'outcome':'The value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        wf.finish(self.store);after=self.store.load()['active_run']
        for key in ['id','root_task_id','current_task_id','phase','stop_reason','next_action','partial_work','admission','limits']:self.assertEqual(after[key],self.before[key],key)
        self.assertIn(self.child,after['completed_ids']);self.assertNotIn('maintenance',after)
        with self.assertRaisesRegex(wf.WorkflowError,'Run stopped'):wf.next_task(self.store)
    def test_focus_cannot_select_another_task_or_expand_into_product_checks(self):
        self.focus()
        with self.assertRaises(wf.WorkflowError):wf.begin_task(self.store,{'task_id':self.root_id})
        text=self.store.text().replace('static-inspection','unity-playmode');self.store.future.write_text(text)
        with self.assertRaises(wf.WorkflowError):wf.begin_task(self.store,{'task_id':self.child})
    def test_failure_and_policy_stop_remain_inside_maintenance_scope(self):
        self.focus();wf.begin_task(self.store,{'task_id':self.child});a=wf.prepare_check(self.store,{'task_id':self.child,'check_id':'static'})
        wf.record_check(self.store,{'task_id':self.child,'check_id':'static','attempt_id':a['attempt_id'],'result':'unavailable','classification':'host-policy-rejection','actual_lane':'static','environment_identity':a['environment_identity'],'cleanup':'No process started.','reason':'Unavailable infrastructure scope.'})
        after=self.store.load()['active_run'];self.assertEqual(after['stop_reason'],self.before['stop_reason']);self.assertIn('Host policy',after['maintenance']['stop_reason'])
        with self.assertRaises(wf.WorkflowError):wf.advance(self.store)
        wf.resume_task(self.store,{'task_id':self.child,'resolution':'The owner supplies the missing non-product scope; product execution remains stopped.'})
        self.assertEqual(wf.advance(self.store)['task_id'],self.child)
        self.assertEqual(self.store.load()['active_run']['stop_reason'],self.before['stop_reason'])

if __name__=='__main__':unittest.main()
