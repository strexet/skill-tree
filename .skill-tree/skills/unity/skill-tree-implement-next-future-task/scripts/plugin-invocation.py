"""Pure invocation metadata; callers own host execution and guarded core changes."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import uuid


class InvocationError(ValueError):
    pass


SHA=re.compile(r'^[a-f0-9]{64}$')
HC=re.compile(r'^HC-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
HI=re.compile(r'^HI-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$')
KINDS={'request','project','document','snapshot','management','controller','pending','task','task-group','review'}
PENDING={'prepared','invoking','unknown'}
OUTCOMES={'passed','findings','questions','failed','unavailable','cancelled'}
COMMANDS={'prepare','invoke','record','accept','reconcile','resume'}


def require(condition,message):
    if not condition:raise InvocationError(message)


def text(value):return isinstance(value,str) and bool(value.strip())


def clone(value):
    def keys(item,seen):
        if isinstance(item,(dict,list)):
            require(id(item) not in seen,'Invocation data must be finite acyclic JSON');seen.add(id(item))
            if isinstance(item,dict):
                require(all(isinstance(key,str) for key in item),'Invocation JSON object keys must be strings')
                for part in item.values():keys(part,seen)
            else:
                for part in item:keys(part,seen)
            seen.remove(id(item))
    keys(value,set())
    try:return json.loads(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False))
    except (ValueError,TypeError,OverflowError) as error:raise InvocationError('Invocation data must be finite JSON') from error


def digest(value):
    return hashlib.sha256(json.dumps(clone(value),sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def relative(value):
    return text(value) and not value.startswith(('/','\\')) and not re.match(r'^[A-Za-z]:',value) and '\\' not in value and '\0' not in value and all(part not in {'','..','.'} for part in value.split('/'))


def identity(value,prefix):return isinstance(value,str) and re.fullmatch(re.escape(prefix)+r'-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value) is not None


def context(value):
    value=clone(value);require(isinstance(value,dict) and value.get('kind') in KINDS and text(value.get('id')),'An actual typed operation context is required')
    require(all(isinstance(value.get(key),str) and SHA.fullmatch(value[key]) for key in ['semantic_fingerprint','content_fingerprint']),'Current semantic and content fingerprints are required')
    kind=value['kind'];allowed={'pending':{'pending_ids'},'task':{'task_ids','pending_ids'},'task-group':{'task_ids','pending_ids'},'controller':{'task_ids'},'review':{'task_ids'}}.get(kind,set())
    for key,prefix in [('task_ids','T'),('pending_ids','P')]:
        if key in value:
            ids=value[key];require(key in allowed and isinstance(ids,list) and ids and all(identity(item,prefix) for item in ids) and len(ids)==len(set(ids)),'Context must retain distinct actual task or Pending identities')
    if kind=='pending':require(value.get('pending_ids'),'Pending context requires real selected P identities')
    if kind in {'task','task-group'}:require(value.get('task_ids'),'Task context requires real selected T identities')
    if kind=='task':require(len(value['task_ids'])==1,'A single task context requires exactly one task')
    if kind=='controller':require(identity(value.get('run_id'),'WR'),'Controller context requires a recorded run identity')
    if kind=='review':require(all(isinstance(value.get(key),str) and re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})',value[key]) for key in ['head','base_oid']),'Review context requires immutable current head and base')
    for key in ['path','document_path']:
        if key in value:require(relative(value[key]),'Operation paths must remain repository-relative')
    if kind in {'document','snapshot'} or 'paths' in value:require(isinstance(value.get('paths'),list) and value['paths'] and all(relative(item) for item in value['paths']),'Document scope requires bounded paths')
    return value


def actor(value):
    require(isinstance(value,dict) and set(value)=={'id','context_id'} and all(text(item) for item in value.values()),'An actual actor and context identity are required');return clone(value)


def event(value):
    value=clone(value);require(isinstance(value,dict) and all(text(value.get(key)) for key in ['id','operation','anchor']),'An exact operation event and anchor identity are required')
    for key in ['attempt_id','boundary_id']:
        if key in value:require(text(value[key]),'Event identities cannot be empty')
    return value


def authority(value,ctx,mode):
    value=clone(value);require(mode in {'auto','manual'} and isinstance(value,dict),'A frozen decision mode and bounded owner grant are required')
    require(text(value.get('id')) and type(value.get('revision')) is int and value['revision']>0 and value.get('context_id')==ctx['id'],'The owner authority must identify the actual scope')
    allowed=value.get('allowed_kinds');require(isinstance(allowed,list) and all(isinstance(item,str) and item in {'technical','product','specification-acceptance'} for item in allowed) and len(allowed)==len(set(allowed)),'Plugin invocation cannot delegate reserved authority')
    require(isinstance(value.get('constraints'),list) and value['constraints'] and all(text(item) for item in value['constraints']),'The authority requires explicit constraints')
    evidence=value.get('evidence');require(isinstance(evidence,dict) and evidence.get('kind') in {'owner-message','submitted-answer'} and text(evidence.get('reference')),'The invocation grant requires actual owner-origin evidence')
    if 'revoked' in value:require(type(value['revoked']) is bool,'Authority revocation must be explicit')
    return value


def configuration(value,operation):
    value=clone(value);require(isinstance(value,dict) and isinstance(value.get('configuration_digest'),str) and SHA.fullmatch(value['configuration_digest']),'An owned Node configuration digest is required')
    rows=value.get('bindings');packages=value.get('packages');require(isinstance(rows,list) and isinstance(packages,dict),'Frozen ordered bindings and package identities are required')
    seen=set()
    for row in rows:
        require(isinstance(row,dict) and text(row.get('id')) and row['id'] not in seen,'Binding occurrences require distinct stable identities');seen.add(row['id'])
        require(row.get('operation')==operation and text(row.get('anchor')) and type(row.get('enabled')) is bool,'Binding occurrence belongs to another operation or lacks explicit enabled state')
        plugin=row.get('plugin_id');require(text(plugin) and plugin in packages,'A binding requires a pinned package identity');package=packages[plugin]
        require(isinstance(package,dict) and text(package.get('revision')) and isinstance(package.get('content_digest'),str) and SHA.fullmatch(package['content_digest']) and relative(package.get('entry')),'The plugin package revision and entry must be pinned')
        resources=package.get('resources',package.get('files'));require(isinstance(resources,dict) and resources and all(relative(key) and isinstance(item,str) and SHA.fullmatch(item) for key,item in resources.items()),'A package requires the declared resource digest closure')
        declared=row.get('package_identity',{})
        require(isinstance(declared,dict) and all(key not in declared or declared[key]==package[key] for key in ['revision','content_digest']),'Compiled package identity differs from the frozen package')
        effective=row.get('effective');require(isinstance(effective,dict) and 'values' in effective and isinstance(effective.get('instructions'),str) and isinstance(effective.get('digest'),str) and SHA.fullmatch(effective['digest']),'The owned Node effective values, instructions and digest are required')
        secrets=effective.get('secretReferences',[]);require(isinstance(secrets,list) and all(text(item) for item in secrets),'Secret references require stable names')
        require(not any(key in row for key in ['authority','context','event','attempt_id','delivery_key','input_digest']),'Binding data cannot replace core identity or authority')
    if 'run_overrides' in value:require(isinstance(value['run_overrides'],dict),'Explicit run overrides require a frozen identity map')
    return value


def snapshot(value):
    require(isinstance(value,dict) and all(text(key) and (item is None or isinstance(item,str) and SHA.fullmatch(item)) for key,item in value.items()),'Execution inputs require a frozen SHA256/null map');return clone(value)


def scope_snapshot(value):
    value=snapshot(value);require(all(relative(key) for key in value),'Scoped source snapshots require repository-relative file paths');return value


def attempt_sources(attempt,proof):
    require(isinstance(proof,dict),'A current owned scoped-source proof is required')
    require(scope_snapshot(proof.get('scope_source_snapshot',{}))==scope_snapshot(attempt['input'].get('scope_source_snapshot',{})),'The original invocation declared source bytes changed; reconcile or explicitly retry against current sources')


def location(store,chain_id):
    require(isinstance(chain_id,str) and HC.fullmatch(chain_id),'An exact HC chain identity is required');path=store.owned('.skill-tree/invocations/'+chain_id.lower()+'.json')
    require(not path.is_symlink() and not path.parent.is_symlink(),'Invocation metadata cannot use symlinks');return path


def raw(store,chain_id):
    path=location(store,chain_id);require(path.is_file(),'Unknown invocation chain')
    try:
        contents=path.read_bytes();value=json.loads(contents)
    except (OSError,ValueError) as error:raise InvocationError('Unreadable invocation chain') from error
    require(isinstance(value,dict) and value.get('schema')==1 and value.get('id')==chain_id and value.get('chain_hash')==digest({key:item for key,item in value.items() if key!='chain_hash'}),'Unsupported or modified invocation chain')
    require(type(value.get('revision')) is int and value['revision']>0 and value.get('state') in {'active','blocked','complete','superseded'},'Invalid invocation revision or state')
    require({'context','initial_context','authority','mode','executor','event','configuration','execution_snapshot','stages','attempts','cursor','prepared_attempt_id','history'}<=set(value),'Invocation metadata lacks required state fields')
    require(isinstance(value['history'],list),'Invocation history must be retained')
    ctx=context(value['context']);context(value['initial_context']);authority(value['authority'],value['initial_context'],value['mode']);actor(value['executor']);ev=event(value['event']);config=configuration(value['configuration'],ev['operation']);snapshot(value['execution_snapshot'])
    rows=config['bindings'];stages=value.get('stages');attempts=value.get('attempts');cursor=value.get('cursor')
    require(isinstance(stages,list) and len(stages)==len(rows) and isinstance(attempts,dict) and type(cursor) is int and 0<=cursor<=len(stages),'Invalid ordered occurrence frontier')
    for index,(stage,row) in enumerate(zip(stages,rows)):
        require(isinstance(stage,dict) and stage.get('index')==index and stage.get('binding_id')==row['id'] and isinstance(stage.get('attempt_ids'),list),'Occurrence identity differs from the frozen order')
        require(stage.get('status') in {'pending','skipped','prepared','invoking','awaiting-acceptance','complete','blocked'},'Unknown occurrence state')
        require(index>=cursor or stage['status'] in {'skipped','complete'},'Completed prefix is not satisfied')
        for original in stage['attempt_ids']:require(identity(original,'HI') and original in attempts and attempts[original].get('index')==index,'Occurrence original attempt is missing')
    for original,attempt in attempts.items():
        require(identity(original,'HI') and isinstance(attempt,dict) and attempt.get('id')==original and type(attempt.get('index')) is int and 0<=attempt['index']<len(stages),'Invalid original attempt identity')
        require(attempt.get('binding_id')==rows[attempt['index']]['id'] and original in stages[attempt['index']]['attempt_ids'],'Attempt belongs to another occurrence')
        require(attempt.get('status') in PENDING|{'returned','failed','unavailable','cancelled'},'Unknown original attempt status');actor(attempt['actor'])
        require(isinstance(attempt.get('input'),dict) and attempt.get('input_digest')==digest(attempt['input']),'The original public sealed input changed');scope_snapshot(attempt['input'].get('scope_source_snapshot',{}))
        if attempt['input'].get('attempt_id')!=original or attempt['input'].get('chain_id')!=chain_id:raise InvocationError('Original sealed input belongs to another invocation')
    require(value.get('prepared_attempt_id') is None or identity(value.get('prepared_attempt_id'),'HI') and value['prepared_attempt_id'] in attempts,'The current original attempt is missing')
    require(value['state']!='complete' or cursor==len(stages),'A chain cannot complete before every occurrence');require(text(value.get('request_id')) and isinstance(value.get('start_digest'),str) and SHA.fullmatch(value['start_digest']),'Stable start identity is missing')
    if value['state']=='superseded':require(identity(value.get('superseded_by'),'HC') and value['superseded_by']!=value['id'],'A superseded chain requires its exact distinct replacement')
    return value


def read(store,chain_id):return clone(raw(store,chain_id))


def encoded_write(store,chain,command,detail=None):
    old=chain.pop('chain_hash',None);chain['revision']+=1;chain['history'].append({'sequence':chain['revision'],'event':command,'previous_chain_hash':old,'detail':clone(detail or {})});chain['chain_hash']=digest(chain)
    path=location(store,chain['id']);relative_path=path.relative_to(store.root).as_posix()
    if old is None:
        require(callable(getattr(store,'expect_unchanged',None)),'New invocation metadata requires compare-and-swap Store registration');store.expect_unchanged(relative_path,None)
    return {relative_path:json.dumps(chain,sort_keys=True,ensure_ascii=True,indent=2,allow_nan=False)+'\n'}


def write(store,chain,command,detail=None):
    store.commit(encoded_write(store,chain,command,detail));return clone(chain)


def proof_check(chain,proof,*,context_value=None,allow_snapshot=False):
    require(isinstance(proof,dict),'A trusted owned preparation proof is required')
    require(proof.get('configuration_digest')==chain['configuration']['configuration_digest'],'The frozen effective configuration changed')
    require(proof.get('event')==chain['event'],'The current operation event changed')
    current=context(proof.get('context'));require(current==(context_value if context_value is not None else chain['context']),'The current accepted context changed')
    actual=snapshot(proof.get('execution_snapshot'));require(allow_snapshot or actual==chain['execution_snapshot'],'Execution source/profile changed; reconcile originals and explicitly resume')
    rows=proof.get('bindings');require(isinstance(rows,list) and isinstance(proof.get('unresolved',[]),list) and isinstance(proof.get('prerequisites',[]),list),'The owned selection proof is incomplete')
    configured={row['id']:row for row in chain['configuration']['bindings']};seen=set()
    for row in rows:
        require(isinstance(row,dict) and text(row.get('id')) and row.get('id') in configured and row['id'] not in seen and row==configured[row['id']],'A selected occurrence differs from frozen definitions');seen.add(row['id'])
    return current


def start(store,payload,*,proof,verify_supersession=None,guard=None):
    payload=clone(payload);require(isinstance(payload,dict) and text(payload.get('request_id')),'A stable invocation request identity is required')
    ev=event(payload.get('event'));ctx=context(payload.get('context'));mode=payload.get('mode','auto');grant=authority(payload.get('authority'),ctx,mode);executor=actor(payload.get('executor'));config=configuration(payload.get('configuration'),ev['operation'])
    require(not grant.get('revoked',False),'A revoked owner grant cannot start plugin execution')
    lineage=clone(payload.get('lineage',[]));require(isinstance(lineage,list),'Active invocation lineage must be an ordered list')
    inputs={'request_id':payload['request_id'],'event':ev,'context':ctx,'mode':mode,'authority':grant,'executor':executor,'configuration':config,'initial_lineage':lineage}
    if 'supersedes_chain_id' in payload:inputs['supersedes_chain_id']=payload['supersedes_chain_id']
    chain={'schema':1,'id':'HC-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-tree-invocation:'+payload['request_id'])),'revision':0,'state':'active' if config['bindings'] else 'complete','initial_context':clone(ctx),'execution_snapshot':snapshot(proof.get('execution_snapshot')) if isinstance(proof,dict) else {},'cursor':0,'stages':[{'index':index,'binding_id':row['id'],'status':'pending','attempt_ids':[],'accepted_context':None,'accepted_transition':None} for index,row in enumerate(config['bindings'])],'attempts':{},'prepared_attempt_id':None,'history':[],'epoch':1,'prerequisites':[],'start_digest':digest(inputs),**inputs}
    proof_check(chain,proof)
    with store.lock():
        if guard is not None:guard(clone(chain),'start',clone(payload))
        if location(store,chain['id']).exists():
            previous=raw(store,chain['id']);require(previous['start_digest']==chain['start_digest'],'Invocation request identity was reused for different inputs');return clone(previous)
        if payload.get('supersedes_chain_id'):
            old=raw(store,payload['supersedes_chain_id']);require(old['id']!=chain['id'] and old['state']!='superseded','A chain cannot supersede itself or an already replaced chain')
            require(payload.get('expected_predecessor_hash')==old['chain_hash'] and payload.get('expected_predecessor_revision')==old['revision'],'The original predecessor hash or revision changed during configuration adoption')
            require(not any(item['status'] in PENDING for item in old['attempts'].values()),'Reconcile original predecessor invocations before configuration adoption')
            for key in ['kind','id','task_ids','pending_ids','run_id','session_id']:
                require(chain['context'].get(key)==old['context'].get(key),'Configuration adoption cannot substitute another operation scope')
            for key in ['operation','anchor','boundary_id']:
                require(chain['event'].get(key)==old['event'].get(key),'Configuration adoption must retain the actual boundary')
            require(verify_supersession is not None,'Configuration adoption requires actual core authorization')
            receipt=verify_supersession(clone(old),clone(payload),clone(payload.get('supersession_receipt')))
            require(isinstance(receipt,dict) and receipt.get('kind')=='configuration-adoption' and text(receipt.get('reference')) and receipt.get('before_configuration_digest')==old['configuration']['configuration_digest'] and receipt.get('after_configuration_digest')==chain['configuration']['configuration_digest'],'The core configuration adoption receipt differs')
            old.update(state='superseded',superseded_by=chain['id'],supersession_receipt=clone(receipt));chain['supersession_receipt']=clone(receipt)
            writes=encoded_write(store,old,'superseded',{'replacement_chain_id':chain['id'],'receipt':receipt});writes.update(encoded_write(store,chain,'start',{'supersedes_chain_id':old['id'],'receipt':receipt}));store.commit(writes);return clone(chain)
        return write(store,chain,'start')


def pending_scan(store):
    directory=store.owned('.skill-tree/invocations');require(not directory.is_symlink(),'Invocation directory cannot be a symlink');result=[]
    if directory.exists():
        require(directory.is_dir(),'The owned invocation metadata directory is invalid')
        for path in sorted(directory.glob('*.json')):
            require(re.fullmatch(r'hc-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json',path.name),'Unrecognized owned invocation metadata requires recovery')
            chain=raw(store,'HC-'+path.stem[3:])
            if chain['state']=='superseded':require(location(store,chain['superseded_by']).is_file(),'A superseded invocation replacement is missing; explicit recovery is required')
            for attempt in chain['attempts'].values():
                if attempt['status'] in PENDING:result.append({'chain_id':chain['id'],'attempt_id':attempt['id'],'status':attempt['status'],'binding_id':attempt['binding_id']})
    return result


def current_attempt(chain):
    original=chain.get('prepared_attempt_id');return chain['attempts'].get(original) if original else None


def next_action(store,chain_id,*,proof=None):
    chain=raw(store,chain_id);base={'chain_id':chain['id'],'state':chain['state'],'cursor':chain['cursor'],'chain_hash':chain['chain_hash'],'revision':chain['revision']}
    if chain['authority'].get('revoked',False):return {**base,'action':'prerequisite','prerequisites':[{'code':'authority-revoked','reason':'Explicitly restore actual owner authority after original attempt reconciliation.'}]}
    if chain['state']=='complete':
        if proof is not None:
            try:proof_check(chain,proof)
            except InvocationError as error:return {**base,'action':'prerequisite','prerequisites':[{'code':'completed-chain-drift','reason':str(error)}]}
        return {**base,'action':'complete'}
    if chain['state']=='superseded':return {**base,'action':'superseded','replacement_chain_id':chain['superseded_by']}
    original=current_attempt(chain)
    if original:
        if proof is not None:
            try:attempt_sources(original,proof)
            except InvocationError as error:return {**base,'action':'prerequisite','attempt_id':original['id'],'prerequisites':[{'code':'scope-source-drift','reason':str(error)}]}
        if original['status'] in {'invoking','unknown'}:return {**base,'action':'wait-original','attempt_id':original['id']}
        if original['status']=='prepared':return {**base,'action':'invoke','attempt_id':original['id'],'input':clone(original['input']),'input_digest':original['input_digest']}
        if original['status']=='returned':return {**base,'action':'accept' if original['result']['status']=='passed' else 'resolve','attempt_id':original['id'],'result':clone(original['result'])}
        return {**base,'action':'prerequisite','attempt_id':original['id'],'prerequisites':[{'code':'original-'+original['status']}]}
    if proof is None:return {**base,'action':'prerequisite','prerequisites':[{'code':'preparation-proof-required'}]}
    try:proof_check(chain,proof)
    except InvocationError as error:return {**base,'action':'prerequisite','prerequisites':[{'code':'stale-preparation','reason':str(error)}]}
    if proof.get('prerequisites') or proof.get('unresolved'):return {**base,'action':'prerequisite','prerequisites':clone(proof.get('prerequisites',[])+proof.get('unresolved',[]))}
    return {**base,'action':'prepare','binding_id':chain['configuration']['bindings'][chain['cursor']]['id']}


def guards(chain,payload):
    require(payload.get('expected_chain_hash')==chain['chain_hash'] and payload.get('expected_chain_revision')==chain['revision'],'Invocation chain bytes or revision changed; reread before mutation')


def producer(value,kind,who,mechanism=False):
    require(isinstance(value,dict) and value.get('kind')==kind and all(text(value.get(key)) for key in ['provider','tool','reference']),'Actual host producer evidence is required')
    require(value.get('actor_id')==who['id'] and value.get('actor_context_id')==who['context_id'],'Host evidence belongs to another actor or context')
    if mechanism:require(value.get('mechanism')=='source-backed-context','The adapter cannot claim an unavailable native Skill invocation')
    return clone(value)


def prepare(chain,payload,proof):
    proof_check(chain,proof);require(not chain['authority'].get('revoked'),'The bounded invocation authority has been revoked');require(not current_attempt(chain),'Reconcile or accept the original occurrence before preparing another attempt')
    require(not proof.get('unresolved') and not proof.get('prerequisites'),'The owned boundary still has unresolved prerequisites')
    selected={row['id'] for row in proof['bindings']};rows=chain['configuration']['bindings']
    while chain['cursor']<len(rows):
        stage=chain['stages'][chain['cursor']];row=rows[chain['cursor']]
        if row['enabled'] and row['id'] in selected:break
        stage.update(status='skipped',accepted_context=clone(chain['context']),accepted_transition={'before':clone(chain['context']),'after':clone(chain['context']),'receipt':{'kind':'not-selected','reference':'owned-condition-selection','before':digest(chain['context']),'after':digest(chain['context'])}});chain['cursor']+=1
    if chain['cursor']==len(rows):chain['state']='complete';return {'skipped_to_completion':True}
    row=rows[chain['cursor']];who=actor(payload.get('actor'));require(who['id']!=chain['executor']['id'] and who['context_id']!=chain['executor']['context_id'],'Source-backed invocation requires an isolated actor context')
    require(not any(item['index']!=chain['cursor'] and (item['actor']['id']==who['id'] or item['actor']['context_id']==who['context_id']) for item in chain['attempts'].values()),'A separate binding occurrence requires an isolated invocation lifetime')
    created=producer(payload.get('creation_evidence'),'host-agent-created',who)
    boundary=chain['event'].get('boundary_id',chain['event']['operation']+':'+chain['event']['anchor']);lineage=clone(chain['initial_lineage']);require(len(lineage)<64 and all(isinstance(item,dict) and text(item.get('binding_id')) and text(item.get('boundary_id')) for item in lineage),'Active invocation lineage is invalid')
    require(not any(item['binding_id']==row['id'] and item['boundary_id']==boundary for item in lineage),'Recursive re-entry of the same active occurrence is forbidden');lineage.append({'binding_id':row['id'],'boundary_id':boundary})
    original='HI-'+str(uuid.uuid4());package={'plugin_id':row['plugin_id'],**clone(chain['configuration']['packages'][row['plugin_id']])}
    sealed={'chain_id':chain['id'],'attempt_id':original,'binding_id':row['id'],'index':chain['cursor'],'event':clone(chain['event']),'context':clone(chain['context']),'configuration_digest':chain['configuration']['configuration_digest'],'mode':chain['mode'],'epoch':chain['epoch'],'execution_snapshot_digest':digest(chain['execution_snapshot']),'authority_digest':digest(chain['authority']),'authority':clone(chain['authority']),'scope_source_snapshot':scope_snapshot(proof.get('scope_source_snapshot',{})),'package_identity':package,'parameters':clone(row['effective']['values']),'extra_instructions':row['effective']['instructions'],'parameter_digest':row['effective']['digest'],'lineage':lineage}
    if 'execution_policy' in chain['configuration']:sealed['execution_policy']=clone(chain['configuration']['execution_policy'])
    attempt={'id':original,'index':chain['cursor'],'binding_id':row['id'],'status':'prepared','actor':who,'creation_evidence':created,'invoke_evidence':None,'result_evidence':None,'input':sealed,'input_digest':digest(sealed),'delivery_digest':None,'resolved_parameter_digest':None,'result':None}
    chain['attempts'][original]=attempt;stage=chain['stages'][chain['cursor']];stage['attempt_ids'].append(original);stage['status']='prepared';chain['prepared_attempt_id']=original;chain['state']='active';return {'attempt_id':original}


def exact_attempt(chain,payload,require_digest=True):
    original=payload.get('attempt_id');require(identity(original,'HI') and original in chain['attempts'],'The original invocation attempt is unknown');attempt=chain['attempts'][original]
    require(not require_digest or payload.get('input_digest')==attempt['input_digest'],'The result does not match the original public sealed input');return attempt


def mutate(store,command,payload,*,proof=None,verify_transition=None,guard=None):
    require(isinstance(command,str),'Invocation command is required');command=command.removeprefix('hook-');require(command in COMMANDS and isinstance(payload,dict),'Unknown invocation operation');payload=clone(payload)
    with store.lock():
        chain=raw(store,payload.get('chain_id'));guards(chain,payload);require(chain['state']!='superseded','The invocation chain was explicitly superseded; select its recorded replacement')
        if guard is not None:guard(clone(chain),command,clone(payload))
        if command not in {'reconcile','resume'}:require(not chain['authority'].get('revoked',False),'A revoked owner grant permits only original reconciliation and explicit reauthorization')
        detail={}
        if command=='prepare':detail=prepare(chain,payload,proof)
        elif command=='invoke':
            proof_check(chain,proof);attempt=exact_attempt(chain,payload);attempt_sources(attempt,proof);require(attempt['id']==chain['prepared_attempt_id'] and attempt['status']=='prepared','Only the original prepared attempt can begin invocation');delivery=proof.get('delivery')
            require(isinstance(delivery,dict) and delivery.get('input_digest')==attempt['input_digest'],'A trusted resolved delivery digest is required')
            for key in ['delivery_digest','resolved_parameter_digest']:
                require(isinstance(payload.get(key),str) and SHA.fullmatch(payload[key]) and payload[key]==delivery.get(key),'The actual private delivery identity differs');attempt[key]=payload[key]
            if delivery.get('dispatch_identity') is not None:
                dispatched=clone(delivery['dispatch_identity']);boundary=chain['event'].get('boundary_id',chain['event']['operation']+':'+chain['event']['anchor'])
                expected={'binding_id':attempt['binding_id'],'attempt_id':attempt['id'],'event_id':chain['event']['id'],'operation':chain['event']['operation'],'anchor':chain['event']['anchor'],'boundary_id':boundary}
                require(isinstance(dispatched,dict) and all(dispatched.get(key)==value for key,value in expected.items()) and all(isinstance(dispatched.get(key),str) and SHA.fullmatch(dispatched[key]) for key in ['delivery_key','input_digest']),'The owned Node dispatch identity differs from the original binding, event or attempt')
                attempt['dispatch_identity']=dispatched
            attempt['invoke_evidence']=producer(payload.get('evidence'),'host-invoked',attempt['actor'],True);require(attempt['invoke_evidence']['provider']==attempt['creation_evidence']['provider'],'The dispatch provider differs from the original created actor');attempt['status']='invoking';chain['stages'][attempt['index']]['status']='invoking';detail={'attempt_id':attempt['id']}
        elif command=='record':
            attempt=exact_attempt(chain,payload);attempt_sources(attempt,proof);result=clone(payload.get('result'));require(isinstance(result,dict) and result.get('status') in OUTCOMES,'An actual supported invocation result is required')
            evidence=producer(payload.get('evidence'),'host-result',attempt['actor'],True);require(evidence['provider']==attempt['creation_evidence']['provider'],'The returned provider differs from the original actor')
            require(payload.get('delivery_digest')==attempt['delivery_digest'] and attempt['delivery_digest'] is not None,'The result belongs to another private delivery')
            if 'resolved_parameter_digest' in payload:require(payload['resolved_parameter_digest']==attempt['resolved_parameter_digest'],'The returned resolved parameter digest differs')
            for key in ['input_digest','delivery_digest','resolved_parameter_digest']:
                if key in result:require(result[key]==attempt[key],'Returned output acknowledges another invocation input')
            require(not any(result.get(key) for key in ['real_human','human_approved','native_skill_called','native_tool_called']) and result.get('mechanism','source-backed-context')=='source-backed-context','Source-backed results cannot invent human approval or native Skill execution')
            if attempt['result'] is not None:
                require(result==attempt['result'] and evidence==attempt['result_evidence'],'Conflicting duplicate invocation result');return clone(chain)
            proof_check(chain,proof);require(attempt['id']==chain['prepared_attempt_id'] and attempt['status'] in {'invoking','unknown'},'Only the original invoked attempt can return a result')
            attempt['result']=result;attempt['result_evidence']=evidence;status=result['status'];attempt['status']='returned' if status in {'passed','findings','questions'} else status;chain['stages'][attempt['index']]['status']='awaiting-acceptance' if attempt['status']=='returned' else 'blocked';chain['state']='active' if attempt['status']=='returned' else 'blocked';detail={'attempt_id':attempt['id'],'result_status':status}
        elif command=='accept':
            before=clone(chain['context']);after=context(payload.get('context',before));proof_check(chain,proof,context_value=after);attempt=exact_attempt(chain,payload);attempt_sources(attempt,proof);require(attempt['id']==chain['prepared_attempt_id'] and attempt['status']=='returned','An unresolved failed, unavailable or cancelled result cannot satisfy the occurrence')
            require(attempt['input']['context']==before,'The original returned result belongs to a stale accepted context; explicit retry or verified incorporation is required')
            receipt=payload.get('receipt')
            if attempt['result']['status']=='passed' and after==before and receipt is None:receipt={'kind':'no-change','reference':attempt['result_evidence']['reference'],'before':digest(before),'after':digest(after)}
            else:
                require(verify_transition is not None,'Core findings/questions or edits require actual guarded incorporation evidence');receipt=verify_transition(clone(chain),clone(attempt),clone(receipt),clone(after));require(isinstance(receipt,dict) and receipt.get('kind') in {'core-incorporation','core-resolution'},'A guarded core transition is required')
            require(isinstance(receipt,dict) and text(receipt.get('reference')) and receipt.get('before')==digest(before) and receipt.get('after')==digest(after),'Core incorporation does not bind the exact before and after contexts');require(all(after.get(key)==before.get(key) for key in ['kind','id','task_ids','pending_ids','run_id','session_id']),'An incorporation cannot substitute another actual operation scope')
            stage=chain['stages'][attempt['index']];stage.update(status='complete',accepted_context=clone(after),accepted_transition={'before':before,'after':clone(after),'receipt':clone(receipt)});chain['context']=after;chain['prepared_attempt_id']=None;chain['cursor']+=1;chain['state']='complete' if chain['cursor']==len(chain['stages']) else 'active';detail={'attempt_id':attempt['id'],'transition':clone(receipt)}
        elif command=='reconcile':
            attempt=exact_attempt(chain,payload,False);status=payload.get('status');evidence=payload.get('evidence');require(status in {'unknown','failed','unavailable','cancelled'} and isinstance(evidence,dict) and evidence.get('kind')=='host-reconciliation' and text(evidence.get('reference')),'Original attempt reconciliation requires actual host evidence')
            require(attempt['id']==chain['prepared_attempt_id'] and attempt['status'] in PENDING,'Only an unresolved original attempt can be reconciled');attempt['status']=status;attempt['reconciliation']=clone(evidence);chain['stages'][attempt['index']]['status']='blocked';chain['state']='blocked';detail={'attempt_id':attempt['id'],'status':status}
        elif command=='resume':
            require(text(payload.get('reason')),'Explicit invocation resumption requires the actual resolved condition');require(not any(item['status'] in PENDING for item in chain['attempts'].values()),'Reconcile every unresolved original attempt before resumption');new=context(payload.get('context',chain['context']))
            for key in ['kind','id','task_ids','pending_ids','run_id','session_id']:
                require(new.get(key)==chain['context'].get(key),'Resume cannot substitute another actual operation scope')
            if 'configuration' in payload:require(payload['configuration']==chain['configuration'],'Resume cannot silently replace frozen occurrence order, parameters or package identities')
            mode=payload.get('mode',chain['mode']);grant=authority(payload.get('authority',chain['authority']),new,mode);executor=actor(payload.get('executor',chain['executor']));policy_changed=mode!=chain['mode'] or grant!=chain['authority'] or executor!=chain['executor']
            require(not grant.get('revoked',False),'Resume requires a current nonrevoked owner grant')
            if policy_changed:
                evidence=payload.get('evidence');require(isinstance(evidence,dict) and evidence.get('kind') in {'owner-message','submitted-answer'} and text(evidence.get('reference')),'An explicit mode or authority change requires actual owner-origin evidence')
            proof_check(chain,proof,context_value=new,allow_snapshot=True)
            if chain['state']=='complete':
                require(new==chain['context'] and proof['execution_snapshot']==chain['execution_snapshot'] and not policy_changed,'Completed-chain context, policy or source drift requires an explicitly adopted replacement chain');return clone(chain)
            previous={'context':clone(chain['context']),'execution_snapshot':clone(chain['execution_snapshot']),'mode':chain['mode'],'authority':clone(chain['authority']),'executor':clone(chain['executor'])};chain.update(mode=mode,authority=grant,executor=executor);chain['context']=new;chain['execution_snapshot']=snapshot(proof['execution_snapshot']);chain['epoch']+=1;chain['prerequisites']=[]
            original=current_attempt(chain)
            if original:
                require(payload.get('retry') is True and original['status'] in {'returned','failed','unavailable','cancelled'},'A stopped returned or failed occurrence requires an explicit retry or guarded acceptance');chain['prepared_attempt_id']=None;chain['stages'][chain['cursor']]['status']='pending'
            chain['state']='complete' if chain['cursor']==len(chain['stages']) else 'active';detail={**previous,'reason':payload['reason'],'retry':payload.get('retry',False),'policy_evidence':clone(payload.get('evidence')) if policy_changed else None}
        return write(store,chain,command,detail)
