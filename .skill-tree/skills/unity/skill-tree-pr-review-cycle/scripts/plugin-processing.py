"""Owned post-processing application state within a shared clarification."""
from copy import deepcopy
import json
from pathlib import Path
import re
import uuid


OPERATION = 'skill-tree-process-future-pending'
BOUNDARY = OPERATION + ':after'
MODE = 'required-processing'
BLOCKED = 'Blocked pending answers'

# The verified workflow loader supplies the existing Store and clarification API.
wf = None


def require(condition, message):
    if not condition:
        raise wf.WorkflowError(message)


def hash_value(value):
    return wf.digest(wf.dump(value).encode())


def package_location(store, payload, *, applications_only=False):
    root = store.source_root
    profile_path = wf._hook_safe(root, '.skill-tree/installation/profile.json')
    registry_path = wf._hook_safe(root, '.skill-tree/installation/plugins.json')
    profile_bytes = profile_path.read_bytes() if profile_path.is_file() else None
    registry_bytes = registry_path.read_bytes() if registry_path.is_file() else None
    profile = json.loads(profile_bytes) if profile_bytes else {}
    destinations = {root / relative: entry for relative, entry in profile.get('destinations', {}).items()
                    if entry.get('name') == OPERATION}
    provided = payload.get('package_root')
    local = Path(wf.__file__).absolute().parent.parent
    if provided is not None:
        require(isinstance(provided, str) and provided.strip(), 'Processing requires an actual owned operation package')
        package = Path(provided).absolute()
        require(package in destinations or not destinations and package == local,
                'Processing package differs from the owned operation destination')
    elif local in destinations:
        package = local
    elif destinations:
        package = sorted(destinations)[0]
    elif local.name == OPERATION and (local / 'references/plugin-bindings.json').exists():
        package = local
    else:
        package = None
    observed = {str(profile_path): wf.digest(profile_bytes) if profile_bytes is not None else None,
                str(registry_path): wf.digest(registry_bytes) if registry_bytes is not None else None}
    registry = json.loads(registry_bytes) if registry_bytes else {}
    if package is None:
        require(not _configured(registry, applications_only=applications_only),
                'Configured post-processing requires an owned Processing package')
        return package, observed, None
    path = wf._hook_safe(package, 'references/plugin-bindings.json')
    data = path.read_bytes()
    observed[str(path)] = wf.digest(data)
    entry = destinations.get(package)
    if entry is not None:
        require(entry.get('files', {}).get('references/plugin-bindings.json') == observed[str(path)],
                'The installed Processing manifest differs from the owned profile')
    manifest = json.loads(data)
    require(manifest.get('operation') == OPERATION and isinstance(manifest.get('bindings'), list),
            'The owned Processing binding manifest is unavailable')
    live_required = _configured(registry, applications_only=applications_only)
    composed_required = _configured(manifest, applications_only=applications_only)
    require(not live_required or registry.get('identity') == manifest.get('registry_identity'),
            'The active post-processing configuration requires an owned refresh')
    if composed_required and manifest.get('registry_present'):
        require(registry_bytes is not None, 'The managed post-processing registry is unavailable')
    return package, observed, manifest


def candidate(row):
    if not isinstance(row, dict) or row.get('operation') != OPERATION or row.get('enabled') is not True:
        return False
    location = row.get('location', {})
    if location.get('boundary_id'):
        return location['boundary_id'] == BOUNDARY
    # A not-yet-resolved named row is conservatively inspected by Node.
    return row.get('anchor') not in {'before', 'during'}


def _configured(source, *, applications_only):
    for row in source.get('bindings', []):
        if not candidate(row):
            continue
        if not applications_only or 'application' in row:
            return True
        package = source.get('packages', {}).get(row.get('plugin_id'), {})
        declaration = package.get('adaptation', {}).get('processing_application')
        if isinstance(declaration, dict) and 'default_role' in declaration:
            return True
    return False


def application(configuration, row):
    try:
        return wf.hook_helper().processing_application(configuration, row)
    except ValueError as error:
        raise wf.WorkflowError(str(error)) from error


def _replace_task(text, task, entry):
    lines = text.splitlines(keepends=True)
    lines[task['start']:task['end']] = [entry]
    return ''.join(lines)


def _block(text, task, marker):
    if marker in task['body']:
        raise wf.WorkflowError('The owned processing hold marker already exists')
    entry = task['body'].rstrip() + '\n\n' + marker + '\n\n'
    entry = re.sub(r'(?m)^status: Ready$', 'status: ' + BLOCKED, entry, count=1)
    return _replace_task(text, task, entry)


def _fingerprints(task):
    baseline = wf.clarification_baselines([task])
    return {'semantic_fingerprint': wf.clarification_fingerprints(baseline)[task['id']],
            'content_fingerprint': baseline[task['id']]['content_hash']}


def _context(task, session_id):
    return {'kind': 'task', 'id': 'task-scope:' + task['id'], 'task_ids': [task['id']],
            'pending_ids': task['parent_pending_ids'], 'session_id': session_id, 'parent_mode_epoch': 0,
            'body': task['body'], **_fingerprints(task)}


def _policy(record, payload, selected):
    mode = payload.get('decision_mode', 'auto')
    require(mode in {'auto', 'manual'}, 'Unknown processing decision mode')
    parent = payload.get('decision_authority')
    grant = None
    if parent is not None:
        parent = wf.decision_helper().validate_authority(parent, {'id': 'pending-scope:' + ','.join(selected)}, mode)
        require(not parent.get('revoked'), 'A revoked Pending grant cannot authorize processing')
        grant = {**parent, 'context_id': 'task-scope:' + record['task_ids'][0]}
    executor = payload.get('decision_executor')
    if executor is not None:
        executor = wf.hook_helper().actor(executor)
    if mode == 'auto' and (grant is None or executor is None):
        record.update(state='blocked', next_action='Supply the actual owner grant and executor for this Auto clarification')
    record.update(decision_mode=mode, decision_authority=grant, decision_executor=executor,
                  decision_mode_epoch=0, decision_mode_history=[])
    return parent


def _request(store, payload, event, context):
    result = {'runtime_action': 'requirement-plan', 'project_root': str(store.source_root),
              'event': event, 'context': context, 'capabilities': deepcopy(payload.get('capabilities', [])),
              'adapter': deepcopy(payload.get('adapter', {'provider': 'codex', 'mechanism': 'source-backed-context'})),
              'run_overrides': deepcopy(payload.get('run_overrides', {}))}
    if 'execution_policy' in payload:
        result['execution_policy'] = deepcopy(payload['execution_policy'])
    return result


def _selected(configuration, proof):
    applicable = {row['id'] for row in proof['bindings']} | {row['id'] for row in proof['unresolved']}
    return {row['id']: application(configuration, row) for row in configuration['bindings'] if row['id'] in applicable}


def prepare_publication(store, payload, allocated, processing_id):
    package, observed, manifest = package_location(store, payload, applications_only=True)
    result = {'package': package, 'observed': observed, 'sessions': {}, 'watch': None}
    if manifest is None or not _configured(manifest, applications_only=True):
        return result
    require(not getattr(store, '_writer_active', False) and not (store.base / '.writer-lock').exists(),
            'Post-processing preparation requires the outside-writer boundary')
    text = store.text()
    source_hash = wf.digest(text.encode())
    store.guard(payload.get('expected_source_hash'))
    state = store.load(text)
    proposed, receipt = wf._processing_proposal(store, payload, text, state, allocated, processing_id)
    result.update(source_hash=source_hash, proposal_hash=wf.digest(proposed.encode()),
                  request_hash=hash_value(payload), watch=wf._hook_watch(package, store.source_root))
    for tid in dict.fromkeys(receipt['created_ids'] + receipt['reused_ids']):
        original = wf.resolve(wf.parse(proposed), [tid], 'Prioritized Next Changes')[0]
        session_id = wf.identity('CL')
        marker = 'Processing readiness:\n- [Unresolved - blocks implementation] Required post-processing clarification ' + session_id + '.'
        prospective = _block(proposed, original, marker)
        held = wf.resolve(wf.parse(prospective), [tid], 'Prioritized Next Changes')[0]
        context = _context(held, session_id)
        run = state.get('active_run')
        if run and tid in run['admitted_task_ids']:
            context['run_id'] = run['id']
        request_id = 'post-processing:' + session_id
        event = {'id': request_id, 'operation': OPERATION, 'anchor': 'after'}
        request = _request(store, payload, event, context)
        metadata = wf._hook_node(package, request)
        proof, configuration = metadata['proof'], metadata['configuration']
        require(proof.get('proof_kind') == 'completed-readiness' and proof.get('context') == context,
                'Post-processing configuration must come from exact owned requirement preparation')
        selected = _selected(configuration, proof)
        if not any(role is not None for role in selected.values()):
            continue
        baseline = wf.clarification_baselines([held])
        record = {'schema': 1, 'id': session_id, 'revision': 1, 'mode': MODE, 'task_ids': [tid],
                  'state': 'researching', 'baselines': baseline,
                  'semantic_fingerprints': wf.clarification_fingerprints(baseline), 'facts': {}, 'questions': {},
                  'rounds': [], 'answers': {}, 'task_revisions': [], 'confirmation': None, 'clarity': None,
                  'no_progress_rounds': 0, 'next_action': 'Start the exact configured post-processing chain',
                  'created_at': wf.now()}
        parent_grant = _policy(record, payload, receipt['selected_ids'])
        record['processing_requirements'] = {
            'schema': 1, 'processing_id': processing_id, 'selected_pending_ids': receipt['selected_ids'],
            'configuration': configuration, 'execution_snapshot': proof['execution_snapshot'],
            'package_path': _package_path(store, package),
            'task_holds': {tid: {'status': BLOCKED, 'original_status': original['status'], 'marker': marker}},
            'required_bindings': list(selected), 'applications': selected, 'context': context,
            'event': proof['event'], 'request_id': request_id, 'chain_id': None,
            'capabilities': request['capabilities'], 'adapter': request['adapter'],
            'prerequisites': proof['prerequisites'], 'parent_authority': parent_grant,
            'contributions': {}, 'rechecks': {}, 'adoptions': [], 'retired_chains': [], 'finalization': None,
        }
        result['sessions'][tid] = record
    guard_publication(store, payload, result)
    return result


def guard_publication(store, payload, prepared):
    for path, expected in prepared['observed'].items():
        require(wf.file_hash(Path(path)) == expected, 'The owned Processing installation changed during preparation')
    if prepared['watch'] is not None:
        store.guard(prepared['source_hash'])
        require(hash_value(payload) == prepared['request_hash'], 'The researched Processing proposal changed')
        wf._hook_watch_guard(prepared['watch'], prepared['package'])


def _required_attachment(before_text, before, after, tasks, receipt):
    if before['id'] in receipt['reused_ids']:
        return []
    children = [tid for tid in receipt['created_ids'] + receipt['reused_ids']
                if tasks[tid]['related_task_id'] == before['id'] and tasks[tid]['relation'] in {'blocker', 'subtask'}]
    added = [tid for tid in dict.fromkeys(children) if tid not in before['depends_on']]
    if not added:
        return []
    expected = wf.rewrite_meta(before_text, before['id'], {'depends_on': before['depends_on'] + added})
    expected_task = wf.resolve(wf.parse(expected), [before['id']], 'Prioritized Next Changes')[0]
    return added if after['body'] == expected_task['body'] else []


def attach_existing_changes(store, before_text, text, receipt, state):
    before = {task['id']: task for task in wf.parse(before_text) if task['queue'] == 'Prioritized Next Changes'}
    tasks = {task['id']: task for task in wf.parse(text) if task['queue'] == 'Prioritized Next Changes'}
    changed = {tid for tid in before if tasks[tid]['body'] != before[tid]['body']}
    if not changed:
        return text, {}
    reopened = {}
    for path in (store.base / 'clarifications').glob('cl-*.json'):
        record = wf.clarification_read(store, 'CL-' + path.stem[3:])
        if not changed.intersection(record['task_ids']):
            continue
        if record['mode'] != MODE:
            require(record['state'] in {'complete', 'cancelled'}, 'A changed task already belongs to a clarification session')
            continue
        tid = record['task_ids'][0]
        added = _required_attachment(before_text, before[tid], tasks[tid], tasks, receipt)
        if record['state'] != 'complete' and added:
            pending_guard(store, record)
            raise wf.WorkflowError('Complete the original post-processing clarification ' + record['id']
                                   + ' before retrying the required-child Pending promotion')
        require(record['state'] == 'complete' and tid not in reopened,
                'A changed task already belongs to a clarification session')
        require(added, 'A released processing task retains exact prior provenance and requires a separate task or explicit scoped recovery')
        _verify_finalization(store, record, before[tid])
        pending_guard(store, record)
        progress = state.get('task_progress', {}).get(tid, {})
        run = state.get('active_run') or {}
        owners = (progress.get('run_id'), state.get('run_registry', {}).get('claims', {}).get(tid))
        require(all(owner in {None, run.get('id')} for owner in owners),
                'The released processing parent belongs to another run')
        wf.clarification_progress_guard(state, tid)
        text = _reopen_held(store, record, wf.clarification_tasks(store, [tid], text)[0], text,
                            'processing-required-child', {'processing_id': receipt['id'], 'added_dependency_ids': added})
        reopened[tid] = record
    return text, reopened


def guard_implementation_progress(store, task):
    if task['status'] != 'Ready' and session_for_task(store, task['id']):
        raise wf.WorkflowError('Complete the owned post-processing clarification before implementation or new validation')


def publish(store, text, state, receipt, prepared):
    require(wf.digest(text.encode()) == prepared['proposal_hash'], 'The prepared task allocations or proposal changed')
    records = prepared['sessions']
    for tid, record in records.items():
        require(tid not in state.get('task_progress', {}), 'A task with active implementation cannot enter a processing hold')
        task = wf.resolve(wf.parse(text), [tid], 'Prioritized Next Changes')[0]
        marker = record['processing_requirements']['task_holds'][tid]['marker']
        text = _block(text, task, marker)
        held = wf.resolve(wf.parse(text), [tid], 'Prioritized Next Changes')[0]
        published_context = _context(held, record['id'])
        run = state.get('active_run')
        if run and tid in run['admitted_task_ids']:
            published_context['run_id'] = run['id']
        require(published_context == record['processing_requirements']['context'],
                'The published hold differs from the exact selected prospective task')
    return text, records


def publication_writes(store, text, records, reopened):
    source_hash = wf.digest(text.encode())
    writes = {}
    for record in reopened.values():
        record['task_revisions'][-1]['source_after'] = source_hash
    for record in [*records.values(), *reopened.values()]:
        path = wf.clarification_path(store, record['id']).relative_to(store.root).as_posix()
        previous = record.pop('session_hash', None)
        store.expect_unchanged(path, previous)
        if previous is not None:
            record['revision'] += 1
        record.update(source_hash=source_hash, updated_at=wf.now())
        writes[path] = wf.dump(record)
    return writes


def requirements(record):
    value = record.get('processing_requirements')
    require(record.get('mode') == MODE and isinstance(value, dict) and value.get('schema') == 1,
            'The actual required post-processing session is unavailable')
    return value


def linked(store, context):
    session_id = context.get('session_id')
    if not session_id:
        return None
    record = wf.clarification_read(store, session_id)
    if record.get('mode') != MODE:
        return None
    req = requirements(record)
    require(context.get('task_ids') == record['task_ids'] and all(
        context.get(key) == req['context'].get(key) for key in ('id', 'kind', 'pending_ids')),
        'Post-processing context differs from the exact registered task and provenance')
    return record


def _chain_id(request_id):
    return 'HC-' + str(uuid.uuid5(uuid.NAMESPACE_URL, 'skill-tree-invocation:' + request_id))


def _spec(record, context):
    req = requirements(record)
    recheck_id = context.get('processing_recheck_id')
    require((recheck_id is None) == (context.get('processing_recheck_digest') is None),
            'A processing recheck requires both exact mandate identifiers')
    if recheck_id is None:
        return req
    value = req['rechecks'].get(recheck_id)
    require(value is not None and value['mandate_digest'] == context['processing_recheck_digest'],
            'The actual CL-owned editorial recheck mandate is unavailable')
    return value


def check_start(store, record, context, event, configuration, snapshot, payload):
    req = requirements(record)
    spec = _spec(record, context)
    require(record['state'] not in {'complete', 'cancelled'} and (record['decision_mode'] == 'manual'
            or record.get('decision_authority') and record.get('decision_executor')),
            'The post-processing session requires a current decision policy before invocation')
    require(not payload.get('supersedes_chain_id'), 'Use explicit processing configuration adoption for this CL')
    require(payload.get('request_id') == spec['request_id'] and event == spec['event'],
            'Post-processing requires the exact registered request and after boundary')
    require(configuration == req['configuration'] and snapshot == req['execution_snapshot'],
            'Post-processing requires the original full frozen configuration and execution source')
    require(not spec.get('retired') and spec.get('chain_id') in {None, _chain_id(spec['request_id'])},
            'Post-processing already has an original registered chain')
    require(context == wf.actual_hook_context(store, spec['context']),
            'Post-processing requires the exact current owned task context')
    guard_current_scope(store, record, context)


def check_snapshot(record, snapshot):
    require(snapshot == requirements(record)['execution_snapshot'],
            'The registered post-processing execution snapshot changed; use explicit processing configuration adoption')


def check_live(record, frame, context):
    spec = _spec(record, context)
    require(not spec.get('retired') and spec.get('chain_id') == frame['id'] and frame['configuration'] == requirements(record)['configuration']
            and frame['event'] == spec['event'], 'The invocation does not belong to the current post-processing chain')
    check_snapshot(record, frame['execution_snapshot'])


def register_chain(store, writes, record, context, chain_id, grant, executor):
    spec = _spec(record, context)
    require(spec['chain_id'] is None and chain_id == _chain_id(spec['request_id']),
            'The original post-processing chain registration changed')
    spec['chain_id'] = chain_id
    if record['decision_mode'] == 'manual' and record['decision_authority'] is None:
        record['decision_authority'] = deepcopy(grant)
        record['decision_executor'] = deepcopy(executor)
    record['revision'] += 1
    record['updated_at'] = wf.now()
    record.pop('session_hash', None)
    path = wf.clarification_path(store, record['id']).relative_to(store.root).as_posix()
    writes[path] = wf.dump(record)


def _current_attempt(store, record, chain_id, attempt_id):
    chain = wf.hook_helper().read(store, chain_id)
    context = chain['context']
    require(context.get('session_id') == record['id'], 'The contribution belongs to another clarification')
    check_live(record, chain, context)
    require(attempt_id == chain.get('prepared_attempt_id'), 'The contribution requires the original current invocation')
    attempt = chain['attempts'].get(attempt_id)
    require(attempt and attempt['status'] == 'returned' and attempt.get('invoke_evidence') and attempt.get('result_evidence'),
            'The original invocation has no actual returned contribution')
    current = wf.actual_hook_context(store, context)
    require(current['parent_mode_epoch'] == context.get('parent_mode_epoch'), 'The returned contribution belongs to another mode epoch')
    wf._hook_policy_guard(store, current, chain['mode'], chain['authority'], chain['executor'])
    location = wf._hook_locator(store, chain_id)
    wf._hook_watch_guard(location['watch'], location['package_root'])
    wf._hook_scope_source_guard(store, attempt['input']['scope_source_snapshot'])
    return chain, attempt


def _question_specs(record, attempt):
    result = attempt['result']
    status = result['status']
    questions = result.get('questions') or []
    findings = result.get('findings') or []
    require(isinstance(questions, list) and isinstance(findings, list)
            and bool(questions) == (status == 'questions') and bool(findings) == (status == 'findings'),
            'A post-processing result requires the matching structured question or finding payload')
    for finding in findings:
        require(isinstance(finding, dict) and all(isinstance(finding.get(key), str) and finding[key].strip()
                for key in ('id', 'observation', 'consequence')), 'A post-processing finding requires exact observation and consequence')
        bindings = finding.get('bindings')
        if bindings is not None:
            require(isinstance(bindings, dict) and bindings and set(bindings).issubset(record['task_ids'])
                    and all(isinstance(fields, list) and fields and all(isinstance(field, str) and field in wf.CLARIFICATION_FIELDS for field in fields)
                            and len(fields) == len(set(fields)) for fields in bindings.values()),
                    'Processing findings bind the exact affected selected task fields')
    require(len({finding['id'] for finding in findings}) == len(findings), 'Duplicate post-processing finding')
    namespace = 'hook-' + attempt['id'][3:] + '-'
    ids = set()
    for question in questions:
        require(isinstance(question, dict) and isinstance(question.get('id'), str)
                and re.fullmatch('[a-z][a-z0-9-]*', question['id']) and question['id'] not in ids,
                'A returned question requires a unique stable identity')
        ids.add(question['id'])
    specs = []
    fact_requests = {}
    for question in questions:
        item = deepcopy(question)
        item['id'] = namespace + item['id']
        item['required'] = True
        prerequisites = item.get('prerequisites', [])
        require(isinstance(prerequisites, list) and all(isinstance(v, str) for v in prerequisites),
                'Returned question prerequisites require stable identities')
        item['prerequisites'] = [namespace + value if value in ids else value for value in prerequisites]
        fact_ids = item.pop('fact_prerequisites', [])
        require(isinstance(fact_ids, list) and all(isinstance(v, str) and re.fullmatch('[a-z][a-z0-9-]*', v) for v in fact_ids)
                and len(set(fact_ids)) == len(fact_ids), 'Factual prerequisites require distinct stable identities')
        if fact_ids:
            fact_requests[item['id']] = [item['id'] + '-fact-' + value + '-' + hash_value([item['id'], value])
                                         for value in fact_ids]
        specs.append(item)
    return specs, fact_requests


def register_contribution(store, record, payload):
    chain, attempt = _current_attempt(store, record, payload.get('chain_id'), payload.get('attempt_id'))
    req = requirements(record)
    existing = req['contributions'].get(attempt['id'])
    if existing is not None:
        require(existing['result_digest'] == wf.hook_helper().digest(attempt['result']), 'Conflicting replay of a processing contribution')
        return
    live = wf.actual_hook_context(store, chain['context'])
    require(_point(live) == _point(attempt['input']['context']) == _baseline_point(record),
            'Register the original returned contribution before revising the task')
    specs, facts = _question_specs(record, attempt)
    wf.clarification_questions(record, specs)
    contribution = {'chain_id': chain['id'], 'attempt_id': attempt['id'], 'binding_id': attempt['binding_id'],
                    'input_digest': attempt['input_digest'], 'result_digest': wf.hook_helper().digest(attempt['result']),
                    'question_ids': [spec['id'] for spec in specs], 'fact_prerequisites': facts,
                    'questions': {spec['id']: deepcopy(record['questions'][spec['id']]) for spec in specs},
                    'decision_mode_epoch': record['decision_mode_epoch'], 'executor': deepcopy(chain['executor']),
                    'revision_start': len(record['task_revisions']),
                    'fields_before': {tid: deepcopy(row['fields']) for tid, row in record['baselines'].items()}}
    req['contributions'][attempt['id']] = contribution
    if specs:
        record.update(state='researching', clarity=None, confirmation=None,
                      next_action='Resolve the registered post-processing contribution through the same clarification')


def guard_questions(record, specs):
    req = requirements(record)
    owned = {qid for item in req['contributions'].values() for qid in item['question_ids']}
    for spec in specs if isinstance(specs, list) else []:
        if isinstance(spec, dict) and spec.get('id') in owned:
            raise wf.WorkflowError('A registered required plugin question cannot be replaced or downgraded')


def fact_contexts(store, record):
    """Bind each question to the live facts required by it and its prerequisites."""
    direct = {}
    seen_actors = set()
    stale = set(wf.clarification_stale_facts(store, record))
    for contribution in requirements(record)['contributions'].values():
        executor = contribution['executor']
        for qid, facts in contribution['fact_prerequisites'].items():
            values = {}
            for fid in facts:
                fact = record['facts'].get(fid, {})
                evidence = fact.get('producer_evidence', {})
                key = (evidence.get('actor_id'), evidence.get('actor_context_id'))
                valid = (fid not in stale and evidence.get('kind') == 'fresh-factual-helper-result'
                         and all(isinstance(evidence.get(k), str) and evidence[k].strip()
                                 for k in ('actor_id', 'actor_context_id', 'creation_reference', 'reference', 'provider', 'tool'))
                         and evidence.get('session_id') == record['id'] and evidence.get('question_id') == qid
                         and evidence.get('fact_id') == fid and evidence.get('input_digest') == contribution['input_digest']
                         and evidence.get('parent_mode_epoch') == contribution['decision_mode_epoch']
                         and key[0] != executor.get('id') and key[1] != executor.get('context_id'))
                if valid and key not in seen_actors:
                    values[fid] = hash_value(fact)
                    seen_actors.add(key)
            direct[qid] = values if len(values) == len(facts) else None
    current = {}

    def collect(qid):
        if qid in current:
            return current[qid]
        own = direct.get(qid, {})
        ancestors = [collect(key) for key in record['questions'][qid]['prerequisites']]
        if own is None or any(value is None for value in ancestors):
            current[qid] = None
        else:
            combined = dict(own)
            for value in ancestors:
                combined.update(value)
            current[qid] = combined
        return current[qid]

    for key in record['questions']:
        collect(key)
    return current


def invalidate_fact_answers(record, current):
    rounds = {item['id']: item for item in record['rounds']}
    changed = False
    for key, answer in record['answers'].items():
        previous = rounds[answer['round_id']].get('fact_fingerprints', {}).get(key, {})
        if answer.get('valid') and current[key] != previous:
            answer['valid'] = False
            changed = True
    if changed:
        if record.get('confirmation'):
            record.setdefault('confirmation_history', []).append(record['confirmation'])
        record.update(clarity=None, confirmation=None)


def _point(context):
    return {key: context[key] for key in ('semantic_fingerprint', 'content_fingerprint')}


def _baseline_point(record):
    tid = record['task_ids'][0]
    return {'semantic_fingerprint': record['semantic_fingerprints'][tid],
            'content_fingerprint': record['baselines'][tid]['content_hash']}


def revision_path(record, before, after, *, expected_ids=None, from_revision=None):
    tid = record['task_ids'][0]
    revisions = record['task_revisions']
    if expected_ids is not None:
        require(isinstance(expected_ids, list), 'The accepted revision path is malformed')
        if not expected_ids:
            require(before == after, 'An empty revision receipt cannot bind changed task wording')
            return []
        start = next((i for i, revision in enumerate(revisions) if revision['id'] == expected_ids[0]), None)
        require(start is not None, 'The accepted revision receipt does not exist in this clarification')
        segment = revisions[start:start + len(expected_ids)]
        require([item['id'] for item in segment] == expected_ids, 'The accepted revision receipt does not bind a contiguous segment')
        starts = [segment]
    elif from_revision is not None:
        require(type(from_revision) is int and 0 <= from_revision <= len(revisions), 'The original contribution revision position is invalid')
        starts = [revisions[from_revision:]]
    else:
        if before == after:
            return []
        starts = [revisions[start:] for start, item in enumerate(revisions)
                  if item.get('task_fingerprints', {}).get(tid, {}).get('before') == before]
    for segment in starts:
        cursor = before
        path = []
        for step in segment:
            pair = step.get('task_fingerprints', {}).get(tid)
            if not pair or pair['before'] != cursor:
                break
            path.append(step['id'])
            cursor = pair['after']
            if expected_ids is None and from_revision is None and cursor == after:
                return path
        if cursor == after and len(path) == len(segment):
            return path
    raise wf.WorkflowError('The actual post-processing task changes lack a contiguous clarification revision path')


def _answers(store, record, keys):
    current_facts = fact_contexts(store, record)
    references = {}
    for key in keys:
        question = record['questions'].get(key)
        answer = record['answers'].get(key)
        round_record = next((r for r in record['rounds'] if answer and r['id'] == answer['round_id']), None)
        require(question and answer and answer.get('valid') and round_record
                and current_facts[key] == round_record.get('fact_fingerprints', {}).get(key, {})
                and answer['question_revision'] == question['revision']
                and round_record['question_revisions'].get(key) == question['revision'],
                'The current required processing question has no actual answer: ' + key)
        epoch = round_record.get('decision_mode_epoch', 0)
        policy_record = record
        if epoch != record['decision_mode_epoch']:
            previous = next((entry for entry in record['decision_mode_history'] if entry['previous_epoch'] == epoch), None)
            require(previous is not None, 'A settled answer belongs to an unknown prior policy epoch')
            wf.clarification_evidence(previous['evidence'])
            policy_record = {**record, **previous['previous_policy'], 'decision_mode_epoch': epoch}
        wf.clarification_answer_evidence(store, policy_record, answer, 'answer', key)
        references[key] = {'round_id': round_record['id'], 'question_revision': question['revision'],
                           'answer_digest': hash_value(answer)}
    return references


def _clarity(store, record):
    value = record.get('clarity')
    require(value and value['semantic_fingerprints'] == record['semantic_fingerprints']
            and all(item is True for key, item in value['assessment'].items() if key != 'evidence')
            and not wf.clarification_stale_facts(store, record), 'A current clarity recheck is required')
    return hash_value(value)


def verify_contribution(store, chain, attempt, supplied, after):
    record = linked(store, chain['context'])
    require(record is not None, 'A processing contribution requires an actual shared clarification')
    _current_attempt(store, record, chain['id'], attempt['id'])
    req = requirements(record)
    contribution = req['contributions'].get(attempt['id'])
    require(contribution and supplied.get('processing_contribution_id') == attempt['id']
            and contribution['input_digest'] == attempt['input_digest']
            and contribution['result_digest'] == wf.hook_helper().digest(attempt['result'])
            and contribution['decision_mode_epoch'] == record['decision_mode_epoch'],
            'Use the registered original post-processing contribution')
    require(_point(after) == _baseline_point(record), 'The post-processing task requires a current guarded clarification revision')
    revisions = revision_path(record, _point(attempt['input']['context']), _point(after),
                              from_revision=contribution['revision_start'])
    answers = {}
    clarity = None
    disposition = None
    if attempt['result']['status'] == 'questions':
        required = {key for key, question in record['questions'].items() if question['required']}
        answers = _answers(store, record, sorted(required | set(contribution['question_ids'])))
        clarity = _clarity(store, record)
    if attempt['result']['status'] == 'findings':
        changes = {tid: set() for tid in record['task_ids']}
        for revision in record['task_revisions']:
            if revision['id'] not in revisions:
                continue
            for tid, fields in revision['changed_fields'].items():
                changes[tid].update(fields)
            for tid in revision.get('content_changed_task_ids', []):
                changes[tid].add('content')
        for tid, fields in changes.items():
            net = {field for field, value in record['baselines'][tid]['fields'].items()
                   if value != contribution['fields_before'][tid][field]}
            if _point(after)['content_fingerprint'] != _point(attempt['input']['context'])['content_fingerprint']:
                net.add('content')
            fields.intersection_update(net)
        unresolved = [finding['id'] for finding in attempt['result']['findings']
                      if not finding.get('bindings') or any(not set(fields).intersection(changes[tid])
                                                          for tid, fields in finding['bindings'].items())]
        if unresolved:
            reference = supplied.get('decision_receipt')
            require(reference is not None, 'A processing finding requires a matching task revision or an actual scoped dismissal')
            context = wf._hook_resolution_context(after, chain, attempt, 'hook-result-resolution')
            decision = wf.decision_helper().acceptance_reference(store, reference, {
                'context': context, 'mode': chain['mode'], 'kind': 'technical', 'authority_digest': wf.decision_helper()._hash(chain['authority'])})
            require(decision['answer'] == 'dismiss', 'An unchanged finding requires an actual current dismissal')
            disposition = deepcopy(reference)
    return {'kind': 'core-incorporation' if revisions else 'core-resolution',
            'reference': '.skill-tree/clarifications/' + record['id'].lower() + '.json',
            'session_id': record['id'], 'processing_contribution_id': attempt['id'],
            'chain_id': chain['id'], 'attempt_id': attempt['id'], 'result_digest': contribution['result_digest'],
            'before': wf.hook_helper().digest(chain['context']), 'after': wf.hook_helper().digest(after),
            'revision_ids': revisions, 'answer_refs': answers, 'clarity_fingerprint': clarity,
            'decision_receipt': disposition, 'mode_epoch': record['decision_mode_epoch'], 'final_confirmation': False}


def _policy_digest(record):
    return hash_value({key: record.get(key) for key in (
        'decision_mode', 'decision_authority', 'decision_executor', 'decision_mode_epoch')})


def _check_historical_policy(store, record, frame):
    epoch = frame['context'].get('parent_mode_epoch')
    if epoch == record['decision_mode_epoch']:
        wf._hook_policy_guard(store, frame['context'], frame['mode'], frame['authority'], frame['executor'])
        return
    previous = next((row for row in record['decision_mode_history'] if row['previous_epoch'] == epoch), None)
    require(previous is not None, 'The completed processing stage belongs to an unknown policy epoch')
    wf.clarification_evidence(previous['evidence'])
    policy = previous['previous_policy']
    require((frame['mode'], frame['authority'], frame['executor']) ==
            (policy['decision_mode'], policy['decision_authority'], policy['decision_executor']),
            'The completed processing stage differs from its actual historical authority')


def _completed_chain(store, record, spec, required_ids):
    req = requirements(record)
    chain_id = spec.get('chain_id')
    require(chain_id and chain_id == _chain_id(spec['request_id']), 'The required post-processing chain has not started')
    chain = wf.hook_helper().read(store, chain_id)
    require(chain['state'] == 'complete', 'The required post-processing chain is unfinished')
    check_live(record, chain, chain['context'])
    _check_historical_policy(store, record, chain)
    stages = {stage['binding_id']: stage for stage in chain['stages']}
    for binding in required_ids:
        stage = stages.get(binding)
        require(stage and stage['status'] == 'complete' and stage['attempt_ids'],
                'A required processing occurrence has no accepted original invocation: ' + binding)
    completed = {}
    for binding, stage in stages.items():
        if stage['status'] != 'complete':
            continue
        attempt = chain['attempts'][stage['attempt_ids'][-1]]
        transition = stage['accepted_transition']
        receipt = transition['receipt']
        contribution = req['contributions'].get(attempt['id'])
        require(attempt['status'] == 'returned' and attempt.get('invoke_evidence') and attempt.get('result_evidence')
                and transition['after'] == stage['accepted_context']
                and transition['before'] == attempt['input']['context'],
                'A completed processing occurrence lacks its original accepted result')
        if receipt['kind'] == 'no-change':
            require(attempt['result']['status'] == 'passed' and not attempt['result'].get('questions')
                    and not attempt['result'].get('findings') and transition['before'] == transition['after'],
                    'A no-change receipt cannot settle a returned processing contribution')
        else:
            require(contribution and receipt.get('processing_contribution_id') == attempt['id']
                    and contribution['result_digest'] == receipt.get('result_digest')
                    and contribution['result_digest'] == wf.hook_helper().digest(attempt['result']),
                    'The accepted result lacks its actual registered processing contribution')
        revision_path(record, _point(transition['before']), _point(transition['after']),
                      expected_ids=receipt.get('revision_ids', []))
        completed[binding] = (chain, stage, attempt)
    return chain, completed


def _editor_key(record, item):
    chain, stage, attempt = item
    row = next(r for r in chain['configuration']['bindings'] if r['id'] == stage['binding_id'])
    adapter = application(chain['configuration'], row)
    if not adapter or adapter['role'] != 'task-editorial':
        return None
    package = chain['configuration']['packages'][row['plugin_id']]
    return hash_value({'plugin_id': row['plugin_id'], 'revision': package['revision'],
                       'content_digest': package['content_digest'], 'application': adapter})


def _main_editors(record, completed):
    editors = {}
    for item in completed.values():
        key = _editor_key(record, item)
        if key:
            editors[key] = item
    return editors


def _main(store, record):
    req = requirements(record)
    if not req['required_bindings']:
        require(req['chain_id'] is None, 'An empty adopted requirement cannot supply a successful invocation')
        return None, {}
    return _completed_chain(store, record, req, req['required_bindings'])


def _mandate_digest(mandate):
    return hash_value({key: value for key, value in mandate.items()
                       if key not in {'chain_id', 'mandate_digest', 'context', 'event'}})


def _read_mandate(store, record, context, event):
    req = requirements(record)
    mandate = _spec(record, context)
    require(mandate is not req and mandate['mandate_digest'] == _mandate_digest(mandate)
            and mandate['event'] == event == {**req['event'], 'id': mandate['request_id']}
            and mandate['configuration_digest'] == req['configuration']['configuration_digest'],
            'The derived post-processing recheck mandate differs from the frozen scope')
    main, completed = _main(store, record)
    item = completed.get(mandate['origin_binding_id'])
    require(main and item and main['id'] == mandate['origin_chain_id']
            and main['chain_hash'] == mandate['origin_chain_hash'] and item[2]['id'] == mandate['origin_attempt_id']
            and _editor_key(record, item) == mandate['editorial_policy'],
            'The derived editorial recheck lacks the original accepted occurrence')
    row = next(row for row in req['configuration']['bindings'] if row['id'] == mandate['origin_binding_id'])
    require(hash_value(row['effective']) == mandate['effective_digest'], 'Editorial recheck parameters differ from the frozen occurrence')
    return mandate


def recheck_guard(store, context, event, readiness):
    record = linked(store, context)
    require(record is not None and record['state'] != 'cancelled', 'The actual CL-owned editorial mandate is unavailable')
    mandate = _read_mandate(store, record, context, event)
    result = {'recheck_id': mandate['id'], 'mandate_digest': mandate['mandate_digest'],
              'configuration_digest': mandate['configuration_digest'], 'binding_ids': [mandate['origin_binding_id']]}
    if readiness:
        chain, completed = _completed_chain(store, record, mandate, [mandate['origin_binding_id']])
        require(chain['context'] == context, 'Completed derived recheck requires the exact registered context')
        readiness_context(store, record, chain, check_mandates=False)
        result['selection_context'] = completed[mandate['origin_binding_id']][2]['input']['context']
    else:
        require(record['state'] != 'complete' and mandate['policy_digest'] == _policy_digest(record)
                and wf.actual_hook_context(store, context) == context, 'The derived editorial mandate is stale for the current task or policy')
        revision_path(record, mandate['required_input'], _point(context))
        if mandate['chain_id'] is None:
            require(_point(context) == mandate['required_input'], 'The prepared recheck requires the original exact current task input')
    return result


def _completed_rechecks(store, record, require_complete=True):
    req = requirements(record)
    completed = []
    for mandate in sorted(req['rechecks'].values(), key=lambda item: item['sequence']):
        if mandate.get('retired'):
            continue
        if not mandate['chain_id']:
            if require_complete:
                raise wf.WorkflowError('An affected editorial recheck has not completed')
            continue
        current = wf.hook_helper().read(store, mandate['chain_id'])
        if current['state'] != 'complete' and not require_complete:
            continue
        _read_mandate(store, record, current['context'], current['event'])
        chain, stages = _completed_chain(store, record, mandate, [mandate['origin_binding_id']])
        require(set(stages) == {mandate['origin_binding_id']}, 'A derived recheck executed an unrelated configured occurrence')
        item = stages[mandate['origin_binding_id']]
        require(_point(item[2]['input']['context']) == mandate['required_input'],
                'The editorial recheck did not inspect the mandated input')
        completed.append((mandate, chain, item))
    return completed


def affected_editors(store, record, current, require_complete=False):
    main, accepted = _main(store, record)
    latest = _main_editors(record, accepted)
    matched = {key: item[1]['accepted_context'] for key, item in latest.items()}
    derived = _completed_rechecks(store, record, require_complete)
    for mandate, _, item in derived:
        key = mandate['editorial_policy']
        require(key in latest, 'The recheck no longer has an original registered editorial application')
        matched[key] = item[1]['accepted_context']
    return main, derived, {key: latest[key] for key, value in matched.items() if _point(value) != current}


def create_recheck(store, record, payload):
    req = requirements(record)
    origin_binding_id = payload.get('origin_binding_id')
    current = wf.actual_hook_context(store, req['context'])
    main, _, affected = affected_editors(store, record, _point(current))
    item = next((item for item in affected.values() if item[1]['binding_id'] == origin_binding_id), None)
    require(item is not None, 'No affected current editorial input requires that occurrence')
    key = _editor_key(record, item)
    for mandate in req['rechecks'].values():
        if mandate['editorial_policy'] != key or mandate.get('retired'):
            continue
        if mandate['chain_id']:
            previous = wf.hook_helper().read(store, mandate['chain_id'])
            require(previous['state'] == 'complete', 'Resume or reconcile the original affected editorial recheck first')
            require(mandate['required_input'] != _point(current) or mandate['policy_digest'] != _policy_digest(record),
                    'This editorial recheck input already executed under the current policy; resolve the repeated wording hold')
        elif mandate['required_input'] == _point(current) and mandate['policy_digest'] == _policy_digest(record):
            return
        else:
            raise wf.WorkflowError('Reconcile the earlier affected editorial recheck before creating another mandate')
    row = next(row for row in req['configuration']['bindings'] if row['id'] == origin_binding_id)
    identifier = wf.identity('ER')
    request_id = req['request_id'] + ':editorial-recheck:' + identifier
    mandate = {'id': identifier, 'request_id': request_id, 'chain_id': None, 'sequence': len(req['rechecks']) + 1,
               'origin_chain_id': main['id'], 'origin_chain_hash': main['chain_hash'],
               'origin_attempt_id': item[2]['id'], 'origin_binding_id': origin_binding_id,
               'configuration_digest': req['configuration']['configuration_digest'], 'editorial_policy': key,
               'required_input': _point(current), 'effective_digest': hash_value(row['effective']),
               'policy_digest': _policy_digest(record), 'policy_epoch': record['decision_mode_epoch']}
    mandate['mandate_digest'] = _mandate_digest(mandate)
    mandate['event'] = {**req['event'], 'id': request_id}
    mandate['context'] = {**current, 'processing_recheck_id': identifier,
                          'processing_recheck_digest': mandate['mandate_digest']}
    req['rechecks'][identifier] = mandate


def _release_entry(body, marker):
    suffix = '\n\n' + marker + '\n\n'
    require(body.endswith(suffix) and body.count(marker) == 1,
            'The exact owned processing blocking marker changed')
    ready, count = re.subn(r'(?m)^status: Blocked pending answers$', 'status: Ready', body[:-len(suffix)] + '\n\n', count=1)
    require(count == 1, 'The exact owned blocked status changed')
    require(not re.search(r'\[Unresolved (?:-|—) blocks implementation\]', ready),
            'Unrelated unresolved questions still prevent Ready status')
    return ready


def completion(store, record):
    req = requirements(record)
    current = wf.actual_hook_context(store, req['context'])
    guard_current_scope(store, record, current)
    _require_task_sections(current['body'])
    required = sorted(key for key, question in record['questions'].items() if question['required'])
    _answers(store, record, required)
    _clarity(store, record)
    main, derived, affected = affected_editors(store, record, _point(current), require_complete=True)
    require(not affected, 'An affected editorial application must recheck the current task wording')
    frames = ([main] if main else []) + [chain for _, chain, _ in derived]
    for frame in frames:
        revision_path(record, _point(frame['context']), _point(current))
    return frames


def _verify_finalization(store, record, task=None):
    req = requirements(record)
    final = req.get('finalization')
    require(final and record['state'] == 'complete' and wf.clarification_acceptance_current(store, record)
            and final['policy_digest'] == _policy_digest(record)
            and final['confirmation_digest'] == hash_value(record['confirmation']),
            'The post-processing task has no current exact release')
    tid = record['task_ids'][0]
    hold = req['task_holds'][tid]
    require(_release_entry(final['before_body'], hold['marker']) == final['after_body']
            and final['before'] == _baseline_point(record)
            and wf.digest(final['before_body'].encode()) == final['before']['content_fingerprint']
            and wf.digest(final['after_body'].encode()) == final['after']['content_fingerprint'],
            'The mechanical release differs from the verified blocked and Ready bytes')
    if task is None:
        task = next((item for item in wf.parse(store.text()) if item['id'] == tid), None)
    if task:
        require(task['status'] == 'Ready' and task['body'] == final['after_body']
                and _fingerprints(task) == final['after']
                and wf.clarification_identity(task) == record['baselines'][tid]['identity'],
                'The released task changed and requires explicit processing clarification resume')
    else:
        completed = next((item for item in store.outcomes() if item['task_id'] == tid and item['disposition'] == 'completed'), None)
        require(completed and completed.get('task_context') == final['after'],
                'The released task lacks an exact successful completed context')
    return final


def readiness_context(store, record, frame, check_mandates=True):
    req = requirements(record)
    check_live(record, frame, frame['context'])
    _check_historical_policy(store, record, frame)
    if frame['context'].get('run_id'):
        run = wf._hook_controller(store, frame['context']['run_id'])
        require(set(record['task_ids']).issubset(run.get('admitted_task_ids', run.get('required_ids', []))),
                'The processing task exceeds the actual linked controller scope')
    if req.get('finalization'):
        final = _verify_finalization(store, record)
        require(final['chain_hashes'].get(frame['id']) == frame['chain_hash'],
                'The registered completed processing chain differs from the exact release')
        terminal = final['before']
    else:
        actual = wf.actual_hook_context(store, req['context'])
        terminal = _point(actual)
        require(terminal == _baseline_point(record), 'The held task lacks its exact guarded current wording')
    revision_path(record, _point(frame['context']), terminal)
    if check_mandates and frame['context'].get('processing_recheck_id'):
        recheck_guard(store, frame['context'], frame['event'], True)
    return deepcopy(frame['context'])


def admit(store, record, task):
    final = _verify_finalization(store, record, task)
    req = requirements(record)
    main, derived, affected = affected_editors(store, record, final['before'], require_complete=True)
    frames = ([main] if main else []) + [chain for _, chain, _ in derived]
    require(not affected and final['chain_hashes'] == {chain['id']: chain['chain_hash'] for chain in frames},
            'The exact released task lacks its required processing occurrence history')
    for frame in frames:
        revision_path(record, _point(frame['context']), final['before'])
    _answers(store, record, sorted(key for key, question in record['questions'].items() if question['required']))
    _clarity(store, record)


def finalize(store, record, frames):
    req = requirements(record)
    tid = record['task_ids'][0]
    text = store.text()
    task = wf.clarification_tasks(store, [tid], text)[0]
    entry = _release_entry(task['body'], req['task_holds'][tid]['marker'])
    updated = _replace_task(text, task, entry)
    released = wf.clarification_tasks(store, [tid], updated)[0]
    require(wf.clarification_identity(task) == wf.clarification_identity(released),
            'Mechanical release cannot change the selected task provenance')
    req['finalization'] = {'before': _fingerprints(task), 'after': _fingerprints(released),
                           'before_body': task['body'], 'after_body': released['body'],
                           'policy_digest': _policy_digest(record), 'confirmation_digest': hash_value(record['confirmation']),
                           'chain_hashes': {frame['id']: frame['chain_hash'] for frame in frames}}
    return updated


def session_for_task(store, task_id):
    found = []
    for path in (store.base / 'clarifications').glob('cl-*.json'):
        record = wf.clarification_read(store, 'CL-' + path.stem[3:])
        if record['mode'] == MODE and task_id in record['task_ids']:
            found.append(record)
    require(len(found) <= 1, 'Multiple post-processing sessions own the same task')
    return found[0] if found else None


def _package_path(store, package_root):
    package = Path(package_root).absolute()
    require(package.is_relative_to(store.source_root), 'Post-processing requires its owned installed package destination')
    return package.relative_to(store.source_root).as_posix()


def guard_package(store, record, package_root):
    require(_package_path(store, package_root) == requirements(record)['package_path'],
            'Post-processing requires its original owned installed package destination')
    package_location(store, {'package_root': str(package_root)})


def guard_current_scope(store, record, context):
    require(_point(context) == _baseline_point(record),
            'The post-processing task changed outside its guarded clarification; explicitly resume it')
    wf._hook_scope_source_guard(store, requirements(record).get('adopted_scope_sources', {}))


def scope_guard(store, context, package_root):
    for task_id in context.get('task_ids', []):
        record = session_for_task(store, task_id)
        if record is None:
            continue
        require(context.get('session_id') == record['id'],
                'Use the exact registered post-processing clarification scope')
        guard_package(store, record, package_root)
        spec = _spec(record, context)
        require(context == wf.actual_hook_context(store, spec['context']),
                'Post-processing requires the exact current owned task context')
        guard_current_scope(store, record, context)


def pending_guard(store, record):
    wf.hook_pending_admission(store, scope=record['task_ids'][0])


def _task_sections(body):
    result = {}
    name = None
    fenced = False
    for line in body.splitlines(keepends=True):
        if line.startswith('```'):
            fenced = not fenced
        heading = None if fenced else re.fullmatch(r'([A-Z][A-Za-z /-]+):\s*\n?', line)
        if heading:
            name = heading[1]
            result.setdefault(name, [])
        elif name:
            result[name].append(line)
    return {key: wf.clarification_text_semantics(''.join(value)) for key, value in result.items()}


def _require_task_sections(body):
    sections = _task_sections(body)
    require(all(sections.get(name, '').strip(' -*\n') for name in wf.SECTIONS),
            'Processing requires nonempty real Goal, Touch, Validation and Acceptance sections')
    return sections


def _protect_revision(before, after, record, editorial=False):
    marker = requirements(record)['task_holds'][before['id']]['marker']
    require(before['depends_on'] == after['depends_on'] and before['status'] == after['status']
            and after['body'].count(marker) == 1 and after['body'].endswith('\n\n' + marker + '\n\n'),
            'Processing revisions preserve dependencies and the exact owned hold')
    previous, current = _task_sections(before['body']), _require_task_sections(after['body'])
    protected = {'Constraints', 'Implementation constraints', 'Out of scope', 'Exclusions', 'Required plugin policy'}
    if editorial:
        protected.add('Validation')
    require(all(previous.get(name) == current.get(name) for name in protected),
            'Processing revisions preserve the selected task constraints and exclusions')


def guard_revision(store, record, before, after):
    pending_guard(store, record)
    req = requirements(record)
    chain_ids = [req['chain_id']] + [mandate['chain_id'] for mandate in req['rechecks'].values() if not mandate.get('retired')]
    editorial = False
    for chain_id in filter(None, chain_ids):
        chain = wf.hook_helper().read(store, chain_id)
        attempt = chain['attempts'].get(chain.get('prepared_attempt_id'))
        policy = (attempt or {}).get('input', {}).get('processing_application') or {}
        if attempt and attempt['status'] == 'returned' and policy.get('role') == 'task-editorial':
            editorial = True
            break
    _protect_revision(before, after, record, editorial)


def recover_held_revision(store, record, task, baselines):
    _require_task_sections(task['body'])
    before = _baseline_point(record)
    tid = task['id']
    after = _fingerprints(task)
    if before == after:
        return
    pending_guard(store, record)
    marker = requirements(record)['task_holds'][tid]['marker']
    require(task['status'] == BLOCKED and task['body'].count(marker) == 1
            and task['body'].endswith('\n\n' + marker + '\n\n')
            and baselines[tid]['fields']['dependencies'] == record['baselines'][tid]['fields']['dependencies'],
            'Restore the exact owned processing hold and dependencies before clarification recovery')
    source_before = record['source_hash']
    changed = wf.clarification_invalidate(record, baselines)
    record['task_revisions'].append({'id': wf.identity('TR'), 'task_ids': [tid],
                                     'task_fingerprints': {tid: {'before': before, 'after': after}},
                                     'content_changed_task_ids': [tid],
                                     'changed_fields': {tid: sorted(changed[tid])},
                                     'source_before': source_before, 'source_after': wf.file_hash(store.future),
                                     'recorded_at': wf.now(), 'kind': 'explicit-processing-recovery'})


def reopen(store, record, task, allow_drift=False):
    req = requirements(record)
    final = req.get('finalization')
    if not final:
        return None
    require(task['status'] == 'Ready' and (allow_drift or task['body'] == final['after_body']),
            'The released task changed; explicitly resume clarification before another mutation')
    _require_task_sections(task['body'])
    neutral = wf.Store(store.root, allow_unselected=True, neutral=True)
    require(task['id'] not in neutral.load().get('task_progress', {}),
            'Reconcile existing implementation progress before reopening a released task')
    return _reopen_held(store, record, task, store.text(), 'explicit-processing-reopen')


def _reopen_held(store, record, task, text, kind, detail=None):
    req = requirements(record)
    marker = req['task_holds'][task['id']]['marker']
    text = _block(text, task, marker)
    held = wf.resolve(wf.parse(text), [task['id']], 'Prioritized Next Changes')[0]
    previous = _baseline_point(record)
    baselines = wf.clarification_baselines([held])
    changed = wf.clarification_invalidate(record, baselines)
    current = _baseline_point(record)
    if previous != current:
        record['task_revisions'].append({'id': wf.identity('TR'), 'task_ids': [task['id']],
                                         'task_fingerprints': {task['id']: {'before': previous, 'after': current}},
                                         'content_changed_task_ids': [task['id']], 'changed_fields': {key: sorted(value) for key, value in changed.items()},
                                         'source_before': wf.file_hash(store.future), 'source_after': wf.digest(text.encode()),
                                         'recorded_at': wf.now(), 'kind': kind, **(detail or {})})
    req.setdefault('finalization_history', []).append(req['finalization'])
    req['finalization'] = None
    record.update(state='researching', next_action='Recheck the affected post-processing requirements before release')
    return text


def policy_switched(store, record):
    req = requirements(record)
    for mandate in req['rechecks'].values():
        chain_id = mandate.get('chain_id')
        chain = wf.hook_helper().read(store, chain_id) if chain_id else None
        if chain and chain['state'] == 'complete' or mandate.get('retired'):
            continue
        mandate['retired'] = 'explicit-owner-mode-switch'
        if chain:
            _retire(req, chain, 'explicit-owner-mode-switch')


def _retire(req, chain, reason):
    req['retired_chains'].append({'id': chain['id'], 'chain_hash': chain['chain_hash'], 'reason': reason})


def retired_chain(store, frame):
    record = linked(store, frame['context'])
    if record is None:
        return False
    value = next((row for row in requirements(record)['retired_chains'] if row['id'] == frame['id']), None)
    if value is None:
        return False
    require(value['chain_hash'] == frame['chain_hash'] and not any(
        attempt['status'] in wf.hook_helper().PENDING for attempt in frame['attempts'].values()),
        'A retired processing chain changed or retains an unresolved original attempt')
    return True


def _metadata(store, record, payload):
    req = requirements(record)
    package, observed, manifest = package_location(store, payload)
    require(package and manifest, 'The current owned Processing package is unavailable')
    watch = wf._hook_watch(package, store.source_root)
    source_hash = wf.file_hash(store.future)
    if req.get('finalization'):
        task = wf.clarification_tasks(store, record['task_ids'])[0]
        _verify_finalization(store, record, task)
        text = _block(store.text(), task, req['task_holds'][task['id']]['marker'])
        held = wf.clarification_tasks(store, record['task_ids'], text)[0]
        context = {**req['context'], **_context(held, record['id']), 'parent_mode_epoch': record['decision_mode_epoch']}
    elif record['state'] == 'cancelled':
        task = wf.clarification_tasks(store, record['task_ids'])[0]
        context = {**req['context'], **_context(task, record['id']), 'parent_mode_epoch': record['decision_mode_epoch']}
    else:
        context = wf.actual_hook_context(store, req['context'])
    request = _request(store, {'capabilities': req['capabilities'], 'adapter': req['adapter'],
                              'run_overrides': req['configuration'].get('run_overrides', {}),
                              'execution_policy': req['configuration'].get('execution_policy'), **payload}, req['event'], context)
    metadata = wf._hook_node(package, request)
    configuration, proof = metadata['configuration'], metadata['proof']
    require(proof.get('proof_kind') == 'completed-readiness' and proof['context'] == context,
            'The new Processing configuration requires actual owned metadata preparation')
    store.guard(source_hash)
    wf._hook_watch_guard(watch, package)
    return {'package': package, 'watch': watch, 'observed': observed, 'source_hash': source_hash,
            'session_hash': record['session_hash'], 'configuration': configuration, 'proof': proof,
            'capabilities': request['capabilities'], 'adapter': request['adapter']}


def _accepted_sources(frames):
    return {frame['id']: {stage['attempt_ids'][-1]: frame['attempts'][stage['attempt_ids'][-1]]['input']['scope_source_snapshot']
                          for stage in frame['stages'] if stage['status'] == 'complete'}
            for frame in frames}


def _registered_frames(store, req):
    chain_ids = [req['chain_id']] + [mandate['chain_id'] for mandate in req['rechecks'].values() if not mandate.get('retired')]
    return [wf.hook_helper().read(store, chain_id) for chain_id in filter(None, chain_ids)]


def _guard_accepted_sources(store, frames):
    for chain_id, attempts in _accepted_sources(frames).items():
        location = wf._hook_locator(store, chain_id)
        source = wf._hook_source_store(store, location['execution_root'])
        for snapshot in attempts.values():
            wf._hook_scope_source_guard(source, snapshot)


def prepare_adoption(store, record, payload):
    req = requirements(record)
    prepared = _metadata(store, record, payload)
    proof = prepared['proof']
    configuration = prepared['configuration']
    before = req['configuration']['configuration_digest']
    after = configuration['configuration_digest']
    accepted_sources = _accepted_sources(_registered_frames(store, req))
    old_sources = [req.get('adopted_scope_sources', {})] + [snapshot for attempts in accepted_sources.values() for snapshot in attempts.values()]
    sources = {path: wf._hook_scope_source_hash(store, path) for path in sorted({path for snapshot in old_sources for path in snapshot})}
    changed_sources = any(sources[path] != value for snapshot in old_sources for path, value in snapshot.items())
    require(configuration != req['configuration'] or proof['execution_snapshot'] != req['execution_snapshot']
            or _package_path(store, prepared['package']) != req['package_path'] or changed_sources,
            'The current Processing configuration and execution source already match the hold')
    context = deepcopy(proof['context'])
    context['clarification_session_id'] = context.pop('session_id')
    context.pop('body', None)
    context.update(purpose='processing-configuration-adoption', before_configuration_digest=before,
                   after_configuration_digest=after, before_execution_digest=hash_value(req['execution_snapshot']),
                   after_execution_digest=hash_value(proof['execution_snapshot']),
                   before_scope_source_digest=hash_value({'accepted': accepted_sources, 'adopted': old_sources[0]}),
                   after_scope_source_digest=hash_value(sources))
    prepared.update(decision_context=context, scope_sources=sources, accepted_scope_sources=accepted_sources)
    return prepared


def guard_metadata(store, record, prepared):
    require(prepared and record['session_hash'] == prepared['session_hash'],
            'The post-processing session changed after outside-writer preparation')
    store.guard(prepared['source_hash'])
    wf._hook_watch_guard(prepared['watch'], prepared['package'])
    wf._hook_scope_source_guard(store, prepared.get('scope_sources', {}))
    for path, expected in prepared['observed'].items():
        require(wf.file_hash(Path(path)) == expected, 'The prepared post-processing configuration changed')


def adopt(store, record, payload, prepared):
    guard_metadata(store, record, prepared)
    pending_guard(store, record)
    req = requirements(record)
    require(_accepted_sources(_registered_frames(store, req)) == prepared['accepted_scope_sources'],
            'The original accepted processing source scope changed after adoption preparation')
    proof, configuration = prepared['proof'], prepared['configuration']
    authority = record.get('decision_authority')
    require(authority is not None, 'Configuration adoption requires an actual current scoped authority')
    receipt = wf.decision_helper().acceptance_reference(store, payload.get('decision_receipt'), {
        'context': prepared['decision_context'], 'mode': record['decision_mode'], 'kind': 'technical',
        'authority_digest': wf.decision_helper()._hash(authority)})
    require(receipt['answer'] == 'adopt', 'The current core decision did not adopt this Processing configuration')
    retired = ([req['chain_id']] if req['chain_id'] else []) + [m['chain_id'] for m in req['rechecks'].values() if m['chain_id'] and not m.get('retired')]
    for chain_id in retired:
        _retire(req, wf.hook_helper().read(store, chain_id), 'explicit-configuration-adoption')
    req['adoptions'].append({'decision_receipt': deepcopy(payload['decision_receipt']), 'acceptance': receipt,
                             'previous_configuration': req['configuration'], 'previous_execution_snapshot': req['execution_snapshot'],
                             'previous_package_path': req['package_path'],
                             'previous_chain_id': req['chain_id'], 'previous_rechecks': req['rechecks']})
    selected = _selected(configuration, proof)
    req['adoptions'][-1].update(previous_accepted_scope_sources=prepared['accepted_scope_sources'],
                                previous_adopted_scope_sources=req.get('adopted_scope_sources', {}),
                                adopted_scope_sources=prepared['scope_sources'])
    request_id = 'post-processing:' + record['id'] + ':adoption:' + str(len(req['adoptions']))
    req.update(configuration=configuration, execution_snapshot=proof['execution_snapshot'], context=proof['context'],
               package_path=_package_path(store, prepared['package']),
               adopted_scope_sources=prepared['scope_sources'],
               event={**proof['event'], 'id': request_id}, request_id=request_id, chain_id=None,
               required_bindings=list(selected), applications=selected, rechecks={},
               capabilities=prepared['capabilities'], adapter=prepared['adapter'], prerequisites=proof['prerequisites'])
    if record.get('confirmation'):
        record.setdefault('confirmation_history', []).append(record['confirmation'])
    record.update(state='researching', confirmation=None, clarity=None, no_progress_rounds=0,
                  next_action='Recheck the adopted post-processing obligations and obtain current acceptance')


def prepare_release(store, record):
    frames = completion(store, record)
    if frames:
        _guard_accepted_sources(store, frames)
        tid = record['task_ids'][0]
        wf.prepare_hook_admission(store, scope=tid, chain_ids=[frame['id'] for frame in frames])
        return {'frames': {frame['id']: frame['chain_hash'] for frame in frames}, 'metadata': None}
    metadata = _metadata(store, record, {})
    req = requirements(record)
    guard_package(store, record, metadata['package'])
    require(metadata['configuration'] == req['configuration'] and metadata['proof']['execution_snapshot'] == req['execution_snapshot']
            and not _selected(metadata['configuration'], metadata['proof']),
            'The explicit empty adoption no longer matches the current Processing configuration')
    return {'frames': {}, 'metadata': metadata}


def guard_release(store, record, prepared, *, register=True):
    frames = completion(store, record)
    require(prepared and prepared['frames'] == {frame['id']: frame['chain_hash'] for frame in frames},
            'The completed Processing chains changed before release')
    if frames:
        _guard_accepted_sources(store, frames)
        wf._hook_admission(store, record['task_ids'][0], list(prepared['frames']), register=register)
    else:
        guard_metadata(store, record, prepared['metadata'])
    return frames
