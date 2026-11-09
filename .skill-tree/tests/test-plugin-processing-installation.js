'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const installation=require('../lib/installation.js');
const lifecycle=require('../lib/plugin-lifecycle.js');

const core=path.resolve(__dirname,'..');
const operation='skill-tree-process-future-pending';
const taskId='T-10000000-0000-4000-8000-000000000001';
const pendingId='P-10000000-0000-4000-8000-000000000001';
const instructions='Propose bounded wording changes under the task document rules.';
const authority={
 id:'fixture-authority',revision:1,context_id:'fixture-task',allowed_kinds:['technical'],
 constraints:['Isolated fixture only.'],
 evidence:{kind:'owner-message',reference:'Scripted test input only.'}
};
const taskContext={
 kind:'task',id:'fixture-task',task_ids:[taskId],pending_ids:[pendingId],
 semantic_fingerprint:'a'.repeat(64),content_fingerprint:'b'.repeat(64)
};

function write(root,relative,contents){
 const file=path.join(root,relative);
 fs.mkdirSync(path.dirname(file),{recursive:true});
 fs.writeFileSync(file,typeof contents==='string'?contents:JSON.stringify(contents));
}

async function fixture(t){
 const base=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-processing-dispatch-')));
 t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'project'),upstream=path.join(base,'upstream');
 write(root,'package.json',{scripts:{test:'node --test'}});
 write(upstream,'SKILL.md','---\nname: inert-processing-fixture\n---\nReturn bounded proposals.\n');
 const relative='.agents/skills/'+operation;
 installation.install(root,core,'general',[{name:operation,provider:'codex',rel:relative}]);
 const proposal=await lifecycle.prepareProposal(root,{
  request_id:'install-processing-dispatch-fixture',operation:'install',
  sources:[{id:'inert-processing-fixture',path:upstream,adapter:{
   context_kinds:['task'],
   processing_application:{schema:1,roles:['task-editorial','task-interview'],default_role:'task-editorial',instructions}
  }}],
  bindings:[
   {id:'editorial',plugin_id:'inert-processing-fixture',operation,anchor:'after-task-creation',
    enabled:true,parameters:{role:'task-interview'},instructions:'Additional fixture instructions.'},
   {id:'interview',plugin_id:'inert-processing-fixture',operation,anchor:'after',
    enabled:true,application:{role:'task-interview'}}
  ]
 });
 lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});
 installation.refresh(root,core);
 fs.rmSync(upstream,{recursive:true});
 const packageRoot=path.join(root,relative);
 const request={
  project_root:root,event:{id:'fixture-processing-after',operation,anchor:'after'},
  context:taskContext,capabilities:['codex-source-backed-context']
 };
 return {root,packageRoot,request};
}

function hook(project,action,payload,expected=0){
 const run=spawnSync(process.execPath,[path.join(project.packageRoot,'scripts/plugin-hooks.js'),'--input','-'],{
  cwd:project.root,encoding:'utf8',timeout:30000,input:JSON.stringify({...payload,runtime_action:action})
 });
 assert.equal(run.status,expected,run.error?.message||run.stdout+run.stderr);
 return expected===0?JSON.parse(run.stdout):run.stderr;
}

function taskBody(){
 const criterion='The fixture wording retains the declared requirement.';
 const check={id:'fixture-check',recipe_id:'fixture',criteria:[criterion],sources:['fixture.py'],
  parameters:{},assertion:criterion,timing:'immediate'};
 return ['Goal:','- '+criterion,'','Touch:','- fixture.py','','Validation:',
  '```json',JSON.stringify({checks:[check]}),'```','','Acceptance:','- '+criterion].join('\n');
}

function visibleTask(project){
 write(project.root,'.skill-tree/documents/future.md',[
  '# Future Work','','## Pending Task Format','','## Pending Queue','','## Prioritized Next Changes','',
  '### Preserve fixture wording','','```yaml','id: '+taskId,'priority: 100','status: Ready',
  'parent_pending_ids: ["'+pendingId+'"]','processing_run_id: null','root_task_id: null',
  'related_task_id: null','relation: main','depends_on: []','```','',taskBody(),'','## Backlog',''
 ].join('\n'));
}

test('the copied Processing dispatcher seals the chosen application separately from user parameters',async t=>{
 const project=await fixture(t);
 const {request}=project;
 const metadata=hook(project,'requirement-plan',request);
 assert.equal(metadata.proof.proof_kind,'completed-readiness');
 assert.deepEqual(metadata.proof.processing_applications,{
  editorial:{role:'task-editorial',instructions},
  interview:{role:'task-interview',instructions}
 });
 assert.deepEqual(metadata.proof.bindings.map(row=>row.id),['editorial','interview']);
 assert.equal(fs.existsSync(path.join(project.root,'.skill-tree/documents/future.md')),false);
 assert.equal(fs.existsSync(path.join(project.root,'.skill-tree/invocations')),false);
 assert.match(hook(project,'freeze-chain',{...request,proof_kind:metadata.proof.proof_kind},1),/cannot substitute/i);
 const writePolicy={allowed_tools:['read-scoped-context'],allowed_actions:['return-proposals','write-queue']};
 assert.match(hook(project,'requirement-plan',{...request,execution_policy:writePolicy},1),/proposal actions only/i);
 visibleTask(project);
 const frozen=hook(project,'freeze-chain',request);
 assert.deepEqual(frozen.configuration,metadata.configuration);
 const start={
  request_id:'fixture-processing-seal',event:frozen.proof.event,context:frozen.proof.context,
  mode:'manual',authority,executor:{id:'fixture-executor',context_id:'fixture-executor-context'},
  configuration:frozen.configuration
 };
 const python=`
import importlib.util,json,pathlib,sys
scripts=pathlib.Path(sys.argv[1])
def load(name):
    file=scripts/(name+'.py')
    spec=importlib.util.spec_from_file_location('fixture_'+name,file)
    module=importlib.util.module_from_spec(spec)
    exec(compile(file.read_bytes(),str(file),'exec'),module.__dict__)
    return module
w=load('workflow-state')
h=load('plugin-invocation')
value=json.load(sys.stdin)
s=w.Store(pathlib.Path(sys.argv[2]),allow_unselected=True,neutral=True)
chain=h.start(s,value['start'],proof=value['proof'])
actor={'id':'fixture-actor','context_id':'fixture-actor-context'}
created={'kind':'host-agent-created','provider':'fixture-host','tool':'fixture-create','reference':'Synthetic actor only.',
         'actor_id':actor['id'],'actor_context_id':actor['context_id']}
prepare={'chain_id':chain['id'],'expected_chain_hash':chain['chain_hash'],
         'expected_chain_revision':chain['revision'],'actor':actor,'creation_evidence':created}
missing={key:item for key,item in value['proof'].items() if key!='processing_applications'}
forged={**value['proof'],'processing_applications':{'editorial':{'role':'task-interview'}}}
for rejected in [missing,forged]:
    try:
        h.mutate(s,'prepare',prepare,proof=rejected)
    except h.InvocationError as error:
        assert 'frozen Processing application' in str(error)
    else:
        raise AssertionError('A missing or forged role prepared an invocation')
    assert h.read(s,chain['id'])==chain
chain=h.mutate(s,'prepare',prepare,proof=value['proof'])
print(json.dumps(chain['attempts'][chain['prepared_attempt_id']]))
`;
 const run=spawnSync('python3',['-I','-B','-c',python,path.join(project.packageRoot,'scripts'),project.root],{
  cwd:project.root,encoding:'utf8',timeout:30000,input:JSON.stringify({start,proof:frozen.proof})
 });
 assert.equal(run.status,0,run.error?.message||run.stdout+run.stderr);
 const attempt=JSON.parse(run.stdout);
 const deliveryRequest={...request,configuration:frozen.configuration,authority,chain_id:attempt.input.chain_id,
  attempt_id:attempt.id,public_input:attempt.input,input_digest:attempt.input_digest};
 const delivered=hook(project,'delivery-data',deliveryRequest).payload;
 assert.deepEqual(attempt.input.processing_application,{role:'task-editorial',instructions});
 assert.deepEqual(delivered.processing_application,attempt.input.processing_application);
 assert.equal(delivered.parameters.role,'task-interview');
 assert.equal(delivered.extra_instructions,'Additional fixture instructions.');
 const swapped={...attempt.input,processing_application:{role:'task-interview',instructions}};
 assert.match(hook(project,'delivery-data',{...deliveryRequest,public_input:swapped},1),/sealed immutable Processing application/i);
 const broadened={...attempt.input,execution_policy:writePolicy};
 assert.match(hook(project,'delivery-data',{...deliveryRequest,public_input:broadened},1),/sealed allowed tools and actions/i);
});

test('a caller mask and forged recheck identity cannot change copied Processing dispatch',async t=>{
 const project=await fixture(t);
 const {request}=project;
 visibleTask(project);
 const frozen=hook(project,'freeze-chain',{...request,binding_ids:['editorial']});
 assert.deepEqual(frozen.proof.bindings.map(row=>row.id),['editorial','interview']);
 const reduced={...frozen.configuration,bindings:[frozen.configuration.bindings[0]]};
 assert.match(hook(project,'occurrence-plan',{...request,configuration:reduced},1),/recorded frozen configuration differs/i);
 const forged={
  ...request,configuration:frozen.configuration,binding_ids:['editorial'],
  context:{...taskContext,session_id:'CL-10000000-0000-4000-8000-000000000001',
   processing_recheck_id:'fixture-forged-mandate',processing_recheck_digest:'c'.repeat(64)}
 };
 assert.match(hook(project,'requirement-plan',forged,1),/requirement inspection.*mandate/i);
 assert.match(hook(project,'freeze-chain',forged,1),/clarification|unknown session/i);
 assert.match(hook(project,'readiness-plan',forged,1),/clarification|unknown session/i);
 const profilePath=path.join(project.root,'.skill-tree/installation/profile.json');
 const originalProfile=fs.readFileSync(profilePath);
 const profile=JSON.parse(originalProfile);
 profile.destinations['.agents/skills/'+operation].files['scripts/workflow-state.py']='d'.repeat(64);
 fs.writeFileSync(profilePath,JSON.stringify(profile));
 for(const action of ['freeze-chain','readiness-plan']){
  assert.match(hook(project,action,forged,1),/ownership receipt|owned inventory/i);
 }
 fs.writeFileSync(profilePath,originalProfile);
 fs.rmSync(path.join(project.root,'.skill-tree/installation/plugins.json'));
 assert.match(hook(project,'readiness-plan',forged,1),/requires the frozen live plugin registry/i);
 assert.equal(fs.existsSync(path.join(project.root,'.skill-tree/invocations')),false);
 assert.equal(fs.existsSync(path.join(project.root,'.skill-tree/clarifications')),false);
 const detached={packageRoot:path.join(project.root,'..','copied-operation'),root:path.join(project.root,'..','detached-project')};
 fs.cpSync(project.packageRoot,detached.packageRoot,{recursive:true});
 visibleTask(detached);
 assert.match(hook(detached,'readiness-plan',{...forged,project_root:detached.root},1),/clarification|unknown session/i);
 assert.equal(fs.existsSync(path.join(detached.root,'.skill-tree/installation')),false);
});

test('the held-task alias requires the actual Processing clarification in business preparation',async t=>{
 const project=await fixture(t);
 write(project.root,'.skill-tree/documents/future.md',
  '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 const python=`
import importlib.util,json,pathlib,sys
package=pathlib.Path(sys.argv[1])
helper=package/'scripts/workflow-state.py'
spec=importlib.util.spec_from_file_location('fixture_workflow',helper)
w=importlib.util.module_from_spec(spec)
exec(compile(helper.read_bytes(),str(helper),'exec'),w.__dict__)
s=w.Store(pathlib.Path(sys.argv[2]),allow_unselected=True,neutral=True)
pending=w.intake(s,{'title':'Check the registered alias','description':'Preserve the Processing hold.',
                   'expected_behavior':'The actual clarification supplies the held task context.'})['id']
result=w.process(s,{'selectors':[pending],'dispositions':{pending:{'status':'promoted','reason':'The fixture has a concrete behavior.'}},
    'tasks':[{'title':'Preserve fixture wording','body':json.load(sys.stdin),'parent_pending_ids':[pending]}],
    'expected_source_hash':w.file_hash(s.future),'package_root':str(package),
    'decision_mode':'manual','capabilities':['codex-source-backed-context']})
task=result['created_ids'][0]
assert w.resolve(w.parse(s.text()),[task],'Prioritized Next Changes')[0]['status']=='Blocked pending answers'
session=w.clarification_read(s,result['clarification_sessions'][task])
print(json.dumps(session['processing_requirements']['context']))
`;
 const run=spawnSync('python3',['-I','-B','-c',python,project.packageRoot,project.root],{
  cwd:project.root,encoding:'utf8',timeout:30000,input:JSON.stringify(taskBody())
 });
 assert.equal(run.status,0,run.error?.message||run.stdout+run.stderr);
 const context=JSON.parse(run.stdout);
 const {session_id,...unlinked}=context;
 assert.match(session_id,/^CL-/);
 const request={...project.request,event:{...project.request.event,anchor:'after-task-creation'},context};
 const queue=path.join(project.root,'.skill-tree/documents/future.md');
 const before=fs.readFileSync(queue);
 assert.match(hook(project,'freeze-chain',{...request,context:unlinked},1),/clarification/i);
 const linked=hook(project,'freeze-chain',request);
 assert.equal(linked.proof.event.boundary_id,operation+':after');
 assert.deepEqual(linked.proof.bindings.map(row=>row.id),['editorial','interview']);
 const external={...project,packageRoot:path.join(project.root,'..','external-processing-copy')};
 fs.cpSync(project.packageRoot,external.packageRoot,{recursive:true});
 const spoofed={...request,package_root:project.packageRoot};
 const wrongDestination=/requires its (?:original )?owned installed package destination/i;
 assert.match(hook(external,'freeze-chain',spoofed,1),wrongDestination);
 fs.rmSync(path.join(project.root,'.skill-tree/installation/plugins.json'));
 assert.match(hook(external,'freeze-chain',spoofed,1),wrongDestination);
 assert.deepEqual(fs.readFileSync(queue),before);
 assert.equal(fs.existsSync(path.join(project.root,'.skill-tree/invocations')),false);
});
