#!/usr/bin/env python3
"""Check the exact local r017 acceptance and the observed Unity native controls."""

import argparse
import csv
from hashlib import file_digest
import json
from math import hypot, isclose, isfinite
from pathlib import Path
from xml.etree import ElementTree


BASE = Path('.skill-tree/history/validation/3d-creature-reference/pilot-close-nov18')
CLOSEOUT_SHA256 = '7db8f3c68b9f41b4d8fee7995b6ebc4ee422b3641986b4968f6f57ce40f57915'
CLIPS = {'Idle', 'Walk', 'Trot', 'Turn', 'Gallop'}
SPECIES = {'cat', 'dog'}
PLAYBACK_CASES = {
    'CatalogPetsPlayModeTests.ExactCatalogPrefabsExerciseGenericClipsAndSkinnedLods',
    'CatalogSurfaceTests.InspectCurrentSurfaces',
}
PAW_CASE = 'CatalogPawPlantTests.SampleCatalogPlants'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def digest(path):
    with path.open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def pinned(root, item):
    relative = Path(item['path'])
    require(not relative.is_absolute() and '..' not in relative.parts, f'Invalid artifact path {relative}')
    path = root / relative
    require(path.resolve() == path, f'Invalid artifact path {relative}')
    require(digest(path) == item['sha256'], f'Changed artifact {item["path"]}')
    return path


def check_native_cases(path, expected):
    root = ElementTree.parse(path).getroot()
    require(root.tag == 'test-run' and root.get('result') == 'Passed', f'Native test failure in {path.name}')
    count = str(len(expected))
    required = {'total': count, 'passed': count, 'failed': '0', 'skipped': '0'}
    require(all(root.get(key) == value for key, value in required.items()), f'Unexpected coverage in {path.name}')

    cases = root.findall('.//test-case')
    require(len(cases) == len(expected) and {case.get('fullname') for case in cases} == expected
            and all(case.get('result') == 'Passed' for case in cases), f'Unexpected native test names in {path.name}')


def closeout_pins(root):
    report = root / BASE / 'pilot-closeout.json'
    require(digest(report) == CLOSEOUT_SHA256, 'The reviewed pilot closeout receipt changed')
    closeout = read(report)
    return closeout, {item['path']: item for item in closeout['package_files']}


def read_pose_samples(path, specimens):
    expected_fields = 'species,gait,lod,frame,paw,points,x_m,z_m,sole_m'.split(',')
    samples = {}
    with path.open(newline='') as handle:
        reader = csv.DictReader(handle)
        require(reader.fieldnames == expected_fields, 'Unexpected native paw CSV columns')
        for row in reader:
            species, gait = row['species'], row['gait']
            lod, frame, paw, points = (int(row[field]) for field in ('lod', 'frame', 'paw', 'points'))
            frame_count = specimens.get(species, {}).get('sampled_frames', {}).get(gait, 0)
            require(lod in (0, 1) and 0 <= frame < frame_count and 0 <= paw < 4, 'Unexpected native paw sample identity')
            require(points == 65 if lod == 0 else 8 <= points < 65, 'Unexpected number of sampled paw points')
            key = species, gait, lod, frame, paw
            measured = tuple(float(row[field]) for field in ('x_m', 'z_m', 'sole_m'))
            require(key not in samples and all(map(isfinite, measured)), 'Duplicate or non-finite native paw sample')
            samples[key] = measured
    expected_total = sum(sum(row['sampled_frames'].values()) for row in specimens.values()) * 2 * 4
    require(len(samples) == expected_total, 'Incomplete native paw sample coverage')
    return samples


def replay_interval(samples, identity, start, count, frame_count, travel):
    species, gait, lod, paw = identity
    require(0 <= start < frame_count and 3 <= count <= frame_count, 'Invalid archived paw stance interval')
    positions = []
    for frame in range(start, start + count):
        cycles, phase_frame = divmod(frame, frame_count)
        x, z, height = samples[species, gait, lod, phase_frame, paw]
        positions.append((x + cycles * travel[0], z + cycles * travel[1], height))
    x0, z0, _ = positions[0]
    return {
        'slide_mm': 1000 * max(hypot(x - x0, z - z0) for x, z, _ in positions),
        'adjacent_step_mm': 1000 * max(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(positions, positions[1:])),
        'lowest_sole_mm': 1000 * min(point[2] for point in positions),
        'highest_sole_mm': 1000 * max(point[2] for point in positions),
        'absolute_height_mm': 1000 * max(abs(point[2]) for point in positions),
    }


def verify_paw_data(root, pins):
    contact_dir = BASE / 'pets-r017-contact'
    paths = {name: pinned(root, pins[(contact_dir / name).as_posix()]) for name in (
        'paw-coverage.json', 'paw-1-samples.csv', 'placement-reconciliation.json', 'paw-1-native.json')}
    coverage = read(paths['paw-coverage.json'])
    placement = read(paths['placement-reconciliation.json'])
    native = read(paths['paw-1-native.json'])
    specimens = {row['id']: row for row in coverage['specimens']}
    require(set(specimens) == SPECIES and len(coverage['specimens']) == len(SPECIES), 'Incomplete catalog specimen coverage')
    require(native['status'] == 'Passed' and native['test'] == PAW_CASE
            and native['input_sha256'] == coverage['request_sha256'], 'Archive request differs from the observed native run')
    samples = read_pose_samples(paths['paw-1-samples.csv'], specimens)
    require(placement['native_samples'] == len(samples), 'Native sample count differs from the reviewed report')
    paw_index = {paw: i for i, paw in enumerate(('LF', 'RF', 'LH', 'RH'))}
    verified = set()
    required = []
    for row in placement['measurements']:
        species, gait, lod, paw = row['species'], row['gait'], row['lod'], paw_index[row['paw']]
        identity = species, gait, lod, paw
        spec = specimens[species]
        frame_count = spec['sampled_frames'][gait]
        distance = spec['stride_metres'][gait]
        travel = [component * distance for component in coverage['world_travel_xz']]
        require(identity not in verified and row['intervals'], 'Duplicate or empty archived paw case')
        verified.add(identity)
        for span in row['intervals']:
            actual = replay_interval(samples, identity, span['start_frame'], span['sample_count'], frame_count, travel)
            require(all(isclose(value, span[name], rel_tol=0, abs_tol=1e-6) for name, value in actual.items()),
                    f'Native paw samples do not reproduce the archived metrics for {identity}')
        if gait in ('Walk', 'Trot'):
            required.append(row)
    expected = {(species, gait, lod, paw) for species, row in specimens.items()
                for gait in row['sampled_frames'] for lod in (0, 1) for paw in range(4)}
    require(verified == expected and len(required) == placement['required_paw_lod_cases'] == 32
            and placement['status'] == 'passed', 'Incomplete archived r017 paw case coverage')
    require(all(row['original_budget_pass'] and row['gallopreview_budget_pass'] for row in required),
            'A mandatory archived paw case exceeds its budget')
    return placement, {'required_contacts': len(required), 'all_cases': len(verified), 'native_samples': len(samples),
                      'maximum_required_slide_mm': placement['max_required_slide_mm'],
                      'maximum_required_height_mm': placement['max_required_height_mm']}


def verify_package(root):
    closeout, pins = closeout_pins(root)
    for item in pins.values():
        pinned(root, item)
    require(closeout['result'] == 'completed' and len(closeout['checks']) == 7
            and all(check['result'] == 'pass' for check in closeout['checks']), 'Incomplete pilot closeout receipt')
    _, coverage = verify_paw_data(root, pins)
    return {'schema': 1, 'status': 'passed', 'control': 'package', 'evidence_kind': 'retained-native-archive',
            'outcome_id': closeout['outcome_id'], 'coverage': coverage}


def verify_native_archive(root, queue, control):
    acceptance = read(root / BASE / 'pets-r017-owner-acceptance.json')
    require(acceptance == read(queue / BASE.parent / 'catalog-pets-r017-acceptance.json'), 'The local copy differs from the canonical owner acceptance')
    model_entries = {'base.reference-led-' + species + '@r017' for species in SPECIES}
    require(acceptance['status'] == 'accepted' and acceptance['owner_decision']['entries'] == dict.fromkeys(model_entries, 'accepted'), 'Expected the two accepted exact r017 models')
    search = read(pinned(root, acceptance['catalog_search']))
    require({row['ref']: row['action'] for row in search['candidates']} == dict.fromkeys(model_entries, 'use'), 'Catalog lookup must permit exact local reuse')
    pinned(root, acceptance['accepted_catalog'])
    pinned(root, acceptance['review_packet'])
    archived_playmode = pinned(root, acceptance['native_playmode_result']['report'])
    check_native_cases(archived_playmode, PLAYBACK_CASES)
    results = {}
    for model in acceptance['model_candidates']:
        species = model['entry'].removesuffix('@r017').removeprefix('base.reference-led-')
        require(species in SPECIES and species not in results, 'Unexpected catalog model')
        for key in ('blender', 'unity_model', 'prefab', 'preview'):
            pinned(root, model[key])
        technical = read(pinned(root, model['native_receipt']))
        required = technical['status'] == 'pass' and technical['origin'] == 'actual' and technical['entry'] == model['entry']
        require(required, f'Expected the exact native technical receipt for {species}')
        editor = read(pinned(root, technical['unity_import_and_reimport']))
        require(editor['species'] == species and editor['unity'] == '6000.3.27f2', f'Unexpected Unity import context for {species}')
        require(editor['result'] == 'pass' and editor['forcedReimports'] == 2, f'Failed native references for {species}')
        require(editor['modelSha256'] == model['unity_model']['sha256'] and editor['prefabSha256'] == model['prefab']['sha256'], f'Native import revision mismatch for {species}')
        require({row['name'] for row in editor['clips']} == CLIPS and {row['lod'] for row in editor['renderers']} == {0, 1}, f'Missing clip and LOD coverage for {species}')
        require(editor['avatar'] and editor['prefab'] and editor['controller'] and all(row['reference'] for row in editor['clips']), f'Missing reference identity for {species}')
        rows = read(pinned(root, technical['unity_playmode']))
        playback = [item for item in rows['animals'] if item['id'] == species]
        require(rows['verdict'] == 'passed' and len(playback) == 1, f'Missing native playback for {species}')
        clips = playback[0]['clips']
        require({row['state'] for row in clips} == CLIPS and all(row['samples_per_lod'] >= 9 and row['lod0_peak_skinned_motion_m'] > 0 and row['lod1_peak_skinned_motion_m'] > 0 for row in clips), f'Missing native skinned playback for {species}')
        results[species] = {'model_sha256': editor['modelSha256'], 'prefab_sha256': editor['prefabSha256'], 'forced_reimports': editor['forcedReimports'], 'clips': sorted(CLIPS), 'skinned_lods': [0, 1]}
    require(set(results) == SPECIES, 'Missing accepted species')
    native_controls = {'saved_editmode_and_playmode': True}
    if control == 'motion':
        _, pins = closeout_pins(root)
        contact, sample_scope = verify_paw_data(root, pins)
        paths = {key: pinned(root, value) for key, value in contact['inputs'].items()}
        check_native_cases(paths['paw-1.xml'], {PAW_CASE})
        check_native_cases(paths['paw-1-private.xml'], {PAW_CASE})
        process = read(paths['paw-1-process.json'])
        require(process['exit_code'] == 0 and process['lock_absent'] and process['process_group_absent'], 'Native catalog process cleanup is unverified')
        observed = read(paths['paw-1-native.json'])
        require(observed['status'] == 'Passed' and observed['input_sha256'] == digest(paths['paw-request.json']) and observed['test_source_sha256'] == digest(paths['CatalogPawPlantTests.cs']), 'Paw receipt does not bind the observed run')
        require(observed['test'] == PAW_CASE and observed['protected']['runtime_verified'], 'Native paw isolation or test identity differs')
        for row in read(paths['paw-request.json'])['species']:
            species = row['id']
            require(row['unity_model_sha256'] == results[species]['model_sha256'] and row['prefab_sha256'] == results[species]['prefab_sha256'], f'Paw fixture revision changed for {species}')
        required = [row for row in contact['measurements'] if row['gait'] in ('Walk', 'Trot')]
        coverage = {(row['species'], row['gait'], row['lod'], row['paw']) for row in required}
        expected = {(species, gait, lod, paw) for species in SPECIES for gait in ('Walk', 'Trot') for lod in (0, 1) for paw in ('LF', 'RF', 'LH', 'RH')}
        require(contact['status'] == 'passed' and len(required) == len(expected) and coverage == expected, 'Incomplete r017 paw contact coverage')
        for row in required:
            spans = row['intervals']
            require(spans and all(span['sample_count'] >= 3 for span in spans), 'Missing sustained paw contact evidence')
            require(row['max_slide_mm'] == max(span['slide_mm'] for span in spans)
                    and row['max_height_mm'] == max(span['absolute_height_mm'] for span in spans), 'Paw intervals differ from reported maxima')
            require(row['original_budget_pass'] and row['max_slide_mm'] <= 35 and row['max_height_mm'] <= 25, 'r017 paw motion exceeds the pilot criteria')
        require(contact['max_required_slide_mm'] == max(row['max_slide_mm'] for row in required)
                and contact['max_required_height_mm'] == max(row['max_height_mm'] for row in required), 'Paw summary differs from reported cases')
        native_controls.update(sample_scope)
        native_controls['archived_catalog_playmode_contacts'] = True
    return {'schema': 1, 'status': 'passed', 'control': control, 'models': results, 'coverage': native_controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--queue', type=Path)
    parser.add_argument('--control', required=True, choices=['package', 'import', 'motion'])
    parser.add_argument('--local-native-archive', action='store_true',
                        help='Replay the exact archived native controls with the retained Unity files')
    args = parser.parse_args()
    root = args.project.resolve()
    if args.control == 'package' and (args.queue or args.local_native_archive):
        parser.error('Package verification uses the committed evidence only')
    if args.control != 'package' and (not args.queue or not args.local_native_archive):
        parser.error('Native archive replay requires --local-native-archive, --queue and the retained Unity files. Use --control package for a clean checkout.')
    try:
        if args.control == 'package':
            result = verify_package(root)
        else:
            result = verify_native_archive(root, args.queue.resolve(), args.control)
        print(json.dumps(result, sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as error:
        parser.exit(1, f'Catalog pilot evidence: {error}\n')


if __name__ == '__main__':
    main()
