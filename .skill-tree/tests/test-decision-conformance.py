"""Synthetic capture inputs test the oracle, never actual-native or real-human qualification."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]
def module(name,relative):
    spec=importlib.util.spec_from_file_location(name,CORE/relative)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
grader=module('decision_conformance','scripts/agent-conformance.py')
wf=module('decision_conformance_store','common/scripts/workflow-state.py')
do=module('decision_conformance_orchestration','common/scripts/decision-orchestration.py')
dg=module('decision_conformance_ledger','common/scripts/decision-governance.py')
sha=lambda value:hashlib.sha256(value.encode()).hexdigest()

class CoreDecisionConformanceTests(unittest.TestCase):
    def trace(self,material_defect=None):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        sources={relative:grader.digest(CORE/relative) for relative in grader.CORE_DECISION_SOURCES}
        capture={'schema':1,'kind':'core-decision-native-capture','source_snapshot':sources,'events':[]}
        report={'schema':1,'kind':'core-decision-agent-conformance','source_snapshot':sources,'scenarios':[],
                'limitations':['Capture trust is supplied separately by the observing caller; unit traces are synthetic.',
                              'Owner inputs are scripted, not real-human acceptance; native tool call IDs, exact model, tokens and costs can be unexposed.']}
        for scenario in sorted(grader.CORE_DECISION_CASES):
            events=[];root=Path(temporary.name)/scenario;root.mkdir();store=wf.Store(root,allow_unselected=True,neutral=True)
            def event(kind,**values):
                value={'id':scenario+'-event-'+str(len(events)+1),'scenario_id':scenario,'sequence':len(events)+1,'kind':kind,**copy.deepcopy(values)}
                events.append(value);return value
            def created(role):
                actor={'id':scenario+'-'+role+'-'+str(len(events)), 'context_id':scenario+'-'+role+'-context-'+str(len(events))}
                return event('actor-created',role=role,actor=actor,provider='unit-controlled-host',tool='collaboration.spawn_agent',native_request_sha256=sha('unit native request '+str(len(events))),tool_call_id=None,model=None,tokens=None,cost=None)
            executor=created('worker') if scenario=='core-manual' else event('executor-observed',actor={'id':'/root','context_id':'/root'},provider='unit-controlled-host',tool='collaboration.list_agents',inventory_entry={'agent_name':'/root','agent_status':'running'},native_request_sha256=sha('unit inventory request'),tool_call_id=None,model=None,tokens=None,cost=None)
            context={'kind':'request','id':scenario,'semantic_fingerprint':sha('unit scope'),'content_fingerprint':sha('unit bytes')}
            authority={'id':'unit-grant','revision':1,'context_id':scenario,'allowed_kinds':['technical','product','specification-acceptance'],'constraints':['Unit metadata only.'],'evidence':{'kind':'owner-message','reference':'Synthetic grant, never actual human.'}}
            frame=do.start(store,{'request_id':scenario,'context':context,'authority':authority,'executor':executor['actor'],'mode':'manual' if scenario=='core-manual' else 'auto','capabilities':{'independent_actors':True},'execution_snapshot':sources})
            def change(command,**payload):
                nonlocal frame
                frame=do.mutate(store,command,{'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],'expected_orchestration_revision':frame['revision'],**payload});return frame
            def ledger():return dg.read(store,frame['question_decision_id'])
            def observed(label):return event('observation',label=label,decision=ledger(),orchestration=frame,action=do.next_action(store,frame['id'])['action'])
            change('question',purpose='decision',question={'id':'representation','kind':'technical','text':'Which fixture representation?','options':[{'id':'json','text':'JSON'},{'id':'text','text':'Text'}],'recommendation':'json','significance':'significant' if scenario=='core-auto-significant' else 'routine'})
            def prepare(role):
                current=do.next_action(store,frame['id']);self.assertEqual(current['role'],role)
                creation=None if role=='owner' else created(role)
                actor={'id':'scripted-fixture-owner','context_id':'scripted-fixture-owner-context'} if creation is None else creation['actor']
                evidence=None if creation is None else {'kind':'host-agent-created','provider':creation['provider'],'tool':creation['tool'],'reference':creation['id'],'actor_id':actor['id'],'actor_context_id':actor['context_id']}
                change('prepare-actor',actor=actor,creation_evidence=evidence,input_digest=current['input_digest'],expected_decision_hash=current['decision_hash'])
                if material_defect and scenario=='core-auto-significant' and role==material_defect[0]:
                    # Model a malformed sealed transport while retaining valid checksums,
                    # native result digests and every original DG predecessor receipt.
                    request=frame['actor_requests'][frame['prepared_actor']['attempt_id']];envelope=request['input'];variant=material_defect[1]
                    if variant=='absent':envelope.pop('prior_role_results',None)
                    elif variant=='missing-role':envelope['prior_role_results'].pop('resolver')
                    elif variant=='answer':envelope['prior_role_results']['resolver']['result']['answer']='text'
                    elif variant=='rationale':envelope['prior_role_results']['resolver']['result']['rationale']='Invented rationale that the predecessor never returned.'
                    elif variant=='actor':envelope['prior_role_results']['resolver']['actor']['id']='invented-predecessor'
                    elif variant=='evidence':envelope['prior_role_results']['resolver']['evidence']['reference']='invented-return-event'
                    elif variant=='status':envelope['prior_role_results']['resolver']['status']='disagree'
                    elif variant=='extra-role':envelope['prior_role_results']['owner']=copy.deepcopy(envelope['prior_role_results']['resolver'])
                    else:raise AssertionError('Unknown material negative control')
                    request['input_digest']=dg._hash(envelope);frame['prepared_actor']=copy.deepcopy(request)
                    frame['orchestration_hash']=dg._hash({key:value for key,value in frame.items() if key!='orchestration_hash'})
                    do.path(store,frame['id']).write_text(json.dumps(frame))
                return creation,copy.deepcopy(frame['prepared_actor'])
            def returned(creation,request,status='answered',answer='json'):
                result={'status':status,'answer':answer,'rationale':'Controlled unit decision rationale.','input_digest':request['input_digest']}
                if creation is None:
                    evidence={'kind':'submitted-answer','reference':scenario+'-owner-input'}
                    observed_event=event('scripted-owner-input',actor={'id':'scripted-fixture-owner','context_id':'scripted-fixture-owner-context'},result=result,evidence=evidence,real_human=False)
                else:
                    observed_event=event('actor-returned',creation_event_id=creation['id'],input_digest=request['input_digest'],result=result)
                    evidence={'kind':'delegated-agent','reference':observed_event['id'],'creation_reference':creation['id'],'provider':creation['provider'],'tool':'collaboration.followup_task','actor_id':creation['actor']['id'],'actor_context_id':creation['actor']['context_id']}
                return result,evidence
            def settle(role,status='answered',answer='json'):
                creation,request=prepare(role);result,evidence=returned(creation,request,status,answer)
                change('record-actor',attempt_id=request['attempt_id'],input_digest=request['input_digest'],expected_decision_hash=ledger()['decision_hash'],result=result,evidence=evidence)
            if scenario=='core-auto-significant':
                settle('resolver');settle('critic','disagree','text');settle('arbiter',answer='text')
            elif scenario=='core-manual':
                worker=executor;worker_digest=sha('unit manual worker request')
                event('actor-returned',creation_event_id=worker['id'],input_digest=worker_digest,result={'status':'waiting','input_digest':worker_digest,'rationale':'Waiting for fixture-owner answer.'})
                observed('manual-wait');settle('owner')
                event('actor-returned',creation_event_id=worker['id'],input_digest=worker_digest,result={'status':'complete','input_digest':worker_digest,'rationale':'Observed the scripted answer.'})
            else:
                creation,request=prepare('resolver');old_result,old_evidence=returned(creation,request);observed('original-pending')
                change('reconcile-actor',attempt_id=request['attempt_id'],expected_decision_hash=ledger()['decision_hash'],status='cancelled',evidence={'kind':'actor-reconciliation','reference':'Unit controlled held response cancelled.'});observed('reconciled')
                change('switch-mode',mode='manual',evidence={'kind':'owner-message','reference':'Synthetic explicit fixture mode switch.'});observed('switched')
                change('resume',context={**context,'content_fingerprint':sha('unit formatted bytes')});observed('resumed')
                before=ledger()
                with self.assertRaises(do.OrchestrationError) as rejected:
                    change('record-actor',attempt_id=request['attempt_id'],input_digest=request['input_digest'],expected_decision_hash=before['decision_hash'],result=old_result,evidence=old_evidence)
                event('stale-result-rejected',attempt_id=request['attempt_id'],input_digest=request['input_digest'],error=str(rejected.exception),decision=ledger())
                settle('owner')
            change('accept-decision');observed('final')
            capture['events'].extend(events);report['scenarios'].append({'scenario_id':scenario,'event_ids':[e['id'] for e in events]})
        return report,capture

    def reject(self,report,capture):
        with self.assertRaises(ValueError):grader.validate_core_decision_report(report,capture)

    def test_complete_separately_captured_scenarios_validate_with_bounded_claim(self):
        report,capture=self.trace();result=grader.validate_core_decision_report(report,capture)
        self.assertTrue(result['passed']);self.assertEqual(result['scenarios'],3);self.assertIn('capture',result['scope'])

    def test_report_native_labels_and_all_true_checks_cannot_supply_capture(self):
        report,capture=self.trace();report['trusted_capture']=capture;report['checks']={'everything':True}
        self.reject(report,None)

    def test_missing_duplicate_or_unbound_capture_event_ids_reject(self):
        report,capture=self.trace()
        for variant in ['missing-scenario','duplicate-row','unknown-event','duplicate-event','cross-scenario']:
            value=copy.deepcopy(report)
            if variant=='missing-scenario':value['scenarios'].pop()
            elif variant=='duplicate-row':value['scenarios'][-1]=value['scenarios'][0]
            elif variant=='unknown-event':value['scenarios'][0]['event_ids'][0]='invented'
            elif variant=='duplicate-event':value['scenarios'][0]['event_ids'].append(value['scenarios'][0]['event_ids'][0])
            else:value['scenarios'][0]['event_ids'][0]=value['scenarios'][1]['event_ids'][0]
            with self.subTest(variant=variant):self.reject(value,capture)

    def test_current_source_and_do_execution_snapshot_must_match_external_capture(self):
        report,capture=self.trace()
        for variant in ['report-source','capture-source','do-source']:
            value=copy.deepcopy(report);external=copy.deepcopy(capture);relative=next(iter(report['source_snapshot']))
            if variant=='report-source':value['source_snapshot'][relative]='0'*64
            elif variant=='capture-source':external['source_snapshot'][relative]='0'*64
            else:
                observation=next(e for e in external['events'] if e.get('label')=='final');observation['orchestration']['execution_snapshot'][relative]='0'*64
            with self.subTest(variant=variant):self.reject(value,external)

    def test_actual_creation_identity_request_hash_and_sealed_result_digest_are_required(self):
        report,capture=self.trace()
        for variant in ['missing-creation','wrong-actor','no-provider','no-request-hash','input-digest','executor-self']:
            external=copy.deepcopy(capture);creation=next(e for e in external['events'] if e.get('role')=='resolver');returned=next(e for e in external['events'] if e.get('creation_event_id')==creation['id'])
            if variant=='missing-creation':external['events'].remove(creation)
            elif variant=='wrong-actor':creation['actor']['id']='invented-actor'
            elif variant=='no-provider':creation['provider']=''
            elif variant=='no-request-hash':creation['native_request_sha256']=None
            elif variant=='input-digest':returned['input_digest']='0'*64
            else:creation['actor']=next(e for e in external['events'] if e['kind']=='executor-observed')['actor']
            with self.subTest(variant=variant):self.reject(report,external)

    def test_captured_result_disagreement_and_final_acceptance_must_match_ledger(self):
        report,capture=self.trace()
        for variant in ['result','critic','arbiter','acceptance']:
            external=copy.deepcopy(capture)
            if variant=='result':next(e for e in external['events'] if e['kind']=='actor-returned')['result']['answer']='text'
            elif variant in {'critic','arbiter'}:
                creation=next(e for e in external['events'] if e.get('role')==variant);external['events']=[e for e in external['events'] if e.get('creation_event_id')!=creation['id']]
            else:next(e for e in external['events'] if e.get('label')=='final')['decision']['acceptance']['answer']='json'
            with self.subTest(variant=variant):self.reject(report,external)

    def test_sealed_predecessor_material_is_required_despite_valid_receipt_hashes(self):
        for role in ['critic','arbiter']:
            for variant in ['absent','missing-role','answer','rationale','actor','evidence','status','extra-role']:
                with self.subTest(role=role,variant=variant):
                    report,capture=self.trace((role,variant))
                    # The fixture seals and records the malformed input normally; the
                    # independent oracle must reject semantic material, not a checksum.
                    with self.assertRaisesRegex(ValueError,'predecessor material'):
                        grader.validate_core_decision_report(report,capture)

    def test_manual_worker_wait_precedes_scripted_owner_and_completion_without_human_claim(self):
        report,capture=self.trace()
        for variant in ['no-wait','owner-first','human','no-completion','wait-accepted']:
            external=copy.deepcopy(capture);manual=[e for e in external['events'] if e['scenario_id']=='core-manual'];owner=next(e for e in manual if e['kind']=='scripted-owner-input')
            if variant=='no-wait':next(e for e in manual if e.get('label')=='manual-wait')['action']='accepted'
            elif variant=='owner-first':owner['sequence']=1
            elif variant=='human':owner['real_human']=True
            elif variant=='no-completion':external['events']=[e for e in external['events'] if not (e['scenario_id']=='core-manual' and e.get('result',{}).get('status')=='complete')]
            else:next(e for e in manual if e.get('label')=='manual-wait')['orchestration']['acceptance']={'invented':True}
            with self.subTest(variant=variant):self.reject(report,external)

    def test_original_pending_requires_explicit_reconcile_switch_resume_and_rejected_stale_delivery(self):
        report,capture=self.trace()
        for variant in ['pending','reconcile','switch','resume','stale','different-attempt']:
            external=copy.deepcopy(capture);events=[e for e in external['events'] if e['scenario_id']=='core-switch-resume']
            if variant in {'pending','reconcile','switch','resume'}:
                label={'pending':'original-pending','reconcile':'reconciled','switch':'switched','resume':'resumed'}[variant]
                external['events']=[e for e in external['events'] if not (e['scenario_id']=='core-switch-resume' and e.get('label')==label)]
            elif variant=='stale':next(e for e in events if e['kind']=='stale-result-rejected')['error']=''
            else:next(e for e in events if e['kind']=='stale-result-rejected')['attempt_id']='DA-invented'
            with self.subTest(variant=variant):self.reject(report,external)

    def test_snapshot_checksums_and_current_scope_mode_cannot_be_forged_by_report(self):
        report,capture=self.trace()
        for variant in ['hash','mode','scope','epoch','limitations']:
            external=copy.deepcopy(capture);value=copy.deepcopy(report);final=next(e for e in external['events'] if e.get('label')=='final')
            if variant=='hash':final['decision']['decision_hash']='0'*64
            elif variant=='mode':final['orchestration']['mode']='manual'
            elif variant=='scope':final['orchestration']['context']['id']='another-request'
            elif variant=='epoch':final['decision']['acceptance']['mode_epoch']+=1
            else:value['limitations']=[]
            with self.subTest(variant=variant):self.reject(value,external)

if __name__=='__main__':unittest.main()
