"""Guarded decision metadata; queue binding and host observation belong to callers."""
from copy import deepcopy
import hashlib
import json
import re
import uuid


class DecisionError(ValueError):
    pass


COMMANDS={'decision-prepare','decision-record','decision-reconcile','decision-switch','decision-accept','decision-resume'}
KINDS={'product','technical','specification-acceptance'}
CONTEXTS={'request','project','pending','task','task-group','document','snapshot','management','controller','review','clarification'}
MODES={'auto','manual'}
TERMINAL={'answered','agree','disagree','failed','unavailable','cancelled'}
SHA=re.compile(r'^[a-f0-9]{64}$')
DG=re.compile(r'^DG-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')


def _require(condition,message):
    if not condition:raise DecisionError(message)


def _text(value):
    return isinstance(value,str) and bool(value.strip())


def _json(value):
    try:return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    except (ValueError,TypeError) as error:raise DecisionError('Decision data must be finite JSON') from error


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _actor(value):
    _require(isinstance(value,dict) and set(value)=={'id','context_id'} and all(_text(v) for v in value.values()),'An actor requires an exact identity and independent context')
    return deepcopy(value)


def validate_context(context):
    _require(isinstance(context,dict),'A typed decision context is required')
    _require(context.get('kind') in CONTEXTS and _text(context.get('id')),'Unknown or missing decision context identity')
    _require(all(isinstance(context.get(key),str) and SHA.fullmatch(context[key]) for key in ('semantic_fingerprint','content_fingerprint')),'Context requires current semantic and content SHA256 fingerprints')
    allowed={'pending':{'pending_ids'},'task':{'task_ids','pending_ids'},'task-group':{'task_ids','pending_ids'},'controller':{'task_ids'},'review':{'task_ids'}}.get(context['kind'],set())
    for key in ('task_ids','pending_ids'):
        if key in context:
            _require(key in allowed,'Task identity fields do not apply to the selected context kind')
            values=context[key];prefix='T-' if key=='task_ids' else 'P-'
            _require(isinstance(values,list) and values and all(_typed_id(v,prefix) for v in values) and len(values)==len(set(values)),'Context scope requires distinct typed identities')
    if context['kind'] in {'task','task-group'}:_require(context.get('task_ids'),'Task contexts require task identities')
    if context['kind']=='task':_require(len(context['task_ids'])==1,'A single-task context requires exactly one selected task')
    if context['kind']=='pending':_require(context.get('pending_ids'),'Pending contexts require Pending identities')
    if context['kind']=='controller':_require(_typed_id(context.get('run_id'),'WR-'),'A controller context requires an actual run identity')
    if 'purpose' in context:
        purpose=context['purpose'];_require(isinstance(purpose,str) and re.fullmatch('[a-z][a-z0-9-]*',purpose),'Decision purpose requires a bounded kebab identifier')
        if 'session_id' in context:_require(purpose in {'answer','confirmation'},'Unknown clarification decision purpose')
    for key in ('question_revision','parent_mode_epoch'):
        if key in context:_require(type(context[key]) is int and context[key]>=0,'Invalid context revision or epoch')
    for key in ('path','document_path'):
        if key in context:_require(_relative_path(context[key]),'Context paths must be repository-relative')
    if context['kind'] in {'document','snapshot'} or 'paths' in context:
        paths=context.get('paths');_require(isinstance(paths,list) and paths and all(_relative_path(value) for value in paths),'Document and snapshot contexts require bounded repository-relative paths')
    if context['kind']=='review':
        _require(all(isinstance(context.get(key),str) and re.fullmatch('(?:[a-f0-9]{40}|[a-f0-9]{64})',context[key]) for key in ('head','base_oid')),'Review decisions require immutable head and base identities')
    _json(context);return deepcopy(context)


def _typed_id(value,prefix):
    return isinstance(value,str) and bool(re.fullmatch(re.escape(prefix)+r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value))


def _relative_path(value):
    return _text(value) and not value.startswith(('/','\\')) and not re.match(r'^[A-Za-z]:',value) and '\\' not in value and '\0' not in value and '..' not in value.split('/')


def validate_authority(authority,context,mode):
    _require(mode in MODES,'Unknown decision mode')
    _require(isinstance(authority,dict),'A bounded owner authority grant is required')
    _require(_text(authority.get('id')) and type(authority.get('revision')) is int and authority['revision']>0,'Authority requires an identity and positive revision')
    _require(authority.get('context_id')==context['id'],'Authority belongs to another decision scope')
    allowed=authority.get('allowed_kinds')
    _require(isinstance(allowed,list) and all(isinstance(v,str) and v in KINDS for v in allowed) and len(allowed)==len(set(allowed)),'Authority cannot delegate reserved actions or wildcard permissions')
    constraints=authority.get('constraints')
    _require(isinstance(constraints,list) and constraints and all(_text(v) for v in constraints),'Authority requires bounded constraints')
    evidence=authority.get('evidence')
    _require(isinstance(evidence,dict) and evidence.get('kind') in {'owner-message','submitted-answer'} and _text(evidence.get('reference')),'Authority requires owner-origin evidence, never an agent recommendation')
    if 'revoked' in authority:_require(type(authority['revoked']) is bool,'Authority revocation must be explicit')
    _json(authority);return deepcopy(authority)


def _question(value):
    _require(isinstance(value,dict) and _text(value.get('id')) and _text(value.get('text')) and value.get('kind') in KINDS,'Question requires an identity, text and a nonreserved decision kind')
    options=value.get('options')
    _require(isinstance(options,list) and options and all(isinstance(v,dict) and _text(v.get('id')) and _text(v.get('text')) for v in options),'Question requires explicit answer options')
    ids=[v['id'] for v in options]
    _require(len(ids)==len(set(ids)) and value.get('recommendation') in ids,'Question options must be unique and include the recommendation')
    _require(value.get('significance','routine') in {'routine','significant'},'Unknown question significance')
    _json(value);return deepcopy(value)


def _path(store,decision_id):
    _require(isinstance(decision_id,str) and DG.fullmatch(decision_id),'An exact DG identity is required')
    path=store.owned('.skill-tree/decisions/'+decision_id.lower()+'.json')
    _require(not path.is_symlink() and not path.parent.is_symlink(),'Decision metadata cannot use symlinks')
    return path


def _raw(store,decision_id):
    path=_path(store,decision_id)
    _require(path.is_file(),'Unknown decision identity')
    try:record=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:raise DecisionError('Unreadable decision metadata') from error
    _require(isinstance(record,dict) and record.get('schema')==1 and record.get('id')==decision_id,'Unsupported decision metadata')
    _require(record.get('decision_hash')==_hash({k:v for k,v in record.items() if k!='decision_hash'}),'Decision metadata checksum differs')
    _require(record.get('mode') in MODES and type(record.get('revision')) is int and record['revision']>0 and type(record.get('mode_epoch')) is int and record['mode_epoch']>0,'Invalid decision revision or mode')
    validate_context(record['context']);_question(record['question']);validate_authority(record['authority'],record['context'],record['mode']);_actor(record['executor'])
    _require(record.get('authority_digest')==_hash(record['authority']) and isinstance(record.get('attempts'),dict) and isinstance(record.get('history'),list),'Invalid authority or decision history')
    if record.get('acceptance') is not None:
        accepted=record['acceptance'];_require(isinstance(accepted,dict) and accepted.get('digest')==_hash({k:v for k,v in accepted.items() if k!='digest'}),'Acceptance checksum differs')
    return record


def read(store,decision_id):
    return deepcopy(_raw(store,decision_id))


def _commit(store,record,event,detail=None):
    previous=record.pop('decision_hash',None);record['revision']+=1
    record['history'].append({'sequence':record['revision'],'event':event,'mode_epoch':record['mode_epoch'],'context_fingerprint':record['context']['content_fingerprint'],'previous_record_hash':previous,'detail':deepcopy(detail or {})})
    record['decision_hash']=_hash(record)
    path=_path(store,record['id']);relative=path.relative_to(store.root).as_posix()
    if hasattr(store,'_write_hashes') and relative not in store._write_hashes:store._write_hashes[relative]=None
    store.commit({relative:json.dumps(record,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n'})
    return deepcopy(record)


def _permitted(record):
    return not record['authority'].get('revoked',False) and record['question']['kind'] in record['authority']['allowed_kinds']


def start(store,payload):
    _require(isinstance(payload,dict) and _text(payload.get('request_id')),'Decision start requires a stable request identity')
    context=validate_context(payload.get('context'));question=_question(payload.get('question'));mode=payload.get('mode','manual')
    authority=validate_authority(payload.get('authority'),context,mode);executor=_actor(payload.get('executor'))
    initial={'request_id':payload['request_id'],'context':context,'question':question,'mode':mode,'authority':authority,'executor':executor}
    decision_id='DG-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-tree-decision:'+payload['request_id']))
    with store.lock():
        path=_path(store,decision_id)
        if path.exists():
            record=_raw(store,decision_id);_require(record['start_digest']==_hash(initial),'Decision request identity was reused for different inputs');return deepcopy(record)
        record={'schema':1,'id':decision_id,'revision':0,'mode':mode,'mode_epoch':1,'frontier_epoch':1,'authority_digest':_hash(authority),'state':'open','attempts':{},'active_attempt_id':None,'prepared_attempt_id':None,'history':[],'acceptance':None,'start_digest':_hash(initial),**initial}
        if not _permitted(record):record['state']='blocked'
        return _commit(store,record,'started')


def _guard(record,payload):
    expected={'expected_decision_hash':record['decision_hash'],'expected_decision_revision':record['revision'],'expected_mode_epoch':record['mode_epoch'],'expected_context_fingerprint':record['context']['content_fingerprint']}
    _require(all(payload.get(key)==value for key,value in expected.items()),'Decision bytes, revision, mode epoch or context changed; reread before mutation')


def _identity(context):
    return {k:v for k,v in context.items() if k not in {'semantic_fingerprint','content_fingerprint'}}


def _matches(record,attempt):
    return attempt['mode']==record['mode'] and attempt['mode_epoch']==record['mode_epoch'] and attempt['frontier_epoch']==record['frontier_epoch'] and attempt['authority_digest']==record['authority_digest'] and attempt['semantic_fingerprint']==record['context']['semantic_fingerprint'] and attempt['question_digest']==_hash(record['question'])


def _roles(record):
    return {attempt['role']:attempt for attempt in record['attempts'].values() if _matches(record,attempt) and attempt['status'] in {'answered','agree','disagree'}}


def _receipt(attempt):
    return _hash({'id':attempt['id'],'result':attempt.get('result'),'evidence':attempt.get('evidence'),'basis_digest':attempt['basis_digest']})


def _basis(record,role):
    roles=_roles(record)
    if role in {'resolver','owner'}:return None
    resolver=roles.get('resolver');_require(resolver and resolver['status']=='answered','A current resolver answer is required before independent review')
    basis={'resolver':_receipt(resolver)}
    if role=='arbiter':
        critic=roles.get('critic');_require(critic and critic['status']=='disagree','A substantive current critic disagreement requires arbitration');basis['critic']=_receipt(critic)
    return _hash(basis)


def _pending(record):
    return any(attempt['status']=='pending' for attempt in record['attempts'].values())


def _prepare(record,payload):
    _require(_permitted(record),'Decision is outside the current authority grant; request owner clarification')
    _require(not _pending(record),'Reconcile the original pending actor before another attempt')
    _require(record['acceptance'] is None,'Accepted decisions require explicit context or authority reconciliation')
    role=payload.get('role');_require(role in ({'owner'} if record['mode']=='manual' else {'resolver','critic','arbiter'}),'Role cannot replace the current mode authority')
    actor=_actor(payload.get('actor'));roles=_roles(record)
    _require(role not in roles,'A settled role cannot be replaced within the current decision frontier')
    if record['mode']=='auto':
        others=[record['executor']]+[a['actor'] for a in record['attempts'].values() if _matches(record,a)]
        _require(all(actor['id']!=other['id'] and actor['context_id']!=other['context_id'] for other in others),'Decision roles require separate actual actor identities and contexts')
    basis=_basis(record,role);attempt_id='DA-'+str(uuid.uuid4())
    record['attempts'][attempt_id]={'id':attempt_id,'role':role,'actor':actor,'mode':record['mode'],'mode_epoch':record['mode_epoch'],'frontier_epoch':record['frontier_epoch'],'authority_digest':record['authority_digest'],'semantic_fingerprint':record['context']['semantic_fingerprint'],'content_fingerprint':record['context']['content_fingerprint'],'question_digest':_hash(record['question']),'basis_digest':basis,'status':'pending'}
    record.update(active_attempt_id=attempt_id,prepared_attempt_id=attempt_id,state='awaiting-owner' if role=='owner' else 'awaiting-actor')
    return {'attempt_id':attempt_id,'role':role}


def _record(record,payload):
    attempt=record['attempts'].get(payload.get('attempt_id'));_require(attempt is not None,'Unknown original decision attempt')
    _require(_matches(record,attempt) and attempt['content_fingerprint']==record['context']['content_fingerprint'],'Original actor inputs are stale; reconcile the original attempt')
    result=payload.get('result');evidence=payload.get('evidence')
    _require(isinstance(result,dict) and result.get('status') in TERMINAL and _text(result.get('rationale')),'Actor result requires an explicit outcome and rationale')
    _require(isinstance(evidence,dict) and _text(evidence.get('reference')),'Actor result requires traceable evidence')
    role=attempt['role'];owner=role=='owner'
    _require(evidence.get('kind') in ({'owner-message','submitted-answer'} if owner else {'delegated-agent'}),'Result provenance differs from the current mode and original actor')
    for key,field in [('actor_id','id'),('actor_context_id','context_id')]:
        _require((owner and key not in evidence) or evidence.get(key)==attempt['actor'][field],'Result came from another actor identity or context')
    status=result['status']
    _require(status in ({'agree','disagree','unavailable','failed','cancelled'} if role=='critic' else {'answered','unavailable','failed','cancelled'}),'Result outcome is invalid for the original role')
    if status=='answered' or 'answer' in result:_require(result.get('answer') in {v['id'] for v in record['question']['options']},'Answer must reference a declared option')
    if role=='critic' and status=='agree' and 'answer' in result:
        _require(result['answer']==_roles(record)['resolver']['result']['answer'],'Critic agreement cannot name another resolver candidate')
    _json(result);_json(evidence)
    if attempt['status']!='pending':
        _require(attempt.get('result')==result and attempt.get('evidence')==evidence,'Conflicting replay cannot replace an original actor result');return None
    _require(attempt['basis_digest']==_basis(record,role),'Actor result refers to another resolver or disagreement receipt')
    attempt.update(status=status,result=deepcopy(result),evidence=deepcopy(evidence));record['active_attempt_id']=None;record['state']='open'
    return {'attempt_id':attempt['id'],'status':status}


def _reconcile(record,payload):
    attempt=record['attempts'].get(payload.get('attempt_id'));_require(attempt is not None and attempt['status']=='pending','Only the original pending attempt can be reconciled')
    status=payload.get('status');evidence=payload.get('evidence')
    _require(status in {'cancelled','failed','unavailable'} and isinstance(evidence,dict) and evidence.get('kind')=='actor-reconciliation' and _text(evidence.get('reference')),'Reconciliation requires an explicit original-actor outcome and evidence')
    attempt.update(status=status,reconciliation=deepcopy(evidence));record['active_attempt_id']=None;record['state']='open' if _permitted(record) else 'blocked'
    return {'attempt_id':attempt['id'],'status':status}


def _invalidate(record):
    previous=record.get('acceptance');record['acceptance']=None;record['state']='open' if _permitted(record) else 'blocked';return deepcopy(previous)


def _switch(record,payload):
    _require(not _pending(record),'Reconcile pending original actors before changing decision authority')
    mode=payload.get('mode');authority=validate_authority(payload.get('authority',record['authority']),record['context'],mode)
    if mode==record['mode'] and authority==record['authority']:return None
    previous={'mode':record['mode'],'mode_epoch':record['mode_epoch'],'authority':deepcopy(record['authority']),'acceptance':deepcopy(record['acceptance'])}
    record.update(mode=mode,mode_epoch=record['mode_epoch']+1,authority=authority,authority_digest=_hash(authority));_invalidate(record)
    return previous


def _resume(record,payload):
    _require(not _pending(record),'Reconcile original actors before resuming changed context')
    context=validate_context(payload.get('context'));_require(_identity(context)==_identity(record['context']),'Resume cannot substitute another scope, question binding or parent epoch')
    question=_question(payload.get('question',record['question']));_require(question['id']==record['question']['id'],'Resume cannot substitute another question identity')
    if context==record['context'] and question==record['question']:return None
    detail={'previous_context':deepcopy(record['context']),'previous_question':deepcopy(record['question'])}
    substantive=context['semantic_fingerprint']!=record['context']['semantic_fingerprint'] or question!=record['question']
    record.update(context=context,question=question)
    if substantive:
        record['frontier_epoch']+=1;detail['previous_acceptance']=_invalidate(record)
    return detail


def _selected(record):
    _require(_permitted(record) and not _pending(record),'Current authority and reconciled actor state are required for acceptance')
    roles=_roles(record);role='owner' if record['mode']=='manual' else 'resolver';answer=roles.get(role)
    attempted={attempt['role'] for attempt in record['attempts'].values() if _matches(record,attempt)}
    _require(attempted<=set(roles),'An explicitly attempted actor role remains unresolved until successful retry or explicit reconciliation')
    _require(answer is not None and answer['status']=='answered','Current mode requires an actual completed answer')
    if record['mode']=='auto':
        critic=roles.get('critic')
        if record['question'].get('significance','routine')=='significant':_require(critic is not None,'Significant decisions require an independent current critic')
        if critic:
            _require(critic['basis_digest']==_basis(record,'critic'),'Critic evidence belongs to another candidate')
            if critic['status']=='disagree':
                answer=roles.get('arbiter');_require(answer is not None and answer['status']=='answered' and answer['basis_digest']==_basis(record,'arbiter'),'Current substantive disagreement requires an independent arbiter')
    return answer,roles


def _accept(record,payload):
    answer,roles=_selected(record)
    if record['acceptance'] is not None:return None
    accepted={'decision_id':record['id'],'kind':record['question']['kind'],'question_id':record['question']['id'],'question_digest':_hash(record['question']),'context_identity':_identity(record['context']),'semantic_fingerprint':record['context']['semantic_fingerprint'],'mode':record['mode'],'mode_epoch':record['mode_epoch'],'authority_digest':record['authority_digest'],'answer':answer['result']['answer'],'rationale':answer['result']['rationale'],'origin':deepcopy(answer['evidence']),'actor':deepcopy(answer['actor']),'attempt_id':answer['id'],'role_receipts':{role:_receipt(attempt) for role,attempt in roles.items()}}
    accepted['digest']=_hash(accepted);record.update(acceptance=accepted,state='accepted');return {'acceptance_digest':accepted['digest']}


def mutate(store,command,payload):
    if not command.startswith('decision-'):command='decision-'+command
    _require(command in COMMANDS and isinstance(payload,dict),'Unknown decision mutation')
    handlers={'decision-prepare':_prepare,'decision-record':_record,'decision-reconcile':_reconcile,'decision-switch':_switch,'decision-resume':_resume,'decision-accept':_accept}
    with store.lock():
        record=_raw(store,payload.get('decision_id'));_guard(record,payload);detail=handlers[command](record,payload)
        if detail is None:return deepcopy(record)
        return _commit(store,record,command[9:],detail)


def acceptance_reference(store,reference,expected):
    _require(isinstance(reference,dict) and isinstance(expected,dict),'An exact acceptance reference and current context are required')
    record=_raw(store,reference.get('decision_id'));accepted=record.get('acceptance')
    _require(accepted is not None and reference.get('acceptance_digest')==accepted['digest'],'Unknown or invalidated decision acceptance')
    context=validate_context(expected.get('context'))
    _require(_identity(context)==_identity(record['context']) and context['semantic_fingerprint']==record['context']['semantic_fingerprint'],'Acceptance context differs from the current decision scope or semantics')
    _require(accepted['context_identity']==_identity(context) and accepted['semantic_fingerprint']==context['semantic_fingerprint'] and accepted['question_digest']==_hash(record['question']),'Acceptance semantics or question differs')
    _require(expected.get('mode')==record['mode']==accepted['mode'] and accepted['mode_epoch']==record['mode_epoch'],'Acceptance belongs to an old mode epoch')
    if 'mode_epoch' in expected:_require(expected['mode_epoch']==record['mode_epoch'],'Acceptance mode epoch differs')
    _require(expected.get('authority_digest')==record['authority_digest']==accepted['authority_digest'] and _permitted(record),'Acceptance authority is stale, revoked or outside the grant')
    _require(expected.get('kind')==record['question']['kind']==accepted['kind'],'An answer cannot substitute another acceptance purpose')
    answer,roles=_selected(record)
    _require(accepted['attempt_id']==answer['id'] and accepted['role_receipts']=={role:_receipt(attempt) for role,attempt in roles.items()},'Acceptance evidence differs from the current decision frontier')
    return deepcopy(accepted)
