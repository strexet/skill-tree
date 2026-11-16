#!/usr/bin/env python3
"""Check finite, declared narrative routes without executing story code."""

import argparse
import json
from pathlib import Path
import re


ID = re.compile(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')
EXITS = {'terminal', 'continuation'}
OPS = {'eq', 'ne', 'lt', 'lte', 'gt', 'gte'}
ROUTE_DIAGNOSTICS = {
    'unavailable-state', 'unavailable-action', 'offered-mismatch', 'state-mismatch',
    'missing-exit', 'exit-mismatch', 'node-mismatch', 'visit-limit', 'repeated-unique-effect',
}


class RouteError(ValueError):
    def __init__(self, code, field, route=None, step=None):
        super().__init__(f'{code}: {field}')
        self.diagnostic = {'code': code, 'field': field}
        if route is not None:
            self.diagnostic['route'] = route
        if step is not None:
            self.diagnostic['step'] = step


def require(condition, field, code='malformed-contract'):
    if not condition:
        raise RouteError(code, field)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, key, 'duplicate-key')
        result[key] = value
    return result


def load(path):
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def locate(origin, relative):
    require(isinstance(relative, str) and relative, 'locator')
    parts = relative.split('/')
    require(all(part not in {'', '.', '..'} for part in parts)
            and not any(char in relative for char in ('\\', ':', '\0')), 'portable relative locator')
    path = origin.parent
    for part in parts:
        path = path / part
        require(not path.is_symlink(), relative)
    require(path.is_file(), relative)
    return path


def identity(value):
    return isinstance(value, str) and ID.fullmatch(value) is not None


def integer(value):
    return type(value) is int


def value_matches(entry, value):
    kind = entry['type']
    if kind == 'boolean':
        return type(value) is bool
    if kind == 'enum':
        return isinstance(value, str) and value in entry['allowed']
    return integer(value) and entry['minimum'] <= value <= entry['maximum']


def registry_values(data, work):
    require(isinstance(data, dict) and type(data.get('schema_version')) is int and data['schema_version'] == 1 and data.get('work_id') == work, 'state registry identity')
    values = data.get('values')
    require(isinstance(values, dict) and values, 'state registry values')
    for key, entry in values.items():
        require(identity(key) and isinstance(entry, dict) and entry.get('type') in ('boolean', 'enum', 'integer'), key)
        if entry['type'] == 'enum':
            allowed = entry.get('allowed')
            require(isinstance(allowed, list) and allowed and all(isinstance(v, str) for v in allowed)
                    and len(set(allowed)) == len(allowed), f'{key}.allowed')
        if entry['type'] == 'integer':
            low, high = entry.get('minimum'), entry.get('maximum')
            require(integer(low) and integer(high) and low <= high, f'{key}.bounds')
        require('initial' in entry and value_matches(entry, entry['initial']), f'{key}.initial')
        require(type(entry.get('unique_effect', False)) is bool, f'{key}.unique_effect')
    return values


def assignments(values, data, field):
    require(isinstance(data, dict), field)
    for key, value in data.items():
        require(key in values and value_matches(values[key], value), f'{field}.{key}')


def validate_predicate(predicate, values, depth=0):
    require(isinstance(predicate, dict) and depth < 32, 'predicate')
    keys = set(predicate)
    if keys in ({'all'}, {'any'}):
        members = next(iter(predicate.values()))
        require(isinstance(members, list) and members, 'predicate operands')
        for member in members:
            validate_predicate(member, values, depth + 1)
        return
    require(keys == {'key', 'op', 'value'}, 'predicate form')
    key, op = predicate['key'], predicate['op']
    require(isinstance(key, str) and key in values and isinstance(op, str) and op in OPS, 'predicate key or operation')
    require(op in {'eq', 'ne'} or values[key]['type'] == 'integer', 'predicate integer ordering')
    require(value_matches(values[key], predicate['value']), f'{key}.predicate value')


def predicate_result(predicate, state, route, position):
    if 'all' in predicate or 'any' in predicate:
        op, members = next(iter(predicate.items()))
        results = [predicate_result(member, state, route, position) for member in members]
        return all(results) if op == 'all' else any(results)
    key, op, right = predicate['key'], predicate['op'], predicate['value']
    if key not in state:
        raise RouteError('unavailable-state', key, route, position)
    left = state[key]
    if op == 'eq':
        return left == right
    if op == 'ne':
        return left != right
    return {'lt': left < right, 'lte': left <= right, 'gt': left > right, 'gte': left >= right}[op]


def validate_model(model, values):
    require(isinstance(model, dict), 'model')
    nodes = model.get('nodes')
    require(isinstance(nodes, dict) and nodes, 'nodes')
    entry = model.get('entry')
    require(identity(entry) and entry in nodes, 'entry')
    for node_id, node in nodes.items():
        require(identity(node_id) and isinstance(node, dict), 'node identity')
        actions = node.get('actions')
        require(isinstance(actions, dict), f'{node_id}.actions')
        if 'exit' in node:
            require(isinstance(node['exit'], str) and node['exit'] in EXITS and not actions, f'{node_id}.exit')
        assignments(values, node.get('on_enter_once', {}), f'{node_id}.on_enter_once')
        for action_id, action in actions.items():
            require(identity(action_id) and isinstance(action, dict), f'{node_id}.action')
            target = action.get('target')
            require(identity(target) and target in nodes, f'{node_id}.{action_id}.target')
            assignments(values, action.get('effects', {}), f'{node_id}.{action_id}.effects')
            if 'when' in action:
                validate_predicate(action['when'], values)


def validate_trace(trace, nodes, values):
    require(isinstance(trace, dict) and identity(trace.get('id')), 'trace identity')
    for field in ['initial_state', 'expected_state']:
        assignments(values, trace.get(field), field)
    require(isinstance(trace.get('expected_exit'), str) and trace['expected_exit'] in EXITS, 'expected_exit')
    limits = trace.get('visit_limits', {})
    require(isinstance(limits, dict) and all(key in nodes and integer(value) and value > 0
                                             for key, value in limits.items()), 'visit limits')
    steps = trace.get('steps')
    require(isinstance(steps, list) and 0 < len(steps) <= 10000, 'trace steps')
    for index, step in enumerate(steps):
        require(isinstance(step, dict) and identity(step.get('node')) and step['node'] in nodes, f'step {index}.node')
        offered = step.get('offered')
        require(isinstance(offered, list) and all(identity(key) for key in offered)
                and len(set(offered)) == len(offered), f'step {index}.offered')
        require(identity(step.get('action')) if index + 1 < len(steps) else 'action' not in step,
                f'step {index}.action')


def apply_effects(state, changes, values, unique, route, position):
    for key, value in changes.items():
        if values[key].get('unique_effect'):
            if key in unique:
                raise RouteError('repeated-unique-effect', key, route, position)
            unique.add(key)
        state[key] = value


def check_trace(model, trace, values):
    validate_trace(trace, model['nodes'], values)
    route, state = trace['id'], dict(trace['initial_state'])
    current = model['entry']
    visits = {}
    unique = {key for key, value in state.items()
              if values[key].get('unique_effect') and value != values[key]['initial']}
    for index, step in enumerate(trace['steps']):
        if current != step['node']:
            raise RouteError('node-mismatch', current, route, index)
        node = model['nodes'][current]
        visits[current] = visits.get(current, 0) + 1
        if visits[current] > trace.get('visit_limits', {}).get(current, 1):
            raise RouteError('visit-limit', current, route, index)
        if visits[current] == 1:
            apply_effects(state, node.get('on_enter_once', {}), values, unique, route, index)
        offered = {key for key, action in node['actions'].items()
                   if 'when' not in action or predicate_result(action['when'], state, route, index)}
        if offered != set(step['offered']):
            raise RouteError('offered-mismatch', f'{current}: {sorted(offered)}', route, index)
        choice = step.get('action')
        if choice is None:
            if 'exit' not in node:
                raise RouteError('missing-exit', current, route, index)
            if node['exit'] != trace['expected_exit']:
                raise RouteError('exit-mismatch', current, route, index)
            for key, value in trace['expected_state'].items():
                if key not in state:
                    raise RouteError('unavailable-state', key, route, index)
                if state[key] != value:
                    raise RouteError('state-mismatch', key, route, index)
            return
        if choice not in offered:
            raise RouteError('unavailable-action', choice, route, index)
        action = node['actions'][choice]
        apply_effects(state, action.get('effects', {}), values, unique, route, index)
        current = action['target']


def check_case(model, traces, values, expected=None):
    validate_model(model, values)
    require(isinstance(traces, list) and traces, 'traces')
    require(expected is None or isinstance(expected, str) and expected in ROUTE_DIAGNOSTICS
            and len(traces) == 1, 'expected route diagnostic')
    seen, rows = set(), []
    for trace in traces:
        name = trace.get('id') if isinstance(trace, dict) else None
        require(identity(name) and name not in seen, 'trace identity')
        seen.add(name)
        diagnostic = None
        try:
            check_trace(model, trace, values)
        except RouteError as error:
            if error.diagnostic['code'] not in ROUTE_DIAGNOSTICS:
                raise RouteError(error.diagnostic['code'], error.diagnostic['field'], route=name) from error
            diagnostic = error.diagnostic
        observed = diagnostic['code'] if diagnostic else None
        rows.append({'id':name, 'expected_diagnostic':expected, 'observed_diagnostic':diagnostic,
                     'result':'pass' if observed == expected else 'fail'})
    return rows


def load_contract(path, contract=None):
    contract = load(path) if contract is None else contract
    require(isinstance(contract, dict) and type(contract.get('schema_version')) is int
            and contract['schema_version'] == 1, 'contract version')
    require(identity(contract.get('work_id')) and identity(contract.get('continuity_id')), 'work or continuity')
    source = contract.get('source')
    require(isinstance(source, dict) and ((set(source) == {'draft_id'} and identity(source['draft_id']))
            or (set(source) == {'snapshot_sha256'} and isinstance(source['snapshot_sha256'], str)
                and SHA.fullmatch(source['snapshot_sha256']))), 'source identity')
    registry = load(locate(path, contract.get('state_registry')))
    return contract, registry_values(registry, contract['work_id'])


def run(path):
    data = load(path)
    require(isinstance(data, dict), 'document')
    if 'cases' not in data:
        contract, values = load_contract(path, data)
        return check_case(contract, contract.get('traces'), values)
    require(type(data.get('schema_version')) is int and data['schema_version'] == 1
            and isinstance(data['cases'], list) and data['cases'], 'fixture version or cases')
    model, values = load_contract(locate(path, data.get('base_contract')))
    results, seen = [], set()
    for case in data['cases']:
        require(isinstance(case, dict) and identity(case.get('id')) and case['id'] not in seen, 'case identity')
        seen.add(case['id'])
        rows = check_case(case.get('model', model), case.get('traces'), values, case.get('expected_diagnostic'))
        results.extend({'case':case['id'], **row} for row in rows)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path)
    args = parser.parse_args()
    try:
        rows = run(args.document)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError, RouteError) as error:
        diagnostic = error.diagnostic if isinstance(error, RouteError) else {'code':'invalid-input','field':str(error)}
        print(json.dumps({'scope':'declared-traces-only','result':'error','diagnostic':diagnostic}, sort_keys=True))
        return 2
    passed = all(row['result'] == 'pass' for row in rows)
    print(json.dumps({'scope':'declared-traces-only','result':'pass' if passed else 'fail',
                      'traces':rows}, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
