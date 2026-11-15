'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const test = require('node:test');

const cli = path.resolve(__dirname, '../bin/install.js');
const manager = '.agents/skills/skill-tree-plugins/scripts/plugin-manager.js';
const defaults = ['direct-replacement', 'network-polling'];

function run(args, input) {
  const result = spawnSync(process.execPath, args, {encoding: 'utf8', input, timeout: 20000});
  assert.equal(result.status, 0, result.stderr + result.stdout);
  return result.stdout;
}

function install(root, flavor, ...args) {
  return run([cli, '--target', root, '--only', 'codex', '--flavor', flavor,
    '--skills', 'skill-tree-plugins', '--skills', 'skill-tree-pr-review-cycle', '--non-interactive', ...args]);
}

function inspect(root, request = {action: 'inventory'}) {
  return JSON.parse(run([path.join(root, manager), '--project-root', root, '--input', '-'],
    JSON.stringify(request)));
}

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-policies-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  return root;
}

for (const flavor of ['general', 'web', 'unity']) {
  test(flavor + ' enables both owned policies offline and preserves independent choices', t => {
    const root = fixture(t);
    if (flavor === 'unity') {
      fs.mkdirSync(path.join(root, 'ProjectSettings'));
      fs.writeFileSync(path.join(root, 'ProjectSettings/ProjectVersion.txt'), 'm_EditorVersion: 6000.0.1f1\n');
    }
    fs.writeFileSync(path.join(root, 'AGENTS.md'), '# Owner rules\n');
    install(root, flavor, '--with-init');
    const view = inspect(root);
    assert.deepEqual(view.built_in_policies.filter(item => item.enabled).map(item => item.id), defaults);
    assert.deepEqual(view.plugins, []);
    const bridge = () => fs.readFileSync(path.join(root, 'AGENTS.md'), 'utf8');
    assert.match(bridge(), /direct-replacement/);
    assert.match(bridge(), /network-polling/);
    inspect(root, {action: 'set-builtin', policy: 'direct-replacement', enabled: false});
    install(root, flavor === 'web' ? 'general' : 'web');
    run([path.join(root, '.skill-tree/installation/manager.js'), '--refresh-profile']);
    assert.deepEqual(inspect(root).built_in_policies.filter(item => item.enabled).map(item => item.id), ['network-polling']);
    assert.doesNotMatch(bridge(), /direct-replacement/);
    assert.match(bridge(), /network-polling/);
    assert.match(bridge(), /# Owner rules/);
    inspect(root, {action: 'set-builtin', policy: 'direct-replacement', enabled: true});
    assert.deepEqual(inspect(root).built_in_policies.filter(item => item.enabled).map(item => item.id), defaults);
  });
}

test('repeat installation of a project without an explicit preference composes the defaults', t => {
  const root = fixture(t);
  install(root, 'general');
  assert.equal(fs.existsSync(path.join(root, '.skill-tree/development-policies.json')), false);
  const output = install(root, 'general', '--with-init');
  assert.doesNotMatch(output, /activate both|compatibility warning/i);
  assert.deepEqual(inspect(root).built_in_policies.filter(item => item.enabled).map(item => item.id), defaults);
});
