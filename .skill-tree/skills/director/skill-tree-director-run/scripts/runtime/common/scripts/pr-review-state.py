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
import tempfile
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

def instruction_lines(text):
    visible = []
    fence = None
    quoted = False
    for line in text.splitlines():
        marker = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if fence is not None:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
        elif not line.strip():
            quoted = False
        elif re.match(r'^ {0,3}>', line):
            quoted = True
        elif not quoted:
            if marker and (marker[1][0] == '~' or '`' not in marker[2]):
                fence = marker[1]
            elif not line.startswith(('    ', '\t')):
                visible.append(line)
                continue
        visible.append('\ufffc' if line.strip() else '')
    return '\n'.join(visible)


def instructions(text):
    # Keep positions for inline branch names following direct instruction words.
    quoted = r'(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)|"[^"]*"|«[^»]*»|“[^”]*”|(?<!\w)\x27[^\x27]*\x27(?!\w)'
    return re.sub(quoted, lambda match: '\ufffc' * len(match[0]), text, flags=re.S)


def branch_operand(text, offset):
    return re.compile(r'[ \t]*(?:(`+)([\w./-]+)\1|([\w./-]+))').match(text, offset)

def parameters(current_branch, payload):
    raw=instruction_lines(payload.get('instruction','')) if payload.get('instruction_origin','owner')=='owner' else ''
    text=instructions(raw)
    original=text
    positive=[];negative=[]
    for match in re.finditer(r'\bmerge\s*=\s*(true|false)\b',text,re.I):
        (positive if match[1].casefold()=='true' else negative).append(match.span())
    neg=r'\b(?:без\s+(?:merge|мерд?ж\w*|слияния)|не\s+(?:merge|мерд?ж\w*|см[е]?рд?ж\w*|вмерд?ж\w*|соль[её]м|слей|сливай|сливать|слить)|without\s+merge|do\s+not\s+merge|don[’\x27]t\s+merge|no\s+merge)\b'
    negative+= [m.span() for m in re.finditer(neg,text,re.I)]
    scrub=list(text)
    for start,end in negative:
        scrub[start:end]=' '*(end-start)
    affirmative=''.join(scrub)
    natural_original=''.join(' ' if a==' ' and b!=' ' else b for a,b in zip(affirmative,original))
    action=r'(?:см[е]?рд?жи(?:ть)?|смржи|вмерд?жи(?:ть)?|соль[её]м|слей|сливай|слить)'
    pos=r'\b(?:with\s+merge|с\s+(?:merge|мерд?жем)|(?:затем\s+)?'+action+r'|then\s+merge)\b'
    positive+=[m.span() for m in re.finditer(pos,affirmative,re.I)]
    if 'merge' in payload:
        if type(payload['merge']) is not bool:raise ReviewError('merge requires a boolean')
        if payload.get('instruction_origin','owner')=='owner':
            (positive if payload['merge'] else negative).append((0,0))
    if positive and negative:raise ReviewError('Conflicting explicit merge instructions require clarification')
    choices={'source_branch':[], 'target_branch':[]}
    for key in choices:
        if payload.get(key):choices[key].append(payload[key])
        for match in re.finditer(r'\b'+key+r'[ \t]*=',original,re.I):
            operand=branch_operand(raw,match.end())
            if not operand:raise ReviewError('An explicit named '+key+' is required')
            choices[key].append(operand[2] or operand[3])
    for match in re.finditer(r'\b(?:из|from)\b(?=[ \t])',original,re.I):
        source=branch_operand(raw,match.end())
        if source is None:continue
        destination=re.compile(r'[ \t]+(?:в|to|into)\b',re.I).match(original,source.end())
        if destination is None:continue
        target=branch_operand(raw,destination.end())
        if not target:raise ReviewError('An explicit named target branch is required')
        choices['source_branch'].append(source[2] or source[3]);choices['target_branch'].append(target[2] or target[3])
    target_clause=r'\b(?:'+action+r'|then\s+merge|with\s+merge|мерд?жем)(?:[ \t]+(?:эту[ \t]+)?ветку)?[ \t]+(?:в|into|to)\b'
    for match in re.finditer(target_clause,natural_original,re.I):
        target=branch_operand(raw,match.end())
        if not target:raise ReviewError('An explicit named target branch is required')
        choices['target_branch'].append(target[2] or target[3])
    result={}
    for key,default in [('source_branch',current_branch),('target_branch','develop')]:
        values=set(choices[key])
        if len(values)>1:raise ReviewError('Conflicting '+key+' instructions require clarification')
        result[key]=next(iter(values)) if values else default
        if not result[key] or result[key].startswith('-'):raise ReviewError('An explicit named source and target branch is required')
    if result['source_branch']==result['target_branch']:raise ReviewError('Source and target branches differ')
    result['merge']=bool(positive)
    result['merge_explicit']=bool(positive or negative)
    result['target_explicit']=bool(choices['target_branch'])
    result['authorization']={'pr':payload.get('instruction_origin','owner')=='owner','merge':bool(positive),'origin':payload.get('instruction_origin','owner'),'instruction_digest':digest(text),'target_branch':result['target_branch']}
    return result

def github_remote(url):
    match = re.fullmatch(r'(?:https://|ssh://git@|git@)([\w.-]+)[/:]([\w.-]+/[\w.-]+?)(?:\.git)?', url)
    if not match:
        raise ReviewError('Select a credential-free GitHub remote with an exact owner/repository')
    return match[1].lower(), match[2].lower()


def publication_repositories(root, payload, base_url, remote):
    if not {'head_remote', 'head_repository', 'base_repository'}.intersection(payload):
        return {}
    head_remote = payload.get('head_remote', remote)
    if head_remote not in ws.git(root, 'remote').splitlines():
        raise ReviewError('Unknown source-branch push remote')
    destinations = ws.git(root, 'remote', 'get-url', '--push', '--all', head_remote).splitlines()
    if len(destinations) != 1:
        raise ReviewError('Select one push destination for the publication head')
    base_host, base = github_remote(base_url)
    head_host, head = github_remote(destinations[0])
    expected_head, expected_base = payload.get('head_repository', head), payload.get('base_repository', base)
    if (head_host != base_host or not isinstance(expected_head, str) or expected_head.lower() != head
            or not isinstance(expected_base, str) or expected_base.lower() != base):
        raise ReviewError('Selected publication repositories differ from the configured Git remotes')
    return {'base_repository': base, 'head_repository': head, 'head_remote': head_remote}


def repository_scope(snapshot):
    return {key: snapshot[key] for key in ('base_repository', 'head_repository', 'head_remote') if key in snapshot}


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
    repositories = publication_repositories(root, payload, url, remote)
    ws.git(root,'fetch','--no-tags',remote)
    target=ws.branch(root,params['target_branch']);ws.branch(root,params['source_branch'])
    base=ws.git(root,'rev-parse','--verify','refs/remotes/'+remote+'/'+target+'^{commit}')
    head=ws.git(root,'rev-parse','HEAD');changed=ws.git(root,'diff','--name-only',base+'...'+head).splitlines()
    if not changed:raise ReviewError('No changes relative to the current target branch')
    return {**params,**repositories,'repo_id':ws.repo_id(root),'remote':remote,'remote_id':hashlib.sha256(url.encode()).hexdigest(),'head':head,'base_oid':base,'changed_files':changed,'candidate_objects_required':True}

def identity(snapshot):
    return {**repository_scope(snapshot),**{key:snapshot[key] for key in ['repo_id','remote','source_branch','target_branch','head','base_oid']},'remote_id':snapshot.get('remote_id')}

def review_key(snapshot):
    return digest({key:snapshot.get(key) for key in ['head','base_oid','target_branch','changed_files','candidate_objects_required','threads','reviews','comments','checks','checks_known','required_checks_missing','approvals_known','approvals_required','approved']})

def decision_context(snapshot,purpose='finding-resolution'):
    if not isinstance(purpose,str) or not re.fullmatch(r'[a-z][a-z0-9-]*',purpose):raise ReviewError('Review decision requires an exact bounded purpose')
    scope={key:snapshot.get(key) for key in ['repo_id','remote','remote_id','source_branch','target_branch','head','base_oid']}
    scope.update(repository_scope(snapshot))
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

def reconcile(record,snapshot,*,retarget=None):
    record=deepcopy(record)
    for key in ['repo_id','remote','remote_id','source_branch','base_repository','head_repository','head_remote']:
        if record['identity'].get(key)!=snapshot.get(key):raise ReviewError('Publication repository/source identity conflict')
    previous_target=record['identity']['target_branch']
    target_changed=previous_target!=snapshot['target_branch']
    if target_changed:
        authorization=(retarget or {}).get('authorization',{})
        if not ((retarget or {}).get('target_explicit') and authorization.get('origin')=='owner'
                and authorization.get('pr') and authorization.get('target_branch')==snapshot['target_branch']):
            raise ReviewError('Publication retarget requires its explicit identity and a current owner instruction for the new target')
        previous=deepcopy(record['authorization']);previous.setdefault('target_branch',previous_target)
        record.setdefault('authorization_history',[]).append(previous)
        record['authorization']=deepcopy(authorization)
    pr=snapshot.get('pr')
    if record.get('pr') and pr and record['pr']['id']!=pr['id']:raise ReviewError('Existing PR identity conflict')
    if pr:record['pr']=pr
    current_identity=identity(snapshot)
    changed=record['identity']!=current_identity or record.get('snapshot_key')!=review_key(snapshot)
    if record['identity']!=current_identity:
        for finding in record.get('findings',{}).values():
            if finding.get('status') in {'verified-fixed','dismissed'}:
                finding['status']='open'
                for key in ('verified_head','verification_evidence','dismissal_reason'):
                    finding.pop(key,None)
    record['identity']=identity(snapshot);record['snapshot_key']=review_key(snapshot)
    if snapshot.get('state')=='CLOSED':
        record['status']='blocked';record['blocked_reason']='The selected PR is closed without merge';return record
    if snapshot.get('state')=='MERGED':
        if not record.get('pr') or not record['pr'].get('id'):raise ReviewError('Merged status requires the existing provider PR identity')
        integration = snapshot.get('merge_commit')
        if not isinstance(integration, str) or not re.fullmatch(r'(?:[a-f0-9]{40}|[a-f0-9]{64})', integration):
            raise ReviewError('Merged provider result lacks merge commit evidence')
        if target_changed or record.get('merge_commit') != integration:
            record.pop('local_target_sync', None)
        record['status'] = 'merged'
        record['merge_commit'] = integration
        record['same_repository'] = snapshot.get('same_repository') is True
        return record
    if changed:
        record.pop('review',None)
        record['status']='pr-review-in-progress'
    return record

DEVELOPMENT_POLICIES = frozenset({'direct-replacement', 'network-polling'})
POLICY_FINDING_PREFIX = 'development-policy:'


def enabled_development_policies(store):
    if store is None:
        return DEVELOPMENT_POLICIES
    root = Path(store.source_root)
    profile = root / '.skill-tree/installation/profile.json'
    config = root / '.skill-tree/development-policies.json'
    if profile.is_symlink() or config.is_symlink():
        raise ReviewError('Owned development policy paths cannot use symlinks')
    try:
        active = json.loads(profile.read_text()).get('development_policies') if profile.exists() else None
        config_bytes = config.read_bytes() if config.exists() else None
        overrides = json.loads(config_bytes).get('policies', {}) if config_bytes is not None else {}
    except (OSError, ValueError, AttributeError) as error:
        raise ReviewError('Cannot read the owned development policy installation') from error
    if active is None and config_bytes is None:
        return DEVELOPMENT_POLICIES
    actual = hashlib.sha256(config_bytes).hexdigest() if config_bytes is not None else None
    if not isinstance(active, dict) or active.get('input_digest') != actual:
        raise ReviewError('Development policies require a current owned installation profile')
    rows = active.get('policies')
    if (not isinstance(rows, list) or len(rows) != len(DEVELOPMENT_POLICIES) or
            any(not isinstance(row, dict) or type(row.get('id')) is not str or
                type(row.get('enabled')) is not bool for row in rows) or
            {row['id'] for row in rows} != DEVELOPMENT_POLICIES):
        raise ReviewError('The owned development policies are invalid')
    if (not isinstance(overrides, dict) or
            any(row['enabled'] is not overrides.get(row['id'], True) for row in rows)):
        raise ReviewError('The owned development policy settings differ from project configuration')
    return {row['id'] for row in rows if row['enabled']}


def policy_source(root, snapshot, path, line, excerpt):
    head = snapshot['head']
    if (not re.fullmatch('[a-f0-9]{40}|[a-f0-9]{64}', head) or type(path) is not str or
            path not in snapshot['changed_files'] or any(part in {'', '.', '..'} for part in path.split('/')) or
            '\\' in path or '\0' in path or type(line) is not int or line < 1 or
            type(excerpt) is not str or not excerpt.strip()):
        raise ReviewError('A policy violation requires a changed file and exact candidate source line')
    try:
        result = subprocess.run(['git', '--no-replace-objects', '-C', str(root), 'show', head + ':' + path],
                                capture_output=True, timeout=10)
        lines = result.stdout.decode('utf-8').split('\n')
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as error:
        raise ReviewError('Cannot read the policy candidate source') from error
    if result.returncode or line > len(lines) or lines[line-1].removesuffix('\r') != excerpt:
        raise ReviewError('Policy evidence differs from the exact candidate source')


def policy_findings(store, snapshot, observations, enabled):
    if not isinstance(observations, list) or (observations and store is None):
        raise ReviewError('Policy observations require an owned review workspace and a list')
    findings = {}
    notes = []
    for row in observations:
        if (not isinstance(row, dict) or type(row.get('policy')) is not str or
                row['policy'] not in DEVELOPMENT_POLICIES):
            raise ReviewError('Select an exact built-in development policy')
        if row['policy'] not in enabled:
            continue
        if row.get('outcome') == 'inconclusive':
            missing = row.get('missing_fact')
            if type(missing) is not str or not missing.strip():
                raise ReviewError('An inconclusive policy observation requires the missing fact')
            notes.append({'policy': row['policy'], 'outcome': 'inconclusive', 'missing_fact': missing})
            continue
        if row.get('outcome') != 'violation':
            raise ReviewError('Unknown development policy observation outcome')
        fields = ('id', 'cause', 'consequence', 'severity')
        if (any(type(row.get(field)) is not str or not row[field].strip() for field in fields) or
                not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}', row['id'])):
            raise ReviewError('A policy violation requires a stable ID, source-backed cause, consequence and severity')
        policy_source(store.source_root, snapshot, row.get('path'), row.get('line'), row.get('source_line'))
        key = POLICY_FINDING_PREFIX + row['policy'] + ':' + row['id']
        if key in findings:
            raise ReviewError('Duplicate development policy finding: ' + key)
        findings[key] = {**{field: row[field] for field in (*fields, 'path', 'line', 'source_line')},
                         'id': key, 'development_policy': row['policy'], 'status': 'open',
                         'observed_head': snapshot['head']}
    return findings, notes


def finding_policy(finding):
    policy = finding.get('development_policy')
    key = finding.get('id')
    if type(policy) is str and policy in DEVELOPMENT_POLICIES and isinstance(key, str) and key.startswith(
            POLICY_FINDING_PREFIX + policy + ':'):
        return policy
    return None


def unresolved_findings(record, snapshot, store=None, enabled=None):
    if enabled is None:
        enabled = enabled_development_policies(store)
    return [finding for finding in record.get('findings', {}).values()
            if ((policy := finding_policy(finding)) is None or policy in enabled)
            and not finding_verified(finding, snapshot)]


def reviewed(record,snapshot,payload,*,store=None):
    record=inspected(record,snapshot,payload)
    if record['status']=='merged':return record
    if record['status']=='blocked':raise ReviewError(record['blocked_reason'])
    if payload.get('head')!=snapshot['head'] or payload.get('base_oid')!=snapshot['base_oid'] or payload.get('target_branch')!=snapshot['target_branch']:
        raise ReviewError('Review evidence does not match current head/base/target')
    if set(payload.get('files',[]))!=set(snapshot['changed_files']) or not payload.get('context_inspected'):
        raise ReviewError('Review requires the full diff and necessary surrounding context')
    if not payload.get('discussions_inspected') or not payload.get('checks_inspected'):
        raise ReviewError('Review requires current reviews, inline discussions and CI results')
    enabled = enabled_development_policies(store)
    observed, notes = policy_findings(store, snapshot, payload.get('development_policy_observations', []), enabled)
    ledger=record.setdefault('findings',{})
    findings=deepcopy(payload.get('findings',[]))
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get('id'), str) or 'development_policy' in finding:
            raise ReviewError('Submit new policy findings through development policy observations and use string finding IDs')
        if finding['id'].startswith(POLICY_FINDING_PREFIX):
            previous = ledger.get(finding['id'], {})
            if not finding_policy(previous) or finding.get('status') not in {'verified-fixed', 'dismissed'} or finding['id'] in observed:
                raise ReviewError('A previous policy finding requires current-head resolution evidence')
            finding.update({key: previous[key] for key in ('development_policy', 'path', 'line', 'source_line', 'observed_head')})
        elif (finding.get('path') not in snapshot['changed_files'] or
              type(finding.get('line')) is not int or finding['line'] < 1):
            raise ReviewError('Actionable finding requires a current changed-file location')
        if any(not finding.get(key) for key in ['id','cause','consequence','severity']):
            raise ReviewError('Actionable finding requires location, cause, consequence and severity')
        if finding.get('status') in {'verified-fixed','dismissed'} and (finding.get('verified_head')!=snapshot['head'] or not finding.get('verification_evidence')):
            raise ReviewError('Fixed finding requires current-head verification evidence')
        if finding.get('status')=='dismissed' and not finding.get('dismissal_reason'):
            raise ReviewError('Dismissed finding requires an evidence-backed reason')
        ledger[finding['id']]=deepcopy(finding)
    ledger.update(observed)
    findings.extend(observed.values())
    unresolved=unresolved_findings(record,snapshot,enabled=enabled)
    record['review']={'key':review_key(snapshot),'head':snapshot['head'],'base_oid':snapshot['base_oid'],'findings':findings,'unresolved':len(unresolved),'independent_approval':False,'evidence':payload.get('evidence',[])}
    if notes:
        record['review']['development_policy_notes'] = notes
    record['rounds']=record.get('rounds',[])+[deepcopy(record['review'])]
    return record


def finding_verified(finding,snapshot):
    return (finding.get('status') in {'verified-fixed','dismissed'}
            and finding.get('verified_head')==snapshot['head'] and bool(finding.get('verification_evidence')))


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
    scope.update(repository_scope(record['identity']))
    if context.get('id')!='review-hook:'+digest(scope) or context.get('semantic_fingerprint')!=digest({'scope':scope,'review_key':record.get('snapshot_key')}):raise ReviewError('The review context differs from the actual publication review identity')
    key=record.get('snapshot_key');core=record.get('review') if phase=='after' else record.get('inspection') or record.get('review') if phase=='during' else None
    if phase in {'during','after'} and (not core or core.get('key')!=key):raise ReviewError('The configured review phase requires current full core review or inspection')
    if phase=='after' and core.get('unresolved')!=0:raise ReviewError('The after phase requires a current core review with zero unresolved findings')
    if record.get('status') in {'blocked','merged'}:raise ReviewError('The publication is not an active review scope')
    return {'publication_id':publication_id,'publication_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'phase':phase,
        'core_review_key':core.get('key') if core else None,'core_review_digest':digest(core) if core else None}


def _review_root(store,record,package_root=None):
    def owns_review(candidate):
        manifest=candidate/'references/plugin-bindings.json'
        return manifest.is_file() and json.loads(manifest.read_text()).get('operation')==REVIEW_OPERATION

    if package_root is not None:
        candidate=Path(package_root).absolute()
        if not owns_review(candidate):raise ReviewError('The explicit package must own the PR review operation')
        return candidate
    candidate=Path(__file__).parent.parent
    composed=(candidate/'references/plugin-bindings.json').is_file()
    if not owns_review(candidate):
        relative=(record or {}).get('review_requirements',{}).get('operation_package')
        if relative:
            if Path(relative).is_absolute() or any(part in {'','..','.'} for part in relative.split('/')):raise ReviewError('The frozen review operation package must remain repository-relative')
            candidate=store.source_root/relative
            if not owns_review(candidate):raise ReviewError('The frozen PR review operation package is missing or changed')
    if owns_review(candidate):return candidate
    registry=store.source_root/'.skill-tree/installation/plugins.json'
    if registry.is_file():
        value=json.loads(registry.read_text());packages=value.get('packages',{})
        # Source-checkout callers can still use the existing attached review-chain path.
        if any(row.get('operation')==REVIEW_OPERATION and row.get('enabled') and
               (composed or packages.get(row.get('plugin_id'),{}).get('adaptation',{}).get('invocation_policy'))
               for row in value.get('bindings',[])):raise ReviewError('Configured review plugins require the explicitly trusted composed operation package')
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
        item=deepcopy(finding);item.pop('development_policy',None);item['id']=attempt['id']+':'+str(finding['id']);item['source_attempt_id']=attempt['id'];output.append(item)
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
    scope.update(repository_scope(snapshot))
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


def api_lock_admission(store,snapshot):
    root=Path(store.source_root)
    script=Path(__file__).with_name('api-contract-locks.js')
    if not script.is_file():script=Path(__file__).resolve().parents[2]/'lib/api-contract-locks.js'
    try:
        result=subprocess.run(['node',str(script),'review',str(root)],input=json.dumps(snapshot),
                              capture_output=True,text=True,timeout=30)
    except (OSError,subprocess.TimeoutExpired) as error:
        raise ReviewError('API lock review did not return current evidence') from error
    try:evidence=json.loads(result.stdout)
    except ValueError:
        raise ReviewError('API lock review is unavailable: '+result.stderr.strip())
    if result.returncode or evidence.get('failures'):
        raise ReviewError('API lock review blocked readiness: '+('; '.join(evidence.get('failures',[])) or 'no current evidence'))
    if not evidence.get('reviewer'):return None
    return {'head':snapshot['head'],'base_oid':snapshot['base_oid'],'affected':evidence['affected'],
            'plugin_id':'api-lock-review','stage':'before-pr-ready'}


def ready(record,snapshot,*,store=None):
    ws.validate_hook_references(record)
    if store is not None:record=_retire_review_hook_references(store,record,snapshot)
    record=reconcile(record,snapshot)
    if record['status']=='merged':return record
    if record['status']=='blocked':raise ReviewError(record['blocked_reason'])
    if (record.get('hook_chains') or any(record.get('review_requirements',{}).get('phases',{}).values())) and store is None:raise ReviewError('Current hook readiness requires the live owned store')
    if store is not None:
        _review_requirement_admission(store,record,snapshot);hook_admission(store,record,snapshot)
        api_locks=api_lock_admission(store,snapshot)
        if api_locks:record['api_lock_review']=api_locks
        else:record.pop('api_lock_review',None)
    if not record.get('pr') or not record['pr'].get('id') or not record['pr'].get('url'):raise ReviewError('PR readiness requires the existing provider PR identity and URL')
    review=record.get('review')
    if not review or review['key']!=review_key(snapshot):
        raise ReviewError('Current full review or actionable finding verification remains incomplete')
    unresolved = unresolved_findings(record, snapshot, store)
    if unresolved:
        policy = next((finding for finding in unresolved if finding_policy(finding)), None)
        if policy:
            raise ReviewError('Development policy ' + policy['development_policy'] + ' blocked review at ' +
                              policy['path'] + ':' + str(policy['line']) + ': ' + policy['cause'])
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
    if (not authorization.get('merge') or not authorization.get('pr') or authorization.get('origin')!='owner'
            or authorization.get('target_branch')!=snapshot['target_branch']):raise ReviewError('Merge lacks explicit owner authorization for the current target')
    if snapshot.get('approvals_known') is not True:raise ReviewError('Required approval policy is unknown')
    if snapshot.get('approvals_required') and not snapshot.get('approved'):raise ReviewError('External approval requirements remain unsatisfied')
    if snapshot.get('mergeable')!='MERGEABLE':raise ReviewError('Merge conflict or unknown mergeability')
    return record

class GitHub:
    """Authorized gh fallback; connectors can supply the same normalized snapshots."""
    def __init__(self, root, repository, head_repository=None):
        self.root = Path(root)
        for name in (repository, head_repository or repository):
            if not isinstance(name, str) or not re.fullmatch(r'[\w.-]+/[\w.-]+', name):
                raise ReviewError('Explicit GitHub owner/repository required')
        self.repository = repository.lower()
        self.head_repository = (head_repository or repository).lower()
        self.explicit_head = head_repository is not None

    @classmethod
    def from_preflight(cls, root, checked):
        if not checked.get('base_repository') or not checked.get('head_repository'):
            raise ReviewError('Select the reviewed base and head remotes in publication preflight')
        return cls(root, checked['base_repository'], checked['head_repository'])
    def gh(self,*args):
        if '--paginate' in args and '--slurp' not in args:args=(*args,'--slurp')
        result=subprocess.run(['gh',*map(str,args)],cwd=self.root,capture_output=True,text=True,timeout=45)
        if result.returncode:raise ReviewError('GitHub access or operation failed; preserve the publication checkpoint')
        data=json.loads(result.stdout) if result.stdout.strip() else None
        if '--slurp' in args and data and isinstance(data[0],list):return [item for page in data for item in page]
        return data
    def _matches(self, pull, source, target):
        head, base = pull.get('head') or {}, pull.get('base') or {}
        head_repo = (head.get('repo') or {}).get('full_name', '').lower()
        base_repo = (base.get('repo') or {}).get('full_name', '').lower()
        return (head_repo == self.head_repository and head.get('ref') == source and base.get('ref') == target
                and (base_repo == self.repository or (not self.explicit_head and not base_repo)))

    def find(self, source, target, expected_head=None):
        owner = self.head_repository.split('/')[0]
        prs = self.gh('api', '--method', 'GET', 'repos/' + self.repository + '/pulls',
                      '-f', 'state=all', '-f', 'head=' + owner + ':' + source, '-f', 'base=' + target, '--paginate')
        matches = [pull for pull in prs if self._matches(pull, source, target)]
        opened = [pull for pull in matches if pull['state'] == 'open']
        if len(opened) > 1:
            raise ReviewError('Multiple matching open PRs require explicit selection')
        if opened and expected_head and opened[0]['head'].get('sha') != expected_head:
            raise ReviewError('The open PR head differs from the selected publication commit')
        merged = [pull for pull in matches if pull.get('merged_at') and expected_head and pull['head'].get('sha') == expected_head]
        return (opened or sorted(merged, key=lambda pull:pull['merged_at'], reverse=True) or [None])[0]

    def ensure(self, source, target, title, body, draft=False, expected_head=None):
        existing = self.find(source, target, expected_head)
        endpoint = 'repos/' + self.repository + '/pulls'
        if existing:
            if existing.get('merged_at'):
                return existing
            result = self.gh('api', '--method', 'PATCH', endpoint + '/' + str(existing['number']),
                             '-f', 'title=' + title, '-f', 'body=' + body)
        else:
            owner, name = self.head_repository.split('/')
            foreign = self.head_repository != self.repository
            label = owner + ':' + source if foreign else source
            extra = ('-f', 'head_repo=' + name) if foreign and owner == self.repository.split('/')[0] else ()
            result = self.gh('api', '--method', 'POST', endpoint, '-f', 'head=' + label, *extra, '-f', 'base=' + target,
                             '-f', 'title=' + title, '-f', 'body=' + body, '-F', 'draft=' + str(draft).lower())
        if not self._matches(result, source, target) or (expected_head and result['head'].get('sha') != expected_head):
            raise ReviewError('Provider returned a different PR repository, ref or source commit')
        return result
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
        raw=self.gh('pr','view',number,'--repo',self.repository,'--json','id,number,url,state,headRefOid,headRefName,baseRefOid,baseRefName,mergeable,reviewDecision,mergeCommit,statusCheckRollup,changedFiles,isCrossRepository,headRepository,headRepositoryOwner')
        if raw['headRefName']!=context['source_branch'] or raw['baseRefName']!=context['target_branch']:
            raise ReviewError('Provider PR branch identity differs from preflight')
        observed_owner = (raw.get('headRepositoryOwner') or {}).get('login', '')
        observed_repo = (raw.get('headRepository') or {}).get('name', '')
        observed = (observed_owner + '/' + observed_repo).lower()
        if (context.get('base_repository', self.repository) != self.repository
                or context.get('head_repository', self.head_repository) != self.head_repository
                or ((self.explicit_head or observed != '/') and observed != self.head_repository)
                or (self.explicit_head and (raw['headRefOid'] != context['head']
                    or raw['state'] != 'MERGED' and raw['baseRefOid'] != context['base_oid']))):
            raise ReviewError('Provider PR source repository or selected commit identity differs from preflight')
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
        return {**context,'head':raw['headRefOid'],'base_oid':raw['baseRefOid'],'candidate_objects_required':True,'changed_files':[f['filename'] for f in files],'pr':{'id':raw['id'],'number':raw['number'],'url':raw['url']},'state':raw['state'],'merge_commit':(raw.get('mergeCommit') or {}).get('oid'),'mergeable':raw['mergeable'],'reviews':reviews,'comments':comments+inline,'threads':threads,'checks':checks,'checks_known':policy.get('checks_known') is True,'required_checks_missing':sorted(required-{c['name'] for c in checks}),'approvals_known':policy.get('approvals_known') is True,'approvals_required':policy.get('approvals_required',True),'approved':raw.get('reviewDecision')=='APPROVED','same_repository':raw.get('isCrossRepository') is False}
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

def registered_target(root, ref):
    worktrees = ws.local_git(root, 'worktree', 'list', '--porcelain', '-z').stdout.decode()
    matches = []
    for entry in worktrees.split('\0\0'):
        location, *fields = entry.split('\0')
        if 'branch ' + ref in fields:
            if not location.startswith('worktree ') or any(field.startswith(('locked', 'prunable')) for field in fields):
                raise ReviewError('The target worktree is locked or unavailable')
            matches.append(Path(location.removeprefix('worktree ')).resolve())
    if len(matches) > 1:
        raise ReviewError('Multiple worktrees have the target checked out')
    return matches[0] if matches else None


def fast_forward_checked_out_target(root, worktree, checkout, tracking, remote_head):
    # The protected ref update needs a different Git HEAD from the target.
    preparation = {
        'source_ref': tracking, 'source_head': remote_head,
        'target_ref': checkout['ref'], 'target_head': checkout['head'],
        'incoming': ws.local_incoming(worktree, checkout['head'], remote_head),
        'allow_unrelated_staged': True,
    }
    if root != worktree:
        ws.run_local_merge(worktree, root, preparation, fast_forward=True)
        return
    with tempfile.TemporaryDirectory(prefix='skill-tree-pr-target-') as temporary:
        writer = Path(temporary).resolve() / 'ref-writer'
        ws.local_git(root, 'worktree', 'add', '--detach', '--no-checkout', '--', writer, remote_head)
        initialized = False
        try:
            ws.local_git(writer, 'read-tree', '--reset', '-u', remote_head)
            initialized = True
            ws.run_local_merge(worktree, writer, preparation, fast_forward=True)
        finally:
            # The incomplete checkout exists only inside private scratch space.
            options = () if initialized else ('--force',)
            ws.local_git(root, 'worktree', 'remove', *options, '--', writer)


def fast_forward_local_target(root, ref, local_head, tracking, remote_head):
    worktree = registered_target(root, ref)
    if worktree is not None:
        checkout = ws.checked_out_branch(worktree)
        if (checkout['ref'], checkout['head']) != (ref, local_head) or ws.common_dir(worktree) != ws.common_dir(root):
            raise ReviewError('The exact target worktree changed during synchronization')
        fast_forward_checked_out_target(root, worktree, checkout, tracking, remote_head)
        return
    # Git refuses a local fetch into a branch checked out in any worktree.
    # A non-forced exact refspec also protects any intervening local commits.
    ws.local_git_policy(root, merge=False, signed=True)
    try:
        ws.local_git(root, 'fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
                     '--refmap=', '--', '.', remote_head + ':' + ref)
    except ws.RunError:
        if registered_target(root, ref) is not None:
            raise ReviewError('The target was checked out during synchronization') from None
        raise



def synchronize_local_target(root, record):
    scope = record['identity']
    target = scope['target_branch']
    remote = scope['remote']
    integration = record['merge_commit']
    receipt = {'status': 'pending', 'target_branch': target, 'remote': remote, 'merge_commit': integration}
    try:
        if remote not in ws.local_git_text(root, 'remote').splitlines():
            raise ReviewError('The publication remote is unavailable')
        url = ws.local_git_text(root, 'remote', 'get-url', '--', remote)
        if hashlib.sha256(url.encode()).hexdigest() != scope['remote_id'] or ws.repo_id(root) != scope['repo_id']:
            raise ReviewError('The publication repository or remote identity changed')

        ref = 'refs/heads/' + target
        tracking = 'refs/remotes/' + remote + '/' + target
        for name in (ref, tracking):
            ws.local_git(root, 'check-ref-format', name)
            if ws.local_git(root, 'symbolic-ref', '--quiet', '--no-recurse', name, accepted=(0, 1)).returncode == 0:
                raise ReviewError('The exact target or tracking ref is symbolic')
        ws.git(root, 'fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head', '--refmap=', '--',
               remote, '+' + ref + ':' + tracking)
        remote_head = ws.local_git_text(root, 'rev-parse', '--verify', tracking + '^{commit}')
        receipt['remote_head'] = remote_head
        if ws.local_git(root, 'merge-base', '--is-ancestor', integration, remote_head, accepted=(0, 1, 128)).returncode:
            raise ReviewError('The fetched target does not contain the confirmed PR integration commit')

        present = ws.local_git(root, 'show-ref', '--verify', '--quiet', ref, accepted=(0, 1)).returncode == 0
        local_head = ws.local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}') if present else None
        receipt['local_head'] = local_head
        if local_head and ws.local_git(root, 'merge-base', '--is-ancestor', remote_head, local_head, accepted=(0, 1)).returncode == 0:
            receipt['status'] = 'synchronized'
            return receipt
        if local_head and ws.local_git(root, 'merge-base', '--is-ancestor', local_head, remote_head, accepted=(0, 1)).returncode:
            raise ReviewError('Local and remote targets diverged and require a reviewed local integration')

        fast_forward_local_target(root, ref, local_head, tracking, remote_head)
        receipt['local_head'] = ws.local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}')
        if ws.local_git(root, 'merge-base', '--is-ancestor', remote_head, receipt['local_head'], accepted=(0, 1)).returncode:
            raise ReviewError('Verify that the local target contains the fetched target after updating')
        receipt['status'] = 'synchronized'
    except (ReviewError, ws.RunError) as error:
        receipt['reason'] = str(error)
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        receipt['reason'] = 'The local target Git operation was unavailable or timed out'
    return receipt


def publication_complete(record):
    if record['status'] == 'merged':
        return record.get('local_target_sync', {}).get('status') == 'synchronized'
    return record['status'] == 'pr-ready' and not record['authorization'].get('merge')

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
            key=args.publication_id or digest({**repository_scope(snapshot), **{k:snapshot[k] for k in ['repo_id','remote','source_branch','target_branch']}})[:32]
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
                        retarget=bool(record and record['identity']['target_branch']!=snapshot['target_branch'])
                        result=reconcile(record,snapshot,retarget=params if args.publication_id else None) if record else new_record(snapshot,params)
                        result['publication_id']=key
                        if not record and snapshot.get('state') in {'MERGED', 'CLOSED'}:
                            result = reconcile(result, snapshot)
                        if prepared_review and 'review_requirements' not in result:result['review_requirements']=_frozen_review_requirements(store,prepared_review)
                        if record and not retarget and params['merge_explicit']:
                            result.setdefault('authorization_history',[]).append(deepcopy(result['authorization']))
                            result['authorization']=params['authorization']
                    else:
                        if not record:raise ReviewError('Initialize or select the existing publication record')
                        if args.command=='observe':result=reconcile(record,snapshot)
                        elif args.command=='review':result=reviewed(record,snapshot,payload['review'],store=store)
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
                observed_integration = (args.command in {'init', 'observe', 'review', 'inspection', 'ready', 'merge-gate'}
                                        and snapshot.get('state') == 'MERGED' and result['status'] == 'merged')
                if observed_integration:
                    result['local_target_sync'] = synchronize_local_target(root, result)
                if 'local_target_sync' in result:
                    result['order_completed'] = publication_complete(result)
                with store.lock():
                    current_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                    if current_hash != carrier_hash:
                        raise ReviewError('The inspected publication carrier changed before recording the result')
                    if prepared_review:wf._hook_watch_guard(prepared_review['watch'],prepared_review['package_root'])
                    store.commit({relative:json.dumps(result,sort_keys=True,indent=2)+'\n'})
                    if store.state.exists():
                        state=store.load();registry=state.get('run_registry')
                        matches=[r for r in registry['runs'].values() if r.get('workspace',{}).get('branch')==result['identity']['source_branch']] if registry else []
                        if len(matches)>1:raise ReviewError('Publication run identity is ambiguous')
                        if matches:
                            run=matches[0];run.setdefault('delivery',{})['publication']=relative
                            delivery = run['delivery']
                            delivery['status'] = result['status']
                            delivery['authorization'] = result['authorization']
                            if 'local_target_sync' in result:
                                delivery['local_target_sync'] = result['local_target_sync']
                                if result['status'] == 'merged' and not result['order_completed']:
                                    delivery['status'] = 'local-target-sync-pending'
                            if result['status'] != 'merged' or 'local_target_sync' in result:
                                delivery['order_completed'] = publication_complete(result)
                            run['delivery']['pr']=result.get('pr');run['delivery']['merge_commit']=result.get('merge_commit')
                            store.save(store.text(),state)
                            if observed_integration:
                                if result['order_completed']:
                                    result['worktree_cleanup'] = wf.cleanup_after_merge(store, state, run)
                                else:
                                    result['worktree_cleanup'] = {'status': 'deferred', 'reason': result['local_target_sync']['reason']}
            result={'publication_id':key,**result}
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except (ReviewError,ws.RunError,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
