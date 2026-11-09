'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const operation = 'skill-tree-plugins';
const maintenance = '.skill-tree/installation';
const bundledSource = maintenance + '/source';
const optionalCatalog = new Set(['config/plugin-catalog.json', 'config/plugin-catalog-eligibility.json']);
const own = (value, key) => Object.hasOwn(value, key);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const hash = value => crypto.createHash('sha256').update(value).digest('hex');
const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (!object(value)) return value;
  return Object.fromEntries(Object.keys(value).sort().map(key => [key, stable(value[key])]));
}

function seal(value) {
  return hash(JSON.stringify(stable(value), null, 2) + '\n');
}

function relative(value) {
  if (typeof value !== 'string' || path.posix.isAbsolute(value) || path.win32.isAbsolute(value) ||
      value.includes('\\') || value.includes('\0') || value.split('/').some(part => !part || part === '.' || part === '..')) {
    throw Error('Invalid owned manager resource path');
  }
  return value;
}

function ownedPath(root, location) {
  let current = root;
  for (const part of relative(location).split('/')) {
    current = path.join(current, part);
    if (fs.lstatSync(current).isSymbolicLink()) throw Error('Symlink in owned manager resources: ' + location);
  }
  return current;
}

function ownedBytes(root, location, expected) {
  const bytes = fs.readFileSync(ownedPath(root, location));
  if (!digest(expected) || hash(bytes) !== expected) throw Error('Owned manager resource digest changed: ' + location);
  return bytes;
}

function verifyCommonJs(root, location, expected) {
  const config = JSON.parse(ownedBytes(root, location, expected).toString('utf8'));
  if (!object(config) || config.type !== 'commonjs' || Object.keys(config).length !== 1) {
    throw Error('Owned manager requires its CommonJS package boundary: ' + location);
  }
}

function verifyProfile(root, packageRoot) {
  const profile = JSON.parse(fs.readFileSync(ownedPath(root, maintenance + '/profile.json'), 'utf8'));
  if (profile?.format !== 'skill-tree-profile' || profile.schema !== 1 || profile.project_root !== root ||
      !['general', 'web', 'unity'].includes(profile.flavor) || !object(profile.source_digests) ||
      !object(profile.bundle_digests) || !object(profile.destinations)) {
    throw Error('An owned project profile is required before loading the plugin manager');
  }
  const outputs = Object.fromEntries(Object.values(profile.destinations).map(record => [record.name, record.files]));
  if (seal({
    flavor: profile.flavor, environment_id: profile.environment_id,
    source_digests: profile.source_digests, output_digests: outputs,
  }) !== profile.identity) throw Error('Owned manager profile identity mismatch');
  const packageRelative = relative(path.relative(root, packageRoot).split(path.sep).join('/'));
  const record = own(profile.destinations, packageRelative) ? profile.destinations[packageRelative] : null;
  if (path.basename(packageRelative) !== operation || record?.name !== operation ||
      record.flavor !== profile.flavor || !object(record.files) || seal(record.files) !== record.identity ||
      ownedPath(root, packageRelative) !== packageRoot) throw Error('The plugin manager is outside an owned operation destination');

  const entry = 'scripts/plugin-manager.js';
  ownedBytes(root, packageRelative + '/' + entry, record.files[entry]);
  verifyCommonJs(root, packageRelative + '/scripts/package.json', record.files['scripts/package.json']);
  const boundary = maintenance + '/package.json';
  verifyCommonJs(root, boundary, profile.bundle_digests[boundary]);
  return profile;
}

function verifyBundle(root, profile, inventory) {
  const source = ownedPath(root, bundledSource);
  const expected = new Map();
  for (const [location, sum] of Object.entries(profile.source_digests)) {
    relative(location);
    if (location.startsWith('domains/') && !location.startsWith('domains/' + profile.flavor + '/')) continue;
    if (location === 'config/repository.json') continue;
    if (!digest(sum) || profile.bundle_digests[bundledSource + '/' + location] !== sum) {
      throw Error('Owned maintenance bundle and source identities disagree: ' + location);
    }
    expected.set(location, sum);
  }
  if (!expected.has('lib/plugin-management.js') || !expected.has('lib/installation.js') ||
      Object.keys(profile.bundle_digests).filter(file => file.startsWith(bundledSource + '/')).length !== expected.size) {
    throw Error('The owned plugin manager maintenance bundle is incomplete');
  }
  const catalogChanged = new Set();
  function visit(directory, prefix = '') {
    for (const item of fs.readdirSync(directory, {withFileTypes: true})) {
      const location = prefix + item.name, file = path.join(directory, item.name);
      if (item.isDirectory()) {
        if (item.name !== '__pycache__') visit(file, location + '/');
        continue;
      }
      const sum = expected.get(location);
      const valid = item.isFile() && sum !== undefined && hash(fs.readFileSync(file)) === sum;
      if (!valid) {
        if (!inventory || !optionalCatalog.has(location)) throw Error('Owned maintenance bundle changed: ' + location);
        catalogChanged.add(location);
      }
      expected.delete(location);
    }
  }
  visit(source);
  for (const location of expected.keys()) {
    if (!inventory || !optionalCatalog.has(location)) throw Error('Owned maintenance bundle resource missing: ' + location);
    catalogChanged.add(location);
  }
  return {
    source,
    ...(catalogChanged.size ? {catalogDiagnostic: 'Optional curated catalog bytes differ from the owned source receipt'} : {}),
  };
}

function envelope(input) {
  const fields = {
    inventory: ['action', 'format', 'group_by', 'host', 'flavor', 'point'],
    prepare: ['action', 'request'],
    apply: ['action', 'proposal', 'confirmation'],
  };
  if (!object(input) || !own(fields, input.action) || Object.keys(input).some(key => !fields[input.action].includes(key))) {
    throw Error('Select an inventory, prepare or apply management envelope');
  }
  if (input.action === 'inventory' &&
      (!['json', 'text'].includes(input.format ?? 'json') || !['plugin', 'point'].includes(input.group_by ?? 'plugin'))) {
    throw Error('Inventory format requires json or text and grouping requires plugin or point');
  }
  return input;
}

async function main(args) {
  if (args.length !== 4 || args[0] !== '--project-root' || args[2] !== '--input') {
    throw Error('Usage: node scripts/plugin-manager.js --project-root <project-root> --input <request.json|->');
  }
  const input = envelope(JSON.parse(fs.readFileSync(args[3] === '-' ? 0 : args[3], 'utf8')));
  const root = fs.realpathSync(args[1]), packageRoot = path.resolve(__dirname, '..');
  const profile = verifyProfile(root, packageRoot);
  const options = verifyBundle(root, profile, input.action === 'inventory');
  const manager = require(path.join(options.source, 'lib/plugin-management.js'));
  if (input.action === 'inventory') {
    const view = manager.managementInventory(root, {...options, host: input.host, flavor: input.flavor, point: input.point});
    return input.format === 'text' ? manager.formatInventory(view, {groupBy: input.group_by}) : JSON.stringify(view, null, 2) + '\n';
  }
  require(path.join(options.source, 'lib/installation.js')).verifyOwned(root, profile);
  const value = await (input.action === 'prepare'
    ? manager.prepareManagerRequest(root, input.request, options)
    : manager.applyManagerProposal(root, input.proposal, input.confirmation, options));
  return JSON.stringify(value, null, 2) + '\n';
}

if (require.main === module) {
  main(process.argv.slice(2)).then(output => process.stdout.write(output)).catch(error => {
    process.stderr.write((error.path ? 'An owned manager operation could not access a required file' : error.message) + '\n');
    process.exitCode = 1;
  });
}
