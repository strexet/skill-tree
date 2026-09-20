#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/workflow-state.py; generator: skill-tree/scripts/sync-skill-references.py
"""Manage current Skill Tree task metadata, checkpoints and bounded evidence."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import unicodedata
import uuid

QUEUES = ['Pending Queue', 'Prioritized Next Changes', 'Backlog']
FIELDS = ['id', 'priority', 'status', 'parent_pending_ids', 'processing_run_id', 'root_task_id', 'related_task_id', 'relation', 'depends_on']
SECTIONS = ['Goal', 'Current behavior', 'Desired behavior', 'Touch', 'Discovery allowance', 'Out of scope', 'Implementation constraints', 'Questions and required clarifications', 'Validation', 'Acceptance', 'Documentation updates', 'Risks']
RELATIONS = {'main', 'blocker', 'subtask', 'followup'}
TERMINAL = {'completed', 'cancelled', 'superseded', 'merged'}
FORMAT = 'skill-tree-future'

class WorkflowError(ValueError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def identity(prefix):
    return f'{prefix}-{uuid.uuid4()}'

def valid_id(value, prefix):
    if not isinstance(value, str) or not value.startswith(prefix+'-'):
        return False
    try:
        return str(uuid.UUID(value[len(prefix)+1:])) == value[len(prefix)+1:]
    except ValueError:
        return False

def normalized(value):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', value).strip()).casefold()

def digest(content):
    return hashlib.sha256(content).hexdigest()

def file_hash(path):
    return digest(path.read_bytes()) if path.exists() else None

def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)+'\n'

def assert_prose(text):
    path=Path(__file__).with_name('validate-document-rules.py')
    spec=importlib.util.spec_from_file_location('skill_tree_document_rules',path);rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
    if not isinstance(text,str):raise WorkflowError('Generated prose requires a string')
    errors=rules.check_text(text)
    if errors:raise WorkflowError('Generated prose violates document rules: '+', '.join(errors))

def validate_metadata(meta, queue):
    missing = set(FIELDS)-set(meta)
    if missing:
        raise WorkflowError('Task header missing fields: '+', '.join(sorted(missing)))
    prefix = {'Pending Queue':'P','Prioritized Next Changes':'T','Backlog':'B'}[queue]
    if not valid_id(meta['id'], prefix):
        raise WorkflowError('Invalid task identity for '+queue)
    if type(meta['priority']) is not int:
        raise WorkflowError('Priority requires an integer')
    statuses = {'Pending Queue':{'Pending'}, 'Prioritized Next Changes':{'Ready','Blocked pending answers'}, 'Backlog':{'Backlog'}}
    if meta['status'] not in statuses[queue]:
        raise WorkflowError('Invalid task status for '+queue)
    if meta['relation'] not in RELATIONS:
        raise WorkflowError('Invalid task relation')
    for field, kind in [('parent_pending_ids','P'),('depends_on','T')]:
        values=meta[field]
        if not isinstance(values,list) or any(not valid_id(v,kind) for v in values) or len(values)!=len(set(values)):
            raise WorkflowError('Invalid identity list: '+field)
    for field, kind in [('processing_run_id','PR'),('root_task_id','T'),('related_task_id','T')]:
        if meta[field] is not None and not valid_id(meta[field],kind):
            raise WorkflowError('Invalid identity: '+field)
    if meta['relation'] in {'blocker','subtask','followup'} and (meta['root_task_id'] is None or meta['related_task_id'] is None):
        raise WorkflowError('Related work requires root and direct-parent task IDs')
    if queue=='Prioritized Next Changes' and not meta['parent_pending_ids']:
        raise WorkflowError('Prioritized tasks require Pending provenance')
    if meta['id'] in meta['depends_on']:
        raise WorkflowError('A task cannot depend on the task identity')

def parse(text):
    """Read fixed headers; task bodies remain outside the metadata index."""
    lines=text.splitlines(keepends=True); queue=None; found=[]; entries=[]; current=None; fenced=False
    for i,line in enumerate(lines):
        if line.startswith('```'):
            fenced=not fenced
            continue
        if fenced:
            continue
        h=re.match(r'^(#{1,3})\s+(.+?)\s*$',line)
        if not h:
            continue
        level=len(h[1]); title=h[2]
        if level<=3 and current is not None:
            current['end']=i; entries.append(current); current=None
        if level==2:
            queue=title if title in QUEUES else None
            if queue:
                found.append(queue)
        elif level==3 and queue:
            current={'title':title,'queue':queue,'start':i}
    if current is not None:
        current['end']=len(lines);entries.append(current)
    format_line=next((i for i,line in enumerate(lines) if line.strip()=='## Pending Task Format'),None)
    pending_line=next((i for i,line in enumerate(lines) if line.strip()=='## Pending Queue'),None)
    if format_line is None or pending_line is None or format_line>=pending_line:raise WorkflowError('Pending Task Format must precede Pending Queue')
    if found!=QUEUES:
        raise WorkflowError('Queue order requires Pending Queue, Prioritized Next Changes, Backlog')
    seen=set()
    for task in entries:
        body=''.join(lines[task['start']:task['end']]); match=re.match(r'^###[^\n]+\n\s*```yaml\n(.*?)\n```',body,re.S)
        if not match:
            raise WorkflowError(task['title']+': current task header required; run explicit documentation setup')
        meta={}
        for line in match[1].splitlines():
            if ':' not in line:
                raise WorkflowError('Malformed task header')
            key,value=line.split(':',1); key=key.strip();value=value.strip()
            if key in meta or key not in FIELDS:
                raise WorkflowError('Duplicate or unknown task field: '+key)
            if value in {'null','[]'} or value.startswith('[') or value.startswith('"') or re.fullmatch(r'-?\d+',value):
                try: value=json.loads(value)
                except json.JSONDecodeError as exc: raise WorkflowError('Invalid header value: '+key) from exc
            meta[key]=value
        validate_metadata(meta,task['queue'])
        if meta['id'] in seen: raise WorkflowError('Duplicate task ID: '+meta['id'])
        seen.add(meta['id']); task.update(meta);task['body']=body;task['line']=task['start']+1
        if task['queue']=='Prioritized Next Changes':
            for section in SECTIONS:
                if not re.search(r'(?m)^'+re.escape(section)+r':\s*$',body):
                    raise WorkflowError(task['title']+': missing section '+section)
            blocked='[Unresolved - blocks implementation]' in body or '[Unresolved — blocks implementation]' in body
            if blocked != (task['status']=='Blocked pending answers'):
                raise WorkflowError('Blocking question and status disagree: '+task['title'])
    return entries

def index(text):
    return [{k:v for k,v in t.items() if k not in {'body','start','end'}} for t in parse(text)]

def resolve(tasks, selectors, queue=None):
    eligible=[t for t in tasks if queue is None or t['queue']==queue]
    if not selectors: return eligible
    result=[]
    for value in selectors:
        matches=[t for t in eligible if t['id']==value]
        if not matches: matches=[t for t in eligible if normalized(t['title'])==normalized(value)]
        if len(matches)!=1:
            raise WorkflowError('Absent or ambiguous task selection: '+value)
        if matches[0]['id'] in [t['id'] for t in result]: raise WorkflowError('Repeated task selection: '+value)
        result.append(matches[0])
    return result

def select(tasks, selector=None):
    choices=resolve(tasks,[selector] if selector else [],'Prioritized Next Changes')
    if not choices: raise WorkflowError('No prioritized tasks')
    task=choices[0] if selector else max(choices,key=lambda t:t['priority'])
    if task['status']!='Ready': raise WorkflowError('Selected task has blocking unresolved questions: '+task['id'])
    return task

def render(title,meta,body):
    if not title.strip() or '\n' in title: raise WorkflowError('Task title requires one nonempty line')
    header='\n'.join(k+': '+(json.dumps(meta[k],ensure_ascii=False) if not isinstance(meta[k],str) else meta[k]) for k in FIELDS)
    return '### '+title+'\n\n```yaml\n'+header+'\n```\n\n'+body.strip()+'\n\n'

def insert(text,queue,entry):
    # Insert before equal-priority peers; preserve all existing entries.
    tasks=[t for t in parse(text) if t['queue']==queue]
    p=parse_entry_priority(entry)
    lines=text.splitlines(keepends=True)
    target=next((t['start'] for t in tasks if t['priority']<=p),None)
    if target is None:
        queue_start=next(i for i,l in enumerate(lines) if l.strip()=='## '+queue)
        target=next((i for i in range(queue_start+1,len(lines)) if lines[i].startswith('## ')),len(lines))
    lines.insert(target,entry)
    return ''.join(lines)

def parse_entry_priority(entry):
    return int(re.search(r'(?m)^priority: (-?\d+)$',entry)[1])

def remove(text,ids):
    tasks=parse(text);lines=text.splitlines(keepends=True)
    for task in reversed(tasks):
        if task['id'] in ids: del lines[task['start']:task['end']]
    return ''.join(lines)

def rewrite_meta(text,task_id,changes):
    task=resolve(parse(text),[task_id])[0]
    meta={k:deepcopy(task[k]) for k in FIELDS};meta.update(changes)
    validate_metadata(meta,task['queue'])
    match=re.match(r'^###[^\n]+\n\s*```yaml\n.*?\n```\s*',task['body'],re.S)
    entry=render(task['title'],meta,task['body'][match.end():])
    lines=text.splitlines(keepends=True);lines[task['start']:task['end']]=[entry]
    return ''.join(lines)

class Store:
    def __init__(self,root):
        self.root=Path(root).resolve();self.base=self.root/'skill-tree';self.future=self.base/'documents/future.md';self.state=self.base/'documents/future.json'
        if not self.root.is_dir(): raise WorkflowError('Target repository does not exist')
        if self.base.is_symlink(): raise WorkflowError('Owned metadata directory cannot be a symlink')
    def owned(self,relative):
        path=self.root/relative
        if not relative.startswith('skill-tree/') or not path.resolve().is_relative_to(self.base.resolve()) or self.base.is_symlink():
            raise WorkflowError('Metadata path outside owned directory: '+relative)
        return path
    @contextmanager
    def lock(self):
        self.base.mkdir(exist_ok=True)
        path=self.base/'.writer-lock'
        try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise WorkflowError('Writer lock exists; verify owner PID/host before explicit lock removal') from exc
        try:
            os.write(fd,dump({'pid':os.getpid(),'host':socket.gethostname()}).encode());os.close(fd)
            self.recover()
            mutable=[self.future,self.state,self.base/'skill-tree.json',self.base/'history/task-outcomes.jsonl',*list((self.base/'history').rglob('*.json'))]
            self._write_hashes={p.relative_to(self.root).as_posix():file_hash(p) for p in mutable}
            yield
        finally:
            path.unlink(missing_ok=True)
    def replace(self,path,content):
        path.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='transaction-',dir=path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temp,path)
        finally:
            Path(temp).unlink(missing_ok=True)
    def recover(self):
        journal=self.base/'.transaction.json'
        if not journal.exists(): return
        record=json.loads(journal.read_text())
        if record.get('format')!='skill-tree-transaction' or not isinstance(record.get('writes'),list): raise WorkflowError('Unsupported transaction state')
        # Validate every target before replay, including already-applied writes.
        for write in record['writes']:
            path=self.owned(write['path']);actual=file_hash(path);desired=digest(write['content'].encode())
            if actual not in {write['expected_hash'],desired}: raise WorkflowError('Interrupted transaction conflicts with source: '+write['path'])
        for write in record['writes']:
            self.replace(self.owned(write['path']),write['content'])
        journal.unlink()
    def commit(self,writes):
        record={'format':'skill-tree-transaction','writes':[]}
        for rel,content in writes.items():
            path=self.owned(rel);actual=file_hash(path);expected=getattr(self,'_write_hashes',{}).get(rel,actual)
            if actual!=expected:raise WorkflowError('Metadata changed during the operation; preserve developer changes: '+rel)
            record['writes'].append({'path':rel,'expected_hash':expected,'content':content})
        self.replace(self.base/'.transaction.json',dump(record));self.recover()
        if hasattr(self,'_write_hashes'):
            for write in record['writes']:self._write_hashes[write['path']]=digest(write['content'].encode())
    def text(self):
        self.owned('skill-tree/documents/future.md')
        if not self.future.is_file(): raise WorkflowError('Missing skill-tree/documents/future.md; run explicit documentation setup')
        return self.future.read_text()
    def load(self,text=None):
        text=self.text() if text is None else text
        value={'format':FORMAT,'source_hash':digest(text.encode()),'tasks':index(text),'active_run':None}
        self.owned('skill-tree/documents/future.json')
        if self.state.exists():
            old=json.loads(self.state.read_text())
            if old.get('format')!=FORMAT or not isinstance(old.get('tasks'),list) or 'active_run' not in old: raise WorkflowError('Unsupported checkpoint; reinstall and run explicit setup')
            run=old['active_run']
            if run is not None:
                validate_run(run)
            value['active_run']=run
        return value
    def outcomes(self):
        path=self.base/'history/task-outcomes.jsonl'
        if not path.exists(): return []
        try: return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except json.JSONDecodeError as exc: raise WorkflowError('Corrupt task outcome ledger') from exc
    def save(self,text,state,extras=None):
        state['source_hash']=digest(text.encode());state['tasks']=index(text)
        writes=dict(extras or {})
        if text!=self.text(): writes['skill-tree/documents/future.md']=text
        writes['skill-tree/documents/future.json']=dump(state)
        self.commit(writes)
        self.commit({'skill-tree/skill-tree.json':dump(manifest(self))})
    def guard(self,expected):
        if expected and file_hash(self.future)!=expected: raise WorkflowError('Source changed since inspection; reread selected task')

def validate_run(run):
    required={'id','mode','snapshot','root_task_id','current_task_id','phase','required_ids','deferred_ids','pending_ids','processing_results','completed_ids','limits','next_action','stop_reason'}
    if not isinstance(run,dict) or not required.issubset(run) or not valid_id(run.get('id'),'WR') or run.get('mode') not in {'next','all'}:
        raise WorkflowError('Corrupt active checkpoint')
    for key in ['snapshot','required_ids','deferred_ids','completed_ids']:
        if not isinstance(run[key],list) or any(not valid_id(v,'T') for v in run[key]): raise WorkflowError('Corrupt checkpoint task identities')
    if not isinstance(run['pending_ids'],list) or any(not valid_id(v,'P') for v in run['pending_ids']): raise WorkflowError('Corrupt checkpoint Pending identities')
    for key in ['root_task_id','current_task_id']:
        if run[key] is not None and not valid_id(run[key],'T'): raise WorkflowError('Corrupt checkpoint task pointer')
    if not isinstance(run['limits'],dict) or not isinstance(run['processing_results'],list): raise WorkflowError('Corrupt checkpoint limits/results')
    budget=run['limits'].get('selected_task_budget')
    if budget is not None:
        if not isinstance(budget,dict) or set(budget)!={'limit_seconds','used_seconds','rationale'}:raise WorkflowError('Selected-task budget requires limit_seconds, used_seconds and rationale')
        if type(budget['limit_seconds']) not in {int,float} or budget['limit_seconds']<=0:raise WorkflowError('Selected-task budget limit must be positive')
        if type(budget['used_seconds']) not in {int,float} or budget['used_seconds']<0:raise WorkflowError('Selected-task budget usage must be non-negative')
        if not isinstance(budget['rationale'],str) or not budget['rationale'].strip():raise WorkflowError('Selected-task budget requires a concrete rationale')
    if not isinstance(run['phase'],str) or (run['stop_reason'] is not None and not isinstance(run['stop_reason'],str)):raise WorkflowError('Corrupt checkpoint phase/reason')
    for key in ['partial_work','history_refs']:
        if key in run and (not isinstance(run[key],list) or any(not isinstance(v,str) for v in run[key])):raise WorkflowError('Corrupt checkpoint references')

def intake(store,payload):
    with store.lock():
        store.guard(payload.get('expected_source_hash'));text=store.text();tasks=parse(text);state=store.load(text)
        matches=[t for t in tasks if normalized(t['title'])==normalized(payload['title'])]
        if matches: raise WorkflowError('Possible duplicate task; clarify update/reuse before intake: '+matches[0]['id'])
        relation=payload.get('relation','main');priority=payload.get('priority')
        parent=payload.get('related_task_id');root=payload.get('root_task_id')
        if relation!='main':
            related=resolve(tasks,[parent],'Prioritized Next Changes')[0]
            expected_root=related['root_task_id'] or related['id']
            if root!=expected_root: raise WorkflowError('Finding root does not match direct parent')
            root_task=resolve(tasks,[root],'Prioritized Next Changes')[0]
            if priority is None: priority=max((t['priority'] for t in tasks),default=100)+1 if relation in {'blocker','subtask'} else root_task['priority']-1
        if priority is None: priority=25 if payload.get('low_priority') else 100
        meta={'id':identity('P'),'priority':priority,'status':'Pending','parent_pending_ids':[],'processing_run_id':None,'root_task_id':root,'related_task_id':parent,'relation':relation,'depends_on':[]}
        validate_metadata(meta,'Pending Queue')
        for field in ['description','expected_behavior']:
            if not isinstance(payload.get(field),str) or not payload[field].strip(): raise WorkflowError('Intake requires understood '+field)
        body='Description:\n- '+payload['description']+'\n\nExpected behavior:\n- '+payload['expected_behavior']
        for field,label in [('context','Current context'),('source','Source'),('priority_reason','Priority rationale')]:
            if payload.get(field): body+='\n\n'+label+':\n- '+payload[field]
        assert_prose(payload['title']+'\n'+body)
        text=insert(text,'Pending Queue',render(payload['title'],meta,body))
        run=state['active_run']
        if run:
            run['pending_ids'].append(meta['id']);run['phase']='capture-findings'
        store.save(text,state)
        return meta

def process(store,payload):
    """Apply researched dispositions; receipt scope is explicitly selected first."""
    with store.lock():
        store.guard(payload.get('expected_source_hash'));text=store.text();tasks=parse(text);state=store.load(text)
        selected=resolve(tasks,payload.get('selectors',[]),'Pending Queue'); selected_ids={t['id'] for t in selected}
        dispositions=payload.get('dispositions',{})
        if set(dispositions)!=selected_ids: raise WorkflowError('Every selected Pending ID requires one disposition')
        for result in dispositions.values():
            if result.get('status') not in {'promoted','retained','resolved'} or not result.get('reason'): raise WorkflowError('Processing disposition requires status and reason')
        for result in dispositions.values():assert_prose(result['reason'])
        pr=identity('PR');produced=[];reused=[]; consumed=set();run=state['active_run']
        for spec in payload.get('tasks',[]):
            parents=spec.get('parent_pending_ids',[])
            if not parents or not set(parents).issubset(selected_ids): raise WorkflowError('Produced task requires selected Pending provenance')
            sources=[t for t in selected if t['id'] in parents]
            contexts={(t['root_task_id'],t['related_task_id'],t['relation']) for t in sources}
            if len(contexts)!=1: raise WorkflowError('Conflicting task roots/relationships require clarification before merge')
            root,parent,relation=next(iter(contexts));consumed.update(parents)
            if any(dispositions[p]['status']!='promoted' for p in parents): raise WorkflowError('Produced task conflicts with Pending disposition')
            if spec.get('reuse_id'):
                reused_task=resolve(tasks,[spec['reuse_id']],'Prioritized Next Changes')[0]
                if (reused_task['root_task_id'],reused_task['related_task_id'],reused_task['relation'])!=(root or reused_task['id'],parent,relation): raise WorkflowError('Reused task relationship conflicts')
                merged=list(dict.fromkeys(reused_task['parent_pending_ids']+parents))
                text=rewrite_meta(text,reused_task['id'],{'parent_pending_ids':merged,'processing_run_id':pr});reused.append(reused_task['id']); continue
            assert_prose(spec['title']+'\n'+spec['body'])
            task_id=identity('T')
            priority=spec.get('priority',max(t['priority'] for t in sources))
            meta={'id':task_id,'priority':priority,'status':'Ready','parent_pending_ids':parents,'processing_run_id':pr,'root_task_id':root or task_id,'related_task_id':parent,'relation':relation,'depends_on':spec.get('depends_on',[])}
            validate_metadata(meta,'Prioritized Next Changes')
            if any(t['id'] not in parents and normalized(t['title'])==normalized(spec['title']) for t in parse(text)): raise WorkflowError('Duplicate produced title requires explicit reuse')
            text=insert(text,'Prioritized Next Changes',render(spec['title'],meta,spec['body']));produced.append(task_id)
        if {p for p in selected_ids if dispositions[p]['status']=='promoted'}!=consumed: raise WorkflowError('Promoted Pending task requires produced or reused task')
        for source in selected:
            if dispositions[source['id']]['status']=='retained':
                old=resolve(parse(text),[source['id']])[0]
                lines=text.splitlines(keepends=True)
                body=old['body'].rstrip()+'\n\nProcessing blocker:\n- '+dispositions[source['id']]['reason']+'\n\n'
                lines[old['start']:old['end']]=[body];text=''.join(lines)
        # Attach promoted required work to the direct parent before removing intake.
        updated=parse(text)
        for tid in produced+reused:
            child=resolve(updated,[tid])[0]
            if child['relation'] in {'blocker','subtask'}:
                parent_task=resolve(parse(text),[child['related_task_id']],'Prioritized Next Changes')[0]
                text=rewrite_meta(text,parent_task['id'],{'depends_on':list(dict.fromkeys(parent_task['depends_on']+[tid]))})
            if run:
                key='required_ids' if child['relation'] in {'blocker','subtask'} else 'deferred_ids'
                if tid not in run[key]:run[key].append(tid)
        text=remove(text,{p for p in selected_ids if dispositions[p]['status']!='retained'})
        receipt={'id':pr,'selected_ids':[t['id'] for t in selected],'created_ids':produced,'reused_ids':reused,'dispositions':dispositions}
        if run: run['processing_results'].append(receipt);run['phase']='dependencies';run['next_action']='Select required task'
        store.save(text,state)
        return receipt

def start(store,mode,selector=None,limits=None):
    with store.lock():
        text=store.text();state=store.load(text)
        if state['active_run'] is not None: raise WorkflowError('Active run exists; resume the recorded run')
        tasks=parse(text);chosen=select(tasks,selector)
        snapshot=[chosen['id']] if mode=='next' else [t['id'] for t in sorted([t for t in tasks if t['queue']=='Prioritized Next Changes'],key=lambda t:-t['priority'])]
        if mode=='all' and selector:raise WorkflowError('Implement All uses the initial prioritized snapshot')
        run={'id':identity('WR'),'mode':mode,'snapshot':snapshot,'root_task_id':chosen['id'],'current_task_id':chosen['id'],'phase':'implement','required_ids':[chosen['id']],'deferred_ids':[],'pending_ids':[],'processing_results':[],'completed_ids':[],'limits':limits or {},'partial_work':[],'stop_reason':None,'next_action':'Implement selected task','started_at':now()}
        validate_run(run);state['active_run']=run;store.save(text,state);return run

def enforce_limits(run):
    if run.get('stop_reason'):raise WorkflowError('Run stopped: '+str(run['stop_reason'])+'; resolve the recorded condition before explicit checkpoint resumption')
    budget=run['limits'].get('selected_task_budget')
    if budget is not None and budget['used_seconds']>=budget['limit_seconds']:raise WorkflowError('Selected-task budget exhausted')

def next_task(store):
    state=store.load();run=state['active_run']
    if not run:raise WorkflowError('No active run')
    enforce_limits(run);tasks=parse(store.text());by_id={t['id']:t for t in tasks};done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
    visiting=set();visited=set()
    def walk(tid):
        if tid in done:return []
        if tid in visiting:raise WorkflowError('Dependency cycle: '+tid)
        if tid not in by_id:raise WorkflowError('Missing task without completion evidence: '+tid)
        task=by_id[tid]
        if task['queue']!='Prioritized Next Changes':raise WorkflowError('Required task outside prioritized queue')
        if tid in visited:return []
        visiting.add(tid);candidates=[]
        for dep in task['depends_on']:candidates.extend(walk(dep))
        visiting.remove(tid);visited.add(tid)
        if not candidates and all(dep in done for dep in task['depends_on']):candidates.append(task)
        return candidates
    root=run['root_task_id']
    if root in done:
        remaining=[tid for tid in run['snapshot'] if tid not in done]
        if not remaining:return {'phase':'deferred-processing','pending_ids':[t['id'] for t in tasks if t['queue']=='Pending Queue' and t['id'] in run['pending_ids'] and t['relation']=='followup']}
        # Current priorities decide remaining initial roots; absent entries never count as done.
        for tid in remaining:
            if tid not in by_id:raise WorkflowError('Initial task missing without completion evidence: '+tid)
        root=max(remaining,key=lambda tid:by_id[tid]['priority'])
    candidates=walk(root)
    if not candidates:raise WorkflowError('Required dependency closure has no actionable task')
    task=max(candidates,key=lambda t:t['priority'])
    if task['status']!='Ready':raise WorkflowError('Selected required task has blocking unresolved questions: '+task['id'])
    pending=[t['id'] for t in tasks if t['queue']=='Pending Queue' and t['root_task_id']==root and t['relation'] in {'blocker','subtask'}]
    if pending:return {'phase':'process-required','root_task_id':root,'pending_ids':pending}
    return {'phase':'implement','root_task_id':root,'task_id':task['id'],'title':task['title'],'priority':task['priority'],'body':task['body']}

def advance(store):
    with store.lock():
        result=next_task(store);text=store.text();state=store.load(text);run=state['active_run']
        run['phase']=result['phase'];run['current_task_id']=result.get('task_id');run['root_task_id']=result.get('root_task_id',run['root_task_id']);run['next_action']=result['phase']
        if result.get('task_id') and result['task_id'] not in run['required_ids']:run['required_ids'].append(result['task_id'])
        store.save(text,state);return result

def checkpoint(store,payload):
    allowed={'phase','partial_work','stop_reason','next_action','validation_consumed','task_budget_used_seconds','history_refs'}
    if set(payload)-allowed:raise WorkflowError('Checkpoint contains unsupported fields')
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        consumed=payload.get('validation_consumed',{})
        if not isinstance(consumed,dict):raise WorkflowError('Invalid consumed validation counters')
        for k,v in consumed.items():
            if k not in {'retry_used','repair_used','reload_used'} or type(v) is not int or v<run['limits'].get(k,0):raise WorkflowError('Validation counters cannot decrease')
            run['limits'][k]=v
        if 'task_budget_used_seconds' in payload:
            budget=run['limits'].get('selected_task_budget')
            used=payload['task_budget_used_seconds']
            if budget is None:raise WorkflowError('No selected-task budget exists')
            if type(used) not in {int,float} or used<budget['used_seconds']:raise WorkflowError('Selected-task budget usage cannot decrease')
            budget['used_seconds']=used
        run.update({k:v for k,v in payload.items() if k not in {'validation_consumed','task_budget_used_seconds'}});validate_run(run);store.save(text,state);return run

def complete(store,payload):
    with store.lock():
        store.guard(payload.get('expected_source_hash'));text=store.text();tasks=parse(text);state=store.load(text);task=resolve(tasks,[payload['task_id']],'Prioritized Next Changes')[0]
        outcomes=store.outcomes();done={o['task_id'] for o in outcomes if o['disposition']=='completed'}
        if task['id'] in {o['task_id'] for o in outcomes}:raise WorkflowError('Task already has terminal outcome')
        disposition=payload.get('disposition','completed')
        if disposition not in TERMINAL:raise WorkflowError('Unsupported terminal disposition')
        if not payload.get('outcome'):raise WorkflowError('Terminal outcome requires delivered behavior or reason')
        assert_prose(payload['outcome'])
        for limitation in payload.get('limitations',[]):assert_prose(limitation)
        if disposition=='completed':
            run=state['active_run']
            if run:enforce_limits(run)
            if task['status']!='Ready':raise WorkflowError('Blocked task cannot complete')
            if any(dep not in done for dep in task['depends_on']):raise WorkflowError('Required dependencies remain incomplete')
            if any(t['queue']=='Pending Queue' and t['related_task_id']==task['id'] and t['relation'] in {'blocker','subtask'} for t in tasks):raise WorkflowError('Required Pending work remains unprocessed')
            checks=payload.get('acceptance',[])
            if not checks or any(not c.get('criterion') or not c.get('result') for c in checks):raise WorkflowError('Completion requires individual acceptance results')
            if any(c.get('required',True) is not True or c['result']!='pass' or not c.get('evidence') for c in checks):raise WorkflowError('Mandatory acceptance requires passing matching evidence')
            if not payload.get('source_fingerprints'):raise WorkflowError('Completion requires recorded source fingerprints')
            if any(v is None for v in payload['source_fingerprints'].values()) or fingerprints(store,list(payload['source_fingerprints']))!=payload['source_fingerprints']:raise WorkflowError('Completion source fingerprints do not match current repository')
            acceptance_body=task['body'].split('Acceptance:',1)[1].split('Documentation updates:',1)[0]
            expected=[line[2:].strip() for line in acceptance_body.splitlines() if line.startswith('- ')]
            criteria=[c['criterion'] for c in checks]
            if not expected or len(criteria)!=len(set(criteria)) or set(criteria)!=set(expected):raise WorkflowError('Acceptance results must cover exactly the recorded task criteria')
            for check in checks:
                if not isinstance(check['evidence'],list):raise WorkflowError('Acceptance evidence requires repository-relative file references')
                check['evidence']=[evidence_pointer(store,ref,required=True) for ref in check['evidence']]
        record={'depends_on':task['depends_on'],'id':identity('O'),'task_id':task['id'],'title':task['title'],'root_task_id':task['root_task_id'],'related_task_id':task['related_task_id'],'parent_pending_ids':task['parent_pending_ids'],'disposition':disposition,'outcome':payload['outcome'],'acceptance':payload.get('acceptance',[]),'limitations':payload.get('limitations',[]),'followup_ids':payload.get('followup_ids',[]),'source_fingerprints':payload.get('source_fingerprints',{}),'commits':payload.get('commits',[]),'evidence':[evidence_pointer(store,e) for e in payload.get('evidence',[])],'recorded_at':now()}
        ledger=''.join(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n' for o in outcomes+[record])
        if state['active_run']:
            run=state['active_run'];run.setdefault('completion_refs',{})[task['id']]=record['id'];run['completed_ids'].append(task['id']) if disposition=='completed' else None
            run['current_task_id']=None;run['phase']='resume-parent';run['next_action']='Select required task or finish root'
        text=remove(text,{task['id']});store.save(text,state,{'skill-tree/history/task-outcomes.jsonl':ledger});return record

def finish(store):
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
        required=set(run['snapshot']+run['required_ids'])
        if not required.issubset(done):raise WorkflowError('Main tasks or required descendants remain incomplete')
        if any(t['id'] in run['pending_ids'] and t['relation'] in {'blocker','subtask'} for t in parse(text)):raise WorkflowError('Required Pending tasks remain')
        followups=[t for t in parse(text) if t['id'] in run['pending_ids'] and t['relation']=='followup']
        if any(t['id'] not in {p for r in run['processing_results'] for p in r['selected_ids']} for t in followups):raise WorkflowError('Nonblocking findings require one processing pass before finish')
        summary=deepcopy(run);summary['finished_at']=now();summary['phase']='completed';summary['next_action']=None
        state['active_run']=None;store.save(text,state,{'skill-tree/history/runs/run-'+run['id'].lower()+'.json':dump(summary)})
    prune(store,True);return summary

def record_cycle(store):
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        semantic_fields=['id','queue','priority','status','parent_pending_ids','root_task_id','related_task_id','relation','depends_on']
        task_state=[{key:task[key] for key in semantic_fields} for task in state['tasks']]
        signature=digest(dump({'tasks':task_state,'outcomes':[o['task_id'] for o in store.outcomes()]}).encode())
        if run.get('cycle_signature')==signature:
            run['phase']='blocked';run['stop_reason']='Completed cycle without task/dependency progress';run['next_action']='Resolve recorded blocker before resumption'
        run['cycle_signature']=signature;store.save(text,state);return run

def fingerprints(store,paths):
    result={}
    for rel in paths:
        path=store.root/rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or not path.resolve().is_relative_to(store.root):raise WorkflowError('Source fingerprint requires repository-relative path')
        result[rel]=file_hash(path)
    return result

def audit(store,payload):
    with store.lock():
        if not payload.get('scope') or not payload.get('sources') or 'checks' not in payload or 'coverage_gaps' not in payload:raise WorkflowError('Audit requires scope, inspected sources, checks and coverage gaps')
        for gap in payload['coverage_gaps']:assert_prose(gap)
        record=deepcopy(payload);record['id']=identity('A');record['recorded_at']=now();record['source_fingerprints']=fingerprints(store,payload['sources'])
        for finding in record.get('findings',[]):
            if not finding.get('id') or not finding.get('observation'):raise WorkflowError('Audit finding requires stable ID and observation')
            assert_prose(finding['observation'])
        store.commit({'skill-tree/history/audits/audit-'+record['id'].lower()+'.json':dump(record)})
    prune(store,True);return record

def evidence_pointer(store,reference,required=False):
    ref={'path':reference} if isinstance(reference,str) else deepcopy(reference)
    if not isinstance(ref,dict) or not isinstance(ref.get('path'),str):raise WorkflowError('Evidence requires a repository-relative path')
    actual=fingerprints(store,[ref['path']])[ref['path']]
    if required and (actual is None or (ref.get('sha256') and ref['sha256']!=actual)):raise WorkflowError('Required acceptance evidence missing or mismatched: '+ref['path'])
    ref['available']=actual is not None and (not ref.get('sha256') or ref['sha256']==actual)
    if 'sha256' not in ref:ref['sha256']=actual
    return ref

def history(store,task_id=None,component=None):
    result=[]
    for outcome in store.outcomes():
        if task_id and outcome['task_id']!=task_id:continue
        if component and normalized(component) not in normalized(outcome['title']+' '+outcome['outcome']+' '+' '.join(outcome.get('source_fingerprints',{}))):continue
        view=deepcopy(outcome)
        for check in view.get('acceptance',[]):check['evidence']=[evidence_pointer(store,e) for e in check.get('evidence',[])]
        view['evidence']=[evidence_pointer(store,e) for e in view.get('evidence',[])]
        result.append(view)
    return result

def manifest(store):
    path=store.base/'skill-tree.json';existing=json.loads(path.read_text()) if path.exists() else {}
    role='source' if (store.base/'skills').is_dir() else 'target';files=[]
    for p in sorted((store.base/'documents').glob('*')):
        if p.is_file():files.append({'path':p.relative_to(store.root).as_posix(),'role':'generated-index-and-active-state' if p.name=='future.json' else 'canonical','owner':'skill-tree'})
    catalog=[]
    if role=='source':
        canonical=[*sorted((store.base/'common').rglob('*')),*sorted((store.base/'scripts').glob('*.py')),store.base/'bin/install.js',store.base/'config/providers.json',store.base/'config/resource-map.json',store.base/'src/init-rules/skill-tree-skills.md']
        for p in canonical:
            if p.is_file() and '__pycache__' not in p.parts:files.append({'path':p.relative_to(store.root).as_posix(),'role':'canonical','owner':'skill-tree'})
        for p in sorted((store.base/'skills').glob('*/SKILL.md')):
            catalog.append({'name':p.parent.name,'entrypoint':p.relative_to(store.root).as_posix(),'resources':[r.relative_to(store.root).as_posix() for r in sorted(p.parent.rglob('*')) if r.is_file() and '__pycache__' not in r.parts]})
    audits=[]
    for p in (store.base/'history/audits').glob('*.json'):
        record=json.loads(p.read_text());old=record['source_fingerprints'];fresh=fingerprints(store,list(old))==old
        audits.append({'id':record['id'],'path':p.relative_to(store.root).as_posix(),'recorded_at':record['recorded_at'],'scope':record['scope'],'fresh':fresh})
    audits.sort(key=lambda r:r['recorded_at'])
    result={'format':'skill-tree-manifest','role':role,'files':files,'queue':store.future.relative_to(store.root).as_posix() if store.future.exists() else None,'state':store.state.relative_to(store.root).as_posix() if store.state.exists() else None,'catalog':catalog,'history':{'task_outcomes':'skill-tree/history/task-outcomes.jsonl','audits':'skill-tree/history/audits','runs':'skill-tree/history/runs'},'latest_audit':audits[-1] if audits else None,'audit_scopes':audits,'retention':existing.get('retention',{'audits':10,'runs':10,'pins':[]}),'policy_references':existing.get('policy_references',[rel for rel in ['AGENTS.md','skill-tree/documents/rules.md'] if (store.root/rel).is_file()]),'validation_commands':existing.get('validation_commands',['npm run sync:check','npm run validate','npm run test:py','npm run test:node','git diff --check'] if role=='source' else [])}
    if role=='source':
        result['canonical_resources']={'references':'skill-tree/common/references','scripts':'skill-tree/common/scripts','resource_map':'skill-tree/config/resource-map.json','provider_matrix':'skill-tree/config/providers.json','generator':'skill-tree/scripts/sync-skill-references.py'}
    result['source_digests']={f['path']:file_hash(store.root/f['path']) for f in files if f['role']=='canonical'}
    return result

def prune(store,apply=False):
    config=manifest(store)['retention'];pinned=set(config.get('pins',[]));protected=set(pinned)
    if store.state.exists():
        run=store.load()['active_run']
        if run: protected.update(run.get('history_refs',[]))
    if store.future.exists():
        # Explicit history refs in live tasks pin referenced evidence records.
        protected.update(re.findall(r'skill-tree/history/(?:audits|runs)/[a-zA-Z0-9-]+\.json',store.text()))
    latest_findings={}
    for path in sorted((store.base/'history/audits').glob('*.json'),key=lambda p:json.loads(p.read_text()).get('recorded_at','')):
        data=json.loads(path.read_text());scope=json.dumps(data.get('scope'),sort_keys=True)
        for f in data.get('findings',[]):latest_findings[(scope,f['id'])]=f.get('status','open')
    records=[];removals=[]
    for kind in ['audits','runs']:
        keep=config.get(kind,10)
        if type(keep) is not int or keep<1:raise WorkflowError('Retention count requires a positive integer')
        records=[]
        for path in (store.base/'history'/kind).glob('*.json'):
            data=json.loads(path.read_text());records.append((data.get('recorded_at',data.get('finished_at','')),path,data))
        records.sort(key=lambda item:item[0],reverse=True)
        for _,path,data in records[keep:]:
            rel=path.relative_to(store.root).as_posix()
            scope=json.dumps(data.get('scope'),sort_keys=True)
            unresolved=any(latest_findings.get((scope,f['id']),'open')=='open' for f in data.get('findings',[]))
            if rel not in protected and data.get('id') not in protected and not unresolved:removals.append(rel)
    if apply:
        with store.lock():
            # Re-evaluate under exclusive ownership.
            removals=prune(store,False)
            for rel in removals:store.owned(rel).unlink()
    return removals

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['refresh','manifest','index','read','select','pending','intake','process','start','next','advance','checkpoint','complete','finish','audit','prune','history','cycle']);parser.add_argument('root',type=Path);parser.add_argument('--id');parser.add_argument('--names',nargs='*');parser.add_argument('--input',type=Path);parser.add_argument('--mode',choices=['next','all'],default='next');parser.add_argument('--component');parser.add_argument('--apply',action='store_true');parser.add_argument('--expected-source-hash')
    args=parser.parse_args(argv)
    try:
        store=Store(args.root);payload=json.loads(args.input.read_text()) if args.input else {}
        if args.expected_source_hash:payload['expected_source_hash']=args.expected_source_hash
        cmd=args.command
        if cmd=='manifest':
            if args.apply:
                with store.lock():result=manifest(store);store.commit({'skill-tree/skill-tree.json':dump(result)})
            else:result=manifest(store)
        elif cmd=='refresh':
            with store.lock():text=store.text();result=store.load(text);store.save(text,result)
        elif cmd=='index':result=store.load()
        elif cmd=='read':result=resolve(parse(store.text()),[args.id])[0]
        elif cmd=='select':result=select(parse(store.text()),args.id)
        elif cmd=='pending':result=resolve(parse(store.text()),args.names or ([args.id] if args.id else []),'Pending Queue')
        elif cmd=='intake':result=intake(store,payload)
        elif cmd=='process':result=process(store,payload)
        elif cmd=='start':result=start(store,args.mode,args.id,payload.get('limits'))
        elif cmd=='next':result=next_task(store)
        elif cmd=='advance':result=advance(store)
        elif cmd=='checkpoint':result=checkpoint(store,payload)
        elif cmd=='complete':result=complete(store,payload)
        elif cmd=='finish':result=finish(store)
        elif cmd=='audit':result=audit(store,payload)
        elif cmd=='history':result=history(store,args.id,args.component)
        elif cmd=='cycle':result=record_cycle(store)
        else:result={'removed' if args.apply else 'candidates':prune(store,args.apply)}
        print(dump(result),end='');return 0
    except (WorkflowError,OSError,json.JSONDecodeError,KeyError,TypeError) as exc:
        print(dump({'ok':False,'error':str(exc)}),end='');return 2
if __name__=='__main__':
    raise SystemExit(main())
