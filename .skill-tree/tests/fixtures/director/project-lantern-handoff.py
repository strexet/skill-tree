"""Project verified Blender and Unity observations onto the Director carry change."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from xml.etree import ElementTree


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
HISTORY = '.skill-tree/history/validation/director/'
FIXTURES = '.skill-tree/tests/fixtures/director/'
HANDOFF = HISTORY + 'lantern-handoff.json'
MODES = ('EditMode', 'PlayMode')
EVIDENCE_ENV = 'DIRECTOR_LANTERN_UNITY_EVIDENCE_ROOT'
PLAN_SOURCE = '.skill-tree/common/scripts/director-plans.py'


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem.replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ART = load(HERE / 'verify-lantern-art.py')
UNITY = load(HERE / 'verify-unity-lantern.py')
PLANS = load(ROOT / PLAN_SOURCE)


def reference(root, relative):
    return {'path': relative, 'sha256': ART.sha(ART.raw(root, relative))}


def review_sources(root):
    return {path: reference(root, path)['sha256'] for path in (
        PLAN_SOURCE, FIXTURES + 'project-lantern-handoff.py', FIXTURES + 'verify-lantern-art.py',
        FIXTURES + 'verify-unity-lantern.py', FIXTURES + 'verify-unity-baseline.py',
        FIXTURES + 'produce-lantern-blender.py', FIXTURES + 'run-unity-lantern.py',
        FIXTURES + 'lantern-fixture.json', FIXTURES + 'unity-baseline.json', HISTORY + 'unity-baseline.json',
    )}


def inputs(root):
    art_bytes = ART.raw(root, ART.RESULT)
    art = json.loads(art_bytes)
    ART.require(art['schema'] == 1 and art['kind'] == 'director-lantern-art-result'
                and art['task_id'] == ART.TASK and ART.identity(art['source_run_id'], 'WR')
                and ART.identity(art['attempt_id'], 'C'), 'Unexpected Blender task, run or native attempt')
    receipts = {}
    for mode in MODES:
        receipt, *values = UNITY.receipt_inputs(root, mode)
        fixture = UNITY.verify_compact(receipt, mode, *values)
        ART.require(receipt['task_id'] == art['task_id'] and receipt['source_run_id'] == art['source_run_id']
                    and receipt['fixture_id'] == art['fixture_id'] == fixture['fixture_id']
                    and receipt['artifact'] == art['artifact'] and receipt['wrappers'] == art['wrappers']
                    and receipt['evidence']['art']['sha256'] == ART.sha(art_bytes),
                    'Unity receipt does not attach the exact observed Blender candidate and both carry revisions')
        receipts[mode] = receipt
    edit, play = (receipts[mode] for mode in MODES)
    ART.require(all(edit[key] == play[key] for key in ('project_path_sha256', 'profile', 'evidence', 'asset_sources'))
                and edit['batch']['pid'] != play['batch']['pid']
                and ART.time(art['process']['finished_at']) <= ART.time(edit['batch']['started_at'])
                and ART.time(edit['batch']['finished_at']) <= ART.time(play['batch']['started_at']),
                'Unity reports do not identify one matching project, profile and ordered session')
    artifact = art['artifact']
    binary = ART.asset(root, artifact, fixture['model']['asset'])
    ART.require(binary.startswith(b'Kaydara FBX Binary  \x00\x1a\x00') and artifact['bytes'] == len(binary),
                'Archived Blender candidate bytes are unavailable or changed')
    native = json.loads(ART.asset(root, art['native'], 'blender-native.json'))
    ART.require(native['artifact'] == artifact and native['pid'] == art['process']['pid'],
                'Archived Blender geometry proof belongs to a different exact candidate')
    ART.verify_model(fixture, native)
    wrappers = {mode: ART.verify_wrapper(root, artifact, fixture, mode, art['wrappers'][mode])
                for mode in ('hand', 'belt')}
    return fixture, art, receipts, wrappers


def source_pin(area, adapter, record_id, revision, sha256, role):
    return {'area_id': area, 'adapter': adapter, 'record_id': record_id, 'revision': revision,
            'sha256': sha256, 'role': role, 'strength': 'required', 'status': 'verified'}


def assignment(name, area, pins=(), dependencies=()):
    return {'id': name, 'area': {'id': area}, 'pins': list(pins), 'depends_on': list(dependencies)}


def scoped_plan(story, wrapper, model, wall):
    return {'assignments': [
        assignment('lantern-model-geometry', 'art', [model]),
        assignment('lantern-repeat-import', 'game', [model], ['lantern-model-geometry']),
        assignment('wall-mount-diagnostic', 'game', [wall]),
        assignment('lantern-attachment', 'game', [story, wrapper], ['lantern-model-geometry']),
        assignment('lantern-cave-carry', 'game', dependencies=['lantern-repeat-import', 'lantern-attachment']),
    ]}


def unity_reference(root, receipt, mode):
    batch = receipt['batch']
    return {**reference(root, HISTORY + 'lantern-' + mode.lower() + '.json'),
            'xml': batch['report'], 'log': batch['log'], 'pid': batch['pid'],
            'recipe_id': batch['recipe_id'], 'cases': batch['cases']}


def case(receipt, method):
    matches = [row for row in receipt['cases'] if row.rsplit('.', 1)[-1] == method]
    ART.require(len(matches) == 1, 'Exact native Unity method is absent: ' + method)
    return matches[0]


def acceptance(target, verified):
    fields = ('source_pin', 'wrapper_pin', 'socket', 'check', 'observed_batch')
    exact = any(all(receipt[field] == target[field] for field in fields) for receipt in verified)
    return 'eligible' if exact else 'held'


def projection(root, fixture, art, receipts, wrappers):
    model = fixture['model']
    model_pin = source_pin('art', 'blender-observed', model['id'], model['revision'], art['artifact']['sha256'], 'geometry')
    wall = fixture['wall_control']
    wall_pin = source_pin('game', 'unity-control', 'wall-mounted-lantern', wall['guid'], wall['sha256'], 'diagnostic')
    edit, play = (unity_reference(root, receipts[mode], mode) for mode in MODES)
    model_ref = reference(root, ART.EVIDENCE + model['asset'].lower())
    native_ref = reference(root, ART.EVIDENCE + art['native']['path'])
    ART.require(model_ref['sha256'] == model_pin['sha256'] and native_ref['sha256'] == art['native']['sha256'],
                'The reviewed model or native geometry evidence changed during projection')
    model_receipt = {'artifact': model_ref, 'pin': model_pin, 'native_reimport': native_ref}
    states = {}
    plans = {}
    for attachment, method in (('hand', 'HandPickupAndCarryThroughCave'), ('belt', 'BeltPickupAndCarryThroughCave')):
        story = fixture['story'][attachment]
        wrapper = wrappers[attachment]
        story_pin = source_pin('story', 'fixture-narrative', fixture['story']['id'], story['revision'], story['sha256'], 'carry-requirement')
        wrapper_ref = reference(root, ART.EVIDENCE + art['wrappers'][attachment]['path'])
        story_ref = reference(root, story['path'])
        ART.require(wrapper_ref['sha256'] == art['wrappers'][attachment]['sha256'] and story_ref['sha256'] == story['sha256'],
                    'The approved wrapper or story pin changed during projection')
        wrapper_pin = source_pin('art', 'blender-observed', 'lantern-carry-wrapper', wrapper['revision'],
                                  wrapper_ref['sha256'], 'attachment-wrapper')
        plans[attachment] = scoped_plan(story_pin, wrapper_pin, model_pin, wall_pin)
        states[attachment] = {'source_pin': story_pin, 'source': story_ref, 'wrapper_pin': wrapper_pin,
                              'wrapper': wrapper_ref, 'socket': wrapper['socket'], 'check': case(play, method),
                              'observed_batch': play['xml']['sha256']}
    changed = {field: states['hand']['source_pin'][field] for field in ('area_id', 'adapter', 'record_id')}
    impact = PLANS.impact(plans['hand'], changed)
    confirmed = PLANS.impact(plans['belt'], changed)
    ART.require(impact == confirmed and impact['coverage'] == 'recorded-paths' and not impact['unknown']
                and states['hand']['socket'] != states['belt']['socket']
                and states['hand']['source']['sha256'] != states['belt']['source']['sha256']
                and states['hand']['wrapper']['sha256'] != states['belt']['wrapper']['sha256'],
                'The revised requirement does not change only the bounded recorded carry paths')
    affected = {item['assignment_id'] for item in impact['affected']}
    ART.require(affected == {'lantern-attachment', 'lantern-cave-carry'}, 'Unexpected native fixture impact scope')
    unchanged = {item['id']: item for item in plans['hand']['assignments'] if item['id'] not in affected}
    ART.require(unchanged == {item['id']: item for item in plans['belt']['assignments'] if item['id'] not in affected},
                'Independent model or diagnostic fingerprints changed across carry revisions')
    output = {
        'schema': 1, 'kind': 'director-lantern-handoff-observation', 'scope': 'disposable-native-fixture',
        'task_id': art['task_id'], 'source_run_id': art['source_run_id'], 'fixture_id': fixture['fixture_id'],
        'verification_sources': review_sources(root),
        'blender': {**reference(root, ART.RESULT), 'attempt_id': art['attempt_id'], 'model': model_receipt,
                    'manifest': reference(root, ART.MANIFEST),
                    'original_sandbox': {'before': art['source_before'], 'after': art['source_after']}},
        'unity': {'editmode': edit, 'playmode': play, 'profile': receipts['EditMode']['profile'],
                  'project_path_sha256': receipts['EditMode']['project_path_sha256'],
                  'observation': receipts['EditMode']['evidence']['observation']},
        'change': {'previous': states['hand'], 'next': states['belt']},
        'impact': {**impact, 'superseded': sorted(affected), 'current': sorted(unchanged),
                   'unrecorded': ['animation', 'blog']},
        'independent_checks': {
            'lantern-model-geometry': model_receipt,
            'lantern-repeat-import': {'check': case(edit, 'RepeatedImportPreservesGuidMeshAndMetricSockets'),
                                      'report_sha256': edit['xml']['sha256'], 'artifact_sha256': model_pin['sha256']},
            'wall-mount-diagnostic': {'check': case(edit, 'WrongTargetAndWallMountedControlRejectAttachment'),
                                      'report_sha256': edit['xml']['sha256'], 'control': wall},
        },
        'acceptance': {
            'previous_requirement': acceptance(states['hand'], [states['hand']]),
            'replacement_while_unverified': acceptance(states['belt'], [states['hand']]),
            'next_requirement_after_matching_check': acceptance(states['belt'], states.values()),
            'delivery': 'unreviewed',
        },
    }
    return {**output, 'projection_sha256': PLANS.digest(output)}


def verify_observed(root, raw_root, fixture, art, receipts):
    blender = ART.verify(root)
    ART.require(blender['status'] == 'pass' and blender['lane'] == 'native'
                and blender['attempt_id'] == art['attempt_id'] and blender['artifact_sha256'] == art['artifact']['sha256'],
                'Blender native verifier did not pass the exact published artifact attempt')
    for mode in MODES:
        checked = UNITY.verify_native(receipts[mode], mode, fixture, raw_root)
        ART.require(checked == {'passed': 2, 'failed': 0, 'skipped': 0}, 'Incomplete exact Unity native report')


def from_observations(root, raw_root):
    fixture, art, receipts, wrappers = inputs(root)
    verify_observed(root, raw_root, fixture, art, receipts)
    return projection(root, fixture, art, receipts, wrappers)


def verify_archive(root, raw_root=None):
    current = json.loads(ART.raw(root, HANDOFF))
    if raw_root is None:
        derived = projection(root, *inputs(root))
    else:
        derived = from_observations(root, raw_root)
    ART.require(current == derived, 'Archived handoff differs from the exact current reviewed projection')
    return derived


def write(root, report):
    path = root / HANDOFF
    ART.require(not path.exists() and not path.is_symlink(), 'A handoff observation already exists')
    descriptor, temporary = tempfile.mkstemp(prefix='.lantern-handoff-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('raw_unity_evidence', type=Path)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    try:
        root = args.root.resolve(strict=True)
        raw_root = args.raw_unity_evidence.resolve(strict=True)
        report = from_observations(root, raw_root)
        if args.write:
            write(root, report)
        print(json.dumps(report, sort_keys=True))
    except (KeyError, TypeError, OSError, ValueError, ElementTree.ParseError) as error:
        parser.exit(2, f'{error}\n')


if __name__ == '__main__':
    main()
