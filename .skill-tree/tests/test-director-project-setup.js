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
  const env = {...process.env, GIT_TERMINAL_PROMPT:'0'};
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
  // Compose the test installation from a private package source pinned to the
  // fixture. Production verifies the effective upstream URL before acquisition.
  const composed = path.join(base, 'fixture-source', '.skill-tree');
  fs.mkdirSync(composed, {recursive:true});
  for (const name of ['common','config','domains','lib','src','templates','tests/fixtures/director']) {
    fs.cpSync(path.join(__dirname, '..', name), path.join(composed, name), {recursive:true});
  }
  const maintenance = path.join(composed, 'common/scripts/director-maintenance.py');
  const original = fs.readFileSync(maintenance, 'utf8');
  const fixture = original.replace("UPSTREAM = 'https://github.com/strexet/skill-tree.git'",
    "UPSTREAM = '" + pathToFileURL(seed).href + "'");
  assert.notEqual(fixture, original);
  fs.writeFileSync(maintenance, fixture);
  init(root,'main');fs.writeFileSync(path.join(root,'index.html'),'<!DOCTYPE html>');commit(root);
  const head=git(root,'rev-parse','HEAD');
  const install = host => run(process.execPath,[path.join(__dirname,'../bin/install.js'),'--only',host,
    '--target',root,'--source',composed]);
  install('codex');
  const app=path.join(home,data(home,'workspace.json').setup_entry),input=path.join(base,'request.json');
  const invoke=(cmd,payload)=>{
    const args=['-B',app,cmd,home];
    if(payload){fs.writeFileSync(input,JSON.stringify(payload));args.push('--input',input);}
    return JSON.parse(run('python3',args));
  };
  assert.deepEqual(invoke('project-menu').choices,['existing','new','later']);
  const custom=path.join(base,'custom-location');
  for (const [choice,target,flavor] of [
    [{kind:'existing',name:'site',path:root},root,'web'],
    [{kind:'new',name:'example'},path.join(root,'example'),'general'],
    [{kind:'new',name:'external',path:custom,flavor:'web'},custom,'web']]) {
    assert.equal(invoke('project-preview',choice).checkout,target);
    const result=invoke('project-setup',choice);
    assert.equal(result.status,'registered');assert.equal(result.checkout,target);assert.equal(result.flavor,flavor);
    if (choice.name === 'site') {
      const menu=invoke('project-menu');
      assert.deepEqual(menu.choices,['intake','status','audit','setup']);
      assert.deepEqual(menu.projects.map(project=>project.id),['site']);
      assert.equal(menu.projects[0].queue_id,result.queue_id);
      assert.equal(menu.projects[0].core_routing,'guarded');
      const route=invoke('project-route',{operation:'implement-all'});
      assert.deepEqual(route.project,menu.projects[0]);
      assert.equal(route.route,'director');
      assert.deepEqual(route.task_ids,[]);
      assert.equal(invoke('project-route',{operation:'implement-all',route:'direct'}).route,'direct');
      const future='.skill-tree/documents/future.md';
      const childBefore=fs.readFileSync(path.join(root,future),'utf8');
      const directorBefore=fs.readFileSync(path.join(home,future),'utf8');
      const skill=path.join(root,'.agents/skills/skill-tree-add-pending-task/scripts/workflow-state.py');
      const intake={title:'Check the site',description:'Check the site.',expected_behavior:'Show the site.'};
      fs.writeFileSync(input,JSON.stringify(intake));
      const args=['-B',skill,'intake',root,'--standalone','--input',input];
      const guarded=spawnSync('python3',args,{cwd:root,env,encoding:'utf8'});
      assert.notEqual(guarded.status,0);
      assert.match(guarded.stdout+guarded.stderr,/project-route/);
      assert.equal(fs.readFileSync(path.join(root,future),'utf8'),childBefore);
      assert.equal(fs.readFileSync(path.join(home,future),'utf8'),directorBefore);
      const added=JSON.parse(run('python3',[...args,'--direct-project'],root));
      const pending=invoke('project-route',{operation:'process',task_ids:[added.id]});
      assert.deepEqual(pending.task_ids,[added.id]);
      assert.equal(pending.project.queue_id,result.queue_id);
      const registryPath=path.join(home,'.skill-tree/director/registry.json');
      const current=fs.readFileSync(registryPath);
      const restricted=JSON.parse(current);
      restricted.areas.site.allowed_effects=['status'];
      fs.writeFileSync(registryPath, JSON.stringify(restricted));
      const unavailable=invoke('project-route',{operation:'process'});
      assert.equal(unavailable.status,'prerequisite');
      assert.deepEqual(unavailable.task_ids,[]);
      assert.equal(unavailable.queue_sha256,undefined);
      fs.writeFileSync(registryPath,current);
      assert.notEqual(fs.readFileSync(path.join(root,future),'utf8'),childBefore);
      assert.equal(fs.readFileSync(path.join(home,future),'utf8'),directorBefore);
      const existingProfile = data(target,'.skill-tree/installation/profile.json');
      assert.equal(existingProfile.destinations['.claude/skills/skill-tree-add-pending-task'],undefined);
      install('claude-code');
      assert.deepEqual(invoke('project-preview',choice).providers,['codex','claude-code']);
      const extended = invoke('project-setup',choice);
      assert.equal(extended.queue_id,result.queue_id);
      assert.deepEqual(extended.providers,['codex','claude-code']);
    }
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
