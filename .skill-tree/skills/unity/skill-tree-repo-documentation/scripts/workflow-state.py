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
import stat
import subprocess
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

try:workspaces=owned_module('skill_tree_run_workspaces',Path(__file__).with_name('run-workspaces.py'))
except (ValueError,OSError) as error:
    if __name__!='__main__':raise
    print(json.dumps({'ok':False,'error':str(error)},ensure_ascii=True,sort_keys=True));raise SystemExit(2)

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
    rules=owned_module('skill_tree_document_rules',path)
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
    meta={k:deepcopy(task[k]) for k in FIELDS+OPTIONAL_FIELDS if k in task};meta.update(changes)
    validate_metadata(meta,task['queue'])
    match=re.match(r'^###[^\n]+\n\s*```yaml\n.*?\n```\s*',task['body'],re.S)
    entry=render(task['title'],meta,task['body'][match.end():])
    lines=text.splitlines(keepends=True);lines[task['start']:task['end']]=[entry]
    return ''.join(lines)

class Store:
    def __init__(self,root,run_id=None,allow_unselected=False,route_queue=True,neutral=False):
        self.source_root=Path(root).resolve();self.run_id=run_id;self.selected_run_id=None;self.allow_unselected=allow_unselected;self.neutral=neutral
        self.root=workspaces.canonical(root) if route_queue else self.source_root;self.base=self.root/'.skill-tree';self.future=self.base/'documents/future.md';self.state=self.base/'documents/future.json'
        if not self.root.is_dir(): raise WorkflowError('Target repository does not exist')
        if self.base.is_symlink(): raise WorkflowError('Owned metadata directory cannot be a symlink')
    def owned(self,relative):
        path=self.root/relative
        if not relative.startswith('.skill-tree/') or not path.resolve().is_relative_to(self.base.resolve()) or self.base.is_symlink():
            raise WorkflowError('Metadata path outside owned directory: '+relative)
        return path
    @contextmanager
    def lock(self, *, local_delivery=None):
        self.base.mkdir(exist_ok=True)
        if (self.base/'installation/.install-lock').exists():raise WorkflowError('Installation lock exists; implementation waits for the owned profile transaction')
        path=self.base/'.writer-lock'
        try: fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError as exc: raise WorkflowError('Writer lock exists; verify owner PID/host before explicit lock removal') from exc
        try:
            os.write(fd,dump({'pid':os.getpid(),'host':socket.gethostname()}).encode());os.close(fd)
            if (self.base/'installation/.install-lock').exists():raise WorkflowError('Installation lock exists; preserve the profile handoff')
            self._local_delivery = local_delivery
            self.recover()
            mutable=[self.future,self.state,self.base/'skill-tree.json',self.base/'history/task-outcomes.jsonl',*list((self.base/'history').rglob('*.json')),*list((self.base/'clarifications').glob('*.json')),*list((self.base/'decisions').glob('*.json')),*list((self.base/'invocations').glob('*.json'))]
            self._write_hashes={p.relative_to(self.root).as_posix():file_hash(p) for p in mutable}
            self._writer_active=True;self._hook_active_admissions=[];self._hook_business_committed=False
            yield
        finally:
            self._writer_active=False;self._hook_preflights={};self._hook_active_admissions=[];self._hook_business_committed=False
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
        if not journal.exists() and not journal.is_symlink(): return
        if journal.is_symlink():raise WorkflowError('Workflow transaction journal cannot be a symlink')
        record=json.loads(journal.read_text())
        if record.get('local_delivery') != getattr(self, '_local_delivery', None):
            raise WorkflowError('Workflow transaction journal requires its exact original local delivery action')
        if record.get('format')!='skill-tree-transaction' or not isinstance(record.get('writes'),list): raise WorkflowError('Unsupported transaction state')
        # Validate every target before replay, including already-applied writes.
        for write in record['writes']:
            path=self.owned(write['path']);actual=file_hash(path);desired=digest(write['content'].encode())
            if actual not in {write['expected_hash'],desired}: raise WorkflowError('Interrupted transaction conflicts with source: '+write['path'])
        for write in record['writes']:
            self.replace(self.owned(write['path']),write['content'])
        journal.unlink()
    def commit(self,writes):
        admissions=list(getattr(self,'_hook_active_admissions',[]))
        navigation_followup=set(writes)=={'.skill-tree/skill-tree.json'} and getattr(self,'_hook_business_committed',False)
        for admission in admissions:
            _hook_admission(self,admission['scope'],admission['chain_ids'],register=False,navigation_followup=navigation_followup)
        record={'format':'skill-tree-transaction','writes':[]}
        if getattr(self, '_local_delivery', None) is not None:
            record['local_delivery'] = self._local_delivery
        for rel,content in writes.items():
            path=self.owned(rel);actual=file_hash(path);expected=getattr(self,'_write_hashes',{}).get(rel,actual)
            if actual!=expected:raise WorkflowError('Metadata changed during the operation; preserve developer changes: '+rel)
            record['writes'].append({'path':rel,'expected_hash':expected,'content':content})
        self.replace(self.base/'.transaction.json',dump(record));self.recover()
        if admissions and not navigation_followup:self._hook_business_committed=True
        if hasattr(self,'_write_hashes'):
            for write in record['writes']:self._write_hashes[write['path']]=digest(write['content'].encode())
    def expect_unchanged(self,relative,expected_hash):
        if not hasattr(self,'_write_hashes'):raise WorkflowError('Metadata expectations require the owned writer lock')
        path=self.owned(relative)
        if expected_hash is not None and (not isinstance(expected_hash,str) or not re.fullmatch('[a-f0-9]{64}',expected_hash)):raise WorkflowError('Metadata expectation requires an exact digest or absent state')
        if relative in self._write_hashes and self._write_hashes[relative]!=expected_hash:raise WorkflowError('Metadata expectation conflicts with the writer snapshot')
        if file_hash(path)!=expected_hash:raise WorkflowError('Metadata changed before expectation registration')
        self._write_hashes[relative]=expected_hash

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
            if old.get('format')!=FORMAT or old.get('schema') not in {2,3} or not isinstance(old.get('tasks'),list) or 'active_run' not in old: raise WorkflowError('Unsupported checkpoint; reinstall and run explicit setup')
            if old['schema']==3 and not old.get('run_registry'):raise WorkflowError('Schema 3 requires the run registry; explicit recovery required')
            if old['schema']==2 and old.get('run_registry'):raise WorkflowError('Unfinalized run registry requires explicit workspace-setup confirm_queue_id')
            value['schema']=old['schema']
            run=old['active_run']
            if run is not None:
                validate_run(run)
            value['active_run']=run
            if 'run_registry' in old:value['run_registry']=old['run_registry']
            if self.neutral:
                if 'run_registry' in value:workspaces.validate_registry(value['run_registry'])
            else:value=workspaces.project(self,value)
            for retained in value.get('run_registry',{}).get('runs',{}).values():validate_run(retained)
            value['task_progress']=old.get('task_progress')
            validate_progress(value,parse(text),{record['task_id'] for record in self.outcomes() if record['disposition']=='completed'})
        return value
    def outcomes(self):
        path=self.base/'history/task-outcomes.jsonl'
        if not path.exists(): return []
        try: return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except json.JSONDecodeError as exc: raise WorkflowError('Corrupt task outcome ledger') from exc
    def save(self,text,state,extras=None,*,update_navigation=True):
        state['source_hash']=digest(text.encode());state['tasks']=index(text)
        writes=dict(extras or {})
        if text!=self.text(): writes['.skill-tree/documents/future.md']=text
        persisted=workspaces.persist(self,state)
        self.record_run_event(text,persisted,writes)
        writes['.skill-tree/documents/future.json']=dump(persisted)
        self.commit(writes)
        if 'run_registry' in persisted:state['run_registry']=persisted['run_registry']
        if update_navigation:
            self.commit({'.skill-tree/skill-tree.json':dump(manifest(self))})
    def record_run_event(self,text,state,writes):
        registry=state.get('run_registry');rid=self.selected_run_id
        if not registry or not rid:return
        old=json.loads(self.state.read_text()) if self.state.exists() else {}
        before={t['id']:t for t in parse(self.text())};after={t['id']:t for t in parse(text)}
        changes=[]
        for tid in sorted(set(before)|set(after)):
            a=before.get(tid);b=after.get(tid)
            if (a or {}).get('body')!=(b or {}).get('body'):
                changes.append({'task_id':tid,'before':a and {'queue':a['queue'],'body':a['body']},'after':b and {'queue':b['queue'],'body':b['body']}})
        ledger=writes.get('.skill-tree/history/task-outcomes.jsonl','')
        prior_ids={r['id'] for r in self.outcomes()}
        outcomes=[json.loads(line) for line in ledger.splitlines() if line.strip() and json.loads(line)['id'] not in prior_ids]
        prior=old.get('run_registry',{}).get('runs',{}).get(rid)
        current=registry['runs'].get(rid)
        owned=set((prior or {}).get('admitted_task_ids',[]))|set((current or {}).get('admitted_task_ids',[]))
        progress_changes=[]
        for tid in sorted(owned):
            before_progress=old.get('task_progress',{}).get(tid);after_progress=state['task_progress'].get(tid)
            if before_progress!=after_progress:progress_changes.append({'task_id':tid,'before':before_progress,'after':after_progress})
        if not changes and not outcomes and not progress_changes and prior==current:return
        sequence=state['run_registry'].setdefault('event_sequences',{}).get(rid,0)+1
        state['run_registry']['event_sequences'][rid]=sequence
        event={'sequence':sequence,'schema':1,'id':identity('E'),'queue_id':registry['queue_id'],'run_id':rid,'changes':changes,'progress_changes':progress_changes,'outcomes':outcomes,'checkpoint_before':prior,'checkpoint_after':current}
        state['run_registry'].setdefault('applied_events',[]).append(event['id'])
        writes['.skill-tree/history/run-events/'+rid.lower()+'/'+event['id'].lower()+'.json']=dump(event)
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
    focus=run.get('maintenance')
    if focus is not None:
        if not isinstance(focus,dict) or not valid_id(focus.get('id'),'MF') or not run.get('stop_reason') or focus.get('execution_restriction')!='static-unit-only' or not focus.get('instruction') or not isinstance(focus.get('admission'),dict):raise WorkflowError('Corrupt maintenance scope')
        if any(not isinstance(focus.get(key),list) or not set(focus[key]).issubset(run['admitted_task_ids']) for key in ['snapshot','required_ids','admitted_task_ids']):raise WorkflowError('Maintenance scope expands the preserved controller')

def intake(store,payload):
    with store.lock():
        store.guard(payload.get('expected_source_hash'));text=store.text();tasks=parse(text);state=store.load(text)
        matches=[t for t in tasks if normalized(t['title'])==normalized(payload['title'])]
        if matches: raise WorkflowError('Possible duplicate task; clarify update/reuse before intake: '+matches[0]['id'])
        relation=payload.get('relation','main');priority=payload.get('priority')
        classification=payload.get('classification')
        if classification is not None:
            if not isinstance(classification,dict) or not isinstance(classification.get('kind'),str) or classification['kind'] not in {'defect','other'} or not isinstance(classification.get('reason'),str) or not classification['reason'].strip():
                raise WorkflowError('Intake classification requires defect/other kind and a semantic reason')
        defect=classification is not None and classification['kind']=='defect'
        placement=payload.get('relative_priority')
        if placement is not None:
            if priority is not None:raise WorkflowError('Conflicting numeric and relative priorities require owner clarification')
            if not isinstance(placement,dict) or not isinstance(placement.get('direction'),str) or placement['direction'] not in {'above','below'}:
                raise WorkflowError('Relative priority requires above/below direction and an exact open task ID')
            anchors=[task for task in tasks if task['id']==placement.get('task_id')]
            if len(anchors)!=1:raise WorkflowError('Relative priority requires an exact open task ID')
            priority=anchors[0]['priority']+(1 if placement['direction']=='above' else -1)
        parent=payload.get('related_task_id');root=payload.get('root_task_id')
        related_priority=None
        if relation!='main':
            related=resolve(tasks,[parent],'Prioritized Next Changes')[0]
            expected_root=related['root_task_id'] or related['id']
            if root!=expected_root: raise WorkflowError('Finding root does not match direct parent')
            root_task=resolve(tasks,[root],'Prioritized Next Changes')[0]
            related_priority=max((t['priority'] for t in tasks),default=100)+1 if relation in {'blocker','subtask'} else root_task['priority']-1
        automatic_defect=priority is None and defect and not payload.get('low_priority')
        if priority is None and defect:
            priority=25 if payload.get('low_priority') else max((t['priority'] for t in tasks),default=100)+1
        if priority is None and related_priority is not None:priority=related_priority
        if priority is None: priority=25 if payload.get('low_priority') else 100
        meta={'id':identity('P'),'priority':priority,'status':'Pending','parent_pending_ids':[],'processing_run_id':None,'root_task_id':root,'related_task_id':parent,'relation':relation,'depends_on':[]}
        validate_metadata(meta,'Pending Queue')
        for field in ['description','expected_behavior']:
            if not isinstance(payload.get(field),str) or not payload[field].strip(): raise WorkflowError('Intake requires understood '+field)
        body='Description:\n- '+payload['description']+'\n\nExpected behavior:\n- '+payload['expected_behavior']
        if classification is not None:
            body+='\n\nRequest classification:\n- '+classification['kind']+': '+classification['reason']
        for field,label in [('context','Current context'),('source','Source'),('priority_reason','Priority rationale')]:
            if payload.get(field): body+='\n\n'+label+':\n- '+payload[field]
        if automatic_defect and not payload.get('priority_reason'):
            body+='\n\nPriority rationale:\n- Defect intake receives the highest open Pending, Prioritized or Backlog priority plus one; an empty queue uses the default-100 baseline.'
        assert_prose(payload['title']+'\n'+body)
        text=insert(text,'Pending Queue',render(payload['title'],meta,body))
        run=state['active_run']
        if run:
            run['pending_ids'].append(meta['id'])
            if not run.get('stop_reason'):run['phase']='capture-findings'
            focus=run.get('maintenance')
            if focus and parent in focus['admitted_task_ids']:focus['pending_ids'].append(meta['id'])
        store.save(text,state)
        return meta

def capture_foundation(store):
    profile=store.source_root/'.skill-tree/installation/profile.json'
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

def processing_helper():
    # The helper shares the workflow API without importing a sibling entry point.
    from types import SimpleNamespace
    module=owned_module('skill_tree_processing',Path(__file__).with_name('plugin-processing.py'))
    module.wf=SimpleNamespace(**globals())
    return module


def process(store,payload):
    """Apply researched dispositions and publish optional holds atomically."""
    proposed=payload.get('dispositions',{})
    due=[tid for tid,row in proposed.items() if isinstance(row,dict) and row.get('status') in {'promoted','resolved'}] if isinstance(proposed,dict) else []
    if due:prepare_hook_admission(store,scope={'kind':'pending','pending_ids':due})
    specs=payload.get('tasks',[])
    if not isinstance(specs,list) or any(not isinstance(spec,dict) for spec in specs):
        raise WorkflowError('Processing tasks require a list of objects')
    assigned=[spec.get('reuse_id') or identity('T') for spec in specs]
    pr=identity('PR')
    application=processing_helper() if specs else None
    prepared=application.prepare_publication(store,payload,assigned,pr) if application else None
    with store.lock():
        store.guard(payload.get('expected_source_hash'))
        text=store.text();state=store.load(text)
        if due:hook_admission(store,scope={'kind':'pending','pending_ids':due})
        if application:application.guard_publication(store,payload,prepared)
        before_text=text;text,receipt=_processing_proposal(store,payload,text,state,assigned,pr)
        extras={};sessions={}
        if prepared and prepared['sessions']:
            text,sessions=application.publish(store,text,state,receipt,prepared)
            receipt['clarification_sessions']={tid:record['id'] for tid,record in sessions.items()}
        if application:
            text,reopened=application.attach_existing_changes(store,before_text,text,receipt,state)
            extras=application.publication_writes(store,text,sessions,reopened)
            if reopened:receipt['reopened_clarification_sessions']={tid:record['id'] for tid,record in reopened.items()}
            run=state['active_run']
            if run and any(tid in run['admitted_task_ids'] for tid in sessions.keys()|reopened.keys()):
                run['next_action']='Complete the held post-processing clarification before implementation'
        store.save(text,state,extras)
        return receipt


def _processing_proposal(store,payload,text,state,assigned,pr):
    """Build the same prospective output inside and outside the writer."""
    tasks=parse(text)
    selected=resolve(tasks,payload.get('selectors',[]),'Pending Queue'); selected_ids={t['id'] for t in selected}
    dispositions=payload.get('dispositions',{})
    if set(dispositions)!=selected_ids: raise WorkflowError('Every selected Pending ID requires one disposition')
    for result in dispositions.values():
        if result.get('status') not in {'promoted','retained','resolved'} or not result.get('reason'): raise WorkflowError('Processing disposition requires status and reason')
    for result in dispositions.values():assert_prose(result['reason'])
    due=[tid for tid,result in dispositions.items() if result.get('status') in {'promoted','resolved'}]
    specs=payload.get('tasks',[])
    if not isinstance(specs,list) or any(not isinstance(spec,dict) for spec in specs):raise WorkflowError('Processing tasks require a list of objects')
    # Allocate every identity before resolving forward references; no writes occur until validation succeeds.
    keys={}
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
    produced=[];reused=[]; consumed=set();run=state['active_run']
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
    receipt={'id':pr,'pending_contexts':{task['id']:{'semantic_fingerprint':digest(clarification_text_semantics(task['body']).encode()),'content_fingerprint':digest(task['body'].encode())} for task in selected},'selected_ids':[t['id'] for t in selected],'created_ids':produced,'reused_ids':reused,'task_keys':keys,'dispositions':dispositions}
    if run:
        run['processing_results'].append(receipt)
        if not run.get('stop_reason'):run['phase']='dependencies';run['next_action']='Select required task'
        allowed=set(run['admitted_task_ids']);introduced=set();updated=parse(text)
        for tid in produced+reused:
            child=resolve(updated,[tid])[0]
            if child['relation'] in {'blocker','subtask'} and child['related_task_id'] in allowed:
                introduced.update(dependency_scope(updated,{'snapshot':[tid]}))
        if dependency_scope(updated,run)-allowed-introduced:raise WorkflowError('Processing cannot admit a dependency outside the captured required scope')
        run['admitted_task_ids']=sorted(allowed|introduced);run['required_ids']=list(dict.fromkeys(run['required_ids']+sorted(introduced)));run['admitted_groups']=admitted_groups(updated,run)
        focus=run.get('maintenance')
        if focus:
            focused=dependency_scope(updated,focus)
            if not focused.issubset(set(focus['admitted_task_ids'])|introduced):raise WorkflowError('Processing cannot expand the maintenance scope outside captured required work')
            for task in updated:
                if task['id'] in focused and any(recipe_for(store,check)[0]['lane'] not in {'static','unit'} for check in check_specs(task)):raise WorkflowError('Maintenance descendants require non-product validation')
            focus['admitted_task_ids']=sorted(focused);focus['required_ids']=sorted(focused)
    return text,receipt

def _start_selection(store,mode,selector,workspace,text=None):
    tasks=parse(store.text() if text is None else text);options=workspace or {}
    scoped='snapshot_ids' in options
    if scoped:
        ids=options['snapshot_ids']
        if mode!='all' or selector or not isinstance(ids,list) or not ids or any(not valid_id(tid,'T') for tid in ids) or len(set(ids))!=len(ids):
            raise WorkflowError('Exact Implement All snapshot requires a nonempty unique list of prioritized T- IDs')
        selected=set(ids)
        roots=sorted([t for t in tasks if t['queue']=='Prioritized Next Changes' and t['id'] in selected],key=lambda t:-t['priority'])
        missing=selected-{t['id'] for t in roots}
        if missing:raise WorkflowError('Snapshot IDs must identify exact prioritized tasks: '+', '.join(sorted(missing)))
        for task in roots:select(tasks,task['id'])
        chosen=roots[0];snapshot=[t['id'] for t in roots]
    else:
        chosen=select(tasks,selector)
        snapshot=[chosen['id']] if mode=='next' else [t['id'] for t in sorted([t for t in tasks if t['queue']=='Prioritized Next Changes'],key=lambda t:-t['priority'])]
    if mode=='all' and selector:raise WorkflowError('Implement All uses the initial prioritized snapshot')
    return tasks,chosen,snapshot

def start(store,mode,selector=None,limits=None,workspace=None):
    admission=admit_profile(store)
    pre_tasks,pre_chosen,pre_snapshot=_start_selection(store,mode,selector,workspace)
    for tid in dependency_scope(pre_tasks,{'snapshot':pre_snapshot}):prepare_hook_admission(store,scope=tid)
    with store.lock():
        text=store.text();state=store.load(text)
        registry=state.get('run_registry')
        if not registry and state['active_run'] is not None: raise WorkflowError('Active run exists; resume the recorded run')
        if not registry and workspaces.common_dir(store.root):raise WorkflowError('Git controllers require workspace-setup before start')
        tasks,chosen,snapshot=_start_selection(store,mode,selector,workspace,text)
        run={'id':identity('WR'),'mode':mode,'snapshot':snapshot,'root_task_id':chosen['id'],'current_task_id':chosen['id'],'phase':'implement','required_ids':[chosen['id']],'deferred_ids':[],'pending_ids':[],'processing_results':[],'completed_ids':[],'limits':limits or {},'partial_work':[],'stop_reason':None,'next_action':'Implement selected task','started_at':now()}
        for tid in dependency_scope(tasks,run):clarification_admission(store,tid)
        run['admission']=admission;run['admitted_task_ids']=sorted(dependency_scope(tasks,run));run['required_ids']=list(run['admitted_task_ids']);run['admitted_groups']=admitted_groups(tasks,run)
        if registry:
            done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
            conflicts={tid:registry['claims'][tid] for tid in run['admitted_task_ids'] if tid not in done and tid in registry['claims']}
            if conflicts:raise WorkflowError('Required task claims conflict: '+dump(conflicts))
            path=workspaces.provision(store,run,workspace or {})
            registry['runs'][run['id']]=run;store.selected_run_id=run['id'];store.run_id=run['id']
        validate_run(run);state['active_run']=run;store.save(text,state)
        if registry:
            # A failed Git operation leaves the reserved run and claims for explicit recovery.
            workspaces.create_reserved(store,run,path);store.save(text,state)
        return run

def enforce_limits(run):
    if run.get('stop_reason'):raise WorkflowError('Run stopped: '+str(run['stop_reason'])+'; resolve the recorded condition before explicit checkpoint resumption')
    budget=run['limits'].get('selected_task_budget')
    if budget is not None and budget['used_seconds']>=budget['limit_seconds']:raise WorkflowError('Selected-task budget exhausted')

def execution_run(run):
    return run.get('maintenance',run)

def focus_maintenance(store,payload):
    """Bound explicitly requested non-product work while preserving a stopped controller."""
    admission=admit_profile(store)
    if not payload.get('instruction'):raise WorkflowError('Maintenance focus requires the explicit owner instruction')
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run'];tasks=parse(text)
        if not run or not run.get('stop_reason'):raise WorkflowError('Maintenance focus requires a preserved stopped controller')
        if run.get('maintenance'):raise WorkflowError('Resume the existing maintenance focus')
        selected=resolve(tasks,[payload['task_id']],'Prioritized Next Changes')[0]
        scope=dependency_scope(tasks,{'snapshot':[selected['id']]})
        if not scope.issubset(scope_ids(tasks,run)):raise WorkflowError('Maintenance focus is outside the admitted required scope')
        for task in tasks:
            if task['id'] in scope:
                if task['status']!='Ready' or any(recipe_for(store,check)[0]['lane'] not in {'static','unit'} for check in check_specs(task)):raise WorkflowError('Maintenance focus permits only researched static/unit infrastructure checks')
        run['maintenance']={'id':identity('MF'),'root_task_id':selected['id'],'snapshot':[selected['id']],'required_ids':sorted(scope),'admitted_task_ids':sorted(scope),'admitted_groups':{},'current_task_id':selected['id'],'completed_ids':[],'deferred_ids':[],'pending_ids':[],'phase':'implement','limits':{},'stop_reason':None,'admission':admission,'instruction':payload['instruction'],'next_action':'Implement the bounded infrastructure task','execution_restriction':'static-unit-only'}
        store.save(text,state);return run['maintenance']

def next_task(store):
    state=store.load();run=state['active_run']
    if not run:raise WorkflowError('No active run')
    workspaces.ensure_workspace(store,run)
    enforce_limits(execution_run(run));assert_admission(store,state)
    if run.get('maintenance'):
        state=deepcopy(state);run=deepcopy(run['maintenance']);state['active_run']=run
    tasks=parse(store.text());by_id={t['id']:t for t in tasks};done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
    validate_dependencies(tasks,done)
    visiting=set();visited=set()
    def walk(tid):
        if tid in done:
            if state.get('run_registry') and not completed_dependency_integrated(store,state,tid):
                task=validation_task(store,tid)
                return [{**task,'priority':0,'completed_contract':True}]
            return []
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
    pending=[t['id'] for t in tasks if t['queue']=='Pending Queue' and t['root_task_id']==root and t['relation'] in {'blocker','subtask'}]
    if pending:return {'phase':'process-required','root_task_id':root,'pending_ids':pending}
    if task.get('completed_contract'):
        return {'phase':'validate','task_id':task['id'],'root_task_id':root,'completed_contract':True,'title':task['title'],'body':task['body'],'checks':check_specs(task)}
    if task['status']!='Ready':
        session=processing_helper().session_for_task(store,task['id'])
        if session:raise WorkflowError('Selected required task has an open post-processing hold: '+session['id']+' — '+session['next_action'])
        raise WorkflowError('Selected required task has blocking unresolved questions: '+task['id'])
    clarification_admission(store,task['id'])
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
    clarification_admission(store,task['id'])
    return {'phase':'validate' if stage=='awaiting-validation' else 'implement','root_task_id':root,'task_id':task['id'],'title':task['title'],'priority':task['priority'],'body':task['body'],'checks':check_specs(task)}

def advance(store):
    # Read-only selection prepares the exact initial and group-switched hook scopes.
    next_task(store)
    with store.lock():
        result=next_task(store);text=store.text();state=store.load(text);run=state['active_run']
        run=execution_run(run)
        run['admitted_groups']=admitted_groups(parse(text),run)
        run['phase']=result['phase'];run['current_task_id']=result.get('task_id');run['root_task_id']=result.get('root_task_id',run['root_task_id']);run['next_action']=result['phase']
        if result.get('task_id') and result['task_id'] not in run['required_ids']:run['required_ids'].append(result['task_id'])
        if result.get('completed_contract'):
            tid=result['task_id'];entry=state['task_progress'].get(tid)
            if entry and entry.get('run_id') not in {None,state['active_run']['id']}:raise WorkflowError('Task validation progress belongs to another run')
            if not entry:state['task_progress'][tid]={'stage':'awaiting-validation','checks':{},'revalidation':True,'admission':run['admission'],'run_id':state['active_run']['id']}
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
    if payload.get('disposition','completed')=='completed':prepare_hook_admission(store,scope=payload.get('task_id'))
    with store.lock():
        store.guard(payload.get('expected_source_hash'));text=store.text();tasks=parse(text);state=store.load(text);task=resolve(tasks,[payload['task_id']],'Prioritized Next Changes')[0]
        disposition=payload.get('disposition','completed')
        if disposition!='completed':hook_pending_admission(store,scope=task['id'])
        clarification_admission(store,task['id'],hook_gate=disposition=='completed')
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
            if run:enforce_limits(execution_run(run))
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
        task_context={'semantic_fingerprint':clarification_fingerprints(clarification_baselines([task]))[task['id']],'content_fingerprint':digest(task['body'].encode())}
        record={'task_context':task_context,'run_id':state['active_run']['id'] if state['active_run'] else None,'validation_group_id':task.get('validation_group_id'),'boundary_validation':task.get('boundary_validation','not-required'),'validation_plan':check_specs(task),'validation_signature':task_signature(task),'check_results':validation_records,'depends_on':task['depends_on'],'id':identity('O'),'task_id':task['id'],'title':task['title'],'root_task_id':task['root_task_id'],'related_task_id':task['related_task_id'],'parent_pending_ids':task['parent_pending_ids'],'disposition':disposition,'outcome':payload['outcome'],'acceptance':payload.get('acceptance',[]),'limitations':payload.get('limitations',[]),'followup_ids':payload.get('followup_ids',[]),'source_fingerprints':payload.get('source_fingerprints',{}),'commits':payload.get('commits',[]),'evidence':[evidence_pointer(store,e) for e in payload.get('evidence',[])],'recorded_at':now()}
        ledger=''.join(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n' for o in outcomes+[record])
        if state['active_run']:
            run=state['active_run'];run.setdefault('completion_refs',{})[task['id']]=record['id'];run['completed_ids'].append(task['id']) if disposition=='completed' else None
            target=execution_run(run)
            if target is not run and disposition=='completed':target['completed_ids'].append(task['id'])
            target['current_task_id']=None;target['phase']='resume-parent';target['next_action']='Select required task or finish root'
        state['task_progress'].pop(task['id'],None)
        text=remove(text,{task['id']});store.save(text,state,{'.skill-tree/history/task-outcomes.jsonl':ledger});return record

LOCAL_DELIVERY_COMMANDS = {
    'local-delivery-' + name: action for name, action in (
        ('status', 'status'), ('prepare', 'prepare'), ('merge', 'merge'), ('reconcile', 'reconcile'),
        ('admit-target', 'admit-target'), ('admit-retained', 'admit-retained'),
        ('validate', 'validate-target'), ('complete', 'complete'),
    )
}


def _delivery_receipt_path(run, suffix=''):
    return '.skill-tree/history/runs/run-' + run['id'].lower() + suffix + '.json'


def _delivery_install_barrier(root):
    for relative in ('.skill-tree/installation/.install-lock', '.skill-tree/installation/.journal.json',
                     '.skill-tree/installation/.plugin-journal.json'):
        path = root / relative
        if path.exists() or path.is_symlink():
            raise WorkflowError('Local delivery requires explicit resolution of the installation lock or journal: ' + relative)


def _delivery_writer_barrier(store, owner):
    _delivery_install_barrier(store.root)
    path = store.base / '.writer-lock'
    if path.exists() or path.is_symlink():
        raise WorkflowError('Local delivery requires the canonical workflow writer to stop')
    journal = store.base / '.transaction.json'
    if journal.exists() or journal.is_symlink():
        if journal.is_symlink() or json.loads(journal.read_text()).get('local_delivery') != owner:
            raise WorkflowError('Unrelated or uncertain workflow transaction journal requires explicit recovery')


def _delivery_inspect_installation(root, source, *, current=False):
    library = source / '.skill-tree/lib/installation.js'
    profile = root / '.skill-tree/installation/profile.json'
    if not library.is_file():
        if current or profile.exists() or (root / '.skill-tree/invocations').exists():
            raise WorkflowError('The reviewed owned installation verifier is unavailable')
        return {'paths': [], 'scope': None, 'active': False}
    if (library.is_symlink() or library.parent.is_symlink()
            or workspaces.local_git(source, 'ls-files', '--error-unmatch', '--', '.skill-tree/lib/installation.js',
                                    accepted=(0, 1)).returncode
            or workspaces.local_git(source, 'diff', '--quiet', '--', '.skill-tree/lib/', accepted=(0, 1)).returncode):
        raise WorkflowError('Local delivery requires the tracked reviewed owned installation verifier')
    script = r"""
const path = require('node:path');
const [root, source, current] = process.argv.slice(1);
const directory = path.join(source, '.skill-tree');
const core = require(path.join(directory, 'lib/installation.js'));
const composer = require(path.join(directory, 'lib/composer.js'));
const profile = core.receipt(root, current === 'true');
const active = core.hasActiveOperation(root);
if (!profile) { console.log(JSON.stringify({paths: [], scope: null, active})); process.exit(0); }
core.verifyOwned(root, profile);
const paths = new Set([core.PROFILE, ...Object.keys(profile.bundle_digests)]);
const destinations = {}, installed = new Map();
for (const [relative, record] of Object.entries(profile.destinations)) {
  for (const file of Object.keys(record.files)) paths.add(relative + '/' + file);
  const owners = [...(record.providers || [record.provider])].sort();
  destinations[relative] = {name: record.name, providers: owners};
  for (const provider of owners) {
    if (!installed.has(provider)) installed.set(provider, new Set());
    installed.get(provider).add(record.name);
  }
}
if (current === 'true') {
  core.verify(root, directory);
  if (composer.json(composer.sourceInputs(directory)) !== composer.json(profile.source_digests))
    throw Error('The target owned generation does not match the exact merged source');
} else {
  const previous = path.join(root, core.INSTALL, 'source');
  const priorOperations = Object.keys(composer.readJson(previous, 'templates/operations.json'));
  const nextOperations = Object.keys(composer.readJson(directory, 'templates/operations.json'));
  const matrix = composer.readJson(directory, 'config/providers.json').providers;
  for (const [provider, names] of installed) {
    if (!priorOperations.every(name => names.has(name))) continue;
    const owner = matrix.find(item => item.id === provider);
    if (!owner) throw Error('A retained target provider is unavailable');
    for (const name of nextOperations) {
      const relative = path.posix.join(provider === 'generic' ? '' : owner.projectPath, name);
      const record = destinations[relative] || {name, providers: []};
      if (record.name !== name) throw Error('A retained target destination conflicts with an incoming core operation');
      destinations[relative] = {...record, providers: [...new Set([...record.providers, provider])].sort()};
    }
  }
}
console.log(JSON.stringify({paths: [...paths].sort(), active, scope: {flavor: profile.flavor, destinations},
  admission: {identity: profile.identity, environment_id: profile.environment_id, flavor: profile.flavor}}));
"""
    environment = {key: value for key, value in os.environ.items() if key not in {'NODE_OPTIONS', 'NODE_PATH'}}
    result = subprocess.run(['node', '-e', script, str(root), str(source), str(current).lower()],
                            capture_output=True, text=True, timeout=35, env=environment)
    if result.returncode:
        reason = next((line.removeprefix('Error: ') for line in result.stderr.splitlines() if line.startswith('Error: ')),
                      'Owned installation verification failed')
        raise WorkflowError(reason)
    return json.loads(result.stdout)


def _delivery_path_hash(root, relative):
    path = root
    for part in relative.split('/'):
        path = path / part
        if path.is_symlink():
            raise WorkflowError('Local delivery requires an ordinary owned file: ' + repr(relative))
    return file_hash(path) if path.is_file() else None


def _delivery_metadata_path(relative, *, canonical):
    if relative.startswith('.skill-tree/history/'):
        return True
    return canonical and (relative in {'.skill-tree/documents/future.md', '.skill-tree/documents/future.json',
                                       '.skill-tree/skill-tree.json'}
                          or relative.startswith(('.skill-tree/clarifications/', '.skill-tree/decisions/',
                                                  '.skill-tree/invocations/')))


def _delivery_dirt(root, source, *, canonical):
    dirt = workspaces.local_worktree_dirt(root)
    if any(relative.startswith('.skill-tree/lib/') for relative in dirt):
        raise WorkflowError('Local integration requires the reviewed owned installation verifier bytes')
    installed = _delivery_inspect_installation(root, source)
    owned = set(installed['paths'])
    preserved = set()
    for relative in dirt:
        if relative not in owned and not _delivery_metadata_path(relative, canonical=canonical):
            if workspaces.local_unchanged_file(root, relative):
                continue
            raise WorkflowError('Dirty worktree has no matching owned delivery scope: ' + repr(relative))
        if _delivery_path_hash(root, relative) is None:
            raise WorkflowError('A preserved local delivery path is missing: ' + repr(relative))
        preserved.add(relative)
    return preserved, installed


def _delivery_freeze_source(store, run, expected=None):
    source = workspaces.local_source_identity(store, run)
    if expected is not None and source != {key: value for key, value in expected.items() if key != 'preserved_dirt'}:
        raise WorkflowError('The source head, tree or worktree changed after implementation acceptance')
    _delivery_install_barrier(store.source_root)
    dirt, _ = _delivery_dirt(store.source_root, store.source_root, canonical=False)
    source['preserved_dirt'] = {relative: _delivery_path_hash(store.source_root, relative) for relative in sorted(dirt)}
    return source


def _delivery_original(store, run):
    delivery = run['delivery']
    ref = _delivery_receipt_path(run)
    if not delivery.get('implementation_receipt_sha256'):
        raise WorkflowError('Local delivery requires an immutable implementation acceptance receipt')
    if _delivery_path_hash(store.root, ref) != delivery['implementation_receipt_sha256']:
        raise WorkflowError('The immutable local implementation completion receipt changed or is unavailable')
    original = json.loads(store.owned(ref).read_text())
    original_delivery = original.get('delivery', {})
    if (original.get('id') != run['id'] or original.get('workspace') != run.get('workspace')
            or original_delivery.get('authorization') != delivery.get('authorization')
            or original_delivery.get('reviewed_source') != delivery.get('reviewed_source')):
        raise WorkflowError('The immutable local implementation completion identity differs')
    return original


def _delivery_state_projection(state, run_id, retained):
    projection = deepcopy(state)
    projection['active_run'] = None
    registry = projection['run_registry']
    own = registry['runs'][run_id]
    for field in ('delivery', 'profile_refresh_required', 'stop_reason', 'next_action'):
        own.pop(field, None)
    for retained_id in retained:
        record = registry['runs'][retained_id]
        for field in ('profile_refresh_required', 'admission', 'local_delivery_readmissions'):
            record.pop(field, None)
    registry.pop('applied_events', None)
    for changed in (run_id, *retained):
        registry.get('event_sequences', {}).pop(changed, None)
    return digest(dump(projection).encode())


def _delivery_preservation(store, state, run, incoming, dirt):
    retained = {}
    for retained_id, candidate in state['run_registry']['runs'].items():
        if retained_id == run['id'] or workspaces.delivery_finished(candidate):
            continue
        if not candidate.get('stop_reason') or candidate.get('maintenance'):
            raise WorkflowError('Retained local run requires a stopped handoff: ' + retained_id)
        retained[retained_id] = {
            'admission': candidate['admission'], 'profile_refresh_required': candidate.get('profile_refresh_required'),
            'local_delivery_readmissions': candidate.get('local_delivery_readmissions', []),
        }
    files = {'.skill-tree/documents/future.md', '.skill-tree/history/task-outcomes.jsonl'}
    files.update(path for path in dirt if _delivery_metadata_path(path, canonical=True))
    for name in ('clarifications', 'decisions', 'invocations', 'history/run-events'):
        directory = store.base / name
        files.update(path.relative_to(store.root).as_posix() for path in directory.rglob('*')
                     if path.is_file() or path.is_symlink())
    files.difference_update({'.skill-tree/documents/future.json', '.skill-tree/skill-tree.json'})
    return {
        'files': {relative: _delivery_path_hash(store.root, relative) for relative in sorted(files)
                  if not any(workspaces.local_overlap(relative, path) for path in incoming)},
        'state_sha256': _delivery_state_projection(state, run['id'], retained),
        'applied_events': state['run_registry'].get('applied_events', []),
        'sequences': {rid: state['run_registry']['event_sequences'].get(rid, 0) for rid in (run['id'], *retained)},
        'retained': retained,
    }


def _delivery_assert_preserved(store, state, run, preservation):
    retained = preservation['retained']
    if _delivery_state_projection(state, run['id'], retained) != preservation['state_sha256']:
        raise WorkflowError('The preserved canonical workflow or retained scope changed')
    registry = state['run_registry']
    previous_events = preservation['applied_events']
    current_events = registry.get('applied_events', [])
    if current_events[:len(previous_events)] != previous_events:
        raise WorkflowError('The preserved workflow event history changed')
    sequences = dict(preservation['sequences'])
    for event_id in current_events[len(previous_events):]:
        if not valid_id(event_id, 'E'):
            raise WorkflowError('A local delivery workflow event has an invalid identity')
        candidates = [store.base / 'history/run-events' / rid.lower() / (event_id.lower() + '.json')
                      for rid in sequences]
        records = [path for path in candidates if path.is_file() and not path.is_symlink()]
        if len(records) != 1:
            raise WorkflowError('A workflow event outside the prepared local delivery scope appeared')
        event = json.loads(records[0].read_text())
        rid = event.get('run_id')
        if (rid not in sequences or records[0].parent.name != rid.lower() or event.get('id') != event_id
                or event.get('queue_id') != registry['queue_id'] or event.get('sequence') != sequences[rid] + 1
                or any(event.get(key) for key in ('changes', 'progress_changes', 'outcomes'))):
            raise WorkflowError('A workflow event changed outside the exact local delivery scope')
        sequences[rid] += 1
    if any(registry['event_sequences'].get(rid, 0) != count for rid, count in sequences.items()):
        raise WorkflowError('The preserved workflow event counters changed')
    for relative, expected in preservation['files'].items():
        if _delivery_path_hash(store.root, relative) != expected:
            raise WorkflowError('A preserved canonical queue or history file changed: ' + relative)
    for retained_id, prior in retained.items():
        current = state['run_registry']['runs'][retained_id]
        entries = current.get('local_delivery_readmissions', [])
        if entries == prior['local_delivery_readmissions']:
            if (current['admission'] != prior['admission']
                    or current.get('profile_refresh_required') not in (prior['profile_refresh_required'], True)):
                raise WorkflowError('A retained run changed outside scoped local delivery admission')
        elif (len(entries) != len(prior['local_delivery_readmissions']) + 1
              or entries[:-1] != prior['local_delivery_readmissions']
              or entries[-1].get('delivery_run_id') != run['id']
              or entries[-1].get('admission') != current['admission']
              or current.get('profile_refresh_required')):
            raise WorkflowError('A retained local delivery re-admission receipt conflicts with the stopped run')


def _delivery_preflight(store, state, run, preparation=None):
    if run.get('stop_reason') != 'Local delivery pending':
        raise WorkflowError('Local delivery requires its original stopped handoff')
    reviewed = run['delivery']['reviewed_source']
    if _delivery_freeze_source(store, run, reviewed) != reviewed:
        raise WorkflowError('The source head, worktree or preserved source bytes changed after implementation acceptance')
    ref, head = workspaces.local_target_head(store, run)
    dirt, installed = _delivery_dirt(store.root, store.source_root, canonical=True)
    if installed['active']:
        raise WorkflowError('Canonical execution requires a stopped installation and workflow handoff')
    if preparation is None:
        workspaces.local_merge_base(store, run, reviewed, head)
        incoming = workspaces.local_incoming(store.root, head, reviewed['source_head'])
        workspaces.local_preflight_collisions(store.root, incoming, dirt)
        preparation = {
            **{key: value for key, value in reviewed.items() if key != 'preserved_dirt'},
            'target_ref': ref, 'target_head': head, 'incoming': sorted(incoming), 'target_scope': installed['scope'],
            'prior_target_profile': installed.get('admission', {}).get('identity'),
            'preservation': _delivery_preservation(store, state, run, incoming, dirt),
        }
    elif ref != preparation['target_ref']:
        raise WorkflowError('The prepared target branch identity changed')
    elif head == preparation['target_head'] and (installed['scope'] != preparation['target_scope']
            or installed.get('admission', {}).get('identity') != preparation['prior_target_profile']):
        raise WorkflowError('The prepared target ownership or installation profile changed before merge')
    _delivery_assert_preserved(store, state, run, preparation['preservation'])
    return preparation, head, dirt


def _delivery_verified_target(store, preparation, merge):
    expected = preparation['target_scope']
    if not expected:
        raise WorkflowError('Local delivery has no previously verified target flavor and provider scope')
    inspected = _delivery_inspect_installation(store.root, store.root, current=True)
    if inspected['scope'] != expected:
        raise WorkflowError('Target flavor, provider or destination scope differs from the prepared local delivery')
    if inspected['active']:
        raise WorkflowError('Canonical execution requires a stopped installation and workflow handoff')
    profile = inspected['admission']['identity']
    affected = [rid for rid, previous in preparation['preservation']['retained'].items()
                if preparation['prior_target_profile'] != profile or previous['profile_refresh_required']]
    return {'merge_commit': merge['commit'], 'profile_identity': profile,
            'admission': inspected['admission'], 'scope': expected, 'affected_retained': sorted(affected)}


def _local_delivery_commands(merge):
    return (
        ('owned-installation', ('node', '.skill-tree/installation/manager.js', '--verify')),
        ('source-sync', ('npm', 'run', 'sync:check')),
        ('repository-validation', ('npm', 'run', 'validate')),
        ('installer-list', ('node', '.skill-tree/bin/install.js', '--list')),
        ('incoming-diff', ('git', '--no-replace-objects', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                           '-c', 'diff.autoRefreshIndex=false', 'diff', '--check', merge['parents'][0], merge['commit'], '--')),
    )


def _run_local_delivery_checks(root, merge):
    checks = []
    for name, argv in _local_delivery_commands(merge):
        result = subprocess.run(argv, cwd=root, capture_output=True, timeout=120)
        if result.returncode:
            raise WorkflowError('Current local target validation failed: ' + name)
        checks.append({'id': name, 'argv': list(argv), 'exit_code': result.returncode,
                       'stdout_sha256': digest(result.stdout), 'stderr_sha256': digest(result.stderr)})
    return checks


def _delivery_validate_record(store, run, integration, admission):
    validation = integration.get('validation', {})
    if (validation.get('merge_commit') != admission['merge_commit']
            or validation.get('profile_identity') != admission['profile_identity']
            or not validation.get('checks') or any(check.get('exit_code') != 0 for check in validation['checks'])
            or len(validation.get('evidence', [])) != 1):
        raise WorkflowError('Current executed validation is required before local delivery completion')
    evidence = validation['evidence'][0]
    if (evidence.get('path') != _delivery_receipt_path(run, '-local-validation')
            or _delivery_path_hash(store.root, evidence['path']) != evidence.get('sha256')):
        raise WorkflowError('Local target validation evidence is missing or changed')
    report = json.loads(store.owned(evidence['path']).read_text())
    if report != {key: value for key, value in validation.items() if key != 'evidence'}:
        raise WorkflowError('The fixed local validation report differs from its recorded result')


def _delivery_save(store, run_id, expected, owner, change, extras=None, *, guard=None):
    with store.lock(local_delivery=owner):
        _delivery_install_barrier(store.root)
        if file_hash(store.state) != expected:
            raise WorkflowError('Canonical workflow changed during the local delivery action')
        text = store.text()
        state = store.load(text)
        run = state['active_run']
        if run['id'] != run_id:
            raise WorkflowError('Local delivery workflow identity changed')
        if guard is not None:
            guard(state, run)
        change(run)
        store.save(text, state, extras, update_navigation=False)


def _delivery_admit_retained(store, state, run, preparation, merge, admission, retained_id, owner, before):
    if retained_id not in admission['affected_retained']:
        raise WorkflowError('Select an exact retained stopped run from the prepared local delivery scope')
    retained = state['run_registry']['runs'][retained_id]
    entries = retained.get('local_delivery_readmissions', [])
    if entries and entries[-1].get('delivery_run_id') == run['id']:
        if entries[-1]['merge_commit'] != merge['commit']:
            raise WorkflowError('The original retained re-admission binds another merge')
        return
    if not retained.get('profile_refresh_required'):
        raise WorkflowError('The selected retained run has no affected installation profile to re-admit')
    retained_store = Store(store.root, retained_id)
    retained_store.load()
    workspaces.ensure_workspace(retained_store, retained)
    _delivery_install_barrier(retained_store.source_root)
    profile_path = '.skill-tree/installation/profile.json'
    profile_hash = _delivery_path_hash(retained_store.source_root, profile_path)
    admitted = admit_profile(retained_store)
    prior = preparation['preservation']['retained'][retained_id]['admission']
    if admitted['identity'] == 'repository-local' and prior.get('identity') != 'repository-local':
        raise WorkflowError('The retained stopped run lost its previously owned installation profile')
    receipt = {'delivery_run_id': run['id'], 'merge_commit': merge['commit'],
               'run_id': retained_id, 'admission': admitted}

    def update(record):
        record['admission'] = admitted
        record.pop('profile_refresh_required', None)
        record.setdefault('local_delivery_readmissions', []).append(receipt)

    def guard(current, record):
        selected = current['run_registry']['runs'][run['id']]
        if selected.get('stop_reason') != 'Local delivery pending':
            raise WorkflowError('The original stopped local delivery handoff changed during re-admission')
        _delivery_assert_preserved(store, current, selected, preparation['preservation'])
        workspaces.ensure_workspace(retained_store, record)
        _delivery_install_barrier(retained_store.source_root)
        if _delivery_path_hash(retained_store.source_root, profile_path) != profile_hash:
            raise WorkflowError('The retained worktree profile changed during scoped re-admission')

    _delivery_save(retained_store, retained_id, before, owner, update, guard=guard)


def _delivery_retained_current(store, state, run, admission):
    fingerprints = {}
    for retained_id in admission['affected_retained']:
        retained = state['run_registry']['runs'][retained_id]
        entries = retained.get('local_delivery_readmissions', [])
        if (retained.get('profile_refresh_required') or not entries
                or entries[-1].get('delivery_run_id') != run['id']
                or entries[-1].get('merge_commit') != admission['merge_commit']):
            raise WorkflowError('Affected retained runs require exact scoped re-admission')
        retained_store = Store(store.root, retained_id)
        retained_store.load()
        workspaces.ensure_workspace(retained_store, retained)
        _delivery_install_barrier(retained_store.source_root)
        profile = '.skill-tree/installation/profile.json'
        fingerprints[retained_id] = _delivery_path_hash(retained_store.source_root, profile)
        if admit_profile(retained_store) != entries[-1]['admission']:
            raise WorkflowError('A retained stopped admission changed after local re-admission')
    return fingerprints


def local_delivery_action(store, action, payload):
    if not valid_id(store.run_id, 'WR'):
        raise WorkflowError('Local delivery requires an explicit --run-id')
    if action not in LOCAL_DELIVERY_COMMANDS.values() or not isinstance(payload, dict):
        raise WorkflowError('Select an exact local delivery action')
    if (set(payload) != ({'run_id'} if action == 'admit-retained' else set())
            or action == 'admit-retained' and not valid_id(payload.get('run_id'), 'WR')):
        raise WorkflowError('Local delivery only accepts the exact scoped action inputs')
    workspaces.local_git_environment()
    run = store.load()['active_run']
    if not run or not workspaces.local_merge_order(run):
        raise WorkflowError('The selected run has no authorized local-merge order')
    if action == 'status':
        return run['delivery']
    target = workspaces.local_merge_target(store.root, run)
    owner = {'run_id': run['id'], 'action': action, **({'retained_run_id': payload['run_id']} if payload else {})}
    with workspaces.publication_lock(store.root, 'local', target):
        _delivery_writer_barrier(store, owner)
        if (store.base / '.transaction.json').exists():
            with store.lock(local_delivery=owner):
                pass
        state = store.load()
        run = state['active_run']
        _delivery_original(store, run)
        delivery = run['delivery']
        if workspaces.delivery_finished(run):
            if action == 'complete':
                return delivery
            raise WorkflowError('The selected local delivery is already completed')
        before = file_hash(store.state)
        integration = deepcopy(delivery.get('local_integration', {}))
        preparation = integration.get('preparation')
        if not preparation and action != 'prepare':
            raise WorkflowError('Prepare the exact authorized local delivery before continuation')
        prepared, head, dirt = _delivery_preflight(store, state, run, preparation)
        extras = None
        if action == 'prepare':
            if preparation and head != preparation['target_head']:
                raise WorkflowError('The prepared target head has moved; reconcile the original merge')
            workspaces.local_preflight_collisions(store.root, prepared['incoming'], dirt)
            integration['preparation'] = prepared
        else:
            if action == 'merge' and head == prepared['target_head']:
                workspaces.local_preflight_collisions(store.root, prepared['incoming'], dirt)
                _delivery_writer_barrier(store, owner)
                with store.lock(local_delivery=owner):
                    _delivery_install_barrier(store.root)
                    if file_hash(store.state) != before:
                        raise WorkflowError('Canonical workflow changed before local integration')
                    workspaces.run_local_merge(store.root, store.source_root, prepared)
                _, head, _ = _delivery_preflight(store, state, run, prepared)
            merge = workspaces.local_merge_receipt(store.root, prepared, head)
            if action in ('merge', 'reconcile'):
                integration['merge'] = merge
            elif integration.get('merge') != merge:
                raise WorkflowError('Reconcile the exact actual local merge before target activation')
            else:
                admission = _delivery_verified_target(store, prepared, merge)
                if action == 'admit-target':
                    integration['target_admission'] = admission
                elif integration.get('target_admission') != admission:
                    raise WorkflowError('Explicit current canonical target re-admission is required')
                elif action == 'admit-retained':
                    _delivery_admit_retained(store, state, run, prepared, merge, admission, payload['run_id'], owner, before)
                    return store.load()['active_run']['delivery']
                elif action == 'validate-target':
                    if 'validation' in integration:
                        try:
                            _delivery_validate_record(store, run, integration, admission)
                        except (WorkflowError, ValueError):
                            pass
                        else:
                            return delivery
                    checks = _run_local_delivery_checks(store.root, merge)
                    report = {'merge_commit': merge['commit'], 'profile_identity': admission['profile_identity'], 'checks': checks}
                    path = _delivery_receipt_path(run, '-local-validation')
                    content = dump(report)
                    extras = {path: content}
                    integration['validation'] = {**report, 'evidence': [{'path': path, 'sha256': digest(content.encode())}]}
                elif action == 'complete':
                    _delivery_validate_record(store, run, integration, admission)
                    retained_profiles = _delivery_retained_current(store, state, run, admission)
        _, current_head, _ = _delivery_preflight(store, store.load(), run, prepared)
        if current_head != head:
            raise WorkflowError('The exact canonical target head changed during local delivery')
        if action in {'validate-target', 'complete'} and _delivery_verified_target(store, prepared, integration['merge']) != admission:
            raise WorkflowError('The verified target installation changed during local delivery')
        if (integration == delivery.get('local_integration') and action != 'complete'
                and not (action == 'admit-target' and run.get('profile_refresh_required'))):
            return delivery

        def update(record):
            record['delivery']['local_integration'] = integration
            if action == 'admit-target':
                record.pop('profile_refresh_required', None)
            elif action == 'complete':
                record['delivery'].update(status='merged', order_completed=True)
                record['stop_reason'] = None
                record['next_action'] = None

        profile_hash = _delivery_path_hash(store.root, '.skill-tree/installation/profile.json')

        def guard(current, record):
            if workspaces.local_target_head(store, record)[1] != head:
                raise WorkflowError('The canonical target head changed before receipt recording')
            if workspaces.local_source_identity(store, record)['source_head'] != prepared['source_head']:
                raise WorkflowError('The reviewed source head changed before receipt recording')
            if _delivery_path_hash(store.root, '.skill-tree/installation/profile.json') != profile_hash:
                raise WorkflowError('The target installation changed before receipt recording')
            _delivery_assert_preserved(store, current, record, prepared['preservation'])
            if action == 'complete':
                _delivery_validate_record(store, record, integration, admission)
                for rid, expected in retained_profiles.items():
                    retained = Store(store.root, rid)
                    retained.load()
                    if _delivery_path_hash(retained.source_root, '.skill-tree/installation/profile.json') != expected:
                        raise WorkflowError('A retained stopped admission changed before local completion')

        _delivery_save(store, run['id'], before, owner, update, extras, guard=guard)
        return store.load()['active_run']['delivery']


def finish(store):
    inspected = store.load().get('active_run')
    if inspected and workspaces.local_merge_order(inspected) and not inspected.get('maintenance'):
        workspaces.local_git_environment()
        if inspected['delivery']['implementation'] == 'completed':
            return _delivery_original(store, inspected)
        target = workspaces.local_merge_target(store.root, inspected)
        owner = {'run_id': inspected['id'], 'action': 'finish'}
        with workspaces.publication_lock(store.root, 'local', target):
            _delivery_writer_barrier(store, owner)
            if (store.base / '.transaction.json').exists():
                with store.lock(local_delivery=owner):
                    pass
                inspected = store.load()['active_run']
                if inspected['delivery']['implementation'] == 'completed':
                    return _delivery_original(store, inspected)
            before = store.load()
            _implementation_finish_checks(store, before, before['active_run'], store.text())
            reviewed = _delivery_freeze_source(store, before['active_run'])
            return _finish_implementation(store, reviewed, owner)
    return _finish_implementation(store)


def _implementation_finish_checks(store, state, run, text):
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


def _finish_implementation(store, reviewed=None, owner=None):
    inspected=store.load().get('active_run')
    if inspected:
        references=execution_run(inspected).get('hook_chains',[])
        prepare_hook_admission(store,chain_ids=references)
    with store.lock(local_delivery=owner) if owner else store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        if run.get('maintenance'):
            focus=run['maintenance'];enforce_limits(focus)
            assert_admission(store,state)
            done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
            if not set(focus['required_ids']).issubset(done):raise WorkflowError('Maintenance scope remains incomplete')
            context=deepcopy(state);context['active_run']=deepcopy(focus)
            if stale_completed_checks(store,context):raise WorkflowError('Maintenance acceptance evidence is stale')
            hook_admission(store,chain_ids=focus.get('hook_chains',[]))
            summary=deepcopy(focus);summary.update({'finished_at':now(),'phase':'completed','next_action':None})
            del run['maintenance']
            ref='.skill-tree/history/runs/scope-'+summary['id'].lower()+'.json';run.setdefault('history_refs',[]).append(ref)
            store.save(text,state,{ref:dump(summary)});return summary
        _implementation_finish_checks(store, state, run, text)
        hook_admission(store,chain_ids=run.get('hook_chains',[]))
        run.setdefault('delivery',{'publication':'not-requested','authorization':{}}).update({'implementation':'completed','status':'implementation-completed'})
        if reviewed is not None:
            if workspaces.local_source_identity(store, run) != {key: value for key, value in reviewed.items() if key != 'preserved_dirt'}:
                raise WorkflowError('The reviewed source changed before freezing implementation acceptance')
            run['delivery'].update(status='local-delivery-pending', reviewed_source=reviewed)
            run['stop_reason'] = 'Local delivery pending'
        elif not run['delivery'].get('authorization',{}).get('pr'):
            run['delivery']['status']='local-result'
        run['delivery']['order_completed']=run['delivery']['status']=='local-result'
        summary=deepcopy(run);summary['finished_at']=now();summary['phase']='completed';summary['next_action']=None
        original = dump(summary)
        if state.get('run_registry'):
            registered = deepcopy(summary)
            if reviewed is not None:
                registered['delivery']['implementation_receipt_sha256'] = digest(original.encode())
                registered['next_action'] = 'Prepare the exact authorized local delivery'
            state['run_registry']['runs'][run['id']]=registered
        state['active_run']=None;store.save(text,state,{_delivery_receipt_path(run): original})
    if reviewed is None:prune(store,True)
    return summary

def record_cycle(store):
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        run=execution_run(run)
        semantic_fields=['id','queue','priority','status','parent_pending_ids','root_task_id','related_task_id','relation','depends_on']
        task_state=[{key:task[key] for key in semantic_fields} for task in state['tasks']]
        signature=digest(dump({'tasks':task_state,'outcomes':[o['task_id'] for o in store.outcomes()],'revalidated':{tid:[entry['result']['key'] for entry in checks] for tid,checks in run.get('revalidated_checks',{}).items()},'progress':{tid:{'stage':entry['stage'],'diagnostics':{cid:slot.get('result',{}).get('diagnostic_key') for cid,slot in entry['checks'].items() if slot.get('result',{}).get('diagnostic_key')},'checks':{cid:slot.get('result',{}).get('key') if slot.get('result',{}).get('result')=='pass' else None for cid,slot in entry['checks'].items() if slot.get('result',{}).get('result')=='pass'}} for tid,entry in state['task_progress'].items()}}).encode())
        if run.get('cycle_signature')==signature:
            run['phase']='blocked';run['stop_reason']='Completed cycle without task/dependency progress';run['next_action']='Resolve recorded blocker before resumption'
        run['cycle_signature']=signature;store.save(text,state);return run

def fingerprints(store,paths):
    result={}
    for rel in paths:
        path=store.source_root/rel
        if Path(rel).is_absolute() or '..' in Path(rel).parts or not path.resolve().is_relative_to(store.source_root):raise WorkflowError('Source fingerprint requires repository-relative path')
        result[rel]=binding_snapshot(store.source_root,[rel]) if path.is_dir() else file_hash(path)
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
        proof_store=store
        if outcome.get('run_id'):
            proof_store=deepcopy(store);locator=workspaces.runtime(store.root)
            location=locator['worktrees'].get(outcome['run_id']) if locator else None
            proof_store.source_root=Path(location) if location else store.root/'.skill-tree/unavailable-run-evidence'
        for check in view.get('acceptance',[]):check['evidence']=[evidence_pointer(proof_store,e) for e in check.get('evidence',[])]
        view['evidence']=[evidence_pointer(proof_store,e) for e in view.get('evidence',[])]
        for item in view.get('check_results',[]):
            for key in ['result','red']:
                if key in item:
                    proof=item[key];proof['evidence']=[evidence_pointer(proof_store,ref) for ref in proof.get('evidence',[])]
                    proof['source_fingerprints_match']=fingerprints(proof_store,list(proof.get('sources',{})))==proof.get('sources',{})
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
    for p in sorted((store.base/'documents').rglob('*')):
        if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.name!='.DS_Store':files.append({'path':p.relative_to(store.root).as_posix(),'role':'generated-index-and-active-state' if p==store.state else 'canonical','owner':'skill-tree'})
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
        state=store.load();runs=list(state.get('run_registry',{}).get('runs',{}).values()) or [state['active_run']]
        for run in runs:
            if run:protected.update(run.get('history_refs',[]));protected.add(run['id'])
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
        revalidating=isinstance(entry,dict) and entry.get('revalidation') is True and tid in completed and any(tid in run['required_ids'] for run in (list(state.get('run_registry',{}).get('runs',{}).values()) or [state['active_run']]) if run)
        if (tid not in open_ids and not revalidating) or not isinstance(entry,dict) or entry.get('stage') not in {'implementing','awaiting-validation','blocked'} or not isinstance(entry.get('checks'),dict):raise WorkflowError('Corrupt task progress: '+tid)

def admit_profile(store):
    path=store.source_root/'.skill-tree/installation/profile.json'
    if not path.is_file():
        source=store.source_root/'.skill-tree/config/repository.json'
        if source.is_file() and json.loads(source.read_text()).get('role')=='source':return {'identity':'repository-local','flavor':'general'}
        raise WorkflowError('Missing installation profile; install a project-scoped flavor before implementation')
    manager=store.source_root/'.skill-tree/installation/manager.js'
    if not manager.is_file():raise WorkflowError('Missing local profile manager; repair the owned installation')
    import subprocess
    try:result=subprocess.run(['node',str(manager),'--verify'],capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as exc:raise WorkflowError('Profile admission failed within 30 seconds; cleanup reserve 5 seconds') from exc
    if result.returncode:raise WorkflowError((result.stderr or result.stdout).strip())
    value=json.loads(path.read_text())
    return {'identity':value['identity'],'environment_id':value['environment_id'],'flavor':value['flavor']}

def resume_admission(store):
    store.load()
    admitted=admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run']
        if not run:raise WorkflowError('No active run')
        target=execution_run(run);target['admission']=admitted
        if target is run and run.pop('profile_refresh_required',False) and run['stop_reason']=='Installation profile changed; re-admit before continuation':run['stop_reason']=None
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

def binding_path(root,relative):
    if not isinstance(relative,str) or not relative or Path(relative).is_absolute() or '\\' in relative or any(part in {'','.','..'} for part in relative.split('/')):raise WorkflowError('Binding paths require canonical repository-relative paths')
    current=Path(root)
    for part in relative.split('/'):
        current=current/part
        if current.is_symlink():raise WorkflowError('Binding symlink is unsupported: '+relative)
    return current

def binding_snapshot(root,paths,excluded=None,allow_empty=False):
    if not isinstance(paths,list) or (not paths and not allow_empty):raise WorkflowError('Binding requires source paths')
    excluded=excluded or []
    if not isinstance(excluded,list):raise WorkflowError('Binding exclusions require relative paths')
    for relative in excluded:binding_path(root,relative)
    files={}
    def visit(relative):
        if any(relative==prefix or relative.startswith(prefix+'/') for prefix in excluded):return
        path=binding_path(root,relative)
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.name not in {'.git','__pycache__','.DS_Store'}:visit(relative+'/'+child.name)
        elif path.is_file():files[relative]=file_hash(path)
        else:raise WorkflowError('Missing or unsupported binding source: '+relative)
    for relative in paths:visit(relative)
    return digest(''.join(name+'\0'+files[name]+'\n' for name in sorted(files)).encode())

def binding_context(store,recipe,allow_blocked=False):
    binding_id=recipe.get('execution_binding')
    if not binding_id:return None
    profile=json.loads((store.source_root/'.skill-tree/installation/profile.json').read_text())
    binding=profile.get('execution_bindings',{}).get(binding_id)
    if not binding or recipe.get('lane') not in {'unity-editmode','unity-playmode'}:raise WorkflowError('A reviewed Unity execution binding is required')
    if not binding.get('locator','').startswith('.skill-tree/local/'):raise WorkflowError('Binding locator requires local machine configuration')
    locator_path=binding_path(store.source_root,binding['locator'])
    if file_hash(locator_path)!=binding['locator_digest']:raise WorkflowError('Binding locator changed; review and refresh the owned profile')
    locator=json.loads(locator_path.read_text(encoding='utf-8-sig'))
    for key in ['queue_root','workspace_root','execution_root']:
        path=Path(binding[key])
        if not path.is_absolute() or not path.is_dir() or path.resolve()!=path:raise WorkflowError('Binding root requires an exact real directory')
    queue=Path(binding['queue_root']);workspace=Path(binding['workspace_root']);execution=Path(binding['execution_root'])
    if locator.get('schema')!=1 or locator.get('queue_root')!=str(store.source_root) or locator.get('workspace_root')!=str(workspace) or queue!=store.source_root or binding_path(workspace,binding['execution_subdir'])!=execution:raise WorkflowError('Foreign binding queue or execution identity')
    if queue==execution or queue in execution.parents or execution in queue.parents or queue==workspace or queue in workspace.parents or workspace in queue.parents:raise WorkflowError('Binding queue and execution roots overlap')
    if file_hash(binding_path(queue,binding['review_path']))!=binding['review_digest']:raise WorkflowError('Binding source review changed')
    for root,paths,key in [(queue,binding['source_paths'],'queue_digest'),(execution,binding['source_paths'],'execution_digest'),(workspace,binding['workspace_paths'],'workspace_digest')]:
        if binding_snapshot(root,paths,binding.get('exclude_paths',[]) if root!=workspace else [],allow_empty=root==workspace)!=binding[key]:raise WorkflowError('Binding source identity changed: '+key)
    queue_paths=binding.get('queue_paths',[])
    if not isinstance(queue_paths,list):raise WorkflowError('Binding support paths require a list')
    if not queue_paths and not binding.get('workspace_paths'):raise WorkflowError('Binding requires reviewed runner/profile paths')
    if queue_paths and binding_snapshot(queue,queue_paths)!=binding.get('queue_support_digest'):raise WorkflowError('Binding queue support identity changed')
    pins=binding['pins']
    if recipe.get('editor_version')!=pins['editor_version']:raise WorkflowError('Recipe Editor pin differs from the reviewed binding')
    for root in [queue,execution]:
        text=binding_path(root,'ProjectSettings/ProjectVersion.txt').read_text();version=re.search(r'm_EditorVersion:\s*(\S+)',text)
        locked=json.loads(binding_path(root,'Packages/packages-lock.json').read_text(encoding='utf-8-sig'))['dependencies']
        if not version or version[1]!=pins['editor_version'] or locked.get('com.unity.test-framework',{}).get('version')!=pins['utf_version']:raise WorkflowError('Binding Editor or UTF pin mismatch')
        if root==execution:
            pipeline=locked.get('com.unity.pipeline',{});pipeline_version=pipeline.get('version')
            if pipeline.get('source')=='embedded':
                if pipeline_version!='file:com.unity.pipeline':raise WorkflowError('Binding embedded Pipeline location mismatch')
                embedded=json.loads(binding_path(execution,'Packages/com.unity.pipeline/package.json').read_text(encoding='utf-8-sig'))
                if embedded.get('name')!='com.unity.pipeline':raise WorkflowError('Binding embedded Pipeline identity mismatch')
                pipeline_version=embedded.get('version')
            if pipeline_version!=pins['pipeline_version']:raise WorkflowError('Binding Pipeline pin mismatch')
    if binding['blockers'] and not allow_blocked:raise WorkflowError('Validation-blocked: '+str(len(binding['blockers']))+' unqualified isolated source differences; review '+binding['review_path'])
    return {'id':binding_id,**({'queue_support_digest':binding['queue_support_digest']} if 'queue_support_digest' in binding else {}),**{key:binding[key] for key in ['queue_root','execution_root','workspace_root','queue_digest','execution_digest','workspace_digest','pins','review_digest','blockers']}}

def recipe_for(store,check):
    profile_path=store.source_root/'.skill-tree/installation/profile.json'
    profile=json.loads(profile_path.read_text()) if profile_path.exists() else {}
    local_path=store.source_root/'.skill-tree/config/repository.json'
    local=json.loads(local_path.read_text()) if local_path.exists() else {}
    recipes=profile.get('recipes',local.get('recipes',{}))
    recipe=recipes.get(check['recipe_id'])
    if recipe is None and check['recipe_id']=='static-inspection':recipe={'lane':'static','input_paths':[],'assertion_contract':'explicit source and artifact assertions'}
    if recipe is None:raise WorkflowError('Validation-blocked: recipe unavailable: '+check['recipe_id']+'; review the required plan after profile refresh')
    inputs={}
    for rel in recipe.get('input_paths',[]):inputs.update(fingerprints(store,[rel]))
    if profile and any(profile.get('inputs',{}).get(rel)!=value for rel,value in inputs.items()):raise WorkflowError('Profile refresh-required: node .skill-tree/installation/manager.js --refresh-profile')
    recipe=deepcopy(recipe);recipe.pop('execution_context',None)
    binding=binding_context(store,recipe)
    parameters={**check['parameters'],'project_root':str(store.source_root),'queue_root':str(store.root)}
    if binding:
        if parameters.get('execution_checkout',binding['execution_root'])!=binding['execution_root']:raise WorkflowError('Check checkout differs from the reviewed execution binding')
        declared=profile['execution_bindings'][recipe['execution_binding']]
        for relative in check.get('sources',[]):
            if any(relative==prefix or relative.startswith(prefix+'/') for prefix in declared.get('exclude_paths',[])):raise WorkflowError('A required check source is excluded from the binding')
        recipe['execution_context']=binding;parameters.update({'project_root':binding['execution_root'],'binding_workspace':binding['workspace_root']})
    arguments=[]
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
    if store.state.exists() and store.load().get('run_registry'):workspaces.environment(store,{'runtime':True})
    fields=['project_root','authorization','profile_id','deadline_utc','cleanup_seconds','tool_identity','session_identity','fixture_identity','build_identity','identity_evidence']
    if not isinstance(session,dict) or any(not session.get(key) for key in fields):raise WorkflowError('Product checks require an owned execution session with authorization, identity evidence, deadline and cleanup reserve')
    binding=binding_context(store,recipe)
    expected_root=Path(binding['execution_root']) if binding else store.source_root
    if Path(session['project_root']).resolve()!=expected_root:raise WorkflowError('Execution session checkout differs from the covered root')
    if binding:
        if session.get('queue_root')!=str(store.root) or session.get('binding_id')!=binding['id'] or session.get('source_identity')!=binding['execution_digest']:raise WorkflowError('Execution session lacks the reviewed queue, binding or source identity')
        tools=session.get('tool_identity')
        if not isinstance(tools,dict) or any(tools.get(key)!=binding['pins'][key] for key in ['cli_version','pipeline_version']):raise WorkflowError('Execution session toolchain differs from the binding pins')
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

def stale_completed_checks(store,state,task_ids=None):
    run=state['active_run'];outcomes={record['task_id']:record for record in store.outcomes() if record['disposition']=='completed'};stale=[]
    for tid in dict.fromkeys(run['snapshot']+run['required_ids'] if task_ids is None else task_ids):
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

def completed_dependency_integrated(store,state,tid):
    """Accept exact original sources or current accepted, fully covered revalidation."""
    run=execution_run(state['active_run'])
    if tid not in run['admitted_task_ids'] or tid not in run['required_ids']:raise WorkflowError('Completed dependency is outside the admitted controller scope')
    entry=state['task_progress'].get(tid,{})
    if entry.get('revalidation'):return False
    record=next((o for o in store.outcomes() if o['task_id']==tid and o['disposition']=='completed'),None)
    expected=record.get('source_fingerprints',{}) if record else {}
    if not expected:raise WorkflowError('Completed dependency lacks source fingerprints; explicit source integration review is required: '+tid)
    current=fingerprints(store,list(expected))
    if any(value is None for value in current.values()):raise WorkflowError('Completed dependency source input is unavailable: '+tid)
    if current==expected:return True
    results=run.get('revalidated_checks',{}).get(tid)
    if not results:return False
    context=deepcopy(state);context['active_run']=deepcopy(run)
    if stale_completed_checks(store,context,[tid]):return False
    covered={path:value for item in results for path,value in item['result']['sources'].items()}
    if not set(expected).issubset(covered):raise WorkflowError('Completed dependency revalidation does not cover recorded source fingerprints: '+tid)
    return all(covered[path]==value for path,value in current.items())

def accept_revalidation(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task=validation_task(store,payload['task_id'])
        if not task.get('completed_contract') or not state['task_progress'].get(task['id'],{}).get('revalidation'):raise WorkflowError('No completed-contract revalidation is prepared')
        assert_scope(store,state,parse(text),task['id'])
        results=validate_task_checks(store,task['id'],state)
        execution_run(state['active_run']).setdefault('revalidated_checks',{})[task['id']]=results
        state['task_progress'].pop(task['id']);execution_run(state['active_run'])['next_action']='Select remaining due checks or finish the preserved run'
        store.save(text,state);return {'task_id':task['id'],'phase':'revalidated','checks':[entry['check']['id'] for entry in results]}

def scoped_check_task(store,state,tid):
    progress_owner=state.get('task_progress',{}).get(tid,{}).get('run_id')
    if progress_owner and (not state['active_run'] or state['active_run']['id']!=progress_owner):raise WorkflowError('Task validation progress belongs to another run')
    task=validation_task(store,tid)
    allowed=state['active_run'] and task.get('completed_contract') and task['id'] in state['active_run']['admitted_task_ids'] and task['id'] in state['active_run']['required_ids']
    if task.get('completed_contract') and not allowed:raise WorkflowError('Completed validation contract is outside the active scope')
    if state['active_run'] and task['id'] not in scope_ids(parse(store.text()),state['active_run']) and not allowed:raise WorkflowError('Task is outside the admitted controller scope')
    return task

def get_check(store,state,payload):
    task=scoped_check_task(store,state,payload['task_id'])
    matches=[check for check in check_specs(task) if check['id']==payload['check_id']]
    if len(matches)!=1:raise WorkflowError('Absent check identity')
    return task,matches[0]

def assert_admission(store,state,tid=None):
    profile_path=store.source_root/'.skill-tree/installation/profile.json'
    if not profile_path.is_file():
        local=store.source_root/'.skill-tree/config/repository.json'
        if state.get('run_registry') and not (local.is_file() and json.loads(local.read_text()).get('role')=='source'):raise WorkflowError('Missing worktree installation profile; checkpoint and install the selected flavor before implementation')
        return
    profile=json.loads(profile_path.read_text());run=state['active_run']
    admitted=execution_run(run).get('admission') if run else state['task_progress'].get(tid,{}).get('admission')
    if not admitted or admitted.get('identity')!=profile.get('identity'):raise WorkflowError('Profile admission changed; explicitly re-admit the current profile before continuation')
    plugin_registry='.skill-tree/installation/plugins.json';registry_path=store.source_root/plugin_registry
    if (store.source_root/'.skill-tree/installation/.plugin-journal.json').exists():raise WorkflowError('Plugin installation recovery is required before continuation')
    if registry_path.is_symlink() or file_hash(registry_path)!=profile.get('inputs',{}).get(plugin_registry):raise WorkflowError('Plugin generation changed; refresh the owned profile and explicitly re-admit before continuation')

def assert_scope(store,state,tasks,tid):
    run=state['active_run']
    progress_owner=state.get('task_progress',{}).get(tid,{}).get('run_id')
    if progress_owner and (not run or progress_owner!=run['id']):raise WorkflowError('Task validation progress belongs to another run')
    owner=state.get('run_registry',{}).get('claims',{}).get(tid)
    if owner and (not run or owner!=run['id']):raise WorkflowError('Task claimed by another run')
    if run:
        workspaces.ensure_workspace(store,run)
        run=execution_run(run);enforce_limits(run)
        if tid not in scope_ids(tasks,run) and not (state['task_progress'].get(tid,{}).get('revalidation') and tid in run['admitted_task_ids'] and tid in run['required_ids']):raise WorkflowError('Task is outside the admitted controller scope')
        if run.get('execution_restriction')=='static-unit-only':
            task=validation_task(store,tid) if state['task_progress'].get(tid,{}).get('revalidation') else resolve(tasks,[tid],'Prioritized Next Changes')[0]
            if any(recipe_for(store,check)[0]['lane'] not in {'static','unit'} for check in check_specs(task)):raise WorkflowError('Maintenance focus refuses product checks')
    assert_admission(store,state,tid)

def begin_task(store,payload):
    clarification_admission(store,payload['task_id'])
    # Standalone admission occurs once at the implementation boundary; controller leaves reuse the admitted profile.
    state=store.load();admission=execution_run(state['active_run']).get('admission') if state['active_run'] else admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);task=resolve(parse(text),[payload['task_id']],'Prioritized Next Changes')[0]
        if task['status']!='Ready':raise WorkflowError('Selected task has blocking questions')
        clarification_admission(store,task['id'])
        if state['active_run']:assert_scope(store,state,parse(text),task['id'])
        done={o['task_id'] for o in store.outcomes() if o['disposition']=='completed'}
        if any(dep not in done for dep in task['depends_on']):raise WorkflowError('Verified dependencies remain incomplete')
        if state.get('run_registry') and state['active_run']:
            for dep in task['depends_on']:
                if not completed_dependency_integrated(store,state,dep):raise WorkflowError('Completed dependency requires reviewed source integration into the selected worktree: '+dep)
        entry=state['task_progress'].setdefault(task['id'],{'stage':'implementing','checks':{},'admission':admission,'partial_work':[]})
        if entry['stage']=='blocked':raise WorkflowError('Task progress is blocked; explicitly resolve the recorded stop')
        entry['admission']=admission
        if state['active_run']:entry['run_id']=state['active_run']['id']
        result={'task_id':task['id'],'phase':'validate' if entry['stage']=='awaiting-validation' else 'implement','checks':check_specs(task)}
        store.save(text,state);return result

def mark_implemented(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task=resolve(parse(text),[payload['task_id']],'Prioritized Next Changes')[0]
        if task['status']!='Ready':processing_helper().guard_implementation_progress(store,task)
        entry=state['task_progress'].get(task['id'])
        if not entry or entry['stage']=='blocked':raise WorkflowError('Begin or resume implementation before marking the unit implemented')
        assert_scope(store,state,parse(text),task['id'])
        entry['stage']='awaiting-validation';entry['definition']=task_signature(task);entry['partial_work']=payload.get('changed_files',[])
        store.save(text,state);return {'task_id':task['id'],'phase':'validate','checks':check_specs(task)}

def pending_check_attempt(slot):
    attempt=slot.get('attempt')
    if attempt and not any(record.get('attempt_id')==attempt['attempt_id']
                           for record in (slot.get('result',{}),slot.get('red',{}),*slot.get('receipts',{}).values())):
        return attempt
    return None

def observed_recipe_input_drift(store,attempt):
    recipe=attempt['recipe']
    paths=recipe.get('input_paths',[])
    profile_path=store.source_root/'.skill-tree/installation/profile.json'
    if not paths or recipe.get('execution_binding') or recipe.get('lane') in PRODUCT_LANES or not profile_path.is_file():
        return None
    profile=json.loads(profile_path.read_text())
    inputs=profile.get('inputs',{})
    original={path:inputs.get(path) for path in paths}
    original_environment=digest(dump({'recipe':recipe,'inputs':original}).encode())
    if original_environment!=attempt['environment_identity']:
        return None
    current=fingerprints(store,paths)
    return current if current!=original else None

def check_drift(store,state,task,check_id,attempt):
    observed={'key':None,'definition':task_signature(task),'sources':fingerprints(store,list(attempt['sources']))}
    direct=any(observed[key]!=attempt[key] for key in ('definition','sources'))
    current=next((check for check in check_specs(task) if check['id']==check_id),None)
    if current:
        try:observed['key']=check_snapshot(store,task,current,state)['key']
        except WorkflowError:
            recipe_inputs=observed_recipe_input_drift(store,attempt)
            if recipe_inputs is not None:
                observed['recipe_inputs']=recipe_inputs
                direct=True
            if not direct:raise
    if observed['key'] is None and not direct:
        raise WorkflowError('Current check identity is unavailable without verified drift')
    return observed,direct or observed['key']!=attempt['key']

def check_reconciliation_target(store,state,payload,run_id):
    tid=payload['task_id'];cid=payload['check_id']
    task=scoped_check_task(store,state,tid)
    entry=state['task_progress'].get(tid,{})
    owner=state.get('run_registry',{}).get('claims',{}).get(tid)
    if entry.get('run_id')!=run_id or (owner is not None and owner!=run_id):
        raise WorkflowError('The prepared check belongs to another run or standalone scope')
    focus=(state['active_run'] or {}).get('maintenance')
    if focus:
        required_revalidation=entry.get('revalidation') and tid in focus['admitted_task_ids'] and tid in focus['required_ids']
        if tid not in scope_ids(parse(store.text()),focus) and not required_revalidation:
            raise WorkflowError('The prepared check is outside the active maintenance scope')
    slot=entry.get('checks',{}).get(cid,{})
    attempt=pending_check_attempt(slot)
    if not attempt or attempt['attempt_id']!=payload['attempt_id']:
        raise WorkflowError('Select the exact original pending check attempt')
    origin={key:payload[key] for key in ('task_id','check_id','attempt_id')}
    origin.update(run_id=run_id,expected_key=attempt['key'],expected_definition=attempt['definition'],
                  environment_identity=attempt['environment_identity'])
    return task,slot,attempt,origin

def check_runner_group(value):
    if type(value) is not int or not 1<value<=2**31-1:
        raise WorkflowError('Supply the original positive dedicated process group')
    if not all(hasattr(os,name) for name in ('getpgid','getpgrp','killpg','O_NOFOLLOW','O_DIRECTORY','O_NONBLOCK')):
        raise WorkflowError('Local POSIX process-group inspection is unavailable')
    if value==os.getpgrp():
        raise WorkflowError('The workflow helper group cannot own the original runner')
    return value

def check_runner_timestamp(value):
    try:parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    except (AttributeError,TypeError,ValueError) as error:
        raise WorkflowError('Runner observation requires a valid time') from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkflowError('Runner observation requires a timezone')
    return parsed

def read_check_cleanup_artifact(root,relative):
    path=binding_path(root,relative)
    dir_flags=os.O_RDONLY|os.O_NOFOLLOW|os.O_DIRECTORY
    directory=os.open(root,dir_flags)
    try:
        for part in path.relative_to(root).parts[:-1]:
            child=os.open(part,dir_flags,dir_fd=directory)
            os.close(directory)
            directory=child
        fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=directory)
        with os.fdopen(fd,'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise WorkflowError('Runner cleanup evidence requires an ordinary file')
            return stream.read(65537)
    finally:
        os.close(directory)

def check_cleanup_evidence(store,reference,origin,binding):
    if not isinstance(reference,dict) or set(reference)!={'path','sha256'} or not isinstance(reference['sha256'],str) or not re.fullmatch('[a-f0-9]{64}',reference['sha256']):
        raise WorkflowError('Supply the exact cleanup artifact path and SHA-256')
    try:
        raw=read_check_cleanup_artifact(store.source_root,reference['path'])
        if len(raw)>65536 or digest(raw)!=reference['sha256']:
            raise WorkflowError('The original runner cleanup artifact changed')
        proof=json.loads(raw)
    except (OSError,UnicodeError,json.JSONDecodeError,NotImplementedError) as error:
        raise WorkflowError('The original runner cleanup artifact is unreadable') from error
    expected={**origin,'schema':1,'kind':'local-process-group-cleanup',
              'host':binding['host'],'process_group':binding['process_group'],'observed_live_processes':0}
    if (not isinstance(proof,dict) or set(proof)!=set(expected)|{'observed_at'} or
            any(type(proof[key]) is not type(value) or proof[key]!=value for key,value in expected.items())):
        raise WorkflowError('Cleanup evidence must identify the exact bound original runner and zero observed live processes')
    at=check_runner_timestamp(proof['observed_at'])
    if not check_runner_timestamp(binding['bound_at'])<=at<=datetime.now(timezone.utc):
        raise WorkflowError('Cleanup observation must follow the original live runner binding')
    return {**reference,'observation':proof}

def reconcile_check(store,payload):
    fields={'task_id','check_id','attempt_id','action'}
    action=payload.get('action') if isinstance(payload,dict) else None
    actions={'inspect':set(),'bind-runner':{'expected_key','expected_definition','process_group'},
             'cancel':{'expected_key','expected_definition','observed','cleanup'}}
    if (not isinstance(action,str) or action not in actions or set(payload)!=fields|actions[action] or
            not valid_id(payload['task_id'],'T') or not valid_id(payload['attempt_id'],'C') or
            not isinstance(payload['check_id'],str) or not re.fullmatch('[a-z][a-z0-9-]*',payload['check_id'])):
        raise WorkflowError('Reconcile check requires an action and exact task, check and attempt identities')
    if action=='inspect':
        state=store.load();run=state['active_run']
        if run:workspaces.ensure_workspace(store,run)
        task,slot,attempt,origin=check_reconciliation_target(store,state,payload,run['id'] if run else None)
        observed,stale=check_drift(store,state,task,payload['check_id'],attempt)
        return {**origin,'observed':observed,'stale':stale,
                'runner_binding':slot.get('runner_bindings',{}).get(attempt['attempt_id'])}
    with store.lock():
        text=store.text();state=store.load(text);run=state['active_run'];run_id=run['id'] if run else None
        if run:workspaces.ensure_workspace(store,run)
        reference='.skill-tree/history/check-reconciliations/'+payload['attempt_id'].lower()+'.json'
        archive=binding_path(store.root,reference)
        request_digest=digest(dump(payload).encode())
        if action=='cancel' and archive.exists():
            if not archive.is_file():raise WorkflowError('Original cancellation archive is invalid')
            try:receipt=json.loads(archive.read_text())
            except (OSError,UnicodeError,json.JSONDecodeError) as error:
                raise WorkflowError('Original cancellation archive is unreadable') from error
            if (not isinstance(receipt,dict) or receipt.get('status')!='cancelled-no-result' or receipt.get('run_id')!=run_id or
                    any(receipt.get(key)!=payload[key] for key in ('task_id','check_id','attempt_id')) or
                    receipt.get('request_digest')!=request_digest):
                raise WorkflowError('Conflicting replay of the original check reconciliation')
            return receipt
        task,slot,attempt,origin=check_reconciliation_target(store,state,payload,run_id)
        if any(payload[key]!=origin[key] for key in ('expected_key','expected_definition')):
            raise WorkflowError('Original prepared check key or definition changed')
        recipe=attempt['recipe']
        if recipe.get('lane') in PRODUCT_LANES or recipe.get('execution_binding'):
            raise WorkflowError('Original runner requires cleanup evidence beyond the local process group')
        group_binding=slot.get('runner_bindings',{}).get(attempt['attempt_id'])
        if action=='bind-runner':
            group=check_runner_group(payload['process_group'])
            if group_binding:
                if group_binding.get('process_group')!=group or group_binding.get('host')!=socket.gethostname():
                    raise WorkflowError('Conflicting binding for the original check runner')
                return group_binding
            _,stale=check_drift(store,state,task,payload['check_id'],attempt)
            if stale:raise WorkflowError('Bind the live original runner before source or check drift')
            host=socket.gethostname()
            for progress in state['task_progress'].values():
                for other in progress['checks'].values():
                    pending=pending_check_attempt(other)
                    if not pending:continue
                    owner_binding=other.get('runner_bindings',{}).get(pending['attempt_id'],{})
                    if owner_binding.get('host')==host and owner_binding.get('process_group')==group:
                        raise WorkflowError('The local runner group already owns another pending attempt')
            try:
                if os.getpgid(group)!=group:raise WorkflowError('The reported process must lead the dedicated runner group')
                os.killpg(group,0)
            except OSError as error:raise WorkflowError('The original local runner group cannot be verified live') from error
            binding={**origin,'host':host,'process_group':group,'bound_at':now()}
            slot.setdefault('runner_bindings',{})[attempt['attempt_id']]=binding
            store.save(text,state,update_navigation=False)
            return binding
        if (not group_binding or any(group_binding.get(key)!=value for key,value in origin.items()) or
                group_binding.get('host')!=socket.gethostname()):
            raise WorkflowError('The original attempt lacks a verified live runner binding on this host')
        observed,stale=check_drift(store,state,task,payload['check_id'],attempt)
        if not stale or observed!=payload['observed']:
            raise WorkflowError('Reconciliation requires the exact current observation of source or check drift')
        group=check_runner_group(group_binding['process_group'])
        cleanup=check_cleanup_evidence(store,payload['cleanup'],origin,group_binding)
        if check_drift(store,state,task,payload['check_id'],attempt)!=(observed,True):
            raise WorkflowError('Source or check drift changed during cleanup verification')
        try:os.killpg(group,0)
        except ProcessLookupError:pass
        except OSError as error:raise WorkflowError('The bound original runner group cleanup is uncertain') from error
        else:raise WorkflowError('The bound original runner group remains live')
        receipt={**origin,'status':'cancelled-no-result','original_attempt':deepcopy(attempt),
                 'runner_binding':deepcopy(group_binding),'observed':observed,'cleanup':cleanup,
                 'request_digest':request_digest,'recorded_at':now()}
        slot.setdefault('receipts',{})[attempt['attempt_id']]=receipt
        store.expect_unchanged(reference,None)
        store.save(text,state,{reference:dump(receipt)},update_navigation=False)
        return receipt

def prepare_check(store,payload):
    with store.lock():
        text=store.text();state=store.load(text);task,check=get_check(store,state,payload);entry=state['task_progress'].get(task['id'])
        if task.get('status')=='Blocked pending answers':processing_helper().guard_implementation_progress(store,task)
        if task.get('completed_contract') and not entry:entry=state['task_progress'].setdefault(task['id'],{'stage':'awaiting-validation','checks':{},'revalidation':True,'admission':state['active_run']['admission'],'run_id':state['active_run']['id']})
        if not entry or entry['stage']=='blocked':raise WorkflowError('Begin implementation before check preparation')
        assert_scope(store,state,parse(text),task['id'])
        slot=entry['checks'].get(check['id'],{})
        if pending_check_attempt(slot):raise WorkflowError('Recover and close the original pending check attempt before preparing another control')
        if state['active_run']:
            target=execution_run(state['active_run']);enforce_limits(target);target['admitted_groups']=admitted_groups(parse(text),target)
        recipe,environment=recipe_for(store,check);execution_session(store,recipe,environment,entry,payload.get('execution'),require_current=True)
        snapshot=check_snapshot(store,task,check,state)
        launch=payload.get('launch')
        if launch:
            required=['assertion','cheaper_evidence_insufficient','authorization','deadline_utc','cleanup_seconds','project_root','execution_profile']
            if not isinstance(launch,dict) or any(not launch.get(key) for key in required):raise WorkflowError('Launch requires concrete assertion, rationale, authorization, exact checkout, deadline and cleanup profile')
            if type(launch['cleanup_seconds']) not in {int,float} or launch['cleanup_seconds']<=0:raise WorkflowError('Launch cleanup reserve must be positive')
            if launch['cheaper_evidence_insufficient'].strip().casefold() in {'run everything to be safe','to be safe','routine checklist'}:raise WorkflowError('Launch requires an assertion-specific rationale')
            expected_root=Path(recipe['execution_context']['execution_root']) if recipe.get('execution_binding') else store.source_root
            if Path(launch['project_root']).resolve()!=expected_root:raise WorkflowError('Launch checkout differs from the covered root')
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
            if delivered.get('status')=='cancelled-no-result':raise WorkflowError('The original check attempt was cancelled without a result')
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
                if state['active_run']:execution_run(state['active_run']).update({'phase':'blocked','stop_task_id':task['id'],'stop_reason':entry['stop_reason'],'next_action':'Resolve the recorded failure before explicit resumption'})
        elif result in {'pass','red'}:entry.pop('unchanged_failure',None)
        if classification=='host-policy-rejection':
            entry['resume_stage']=entry['stage'];entry['stage']='blocked';entry['stop_reason']='Host policy rejected the operation: '+payload.get('reason','missing execution scope')
            if state['active_run']:execution_run(state['active_run']).update({'phase':'blocked','stop_task_id':task['id'],'stop_reason':entry['stop_reason'],'next_action':payload.get('next_action','Report the rejection and missing scope')})
        store.save(text,state);return record

def validate_task_checks(store,tid,state=None,check_id=None):
    state=state or store.load();task=validation_task(store,tid);entry=state['task_progress'].get(tid)
    if not entry or entry['stage'] not in {'implementing','awaiting-validation'}:raise WorkflowError('Task implementation/check progress is missing or blocked')
    assert_admission(store,state,tid)
    for cid,slot in entry['checks'].items():
        if (check_id is None or cid==check_id) and pending_check_attempt(slot):
            raise WorkflowError('Required check has a pending attempt: '+cid)
    records=[]
    for check in check_specs(task):
        if check_id is not None and check['id']!=check_id:continue
        record=entry['checks'].get(check['id'],{}).get('result')
        if not record or record['result']!='pass':raise WorkflowError('Required check pending, failed or unavailable: '+check['id'])
        current=check_snapshot(store,task,check,state)
        if record['key']!=current['key'] or record['definition']!=current['definition']:raise WorkflowError('Required check evidence is stale: '+check['id'])
        for ref in record['evidence']:
            if not ref.get('available') or file_hash(store.source_root/ref['path'])!=ref['sha256']:raise WorkflowError('Required result evidence is unavailable or changed: '+check['id'])
        records.append({'check':check,'result':record,**({'red':entry['checks'][check['id']]['red']} if 'red' in entry['checks'][check['id']] else {})})
    return records

def resume_task(store,payload):
    if not isinstance(payload.get('resolution'),str) or not payload['resolution'].strip():raise WorkflowError('Explicit resumption requires the resolved condition and evidence')
    store.load();admitted=admit_profile(store)
    with store.lock():
        text=store.text();state=store.load(text);entry=state['task_progress'].get(payload['task_id'])
        if not entry or entry['stage']!='blocked':raise WorkflowError('No blocked task progress to resume')
        run=execution_run(state['active_run']) if state['active_run'] else None
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
        if target.get('status')=='Blocked pending answers':processing_helper().guard_implementation_progress(store,target)
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

def export_run(store):
    state=store.load();run=state['active_run']
    if not run or not state.get('run_registry'):raise WorkflowError('Select a registered run before export')
    workspaces.ensure_workspace(store,run)
    paths=sorted((store.base/'history/run-events'/run['id'].lower()).glob('*.json'),key=lambda p:p.stat().st_mtime_ns)
    events=sorted([json.loads(path.read_text()) for path in paths],key=lambda e:e.get('sequence',0))
    package={'schema':1,'queue_id':state['run_registry']['queue_id'],'run_id':run['id'],'events':events,'checkpoint':run,'task_progress':{tid:value for tid,value in state['task_progress'].items() if tid in run['admitted_task_ids']}}
    relative='.skill-tree/run-evidence/'+run['id'].lower()+'/events.json'
    path=store.source_root/relative;path.parent.mkdir(parents=True,exist_ok=True)
    package=workspaces.portable_envelope(package,store.source_root,store.root)
    workspaces.atomic(path,package)
    return {'path':relative,'events':len(events),'queue_id':package['queue_id']}

def replay_events(store,payload):
    # Semantic compare-and-swap deltas preserve unrelated queue entries and outcomes.
    with store.lock():
        text=store.text();state=store.load(text);registry=state.get('run_registry')
        if not registry or payload.get('schema')!=1 or payload.get('queue_id')!=registry['queue_id']:raise WorkflowError('Event replay queue identity mismatch')
        applied=set(registry.get('applied_events',[]));outcomes=store.outcomes();outcome_ids={o['id']:o for o in outcomes}
        for event in payload.get('events',[]):
            if event.get('id') in applied:continue
            locator=workspaces.runtime(store.root);run_path=locator['worktrees'].get(event['run_id']) if locator else None
            if not run_path:raise WorkflowError('Event replay requires an explicitly recovered run worktree locator')
            event=workspaces.restore_envelope(event,run_path,store.root,payload.get('local_paths',{}))
            if event.get('queue_id')!=registry['queue_id'] or event.get('run_id')!=payload.get('run_id'):raise WorkflowError('Event replay run identity mismatch')
            for change in event['changes']:
                matches=[t for t in parse(text) if t['id']==change['task_id']]
                current={'queue':matches[0]['queue'],'body':matches[0]['body']} if matches else None
                if current==change['after']:continue
                if current!=change['before']:raise WorkflowError('Event conflicts with canonical task: '+change['task_id'])
                if matches:text=remove(text,{change['task_id']})
                if change['after']:text=insert(text,change['after']['queue'],change['after']['body'])
            for change in event.get('progress_changes',[]):
                tid=change['task_id'];current_progress=state['task_progress'].get(tid)
                if current_progress==change['after']:continue
                if current_progress!=change['before']:raise WorkflowError('Event validation progress conflict: '+tid)
                if change['after'] is None:state['task_progress'].pop(tid,None)
                else:state['task_progress'][tid]=change['after']
            for outcome in event['outcomes']:
                if any(old['task_id']==outcome['task_id'] and old!=outcome for old in outcomes):raise WorkflowError('Event task already has different terminal evidence')
                if outcome['id'] in outcome_ids and outcome_ids[outcome['id']]!=outcome:raise WorkflowError('Event completion evidence conflict')
                if outcome['id'] not in outcome_ids:outcomes.append(outcome);outcome_ids[outcome['id']]=outcome
            rid=event['run_id'];current=registry['runs'].get(rid)
            if current!=event['checkpoint_after']:
                if current!=event['checkpoint_before']:raise WorkflowError('Event checkpoint conflict; explicit reconciliation required')
                registry['runs'][rid]=event['checkpoint_after']
                if state['active_run'] and state['active_run']['id']==rid:state['active_run']=registry['runs'][rid]
            applied.add(event['id'])
        validate_dependencies(parse(text),{o['task_id'] for o in outcomes if o['disposition']=='completed'})
        registry['applied_events']=sorted(applied)
        ledger=''.join(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n' for o in outcomes)
        store.save(text,state,{'.skill-tree/history/task-outcomes.jsonl':ledger})
        return {'applied_events':len(applied)}



# Hook metadata remains independent of controller selection and Future bootstrap.
HOOK_COMMANDS={'hook-'+name for name in ['start','read','next','prepare','invoke','record','accept','reconcile','resume','pending']}


def hook_helper():
    return owned_module('skill_tree_plugin_invocation',Path(__file__).with_name('plugin-invocation.py'))


def _hook_safe(root,relative):
    helper=hook_helper()
    if not helper.relative(relative):raise WorkflowError('Hook resource paths must remain bounded and repository-relative')
    base=Path(root).resolve();value=base
    for part in relative.split('/'):
        value=value/part
        if value.is_symlink():raise WorkflowError('Hook resource symlinks are unsupported')
    return value


def _hook_source_store(store,source_root):
    # Canonical routing was established before writer-lock entry; scoped reads stay pure.
    result=object.__new__(Store);result.__dict__.update(store.__dict__)
    result.source_root=Path(source_root).resolve();result.neutral=True;result.allow_unselected=True;result.run_id=None;result.selected_run_id=None
    return result


def _hook_controller(store,run_id):
    if not store.future.is_file() or not store.state.is_file():raise WorkflowError('A controller hook requires an existing recorded run')
    state=_hook_source_store(store,store.source_root).load()
    runs=dict(state.get('run_registry',{}).get('runs',{}))
    if state.get('active_run'):runs[state['active_run']['id']]=state['active_run']
    if run_id not in runs and getattr(store,'_hook_readiness',False) and valid_id(run_id,'WR'):
        archived=_hook_safe(store.root,'.skill-tree/history/runs/run-'+run_id.lower()+'.json')
        if archived.is_file():
            receipt=json.loads(archived.read_text());validate_run(receipt)
            if receipt.get('id')==run_id and receipt.get('phase')=='completed' and isinstance(receipt.get('finished_at'),str):
                required=set(receipt['snapshot']+receipt['required_ids']);outcomes=store.outcomes()
                successful={row['task_id'] for row in outcomes if row.get('disposition')=='completed'}
                owned={row['task_id']:row for row in outcomes if row.get('run_id')==run_id}
                actual_completed={tid for tid,row in owned.items() if row.get('disposition')=='completed'}
                references=receipt.get('completion_refs',{})
                if not required.issubset(successful) or set(receipt['completed_ids'])!=actual_completed or not isinstance(references,dict) or references!={tid:row['id'] for tid,row in owned.items()}:raise WorkflowError('The completed controller archive differs from successful original and current-run task outcomes')
                runs[run_id]=receipt
    if run_id not in runs:raise WorkflowError('The hook controller is not an actual recorded run')
    return runs[run_id]


def actual_hook_context(store,value):
    """Bind only selected scope bytes, preserving unrelated queue independence."""
    if not isinstance(value,dict):raise WorkflowError('A typed hook context is required')
    result=deepcopy(value);kind=result.get('kind')
    if kind in {'task','task-group','pending'}:
        key='pending_ids' if kind=='pending' else 'task_ids';ids=result.get(key)
        if not isinstance(ids,list) or not ids:raise WorkflowError('Hook scope requires actual selected identities')
        selected=resolve(parse(store.text()),ids,'Pending Queue' if kind=='pending' else 'Prioritized Next Changes')
        if kind=='pending':
            fingerprints={item['id']:{'semantic_fingerprint':digest(clarification_text_semantics(item['body']).encode()),'content_fingerprint':digest(item['body'].encode())} for item in selected}
        else:
            baselines=clarification_baselines(selected);semantics=clarification_fingerprints(baselines)
            fingerprints={tid:{'semantic_fingerprint':semantics[tid],'content_fingerprint':baseline['content_hash']} for tid,baseline in baselines.items()}
            if set(result.get('pending_ids',[]))-{item for task in selected for item in task['parent_pending_ids']}:raise WorkflowError('Hook Pending provenance differs from actual selected tasks')
        if len(selected)==1:
            result.update(fingerprints[selected[0]['id']])
            if 'body' in result:result['body']=selected[0]['body']
        else:
            result['semantic_fingerprint']=digest(dump({tid:part['semantic_fingerprint'] for tid,part in fingerprints.items()}).encode())
            result['content_fingerprint']=digest(dump({tid:part['content_fingerprint'] for tid,part in fingerprints.items()}).encode())
            if 'body' in result:result['body']={task['id']:task['body'] for task in selected}
        if kind=='task-group' or 'task_fingerprints' in result:result['task_fingerprints']=fingerprints
    elif kind in {'document','snapshot'}:
        paths=result.get('paths');
        if not isinstance(paths,list) or not paths:raise WorkflowError('Document hook context requires bounded paths')
        files={};semantic={};bodies={}
        for relative in paths:
            path=_hook_safe(store.source_root,relative);raw=path.read_bytes() if path.is_file() else None;files[relative]=digest(raw) if raw is not None else None
            if raw is None:semantic[relative]=None
            else:
                try:
                    content=raw.decode('utf-8');semantic[relative]=digest(clarification_text_semantics(content).encode());bodies[relative]=content
                except UnicodeError:semantic[relative]=files[relative]
        result['semantic_fingerprint']=digest(dump(semantic).encode());result['content_fingerprint']=digest(dump(files).encode())
        if 'body' in result:result['body']=bodies
    elif kind=='controller':
        run=_hook_controller(store,result.get('run_id'));admitted=set(run.get('admitted_task_ids',run.get('snapshot',[]))+run.get('required_ids',[]))
        if set(result.get('task_ids',[]))-admitted:raise WorkflowError('Hook scope exceeds the actual controller admission')
        scope={key:run.get(key) for key in ['id','mode','snapshot','root_task_id','admitted_task_ids','required_ids']}
        result['semantic_fingerprint']=digest(dump(scope).encode());result['content_fingerprint']=result['semantic_fingerprint']
    elif kind=='review':
        # The PR bridge supplies the current independently inspected provider snapshot.
        # A typed ledger never replaces ordinary PR head/base/check/authorization gates.
        pass
    elif kind in {'request','project','management'}:
        data={key:item for key,item in result.items() if key not in {'semantic_fingerprint','content_fingerprint'}}
        if kind in {'project','management'}:
            data['owned_profile']=file_hash(store.source_root/'.skill-tree/installation/profile.json')
            if kind=='management':data['registry']=file_hash(store.source_root/'.skill-tree/installation/plugins.json')
        result['semantic_fingerprint']=hook_helper().digest(data);result['content_fingerprint']=result['semantic_fingerprint']
    else:raise WorkflowError('Unknown hook context kind')
    return _hook_context_links(store,result)


def _hook_context_links(store,result):
    kind=result['kind']
    if result.get('orchestration_id'):
        core=owned_module('skill_tree_hook_plan_context',Path(__file__).with_name('decision-orchestration.py')).read(store,result['orchestration_id'])
        if any(result.get(key)!=core['context'].get(key) for key in ['kind','id','task_ids','pending_ids']):raise WorkflowError('The hook plan belongs to another actual selected operation scope')
        result['orchestration_plan_digest']=core['plan']['digest'] if core.get('plan') else None
        result['orchestration_plan_fingerprint']=hook_helper().digest(core['plan']) if core.get('plan') else None
    if result.get('session_id'):
        parent=clarification_read(store,result['session_id'])
        if parent['state']=='cancelled':raise WorkflowError('Cancelled clarification permits only original hook cleanup')
        if set(result.get('task_ids',[]))-set(parent['task_ids']):raise WorkflowError('Hook task scope differs from the linked clarification')
        result['parent_mode_epoch']=parent.get('decision_mode_epoch',0)
        if result.get('question_id') and result.get('purpose')!='confirmation':
            question=parent['questions'].get(result['question_id'])
            if not question:raise WorkflowError('The linked hook question is not current')
            result['question_revision']=question['revision']
    if result.get('run_id') and kind!='controller':
        run=_hook_controller(store,result['run_id'])
        if set(result.get('task_ids',[]))-set(run.get('admitted_task_ids',run.get('snapshot',[]))+run.get('required_ids',[])):raise WorkflowError('Hook tasks exceed the linked controller scope')
    try:return hook_helper().context(result)
    except ValueError as error:raise WorkflowError(str(error)) from error


def _hook_admitted_context(store,value):
    # Completed outcomes retain the exact consumed task bytes for readiness only.
    # Runtime preparation still requires live selected tasks in actual_hook_context.
    if value.get('kind')=='pending':return _hook_admitted_pending_context(store,value)
    if value.get('kind') not in {'task','task-group'}:return actual_hook_context(store,value)
    ids=value['task_ids'];open_tasks={task['id']:task for task in parse(store.text()) if task['queue']=='Prioritized Next Changes'}
    if all(tid in open_tasks for tid in ids):return actual_hook_context(store,value)
    completed={item['task_id']:item for item in store.outcomes() if item.get('disposition')=='completed'}
    selected=[open_tasks[tid] for tid in ids if tid in open_tasks];baselines=clarification_baselines(selected);semantics=clarification_fingerprints(baselines)
    fingerprints={tid:{'semantic_fingerprint':semantics[tid],'content_fingerprint':part['content_hash']} for tid,part in baselines.items()}
    provenance={item for task in selected for item in task['parent_pending_ids']}
    for tid in ids:
        if tid in fingerprints:continue
        outcome=completed.get(tid);part=(outcome or {}).get('task_context')
        if not isinstance(part,dict) or set(part)!={'semantic_fingerprint','content_fingerprint'} or any(not isinstance(item,str) or re.fullmatch('[a-f0-9]{64}',item) is None for item in part.values()):raise WorkflowError('The removed hook task lacks an exact successful completed context: '+tid)
        fingerprints[tid]=deepcopy(part);provenance.update(outcome['parent_pending_ids'])
    if set(value.get('pending_ids',[]))-provenance:raise WorkflowError('Completed hook Pending provenance differs from the preserved task outcomes')
    result=deepcopy(value)
    if len(ids)==1:result.update(fingerprints[ids[0]])
    else:
        for key in ['semantic_fingerprint','content_fingerprint']:result[key]=digest(dump({tid:part[key] for tid,part in fingerprints.items()}).encode())
    if result['kind']=='task-group' or 'task_fingerprints' in result:result['task_fingerprints']=fingerprints
    if 'body' in result:
        bodies={tid:open_tasks[tid]['body'] if tid in open_tasks else result['body'].get(tid) if isinstance(result['body'],dict) else result['body'] for tid in ids}
        if any(not isinstance(body,str) or digest(body.encode())!=fingerprints[tid]['content_fingerprint'] for tid,body in bodies.items()):raise WorkflowError('Completed hook body differs from the exact preserved task outcome')
        result['body']=bodies[ids[0]] if len(ids)==1 else bodies
    return _hook_context_links(store,result)


def _hook_admitted_pending_context(store,value):
    ids=value['pending_ids'];open_tasks={task['id']:task for task in parse(store.text()) if task['queue']=='Pending Queue'}
    if all(pid in open_tasks for pid in ids):return actual_hook_context(store,value)
    if not value.get('run_id'):raise WorkflowError('Consumed Pending hook readiness requires the original linked controller receipt')
    run=_hook_controller(store,value['run_id']);receipts=run.get('processing_results',[]);fingerprints={}
    for pid in ids:
        if pid in open_tasks:
            body=open_tasks[pid]['body'];fingerprints[pid]={'semantic_fingerprint':digest(clarification_text_semantics(body).encode()),'content_fingerprint':digest(body.encode())};continue
        receipt=next((item for item in reversed(receipts) if pid in item.get('selected_ids',[]) and item.get('dispositions',{}).get(pid,{}).get('status') in {'promoted','resolved'}),None)
        part=(receipt or {}).get('pending_contexts',{}).get(pid)
        if not isinstance(part,dict) or set(part)!={'semantic_fingerprint','content_fingerprint'} or any(not isinstance(item,str) or re.fullmatch('[a-f0-9]{64}',item) is None for item in part.values()):raise WorkflowError('The consumed Pending hook lacks an exact successful processing receipt: '+pid)
        fingerprints[pid]=deepcopy(part)
    result=deepcopy(value)
    if len(ids)==1:result.update(fingerprints[ids[0]])
    else:
        for key in ['semantic_fingerprint','content_fingerprint']:result[key]=digest(dump({pid:part[key] for pid,part in fingerprints.items()}).encode())
    if 'task_fingerprints' in result:result['task_fingerprints']=fingerprints
    if 'body' in result:
        bodies={pid:open_tasks[pid]['body'] if pid in open_tasks else result['body'].get(pid) if isinstance(result['body'],dict) else result['body'] for pid in ids}
        if any(not isinstance(body,str) or digest(body.encode())!=fingerprints[pid]['content_fingerprint'] for pid,body in bodies.items()):raise WorkflowError('Consumed Pending hook body differs from the exact processing receipt')
        result['body']=bodies[ids[0]] if len(ids)==1 else bodies
    return _hook_context_links(store,result)


def _hook_locator_path(store,chain_id):
    if not valid_id(chain_id,'HC'):raise WorkflowError('Hook lookup requires an exact HC identity')
    path=_hook_safe(store.root,'.skill-tree/local/hook-locations/'+chain_id.lower()+'.json')
    if path.is_symlink() or path.parent.is_symlink():raise WorkflowError('Private hook locators cannot use symlinks')
    return path


def _hook_locator(store,chain_id):
    path=_hook_locator_path(store,chain_id)
    if not path.is_file():raise WorkflowError('The private hook execution locator is unavailable; explicitly recover the owned location')
    raw=path.read_bytes();value=json.loads(raw)
    if not isinstance(value,dict) or value.get('schema')!=1 or value.get('chain_id')!=chain_id or not isinstance(value.get('watch'),dict):raise WorkflowError('Unsupported private hook locator')
    if any(not isinstance(path,str) or not Path(path).is_absolute() or (expected is not None and (not isinstance(expected,str) or re.fullmatch('[a-f0-9]{64}',expected) is None)) for path,expected in value['watch'].items()):raise WorkflowError('Unsupported private hook resource watchers')
    for key in ['package_root','execution_root']:
        if not isinstance(value.get(key),str) or not Path(value[key]).is_absolute():raise WorkflowError('Private hook locations require actual absolute roots')
    if value.get('canonical_root')!=str(store.root):raise WorkflowError('Hook execution locator belongs to another canonical repository')
    value['_locator_hash']=digest(raw)
    return value


def _hook_inventory_guard(manifest_path):
    """Recheck exact owned file closure using only pinned local metadata."""
    root=manifest_path.parent.parent;manifest=json.loads(manifest_path.read_text())
    if not isinstance(manifest,dict):raise WorkflowError('The frozen hook manifest is invalid')
    inventory=manifest.get('owned_resources');packages=manifest.get('packages')
    if not isinstance(inventory,dict) or not isinstance(packages,dict):raise WorkflowError('The frozen hook resource inventory is unavailable')
    def walk(directory,prefix='',dispatcher=False):
        actual={}
        for path in sorted(directory.iterdir()):
            relative=prefix+path.name
            if dispatcher and (path.name=='__pycache__' or not prefix and path.name=='plugins' or relative=='references/plugin-bindings.json'):continue
            if path.is_symlink():raise WorkflowError('The hook resource inventory contains a symlink')
            if path.is_dir():actual.update(walk(path,relative+'/',dispatcher))
            elif path.is_file():actual[relative]=file_hash(path)
            else:raise WorkflowError('The hook resource inventory contains an unsupported entry')
        return actual
    if walk(root,dispatcher=True)!=inventory:raise WorkflowError('The exact owned hook dispatcher resource closure changed')
    plugin_root=root/'plugins'
    if plugin_root.is_symlink() or plugin_root.exists() and not plugin_root.is_dir():raise WorkflowError('The hook plugin inventory is not an owned directory')
    names=sorted(path.name for path in plugin_root.iterdir()) if plugin_root.exists() else []
    if names!=sorted(packages):raise WorkflowError('The exact owned hook plugin package inventory changed')
    for identity,record in packages.items():
        if not isinstance(record,dict) or not isinstance(record.get('files'),dict):raise WorkflowError('The hook plugin resource inventory is invalid')
        directory=plugin_root/identity
        if directory.is_symlink() or not directory.is_dir():raise WorkflowError('The hook plugin resource inventory changed')
        if walk(directory,'plugins/'+identity+'/')!=record['files']:raise WorkflowError('The exact owned hook plugin resource closure changed')


def _hook_watch(package_root,execution_root):
    package_root=Path(package_root).resolve();manifest_path=_hook_safe(package_root,'references/plugin-bindings.json')
    manifest=json.loads(manifest_path.read_text());watch={str(manifest_path):file_hash(manifest_path)}
    inventory=manifest.get('owned_resources')
    if not isinstance(inventory,dict):raise WorkflowError('The actual owned hook inventory is unavailable')
    for relative,expected in inventory.items():
        path=_hook_safe(package_root,relative)
        if file_hash(path)!=expected:raise WorkflowError('Owned hook bytes changed during preparation')
        watch[str(path)]=expected
    for package in manifest.get('packages',{}).values():
        for relative,expected in package.get('files',{}).items():
            path=_hook_safe(package_root,relative)
            if file_hash(path)!=expected:raise WorkflowError('Pinned plugin bytes changed during preparation')
            watch[str(path)]=expected
    for relative in ['.skill-tree/installation/profile.json','.skill-tree/installation/plugins.json']:
        path=_hook_safe(execution_root,relative);watch[str(path)]=file_hash(path)
    _hook_watch_guard(watch,package_root)
    return watch


def _hook_watch_guard(watch,package_root):
    for value,expected in watch.items():
        path=Path(value)
        if not path.is_absolute() or any(parent.is_symlink() for parent in [path,*path.parents]) or file_hash(path)!=expected:raise WorkflowError('Hook package, profile or configuration changed; explicitly reconcile the frozen invocation')
    manifest=_hook_safe(package_root,'references/plugin-bindings.json')
    expected=watch.get(str(manifest))
    if not isinstance(expected,str) or re.fullmatch('[a-f0-9]{64}',expected) is None:raise WorkflowError('The exact owned operation manifest is missing from the original hook watch')
    _hook_inventory_guard(manifest)


HOOK_MUTABLE_SOURCE_PATHS=(
    '.skill-tree/documents/future.md','.skill-tree/documents/future.json','.skill-tree/skill-tree.json',
    '.skill-tree/invocations','.skill-tree/clarifications','.skill-tree/decisions','.skill-tree/local',
    '.skill-tree/history/checkpoints','.skill-tree/history/runs','.skill-tree/history/run-events',
    '.skill-tree/history/task-outcomes.jsonl','.skill-tree/run-evidence','.skill-tree/artifacts',
    '.skill-tree/.writer-lock','.skill-tree/.transaction.json',
)


def _hook_mutable_source(relative):
    return any(relative==prefix or relative.startswith(prefix+'/') for prefix in HOOK_MUTABLE_SOURCE_PATHS)


def _hook_scope_source_hash(store,relative):
    path=_hook_safe(store.source_root,relative)
    return binding_snapshot(store.source_root,[relative],excluded=list(HOOK_MUTABLE_SOURCE_PATHS)) if path.is_dir() else file_hash(path)


def _hook_scope_sources(store,ctx,original=None):
    if original is not None:
        paths=list(original['input'].get('scope_source_snapshot',{}))
    else:
        paths=deepcopy(ctx.get('source_paths',[]))
        if not isinstance(paths,list):raise WorkflowError('Explicit scoped source files require a bounded path list')
        if ctx['kind'] in {'task','task-group'}:
            selected=resolve(parse(store.text()),ctx['task_ids'],'Prioritized Next Changes')
            paths.extend(relative for task in selected for check in check_specs(task) for relative in check['sources'])
    result={}
    for relative in paths:
        _hook_safe(store.source_root,relative)
        if not _hook_mutable_source(relative):result[relative]=_hook_scope_source_hash(store,relative)
    return result


def _hook_scope_source_guard(store,expected):
    if any(_hook_scope_source_hash(store,relative)!=value for relative,value in expected.items()):raise WorkflowError('The selected invocation source bytes changed during preparation; reconcile or explicitly retry')


def _hook_policy_guard(store,ctx,mode,authority,executor):
    if isinstance(authority,dict) and authority.get('revoked',False):raise WorkflowError('The actual hook owner authority is revoked')
    if ctx.get('orchestration_id'):
        core=owned_module('skill_tree_hook_plan_policy',Path(__file__).with_name('decision-orchestration.py')).read(store,ctx['orchestration_id'])
        if mode!=core['mode'] or authority!=core['authority'] or executor!=core['executor']:raise WorkflowError('Hook mode, authority or executor differs from the actual linked plan orchestration')
    if not ctx.get('session_id'):return
    parent=clarification_read(store,ctx['session_id'])
    if parent['state']=='cancelled' or mode!=clarification_decision_mode(parent):raise WorkflowError('Hook decision mode differs from the current linked clarification')
    if parent.get('decision_authority') is not None and authority!=parent['decision_authority']:raise WorkflowError('Hook authority differs from the actual linked clarification grant')
    if mode=='auto' and executor!=parent.get('decision_executor'):raise WorkflowError('Hook executor differs from the actual linked Auto clarification')


def _hook_node(package_root,request):
    package_root=Path(package_root).absolute();verified=_hook_safe(package_root,'scripts/plugin-hooks.js')
    # Keep the lexical installed destination visible to the owned bootstrap.
    # The actual script closure is verified independently before execution.
    script=package_root/'scripts/plugin-hooks.js'
    if script.resolve()!=verified:raise WorkflowError('The lexical hook entry differs from the verified operation script')
    run=subprocess.run(['node',str(script),'--input','-'],input=json.dumps(request,ensure_ascii=True),capture_output=True,text=True,timeout=30)
    if run.returncode:raise WorkflowError('Owned hook preparation failed: '+(run.stderr.strip().splitlines()[-1] if run.stderr.strip() else 'The owned Node bridge is unavailable'))
    try:return json.loads(run.stdout)
    except ValueError as error:raise WorkflowError('Owned hook preparation returned invalid JSON') from error


def _hook_review_frontier(store,ctx,frontier):
    if not frontier.get('publication_id'):return
    helper=owned_module('skill_tree_review_frontier',Path(__file__).with_name('pr-review-state.py'))
    current=helper.review_phase_guard(store,ctx,frontier['phase'])
    if any(current.get(key)!=frontier.get(key) for key in ['publication_id','publication_hash','phase','core_review_key','core_review_digest']):raise WorkflowError('The actual publication review frontier changed during invocation preparation')


def _hook_resolution_context(ctx,chain,attempt,purpose):
    result=deepcopy(ctx)
    if result.get('session_id'):result['clarification_session_id']=result.pop('session_id')
    result.update(purpose=purpose,hook_chain_id=chain['id'],hook_attempt_id=attempt['id'],hook_result_digest=hook_helper().digest(attempt['result']))
    return result


def _hook_transition(store,chain,attempt,receipt,after):
    if chain['context'].get('session_id'):
        application=processing_helper()
        if application.linked(store,chain['context']):
            if not isinstance(receipt,dict):raise WorkflowError('Use the original registered post-processing contribution')
            return application.verify_contribution(store,chain,attempt,receipt,after)
    helper=hook_helper()
    if not isinstance(receipt,dict):raise WorkflowError('Hook incorporation requires actual ordinary core transition evidence')
    before=chain['context']
    if receipt.get('before')!=helper.digest(before) or receipt.get('after')!=helper.digest(after):raise WorkflowError('Core hook receipt differs from the exact before/after operation context')
    if before.get('kind')=='review' and before.get('publication_id') and attempt.get('result',{}).get('status')=='findings' and (receipt.get('kind')!='core-incorporation' or receipt.get('publication_id')!=before['publication_id']):raise WorkflowError('Publication-bound review findings require actual ordinary publication contribution incorporation evidence')
    if receipt.get('kind')=='core-incorporation' and before.get('kind')=='review' and receipt.get('publication_id'):
        review=owned_module('skill_tree_review_incorporation',Path(__file__).with_name('pr-review-state.py'))
        try:return review.verify_review_contribution(store,chain,attempt,receipt,after)
        except ValueError as error:raise WorkflowError(str(error)) from error
    if receipt.get('kind')=='core-incorporation' and receipt.get('orchestration_id'):
        oid=receipt['orchestration_id']
        if oid!=before.get('orchestration_id') or oid!=after.get('orchestration_id'):raise WorkflowError('Core plan incorporation belongs to another original orchestration')
        core=owned_module('skill_tree_hook_plan_incorporation',Path(__file__).with_name('decision-orchestration.py')).read(store,oid)
        _hook_policy_guard(store,after,chain['mode'],chain['authority'],chain['executor'])
        if any(after.get(key)!=core['context'].get(key) or before.get(key)!=after.get(key) for key in ['kind','id','task_ids','pending_ids','semantic_fingerprint','content_fingerprint']):raise WorkflowError('Core plan incorporation cannot substitute the original actual task scope')
        sequence=receipt.get('plan_sequence');entry=next((item for item in core['history'] if item.get('sequence')==sequence and item.get('event')=='plan'),None)
        previous=(entry or {}).get('detail',{}).get('previous_plan')
        if not isinstance(previous,dict) or previous.get('digest')!=before.get('orchestration_plan_digest') or helper.digest(previous)!=before.get('orchestration_plan_fingerprint'):raise WorkflowError('Core plan incorporation lacks the exact original previous plan event')
        if any(item.get('event')=='plan' and item.get('sequence',0)>sequence for item in core['history']):raise WorkflowError('A later core plan event superseded the incorporation receipt')
        if core['phase']!='plan-review' or not core.get('plan') or core.get('plan_acceptance') is not None or core.get('checks') is not None or core.get('review') is not None:raise WorkflowError('Core plan incorporation requires the actual unaccepted revised draft frontier')
        if helper.digest(previous)==helper.digest(core['plan']):raise WorkflowError('A no-op plan revision cannot resolve hook findings or questions; use a current accepted core resolution')
        if core['plan']['digest']!=after.get('orchestration_plan_digest') or helper.digest(core['plan'])!=after.get('orchestration_plan_fingerprint') or actual_hook_context(store,after)!=after:raise WorkflowError('Core plan incorporation does not bind the exact current revised plan')
        return {**deepcopy(receipt),'reference':'.skill-tree/decisions/'+oid.lower()+'.json','plan_before':deepcopy(previous),'plan_after':deepcopy(core['plan']),'final_confirmation':False}
    if any(before.get(key)!=after.get(key) for key in ['orchestration_id','orchestration_plan_digest','orchestration_plan_fingerprint']):raise WorkflowError('A changed plan requires the exact ordinary core plan incorporation receipt')
    if receipt.get('kind')=='core-incorporation':
        session=clarification_read(store,receipt.get('session_id'));revision=next((item for item in session.get('task_revisions',[]) if item.get('id')==receipt.get('task_revision_id')),None)
        if not revision:raise WorkflowError('The actual guarded clarification revision is unavailable')
        ids=before.get('task_ids',[])
        if not ids or set(revision['task_ids'])-set(ids):raise WorkflowError('Core incorporation changes another hook task scope')
        if before.get('session_id') and before['session_id']!=session['id']:raise WorkflowError('Core incorporation belongs to another clarification session')
        fingerprints=revision.get('task_fingerprints',{})
        for tid in ids:
            if tid not in fingerprints:raise WorkflowError('Core task revision lacks exact selected-task fingerprints')
        changed=[tid for tid in revision['task_ids'] if tid in ids and fingerprints[tid]['before']!=fingerprints[tid]['after']]
        if not changed or not any(revision.get('changed_fields',{}).get(tid) or tid in revision.get('content_changed_task_ids',[]) for tid in changed):raise WorkflowError('A no-op task revision cannot resolve hook findings or questions; use a current accepted core resolution')
        old=fingerprints[ids[0]]['before'] if len(ids)==1 else {'semantic_fingerprint':digest(dump({tid:fingerprints[tid]['before']['semantic_fingerprint'] for tid in ids}).encode()),'content_fingerprint':digest(dump({tid:fingerprints[tid]['before']['content_fingerprint'] for tid in ids}).encode())}
        new=fingerprints[ids[0]]['after'] if len(ids)==1 else {'semantic_fingerprint':digest(dump({tid:fingerprints[tid]['after']['semantic_fingerprint'] for tid in ids}).encode()),'content_fingerprint':digest(dump({tid:fingerprints[tid]['after']['content_fingerprint'] for tid in ids}).encode())}
        if any(before.get(key)!=old[key] or after.get(key)!=new[key] for key in ['semantic_fingerprint','content_fingerprint']):raise WorkflowError('The actual core revision does not bind the original task and current incorporated bytes')
        if actual_hook_context(store,after)!=after:raise WorkflowError('The incorporated hook task context is no longer current')
        for key in ['source_before','source_after']:
            if key in receipt and receipt[key]!=revision[key]:raise WorkflowError('The supplied core revision source receipt differs')
        return {**deepcopy(receipt),'reference':'.skill-tree/clarifications/'+session['id'].lower()+'.json','source_before':revision['source_before'],'source_after':revision['source_after'],'final_confirmation':False}
    if receipt.get('kind')=='core-resolution':
        decisions=decision_helper();expected=_hook_resolution_context(after,chain,attempt,'hook-result-resolution');reference=receipt.get('decision_receipt')
        accepted=decisions.acceptance_reference(store,reference,{'context':expected,'mode':chain['mode'],'kind':'technical','authority_digest':decisions._hash(chain['authority'])})
        if accepted['answer'] not in {'accept','resolve','dismiss'}:raise WorkflowError('The current core decision did not resolve the hook contribution')
        return {**deepcopy(receipt),'reference':'.skill-tree/decisions/'+reference['decision_id'].lower()+'.json','decision_receipt':reference}
    raise WorkflowError('An unsupported core receipt cannot satisfy a hook result')


def _hook_supersession(store,old,new,receipt):
    if not isinstance(receipt,dict):raise WorkflowError('Hook configuration adoption requires an actual current core decision')
    decisions=decision_helper();ctx=deepcopy(new['context'])
    if ctx.get('session_id'):ctx['clarification_session_id']=ctx.pop('session_id')
    ctx.update(purpose='hook-configuration-adoption',hook_chain_id=old['id'],before_configuration_digest=old['configuration']['configuration_digest'],after_configuration_digest=new['configuration']['configuration_digest'])
    reference=receipt.get('decision_receipt');accepted=decisions.acceptance_reference(store,reference,{'context':ctx,'mode':new.get('mode','auto'),'kind':'technical','authority_digest':decisions._hash(new['authority'])})
    if accepted['answer']!='adopt':raise WorkflowError('The current core decision did not adopt the replacement configuration')
    return {'kind':'configuration-adoption','reference':'.skill-tree/decisions/'+reference['decision_id'].lower()+'.json','decision_receipt':reference,'before_configuration_digest':old['configuration']['configuration_digest'],'after_configuration_digest':new['configuration']['configuration_digest']}


def _hook_register(store,writes,ctx,chain_id):
    if not ctx.get('run_id'):return
    registration=_hook_source_store(store,store.source_root);registration.run_id=ctx['run_id'];registration.selected_run_id=ctx['run_id'];state=registration.load()
    run=state.get('run_registry',{}).get('runs',{}).get(ctx['run_id']) or state.get('active_run')
    if not run or run['id']!=ctx['run_id']:raise WorkflowError('The hook controller registration is not current')
    state['active_run']=workspaces.register_hook_reference(run,chain_id,ctx.get('task_ids',[]));persisted=workspaces.persist(registration,state)
    registration.record_run_event(registration.text(),persisted,writes);writes['.skill-tree/documents/future.json']=dump(persisted)


def hook_action(store,command,payload,*,private_delivery_provider=None,private_delivery_sink=None):
    if not isinstance(payload,dict):raise WorkflowError('Hook operations require a structured payload')
    if any(key in payload for key in ['private_delivery_provider','private_delivery_sink']):raise WorkflowError('Private delivery callbacks are trusted in-process callables, never JSON input')
    if any(value is not None and not callable(value) for value in [private_delivery_provider,private_delivery_sink]):raise WorkflowError('Private delivery callbacks require actual in-process callables')
    if command!='hook-invoke' and any(value is not None for value in [private_delivery_provider,private_delivery_sink]):raise WorkflowError('Private delivery callbacks apply only to the original invocation dispatch')
    try:return _hook_action(store,command,payload,private_delivery_provider=private_delivery_provider,private_delivery_sink=private_delivery_sink)
    except WorkflowError:raise
    except ValueError as error:raise WorkflowError(str(error)) from error


def _hook_action(store,command,payload,*,private_delivery_provider=None,private_delivery_sink=None):
    helper=hook_helper();cmd=command.removeprefix('hook-')
    if command not in HOOK_COMMANDS:raise WorkflowError('Unknown hook operation')
    if cmd=='read':return helper.read(store,payload.get('chain_id'))
    if cmd=='pending':return helper.pending_scan(store)
    frame=None if cmd=='start' else helper.read(store,payload.get('chain_id'))
    cleanup=cmd=='reconcile';locator=None
    if frame is not None and not cleanup:
        locator=_hook_locator(store,frame['id'])
    if cleanup:
        class CleanupStore:
            def __getattr__(self,key):return getattr(store,key)
            @contextmanager
            def lock(self):
                with store.lock():
                    if payload.get('expected_source_hash') is not None and store.future.exists():store.guard(payload['expected_source_hash'])
                    yield
        return helper.mutate(CleanupStore(),'reconcile',payload)
    business=cmd in {'prepare','invoke','record','accept'}
    if locator is not None and business:_hook_watch_guard(locator['watch'],locator['package_root'])
    execution_root=Path(locator['execution_root']) if locator else store.source_root
    effective=Store(execution_root,allow_unselected=True,neutral=True)
    if effective.root!=store.root:raise WorkflowError('Hook execution belongs to another canonical queue')
    package_root=Path(payload.get('package_root') or (locator or {}).get('package_root') or Path(__file__).parent.parent).absolute()
    ctx=deepcopy(payload.get('context',frame['context'] if frame else None))
    if not isinstance(ctx,dict):raise WorkflowError('A typed current hook context is required')
    orchestration_id=payload.get('orchestration_id') or (locator or {}).get('orchestration_id') or ctx.get('orchestration_id')
    if orchestration_id:ctx['orchestration_id']=orchestration_id
    if frame is None and ctx.get('kind')=='review' and payload.get('publication_id'):ctx['publication_id']=payload['publication_id']
    application=processing_helper() if ctx.get('session_id') or 'processing_recheck_id' in ctx or 'processing_recheck_digest' in ctx else None
    session=application.linked(effective,ctx) if application else None
    if session:application.guard_package(effective,session,package_root)
    completed_processing=bool(session and frame and frame['state']=='complete' and cmd=='next')
    ctx=application.readiness_context(effective,session,frame) if completed_processing else actual_hook_context(effective,ctx)
    if session and frame and not completed_processing:application.check_live(session,frame,ctx)
    run_locator=None
    if ctx.get('run_id'):
        selected=Store(execution_root,ctx['run_id']);selected.load()
        if selected.source_root!=execution_root:raise WorkflowError('Hook execution must use the actual linked controller worktree')
        run_locator=workspaces.runtime_file(effective.root)
    ev=payload.get('event') if frame is None else frame['event'];configuration=frame['configuration'] if frame else None
    request={'runtime_action':'freeze-chain' if frame is None else 'readiness-plan' if cmd=='next' and frame['state']=='complete' else 'occurrence-plan','project_root':str(execution_root),'event':ev,'context':ctx,'capabilities':deepcopy(payload.get('capabilities',(locator or {}).get('capabilities',[]))),'adapter':deepcopy(payload.get('adapter',(locator or {}).get('adapter',{'provider':'codex','mechanism':'source-backed-context'})))}
    if orchestration_id:request['orchestration_id']=orchestration_id
    if frame is None:
        frozen=session['processing_requirements']['configuration'] if session else {}
        request['run_overrides']=deepcopy(payload.get('run_overrides',frozen.get('run_overrides',{})))
        if 'execution_policy' in payload or 'execution_policy' in frozen:request['execution_policy']=deepcopy(payload.get('execution_policy',frozen.get('execution_policy')))
        if session:
            request['capabilities']=deepcopy(payload.get('capabilities',session['processing_requirements']['capabilities']))
            request['adapter']=deepcopy(payload.get('adapter',session['processing_requirements']['adapter']))
    else:request['configuration']=configuration
    prepared=_hook_node(package_root,request);proof=prepared['proof'] if frame is None else prepared
    if session and frame:application.check_snapshot(session,proof['execution_snapshot'])
    if frame is None:
        if proof['event'].get('boundary_id')==processing_helper().BOUNDARY:processing_scope_guard(effective,ctx,package_root=package_root)
        configuration=prepared['configuration']
        if session:application.check_start(effective,session,ctx,proof['event'],configuration,proof['execution_snapshot'],payload)
        request_id=payload.get('request_id');existing=False
        if isinstance(request_id,str) and request_id.strip():
            original_id='HC-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-tree-invocation:'+request_id))
            existing=helper.location(store,original_id).exists()
        candidate={'configuration':configuration,'state':'active','cursor':0,'prepared_attempt_id':None,'attempts':{}}
        if not session and not proof.get('bindings') and not proof.get('unresolved') and not helper.applicable_prerequisites(candidate,proof) and not payload.get('supersedes_chain_id') and not existing:
            return {'status':'noop','state':'complete','bindings':[]}
    original_source=frame['attempts'].get(payload.get('attempt_id') or frame.get('prepared_attempt_id')) if frame is not None and cmd in {'invoke','record','accept','next'} else None
    scoped_sources=_hook_scope_sources(effective,ctx,original_source)
    proof['scope_source_snapshot']=scoped_sources
    normalized={key:deepcopy(value) for key,value in payload.items() if key not in {'proof','private_secrets','package_root'}};normalized['context']=ctx
    if frame is None:normalized.update(configuration=configuration,event=proof['event'])
    if ctx.get('orchestration_id') and frame is None:
        core=owned_module('skill_tree_hook_plan_defaults',Path(__file__).with_name('decision-orchestration.py')).read(effective,ctx['orchestration_id'])
        for key in ['mode','authority','executor']:normalized.setdefault(key,core[key])
    if ctx.get('session_id') and frame is None:
        parent=clarification_read(effective,ctx['session_id']);normalized.setdefault('mode',clarification_decision_mode(parent))
        if parent.get('decision_authority') is not None:normalized.setdefault('authority',parent['decision_authority'])
        if parent.get('decision_executor') is not None:normalized.setdefault('executor',parent['decision_executor'])
    watch=_hook_watch(package_root,execution_root)
    if run_locator is not None:watch[str(run_locator.resolve())]=file_hash(run_locator)
    if locator is not None and business:
        if watch!=locator['watch']:raise WorkflowError('The frozen hook resource watch changed; explicitly reconcile and resume before adopting a new baseline')
        watch=deepcopy(locator['watch'])
    if session and business and cmd in {'accept','record'}:
        original=frame['attempts'].get(payload.get('attempt_id'))
        result=payload.get('result') if cmd=='record' else (original or {}).get('result')
        if original and isinstance(result,dict) and result.get('status') in {'passed','findings','questions'}:
            questions,_=application._question_specs(session,{**original,'result':result})
            clarification_questions(deepcopy(session),questions)
    mode=normalized.get('mode',frame['mode'] if frame else 'auto');grant=normalized.get('authority',frame['authority'] if frame else None);executor=normalized.get('executor',frame['executor'] if frame else None)
    if session and not completed_processing and cmd!='next':
        _hook_policy_guard(effective,ctx,mode,grant,executor)
        if session.get('decision_executor') is not None and executor!=session['decision_executor']:
            raise WorkflowError('Post-processing requires the frozen clarification executor')
        if frame and business and frame['context'].get('parent_mode_epoch')!=ctx.get('parent_mode_epoch'):
            raise WorkflowError('Explicitly resume under the current post-processing policy before using an old result')
    if 'processing_recheck_id' in ctx or 'processing_recheck_digest' in ctx:
        if processing_recheck_guard(effective,ctx,proof['event'],readiness=completed_processing)!=(proof.get('guard') or {}).get('processing_recheck'):
            raise WorkflowError('The current owned processing recheck differs from preparation')
    if business:
        helper.guards(frame,normalized)
        helper.proof_check(frame,proof,context_value=ctx if cmd=='accept' else None);helper.require_business_admission(frame,proof)
        _hook_review_frontier(effective,ctx,proof.get('guard') or {})
    if cmd=='invoke':
        if session and (application.linked(effective,ctx)['session_hash']!=session['session_hash'] or actual_hook_context(effective,ctx)!=ctx):
            raise WorkflowError('The owned post-processing scope changed before private delivery')
        original=frame['attempts'].get(payload.get('attempt_id'))
        if not original or payload.get('input_digest')!=original['input_digest']:raise WorkflowError('Hook dispatch does not match the original attempt input')
        if original['id']!=frame['prepared_attempt_id'] or original['status']!='prepared':raise WorkflowError('Only the original prepared attempt can begin invocation')
        helper.attempt_sources(original,proof);helper.review_frontier(original,proof)
        private_request={**request,'package_root':str(package_root),'runtime_action':'delivery-data','chain_id':frame['id'],'attempt_id':original['id'],'binding_id':original['binding_id'],'public_input':original['input'],'input_digest':original['input_digest'],'mode':frame['mode'],'authority':frame['authority']}
        if 'private_secrets' in payload:private_request['private_secrets']=payload['private_secrets']
        if private_delivery_provider is None:delivery=_hook_node(package_root,private_request)
        else:
            try:delivery=private_delivery_provider(deepcopy(private_request))
            except Exception as error:raise WorkflowError('The trusted private delivery provider is unavailable') from error
        if not isinstance(delivery,dict) or not isinstance(delivery.get('payload'),dict):raise WorkflowError('The trusted private provider must return the exact owned Node delivery envelope')
        private_input=delivery['payload']
        for key,expected in {'chain_id':frame['id'],'attempt_id':original['id'],'binding_id':original['binding_id'],'context':ctx,'event':proof['event'],'input_digest':original['input_digest'],'mode':frame['mode'],'authority':frame['authority']}.items():
            if private_input.get(key)!=expected:raise WorkflowError('The trusted private delivery differs from the original current invocation')
        if private_input.get('invocation_policy')!=original['input'].get('invocation_policy'):raise WorkflowError('Private delivery differs from the sealed immutable invocation policy')
        if private_input.get('processing_application')!=original['input'].get('processing_application'):raise WorkflowError('Private delivery differs from the sealed processing application policy')
        for key in ['allowed_tools','allowed_actions']:
            if private_input.get(key)!=original['input'].get('execution_policy',{}).get(key):raise WorkflowError('Private delivery tools or actions differ from the original sealed execution policy')
        proof['delivery']={key:delivery[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
        if 'dispatch_identity' in delivery:proof['delivery']['dispatch_identity']=delivery['dispatch_identity']
    chain_id=frame['id'] if frame else 'HC-'+str(uuid.uuid5(uuid.NAMESPACE_URL,'skill-tree-invocation:'+normalized.get('request_id','')))
    private_path=_hook_locator_path(effective,chain_id);private_expected=locator['_locator_hash'] if locator else file_hash(private_path)
    private={'schema':1,'chain_id':chain_id,'canonical_root':str(effective.root),'package_root':str(package_root),'execution_root':str(execution_root),'watch':watch,'capabilities':request['capabilities'],'adapter':request['adapter'],'orchestration_id':orchestration_id}
    def guard(current,operation,values):
        _hook_watch_guard(watch,package_root)
        if business:
            _hook_watch_guard(locator['watch'],locator['package_root']);_hook_scope_source_guard(effective,scoped_sources)
            helper.proof_check(current,proof,context_value=ctx if cmd=='accept' else None);helper.require_business_admission(current,proof)
        if effective.future.exists():
            if not normalized.get('expected_source_hash'):raise WorkflowError('Hook mutation requires the inspected existing queue source hash')
            effective.guard(normalized['expected_source_hash'])
        elif normalized.get('expected_source_hash') is not None:raise WorkflowError('Hook queue context changed; reread before mutation')
        if actual_hook_context(effective,ctx)!=ctx:raise WorkflowError('The actual selected hook scope changed during preparation')
        frontier=proof.get('guard') or {}
        if (frame is None or business) and proof['event'].get('boundary_id')==processing_helper().BOUNDARY:processing_scope_guard(effective,ctx,package_root=package_root)
        if session:
            latest=application.linked(effective,ctx)
            application.guard_package(effective,latest,package_root)
            if latest['session_hash']!=session['session_hash']:raise WorkflowError('Post-processing clarification changed during invocation preparation')
            if frame is None:application.check_start(effective,latest,ctx,proof['event'],configuration,proof['execution_snapshot'],normalized)
            else:
                application.check_live(latest,frame,ctx)
                application.check_snapshot(latest,proof['execution_snapshot'])
        if 'processing_recheck_id' in ctx or 'processing_recheck_digest' in ctx:
            if processing_recheck_guard(effective,ctx,proof['event'])!=frontier.get('processing_recheck'):raise WorkflowError('The owned processing recheck guard changed before commit')
        _hook_review_frontier(effective,ctx,frontier)
        if frontier.get('orchestration_id'):
            core=owned_module('skill_tree_hook_orchestration_guard',Path(__file__).with_name('decision-orchestration.py')).read(effective,frontier['orchestration_id'])
            if core['orchestration_hash']!=frontier.get('orchestration_hash') or core['phase']!='plan-review' or not core['plan'] or core['plan']['digest']!=frontier.get('plan_digest') or core['plan_acceptance'] is not None:raise WorkflowError('The current draft-plan frontier changed during hook preparation')
        _hook_policy_guard(effective,ctx,mode,grant,executor)
    class BoundStore:
        def __getattr__(self,key):return getattr(effective,key)
        @contextmanager
        def lock(self):
            with effective.lock():guard(frame or {},cmd,normalized);yield
        def commit(self,writes):
            guard(frame or {},cmd,normalized);merged=dict(writes)
            relative_path=private_path.relative_to(effective.root).as_posix();effective.expect_unchanged(relative_path,private_expected);merged[relative_path]=json.dumps(private,sort_keys=True,ensure_ascii=True,indent=2)+'\n'
            if frame is None:
                _hook_register(effective,merged,ctx,chain_id)
                if session:application.register_chain(effective,merged,deepcopy(session),ctx,chain_id,grant,executor)
            effective.commit(merged)
    bound=BoundStore()
    if cmd=='next':
        try:
            _hook_watch_guard(locator['watch'],locator['package_root'])
            if not completed_processing:_hook_policy_guard(effective,ctx,mode,grant,executor)
        except WorkflowError as error:return {'chain_id':frame['id'],'state':frame['state'],'cursor':frame['cursor'],'action':'prerequisite','prerequisites':[{'code':'current-hook-inputs','reason':str(error)}]}
        return helper.next_action(bound,frame['id'],proof=proof)
    if frame is None:return helper.start(bound,normalized,proof=proof,verify_supersession=lambda old,new,receipt:_hook_supersession(effective,old,new,receipt),guard=guard)
    result=helper.mutate(bound,cmd,normalized,proof=proof,verify_transition=lambda chain,attempt,receipt,after:_hook_transition(effective,chain,attempt,receipt,after),guard=guard)
    if cmd=='invoke' and private_delivery_sink is not None:
        try:private_delivery_sink(deepcopy(delivery['payload']))
        except Exception as error:raise WorkflowError('The private delivery sink failed; reconcile the original invocation before retrying') from error
    return result


def hook_pending_admission(store,scope=None):
    try:return _hook_pending_admission(store,scope)
    except WorkflowError:raise
    except ValueError as error:raise WorkflowError(str(error)) from error


def _hook_pending_admission(store,scope=None):
    helper=hook_helper()
    for pending in helper.pending_scan(store):
        frame=helper.read(store,pending['chain_id'])
        if _hook_scope_matches(frame,scope):raise WorkflowError('Reconcile the original pending hook attempt before cancelling the selected task: '+pending['attempt_id'])


def _hook_scope_matches(chain,scope):
    if scope is None:return True
    if isinstance(scope,str):return scope in chain['context'].get('task_ids',[]) or scope in chain['context'].get('pending_ids',[])
    if not isinstance(scope,dict):raise WorkflowError('Hook admission requires an exact scope')
    if scope.get('kind') and scope['kind']!=chain['context']['kind']:return False
    for key in ['task_ids','pending_ids']:
        if key in scope:return bool(set(scope[key])&set(chain['context'].get(key,[])))
    return scope.get('id')==chain['context']['id']


def _hook_admission_key(scope,chain_ids):
    return hook_helper().digest({'scope':scope,'selection':'scope' if chain_ids is None else 'references'})


def _hook_admission_selection(store,scope,chain_ids):
    helper=hook_helper();directory=store.base/'invocations'
    if chain_ids is None:
        if not directory.exists():return []
        if not directory.is_dir():raise WorkflowError('Owned hook metadata requires recovery')
        selected=[]
        for path in sorted(directory.glob('*.json')):
            value='HC-'+path.stem[3:]
            if not valid_id(value,'HC'):raise WorkflowError('Unrecognized hook metadata requires recovery')
            frame=helper.read(store,value)
            if _hook_scope_matches(frame,scope) and not (frame['context'].get('session_id') and processing_helper().retired_chain(store,frame)):
                selected.append(value)
    else:
        if not isinstance(chain_ids,list) or len(chain_ids)!=len(set(chain_ids)) or any(not valid_id(item,'HC') for item in chain_ids):raise WorkflowError('Hook admission requires distinct exact chain references')
        selected=list(chain_ids)
    result=[]
    for original in selected:
        initial=helper.read(store,original)
        if initial['context'].get('session_id') and processing_helper().retired_chain(store,initial):continue
        current=original;seen=set();lineage=[]
        while True:
            if current in seen:raise WorkflowError('Hook replacement lineage contains a cycle')
            seen.add(current);frame=helper.read(store,current)
            lineage.append({'id':current,'chain_hash':frame['chain_hash'],'revision':frame['revision']})
            if frame['state']!='superseded':break
            current=frame['superseded_by']
        if scope is not None and not _hook_scope_matches(frame,scope):raise WorkflowError('A referenced hook belongs to another selected scope')
        result.append({'original':original,'chain_id':current,'lineage':lineage})
    return result


def _hook_admission_inputs(store,item,scope):
    helper=hook_helper();frame=helper.read(store,item['chain_id'])
    if frame['state']!='complete':raise WorkflowError('An existing required hook chain remains unfinished: '+frame['id'])
    location=_hook_locator(store,frame['id']);execution=_hook_source_store(store,location['execution_root']);execution._hook_readiness=True;_hook_watch_guard(location['watch'],location['package_root'])
    application=processing_helper() if frame['context'].get('session_id') else None
    session=application.linked(execution,frame['context']) if application else None
    if session:
        actual=application.readiness_context(execution,session,frame)
    else:
        actual=deepcopy(scope) if isinstance(scope,dict) and scope.get('kind')=='review' else _hook_admitted_context(execution,frame['context'])
        if actual!=frame['context']:raise WorkflowError('The completed hook result is stale for the actual current scope')
        _hook_policy_guard(execution,actual,frame['mode'],frame['authority'],frame['executor'])
    if frame['stages'] and frame['stages'][-1].get('accepted_context')!=actual:raise WorkflowError('The final hook stage does not bind the current accepted context')
    identity={'chain_hash':frame['chain_hash'],'revision':frame['revision'],'locator_hash':location['_locator_hash'],
        'context':actual,'watch':location['watch'],'execution_root':location['execution_root']}
    if session:identity['processing_session_hash']=session['session_hash']
    return frame,location,identity


def prepare_hook_admission(store,scope=None,chain_ids=None):
    """Prepare trusted current readiness outside the writer; retain no second ledger."""
    helper=hook_helper();selection=_hook_admission_selection(store,scope,chain_ids);entries={}
    if selection and (getattr(store,'_writer_active',False) or (store.base/'.writer-lock').exists()):raise WorkflowError('Hook readiness preflight must run outside the metadata writer scope')
    for item in selection:
        frame,location,identity=_hook_admission_inputs(store,item,scope)
        if frame['configuration']['bindings']:
            request={'runtime_action':'readiness-plan','project_root':location['execution_root'],'configuration':frame['configuration'],
                'event':frame['event'],'context':identity['context'],'capabilities':location.get('capabilities',[]),
                'adapter':location.get('adapter',{'provider':'codex','mechanism':'source-backed-context'})}
            proof=_hook_node(Path(location['package_root']),request)
        else:
            proof={'proof_kind':'completed-readiness','configuration_digest':frame['configuration']['configuration_digest'],
                'event':frame['event'],'context':identity['context'],'execution_snapshot':frame['execution_snapshot'],
                'bindings':[],'prerequisites':[],'unresolved':[]}
        if proof.get('proof_kind')!='completed-readiness':raise WorkflowError('The owned completed-readiness proof is unavailable')
        helper.proof_check(frame,proof,allow_readiness=True);helper.require_business_admission(frame,proof)
        entries[frame['id']]={'identity':deepcopy(identity),'proof':deepcopy(proof)}
    key=_hook_admission_key(scope,chain_ids);cache=getattr(store,'_hook_preflights',{})
    cache[key]={'selection':deepcopy(selection),'entries':entries};store._hook_preflights=cache
    return {'chain_ids':[item['chain_id'] for item in selection]}


def hook_admission(store,scope=None,chain_ids=None):
    try:
        if not getattr(store,'_writer_active',False):prepare_hook_admission(store,scope,chain_ids)
        return _hook_admission(store,scope,chain_ids)
    except WorkflowError:raise
    except ValueError as error:raise WorkflowError(str(error)) from error


def _hook_admission(store,scope=None,chain_ids=None,*,register=True,navigation_followup=False):
    helper=hook_helper();selection=_hook_admission_selection(store,scope,chain_ids)
    key=_hook_admission_key(scope,chain_ids);cached=getattr(store,'_hook_preflights',{}).get(key)
    if cached is None:
        if selection:raise WorkflowError('Current hook readiness preflight is missing for the selected chain identity')
        # Empty scope needs no Node tool. Retain the observed absence so a newly
        # matching obligation cannot appear before the same writer commits.
        cached={'selection':[],'entries':{}}
        cache=getattr(store,'_hook_preflights',{});cache[key]=cached;store._hook_preflights=cache
    if cached['selection']!=selection:raise WorkflowError('The selected hook chain identity changed after current readiness preflight')
    for item in selection:
        if navigation_followup:
            # The exact navigation-only follow-up cannot re-authorize business or
            # reconstruct a scope consumed by the preceding guarded atomic save.
            frame=helper.read(store,item['chain_id']);location=_hook_locator(store,frame['id']);_hook_watch_guard(location['watch'],location['package_root'])
            identity={'chain_hash':frame['chain_hash'],'revision':frame['revision'],'locator_hash':location['_locator_hash'],
                'context':frame['context'],'watch':location['watch'],'execution_root':location['execution_root']}
            if frame['context'].get('session_id'):
                session=processing_helper().linked(store,frame['context'])
                if session:identity['processing_session_hash']=session['session_hash']
        else:frame,location,identity=_hook_admission_inputs(store,item,scope)
        entry=cached['entries'].get(frame['id'])
        if entry is None or entry['identity']!=identity:raise WorkflowError('Current hook readiness identity changed after preflight')
        helper.proof_check(frame,entry['proof'],allow_readiness=True);helper.require_business_admission(frame,entry['proof'])
    if register and getattr(store,'_writer_active',False):
        reference={'scope':deepcopy(scope),'chain_ids':deepcopy(chain_ids)}
        if reference not in store._hook_active_admissions:store._hook_active_admissions.append(reference)


# Clarification state is independent of implementation run selection and admission.
CLARIFICATION_STATES={'researching','awaiting-answers','revising','awaiting-confirmation','complete','blocked','cancelled'}
CLARIFICATION_FIELDS={'title','goal','scope','exclusions','dependencies','acceptance','validation','required_plugin_policy','content'}
DECISION_COMMANDS={'decision-start','decision-read','decision-prepare','decision-record','decision-reconcile','decision-switch','decision-accept','decision-resume'}
ORCHESTRATION_COMMANDS={'orchestration-'+command for command in ['start','read','next','question','prepare-actor','record-actor','reconcile-actor','switch-mode','accept-decision','research','plan','accept-plan','implement','checks','review','resolve','fix','resume','observe-failure']}

def orchestration_execution_snapshot(store):
    scripts=Path(__file__).parent;references=scripts.parent/'references'
    paths={'common/scripts/'+name:scripts/name for name in ['workflow-state.py','decision-governance.py','decision-orchestration.py','run-workspaces.py','validate-document-rules.py']}
    paths.update({'common/references/'+name:references/name for name in ['decision-governance.md','validation-policy.md']})
    paths['owned-profile']=store.source_root/'.skill-tree/installation/profile.json'
    if any(path.is_symlink() for path in paths.values()):raise WorkflowError('Execution snapshot cannot adopt symlinked core inputs')
    return {key:file_hash(path) for key,path in paths.items()}

def orchestration_action(store,command,payload):
    helper=owned_module('skill_tree_decision_orchestration',Path(__file__).with_name('decision-orchestration.py'))
    try:
        if command=='orchestration-read':return helper.read(store,payload.get('orchestration_id'))
        frame=None if command=='orchestration-start' else helper.read(store,payload.get('orchestration_id'))
        current_snapshot=orchestration_execution_snapshot(store)
        if frame is None or command=='orchestration-resume':
            if 'execution_snapshot' in payload and payload['execution_snapshot']!=current_snapshot:raise WorkflowError('Orchestration execution snapshot differs from the actual current bundle/profile')
            payload={**payload,'execution_snapshot':current_snapshot}
        elif command!='orchestration-reconcile-actor' and frame.get('execution_snapshot')!=current_snapshot:raise WorkflowError('Core bundle/profile changed; reconcile original actors and explicitly resume the same orchestration')
        payload={key:value for key,value in payload.items() if key!='parent_policy_reconciliation'}
        context=payload.get('context') if frame is None else payload.get('context',frame['context']) if command=='orchestration-resume' else frame['context']
        if frame is not None and command=='orchestration-resume' and frame['context'].get('session_id'):
            parent=clarification_read(store,frame['context']['session_id'])
            current=clarification_decision_context(parent,frame['context'].get('purpose'),frame['context'].get('question_id') if frame['context'].get('purpose')=='answer' else None)
            if context!=current:raise WorkflowError('Resume requires the exact current parent clarification context')
            old_epoch=frame['context'].get('parent_mode_epoch',0);new_epoch=parent.get('decision_mode_epoch',0)
            if new_epoch!=old_epoch:
                stable=lambda value:{key:item for key,item in value.items() if key not in {'parent_mode_epoch','semantic_fingerprint','content_fingerprint'}}
                if stable(frame['context'])!=stable(current):raise WorkflowError('Parent-policy resume cannot substitute another session, task, question or purpose')
                previous={'decision_mode':frame['mode'],'decision_authority':frame['authority'],'decision_executor':frame['executor']}
                switches=[entry for entry in parent.get('decision_mode_history',[]) if entry.get('previous_epoch',-1)>=old_epoch]
                if new_epoch<=old_epoch or not switches or switches[0].get('previous_epoch')!=old_epoch or switches[0].get('previous_policy')!=previous or [entry.get('previous_epoch') for entry in switches]!=list(range(old_epoch,new_epoch)):raise WorkflowError('Parent policy reconciliation requires the actual contiguous original switch history')
                authority=parent.get('decision_authority');executor=parent.get('decision_executor')
                if authority is None or executor is None:raise WorkflowError('The current parent cleared the bounded grant or executor; restore explicit policy before resuming the frame')
                payload={**payload,'parent_policy_reconciliation':{'mode':clarification_decision_mode(parent),'authority':authority,'executor':executor,'switches':deepcopy(switches)}}
        cleanup=command=='orchestration-reconcile-actor'
        def scope_guard():
            decision_context_guard(store,context,allow_stale=cleanup)
            if cleanup:return
            if context.get('session_id'):
                parent=clarification_read(store,context['session_id'])
                if parent['state']=='cancelled':raise WorkflowError('Cancelled clarification permits only original actor cleanup')
                adopted=payload.get('parent_policy_reconciliation') if command=='orchestration-resume' else None
                mode=adopted['mode'] if adopted else payload.get('mode','auto') if frame is None else frame['mode']
                authority=adopted['authority'] if adopted else payload.get('authority') if frame is None else frame['authority']
                executor=adopted['executor'] if adopted else payload.get('executor') if frame is None else frame['executor']
                if mode!=clarification_decision_mode(parent) or authority!=parent.get('decision_authority') or mode=='auto' and executor!=parent.get('decision_executor'):raise WorkflowError('Orchestration mode, authority or executor differs from the current clarification')
                if command=='orchestration-switch-mode' and payload.get('mode')!=mode:raise WorkflowError('Change the parent clarification mode through the guarded session')
        if command=='orchestration-next':
            scope_guard();return helper.next_action(store,payload['orchestration_id'])
        if command=='orchestration-switch-mode':clarification_evidence(payload.get('evidence'))
        class BoundStore:
            def __getattr__(self,key):return getattr(store,key)
            def guard(self):
                if store.future.exists():
                    if not payload.get('expected_source_hash'):raise WorkflowError('Orchestration mutation requires the inspected existing queue hash')
                    store.guard(payload['expected_source_hash'])
                elif payload.get('expected_source_hash') is not None:raise WorkflowError('Orchestration queue context changed; reread before mutation')
                if not cleanup and orchestration_execution_snapshot(store)!=current_snapshot:raise WorkflowError('Core execution inputs changed during the metadata operation')
                scope_guard()
            @contextmanager
            def lock(self):
                with store.lock():self.guard();yield
            def commit(self,writes):
                self.guard();return store.commit(writes)
        bound=BoundStore()
        return helper.start(bound,payload) if frame is None else helper.mutate(bound,command,payload)
    except helper.OrchestrationError as error:raise WorkflowError(str(error)) from error

def decision_action(store,command,payload):
    helper=decision_helper()
    if command=='decision-read':return helper.read(store,payload.get('decision_id'))
    if command not in DECISION_COMMANDS:raise WorkflowError('Unknown decision operation')
    if command=='decision-start':context=payload.get('context',{})
    else:context=payload.get('context') if command=='decision-resume' else helper.read(store,payload.get('decision_id'))['context']
    cleanup=command=='decision-reconcile'
    confirmation=None;prepared=None
    def awaiting_confirmation():
        parent=clarification_read(store,context['session_id'])
        if parent['mode']=='required-processing' and parent['state']!='awaiting-confirmation':raise WorkflowError('Post-processing decisions require current clarification readiness before final confirmation')
        return parent
    if not cleanup and isinstance(context,dict) and context.get('session_id') and context.get('purpose')=='confirmation':
        inspected=awaiting_confirmation()
        if inspected['mode']=='required-processing':
            confirmation=processing_helper();prepared=confirmation.prepare_release(store,inspected)
    def scope_guard():
        decision_context_guard(store,context,allow_stale=cleanup)
        if confirmation:confirmation.guard_release(store,awaiting_confirmation(),prepared,register=False)
    class BoundStore:
        def __getattr__(self,key):return getattr(store,key)
        def guard(self):
            if store.future.exists():
                if not payload.get('expected_source_hash'):raise WorkflowError('Decision mutation requires the inspected existing queue source hash')
                store.guard(payload['expected_source_hash'])
            elif payload.get('expected_source_hash') is not None:raise WorkflowError('Decision queue context changed; reread the project')
        @contextmanager
        def lock(self):
            with store.lock():
                self.guard();scope_guard()
                if context.get('session_id') and not cleanup:
                    session=clarification_read(store,context['session_id'])
                    if session['state']=='cancelled':raise WorkflowError('Cancelled clarification permits only original-attempt reconciliation')
                    current=None if command=='decision-start' else helper.read(store,payload['decision_id'])
                    mode=payload.get('mode') if current is None else current['mode']
                    if mode!=clarification_decision_mode(session):raise WorkflowError('Decision mode differs from the current clarification mode')
                    if command=='decision-switch' and (payload.get('mode',mode)!=mode or payload.get('authority',session.get('decision_authority'))!=session.get('decision_authority')):raise WorkflowError('Switch the clarification mode and authority through the guarded parent session')
                    authority=payload.get('authority') if current is None else current['authority']
                    if authority!=session.get('decision_authority'):raise WorkflowError('Decision authority differs from the current clarification grant')
                    executor=payload.get('executor') if current is None else payload.get('executor',current['executor'])
                    if mode=='auto' and executor!=session.get('decision_executor'):raise WorkflowError('Decision executor differs from the actual clarification executor')
                    question=clarification_decision_question(session,context['purpose'],context.get('question_id'))
                    candidate=payload.get('question') if command in {'decision-start','decision-resume'} and 'question' in payload else current['question']
                    if not isinstance(candidate,dict):raise WorkflowError('Decision question requires a structured current definition')
                    if any(candidate.get(key)!=value for key,value in question.items()):raise WorkflowError('Decision question differs from the current clarification question or acceptance purpose')
                yield
        def commit(self,writes):
            self.guard();scope_guard();return store.commit(writes)
    try:
        bound=BoundStore()
        return helper.start(bound,payload) if command=='decision-start' else helper.mutate(bound,command,payload)
    except helper.DecisionError as error:raise WorkflowError(str(error)) from error

def decision_helper():
    return owned_module('skill_tree_decision_governance',Path(__file__).with_name('decision-governance.py'))

def decision_context_guard(store,context,allow_stale=False):
    try:decision_helper().validate_context(context)
    except ValueError as error:raise WorkflowError(str(error)) from error
    # Cleanup closes an existing guarded original attempt and supplies no
    # answer/acceptance. Completion or removal of its former scope cannot strand
    # that attempt; ordinary decision mutations still require live scope below.
    if allow_stale:return
    kind=context.get('kind')
    if kind in {'task','task-group','pending'}:
        selectors=context.get('pending_ids',[]) if kind=='pending' else context.get('task_ids',[])
        if not selectors:raise WorkflowError('Task and Pending decisions require actual selected identities')
        selected=resolve(parse(store.text()),selectors,'Pending Queue' if kind=='pending' else 'Prioritized Next Changes')
        if kind!='pending' and set(context.get('pending_ids',[]))-{pending for task in selected for pending in task['parent_pending_ids']}:raise WorkflowError('Decision Pending provenance differs from the selected tasks')
    if kind=='controller':
        if not store.future.is_file() or not store.state.is_file():raise WorkflowError('A controller decision requires an existing recorded run')
        state=Store(store.root,allow_unselected=True,route_queue=False,neutral=True).load()
        runs=dict(state.get('run_registry',{}).get('runs',{}))
        if state.get('active_run'):runs[state['active_run']['id']]=state['active_run']
        run=runs.get(context.get('run_id'))
        if not run:raise WorkflowError('Controller decision identity is not a recorded run')
        if set(context.get('task_ids',[]))-set(run.get('admitted_task_ids',run.get('snapshot',[]))+run.get('required_ids',[])):raise WorkflowError('Decision scope exceeds the recorded controller scope')
    if context.get('session_id'):
        session=clarification_read(store,context['session_id'])
        current=clarification_decision_context(session,context.get('purpose'),context.get('question_id') if context.get('purpose')=='answer' else None)
        if context!=current:raise WorkflowError('Decision context differs from the current clarification question, semantics or mode epoch')

def clarification_decision_mode(record):
    mode=record.get('decision_mode','manual')
    if mode not in {'auto','manual'}:raise WorkflowError('Unknown clarification decision mode')
    return mode

def clarification_decision_context(record,purpose,question_id=None):
    if purpose not in {'answer','confirmation'}:raise WorkflowError('Unknown clarification decision purpose')
    identity={'kind':'task' if len(record['task_ids'])==1 else 'task-group','id':'task-scope:'+','.join(record['task_ids']),'task_ids':record['task_ids'],'session_id':record['id'],'purpose':purpose,'parent_mode_epoch':record.get('decision_mode_epoch',0)}
    if purpose=='answer':
        question=record['questions'].get(question_id)
        if not question:raise WorkflowError('Decision requires a current clarification question')
        identity.update(question_id=question_id,question_revision=question['revision'])
        semantics={tid:{field:record['baselines'][tid]['fields'][field] for field in fields} for tid,fields in question['bindings'].items()}
        if record['mode']=='required-processing':
            offered=next((round_record for round_record in reversed(record['rounds']) if question_id in round_record['question_ids']),{})
            facts=offered.get('fact_fingerprints',{}).get(question_id)
            if facts:semantics={'bound_fields':semantics,'fact_fingerprints':facts}
    else:
        generation=len(record['processing_requirements']['adoptions']) if record['mode']=='required-processing' else 0
        identity.update(question_id='final-confirmation',question_revision=1+generation)
        semantics=record['semantic_fingerprints']
    semantic=digest(dump({'identity':identity,'mode':clarification_decision_mode(record),'semantics':semantics}).encode())
    content=digest(dump({'identity':identity,'content':{tid:b['content_hash'] for tid,b in record['baselines'].items()}}).encode())
    return {**identity,'semantic_fingerprint':semantic,'content_fingerprint':content}

def clarification_decision_question(record,purpose,question_id=None):
    if purpose=='confirmation':return {'id':'final-confirmation','kind':'specification-acceptance','text':'Accept the current selected task specification.'}
    question=record['questions'].get(question_id)
    if purpose!='answer' or not question:raise WorkflowError('Unknown clarification decision question')
    return {'id':question_id,'kind':question.get('decision_kind','technical'),'text':question['text']}

def clarification_decision_policy(record,payload):
    mode=payload.get('decision_mode','manual')
    if mode not in {'auto','manual'}:raise WorkflowError('Unknown clarification decision mode')
    authority=payload.get('decision_authority',record.get('decision_authority') if mode=='manual' else None)
    if mode=='auto' and not authority:raise WorkflowError('Auto clarification requires an explicit bounded owner grant')
    if authority is not None:
        try:authority=decision_helper().validate_authority(authority,clarification_decision_context(record,'confirmation'),mode)
        except ValueError as error:raise WorkflowError(str(error)) from error
    executor=payload.get('decision_executor',record.get('decision_executor') if mode=='manual' else None)
    if mode=='auto' and (not isinstance(executor,dict) or set(executor)!={'id','context_id'} or any(not isinstance(v,str) or not v.strip() for v in executor.values())):raise WorkflowError('Auto clarification requires the actual executor identity and context')
    return {'decision_mode':mode,'decision_authority':authority,'decision_executor':executor}

def clarification_answer_evidence(store,record,payload,purpose,question_id=None):
    reference=payload.get('decision_receipt')
    mode=clarification_decision_mode(record)
    if reference is None:
        if mode!='manual':raise WorkflowError('Auto clarification requires a current delegated decision receipt')
        return clarification_evidence(payload.get('evidence')),None
    if not isinstance(reference,dict):raise WorkflowError('Decision receipt requires a decision ID and acceptance digest')
    reference={key:reference.get(key) for key in ['decision_id','acceptance_digest']}
    helper=decision_helper();context=clarification_decision_context(record,purpose,question_id)
    if not record.get('decision_authority'):raise WorkflowError('A decision receipt requires the frozen clarification authority')
    expected={'context':context,'mode':mode,'kind':clarification_decision_question(record,purpose,question_id)['kind']}
    # The helper owns the grant digest representation; compare the actual frozen
    # authority as well as the validated helper acceptance identity.
    try:
        decision=helper.read(store,reference.get('decision_id'))
        if decision.get('authority')!=record['decision_authority']:raise WorkflowError('Decision receipt uses another authority grant')
        question=clarification_decision_question(record,purpose,question_id)
        if any(decision.get('question',{}).get(key)!=value for key,value in question.items()):raise WorkflowError('Decision receipt answers another clarification question')
        expected['authority_digest']=decision['authority_digest']
        accepted=helper.acceptance_reference(store,reference,expected)
        if not isinstance(accepted,dict) or not isinstance(accepted.get('origin'),dict):raise WorkflowError('Decision acceptance lacks actual producer evidence')
        if purpose=='confirmation' and record['mode']=='required-processing' and accepted.get('answer')!='accept':raise WorkflowError('Specification confirmation requires an affirmative accept decision')
    except (ValueError,AttributeError,KeyError) as error:raise WorkflowError('Invalid current clarification decision receipt: '+str(error)) from error
    if purpose=='answer':
        option=next((item for item in decision['question']['options'] if item['id']==accepted.get('answer')),None)
        if not option or payload.get('answer') not in {option['id'],option['text']}:raise WorkflowError('Clarification answer differs from the actual accepted decision')
    return accepted['origin'],{'decision_id':reference['decision_id'],'acceptance_digest':reference['acceptance_digest'],'mode':mode,'parent_mode_epoch':record.get('decision_mode_epoch',0),'acceptance':accepted}

def clarification_pending_decisions(store,record):
    helper=decision_helper();pending=[]
    for path in (store.base/'decisions').glob('dg-*.json'):
        decision=helper.read(store,'DG-'+path.stem[3:])
        if decision.get('context',{}).get('session_id')==record['id'] and decision.get('active_attempt_id'):pending.append(decision['id'])
    return pending

CLARIFICATION_COMMANDS={'clarify-start','clarify-read','clarify-round','clarify-answer','clarify-revise','clarify-confirm','clarify-resume','clarify-cancel','clarify-switch-mode','clarify-processing-contribute','clarify-processing-recheck','clarify-processing-adopt'}


def processing_scope_guard(store,context,*,package_root):
    processing_helper().scope_guard(store,context,package_root)

def processing_recheck_guard(store,context,event,readiness=False):
    return processing_helper().recheck_guard(store,context,event,readiness)

def clarification_path(store,session_id):
    if not valid_id(session_id,'CL'):raise WorkflowError('Clarification requires an exact CL- identity')
    return store.owned('.skill-tree/clarifications/'+session_id.lower()+'.json')

def clarification_read(store,session_id):
    path=clarification_path(store,session_id)
    if not path.is_file():raise WorkflowError('Unknown clarification session')
    raw=path.read_bytes();record=json.loads(raw)
    if record.get('schema')!=1 or record.get('id')!=session_id or record.get('state') not in CLARIFICATION_STATES or type(record.get('revision')) is not int or record['revision']<1:
        raise WorkflowError('Unsupported clarification session')
    ids=record.get('task_ids')
    if not isinstance(ids,list) or not ids or any(not valid_id(tid,'T') for tid in ids) or len(set(ids))!=len(ids):raise WorkflowError('Corrupt clarification scope')
    return {**record,'session_hash':digest(raw)}

def clarification_tasks(store,task_ids,text=None):
    if not isinstance(task_ids,list) or not task_ids or any(not valid_id(tid,'T') for tid in task_ids) or len(set(task_ids))!=len(task_ids):raise WorkflowError('Clarification requires exact unique prioritized T- identities')
    tasks=parse(store.text() if text is None else text);selected=set(task_ids)
    result=[t for t in tasks if t['queue']=='Prioritized Next Changes' and t['id'] in selected]
    if {t['id'] for t in result}!=selected:raise WorkflowError('Clarification task is absent, terminal or outside the prioritized queue')
    if any(o['task_id'] in selected for o in store.outcomes()):raise WorkflowError('Terminal task definitions cannot be clarified or revised')
    return sorted(result,key=lambda t:-t['priority'])

def clarification_text_semantics(value):
    # Only supported presentation equivalence is normalized; literals stay case-sensitive.
    chunks=re.split(r'(```[^\n]*\n.*?\n```|`[^`\n]*`)',value,flags=re.S);result=[]
    for chunk in chunks:
        if chunk.startswith('```'):
            match=re.fullmatch(r'```json\n(.*?)\n```',chunk,re.S)
            if match:
                try:chunk='```json\n'+dump(json.loads(match[1])).strip()+'\n```'
                except json.JSONDecodeError:pass
            result.append(chunk)
        elif chunk.startswith('`'):result.append(chunk)
        else:
            chunk=re.sub(r'(\*\*|__)(\S(?:.*?\S)?)\1',r'\2',chunk)
            result.append('\n'.join(re.sub(r'[ \t]+',' ',line.strip()) for line in chunk.splitlines() if line.strip()))
    return ''.join(result).strip()

def clarification_semantics(task):
    body=re.sub(r'^###[^\n]+\n\s*```yaml\n.*?\n```\s*','',task['body'],count=1,flags=re.S)
    sections={};heading='content';fenced=False
    for line in body.splitlines(keepends=True):
        if line.startswith('```'):fenced=not fenced
        match=None if fenced else re.fullmatch(r'([A-Z][A-Za-z /-]+):\s*\n?',line)
        if match:heading=match[1];sections.setdefault(heading,[])
        else:sections.setdefault(heading,[]).append(line)
    mapping={'Goal':'goal','Scope':'scope','Touch':'scope','Out of scope':'exclusions','Exclusions':'exclusions','Acceptance':'acceptance','Validation':'validation','Required plugin policy':'required_plugin_policy'}
    fields={key:[] for key in CLARIFICATION_FIELDS-{'title','dependencies'}}
    for name,lines in sections.items():fields[mapping.get(name,'content')].append((name,clarification_text_semantics(''.join(lines))))
    fields={key:value for key,value in fields.items()}
    fields['validation'].append(('metadata',{key:task.get(key) for key in OPTIONAL_FIELDS}))
    fields['content'].append(('identity',clarification_identity(task)))
    fields.update(title=task['title'],dependencies=task['depends_on'])
    return {key:digest(dump(value).encode()) for key,value in fields.items()}

def clarification_identity(task):
    return {key:task[key] for key in ['id','parent_pending_ids','processing_run_id','root_task_id','related_task_id','relation']}

def clarification_baselines(tasks):
    return {task['id']:{'content_hash':digest(task['body'].encode()),'identity':clarification_identity(task),'fields':clarification_semantics(task)} for task in tasks}

def clarification_fingerprints(baselines):
    return {tid:digest(dump(baseline['fields']).encode()) for tid,baseline in baselines.items()}

def clarification_invalidate(record,baselines):
    changed={tid:{field for field,value in baseline['fields'].items() if value!=record['baselines'][tid]['fields'].get(field)} for tid,baseline in baselines.items()}
    invalid=set()
    for key,answer in record['answers'].items():
        question=record['questions'][key]
        if any(changed.get(tid,set())&set(fields) for tid,fields in question['bindings'].items()):invalid.add(key)
    while True:
        expanded=invalid|{key for key,q in record['questions'].items() if set(q['prerequisites'])&invalid}
        if expanded==invalid:break
        invalid=expanded
    for key in invalid:
        if key in record['answers']:record['answers'][key]['valid']=False
    semantic_change=any(changed.values())
    if semantic_change:
        if record.get('confirmation'):record.setdefault('confirmation_history',[]).append(record['confirmation'])
        record['confirmation']=None;record['clarity']=None;record['state']='researching';record['next_action']='Recheck changed task semantics and affected decisions'
    record['baselines']=baselines;record['semantic_fingerprints']=clarification_fingerprints(baselines)
    return changed

def clarification_admission(store,task_id,hook_gate=True):
    if hook_gate:hook_admission(store,scope=task_id)
    done={o['task_id']:o for o in store.outcomes() if o['disposition']=='completed'}
    if task_id in done:return
    tasks={t['id']:t for t in parse(store.text())}
    required=[];satisfied=[]
    for path in sorted((store.base/'clarifications').glob('*.json')):
        record=clarification_read(store,'CL-'+path.stem[3:])
        if task_id not in record['task_ids']:continue
        if record['mode']=='required-processing':
            processing_helper().admit(store,record,tasks.get(task_id))
            continue
        if record['mode']=='explicit' and record['state']=='cancelled':continue
        fresh=not clarification_stale_facts(store,record)
        for tid in record['task_ids']:
            if tid in tasks:
                fresh=fresh and clarification_fingerprints(clarification_baselines([tasks[tid]]))[tid]==record['semantic_fingerprints'].get(tid)
            else:
                # Successful guarded completion removes the definition; immutable history retains acceptance.
                fresh=fresh and tid in done and done[tid]['recorded_at']>=(record.get('confirmation') or {}).get('recorded_at','')
        if record['state']=='complete' and fresh and clarification_acceptance_current(store,record):
            if record['mode']=='required-interview':satisfied.append(record)
            continue
        if record['mode']=='required-interview':required.append(record)
        elif record['state']!='cancelled':raise WorkflowError('Selected task has an open or stale clarification hold: '+record['id'])
    if required and not all(any(set(old['task_ids']).issubset(set(done['task_ids'])) and done['created_at']>=old['created_at'] for done in satisfied) for old in required):
        raise WorkflowError('Selected task has an unsatisfied required interview hold: '+required[0]['id'])

def clarification_acceptance_current(store,record):
    confirmation=record.get('confirmation')
    if not confirmation:return False
    if 'decision_mode' in record and (confirmation.get('decision_mode')!=clarification_decision_mode(record) or confirmation.get('decision_mode_epoch')!=record.get('decision_mode_epoch',0)):return False
    try:
        clarification_answer_evidence(store,record,{'evidence':confirmation.get('evidence'),'decision_receipt':confirmation.get('decision_receipt')},'confirmation')
        for key,answer in record['answers'].items():
            reference=answer.get('decision_receipt')
            if answer.get('valid') and reference and reference.get('parent_mode_epoch')==record.get('decision_mode_epoch',0):
                clarification_answer_evidence(store,record,{'answer':answer['answer'],'decision_receipt':reference},'answer',key)
    except (ValueError,KeyError,TypeError):return False
    return True

def clarification_evidence(value):
    if not isinstance(value,dict) or set(value)!={'kind','reference'} or value['kind'] not in {'owner-message','submitted-answer'} or not isinstance(value['reference'],str) or not value['reference'].strip():
        raise WorkflowError('Actual owner answer evidence requires owner-message or submitted-answer and a nonempty reference')
    return value

def clarification_stale_facts(store,record):
    stale=[];origin=digest(str(store.source_root.resolve()).encode())
    for key,fact in record['facts'].items():
        if fact.get('source_origin')!=origin or any(file_hash(binding_path(store.source_root,source['path']))!=source['sha256'] for source in fact['sources']):stale.append(key)
    return stale

def clarification_write(store,record,writes=None):
    record.pop('session_hash',None)
    record['updated_at']=now()
    relative=clarification_path(store,record['id']).relative_to(store.root).as_posix()
    store.commit({**(writes or {}),relative:dump(record)})
    return clarification_read(store,record['id'])

def clarification_guard(store,payload):
    if not isinstance(payload.get('expected_source_hash'),str) or not payload['expected_source_hash']:raise WorkflowError('Clarification requires expected_source_hash from inspected complete queue bytes')
    store.guard(payload['expected_source_hash'])
    record=clarification_read(store,payload.get('session_id'))
    if payload.get('expected_session_hash')!=record['session_hash'] or type(payload.get('expected_session_revision')) is not int or payload['expected_session_revision']!=record['revision']:
        raise WorkflowError('Clarification session changed since inspection; reread the session')
    return record

def clarification_start(store,payload):
    with store.lock():
        if not payload.get('expected_source_hash'):raise WorkflowError('Clarification requires expected_source_hash')
        store.guard(payload['expected_source_hash']);tasks=clarification_tasks(store,payload.get('task_ids'))
        mode=payload.get('mode','explicit')
        if mode not in {'explicit','required-interview'}:raise WorkflowError('Unknown clarification mode')
        for path in (store.base/'clarifications').glob('*.json'):
            old=clarification_read(store,'CL-'+path.stem[3:])
            if old['state'] not in {'complete','cancelled'} and set(old['task_ids'])&{t['id'] for t in tasks}:raise WorkflowError('Selected task already has an open clarification session: '+old['id'])
        baselines=clarification_baselines(tasks)
        record={'schema':1,'id':identity('CL'),'revision':1,'mode':mode,'task_ids':[t['id'] for t in tasks],'state':'researching','source_hash':file_hash(store.future),'baselines':baselines,'semantic_fingerprints':clarification_fingerprints(baselines),'facts':{},'questions':{},'rounds':[],'answers':{},'task_revisions':[],'confirmation':None,'clarity':None,'no_progress_rounds':0,'next_action':'Research source facts and prepare the independent decision frontier','created_at':now()}
        record.update(clarification_decision_policy(record,payload));record['decision_mode_epoch']=0;record['decision_mode_history']=[]
        store.guard(payload['expected_source_hash'])
        return clarification_write(store,record)

def clarification_questions(record,specs):
    if not isinstance(specs,list):raise WorkflowError('Questions require a list')
    seen=set()
    for spec in specs:
        if not isinstance(spec,dict):raise WorkflowError('Question requires a structured definition')
        key=spec.get('id');bindings=spec.get('bindings');prerequisites=spec.get('prerequisites',[])
        if not isinstance(key,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',key) or key in seen:raise WorkflowError('Questions require unique stable lowercase IDs')
        seen.add(key)
        if any(not isinstance(spec.get(field),str) or not spec[field].strip() for field in ['text','recommendation']):raise WorkflowError('Every question requires text and a recommendation')
        if not isinstance(bindings,dict) or not bindings or not set(bindings).issubset(record['task_ids']):raise WorkflowError('Questions bind exact selected tasks')
        for fields in bindings.values():
            if not isinstance(fields,list) or not fields or len(set(fields))!=len(fields) or not set(fields).issubset(CLARIFICATION_FIELDS):raise WorkflowError('Question bindings require explicit semantic fields')
        if not isinstance(prerequisites,list) or any(not isinstance(v,str) for v in prerequisites) or len(set(prerequisites))!=len(prerequisites) or key in prerequisites:raise WorkflowError('Invalid question prerequisites')
        question={field:deepcopy(spec[field]) for field in ['id','text','recommendation','bindings']};question.update(prerequisites=prerequisites,required=spec.get('required',True))
        if 'decision_kind' in spec:
            if spec['decision_kind'] not in {'product','technical'}:raise WorkflowError('Clarification question requires a bounded product or technical decision kind')
            question['decision_kind']=spec['decision_kind']
        if type(question['required']) is not bool:raise WorkflowError('Question required flag requires a boolean')
        old=record['questions'].get(key);definition={k:v for k,v in (old or {}).items() if k!='revision'}
        question['revision']=(old['revision']+(question!=definition)) if old else 1
        if 'revision' in spec and spec['revision']!=question['revision']:raise WorkflowError('Question revision does not match the current definition')
        if old and question['revision']!=old['revision']:
            if key in record['answers']:record['answers'][key]['valid']=False
            record['confirmation']=None;record['clarity']=None
        record['questions'][key]=question
    visiting=set();visited=set()
    def visit(key):
        if key not in record['questions']:raise WorkflowError('Unknown question prerequisite: '+key)
        if key in visiting:raise WorkflowError('Question prerequisite cycle')
        if key in visited:return
        visiting.add(key)
        for prerequisite in record['questions'][key]['prerequisites']:visit(prerequisite)
        visiting.remove(key);visited.add(key)
    for key in record['questions']:visit(key)
    # A changed prerequisite invalidates downstream settled answers, too.
    for _ in record['questions']:
        for key,q in record['questions'].items():
            if key in record['answers'] and any(not record['answers'].get(p,{}).get('valid') for p in q['prerequisites']):record['answers'][key]['valid']=False

def clarification_round(store,record,payload):
    application=processing_helper() if record['mode']=='required-processing' else None
    if application:application.guard_questions(record,payload.get('questions',[]))
    clarification_questions(record,payload.get('questions',[]))
    facts=payload.get('facts',[])
    if not isinstance(facts,list):raise WorkflowError('Source facts require a list')
    for fact in facts:
        if not isinstance(fact,dict) or not isinstance(fact.get('id'),str) or not re.fullmatch(r'[a-z][a-z0-9-]*',fact['id']) or not fact.get('observation') or not isinstance(fact.get('limitations'),list) or not fact.get('sources'):raise WorkflowError('Source facts require stable identity, observation, inspected sources and limitations')
        for source in fact['sources']:
            path=binding_path(store.source_root,source['path'])
            if not source.get('sha256') or file_hash(path)!=source['sha256']:raise WorkflowError('Source fact does not match inspected source bytes')
        record['facts'][fact['id']]={**deepcopy(fact),'source_origin':digest(str(store.source_root.resolve()).encode())}
    fact_contexts=application.fact_contexts(store,record) if application else {}
    if application:application.invalidate_fact_answers(record,fact_contexts)
    settled={key for key,answer in record['answers'].items() if answer['valid']}
    unresolved=[key for key,q in record['questions'].items() if q['required'] and key not in settled]
    frontier=[key for key,q in record['questions'].items() if key not in settled and fact_contexts.get(key,{}) is not None and set(q['prerequisites']).issubset(settled)]
    clarity=payload.get('clarity')
    if clarity is not None:
        fields={'goals','scope','exclusions','dependencies','acceptance','validation','decisions'}
        if not isinstance(clarity,dict) or set(clarity)!=fields|{'evidence'} or any(type(clarity[k]) is not bool for k in fields) or not isinstance(clarity['evidence'],list) or not clarity['evidence'] or any(not isinstance(e,str) or not e.strip() for e in clarity['evidence']):raise WorkflowError('Clarity recheck requires all rubric booleans and concrete evidence')
        record['clarity']={'assessment':clarity,'semantic_fingerprints':record['semantic_fingerprints']}
    progress=digest(dump({key:record[key] for key in ['facts','questions','answers','semantic_fingerprints','clarity']}).encode())
    record['no_progress_rounds']=record['no_progress_rounds']+1 if record.get('progress_signature')==progress else 0
    record['progress_signature']=progress
    round_record={'id':identity('CR'),'question_ids':frontier,'question_revisions':{key:record['questions'][key]['revision'] for key in frontier},'source_hash':file_hash(store.future),'semantic_fingerprints':record['semantic_fingerprints']}
    if 'decision_mode' in record:round_record['decision_mode_epoch']=record.get('decision_mode_epoch',0)
    if application:round_record['fact_fingerprints']={key:fact_contexts[key] for key in frontier if fact_contexts[key]}
    record['rounds'].append(round_record)
    checked=record.get('clarity')
    record['stale_facts']=clarification_stale_facts(store,record)
    if record['stale_facts'] and not (application and frontier):record.update(state='blocked',clarity=None,confirmation=None,next_action='Research changed or unavailable source facts in the original execution checkout: '+', '.join(record['stale_facts']))
    elif record['no_progress_rounds']>=2:record.update(state='blocked',next_action='Resolve the unchanged decision or source-research prerequisite before another round')
    elif frontier:record.update(state='awaiting-answers',next_action='Prepare bounded independent delegated decisions for the current question frontier' if clarification_decision_mode(record)=='auto' else 'Present every independent question with its recommendation and wait for actual owner answers')
    elif unresolved:record.update(state='blocked',next_action='Resolve unsettled question prerequisites')
    elif checked and checked['semantic_fingerprints']==record['semantic_fingerprints'] and all(value is True for key,value in checked['assessment'].items() if key!='evidence'):
        record.update(state='awaiting-confirmation',next_action='Obtain current delegated specification acceptance under the frozen authority' if clarification_decision_mode(record)=='auto' else 'Present the current selected task summary and request explicit shared-understanding confirmation')
    else:record.update(state='researching',next_action='Research remaining facts and record a complete clarity recheck')

def clarification_progress_guard(state,task_id):
    for slot in state.get('task_progress',{}).get(task_id,{}).get('checks',{}).values():
        if pending_check_attempt(slot):raise WorkflowError('Recover the prepared implementation check before task revision')

def clarification_revise(store,record,payload,base_text=None):
    specs=payload.get('tasks')
    if not isinstance(specs,list) or not specs:raise WorkflowError('Task revision requires nonempty replacement specifications')
    text=store.text() if base_text is None else base_text;old_text=text;before_tasks=parse(text);seen=set()
    # Validate existing checkpoint without projecting or persisting a selected implementation run.
    state=Store(store.root,allow_unselected=True,neutral=True).load(text);persisted=json.loads(store.state.read_text()) if store.state.exists() else state
    for spec in specs:
        if not isinstance(spec,dict) or set(spec)-{'task_id','title','body','depends_on'}:raise WorkflowError('Task revision permits only selected task content, title and dependencies')
        tid=spec.get('task_id')
        if tid not in record['task_ids'] or tid in seen:raise WorkflowError('Task revision requires exact unique selected tasks')
        seen.add(tid);task=clarification_tasks(store,[tid],text)[0]
        clarification_progress_guard(persisted,tid)
        meta={key:deepcopy(task[key]) for key in FIELDS+OPTIONAL_FIELDS if key in task}
        if 'depends_on' in spec:meta['depends_on']=spec['depends_on']
        match=re.match(r'^###[^\n]+\n\s*```yaml\n.*?\n```\s*',task['body'],re.S)
        body=spec.get('body',task['body'][match.end():]);title=spec.get('title',task['title'])
        if not isinstance(body,str):raise WorkflowError('Replacement task body requires text')
        fenced=False
        for line in body.splitlines():
            if line.startswith('```'):fenced=not fenced
            elif not fenced and re.match(r'^#{1,3}\s',line):raise WorkflowError('Replacement task body cannot contain document, queue or task headings')
        assert_prose(title+'\n'+body);validate_metadata(meta,task['queue']);entry=render(title,meta,body)
        lines=text.splitlines(keepends=True);lines[task['start']:task['end']]=[entry];text=''.join(lines)
    tasks=parse(text)
    if [(t['id'],t['queue']) for t in before_tasks]!=[(t['id'],t['queue']) for t in tasks] or any(old['body']!=new['body'] for old,new in zip(before_tasks,tasks) if old['id'] not in seen):raise WorkflowError('Task revision changes unselected tasks or queue membership')
    validate_dependencies(tasks,{o['task_id'] for o in store.outcomes() if o['disposition']=='completed'})
    if record['mode']=='required-processing':
        application=processing_helper()
        for old,new in zip(before_tasks,tasks):
            if old['id'] in seen:application.guard_revision(store,record,old,new)
    before_baselines=clarification_baselines([task for task in before_tasks if task['id'] in record['task_ids']]);before_semantics=clarification_fingerprints(before_baselines)
    baselines=clarification_baselines(clarification_tasks(store,record['task_ids'],text));after_semantics=clarification_fingerprints(baselines);changed=clarification_invalidate(record,baselines)
    revision_fingerprints={tid:{'before':{'semantic_fingerprint':before_semantics[tid],'content_fingerprint':before_baselines[tid]['content_hash']},'after':{'semantic_fingerprint':after_semantics[tid],'content_fingerprint':baselines[tid]['content_hash']}} for tid in record['task_ids']}
    record['task_revisions'].append({'id':identity('TR'),'task_ids':[tid for tid in record['task_ids'] if tid in seen],'task_fingerprints':revision_fingerprints,'content_changed_task_ids':[tid for tid in record['task_ids'] if before_baselines[tid]['content_hash']!=baselines[tid]['content_hash']],'source_before':digest(old_text.encode()),'source_after':digest(text.encode()),'changed_fields':{key:sorted(value) for key,value in changed.items()},'recorded_at':now()})
    return _clarification_queue_writes(store,record,text,persisted)


def _clarification_queue_writes(store,record,text,persisted=None):
    if persisted is None:
        neutral=Store(store.root,allow_unselected=True,neutral=True)
        state=neutral.load()
        persisted=json.loads(store.state.read_text()) if store.state.exists() else state
    persisted['source_hash']=digest(text.encode());persisted['tasks']=index(text)
    manifest_value=manifest(store);state_rel='.skill-tree/documents/future.json'
    if not any(f['path']==state_rel for f in manifest_value['files']):manifest_value['files'].append({'path':state_rel,'role':'generated-index-and-active-state','owner':'skill-tree'})
    manifest_value['state']=state_rel;manifest_value['source_digests']['.skill-tree/documents/future.md']=digest(text.encode())
    record['source_hash']=digest(text.encode())
    return {'.skill-tree/documents/future.md':text,state_rel:dump(persisted),'.skill-tree/skill-tree.json':dump(manifest_value)}

def clarification_mutate(store,command,payload):
    prepared=None
    if command in {'clarify-confirm','clarify-processing-adopt'}:
        inspected=clarification_guard(store,payload)
        if inspected['mode']=='required-processing':
            application=processing_helper()
            if command=='clarify-confirm':
                prepared=application.prepare_release(store,inspected)
            else:
                prepared=application.prepare_adoption(store,inspected,payload)
                if 'decision_receipt' not in payload:
                    return {'decision_context':prepared['decision_context'],
                            'configuration_digest':prepared['configuration']['configuration_digest'],
                            'execution_snapshot':prepared['proof']['execution_snapshot'],
                            'required_bindings':list(application._selected(prepared['configuration'],prepared['proof']))}
    with store.lock():
        record=clarification_guard(store,payload);tasks=clarification_tasks(store,record['task_ids']);baselines=clarification_baselines(tasks)
        if any(baselines[tid]['identity']!=record['baselines'][tid]['identity'] for tid in record['task_ids']):raise WorkflowError('Selected task provenance or relationship identity changed; preserve the clarification and resolve the conflict')
        application=processing_helper() if record['mode']=='required-processing' else None
        if command.startswith('clarify-processing-') and not application:raise WorkflowError('An actual required post-processing session is needed')
        if record['state']=='cancelled' and command!='clarify-processing-adopt':raise WorkflowError('Cancelled clarification remains terminal; start a new explicit session')
        if command=='clarify-switch-mode':
            mode_evidence=clarification_evidence(payload.get('evidence'))
            new_policy=clarification_decision_policy(record,payload)
            old_policy={key:record.get(key,'manual' if key=='decision_mode' else None) for key in new_policy}
            if new_policy==old_policy:return record
        reopened=None
        if application and record['state']=='complete' and command in {'clarify-resume','clarify-revise','clarify-switch-mode','clarify-processing-adopt'}:
            application.pending_guard(store,record)
            reopened=application.reopen(store,record,tasks[0],allow_drift=command=='clarify-resume')
            if reopened:baselines=clarification_baselines(clarification_tasks(store,record['task_ids'],reopened))
        if command=='clarify-resume':
            if application and not reopened:application.recover_held_revision(store,record,tasks[0],baselines)
            clarification_invalidate(record,baselines)
            if application:application.invalidate_fact_answers(record,application.fact_contexts(store,record))
            if record['state']=='blocked':record.update(state='researching',next_action='Resolve the recorded prerequisite and recheck the same selected tasks')
            record['stale_facts']=clarification_stale_facts(store,record)
            if record['stale_facts']:record.update(state='blocked',clarity=None,confirmation=None,next_action='Research changed or unavailable source facts in the original execution checkout: '+', '.join(record['stale_facts']))
        elif any(baselines[tid]['content_hash']!=record['baselines'][tid]['content_hash'] for tid in record['task_ids']):raise WorkflowError('Selected task source changed; resume clarification to reconcile drift')
        writes=_clarification_queue_writes(store,record,reopened) if reopened else None
        if command=='clarify-round':
            if record['state']=='complete':raise WorkflowError('Completed clarification requires semantic drift before another round')
            clarification_round(store,record,payload)
        elif command=='clarify-answer':
            key=payload.get('question_id');question=record['questions'].get(key);round_record=next((r for r in record['rounds'] if r['id']==payload.get('round_id')),None)
            if not question or not round_record or key not in round_record['question_ids'] or payload.get('question_revision')!=question['revision'] or round_record['question_revisions'][key]!=question['revision']:raise WorkflowError('Answer does not match the session round and question revision')
            if round_record.get('decision_mode_epoch',0)!=record.get('decision_mode_epoch',0):raise WorkflowError('Answer belongs to a previous decision mode epoch')
            if application and application.fact_contexts(store,record)[key]!=round_record.get('fact_fingerprints',{}).get(key,{}):raise WorkflowError('Question factual prerequisites changed; research and prepare a current round before answering')
            if not isinstance(payload.get('answer'),str) or not payload['answer'].strip():raise WorkflowError('Actual submitted owner answer is required')
            evidence,decision_receipt=clarification_answer_evidence(store,record,payload,'answer',key)
            answer={'round_id':round_record['id'],'question_revision':question['revision'],'answer':payload['answer'],'evidence':evidence,'valid':True}
            if decision_receipt is not None:answer['decision_receipt']=decision_receipt
            old=record['answers'].get(key)
            if old and old['valid'] and old['round_id']==round_record['id']:
                if old!=answer:raise WorkflowError('Conflicting replay of the original owner answer')
                return record
            if any(round_record['semantic_fingerprints'].get(tid)!=record['semantic_fingerprints'][tid] for tid in question['bindings']):raise WorkflowError('Question task context changed; prepare a current round before another owner answer')
            if round_record!=record['rounds'][-1] or any(not record['answers'].get(p,{}).get('valid') for p in question['prerequisites']):raise WorkflowError('Answer round is stale or its prerequisites remain unsettled')
            if old:record.setdefault('answer_history',[]).append({'question_id':key,**deepcopy(old)})
            record['answers'][key]=answer;record.update(state='revising',clarity=None,confirmation=None,next_action='Apply accepted decisions to the selected tasks and recheck the decision frontier')
        elif command=='clarify-revise':writes=clarification_revise(store,record,payload,reopened)
        elif command=='clarify-processing-contribute':
            if record['state']=='complete':raise WorkflowError('Resume the exact released post-processing task before incorporating another result')
            application.register_contribution(store,record,payload)
        elif command=='clarify-processing-recheck':
            if record['state']=='complete':raise WorkflowError('Resume the exact released post-processing task before starting a recheck')
            application.create_recheck(store,record,payload)
        elif command=='clarify-processing-adopt':application.adopt(store,record,payload,prepared)
        elif command=='clarify-confirm':
            if clarification_stale_facts(store,record):raise WorkflowError('Source facts changed after research; resume and recheck before confirmation')
            if record['state']!='awaiting-confirmation' or payload.get('task_ids')!=record['task_ids'] or payload.get('semantic_fingerprints')!=record['semantic_fingerprints']:raise WorkflowError('Confirmation must match the current exact scope and semantic task fingerprints after clarity recheck')
            frames=application.guard_release(store,record,prepared) if application else None
            retained=application and not ('evidence' in payload or 'decision_receipt' in payload) and clarification_acceptance_current(store,record)
            if not retained:
                evidence,decision_receipt=clarification_answer_evidence(store,record,payload,'confirmation')
                record['confirmation']={'task_ids':record['task_ids'],'semantic_fingerprints':record['semantic_fingerprints'],'evidence':evidence,'recorded_at':now()}
                if 'decision_mode' in record:record['confirmation'].update(decision_mode=clarification_decision_mode(record),decision_mode_epoch=record.get('decision_mode_epoch',0))
                if decision_receipt is not None:record['confirmation']['decision_receipt']=decision_receipt
            record.update(state='complete',next_action='Report clarification acceptance; wait for a separate implementation instruction')
            if application:writes=_clarification_queue_writes(store,record,application.finalize(store,record,frames))
        elif command=='clarify-switch-mode':
            if clarification_pending_decisions(store,record):raise WorkflowError('Reconcile or cancel the original pending delegated decision before switching mode')
            if application:
                application.pending_guard(store,record)
                application.policy_switched(store,record)
            record.setdefault('decision_mode_history',[]).append({'previous_policy':old_policy,'previous_epoch':record.get('decision_mode_epoch',0),'previous_confirmation':deepcopy(record.get('confirmation')),'evidence':mode_evidence,'recorded_at':now()})
            record.update(new_policy);record['decision_mode_epoch']=record.get('decision_mode_epoch',0)+1
            record.update(state='researching',confirmation=None,clarity=None,next_action='Recheck current clarity and obtain acceptance under the explicitly selected mode and authority')
        elif command=='clarify-cancel':
            if not isinstance(payload.get('reason'),str) or not payload['reason'].strip():raise WorkflowError('Cancellation requires an explicit reason')
            if clarification_pending_decisions(store,record):raise WorkflowError('Reconcile or cancel original pending delegated decisions before cancelling clarification')
            if application:
                if record['state']=='complete':raise WorkflowError('Resume a released task before cancelling post-processing clarification')
                application.pending_guard(store,record)
            record.update(state='cancelled',cancellation={'reason':payload['reason'],'recorded_at':now()},next_action='Report cancelled discussion and any unsatisfied required interview obligation')
        record['revision']+=1
        if writes is None:record['source_hash']=file_hash(store.future)
        store.guard(payload['expected_source_hash'])
        return clarification_write(store,record,writes)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=sorted(CLARIFICATION_COMMANDS|DECISION_COMMANDS|ORCHESTRATION_COMMANDS|HOOK_COMMANDS|set(LOCAL_DELIVERY_COMMANDS)|{'refresh','manifest','index','read','select','pending','intake','process','start','next','advance','checkpoint','complete','finish','audit','prune','history','cycle','capture-foundation','begin','implemented','prepare-check','record-check','reconcile-check','reuse-check','admit','resume-task','accept-revalidation','focus-maintenance','workspace-setup','recover-locator','recover-workspace','resource','environment','runs','export-run','replay-events'}));parser.add_argument('root',type=Path);parser.add_argument('--id');parser.add_argument('--names',nargs='*');parser.add_argument('--input',type=Path);parser.add_argument('--mode',choices=['next','all'],default='next');parser.add_argument('--component');parser.add_argument('--apply',action='store_true');parser.add_argument('--expected-source-hash');parser.add_argument('--run-id')
    args=parser.parse_args(argv)
    try:
        store=Store(args.root,args.run_id,allow_unselected=args.command in {'index','runs','manifest','start','workspace-setup','recover-locator'},route_queue=args.command!='recover-locator');payload=json.loads(args.input.read_text()) if args.input else {}
        if args.expected_source_hash:payload['expected_source_hash']=args.expected_source_hash
        cmd=args.command
        if cmd in LOCAL_DELIVERY_COMMANDS:
            result=local_delivery_action(store,LOCAL_DELIVERY_COMMANDS[cmd],payload)
        elif cmd in HOOK_COMMANDS:
            store=Store(args.root,allow_unselected=True,neutral=True)
            if args.id:payload['chain_id']=args.id
            result=hook_action(store,cmd,payload)
        elif cmd in ORCHESTRATION_COMMANDS:
            store=Store(args.root,allow_unselected=True,neutral=True)
            if args.id:payload['orchestration_id']=args.id
            result=orchestration_action(store,cmd,payload)
        elif cmd in DECISION_COMMANDS:
            store=Store(args.root,allow_unselected=True,neutral=True)
            if args.id:payload['decision_id']=args.id
            result=decision_action(store,cmd,payload)
        elif cmd in CLARIFICATION_COMMANDS:
            # Canonical routing only: no checkpoint load or implicit implementation-run selection.
            store=Store(args.root,allow_unselected=True,neutral=True)
            if cmd=='clarify-start':result=clarification_start(store,payload)
            elif cmd=='clarify-read':result=clarification_read(store,args.id or payload.get('session_id'))
            else:result=clarification_mutate(store,cmd,payload)
        elif cmd=='manifest':
            store=Store(args.root,args.run_id,allow_unselected=True,route_queue=False)
            if args.apply:
                with store.lock():result=manifest(store);store.commit({'.skill-tree/skill-tree.json':dump(result)})
            else:result=manifest(store)
        elif cmd=='refresh':
            with store.lock():text=store.text();result=store.load(text);store.save(text,result)
        elif cmd=='index':result=store.load()
        elif cmd=='read':result=resolve(parse(store.text()),[args.id])[0]
        elif cmd=='select':
            result=select(parse(store.text()),args.id);clarification_admission(store,result['id'])
        elif cmd=='pending':result=resolve(parse(store.text()),args.names or ([args.id] if args.id else []),'Pending Queue')
        elif cmd=='intake':result=intake(store,payload)
        elif cmd=='capture-foundation':result=capture_foundation(store)
        elif cmd=='begin':result=begin_task(store,payload)
        elif cmd=='implemented':result=mark_implemented(store,payload)
        elif cmd=='prepare-check':result=prepare_check(store,payload)
        elif cmd=='record-check':result=record_check(store,payload)
        elif cmd=='reconcile-check':result=reconcile_check(store,payload)
        elif cmd=='reuse-check':result=reuse_check(store,payload)
        elif cmd=='admit':result=resume_admission(store)
        elif cmd=='focus-maintenance':result=focus_maintenance(store,payload)
        elif cmd=='resume-task':result=resume_task(store,payload)
        elif cmd=='accept-revalidation':result=accept_revalidation(store,payload)
        elif cmd=='process':result=process(store,payload)
        elif cmd=='workspace-setup':result=workspaces.setup(store,payload)
        elif cmd=='recover-locator':result=workspaces.recover_locator(store,payload)
        elif cmd=='recover-workspace':result=workspaces.recover_workspace(store,payload)
        elif cmd=='resource':result=workspaces.resource(store,payload)
        elif cmd=='environment':result=workspaces.environment(store,payload)
        elif cmd=='export-run':result=export_run(store)
        elif cmd=='replay-events':result=replay_events(store,payload)
        elif cmd=='runs':result=store.load().get('run_registry',{})
        elif cmd=='start':result=start(store,args.mode,args.id,payload.get('limits'),payload)
        elif cmd=='next':result=next_task(store)
        elif cmd=='advance':result=advance(store)
        elif cmd=='checkpoint':result=checkpoint(store,payload)
        elif cmd=='complete':result=complete(store,payload)
        elif cmd=='finish':result=finish(store)
        elif cmd=='audit':result=audit(store,payload)
        elif cmd=='history':result=history(store,args.id,args.component)
        elif cmd=='cycle':result=record_cycle(store)
        else:result={'removed' if args.apply else 'candidates':prune(store,args.apply)}
        print(json.dumps(result,ensure_ascii=True,indent=2,sort_keys=True)+'\n' if cmd in HOOK_COMMANDS else dump(result),end='');return 0
    except (WorkflowError,workspaces.RunError,OSError,json.JSONDecodeError,KeyError,TypeError,subprocess.TimeoutExpired) as exc:
        print(dump({'ok':False,'error':str(exc)}),end='');return 2
if __name__=='__main__':
    raise SystemExit(main())
