"""Validate the observed pinned Blender process, exact FBX and carry wrappers."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from math import isclose
from pathlib import Path
import re
import sys


FIXTURES = '.skill-tree/tests/fixtures/director/'
HISTORY = '.skill-tree/history/validation/director/'
MANIFEST = HISTORY + 'lantern-art.json'
RESULT = HISTORY + 'lantern-art-result.json'
EVIDENCE = HISTORY + 'lantern-art/'
PROFILE = '.skill-tree/installation/profile.json'
TASK = 'T-2d4cdd62-11bd-49b7-906f-343a0df202f3'
RECIPE = 'director-blender-observed'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pin(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)


def identity(value, prefix):
    return isinstance(value, str) and re.fullmatch(prefix + r'-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', value)


def time(value):
    timestamp = datetime.fromisoformat(value)
    require(timestamp.tzinfo is not None, 'Native process timestamps need a timezone')
    return timestamp


def raw(root, relative):
    path = root
    for part in relative.split('/'):
        require(part not in {'', '.', '..'} and '\\' not in part, 'Nonportable evidence locator')
        path = path / part
        require(not path.is_symlink(), 'Evidence may not traverse a symlink')
    require(path.is_file() and 0 < path.stat().st_size <= 8_000_000, 'Native evidence is missing or oversized')
    return path.read_bytes()


def asset(root, record, name):
    require(record['path'] == name and pin(record['sha256']), 'Unexpected evidence identity')
    data = raw(root, EVIDENCE + name.lower())
    require(sha(data) == record['sha256'], 'Raw native evidence digest changed: ' + name)
    return data


def values_match(first, second, tolerance=0.001):
    return len(first) == len(second) and all(
        isinstance(a, (int, float)) and isinstance(b, (int, float)) and isclose(a, b, abs_tol=tolerance)
        for a, b in zip(first, second)
    )


def verify_model(fixture, native):
    model = fixture['model']
    initial, imported = (native[key] for key in ('pre_export', 'native_reimport'))
    for record in (initial, imported):
        require(record['mesh_names'] == ['CarryGrip', 'LanternBody', 'LanternCap', 'LanternFoot']
                and isinstance(record['vertices'], int) and record['vertices'] > 100
                and set(record['sockets']) == set(model['sockets'])
                and values_match(sorted(record['dimensions']), sorted(model['scale_meters']), 0.005),
                'The opposite-side reader observed changed geometry, scale or attachment names')
    for name, position in model['sockets'].items():
        require(values_match(initial['sockets'][name], position), 'Reviewed grip/socket position changed')
    require(isclose(initial['socket_distance'], imported['socket_distance'], abs_tol=0.005)
            and 0.19 <= imported['socket_distance'] <= 0.205,
            'The exact relinked grip and belt sockets lost their metric separation')


def verify_wrapper(root, artifact, fixture, mode, reference):
    structure = fixture['wrappers'][mode]
    model = fixture['model']
    story = fixture['story'][mode]
    story_bytes = raw(root, story['path'])
    reviewed = json.loads(story_bytes)
    require(sha(story_bytes) == story['sha256']
            and (reviewed['requirement_id'], reviewed['revision'], reviewed['attachment']) ==
            (fixture['story']['id'], story['revision'], mode), 'The marked story approval differs from the exact revision')
    observed = json.loads(asset(root, reference, structure['path']))
    require(observed == {
        'schema': 1, 'revision': structure['revision'], 'attachment': mode, 'socket': structure['socket'],
        'artifact': {key: artifact[key] for key in ('path', 'sha256')},
        'story': {'id': fixture['story']['id'], 'revision': story['revision'], 'sha256': story['sha256']},
        'scale_meters': model['scale_meters'], 'grip_socket': model['sockets']['GripSocket'],
        'belt_socket': model['sockets']['BeltSocket'],
    }, 'The accepted candidate wrapper differs from the reviewed story or model')
    return observed


def verify(root):
    fixture_bytes = raw(root, FIXTURES + 'lantern-fixture.json')
    fixture = json.loads(fixture_bytes)
    manifest_bytes = raw(root, MANIFEST)
    manifest = json.loads(manifest_bytes)
    result = json.loads(raw(root, RESULT))
    source_profile = raw(root, PROFILE)
    source_snapshot = json.loads(raw(root, FIXTURES + 'unity-baseline.json'))['observed_baseline']['original_snapshot']
    require(fixture['schema'] == 1 and fixture['kind'] == 'director-lantern-fixture'
            and result['schema'] == 1 and result['kind'] == 'director-lantern-art-result'
            and manifest['fixture_sha256'] == sha(fixture_bytes) and result['manifest_sha256'] == sha(manifest_bytes)
            and manifest['producer_sha256'] == sha(raw(root, FIXTURES + 'produce-lantern-blender.py')),
            'Observed native evidence does not match the reviewed exact native attempt inputs')
    require(result['task_id'] == manifest['task_id'] == TASK
            and result['fixture_id'] == manifest['fixture_id'] == fixture['fixture_id']
            and result['source_run_id'] == manifest['source_run_id'] and identity(result['source_run_id'], 'WR')
            and identity(result['attempt_id'], 'C'), 'Native evidence has the wrong task, attempt or source run')
    require(result['profile_sha256'] == manifest['profile_sha256'] == sha(source_profile)
            and json.loads(source_profile)['recipes'][RECIPE]['lane'] == 'native',
            'Current owned profile differs or the Blender recipe is unavailable')
    require(result['source_before'] == result['source_after'] == manifest['original_snapshot'] == source_snapshot
            and source_snapshot['files'] > 0 and pin(source_snapshot['sha256']), 'Original sandbox source changed')
    tool = result['tool']
    require((tool['version'], tool['build']) == (fixture['tool_pins']['blender_version'], fixture['tool_pins']['blender_build'])
            and pin(tool['executable_sha256']) and tool['executable_sha256'] == manifest['blender_executable_sha256'],
            'Observed Blender executable differs from the exact approved version and build')
    process = result['process']
    require(type(process['pid']) is int and process['pid'] > 0 and process['exit_code'] == 0
            and process['process_group_cleared'] is True
            and time(result['prepared_at']) <= time(process['started_at']) <= time(process['finished_at']) < time(result['deadline']),
            'The actual Blender process did not complete cleanly inside its prepared native window')
    require(b'DIRECTOR_LANTERN_EXPORT_VERIFIED' in asset(root, process['log'], 'blender.log'),
            'The owned Blender process log lacks completed round trip')
    native = json.loads(asset(root, result['native'], 'blender-native.json'))
    require(native['kind'] == 'director-lantern-blender-runtime' and native['schema'] == 1
            and native['artifact'] == result['artifact'] and native['pid'] == process['pid']
            and native['version'] == tool['version'] and native['build'] == tool['build']
            and native['manifest_sha256'] == manifest['fixture_sha256'],
            'Embedded Blender observation does not match launcher and exact artifact')
    fbx = asset(root, result['artifact'], fixture['model']['asset'])
    require(fbx.startswith(b'Kaydara FBX Binary  \x00\x1a\x00') and result['artifact']['bytes'] == len(fbx),
            'The exact Blender candidate is not the observed binary FBX')
    verify_model(fixture, native)
    hand, belt = (verify_wrapper(root, result['artifact'], fixture, mode, result['wrappers'][mode])
                  for mode in ('hand', 'belt'))
    require(hand['story']['sha256'] != belt['story']['sha256'] and hand['revision'] != belt['revision']
            and hand['socket'] == 'GripSocket' and belt['socket'] == 'BeltSocket',
            'The recorded carry revision did not independently change the active socket')
    return {'status': 'pass', 'lane': 'native', 'attempt_id': result['attempt_id'],
            'artifact_sha256': result['artifact']['sha256'], 'hand': hand['story']['revision'], 'belt': belt['story']['revision']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root.resolve(strict=True)), sort_keys=True))
    except (KeyError, OSError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
