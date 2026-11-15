'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const test = require('node:test');

const core = path.resolve(__dirname, '..');

function exec(command, args, root, input) {
  return spawnSync(command, args, {cwd: root, input, encoding: 'utf8', timeout: 20000});
}

function git(root, ...args) {
  const result = exec('git', ['-c', 'commit.gpgSign=false', '-c', 'tag.gpgSign=false', ...args], root);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}

function write(root, name, value) {
  const file = path.join(root, name);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, JSON.stringify(value, null, 2) + '\n');
}

function api() {
  const operation = reference => ({responses: {'200': {description: 'OK', content: {
    'application/json': {schema: {$ref: reference}}
  }}}});
  return {
    openapi: '3.1.0',
    paths: {'/items': {get: operation('#/components/schemas/Item')}, '/notes': {get: operation('#/components/schemas/Note')}},
    components: {schemas: {Item: {type: 'string'}, Note: {type: 'string'}}}
  };
}

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-locks-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  git(root, 'init', '-q');
  git(root, 'config', 'user.name', 'API lock fixture');
  git(root, 'config', 'user.email', 'fixture@example.invalid');
  write(root, 'openapi.json', api());
  write(root, '.skill-tree/api-contracts.json', {
    schema: 1,
    contracts: {items: {openapi: 'openapi.json', operation: 'GET /items', checks: ['contract-items']}},
    sets: {'public-api': ['items']}
  });
  git(root, 'add', '.');
  git(root, 'commit', '-qm', 'API baseline');
  git(root, 'tag', 'api-v1');
  const install = exec(process.execPath, [path.join(core, 'bin/install.js'), '--only', 'codex',
    '--target', root, '--flavor', 'general', '--skills', 'skill-tree-plugins', '--non-interactive'], root);
  assert.equal(install.status, 0, install.stderr);
  return root;
}

function manager(root, ...args) {
  return exec(process.execPath, ['.skill-tree/installation/manager.js', ...args], root);
}

function report(result) {
  assert.equal(result.status, 0, result.stderr + result.stdout);
  return JSON.parse(result.stdout);
}

test('first lock attaches one reviewer, partial unlock preserves overlaps and last unlock removes it', t => {
  const root = fixture(t);
  assert.equal(report(manager(root, 'lock-api', 'items')).reviewer.action, 'attached');
  assert.equal(report(manager(root, 'lock-api', 'public-api', '--baseline', 'api-v1')).reviewer.action, 'updated');
  const tool = '.agents/skills/skill-tree-plugins/scripts/plugin-manager.js';
  const read = request => exec(process.execPath,[tool,'--project-root',root,'--input','-'],root,JSON.stringify(request));
  assert.equal(report(read({action: 'inventory'})).managed_review_plugin.managed_by, 'lock-api');
  assert.match(read({action: 'set-builtin', policy: 'api-lock-review', enabled: false}).stderr, /unlock-api/);
  assert.equal(report(manager(root, 'unlock-api', 'items')).reviewer.action, 'updated');
  assert.deepEqual(report(read({action: 'inventory'})).managed_review_plugin.locks, ['public-api']);
  assert.equal(report(manager(root, 'unlock-api', 'public-api')).reviewer.action, 'removed');
  assert.equal(report(read({action: 'inventory'})).managed_review_plugin, null);
});

test('only changes to the exact selected operation require an explicit committed baseline', t => {
  const root = fixture(t);
  const doc = api();
  doc.components.schemas.Note.type = 'integer';
  write(root, 'openapi.json', doc);
  assert.equal(report(manager(root, 'lock-api', 'items')).reviewer.action, 'attached');
  report(manager(root, 'unlock-api', 'items'));
  doc.components.schemas.Item.type = 'integer';
  write(root, 'openapi.json', doc);
  const rejected = manager(root, 'lock-api', 'items');
  assert.notEqual(rejected.status, 0);
  assert.match(rejected.stderr, /uncommitted.*contract/i);
  assert.equal(report(manager(root, 'lock-api', 'items', '--baseline', 'api-v1')).reviewer.action, 'attached');
});

test('the review-stage adapter reads the exact candidate and requires current contract checks', t => {
  const root = fixture(t);
  const base = git(root, 'rev-parse', 'HEAD');
  report(manager(root, 'lock-api', 'items'));
  const doc = api();
  doc.components.schemas.Note.type = 'integer';
  write(root, 'openapi.json', doc);
  git(root, 'add', 'openapi.json');
  git(root, 'commit', '-qm', 'Unrelated operation');
  const changed = {head: git(root,'rev-parse','HEAD'), base_oid:base, changed_files:['openapi.json'], checks:[]};
  const library = path.join(core, 'lib/api-contract-locks.js');
  const review = value => exec(process.execPath, [library, 'review', root], root, JSON.stringify(value));
  assert.deepEqual(report(review(changed)).affected, []);
  doc.components.schemas.Item.type = 'integer';
  write(root, 'openapi.json', doc);
  git(root, 'add', 'openapi.json');
  git(root, 'commit', '-qm', 'Change protected response type');
  const breaking = review({...changed,head:git(root,'rev-parse','HEAD'),
    checks:[{name:'contract-items',status:'success'}]});
  assert.equal(breaking.status, 2);
  assert.match(breaking.stdout, /Protected OpenAPI operation changed/);
  fs.writeFileSync(path.join(root, 'openapi.json'), JSON.stringify(api()));
  assert.equal(review({...changed,head:git(root,'rev-parse','HEAD')}).status, 2);
});

test('owner-declared contracts require their exact check when a declared input changes', t => {
  const root = fixture(t);
  fs.writeFileSync(path.join(root, 'sdk.txt'), 'stable public surface');
  write(root, '.skill-tree/api-contracts.json', {
    schema: 1, contracts: {sdk: {file:'sdk.txt',checks:['sdk-compat'],consumers:['downstream-sdk']}}
  });
  git(root, 'add', 'sdk.txt', '.skill-tree/api-contracts.json');
  git(root, 'commit', '-qm', 'Declare the SDK contract');
  const base=git(root,'rev-parse','HEAD');
  const contractFile = path.join(root, 'sdk.txt');
  fs.appendFileSync(contractFile, '\nnew public member');
  const rejected = manager(root, 'lock-api', 'sdk');
  assert.equal(rejected.status, 2);
  assert.match(rejected.stderr, /Working copy: new public member/);
  fs.writeFileSync(contractFile, 'stable public surface');
  report(manager(root, 'lock-api', 'sdk'));
  fs.writeFileSync(path.join(root, 'sdk.txt'), 'current public surface\n');
  git(root, 'add', 'sdk.txt');
  git(root, 'commit', '-qm', 'Change the SDK surface');
  const snapshot={head:git(root,'rev-parse','HEAD'),base_oid:base,changed_files:['sdk.txt'],checks:[]};
  const library=path.join(core,'lib/api-contract-locks.js');
  const review = value => exec(process.execPath,[library,'review',root],root,JSON.stringify(value));
  assert.match(review(snapshot).stdout,/Missing current successful API contract check: sdk-compat/);
  snapshot.checks=[{name:'sdk-compat',status:'success'}];
  assert.deepEqual(report(review(snapshot)).affected,['sdk (sdk.txt)']);
  assert.deepEqual(report(manager(root,'unlock-api','--all')).known_consumers,['downstream-sdk']);
});

test('a lock committed on the target after branching still protects a renamed contract from an older candidate', t => {
  const root = fixture(t);
  const ancestor = git(root, 'rev-parse', 'HEAD');
  report(manager(root, 'lock-api', 'items'));
  git(root, 'add', '.skill-tree/development-policies.json');
  git(root, 'commit', '-qm', 'Pin items on target');
  const base = git(root, 'rev-parse', 'HEAD');
  report(manager(root, 'unlock-api', 'items'));
  git(root, 'checkout', '--detach', '--force', ancestor);
  report(manager(root, '--refresh-profile'));
  git(root, 'mv', 'openapi.json', 'renamed.json');
  git(root, 'commit', '-qm', 'Rename protected document');
  const snapshot = {head: git(root, 'rev-parse', 'HEAD'), base_oid: base, changed_files: ['renamed.json'],
    candidate_objects_required: true, checks: []};
  const library = path.join(core, 'lib/api-contract-locks.js');
  const renamed = exec(process.execPath, [library, 'review', root], root, JSON.stringify(snapshot));
  assert.equal(renamed.status, 2);
  assert.match(renamed.stdout, /items \(GET \/items\).*Required Git object/);
  assert.match(exec(process.execPath, [library, 'review', root], root,
    JSON.stringify({...snapshot, base_oid: '0'.repeat(40)})).stderr, /current Git head and base/);
});

test('a candidate can commit an explicit unlock of an inherited policy and must match the reviewed configuration', t => {
  const root = fixture(t);
  report(manager(root, 'lock-api', 'items'));
  git(root, 'add', '.skill-tree/development-policies.json');
  git(root, 'commit', '-qm', 'Record inherited lock');
  const base = git(root, 'rev-parse', 'HEAD');
  report(manager(root, 'unlock-api', 'items'));
  const changed = api();
  changed.components.schemas.Item.type = 'integer';
  write(root, 'openapi.json', changed);
  git(root, 'add', 'openapi.json', '.skill-tree/development-policies.json');
  git(root, 'commit', '-qm', 'Explicitly unlock and change the API');
  const snapshot = {head: git(root, 'rev-parse', 'HEAD'), base_oid: base,
    changed_files: ['openapi.json', '.skill-tree/development-policies.json'], checks: []};
  const library = path.join(core, 'lib/api-contract-locks.js');
  const review = () => exec(process.execPath, [library, 'review', root], root, JSON.stringify(snapshot));
  assert.equal(report(review()).reviewer, null);
  report(manager(root, 'lock-api', 'items', '--baseline', base));
  assert.match(review().stderr, /configuration from the current candidate/);
});

test('the adapter preserves literal names and rejects unsupported numeric precision', t => {
  const root = fixture(t);
  const doc = api();
  doc.components.schemas.Item = {type: 'object', properties: {$id: {type: 'string'}}};
  doc.paths['/items'].get.responses['200'].content['application/json'].example = {$ref: 'text', $id: 'example'};
  write(root, 'openapi.json', doc);
  git(root, 'add', 'openapi.json');
  git(root, 'commit', '-qm', 'Use literal reserved-looking properties');
  report(manager(root, 'lock-api', 'items'));
  const base = git(root, 'rev-parse', 'HEAD');
  const file = path.join(root, 'openapi.json');
  doc.components.schemas.Note.maximum = 'BOUND';
  fs.writeFileSync(file, JSON.stringify(doc).replace('"BOUND"', '9223372036854775807'));
  git(root, 'add', 'openapi.json');
  git(root, 'commit', '-qm', 'Declare an exact int64 bound for an unrelated operation');
  const library = path.join(core, 'lib/api-contract-locks.js');
  const snapshot = {head: git(root, 'rev-parse', 'HEAD'), base_oid: base, changed_files: ['openapi.json']};
  assert.deepEqual(report(exec(process.execPath, [library, 'review', root], root, JSON.stringify(snapshot))).affected, []);
  report(manager(root, 'unlock-api', 'items'));
  delete doc.components.schemas.Note.maximum;
  doc.components.schemas.Item.maximum = 'BOUND';
  fs.writeFileSync(file, JSON.stringify(doc).replace('"BOUND"', '9007199254740993'));
  git(root, 'add', 'openapi.json');
  git(root, 'commit', '-qm', 'Declare an unsafe bound');
  assert.match(manager(root, 'lock-api', 'items').stderr, /lossless JavaScript precision/);
});

test('raw byte and explicit input changes require an explicit baseline', t => {
  const root = fixture(t);
  const binary = path.join(root, 'contract.bin');
  fs.writeFileSync(binary, Buffer.from([0x80]));
  fs.writeFileSync(path.join(root, 'source.js'), 'old line\n');
  write(root, '.skill-tree/api-contracts.json', {schema: 1, contracts: {
    raw: {file: 'contract.bin', checks: ['contract-byte-check'], inputs: ['source.js']}
  }});
  git(root, 'add', 'contract.bin', 'source.js', '.skill-tree/api-contracts.json');
  git(root, 'commit', '-qm', 'Declare binary contract and implementation input');
  fs.writeFileSync(binary, Buffer.from([0x81]));
  assert.match(manager(root, 'lock-api', 'raw').stderr, /Contract bytes differ/);
  fs.writeFileSync(binary, Buffer.from([0x80]));
  fs.writeFileSync(path.join(root, 'source.js'), 'new line\n');
  assert.match(manager(root, 'lock-api', 'raw').stderr, /source\.js.*new line/);
  report(manager(root, 'lock-api', 'raw', '--baseline', 'HEAD'));
});

test('a configured repository remote requires both candidate objects even when a normalized snapshot omits the flag', t => {
  const root = fixture(t);
  git(root, 'remote', 'add', 'origin', 'https://example.invalid/test-repository');
  const library = path.join(core, 'lib/api-contract-locks.js');
  const snapshot = {head: git(root, 'rev-parse', 'HEAD'), base_oid: '0'.repeat(40), changed_files: ['openapi.json']};
  const rejected = exec(process.execPath, [library, 'review', root], root, JSON.stringify(snapshot));
  assert.equal(rejected.status, 2);
  assert.match(rejected.stderr, /current Git head and base/);
});
