"""Synthetic orchestration guards; native host observations are a separate required check."""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


flow=load('unit_decision_orchestration',CORE/'common/scripts/decision-orchestration.py')
dg=load('unit_orchestration_ledger',CORE/'common/scripts/decision-governance.py')
wf=load('unit_orchestration_store',CORE/'common/scripts/workflow-state.py')
sha=lambda value:hashlib.sha256(value.encode()).hexdigest()


class QueueFreeStore(wf.Store):
    def text(self):raise AssertionError('Orchestration cannot create or load a queue')
    def load(self,*args,**kwargs):raise AssertionError('Orchestration cannot select a run')
    def save(self,*args,**kwargs):raise AssertionError('Orchestration cannot save workflow state')


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.store=QueueFreeStore(self.root,allow_unselected=True,neutral=True)

    def context(self):return {'kind':'request','id':'unit-operation','semantic_fingerprint':sha('meaning'),'content_fingerprint':sha('bytes')}
    def authority(self,**extra):return {'id':'unit-grant','revision':1,'context_id':'unit-operation','allowed_kinds':['product','technical','specification-acceptance'],'constraints':['Isolated fixture decisions only; no publication or live side effects.'],'evidence':{'kind':'owner-message','reference':'Synthetic fixture grant; no actual human approval.'},**extra}
    def actor(self,role='resolver',n=1):return {'id':role+'-'+str(n),'context_id':role+'-context-'+str(n)}
    def question(self,**extra):return {'id':'choice','kind':'technical','text':'Choose a bounded fixture representation.','options':[{'id':'accept','text':'Accept the bounded plan.'},{'id':'revise','text':'Revise the bounded plan.'}],'recommendation':'accept','significance':'routine',**extra}
    def start(self,**extra):return flow.start(self.store,{'request_id':'unit-orchestration','context':self.context(),'authority':self.authority(),'executor':{'id':'executor','context_id':'executor-context'},'capabilities':{'independent_actors':True},**extra})
    def change(self,frame,command,**extra):return flow.mutate(self.store,command,{'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],'expected_orchestration_revision':frame['revision'],**extra})
    def action(self,frame):return flow.next_action(self.store,frame['id'])
    def creation(self,actor):return {'kind':'host-agent-created','provider':'unit-host','tool':'unit-spawn','reference':'synthetic-created:'+actor['id'],'actor_id':actor['id'],'actor_context_id':actor['context_id']}
    def prepare(self,frame,role=None,actor=None):
        action=self.action(frame);self.assertIn(action['action'],{'delegate','ask-owner'});role=role or action['role'];actor=actor or self.actor(role)
        return self.change(frame,'prepare-actor',actor=actor,input_digest=action['input_digest'],expected_decision_hash=action['decision_hash'],creation_evidence=None if role=='owner' else self.creation(actor))
    def answer(self,frame,status='answered',answer='accept'):
        decision=dg.read(self.store,frame['question_decision_id']);attempt=decision['attempts'][decision['prepared_attempt_id']];actor=attempt['actor'];owner=attempt['role']=='owner';action=self.action(frame)
        evidence={'kind':'submitted-answer' if owner else 'delegated-agent','reference':'Synthetic fixture role result; never native qualification.','actor_id':actor['id'],'actor_context_id':actor['context_id']}
        if not owner:evidence.update(provider='unit-host',tool='unit-message',creation_reference='synthetic-created:'+actor['id'])
        return self.change(frame,'record-actor',attempt_id=attempt['id'],expected_decision_hash=decision['decision_hash'],input_digest=action['input_digest'],result={'status':status,'answer':answer,'rationale':'Synthetic bounded decision rationale.'},evidence=evidence)
    def decision(self,frame,purpose='decision',question=None,finding_id=None,answer='accept'):
        frame=self.change(frame,'question',question=question or self.question(),purpose=purpose,finding_id=finding_id);frame=self.prepare(frame);frame=self.answer(frame,answer=answer);return self.change(frame,'accept-decision')
    def plan_ready(self):
        frame=self.start();frame=self.change(frame,'research',reference='Synthetic researched fixture.');frame=self.change(frame,'plan',plan_digest=sha('plan-one'),required_checks=['unit'],reference='Synthetic plan-one.');frame=self.decision(frame,'plan',self.question(kind='specification-acceptance'));frame=self.change(frame,'accept-plan',decision_receipt=frame['acceptance']);self.assertEqual(frame['phase'],'implement');return frame
    def identity(self,n=1):return {'head':str(n)*40,'base_oid':'b'*40,'source_digest':sha('source-'+str(n))}
    def reviewed(self,findings):
        frame=self.plan_ready();frame=self.change(frame,'implement',identity=self.identity(),reference='Synthetic implementation.');frame=self.change(frame,'checks',identity=self.identity(),results=[{'id':'unit','status':'passed','reference':'Synthetic test evidence.'}]);frame=self.change(frame,'review',identity=self.identity(),review_id='review-one',findings=findings,reference='Synthetic full review.');return frame
    def finding(self):return {'id':'finding-one','digest':sha('finding one'),'description':'The bounded fixture misses a declared condition.'}
    def snapshot(self):return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def test_api_is_runnable(self):
        for name in ['start','read','next_action','mutate']:self.assertTrue(callable(getattr(flow,name)))

    def test_new_frame_defaults_auto_and_never_bootstraps_queue(self):
        frame=self.start();self.assertEqual(frame['mode'],'auto');self.assertEqual(frame['phase'],'research');self.assertFalse((self.root/'.skill-tree/documents').exists());self.assertEqual(flow.read(self.store,frame['id']),frame)

    def test_start_nonce_replay_and_read_are_nonmutating(self):
        frame=self.start();before=self.snapshot();self.assertEqual(self.start(),frame);self.assertEqual(self.snapshot(),before)
        with self.assertRaises(flow.OrchestrationError):self.start(mode='manual')
        self.assertEqual(flow.read(self.store,frame['id']),frame);self.assertEqual(self.snapshot(),before)
        decision=dg.start(self.store,{'request_id':'external-clarification-decision','context':self.context(),'question':self.question(),'mode':'auto','authority':self.authority(),'executor':{'id':'executor','context_id':'executor-context'}})
        frame=self.change(frame,'question',existing_decision_id=decision['id'],purpose='decision');self.assertEqual(frame['question_decision_id'],decision['id']);self.assertEqual(self.action(frame)['role'],'resolver')
        other=self.start(request_id='other-frame',context={**self.context(),'id':'other-scope'},authority=self.authority(context_id='other-scope'))
        with self.assertRaises(flow.OrchestrationError):self.change(other,'question',existing_decision_id=decision['id'],purpose='decision')

    def test_actual_role_frontier_requires_critic_and_arbiter_for_disagreement(self):
        frame=self.change(self.start(),'question',question=self.question(significance='significant'),purpose='decision');self.assertEqual(self.action(frame)['role'],'resolver');frame=self.answer(self.prepare(frame));self.assertEqual(self.action(frame)['role'],'critic');frame=self.answer(self.prepare(frame),status='disagree');self.assertEqual(self.action(frame)['role'],'arbiter');frame=self.answer(self.prepare(frame),answer='revise');frame=self.change(frame,'accept-decision');self.assertEqual(frame['acceptance']['answer'],'revise');self.assertEqual(frame['acceptance']['origin']['kind'],'delegated-agent')

    def test_sealed_review_inputs_include_actual_predecessor_answers_and_rationale(self):
        frame=self.change(self.start(),'question',question=self.question(significance='significant'),purpose='decision')
        self.assertEqual(self.action(frame)['input']['prior_role_results'],{})
        frame=self.answer(self.prepare(frame));action=self.action(frame)
        resolver=next(iter(dg.read(self.store,frame['question_decision_id'])['attempts'].values()))
        material={'resolver':{key:copy.deepcopy(resolver[key]) for key in ('actor','status','result','evidence')}}
        self.assertEqual(action['input']['prior_role_results'],material)
        self.assertEqual(material['resolver']['result']['answer'],'accept')
        self.assertEqual(material['resolver']['result']['rationale'],'Synthetic bounded decision rationale.')
        changed=copy.deepcopy(action['input']);changed['prior_role_results']['resolver']['result']['rationale']='Altered rationale.'
        self.assertNotEqual(flow.digest(changed),action['input_digest']);before=self.snapshot();critic=self.actor('critic')
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'prepare-actor',actor=critic,input_digest=flow.digest(changed),expected_decision_hash=action['decision_hash'],creation_evidence=self.creation(critic))
        self.assertEqual(before,self.snapshot());frame=self.prepare(frame)
        self.assertEqual(frame['prepared_actor']['input']['prior_role_results'],material)
        frame['prepared_actor']['input']['prior_role_results']['resolver']['result']['answer']='revise'
        frame=flow.read(self.store,frame['id']);self.assertEqual(frame['prepared_actor']['input']['prior_role_results'],material)
        frame=self.answer(frame,status='disagree',answer='revise');action=self.action(frame)
        self.assertEqual(action['role'],'arbiter');self.assertEqual(set(action['input']['prior_role_results']),{'resolver','critic'})
        self.assertEqual(action['input']['prior_role_results']['resolver'],material['resolver'])
        self.assertEqual(action['input']['prior_role_results']['critic']['result']['answer'],'revise')
        self.assertEqual(action['input']['prior_role_results']['critic']['status'],'disagree')
        frame=self.prepare(frame);self.assertEqual(frame['prepared_actor']['input']['prior_role_results'],action['input']['prior_role_results'])
        changed=copy.deepcopy(frame['prepared_actor']['input']);del changed['prior_role_results']['critic'];self.assertNotEqual(flow.digest(changed),frame['prepared_actor']['input_digest'])

    def test_predecessor_material_excludes_historical_modes_and_semantic_frontiers(self):
        frame=self.change(self.start(),'question',question=self.question(significance='significant'),purpose='decision');frame=self.answer(self.prepare(frame))
        self.assertIn('resolver',self.action(frame)['input']['prior_role_results'])
        frame=self.change(frame,'switch-mode',mode='manual');self.assertEqual(self.action(frame)['input']['prior_role_results'],{})
        frame=self.change(frame,'switch-mode',mode='auto');self.assertEqual(self.action(frame)['role'],'resolver');self.assertEqual(self.action(frame)['input']['prior_role_results'],{})
        frame=self.answer(self.prepare(frame,actor=self.actor('resolver',2)))
        self.assertEqual(self.action(frame)['input']['prior_role_results']['resolver']['actor'],self.actor('resolver',2))
        frame=self.change(frame,'resume',context={**self.context(),'semantic_fingerprint':sha('changed meaning'),'content_fingerprint':sha('changed bytes')})
        self.assertIsNone(frame['question_decision_id']);frame=self.change(frame,'question',question=self.question(significance='significant'),purpose='decision')
        self.assertEqual(self.action(frame)['role'],'resolver');self.assertEqual(self.action(frame)['input']['prior_role_results'],{})

    def test_false_executor_independence_rejects_before_any_actor_write(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');action=self.action(frame);before=self.snapshot()
        for actor in [{'id':'executor','context_id':'another'},{'id':'renamed','context_id':'executor-context'}]:
            with self.subTest(actor=actor),self.assertRaises(flow.OrchestrationError):self.change(frame,'prepare-actor',actor=actor,input_digest=action['input_digest'],expected_decision_hash=action['decision_hash'],creation_evidence=self.creation(actor))
        self.assertEqual(self.snapshot(),before)

    def test_absent_host_capability_is_visible_without_manual_fallback(self):
        frame=self.change(self.start(capabilities={'independent_actors':False}),'question',question=self.question(),purpose='decision');self.assertEqual(self.action(frame)['action'],'prerequisite');self.assertEqual(frame['mode'],'auto');self.assertIsNone(frame['acceptance'])

    def test_creation_identity_and_sealed_input_are_current(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');action=self.action(frame);before=self.snapshot();actor=self.actor()
        for extra in [{'input_digest':'0'*64},{'creation_evidence':self.creation({**actor,'context_id':'counterfeit'})}]:
            with self.subTest(extra=extra),self.assertRaises(flow.OrchestrationError):self.change(frame,'prepare-actor',actor=actor,input_digest=extra.get('input_digest',action['input_digest']),expected_decision_hash=action['decision_hash'],creation_evidence=extra.get('creation_evidence',self.creation(actor)))
        self.assertEqual(self.snapshot(),before)

    def test_unavailable_actor_retains_prerequisite_and_original_attempt(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');frame=self.answer(self.prepare(frame),status='unavailable');self.assertEqual(self.action(frame)['action'],'prerequisite');self.assertEqual(frame['mode'],'auto');self.assertIsNone(frame['acceptance']);decision=dg.read(self.store,frame['question_decision_id']);self.assertEqual(len(decision['attempts']),1)

    def test_manual_waits_for_owner_answer_and_retains_origin(self):
        frame=self.change(self.start(mode='manual'),'question',question=self.question(),purpose='decision');self.assertEqual(self.action(frame)['action'],'ask-owner');self.assertIsNone(frame['acceptance']);frame=self.prepare(frame);self.assertEqual(self.action(frame)['action'],'wait-owner');frame=self.answer(frame);frame=self.change(frame,'accept-decision');self.assertEqual(frame['acceptance']['origin']['kind'],'submitted-answer');self.assertEqual(frame['mode'],'manual')

    def test_mode_switch_reconciles_original_pending_actor(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');frame=self.prepare(frame);before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'switch-mode',mode='manual')
        self.assertEqual(self.snapshot(),before);decision=dg.read(self.store,frame['question_decision_id']);old=decision['prepared_attempt_id'];frame=self.change(frame,'reconcile-actor',attempt_id=old,expected_decision_hash=decision['decision_hash'],status='cancelled',evidence={'kind':'actor-reconciliation','reference':'Synthetic explicit original actor cancellation.'});frame=self.change(frame,'switch-mode',mode='manual');self.assertEqual(frame['mode'],'manual');self.assertEqual(self.action(frame)['action'],'ask-owner')

    def test_full_clean_path_reaches_ready_without_inventing_a_fix(self):
        frame=self.reviewed([]);self.assertEqual(frame['phase'],'ready');self.assertFalse(any(item['event']=='fix' for item in frame['history']))

    def test_changed_plan_invalidates_prior_acceptance_and_downstream_evidence(self):
        frame=self.plan_ready();old=copy.deepcopy(frame['plan_acceptance']);frame=self.change(frame,'plan',plan_digest=sha('plan-two'),required_checks=['unit'],reference='Synthetic changed plan.');self.assertEqual(frame['phase'],'plan-review');self.assertIsNone(frame['plan_acceptance'])
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'accept-plan',decision_receipt=old)
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'implement',identity=self.identity(),reference='Cannot use old plan.')

    def test_product_answer_cannot_accept_current_plan(self):
        frame=self.start();frame=self.change(frame,'research',reference='Synthetic research.');frame=self.change(frame,'plan',plan_digest=sha('plan-one'),required_checks=['unit'],reference='Synthetic plan.');frame=self.decision(frame,'decision',self.question(kind='product'));before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'accept-plan',decision_receipt=frame['acceptance'])
        self.assertEqual(self.snapshot(),before)

    def test_checks_bind_current_identity_and_all_required_checks(self):
        frame=self.plan_ready();frame=self.change(frame,'implement',identity=self.identity(),reference='Synthetic implementation.');before=self.snapshot()
        for extra in [{'identity':self.identity(2),'results':[{'id':'unit','status':'passed','reference':'Wrong source.'}]},{'identity':self.identity(),'results':[]}]:
            with self.subTest(extra=extra),self.assertRaises(flow.OrchestrationError):self.change(frame,'checks',**extra)
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'review',identity=self.identity(),review_id='early',findings=[],reference='Missing actual checks.')
        self.assertEqual(self.snapshot(),before)

    def test_finding_fix_requires_resolution_checks_and_clean_current_rereview(self):
        finding=self.finding();frame=self.reviewed([finding]);self.assertEqual(frame['phase'],'resolution')
        question=self.question(options=[{'id':'fix','text':'Fix the evidenced finding.'},{'id':'reject','text':'Reject with current evidence.'}],recommendation='fix')
        frame=self.change(frame,'question',question=question,purpose='finding-resolution',finding_id=finding['id']);frame=self.prepare(frame);frame=self.answer(frame,answer='fix');frame=self.change(frame,'accept-decision');frame=self.change(frame,'resolve',finding_id=finding['id'],disposition='fix',decision_receipt=frame['acceptance'],reference='Synthetic accepted finding.');self.assertEqual(frame['phase'],'fix')
        frame=self.change(frame,'fix',identity=self.identity(2),fixed_ids=[finding['id']],reference='Synthetic scoped fix.');self.assertEqual(frame['phase'],'checks');frame=self.change(frame,'checks',identity=self.identity(2),results=[{'id':'unit','status':'passed','reference':'Synthetic post-fix check.'}]);self.assertEqual(frame['phase'],'re-review');frame=self.change(frame,'review',identity=self.identity(2),review_id='review-two',findings=[],reference='Synthetic current clean review.');self.assertEqual(frame['phase'],'ready')

    def test_changed_review_identity_invalidates_earlier_finding_receipt(self):
        options=[{'id':'fix','text':'Fix the current finding.'},{'id':'reject','text':'Reject with current evidence.'}]
        frame=self.reviewed([self.finding()]);frame=self.decision(frame,'finding-resolution',self.question(options=options,recommendation='fix'),finding_id=self.finding()['id'],answer='fix');old=copy.deepcopy(frame['acceptance']);frame=self.change(frame,'review',identity=self.identity(),review_id='review-two',findings=[self.finding()],reference='Synthetic new review.');self.assertEqual(frame['phase'],'resolution');before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'resolve',finding_id=self.finding()['id'],disposition='fix',decision_receipt=old,reference='Stale decision.')
        self.assertEqual(self.snapshot(),before)

    def test_valid_ledger_write_and_frame_write_commit_or_recover_together(self):
        frame=self.start();before=self.snapshot();commit=self.store.commit
        def rejected(writes):
            self.assertEqual(len(writes),2);raise RuntimeError('Synthetic pre-commit failure after valid buffered DG mutation')
        self.store.commit=rejected
        with self.assertRaisesRegex(RuntimeError,'pre-commit'):self.change(frame,'question',question=self.question(),purpose='decision')
        self.assertEqual(self.snapshot(),before);self.store.commit=commit;frame=self.change(frame,'question',question=self.question(),purpose='decision');replace=self.store.replace;failed=False
        def interrupted(path,content):
            nonlocal failed
            if path.name==frame['id'].lower()+'.json' and not failed:
                failed=True;raise RuntimeError('Synthetic interruption after DG activation before DO activation')
            return replace(path,content)
        self.store.replace=interrupted
        with self.assertRaisesRegex(RuntimeError,'interruption'):self.prepare(frame)
        self.assertTrue((self.root/'.skill-tree/.transaction.json').is_file());self.store.replace=replace
        with self.store.lock():pass
        recovered=flow.read(self.store,frame['id']);decision=dg.read(self.store,recovered['question_decision_id']);self.assertEqual(recovered['prepared_actor']['attempt_id'],decision['active_attempt_id']);self.assertEqual(self.action(recovered)['action'],'wait-actor');self.assertFalse((self.root/'.skill-tree/.transaction.json').exists())

    def test_valid_same_request_receipt_cannot_resolve_another_finding(self):
        first=self.finding();second={**self.finding(),'id':'finding-two','digest':sha('finding two')};frame=self.reviewed([first,second]);question=self.question(options=[{'id':'fix','text':'Fix the finding.'},{'id':'reject','text':'Reject with evidence.'}],recommendation='fix');frame=self.decision(frame,'finding-resolution',question,finding_id=first['id'],answer='fix');receipt=copy.deepcopy(frame['acceptance']);before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'resolve',finding_id=second['id'],disposition='fix',decision_receipt=receipt,reference='Wrong current finding.')
        self.assertEqual(self.snapshot(),before);frame=self.change(frame,'resolve',finding_id=first['id'],disposition='fix',decision_receipt=receipt,reference='Correct current finding.');self.assertIn(first['id'],frame['resolutions']);self.assertNotIn(second['id'],frame['resolutions'])

    def test_evidenced_rejection_rereviews_current_source_without_a_fake_fix(self):
        finding=self.finding();frame=self.reviewed([finding]);question=self.question(options=[{'id':'fix','text':'Fix the finding.'},{'id':'reject','text':'Reject with current evidence.'}],recommendation='reject');frame=self.decision(frame,'finding-resolution',question,finding_id=finding['id'],answer='reject');before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'resolve',finding_id=finding['id'],disposition='reject',decision_receipt=frame['acceptance'],reference='An unsupported dismissal.')
        self.assertEqual(self.snapshot(),before);frame=self.change(frame,'resolve',finding_id=finding['id'],disposition='reject',decision_receipt=frame['acceptance'],reference='Synthetic source-backed rejection.',evidence={'identity':self.identity(),'reference':'Synthetic exact fixture condition already satisfies the requirement.'});self.assertEqual(frame['phase'],'re-review');frame=self.change(frame,'review',identity=self.identity(),review_id='review-after-rejection',findings=[],reference='Synthetic clean review confirms rejection evidence.');self.assertEqual(frame['phase'],'ready');self.assertFalse(any(row['event']=='fix' for row in frame['history']));self.assertEqual(frame['identity'],self.identity())

    def test_resume_refreshes_actor_bytes_and_invalidates_changed_source_evidence(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');context={**self.context(),'content_fingerprint':sha('formatted bytes')};frame=self.change(frame,'resume',context=context);self.assertEqual(self.action(frame)['input']['context']['content_fingerprint'],context['content_fingerprint']);frame=self.prepare(frame);before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'resume',context={**context,'content_fingerprint':sha('new bytes while actor pending')})
        self.assertEqual(before,self.snapshot());fixture=self.root/'phase-fixture';fixture.mkdir();self.store=QueueFreeStore(fixture,allow_unselected=True,neutral=True);frame=self.reviewed([]);plan=copy.deepcopy(frame['plan_acceptance']);frame=self.change(frame,'resume',identity=self.identity(2));self.assertEqual(frame['phase'],'checks');self.assertIsNone(frame['checks']);self.assertIsNone(frame['review']);self.assertEqual(frame['plan_acceptance'],plan)
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'review',identity=self.identity(),review_id='stale',findings=[],reference='Old source evidence.')
        frame=self.change(frame,'checks',identity=self.identity(2),results=[{'id':'unit','status':'passed','reference':'Current source tests.'}]);frame=self.change(frame,'review',identity=self.identity(2),review_id='current-source',findings=[],reference='Current source full review.');self.assertEqual(frame['phase'],'ready')
        decision=dg.read(self.store,frame['plan_acceptance']['decision_id']);dg.mutate(self.store,'decision-switch',{'decision_id':decision['id'],'expected_decision_hash':decision['decision_hash'],'expected_decision_revision':decision['revision'],'expected_mode_epoch':decision['mode_epoch'],'expected_context_fingerprint':decision['context']['content_fingerprint'],'mode':'auto','authority':{**decision['authority'],'revision':2,'revoked':True}});self.assertEqual(self.action(frame)['action'],'prerequisite')

    def test_review_plan_and_actor_bookkeeping_cannot_reset_unchanged_obligations(self):
        frame=self.reviewed([self.finding()]);frame=self.decision(frame);frame=self.change(frame,'observe-failure',code='unchanged-finding',reference='Failed observation one.');frame=self.decision(frame);self.assertEqual(frame['stagnation']['count'],1)
        before=copy.deepcopy(frame);frame=self.change(frame,'plan',plan_digest=frame['plan']['digest'],required_checks=['unit'],reference='A new reference to the identical plan.');self.assertEqual(frame,before)
        frame=self.change(frame,'review',identity=self.identity(),review_id='review-id-churn-two',findings=[self.finding()],reference='Same findings and source, new run identifier.');self.assertEqual(frame['stagnation']['count'],1);frame=self.change(frame,'observe-failure',code='unchanged-finding',reference='Failed observation two.');frame=self.change(frame,'review',identity=self.identity(),review_id='review-id-churn-three',findings=[self.finding()],reference='Still the same unresolved obligation.');self.assertEqual(frame['stagnation']['count'],2);frame=self.change(frame,'observe-failure',code='unchanged-finding',reference='Failed observation three.');self.assertIsNotNone(frame['owner_question'])

    def test_required_open_question_blocks_implementation_despite_an_accepted_plan(self):
        frame=self.plan_ready();frame=self.change(frame,'question',question=self.question(),purpose='decision');frame=self.change(frame,'resume',capabilities={'independent_actors':False});self.assertEqual(self.action(frame)['action'],'prerequisite');before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'implement',identity=self.identity(),reference='An old accepted plan cannot bypass the open question.')
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'question',question=self.question(id='replacement',text='A replacement cannot erase the old required question.'),purpose='decision')
        self.assertEqual(before,self.snapshot());frame=self.change(frame,'resume',capabilities={'independent_actors':True});frame=self.answer(self.prepare(frame));frame=self.change(frame,'accept-decision');frame=self.change(frame,'implement',identity=self.identity(),reference='Current open question now actually accepted.');self.assertEqual(frame['phase'],'checks')

    def test_repeated_review_cannot_erase_unresolved_or_unfixed_findings(self):
        frame=self.reviewed([self.finding()]);before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'review',identity=self.identity(),review_id='erase-unresolved',findings=[],reference='A fresh review ID does not resolve the existing finding.')
        self.assertEqual(before,self.snapshot());question=self.question(options=[{'id':'fix','text':'Fix the finding.'},{'id':'reject','text':'Reject with proof.'}],recommendation='fix');frame=self.decision(frame,'finding-resolution',question,finding_id=self.finding()['id'],answer='fix');frame=self.change(frame,'resolve',finding_id=self.finding()['id'],disposition='fix',decision_receipt=frame['acceptance'],reference='The finding requires an actual source fix.');before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'review',identity=self.identity(),review_id='erase-unfixed',findings=[],reference='A requested fix has not been implemented.')
        self.assertEqual(before,self.snapshot())

    def test_snapshot_is_frozen_in_actor_input_and_explicit_resume_invalidates_acceptance(self):
        first={'scripts/decision-orchestration.py':sha('bundle one'),'profile.json':None};second={'scripts/decision-orchestration.py':sha('bundle two'),'profile.json':sha('current profile')};frame=self.start(execution_snapshot=first);frame=self.change(frame,'question',question=self.question(),purpose='decision');self.assertEqual(self.action(frame)['input']['execution_snapshot'],first);frame=self.prepare(frame);before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'resume',execution_snapshot=second)
        self.assertEqual(before,self.snapshot());decision=dg.read(self.store,frame['question_decision_id']);old_epoch=decision['frontier_epoch'];frame=self.change(frame,'reconcile-actor',attempt_id=decision['prepared_attempt_id'],expected_decision_hash=decision['decision_hash'],status='cancelled',evidence={'kind':'actor-reconciliation','reference':'Synthetic original actor cancellation before bundle refresh.'});frame=self.change(frame,'resume',execution_snapshot=second);self.assertIsNone(frame['question_decision_id']);self.assertEqual(frame['mode'],'auto');self.assertEqual(frame['execution_snapshot'],second);self.assertGreater(dg.read(self.store,decision['id'])['frontier_epoch'],old_epoch)
        fixture=self.root/'accepted-plan-fixture';fixture.mkdir();self.store=QueueFreeStore(fixture,allow_unselected=True,neutral=True);frame=self.plan_ready();plan=copy.deepcopy(frame['plan']);accepted_plan=copy.deepcopy(frame['plan_acceptance']);frame=self.change(frame,'resume',execution_snapshot=second);self.assertEqual(frame['plan'],plan);self.assertEqual(frame['phase'],'plan-review');self.assertIsNone(frame['plan_acceptance']);self.assertEqual(frame['mode'],'auto');self.assertTrue(any(row['detail'].get('previous_plan_acceptance')==accepted_plan for row in frame['history']))
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'implement',identity=self.identity(),reference='Old plan acceptance cannot cross a changed execution snapshot.')
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'accept-plan',decision_receipt=accepted_plan)
        self.assertIsNone(dg.read(self.store,accepted_plan['decision_id'])['acceptance'])

    def test_unchanged_failures_persist_one_owner_question_without_agent_progress(self):
        frame=self.start()
        for n in range(3):frame=self.change(frame,'observe-failure',code='same-prerequisite',reference='Synthetic failed observation '+str(n),actor_count=n+1)
        self.assertIsNotNone(frame['owner_question']);question=copy.deepcopy(frame['owner_question']);self.assertEqual(self.action(frame)['action'],'owner-question');frame=self.change(frame,'observe-failure',code='same-prerequisite',reference='Another unchanged observation.',actor_count=99);self.assertEqual(frame['owner_question'],question);self.assertEqual(frame['mode'],'auto')

    def test_guards_locks_and_existing_queue_bytes_are_preserved(self):
        frame=self.start();before=self.snapshot()
        with self.assertRaises(flow.OrchestrationError):self.change({**frame,'orchestration_hash':'0'*64},'research',reference='Stale frame.')
        self.assertEqual(self.snapshot(),before);docs=self.root/'.skill-tree/documents';docs.mkdir();(docs/'future.md').write_text('Preserved unrelated queue bytes.');(docs/'future.json').write_text('{"parked":"unchanged"}\n');before=self.snapshot();lock=self.root/'.skill-tree/.writer-lock';lock.write_text('fixture owner')
        with self.assertRaises(Exception):self.change(frame,'research',reference='Writer is already active.')
        lock.unlink();installation=self.root/'.skill-tree/installation';installation.mkdir();install_lock=installation/'.install-lock';install_lock.write_text('fixture installer')
        with self.assertRaises(Exception):self.change(frame,'research',reference='Installer is active.')
        install_lock.unlink();frame=self.change(frame,'research',reference='Safe scoped metadata write.');after=self.snapshot();self.assertEqual({k:v for k,v in before.items() if '/decisions/' not in k},{k:v for k,v in after.items() if '/decisions/' not in k})

    def test_out_of_grant_question_stays_unresolved_without_publication_authority(self):
        frame=self.start(authority=self.authority(allowed_kinds=['product']));frame=self.change(frame,'question',question=self.question(),purpose='decision');self.assertEqual(self.action(frame)['action'],'prerequisite');self.assertIsNone(frame['acceptance'])
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'question',question=self.question(kind='publication'),purpose='decision')
        with self.assertRaises(flow.OrchestrationError):self.change(frame,'question',question=self.question(id='allowed-replacement',kind='product'),purpose='decision')

    def test_exact_actor_result_replay_is_idempotent_and_conflict_rejects(self):
        frame=self.change(self.start(),'question',question=self.question(),purpose='decision');frame=self.answer(self.prepare(frame));before=self.snapshot();self.assertEqual(self.answer(frame),frame);self.assertEqual(self.snapshot(),before)
        with self.assertRaises(flow.OrchestrationError):self.answer(frame,answer='revise')
        self.assertEqual(self.snapshot(),before)


if __name__=='__main__':unittest.main()
