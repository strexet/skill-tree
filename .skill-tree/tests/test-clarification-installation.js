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
for (const flavor of ['general', 'web', 'unity']) test(`${flavor} clarification package runs independently of source and sibling packages`, t => {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-clarify-'));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const root = path.join(base, 'project');
  fs.mkdirSync(root);
  write(root, 'package.json', {scripts:{test:'node --test'}});
  if (flavor === 'unity') {
    write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2');
    write(root, 'Packages/manifest.json', {dependencies:{'com.unity.test-framework':'1.6.0'}});
    write(root, 'Packages/packages-lock.json', {dependencies:{'com.unity.test-framework':{version:'1.6.0'}}});
  }
  const name = 'skill-tree-clarify-tasks';
  run(process.execPath, [path.join(core, 'bin/install.js'), '--target', root, '--only', 'codex', '--flavor', flavor, '--skills', name]);
  const isolated = path.join(base, 'standalone');
  fs.cpSync(path.join(root, '.agents/skills', name), isolated, {recursive:true});
  fs.rmSync(path.join(root, '.agents'), {recursive:true});
  const helper = path.join(isolated, 'scripts/workflow-state.py');
  const task = 'T-11111111-1111-4111-8111-111111111111';
  const check = {id:'behavior',recipe_id:'static-inspection',criteria:['Preserve bounded behavior.'],sources:['source.py'],parameters:{},assertion:'Preserve bounded behavior.',timing:'immediate'};
  write(root, 'source.py', 'VALUE = 1\n');
  write(root, '.skill-tree/documents/future.md', '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n### Selected task\n\n```yaml\nid: '+task+'\npriority: 100\nstatus: Ready\nparent_pending_ids: ["P-11111111-1111-4111-8111-111111111111"]\nprocessing_run_id: null\nroot_task_id: '+task+'\nrelated_task_id: null\nrelation: main\ndepends_on: []\n```\n\nGoal:\n- Preserve bounded behavior.\n\nScope:\n- The selected source.\n\nOut of scope:\n- Remote services.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+JSON.stringify({checks:[check]})+'\n```\n\nAcceptance:\n- Preserve bounded behavior.\n\n## Backlog\n');
  const crypto = require('node:crypto');
  const sourceHash = () => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, '.skill-tree/documents/future.md'))).digest('hex');
  function invoke(command, payload) {
    const input = path.join(base, 'request.json');
    write(base, 'request.json', payload);
    return JSON.parse(run('python3', [helper, command, root, '--input', input]));
  }
  const original = fs.readFileSync(path.join(root, '.skill-tree/documents/future.md'));
  let session = invoke('clarify-start', {task_ids:[task],expected_source_hash:sourceHash()});
  assert.deepEqual(session.task_ids, [task]);
  const guard = () => ({session_id:session.id,expected_source_hash:sourceHash(),expected_session_hash:session.session_hash,expected_session_revision:session.revision});
  session = invoke('clarify-round', {...guard(),clarity:{goals:true,scope:true,exclusions:true,dependencies:true,acceptance:true,validation:true,decisions:true,evidence:['Source and current task define explicit observable behavior.']}});
  assert.equal(session.state, 'awaiting-confirmation');
  session = invoke('clarify-confirm', {...guard(),task_ids:[task],semantic_fingerprints:session.semantic_fingerprints,evidence:{kind:'submitted-answer',reference:'Owner confirmed the current displayed task summary.'}});
  assert.equal(session.state, 'complete');
  assert.deepEqual(fs.readFileSync(path.join(root, '.skill-tree/documents/future.md')), original);
  assert.ok(!fs.existsSync(path.join(root, '.skill-tree/documents/future.json')));
  assert.ok(fs.existsSync(path.join(isolated, 'scripts/run-workspaces.py')));
  assert.match(fs.readFileSync(path.join(isolated, 'references/project-profile.md'), 'utf8'), new RegExp('Flavor: '+flavor));
});
