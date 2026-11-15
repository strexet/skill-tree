#!/usr/bin/env python3
"""Compile Director plans from read-only, positively identified source records."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import PurePosixPath
import re


TOKEN = re.compile(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z')
RECORD = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]*\Z')
SHA = re.compile(r'[0-9a-f]{64}\Z')
OBJECT = re.compile(r'(?:OB|PL|P|T)-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z')
WORKSPACES = {'existing-checkout', 'artifact', 'recorded-worktree', 'separate-clone', 'separate-runtime'}
PIN_STATES = {'verified', 'missing', 'changed', 'unavailable', 'unsupported', 'inferred'}


class PlanError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise PlanError(message)


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def matches(value, pattern):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def token(value):
    return matches(value, TOKEN)


def task_id(value, prefixes):
    return matches(value, OBJECT) and value.split('-', 1)[0] in prefixes


def fields(value, required, optional=()):
    require(isinstance(value, dict) and required <= value.keys() and not value.keys() - required - set(optional),
            'Unexpected plan input fields')


def text(value):
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def distinct(values, name, check, *, at_least_one=False):
    require(isinstance(values, list) and (values or not at_least_one) and all(check(value) for value in values),
            f'Invalid {name}')
    require(len(set(values)) == len(values), f'Duplicate {name}')
    return sorted(values)


def path(value):
    return (text(value) and '\\' not in value and ':' not in value.split('/', 1)[0]
            and all(part not in {'', '.', '..', '.git'} for part in value.split('/')))


def choose_area(areas, assignment, resolve_area):
    explicit = assignment.get('area_id')
    candidates = [
        area for area in areas.values()
        if area['role'] == assignment['role'] and assignment['capability'] in area['capabilities']
        and (explicit is None or area['id'] == explicit)
    ]
    qualified = []
    for candidate in sorted(candidates, key=lambda area: area['id']):
        evidence = resolve_area(deepcopy(candidate), assignment['capability'])
        if evidence is not None:
            fields(evidence, {'head', 'profile_sha256', 'qualification_sha256'})
            require(all(matches(evidence[k], SHA) for k in ('profile_sha256', 'qualification_sha256'))
                    and isinstance(evidence['head'], str)
                    and re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', evidence['head']) is not None,
                    'Unusable area qualification')
            identity = {k: candidate[k] for k in ('id', 'queue_id', 'repo_id', 'scope')}
            qualified.append((candidate, {**identity, 'qualification': deepcopy(evidence)}))
    require(len(qualified) == 1, f"Assignment {assignment['id']} requires one positively qualified area")
    return qualified[0]


def compile_pin(areas, value, resolve_pin):
    fields(value, {'area_id', 'adapter', 'record_id', 'revision', 'sha256', 'role', 'strength'},
           {'snapshot', 'path', 'preliminary_check', 'replacement_gate'})
    require(matches(value['area_id'], TOKEN) and value['area_id'] in areas
            and all(matches(value[k], TOKEN) for k in ('adapter', 'role'))
            and all(matches(value[k], RECORD) for k in ('record_id', 'revision'))
            and matches(value['sha256'], SHA), 'Source pin requires exact portable identity, revision and digest')
    require('snapshot' not in value or matches(value['snapshot'], RECORD), 'Invalid source snapshot')
    require('path' not in value or path(value['path']), 'Invalid source path')
    strength = value['strength']
    require(strength in ('required', 'optional', 'provisional'), 'Invalid source requirement strength')
    gates = {'preliminary_check', 'replacement_gate'} & value.keys()
    if strength == 'provisional':
        require(len(gates) == 2 and all(matches(value[k], TOKEN) for k in gates),
                'Provisional source requires exact preliminary check and replacement gate')
    else:
        require(not gates, 'Only provisional source has a replacement gate')
    observation = resolve_pin(deepcopy(areas[value['area_id']]), deepcopy(value))
    fields(observation, {'status'}, {'revision', 'sha256'})
    state = observation['status']
    require(isinstance(state, str) and state in PIN_STATES, 'Unknown source evidence state')
    if state == 'verified':
        require(observation.get('revision') == value['revision'] and observation.get('sha256') == value['sha256'],
                'Verified source differs from the exact pin')
    elif strength != 'optional':
        raise PlanError(f"Source {value['record_id']} for {strength} pin is {state}")
    return {**value, 'status': state}


def compile_child(candidate, child, effects, resolve_child):
    require(isinstance(child, dict), 'Child selection requires existing task or bounded intake')
    if 'task_id' in child:
        fields(child, {'task_id', 'body_sha256'})
        require(task_id(child['task_id'], {'P', 'T'}) and matches(child['body_sha256'], SHA),
                'Existing task requires exact ID and body digest')
        observed = resolve_child(deepcopy(candidate), deepcopy(child))
        require(observed == child, 'Existing child task is missing or its exact body changed')
        return deepcopy(child)
    fields(child, {'title', 'description', 'acceptance'})
    require('intake' in effects and text(child['title']) and text(child['description'])
            and isinstance(child['acceptance'], list) and child['acceptance'] and all(map(text, child['acceptance'])),
            'New child task requires a bounded authorized intake')
    return deepcopy(child)


def compile_assignment(areas, request, resolve_area, resolve_pin, resolve_child):
    fields(request, {'id', 'role', 'capability', 'workspace', 'write_paths', 'resources', 'child', 'pins',
                     'depends_on', 'expected_result', 'check', 'authority_ref', 'effects', 'stop_rules'}, {'area_id'})
    require(all(matches(request[k], TOKEN) for k in ('id', 'role', 'capability', 'check', 'authority_ref'))
            and ('area_id' not in request or matches(request['area_id'], TOKEN))
            and isinstance(request['workspace'], str) and request['workspace'] in WORKSPACES
            and text(request['expected_result']), 'Invalid assignment scope or verification')
    candidate, area = choose_area(areas, request, resolve_area)
    effects = distinct(request['effects'], 'effects', token)
    require(set(effects) <= set(candidate['allowed_effects']), 'Requested effects exceed registered area effects')
    require(isinstance(request['pins'], list), 'Assignments require a list of explicit source pins')
    pins = [compile_pin(areas, pin, resolve_pin) for pin in request['pins']]
    pin_ids = [tuple(pin[k] for k in ('area_id', 'adapter', 'record_id', 'role')) for pin in pins]
    require(len(pin_ids) == len(set(pin_ids)), 'Duplicate source pin')
    assignment = {k: request[k] for k in ('id', 'role', 'capability', 'workspace', 'expected_result',
                                          'check', 'authority_ref')}
    assignment.update(
        area=area,
        write_paths=distinct(request['write_paths'], 'write paths', path),
        resources=distinct(request['resources'], 'resource keys', token),
        child=compile_child(candidate, request['child'], effects, resolve_child),
        pins=[pin for _, pin in sorted(zip(pin_ids, pins), key=lambda pair: pair[0])],
        depends_on=distinct(request['depends_on'], 'dependencies', token),
        effects=effects,
        stop_rules=distinct(request['stop_rules'], 'stop rules', text, at_least_one=True),
    )
    return assignment


def ordered_assignments(assignments):
    identities = {assignment['id']: assignment for assignment in assignments}
    require(len(identities) == len(assignments), 'Duplicate assignment identity')
    children = [(item['area']['queue_id'], item['child']['task_id']) for item in assignments if 'task_id' in item['child']]
    require(len(set(children)) == len(children), 'An exact child task can have only one assignment in this plan')
    for assignment in assignments:
        require(set(assignment['depends_on']) <= identities.keys(),
                f"Assignment {assignment['id']} has unknown dependencies")
    ancestors = {}
    for _ in assignments:
        next_id = next((key for key in sorted(identities.keys() - ancestors.keys())
                        if set(identities[key]['depends_on']) <= ancestors.keys()), None)
        require(next_id is not None, 'Assignment dependency cycle')
        direct = identities[next_id]['depends_on']
        ancestors[next_id] = set(direct).union(*(ancestors[key] for key in direct))
    for current, preceding in ancestors.items():
        left = identities[current]
        ls = PurePosixPath(left['area']['scope'])
        for other in sorted(ancestors.keys() - preceding):
            if current >= other or current in ancestors[other]:
                continue
            right = identities[other]
            if left['area']['queue_id'] != right['area']['queue_id'] or 'artifact' in {left['workspace'], right['workspace']}:
                continue
            rs = PurePosixPath(right['area']['scope'])
            require(not any(overlap(ls / a, rs / b) for a in left['write_paths'] for b in right['write_paths']),
                    f'Unordered assignment writes overlap: {current}, {other}')
    return [identities[key] for key in ancestors]


def overlap(left, right):
    return left == right or left in right.parents or right in left.parents


def compile_plan(registry, objective, request, resolve_area, resolve_pin, resolve_child):
    """Project portable scope without persistence or any child mutation."""
    fields(request, {'plan_id', 'plan_revision', 'objective_id', 'objective_revision', 'objective_sha256',
                     'assignments'})
    require(task_id(request['plan_id'], {'PL'}) and task_id(request['objective_id'], {'OB'})
            and type(request['plan_revision']) is int and request['plan_revision'] > 0
            and type(request['objective_revision']) is int and request['objective_revision'] > 0
            and matches(request['objective_sha256'], SHA), 'Plan requires exact versioned identities')
    expected = {k: request[k] for k in ('objective_id', 'objective_revision', 'objective_sha256')}
    observed = {'objective_id': objective['objective_id'], 'objective_revision': objective['revision']['revision'],
                'objective_sha256': objective['revision']['sha256']}
    require(expected == observed and objective['director_id'] == registry['director_id'],
            'Objective record differs from the exact requested revision')
    require(isinstance(request['assignments'], list) and request['assignments'], 'Plan requires assignments')
    assignments = ordered_assignments([
        compile_assignment(registry['areas'], selection, resolve_area, resolve_pin, resolve_child)
        for selection in request['assignments']
    ])
    plan = {
        'schema': 1,
        'director_id': registry['director_id'],
        'registry_revision': registry['revision'],
        'objective': expected,
        'plan_id': request['plan_id'],
        'plan_revision': request['plan_revision'],
        'assignments': assignments,
    }
    plan_sha256 = digest(plan)
    return {'plan': plan, 'sha256': plan_sha256, 'briefs': {
        item['id']: {**expected, 'plan_id': plan['plan_id'], 'plan_revision': plan['plan_revision'],
                     'plan_sha256': plan_sha256, **deepcopy(item)}
        for item in assignments
    }}


def context(plan):
    return {'objective': deepcopy(plan['objective']), 'assignments': [
        {'id': item['id'], 'area_id': item['area']['id'], 'pins': deepcopy(item['pins'])}
        for item in plan['assignments']
    ]}


def impact(plan, changed):
    """Project dependency paths from a known changed source identity."""
    fields(changed, {'area_id', 'adapter', 'record_id'})
    require(all(matches(changed[k], TOKEN) for k in ('area_id', 'adapter'))
            and matches(changed['record_id'], RECORD), 'Impact requires exact source identity')
    paths = {}
    for item in plan['assignments']:
        incoming = [path + [item['id']] for predecessor in item['depends_on'] for path in paths.get(predecessor, [])]
        pins = [pin for pin in item['pins'] if all(pin[k] == value for k, value in changed.items())]
        if pins:
            incoming.append([item['id']])
        if incoming:
            paths[item['id']] = incoming
    return {
        'source': deepcopy(changed),
        'coverage': 'recorded-paths' if paths else 'unknown',
        'affected': [{'assignment_id': key, 'paths': value} for key, value in paths.items()],
        'unknown': [{'assignment_id': item['id'], 'pin': deepcopy(pin)}
                    for item in plan['assignments'] for pin in item['pins'] if pin['status'] != 'verified'],
    }
