'use strict';
// Requirements-led composition fixtures. These tests never claim native plugin execution.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const composer=require('../lib/composer.js'),installation=require('../lib/installation.js');
const lifecycle=require('../lib/plugin-lifecycle.js'),registry=require('../lib/plugin-registry.js'),bindings=require('../lib/plugin-bindings.js');
const core=path.resolve(__dirname,'..'),operations=require('../templates/operations.json');
const processing='skill-tree-process-future-pending',implementation='skill-tree-implement-next-future-task',intake='skill-tree-add-pending-task';
const manifestPath='references/plugin-bindings.json';
const api=()=>require('../lib/plugin-composition.js'); // Lazy loading preserves full Red discovery before the module exists.
function write(root,relative,value){const file=path.join(root,relative);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,Buffer.isBuffer(value)||typeof value==='string'?value:JSON.stringify(value));}
const read=(root,relative)=>fs.readFileSync(path.join(root,relative));
const row=(id,plugin_id='editor',extra={})=>({id,plugin_id,operation:processing,anchor:'after',enabled:true,...extra});
const event=(operation=processing,anchor='after')=>({id:'controlled-boundary-event',attempt_id:'controlled-attempt',operation,anchor});
function temporary(t){const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-plugin-composition-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));return base;}
function project(root,flavor){fs.mkdirSync(root,{recursive:true});write(root,'package.json',{scripts:{test:'node --test'}});if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}}
function sourceCopy(destination){fs.mkdirSync(destination);for(const relative of Object.keys(composer.sourceInputs(core)))write(destination,relative,read(core,relative));return destination;}
async function fixture(t,{flavor='general',rows=[],ids=['editor','interview'],capabilities=[],adapter=undefined,adapters={},source=core,base=temporary(t)}={}){
 const root=path.join(base,'project');project(root,flavor);installation.install(root,source,flavor,[{name:processing,provider:'codex',rel:'.agents/skills/'+processing}]);
 const originals={},sources=[];
 for(const id of ids){const upstream=path.join(base,'upstream-'+id),marker=path.join(base,'upstream-helper-executed-'+id);fs.mkdirSync(upstream);const skill=Buffer.from('\ufeff---\nname: external-'+id+'\n---\nExternal '+id+' instructions. Read [data](assets/data.bin) and [helper](scripts/sentinel.py).\n');const binary=Buffer.from([0,255,128,13,10,0,42]);write(upstream,'SKILL.md',skill);write(upstream,'assets/data.bin',binary);write(upstream,'scripts/sentinel.py','from pathlib import Path\nPath('+JSON.stringify(marker)+').write_text("unexpected execution")\nraise RuntimeError("upstream helper must remain inert")\n');write(upstream,'unrelated-private.txt','Excluded from the declared closure.');originals[id]={skill,binary,marker,upstream};const selectedAdapter=Object.hasOwn(adapters,id)?adapters[id]:adapter;sources.push({id,path:upstream,capabilities,...(selectedAdapter===undefined?{}:{adapter:selectedAdapter}),metadata:{authoring_host:'claude',custom:'source provenance survives'}});}
 if(sources.length){const proposal=await lifecycle.prepareProposal(root,{request_id:'controlled-plugin-install',operation:'install',sources,bindings:rows});lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});installation.refresh(root,source);}
 return {base,root,flavor,source,originals};
}
function build(f,operation=processing,profile=composer.resolveProfile(f.source,f.root,f.flavor)){const composition=composer.compose(f.source,profile,[operation]);return {profile,composition,files:composition.packages[operation]};}
function manifest(files){assert.ok(files[manifestPath],'Each composed operation declares its own ordered plugin manifest.');return JSON.parse(String(files[manifestPath]));}
function mount(f,files,name='only-package'){const target=path.join(f.base,name);fs.mkdirSync(target);for(const [relative,value]of Object.entries(files))write(target,relative,value);return target;}
function request(f,operation=intake,anchor='before',extra={}){return {project_root:f.root,event:event(operation,anchor),context:{kind:'request',id:'controlled-task-free-request'},capabilities:[],...extra};}
function noForbiddenWorkflow(root){for(const relative of ['.skill-tree/documents/future.md','.skill-tree/documents/future.json','.skill-tree/clarifications','.skill-tree/decisions'])assert.equal(fs.existsSync(path.join(root,relative)),false,'Preparation created forbidden workflow state: '+relative);}
function metadataBytes(root){const result={};const start=path.join(root,'.skill-tree');if(!fs.existsSync(start))return result;function walk(relative){for(const entry of fs.readdirSync(path.join(start,relative),{withFileTypes:true})){const rel=path.posix.join(relative,entry.name);if(entry.isDirectory()){if(['installation','__pycache__'].includes(entry.name))continue;walk(rel);}else result[rel]=fs.readFileSync(path.join(start,rel));}}walk('');return result;}
function python(helper,root,script,...args){const result=spawnSync('python3',['-I','-c',script,helper,root,...args],{encoding:'utf8',timeout:30000});assert.equal(result.status,0,result.stdout+result.stderr);return JSON.parse(result.stdout);}
function workflow(f,{phase='none'}={}){
 const helper=path.join(f.root,'.agents/skills',processing,'scripts/workflow-state.py');
 return python(helper,f.root,String.raw`import hashlib,importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('controlled_workflow',sys.argv[1]);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
root=Path(sys.argv[2]);s=w.Store(root,allow_unselected=True,route_queue=False,neutral=True)
s.future.parent.mkdir(parents=True,exist_ok=True)
if not s.future.exists():s.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
p=w.intake(s,{'title':'Unresolved controlled Pending','description':'A bounded task needs processing.','expected_behavior':'The bounded request remains Pending until processing completes.','priority':100})['id']
q=w.intake(s,{'title':'Controlled implementation','description':'A bounded task has researched requirements.','expected_behavior':'The researched fixture task preserves the declared behavior.','priority':99})['id']
criterion='Preserve bounded behavior.'
body='Goal:\n- '+criterion+'\n\nScope:\n- The controlled fixture.\n\nOut of scope:\n- External systems.\n\nTouch:\n- source.txt\n\nValidation:\n\x60\x60\x60json\n'+json.dumps({'checks':[{'id':'bounded','recipe_id':'static-inspection','criteria':[criterion],'sources':['source.txt'],'parameters':{},'assertion':criterion,'timing':'immediate'}]})+'\n\x60\x60\x60\n\nAcceptance:\n- '+criterion+'\n'
(root/'source.txt').write_text('controlled bytes\n')
t=w.process(s,{'selectors':[q],'dispositions':{q:{'status':'promoted','reason':'Actual controlled source research.'}},'tasks':[{'title':'Controlled implementation','body':body,'parent_pending_ids':[q]}]})['created_ids'][0]
task=w.resolve(w.parse(s.text()),[t])[0];fingerprint=hashlib.sha256(task['body'].encode()).hexdigest();context={'kind':'task','id':'controlled-task-scope','task_ids':[t],'semantic_fingerprint':fingerprint,'content_fingerprint':fingerprint}
out={'pending_id':p,'task_id':t,'context':context}
if sys.argv[3]!='none':
 authority={'id':'controlled-grant','revision':1,'context_id':context['id'],'allowed_kinds':['technical','specification-acceptance'],'constraints':['Only isolated fixture metadata; no product or publication.'],'evidence':{'kind':'owner-message','reference':'Synthetic fixture grant, never real-human approval.'}}
 frame=w.orchestration_action(s,'orchestration-start',{'request_id':'controlled-implementation','context':context,'authority':authority,'executor':{'id':'controlled-executor','context_id':'controlled-executor-context'},'mode':'manual','capabilities':{'independent_actors':False},'expected_source_hash':s.load()['source_hash']})
 def change(command,**extra):
  global frame
  frame=w.orchestration_action(s,'orchestration-'+command,{'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],'expected_orchestration_revision':frame['revision'],'expected_source_hash':s.load()['source_hash'],**extra});return frame
 if sys.argv[3]!='research':
  change('research',reference='Actual controlled source.txt read.');change('plan',plan_digest='a'*64,required_checks=['bounded'],reference='Controlled draft plan.')
 if sys.argv[3] in {'accepted','changed-plan'}:
  change('question',purpose='plan',question={'id':'accept-plan','kind':'specification-acceptance','text':'Accept the controlled draft?','options':[{'id':'accept','text':'Accept.'}],'recommendation':'accept','significance':'routine'})
  action=w.orchestration_action(s,'orchestration-next',{'orchestration_id':frame['id']});decision=w.decision_helper().read(s,frame['question_decision_id'])
  change('prepare-actor',actor={'id':'scripted-owner','context_id':'scripted-owner-context'},creation_evidence=None,input_digest=action['input_digest'],expected_decision_hash=decision['decision_hash'])
  decision=w.decision_helper().read(s,frame['question_decision_id']);sealed=frame['prepared_actor'];change('record-actor',attempt_id=sealed['attempt_id'],input_digest=sealed['input_digest'],expected_decision_hash=decision['decision_hash'],result={'status':'answered','answer':'accept','rationale':'Controlled owner submission, not real-human approval.'},evidence={'kind':'submitted-answer','reference':'Synthetic fixture owner answer.'});change('accept-decision')
  change('accept-plan',decision_receipt={'decision_id':frame['acceptance']['decision_id'],'acceptance_digest':frame['acceptance']['digest']})
  out['previous_plan_acceptance']=frame['plan_acceptance']
  if sys.argv[3]=='changed-plan':change('plan',plan_digest='b'*64,required_checks=['bounded'],reference='Controlled materially changed draft.')
 out['frame']=frame
print(json.dumps(out))`,phase);
}

test('composition exposes real callable composition and boundary APIs',()=>{for(const name of ['createCatalog','resolveInputs','composeOperation','prepareBoundary'])assert.equal(typeof api()[name],'function');});
for(const flavor of ['general','web','unity'])test(flavor+' core-only composition covers registered operations with W1 and no optional plugin hold',async t=>{
 const f=await fixture(t,{flavor,ids:[]});const profile=composer.resolveProfile(core,f.root,flavor),result=composer.compose(core,profile);assert.deepEqual(Object.keys(result.packages).sort(),Object.keys(operations).sort());
 for(const [operation,files]of Object.entries(result.packages)){const m=manifest(files);assert.equal(m.operation,operation);assert.deepEqual(m.bindings,[]);assert.deepEqual(m.packages,{});assert.match(files['SKILL.md'],/Core Decision Governance|core decision governance/);assert.match(files['SKILL.md'],/Auto/);assert.ok(files['scripts/plugin-hooks.js']);}
 const packageRoot=mount(f,result.packages[intake]);const before=metadataBytes(f.root),prepared=api().prepareBoundary(packageRoot,request(f));assert.equal(prepared.status,'noop');assert.equal(prepared.invocation,'not-executed');assert.deepEqual(prepared.prerequisites,[]);assert.deepEqual(metadataBytes(f.root),before);noForbiddenWorkflow(f.root);
});
for(const flavor of ['general','web','unity'])test(flavor+' composes A-to-B-to-A occurrences in exact order with independent parameters',async t=>{
 const rows=[row('initial-a','editor',{parameters:{pass:'initial',nested:{keep:true}},instructions:'Initial wording.'}),row('interview-b','interview',{parameters:{turns:2}}),row('final-a','editor',{parameters:{pass:'final',nested:{keep:false}},instructions:'Final wording.'})];const f=await fixture(t,{flavor,rows});const {files}=build(f),m=manifest(files);
 assert.deepEqual(m.bindings.map(v=>v.id),['initial-a','interview-b','final-a']);assert.deepEqual(m.bindings.map(v=>v.plugin_id),['editor','interview','editor']);assert.equal(m.bindings[0].effective.values.pass,'initial');assert.equal(m.bindings[2].effective.values.pass,'final');assert.equal(m.bindings[2].effective.values.nested.keep,false);assert.equal(m.bindings[2].effective.instructions,'Final wording.');assert.deepEqual(Object.keys(m.packages).sort(),['editor','interview']);
 assert.equal(Object.keys(files).filter(rel=>rel==='plugins/editor/upstream/SKILL.md').length,1);assert.equal(Object.keys(files).filter(rel=>rel==='plugins/interview/upstream/SKILL.md').length,1);
});
test('selected operation closure excludes unrelated plugins and preserves locked core instructions',async t=>{
 const unrelatedMarker='UNRELATED_PACKAGE_PRIVATE_PARAMETER_DEFAULT';const f=await fixture(t,{rows:[row('selected')],ids:['editor','interview'],adapters:{interview:{parameter_defaults:{upstream:{values:{opaque_marker:unrelatedMarker}}}}}});const selected=build(f).files,unrelated=build(f,intake).files;assert.deepEqual(Object.keys(manifest(selected).packages),['editor']);assert.deepEqual(manifest(unrelated).packages,{});assert.equal(Object.keys(unrelated).some(rel=>rel.startsWith('plugins/')),false);for(const files of [selected,unrelated]){assert.equal(String(files[manifestPath]).includes(unrelatedMarker),false,'An unrelated package parameter default leaked into this operation.');assert.equal(Object.hasOwn(manifest(files).parameter_defaults,'interview'),false);}assert.equal(selected['SKILL.md'].includes('External editor instructions.'),false);assert.match(selected['SKILL.md'],/truthful evidence/);assert.match(selected['SKILL.md'],/installation or publication authority/);
});
test('upstream BOM and binary bytes survive composition and original-byte hashing',async t=>{
 const f=await fixture(t,{rows:[row('selected')],ids:['editor']}),{files,composition}=build(f),m=manifest(files);assert.deepEqual(files['plugins/editor/upstream/SKILL.md'],f.originals.editor.skill);assert.deepEqual(files['plugins/editor/upstream/assets/data.bin'],f.originals.editor.binary);assert.equal(Buffer.isBuffer(files['plugins/editor/upstream/assets/data.bin']),true);assert.equal(composition.output_digests[processing]['plugins/editor/upstream/assets/data.bin'],composer.hash(f.originals.editor.binary));assert.equal(m.packages.editor.entry,'plugins/editor/upstream/SKILL.md');assert.equal(m.packages.editor.files['plugins/editor/upstream/assets/data.bin'],composer.hash(f.originals.editor.binary));assert.equal(files['plugins/editor/upstream/unrelated-private.txt'],undefined);
});
test('owned catalog registers all operation phases and approved named aliases with callable guards',()=>{
 const catalog=api().createCatalog(operations);for(const operation of Object.keys(operations))for(const anchor of ['before','during','after']){const resolved=bindings.resolveLocation({operation,anchor},catalog);assert.equal(resolved.status,'resolved');assert.equal(typeof catalog.boundaries[resolved.boundary_id].handler,'function');}
 for(const [operation,anchor,phase]of [[processing,'before-research','before'],[processing,'before-task-formulation','during'],[processing,'after-task-creation','after'],[implementation,'after-draft-plan','during'],['skill-tree-pr-review-cycle','before-pr-ready','after']])assert.equal(bindings.resolveLocation({operation,anchor},catalog).boundary_id,operation+':'+phase);
});
test('a later registered operation composes through the same extension without a fixed manager count',async t=>{
 const base=temporary(t),source=sourceCopy(path.join(base,'source'));const declared=JSON.parse(read(source,'templates/operations.json')),map=JSON.parse(read(source,'config/resource-map.json'));declared['skill-tree-later-operation']={...declared[intake],title:'Later Operation'};map['skill-tree-later-operation']=map[intake];write(source,'templates/operations.json',declared);write(source,'config/resource-map.json',map);
 const f=await fixture(t,{base,source,rows:[row('later','editor',{operation:'skill-tree-later-operation',anchor:'before'})],ids:['editor']}),{files}=build(f,'skill-tree-later-operation');assert.equal(manifest(files).operation,'skill-tree-later-operation');assert.deepEqual(manifest(files).bindings.map(v=>v.id),['later']);assert.equal(Object.keys(composer.compose(source,composer.resolveProfile(source,f.root,'general')).packages).length,Object.keys(declared).length);
});
test('an unknown configured label remains unresolved and never supplies a successful executable boundary',async t=>{
 const f=await fixture(t,{rows:[row('unknown','editor',{operation:intake,anchor:'some-unregistered-step'})],ids:['editor']}),{files}=build(f,intake),m=manifest(files);assert.equal(m.bindings[0].location.status,'unresolved');const packageRoot=mount(f,files),result=api().prepareBoundary(packageRoot,request(f,intake,'some-unregistered-step'));assert.equal(result.status,'prerequisite');assert.equal(result.invocation,'not-executed');assert.ok(result.unresolved.length||result.prerequisites.length);
});
test('missing native tools remain explicit unavailable prerequisites for noncatalog cross-host sources',async t=>{
 const f=await fixture(t,{rows:[row('native','editor',{operation:intake,anchor:'before'})],ids:['editor'],capabilities:['external-native-skill-tool']}),{files}=build(f,intake),packageRoot=mount(f,files),result=api().prepareBoundary(packageRoot,request(f));assert.equal(manifest(files).packages.editor.metadata.authoring_host,'claude');assert.equal(result.status,'prerequisite');assert.equal(result.invocation,'not-executed');assert.match(JSON.stringify(result.prerequisites),/external-native-skill-tool/);assert.deepEqual(result.bindings.map(v=>v.id),['native']);noForbiddenWorkflow(f.root);
});
test('composition installation list and dry-run never execute an upstream helper or mutate plugin configuration',async t=>{
 const f=await fixture(t,{rows:[row('selected')],ids:['editor']}),before=read(f.root,registry.REGISTRY);build(f);installation.refresh(f.root,core);for(const args of [['--list'],['--dry-run','--all','--target',f.root,'--flavor','general']]){const command=spawnSync('node',[path.join(core,'bin/install.js'),...args],{encoding:'utf8',timeout:30000});assert.equal(command.status,0,command.stdout+command.stderr);}assert.equal(fs.existsSync(f.originals.editor.marker),false);assert.deepEqual(read(f.root,registry.REGISTRY),before);noForbiddenWorkflow(f.root);
});
for(const flavor of ['general','web','unity'])test(flavor+' copied installed operation prepares without source installation or sibling packages',async t=>{
 const base=temporary(t),source=sourceCopy(path.join(base,'source')),f=await fixture(t,{base,source,flavor,rows:[row('one','editor',{operation:intake,anchor:'before'})],ids:['editor']});installation.install(f.root,source,flavor,[{name:intake,provider:'codex',rel:'.agents/skills/'+intake}]);const original=path.join(f.root,'.agents/skills',intake),standalone=path.join(base,'only-package');fs.cpSync(original,standalone,{recursive:true});fs.rmSync(source,{recursive:true});fs.rmSync(f.root,{recursive:true});const runtime=path.join(base,'task-free-runtime');fs.mkdirSync(runtime);const input=path.join(base,'boundary-input.json');write(base,'boundary-input.json',{project_root:runtime,event:event(intake,'before'),context:{kind:'request',id:'standalone-request'},capabilities:[]});
 assert.deepEqual(read(standalone,'plugins/editor/upstream/SKILL.md'),f.originals.editor.skill);assert.deepEqual(read(standalone,'plugins/editor/upstream/assets/data.bin'),f.originals.editor.binary);const command=spawnSync('node',[path.join(standalone,'scripts/plugin-hooks.js'),'--input',input],{cwd:runtime,encoding:'utf8',timeout:30000,env:{...process.env,NODE_PATH:''}});assert.equal(command.status,0,command.stdout+command.stderr);const result=JSON.parse(command.stdout);assert.equal(result.status,'prerequisite');assert.equal(result.invocation,'not-executed');assert.deepEqual(result.bindings.map(v=>v.id),['one']);assert.ok(result.prerequisites.length);assert.equal(fs.existsSync(f.originals.editor.marker),false);noForbiddenWorkflow(runtime);
});
test('Processing before and during bind actual selected Pending identities and preserve unresolved intake bytes',async t=>{
 for(const anchor of ['before','during']){const base=path.join(temporary(t),anchor);fs.mkdirSync(base);const f=await fixture(t,{base,rows:[row('pending','editor',{anchor})],ids:['editor']}),state=workflow(f),{files}=build(f),packageRoot=mount(f,files),before=metadataBytes(f.root),result=api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,anchor),context:{kind:'pending',id:'selected-pending',pending_ids:[state.pending_id]},capabilities:[]});assert.equal(result.status,'prerequisite');assert.equal(result.invocation,'not-executed');assert.deepEqual(result.context.pending_ids,[state.pending_id]);assert.equal(result.context.task_ids,undefined);assert.deepEqual(metadataBytes(f.root),before);assert.match(read(f.root,'.skill-tree/documents/future.md').toString(),new RegExp(state.pending_id));}
});
test('Processing guard rejects fabricated absent or premature task context without changing the queue',async t=>{
 const f=await fixture(t,{rows:[row('pending','editor',{anchor:'before'})],ids:['editor']}),state=workflow(f),{files}=build(f),packageRoot=mount(f,files),before=metadataBytes(f.root);for(const context of [{kind:'request',id:'pretend-pending'},{kind:'task',id:'premature-task',task_ids:[state.task_id]},{kind:'pending',id:'absent-pending',pending_ids:['P-11111111-1111-4111-8111-111111111111']}]){assert.throws(()=>api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,'before'),context,capabilities:[]}),/Pending|pending|context|selected/i);assert.deepEqual(metadataBytes(f.root),before);}
});
test('implementation During requires the matching actual draft-plan frame before acceptance',async t=>{
 const f=await fixture(t,{rows:[row('during','editor',{operation:implementation,anchor:'during'})],ids:['editor']}),state=workflow(f,{phase:'draft'}),{files}=build(f,implementation),packageRoot=mount(f,files),before=metadataBytes(f.root),value={project_root:f.root,event:event(implementation,'during'),context:state.context,capabilities:[],orchestration_id:state.frame.id};assert.equal(state.frame.phase,'plan-review');assert.equal(state.frame.plan_acceptance,null);assert.equal(api().prepareBoundary(packageRoot,value).status,'prerequisite');const {orchestration_id:omitted,...withoutOrchestration}=value;assert.ok(omitted);assert.throws(()=>api().prepareBoundary(packageRoot,withoutOrchestration),/orchestration|draft|plan|frame/i);assert.throws(()=>api().prepareBoundary(packageRoot,{...value,context:{...state.context,task_ids:['T-11111111-1111-4111-8111-111111111111']}}),/scope|task|context|selected/i);assert.deepEqual(metadataBytes(f.root),before);
});
test('implementation During rejects research-only and already accepted plans without stale readiness',async t=>{
 for(const phase of ['research','accepted']){const base=path.join(temporary(t),phase);fs.mkdirSync(base);const f=await fixture(t,{base,rows:[row('during','editor',{operation:implementation,anchor:'during'})],ids:['editor']}),state=workflow(f,{phase}),{files}=build(f,implementation),packageRoot=mount(f,files),before=metadataBytes(f.root);assert.throws(()=>api().prepareBoundary(packageRoot,{project_root:f.root,event:event(implementation,'during'),context:state.context,capabilities:[],orchestration_id:state.frame.id}),/draft|plan|phase|accept/i);assert.deepEqual(metadataBytes(f.root),before);}
});
test('a materially changed draft loses old acceptance before the next During preparation',async t=>{
 const f=await fixture(t,{rows:[row('during','editor',{operation:implementation,anchor:'during'})],ids:['editor']}),state=workflow(f,{phase:'changed-plan'}),{files}=build(f,implementation),packageRoot=mount(f,files);assert.ok(state.previous_plan_acceptance);assert.equal(state.frame.plan_acceptance,null);assert.equal(state.frame.phase,'plan-review');assert.equal(state.frame.plan.digest,'b'.repeat(64));const before=metadataBytes(f.root),result=api().prepareBoundary(packageRoot,{project_root:f.root,event:event(implementation,'during'),context:state.context,capabilities:[],orchestration_id:state.frame.id});assert.equal(result.status,'prerequisite');assert.equal(result.invocation,'not-executed');assert.deepEqual(metadataBytes(f.root),before);
});
test('sequence edits change profile and composition identity without mutating the frozen previous manifest',async t=>{
 const rows=[row('initial'),row('interview','interview'),row('final')],f=await fixture(t,{rows}),first=build(f),frozen=String(first.files[manifestPath]);const proposal=await lifecycle.prepareProposal(f.root,{request_id:'controlled-reorder',operation:'configure',sources:[],bindings:[rows[2],rows[1],rows[0]]});lifecycle.applyProposal(f.root,proposal,{proposal_digest:proposal.digest});assert.throws(()=>installation.verify(f.root,core),/refresh|mismatch|changed/i);const second=build(f);assert.notEqual(first.profile.environment_id,second.profile.environment_id);assert.notEqual(first.composition.identity,second.composition.identity);assert.deepEqual(manifest(second.files).bindings.map(v=>v.id),['final','interview','initial']);assert.equal(String(first.files[manifestPath]),frozen);assert.deepEqual(manifest(first.files).bindings.map(v=>v.id),['initial','interview','final']);
});
test('modified owned resources and escaping registry paths cannot enter a composed package',async t=>{
 const f=await fixture(t,{rows:[row('selected')],ids:['editor']}),r=registry.readRegistry(f.root);write(f.root,r.packages.editor.destination+'/upstream/assets/data.bin',Buffer.from('changed'));assert.throws(()=>composer.resolveProfile(core,f.root,'general'),/owned|modified|resource|inventory/i);
 const g=await fixture(t,{base:temporary(t),rows:[row('selected')],ids:['editor']}),bad=registry.readRegistry(g.root);bad.packages.editor.destination='../outside';write(g.root,registry.REGISTRY,registry.json(registry.seal(bad)));assert.throws(()=>composer.resolveProfile(core,g.root,'general'),/owned|path|record|registry/i);
});
test('copied operation detects changed local plugin bytes before preparing any occurrence',async t=>{
 const f=await fixture(t,{rows:[row('selected','editor',{operation:intake,anchor:'before'})],ids:['editor']}),{files}=build(f,intake),packageRoot=mount(f,files);write(packageRoot,'plugins/editor/upstream/assets/data.bin',Buffer.from('tampered'));assert.throws(()=>api().prepareBoundary(packageRoot,request(f)),/changed|digest|resource|inventory|modified/i);assert.equal(fs.existsSync(f.originals.editor.marker),false);noForbiddenWorkflow(f.root);
});

test('condition-excluded Processing occurrence is a task-free no-op without Pending or DO guards',async t=>{
 for(const adapter of [undefined,{context_kinds:['task']}]){
  const f=await fixture(t,{rows:[row('conditional','editor',{anchor:'before',condition:false})],ids:['editor'],adapter}),{files}=build(f),packageRoot=mount(f,files),before=metadataBytes(f.root);noForbiddenWorkflow(f.root);
  const result=api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,'before'),context:{kind:'request',id:'conditional-task-free-request'},capabilities:[]});
  assert.equal(result.status,'noop');assert.equal(result.invocation,'not-executed');assert.deepEqual(result.bindings,[]);assert.deepEqual(result.unresolved,[]);assert.deepEqual(result.prerequisites,[]);assert.deepEqual(metadataBytes(f.root),before);noForbiddenWorkflow(f.root);
 }
});

test('copied workflow guard bytes are verified before a tampered helper can forge selected scope',async t=>{
 const f=await fixture(t,{rows:[row('guarded','editor',{anchor:'before'})],ids:['editor']}),{files}=build(f),packageRoot=mount(f,files),originalManifest=read(packageRoot,manifestPath),marker=path.join(f.base,'tampered-core-helper-executed');noForbiddenWorkflow(f.root);
 const forged='from pathlib import Path\nPath('+JSON.stringify(marker)+').write_text("tampered helper executed")\nclass Store:\n def __init__(self,root,**options):\n  self.base=Path(root)/".skill-tree"; self.future=self.base/"documents/future.md"\n def text(self): return "forged task scope"\ndef parse(value): return []\ndef resolve(tasks,identities,queue): return [{"id":identity,"status":"Ready","parent_pending_ids":[]} for identity in identities]\n';
 write(packageRoot,'scripts/workflow-state.py',forged);assert.deepEqual(read(packageRoot,manifestPath),originalManifest);let failure;
 try{api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,'before'),context:{kind:'pending',id:'forged-pending-scope',pending_ids:['P-11111111-1111-4111-8111-111111111111']},capabilities:[]});}catch(error){failure=error;}
 assert.equal(fs.existsSync(marker),false,'The tampered owned helper executed before core resource verification.');assert.ok(failure,'Changed owned workflow bytes must reject before scope validation.');assert.match(failure.message,/owned|helper|digest|resource|inventory|changed|modified/i);noForbiddenWorkflow(f.root);
});

test('timestamp-valid bytecode cannot replace verified workflow source or execute a cached guard',async t=>{
 const f=await fixture(t,{rows:[row('cache-guarded','editor',{anchor:'before'})],ids:['editor']}),state=workflow(f),{files}=build(f),packageRoot=mount(f,files),helper=path.join(packageRoot,'scripts/workflow-state.py'),originalSource=fs.readFileSync(helper),originalManifest=read(packageRoot,manifestPath),marker=path.join(f.base,'forged-workflow-cache-executed');
 assert.equal(manifest(files).owned_resources['scripts/workflow-state.py'],composer.hash(originalSource));
 const forged='from pathlib import Path\nPath('+JSON.stringify(marker)+').write_text("forged cached helper executed")\nclass Store:\n def __init__(self,root,**options):\n  self.base=Path(root)/".skill-tree"; self.future=self.base/"documents/future.md"\n def text(self): return "forged task scope"\ndef parse(value): return []\ndef resolve(tasks,identities,queue): return [{"id":identity,"status":"Ready","parent_pending_ids":[]} for identity in identities]\n';
 const control=python(helper,f.root,String.raw`import hashlib,importlib.util,json,marshal,struct,sys
from pathlib import Path
source=Path(sys.argv[1]);original=source.read_bytes();stat=source.stat();cache=Path(importlib.util.cache_from_source(str(source)))
code=compile(sys.argv[3],str(source),'exec');header=importlib.util.MAGIC_NUMBER+struct.pack('<III',0,int(stat.st_mtime)&0xffffffff,len(original)&0xffffffff)
cache.parent.mkdir(parents=True,exist_ok=True);cache.write_bytes(header+marshal.dumps(code))
assert source.read_bytes()==original
print(json.dumps({'cache_file':str(cache),'source_sha256':hashlib.sha256(original).hexdigest()}))`,forged);
 assert.equal(control.source_sha256,composer.hash(originalSource));assert.deepEqual(fs.readFileSync(helper),originalSource);assert.deepEqual(read(packageRoot,manifestPath),originalManifest);const originalCache=fs.readFileSync(control.cache_file),before=metadataBytes(f.root);
 const result=api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,'before'),context:{kind:'pending',id:'actual-pending-scope',pending_ids:[state.pending_id]},capabilities:[]});
 assert.equal(fs.existsSync(marker),false,'A timestamp-valid cache replaced the verified owned workflow source.');assert.equal(result.status,'prerequisite');assert.equal(result.guard.kind,'actual-owned-scope');
 assert.throws(()=>api().prepareBoundary(packageRoot,{project_root:f.root,event:event(processing,'before'),context:{kind:'pending',id:'forged-pending-scope',pending_ids:['P-11111111-1111-4111-8111-111111111111']},capabilities:[]}),/actual|selected|Pending|pending|scope/i);
 assert.equal(fs.existsSync(marker),false);assert.deepEqual(fs.readFileSync(control.cache_file),originalCache,'Existing bytecode belongs to the fixture and must remain untouched.');assert.deepEqual(fs.readFileSync(helper),originalSource);assert.deepEqual(read(packageRoot,manifestPath),originalManifest);assert.deepEqual(metadataBytes(f.root),before);
});
