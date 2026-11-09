'use strict';

const fs = require('node:fs');
const path = require('node:path');
const registry = require('./plugin-registry.js');
const {createCatalog} = require('./plugin-composition.js');
const {resolveLocation} = require('./plugin-bindings.js');
const {normalizeSource} = require('./plugin-sources.js');

const flavors = ['general', 'unity', 'web'];
const hosts = ['codex', 'other'];
const support = ['observed', 'unqualified', 'unsupported', 'not-applicable'];
const qualification = ['qualified', 'unqualified', 'compatibility-only', 'unsupported'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = value => typeof value === 'string' && value.length > 0;
const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const revision = value => typeof value === 'string' && /^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(value);
const clone = structuredClone;

function fail(message) {
  registry.fail('plugin-catalog', message);
}

function read(source, relative) {
  return JSON.parse(fs.readFileSync(registry.safe(source, relative), 'utf8'));
}

function portableUrl(value) {
  let url;
  try { url = new URL(value); } catch { fail('Catalog provenance requires a portable URL'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) {
    fail('Catalog provenance requires a portable HTTPS URL without credentials');
  }
}

function sourceIdentity(source) {
  return registry.json([source?.kind, source?.url, source?.entry, source?.ref, source?.locator_id]);
}

function sameSource(left, right) {
  return left?.kind === right?.kind && left?.url === right?.url && left?.entry === right?.entry &&
    left?.locator_id === right?.locator_id;
}

function repositorySource(value) {
  if (!object(value) || value.kind !== 'repository' || !revision(value.ref)) {
    fail('A curated source requires an exact immutable repository revision');
  }
  portableUrl(value.url);
  registry.relative(value.entry);
}

function packageIds(values) {
  if (!Array.isArray(values) || values.some(id => !registry.validId(id)) || new Set(values).size !== values.length) {
    fail('Catalog package dependencies require exact distinct identities');
  }
  return values;
}

function supportMap(value, keys) {
  return object(value) && Object.keys(value).length === keys.length &&
    keys.every(key => Object.hasOwn(value, key) && support.includes(value[key]));
}

function descriptorFor(root, entry) {
  if (entry.descriptor === null) {
    if (entry.adapter.status !== 'requires-preparation') fail('A discovery-only entry requires explicit adapter preparation');
    return null;
  }
  if (typeof entry.descriptor !== 'string' || !/^config\/plugins\/[a-z][a-z0-9-]*\.json$/.test(entry.descriptor)) {
    fail('A catalog descriptor requires an owned plugin configuration path');
  }
  const descriptor = read(root, entry.descriptor);
  if (!object(descriptor) || ['locator', 'url', 'path'].some(key => Object.hasOwn(descriptor, key)) ||
      descriptor.id !== entry.id ||
      sourceIdentity(descriptor.source) !== sourceIdentity(entry.source)) {
    fail('Catalog and descriptor source identities conflict: ' + entry.id);
  }
  if (!digest(entry.content_digest) || descriptor.metadata?.source_verification?.expected_content_digest !== entry.content_digest) {
    fail('Catalog and descriptor content digests conflict: ' + entry.id);
  }
  const paths = [descriptor.resources, descriptor.dependencies];
  if (paths.some(list => !Array.isArray(list))) fail('A catalog descriptor requires exact source resources and dependencies');
  const expected = descriptor.expectedDigests;
  if (!object(expected) || ![entry.source.entry, ...paths.flat()].every(file => Object.hasOwn(expected, file))) {
    fail('A catalog descriptor requires source pins for every declared resource');
  }
  for (const [file, hash] of Object.entries(expected)) {
    registry.relative(file);
    if (!digest(hash)) fail('A catalog descriptor has an invalid resource digest');
  }
  const pinned = Object.fromEntries(Object.keys(expected).sort().map(file => [file, expected[file]]));
  if (registry.hash(JSON.stringify({entry: entry.source.entry, digests: pinned})) !== entry.content_digest) {
    fail('Catalog resource pins do not reproduce the pinned content identity: ' + entry.id);
  }
  if (!Array.isArray(descriptor.capabilities) || !descriptor.capabilities.every(text) ||
      !entry.adapter.context_kinds.every(kind => descriptor.adapter?.context_kinds?.includes(kind))) {
    fail('Catalog and descriptor adapter contexts conflict: ' + entry.id);
  }
  return {...descriptor, package_dependencies: packageIds(descriptor.package_dependencies ?? [])};
}

function locationsFor(values, anchors, strict) {
  if (!Array.isArray(values) || strict && !values.length) fail('A catalog entry requires locations');
  const resolved = [], unresolved = [];
  const seen = new Set();
  for (const input of values) {
    const location = resolveLocation(input, anchors);
    if (location.status !== 'resolved') {
      if (strict) fail('Catalog location has no owned callable anchor: ' + JSON.stringify(input));
      unresolved.push(location);
    } else if (seen.has(location.boundary_id)) {
      if (strict) fail('Duplicate catalog locations resolve to the same boundary: ' + location.boundary_id);
    } else {
      seen.add(location.boundary_id);
      resolved.push(location);
    }
  }
  return {resolved, unresolved};
}

function compatibleLocation(row, descriptor, location) {
  const policy = descriptor?.metadata?.application_policy ?? descriptor?.metadata?.pilot_policy;
  const phases = policy?.configurable_anchors ?? (policy?.suggested_anchor ? [policy.suggested_anchor] : []);
  const phase = location.boundary_id.slice(location.operation.length + 1);
  return row.adapter.context_kinds.every(kind => location.context_kinds.includes(kind)) &&
    (!policy?.operation || policy.operation === location.operation) && (!phases.length || phases.includes(phase));
}

function descriptorFingerprints(descriptor) {
  const {adapter, expectedDigests, resources, dependencies, package_dependencies, capabilities} = descriptor;
  return {
    adapter_digest: registry.hash(registry.json({adapter, capabilities})),
    dependency_digest: registry.hash(registry.json({expectedDigests, resources, dependencies, package_dependencies})),
  };
}

function independentlyEligible(entry, {host, flavor, boundary_id}, eligibility) {
  const {row, descriptor, locations} = entry;
  if (!descriptor || row.evidence.kind !== 'comparison' ||
      !hosts.includes(host) || !flavors.includes(flavor) ||
      row.hosts[host] !== 'observed' || row.flavors[flavor] !== 'observed' ||
      !locations.some(location => location.boundary_id === boundary_id)) return false;
  const fingerprint = descriptorFingerprints(descriptor);
  return eligibility.eligible.some(record =>
    record?.id === row.id && record.application === row.application && record.flavor === flavor &&
    record.host === host && record.boundary_id === boundary_id &&
    sourceIdentity(record.source) === sourceIdentity(row.source) && record.content_digest === row.content_digest &&
    record.adapter_digest === fingerprint.adapter_digest && record.dependency_digest === fingerprint.dependency_digest
  );
}

function verifyPackageClosure(dependencies, scope) {
  const visiting = new Set(), complete = new Set();
  function visit(id) {
    if (complete.has(id)) return;
    if (visiting.has(id) || !dependencies.has(id)) fail('Catalog ' + scope + ' dependency is unresolved: ' + id);
    visiting.add(id);
    for (const dependency of dependencies.get(id)) visit(dependency);
    visiting.delete(id);
    complete.add(id);
  }
  for (const id of dependencies.keys()) visit(id);
}

function validateRecommendations(data, eligibility, entries) {
  if (!object(data) || Object.keys(data).length !== flavors.length ||
      !flavors.every(flavor => Array.isArray(data[flavor]))) fail('Catalog recommendations require every flavor');
  for (const flavor of flavors) {
    const bundle = data[flavor], selected = new Map();
    for (const item of bundle) {
      const entry = entries.get(item?.id);
      if (!entry || selected.has(item.id)) fail('Unknown or duplicate catalog recommendation');
      if (entry.row.status !== 'qualified' || !independentlyEligible(entry, {...item, flavor}, eligibility)) {
        fail('Catalog recommendation lacks independently qualified comparison evidence: ' + item.id);
      }
      selected.set(item.id, entry.descriptor.package_dependencies);
    }

    verifyPackageClosure(selected, 'recommendation');
  }
}

function emptyCatalog(source = path.resolve(__dirname, '..')) {
  const operations = read(source, 'templates/operations.json');
  return {anchors: createCatalog(operations), entries: new Map(),
    recommendations: Object.fromEntries(flavors.map(flavor => [flavor, []]))};
}

function loadCatalog(source = path.resolve(__dirname, '..'), {manifest} = {}) {
  const data = manifest ?? read(source, 'config/plugin-catalog.json');
  const eligibility = read(source, 'config/plugin-catalog-eligibility.json');
  if (eligibility?.schema !== 1 || !object(eligibility.source) ||
      !digest(eligibility.source.sha256) || !Array.isArray(eligibility.eligible)) {
    fail('The owned comparison eligibility input is invalid');
  }
  registry.relative(eligibility.source.path);
  const operations = read(source, 'templates/operations.json');
  const anchors = createCatalog(operations), entries = new Map();
  if (data?.schema !== 1 || !Array.isArray(data.entries)) fail('Unsupported curated catalog schema');
  for (const row of data.entries) {
    if (!object(row) || !registry.validId(row.id) || entries.has(row.id)) fail('Invalid or duplicate catalog identity');
    if (!text(row.title) || !registry.validId(row.application) || !qualification.includes(row.status) ||
        !(row.content_digest === null || digest(row.content_digest)) ||
        !supportMap(row.hosts, hosts) || !supportMap(row.flavors, flavors)) fail('Invalid curated catalog metadata: ' + row.id);
    if (!object(row.adapter) || !['available', 'requires-preparation'].includes(row.adapter.status) ||
        !Array.isArray(row.adapter.context_kinds) || !row.adapter.context_kinds.length ||
        !row.adapter.context_kinds.every(text) ||
        !Array.isArray(row.adapter.prerequisites) || !row.adapter.prerequisites.every(text)) {
      fail('Catalog adapter metadata requires explicit contexts and prerequisites: ' + row.id);
    }
    if (!object(row.license) || !text(row.license.identifier)) fail('Catalog license provenance is missing: ' + row.id);
    portableUrl(row.license.source);
    if (!object(row.evidence) || Object.hasOwn(row.evidence, 'eligible') ||
        !['comparison', 'source-inspection'].includes(row.evidence.kind)) {
      fail('Catalog evidence requires an explicit source: ' + row.id);
    }
    registry.relative(row.evidence.reference);
    if (row.evidence.kind === 'comparison' &&
        (row.evidence.reference !== eligibility.source?.path || row.evidence.sha256 !== eligibility.source?.sha256)) {
      fail('Catalog comparison provenance differs from the owned evidence identity: ' + row.id);
    }
    repositorySource(row.source);
    const locations = locationsFor(row.locations, anchors, true).resolved;
    const descriptor = descriptorFor(source, row);
    if (locations.some(location => !compatibleLocation(row, descriptor, location))) {
      fail('Catalog adapter contexts are incompatible with the location: ' + row.id);
    }
    const entry = {row: clone(row), descriptor, locations};
    if (row.status === 'qualified' && !eligibility.eligible.some(scope =>
      scope?.id === row.id && independentlyEligible(entry, scope, eligibility)
    )) fail('Catalog status lacks independently qualified comparison evidence: ' + row.id);
    entries.set(row.id, entry);
  }
  const available = [...entries.values()].filter(entry => entry.descriptor);
  verifyPackageClosure(new Map(available.map(({row, descriptor}) => [row.id, descriptor.package_dependencies])), 'package');
  validateRecommendations(data.recommendations, eligibility, entries);
  return {anchors, entries, recommendations: clone(data.recommendations)};
}

function publicSource(value) {
  if (value.kind === 'local') {
    const entry = registry.relative(value.entry);
    return {kind: 'local', entry, ...(digest(value.locator_id) ? {locator_id: value.locator_id} : {})};
  }
  if (!['raw', 'repository'].includes(value.kind)) fail('Invalid project-known source kind');
  const {definition} = normalizeSource({id: 'catalog-projection', source: value});
  const {kind, url, entry, ref} = definition.source;
  const safeRef = typeof ref === 'string' && /^[a-z0-9_][a-z0-9_./-]{0,199}$/i.test(ref) && !ref.includes('..') &&
    !ref.includes('//') && !ref.endsWith('/');
  return {kind, url, entry, ...(safeRef ? {ref} : {})};
}

function knownDefinitions(known, catalog) {
  if (!object(known)) fail('Project-known sources require an identity-keyed map');
  const additions = new Map(), matches = new Map(), conflicts = new Set();
  for (const [id, entry] of Object.entries(known)) {
    if (!registry.validId(id) || !object(entry)) fail('Invalid project-known identity');
    const descriptor = entry.descriptor ?? entry.definition ?? entry;
    if (!object(descriptor) || descriptor.id !== undefined && descriptor.id !== id || !object(descriptor.source)) {
      fail('Invalid project-known source identity');
    }
    const source = publicSource(descriptor.source);
    const current = catalog.entries.get(id);
    if (!current) additions.set(id, {descriptor: {...descriptor, id}, locator: entry.locator, entry, source});
    else if (sourceIdentity(source) === sourceIdentity(current.row.source)) matches.set(id, entry);
    else conflicts.add(id);
  }
  return {additions, matches, conflicts};
}

function installedStatus(inventory, row) {
  if (!inventory || inventory.status === 'unavailable') return 'unknown';
  const actual = inventory.plugins.find(item => item.id === row.id);
  if (!actual) return 'absent';
  if (!sameSource(actual.source, row.source)) return 'conflict';
  if ((row.revision && actual.revision !== row.revision) ||
      (row.content_digest && actual.content_digest !== row.content_digest)) return 'changed';
  if (actual.ownership?.status !== 'verified') return 'unverified';
  return row.revision && row.content_digest ? 'matching' : 'source-match';
}

function catalogView(catalog, {host, flavor, point, known = {}, inventory} = {}) {
  if (host !== undefined && !hosts.includes(host)) fail('Unknown catalog host filter');
  if (flavor !== undefined && !flavors.includes(flavor)) fail('Unknown catalog flavor filter');
  const boundary = point === undefined ? undefined : locationsFor([point], catalog.anchors, true).resolved[0].boundary_id;
  const {additions, matches, conflicts} = knownDefinitions(known, catalog);
  const entries = [], points = new Map();
  function group(location) {
    const id = location.boundary_id;
    if (!points.has(id)) {
      points.set(id, {boundary_id: id, operation: location.operation, anchor: id.slice(location.operation.length + 1), suggested: [], bindings: []});
    }
    return points.get(id);
  }
  for (const row of inventory?.bindings ?? []) {
    const location = row.location ?? resolveLocation(row, catalog.anchors);
    if (location.status === 'resolved' && (!boundary || boundary === location.boundary_id)) group(location).bindings.push(clone(row));
  }
  const bound = new Set([...points.values()].flatMap(group => group.bindings.map(binding => binding.plugin_id)));
  function add(row, locations) {
    const applies = row.hosts?.[host] !== 'not-applicable' && row.flavors?.[flavor] !== 'not-applicable';
    const selected = applies ? locations.filter(location => !boundary || location.boundary_id === boundary) : [];
    if ((!applies || boundary) && !selected.length && !bound.has(row.id)) return;
    for (const location of selected) group(location).suggested.push(row.id);
    entries.push({...row, installed: installedStatus(inventory, row)});
  }
  for (const {row, descriptor, locations} of catalog.entries.values()) {
    const supplied = locationsFor(matches.get(row.id)?.suggested_locations ?? [], catalog.anchors, false);
    const existing = new Set(locations.map(location => location.boundary_id));
    const extra = [];
    const unresolved = supplied.unresolved.map(({status, reason}) => ({status, reason}));
    for (const location of supplied.resolved) {
      if (existing.has(location.boundary_id)) continue;
      if (compatibleLocation(row, descriptor, location)) extra.push(location);
      else unresolved.push({status: 'unresolved', reason: 'The pinned adapter does not support the suggested boundary'});
    }
    add({...clone(row), origin: 'curated', revision: row.source.ref, known_conflict: conflicts.has(row.id),
      locations: [...clone(row.locations), ...extra.map(({operation, anchor}) => ({operation, anchor}))],
      unresolved_locations: unresolved,
      dependencies: {
        packages: clone(descriptor?.package_dependencies ?? []),
        resources: clone(descriptor?.resources ?? []),
        source: clone(descriptor?.dependencies ?? row.source_dependencies ?? []),
        prerequisites: clone(row.adapter.prerequisites),
      },
    }, [...locations, ...extra]);
  }
  for (const [id, {source, entry}] of additions) {
    const locations = locationsFor(entry.suggested_locations ?? [], catalog.anchors, false);
    const title = typeof entry.title === 'string' && !/[\/\\\x00-\x1f]/.test(entry.title) ? entry.title : id;
    add({id, title, origin: 'project-known', revision: revision(source.ref) ? source.ref : null, source, status: 'unqualified',
      locations: locations.resolved.map(({operation, anchor}) => ({operation, anchor})),
      unresolved_locations: locations.unresolved.map(({status, reason}) => ({status, reason})),
    }, locations.resolved);
  }
  const recommendations = Object.fromEntries(flavors.map(key => [key, catalog.recommendations[key]
    .filter(item => (!flavor || flavor === key) && (!host || host === item.host) && (!boundary || boundary === item.boundary_id))
    .map(item => clone(item))]));
  const groups = [...points.keys()].sort().map(id => points.get(id));
  for (const row of groups) row.suggested.sort();
  entries.sort((left, right) => left.id < right.id ? -1 : left.id > right.id ? 1 : 0);
  return {status: 'ok', entries, groups, recommendations};
}

function selectSource(catalog, id, {known = {}} = {}) {
  const {additions, conflicts} = knownDefinitions(known, catalog);
  if (conflicts.has(id)) fail('Project-known identity conflicts with a different curated source: ' + id);
  const curated = catalog.entries.get(id);
  if (curated) {
    if (!curated.descriptor) fail('Catalog source requires adapter preparation: ' + id);
    return clone(curated.descriptor);
  }
  const addition = additions.get(id);
  if (!addition) fail('Select an exact known plugin identity');
  return clone(addition.locator ? {...addition.descriptor, locator: addition.locator} : addition.descriptor);
}

module.exports = {loadCatalog, emptyCatalog, catalogView, selectSource};
