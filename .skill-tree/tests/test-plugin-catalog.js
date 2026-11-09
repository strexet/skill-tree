'use strict';

const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const source = path.resolve(__dirname, '..');
const load = relative => require(path.join(source, relative));
const core = load('lib/installation.js');
const composer = load('lib/composer.js');
const lifecycle = load('lib/plugin-lifecycle.js');
const {formatInventory} = load('lib/plugin-management.js');
const registry = load('lib/plugin-registry.js');
const sources = load('lib/plugin-sources.js');
const {loadCatalog, catalogView, selectSource} = load('lib/plugin-catalog.js');
const manifest = load('config/plugin-catalog.json');

const processOperation = 'skill-tree-process-future-pending';
const processPoint = processOperation + ':after';
const flavors = ['general', 'unity', 'web'];
const noRecommendations = Object.fromEntries(flavors.map(flavor => [flavor, []]));
const existingDescriptors = ['ponytail', 'task-editorial', 'task-interview'];
const entryById = (view, id) => view.entries.find(row => row.id === id);
const groupByPoint = (view, point) => view.groups.find(row => row.boundary_id === point);

function write(root, relative, value) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, value);
}

function files(root, relative = '') {
  const rows = {};
  for (const entry of fs.readdirSync(path.join(root, relative), {withFileTypes: true})) {
    const name = path.posix.join(relative, entry.name);
    const absolute = path.join(root, name);
    if (entry.isDirectory()) Object.assign(rows, {[name]: 'directory'}, files(root, name));
    else if (entry.isSymbolicLink()) rows[name] = fs.readlinkSync(absolute);
    else rows[name] = registry.hash(fs.readFileSync(absolute));
  }
  return rows;
}

function setup(t) {
  const temp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-catalog-')));
  t.after(() => fs.rmSync(temp, {recursive: true, force: true}));
  const root = path.join(temp, 'project');
  const checkout = path.join(temp, 'copied-source');
  const separate = path.join(temp, 'separate-cwd');
  fs.mkdirSync(root);
  fs.mkdirSync(checkout);
  fs.mkdirSync(separate);
  return {temp, root, checkout, separate};
}

function node(file, args, cwd, guard) {
  const run = spawnSync(process.execPath, ['--require', guard, file, ...args], {cwd, encoding: 'utf8', timeout: 30000});
  assert.equal(run.status, 0, run.stdout + run.stderr);
  return run.stdout;
}

function occurrence(id, plugin_id, overrides = {}) {
  return {id, plugin_id, operation: processOperation, anchor: 'after', enabled: true, ...overrides};
}

function known(descriptor) {
  return {
    descriptor,
    suggested_locations: [{operation: processOperation, anchor: 'after'}],
    title: 'Project discovery entry',
  };
}

function arbitrary(id, ref = '1'.repeat(40)) {
  return {
    id,
    source: {kind: 'repository', url: 'https://github.com/example/independent-skill', entry: 'SKILL.md', ref},
    resources: ['LICENSE'],
    dependencies: [],
    capabilities: [],
    expectedDigests: {'SKILL.md': '2'.repeat(64), LICENSE: '3'.repeat(64)},
    package_dependencies: [],
  };
}

test('curated listing has stable identities, actual hook groups, and explicit empty recommendations', () => {
  const catalog = loadCatalog(source);
  const complete = catalogView(catalog);
  const ids = complete.entries.map(row => row.id);
  const groupIds = complete.groups.map(group => group.boundary_id);

  assert.deepEqual(ids, [...new Set(ids)].sort());
  assert.deepEqual(groupIds, [...new Set(groupIds)].sort());
  assert.deepEqual([...new Set(complete.groups.flatMap(group => group.suggested))].sort(), ids);
  assert.deepEqual(complete.recommendations, noRecommendations);

  for (const [id, boundary] of [
    ['ponytail', 'skill-tree-pr-review-cycle:after'],
    ['task-editorial', processPoint],
    ['task-interview', processPoint],
    ['writing-for-agents-documentation-report', 'skill-tree-repo-documentation-audit:after'],
  ]) {
    const row = entryById(complete, id);
    assert.ok(row, id);
    assert.match(row.revision, /^[0-9a-f]{40}$/);
    assert.ok(row.source && row.source.entry && row.source.url);
    assert.ok(row.dependencies);
    assert.equal(row.status, 'unqualified');
    assert.ok(row.hosts && row.flavors);
    assert.ok(groupByPoint(complete, boundary).suggested.includes(id));
  }

  const byPoint = catalogView(catalog, {point: processPoint, flavor: 'general', host: 'codex'});
  assert.deepEqual(byPoint.groups.map(row => row.boundary_id), [processPoint]);
  assert.ok(groupByPoint(byPoint, processPoint).suggested.includes('task-editorial'));
  assert.equal(entryById(byPoint, 'task-editorial').status, 'unqualified');
  assert.ok(!entryById(byPoint, 'ponytail'));
  assert.throws(() => catalogView(catalog, {flavor: 'invented'}), /flavor/i);
  assert.throws(() => catalogView(catalog, {point: 'invented'}), /point|anchor|location/i);
  assert.deepEqual(complete, catalogView(loadCatalog(source)));
});

test('comparison records remain distinct by application and cannot self-authorize', () => {
  const evidencePath = 'history/research/plugin-comparison-results.json';
  const qualified = load(evidencePath);
  const eligibility = load('config/plugin-catalog-eligibility.json');
  assert.equal(eligibility.source.path, '.skill-tree/' + evidencePath);
  assert.equal(eligibility.source.sha256, registry.hash(fs.readFileSync(path.join(source, evidencePath))));
  assert.deepEqual(eligibility.eligible, []);
  const complete = catalogView(loadCatalog(source));
  assert.deepEqual(complete.recommendations, Object.fromEntries(
    flavors.map(flavor => [flavor, qualified.recommendations[flavor].eligible])
  ));
  for (const observation of Object.values(qualified.applications)) {
    const entry = entryById(complete, observation.plugin_id);
    assert.equal(entry.status, observation.status);
    assert.equal(entry.application, observation.application);
    assert.equal(entry.revision, observation.source.ref);
    assert.equal(entry.source.entry, observation.source.entry);
    assert.equal(entry.content_digest, observation.content_digest);
    assert.ok(groupByPoint(complete, observation.boundary_id).suggested.includes(entry.id));
  }

  const altered = structuredClone(manifest);
  const pilot = altered.entries.find(row => row.id === 'ponytail');
  pilot.status = 'qualified';
  pilot.evidence.eligible = true;
  altered.recommendations.general.push({
    id: 'ponytail', boundary_id: 'skill-tree-pr-review-cycle:after', host: 'codex',
  });
  assert.throws(() => loadCatalog(source, {manifest: altered}), /evidence|recommend/i);
  altered.recommendations.general = [];
  delete pilot.evidence.eligible;
  assert.throws(() => loadCatalog(source, {manifest: altered}), /evidence|recommend/i);

  const injected = known(arbitrary('self-promoted'));
  injected.evidence = {status: 'qualified', eligible: true};
  const view = catalogView(loadCatalog(source), {known: {'self-promoted': injected}});
  assert.deepEqual(view.recommendations, noRecommendations);
  assert.notEqual(entryById(view, 'self-promoted').status, 'qualified');
});

test('invalid metadata rejects unknown hooks, duplicate identity, aliases and missing recommendation sources', () => {
  const mutate = change => {
    const altered = structuredClone(manifest);
    change(altered, altered.entries.find(row => row.id === 'task-editorial'));
    return () => loadCatalog(source, {manifest: altered});
  };
  assert.throws(mutate((_, row) => row.locations.push({operation: processOperation, anchor: 'unknown'})), /anchor|location|boundary/i);
  assert.throws(mutate((_, row) => row.locations.push({operation: processOperation, anchor: 'after-task-creation'})), /duplicate|same boundary/i);
  assert.throws(mutate((data, row) => data.entries.push({...row})), /duplicate|identity/i);
  assert.throws(mutate(data => data.recommendations.general.push({
    id: 'unknown-plugin', boundary_id: processPoint, host: 'codex',
  })), /unknown|recommend/i);
});

test('independent eligibility must match the exact scope, adapter and dependency closure', t => {
  const {checkout} = setup(t);
  const evidencePath = 'config/plugin-catalog-eligibility.json';
  const eligible = structuredClone(load(evidencePath));
  const draft = structuredClone(manifest);
  const pilot = draft.entries.find(row => row.id === 'ponytail');
  const second = draft.entries.find(row => row.id === 'task-editorial');
  for (const relative of ['templates/operations.json', ...draft.entries.map(row => row.descriptor).filter(Boolean)]) {
    write(checkout, relative, fs.readFileSync(path.join(source, relative)));
  }
  const save = (relative, value) => write(checkout, relative, JSON.stringify(value));
  const selected = {id: pilot.id, host: 'codex', boundary_id: 'skill-tree-pr-review-cycle:after'};
  const descriptor = structuredClone(load(pilot.descriptor));
  const other = structuredClone(load(second.descriptor));
  const record = () => {
    const {adapter, capabilities, expectedDigests, resources, dependencies, package_dependencies = []} = descriptor;
    return {
      ...selected, flavor: 'general', application: pilot.application, source: pilot.source, content_digest: pilot.content_digest,
      adapter_digest: registry.hash(registry.json({adapter, capabilities})),
      dependency_digest: registry.hash(registry.json({expectedDigests, resources, dependencies, package_dependencies})),
    };
  };

  pilot.status = 'qualified';
  pilot.flavors.general = 'observed';
  draft.recommendations.general = [selected];
  eligible.eligible = [record()];
  save(evidencePath, eligible);
  assert.deepEqual(catalogView(loadCatalog(checkout, {manifest: draft})).recommendations.general, [selected]);

  for (const [field, value] of [
    ['adapter_digest', '0'.repeat(64)], ['dependency_digest', '0'.repeat(64)],
    ['host', 'other'], ['flavor', 'web'], ['boundary_id', processPoint],
    ['content_digest', '0'.repeat(64)], ['source', {...pilot.source, ref: '0'.repeat(40)}],
  ]) {
    save(evidencePath, {...eligible, eligible: [{...record(), [field]: value}]});
    assert.throws(() => loadCatalog(checkout, {manifest: draft}), /independently qualified/i, field);
  }
  save(evidencePath, eligible);
  for (const [key, value] of [
    ['locator', {url: 'https://example.invalid/acquisition-override'}],
    ['url', 'https://example.invalid/acquisition-override'], ['path', '/private/acquisition'],
  ]) {
    save(pilot.descriptor, {...descriptor, [key]: value});
    assert.throws(() => loadCatalog(checkout, {manifest: draft}), /identity|source/i, key);
  }

  descriptor.package_dependencies = [second.id];
  save(pilot.descriptor, descriptor);
  save(evidencePath, {...eligible, eligible: [record()]});
  assert.throws(() => loadCatalog(checkout, {manifest: draft}), /recommendation dependency is unresolved/i);

  pilot.status = 'unqualified';
  draft.recommendations.general = [];
  save(pilot.descriptor, {...descriptor, package_dependencies: ['missing']});
  assert.throws(() => loadCatalog(checkout, {manifest: draft}), /package dependency is unresolved/i);
  save(pilot.descriptor, descriptor);
  save(second.descriptor, {...other, package_dependencies: [pilot.id]});
  assert.throws(() => loadCatalog(checkout, {manifest: draft}), /package dependency is unresolved/i);
});

test('source selection preserves full pins and never restricts custom acquisition', async t => {
  const catalog = loadCatalog(source);
  for (const id of existingDescriptors) {
    const descriptor = load('config/plugins/' + id + '.json');
    const selected = selectSource(catalog, id);
    for (const key of ['source', 'resources', 'dependencies', 'capabilities', 'adapter', 'expectedDigests']) {
      assert.deepEqual(selected[key], descriptor[key], id + ' ' + key);
    }
    assert.deepEqual(selected.package_dependencies, descriptor.package_dependencies ?? []);
    selected.expectedDigests[descriptor.source.entry] = '0'.repeat(64);
    assert.deepEqual(selectSource(catalog, id).expectedDigests, descriptor.expectedDigests);
  }
  assert.throws(() => selectSource(catalog, 'unknown-plugin'), /unknown|select|identity/i);
  assert.equal(sources.normalizeSource('https://github.com/example/unlisted/blob/' + 'a'.repeat(40) + '/SKILL.md').definition.source.kind, 'repository');

  const fixture = setup(t);
  core.install(fixture.root, source, 'general', [{
    name: processOperation, provider: 'codex', rel: '.agents/skills/' + processOperation,
  }]);
  const selected = selectSource(catalog, 'task-interview');
  const acquire = async ({definition}) => ({
    revision: definition.source.ref,
    files: Object.fromEntries(Object.keys(selected.expectedDigests).map(relative => [
      relative,
      fs.readFileSync(path.join(source, 'tests/fixtures/task-processing', relative)),
    ])),
  });
  const request = {request_id: 'catalog-pinned-source', operation: 'install', sources: [selected]};
  const prepared = await lifecycle.prepareProposal(fixture.root, request, {acquire});
  assert.deepEqual(prepared.snapshots['task-interview'].digests, selected.expectedDigests);
  const changed = await acquire({definition: selected});
  changed.files[selected.source.entry] = Buffer.from('# Changed source bytes');
  await assert.rejects(lifecycle.prepareProposal(fixture.root, request, {acquire: async () => changed}), /drift|changed/i);
  assert.equal(fs.existsSync(path.join(fixture.root, registry.REGISTRY)), false);
});

test('known entries merge by identity without changing curated pins or the actual occurrence order', () => {
  const catalog = loadCatalog(source);
  const matching = selectSource(catalog, 'task-editorial');
  const custom = arbitrary('project-extra');
  const initial = catalogView(catalog);
  const actual = [
    occurrence('a-first', 'task-editorial', {anchor: 'after-task-creation'}),
    occurrence('b-middle', 'project-extra', {enabled: false}),
    occurrence('a-last', 'task-editorial', {parameters: {pass: 'last'}}),
    occurrence('actual-only', 'task-editorial', {anchor: 'before'}),
  ];
  const inventory = {status: 'ok', plugins: [
    {id: 'task-editorial', source: matching.source, revision: matching.source.ref, ownership: {status: 'verified'},
      content_digest: manifest.entries.find(row => row.id === 'task-editorial').content_digest},
    {id: 'project-extra', source: custom.source, revision: custom.source.ref, ownership: {status: 'verified'}},
  ], bindings: actual};
  const projectKnown = {
    'task-editorial': known({...matching, expectedDigests: {}}),
    'project-extra': known(custom),
  };
  projectKnown.ponytail = {descriptor: selectSource(catalog, 'ponytail'),
    suggested_locations: [{operation: 'skill-tree-pr-review-cycle', anchor: 'before'}]};
  projectKnown['task-editorial'].suggested_locations.push(
    {operation: processOperation, anchor: 'after-task-creation'},
    {operation: processOperation, anchor: 'during'},
  );
  const merged = catalogView(catalog, {known: projectKnown, inventory});
  assert.equal(merged.entries.length, initial.entries.length + 1);
  assert.equal(merged.entries.filter(row => row.id === 'task-editorial').length, 1);
  assert.deepEqual(selectSource(catalog, 'task-editorial', {known: projectKnown}), matching);
  assert.deepEqual(selectSource(catalog, 'project-extra', {known: projectKnown}), custom);
  assert.deepEqual(groupByPoint(merged, processPoint).bindings.map(row => [row.id, row.enabled]), [
    ['a-first', true], ['b-middle', false], ['a-last', true],
  ]);
  assert.deepEqual(groupByPoint(merged, processPoint).bindings[2].parameters, {pass: 'last'});
  assert.deepEqual(merged.recommendations, noRecommendations);
  assert.equal(entryById(merged, 'task-editorial').installed, 'matching');
  assert.equal(entryById(merged, 'project-extra').installed, 'source-match');
  assert.equal(groupByPoint(merged, processOperation + ':during'), undefined);
  assert.equal(entryById(merged, 'task-editorial').unresolved_locations[0].status, 'unresolved');
  assert.deepEqual(groupByPoint(merged, 'skill-tree-pr-review-cycle:before').suggested, ['ponytail']);
  assert.equal(groupByPoint(merged, processPoint).suggested.filter(id => id === 'task-editorial').length, 1);
  const actualOnly = catalogView(catalog, {known: projectKnown, inventory, point: processOperation + ':before'});
  assert.ok(entryById(actualOnly, 'task-editorial'));
  assert.ok(!actualOnly.groups[0].suggested.includes('task-editorial'));
  assert.deepEqual(actualOnly.groups[0].bindings.map(row => row.id), ['actual-only']);

  const conflict = {'task-editorial': known(arbitrary('task-editorial'))};
  assert.equal(entryById(catalogView(catalog, {known: conflict}), 'task-editorial').known_conflict, true);
  assert.throws(() => selectSource(catalog, 'task-editorial', {known: conflict}), /conflict|identity|different source/i);
});

test('project-known discovery keeps private locators and unresolved input out of public results', () => {
  const catalog = loadCatalog(source);
  const remote = known(arbitrary('remote-custom'));
  remote.descriptor.source.url = 'https://private-user:private-secret@github.com/example/independent-skill?secret=query-secret';
  remote.descriptor.source.ref = '/private/ref-locator';
  remote.locator = {url: 'https://private-acquisition.example/repo'};
  remote.suggested_locations = [{operation: '/private/request-locator', anchor: 'private-anchor'}];
  const local = {
    title: '/private/title-locator',
    definition: {id: 'local-custom', source: {kind: 'local', entry: 'SKILL.md', label: '/private/label-locator', locator_id: 'f'.repeat(64)}},
    locator: {path: '/private/source-locator'},
  };
  const projectKnown = {'remote-custom': remote, 'local-custom': local};
  const view = catalogView(catalog, {known: projectKnown});
  assert.doesNotMatch(JSON.stringify(view), /private|query-secret/);
  assert.equal(entryById(view, 'remote-custom').source.url, 'https://github.com/example/independent-skill');
  assert.equal(entryById(view, 'remote-custom').source.ref, undefined);
  assert.equal(entryById(view, 'remote-custom').unresolved_locations[0].status, 'unresolved');
  assert.deepEqual(selectSource(catalog, 'local-custom', {known: projectKnown}).locator, local.locator);
  const human = formatInventory({status: 'ok', plugins: [], bindings: [], points: [],
    known: {status: 'provided', entries: []}, frozen_requirements: [], issues: [], catalog: view});
  assert.match(human, /Catalog entries without a suggested point/);
  assert.match(human, /remote-custom/);
  assert.doesNotMatch(human, /private|query-secret/);
  local.definition.source.entry = '/private/entry-locator';
  assert.throws(() => catalogView(catalog, {known: projectKnown}), /relative|portable/i);
});

for (const flavor of flavors) test(flavor + ' source and standalone installed catalog listing agree and are read-only', t => {
  const fixture = setup(t);
  for (const relative of Object.keys(composer.sourceInputs(source))) {
    write(fixture.checkout, relative, fs.readFileSync(path.join(source, relative)));
  }
  if (flavor === 'unity') {
    write(fixture.root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2');
    write(fixture.root, 'Packages/manifest.json', '{"dependencies":{"com.unity.test-framework":"1.6.0"}}');
    write(fixture.root, 'Packages/packages-lock.json', '{"dependencies":{"com.unity.test-framework":{"version":"1.6.0"}}}');
  }
  write(fixture.root, 'preserved.txt', 'Project-owned input.');
  write(fixture.temp, 'guard.js', [
    "'use strict';",
    "const deny = () => { throw Error('Read-only catalog attempted network or dispatch'); };",
    "const cp = require('node:child_process'), spawn = cp.spawnSync;",
    "cp.spawnSync = (file, args, options) => file === 'git' && args.includes('rev-parse') ? spawn(file, args, options) : deny();",
    "for (const name of ['exec', 'execFile', 'execFileSync', 'execSync', 'fork', 'spawn']) cp[name] = deny;",
    "global.fetch = deny;",
    "for (const name of ['node:http', 'node:https']) { const client = require(name); client.get = client.request = deny; }",
  ].join('\n'));
  const guard = path.join(fixture.temp, 'guard.js');
  const cli = path.join(source, 'bin/install.js');
  const cliArgs = ['--list-plugins', '--target', fixture.root];
  const beforeFresh = files(fixture.root);
  const fresh = JSON.parse(node(cli, [...cliArgs, '--json'], fixture.separate, guard));
  assert.deepEqual(fresh.plugins, []);
  assert.deepEqual(fresh.catalog.recommendations, noRecommendations);
  assert.deepEqual(files(fixture.root), beforeFresh);

  core.install(fixture.root, fixture.checkout, flavor, [{
    name: processOperation, provider: 'codex', rel: '.agents/skills/' + processOperation,
  }]);
  fs.rmSync(fixture.checkout, {recursive: true});
  const before = files(fixture.root);
  const installed = path.join(fixture.root, '.skill-tree/installation/manager.js');
  const machine = JSON.parse(node(cli, [...cliArgs, '--json'], fixture.separate, guard));
  assert.deepEqual(JSON.parse(node(installed, ['--list-plugins', '--json'], fixture.separate, guard)), machine);
  assert.deepEqual(machine.plugins, []);
  assert.deepEqual(machine.bindings, []);
  assert.equal(machine.registry.present, false);
  assert.deepEqual(machine.catalog.recommendations, noRecommendations);
  assert.ok(machine.catalog.entries.some(row => row.id === 'task-editorial'));
  const human = node(installed, ['--list-plugins', '--group-by', 'point'], fixture.separate, guard);
  assert.equal(human, node(cli, [...cliArgs, '--group-by', 'point'], fixture.separate, guard));
  assert.match(human, /catalog/i);
  assert.match(human, /task-editorial/);
  assert.deepEqual(files(fixture.root), before);
  assert.equal(fs.existsSync(path.join(fixture.root, '.skill-tree/documents/future.json')), false);
});

test('installed catalog survives unreadable registry and isolates drift in its own metadata', async t => {
  const fixture = setup(t);
  core.install(fixture.root, source, 'general', [{
    name: processOperation, provider: 'codex', rel: '.agents/skills/' + processOperation,
  }]);
  const local = ['task-editorial', 'project-extra'].map(id => {
    write(fixture.temp, id + '/SKILL.md', '# Controlled instruction for ' + id);
    return {id, path: path.join(fixture.temp, id)};
  });
  const bindings = [
    occurrence('editor-first', 'task-editorial'),
    occurrence('other-middle', 'project-extra', {enabled: false}),
    occurrence('editor-last', 'task-editorial', {anchor: 'after-task-creation'}),
  ];
  const proposal = await lifecycle.prepareProposal(fixture.root, {
    request_id: 'catalog-installed-separation', operation: 'install', sources: local, bindings,
  });
  lifecycle.applyProposal(fixture.root, proposal, {proposal_digest: proposal.digest});
  core.refresh(fixture.root, source);
  const manager = path.join(fixture.root, '.skill-tree/installation/manager.js');
  function inspect(status) {
    const before = files(fixture.root);
    const run = spawnSync(process.execPath, [manager, '--list-plugins', '--json'], {
      cwd: fixture.separate, encoding: 'utf8', timeout: 30000,
    });
    assert.equal(run.status, status, run.stdout + run.stderr);
    assert.deepEqual(files(fixture.root), before);
    return JSON.parse(run.stdout);
  }

  const intact = inspect(0);
  assert.deepEqual(intact.plugins.map(row => row.id), ['project-extra', 'task-editorial']);
  assert.equal(entryById(intact.catalog, 'task-editorial').installed, 'conflict');
  assert.deepEqual(groupByPoint(intact.catalog, processPoint).bindings.map(row => [row.id, row.enabled]), [
    ['editor-first', true], ['other-middle', false], ['editor-last', true],
  ]);

  const registryPath = path.join(fixture.root, registry.REGISTRY);
  const original = fs.readFileSync(registryPath);
  fs.writeFileSync(registryPath, '{unreadable original');
  const unavailable = inspect(2);
  assert.equal(unavailable.status, 'unavailable');
  assert.equal(unavailable.catalog.status, 'ok');
  assert.equal(entryById(unavailable.catalog, 'task-editorial').installed, 'unknown');

  fs.writeFileSync(registryPath, original);
  write(fixture.root, '.skill-tree/installation/source/config/plugin-catalog.json', '{tampered bundled catalog');
  const drift = inspect(1);
  assert.deepEqual(drift.plugins.map(row => row.id), ['project-extra', 'task-editorial']);
  assert.equal(drift.status, 'drift');
  assert.equal(drift.catalog.status, 'unavailable');
});
