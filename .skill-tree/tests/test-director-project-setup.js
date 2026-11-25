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
  const root = path.join(base,'workspace'), seed = path.join(base,'seed'), home = path.join(root,'.skill-tree/.director');
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
  const instructions = path.join(root, 'AGENTS.md');
  const customInstructions = Buffer.from('Project rules\r\nUse its own checked fixtures.');
  fs.writeFileSync(instructions, customInstructions);
  fs.mkdirSync(path.join(root,'.skill-tree/documents'),{recursive:true});
  fs.copyFileSync(path.join(seed,'.skill-tree/documents/future.md'),path.join(root,'.skill-tree/documents/future.md'));
  const head=git(root,'rev-parse','HEAD');
  const install = host => run(process.execPath,[path.join(__dirname,'../bin/install.js'),'--only',host,
    '--target',root,'--source',composed]);
  const coreSetup = path.join(__dirname,'../common/scripts/workflow-state.py');
  run(process.execPath,[path.join(__dirname,'../bin/install.js'),'--only','codex','--target',root,
    '--source',composed,'--project','--flavor','web']);
  install('codex');
  assert.ok(fs.readFileSync(instructions).subarray(0, customInstructions.length).equals(customInstructions));
  assert.match(fs.readFileSync(instructions, 'utf8'), /project-route.*project-menu/);
  const app=path.join(home,data(home,'workspace.json').setup_entry),input=path.join(base,'request.json');
  const invoke=(cmd,payload)=>{
    const args=['-B',app,cmd,home];
    if(payload){fs.writeFileSync(input,JSON.stringify(payload));args.push('--input',input);}
    return JSON.parse(run('python3',args));
  };
  assert.deepEqual(invoke('project-menu').choices,['existing','new','later']);
  const unregistered = invoke('project-route',{operation:'intake',route:'direct'});
  assert.equal(unregistered.project.registered,false);
  assert.equal(unregistered.project.checkout,root);
  assert.equal(unregistered.execution,'direct-project');
  assert.equal(unregistered.project.queue_id,null);
  run('python3',['-B',coreSetup,'workspace-setup',root]);
  const queueLocator = path.join(root,'.git/skill-tree-runtime.json');
  const savedLocator = fs.readFileSync(queueLocator);
  try {
    fs.unlinkSync(queueLocator);
    assert.throws(() => invoke('project-route',{operation:'intake',route:'direct'}), /Restore the canonical Core queue locator/);
  } finally {
    fs.writeFileSync(queueLocator,savedLocator);
  }
  const descriptorPath = path.join(home,'workspace.json');
  const descriptorBytes = fs.readFileSync(descriptorPath);
  try {
    fs.writeFileSync(descriptorPath, JSON.stringify({...JSON.parse(descriptorBytes),setup_entry:'other/setup/bin/director-entry.py'}));
    assert.throws(() => invoke('project-route',{operation:'discovery'}), /differs from the owned host destination/);
  } finally {
    fs.writeFileSync(descriptorPath,descriptorBytes);
  }
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
      const expected = data(composed, 'config/flavors.json');
      const inventory = invoke('project-route', {operation:'discovery'});
      assert.deepEqual(inventory.operations.map(row => row.operation),
        [...expected.core_operations, ...expected.flavors.director.operations]);
      const packageRoot = path.join(home, '.agents/skills');
      for (const entry of inventory.operations) {
        const routed = invoke('project-route', {operation:entry.operation, project_id:'site'});
        assert.equal(routed.route, 'director', entry.operation);
        assert.equal(routed.execution, entry.route, entry.operation);
        assert.ok(['preview', 'prerequisite'].includes(routed.status), entry.operation);
        if (entry.route === 'project-skill') {
          if (routed.status === 'preview') {
            assert.ok(routed.child_skill.startsWith(root + path.sep), entry.operation);
            assert.ok(fs.existsSync(routed.child_skill), entry.operation);
          } else {
            assert.deepEqual(routed.limitations, ['project-skill-unavailable'], entry.operation);
          }
        } else {
          assert.ok(routed.entry.startsWith(packageRoot + path.sep), entry.operation);
          assert.ok(fs.existsSync(routed.entry), entry.operation);
          assert.equal(typeof routed.command, 'string', entry.operation);
        }
      }
      assert.equal(invoke('project-route',{operation:'unregistered-operation'}).status, 'unsupported');
      const beforeFullCycle = fs.readFileSync(path.join(root,'.skill-tree/documents/future.md'));
      const fullCycle = invoke('project-route',{operation:'skill-tree-full-cycle',project_id:'site'});
      assert.equal(fullCycle.status, 'preview');
      assert.equal(fullCycle.execution, 'project-skill');
      assert.equal(fullCycle.child_skill, path.join(root,'.agents/skills/skill-tree-full-cycle/SKILL.md'));
      assert.deepEqual(fs.readFileSync(path.join(root,'.skill-tree/documents/future.md')), beforeFullCycle);
      assert.equal(git(root,'rev-parse','HEAD'),head);
      assert.equal(invoke('project-route',{operation:'intake',project_id:'site'}).project.id, 'site');
      assert.equal(invoke('project-route',{operation:'project-read'}).project.id, 'site');
      assert.equal(invoke('project-route',{operation:'registration'}).command, 'project-preview');
      const skillReceipt = path.join(root,'.skill-tree/installation/profile.json');
      const childOperation = 'skill-tree-create-documents-snapshot';
      const originalProfile = fs.readFileSync(skillReceipt);
      const childRoute = invoke('project-route',{operation:childOperation});
      const originalSkill = fs.readFileSync(childRoute.child_skill);
      try {
        const edited = Buffer.concat([originalSkill,Buffer.from('\nUnreviewed instruction.\n')]);
        const receipt = JSON.parse(originalProfile);
        receipt.destinations[path.relative(root,path.dirname(childRoute.child_skill))].files['SKILL.md'] =
          require('node:crypto').createHash('sha256').update(edited).digest('hex');
        fs.writeFileSync(childRoute.child_skill,edited);
        fs.writeFileSync(skillReceipt,JSON.stringify(receipt));
        assert.equal(invoke('project-route',{operation:childOperation}).status,'prerequisite');
      } finally {
        fs.writeFileSync(childRoute.child_skill,originalSkill);
        fs.writeFileSync(skillReceipt,originalProfile);
      }
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
      const directorProfile = path.join(home,'.skill-tree/installation/profile.json');
      const retainedProfile = fs.readFileSync(directorProfile);
      try {
        fs.unlinkSync(directorProfile);
        const missing = spawnSync('python3',args,{cwd:root,env,encoding:'utf8'});
        assert.notEqual(missing.status,0);
        assert.match(missing.stdout+missing.stderr,/Repair the registered shared Director profile/);
      } finally {
        fs.writeFileSync(directorProfile,retainedProfile);
      }
      const currentDescriptor = fs.readFileSync(descriptorPath);
      fs.unlinkSync(descriptorPath);
      try {
        const missing = spawnSync('python3',args,{cwd:root,env,encoding:'utf8'});
        assert.notEqual(missing.status,0);
        assert.match(missing.stdout+missing.stderr,/Repair the registered shared Director descriptor/);
      } finally {
        fs.writeFileSync(descriptorPath,currentDescriptor);
      }
      assert.equal(fs.readFileSync(path.join(root,future),'utf8'),childBefore);
      assert.equal(fs.readFileSync(path.join(home,future),'utf8'),directorBefore);
      const added=JSON.parse(run('python3',[...args,'--direct-project'],root));
      const statusEntry = path.join(packageRoot,'skill-tree-director-status/scripts/director-entry.py');
      fs.writeFileSync(input, JSON.stringify({project_work:{area_id:'site'}}));
      const projectStatus = JSON.parse(run('python3',['-B',statusEntry,'status',home,'--input',input]));
      assert.equal(projectStatus.project_work[0].tasks[0].id, added.id);
      assert.equal(projectStatus.project_work[0].total_tasks, 1);
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
  const workspaceStatus = invoke('project-route', {operation:'workspace-status'});
  assert.deepEqual(workspaceStatus.projects.map(project=>project.id),['example','external','site']);
  assert.deepEqual(workspaceStatus.input,{area_ids:['example','external','site']});
  const focusedStatus = invoke('project-route',{operation:'status',project_id:'site'});
  assert.deepEqual(focusedStatus.input,{area_ids:['site'],project_work:{area_id:'site'}});
  fs.writeFileSync(input, JSON.stringify(focusedStatus.input));
  const siteOnly = JSON.parse(run('python3',['-B',focusedStatus.entry,focusedStatus.command,home,'--input',input]));
  assert.deepEqual(siteOnly.areas.map(area=>area.id),['site']);
  assert.equal(siteOnly.project_work.length,1);
  const focusedAudit = invoke('project-route',{operation:'audit',project_id:'site'});
  assert.deepEqual(focusedAudit.input,{project_ids:['site']});
  fs.writeFileSync(input, JSON.stringify(focusedAudit.input));
  const auditResult = JSON.parse(run('python3',['-B',focusedAudit.entry,focusedAudit.command,home,'--input',input]));
  assert.deepEqual(auditResult.projects.map(project=>project.project_id),['site']);
  const linked = path.join(base, 'linked-workspace');
  git(root, 'worktree', 'add', '-qb', 'linked-routing', linked);
  run(process.execPath,[path.join(__dirname,'../bin/install.js'),'--only','codex','--target',linked,'--source',composed]);
  const linkedHome = path.join(linked, '.skill-tree/.director');
  const linkedEntry = path.join(linkedHome, data(linkedHome, 'workspace.json').setup_entry);
  const linkedCall = (command, payload) => {
    fs.writeFileSync(input, JSON.stringify(payload));
    return JSON.parse(run('python3',['-B',linkedEntry,command,linkedHome,'--input',input],linked));
  };
  const areas = [
    {id:'site', role:'web', checkout:linked},
    {id:'skill-tree-source', role:'source-maintenance', checkout:seed},
  ].map(area => ({...area, scope:'.', allowed_effects:['status','preview','intake'],
    capabilities:['core-task'], interface:{kind:'skill-tree',version:1}}));
  run('python3',['-B',path.join(__dirname,'../common/scripts/workflow-state.py'),'workspace-setup',seed]);
  const declaration = {director_id:'linked-workspace-director',areas};
  const approved = linkedCall('setup-preview', declaration);
  linkedCall('setup-apply',{...declaration,expected_preview_sha256:approved.preview_sha256});
  const linkedRoute = linkedCall('project-route',{operation:'intake'});
  assert.equal(linkedRoute.project.workspace_checkout, linked);
  assert.equal(linkedRoute.project.checkout, root);
  assert.equal(linkedRoute.project.queue_id, invoke('project-menu').projects.find(project => project.id === 'site').queue_id);
  const futureBefore = data(root,'.skill-tree/documents/future.json');
  fs.writeFileSync(input, JSON.stringify({title:'Linked input',description:'Preview scoped intake.',expected_behavior:'Retain the product queue.'}));
  const installedCore = path.join(root,'.agents/skills/skill-tree-add-pending-task/scripts/workflow-state.py');
  const linkedGuard = spawnSync('python3',['-B',installedCore,'intake',linked,'--standalone','--input',input], {cwd:linked,env,encoding:'utf8'});
  assert.notEqual(linkedGuard.status,0);
  assert.match(linkedGuard.stdout+linkedGuard.stderr,/Director owns the default route/);
  assert.deepEqual(data(root,'.skill-tree/documents/future.json'), futureBefore);
});
