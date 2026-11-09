'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http'),{spawnSync}=require('node:child_process');
const core=require('../lib/installation.js'),registry=require('../lib/plugin-registry.js');
const lifecycle=require('../lib/plugin-lifecycle.js'),sources=require('../lib/plugin-sources.js'),remote=require('../lib/plugin-acquisition.js');
const sourceRoot=path.resolve(__dirname,'..');
function fixture(t,files={'SKILL.md':Buffer.from('# Source\n')}){
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-plugin-lifecycle-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const target=path.join(base,'target'),upstream=path.join(base,'upstream');fs.mkdirSync(target);fs.mkdirSync(upstream);
 for(const [rel,value]of Object.entries(files)){const dest=path.join(upstream,rel);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,value);}
 const root=fs.realpathSync(target);core.install(root,sourceRoot,'general',[{name:'skill-tree-add-pending-task',provider:'codex',rel:'.agents/skills/skill-tree-add-pending-task'}]);
 return {root,upstream,source:{id:'example',path:fs.realpathSync(upstream)}};
}
const binding=(id='first',plugin_id='example',extra={})=>({id,plugin_id,operation:'skill-tree-process-future-pending',anchor:'after',enabled:true,...extra});
const confirm=proposal=>({proposal_digest:proposal.digest});
async function prepared(f,request={},options={}){return lifecycle.prepareProposal(f.root,{request_id:'install-example',operation:'install',sources:[f.source],bindings:[binding()],...request},options);}
async function installed(f,request={}){const proposal=await prepared(f,request);const result=lifecycle.applyProposal(f.root,JSON.parse(JSON.stringify(proposal)),confirm(proposal));return {proposal,result,registry:registry.verifyInstalled(f.root)};}
const read=(root,rel)=>fs.readFileSync(path.join(root,rel));
function originalBytes(root,record,rel='SKILL.md'){return read(root,path.posix.join(record.destination,'upstream',rel));}

test('confirmed local installation preserves exact source closure, binary bytes and separate adaptation',async t=>{
 const bytes=Buffer.from('\ufeff---\nname: claude-source\n---\nRead [asset](assets/data.bin).\n'),asset=Buffer.from([0,255,128,13,10]);
 const f=fixture(t,{'SKILL.md':bytes,'assets/data.bin':asset,'private.txt':'unrelated'});f.source.adapter={mode:'source-backed',instructions:'Bounded translation.'};
 const {result,registry:r}=await installed(f),record=r.packages.example;
 assert.equal(result.action,'installed');assert.equal(r.generation,1);assert.deepEqual(originalBytes(f.root,record),bytes);assert.deepEqual(originalBytes(f.root,record,'assets/data.bin'),asset);assert.equal(record.files['upstream/private.txt'],undefined);assert.equal(record.adaptation.instructions,'Bounded translation.');assert.deepEqual(r.bindings,[binding()]);
});
test('a complete source with missing native tools installs inertly and retains provenance',async t=>{
 const f=fixture(t);f.source.capabilities=['native-skill-tool'];f.source.metadata={authoring_host:'claude',custom:'preserved'};
 const {registry:r}=await installed(f),record=r.packages.example;assert.equal(record.execution.state,'unavailable');assert.deepEqual(record.execution.missing,['native-skill-tool']);assert.equal(record.metadata.authoring_host,'claude');assert.equal(record.metadata.custom,'preserved');
});
test('proposal serialization excludes local locators and changed or absent consent rejects all writes',async t=>{
 const f=fixture(t),p=await prepared(f),before=core.treeHash(f.root,'.skill-tree');
 assert.equal(JSON.stringify(p).includes(f.upstream),false);assert.match(p.digest,/^[a-f0-9]{64}$/);
 assert.throws(()=>lifecycle.applyProposal(f.root,p,{}),/consent|confirm/i);assert.throws(()=>lifecycle.applyProposal(f.root,p,{proposal_digest:'0'.repeat(64)}),/consent|confirm/i);
 const changed=JSON.parse(JSON.stringify(p));changed.bindings[0].enabled=false;assert.throws(()=>lifecycle.applyProposal(f.root,changed,confirm(p)),/digest|changed|proposal/i);assert.equal(core.treeHash(f.root,'.skill-tree'),before);
});
test('exact duplicate requests recover original outcomes without new generations or occurrences',async t=>{
 const f=fixture(t),{proposal:p,registry:r}=await installed(f),before=read(f.root,registry.REGISTRY);
 const repeat=lifecycle.applyProposal(f.root,p,confirm(p));assert.equal(repeat.replayed,true);assert.equal(registry.readRegistry(f.root).generation,r.generation);assert.deepEqual(read(f.root,registry.REGISTRY),before);assert.equal(registry.readRegistry(f.root).bindings.length,1);
});
test('stale proposal and conflicting request identity cannot overwrite a later configuration',async t=>{
 const f=fixture(t);await installed(f);const stale=await prepared(f,{request_id:'stale-config',operation:'configure',sources:[],bindings:[binding('second')]});
 const current=await prepared(f,{request_id:'current-config',operation:'configure',sources:[],bindings:[binding('current')]});lifecycle.applyProposal(f.root,current,confirm(current));
 assert.throws(()=>lifecycle.applyProposal(f.root,stale,confirm(stale)),/stale|generation|changed/i);
 const conflict=await prepared(f,{request_id:'install-example',operation:'configure',sources:[],bindings:[]});assert.throws(()=>lifecycle.applyProposal(f.root,conflict,confirm(conflict)),/request|replay|conflict/i);assert.equal(registry.readRegistry(f.root).bindings[0].id,'current');
});
test('matching repeat installation is an owned no-op and keeps frozen binding configuration',async t=>{
 const f=fixture(t);await installed(f);const before=read(f.root,registry.REGISTRY),p=await prepared(f,{request_id:'repeat-same'}),result=lifecycle.applyProposal(f.root,p,confirm(p));
 assert.equal(result.action,'verified-no-op');assert.deepEqual(read(f.root,registry.REGISTRY),before);
});
test('modified and unowned package resources reject replacement without force adoption',async t=>{
 const f=fixture(t);await installed(f);const r=registry.readRegistry(f.root),file=path.join(f.root,r.packages.example.destination,'upstream/SKILL.md');fs.writeFileSync(file,'developer edit');
 await assert.rejects(prepared(f,{request_id:'changed',operation:'update'}),/owned|modified|conflict/i);assert.equal(fs.readFileSync(file,'utf8'),'developer edit');
 const other=fixture(t);const unowned=path.join(other.root,registry.PACKAGES,'example');fs.mkdirSync(unowned,{recursive:true});fs.writeFileSync(path.join(unowned,'private.txt'),'keep');await assert.rejects(prepared(other),/owned|conflict/i);assert.equal(fs.readFileSync(path.join(unowned,'private.txt'),'utf8'),'keep');
});
test('missing required resources and tampered staged snapshot bytes reject before activation',async t=>{
 const f=fixture(t);f.source.resources=['missing.md'];await assert.rejects(prepared(f),/source|resource|missing/i);assert.equal(fs.existsSync(path.join(f.root,registry.REGISTRY)),false);
 const g=fixture(t),p=await prepared(g),serialized=JSON.stringify(p),encoded=Buffer.from('# Source\n').toString('base64');assert.ok(serialized.includes(encoded));const changed=JSON.parse(serialized.replace(encoded,Buffer.from('# Changed\n').toString('base64')));assert.throws(()=>lifecycle.applyProposal(g.root,changed,confirm(p)),/digest|snapshot|changed|proposal/i);assert.equal(fs.existsSync(path.join(g.root,registry.REGISTRY)),false);
});
test('configure enable and disable preserve independent repeated binding occurrences',async t=>{
 const f=fixture(t);await installed(f,{bindings:[binding('editor-a'),binding('editor-c','example',{parameters:{pass:'final'}})]});
 const disable=await prepared(f,{request_id:'disable-one',operation:'disable',sources:[],binding_ids:['editor-a']});lifecycle.applyProposal(f.root,disable,confirm(disable));let r=registry.readRegistry(f.root);assert.deepEqual(r.bindings.map(b=>b.enabled),[false,true]);assert.equal(r.bindings[1].parameters.pass,'final');
 const enable=await prepared(f,{request_id:'enable-one',operation:'enable',sources:[],binding_ids:['editor-a']});lifecycle.applyProposal(f.root,enable,confirm(enable));r=registry.readRegistry(f.root);assert.deepEqual(r.bindings.map(b=>b.id),['editor-a','editor-c']);assert.deepEqual(r.bindings.map(b=>b.enabled),[true,true]);
});
test('package dependencies and uninstall remove every selected live binding while preserving original source',async t=>{
 const f=fixture(t);const p=await prepared(f,{sources:[{...f.source,id:'shared'},{...f.source,id:'consumer',package_dependencies:['shared']}],bindings:[binding('a','shared'),binding('b','shared'),binding('c','consumer')]});lifecycle.applyProposal(f.root,p,confirm(p));
 await assert.rejects(prepared(f,{request_id:'remove-dependent',operation:'uninstall',sources:[],plugin_ids:['shared']}),/depend/i);
 const remove=await prepared(f,{request_id:'remove-consumer',operation:'uninstall',sources:[],plugin_ids:['consumer']});lifecycle.applyProposal(f.root,remove,confirm(remove));const r=registry.verifyInstalled(f.root);assert.ok(r.packages.shared);assert.equal(r.packages.consumer,undefined);assert.deepEqual(r.bindings.map(b=>b.id),['a','b']);assert.equal(fs.existsSync(path.join(f.upstream,'SKILL.md')),true);
 const shared=await prepared(f,{request_id:'remove-shared',operation:'uninstall',sources:[],plugin_ids:['shared']});lifecycle.applyProposal(f.root,shared,confirm(shared));assert.deepEqual(registry.readRegistry(f.root).bindings,[]);
});
test('plugin rollback restores binary resources as a new generation and preserves core rollback evidence',async t=>{
 const first=Buffer.from([0,255,128,13,10]),f=fixture(t,{'SKILL.md':'# Version one','asset.bin':first});f.source.resources=['asset.bin'];const coreJournal=read(f.root,'.skill-tree/installation/.last-transaction.json');await installed(f);
 fs.writeFileSync(path.join(f.upstream,'SKILL.md'),'# Version two');fs.writeFileSync(path.join(f.upstream,'asset.bin'),Buffer.from([4,5,6]));const update=await prepared(f,{request_id:'update-v2',operation:'update'});lifecycle.applyProposal(f.root,update,confirm(update));const generation=registry.readRegistry(f.root).generation;
 const rollback=await lifecycle.prepareRollback(f.root,{request_id:'rollback-v1'});lifecycle.applyProposal(f.root,rollback,confirm(rollback));const r=registry.verifyInstalled(f.root);assert.ok(r.generation>generation);assert.deepEqual(originalBytes(f.root,r.packages.example,'asset.bin'),first);assert.match(originalBytes(f.root,r.packages.example).toString(),/Version one/);assert.ok(r.requests['update-v2']);assert.ok(r.requests['rollback-v1']);assert.deepEqual(read(f.root,'.skill-tree/installation/.last-transaction.json'),coreJournal);
});
test('interrupted registry activation recovers resources registry and bindings without duplicate delivery',async t=>{
 const f=fixture(t),p=await prepared(f),rename=fs.renameSync;let failed=false;
 fs.renameSync=(from,to)=>{if(!failed&&String(to)===path.join(f.root,registry.REGISTRY)){failed=true;throw Error('fixture interruption');}return rename(from,to);};
 try{assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/fixture interruption/);}finally{fs.renameSync=rename;}
 assert.equal(fs.existsSync(path.join(f.root,'.skill-tree/installation/.plugin-journal.json')),true);lifecycle.recoverPlugins(f.root);const r=registry.verifyInstalled(f.root);assert.ok(r.packages.example);assert.equal(r.bindings.length,1);assert.equal(lifecycle.applyProposal(f.root,p,confirm(p)).replayed,true);
});
test('writer locks and active retained runs reject activation and preserve all checkpoint state',async t=>{
 const f=fixture(t),p=await prepared(f);fs.writeFileSync(path.join(f.root,'.skill-tree/.writer-lock'),'owned fixture');assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/writer|lock/i);fs.unlinkSync(path.join(f.root,'.skill-tree/.writer-lock'));
 const state={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{},run_registry:{schema:1,runs:{first:{id:'first',phase:'validate',stop_reason:null},other:{id:'other',phase:'implement',stop_reason:null}}}};fs.mkdirSync(path.join(f.root,'.skill-tree/documents'));const file=path.join(f.root,'.skill-tree/documents/future.json');fs.writeFileSync(file,JSON.stringify(state));const before=read(f.root,'.skill-tree/documents/future.json');assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/active|handoff|stop/i);assert.deepEqual(read(f.root,'.skill-tree/documents/future.json'),before);assert.equal(fs.existsSync(path.join(f.root,registry.REGISTRY)),false);
});
test('installation treats a local merge order as unfinished until delivery receipts match',t=>{
 const {root}=fixture(t),folder=path.join(root,'.skill-tree/documents');
 fs.mkdirSync(folder);
 const file=path.join(folder,'future.json');
 const run={id:'local',phase:'completed',delivery:{
  implementation:'completed',status:'local-result',order_completed:true,
  authorization:{pr:false,merge:true,mode:'local-merge'},
 }};
 const state={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{},
  run_registry:{schema:1,runs:{local:run}}};
 const save=()=>fs.writeFileSync(file,JSON.stringify(state));
 save();
 assert.equal(core.hasActiveOperation(root),true);

 const commit='1'.repeat(40),profileIdentity='2'.repeat(64);
 run.delivery.status='merged';
 run.delivery.local_integration={
  merge:{commit,tree:'3'.repeat(40),parents:['4'.repeat(40),'5'.repeat(40)]},
  target_admission:{merge_commit:commit,profile_identity:profileIdentity},
  validation:{merge_commit:commit,profile_identity:'stale',checks:[{exit_code:0}],
   evidence:[{path:'.skill-tree/history/runs/local-validation.json',sha256:'6'.repeat(64)}]},
 };
 save();
 assert.equal(core.hasActiveOperation(root),true);
 run.delivery.local_integration.validation.profile_identity=profileIdentity;
 save();
 assert.equal(core.hasActiveOperation(root),false);
});
test('changed plugin generations require current profile refresh and preserve retained run progress',async t=>{
 const f=fixture(t),state={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{retained:{stage:'awaiting-validation',checks:{}}},run_registry:{schema:1,runs:{first:{id:'first',phase:'awaiting-validation',stop_reason:null,snapshot:['keep']},second:{id:'second',phase:'blocked',stop_reason:'retain owner wait',snapshot:['other']}}}};fs.mkdirSync(path.join(f.root,'.skill-tree/documents'));fs.writeFileSync(path.join(f.root,'.skill-tree/documents/future.json'),JSON.stringify(state));
 const helper=path.join(f.root,'.agents/skills/skill-tree-add-pending-task/scripts/workflow-state.py');
 const admit=()=>spawnSync('python3',['-c','import importlib.util,sys; from pathlib import Path; s=importlib.util.spec_from_file_location("fixture_admission",sys.argv[1]); w=importlib.util.module_from_spec(s); s.loader.exec_module(w); w.admit_profile(w.Store(Path(sys.argv[2]),allow_unselected=True,route_queue=False,neutral=True))',helper,f.root],{encoding:'utf8',timeout:15000});
 assert.equal(admit().status,0);await installed(f);
 const after=JSON.parse(read(f.root,'.skill-tree/documents/future.json'));assert.deepEqual(after.task_progress,state.task_progress);assert.deepEqual(after.run_registry.runs.first.snapshot,['keep']);assert.equal(after.run_registry.runs.second.stop_reason,'retain owner wait');assert.equal(after.run_registry.runs.first.profile_refresh_required,true);assert.throws(()=>core.verify(f.root,sourceRoot),/refresh|mismatch/i);
 assert.notEqual(admit().status,0);core.refresh(f.root,sourceRoot);assert.ok(core.verify(f.root,sourceRoot));const current=admit();assert.equal(current.status,0,current.stderr);assert.deepEqual(JSON.parse(read(f.root,'.skill-tree/documents/future.json')).task_progress,state.task_progress);
});
test('malformed multi-run registry cannot be treated as an empty safe handoff',async t=>{
 const f=fixture(t),p=await prepared(f);fs.mkdirSync(path.join(f.root,'.skill-tree/documents'));const file=path.join(f.root,'.skill-tree/documents/future.json');
 const base={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{},run_registry:{schema:1,runs:{}}};
 for(const state of [{...base,run_registry:{schema:1,runs:[]}},{...base,active_run:{id:'hidden',phase:'implement'}},{...base,schema:2}]){fs.writeFileSync(file,JSON.stringify(state));const before=fs.readFileSync(file);assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/registry|schema|authority/i);assert.deepEqual(fs.readFileSync(file),before);assert.equal(fs.existsSync(path.join(f.root,registry.REGISTRY)),false);}
});
test('dangling owned-registry symlinks are conflicts rather than absent files',async t=>{
 const f=fixture(t),file=path.join(f.root,registry.REGISTRY);fs.symlinkSync('missing-unowned-target',file);await assert.rejects(prepared(f),/symlink|owned/i);assert.equal(fs.lstatSync(file).isSymbolicLink(),true);assert.equal(fs.existsSync(path.join(f.root,registry.PACKAGES)),false);
});
test('prototype-shaped request identities retain own receipts and replay idempotently',async t=>{
 const f=fixture(t),{proposal:p}=await installed(f,{request_id:'__proto__'}),r=registry.readRegistry(f.root);assert.equal(Object.hasOwn(r.requests,'__proto__'),true);assert.equal(lifecycle.applyProposal(f.root,p,confirm(p)).replayed,true);assert.equal(registry.readRegistry(f.root).generation,1);assert.equal(Object.prototype.action,undefined);
});
test('invalid binding JSON rejects without coercion or executing accessors',async t=>{
 const f=fixture(t);await assert.rejects(prepared(f,{bindings:[binding('invalid','example',{parameters:{limit:Infinity}})]}),/JSON|finite/i);let reads=0;const parameters={};Object.defineProperty(parameters,'bad',{enumerable:true,get(){reads++;return 'secret';}});await assert.rejects(prepared(f,{bindings:[binding('getter','example',{parameters})]}),/accessor|JSON/i);assert.equal(reads,0);assert.equal(fs.existsSync(path.join(f.root,registry.REGISTRY)),false);
});
test('concurrent developer edits during plugin staging survive rejected update',async t=>{
 const f=fixture(t);await installed(f);const installedRecord=registry.readRegistry(f.root).packages.example,victim=path.join(f.root,installedRecord.destination,'upstream/SKILL.md'),before=read(f.root,registry.REGISTRY);fs.writeFileSync(path.join(f.upstream,'SKILL.md'),'# Updated');const p=await prepared(f,{request_id:'racing-update',operation:'update'}),write=fs.writeFileSync;let changed=false;
 fs.writeFileSync=(file,...args)=>{if(!changed&&String(file).includes('/.plugin-staging/')){changed=true;write(victim,'concurrent developer edit');}return write(file,...args);};
 try{assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/changed|conflict|modified/i);}finally{fs.writeFileSync=write;}
 assert.equal(fs.readFileSync(victim,'utf8'),'concurrent developer edit');assert.deepEqual(read(f.root,registry.REGISTRY),before);
});
test('registry verification rejects inconsistent snapshot claims even with a recomputed registry digest',async t=>{
 const f=fixture(t);await installed(f);const record=registry.readRegistry(f.root);record.packages.example.content_digest='0'.repeat(64);fs.writeFileSync(path.join(f.root,registry.REGISTRY),registry.json(registry.seal(record)));assert.throws(()=>registry.verifyInstalled(f.root),/snapshot|identity|digest|owned/i);
});
test('rehashing an unrelated extra owned resource cannot extend the inspected source closure',async t=>{
 const f=fixture(t);await installed(f);const record=registry.readRegistry(f.root),destination=record.packages.example.destination;fs.writeFileSync(path.join(f.root,destination,'unrelated.txt'),'unreviewed');record.packages.example.files['unrelated.txt']=registry.hash('unreviewed');fs.writeFileSync(path.join(f.root,registry.REGISTRY),registry.json(registry.seal(record)));assert.throws(()=>registry.verifyInstalled(f.root),/inventory|snapshot|owned/i);
});
test('active focused maintenance blocks mutation even when the retained outer run is stopped',async t=>{
 const f=fixture(t),p=await prepared(f);fs.mkdirSync(path.join(f.root,'.skill-tree/documents'));const file=path.join(f.root,'.skill-tree/documents/future.json'),state={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{},run_registry:{schema:1,runs:{outer:{id:'outer',phase:'blocked',stop_reason:'Preserved owner stop',maintenance:{id:'maintenance',phase:'implement',stop_reason:null}}}}};fs.writeFileSync(file,JSON.stringify(state));const before=fs.readFileSync(file);assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/active|handoff|stop/i);assert.deepEqual(fs.readFileSync(file),before);assert.equal(fs.existsSync(path.join(f.root,registry.REGISTRY)),false);
});
test('linked target honors canonical locks and explicit stopped handoff without changing queue copies',async t=>{
 const f=fixture(t),owner=path.join(path.dirname(f.root),'canonical');fs.mkdirSync(path.join(owner,'.skill-tree/documents'),{recursive:true});const init=spawnSync('git',['-C',f.root,'init'],{encoding:'utf8'});assert.equal(init.status,0,init.stderr);fs.writeFileSync(path.join(f.root,'.git/skill-tree-runtime.json'),JSON.stringify({schema:1,canonical_root:owner}));
 const state={format:'skill-tree-future',schema:3,tasks:[],active_run:null,task_progress:{},run_registry:{schema:1,runs:{kept:{id:'kept',phase:'awaiting-validation',stop_reason:null}}}},stateFile=path.join(owner,'.skill-tree/documents/future.json');fs.writeFileSync(stateFile,JSON.stringify(state));fs.mkdirSync(path.join(f.root,'.skill-tree/documents'));const copy=path.join(f.root,'.skill-tree/documents/future.json');fs.writeFileSync(copy,'unrelated execution queue copy');
 const p=await prepared(f);fs.writeFileSync(path.join(owner,'.skill-tree/.writer-lock'),'canonical owner');assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/writer|lock/i);fs.unlinkSync(path.join(owner,'.skill-tree/.writer-lock'));assert.throws(()=>lifecycle.applyProposal(f.root,p,confirm(p)),/canonical|stopped|handoff/i);
 state.run_registry.runs.kept.stop_reason='Explicit plugin cleanup handoff';fs.writeFileSync(stateFile,JSON.stringify(state));const before=fs.readFileSync(stateFile);assert.equal(lifecycle.applyProposal(f.root,p,confirm(p)).action,'installed');assert.deepEqual(fs.readFileSync(stateFile),before);assert.equal(fs.readFileSync(copy,'utf8'),'unrelated execution queue copy');assert.throws(()=>core.verify(f.root,sourceRoot),/refresh|mismatch/i);
});
test('offline dry-run and inventory do not acquire remote sources or mutate installation state',async t=>{
 const f=fixture(t),before=core.treeHash(f.root,'.skill-tree');let calls=0;const p=await prepared(f,{sources:[{id:'remote',kind:'raw',url:'https://example.invalid/SKILL.md'}],bindings:[]},{dryRun:true,acquire:async()=>{calls++;throw Error('Unexpected network');}});registry.readRegistry(f.root);registry.verifyInstalled(f.root);assert.equal(calls,0);assert.equal(p.action,'dry-run');assert.ok(p.prerequisites.length);assert.equal(core.treeHash(f.root,'.skill-tree'),before);
});
test('real raw HTTP acquisition resolves linked bytes without executing source scripts',async t=>{
 const files={
  '/skill/SKILL.md':Buffer.from('# Raw\nRead [notes][notes] and [guide](references/v2(guide).md).\n\n[notes]: references/notes.md\n\n```markdown\n[example](missing.md)\n```\n'),
  '/skill/references/notes.md':Buffer.from('# Notes'),'/skill/references/v2(guide).md':Buffer.from('# Guide'),
 },requests=[];
 const server=http.createServer((req,res)=>{requests.push(req.url);if(!files[req.url]){res.statusCode=404;res.end('missing');return;}res.end(files[req.url]);});await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
 const url='http://127.0.0.1:'+server.address().port+'/skill/SKILL.md',normalized=sources.normalizeSource({id:'http-source',kind:'raw',url});const snapshot=await sources.resolveSource(normalized,{acquire:remote.acquireRemote});assert.deepEqual(snapshot.files['SKILL.md'],files['/skill/SKILL.md']);assert.deepEqual(snapshot.files['references/notes.md'],files['/skill/references/notes.md']);assert.deepEqual(snapshot.files['references/v2(guide).md'],files['/skill/references/v2(guide).md']);assert.deepEqual(requests.sort(),Object.keys(files).sort());assert.equal(snapshot.execution.state,'unqualified');
});
test('cached normal and maintenance admission rejects changed plugin state and pending recovery',async t=>{
 const f=fixture(t),helper=path.join(sourceRoot,'common/scripts/workflow-state.py'),initial=core.receipt(f.root,true).identity;
 const script="import importlib.util,sys; from pathlib import Path; p=Path(sys.argv[1]); spec=importlib.util.spec_from_file_location('cached_plugin_admission',p); w=importlib.util.module_from_spec(spec); spec.loader.exec_module(w); admission={'identity':sys.argv[3]}; run={'admission':admission}; run=({'admission':{'identity':'outer-unused'},'maintenance':run} if sys.argv[4]=='true' else run); w.assert_admission(w.Store(Path(sys.argv[2]),allow_unselected=True,route_queue=False,neutral=True),{'active_run':run,'task_progress':{}})";
 const cached=(identity,maintenance=false)=>spawnSync('python3',['-c',script,helper,f.root,identity,String(maintenance)],{encoding:'utf8',timeout:30000});
 for(const maintenance of [false,true])assert.equal(cached(initial,maintenance).status,0);
 await installed(f);
 for(const maintenance of [false,true]){const result=cached(initial,maintenance);assert.notEqual(result.status,0);assert.match(result.stderr,/Plugin generation changed/);}
 core.refresh(f.root,sourceRoot);const current=core.receipt(f.root,true).identity;
 for(const maintenance of [false,true])assert.equal(cached(current,maintenance).status,0);
 fs.writeFileSync(path.join(f.root,'.skill-tree/installation/.plugin-journal.json'),'{}');
 for(const maintenance of [false,true]){const result=cached(current,maintenance);assert.notEqual(result.status,0);assert.match(result.stderr,/recovery is required/);}
 assert.throws(()=>core.verify(f.root,sourceRoot),/recovery is required/);
});
test('staging path aliases reject before overwriting resources or core rollback evidence',t=>{
 const f=fixture(t),before=read(f.root,'.skill-tree/installation/.last-transaction.json'),destination=registry.PACKAGES+'/collision';
 assert.throws(()=>core.transaction(f.root,{[destination]:{'same.txt':Buffer.from('first'),'./same.txt':Buffer.from('second')}},{},null,'plugins'),/collision/i);
 assert.equal(fs.existsSync(path.join(f.root,destination)),false);assert.equal(fs.existsSync(path.join(f.root,'.skill-tree/installation/.plugin-journal.json')),false);assert.deepEqual(read(f.root,'.skill-tree/installation/.last-transaction.json'),before);
});
test('no-op request nonce cannot authorize a later mutation and replays its original outcome after progress',async t=>{
 const f=fixture(t);await installed(f);const noop=await prepared(f,{request_id:'__proto__'}),before=read(f.root,registry.REGISTRY),result=lifecycle.applyProposal(f.root,noop,confirm(noop));assert.equal(result.action,'verified-no-op');assert.deepEqual(read(f.root,registry.REGISTRY),before);assert.equal(Object.hasOwn(registry.readNoopRequests(f.root).requests,'__proto__'),true);
 const conflict=await prepared(f,{request_id:'__proto__',operation:'disable',sources:[],binding_ids:['first']});assert.throws(()=>lifecycle.applyProposal(f.root,conflict,confirm(conflict)),/request|replay|conflict/i);
 const disable=await prepared(f,{request_id:'later-disable',operation:'disable',sources:[],binding_ids:['first']});lifecycle.applyProposal(f.root,disable,confirm(disable));const replay=lifecycle.applyProposal(f.root,noop,confirm(noop));assert.equal(replay.replayed,true);assert.equal(replay.action,'verified-no-op');assert.equal(replay.generation,1);assert.equal(replay.current_generation,2);assert.equal(registry.readRegistry(f.root).bindings[0].enabled,false);
});
test('no-op receipt preserves both meaningful rollback channels and survives a new rollback generation',async t=>{
 const f=fixture(t);await installed(f);fs.writeFileSync(path.join(f.upstream,'SKILL.md'),'# Version two');const update=await prepared(f,{request_id:'second-version',operation:'update'});lifecycle.applyProposal(f.root,update,confirm(update));
 const coreBefore=read(f.root,'.skill-tree/installation/.last-transaction.json'),pluginBefore=read(f.root,'.skill-tree/installation/.last-plugin-transaction.json'),backupBefore=core.treeHash(f.root,'.skill-tree/installation/.plugin-backups'),before=read(f.root,registry.REGISTRY),noop=await prepared(f,{request_id:'noop-before-rollback',operation:'configure',sources:[],bindings:[binding()]});assert.equal(lifecycle.applyProposal(f.root,noop,confirm(noop)).action,'verified-no-op');
 assert.deepEqual(read(f.root,registry.REGISTRY),before);assert.deepEqual(read(f.root,'.skill-tree/installation/.last-transaction.json'),coreBefore);assert.deepEqual(read(f.root,'.skill-tree/installation/.last-plugin-transaction.json'),pluginBefore);assert.equal(core.treeHash(f.root,'.skill-tree/installation/.plugin-backups'),backupBefore);
 const rollback=await lifecycle.prepareRollback(f.root,{request_id:'rollback-after-noop'});lifecycle.applyProposal(f.root,rollback,confirm(rollback));assert.match(originalBytes(f.root,registry.verifyInstalled(f.root).packages.example).toString(),/# Source/);const replay=lifecycle.applyProposal(f.root,noop,confirm(noop));assert.equal(replay.replayed,true);assert.equal(replay.generation,2);assert.equal(replay.current_generation,3);assert.ok(registry.readNoopRequests(f.root).requests['noop-before-rollback']);
});
test('an unowned root resource named __proto__ remains visible to ownership verification',async t=>{
 const f=fixture(t);await installed(f);const record=registry.readRegistry(f.root).packages.example;fs.writeFileSync(path.join(f.root,record.destination,'__proto__'),'unowned');assert.throws(()=>registry.verifyInstalled(f.root),/modified|owned|inventory/i);assert.equal(fs.readFileSync(path.join(f.root,record.destination,'__proto__'),'utf8'),'unowned');
});
test('a declared upstream resource named __proto__ survives portable snapshot encoding and hydration',async t=>{
 const bytes=Buffer.from([0,255,128]),f=fixture(t,Object.fromEntries([['SKILL.md','# Source\n'],['__proto__',bytes]]));f.source.resources=['__proto__'];const {registry:r}=await installed(f);assert.deepEqual(originalBytes(f.root,r.packages.example,'__proto__'),bytes);assert.equal(Object.hasOwn(r.packages.example.snapshot.digests,'__proto__'),true);assert.ok(registry.verifyInstalled(f.root));
});
test('an explicitly declared cache-named resource updates and rolls back without disappearing from transactions',async t=>{
 const first=Buffer.from([0,255,1]),second=Buffer.from([0,128,2]),f=fixture(t,{'SKILL.md':'# Constant source','__pycache__/needed.bin':first});f.source.resources=['__pycache__/needed.bin'];await installed(f);fs.writeFileSync(path.join(f.upstream,'__pycache__/needed.bin'),second);
 const update=await prepared(f,{request_id:'cache-only-update',operation:'update'});lifecycle.applyProposal(f.root,update,confirm(update));assert.deepEqual(originalBytes(f.root,registry.verifyInstalled(f.root).packages.example,'__pycache__/needed.bin'),second);
 const rollback=await lifecycle.prepareRollback(f.root,{request_id:'cache-only-rollback'});lifecycle.applyProposal(f.root,rollback,confirm(rollback));assert.deepEqual(originalBytes(f.root,registry.verifyInstalled(f.root).packages.example,'__pycache__/needed.bin'),first);
});
require('./fixtures/plugin-acquisition-cases.js');
