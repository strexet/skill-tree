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
