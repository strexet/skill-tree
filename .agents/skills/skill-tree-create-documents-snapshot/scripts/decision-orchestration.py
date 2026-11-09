"""Core phases and host requests; the sibling DG ledger owns every decision answer."""
from contextlib import contextmanager
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import uuid

spec=importlib.util.spec_from_file_location('skill_tree_orchestration_decisions',Path(__file__).with_name('decision-governance.py'))
dg=importlib.util.module_from_spec(spec);spec.loader.exec_module(dg)


class OrchestrationError(ValueError):
    pass


COMMANDS={'question','prepare-actor','record-actor','reconcile-actor','switch-mode','accept-decision','research','plan','accept-plan','implement','checks','review','resolve','fix','resume','observe-failure'}
PHASES={'research','plan','plan-review','implement','checks','review','resolution','fix','re-review','ready'}
DO=re.compile(r'^DO-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')


def require(condition,message):
    if not condition:raise OrchestrationError(message)


def text(value):return isinstance(value,str) and bool(value.strip())
def digest(value):return dg._hash(value)


def execution_snapshot(value):
    require(value is None or isinstance(value,dict) and all(text(key) and '\0' not in key and (item is None or isinstance(item,str) and dg.SHA.fullmatch(item)) for key,item in value.items()),'Execution snapshot requires a frozen SHA256/null map');return deepcopy(value)


class BufferedStore:
    """One DG write joins the phase write in the existing canonical transaction."""
    def __init__(self,store):self.store=store;self.writes={};self.commits=0
    def __getattr__(self,key):return getattr(self.store,key)
    @contextmanager
    def lock(self):yield
    def commit(self,writes):
        require(self.commits==0,'An orchestration command permits only one DG mutation')
        self.commits+=1;self.writes.update(writes)


def path(store,identity):
    require(isinstance(identity,str) and DO.fullmatch(identity),'An exact DO identity is required')
    value=store.owned('.skill-tree/decisions/'+identity.lower()+'.json')
    require(not value.is_symlink() and not value.parent.is_symlink(),'Orchestration metadata cannot use symlinks');return value


def raw(store,identity):
    value=path(store,identity);require(value.is_file(),'Unknown orchestration identity')
    try:record=json.loads(value.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise OrchestrationError('Unreadable orchestration metadata') from error
    require(isinstance(record,dict) and record.get('schema')==1 and record.get('id')==identity,'Unsupported orchestration metadata')
    require(record.get('orchestration_hash')==digest({k:v for k,v in record.items() if k!='orchestration_hash'}),'Orchestration metadata checksum differs')
    require(record.get('phase') in PHASES and record.get('mode') in {'auto','manual'} and type(record.get('revision')) is int and record['revision']>0,'Invalid orchestration phase or revision')
    dg.validate_context(record['context']);dg.validate_authority(record['authority'],record['context'],record['mode']);dg._actor(record['executor']);execution_snapshot(record.get('execution_snapshot'));return record


def read(store,orchestration_id):
    try:return deepcopy(raw(store,orchestration_id))
    except dg.DecisionError as error:raise OrchestrationError(str(error)) from error


def write(store,frame,event,detail=None,buffer=None):
    previous=frame.pop('orchestration_hash',None);frame['revision']+=1
    frame['history'].append({'sequence':frame['revision'],'event':event,'phase':frame['phase'],'previous_frame_hash':previous,'detail':deepcopy(detail or {})})
    frame['orchestration_hash']=digest(frame);value=path(store,frame['id']);relative=value.relative_to(store.root).as_posix()
    if hasattr(store,'_write_hashes') and relative not in store._write_hashes:store._write_hashes[relative]=None
    writes=dict(buffer.writes) if buffer else {};writes[relative]=json.dumps(frame,ensure_ascii=False,sort_keys=True,indent=2)+'\n';store.commit(writes);return deepcopy(frame)


def start(store,payload):
    try:
        require(isinstance(payload,dict) and text(payload.get('request_id')),'A stable orchestration request identity is required')
        context=dg.validate_context(payload.get('context'));mode=payload.get('mode','auto');authority=dg.validate_authority(payload.get('authority'),context,mode);executor=dg._actor(payload.get('executor'))
        capabilities=deepcopy(payload.get('capabilities',{'independent_actors':False}));require(isinstance(capabilities,dict) and type(capabilities.get('independent_actors')) is bool,'Independent actor capability must be explicit')
        limit=payload.get('stagnation_limit',3);require(type(limit) is int and 2<=limit<=10,'Stagnation limit must be bounded')
        inputs={'request_id':payload['request_id'],'context':context,'mode':mode,'authority':authority,'executor':executor,'capabilities':capabilities,'stagnation_limit':limit,'execution_snapshot':execution_snapshot(payload.get('execution_snapshot'))};identity='DO-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-tree-orchestration:'+payload['request_id']))
        with store.lock():
            if path(store,identity).exists():
                frame=raw(store,identity);require(frame['start_digest']==digest(inputs),'Orchestration request identity was reused for different inputs');return deepcopy(frame)
            frame={'schema':1,'id':identity,'revision':0,'phase':'research','history':[],'question_decision_id':None,'question_context':None,'question_purpose':None,'question_sequence':0,'actor_requests':{},'prepared_actor':None,'acceptance':None,'plan':None,'plan_acceptance':None,'identity':None,'checks':None,'review':None,'resolutions':{},'phase_after_checks':'review','owner_question':None,'prerequisites':[],'stagnation':{'key':None,'count':0},'failure_observations':[],'accepted_obligations':[],'resolved_obligations':[],'start_digest':digest(inputs),**inputs}
            return write(store,frame,'start')
    except dg.DecisionError as error:raise OrchestrationError(str(error)) from error


def ledger(store,frame):
    if not frame['question_decision_id']:return None
    decision=dg.read(store,frame['question_decision_id'])
    require(decision['mode']==frame['mode'] and decision['authority']==frame['authority'] and decision['executor']==frame['executor'],'Current DG mode, grant or executor differs; explicitly reconcile the frame')
    require(decision['context']==frame['question_context'],'Current DG context differs from the attached question');return decision


def decision_context(frame,purpose,finding_id=None):
    context={**frame['context'],'orchestration_id':frame['id'],'decision_purpose':purpose}
    if frame.get('execution_snapshot') is not None:context['execution_snapshot_digest']=digest(frame['execution_snapshot'])
    if purpose=='plan':
        require(frame['plan'] is not None,'A current plan is required');context.update(plan_digest=frame['plan']['digest'],required_checks_digest=digest(frame['plan']['required_checks']))
    if purpose=='finding-resolution':
        review=frame['review'];require(review is not None,'A current full review is required');finding=next((v for v in review['findings'] if v['id']==finding_id),None);require(finding is not None,'Unknown current review finding')
        context.update(review_digest=review['digest'],finding_id=finding_id,finding_digest=finding['digest'])
    return context


def guards(frame,payload):
    require(payload.get('expected_orchestration_hash')==frame['orchestration_hash'] and payload.get('expected_orchestration_revision')==frame['revision'],'Orchestration bytes or revision changed; reread before mutation')


def dg_change(buffer,decision,command,payload):
    return dg.mutate(buffer,'decision-'+command,{'decision_id':decision['id'],'expected_decision_hash':decision['decision_hash'],'expected_decision_revision':decision['revision'],'expected_mode_epoch':decision['mode_epoch'],'expected_context_fingerprint':decision['context']['content_fingerprint'],**payload})


def reference(value):
    require(isinstance(value,dict),'An actual DG acceptance reference is required')
    return {'decision_id':value.get('decision_id'),'acceptance_digest':value.get('acceptance_digest',value.get('digest'))}


def accepted(store,frame,value,purpose,kind,finding_id=None):
    return dg.acceptance_reference(store,reference(value),{'context':decision_context(frame,purpose,finding_id),'mode':frame['mode'],'authority_digest':digest(frame['authority']),'kind':kind})


def no_pending(store,frame):
    decision=ledger(store,frame)
    require(not decision or not dg._pending(decision),'Reconcile the original pending actor before changing phases or inputs')


def fresh_plan(store,frame):
    require(frame['plan_acceptance'] is not None,'A current accepted plan is required');accepted(store,frame,frame['plan_acceptance'],'plan','specification-acceptance')


def clear_decision(store,frame):
    require(not frame['prerequisites'],'The visible decision prerequisite remains unresolved')
    decision=ledger(store,frame)
    if decision:
        require(decision['acceptance'] is not None and frame['acceptance']==decision['acceptance'],'The current decision frontier must be accepted before business transitions')
        dg.acceptance_reference(store,reference(decision['acceptance']),{'context':decision['context'],'mode':frame['mode'],'authority_digest':digest(frame['authority']),'kind':decision['question']['kind']})


def review_obligations(frame):
    return digest({'identity':frame['review']['identity'],'findings':frame['review']['findings']}) if frame['review'] else None


def fresh_resolutions(store,frame):
    for finding_id,resolution in frame['resolutions'].items():
        receipt=accepted(store,frame,resolution['receipt'],'finding-resolution','technical',finding_id)
        require(receipt['answer']==resolution['disposition'],'Current finding resolution authority changed')


def next_value(store,frame):
    result={'frame':deepcopy(frame),'phase':frame['phase'],'role':None,'input_digest':None,'decision_hash':None}
    if frame['owner_question']:return {**result,'action':'owner-question','question':deepcopy(frame['owner_question'])}
    if frame['phase'] in {'implement','checks','review','resolution','fix','re-review','ready'}:
        try:fresh_plan(store,frame)
        except (OrchestrationError,dg.DecisionError) as error:return {**result,'action':'prerequisite','prerequisites':[str(error)]}
    decision=ledger(store,frame)
    if not decision:return {**result,'action':'phase'}
    result['decision_hash']=decision['decision_hash'];result['decision_id']=decision['id']
    pending=next((a for a in decision['attempts'].values() if a['status']=='pending'),None)
    if pending:
        request=frame['actor_requests'].get(pending['id']);require(request is not None,'The attached original actor requires explicit reconciliation before broker reuse')
        return {**result,'action':'wait-owner' if pending['role']=='owner' else 'wait-actor','role':pending['role'],'input':deepcopy(request['input']),'input_digest':request['input_digest'],'attempt_id':pending['id']}
    previous=frame.get('prepared_actor')
    if previous:result.update(input=deepcopy(previous['input']),input_digest=previous['input_digest'],attempt_id=previous['attempt_id'])
    if frame['prerequisites']:return {**result,'action':'prerequisite','prerequisites':deepcopy(frame['prerequisites'])}
    if not dg._permitted(decision):return {**result,'action':'prerequisite','prerequisites':['The current question is outside the bounded owner grant.']}
    if decision['acceptance'] is not None:return {**result,'action':'accepted','acceptance':deepcopy(decision['acceptance'])}
    roles=dg._roles(decision);role='owner' if decision['mode']=='manual' else 'resolver'
    if role in roles:
        role=None
        if decision['mode']=='auto':
            attempted={a['role'] for a in decision['attempts'].values() if dg._matches(decision,a)}
            if 'critic' not in roles and (decision['question'].get('significance')=='significant' or 'critic' in attempted):role='critic'
            elif roles.get('critic',{}).get('status')=='disagree' and 'arbiter' not in roles:role='arbiter'
    if role is None:return {**result,'action':'accept-decision'}
    if role!='owner' and not frame['capabilities']['independent_actors']:return {**result,'action':'prerequisite','role':role,'prerequisites':['The host must expose actual independent agent creation and observed result tools.']}
    predecessors={'critic':('resolver',),'arbiter':('resolver','critic')}.get(role,())
    material={r:{key:deepcopy(roles[r][key]) for key in ('actor','status','result','evidence')} for r in predecessors}
    envelope={'schema':1,'orchestration_id':frame['id'],'orchestration_revision':frame['revision'],'decision_id':decision['id'],'decision_hash':decision['decision_hash'],'mode':decision['mode'],'mode_epoch':decision['mode_epoch'],'role':role,'context':deepcopy(decision['context']),'question':deepcopy(decision['question']),'authority':deepcopy(decision['authority']),'authority_digest':decision['authority_digest'],'execution_snapshot':deepcopy(frame.get('execution_snapshot')),'role_receipts':{r:dg._receipt(a) for r,a in roles.items()},'prior_role_results':material}
    return {**result,'action':'ask-owner' if role=='owner' else 'delegate','role':role,'input':envelope,'input_digest':digest(envelope)}


def next_action(store,orchestration_id):
    try:return next_value(store,raw(store,orchestration_id))
    except dg.DecisionError as error:raise OrchestrationError(str(error)) from error


def failure(frame,code,reference_value):
    require(text(code) and text(reference_value),'A failed observation requires a stable obligation code and actual evidence reference')
    observation=digest({'code':code,'reference':reference_value})
    if observation in frame['failure_observations']:return False
    frame['failure_observations'].append(observation)
    key=digest({'code':code,'semantics':frame['context']['semantic_fingerprint'],'plan':frame['plan']['digest'] if frame['plan'] else None,'review':review_obligations(frame)})
    count=frame['stagnation']['count']+1 if frame['stagnation']['key']==key else 1;frame['stagnation']={'key':key,'count':count}
    if count>=frame['stagnation_limit'] and frame['owner_question'] is None:
        frame['owner_question']={'id':'OQ-'+str(uuid.uuid5(uuid.NAMESPACE_URL,frame['id']+key)),'text':'The '+code+' obligation remains unchanged after '+str(count)+' observations. Which concrete prerequisite or bounded direction should change before execution resumes?','obligation':code,'context_fingerprint':frame['context']['semantic_fingerprint']}
    return True


def progress(frame):frame['stagnation']={'key':None,'count':0}


def identity(value):
    require(isinstance(value,dict) and all(isinstance(value.get(k),str) and re.fullmatch('(?:[a-f0-9]{40}|[a-f0-9]{64})',value[k]) for k in ('head','base_oid')) and isinstance(value.get('source_digest'),str) and dg.SHA.fullmatch(value['source_digest']),'Current implementation identity requires exact head, base and source digest');return deepcopy(value)


def question_command(store,buffer,frame,payload):
    no_pending(store,frame);purpose=payload.get('purpose','decision');require(purpose in {'decision','plan','finding-resolution'},'Unknown question purpose')
    if purpose=='plan':require(frame['phase']=='plan-review','Plan decisions require the current plan-review phase')
    if purpose=='finding-resolution':require(frame['phase']=='resolution','Finding decisions require current resolution phase')
    previous=ledger(store,frame)
    require(not previous or previous['acceptance'] is not None,'An unresolved decision frontier cannot be silently replaced')
    if payload.get('existing_decision_id'):
        require(purpose=='decision','A phase-specific question requires its exact current plan or finding binding')
        decision=dg.read(store,payload['existing_decision_id']);require(decision['context']==frame['context'] and decision['mode']==frame['mode'] and decision['authority']==frame['authority'] and decision['executor']==frame['executor'],'Existing DG identity belongs to another context, mode, grant or executor')
    else:
        context=decision_context(frame,purpose,payload.get('finding_id'));frame['question_sequence']+=1
        decision=dg.start(buffer,{'request_id':frame['id']+':question:'+str(frame['question_sequence']),'context':context,'question':payload.get('question'),'mode':frame['mode'],'authority':frame['authority'],'executor':frame['executor']})
    frame.update(question_decision_id=decision['id'],question_context=deepcopy(decision['context']),question_purpose=purpose,acceptance=None,prepared_actor=None,prerequisites=[])
    return {'decision_id':decision['id'],'purpose':purpose}


def prepare_actor(store,buffer,frame,payload):
    action=next_value(store,frame);require(action['action'] in {'delegate','ask-owner'},'The current frontier does not permit another actor')
    require(payload.get('input_digest')==action['input_digest'] and payload.get('expected_decision_hash')==action['decision_hash'],'Prepared role inputs or DG bytes are stale')
    actor=dg._actor(payload.get('actor'));creation=payload.get('creation_evidence');role=action['role']
    if role!='owner':
        require(isinstance(creation,dict) and creation.get('kind')=='host-agent-created' and all(text(creation.get(k)) for k in ('provider','tool','reference')) and creation.get('actor_id')==actor['id'] and creation.get('actor_context_id')==actor['context_id'],'An actual host-created actor identity and traceable creation event are required')
    else:require(creation is None,'Manual owner input cannot be represented as agent creation')
    decision=dg_change(buffer,ledger(store,frame),'prepare',{'role':role,'actor':actor});attempt=decision['prepared_attempt_id']
    sealed={**action['input'],'actor':actor,'creation_evidence':deepcopy(creation)};request={'attempt_id':attempt,'input':sealed,'input_digest':digest(sealed),'creation_evidence':deepcopy(creation)}
    frame['actor_requests'][attempt]=request;frame['prepared_actor']=deepcopy(request);return {'attempt_id':attempt,'input_digest':request['input_digest']}


def record_actor(store,buffer,frame,payload):
    decision=ledger(store,frame);require(decision is not None and payload.get('expected_decision_hash')==decision['decision_hash'],'Current original DG bytes are required')
    request=frame['actor_requests'].get(payload.get('attempt_id'));require(request is not None and payload.get('input_digest')==request['input_digest'],'Result does not match the sealed original actor input')
    evidence=payload.get('evidence');creation=request['creation_evidence']
    if creation is not None:require(isinstance(evidence,dict) and evidence.get('creation_reference')==creation['reference'] and evidence.get('provider')==creation['provider'] and text(evidence.get('tool')),'Result must reference the original actual host creation and observed message event')
    updated=dg_change(buffer,decision,'record',{'attempt_id':payload['attempt_id'],'result':payload.get('result'),'evidence':evidence})
    if updated['decision_hash']==decision['decision_hash']:return None
    status=payload['result']['status']
    if status in {'unavailable','failed','cancelled'}:
        frame['prerequisites']=['The original '+updated['attempts'][payload['attempt_id']]['role']+' is '+status+'; explicitly restore capability or reconcile before retry.'];failure(frame,'actor-'+status,evidence['reference'])
    return {'attempt_id':payload['attempt_id'],'status':status}


def mutate(store,command,payload):
    try:
        if command.startswith('orchestration-'):command=command[len('orchestration-'):]
        require(command in COMMANDS and isinstance(payload,dict),'Unknown orchestration operation')
        with store.lock():
            frame=raw(store,payload.get('orchestration_id'));guards(frame,payload);buffer=BufferedStore(store);detail={}
            require(not frame['owner_question'] or command in {'observe-failure','reconcile-actor','switch-mode','resume'},'Unchanged obligations require the persisted owner answer before further business work')
            if command=='question':detail=question_command(store,buffer,frame,payload)
            elif command=='prepare-actor':detail=prepare_actor(store,buffer,frame,payload)
            elif command=='record-actor':detail=record_actor(store,buffer,frame,payload)
            elif command=='reconcile-actor':
                decision=ledger(store,frame);require(decision is not None and payload.get('expected_decision_hash')==decision['decision_hash'],'Original DG bytes are required for reconciliation');dg_change(buffer,decision,'reconcile',{'attempt_id':payload.get('attempt_id'),'status':payload.get('status'),'evidence':payload.get('evidence')});frame['prerequisites']=[];detail={'attempt_id':payload.get('attempt_id')}
            elif command=='switch-mode':
                no_pending(store,frame);mode=payload.get('mode');authority=dg.validate_authority(payload.get('authority',frame['authority']),frame['context'],mode)
                if mode==frame['mode'] and authority==frame['authority']:return deepcopy(frame)
                evidence=payload.get('evidence')
                if evidence is not None:require(isinstance(evidence,dict) and evidence.get('kind') in {'owner-message','submitted-answer'} and text(evidence.get('reference')),'Explicit mode evidence requires a traceable submitted owner input')
                detail={'previous_mode':frame['mode'],'previous_authority':deepcopy(frame['authority']),'previous_acceptance':deepcopy(frame['acceptance']),'previous_plan_acceptance':deepcopy(frame['plan_acceptance']),'evidence':deepcopy(evidence),'source':'submitted-owner-input' if evidence is not None else 'explicit-host-api'};decision=ledger(store,frame)
                if decision:dg_change(buffer,decision,'switch',{'mode':mode,'authority':authority})
                frame.update(mode=mode,authority=authority,acceptance=None,plan_acceptance=None,prerequisites=[])
                if frame['plan']:frame['phase']='plan-review'
            elif command=='accept-decision':
                decision=ledger(store,frame);require(decision is not None,'A current question is required');updated=dg_change(buffer,decision,'accept',{})
                if frame['acceptance']==updated['acceptance']:return deepcopy(frame)
                frame['acceptance']=deepcopy(updated['acceptance']);obligation=digest({'semantics':frame['context']['semantic_fingerprint'],'question':decision['question'],'purpose':frame['question_purpose'],'plan':frame['plan']['digest'] if frame['question_purpose']=='plan' else None,'review':review_obligations(frame) if frame['question_purpose']=='finding-resolution' else None,'finding':decision['context'].get('finding_digest'),'answer':updated['acceptance']['answer']})
                if obligation not in frame['accepted_obligations']:frame['accepted_obligations'].append(obligation);progress(frame)
                detail={'decision_id':decision['id'],'acceptance_digest':updated['acceptance']['digest']}
            elif command=='research':
                clear_decision(store,frame);require(frame['phase']=='research' and text(payload.get('reference')),'Research evidence is required before drafting a plan');frame.update(phase='plan',research_reference=payload['reference']);progress(frame)
            elif command=='plan':
                clear_decision(store,frame);require(frame['phase']!='research','Research precedes the draft plan');checks=payload.get('required_checks');require(isinstance(checks,list) and checks and all(text(v) for v in checks) and len(checks)==len(set(checks)) and isinstance(payload.get('plan_digest'),str) and dg.SHA.fullmatch(payload['plan_digest']) and text(payload.get('reference')),'A plan requires a content digest, reference and exact required checks')
                plan={'digest':payload['plan_digest'],'required_checks':checks,'reference':payload['reference']}
                if frame['plan'] and frame['plan']['digest']==plan['digest'] and frame['plan']['required_checks']==checks:return deepcopy(frame)
                detail={'previous_plan':deepcopy(frame['plan']),'previous_acceptance':deepcopy(frame['plan_acceptance'])};frame.update(plan=deepcopy(plan),phase='plan-review',plan_acceptance=None,checks=None,review=None,resolutions={},question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None);progress(frame)
            elif command=='accept-plan':
                clear_decision(store,frame);require(frame['phase']=='plan-review','Only the current plan-review phase accepts a plan');receipt=accepted(store,frame,payload.get('decision_receipt'),'plan','specification-acceptance');require(receipt['answer']=='accept','A request to revise cannot accept a plan');frame.update(plan_acceptance=receipt,phase='implement');progress(frame)
            elif command=='implement':
                clear_decision(store,frame);fresh_plan(store,frame);require(frame['phase']=='implement' and text(payload.get('reference')),'Implementation requires the accepted current plan');frame.update(identity=identity(payload.get('identity')),checks=None,review=None,resolutions={},phase='checks',phase_after_checks='review');progress(frame)
            elif command=='checks':
                clear_decision(store,frame);fresh_plan(store,frame);require(frame['phase']=='checks' and identity(payload.get('identity'))==frame['identity'],'Checks require the current implementation identity');results=payload.get('results');require(isinstance(results,list) and all(isinstance(v,dict) and text(v.get('id')) and v.get('status') in {'passed','failed','unavailable','skipped'} and text(v.get('reference')) for v in results),'Actual required check outcomes and references are required');require(len({v['id'] for v in results})==len(results) and {v['id'] for v in results}==set(frame['plan']['required_checks']),'Every required check must be recorded exactly once')
                passed=all(v['status']=='passed' for v in results);frame['checks']={'identity':deepcopy(frame['identity']),'results':deepcopy(results),'passed':passed,'required_checks_digest':digest(frame['plan']['required_checks'])}
                if passed:frame['phase']=frame['phase_after_checks'];progress(frame)
                else:failure(frame,'checks:'+','.join(sorted(v['id']+':'+v['status'] for v in results if v['status']!='passed')),digest(results))
            elif command=='review':
                clear_decision(store,frame);fresh_plan(store,frame);fresh_resolutions(store,frame);current=identity(payload.get('identity'));require(frame['phase'] in {'review','re-review','resolution','ready'} and current==frame['identity'] and frame['checks'] and frame['checks']['passed'] and frame['checks']['identity']==current and frame['checks']['required_checks_digest']==digest(frame['plan']['required_checks']),'Full review requires passing current checks and current plan/source identity')
                findings=payload.get('findings');require(isinstance(findings,list) and all(isinstance(v,dict) and text(v.get('id')) and text(v.get('description')) and isinstance(v.get('digest'),str) and dg.SHA.fullmatch(v['digest']) for v in findings) and len({v['id'] for v in findings})==len(findings) and text(payload.get('review_id')) and text(payload.get('reference')),'A current full review requires exact findings and actual evidence')
                review={'id':payload['review_id'],'identity':current,'findings':deepcopy(findings),'reference':payload['reference']};review['digest']=digest({k:v for k,v in review.items() if k!='reference'})
                if frame['review']:
                    retained={(v['id'],v['digest']) for v in findings};required={(v['id'],v['digest']) for v in frame['review']['findings'] if frame['resolutions'].get(v['id'],{}).get('disposition')!='reject'};require(required<=retained,'A repeated same-source review cannot erase unresolved or unfixed findings')
                    if review['digest']==frame['review']['digest']:return deepcopy(frame)
                meaningful=not frame['review'] or digest({'identity':current,'findings':findings})!=review_obligations(frame);detail={'previous_review':deepcopy(frame['review']),'previous_resolutions':deepcopy(frame['resolutions'])};frame.update(review=review,resolutions={},phase='resolution' if findings else 'ready',question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None)
                if meaningful:progress(frame)
            elif command=='resolve':
                clear_decision(store,frame);fresh_plan(store,frame);require(frame['phase']=='resolution' and text(payload.get('reference')),'Current finding resolution requires evidence');finding_id=payload.get('finding_id');disposition=payload.get('disposition');require(disposition in {'fix','reject'},'A finding requires explicit fix or evidenced rejection');receipt=accepted(store,frame,payload.get('decision_receipt'),'finding-resolution','technical',finding_id);require(receipt['answer']==disposition,'Finding disposition differs from the actual accepted decision')
                if disposition=='reject':require(isinstance(payload.get('evidence'),dict) and text(payload['evidence'].get('reference')) and payload['evidence'].get('identity')==frame['identity'],'Rejected findings require concrete evidence for the current source identity')
                resolution={'disposition':disposition,'receipt':receipt,'reference':payload['reference'],'evidence':deepcopy(payload.get('evidence'))};previous=frame['resolutions'].get(finding_id)
                if previous:
                    require(previous['disposition']==disposition and previous['receipt']==receipt and previous['evidence']==resolution['evidence'],'A settled finding cannot be overwritten within the current review');return deepcopy(frame)
                frame['resolutions'][finding_id]=resolution
                if len(frame['resolutions'])==len(frame['review']['findings']):frame['phase']='fix' if any(v['disposition']=='fix' for v in frame['resolutions'].values()) else 're-review'
                obligation=digest({'review':review_obligations(frame),'finding':finding_id,'disposition':disposition})
                if obligation not in frame['resolved_obligations']:frame['resolved_obligations'].append(obligation);progress(frame)
            elif command=='fix':
                clear_decision(store,frame);fresh_plan(store,frame);fresh_resolutions(store,frame);require(frame['phase']=='fix' and text(payload.get('reference')),'Only accepted current findings authorize the fix phase');ids=payload.get('fixed_ids');require(isinstance(ids,list) and len(ids)==len(set(ids)) and set(ids)=={key for key,value in frame['resolutions'].items() if value['disposition']=='fix'},'Fix evidence must cover exactly the accepted findings');current=identity(payload.get('identity'));require(current!=frame['identity'],'A claimed fix requires changed current source identity');detail={'review':deepcopy(frame['review']),'resolutions':deepcopy(frame['resolutions'])};frame.update(identity=current,checks=None,review=None,resolutions={},phase='checks',phase_after_checks='re-review',question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None);progress(frame)
            elif command=='resume':
                no_pending(store,frame);context=dg.validate_context(payload.get('context',frame['context']));parent_policy=payload.get('parent_policy_reconciliation');detail={'previous_context':deepcopy(frame['context'])}
                if parent_policy is not None:
                    require(isinstance(parent_policy,dict) and frame['context'].get('session_id') and context.get('parent_mode_epoch',0)>frame['context'].get('parent_mode_epoch',0),'Parent policy resume requires the same explicit clarification with a newer policy epoch')
                    stable=lambda value:{key:item for key,item in dg._identity(value).items() if key!='parent_mode_epoch'}
                    require(stable(context)==stable(frame['context']),'Parent policy resume cannot change the original typed session, task, question or purpose')
                    mode=parent_policy.get('mode');authority=dg.validate_authority(parent_policy.get('authority'),context,mode);executor=dg._actor(parent_policy.get('executor'));switches=parent_policy.get('switches')
                    require(isinstance(switches,list) and switches and all(isinstance(entry,dict) and isinstance(entry.get('evidence'),dict) and entry['evidence'].get('kind') in {'owner-message','submitted-answer'} and text(entry['evidence'].get('reference')) for entry in switches),'Parent policy resume requires traceable original owner switch evidence')
                    detail['parent_policy_reconciliation']={'previous_mode':frame['mode'],'previous_authority':deepcopy(frame['authority']),'previous_executor':deepcopy(frame['executor']),'previous_acceptance':deepcopy(frame['acceptance']),'previous_plan_acceptance':deepcopy(frame['plan_acceptance']),'previous_question_decision_id':frame['question_decision_id'],'switches':deepcopy(switches)}
                    frame.update(context=context,mode=mode,authority=authority,executor=executor,plan_acceptance=None,checks=None,review=None,resolutions={},question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None,prerequisites=[])
                    if frame['plan']:frame['phase']='plan-review'
                else:require(dg._identity(context)==dg._identity(frame['context']),'Resume cannot substitute another typed scope')
                snapshot=execution_snapshot(payload.get('execution_snapshot',frame.get('execution_snapshot')));snapshot_changed=snapshot!=frame.get('execution_snapshot');original=ledger(store,frame)
                target=original or (dg.read(store,frame['plan_acceptance']['decision_id']) if snapshot_changed and frame['plan_acceptance'] else None);updated=None
                if target and (context!=frame['context'] or snapshot_changed):
                    updated_context={**target['context'],'content_fingerprint':context['content_fingerprint'],'semantic_fingerprint':context['semantic_fingerprint']};changes={'context':updated_context}
                    if snapshot_changed:changes['question']={**target['question'],'execution_snapshot_digest':digest(snapshot)}
                    updated=dg_change(buffer,target,'resume',changes)
                if context['semantic_fingerprint']!=frame['context']['semantic_fingerprint']:frame.update(plan=None,plan_acceptance=None,checks=None,review=None,resolutions={},question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None,phase='research')
                elif original and updated:frame['question_context']=deepcopy(updated['context'])
                frame['context']=context
                if 'identity' in payload:
                    current=identity(payload['identity'])
                    if current!=frame['identity']:
                        detail.update(previous_identity=deepcopy(frame['identity']),previous_review=deepcopy(frame['review']));following='re-review' if frame['review'] else 'review';frame.update(identity=current,checks=None,review=None,resolutions={},question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None,phase_after_checks=following)
                        if frame['plan_acceptance']:fresh_plan(store,frame);frame['phase']='checks'
                if 'execution_snapshot' in payload:
                    if snapshot_changed:
                        detail.update(previous_execution_snapshot=deepcopy(frame.get('execution_snapshot')),previous_plan_acceptance=deepcopy(frame['plan_acceptance']),previous_question_decision_id=frame['question_decision_id']);frame.update(execution_snapshot=snapshot,plan_acceptance=None,checks=None,review=None,resolutions={},question_decision_id=None,question_context=None,acceptance=None,prepared_actor=None,prerequisites=[])
                        if frame['plan']:frame['phase']='plan-review'
                if 'capabilities' in payload:
                    caps=payload['capabilities'];require(isinstance(caps,dict) and type(caps.get('independent_actors')) is bool,'Resume requires explicit host capability facts');frame['capabilities']=deepcopy(caps)
                if payload.get('retry') or 'capabilities' in payload:frame['prerequisites']=[]
                if frame['owner_question']:
                    evidence=payload.get('owner_evidence');require(isinstance(evidence,dict) and evidence.get('kind') in {'owner-message','submitted-answer'} and text(evidence.get('reference')),'A persisted no-progress question requires actual owner input before resume');detail['owner_question']=deepcopy(frame['owner_question']);detail['owner_evidence']=deepcopy(evidence);frame['owner_question']=None
            elif command=='observe-failure':
                if not failure(frame,payload.get('code'),payload.get('reference')):return deepcopy(frame)
                detail={'code':payload['code'],'reference':payload['reference']}
            if detail is None:return deepcopy(frame)
            return write(store,frame,command,detail,buffer)
    except dg.DecisionError as error:raise OrchestrationError(str(error)) from error
