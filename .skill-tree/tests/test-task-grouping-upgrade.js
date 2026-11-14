'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const test = require('node:test');
const composer = require('../lib/composer.js');
const installation = require('../lib/installation.js');

const source = path.resolve(__dirname, '..');
const future = '.skill-tree/documents/future.md';
const state = '.skill-tree/documents/future.json';
const outcomes = '.skill-tree/history/task-outcomes.jsonl';
const workflowSource = 'common/scripts/workflow-state.py';
const operation = 'skill-tree-add-pending-task';
const helper = `.agents/skills/${operation}/scripts/workflow-state.py`;
const selections = [{rel: `.agents/skills/${operation}`, provider: 'codex', name: operation}];
const legacyQueue = `# Future Work

## Pending Task Format

Fixed metadata records task identity.

## Pending Queue

### Preserve legacy scope

\`\`\`yaml
id: P-12345678-1234-4123-8123-123456789abc
priority: 100
status: Pending
parent_pending_ids: []
processing_run_id: null
root_task_id: null
related_task_id: null
relation: main
depends_on: []
\`\`\`

Description:
- Preserve the original task.

\`\`\`yaml
topic: example-in-body
\`\`\`

## Prioritized Next Changes

## Backlog
`;
const groupedQueue = legacyQueue.replace('depends_on: []', 'depends_on: []\ntopic: director');

function write(root, relative, value) {
 const file = path.join(root, relative);
 fs.mkdirSync(path.dirname(file), {recursive: true});
 fs.writeFileSync(file, typeof value === 'string' ? value : JSON.stringify(value));
}

function fixture(t, flavor = 'general', schema = 2) {
 const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-grouping-upgrade-'));
 t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
 const root = path.join(directory, 'target');
 const legacy = path.join(directory, 'legacy');
 fs.mkdirSync(root);
 for (const folder of ['common', 'config', 'domains', 'lib', 'src', 'templates']) {
  fs.cpSync(path.join(source, folder), path.join(legacy, folder), {recursive: true});
 }
 const sourceBody = fs.readFileSync(path.join(source, workflowSource), 'utf8');
 assert.match(sourceBody, /^TASK_GROUPING_COMPATIBILITY = 1$/m);
 write(legacy, workflowSource, sourceBody.replace(/^TASK_GROUPING_COMPATIBILITY = 1\n/m, ''));
 write(root, 'package.json', {scripts: {test: 'node --test'}});
 write(root, future, legacyQueue);
 const checkpoint = {format: 'skill-tree-future', schema, tasks: [], task_progress: {}, active_run: null};
 if (schema === 3) checkpoint.run_registry = {schema: 1, runs: {}, claims: {}, resources: {}};
 write(root, state, checkpoint);
 write(root, outcomes, 'Archived workflow evidence.\n');
 write(root, 'unrelated.txt', 'Developer changes.\n');
 if (flavor === 'unity') {
  write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2\n');
  write(root, 'Packages/manifest.json', {dependencies: {'com.unity.test-framework': '1.6.0'}});
  write(root, 'Packages/packages-lock.json', {dependencies: {'com.unity.test-framework': {version: '1.6.0'}}});
 }
 const snapshot = () => [future, state, outcomes, 'unrelated.txt'].map(relative => fs.readFileSync(path.join(root, relative), 'utf8'));
 return {root, legacy, snapshot, install: (candidate = source, options = {}) => installation.install(root, candidate, flavor, selections, options)};
}

for (const [flavor, schema] of [['general', 2], ['web', 3], ['unity', 3]]) {
 test(`${flavor} upgrade qualifies grouped parser bytes and protects schema ${schema} queue evidence`, t => {
  const target = fixture(t, flavor, schema);
  const before = target.snapshot();
  const old = target.install(target.legacy).profile;
  assert.equal(old.task_grouping, undefined);
  assert.throws(() => installation.verifyTaskGroupingProfile(target.root), /lacks verified task grouping support/);
  const dryRun = target.install(source, {dryRun: true});
  assert.equal(dryRun.profile.task_grouping.schema, 1);
  assert.deepEqual(target.snapshot(), before);
  assert.equal(installation.receipt(target.root, true).identity, old.identity);
  const candidate = target.install().profile;
  const proof = installation.verifyTaskGroupingProfile(target.root);
  assert.equal(proof.profile_identity, candidate.identity);
  assert.equal(proof.profile_sha256, composer.hash(fs.readFileSync(path.join(target.root, installation.PROFILE))));
  assert.deepEqual(proof.package_helpers, {[helper]: proof.source_helper_sha256});
  assert.deepEqual(target.snapshot(), before);
  write(target.root, future, groupedQueue);
  assert.equal(installation.verify(target.root, source).identity, candidate.identity);
  const grouped = target.snapshot();
  assert.throws(() => installation.rollback(target.root), /Grouped task headers require a compatible owned installation generation/);
  assert.throws(() => target.install(target.legacy), /Grouped task headers require a compatible owned installation generation/);
  assert.throws(() => installation.uninstall(target.root, selections), /Grouped task headers require a compatible owned installation generation/);
  assert.deepEqual(target.snapshot(), grouped);
  assert.equal(installation.verifyTaskGroupingProfile(target.root).profile_identity, candidate.identity);
 });
}

test('legacy task prose permits rollback before grouped metadata is written', t => {
 const target = fixture(t);
 const before = target.snapshot();
 const old = target.install(target.legacy).profile;
 target.install();
 installation.rollback(target.root);
 assert.equal(installation.verify(target.root, target.legacy).identity, old.identity);
 assert.deepEqual(target.snapshot(), before);
});

test('grouping profile evidence rejects altered capability and owned helper bytes', t => {
 const target = fixture(t);
 target.install();
 const receipt = path.join(target.root, installation.PROFILE);
 const original = fs.readFileSync(receipt);
 const altered = JSON.parse(original);
 altered.task_grouping.package_helpers[helper] = 'f'.repeat(64);
 fs.writeFileSync(receipt, JSON.stringify(altered));
 assert.throws(() => installation.verifyTaskGroupingProfile(target.root), /does not match owned source and package bytes/);
 fs.writeFileSync(receipt, original);
 fs.appendFileSync(path.join(target.root, helper), '\n# Local edits.\n');
 assert.throws(() => installation.verifyTaskGroupingProfile(target.root), /locally modified package/);
});

test('interrupted compatible activation retains and recovers the exact owned candidate', t => {
 const target = fixture(t);
 const before = target.snapshot();
 target.install(target.legacy);
 const rename = fs.renameSync;
 fs.renameSync = (from, to) => {
  if (from.includes(`${path.sep}.staging${path.sep}`)) throw new Error('Injected activation interruption');
  return rename(from, to);
 };
 try {
  assert.throws(() => target.install(), /Injected activation interruption/);
 } finally {
  fs.renameSync = rename;
 }
 assert.throws(() => installation.verifyTaskGroupingProfile(target.root), /recovery is required/);
 installation.locked(target.root, () => {});
 const observed = installation.verifyTaskGroupingProfile(target.root);
 assert.equal(target.install().action, 'verified no-op current');
 assert.deepEqual(installation.verifyTaskGroupingProfile(target.root), observed);
 assert.deepEqual(target.snapshot(), before);
});

test('linked worktree rollback detects grouped headers in canonical Markdown despite a legacy queue copy', t => {
 const target = fixture(t);
 const git = (...args) => {
  const result = spawnSync('git', ['-C', target.root, ...args], {encoding: 'utf8'});
  assert.equal(result.status, 0, result.stderr);
 };
 git('init', '-b', 'main');
 git('add', '.');
 git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Fixture');
 const worktree = path.join(path.dirname(target.root), 'linked');
 git('worktree', 'add', '-b', 'fixture', worktree);
 write(target.root, '.git/skill-tree-runtime.json', {schema: 1, canonical_root: target.root, worktrees: {}});
 installation.install(worktree, target.legacy, 'general', selections);
 installation.install(worktree, source, 'general', selections);
 write(target.root, future, groupedQueue);
 assert.equal(fs.readFileSync(path.join(worktree, future), 'utf8'), legacyQueue);
 const before = target.snapshot();
 assert.throws(() => installation.rollback(worktree), /Grouped task headers require a compatible owned installation generation/);
 assert.deepEqual(target.snapshot(), before);
});
