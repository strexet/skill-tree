'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');
const {fixture, finding} = require('./development-policy-fixture.js');
const id = 'network-polling';
const poll = 'module.exports = (source, scheduler) => scheduler.repeat(() => source.fetch(), 5000);';

test('review blocks a recurring network request when a suitable subscription exists', t => {
  const project = fixture(t);
  const implement = project.intent('skill-tree-implement-next-future-task');
  assert.match(implement, /freshness and available source mechanisms/);
  assert.match(implement, /lifecycle request/);
  assert.match(implement, /justify the interval, owner, start and stop conditions/);
  const head = project.commit(poll + '\n');
  const fact = finding(id, poll, 'The mounted view calls the remote source every 5 seconds even though subscribe() delivers the required updates.',
    'Idle views repeatedly query the provider and overlapping slow fetches write stale data.');
  const result = project.review(head, [fact]);
  assert.match(result.error, /network-polling.*remote source every 5 seconds/);
  assert.equal(Object.values(result.record.findings)[0].source_line, poll);
  const onPush = '(source, receive) => source.subscribe(receive)';
  const replacement = project.commit('module.exports = ' + onPush + ';\n');
  const installed = require(path.join(project.root, 'app.js'));
  const stop = () => {};
  assert.equal(installed({subscribe: () => stop}, () => {}), stop);
  const resolved = {id: Object.keys(result.record.findings)[0], path: 'app.js', line: 1,
    cause: 'The mounted view now subscribes.', consequence: 'No recurring requests remain.',
    severity: 'P1', status: 'verified-fixed', verified_head: replacement,
    verification_evidence: ['The current mount function subscribes and returns the unsubscribe function.']};
  assert.equal(project.review(replacement, [], result.record, [resolved]).ready.status, 'pr-ready');
});

test('lifecycle fetches, bounded local waits and a pull-only loop satisfy the scoped policy', async t => {
  const project = fixture(t);
  const head = project.commit([
    'exports.mount = source => source.fetch();',
    'exports.wait = async probe => { for (let i = 0; i < 3; i++) if (await probe()) return true; return false; };',
    'exports.attachPullOnly = (source, scheduler, onError) => {',
    '  let inFlight = false;',
    '  const tick = async () => {',
    '    if (inFlight) return;',
    '    inFlight = true;',
    '    try { await source.fetch(); } catch (error) { onError(error); } finally { inFlight = false; }',
    '  };',
    '  return scheduler.repeat(tick, 5000);',
    '};', ''
  ].join('\n'));
  const refresh = require(path.join(project.root, 'app.js'));
  let fetches = 0;
  await refresh.mount({fetch: () => fetches++});
  assert.equal(fetches, 1);
  let checks = 0;
  assert.equal(await refresh.wait(() => { checks++; return false; }), false);
  assert.equal(checks, 3);
  let current, finish, report;
  const scheduler = {repeat(tick, rate) {
    assert.equal(rate, 5000);
    current = tick;
    return () => { current = undefined; };
  }};
  const stop = refresh.attachPullOnly({fetch() {
    fetches++;
    return new Promise((resolve, reject) => { finish = reject; });
  }}, scheduler, error => { report = error; });
  const first = current();
  await current();
  assert.equal(fetches, 2);
  finish(new Error('temporary disconnect'));
  await first;
  assert.equal(report.message, 'temporary disconnect');
  const recovered = current();
  assert.equal(fetches, 3);
  finish(new Error('temporary disconnect'));
  await recovered;
  stop();
  assert.equal(current, undefined);
  assert.equal(project.review(head, []).ready.status, 'pr-ready');
});

test('an inconclusive timer observation leaves readiness to independent checks', t => {
  const project = fixture(t);
  const head = project.commit('module.exports = callback => setTimeout(callback, 500);\n');
  const finding = {policy: id, outcome: 'inconclusive', missing_fact: 'The caller or timer target has not been established.'};
  const result = project.review(head, [finding]);
  assert.deepEqual(result.record.review.development_policy_notes, [finding]);
  assert.equal(result.ready.status, 'pr-ready');
  assert.match(project.review(head, [finding], null, [],
    {checks: [{name: 'suite', status: 'pending', required: true}]}).error, /Required checks/);
});

test('disabling polling preserves direct replacement and locked check requirements', t => {
  const project = fixture(t);
  project.write('.skill-tree/api-contracts.json', JSON.stringify({schema: 1, contracts: {
    protocol: {file: 'app.js', checks: ['consumer-contract']}
  }}));
  project.manager('lock-api', 'protocol');
  const head = project.commit(poll + '\n');
  const required = {checks: [{name: 'consumer-contract', status: 'success'}]};
  const refresh = finding(id, poll, 'The network refresh overlaps.', 'Repeated requests ship.');
  const direct = finding('direct-replacement', poll, 'The view retains the old source through its default registration.',
    'Affected callers continue to use the superseded path.');
  const blocked = project.review(head, [refresh, direct], null, [], required).record;
  project.toggle(id, false);
  const readyOnly = {ready_only: true, ...required};
  assert.match(project.review(head, [], blocked, [], readyOnly).error, /direct-replacement/);
  assert.match(project.review(head, [], blocked, [], {ready_only: true}).error, /successful API contract check/);
  assert.doesNotMatch(project.intent('skill-tree-implement-next-future-task'), /network-polling/);
  assert.match(project.intent('skill-tree-implement-next-future-task'), /direct-replacement/);
});
