'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-policy-review-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  function run(command, args, input) {
    const result = spawnSync(command, args, {cwd: root, input, encoding: 'utf8', timeout: 20000});
    assert.equal(result.status, 0, result.stderr + result.stdout);
    return result.stdout.trim();
  }
  const git = (...args) => run('git', ['-c', 'commit.gpgSign=false', ...args]);
  const write = (file, contents) => fs.writeFileSync(path.join(root, file), contents);
  function commit(contents) {
    write('app.js', contents);
    git('add', 'app.js');
    git('commit', '-qm', 'fixture change');
    return git('rev-parse', 'HEAD');
  }
  git('init', '-q');
  git('config', 'user.email', 'fixture@example.invalid');
  git('config', 'user.name', 'Fixture');
  const base = commit('module.exports = function app(state) { return state.old(); };\n');
  const skills = '.agents/skills';
  run(process.execPath, [path.resolve(__dirname, '../bin/install.js'), '--target', root, '--flavor',
    'general', '--only', 'codex', '--non-interactive', '--with-init', '--skills', 'skill-tree-plugins',
    '--skills', 'skill-tree-pr-review-cycle', '--skills', 'skill-tree-implement-next-future-task']);
  const manager = (...args) => JSON.parse(run(process.execPath, ['.skill-tree/installation/manager.js', ...args]));
  const intent = id => fs.readFileSync(path.join(root, skills, id, 'SKILL.md'), 'utf8');
  function toggle(id, enabled) {
    run(process.execPath, [path.join(skills, 'skill-tree-plugins/scripts/plugin-manager.js'),
      '--project-root', root, '--input', '-'], JSON.stringify({action: 'set-builtin', policy: id, enabled}));
  }
  function review(head, observations, previous = null, findings = [], extra = {}) {
    return JSON.parse(run('python3', ['-B', path.join(__dirname, 'development-policy-review-fixture.py')],
      JSON.stringify({head, base, observations, previous, findings, ...extra})));
  }
  return {root, git, write, commit, intent, toggle, review, manager};
}

function finding(policy, source, cause, consequence) {
  return {policy, outcome: 'violation', id: 'active-path', path: 'app.js', line: 1,
    source_line: source, cause, consequence, severity: 'P1'};
}

module.exports = {fixture, finding};
