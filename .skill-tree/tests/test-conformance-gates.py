import importlib.util
import json
from pathlib import Path
from datetime import datetime,timezone,timedelta
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
def load(name,rel):
    spec=importlib.util.spec_from_file_location(name,CORE/rel);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
fixture=load('conformance_fixture','tests/test-validation-progress.py');wf=fixture.wf

class ConformanceGateTests(unittest.TestCase):
    setUp=fixture.ValidationProgressTests.setUp
    task=fixture.ValidationProgressTests.task
    progress=fixture.ValidationProgressTests.progress
    passed=fixture.ValidationProgressTests.passed
    def edit_plan(self,tid,transform):
        task=wf.resolve(wf.parse(self.store.text()),[tid])[0];body=task['body'];start=body.index('```json\n')+8;end=body.index('\n```',start);plan=json.loads(body[start:end]);transform(plan)
        self.store.future.write_text(self.store.text().replace(body,body[:start]+json.dumps(plan)+body[end:]))
    def set_root(self,tid):
        state=self.store.load();state['active_run']['root_task_id']=tid
        with self.store.lock():self.store.save(self.store.text(),state)
    def test_scheduler_does_not_batch_beyond_a_stale_immediate_check(self):
        group=wf.identity('VG');a=self.task('First',group);b=self.task('Second',group,timing='group-end')
        self.edit_plan(a,lambda p:p['checks'].append({**p['checks'][0],'id':'boundary','timing':'group-end'}))
        wf.start(self.store,'all');self.set_root(a);self.progress(a);self.passed(a);(self.root/'source.py').write_text('value = 2\n')
        result=wf.next_task(self.store);self.assertEqual(result['phase'],'validate');self.assertEqual(result['task_id'],a)
    def test_check_reuse_preserves_a_pass_while_another_check_is_pending(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end')
        self.edit_plan(a,lambda p:p['checks'].append({**p['checks'][0],'id':'unrelated'}));wf.start(self.store,'all');self.progress(a);self.progress(b);self.passed(a)
        reused=wf.reuse_check(self.store,{'from_task_id':a,'from_check_id':'behavior','task_id':b,'check_id':'behavior'});self.assertEqual(reused['result'],'pass')
    def test_processing_unrelated_intake_cannot_launder_an_unadmitted_dependency(self):
        a=self.task('Root');b=self.task('Unrelated');wf.start(self.store,'next',a);self.store.future.write_text(wf.rewrite_meta(self.store.text(),a,{'depends_on':[b]}))
        p=wf.intake(self.store,{'title':'Separate research','description':'Inspect separate documentation.','expected_behavior':'Clarify a separate scope.'});before=self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'admitted|scope'):
            wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'resolved','reason':'The separate question is resolved.'}},'tasks':[]})
        self.assertEqual(before,self.store.future.read_bytes());self.assertNotIn(b,self.store.load()['active_run']['admitted_task_ids'])
    def unit(self):
        tid=self.task();self.store.future.write_text(self.store.text().replace('static-inspection','fixture-unit'))
        (self.store.base/'config/repository.json').write_text(json.dumps({'schema':1,'role':'source','recipes':{'fixture-unit':{'lane':'unit','argv':['fixture'],'input_paths':[]}}}));self.progress(tid);return tid
    def result(self,tid,result='pass'):
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});red=result=='red'
        payload={'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':result,'classification':'executed-control','actual_lane':'unit','environment_identity':attempt['environment_identity'],'counts':{'expected':1,'discovered':1,'passed':0 if red else 1,'failed':1 if red else 0,'skipped':0},'failure_category':'expected-behavior','cleanup':'The fixture stopped.','evidence':['report.json']}
        return payload,wf.record_check(self.store,payload)
    def test_new_red_does_not_leave_a_previous_green_usable(self):
        tid=self.unit();self.result(tid);self.result(tid,'red')
        with self.assertRaises(wf.WorkflowError):wf.validate_task_checks(self.store,tid)
    def test_original_check_receipt_is_idempotent_and_conflicting_replay_is_refused(self):
        tid=self.unit();payload,record=self.result(tid);again=wf.record_check(self.store,payload);self.assertEqual(record,again)
        wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});self.assertEqual(wf.record_check(self.store,payload),record)
        payload['result']='red';payload['counts'].update({'passed':0,'failed':1})
        with self.assertRaisesRegex(wf.WorkflowError,'receipt|conflict'):wf.record_check(self.store,payload)
    def test_a_prepared_check_cannot_be_replaced_before_the_original_receipt(self):
        tid=self.unit();wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        with self.assertRaisesRegex(wf.WorkflowError,'original|pending'):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
    def test_completed_standalone_work_cannot_mutate_an_unrelated_controller(self):
        a=self.task('Standalone');self.progress(a);self.passed(a);b=self.task('Controller');wf.start(self.store,'next',b)
        with self.assertRaisesRegex(wf.WorkflowError,'scope'):
            wf.complete(self.store,{'task_id':a,'outcome':'The value remains observable.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
    def test_changed_receipt_identity_invalidates_the_cached_controller_admission(self):
        tid=self.task();profile=self.store.base/'installation/profile.json';profile.parent.mkdir();profile.write_text(json.dumps({'identity':'old','recipes':{},'inputs':{}}))
        with patch.object(wf,'admit_profile',return_value={'identity':'old'}):wf.start(self.store,'next')
        profile.write_text(json.dumps({'identity':'new','recipes':{},'inputs':{}}))
        with self.assertRaisesRegex(wf.WorkflowError,'admission|profile'):wf.begin_task(self.store,{'task_id':tid})

    def test_product_lane_requires_an_owned_execution_session_without_a_new_launch(self):
        tid=self.task();self.store.future.write_text(self.store.text().replace('static-inspection','browser-fixture'))
        (self.store.base/'config/repository.json').write_text(json.dumps({'role':'source','schema':1,'recipes':{'browser-fixture':{'lane':'browser','argv':['controlled-fixture'],'input_paths':[]}}}));self.progress(tid)
        with self.assertRaisesRegex(wf.WorkflowError,'execution|session'):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
    def test_immediate_behavior_tests_cannot_be_moved_to_a_group_boundary(self):
        tid=self.unit();self.store.future.write_text(wf.rewrite_meta(self.store.text(),tid,{'boundary_validation':'group-end'}));self.edit_plan(tid,lambda p:p['checks'][0].update({'timing':'group-end'}))
        with self.assertRaisesRegex(wf.WorkflowError,'immediate|focused'):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})

    def test_owned_product_session_reuses_identity_and_keeps_evidence_after_the_operation_deadline(self):
        tid=self.task();self.store.future.write_text(self.store.text().replace('static-inspection','browser-fixture'))
        (self.store.base/'config/repository.json').write_text(json.dumps({'role':'source','schema':1,'recipes':{'browser-fixture':{'lane':'browser','argv':['controlled-fixture'],'input_paths':[]}}}));self.progress(tid)
        execution={'project_root':str(self.root),'authorization':'Synthetic source fixture only','profile_id':'fixture-profile','deadline_utc':(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat(),'cleanup_seconds':5,'tool_identity':{'name':'mock-browser','version':'1'},'session_identity':'fixture-session','fixture_identity':'isolated-source-control','build_identity':'fixture-build','identity_evidence':['report.json']}
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior','execution':execution})
        wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'browser','environment_identity':attempt['environment_identity'],'classification':'executed-control','counts':{'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0},'evidence':['report.json'],'cleanup':'No browser was launched; the session is synthetic.'})
        state=self.store.load();entry=state['task_progress'][tid];session=next(iter(entry['execution_sessions'].values()));session['deadline_utc']='2020-01-01T00:00:00+00:00'
        with self.store.lock():self.store.save(self.store.text(),state)
        wf.validate_task_checks(self.store,tid)
        with self.assertRaisesRegex(wf.WorkflowError,'deadline'):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})

    def test_workflow_mutation_waits_for_the_installation_lock(self):
        install=self.store.base/'installation';install.mkdir();(install/'.install-lock').write_text('synthetic-owner')
        before=self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'Installation lock'):wf.intake(self.store,{'title':'New task','description':'Inspect the scope.','expected_behavior':'Preserve the profile transaction.'})
        self.assertEqual(self.store.future.read_bytes(),before)

    def test_profile_recipe_parameters_resolve_to_concrete_argument_vectors(self):
        tid=self.task();self.store.future.write_text(self.store.text().replace('static-inspection','focused-fixture'))
        (self.store.base/'config/repository.json').write_text(json.dumps({'role':'source','schema':1,'recipes':{'focused-fixture':{'lane':'unit','argv':['fixture','--root','{project_root}','--case','{case}'],'input_paths':[]}}}));self.progress(tid)
        with self.assertRaisesRegex(wf.WorkflowError,'parameters'):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        self.edit_plan(tid,lambda plan:plan['checks'][0]['parameters'].update({'case':'two words; literal argument'}))
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});self.assertEqual(attempt['recipe']['argv'],['fixture','--root',str(self.root.resolve()),'--case','two words; literal argument'])

    def finish_task(self,tid):
        self.progress(tid);self.passed(tid)
        return wf.complete(self.store,{'task_id':tid,'outcome':'The value remains observable.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
    def test_finish_refuses_stale_completed_checks_and_revalidation_never_reimplements_or_duplicates_history(self):
        tid=self.task();wf.start(self.store,'next');self.finish_task(tid);ledger=(self.store.base/'history/task-outcomes.jsonl').read_bytes();(self.root/'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(wf.WorkflowError,'stale|unavailable'):wf.finish(self.store)
        self.assertEqual(wf.next_task(self.store)['phase'],'validate');self.passed(tid);wf.accept_revalidation(self.store,{'task_id':tid});wf.finish(self.store)
        self.assertEqual((self.store.base/'history/task-outcomes.jsonl').read_bytes(),ledger);self.assertIsNone(self.store.load()['active_run'])
    def test_resuming_an_unrelated_blocked_task_cannot_clear_an_active_execution_stop(self):
        outside=self.task('Outside');self.progress(outside);inside=self.task('Inside');wf.start(self.store,'next',inside);state=self.store.load();state['task_progress'][outside].update({'stage':'blocked','resume_stage':'awaiting-validation','stop_reason':'unrelated failure'});state['active_run']['stop_reason']='Owner decision remains unresolved'
        with self.store.lock():self.store.save(self.store.text(),state)
        with self.assertRaisesRegex(wf.WorkflowError,'scope'):wf.resume_task(self.store,{'task_id':outside,'resolution':'The unrelated fixture is repaired.'})
        self.assertEqual(self.store.load()['active_run']['stop_reason'],'Owner decision remains unresolved')

    def test_finish_never_discards_a_pending_revalidation_attempt(self):
        tid=self.task();wf.start(self.store,'next');self.finish_task(tid);wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        with self.assertRaisesRegex(wf.WorkflowError,'stale|pending|unavailable'):wf.finish(self.store)
        self.assertEqual(wf.next_task(self.store)['task_id'],tid);self.assertIsNotNone(self.store.load()['active_run'])
    def test_completed_check_history_reports_missing_artifacts_without_rewriting_the_ledger(self):
        tid=self.task();self.finish_task(tid);before=(self.store.base/'history/task-outcomes.jsonl').read_bytes();(self.root/'report.json').unlink();view=wf.history(self.store,tid)[0]
        self.assertFalse(view['check_results'][0]['result']['evidence'][0]['available']);self.assertEqual((self.store.base/'history/task-outcomes.jsonl').read_bytes(),before)

if __name__=='__main__':unittest.main()
