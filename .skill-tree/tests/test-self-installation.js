const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const cli=path.resolve(__dirname,'../bin/install.js'),installation=require('../lib/installation.js');
function fixture(t){const directory=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-rebind-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));return directory;}
function command(root,args){return spawnSync(process.execPath,[path.join(root,'.skill-tree/installation/manager.js'),...args],{encoding:'utf8',timeout:20000});}
function install(root){fs.mkdirSync(root,{recursive:true});const result=spawnSync(process.execPath,[cli,'--target',root,'--only','codex','--flavor','general','--copy'],{encoding:'utf8',timeout:20000});assert.equal(result.status,0,result.stderr);}
function git(root,...args){const result=spawnSync('git',['-C',root,...args],{encoding:'utf8',timeout:20000});assert.equal(result.status,0,result.stderr);return result.stdout.trim();}
test('explicit rebind verifies relocated ownership and remains idempotent',t=>{
 const directory=fixture(t),original=path.join(directory,'original'),moved=path.join(directory,'moved');install(original);fs.cpSync(original,moved,{recursive:true});
 const packages=installation.treeHash(moved,'.agents/skills');assert.notEqual(command(moved,['--verify']).status,0);
 const result=command(moved,['--rebind']);assert.equal(result.status,0,result.stderr);
 assert.equal(command(moved,['--verify']).status,0);assert.equal(installation.treeHash(moved,'.agents/skills'),packages);
 const receipt=path.join(moved,'.skill-tree/installation/profile.json');assert.equal(JSON.parse(fs.readFileSync(receipt)).project_root,fs.realpathSync(moved));
 const before=fs.readFileSync(receipt,'utf8');assert.equal(command(moved,['--rebind']).status,0);assert.equal(fs.readFileSync(receipt,'utf8'),before);
 assert.equal(command(original,['--verify']).status,0);
});
test('rebind preserves the retained package generation and rollback uses the new project root',t=>{
 const directory=fixture(t),original=path.join(directory,'original'),moved=path.join(directory,'moved');install(original);
 const ownedPackages=installation.treeHash(original,'.agents/skills');
 fs.writeFileSync(path.join(original,'package.json'),'{"scripts":{"test":"node --test"}}');
 assert.equal(command(original,['--refresh-profile']).status,0);
 fs.cpSync(original,moved,{recursive:true});
 const last=path.join(moved,'.skill-tree/installation/.last-transaction.json'),retained=fs.readFileSync(last);
 assert.equal(command(moved,['--rebind']).status,0);
 assert.deepEqual(fs.readFileSync(last),retained);
 fs.unlinkSync(path.join(moved,'package.json'));
 const rollback=command(moved,['--rollback']);assert.equal(rollback.status,0,rollback.stderr);
 assert.equal(command(moved,['--verify']).status,0);
 assert.equal(installation.treeHash(moved,'.agents/skills'),ownedPackages);
 assert.equal(installation.receipt(fs.realpathSync(moved),true).project_root,fs.realpathSync(moved));
 assert.equal(command(original,['--verify']).status,0);
});
test('rebind never adopts edited packages, unknown bundle files or pending transactions',t=>{
 const directory=fixture(t),original=path.join(directory,'original');install(original);
 for(const kind of ['package','bundle','journal','inputs']){
  const moved=path.join(directory,kind);fs.cpSync(original,moved,{recursive:true});
  if(kind==='package')fs.appendFileSync(path.join(moved,'.agents/skills/skill-tree-add-pending-task/SKILL.md'),'Local edits.\n');
  if(kind==='bundle')fs.writeFileSync(path.join(moved,'.skill-tree/installation/source/unknown.txt'),'Unowned');
  if(kind==='journal')fs.writeFileSync(path.join(moved,'.skill-tree/installation/.journal.json'),'{}');
  if(kind==='inputs')fs.writeFileSync(path.join(moved,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));
  const before=installation.treeHash(moved,'.skill-tree'),packages=installation.treeHash(moved,'.agents');
  assert.notEqual(command(moved,['--rebind']).status,0,kind);assert.equal(installation.treeHash(moved,'.skill-tree'),before);assert.equal(installation.treeHash(moved,'.agents'),packages);
 }
});
test('clean clones recover terminal registry locators while retaining every historical checkpoint',t=>{
 const directory=fixture(t),original=path.join(directory,'original'),clone=path.join(directory,'clone');install(original);
 const docs=path.join(original,'.skill-tree/documents');fs.mkdirSync(docs,{recursive:true});
 const future='# Future Work\n\n## Pending Task Format\n\nFixed headers precede task bodies.\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n';fs.writeFileSync(path.join(docs,'future.md'),future);
 const rid='WR-11111111-1111-4111-8111-111111111111',qid='Q-22222222-2222-4222-8222-222222222222';
 const run={id:rid,mode:'all',snapshot:[],root_task_id:null,current_task_id:null,phase:'completed',required_ids:[],deferred_ids:[],pending_ids:[],processing_results:[],completed_ids:[],limits:{},next_action:'Local result',stop_reason:null,admission:{},admitted_task_ids:[],admitted_groups:{},delivery:{implementation:'completed',status:'local-result'},workspace:{branch:'retired'}};
 const state={format:'skill-tree-future',schema:3,source_hash:require('../lib/composer.js').hash(future),tasks:[],task_progress:{},active_run:null,run_registry:{schema:1,queue_id:qid,runs:{[rid]:run},claims:{},resources:{}}};fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify(state));
 git(original,'init','--initial-branch=main');git(original,'add','.');git(original,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Fixture');git(directory,'clone','--quiet','--no-local',original,clone);
 assert.equal(command(clone,['--rebind']).status,0);
 const helper=path.join(clone,'.agents/skills/skill-tree-implement-all/scripts/workflow-state.py'),request=path.join(directory,'recover.json');fs.writeFileSync(request,JSON.stringify({queue_id:qid,worktrees:{}}));
 let result=spawnSync('python3',[helper,'recover-locator',clone,'--input',request],{encoding:'utf8',timeout:20000});assert.equal(result.status,0,result.stdout+result.stderr);
 result=spawnSync('python3',[helper,'index',clone],{encoding:'utf8',timeout:20000});assert.equal(result.status,0,result.stdout+result.stderr);assert.deepEqual(JSON.parse(result.stdout).run_registry,state.run_registry);
 assert.deepEqual(JSON.parse(fs.readFileSync(path.join(clone,'.skill-tree/documents/future.json'))),state);
 state.run_registry.runs[rid].delivery={implementation:'in-progress',status:'implementation-in-progress'};fs.writeFileSync(path.join(clone,'.skill-tree/documents/future.json'),JSON.stringify(state));
 result=spawnSync('python3',[helper,'recover-locator',clone,'--input',request],{encoding:'utf8',timeout:20000});assert.notEqual(result.status,0);assert.match(result.stdout,/unfinished|retained run locator/);
});
test('linked worktree rebind preserves canonical queue authority and workflow bytes',t=>{
 const directory=fixture(t),original=path.join(directory,'original'),linked=path.join(directory,'linked');install(original);
 const docs=path.join(original,'.skill-tree/documents');fs.mkdirSync(docs,{recursive:true});
 const state={format:'skill-tree-future',schema:2,tasks:[],task_progress:{},active_run:{phase:'implement',stop_reason:null}};fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify(state));
 git(original,'init','--initial-branch=main');git(original,'add','.');git(original,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Fixture');git(original,'worktree','add','-b','codex/fixture',linked);
 fs.writeFileSync(path.join(original,'.git/skill-tree-runtime.json'),JSON.stringify({schema:1,canonical_root:original,worktrees:{}}));
 const active=installation.treeHash(original,'.skill-tree');assert.notEqual(command(linked,['--rebind']).status,0);assert.equal(installation.treeHash(original,'.skill-tree'),active);
 state.active_run.phase='blocked';state.active_run.stop_reason='Stopped for an explicit profile handoff.';fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify(state));
 const before=installation.treeHash(original,'.skill-tree');assert.equal(command(linked,['--rebind']).status,0);assert.equal(command(linked,['--verify']).status,0);assert.equal(installation.treeHash(original,'.skill-tree'),before);
});
