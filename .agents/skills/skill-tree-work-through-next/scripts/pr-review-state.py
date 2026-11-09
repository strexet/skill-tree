#!/usr/bin/env python3
"""Persist exact-head PR review evidence and idempotent publication operations."""
from copy import deepcopy
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

def owned_module(name,path):
    path=Path(path)
    if path.is_symlink() or path.parent.is_symlink():raise ValueError('Owned Python helpers cannot use symlinks')
    source=path.read_bytes();package_root=path.parent.parent;manifest_path=package_root/'references/plugin-bindings.json'
    if manifest_path.exists() or (package_root/'SKILL.md').exists():
        if not manifest_path.is_file() or manifest_path.is_symlink() or manifest_path.parent.is_symlink():raise ValueError('The owned package inventory is unavailable')
        manifest=json.loads(manifest_path.read_text())
        if not isinstance(manifest,dict):raise ValueError('The owned package inventory is invalid')
        inventory=manifest.get('owned_resources')
        if not isinstance(inventory,dict) or not inventory or path.relative_to(package_root).as_posix() not in inventory:raise ValueError('The owned package inventory does not contain the requested helper')
        for relative,expected in inventory.items():
            if not isinstance(relative,str) or not relative or relative.startswith(('/','\\')) or '\\' in relative or '\0' in relative or re.match(r'^[A-Za-z]:',relative) or any(part in {'','.','..'} for part in relative.split('/')) or not isinstance(expected,str) or re.fullmatch('[a-f0-9]{64}',expected) is None:raise ValueError('The owned package inventory has invalid resource metadata')
            resource=package_root
            for part in relative.split('/'):
                resource=resource/part
                if resource.is_symlink():raise ValueError('Owned package resources cannot use symlinks')
            if not resource.is_file():raise ValueError('Owned package resource bytes differ: '+relative)
            current=source if resource==path else resource.read_bytes()
            if hashlib.sha256(current).hexdigest()!=expected:raise ValueError('Owned package resource bytes differ: '+relative)
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    previous=(sys.pycache_prefix,sys.dont_write_bytecode)
    prefix=path.parent/('.owned-source-'+uuid.uuid4().hex)
    if prefix.exists():raise ValueError('A fresh source-only helper prefix is required')
    try:
        sys.pycache_prefix=str(prefix);sys.dont_write_bytecode=True
        exec(compile(source,str(path),'exec'),module.__dict__)
    finally:sys.pycache_prefix,sys.dont_write_bytecode=previous
    return module

try:ws=owned_module('pr_workspaces',Path(__file__).with_name('run-workspaces.py'))
except (ValueError,OSError) as error:
    if __name__!='__main__':raise
    print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=True,sort_keys=True));raise SystemExit(2)

class ReviewError(ValueError):
    pass

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def instructions(text):
    # Only the current owner's direct instruction enters the authorization parser.
    text=re.sub(r'(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1[^\n]*', '', text)
    text=re.sub(r'(`+).*?\1', '', text, flags=re.S)
    text=re.sub(r'(?m)^\s*>.*$', '', text)
    return re.sub(r'"[^"\n]*"|«[^»]*»|“[^”]*”|\x27[^\x27\n]*\x27', '', text)

def parameters(current_branch, payload):
    text=instructions(payload.get('instruction','')) if payload.get('instruction_origin','owner')=='owner' else ''
    original=text
    positive=[];negative=[]
    for match in re.finditer(r'\bmerge\s*=\s*(true|false)\b',text,re.I):
        (positive if match[1].casefold()=='true' else negative).append(match.span())
    neg=r'\b(?:без\s+(?:merge|мерд?ж\w*)|не\s+(?:merge|мерд?ж\w*|см[е]?рд?ж\w*|вмерд?ж\w*)|without\s+merge|do\s+not\s+merge|don[’\x27]t\s+merge|no\s+merge)\b'
    negative+= [m.span() for m in re.finditer(neg,text,re.I)]
    scrub=list(text)
    for start,end in negative:
        scrub[start:end]=' '*(end-start)
    affirmative=''.join(scrub)
    natural_original=''.join(' ' if a==' ' and b!=' ' else b for a,b in zip(affirmative,original))
    pos=r'\b(?:with\s+merge|с\s+(?:merge|мерд?жем)|(?:затем\s+)?(?:см[е]?рд?жи|смржи|вмерд?жи)(?:ть)?|then\s+merge)\b'
    positive+=[m.span() for m in re.finditer(pos,affirmative,re.I)]
    if 'merge' in payload:
        if type(payload['merge']) is not bool:raise ReviewError('merge requires a boolean')
        if payload.get('instruction_origin','owner')=='owner':
            (positive if payload['merge'] else negative).append((0,0))
    if positive and negative:raise ReviewError('Conflicting explicit merge instructions require clarification')
    choices={'source_branch':[], 'target_branch':[]}
    for key in choices:
        if payload.get(key):choices[key].append(payload[key])
        choices[key]+=[m[1] for m in re.finditer(r'\b'+key+r'\s*=\s*([\w./-]+)',original,re.I)]
    pair=re.search(r'(?:\bиз|\bfrom)\s+([\w./-]+)\s+(?:в|to|into)\s+([\w./-]+)',original,re.I)
    if pair:
        choices['source_branch'].append(pair[1]);choices['target_branch'].append(pair[2])
    target=re.search(r'(?:см[е]?рд?жи|смржи|вмерд?жи|then\s+merge|with\s+merge|мерд?жем)\s+(?:в|into|to)\s+([\w./-]+)',natural_original,re.I)
    if target:choices['target_branch'].append(target[1])
    result={}
    for key,default in [('source_branch',current_branch),('target_branch','develop')]:
        values=set(choices[key])
        if len(values)>1:raise ReviewError('Conflicting '+key+' instructions require clarification')
        result[key]=next(iter(values)) if values else default
        if not result[key] or result[key].startswith('-'):raise ReviewError('An explicit named source and target branch is required')
    if result['source_branch']==result['target_branch']:raise ReviewError('Source and target branches differ')
    result['merge']=bool(positive)
    result['merge_explicit']=bool(positive or negative)
    result['authorization']={'pr':payload.get('instruction_origin','owner')=='owner','merge':bool(positive),'origin':payload.get('instruction_origin','owner'),'instruction_digest':digest(text)}
    return result

def preflight(root,payload):
    root=Path(root).resolve();ws.unfinished(root)
    current=ws.git(root,'symbolic-ref','--quiet','--short','HEAD')
    params=parameters(current,payload)
    if current!=params['source_branch']:raise ReviewError('Select the source branch worktree before publication')
    if ws.git(root,'status','--porcelain'):raise ReviewError('Dirty worktree; preserve unrelated changes and make authorized scoped commits first')
    remote=payload.get('remote','origin')
    if remote not in ws.git(root,'remote').splitlines():raise ReviewError('Unknown remote')
    url=ws.git(root,'remote','get-url',remote)
    if re.search(r'://[^/@]+:[^/@]+@',url) or '?' in url:raise ReviewError('Remote credentials cannot enter publication metadata')
    ws.git(root,'fetch','--no-tags',remote)
    target=ws.branch(root,params['target_branch']);ws.branch(root,params['source_branch'])
    base=ws.git(root,'rev-parse','--verify','refs/remotes/'+remote+'/'+target+'^{commit}')
    head=ws.git(root,'rev-parse','HEAD');changed=ws.git(root,'diff','--name-only',base+'...'+head).splitlines()
    if not changed:raise ReviewError('No changes relative to the current target branch')
    return {**params,'repo_id':ws.repo_id(root),'remote':remote,'remote_id':hashlib.sha256(url.encode()).hexdigest(),'head':head,'base_oid':base,'changed_files':changed}

def identity(snapshot):
    return {**{key:snapshot[key] for key in ['repo_id','remote','source_branch','target_branch','head','base_oid']},'remote_id':snapshot.get('remote_id')}

def review_key(snapshot):
    return digest({key:snapshot.get(key) for key in ['head','base_oid','target_branch','changed_files','threads','reviews','comments','checks','checks_known','required_checks_missing','approvals_known','approvals_required','approved']})

def decision_context(snapshot,purpose='finding-resolution'):
    if not isinstance(purpose,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',purpose):raise ReviewError('Review decision requires an exact bounded purpose')
    scope={key:snapshot.get(key) for key in ['repo_id','remote','remote_id','source_branch','target_branch','head','base_oid']}
    semantic=digest({'scope':scope,'review_key':review_key(snapshot),'purpose':purpose})
    return {'kind':'review','id':'review:'+digest(scope),'head':snapshot.get('head'),'base_oid':snapshot.get('base_oid'),'target_branch':snapshot.get('target_branch'),'purpose':purpose,'semantic_fingerprint':semantic,'content_fingerprint':digest(snapshot)}

def decision_acceptance(store,record,snapshot,reference,expected):
    if record.get('identity')!=identity(snapshot):raise ReviewError('Decision requires the current review repository, head, base and target')
    if expected.get('kind') not in {'technical','product','specification-acceptance'}:raise ReviewError('Delegated review decisions cannot replace publication authority, checks or external approval')
    purpose=expected.get('context',{}).get('purpose','finding-resolution')
    helper=owned_module('review_decision_governance',Path(__file__).with_name('decision-governance.py'))
    try:accepted=helper.acceptance_reference(store,reference,{**expected,'context':decision_context(snapshot,purpose)})
    except ValueError as error:raise ReviewError(str(error)) from error
    result=deepcopy(record);receipts=result.setdefault('decision_receipts',[])
    if accepted not in receipts:receipts.append(deepcopy(accepted))
    return result

def reconcile(record,snapshot):
    record=deepcopy(record)
    for key in ['repo_id','remote','remote_id','source_branch']:
        if record['identity'].get(key)!=snapshot.get(key):raise ReviewError('Publication repository/source identity conflict')
    pr=snapshot.get('pr')
    if record.get('pr') and pr and record['pr']['id']!=pr['id']:raise ReviewError('Existing PR identity conflict')
    if pr:record['pr']=pr
    changed=record['identity']!=identity(snapshot) or record.get('snapshot_key')!=review_key(snapshot)
    record['identity']=identity(snapshot);record['snapshot_key']=review_key(snapshot)
    if snapshot.get('state')=='CLOSED':
        record['status']='blocked';record['blocked_reason']='The selected PR is closed without merge';return record
    if snapshot.get('state')=='MERGED':
        if not record.get('pr') or not record['pr'].get('id'):raise ReviewError('Merged status requires the existing provider PR identity')
        if not snapshot.get('merge_commit'):raise ReviewError('Merged provider result lacks merge commit evidence')
        record['status']='merged';record['merge_commit']=snapshot['merge_commit'];return record
    if changed:
        record.pop('review',None)
        record['status']='pr-review-in-progress'
    return record

def reviewed(record,snapshot,payload):
    record=inspected(record,snapshot,payload)
    if record['status']=='merged':return record
    if record['status']=='blocked':raise ReviewError(record['blocked_reason'])
    if payload.get('head')!=snapshot['head'] or payload.get('base_oid')!=snapshot['base_oid'] or payload.get('target_branch')!=snapshot['target_branch']:
        raise ReviewError('Review evidence does not match current head/base/target')
    if set(payload.get('files',[]))!=set(snapshot['changed_files']) or not payload.get('context_inspected'):
        raise ReviewError('Review requires the full diff and necessary surrounding context')
    if not payload.get('discussions_inspected') or not payload.get('checks_inspected'):
        raise ReviewError('Review requires current reviews, inline discussions and CI results')
    findings=payload.get('findings',[])
    for finding in findings:
        if any(not finding.get(key) for key in ['id','path','line','cause','consequence','severity']) or finding['path'] not in snapshot['changed_files'] or type(finding['line']) is not int or finding['line']<1:
            raise ReviewError('Actionable finding requires location, cause, consequence and severity')
    ledger=record.setdefault('findings',{})
    for finding in findings:ledger[finding['id']]=deepcopy(finding)
    unresolved=[f for f in ledger.values() if f.get('status','open') not in {'verified-fixed','dismissed'}]
    # A claimed fix requires independently recorded verification of the current revision.
    if any(f.get('status') in {'verified-fixed','dismissed'} and (f.get('verified_head')!=snapshot['head'] or not f.get('verification_evidence')) for f in findings):
        raise ReviewError('Fixed finding requires current-head verification evidence')
    if any(f.get('status')=='dismissed' and not f.get('dismissal_reason') for f in findings):raise ReviewError('Dismissed finding requires an evidence-backed reason')
    record['review']={'key':review_key(snapshot),'head':snapshot['head'],'base_oid':snapshot['base_oid'],'findings':findings,'unresolved':len(unresolved),'independent_approval':False,'evidence':payload.get('evidence',[])}
    record['rounds']=record.get('rounds',[])+[deepcopy(record['review'])]
    return record

REVIEW_OPERATION='skill-tree-pr-review-cycle'
REVIEW_PHASES={'before':'before','during':'during','after':'after','before-review':'before','after-core-inspection':'during','before-pr-ready':'after'}


def _review_path(store,publication_id):
    if not isinstance(publication_id,str) or not re.fullmatch(r'[a-f0-9]{32}',publication_id):raise ReviewError('An exact owned publication identity is required')
    path=store.root/'.skill-tree/history/publications'/('pub-'+publication_id+'.json')
    if any(part.is_symlink() for part in [path,*path.parents]):raise ReviewError('Publication metadata cannot use symlinks')
    return path


def inspected(record,snapshot,payload):
    record=reconcile(record,snapshot)
    if any(payload.get(key)!=snapshot[key] for key in ['head','base_oid','target_branch']) or set(payload.get('files',[]))!=set(snapshot['changed_files']) or not all(payload.get(key) is True for key in ['context_inspected','discussions_inspected','checks_inspected']):raise ReviewError('Current complete core inspection is required')
    record['inspection']={'key':review_key(snapshot),'head':snapshot['head'],'base_oid':snapshot['base_oid'],'files':deepcopy(snapshot['changed_files']),'evidence':deepcopy(payload.get('evidence',[]))}
    return record


def review_phase_guard(store,context,phase):
    publication_id=context.get('publication_id');path=_review_path(store,publication_id)
    if not path.is_file():raise ReviewError('The review invocation requires its existing owned publication')
    record=json.loads(path.read_text());phase=REVIEW_PHASES.get(phase,phase)
    if phase not in {'before','during','after'}:raise ReviewError('The review phase is unavailable')
    if any(record.get('identity',{}).get(key)!=context.get(key) for key in ['head','base_oid','target_branch']):raise ReviewError('The plugin review belongs to another publication head/base/target')
    scope={name:record['identity'].get(name) for name in ['repo_id','remote','remote_id','source_branch','target_branch']}
    if context.get('id')!='review-hook:'+digest(scope) or context.get('semantic_fingerprint')!=digest({'scope':scope,'review_key':record.get('snapshot_key')}):raise ReviewError('The review context differs from the actual publication review identity')
    key=record.get('snapshot_key');core=record.get('review') if phase=='after' else record.get('inspection') or record.get('review') if phase=='during' else None
    if phase in {'during','after'} and (not core or core.get('key')!=key):raise ReviewError('The configured review phase requires current full core review or inspection')
    if phase=='after' and core.get('unresolved')!=0:raise ReviewError('The after phase requires a current core review with zero unresolved findings')
    if record.get('status') in {'blocked','merged'}:raise ReviewError('The publication is not an active review scope')
    return {'publication_id':publication_id,'publication_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'phase':phase,
        'core_review_key':core.get('key') if core else None,'core_review_digest':digest(core) if core else None}


def _review_root(store,record,package_root=None):
    candidate=Path(package_root).absolute() if package_root else Path(__file__).parent.parent
    if not (candidate/'references/plugin-bindings.json').is_file():
        relative=(record or {}).get('review_requirements',{}).get('operation_package')
        if relative:
            if Path(relative).is_absolute() or any(part in {'','..','.'} for part in relative.split('/')):raise ReviewError('The frozen review operation package must remain repository-relative')
            candidate=store.source_root/relative
    if (candidate/'references/plugin-bindings.json').is_file():return candidate
    registry=store.source_root/'.skill-tree/installation/plugins.json'
    if registry.is_file():
        value=json.loads(registry.read_text());packages=value.get('packages',{})
        if any(row.get('operation')==REVIEW_OPERATION and row.get('enabled') and packages.get(row.get('plugin_id'),{}).get('adaptation',{}).get('invocation_policy') for row in value.get('bindings',[])):raise ReviewError('Configured review plugins require the explicitly trusted composed operation package')
    return None


def review_requirement_plan(store,snapshot,*,package_root=None,run_overrides=None,record=None,publication_id=None):
    if getattr(store,'_writer_active',False):raise ReviewError('Review requirement preparation must run outside the writer lock')
    root=_review_root(store,record,package_root)
    if root is None:return None
    wf=owned_module('review_requirement_workflow',Path(__file__).with_name('workflow-state.py'))
    watch=wf._hook_watch(root,store.source_root);manifest=json.loads((root/'references/plugin-bindings.json').read_text())
    if not manifest.get('definitions') and not (record or {}).get('review_requirements'):return None
    phases={};proofs={};configuration=None
    for phase in ['before','during','after']:
        context=hook_context(snapshot)
        if publication_id:context['publication_id']=publication_id
        value=wf._hook_node(root,{'runtime_action':'requirement-plan','project_root':str(store.source_root),'event':{'id':'review-requirements-'+phase,'operation':REVIEW_OPERATION,'anchor':phase},'context':context,'capabilities':['codex-source-backed-context'],'adapter':{'provider':'codex','mechanism':'source-backed-context'},'run_overrides':deepcopy(run_overrides or {})})
        if configuration is not None and configuration!=value['configuration']:raise ReviewError('Review configuration changed during requirement preparation')
        configuration=value['configuration'];proof=value['proof'];proofs[phase]=proof
        phases[phase]=[row['id'] for row in proof['bindings']]+[row['id'] for row in proof.get('unresolved',[])]
    return {'configuration':configuration,'phases':phases,'proofs':proofs,'watch':watch,'package_root':str(root)}


def _frozen_review_requirements(store,prepared,history=None):
    root=Path(prepared['package_root']).resolve()
    try:relative=root.relative_to(store.source_root).as_posix()
    except ValueError:relative=None
    return {'schema':1,'configuration_digest':prepared['configuration']['configuration_digest'],'configuration':deepcopy(prepared['configuration']),
        'execution_snapshot':deepcopy(prepared['proofs']['after']['execution_snapshot']),'phases':deepcopy(prepared['phases']),
        'operation_package':relative,'history':deepcopy(history or []),'outcome':'required' if any(prepared['phases'].values()) else 'disabled'}


def review_configuration_context(snapshot,publication_id,before_configuration_digest,after_configuration_digest):
    value=decision_context(snapshot,'review-plugin-configuration');value.update(publication_id=publication_id,before_configuration_digest=before_configuration_digest,after_configuration_digest=after_configuration_digest)
    value['semantic_fingerprint']=digest({key:item for key,item in value.items() if key not in {'semantic_fingerprint','content_fingerprint'}});value['content_fingerprint']=value['semantic_fingerprint'];return value


def reconcile_review_requirements(store,record,snapshot,publication_id,prepared,reference):
    old=record.get('review_requirements')
    if old is None or prepared is None:raise ReviewError('Explicit review reconciliation requires both frozen and inspected configuration')
    dg=owned_module('review_policy_governance',Path(__file__).with_name('decision-governance.py'));decision=dg.read(store,reference.get('decision_id'))
    context=review_configuration_context(snapshot,publication_id,old['configuration_digest'],prepared['configuration']['configuration_digest'])
    accepted=dg.acceptance_reference(store,reference,{'context':context,'mode':decision['mode'],'kind':'technical','authority_digest':decision['authority_digest']})
    if accepted['answer']!='adopt':raise ReviewError('The current core decision did not adopt the review configuration')
    engine=owned_module('review_policy_invocations',Path(__file__).with_name('plugin-invocation.py'));refs=set(record.get('hook_chains',[]))
    for row in engine.pending_scan(store):
        chain=engine.read(store,row['chain_id'])
        if row['chain_id'] in refs or chain.get('context',{}).get('publication_id')==publication_id:raise ReviewError('Reconcile original pending review actors before changing the required policy')
    result=deepcopy(record);history=list(old.get('history',[]))+[{'configuration_digest':old['configuration_digest'],'hook_chains':list(refs),'decision_receipt':deepcopy(reference),'outcome':'explicit-configuration-adoption'}]
    result['review_requirements']=_frozen_review_requirements(store,prepared,history);result['hook_chains']=[]
    return result


def review_findings_context(snapshot,publication_id,chain_id,attempt_id,result_digest):
    value=decision_context(snapshot,'review-plugin-findings');value.update(publication_id=publication_id,hook_chain_id=chain_id,hook_attempt_id=attempt_id,hook_result_digest=result_digest)
    value['semantic_fingerprint']=digest({key:item for key,item in value.items() if key not in {'semantic_fingerprint','content_fingerprint'}});value['content_fingerprint']=value['semantic_fingerprint'];return value


def incorporate_review_findings(store,record,snapshot,publication_id,payload):
    engine=owned_module('review_finding_engine',Path(__file__).with_name('plugin-invocation.py'));chain=engine.read(store,payload.get('chain_id'))
    attempt=chain['attempts'].get(payload.get('attempt_id'))
    if chain['context']!=hook_context(snapshot,publication_id) or attempt is None or attempt['status']!='returned' or attempt['result']['status']!='findings':raise ReviewError('A current original returned review finding contribution is required')
    values=attempt['result'].get('findings')
    if not isinstance(values,list) or not values:raise ReviewError('A finding contribution must contain actual nonempty findings')
    output=[]
    for finding in values:
        if not isinstance(finding,dict) or any(not finding.get(key) for key in ['id','path','line','cause','consequence','severity']) or finding['path'] not in snapshot['changed_files'] or type(finding['line']) is not int or finding['line']<1:raise ReviewError('Plugin findings require concrete current changed-file locations, cause and consequence')
        if finding.get('status','open')!='open':raise ReviewError('A plugin cannot self-verify or dismiss a finding')
        item=deepcopy(finding);item['id']=attempt['id']+':'+str(finding['id']);item['source_attempt_id']=attempt['id'];output.append(item)
    if len({item['id'] for item in output})!=len(output):raise ReviewError('Review contribution finding identities must be distinct')
    result_digest=engine.digest(attempt['result']);reference=payload.get('decision_receipt')
    if not isinstance(reference,dict):raise ReviewError('Actual W1 finding substantiation requires a current core decision receipt')
    dg=owned_module('review_findings_governance',Path(__file__).with_name('decision-governance.py'));decision=dg.read(store,reference.get('decision_id'))
    context=review_findings_context(snapshot,publication_id,chain['id'],attempt['id'],result_digest)
    accepted=dg.acceptance_reference(store,reference,{'context':context,'mode':decision['mode'],'kind':'technical','authority_digest':decision['authority_digest']})
    if accepted['answer']!='incorporate':raise ReviewError('The current core decision did not substantiate the review findings')
    result=deepcopy(record);contribution_id='RC-'+digest({'attempt_id':attempt['id'],'result_digest':result_digest})[:32]
    contribution={'id':contribution_id,'chain_id':chain['id'],'attempt_id':attempt['id'],'result_digest':result_digest,'head':snapshot['head'],'base_oid':snapshot['base_oid'],
        'findings':output,'decision_receipt':deepcopy(reference)}
    ledger=result.setdefault('review_plugin_contributions',{})
    if contribution_id in ledger and ledger[contribution_id]!=contribution:raise ReviewError('Conflicting original review finding contribution')
    for finding in output:
        existing=result.setdefault('findings',{}).get(finding['id'])
        if existing is not None and existing!=finding:raise ReviewError('A finding contribution cannot overwrite an existing core resolution')
        result['findings'][finding['id']]=finding
    ledger[contribution_id]=contribution
    receipt={'kind':'core-incorporation','publication_id':publication_id,'contribution_id':contribution_id,'reference':'.skill-tree/history/publications/pub-'+publication_id+'.json#'+contribution_id,
        'before':engine.digest(chain['context']),'after':engine.digest(chain['context'])}
    result['contribution_receipt']=receipt;return result


def verify_review_contribution(store,chain,attempt,receipt,after):
    publication_id=receipt.get('publication_id')
    if publication_id!=chain['context'].get('publication_id') or after!=chain['context']:raise ReviewError('Review incorporation cannot substitute another publication context')
    record=json.loads(_review_path(store,publication_id).read_text());contribution=record.get('review_plugin_contributions',{}).get(receipt.get('contribution_id'))
    engine=owned_module('review_contribution_engine',Path(__file__).with_name('plugin-invocation.py'))
    if not contribution or contribution['chain_id']!=chain['id'] or contribution['attempt_id']!=attempt['id'] or contribution['result_digest']!=engine.digest(attempt['result']) or contribution['head']!=after['head'] or contribution['base_oid']!=after['base_oid']:raise ReviewError('The actual review contribution differs from the original returned result')
    if not contribution['findings'] or any(record.get('findings',{}).get(item['id'])!=item for item in contribution['findings']):raise ReviewError('The actual accepted review findings are missing or changed')
    dg=owned_module('review_contribution_governance',Path(__file__).with_name('decision-governance.py'));decision=dg.read(store,contribution['decision_receipt']['decision_id'])
    # The original snapshot context is sealed by the accepted DG context and the
    # current publication core identity; mutation cannot invent a role result.
    accepted=dg.acceptance_reference(store,contribution['decision_receipt'],{'context':decision['context'],'mode':decision['mode'],'kind':'technical','authority_digest':decision['authority_digest']})
    if accepted['answer']!='incorporate' or decision['context'].get('publication_id')!=publication_id or decision['context'].get('hook_chain_id')!=chain['id'] or decision['context'].get('hook_attempt_id')!=attempt['id'] or decision['context'].get('hook_result_digest')!=engine.digest(attempt['result']):raise ReviewError('The current W1 review finding acceptance is invalid')
    return deepcopy(receipt)


def _review_requirement_admission(store,record,snapshot):
    frozen=record.get('review_requirements');prepared=getattr(store,'_review_requirement_preflight',None)
    if not getattr(store,'_writer_active',False):
        prepared=review_requirement_plan(store,snapshot,record=record,run_overrides=(frozen or {}).get('configuration',{}).get('run_overrides',{}),publication_id=record.get('publication_id'))
    if prepared is None:
        if frozen and any(frozen['phases'].values()):raise ReviewError('Current configured review requirements are unavailable')
        return
    wf=owned_module('review_requirement_admission',Path(__file__).with_name('workflow-state.py'));wf._hook_watch_guard(prepared['watch'],prepared['package_root'])
    if frozen is None:raise ReviewError('Configured review plugins require a frozen publication requirement plan before readiness')
    if frozen['configuration_digest']!=prepared['configuration']['configuration_digest'] or frozen['execution_snapshot']!=prepared['proofs']['after']['execution_snapshot']:raise ReviewError('Frozen review plugin configuration or source changed; explicit reconciliation is required')
    engine=owned_module('review_requirement_engine',Path(__file__).with_name('plugin-invocation.py'));chains=[engine.read(store,value) for value in record.get('hook_chains',[])]
    for phase,ids in prepared['phases'].items():
        for binding_id in ids:
            matched=[]
            for chain in chains:
                if chain['context']!=hook_context(snapshot,record.get('publication_id')) or chain['configuration']['configuration_digest']!=frozen['configuration_digest'] or chain['event'].get('operation')!=REVIEW_OPERATION or chain['event'].get('boundary_id')!=prepared['proofs'][phase]['event'].get('boundary_id'):continue
                stage=next((stage for stage in chain['stages'] if stage['binding_id']==binding_id),None)
                if stage and stage['status']=='complete':matched.append(chain)
            if len(matched)!=1:raise ReviewError('A configured enabled review occurrence is missing a unique explicitly attached current completed pass: '+binding_id)
    for proof in prepared['proofs'].values():
        if proof.get('unresolved') or any(item.get('code') not in {'invocation-unqualified','unsupported-adapter','missing-capability'} for item in proof.get('prerequisites',[])):raise ReviewError('Current review plugin configuration has unresolved prerequisites')


def hook_context(snapshot,publication_id=None):
    scope={key:snapshot.get(key) for key in ['repo_id','remote','remote_id','source_branch','target_branch']}
    value={'kind':'review','id':'review-hook:'+digest(scope),'head':snapshot.get('head'),'base_oid':snapshot.get('base_oid'),'target_branch':snapshot.get('target_branch'),'semantic_fingerprint':digest({'scope':scope,'review_key':review_key(snapshot)}),'content_fingerprint':digest(snapshot)}
    if publication_id:value['publication_id']=publication_id
    return value

def _retire_review_hook_references(store,record,snapshot):
    if not record or not record.get('hook_chains'):return record
    engine=owned_module('review_retirement_engine',Path(__file__).with_name('plugin-invocation.py'))
    current=[hook_context(snapshot),hook_context(snapshot,record.get('publication_id'))];retired=[];retained=[];states={}
    for value in record['hook_chains']:
        chain=engine.read(store,value)
        if chain['context'] not in current and not any(attempt['status'] in engine.PENDING for attempt in chain['attempts'].values()):
            retired.append(value);states[value]={'state':chain['state'],'context':deepcopy(chain['context']),'attempt_statuses':{key:attempt['status'] for key,attempt in chain['attempts'].items()}}
        else:retained.append(value)
    if not retired:return record
    result=deepcopy(record);result.setdefault('review_hook_history',[]).append({'identity':deepcopy(record['identity']),'snapshot_key':record.get('snapshot_key'),'hook_chains':retired,'states':states,'outcome':'review-snapshot-invalidated'})
    result['hook_chains']=retained;return result


def attach_hook_chain(store,record,snapshot,chain_id):
    ws.validate_hook_references(record)
    if record.get('identity')!=identity(snapshot):raise ReviewError('Hook attachment requires the exact current review snapshot')
    engine=owned_module('review_plugin_invocation',Path(__file__).with_name('plugin-invocation.py'))
    try:chain=engine.read(store,chain_id)
    except ValueError as error:raise ReviewError(str(error)) from error
    if chain['context']!=hook_context(snapshot,record.get('publication_id')) and chain['context']!=hook_context(snapshot):raise ReviewError('Hook chain belongs to another review scope or current head/base')
    result=deepcopy(record);refs=result.setdefault('hook_chains',[])
    if chain_id not in refs:refs.append(chain_id)
    return result

def hook_admission(store,record,snapshot):
    wf=owned_module('review_hook_workflow',Path(__file__).with_name('workflow-state.py'))
    engine=owned_module('review_admission_engine',Path(__file__).with_name('plugin-invocation.py'))
    for pending in engine.pending_scan(store):
        chain=engine.read(store,pending['chain_id'])
        if chain['context'].get('publication_id')==record.get('publication_id') and record.get('publication_id'):raise ReviewError('Original pending review actors require host cleanup before publication readiness')
    for value in record.get('hook_chains',[]):
        chain=engine.read(store,value)
        if chain['context'] not in [hook_context(snapshot),hook_context(snapshot,record.get('publication_id'))]:raise ReviewError('The attached review pass is stale for the current publication')
    try:wf.hook_admission(store,chain_ids=record.get('hook_chains',[]))
    except (ValueError,OSError) as error:raise ReviewError('Current review hook obligations remain unresolved: '+str(error)) from error


def ready(record,snapshot,*,store=None):
    ws.validate_hook_references(record)
    if store is not None:record=_retire_review_hook_references(store,record,snapshot)
    record=reconcile(record,snapshot)
    if record['status']=='merged':return record
    if record['status']=='blocked':raise ReviewError(record['blocked_reason'])
    if (record.get('hook_chains') or any(record.get('review_requirements',{}).get('phases',{}).values())) and store is None:raise ReviewError('Current hook readiness requires the live owned store')
    if store is not None:
        _review_requirement_admission(store,record,snapshot);hook_admission(store,record,snapshot)
    if not record.get('pr') or not record['pr'].get('id') or not record['pr'].get('url'):raise ReviewError('PR readiness requires the existing provider PR identity and URL')
    review=record.get('review')
    if not review or review['key']!=review_key(snapshot) or review['unresolved'] or any(f.get('status','open') not in {'verified-fixed','dismissed'} for f in record.get('findings',{}).values()):
        raise ReviewError('Current full review or actionable finding verification remains incomplete')
    if any(not t.get('resolved') and (t.get('required') or t.get('actionable')) for t in snapshot.get('threads',[])):
        raise ReviewError('Mandatory/actionable PR discussions remain unresolved')
    if snapshot.get('checks_known') is not True:raise ReviewError('Required check policy is unknown')
    checks=snapshot.get('checks',[])
    if any(c.get('required') and c.get('status')!='success' for c in checks):raise ReviewError('Required checks remain pending or failed')
    if snapshot.get('required_checks_missing'):raise ReviewError('Required checks are missing')
    record['ci']='not-configured' if not checks else 'required-checks-passed'
    record['status']='pr-ready';return record

def merge_gate(record,snapshot,*,store=None):
    record=ready(record,snapshot,store=store)
    if record['status']=='merged':return record
    authorization=record['authorization']
    if not authorization.get('merge') or not authorization.get('pr') or authorization.get('origin')!='owner':raise ReviewError('Merge lacks explicit owner authorization')
    if snapshot.get('approvals_known') is not True:raise ReviewError('Required approval policy is unknown')
    if snapshot.get('approvals_required') and not snapshot.get('approved'):raise ReviewError('External approval requirements remain unsatisfied')
    if snapshot.get('mergeable')!='MERGEABLE':raise ReviewError('Merge conflict or unknown mergeability')
    return record

class GitHub:
    """Authorized gh fallback; connectors can supply the same normalized snapshots."""
    def __init__(self,root,repository):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+',repository):raise ReviewError('Explicit GitHub owner/repository required')
        self.root=Path(root);self.repository=repository
    def gh(self,*args):
        if '--paginate' in args and '--slurp' not in args:args=(*args,'--slurp')
        result=subprocess.run(['gh',*map(str,args)],cwd=self.root,capture_output=True,text=True,timeout=45)
        if result.returncode:raise ReviewError('GitHub access or operation failed; preserve the publication checkpoint')
        data=json.loads(result.stdout) if result.stdout.strip() else None
        if '--slurp' in args and data and isinstance(data[0],list):return [item for page in data for item in page]
        return data
    def find(self,source,target,expected_head=None):
        prs=self.gh('api','--method','GET','repos/'+self.repository+'/pulls','-f','state=all','-f','head='+self.repository.split('/')[0]+':'+source,'-f','base='+target,'--paginate')
        matches=[p for p in prs if p['head']['ref']==source and p['base']['ref']==target and p['head']['repo']['full_name']==self.repository]
        opened=[p for p in matches if p['state']=='open'];merged=[p for p in matches if p.get('merged_at') and expected_head and p['head'].get('sha')==expected_head]
        if len(opened)>1:raise ReviewError('Multiple matching open PRs require explicit selection')
        return (opened or sorted(merged,key=lambda p:p['merged_at'],reverse=True) or [None])[0]
    def ensure(self,source,target,title,body,draft=False,expected_head=None):
        existing=self.find(source,target,expected_head)
        if existing:
            if existing.get('merged_at'):return existing
            return self.gh('api','--method','PATCH','repos/'+self.repository+'/pulls/'+str(existing['number']),'-f','title='+title,'-f','body='+body)
        # Lost-response recovery queries the exact source/base before another creation.
        return self.gh('api','--method','POST','repos/'+self.repository+'/pulls','-f','head='+source,'-f','base='+target,'-f','title='+title,'-f','body='+body,'-F','draft='+str(draft).lower())
    def comment(self,number,key,body):
        marker='<!-- skill-tree:'+key+' -->';endpoint='repos/'+self.repository+'/issues/'+str(number)+'/comments'
        comments=self.gh('api','--method','GET',endpoint,'--paginate')
        matches=[c for c in comments if marker in c['body']]
        if len(matches)>1:raise ReviewError('Duplicate publication markers require reconciliation')
        if matches:
            if matches[0]['body']!=body+'\n\n'+marker:raise ReviewError('Existing comment marker has different content; reconcile before a new operation')
            return matches[0]
        return self.gh('api','--method','POST',endpoint,'-f','body='+body+'\n\n'+marker)
    def snapshot(self,number,context,policy):
        raw=self.gh('pr','view',number,'--repo',self.repository,'--json','id,number,url,state,headRefOid,headRefName,baseRefOid,baseRefName,mergeable,reviewDecision,mergeCommit,statusCheckRollup,changedFiles')
        if raw['headRefName']!=context['source_branch'] or raw['baseRefName']!=context['target_branch']:
            raise ReviewError('Provider PR branch identity differs from preflight')
        endpoint='repos/'+self.repository
        files=self.gh('api','--method','GET',endpoint+'/pulls/'+str(number)+'/files','--paginate')
        if len(files)!=raw['changedFiles']:raise ReviewError('Provider full-diff file inventory is incomplete')
        reviews=self.gh('api','--method','GET',endpoint+'/pulls/'+str(number)+'/reviews','--paginate')
        comments=self.gh('api','--method','GET',endpoint+'/issues/'+str(number)+'/comments','--paginate')
        inline=self.gh('api','--method','GET',endpoint+'/pulls/'+str(number)+'/comments','--paginate')
        owner,name=self.repository.split('/');threads=[];cursor=None
        query='query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{id isResolved isOutdated path line} pageInfo{hasNextPage endCursor}}}}}'
        while True:
            args=['api','graphql','-f','query='+query,'-f','owner='+owner,'-f','name='+name,'-F','number='+str(number)]
            if cursor:args+=['-f','cursor='+cursor]
            response=self.gh(*args)
            if response.get('errors'):raise ReviewError('Provider discussion inventory is incomplete')
            page=response['data']['repository']['pullRequest']['reviewThreads']
            threads.extend({'id':t['id'],'resolved':t['isResolved'],'required':not t['isResolved'],'path':t['path'],'line':t['line'],'outdated':t['isOutdated']} for t in page['nodes'])
            if not page['pageInfo']['hasNextPage']:break
            new_cursor=page['pageInfo']['endCursor']
            if not new_cursor or new_cursor==cursor:raise ReviewError('Provider discussion pagination did not advance')
            cursor=new_cursor
        required=set(policy.get('required_check_names',[]));checks=[]
        for check in raw.get('statusCheckRollup') or []:
            name=check.get('name') or check.get('context');status=check.get('conclusion') or check.get('state') or check.get('status') or 'UNKNOWN'
            checks.append({'name':name,'status':'success' if status=='SUCCESS' else status.lower(),'required':name in required})
        return {**context,'head':raw['headRefOid'],'base_oid':raw['baseRefOid'],'changed_files':[f['filename'] for f in files],'pr':{'id':raw['id'],'number':raw['number'],'url':raw['url']},'state':raw['state'],'merge_commit':(raw.get('mergeCommit') or {}).get('oid'),'mergeable':raw['mergeable'],'reviews':reviews,'comments':comments+inline,'threads':threads,'checks':checks,'checks_known':policy.get('checks_known') is True,'required_checks_missing':sorted(required-{c['name'] for c in checks}),'approvals_known':policy.get('approvals_known') is True,'approvals_required':policy.get('approvals_required',True),'approved':raw.get('reviewDecision')=='APPROVED'}
    def merge(self,number,head,method):
        if method not in {'merge','squash','rebase'}:raise ReviewError('Repository-approved merge method required')
        return self.gh('api','--method','PUT','repos/'+self.repository+'/pulls/'+str(number)+'/merge','-f','sha='+head,'-f','merge_method='+method)

def new_record(snapshot,params):
    if not params['authorization'].get('pr'):raise ReviewError('Publication requires the direct owner invocation')
    return {'schema':1,'identity':identity(snapshot),'snapshot_key':review_key(snapshot),'authorization':params['authorization'],'status':'pr-review-in-progress','pr':snapshot.get('pr'),'rounds':[],'operations':{}}

def operation(record,key,request,result=None):
    record=deepcopy(record);ops=record.setdefault('operations',{});signature=digest(request)
    if key in ops:
        if ops[key]['request_digest']!=signature:raise ReviewError('Publication operation key replay conflicts with the original request')
        if ops[key].get('result') is not None:
            if result is not None and ops[key]['result']!=result:raise ReviewError('Publication result replay conflict')
            return record
    slot=ops.setdefault(key,{'request_digest':signature,'state':'prepared'})
    if result is not None:slot.update({'state':'confirmed','result':result})
    return record

def local_fast_forward(root,target,remote):
    # Never switch another worktree or overwrite divergence/dirty changes.
    rows=ws.git(root,'worktree','list','--porcelain').split('\n\n')
    occupied=any('branch refs/heads/'+target in row for row in rows)
    if occupied:return {'updated':False,'reason':'Target branch belongs to an existing worktree'}
    ws.git(root,'fetch','--no-tags',remote)
    ref='refs/heads/'+target;remote_ref='refs/remotes/'+remote+'/'+target
    try:old=ws.git(root,'rev-parse','--verify',ref)
    except ws.RunError:
        ws.git(root,'branch',target,remote_ref);return {'updated':True}
    ws.git(root,'merge-base','--is-ancestor',old,remote_ref)
    new=ws.git(root,'rev-parse',remote_ref)
    ws.git(root,'update-ref',ref,new,old);return {'updated':True,'commit':new}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['parameters','preflight','init','observe','review','ready','merge-gate','operation','block','hook-attach','inspection','review-reconcile','plugin-findings'])
    parser.add_argument('root',type=Path);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--publication-id')
    args=parser.parse_args(argv)
    try:
        payload=json.loads(args.input.read_text());root=args.root.resolve()
        if args.command=='parameters':result=parameters(payload.get('current_branch',ws.git(root,'symbolic-ref','--short','HEAD')),payload)
        elif args.command=='preflight':result=preflight(root,payload)
        else:
            # Metadata-only commands never send provider requests. The agent supplies inspected snapshots.
            canonical=ws.canonical(root);snapshot=payload.get('snapshot',{})
            key=args.publication_id or digest({k:snapshot[k] for k in ['repo_id','remote','source_branch','target_branch']})[:32]
            if not re.fullmatch(r'[a-f0-9]{32}',key):raise ReviewError('Invalid publication ID')
            wf=owned_module('pr_workflow',Path(__file__).with_name('workflow-state.py'))
            store=wf.Store(root,allow_unselected=True)
            with ws.publication_lock(root,snapshot.get('remote','origin'),snapshot.get('target_branch',key)):
                carrier=canonical/('.skill-tree/history/publications/pub-'+key+'.json');carrier_hash=hashlib.sha256(carrier.read_bytes()).hexdigest() if carrier.exists() else None
                original=json.loads(carrier.read_text()) if carrier.exists() else None
                overrides=payload.get('run_overrides',(original or {}).get('review_requirements',{}).get('configuration',{}).get('run_overrides',{}))
                prepared_review=review_requirement_plan(store,snapshot,record=original,package_root=payload.get('package_root'),run_overrides=overrides,publication_id=key)
                store._review_requirement_preflight=prepared_review
                if args.command in {'ready','merge-gate'}:
                    prior=canonical/('.skill-tree/history/publications/pub-'+key+'.json')
                    inspected_carrier=_retire_review_hook_references(store,json.loads(prior.read_text()),snapshot) if prior.exists() else None
                    if inspected_carrier:
                        wf.prepare_hook_admission(store,chain_ids=inspected_carrier.get('hook_chains',[]))
                with store.lock():
                    relative='.skill-tree/history/publications/pub-'+key+'.json';path=canonical/relative
                    record=json.loads(path.read_text()) if path.exists() else None
                    if (hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None)!=carrier_hash:raise ReviewError('The inspected publication carrier changed before the writer')
                    if prepared_review:wf._hook_watch_guard(prepared_review['watch'],prepared_review['package_root'])
                    record=_retire_review_hook_references(store,record,snapshot)
                    if args.command=='init':
                        params=parameters(snapshot['source_branch'],payload)
                        if params['source_branch']!=snapshot['source_branch'] or params['target_branch']!=snapshot['target_branch']:raise ReviewError('Publication parameter/snapshot identity conflict')
                        result=reconcile(record,snapshot) if record else new_record(snapshot,params)
                        result['publication_id']=key
                        if prepared_review and 'review_requirements' not in result:result['review_requirements']=_frozen_review_requirements(store,prepared_review)
                        if record and params['merge_explicit']:
                            result.setdefault('authorization_history',[]).append(deepcopy(result['authorization']))
                            result['authorization']=params['authorization']
                    else:
                        if not record:raise ReviewError('Initialize or select the existing publication record')
                        if args.command=='observe':result=reconcile(record,snapshot)
                        elif args.command=='review':result=reviewed(record,snapshot,payload['review'])
                        elif args.command=='inspection':result=inspected(record,snapshot,payload['inspection'])
                        elif args.command=='review-reconcile':result=reconcile_review_requirements(store,record,snapshot,key,prepared_review,payload['decision_receipt'])
                        elif args.command=='plugin-findings':result=incorporate_review_findings(store,record,snapshot,key,payload)
                        elif args.command=='hook-attach':result=attach_hook_chain(store,record,snapshot,payload['chain_id'])
                        elif args.command=='ready':result=ready(record,snapshot,store=store)
                        elif args.command=='merge-gate':result=merge_gate(record,snapshot,store=store)
                        elif args.command=='block':
                            if not payload.get('reason'):raise ReviewError('Publication block requires the actual prerequisite or failure')
                            result=deepcopy(record);result['status']='blocked';result['blocked_reason']=payload['reason']
                        else:result=operation(record,payload['key'],payload['request'],payload.get('result'))
                    if prepared_review:wf._hook_watch_guard(prepared_review['watch'],prepared_review['package_root'])
                    store.commit({relative:json.dumps(result,sort_keys=True,indent=2)+'\n'})
                    if store.state.exists():
                        state=store.load();registry=state.get('run_registry')
                        matches=[r for r in registry['runs'].values() if r.get('workspace',{}).get('branch')==result['identity']['source_branch']] if registry else []
                        if len(matches)>1:raise ReviewError('Publication run identity is ambiguous')
                        if matches:
                            run=matches[0];run.setdefault('delivery',{})['publication']=relative
                            run['delivery']['status']=result['status'];run['delivery']['authorization']=result['authorization']
                            run['delivery']['order_completed']=result['status']=='merged' or result['status']=='pr-ready' and not result['authorization'].get('merge')
                            run['delivery']['pr']=result.get('pr');run['delivery']['merge_commit']=result.get('merge_commit')
                            store.save(store.text(),state)
            result={'publication_id':key,**result}
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (ReviewError,ws.RunError,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
