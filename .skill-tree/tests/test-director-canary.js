'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const childProcess = require('node:child_process');
const {spawnSync} = childProcess;
const core = require('../lib/installation.js');
const c = require('../lib/composer.js');
const canary = require('../lib/director-canary.js');

const SOURCE = path.resolve(__dirname, '..');
const SNAPSHOT = 'skill-tree-create-documents-snapshot';
const CONTROLLER = 'skill-tree-work-through-next';
const SCOPE_HELPER = 'common/scripts/create-documentation-snapshot.py';
const INSTALLED_HELPER = '.agents/skills/' + SNAPSHOT + '/scripts/create-documentation-snapshot.py';
const WORKFLOW = '.skill-tree/documents/future.json';
const README = '# Director snapshot canary\n\nThis document is the selected Markdown input.\n';
const FLAVOR = 'general';
const SCENARIO = {
  id: 'director-documentation-snapshot-readme', recipe_id: 'director-snapshot-canary',
  lane: 'unit', assertion_id: 'snapshot-scope-preserves-markdown-extension',
  assertion: 'The dry-run report preserves the Markdown extension of README.md.', input_sha256: c.hash(README),
};
const cid = prefix => prefix + '-' + randomUUID();
const seal = value => c.hash(c.json(value));

function write(root, relative, value) {
  const filename = path.join(root, relative);
  fs.mkdirSync(path.dirname(filename), {recursive: true});
  fs.writeFileSync(filename, value);
}

function run(cwd, args) {
  const result = spawnSync(args[0], args.slice(1), {cwd, encoding: 'utf8', timeout: 30000});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout.trim();
}

function git(root, ...args) {
  return run(root, ['git', '-C', root, ...args]);
}

function workflow(root, location, command, data, ...flags) {
  const payload = path.join(location, 'fixture-request.json');
  fs.writeFileSync(payload, JSON.stringify(data || {}));
  const entry = path.join(root, '.agents/skills', CONTROLLER, 'scripts/workflow-state.py');
  return JSON.parse(run(root, ['python3', '-B', entry, command, root, '--input', payload, ...flags]));
}

function copySource(base, name) {
  const dest = path.join(base, name);
  fs.mkdirSync(dest);
  for (const relative of Object.keys(c.sourceInputs(SOURCE)))
    write(dest, relative, fs.readFileSync(path.join(SOURCE, relative)));
  return dest;
}

function installedSnapshot(root) {
  const output = run(root, ['python3', '-B', path.join(root, INSTALLED_HELPER), root,
    '--dry-run', '--include', 'README.md', '--timestamp', '2000-01-01-00-00']);
  return output.split(/\r?\n/).slice(1);
}

function buildCandidate(source, target, repaired, previous) {
  const profile = c.resolveProfile(source, target, FLAVOR);
  const output = c.compose(source, profile, [SNAPSHOT, CONTROLLER]);
  const source_inventory_sha256 = seal(c.sourceInputs(source));
  const scenario_sha256 = seal(SCENARIO);
  const checks = {};
  for (const [name, result, observed] of [['original', 'fail', previous], ['repaired', 'pass', repaired]]) {
    checks[name] = {result, scenario_sha256, record_sha256: seal(observed), attempt_id: cid('C'),
      evidence: {path: 'fixture-' + name + '.txt', sha256: seal(observed)}};
  }
  const installed = core.receipt(target, true).destinations['.agents/skills/' + SNAPSHOT];
  const body = {
    schema: 1, kind: 'director-source-repair-candidate', finding_sha256: c.hash('fixture finding'),
    route: {area_id: 'source-maintenance', queue_id: cid('Q'), pending_id: cid('P'), processing_run_id: cid('PR'),
      task_id: cid('T'), run_id: cid('WR'), outcome_id: cid('O')},
    owner: {actor: 'fixture-owner', kind: 'owner-message', reference: 'synthetic-scope'},
    source: {revision: 'source-inventory:' + source_inventory_sha256, source_inventory_sha256},
    packages: {flavor: FLAVOR, provider: 'codex', environment_id: profile.environment_id,
      output_digests: output.output_digests},
    scenario: SCENARIO, checks, review: {reference: 'unit-fixture-reviewed',
      before_sha256: installed.files['scripts/create-documentation-snapshot.py'],
      after_sha256: output.output_digests[SNAPSHOT]['scripts/create-documentation-snapshot.py']},
  };
  return {...body, candidate_sha256: seal(body)};
}

function fixture(t) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'director-canary-unit-'));
  t.after(() => fs.rmSync(base, {force: true, recursive: true}));
  const local = fs.realpathSync(base);
  const old = copySource(local, 'old');
  const source = copySource(local, 'candidate');
  const oldBody = fs.readFileSync(path.join(old, SCOPE_HELPER), 'utf8');
  const mutant = oldBody.replace('print(f"- {item}")', 'print(f"- {item.removesuffix(\'.md\')}")');
  assert.notEqual(mutant, oldBody);
  write(old, SCOPE_HELPER, mutant);
  const owner = path.join(local, 'owner');
  const target = path.join(local, 'worktree');
  fs.mkdirSync(owner);
  git(owner, 'init', '-b', 'develop');
  git(owner, 'config', 'core.hooksPath', os.devnull);
  git(owner, 'config', 'protocol.allow', 'never');
  git(owner, 'remote', 'add', 'origin', path.join(local, 'unused-local-remote.git'));
  write(owner, 'README.md', README);
  write(owner, '.skill-tree/documents/future.md', '# Future Work\n\n## Pending Task Format\n\nFixture.\n\n' +
    '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  git(owner, 'add', '.');
  git(owner, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
    '-c', 'commit.gpgsign=false', 'commit', '-m', 'Local canary fixture');
  const selections = [SNAPSHOT, CONTROLLER].map(name => ({name, provider: 'codex', rel: '.agents/skills/' + name}));
  core.install(owner, old, FLAVOR, selections);
  const queue = workflow(owner, local, 'workspace-setup', {}).queue_id;
  const requirement = 'Preserve the installed snapshot member extension.';
  const pending = workflow(owner, local, 'intake', {title: 'Check snapshot member extension', description: requirement,
    expected_behavior: requirement}).id;
  const spec = {id: 'unit-fixture', recipe_id: 'static-inspection', criteria: [requirement], sources: ['README.md'],
    parameters: {}, assertion: requirement, timing: 'immediate'};
  const body = 'Goal:\n- ' + requirement + '\n\nTouch:\n- README.md\n\nValidation:\n```json\n' +
    JSON.stringify({checks: [spec]}) + '\n```\n\nAcceptance:\n- ' + requirement + '\n';
  const task = workflow(owner, local, 'process', {selectors: [pending], dispositions: {
    [pending]: {status: 'promoted', reason: 'The fixture defines exact scope.'}},
  tasks: [{title: 'Check snapshot member extension', body, parent_pending_ids: [pending]}]}).created_ids[0];
  const opened = workflow(owner, local, 'start', {local_base: true, local_base_authorization: 'Local fixture only.',
    base_branch: 'develop', branch: 'codex/canary-fixture', worktree: target}, '--id', task);
  workflow(owner, local, 'checkpoint', {phase: 'refresh-profile', stop_reason: 'Stopped for canary installation.',
    next_action: 'Verify the planned installation.'}, '--run-id', opened.id);
  core.install(target, old, FLAVOR, selections);
  workflow(target, local, 'admit', {}, '--run-id', opened.id);
  write(target, 'product.txt', 'Preserved product bytes.\n');
  write(owner, '.skill-tree/history/independent-acceptance.json', '{"fixture":"preserve"}\n');
  const scope = {queue_id: queue, run_id: opened.id, task_id: task, flavor: FLAVOR, provider: 'codex',
    authority_ref: 'fixture-owner-selected-canary', preserve_paths: ['product.txt']};
  const previous = installedSnapshot(target);
  assert.deepEqual(previous, ['included: 1', '- README']);
  const repaired = run(target, ['python3', '-B', path.join(source, SCOPE_HELPER), target,
    '--dry-run', '--include', 'README.md', '--timestamp', '2000-01-01-00-00']).split(/\r?\n/).slice(1);
  assert.deepEqual(repaired, ['included: 1', '- README.md']);
  const candidate = buildCandidate(source, target, repaired, previous);
  return {local, owner, target, scope, candidate, source, old};
}

test('canary activation reuses the owned installer and original admitted run', t => {
  const f = fixture(t);
  const before = core.treeHash(f.owner, WORKFLOW);
  const old = core.receipt(f.target, true);
  const preview = canary.preview(f.target, f.source, f.candidate, f.scope, f.candidate.candidate_sha256);
  assert.equal(core.treeHash(f.owner, WORKFLOW), before);
  assert.equal(core.receipt(f.target, true).identity, old.identity);
  assert.equal(canary.reconcile(f.target, preview, preview.preview_sha256).status, 'not-activated');
  assert.doesNotMatch(JSON.stringify(preview), new RegExp(f.local));
  assert.throws(() => canary.apply(f.owner, f.source, f.candidate, preview, preview.preview_sha256), /original exact canary/);
  const scope = {...f.scope, queue_id: cid('Q')};
  assert.throws(() => canary.preview(f.target, f.source, f.candidate, scope, f.candidate.candidate_sha256), /canonical queue/);
  const activated = canary.apply(f.target, f.source, f.candidate, preview, preview.preview_sha256);
  assert.equal(activated.replay_status, 'required');
  assert.equal(core.treeHash(f.owner, WORKFLOW), before);
  assert.equal(core.receipt(f.target, true).source_version, old.source_version);
  assert.notEqual(core.receipt(f.target, true).identity, old.identity);
  assert.equal(canary.apply(f.target, f.source, f.candidate, preview, preview.preview_sha256).acknowledgement,
    'recovered-exact-candidate');
  assert.throws(() => canary.replay(f.target, f.source, f.candidate, preview, preview.preview_sha256), /admission event/);
  workflow(f.target, f.local, 'admit', {}, '--run-id', f.scope.run_id);
  const report = canary.replay(f.target, f.source, f.candidate, preview, preview.preview_sha256);
  assert.equal(report.status, 'verified-replay');
  assert.equal(report.run_id, f.scope.run_id);
  assert.equal(report.diagnostic.cause, 'verified');
  assert(Number.isSafeInteger(report.diagnostic.duration_ms) && report.diagnostic.duration_ms >= 0);
  assert.equal(canary.reconcile(f.target, preview, preview.preview_sha256).status, 'installed');
  assert.equal(report.wider_rollout, 'separate-authority-required');
  assert.equal(core.workflowState(f.target).run_registry.runs[f.scope.run_id].stop_reason, 'Stopped for canary installation.');
  const rollback = canary.rollbackPreview(f.target, preview, preview.preview_sha256);
  const helper = fs.readFileSync(path.join(f.target, INSTALLED_HELPER));
  write(f.target, INSTALLED_HELPER, Buffer.concat([helper, Buffer.from('\n# conflict\n')]));
  assert.throws(() => canary.rollback(f.target, preview, preview.preview_sha256, rollback.rollback_sha256), /modified package/);
  write(f.target, INSTALLED_HELPER, helper);
  assert.equal(canary.rollback(f.target, preview, preview.preview_sha256, rollback.rollback_sha256).status, 'rolled-back');
  assert.equal(core.receipt(f.target, true).identity, old.identity);
  assert.deepEqual(installedSnapshot(f.target), ['included: 1', '- README']);
});

test('canary replay distinguishes process failures without returning private output', t => {
  const f = fixture(t);
  const preview = canary.preview(f.target, f.source, f.candidate, f.scope, f.candidate.candidate_sha256);
  canary.apply(f.target, f.source, f.candidate, preview, preview.preview_sha256);
  workflow(f.target, f.local, 'admit', {}, '--run-id', f.scope.run_id);
  const before = core.treeHash(f.owner, WORKFLOW);
  const privateText = 'Private process detail at ' + f.local;
  const helper = path.join(f.target, INSTALLED_HELPER);
  for (const [cause, status, code] of [
    ['timed-out', null, 'ETIMEDOUT'],
    ['launch-error', null, 'ENOENT'],
    ['exit-failure', 2, null],
    ['unexpected-output', 0, null],
    ['unexpected-output', null, 'ENOBUFS'],
  ]) {
    const error = code ? Object.assign(new Error(privateText), {code}) : undefined;
    const execution = {status, error, stdout: privateText, stderr: privateText};
    const mock = t.mock.method(childProcess, 'spawnSync', (program, args, options) => {
      if (program === 'python3' && args[1] === helper && args.includes('--dry-run')) return execution;
      return spawnSync(program, args, options);
    });
    try {
      const result = canary.replay(f.target, f.source, f.candidate, preview, preview.preview_sha256);
      assert.equal(result.status, 'rollout-held');
      assert.equal(result.run_id, f.scope.run_id);
      assert.equal(result.exit_code, status);
      assert.equal(result.diagnostic.cause, cause);
      assert(Number.isSafeInteger(result.diagnostic.duration_ms) && result.diagnostic.duration_ms >= 0);
      assert.equal(JSON.stringify(result).includes(privateText), false);
    } finally {
      mock.mock.restore();
    }
  }
  assert.equal(core.treeHash(f.owner, WORKFLOW), before);
});

test('stale preview and unauthorized mixed recovery preserve the original target', t => {
  const f = fixture(t);
  const preview = canary.preview(f.target, f.source, f.candidate, f.scope, f.candidate.candidate_sha256);
  const existing = core.receipt(f.target, true).identity;
  write(f.target, 'product.txt', 'Changed product scope.\n');
  assert.throws(() => canary.apply(f.target, f.source, f.candidate, preview, preview.preview_sha256), /Protected project/);
  assert.equal(core.receipt(f.target, true).identity, existing);
  write(f.target, 'product.txt', 'Preserved product bytes.\n');
  const originalRename = fs.renameSync;
  const journal = core.transactionPaths().journal;
  let interrupted = false;
  const fault = t.mock.method(fs, 'renameSync', (from, to) => {
    if (!interrupted && fs.existsSync(path.join(f.target, journal)) && from.startsWith(f.target)) {
      interrupted = true;
      throw Error('Simulated lost activation acknowledgment');
    }
    return originalRename(from, to);
  });
  assert.throws(() => canary.apply(f.target, f.source, f.candidate, preview, preview.preview_sha256), /Simulated lost/);
  fault.mock.restore();
  assert(interrupted);
  const originalJournal = fs.readFileSync(path.join(f.target, journal));
  const digest = c.hash(originalJournal);
  assert.equal(canary.reconcile(f.target, preview, preview.preview_sha256).journal_sha256, digest);
  const mixed = JSON.parse(originalJournal);
  mixed.entries.push({dest: 'unrelated.txt', old: null, next: c.hash('unrelated')});
  write(f.target, journal, c.json(mixed));
  assert.throws(() => canary.reconcile(f.target, preview, preview.preview_sha256), /exact preview/);
  assert.equal(fs.existsSync(path.join(f.target, 'unrelated.txt')), false);
  write(f.target, journal, originalJournal);
  assert.throws(() => canary.recover(f.target, preview, preview.preview_sha256, '1'.repeat(64)), /journal digest/);
  assert.equal(c.hash(fs.readFileSync(path.join(f.target, journal))), digest);
  assert.equal(canary.recover(f.target, preview, preview.preview_sha256, digest).acknowledgement, 'reconciled-owned-journal');
  assert.notEqual(core.receipt(f.target, true).identity, existing);
  assert.equal(fs.existsSync(path.join(f.target, journal)), false);
});
