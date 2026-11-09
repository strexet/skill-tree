'use strict';

const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const source = path.resolve(__dirname, '..');
const composer = require('../lib/composer.js');
const core = require('../lib/installation.js');
const lifecycle = require('../lib/plugin-lifecycle.js');
const registry = require('../lib/plugin-registry.js');

const operation = 'skill-tree-plugins';
const catalogFiles = ['config/plugin-catalog.json', 'config/plugin-catalog-eligibility.json'];

function write(root, relative, value) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, value);
}

function json(root, relative, value) {
  write(root, relative, JSON.stringify(value) + '\n');
}

function workspace(t, {flavor = 'general', provider = 'codex', withoutCatalog = false} = {}) {
  const tmp = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-manager-install-')));
  t.after(() => fs.rmSync(tmp, {recursive: true, force: true}));
  const root = path.join(tmp, 'project');
  const recipe = path.join(tmp, 'authoring-copy');
  const cwd = path.join(tmp, 'unrelated-cwd');
  for (const dir of [root, recipe, cwd]) fs.mkdirSync(dir);
  const omitted = new Set(withoutCatalog ? catalogFiles : []);
  for (const relative of Object.keys(composer.sourceInputs(source))) {
    if (!omitted.has(relative)) write(recipe, relative, fs.readFileSync(path.join(source, relative)));
  }
  if (flavor === 'web') json(root, 'package.json', {type: 'module', scripts: {test: 'node --test'}});
  if (flavor === 'unity') {
    write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2\n');
    json(root, 'Packages/manifest.json', {dependencies: {'com.unity.test-framework': '1.6.0'}});
    json(root, 'Packages/packages-lock.json', {dependencies: {'com.unity.test-framework': {version: '1.6.0'}}});
  }
  const directory = provider === 'claude-code' ? '.claude/skills' : '.agents/skills';
  const names = Object.keys(require('../templates/operations.json')).sort();
  const selections = names.map(name => ({provider, name, rel: directory + '/' + name}));
  const manager = path.join(root, directory, operation, 'scripts/plugin-manager.js');
  return {tmp, root, recipe, cwd, manager, directory, names, selections};
}

function cli(f, payload, {guard} = {}) {
  const options = guard ? ['--require', guard] : [];
  return spawnSync(process.execPath, [...options, f.manager, '--project-root', f.root, '--input', '-'], {
    cwd: f.cwd, input: JSON.stringify(payload), encoding: 'utf8', timeout: 30000,
    env: {...process.env, NODE_PATH: ''},
  });
}

function result(run) {
  assert.equal(run.status, 0, run.stdout + run.stderr);
  return JSON.parse(run.stdout);
}

function noWorkflow(f) {
  for (const relative of [
    '.skill-tree/documents/future.md', '.skill-tree/documents/future.json',
    '.skill-tree/invocations', '.skill-tree/decisions', '.skill-tree/clarifications',
  ]) assert.equal(fs.existsSync(path.join(f.root, relative)), false, relative);
}

function guard(f) {
  write(f.tmp, 'guard.cjs', [
    "'use strict';",
    "const deny = () => { throw Error('Inventory attempted network or dispatch'); };",
    "const cp = require('node:child_process'), original = cp.spawnSync;",
    "cp.spawnSync = (file,args,options) => file === 'git' && args.includes('rev-parse') ? original(file,args,options) : deny();",
    "for (const key of ['exec','execFile','execFileSync','execSync','fork','spawn']) cp[key] = deny;",
    "global.fetch = deny;",
    "for (const key of ['node:http','node:https']) { const client = require(key); client.get = client.request = deny; }",
  ].join('\n'));
  return path.join(f.tmp, 'guard.cjs');
}

for (const [flavor, provider] of [['general', 'codex'], ['web', 'codex'], ['unity', 'claude-code']]) {
  test(flavor + ' installs eleven owned operations and runs offline management without the source checkout', t => {
    const f = workspace(t, {flavor, provider});
    const installed = core.install(f.root, f.recipe, flavor, f.selections);
    assert.equal(f.names.length, 11);
    assert.ok(f.names.includes(operation));
    assert.deepEqual(fs.readdirSync(path.join(f.root, f.directory)).sort(), f.names);
    assert.equal(core.verify(f.root, f.recipe).identity, installed.profile.identity);
    assert.equal(core.install(f.root, f.recipe, flavor, f.selections).action, 'verified no-op current');
    fs.rmSync(f.recipe, {recursive: true});
    const before = core.treeHash(f.root, '.skill-tree');
    const view = result(cli(f, {action: 'inventory'}, {guard: guard(f)}));
    assert.deepEqual(view.plugins, []);
    assert.deepEqual(view.bindings, []);
    assert.ok(view.catalog.entries.some(row => row.id === 'task-editorial'));
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
    assert.equal(core.treeHash(f.root, '.skill-tree'), before);
    noWorkflow(f);
  });
}

test('installed manager custom source preview works when optional catalog data is absent', t => {
  const f = workspace(t, {withoutCatalog: true});
  core.install(f.root, f.recipe, 'general', f.selections.filter(item => item.name === operation));
  assert.deepEqual(fs.readdirSync(path.join(f.root, f.directory)), [operation]);
  fs.rmSync(f.recipe, {recursive: true});
  write(f.tmp, 'upstream/SKILL.md', '# Unlisted source\n');
  const original = path.join(f.tmp, 'upstream');
  const view = result(cli(f, {action: 'inventory'}, {guard: guard(f)}));
  assert.deepEqual(view.plugins, []);
  assert.deepEqual(view.catalog.entries, []);
  const before = core.treeHash(f.root, '.skill-tree');
  const prepared = result(cli(f, {action: 'prepare', request: {
    action: 'save-known', request_id: 'save-custom', source: {id: 'custom', path: original},
  }}));
  assert.equal(prepared.status, 'ready');
  assert.match(prepared.proposal.digest, /^[0-9a-f]{64}$/);
  assert.ok(!JSON.stringify(prepared.preview).includes(original));
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  result(cli(f, {action: 'apply', proposal: prepared.proposal, confirmation: {proposal_digest: prepared.proposal.digest}}));
  assert.ok(result(cli(f, {action: 'inventory'})).catalog.entries.some(row => row.id === 'custom'));
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  noWorkflow(f);
});

test('manager rejects executable bundle tampering before importing target code', t => {
  const f = workspace(t);
  core.install(f.root, f.recipe, 'general', f.selections);
  const marker = path.join(f.tmp, 'tampered-module-executed');
  const relative = '.skill-tree/installation/source/lib/plugin-management.js';
  const changed = 'require("node:fs").writeFileSync(' + JSON.stringify(marker) + ', "executed");\n' +
    fs.readFileSync(path.join(f.root, relative), 'utf8');
  write(f.root, relative, changed);
  const view = cli(f, {action: 'inventory'});
  assert.notEqual(view.status, 0);
  assert.match(view.stderr, /ownership|digest|modified|bundle/i);
  assert.equal(fs.existsSync(marker), false);
  noWorkflow(f);
});

test('core-only repeat preserves installed packages and every ordered binding byte', async t => {
  const f = workspace(t, {flavor: 'web'});
  core.install(f.root, f.recipe, 'web', f.selections);
  write(f.tmp, 'upstream/SKILL.md', '# Controlled local instruction\n');
  const bindings = ['first', 'last'].map((id, index) => ({
    id, plugin_id: 'custom', operation, anchor: 'during', enabled: true, parameters: {index},
  }));
  const prepared = await lifecycle.prepareProposal(f.root, {
    request_id: 'fixture-install', operation: 'install', sources: [{id: 'custom', path: path.join(f.tmp, 'upstream')}], bindings,
  });
  lifecycle.applyProposal(f.root, prepared, {proposal_digest: prepared.digest});
  const savedRegistry = fs.readFileSync(path.join(f.root, registry.REGISTRY));
  const savedOwnedPackage = core.treeHash(f.root, registry.PACKAGES);
  core.install(f.root, f.recipe, 'web', f.selections);
  assert.equal(core.install(f.root, f.recipe, 'web', f.selections).action, 'verified no-op current');
  fs.rmSync(f.recipe, {recursive: true});
  fs.rmSync(path.join(f.tmp, 'upstream'), {recursive: true});
  const before = core.treeHash(f.root, '.skill-tree');
  const view = result(cli(f, {action: 'inventory'}, {guard: guard(f)}));
  assert.deepEqual(view.bindings.map(row => [row.id, row.point_position, row.parameters.index]), [
    ['first', 1, 0], ['last', 2, 1],
  ]);
  assert.deepEqual(fs.readFileSync(path.join(f.root, registry.REGISTRY)), savedRegistry);
  assert.equal(core.treeHash(f.root, registry.PACKAGES), savedOwnedPackage);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  noWorkflow(f);

  write(f.root, '.skill-tree/installation/source/' + catalogFiles[0], '{malformed optional catalog');
  const drifted = core.treeHash(f.root, '.skill-tree');
  const readable = result(cli(f, {action: 'inventory'}, {guard: guard(f)}));
  assert.deepEqual(readable.bindings.map(row => row.id), ['first', 'last']);
  assert.equal(readable.catalog.status, 'unavailable');
  const refused = cli(f, {action: 'prepare', request: {
    action: 'move', request_id: 'ownership-blocks-mutation', binding_id: 'last', index: 0,
  }});
  assert.notEqual(refused.status, 0);
  assert.match(refused.stderr, /ownership|bundle|digest/i);
  assert.equal(core.treeHash(f.root, '.skill-tree'), drifted);
});
