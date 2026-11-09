'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const {spawnSync} = require('node:child_process');
const composer = require('../lib/composer.js');
const installation = require('../lib/installation.js');
const core = path.resolve(__dirname, '..');
const operations = Object.keys(require('../templates/operations.json')).sort();

function write(root, relative, value) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive:true});
  fs.writeFileSync(file, Buffer.isBuffer(value) || typeof value === 'string' ? value : JSON.stringify(value));
}
function snapshot(root) {
  const result = {};
  function walk(relative) {
    for (const entry of fs.readdirSync(path.join(root, relative), {withFileTypes:true})) {
      const child = path.posix.join(relative, entry.name);
      assert.ok(!entry.isSymbolicLink(), 'Standalone fixture must contain actual package files.');
      if (entry.isDirectory()) walk(child);
      else result[child] = fs.readFileSync(path.join(root, child));
    }
  }
  walk('');
  return result;
}
function python(args, cwd) {
  const result = spawnSync('python3', ['-I', ...args], {cwd, encoding:'utf8', timeout:30000});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout;
}
function noTaskOrPluginState(root) {
  for (const relative of ['.skill-tree/documents/future.md', '.skill-tree/documents/future.json', '.skill-tree/installation']) {
    assert.ok(!fs.existsSync(path.join(root, relative)), 'Task-free core operation created forbidden state: ' + relative);
  }
}

for (const flavor of ['general', 'web', 'unity']) test(`${flavor} core decision operations run with no source, siblings, Future or plugins`, t => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-decision-core-'));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const source = path.join(base, 'temporary-source'), project = path.join(base, 'installed-project');
  fs.mkdirSync(source);
  fs.mkdirSync(project);
  for (const relative of Object.keys(composer.sourceInputs(core))) write(source, relative, fs.readFileSync(path.join(core, relative)));
  write(project, 'package.json', {scripts:{test:'node --test'}});
  if (flavor === 'unity') {
    write(project, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2');
    write(project, 'Packages/manifest.json', {dependencies:{'com.unity.test-framework':'1.6.0'}});
    write(project, 'Packages/packages-lock.json', {dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});
  }
  installation.install(project, source, flavor, operations.map(name => ({name, provider:'codex', rel:'.agents/skills/' + name})));
  const packages = Object.fromEntries(operations.map(name => [name, snapshot(path.join(project, '.agents/skills', name))]));
  fs.rmSync(source, {recursive:true});
  fs.rmSync(project, {recursive:true});
  assert.ok(!fs.existsSync(source) && !fs.existsSync(project), 'Temporary source and original installation must be removed before invocation.');

  for (const name of operations) {
    const standalone = path.join(base, 'only-package'), runtime = path.join(base, 'task-free-project');
    fs.mkdirSync(standalone);
    fs.mkdirSync(runtime);
    for (const [relative, bytes] of Object.entries(packages[name])) write(standalone, relative, bytes);
    const scripts = path.join(standalone, 'scripts');
    for (const helper of ['decision-orchestration.py', 'decision-governance.py', 'workflow-state.py', 'run-workspaces.py', 'validate-document-rules.py']) {
      assert.ok(fs.existsSync(path.join(scripts, helper)), `${name} must bundle ${helper} for standalone core decisions.`);
    }
    assert.match(fs.readFileSync(path.join(standalone, 'references/project-profile.md'), 'utf8'), new RegExp('Flavor: ' + flavor));
    python(['-c', 'import importlib.util,pathlib,sys\nroot=pathlib.Path(sys.argv[1])\nfor name in ("decision-orchestration", "decision-governance", "workflow-state", "run-workspaces", "validate-document-rules"):\n spec=importlib.util.spec_from_file_location("standalone_"+name.replace("-","_"),root/(name+".py"))\n module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)\n', scripts], runtime);
    const helper = path.join(scripts, 'workflow-state.py');
    function invoke(command, payload) {
      const input = path.join(base, 'input.json');
      fs.writeFileSync(input, JSON.stringify(payload));
      return JSON.parse(python([helper, command, runtime, '--input', input], runtime));
    }
    const context = {kind:'request', id:'fixture-request', semantic_fingerprint:'a'.repeat(64), content_fingerprint:'b'.repeat(64)};
    const frame = invoke('orchestration-start', {
      request_id:'standalone-fixture', context,
      authority:{id:'fixture-grant', revision:1, context_id:context.id, allowed_kinds:['product', 'technical', 'specification-acceptance'], constraints:['Fixture metadata only; no live side effects.'], evidence:{kind:'owner-message', reference:'Synthetic isolated fixture grant, never actual human.'}},
      executor:{id:'fixture-executor', context_id:'fixture-executor-context'}, capabilities:{independent_actors:false}
    });
    assert.match(frame.id, /^DO-[a-f0-9-]{36}$/);
    assert.equal(frame.mode, 'auto');
    assert.equal(frame.phase, 'research');
    assert.deepEqual(frame.context, context);
    const next = invoke('orchestration-next', {orchestration_id:frame.id});
    assert.equal(next.action, 'phase');
    assert.equal(next.phase, 'research');
    assert.equal(next.frame.id, frame.id);
    noTaskOrPluginState(runtime);
    invoke('orchestration-question', {
      orchestration_id:frame.id, expected_orchestration_hash:frame.orchestration_hash, expected_orchestration_revision:frame.revision,
      purpose:'decision', question:{id:'choice', kind:'technical', text:'Fixture choice?', options:[{id:'keep', text:'Keep fixture.'}], recommendation:'keep', significance:'routine'}
    });
    const blocked = invoke('orchestration-next', {orchestration_id:frame.id});
    assert.equal(blocked.action, 'prerequisite');
    assert.match(JSON.stringify(blocked), /independent.{0,40}actor|actor.{0,40}capability/i);
    assert.equal(blocked.frame.mode, 'auto', 'Absent native actor capability must not silently select Manual.');
    assert.equal(blocked.frame.acceptance, null);
    noTaskOrPluginState(runtime);
    fs.rmSync(standalone, {recursive:true});
    fs.rmSync(runtime, {recursive:true});
  }
});
