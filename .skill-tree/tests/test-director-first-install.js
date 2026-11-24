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
    const home = path.join(root, '.skill-tree/.director');
    const read = (base, name) => fs.readFileSync(path.join(base, name), 'utf8');
    run('git', ['init', '-q', '-b', 'main', root], root);
    fs.writeFileSync(path.join(root,'index.html'), '<!DOCTYPE html>');
    const launch = (...args) => run(process.execPath, [path.join(source, '.skill-tree/bin/install.js'), '--only','codex', ...args],root);
    const web = () => launch('--target',root,'--flavor','web');
    if (webFirst) web();
    const before = webFirst && read(root, receipt);
    const exclude = path.join(root,'.git/info/exclude');
    fs.writeFileSync(exclude, '# Existing local comment without a trailing newline');
    fs.writeFileSync(path.join(root,'.gitignore'),'*.local\n');
    assert.match(launch('--dry-run'), /Director preview/);
    assert.match(launch('--flavor','director','--dry-run'), /Director preview/);
    assert.equal(fs.existsSync(home),false);
    const choice = webFirst ? ['--flavor','director'] : [];
    const stdout = process.platform === 'win32' ? launch(...choice) : run('sh',[path.join(source, 'install.sh'),'--only','codex',...choice], root);
    assert.match(stdout,/Connect an existing project, create a new project, or continue later/);
    assert.equal(stdout.split('\n').length < 12, true);
    assert.equal(fs.existsSync(path.join(root, '.skill-tree-director')), false);
    const excluded = read(root,'.git/info/exclude');
    assert.match(excluded,/^# Existing local comment without a trailing newline\r?\n/);
    assert.equal(read(root,'.gitignore'),'*.local\n');
    assert.doesNotMatch(run('git',['status','--short','--untracked-files=all'],root),/\?\? \.skill-tree\/\.director/);
    run('git',['add','-A'],root);
    assert.doesNotMatch(run('git',['ls-files'],root),/\.skill-tree\/\.director/);
    launch('--flavor','director');
    assert.equal(read(root,'.git/info/exclude'),excluded);
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
    assert.match(launch('--flavor','director','--verify'),/Director verified/);
    const launcher = path.join(root,'.agents/skills/skill-tree-director/SKILL.md');
    if (webFirst) {
      const expected = fs.readFileSync(launcher);
      const legacy = fs.readFileSync(path.join(__dirname,'fixtures/director/legacy-workspace-launcher.md'));
      fs.writeFileSync(launcher,Buffer.concat([legacy,Buffer.from('Owner edit\n')]));
      assert.throws(() => launch('--flavor','director'),/launcher conflicts/);
      assert.match(fs.readFileSync(launcher,'utf8'),/Owner edit/);
      fs.writeFileSync(launcher,expected);
      launch('--flavor','director');
      assert.deepEqual(fs.readFileSync(launcher),expected);
    }
    fs.unlinkSync(launcher);
    const missing = spawnSync(process.execPath,[path.join(source,'.skill-tree/bin/install.js'),'--target',root,
      '--flavor','director','--verify'],{encoding:'utf8',timeout:30000});
    assert.notEqual(missing.status,0);
    assert.match(missing.stderr,/launcher/i);
    assert.equal(fs.existsSync(launcher),false);
  });
}

test('a nested new workspace can be previewed and created with the public launcher', t => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-new-location-')));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const root = path.join(base, 'new-parent', 'new-workspace');
  const args = ['--target',root,'--only','codex','--flavor','director'];
  const launch = extra => process.platform === 'win32'
    ? run('powershell',['-NoProfile','-File',path.join(source,'install.ps1'),...args,...extra],base)
    : run('sh',[path.join(source,'install.sh'),...args,...extra],base);
  assert.match(launch(['--dry-run']),/Director preview/);
  assert.deepEqual(fs.readdirSync(base),[]);
  assert.match(launch([]),/Director ready/);
  assert.equal(JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/.director',receipt))).flavor,'director');
});

test('explicit low-level installation and repeated legacy Director verification keep the original owner', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'director-raw-profile-')));
  t.after(() => fs.rmSync(root,{recursive:true, force:true}));
  const args = [path.join(source,'.skill-tree/bin/install.js'),'--only','codex','--target',root,'--flavor','director'];
  run(process.execPath,[...args,'--project'],root);
  const profile = JSON.parse(fs.readFileSync(path.join(root,receipt)));
  assert.equal(profile.project_root,root);
  assert.equal(profile.flavor,'director');
  run(process.execPath,[...args,'--verify'],root);
  run(process.execPath,args,root);
  assert.equal(fs.existsSync(path.join(root,'.skill-tree/.director')),false);
});

test('scoped Director uninstall preserves shared discovery, the remaining host and the service queue', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'director-host-removal-')));
  t.after(() => fs.rmSync(root,{recursive:true,force:true}));
  const home = path.join(root,'.skill-tree/.director');
  const cli = path.join(source,'.skill-tree/bin/install.js');
  const launch = (...flags) => run(process.execPath,[cli,'--target',root,'--flavor','director',...flags],root);
  const read = (dir, name) => fs.readFileSync(path.join(dir,name),'utf8');
  const config = () => JSON.parse(read(home, 'workspace.json'));
  const menu = () => JSON.parse(run('python3',['-B',path.join(home,config().setup_entry),'project-menu',home],root));
  const shared = path.join(root,'.agents/skills/skill-tree-director/SKILL.md');
  const separate = path.join(root,'.claude/skills/skill-tree-director/SKILL.md');
  const routingBlock = '<!-- BEGIN skill-tree-director-routing -->';
  run(process.execPath,[cli,'--target',root,'--only','codex','--flavor','web'],root);
  const original = read(root,receipt);
  const originalAgents = fs.existsSync(path.join(root,'AGENTS.md')) ? read(root,'AGENTS.md') : null;
  fs.writeFileSync(path.join(root, 'CLAUDE.md'), '');
  const wrongOwner = spawnSync(process.execPath,[cli,'--target',root,'--project','--only','codex',
    '--flavor','director','--uninstall'],{encoding:'utf8'});
  assert.notEqual(wrongOwner.status,0);
  assert.match(wrongOwner.stderr,/no ownership/);
  assert.equal(read(root,receipt),original);
  launch('--only','codex','--only','dsh','--only','claude-code');
  assert.ok(read(root,'AGENTS.md').includes(routingBlock));
  assert.ok(read(root,'CLAUDE.md').includes(routingBlock));
  const initial = config();
  const queue = read(home,'.skill-tree/documents/future.json');
  const sourceStore = path.join(home,'sources','local-work');
  fs.mkdirSync(sourceStore,{recursive:true});
  fs.writeFileSync(path.join(sourceStore,'draft.md'),'retained work');
  assert.match(launch('--only','codex','--uninstall','--dry-run'),/preview/);
  assert.deepEqual(config(),initial);
  launch('--only','codex','--uninstall');
  assert.deepEqual(config().providers,['dsh','claude-code']);
  assert.equal(fs.existsSync(shared),true);
  assert.ok(read(root,'AGENTS.md').includes(routingBlock));
  assert.deepEqual(menu().providers,config().providers);
  assert.match(launch('--only','codex','--uninstall'),/already absent/);
  launch('--only','dsh','--uninstall');
  assert.deepEqual(config().providers,['claude-code']);
  assert.equal(fs.existsSync(shared),false);
  assert.equal(fs.existsSync(path.join(root,'AGENTS.md')) ? read(root,'AGENTS.md') : null, originalAgents);
  assert.equal(fs.existsSync(separate),true);
  assert.ok(read(root,'CLAUDE.md').includes(routingBlock));
  assert.deepEqual(menu().providers,['claude-code']);
  assert.match(launch('--only','claude-code','--verify'),/Director verified/);
  launch('--only','claude-code','--uninstall');
  assert.deepEqual(config().providers,[]);
  assert.equal(config().setup_entry,null);
  assert.equal(fs.existsSync(separate),false);
  assert.equal(read(root,'CLAUDE.md'), '');
  assert.match(launch('--only','claude-code','--uninstall'),/already absent/);
  assert.equal(read(sourceStore,'draft.md'),'retained work');
  assert.equal(read(home,'.skill-tree/documents/future.json'),queue);
  assert.equal(read(root,receipt),original);
  launch('--only','claude-code');
  assert.deepEqual(menu().providers,['claude-code']);
  assert.equal(read(home,'.skill-tree/documents/future.json'),queue);
});

test('linked product worktree excludes the service through the shared Git directory', t => {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-linked-')));
  t.after(() => fs.rmSync(base, {recursive:true, force:true}));
  const root = path.join(base,'product'), linked = path.join(base,'linked');
  run('git',['init','-q','-b','main',root],base);
  run('git',['-c','user.name=Fixture','-c','user.email=fixture@invalid.test','commit','--allow-empty','-qm','Fixture'],root);
  run('git',['worktree','add','-qb','fixture-work',linked],root);
  const launch = () => run(process.execPath,[path.join(source,'.skill-tree/bin/install.js'),'--only','codex',
    '--target',linked,'--flavor','director'],linked);
  launch();
  const service = '.skill-tree/.director';
  assert.match(run('git',['check-ignore',service+'/'],linked),/skill-tree\/\.director/);
  assert.doesNotMatch(run('git',['status','--short','--untracked-files=all'],linked),/\?\? \.skill-tree\/\.director/);
  run('git',['add','-f',service],linked);
  const index = run('git',['ls-files','-s'],linked);
  assert.match(index,/\.skill-tree\/\.director/);
  assert.throws(launch,/overlaps tracked product files/);
  assert.equal(run('git',['ls-files','-s'],linked),index);
});

test('higher-priority product Git rules block setup before creating service storage', t => {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'director-git-rule-')));
  t.after(() => fs.rmSync(root, {recursive:true, force:true}));
  run('git',['init','-q','-b','main',root],root);
  const exclude=path.join(root,'.git/info/exclude'),ignore=path.join(root,'.gitignore');
  const original=fs.readFileSync(exclude);
  fs.writeFileSync(ignore,'!/.skill-tree/.director/\n');
  const install=()=>run(process.execPath,[path.join(source,'.skill-tree/bin/install.js'),'--only','codex',
    '--target',root,'--flavor','director'],root);
  assert.throws(install,/Product Git ignore rules expose Director storage/);
  assert.deepEqual(fs.readFileSync(exclude),original);
  assert.equal(fs.readFileSync(ignore,'utf8'),'!/.skill-tree/.director/\n');
  assert.equal(fs.existsSync(path.join(root,'.skill-tree/.director')),false);
});
