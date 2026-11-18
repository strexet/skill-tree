#!/usr/bin/env python3
"""Check the exact local r017 acceptance and the observed Unity native controls."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path
from xml.etree import ElementTree


BASE = Path('.skill-tree/history/validation/3d-creature-reference/pilot-close-nov18')
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


def verify(root, queue, control):
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
        contact = read(root / BASE / 'pets-r017-contact/placement-reconciliation.json')
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
        native_controls.update({'new_catalog_playmode_contacts': True, 'required_contacts': len(required), 'native_samples': contact['native_samples'], 'maximum_required_slide_mm': contact['max_required_slide_mm'], 'maximum_required_height_mm': contact['max_required_height_mm']})
    return {'schema': 1, 'status': 'passed', 'control': control, 'models': results, 'coverage': native_controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--queue', required=True, type=Path)
    parser.add_argument('--control', required=True, choices=['import', 'motion'])
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.project.resolve(), args.queue.resolve(), args.control), sort_keys=True, indent=2))
    except (OSError, ValueError, KeyError, ElementTree.ParseError) as error:
        parser.exit(1, f'Catalog pilot evidence: {error}\n')


if __name__ == '__main__':
    main()
