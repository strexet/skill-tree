'use strict';

const {hash, json, fail} = require('./plugin-registry.js');

const CONFIG = '.skill-tree/development-policies.json';
const definitions = Object.freeze({
  'direct-replacement': 'Replace the active implementation, migrate affected consumers, and retire the superseded path. Preserve compatibility for explicit owner requirements or matching API locks. During planning and review, verify the entry point and report a blocking finding only for a concrete violation evidenced by the active path. Identify the affected consumer and retirement condition for any authorized transition. Treat variant names as prompts to inspect source.',
  'network-polling': 'For changed recurring network refresh, establish freshness and available source mechanisms. Choose a user-triggered or lifecycle request when sufficient and an existing suitable subscription when continuous updates are needed. For pull-only sources or other demonstrated requirements, justify the interval, owner, start and stop conditions, error and recovery behavior, and how requests avoid overlap. Report concrete violations as blocking findings and state the missing fact for inconclusive observations. Bounded local process waits fall outside the network policy.'
});
const roles = new Set([
  'skill-tree-implement-all', 'skill-tree-implement-next-future-task',
  'skill-tree-work-through-next', 'skill-tree-pr-review-cycle'
]);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);

function configuration(raw) {
  if (raw === null) return {schema: 1, policies: {}, locks: {}};
  const value = JSON.parse(raw);
  if (!object(value) || value.schema !== 1 || !object(value.policies) ||
      Object.keys(value).some(key => !['schema', 'policies', 'locks'].includes(key)) ||
      Object.entries(value.policies).some(([id, enabled]) => !Object.hasOwn(definitions, id) || typeof enabled !== 'boolean') ||
      (value.locks !== undefined && !object(value.locks))) {
    fail('development-policy', 'Unsupported project development policy configuration');
  }
  return {...value, locks: value.locks ?? {}};
}

function effective(raw) {
  const config = configuration(raw);
  return {
    input_digest: raw === null ? null : hash(raw),
    policies: Object.keys(definitions).map(id => ({
      id, enabled: config.policies[id] ?? true,
      origin: Object.hasOwn(config.policies, id) ? 'project' : 'default'
    })),
    lock_review: Object.keys(config.locks).length ? {
      id: 'api-lock-review', enabled: true, managed_by: 'lock-api',
      operation: 'skill-tree-pr-review-cycle', anchor: 'before-pr-ready',
      config: CONFIG, locks: Object.keys(config.locks).sort()
    } : null
  };
}

function instructions(profile, operation = null) {
  if (operation && !roles.has(operation)) return '';
  const active = profile.development_policies;
  if (!active) return '';
  const rules = active.policies.filter(row => row.enabled).map(row => '- `' + row.id + '` ' + definitions[row.id]);
  if (rules.length && operation === 'skill-tree-pr-review-cycle') {
    rules.push('Record policy observations with the current full review using `development_policy_observations`. Use `policy`, `outcome: violation`, a stable `id`, changed-file `path`, one-based `line`, exact candidate `source_line`, `cause`, `consequence` and `severity`. Explain the actual execution path and how the change violates the active rule. Use the finding ID returned by the review helper to record verified fixes or dismissals on the current head. Use `outcome: inconclusive` and `missing_fact` when decisive context is unavailable.');
  }
  if (active.lock_review && (!operation || operation === 'skill-tree-pr-review-cycle')) {
    rules.push('- `api-lock-review` Check the active project API locks before PR readiness. Report the affected contract and current check result. Missing required check evidence blocks readiness.');
  }
  return rules.length ? '## Project Development Policies\n\n' + rules.join('\n') + '\n' : '';
}

function toggle(config, id, enabled) {
  if (id === 'api-lock-review') fail('api-lock-managed', 'Use unlock-api to remove managed API lock review');
  if (!Object.hasOwn(definitions, id) || typeof enabled !== 'boolean') {
    fail('development-policy', 'Select an exact built-in policy and explicit enabled state');
  }
  return {...config, policies: {...config.policies, [id]: enabled}};
}

module.exports = {CONFIG, configuration, effective, instructions, toggle, encode: json};
