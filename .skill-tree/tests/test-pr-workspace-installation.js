const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const core=path.resolve(__dirname,'..'),cli=path.join(core,'bin/install.js');
function run(command,args,options={}){const r=spawnSync(command,args,{encoding:'utf8',timeout:30000,...options});assert.equal(r.status,0,r.stdout+r.stderr);return r.stdout;}
function write(root,rel,value){const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof value==='string'?value:JSON.stringify(value));}
for(const flavor of ['general','web','unity'])test(`installed ${flavor} PR/controller packages execute without source or sibling packages`,t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-pr-installed-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 run('git',['init','-b','feature/example',root]);
 write(root,'package.json',{scripts:{test:'node --test'}});
 if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.27f2');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});}
 const names=['skill-tree-pr-review-cycle','skill-tree-work-through-next','skill-tree-implement-all','skill-tree-full-cycle'];
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor',flavor,'--skills',...names]);
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor',flavor,'--skills',...names,'--verify']);
 const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));assert.equal(profile.flavor,flavor);assert.equal(profile.worktree_environment.schema,1);
 // Copy one installed package outside the target and remove access to target siblings.
 for(const name of names){
  const isolated=path.join(root,'isolated',name);fs.cpSync(path.join(root,'.agents/skills',name),isolated,{recursive:true});
  const request=path.join(root,'request.json');fs.writeFileSync(request,JSON.stringify({current_branch:'Feature/Case',instruction:'with merge',target_branch:'release/example'}));
  assert.match(run('python3',[path.join(isolated,'scripts/pr-review-state.py'),'--help'],{cwd:os.tmpdir()}),/final-validation/);
  const helper=path.join(isolated,'scripts/pr-review-state.py');const result=JSON.parse(run('python3',[helper,'parameters',root,'--input',request],{cwd:os.tmpdir()}));
  assert.equal(result.source_branch,'Feature/Case');assert.equal(result.target_branch,'release/example');assert.equal(result.merge,true);
  assert.ok(fs.existsSync(path.join(isolated,'scripts/run-workspaces.py')));assert.match(fs.readFileSync(path.join(isolated,'references/project-profile.md'),'utf8'),new RegExp('Flavor: '+flavor));
  if(name==='skill-tree-full-cycle'){
   const contract=fs.readFileSync(path.join(isolated,'references/full-cycle.md'),'utf8');
   for(const match of contract.matchAll(/\]\(([^)#]+)(?:#[^)]+)?\)/g)){
    assert.ok(fs.existsSync(path.join(isolated,'references',match[1])),match[1]);
   }
   run('python3',[path.join(isolated,'scripts/workflow-state.py'),'--help'],{cwd:os.tmpdir()});
   assert.ok(fs.existsSync(path.join(isolated,'scripts/validate-future-document.py')));
  }
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

test('the installed Full Cycle prepares the original existing PR handoff',t=>{
 const fixture=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-installed-handoff-'));
 t.after(()=>fs.rmSync(fixture,{recursive:true,force:true}));
 const root=path.join(fixture,'project'), request=path.join(fixture,'request.json');
 const git=(...args)=>run('git',['-C',root,...args]).trim();
 run('git',['init','-b','develop',root]);
 git('config','user.name','Fixture');
 git('config','user.email','fixture@example.test');
 write(root,'.gitignore','.skill-tree/\n.agents/\nAGENTS.md\n');
 write(root,'product.txt','Base\n');
 git('add','--','.gitignore','product.txt');
 git('commit','-m','Fixture base');
 const base=git('rev-parse','HEAD');
 git('switch','-c','feature/alternate');
 write(root,'product.txt','Reviewed source\n');
 git('add','--','product.txt');
 git('commit','-m','Fixture source');
 const head=git('rev-parse','HEAD'), remote='https://github.example/fixture/product.git';
 git('remote','add','origin',remote);
 run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','general','--skills','skill-tree-full-cycle']);
 const helper=path.join(root,'.agents/skills/skill-tree-full-cycle/scripts/pr-review-state.py');
 const binary=path.join(fixture,'bin'), calls=path.join(fixture,'gh-calls');
 const id={id:'PR_installed_fixture',number:43,url:'https://github.example/fixture/product/pull/43'};
 const github={...id,state:'OPEN',headRefOid:head,baseRefOid:base,headRefName:'feature/alternate',
  baseRefName:'develop',mergeable:'MERGEABLE',reviewDecision:'APPROVED',mergeCommit:null,
  statusCheckRollup:[{name:'Verify source',conclusion:'SUCCESS'}],changedFiles:1,isCrossRepository:false,
  headRepository:{name:'product'},headRepositoryOwner:{login:'fixture'}};
 write(fixture,'bin/gh',[
  '#!/usr/bin/env node',
  "const assert=require('node:assert/strict'),fs=require('node:fs'),args=process.argv.slice(2);",
  "fs.appendFileSync(process.env.FIXTURE_GH_CALLS,JSON.stringify(args)+'\\n');",
  "if(args[0]==='pr'){assert.deepEqual(args.slice(1,5),['view','43','--repo','github.example/fixture/product']);console.log(process.env.FIXTURE_GH_PR);}",
  "else{assert.equal(args[0],'api');assert.equal(args[args.indexOf('--hostname')+1],'github.example');",
  "if(args[1]==='graphql'){assert.ok(args.includes('number=43'));console.log(JSON.stringify({data:{repository:{pullRequest:{id:'PR_installed_fixture',reviewThreads:{nodes:[],pageInfo:{hasNextPage:false}}}}}}));}",
  "else{assert.deepEqual(args.slice(1,3),['--method','GET']);assert.ok(args.includes('--paginate')&&args.includes('--slurp'));console.log(args[3].endsWith('/files')?'[[{\"filename\":\"product.txt\"}]]':'[[]]');}}",
 ].join('\n'));
 fs.chmodSync(path.join(binary,'gh'),0o755);
 const env={...process.env,PATH:binary+path.delimiter+process.env.PATH,FIXTURE_GH_CALLS:calls,FIXTURE_GH_PR:JSON.stringify(github)};
 const invoke=(command,payload,publication)=>{
  fs.writeFileSync(request,JSON.stringify(payload));
  return JSON.parse(run('python3',['-B',helper,command,root,'--input',request,
   ...(publication?['--publication-id',publication]:[])],{cwd:fixture,env}));
 };
 const {createHash}=require('node:crypto');
 const sha=value=>createHash('sha256').update(value).digest('hex');
 const original=invoke('init',{snapshot:{repo_id:sha(git('rev-list','--max-parents=0','HEAD')),
  remote:'origin',remote_id:sha(remote),source_branch:'feature/alternate',target_branch:'develop',
  head,base_oid:base,changed_files:['product.txt'],pr:id,state:'OPEN'},target_branch:'develop'});
 const carrier=path.join(root,'.skill-tree/history/publications/pub-'+original.publication_id+'.json');
 const before=fs.readFileSync(carrier), refs=git('show-ref');
 const input={source_checkout:fs.realpathSync(root),head,base_oid:base,
  provider_policy:{host:'github.example',repository:'fixture/product',target_branch:'develop',
   required_check_names:['Verify source'],approvals_required:true,reference:'Fixture target-rule inspection.'}};
 const handoff=invoke('prepare-handoff',input,original.publication_id);
 assert.deepEqual(handoff,invoke('prepare-handoff',input,original.publication_id));
 assert.deepEqual(handoff.pr,id);
 assert.equal(handoff.publication_sha256,sha(before));
 assert.deepEqual(handoff.next.input.snapshot.checks,[{name:'Verify source',status:'success',required:true}]);
 assert.equal(handoff.next.input.snapshot.approved,true);
 assert.equal(handoff.next.command,'observe');
 assert.deepEqual(fs.readFileSync(carrier),before);
 assert.equal(git('show-ref'),refs);
 assert.equal(fs.readFileSync(calls,'utf8').trim().split('\n').length,14);
 const seen=invoke(handoff.next.command,handoff.next.input,original.publication_id);
 assert.deepEqual(seen.pr,id);
 assert.deepEqual(seen.authorization,original.authorization);
 assert.equal(git('show-ref'),refs);
});
