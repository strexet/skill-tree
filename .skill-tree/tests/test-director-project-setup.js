'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const test = require('node:test');

test('installed Setup registers existing, default and custom projects with selected hosts and preserves existing Git', t => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'director-project-choice-')));
  t.after(() => fs.rmSync(base,{recursive:true,force:true}));
  const root = path.join(base,'workspace'), seed = path.join(base,'seed'), home = path.join(root,'.skill-tree-director');
  const env = {...process.env,GIT_CONFIG_GLOBAL:path.join(base,'gitconfig'), GIT_TERMINAL_PROMPT:'0'};
  function run(command,args,cwd=base) {
    const result = spawnSync(command,args,{cwd,env,encoding:'utf8',timeout:180000});
    assert.equal(result.status,0,result.stdout+result.stderr);
    return result.stdout.trim();
  }
  const git = (dir, ...args) => run('git',['-C',dir,...args]);
  const data = (dir,name) => JSON.parse(fs.readFileSync(path.join(dir,name)));
  const init = (dir,branch) => {fs.mkdirSync(dir);git(dir,'init','-q','-b',branch);};
  const commit = dir => {git(dir,'add','.');git(dir,'-c','user.name=Fixture','-c','user.email=fixture@invalid.test','commit','-qm','Initial');};
  init(seed,'develop');
  fs.mkdirSync(path.join(seed,'.skill-tree/config'),{recursive:true});
  fs.mkdirSync(path.join(seed,'.skill-tree/documents'));
  fs.writeFileSync(path.join(seed,'.skill-tree/config/repository.json'),'{"role":"source"}');
  fs.writeFileSync(path.join(seed,'.skill-tree/documents/future.md'),'# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  commit(seed);
  git(base,'config','--file',env.GIT_CONFIG_GLOBAL,'url.'+pathToFileURL(seed).href+'.insteadOf','https://github.com/strexet/skill-tree.git');
  init(root,'main');fs.writeFileSync(path.join(root,'index.html'),'<!DOCTYPE html>');commit(root);
  const head=git(root,'rev-parse','HEAD');
  run(process.execPath,[path.join(__dirname,'../bin/install.js'),'--only','codex','--only','claude-code','--target',root]);
  const app=path.join(home,data(home,'workspace.json').setup_entry),input=path.join(base,'request.json');
  const invoke=(cmd,payload)=>{fs.writeFileSync(input,JSON.stringify(payload));return JSON.parse(run('python3',['-B',app,cmd,home,'--input',input]));};
  const custom=path.join(base,'custom-location');
  for (const [choice,target,flavor] of [
    [{kind:'existing',name:'site',path:root},root,'web'],
    [{kind:'new',name:'example'},path.join(root,'example'),'general'],
    [{kind:'new',name:'external',path:custom,flavor:'web'},custom,'web']]) {
    assert.equal(invoke('project-preview',choice).checkout,target);
    const result=invoke('project-setup',choice);
    assert.equal(result.status,'registered');assert.equal(result.checkout,target);assert.equal(result.flavor,flavor);
    const installed=data(target,'.skill-tree/installation/profile.json');
    for(const [dest,host] of [['.agents/skills','codex'],['.claude/skills','claude-code']]) {
      assert.ok(installed.destinations[dest+'/skill-tree-add-pending-task'].providers.includes(host));
    }
    const registry=data(home,'.skill-tree/director/registry.json');
    assert.equal(registry.areas[choice.name].queue_id,result.queue_id);
    assert.equal(invoke('project-setup',choice).queue_id,result.queue_id);
  }
  assert.equal(git(root,'rev-parse','HEAD'),head);
});
