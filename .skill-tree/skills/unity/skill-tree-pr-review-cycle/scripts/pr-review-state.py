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

_spec=importlib.util.spec_from_file_location('pr_workspaces',Path(__file__).with_name('run-workspaces.py'))
ws=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(ws)

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
    spec=importlib.util.spec_from_file_location('review_decision_governance',Path(__file__).with_name('decision-governance.py'))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
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
    record=reconcile(record,snapshot)
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

def ready(record,snapshot):
    record=reconcile(record,snapshot)
    if record['status']=='merged':return record
    if record['status']=='blocked':raise ReviewError(record['blocked_reason'])
    if not record.get('pr') or not record['pr'].get('id') or not record['pr'].get('url'):raise ReviewError('PR readiness requires the existing provider PR identity and URL')
    review=record.get('review')
    if not review or review['key']!=review_key(snapshot) or review['unresolved']:
        raise ReviewError('Current full review or actionable finding verification remains incomplete')
    if any(not t.get('resolved') and (t.get('required') or t.get('actionable')) for t in snapshot.get('threads',[])):
        raise ReviewError('Mandatory/actionable PR discussions remain unresolved')
    if snapshot.get('checks_known') is not True:raise ReviewError('Required check policy is unknown')
    checks=snapshot.get('checks',[])
    if any(c.get('required') and c.get('status')!='success' for c in checks):raise ReviewError('Required checks remain pending or failed')
    if snapshot.get('required_checks_missing'):raise ReviewError('Required checks are missing')
    record['ci']='not-configured' if not checks else 'required-checks-passed'
    record['status']='pr-ready';return record

def merge_gate(record,snapshot):
    record=ready(record,snapshot)
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
    return {'schema':1,'identity':identity(snapshot),'authorization':params['authorization'],'status':'pr-review-in-progress','pr':snapshot.get('pr'),'rounds':[],'operations':{}}

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
    parser.add_argument('command',choices=['parameters','preflight','init','observe','review','ready','merge-gate','operation','block'])
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
            spec=importlib.util.spec_from_file_location('pr_workflow',Path(__file__).with_name('workflow-state.py'));wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)
            store=wf.Store(canonical,allow_unselected=True)
            with ws.publication_lock(root,snapshot.get('remote','origin'),snapshot.get('target_branch',key)):
                with store.lock():
                    relative='.skill-tree/history/publications/pub-'+key+'.json';path=canonical/relative
                    record=json.loads(path.read_text()) if path.exists() else None
                    if args.command=='init':
                        params=parameters(snapshot['source_branch'],payload)
                        if params['source_branch']!=snapshot['source_branch'] or params['target_branch']!=snapshot['target_branch']:raise ReviewError('Publication parameter/snapshot identity conflict')
                        result=reconcile(record,snapshot) if record else new_record(snapshot,params)
                        if record and params['merge_explicit']:
                            result.setdefault('authorization_history',[]).append(deepcopy(result['authorization']))
                            result['authorization']=params['authorization']
                    else:
                        if not record:raise ReviewError('Initialize or select the existing publication record')
                        if args.command=='observe':result=reconcile(record,snapshot)
                        elif args.command=='review':result=reviewed(record,snapshot,payload['review'])
                        elif args.command=='ready':result=ready(record,snapshot)
                        elif args.command=='merge-gate':result=merge_gate(record,snapshot)
                        elif args.command=='block':
                            if not payload.get('reason'):raise ReviewError('Publication block requires the actual prerequisite or failure')
                            result=deepcopy(record);result['status']='blocked';result['blocked_reason']=payload['reason']
                        else:result=operation(record,payload['key'],payload['request'],payload.get('result'))
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
