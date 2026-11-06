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
