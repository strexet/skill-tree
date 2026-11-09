'use strict';

// Controlled project, source and registry fixtures. No external plugin is executed.
const assert = require('node:assert/strict');
const {randomUUID} = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const sourceRoot = path.resolve(__dirname, '..');
const {
  managementInventory, prepareManagerRequest, applyManagerProposal, formatInventory,
} = require(path.join(sourceRoot, 'lib/plugin-management.js'));
const core = require(path.join(sourceRoot, 'lib/installation.js'));
const composer = require(path.join(sourceRoot, 'lib/composer.js'));
const registry = require(path.join(sourceRoot, 'lib/plugin-registry.js'));
const lifecycle = require(path.join(sourceRoot, 'lib/plugin-lifecycle.js'));

const operation = 'skill-tree-process-future-pending';
const point = operation + ':after';
const occurrence = (id, plugin_id, overrides = {}) => ({
  id, plugin_id, operation, anchor: 'after', enabled: true, ...overrides,
});

function write(root, relative, value) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, value);
}

function temporaryProject(t, {withoutCatalog = false} = {}) {
  const temp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-manager-')));
  const root = path.join(temp, 'project'), upstream = path.join(temp, 'private-acquisition');
  fs.mkdirSync(root);
  fs.mkdirSync(upstream);
  t.after(() => fs.rmSync(temp, {recursive: true, force: true}));
  const source = withoutCatalog ? path.join(temp, 'source-without-catalog') : sourceRoot;
  if (withoutCatalog) {
    const omitted = new Set(['config/plugin-catalog.json', 'config/plugin-catalog-eligibility.json']);
    for (const relative of Object.keys(composer.sourceInputs(sourceRoot))) {
      if (!omitted.has(relative)) write(source, relative, fs.readFileSync(path.join(sourceRoot, relative)));
    }
  }
  core.install(root, source, 'general', [{
    name: operation, provider: 'codex', rel: '.agents/skills/' + operation,
  }]);

  const marker = path.join(upstream, 'helper-executed');
  const definitions = ['fixture-editor', 'fixture-interview'].map(id => {
    const original = path.join(upstream, id);
    write(original, 'SKILL.md', '---\nname: ' + id + '\n---\nReview [notes](notes.md) and [the helper](helper.js).\n');
    write(original, 'notes.md', '# Exact test resource for ' + id + '\n');
    write(original, 'helper.js', 'require("node:fs").writeFileSync(' + JSON.stringify(marker) + ', "unexpected");\n');
    return {
      id, path: original,
      metadata: {authoring_host: 'claude'},
      ...(id === 'fixture-interview' ? {capabilities: ['fixture-native-tool']} : {}),
    };
  });
  return {root, source, upstream, marker, definitions};
}

function noWorkflow(fixture) {
  for (const relative of [
    '.skill-tree/documents/future.md', '.skill-tree/documents/future.json',
    '.skill-tree/invocations', '.skill-tree/decisions', '.skill-tree/clarifications',
  ]) assert.equal(fs.existsSync(path.join(fixture.root, relative)), false, relative);
  assert.equal(fs.existsSync(fixture.marker), false, 'A source helper executed during management');
}

function current(fixture) {
  return registry.readRegistry(fixture.root);
}

function inspect(fixture) {
  return managementInventory(fixture.root, {source: fixture.source});
}

async function preview(fixture, request) {
  const result = await prepareManagerRequest(fixture.root, request, {source: fixture.source});
  assert.equal(result.status, 'ready', JSON.stringify(result.prerequisites));
  assert.match(result.proposal.digest, /^[a-f0-9]{64}$/);
  assert.ok(result.preview, 'A public reviewable preview must be separate from the internal proposal');
  return result;
}

async function apply(fixture, prepared, confirmation = {proposal_digest: prepared.proposal.digest}) {
  return applyManagerProposal(fixture.root, prepared.proposal, confirmation, {source: fixture.source});
}

function liveOrder(fixture) {
  return current(fixture).bindings.map(row => row.id);
}

function publicChain(prepared) {
  return prepared.preview.bindings.map(row => [row.id, row.plugin_id, row.point_position, row.parameters]);
}

const installChain = [
  occurrence('editor-first', 'fixture-editor', {parameters: {pass: 'first', controls: [1, null]}, instructions: 'First wording pass.'}),
  occurrence('interview-middle', 'fixture-interview', {
    anchor: 'after-task-creation', condition: {present: '/accepted_marker'}, parameters: {rounds: 2},
  }),
  occurrence('editor-last', 'fixture-editor', {parameters: {pass: 'last', controls: [3, true]}, instructions: 'Recheck new wording.'}),
];

test('missing curated data keeps fresh and saved project-known management offline', async t => {
  const f = temporaryProject(t, {withoutCatalog: true});
  const pristine = core.treeHash(f.root, '.skill-tree');
  const clean = await inspect(f);
  assert.deepEqual(clean.plugins, []);
  assert.deepEqual(clean.bindings, []);
  assert.equal(core.treeHash(f.root, '.skill-tree'), pristine);
  noWorkflow(f);

  const first = f.definitions[0];
  const save = await preview(f, {
    action: 'save-known', request_id: 'save-project-source', source: first,
    suggested_locations: [{operation, anchor: 'after-task-creation'}],
  });
  assert.ok(!JSON.stringify(save.preview).includes(f.upstream), 'Public preview exposes a machine-local locator');
  await assert.rejects(apply(f, save, {proposal_digest: '0'.repeat(64)}), /consent|confirm|digest/i);
  assert.equal(core.treeHash(f.root, '.skill-tree'), pristine);
  await apply(f, save);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false, 'Saving a known source installed a plugin');
  const known = await inspect(f);
  assert.ok(known.catalog.entries.some(row => row.id === first.id && row.origin === 'project-known'));
  assert.ok(known.catalog.groups.find(row => row.boundary_id === point).suggested.includes(first.id));
  assert.match(formatInventory(known, {groupBy: 'point'}), /Catalog is unavailable/);
  assert.match(formatInventory(known, {groupBy: 'point'}), /fixture-editor/);
  await assert.rejects(prepareManagerRequest(f.root, {
    action: 'install', request_id: 'missing-current-locator', sources: [first.id],
  }, {source: f.source}), /explicit current acquisition locator/);
  await assert.rejects(prepareManagerRequest(f.root, {
    action: 'install', request_id: 'foreign-current-locator',
    sources: [{known_id: first.id, locator: {path: f.definitions[1].path}}],
  }, {source: f.source}), /differs from the selected source identity/);
  assert.ok(!JSON.stringify(known).includes(f.upstream), 'Public inventory exposes a machine-local locator');
  noWorkflow(f);
});

test('shared manager previews exact A-B-A and preserves order across cancellation, move and replay', async t => {
  const f = temporaryProject(t);
  const before = core.treeHash(f.root, '.skill-tree');
  const install = await preview(f, {
    action: 'install', request_id: 'install-aba', sources: f.definitions, bindings: installChain,
  });
  assert.deepEqual(publicChain(install), installChain.map((row, index) => [row.id, row.plugin_id, index + 1, row.parameters]));
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  await assert.rejects(apply(f, install, {proposal_digest: '0'.repeat(64)}), /consent|confirm|digest/i);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  await apply(f, install);

  assert.deepEqual(liveOrder(f), installChain.map(row => row.id));
  const installed = await inspect(f);
  assert.equal(installed.plugins.length, 2, 'A second editor occurrence must not install a second package');
  assert.deepEqual(installed.points.find(row => row.boundary_id === point).bindings.map(row => row.id), liveOrder(f));
  assert.deepEqual(installed.plugins.find(row => row.id === 'fixture-interview').execution.missing, ['fixture-native-tool']);
  assert.deepEqual(installed.bindings[1].condition, installChain[1].condition);
  assert.deepEqual(installed.bindings[2].effective.values, installChain[2].parameters);
  assert.equal(installed.bindings[2].effective.instructions, installChain[2].instructions);

  const originalRegistry = fs.readFileSync(path.join(f.root, registry.REGISTRY));
  const abandon = await preview(f, {
    action: 'move', request_id: 'abandon-reorder', binding_id: 'editor-last', index: 0,
  });
  assert.deepEqual(abandon.preview.bindings.map(row => row.id), ['editor-last', 'editor-first', 'interview-middle']);
  // Cancellation has no activation call. A mismatched digest from the abandoned
  // preview also must not confirm a later one.
  const change = await preview(f, {
    action: 'move', request_id: 'confirm-reorder', binding_id: 'interview-middle', index: 0,
  });
  await assert.rejects(apply(f, change, {proposal_digest: abandon.proposal.digest}), /consent|confirm|digest/i);
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), originalRegistry);
  await apply(f, change);
  assert.deepEqual(liveOrder(f), ['interview-middle', 'editor-first', 'editor-last']);
  assert.deepEqual(current(f).bindings.find(row => row.id === 'editor-last'), installChain[2]);

  const updated = fs.readFileSync(path.join(f.root, registry.REGISTRY));
  const replay = await apply(f, change);
  assert.equal(replay.replayed, true);
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), updated);
  await assert.rejects(apply(f, abandon), /stale|generation|current/i);
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), updated);
  noWorkflow(f);
});

test('manager preview derives readiness from the actual boundary and validates active adaptations', async t => {
  const f = temporaryProject(t);
  const source = f.definitions[0];
  source.metadata.application_policy = {readiness_effect: 'This source claims no readiness effect.'};
  source.adapter = {processing_application: {schema: 1, roles: ['task-editorial'], default_role: 'task-editorial'}};
  const prepared = await preview(f, {
    action: 'install', request_id: 'preview-readiness', sources: [source], bindings: [
      occurrence('editor', source.id, {anchor: 'after-task-creation'}),
      occurrence('ordinary', source.id, {anchor: 'before'}),
      occurrence('review', source.id, {operation: 'skill-tree-pr-review-cycle'}),
      occurrence('excluded', source.id, {condition: false}),
    ],
  });
  const effects = Object.fromEntries(prepared.preview.bindings.map(row => [row.id, row.readiness]));
  assert.match(effects.editor, /task-editorial.*acceptance before implementation/);
  assert.match(effects.ordinary, /participate/);
  assert.match(effects.review, /before PR readiness/);
  assert.match(effects.excluded, /condition excludes/);
  const before = core.treeHash(f.root, '.skill-tree');
  source.adapter.processing_application.default_role = 'missing-role';
  await assert.rejects(prepareManagerRequest(f.root, {
    action: 'install', request_id: 'invalid-readiness', sources: [source], bindings: [occurrence('editor', source.id)],
  }), {code: 'runtime-application'});
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
});

test('unreadable project-known state reports drift without hiding installed plugins', async t => {
  const f = temporaryProject(t);
  await apply(f, await preview(f, {
    action: 'install', request_id: 'before-known-drift', sources: [f.definitions[0]],
  }));
  core.refresh(f.root, f.source);
  write(f.root, '.skill-tree/installation/plugin-known.json', '{invalid');
  const before = core.treeHash(f.root, '.skill-tree');
  const inventory = inspect(f);
  assert.equal(inventory.status, 'drift');
  assert.equal(inventory.known.status, 'unavailable');
  assert.deepEqual(inventory.plugins.map(row => row.id), [f.definitions[0].id]);
  assert.ok(inventory.issues.some(issue => issue.scope === 'project-known'));
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  await apply(f, await preview(f, {
    action: 'uninstall', request_id: 'uninstall-with-known-drift', plugin_id: f.definitions[0].id,
  }));
  assert.deepEqual(Object.keys(current(f).packages), []);
  assert.equal(fs.readFileSync(path.join(f.root, '.skill-tree/installation/plugin-known.json'), 'utf8'), '{invalid');
});

test('exact unbind, package uninstall and forget preserve independent owned records', async t => {
  const f = temporaryProject(t);
  const first = f.definitions[0];
  await apply(f, await preview(f, {action: 'save-known', request_id: 'remember-editor', source: first}));
  await apply(f, await preview(f, {
    action: 'install', request_id: 'install-removal-fixture',
    sources: [{known_id: first.id, locator: {path: first.path}}, f.definitions[1]], bindings: installChain,
  }));
  await assert.rejects(async () => preview(f, {
    action: 'unbind', request_id: 'fuzzy-unbind', binding_id: 'editor',
  }), /exact|exist|unknown|identity/i);

  const one = await preview(f, {
    action: 'unbind', request_id: 'remove-editor-first', binding_id: 'editor-first',
  });
  await apply(f, one);
  assert.deepEqual(liveOrder(f), ['interview-middle', 'editor-last']);
  assert.ok(current(f).packages[first.id]);

  const remove = await preview(f, {
    action: 'uninstall', request_id: 'remove-editor-package', plugin_id: first.id,
  });
  await apply(f, remove);
  assert.deepEqual(liveOrder(f), ['interview-middle']);
  assert.ok(!current(f).packages[first.id]);
  assert.ok(current(f).packages['fixture-interview']);
  assert.ok(fs.existsSync(path.join(first.path, 'SKILL.md')));
  assert.ok((await inspect(f)).catalog.entries.some(row => row.id === first.id));
  assert.equal((await apply(f, remove)).replayed, true);

  const preserved = fs.readFileSync(path.join(f.root, registry.REGISTRY));
  await apply(f, await preview(f, {action: 'forget-known', request_id: 'forget-editor', plugin_id: first.id}));
  assert.ok(!(await inspect(f)).catalog.entries.some(row => row.id === first.id));
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), preserved);
  assert.ok(fs.existsSync(path.join(first.path, 'SKILL.md')));
  noWorkflow(f);
});

function rehashEnvelope(proposal) {
  const {digest, ...data} = proposal;
  return {...data, digest: registry.hash(registry.json(data))};
}

test('confirmed provider scope is checked inside lifecycle and original replay survives a later provider change', async t => {
  const f = temporaryProject(t);
  const original = await preview(f, {action: 'install', request_id: 'scope-original', sources: f.definitions, bindings: installChain});
  await apply(f, original);
  core.refresh(f.root, f.source);
  const stale = await preview(f, {action: 'move', request_id: 'scope-stale', binding_id: 'editor-last', index: 0});
  const profile = core.receipt(f.root, true);
  core.install(f.root, f.source, 'general', [{
    name: operation, provider: 'gemini-cli', rel: '.agents/skills/' + operation,
  }]);
  const changed = core.receipt(f.root, true);
  assert.equal(changed.identity, profile.identity, 'The ownership-only provider change must preserve composition identity');
  assert.notDeepEqual(changed.destinations, profile.destinations);
  const before = core.treeHash(f.root, '.skill-tree');
  await assert.rejects(apply(f, stale), /provider or destination scope changed/);
  assert.equal((await apply(f, original)).replayed, true);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  noWorkflow(f);
});

test('rehashed outer preview and configure-action relabelling cannot replace the inner seal', async t => {
  const f = temporaryProject(t);
  await apply(f, await preview(f, {action: 'install', request_id: 'seal-install', sources: f.definitions, bindings: installChain}));
  const planned = await preview(f, {action: 'move', request_id: 'seal-move', binding_id: 'editor-last', index: 0});
  await assert.rejects(prepareManagerRequest(f.root, {action: 'move', request_id: 'wrong-fields',
    binding_id: 'editor-last', index: 0, bindings: []}, {source: f.source}), /exact fields/);
  await assert.rejects(apply(f, planned, {proposal_digest: planned.proposal.digest, cancelled: true}), /confirmation/);
  const before = core.treeHash(f.root, '.skill-tree');
  const altered = structuredClone(planned.proposal);
  altered.preview.impact.removed_bindings = ['fabricated'];
  const relabelled = structuredClone(planned.proposal);
  relabelled.action = 'edit';
  relabelled.preview.action = 'edit';
  for (const untrusted of [altered, relabelled]) {
    const proposal = rehashEnvelope(untrusted);
    await assert.rejects(apply(f, {proposal}), /does not match the owned lifecycle proposal/);
  }
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  await apply(f, planned);
  assert.equal(liveOrder(f)[0], 'editor-last');
});

test('known-only activation neither recovers unrelated journals nor mutates installed state', async t => {
  const f = temporaryProject(t);
  const save = await preview(f, {action: 'save-known', request_id: 'scoped-known-save', source: f.definitions[0]});
  const later = await preview(f, {action: 'save-known', request_id: 'stale-known-save', source: f.definitions[1]});
  for (const channel of ['core', 'plugins']) {
    const relative = core.transactionPaths(channel).journal;
    write(f.root, relative, '{"unrelated":true}\n');
    const original = core.treeHash(f.root, '.skill-tree');
    await assert.rejects(apply(f, save), /recovery is required/);
    assert.equal(core.treeHash(f.root, '.skill-tree'), original);
    fs.unlinkSync(path.join(f.root, relative));
  }
  await apply(f, save);
  const saved = core.treeHash(f.root, '.skill-tree');
  assert.equal((await apply(f, save)).replayed, true);
  await assert.rejects(apply(f, later), /known generation|provider scope changed/);
  assert.equal(core.treeHash(f.root, '.skill-tree'), saved);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  noWorkflow(f);
});

function retainedFixture(f, execution, attempts = {}) {
  const value = current(f);
  const id = 'HC-' + randomUUID();
  const frame = {
    schema: 1, id, revision: 1, state: 'cancelled', attempts, stages: [],
    configuration: {packages: value.packages, bindings: value.bindings},
  };
  const chain_hash = registry.hash(JSON.stringify(JSON.parse(registry.json(frame))));
  const relative = id.toLowerCase() + '.json';
  write(f.root, '.skill-tree/invocations/' + relative, JSON.stringify({...frame, chain_hash}));
  if (execution) write(f.root, '.skill-tree/local/hook-locations/' + relative,
    JSON.stringify({schema: 1, chain_id: id, canonical_root: f.root, execution_root: execution}));
  return {id, path: path.join(f.root, '.skill-tree/invocations', relative)};
}

test('pure point reorder exposes matched frozen requirements while preserving unrelated slots and records', async t => {
  const f = temporaryProject(t);
  const differentPoint = occurrence('independent', 'fixture-editor', {anchor: 'before'});
  const initial = [installChain[0], differentPoint, ...installChain.slice(1)];
  await apply(f, await preview(f, {action: 'install', request_id: 'parked-install', sources: f.definitions, bindings: initial}));
  const matched = retainedFixture(f, f.root), foreign = retainedFixture(f, f.upstream), uncertain = retainedFixture(f);
  const original = fs.readFileSync(matched.path);
  const move = await preview(f, {action: 'move', request_id: 'parked-reorder', binding_id: 'editor-last', index: 0});
  assert.deepEqual(move.preview.impact.frozen_requirements.map(row => row.chain_id), [matched.id]);
  assert.deepEqual(move.preview.impact.uncertain_frozen_requirements.map(row => row.chain_id), [uncertain.id]);
  assert.ok(!JSON.stringify(move.preview.impact).includes(foreign.id));
  assert.deepEqual(move.preview.bindings.map(row => row.id), ['editor-last', 'independent', 'editor-first', 'interview-middle']);
  await apply(f, move);
  assert.deepEqual(fs.readFileSync(matched.path), original);
  assert.deepEqual(current(f).bindings[1], differentPoint);
  assert.equal(fs.existsSync(f.marker), false);
});

test('bind, edit, activation and update use one exact proposal shape with no dispatch', async t => {
  const f = temporaryProject(t);
  const initial = installChain.slice(0, 2);
  await apply(f, await preview(f, {action: 'install', request_id: 'editable-install', sources: f.definitions, bindings: initial}));
  const extra = occurrence('editor-extra', 'fixture-editor', {parameters: {mode: 'extra'}});
  const {operation: targetOperation, anchor, ...values} = extra;
  await apply(f, await preview(f, {action: 'bind', request_id: 'editable-bind',
    binding: {...values, location: targetOperation + ':' + anchor}}));
  assert.deepEqual(liveOrder(f), ['editor-first', 'interview-middle', 'editor-extra']);
  await apply(f, await preview(f, {action: 'edit', request_id: 'editable-edit', binding_id: 'editor-extra',
    changes: {parameters: {mode: 'new'}, instructions: 'Inspect the requested text.', condition: {present: '/selected'}}}));
  await apply(f, await preview(f, {action: 'disable', request_id: 'editable-disable', binding_id: 'editor-extra'}));
  assert.equal(current(f).bindings.at(-1).enabled, false);
  await apply(f, await preview(f, {action: 'enable', request_id: 'editable-enable', binding_id: 'editor-extra'}));
  const previous = current(f);
  write(f.definitions[0].path, 'notes.md', '# Updated source bytes\n');
  const update = await preview(f, {action: 'update', request_id: 'editable-update', sources: [f.definitions[0]]});
  await apply(f, update);
  const after = current(f);
  assert.notEqual(after.packages['fixture-editor'].revision, previous.packages['fixture-editor'].revision);
  assert.deepEqual(after.bindings, previous.bindings);
  assert.deepEqual(after.bindings.at(-1).parameters, {mode: 'new'});
  noWorkflow(f);
});

test('manager lifecycle preserves pending journals for new requests and exact recorded replay', async t => {
  const f = temporaryProject(t);
  const original = await preview(f, {action: 'install', request_id: 'journal-origin', sources: f.definitions, bindings: installChain});
  await apply(f, original);
  const move = await preview(f, {action: 'move', request_id: 'journal-move', binding_id: 'editor-last', index: 0});
  for (const channel of ['core', 'plugins']) {
    const relative = core.transactionPaths(channel).journal;
    write(f.root, relative, JSON.stringify({schema: 1, channel, entries: []}));
    const originalBytes = core.treeHash(f.root, '.skill-tree');
    await assert.rejects(apply(f, move), /recovery is required/);
    assert.equal((await apply(f, original)).replayed, true);
    assert.equal(core.treeHash(f.root, '.skill-tree'), originalBytes);
    fs.unlinkSync(path.join(f.root, relative));
  }
  const legacy = await lifecycle.prepareProposal(f.root, {
    request_id: 'legacy-recovers', operation: 'configure', bindings: installChain.slice().reverse(),
  });
  const journal = core.transactionPaths('plugins').journal;
  write(f.root, journal, JSON.stringify({schema: 1, channel: 'plugins', entries: []}));
  assert.equal(lifecycle.applyProposal(f.root, legacy, {proposal_digest: legacy.digest}).action, 'configured');
  assert.equal(fs.existsSync(path.join(f.root, journal)), false);
  noWorkflow(f);
});

test('blocked preparation shows the requested change without exposing an actionable proposal', async t => {
  const f = temporaryProject(t);
  await apply(f, await preview(f, {action: 'install', request_id: 'blocked-origin', sources: f.definitions, bindings: installChain}));
  const pending = retainedFixture(f, f.root, {'fixture-attempt': {status: 'prepared'}});
  const before = core.treeHash(f.root, '.skill-tree');
  const blocked = await prepareManagerRequest(f.root, {action: 'move', request_id: 'blocked-move',
    binding_id: 'editor-last', index: 0}, {source: f.source});
  assert.equal(blocked.status, 'blocked');
  assert.ok(blocked.prerequisites.some(item => item.code === 'plugin-active'));
  assert.equal(blocked.preview.bindings[0].id, 'editor-last');
  assert.equal(blocked.proposal, null);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  assert.equal(fs.existsSync(pending.path), true);
});

test('new stopped frozen impact invalidates consent and inner lifecycle cannot bypass the manager guard', async t => {
  const f = temporaryProject(t);
  await apply(f, await preview(f, {action: 'install', request_id: 'impact-origin', sources: f.definitions, bindings: installChain}));
  const action = {action: 'move', request_id: 'impact-move', binding_id: 'editor-last', index: 0};
  const stale = await preview(f, action);
  const raw = stale.proposal.mutation.proposal;
  assert.throws(() => lifecycle.applyProposal(f.root, raw, {proposal_digest: raw.digest}), /manager.*guard/i);
  const foreign = retainedFixture(f, f.upstream);
  assert.ok(!JSON.stringify(stale.preview.impact).includes(foreign.id));
  const matched = retainedFixture(f, f.root);
  const before = core.treeHash(f.root, '.skill-tree');
  await assert.rejects(apply(f, stale), /frozen.*changed/i);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  const current = await preview(f, action);
  assert.deepEqual(current.preview.impact.frozen_requirements.map(row => row.chain_id), [matched.id]);
  assert.notEqual(current.proposal.digest, stale.proposal.digest);
  assert.equal((await apply(f, current)).action, 'configured');
  assert.deepEqual(liveOrder(f), ['editor-last', 'editor-first', 'interview-middle']);
});

test('staged activation rechecks frozen impact before mutating the registry', async t => {
  const f = temporaryProject(t);
  await apply(f, await preview(f, {action: 'install', request_id: 'staged-origin', sources: f.definitions, bindings: installChain}));
  const move = await preview(f, {action: 'move', request_id: 'staged-move', binding_id: 'editor-last', index: 0});
  const before = fs.readFileSync(path.join(f.root, registry.REGISTRY));
  const actualTransaction = core.transaction;
  let injected;
  core.transaction = (root, changes, expected, beforeActivate, channel) => actualTransaction(
    root, changes, expected, () => {
      injected = retainedFixture(f, f.root);
      beforeActivate();
    }, channel);
  try {
    await assert.rejects(apply(f, move), /frozen.*changed/i);
  } finally {
    core.transaction = actualTransaction;
  }
  assert.ok(injected && fs.existsSync(injected.path));
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), before);
});
