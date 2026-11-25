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
  return spawn(process.execPath, [CLI, '--project', '--target', project, '--only', 'codex', '--flavor', flavor, ...extra]);
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

test('dedicated launcher guides fresh implementation and upgrades owned prior text', t => {
  const {project} = fixture(t);
  const instructions = 'AGENTS.md';
  const launcher = AGENTS + '/skill-tree-director/SKILL.md';
  const hooks = '.claude/settings.json';
  const prefix = 'Owner rules\r\nKeep the local conventions.\n';
  const suffix = '\nOwner notes after routing.\n';
  write(project, instructions, prefix);
  fs.chmodSync(path.join(project, instructions), 0o664);
  write(project, hooks, '{"hooks":{"PreToolUse":[]}}\n');
  const install = (...extra) => {
    const previousUmask = process.umask(0o022);
    try {
      return spawn(process.execPath, [CLI, '--target', project, '--only', 'codex', '--flavor', 'director', ...extra]);
    } finally {
      process.umask(previousUmask);
    }
  };
  pass(cli(project, 'general'));
  const coreProfile = read(project, PROFILE);
  assert.deepEqual(JSON.parse(coreProfile).bridges, {});
  pass(install());
  const guided = read(project, launcher).toString('utf8');
  assert.match(guided, /Full Cycle.*skill-tree-full-cycle.*before creating a branch or editing product files/,
    'The fresh Director launcher must route implementation through Full Cycle before product writes');
  assert.match(guided, /exact task and isolated worktree/);
  assert.match(guided, /publication and merge authorization/);
  const bridge = read(project, instructions).toString('utf8') + suffix;
  assert.ok(bridge.startsWith(prefix));
  assert.match(bridge, /skill-tree-full-cycle/);

  const withoutGuidance = text => text.split('\n').filter(line =>
    !line.startsWith('For fresh managed implementation, preview Full Cycle')
    && !line.startsWith('For queue-only intake, use')
    && !line.startsWith('Begin scoped source edits after Core')).join('\n');
  const oldLauncher = withoutGuidance(guided);
  const oldBridge = withoutGuidance(bridge);
  write(project, launcher, oldLauncher);
  write(project, instructions, oldBridge);
  pass(install('--dry-run'));
  assert.equal(read(project, instructions).toString('utf8'), oldBridge);
  assert.equal(read(project, launcher).toString('utf8'), oldLauncher);
  pass(install());
  assert.equal(read(project, instructions).toString('utf8'), bridge);
  assert.equal(read(project, launcher).toString('utf8'), guided);
  assert.equal(fs.statSync(path.join(project, instructions)).mode & 0o777, 0o664);
  assert.equal(read(project, hooks).toString('utf8'), '{"hooks":{"PreToolUse":[]}}\n');
  assert.deepEqual(read(project, PROFILE), coreProfile);
  pass(install('--verify'));

  const editedBridge = bridge.replace('use the Skill Tree Director first.', 'use the owner-edited routing block.');
  assert.notEqual(editedBridge, bridge);
  write(project, instructions, editedBridge);
  const blocked = install();
  assert.notEqual(blocked.status, 0);
  assert.match(blocked.stdout + blocked.stderr, /Director routing instructions conflict/);
  assert.equal(read(project, instructions).toString('utf8'), editedBridge);
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

test('guided bootstrap applies only the reviewed projects and resumes a partial setup', t => {
  const { directory, project: tools, unrelated: source } = fixture(t);
  fs.mkdirSync(path.join(source, '.skill-tree'));
  for (const relative of ['bin', 'common', 'config', 'domains', 'lib', 'src', 'templates', 'tests/fixtures/director']) {
    fs.cpSync(path.join(SOURCE, relative), path.join(source, '.skill-tree', relative), {
      recursive: true, filter: file => path.basename(file) !== '__pycache__',
    });
  }
  const commit = (project, message) => git(project, '-c', 'user.name=Director Fixture',
    '-c', 'user.email=director-fixture@example.invalid', 'commit', '-m', message);
  git(source, 'init', '-b', 'develop');
  git(source, 'add', '.skill-tree');
  commit(source, 'Pin the local setup source');
  const approvedSource = { checkout: source, revision: git(source, 'rev-parse', 'HEAD').trim() };
  pass(cli(tools, 'director', ['--skills', 'skill-tree-director-setup']));
  const entry = path.join(tools, AGENTS, 'skill-tree-director-setup/scripts/director-entry.py');

  const existing = path.join(directory, 'existing');
  fs.mkdirSync(existing);
  git(existing, 'init', '-b', 'develop');
  write(existing, QUEUE, '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  write(existing, 'unrelated.txt', 'Already committed\n');
  write(existing, '.skill-tree/documents/project.md', '# Established project\n');
  git(existing, 'add', '.');
  commit(existing, 'Original project work');
  git(existing, 'remote', 'add', 'origin', path.join(directory, 'unused-remote.git'));
  pass(cli(existing, 'general'));
  const task = coreTask(existing);
  const queue = core(existing, 'workspace-setup', {}).queue_id;
  const run = core(existing, 'start', {
    local_base: true, local_base_authorization: 'Disposable local fixture.', base_branch: 'develop',
    branch: 'codex/retained-bootstrap-fixture', worktree: path.join(directory, 'active-worktree'),
  }, ['--id', task]);
  core(existing, 'checkpoint', { phase: 'blocked', stop_reason: 'Fixture waiting for the owner.' }, ['--run-id', run.id]);
  write(existing, 'unrelated.txt', 'Staged work\n');
  git(existing, 'add', 'unrelated.txt');
  write(existing, 'unrelated.txt', MARKER);

  const preserve = [QUEUE, STATE, PROFILE, '.skill-tree/skill-tree.json', '.skill-tree/documents/project.md', 'unrelated.txt'];
  const previous = preserve.map(relative => read(existing, relative));
  const ref = git(existing, 'symbolic-ref', 'HEAD');
  const head = git(existing, 'rev-parse', 'HEAD');
  const staged = git(existing, 'diff', '--cached', '--binary');
  const root = path.join(directory, 'director');
  const web = path.join(root, 'areas', 'web');
  const shared = path.join(root, 'story', 'chapters');
  const alias = path.join(directory, 'linked-existing');
  git(existing, 'worktree', 'add', '-b', 'linked-existing', alias);
  fs.mkdirSync(path.join(existing, 'notes'));
  const area = (id, role, project, flavor) => ({
    id, role, capabilities: ['review-source'], allowed_effects: ['status'], project,
    ...(flavor ? { source: approvedSource, flavor } : {}),
  });
  const request = {
    director_id: 'bootstrap-fixture',
    workspace: { kind: 'new', source: approvedSource },
    areas: [
      area('maintenance', 'source-maintenance', { kind: 'existing', topology: 'separate', path: source }, 'general'),
      area('web', 'web', { kind: 'new', topology: 'separate', placement: 'inside', path: 'areas/web' }, 'web'),
      area('story', 'narrative', { kind: 'new', topology: 'shared', placement: 'inside', path: 'story/chapters' }),
      area('existing', 'product', { kind: 'existing', topology: 'separate', path: existing }, 'general'),
      area('alias', 'notes', { kind: 'existing', topology: 'separate', path: alias, scope: 'notes' }, 'general'),
    ],
  };
  function invoke(operation, value) {
    const input = write(directory, 'guided-request.json', JSON.stringify(value));
    return spawn(PYTHON, ['-B', entry, operation, root, '--input', input], { timeout: 90000 });
  }

  const sourceQueue = '# Retained source queue\r\n\r\n## Pending Task Format\r\n\r\n## Pending Queue\r\n\r\n## Prioritized Next Changes\r\n\r\n## Backlog\r\n';
  write(source, QUEUE, sourceQueue);
  const conflictPath = `${AGENTS}/skill-tree-work-through-next/SKILL.md`;
  write(source, conflictPath, '# Existing unrelated operation\n');
  const preview = JSON.parse(pass(invoke('setup-preview', request)));
  const input = { request, expected_preview_sha256: preview.preview_sha256 };
  assert.equal(invoke('setup-bootstrap', { ...input, expected_preview_sha256: 'a'.repeat(64) }).status, 2);
  assert.equal(fs.existsSync(root), false);
  fs.appendFileSync(path.join(existing, '.skill-tree/documents/project.md'), 'Changed after approval.\n');
  const stale = invoke('setup-bootstrap', input);
  assert.equal(stale.status, 2);
  assert.match(stale.stdout, /Approved setup preview changed/);
  assert.equal(fs.existsSync(root), false);
  fs.writeFileSync(path.join(existing, '.skill-tree/documents/project.md'), previous[4]);

  const partial = invoke('setup-bootstrap', input);
  assert.equal(partial.status, 2, partial.stdout + partial.stderr);
  const deferred = JSON.parse(partial.stdout);
  assert.equal(deferred.status, 'deferred', partial.stdout);
  assert.match(deferred.error, /Unowned destination conflict/);
  assert.ok(deferred.completed[root].includes('core'));
  assert.deepEqual(preserve.map(relative => read(existing, relative)), previous);
  const coordinator = installedClosure(root, CLOSURE);
  const retainedState = read(root, STATE);
  const retainedHead = git(root, 'rev-parse', 'HEAD');
  assert.equal(read(source, conflictPath).toString(), '# Existing unrelated operation\n');
  fs.rmSync(path.dirname(path.join(source, conflictPath)), { recursive: true });

  const transaction = '.skill-tree/.transaction.json';
  const foreign = JSON.stringify({ format: 'skill-tree-transaction', writes: [
    { path: QUEUE, expected_hash: sha(previous[0]), content: previous[0].toString() + '\nChanged by a different owner.\n' },
  ] });
  write(existing, transaction, foreign);
  const retained = invoke('setup-bootstrap', input);
  assert.equal(retained.status, 2);
  assert.match(retained.stdout, /Reconcile the existing Core transaction before bootstrap/);
  assert.deepEqual(read(existing, QUEUE), previous[0]);
  assert.equal(read(existing, transaction).toString(), foreign);
  fs.unlinkSync(path.join(existing, transaction));

  git(existing, 'switch', '-c', 'other-existing-branch');
  const switched = invoke('setup-bootstrap', input);
  assert.equal(switched.status, 2);
  assert.match(switched.stdout, /setup file identity changed/);
  git(existing, 'switch', 'develop');

  const sharedParent = path.dirname(shared);
  fs.mkdirSync(sharedParent);
  git(sharedParent, 'init', '-b', 'unrelated');
  const nested = invoke('setup-bootstrap', input);
  assert.equal(nested.status, 2);
  assert.match(nested.stdout, /Approved shared area has a different Git owner/);
  assert.equal(fs.existsSync(shared), false);
  fs.rmSync(sharedParent, { recursive: true });

  const result = JSON.parse(pass(invoke('setup-bootstrap', input)));
  assert.equal(result.status, 'prepared');
  assert.deepEqual(read(root, STATE), retainedState);
  assert.equal(git(root, 'rev-parse', 'HEAD'), retainedHead);
  assert.deepEqual(json(root, PROFILE), coordinator);
  assert.equal(result.projects[existing].queue.queue_id, queue);
  assert.equal(result.projects[alias].queue.queue_id, queue);
  assert.equal(result.areas.story.queue.queue_id, result.projects[root].queue.queue_id);
  assert.notEqual(result.projects[web].queue.queue_id, result.projects[root].queue.queue_id);
  assert.equal(git(shared, 'rev-parse', '--show-toplevel').trim(), root);
  assert.equal(fs.existsSync(path.join(shared, STATE)), false);
  assert.equal(fs.existsSync(path.join(root, '.skill-tree/director/registry.json')), false);
  assert.equal(installedClosure(web, CORE).flavor, 'web');
  assert.equal(installedClosure(source, CORE).flavor, 'general');
  assert.equal(read(source, QUEUE).toString(), sourceQueue);
  assert.deepEqual(preserve.map(relative => read(existing, relative)), previous);
  assert.equal(git(existing, 'symbolic-ref', 'HEAD'), ref);
  assert.equal(git(existing, 'rev-parse', 'HEAD'), head);
  assert.equal(git(existing, 'diff', '--cached', '--binary'), staged);

  const journal = '.skill-tree/artifacts/director/setup-bootstrap.json';
  const retainedJournal = read(root, journal);
  assert.deepEqual(JSON.parse(pass(invoke('setup-bootstrap', input))), result);
  assert.deepEqual(read(root, journal), retainedJournal);
  const sourceInput = '.skill-tree/templates/operations.json';
  const sourceBytes = read(source, sourceInput);
  fs.appendFileSync(path.join(source, sourceInput), '\n');
  const drift = invoke('setup-bootstrap', input);
  assert.equal(drift.status, 2);
  assert.match(drift.stdout, /outside the exact selected commit/);
  write(source, sourceInput, sourceBytes);
  fs.renameSync(web, web + '-moved');
  fs.symlinkSync(web + '-moved', web, 'dir');
  const moved = invoke('setup-bootstrap', input);
  assert.equal(moved.status, 2);
  assert.match(moved.stdout, /Symlink in approved setup destination/);
  fs.unlinkSync(web);
  fs.renameSync(web + '-moved', web);
  fs.appendFileSync(path.join(root, '.skill-tree/documents/project.md'), 'New project work.\n');
  const changed = invoke('setup-bootstrap', input);
  assert.equal(changed.status, 2);
  assert.match(changed.stdout, /setup file identity changed/);
});
