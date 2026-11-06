'use strict';
// Copied fixtures establish resource/bridge behavior, never actual native plugin invocation.
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const composer=require('../lib/composer.js'),installation=require('../lib/installation.js');
const core=path.resolve(__dirname,'..'),operations=Object.keys(require('../templates/operations.json')).sort();
function write(root,relative,value){const file=path.join(root,relative);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,Buffer.isBuffer(value)||typeof value==='string'?value:JSON.stringify(value));}
function files(root){const out={};function visit(relative){for(const e of fs.readdirSync(path.join(root,relative),{withFileTypes:true})){const next=path.posix.join(relative,e.name);assert.equal(e.isSymbolicLink(),false);if(e.isDirectory())visit(next);else out[next]=fs.readFileSync(path.join(root,next));}}visit('');return out;}
function python(args,cwd,expected=0){const run=spawnSync('python3',['-I','-B',...args],{cwd,encoding:'utf8',timeout:30000});assert.equal(run.status,expected,run.stdout+run.stderr);return run.stdout;}
function noFuture(root){for(const relative of ['.skill-tree/documents/future.md','.skill-tree/documents/future.json','.skill-tree/clarifications','.skill-tree/installation'])assert.equal(fs.existsSync(path.join(root,relative)),false,'Task-free runtime created forbidden state: '+relative);}
for(const flavor of ['general','web','unity'])test(flavor+' copied invocation bridge retains all registered operation closures without source siblings or Future',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-standalone-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const source=path.join(base,'source'),project=path.join(base,'project');fs.mkdirSync(source);fs.mkdirSync(project);
 for(const relative of Object.keys(composer.sourceInputs(core)))write(source,relative,fs.readFileSync(path.join(core,relative)));
 write(project,'package.json',{scripts:{test:'node --test'}});
 if(flavor==='unity'){write(project,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(project,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(project,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 installation.install(project,source,flavor,operations.map(name=>({name,provider:'codex',rel:'.agents/skills/'+name})));
 const snapshots=Object.fromEntries(operations.map(name=>[name,files(path.join(project,'.agents/skills',name))]));
 fs.rmSync(source,{recursive:true});fs.rmSync(project,{recursive:true});
 for(const name of operations){
  const standalone=path.join(base,'only-operation'),runtime=path.join(base,'task-free-runtime');fs.mkdirSync(standalone);fs.mkdirSync(runtime);
  for(const [relative,bytes]of Object.entries(snapshots[name]))write(standalone,relative,bytes);
  const scripts=path.join(standalone,'scripts');
  for(const helper of ['plugin-invocation.py','workflow-state.py','plugin-hooks.js','plugin-composition.js','plugin-bindings.js','plugin-parameters.js','plugin-registry.js','plugin-sources.js'])assert.ok(fs.existsSync(path.join(scripts,helper)),name+' requires its own '+helper);
  const manifest=JSON.parse(fs.readFileSync(path.join(standalone,'references/plugin-bindings.json'),'utf8'));
  assert.equal(manifest.operation,name);assert.deepEqual(manifest.definitions,[]);assert.deepEqual(Object.keys(manifest.packages),[]);
  const program='import importlib.util,json,pathlib,sys\nroot=pathlib.Path(sys.argv[1])\ndef load(name):\n path=root/(name+".py");spec=importlib.util.spec_from_file_location("copied_"+name,path);module=importlib.util.module_from_spec(spec);exec(compile(path.read_bytes(),str(path),"exec"),module.__dict__);return module\nw=load("workflow-state");h=load("plugin-invocation")\nassert all(callable(getattr(h,n,None)) for n in ["start","read","next_action","mutate","pending_scan"])\nassert h.pending_scan(w.Store(pathlib.Path(sys.argv[2]),allow_unselected=True,neutral=True))==[]\nprint(json.dumps({"owned_helper":"available","pending":0}))\n';
  assert.deepEqual(JSON.parse(python(['-c',program,scripts,runtime],runtime)),{owned_helper:'available',pending:0});noFuture(runtime);
  const input=path.join(base,'read-unknown.json');write(base,'read-unknown.json',{chain_id:'HC-11111111-1111-4111-8111-111111111111'});
  const result=JSON.parse(python([path.join(scripts,'workflow-state.py'),'hook-read',runtime,'--input',input],runtime,2));assert.equal(result.ok,false);assert.match(JSON.stringify(result),/chain|identity|invocation|unknown/i);noFuture(runtime);
  const context={kind:'request',id:'copied-no-hook-request',semantic_fingerprint:'a'.repeat(64),content_fingerprint:'b'.repeat(64)};
  const empty={package_root:standalone,request_id:'core-only-'+name,event:{id:'empty-event',operation:name,anchor:'before'},context,mode:'manual',authority:{id:'copied-grant',revision:1,context_id:context.id,allowed_kinds:['technical'],constraints:['Task-free fixture only.'],evidence:{kind:'owner-message',reference:'Scripted isolated fixture grant; not actual human approval.'}},executor:{id:'copied-executor',context_id:'copied-executor-context'}};
  write(base,'no-hook-input.json',empty);
  const noop=JSON.parse(python([path.join(scripts,'workflow-state.py'),'hook-start',runtime,'--input',path.join(base,'no-hook-input.json')],runtime));
  assert.equal(noop.status,'noop');assert.ok(!noop.chain_id&&!noop.id,'An empty optional hook set creates no chain.');
  assert.equal(fs.existsSync(path.join(runtime,'.skill-tree/invocations')),false);noFuture(runtime);
  assert.equal(fs.existsSync(path.join(standalone,'plugins')),false,'Core-only installation contains no external plugin package.');
  fs.rmSync(standalone,{recursive:true});fs.rmSync(runtime,{recursive:true});
 }
});

test('copied hook entry loads verified Python source instead of timestamp-valid alternate bytecode',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-cache-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project'),standalone=path.join(base,'only-operation'),runtime=path.join(base,'runtime');
 fs.mkdirSync(project);fs.mkdirSync(runtime);write(project,'package.json',{scripts:{test:'node --test'}});
 const name='skill-tree-add-pending-task';installation.install(project,core,'general',[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 fs.cpSync(path.join(project,'.agents/skills',name),standalone,{recursive:true});fs.rmSync(project,{recursive:true});
 const helper=path.join(standalone,'scripts/workflow-state.py'),module=path.join(standalone,'scripts/plugin-invocation.py');
 assert.ok(fs.existsSync(module),'The copied operation must contain the owned runtime helper.');
 const source=fs.readFileSync(module),marker=path.join(base,'unreviewed-cache-executed');
 const program='import importlib.util,json,marshal,pathlib,struct,sys\np=pathlib.Path(sys.argv[1]);marker=sys.argv[2]\ncode=compile("from pathlib import Path\\nPath("+repr(marker)+").write_text(\'unreviewed cache ran\')\\n",str(p),"exec")\ncache=pathlib.Path(importlib.util.cache_from_source(str(p)));cache.parent.mkdir(parents=True,exist_ok=True)\nheader=importlib.util.MAGIC_NUMBER+struct.pack("<III",0,int(p.stat().st_mtime)&0xffffffff,p.stat().st_size)\ncache.write_bytes(header+marshal.dumps(code))\nprint(json.dumps({"cache":str(cache)}))\n';
 const cache=JSON.parse(python(['-c',program,module,marker],runtime)).cache,beforeCache=fs.readFileSync(cache);
 write(base,'unknown-chain.json',{chain_id:'HC-11111111-1111-4111-8111-111111111111'});
 const run=spawnSync('python3',['-I','-B',helper,'hook-read',runtime,'--input',path.join(base,'unknown-chain.json')],{cwd:runtime,encoding:'utf8',timeout:30000});
 assert.equal(fs.existsSync(marker),false,'Timestamp-valid unreviewed cache executed before source validation.');
 assert.equal(run.status,2,run.stdout+run.stderr);assert.equal(JSON.parse(run.stdout).ok,false);
 assert.deepEqual(fs.readFileSync(module),source);assert.deepEqual(fs.readFileSync(cache),beforeCache,'The source-only path must preserve existing cache bytes.');noFuture(runtime);
});

test('a task-free prepared invocation blocks installation until the original attempt is reconciled',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-install-barrier-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project');fs.mkdirSync(project);write(project,'package.json',{scripts:{test:'node --test'}});
 installation.install(project,core,'general',[{name:'skill-tree-add-pending-task',provider:'codex',rel:'.agents/skills/skill-tree-add-pending-task'}]);
 const effective=require('../lib/plugin-parameters.js').resolveParameters({run:{values:{marker:'barrier-only'},instructions:'Inert controlled fixture.'}});
 const row={id:'barrier-occurrence',plugin_id:'controlled',operation:'skill-tree-add-pending-task',anchor:'before',enabled:true,effective,package_identity:{revision:'a'.repeat(40),content_digest:'d'.repeat(64)}};
 const context={kind:'request',id:'barrier-request',semantic_fingerprint:'a'.repeat(64),content_fingerprint:'b'.repeat(64)};
 const request={request_id:'task-free-install-barrier',event:{id:'barrier-event',operation:row.operation,anchor:row.anchor},context,mode:'manual',authority:{id:'barrier-grant',revision:1,context_id:context.id,allowed_kinds:['technical'],constraints:['Synthetic metadata fixture.'],evidence:{kind:'owner-message',reference:'Scripted fixture grant; no real-human installation approval.'}},executor:{id:'barrier-executor',context_id:'barrier-executor-context'},configuration:{configuration_digest:'c'.repeat(64),bindings:[row],packages:{controlled:{revision:'a'.repeat(40),content_digest:'d'.repeat(64),entry:'plugins/controlled/upstream/SKILL.md',resources:{'SKILL.md':'e'.repeat(64)}}},run_overrides:{}}};
 write(base,'request.json',request);
 const create='import importlib.util,json,pathlib,sys\ncore=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);p=json.load(open(sys.argv[3]))\ndef load(name):\n file=core/"common/scripts"/(name+".py");spec=importlib.util.spec_from_file_location("fixture_"+name,file);module=importlib.util.module_from_spec(spec);exec(compile(file.read_bytes(),str(file),"exec"),module.__dict__);return module\nw=load("workflow-state");h=load("plugin-invocation");s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False)\nproof={"configuration_digest":p["configuration"]["configuration_digest"],"context":p["context"],"event":p["event"],"bindings":p["configuration"]["bindings"],"unresolved":[],"prerequisites":[],"execution_snapshot":{"controlled-owned-module":"f"*64}}\nc=h.start(s,p,proof=proof);actor={"id":"barrier-actor","context_id":"barrier-actor-context"}\nc=h.mutate(s,"prepare",{"chain_id":c["id"],"expected_chain_hash":c["chain_hash"],"expected_chain_revision":c["revision"],"actor":actor,"creation_evidence":{"kind":"host-agent-created","provider":"controlled-unit-host","tool":"controlled-create","reference":"Synthetic prepared original, no native call.","actor_id":actor["id"],"actor_context_id":actor["context_id"]}},proof=proof)\nprint(json.dumps({"chain_id":c["id"],"attempt_id":c["prepared_attempt_id"]}))\n';
 const started=JSON.parse(python(['-c',create,core,project,path.join(base,'request.json')],project));
 assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.md')),false);
 assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.json')),false);
 const record=path.join(project,'.skill-tree/invocations',started.chain_id.toLowerCase()+'.json'),before=fs.readFileSync(record),profile=fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json'));
 assert.equal(installation.hasActiveOperation(project),true,'A missing Future must not hide the prepared task-free original.');
 assert.throws(()=>installation.refresh(project,core),/active|pending|invocation|handoff|stop/i);
 assert.deepEqual(fs.readFileSync(record),before);assert.deepEqual(fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json')),profile);
 const reconcile='import importlib.util,json,pathlib,sys\ncore=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2])\ndef load(name):\n file=core/"common/scripts"/(name+".py");spec=importlib.util.spec_from_file_location("fixture_"+name,file);module=importlib.util.module_from_spec(spec);exec(compile(file.read_bytes(),str(file),"exec"),module.__dict__);return module\nw=load("workflow-state");h=load("plugin-invocation");s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False);c=h.read(s,sys.argv[3])\nh.mutate(s,"reconcile",{"chain_id":c["id"],"expected_chain_hash":c["chain_hash"],"expected_chain_revision":c["revision"],"attempt_id":sys.argv[4],"status":"cancelled","evidence":{"kind":"host-reconciliation","reference":"Synthetic original cancellation before actual dispatch."}})\nprint(json.dumps({"pending":len(h.pending_scan(s))}))\n';
 assert.deepEqual(JSON.parse(python(['-c',reconcile,core,project,started.chain_id,started.attempt_id],project)),{pending:0});
 assert.equal(installation.hasActiveOperation(project),false);assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.json')),false);
});

test('private delivery resolves JSON secret values only into the adapter context while ordinary state keeps references',async t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-private-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project'),upstream=path.join(base,'upstream'),name='skill-tree-add-pending-task';fs.mkdirSync(project);fs.mkdirSync(upstream);
 write(project,'package.json',{scripts:{test:'node --test'}});write(upstream,'SKILL.md','---\nname: controlled-private-input\n---\nRead controlled invocation data without executing helpers.\n');
 installation.install(project,core,'general',[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 const values={token:{$secret:'fixture-token'},nested:[{$secret:'fixture-object'},1e-7,'🧩'],authority:{permission:'ordinary parameter data'}};
 const row={id:'private-occurrence',plugin_id:'private-fixture',operation:name,anchor:'before',enabled:true,parameters:values,instructions:'EXTRA-PRIVATE-MARKER'};
 const lifecycle=require('../lib/plugin-lifecycle.js'),proposal=await lifecycle.prepareProposal(project,{request_id:'private-fixture-install',operation:'install',sources:[{id:'private-fixture',path:upstream}],bindings:[row]});
 lifecycle.applyProposal(project,proposal,{proposal_digest:proposal.digest});installation.refresh(project,core);
 const packageRoot=path.join(project,'.agents/skills',name),runtime=require('../lib/plugin-runtime.js');
 const context={kind:'request',id:'private-request',semantic_fingerprint:'a'.repeat(64),content_fingerprint:'b'.repeat(64)};
 const request={project_root:project,event:{id:'private-event',operation:name,anchor:'before'},context,capabilities:['codex-source-backed-context']};
 const frozen=runtime.freezePlan(packageRoot,request);assert.deepEqual(frozen.proof.prerequisites,[]);
 const start={request_id:'private-engine-chain',event:frozen.proof.event,context:frozen.proof.context,mode:'manual',authority:{id:'private-grant',revision:1,context_id:context.id,allowed_kinds:['technical'],constraints:['Synthetic private delivery fixture; no service credentials or native actor execution.'],evidence:{kind:'owner-message',reference:'Scripted fixture grant; no actual human approval.'}},executor:{id:'private-executor',context_id:'private-executor-context'},configuration:frozen.configuration};
 write(base,'public-start.json',{start,proof:frozen.proof});
 const startProgram='import importlib.util,json,pathlib,sys\ncore=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);p=json.load(open(sys.argv[3]))\ndef load(name):\n file=core/"common/scripts"/(name+".py");spec=importlib.util.spec_from_file_location("private_"+name,file);module=importlib.util.module_from_spec(spec);exec(compile(file.read_bytes(),str(file),"exec"),module.__dict__);return module\nw=load("workflow-state");h=load("plugin-invocation");s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False);c=h.start(s,p["start"],proof=p["proof"]);actor={"id":"private-actor","context_id":"private-actor-context"}\nc=h.mutate(s,"prepare",{"chain_id":c["id"],"expected_chain_hash":c["chain_hash"],"expected_chain_revision":c["revision"],"actor":actor,"creation_evidence":{"kind":"host-agent-created","provider":"controlled-unit-host","tool":"controlled-create","reference":"Synthetic private adapter context; no real host creation.","actor_id":actor["id"],"actor_context_id":actor["context_id"]}},proof=p["proof"])\nprint(json.dumps(c))\n';
 const chain=JSON.parse(python(['-c',startProgram,core,project,path.join(base,'public-start.json')],project)),attempt=chain.attempts[chain.prepared_attempt_id];
 const input={...request,configuration:frozen.configuration,chain_id:chain.id,attempt_id:attempt.id,binding_id:row.id,public_input:attempt.input,input_digest:attempt.input_digest,authority:chain.authority};
 const secretToken='CONTROLLED-'+require('node:crypto').randomUUID(),secretObject={value:'OBJECT-'+require('node:crypto').randomUUID()},calls=[];
 const resolve=name=>{assert.equal(fs.existsSync(path.join(project,'.skill-tree/.writer-lock')),false,'Secret resolution must occur outside the metadata writer lock.');calls.push(name);if(name==='fixture-token')return secretToken;if(name==='fixture-object')return secretObject;throw Error('Unknown controlled secret reference.');};
 assert.throws(()=>runtime.deliveryData(packageRoot,input),/secret provider|secret reference|invocation.context/i);
 assert.throws(()=>runtime.deliveryData(packageRoot,{...input,authority:{...chain.authority,revision:99}},resolve),/sealed.*authority/i);
 assert.throws(()=>runtime.deliveryData(packageRoot,{...input,public_input:{...attempt.input,execution_policy:{allowed_tools:['invented'],allowed_actions:['publish']}}},resolve),/sealed.*tools|sealed.*actions/i);
 assert.throws(()=>runtime.deliveryData(packageRoot,{...input,public_input:{...attempt.input,context:{...context,id:'different-context'}}},resolve),/authority|sealed.*context/i);
 const delivery=runtime.deliveryData(packageRoot,input,resolve);let observed;
 const adapterSpy=payload=>{observed=JSON.parse(JSON.stringify(payload));};adapterSpy(delivery.payload);
 assert.deepEqual([...calls].sort(),['fixture-object','fixture-token']);
 assert.equal(observed.parameters.token,secretToken);assert.deepEqual(observed.parameters.nested,[secretObject,1e-7,'🧩']);
 assert.deepEqual(observed.parameters.authority,{permission:'ordinary parameter data'});assert.deepEqual(observed.context,context);
  assert.deepEqual(observed.authority,chain.authority);assert.equal(observed.authority_digest,attempt.input.authority_digest);
  assert.equal(observed.mode,chain.mode);assert.ok(Array.isArray(observed.allowed_tools)&&observed.allowed_tools.length);
  assert.ok(Array.isArray(observed.allowed_actions)&&observed.allowed_actions.length);
 assert.equal(observed.extra_instructions,'EXTRA-PRIVATE-MARKER');assert.equal(delivery.contains_secrets,true);
 assert.equal(delivery.configuration_parameter_digest,attempt.input.parameter_digest);assert.notEqual(delivery.resolved_parameter_digest,delivery.configuration_parameter_digest);
 assert.throws(()=>runtime.deliveryData(packageRoot,input,()=>{throw Error(secretToken);}),error=>error.code==='runtime-secret'&&!error.message.includes(secretToken));
 const publicDelivery={input_digest:delivery.input_digest,delivery_digest:delivery.delivery_digest,resolved_parameter_digest:delivery.resolved_parameter_digest};
 write(base,'public-invoke.json',{chain_id:chain.id,attempt_id:attempt.id,proof:{...frozen.proof,delivery:publicDelivery},...publicDelivery});
 const invokeProgram='import importlib.util,json,pathlib,sys\ncore=pathlib.Path(sys.argv[1]);root=pathlib.Path(sys.argv[2]);p=json.load(open(sys.argv[3]))\ndef load(name):\n file=core/"common/scripts"/(name+".py");spec=importlib.util.spec_from_file_location("private_"+name,file);module=importlib.util.module_from_spec(spec);exec(compile(file.read_bytes(),str(file),"exec"),module.__dict__);return module\nw=load("workflow-state");h=load("plugin-invocation");s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False);c=h.read(s,p["chain_id"]);a=c["attempts"][p["attempt_id"]]\nc=h.mutate(s,"invoke",{"chain_id":c["id"],"expected_chain_hash":c["chain_hash"],"expected_chain_revision":c["revision"],"attempt_id":a["id"],"input_digest":p["input_digest"],"delivery_digest":p["delivery_digest"],"resolved_parameter_digest":p["resolved_parameter_digest"],"evidence":{"kind":"host-invoked","provider":"controlled-unit-host","tool":"controlled-private-spy","reference":"Synthetic in-memory private adapter spy, not actual native execution.","actor_id":a["actor"]["id"],"actor_context_id":a["actor"]["context_id"],"mechanism":"source-backed-context"}},proof=p["proof"])\nprint(json.dumps(c))\n';
 const ordinary=JSON.parse(python(['-c',invokeProgram,core,project,path.join(base,'public-invoke.json')],project));
 const previews=JSON.stringify({frozen,original:chain,current:ordinary,publicDelivery});
 assert.ok(!previews.includes(secretToken)&&!previews.includes(secretObject.value));
 assert.deepEqual(ordinary.configuration.bindings[0].effective.values,values);
 const ledger=fs.readFileSync(path.join(project,'.skill-tree/invocations',chain.id.toLowerCase()+'.json'),'utf8');
 assert.ok(!ledger.includes(secretToken)&&!ledger.includes(secretObject.value));assert.ok(ledger.includes('fixture-token'));
 assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.json')),false);
});

test('copied direct workflow entry rejects changed owned runtime source before import side effects',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-source-drift-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project'),standalone=path.join(base,'only-operation'),runtime=path.join(base,'runtime');
 fs.mkdirSync(project);fs.mkdirSync(runtime);write(project,'package.json',{scripts:{test:'node --test'}});
 const name='skill-tree-add-pending-task';installation.install(project,core,'general',[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 fs.cpSync(path.join(project,'.agents/skills',name),standalone,{recursive:true});fs.rmSync(project,{recursive:true});
 const helper=path.join(standalone,'scripts/workflow-state.py'),module=path.join(standalone,'scripts/plugin-invocation.py');
 assert.ok(fs.existsSync(module),'The owned runtime source is part of the copied closure.');
 const marker=path.join(base,'changed-source-executed'),original=fs.readFileSync(module);
 fs.writeFileSync(module,'from pathlib import Path\nPath('+JSON.stringify(marker)+').write_text("unreviewed import executed")\n'+original.toString('utf8'));
 write(base,'unknown-source-chain.json',{chain_id:'HC-11111111-1111-4111-8111-111111111111'});
 const run=spawnSync('python3',['-I','-B',helper,'hook-read',runtime,'--input',path.join(base,'unknown-source-chain.json')],{cwd:runtime,encoding:'utf8',timeout:30000});
 assert.equal(fs.existsSync(marker),false,'Changed owned helper source executed before ownership verification.');
 assert.equal(run.status,2,run.stdout+run.stderr);const result=JSON.parse(run.stdout);assert.equal(result.ok,false);
 assert.match(JSON.stringify(result),/owned|resource|digest|source|inventory|changed/i);noFuture(runtime);
});


test('copied PR entry verifies owned inventory before loading workspace helpers',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-hook-pr-source-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project'),standalone=path.join(base,'only-operation'),runtime=path.join(base,'runtime');
 fs.mkdirSync(project);fs.mkdirSync(runtime);write(project,'package.json',{scripts:{test:'node --test'}});
 const name='skill-tree-pr-review-cycle';installation.install(project,core,'general',[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 fs.cpSync(path.join(project,'.agents/skills',name),standalone,{recursive:true});fs.rmSync(project,{recursive:true});
 const helper=path.join(standalone,'scripts/pr-review-state.py'),module=path.join(standalone,'scripts/run-workspaces.py'),marker=path.join(base,'changed-workspace-executed');
 fs.writeFileSync(module,'from pathlib import Path\nPath('+JSON.stringify(marker)+').write_text("unreviewed import executed")\n'+fs.readFileSync(module,'utf8'));
 const run=spawnSync('python3',['-I','-B',helper,'--help'],{cwd:runtime,encoding:'utf8',timeout:30000});
 assert.equal(fs.existsSync(marker),false);assert.equal(run.status,2,run.stdout+run.stderr);assert.equal(JSON.parse(run.stdout).ok,false);noFuture(runtime);
});

for(const flavor of ['general','web','unity'])test(flavor+' managed registry loss holds the copied bridge while an independent source-free copy stays usable',async t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-managed-registry-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const source=path.join(base,'source'),project=path.join(base,'project'),upstream=path.join(base,'upstream'),standalone=path.join(base,'only-operation'),runtime=path.join(base,'independent-runtime'),name='skill-tree-add-pending-task';
 fs.mkdirSync(source);fs.mkdirSync(project);fs.mkdirSync(upstream);fs.mkdirSync(runtime);
 for(const relative of Object.keys(composer.sourceInputs(core)))write(source,relative,fs.readFileSync(path.join(core,relative)));
 write(project,'package.json',{scripts:{test:'node --test'}});write(upstream,'SKILL.md','# Controlled plugin\nRead [marker](marker.json) and return a bounded proposal.\n');write(upstream,'marker.json',{marker:'controlled-source-closure'});
 if(flavor==='unity'){write(project,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(project,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(project,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 installation.install(project,source,flavor,[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 const lifecycle=require('../lib/plugin-lifecycle.js'),registry=require('../lib/plugin-registry.js'),proposal=await lifecycle.prepareProposal(project,{request_id:'managed-copy-install',operation:'install',sources:[{id:'controlled',path:upstream}],bindings:[{id:'controlled-before',plugin_id:'controlled',operation:name,anchor:'before',enabled:true,parameters:{marker:'controlled-input'}}]});
 lifecycle.applyProposal(project,proposal,{proposal_digest:proposal.digest});installation.refresh(project,source);
 const packageRoot=path.join(project,'.agents/skills',name),script=path.join(packageRoot,'scripts/plugin-hooks.js'),event={id:'managed-copy-event',operation:name,anchor:'before'},context={kind:'request',id:'managed-copy-request',semantic_fingerprint:'a'.repeat(64),content_fingerprint:'b'.repeat(64)},request={runtime_action:'freeze-chain',project_root:project,event,context,capabilities:['codex-source-backed-context']};
 function prepare(script,packet){const input=path.join(base,'request.json');fs.writeFileSync(input,JSON.stringify(packet));const run=spawnSync(process.execPath,[script,'--input',input],{cwd:base,encoding:'utf8',timeout:30000});assert.equal(run.status,0,run.stdout+run.stderr);return JSON.parse(run.stdout);}
 const original=prepare(script,request);assert.deepEqual(original.proof.prerequisites,[]);
 fs.unlinkSync(path.join(project,registry.REGISTRY));
 for(const packet of [request,{...request,runtime_action:'occurrence-plan',configuration:original.configuration}]){
  const result=prepare(script,packet),proof=result.proof||result;assert.ok(proof.prerequisites.length,'Registry absence at the actual owned destination must remain a prerequisite.');assert.match(JSON.stringify(proof.prerequisites),/registry|profile|ownership|association|configuration/i);
 }
 const program=String.raw`import importlib.util,json,pathlib,sys
p=pathlib.Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('managed_copied_workflow',p);w=importlib.util.module_from_spec(spec);exec(compile(p.read_bytes(),str(p),'exec'),w.__dict__)
root=pathlib.Path(sys.argv[2]);s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False);package=p.parent.parent
context={'kind':'request','id':'managed-bridge-request'}
grant={'id':'managed-bridge-grant','revision':1,'context_id':context['id'],'allowed_kinds':['technical'],'constraints':['Controlled fixture only; no native actor or external actions.'],'evidence':{'kind':'owner-message','reference':'Scripted isolated test configuration, not actual human approval.'}}
c=w.hook_action(s,'hook-start',{'request_id':'managed-bridge-chain','package_root':str(package),'event':{'id':'managed-bridge-event','operation':'skill-tree-add-pending-task','anchor':'before'},'context':context,'mode':'manual','authority':grant,'executor':{'id':'controlled-parent','context_id':'controlled-parent-context'},'capabilities':['codex-source-backed-context']})
next_action=w.hook_action(s,'hook-next',{'chain_id':c['id']});held=False
try:
 w.hook_action(s,'hook-prepare',{'chain_id':c['id'],'expected_chain_hash':c['chain_hash'],'expected_chain_revision':c['revision'],'actor':{'id':'synthetic-held-actor','context_id':'synthetic-held-context'},'creation_evidence':{'kind':'host-agent-created','provider':'controlled-unit-host','tool':'controlled-fixture','reference':'Synthetic metadata input; no actual actor was created.','actor_id':'synthetic-held-actor','actor_context_id':'synthetic-held-context'}})
except w.WorkflowError:held=True
after=w.hook_action(s,'hook-read',{'chain_id':c['id']})
print(json.dumps({'action':next_action['action'],'held':held,'attempts':len(after['attempts']),'cursor':after['cursor'],'future_created':s.future.exists()}))`;
 const bridge=JSON.parse(python(['-c',program,path.join(packageRoot,'scripts/workflow-state.py'),project],project));assert.deepEqual(bridge,{action:'prerequisite',held:true,attempts:0,cursor:0,future_created:false});
 for(const forbidden of ['installation.js','composer.js'])assert.equal(fs.existsSync(path.join(packageRoot,'scripts',forbidden)),false,'The operation must not gain an installer dependency.');
 fs.cpSync(packageRoot,standalone,{recursive:true});fs.rmSync(project,{recursive:true});fs.rmSync(source,{recursive:true});fs.rmSync(upstream,{recursive:true});
 const copiedScript=path.join(standalone,'scripts/plugin-hooks.js'),independent={...request,project_root:runtime},copied=prepare(copiedScript,independent);assert.deepEqual(copied.proof.prerequisites,[]);assert.equal(copied.proof.bindings.length,1);
 assert.deepEqual(prepare(copiedScript,{...independent,runtime_action:'occurrence-plan',configuration:copied.configuration}).prerequisites,[]);noFuture(runtime);
});

for(const flavor of ['general','web','unity'])test(flavor+' executable copied CLI and workflow retain an owned symlink entry claim',async t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-owned-entry-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const project=path.join(base,'project'),upstream=path.join(base,'upstream'),relocated=path.join(base,'relocated-operation'),name='skill-tree-add-pending-task';fs.mkdirSync(project);fs.mkdirSync(upstream);
 write(project,'package.json',{scripts:{test:'node --test'}});write(upstream,'SKILL.md','# Controlled owned entry\nReturn a bounded proposal.\n');
 if(flavor==='unity'){write(project,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(project,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(project,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 installation.install(project,core,flavor,[{name,provider:'codex',rel:'.agents/skills/'+name}]);
 const lifecycle=require('../lib/plugin-lifecycle.js'),registry=require('../lib/plugin-registry.js'),proposal=await lifecycle.prepareProposal(project,{request_id:'owned-entry-install',operation:'install',sources:[{id:'controlled',path:upstream}],bindings:[{id:'owned-entry',plugin_id:'controlled',operation:name,anchor:'before',enabled:true}]});lifecycle.applyProposal(project,proposal,{proposal_digest:proposal.digest});installation.refresh(project,core);
 const packageRoot=path.join(project,'.agents/skills',name),script=path.join(packageRoot,'scripts/plugin-hooks.js'),request={runtime_action:'freeze-chain',project_root:project,event:{id:'owned-entry-event',operation:name,anchor:'before'},context:{kind:'request',id:'owned-entry-context'},capabilities:['codex-source-backed-context']};
 const run=packet=>spawnSync(process.execPath,[script,'--input','-'],{input:JSON.stringify(packet),encoding:'utf8',timeout:30000}),initial=run(request);assert.equal(initial.status,0,initial.stdout+initial.stderr);const frozen=JSON.parse(initial.stdout);assert.deepEqual(frozen.proof.prerequisites,[]);
 const profile=fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json'));fs.renameSync(packageRoot,relocated);fs.symlinkSync(relocated,packageRoot,'dir');fs.unlinkSync(path.join(project,registry.REGISTRY));
 const assertHeldCLI=()=>{for(const packet of [request,{...request,runtime_action:'occurrence-plan',configuration:frozen.configuration}]){const prepared=run(packet);if(prepared.status===0){const value=JSON.parse(prepared.stdout),proof=value.proof||value;assert.ok(proof.prerequisites.length||proof.unresolved.length,'Executable owned symlink entry silently supplied an executable proof');assert.match(JSON.stringify([proof.prerequisites,proof.unresolved]),/registry|profile|ownership|association|configuration|receipt|symlink/i);}else assert.match(prepared.stderr,/registry|profile|ownership|association|configuration|receipt|symlink/i);}};assertHeldCLI();
 const program=String.raw`import importlib.util,json,pathlib,sys
p=pathlib.Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('owned_entry_workflow',p);w=importlib.util.module_from_spec(spec);exec(compile(p.read_bytes(),str(p),'exec'),w.__dict__)
root=pathlib.Path(sys.argv[2]);package=pathlib.Path(sys.argv[3]);s=w.Store(root,allow_unselected=True,neutral=True,route_queue=False)
context={'kind':'request','id':'owned-entry-bridge-context'}
grant={'id':'owned-entry-grant','revision':1,'context_id':context['id'],'allowed_kinds':['technical'],'constraints':['Controlled metadata only; no actual actor or external action.'],'evidence':{'kind':'owner-message','reference':'Scripted isolated fixture grant, not actual human approval.'}}
held=False;attempts=0
try:
 c=w.hook_action(s,'hook-start',{'request_id':sys.argv[4],'package_root':str(package),'event':{'id':'owned-entry-bridge-event','operation':'skill-tree-add-pending-task','anchor':'before'},'context':context,'mode':'manual','authority':grant,'executor':{'id':'controlled-parent','context_id':'controlled-parent-context'},'capabilities':['codex-source-backed-context']})
 current=w.hook_action(s,'hook-next',{'chain_id':c['id']});held=current['action']=='prerequisite';attempts=len(w.hook_action(s,'hook-read',{'chain_id':c['id']})['attempts'])
except w.WorkflowError as error:
 if not any(word in str(error).lower() for word in ['registry','profile','ownership','association','configuration','receipt','symlink']):raise
 held=True
print(json.dumps({'held':held,'attempts':attempts,'future_created':s.future.exists()}))`;
 const bridge=JSON.parse(python(['-c',program,path.join(packageRoot,'scripts/workflow-state.py'),project,packageRoot,'owned-entry-chain-readable'],project));assert.deepEqual(bridge,{held:true,attempts:0,future_created:false});
 write(project,'.skill-tree/installation/profile.json','{unreadable relevant ownership profile');assertHeldCLI();
 const opaqueBridge=JSON.parse(python(['-c',program,path.join(packageRoot,'scripts/workflow-state.py'),project,packageRoot,'owned-entry-chain-opaque'],project));assert.deepEqual(opaqueBridge,{held:true,attempts:0,future_created:false});
 fs.writeFileSync(path.join(project,'.skill-tree/installation/profile.json'),profile);
 assert.equal(fs.lstatSync(packageRoot).isSymbolicLink(),true);assert.deepEqual(fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json')),profile);assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.md')),false);assert.equal(fs.existsSync(path.join(project,'.skill-tree/documents/future.json')),false);
});

for(const flavor of ['general','web','unity'])test(flavor+' copied CLI provides distinct read-only completed readiness without source siblings',async t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-readiness-entry-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));const project=path.join(base,'project'),upstream=path.join(base,'upstream'),standalone=path.join(base,'standalone'),runtime=path.join(base,'runtime'),name='skill-tree-add-pending-task';fs.mkdirSync(project);fs.mkdirSync(upstream);fs.mkdirSync(runtime);write(project,'package.json',{scripts:{test:'node --test'}});write(upstream,'SKILL.md','# Controlled retained readiness\nReturn a bounded proposal.\n');
 if(flavor==='unity'){write(project,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(project,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(project,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 installation.install(project,core,flavor,[{name,provider:'codex',rel:'.agents/skills/'+name}]);const lifecycle=require('../lib/plugin-lifecycle.js'),registry=require('../lib/plugin-registry.js'),proposal=await lifecycle.prepareProposal(project,{request_id:'readiness-entry-install',operation:'install',sources:[{id:'controlled',path:upstream}],bindings:[{id:'retained-entry',plugin_id:'controlled',operation:name,anchor:'before',enabled:true}]});lifecycle.applyProposal(project,proposal,{proposal_digest:proposal.digest});installation.refresh(project,core);
 const packageRoot=path.join(project,'.agents/skills',name),request={project_root:project,event:{id:'retained-readiness-event',operation:name,anchor:'before'},context:{kind:'request',id:'retained-readiness-context'},capabilities:['codex-source-backed-context']};
 const run=(root,packet)=>{const value=spawnSync(process.execPath,[path.join(root,'scripts/plugin-hooks.js'),'--input','-'],{input:JSON.stringify(packet),encoding:'utf8',timeout:30000});assert.equal(value.status,0,value.stdout+value.stderr);return JSON.parse(value.stdout);},configuration=run(packageRoot,{...request,runtime_action:'freeze-chain'}).configuration,input={...request,configuration,runtime_action:'readiness-plan'};
 const profile=fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json')),ready=run(packageRoot,input);assert.equal(ready.proof_kind,'completed-readiness');assert.equal(ready.guard,null);assert.deepEqual(ready.prerequisites,[]);fs.unlinkSync(path.join(project,registry.REGISTRY));assert.ok(run(packageRoot,input).prerequisites.length,'Completed readiness must preserve missing managed authority.');assert.deepEqual(fs.readFileSync(path.join(project,'.skill-tree/installation/profile.json')),profile);
 fs.cpSync(packageRoot,standalone,{recursive:true});fs.rmSync(project,{recursive:true});fs.rmSync(upstream,{recursive:true});const independent=run(standalone,{...input,project_root:runtime});assert.equal(independent.proof_kind,'completed-readiness');assert.deepEqual(independent.prerequisites,[]);assert.equal(independent.bindings.length,1);noFuture(runtime);
});
