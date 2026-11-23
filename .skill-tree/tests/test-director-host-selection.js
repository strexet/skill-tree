'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const core = require('../lib/installation.js');
const canary = require('../lib/director-canary.js');
const {fixture, workflow, SNAPSHOT} = require('./fixtures/director-canary.js');

for (const providers of [['claude-code'], ['dsh', 'gemini-cli']]) {
  test('verified audit and canary replay in ' + providers.join(' + '), t => {
    const f = fixture(t, providers);
    const audit = path.resolve(__dirname, '../common/scripts/director-audit.py');
    const probe = spawnSync('python3', ['-B','-c', [
      'from pathlib import Path',
      'import runpy,sys',
      'audit=runpy.run_path(sys.argv[1])',
      'controlled=audit["_generation"](Path(sys.argv[2]),sys.argv[3])',
      'assert controlled and not audit["_generation"](Path(sys.argv[2]), "foreign/"+sys.argv[3])',
    ].join('\n'), audit, f.target, f.helper], {encoding:'utf8'});
    assert.equal(probe.status, 0, probe.stdout + probe.stderr);
    const view = canary.preview(f.target, f.source, f.candidate, f.scope, f.candidate.candidate_sha256);
    const destination = path.posix.dirname(path.posix.dirname(f.helper));
    assert.equal(path.posix.basename(destination), SNAPSHOT);
    assert.deepEqual(view.host_destinations[destination], [...providers].sort());
    const other = {...f.scope, provider: 'unregistered'};
    assert.throws(() => canary.preview(f.target, f.source, f.candidate, other, f.candidate.candidate_sha256), /selected flavor and provider|selected host/);
    canary.apply(f.target, f.source, f.candidate, view, view.preview_sha256);
    assert.deepEqual(core.receipt(f.target,true).destinations[destination].providers,[...providers].sort());
    workflow(f.target, f.local, 'admit', {}, '--run-id', f.scope.run_id);
    assert.equal(canary.replay(f.target, f.source, f.candidate, view, view.preview_sha256).status,'verified-replay');
  });
}
