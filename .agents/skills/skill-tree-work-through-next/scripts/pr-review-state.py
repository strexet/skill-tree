#!/usr/bin/env python3
"""Persist exact-head PR review evidence and idempotent publication operations."""
from contextlib import contextmanager
from copy import deepcopy
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
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

class HandoffHold(ReviewError):
    def __init__(self, publication_id, reason, message, **details):
        super().__init__(message)
        self.result = {'ok': False, 'status': 'held', 'publication_id': publication_id,
                       'reason': reason, 'error': message, **details}


class ProviderHandoffChanged(ReviewError):
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
    if record.get('pr') and pr and (record['pr']['id']!=pr['id']
            or ('final_validation' in record and record['pr'] != pr)):
        raise ReviewError('Existing PR identity conflict')
    if pr:record['pr']=pr
    current_identity=identity(snapshot)
    changed=record['identity']!=current_identity or record.get('snapshot_key')!=review_key(snapshot)
    if record['identity']!=current_identity:
        if 'final_validation' in record:
            record['final_validation'].pop('code_review', None)
            record['final_validation']['phase'] = 'code-review'
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
            maintenance = record.pop('profile_maintenance', None)
            if maintenance:
                record.setdefault('profile_maintenance_history', []).append(maintenance)
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
    record['review']={'key':review_key(snapshot),'head':snapshot['head'],'base_oid':snapshot['base_oid'],
                      'target_branch':snapshot['target_branch'],'findings':findings,'unresolved':len(unresolved),
                      'independent_approval':False,'evidence':payload.get('evidence',[])}
    if notes:
        record['review']['development_policy_notes'] = notes
    record['rounds']=record.get('rounds',[])+[deepcopy(record['review'])]
    if 'final_validation' in record:
        state = record['final_validation']
        if unresolved:
            state.pop('code_review', None)
            state['phase'] = 'code-review'
        elif snapshot.get('pr'):
            candidate = final_validation_candidate(record, snapshot)
            if state.get('code_review') != candidate:
                state['code_review'] = candidate
                state['phase'] = 'final-validation'
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


def existing_source_checkout(store, selected, record, publication_id, snapshot=None):
    provider_pr = (record or {}).get('pr')
    if (not isinstance(provider_pr,dict) or record.get('publication_id') != publication_id
            or type(provider_pr.get('number')) is not int or provider_pr['number'] < 1
            or any(not isinstance(provider_pr.get(field),str) or not provider_pr[field].strip()
                   for field in ('id','url'))):
        raise ReviewError('Select the existing exact publication and complete provider PR identity')
    if record.get('status') == 'merged':
        raise ReviewError('Continue the merged publication through ordinary delivery reconciliation')
    saved = record['identity']
    if snapshot is not None:
        if (snapshot.get('state') != 'OPEN' or identity(snapshot) != saved
                or snapshot.get('pr') != record['pr']):
            raise ReviewError('Resume requires the original open PR, exact head, base and target')
    path, checkout = ws.verified_pr_source_worktree(store.root,selected,saved['source_branch'],saved['head'])
    if ws.repo_id(path) != saved['repo_id']:
        raise ReviewError('The source checkout belongs to a different publication repository')
    remote = saved['remote']
    url = ws.local_git_text(path,'remote','get-url','--',remote)
    if hashlib.sha256(url.encode()).hexdigest() != saved.get('remote_id'):
        raise ReviewError('The selected source checkout has a different publication remote')
    if publication_repositories(path,saved,url,remote) != repository_scope(saved):
        raise ReviewError('The selected source checkout has different publication repositories')
    if ws.local_git_text(path,'rev-parse','--verify',saved['base_oid']+'^{commit}') != saved['base_oid']:
        raise ReviewError('The selected source checkout lacks the original target base')
    return {'path':str(path),**checkout}


def existing_source_files(checkout, saved):
    output = ws.local_git(Path(checkout['path']),'diff','--name-only','--no-ext-diff','--no-textconv','-z',
                          saved['base_oid']+'...'+saved['head'],'--').stdout
    paths = [os.fsdecode(name) for name in output.split(b'\0') if name]
    if not paths:
        raise ReviewError('The selected publication has no changes relative to the original target base')
    return paths


def existing_source_preflight(root, payload, publication_id):
    if not publication_id:
        raise ReviewError('A source checkout selection requires the existing publication ID')
    wf=owned_module('pr_source_preflight_workflow',Path(__file__).with_name('workflow-state.py'))
    store=wf.Store(ws.canonical(root),allow_unselected=True,neutral=True)
    carrier=_review_path(store,publication_id)
    raw = _regular_input(carrier, 'Publication receipts', 16 * 1024 * 1024)
    if raw is None:
        raise ReviewError('Select the existing exact publication and provider PR identity')
    record=json.loads(raw)
    if not isinstance(record, dict) or record.get('publication_id') != publication_id:
        raise ReviewError('Select the existing exact publication and provider PR identity')
    verified=existing_source_checkout(store,payload['source_checkout'],record,publication_id,payload.get('snapshot'))
    saved=record['identity']
    changed=existing_source_files(verified,saved)
    if payload.get('snapshot') is not None and set(payload['snapshot'].get('changed_files',[])) != set(changed):
        raise ReviewError('Current provider diff differs from the verified source checkout')
    if (existing_source_checkout(store,payload['source_checkout'],record,publication_id,payload.get('snapshot')) != verified
            or _regular_input(carrier, 'Publication receipts', 16 * 1024 * 1024) != raw):
        raise ReviewError('The original publication checkout changed during preflight')
    return {**saved,'publication_id':publication_id,'pr':record['pr'],'status':record['status'],
            'authorization':record['authorization'],'source_checkout':verified,'changed_files':changed,
            'publication_sha256':hashlib.sha256(raw).hexdigest(),
            'requires_frozen_review_generation':bool(record.get('review_requirements')),
            'candidate_objects_required':True}


def handoff_provider_scope(checkout, checked):
    url = ws.local_git_text(checkout, 'remote', 'get-url', '--', checked['remote'])
    if hashlib.sha256(url.encode()).hexdigest() != checked['remote_id']:
        raise ProviderHandoffChanged('The verified publication remote changed')
    host, base = github_remote(url)
    retained = repository_scope(checked)
    if retained and (retained.get('base_repository') != base or not retained.get('head_repository')):
        raise ProviderHandoffChanged('The retained GitHub repository scope is incomplete or changed')
    return host, base, retained.get('head_repository', base), not retained


def handoff_provider_policy(policy, host, base, target):
    fields = {'host', 'repository', 'target_branch', 'reference',
              'required_check_names', 'approvals_required'}
    if (not isinstance(policy, dict) or set(policy) != fields
            or (policy['host'], policy['repository'], policy['target_branch']) != (host, base, target)
            or not isinstance(policy['reference'], str) or not policy['reference'].strip()
            or type(policy['approvals_required']) is not bool):
        raise ReviewError('Inspect the required checks and approvals for the exact GitHub repository and target')
    names = policy['required_check_names']
    if (not isinstance(names, list) or any(not isinstance(name, str) or not name.strip() for name in names)
            or len(set(names)) != len(names)):
        raise ReviewError('Inspect the complete required-check policy for the exact target')
    return {'checks_known': True, 'approvals_known': True, 'required_check_names': names,
            'approvals_required': policy['approvals_required']}


def handoff_pending_operations(record):
    pending = []
    operations = record.get('operations')
    if not isinstance(operations, dict):
        raise ReviewError('The retained publication operation inventory is incomplete')
    for key, operation in sorted(operations.items()):
        if (not isinstance(key, str) or not key or not isinstance(operation, dict)
                or not isinstance(operation.get('request_digest'), str)
                or not re.fullmatch(r'[a-f0-9]{64}', operation['request_digest'])
                or operation.get('state') not in {'prepared', 'confirmed'}
                or (operation.get('result') is None) != (operation['state'] == 'prepared')):
            raise ReviewError('The retained publication operation receipt requires reconciliation')
        if operation['state'] == 'prepared':
            pending.append({'key': key, 'request_digest': operation['request_digest']})
    return pending


def prepare_handoff(root, payload, publication_id):
    required = {'source_checkout', 'head', 'base_oid'}
    if (not required.issubset(payload) or set(payload) - required - {'provider_policy', 'expected_publication_sha256'}
            or any(not isinstance(payload[key], str) or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', payload[key])
                   for key in ('head', 'base_oid'))):
        raise HandoffHold(publication_id, 'request-incomplete',
                          'Supply the original source checkout, expected head and expected target base')
    source = {'source_checkout': payload['source_checkout']}
    try:
        checked = existing_source_preflight(root, source, publication_id)
        canonical = ws.canonical(root)
        carrier = _review_path(SimpleNamespace(root=canonical), publication_id)
        raw = _regular_input(carrier, 'Publication receipts', 16 * 1024 * 1024)
        if raw is None or hashlib.sha256(raw).hexdigest() != checked['publication_sha256']:
            raise ReviewError('The original publication record changed during preflight')
        record = json.loads(raw)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise HandoffHold(publication_id, 'publication-or-checkout-unavailable',
                          'Select the exact existing publication and verified source checkout') from error
    if (any(payload[key] != checked[key] for key in ('head', 'base_oid'))
            or payload.get('expected_publication_sha256', checked['publication_sha256']) != checked['publication_sha256']):
        raise HandoffHold(publication_id, 'publication-changed',
                          'Reinspect the original publication head, target base or receipt')
    authorization = checked['authorization']
    if (not isinstance(authorization, dict) or authorization.get('origin') != 'owner'
            or authorization.get('pr') is not True):
        raise HandoffHold(publication_id, 'publication-authority-unavailable',
                          'The original publication requires a retained direct owner grant')
    try:
        pending = handoff_pending_operations(record)
    except ReviewError as error:
        raise HandoffHold(publication_id, 'operation-reconciliation-required', str(error)) from error
    if pending:
        raise HandoffHold(publication_id, 'operation-reconciliation-required',
                          'Reconcile the original operation against provider evidence before continuing',
                          operations=pending,
                          recovery={'command': 'operation', 'publication_id': publication_id})
    checkout = Path(checked['source_checkout']['path'])
    try:
        host, base, head_repository, same_repository_required = handoff_provider_scope(checkout, checked)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise HandoffHold(publication_id, 'provider-scope-unavailable',
                          'Restore the GitHub repository scope bound to the original publication') from error
    try:
        policy = handoff_provider_policy(payload.get('provider_policy'), host, base, checked['target_branch'])
    except ReviewError as error:
        raise HandoffHold(publication_id, 'provider-policy-unavailable', str(error)) from error
    context = identity(checked)
    adapter_context = {**context, 'base_repository': base, 'head_repository': head_repository}
    try:
        provider = GitHub.from_preflight(checkout, adapter_context, host=host)
        snapshot = provider.snapshot(checked['pr']['number'], adapter_context, policy,
                                     expected_pr=checked['pr'], same_repository_required=same_repository_required)
    except ProviderHandoffChanged as error:
        raise HandoffHold(publication_id, 'provider-pr-changed', str(error)) from error
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise HandoffHold(publication_id, 'provider-inspection-unavailable',
                          'Restore access to GitHub PR, discussion, review and check inspection') from error
    for key in repository_scope(snapshot).keys() - repository_scope(checked).keys():
        snapshot.pop(key)
    if (identity(snapshot) != context or snapshot.get('pr') != checked['pr']
            or snapshot.get('state') != 'OPEN' or sorted(snapshot['changed_files']) != sorted(checked['changed_files'])):
        raise HandoffHold(publication_id, 'provider-pr-changed',
                          'The current provider PR or complete file set differs from the original publication')
    try:
        final = existing_source_preflight(root, {**source, 'snapshot': snapshot}, publication_id)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        raise HandoffHold(publication_id, 'publication-changed',
                          'The original publication or source checkout changed during provider inspection') from error
    if final != checked:
        raise HandoffHold(publication_id, 'publication-changed',
                          'The original publication or source checkout changed during provider inspection')
    return {'status': 'handoff-prepared', 'publication_id': publication_id, 'pr': checked['pr'],
            'head': checked['head'], 'base_oid': checked['base_oid'],
            'publication_sha256': checked['publication_sha256'],
            'provider_policy_reference': payload['provider_policy']['reference'],
            'next': {'command': 'observe', 'root': str(canonical), 'publication_id': publication_id,
                     'input': {**source, 'snapshot': snapshot,
                               'expected_publication_sha256': checked['publication_sha256']}}}


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


def review_requirement_plan(store,snapshot,*,package_root=None,run_overrides=None,record=None,publication_id=None,verified_watch=None):
    if getattr(store,'_writer_active',False):raise ReviewError('Review requirement preparation must run outside the writer lock')
    root=_review_root(store,record,package_root)
    if root is None:return None
    wf=owned_module('review_requirement_workflow',Path(__file__).with_name('workflow-state.py'))
    watch=wf._hook_watch(root,store.source_root) if verified_watch is None else verified_watch
    manifest=json.loads((root/'references/plugin-bindings.json').read_text())
    if not manifest.get('definitions') and not (record or {}).get('review_requirements'):return None
    phases={};proofs={};configuration=None
    for phase in ['before','during','after']:
        if verified_watch is not None:
            wf._hook_watch_guard(watch,root)
        context=hook_context(snapshot)
        if publication_id:context['publication_id']=publication_id
        value=wf._hook_node(root,{'runtime_action':'requirement-plan','project_root':str(store.source_root),'event':{'id':'review-requirements-'+phase,'operation':REVIEW_OPERATION,'anchor':phase},'context':context,'capabilities':['codex-source-backed-context'],'adapter':{'provider':'codex','mechanism':'source-backed-context'},'run_overrides':deepcopy(run_overrides or {})})
        if configuration is not None and configuration!=value['configuration']:raise ReviewError('Review configuration changed during requirement preparation')
        configuration=value['configuration'];proof=value['proof'];proofs[phase]=proof
        phases[phase]=[row['id'] for row in proof['bindings']]+[row['id'] for row in proof.get('unresolved',[])]
    return {'configuration':configuration,'phases':phases,'proofs':proofs,'watch':watch,'package_root':str(root)}


def isolated_review_requirements(store, snapshot, record, key, workflow):
    frozen = record.get('review_requirements')
    source = store.source_root
    if not frozen:
        # Detect newly configured review packages without executing a candidate.
        registry = _profile_input(source,'.skill-tree/installation/plugins.json')
        bindings = json.loads(registry).get('bindings',[]) if registry else []
        if any(row.get('operation') == REVIEW_OPERATION and row.get('enabled') for row in bindings):
            raise ReviewError('The selected checkout requires an original frozen review plan')
        profile = _profile_input(source,'.skill-tree/installation/profile.json')
        destinations = json.loads(profile).get('destinations',{}) if profile else {}
        candidates = [Path(__file__).resolve().parent.parent]
        candidates.extend(_profile_path(source,relative) for relative,item in destinations.items()
                          if item.get('name') == REVIEW_OPERATION)
        for candidate in candidates:
            manifest = _profile_input(candidate,'references/plugin-bindings.json')
            if manifest:
                declaration = json.loads(manifest)
                if declaration.get('operation') == REVIEW_OPERATION and declaration.get('definitions'):
                    raise ReviewError('The selected checkout requires an original frozen review plan')
        return None

    relative = frozen.get('operation_package')
    expected = frozen.get('execution_snapshot',{})
    if not isinstance(relative,str) or not isinstance(expected,dict):
        raise ReviewError('The selected checkout cannot prove the frozen review package')
    package = _profile_path(source,relative)
    manifest_path = 'references/plugin-bindings.json'
    manifest = _profile_input(package,manifest_path)
    if not manifest or hashlib.sha256(manifest).hexdigest() != expected.get('operation-manifest'):
        raise ReviewError('The selected checkout cannot prove the frozen review package')
    profile_path = '.skill-tree/installation/profile.json'
    profile = _profile_input(source,profile_path)
    profile_digest = hashlib.sha256(profile).hexdigest() if profile is not None else None
    if 'owned-profile' not in expected or profile_digest != expected['owned-profile']:
        raise ReviewError('The selected checkout differs from the frozen review generation; reconcile it through the original owned review route')

    watch = workflow._hook_watch(package,source)
    manifest_inventory = json.loads(manifest).get('owned_resources',{})
    retained_inventory = {name.removeprefix('owned/'):value
                          for name,value in expected.items() if name.startswith('owned/')}
    if (retained_inventory != manifest_inventory
            or watch.get(str(package/manifest_path)) != expected['operation-manifest']
            or watch.get(str(source/profile_path)) != profile_digest):
        raise ReviewError('The selected checkout differs from the frozen review package')
    prepared = review_requirement_plan(store,snapshot,package_root=package,record=record,
        run_overrides=frozen['configuration'].get('run_overrides',{}),publication_id=key,verified_watch=watch)
    if (prepared['configuration']['configuration_digest'] != frozen['configuration_digest']
            or prepared['proofs']['after']['execution_snapshot'] != expected):
        raise ReviewError('The selected checkout differs from the frozen review generation; reconcile it through the original owned review route')
    return prepared


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


def final_validation_candidate(record, snapshot):
    pr = snapshot.get('pr')
    if (not isinstance(pr, dict) or record.get('pr') != pr
            or not isinstance(pr.get('id'), str) or not pr['id']
            or type(pr.get('number')) is not int or pr['number'] < 1
            or not isinstance(pr.get('url'), str) or not pr['url']):
        raise ReviewError('Final validation requires the exact current provider PR')
    return digest({'scope': identity(snapshot), 'pr': pr,
                   'files': sorted(snapshot['changed_files']),
                   'definition': record['final_validation']['definition_sha256']})


@contextmanager
def offline_candidate_git():
    limits = {'GIT_NO_LAZY_FETCH': '1', 'GIT_ALLOW_PROTOCOL': ''}
    original = {name: os.environ.get(name) for name in limits}
    os.environ.update(limits)
    try:
        yield
    finally:
        for name, value in original.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def final_validation_checkout(store, snapshot):
    if store is None or not snapshot.get('candidate_objects_required'):
        raise ReviewError('Final validation requires the verified source checkout and Git candidate')
    root, checkout = ws.verified_pr_source_worktree(
        store.root, str(store.source_root), snapshot['source_branch'], snapshot['head'])
    target_ref = 'refs/remotes/' + snapshot['remote'] + '/' + snapshot['target_branch']
    if (ws.repo_id(root) != snapshot['repo_id']
            or ws.local_git_text(root, 'rev-parse', '--verify', target_ref + '^{commit}') != snapshot['base_oid']):
        raise ReviewError('Final validation checkout differs from the current repository or base')
    remote = ws.local_git_text(root, 'remote', 'get-url', '--', snapshot['remote'])
    if (hashlib.sha256(remote.encode()).hexdigest() != snapshot.get('remote_id')
            or publication_repositories(root, snapshot, remote, snapshot['remote']) != repository_scope(snapshot)):
        raise ReviewError('Final validation remote differs from the reviewed remote')
    if set(existing_source_files({'path': str(root)}, snapshot)) != set(snapshot['changed_files']):
        raise ReviewError('Final validation requires the full reviewed diff')
    with tempfile.TemporaryDirectory(prefix='skill-tree-final-validation-') as temporary:
        index = Path(temporary) / 'index'
        ws.local_git(root, 'read-tree', snapshot['head'], index=index)
        if ws.local_git(root, '-c', 'core.filemode=true', 'status', '--porcelain', '-z',
                        '--untracked-files=all', index=index).stdout:
            raise ReviewError('Final validation requires the exact committed source bytes')
    return root, digest({'path': str(root), 'registration': checkout['checkout']})

def final_validation_definition(root, head, path):
    if not isinstance(path, str) or not path:
        raise ReviewError('Final validation requires a committed definition path')
    full = _profile_path(root, path)
    if '.git' in Path(path).parts:
        raise ReviewError('Final validation paths must be outside Git metadata')
    entry = ws.local_git(root, 'ls-tree', '-z', head, '--', path).stdout
    match = re.fullmatch(rb'100(?:644|755) blob ([a-f0-9]{40}|[a-f0-9]{64})\t[^\0]+\0', entry)
    if not match:
        raise ReviewError('Final validation definition must be a committed regular file')
    blob = match[1].decode()
    if int(ws.local_git_text(root, 'cat-file', '-s', blob)) > 65536:
        raise ReviewError('Final validation definition exceeds the read limit')
    raw = ws.local_git(root, 'cat-file', 'blob', blob).stdout
    if _regular_input(full, 'Final validation definition', 65536) != raw:
        raise ReviewError('Final validation definition differs from the reviewed commit')
    definition = json.loads(raw)
    checks = definition.get('checks') if isinstance(definition, dict) and set(definition) == {'checks'} else None
    if not isinstance(checks, list) or not checks:
        raise ReviewError('Final validation definition requires a nonempty checks list')
    ids = set()
    for check in checks:
        if (not isinstance(check, dict) or set(check) != {'id', 'argv'}
                or not isinstance(check['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}', check['id'])
                or check['id'] in ids or not isinstance(check['argv'], list) or not check['argv']
                or any(not isinstance(arg, str) or '\0' in arg for arg in check['argv'])
                or not check['argv'][0]):
            raise ReviewError('Final validation checks require distinct IDs and exact argument vectors')
        ids.add(check['id'])
    return {'path': path, 'definition_sha256': hashlib.sha256(raw).hexdigest(), 'checks': checks}


def final_validation_inputs(store, snapshot, path):
    with offline_candidate_git():
        root, checkout = final_validation_checkout(store, snapshot)
        return root, checkout, final_validation_definition(root, snapshot['head'], path)


def declare_final_validation(store, record, snapshot, request, *, existing):
    if not isinstance(request, dict) or set(request) != {'path'}:
        raise ReviewError('Final validation declaration requires one exact definition path')
    if snapshot.get('state') in {'CLOSED', 'MERGED'}:
        raise ReviewError('Declare final validation before publication closes')
    _, _, definition = final_validation_inputs(store, snapshot, request['path'])
    state = record.get('final_validation')
    if existing:
        if state is None or any(state.get(key) != value for key, value in definition.items()):
            raise ReviewError('The publication already binds a different final validation declaration')
        return
    record['final_validation'] = {
        **definition, 'phase': 'code-review', 'attempts': {},
        'evidence_root': '.skill-tree/local/pr-final-validation/' + record['publication_id'],
    }


def verified_final_validation(store, record, snapshot):
    if snapshot.get('state') != 'OPEN':
        raise ReviewError('Final validation requires a confirmed open provider PR')
    state = record['final_validation']
    candidate = final_validation_candidate(record, snapshot)
    if state.get('code_review') != candidate or unresolved_findings(record, snapshot, store):
        raise ReviewError('Complete the current code review and resolve findings before final validation')
    root, checkout, definition = final_validation_inputs(store, snapshot, state['path'])
    if any(state.get(key) != value for key, value in definition.items()):
        raise ReviewError('Final validation definition differs from the original publication declaration')
    return root, candidate, checkout


def final_validation_results(root, state, attempt_id, attempt, results):
    checks = state['checks']
    if (not isinstance(results, list) or any(not isinstance(row, dict) for row in results)
            or [row.get('id') for row in results] != [check['id'] for check in checks]):
        raise ReviewError('Final validation requires one result per declared check in declaration order')
    for row, check in zip(results, checks):
        evidence = row.get('evidence')
        path = f"{state['evidence_root']}/{attempt_id}/{check['id']}.json"
        if (set(row) != {'id', 'exit_code', 'evidence'} or type(row['exit_code']) is not int
                or not isinstance(evidence, dict) or set(evidence) != {'path', 'sha256'}
                or evidence['path'] != path or not isinstance(evidence['sha256'], str)
                or not re.fullmatch(r'[a-f0-9]{64}', evidence['sha256'])):
            raise ReviewError('Final validation requires evidence at the exact attempt and check path')
        raw = _regular_input(_profile_path(root, path), 'Final validation evidence', 16*1024*1024)
        if not raw or hashlib.sha256(raw).hexdigest() != evidence['sha256']:
            raise ReviewError('Final validation evidence is missing or changed for ' + check['id'])
        observed = json.loads(raw)
        expected = {'attempt_id': attempt_id, 'candidate': attempt['candidate'], 'check_id': check['id'],
                    'argv': check['argv'], 'exit_code': row['exit_code']}
        if (not isinstance(observed, dict) or set(observed) != set(expected) | {'output'}
                or type(observed.get('exit_code')) is not int or not isinstance(observed.get('output'), str)
                or any(observed.get(key) != value for key, value in expected.items())):
            raise ReviewError('Final validation evidence does not match the prepared command and result')
    return all(row['exit_code'] == 0 for row in results)


def current_final_pass(root, state, candidate, checkout):
    for attempt_id, attempt in state['attempts'].items():
        if attempt['candidate'] == candidate and attempt['checkout'] == checkout and attempt['status'] == 'passed':
            try:
                if final_validation_results(root, state, attempt_id, attempt, attempt['results']):
                    return True
            except (OSError, ValueError):
                continue
    return False


def final_validation_transition(store, record, snapshot, request):
    record = reconcile(record, snapshot)
    if snapshot.get('state') != 'OPEN' or record['status'] in {'blocked', 'merged'} or 'final_validation' not in record:
        raise ReviewError('Final validation requires an open publication with a declared suite')
    if not isinstance(request, dict) or request.get('action') not in ('prepare', 'record'):
        raise ReviewError('Final validation requires a prepare or record action')
    action = request['action']
    attempt_id = request.get('attempt_id')
    fields = {'action', 'attempt_id'} | ({'results'} if action == 'record' else set())
    if set(request) != fields or not isinstance(attempt_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', attempt_id):
        raise ReviewError('Final validation requires an exact attempt ID and action payload')
    if action == 'prepare' and any(not thread.get('resolved') and (thread.get('required') or thread.get('actionable'))
                                   for thread in snapshot.get('threads', [])):
        raise ReviewError('Resolve current mandatory or actionable discussions before final validation')
    root, candidate, checkout = verified_final_validation(store, record, snapshot)
    state = record['final_validation']
    attempts = state['attempts']
    attempt = attempts.get(attempt_id)
    if attempt and (attempt['candidate'] != candidate or attempt['checkout'] != checkout):
        raise ReviewError('Final validation attempt belongs to a different candidate or checkout')
    if action == 'prepare':
        if attempt is not None:
            return record
        if any(row['status'] == 'prepared' and row['candidate'] == candidate for row in attempts.values()):
            raise ReviewError('Reconcile the original prepared final validation attempt')
        if current_final_pass(root, state, candidate, checkout):
            raise ReviewError('The current final validation pass remains available')
        attempts[attempt_id] = {'candidate': candidate, 'checkout': checkout, 'status': 'prepared'}
    else:
        if attempt is None:
            raise ReviewError('Prepare the exact final validation attempt before recording results')
        results = request['results']
        if attempt['status'] != 'prepared' and attempt['results'] != results:
            raise ReviewError('Final validation result replay conflicts with the original result')
        passed = final_validation_results(root, state, attempt_id, attempt, results)
        attempt.update(status='passed' if passed else 'failed', results=deepcopy(results))
    return record


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
    if 'final_validation' in record:
        if record.get('inspection', {}).get('key') != review_key(snapshot):
            raise ReviewError('Inspect current provider discussions and checks before readiness')
        root, candidate, checkout = verified_final_validation(store, record, snapshot)
        if not current_final_pass(root, record['final_validation'], candidate, checkout):
            raise ReviewError('Current candidate has no verified passing final validation')
        record['final_validation']['phase'] = 'qualified'
    elif record.get('review', {}).get('key') != review_key(snapshot):
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


def reviewed_bases(record, head, target):
    """Read retained reviews of this source head and target in newest-first order."""
    legacy_target_known = all(row.get('target_branch') == target for row in record.get('authorization_history', []))
    bases = []
    for review in reversed(record.get('rounds', []) + ([record['review']] if record.get('review') else [])):
        if review.get('head') != head:
            continue
        round_target = review.get('target_branch')
        sha, key = review.get('base_oid'), review.get('key')
        if ((round_target == target or (round_target is None and legacy_target_known))
                and isinstance(sha,str) and len(sha) == len(head) and re.fullmatch(r'[a-f0-9]+',sha)
                and isinstance(key,str) and re.fullmatch(r'[a-f0-9]{64}',key)):
            bases.append(sha)
    return bases


def workflow_diff(root, base, head):
    environment = {**ws.local_git_environment(), 'GIT_NO_LAZY_FETCH':'1', 'GIT_ALLOW_PROTOCOL':''}
    unavailable = {'status':'unavailable','paths':[]}

    def git(*args, input_data=None):
        return subprocess.run(ws.local_git_args(root,*args), env=environment, input=input_data,
                              capture_output=True, timeout=15)

    try:
        objects = git('cat-file','--batch-check=%(objectname) %(objecttype)',
                      input_data=(base+'\n'+head+'\n').encode('ascii'))
        if objects.returncode or objects.stdout.splitlines() != [(sha+' commit').encode('ascii') for sha in (base,head)]:
            return unavailable
        bases = git('merge-base','--all',base,head)
        if bases.returncode or len(bases.stdout.splitlines()) != 1:
            return unavailable
        common = bases.stdout.strip().decode('ascii')
        if len(common) != len(head) or not re.fullmatch(r'[a-f0-9]+',common):
            return unavailable
        result = git('diff','--name-only','--no-renames','--no-ext-diff','--no-textconv','-z',
                     common,head,'--','.github/workflows')
        if result.returncode:
            return unavailable
        paths = sorted(name.decode('utf-8') for name in result.stdout.split(b'\0')
                       if name.startswith(b'.github/workflows/'))
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        return unavailable
    return {'status':'observed','paths':paths}


def scoped_refusal(status, message):
    return (type(status) is int and 400 <= status < 500 and status != 408
            and isinstance(message,str) and 0 < len(message) <= 2048 and bool(message.strip())
            and all(32 <= ord(char) < 127 or ord(char) >= 160 for char in message)
            and not re.search(r'\b(?:gh[pousr]_\w{10,}|github_pat_\w{10,}|Bearer\s+[\w./=-]{8,})'
                              r'|https?://[^/\s]+@', message, re.I))


def merge_denial_preview(root, record, payload):
    allowed = {'snapshot','provider_refusal','expected_publication_sha256'}
    if set(payload) - allowed or not isinstance(payload.get('snapshot'), dict):
        raise ReviewError('Merge denial preview requires the exact publication and provider snapshot')
    snapshot = payload['snapshot']
    expected_pr, pr = record.get('pr'), snapshot.get('pr')
    if (not isinstance(expected_pr, dict) or not isinstance(pr, dict) or snapshot.get('state') != 'OPEN'
            or type(expected_pr.get('id')) not in (int,str) or not expected_pr['id']
            or type(expected_pr.get('number')) is not int or expected_pr['number'] < 1
            or not isinstance(expected_pr.get('url'),str) or not expected_pr['url']
            or any(type(expected_pr[key]) is not type(pr.get(key)) or expected_pr[key] != pr[key]
                   for key in ('id','number','url'))):
        raise ReviewError('Merge denial preview requires the original open provider PR')
    for key in ('head','base_oid'):
        if not isinstance(snapshot.get(key), str) or re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', snapshot[key]) is None:
            raise ReviewError('Merge denial preview requires exact provider head and base objects')
    reconcile(record, snapshot)
    head, base, target = (snapshot[key] for key in ('head','base_oid','target_branch'))
    historical_bases = reviewed_bases(record, head, target)
    previous = historical_bases[0] if historical_bases else None
    drift = 'unknown' if previous is None else 'unchanged' if previous == base else 'moved'
    refusal = payload.get('provider_refusal')
    if refusal is not None:
        required = {'provider','repository','number','head','http_status','message','target_branch','attempted_base_oid'}
        repository = record['identity'].get('base_repository')
        if repository is None:
            match = re.fullmatch(r'https://[^/]+/([\w.-]+/[\w.-]+)/pull/([1-9][0-9]*)', expected_pr.get('url') or '')
            if match and int(match[2]) == expected_pr['number']:
                repository = match[1].lower()
        accepted_bases = [base,*historical_bases]
        if record['identity']['head'] == head:
            accepted_bases.append(record['identity']['base_oid'])
        attempted_base = refusal.get('attempted_base_oid') if isinstance(refusal,dict) else None
        if (not isinstance(refusal, dict) or set(refusal) != required or refusal['provider'] != 'github'
                or not repository or refusal['repository'] != repository or type(refusal['number']) is not int
                or refusal['number'] != pr['number']
                or refusal['head'] != head or refusal['target_branch'] != target
                or not isinstance(attempted_base,str) or len(attempted_base) != len(head)
                or re.fullmatch(r'[a-f0-9]+',attempted_base) is None or attempted_base not in accepted_bases
                or not scoped_refusal(refusal['http_status'],refusal['message'])):
            raise ReviewError('Provider refusal requires the actual bounded HTTP response and the original merge attempt scope')
    files = workflow_diff(root, base, head)
    prerequisite = None
    if drift == 'moved' and files['paths']:
        prerequisite = {'kind':'review-refresh-required','target_branch':target,'head':head,'base_oid':base,
                        'actions':['inspect-current-provider-snapshot','review-current-head-and-base',
                                   'rerun-required-checks','apply-existing-merge-gate']}
    return {'pr':deepcopy(expected_pr),'authorization':deepcopy(record['authorization']),'head':head,
            'target_branch':target,'base_oid':base,'reviewed_base_oid':previous,'base_drift':drift,
            'workflow_diff':files,'provider_refusal':deepcopy(refusal),'credential_permissions':'unknown',
            'prerequisite':prerequisite}


class GitHub:
    """Authorized gh fallback; connectors can supply the same normalized snapshots."""
    def __init__(self, root, repository, head_repository=None, *, host=None):
        self.root = Path(root)
        for name in (repository, head_repository or repository):
            if not isinstance(name, str) or not re.fullmatch(r'[\w.-]+/[\w.-]+', name):
                raise ReviewError('Explicit GitHub owner/repository required')
        self.repository = repository.lower()
        self.head_repository = (head_repository or repository).lower()
        self.explicit_head = head_repository is not None
        if host is not None and (not isinstance(host, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]*', host)):
            raise ReviewError('A verified GitHub hostname is required')
        self.host = host

    @classmethod
    def from_preflight(cls, root, checked, *, host=None):
        if not checked.get('base_repository') or not checked.get('head_repository'):
            raise ReviewError('Select the reviewed base and head remotes in publication preflight')
        return cls(root, checked['base_repository'], checked['head_repository'], host=host)
    def gh(self,*args):
        if self.host and args[:1] == ('api',):
            args = (*args, '--hostname', self.host)
        if '--paginate' in args and '--slurp' not in args:args=(*args,'--slurp')
        result=subprocess.run(['gh',*map(str,args)],cwd=self.root,capture_output=True,text=True,timeout=45)
        if result.returncode:
            error = ReviewError('GitHub access or operation failed; preserve the publication checkpoint')
            if (len(args) >= 4 and args[:3] == ('api','--method','PUT')
                    and re.fullmatch(r'repos/[^/]+/[^/]+/pulls/\d+/merge', args[3])):
                response = re.fullmatch(r'gh: (.{1,2048}) \(HTTP (4[0-9]{2})\)', result.stderr.strip())
                if response and scoped_refusal(int(response[2]), response[1]):
                    error.http_refusal = {'http_status':int(response[2]),'message':response[1]}
            raise error
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
    def pull_view(self, number):
        repo = self.host + '/' + self.repository if self.host else self.repository
        return self.gh('pr','view',number,'--repo',repo,'--json',
                       'id,number,url,state,headRefOid,headRefName,baseRefOid,baseRefName,mergeable,reviewDecision,mergeCommit,statusCheckRollup,changedFiles,isCrossRepository,headRepository,headRepositoryOwner')

    def require_handoff_pull(self, raw, context, expected_pr, same_repository_required):
        if not isinstance(raw, dict):
            raise ReviewError('Provider PR inspection is unavailable')
        fields = {'headRefOid': 'head', 'baseRefOid': 'base_oid',
                  'headRefName': 'source_branch', 'baseRefName': 'target_branch'}
        identity_url = 'https://' + self.host + '/' + self.repository + '/pull/' + str(expected_pr['number'])
        owner = raw.get('headRepositoryOwner')
        repository = raw.get('headRepository')
        if not isinstance(owner, dict) or not isinstance(repository, dict):
            raise ReviewError('Provider head repository evidence is unavailable')
        owner_name, repository_name = owner.get('login'), repository.get('name')
        if not isinstance(owner_name, str) or not isinstance(repository_name, str):
            raise ReviewError('Provider head repository evidence is unavailable')
        head = (owner_name + '/' + repository_name).lower()
        if ({key: raw.get(key) for key in ('id', 'number', 'url')} != expected_pr
                or type(raw.get('number')) is not int or raw['url'].lower() != identity_url
                or raw.get('state') != 'OPEN' or any(raw.get(key) != context[value] for key, value in fields.items())
                or head != self.head_repository
                or (same_repository_required and raw.get('isCrossRepository') is not False)):
            raise ProviderHandoffChanged('The original open GitHub PR, repository, head or target base changed')

    def snapshot(self,number,context,policy,*,expected_pr=None,same_repository_required=False):
        raw=self.pull_view(number)
        if expected_pr is not None:
            self.require_handoff_pull(raw, context, expected_pr, same_repository_required)
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
        if (not isinstance(files, list) or any(not isinstance(row, dict) or not isinstance(row.get('filename'), str)
                                                for row in files) or len(files)!=raw['changedFiles']):
            raise ReviewError('Provider full-diff file inventory is incomplete')
        reviews=self.gh('api','--method','GET',endpoint+'/pulls/'+str(number)+'/reviews','--paginate')
        comments=self.gh('api','--method','GET',endpoint+'/issues/'+str(number)+'/comments','--paginate')
        inline=self.gh('api','--method','GET',endpoint+'/pulls/'+str(number)+'/comments','--paginate')
        if any(not isinstance(inventory, list) or any(not isinstance(row, dict) for row in inventory)
               for inventory in (reviews, comments, inline)):
            raise ReviewError('Provider review or comment inventory is incomplete')
        owner,name=self.repository.split('/');threads=[];cursor=None;seen=set()
        query='query($owner:String!,$name:String!,$number:Int!,$cursor:String){repository(owner:$owner,name:$name){pullRequest(number:$number){reviewThreads(first:100,after:$cursor){nodes{id isResolved isOutdated path line} pageInfo{hasNextPage endCursor}}}}}'
        if expected_pr is not None:
            query=query.replace('{reviewThreads(', '{id reviewThreads(')
        while True:
            args=['api','graphql','-f','query='+query,'-f','owner='+owner,'-f','name='+name,'-F','number='+str(number)]
            if cursor:args+=['-f','cursor='+cursor]
            response=self.gh(*args)
            if not isinstance(response, dict) or response.get('errors'):
                raise ReviewError('Provider discussion inventory is incomplete')
            pull=response['data']['repository']['pullRequest']
            if not isinstance(pull, dict):
                raise ReviewError('Provider discussion inventory is incomplete')
            if expected_pr is not None and pull.get('id')!=expected_pr['id']:
                raise ProviderHandoffChanged('The provider discussion page identifies a different PR')
            page=pull['reviewThreads']
            threads.extend({'id':t['id'],'resolved':t['isResolved'],'required':not t['isResolved'],'path':t['path'],'line':t['line'],'outdated':t['isOutdated']} for t in page['nodes'])
            if not page['pageInfo']['hasNextPage']:break
            new_cursor=page['pageInfo']['endCursor']
            if not isinstance(new_cursor, str) or not new_cursor or new_cursor in seen:
                raise ReviewError('Provider discussion pagination did not advance')
            seen.add(new_cursor)
            cursor=new_cursor
        if expected_pr is not None:
            raw = self.pull_view(number)
            self.require_handoff_pull(raw, context, expected_pr, same_repository_required)
            rollup = raw.get('statusCheckRollup')
            if (not isinstance(rollup, list) or any(not isinstance(check, dict) for check in rollup)
                    or 'reviewDecision' not in raw):
                raise ReviewError('Provider check or approval inventory is unavailable')
            if len(files)!=raw['changedFiles']:
                raise ProviderHandoffChanged('The provider full-diff inventory changed during inspection')
        required=set(policy.get('required_check_names',[]));checks=[]
        for check in raw.get('statusCheckRollup') or []:
            name=check.get('name') or check.get('context');status=check.get('conclusion') or check.get('state') or check.get('status') or 'UNKNOWN'
            if expected_pr is not None and (not isinstance(name, str) or not isinstance(status, str)):
                raise ReviewError('Provider check identity or status is unavailable')
            checks.append({'name':name,'status':'success' if status=='SUCCESS' else status.lower(),'required':name in required})
        return {**context,'head':raw['headRefOid'],'base_oid':raw['baseRefOid'],'candidate_objects_required':True,'changed_files':[f['filename'] for f in files],'pr':{'id':raw['id'],'number':raw['number'],'url':raw['url']},'state':raw['state'],'merge_commit':(raw.get('mergeCommit') or {}).get('oid'),'mergeable':raw['mergeable'],'reviews':reviews,'comments':comments+inline,'threads':threads,'checks':checks,'checks_known':policy.get('checks_known') is True,'required_checks_missing':sorted(required-{c['name'] for c in checks}),'approvals_known':policy.get('approvals_known') is True,'approvals_required':policy.get('approvals_required',True),'approved':raw.get('reviewDecision')=='APPROVED','same_repository':raw.get('isCrossRepository') is False}
    def merge(self,number,head,method):
        if method not in {'merge','squash','rebase'}:raise ReviewError('Repository-approved merge method required')
        try:
            return self.gh('api','--method','PUT','repos/'+self.repository+'/pulls/'+str(number)+'/merge',
                           '-f','sha='+head,'-f','merge_method='+method)
        except ReviewError as error:
            if hasattr(error,'http_refusal'):
                error.provider_refusal = {'provider':'github','repository':self.repository,'number':number,
                                          'head':head,**error.http_refusal}
            raise

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


def _profile_path(root, relative):
    path = Path(relative)
    if (path.is_absolute() or path.as_posix() != relative or not path.parts
            or '..' in path.parts or '\\' in relative or '\0' in relative):
        raise ValueError('An owned profile input requires an exact repository-relative path')
    full = root / path
    if full.resolve() != full:
        raise ValueError('Owned profile inputs cannot follow symbolic links')
    return full


def _regular_input(full, label, limit=None):
    try:
        descriptor = os.open(full, os.O_RDONLY | getattr(os,'O_NOFOLLOW',0) | getattr(os,'O_NONBLOCK',0))
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, 'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise ValueError(label+' require regular files')
        content = source.read() if limit is None else source.read(limit+1)
        if limit is not None and len(content) > limit:
            raise ValueError(label+' exceed the read limit')
        return content


def _profile_input(root, relative):
    return _regular_input(_profile_path(root,relative),'Owned profile inputs')


def _profile_discovery_paths(root, rules):
    names = set(rules['names'])
    extensions = set(rules['extensions'])
    excluded = {'node_modules', '.git', 'Library', 'Temp', 'artifacts', 'installation'}
    found = {name for name in names if _profile_path(root, name).exists()}
    for relative in rules['roots']:
        start = _profile_path(root, relative)
        if not start.exists():
            continue
        if not start.is_dir():
            raise ValueError('Profile inventory roots require directories')
        for directory, directories, files in os.walk(start, followlinks=False):
            directories[:] = [name for name in directories if name not in excluded]
            for name in directories + files:
                path = Path(directory) / name
                if path.is_symlink() and name not in excluded:
                    raise ValueError('The profile inventory contains a symbolic link')
            for name in files:
                if name not in excluded and (name in names or Path(name).suffix in extensions):
                    found.add((Path(directory) / name).relative_to(root).as_posix())
    return found


def _owned_profile_files_match(root, relative, files):
    destination = _profile_path(root, relative)
    if not destination.is_dir() or not isinstance(files, dict) or not files:
        return False
    actual = set()
    for directory, directories, names in os.walk(destination, followlinks=False):
        parent = Path(directory)
        prefix = parent.relative_to(destination).as_posix()
        if prefix != 'plugins' and not prefix.startswith('plugins/'):
            directories[:] = [name for name in directories if name != '__pycache__']
            names = [name for name in names if name != '__pycache__']
        if any((parent / name).is_symlink() for name in directories):
            return False
        for name in names:
            actual.add((parent / name).relative_to(destination).as_posix())
    if actual != files.keys():
        return False
    for name, expected in files.items():
        source = _profile_input(root, relative + '/' + name)
        if source is None or hashlib.sha256(source).hexdigest() != expected:
            return False
    return True


def _owned_profile_destinations_match(root, destinations):
    if not isinstance(destinations, dict) or not destinations:
        return False
    for relative, record in destinations.items():
        files = record.get('files') if isinstance(record, dict) else None
        name = record.get('name', '') if isinstance(record, dict) else ''
        if (not isinstance(name, str) or not re.fullmatch(r'skill-tree-[a-z0-9-]+', name)
                or Path(relative).name != name or not _owned_profile_files_match(root, relative, files)):
            return False
    return True


def _owned_profile_bridges_match(root, bridges):
    if not isinstance(bridges, dict):
        return False
    begin = '<!-- BEGIN skill-tree-skills -->'
    end = '<!-- END skill-tree-skills -->'
    for relative, record in bridges.items():
        raw = _profile_input(root, relative)
        if raw is None or not isinstance(record, dict):
            return False
        contents = raw.decode('utf-8', errors='replace')
        start = contents.find(begin)
        stop = contents.find(end)
        if (start < 0 or stop < start or contents.find(begin, start + len(begin)) >= 0
                or contents.find(end, stop + len(end)) >= 0):
            return False
        block = contents[start:stop + len(end)]
        if hashlib.sha256(block.encode('utf-8')).hexdigest() != record.get('hash'):
            return False
    return True


def canonical_profile_prerequisite(root):
    """Report owned discovery input drift without executing target code."""
    root = Path(root).resolve()
    profile_path = '.skill-tree/installation/profile.json'
    manager_path = '.skill-tree/installation/manager.js'
    bundle_source = '.skill-tree/installation/source'
    capability_path = bundle_source + '/config/capabilities.json'
    try:
        raw = _profile_input(root, profile_path)
        if raw is None:
            return None
        profile = json.loads(raw)
        if (not isinstance(profile, dict) or profile.get('format') != 'skill-tree-profile'
                or profile.get('schema') != 1 or profile.get('project_root') != str(root)
                or not isinstance(profile.get('inputs'), dict)
                or not isinstance(profile.get('bundle_digests'), dict)):
            return None
        bundle = profile['bundle_digests']
        if manager_path not in bundle or capability_path not in bundle:
            return None
        prefix = bundle_source + '/'
        bundle_files = {relative[len(prefix):]: expected for relative, expected in bundle.items()
                        if relative.startswith(prefix)}
        if not _owned_profile_files_match(root, bundle_source, bundle_files):
            return None
        for relative in bundle.keys() - {prefix + name for name in bundle_files}:
            source = _profile_input(root, relative)
            if source is None or hashlib.sha256(source).hexdigest() != bundle[relative]:
                return None
        capabilities = json.loads(_profile_input(root, capability_path))
        discovered = _profile_discovery_paths(root, capabilities['inventory'])
        inputs = profile['inputs']
        changed = []
        for relative in inputs.keys() | discovered:
            expected = inputs.get(relative)
            if expected is not None and (not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected)):
                return None
            source = _profile_input(root, relative)
            actual = hashlib.sha256(source).hexdigest() if source is not None else None
            if actual != expected:
                changed.append(relative)
        if (not changed or not _owned_profile_destinations_match(root, profile.get('destinations'))
                or not _owned_profile_bridges_match(root, profile.get('bridges', {}))
                or _profile_input(root, profile_path) != raw):
            return None
        return {'code': 'profile-refresh-required', 'changed_inputs': sorted(changed),
                'profile_sha256': hashlib.sha256(raw).hexdigest(),
                'recovery_argv': ['node', manager_path, '--refresh-profile']}
    except (OSError, TypeError, KeyError, ValueError, subprocess.TimeoutExpired):
        return None


def synchronized_profile_prerequisite(root, ref, expected_head):
    try:
        target = registered_target(root, ref)
        if target is None or ws.common_dir(target) != ws.common_dir(root):
            return None
        checkout = ws.checked_out_branch(target)
        if (checkout['ref'], checkout['head']) != (ref, expected_head):
            return None
        prerequisite = canonical_profile_prerequisite(target)
        if prerequisite and ws.checked_out_branch(target) == checkout:
            return {**prerequisite, 'target_ref': ref, 'target_head': expected_head,
                    'target_checkout': checkout['checkout']}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    return None


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
    ws.local_git_policy(worktree, signed=True, fast_forward=True)
    with tempfile.TemporaryDirectory(prefix='skill-tree-pr-target-') as temporary:
        scratch = Path(temporary).resolve()
        writer = scratch / 'ref-writer'
        hooks = scratch / 'hooks'
        hooks.mkdir()
        no_hooks = ('-c', f'core.hooksPath={hooks}')
        ws.local_git(root, *no_hooks, 'worktree', 'add', '--detach', '--no-checkout', '--', writer, remote_head)
        initialized = False
        try:
            ws.local_git(writer, *no_hooks, 'read-tree', '--reset', '-u', remote_head)
            initialized = True
            ws.run_local_merge(worktree, writer, preparation, fast_forward=True)
        finally:
            # The incomplete checkout exists only inside private scratch space.
            options = () if initialized else ('--force',)
            ws.local_git(root, *no_hooks, 'worktree', 'remove', *options, '--', writer)


def fetch_synchronization_ref(root, remote, refspec):
    ws.require_local_git_hooks(root, ('reference-transaction',))
    fetch = ws.local_git if remote == '.' else ws.git
    with tempfile.TemporaryDirectory(prefix='skill-tree-fetch-hooks-') as hooks:
        fetch(root, 'fetch', '--no-tags', '--no-recurse-submodules', '--no-write-fetch-head',
              '--no-auto-maintenance', '--refmap=', '--', remote, refspec,
              git_options=('-c', f'core.hooksPath={hooks}'))


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
    try:
        fetch_synchronization_ref(root, '.', remote_head + ':' + ref)
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
        fetch_synchronization_ref(root, remote, '+' + ref + ':' + tracking)
        remote_head = ws.local_git_text(root, 'rev-parse', '--verify', tracking + '^{commit}')
        receipt['remote_head'] = remote_head
        if ws.local_git(root, 'merge-base', '--is-ancestor', integration, remote_head, accepted=(0, 1, 128)).returncode:
            raise ReviewError('The fetched target does not contain the confirmed PR integration commit')

        present = ws.local_git(root, 'show-ref', '--verify', '--quiet', ref, accepted=(0, 1)).returncode == 0
        local_head = ws.local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}') if present else None
        receipt['local_head'] = local_head
        if not local_head or ws.local_git(root, 'merge-base', '--is-ancestor', remote_head, local_head, accepted=(0, 1)).returncode:
            if local_head and ws.local_git(root, 'merge-base', '--is-ancestor', local_head, remote_head, accepted=(0, 1)).returncode:
                raise ReviewError('Local and remote targets diverged and require a reviewed local integration')
            fast_forward_local_target(root, ref, local_head, tracking, remote_head)
            receipt['local_head'] = ws.local_git_text(root, 'rev-parse', '--verify', ref + '^{commit}')
            if ws.local_git(root, 'merge-base', '--is-ancestor', remote_head, receipt['local_head'], accepted=(0, 1)).returncode:
                raise ReviewError('Verify that the local target contains the fetched target after updating')
            if local_head:
                receipt['previous_local_head'] = local_head
        prior = record.get('local_target_sync', {})
        if (prior.get('status') == 'synchronized' and prior.get('remote_head') == remote_head
                and prior.get('local_head') == receipt['local_head'] and prior.get('previous_local_head')):
            receipt.setdefault('previous_local_head', prior['previous_local_head'])
        receipt['status'] = 'synchronized'
        prerequisite = synchronized_profile_prerequisite(root, ref, receipt['local_head'])
        if prerequisite:
            receipt['profile_prerequisite'] = prerequisite
    except (ReviewError, ws.RunError) as error:
        receipt['reason'] = str(error)
    except (OSError, UnicodeError, subprocess.TimeoutExpired):
        receipt['reason'] = 'The local target Git operation was unavailable or timed out'
    return receipt


def _profile_maintenance_library():
    # Resolve the executing generation without using product or target Git content as code.
    script = Path(__file__).resolve()
    core = script.parents[2]
    if script.parent == core / 'common/scripts':
        library = _profile_path(core, 'lib/installation.js')
        if library.is_file():
            return library
    package = script.parent.parent
    bundle = '.skill-tree/installation/source'
    for actor_root in package.parents:
        raw = _profile_input(actor_root, '.skill-tree/installation/profile.json')
        if raw is None:
            continue
        profile = json.loads(raw)
        destination = package.relative_to(actor_root).as_posix()
        owned = profile.get('destinations', {}).get(destination, {}).get('files', {})
        if (profile.get('project_root') != str(actor_root)
                or owned.get('scripts/pr-review-state.py') != hashlib.sha256(script.read_bytes()).hexdigest()):
            continue
        prefix = bundle + '/'
        files = {relative[len(prefix):]: expected for relative, expected in profile.get('bundle_digests', {}).items()
                 if relative.startswith(prefix)}
        if 'lib/installation.js' in files and _owned_profile_files_match(actor_root, bundle, files):
            return _profile_path(actor_root, bundle + '/lib/installation.js')
    raise ReviewError('The trusted acting installation library is unavailable')


def _operate_delivery_profile(library, target, request):
    script = """
const [library,root]=process.argv.slice(1);
try {
  const request=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
  const result=require(library).maintainDeliveredProfile(root,request);
  console.log(JSON.stringify(result));
} catch (error) {
  console.log(JSON.stringify({error:error.message}));
  process.exitCode=2;
}
"""
    environment = ws.local_git_environment()
    environment.pop('NODE_OPTIONS', None)
    environment.pop('NODE_PATH', None)
    output = subprocess.run(['node', '-e', script, str(library), str(target)], cwd=library.parent,
                            input=json.dumps(request), capture_output=True, text=True,
                            env=environment, timeout=45)
    try:
        result = json.loads(output.stdout)
    except ValueError as error:
        raise ReviewError('The trusted profile maintenance operation returned no structured result') from error
    if output.returncode:
        raise ReviewError(result.get('error') or 'The trusted profile maintenance operation failed')
    return result


def restore_delivery_profile(root, store, key, authorization):
    relative = '.skill-tree/history/publications/pub-' + key + '.json'
    carrier = store.owned(relative)
    original = carrier.read_bytes()
    record = json.loads(original)
    identity = record['identity']
    with ws.publication_lock(root, identity['remote'], identity['target_branch']):
        if carrier.read_bytes() != original:
            raise ReviewError('The selected publication changed before profile maintenance')
        sync = record.get('local_target_sync', {})
        if (record.get('status') != 'merged' or sync.get('status') != 'synchronized'
                or sync.get('merge_commit') != record.get('merge_commit')
                or sync.get('target_branch') != identity['target_branch'] or sync.get('remote') != identity['remote']):
            raise ReviewError('Profile maintenance requires an exact verified PR delivery')
        ref = 'refs/heads/' + identity['target_branch']
        tracking = 'refs/remotes/' + identity['remote'] + '/' + identity['target_branch']
        head = sync['local_head']
        previous = record.get('profile_maintenance')
        if authorization is None and previous:
            authorization = previous['authorization']
        if not isinstance(authorization, dict):
            raise ReviewError('Profile maintenance requires a bounded explicit owner instruction')
        base = {'origin': 'owner', 'permission': 'refresh-compatible-profile', 'publication_id': key,
                'repo_id': identity['repo_id'], 'merge_commit': record['merge_commit'],
                'target_ref': ref, 'target_head': head}
        if (authorization.keys() != base.keys() | {'target_checkout', 'profile_sha256'}
                or any(authorization.get(name) != value for name, value in base.items())
                or any(not isinstance(authorization.get(name), str)
                       or not re.fullmatch('[a-f0-9]{64}', authorization[name])
                       for name in ('target_checkout', 'profile_sha256'))):
            raise ReviewError('Profile maintenance authorization differs from the exact verified delivery')
        if previous and previous.get('authorization') != authorization:
            record.setdefault('profile_maintenance_history', []).append(previous)
            previous = None
        if previous is None:
            prerequisite = sync.get('profile_prerequisite', {})
            if any(prerequisite.get(name) != authorization[name] for name in
                   ('target_ref', 'target_head', 'target_checkout', 'profile_sha256')):
                raise ReviewError('Profile maintenance requires the exact observed profile prerequisite')

        maintenance = deepcopy(previous) if previous is not None else {'authorization': authorization}
        record['profile_maintenance'] = maintenance
        record['order_completed'] = publication_complete(record)
        def save(*, final=False):
            nonlocal original
            with store.lock():
                if carrier.read_bytes() != original:
                    raise ReviewError('The publication carrier changed during profile maintenance')
                rendered = json.dumps(record, sort_keys=True, indent=2) + '\n'
                state = store.load() if final and store.state.is_file() and store.future.is_file() else None
                runs = ((state or {}).get('run_registry') or {}).get('runs', {})
                matching = [run for run in runs.values()
                            if run.get('delivery', {}).get('publication') == relative
                            and run.get('workspace', {}).get('branch') == identity['source_branch']]
                if len(matching) > 1:
                    raise ReviewError('The publication run identity changed before profile maintenance recording')
                if matching:
                    matching[0]['delivery'].update(local_target_sync=sync, profile_maintenance=maintenance)
                    store.save(store.text(), state, extras={relative: rendered})
                else:
                    store.commit({relative: rendered})
                original = rendered.encode()

        try:
            remote = ws.local_git_text(root, 'remote', 'get-url', '--', identity['remote'])
            if (hashlib.sha256(remote.encode()).hexdigest() != identity['remote_id']
                    or ws.repo_id(root) != identity['repo_id'] or head != sync['remote_head']
                    or not sync.get('previous_local_head')):
                raise ReviewError('Original synchronized target or pre-sync input provenance is unavailable')
            target = registered_target(root, ref)
            if target != ws.canonical(root) or ws.common_dir(target) != ws.common_dir(root):
                raise ReviewError('Profile maintenance requires the recorded canonical checkout')
            library = _profile_maintenance_library()
            checkout = {'ref': ref, 'head': head, 'checkout': authorization['target_checkout']}
            request = {**authorization, 'previous_local_head': sync['previous_local_head']}
            profile_path = '.skill-tree/installation/profile.json'
            with tempfile.TemporaryDirectory(prefix='skill-tree-profile-ref-') as hooks:
                with ws.local_ref_transaction(target, hooks, tracking, head, ref, head, head):
                    if ws.checked_out_branch(target) != checkout:
                        raise ReviewError('The authorized target checkout changed before maintenance')
                    raw = _profile_input(target, profile_path)
                    actual = hashlib.sha256(raw).hexdigest() if raw else None
                    plan = maintenance.get('plan')
                    if plan is not None and actual == plan['after']['profile_sha256']:
                        restored = _operate_delivery_profile(library, target, {**request, 'phase': 'verify', 'plan': plan})
                        status = 'restored' if maintenance.get('status') == 'restored' else 'reconciled'
                    else:
                        if actual != authorization['profile_sha256']:
                            raise ReviewError('The current profile differs from both exact maintenance generations')
                        derived = _operate_delivery_profile(library, target, {**request, 'phase': 'prepare'})
                        if plan is not None and derived['plan'] != plan:
                            raise ReviewError('Retained profile maintenance intent differs from current evidence')
                        plan = derived['plan']
                        maintenance.update(status='prepared', plan=plan)
                        maintenance.pop('reason', None)
                        save()
                        _operate_delivery_profile(library, target, {**request, 'phase': 'activate', 'plan': plan})
                        restored = _operate_delivery_profile(library, target, {**request, 'phase': 'verify', 'plan': plan})
                        status = 'restored'
                    raw = _profile_input(target, profile_path)
                    if (ws.checked_out_branch(target) != checkout or restored['profile'] != plan['after']
                            or raw is None or hashlib.sha256(raw).hexdigest() != plan['after']['profile_sha256']):
                        raise ReviewError('The exact target or anticipated installation changed before receipt recording')
                    maintenance['status'] = status
                    maintenance.pop('reason', None)
                    sync.pop('profile_prerequisite', None)
                    save(final=True)
                    return record
        except (ReviewError, ws.RunError, OSError, subprocess.TimeoutExpired) as error:
            maintenance.update(status='retryable', reason=str(error))
        save(final=True)
        return record


def publication_complete(record):
    if record['status'] == 'merged':
        return record.get('local_target_sync', {}).get('status') == 'synchronized'
    return record['status'] == 'pr-ready' and not record['authorization'].get('merge')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['parameters','preflight','prepare-handoff','init','observe','review','ready','merge-gate','merge-denial-preview','operation','block','hook-attach','inspection','review-reconcile','plugin-findings','profile-maintenance','final-validation'])
    parser.add_argument('root',type=Path);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--publication-id')
    args=parser.parse_args(argv)
    if args.command in {'final-validation', 'prepare-handoff'}:
        with offline_candidate_git():
            return dispatch(args)
    return dispatch(args)


def dispatch(args):
    try:
        payload=json.loads(args.input.read_text());root=args.root.resolve()
        if not isinstance(payload,dict):raise ReviewError('Publication requests require an object')
        explicit_source = 'source_checkout' in payload
        if explicit_source and args.command != 'prepare-handoff' and (not args.publication_id
                or args.command in {'parameters','profile-maintenance','init','operation','review-reconcile'}):
            raise ReviewError('A source checkout selection applies to an existing exact review publication')
        if explicit_source and {'package_root','run_overrides'} & payload.keys():
            raise ReviewError('An isolated review keeps the original package and overrides')
        if args.command=='parameters':result=parameters(payload.get('current_branch',ws.git(root,'symbolic-ref','--short','HEAD')),payload)
        elif args.command=='preflight':
            result=existing_source_preflight(root,payload,args.publication_id) if explicit_source else preflight(root,payload)
        elif args.command=='prepare-handoff':
            result=prepare_handoff(root,payload,args.publication_id)
        elif args.command=='merge-denial-preview':
            carrier = _review_path(SimpleNamespace(root=ws.canonical(root)),args.publication_id)
            raw = _regular_input(carrier,'Publication receipts',16*1024*1024)
            if raw is None:
                raise ReviewError('Merge denial preview requires the exact retained publication')
            observed_hash = hashlib.sha256(raw).hexdigest()
            if payload.get('expected_publication_sha256',observed_hash) != observed_hash:
                raise ReviewError('The selected publication changed before merge denial preview')
            record = json.loads(raw)
            if not isinstance(record,dict) or record.get('publication_id') != args.publication_id:
                raise ReviewError('Merge denial preview requires the exact retained publication')
            result = merge_denial_preview(root,record,payload)
            if _regular_input(carrier,'Publication receipts',16*1024*1024) != raw:
                raise ReviewError('The selected publication changed during merge denial preview')
            result.update(publication_id=args.publication_id,publication_sha256=observed_hash)
        elif args.command=='profile-maintenance':
            key = args.publication_id
            if not key or not re.fullmatch(r'[a-f0-9]{32}', key):
                raise ReviewError('Profile maintenance requires the existing exact publication ID')
            wf = owned_module('pr_workflow', Path(__file__).with_name('workflow-state.py'))
            result = restore_delivery_profile(root, wf.Store(root, allow_unselected=True), key,
                                              payload.get('profile_authorization'))
        else:
            # Metadata-only commands never send provider requests. The agent supplies inspected snapshots.
            canonical=ws.canonical(root);snapshot=payload.get('snapshot',{})
            key=args.publication_id or digest({**repository_scope(snapshot), **{k:snapshot[k] for k in ['repo_id','remote','source_branch','target_branch']}})[:32]
            if not re.fullmatch(r'[a-f0-9]{32}',key):raise ReviewError('Invalid publication ID')
            wf=owned_module('pr_workflow',Path(__file__).with_name('workflow-state.py'))
            store = (wf.Store(canonical,allow_unselected=True,neutral=True) if explicit_source
                     else wf.Store(root,allow_unselected=True))
            cleanup_run_id = None
            source_checkout = None
            with ws.publication_lock(root,snapshot.get('remote','origin'),snapshot.get('target_branch',key)):
                carrier=_review_path(store,key)
                carrier_hash=hashlib.sha256(carrier.read_bytes()).hexdigest() if carrier.exists() else None
                if args.command == 'observe' and explicit_source and 'expected_publication_sha256' in payload:
                    expected = payload['expected_publication_sha256']
                    if (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected)
                            or expected != carrier_hash):
                        raise ReviewError('The publication changed after handoff preparation')
                original=json.loads(carrier.read_text()) if carrier.exists() else None
                if explicit_source:
                    source_checkout=existing_source_checkout(store,payload['source_checkout'],original,key,snapshot)
                    verified_files=existing_source_files(source_checkout,original['identity'])
                    if set(snapshot.get('changed_files',[])) != set(verified_files):
                        raise ReviewError('Current provider diff differs from the verified source checkout')
                    store.source_root=Path(source_checkout['path'])
                if explicit_source:
                    prepared_review=isolated_review_requirements(store,snapshot,original,key,wf)
                else:
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
                    if explicit_source:
                        if existing_source_checkout(store,payload['source_checkout'],record,key,snapshot)!=source_checkout:
                            raise ReviewError('The selected PR source worktree changed before the review writer')
                        if prepared_review is None:
                            isolated_review_requirements(store,snapshot,record,key,wf)
                    if prepared_review:wf._hook_watch_guard(prepared_review['watch'],prepared_review['package_root'])
                    record=_retire_review_hook_references(store,record,snapshot)
                    if args.command=='init':
                        params=parameters(snapshot['source_branch'],payload)
                        if params['source_branch']!=snapshot['source_branch'] or params['target_branch']!=snapshot['target_branch']:raise ReviewError('Publication parameter/snapshot identity conflict')
                        retarget=bool(record and record['identity']['target_branch']!=snapshot['target_branch'])
                        result=reconcile(record,snapshot,retarget=params if args.publication_id else None) if record else new_record(snapshot,params)
                        result['publication_id']=key
                        if 'final_validation' in payload:
                            if not params['authorization'].get('pr'):
                                raise ReviewError('Declaring final validation requires the direct publication invocation')
                            declare_final_validation(store, result, snapshot, payload['final_validation'], existing=record is not None)
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
                        elif args.command=='final-validation':result=final_validation_transition(store,record,snapshot,payload.get('final_validation'))
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
                grant = payload.get('profile_authorization')
                retained = result.get('profile_maintenance', {})
                automatic_profile = (observed_integration and args.command in {'init', 'observe'}
                                     and result['order_completed']
                                     and (grant is not None or
                                          (retained.get('status') in {'prepared', 'retryable'} and
                                           retained.get('authorization', {}).get('target_head')
                                           == result['local_target_sync']['local_head'])))
                with store.lock():
                    current_hash = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
                    if current_hash != carrier_hash:
                        raise ReviewError('The inspected publication carrier changed before recording the result')
                    if explicit_source:
                        if existing_source_checkout(store,payload['source_checkout'],record,key,snapshot)!=source_checkout:
                            raise ReviewError('The selected PR source worktree changed before recording the result')
                        if prepared_review is None:
                            isolated_review_requirements(store,snapshot,record,key,wf)
                    if prepared_review:wf._hook_watch_guard(prepared_review['watch'],prepared_review['package_root'])
                    state=store.load() if store.state.exists() else None
                    registry=(state or {}).get('run_registry') or {}
                    matches=[r for r in registry.get('runs',{}).values()
                             if r.get('workspace',{}).get('branch')==result['identity']['source_branch']
                             and (not explicit_source or r.get('delivery',{}).get('publication')==relative)]
                    if len(matches)>1:raise ReviewError('Publication run identity is ambiguous')
                    carrier_write={relative:json.dumps(result,sort_keys=True,indent=2)+'\n'}
                    if not explicit_source or not matches:
                        store.commit(carrier_write)
                    if matches:
                        run=matches[0];run.setdefault('delivery',{})['publication']=relative
                        delivery = run['delivery']
                        delivery['status'] = result['status']
                        delivery['authorization'] = result['authorization']
                        if 'local_target_sync' in result:
                            delivery['local_target_sync'] = result['local_target_sync']
                            if 'profile_maintenance' in result:
                                delivery['profile_maintenance'] = result['profile_maintenance']
                            else:
                                delivery.pop('profile_maintenance', None)
                            if result['status'] == 'merged' and not result['order_completed']:
                                delivery['status'] = 'local-target-sync-pending'
                        if result['status'] != 'merged' or 'local_target_sync' in result:
                            delivery['order_completed'] = publication_complete(result)
                        run['delivery']['pr']=result.get('pr');run['delivery']['merge_commit']=result.get('merge_commit')
                        if explicit_source:
                            store.save(store.text(),state,extras=carrier_write,update_navigation=False)
                        else:
                            store.save(store.text(),state)
                        if observed_integration:
                            if result['order_completed']:
                                if automatic_profile:
                                    cleanup_run_id = run['id']
                                else:
                                    result['worktree_cleanup'] = wf.cleanup_after_merge(store, state, run)
                            else:
                                result['worktree_cleanup'] = {'status': 'deferred', 'reason': result['local_target_sync']['reason']}
            if automatic_profile:
                try:
                    result = restore_delivery_profile(root, store, key, grant)
                except (ReviewError, wf.WorkflowError, ws.RunError, OSError, subprocess.TimeoutExpired) as error:
                    result['profile_maintenance_error'] = str(error)
                if cleanup_run_id:
                    try:
                        with ws.publication_lock(root, snapshot['remote'], snapshot['target_branch']), store.lock():
                            persisted = json.loads(path.read_text())
                            state = store.load()
                            run = state['run_registry']['runs'].get(cleanup_run_id)
                            if (run is None or run['delivery'].get('publication') != relative
                                    or persisted != {k: v for k, v in result.items() if k != 'profile_maintenance_error'}):
                                raise ReviewError('The publication changed during profile maintenance')
                            result['worktree_cleanup'] = wf.cleanup_after_merge(store, state, run)
                    except (ReviewError, wf.WorkflowError, ws.RunError, OSError, subprocess.TimeoutExpired) as error:
                        result['worktree_cleanup'] = {'status': 'deferred', 'reason': str(error)}
            result={'publication_id':key,**result}
            if explicit_source:
                result['source_checkout']=source_checkout
        print(json.dumps(result,indent=2,ensure_ascii=False));return 0
    except HandoffHold as exc:
        print(json.dumps(exc.result,ensure_ascii=False));return 2
    except (ReviewError,ws.RunError,OSError,ValueError,KeyError,subprocess.TimeoutExpired) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False));return 2

if __name__=='__main__':raise SystemExit(main())
