#!/usr/bin/env python3
"""Prepare isolated agent scenarios and grade observable workflow artifacts."""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import zipfile

CORE=Path(__file__).resolve().parents[1]
SCENARIOS=CORE/'tests/fixtures/agent-conformance/scenarios.json'
REQUIRED_CHECKS={
    'intake-ru':{'one_pending','notes_unchanged','no_implementation'},
    'intake-en-clarify':{'fixture_unchanged','queue_unchanged','source_unchanged','no_implementation'},
    'routing-negative':{'fixture_unchanged','queue_unchanged','source_unchanged','no_implementation'},
    'process-en':{'one_prioritized','source_unchanged','waits_for_selection'},
    'resume-status-ru':{'checkpoint_unchanged','source_unchanged','queue_unchanged'},
    'controller-en':{'exact_snapshot','selected_completed','unrelated_deferred','controller_finished','independent_behavior'},
    'pr-literal-en':{'merge_not_authorized','branches_preserved','source_unchanged'},
    'snapshot-en':{'one_snapshot','canonical_readme','generated_and_private_excluded','source_unchanged'},
}
CLARIFICATION_CASES={
    'clarification-full-en':{'resume':False},
    'clarification-resume-en':{'resume':True},
}
CLARIFICATION_CHECKS={
    'actual_agent_observations','exact_scope','question_before_answer',
    'submitted_answers_bound','task_revised','revision_identity_preserved',
    'current_clarity','current_confirmation','source_unchanged',
    'parked_state_unchanged','no_implementation','execution_snapshot_unchanged',
}

def load_workflow(root):
    spec=importlib.util.spec_from_file_location('conformance_workflow',root/'.agents/skills/skill-tree-implement-all/scripts/workflow-state.py')
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def cases():
    return json.loads(SCENARIOS.read_text())['scenarios']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot(root):
    return {p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts}

def prepare(case_id,root):
    case=next(case for case in cases() if case['id']==case_id)
    if root.exists():raise ValueError('An unused isolated fixture path is required')
    ancestor=root.parent
    while not ancestor.exists():ancestor=ancestor.parent
    repository=subprocess.run(['git','-C',str(ancestor),'rev-parse','--show-toplevel'],capture_output=True)
    if repository.returncode==0:raise ValueError('An agent fixture must remain outside an existing Git repository')
    root.mkdir(parents=True)
    (root/'package.json').write_text(json.dumps({'scripts':{'test':'python3 -m unittest discover -s tests -v'}}))
    (root/'README.md').write_text('# Counter Project\n\nThe project increments an integer.\n')
    (root/'AGENTS.md').write_text('# Fixture Rules\n\nUse matching installed Skill Tree operations. Writes stay inside the fixture. Network, publication, dependency installation and commits are outside the fixture scope.\n')
    (root/'counter.py').write_text('def increment(value):\n    return value\n')
    (root/'notes.md').write_text('Preserved fixture notes.\n')
    (root/'unrelated.py').write_text('UNCHANGED = True\n')
    (root/'tests').mkdir();(root/'tests/test_counter.py').write_text('import unittest\nfrom counter import increment\n\nclass CounterTests(unittest.TestCase):\n    def test_increment(self):\n        self.assertEqual(increment(4), 5)\n')
    docs=root/'.skill-tree/documents';docs.mkdir(parents=True)
    (docs/'future.md').write_text('# Future Work\n\n## Pending Task Format\n\nFixed headers precede task bodies.\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
    subprocess.run(['node',str(CORE/'bin/install.js'),'--target',str(root),'--only','codex','--flavor','general','--copy'],check=True,stdout=subprocess.DEVNULL)
    wf=load_workflow(root);store=wf.Store(root)
    with store.lock():store.save(store.text(),store.load())
    selected=None
    if case_id in {'process-en','controller-en','resume-status-ru'}:
        pending=wf.intake(store,{'title':'Increment the supplied integer','description':'The increment function returns the supplied value unchanged.','expected_behavior':'The increment function returns the supplied integer plus one.'})
        selected=pending['id']
        if case_id!='process-en':
            criterion='Increment the supplied integer by one.'
            check={'id':'counter','recipe_id':'script-test','criteria':[criterion],'sources':['counter.py','tests/test_counter.py'],'parameters':{},'assertion':criterion,'timing':'immediate'}
            body='Goal:\n- '+criterion+'\n\nTouch:\n- counter.py\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- '+criterion+'\n'
            result=wf.process(store,{'selectors':[selected],'dispositions':{selected:{'status':'promoted','reason':'Counter source and the local unit assertion identify the scoped defect.'}},'tasks':[{'title':'Increment the supplied integer','parent_pending_ids':[selected],'body':body}]})
            selected=result['created_ids'][0]
            if case_id=='controller-en':
                other=wf.intake(store,{'title':'Keep unrelated work deferred','description':'The unrelated module has a separate future requirement.','expected_behavior':'The unrelated requirement remains outside the selected group.'})
                wf.process(store,{'selectors':[other['id']],'dispositions':{other['id']:{'status':'promoted','reason':'The independent requirement remains selectable outside the scoped group.'}},'tasks':[{'title':'Keep unrelated work deferred','parent_pending_ids':[other['id']],'body':body.replace('counter.py','unrelated.py'),'priority':110}]})
            else:
                wf.start(store,'next',selected)
                wf.checkpoint(store,{'phase':'blocked','stop_reason':'The owner paused implementation.','next_action':'Wait for an explicit continuation instruction.'})
    if case_id=='pr-literal-en':subprocess.run(['git','init','--quiet','--initial-branch=codex/example',str(root)],check=True)
    if case_id=='snapshot-en':
        private=root/'vendor/private.md';private.parent.mkdir();private.write_text('Private project architecture.\n')
    request=case['request'].replace('{selected_id}',selected or '')
    context={'scenario_id':case_id,'request':request,'request_sha256':hashlib.sha256(request.encode()).hexdigest(),'selected_id':selected,'before':snapshot(root),'skill_snapshot':{p.relative_to(root).as_posix():digest(p) for p in (root/'.agents/skills').rglob('*') if p.is_file() and '__pycache__' not in p.parts}}
    return context

def grade(context,root,reply):
    case_id=context['scenario_id'];wf=load_workflow(root);store=wf.Store(root);tasks=wf.parse(store.text());state=store.load();before=context['before'];after=snapshot(root)
    unchanged=lambda path:after.get(path)==before.get(path)
    common={'counter_unchanged':unchanged('counter.py'),'notes_unchanged':unchanged('notes.md'),'unrelated_unchanged':unchanged('unrelated.py')}
    if case_id=='intake-ru':checks={'one_pending':len(tasks)==1 and tasks[0]['queue']=='Pending Queue','notes_unchanged':common['notes_unchanged'],'no_implementation':not state['task_progress'] and state['active_run'] is None}
    elif case_id in {'intake-en-clarify','routing-negative'}:checks={'fixture_unchanged':after==before,'queue_unchanged':unchanged('.skill-tree/documents/future.md'),'source_unchanged':all(common.values()),'no_implementation':not state['task_progress'] and state['active_run'] is None}
    elif case_id=='process-en':checks={'one_prioritized':len(tasks)==1 and tasks[0]['queue']=='Prioritized Next Changes','source_unchanged':all(common.values()),'waits_for_selection':not state['task_progress'] and state['active_run'] is None and not store.outcomes()}
    elif case_id=='resume-status-ru':checks={'checkpoint_unchanged':unchanged('.skill-tree/documents/future.json'),'source_unchanged':all(common.values()),'queue_unchanged':unchanged('.skill-tree/documents/future.md')}
    elif case_id=='controller-en':
        summaries=[json.loads(path.read_text()) for path in (root/'.skill-tree/history/runs').glob('run-*.json')]
        run=state['active_run'] or (sorted(summaries,key=lambda row:row.get('finished_at',''))[-1] if summaries else {})
        outcomes=store.outcomes();behavior=subprocess.run(['python3','-c','from counter import increment; assert increment(4)==5; assert increment(-1)==0; assert increment(0)==1'],cwd=root,capture_output=True)
        checks={'exact_snapshot':run.get('snapshot')==[context['selected_id']],'selected_completed':any(o['task_id']==context['selected_id'] and o['disposition']=='completed' for o in outcomes),'unrelated_deferred':len(tasks)==1 and tasks[0]['id']!=context['selected_id'] and common['unrelated_unchanged'],'controller_finished':state['active_run'] is None and run.get('phase')=='completed','independent_behavior':behavior.returncode==0}
    elif case_id=='pr-literal-en':
        result=json.loads((root/'parameters.json').read_text());checks={'merge_not_authorized':result.get('merge') is False and result.get('authorization',{}).get('merge') is False,'branches_preserved':result.get('source_branch')=='codex/example' and result.get('target_branch')=='develop','source_unchanged':all(common.values())}
    elif case_id=='snapshot-en':
        archives=list((root/'.skill-tree/artifacts').glob('*.zip'));paths=[]
        if len(archives)==1:
            with zipfile.ZipFile(archives[0]) as archive:
                paths=[relevance.split('Original source path: ',1)[1].splitlines()[0] for name in archive.namelist() for relevance in [archive.read(name).decode()] if 'Original source path: ' in relevance]
        checks={'one_snapshot':len(archives)==1,'canonical_readme': 'README.md' in paths,'generated_and_private_excluded':bool(paths) and all(not p.startswith(('.skill-tree/installation/','.agents/','vendor/')) for p in paths),'source_unchanged':all(common.values())}
    else:raise ValueError('Unknown scenario')
    checks['execution_snapshot_unchanged']=all(after.get(path)==value for path,value in before.items() if path.startswith(('.agents/','.skill-tree/installation/')))
    return {'scenario_id':case_id,'checks':checks,'passed':bool(reply.strip()) and all(checks.values()),'request_sha256':context['request_sha256'],'skill_snapshot_sha256':hashlib.sha256(json.dumps(context['skill_snapshot'],sort_keys=True).encode()).hexdigest(),'reply':reply}

def validate_report(report):
    expected={case['id'] for case in cases()};rows=report.get('scenarios',[])
    if report.get('schema')!=1 or len(rows)!=len(expected) or {row.get('scenario_id') for row in rows}!=expected:raise ValueError('Complete unique scenario coverage is required')
    for row in rows:
        if not row.get('agent_id') or not row.get('provider') or not row.get('model_configuration') or not row.get('request_sha256') or not row.get('skill_snapshot_sha256'):raise ValueError('Actual agent, provider, model configuration and context identities are required')
        required=REQUIRED_CHECKS[row['scenario_id']]|{'execution_snapshot_unchanged'}
        if not row.get('reviewed') or not row.get('review_notes') or not row.get('passed') or set(row.get('checks',{}))!=required or not all(value is True for value in row['checks'].values()):raise ValueError('Observed artifacts and reviewed semantic assertions must pass')
        configuration=row['model_configuration']
        if isinstance(configuration,dict) and not configuration.get('reported_model_id') and not report.get('limitations'):raise ValueError('An unexposed exact model identity requires an explicit report limitation')
    return {'passed':True,'scenarios':len(rows),'scope':'Bounded observed Codex scenarios; helper tests and universal agent adherence remain separate.'}

def clarification_cases():
    return [{'id':key,**value} for key,value in CLARIFICATION_CASES.items()]

def _clarification_body():
    criterion='The counter export specification records the owner-selected format and signed-integer policy.'
    check={'id':'export-specification','recipe_id':'static-inspection','criteria':[criterion],
           'sources':['counter.py','README.md'],'parameters':{},'assertion':criterion,'timing':'immediate'}
    return ('Goal:\n- Define a counter export interface before implementation.\n\n'
            'Scope:\n- Choose the export representation and treatment of negative integers.\n\n'
            'Out of scope:\n- Counter implementation, network services and package changes.\n\n'
            'Current behavior:\n- counter.py contains the existing counter function and no export interface.\n\n'
            'Touch:\n- counter.py\n- README.md\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+
            '\n```\n\nAcceptance:\n- '+criterion+'\n')

def _implementation_state(state):
    return {key:state.get(key) for key in ['active_run','run_registry','task_progress']}

def _project_sources(root):
    return {p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file()
            and not any(part in {'.git','.agents','.skill-tree','__pycache__'} for part in p.relative_to(root).parts)
            and (p.suffix in {'.py','.js','.ts','.tsx','.cs','.md'} or p.name in {'package.json','package-lock.json'})}

def prepare_clarification(case_id,root):
    if case_id not in CLARIFICATION_CASES:raise ValueError('Unknown clarification scenario')
    # The existing parked-run fixture supplies a real unrelated checkpoint, never a successful interview.
    prepare('resume-status-ru',root)
    wf=load_workflow(root);store=wf.Store(root)
    if not hasattr(wf,'clarification_read') or not (root/'.agents/skills/skill-tree-clarify-tasks/SKILL.md').is_file():
        raise ValueError('Sync the authored clarification operation before installing the isolated fixture')
    pending=wf.intake(store,{'title':'Specify counter export','description':'The export representation and signed-integer policy require owner decisions before implementation.',
                             'expected_behavior':'The task records an owner-approved counter export specification.','priority':120})
    selected=wf.process(store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Source inspection identifies the existing counter and the missing export specification.'}},
                              'tasks':[{'title':'Specify counter export','parent_pending_ids':[pending['id']],'body':_clarification_body()}]})['created_ids'][0]
    text=store.text();tasks=wf.parse(text);state=store.load(text)
    request=f'Use the installed task clarification skill to clarify {selected} in {root}. Resolve the task specification with me before implementation.'
    context={'schema':1,'kind':'clarification-agent-context','scenario_id':case_id,'root':str(root.resolve()),
             'request':request,'request_sha256':hashlib.sha256(request.encode()).hexdigest(),'selected_ids':[selected],
             'before':snapshot(root),'source_snapshot':_project_sources(root),'implementation_state':_implementation_state(state),
             'task_baselines':{task['id']:task for task in tasks},
             'skill_snapshot':{p.relative_to(root).as_posix():digest(p) for p in (root/'.agents/skills').rglob('*') if p.is_file() and '__pycache__' not in p.parts},
             'fixture_owner':{'answer':{'phase':'owner-answer','reference':'fixture-owner:answer-1','text':'Use a JSON object with a value integer field. Preserve signed integers, including negative values. Keep counter implementation outside this task.'},
                              'confirmation':{'phase':'owner-confirmation','reference':'fixture-owner:confirmation-1','text':'Yes, I confirm the current revised task specification and summary. Do not implement the counter.'}},
             'limitations':['Owner inputs are scripted fixture-owner messages, not real-human acceptance.',
                            'The native external Skill tool is unavailable; installed clarification behavior and native invocation remain separate.',
                            'The current inherited host configuration is used; the exact model identifier may remain unexposed.']}
    return context

def observe_clarification(context,root,phase,reply):
    """Capture artifact observations; the caller supplies actual agent identity separately."""
    if not isinstance(phase,str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*',phase):raise ValueError('Observation phase requires a lowercase descriptive label')
    wf=load_workflow(root);store=wf.Store(root);text=store.text()
    sessions=[json.loads(path.read_text()) for path in sorted((root/'.skill-tree/clarifications').glob('cl-*.json'))]
    return {'phase':phase,'reply':reply,'sessions':sessions,'source_hash':hashlib.sha256(text.encode()).hexdigest(),
            'tasks':{task['id']:task for task in wf.parse(text)},'implementation_state':_implementation_state(store.load(text)),
            'source_snapshot':_project_sources(root)}

def interrupt_clarification(context,root):
    """Insert only an unrelated fixture task; an actual agent must resume the interview."""
    if context['scenario_id']!='clarification-resume-en':raise ValueError('Only the resume scenario accepts an interruption')
    wf=load_workflow(root);store=wf.Store(root)
    sessions=list((root/'.skill-tree/clarifications').glob('cl-*.json'))
    if len(sessions)!=1:raise ValueError('Observe one actual question session before interruption')
    session=json.loads(sessions[0].read_text())
    if session['state']!='awaiting-answers' or session['task_ids']!=context['selected_ids']:raise ValueError('Interruption requires the unanswered selected session')
    # Controlled fixture arrival changes the queue, never the parked implementation checkpoint.
    task_id=wf.identity('T');meta={'id':task_id,'priority':999,'status':'Ready','parent_pending_ids':[wf.identity('P')],
        'processing_run_id':wf.identity('PR'),'root_task_id':task_id,'related_task_id':None,'relation':'main','depends_on':[]}
    with store.lock():
        text=store.text();state=store.load(text)
        store.save(wf.insert(text,'Prioritized Next Changes',wf.render('Later unrelated requirement',meta,_clarification_body())),state)
    task=next(task for task in wf.parse(store.text()) if task['id']==task_id)
    return {'phase':'interruption','session':session,'added_task':task,
            'implementation_state':_implementation_state(store.load()),
            'resume_request':f'Resume clarification session {session["id"]} in {root}. Continue the existing selected discussion.'}

def _owner_evidence_matches(evidence,message,answer=None):
    if not isinstance(evidence,dict) or evidence.get('kind') not in {'owner-message','submitted-answer'}:return False
    reference=evidence.get('reference','')
    return bool(reference and (message.get('reference','!missing!') in reference or message.get('text','!missing!') in reference or answer==message.get('text')))

def _clarification_role(event,role):
    conventional={'revision-summary':'revision','owner-confirmation':'owner-confirmation'}
    if event.get('phase')==conventional[role]:return True
    review=event.get('role_review',{})
    return (role in event.get('roles',[]) and review.get('reviewed') is True and
            bool(review.get('reviewer')) and review.get('reviewer')!=event.get('agent_id') and
            isinstance(review.get('notes'),str) and bool(review['notes'].strip()))

def _clarification_turns(events):
    complete=next(((i,e) for i,e in reversed(list(enumerate(events))) if e.get('phase')=='complete'),(-1,{}))
    consent=next(((i,e) for i,e in reversed(list(enumerate(events))) if i<complete[0] and _clarification_role(e,'owner-confirmation')),(-1,{}))
    before=consent[0] if consent[0]>=0 else complete[0]
    summary=next(((i,e) for i,e in reversed(list(enumerate(events))) if i<before and _clarification_role(e,'revision-summary')),(-1,{}))
    return summary,consent,complete

def _current_clarification_display(event,session,tasks,source_hash):
    sessions=event.get('sessions',[]);selected=session.get('task_ids',[])
    return (len(sessions)==1 and sessions[0].get('id')==session.get('id') and
            sessions[0].get('task_ids')==selected and bool(selected) and
            sessions[0].get('semantic_fingerprints')==session.get('semantic_fingerprints') and
            event.get('source_hash')==source_hash and
            all(tid in tasks and event.get('tasks',{}).get(tid,{}).get('body')==tasks[tid]['body'] for tid in selected))

def grade_clarification(context,root,observations):
    if context.get('scenario_id') not in CLARIFICATION_CASES:raise ValueError('Unknown clarification scenario')
    events=observations.get('events',[]);wf=load_workflow(root);store=wf.Store(root);text=store.text();tasks=wf.parse(text);by_id={task['id']:task for task in tasks}
    paths=list((root/'.skill-tree/clarifications').glob('cl-*.json'));session=json.loads(paths[0].read_text()) if len(paths)==1 else {}
    selected=context['selected_ids'];question=next((e for e in events if e.get('phase')=='question'),{})
    (summary_index,revision),(consent_index,confirm_owner),(complete_index,complete)=_clarification_turns(events)
    owners=[e for e in events if e.get('phase')=='owner-answer']
    initial_session=question.get('sessions',[{}])[0] if len(question.get('sessions',[]))==1 else {}
    valid_answers=[a for a in session.get('answers',{}).values() if a.get('valid') is True]
    phases=[e.get('phase') for e in events]
    ordered=lambda a,b:a in phases and b in phases and phases.index(a)<phases.index(b)
    protected={key:value for key,value in context['before'].items() if key.startswith(('.agents/','.skill-tree/installation/'))}
    after=snapshot(root);state=store.load(text);expected_state=context['implementation_state']
    interruptions=[e for e in events if e.get('phase')=='interruption']
    expected_ids=set(context['task_baselines'])|{e['added_task']['id'] for e in interruptions if e.get('added_task',{}).get('id')}
    semantics=wf.clarification_fingerprints(wf.clarification_baselines([by_id[tid] for tid in selected if tid in by_id])) if hasattr(wf,'clarification_fingerprints') else {}
    confirmation=session.get('confirmation') or {};clarity=session.get('clarity') or {}
    source_hash=hashlib.sha256(text.encode()).hexdigest()
    displayed_current=_current_clarification_display(revision,session,by_id,source_hash)
    actor_snapshots=[e for e in events if e.get('agent_id') and e.get('sessions')]
    observed_after=events[summary_index+1:complete_index+1] if summary_index>=0 else []
    unchanged_after=displayed_current and all(_current_clarification_display(e,session,by_id,source_hash) for e in observed_after if e.get('sessions'))
    displayed_revisions={row.get('id') for s in revision.get('sessions',[]) for row in s.get('task_revisions',[])}
    unchanged_after=unchanged_after and not any(any(row.get('changed_fields',{}).get(tid) for tid in selected) for row in session.get('task_revisions',[]) if row.get('id') not in displayed_revisions)
    provenance=['id','parent_pending_ids','processing_run_id','root_task_id','related_task_id','relation','validation_group_id','boundary_validation']
    checks={
      'actual_agent_observations':all(event.get('agent_id') and event.get('reply','').strip() for event in [question,revision,complete]),
      'exact_scope':len(paths)==1 and session.get('task_ids')==selected and initial_session.get('task_ids')==selected and set(by_id)==expected_ids,
      'question_before_answer':bool(initial_session.get('rounds')) and initial_session.get('state')=='awaiting-answers' and not initial_session.get('answers') and ordered('question','owner-answer'),
      'submitted_answers_bound':bool(owners) and bool(valid_answers) and all(any(_owner_evidence_matches(answer.get('evidence'),owner,answer.get('answer')) for owner in owners) for answer in valid_answers),
      'task_revised':bool(session.get('task_revisions')) and all(tid in by_id and by_id[tid]['body']!=context['task_baselines'][tid]['body'] and session.get('semantic_fingerprints',{}).get(tid)!=initial_session.get('semantic_fingerprints',{}).get(tid) for tid in selected) and any(e.get('phase')=='owner-answer' for e in events[:max(summary_index,0)]),
      'revision_identity_preserved':all(tid in by_id and all(by_id[tid].get(field)==context['task_baselines'][tid].get(field) for field in provenance) for tid in selected),
      'current_clarity':displayed_current and bool(clarity.get('assessment',{}).get('evidence')) and all(clarity.get('assessment',{}).get(key) is True for key in ['goals','scope','exclusions','dependencies','acceptance','validation','decisions']) and clarity.get('semantic_fingerprints')==semantics and bool(session.get('rounds')) and not session['rounds'][-1].get('question_ids') and all(not q.get('required',True) or session.get('answers',{}).get(key,{}).get('valid') is True for key,q in session.get('questions',{}).items()),
      'current_confirmation':unchanged_after and summary_index<consent_index<complete_index and session.get('state')=='complete' and confirmation.get('task_ids')==selected and confirmation.get('semantic_fingerprints')==semantics and _owner_evidence_matches(confirmation.get('evidence'),confirm_owner) and session.get('source_hash')==source_hash,
      'source_unchanged':_project_sources(root)==context['source_snapshot'] and all(event.get('source_snapshot')==context['source_snapshot'] for event in actor_snapshots),
      'parked_state_unchanged':_implementation_state(state)==expected_state and all(event.get('implementation_state')==expected_state for event in actor_snapshots) and all(task_id in by_id and by_id[task_id]['body']==baseline['body'] for task_id,baseline in context['task_baselines'].items() if task_id not in selected),
      'no_implementation':_implementation_state(state)==expected_state and {path:value for path,value in after.items() if path.startswith('.skill-tree/history/task-outcomes')}=={path:value for path,value in context['before'].items() if path.startswith('.skill-tree/history/task-outcomes')},
      'execution_snapshot_unchanged':{path:value for path,value in after.items() if path.startswith(('.agents/','.skill-tree/installation/'))}==protected,
    }
    if CLARIFICATION_CASES[context['scenario_id']]['resume']:
        interruption=interruptions[0] if len(interruptions)==1 else {};resumed=next((e for e in events if e.get('phase')=='resumed'),{})
        resumed_session=resumed.get('sessions',[{}])[0] if len(resumed.get('sessions',[]))==1 else {}
        added=interruption.get('added_task',{})
        checks['same_session_resumed']=bool(resumed.get('agent_id')) and resumed.get('agent_id')!=question.get('agent_id') and initial_session.get('id')==resumed_session.get('id')==session.get('id') and resumed_session.get('task_ids')==selected and not resumed_session.get('answers') and interruption.get('implementation_state')==expected_state and ordered('question','interruption') and ordered('interruption','resumed') and ordered('resumed','owner-answer')
        checks['higher_unrelated_deferred']=added.get('priority',0)>max(context['task_baselines'][tid]['priority'] for tid in selected) and added.get('id') in by_id and by_id[added['id']]['body']==added.get('body') and added['id'] not in session.get('task_ids',[])
    return {'scenario_id':context['scenario_id'],'checks':checks,'passed':all(checks.values()),
            'request_sha256':context['request_sha256'],'skill_snapshot_sha256':hashlib.sha256(json.dumps(context['skill_snapshot'],sort_keys=True).encode()).hexdigest(),
            'session_id':session.get('id'),'session_sha256':digest(paths[0]) if len(paths)==1 else None,
            'selected_task_ids':selected,'task_content':{tid:by_id[tid]['body'] for tid in selected if tid in by_id},
            'observations':observations,'limitations':context['limitations']}

def validate_clarification_report(report):
    rows=report.get('scenarios',[])
    if report.get('schema')!=1 or report.get('kind')!='clarification-agent-conformance' or len(rows)!=2 or {row.get('scenario_id') for row in rows}!=set(CLARIFICATION_CASES):raise ValueError('Both unique clarification scenarios are required')
    for row in rows:
        required=CLARIFICATION_CHECKS|({'same_session_resumed','higher_unrelated_deferred'} if CLARIFICATION_CASES[row['scenario_id']]['resume'] else set())
        if set(row.get('checks',{}))!=required or not row.get('passed') or not all(value is True for value in row['checks'].values()):raise ValueError('Actual observations and artifact checks must pass')
        if not row.get('provider') or not row.get('model_configuration') or not row.get('session_id') or not row.get('session_sha256') or not row.get('request_sha256') or not row.get('skill_snapshot_sha256'):raise ValueError('Actual host, model configuration, session and context identities are required')
        if not row.get('reviewed') or not row.get('review_notes') or not row.get('semantic_revision_review'):raise ValueError('Independent semantic revision and interaction review is required')
        events=row.get('observations',{}).get('events',[])
        summary,consent,complete=_clarification_turns(events)
        for event in [next((event for event in events if event.get('phase')=='question'),{}),summary[1],complete[1]]:
            if not event.get('agent_id') or not event.get('reply') or len(event.get('sessions',[]))!=1 or not event.get('source_hash') or not event.get('tasks'):raise ValueError('Observed interaction turns and captured fixture artifacts are required')
        if not summary[0]<consent[0]<complete[0]:raise ValueError('A displayed current summary and later actual consent are required')
        if not report.get('limitations'):raise ValueError('Scripted-owner, native invocation and model identity limitations are required')
    return {'passed':True,'scenarios':2,'scope':'Bounded actual-agent clarification observations with scripted fixture-owner inputs; no real-human or native external-skill qualification.'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','grade','validate','clarification-prepare','clarification-observe','clarification-interrupt','clarification-grade','clarification-validate']);parser.add_argument('--scenario');parser.add_argument('--root',type=Path);parser.add_argument('--input',type=Path);parser.add_argument('--reply',type=Path);parser.add_argument('--observations',type=Path);parser.add_argument('--phase');args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.scenario,args.root.resolve())
    elif args.command=='grade':result=grade(json.loads(args.input.read_text()),args.root.resolve(),args.reply.read_text())
    elif args.command=='validate':result=validate_report(json.loads(args.input.read_text()))
    elif args.command=='clarification-prepare':result=prepare_clarification(args.scenario,args.root.resolve())
    elif args.command=='clarification-observe':result=observe_clarification(json.loads(args.input.read_text()),args.root.resolve(),args.phase,args.reply.read_text())
    elif args.command=='clarification-interrupt':result=interrupt_clarification(json.loads(args.input.read_text()),args.root.resolve())
    elif args.command=='clarification-grade':result=grade_clarification(json.loads(args.input.read_text()),args.root.resolve(),json.loads(args.observations.read_text()))
    else:result=validate_clarification_report(json.loads(args.input.read_text()))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
