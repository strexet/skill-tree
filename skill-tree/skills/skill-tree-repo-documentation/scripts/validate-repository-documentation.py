#!/usr/bin/env python3
# GENERATED FILE
# Source: skill-tree/common/scripts/validate-repository-documentation.py; generator: skill-tree/scripts/sync-skill-references.py
"""Validate target documents, navigation manifests and checkpoint consistency."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

REQUIRED=['project.md','technical.md','features.md','future.md','rules.md','repository-map.md','build-and-release.md','testing.md','dependencies.md']

def load(name):
    path=Path(__file__).with_name(name+'.py');spec=importlib.util.spec_from_file_location(name.replace('-','_'),path);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

def validate_manifest(root):
    """Read persisted metadata directly; never refresh or replace a checkpoint."""
    root=root.resolve();errors=[];warnings=[];wf=load('workflow-state')
    manifest_path=root/'skill-tree/skill-tree.json'
    try:data=json.loads(manifest_path.read_text())
    except (OSError,ValueError) as exc:return {'ok':False,'errors':['Invalid manifest JSON: '+str(exc)],'warnings':[]}
    if not isinstance(data,dict):return {'ok':False,'errors':['Manifest requires an object'],'warnings':[]}
    if data.get('format')!='skill-tree-manifest':errors.append('Unsupported manifest format')
    if data.get('role') not in {'source','target'}:errors.append('Unsupported manifest role')
    actual_role='source' if (root/'skill-tree/skills').is_dir() else 'target'
    if data.get('role')!=actual_role:errors.append('Manifest role disagrees with repository layout')
    for field in ['queue','state','latest_audit']:
        if field not in data:errors.append('Missing manifest field: '+field)
    for field,kind in [('files',list),('catalog',list),('source_digests',dict),('history',dict),('retention',dict),('policy_references',list),('validation_commands',list),('audit_scopes',list)]:
        if not isinstance(data.get(field),kind):errors.append('Invalid manifest field: '+field)
    if errors:return {'ok':False,'errors':errors,'warnings':warnings}
    def portable(value,label,must_exist=True):
        if not isinstance(value,str) or not value or Path(value).is_absolute() or re.match(r'^[A-Za-z]:',value) or '..' in Path(value).parts or '\\' in value:
            errors.append('Invalid repository-relative path: '+label);return None
        target=root/value
        if must_exist and not target.is_file():errors.append('Missing manifest file: '+value)
        return target
    seen=set();canonical=set()
    for item in data['files']:
        if not isinstance(item,dict) or item.get('role') not in {'canonical','generated-index-and-active-state'} or item.get('owner')!='skill-tree':
            errors.append('Invalid manifest file entry');continue
        path=item.get('path');target=portable(path,'files')
        if target is None:continue
        if path in seen:errors.append('Duplicate manifest file: '+path)
        seen.add(path)
        if item['role']=='canonical':canonical.add(path)
    if set(data['source_digests'])!=canonical:errors.append('Manifest source digests do not cover canonical files')
    for path,expected in data['source_digests'].items():
        target=portable(path,'source_digests')
        if not isinstance(expected,str) or not re.fullmatch(r'[a-f0-9]{64}',expected):errors.append('Invalid source digest: '+path)
        elif target is not None and target.is_file() and wf.file_hash(target)!=expected:errors.append('Stale manifest source digest: '+path)
    for field in ['queue','state']:
        value=data.get(field)
        if value is not None:portable(value,field)
    if data['role']=='target' and (data.get('queue')!='skill-tree/documents/future.md' or data.get('state')!='skill-tree/documents/future.json'):
        errors.append('Target manifest requires canonical queue and state paths')
    if data.get('queue') is not None and data.get('state') is None:errors.append('A queue requires an indexed checkpoint file')
    for path in data['policy_references']:portable(path,'policy_references')
    if any(not isinstance(command,str) or not command.strip() for command in data['validation_commands']):errors.append('Invalid manifest validation commands')
    history=data['history']
    for key in ['task_outcomes','audits','runs']:
        if key not in history:errors.append('Missing manifest history location: '+key)
        else:portable(history[key],'history',must_exist=False)
    retention=data['retention']
    if any(type(retention.get(key)) is not int or retention[key]<1 for key in ['audits','runs']) or not isinstance(retention.get('pins'),list):errors.append('Invalid manifest retention policy')
    entries=set()
    for skill in data['catalog']:
        if not isinstance(skill,dict) or not isinstance(skill.get('resources'),list) or not isinstance(skill.get('name'),str):
            errors.append('Invalid manifest skill entry');continue
        entrypoint=skill.get('entrypoint');target=portable(entrypoint,'catalog')
        if target is None:continue
        if not re.fullmatch(r'skill-tree-[a-z0-9-]+',skill['name']) or target.name!='SKILL.md' or target.parent.name!=skill['name']:errors.append('Invalid manifest skill entrypoint: '+entrypoint)
        if entrypoint in entries:errors.append('Duplicate manifest skill entrypoint: '+entrypoint)
        entries.add(entrypoint)
        for resource in skill['resources']:
            resource_path=portable(resource,'catalog.resources')
            if resource_path is not None and target.parent not in resource_path.parents:errors.append('Skill resource escapes package: '+resource)
        if entrypoint not in skill['resources']:errors.append('Skill resources omit entrypoint: '+entrypoint)
    if data['role']=='target':
        actual=wf.installed_catalog(root)
        if entries!={item['entrypoint'] for item in actual}:errors.append('Installed skill catalog is stale; refresh the manifest')
        expected_resources={item['entrypoint']:item['resources'] for item in actual}
        for skill in data['catalog']:
            if isinstance(skill,dict) and skill.get('entrypoint') in expected_resources and skill.get('resources')!=expected_resources[skill['entrypoint']]:errors.append('Installed skill resources are stale: '+skill['entrypoint'])
    else:
        actual={p.relative_to(root).as_posix() for p in (root/'skill-tree/skills').glob('*/SKILL.md')}
        if entries!=actual:errors.append('Source skill catalog is stale; refresh the manifest')
    for audit in data['audit_scopes']:
        if not isinstance(audit,dict):errors.append('Invalid audit navigation entry')
        else:portable(audit.get('path'),'audit_scopes')
    latest=data.get('latest_audit')
    if latest is not None:
        if not isinstance(latest,dict) or latest not in data['audit_scopes']:errors.append('Latest audit must match an audit navigation entry')
        elif not latest.get('fresh'):warnings.append('Latest recorded audit is stale; historical verdicts remain unchanged')
    if data.get('queue')=='skill-tree/documents/future.md':
        try:
            store=wf.Store(root);text=store.text();tasks=wf.parse(text)
            state=json.loads(store.state.read_text())
            if not isinstance(state,dict) or state.get('format')!=wf.FORMAT or 'active_run' not in state:raise wf.WorkflowError('Unsupported checkpoint schema')
            if state.get('source_hash')!=wf.digest(text.encode()):errors.append('Queue index source hash is stale')
            if state.get('tasks')!=wf.index(text):errors.append('Queue index differs from task definitions')
            completed={o['task_id'] for o in store.outcomes() if o.get('disposition')=='completed'}
            wf.validate_dependencies(tasks,completed)
            run=state['active_run']
            if run is not None:
                wf.validate_run(run)
                open_ids={task['id'] for task in tasks if task['queue']=='Prioritized Next Changes'}
                required=set(run['snapshot']+run['required_ids'])
                if not required.issubset(open_ids|completed):errors.append('Active checkpoint references missing required work without completion evidence')
                if not set(run['completed_ids']).issubset(completed):errors.append('Active checkpoint completion IDs lack recorded outcomes')
                for field in ['root_task_id','current_task_id']:
                    if run[field] is not None and run[field] not in open_ids|completed:errors.append('Active checkpoint has an unknown task pointer: '+field)
        except (OSError,ValueError,KeyError,TypeError) as exc:errors.append('Invalid queue/checkpoint: '+str(exc))
    return {'ok':not errors,'errors':errors,'warnings':warnings}

def validate(root,strict=False):
    errors=[];warnings=[];docs=root/'skill-tree/documents'
    for rel in ['README.md','AGENTS.md','skill-tree/skill-tree.json','skill-tree/documents/future.json']+['skill-tree/documents/'+name for name in REQUIRED]:
        if not (root/rel).is_file():errors.append('Missing '+rel)
    if (docs/'future.md').exists():
        result=load('validate-future-document').validate(docs/'future.md',strict);errors+=result['errors']
    result=validate_manifest(root);errors+=result['errors'];warnings+=result['warnings']
    if strict:
        rules=load('validate-document-rules')
        for path in sorted(docs.glob('*.md')):errors+=rules.check(path,warnings_as_errors=True)
    return {'ok':not errors,'errors':errors,'warnings':warnings}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);parser.add_argument('--strict',action='store_true');parser.add_argument('--format',choices=['text','json'],default='text');args=parser.parse_args(argv);result=validate(args.root,args.strict);print(json.dumps(result,indent=2));return int(not result['ok'])
if __name__=='__main__':raise SystemExit(main())
