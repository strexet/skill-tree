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
  init(root,'main');
  fs.writeFileSync(path.join(root,'index.html'),'<!DOCTYPE html>');
  const overlapping = path.join(root,'nested-with-canonical-file');
  fs.mkdirSync(overlapping);
  fs.writeFileSync(path.join(overlapping,'canonical.txt'),'canonical fixture');
  commit(root);
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
  const ownerSettings = path.join(root,'.claude/settings.json');
  fs.mkdirSync(path.dirname(ownerSettings),{recursive:true});
  const ownerBytes = Buffer.from('{"hooks":{"PreToolUse":[{"matcher":"Write","hooks":[{"type":"command","command":"true"}]}]}}\n');
  fs.writeFileSync(ownerSettings,ownerBytes);
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
  let guardPreTool;
  for (const [choice,target,flavor] of [
    [{kind:'existing',name:'site',path:root},root,'web'],
    [{kind:'new',name:'example'},path.join(root,'example'),'general'],
    [{kind:'new',name:'external',path:custom,flavor:'web'},custom,'web']]) {
    assert.equal(invoke('project-preview',choice).checkout,target);
    const result=invoke('project-setup',choice);
    assert.equal(result.status,'registered');assert.equal(result.checkout,target);assert.equal(result.flavor,flavor);
    assert.match(result.operation_id,/^OP-[a-f0-9-]+$/);
    const registration = path.join(home, '.skill-tree/artifacts/director/projects', choice.name + '.json');
    const installedReceipt = path.join(home, '.skill-tree/artifacts/setup-operations', result.operation_id + '.json');
    const registrationInode = fs.statSync(registration).ino;
    const setupReceiptBytes = fs.readFileSync(installedReceipt);
    const replay = invoke('project-setup', {...choice,operation_id:result.operation_id});
    assert.equal(replay.queue_id,result.queue_id);
    assert.equal(replay.replayed,true);
    assert.equal(fs.statSync(registration).ino,registrationInode);
    assert.deepEqual(fs.readFileSync(installedReceipt),setupReceiptBytes);
    if (choice.name === 'site') {
      const replayRegistryPath = path.join(home,'.skill-tree/director/registry.json');
      const registryBefore = fs.readFileSync(replayRegistryPath);
      const changed = JSON.parse(registryBefore);
      delete changed.areas.site;
      const changedRegistry = JSON.stringify(changed);
      fs.writeFileSync(replayRegistryPath,changedRegistry);
      try {
        assert.throws(() => invoke('project-setup',{...choice,operation_id:result.operation_id}),
                      /Registered Director area or local binding changed/);
        assert.equal(fs.readFileSync(replayRegistryPath,'utf8'),changedRegistry);
        assert.deepEqual(fs.readFileSync(installedReceipt),setupReceiptBytes);
      } finally {
        fs.writeFileSync(replayRegistryPath,registryBefore);
      }
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
        const recommendation = invoke('project-route', {project_id:'site', request_text:'Implement the settings page'});
        assert.equal(recommendation.candidate_operation, 'skill-tree-full-cycle');
        assert.deepEqual(recommendation.limitations, ['project-skill-unavailable']);
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
      const ready = 'T-12a45678-cdef-4aef-acda-0123456789ab';
      const blocked = 'T-22a45678-cdef-4aef-acda-0123456789ab';
      const missingTask = 'T-32a45678-cdef-4aef-acda-0123456789ab';
      const checks = {checks:[{id:'fixture',recipe_id:'quality-node',parameters:{},sources:['index.html'],
        criteria:['The site renders.'], assertion:'Open the site.', timing:'immediate'}]};
      function task(id, state) {
        return [
          '### Fixture task ' + id, '', '```yaml', 'id: ' + id, 'priority: 100', 'status: ' + state,
          'parent_pending_ids: ' + JSON.stringify([added.id]), 'processing_run_id: null', 'root_task_id: ' + id,
          'related_task_id: null', 'relation: main', 'depends_on: []', '```', '', 'Goal:', 'Render the site.', '',
          'Touch:', '- index.html', '', 'Validation:', '```json', JSON.stringify(checks), '```', '',
          'Acceptance:', '- The site renders.', '',
          ...(state === 'Ready' ? [] : ['[Unresolved - blocks implementation]', '']), '',
        ].join('\n');
      }
      const futurePath = path.join(root,future);
      const retained = fs.readFileSync(futurePath,'utf8');
      fs.writeFileSync(futurePath,retained.replace('## Backlog',task(ready,'Ready') +
        task(blocked,'Blocked pending answers') + '## Backlog'));
      try {
        const ownedState = [futurePath, path.join(root,'.skill-tree/documents/future.json'), queueLocator,
          skillReceipt, registryPath, path.join(home,'.skill-tree/documents/future.json'),
          path.join(home,'.skill-tree/artifacts/director/local-bindings.json'),
          path.join(root,'.skill-tree/history/task-outcomes.jsonl')];
        const bytes = file => fs.existsSync(file) ? fs.readFileSync(file) : null;
        const before = ownedState.map(bytes);
        function recommendation(request_text, project_id = 'site') {
          const preview = invoke('project-route',{project_id,request_text});
          for (const unavailable of ['command','entry','input','grant','authority','argv']) {
            assert.equal(preview[unavailable],undefined,unavailable);
          }
          return preview;
        }
        const fresh = recommendation('Implement a new settings page');
        assert.equal(fresh.status,'preview');
        assert.equal(fresh.candidate_operation,'skill-tree-full-cycle');
        assert.deepEqual(fresh.matched_intents,['fresh-implementation']);
        assert.equal(fresh.confidence,'bounded-explicit-wording');
        const existing = recommendation('Implement ready task ' + ready);
        assert.equal(existing.status,'preview');
        assert.equal(existing.candidate_operation,'skill-tree-work-through-next');
        assert.deepEqual(existing.task_ids,[ready]);
        assert.deepEqual(existing.limitations,[]);
        const intakeOnly = recommendation('Add to Pending to check the settings page, no implementation');
        assert.equal(intakeOnly.candidate_operation,'skill-tree-add-pending-task');
        assert.equal(intakeOnly.status,'preview');
        const pr = recommendation('Проверь PR #12');
        assert.equal(pr.candidate_operation,'skill-tree-pr-review-cycle');
        assert.equal(pr.status,'preview');
        assert.equal(invoke('project-route',{operation:'review',project_id:'site'}).command,'review-preview');
        const mixed = recommendation('Implement the settings page and add a Pending follow-up');
        assert.equal(mixed.candidate_operation,null);
        assert.deepEqual(mixed.limitations,['mixed-request-intent']);
        assert.deepEqual(mixed.unresolved_choices.map(choice=>choice.operation),
                         ['skill-tree-full-cycle','skill-tree-add-pending-task']);
        const tentative = recommendation('Maybe implement the settings page?');
        assert.equal(tentative.confidence,'unresolved');
        assert.deepEqual(tentative.limitations,['uncertain-request-intent']);
        assert.deepEqual(recommendation('Explain the queue').limitations,['unsupported-request-intent']);
        assert.deepEqual(recommendation('Explain how to build the project.').limitations,['unsupported-request-intent']);
        assert.deepEqual(recommendation('The previous agent tried to implement the page.').limitations,['unsupported-request-intent']);
        assert.deepEqual(recommendation('Add to Pending and process it.').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Add to Pending and implement all tasks.').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Add to Pending and start implementation.').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Implement the settings page, merge it.').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Implement the page and fix the login screen.').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Implement task ABC.').limitations,['select-one-exact-task']);
        assert.deepEqual(recommendation('Implement T-zzzz.').limitations,['exact-task-id-required']);
        assert.equal(recommendation('Please implement a release notes page.').candidate_operation,'skill-tree-full-cycle');
        assert.equal(recommendation('Could you review the PR?').candidate_operation,'skill-tree-pr-review-cycle');
        assert.deepEqual(recommendation('Implement all ready tasks.').limitations,['unsupported-request-intent']);
        assert.deepEqual(recommendation('Review PR #12 and merge it').limitations,['mixed-request-intent']);
        assert.deepEqual(recommendation('Implement ' + added.id).limitations,['prioritized-task-required']);
        assert.deepEqual(recommendation('Implement ' + blocked).limitations,['task-clarification-required']);
        assert.deepEqual(recommendation('Implement ' + missingTask).limitations,['task-outside-project-queue']);
        assert.deepEqual(recommendation('Implement ' + ready + ' and ' + blocked).limitations,['select-one-exact-task']);
        assert.deepEqual(recommendation('Implement the Ready task').limitations,['select-one-exact-task']);
        assert.deepEqual(recommendation('Implement T-0123').limitations,['exact-task-id-required']);
        assert.deepEqual(invoke('project-route',{request_text:'Implement the page'}).unresolved_choices,[{project_id:'site'}]);
        assert.deepEqual(recommendation('Implement the page','different').limitations,['exact-registered-project-required']);
        assert.throws(() => invoke('project-route',{operation:'intake',request_text:'Add to Pending'}),/Unexpected Director input/);
        assert.deepEqual(ownedState.map(bytes),before);
        assert.equal(git(root,'rev-parse','HEAD'),head);
      } finally {
        fs.writeFileSync(futurePath,retained);
      }
      const restricted=JSON.parse(current);
      restricted.areas.site.allowed_effects=['status'];
      fs.writeFileSync(registryPath, JSON.stringify(restricted));
      const unavailable=invoke('project-route',{operation:'process'});
      assert.equal(unavailable.status,'prerequisite');
      assert.deepEqual(unavailable.task_ids,[]);
      assert.equal(unavailable.queue_sha256,undefined);
      const denied = invoke('project-route',{project_id:'site',request_text:'Implement the page'});
      assert.deepEqual(denied.limitations,['project-preview-not-authorized']);
      assert.equal(denied.candidate_operation,null);
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
      const versionBin = path.join(base,'controlled-version-bin');
      fs.mkdirSync(versionBin);
      const version = path.join(versionBin,'claude');
      fs.writeFileSync(version,"#!/bin/sh\nprintf '%s\\n' '2.1.109 (Claude Code)'\n",{mode:0o755});
      const installHosts = {...env,PATH:versionBin+path.delimiter+env.PATH};
      const guardArgs = ['-B',path.relative(root,app),'claude-guard-settings',path.relative(root,home),'--project-id','site'];
      const qualified = spawnSync('python3',guardArgs,{cwd:root,env:installHosts,encoding:'utf8'});
      assert.equal(qualified.status,0,'Installed Setup must return a qualified Claude Code guard overlay: '+qualified.stdout+qualified.stderr);
      const overlay = JSON.parse(qualified.stdout);
      assert.ok(path.isAbsolute(overlay.entry));
      const hook = overlay.settings.hooks.PreToolUse[0];
      assert.equal(hook.matcher,'Write|Edit|Bash');
      const preTool = (tool,tool_input,cwd=root,hookEnvironment=env) => {
        const result = spawnSync('/bin/sh',['-c',hook.hooks[0].command],{cwd,env:hookEnvironment,encoding:'utf8',timeout:20000,
          input:JSON.stringify({hook_event_name:'PreToolUse',tool_name:tool,cwd,tool_input})});
        assert.equal(result.status,0,result.stdout+result.stderr);
        return JSON.parse(result.stdout);
      };
      guardPreTool = preTool;
      const verifyDeny = output => assert.equal(output.hookSpecificOutput.permissionDecision,'deny');
      const canonicalSource = path.join(root,'index.html');
      const slowGit = path.join(versionBin,'git');
      fs.writeFileSync(slowGit,'#!/bin/sh\nexec /bin/sleep 60\n',{mode:0o755});
      try {
        const stalled = preTool('Write',{file_path:canonicalSource},root,installHosts);
        verifyDeny(stalled);
        assert.match(stalled.hookSpecificOutput.permissionDecisionReason,/timed out before effects/);
      } finally {
        fs.unlinkSync(slowGit);
      }
      const directorReceipt = path.join(home,'.skill-tree/installation/profile.json');
      const receiptBytes = fs.readFileSync(directorReceipt);
      try {
        fs.unlinkSync(directorReceipt);
        verifyDeny(preTool('Edit',{file_path:canonicalSource}));
      } finally {
        fs.writeFileSync(directorReceipt,receiptBytes);
      }
      verifyDeny(preTool('Write',{file_path:canonicalSource}));
      const differentlySpelledRoot = path.join(path.dirname(root),path.basename(root).toUpperCase());
      const differentSpelling = fs.statSync(differentlySpelledRoot,{throwIfNoEntry:false});
      if (differentSpelling?.ino === fs.statSync(root).ino && differentSpelling.dev === fs.statSync(root).dev) {
        verifyDeny(preTool('Write',{file_path:path.join(differentlySpelledRoot,'protected-case-alias.txt')},base));
        verifyDeny(preTool('Bash',{command:'git -C '+JSON.stringify(differentlySpelledRoot)+' branch guarded-case-alias'},base));
      }
      verifyDeny(preTool('Edit',{file_path:canonicalSource}));
      verifyDeny(preTool('Write',{}));
      verifyDeny(preTool('Bash',{command:'git branch unadmitted'}));
      verifyDeny(preTool('Bash',{command:'git -C '+JSON.stringify(root)+' switch -c unadmitted'},base));
      verifyDeny(preTool('Bash',{command:'git --git-dir=.git update-ref refs/heads/unadmitted HEAD'}));
      verifyDeny(preTool('Bash',{command:'git diff --output=index.html'}));
      assert.deepEqual(preTool('Bash',{command:'git branch --show-current'}),{});
      assert.deepEqual(preTool('Bash',{command:'git status --short'}),{});
      assert.deepEqual(preTool('Write',{file_path:path.join(base,'unregistered.txt')}),{});
      verifyDeny(preTool('Bash',{command:'git -C '+JSON.stringify(seed)+' diff --output='+JSON.stringify(canonicalSource)},base));
      const nested = path.join(root,'independent-checkout');
      init(nested,'main');
      verifyDeny(preTool('Write',{file_path:path.join(nested,'unregistered.txt')}));
      fs.rmSync(nested,{recursive:true});
      git(overlapping,'init','-q','-b','main');
      verifyDeny(preTool('Edit',{file_path:path.join(overlapping,'canonical.txt')}));
      fs.rmSync(path.join(overlapping,'.git'),{recursive:true});
      const outsideLinked = path.join(base,'retained-external-worktree');
      fs.mkdirSync(outsideLinked);
      const retainedLocator = JSON.parse(savedLocator);
      retainedLocator.worktrees['WR-12345678-1234-1234-1234-1234567890ab'] = outsideLinked;
      fs.writeFileSync(queueLocator,JSON.stringify(retainedLocator));
      try {
        verifyDeny(preTool('Write',{file_path:path.join(outsideLinked,'guarded.txt')},base));
        fs.symlinkSync(path.join(base,'unregistered.txt'),path.join(outsideLinked,'outside-alias'));
        verifyDeny(preTool('Edit',{file_path:path.join(outsideLinked,'outside-alias')},base));
      } finally {
        fs.writeFileSync(queueLocator,savedLocator);
      }
      const alias = path.join(base,'canonical-alias');
      fs.symlinkSync(canonicalSource,alias);
      verifyDeny(preTool('Edit',{file_path:alias}));
      try {
        fs.unlinkSync(queueLocator);
        verifyDeny(preTool('Write',{file_path:canonicalSource}));
        assert.deepEqual(preTool('Bash',{command:'git branch --show-current'}),{});
      } finally {
        fs.writeFileSync(queueLocator,savedLocator);
      }
      fs.writeFileSync(version,"#!/bin/sh\nprintf '%s\\n' '9.9.9 (Claude Code)'\n",{mode:0o755});
      const unqualified = spawnSync('python3',guardArgs,{cwd:root,env:installHosts,encoding:'utf8'});
      assert.notEqual(unqualified.status,0);
      assert.match(unqualified.stdout+unqualified.stderr,/qualified Claude Code 2\.1\.109/i);
      assert.equal(fs.readFileSync(canonicalSource,'utf8'),'<!DOCTYPE html>');
      assert.equal(git(root,'branch','--list','unadmitted'),'');
      assert.equal(git(root,'rev-parse','HEAD'),head);
      assert.deepEqual(fs.readFileSync(ownerSettings),ownerBytes);
      assert.deepEqual(data(root,'.skill-tree/installation/profile.json').bridges,{});
    }
    if (choice.name === 'example') {
      assert.deepEqual(guardPreTool('Write',{file_path:path.join(target,'unrelated-to-site.txt')}),{});
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
  const registerLinked = {...declaration,expected_preview_sha256:approved.preview_sha256};
  const localBinding = '.skill-tree/artifacts/director/local-bindings.json';
  const linkedIgnore = path.join(linkedHome, '.gitignore');
  const linkedExclude = path.join(linkedHome, '.git/info/exclude');
  const savedRules = fs.readFileSync(linkedExclude);
  fs.writeFileSync(linkedIgnore, '!/'+localBinding+'\n', {flag:'wx'});
  try {
    fs.writeFileSync(input, JSON.stringify(registerLinked));
    const rejected = spawnSync('python3',['-B',linkedEntry,'setup-apply',linkedHome,'--input',input],
      {cwd:linked,env,encoding:'utf8',timeout:120000});
    assert.equal(rejected.status,2,rejected.stdout+rejected.stderr);
    assert.match(rejected.stdout+rejected.stderr,/needs a local Git exclusion/);
    assert.equal(fs.existsSync(path.join(linkedHome,localBinding)),false);
    assert.equal(fs.existsSync(path.join(linkedHome,'.skill-tree/director/registry.json')),false);
    assert.deepEqual(fs.readFileSync(linkedExclude),savedRules);
    const descriptorPath = path.join(linkedHome, 'workspace.json');
    const savedDescriptor = fs.readFileSync(descriptorPath);
    fs.unlinkSync(descriptorPath);
    try {
      const missing = spawnSync('python3',['-B',linkedEntry,'setup-apply',linkedHome,'--input',input],
        {cwd:linked,env,encoding:'utf8',timeout:120000});
      assert.equal(missing.status,2,missing.stdout+missing.stderr);
      assert.match(missing.stdout+missing.stderr,/Director workspace installation is unavailable/);
      assert.equal(fs.existsSync(path.join(linkedHome,localBinding)),false);
      assert.equal(fs.existsSync(path.join(linkedHome,'.skill-tree/director/registry.json')),false);
    } finally {
      fs.writeFileSync(descriptorPath,savedDescriptor);
    }
  } finally {
    fs.unlinkSync(linkedIgnore);
  }
  linkedCall('setup-apply',registerLinked);
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

test('dedicated coordinator protects machine-local paths and preserves portable Git inputs', t => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-coordinator-ignore-')));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const workspace = path.join(base, 'workspace');
  fs.mkdirSync(workspace);
  const env = {...Object.fromEntries(Object.entries(process.env).filter(([key]) => !key.startsWith('GIT_'))),
    GIT_TERMINAL_PROMPT:'0', GIT_CONFIG_NOSYSTEM:'1', GIT_CONFIG_GLOBAL:os.devNull};
  function run(command, args, cwd=base, expected=0) {
    const result = spawnSync(command, args, {cwd, env, encoding:'utf8', timeout:120000});
    assert.equal(result.status, expected, result.stdout + result.stderr);
    return result.stdout;
  }
  const git = (cwd, ...args) => run('git', args, cwd);
  git(workspace, 'init', '-q', '-b', 'develop');
  run(process.execPath, [path.join(__dirname, '../bin/install.js'), '--only', 'codex', '--target', workspace]);
  const root = path.join(workspace, '.skill-tree/.director');
  const setup = path.join(root, JSON.parse(fs.readFileSync(path.join(root, 'workspace.json'))).setup_entry);
  const contents = [
    'sources/skill-tree/fixture-source.txt',
    'sources/projects/fixture-project/fixture-source.txt',
    '.skill-tree/artifacts/director/local-bindings.json',
  ];
  function write(relative, value) {
    const absolute = path.join(root, relative);
    fs.mkdirSync(path.dirname(absolute), {recursive:true});
    fs.writeFileSync(absolute, value);
    return absolute;
  }
  for (const relative of contents) write(relative, 'Local fixture\n');
  const portable = '.skill-tree/director/registry.json';
  const sibling = 'sources/portable-note.txt';
  write(portable, '{}\n');
  write(sibling, 'Portable source note\n');
  const staging = git(root, 'add', '--all', '--dry-run');
  for (const relative of contents) {
    assert.equal(staging.includes(relative), false, 'Coordinator Git staging exposes a machine-local path: ' + relative);
  }
  assert.ok(staging.includes(portable));
  assert.ok(staging.includes(sibling));

  const exclude = path.join(root, '.git/info/exclude');
  fs.chmodSync(exclude, 0o640);
  const excludeMode = fs.statSync(exclude).mode;
  fs.appendFileSync(exclude, '# Fixture rule\n*.fixture-local\n');
  const original = fs.readFileSync(exclude);
  const command = ['-B', setup, 'project-init', root];
  run('python3', command);
  assert.deepEqual(fs.readFileSync(exclude), original);

  git(root, 'add', '-f', '--', contents[0]);
  const index = git(root, 'ls-files', '--stage', '--', contents[0]);
  const blocked = spawnSync('python3', command, {cwd:base, env, encoding:'utf8', timeout:120000});
  assert.equal(blocked.status, 2, blocked.stdout + blocked.stderr);
  assert.match(blocked.stdout + blocked.stderr, /tracked.*(Git|coordinator)/i);
  assert.deepEqual(fs.readFileSync(exclude), original);
  assert.equal(git(root, 'ls-files', '--stage', '--', contents[0]), index);

  git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
    'commit', '-qm', 'Record fixture tracked local conflict');
  git(root, 'rm', '--cached', '--', contents[0]);
  const stagedRemoval = git(root, 'diff', '--cached', '--name-status');
  const retained = spawnSync('python3', command, {cwd:base, env, encoding:'utf8', timeout:120000});
  assert.equal(retained.status, 2, retained.stdout + retained.stderr);
  assert.match(retained.stdout + retained.stderr, /tracked.*(Git|coordinator)/i);
  assert.equal(git(root, 'diff', '--cached', '--name-status'), stagedRemoval);
  assert.deepEqual(fs.readFileSync(exclude), original);
  git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
    'commit', '-qm', 'Remove fixture tracked local conflict');
  const broadRules = fs.readFileSync(exclude, 'utf8').split('\n')
    .filter(line => line !== '/sources/skill-tree/').join('\n');
  fs.writeFileSync(exclude, broadRules);
  write('.gitignore', '!/sources/skill-tree/\n');
  const refused = spawnSync('python3', command, {cwd:base, env, encoding:'utf8', timeout:120000});
  assert.equal(refused.status, 2, refused.stdout + refused.stderr);
  assert.match(refused.stdout + refused.stderr, /ignore rules.*expose/i);
  assert.equal(fs.readFileSync(exclude, 'utf8'), broadRules);
  assert.equal(fs.statSync(exclude).mode, excludeMode);
});
