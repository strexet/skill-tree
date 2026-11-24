'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const {pathToFileURL} = require('node:url');
const test = require('node:test');

const source = path.join(__dirname, '..');
const profile = '.skill-tree/installation/profile.json';
const future = '.skill-tree/documents/future.json';
const launcher = '.agents/skills/skill-tree-director/SKILL.md';

function run(cwd, command, ...args) {
  const result = spawnSync(command, args, {cwd, encoding: 'utf8', timeout: 180000});
  if (result.status !== 0) throw Error((result.error?.message || '') + result.stdout + result.stderr);
  return result.stdout.trim();
}

test('the Director installer relocates a registered legacy workspace and its dirty linked maintenance worktree', t => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-relocation-')));
  t.after(() => fs.rmSync(base, {recursive: true, force: true}));
  const product = path.join(base, 'product'), seed = path.join(base, 'seed');
  const old = path.join(product, '.skill-tree-director'), home = path.join(product, '.skill-tree/.director');
  const bundle = path.join(base, 'fixture-source');
  const read = (root, relative) => fs.readFileSync(path.join(root, relative));
  const json = (root, relative) => JSON.parse(read(root, relative));
  const write = (root, relative, value) => {
    const file = path.join(root, relative);
    fs.mkdirSync(path.dirname(file), {recursive: true});
    fs.writeFileSync(file, value);
  };
  const git = (root, ...args) => run(root, 'git', ...args);
  const init = (root, branch) => {
    fs.mkdirSync(root);
    git(root, 'init', '-qb', branch);
  };
  const commit = root => {
    git(root, 'add', '.');
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@invalid.test', 'commit', '-qm', 'Fixture');
  };
  const install = (root, ...args) => run(root, process.execPath, path.join(source, 'bin/install.js'),
    '--target', root, '--only', 'codex', '--source', bundle, ...args);
  const setup = (root, command, data) => {
    const input = path.join(base, 'setup.json');
    const args = ['-B', path.join(root, json(root, 'workspace.json').setup_entry), command, root];
    if (data) {
      fs.writeFileSync(input, JSON.stringify(data));
      args.push('--input', input);
    }
    return JSON.parse(run(product, 'python3', ...args));
  };
  init(seed, 'develop');
  write(seed, '.skill-tree/config/repository.json', '{"schema":1,"role":"source"}');
  write(seed, '.skill-tree/documents/future.md',
    '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  write(seed, 'README.md', 'Original source\n');
  commit(seed);
  fs.mkdirSync(bundle);
  for (const name of ['common', 'config', 'domains', 'lib', 'src', 'templates', 'tests/fixtures/director']) {
    fs.cpSync(path.join(source, name), path.join(bundle, name), {recursive: true});
  }
  const upstream = "UPSTREAM = 'https://github.com/strexet/skill-tree.git'";
  const maintenance = 'common/scripts/director-maintenance.py';
  const configured = read(bundle, maintenance).toString().replace(upstream, `UPSTREAM = '${pathToFileURL(seed).href}'`);
  assert.notEqual(configured, read(bundle, maintenance).toString());
  write(bundle, maintenance, configured);
  const workflow = 'common/scripts/workflow-state.py';
  const currentGuard = read(bundle, workflow);
  const pathSelection = "homes = [store.source_root / '.skill-tree/.director', store.source_root / '.skill-tree-director']";
  assert.ok(currentGuard.toString().includes(pathSelection));
  const priorGuard = currentGuard.toString().replace('SHARED_WORKSPACE_ROUTING = 2', 'SHARED_WORKSPACE_ROUTING = 1')
    .replace(pathSelection, "homes = [store.root / '.skill-tree-director']");
  assert.notEqual(currentGuard.toString(), priorGuard);
  write(bundle, workflow, priorGuard);
  const initRules = 'src/init-rules/skill-tree-skills.md';
  const currentRules = read(bundle, initRules);
  const oldRules = currentRules.toString().replace('`.skill-tree/.director`', '`.skill-tree-director`');
  assert.notEqual(currentRules.toString(), oldRules);
  write(bundle, initRules, oldRules);

  init(product, 'main');
  write(product, 'index.html', '<!doctype html>');
  commit(product);
  fs.mkdirSync(old);
  install(old, '--project', '--flavor', 'director');
  write(old, 'workspace.json', JSON.stringify({schema: 1, kind: 'director-workspace', providers: ['codex'],
    setup_entry: '.agents/skills/skill-tree-director-setup/scripts/director-entry.py'}));
  write(product, launcher, read(source, 'tests/fixtures/director/legacy-workspace-launcher.md'));
  setup(old, 'project-init');
  const choice = {name: 'site', kind: 'existing', path: product};
  const registered = setup(old, 'project-setup', choice);
  const projectRules = 'Project instructions from its owner.\n';
  write(product, 'AGENTS.md', projectRules);
  install(product, '--project', '--flavor', 'web', '--with-init');
  const oldProfile = json(product, profile);
  const linked = path.join(old, 'sources/projects/site');
  const repository = path.join(old, 'sources/skill-tree');
  install(repository, '--project', '--flavor', 'general');
  write(linked, 'README.md', 'Staged maintenance edit\n');
  git(linked, 'add', 'README.md');
  write(linked, 'notes.txt', 'Untracked maintenance notes\n');
  write(old, 'owned-note.txt', 'Retained Director work\n');
  const before = {
    state: read(old, future), child: read(product, future), source: read(repository, future),
    sourceRefs: git(repository, 'show-ref'), productHead: git(product, 'rev-parse', 'HEAD'),
    sourceGit: fs.statSync(path.join(repository, '.git')).ino, homeGit: fs.statSync(path.join(old, '.git')).ino,
    linkedStatus: git(linked, 'status', '--porcelain'), linkedHead: git(linked, 'rev-parse', 'HEAD'),
    exclude: read(product, '.git/info/exclude'),
  };
  write(bundle, workflow, currentGuard);
  write(bundle, initRules, currentRules);
  const update = (...args) => install(product, '--flavor', 'director', ...args);
  const coreIntake = () => {
    const request = path.join(base, 'intake.json');
    fs.writeFileSync(request, JSON.stringify({title: 'Preview rejection', description: 'Read this project.',
      expected_behavior: 'Keep the project queue unchanged.'}));
    return run(product, 'python3', '-B', path.join(product,
      '.agents/skills/skill-tree-add-pending-task/scripts/workflow-state.py'),
    'intake', product, '--standalone', '--input', request);
  };
  assert.match(update('--dry-run'), /move the retained Director workspace/);
  assert.equal(fs.existsSync(home), false);
  assert.deepEqual(read(product, '.git/info/exclude'), before.exclude);

  write(home, 'foreign.txt', 'Preserve conflict\n');
  assert.throws(() => update(), /conflicting Director storage/);
  assert.equal(read(home, 'foreign.txt').toString(), 'Preserve conflict\n');
  fs.rmSync(home, {recursive: true});
  git(product, 'add', '-f', '.skill-tree-director');
  const trackedOld = git(product, 'ls-files', '-s');
  assert.throws(() => update(), /Legacy Director storage overlaps tracked product files/);
  assert.equal(git(product, 'ls-files', '-s'), trackedOld);
  assert.deepEqual(read(product, '.git/info/exclude'), before.exclude);
  assert.deepEqual(read(old, future), before.state);
  assert.equal(fs.existsSync(home), false);
  git(product, 'reset', '--', '.skill-tree-director');
  const maintainedSkill = '.agents/skills/skill-tree-add-pending-task/SKILL.md';
  const ownedBytes = read(repository, maintainedSkill);
  write(repository, maintainedSkill, Buffer.concat([ownedBytes, Buffer.from('Local package edit\n')]));
  assert.throws(() => update(), /Unowned or locally modified package conflicts/);
  assert.match(read(repository, maintainedSkill).toString(), /Local package edit/);
  assert.deepEqual(read(product, '.git/info/exclude'), before.exclude);
  assert.equal(fs.existsSync(home), false);
  write(repository, maintainedSkill, ownedBytes);
  write(old, '.skill-tree/.transaction.json', '{}');
  assert.throws(() => update(), /Finish or recover the existing operation/);
  assert.equal(fs.existsSync(home), false);
  assert.deepEqual(read(old, future), before.state);
  fs.unlinkSync(path.join(old, '.skill-tree/.transaction.json'));
  const question = '.skill-tree/director/runs/dr-df35a3e9-20a7-4201-adef-9c88cd1a52cc.json';
  write(old, question, JSON.stringify({assignments: {site: {dispatches: {}, questions: {q: {phase: 'answer-recorded'}}}}}));
  assert.throws(() => update(), /Reconcile the in-flight Director question delivery/);
  assert.equal(fs.existsSync(home), false);
  fs.unlinkSync(path.join(old, question));

  if (process.platform !== 'win32') {
    const injector = path.join(base, 'interrupt.py');
    fs.writeFileSync(injector, [
      'import os, runpy, sys',
      'from pathlib import Path',
      'rename = Path.rename',
      'def interrupted(source, destination):',
      '    result = rename(source, destination)',
      "    if source.name == '.skill-tree-director' and destination.name == '.director':",
      "        os.write(2, b'Interrupted after relocation')",
      '        os._exit(1)',
      '    return result',
      'Path.rename = interrupted',
      'sys.argv = sys.argv[1:]',
      "runpy.run_path(sys.argv[0], run_name='__main__')",
      ''
    ].join('\n'));
    const wrapper = path.join(base, 'interrupt-after-move');
    fs.writeFileSync(wrapper, [
      '#!/bin/sh',
      'if [ "$3" = move ]; then exec python3 "$(dirname "$0")/interrupt.py" "$2" "$3" "$4"; fi',
      'exec python3 "$@"',
      ''
    ].join('\n'), {mode: 0o755});
    const python = process.env.PYTHON;
    process.env.PYTHON = wrapper;
    try {
      assert.throws(() => update(), /Interrupted after relocation/);
      assert.equal(fs.existsSync(old), false);
      const journal = json(home, '.director-relocation.json');
      const owner = json(home, '.skill-tree/.writer-lock');
      assert.equal(owner.relocation_id, journal.relocation_id);
      assert.equal(owner.host, os.hostname());
      assert.ok(owner.pid > 0);
      assert.throws(coreIntake, /Finish the retained Director storage migration/);
      assert.deepEqual(read(home, future), before.state);
      assert.deepEqual(read(product, future), before.child);
    } finally {
      if (python === undefined) delete process.env.PYTHON;
      else process.env.PYTHON = python;
    }
  }
  assert.match(update(), /Director ready/);
  const rules = read(product, 'AGENTS.md').toString();
  assert.ok(rules.startsWith(projectRules));
  assert.match(rules, /BEGIN skill-tree-skills/);
  assert.match(rules, /BEGIN skill-tree-director-routing/);
  assert.equal(fs.existsSync(old), false);
  assert.equal(fs.existsSync(path.join(home, '.director-relocation.json')), false);
  assert.equal(fs.existsSync(path.join(home, '.skill-tree/.writer-lock')), false);
  const sourceNow = path.join(home, 'sources/skill-tree');
  const linkedNow = path.join(home, 'sources/projects/site');
  assert.equal(fs.statSync(path.join(home, '.git')).ino, before.homeGit);
  assert.equal(fs.statSync(path.join(sourceNow, '.git')).ino, before.sourceGit);
  assert.deepEqual(read(home, future), before.state);
  assert.deepEqual(read(product, future), before.child);
  assert.deepEqual(read(sourceNow, future), before.source);
  assert.equal(git(sourceNow, 'show-ref'), before.sourceRefs);
  assert.equal(git(linkedNow, 'rev-parse', 'HEAD'), before.linkedHead);
  assert.equal(git(linkedNow, 'status', '--porcelain'), before.linkedStatus);
  assert.equal(read(linkedNow, 'notes.txt').toString(), 'Untracked maintenance notes\n');
  assert.equal(read(home, 'owned-note.txt').toString(), 'Retained Director work\n');
  assert.equal(git(product, 'rev-parse', 'HEAD'), before.productHead);
  assert.equal(json(home, profile).project_root, home);
  assert.equal(json(sourceNow, profile).project_root, sourceNow);
  assert.deepEqual(Object.keys(json(product, profile).destinations), Object.keys(oldProfile.destinations));
  assert.match(read(product, launcher).toString(), /project-menu \.skill-tree\/\.director/);
  assert.equal(setup(home, 'project-menu').projects[0].queue_id, registered.queue_id);
  assert.throws(coreIntake, /Director owns the default route/);
  assert.deepEqual(read(product, future), before.child);
  assert.equal(setup(home, 'project-setup', choice).maintenance.queue_id, registered.maintenance.queue_id);
  assert.match(update('--verify'), /Director verified/);
  assert.match(update(), /Director ready/);
  git(product, 'add', '-A');
  assert.doesNotMatch(git(product, 'ls-files'), /\.skill-tree\/\.director\//);
  assert.match(git(product, 'ls-files'), /\.skill-tree\/documents\/future\.json/);
});
