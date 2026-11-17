const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const source = path.resolve(__dirname, '..');
const operation = 'skill-tree-3d';
const family = ['references', 'blender', 'texture', 'motion', 'unity'].map(role => operation + '-' + role);
const selected = [operation, ...family];
const profiles = {
  general: {},
  director: {},
  web: {
    'package.json': { scripts: { test: 'node --test' } },
  },
  unity: {
    'ProjectSettings/ProjectVersion.txt': 'm_EditorVersion: 6000.3.27f2\n',
    'Packages/manifest.json': { dependencies: { 'com.unity.test-framework': '1.6.0' } },
    'Packages/packages-lock.json': {
      dependencies: { 'com.unity.test-framework': { version: '1.6.0', source: 'builtin' } },
    },
  },
};

function runNode(cwd, entrypoint, args, label) {
  const result = spawnSync(process.execPath, [entrypoint, ...args], {
    cwd,
    encoding: 'utf8',
    timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, [label, result.stdout, result.stderr].join('\n'));
}

test('the scoped 3D operation installs and verifies without its source in every flavor', t => {
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-3d-install-'));
  t.after(() => fs.rmSync(scratch, { recursive: true, force: true }));
  const fixtureSource = path.join(scratch, 'source');
  for (const relative of ['bin', 'common', 'config', 'domains', 'lib', 'skills/general', 'src', 'templates', 'tests/fixtures/director']) {
    fs.cpSync(path.join(source, relative), path.join(fixtureSource, relative), { recursive: true });
  }

  for (const [flavor, inputs] of Object.entries(profiles)) {
    const target = path.join(scratch, flavor);
    fs.mkdirSync(target);
    for (const [relative, value] of Object.entries(inputs)) {
      const filename = path.join(target, relative);
      fs.mkdirSync(path.dirname(filename), { recursive: true });
      fs.writeFileSync(filename, typeof value === 'string' ? value : JSON.stringify(value));
    }
    runNode(target, path.join(fixtureSource, 'bin/install.js'), [
      '--source', fixtureSource, '--project', '--target', target, '--flavor', flavor,
      '--only', 'codex', '--skills', ...selected, '--non-interactive',
    ], `Install ${operation} for ${flavor}`);
  }

  fs.rmSync(fixtureSource, { recursive: true });
  for (const flavor of Object.keys(profiles)) {
    const target = path.join(scratch, flavor);
    const skills = path.join(target, '.agents/skills');
    assert.deepEqual(fs.readdirSync(skills).sort(), selected.slice().sort(), flavor);
    const installed = path.join(skills, operation);
    const skill = fs.readFileSync(path.join(installed, 'SKILL.md'), 'utf8');
    assert.match(skill, /^name: skill-tree-3d$/m, flavor);
    assert.ok(skill.includes(`Flavor: ${flavor}.`), flavor);
    assert.match(skill, /\]\(references\/3d-workflow\.md\)/, flavor);
    assert.ok(fs.readFileSync(path.join(installed, 'references/3d-workflow.md'), 'utf8').trim(), flavor);
    for (const name of [operation, 'skill-tree-3d-blender']) {
      const symmetry = path.join(skills, name, 'scripts', '3d-neutral-symmetry.py');
      assert.ok(fs.statSync(symmetry).isFile(), `Native symmetry inspector in ${name}, ${flavor}`);
    }
    for (const name of selected) {
      const command = path.join(skills, name, 'scripts', '3d-stages.py');
      const payload = {
        schema: 1, asset: 'fixture.asset', target: 'fixture.target', goal: 'references',
        fixture: true, stages: {
          references: {
            inputs: {}, allowed: ['silhouette'], protected: [], shots: ['side'],
            requirements: {'shot-states': {side: 'neutral'}},
          },
        },
      };
      fs.writeFileSync(path.join(target, 'fixture-plan.json'), JSON.stringify(payload));
      const invoke = spawnSync('python3', [
        '-B', command, '--root', target, '--run', name, 'init', '--input', 'fixture-plan.json',
      ], {cwd: scratch, encoding: 'utf8', timeout: 10_000});
      assert.ifError(invoke.error);
      assert.equal(invoke.status, 0, invoke.stderr);
      assert.deepEqual(JSON.parse(invoke.stdout).steps, [{stage: 'references', status: 'pending'}]);
    }
    runNode(scratch, path.join(target, '.skill-tree/installation/manager.js'), ['--verify'],
      `Verify standalone ${flavor} installation`);
  }
});
