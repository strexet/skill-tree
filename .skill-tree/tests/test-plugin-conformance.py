"""Synthetic captures test the oracle; unit traces never establish actual native execution."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

CORE = Path(__file__).resolve().parents[1]

def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, CORE / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

grader = load('plugin_observation_oracle', 'scripts/agent-conformance.py')
sha = lambda value: hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()
def digest(value):
    return sha(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False))

def node_digests(delivery):
    program = """const fs=require('node:fs'),crypto=require('node:crypto'),p=require(process.argv[1]);
const value=JSON.parse(fs.readFileSync(0,'utf8'));
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const resolved=p.resolveParameters({run:{values:value.parameters,instructions:value.extra_instructions}});
process.stdout.write(JSON.stringify({delivery_digest:crypto.createHash('sha256').update(canonical(value)).digest('hex'),resolved_parameter_digest:resolved.digest}));"""
    result = subprocess.run(['node', '-e', program, str(CORE/'lib/plugin-parameters.js')], input=json.dumps(delivery), capture_output=True, text=True)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)

def node_configuration_digest(binding_digest,policy):
    program="""const fs=require('node:fs'),crypto=require('node:crypto'),v=JSON.parse(fs.readFileSync(0,'utf8'));
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
process.stdout.write(crypto.createHash('sha256').update(canonical(v)).digest('hex'));"""
    value={'binding_configuration_digest':binding_digest,'execution_policy':policy}
    run=subprocess.run(['node','-e',program],input=json.dumps(value),capture_output=True,text=True)
    if run.returncode:raise AssertionError(run.stdout+run.stderr)
    return run.stdout

def node_dispatch(row,delivery,configuration_digest):
    program="""const fs=require('node:fs'),crypto=require('node:crypto'),p=JSON.parse(fs.readFileSync(0,'utf8')),row=p.row,d=p.delivery;
function stable(v){if(Array.isArray(v))return v.map(stable);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));return v;}
const hash=v=>crypto.createHash('sha256').update(JSON.stringify(stable(v))).digest('hex');
const identity={binding_id:row.id,boundary_id:row.location?.boundary_id||row.operation+':'+row.anchor,operation:d.event.operation,anchor:d.event.anchor,event_id:d.event.id,attempt_id:d.attempt_id};
const inputs={configuration_digest:p.configuration_digest,parameters:d.parameters,extra_instructions:d.extra_instructions};
process.stdout.write(JSON.stringify({...identity,binding_anchor:row.anchor,delivery_key:hash(identity),input_digest:hash({context:d.context,inputs,binding:row})}));"""
    value={'row':row,'delivery':delivery,'configuration_digest':configuration_digest}
    run=subprocess.run(['node','-e',program],input=json.dumps(value),capture_output=True,text=True)
    if run.returncode:raise AssertionError(run.stdout+run.stderr)
    return json.loads(run.stdout)

def node_manifest_configuration(packages,definitions,operations,policy,owned_resources):
    program="""const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),c=require(process.argv[1]),b=require(process.argv[2]),r=require(process.argv[3]),p=JSON.parse(fs.readFileSync(0,'utf8'));
function canonical(v){if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
const hash=v=>crypto.createHash('sha256').update(canonical(v)).digest('hex'),catalog=c.createCatalog(p.operations),compiled=b.compileBindings(p.definitions,{packages:p.packages,catalog,parameterDefaults:{},runOverrides:{}});
const manifest=r.seal({format:'skill-tree-plugin-bindings',schema:1,operation:'skill-tree-process-future-pending',owned_resources:p.owned_resources,operations:p.operations,definitions:p.definitions,bindings:compiled.bindings,packages:p.packages,parameter_defaults:{},registry_identity:'0'.repeat(64),registry_present:true,configuration_digest:compiled.configuration_digest,catalog:{operations:catalog.operations,entries:catalog.entries,aliases:catalog.aliases,digest:catalog.digest}});
const configuration={configuration_digest:hash({binding_configuration_digest:compiled.configuration_digest,execution_policy:p.policy}),binding_configuration_digest:compiled.configuration_digest,execution_policy:p.policy,bindings:compiled.bindings,definitions:p.definitions,packages:p.packages,parameter_defaults:{},run_overrides:{},manifest_identity:manifest.identity,operation:manifest.operation};
process.stdout.write(JSON.stringify({configuration,manifest_raw:r.json(manifest)}));"""
    value={'packages':packages,'definitions':definitions,'operations':operations,'policy':policy,'owned_resources':owned_resources}
    run=subprocess.run(['node','-e',program,str(CORE/'lib/plugin-composition.js'),str(CORE/'lib/plugin-bindings.js'),str(CORE/'lib/plugin-registry.js')],input=json.dumps(value),capture_output=True,text=True)
    if run.returncode:raise AssertionError(run.stdout+run.stderr)
    return json.loads(run.stdout)

class PluginInvocationOracleTests(unittest.TestCase):
    def validator(self):
        function = getattr(grader, 'validate_plugin_invocation_report', None)
        self.assertTrue(callable(function), 'The actual plugin observation oracle is not implemented.')
        return function

    def trace(self):
        wf = load('plugin_oracle_workflow_fixture', 'common/scripts/workflow-state.py')
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        store = wf.Store(root, allow_unselected=True, neutral=True)
        store.future.parent.mkdir(parents=True)
        store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        (store.base/'config').mkdir()
        (store.base/'config/repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (root/'source.py').write_text('VALUE = 1\n')
        research=root/'.skill-tree/history/research/controlled-plan.md';research.parent.mkdir(parents=True,exist_ok=True);research.write_text('The controlled source plan remains unchanged.\n')
        project_sources={'source.py':sha((root/'source.py').read_bytes()),'.skill-tree/history/research/controlled-plan.md':sha(research.read_bytes())}
        def body(marker):
            criterion = 'Preserve bounded behavior.'
            check = {'id':'behavior','recipe_id':'static-inspection','criteria':[criterion],'sources':['source.py','.skill-tree/history/research/controlled-plan.md','.skill-tree/documents/future.md','.skill-tree/invocations','.skill-tree/artifacts'],'parameters':{},'assertion':criterion,'timing':'immediate'}
            return 'Goal:\n- Preserve bounded behavior.\n- Context marker: '+marker+'.\n\nScope:\n- The controlled counter.\n\nOut of scope:\n- Remote services.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- '+criterion+'\n'
        pending = wf.intake(store, {'title':'Controlled plugin task','description':'Preserve bounded behavior.','expected_behavior':'The controlled task remains explicit.','priority':100})
        tid = wf.process(store, {'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Controlled source research identifies the bounded task.'}},'tasks':[{'title':'Controlled plugin task','body':body('context-initial'),'parent_pending_ids':[pending['id']]}]})['created_ids'][0]
        def selected(): return wf.resolve(wf.parse(store.text()), [tid])[0]
        def context():
            task = selected()
            return {'kind':'task','id':'task-scope:'+tid,'task_ids':[tid], 'semantic_fingerprint':wf.clarification_fingerprints(wf.clarification_baselines([task]))[tid], 'content_fingerprint':sha(task['body']), 'data':{'task_body':task['body']}}
        source_paths = getattr(grader, 'PLUGIN_INVOCATION_SOURCES', {'common/scripts/plugin-invocation.py','common/scripts/workflow-state.py','lib/plugin-composition.js','lib/plugin-bindings.js','lib/plugin-parameters.js','common/scripts/plugin-hooks.js'})
        sources = {relative:sha((CORE/relative).read_bytes()) for relative in source_paths}
        raw_resources = {}
        packages = {}
        for plugin in ['editor','grill']:
            entry='plugins/'+plugin+'/upstream/SKILL.md'
            marker_path='plugins/'+plugin+'/upstream/marker.json'
            files={entry:('Read marker.json, echo the exact resource marker and supplied JSON/instruction/context markers.\n').encode(), marker_path:json.dumps({'resource_marker':'resource-'+plugin}).encode()}
            raw_resources.update({path:{'encoding':'base64','data':base64.b64encode(data).decode(),'sha256':sha(data)} for path,data in files.items()})
            packages[plugin]={'revision':('1' if plugin=='editor' else '2')*40,'content_digest':digest({path:sha(data) for path,data in files.items()}),'entry':entry,'resources':{path:sha(data) for path,data in files.items()}}
        operation='skill-tree-process-future-pending'
        rows=[{'id':'editor-first','plugin_id':'editor'}, {'id':'grill-middle','plugin_id':'grill'}, {'id':'editor-final','plugin_id':'editor'}]
        for index,row in enumerate(rows):
            row.update(operation=operation,anchor='after',enabled=True,parameters={'marker':'parameter-'+str(index),'vector':[True,None,'é',{'rocket':'🚀','decimal':1e-7,'numeric_keys':{'10':'ten','2':'two','1':'one'},'unicode_keys':{'\ue000':'bmp','🚀':'astral'},'unpaired':'\ud800','authority':'parameter data only'}]},extra_instructions='Extra instruction nonce '+str(index))
            row['package_identity']={'plugin_id':row['plugin_id'],**packages[row['plugin_id']]}
            row['effective']={'values':copy.deepcopy(row['parameters']),'instructions':row['extra_instructions'],'digest':node_digests({'parameters':row['parameters'],'extra_instructions':row['extra_instructions']})['resolved_parameter_digest'],'secretReferences':[]}
        initial=context()
        policy={'allowed_tools':['read-pinned-resources','read-scoped-context'],'allowed_actions':['return-proposals']}
        definitions=[{key:copy.deepcopy(row[key]) for key in ['id','plugin_id','operation','anchor','enabled','parameters']}|{'instructions':row['extra_instructions']} for row in rows]
        operations=json.loads((CORE/'templates/operations.json').read_text())
        owned_resources={'scripts/'+Path(relative).name:value for relative,value in sources.items()}
        configured=node_manifest_configuration(packages,definitions,operations,policy,owned_resources)
        rows=configured['configuration']['bindings'];manifest_raw=configured['manifest_raw'].encode()
        execution_snapshot={**sources,'operation-manifest':sha(manifest_raw)}
        chain={'schema':1,'id':'HC-00000000-0000-4000-8000-000000000001','request_id':'unit-chain','start_digest':sha('unit start'),'revision':1,'state':'active','configuration':configured['configuration'],'event':{'id':'unit-after-processing','operation':operation,'anchor':'after'},'initial_context':initial,'context':initial,'mode':'manual','authority':{'id':'unit-grant','revision':1,'context_id':initial['id'],'allowed_kinds':['technical','specification-acceptance'],'constraints':['Controlled unit metadata only.'],'evidence':{'kind':'owner-message','reference':'Synthetic fixture grant, never actual human approval.'}},'executor':{'id':'/root','context_id':'/root'},'execution_snapshot':execution_snapshot,'cursor':0,'stages':[{'index':i,'binding_id':row['id'],'status':'pending','attempt_ids':[],'accepted_context':None,'accepted_transition':None} for i,row in enumerate(rows)],'attempts':{},'prepared_attempt_id':None,'history':[],'initial_lineage':[],'epoch':1,'prerequisites':[]}
        capture={'schema':1,'kind':'plugin-invocation-native-capture','source_snapshot':sources,'resources':raw_resources,'operation_manifest':{'encoding':'base64','data':base64.b64encode(manifest_raw).decode(),'sha256':sha(manifest_raw)},'protected_inventory_before':{**project_sources,'operation/references/plugin-bindings.json':sha(manifest_raw),**{'operation/'+path:record['sha256'] for path,record in raw_resources.items()},**{'operation/'+path:value for path,value in owned_resources.items()}},'qualification':{'limits':{'contexts':6,'requests':12,'wall_seconds':1800,'cleanup_seconds':60},'consumed':{'contexts':3,'requests':6,'wall_seconds':100.0},'previous_attempts':[]},'events':[]}
        report={'schema':1,'kind':'plugin-invocation-agent-conformance','source_snapshot':sources,'scenario':{'id':'source-backed-a-b-a','event_ids':[]},'limitations':['The caller supplies separate trusted capture; unit capture traces are synthetic, not actual native qualification.','Fixture owner inputs are scripted and establish no real-human approval.','Exact model, native call IDs, tokens and cost may be unexposed and remain null.','This bounded source-backed Codex context observation does not claim a native Skill call, provider universality or plugin efficacy.']}
        def event(kind,**values):
            result={'id':'plugin-event-'+str(len(capture['events'])+1),'sequence':len(capture['events'])+1,'kind':kind,**copy.deepcopy(values)}
            capture['events'].append(result)
            return result
        def seal():
            previous=chain.get('chain_hash')
            chain['revision']+=1
            chain['history'].append({'sequence':chain['revision'],'event':'unit-stage-observation','previous_chain_hash':previous,'detail':{}})
            chain['chain_hash']=digest({key:value for key,value in chain.items() if key!='chain_hash'})
        def observed(label):
            seal()
            return event('chain-observed',label=label,chain=chain)
        observed('start')
        incorporation=None
        for index,row in enumerate(rows):
            actor={'id':'/root/unit-'+row['id'],'context_id':'/root/unit-'+row['id']}
            created=event('actor-created',binding_id=row['id'],actor=actor,provider='Codex collaboration',tool='collaboration.spawn_agent',native_request_sha256=sha('unit creation '+row['id']),tool_call_id=None,model=None,tokens=None,cost=None)
            attempt_id='HI-00000000-0000-4000-8000-'+str(index+10).zfill(12)
            before=copy.deepcopy(chain['context'])
            public={'chain_id':chain['id'],'attempt_id':attempt_id,'binding_id':row['id'],'index':index,'event':chain['event'],'context':before,'configuration_digest':chain['configuration']['configuration_digest'],'mode':chain['mode'],'epoch':chain['epoch'],'execution_snapshot_digest':digest(chain['execution_snapshot']),'authority_digest':digest(chain['authority']),'authority':chain['authority'],'execution_policy':policy,'scope_source_snapshot':copy.deepcopy(project_sources),'package_identity':{'plugin_id':row['plugin_id'],**packages[row['plugin_id']]},'parameters':row['effective']['values'],'extra_instructions':row['effective']['instructions'],'parameter_digest':row['effective']['digest'],'lineage':[{'binding_id':row['id'],'boundary_id':operation+':after'}]}
            input_digest=digest(public)
            delivery={'mechanism':'source-backed-context','provider':'codex','chain_id':chain['id'],'attempt_id':attempt_id,'binding_id':row['id'],'event':chain['event'],'plugin':{'plugin_id':row['plugin_id'],'revision':packages[row['plugin_id']]['revision'],'content_digest':packages[row['plugin_id']]['content_digest'],'entry':packages[row['plugin_id']]['entry'],'resource_digests':packages[row['plugin_id']]['resources']},'context':before,'parameters':row['effective']['values'],'extra_instructions':row['effective']['instructions'],'input_digest':input_digest,'mode':chain['mode'],'authority':chain['authority'],'authority_digest':public['authority_digest'],'allowed_tools':policy['allowed_tools'],'allowed_actions':policy['allowed_actions'],'scope_source_snapshot':public['scope_source_snapshot']}
            delivery['dispatch_identity']=node_dispatch(row,delivery,chain['configuration']['configuration_digest'])
            resolved=node_digests(delivery)
            dispatched=event('actor-dispatched',creation_event_id=created['id'],actor=actor,attempt_id=attempt_id,binding_id=row['id'],input=public,input_digest=input_digest,delivery=delivery,**resolved,provider='Codex collaboration',tool='collaboration.followup_task',native_request_sha256=sha('unit dispatch '+row['id']),tool_call_id=None,model=None,tokens=None,cost=None,mechanism='source-backed-context',native_skill_called=False)
            status='findings' if index==1 else 'passed'
            result={'status':status,'input_digest':input_digest,'delivery_digest':resolved['delivery_digest'],'evidence':{'resource_marker':'resource-'+row['plugin_id'],'parameter_marker':row['parameters']['marker'],'extra_instruction_marker':row['effective']['instructions'],'context_marker':'context-from-b' if index==2 else 'context-initial'}}
            if index==1:
                result['proposal']={'task_id':tid,'context_marker':'context-from-b'}
            returned=event('actor-returned',creation_event_id=created['id'],dispatch_event_id=dispatched['id'],actor=actor,attempt_id=attempt_id,binding_id=row['id'],result=result,input_digest=input_digest,delivery_digest=resolved['delivery_digest'])
            creation_evidence={'kind':'host-agent-created','provider':created['provider'],'tool':created['tool'],'reference':created['id'],'actor_id':actor['id'],'actor_context_id':actor['context_id']}
            invoke_evidence={'kind':'host-invoked','reference':dispatched['id'],'mechanism':'source-backed-context','provider':created['provider'],'tool':dispatched['tool'],'actor_id':actor['id'],'actor_context_id':actor['context_id']}
            result_evidence={'kind':'host-result','reference':returned['id'],'mechanism':'source-backed-context','provider':created['provider'],'tool':dispatched['tool'],'actor_id':actor['id'],'actor_context_id':actor['context_id']}
            chain['attempts'][attempt_id]={'id':attempt_id,'index':index,'binding_id':row['id'],'status':'returned','actor':actor,'creation_evidence':creation_evidence,'invoke_evidence':invoke_evidence,'result_evidence':result_evidence,'input':public,'input_digest':input_digest,'dispatch_identity':delivery['dispatch_identity'],**resolved,'result':result}
            stage=chain['stages'][index]
            stage['attempt_ids']=[attempt_id]
            stage['status']='awaiting-acceptance'
            if index==1:
                observed('b-returned')
                session=wf.clarification_start(store,{'task_ids':[tid],'expected_source_hash':sha(store.text()),'decision_mode':'manual'})
                def change(command,**payload):
                    nonlocal session
                    session=wf.clarification_mutate(store,command,{'session_id':session['id'],'expected_source_hash':sha(store.text()),'expected_session_hash':session['session_hash'],'expected_session_revision':session['revision'],**payload})
                    return session
                question={'id':'incorporate','text':'Incorporate the controlled plugin addition?','recommendation':'Incorporate the bounded task addition.','prerequisites':[],'bindings':{tid:['goal']}}
                change('clarify-round',questions=[question])
                owner=event('scripted-owner-input',purpose='incorporation',real_human=False,actor={'id':'scripted-fixture-owner','context_id':'scripted-fixture-owner'},answer='Incorporate the bounded plugin proposal.',evidence={'kind':'submitted-answer','reference':'scripted-fixture-owner-incorporation'})
                change('clarify-answer',round_id=session['rounds'][-1]['id'],question_id='incorporate',question_revision=session['questions']['incorporate']['revision'],answer=owner['answer'],evidence=owner['evidence'])
                future_before=store.text();session_before=copy.deepcopy(session)
                change('clarify-revise',tasks=[{'task_id':tid,'body':body('context-from-b')}])
                future_after=store.text();after=context();revision=session['task_revisions'][-1]
                receipt={'kind':'core-incorporation','reference':'unit-core-incorporation','before':digest(before),'after':digest(after),'session_id':session['id'],'task_revision_id':revision['id'],'source_before':sha(future_before),'source_after':sha(future_after)}
                incorporation=event('core-incorporation',attempt_id=attempt_id,binding_id=row['id'],owner_event_id=owner['id'],receipt=receipt,before_context=before,after_context=after,future_before=future_before,future_after=future_after,session_before=session_before,session_after=session)
                chain['context']=after
            else:
                after=before;receipt={'kind':'no-change','reference':returned['id'],'before':digest(before),'after':digest(before)}
            stage.update(status='complete',accepted_context=copy.deepcopy(after),accepted_transition={'before':before,'after':after,'receipt':receipt})
            chain['cursor']=index+1
            if index==2:chain['state']='complete'
            observed('after-'+row['id'] if index<2 else 'chain-complete')
        change('clarify-round')
        change('clarify-answer',round_id=session['rounds'][-1]['id'],question_id='incorporate',question_revision=session['questions']['incorporate']['revision'],answer='Retain the current incorporated task.',evidence={'kind':'submitted-answer','reference':'scripted-current-answer'})
        clarity={key:True for key in ['goals','scope','exclusions','dependencies','acceptance','validation','decisions']}
        clarity['evidence']=['The controlled task and source.py define explicit feasible behavior.']
        change('clarify-round',clarity=clarity)
        final_owner=event('scripted-owner-input',purpose='confirmation',real_human=False,actor={'id':'scripted-fixture-owner','context_id':'scripted-fixture-owner'},evidence={'kind':'submitted-answer','reference':'scripted-final-confirmation'})
        change('clarify-confirm',task_ids=[tid],semantic_fingerprints=session['semantic_fingerprints'],evidence=final_owner['evidence'])
        event('core-confirmation',owner_event_id=final_owner['id'],session=session,future=store.text())
        observed('final')
        capture['protected_inventory_after']=copy.deepcopy(capture['protected_inventory_before'])
        report['scenario']['event_ids']=[event['id'] for event in capture['events']]
        return report,capture

    def reject(self, report, capture):
        with self.assertRaises(ValueError):self.validator()(report,capture)

    def test_actual_observation_api_and_complete_separately_captured_chain(self):
        validator=self.validator();report,capture=self.trace();result=validator(report,capture)
        self.assertTrue(result['passed']);self.assertEqual(result['occurrences'],3);self.assertIn('source-backed',result['scope'])

    def test_self_reported_pass_and_native_labels_cannot_replace_capture(self):
        self.validator();report,capture=self.trace();report.update(trusted_capture=capture,checks={'native':True})
        self.reject(report,None)

    def test_current_source_and_raw_resource_bytes_must_match_capture(self):
        self.validator();report,capture=self.trace()
        for kind in ['source','resource','protected','manifest-configuration']:
            r=copy.deepcopy(report);c=copy.deepcopy(capture)
            if kind=='source':r['source_snapshot'][next(iter(r['source_snapshot']))]='0'*64
            elif kind=='resource':next(iter(c['resources'].values()))['data']=base64.b64encode(b'changed').decode()
            elif kind=='protected':c['protected_inventory_after']['source.py']='0'*64
            else:
                for event in c['events']:
                    if event['kind']=='chain-observed':
                        event['chain']['configuration']['definitions'][0]['parameters']['marker']='invented'
                        event['chain']['chain_hash']=digest({k:v for k,v in event['chain'].items() if k!='chain_hash'})
            with self.subTest(kind=kind):self.reject(r,c)

    def test_missing_duplicate_unknown_and_reordered_events_reject(self):
        self.validator();report,capture=self.trace()
        for kind in ['missing-native','duplicate-id','unknown-ref','order']:
            r=copy.deepcopy(report);c=copy.deepcopy(capture)
            if kind=='missing-native':c['events']=[e for e in c['events'] if e['kind']!='actor-created']
            elif kind=='duplicate-id':c['events'][1]['id']=c['events'][0]['id']
            elif kind=='unknown-ref':r['scenario']['event_ids'].append('invented')
            else:r['scenario']['event_ids'].reverse()
            with self.subTest(kind=kind):self.reject(r,c)

    def test_repeated_package_occurrences_need_distinct_actual_contexts(self):
        self.validator();report,capture=self.trace();events=[e for e in capture['events'] if e['kind']=='actor-created'];events[2]['actor']=copy.deepcopy(events[0]['actor'])
        self.reject(report,capture)

    def test_exact_returned_markers_and_forwarded_values_are_independent(self):
        self.validator();report,capture=self.trace()
        for key in ['resource_marker','parameter_marker','extra_instruction_marker','context_marker']:
            c=copy.deepcopy(capture);returned=next(e for e in c['events'] if e['kind']=='actor-returned');returned['result']['evidence'][key]='invented'
            # Retain matching native/ledger results and valid HC checksums so the
            # independently expected nonce is the rejecting oracle.
            for event in c['events']:
                if event['kind']=='chain-observed' and returned['attempt_id'] in event['chain']['attempts']:
                    event['chain']['attempts'][returned['attempt_id']]['result']=copy.deepcopy(returned['result'])
                    event['chain']['chain_hash']=digest({k:v for k,v in event['chain'].items() if k!='chain_hash'})
            with self.subTest(key=key):self.reject(report,c)

    def test_semantic_delivery_tampering_resealed_with_valid_digests_still_rejects(self):
        self.validator();report,capture=self.trace()
        for key in ['parameters','extra_instructions','context','mode','authority','allowed_tools','allowed_actions','dispatch_identity','scope_source_snapshot','mutable-source-injection','research-source-omission','sealed-authority','sealed-policy']:
            c=copy.deepcopy(capture);dispatch=next(e for e in c['events'] if e['kind']=='actor-dispatched');attempt_id=dispatch['attempt_id']
            if key=='parameters':dispatch['delivery']['parameters']['marker']='changed'
            elif key=='extra_instructions':dispatch['delivery'][key]='changed'
            elif key=='context':dispatch['delivery'][key]['content_fingerprint']='0'*64
            elif key=='mode':dispatch['delivery'][key]='auto'
            elif key=='authority':dispatch['delivery'][key]['constraints']=['Invented unrestricted authority.']
            elif key=='dispatch_identity':dispatch['delivery'][key]['delivery_key']='0'*64
            elif key=='scope_source_snapshot':
                dispatch['input'][key]={'source.py':'0'*64};dispatch['delivery'][key]=copy.deepcopy(dispatch['input'][key])
            elif key=='mutable-source-injection':
                path='.skill-tree/artifacts';value=sha('Synthetic mutable host output.')
                dispatch['input']['scope_source_snapshot'][path]=value;dispatch['delivery']['scope_source_snapshot']=copy.deepcopy(dispatch['input']['scope_source_snapshot'])
                c['protected_inventory_before'][path]=value;c['protected_inventory_after'][path]=value
            elif key=='research-source-omission':
                del dispatch['input']['scope_source_snapshot']['.skill-tree/history/research/controlled-plan.md'];dispatch['delivery']['scope_source_snapshot']=copy.deepcopy(dispatch['input']['scope_source_snapshot'])
            elif key=='sealed-authority':
                dispatch['input']['authority']['constraints']=['Invented sealed grant.'];dispatch['input']['authority_digest']=digest(dispatch['input']['authority'])
                dispatch['delivery']['authority']=copy.deepcopy(dispatch['input']['authority']);dispatch['delivery']['authority_digest']=dispatch['input']['authority_digest']
            elif key=='sealed-policy':
                dispatch['input']['execution_policy']['allowed_tools']=['invented-tool'];dispatch['delivery']['allowed_tools']=['invented-tool']
            else:dispatch['delivery'][key]=['invented-unrestricted-action']
            if key in {'scope_source_snapshot','mutable-source-injection','research-source-omission','sealed-authority','sealed-policy'}:
                dispatch['input_digest']=digest(dispatch['input']);dispatch['delivery']['input_digest']=dispatch['input_digest']
            digests=node_digests(dispatch['delivery']);dispatch.update(digests)
            for event in c['events']:
                if event['kind']=='actor-returned' and event['attempt_id']==attempt_id:event['delivery_digest']=digests['delivery_digest'];event['result']['delivery_digest']=digests['delivery_digest'];event['input_digest']=dispatch['input_digest'];event['result']['input_digest']=dispatch['input_digest']
                if event['kind']=='chain-observed' and attempt_id in event['chain']['attempts']:
                    attempt=event['chain']['attempts'][attempt_id];attempt.update(digests);attempt['input']=copy.deepcopy(dispatch['input']);attempt['input_digest']=dispatch['input_digest'];attempt['result']['input_digest']=dispatch['input_digest']
                    if key=='dispatch_identity':attempt['dispatch_identity']=copy.deepcopy(dispatch['delivery']['dispatch_identity'])
                    attempt['result']['delivery_digest']=digests['delivery_digest'];event['chain']['chain_hash']=digest({k:v for k,v in event['chain'].items() if k!='chain_hash'})
            with self.subTest(key=key):self.reject(report,c)

    def test_b_incorporation_is_ordinary_core_revision_before_a2(self):
        self.validator();report,capture=self.trace()
        for kind in ['absent','late','task-bytes','revision']:
            c=copy.deepcopy(capture);event=next(e for e in c['events'] if e['kind']=='core-incorporation')
            if kind=='absent':c['events'].remove(event)
            elif kind=='late':event['sequence']=1000
            elif kind=='task-bytes':event['future_after']=event['future_before']
            else:event['receipt']['task_revision_id']='TR-invented'
            with self.subTest(kind=kind):self.reject(report,c)

    def test_a1_historical_input_survives_b_change_and_a2_uses_new_context(self):
        self.validator();report,capture=self.trace();a2=next(e for e in capture['events'] if e['kind']=='actor-dispatched' and e['binding_id']=='editor-final');a1=next(e for e in capture['events'] if e['kind']=='actor-dispatched' and e['binding_id']=='editor-first');old=copy.deepcopy(a1['delivery']['context']);a2['delivery']['context']=old;a2['input']['context']=old;a2['input_digest']=digest(a2['input']);a2['delivery']['input_digest']=a2['input_digest'];final_chain=next(e['chain'] for e in capture['events'] if e.get('label')=='final');a2['delivery']['dispatch_identity']=node_dispatch(final_chain['configuration']['bindings'][2],a2['delivery'],final_chain['configuration']['configuration_digest']);a2.update(node_digests(a2['delivery']))
        for event in capture['events']:
            if event['kind']=='actor-returned' and event['attempt_id']==a2['attempt_id']:
                event['input_digest']=a2['input_digest'];event['delivery_digest']=a2['delivery_digest'];event['result'].update(input_digest=a2['input_digest'],delivery_digest=a2['delivery_digest'])
            if event['kind']=='chain-observed' and a2['attempt_id'] in event['chain']['attempts']:
                attempt=event['chain']['attempts'][a2['attempt_id']];attempt.update(input=copy.deepcopy(a2['input']),input_digest=a2['input_digest'],delivery_digest=a2['delivery_digest'],resolved_parameter_digest=a2['resolved_parameter_digest'],dispatch_identity=copy.deepcopy(a2['delivery']['dispatch_identity']));attempt['result'].update(input_digest=a2['input_digest'],delivery_digest=a2['delivery_digest']);stage=event['chain']['stages'][2];stage['accepted_transition']['before']=old;stage['accepted_transition']['after']=old;stage['accepted_context']=old;stage['accepted_transition']['receipt']['before']=digest(old);stage['accepted_transition']['receipt']['after']=digest(old);event['chain']['chain_hash']=digest({k:v for k,v in event['chain'].items() if k!='chain_hash'})
        self.reject(report,capture)

    def test_final_confirmation_follows_complete_chain_and_never_claims_human_input(self):
        self.validator();report,capture=self.trace()
        for kind in ['human','early','absent','not-complete']:
            c=copy.deepcopy(capture);owner=next(e for e in c['events'] if e.get('purpose')=='confirmation');core=next(e for e in c['events'] if e['kind']=='core-confirmation')
            if kind=='human':owner['real_human']=True
            elif kind=='early':core['sequence']=1
            elif kind=='absent':c['events'].remove(core)
            else:core['session']['state']='awaiting-confirmation'
            with self.subTest(kind=kind):self.reject(report,c)

    def test_unresolved_original_or_collapsed_order_cannot_claim_chain_completion(self):
        self.validator();report,capture=self.trace()
        for kind in ['unknown','order','collapsed']:
            c=copy.deepcopy(capture)
            for event in c['events']:
                if event['kind']!='chain-observed' or event['label'] not in {'chain-complete','final'}:continue
                chain=event['chain']
                if kind=='unknown':next(iter(chain['attempts'].values()))['status']='unknown'
                elif kind=='order':chain['configuration']['bindings'].reverse()
                else:chain['stages'][2]['binding_id']=chain['stages'][0]['binding_id']
                chain['chain_hash']=digest({k:v for k,v in chain.items() if k!='chain_hash'})
            with self.subTest(kind=kind):self.reject(report,c)

    def test_source_backed_mechanism_and_unknown_accounting_remain_honest(self):
        self.validator();report,capture=self.trace()
        for kind in ['native-skill','no-provider','provider-substitution','no-accounting','limitations','budget']:
            r=copy.deepcopy(report);c=copy.deepcopy(capture);event=next(e for e in c['events'] if e['kind']=='actor-dispatched')
            if kind=='native-skill':event['native_skill_called']=True
            elif kind=='no-provider':event['provider']=''
            elif kind=='provider-substitution':
                for observation in c['events']:
                    if observation['kind']=='chain-observed':
                        for attempt in observation['chain']['attempts'].values():attempt['invoke_evidence']['provider']='invented-provider'
                        observation['chain']['chain_hash']=digest({k:v for k,v in observation['chain'].items() if k!='chain_hash'})
            elif kind=='no-accounting':event.pop('tokens')
            elif kind=='budget':c['qualification']['consumed']['requests']=13
            else:r['limitations']=[]
            with self.subTest(kind=kind):self.reject(r,c)

if __name__ == '__main__':unittest.main()
