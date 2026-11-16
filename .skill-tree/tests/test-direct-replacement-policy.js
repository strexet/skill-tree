'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const {fixture, finding} = require('./development-policy-fixture.js');
const id = 'direct-replacement';
const source = 'module.exports = function app(state) { return state.mode === "old" ? state.old() : state.next(); };';

test('installed direct replacement rule blocks a verified second active path', t => {
  const project = fixture(t);
  assert.match(project.intent('skill-tree-implement-next-future-task'), /migrate affected consumers/);
  const head = project.commit(source + '\n');
  const observation = finding(id, source, 'app still dispatches to state.old() for existing mode',
    'The superseded implementation stays active in the normal entry point without an agreed contract.');
  const result = project.review(head, [observation]);
  assert.match(result.error, /direct-replacement.*app still dispatches/);
  assert.equal(Object.values(result.record.findings)[0].source_line, source);
  project.write('app.js', 'local changes');
  assert.match(project.review(head, [observation]).error, /direct-replacement/);
  assert.match(project.review(head, [{...observation, source_line: 'different source'}]).error, /candidate source/);
  assert.match(project.review(head, [{...observation, path: 'unrelated.js'}]).error, /changed file/);
});

test('the entry point switches directly and an inconclusive naming signal does not block', t => {
  const project = fixture(t);
  const head = project.commit('module.exports = function app(state) { return state.nextV2(); };\n');
  assert.deepEqual(project.review(head, []).ready.review.findings, []);
  const note = {policy: id, outcome: 'inconclusive', missing_fact: 'The version-like name does not establish another caller.'};
  const result = project.review(head, [note]);
  assert.equal(result.ready.status, 'pr-ready');
  assert.deepEqual(result.record.review.development_policy_notes, [note]);
  assert.match(project.intent('skill-tree-pr-review-cycle'), /explicit owner requirements or matching API locks/);
  assert.match(project.review(head, [{policy: id, outcome: 'inconclusive'}]).error, /missing fact/);
});

test('disabling direct replacement retires only its own readiness finding', t => {
  const project = fixture(t);
  const head = project.commit(source + '\n');
  const direct = finding(id, source, 'app preserves state.old()', 'Two active implementations ship.');
  const current = project.review(head, [direct]);
  project.toggle(id, false);
  assert.doesNotMatch(project.intent('skill-tree-implement-next-future-task'), /direct-replacement/);
  assert.match(project.intent('skill-tree-implement-next-future-task'), /network-polling/);
  assert.equal(project.review(head, [], current.record, [], {ready_only: true}).ready.status, 'pr-ready');
  const independent = {id: 'ordinary', path: 'app.js', line: 1, cause: 'Bad input', consequence: 'Invalid result', severity: 'P2'};
  assert.match(project.review(head, [direct], current.record, [independent]).error, /actionable finding/);
});

test('scoped API coexistence requires the named current check even with direct replacement disabled', t => {
  const project = fixture(t);
  project.write('.skill-tree/api-contracts.json', JSON.stringify({schema: 1, contracts: {
    api: {file: 'app.js', checks: ['public-consumer'], consumers: ['external service']}
  }}));
  project.manager('lock-api', 'api');
  const head = project.commit(source + '\n');
  assert.match(project.review(head, []).error, /Missing current successful API contract check/);
  project.toggle(id, false);
  assert.match(project.review(head, []).error, /Missing current successful API contract check/);
  const result = project.review(head, [], null, [], {checks: [{name: 'public-consumer', status: 'success'}]});
  assert.equal(result.ready.api_lock_review.plugin_id, 'api-lock-review');
  assert.deepEqual(result.ready.api_lock_review.affected, ['api (app.js)']);
  project.manager('unlock-api', 'api');
  assert.equal(project.review(head, []).ready.api_lock_review, undefined);
});

test('reverting the offending file resolves the policy finding when the PR still changes another file', t => {
  const project = fixture(t);
  const head = project.commit(source + '\n');
  const observed = finding(id, source, 'The old branch stays active.', 'The obsolete path ships.');
  const result = project.review(head, [observed]);
  const saved = Object.values(result.record.findings)[0];
  project.git('restore', '--source=HEAD^', 'app.js');
  project.write('notes.md', 'Retain an unrelated change.\n');
  project.git('add', 'app.js', 'notes.md');
  project.git('commit', '-qm', 'Remove the old path change');
  const current = project.git('rev-parse', 'HEAD');
  const fix = {id: saved.id, cause: 'The offending file matches the base.', consequence: 'The competing branch is gone.',
    severity: 'P1', status: 'verified-fixed', verified_head: current, verification_evidence: ['Compared the file to the base.']};
  const checked = project.review(current, [], result.record, [fix], {files: ['notes.md']});
  assert.equal(checked.ready.status, 'pr-ready');
  assert.equal(checked.record.findings[saved.id].path, 'app.js');
});
