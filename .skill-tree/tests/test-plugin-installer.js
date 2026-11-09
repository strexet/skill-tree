'use strict';

// Disposable projects exercise the public installer and the actual T131 manager.
const assert = require('node:assert/strict');
const {spawnSync} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const source = path.resolve(__dirname, '..');
const installer = path.join(source, 'bin/install.js');
const core = require(path.join(source, 'lib/installation.js'));
const registry = require(path.join(source, 'lib/plugin-registry.js'));
const manager = require(path.join(source, 'lib/plugin-management.js'));
const op = 'skill-tree-process-future-pending';
const managerName = 'skill-tree-plugins';
const bindings = [
  {id: 'editor-first', plugin_id: 'fixture-editor', operation: op, anchor: 'after', enabled: true,
    parameters: {pass: 'first', extra: [null, true]}, instructions: 'Review original wording.'},
  {id: 'interview', plugin_id: 'fixture-interview', operation: op, anchor: 'after-task-creation', enabled: false,
    parameters: {rounds: 2}, condition: {present: '/accepted_marker'}},
  {id: 'editor-last', plugin_id: 'fixture-editor', operation: op, anchor: 'after', enabled: true,
    parameters: {pass: 'last', extra: [3]}, instructions: 'Review amended wording.'},
];

function write(root, relative, text) {
  const file = path.join(root, relative);
  fs.mkdirSync(path.dirname(file), {recursive: true});
  fs.writeFileSync(file, text);
  return file;
}

function setup(t) {
  const base = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'skill-tree-optional-installer-')));
  t.after(() => fs.rmSync(base, {recursive: true, force: true}));
  const root = path.join(base, 'target');
  fs.mkdirSync(root);
  const marker = path.join(base, 'upstream-script-executed');
  const sources = ['fixture-editor', 'fixture-interview'].map(id => {
    write(base, id + '/SKILL.md', '# Controlled instruction\n\n[Optional helper](helper.js).\n');
    write(base, id + '/helper.js', 'require("node:fs").writeFileSync(' + JSON.stringify(marker) + ', "unexpected");');
    return {id, path: path.join(base, id), metadata: {authoring_host: 'claude'}};
  });
  const guard = write(base, 'no-network-or-dispatch.cjs', [
    "'use strict';",
    "const deny = () => { throw Error('unexpected network acquisition or skill dispatch'); };",
    "const cp = require('node:child_process'), git = cp.spawnSync;",
    "cp.spawnSync = (file,args,options) => file === 'git' && args.includes('rev-parse') ? git(file,args,options) : deny();",
    "for (const key of ['exec','execFile','execFileSync','execSync','fork','spawn']) cp[key] = deny;",
    "global.fetch = deny;",
    "for (const key of ['node:http','node:https']) { const client = require(key); client.get = client.request = deny; }",
  ].join('\n'));
  return {base, root, sources, marker, guard};
}

function run(f, flags = [], {only = ['codex'], guard = f.guard, file = installer} = {}) {
  const args = file === installer ?
    ['--target', f.root, '--flavor', 'general', ...only.flatMap(id => ['--only', id]), ...flags] : flags;
  return spawnSync(process.execPath, [...(guard ? ['--require', guard] : []), file, ...args], {
    cwd: f.base, encoding: 'utf8', timeout: 30000, input: '', env: {...process.env, NODE_PATH: ''},
  });
}

function output(run) {
  return JSON.parse(run.stdout.split('\nDocumentation setup remains separate:')[0]);
}

function stage(run) {
  const envelope = output(run);
  return {core: envelope.core, plugins: envelope.plugin_stage ?? envelope.plugins};
}

function assertNoWorkflow(f) {
  for (const relative of [
    '.skill-tree/documents/future.json', '.skill-tree/documents/future.md',
    '.skill-tree/invocations', '.skill-tree/decisions', '.skill-tree/clarifications',
  ]) assert.equal(fs.existsSync(path.join(f.root, relative)), false, relative);
  assert.equal(fs.existsSync(f.marker), false, 'Installation executed a plugin helper');
}

function rawRegistry(f) {
  return fs.readFileSync(path.join(f.root, registry.REGISTRY));
}

async function installProposal(f, requestId = 'install-exact-aba') {
  const prepared = await manager.prepareManagerRequest(f.root, {
    action: 'install', request_id: requestId, sources: f.sources, bindings,
  }, {source});
  assert.equal(prepared.status, 'ready');
  assert.deepEqual(prepared.preview.bindings.map(row => row.id), bindings.map(row => row.id));
  return prepared.proposal;
}

function store(f, proposal, name = 'reviewed-proposal.json') {
  return write(f.base, name, JSON.stringify(proposal) + '\n');
}

function confirm(file, proposal) {
  return ['--non-interactive', '--plugins', file, '--confirm-plugins', proposal.digest];
}

test('core-only first and repeat installs keep the legacy output and default to zero external plugins', t => {
  const f = setup(t);
  for (const flags of [[], ['--yes']]) {
    const installed = run(f, flags);
    assert.equal(installed.status, 0, installed.stderr + installed.stdout);
    const providers = output(installed);
    assert.ok(Array.isArray(providers));
    assert.equal(providers.length, 1);
    assert.equal(providers[0].packages.length, 11);
    assert.ok(providers[0].packages.some(pkg => pkg.name === managerName));
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
    assertNoWorkflow(f);
  }
});

test('setup flags require explicit noninteractive proposal consent and reject conflicting operations', t => {
  const f = setup(t);
  for (const flags of [
    ['--configure-plugins', '--yes'],
    ['--confirm-plugins', 'a'.repeat(64)],
    ['--configure-plugins', '--plugins', 'unused.json'],
    ['--configure-plugins', '--verify'],
    ['--configure-plugins', '--uninstall'],
    ['--configure-plugins', '--list-plugins'],
  ]) {
    const rejected = run(f, flags);
    assert.notEqual(rejected.status, 0, flags.join(' '));
    assert.match(rejected.stdout + rejected.stderr, /plugin|proposal|confirm|interactive/i);
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
    assertNoWorkflow(f);
  }
});

test('a serialized shared-manager proposal activates exact A–B–A, replays offline, and preserves core-only repeat', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const proposal = await installProposal(f);
  const file = store(f, proposal);
  const before = core.treeHash(f.root, '.skill-tree');
  for (const flags of [
    ['--yes', '--plugins', file],
    ['--yes', '--plugins', file, '--confirm-plugins', '0'.repeat(64)],
  ]) {
    const rejected = run(f, flags);
    assert.notEqual(rejected.status, 0);
    assert.match(rejected.stdout + rejected.stderr, /consent|confirm|digest/i);
    assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  }
  const dry = run(f, ['--dry-run', ...confirm(file, proposal)]);
  assert.equal(dry.status, 0, dry.stderr + dry.stdout);
  assert.equal(stage(dry).plugins.dry_run, true);
  assert.equal(core.treeHash(f.root, '.skill-tree'), before);
  const foreign = setup(t);
  assert.equal(run(foreign, ['--yes']).status, 0);
  const wrongTarget = run(foreign, confirm(file, proposal));
  assert.notEqual(wrongTarget.status, 0);
  assert.match(wrongTarget.stdout + wrongTarget.stderr, /target|proposal/i);
  assert.equal(fs.existsSync(path.join(foreign.root, registry.REGISTRY)), false);
  const accepted = run(f, confirm(file, proposal));
  assert.equal(accepted.status, 0, accepted.stderr + accepted.stdout);
  const first = stage(accepted);
  assert.ok(first.core.every(row => row.ok));
  assert.match(JSON.stringify(first.plugins), /installed|activated/i);
  const publicStage = JSON.stringify(first.plugins);
  assert.doesNotMatch(publicStage, /base64|"snapshots"/i);
  for (const definition of f.sources) assert.ok(!publicStage.includes(definition.path));

  const installed = registry.verifyInstalled(f.root);
  assert.deepEqual(installed.bindings.map(row => [row.id, row.plugin_id, row.enabled, row.parameters]), bindings.map(
    row => [row.id, row.plugin_id, row.enabled, row.parameters]));
  assert.deepEqual(installed.bindings[1].condition, bindings[1].condition);
  assert.equal(installed.bindings[2].instructions, bindings[2].instructions);
  assert.deepEqual(Object.keys(installed.packages).sort(), ['fixture-editor', 'fixture-interview']);
  const bytes = rawRegistry(f);
  const later = manager.managementInventory(f.root, {source});
  assert.deepEqual(later.points.find(point => point.boundary_id === op + ':after').bindings.map(row => row.id),
    bindings.map(row => row.id));
  for (const definition of f.sources) fs.rmSync(definition.path, {recursive: true});
  const replayed = run(f, confirm(file, proposal));
  assert.equal(replayed.status, 0, replayed.stderr + replayed.stdout);
  assert.match(JSON.stringify(stage(replayed).plugins), /"replayed":true/);
  assert.deepEqual(rawRegistry(f), bytes);
  assert.equal(run(f, ['--yes']).status, 0);
  assert.deepEqual(rawRegistry(f), bytes);
  const owned = core.treeHash(f.root, '.skill-tree');
  const verified = run(f, ['--verify', '--yes']);
  assert.equal(verified.status, 0, verified.stderr + verified.stdout);
  assert.equal(core.treeHash(f.root, '.skill-tree'), owned);
  assertNoWorkflow(f);
});

test('one real provider failure preserves another provider result and blocks the optional stage', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const install = await installProposal(f, 'install-before-partial');
  assert.equal(run(f, confirm(store(f, install), install)).status, 0);
  const move = await manager.prepareManagerRequest(f.root, {
    action: 'move', request_id: 'partial-provider-reorder', binding_id: 'editor-last', index: 0,
  }, {source});
  const file = store(f, move.proposal, 'reviewed-move.json');
  const bytes = rawRegistry(f);
  const collision = '.claude/skills/' + managerName + '/SKILL.md';
  write(f.root, collision, '# Unowned destination must survive.\n');
  const partial = run(f, confirm(file, move.proposal), {only: ['codex', 'claude-code']});
  assert.notEqual(partial.status, 0);
  const observed = stage(partial);
  assert.equal(observed.core.find(row => row.provider === 'codex').ok, true);
  assert.equal(observed.core.find(row => row.provider === 'claude-code').ok, false);
  assert.match(JSON.stringify(observed.plugins), /blocked|provider|prerequisite/i);
  assert.deepEqual(rawRegistry(f), bytes);
  assert.equal(fs.readFileSync(path.join(f.root, collision), 'utf8'), '# Unowned destination must survive.\n');
  assertNoWorkflow(f);
});

test('adding a provider without changing composition identity makes an old scope proposal stale', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const original = core.receipt(f.root, true).identity;
  const proposal = await installProposal(f);
  const file = store(f, proposal);
  assert.equal(run(f, ['--yes'], {only: ['claude-code']}).status, 0);
  assert.equal(core.receipt(f.root, true).identity, original);
  const rejected = run(f, confirm(file, proposal));
  assert.notEqual(rejected.status, 0);
  assert.match(rejected.stdout + rejected.stderr, /scope|stale|destination|provider/i);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  assertNoWorkflow(f);
});

test('interrupted optional activation keeps verified core results and requires owned recovery', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const prepared = await installProposal(f, 'interrupt-exact-optional-activation');
  const proposalFile = store(f, prepared);
  const receiptBefore = core.treeHash(f.root, '.skill-tree/installation/profile.json');
  const registryFile = path.join(f.root, registry.REGISTRY);
  const journal = core.transactionPaths('plugins').journal;

  const fault = write(f.base, 'interrupt-plugin-activation.cjs', fs.readFileSync(f.guard, 'utf8') + '\n' + [
    "const fs = require('node:fs'), rename = fs.renameSync;",
    'const registry = ' + JSON.stringify(registryFile) + ';',
    'let injected = false;',
    'fs.renameSync = (from, to) => {',
    '  if (!injected && to === registry) {',
    '    injected = true;',
    '    throw Error("controlled interruption at registry activation");',
    '  }',
    '  return rename(from, to);',
    '};',
  ].join('\n'));
  const interrupted = run(f, confirm(proposalFile, prepared), {guard: fault});
  assert.notEqual(interrupted.status, 0);
  const interruptedStage = stage(interrupted);
  assert.ok(interruptedStage.core.every(row => row.ok));
  assert.match(JSON.stringify(interruptedStage.plugins), /interruption|failed|recovery/i);
  assert.equal(core.treeHash(f.root, '.skill-tree/installation/profile.json'), receiptBefore);
  assert.equal(fs.existsSync(registryFile), false);
  assert.ok(fs.existsSync(path.join(f.root, journal)));
  core.verifyOwned(f.root, core.receipt(f.root, true));

  const paused = core.treeHash(f.root, '.skill-tree');
  const listed = spawnSync(process.execPath, ['--require', f.guard, installer,
    '--list-plugins', '--target', f.root, '--json'], {
    cwd: f.base, encoding: 'utf8', timeout: 30000, env: {...process.env, NODE_PATH: ''},
  });
  assert.ok(listed.stdout.includes('skill-tree-plugin-inventory'));
  assert.equal(core.treeHash(f.root, '.skill-tree'), paused);
  for (const flags of [
    ['--dry-run', ...confirm(proposalFile, prepared)],
    ['--yes'],
    ['--yes', '--plugins', proposalFile, '--confirm-plugins', '0'.repeat(64)],
  ]) {
    const held = run(f, flags);
    assert.notEqual(held.status, 0);
    assert.match(held.stdout + held.stderr, /recovery|journal|confirm|digest/i);
    assert.equal(core.treeHash(f.root, '.skill-tree'), paused, flags.join(' '));
  }
  assertNoWorkflow(f);

  const owner = path.join(f.root, '.skill-tree/installation/manager.js');
  const rollback = run(f, ['--rollback'], {file: owner});
  assert.notEqual(rollback.status, 0);
  assert.match(rollback.stderr, /plugin installation recovery/i);
  assert.equal(core.treeHash(f.root, '.skill-tree'), paused);
  const recovered = run(f, ['--recover'], {file: owner});
  assert.equal(recovered.status, 0, recovered.stderr + recovered.stdout);
  assert.equal(fs.existsSync(path.join(f.root, journal)), false);
  const activated = registry.verifyInstalled(f.root);
  assert.deepEqual(activated.bindings.map(row => row.id), bindings.map(row => row.id));
  assert.equal(activated.requests[prepared.request_id].proposal_digest, prepared.mutation.proposal.digest);

  const bytes = rawRegistry(f);
  const replay = run(f, confirm(proposalFile, prepared));
  assert.equal(replay.status, 0, replay.stderr + replay.stdout);
  assert.match(JSON.stringify(stage(replay).plugins), /"replayed":true/);
  assert.deepEqual(rawRegistry(f), bytes);
  assertNoWorkflow(f);
});

test('core refresh and rollback retain binary plugin resources in cache-named directories', async t => {
  const f = setup(t), skill = f.sources[0].path;
  const relative = '__pycache__/fixture.bin', bytes = Buffer.from([0, 255, 128, 13, 10]);
  fs.appendFileSync(path.join(skill, 'SKILL.md'), `\n[Binary resource](${relative}).\n`);
  write(skill, relative, bytes);
  assert.equal(run(f, ['--yes']).status, 0);
  const proposal = await installProposal(f);
  assert.equal(run(f, confirm(store(f, proposal), proposal)).status, 0);
  const owner = path.join(f.root, '.skill-tree/installation/manager.js');
  const manage = flag => {
    const result = run(f, [flag], {file: owner});
    assert.equal(result.status, 0, result.stderr + result.stdout);
  };
  manage('--refresh-profile');
  const installed = path.join(f.root, '.agents/skills', op, 'plugins/fixture-editor/upstream', relative);
  assert.deepEqual(fs.readFileSync(installed), bytes);
  const before = core.treeHash(f.root, '.agents/skills/' + op);
  const projectInputs = write(f.root, 'package.json', '{"scripts":{"test":"node --test"}}');
  manage('--refresh-profile');
  assert.notEqual(core.treeHash(f.root, '.agents/skills/' + op), before);
  fs.unlinkSync(projectInputs);
  manage('--rollback');
  assert.deepEqual(fs.readFileSync(installed), bytes);
  assert.equal(core.treeHash(f.root, '.agents/skills/' + op), before);
  manage('--verify');
  assertNoWorkflow(f);
});

test('core can be reinstalled after initial rollback with an independent plugin generation', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const proposal = await installProposal(f);
  manager.applyManagerProposal(f.root, proposal, {proposal_digest: proposal.digest});
  const bytes = rawRegistry(f);
  const owner = path.join(f.root, '.skill-tree/installation/manager.js');
  const rolled = run(f, ['--rollback'], {file: owner});
  assert.equal(rolled.status, 0, rolled.stderr);
  assert.equal(core.receipt(f.root), null);
  assert.deepEqual(rawRegistry(f), bytes);
  const reinstalled = run(f, ['--yes']);
  assert.equal(reinstalled.status, 0, reinstalled.stderr + reinstalled.stdout);
  assert.deepEqual(rawRegistry(f), bytes);
  assert.equal(run(f, ['--verify'], {file: owner}).status, 0);
  assertNoWorkflow(f);
});

test('unowned plugin staging and backup files survive rejected core and plugin activation', async t => {
  for (const key of ['stage', 'backups']) {
    const f = setup(t), relative = core.transactionPaths('plugins')[key] + '/unrelated.txt';
    const marker = write(f.root, relative, 'Keep these local bytes.');
    const initial = run(f, ['--yes']);
    assert.notEqual(initial.status, 0);
    assert.match(initial.stdout + initial.stderr, /unowned maintenance/i);
    assert.equal(fs.readFileSync(marker, 'utf8'), 'Keep these local bytes.');
    fs.unlinkSync(marker);
    fs.rmdirSync(path.dirname(marker));
    assert.equal(run(f, ['--yes']).status, 0);
    write(f.root, relative, 'Keep these local bytes.');
    const proposal = await installProposal(f);
    assert.throws(() => manager.applyManagerProposal(f.root, proposal, {proposal_digest: proposal.digest}), /staging already exists|unowned.*backups/i);
    assert.equal(fs.readFileSync(marker, 'utf8'), 'Keep these local bytes.');
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
    assertNoWorkflow(f);
  }
});

function interactive(f, flags, answers, {only = ['codex'], scopeChange, allowUnused = false} = {}) {
  const transcript = path.join(f.base, 'prompt-transcript.json');
  const argv = ['--target', f.root, '--flavor', 'general', ...only.flatMap(id => ['--only', id]), ...flags];
  const fixture = write(f.base, 'interactive-installer.cjs', [
    "'use strict';",
    "const fs = require('node:fs');",
    'const {main} = require(' + JSON.stringify(installer) + ');',
    'const answers = ' + JSON.stringify(answers) + ';',
    'const events = [];',
    'const scopeChange = ' + JSON.stringify(scopeChange ?? null) + ';',
    'let asks = 0;',
    'const promptFactory = () => {',
    "  events.push({action: 'open'});",
    '  return {',
    '    async ask(question) {',
    "      events.push({action: 'ask', question: String(question), coreInstalled: fs.existsSync(" +
      JSON.stringify(path.join(f.root, '.agents/skills/skill-tree-plugins/SKILL.md')) + ')});',
    '      if (++asks === scopeChange?.at) {',
    '        const core = require(' + JSON.stringify(path.join(source, 'lib/installation.js')) + ');',
    '        const root = ' + JSON.stringify(f.root) + ';',
    '        const profile = core.receipt(root, true);',
    '        const owned = Object.entries(profile.destinations).flatMap(([rel, row]) =>',
    '          (row.providers || [row.provider]).map(provider => ({rel, name: row.name, provider})));',
    "        if (scopeChange.action === 'remove-provider') {",
    "          const claude = owned.filter(row => row.provider === 'claude-code');",
    "          if (!claude.length) throw Error('Fixture has no Claude destinations to remove');",
    '          core.uninstall(root, claude);',
    "        } else if (scopeChange.action === 'edit-source') {",
    '          fs.appendFileSync(scopeChange.file, scopeChange.append);',
    '        } else {',
    '          core.install(root, ' + JSON.stringify(source) + ", 'web', owned);",
    '        }',
    "        events.push({action: scopeChange.action});",
    '      }',
    "      if (!answers.length) throw Error('Unexpected prompt: ' + question);",
    '      return answers.shift();',
    '    },',
    "    close() { events.push({action: 'close'}); },",
    '  };',
    '};',
    'main(' + JSON.stringify(argv) + ', {promptFactory}).then(code => {',
    '  process.exitCode = code;',
    '}, error => { console.error(error.message); process.exitCode = 2; }).finally(() => {',
    '  fs.writeFileSync(' + JSON.stringify(transcript) + ', JSON.stringify({events, unused: answers}));',
    '});',
  ].join('\n'));
  const result = run(f, [], {file: fixture});
  const captured = JSON.parse(fs.readFileSync(transcript, 'utf8'));
  if (!allowUnused) assert.deepEqual(captured.unused, [], result.stderr + result.stdout);
  assert.equal(captured.events.filter(event => event.action === 'open').length, 1);
  assert.equal(captured.events.filter(event => event.action === 'close').length, 1);
  assert.equal(captured.events.at(-1).action, 'close');
  const questions = captured.events.filter(event => event.action === 'ask');
  assert.ok(questions.every(event => event.coreInstalled), 'Optional setup prompted before core installation');
  return {result, events: captured.events, questions: questions.map(event => event.question)};
}

test('ordinary interactive blank keeps the core-only default and closes the one prompt session', t => {
  const f = setup(t);
  const {result, questions} = interactive(f, [], ['']);
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(questions.length, 1);
  assert.match(questions[0], /continue|without|skip/i);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  assert.ok(core.verify(f.root, source).destinations['.agents/skills/' + managerName]);
  assertNoWorkflow(f);
});

test('initial interactive typed request uses the manager chain and cancelling later reorder preserves parked evidence', t => {
  const f = setup(t);
  const request = {action: 'install', request_id: 'interactive-exact-chain', sources: f.sources, bindings};
  const initial = interactive(f, ['--configure-plugins'], ['request', JSON.stringify(request), 'y']);
  assert.equal(initial.result.status, 0, initial.result.stderr + initial.result.stdout);
  assert.equal(initial.questions.length, 3);
  assert.match(initial.questions[0], /request|configure/i);
  assert.match(initial.questions[1], /JSON|request/i);
  assert.match(initial.questions[2], /apply|confirm|y\/N/i);
  for (const binding of bindings) assert.ok(initial.result.stdout.includes(binding.id), 'Preview omits ' + binding.id);
  for (const definition of f.sources) assert.ok(!initial.result.stdout.includes(definition.path));
  const installed = registry.verifyInstalled(f.root);
  assert.deepEqual(installed.bindings.map(row => [row.id, row.plugin_id, row.enabled, row.parameters]), bindings.map(
    row => [row.id, row.plugin_id, row.enabled, row.parameters]));
  const later = manager.managementInventory(f.root, {source});
  assert.deepEqual(later.points.find(row => row.boundary_id === op + ':after').bindings.map(row => row.id),
    bindings.map(row => row.id));
  assertNoWorkflow(f);

  // Retain a stopped original configuration as a controlled fixture. An
  // abandoned reorder must leave both the installed and frozen chain intact.
  const id = 'HC-' + require('node:crypto').randomUUID();
  const record = {schema: 1, id, revision: 1, state: 'cancelled', attempts: {}, stages: [],
    configuration: {packages: installed.packages, bindings: installed.bindings}};
  const chain_hash = registry.hash(JSON.stringify(JSON.parse(registry.json(record))));
  const parked = write(f.root, '.skill-tree/invocations/' + id.toLowerCase() + '.json', JSON.stringify({...record, chain_hash}));
  write(f.root, '.skill-tree/local/hook-locations/' + id.toLowerCase() + '.json', JSON.stringify({
    schema: 1, chain_id: id, canonical_root: f.root, execution_root: f.root,
  }));
  const runId = 'WR-' + require('node:crypto').randomUUID();
  const future = write(f.root, '.skill-tree/documents/future.json', JSON.stringify({
    format: 'skill-tree-future', schema: 3, active_run: null, tasks: [], task_progress: {},
    run_registry: {schema: 1, runs: {[runId]: {
      id: runId, phase: 'blocked', stop_reason: 'Preserved fixture handoff', hook_chains: [id],
    }}},
  }));
  const frozen = fs.readFileSync(parked), queue = fs.readFileSync(future), bytes = rawRegistry(f);
  const move = {action: 'move', request_id: 'interactive-cancelled-reorder', binding_id: 'editor-last', index: 0};
  const entry = path.join(f.root, '.agents/skills', managerName, 'scripts/plugin-manager.js');
  const installedPreview = spawnSync(process.execPath, ['--require', f.guard, entry,
    '--project-root', f.root, '--input', '-'], {
    cwd: f.base, input: JSON.stringify({action: 'prepare', request: move}), encoding: 'utf8',
    timeout: 30000, env: {...process.env, NODE_PATH: ''},
  });
  assert.equal(installedPreview.status, 0, installedPreview.stderr + installedPreview.stdout);
  const {proposal} = output(installedPreview);
  assert.match(proposal.digest, /^[a-f0-9]{64}$/);
  const cancelled = interactive(f, ['--configure-plugins'], ['request', JSON.stringify(move), '']);
  assert.equal(cancelled.result.status, 0, cancelled.result.stderr + cancelled.result.stdout);
  assert.match(cancelled.result.stdout, /cancel|skip/i);
  assert.ok(cancelled.result.stdout.includes(id), 'Reorder preview omits the affected frozen requirement');
  assert.ok(cancelled.result.stdout.includes(proposal.digest), 'Setup and the installed manager did not preview the same proposal');
  assert.deepEqual(rawRegistry(f), bytes);
  assert.deepEqual(fs.readFileSync(parked), frozen);
  assert.deepEqual(fs.readFileSync(future), queue);
  assert.equal(fs.existsSync(f.marker), false);
});

test('interactive EOF exits the optional stage without selecting a recommendation', t => {
  const f = setup(t);
  const {result, questions} = interactive(f, ['--configure-plugins'], [null]);
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(questions.length, 1);
  assert.doesNotMatch(result.stdout, /"status":\s*"installed"/i);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  assertNoWorkflow(f);
});

test('optional plugin confirmation refreshes from the installed core after a source checkout edit', t => {
  const f = setup(t), checkout = path.join(f.base, 'checkout');
  for (const relative of ['common', 'config', 'domains', 'lib', 'src', 'templates', 'skills/general']) {
    fs.cpSync(path.join(source, relative), path.join(checkout, relative), {recursive: true});
  }
  const resource = 'common/references/decision-governance.md';
  const original = fs.readFileSync(path.join(checkout, resource));
  const request = {action: 'install', request_id: 'install-on-verified-core', sources: f.sources, bindings};
  const {result, events} = interactive(f, ['--source', checkout, '--configure-plugins'], ['request', JSON.stringify(request), 'y'], {
    scopeChange: {at: 3, action: 'edit-source', file: path.join(checkout, resource), append: '\nUnreviewed source edit.\n'},
  });
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.ok(events.some(event => event.action === 'edit-source'));
  const stage = JSON.parse(result.stdout.slice(result.stdout.lastIndexOf('\n{') + 1)).plugin_stage;
  assert.equal(stage.status, 'installed');
  assert.equal(stage.profile, 'current');
  const owned = '.skill-tree/installation/source';
  assert.deepEqual(fs.readFileSync(path.join(f.root, owned, resource)), original);
  assert.notDeepEqual(fs.readFileSync(path.join(checkout, resource)), original);
  const receipt = core.verify(f.root, source);
  assert.equal(receipt.source_digests[resource], registry.hash(original));
  assert.deepEqual(registry.verifyInstalled(f.root).bindings.map(row => row.id), bindings.map(row => row.id));
  assertNoWorkflow(f);
});

test('known browsing offers grouped alternatives and a direct local source can install repeated occurrences', t => {
  const f = setup(t);
  const browse = interactive(f, ['--configure-plugins'], ['known', '']);
  assert.equal(browse.result.status, 0, browse.result.stderr + browse.result.stdout);
  assert.match(browse.questions[0], /known.*custom.*request/i);
  assert.doesNotMatch(browse.questions[0], /recommended/i);
  assert.match(browse.result.stdout, /Catalog suggestions by integration point/);
  assert.match(browse.result.stdout, /skill-tree-process-future-pending:after/);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);

  const directBindings = [bindings[0], bindings[2]];
  const custom = interactive(f, ['--configure-plugins'], [
    'custom', JSON.stringify(f.sources[0]), JSON.stringify(directBindings), 'y',
  ]);
  assert.equal(custom.result.status, 0, custom.result.stderr + custom.result.stdout);
  assert.match(custom.questions[1], /source.*local|local.*source/i);
  assert.match(custom.questions[2], /ordered bindings/i);
  assert.deepEqual(registry.verifyInstalled(f.root).bindings.map(row => [row.id, row.parameters]), directBindings.map(
    row => [row.id, row.parameters]));
  assertNoWorkflow(f);
});

test('a typed remote request still requires the separate online resolution choice', t => {
  const f = setup(t);
  const request = {
    action: 'install', request_id: 'remote-no-consent',
    sources: [{id: 'remote-fixture', url: 'https://example.invalid/SKILL.md'}],
    resolve_remote: true,
  };
  const {result, questions} = interactive(f, ['--configure-plugins'], ['request', JSON.stringify(request), '']);
  assert.equal(result.status, 0, result.stderr + result.stdout);
  assert.equal(questions.length, 3);
  assert.match(questions[2], /online|remote/i);
  assert.doesNotMatch(result.stdout + result.stderr, /unexpected network acquisition/i);
  assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  assertNoWorkflow(f);
});

for (const [action, only, flavor] of [
  ['remove-provider', ['codex', 'claude-code'], 'general'],
  ['switch-flavor', ['codex'], 'web'],
]) {
  test(action + ' during prompt preparation blocks plugin activation', t => {
    const f = setup(t);
    const request = {action: 'install', request_id: action + '-during-prompt', sources: f.sources, bindings};
    const {result, events} = interactive(f, ['--configure-plugins'], ['request', JSON.stringify(request), 'y'], {
      only, scopeChange: {at: 2, action}, allowUnused: true,
    });
    assert.ok(events.some(event => event.action === action));
    assert.notEqual(result.status, 0, result.stderr + result.stdout);
    const stage = JSON.parse(result.stdout.slice(result.stdout.lastIndexOf('\n{') + 1)).plugin_stage;
    assert.equal(stage.status, 'blocked');
    assert.match(stage.reason, /scope|destination|provider|flavor/i);
    assert.equal(stage.receipt, undefined);
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
    const profile = core.receipt(f.root, true);
    assert.equal(profile.flavor, flavor);
    assert.ok(profile.destinations['.agents/skills/' + managerName]);
    assert.ok(!profile.destinations['.claude/skills/' + managerName]);
    assertNoWorkflow(f);
  });
}

test('offline dry-run rejects digest-correct malformed manager envelopes without writes', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const proposal = await installProposal(f);
  const missingNested = structuredClone(proposal);
  delete missingNested.mutation.proposal;
  const wrongAction = {...proposal, action: 'uninstall'};
  const hiddenBindings = structuredClone(proposal);
  hiddenBindings.preview.bindings = [];
  const lifecycle = hiddenBindings.mutation.proposal;
  lifecycle.manager_preview_digest = registry.hash(registry.json(hiddenBindings.preview));
  lifecycle.digest = require('../lib/plugin-lifecycle.js').proposalDigest(lifecycle);
  const before = core.treeHash(f.root, '.skill-tree');
  for (const malformed of [missingNested, wrongAction, hiddenBindings]) {
    delete malformed.digest;
    malformed.digest = registry.hash(registry.json(malformed));
    const file = store(f, malformed);
    for (const flags of malformed === hiddenBindings ? [['--dry-run'], []] : [['--dry-run']]) {
      const result = run(f, [...flags, ...confirm(file, malformed)]);
      assert.notEqual(result.status, 0, result.stderr + result.stdout);
      assert.equal(stage(result).plugins.status, 'blocked');
      assert.equal(core.treeHash(f.root, '.skill-tree'), before);
    }
  }
  assertNoWorkflow(f);
});

test('legacy core-only invocation resolves a symlink target before selecting provider paths', t => {
  const f = setup(t);
  const alias = path.join(f.base, 'target-alias');
  fs.symlinkSync(f.root, alias, 'dir');
  const installed = run({...f, root: alias}, ['--yes']);
  assert.equal(installed.status, 0, installed.stderr + installed.stdout);
  assert.ok(Array.isArray(output(installed)));
  assert.equal(core.receipt(f.root, true).project_root, f.root);
  assert.ok(fs.existsSync(path.join(f.root, '.agents/skills', managerName, 'SKILL.md')));
  assertNoWorkflow(f);
});

test('a rehashed incomplete save-known entry cannot pass offline inspection or live application', async t => {
  const f = setup(t);
  assert.equal(run(f, ['--yes']).status, 0);
  const prepared = await manager.prepareManagerRequest(f.root, {
    action: 'save-known', request_id: 'incomplete-known-entry', source: f.sources[0],
  }, {source});
  assert.equal(prepared.status, 'ready');
  const malformed = structuredClone(prepared.proposal);
  delete malformed.mutation.entry.suggested_locations;
  delete malformed.preview.known.suggested_locations;
  delete malformed.digest;
  malformed.digest = registry.hash(registry.json(malformed));
  const file = store(f, malformed);
  const before = core.treeHash(f.root, '.skill-tree');
  for (const flags of [['--dry-run'], []]) {
    const rejected = run(f, [...flags, ...confirm(file, malformed)]);
    assert.notEqual(rejected.status, 0, rejected.stderr + rejected.stdout);
    assert.ok(['blocked', 'failed'].includes(stage(rejected).plugins.status));
    assert.equal(core.treeHash(f.root, '.skill-tree'), before);
    assert.equal(fs.existsSync(path.join(f.root, '.skill-tree/installation/plugin-known.json')), false);
    assert.equal(fs.existsSync(path.join(f.root, registry.REGISTRY)), false);
  }
  assertNoWorkflow(f);
});
