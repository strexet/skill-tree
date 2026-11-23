'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const installer = require('../bin/install.js');
const core = require('../lib/installation.js');

const source = path.resolve(__dirname, '..');
const cli = path.join(source, 'bin/install.js');
const operation = 'skill-tree-director-setup';
const matrix = installer.loadProviders();
function project(t) {
  const directory = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'installation-host-')));
  t.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  return directory;
}
function run(root, ...flags) {
  return spawnSync(process.execPath, [cli, '--non-interactive', '--target', root, '--flavor', 'director',
    '--skills', operation, ...flags], {encoding: 'utf8', timeout: 60000});
}
function pass(result) {
  assert.equal(result.status, 0, result.stderr + result.stdout);
  return result.stdout;
}
function read(root, name) { return fs.readFileSync(path.join(root, name), 'utf8'); }

test('explicit clients resolve before writing and complete selections remain available', t => {
  const root = project(t);
  for (const [args, message] of [
    [['--all','--only','dsh'], /mutually exclusive/],
    [['--all','--only','typo'], /mutually exclusive/],
    [['--only','codex','--only','typo'], /unknown provider.*--list/],
    [['--agent','codex'], /unsupported.*--only/],
  ]) {
    const result = run(root, ...args);
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, message);
    assert.deepEqual(fs.readdirSync(root), []);
  }
  const all = pass(run(root, '--all', '--dry-run'));
  assert.equal((all.match(/"ok": true/g) || []).length, matrix.providers.filter(provider => !provider.soft).length);
  assert.deepEqual(fs.readdirSync(root), []);
  pass(run(root, '--only', 'claude-code', '--only', 'deepseek', '--only','dsh'));
  const receipt = core.receipt(root, true);
  assert.deepEqual(receipt.destinations['.agents/skills/' + operation].providers, ['dsh']);
  assert.deepEqual(receipt.destinations['.claude/skills/' + operation].providers, ['claude-code']);
  assert.match(read(root, '.agents/skills/' + operation + '/SKILL.md'), /^---\nname: skill-tree-director-setup\n/);
  pass(run(root, '--only','dsh','--verify'));
});

test('standalone client probes recognize executable identities without executing them', t => {
  const root = project(t);
  const bin = path.join(root,'bin'), versions = path.join(root,'versions');
  fs.mkdirSync(bin); fs.mkdirSync(versions);
  const env = {PATH:bin};
  const cursor = matrix.providers.find(row => row.id === 'cursor');
  const copilot = matrix.providers.find(row => row.id === 'github-copilot');
  const probe = row => row.detect.some(item => item.kind === 'command' && installer.detectProbe(item,env,root));
  const binary = name => path.join(bin, name + (process.platform === 'win32' ? '.exe' : ''));
  const writeExecutable = file => fs.writeFileSync(file, '#!/bin/sh\nexit 1\n', {mode:0o755});
  writeExecutable(binary('agent'));
  assert.equal(probe(cursor),false);
  writeExecutable(binary('copilot'));
  assert.equal(probe(copilot),true);
  fs.unlinkSync(binary('agent'));
  if (process.platform !== 'win32') {
    const real = path.join(versions,'cursor-agent');
    writeExecutable(real); fs.symlinkSync(real, binary('agent'));
    assert.equal(probe(cursor),true);
    fs.unlinkSync(binary('agent')); fs.chmodSync(binary('copilot'),0o600);
    assert.equal(probe(copilot),false);
  }
  writeExecutable(binary('cursor-agent'));
  assert.equal(probe(cursor),true);
  const extensions = path.join(root,'.vscode/extensions/github.copilot-chat-1.2');
  fs.mkdirSync(extensions, {recursive:true});
  assert.ok(copilot.detect.filter(item => item.kind === 'vscode-extension').some(item => installer.detectProbe(item,env,root)));
});

test('OpenCode upgrades the owned legacy instructions and shares root rules with Codex', t => {
  const root = project(t), legacy = '.opencode/AGENTS.md', base = '.agents/skills/' + operation;
  fs.mkdirSync(path.join(root,'.opencode'));
  fs.writeFileSync(path.join(root,legacy), '# Legacy owner text\n');
  fs.writeFileSync(path.join(root,'AGENTS.md'), '# Current owner text\n');
  core.install(root, source, 'director', [{name:operation, provider:'opencode', rel:base}],
    {provider:'opencode', bridges:[legacy]});
  pass(run(root,'--only','opencode','--with-init','--dry-run'));
  assert.match(read(root,legacy), /BEGIN skill-tree-skills/);
  pass(run(root,'--only','opencode','--with-init'));
  const receipt = core.receipt(root, true);
  assert.deepEqual(Object.keys(receipt.bridges), ['AGENTS.md']);
  assert.deepEqual(receipt.bridges['AGENTS.md'].providers,['opencode']);
  assert.match(read(root,'AGENTS.md'), /^# Current owner text\n/);
  assert.ok(!read(root,legacy).includes('BEGIN skill-tree-skills'));
  assert.match(read(root,legacy), /^# Legacy owner text\n/);
  pass(run(root,'--only','opencode','--with-init'));
  pass(run(root,'--only','codex','--with-init'));
  assert.deepEqual(core.receipt(root,true).bridges['AGENTS.md'].providers,['codex','opencode']);
  pass(run(root,'--only','opencode','--with-init','--uninstall'));
  assert.match(read(root,'AGENTS.md'),/BEGIN skill-tree-skills/);
  assert.deepEqual(core.receipt(root,true).bridges['AGENTS.md'].providers,['codex']);
  pass(run(root,'--only','codex','--with-init','--uninstall'));
  assert.match(read(root,'AGENTS.md'), /^# Current owner text\n/);
  assert.ok(!read(root,'AGENTS.md').includes('BEGIN skill-tree-skills'));
});
