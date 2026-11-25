"""Preview the exact workspace route before any product effects."""
from pathlib import Path
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
        elif operation != 'intake':
            limitations.append('director-dispatch-requires-one-exact-task-per-assignment')
    task_ids = [task['id'] for task in tasks]
    required = D.WF.dependency_scope(all_tasks, {'snapshot':task_ids}) if operation.startswith('implement-') else set()
    return {**summary, 'status':'preview', 'queue_sha256':D.WF.digest(text.encode()),
            'task_ids':task_ids, 'required_dependency_ids':sorted(required - set(task_ids)),
            'tasks':[{key: task[key] for key in ('id', 'title', 'status', 'priority', 'depends_on')} for task in tasks],
            'limitations':limitations}


def preview(D, root, workspace, settings, profile, products, request):
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
