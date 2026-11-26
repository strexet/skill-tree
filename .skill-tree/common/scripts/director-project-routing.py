"""Preview the exact workspace route before any product effects."""
from pathlib import Path
import re
import subprocess


TASK_ROUTES = {
    'intake': (None, 'intake'),
    'process': ('Pending Queue', 'process'),
    'implement-next': ('Prioritized Next Changes', 'launch'),
    'implement-all': ('Prioritized Next Changes', 'launch'),
}
CORE_TASK_ROUTES = {
    'skill-tree-add-pending-task': 'intake',
    'skill-tree-process-future-pending': 'process',
    'skill-tree-implement-next-future-task': 'implement-next',
    'skill-tree-work-through-next': 'implement-next',
    'skill-tree-implement-all': 'implement-all',
}
DIRECTOR_ROUTES = {
    'skill-tree-director-audit': ('workspace-audit', 'audit'),
    'skill-tree-director-decide': ('run-status', None),
    'skill-tree-director-install': ('preview', None),
    'skill-tree-director-intake': ('objective-preview', 'intake'),
    'skill-tree-director-plan': ('plan-preview', 'preview'),
    'skill-tree-director-review': ('review-preview', 'review'),
    'skill-tree-director-run': ('run-status', 'launch'),
    'skill-tree-director-setup': ('project-menu', None),
    'skill-tree-director-status': ('status', 'status'),
}
ALIASES = {
    'status': 'skill-tree-director-status',
    'workspace-status': 'skill-tree-director-status',
    'audit': 'skill-tree-director-audit',
    'diagnose': 'skill-tree-director-audit',
    'setup': 'skill-tree-director-setup',
    'registration': 'skill-tree-director-setup',
    'objective': 'skill-tree-director-intake',
    'plan': 'skill-tree-director-plan',
    'review': 'skill-tree-director-review',
    'run': 'skill-tree-director-run',
    'questions': 'skill-tree-director-decide',
    'installation': 'skill-tree-director-install',
}

REQUEST_ROUTES = {
    'fresh-implementation': ('skill-tree-full-cycle', ('intake', 'process', 'launch')),
    'existing-task': ('skill-tree-work-through-next', ('launch',)),
    'pending-intake': ('skill-tree-add-pending-task', ('intake',)),
    'pr-review': ('skill-tree-pr-review-cycle', ('review',)),
}
IMPLEMENT_REQUEST = re.compile(r'^(?:implement|fix|build|full cycle|реализу(?:й|ем|йте)|реализовать|'
                               r'исправ(?:ь|им|ьте|ить)|полный цикл)\b')
INTAKE_REQUEST = re.compile(r'^(?:add (?:to |a )?pending|capture (?:as )?pending|record (?:a )?pending|'
                            r'добав(?:ь|им|ьте|ить)\b[^.!?\n]{0,40}\b(?:pending|отложенн\w*)|'
                            r'только (?:в )?pending)\b')
PR_REVIEW_REQUEST = re.compile(r'^(?:review (?:the |this |an? )?(?:pr|pull request)|pr review|'
                               r'(?:проведи )?ревью (?:этот )?(?:pr|pull request|пул-реквест)|'
                               r'(?:проверь|проверьте|проверить) (?:этот )?(?:pr|pull request|пул-реквест))\b')
DEFERRED_IMPLEMENTATION = re.compile(r"(?:\b(?:without|no) implementation\b|"
                                    r"\b(?:do not|don't) implement\b|\bне реализовывай\b|\bбез реализации\b)")
UNCERTAIN_REQUEST = re.compile(r"\b(?:maybe|perhaps|should we|do not|don't|never|instead of|"
                               r"возможно|может быть|не|вместо|если)\b")
ADDITIONAL_EFFECT = re.compile(r'^(?:process|merge|publish|push|deploy|release|обработ(?:ай|аем|айте|ать)|мерж|'
                               r'влей|влить|опубликуй|опубликовать|запушить|задеплоить|релиз)\b')
UNSUPPORTED_IMPLEMENT = re.compile(r'^(?:implement (?:all|every)|start implementation|реализу(?:й|ем|йте) все|начн(?:и|ите) реализацию)\b')
POLITE_QUESTION = re.compile(r'^(?:can you|could you|можешь|можете)\b')
REQUEST_PREFIX = re.compile(r"^(?:(?:please|can you|could you|можешь|можете|let's|давай(?:те)?|пожалуйста)[, ]+)+")
REQUEST_SEPARATORS = re.compile(r'[,.!?;\n]\s*|\b(?:and(?: then)?|then|also|и(?: затем)?|затем|а также)\s+')
EXISTING_TASK = re.compile(r'^(?:(?:(?:the |an? |this |that )?(?:(?:existing|ready|prioritized|pending) )?task|next)\b|'
                           r'(?:эту |готовую |существующую )?задачу\b)')
TASK_REFERENCE = re.compile(r'(?<![\w-])[PT]-[\w-]+', re.IGNORECASE)


def package_entry(D, root, settings, profile, skill):
    host = settings['providers'][0]
    matches = [(relative, record) for relative, record in profile['destinations'].items()
               if record['name'] == skill and host in record.get('providers', [record.get('provider')])]
    D._require(len(matches) == 1, 'The selected Director operation is missing from the registered host')
    relative, record = matches[0]
    script = 'scripts/director-entry.py'
    target = D._safe_path(root, relative + '/' + script)
    expected = record['files'].get(script)
    D._require(D._sha(expected) and D.WF.file_hash(target) == expected,
               'The selected Director entry differs from the installed receipt')
    return str(target)


def installed_operations(D, root):
    cfg, _ = D._read(root, '.skill-tree/installation/source/config/flavors.json')
    D._require(isinstance(cfg, dict), 'The Director installation operation catalog is unavailable')
    return cfg['core_operations'], cfg['flavors']['director']['operations']


def child_skill(D, project, name):
    checkout = Path(project.get('workspace_checkout', project['checkout']))
    try:
        owned = D._inspect_profile(checkout)
        profile, digest = D._read(checkout, '.skill-tree/installation/profile.json')
        if owned['kind'] != 'owned-profile' or digest != owned['sha256']:
            return None
        matches = [(relative, record) for relative, record in profile['destinations'].items() if record['name'] == name]
        for relative, record in sorted(matches):
            file = D._safe_path(checkout, relative + '/SKILL.md')
            if file.is_file() and D.WF.file_hash(file) == record['files'].get('SKILL.md'):
                return str(file)
    except (ValueError, OSError, subprocess.TimeoutExpired):
        return None
    return None


def project_for(D, workspace, products, selected, mode='director'):
    colocated = [item for item in products if workspace == Path(item.get('workspace_checkout', item.get('checkout') or '.'))]
    local_receipt = D._safe_path(workspace, '.skill-tree/installation/profile.json')
    if mode == 'direct' and selected is None and not colocated and local_receipt.is_file():
        profile = D._inspect_profile(workspace)
        D._require(profile['kind'] == 'owned-profile' and profile['flavor'] != 'director',
                   'Select an exact installed Core project for direct routing')
        locator = D.WS.runtime_file(workspace)
        checkout, queue_id = str(workspace), None
        if locator is not None and (locator.exists() or locator.is_symlink()):
            queue_id, _, owner = D._inspect_owner(workspace)
            checkout = owner['root']
        else:
            state, _ = D._read(workspace, '.skill-tree/documents/future.json')
            D._require(not isinstance(state, dict) or state.get('schema') != 3,
                       'Restore the canonical Core queue locator before selecting direct routing')
        return {'id':None, 'role':profile['flavor'], 'queue_id':queue_id, 'checkout':checkout,
                'workspace_checkout':str(workspace), 'allowed_effects':[], 'state':'available', 'registered':False}
    if selected is not None:
        candidates = [item for item in products if item['id'] == selected]
    else:
        candidates = colocated or products
    D._require(len(candidates) == 1 and candidates[0]['state'] == 'available',
               'Select an exact available project from project-menu')
    return candidates[0]


def inventory(core, director):
    return ([{'operation': name, 'route': 'director-assignment' if name in CORE_TASK_ROUTES else 'project-skill'}
             for name in core]
            + [{'operation': name, 'route': 'director'} for name in director])


def task_preview(D, summary, request, operation, mode):
    project = summary['project']
    queue, required_effect = TASK_ROUTES[operation]
    summary['queue'] = queue or 'Pending Queue'
    if mode == 'director' and 'preview' not in project['allowed_effects']:
        return {**summary, 'status':'prerequisite', 'task_ids':[], 'limitations':['project-preview-not-authorized']}
    store = D.WF.Store(Path(project['checkout']), route_queue=False, neutral=True)
    text = store.text()
    all_tasks = D.WF.parse(text)
    tasks = [task for task in all_tasks if task['queue'] == queue]
    requested = request.get('task_ids')
    if requested is not None:
        D._require(queue is not None and isinstance(requested, list) and requested
                   and all(isinstance(item, str) for item in requested) and len(set(requested)) == len(requested),
                   'Select distinct exact task identities for this operation')
        D._require(set(requested) <= {task['id'] for task in tasks}, 'A selected task is outside the receiving queue')
        if operation == 'process' and mode == 'director':
            by_id = {task['id']: task for task in tasks}
            tasks = [by_id[task_id] for task_id in requested]
        else:
            tasks = [task for task in tasks if task['id'] in requested]
    if operation == 'implement-next':
        D._require(requested is None or len(requested) == 1, 'Implement Next selects one exact task')
        tasks = sorted(tasks, key=lambda task: -task['priority'])[:1]
    if operation.startswith('implement-'):
        tasks = sorted(tasks, key=lambda task: -task['priority'])
    limitations = []
    if project.get('core_routing') == 'upgrade-project-installation':
        limitations.append('upgrade-co-located-project-installation-through-project-setup')
    if mode == 'director':
        if required_effect not in project['allowed_effects']:
            limitations.append(f'director-{required_effect}-not-authorized')
        if operation == 'implement-all':
            limitations.append('director-managed-implement-all-requires-frozen-assignments')
        elif operation == 'process' and len(tasks) > 1:
            limitations.append('director-batch-processing-requires-frozen-intake-receipt')
        elif operation != 'intake':
            limitations.append('director-dispatch-requires-one-exact-task-per-assignment')
    task_ids = [task['id'] for task in tasks]
    required = D.WF.dependency_scope(all_tasks, {'snapshot':task_ids}) if operation.startswith('implement-') else set()
    fields = ['id', 'title', 'status', 'priority', 'depends_on']
    if operation == 'process':
        fields.extend(['topic', 'intake_batch_ids', 'pending_depends_on'])
    return {**summary, 'status':'preview', 'queue_sha256':D.WF.digest(text.encode()),
            'task_ids':task_ids, 'required_dependency_ids':sorted(required - set(task_ids)),
            'tasks':[{key: task[key] for key in fields if key in task} for task in tasks],
            'limitations':limitations}


def recommendation_choices(core, intents=()):
    return [{'intent': intent, 'operation': operation}
            for intent, (operation, _) in REQUEST_ROUTES.items()
            if operation in core and (not intents or intent in intents)]


def request_intents(text, ids):
    original = text.casefold().strip()
    normalized = REQUEST_PREFIX.sub('', original)
    if INTAKE_REQUEST.match(normalized):
        normalized = DEFERRED_IMPLEMENTATION.sub('', normalized)
    clauses = [REQUEST_PREFIX.sub('', clause.strip()) for clause in REQUEST_SEPARATORS.split(normalized)
               if clause.strip()]
    intents = []
    first_recognized = False
    additional = False
    for index, clause in enumerate(clauses):
        unsupported = UNSUPPORTED_IMPLEMENT.match(clause)
        implement = None if unsupported else IMPLEMENT_REQUEST.match(clause)
        intent = None
        if implement:
            selects_task = EXISTING_TASK.match(clause[implement.end():].lstrip())
            intent = 'existing-task' if ids or selects_task else 'fresh-implementation'
        elif INTAKE_REQUEST.match(clause):
            intent = 'pending-intake'
        elif PR_REVIEW_REQUEST.match(clause):
            intent = 'pr-review'
        additional = additional or bool(unsupported or ADDITIONAL_EFFECT.match(clause))
        if intent:
            first_recognized = first_recognized or index == 0
            intents.append(intent)
    uncertain = ((normalized.endswith('?') and not POLITE_QUESTION.match(original))
                 or bool(UNCERTAIN_REQUEST.search(normalized))
                 or (bool(intents) and not first_recognized))
    return list(dict.fromkeys(intents)), uncertain, additional or len(intents) > 1

def request_queue_prerequisite(D, project, task_ids, intent):
    """Check exact task identity and passive Core admission inputs."""
    try:
        store = D.WF.Store(Path(project['checkout']), route_queue=False, neutral=True)
        text = store.text()
        tasks = D.WF.parse(text)
        by_id = {task['id']: task for task in tasks}
        if any(task_id not in by_id for task_id in task_ids):
            return 'task-outside-project-queue', {}
        if intent != 'existing-task':
            return None, {}
        task_id = task_ids[0]
        task = by_id[task_id]
        if task['queue'] != 'Prioritized Next Changes':
            return 'prioritized-task-required', {'task_status': task['status']}
        state = store.load(text)
        registry = state['run_registry']
        D._require(registry['queue_id'] == project['queue_id'], 'Project queue changed during route preview')
        completed = {outcome['task_id']: outcome for outcome in store.outcomes()
                     if outcome['disposition'] == 'completed'}
        required = D.WF.dependency_scope(tasks, {'snapshot': task_ids}) - completed.keys()
        claims = registry['claims']
        for required_id in sorted(required):
            entry = by_id.get(required_id)
            if entry is None or entry['queue'] != 'Prioritized Next Changes':
                return 'required-task-unavailable', {'required_task_id': required_id}
            if entry['status'] != 'Ready':
                return 'task-clarification-required', {'required_task_id': required_id, 'task_status': entry['status']}
            if required_id in claims:
                return 'task-claimed', {'required_task_id': required_id, 'run_id': claims[required_id]}
            try:
                D.WF.clarification_admission(store, required_id, hook_gate=False)
            except ValueError:
                return 'task-clarification-required', {'required_task_id': required_id}
        return None, {'task_status': task['status'], 'queue_sha256': D.WF.digest(text.encode())}
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired):
        return 'project-queue-unavailable', {}


def recommend_request(D, workspace, products, core, request):
    D._object(request, {'request_text'}, {'project_id'})
    text = request['request_text']
    D._require(isinstance(text, str) and 0 < len(text) <= 4000 and text.strip(),
               'A route recommendation requires nonempty request text up to 4000 characters')
    selected = request.get('project_id')
    D._require(selected is None or D._token(selected), 'Select an exact project ID from project-menu')
    ids = list(dict.fromkeys(TASK_REFERENCE.findall(text)))
    intents, uncertain, additional = request_intents(text, ids)
    summary = {'route': 'director', 'execution': 'route-recommendation', 'status': 'preview',
               'matched_intents': intents, 'confidence': 'unresolved', 'candidate_operation': None,
               'unresolved_choices': [], 'limitations': []}

    def prerequisite(code, **details):
        return {**summary, **details, 'status': 'prerequisite', 'limitations': [code]}

    if selected is None or not any(project['id'] == selected for project in products):
        return prerequisite('exact-registered-project-required',
                            unresolved_choices=[{'project_id': project['id']} for project in products
                                                if project['state'] == 'available'])
    try:
        project = project_for(D, workspace, products, selected)
    except ValueError:
        return prerequisite('registered-project-unavailable', project_id=selected)
    summary['project'] = project
    if 'preview' not in project['allowed_effects']:
        return prerequisite('project-preview-not-authorized')
    if len(intents) != 1 or uncertain or additional:
        reason = ('mixed-request-intent' if len(intents) > 1 or (additional and intents)
                  else 'uncertain-request-intent' if uncertain else 'unsupported-request-intent')
        return {**summary, 'limitations': [reason], 'unresolved_choices': recommendation_choices(core, intents)}

    intent = intents[0]
    operation, effects = REQUEST_ROUTES[intent]
    summary.update(candidate_operation=operation, confidence='bounded-explicit-wording')
    if operation not in core:
        return prerequisite('operation-is-outside-installed-catalog')
    if denied := [effect for effect in effects if effect not in project['allowed_effects']]:
        return prerequisite('project-operation-effects-unavailable', required_effects=denied)
    if project.get('core_routing') == 'upgrade-project-installation':
        return prerequisite('upgrade-co-located-project-installation-through-project-setup')
    if not child_skill(D, project, operation):
        diagnostic = D._profile_refresh_prerequisite(Path(project.get('workspace_checkout', project['checkout'])))
        if diagnostic:
            # A recommendation reports the prerequisite without returning an executor command.
            profile = {key: diagnostic[key] for key in ('code', 'changed_inputs', 'profile_sha256')
                       if key in diagnostic}
            return prerequisite(diagnostic['code'], profile_prerequisite=profile)
        return prerequisite('project-skill-unavailable')
    if any(not (D.WF.valid_id(task_id, 'T') or D.WF.valid_id(task_id, 'P')) for task_id in ids):
        return prerequisite('exact-task-id-required', unresolved_choices=[{'queue': 'Prioritized Next Changes'}])
    if len(ids) > 1 or (intent == 'existing-task' and not ids):
        return prerequisite('select-one-exact-task',
                            unresolved_choices=[{'queue': 'Prioritized Next Changes'}])
    if ids:
        summary['task_ids'] = ids
        code, details = request_queue_prerequisite(D, project, ids, intent)
        if code:
            return prerequisite(code, **details)
        summary.update(details)
    return summary


def preview(D, root, workspace, settings, profile, products, request):
    if isinstance(request, dict) and 'request_text' in request:
        core, _ = installed_operations(D, root)
        return recommend_request(D, workspace, products, core, request)
    D._object(request, {'operation'}, {'project_id', 'route', 'task_ids'})
    operation, mode = request['operation'], request.get('route', 'director')
    D._require(isinstance(operation, str) and mode in ('director', 'direct'), 'Select a known operation and route')
    core, director = installed_operations(D, root)
    chosen = request.get('project_id')
    op = CORE_TASK_ROUTES.get(operation, operation)
    summary = {'route':mode, 'operation':operation}
    if op in TASK_ROUTES:
        project = project_for(D, workspace, products, chosen, mode)
        summary.update(project=project, execution='director-assignment' if mode == 'director' else 'direct-project')
        if mode == 'director':
            skill = 'skill-tree-director-intake' if op == 'intake' else 'skill-tree-director-run'
            summary['entry'] = package_entry(D, root, settings, profile, skill)
            summary['command'] = {'intake': 'objective-preview', 'implement-all': 'run-start'}.get(op, 'run-dispatch')
            if op == 'implement-all':
                summary['advance_command'] = 'run-advance-all'
        return task_preview(D, summary, request, op, mode)
    D._require('task_ids' not in request, 'Task identity selections belong to an exact queue operation')

    skill = ALIASES.get(operation, operation)
    if operation == 'discovery':
        return {**summary, 'status':'preview', 'execution':'workspace-discovery', 'projects':products,
                'operations':inventory(core, director)}
    if skill in director:
        if skill not in DIRECTOR_ROUTES:
            return {**summary, 'status':'unsupported', 'limitations':['director-operation-has-no-workspace-route']}
        D._require(mode == 'director', 'Select a Core project operation for direct routing')
        command, effect = DIRECTOR_ROUTES[skill]
        if operation == 'diagnose':
            command = 'diagnose'
        elif operation == 'registration':
            command = 'project-preview'
        summary.update(execution='director', entry=package_entry(D, root, settings, profile, skill), command=command)
        if operation == 'workspace-status':
            D._require(chosen is None, 'Use status to select an exact project')
        workspace_scope = (command in {'workspace-audit', 'project-menu', 'project-preview'} or
                           operation == 'workspace-status') and chosen is None
        if workspace_scope:
            selectors = {'area_ids':[item['id'] for item in products if 'status' in item['allowed_effects']]} if command == 'status' else {}
            return {**summary, 'status':'preview', 'projects':products, 'input':selectors, 'limitations':[]}
        project = project_for(D, workspace, products, chosen)
        denied = effect is not None and effect not in project['allowed_effects']
        if denied:
            return {**summary, 'project':project, 'status':'prerequisite',
                    'limitations':[f'director-{effect}-not-authorized']}
        if command == 'status':
            summary['input'] = {'area_ids':[project['id']], 'project_work':{'area_id':project['id']}}
        elif command == 'workspace-audit':
            summary['input'] = {'project_ids':[project['id']]}
        return {**summary, 'project':project, 'status':'preview', 'limitations':[]}

    if operation not in core and operation != 'project-read':
        return {**summary, 'status':'unsupported', 'limitations':['operation-is-outside-installed-catalog']}
    project = project_for(D, workspace, products, chosen, mode)
    summary.update(project=project)
    if operation == 'project-read':
        permitted = 'preview' in project['allowed_effects'] or 'status' in project['allowed_effects']
        return {**summary, 'execution':'project-read', 'status':'preview' if permitted else 'prerequisite',
                'limitations':[] if permitted else ['project-read-not-authorized']}
    if mode == 'director' and 'preview' not in project['allowed_effects']:
        return {**summary, 'execution':'project-skill', 'status':'prerequisite', 'child_skill':None,
                'limitations':['project-preview-not-authorized']}
    package = child_skill(D, project, operation)
    execution = 'direct-project' if mode == 'direct' else 'project-skill'
    if package:
        limitations = [] if mode == 'direct' else ['requires-exact-child-scope-and-effect-authorization']
        return {**summary, 'execution': execution, 'status': 'preview', 'child_skill': package,
                'limitations': limitations}
    checkout = Path(project.get('workspace_checkout', project['checkout']))
    prerequisite = D._profile_refresh_prerequisite(checkout)
    if prerequisite:
        return {**summary, 'execution': execution, 'status': 'prerequisite', 'child_skill': None,
                'limitations': [prerequisite['code']], 'profile_prerequisite': prerequisite}
    return {**summary, 'execution': execution, 'status': 'prerequisite', 'child_skill': None,
            'limitations': ['project-skill-unavailable']}
