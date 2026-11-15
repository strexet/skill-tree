"""Stage and observe carried-lantern tests in the previously verified Unity copy."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
from xml.etree import ElementTree


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ASSET_ROOT = 'Assets/DirectorLanternFixture'
BASELINE_HISTORY = '.skill-tree/history/validation/director/unity-baseline.json'
TASK_ID = 'T-2d4cdd62-11bd-49b7-906f-343a0df202f3'
AREA = ('Assets', 'Packages', 'ProjectSettings')
NAMESPACE = 'SkillTreeSandbox.Director.'
TESTS = {
    'EditMode': ('DirectorLanternImport', 'DirectorLanternEditTests', (
        'RepeatedImportPreservesGuidMeshAndMetricSockets', 'WrongTargetAndWallMountedControlRejectAttachment')),
    'PlayMode': ('DirectorLanternCarry', 'DirectorLanternPlayTests', (
        'HandPickupAndCarryThroughCave', 'BeltPickupAndCarryThroughCave')),
}


def owned(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require(condition, detail):
    if not condition:
        raise RuntimeError(detail)


def path_sha(path):
    return sha256(str(path).encode()).hexdigest()


def selected_sources(base, art, expected_sha, fixture):
    art = base.exact_path(art)
    result = base.json_file(art)
    require(base.digest(art) == expected_sha and result['kind'] == 'director-lantern-art-result'
            and result['task_id'] == TASK_ID and result['fixture_id'] == fixture['fixture_id']
            and result['process']['exit_code'] == 0 and result['process']['process_group_cleared'] is True,
            'Select the exact observed Blender result for the lantern task')
    refs = result['artifact']
    artifact = {'path': refs['path'], 'sha256': refs['sha256']}
    model = fixture['model']
    require(artifact['path'] == model['asset'] == 'DirectorLantern.fbx', 'The admitted FBX asset name changed')
    paths = {
        path.relative_to(HERE / 'lantern-unity').as_posix(): path
        for path in (HERE / 'lantern-unity').glob('*/*')
        if path.suffix in {'.asmdef', '.cs'}
    }
    paths['runtime/DirectorLanternPickup.cs'] = paths.pop('runtime/director-lantern-pickup.cs')
    require(len(paths) == 6, 'The reviewed Unity fixture requires exactly three sources and three assemblies')
    fbx = base.exact_path(art.parent / artifact['path'])
    require(base.digest(fbx) == artifact['sha256'] and fbx.stat().st_size == refs['bytes'],
            'The Blender result does not match the selected FBX bytes')
    paths['Resources/' + fbx.name] = fbx
    for attachment in ('hand', 'belt'):
        pin = fixture['wrappers'][attachment]
        record = result['wrappers'][attachment]
        require(record['path'] == pin['path'] == 'lantern-' + attachment + '.json', 'Wrong carry revision wrapper path')
        wrapper = base.exact_path(art.parent / record['path'])
        story = fixture['story'][attachment]
        expected = {'schema': 1, 'revision': pin['revision'], 'attachment': attachment,
                    'socket': pin['socket'], 'artifact': artifact,
                    'story': {'id': fixture['story']['id'], 'revision': story['revision'], 'sha256': story['sha256']},
                    'scale_meters': model['scale_meters'], 'grip_socket': model['sockets']['GripSocket'],
                    'belt_socket': model['sockets']['BeltSocket']}
        require(base.digest(wrapper) == record['sha256'] and base.json_file(wrapper) == expected,
                'Carry wrapper does not match the exact model, attachment and requirement revision')
        paths['Resources/' + wrapper.name] = wrapper
    return paths, result


def split_inventory(base, verifier, project, baseline_snapshot):
    inventory = base.inventory(project, AREA)
    additions = {rel: value for rel, value in inventory.items()
                 if rel.startswith(ASSET_ROOT + '/') or rel == ASSET_ROOT + '.meta'}
    background = {rel: value for rel, value in inventory.items() if rel not in additions}
    require(verifier.snapshot_digest(background) == baseline_snapshot,
            'The original Unity copy inputs differ outside the reviewed lantern folder')
    return additions


def validate_assets(assets, expected):
    input_paths = {ASSET_ROOT + '/' + rel: value for rel, value in expected.items()}
    metadata = {ASSET_ROOT + '.meta'}
    for relative in input_paths:
        asset = Path(relative)
        metadata.add(relative + '.meta')
        metadata.add(asset.parent.as_posix() + '.meta')
    require(assets.keys() <= input_paths.keys() | metadata
            and all(assets.get(rel) == value for rel, value in input_paths.items()),
            'The staged lantern source, model, wrapper or generated metadata scope changed')


def original_outputs(base, locator, original):
    settings = (original / base.SETTINGS).read_text(encoding='utf-8')
    def field(name):
        found = re.findall(r'^  ' + name + r': ([A-Za-z0-9_-]+)$', settings, re.M)
        require(len(found) == 1, 'The original save identity changed')
        return found[0]
    results = Path(locator['application_support']) / field('companyName') / field('productName') / 'TestResults.xml'
    return {'profile': base.digest(original / base.PROFILE), 'original_utf': base.file_observation(results)}


def profile(base, project, expected):
    prior = base.digest(project / base.PROFILE)
    require(prior == expected, 'The child profile does not match the admitted profile digest')
    base.command('node', project / base.MANAGER, '--verify', timeout=45)
    value = base.json_file(project / base.PROFILE)
    require(value['project_root'] == str(project) and value['flavor'] == 'unity'
            and base.digest(project / base.PROFILE) == prior, 'The verified Unity installation identifies another project')
    return value


def ensure_editor_stopped(base, project, *, inspect_owned_lock=False):
    lock = project / 'Temp/UnityLockfile'
    require(inspect_owned_lock or not (lock.exists() or lock.is_symlink()),
            'The exact disposable project already has a Unity lock')
    deadline = time.monotonic() + (8 if inspect_owned_lock else 0)
    while True:
        editing = []
        listing = base.command('ps', '-ax', '-o', 'pid=,stat=,comm=', timeout=10)
        for row in listing.splitlines():
            fields = row.strip().split(maxsplit=2)
            if len(fields) != 3 or fields[1].startswith('Z') or Path(fields[2]).name != 'Unity':
                continue
            arguments = subprocess.run(['ps', '-p', fields[0], '-o', 'args='], capture_output=True, text=True, timeout=10)
            require(arguments.returncode in {0, 1}, 'The exact Unity process inventory is unavailable')
            launch = arguments.stdout.partition(' -projectPath ')[2].split(' -', 1)[0].strip().strip('"')
            if launch == str(project):
                editing.append(fields[0])
        if not editing:
            return
        require(time.monotonic() < deadline,
                'Unity Editor still targets this disposable project: ' + ', '.join(editing))
        time.sleep(0.25)


def retain_stale_pipeline_lock(base, project, reports, observation):
    """Retain only an unopened sentinel created by the stopped owned probe."""
    lock = project / 'Temp/UnityLockfile'
    if not lock.exists() and not lock.is_symlink():
        return
    ensure_editor_stopped(base, project, inspect_owned_lock=True)
    require(not base.group_exists(observation['pid']) and lock.resolve(strict=True) == lock,
            'The observed Pipeline process group or lock path is unresolved')
    inspected = lock.lstat()
    started = datetime.fromisoformat(observation['started_at']).timestamp()
    stopped = datetime.fromisoformat(observation['stopped_at']).timestamp()
    require(stat.S_ISREG(inspected.st_mode) and inspected.st_size == 0 and started <= inspected.st_mtime <= stopped,
            'The Unity lock does not belong to the exact stopped Pipeline attempt')
    listing = subprocess.run(['lsof', '-F', 'pc', str(lock)], capture_output=True, timeout=15)
    require(listing.returncode == 1 and not listing.stdout and not listing.stderr,
            'The exact Unity lock still has a process owner')
    retained = reports / 'stale-pipeline-unity-lock'
    require(not retained.exists() and not retained.is_symlink() and lock.lstat() == inspected,
            'The owned stale lock changed during verification')
    lock.rename(retained)


@contextmanager
def resource(project):
    lock = project.parent / '.director-lantern-lock'
    lock.mkdir()
    try:
        yield
    finally:
        lock.rmdir()


def stage(project, files):
    destination = project / ASSET_ROOT
    require(not destination.exists() and not destination.is_symlink(), 'The lantern fixture is already staged')
    with tempfile.TemporaryDirectory(prefix='.director-lantern-stage-', dir=project.parent) as scratch:
        stage_root = Path(scratch) / 'new-fixture'
        for relative, source in files.items():
            target = stage_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        stage_root.rename(destination)


def observe_batch(base, project, reports, recipe, mode, tools, pins, pipeline, groups, timeout):
    fixture, assembly, methods = TESTS[mode]
    test_filter = NAMESPACE + fixture
    mode_path = reports / mode.lower()
    mode_path.mkdir()
    xml, log = mode_path / 'report.xml', mode_path / 'editor.log'
    expected = ['Unity', '-batchmode', '-projectPath', '{project_root}', '-runTests', '-testPlatform', mode,
                '-testFilter', '{test_filter}', '-testResults', '{result_path}', '-logFile', '{log_path}']
    require(recipe['argv'] == expected and recipe['lane'] == 'unity-' + mode.lower()
            and recipe['editor_version'] == pins['editor'] and recipe['utf_version'] == pins['test_framework'],
            'The selected test lane does not match the exact owned Unity recipe')
    args = [item.format(project_root=project, test_filter=test_filter, result_path=xml, log_path=log)
            for item in recipe['argv'][1:]]
    started = base.now()
    with base.owned_editor([tools['editor'], *args], mode_path / 'launch.txt', groups) as process:
        pid = process.pid
        exit_code = process.wait(timeout=timeout)
    ended = base.now()
    require(exit_code == 0 and xml.is_file() and log.is_file(), 'The owned Unity test process did not return its exact results')
    xml_bytes = xml.read_bytes()
    require(0 < len(xml_bytes) < 1024 * 1024 and b'<!DOCTYPE' not in xml_bytes and b'<!ENTITY' not in xml_bytes,
            'Invalid Unity NUnit report')
    report = ElementTree.fromstring(xml_bytes)
    counters = {'total': '2', 'passed': '2', 'failed': '0', 'skipped': '0', 'inconclusive': '0'}
    cases = report.findall('.//test-case')
    expected_cases = sorted(test_filter + '.' + method for method in methods)
    require(report.tag == 'test-run' and report.get('result') == 'Passed'
            and all(report.get(key) == value for key, value in counters.items()) and len(cases) == 2
            and sorted(case.get('fullname') for case in cases) == expected_cases
            and all(case.get('result') == 'Passed' for case in cases), 'The focused Unity report is incomplete or failed')
    assemblies = report.findall(".//test-suite[@type='Assembly']")
    require(len(assemblies) == 1 and assemblies[0].get('fullname') == str(project / 'Library/ScriptAssemblies' / (assembly + '.dll')),
            'The observed test assembly belongs to another project')
    attributes = {element.get('name'): element.get('value') for element in assemblies[0].findall('./properties/property')}
    log_text = log.read_text(encoding='utf-8', errors='replace')
    require(attributes.get('_PID') == str(pid) and attributes.get('platform') == mode
            and f"{pins['editor']} ({pins['editor_revision']})" in log_text
            and pipeline['default_results_path'] in (log_text + xml_bytes.decode('utf-8')),
            'The exact Unity process, revision, lane or isolated saves were not attested')
    return {'lane': recipe['lane'], 'recipe_id': recipe['lane'], 'pid': pid, 'exit_code': exit_code,
            'started_at': started, 'finished_at': ended, 'test_filter': test_filter, 'cases': expected_cases,
            'report': {'path': xml.relative_to(reports).as_posix(), 'sha256': base.digest(xml)},
            'log': {'path': log.relative_to(reports).as_posix(), 'sha256': base.digest(log)}}


def run(args):
    base = owned('run-unity-baseline')
    verifier = owned('verify-unity-baseline')
    fixture_path = HERE / 'lantern-fixture.json'
    fixture = base.json_file(fixture_path)
    baseline = base.json_file(ROOT / BASELINE_HISTORY)
    locator = base.json_file(base.exact_path(args.locator))
    original = base.exact_path(locator['original_project'], directory=True)
    project = base.exact_path(args.project, directory=True)
    scope = baseline['scope']
    require(path_sha(project) == scope['project_path_sha256'] and path_sha(original) == scope['original_path_sha256']
            and not project.is_relative_to(original) and project.name == 'project',
            'Use only the previously qualified disposable Unity project and original')
    require(verifier.snapshot_digest(base.inventory(original, AREA)) == scope['original_before']
            and fixture['tool_pins'] == baseline['tools'],
            'The original Unity fixture or reviewed tool pins changed')
    isolation = verifier.artifact(project.parent, baseline['isolation'], verifier.REPORT_LIMIT)
    isolation = json.loads(isolation)
    require(isolation['project_path'] == str(project) and isolation['original_project_path'] == str(original),
            'Baseline save isolation identifies another project')
    child_state = base.json_file(project / '.skill-tree/documents/future.json')
    require(child_state['run_registry']['queue_id'] == baseline['profile']['queue_id']
            and base.command('git', 'rev-parse', 'HEAD', cwd=project).strip() == baseline['profile']['base_commit'],
            'The isolated child queue or private Git base changed')
    expected_sources, art = selected_sources(base, args.art_result, args.expected_art_sha256, fixture)
    expected_assets = {rel: base.digest(path) for rel, path in expected_sources.items()}
    untouched = original_outputs(base, locator, original)

    with resource(project):
        ensure_editor_stopped(base, project)
        profile_value = profile(base, project, args.expected_profile_sha256)
        prior_assets = split_inventory(base, verifier, project, scope['runtime_before'])
        if args.operation == 'stage':
            require(args.expected_profile_sha256 == baseline['profile']['receipt_sha256'] and not prior_assets,
                    'Stage requires the unchanged qualified baseline and a fresh fixture destination')
            stage(project, expected_sources)
            validate_assets(split_inventory(base, verifier, project, scope['runtime_before']), expected_assets)
            return
        validate_assets(prior_assets, expected_assets)
        reports = args.reports
        require(reports is not None and reports.is_absolute() and reports.resolve() == reports
                and reports.parent == project.parent and not reports.exists(),
                'Observe requires fresh evidence output beside the exact disposable project')
        reports.mkdir()
        tools = {name: base.exact_path(locator[name]) for name in ('editor', 'unity_cli')}
        pins = fixture['tool_pins']
        require(pins['unity_cli'] in base.command(tools['unity_cli'], '--version'), 'The exact Unity CLI version changed')
        groups = set()
        pipeline = base.probe_pipeline(tools, project, reports, groups, args.pipeline_seconds, pins['editor'])
        require(pipeline['persistent_path'] == isolation['observed_persistent_data_path']
                and pipeline['default_results_path'] == isolation['observed_default_result_path'] and not groups,
                'The live Editor did not report the previously verified private save namespace')
        retain_stale_pipeline_lock(base, project, reports, pipeline)
        validate_assets(split_inventory(base, verifier, project, scope['runtime_before']), expected_assets)
        profile(base, project, args.expected_profile_sha256)
        batches = {}
        for mode in TESTS:
            ensure_editor_stopped(base, project)
            recipe = profile_value['recipes']['unity-' + mode.lower()]
            batches[mode] = observe_batch(base, project, reports, recipe, mode, tools, pins, pipeline, groups, args.batch_seconds)
        ensure_editor_stopped(base, project)
        after_assets = split_inventory(base, verifier, project, scope['runtime_before'])
        validate_assets(after_assets, expected_assets)
        profile(base, project, args.expected_profile_sha256)
        require(not groups and original_outputs(base, locator, original) == untouched
                and verifier.snapshot_digest(base.inventory(original, AREA)) == scope['original_before'],
                'Unity cleanup or original isolation changed')
        observation = reports / 'lantern-unity-observed.json'
        artist_result = reports / 'lantern-art-result.json'
        shutil.copyfile(args.art_result, artist_result)
        require(base.digest(artist_result) == args.expected_art_sha256, 'The observed Blender result changed')
        base.write_json(observation, {
            'schema': 1, 'kind': 'director-lantern-unity-observed', 'task_id': TASK_ID,
            'fixture_id': fixture['fixture_id'], 'fixture_sha256': base.digest(fixture_path),
            'launcher_sha256': base.digest(Path(__file__)),
            'art_result_sha256': args.expected_art_sha256, 'artifact': art['artifact'], 'wrappers': art['wrappers'],
            'source_run_id': art['source_run_id'], 'project_path': str(project),
            'unity_profile': {'identity': profile_value['identity'], 'sha256': args.expected_profile_sha256,
                              'flavor': profile_value['flavor'], 'queue_id': child_state['run_registry']['queue_id']},
            'pipeline': pipeline, 'batches': batches, 'assets_before': prior_assets, 'assets_after': after_assets,
            'tools': pins, 'original_preserved': True, 'cleanup_complete': True,
        })
        for mode, batch in batches.items():
            receipt = {
                'schema': 1, 'kind': 'director-lantern-unity-receipt', 'origin': 'observed-unity-editor',
                'task_id': TASK_ID, 'fixture_id': fixture['fixture_id'], 'fixture_sha256': base.digest(fixture_path),
                'launcher_sha256': base.digest(Path(__file__)),
                'source_run_id': art['source_run_id'], 'mode': mode, 'batch': batch,
                'project_path_sha256': path_sha(project), 'baseline_sha256': base.digest(ROOT / BASELINE_HISTORY),
                'asset_sources': expected_assets, 'artifact': art['artifact'], 'wrappers': art['wrappers'],
                'profile': {'identity': profile_value['identity'], 'sha256': args.expected_profile_sha256,
                            'queue_id': child_state['run_registry']['queue_id']},
                'evidence': {name: {'path': path.name, 'sha256': base.digest(path)} for name, path in {
                    'observation': observation, 'art': artist_result, 'pipeline_status': reports / 'pipeline-state.json',
                    'save_probe': reports / 'persistent-path.json',
                }.items()},
            }
            base.write_json(reports / ('lantern-' + mode.lower() + '.json'), receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('stage', 'observe'))
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--locator', required=True, type=Path)
    parser.add_argument('--art-result', required=True, type=Path)
    parser.add_argument('--expected-art-sha256', required=True)
    parser.add_argument('--expected-profile-sha256', required=True)
    parser.add_argument('--reports', type=Path)
    parser.add_argument('--pipeline-seconds', type=int, default=110)
    parser.add_argument('--batch-seconds', type=int, default=120)
    args = parser.parse_args()
    run(args)


if __name__ == '__main__':
    main()
