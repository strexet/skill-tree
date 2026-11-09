"""Controlled post-processing fixtures use inert resources and scripted inputs.

Temporary owned installations exercise task publication and application guards.
The controls supply no actual candidate, native host or human approval evidence.
"""
import hashlib
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

CORE=next(root for root in Path(__file__).resolve().parents
          if (root/'lib/plugin-runtime.js').is_file())
OP='skill-tree-process-future-pending'
ROLES=('task-editorial','task-interview')
BINDINGS=('editorial-before-interview','interview-required')
FINAL_EDITOR='editorial-after-interview'
CAPABILITIES=['codex-source-backed-context']
OWNER={'kind':'owner-message','reference':'Scripted fixture-owner input only.'}
EXECUTOR={'id':'processing-executor','context_id':'processing-executor-context'}
CRITERION='The selected fixture retains the declared value.'
QUEUE='# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n'


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


INSTALL = r"""const fs = require('node:fs');
const path = require('node:path');
const [core, root, encoded] = process.argv.slice(1);
const options = JSON.parse(encoded);
const installation = require(path.join(core, 'lib/installation.js'));
const lifecycle = require(path.join(core, 'lib/plugin-lifecycle.js'));
const operation = 'skill-tree-process-future-pending';
const destination = '.agents/skills/' + operation;
installation.install(root, core, 'general', [{name: operation, provider: 'codex', rel: destination}]);

async function prepareFixture() {
    if (options.enabled) {
        const upstream = path.join(root, 'controlled-processing-resource');
        fs.mkdirSync(upstream);
        fs.writeFileSync(path.join(upstream, 'SKILL.md'), [
            '---', 'name: controlled-processing-resource',
            'description: Inert bounded task-proposal fixture.', '---',
            'Return bounded proposals only for the explicitly selected task application.', ''
        ].join('\n'));
        const source = {
            id: 'controlled-processing-resource', path: upstream, capabilities: [],
            adapter: {
                context_kinds: ['task', 'task-group'],
                processing_application: {
                    schema: 1, roles: ['task-editorial', 'task-interview'],
                    instructions: 'Retain the fixture constraints and return bounded proposals.'
                }
            }
        };
        const bindings = options.rows.map(row => ({
            plugin_id: source.id, operation, anchor: 'after', enabled: true,
            parameters: {fixture_marker: row.id}, instructions: 'Occurrence ' + row.id + '.', ...row
        }));
        const proposal = await lifecycle.prepareProposal(root, {
            request_id: 'processing115-inert-fixture', operation: 'install', sources: [source], bindings
        });
        lifecycle.applyProposal(root, proposal, {proposal_digest: proposal.digest});
        installation.refresh(root, core);
    }
    process.stdout.write(JSON.stringify({package_root: path.join(root, destination)}));
}

prepareFixture().catch(error => {
    process.stderr.write(error.stack);
    process.exitCode = 1;
});
"""

RECONFIGURE = r"""const path = require('node:path');
const [core, root, encoded] = process.argv.slice(1);
const lifecycle = require(path.join(core, 'lib/plugin-lifecycle.js'));
const installation = require(path.join(core, 'lib/installation.js'));

async function reconfigureFixture() {
    const proposal = await lifecycle.prepareProposal(root, {
        request_id: 'processing115-fixture-reconfigure', operation: 'configure',
        sources: [], bindings: JSON.parse(encoded)
    });
    lifecycle.applyProposal(root, proposal, {proposal_digest: proposal.digest});
    installation.refresh(root, core);
}

reconfigureFixture().catch(error => {
    process.stderr.write(error.stack);
    process.exitCode = 1;
});
"""


class PluginProcessingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        (self.root/'source.py').write_text('VALUE = 1\n')
        (self.root/'package.json').write_text(json.dumps({'scripts':{'test':'node --test'}}))
        # A real profile recipe avoids unrelated missing-recipe admission errors.
        control={'schema':1,'recipes':{'fixture-source-check':{'lane':'static',
            'argv':['python3','-I','-B','-c',"from pathlib import Path; ns={}; exec(Path('source.py').read_text(),ns); assert ns['VALUE']==1"],
            'input_paths':['source.py']}}}
        (self.root/'.skill-tree').mkdir()
        (self.root/'.skill-tree/validation-recipes.json').write_text(json.dumps(control))

    def install(self,enabled=True,rows=None):
        if rows is None:
            rows=[self.row(key,role) for key,role in zip(BINDINGS,ROLES)] if enabled else []
        result=subprocess.run(['node','-e',INSTALL,str(CORE),str(self.root),
            json.dumps({'enabled':bool(rows),'rows':rows})],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.package_root=Path(json.loads(result.stdout)['package_root'])
        self.wf=load('processing115_owned_fixture',self.package_root/'scripts/workflow-state.py')
        self.store=self.wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True,exist_ok=True)
        if not self.store.future.exists():
            self.store.future.write_text(QUEUE)
        manifest=json.loads((self.package_root/'references/plugin-bindings.json').read_text())
        self.assertEqual([row['id'] for row in manifest['bindings']],[row['id'] for row in rows])
        for authored, installed in zip(rows,manifest['bindings']):
            self.assertEqual(installed.get('application'),authored.get('application'))
            self.assertEqual(installed['enabled'],authored.get('enabled',True))
            self.assertEqual(installed['anchor'],authored.get('anchor','after'))
        profile=json.loads((self.root/'.skill-tree/installation/profile.json').read_text())
        self.assertIn('fixture-source-check',profile['recipes'])

    def row(self,key,role=None,**options):
        return {'id':key,**({'application':{'role':role}} if role else {}),**options}

    def reconfigure(self,rows):
        definitions=[{'plugin_id':'controlled-processing-resource','operation':OP,
                      'anchor':'after','enabled':True,**row} for row in rows]
        result=subprocess.run(['node','-e',RECONFIGURE,str(CORE),str(self.root),json.dumps(definitions)],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def body(self):
        check={'id':'fixture-behavior','recipe_id':'fixture-source-check','criteria':[CRITERION],
            'sources':['source.py'],'parameters':{},'assertion':CRITERION,'timing':'immediate'}
        return ('Goal:\n- '+CRITERION+'\n\nScope:\n- The selected fixture value.\n\n'
            'Out of scope:\n- Remote services and product runtime execution.\n\nTouch:\n- source.py\n\n'
            'Validation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- '+CRITERION+'\n')

    def pending(self,title='Bounded fixture value'):
        return self.wf.intake(self.store,{'title':title,
            'description':'Preserve the selected fixture value.',
            'expected_behavior':CRITERION,'priority':100})

    def process_payload(self,pending,spec=None,**options):
        if options.get('decision_mode')=='auto' and 'decision_authority' not in options:
            options.update(decision_authority=self.authority('pending-scope:'+pending['id']),
                           decision_executor=EXECUTOR)
        return {'selectors':[pending['id']],
                'dispositions':{pending['id']:{'status':'promoted','reason':'The inspected source and bounded fixture recipe support the selected task.'}},
                'tasks':[{'title':'Preserve bounded fixture value','body':self.body(),'parent_pending_ids':[pending['id']],**(spec or {})}],
                'expected_source_hash':self.source_hash(),
                'package_root':str(self.package_root),'decision_mode':'manual',
                'capabilities':CAPABILITIES,**options}

    def process(self,**options):
        pending=self.pending()
        self.pending_id=pending['id']
        self.first_publications=[]
        actual_commit=self.store.commit
        def observe_committed_publication(writes):
            # Observe the actual committed state; do not replace the transaction,
            # synthesize a task/session, or compute readiness through a mock oracle.
            result=actual_commit(writes)
            if '.skill-tree/documents/future.md' in writes:
                selected=[task for task in self.wf.parse(self.store.text())
                    if task['queue']=='Prioritized Next Changes' and self.pending_id in task['parent_pending_ids']]
                if selected:
                    self.first_publications.append({'tasks':selected,'write_keys':set(writes),
                        'sessions':{str(item.relative_to(self.root)):json.loads(item.read_text())
                            for item in (self.store.base/'clarifications').glob('cl-*.json')},
                        'index':json.loads(self.store.state.read_text())['tasks']})
            return result
        payload=self.process_payload(pending,**options)
        with patch.object(self.store,'commit',side_effect=observe_committed_publication):
            receipt=self.wf.process(self.store,payload)
        self.assertEqual(len(receipt['created_ids']),1)
        self.assertTrue(self.first_publications,'The first actually committed T publication must be observed.')
        return receipt,self.first_publications[0]

    def source_hash(self):
        return self.wf.file_hash(self.store.future)

    def snapshot(self):
        return {path.relative_to(self.store.base).as_posix():path.read_bytes()
                for path in self.store.base.rglob('*') if path.is_file() and '__pycache__' not in path.parts}

    def task(self,tid):
        return self.wf.resolve(self.wf.parse(self.store.text()),[tid],'Prioritized Next Changes')[0]

    def session(self,session_id):
        return self.wf.clarification_read(self.store,session_id)

    def published_session(self,published):
        self.assertEqual(len(published['sessions']),1)
        return self.session(next(iter(published['sessions'].values()))['id'])

    def cl(self,session,command,**options):
        return self.wf.clarification_mutate(self.store,command,{
            'session_id':session['id'],'expected_session_hash':session['session_hash'],
            'expected_session_revision':session['revision'],'expected_source_hash':self.source_hash(),**options})

    def authority(self,context_id):
        return {'id':'fixture-processing-authority','revision':1,'context_id':context_id,
                'allowed_kinds':['technical','product','specification-acceptance'],
                'constraints':['Retain the fixture goal, scope, checks and exclusions.'],'evidence':OWNER}

    def hook_start(self,session,**options):
        req=session['processing_requirements']
        return self.wf.hook_action(self.store,'hook-start',{
            'package_root':str(self.package_root),'request_id':req['request_id'],
            'event':req['event'],'context':req['context'],
            'authority':session.get('decision_authority') or self.authority(req['context']['id']),
            'run_overrides':req['configuration'].get('run_overrides',{}),
            'executor':EXECUTOR,'capabilities':CAPABILITIES,'expected_source_hash':self.source_hash(),**options})

    def hook(self,chain,command,*,private_delivery_sink=None,**options):
        return self.wf.hook_action(self.store,'hook-'+command,{
            'chain_id':chain['id'],'expected_chain_hash':chain['chain_hash'],
            'expected_chain_revision':chain['revision'],'expected_source_hash':self.source_hash(),**options},
            private_delivery_sink=private_delivery_sink)

    def actor_evidence(self,actor,kind):
        return {'kind':kind,'provider':'controlled-fixture-host','tool':'scripted-'+kind,
                'actor_id':actor['id'],'actor_context_id':actor['context_id'],
                'reference':'Synthetic host evidence for the unit control.',
                **({'mechanism':'source-backed-context'} if kind!='host-agent-created' else {})}

    def prepare_actor(self,chain):
        token=chain['id']+'-'+str(len(chain['attempts']))
        actor={'id':'actor-'+token,'context_id':'context-'+token}
        return self.hook(chain,'prepare',actor=actor,creation_evidence=self.actor_evidence(actor,'host-agent-created'))

    def invoke(self,chain):
        prepared=self.prepare_actor(chain)
        attempt=prepared['attempts'][prepared['prepared_attempt_id']]
        raw=self.wf._hook_node(self.package_root,{
            'runtime_action':'delivery-data','project_root':str(self.root),
            'event':prepared['event'],'context':prepared['context'],'capabilities':CAPABILITIES,
            'configuration':prepared['configuration'],'chain_id':prepared['id'],
            'attempt_id':attempt['id'],'binding_id':attempt['binding_id'],'public_input':attempt['input'],
            'input_digest':attempt['input_digest'],'mode':prepared['mode'],'authority':prepared['authority']})
        observed=[]
        def sink(payload):
            self.assertFalse((self.store.base/'.writer-lock').exists())
            observed.append(payload)
        invoked=self.hook(prepared,'invoke',private_delivery_sink=sink,
            **{key:raw[key] for key in ('input_digest','delivery_digest','resolved_parameter_digest')},
            attempt_id=attempt['id'],evidence=self.actor_evidence(attempt['actor'],'host-invoked'))
        self.assertEqual(observed,[raw['payload']])
        return invoked,observed[0]

    def record(self,chain,result):
        attempt=chain['attempts'][chain['prepared_attempt_id']]
        return self.hook(chain,'record',attempt_id=attempt['id'],input_digest=attempt['input_digest'],
                         delivery_digest=attempt['delivery_digest'],result=result,
                         evidence=self.actor_evidence(attempt['actor'],'host-result'))

    def returned(self,chain,result=None):
        invoked,private=self.invoke(chain)
        return self.record(invoked,result or {'status':'passed'}),private

    def accept(self,chain,**options):
        attempt=chain['attempts'][chain['prepared_attempt_id']]
        return self.hook(chain,'accept',attempt_id=attempt['id'],input_digest=attempt['input_digest'],**options)

    def question(self,task_id,key,text,field,prerequisites=()):
        return {'id':key,'text':text,'recommendation':'Retain the declared fixture contract.',
                'prerequisites':list(prerequisites),'bindings':{task_id:[field]},'required':True}

    def clarity(self):
        return {key:True for key in ('goals','scope','exclusions','dependencies','acceptance','validation','decisions')} | {
            'evidence':['The selected task and source.py define observable fixture behavior.']}

    def answer(self,session,question_id,**evidence):
        return self.cl(session,'clarify-answer',round_id=session['rounds'][-1]['id'],question_id=question_id,
                       question_revision=session['questions'][question_id]['revision'],
                       answer=evidence.pop('answer','Retain the declared fixture contract.'),
                       **(evidence or {'evidence':OWNER}))

    def confirm(self,session,**evidence):
        return self.cl(session,'clarify-confirm',task_ids=session['task_ids'],
                       semantic_fingerprints=session['semantic_fingerprints'],**(evidence or {'evidence':OWNER}))

    def revise(self,session,old,new):
        tid=session['task_ids'][0]
        body=self.task(tid)['body'].split('\n```\n',1)[1]
        self.assertEqual(body.count(old),1)
        return self.cl(session,'clarify-revise',tasks=[{'task_id':tid,'body':body.replace(old,new,1)}])

    def contribute(self,session,chain):
        return self.cl(self.session(session['id']),'clarify-processing-contribute',
                       chain_id=chain['id'],attempt_id=chain['prepared_attempt_id'])

    def contribution(self,session,chain):
        entries=session['processing_requirements']['contributions']
        match=[key for key,value in entries.items()
               if value['attempt_id']==chain['prepared_attempt_id'] and value['chain_id']==chain['id']]
        self.assertEqual(len(match),1)
        return match[0]

    def accept_contribution(self,session,chain,**override):
        after=self.wf.actual_hook_context(self.store,chain['context'])
        digest=self.wf.hook_helper().digest
        receipt={'kind':'core-incorporation','processing_contribution_id':self.contribution(session,chain),
                 'before':digest(chain['context']),'after':digest(after),**override}
        return self.accept(chain,context=after,receipt=receipt)

    def imported_question(self,session,proposal):
        matches=[key for key,value in session['questions'].items() if value['text']==proposal['text']]
        self.assertEqual(len(matches),1)
        return matches[0]

    def decision_change(self,decision,action,**options):
        return self.wf.decision_action(self.store,'decision-'+action,{
            'decision_id':decision['id'],'expected_decision_hash':decision['decision_hash'],
            'expected_decision_revision':decision['revision'],'expected_mode_epoch':decision['mode_epoch'],
            'expected_context_fingerprint':decision['context']['content_fingerprint'],
            'expected_source_hash':self.source_hash(),**options})

    def delegated(self,session,purpose,key=None,*,pending=False):
        context=self.wf.clarification_decision_context(session,purpose,key)
        question=self.wf.clarification_decision_question(session,purpose,key)
        option='accept' if purpose=='confirmation' else 'retain'
        return self.decision_reference(session,context,question,option,'fixture-'+purpose+'-'+str(key),pending=pending)

    def decision_reference(self,session,context,question,option,request_id,*,pending=False):
        mode=session['decision_mode']
        role='owner' if mode=='manual' else 'resolver'
        decision=self.wf.decision_action(self.store,'decision-start',{
            'request_id':request_id,'context':context,'mode':mode,
            'question':{**question,'options':[{'id':option,'text':'Retain the explicit fixture contract.'}],
                        'recommendation':option,'significance':'routine'},
            'authority':session['decision_authority'],'executor':session['decision_executor'],
            'expected_source_hash':self.source_hash()})
        actor={'id':'fixture-'+role+'-'+decision['id'],'context_id':'fixture-context-'+decision['id']}
        decision=self.decision_change(decision,'prepare',role=role,actor=actor)
        if pending:
            return decision
        decision=self.decision_change(decision,'record',attempt_id=decision['prepared_attempt_id'],
            result={'status':'answered','answer':option,'rationale':'Synthetic unit decision on the exact fixture scope.'},
            evidence={'kind':'submitted-answer' if mode=='manual' else 'delegated-agent',
                      'reference':'Synthetic unit decision producer.',
                      'actor_id':actor['id'],'actor_context_id':actor['context_id']})
        decision=self.decision_change(decision,'accept')
        return {'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']}

    def assert_held(self,tid):
        self.assertEqual(self.task(tid)['status'],'Blocked pending answers')
        with self.assertRaises(self.wf.WorkflowError):
            self.wf.begin_task(self.store,{'task_id':tid})

    def assert_rejected_without_writes(self,action,match=None):
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,match or r'.+'):
            action()
        self.assertEqual(self.snapshot(),before)

    def assert_released(self,initial,session,chains):
        tid=initial['id']
        released=self.task(tid)
        self.assertEqual(session['state'],'complete')
        self.assertEqual(released['status'],'Ready')
        self.assertEqual(released['parent_pending_ids'],initial['parent_pending_ids'])
        for key in ('processing_run_id','root_task_id','related_task_id','relation','depends_on'):
            self.assertEqual(released[key],initial[key],key)
        text=released['body']
        self.assertNotIn('blocks implementation]',text)
        for section in ('Scope:','Out of scope:\n- Remote services and product runtime execution.',
                        'Touch:\n- source.py','Validation:',f'Acceptance:\n- {CRITERION}'):
            self.assertIn(section,text)
        for chain in chains:
            self.assertEqual(self.hook(chain,'read'),chain,'CL release leaves completed HC history intact.')
        self.wf.clarification_admission(self.store,tid)
        self.assertEqual(self.wf.select(self.wf.parse(self.store.text()),tid)['id'],tid)

    def test_00_enabled_applications_block_first_publication_before_any_hook_start(self):
        self.install(enabled=True)
        receipt,published=self.process()
        task=published['tasks'][0]
        # Intended genuine Red: current installed Processing commits Ready here.
        # No new helper/import/descriptor/session field is required to reach it.
        self.assertEqual(task['status'],'Blocked pending answers',
                         'The first published T-task must already carry its configured post-processing hold.')
        self.assertEqual(task['id'],receipt['created_ids'][0])
        self.assertEqual(task['parent_pending_ids'],[self.pending_id])
        self.assertEqual(len(published['sessions']),1)
        session_path,session=next(iter(published['sessions'].items()))
        self.assertEqual(session['task_ids'],[task['id']])
        self.assertEqual(session['mode'],'required-processing')
        self.assertNotEqual(session['state'],'complete')
        self.assertIsNone(session['confirmation'])
        self.assertEqual(session['answers'],{})
        self.assertIn(session_path,published['write_keys'],
                      'The real CL record and blocked T definition must commit in the same transaction.')
        requirements=session['processing_requirements']
        self.assertEqual([row['id'] for row in requirements['configuration']['bindings']],list(BINDINGS))
        owned=requirements['task_holds'][task['id']]
        self.assertEqual(owned['status'],'Blocked pending answers')
        self.assertTrue(any(token in owned['marker'] for token in
            ['[Unresolved - blocks implementation]','[Unresolved — blocks implementation]']))
        self.assertIn(session['id'],owned['marker'])
        self.assertEqual(task['body'].count(owned['marker']),1)
        indexed=next(row for row in published['index'] if row['id']==task['id'])
        self.assertEqual(indexed['status'],'Blocked pending answers')
        self.assertFalse((self.store.base/'invocations').exists(),'Requirement publication starts no HC/HI or actor.')
        current=self.wf.resolve(self.wf.parse(self.store.text()),[task['id']],'Prioritized Next Changes')[0]
        self.assertEqual(current['status'],'Blocked pending answers')
        with self.assertRaisesRegex(ValueError,r'(?i)block|unresolved|question'):
            self.wf.select(self.wf.parse(self.store.text()),task['id'])
        before={item.relative_to(self.store.base).as_posix():item.read_bytes()
                for item in self.store.base.rglob('*') if item.is_file()}
        with self.assertRaisesRegex(ValueError,r'(?i)clarification|interview|block|hold|question|processing'):
            self.wf.begin_task(self.store,{'task_id':task['id']})
        self.assertEqual({item.relative_to(self.store.base).as_posix():item.read_bytes()
                          for item in self.store.base.rglob('*') if item.is_file()},before)

    def test_core_only_processing_keeps_ready_without_optional_session_or_hook(self):
        self.install(enabled=False)
        with patch.object(self.wf,'_hook_node',side_effect=AssertionError('Core-only processing reached the optional dispatcher.')):
            receipt,published=self.process()
        task=published['tasks'][0]
        self.assertEqual(task['id'],receipt['created_ids'][0])
        self.assertEqual(task['status'],'Ready')
        self.assertEqual(published['sessions'],{})
        self.assertNotIn('[Unresolved - blocks implementation]',task['body'])
        self.assertFalse((self.store.base/'invocations').exists())
        self.assertFalse((self.store.base/'clarifications').exists())
        selected=self.wf.select(self.wf.parse(self.store.text()),task['id'])
        self.assertEqual(selected['id'],task['id'])
        self.assertEqual(self.wf.begin_task(self.store,{'task_id':task['id']})['phase'],'implement')

    def test_generic_only_processing_keeps_ordinary_hook_dispatch_without_automatic_hold(self):
        binding = 'generic-after-processing'
        self.install(rows=[self.row(binding)])
        with patch.object(self.wf, '_hook_node', side_effect=AssertionError('Generic-only publication reached requirement preparation.')):
            receipt, published = self.process()
        tid = receipt['created_ids'][0]
        self.assertEqual(self.task(tid)['status'], 'Ready')
        self.assertEqual(published['sessions'], {})
        context = self.wf.actual_hook_context(self.store, {'kind': 'task', 'id': 'task-scope:' + tid, 'task_ids': [tid]})
        chain = self.wf.hook_action(self.store, 'hook-start', {
            'package_root': str(self.package_root), 'request_id': 'generic-after-processing-control',
            'event': {'id': 'generic-after-processing-control', 'operation': OP, 'anchor': 'after'},
            'context': context, 'mode': 'manual', 'authority': self.authority(context['id']), 'executor': EXECUTOR,
            'capabilities': CAPABILITIES, 'expected_source_hash': self.source_hash(),
        })
        chain, private = self.returned(chain)
        self.assertEqual(private['binding_id'], binding)
        self.assertNotIn('processing_application', private)
        self.assertEqual(self.accept(chain)['state'], 'complete')

    def test_disabled_and_excluded_occurrences_create_no_optional_hold(self):
        self.install(rows=[self.row('disabled-editor','task-editorial',enabled=False),
                           self.row('excluded-interview','task-interview',condition=False)])
        receipt,published=self.process()
        self.assertEqual(published['tasks'][0]['status'],'Ready')
        self.assertEqual(published['sessions'],{})
        self.assertEqual(self.wf.begin_task(self.store,{'task_id':receipt['created_ids'][0]})['phase'],'implement')

    def test_editor_only_questions_use_shared_manual_cl_without_interview(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        initial=published['tasks'][0]
        session=self.published_session(published)
        question=self.question(tid,'wording-choice','Should the fixture retain the current scope?','scope')
        chain,private=self.returned(self.hook_start(session),{'status':'questions','questions':[question]})
        self.assertEqual(private['processing_application']['role'],'task-editorial')
        self.assertIn('Retain the fixture constraints',private['processing_application']['instructions'])
        self.assertEqual(private['extra_instructions'],'Occurrence '+BINDINGS[0]+'.')
        session=self.contribute(session,chain)
        key=self.imported_question(session,question)
        session=self.cl(session,'clarify-round')
        self.assertIn(key,session['rounds'][-1]['question_ids'])
        session=self.answer(session,key)
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        chain=self.accept_contribution(session,chain)
        session=self.session(session['id'])
        self.assert_held(tid)
        self.assertEqual(session['answers'][key]['evidence']['kind'],'owner-message')
        session=self.confirm(session)
        self.assert_released(initial,session,[chain])
        self.assertEqual([item['binding_id'] for item in chain['attempts'].values()],[BINDINGS[0]])
        self.assertEqual(len(list((self.store.base/'clarifications').glob('cl-*.json'))),1)

    def test_interview_only_auto_requires_separate_current_delegated_confirmation(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process(decision_mode='auto')
        tid=receipt['created_ids'][0]
        initial=published['tasks'][0]
        session=self.published_session(published)
        self.assertEqual(session['decision_authority']['context_id'],'task-scope:'+tid)
        self.assertEqual(session['decision_authority']['id'],self.authority('placeholder')['id'])
        question=self.question(tid,'auto-choice','Should the fixture retain the declared behavior?','goal')
        chain,private=self.returned(self.hook_start(session),{'status':'questions','questions':[question]})
        self.assertEqual(private['processing_application']['role'],'task-interview')
        session=self.contribute(session,chain)
        key=self.imported_question(session,question)
        session=self.cl(session,'clarify-round')
        self.assert_rejected_without_writes(lambda:self.answer(session,key))
        answer=self.delegated(session,'answer',key)
        session=self.answer(session,key,answer='retain',decision_receipt=answer)
        self.assertEqual(session['answers'][key]['evidence']['kind'],'delegated-agent')
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        chain=self.accept_contribution(session,chain)
        session=self.session(session['id'])
        self.assert_rejected_without_writes(lambda:self.confirm(session,decision_receipt=answer))
        session=self.confirm(session,decision_receipt=self.delegated(session,'confirmation'))
        self.assertEqual(session['confirmation']['evidence']['kind'],'delegated-agent')
        self.assertEqual(session['confirmation']['decision_mode'],'auto')
        self.assert_released(initial,session,[chain])
        self.assertEqual(len(chain['attempts']),1)

    def run_interview_rework(self,final_editor,matching_editor=True):
        rows=[self.row(key,role) for key,role in zip(BINDINGS,ROLES)]
        if final_editor:
            rows.append(self.row(FINAL_EDITOR,'task-editorial'))
        self.install(rows=rows)
        override={BINDINGS[0]:{'values':{'fixture_marker':'frozen-run-a'},'instructions':'Explicit run wording for A.'}}
        if final_editor and matching_editor:
            override[FINAL_EDITOR]=override[BINDINGS[0]]
        receipt,published=self.process(run_overrides=override)
        tid=receipt['created_ids'][0]
        initial=published['tasks'][0]
        session=self.published_session(published)
        main=self.hook_start(session)
        original_a,private_a=self.returned(main)
        self.assertEqual(private_a['binding_id'],BINDINGS[0])
        self.assertEqual(private_a['parameters']['fixture_marker'],'frozen-run-a')
        self.assertEqual(private_a['extra_instructions'],'Explicit run wording for A.')
        main=self.accept(original_a)
        first=self.question(tid,'first-choice','Should remote services remain excluded?','exclusions')
        second=self.question(tid,'dependent-choice','Should dependencies remain unchanged?','dependencies',['first-choice'])
        main,private_b=self.returned(main,{'status':'questions','questions':[first,second]})
        self.assertEqual(private_b['binding_id'],BINDINGS[1])
        session=self.contribute(session,main)
        first_id=self.imported_question(session,first)
        second_id=self.imported_question(session,second)
        self.assert_rejected_without_writes(lambda:self.cl(session,'clarify-round',
            questions=[{**session['questions'][first_id],'required':False}]))
        session=self.cl(session,'clarify-round')
        self.assertEqual(session['rounds'][-1]['question_ids'],[first_id])
        self.assert_rejected_without_writes(lambda:self.accept_contribution(session,main))
        session=self.answer(session,first_id)
        session=self.revise(session,f'Goal:\n- {CRITERION}',f'Goal:\n- {CRITERION}\n- Preserve explicit interview outcome.')
        session=self.cl(session,'clarify-round')
        self.assertEqual(session['rounds'][-1]['question_ids'],[second_id])
        session=self.answer(session,second_id)
        session=self.revise(session,'- The selected fixture value.','- The selected fixture value and recorded interview scope.')
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        self.assertTrue(session['answers'][first_id]['valid'])
        self.assertTrue(session['answers'][second_id]['valid'])
        self.assertIsNone(session['confirmation'])
        self.assert_rejected_without_writes(lambda:self.accept_contribution(
            session,main,processing_contribution_id='unrelated-contribution'))
        main=self.accept_contribution(session,main)
        session=self.session(session['id'])
        self.assertEqual(main['stages'][1]['accepted_transition']['receipt']['revision_ids'],
                         [row['id'] for row in session['task_revisions']])
        self.assertIn('Preserve explicit interview outcome.',main['context']['body'])
        self.assertIn('recorded interview scope.',main['context']['body'])
        self.assert_held(tid)
        self.assert_rejected_without_writes(lambda:self.confirm(session))
        return initial,session,main

    def test_ordered_a_b_c_delivers_b_rework_to_current_c_without_another_call(self):
        initial,session,main=self.run_interview_rework(final_editor=True)
        main,private_c=self.returned(main)
        self.assertEqual(private_c['binding_id'],FINAL_EDITOR)
        self.assertEqual(private_c['parameters']['fixture_marker'],'frozen-run-a')
        self.assertIn('Preserve explicit interview outcome.',private_c['context']['body'])
        self.assertIn('recorded interview scope.',private_c['context']['body'])
        main=self.accept(main)
        session=self.session(session['id'])
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        session=self.confirm(session)
        self.assert_released(initial,session,[main])
        self.assertEqual(len(list((self.store.base/'invocations').glob('hc-*.json'))),1)
        self.assertEqual([stage['binding_id'] for stage in main['stages']],list(BINDINGS)+[FINAL_EDITOR])
        self.assertEqual(len(main['attempts']),3)
        self.assertEqual(len({attempt['actor']['context_id'] for attempt in main['attempts'].values()}),3)

    def test_later_editor_with_different_parameters_does_not_discharge_affected_first_editor(self):
        initial,session,main=self.run_interview_rework(final_editor=True,matching_editor=False)
        main,private_c=self.returned(main)
        self.assertEqual(private_c['binding_id'],FINAL_EDITOR)
        self.assertEqual(private_c['parameters']['fixture_marker'],FINAL_EDITOR)
        main=self.accept(main)
        session=self.session(session['id'])
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        self.assert_rejected_without_writes(lambda:self.confirm(session))
        session=self.cl(session,'clarify-processing-recheck',origin_binding_id=BINDINGS[0])
        mandate=next(iter(session['processing_requirements']['rechecks'].values()))
        derived=self.hook_start(session,request_id=mandate['request_id'],event=mandate['event'],context=mandate['context'])
        derived,private_a=self.returned(derived)
        self.assertEqual(private_a['binding_id'],BINDINGS[0])
        self.assertEqual(private_a['parameters']['fixture_marker'],'frozen-run-a')
        self.assertEqual(private_a['extra_instructions'],'Explicit run wording for A.')
        derived=self.accept(derived)
        if derived['state']!='complete':
            derived=self.hook(derived,'prepare')
        session=self.confirm(self.session(session['id']))
        self.assert_released(initial,session,[main,derived])

    def test_a_b_without_c_rechecks_only_affected_a_and_preserves_main_chain(self):
        initial,session,main=self.run_interview_rework(final_editor=False)
        self.assertEqual(main['state'],'complete')
        session=self.cl(session,'clarify-processing-recheck',origin_binding_id=BINDINGS[0])
        entries=session['processing_requirements']['rechecks']
        self.assertEqual(len(entries),1)
        mandate=next(iter(entries.values()))
        self.assertEqual(mandate['origin_binding_id'],BINDINGS[0])
        self.assert_rejected_without_writes(lambda:self.hook_start(session,request_id=mandate['request_id'],
            event=mandate['event'],context={**mandate['context'],'processing_recheck_digest':'0'*64}))
        derived=self.hook_start(session,request_id=mandate['request_id'],event=mandate['event'],context=mandate['context'])
        self.assertNotEqual(derived['id'],main['id'])
        self.assertEqual(derived['configuration'],main['configuration'])
        finding={'id':'explicit-wording','observation':'The accepted scope can name the interview decision directly.',
                 'consequence':'The final task becomes easier to check against the interview evidence.',
                 'bindings':{initial['id']:['scope']}}
        derived,private=self.returned(derived,{'status':'findings','findings':[finding]})
        self.assertEqual(private['binding_id'],BINDINGS[0])
        self.assertEqual(private['parameters']['fixture_marker'],'frozen-run-a')
        self.assertEqual(private['extra_instructions'],'Explicit run wording for A.')
        self.assertIn('recorded interview scope.',private['context']['body'])
        session=self.contribute(session,derived)
        session=self.revise(session,'recorded interview scope.','recorded interview scope with explicit wording.')
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        derived=self.accept_contribution(session,derived)
        if derived['state']!='complete':
            derived=self.hook(derived,'prepare')
        self.assertEqual(derived['state'],'complete')
        self.assertEqual([row['binding_id'] for row in derived['attempts'].values()],[BINDINGS[0]])
        self.assertEqual(derived['stages'][1]['status'],'skipped')
        self.assertEqual(derived['stages'][1]['attempt_ids'],[])
        self.assertEqual(len(main['attempts']),2)
        session=self.session(session['id'])
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        session=self.confirm(session)
        self.assert_released(initial,session,[main,derived])
        self.assertIn('with explicit wording.',self.task(initial['id'])['body'])

    def test_owned_release_preserves_exact_body_and_does_not_admit_external_edit(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        initial=published['tasks'][0]
        session=self.published_session(published)
        chain,_=self.returned(self.hook_start(session))
        chain=self.accept(chain)
        session=self.session(session['id'])
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        marker=session['processing_requirements']['task_holds'][tid]['marker']
        expected=self.task(tid)['body'].replace('status: Blocked pending answers\n','status: Ready\n',1)
        expected=expected.replace('\n\n'+marker,'',1)
        session=self.confirm(session)
        self.assert_released(initial,session,[chain])
        self.assertEqual(self.task(tid)['body'],expected)
        current=self.store.text()
        self.store.future.write_text(current.replace(CRITERION,'A later external edit changes the selected behavior.',1))
        self.assert_rejected_without_writes(lambda:self.wf.begin_task(self.store,{'task_id':tid}))

    def test_open_processing_scope_cannot_be_reused_by_another_pending_request(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        pending=self.pending('Follow-up request attempts to reuse a held task')
        proposal=self.process_payload(pending,{'reuse_id':tid})
        self.assert_rejected_without_writes(lambda:self.wf.process(self.store,proposal))
        self.assertEqual(self.session(session['id']),session)
        self.assertEqual(self.wf.resolve(self.wf.parse(self.store.text()),[pending['id']],'Pending Queue')[0]['id'],pending['id'])
        self.assert_held(tid)

    def test_controller_retains_required_child_hold_and_admitted_scope(self):
        self.install(enabled=False)
        receipt,_=self.process()
        parent=receipt['created_ids'][0]
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        run=self.wf.start(self.store,'all',workspace={'snapshot_ids':[parent]})
        pending=self.wf.intake(self.store,{'title':'Required bounded fixture correction',
            'description':'Retain the required dependency relationship.',
            'expected_behavior':'A required correction preserves the selected fixture.',
            'relation':'blocker','root_task_id':parent,'related_task_id':parent})
        receipt=self.wf.process(self.store,self.process_payload(pending,{'title':'Required fixture correction'}))
        child=receipt['created_ids'][0]
        checkpoint=self.store.load()['active_run']
        self.assertEqual(checkpoint['id'],run['id'])
        self.assertEqual(checkpoint['snapshot'],[parent])
        self.assertEqual(set(checkpoint['admitted_task_ids']),{parent,child})
        self.assertEqual(self.task(parent)['depends_on'],[child])
        self.assertEqual(self.task(child)['parent_pending_ids'],[pending['id']])
        self.assert_held(child)
        self.assert_rejected_without_writes(lambda:self.wf.advance(self.store))

    def test_reordered_interview_and_repeated_generic_occurrences_keep_independent_ids(self):
        earlier='generic-first'
        later='generic-last'
        self.install(rows=[self.row(BINDINGS[1],'task-interview'),self.row(earlier),self.row(later)])
        receipt,published=self.process()
        initial=published['tasks'][0]
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        question=self.question(tid,'generic-order-choice','Should the existing validation remain?','validation')
        chain,private=self.returned(self.hook_start(session),{'status':'questions','questions':[question]})
        self.assertEqual(private['binding_id'],BINDINGS[1])
        session=self.contribute(session,chain)
        session=self.cl(session,'clarify-round')
        session=self.answer(session,self.imported_question(session,question))
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        chain=self.accept_contribution(session,chain)
        for binding_id in (earlier,later):
            chain,private=self.returned(chain)
            self.assertEqual(private['binding_id'],binding_id)
            self.assertEqual(private['parameters']['fixture_marker'],binding_id)
            self.assertNotIn('processing_application',private)
            chain=self.accept(chain)
        session=self.session(session['id'])
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        session=self.confirm(session)
        self.assert_released(initial,session,[chain])
        self.assertEqual([stage['binding_id'] for stage in chain['stages']],[BINDINGS[1],earlier,later])
        self.assertEqual(len(chain['attempts']),3)

    def test_pending_edit_between_actual_preflight_and_commit_never_publishes_task(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        pending=self.pending()
        proposal=self.process_payload(pending)
        before=self.snapshot()
        changed=self.store.text().replace('Preserve the selected fixture value.',
                                         'Preserve the updated selected fixture value.',1)
        node=self.wf._hook_node
        observations=[]
        def concurrent_edit(package,request):
            result=node(package,request)
            if request.get('runtime_action')=='requirement-plan':
                self.assertFalse((self.store.base/'.writer-lock').exists())
                self.store.future.write_text(changed)
                observations.append(request['context']['task_ids'])
            return result
        with patch.object(self.wf,'_hook_node',side_effect=concurrent_edit):
            with self.assertRaises(self.wf.WorkflowError):
                self.wf.process(self.store,proposal)
        self.assertEqual(len(observations),1)
        after=self.snapshot()
        self.assertEqual(after['documents/future.md'],changed.encode())
        self.assertEqual({k:v for k,v in after.items() if k!='documents/future.md'},
                         {k:v for k,v in before.items() if k!='documents/future.md'})

    def test_formatting_retains_answer_and_semantic_edit_reopens_only_affected_question(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        goal=self.question(tid,'goal-choice','Should the goal retain the current fixture requirement?','goal')
        exclusion=self.question(tid,'excluded-service','Should remote services stay outside the fixture?','exclusions')
        chain,_=self.returned(self.hook_start(session),{'status':'questions','questions':[goal,exclusion]})
        session=self.contribute(session,chain)
        goal_id=self.imported_question(session,goal)
        exclusion_id=self.imported_question(session,exclusion)
        session=self.cl(session,'clarify-round')
        session=self.answer(session,goal_id)
        session=self.answer(session,exclusion_id)
        semantics=session['semantic_fingerprints']
        session=self.revise(session,'Goal:\n','Goal:\n\n')
        self.assertEqual(session['semantic_fingerprints'],semantics)
        self.assertTrue(session['answers'][goal_id]['valid'])
        session=self.revise(session,'Goal:\n\n- '+CRITERION,'Goal:\n\n- Preserve the explicit edited fixture goal.')
        self.assertNotEqual(session['semantic_fingerprints'],semantics)
        self.assertFalse(session['answers'][goal_id]['valid'])
        self.assertTrue(session['answers'][exclusion_id]['valid'])
        self.assert_rejected_without_writes(lambda:self.accept_contribution(session,chain))
        self.assert_held(tid)

    def test_installation_disable_requires_explicit_adoption_and_separate_final_confirmation(self):
        self.install(rows=[self.row(BINDINGS[0],'task-editorial')])
        pending=self.pending()
        receipt=self.wf.process(self.store,self.process_payload(pending,
            decision_authority=self.authority('pending-scope:'+pending['id']),decision_executor=EXECUTOR))
        tid=receipt['created_ids'][0]
        initial=self.task(tid)
        session=self.session(receipt['clarification_sessions'][tid])
        original=session['processing_requirements']['configuration']
        self.reconfigure([self.row(BINDINGS[0],'task-editorial',enabled=False)])
        self.assertEqual(self.session(session['id']),session)
        self.assert_rejected_without_writes(lambda:self.hook_start(session))
        self.assert_held(tid)
        before_preview=self.snapshot()
        preview=self.cl(session,'clarify-processing-adopt')
        self.assertEqual(self.snapshot(),before_preview)
        self.assert_rejected_without_writes(lambda:self.cl(session,'clarify-processing-adopt',
            decision_receipt={'decision_id':'DG-00000000-0000-4000-8000-000000000001','acceptance_digest':'0'*64}))
        reference=self.decision_reference(session,preview['decision_context'],{
            'id':'adopt-disabled-editor','kind':'technical','text':'Adopt the explicitly disabled editorial occurrence.'},
            'adopt','fixture-adopt-disabled-editor')
        session=self.cl(session,'clarify-processing-adopt',decision_receipt=reference)
        req=session['processing_requirements']
        self.assertEqual(req['required_bindings'],[])
        self.assertEqual(req['adoptions'][0]['previous_configuration'],original)
        self.assertEqual(req['adoptions'][0]['decision_receipt'],reference)
        self.assertIsNone(req['chain_id'])
        self.assertIsNone(session['confirmation'])
        self.assert_held(tid)
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        session=self.confirm(session)
        self.assert_released(initial,session,[])
        self.assertFalse((self.store.base/'invocations').exists())

    def test_auto_without_owner_grant_retains_visible_prerequisite(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process(decision_mode='auto',decision_authority=None)
        session=self.published_session(published)
        self.assertEqual(session['decision_mode'],'auto')
        self.assertIsNone(session['decision_authority'])
        self.assertEqual(session['state'],'blocked')
        self.assert_rejected_without_writes(lambda:self.hook_start(session))
        self.assert_held(receipt['created_ids'][0])

    def test_missing_source_backed_capability_holds_task_without_preparing_actor(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process(capabilities=[])
        session=self.published_session(published)
        req=session['processing_requirements']
        self.assertEqual(req['required_bindings'],[BINDINGS[1]])
        self.assertTrue(req['prerequisites'])
        chain=self.hook_start(session,capabilities=[])
        self.assertEqual(self.hook(chain,'next')['action'],'prerequisite')
        self.assert_rejected_without_writes(lambda:self.prepare_actor(chain))
        self.assertEqual(self.hook(chain,'read')['attempts'],{})
        self.assert_held(receipt['created_ids'][0])

    def test_unavailable_invocation_and_cancel_keep_required_task_held(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        chain,_=self.returned(self.hook_start(session),{'status':'unavailable','reason':'Required fixture tool is unavailable.'})
        self.assertEqual(chain['state'],'blocked')
        self.assert_rejected_without_writes(lambda:self.accept(chain))
        session=self.session(session['id'])
        session=self.cl(session,'clarify-cancel',reason='The scripted owner cancels the current clarification.')
        self.assertEqual(session['state'],'cancelled')
        self.assert_held(tid)
        self.assertEqual(self.hook(chain,'read'),chain)

    def factual_observation(self, session, chain, question_id, label):
        contribution = session['processing_requirements']['contributions'][self.contribution(session, chain)]
        fact_id, = contribution['fact_prerequisites'][question_id]
        attempt = chain['attempts'][chain['prepared_attempt_id']]
        return {
            'id': fact_id,
            'observation': 'The inspected fixture source records the current value.',
            'limitations': ['Local static fixture observation.'],
            'sources': [{'path': 'source.py', 'sha256': self.wf.file_hash(self.root / 'source.py')}],
            'producer_evidence': {
                'kind': 'fresh-factual-helper-result',
                'actor_id': 'fixture-observer-' + label,
                'actor_context_id': 'fixture-observer-context-' + label,
                'provider': 'controlled-fixture-host',
                'tool': 'scripted-fact-result',
                'creation_reference': 'Synthetic independent context creation.',
                'reference': 'Synthetic source observation for the unit control.',
                'session_id': session['id'],
                'question_id': question_id,
                'fact_id': fact_id,
                'input_digest': attempt['input_digest'],
                'parent_mode_epoch': contribution['decision_mode_epoch'],
            },
        }

    def test_factual_prerequisite_blocks_only_dependent_question_until_fresh_observation(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        needs_fact=self.question(tid,'current-value','Should the currently observed fixture value remain?','goal')
        needs_fact['fact_prerequisites']=['observed-value']
        independent=self.question(tid,'service-exclusion','Should external services remain outside scope?','exclusions')
        chain,_=self.returned(self.hook_start(session),{'status':'questions','questions':[needs_fact,independent]})
        session=self.contribute(session,chain)
        fact_question=self.imported_question(session,needs_fact)
        independent_question=self.imported_question(session,independent)
        session=self.cl(session,'clarify-round')
        self.assertEqual(session['rounds'][-1]['question_ids'],[independent_question])
        self.assert_rejected_without_writes(lambda:self.answer(session,fact_question))
        session=self.answer(session,independent_question)
        fact = self.factual_observation(session, chain, fact_question, 'current-value')
        source_only = {key: value for key, value in fact.items() if key != 'producer_evidence'}
        session = self.cl(session, 'clarify-round', facts=[source_only])
        self.assertNotIn(fact_question, session['rounds'][-1]['question_ids'])
        session = self.cl(session, 'clarify-round', facts=[fact])
        self.assertEqual(session['rounds'][-1]['question_ids'],[fact_question])
        session=self.answer(session,fact_question)
        session=self.cl(session,'clarify-round',clarity=self.clarity())
        completed=self.accept_contribution(session,chain)
        self.assertEqual(completed['state'],'complete')
        self.assertEqual(len(completed['attempts']),1)

    def test_two_questions_can_use_the_same_upstream_fact_label(self):
        self.install(rows=[self.row(BINDINGS[1], 'task-interview')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        first = self.question(tid, 'goal-fact', 'Should the observed value be kept as the goal?', 'goal')
        second = self.question(tid, 'scope-fact', 'Should the observed value remain in scope?', 'scope')
        for question in (first, second):
            question['fact_prerequisites'] = ['current-value']
        chain, _ = self.returned(self.hook_start(session), {'status': 'questions', 'questions': [first, second]})
        session = self.contribute(session, chain)
        first_id = self.imported_question(session, first)
        second_id = self.imported_question(session, second)
        first_fact = self.factual_observation(session, chain, first_id, 'goal')
        second_fact = self.factual_observation(session, chain, second_id, 'scope')
        self.assertNotEqual(first_fact['id'], second_fact['id'])
        session = self.cl(session, 'clarify-round', facts=[first_fact])
        self.assertEqual(session['rounds'][-1]['question_ids'], [first_id])
        session = self.answer(session, first_id)
        first_answer = deepcopy(session['answers'][first_id])
        session = self.cl(session, 'clarify-round', facts=[second_fact])
        self.assertEqual(session['rounds'][-1]['question_ids'], [second_id])
        self.assertEqual(session['answers'][first_id], first_answer)
        session = self.answer(session, second_id)
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        accepted = self.accept_contribution(session, chain)
        self.assertEqual(accepted['state'], 'complete')
        self.assertEqual(len(accepted['attempts']), 1)

    def test_fact_source_drift_after_round_blocks_dependent_answer(self):
        self.install(rows=[self.row(BINDINGS[1], 'task-interview')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        fact_question = self.question(tid, 'current-value', 'Should the observed fixture value remain?', 'goal')
        fact_question['fact_prerequisites'] = ['current-value']
        independent = self.question(tid, 'independent-exclusion', 'Should external services stay outside scope?', 'exclusions')
        chain, _ = self.returned(self.hook_start(session), {'status': 'questions', 'questions': [fact_question, independent]})
        session = self.contribute(session, chain)
        fact_id = self.imported_question(session, fact_question)
        independent_id = self.imported_question(session, independent)
        fact = self.factual_observation(session, chain, fact_id, 'before-drift')
        session = self.cl(session, 'clarify-round', facts=[fact])
        self.assertIn(fact_id, session['rounds'][-1]['question_ids'])
        self.assertIn(independent_id, session['rounds'][-1]['question_ids'])
        (self.root / 'source.py').write_text('VALUE = 2\n')
        self.assert_rejected_without_writes(lambda: self.answer(session, fact_id))
        session = self.answer(session, independent_id)
        self.assertTrue(session['answers'][independent_id]['valid'])
        self.assertNotIn(fact_id, session['answers'])
        self.assert_held(tid)

    def test_refreshed_facts_require_a_new_delegated_answer(self):
        self.install(rows=[self.row(BINDINGS[1], 'task-interview')])
        receipt, published = self.process(decision_mode='auto')
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        question = self.question(tid, 'current-value', 'Should the current source value remain?', 'goal')
        question['fact_prerequisites'] = ['current-value']
        chain, _ = self.returned(self.hook_start(session), {'status': 'questions', 'questions': [question]})
        session = self.contribute(session, chain)
        key = self.imported_question(session, question)
        first_fact = self.factual_observation(session, chain, key, 'first-current-value')
        session = self.cl(session, 'clarify-round', facts=[first_fact])
        old_context = self.wf.clarification_decision_context(session, 'answer', key)
        old_receipt = self.delegated(session, 'answer', key)
        session = self.answer(session, key, answer='retain', decision_receipt=old_receipt)
        self.assertTrue(session['answers'][key]['valid'])
        (self.root / 'source.py').write_text('VALUE = 2\n')
        current_fact = self.factual_observation(session, chain, key, 'updated-current-value')
        session = self.cl(session, 'clarify-round', facts=[current_fact])
        current_context = self.wf.clarification_decision_context(session, 'answer', key)
        self.assertEqual(old_context['question_revision'], current_context['question_revision'])
        self.assertNotEqual(old_context['semantic_fingerprint'], current_context['semantic_fingerprint'])
        self.assert_rejected_without_writes(lambda: self.answer(session, key, answer='retain', decision_receipt=old_receipt))
        current_receipt = self.decision_reference(session, current_context,
            self.wf.clarification_decision_question(session, 'answer', key), 'retain', 'fixture-refreshed-fact-answer')
        session = self.answer(session, key, answer='retain', decision_receipt=current_receipt)
        self.assertTrue(session['answers'][key]['valid'])
        self.assert_held(tid)

    def test_required_child_attachment_waits_for_the_original_parent_actor(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        parent = receipt['created_ids'][0]
        session = self.published_session(published)
        chain, _ = self.invoke(self.hook_start(session))
        session = self.session(session['id'])
        pending = self.wf.intake(self.store, {
            'title': 'Required held parent correction',
            'description': 'Preserve the required dependency relationship.',
            'expected_behavior': 'A required correction preserves the selected fixture.',
            'relation': 'blocker',
            'root_task_id': parent,
            'related_task_id': parent,
        })
        proposal = self.process_payload(pending, {'title': 'Correct required held parent fixture'})
        self.assert_rejected_without_writes(lambda: self.wf.process(self.store, proposal))
        self.assertEqual(self.task(parent)['depends_on'], [])
        self.assertEqual(self.session(session['id']), session)
        self.assertEqual(self.hook(chain, 'read'), chain)
        self.assert_held(parent)

    def test_required_child_reopens_released_parent_without_erasing_progress(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        parent = receipt['created_ids'][0]
        session = self.published_session(published)
        main, _ = self.returned(self.hook_start(session))
        main = self.accept(main)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        session = self.confirm(session)
        self.assert_released(published['tasks'][0], session, [main])
        previous_release = session['processing_requirements']['finalization']
        run = self.wf.start(self.store, 'all', workspace={'snapshot_ids': [parent]})
        self.wf.begin_task(self.store, {'task_id': parent})
        progress = deepcopy(self.store.load()['task_progress'][parent])
        pending = self.wf.intake(self.store, {
            'title': 'Required correction discovered during implementation',
            'description': 'Capture the required fix before completing the parent.',
            'expected_behavior': 'The required fix preserves the fixture contract.',
            'relation': 'blocker',
            'root_task_id': parent,
            'related_task_id': parent,
        })
        self.assertEqual(self.wf.next_task(self.store)['phase'], 'process-required')
        receipt = self.wf.process(self.store, self.process_payload(pending, {'title': 'Correct required implementation fixture'}))
        child = receipt['created_ids'][0]
        self.assert_held(parent)
        self.assert_held(child)
        self.assertEqual(self.task(parent)['depends_on'], [child])
        self.assertEqual(self.task(parent)['parent_pending_ids'], published['tasks'][0]['parent_pending_ids'])
        self.assertEqual(self.task(child)['parent_pending_ids'], [pending['id']])
        checkpoint = self.store.load()
        self.assertEqual(checkpoint['active_run']['id'], run['id'])
        self.assertEqual(checkpoint['active_run']['snapshot'], [parent])
        self.assertEqual(set(checkpoint['active_run']['admitted_task_ids']), {parent, child})
        self.assertEqual(checkpoint['task_progress'][parent], progress)
        self.assert_rejected_without_writes(lambda: self.wf.mark_implemented(self.store, {'task_id': parent}))
        self.assert_rejected_without_writes(lambda: self.wf.prepare_check(self.store, {
            'task_id': parent, 'check_id': 'fixture-behavior',
        }))
        reopened = self.session(session['id'])
        self.assertEqual(reopened['processing_requirements']['finalization_history'][-1], previous_release)
        self.assertIsNone(reopened['confirmation'])
        self.assertIn('dependencies', reopened['task_revisions'][-1]['changed_fields'][parent])
        self.assertEqual(self.hook(main, 'read'), main)
        reopened = self.cl(reopened, 'clarify-processing-recheck', origin_binding_id=BINDINGS[0])
        mandate = next(iter(reopened['processing_requirements']['rechecks'].values()))
        derived, private = self.returned(self.hook_start(reopened, request_id=mandate['request_id'],
            event=mandate['event'], context=mandate['context']))
        self.assertIn(child, private['context']['body'])
        derived = self.accept(derived)
        reopened = self.session(session['id'])
        reopened = self.cl(reopened, 'clarify-round', clarity=self.clarity())
        reopened = self.confirm(reopened)
        self.assertEqual(reopened['state'], 'complete')
        self.assertEqual(self.task(parent)['status'], 'Ready')
        self.assertEqual(self.task(parent)['depends_on'], [child])
        self.assertEqual(self.store.load()['task_progress'][parent], progress)
        self.assert_rejected_without_writes(lambda: self.wf.begin_task(self.store, {'task_id': parent}),
                                            'dependencies remain incomplete')

    def test_editorial_revision_cannot_empty_the_required_goal_section(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        finding = {
            'id': 'goal-wording',
            'observation': 'The task goal needs clearer wording.',
            'consequence': 'The fixture goal should remain observable.',
            'bindings': {tid: ['goal']},
        }
        chain, _ = self.returned(self.hook_start(session), {'status': 'findings', 'findings': [finding]})
        session = self.contribute(session, chain)
        self.assert_rejected_without_writes(lambda: self.revise(session, 'Goal:\n- ' + CRITERION, 'Goal:'))
        self.assertIn('Goal:\n- ' + CRITERION, self.task(tid)['body'])
        self.assert_held(tid)

    def test_auto_revise_decision_cannot_release_the_held_task(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process(decision_mode='auto')
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        chain, _ = self.returned(self.hook_start(session))
        chain = self.accept(chain)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        context = self.wf.clarification_decision_context(session, 'confirmation')
        question = self.wf.clarification_decision_question(session, 'confirmation')
        revise = self.decision_reference(session, context, question, 'revise', 'fixture-revise-current-specification')
        self.assert_rejected_without_writes(lambda: self.confirm(session, decision_receipt=revise))
        self.assert_held(tid)
        self.assertEqual(self.session(session['id'])['state'], 'awaiting-confirmation')
        accepted = self.confirm(session, decision_receipt=self.delegated(session, 'confirmation'))
        self.assert_released(published['tasks'][0], accepted, [chain])

    def test_unreviewed_held_task_edit_cannot_enter_processing_dispatch(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        original = self.store.text()
        revised = original.replace('- The selected fixture value.', '- The unreviewed fixture scope.', 1)
        self.assertNotEqual(original, revised)
        self.store.future.write_text(revised)
        self.assert_rejected_without_writes(lambda: self.hook_start(session))
        self.assertEqual(self.session(session['id']), session)
        self.assertFalse((self.store.base / 'invocations').exists())
        self.assert_held(tid)

    def test_held_recovery_rejects_an_empty_required_goal(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        original = self.store.text()
        malformed = original.replace('Goal:\n- ' + CRITERION, 'Goal:', 1)
        self.assertNotEqual(original, malformed)
        self.store.future.write_text(malformed)
        self.assert_rejected_without_writes(lambda: self.cl(session, 'clarify-resume'), 'nonempty real Goal')
        self.assert_held(tid)
        valid = original.replace('- The selected fixture value.', '- The reviewed fixture scope.', 1)
        self.assertNotEqual(original, valid)
        self.store.future.write_text(valid)
        resumed = self.cl(session, 'clarify-resume')
        revision = resumed['task_revisions'][-1]
        self.assertEqual(revision['kind'], 'explicit-processing-recovery')
        self.assertEqual(revision['changed_fields'][tid], ['scope'])
        chain, _ = self.returned(self.hook_start(resumed))
        self.assertEqual(self.accept(chain)['state'], 'complete')

    def test_hook_resume_cannot_silently_refresh_a_processing_snapshot(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        chain = self.hook_start(session)
        profile = self.root / '.skill-tree/installation/profile.json'
        profile.write_bytes(profile.read_bytes() + b'\n')
        session = self.session(session['id'])
        preview = self.cl(session, 'clarify-processing-adopt')
        self.assertEqual(preview['configuration_digest'], chain['configuration']['configuration_digest'])
        self.assert_rejected_without_writes(
            lambda: self.hook(chain, 'resume', reason='The owned profile was reconciled.'),
            '(?:frozen Processing|registered post-processing) execution snapshot changed',
        )
        self.assertEqual(self.hook(chain, 'read'), chain)
        self.assert_held(tid)

    def test_scope_source_drift_before_release_requires_explicit_current_adoption(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process()
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        chain, _ = self.returned(self.hook_start(session))
        chain = self.accept(chain)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        (self.root / 'source.py').write_text('VALUE = 2\n')
        self.assert_rejected_without_writes(lambda: self.confirm(session))
        self.assert_held(tid)
        preview = self.cl(session, 'clarify-processing-adopt')
        self.assertEqual(preview['configuration_digest'], chain['configuration']['configuration_digest'])
        reference = self.decision_reference(session, preview['decision_context'], {
            'id': 'adopt-current-scope-source',
            'kind': 'technical',
            'text': 'Adopt the current fixture source for a fresh editorial check.',
        }, 'adopt', 'fixture-adopt-current-scope-source')
        session = self.cl(session, 'clarify-processing-adopt', decision_receipt=reference)
        self.assertEqual(self.hook(chain, 'read'), chain)
        self.assert_held(tid)
        replacement, _ = self.returned(self.hook_start(session))
        replacement = self.accept(replacement)
        self.assertNotEqual(replacement['id'], chain['id'])
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        session = self.confirm(session)
        self.assert_released(published['tasks'][0], session, [replacement])

    def test_delegated_final_acceptance_waits_for_clarity_and_current_occurrences(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process(decision_mode='auto')
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        self.assert_rejected_without_writes(lambda: self.delegated(session, 'confirmation'))
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        self.assert_rejected_without_writes(lambda: self.delegated(session, 'confirmation'))
        self.assert_held(tid)
        chain, _ = self.returned(self.hook_start(session))
        chain = self.accept(chain)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        accepted = self.confirm(session, decision_receipt=self.delegated(session, 'confirmation'))
        self.assert_released(published['tasks'][0], accepted, [chain])

    def test_old_delegated_final_acceptance_cannot_release_an_adopted_source(self):
        self.install(rows=[self.row(BINDINGS[0], 'task-editorial')])
        receipt, published = self.process(decision_mode='auto')
        tid = receipt['created_ids'][0]
        session = self.published_session(published)
        original, _ = self.returned(self.hook_start(session))
        original = self.accept(original)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        old_context = self.wf.clarification_decision_context(session, 'confirmation')
        old_receipt = self.delegated(session, 'confirmation')
        session = self.confirm(session, decision_receipt=old_receipt)
        self.assert_released(published['tasks'][0], session, [original])
        (self.root / 'source.py').write_text('VALUE = 2\n')
        preview = self.cl(session, 'clarify-processing-adopt')
        adoption = self.decision_reference(session, preview['decision_context'], {
            'id': 'adopt-updated-fixture-source', 'kind': 'technical',
            'text': 'Adopt the current source under the original fixture scope.',
        }, 'adopt', 'fixture-adopt-source-for-current-confirmation')
        session = self.cl(session, 'clarify-processing-adopt', decision_receipt=adoption)
        replacement, _ = self.returned(self.hook_start(session))
        replacement = self.accept(replacement)
        session = self.session(session['id'])
        session = self.cl(session, 'clarify-round', clarity=self.clarity())
        current_context = self.wf.clarification_decision_context(session, 'confirmation')
        self.assertEqual(old_context['parent_mode_epoch'], current_context['parent_mode_epoch'])
        self.assertNotEqual(old_context['semantic_fingerprint'], current_context['semantic_fingerprint'])
        self.assert_rejected_without_writes(lambda: self.confirm(session, decision_receipt=old_receipt))
        self.assert_held(tid)
        current_receipt = self.decision_reference(session, current_context,
            self.wf.clarification_decision_question(session, 'confirmation'), 'accept', 'fixture-adopted-source-confirmation')
        session = self.confirm(session, decision_receipt=current_receipt)
        self.assert_released(published['tasks'][0], session, [replacement])
        self.assertEqual(self.hook(original, 'read'), original)

    def test_unknown_original_attempt_requires_cleanup_before_mode_switch(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process()
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        chain,_=self.invoke(self.hook_start(session))
        attempt_id=chain['prepared_attempt_id']
        observation={'kind':'host-reconciliation','reference':'Synthetic host transport reconciliation.'}
        chain=self.hook(chain,'reconcile',attempt_id=attempt_id,status='unknown',evidence=observation)
        self.assertEqual(chain['attempts'][attempt_id]['status'],'unknown')
        session=self.session(session['id'])
        options={'decision_mode':'auto','decision_authority':self.authority('task-scope:'+tid),
                 'decision_executor':EXECUTOR,'evidence':OWNER}
        self.assert_rejected_without_writes(lambda:self.cl(session,'clarify-switch-mode',**options))
        self.assert_rejected_without_writes(lambda:self.prepare_actor(chain))
        chain=self.hook(chain,'reconcile',attempt_id=attempt_id,status='cancelled',evidence=observation)
        session=self.cl(self.session(session['id']),'clarify-switch-mode',**options)
        self.assertEqual(session['decision_mode'],'auto')
        self.assertEqual(session['decision_mode_epoch'],1)
        self.assertEqual(self.hook(chain,'read')['attempts'][attempt_id]['status'],'cancelled')
        self.assert_held(tid)

    def test_mode_switch_rejects_old_delegated_question_receipt_and_preserves_original_result(self):
        self.install(rows=[self.row(BINDINGS[1],'task-interview')])
        receipt,published=self.process(decision_mode='auto')
        tid=receipt['created_ids'][0]
        session=self.published_session(published)
        question=self.question(tid,'mode-choice','Should the fixture retain the current goal?','goal')
        chain,_=self.returned(self.hook_start(session),{'status':'questions','questions':[question]})
        session=self.contribute(session,chain)
        session=self.cl(session,'clarify-round')
        key=self.imported_question(session,question)
        old_receipt=self.delegated(session,'answer',key)
        switched=self.cl(session,'clarify-switch-mode',decision_mode='manual',evidence=OWNER)
        self.assertEqual(switched['decision_mode_epoch'],session['decision_mode_epoch']+1)
        self.assertEqual(switched['decision_mode_history'][0]['previous_policy']['decision_mode'],'auto')
        self.assert_rejected_without_writes(lambda:self.answer(switched,key,answer='retain',decision_receipt=old_receipt))
        self.assert_rejected_without_writes(lambda:self.accept_contribution(switched,chain))
        self.assertEqual(self.hook(chain,'read'),chain)
        self.assert_held(tid)

    def test_pinned_descriptors_close_over_original_resources_and_host_metadata(self):
        fixtures=CORE/'tests/fixtures/task-processing'
        manifest=json.loads((fixtures/'source-manifest.json').read_text())
        revision='4ae2317ddb22b046e26455e4f9c9b3aaaf62212d'
        self.assertEqual(manifest['revision'],revision)
        paths={item['path']:item for item in manifest['files']}
        self.assertEqual(len(paths),8)
        for relative,identity in paths.items():
            data=(fixtures/relative).read_bytes()
            self.assertEqual(len(data),identity['bytes'],relative)
            self.assertEqual(hashlib.sha256(data).hexdigest(),identity['sha256'],relative)
            self.assertEqual(hashlib.sha1(f'blob {len(data)}\0'.encode()+data).hexdigest(),identity['git_blob_sha1'],relative)
        for key in ROLES:
            descriptor=json.loads((CORE/'config/plugins'/f'{key}.json').read_text())
            entry=descriptor['source']['entry']
            self.assertEqual(descriptor['source']['ref'],revision)
            self.assertEqual(descriptor['adapter']['processing_application']['default_role'],key)
            self.assertEqual(descriptor['expectedDigests'],{path:paths[path]['sha256'] for path in
                             [entry,*descriptor['resources'],*descriptor['dependencies']]})
        wrapper=fixtures/'skills/productivity/grill-me'
        self.assertIn('disable-model-invocation: true',(wrapper/'SKILL.md').read_text())
        self.assertIn('allow_implicit_invocation: false',(wrapper/'agents/openai.yaml').read_text())


if __name__=='__main__':unittest.main()
