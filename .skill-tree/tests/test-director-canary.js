'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const childProcess = require('node:child_process');
const {spawnSync} = childProcess;
const c = require('../lib/composer.js');
const core = require('../lib/installation.js');
const canary = require('../lib/director-canary.js');
const {fixture, workflow, installedSnapshot, write, cid, WORKFLOW, INSTALLED_HELPER, README} = require('./fixtures/director-canary.js');

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
