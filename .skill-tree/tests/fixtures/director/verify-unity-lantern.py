"""Verify compact Lantern receipts against current pins and observed Unity bytes."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
from xml.etree import ElementTree


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARTIFACT_PREFIX = 'Assets/DirectorLanternFixture/'


def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load('run-unity-lantern')
STRICT = load('verify-unity-baseline')


def require(check, detail):
    if not check:
        raise ValueError(detail)


def receipt_inputs(root, mode):
    history = root / '.skill-tree/history/validation/director'
    fixtures = root / '.skill-tree/tests/fixtures/director'
    return (json.loads((history / ('lantern-' + mode.lower() + '.json')).read_bytes()),
            (fixtures / 'lantern-fixture.json').read_bytes(), (history / 'unity-baseline.json').read_bytes(), fixtures)


def require_mode(current, mode):
    test, assembly, methods = RUNNER.TESTS[mode]
    name = RUNNER.NAMESPACE + test
    require(current.get('mode') == mode and current['batch'].get('test_filter') == name
            and current['batch'].get('recipe_id') == current['batch'].get('lane') == 'unity-' + mode.lower()
            and current['batch'].get('cases') == sorted(name + '.' + method for method in methods),
            'The receipt does not bind the exact focused Unity lane and cases')
    return assembly


def verify_compact(receipt, mode, fixture_bytes, baseline_bytes, fixtures):
    fixture, baseline = json.loads(fixture_bytes), json.loads(baseline_bytes)
    require(receipt.get('schema') == 1 and receipt.get('kind') == 'director-lantern-unity-receipt'
            and receipt.get('origin') == 'observed-unity-editor' and receipt['task_id'] == RUNNER.TASK_ID,
            'Native lantern acceptance requires an observed Unity receipt')
    require(receipt['fixture_sha256'] == STRICT.digest(fixture_bytes) and receipt['fixture_id'] == fixture['fixture_id']
            and receipt['baseline_sha256'] == STRICT.digest(baseline_bytes)
            and receipt['launcher_sha256'] == STRICT.digest((fixtures / 'run-unity-lantern.py').read_bytes())
            and receipt['project_path_sha256'] == baseline['scope']['project_path_sha256'],
            'The lantern fixture, launcher, Unity baseline or disposable project receipt changed')
    require(receipt['profile']['queue_id'] == baseline['profile']['queue_id']
            and STRICT.pin(receipt['profile']['identity']) and STRICT.pin(receipt['profile']['sha256'])
            and re.fullmatch(r'WR-[a-f0-9-]{36}', receipt['source_run_id']),
            'The receipt does not identify the authorized source run and verified child profile')
    require_mode(receipt, mode)
    expected = {path.relative_to(fixtures / 'lantern-unity').as_posix(): STRICT.digest(path.read_bytes())
                for path in (fixtures / 'lantern-unity').glob('*/*') if path.suffix in {'.asmdef', '.cs'}}
    expected['runtime/DirectorLanternPickup.cs'] = expected.pop('runtime/director-lantern-pickup.cs')
    artifact = receipt['artifact']
    require(artifact['path'] == fixture['model']['asset'] and STRICT.pin(artifact['sha256']) and artifact['bytes'] > 0
            and set(receipt['wrappers']) == {'hand', 'belt'}, 'The receipt does not identify the observed FBX and carry variants')
    expected['Resources/' + artifact['path']] = artifact['sha256']
    for attachment in ('hand', 'belt'):
        wrapper = receipt['wrappers'][attachment]
        story = fixture['story'][attachment]
        source = fixtures.parents[3] / story['path']
        require(STRICT.digest(source.read_bytes()) == story['sha256']
                and wrapper['path'] == fixture['wrappers'][attachment]['path'] and STRICT.pin(wrapper['sha256']),
                'The approved requirement source or wrapper digest changed')
        expected['Resources/' + wrapper['path']] = wrapper['sha256']
    require(len(expected) == 9 and receipt['asset_sources'] == expected, 'The current Unity fixture or input digests changed')
    require(receipt['batch']['exit_code'] == 0 and type(receipt['batch']['pid']) is int and receipt['batch']['pid'] > 0,
            'The exact Unity process did not complete successfully')
    for reference in [receipt['batch']['report'], receipt['batch']['log'], *receipt['evidence'].values()]:
        require(STRICT.pin(reference.get('sha256')) and isinstance(reference.get('path'), str),
                'The compact receipt lacks the expected exact evidence digests')
    require(set(receipt['evidence']) == {'observation', 'art', 'pipeline_status', 'save_probe'},
            'An exact PlayMode or EditMode receipt needs the observed tool and session references')
    return fixture


def verify_report(xml, batch, mode, assembly, project):
    require(b'<!DOCTYPE' not in xml and b'<!ENTITY' not in xml, 'Unexpected XML declaration')
    report = ElementTree.fromstring(xml)
    cases = report.findall('.//test-case')
    required_counts = {'total': '2', 'passed': '2', 'failed': '0', 'skipped': '0', 'inconclusive': '0'}
    require(report.tag == 'test-run' and report.get('result') == 'Passed'
            and all(report.get(key) == value for key, value in required_counts.items()) and len(cases) == 2
            and sorted(case.get('fullname') for case in cases) == batch['cases']
            and all(case.get('result') == 'Passed' for case in cases), 'The native tests did not record two exact passes')
    assemblies = report.findall(".//test-suite[@type='Assembly']")
    require(len(assemblies) == 1
            and assemblies[0].get('fullname') == project + '/Library/ScriptAssemblies/' + assembly + '.dll',
            'The NUnit assembly belongs to another Unity project')
    properties = {item.get('name'): item.get('value') for item in assemblies[0].findall('./properties/property')}
    require(properties.get('_PID') == str(batch['pid']) and properties.get('platform') == mode,
            'The NUnit reporting PID or Unity lane differs from the exact process')
    started, finished = STRICT.utc(batch['started_at']), STRICT.utc(batch['finished_at'])
    require(started.replace(microsecond=0) <= STRICT.utc(report.attrib['start-time'])
            <= STRICT.utc(report.attrib['end-time']) <= finished, 'The NUnit results fall outside the named Editor session')


def verify_native(receipt, mode, fixture, raw_root):
    assembly = require_mode(receipt, mode)
    refs = receipt['evidence']
    evidence = {name: json.loads(STRICT.artifact(raw_root, ref, STRICT.REPORT_LIMIT)) for name, ref in refs.items()}
    observation, art = evidence['observation'], evidence['art']
    profile = receipt['profile']
    require(observation['schema'] == 1 and observation['kind'] == 'director-lantern-unity-observed'
            and observation['task_id'] == receipt['task_id'] and observation['source_run_id'] == receipt['source_run_id']
            and observation['fixture_id'] == receipt['fixture_id'] and observation['fixture_sha256'] == receipt['fixture_sha256']
            and observation['launcher_sha256'] == receipt['launcher_sha256']
            and observation['batches'][mode] == receipt['batch']
            and observation['unity_profile'] == {**profile, 'flavor': 'unity'}
            and observation['tools'] == fixture['tool_pins'] and observation['original_preserved'] is True
            and observation['cleanup_complete'] is True,
            'The observed child, clean closure, original preservation or profile changed')
    require(art['kind'] == 'director-lantern-art-result' and art['source_run_id'] == receipt['source_run_id']
            and art['task_id'] == receipt['task_id'] and art['fixture_id'] == receipt['fixture_id']
            and art['process']['exit_code'] == 0 and art['process']['process_group_cleared'] is True
            and refs['art']['sha256'] == observation['art_result_sha256']
            and art['artifact'] == observation['artifact'] == receipt['artifact']
            and art['wrappers'] == observation['wrappers'] == receipt['wrappers'],
            'The Unity observation lacks the same accepted Blender bytes and carry wrappers')
    for inventory in (observation['assets_before'], observation['assets_after']):
        require(all(inventory.get(ARTIFACT_PREFIX + relative) == fingerprint
                    for relative, fingerprint in receipt['asset_sources'].items()),
                'Native Unity did not receive the exact model, carry revisions and test sources')
    project, pipeline, batch = observation['project_path'], observation['pipeline'], receipt['batch']
    require(STRICT.path_identity(project) == receipt['project_path_sha256']
            and pipeline['pid'] != batch['pid'] and STRICT.utc(pipeline['stopped_at']) <= STRICT.utc(batch['started_at']),
            'The test did not follow the original isolated Pipeline session')
    live = {**pipeline, 'requested_pid': pipeline['pid'], 'observed_pid': pipeline['pid']}
    STRICT.verify_pipeline(evidence['pipeline_status'], live, fixture['tool_pins'], project)
    probe = evidence['save_probe']
    target = probe['data']['target']
    proof = probe['data']['result']
    if 'result' in proof:
        proof = proof['result']
    if isinstance(proof, str):
        proof = json.loads(proof)
    private = Path(pipeline['persistent_path'])
    require(probe['success'] is True and not probe['errors'] and probe['data']['command'] in {'script eval', 'script run'}
            and target['projectPath'] == project and target['host'] in {'127.0.0.1', '::1'}
            and proof['pid'] == pipeline['pid'] and proof['projectPath'] == project
            and proof['persistentDataPath'] == str(private) and private.is_absolute()
            and '..' not in private.parts and private.is_relative_to(Path(project).parent)
            and not private.is_relative_to(project) and pipeline['default_results_path'] == str(private / 'TestResults.xml'),
            'The observed Unity save namespace identifies a different project or process')
    xml = STRICT.artifact(raw_root, batch['report'], STRICT.REPORT_LIMIT)
    log = STRICT.artifact(raw_root, batch['log'], STRICT.LOG_LIMIT).decode('utf-8', errors='replace')
    verify_report(xml, batch, mode, assembly, project)
    combined = log + xml.decode('utf-8')
    pins = fixture['tool_pins']
    require(f"{pins['editor']} ({pins['editor_revision']})" in log
            and pipeline['default_results_path'] in combined, 'The named Unity build or private UTF output was not attested')
    if mode == 'EditMode':
        require(re.search(r'DirectorLanternImport observed guid=[a-f0-9]{32} stable_meshes=[1-9][0-9]*', combined)
                and 'DirectorLanternImport observed wrong_target=rejected wall_attachment=rejected' in combined,
                'Native EditMode lacks the actual repeat import and failed attachment controls')
    else:
        for attachment in ('hand', 'belt'):
            wrapper = fixture['wrappers'][attachment]
            require(f"DirectorLanternCarry observed attachment={attachment} revision={wrapper['revision']} "
                    f"socket={wrapper['socket']} route=entry,threshold,turn,exit" in combined,
                    'Native PlayMode lacks the exact changed attachment and cave-route observation')
    return {'passed': 2, 'failed': 0, 'skipped': 0}
