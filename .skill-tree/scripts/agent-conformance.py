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

CORE_DECISION_CASES={'core-auto-significant','core-manual','core-switch-resume'}
CORE_DECISION_SOURCES={'common/scripts/workflow-state.py','common/scripts/decision-governance.py','common/scripts/decision-orchestration.py'}

def _validate_core_decision_report(report,trusted_capture=None):
    """Validate caller-captured observations; a report never establishes its own origin."""
    import tempfile
    def require(condition,message):
        if not condition:raise ValueError(message)
    def text(value):return isinstance(value,str) and bool(value.strip())
    def sha(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
    def load(name,relative):
        spec=importlib.util.spec_from_file_location(name,CORE/relative)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
    require(isinstance(report,dict) and report.get('schema')==1 and report.get('kind')=='core-decision-agent-conformance','A core decision observation report is required')
    require(isinstance(trusted_capture,dict) and trusted_capture is not report and trusted_capture.get('schema')==1 and trusted_capture.get('kind')=='core-decision-native-capture','A separately supplied trusted native capture is required; report labels are insufficient')
    sources=report.get('source_snapshot');require(isinstance(sources,dict) and CORE_DECISION_SOURCES<=set(sources),'Current core source fingerprints are required')
    require(sources==trusted_capture.get('source_snapshot'),'Report and external capture source fingerprints differ')
    for relative,fingerprint in sources.items():
        require(isinstance(relative,str) and not Path(relative).is_absolute() and '\\' not in relative and '..' not in Path(relative).parts and sha(fingerprint),'Core source paths require portable SHA256 fingerprints')
        file=CORE/relative;require(file.is_file() and digest(file)==fingerprint,'Core source fingerprints differ from the current execution source')
    limitations=report.get('limitations');require(isinstance(limitations,list) and limitations and all(text(v) for v in limitations),'Capture trust, scripted-owner and unexposed native metadata limitations are required')
    words=' '.join(limitations).casefold()
    require(all(word in words for word in ['capture','scripted','human','model','token','cost']),'Capture trust, scripted-owner and unexposed model/token/cost limitations must be explicit')
    rows=report.get('scenarios');events=trusted_capture.get('events')
    require(isinstance(rows,list) and len(rows)==3 and all(isinstance(v,dict) for v in rows) and {v.get('scenario_id') for v in rows}==CORE_DECISION_CASES,'Three unique core decision scenarios are required')
    require(isinstance(events,list) and events and all(isinstance(v,dict) and text(v.get('id')) and v.get('scenario_id') in CORE_DECISION_CASES and type(v.get('sequence')) is int and v['sequence']>0 for v in events),'External capture requires identified ordered native events')
    indexed={event['id']:event for event in events};require(len(indexed)==len(events),'External capture event identities must be unique')
    governance=load('conformance_core_decisions','common/scripts/decision-governance.py')
    orchestration=load('conformance_core_orchestration','common/scripts/decision-orchestration.py')

    def native(event):
        require(text(event.get('provider')) and sha(event.get('native_request_sha256')),'Actual native provider and full request fingerprint are required')
        actor=event.get('actor');require(isinstance(actor,dict) and set(actor)=={'id','context_id'} and all(text(v) for v in actor.values()),'An actual native actor and context identity are required')
        require(all(key in event for key in ['tool_call_id','model','tokens','cost']),'Unexposed native metadata must be explicit null values or actual observations')
        if event['kind']=='actor-created':require(event.get('tool')=='collaboration.spawn_agent','A delegated role requires an actual native actor creation capture')
        else:
            inventory=event.get('inventory_entry',{})
            require(event['kind']=='executor-observed' and event.get('tool')=='collaboration.list_agents' and inventory.get('agent_name')==actor['id'] and inventory.get('agent_status')=='running','An existing executor requires an observed running native inventory entry')
        return actor

    class SnapshotStore:
        def __init__(self,root):self.root=root
        def owned(self,relative):return self.root/relative

    for row in rows:
        scenario=row['scenario_id'];ids=row.get('event_ids')
        require(isinstance(ids,list) and ids and all(isinstance(v,str) and v in indexed for v in ids) and len(ids)==len(set(ids)),'Report event references must resolve uniquely against the separate capture')
        observed=[indexed[value] for value in ids]
        require(all(event['scenario_id']==scenario for event in observed) and set(ids)=={event['id'] for event in events if event['scenario_id']==scenario},'Every scenario event must be captured, referenced and bound to the exact scenario')
        sequence=[event['sequence'] for event in observed];require(sequence==sorted(set(sequence)),'Captured scenario order must be strictly increasing')
        require(all(event['kind'] in {'actor-created','executor-observed','actor-returned','observation','scripted-owner-input','stale-result-rejected'} for event in observed),'Unknown native capture event kind')
        by_id={event['id']:event for event in observed}
        creations=[event for event in observed if event['kind'] in {'actor-created','executor-observed'}]
        for event in creations:native(event)
        returns=[event for event in observed if event['kind']=='actor-returned']
        for event in returns:
            creation=by_id.get(event.get('creation_event_id'),{})
            require(creation.get('kind')=='actor-created' and creation['sequence']<event['sequence'] and sha(event.get('input_digest')) and isinstance(event.get('result'),dict) and event['result'].get('input_digest')==event['input_digest'],'A returned JSON result requires an earlier actual creation and the exact sealed input digest')
        observations=[event for event in observed if event['kind']=='observation']
        final=[event for event in observations if event.get('label')=='final'];require(len(final)==1 and observations[-1] is final[0],'One final current artifact observation is required')
        final=final[0];frame=final.get('orchestration',{});decision=final.get('decision',{})
        require(isinstance(frame,dict) and isinstance(decision,dict),'Actual final DG and orchestration bytes are required')
        executor=[event for event in creations if event.get('actor')==frame.get('executor')]
        require(len(executor)==1 and executor[0]['sequence']<final['sequence'],'The actual observed executor must match the orchestration and decision ledgers')
        require(executor[0]['kind']=='executor-observed' or executor[0].get('role') in {'executor','worker'},'A decision role cannot double as executor evidence')
        with tempfile.TemporaryDirectory(prefix='skill-tree-observed-decision-') as temporary:
            store=SnapshotStore(Path(temporary));directory=store.root/'.skill-tree/decisions';directory.mkdir(parents=True)
            def verify_observation(event,accepted=False):
                current_frame=event.get('orchestration');current_decision=event.get('decision')
                require(isinstance(current_frame,dict) and isinstance(current_decision,dict) and current_frame.get('id')==frame.get('id') and current_decision.get('id')==decision.get('id'),'Captured observations must retain the original exact orchestration and decision identities')
                require(current_frame.get('executor')==frame.get('executor') and governance._identity(current_frame.get('context',{}))==governance._identity(frame.get('context',{})),'Captured executor and typed scope must remain exact')
                frozen=current_frame.get('execution_snapshot');require(isinstance(frozen,dict) and all(frozen.get(key)==value for key,value in sources.items()),'Every current source fingerprint must match the frozen orchestration input')
                for record,key in [(current_frame,'orchestration_hash'),(current_decision,'decision_hash')]:
                    identity=record.get('id');pattern=orchestration.DO if key=='orchestration_hash' else governance.DG
                    require(isinstance(identity,str) and pattern.fullmatch(identity) and record.get(key)==governance._hash({k:v for k,v in record.items() if k!=key}),'Captured artifact identity or checksum differs')
                    (directory/(record['id'].lower()+'.json')).write_text(json.dumps(record))
                try:
                    loaded=orchestration.read(store,current_frame['id']);attached=orchestration.ledger(store,loaded)
                    require(attached==current_decision and current_decision['context']==orchestration.decision_context(loaded,loaded['question_purpose']),'Current question scope differs from the orchestration input')
                    require(event.get('action')==orchestration.next_action(store,loaded['id'])['action'],'Captured next action differs from the actual observed artifact frontier')
                    if accepted:
                        receipt=governance.acceptance_reference(store,{'decision_id':current_decision['id'],'acceptance_digest':current_decision.get('acceptance',{}).get('digest')},{'context':current_decision['context'],'mode':loaded['mode'],'mode_epoch':current_decision['mode_epoch'],'authority_digest':governance._hash(loaded['authority']),'kind':current_decision['question']['kind']})
                        require(loaded.get('acceptance')==receipt and event.get('action')=='accepted','The final orchestration must contain the current exact accepted DG receipt')
                except (KeyError,TypeError,governance.DecisionError,orchestration.OrchestrationError) as error:raise ValueError('Captured current decision artifacts are invalid: '+str(error)) from error
            for event in observations:verify_observation(event,event is final)

        requests=frame.get('actor_requests');require(isinstance(requests,dict),'Actual sealed actor requests are required')
        attempts=decision.get('attempts',{})
        for attempt_id,attempt in attempts.items():
            request=requests.get(attempt_id);require(isinstance(request,dict) and request.get('attempt_id')==attempt_id and isinstance(request.get('input'),dict),'Each original actor attempt requires its sealed orchestration request')
            envelope=request['input'];input_digest=request.get('input_digest')
            require(sha(input_digest) and input_digest==governance._hash(envelope) and envelope.get('orchestration_id')==frame['id'] and envelope.get('actor')==attempt['actor'] and envelope.get('decision_id')==decision['id'] and envelope.get('role')==attempt['role'] and envelope.get('mode')==attempt['mode'] and envelope.get('mode_epoch')==attempt['mode_epoch'] and envelope.get('authority_digest')==attempt['authority_digest']==governance._hash(envelope.get('authority')) and governance._hash(envelope.get('question'))==attempt['question_digest'] and governance._identity(envelope.get('context',{}))==governance._identity(decision['context']) and envelope.get('context',{}).get('semantic_fingerprint')==attempt['semantic_fingerprint'] and envelope.get('context',{}).get('content_fingerprint')==attempt['content_fingerprint'],'Sealed actor input differs from the original exact DG scope, question, mode or authority')
            predecessors={'critic':{'resolver'},'arbiter':{'resolver','critic'}}.get(attempt['role'],set())
            prior={value['role']:value for value in attempts.values() if value['role'] in predecessors and value['status'] in {'answered','agree','disagree'} and all(value[key]==attempt[key] for key in ['mode','mode_epoch','frontier_epoch','authority_digest','semantic_fingerprint','question_digest'])}
            basis={role:governance._receipt(value) for role,value in prior.items()}
            require(envelope.get('role_receipts')==basis,'An actual critic or arbiter input must contain the exact predecessor result and evidence receipts')
            material={role:{key:value[key] for key in ['actor','status','result','evidence']} for role,value in prior.items()}
            require(envelope.get('prior_role_results')==material,'Sealed predecessor material must contain the exact actual answers, public rationales, actors, statuses and evidence; receipt hashes alone are insufficient')
            frozen=envelope.get('execution_snapshot');require(isinstance(frozen,dict) and all(frozen.get(k)==v for k,v in sources.items()),'Actual actor inputs must bind the observed current core sources')
            if attempt['role']=='owner':
                require(request.get('creation_evidence') is None and envelope.get('creation_evidence') is None,'A scripted owner input cannot claim native agent creation')
                owners=[event for event in observed if event['kind']=='scripted-owner-input' and event.get('actor')==attempt['actor'] and event.get('result')==attempt.get('result') and event.get('evidence')==attempt.get('evidence')]
                require(len(owners)==1 and owners[0].get('real_human') is False and owners[0]['sequence']<final['sequence'],'The accepted owner result requires exact externally captured scripted input with no real-human claim')
            else:
                creation=request.get('creation_evidence',{});native_event=by_id.get(creation.get('reference'),{})
                require(native_event.get('kind')=='actor-created' and native_event.get('role')==attempt['role'] and native_event.get('actor')==attempt['actor'] and creation==envelope.get('creation_evidence') and creation.get('kind')=='host-agent-created' and creation.get('provider')==native_event.get('provider') and creation.get('tool')==native_event.get('tool') and creation.get('actor_id')==attempt['actor']['id'] and creation.get('actor_context_id')==attempt['actor']['context_id'],'A delegated DG role must match an actual externally captured creation')
                matches=[event for event in returns if event['creation_event_id']==native_event['id'] and event['input_digest']==input_digest]
                require(len(matches)==1,'Each original delegated input requires one exact actual returned JSON observation')
                returned=matches[0];require(returned['sequence']<final['sequence'],'A decision cannot precede its actual actor result')
                if attempt['status'] in {'answered','agree','disagree'}:
                    evidence=attempt.get('evidence',{})
                    require(returned['result']==attempt.get('result') and evidence.get('kind')=='delegated-agent' and evidence.get('reference')==returned['id'] and evidence.get('creation_reference')==native_event['id'] and evidence.get('provider')==native_event['provider'] and text(evidence.get('tool')),'Actual returned JSON and original creation must match the recorded DG answer evidence')

        def label(name):
            found=[event for event in observations if event.get('label')==name];require(len(found)==1,'The actual '+name+' artifact observation is required');return found[0]
        if scenario=='core-auto-significant':
            require(frame['mode']=='auto' and decision['question'].get('significance')=='significant','The Auto scenario requires an actual significant delegated decision')
            roles=governance._roles(decision)
            require(set(roles)=={'resolver','critic','arbiter'} and roles['critic']['status']=='disagree' and decision['acceptance']['attempt_id']==roles['arbiter']['id'],'Actual substantive critic disagreement must be resolved by the independent current arbiter')
        elif scenario=='core-manual':
            wait=label('manual-wait');workers=[event for event in creations if event.get('role')=='worker' and event.get('actor')==frame['executor']]
            require(len(workers)==1 and frame['mode']=='manual' and wait.get('action') in {'ask-owner','wait-owner'} and wait['orchestration'].get('acceptance') is None and wait['decision'].get('acceptance') is None,'Manual requires an actual independent worker waiting without acceptance')
            owner=[event for event in observed if event['kind']=='scripted-owner-input'];require(len(owner)==1,'Manual requires one actual scripted fixture-owner input')
            worker_returns=[event for event in returns if event['creation_event_id']==workers[0]['id']]
            waiting=[event for event in worker_returns if event['result'].get('status')=='waiting'];complete=[event for event in worker_returns if event['result'].get('status')=='complete']
            require(len(waiting)==len(complete)==1 and waiting[0]['sequence']<=wait['sequence']<owner[0]['sequence']<complete[0]['sequence']<=final['sequence'],'Actual worker wait, scripted owner and completion must occur in that order')
        else:
            pending=label('original-pending');reconciled=label('reconciled');switched=label('switched');resumed=label('resumed')
            original=[attempt for attempt in pending['decision']['attempts'].values() if attempt['status']=='pending'];require(len(original)==1,'The switch scenario requires one original unresolved actor')
            original=original[0];old=original['id'];after=reconciled['decision']['attempts'].get(old,{})
            require(after.get('status')=='cancelled' and after.get('reconciliation',{}).get('kind')=='actor-reconciliation' and text(after['reconciliation'].get('reference')),'Only explicit original-attempt reconciliation can release the pending actor')
            rejected=[event for event in observed if event['kind']=='stale-result-rejected'];require(len(rejected)==1,'An actual rejected delivery of the held original result is required');rejected=rejected[0]
            require(pending['sequence']<reconciled['sequence']<switched['sequence']<resumed['sequence']<rejected['sequence']<final['sequence'] and switched['orchestration']['mode']!=pending['orchestration']['mode'] and switched['decision']['mode_epoch']>pending['decision']['mode_epoch'],'Reconciliation, explicit changed mode, resume and stale delivery must preserve their actual order')
            require(rejected.get('attempt_id')==old and rejected.get('input_digest')==requests[old]['input_digest'] and text(rejected.get('error')) and rejected.get('decision')==resumed['decision'],'Rejected stale delivery must retain the exact current DG bytes')
            require(any(item['event']=='switch-mode' for item in frame['history']) and any(item['event']=='resume' for item in frame['history']) and decision['attempts'][old]['status']=='cancelled' and decision['acceptance']['attempt_id']!=old and decision['acceptance']['mode_epoch']>original['mode_epoch'],'Only a new current accepted result may follow the explicit switch and resume')
    return {'passed':True,'scenarios':3,'scope':'Bounded source-bound actor observations; the separately supplied root capture is the trust boundary, not cryptographic native-origin proof. Scripted owner inputs are not real-human acceptance.'}

def validate_core_decision_report(report,trusted_capture=None):
    try:return _validate_core_decision_report(report,trusted_capture)
    except (KeyError,TypeError,IndexError,AttributeError) as error:raise ValueError('Malformed core decision report or external capture') from error

PLUGIN_INVOCATION_SOURCES={
    'common/scripts/plugin-invocation.py','common/scripts/workflow-state.py',
    'common/scripts/run-workspaces.py','common/scripts/decision-governance.py',
    'common/scripts/decision-orchestration.py','common/scripts/validate-document-rules.py',
    'common/scripts/plugin-hooks.js','lib/plugin-composition.js','lib/plugin-runtime.js',
    'lib/plugin-bindings.js','lib/plugin-parameters.js','lib/plugin-registry.js','lib/plugin-sources.js',
}

# Workflow output has its own task/CL/DO/CAS guards; authored research remains source.
PLUGIN_MUTABLE_WORKFLOW_PATHS={
    '.skill-tree/documents/future.md','.skill-tree/documents/future.json',
    '.skill-tree/skill-tree.json','.skill-tree/invocations','.skill-tree/clarifications',
    '.skill-tree/decisions','.skill-tree/local','.skill-tree/history/checkpoints',
    '.skill-tree/history/runs','.skill-tree/history/run-events','.skill-tree/history/task-outcomes.jsonl',
    '.skill-tree/run-evidence','.skill-tree/artifacts','.skill-tree/.writer-lock',
    '.skill-tree/.transaction.json',
}

def _validate_plugin_invocation_report(report,trusted_capture=None):
    """Check independently captured source-backed invocations, not self-authenticating labels."""
    import base64
    import math
    import tempfile
    def require(condition,message):
        if not condition:raise ValueError(message)
    def text(value):return isinstance(value,str) and bool(value.strip())
    def sha(value):return isinstance(value,str) and re.fullmatch('[a-f0-9]{64}',value) is not None
    def relative(value):return text(value) and not Path(value).is_absolute() and not re.match('^[A-Za-z]:',value) and '\\' not in value and '\0' not in value and all(part not in {'','..','.'} for part in value.split('/'))
    def load(name,path):
        path=CORE/path;spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(),str(path),'exec'),value.__dict__);return value
    require(isinstance(report,dict) and report.get('schema')==1 and report.get('kind')=='plugin-invocation-agent-conformance','A plugin invocation observation report is required')
    require(isinstance(trusted_capture,dict) and trusted_capture is not report and trusted_capture.get('schema')==1 and trusted_capture.get('kind')=='plugin-invocation-native-capture','A separately supplied trusted native capture is required; labels and transcripts cannot supply origin')
    sources=report.get('source_snapshot');require(isinstance(sources,dict) and PLUGIN_INVOCATION_SOURCES<=set(sources) and sources==trusted_capture.get('source_snapshot'),'The report and external capture must bind the complete current invocation source set')
    for path,fingerprint in sources.items():require(relative(path) and sha(fingerprint) and (CORE/path).is_file() and digest(CORE/path)==fingerprint,'An invocation source fingerprint is missing, stale or nonportable')
    limitations=report.get('limitations');require(isinstance(limitations,list) and limitations and all(text(value) for value in limitations),'Explicit source-backed, capture, owner and accounting limitations are required')
    words=' '.join(limitations).casefold();require(all(word in words for word in ['capture','scripted','human','source-backed','native','model','token','cost']),'The capture trust boundary, scripted owner and unexposed metadata limitations must remain explicit')
    engine=load('observed_plugin_invocation','common/scripts/plugin-invocation.py');wf=load('observed_plugin_workflow','common/scripts/workflow-state.py')
    scenario=report.get('scenario');events=trusted_capture.get('events')
    require(isinstance(scenario,dict) and scenario.get('id')=='source-backed-a-b-a' and isinstance(events,list) and events,'The bounded A1-to-B-to-A2 scenario and external events are required')
    ids=scenario.get('event_ids');require(isinstance(ids,list) and len(ids)==len(set(ids)) and len(ids)==len(events),'Every captured event requires one exact report reference')
    require(all(isinstance(event,dict) and text(event.get('id')) and type(event.get('sequence')) is int for event in events),'Native observations require exact identities and sequence numbers')
    indexed={event['id']:event for event in events};require(len(indexed)==len(events) and set(ids)==set(indexed),'Captured native event identities must be unique and complete')
    observed=[indexed[value] for value in ids];require([event['sequence'] for event in observed]==list(range(1,len(observed)+1)),'The externally observed event order must be complete and strictly increasing')
    allowed={'actor-created','actor-dispatched','actor-returned','chain-observed','scripted-owner-input','core-incorporation','core-confirmation'}
    require(all(event.get('kind') in allowed for event in observed),'Unknown invocation capture event kind')
    def native(event,tool):
        require(text(event.get('provider')) and event.get('tool')==tool and sha(event.get('native_request_sha256')),'Native creation or dispatch requires the actually observed provider/tool/request fingerprint')
        actor=event.get('actor');require(isinstance(actor,dict) and set(actor)=={'id','context_id'} and all(text(value) for value in actor.values()),'An actual actor and context identity are required')
        require(all(key in event for key in ['tool_call_id','model','tokens','cost']),'Unexposed model, native call IDs, tokens and cost must be explicit')
        for key in ['tool_call_id','model']:require(event[key] is None or text(event[key]),'Unexposed or observed native identity metadata must remain explicit')
        for key in ['tokens','cost']:require(event[key] is None or type(event[key]) in {int,float} and math.isfinite(event[key]) and event[key]>=0,'Native accounting cannot be invented, negative or boolean')
        return actor
    creations=[event for event in observed if event['kind']=='actor-created'];dispatches=[event for event in observed if event['kind']=='actor-dispatched'];returns=[event for event in observed if event['kind']=='actor-returned']
    require(len(creations)==len(dispatches)==len(returns)==3,'Exactly three distinct actual source-backed invocations are required')
    for event in creations:native(event,'collaboration.spawn_agent')
    for event in dispatches:
        native(event,'collaboration.followup_task');require(event.get('mechanism')=='source-backed-context' and event.get('native_skill_called') is False,'The observation must not invent a native Skill call')
    require(len({event['actor']['id'] for event in creations})==len({event['actor']['context_id'] for event in creations})==3,'Repeated package occurrences require isolated actual invocation contexts')
    qualification=trusted_capture.get('qualification');require(isinstance(qualification,dict),'The finite actual observation budget is required')
    require(qualification.get('limits')=={'contexts':6,'requests':12,'wall_seconds':1800,'cleanup_seconds':60},'Actual invocation limits cannot increase or lose cleanup reserve')
    previous=qualification.get('previous_attempts',[]);require(isinstance(previous,list) and len(previous)<=1,'Only one concrete repaired-source qualification rerun is within the approved reserve')
    contexts=3;requests=6;all_contexts=[event['actor']['context_id'] for event in creations];all_actors=[event['actor']['id'] for event in creations]
    for prior in previous:
        require(isinstance(prior,dict) and prior.get('result')=='fail' and text(prior.get('failure_signature')),'An earlier probe requires a retained concrete failure')
        old=prior.get('capture');require(isinstance(old,dict) and isinstance(old.get('events'),list),'A repaired-source rerun must preserve earlier observations')
        if old.get('source_snapshot')==sources:
            repair=prior.get('repair');require(isinstance(repair,dict) and relative(repair.get('path')) and text(repair.get('reason')) and sha(repair.get('before_sha256')) and sha(repair.get('after_sha256')) and repair['before_sha256']!=repair['after_sha256'],'Unchanged core source requires an explicit concrete installed-resource repair')
            old_resource=old.get('resources',{}).get(repair['path'],{});new_resource=trusted_capture.get('resources',{}).get(repair['path'],{})
            require(old_resource.get('sha256')==repair['before_sha256'] and new_resource.get('sha256')==repair['after_sha256'],'The retained repaired resource digests differ')
        prior_creations=[event for event in old['events'] if event.get('kind')=='actor-created'];prior_dispatches=[event for event in old['events'] if event.get('kind')=='actor-dispatched']
        for event in prior_creations:native(event,'collaboration.spawn_agent')
        for event in prior_dispatches:native(event,'collaboration.followup_task')
        contexts+=len(prior_creations);requests+=len(prior_creations)+len(prior_dispatches);all_contexts.extend(event['actor']['context_id'] for event in prior_creations);all_actors.extend(event['actor']['id'] for event in prior_creations)
    require(len(set(all_contexts))==len(set(all_actors))==contexts,'A repaired-source rerun retains the original distinct native creation/context identities')
    consumed=qualification.get('consumed');require(isinstance(consumed,dict) and consumed.get('contexts')==contexts<=6 and consumed.get('requests')==requests<=12 and type(consumed.get('wall_seconds')) in {int,float} and 0<=consumed['wall_seconds']<=1800,'Observed qualification use must include retained failures and stay within the finite plan')
    raw=trusted_capture.get('resources');require(isinstance(raw,dict) and raw,'Actual installed resource bytes are required for independent nonce checks')
    resources={}
    for path,record in raw.items():
        require(relative(path) and isinstance(record,dict) and record.get('encoding')=='base64' and isinstance(record.get('data'),str) and sha(record.get('sha256')),'Installed resources require portable identities and exact encoded bytes')
        try:content=base64.b64decode(record['data'],validate=True)
        except (ValueError,TypeError) as error:raise ValueError('Malformed captured resource bytes') from error
        require(hashlib.sha256(content).hexdigest()==record['sha256'],'Captured installed resource bytes changed');resources[path]=content
    protected=trusted_capture.get('protected_inventory_before');protected_after=trusted_capture.get('protected_inventory_after')
    require(isinstance(protected,dict) and protected and all(relative(path) and sha(value) for path,value in protected.items()) and protected_after==protected,'The final protected fixture and installed operation/plugin inventory must equal the captured initial bytes')
    def protected_sum(path,value):return any((key==path or key.endswith('/'+path)) and fingerprint==value for key,fingerprint in protected.items())
    require(any(Path(path).name=='source.py' for path in protected),'The controlled source fixture must remain in the protected inventory')
    for path,record in raw.items():require(protected_sum(path,record['sha256']),'The initial and final protected inventory must bind every captured installed plugin resource')
    manifest_record=trusted_capture.get('operation_manifest')
    require(isinstance(manifest_record,dict) and manifest_record.get('encoding')=='base64' and isinstance(manifest_record.get('data'),str) and sha(manifest_record.get('sha256')),'The actual owned operation manifest bytes are required')
    try:
        manifest_bytes=base64.b64decode(manifest_record['data'],validate=True);manifest=json.loads(manifest_bytes)
    except (ValueError,TypeError,UnicodeDecodeError) as error:raise ValueError('Malformed captured operation manifest bytes') from error
    require(hashlib.sha256(manifest_bytes).hexdigest()==manifest_record['sha256'] and protected_sum('references/plugin-bindings.json',manifest_record['sha256']),'The actual manifest bytes differ from the protected installed operation')
    require(isinstance(manifest,dict) and manifest.get('format')=='skill-tree-plugin-bindings' and manifest.get('schema')==1 and isinstance(manifest.get('owned_resources'),dict) and manifest['owned_resources'],'The captured owned operation manifest is unsupported')
    for path,value in manifest['owned_resources'].items():require(relative(path) and sha(value) and protected_sum(path,value),'The actual manifest resources differ from the protected installed operation')
    for path in PLUGIN_INVOCATION_SOURCES:require(manifest['owned_resources'].get('scripts/'+Path(path).name)==sources[path],'The actual installed operation helpers differ from the qualified current invocation source')
    observations=[event for event in observed if event['kind']=='chain-observed']
    def label(name):
        found=[event for event in observations if event.get('label')==name];require(len(found)==1,'A unique '+name+' chain observation is required');return found[0]
    start=label('start');b_returned=label('b-returned');complete=label('chain-complete');final=label('final');require(observations[-1] is final and start['sequence']<b_returned['sequence']<complete['sequence']<final['sequence'],'Original, returned, complete and final chain observations retain actual order')
    chain=final.get('chain');require(isinstance(chain,dict),'The actual final HC record is required');configuration=chain.get('configuration',{});rows=configuration.get('bindings');packages=configuration.get('packages')
    require(isinstance(rows,list) and len(rows)==3 and all(isinstance(row,dict) for row in rows) and isinstance(packages,dict),'The actual frozen ordered three-occurrence configuration is required')
    row_ids=[row.get('id') for row in rows];require(all(text(value) for value in row_ids) and len(set(row_ids))==3 and rows[0].get('plugin_id')==rows[2].get('plugin_id')!=rows[1].get('plugin_id'),'A-to-B-to-A requires distinct occurrence IDs without collapsing repeated packages')
    require(all(row.get('enabled') is True for row in rows),'The observed three-occurrence qualification chain requires three enabled occurrences')
    policy=configuration.get('execution_policy');require(isinstance(policy,dict) and set(policy)=={'allowed_tools','allowed_actions'},'The actual core execution policy must be frozen separately from plugin parameters')
    for key in ['allowed_tools','allowed_actions']:require(isinstance(policy[key],list) and policy[key] and all(text(value) for value in policy[key]) and len(set(policy[key]))==len(policy[key]),'The bounded execution policy requires explicit distinct tool/action names')
    require(sha(configuration.get('binding_configuration_digest')),'The binding configuration digest must remain distinct from the core policy digest')
    policy_program="""const fs=require('node:fs'),crypto=require('node:crypto'),value=JSON.parse(fs.readFileSync(0,'utf8'));
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
process.stdout.write(crypto.createHash('sha256').update(canonical(value)).digest('hex'));"""
    policy_run=subprocess.run(['node','-e',policy_program],input=json.dumps({'binding_configuration_digest':configuration['binding_configuration_digest'],'execution_policy':policy},ensure_ascii=True),capture_output=True,text=True,timeout=10)
    require(policy_run.returncode==0 and policy_run.stdout==configuration.get('configuration_digest'),'The frozen core policy differs from the owned Node configuration identity')
    compile_program="""const fs=require('node:fs'),crypto=require('node:crypto'),c=require(process.argv[1]),b=require(process.argv[2]),r=require(process.argv[3]),p=JSON.parse(fs.readFileSync(0,'utf8')),m=p.manifest;
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const hash=v=>crypto.createHash('sha256').update(canonical(v)).digest('hex');
if(m.identity!==r.seal(m).identity)throw Error('The captured owned manifest seal differs');
const catalog=c.createCatalog(m.operations),compiled=b.compileBindings(m.definitions,{packages:m.packages,catalog,parameterDefaults:m.parameter_defaults,runOverrides:p.configuration.run_overrides||{}});
const expected={configuration_digest:hash({binding_configuration_digest:compiled.configuration_digest,execution_policy:p.configuration.execution_policy}),binding_configuration_digest:compiled.configuration_digest,execution_policy:p.configuration.execution_policy,bindings:compiled.bindings,definitions:m.definitions,packages:m.packages,parameter_defaults:m.parameter_defaults,run_overrides:p.configuration.run_overrides||{},manifest_identity:m.identity,operation:m.operation};
if(canonical(expected)!==canonical(p.configuration))throw Error('The frozen configuration differs from the actual owned definitions and explicit overrides');
const base=b.compileBindings(m.definitions,{packages:m.packages,catalog,parameterDefaults:m.parameter_defaults,runOverrides:{}});
if(canonical(base.bindings)!==canonical(m.bindings)||base.configuration_digest!==m.configuration_digest)throw Error('The captured manifest compiled projection differs');
process.stdout.write('valid');"""
    compiled=subprocess.run(['node','-e',compile_program,str(CORE/'lib/plugin-composition.js'),str(CORE/'lib/plugin-bindings.js'),str(CORE/'lib/plugin-registry.js')],input=json.dumps({'manifest':manifest,'configuration':configuration},ensure_ascii=True,allow_nan=False),capture_output=True,text=True,timeout=10)
    require(compiled.returncode==0 and compiled.stdout=='valid','The captured frozen configuration cannot be independently reproduced from the actual owned operation manifest')

    require(chain.get('state')=='complete' and chain.get('cursor')==3 and chain.get('prepared_attempt_id') is None,'A required unresolved or original attempt cannot complete the chain')
    require(len(chain.get('attempts',{}))==3 and len(chain.get('stages',[]))==3,'One original actual attempt per qualified occurrence is required')
    invocations={};union=set()
    for plugin,package in packages.items():
        require(text(plugin) and isinstance(package,dict) and text(package.get('revision')) and sha(package.get('content_digest')) and relative(package.get('entry')),'The frozen installed package identity is incomplete')
        inventory=package.get('resources',package.get('files'));require(isinstance(inventory,dict) and inventory and package['entry'] in inventory,'The installed entry requires the exact resource closure')
        for path,fingerprint in inventory.items():require(path in resources and fingerprint==hashlib.sha256(resources[path]).hexdigest(),'The installed resource closure differs from the frozen actual package');union.add(path)
    require(set(resources)==union,'The capture cannot substitute unrelated or omitted resources for the declared package closure')
    class SnapshotStore:
        def __init__(self,root):self.root=root;self.base=root/'.skill-tree'
        def owned(self,relative):return self.root/relative
    with tempfile.TemporaryDirectory(prefix='skill-tree-plugin-observation-') as temporary:
        store=SnapshotStore(Path(temporary));directory=store.base/'invocations';directory.mkdir(parents=True)
        previous_frame=None
        for event in observations:
            current=event.get('chain');require(isinstance(current,dict) and current.get('id')==chain['id'],'Captured chain identity cannot change')
            require(all(current.get(key)==chain.get(key) for key in ['configuration','event','initial_context','mode','authority','executor','execution_snapshot','request_id','start_digest','initial_lineage']),'A captured operation, scope, authority or frozen configuration changed')
            frozen=current.get('execution_snapshot');require(isinstance(frozen,dict) and all(frozen.get(path)==value for path,value in sources.items()),'Actual invocation artifacts must bind current execution source hashes')
            require(frozen.get('operation-manifest')==manifest_record['sha256'],'The invocation execution snapshot differs from the actual installed operation manifest bytes')
            require(current.get('chain_hash')==engine.digest({key:value for key,value in current.items() if key!='chain_hash'}),'Captured HC checksum differs')
            path=directory/(current['id'].lower()+'.json');path.write_text(json.dumps(current,ensure_ascii=True))
            try:
                require(engine.read(store,current['id'])==current,'Captured HC data differs from the supported ledger')
                if event is final:require(engine.next_action(store,current['id'])['action']=='complete','Final current engine state remains unresolved')
            except (engine.InvocationError,KeyError,TypeError) as error:raise ValueError('Captured invocation state is invalid: '+str(error)) from error
            if previous_frame:
                require(current['cursor']>=previous_frame['cursor'] and current['history'][:len(previous_frame['history'])]==previous_frame['history'],'Later stage edits cannot rewrite earlier chain progress/history')
                for original,attempt in previous_frame['attempts'].items():
                    if any(stage.get('status')=='complete' and original in stage.get('attempt_ids',[]) for stage in previous_frame['stages']):require(current['attempts'].get(original)==attempt,'Completed-prefix input or result history changed')
            previous_frame=current
    def node_identity(payload,row,configuration_digest):
        program="""const fs=require('node:fs'),crypto=require('node:crypto'),p=require(process.argv[1]),packet=JSON.parse(fs.readFileSync(0,'utf8')),value=packet.delivery;
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const result=p.resolveParameters({run:{values:value.parameters,instructions:value.extra_instructions}});
function stable(v){if(Array.isArray(v))return v.map(stable);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));return v;}
const hash=v=>crypto.createHash('sha256').update(JSON.stringify(stable(v))).digest('hex'),row=packet.row;
const identity={binding_id:row.id,boundary_id:row.location?.boundary_id||row.operation+':'+row.anchor,operation:value.event.operation,anchor:value.event.anchor,event_id:value.event.id,attempt_id:value.attempt_id};
const inputs={configuration_digest:packet.configuration_digest,parameters:value.parameters,extra_instructions:value.extra_instructions};
const dispatch_identity={...identity,binding_anchor:row.anchor,delivery_key:hash(identity),input_digest:hash({context:value.context,inputs,binding:row})};
process.stdout.write(JSON.stringify({delivery_digest:crypto.createHash('sha256').update(canonical(value)).digest('hex'),resolved_parameter_digest:result.digest,dispatch_identity}));"""
        run=subprocess.run(['node','-e',program,str(CORE/'lib/plugin-parameters.js')],input=json.dumps({'delivery':payload,'row':row,'configuration_digest':configuration_digest},ensure_ascii=True,allow_nan=False),capture_output=True,text=True,timeout=10)
        require(run.returncode==0,'The owned JS identity oracle failed');return json.loads(run.stdout)
    for index,row in enumerate(rows):
        stage=chain['stages'][index];require(stage.get('index')==index and stage.get('binding_id')==row['id'] and stage.get('status')=='complete' and len(stage.get('attempt_ids',[]))==1,'Every occurrence must retain its distinct completed original attempt')
        original=stage['attempt_ids'][0];attempt=chain['attempts'].get(original,{});require(attempt.get('id')==original and attempt.get('index')==index and attempt.get('binding_id')==row['id'] and attempt.get('status')=='returned','A failed, unknown or substituted original invocation cannot satisfy an occurrence')
        inp=attempt.get('input');who=attempt.get('actor');require(isinstance(inp,dict) and attempt.get('input_digest')==engine.digest(inp),'The original public sealed input changed')
        require(inp.get('chain_id')==chain['id'] and inp.get('attempt_id')==original and inp.get('index')==index and inp.get('binding_id')==row['id'] and inp.get('event')==chain['event'] and inp.get('configuration_digest')==configuration['configuration_digest'] and inp.get('mode')==chain['mode'] and inp.get('epoch')==chain.get('epoch') and inp.get('execution_snapshot_digest')==engine.digest(chain['execution_snapshot']) and inp.get('authority_digest')==engine.digest(chain['authority']),'The original invocation input changed core operation, mode, authority or occurrence identity')
        require(inp.get('authority')==chain['authority'] and inp.get('execution_policy')==policy,'The original public input must seal the complete actual grant and allowed execution policy')
        scope_sources=inp.get('scope_source_snapshot');require(isinstance(scope_sources,dict) and scope_sources and all(relative(path) and sha(value) and protected.get(path)==value for path,value in scope_sources.items()),'The original bounded task source snapshot differs from the independently captured protected project bytes')
        package=packages[row['plugin_id']];require(inp.get('package_identity')=={'plugin_id':row['plugin_id'],**package},'The actual loaded package identity differs from the pinned occurrence')
        effective=row.get('effective');require(isinstance(effective,dict) and not effective.get('secretReferences') and inp.get('parameters')==effective.get('values') and inp.get('extra_instructions')==effective.get('instructions') and inp.get('parameter_digest')==effective.get('digest'),'The public reference-level values or extra instructions were dropped or replaced')
        current_lineage=[*chain.get('initial_lineage',[]),{'binding_id':row['id'],'boundary_id':chain['event'].get('boundary_id',chain['event']['operation']+':'+chain['event']['anchor'])}];require(inp.get('lineage')==current_lineage,'Active lineage cannot deduplicate a separate occurrence or omit the current occurrence')
        created=[event for event in creations if event.get('binding_id')==row['id'] and event.get('actor')==who];dispatched=[event for event in dispatches if event.get('binding_id')==row['id'] and event.get('attempt_id')==original];returned=[event for event in returns if event.get('binding_id')==row['id'] and event.get('attempt_id')==original]
        require(len(created)==len(dispatched)==len(returned)==1,'Every occurrence requires one actual creation, exact dispatch and returned result')
        created,dispatched,returned=created[0],dispatched[0],returned[0];require(created['sequence']<dispatched['sequence']<returned['sequence']<complete['sequence'],'Invocation evidence must precede chain completion')
        require(dispatched.get('creation_event_id')==created['id'] and returned.get('creation_event_id')==created['id'] and returned.get('dispatch_event_id')==dispatched['id'] and dispatched.get('actor')==returned.get('actor')==who and who['id']!=chain['executor']['id'] and who['context_id']!=chain['executor']['context_id'],'Actual producer identities cannot be substituted or reused as executor')
        require(dispatched.get('input')==inp and dispatched.get('input_digest')==attempt['input_digest']==returned.get('input_digest'),'The actually delivered public envelope differs from the original sealed input')
        delivery=dispatched.get('delivery');require(isinstance(delivery,dict),'Actual resolved nonsecret delivery bytes are required')
        require(delivery.get('mechanism')=='source-backed-context' and delivery.get('provider')=='codex' and all(delivery.get(key)==inp.get(key) for key in ['chain_id','attempt_id','binding_id','event','context']) and delivery.get('input_digest')==attempt['input_digest'],'The source-backed host payload changed the actual operation or scope')
        require(delivery.get('mode')==chain['mode'] and delivery.get('authority')==chain['authority'] and delivery.get('authority_digest')==inp['authority_digest'] and delivery.get('allowed_tools')==policy['allowed_tools'] and delivery.get('allowed_actions')==policy['allowed_actions'],'The actual actor did not receive the frozen mode, complete grant and bounded tool/action policy')
        require(delivery.get('scope_source_snapshot')==scope_sources,'The actual actor did not receive the original sealed bounded project source snapshot')
        expected_plugin={'plugin_id':row['plugin_id'],'revision':package['revision'],'content_digest':package['content_digest'],'entry':package['entry'],'resource_digests':package.get('resources',package.get('files'))};require(delivery.get('plugin')==expected_plugin,'The delivered installed entry or resource inventory differs')
        require(delivery.get('parameters')==effective['values'] and delivery.get('extra_instructions')==effective['instructions'],'The nonsecret actual JSON values or extra instruction text were not forwarded')
        js=node_identity(delivery,row,configuration['configuration_digest']);require(js['delivery_digest']==dispatched.get('delivery_digest')==attempt.get('delivery_digest')==returned.get('delivery_digest') and js['resolved_parameter_digest']==dispatched.get('resolved_parameter_digest')==attempt.get('resolved_parameter_digest')==inp['parameter_digest'],'The actual JS delivery/parameter digest differs; Python JSON formatting supplies no substitute')
        require(delivery.get('dispatch_identity')==attempt.get('dispatch_identity')==js['dispatch_identity'],'Actual binding/event/HI dispatch identity or opaque binding digests differ')
        require(js['dispatch_identity']['operation']==row['operation'] and ('boundary_id' not in chain['event'] or chain['event']['boundary_id']==js['dispatch_identity']['boundary_id']),'The actual dispatch descriptor cannot redirect the frozen owned boundary')
        if 'dispatch_identity' in dispatched:require(dispatched['dispatch_identity']==js['dispatch_identity'],'The captured dispatch descriptor differs from the actual delivery')
        result=returned.get('result');require(isinstance(result,dict) and result==attempt.get('result') and result.get('input_digest')==attempt['input_digest'] and result.get('delivery_digest')==attempt['delivery_digest'],'The observed raw returned JSON must match the original ledger outcome')
        require(result.get('status')==('findings' if index==1 else 'passed') and not result.get('real_human') and result.get('mechanism','source-backed-context')=='source-backed-context','The actual returned outcome cannot invent success, native execution or human approval')
        for key,kind,origin in [('creation_evidence','host-agent-created',created),('invoke_evidence','host-invoked',dispatched),('result_evidence','host-result',returned)]:
            evidence=attempt.get(key);require(isinstance(evidence,dict) and evidence.get('kind')==kind and evidence.get('reference')==origin['id'] and evidence.get('actor_id')==who['id'] and evidence.get('actor_context_id')==who['context_id'] and text(evidence.get('provider')) and text(evidence.get('tool')),'Original ledger evidence must match the actual external producer event')
            require(evidence.get('tool')==(created['tool'] if key=='creation_evidence' else dispatched['tool']),'The producer evidence tool differs from the actual native call')
            require(evidence.get('provider')==created['provider']==dispatched['provider'],'The recorded invocation provider differs from the actual original host creation and dispatch')
            if key!='creation_evidence':require(evidence.get('mechanism')=='source-backed-context','Actual invocation evidence cannot claim an unsupported native mechanism')
        marker_path=(Path(package['entry']).parent/'marker.json').as_posix();require(marker_path in resources,'The controlled installed marker resource is missing')
        try:resource_marker=json.loads(resources[marker_path])['resource_marker']
        except (ValueError,KeyError,TypeError) as error:raise ValueError('Malformed controlled marker resource') from error
        markers=result.get('evidence');require(isinstance(markers,dict) and markers.get('resource_marker')==resource_marker and markers.get('parameter_marker')==delivery['parameters'].get('marker') and markers.get('extra_instruction_marker')==delivery['extra_instructions'],'Actual parameter/resource/instruction nonces differ from independently expected values')
        transition=stage.get('accepted_transition');require(isinstance(transition,dict) and transition.get('before')==inp['context'] and transition.get('after')==stage.get('accepted_context') and isinstance(transition.get('receipt'),dict) and transition['receipt'].get('before')==engine.digest(transition['before']) and transition['receipt'].get('after')==engine.digest(transition['after']),'Accepted stage context transitions must retain original before/after evidence')
        if index!=1:require(transition['receipt'].get('kind')=='no-change' and transition['before']==transition['after'] and transition['receipt'].get('reference')==returned['id'],'A passed editor cannot silently apply another core context transition')
        invocations[index]={'created':created,'dispatched':dispatched,'returned':returned,'attempt':attempt,'stage':stage,'markers':markers}
    require(invocations[0]['returned']['sequence']<invocations[1]['created']['sequence'] and invocations[1]['returned']['sequence']<invocations[2]['created']['sequence'],'Ordered occurrences execute sequentially rather than in parallel or sorted by package identity')
    incorporation=[event for event in observed if event['kind']=='core-incorporation'];confirmation=[event for event in observed if event['kind']=='core-confirmation'];require(len(incorporation)==len(confirmation)==1,'Actual ordinary core incorporation and final confirmation artifacts are required')
    incorporation,confirmation=incorporation[0],confirmation[0]
    require(invocations[1]['returned']['sequence']<b_returned['sequence']<incorporation['sequence']<invocations[2]['dispatched']['sequence']<complete['sequence']<confirmation['sequence']<final['sequence'],'B incorporation precedes A2, while final task confirmation follows the completed chain')
    for event in [incorporation,confirmation]:
        owner=indexed.get(event.get('owner_event_id'),{});require(owner.get('kind')=='scripted-owner-input' and owner.get('real_human') is False and owner['sequence']<event['sequence'] and owner.get('purpose')==('incorporation' if event is incorporation else 'confirmation'),'Core test inputs must be explicitly scripted owner submissions in the actual order')
    require(incorporation.get('attempt_id')==invocations[1]['attempt']['id'] and incorporation.get('binding_id')==rows[1]['id'],'Core incorporation belongs to another returned occurrence')
    before_future=incorporation.get('future_before');after_future=incorporation.get('future_after');require(text(before_future) and text(after_future) and before_future!=after_future and confirmation.get('future')==after_future,'The actual incorporated task bytes must change and remain current through final acceptance')
    before_tasks=wf.parse(before_future);after_tasks=wf.parse(after_future);task_ids=chain['initial_context'].get('task_ids');require(chain['initial_context'].get('kind')=='task' and isinstance(task_ids,list) and len(task_ids)==1,'The actual qualification uses one visible stable T-task')
    tid=task_ids[0];before_task=wf.resolve(before_tasks,[tid],'Prioritized Next Changes')[0];after_task=wf.resolve(after_tasks,[tid],'Prioritized Next Changes')[0]
    for index,invocation in invocations.items():
        selected_task=after_task if index==2 else before_task;declared={path for check in wf.check_specs(selected_task) for path in check['sources']};declared.update(invocation['attempt']['input']['context'].get('source_paths',[]))
        declared={path for path in declared if not any(path==prefix or path.startswith(prefix+'/') for prefix in PLUGIN_MUTABLE_WORKFLOW_PATHS)}
        require(set(invocation['attempt']['input']['scope_source_snapshot'])==declared,'The original bounded source snapshot omits or substitutes actual task check sources or explicit context paths')
    require([(task['id'],task['queue']) for task in before_tasks]==[(task['id'],task['queue']) for task in after_tasks] and wf.clarification_identity(before_task)==wf.clarification_identity(after_task),'Incorporation cannot replace task identity, provenance or queue membership')
    require(all(old['body']==new['body'] for old,new in zip(before_tasks,after_tasks) if old['id']!=tid),'Core incorporation changed an unrelated task')
    def actual_context(ctx,task,future):
        require(isinstance(ctx,dict) and ctx.get('kind')=='task' and ctx.get('task_ids')==[tid] and ctx.get('id')==chain['initial_context']['id'] and ctx.get('content_fingerprint')==hashlib.sha256(task['body'].encode()).hexdigest() and ctx.get('semantic_fingerprint')==wf.clarification_fingerprints(wf.clarification_baselines([task]))[tid],'Actual task context fingerprints differ from captured guarded task bytes')
        if 'source_hash' in ctx:require(ctx['source_hash']==hashlib.sha256(future.encode()).hexdigest(),'The delivered source hash differs from actual queue bytes')
        for key in ['body','task_body']:
            if key in ctx:require(ctx[key]==task['body'],'The delivered task body differs from the accepted current task')
        if 'task_body' in ctx.get('data',{}):require(ctx['data']['task_body']==task['body'],'The delivered task body differs from the accepted current task')
    initial=chain['initial_context'];current=chain['context'];actual_context(initial,before_task,before_future);actual_context(current,after_task,after_future)
    require(invocations[0]['attempt']['input']['context']==invocations[1]['attempt']['input']['context']==initial and invocations[2]['attempt']['input']['context']==current and initial!=current,'A1 history and A2 current accepted context must remain separate')
    require(invocations[0]['stage']['accepted_context']==initial and invocations[1]['stage']['accepted_context']==invocations[2]['stage']['accepted_context']==current,'Only the guarded B incorporation advances the accepted task context')
    require(incorporation.get('before_context')==initial and incorporation.get('after_context')==current and incorporation.get('receipt')==invocations[1]['stage']['accepted_transition']['receipt'],'Actual core revision receipt differs from the accepted B transition')
    before_session=incorporation.get('session_before');after_session=incorporation.get('session_after');final_session=confirmation.get('session');require(all(isinstance(value,dict) for value in [before_session,after_session,final_session]),'Actual clarification revision and final session artifacts are required')
    require(before_session.get('id')==after_session.get('id')==final_session.get('id') and all(value.get('task_ids')==[tid] and value.get('decision_mode','manual')=='manual' for value in [before_session,after_session,final_session]),'The controlled Manual owner/session scope cannot change')
    require(after_session.get('state')!='complete' and final_session.get('state')=='complete','Incorporation is distinct from final confirmation and cannot deadlock the last editor')
    receipt=incorporation['receipt'];revision=[value for value in after_session.get('task_revisions',[]) if value.get('id')==receipt.get('task_revision_id')];require(len(revision)==1 and receipt.get('session_id')==after_session['id'] and receipt.get('kind')=='core-incorporation','The accepted B change requires the actual ordinary clarification task revision')
    require(receipt.get('source_before')==revision[0].get('source_before')==hashlib.sha256(before_future.encode()).hexdigest() and receipt.get('source_after')==revision[0].get('source_after')==hashlib.sha256(after_future.encode()).hexdigest() and tid in revision[0].get('task_ids',[]) and 'goal' in revision[0].get('changed_fields',{}).get(tid,[]),'Core revision evidence does not bind actual before/after task bytes')
    owner=indexed[incorporation['owner_event_id']];require(any(answer.get('valid') and answer.get('answer')==owner.get('answer') and answer.get('evidence')==owner.get('evidence') for answer in before_session.get('answers',{}).values()),'B incorporation lacks the actual scripted submitted answer')
    final_owner=indexed[confirmation['owner_event_id']];confirm=final_session.get('confirmation');require(isinstance(confirm,dict) and confirm.get('evidence')==final_owner.get('evidence') and confirm.get('task_ids')==[tid] and confirm.get('semantic_fingerprints')==final_session.get('semantic_fingerprints'),'Final fixture confirmation must bind the current exact task and explicit scripted input')
    require(final_session.get('baselines')==wf.clarification_baselines([after_task]) and final_session.get('semantic_fingerprints')==wf.clarification_fingerprints(wf.clarification_baselines([after_task])),'Final core acceptance belongs to stale task semantics')
    for record in [before_session,after_session,final_session]:
        raw_record={key:value for key,value in record.items() if key!='session_hash'};require(record.get('session_hash')==hashlib.sha256(wf.dump(raw_record).encode()).hexdigest(),'Captured clarification artifact checksum differs')
    with tempfile.TemporaryDirectory(prefix='skill-tree-plugin-confirmation-') as temporary:
        store=wf.Store(Path(temporary),allow_unselected=True,neutral=True);store.future.parent.mkdir(parents=True);store.future.write_text(after_future);target=wf.clarification_path(store,final_session['id']);target.parent.mkdir(parents=True);target.write_text(wf.dump({key:value for key,value in final_session.items() if key!='session_hash'}))
        try:require(wf.clarification_acceptance_current(store,wf.clarification_read(store,final_session['id'])),'Final core acceptance is no longer current')
        except (wf.WorkflowError,KeyError,TypeError) as error:raise ValueError('Final captured core acceptance is invalid: '+str(error)) from error
    def marker(task):
        values=re.findall(r'Context marker: ([a-zA-Z0-9-]+)\.',task['body']);require(len(values)==1,'The controlled task marker must be independently identifiable');return values[0]
    old_marker,new_marker=marker(before_task),marker(after_task);require(old_marker!=new_marker,'B must incorporate an actual bounded task change')
    proposal=invocations[1]['attempt']['result'].get('proposal');require(isinstance(proposal,dict) and proposal.get('task_id')==tid and proposal.get('context_marker')==new_marker,'The actual B proposal must match the incorporated task addition')
    require(invocations[0]['markers'].get('context_marker')==invocations[1]['markers'].get('context_marker')==old_marker and invocations[2]['markers'].get('context_marker')==new_marker,'The final repeated occurrence did not observe B\'s incorporated current task marker')
    return {'passed':True,'occurrences':3,'actual_contexts':3,'scope':'Bounded source-backed Codex invocation observations with separately trusted native capture; scripted fixture-owner inputs are not real-human approval, native Skill invocation or comparative plugin efficacy.'}

def validate_plugin_invocation_report(report,trusted_capture=None):
    try:return _validate_plugin_invocation_report(report,trusted_capture)
    except (KeyError,TypeError,IndexError,AttributeError,OverflowError,UnicodeError,OSError) as error:raise ValueError('Malformed plugin invocation report or external native capture') from error


MANAGER_PHASES = (
    'p-add', 'p-preview', 'p-apply', 'p-move', 'p-move-preview', 'p-move-apply', 'p-final',
    'n-move', 'n-preview', 'n-cancel', 'grade',
)
MANAGER_GRADES = {
    'positive-preview': 'p-preview', 'positive-confirmation': 'p-apply',
    'positive-reorder': 'p-move-preview', 'negative-cancellation': 'n-cancel',
    'execution-boundary': 'p-final',
}
MANAGER_OPERATION = 'skill-tree-process-future-pending'
MANAGER_POINT = MANAGER_OPERATION + ':after'
MANAGER_REGISTRY = '.skill-tree/installation/plugins.json'
MANAGER_PACKAGE = '.agents/skills/skill-tree-plugins'
MANAGER_LIMITS = {'contexts': 3, 'spawn_or_follow_up_requests': 12, 'wall_seconds': 720, 'cleanup_seconds': 60}
MANAGER_SOURCE_FILES = {
    'templates/operations.json', 'config/resource-map.json', 'common/scripts/plugin-manager.js',
    'lib/plugin-management.js', 'lib/plugin-lifecycle.js', 'lib/installation.js', 'scripts/agent-conformance.py',
    'skills/general/skill-tree-plugins/SKILL.md', 'skills/general/skill-tree-plugins/scripts/plugin-manager.js',
}


def _manager_hash(data):
    return hashlib.sha256(data).hexdigest()


def _manager_json(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode()


def _manager_sha(value):
    return isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value) is not None


def _manager_require(condition, message):
    if not condition:
        raise ValueError(message)


def _manager_bytes(record, *, portable=False):
    import base64
    data = base64.b64decode(record['base64'], validate=True)
    _manager_require(record['sha256'] == _manager_hash(data), 'Manager capture bytes changed')
    source = record.get('source_sha256', record['sha256'])
    _manager_require(_manager_sha(source) and (source == record['sha256'] or (
        portable and record.get('normalization') == 'fixture-path-redaction')),
        'Manager capture normalization is not attributable')
    return data


def _manager_registry(snapshot):
    raw = _manager_bytes(snapshot['registry'])
    _manager_require(snapshot['files'][MANAGER_REGISTRY] == _manager_hash(raw), 'Registry bytes differ from fixture inventory')
    registry = json.loads(raw)
    _manager_require(registry['format'] == 'skill-tree-plugin-registry' and registry['schema'] == 1,
                     'The fixture lacks an owned plugin registry')
    _manager_require(not any(path == '.git' or path.startswith((
        '.git/', '.skill-tree/documents/', '.skill-tree/invocations/', '.skill-tree/clarifications/',
        '.skill-tree/decisions/', '.skill-tree/history/runs/', '.skill-tree/local/hook-locations/',
    )) for path in snapshot['files']), 'The management fixture created workflow or invocation state')
    return registry


def _manager_cli(command, before, after):
    expected_argv = ['node', '--require', '<fixture-network-guard>', MANAGER_PACKAGE + '/scripts/plugin-manager.js',
                     '--project-root', '<fixture-root>', '--input', '-']
    _manager_require(command['argv'] == expected_argv and command['exit_code'] == 0 and command['network_guard'] is True,
                     'The original guarded installed CLI did not complete successfully')
    request = json.loads(_manager_bytes(command['stdin']))
    result = json.loads(_manager_bytes(command['stdout']))
    _manager_bytes(command['stderr'])
    _manager_require(_manager_registry(before) and _manager_registry(after), 'The managed fixture registry is unavailable')
    return request, result


def _manager_check_preview(command, action, actor, expected_rows):
    _manager_require(command['before'] == command['after'], 'A manager preview changed the disposable project')
    request, result = _manager_cli(command, command['before'], command['after'])
    _manager_require(request == {'action': 'prepare', 'request': actor['request']} and request['request']['action'] == action,
                     'The trusted broker did not run the exact observed manager request')
    proposal = result['proposal']
    _manager_require(result['status'] == 'ready' and _manager_sha(proposal['digest']),
                     'The actual manager did not prepare an exact confirmation digest')
    _manager_require(proposal['preview'] == result['preview']
                     and proposal['mutation']['proposal']['bindings'] == expected_rows
                     and proposal['mutation']['proposal']['base_generation'] == _manager_registry(command['before'])['generation'],
                     'The rendered preview does not bind the exact prepared lifecycle configuration')
    preview = result['preview']['bindings']
    _manager_require([row['id'] for row in preview] == [row['id'] for row in expected_rows],
                     'The actual preview does not show the complete configured chain')
    for row, expected in zip(preview, expected_rows):
        _manager_require(all(row.get(field) == expected.get(field)
                             for field in ('plugin_id', 'operation', 'anchor', 'enabled', 'parameters', 'instructions', 'condition')),
                         'An occurrence value differs from the reviewed preview')
    return proposal


def _manager_check_apply(command, proposal, preview_actor, apply_actor, expected_rows, authority):
    before, after = command['before'], command['after']
    request, receipt = _manager_cli(command, before, after)
    approved = proposal['digest']
    _manager_require(authority['kind'] == 'scripted-fixture-owner-input' and authority['decision'] == 'approve'
                     and authority['proposal_digest'] == preview_actor['proposal_digest'] == apply_actor['proposal_digest'] == approved
                     and preview_actor['decision'] == 'awaiting-confirmation' and apply_actor['decision'] == 'apply'
                     and request == {'action': 'apply', 'proposal': proposal, 'confirmation': {'proposal_digest': approved}},
                     'The confirmation or applied proposal differs from the displayed fixture proposal')
    initial, final = _manager_registry(before), _manager_registry(after)
    _manager_require(final['generation'] == initial['generation'] + 1 and final['packages'] == initial['packages']
                     and final['bindings'] == expected_rows and isinstance(receipt, dict),
                     'The real registry does not match the confirmed ordered configuration')
    request_id = proposal['request_id']
    recorded = final['requests'][request_id]
    _manager_require(request_id not in initial['requests']
                     and {key: value for key, value in final['requests'].items() if key != request_id} == initial['requests']
                     and all(receipt.get(key) == value for key, value in recorded.items())
                     and recorded['generation'] == final['generation']
                     and recorded['proposal_digest'] == proposal['mutation']['proposal']['digest']
                     and recorded['action'] == 'configured' and receipt['requires_profile_refresh'] is True,
                     'The installed manager result does not match the actual transaction receipt')
    delta = {path for path in set(before['files']) | set(after['files'])
             if before['files'].get(path) != after['files'].get(path)}
    _manager_require(MANAGER_REGISTRY in delta and all(path in {
        MANAGER_REGISTRY, '.skill-tree/installation/.last-plugin-transaction.json',
        '.skill-tree/installation/.plugin-backups',
    } or path.startswith('.skill-tree/installation/.plugin-backups/') for path in delta),
        'The confirmed configure action changed files outside the owned plugin transaction')


def _validate_plugin_management_report(report, capture):
    need = _manager_require
    need(report['schema'] == 1 and report['kind'] == 'plugin-management-agent-conformance'
         and capture is not report and capture['schema'] == 1 and capture['kind'] == 'plugin-management-native-capture',
         'A separate trusted management capture is required')
    need(report['capture_sha256'] == _manager_hash(_manager_json(capture)), 'Management report and trusted capture differ')
    source = capture['source_snapshot']
    need(source == report['source_snapshot'] and MANAGER_SOURCE_FILES <= set(source),
         'The exact owned management source snapshot is required')
    for relative, fingerprint in source.items():
        target = (CORE / relative).resolve()
        need(not Path(relative).is_absolute() and target.is_relative_to(CORE) and target.is_file()
             and digest(target) == fingerprint, 'Manager source changed or is not portable: ' + relative)
    frozen = capture['freeze']
    need(capture['freeze_sha256'] == _manager_hash(_manager_json(frozen))
         and frozen['source_snapshot'] == source and frozen['base_commit'] == capture['base_commit']
         and frozen['harness_sha256'] == capture['harness_sha256'] and frozen['guard_sha256'] == capture['guard_sha256']
         and frozen['oracle'] == capture['oracle'] and frozen['limits'] == MANAGER_LIMITS
         and tuple(frozen['phases']) == MANAGER_PHASES and _manager_sha(frozen['plan_sha256']),
         'The management fixture freeze differs from the admitted source, oracle or limits')
    need(_manager_hash(_manager_bytes(capture['network_guard'])) == frozen['guard_sha256'],
         'The original network and dispatch guard differs from the frozen helper')
    need(report['limitations'] == ['controller-brokered-cli', 'scripted-fixture-owner-input', 'codex-general-only',
                                   'no-plugin-dispatch', 'no-native-skill-qualification', 'unexposed-accounting'],
         'Manager observation scope and accounting limitations are required')

    events = capture['events']
    need(tuple(event['phase'] for event in events) == MANAGER_PHASES
         and report['event_ids'] == [event['id'] for event in events]
         and len(set(report['event_ids'])) == len(events), 'The exact predeclared host event sequence is required')
    identities, outputs = {}, {}
    for event in events:
        phase = event['phase']
        role = {'p': 'positive', 'n': 'cancel', 'g': 'grader'}[phase[0]]
        native = event['host']
        identity = (native['actor_id'], native['context_id'])
        need(native['provider'] == 'Codex collaboration'
             and native['tool'] == ('collaboration.followup_task' if role in identities else 'collaboration.spawn_agent')
             and all(isinstance(value, str) and value for value in (*identity, native['reference']))
             and all(field in native for field in ('tool_call_id', 'model', 'tokens', 'cost')),
             'Actual management actor identity or native capture evidence is missing')
        need(identities.setdefault(role, identity) == identity, 'An actual management context changed mid-scenario')
        _manager_bytes(event['prompt'], portable=True)
        prompt_hash = event['prompt'].get('source_sha256', event['prompt']['sha256'])
        need(prompt_hash.encode() in _manager_bytes(event['transport'], portable=True),
             'The actual host transport does not bind the exact sealed instruction file')
        output = _manager_bytes(event['reply'], portable=True).decode()
        outputs[phase] = json.loads(output)
    prompts = {event['phase']: _manager_bytes(event['prompt'], portable=True) for event in events}
    need(len({value[0] for value in identities.values()}) == len({value[1] for value in identities.values()}) == 3,
         'Positive, cancellation and grading contexts must be distinct')
    accounting = capture['accounting']
    need(accounting['contexts'] == 3 and accounting['spawn_or_follow_up_requests'] == len(events) <= 12
         and type(accounting['wall_seconds']) in {int, float} and 0 <= accounting['wall_seconds'] <= 720,
         'Management observations exceeded the frozen bound')
    cleanup = capture['cleanup']
    need(set(cleanup) <= set(identities) and all(
        isinstance(item, dict) and item['status'] in {'completed', 'not_found'} and item['reference']
        and (item['actor_id'], item['context_id']) == identities[role] for role, item in cleanup.items()),
        'Management lifecycle telemetry belongs to another actor or claims an unobserved result')

    steps, fixtures, authority = capture['steps'], capture['fixtures'], capture['authority']
    need(set(steps) == {'p-add', 'p-apply', 'p-move', 'p-move-apply', 'n-move'}
         and set(fixtures) == {'positive', 'cancel'} and set(authority) == {'p-apply', 'p-move-apply', 'n-cancel'},
         'Incomplete controlled manager cases or mutation evidence')
    oracle = capture['oracle']
    initial, added, reordered = (oracle[key] for key in ('initial', 'added', 'reordered'))
    need([row['id'] for row in initial] == ['editor-first', 'other-boundary', 'interview-middle']
         and [row['id'] for row in added] == ['editor-first', 'other-boundary', 'interview-middle', 'editor-last']
         and [row['id'] for row in reordered] == ['editor-last', 'other-boundary', 'editor-first', 'interview-middle']
         and added[:-1] == initial and reordered == [added[3], added[1], added[0], added[2]]
         and added[3]['plugin_id'] == initial[0]['plugin_id'] == 'fixture-editor'
         and initial[2]['plugin_id'] == 'fixture-interview'
         and added[3]['parameters'] == {'marker': 'after-interview', 'limit': 2},
         'The frozen oracle changed the intended A–B–A or same-point move')
    for name, rows in (('positive', initial), ('cancel', added)):
        fixture = fixtures[name]
        frozen_fixture = {key: fixture[key] for key in ('before', 'inventory', 'sources_before')}
        need(frozen['fixtures'][name] == _manager_hash(_manager_json(frozen_fixture)),
             'The initial installed fixture differs from its frozen byte inventory')
        state = _manager_registry(fixture['before'])
        need(state['bindings'] == rows and set(state['packages']) == {'fixture-editor', 'fixture-interview'}
             and fixture['before'] == fixture['inventory']['after'] == fixture['inventory']['before'],
             'The initial ordered fixture differs from the predeclared scenario')
        need(fixture['before']['files'][MANAGER_PACKAGE + '/scripts/plugin-manager.js']
             == source['common/scripts/plugin-manager.js']
             and _manager_sha(fixture['before']['files']['.skill-tree/installation/profile.json']),
             'The installed management entry point or owned profile was absent')
        inventory, _ = _manager_cli(fixture['inventory'], fixture['before'], fixture['before'])
        need(inventory == {'action': 'inventory'}, 'The fixture did not exercise raw installed inventory')
        need(fixture['sources_before'] == fixture['sources_after'], 'Original local fixture sources changed')
    need(steps['p-add']['before'] == fixtures['positive']['before']
         and steps['p-add']['after'] == steps['p-apply']['before']
         and steps['p-apply']['after'] == steps['p-move']['before']
         and steps['p-move']['after'] == steps['p-move-apply']['before']
         and steps['p-move-apply']['after'] == fixtures['positive']['after'],
         'Positive previews and actual applications do not form one exact state sequence')
    need(fixtures['cancel']['before'] == steps['n-move']['before'] == steps['n-move']['after'] == fixtures['cancel']['after'],
         'The cancelled move changed the independent project')
    first = _manager_check_preview(steps['p-add'], 'bind', outputs['p-add'], added)
    _manager_check_apply(steps['p-apply'], first, outputs['p-preview'], outputs['p-apply'], added, authority['p-apply'])
    second = _manager_check_preview(steps['p-move'], 'move', outputs['p-move'], reordered)
    _manager_check_apply(steps['p-move-apply'], second, outputs['p-move-preview'], outputs['p-move-apply'],
                         reordered, authority['p-move-apply'])
    cancelled = _manager_check_preview(steps['n-move'], 'move', outputs['n-move'], reordered)
    need(authority['n-cancel']['kind'] == 'scripted-fixture-owner-input'
         and authority['n-cancel']['decision'] == 'cancel' and outputs['n-cancel']['decision'] == 'cancel'
         and outputs['n-preview']['decision'] == 'awaiting-confirmation'
         and authority['n-cancel']['proposal_digest'] == outputs['n-preview']['proposal_digest']
         == outputs['n-cancel']['proposal_digest'] == cancelled['digest'],
         'The actual cancellation does not bind the displayed unexecuted proposal')
    for preview_phase, authority_phase, step in (
        ('p-preview', 'p-apply', 'p-add'), ('p-move-preview', 'p-move-apply', 'p-move'),
        ('n-preview', 'n-cancel', 'n-move'),
    ):
        actual = json.loads(_manager_bytes(steps[step]['stdout']))
        public = {'preview': actual['preview'], 'proposal_digest': actual['proposal']['digest']}
        need(_manager_json(public) in prompts[preview_phase] and _manager_json(authority[authority_phase]) in prompts[authority_phase],
             'The recorded host turns did not deliver the actual public preview and exact scripted decision')
    grades = outputs['grade']['assertions']
    need(set(grades) == set(MANAGER_GRADES)
         and all(grades[key] == {'status': 'observed', 'evidence': phase} for key, phase in MANAGER_GRADES.items())
         and isinstance(outputs['grade']['rationale'], str) and outputs['grade']['rationale'].strip()
         and report['grade'] == outputs['grade'], 'The actual independent grader did not accept the original management evidence')
    return {'passed': True, 'scenarios': 2, 'actual_contexts': 3,
            'scope': 'Observed source-backed General/Codex management with actual brokered CLI evidence and scripted fixture choices.'}


def validate_plugin_management_report(report, trusted_capture=None):
    try:
        return _validate_plugin_management_report(report, trusted_capture)
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError, UnicodeError, OSError) as error:
        raise ValueError('Malformed plugin management report or trusted capture') from error


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','grade','validate','clarification-prepare','clarification-observe','clarification-interrupt','clarification-grade','clarification-validate','core-decision-validate','plugin-invocation-validate','plugin-management-validate']);parser.add_argument('--scenario');parser.add_argument('--root',type=Path);parser.add_argument('--input',type=Path);parser.add_argument('--reply',type=Path);parser.add_argument('--observations',type=Path);parser.add_argument('--capture',type=Path);parser.add_argument('--phase');args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.scenario,args.root.resolve())
    elif args.command=='grade':result=grade(json.loads(args.input.read_text()),args.root.resolve(),args.reply.read_text())
    elif args.command=='validate':result=validate_report(json.loads(args.input.read_text()))
    elif args.command=='clarification-prepare':result=prepare_clarification(args.scenario,args.root.resolve())
    elif args.command=='clarification-observe':result=observe_clarification(json.loads(args.input.read_text()),args.root.resolve(),args.phase,args.reply.read_text())
    elif args.command=='clarification-interrupt':result=interrupt_clarification(json.loads(args.input.read_text()),args.root.resolve())
    elif args.command=='clarification-grade':result=grade_clarification(json.loads(args.input.read_text()),args.root.resolve(),json.loads(args.observations.read_text()))
    elif args.command=='core-decision-validate':result=validate_core_decision_report(json.loads(args.input.read_text()),json.loads(args.capture.read_text()) if args.capture else None)
    elif args.command=='plugin-invocation-validate':result=validate_plugin_invocation_report(json.loads(args.input.read_text()),json.loads(args.capture.read_text()) if args.capture else None)
    elif args.command=='plugin-management-validate':result=validate_plugin_management_report(json.loads(args.input.read_text()),json.loads(args.capture.read_text()) if args.capture else None)
    else:result=validate_clarification_report(json.loads(args.input.read_text()))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
