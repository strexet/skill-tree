'use strict';

const fs = require('node:fs');
const {spawnSync} = require('node:child_process');
const {CONFIG, configuration, effective} = require('./development-policies.js');
const {safe, relative, hash, json} = require('./plugin-registry.js');

const DECLARATIONS = '.skill-tree/api-contracts.json';
const SELECTOR = /^(GET|PUT|POST|DELETE|OPTIONS|HEAD|PATCH|TRACE) (\/[^\s]*)$/;
const OID = /^[a-f0-9]{40}(?:[a-f0-9]{24})?$/;
const NAME = /^[A-Za-z0-9][A-Za-z0-9._:-]*$/;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const read = (root, file) => {
  const location = safe(root, file);
  return fs.existsSync(location) ? fs.readFileSync(location, 'utf8') : null;
};

function gitResult(root, args, encoding = 'utf8') {
  return spawnSync('git', ['--no-replace-objects', '-C', root, ...args],
    {encoding, timeout: 10000, maxBuffer: 4 * 1024 * 1024});
}

function git(root, args, encoding) {
  const result = gitResult(root, args, encoding);
  if (result.status !== 0) throw Error('Required Git object is unavailable for API lock verification');
  return result.stdout;
}

function revision(root, ref) {
  if (typeof ref !== 'string' || !ref || /[\s\0]/.test(ref)) throw Error('Select a Git commit or tag as the API baseline');
  const oid = git(root, ['rev-parse', '--verify', '--end-of-options', ref + '^{commit}']).trim();
  if (!OID.test(oid)) throw Error('API lock baseline must resolve to an exact Git commit');
  return oid;
}

const namedObjects = new Set(['properties', 'patternProperties', '$defs', 'definitions', 'dependentSchemas',
  'content', 'headers', 'encoding', 'callbacks', 'links', 'responses', 'paths', 'webhooks', 'examples', 'parameters']);
const literalValues = new Set(['example', 'default', 'enum', 'const', 'value']);

function exactDecimal(value) {
  const [, sign, whole, fraction = '', exponent = '0'] = /^(-?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/i.exec(value);
  const digits = (whole + fraction).replace(/^0+/, '');
  if (!digits) return '0';
  const significant = digits.replace(/0+$/, '');
  return sign + significant + ':' + (BigInt(exponent) - BigInt(fraction.length) + BigInt(digits.length - significant.length));
}

const unsafeNumber = Symbol('unsafe OpenAPI number');
const jsonToken = /"(?:[^"\\]|\\[\s\S])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;

function parseOpenApi(text) {
  const doc = JSON.parse(text);
  const strings = new Set();
  const unsafe = [];
  for (const token of text.matchAll(jsonToken)) {
    if (token[0][0] === '"') {
      strings.add(JSON.parse(token[0]));
      continue;
    }
    const number = Number(token[0]);
    if (!Number.isFinite(number) || (Number.isInteger(number) && !Number.isSafeInteger(number)) ||
        exactDecimal(token[0]) !== exactDecimal(String(number))) unsafe.push(token);
  }
  if (!unsafe.length) return doc;
  // Mark unrepresentable values before parsing so unrelated operations can still be compared.
  let marker = '\u0000';
  while (strings.has(marker)) marker += '\u0000';
  const encoded = JSON.stringify(marker);
  const fragments = [];
  let cursor = 0;
  for (const token of unsafe) {
    fragments.push(text.slice(cursor, token.index), encoded);
    cursor = token.index + token[0].length;
  }
  fragments.push(text.slice(cursor));
  return JSON.parse(fragments.join(''), (_, value) => value === marker ? unsafeNumber : value);
}

function openApi(rootText, selector) {
  const match = SELECTOR.exec(selector);
  if (!match) throw Error('OpenAPI requires an exact uppercase METHOD and path');
  let doc;
  try { doc = parseOpenApi(rootText); } catch (error) {
    if (!(error instanceof SyntaxError)) throw error;
    throw Error('OpenAPI lock requires a JSON document with local references');
  }
  if (!object(doc) || !/^3\.[01]\./.test(doc.openapi || '') || !object(doc.paths)) {
    throw Error('OpenAPI lock supports JSON OpenAPI 3.0 and 3.1 documents');
  }
  const path = doc.paths[match[2]];
  const operation = path?.[match[1].toLowerCase()];
  if (!object(path) || path.$ref || !object(operation) || !object(operation.responses)) {
    throw Error('OpenAPI operation is unavailable: ' + selector);
  }
  function pointer(reference) {
    if (typeof reference !== 'string' || !reference.startsWith('#/')) {
      throw Error('OpenAPI lock requires local JSON Pointer references');
    }
    let value = doc;
    for (const component of decodeURIComponent(reference.slice(2)).split('/')) {
      const key = component.replace(/~1/g, '/').replace(/~0/g, '~');
      if (!value || !Object.hasOwn(value, key)) throw Error('OpenAPI reference is unavailable: ' + reference);
      value = value[key];
    }
    return value;
  }
  const references = Object.create(null);
  function collect(value, mode = 'object') {
    if (value === unsafeNumber) throw Error('OpenAPI numbers outside lossless JavaScript precision require a project-declared check');
    if (Array.isArray(value)) return value.map(member => collect(member, mode === 'literal' ? 'literal' : 'object'));
    if (!object(value)) return value;
    const reduced = {};
    const inspect = mode === 'object';
    for (const [key, member] of Object.entries(value)) {
      if (inspect && (key === '$dynamicRef' || key === '$id')) {
        throw Error('Dynamic or rebased OpenAPI references require separate verification');
      }
      if (inspect && key === '$ref') {
        const target = pointer(member);
        if (!Object.hasOwn(references, member)) {
          references[member] = null;
          references[member] = collect(target);
        }
      }
      const literal = mode === 'literal' || (inspect && (literalValues.has(key) || key.startsWith('x-') ||
        (key === 'examples' && Array.isArray(member))));
      const childMode = literal ? 'literal' : inspect && namedObjects.has(key) ? 'map' : 'object';
      Object.defineProperty(reduced, key, {value: collect(member, childMode), enumerable: true});
    }
    return reduced;
  }

  const parameters = new Map();
  for (const entry of [...(path.parameters || []), ...(operation.parameters || [])]) {
    let location = entry;
    const seen = new Set();
    while (location?.$ref) {
      if (seen.has(location.$ref)) throw Error('Cyclic OpenAPI parameter reference');
      seen.add(location.$ref);
      location = pointer(location.$ref);
    }
    if (!location?.name || !location.in) throw Error('OpenAPI parameter has no exact identity');
    parameters.set(location.in + ':' + location.name, entry);
  }
  const security = operation.security ?? doc.security;
  const securitySchemes = Object.fromEntries([...new Set((security || []).flatMap(rule => Object.keys(rule)))].map(name => {
    if (!Object.hasOwn(doc.components?.securitySchemes || {}, name)) throw Error('OpenAPI security scheme is unavailable: ' + name);
    return [name, collect(doc.components.securitySchemes[name])];
  }));
  const selected = collect({
    ...operation, parameters: Object.fromEntries(parameters), servers: operation.servers ?? path.servers ?? doc.servers,
    security
  });
  return {version: doc.openapi, dialect: doc.jsonSchemaDialect, selected, securitySchemes, references};
}

function definition(value, label) {
  if (!object(value) || !Array.isArray(value.checks || []) || !Array.isArray(value.inputs || []) || !Array.isArray(value.consumers || [])) {
    throw Error('Invalid declared API contract: ' + label);
  }
  const kind = value.openapi ? 'openapi' : 'file';
  const path = relative(value.openapi || value.file);
  const checks = [...new Set(value.checks || [])];
  const inputs = [...new Set(value.inputs || [])].map(relative);
  const consumers = [...new Set(value.consumers || [])];
  if (consumers.some(name => typeof name !== 'string' || !name.trim())) throw Error('API consumers need exact names');
  if (checks.some(name => typeof name !== 'string' || !name.trim()) || (kind === 'file' && !checks.length)) {
    throw Error('Project-declared contract requires exact check names: ' + label);
  }
  if (kind === 'openapi' && !SELECTOR.test(value.operation || '')) {
    throw Error('OpenAPI contract requires an exact method and path: ' + label);
  }
  return {kind, path, ...(kind === 'openapi' ? {operation: value.operation} : {}), checks, inputs, consumers};
}

function selection(root, target, options) {
  if (!NAME.test(target) && !SELECTOR.test(target)) throw Error('Select an exact API contract or named set');
  if (options.file) {
    if (!SELECTOR.test(target)) throw Error('--file needs an exact OpenAPI operation');
    return [definition({openapi: options.file, operation: target}, target)];
  }
  const raw = read(root, DECLARATIONS);
  const definitions = raw === null ? {} : JSON.parse(raw);
  const {contracts = {}, sets = {}} = definitions;
  if (!object(contracts) || !object(sets) || (raw !== null && definitions.schema !== 1)) throw Error('Unsupported API declaration');
  if (Object.hasOwn(contracts, target) && Object.hasOwn(sets, target)) throw Error('Ambiguous API contract selector: ' + target);
  if (Object.hasOwn(contracts, target)) return [definition(contracts[target], target)];
  if (Object.hasOwn(sets, target)) {
    const members = sets[target];
    if (!Array.isArray(members) || !members.length || new Set(members).size !== members.length ||
        members.some(name => typeof name !== 'string' || !Object.hasOwn(contracts, name))) {
      throw Error('API set needs an explicit list of distinct declared contracts');
    }
    return members.map(name => definition(contracts[name], name));
  }
  const exact = Object.entries(contracts).filter(([, item]) => item.operation === target);
  if (exact.length === 1) return [definition(exact[0][1], target)];
  if (exact.length > 1) throw Error('Ambiguous OpenAPI operation declaration: ' + target);
  throw Error('Unknown API contract. Select a declaration or supply --file with METHOD /path.');
}

function content(text, item) {
  if (text === null) throw Error('Protected API source is missing: ' + item.path);
  return item.kind === 'openapi' ? Buffer.from(json(openApi(text.toString('utf8'), item.operation))) : text;
}

function fromCommit(root, commit, item) {
  return content(git(root, ['show', commit + ':' + item.path], 'buffer'), item);
}

function requireCleanContract(root, baselineBytes, item) {
  let working;
  try { working = content(fs.readFileSync(safe(root, item.path)), item); } catch (error) {
    throw Error('Uncommitted or unavailable selected contract: ' + item.path + '. ' + error.message +
      '. Select --baseline explicitly.');
  }
  if (working.equals(baselineBytes)) return;
  const before = baselineBytes.toString('utf8').split('\n'), after = working.toString('utf8').split('\n');
  const lines = Math.max(before.length, after.length);
  let index = 0;
  while (index < lines && before[index] === after[index]) index++;
  const difference = index < lines ?
    '. Baseline: ' + (before[index] ?? '(end)').slice(0, 240) +
    '. Working copy: ' + (after[index] ?? '(end)').slice(0, 240) : '. Contract bytes differ';
  throw Error('Uncommitted changes to the selected contract in ' + item.path + difference +
    '. Select --baseline explicitly.');
}

function lock(root, config, target, options) {
  if (Object.hasOwn(config.locks, target)) {
    const previous = config.locks[target];
    if ((options.file && previous.some(item => item.path !== options.file)) ||
        (options.baseline && previous.some(item => item.baseline !== revision(root, options.baseline)))) {
      throw Error('Changing a pinned API lock requires unlock-api first');
    }
    return config;
  }
  const baseline = revision(root, options.baseline || 'HEAD');
  const members = selection(root, target, options).map(item => {
    const baselineBytes = fromCommit(root, baseline, item);
    if (!options.baseline) {
      requireCleanContract(root, baselineBytes, item);
      for (const path of item.inputs) {
        const input = {kind: 'file', path};
        requireCleanContract(root, fromCommit(root, baseline, input), input);
      }
    }
    return {...item, baseline, digest: hash(baselineBytes)};
  });
  return {...config, locks: {...config.locks, [target]: members}};
}

function unlock(config, target) {
  if (target === '--all') return {...config, locks: {}};
  if (!Object.hasOwn(config.locks, target)) throw Error('No exact API lock exists: ' + target);
  const locks = {...config.locks};
  delete locks[target];
  return {...config, locks};
}

function candidateLocks(root, snapshot, working) {
  const {head, base_oid: base} = snapshot;
  const exact = [head, base].every(oid => OID.test(oid || '') &&
    gitResult(root, ['cat-file', '-t', oid]).stdout?.trim() === 'commit');
  if (!exact) {
    const configuredRemote = gitResult(root, ['remote']).stdout?.trim();
    if (snapshot.candidate_objects_required || configuredRemote || Object.keys(working.locks).length) {
      throw Error('API lock review needs the current Git head and base objects');
    }
    return {locks: working.locks, touched: new Set(snapshot.changed_files || [])};
  }
  const common = git(root, ['merge-base', base, head]).trim();
  const touched = new Set(git(root, ['diff', '--no-renames', '--name-only', '-z', common, head, '--'])
    .split('\0').filter(Boolean));
  const readConfig = commit => git(root, ['ls-tree', '-z', commit, '--', CONFIG]) ?
    git(root, ['show', commit + ':' + CONFIG]) : null;
  const target = configuration(readConfig(base));
  const candidate = configuration(readConfig(head));
  const original = configuration(readConfig(common));
  if (touched.has(CONFIG) && json(working) !== json(candidate)) {
    throw Error('Review requires the owned development configuration from the current candidate');
  }
  const locks = new Map(Object.entries(target.locks));
  for (const [id, members] of locks) {
    if (touched.has(CONFIG) && Object.hasOwn(original.locks, id) &&
        json(original.locks[id]) === json(members) &&
        (!Object.hasOwn(candidate.locks, id) || json(candidate.locks[id]) !== json(members))) {
      locks.delete(id);
    }
  }
  for (const config of [candidate, working]) {
    for (const [id, members] of Object.entries(config.locks)) {
      if (locks.has(id) && json(locks.get(id)) !== json(members)) {
        throw Error('Conflicting pinned API lock definitions for ' + id);
      }
      locks.set(id, members);
    }
  }
  return {locks: Object.fromEntries(locks), touched};
}

function review(root, snapshot) {
  const raw = read(root, CONFIG);
  const config = configuration(raw);
  const active = effective(raw);
  const profileRaw = read(root, '.skill-tree/installation/profile.json');
  const profile = profileRaw === null ? null : JSON.parse(profileRaw);
  if ((active.lock_review || profile?.development_policies?.lock_review) &&
      (!profile?.development_policies || json(active) !== json(profile.development_policies))) {
    throw Error('API lock configuration differs from the owned installed profile');
  }
  const {locks, touched} = candidateLocks(root, snapshot, config);
  const reviewer = effective(json({...config, locks})).lock_review;
  if (!reviewer) return {reviewer: null, affected: [], failures: []};
  if (!Array.isArray(snapshot.changed_files)) throw Error('API lock review needs the current changed files');
  const affected = [], failures = [];
  for (const [id, members] of Object.entries(locks)) {
    if (!Array.isArray(members) || !members.length) throw Error('Invalid managed API lock: ' + id);
    for (const item of members) {
      const label = id + ' (' + (item.operation || item.path) + ')';
      try {
        if (!OID.test(item.baseline || '') || !['openapi', 'file'].includes(item.kind) ||
            !Array.isArray(item.inputs) || !Array.isArray(item.checks)) throw Error('Incomplete API lock definition');
        relative(item.path);
        const sourceTouched = touched.has(item.path);
        const inputsTouched = item.inputs.map(relative).some(file => touched.has(file));
        if (!sourceTouched && !inputsTouched && !touched.has(CONFIG)) continue;
        const baseline = fromCommit(root, item.baseline, item);
        if (hash(baseline) !== item.digest) throw Error('API lock baseline digest changed');
        const head = fromCommit(root, snapshot.head, item);
        // Another operation may share the same OpenAPI document.
        if (item.kind === 'openapi' && sourceTouched && !inputsTouched && !touched.has(CONFIG) &&
            head.equals(fromCommit(root, snapshot.base_oid, item))) continue;
        affected.push(label);
        if (item.kind === 'openapi' && !baseline.equals(head)) throw Error('Protected OpenAPI operation changed against the pinned contract');
        for (const name of item.checks) {
          const checks = (snapshot.checks || []).filter(check => check.name === name);
          if (checks.length !== 1 || checks[0].status !== 'success') {
            throw Error('Missing current successful API contract check: ' + name);
          }
        }
      } catch (error) {
        failures.push(label + ': ' + error.message);
      }
    }
  }
  return {reviewer, affected, failures};
}

function runCommand(root, source, command, args) {
  const target = args[0];
  if (!target || (command === 'unlock-api' && args.length !== 1)) {
    throw Error('Use lock-api <name|METHOD /path> [--file <path>] [--baseline <ref>] or unlock-api <name|--all>');
  }
  const options = {};
  for (let index = 1; index < args.length; index += 2) {
    const name = args[index].slice(2);
    if (!['--file', '--baseline'].includes(args[index]) || !args[index + 1] || Object.hasOwn(options, name)) {
      throw Error('Select an exact API lock option and value');
    }
    options[name] = args[index + 1];
  }
  let previous, next;
  const core = require('./installation.js');
  core.updateDevelopmentPolicy(root, source, config => {
    previous = config;
    next = command === 'lock-api' ? lock(root, config, target, options) : unlock(config, target);
    return next;
  });
  const hadLocks = Object.keys(previous.locks).length > 0;
  const hasLocks = Object.keys(next.locks).length > 0;
  const action = previous === next ? 'unchanged' : !hadLocks && hasLocks ? 'attached' : hadLocks && !hasLocks ? 'removed' : 'updated';
  const removed = Object.entries(previous.locks).filter(([name]) => !Object.hasOwn(next.locks, name));
  const released = removed.flatMap(([, items]) => items);
  const consumers = [...new Set(released.flatMap(item => item.consumers || []))].sort();
  return {
    action: command, target,
    ...(command === 'unlock-api' ? {
      removed_locks: removed.map(([name]) => name),
      known_consumers: consumers,
      consumer_coverage: released.some(item => !item.consumers?.length) ? 'unknown-or-partial' : 'declared'
    } : {}),
    reviewer: {id: 'api-lock-review', stage: 'before-pr-ready', action, configuration: CONFIG},
    active_locks: Object.keys(next.locks).sort()
  };
}

module.exports = {runCommand, review};
if (require.main === module) {
  try {
    if (process.argv[2] !== 'review' || process.argv.length !== 4) throw Error('Use review <project-root> with a snapshot on standard input');
    const result = review(process.argv[3], JSON.parse(fs.readFileSync(0, 'utf8')));
    process.stdout.write(json(result));
    if (result.failures.length) process.exitCode = 2;
  } catch (error) {
    process.stderr.write(error.message + '\n');
    process.exitCode = 2;
  }
}
