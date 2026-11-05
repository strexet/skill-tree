const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
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
for (const flavor of ['general', 'web', 'unity']) test(`${flavor} standalone defect priority honors semantic decisions and owner overrides`, t => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'pending-priority-'));
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
  run(process.execPath, [path.join(core, 'bin/install.js'), '--target', root, '--only', 'codex', '--flavor', flavor, '--skills', 'skill-tree-add-pending-task']);
  const isolated = path.join(base, 'standalone');
  fs.cpSync(path.join(root, '.agents/skills/skill-tree-add-pending-task'), isolated, {recursive:true});
  const helper = path.join(isolated, 'scripts/workflow-state.py');
  let count = 0;
  function intake(title, extra = {}) {
    const input = path.join(base, `request-${count++}.json`);
    fs.writeFileSync(input, JSON.stringify({title, description:'Preserve observable behavior.', expected_behavior:'Retain the complete queue.', ...extra}));
    return JSON.parse(run('python3', [helper, 'intake', root, '--input', input]));
  }
  const anchor = intake('Existing owner priority', {priority:700});
  const stateFile = path.join(root, '.skill-tree/documents/future.json');
  assert.equal(JSON.parse(fs.readFileSync(stateFile)).schema, 2);
  run('python3', [helper, 'workspace-setup', root]);
  write(root, '.skill-tree/history/retained-note.json', {assertion:'Preserved owner history.'});
  const history = fs.readFileSync(path.join(root, '.skill-tree/history/retained-note.json'));
  const before = JSON.parse(fs.readFileSync(stateFile));
  const defect = {classification:{kind:'defect', reason:'Existing behavior fails, including the reported issuee typo.'}};
  assert.equal(intake('Reported issuee', defect).priority, 701);
  assert.equal(intake('Explicit zero', {...defect, priority:0}).priority, 0);
  assert.equal(intake('Explicit low', {...defect, low_priority:true}).priority, 25);
  assert.equal(intake('Relative placement', {...defect, relative_priority:{direction:'below', task_id:anchor.id}}).priority, 699);
  assert.equal(intake('New bug classifier feature', {classification:{kind:'other', reason:'The owner requests new classification functionality.'}}).priority, 100);
  const after = JSON.parse(fs.readFileSync(stateFile));
  assert.deepEqual(after.run_registry, before.run_registry);
  assert.equal(after.active_run, null);
  assert.deepEqual(after.task_progress, {});
  assert.ok(after.tasks.some(task => task.id === anchor.id && task.priority === 700));
  assert.ok(after.tasks.every(task => task.status === 'Pending'));
  assert.deepEqual(fs.readFileSync(path.join(root, '.skill-tree/history/retained-note.json')), history);
});
