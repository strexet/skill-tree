'use strict';

const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const childProcess = require('node:child_process');
const c = require('./composer.js');
const core = require('./installation.js');

const PROFILE = core.PROFILE;
const BUNDLE = core.INSTALL + '/source';
const FUTURE = '.skill-tree/documents/future.md';
const WORKFLOW = '.skill-tree/documents/future.json';
const HISTORY = '.skill-tree/history';
const SNAPSHOT = 'skill-tree-create-documents-snapshot';
const SNAPSHOT_HELPER = 'scripts/create-documentation-snapshot.py';
const README = 'README.md';
const SCENARIO = {
  id: 'director-documentation-snapshot-readme',
  recipe_id: 'director-snapshot-canary',
  lane: 'unit',
  assertion_id: 'snapshot-scope-preserves-markdown-extension',
  assertion: 'The dry-run report preserves the Markdown extension of README.md.',
};

function requireCanary(condition, message) {
  if (!condition) throw Error(message);
}

const seal = value => c.hash(c.json(value));
const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
const token = value => typeof value === 'string' && /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(value);
const identity = (value, prefix) => typeof value === 'string' &&
  new RegExp('^' + prefix + '-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$').test(value);
const own = (value, key) => Object.hasOwn(value, key);

function object(value, fields) {
  requireCanary(value && typeof value === 'object' && !Array.isArray(value) &&
    Object.keys(value).length === fields.length && fields.every(field => own(value, field)),
  'Unexpected canary request fields');
}

function same(first, second) {
  return c.json(first) === c.json(second);
}

function exactDirectory(location) {
  requireCanary(typeof location === 'string' && path.isAbsolute(location) &&
    fs.realpathSync(location) === location && fs.statSync(location).isDirectory(), 'Use an exact local directory');
  return location;
}

function read(root, relative) {
  const location = c.safe(root, relative);
  return fs.existsSync(location) ? fs.readFileSync(location) : null;
}

function sha(root, relative) {
  const content = read(root, relative);
  return content === null ? null : c.hash(content);
}

function git(root, ...args) {
  const env = {...process.env};
  const config = ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY',
    'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_NAMESPACE', 'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG'];
  // Match Python os.devnull, including Git's 'nul' spelling on Windows.
  const nullDevice = process.platform === 'win32' ? 'nul' : os.devNull;
  const blocked = config.find(key => own(env, key)) || ['GIT_CONFIG_GLOBAL', 'GIT_CONFIG_SYSTEM']
    .find(key => own(env, key) && env[key] !== nullDevice);
  requireCanary(!blocked, 'Clear the inherited Git override ' + blocked + ' for the canary');
  const count = env.GIT_CONFIG_COUNT ?? '0';
  requireCanary(/^(0|[1-9][0-9]{0,2})$/.test(count), 'Invalid inherited Git configuration count');
  delete env.GIT_CONFIG_COUNT;
  for (let index = 0; index < Number(count); index++) {
    const key = 'GIT_CONFIG_KEY_' + index;
    const value = 'GIT_CONFIG_VALUE_' + index;
    const presentation = /^color\.(ui|branch|diff|status)$/i.test(env[key] || '');
    const remote = /^(credential\.https?:\/\/[^\s]+\.(helper|useHttpPath)|http\.https?:\/\/[^\s]+\.(proactiveAuth|followRedirects|extraHeader))$/i.test(env[key] || '');
    requireCanary(own(env, value) && (presentation || remote), 'Unsupported inherited Git setting at index ' + index);
    delete env[key];
    delete env[value];
  }
  requireCanary(!Object.keys(env).some(key => /^GIT_CONFIG_(KEY|VALUE)_/.test(key)),
    'Unexpected inherited Git configuration entries outside GIT_CONFIG_COUNT');
  const result = childProcess.spawnSync('git', ['--no-replace-objects', '--no-optional-locks', '-C', root,
    '-c', 'core.fsmonitor=false', ...args], {env, encoding: 'utf8', timeout: 5000});
  requireCanary(result.status === 0, 'The exact canary Git workspace is unavailable');
  return result.stdout.trim();
}

function readCandidate(value, expected, source) {
  requireCanary(value?.schema === 1 && value.kind === 'director-source-repair-candidate' &&
    hash(expected) && value.candidate_sha256 === expected, 'Select the reviewed source candidate');
  const {candidate_sha256, ...body} = value;
  requireCanary(seal(body) === candidate_sha256 && hash(value.finding_sha256) &&
    value.owner && value.review && value.route, 'The reviewed source candidate digest changed');
  const sourceDigest = seal(c.sourceInputs(source));
  requireCanary(value.source?.source_inventory_sha256 === sourceDigest &&
    value.source.revision === 'source-inventory:' + sourceDigest, 'The candidate source inventory changed');
  requireCanary(token(value.packages?.provider) && value.packages.provider !== 'generic' && token(value.packages.flavor) &&
    hash(value.packages.environment_id) && hash(value.review.before_sha256) && hash(value.review.after_sha256) &&
    value.review.before_sha256 !== value.review.after_sha256 &&
    value.packages.output_digests?.[SNAPSHOT]?.[SNAPSHOT_HELPER] === value.review.after_sha256,
  'The candidate requires a reviewed composition for the selected host');
  requireCanary(Object.entries(SCENARIO).every(([key, item]) => value.scenario?.[key] === item) &&
    hash(value.scenario.input_sha256), 'The exact original canary scenario is unavailable');
  for (const [role, result] of [['original', 'fail'], ['repaired', 'pass']]) {
    const check = value.checks?.[role];
    const proof = check?.evidence;
    requireCanary(check?.result === result && check.scenario_sha256 === seal(value.scenario) &&
      hash(check.record_sha256) && identity(check.attempt_id, 'C') && proof && typeof proof.path === 'string' &&
      hash(proof.sha256) && proof.path.split('/').every(part => part && !['.', '..'].includes(part) && !/[\\:\x00]/.test(part)),
    'Candidate lacks same-scenario source repair evidence');
  }
  requireCanary(value.checks.original.attempt_id !== value.checks.repaired.attempt_id,
    'Original failure and repaired proof need separate executed attempts');
  return value;
}

function targetState(root, scope) {
  object(scope, ['queue_id', 'run_id', 'task_id', 'flavor', 'provider', 'authority_ref', 'preserve_paths']);
  requireCanary(identity(scope.queue_id, 'Q') && identity(scope.run_id, 'WR') &&
    identity(scope.task_id, 'T') && token(scope.provider) && scope.provider !== 'generic' && token(scope.flavor) &&
    token(scope.authority_ref), 'Select exact scoped canary authority, child run and host profile');
  requireCanary(git(root, 'rev-parse', '--show-toplevel') === root, 'Select the exact canary checkout');
  const common = fs.realpathSync(path.resolve(root, git(root, 'rev-parse', '--git-common-dir')));
  const locatorFile = c.safe(common, 'skill-tree-runtime.json');
  const locator = JSON.parse(fs.readFileSync(locatorFile));
  const owner = exactDirectory(locator.canonical_root);
  requireCanary(locator.schema === 1 && locator.queue_id === scope.queue_id &&
    locator.worktrees?.[scope.run_id] === root && core.queueRoot(root) === owner &&
    fs.realpathSync(path.resolve(owner, git(owner, 'rev-parse', '--git-common-dir'))) === common,
  'The target is not the original exact canary workspace and canonical queue');
  const state = core.workflowState(root);
  const run = state?.run_registry?.runs?.[scope.run_id];
  requireCanary(state?.run_registry?.queue_id === scope.queue_id && run?.id === scope.run_id &&
    run.current_task_id === scope.task_id && run.workspace_state === 'ready' &&
    run.workspace?.worktree_id === scope.run_id &&
    run.workspace.branch === git(root, 'symbolic-ref', '--short', 'HEAD') &&
    run.workspace.repo_id === c.hash(git(root, 'rev-list', '--max-parents=0', 'HEAD')),
  'The selected canary run, task or workspace changed');
  return {owner, run, state, locator_sha256: c.hash(fs.readFileSync(locatorFile))};
}

function stopped(root, run) {
  requireCanary(typeof run.stop_reason === 'string' && run.stop_reason &&
    !run.director_question_hold && !run.maintenance && !core.hasActiveOperation(root),
  'The original canary run needs an explicit stopped installation handoff');
}

function preserve(root, owner, paths) {
  requireCanary(Array.isArray(paths) && new Set(paths).size === paths.length,
    'Preservation paths require unique project-relative references');
  const target = {};
  for (const relative of [README, '.skill-tree/installation/plugins.json', ...paths]) {
    requireCanary(typeof relative === 'string' && relative &&
      !relative.startsWith('.agents/skills/') && !relative.startsWith(core.INSTALL + '/source/'),
    'Preservation paths cannot select an owned installation destination');
    target[relative] = core.treeHash(root, relative);
  }
  return {target, authority: Object.fromEntries(
    [FUTURE, '.skill-tree/director', '.skill-tree/invocations'].map(
      relative => [relative, core.treeHash(owner, relative)])), history: core.filesAt(owner, HISTORY) || {}};
}

function profileProof(root, scope) {
  const profile = core.verify(root, c.safe(root, BUNDLE));
  requireCanary(profile.flavor === scope.flavor, 'The selected flavor differs from the owned profile');
  // core.verify checked every provider ID, destination, composed package and content hash.
  const selections = Object.entries(profile.destinations).flatMap(([rel, record]) =>
    (record.providers || [record.provider]).map(provider => ({rel, name: record.name, provider})));
  const snapshot = selections.find(item => item.provider === scope.provider && item.name === SNAPSHOT);
  requireCanary(snapshot, 'The selected host does not own the operation required for canary replay');
  return {profile, selections, snapshot};
}

function frozenGeneration(profile) {
  return {
    identity: profile.identity, environment_id: profile.environment_id,
    source_inventory_sha256: seal(profile.source_digests),
    output_digests: Object.fromEntries(Object.values(profile.destinations).map(row => [row.name, row.files])),
  };
}

function planTrees(plan) {
  function next(value) {
    if (value === null) return null;
    if (typeof value === 'string' || Buffer.isBuffer(value)) return seal({'': c.hash(value)});
    return seal(Object.fromEntries(Object.entries(value).map(([key, data]) => [key, c.hash(data)])));
  }
  return plan.delta.map(relative => ({dest: relative, old: plan.expected[relative], next: next(plan.changes[relative])}))
    .sort((left, right) => left.dest.localeCompare(right.dest));
}

function independentState(state, runId, admissionEvent = null) {
  const independent = structuredClone(state);
  delete independent.run_registry.runs[runId];
  delete independent.run_registry.event_sequences[runId];
  if (admissionEvent) independent.run_registry.applied_events =
    independent.run_registry.applied_events.filter(event => event !== admissionEvent);
  return seal(independent);
}

function preview(root, source, candidate, scope, expectedCandidate) {
  root = exactDirectory(root);
  source = exactDirectory(source);
  requireCanary(root !== source, 'Select the distinct candidate source and canary checkout');
  const pinned = readCandidate(candidate, expectedCandidate, source);
  const {owner, run, state, locator_sha256} = targetState(root, scope);
  stopped(root, run);
  requireCanary(pinned.packages.flavor === scope.flavor && pinned.packages.provider === scope.provider,
    'Candidate composition does not match the selected flavor and provider');
  const {profile, selections, snapshot: selected} = profileProof(root, scope);
  const snapshot = profile.destinations[selected.rel];
  requireCanary(run.admission?.identity === profile.identity && sha(root, README) === pinned.scenario.input_sha256 &&
    snapshot?.files?.[SNAPSHOT_HELPER] === pinned.review.before_sha256,
    'Current previous generation or same-scenario input is unavailable');
  const dry = core.plan(root, source, scope.flavor, selections);
  const generation = frozenGeneration(dry.profile);
  requireCanary(generation.source_inventory_sha256 === pinned.source.source_inventory_sha256 &&
    generation.environment_id === pinned.packages.environment_id &&
    same(generation.output_digests, pinned.packages.output_digests), 'Exact candidate output generation differs');
  requireCanary(dry.delta.length && dry.delta.includes(PROFILE), 'Exact candidate is already installed or would have no effect');
  for (const relative of scope.preserve_paths || []) {
    requireCanary(!Object.keys(profile.destinations).some(dest => relative === dest || relative.startsWith(dest + '/')),
      'Preservation paths cannot select an owned installation destination');
  }
  const business = preserve(root, owner, scope.preserve_paths);
  requireCanary(!dry.delta.some(relative => own(business.target, relative) ||
    [FUTURE, '.skill-tree/history', '.skill-tree/director', '.skill-tree/invocations'].includes(relative)),
  'Candidate writes outside the selected owned installation scope');
  let nextWorkflow = sha(owner, WORKFLOW);
  if (dry.delta.includes(WORKFLOW)) {
    requireCanary(root === owner, 'A linked canary cannot replace the canonical workflow');
    const predicted = JSON.parse(dry.changes[WORKFLOW]);
    const expected = structuredClone(state);
    expected.run_registry.runs[scope.run_id].profile_refresh_required = true;
    requireCanary(same(predicted, expected), 'The installer would modify an independent canonical checkpoint');
    nextWorkflow = c.hash(dry.changes[WORKFLOW]);
  }
  const report = {
    schema: 1, kind: 'director-canary-preview', candidate_sha256: expectedCandidate, scenario_sha256: seal(pinned.scenario),
    target_sha256: seal({root, owner, locator_sha256}), scope, workspace: run.workspace,
    host_destinations: Object.fromEntries(Object.entries(profile.destinations).map(([rel, row]) =>
      [rel, row.providers || [row.provider]])),
    original_run: run, before_profile_sha256: sha(root, PROFILE), generation,
    independent_state_sha256: independentState(state, scope.run_id),
    run_event_sequence: state.run_registry.event_sequences?.[scope.run_id] || 0,
    installed_profile_sha256: c.hash(dry.changes[PROFILE]), protected: business,
    before_workflow_sha256: sha(owner, WORKFLOW), installed_workflow_sha256: nextWorkflow,
    entries: planTrees(dry),
  };
  return {...report, preview_sha256: seal(report)};
}

function reviewed(root, view, expected, {admitted = false} = {}) {
  const report = {...view};
  delete report.preview_sha256;
  requireCanary(view?.schema === 1 && view.kind === 'director-canary-preview' &&
    hash(expected) && view.preview_sha256 === expected && seal(report) === expected, 'Use the exact reviewed canary preview');
  const now = targetState(root, view.scope);
  requireCanary(seal({root, owner: now.owner, locator_sha256: now.locator_sha256}) === view.target_sha256 &&
    same(now.run.workspace, view.workspace), 'The original canary destination or workspace changed');
  const observed = preserve(root, now.owner, view.scope.preserve_paths);
  if (admitted) {
    const additions = Object.keys(observed.history).filter(file => !own(view.protected.history, file));
    requireCanary(additions.length === 1 && additions[0].startsWith('run-events/' + view.scope.run_id.toLowerCase() + '/'),
      'Replay requires the exact current Core admission event');
    const relative = HISTORY + '/' + additions[0];
    const event = c.readJson(now.owner, relative);
    requireCanary(event?.schema === 1 && identity(event.id, 'E') && event.run_id === view.scope.run_id &&
      event.queue_id === view.scope.queue_id && event.sequence === view.run_event_sequence + 1 &&
      now.state.run_registry.event_sequences?.[event.run_id] === event.sequence &&
      now.state.run_registry.applied_events?.at(-1) === event.id && same(event.checkpoint_before, view.original_run) &&
      same(event.checkpoint_after, now.run) && [event.changes, event.progress_changes, event.outcomes].every(
        changes => Array.isArray(changes) && !changes.length) &&
      independentState(now.state, view.scope.run_id, event.id) === view.independent_state_sha256,
    'The admission event changed unrelated controller state');
    delete observed.history[additions[0]];
  }
  requireCanary(same(observed, view.protected), 'Protected project, queue, plugin or history state changed');
  return now;
}

function installed(root, view, expected, {admitted = false} = {}) {
  const current = reviewed(root, view, expected, {admitted});
  const {profile} = profileProof(root, view.scope);
  requireCanary(sha(root, PROFILE) === view.installed_profile_sha256 &&
    same(frozenGeneration(profile), view.generation), 'Mixed or different installed candidate generation');
  if (admitted) {
    requireCanary(current.run.admission?.identity === profile.identity &&
      current.run.admission.environment_id === profile.environment_id && !current.run.profile_refresh_required,
    'Explicitly re-admit the same original run before replay');
    const accepted = {...current.run};
    accepted.admission = view.original_run.admission;
    delete accepted.profile_refresh_required;
    const original = {...view.original_run};
    delete original.profile_refresh_required;
    requireCanary(same(accepted, original), 'The re-admitted checkpoint changed beyond installation admission');
  } else {
    requireCanary(sha(current.owner, WORKFLOW) === view.installed_workflow_sha256,
      'Canonical state changed during candidate activation');
  }
  return {current, profile};
}

function apply(root, source, candidate, view, expected) {
  root = exactDirectory(root);
  source = exactDirectory(source);
  const current = reviewed(root, view, expected);
  stopped(root, current.run);
  readCandidate(candidate, view.candidate_sha256, source);
  if (sha(root, PROFILE) === view.installed_profile_sha256) {
    installed(root, view, expected);
    return {status: 'installed', acknowledgement: 'recovered-exact-candidate', replay_status: 'required', wider_rollout: 'held'};
  }
  requireCanary(sha(root, PROFILE) === view.before_profile_sha256, 'Previous canary profile changed');
  requireCanary(preview(root, source, candidate, view.scope, view.candidate_sha256).preview_sha256 === expected,
    'Reviewed preview is stale');
  const {selections} = profileProof(root, view.scope);
  core.install(root, source, view.scope.flavor, selections, {
    recoverPending: false, recoverPluginPending: false,
    guardPlan: result => {
      const current = reviewed(root, view, expected);
      stopped(root, current.run);
      requireCanary(sha(root, PROFILE) === view.before_profile_sha256 &&
        sha(current.owner, WORKFLOW) === view.before_workflow_sha256 &&
        seal(c.sourceInputs(source)) === view.generation.source_inventory_sha256 &&
        same(frozenGeneration(result.profile), view.generation) && same(planTrees(result), view.entries),
      'The exact activation plan changed at the owned installer boundary');
    },
  });
  installed(root, view, expected);
  return {status: 'installed', acknowledgement: 'observed', replay_status: 'required', wider_rollout: 'held'};
}

function matchingJournal(root, view, relative) {
  const journal = c.readJson(root, relative, null);
  const entries = journal?.entries?.map(({dest, old, next}) => ({dest, old, next}))
    .sort((left, right) => left.dest.localeCompare(right.dest));
  requireCanary(journal?.schema === 1 && journal.channel === 'core' && journal.project_root === root &&
    entries && same(entries, view.entries), 'The retained journal does not belong to the exact preview');
  return sha(root, relative);
}

function reconcile(root, view, expected) {
  root = exactDirectory(root);
  const selected = targetState(root, view.scope);
  const admitted = selected.run.admission?.identity === view.generation.identity;
  const current = reviewed(root, view, expected, {admitted});
  const relative = core.transactionPaths().journal;
  if (read(root, relative) !== null) {
    stopped(root, current.run);
    return {status: 'recovery-required', journal_sha256: matchingJournal(root, view, relative),
      replay_status: 'held', wider_rollout: 'held'};
  }
  if (sha(root, PROFILE) === view.installed_profile_sha256) {
    installed(root, view, expected, {admitted});
    return {status: 'installed', acknowledgement: 'recovered-exact-candidate',
      replay_status: 'required', wider_rollout: 'held'};
  }
  const {profile} = profileProof(root, view.scope);
  requireCanary(sha(root, PROFILE) === view.before_profile_sha256 &&
    profile.identity === current.run.admission?.identity && sha(current.owner, WORKFLOW) === view.before_workflow_sha256,
  'Mixed or unknown canary state requires original owned installation review');
  return {status: 'not-activated', replay_status: 'held', wider_rollout: 'held'};
}

function recover(root, view, expected, journalDigest) {
  root = exactDirectory(root);
  const relative = core.transactionPaths().journal;
  const current = reviewed(root, view, expected);
  stopped(root, current.run);
  requireCanary(hash(journalDigest) && matchingJournal(root, view, relative) === journalDigest,
    'Select the exact interrupted canary journal digest');
  core.locked(root, () => { throw Error('Original interrupted canary journal is no longer pending'); }, {
    recoverPending: false, recoverPluginPending: false,
    onPending: () => {
      const inspected = reviewed(root, view, expected);
      stopped(root, inspected.run);
      requireCanary(matchingJournal(root, view, relative) === journalDigest, 'Original journal changed before recovery');
      core.recover(root);
    },
  });
  installed(root, view, expected);
  return {status: 'installed', acknowledgement: 'reconciled-owned-journal', replay_status: 'required', wider_rollout: 'held'};
}

function replayCause(execution) {
  if (execution.error?.code === 'ETIMEDOUT') return 'timed-out';
  if (execution.error?.code === 'ENOBUFS') return 'unexpected-output';
  if (execution.error) return 'launch-error';
  if (execution.status !== 0) return 'exit-failure';
  const lines = (execution.stdout || '').trim().split(/\r?\n/);
  return /^archive: /.test(lines[0]) && same(lines.slice(1), ['included: 1', '- README.md'])
    ? 'verified' : 'unexpected-output';
}

function replay(root, source, candidate, view, expected) {
  root = exactDirectory(root);
  source = exactDirectory(source);
  const pinned = readCandidate(candidate, view.candidate_sha256, source);
  const {current, profile} = installed(root, view, expected, {admitted: true});
  stopped(root, current.run);
  requireCanary(seal(pinned.scenario) === view.scenario_sha256 && sha(root, README) === pinned.scenario.input_sha256,
    'The exact original scenario input changed');
  const entry = Object.entries(profile.destinations).find(([, record]) =>
    record.name === SNAPSHOT && (record.providers || [record.provider]).includes(view.scope.provider));
  const helper = entry[0] + '/' + SNAPSHOT_HELPER;
  requireCanary(sha(root, helper) === pinned.packages.output_digests[SNAPSHOT][SNAPSHOT_HELPER],
    'The installed candidate helper bytes changed');
  const before = {workflow: sha(current.owner, WORKFLOW), outputs: core.treeHash(root, '.skill-tree/artifacts')};
  const started = performance.now();
  const execution = childProcess.spawnSync('python3', ['-B', c.safe(root, helper), root, '--dry-run', '--include',
    README, '--timestamp', '2000-01-01-00-00'], {cwd: root, encoding: 'utf8', timeout: 30000});
  const duration_ms = Math.round(performance.now() - started);
  const cause = replayCause(execution);
  const outcome = cause === 'verified';
  const after = installed(root, view, expected, {admitted: true});
  requireCanary(before.workflow === sha(after.current.owner, WORKFLOW) &&
    before.outputs === core.treeHash(root, '.skill-tree/artifacts'), 'The read-only original scenario caused an unrelated effect');
  return {
    status: outcome ? 'verified-replay' : 'rollout-held', lane: pinned.scenario.lane,
    candidate_sha256: view.candidate_sha256, recipe_id: pinned.scenario.recipe_id, scenario_sha256: view.scenario_sha256,
    run_id: view.scope.run_id, profile_identity: profile.identity, exit_code: execution.status,
    observation: outcome ? 'markdown-extension-preserved' : 'original-scenario-not-verified',
    diagnostic: {cause, duration_ms},
    wider_rollout: 'separate-authority-required',
  };
}

function rollbackPreview(root, view, expected) {
  root = exactDirectory(root);
  const selected = targetState(root, view.scope);
  const admitted = selected.run.admission?.identity === view.generation.identity;
  const current = reviewed(root, view, expected, {admitted});
  stopped(root, current.run);
  const generation = installed(root, view, expected, {admitted});
  const journal_sha256 = matchingJournal(root, view, core.transactionPaths().last);
  const report = {schema: 1, preview_sha256: expected, journal_sha256, profile_identity: generation.profile.identity,
    workflow_sha256: sha(current.owner, WORKFLOW), target_sha256: view.target_sha256};
  return {...report, rollback_sha256: seal(report)};
}

function rollback(root, view, expected, expectedRollback) {
  root = exactDirectory(root);
  requireCanary(hash(expectedRollback), 'Select the exact reviewed rollback');
  core.rollback(root, {guard: () => {
    requireCanary(rollbackPreview(root, view, expected).rollback_sha256 === expectedRollback,
      'The exact rollback basis changed');
  }});
  const selected = targetState(root, view.scope);
  const current = reviewed(root, view, expected, {admitted: selected.run.admission?.identity === view.generation.identity});
  const {profile} = profileProof(root, view.scope);
  requireCanary(sha(root, PROFILE) === view.before_profile_sha256, 'Original owned generation was not restored exactly');
  requireCanary(current.run.id === view.scope.run_id && same(current.run.workspace, view.workspace),
    'Rollback did not preserve the original controller');
  return {status: 'rolled-back', profile_identity: profile.identity, run_id: current.run.id,
    admission: 'explicit-current-admission-required', wider_rollout: 'held'};
}

function main(argv) {
  requireCanary(argv.length === 3 && argv[1] === '--input', 'Select one canary action and --input <request.json>');
  const [command, , input] = argv;
  const request = JSON.parse(fs.readFileSync(input));
  const needsCandidate = ['apply', 'replay'].includes(command);
  const known = {preview, apply, reconcile, recover, replay, 'rollback-preview': rollbackPreview, rollback};
  requireCanary(own(known, command), 'Unknown canary action');
  if (command === 'preview') {
    object(request, ['target', 'source', 'candidate', 'scope', 'expected_candidate_sha256']);
    return preview(request.target, request.source, request.candidate, request.scope, request.expected_candidate_sha256);
  }
  const base = ['target', 'reviewed_preview', 'expected_preview_sha256'];
  const extra = needsCandidate ? ['source', 'candidate'] : command === 'recover' ? ['journal_sha256'] :
    command === 'rollback' ? ['expected_rollback_sha256'] : [];
  object(request, [...base, ...extra]);
  const args = [request.reviewed_preview, request.expected_preview_sha256];
  if (needsCandidate) return known[command](request.target, request.source, request.candidate, ...args);
  return known[command](request.target, ...args, request[extra[0]]);
}

if (require.main === module) {
  try {
    process.stdout.write(c.json(main(process.argv.slice(2))));
  } catch (error) {
    process.stderr.write(error.message + '\n');
    process.exitCode = 2;
  }
}

module.exports = {preview, apply, reconcile, recover, replay, rollbackPreview, rollback};
