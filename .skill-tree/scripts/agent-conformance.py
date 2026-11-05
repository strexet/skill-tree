#!/usr/bin/env python3
"""Prepare isolated agent scenarios and grade observable workflow artifacts."""
import argparse
import hashlib
import importlib.util
import json
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

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=['prepare','grade','validate']);parser.add_argument('--scenario');parser.add_argument('--root',type=Path);parser.add_argument('--input',type=Path);parser.add_argument('--reply',type=Path);args=parser.parse_args()
    if args.command=='prepare':result=prepare(args.scenario,args.root.resolve())
    elif args.command=='grade':result=grade(json.loads(args.input.read_text()),args.root.resolve(),args.reply.read_text())
    else:result=validate_report(json.loads(args.input.read_text()))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
