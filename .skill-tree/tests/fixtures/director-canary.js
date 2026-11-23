'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const childProcess = require('node:child_process');
const {spawnSync} = childProcess;
const core = require('../../lib/installation.js');
const c = require('../../lib/composer.js');

const SOURCE = path.resolve(__dirname, '../..');
const SNAPSHOT = 'skill-tree-create-documents-snapshot';
const CONTROLLER = 'skill-tree-work-through-next';
const SCOPE_HELPER = 'common/scripts/create-documentation-snapshot.py';
const INSTALLED_HELPER = '.agents/skills/' + SNAPSHOT + '/scripts/create-documentation-snapshot.py';
const WORKFLOW = '.skill-tree/documents/future.json';
const README = '# Director snapshot canary\n\nThis document is the selected Markdown input.\n';
const FLAVOR = 'general';
const SCENARIO = {
  id: 'director-documentation-snapshot-readme', recipe_id: 'director-snapshot-canary',
  lane: 'unit', assertion_id: 'snapshot-scope-preserves-markdown-extension',
  assertion: 'The dry-run report preserves the Markdown extension of README.md.', input_sha256: c.hash(README),
};
const cid = prefix => prefix + '-' + randomUUID();
const seal = value => c.hash(c.json(value));

function write(root, relative, value) {
  const filename = path.join(root, relative);
  fs.mkdirSync(path.dirname(filename), {recursive: true});
  fs.writeFileSync(filename, value);
}

function run(cwd, args) {
  const result = spawnSync(args[0], args.slice(1), {cwd, encoding: 'utf8', timeout: 30000});
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout.trim();
}

function git(root, ...args) {
  return run(root, ['git', '-C', root, ...args]);
}

function workflow(root, location, command, data, ...flags) {
  const payload = path.join(location, 'fixture-request.json');
  fs.writeFileSync(payload, JSON.stringify(data || {}));
  const [destination] = Object.entries(core.receipt(root, true).destinations).find(([,record]) => record.name === CONTROLLER);
  const entry = path.join(root, destination, 'scripts/workflow-state.py');
  return JSON.parse(run(root, ['python3', '-B', entry, command, root, '--input', payload, ...flags]));
}

function copySource(base, name) {
  const dest = path.join(base, name);
  fs.mkdirSync(dest);
  for (const relative of Object.keys(c.sourceInputs(SOURCE)))
    write(dest, relative, fs.readFileSync(path.join(SOURCE, relative)));
  return dest;
}

function installedSnapshot(root, helper = INSTALLED_HELPER) {
  const output = run(root, ['python3', '-B', path.join(root, helper), root,
    '--dry-run', '--include', 'README.md', '--timestamp', '2000-01-01-00-00']);
  return output.split(/\r?\n/).slice(1);
}

function buildCandidate(source, target, repaired, previous, provider, destination) {
  const profile = c.resolveProfile(source, target, FLAVOR);
  const output = c.compose(source, profile, [SNAPSHOT, CONTROLLER]);
  const source_inventory_sha256 = seal(c.sourceInputs(source));
  const scenario_sha256 = seal(SCENARIO);
  const checks = {};
  for (const [name, result, observed] of [['original', 'fail', previous], ['repaired', 'pass', repaired]]) {
    checks[name] = {result, scenario_sha256, record_sha256: seal(observed), attempt_id: cid('C'),
      evidence: {path: 'fixture-' + name + '.txt', sha256: seal(observed)}};
  }
  const installed = core.receipt(target, true).destinations[destination];
  const body = {
    schema: 1, kind: 'director-source-repair-candidate', finding_sha256: c.hash('fixture finding'),
    route: {area_id: 'source-maintenance', queue_id: cid('Q'), pending_id: cid('P'), processing_run_id: cid('PR'),
      task_id: cid('T'), run_id: cid('WR'), outcome_id: cid('O')},
    owner: {actor: 'fixture-owner', kind: 'owner-message', reference: 'synthetic-scope'},
    source: {revision: 'source-inventory:' + source_inventory_sha256, source_inventory_sha256},
    packages: {flavor: FLAVOR, provider, environment_id: profile.environment_id,
      output_digests: output.output_digests},
    scenario: SCENARIO, checks, review: {reference: 'unit-fixture-reviewed',
      before_sha256: installed.files['scripts/create-documentation-snapshot.py'],
      after_sha256: output.output_digests[SNAPSHOT]['scripts/create-documentation-snapshot.py']},
  };
  return {...body, candidate_sha256: seal(body)};
}

function fixture(t, providers = ['codex']) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'director-canary-unit-'));
  t.after(() => fs.rmSync(base, {force: true, recursive: true}));
  const local = fs.realpathSync(base);
  const old = copySource(local, 'old');
  const source = copySource(local, 'candidate');
  const oldBody = fs.readFileSync(path.join(old, SCOPE_HELPER), 'utf8');
  const mutant = oldBody.replace('print(f"- {item}")', 'print(f"- {item.removesuffix(\'.md\')}")');
  assert.notEqual(mutant, oldBody);
  write(old, SCOPE_HELPER, mutant);
  const owner = path.join(local, 'owner');
  const target = path.join(local, 'worktree');
  fs.mkdirSync(owner);
  git(owner, 'init', '-b', 'develop');
  git(owner, 'config', 'core.hooksPath', os.devnull);
  git(owner, 'config', 'protocol.allow', 'never');
  git(owner, 'remote', 'add', 'origin', path.join(local, 'unused-local-remote.git'));
  write(owner, 'README.md', README);
  write(owner, '.skill-tree/documents/future.md', '# Future Work\n\n## Pending Task Format\n\nFixture.\n\n' +
    '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
  if (providers[0] !== 'codex') {
    const {projectPath} = c.readJson(SOURCE, 'config/providers.json').providers.find(row => row.id === providers[0]);
    const helper = path.posix.join(projectPath, SNAPSHOT, 'scripts/create-documentation-snapshot.py');
    write(owner, '.skill-tree/validation-recipes.json', c.json({schema: 1, recipes: {'director-snapshot-canary': {
      lane: 'unit', argv: ['python3','-B',helper,'{project_root}','--dry-run','--include','README.md'], input_paths: [],
    }}}));
  }
  git(owner, 'add', '.');
  git(owner, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
    '-c', 'commit.gpgsign=false', 'commit', '-m', 'Local canary fixture');
  const matrix = c.readJson(SOURCE, 'config/providers.json').providers;
  const selections = providers.flatMap(provider => {
    const {projectPath} = matrix.find(row => row.id === provider);
    return [SNAPSHOT, CONTROLLER].map(name => ({name, provider, rel: path.posix.join(projectPath, name)}));
  });
  const destination = selections[0].rel;
  const helper = destination + '/scripts/create-documentation-snapshot.py';
  core.install(owner, old, FLAVOR, selections);
  const queue = workflow(owner, local, 'workspace-setup', {}).queue_id;
  const requirement = 'Preserve the installed snapshot member extension.';
  const pending = workflow(owner, local, 'intake', {title: 'Check snapshot member extension', description: requirement,
    expected_behavior: requirement}).id;
  const spec = {id: 'unit-fixture', recipe_id: 'static-inspection', criteria: [requirement], sources: ['README.md'],
    parameters: {}, assertion: requirement, timing: 'immediate'};
  const body = 'Goal:\n- ' + requirement + '\n\nTouch:\n- README.md\n\nValidation:\n```json\n' +
    JSON.stringify({checks: [spec]}) + '\n```\n\nAcceptance:\n- ' + requirement + '\n';
  const task = workflow(owner, local, 'process', {selectors: [pending], dispositions: {
    [pending]: {status: 'promoted', reason: 'The fixture defines exact scope.'}},
  tasks: [{title: 'Check snapshot member extension', body, parent_pending_ids: [pending]}]}).created_ids[0];
  const opened = workflow(owner, local, 'start', {local_base: true, local_base_authorization: 'Local fixture only.',
    base_branch: 'develop', branch: 'codex/canary-fixture', worktree: target}, '--id', task);
  workflow(owner, local, 'checkpoint', {phase: 'refresh-profile', stop_reason: 'Stopped for canary installation.',
    next_action: 'Verify the planned installation.'}, '--run-id', opened.id);
  core.install(target, old, FLAVOR, selections);
  workflow(target, local, 'admit', {}, '--run-id', opened.id);
  write(target, 'product.txt', 'Preserved product bytes.\n');
  write(owner, '.skill-tree/history/independent-acceptance.json', '{"fixture":"preserve"}\n');
  const scope = {queue_id: queue, run_id: opened.id, task_id: task, flavor: FLAVOR, provider: providers[0],
    authority_ref: 'fixture-owner-selected-canary', preserve_paths: ['product.txt']};
  const previous = installedSnapshot(target, helper);
  assert.deepEqual(previous, ['included: 1', '- README']);
  const repaired = run(target, ['python3', '-B', path.join(source, SCOPE_HELPER), target,
    '--dry-run', '--include', 'README.md', '--timestamp', '2000-01-01-00-00']).split(/\r?\n/).slice(1);
  assert.deepEqual(repaired, ['included: 1', '- README.md']);
  const candidate = buildCandidate(source, target, repaired, previous, providers[0], destination);
  return {local, owner, target, scope, candidate, source, old, helper};
}

module.exports = {fixture, workflow, installedSnapshot, write, cid, WORKFLOW, INSTALLED_HELPER, README, SNAPSHOT};
