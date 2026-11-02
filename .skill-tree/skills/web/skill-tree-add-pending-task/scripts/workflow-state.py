#!/usr/bin/env python3
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
SECTIONS = ['Goal', 'Touch', 'Validation', 'Acceptance']
OPTIONAL_FIELDS = ['validation_group_id','boundary_validation']
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
    if meta.get('validation_group_id') is not None and not valid_id(meta['validation_group_id'],'VG'):raise WorkflowError('Invalid validation group identity')
    if meta.get('boundary_validation','not-required') not in {'not-required','group-end','before-dependent-work'}:raise WorkflowError('Invalid boundary validation classification')
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
            if key in meta or key not in FIELDS+OPTIONAL_FIELDS:
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
            check_specs(task)
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

def validate_dependencies(tasks, completed_ids=()):
    """Validate the open dependency graph without changing task state."""
    open_tasks={t['id']:t for t in tasks if t['queue']=='Prioritized Next Changes'}
    completed=set(completed_ids);visiting=set();visited=set()
    def visit(task_id):
        if task_id in completed:return
        if task_id not in open_tasks:raise WorkflowError('Missing required dependency: '+task_id)
        if task_id in visiting:raise WorkflowError('Dependency cycle: '+task_id)
        if task_id in visited:return
        visiting.add(task_id)
        for dependency in open_tasks[task_id]['depends_on']:visit(dependency)
        visiting.remove(task_id);visited.add(task_id)
    for task_id in open_tasks:visit(task_id)

def render(title,meta,body):
    if not title.strip() or '\n' in title: raise WorkflowError('Task title requires one nonempty line')
    header='\n'.join(k+': '+(json.dumps(meta[k],ensure_ascii=False) if not isinstance(meta[k],str) else meta[k]) for k in FIELDS+[key for key in OPTIONAL_FIELDS if meta.get(key) is not None])
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
        self.root=Path(root).resolve();self.base=self.root/'.skill-tree';self.future=self.base/'documents/future.md';self.state=self.base/'documents/future.json'
        if not self.root.is_dir(): raise WorkflowError('Target repository does not exist')
        if self.base.is_symlink(): raise WorkflowError('Owned metadata directory cannot be a symlink')
    def owned(self,relative):
        path=self.root/relative
        if not relative.startswith('.skill-tree/') or not path.resolve().is_relative_to(self.base.resolve()) or self.base.is_symlink():
            raise WorkflowError('Metadata path outside owned directory: '+relative)
        return path
    @contextmanager
    def lock(self):
        self.base.mkdir(exist_ok=True)
        if (self.base/'installation/.install-lock').exists():raise WorkflowError('Installation lock exists; implementation waits for the owned profile transaction')
        path=self.base/'.writer-lock'
        try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise WorkflowError('Writer lock exists; verify owner PID/host before explicit lock removal') from exc
        try:
            os.write(fd,dump({'pid':os.getpid(),'host':socket.gethostname()}).encode());os.close(fd)
            if (self.base/'installation/.install-lock').exists():raise WorkflowError('Installation lock exists; preserve the profile handoff')
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
        self.owned('.skill-tree/documents/future.md')
        if not self.future.is_file(): raise WorkflowError('Missing .skill-tree/documents/future.md; run explicit documentation setup')
        return self.future.read_text()
    def load(self,text=None):
        text=self.text() if text is None else text
        value={'format':FORMAT,'source_hash':digest(text.encode()),'schema':2,'tasks':index(text),'active_run':None,'task_progress':{}}
        self.owned('.skill-tree/documents/future.json')
        if self.state.exists():
            old=json.loads(self.state.read_text())
            if old.get('format')!=FORMAT or old.get('schema')!=2 or not isinstance(old.get('tasks'),list) or 'active_run' not in old: raise WorkflowError('Unsupported checkpoint; reinstall and run explicit setup')
            run=old['active_run']
            if run is not None:
                validate_run(run)
            value['active_run']=run
            value['task_progress']=old.get('task_progress')
            validate_progress(value,parse(text),{record['task_id'] for record in self.outcomes() if record['disposition']=='completed'})
        return value
    def outcomes(self):
        path=self.base/'history/task-outcomes.jsonl'
        if not path.exists(): return []
        try: return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except json.JSONDecodeError as exc: raise WorkflowError('Corrupt task outcome ledger') from exc
    def save(self,text,state,extras=None):
        state['source_hash']=digest(text.encode());state['tasks']=index(text)
        writes=dict(extras or {})
        if text!=self.text(): writes['.skill-tree/documents/future.md']=text
        writes['.skill-tree/documents/future.json']=dump(state)
        self.commit(writes)
        self.commit({'.skill-tree/skill-tree.json':dump(manifest(self))})
    def guard(self,expected):
        if expected and file_hash(self.future)!=expected: raise WorkflowError('Source changed since inspection; reread selected task')

def validate_run(run):
    required={'id','mode','snapshot','root_task_id','current_task_id','phase','required_ids','deferred_ids','pending_ids','processing_results','completed_ids','limits','next_action','stop_reason','admission','admitted_task_ids','admitted_groups'}
    if not isinstance(run,dict) or not required.issubset(run) or not valid_id(run.get('id'),'WR') or run.get('mode') not in {'next','all'}:
        raise WorkflowError('Corrupt active checkpoint')
    if not isinstance(run['admission'],dict) or not isinstance(run['admitted_groups'],dict):raise WorkflowError('Corrupt profile admission/group scope')
    if any(not valid_id(group,'VG') or not isinstance(members,list) or any(not valid_id(tid,'T') or tid not in run['admitted_task_ids'] for tid in members) for group,members in run['admitted_groups'].items()):raise WorkflowError('Corrupt admitted group members')
    for key in ['snapshot','required_ids','deferred_ids','completed_ids','admitted_task_ids']:
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

def capture_foundation(store):
    profile=store.base/'installation/profile.json'
    if not profile.is_file():return {'status':'no-profile'}
    value=json.loads(profile.read_text());gap=next((g for g in value.get('gaps',[]) if g.get('key')=='test-foundation'),None)
    if not gap:return {'status':'no-gap'}
    if not store.future.is_file():return {'status':'deferred-until-documentation-setup','gap':gap}
    title='Configure foundational tests for the covered project'
    existing=next((t for t in parse(store.text()) if normalized(t['title'])==normalized(title)),None)
    if existing:return {'status':'reused','task_id':existing['id'],'queue':existing['queue']}
    completed=next((o for o in reversed(store.outcomes()) if o.get('title')==title),None)
    if completed:return {'status':'review-existing-outcome','task_id':completed['task_id'],'gap':gap}
    tasks=parse(store.text())
    result=intake(store,{'title':title,'description':gap['reason'],'expected_behavior':gap['recommendation'],'priority':max((t['priority'] for t in tasks),default=100)+1,'priority_reason':'Missing foundational validation requires researched setup before dependent acceptance.'})
    return {'status':'captured','pending_id':result['id'],'priority':result['priority']}

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
        specs=payload.get('tasks',[])
        if not isinstance(specs,list) or any(not isinstance(spec,dict) for spec in specs):raise WorkflowError('Processing tasks require a list of objects')
        # Allocate every identity before resolving forward references; no writes occur until validation succeeds.
        assigned=[spec.get('reuse_id') or identity('T') for spec in specs];keys={}
        for spec,task_id in zip(specs,assigned):
            key=spec.get('key')
            if key is not None:
                if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',key):raise WorkflowError('Task key requires lowercase kebab-case')
                if key in keys:raise WorkflowError('Duplicate task key: '+key)
                keys[key]=task_id
        def dependencies(spec):
            values=spec.get('depends_on',[])
            if not isinstance(values,list):raise WorkflowError('Task dependencies require a list')
            result=[]
            for value in values:
                if isinstance(value,str) and value.startswith('@'):
                    if value[1:] not in keys:raise WorkflowError('Unknown task key: '+value)
                    value=keys[value[1:]]
                if not valid_id(value,'T'):raise WorkflowError('Dependency requires a T- ID or @task-key')
                if value in result:raise WorkflowError('Duplicate dependency: '+value)
                result.append(value)
            return result
        pr=identity('PR');produced=[];reused=[]; consumed=set();run=state['active_run']
        for spec,task_id in zip(specs,assigned):
            parents=spec.get('parent_pending_ids',[])
            if not parents or not set(parents).issubset(selected_ids): raise WorkflowError('Produced task requires selected Pending provenance')
            sources=[t for t in selected if t['id'] in parents]
            contexts={(t['root_task_id'],t['related_task_id'],t['relation']) for t in sources}
            if len(contexts)!=1: raise WorkflowError('Conflicting task roots/relationships require clarification before merge')
            root,parent,relation=next(iter(contexts));consumed.update(parents)
            if any(dispositions[p]['status']!='promoted' for p in parents): raise WorkflowError('Produced task conflicts with Pending disposition')
            if spec.get('reuse_id'):
                reused_task=resolve(parse(text),[spec['reuse_id']],'Prioritized Next Changes')[0]
                if (reused_task['root_task_id'],reused_task['related_task_id'],reused_task['relation'])!=(root or reused_task['id'],parent,relation): raise WorkflowError('Reused task relationship conflicts')
                merged=list(dict.fromkeys(reused_task['parent_pending_ids']+parents))
                deps=list(dict.fromkeys(reused_task['depends_on']+dependencies(spec)))
                text=rewrite_meta(text,reused_task['id'],{'parent_pending_ids':merged,'processing_run_id':pr,'depends_on':deps});reused.append(reused_task['id']); continue
            assert_prose(spec['title']+'\n'+spec['body'])
            priority=spec.get('priority',max(t['priority'] for t in sources))
            meta={'id':task_id,'priority':priority,'status':'Ready','parent_pending_ids':parents,'processing_run_id':pr,'root_task_id':root or task_id,'related_task_id':parent,'relation':relation,'depends_on':dependencies(spec)}
            meta.update({key:spec[key] for key in OPTIONAL_FIELDS if spec.get(key) is not None})
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
        completed={o['task_id'] for o in store.outcomes() if o.get('disposition')=='completed'}
        validate_dependencies(parse(text),completed)
        receipt={'id':pr,'selected_ids':[t['id'] for t in selected],'created_ids':produced,'reused_ids':reused,'task_keys':keys,'dispositions':dispositions}
        if run:
            run['processing_results'].append(receipt);run['phase']='dependencies';run['next_action']='Select required task'
            allowed=set(run['admitted_task_ids']);introduced=set();updated=parse(text)
            for tid in produced+reused:
                child=resolve(updated,[tid])[0]
                if child['relation'] in {'blocker','subtask'} and child['related_task_id'] in allowed:
                    introduced.update(dependency_scope(updated,{'snapshot':[tid]}))
            if dependency_scope(updated,run)-allowed-introduced:raise WorkflowError('Processing cannot admit a dependency outside the captured required scope')
            run['admitted_task_ids']=sorted(allowed|introduced);run['required_ids']=list(dict.fromkeys(run['required_ids']+sorted(introduced)));run['admitted_groups']=admitted_groups(updated,run)
        store.save(text,state)
        return receipt

def start(store,mode,selector=None,limits=None):
    admission=admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text)
        if state['active_run'] is not None: raise WorkflowError('Active run exists; resume the recorded run')
        tasks=parse(text);chosen=select(tasks,selector)
        snapshot=[chosen['id']] if mode=='next' else [t['id'] for t in sorted([t for t in tasks if t['queue']=='Prioritized Next Changes'],key=lambda t:-t['priority'])]
        if mode=='all' and selector:raise WorkflowError('Implement All uses the initial prioritized snapshot')
        run={'id':identity('WR'),'mode':mode,'snapshot':snapshot,'root_task_id':chosen['id'],'current_task_id':chosen['id'],'phase':'implement','required_ids':[chosen['id']],'deferred_ids':[],'pending_ids':[],'processing_results':[],'completed_ids':[],'limits':limits or {},'partial_work':[],'stop_reason':None,'next_action':'Implement selected task','started_at':now()}
        run['admission']=admission;run['admitted_task_ids']=sorted(dependency_scope(tasks,run));run['required_ids']=list(run['admitted_task_ids']);run['admitted_groups']=admitted_groups(tasks,run)
        validate_run(run);state['active_run']=run;store.save(text,state);return run

def enforce_limits(run):
    if run.get('stop_reason'):raise WorkflowError('Run stopped: '+str(run['stop_reason'])+'; resolve the recorded condition before explicit checkpoint resumption')
    budget=run['limits'].get('selected_task_budget')
    if budget is not None and budget['used_seconds']>=budget['limit_seconds']:raise WorkflowError('Selected-task budget exhausted')

def next_task(store):
    state=store.load();run=state['active_run']
    if not run:raise WorkflowError('No active run')
    enforce_limits(run);assert_admission(store,state);tasks=parse(store.text());by_id={t['id']:t for t in tasks};done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
    validate_dependencies(tasks,done)
    visiting=set();visited=set()
    def walk(tid):
        if tid in done:return []
        if tid in visiting:raise WorkflowError('Dependency cycle: '+tid)
        if tid not in by_id:raise WorkflowError('Missing task without completion evidence: '+tid)
        if tid not in scope_ids(tasks,run):raise WorkflowError('Required task was not admitted through the scoped intake/process flow: '+tid)
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
        if not remaining:
            stale=stale_completed_checks(store,state)
            if stale:
                task=validation_task(store,stale[0]['task_id']);return {'phase':'validate','task_id':task['id'],'root_task_id':root,'completed_contract':True,'body':task['body'],'checks':check_specs(task)}
            return {'phase':'deferred-processing','pending_ids':[t['id'] for t in tasks if t['queue']=='Pending Queue' and t['id'] in run['pending_ids'] and t['relation']=='followup']}
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
    run['admitted_groups']=admitted_groups(tasks,run)
    stage=state['task_progress'].get(task['id'],{}).get('stage')
    if stage=='blocked':raise WorkflowError('Selected task progress is blocked; resolve the recorded stop')
    if stage=='awaiting-validation':
        # Immediate checks and verified consumers force validation before another implementation.
        checks=check_specs(task)
        def due(check):
            try:validate_task_checks(store,task['id'],state,check['id']);return False
            except WorkflowError:return True
        early=any(check['timing']!='group-end' and due(check) for check in checks)
        consumers=any(task['id'] in candidate['depends_on'] for candidate in tasks if candidate['id'] in scope_ids(tasks,run))
        group=task.get('validation_group_id')
        if group and not early and not consumers:
            eligible=[candidate for candidate in tasks if candidate['id'] in scope_ids(tasks,run) and candidate.get('validation_group_id')==group and candidate['queue']=='Prioritized Next Changes' and candidate['status']=='Ready' and state['task_progress'].get(candidate['id'],{}).get('stage') not in {'awaiting-validation','blocked'} and all(dep in done for dep in candidate['depends_on'])]
            if eligible:task=max(eligible,key=lambda candidate:candidate['priority']);stage=state['task_progress'].get(task['id'],{}).get('stage')
    return {'phase':'validate' if stage=='awaiting-validation' else 'implement','root_task_id':root,'task_id':task['id'],'title':task['title'],'priority':task['priority'],'body':task['body'],'checks':check_specs(task)}

def advance(store):
    with store.lock():
        result=next_task(store);text=store.text();state=store.load(text);run=state['active_run']
        run['admitted_groups']=admitted_groups(parse(text),run)
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
        assert_scope(store,state,tasks,task['id'])
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
            expected=acceptance_criteria(task)
            criteria=[c['criterion'] for c in checks]
            if not expected or len(criteria)!=len(set(criteria)) or set(criteria)!=set(expected):raise WorkflowError('Acceptance results must cover exactly the recorded task criteria')
            for check in checks:
                if not isinstance(check['evidence'],list):raise WorkflowError('Acceptance evidence requires repository-relative file references')
                check['evidence']=[evidence_pointer(store,ref,required=True) for ref in check['evidence']]
        validation_records=validate_task_checks(store,task['id'],state) if disposition=='completed' else []
        if disposition=='completed':
            for accepted in payload['acceptance']:
                required_refs={ref['path'] for item in validation_records if accepted['criterion'] in item['check']['criteria'] for ref in item['result']['evidence']}
                if not required_refs.issubset({ref['path'] for ref in accepted['evidence']}):raise WorkflowError('Acceptance evidence does not match the required check receipts')
        record={'validation_group_id':task.get('validation_group_id'),'boundary_validation':task.get('boundary_validation','not-required'),'validation_plan':check_specs(task),'validation_signature':task_signature(task),'check_results':validation_records,'depends_on':task['depends_on'],'id':identity('O'),'task_id':task['id'],'title':task['title'],'root_task_id':task['root_task_id'],'related_task_id':task['related_task_id'],'parent_pending_ids':task['parent_pending_ids'],'disposition':disposition,'outcome':payload['outcome'],'acceptance':payload.get('acceptance',[]),'limitations':payload.get('limitations',[]),'followup_ids':payload.get('followup_ids',[]),'source_fingerprints':payload.get('source_fingerprints',{}),'commits':payload.get('commits',[]),'evidence':[evidence_pointer(store,e) for e in payload.get('evidence',[])],'recorded_at':now()}
        ledger=''.join(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n' for o in outcomes+[record])
        if state['active_run']:
            run=state['active_run'];run.setdefault('completion_refs',{})[task['id']]=record['id'];run['completed_ids'].append(task['id']) if disposition=='completed' else None
            run['current_task_id']=None;run['phase']='resume-parent';run['next_action']='Select required task or finish root'
        state['task_progress'].pop(task['id'],None)
        text=remove(text,{task['id']});store.save(text,state,{'.skill-tree/history/task-outcomes.jsonl':ledger});return record

def finish(store):
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        enforce_limits(run)
        done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
        required=set(run['snapshot']+run['required_ids'])
        if not required.issubset(done):raise WorkflowError('Main tasks or required descendants remain incomplete')
        if any(t['id'] in run['pending_ids'] and t['relation'] in {'blocker','subtask'} for t in parse(text)):raise WorkflowError('Required Pending tasks remain')
        followups=[t for t in parse(text) if t['id'] in run['pending_ids'] and t['relation']=='followup']
        if any(t['id'] not in {p for r in run['processing_results'] for p in r['selected_ids']} for t in followups):raise WorkflowError('Nonblocking findings require one processing pass before finish')
        assert_admission(store,state)
        stale=stale_completed_checks(store,state)
        if stale:raise WorkflowError('Required completed check evidence is stale or unavailable: '+stale[0]['task_id']+'/'+stale[0]['check_id']+'; advance selects the preserved contract for revalidation')
        summary=deepcopy(run);summary['finished_at']=now();summary['phase']='completed';summary['next_action']=None
        state['active_run']=None;store.save(text,state,{'.skill-tree/history/runs/run-'+run['id'].lower()+'.json':dump(summary)})
    prune(store,True);return summary

def record_cycle(store):
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        semantic_fields=['id','queue','priority','status','parent_pending_ids','root_task_id','related_task_id','relation','depends_on']
        task_state=[{key:task[key] for key in semantic_fields} for task in state['tasks']]
        signature=digest(dump({'tasks':task_state,'outcomes':[o['task_id'] for o in store.outcomes()],'revalidated':{tid:[entry['result']['key'] for entry in checks] for tid,checks in run.get('revalidated_checks',{}).items()},'progress':{tid:{'stage':entry['stage'],'diagnostics':{cid:slot.get('result',{}).get('diagnostic_key') for cid,slot in entry['checks'].items() if slot.get('result',{}).get('diagnostic_key')},'checks':{cid:slot.get('result',{}).get('key') if slot.get('result',{}).get('result')=='pass' else None for cid,slot in entry['checks'].items() if slot.get('result',{}).get('result')=='pass'}} for tid,entry in state['task_progress'].items()}}).encode())
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
        store.commit({'.skill-tree/history/audits/audit-'+record['id'].lower()+'.json':dump(record)})
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
        for item in view.get('check_results',[]):
            for key in ['result','red']:
                if key in item:
                    proof=item[key];proof['evidence']=[evidence_pointer(store,ref) for ref in proof.get('evidence',[])]
                    proof['source_fingerprints_match']=fingerprints(store,list(proof.get('sources',{})))==proof.get('sources',{})
        result.append(view)
    return result

def installed_catalog(root):
    """Discover repository-local Skill Tree packages without an upstream checkout."""
    entrypoints=set()
    for pattern in ['skill-tree-*/SKILL.md','.*/skills/skill-tree-*/SKILL.md','.*/agent/skills/skill-tree-*/SKILL.md','skills/skill-tree-*/SKILL.md']:
        entrypoints.update(root.glob(pattern))
    return [{'name':p.parent.name,'entrypoint':p.relative_to(root).as_posix(),'resources':[r.relative_to(root).as_posix() for r in sorted(p.parent.rglob('*')) if r.is_file() and '__pycache__' not in r.parts]} for p in sorted(entrypoints) if p.is_file()]

def manifest(store):
    path=store.base/'skill-tree.json';existing=json.loads(path.read_text()) if path.exists() else {}
    role='source' if (store.base/'config/repository.json').is_file() and json.loads((store.base/'config/repository.json').read_text()).get('role')=='source' else 'target';files=[]
    for p in sorted((store.base/'documents').glob('*')):
        if p.is_file():files.append({'path':p.relative_to(store.root).as_posix(),'role':'generated-index-and-active-state' if p.name=='future.json' else 'canonical','owner':'skill-tree'})
    catalog=installed_catalog(store.root) if role=='target' else []
    if role=='source':
        canonical=[p for directory in ['common','scripts','lib','templates','domains','config','bin','src'] for p in sorted((store.base/directory).rglob('*'))]
        for p in canonical:
            if p.is_file() and '__pycache__' not in p.parts:files.append({'path':p.relative_to(store.root).as_posix(),'role':'canonical','owner':'skill-tree'})
        for p in sorted((store.base/'skills').glob('*/*/SKILL.md')):
            catalog.append({'name':p.parent.name,'entrypoint':p.relative_to(store.root).as_posix(),'resources':[r.relative_to(store.root).as_posix() for r in sorted(p.parent.rglob('*')) if r.is_file() and '__pycache__' not in r.parts]})
    audits=[]
    for p in (store.base/'history/audits').glob('*.json'):
        record=json.loads(p.read_text());old=record['source_fingerprints'];fresh=fingerprints(store,list(old))==old
        audits.append({'id':record['id'],'path':p.relative_to(store.root).as_posix(),'recorded_at':record['recorded_at'],'scope':record['scope'],'fresh':fresh})
    audits.sort(key=lambda r:r['recorded_at'])
    result={'format':'skill-tree-manifest','role':role,'files':files,'queue':store.future.relative_to(store.root).as_posix() if store.future.exists() else None,'state':store.state.relative_to(store.root).as_posix() if store.state.exists() else None,'catalog':catalog,'history':{'task_outcomes':'.skill-tree/history/task-outcomes.jsonl','audits':'.skill-tree/history/audits','runs':'.skill-tree/history/runs'},'latest_audit':audits[-1] if audits else None,'audit_scopes':audits,'retention':existing.get('retention',{'audits':10,'runs':10,'pins':[]}),'policy_references':existing.get('policy_references',[rel for rel in ['AGENTS.md','.skill-tree/documents/rules.md'] if (store.root/rel).is_file()]),'validation_commands':existing.get('validation_commands',['npm run sync:check','npm run validate','npm run test:py','npm run test:node','git diff --check'] if role=='source' else [])}
    if role=='source':
        result['canonical_resources']={'references':'.skill-tree/common/references','scripts':'.skill-tree/common/scripts','resource_map':'.skill-tree/config/resource-map.json','provider_matrix':'.skill-tree/config/providers.json','generator':'.skill-tree/scripts/sync-skill-references.py'}
    result['source_digests']={f['path']:file_hash(store.root/f['path']) for f in files if f['role']=='canonical'}
    return result

def prune(store,apply=False):
    config=manifest(store)['retention'];pinned=set(config.get('pins',[]));protected=set(pinned)
    if store.state.exists():
        run=store.load()['active_run']
        if run: protected.update(run.get('history_refs',[]))
    if store.future.exists():
        # Explicit history refs in live tasks pin referenced evidence records.
        protected.update(re.findall(r'.skill-tree/history/(?:audits|runs)/[a-zA-Z0-9-]+\.json',store.text()))
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

def section_body(body,name):
    match=re.search(r'(?m)^'+re.escape(name)+r':\s*\n',body)
    if not match:return ''
    tail=body[match.end():];end=re.search(r'(?m)^[A-Z][A-Za-z /-]+:\s*$',tail)
    return tail[:end.start()] if end else tail

def acceptance_criteria(task):
    return [line[2:].strip() for line in section_body(task['body'],'Acceptance').splitlines() if line.startswith('- ')]

def check_specs(task):
    text=section_body(task['body'],'Validation');match=re.search(r'```json\n(.*?)\n```',text,re.S)
    if not match:raise WorkflowError('Validation requires a structured JSON checks object')
    try:plan=json.loads(match[1])
    except ValueError as exc:raise WorkflowError('Invalid validation check JSON') from exc
    checks=plan.get('checks')
    if not isinstance(checks,list) or not checks:raise WorkflowError('Validation requires nonempty checks')
    criteria=acceptance_criteria(task);covered=set();seen=set()
    if not criteria or len(criteria)!=len(set(criteria)):raise WorkflowError('Acceptance requires unique observable criteria')
    for check in checks:
        if not isinstance(check,dict):raise WorkflowError('Invalid validation check')
        for key in ['id','recipe_id']:
            if not isinstance(check.get(key),str) or not re.fullmatch(r'[a-z][a-z0-9-]*',check[key]):raise WorkflowError('Check requires stable '+key)
        if check['id'] in seen:raise WorkflowError('Duplicate check identity')
        seen.add(check['id'])
        if not isinstance(check.get('criteria'),list) or not check['criteria'] or not set(check['criteria']).issubset(criteria):raise WorkflowError('Check criterion mapping does not match acceptance')
        covered.update(check['criteria'])
        if not isinstance(check.get('sources'),list) or not check['sources'] or len(set(check['sources']))!=len(check['sources']):raise WorkflowError('Check requires explicit relevant source/test paths')
        for rel in check['sources']:
            if not isinstance(rel,str) or Path(rel).is_absolute() or '..' in Path(rel).parts or '\\' in rel:raise WorkflowError('Check source requires a repository-relative path')
        if not isinstance(check.get('parameters'),dict) or not isinstance(check.get('assertion'),str) or not check['assertion'].strip():raise WorkflowError('Check requires parameters and a concrete assertion')
        if check.get('timing') not in {'immediate','group-end','before-dependent-work'}:raise WorkflowError('Check requires immediate or explicit boundary timing')
        if check['timing']!='immediate' and task.get('boundary_validation','not-required')=='not-required':raise WorkflowError('Boundary check requires task boundary classification')
    if covered!=set(criteria):raise WorkflowError('Every acceptance criterion requires a mapped check')
    return checks

def validate_progress(state,tasks,completed=()):
    progress=state.get('task_progress')
    if not isinstance(progress,dict):raise WorkflowError('Unsupported task progress schema; use the manual update checklist')
    open_ids={t['id'] for t in tasks if t['queue']=='Prioritized Next Changes'}
    for tid,entry in progress.items():
        revalidating=isinstance(entry,dict) and entry.get('revalidation') is True and tid in completed and state['active_run'] and tid in state['active_run']['required_ids']
        if (tid not in open_ids and not revalidating) or not isinstance(entry,dict) or entry.get('stage') not in {'implementing','awaiting-validation','blocked'} or not isinstance(entry.get('checks'),dict):raise WorkflowError('Corrupt task progress: '+tid)

def admit_profile(store):
    path=store.base/'installation/profile.json'
    if not path.is_file():
        source=store.base/'config/repository.json'
        if source.is_file() and json.loads(source.read_text()).get('role')=='source':return {'identity':'repository-local','flavor':'general'}
        raise WorkflowError('Missing installation profile; install a project-scoped flavor before implementation')
    manager=store.base/'installation/manager.js'
    if not manager.is_file():raise WorkflowError('Missing local profile manager; repair the owned installation')
    import subprocess
    try:result=subprocess.run(['node',str(manager),'--verify'],capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as exc:raise WorkflowError('Profile admission failed within 30 seconds; cleanup reserve 5 seconds') from exc
    if result.returncode:raise WorkflowError((result.stderr or result.stdout).strip())
    value=json.loads(path.read_text())
    return {'identity':value['identity'],'environment_id':value['environment_id'],'flavor':value['flavor'],'project_root':value['project_root']}

def resume_admission(store):
    admitted=admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        run['admission']=admitted
        if run.pop('profile_refresh_required',False) and run['stop_reason']=='Installation profile changed; re-admit before continuation':run['stop_reason']=None
        store.save(text,state);return admitted

def dependency_scope(tasks,run):
    by_id={t['id']:t for t in tasks};result=set()
    def visit(tid):
        if tid in result:return
        result.add(tid)
        for dep in by_id.get(tid,{}).get('depends_on',[]):visit(dep)
    for tid in run['snapshot']:visit(tid)
    return result

def scope_ids(tasks,run):
    return dependency_scope(tasks,run) & set(run.get('admitted_task_ids',[]))

def admitted_groups(tasks,run):
    scope=scope_ids(tasks,run);groups=deepcopy(run.get('admitted_groups',{}))
    for task in tasks:
        group=task.get('validation_group_id')
        if task['id'] in scope and group and task['id'] not in groups.setdefault(group,[]):groups[group].append(task['id'])
    return groups

def task_signature(task):
    return digest(dump({'checks':check_specs(task),'criteria':acceptance_criteria(task),'group':task.get('validation_group_id'),'boundary':task.get('boundary_validation','not-required')}).encode())

def recipe_for(store,check):
    profile_path=store.base/'installation/profile.json'
    profile=json.loads(profile_path.read_text()) if profile_path.exists() else {}
    local_path=store.base/'config/repository.json'
    local=json.loads(local_path.read_text()) if local_path.exists() else {}
    recipes=profile.get('recipes',local.get('recipes',{}))
    recipe=recipes.get(check['recipe_id'])
    if recipe is None and check['recipe_id']=='static-inspection':recipe={'lane':'static','input_paths':[],'assertion_contract':'explicit source and artifact assertions'}
    if recipe is None:raise WorkflowError('Validation-blocked: recipe unavailable: '+check['recipe_id']+'; review the required plan after profile refresh')
    inputs={}
    for rel in recipe.get('input_paths',[]):inputs.update(fingerprints(store,[rel]))
    if profile and any(profile.get('inputs',{}).get(rel)!=value for rel,value in inputs.items()):raise WorkflowError('Profile refresh-required: node .skill-tree/installation/manager.js --refresh-profile')
    recipe=deepcopy(recipe)
    arguments=[];parameters={**check['parameters'],'project_root':str(store.root)}
    for argument in recipe.get('argv',[]):
        def parameter(match):
            key=match[1]
            if key not in parameters or not isinstance(parameters[key],str) or not parameters[key]:raise WorkflowError('Recipe parameters are unresolved: '+key)
            return parameters[key]
        arguments.append(re.sub(r'\{([a-z][a-z0-9_]*)\}',parameter,argument))
    if 'argv' in recipe:recipe['argv']=arguments
    environment=digest(dump({'recipe':recipe,'inputs':inputs}).encode())
    return recipe,environment

def group_fingerprint(store,task,state):
    group=task.get('validation_group_id')
    if not group:return None
    tasks=parse(store.text());by_id={t['id']:t for t in tasks};run=state['active_run'];done={o['task_id']:o for o in store.outcomes()}
    members=(run.get('admitted_groups',{}).get(group,[]) if run else [task['id']])
    if task['id'] not in members:raise WorkflowError('Task is outside the frozen validation group scope')
    definitions={tid:task_signature(by_id[tid]) if tid in by_id else done.get(tid,{}).get('validation_signature') for tid in members}
    if any(value is None for value in definitions.values()):raise WorkflowError('Group prerequisite lacks a preserved validation contract')
    return digest(dump(definitions).encode())

PRODUCT_LANES={'browser','server','unity-editmode','unity-playmode','visual','player','device','native'}

def execution_session(store,recipe,environment,entry,provided=None,require_current=False):
    sessions=entry.setdefault('execution_sessions',{})
    session=provided or sessions.get(environment)
    if recipe['lane'] not in PRODUCT_LANES:return None
    fields=['project_root','authorization','profile_id','deadline_utc','cleanup_seconds','tool_identity','session_identity','fixture_identity','build_identity','identity_evidence']
    if not isinstance(session,dict) or any(not session.get(key) for key in fields):raise WorkflowError('Product checks require an owned execution session with authorization, identity evidence, deadline and cleanup reserve')
    if Path(session['project_root']).resolve()!=store.root:raise WorkflowError('Execution session checkout differs from the covered root')
    if type(session['cleanup_seconds']) not in {int,float} or session['cleanup_seconds']<=0:raise WorkflowError('Execution cleanup reserve must be positive')
    try:deadline=datetime.fromisoformat(session['deadline_utc'].replace('Z','+00:00'))
    except (ValueError,TypeError) as exc:raise WorkflowError('Execution deadline requires an aware timestamp') from exc
    if deadline.tzinfo is None or require_current and (deadline-datetime.now(timezone.utc)).total_seconds()<=session['cleanup_seconds']:raise WorkflowError('Execution deadline lacks a cleanup reserve')
    if recipe['lane'].startswith('unity-'):
        if session.get('editor_version')!=recipe.get('editor_version') or not session.get('save_service_isolation'):raise WorkflowError('Unity session requires the pinned Editor and verified save/service isolation')
    if not isinstance(session['identity_evidence'],list):raise WorkflowError('Execution identity requires repository-relative evidence')
    for ref in session['identity_evidence']:evidence_pointer(store,ref,required=True)
    sessions[environment]=deepcopy(session)
    return session

def check_snapshot(store,task,check,state):
    sources=fingerprints(store,check['sources'])
    if any(value is None for value in sources.values()):raise WorkflowError('Required check source/test input is unavailable')
    recipe,environment=recipe_for(store,check)
    if recipe['lane'] in {'unit','unity-editmode'} and check['timing']!='immediate':raise WorkflowError('Focused behavioral checks remain immediate')
    entry=state['task_progress'].get(task['id'],{});session=execution_session(store,recipe,environment,entry)
    if session:
        identity={key:session[key] for key in ['tool_identity','fixture_identity','build_identity','save_service_isolation','editor_version'] if key in session}
        identity['evidence']=[evidence_pointer(store,ref,required=True) for ref in session['identity_evidence']]
        environment=digest(dump({'recipe_environment':environment,'execution':identity}).encode())
    executable={key:check[key] for key in ['recipe_id','sources','parameters','assertion']}
    key=digest(dump({'check':executable,'recipe':recipe,'sources':sources,'environment':environment,'group':group_fingerprint(store,task,state)}).encode())
    return {'key':key,'definition':task_signature(task),'sources':sources,'environment_identity':environment,'recipe':recipe}

def validation_task(store,tid):
    matches=[task for task in parse(store.text()) if task['id']==tid and task['queue']=='Prioritized Next Changes']
    if matches:return matches[0]
    record=next((item for item in store.outcomes() if item['task_id']==tid and item['disposition']=='completed'),None)
    if not record:raise WorkflowError('Missing task without a completed validation contract: '+tid)
    if not record.get('validation_plan') or not record.get('validation_signature'):raise WorkflowError('Completed record lacks an immutable validation contract; manual review is required')
    criteria=[entry['criterion'] for entry in record['acceptance']]
    body='Goal:\n- Revalidate the recorded completed contract.\n\nTouch:\n- Recorded relevant source and test inputs.\n\nValidation:\n```json\n'+dump({'checks':record['validation_plan']})+'```\n\nAcceptance:\n'+'\n'.join('- '+criterion for criterion in criteria)+'\n'
    task={'id':tid,'body':body,'title':record['title'],'validation_group_id':record.get('validation_group_id'),'boundary_validation':record.get('boundary_validation','not-required'),'completed_contract':True}
    if task_signature(task)!=record['validation_signature']:raise WorkflowError('Completed validation contract does not match the recorded signature')
    return task

def stale_completed_checks(store,state):
    run=state['active_run'];outcomes={record['task_id']:record for record in store.outcomes() if record['disposition']=='completed'};stale=[]
    for tid in dict.fromkeys(run['snapshot']+run['required_ids']):
        if tid not in outcomes:continue
        record=outcomes[tid];task=validation_task(store,tid)
        if state['task_progress'].get(tid,{}).get('revalidation'):
            stale.extend({'task_id':tid,'check_id':check['id']} for check in check_specs(task));continue
        results=run.get('revalidated_checks',{}).get(tid,record.get('check_results',[]))
        by_check={entry['check']['id']:entry['result'] for entry in results}
        for check in check_specs(task):
            result=by_check.get(check['id'])
            try:
                if not result or result.get('result')!='pass':raise WorkflowError('Missing passed result')
                context=deepcopy(state);context['task_progress'][tid]={'stage':'awaiting-validation','checks':{},'execution_sessions':result.get('execution_sessions',{})}
                snapshot=check_snapshot(store,task,check,context)
                if result['key']!=snapshot['key'] or result['definition']!=snapshot['definition']:raise WorkflowError('Changed relevant inputs')
                for ref in result['evidence']:evidence_pointer(store,ref,required=True)
            except (WorkflowError,KeyError):stale.append({'task_id':tid,'check_id':check['id']})
    return stale

def accept_revalidation(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task=validation_task(store,payload['task_id'])
        if not task.get('completed_contract') or not state['task_progress'].get(task['id'],{}).get('revalidation'):raise WorkflowError('No completed-contract revalidation is prepared')
        assert_scope(store,state,parse(text),task['id'])
        results=validate_task_checks(store,task['id'],state)
        state['active_run'].setdefault('revalidated_checks',{})[task['id']]=results
        state['task_progress'].pop(task['id']);state['active_run']['next_action']='Select remaining due checks or finish the preserved run'
        store.save(text,state);return {'task_id':task['id'],'phase':'revalidated','checks':[entry['check']['id'] for entry in results]}

def get_check(store,state,payload):
    task=validation_task(store,payload['task_id'])
    allowed=state['active_run'] and task.get('completed_contract') and task['id'] in state['active_run']['admitted_task_ids'] and task['id'] in state['active_run']['required_ids']
    if task.get('completed_contract') and not allowed:raise WorkflowError('Completed validation contract is outside the active scope')
    if state['active_run'] and task['id'] not in scope_ids(parse(store.text()),state['active_run']) and not allowed:raise WorkflowError('Task is outside the admitted controller scope')
    matches=[check for check in check_specs(task) if check['id']==payload['check_id']]
    if len(matches)!=1:raise WorkflowError('Absent check identity')
    return task,matches[0]

def assert_admission(store,state,tid=None):
    profile_path=store.base/'installation/profile.json'
    if not profile_path.is_file():return
    profile=json.loads(profile_path.read_text());run=state['active_run']
    admitted=run.get('admission') if run else state['task_progress'].get(tid,{}).get('admission')
    if not admitted or admitted.get('identity')!=profile.get('identity'):raise WorkflowError('Profile admission changed; explicitly re-admit the current profile before continuation')

def assert_scope(store,state,tasks,tid):
    run=state['active_run']
    if run:
        enforce_limits(run)
        if tid not in scope_ids(tasks,run) and not (state['task_progress'].get(tid,{}).get('revalidation') and tid in run['admitted_task_ids'] and tid in run['required_ids']):raise WorkflowError('Task is outside the admitted controller scope')
    assert_admission(store,state,tid)

def begin_task(store,payload):
    # Standalone admission occurs once at the implementation boundary; controller leaves reuse the admitted profile.
    state=store.load();admission=state['active_run'].get('admission') if state['active_run'] else admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);task=resolve(parse(text),[payload['task_id']],'Prioritized Next Changes')[0]
        if task['status']!='Ready':raise WorkflowError('Selected task has blocking questions')
        done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
        if any(dep not in done for dep in task['depends_on']):raise WorkflowError('Verified dependencies remain incomplete')
        if state['active_run']:assert_scope(store,state,parse(text),task['id'])
        entry=state['task_progress'].setdefault(task['id'],{'stage':'implementing','checks':{},'admission':admission,'partial_work':[]})
        if entry['stage']=='blocked':raise WorkflowError('Task progress is blocked; explicitly resolve the recorded stop')
        entry['admission']=admission
        result={'task_id':task['id'],'phase':'validate' if entry['stage']=='awaiting-validation' else 'implement','checks':check_specs(task)}
        store.save(text,state);return result

def mark_implemented(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task=resolve(parse(text),[payload['task_id']],'Prioritized Next Changes')[0]
        entry=state['task_progress'].get(task['id'])
        if not entry or entry['stage']=='blocked':raise WorkflowError('Begin or resume implementation before marking the unit implemented')
        assert_scope(store,state,parse(text),task['id'])
        entry['stage']='awaiting-validation';entry['definition']=task_signature(task);entry['partial_work']=payload.get('changed_files',[])
        store.save(text,state);return {'task_id':task['id'],'phase':'validate','checks':check_specs(task)}

def prepare_check(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task,check=get_check(store,state,payload);entry=state['task_progress'].get(task['id'])
        if task.get('completed_contract') and not entry:entry=state['task_progress'].setdefault(task['id'],{'stage':'awaiting-validation','checks':{},'revalidation':True,'admission':state['active_run']['admission']})
        if not entry or entry['stage']=='blocked':raise WorkflowError('Begin implementation before check preparation')
        assert_scope(store,state,parse(text),task['id'])
        slot=entry['checks'].get(check['id'],{});previous=slot.get('attempt')
        if previous and not any(record.get('attempt_id')==previous['attempt_id'] for record in [slot.get('result',{}),slot.get('red',{}),*slot.get('receipts',{}).values()]):raise WorkflowError('Recover and close the original pending check attempt before preparing another control')
        if state['active_run']:
            enforce_limits(state['active_run']);state['active_run']['admitted_groups']=admitted_groups(parse(text),state['active_run'])
        recipe,environment=recipe_for(store,check);execution_session(store,recipe,environment,entry,payload.get('execution'),require_current=True)
        snapshot=check_snapshot(store,task,check,state)
        launch=payload.get('launch')
        if launch:
            required=['assertion','cheaper_evidence_insufficient','authorization','deadline_utc','cleanup_seconds','project_root','execution_profile']
            if not isinstance(launch,dict) or any(not launch.get(key) for key in required):raise WorkflowError('Launch requires concrete assertion, rationale, authorization, exact checkout, deadline and cleanup profile')
            if type(launch['cleanup_seconds']) not in {int,float} or launch['cleanup_seconds']<=0:raise WorkflowError('Launch cleanup reserve must be positive')
            if launch['cheaper_evidence_insufficient'].strip().casefold() in {'run everything to be safe','to be safe','routine checklist'}:raise WorkflowError('Launch requires an assertion-specific rationale')
            if Path(launch['project_root']).resolve()!=store.root:raise WorkflowError('Launch checkout differs from the covered root')
            try:deadline=datetime.fromisoformat(launch['deadline_utc'].replace('Z','+00:00'))
            except (ValueError,TypeError) as exc:raise WorkflowError('Launch deadline requires an aware civil timestamp') from exc
            if deadline.tzinfo is None or (deadline-datetime.now(timezone.utc)).total_seconds()<=launch['cleanup_seconds']:raise WorkflowError('Launch deadline lacks a cleanup reserve')
        attempt={**snapshot,'attempt_id':identity('C'),'launch':launch,'prepared_at':now()}
        entry['checks'].setdefault(check['id'],{})['attempt']=attempt
        store.save(text,state);return {**attempt,'task_id':task['id'],'check_id':check['id'],'assertion':check['assertion']}

def record_check(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task,check=get_check(store,state,payload);entry=state['task_progress'].get(task['id'],{});slot=entry.get('checks',{}).get(check['id'],{});attempt=slot.get('attempt')
        delivered=slot.get('receipts',{}).get(payload.get('attempt_id'))
        if delivered:
            if delivered.get('payload_hash')!=digest(dump(payload).encode()):raise WorkflowError('Conflicting replay of the original check receipt')
            return deepcopy(delivered)
        if not attempt or attempt['attempt_id']!=payload.get('attempt_id'):raise WorkflowError('Recover the original prepared check attempt; never invent a receipt')
        current=check_snapshot(store,task,check,state)
        if current['key']!=attempt['key'] or current['definition']!=attempt['definition']:raise WorkflowError('Prepared check is stale; source/test/check-set changed')
        classification=payload.get('classification')
        if classification not in {'executed-control','prerequisite-wait','transport-uncertainty','host-policy-rejection'}:raise WorkflowError('Check requires an operation classification')
        result=payload.get('result')
        if result not in {'pass','fail','red','unavailable'}:raise WorkflowError('Unsupported check result')
        if result in {'pass','red'} and classification!='executed-control':raise WorkflowError('Only an executed control can establish evidence')
        if payload.get('actual_lane')!=attempt['recipe']['lane'] or payload.get('environment_identity')!=attempt['environment_identity']:raise WorkflowError('Runner lane/environment does not match the prepared check')
        if not isinstance(payload.get('cleanup'),str) or not payload['cleanup'].strip():raise WorkflowError('Record actual operation cleanup')
        refs=payload.get('evidence',[])
        if result in {'pass','red'} and not refs:raise WorkflowError('Executed evidence requires result artifacts')
        evidence=[evidence_pointer(store,ref,required=True) for ref in refs]
        lane=attempt['recipe']['lane']
        if result in {'pass','red'}:
            if lane in {'unit','integration','browser','unity-editmode','unity-playmode'}:
                counts=payload.get('counts',{})
                if any(type(counts.get(key)) is not int or counts[key]<0 for key in ['expected','discovered','passed','failed','skipped']):raise WorkflowError('Test runner requires actual nonnegative counts')
                if counts['expected']<1 or counts['discovered']<counts['expected'] or counts['passed']+counts['failed']+counts['skipped']!=counts['discovered']:raise WorkflowError('Expected nonzero test discovery is missing')
                if result=='pass' and (counts['failed'] or counts['skipped']):raise WorkflowError('Failed or skipped required tests cannot pass')
                if result=='red' and (not counts['failed'] or counts['skipped'] or payload.get('failure_category')!='expected-behavior'):raise WorkflowError('Red requires the intended runnable behavioral failure')
            else:
                assertions=payload.get('assertions',[])
                if not assertions or not any(a.get('assertion')==check['assertion'] for a in assertions) or any(a.get('result')!='pass' for a in assertions):raise WorkflowError('Static/visual checks require actual matching assertions')
                if result=='red':raise WorkflowError('Static/visual observations cannot establish behavioral Red')
        timings=payload.get('timing',{})
        if not isinstance(timings,dict) or any(key not in {'active_controller_seconds','tool_wall_seconds','prerequisite_wait_seconds'} or type(value) not in {int,float} or value<0 for key,value in timings.items()):raise WorkflowError('Operation timings require separate nonnegative controller, tool and prerequisite observations')
        record={key:deepcopy(payload[key]) for key in ['result','classification','actual_lane','counts','assertions','failure_category','cleanup','timing'] if key in payload}
        record.update({key:attempt[key] for key in ['key','definition','sources','environment_identity','attempt_id']});record.update({'evidence':evidence,'recorded_at':now(),'execution_sessions':deepcopy(entry.get('execution_sessions',{}))})
        if result=='red':slot['red']=record
        slot['result']=record
        record['payload_hash']=digest(dump(payload).encode());slot.setdefault('receipts',{})[attempt['attempt_id']]=record
        if result=='fail' and classification=='executed-control':
            signature=payload.get('failure_signature')
            if not isinstance(signature,str) or not signature.strip():raise WorkflowError('Executed failure requires a stable failure signature')
            observed=digest(dump({'failure':signature,'sources':attempt['sources'],'check':check['id'],'new_evidence':payload.get('new_evidence')}).encode())
            prior=entry.get('unchanged_failure',{});count=prior.get('count',0)+1 if prior.get('signature')==observed else 1
            entry['unchanged_failure']={'signature':observed,'count':count}
            record['failure_signature']=signature;record['diagnostic_key']=observed
            if count>=2:
                entry['resume_stage']=entry['stage'];entry['stage']='blocked';entry['stop_reason']='Two unchanged executed failures'
                if state['active_run']:state['active_run'].update({'phase':'blocked','stop_task_id':task['id'],'stop_reason':entry['stop_reason'],'next_action':'Resolve the recorded failure before explicit resumption'})
        elif result in {'pass','red'}:entry.pop('unchanged_failure',None)
        if classification=='host-policy-rejection':
            entry['resume_stage']=entry['stage'];entry['stage']='blocked';entry['stop_reason']='Host policy rejected the operation: '+payload.get('reason','missing execution scope')
            if state['active_run']:state['active_run'].update({'phase':'blocked','stop_task_id':task['id'],'stop_reason':entry['stop_reason'],'next_action':payload.get('next_action','Report the rejection and missing scope')})
        store.save(text,state);return record

def validate_task_checks(store,tid,state=None,check_id=None):
    state=state or store.load();task=validation_task(store,tid);entry=state['task_progress'].get(tid)
    if not entry or entry['stage'] not in {'implementing','awaiting-validation'}:raise WorkflowError('Task implementation/check progress is missing or blocked')
    assert_admission(store,state,tid)
    records=[]
    for check in check_specs(task):
        if check_id is not None and check['id']!=check_id:continue
        record=entry['checks'].get(check['id'],{}).get('result')
        if not record or record['result']!='pass':raise WorkflowError('Required check pending, failed or unavailable: '+check['id'])
        current=check_snapshot(store,task,check,state)
        if record['key']!=current['key'] or record['definition']!=current['definition']:raise WorkflowError('Required check evidence is stale: '+check['id'])
        for ref in record['evidence']:
            if not ref.get('available') or file_hash(store.root/ref['path'])!=ref['sha256']:raise WorkflowError('Required result evidence is unavailable or changed: '+check['id'])
        records.append({'check':check,'result':record,**({'red':entry['checks'][check['id']]['red']} if 'red' in entry['checks'][check['id']] else {})})
    return records

def resume_task(store,payload):
    if not isinstance(payload.get('resolution'),str) or not payload['resolution'].strip():raise WorkflowError('Explicit resumption requires the resolved condition and evidence')
    admitted=admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);entry=state['task_progress'].get(payload['task_id'])
        if not entry or entry['stage']!='blocked':raise WorkflowError('No blocked task progress to resume')
        run=state['active_run']
        if run and payload['task_id'] not in scope_ids(parse(text),run):raise WorkflowError('Blocked task is outside the active controller scope')
        entry['stage']=entry.get('resume_stage','awaiting-validation');entry.setdefault('resolutions',[]).append(payload['resolution']);entry['admission']=admitted
        if state['active_run']:
            run['admission']=admitted
            if run.get('stop_task_id')==payload['task_id'] and run['stop_reason']==entry.get('stop_reason'):
                run.update({'stop_reason':None,'next_action':'Resume the recorded check or implementation step'});run.pop('stop_task_id',None)
        store.save(text,state);return {'stage':entry['stage'],'task_id':payload['task_id']}

def reuse_check(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);source,source_check=get_check(store,state,{'task_id':payload['from_task_id'],'check_id':payload['from_check_id']});target,target_check=get_check(store,state,payload)
        if not state['active_run'] or not source.get('validation_group_id') or source.get('validation_group_id')!=target.get('validation_group_id'):raise WorkflowError('Shared evidence requires an admitted compatible group')
        assert_scope(store,state,parse(text),target['id'])
        records=validate_task_checks(store,source['id'],state,source_check['id']);record=next(item['result'] for item in records if item['check']['id']==source_check['id'])
        target_entry=state['task_progress'].get(target['id'],{});recipe,environment=recipe_for(store,target_check)
        source_session=state['task_progress'][source['id']].get('execution_sessions',{}).get(environment)
        if source_session:target_entry.setdefault('execution_sessions',{}).setdefault(environment,deepcopy(source_session))
        snapshot=check_snapshot(store,target,target_check,state)
        if snapshot['key']!=record['key']:raise WorkflowError('Shared checks differ in recipe, parameters, assertion, sources or environment')
        entry=state['task_progress'].get(target['id'])
        if not entry:raise WorkflowError('Shared target implementation has not started')
        reused={**deepcopy(record),'definition':snapshot['definition'],'reused_from':source['id']}
        entry['checks'].setdefault(target_check['id'],{})['result']=reused;store.save(text,state);return reused

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['refresh','manifest','index','read','select','pending','intake','process','start','next','advance','checkpoint','complete','finish','audit','prune','history','cycle','capture-foundation','begin','implemented','prepare-check','record-check','reuse-check','admit','resume-task','accept-revalidation']);parser.add_argument('root',type=Path);parser.add_argument('--id');parser.add_argument('--names',nargs='*');parser.add_argument('--input',type=Path);parser.add_argument('--mode',choices=['next','all'],default='next');parser.add_argument('--component');parser.add_argument('--apply',action='store_true');parser.add_argument('--expected-source-hash')
    args=parser.parse_args(argv)
    try:
        store=Store(args.root);payload=json.loads(args.input.read_text()) if args.input else {}
        if args.expected_source_hash:payload['expected_source_hash']=args.expected_source_hash
        cmd=args.command
        if cmd=='manifest':
            if args.apply:
                with store.lock():result=manifest(store);store.commit({'.skill-tree/skill-tree.json':dump(result)})
            else:result=manifest(store)
        elif cmd=='refresh':
            with store.lock():text=store.text();result=store.load(text);store.save(text,result)
        elif cmd=='index':result=store.load()
        elif cmd=='read':result=resolve(parse(store.text()),[args.id])[0]
        elif cmd=='select':result=select(parse(store.text()),args.id)
        elif cmd=='pending':result=resolve(parse(store.text()),args.names or ([args.id] if args.id else []),'Pending Queue')
        elif cmd=='intake':result=intake(store,payload)
        elif cmd=='capture-foundation':result=capture_foundation(store)
        elif cmd=='begin':result=begin_task(store,payload)
        elif cmd=='implemented':result=mark_implemented(store,payload)
        elif cmd=='prepare-check':result=prepare_check(store,payload)
        elif cmd=='record-check':result=record_check(store,payload)
        elif cmd=='reuse-check':result=reuse_check(store,payload)
        elif cmd=='admit':result=resume_admission(store)
        elif cmd=='resume-task':result=resume_task(store,payload)
        elif cmd=='accept-revalidation':result=accept_revalidation(store,payload)
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
