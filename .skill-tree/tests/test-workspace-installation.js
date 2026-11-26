const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const core=path.resolve(__dirname,'..'),cli=path.join(core,'bin/install.js');
function run(command,args,options={}){const r=spawnSync(command,args,{encoding:'utf8',timeout:30000,...options});assert.equal(r.status,0,r.stdout+r.stderr);return r.stdout;}
function write(root,rel,value){const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof value==='string'?value:JSON.stringify(value));}
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
 const [program,...args]=started.profile_handoff.argv;
 const admitted=JSON.parse(run(program,args));
 assert.equal(admitted.status,'admitted');assert.equal(admitted.run_id,started.id);
 assert.equal(command('begin',working,{task_id:receipt.created_ids[0]}).phase,'implement');
 const raw=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));assert.equal(raw.active_run,null);assert.equal(raw.run_registry.claims[receipt.created_ids[0]],started.id);assert.equal(raw.run_registry.runs[started.id].workspace.branch,started.workspace.branch);
 const profile=path.join(working,'.skill-tree/installation/profile.json');
 const beforeRefresh=fs.readFileSync(profile);
 const checkpointPath=path.join(root,'.skill-tree/documents/future.json');
 command('checkpoint',working,{phase:'validate',stop_reason:'Installation profile changed; re-admit before continuation'},['--run-id',started.id]);
 const checkpoint=JSON.parse(fs.readFileSync(checkpointPath));
 checkpoint.run_registry.runs[started.id].profile_refresh_required=true;
 fs.writeFileSync(checkpointPath,JSON.stringify(checkpoint));
 const compatiblePackage={scripts:{test:'node --test'},description:'Compatible worktree metadata'};
 write(working,'package.json',compatiblePackage);
 const requestFile=path.join(base,'compatible-request.json');
 fs.writeFileSync(requestFile,JSON.stringify({compatible_refresh:true}));
 const interrupted = `
import runpy
import sys
entry = runpy.run_path(sys.argv[1])
workflow = entry['main'].__globals__
original = workflow['owned_profile_installer']
original_process = workflow['subprocess'].run
stage = sys.argv[2]

def publish_then_stop(argv, **kwargs):
    if stage == 'journal' and argv[:2] == ['node', '-e'] and argv[-2:] == ['activate', 'compatible']:
        patch = """
const interruptedFs = require('node:fs');
const writeOriginal = interruptedFs.writeFileSync;
interruptedFs.writeFileSync = function(destination, ...args) {
  const result = writeOriginal.call(this, destination, ...args);
  if (String(destination).endsWith('/.skill-tree/installation/.journal.json')) {
    throw Error('Injected interruption after sealed journal publication');
  }
  return result;
};
"""
        argv = [*argv[:2], patch + argv[2], *argv[3:]]
    return original_process(argv, **kwargs)

def interrupt(store, request, mode, **kwargs):
    result = original(store, request, mode, **kwargs)
    if stage == 'ack' and mode == 'activate' and kwargs.get('compatible'):
        raise workflow['WorkflowError']('Injected loss after owned profile activation')
    return result

workflow['subprocess'].run = publish_then_stop
workflow['owned_profile_installer'] = interrupt
raise SystemExit(entry['main'](sys.argv[3:]))
`;
 const selected=['admit',working,'--run-id',started.id,'--input',requestFile];
 const torn=spawnSync('python3',['-B','-c',interrupted,helper,'journal',...selected],{encoding:'utf8',timeout:45000});
 assert.equal(torn.status,2,torn.stdout+torn.stderr);
 assert.match(torn.stdout+torn.stderr,/Injected interruption after sealed journal publication/);
 assert.deepEqual(fs.readFileSync(profile),beforeRefresh);
 const originalRun=JSON.parse(fs.readFileSync(checkpointPath)).run_registry.runs[started.id];
 const prepared=originalRun.compatible_profile_refresh;
 assert.equal(originalRun.admission.identity,checkpoint.run_registry.runs[started.id].admission.identity);
 const receiptPath=path.join(working,'.skill-tree/artifacts/setup-operations',prepared.operation_id+'.json');
 const beforeRecovery=fs.readFileSync(receiptPath);
 const preparedCheckpoint=fs.readFileSync(checkpointPath);
 const journalPath=path.join(working,'.skill-tree/installation/.journal.json');
 const originalJournal=fs.readFileSync(journalPath);
 assert.match(JSON.parse(beforeRecovery).activation_journal_sha256,/^[a-f0-9]{64}$/);
 assert.equal(JSON.parse(beforeRecovery).status,'failed');
 const otherJournal=Buffer.concat([originalJournal,Buffer.from('\n')]);
 fs.writeFileSync(journalPath,otherJournal);
 const changedJournal=spawnSync('python3',['-B',helper,...selected],{encoding:'utf8',timeout:45000});
 assert.equal(changedJournal.status,2,changedJournal.stdout+changedJournal.stderr);
 assert.match(changedJournal.stdout+changedJournal.stderr,/journal changed since the original attempt/);
 assert.deepEqual(fs.readFileSync(journalPath),otherJournal);
 assert.deepEqual(fs.readFileSync(receiptPath),beforeRecovery);
 fs.writeFileSync(journalPath,originalJournal);
 write(working,'package.json',{...compatiblePackage,description:'Changed after activation'});
 const stale=spawnSync('python3',['-B',helper,...selected],{encoding:'utf8',timeout:45000});
 assert.equal(stale.status,2,stale.stdout+stale.stderr);
 assert.match(stale.stdout+stale.stderr,/compatible profile plan or package input changed/i);
 assert.deepEqual(fs.readFileSync(checkpointPath),preparedCheckpoint);
 assert.deepEqual(fs.readFileSync(receiptPath),beforeRecovery);
 assert.deepEqual(fs.readFileSync(journalPath),originalJournal);
 write(working,'package.json',compatiblePackage);
 write(working,'config/browser-policy.json',{});
 const changedDiscovery=spawnSync('python3',['-B',helper,...selected],{encoding:'utf8',timeout:45000});
 assert.equal(changedDiscovery.status,2,changedDiscovery.stdout+changedDiscovery.stderr);
 assert.match(changedDiscovery.stdout+changedDiscovery.stderr,/worktree discovery inputs or owned source changed/);
 assert.deepEqual(fs.readFileSync(checkpointPath),preparedCheckpoint);
 assert.deepEqual(fs.readFileSync(receiptPath),beforeRecovery);
 assert.deepEqual(fs.readFileSync(journalPath),originalJournal);
 fs.unlinkSync(path.join(working,'config/browser-policy.json'));
 const lost=spawnSync('python3',['-B','-c',interrupted,helper,'ack',...selected],{encoding:'utf8',timeout:45000});
 assert.equal(lost.status,2,lost.stdout+lost.stderr);
 assert.match(lost.stdout+lost.stderr,/Injected loss after owned profile activation/);
 assert.notDeepEqual(fs.readFileSync(profile),beforeRefresh);
 assert.ok(!fs.existsSync(journalPath));
 assert.deepEqual(fs.readFileSync(checkpointPath),preparedCheckpoint);
 const installationReceipt=fs.readFileSync(receiptPath);
 assert.equal(JSON.parse(installationReceipt).status,'completed');
 const readmitted=command('admit',working,{compatible_refresh:true},['--run-id',started.id]);
 assert.equal(readmitted.operation_id,prepared.operation_id);
 assert.deepEqual(fs.readFileSync(receiptPath),installationReceipt);
 const resumed=command('index',working).active_run;
 assert.equal(resumed.current_task_id,receipt.created_ids[0]);
 assert.equal(resumed.stop_reason,null);
 assert.equal(resumed.profile_refresh_required,undefined);
 assert.equal(resumed.compatible_profile_readmissions.length,1);
 assert.deepEqual(command('admit',working,{compatible_refresh:true},['--run-id',started.id]),
                  {...readmitted,replayed:true});
 write(working,'report.json',{queue:raw.run_registry.queue_id});const attempt=command('prepare-check',working,{task_id:receipt.created_ids[0],check_id:'behavior'});
 command('record-check',working,{task_id:receipt.created_ids[0],check_id:'behavior',attempt_id:attempt.attempt_id,result:'pass',classification:'executed-control',actual_lane:'static',environment_identity:attempt.environment_identity,assertions:[{assertion:goal,result:'pass'}],cleanup:'The fixture starts no product process.',evidence:['report.json']});
 command('implemented',working,{task_id:receipt.created_ids[0]});command('complete',working,{task_id:receipt.created_ids[0],outcome:goal,acceptance:[{criterion:goal,result:'pass',evidence:['report.json']}],source_fingerprints:attempt.sources});
 const finished=command('finish',working);assert.equal(finished.delivery.status,'local-result');
 const before=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));
 run(process.execPath,[path.join(working,'.skill-tree/installation/manager.js'),'--refresh-profile']);
 const after=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/documents/future.json')));assert.deepEqual(after,before);
});

test('installed implementation operations select scoped commits and local controller defaults', t => {
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-local-git-policy-'));
 t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'queue');
 fs.mkdirSync(root);
 const git=(...args)=>run('git',['-C',root,...args]).trim();
 git('init','-b','launch');
 git('config','user.name','Fixture');
 git('config','user.email','fixture@example.invalid');
 write(root,'package.json',{scripts:{test:'node --test'}});
 write(root,'source.py','value = 1\n');
 write(root,'.skill-tree/documents/future.md','# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 git('add','.');
 git('commit','-m','Local Git policy fixture');
 const launch=git('rev-parse','HEAD');
 git('config','commit.gpgSign','false');
 const names=['skill-tree-implement-next-future-task','skill-tree-work-through-next','skill-tree-implement-all'];
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','general','--skills',...names]);
 let step=0;
 function command(index,action,payload=null,extra=[]) {
  const helper=path.join(root,'.agents/skills',names[index],'scripts/workflow-state.py');
  const argv=[helper,action,root,...extra];
  if(payload){
   const input=path.join(base,`request-${step++}.json`);
   fs.writeFileSync(input,JSON.stringify(payload));
   argv.push('--input',input);
  }
  return JSON.parse(run('python3',argv));
 }
 function task(title) {
  const item=command(0,'intake',{title,description:'Verify the installed operation.',expected_behavior:'Preserve the selected scope.'});
  const goal='Preserve the selected scope.';
  const check={id:'scope',recipe_id:'static-inspection',criteria:[goal],sources:['source.py'],parameters:{},assertion:goal,timing:'immediate'};
  const body='Goal:\n- '+goal+'\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+JSON.stringify({checks:[check]})+'\n```\n\nAcceptance:\n- '+goal+'\n';
  return command(0,'process',{selectors:[item.id],dispositions:{[item.id]:{status:'promoted',reason:'The disposable Git fixture establishes readiness.'}},
   tasks:[{title,body,parent_pending_ids:[item.id]}]}).created_ids[0];
 }
 const leaf=task('Standalone commit task'), next=task('Reviewed next task'), all=task('Reviewed all task');
 command(0,'workspace-setup',{});
 function skillText(index) {
  return fs.readFileSync(path.join(root,'.agents/skills',names[index],'SKILL.md'),'utf8');
 }
 assert.match(skillText(0),/implementation_operation: "implement-next"/);
 assert.match(skillText(1),/implementation_operation: "work-through-next"/);
 assert.match(skillText(1),/merge-reviewed/);
 assert.match(skillText(2),/implementation_operation: "implement-all"/);
 assert.match(skillText(2),/merge locally into the recorded launch branch/);

 const review=command(1,'start',{implementation_operation:'work-through-next'},['--standalone','--id',next]);
 const merge=command(2,'start',{implementation_operation:'implement-all',snapshot_ids:[all]},['--standalone','--mode','all']);
 assert.equal(review.workspace.base_commit,launch);
 assert.equal(merge.workspace.base_commit,launch);
 assert.equal(review.reviewed_local_delivery.launch.ref,'refs/heads/launch');
 assert.equal(review.reviewed_local_delivery.merge_at_finish,false);
 assert.equal(merge.reviewed_local_delivery.merge_at_finish,true);
 assert.notEqual(merge.workspace.branch,review.workspace.branch);
 command(0,'begin',{task_id:leaf,implementation_operation:'implement-next'},['--standalone']);
 write(root,'source.py','value = 2\n');
 const sealed=command(0,'implemented',{task_id:leaf,changed_files:['source.py']},['--standalone']);
 assert.equal(sealed.git_review_identity.head,launch);
 assert.equal(git('rev-parse','HEAD'),launch);
});

test('installed Full Cycle hands off focused commands and admits the linked suite only in PR final validation',t=>{
 const base=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-worker-brief-')));
 t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'product'),remote=path.join(base,'remote.git');
 fs.mkdirSync(root);
 const git=(checkout,...args)=>run('git',['-C',checkout,...args]);
 git(root,'init','-b','develop');
 git(root,'config','user.name','Fixture');
 git(root,'config','user.email','fixture@example.invalid');
 write(root,'.gitignore','.agents/\n.skill-tree/*\n!.skill-tree/validation-recipes.json\n');
 write(root,'source.py','value = 1\n');
 write(root,'package.json',{name:'focused-worker-fixture'});
 const link={path:'final-suite.json',check_id:'all'};
 const suite={checks:[{id:'all',argv:['python3','-V']}]};
 const recipes={schema:1,recipes:{
  'focused':{lane:'unit',argv:['python3','{file}']},
  'all-checks':{lane:'unit',argv:suite.checks[0].argv,delivery_validation:link},
 }};
 write(root,link.path,suite);
 write(root,'.skill-tree/validation-recipes.json',recipes);
 git(root,'add','.');
 git(root,'commit','-m','Commit the fixture validation declarations');
 run('git',['init','--bare',remote]);
 git(root,'remote','add','origin',remote);
 git(root,'push','origin','develop');

 const install=[cli,'--target',root,'--only','codex','--flavor','general','--skills','skill-tree-full-cycle','skill-tree-pr-review-cycle'];
 write(root,link.path,{checks:[{id:'all',argv:['python3','-VV']}]});
 const mismatch=spawnSync(process.execPath,[...install,'--dry-run'],{encoding:'utf8',timeout:30000});
 assert.notEqual(mismatch.status,0);
 assert.match(mismatch.stdout+mismatch.stderr,/differs from the declared final check/);
 write(root,link.path,suite);
 run(process.execPath,install);
 const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));
 assert.match(profile.inputs[link.path],/^[a-f0-9]{64}$/);
 assert.ok(profile.recipes['all-checks'].input_paths.includes(link.path));

 const future='.skill-tree/documents/future.md';
 const checkpoint='.skill-tree/documents/future.json';
 write(root,future,'# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 const helper=path.join(root,'.agents/skills/skill-tree-full-cycle/scripts/workflow-state.py');
 const prHelper=path.join(root,'.agents/skills/skill-tree-pr-review-cycle/scripts/pr-review-state.py');
 let step=0;
 function command(script,action,target,request,extra=[]){
  const args=['-B',script,action,target,...extra];
  if(request!==undefined){
   const input=path.join(base,`request-${step++}.json`);
   write(base,path.basename(input),request);
   args.push('--input',input);
  }
  return JSON.parse(run('python3',args));
 }
 function wf(action,target=root,request,extra=[]){return command(helper,action,target,request,extra);}
 const title='Scoped worker fixture',goal='Preserve the observable fixture.';
 const pending=wf('intake',root,{title,description:'Verify the managed handoff.',expected_behavior:goal});
 const check={id:'point',recipe_id:'focused',criteria:[goal],sources:['source.py'],
              parameters:{file:'source.py'},assertion:goal,timing:'immediate'};
 const body='Goal:\n- '+goal+'\n\nTouch:\n- source.py\n\nValidation:\n```json\n'
  +JSON.stringify({checks:[check,{...check,id:'early-suite',recipe_id:'all-checks',parameters:{}}]})
  +'\n```\n\nAcceptance:\n- '+goal+'\n';
 const task=wf('process',root,{selectors:[pending.id],
  dispositions:{[pending.id]:{status:'promoted',reason:'The fixture covers the exact handoff.'}},
  tasks:[{title,body,parent_pending_ids:[pending.id]}]}).created_ids[0];
 wf('workspace-setup',root,{});
 const worktree=path.join(base,'worktree');
 const started=wf('start',root,{worktree,delivery_authorization:{pr:true,target_branch:'develop'}},
                  ['--standalone','--mode','next','--id',task]);
 run(started.profile_handoff.argv[0],started.profile_handoff.argv.slice(1));
 const scope=['--run-id',started.id];
 const before=fs.readFileSync(path.join(root,checkpoint));
 const handoff=wf('next',worktree,undefined,scope).worker_brief;
 assert.deepEqual(fs.readFileSync(path.join(root,checkpoint)),before);
 assert.equal(handoff.task_id,task);
 assert.equal(handoff.checkout,worktree);
 assert.deepEqual(handoff.checks[0].argv,['python3','source.py']);
 assert.deepEqual(handoff.checks[1].delivery_validation,link);
 assert.equal(handoff.checks[1].status,'delivery-validation-only');
 assert.equal(handoff.checks[1].argv,undefined);
 assert.deepEqual(wf('advance',worktree,undefined,scope).worker_brief,handoff);
 const checkpointPath=path.join(root,checkpoint);
 const legacy=JSON.parse(fs.readFileSync(checkpointPath));
 delete legacy.run_registry.runs[started.id].initial_profile;
 fs.writeFileSync(checkpointPath,JSON.stringify(legacy));
 const oldHandoff=wf('next',worktree,undefined,scope);
 assert.equal(oldHandoff.task_id,task);
 assert.equal(oldHandoff.phase,'implement');
 assert.deepEqual(oldHandoff.worker_brief.checks,[]);
 assert.match(oldHandoff.worker_brief.prerequisite,/re-admit the selected worktree profile before requesting worker commands/);
 wf('admit',root,{},scope);
 assert.deepEqual(wf('next',worktree,undefined,scope).worker_brief,handoff);
 wf('begin',worktree,{task_id:task},scope);
 const checkpointed=fs.readFileSync(path.join(root,checkpoint));
 const reject=path.join(base,'rejected-check.json');
 write(base,path.basename(reject),{task_id:task,check_id:'early-suite'});
 const denied=spawnSync('python3',[helper,'prepare-check',worktree,...scope,'--input',reject],{encoding:'utf8',timeout:30000});
 assert.equal(denied.status,2,denied.stdout+denied.stderr);
 assert.match(denied.stdout,/requires the declared PR final validation phase/);
 assert.deepEqual(fs.readFileSync(path.join(root,checkpoint)),checkpointed);

 const linkedProfile=path.join(worktree,'.skill-tree/installation/profile.json');
 const ownerManager=path.join(worktree,'.skill-tree/installation/manager.js');
 const ownedBytes=fs.readFileSync(linkedProfile),managerBytes=fs.readFileSync(ownerManager);
 const invalid=JSON.parse(ownedBytes);
 delete invalid.recipes['all-checks'].delivery_validation;
 delete invalid.format;
 fs.writeFileSync(linkedProfile,JSON.stringify(invalid));
 const sentinel=path.join(base,'unexpected-manager-execution');
 fs.writeFileSync(ownerManager,'require("node:fs").writeFileSync('+JSON.stringify(sentinel)+',"invoked");');
 for(const args of [
  [helper,'next',worktree,...scope],
  [helper,'prepare-check',worktree,...scope,'--input',reject],
 ]){
  const forged=spawnSync('python3',args,{encoding:'utf8',timeout:30000});
  assert.equal(forged.status,2,forged.stdout+forged.stderr);
  assert.match(forged.stdout,/differs from the admitted recipe profile/);
 }
 assert.deepEqual(fs.readFileSync(path.join(root,checkpoint)),checkpointed);
 assert.equal(fs.existsSync(sentinel),false);
 fs.writeFileSync(ownerManager,managerBytes);
 fs.writeFileSync(linkedProfile,ownedBytes);
 const allowed=wf('prepare-check',worktree,{task_id:task,check_id:'point'},scope);
 assert.deepEqual(allowed.recipe.argv,handoff.checks[0].argv);

 const publication=path.join(base,'publication-source');
 run('git',['clone','--branch','develop',remote,publication]);
 git(publication,'config','user.name','Fixture');
 git(publication,'config','user.email','fixture@example.invalid');
 git(publication,'switch','-c','review-source');
 write(publication,'source.py','value = 2\n');
 git(publication,'add','source.py');
 git(publication,'commit','-m','Review the fixture candidate');
 const authority={instruction:'Review and then merge into develop',instruction_origin:'owner',target_branch:'develop'};
 const preflight=command(prHelper,'preflight',publication,authority);
 const snapshot={...preflight,state:'OPEN',pr:{id:'fixture-pr',number:1,url:'https://example.invalid/fixture/pull/1'},
                 threads:[],reviews:[],comments:[],checks:[]};
 command(prHelper,'init',publication,{...authority,snapshot,final_validation:{path:link.path}});
 command(prHelper,'review',publication,{snapshot,review:{
  head:snapshot.head,base_oid:snapshot.base_oid,target_branch:'develop',files:snapshot.changed_files,
  context_inspected:true,discussions_inspected:true,checks_inspected:true,findings:[],
 }});
 const ready=command(prHelper,'final-validation',publication,{snapshot,final_validation:{action:'prepare',attempt_id:'final'}});
 assert.deepEqual(ready.final_validation.checks,suite.checks);
 assert.equal(ready.final_validation.attempts.final.status,'prepared');
});

test('owned Web profile refresh binds exact Playwright drift to the same stopped run',t=>{
 const base=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-playwright-readmit-'));
 t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const root=path.join(base,'queue'),remote=path.join(base,'remote.git'),working=path.join(base,'working');
 fs.mkdirSync(root);
 const git=(...args)=>run('git',['-C',root,...args]);
 git('init','-b','develop');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
 const pkg={name:'playwright-readmit-fixture',scripts:{test:'node --test'}};
 const initial='export default { use: { baseURL: "http://127.0.0.1:4000" } };\n';
 const changed='export default { use: { baseURL: "http://127.0.0.1:4001" } };\n';
 write(root,'package.json',pkg);
 write(root,'playwright.config.ts',initial);
 write(root,'source.txt','The recorded static behavior.\n');
 write(root,'partial.txt','Original implementation input.\n');
 write(root,'.skill-tree/validation-recipes.json',{schema:1,recipes:{
  'fixture-browser':{lane:'browser',argv:['node','browser-fixture.js'],input_paths:[]}
 }});
 const future='.skill-tree/documents/future.md',state='.skill-tree/documents/future.json';
 write(root,future,'# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 git('add','.');git('commit','-m','Record tracked Playwright discovery inputs');
 run('git',['init','--bare',remote]);git('remote','add','origin',remote);git('push','origin','develop');
 const skill='skill-tree-work-through-next';
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','web','--skills',skill]);
 const helper=path.join(root,'.agents/skills',skill,'scripts/workflow-state.py');
 function invoke(operation,target,payload,options=[],fail){
  const request=path.join(base,'request.json');
  const args=[helper,operation,target,...options];
  if(payload){fs.writeFileSync(request,JSON.stringify(payload));args.push('--input',request);}
  const result=spawnSync('python3',args,{encoding:'utf8',timeout:55000});
  if(fail){assert.equal(result.status,2,result.stdout+result.stderr);assert.match(result.stdout+result.stderr,fail);return;}
  assert.equal(result.status,0,result.stdout+result.stderr);
  return JSON.parse(result.stdout);
 }
 const pending=invoke('intake',root,{title:'Preserve selected Web progress',description:'Guard owned browser discovery.',
  expected_behavior:'Resume the same Web run after exact configured approval.'});
 const staticCriterion='The static input retains the observed behavior.',browserCriterion='Exercise the configured fixture.';
 const checks=[
  {id:'static',recipe_id:'static-inspection',assertion:staticCriterion,criteria:[staticCriterion],
   sources:['source.txt'],parameters:{},timing:'immediate'},
  {id:'browser',recipe_id:'fixture-browser',assertion:browserCriterion,criteria:[browserCriterion],
   sources:['source.txt'],parameters:{},timing:'immediate'}
 ];
 const body='Goal:\n- Preserve selected Web progress.\n\nTouch:\n- partial.txt\n\nValidation:\n```json\n'+
  JSON.stringify({checks})+'\n```\n\nAcceptance:\n- '+staticCriterion+'\n- '+browserCriterion+'\n';
 const processed=invoke('process',root,{selectors:[pending.id],
  dispositions:{[pending.id]:{status:'promoted',reason:'The controlled Web fixture supplies the required bounds.'}},
  tasks:[{title:'Preserve selected Web progress',body,parent_pending_ids:[pending.id]}]});
 const task_id=processed.created_ids[0];
 invoke('workspace-setup',root,{});
 const runReceipt=invoke('start',root,{worktree:working},['--id',task_id]);
 const selected=['--run-id',runReceipt.id];
 invoke('prepare-worktree-profile',working,null,selected);
 invoke('begin',working,{task_id},selected);
 const inspectBrowser=()=>invoke('validation-preflight',working,{task_id,check_id:'browser'},selected);
 const oldBrowser=inspectBrowser();
 write(working,'partial.txt','Unfinished selected task changes.\n');
 write(working,'static.log','The exact source assertion passed.\n');
 const attempt=invoke('prepare-check',working,{task_id,check_id:'static'},selected);
 invoke('checkpoint',working,{phase:'refresh-profile',stop_reason:'Installation profile changed; re-admit before continuation'},selected);
 write(working,'playwright.config.ts',changed);
 const previewRequest={playwright_refresh:{action:'preview'}};
 invoke('admit',working,previewRequest,selected,/original check attempt/);
 invoke('record-check',working,{task_id,check_id:'static',attempt_id:attempt.attempt_id,result:'pass',
  classification:'executed-control',actual_lane:'static',environment_identity:attempt.environment_identity,
  cleanup:'The fixture started no runtime process.',assertions:[{assertion:staticCriterion,result:'pass'}],
  evidence:['static.log']},selected);
 const statePath=path.join(root,state),queuePath=path.join(root,future);
 const beforeState=fs.readFileSync(statePath),beforeQueue=fs.readFileSync(queuePath);
 const beforeProfile=fs.readFileSync(path.join(working,'.skill-tree/installation/profile.json'));
 const preview=invoke('admit',working,previewRequest,selected);
 assert.equal(preview.status,'approval-required');
 assert.equal(preview.task_id,task_id);
 assert.deepEqual(preview.affected_checks.map(row=>row.check_id),['browser']);
 assert.notEqual(preview.plan.playwright_input.before,preview.plan.playwright_input.after);
 assert.deepEqual(fs.readFileSync(statePath),beforeState);
 assert.deepEqual(fs.readFileSync(queuePath),beforeQueue);
 assert.deepEqual(fs.readFileSync(path.join(working,'.skill-tree/installation/profile.json')),beforeProfile);
 const approval={action:'apply',expected_preview_sha256:preview.preview_sha256,
  owner_instruction:'Fixture owner approves the exact Playwright discovery input for the original stopped run.'};
 invoke('admit',working,{playwright_refresh:{...approval,expected_preview_sha256:'0'.repeat(64)}},selected,/preview changed/);
 write(working,'package.json',{...pkg,description:'A separate discovered input changed.'});
 invoke('admit',working,{playwright_refresh:approval},selected,/material or unknown changes/);
 write(working,'package.json',pkg);
 assert.deepEqual(fs.readFileSync(statePath),beforeState);
 const requestFile=path.join(base,'approved-playwright.json');
 fs.writeFileSync(requestFile,JSON.stringify({playwright_refresh:approval}));
 const interrupt=`
import runpy, sys
entry=runpy.run_path(sys.argv[1])
scope=entry['main'].__globals__
original=scope['owned_profile_installer']
def lose_ack(store, request, mode, **kwargs):
    result=original(store, request, mode, **kwargs)
    if mode=='activate' and request.get('kind')=='playwright-discovery':
        raise scope['WorkflowError']('Injected loss after the exact Playwright activation')
    return result
scope['owned_profile_installer']=lose_ack
raise SystemExit(entry['main'](sys.argv[2:]))
`;
 const lost=spawnSync('python3',['-B','-c',interrupt,helper,'admit',working,...selected,'--input',requestFile],
  {encoding:'utf8',timeout:55000});
 assert.equal(lost.status,2,lost.stdout+lost.stderr);
 assert.match(lost.stdout+lost.stderr,/Injected loss after the exact Playwright activation/);
 const retained=JSON.parse(fs.readFileSync(statePath)).run_registry.runs[runReceipt.id].compatible_profile_refresh;
 assert.equal(retained.kind,'playwright-discovery');
 invoke('admit',working,{compatible_refresh:true},selected,/original exact Playwright approval/);
 const result=invoke('admit',working,{playwright_refresh:approval},selected);
 assert.equal(result.operation_id,retained.operation_id);
 assert.equal(result.run_id,runReceipt.id);
 assert.equal(result.task_id,task_id);
 assert.deepEqual(invoke('admit',working,{playwright_refresh:approval},selected),{...result,replayed:true});
 assert.equal(fs.readFileSync(path.join(working,'partial.txt'),'utf8'),'Unfinished selected task changes.\n');
 assert.deepEqual(fs.readFileSync(queuePath),beforeQueue);
 const afterState=JSON.parse(fs.readFileSync(statePath)),originalState=JSON.parse(beforeState);
 assert.deepEqual(afterState.run_registry.claims,originalState.run_registry.claims);
 assert.deepEqual(afterState.task_progress,originalState.task_progress);
 assert.equal(afterState.run_registry.runs[runReceipt.id].phase,'implement');
 const currentBrowser=inspectBrowser();
 assert.notEqual(currentBrowser.recipe_environment,oldBrowser.recipe_environment);
 assert.equal(currentBrowser.execution.required,true);
 run('git',['-C',working,'add','playwright.config.ts']);
 run('git',['-C',working,'commit','-m','Record the approved fixture configuration']);
 const separateStop='A separate owner decision is still pending';
 invoke('checkpoint',working,{phase:'refresh-profile',stop_reason:separateStop,
  next_action:'Resolve the separate requirement'},selected);
 write(working,'playwright.config.ts',initial);
 const later=invoke('admit',working,previewRequest,selected);
 const retainedStop=invoke('admit',working,{playwright_refresh:{...approval,
  expected_preview_sha256:later.preview_sha256}},selected);
 assert.equal(retainedStop.stop_reason,separateStop);
 const stopped=JSON.parse(fs.readFileSync(statePath)).run_registry.runs[runReceipt.id];
 assert.equal(stopped.phase,'refresh-profile');
 assert.equal(stopped.stop_reason,separateStop);
 assert.equal(stopped.next_action,'Resolve the separate requirement');
});
