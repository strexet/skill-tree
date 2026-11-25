import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wf_progress',CORE/'common/scripts/workflow-state.py');wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)

class ValidationProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=wf.Store(self.root);self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (self.root/'source.py').write_text('value = 1\n');(self.root/'report.json').write_text('{"assertion":"value is preserved"}')
    def task(self,title='Feature',group=None,deps=(),timing='immediate',fresh_review=False):
        p=wf.intake(self.store,{'title':title,'description':'Implement scoped behavior.','expected_behavior':'Preserve the observable value.'})
        check={'id':'behavior','recipe_id':'static-inspection','criteria':['Preserve the value.'],'sources':['source.py'],'parameters':{},'assertion':'The value remains observable.','timing':timing}
        if fresh_review:check['fresh_review']=True
        body='Goal:\n- Preserve the value.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Preserve the value.\n'
        r=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Source research confirms the observable contract.'}},'tasks':[{'title':title,'body':body,'parent_pending_ids':[p['id']],'depends_on':list(deps),'validation_group_id':group,'boundary_validation':'group-end' if group else 'not-required'}]})
        return r['created_ids'][0]
    def progress(self,tid):
        wf.begin_task(self.store,{'task_id':tid});wf.mark_implemented(self.store,{'task_id':tid,'changed_files':['source.py']})
    def passed(self,tid):
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        return wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'static','environment_identity':attempt['environment_identity'],'classification':'executed-control','assertions':[{'assertion':'The value remains observable.','result':'pass'}],'evidence':['report.json'],'cleanup':'No product process was launched.'})

    def git(self,*args,cwd=None):
        return subprocess.check_output(['git',*args],cwd=cwd or self.root,text=True,stderr=subprocess.STDOUT).strip()

    def review_candidate(self,tid,controller=False):
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgSign','false')
        self.git('add','.')
        self.git('commit','-qm','Fixture baseline')
        if controller:
            wf.workspaces.setup(self.store,{})
            scope=wf.Store(self.root,allow_unselected=True,neutral=True)
            run=wf.start(scope,'next',tid,workspace={'implementation_operation':'work-through-next'})
            source=Path(wf.workspaces.runtime(self.root)['worktrees'][run['id']])
            self.store=wf.Store(source,run['id'])
            wf.begin_task(self.store,{'task_id':tid})
        else:
            wf.begin_task(self.store,{'task_id':tid,'implementation_operation':'implement-next'})
        (self.store.source_root/'source.py').write_text('value = 2\n')
        marked=wf.mark_implemented(self.store,{'task_id':tid,'changed_files':['source.py']})
        return marked['git_review_identity'],self.passed(tid)

    def review_change(self,frame,command,store=None,**payload):
        return wf.orchestration_action(store or self.store,'orchestration-'+command,{
            'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],
            'expected_orchestration_revision':frame['revision'],'expected_source_hash':wf.file_hash(self.store.future),**payload})

    def review_frame(self,scope,identity):
        fingerprint=wf.digest(wf.dump(scope).encode())
        context={**scope,'id':'review-fixture-'+fingerprint,'semantic_fingerprint':fingerprint,
                 'content_fingerprint':fingerprint}
        actor={'id':'fixture-owner','context_id':'fixture-owner-context'}
        frame=wf.orchestration_action(self.store,'orchestration-start',{
            'request_id':wf.identity('fixture'),'context':context,'mode':'manual','executor':{'id':'fixture-executor','context_id':'fixture-executor-context'},
            'authority':{'id':'fixture-authorization','revision':1,'context_id':context['id'],
                         'allowed_kinds':['specification-acceptance'],'constraints':['Only synthetic fixture decisions.'],
                         'evidence':{'kind':'owner-message','reference':'Synthetic fixture authority.'}},
            'expected_source_hash':wf.file_hash(self.store.future)})
        frame=self.review_change(frame,'research',reference='Fixture scope inspected.')
        frame=self.review_change(frame,'plan',plan_digest=fingerprint,required_checks=['behavior'],reference='Fixture review plan.')
        frame=self.review_change(frame,'question',purpose='plan',question={
            'id':'fixture','kind':'specification-acceptance','text':'Accept the fixture plan?',
            'options':[{'id':'accept','text':'Accept.'},{'id':'revise','text':'Revise.'}],'recommendation':'accept'})
        def action(frame):
            return wf.orchestration_action(self.store,'orchestration-next',{'orchestration_id':frame['id']})
        next_step=action(frame)
        frame=self.review_change(frame,'prepare-actor',actor=actor,input_digest=next_step['input_digest'],expected_decision_hash=next_step['decision_hash'])
        next_step=action(frame)
        frame=self.review_change(frame,'record-actor',attempt_id=frame['prepared_actor']['attempt_id'],
            input_digest=next_step['input_digest'],expected_decision_hash=next_step['decision_hash'],
            result={'status':'answered','answer':'accept','rationale':'The synthetic plan matches the fixture.'},
            evidence={'kind':'submitted-answer','reference':'Fixture answer.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        frame=self.review_change(frame,'accept-decision')
        frame=self.review_change(frame,'accept-plan',decision_receipt=frame['acceptance'])
        return self.review_change(frame,'implement',identity=identity,reference='Current Git fixture candidate.')

    def test_review_incorporates_actual_check_only_and_revalidates_artifacts_before_review(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        frame=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        candidates=wf.orchestration_action(self.store,'orchestration-check-evidence',{'orchestration_id':frame['id']})
        self.assertEqual(candidates['identity'],identity)
        offer=candidates['checks'][0]
        self.assertEqual(offer['attempt_id'],receipt['attempt_id'])
        self.assertEqual(offer['status'],'reusable')
        request={key:offer[key] for key in ('id','task_id','check_id','attempt_id')}
        with self.assertRaisesRegex(wf.WorkflowError,'verified receipt'):
            self.review_change(frame,'checks',identity=identity,results=[{'id':'behavior','status':'passed','reference':'core-check:invented'}])
        with self.assertRaisesRegex(wf.WorkflowError,'identity changed'):
            self.review_change(frame,'checks',identity=identity,reused_checks=[{**request,'attempt_id':wf.identity('C')}])
        adopted=self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        self.assertEqual(adopted['phase'],'review')
        self.assertEqual(adopted['checks']['results'][0]['core_check']['receipt_sha256'],offer['receipt_sha256'])
        report=self.root/'report.json';original_report=report.read_bytes();report.write_text('Changed result.')
        acceptance={'identity':identity,'review_id':'reviewer-proof','findings':[],'reference':'Independent fixture review.'}
        with self.assertRaisesRegex(wf.WorkflowError,'evidence missing or mismatched'):
            self.review_change(adopted,'review',**acceptance)
        report.write_bytes(original_report)
        task_source=self.root/'source.py';task_source.write_text('value = 3\n')
        with self.assertRaisesRegex(wf.WorkflowError,'sealed task candidate'):
            self.review_change(adopted,'review',**acceptance)
        task_source.write_text('value = 2\n')
        self.assertEqual(self.review_change(adopted,'review',**acceptance)['phase'],'ready')

    def test_review_declines_fresh_pending_or_changed_environment_checks(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        scope={'kind':'task','task_ids':[tid]}
        frame=self.review_frame({**scope,'fresh_check_ids':['behavior']},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        with self.assertRaisesRegex(wf.WorkflowError,'fresh execution'):
            self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        config=self.store.base/'config/repository.json';original=config.read_bytes()
        config.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'static-inspection':{'lane':'static','input_paths':[],'assertion_contract':'Changed fixture contract.'}}}))
        rows=wf.review_check_evidence(self.store,identity,scope)
        self.assertEqual(rows[0]['status'],'rerun-required')
        self.assertIn('environment changed',rows[0]['reason'])
        config.write_bytes(original)
        wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        rows=wf.review_check_evidence(self.store,identity,scope)
        self.assertIn('pending',rows[0]['reason'])

    def test_fresh_review_contract_excludes_a_passing_task_receipt(self):
        tid=self.task(fresh_review=True);identity,_=self.review_candidate(tid)
        rows=wf.review_check_evidence(self.store,identity,{'kind':'task','task_ids':[tid]})
        self.assertEqual(rows[0]['status'],'rerun-required')
        self.assertIn('requires fresh review',rows[0]['reason'])

    def test_task_completion_recovers_prepared_commit_with_reused_review_evidence(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        frame=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        frame=self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        frame=self.review_change(frame,'review',identity=identity,review_id='fixture-review',findings=[],reference='Independent fixture review.')
        completion={'task_id':tid,'review_id':frame['id'],'outcome':'The observable value remains preserved.',
                    'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                    'source_fingerprints':wf.fingerprints(self.store,['source.py'])}
        apply_commit=wf.workspaces.apply_task_commit
        def interrupt_after_commit(*args):
            apply_commit(*args)
            raise RuntimeError('Interrupted before recording completion')
        with patch.object(wf.workspaces,'apply_task_commit',interrupt_after_commit):
            with self.assertRaisesRegex(RuntimeError,'Interrupted before recording completion'):
                wf.complete(self.store,completion)
        head=self.git('rev-parse','HEAD')
        self.assertNotEqual(head,identity['head'])
        self.assertEqual(self.store.load()['task_progress'][tid]['task_git_attempt']['commit'],head)
        self.assertEqual(wf.complete(self.store,completion)['task_git_commit']['commit'],head)

    def controller_with_accepted_leaf(self):
        tid=self.task();identity,receipt=self.review_candidate(tid,controller=True)
        neutral=wf.Store(self.store.source_root,allow_unselected=True,neutral=True)
        task_review=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        task_review=self.review_change(task_review,'checks',store=neutral,identity=identity,reused_checks=[request])
        task_review=self.review_change(task_review,'review',identity=identity,review_id='fixture-task-review',findings=[],reference='Independent fixture review.')
        wf.complete(self.store,{'task_id':tid,'review_id':task_review['id'],'outcome':'The observable value remains preserved.',
            'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        return neutral,receipt,request

    def test_controller_offer_reuses_accepted_leaf_receipt_only_on_current_target(self):
        neutral,receipt,request=self.controller_with_accepted_leaf()
        controller=wf.controller_review_identity(self.store)
        self.assertEqual(controller['check_evidence'][0]['attempt_id'],receipt['attempt_id'])
        run_id=controller['review_scope']['run_id']
        before=wf.file_hash(self.store.state)
        timeline=wf.orchestration_action(neutral,'orchestration-timeline',{'run_ids':[run_id]})
        self.assertEqual(wf.file_hash(self.store.state),before)
        self.assertEqual(timeline['orchestrations'],[])
        run_timing=timeline['runs'][0];check_time=run_timing['check_intervals'][0]
        self.assertEqual((run_timing['run_id'],check_time['attempt_id'],check_time['status']),
                         (run_id,receipt['attempt_id'],'pass'))
        self.assertIsNotNone(check_time['seconds'])
        self.assertIsNone(run_timing['delivery_interval']['seconds'])
        with self.assertRaisesRegex(wf.WorkflowError,'distinct exact run ids'):
            wf.orchestration_action(self.store,'orchestration-timeline',{'run_ids':[run_id,run_id]})
        frame=self.review_frame(controller['review_scope'],controller['identity'])
        frame=self.review_change(frame,'checks',store=neutral,identity=controller['identity'],reused_checks=[request])
        self.assertEqual(frame['phase'],'review')
        self.git('commit','--quiet','--allow-empty','-m','Move fixture target')
        moved=wf.controller_review_identity(self.store)
        self.assertEqual(moved['identity'],controller['identity'])
        self.assertEqual(moved['check_evidence'],[])
        self.assertIn('source and target base',moved['check_evidence_unavailable'])
        with self.assertRaisesRegex(wf.WorkflowError,'source and target base'):
            self.review_change(frame,'review',identity=frame['identity'],review_id='fixture-controller-review',findings=[],reference='Independent fixture review.')

    def test_run_timeline_waits_for_verified_merge_before_recording_delivery_duration(self):
        neutral,_,request=self.controller_with_accepted_leaf()
        controller=wf.controller_review_identity(self.store)
        identity=controller['identity'];run_id=controller['review_scope']['run_id']
        frame=self.review_frame(controller['review_scope'],identity)
        frame=self.review_change(frame,'checks',store=neutral,identity=identity,reused_checks=[request])
        frame=self.review_change(frame,'review',store=neutral,identity=identity,review_id='fixture-controller-review',
                                 findings=[],reference='Independent fixture review.')
        frozen=wf.freeze_reviewed_controller(self.store,{'review_id':frame['id']})
        def delivery_timing():
            return wf.orchestration_action(neutral,'orchestration-timeline',{'run_ids':[run_id]})['runs'][0]['delivery_interval']
        self.assertEqual(delivery_timing()['started_at'],frozen['finished_at'])
        self.assertIsNone(delivery_timing()['seconds'])
        merged=wf.merge_reviewed_controller(self.store,{'owner_instruction':'Merge the isolated fixture locally.'})
        self.assertEqual(self.git('rev-parse','HEAD'),merged['delivery']['reviewed_merge']['commit'])
        observed=delivery_timing()
        self.assertEqual(observed['status'],'merged')
        self.assertEqual(observed['review_id'],frame['id'])
        self.assertTrue(wf.valid_id(observed['verified_delivery_event_id'],'E'))
        self.assertIsNotNone(observed['seconds'])
    def test_standalone_progress_survives_refresh_and_never_reimplements(self):
        tid=self.task();self.progress(tid)
        with self.store.lock():self.store.save(self.store.text(),self.store.load())
        self.assertEqual(wf.begin_task(self.store,{'task_id':tid})['phase'],'validate')
        self.assertEqual(self.store.load()['task_progress'][tid]['stage'],'awaiting-validation')
    def test_pending_stale_missing_and_changed_reports_cannot_complete(self):
        tid=self.task();self.progress(tid)
        with self.assertRaises(wf.WorkflowError):wf.validate_task_checks(self.store,tid)
        self.passed(tid);wf.validate_task_checks(self.store,tid)
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (self.root/'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.validate_task_checks(self.store,tid)
        self.passed(tid);(self.root/'report.json').write_text('changed artifact')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence'):wf.validate_task_checks(self.store,tid)
    def test_group_batching_never_expands_next_scope_or_bypasses_verified_dependency(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end')
        wf.start(self.store,'next',a);self.progress(a)
        result=wf.next_task(self.store);self.assertEqual(result['phase'],'validate');self.assertEqual(result['task_id'],a)
        self.assertNotIn(b,self.store.load()['active_run']['admitted_groups'][group])
    def test_all_batches_only_eligible_declared_group_members(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');other=self.task('Unrelated')
        wf.start(self.store,'all');selected=wf.next_task(self.store)['task_id'];self.assertEqual(selected,other)
        # Explicitly scope the fixture to the two grouped roots.
        state=self.store.load();state['active_run']['snapshot']=[a,b];state['active_run']['root_task_id']=a
        with self.store.lock():self.store.save(self.store.text(),state)
        self.progress(a);self.assertEqual(wf.next_task(self.store)['task_id'],b)
        self.progress(b);self.assertEqual(wf.next_task(self.store)['phase'],'validate')
    def test_zero_discovery_and_wrong_lane_cannot_pass(self):
        tid=self.task();self.progress(tid);attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'unit','environment_identity':attempt['environment_identity'],'classification':'executed-control','counts':{'expected':1,'discovered':0,'passed':0,'failed':0,'skipped':0},'evidence':['report.json'],'cleanup':'Complete.'})
    def test_unchanged_attempts_are_not_semantic_progress(self):
        tid=self.task();wf.start(self.store,'next');self.progress(tid);wf.record_cycle(self.store)
        wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});result=wf.record_cycle(self.store);self.assertEqual(result['phase'],'blocked')
    def test_mandatory_runtime_decision_without_check_mapping_is_rejected(self):
        with self.assertRaises(wf.WorkflowError):
            wf.check_specs({'body':'Validation:\n- Run tests.\nAcceptance:\n- Preserve the value.','boundary_validation':'not-required'})

    def complete(self,tid):
        self.passed(tid)
        return wf.complete(self.store,{'task_id':tid,'outcome':'The observable value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
    def test_shared_check_reuse_finalizes_group_once_and_retains_specification_until_verified(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');wf.start(self.store,'all');self.progress(a);self.progress(b)
        self.passed(a);wf.reuse_check(self.store,{'from_task_id':a,'from_check_id':'behavior','task_id':b,'check_id':'behavior'})
        record=wf.complete(self.store,{'task_id':a,'outcome':'The observable value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        self.assertEqual(record['task_id'],a);wf.validate_task_checks(self.store,b)
        self.assertNotIn(a,self.store.load()['task_progress']);self.assertIn(b,self.store.text());self.assertEqual(wf.next_task(self.store)['phase'],'validate')
        self.complete(b);wf.finish(self.store);self.assertEqual(len(self.store.outcomes()),2)
    def test_group_dependency_forces_upstream_verification_before_downstream_implementation(self):
        group=wf.identity('VG');a=self.task('Upstream',group,timing='group-end');b=self.task('Downstream',group,deps=[a],timing='group-end');wf.start(self.store,'next',b);self.progress(a)
        self.assertEqual(wf.next_task(self.store)['task_id'],a);self.assertEqual(wf.next_task(self.store)['phase'],'validate')
        with self.assertRaises(wf.WorkflowError):wf.begin_task(self.store,{'task_id':b})
        self.complete(a);self.assertEqual(wf.next_task(self.store)['task_id'],b)
    def test_changed_group_check_set_invalidates_affected_shared_evidence(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');wf.start(self.store,'all');self.progress(a);self.passed(a)
        text=self.store.text().replace('The value remains observable.','The value remains explicitly observable.',1);self.store.future.write_text(text)
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.validate_task_checks(self.store,a)
    def test_runtime_red_requires_behavioral_failure_and_nonzero_discovery(self):
        tid=self.task();text=self.store.text().replace('static-inspection','fixture-unit');self.store.future.write_text(text)
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source','recipes':{'fixture-unit':{'lane':'unit','argv':['fixture-runner'],'input_paths':[]}}}))
        self.progress(tid);attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        payload={'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'red','actual_lane':'unit','environment_identity':attempt['environment_identity'],'classification':'executed-control','counts':{'expected':1,'discovered':1,'passed':0,'failed':1,'skipped':0},'failure_category':'runner-failure','evidence':['report.json'],'cleanup':'The isolated fixture stopped.'}
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,payload)
        payload['failure_category']='expected-behavior';wf.record_check(self.store,payload)
        self.assertIn('red',self.store.load()['task_progress'][tid]['checks']['behavior'])
        with self.assertRaises(wf.WorkflowError):wf.validate_task_checks(self.store,tid)
        next_attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});payload['attempt_id']=next_attempt['attempt_id']
        payload.update({'result':'pass','counts':{'expected':1,'discovered':0,'passed':0,'failed':0,'skipped':0}})
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,payload)
        payload['counts']={'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0};wf.record_check(self.store,payload);wf.validate_task_checks(self.store,tid)
    def test_prepared_identity_blocks_changes_during_execution_and_launch_requires_a_deadline(self):
        tid=self.task();self.progress(tid)
        with self.assertRaises(wf.WorkflowError):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior','launch':{'assertion':'Inspect the rendered value.'}})
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});(self.root/'source.py').write_text('value = 3')
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id']})
    def test_only_two_unchanged_executed_failures_trip_the_circuit_breaker(self):
        tid=self.task();wf.start(self.store,'next');self.progress(tid)
        for classification in ['prerequisite-wait','transport-uncertainty','executed-control','executed-control']:
            attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
            wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'fail' if classification=='executed-control' else 'unavailable','actual_lane':'static','environment_identity':attempt['environment_identity'],'classification':classification,'failure_signature':'fixture assertion failed','evidence':['report.json'],'cleanup':'The isolated fixture stopped.'})
        self.assertEqual(self.store.load()['task_progress'][tid]['stage'],'blocked')
        with self.assertRaises(wf.WorkflowError):wf.next_task(self.store)
    def test_completion_cannot_bypass_missing_progress_with_a_passing_payload(self):
        tid=self.task()
        with self.assertRaises(wf.WorkflowError):wf.complete(self.store,{'task_id':tid,'outcome':'The value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        self.assertIn(tid,self.store.text());self.assertEqual(self.store.outcomes(),[])

    def test_profile_admission_is_pinned_once_and_repeated_only_on_explicit_resume(self):
        tid=self.task()
        with patch.object(wf,'admit_profile',wraps=wf.admit_profile) as admission:
            wf.start(self.store,'next');self.progress(tid);self.passed(tid);self.assertEqual(admission.call_count,1)
            wf.resume_admission(self.store);self.assertEqual(admission.call_count,2)
    def test_direct_queue_edit_cannot_admit_a_new_required_task(self):
        a=self.task('Root');wf.start(self.store,'next',a);b=self.task('Late unrelated')
        self.store.future.write_text(wf.rewrite_meta(self.store.text(),a,{'depends_on':[b]}))
        with self.assertRaisesRegex(wf.WorkflowError,'not admitted'):wf.next_task(self.store)
    def test_missing_profile_blocks_implementation_but_leaves_intake_available(self):
        (self.store.base/'config/repository.json').unlink();tid=self.task()
        with self.assertRaisesRegex(wf.WorkflowError,'Missing installation profile'):wf.begin_task(self.store,{'task_id':tid})
        self.assertTrue(wf.intake(self.store,{'title':'Research setup','description':'Inspect the scoped setup.','expected_behavior':'Resolve the missing capability.'})['id'].startswith('P-'))

if __name__=='__main__':unittest.main()
