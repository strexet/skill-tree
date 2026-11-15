"""Verify exact stock EditMode evidence from an observed disposable Unity run."""

import argparse
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from xml.etree import ElementTree


REPORT_LIMIT = 1024 * 1024
LOG_LIMIT = 32 * 1024 * 1024
DIGEST = re.compile(r'[0-9a-f]{64}')
OBJECT_ID = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})')
QUEUE_ID = re.compile(r'Q-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
SENTIS_STANDALONE = re.compile(
    rb'(^  scriptingDefineSymbols:\n    Standalone: )SENTIS_ANALYTICS_ENABLED;(APP_UI_EDITOR_ONLY\n)', re.MULTILINE
)


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def utc(value):
    instant = datetime.fromisoformat(value)
    require(instant.utcoffset() == timedelta(0), 'Evidence timestamps require UTC')
    return instant


def pin(value):
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def path_identity(value):
    path = PurePosixPath(value)
    require(path.root == '/' and '..' not in path.parts and str(path) == value, 'Evidence requires an exact canonical path')
    return digest(value.encode())


def snapshot(root, roots):
    """Hash repo-relative file names and exact bytes, including Unity metadata."""
    return snapshot_digest(inventory(root, roots))


def inventory(root, roots):
    entries = {}

    def visit(path):
        require(not path.is_symlink(), 'Fixture source contains a symlink')
        if path.is_dir():
            for child in path.iterdir():
                if child.name != '.DS_Store':
                    visit(child)
        else:
            require(path.is_file(), 'Fixture source path is missing or unsupported')
            entries[path.relative_to(root).as_posix()] = digest(path.read_bytes())

    for relative in roots:
        require(relative in ('Assets', 'Packages', 'ProjectSettings'), 'Unexpected fixture source root')
        visit(root / relative)
    return entries


def snapshot_digest(entries):
    require(entries and all(pin(value) for value in entries.values()), 'Fixture inventory requires file digests')
    content = ''.join(f'{name}\0{sha}\n' for name, sha in sorted(entries.items())).encode()
    return {'sha256': digest(content), 'files': len(entries)}


def artifact(root, reference, limit):
    name = reference['path']
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and '..' not in rel.parts and str(rel) == name and name != '.', 'Unsafe evidence path')
    path = root
    for step in rel.parts:
        path /= step
        require(not path.is_symlink(), 'Evidence path traverses a symlink')
    require(path.is_file() and 0 < path.stat().st_size <= limit, 'Missing or oversized artifact')
    data = path.read_bytes()
    require(digest(data) == reference['sha256'], 'Artifact bytes differ from recorded digest')
    return data


def verify_report(report, test_filter, batch, project_path):
    require(b'<!DOCTYPE' not in report and b'<!ENTITY' not in report, 'Unexpected XML declaration')
    root = ElementTree.fromstring(report)
    counters = {'total': '1', 'testcasecount': '1', 'passed': '1', 'failed': '0', 'inconclusive': '0', 'skipped': '0'}
    require(root.tag == 'test-run' and root.get('result') == 'Passed'
            and all(root.get(key) == value for key, value in counters.items()), 'Stock test requires one pass and zero failures or skips')
    cases = root.findall('.//test-case')
    require(len(cases) == 1 and cases[0].get('fullname') == test_filter
            and cases[0].get('result') == 'Passed', 'NUnit case differs from selected stock filter or verdict')
    assembly = root.find(".//test-suite[@type='Assembly']")
    require(assembly is not None and assembly.get('fullname') == project_path + '/Library/ScriptAssemblies/SkillTreeSandbox.EditModeTests.dll',
            'NUnit assembly path identifies another project')
    mode = assembly.find("./properties/property[@name='platform']")
    reporter = assembly.find("./properties/property[@name='_PID']")
    require(mode is not None and mode.get('value') == 'EditMode' and reporter is not None
            and reporter.get('value') == str(batch['pid']), 'NUnit platform or reporting process differs')
    raw_start, raw_end = utc(root.attrib['start-time']), utc(root.attrib['end-time'])
    require(utc(batch['started_at']).replace(microsecond=0) <= raw_start <= raw_end <= utc(batch['finished_at']),
            'NUnit report predates the current process or finishes outside the attempt')
    return {'discovered': 1, 'passed': 1, 'failed': 0, 'skipped': 0}


def verify_pipeline(raw, live, tools, project_path):
    data = raw['data']
    require(raw['success'] is True and data['command'] == 'editor status' and not raw['errors'], 'Pipeline status was not successful')
    result, target = data['result'], data['target']
    require(target['host'] in ('127.0.0.1', '::1') and target['projectPath'] == project_path
            and result['projectPath'] == project_path and result['unityVersion'] == tools['editor']
            and result['status'] == 'ready' and result['playMode'] == 'stopped' and result['compiling'] is False,
            'Pipeline status is not ready in the exact isolated project')
    require(live['requested_pid'] == live['observed_pid'] and live['observed_pid'] > 0,
            'Pipeline PID lacks matching process ownership')
    heartbeat = utc(result['lastHeartbeat'])
    observed = utc(live['observed_at'])
    require(utc(live['started_at']) <= heartbeat <= observed <= utc(live['stopped_at'])
            and observed - heartbeat <= timedelta(seconds=30), 'Pipeline observation is stale or outside the owned session')


def verify_live_save_probe(raw, process, live, project_path, isolation):
    data = raw['data']
    require(raw['success'] is True and data['command'] in ('script run', 'script eval') and not raw['errors']
            and data['target']['host'] in ('127.0.0.1', '::1') and data['target']['projectPath'] == project_path,
            'Live save probe did not target the disposable project')
    observed = data['result'].get('result', data['result'])
    require(observed == {'projectPath': project_path, 'pid': live['observed_pid'],
                         'persistentDataPath': isolation['observed_persistent_data_path'],
                         'defaultTestResultsPath': isolation['observed_default_result_path']},
            'Live save probe identifies a different project, process or persistent path')
    pid, command = process.strip().split(maxsplit=1)
    require(pid == str(live['observed_pid']) and 'Unity' in command and '-projectPath ' + project_path in command,
            'Observed OS process does not match the PID and project targeted by Pipeline')


def verify_startup_normalization(runtime, record, pins, inventory, evidence_root):
    require(set(record) == {'after', 'vendor_source', 'package_lock'}, 'Startup normalization requires exact evidence references')
    vendor = artifact(evidence_root, record['vendor_source'], REPORT_LIMIT)
    require(digest(vendor) == pins['vendor_source_sha256'], 'Sentis normalization requires the approved vendor source')
    lock = artifact(evidence_root, record['package_lock'], REPORT_LIMIT)
    package = json.loads(lock)['dependencies'][pins['package']]
    require(digest(lock) == inventory['Packages/packages-lock.json'] and package.get('version') == pins['version'],
            'Sentis normalization requires the original package lock and approved package version')
    observed = artifact(evidence_root, record['after'], REPORT_LIMIT)
    expected, count = SENTIS_STANDALONE.subn(rb'\1\2', runtime)
    require(count == 1 and observed == expected, 'Startup changed more than the exact approved Standalone symbol')
    return observed


def verify_source_override(raw, receipt, manifest, evidence_root):
    override = raw['settings_override']
    path = 'ProjectSettings/ProjectSettings.asset'
    require(override['path'] == path and override['field'] in ('companyName', 'productName'),
            'Only one reviewed companyName or productName setting can differ')
    original = artifact(evidence_root, override['before'], REPORT_LIMIT)
    runtime = artifact(evidence_root, override['after'], REPORT_LIMIT)
    field = override['field'].encode()
    pattern = rb'^([ \t]*' + field + rb':[ \t]*)([^\r\n]*)$'
    prior = re.findall(pattern, original, re.MULTILINE)
    current = re.findall(pattern, runtime, re.MULTILINE)
    require(len(prior) == len(current) == 1 and prior[0] != current[0]
            and re.sub(pattern, lambda match: match[1] + current[0][1], original, count=1, flags=re.MULTILINE) == runtime,
            'Runtime source changed outside one approved player setting')
    inputs = json.loads(artifact(evidence_root, override['inventory'], REPORT_LIMIT))
    require(inputs.get(path) == digest(original), 'Baseline inventory disagrees with reviewed settings bytes')
    if 'startup_normalization' in override:
        runtime = verify_startup_normalization(runtime, override['startup_normalization'],
                                               manifest['startup_normalization'], inputs, evidence_root)
    original_snapshot = snapshot_digest(inputs)
    runtime_snapshot = snapshot_digest({**inputs, path: digest(runtime)})
    scope = receipt['scope']
    require(all(scope[key] == original_snapshot for key in ('original_before', 'original_after', 'copy_before'))
            and all(scope[key] == runtime_snapshot for key in ('runtime_before', 'runtime_after')),
            'Source snapshots differ beyond the exact approved disposable settings')


def verify_isolation(raw, receipt, manifest):
    scope = receipt['scope']
    project, original = raw['project_path'], raw['original_project_path']
    require(path_identity(project) == scope['project_path_sha256']
            and path_identity(original) == scope['original_path_sha256'] and project != original,
            'Original and copied projects require distinct exact identities')
    project_dir, original_dir = PurePosixPath(project), PurePosixPath(original)
    require(project_dir not in original_dir.parents and original_dir not in project_dir.parents,
            'Original and copied projects overlap')
    path_identity(raw['disposable_root'])
    disposable = PurePosixPath(raw['disposable_root'])
    require(disposable in project_dir.parents and disposable not in original_dir.parents and disposable != original_dir,
            'Source and isolated target roots overlap')
    for name in ('report_directory', 'log_directory', 'observed_persistent_data_path', 'observed_default_result_path'):
        observed = raw[name]
        path_identity(observed)
        require(disposable in PurePosixPath(observed).parents, f'{name} escapes disposable roots')
    require(raw['generated_directories'] == manifest['isolation']['generated_directories']
            and raw['resource_scope'] == manifest['isolation']['resource_scope'], 'Runtime directory or resource isolation differs')
    require(PurePosixPath(raw['observed_default_result_path']).parent == PurePosixPath(raw['observed_persistent_data_path']),
            'Default test result is outside the isolated persistent directory')
    require(raw['source_file_changes'] == {} and raw['original_output_changes'] == {}, 'Original or fixture source changed during execution')
    return project


def verify(manifest, receipt, evidence_root):
    require(manifest['schema'] == 1 and manifest['kind'] == 'director-unity-baseline-manifest', 'Unsupported fixture manifest')
    require(receipt['schema'] == 1 and receipt['kind'] == 'director-unity-baseline-receipt' and receipt['origin'] == 'observed-unity-editor',
            'A synthetic or missing receipt cannot qualify native behavior')
    for name in ('fixture_id', 'lane', 'recipe_id', 'test_filter'):
        require(receipt[name] == manifest[name], f'Unexpected {name}')
    tools = receipt['tools']
    require(all(tools.get(name) == value for name, value in manifest['tool_pins'].items())
            and all(isinstance(tools.get(name), str) and tools[name].strip() for name in ('unity_cli', 'blender_version', 'blender_build')),
            'Tool pins are missing or differ from the selected fixture')
    profile = receipt['profile']
    require(profile['flavor'] == manifest['child_flavor'] and profile['verified'] is True and pin(profile['identity'])
            and pin(profile['environment_id']) and QUEUE_ID.fullmatch(profile['queue_id']) and OBJECT_ID.fullmatch(profile['base_commit']),
            'Expected an owned Unity child with exact queue, profile and Git base')
    raw_isolation = json.loads(artifact(evidence_root, receipt['isolation'], REPORT_LIMIT))
    project_path = verify_isolation(raw_isolation, receipt, manifest)
    verify_source_override(raw_isolation, receipt, manifest, evidence_root)
    live, batch, cleanup = (receipt[name] for name in ('pipeline', 'batch', 'cleanup'))
    require(type(batch['pid']) is int and batch['pid'] > 0 and type(live['observed_pid']) is int
            and batch['pid'] != live['observed_pid'] and batch['exit_code'] == 0
            and utc(live['stopped_at']) <= utc(batch['started_at']) < utc(batch['finished_at']),
            'An owned Pipeline process must exit before the successful batch attempt')
    require(cleanup['owned_pids'] == [live['observed_pid'], batch['pid']] and cleanup['observed_live_pids'] == []
            and cleanup['resource_released'] is True and utc(cleanup['observed_at']) >= utc(batch['finished_at']),
            'Process or resource cleanup not established')
    verify_pipeline(json.loads(artifact(evidence_root, live['status'], REPORT_LIMIT)), live, tools, project_path)
    verify_live_save_probe(json.loads(artifact(evidence_root, live['save_probe'], REPORT_LIMIT)),
                           artifact(evidence_root, live['process'], REPORT_LIMIT).decode(), live, project_path, raw_isolation)
    log = artifact(evidence_root, batch['log'], LOG_LIMIT).decode('utf-8', errors='replace')
    require(project_path in log and tools['editor'] in log and tools['editor_revision'] in log,
            'Batch log does not identify the exact project and Editor build')
    report = artifact(evidence_root, batch['report'], REPORT_LIMIT)
    observed_output = re.findall(r'Saving results to:[ \t]+([^\r\n<]+)', report.decode() + '\n' + log)
    expected_output = raw_isolation['observed_default_result_path']
    report_path = raw_isolation['absolute_report_path']
    path_identity(report_path)
    allowed_results = {expected_output, report_path}
    require(PurePosixPath(report_path).parent == PurePosixPath(raw_isolation['report_directory'])
            and expected_output in observed_output and set(observed_output) <= allowed_results,
            'UTF default result path was not observed or names an unexpected location')
    return verify_report(report, manifest['test_filter'], batch, project_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('evidence_root', type=Path)
    args = parser.parse_args()
    try:
        summary = verify(json.loads(args.manifest.read_text()), json.loads(args.receipt.read_text()), args.evidence_root)
    except (KeyError, TypeError, OSError, ValueError, ElementTree.ParseError) as error:
        parser.exit(2, f'{error}\n')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
