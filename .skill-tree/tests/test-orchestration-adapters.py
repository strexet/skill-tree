"""Parent-policy resume controls use synthetic decisions, never native actor claims."""
import copy
import importlib.util
from pathlib import Path
import unittest

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('orchestration_adapter_fixture',CORE/'tests/test-decision-adapters.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
wf=fixture.wf


class OrchestrationAdapterTests(unittest.TestCase):
    setUp=fixture.DecisionAdapterTests.setUp
    body=fixture.DecisionAdapterTests.body
    task=fixture.DecisionAdapterTests.task
    call=fixture.DecisionAdapterTests.call
    source_hash=fixture.DecisionAdapterTests.source_hash
    start=fixture.DecisionAdapterTests.start
    question=fixture.DecisionAdapterTests.question
    snapshot=fixture.DecisionAdapterTests.snapshot
    mutate=fixture.DecisionAdapterTests.mutate
    auto_options=fixture.DecisionAdapterTests.auto_options

    def attached(self):
        session=self.start(**self.auto_options());session=self.mutate('clarify-round',session,questions=[self.question()])
        context=wf.clarification_decision_context(session,'answer','choice')
        request=fixture.request(context,'auto');request.update(request_id='adapter-original-decision',question={**request['question'],**wf.clarification_decision_question(session,'answer','choice')},authority=session['decision_authority'],executor=session['decision_executor'],expected_source_hash=self.source_hash())
        decision=wf.decision_action(self.store,'decision-start',request)
        frame=wf.orchestration_action(self.store,'orchestration-start',{'request_id':'adapter-original-frame','context':context,'authority':session['decision_authority'],'executor':session['decision_executor'],'capabilities':{'independent_actors':True},'expected_source_hash':self.source_hash()})
        return session,self.change(frame,'question',purpose='decision',existing_decision_id=decision['id']),decision

    def change(self,frame,command,**extra):
        return wf.orchestration_action(self.store,'orchestration-'+command,{'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],'expected_orchestration_revision':frame['revision'],'expected_source_hash':self.source_hash(),**extra})

    def switch(self,session,mode,**extra):
        policy=self.auto_options() if mode=='auto' else {'decision_mode':'manual'}
        return self.mutate('clarify-switch-mode',session,**{**policy,**extra},evidence={'kind':'owner-message','reference':'Synthetic explicit parent mode switch to '+mode+'.'})

    def current(self,session):return wf.clarification_decision_context(session,'answer','choice')

    def test_same_frame_adopts_actual_parent_manual_then_auto_policy_and_preserves_history(self):
        session,frame,decision=self.attached();identity=frame['id'];original=copy.deepcopy(decision)
        with self.assertRaises(wf.WorkflowError):self.change(frame,'switch-mode',mode='manual',evidence={'kind':'owner-message','reference':'Synthetic mode request.'})
        session=self.switch(session,'manual');self.assertEqual(session['decision_authority'],frame['authority']);self.assertEqual(session['decision_executor'],frame['executor'])
        frame=self.change(frame,'resume',context=self.current(session));self.assertEqual(frame['id'],identity);self.assertEqual(frame['mode'],'manual');self.assertEqual(frame['context']['parent_mode_epoch'],1);self.assertIsNone(frame['question_decision_id']);self.assertIsNone(frame['acceptance']);self.assertEqual(wf.decision_helper().read(self.store,decision['id']),original)
        detail=frame['history'][-1]['detail']['parent_policy_reconciliation'];self.assertEqual(detail['previous_question_decision_id'],decision['id']);self.assertEqual(detail['switches'][0]['evidence'],session['decision_mode_history'][0]['evidence'])
        session=self.switch(session,'auto');frame=self.change(frame,'resume',context=self.current(session));self.assertEqual(frame['id'],identity);self.assertEqual(frame['mode'],'auto');self.assertEqual(frame['context']['parent_mode_epoch'],2);self.assertEqual(len([row for row in frame['history'] if row.get('detail',{}).get('parent_policy_reconciliation')]),2)

    def test_parent_policy_resume_preserves_plan_bytes_and_requires_current_plan_review(self):
        session,frame,decision=self.attached();action=self.change(frame,'next');actor={'id':'synthetic-resolver','context_id':'synthetic-resolver-context'}
        frame=self.change(frame,'prepare-actor',actor=actor,input_digest=action['input_digest'],expected_decision_hash=action['decision_hash'],creation_evidence={'kind':'host-agent-created','provider':'synthetic-host','tool':'synthetic-spawn','reference':'Synthetic plan setup actor, never native execution.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        current=wf.decision_helper().read(self.store,decision['id']);frame=self.change(frame,'record-actor',attempt_id=current['prepared_attempt_id'],input_digest=frame['prepared_actor']['input_digest'],expected_decision_hash=current['decision_hash'],result={'status':'answered','answer':'keep','rationale':'Synthetic bounded answer.'},evidence={'kind':'delegated-agent','reference':'Synthetic answer.','creation_reference':'Synthetic plan setup actor, never native execution.','provider':'synthetic-host','tool':'synthetic-return','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        frame=self.change(frame,'accept-decision');frame=self.change(frame,'research',reference='Synthetic researched plan.');frame=self.change(frame,'plan',plan_digest='a'*64,required_checks=['unit'],reference='Synthetic plan bytes.');plan=copy.deepcopy(frame['plan'])
        session=self.switch(session,'manual');frame=self.change(frame,'resume',context=self.current(session));self.assertEqual(frame['plan'],plan);self.assertEqual(frame['phase'],'plan-review');self.assertIsNone(frame['plan_acceptance']);self.assertIsNone(frame['checks']);self.assertIsNone(frame['review'])

    def test_original_pending_attempt_blocks_parent_switch_and_resume_until_reconciled(self):
        session,frame,decision=self.attached();action=self.change(frame,'next');actor={'id':'synthetic-resolver','context_id':'synthetic-resolver-context'}
        frame=self.change(frame,'prepare-actor',actor=actor,input_digest=action['input_digest'],expected_decision_hash=action['decision_hash'],creation_evidence={'kind':'host-agent-created','provider':'synthetic-host','tool':'synthetic-spawn','reference':'Synthetic actor fixture, never actual native execution.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        before=self.snapshot()
        self.switch(session,'manual',ok=False)
        with self.assertRaises(wf.WorkflowError):self.change(frame,'resume',context=self.current(session))
        self.assertEqual(self.snapshot(),before)
        decision=wf.decision_helper().read(self.store,decision['id']);attempt=decision['prepared_attempt_id'];frame=self.change(frame,'reconcile-actor',attempt_id=attempt,expected_decision_hash=decision['decision_hash'],status='cancelled',evidence={'kind':'actor-reconciliation','reference':'Synthetic original actor cancellation.'})
        session=self.switch(session,'manual');frame=self.change(frame,'resume',context=self.current(session));self.assertEqual(frame['mode'],'manual');self.assertEqual(wf.decision_helper().read(self.store,decision['id'])['attempts'][attempt]['status'],'cancelled')

    def test_reconciliation_rejects_other_question_session_scope_and_old_epoch_atomically(self):
        session,frame,_=self.attached();session=self.switch(session,'manual');context=self.current(session);before=self.snapshot()
        for extra in [{'question_id':'another-question'},{'session_id':'CL-invented'},{'task_ids':[self.b]},{'purpose':'confirmation'},{'parent_mode_epoch':0}]:
            with self.subTest(extra=extra),self.assertRaises(wf.WorkflowError):self.change(frame,'resume',context={**context,**extra})
            self.assertEqual(self.snapshot(),before)
        frame=self.change(frame,'resume',context=context);self.assertEqual(frame['mode'],'manual')

    def test_explicit_parent_policy_clear_is_a_prerequisite_without_fabricated_authority(self):
        session,frame,decision=self.attached();session=self.switch(session,'manual',decision_authority=None,decision_executor=None);before=self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError,'cleared the bounded grant or executor'):self.change(frame,'resume',context=self.current(session))
        self.assertEqual(self.snapshot(),before);self.assertEqual(frame['mode'],'auto');self.assertEqual(wf.decision_helper().read(self.store,decision['id'])['mode'],'auto')

    def test_injected_parent_policy_cannot_replace_actual_parent_history(self):
        session,frame,_=self.attached();before=self.snapshot();forged={'mode':'manual','authority':frame['authority'],'executor':frame['executor'],'switches':[{'evidence':{'kind':'owner-message','reference':'Invented switch.'}}]}
        with self.assertRaises(wf.WorkflowError):self.change(frame,'resume',context={**self.current(session),'parent_mode_epoch':1},parent_policy_reconciliation=forged)
        self.assertEqual(self.snapshot(),before)

if __name__=='__main__':unittest.main()
