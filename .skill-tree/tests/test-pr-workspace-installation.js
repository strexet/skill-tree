const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const core=path.resolve(__dirname,'..'),cli=path.join(core,'bin/install.js');
function run(command,args,options={}){const r=spawnSync(command,args,{encoding:'utf8',timeout:30000,...options});assert.equal(r.status,0,r.stdout+r.stderr);return r.stdout;}
function write(root,rel,value){const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof value==='string'?value:JSON.stringify(value));}
for(const flavor of ['general','web','unity'])test(`installed ${flavor} PR/controller packages execute without source or sibling packages`,t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-pr-installed-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 run('git',['init','-b','feature/example',root]);
 write(root,'package.json',{scripts:{test:'node --test'}});
 if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 const names=['skill-tree-pr-review-cycle','skill-tree-work-through-next','skill-tree-implement-all'];
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor',flavor,'--skills',...names]);
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor',flavor,'--skills',...names,'--verify']);
 const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));assert.equal(profile.flavor,flavor);assert.equal(profile.worktree_environment.schema,1);
 // Copy one installed package outside the target and remove access to target siblings.
 for(const name of names){
  const isolated=path.join(root,'isolated',name);fs.cpSync(path.join(root,'.agents/skills',name),isolated,{recursive:true});
  const request=path.join(root,'request.json');fs.writeFileSync(request,JSON.stringify({current_branch:'Feature/Case',instruction:'with merge',target_branch:'release/example'}));
  const helper=path.join(isolated,'scripts/pr-review-state.py');const result=JSON.parse(run('python3',[helper,'parameters',root,'--input',request],{cwd:os.tmpdir()}));
  assert.equal(result.source_branch,'Feature/Case');assert.equal(result.target_branch,'release/example');assert.equal(result.merge,true);
  assert.ok(fs.existsSync(path.join(isolated,'scripts/run-workspaces.py')));assert.match(fs.readFileSync(path.join(isolated,'references/project-profile.md'),'utf8'),new RegExp('Flavor: '+flavor));
 }
 const manager=path.join(root,'.skill-tree/installation/manager.js');
 run(process.execPath,[manager,'--refresh-profile'],{cwd:os.tmpdir()});run(process.execPath,[manager,'--verify'],{cwd:os.tmpdir()});
});
test('worktree environment declarations refresh the concrete profile without reading secrets',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-pr-env-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));write(root,'package.json',{scripts:{test:'node --test'}});
 write(root,'.env.local','SECRET_VALUE=fixture-do-not-publish');write(root,'.skill-tree/worktree-profile.json',{schema:1,required_files:['.env.local'],isolated_directories:['generated'],exclusive_resources:['service:local-fixture']});
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','web']);
 const profile=fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json'),'utf8');assert.ok(!profile.includes('fixture-do-not-publish'));assert.ok(profile.includes('service:local-fixture'));
});
for(const flavor of ['general','web','unity'])test(`installed ${flavor} Implement All freezes only the requested group through its standalone CLI`,t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-group-installed-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'queue'),remote=path.join(base,'remote.git');fs.mkdirSync(root);
 const git=(...args)=>run('git',['-C',root,...args]);git('init','-b','main');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
 write(root,'package.json',{scripts:{test:'node --test'}});write(root,'source.py','value = 1\n');
 if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 write(root,'.skill-tree/documents/future.md','# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 git('add','.');git('commit','-m','Synthetic group fixture');git('branch','develop');run('git',['init','--bare',remote]);git('remote','add','origin',remote);git('push','origin','main','develop');
 const name='skill-tree-implement-all';run(process.execPath,[cli,'--target',root,'--only','codex','--flavor',flavor,'--skills',name]);
 const isolated=path.join(base,'standalone');fs.cpSync(path.join(root,'.agents/skills',name),isolated,{recursive:true});const helper=path.join(isolated,'scripts/workflow-state.py');let step=0;
 function command(action,target=root,payload=null,extra=[]){const args=[helper,action,target,...extra];if(payload){const input=path.join(base,`input-${step++}.json`);fs.writeFileSync(input,JSON.stringify(payload));args.push('--input',input);}return JSON.parse(run('python3',args,{cwd:os.tmpdir()}));}
 function task(title,priority,depends_on=[]){
  const pending=command('intake',root,{title,priority,description:'Verify selected group admission.',expected_behavior:'Preserve the requested group.'});
  const goal='Preserve the requested group.',check={id:'scope',recipe_id:'static-inspection',criteria:[goal],sources:['source.py'],parameters:{},assertion:goal,timing:'immediate'};
  const body='Goal:\n- '+goal+'\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+JSON.stringify({checks:[check]})+'\n```\n\nAcceptance:\n- '+goal+'\n';
  return command('process',root,{selectors:[pending.id],dispositions:{[pending.id]:{status:'promoted',reason:'The fixture supplies the source and selection boundary.'}},tasks:[{title,body,depends_on,parent_pending_ids:[pending.id]}]}).created_ids[0];
 }
 const outside=task('Unrelated highest root',500),other=task('Another unrelated root',400),dep=task('Required prerequisite',300),low=task('Selected lower root',100,[dep]),high=task('Selected higher root',200,[dep]);
 command('workspace-setup',root,{});const working=path.join(base,'working');const started=command('start',root,{snapshot_ids:[low,high],worktree:working},['--mode','all']);
 assert.deepEqual(started.snapshot,[high,low]);assert.deepEqual(new Set(started.admitted_task_ids),new Set([low,high,dep]));
 const raw=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));assert.deepEqual(new Set(Object.keys(raw.run_registry.claims)),new Set([low,high,dep]));assert.ok(!raw.run_registry.claims[outside]);assert.ok(!raw.run_registry.claims[other]);
 const resumed=command('index',working).active_run;assert.equal(resumed.id,started.id);assert.deepEqual(resumed.snapshot,[high,low]);assert.equal(resumed.workspace.base_branch,'develop');assert.equal(Object.keys(raw.run_registry.runs).length,1);
});
test('installed controller starts and resumes the same worktree with a canonical queue and profile admission',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-run-installed-'));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));const root=path.join(base,'queue'),remote=path.join(base,'remote.git');fs.mkdirSync(root);
 const git=(...args)=>run('git',['-C',root,...args]);git('init','-b','main');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
 write(root,'package.json',{scripts:{test:'node --test'}});write(root,'source.py','value = 1\n');write(root,'.skill-tree/documents/future.md','# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');git('add','.');git('commit','-m','Synthetic initial fixture');git('branch','develop');run('git',['init','--bare',remote]);git('remote','add','origin',remote);git('push','origin','main','develop');
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','general','--skills','skill-tree-work-through-next']);
 const helper=path.join(root,'.agents/skills/skill-tree-work-through-next/scripts/workflow-state.py');let step=0;
 function command(name,target=root,payload=null,extra=[]){let args=[helper,name,target,...extra];if(payload){const input=path.join(base,`input-${step++}.json`);fs.writeFileSync(input,JSON.stringify(payload));args.push('--input',input);}return JSON.parse(run('python3',args));}
 const pending=command('intake',root,{title:'Installed lifecycle fixture',description:'Verify the isolated workspace lifecycle.',expected_behavior:'Preserve the shared queue identity.'});
 const goal='Preserve the shared queue identity.',check={id:'behavior',recipe_id:'static-inspection',criteria:[goal],sources:['source.py'],parameters:{},assertion:goal,timing:'immediate'};
 const body='Goal:\n- '+goal+'\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+JSON.stringify({checks:[check]})+'\n```\n\nAcceptance:\n- '+goal+'\n';
 const receipt=command('process',root,{selectors:[pending.id],dispositions:{[pending.id]:{status:'promoted',reason:'The controlled fixture supplies the isolated repository.'}},tasks:[{title:'Installed lifecycle fixture',body,parent_pending_ids:[pending.id]}]});
 command('workspace-setup',root,{});const working=path.join(base,'working');const started=command('start',root,{worktree:working},['--id',receipt.created_ids[0]]);
 assert.equal(command('index',working).active_run.id,started.id);assert.equal(command('read',working,null,['--id',receipt.created_ids[0]]).id,receipt.created_ids[0]);
 command('checkpoint',working,{phase:'refresh-profile',next_action:'Install the exact worktree flavor.'});
 run(process.execPath,[cli,'--target',working,'--only','codex','--flavor','general','--skills','skill-tree-work-through-next']);
 command('admit',working);command('checkpoint',working,{phase:'implement'});assert.equal(command('begin',working,{task_id:receipt.created_ids[0]}).phase,'implement');
 const raw=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));assert.equal(raw.active_run,null);assert.equal(raw.run_registry.claims[receipt.created_ids[0]],started.id);assert.equal(raw.run_registry.runs[started.id].workspace.branch,started.workspace.branch);
 write(working,'report.json',{queue:raw.run_registry.queue_id});const attempt=command('prepare-check',working,{task_id:receipt.created_ids[0],check_id:'behavior'});
 command('record-check',working,{task_id:receipt.created_ids[0],check_id:'behavior',attempt_id:attempt.attempt_id,result:'pass',classification:'executed-control',actual_lane:'static',environment_identity:attempt.environment_identity,assertions:[{assertion:goal,result:'pass'}],cleanup:'The fixture starts no product process.',evidence:['report.json']});
 command('implemented',working,{task_id:receipt.created_ids[0]});command('complete',working,{task_id:receipt.created_ids[0],outcome:goal,acceptance:[{criterion:goal,result:'pass',evidence:['report.json']}],source_fingerprints:attempt.sources});
 const finished=command('finish',working);assert.equal(finished.delivery.status,'local-result');
 const before=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));
 run(process.execPath,[path.join(working,'.skill-tree/installation/manager.js'),'--refresh-profile']);
 const after=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));assert.deepEqual(after,before);
});
