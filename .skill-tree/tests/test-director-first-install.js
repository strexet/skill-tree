'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawnSync} = require('node:child_process');
const test = require('node:test');
const source = path.resolve(__dirname, '../..');
const receipt = '.skill-tree/installation/profile.json';

function run(cmd, args, cwd) {
  const result = spawnSync(cmd, args, {cwd, encoding:'utf8', timeout:120000});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout;
}

for (const webFirst of [true, false]) {
  test('Director and web have independent profiles with ' + (webFirst ? 'web' : 'Director') + ' installed first', t => {
    const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-first-')));
    t.after(() => fs.rmSync(root, {recursive:true, force:true}));
    const home = path.join(root, '.skill-tree-director');
    const read = (base, name) => fs.readFileSync(path.join(base, name), 'utf8');
    run('git', ['init', '-q', '-b', 'main', root], root);
    fs.writeFileSync(path.join(root,'index.html'), '<!DOCTYPE html>');
    const launch = (...args) => run(process.execPath, [path.join(source, '.skill-tree/bin/install.js'), '--only','codex', ...args],root);
    const web = () => launch('--target',root,'--flavor','web');
    if (webFirst) web();
    const before = webFirst && read(root, receipt);
    assert.match(launch('--dry-run'), /Director preview/);
    assert.equal(fs.existsSync(home),false);
    const stdout = process.platform === 'win32' ? launch() : run('sh',[path.join(source, 'install.sh'),'--only','codex'], root);
    assert.match(stdout,/Connect an existing project, create a new project, or continue later/);
    assert.equal(stdout.split('\n').length < 12, true);
    const director = JSON.parse(read(home, receipt));
    assert.equal(director.flavor, 'director');
    assert.equal(run('git',['rev-parse','--show-toplevel'],home).trim(),home);
    assert.equal(run('git',['branch','--show-current'],root).trim(),'main');
    const settings = JSON.parse(read(home,'workspace.json'));
    const menu = JSON.parse(run('python3',['-B',path.join(home,settings.setup_entry),'project-menu',home],root));
    assert.deepEqual(menu.choices,['existing','new','later']);
    assert.equal(fs.existsSync(path.join(home,'.skill-tree/director/registry.json')),false);
    if (webFirst) assert.equal(read(root,receipt),before);
    else {
      assert.deepEqual(fs.readdirSync(path.join(root,'.agents/skills')),['skill-tree-director']);
      web();
    }
    assert.equal(JSON.parse(read(root,receipt)).flavor,'web');
    assert.match(read(root,'.agents/skills/skill-tree-director/SKILL.md'), /project-preview/);
    assert.doesNotMatch(read(root,'.agents/skills/skill-tree-add-pending-task/SKILL.md'), /Flavor: director/);
    run(process.execPath,[path.join(root,'.skill-tree/installation/manager.js'),'--verify'],root);
    run(process.execPath,[path.join(home,'.skill-tree/installation/manager.js'),'--verify'],root);
  });
}
