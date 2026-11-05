const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const core = path.resolve(__dirname, '..');

function run(command, args) {
  const result = spawnSync(command, args, {encoding:'utf8', timeout:30000, cwd:os.tmpdir()});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout;
}
function write(root, relative, value) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive:true});
  fs.writeFileSync(file, typeof value === 'string' ? value : JSON.stringify(value));
}

for (const flavor of ['general', 'web', 'unity']) test(`${flavor} standalone intake captures conditional requirements without dispatch`, t => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'pending-boundary-'));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const root = path.join(base, 'queue');
  fs.mkdirSync(root);
  run('git', ['init', '-b', 'main', root]);
  write(root, 'package.json', {scripts:{test:'node --test'}});
  if (flavor === 'unity') {
    write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2');
    write(root, 'Packages/manifest.json', {dependencies:{'com.unity.test-framework':'1.6.0'}});
    write(root, 'Packages/packages-lock.json', {dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});
  }
  write(root, '.skill-tree/documents/future.md', '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  write(root, 'existing-version.txt', 'Retained product version.');
  run(process.execPath, [path.join(core, 'bin/install.js'), '--target', root, '--only', 'codex', '--flavor', flavor, '--skills', 'skill-tree-add-pending-task']);
  const isolated = path.join(base, 'standalone');
  fs.cpSync(path.join(root, '.agents/skills/skill-tree-add-pending-task'), isolated, {recursive:true});
  const helper = path.join(isolated, 'scripts/workflow-state.py');
  run('python3', [helper, 'workspace-setup', root]);
  const stateFile = path.join(root, '.skill-tree/documents/future.json');
  const before = JSON.parse(fs.readFileSync(stateFile));
  const request = {
    title:'Conditional Figma task', description:'Find the corresponding Figma node.',
    expected_behavior:'Stop and report when the node is absent. When the node is found, implement the design and correct the existing version.'
  };
  const input = path.join(base, 'request.json');
  write(base, 'request.json', request);
  const pending = JSON.parse(run('python3', [helper, 'intake', root, '--input', input]));
  const after = JSON.parse(fs.readFileSync(stateFile));
  assert.equal(pending.status, 'Pending');
  assert.equal(after.schema, 3);
  assert.equal(after.active_run, null);
  assert.deepEqual(after.task_progress, {});
  assert.deepEqual(after.run_registry, before.run_registry);
  assert.deepEqual(after.tasks.map(task => task.id), [pending.id]);
  assert.equal(fs.readFileSync(path.join(root, 'existing-version.txt'), 'utf8'), 'Retained product version.');
  assert.ok(fs.readFileSync(path.join(root, '.skill-tree/documents/future.md'), 'utf8').includes(request.expected_behavior));
  assert.equal(fs.existsSync(path.join(root, '.skill-tree/history/task-outcomes.jsonl')), false);
});
