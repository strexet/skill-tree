'use strict';

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const installation = require('../lib/installation.js');
const lifecycle = require('../lib/plugin-lifecycle.js');
const plugins = require('../lib/plugin-registry.js');
const flavors = require('../config/flavors.json');

const SOURCE = path.resolve(__dirname, '..');
const CLI = path.join(SOURCE, 'bin/install.js');
const AGENTS = '.agents/skills';
const PROFILE = '.skill-tree/installation/profile.json';
const MANAGER = '.skill-tree/installation/manager.js';
const QUEUE = '.skill-tree/documents/future.md';
const STATE = '.skill-tree/documents/future.json';
const HISTORY = '.skill-tree/history/research/local-review.md';
const CORE = [...flavors.core_operations].sort();
const DIRECTOR = [
  'skill-tree-director-audit', 'skill-tree-director-decide', 'skill-tree-director-install', 'skill-tree-director-intake', 'skill-tree-director-plan',
  'skill-tree-director-review', 'skill-tree-director-run', 'skill-tree-director-setup', 'skill-tree-director-status',
];
const CLOSURE = [...CORE, ...DIRECTOR].sort();
const PYTHON = 'python3';
const MARKER = 'Changes staged locally; retain the unrelated fixture work.';

function spawn(command, args, options = {}) {
  const processResult = spawnSync(command, args, { encoding: 'utf8', timeout: 45000, ...options });
  assert.ifError(processResult.error);
  return processResult;
}

function pass(result) {
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout;
}

function write(root, relative, content) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
  return file;
}

function read(root, relative) {
  return fs.readFileSync(path.join(root, relative));
}

function json(root, relative) {
  return JSON.parse(read(root, relative));
}

function sha(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

function fixture(t) {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-install-controls-')));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const project = path.join(directory, 'project');
  const unrelated = path.join(directory, 'unrelated');
  fs.mkdirSync(project);
  fs.mkdirSync(unrelated);
  return { directory, project, unrelated };
}

function cli(project, flavor, extra = []) {
  return spawn(process.execPath, [CLI, '--target', project, '--only', 'codex', '--flavor', flavor, ...extra]);
}

function installedClosure(project, names) {
  const profile = json(project, PROFILE);
  const existing = fs.readdirSync(path.join(project, AGENTS)).filter(name => name.startsWith('skill-tree-')).sort();
  assert.deepEqual(existing, names);
  assert.deepEqual(Object.keys(profile.destinations).sort(), names.map(name => `${AGENTS}/${name}`));
  assert.equal(profile.project_root, project);
  for (const [relative, record] of Object.entries(profile.destinations)) {
    assert.equal(record.flavor, profile.flavor);
    assert.deepEqual(installation.filesAt(project, relative), record.files);
  }
  for (const [relative, digest] of Object.entries(profile.bundle_digests)) {
    assert.equal(sha(read(project, relative)), digest, relative);
  }
  pass(spawn(process.execPath, [path.join(project, MANAGER), '--verify']));
  return profile;
}

function core(project, operation, payload = null, extra = []) {
  const entry = path.join(project, AGENTS, 'skill-tree-work-through-next/scripts/workflow-state.py');
  const argv = ['-B', entry, operation, project, ...extra];
  if (payload !== null) {
    const file = write(path.dirname(project), 'input.json', JSON.stringify(payload));
    argv.push('--input', file);
  }
  return JSON.parse(pass(spawn(PYTHON, argv, { cwd: path.dirname(project) })));
}

function coreTask(project) {
  const goal = 'Preserve the isolated scope.';
  const pending = core(project, 'intake', {
    title: 'Inspect the retained scope', description: goal, expected_behavior: goal,
  });
  const check = {
    id: 'fixture-scope', recipe_id: 'static-inspection', criteria: [goal], sources: ['unrelated.txt'],
    parameters: {}, assertion: goal, timing: 'immediate',
  };
  const body = `Goal:\n- ${goal}\n\nTouch:\n- unrelated.txt\n\nValidation:\n\`\`\`json\n${JSON.stringify({ checks: [check] })}\n\`\`\`\n\nAcceptance:\n- ${goal}\n`;
  return core(project, 'process', {
    selectors: [pending.id], dispositions: { [pending.id]: { status: 'promoted', reason: 'The fixture supplies the scope.' } },
    tasks: [{ title: 'Inspect the retained scope', body, parent_pending_ids: [pending.id] }],
  }).created_ids[0];
}

function git(project, ...args) {
  return pass(spawn('git', ['-C', project, '-c', 'commit.gpgsign=false', '-c', `core.hooksPath=${os.devNull}`, ...args]));
}

test('Director lists the exact closure, dry-run is byte-neutral, and the owned package executes independently', t => {
  const { directory, project, unrelated } = fixture(t);
  write(project, `${AGENTS}/independent-skill/SKILL.md`, 'Independent provider content.\n');
  const before = installation.treeHash(directory, 'project');
  for (const flavor of ['general', 'web', 'unity', 'director']) {
    const inventory = pass(spawn(process.execPath, [CLI, '--list', '--flavor', flavor]));
    const listed = inventory.split('\nLogical operations:\n')[1].trim().split('\n');
    assert.deepEqual(listed, flavor === 'director' ? CLOSURE : CORE);
  }
  const dry = pass(cli(project, 'director', ['--dry-run']));
  for (const name of CLOSURE) assert.match(dry, new RegExp(`\\b${name}\\b`));
  assert.equal(installation.treeHash(directory, 'project'), before);
  pass(cli(project, 'director'));
  const profile = installedClosure(project, CLOSURE);
  assert.equal(profile.flavor, 'director');
  assert.equal(read(project, `${AGENTS}/independent-skill/SKILL.md`).toString(), 'Independent provider content.\n');
  assert.equal(fs.existsSync(path.join(project, QUEUE)), false);
  assert.equal(fs.existsSync(path.join(project, STATE)), false);

  const operation = 'skill-tree-director-status';
  const isolated = path.join(unrelated, operation);
  fs.cpSync(path.join(project, AGENTS, operation), isolated, { recursive: true });
  const executable = path.join(isolated, 'scripts/director-entry.py');
  const invoke = () => spawn(PYTHON, ['-B', executable, 'status', project], { cwd: unrelated });
  const status = invoke();
  assert.equal(status.status, 2, status.stdout + status.stderr);
  assert.match(status.stdout, /Register Director areas before requesting status/);
  const modified = 'scripts/runtime/common/scripts/director-state.py';
  const sentinel = path.join(unrelated, 'tamper-ran');
  write(isolated, modified, `from pathlib import Path\nPath(${JSON.stringify(sentinel)}).touch()\n`);
  const refused = invoke();
  assert.equal(refused.status, 2, refused.stdout + refused.stderr);
  assert.match(refused.stderr, /Director package resource changed/);
  assert.equal(fs.existsSync(sentinel), false);
  assert.equal(fs.existsSync(path.join(project, '.skill-tree/director')), false);
});

test('an owned upgrade preserves plugin bytes, queue and the stopped schema-3 run', async t => {
  const { directory, project } = fixture(t);
  git(project, 'init', '-b', 'develop');
  write(project, QUEUE, '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  write(project, 'unrelated.txt', 'Unrelated initial file.\n');
  git(project, 'add', '.');
  git(project, '-c', 'user.name=Director Fixture', '-c', 'user.email=director-fixture@example.invalid', 'commit', '-m', 'Initial local fixture');
  git(project, 'remote', 'add', 'origin', path.join(directory, 'unused-remote.git'));
  pass(cli(project, 'general'));
  installedClosure(project, CORE);
  const source = write(directory, 'plugin/SKILL.md', '# Local instruction package\n');
  const ordered = ['first', 'second'].map((id, index) => ({
    id, plugin_id: 'local-review', operation: 'skill-tree-plugins', anchor: 'during', enabled: true,
    parameters: { index },
  }));
  const proposal = await lifecycle.prepareProposal(project, {
    operation: 'install', request_id: 'director-preserve-plugin',
    sources: [{ id: 'local-review', path: path.dirname(source) }], bindings: ordered,
  });
  lifecycle.applyProposal(project, proposal, { proposal_digest: proposal.digest });
  pass(spawn(process.execPath, [path.join(project, MANAGER), '--refresh-profile']));
  const original = installedClosure(project, CORE);

  const task = coreTask(project);
  const registry = core(project, 'workspace-setup', {});
  const worktree = path.join(directory, 'recorded-worktree');
  const launched = core(project, 'start', {
    local_base: true, local_base_authorization: 'Disposable local fixture.', base_branch: 'develop',
    branch: 'codex/director-install-fixture', worktree,
  }, ['--id', task]);
  const beforeRunning = read(project, STATE);
  const blocked = cli(project, 'director');
  assert.notEqual(blocked.status, 0);
  assert.match(blocked.stderr + blocked.stdout, /stopped cleanup\/handoff/);
  assert.deepEqual(read(project, STATE), beforeRunning);
  assert.deepEqual(json(project, PROFILE), original);

  core(project, 'checkpoint', { phase: 'blocked', stop_reason: 'Waiting for the owner.', next_action: 'Reconcile the exact fixture.' },
    ['--run-id', launched.id]);
  write(project, HISTORY, 'Earlier task source review retained.\n');
  write(project, 'unrelated.txt', MARKER);
  write(worktree, 'local-unrelated.txt', 'Retain worktree-only dirty edits.\n');
  const preserved = Object.fromEntries([QUEUE, HISTORY, plugins.REGISTRY, 'unrelated.txt'].map(rel => [rel, read(project, rel)]));
  const pluginBytes = installation.treeHash(project, plugins.PACKAGES);
  const checkpoint = json(project, STATE);
  assert.equal(checkpoint.run_registry.queue_id, registry.queue_id);

  const dry = pass(cli(project, 'director', ['--dry-run']));
  assert.match(dry, /skill-tree-director-run/);
  assert.deepEqual(json(project, STATE), checkpoint);
  assert.deepEqual(json(project, PROFILE), original);
  pass(cli(project, 'director'));

  const updated = installedClosure(project, CLOSURE);
  assert.equal(updated.flavor, 'director');
  assert.notEqual(updated.identity, original.identity);
  const expected = structuredClone(checkpoint);
  expected.run_registry.runs[launched.id].profile_refresh_required = true;
  assert.deepEqual(json(project, STATE), expected);
  for (const [relative, bytes] of Object.entries(preserved)) assert.deepEqual(read(project, relative), bytes, relative);
  assert.equal(installation.treeHash(project, plugins.PACKAGES), pluginBytes);
  assert.equal(read(worktree, 'local-unrelated.txt').toString(), 'Retain worktree-only dirty edits.\n');
  assert.deepEqual(plugins.verifyInstalled(project).bindings.map(entry => entry.id), ['first', 'second']);

  pass(cli(project, 'director'));
  assert.deepEqual(json(project, STATE), expected);
  assert.deepEqual(json(project, PROFILE), updated);

  const candidate = path.join(directory, 'candidate-source');
  fs.cpSync(path.join(project, '.skill-tree/installation/source'), candidate, { recursive: true });
  const changed = 'domains/director/sections.json';
  fs.appendFileSync(path.join(candidate, changed), '\n');
  assert.equal(installation.install(project, candidate, 'director', []).action, 'installed');
  const revised = installedClosure(project, CLOSURE);
  assert.notEqual(revised.identity, updated.identity);
  assert.equal(revised.source_digests[changed], sha(read(candidate, changed)));
  assert.deepEqual(json(project, STATE), expected);
  for (const [relative, bytes] of Object.entries(preserved)) assert.deepEqual(read(project, relative), bytes, relative);
  assert.equal(installation.treeHash(project, plugins.PACKAGES), pluginBytes);
});
