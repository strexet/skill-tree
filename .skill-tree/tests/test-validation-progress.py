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
    def task(self,title='Feature',group=None,deps=(),timing='immediate',fresh_review=False,recipe='static-inspection',independent_source=None):
        p=wf.intake(self.store,{'title':title,'description':'Implement scoped behavior.','expected_behavior':'Preserve the observable value.'})
        check={'id':'behavior','recipe_id':recipe,'criteria':['Preserve the value.'],'sources':['source.py'],'parameters':{},'assertion':'The value remains observable.','timing':timing}
        if fresh_review:check['fresh_review']=True
        checks = [check]
        if independent_source:
            checks.append({**check,'id':'independent','sources':[independent_source]})
        body='Goal:\n- Preserve the value.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+json.dumps({'checks':checks})+'\n```\n\nAcceptance:\n- Preserve the value.\n'
        r=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Source research confirms the observable contract.'}},'tasks':[{'title':title,'body':body,'parent_pending_ids':[p['id']],'depends_on':list(deps),'validation_group_id':group,'boundary_validation':'group-end' if group else 'not-required'}]})
        return r['created_ids'][0]
    def progress(self,tid):
        wf.begin_task(self.store,{'task_id':tid});wf.mark_implemented(self.store,{'task_id':tid,'changed_files':['source.py']})
    def passed(self,tid,check_id='behavior'):
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':check_id})
        return wf.record_check(self.store,{'task_id':tid,'check_id':check_id,'attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'static','environment_identity':attempt['environment_identity'],'classification':'executed-control','assertions':[{'assertion':'The value remains observable.','result':'pass'}],'evidence':['report.json'],'cleanup':'No product process was launched.'})

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
    def test_revalidation_impact_reports_exact_affected_consumers(self):
        (self.root/'shared').mkdir()
        (self.root/'shared/config.txt').write_text('format-one\n')
        (self.root/'unrelated.txt').write_text('independent data\n')
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'shared-static':{'lane':'static','input_paths':['shared/config.txt'],
                             'assertion_contract':'Review declared source and configuration inputs.'},
        }}))
        producer = self.task('Shared configuration consumer',recipe='shared-static')
        consumer = self.task('Dependent application',deps=[producer])
        outside = self.task('Unselected application',recipe='shared-static')
        wf.start(self.store,'next',consumer)
        if not hasattr(wf,'validation_impact'):
            self.fail('Affected revalidation preview is missing')
        before = (self.store.future.read_bytes(),self.store.state.read_bytes())
        affected = wf.validation_impact(self.store,{'paths':['shared/config.txt']})
        self.assertEqual(affected['paths'],['shared/config.txt'])
        self.assertEqual([(row['task_id'],row['check_id'],row['matched_paths'],row['consumer_ids'])
                          for row in affected['checks']],
                         [(producer,'behavior',['shared/config.txt'],[consumer])])
        self.assertNotIn(outside,[row['task_id'] for row in affected['checks']])
        self.assertEqual(wf.validation_impact(self.store,{'paths':['unrelated.txt']})['checks'],[])
        request = self.root/'impact-request.json'
        request.write_text(json.dumps({'paths':['shared/config.txt']}))
        output = subprocess.check_output(
            ['python3','-B',str(CORE/'common/scripts/workflow-state.py'),'validation-impact',str(self.root),
             '--input',str(request)], text=True)
        self.assertEqual(json.loads(output),affected)
        self.assertEqual((self.store.future.read_bytes(),self.store.state.read_bytes()),before)

    def test_final_revalidation_boundary_stages_exact_group_peers(self):
        group = wf.identity('VG')
        first = self.task('First shared contract',group=group)
        second = self.task('Second shared contract',group=group)
        wf.start(self.store,'all')
        for _ in (first,second):
            selected = wf.advance(self.store)['task_id']
            self.progress(selected)
            self.passed(selected)
            wf.complete(self.store,{'task_id':selected,'outcome':'The scoped value remains visible.',
                         'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                         'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        (self.root/'source.py').write_text('value = 3\n')
        handoff = wf.advance(self.store)
        lead = handoff['task_id']
        peer = next(task for task in (first,second) if task != lead)
        self.assertEqual(handoff['revalidation_bundle'],[
            {'from_task_id':lead,'from_check_id':'behavior','task_id':peer,'check_id':'behavior'},
        ])
        check_pass = self.passed(lead)
        self.assertEqual(wf.reuse_check(self.store,handoff['revalidation_bundle'][0])['attempt_id'],check_pass['attempt_id'])
        for task in (lead,peer):
            wf.accept_revalidation(self.store,{'task_id':task})
        self.assertEqual(wf.next_task(self.store)['phase'],'deferred-processing')

    def test_changed_recipe_input_holds_registered_consumer_until_current_verification(self):
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'shared-static':{'lane':'static','input_paths':['contract-config.txt'],
                             'assertion_contract':'Review declared source and configuration inputs.'},
        }}))
        (self.root/'contract-config.txt').write_text('original configuration\n')
        producer = self.task('Completed producer',recipe='shared-static')
        self.progress(producer)
        self.passed(producer)
        wf.complete(self.store,{'task_id':producer,'outcome':'The scoped value remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        intermediate = self.task('Completed intermediary',deps=[producer])
        self.progress(intermediate)
        self.passed(intermediate)
        wf.complete(self.store,{'task_id':intermediate,'outcome':'The scoped intermediate behavior remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        consumer = self.task('Ready consumer',deps=[intermediate])
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgsign','false')
        self.git('add','.')
        self.git('commit','-qm','Canonical fixture baseline')
        wf.workspaces.setup(self.store,{})
        run = wf.start(wf.Store(self.root,allow_unselected=True,neutral=True),'next',consumer,
                       workspace={'implementation_operation':'work-through-next'})
        self.assertEqual(set(run['required_ids']),{producer,intermediate,consumer})
        checkout = Path(wf.workspaces.runtime(self.root)['worktrees'][run['id']])
        self.store = wf.Store(checkout,run['id'])
        self.assertEqual(wf.next_task(self.store)['task_id'],consumer)
        (checkout/'contract-config.txt').write_text('changed common configuration\n')
        with self.assertRaisesRegex(wf.WorkflowError,'dependency.*'+producer):
            wf.begin_task(self.store,{'task_id':consumer})
        state = self.store.load()
        retained = {**state['active_run'], 'admitted_task_ids':[intermediate,consumer],
                    'required_ids':[intermediate,consumer]}
        outcomes = {item['task_id']:item for item in self.store.outcomes()}
        with self.assertRaisesRegex(wf.WorkflowError,'outside the frozen run scope.*'+producer):
            wf.first_completed_source_gap(self.store,{**state,'active_run':retained},outcomes)
        self.assertEqual(wf.advance(self.store)['task_id'],producer)
        for _ in range(2):
            attempt = wf.prepare_check(self.store,{'task_id':producer,'check_id':'behavior'})
            wf.record_check(self.store,{'task_id':producer,'check_id':'behavior','attempt_id':attempt['attempt_id'],
                'result':'fail','classification':'executed-control','actual_lane':'static',
                'environment_identity':attempt['environment_identity'],'failure_signature':'Fixture verification failed.',
                'evidence':['report.json'],'cleanup':'The fixture starts no product process.'})
        self.assertEqual(self.store.load()['task_progress'][producer]['stage'],'blocked')
        resumed = wf.resume_task(self.store,{'task_id':producer,'resolution':'Corrected the fixture condition.'})
        self.assertEqual(resumed['stage'],'awaiting-validation')
        self.passed(producer)
        wf.accept_revalidation(self.store,{'task_id':producer})
        self.assertEqual(wf.next_task(self.store)['task_id'],consumer)
        self.assertEqual(wf.begin_task(self.store,{'task_id':consumer})['phase'],'implement')

    def test_revalidation_retains_current_check_receipt_for_independent_inputs(self):
        (self.root/'independent.py').write_text('unrelated_value = 5\n')
        task = self.task('Two independently validated inputs',independent_source='independent.py')
        wf.start(self.store,'all')
        self.progress(task)
        self.passed(task)
        retained = self.passed(task,check_id='independent')
        wf.complete(self.store,{'task_id':task,'outcome':'The scoped value remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py','independent.py'])})
        (self.root/'source.py').write_text('value = 3\n')
        handoff = wf.next_task(self.store)
        self.assertEqual([check['id'] for check in handoff['checks']],['behavior'])
        self.assertEqual(handoff['retained_check_ids'],['independent'])
        self.passed(task)
        wf.accept_revalidation(self.store,{'task_id':task})
        check = next(item for item in self.store.load()['active_run']['revalidated_checks'][task]
                     if item['check']['id']=='independent')
        self.assertEqual(check['result']['attempt_id'],retained['attempt_id'])

    def test_validation_impact_keeps_real_runtime_resource_conflict_visible(self):
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'fixture-browser':{'lane':'browser','input_paths':['source.py'],'argv':['fixture-browser']},
        }}))
        (self.store.base/'worktree-profile.json').write_text(json.dumps({
            'schema':1,'exclusive_resources':['browser:fixture'],
        }))
        actor = self.task('Resource owner')
        candidate = self.task('Independent browser candidate',recipe='fixture-browser')
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgsign','false')
        self.git('add','.')
        self.git('commit','-qm','Canonical fixture baseline')
        wf.workspaces.setup(self.store,{})
        owner = wf.Store(self.root,allow_unselected=True,neutral=True)
        first = wf.start(owner,'next',actor,workspace={'implementation_operation':'work-through-next'})
        wf.workspaces.resource(wf.Store(self.root,first['id']),{'resource':'browser:fixture'})
        next_owner = wf.Store(self.root,allow_unselected=True,neutral=True)
        second = wf.start(next_owner,'next',candidate,workspace={'implementation_operation':'work-through-next'})
        scoped = wf.Store(self.root,second['id'])
        view = wf.next_task(scoped)['validation_impact']
        self.assertEqual(view['checks'][0]['lane'],'browser')
        self.assertEqual(view['runtime_resources'],[
            {'resource':'browser:fixture','holder_run_id':first['id'],'status':'occupied'},
        ])
        with self.assertRaisesRegex(wf.workspaces.RunError,'exclusive resource'):
            wf.workspaces.environment(scoped,{'runtime':True})
        task = wf.resolve(wf.parse(scoped.text()),[candidate])[0]
        check = wf.check_specs(task)[0]
        _, environment = wf.recipe_for(scoped,check)
        artifact = wf.evidence_pointer(scoped,'report.json',required=True)
        historical = {environment:{'tool_identity':'fixture-runner','fixture_identity':'fixture-case',
                                   'build_identity':'fixture-package','identity_evidence':[artifact]}}
        state = scoped.load()
        accepted = wf.check_snapshot(scoped,task,check,state,historical_sessions=historical)
        self.assertEqual(accepted['recipe']['lane'],'browser')
        with self.assertRaisesRegex(wf.workspaces.RunError,'exclusive resource'):
            wf.check_snapshot(scoped,task,check,state)
        (scoped.source_root/'report.json').write_text('Changed artifact.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence'):
            wf.check_snapshot(scoped,task,check,state,historical_sessions=historical)

    def test_registered_completion_lineage_must_match_the_applied_event(self):
        self.controller_with_accepted_leaf()
        original, = self.store.outcomes()
        task_id = original['task_id']
        self.assertEqual(wf.completed_dependency_order(self.store,{task_id:original},[task_id]),[task_id])
        ledger = self.store.owned(wf.OUTCOME_LEDGER)
        altered = {**original,'depends_on':[wf.identity('T')]}
        ledger.write_text(json.dumps(altered)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.prepare_check(self.store,{'task_id':task_id,'check_id':'behavior'})
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.accept_revalidation(self.store,{'task_id':task_id})

        alternate = self.store.source_root/'alternate-report.json'
        alternate.write_text('Replacement evidence.')
        substituted = json.loads(json.dumps(original))
        substituted['check_results'][0]['result']['evidence'] = [
            wf.evidence_pointer(self.store,'alternate-report.json',required=True),
        ]
        ledger.write_text(json.dumps(substituted)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)

        ledger.write_text(json.dumps(original)+'\n')
        state = self.store.load()
        run_id = self.store.run_id
        state['active_run'].pop('completed_contract_sha256s',None)
        state['run_registry']['runs'][run_id].pop('completed_contract_sha256s',None)
        with self.store.lock():
            self.store.save(self.store.text(),state)
        directory = self.store.base/'history/run-events'/run_id.lower()
        event_path, = [file for file in directory.glob('e-*.json')
                       if original in json.loads(file.read_text())['outcomes']]
        event = json.loads(event_path.read_text())
        event['outcomes'] = [altered if item==original else item for item in event['outcomes']]
        event_path.write_text(wf.dump(event))
        ledger.write_text(json.dumps(altered)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)

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
