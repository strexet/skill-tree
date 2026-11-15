"""Capture raw stock EditMode evidence for an enrolled Director task."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from xml.etree import ElementTree


PROFILE = Path('.skill-tree/installation/profile.json')
MANAGER = Path('.skill-tree/installation/manager.js')
HELPER = Path('.agents/skills/skill-tree-implement-all/scripts/workflow-state.py')
SETTINGS = 'ProjectSettings/ProjectSettings.asset'
CLEANUP_SECONDS = 30
PIPELINE_PROBE = (
    'return new { projectPath = System.IO.Path.GetDirectoryName(UnityEngine.Application.dataPath), '
    'pid = System.Diagnostics.Process.GetCurrentProcess().Id, '
    'persistentDataPath = UnityEngine.Application.persistentDataPath };'
)


def now():
    return datetime.now(timezone.utc).isoformat()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def json_file(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def digest(path):
    with path.open('rb') as stream:
        return sha256(stream.read()).hexdigest()


def exact_path(value, *, directory=False):
    path = Path(value)
    require(path.is_absolute() and path.resolve(strict=True) == path,
            'The locator requires exact absolute paths without aliases')
    require(path.is_dir() if directory else path.is_file(), 'A selected location is unavailable')
    return path


def command(*arguments, cwd=None, timeout=60, env=None):
    result = subprocess.run([str(argument) for argument in arguments], cwd=cwd, env=env,
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Command failed: ' + Path(str(arguments[0])).name + '\n' + result.stdout + result.stderr)
    return result.stdout


def workflow(worktree, run_id, operation, payload=None):
    arguments = [sys.executable, '-B', worktree / HELPER, operation, worktree, '--run-id', run_id]
    if payload is None:
        return json.loads(command(*arguments))
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', encoding='utf-8') as stream:
        json.dump(payload, stream)
        stream.flush()
        return json.loads(command(*arguments, '--input', stream.name))


def inventory(root, areas):
    result = {}
    for area in areas:
        directory = root / area
        require(directory.is_dir() and not directory.is_symlink(), 'A required source directory is unavailable')
        for path in directory.rglob('*'):
            require(not path.is_symlink(), 'A copied Unity input is a symlink')
            if path.is_file():
                result[path.relative_to(root).as_posix()] = digest(path)
    return result


def file_observation(path):
    if path.exists():
        require(path.is_file() and not path.is_symlink(), 'The original UTF output is not an ordinary file')
        return {'sha256': digest(path), 'mtime_ns': path.stat().st_mtime_ns}
    return None


def copy_fixture(original, project, reports, manifest, company_name):
    areas = manifest['source_paths']
    source_before = inventory(original, areas)
    for area in areas:
        shutil.copytree(original / area, project / area)
    copied = inventory(project, areas)
    require(copied == source_before, 'The disposable copy differs from the original source')
    settings = project / SETTINGS
    initial = settings.read_bytes()
    company = re.findall(rb'^  companyName: ([A-Za-z0-9_-]+)$', initial, re.M)
    product = re.findall(rb'^  productName: ([A-Za-z0-9_-]+)$', initial, re.M)
    require(len(company) == len(product) == 1 and product[0].decode() == manifest['fixture_id'],
            'The original sandbox save identity changed')
    isolated = re.sub(rb'(?m)^  companyName: [A-Za-z0-9_-]+$',
                      b'  companyName: ' + company_name.encode(), initial)
    require(initial != isolated, 'The isolated company name must be distinct')
    settings.write_bytes(isolated)
    (reports / 'original-player-settings.asset').write_bytes(initial)
    (reports / 'isolated-player-settings.asset').write_bytes(isolated)
    runtime = inventory(project, areas)
    require({path for path in source_before if source_before[path] != runtime.get(path)} == {SETTINGS}
            and runtime.keys() == copied.keys(), 'The copy has an unreviewed runtime source delta')
    return source_before, copied, runtime, company[0].decode(), product[0].decode()


def prepare_child(original, project, manifest):
    generated = manifest['isolation']['generated_directories']
    (project / '.gitignore').write_text(''.join(f'/{name}/\n' for name in generated), encoding='utf-8')
    (project / '.skill-tree/documents').mkdir(parents=True)
    recipe = Path('.skill-tree/worktree-profile.json')
    queue = Path('.skill-tree/documents/future.md')
    for relative in (recipe, queue):
        shutil.copy2(original / relative, project / relative)
    git_environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    git_environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    command('git', 'init', '-b', 'main', cwd=project, env=git_environment)
    command('git', 'add', '--', *manifest['source_paths'], '.gitignore', recipe, queue, cwd=project, env=git_environment)
    command('git', '-c', 'user.name=Director Test Fixture', '-c', 'user.email=director-fixture@example.invalid',
            '-c', 'commit.gpgsign=false', '-c', f'core.hooksPath={os.devnull}', 'commit',
            '-m', 'Record the isolated Director validation fixture', cwd=project, env=git_environment)
    return command('git', 'rev-parse', 'HEAD', cwd=project, env=git_environment).strip()


def install_child(original, project):
    source = (original / '.skill-tree/installation/source').resolve(strict=True)
    script = """
const installation = require(process.argv[1]);
const profile = require(process.argv[4]);
const selections = Object.entries(profile.destinations).map(([rel, row]) => ({
  rel, name: row.name, provider: row.provider, providers: row.providers,
}));
const result = installation.install(process.argv[2], process.argv[3], 'unity', selections);
console.log(JSON.stringify({action: result.action, profile: result.profile.identity}));
"""
    environment = {key: value for key, value in os.environ.items() if key not in ('NODE_OPTIONS', 'NODE_PATH')}
    receipt = json.loads(command('node', '-e', script, source / 'lib/installation.js', project, source,
                                 original / PROFILE, env=environment, timeout=90))
    verification = command('node', project / MANAGER, '--verify', env=environment).strip()
    profile = json_file(project / PROFILE)
    require(receipt['action'] == 'installed' and receipt['profile'] == profile['identity']
            and profile['project_root'] == str(project) and profile['flavor'] == 'unity',
            'The installation result does not match the disposable child')
    return profile, receipt | {'verification': verification, 'profile_sha256': digest(project / PROFILE)}


def setup_child_queue(project):
    # The fresh child owns an empty queue; the helper creates the local schema-3 locator.
    helper = project / '.agents/skills/skill-tree-work-through-next/scripts/workflow-state.py'
    state = json.loads(command(sys.executable, '-B', helper, 'index', project))
    require(not state['tasks'] and state['active_run'] is None and not state.get('run_registry'),
            'The disposable child queue already contains work')
    registry = json.loads(command(sys.executable, '-B', helper, 'workspace-setup', project))
    require(re.fullmatch(r'Q-[0-9a-f-]{36}', registry['queue_id']) and not registry['runs'] and not registry['claims'],
            'The disposable child did not receive an empty schema-3 queue')
    return registry['queue_id']


def group_exists(group):
    try:
        os.killpg(group, 0)
    except ProcessLookupError:
        return False
    return True


def stop_group(process):
    for sig, timeout in ((signal.SIGTERM, CLEANUP_SECONDS - 5), (signal.SIGKILL, 5)):
        process.poll()
        if not group_exists(process.pid):
            return
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        cutoff = time.monotonic() + timeout
        while time.monotonic() < cutoff:
            process.poll()
            if not group_exists(process.pid):
                return
            time.sleep(0.2)
    raise RuntimeError('The owned Editor process group did not stop')


@contextmanager
def owned_editor(arguments, launch_log, live_groups):
    with launch_log.open('w', encoding='utf-8') as output:
        process = subprocess.Popen([str(item) for item in arguments], stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        live_groups.add(process.pid)
        try:
            yield process
        finally:
            stop_group(process)
            live_groups.remove(process.pid)


def pipeline_result(raw):
    envelope = json.loads(raw)
    require(envelope['success'] is True and not envelope['errors'], 'The Pipeline request failed')
    return envelope['data']


def probe_pipeline(tools, project, reports, live_groups, deadline_seconds, editor_build):
    started_at = now()
    with owned_editor([tools['editor'], '-batchmode', '-nographics', '-projectPath', project,
                       '-logFile', reports / 'pipeline.log'], reports / 'pipeline-launch.txt', live_groups) as process:
        target = ['--project-path', project, '--pid', process.pid]
        cli = [tools['unity_cli'], '--proxy-disable', '--format', 'json', 'command']
        deadline = time.monotonic() + deadline_seconds
        last_error = ''
        while deadline - time.monotonic() > 8:
            require(process.poll() is None, 'The disposable Pipeline Editor exited before qualification')
            try:
                raw = command(*cli, 'editor', 'status', *target, '--timeout', '4', timeout=5)
                status = pipeline_result(raw)
                runtime = status['result']
                endpoint = status['target']
                require(endpoint['host'] in ('127.0.0.1', '::1') and endpoint['projectPath'] == str(project)
                        and runtime['projectPath'] == str(project) and runtime['unityVersion'] == editor_build
                        and runtime['status'] == 'ready' and runtime['playMode'] == 'stopped'
                        and runtime['compiling'] is False, 'Pipeline is not ready in the exact disposable project')
                probe_budget = min(12, int(deadline - time.monotonic()) - 1)
                require(probe_budget > 0, 'The Pipeline discovery deadline expired')
                evaluated = command(*cli, 'script', 'eval', PIPELINE_PROBE, *target,
                                    '--timeout', probe_budget, timeout=probe_budget + 1)
                proof = pipeline_result(evaluated)['result']
                if isinstance(proof, dict) and 'result' in proof:
                    proof = proof['result']
                if isinstance(proof, str):
                    proof = json.loads(proof)
                persistent = Path(proof['persistentDataPath'])
                require(proof['projectPath'] == str(project) and proof['pid'] == process.pid
                        and persistent.is_absolute() and persistent.resolve().is_relative_to(project.parent)
                        and not persistent.is_relative_to(project), 'The owned Editor did not attest private saves')
                (reports / 'pipeline-state.json').write_text(raw, encoding='utf-8')
                (reports / 'persistent-path.json').write_text(evaluated, encoding='utf-8')
                identity = {'pid': process.pid, 'started_at': started_at, 'observed_at': now(),
                            'persistent_path': str(persistent), 'default_results_path': str(persistent / 'TestResults.xml')}
                break
            except (RuntimeError, subprocess.TimeoutExpired, KeyError, TypeError, ValueError) as error:
                last_error = str(error)
                time.sleep(1)
        else:
            raise RuntimeError('Named Pipeline readiness deadline expired: ' + last_error)
    identity['stopped_at'] = now()
    return identity


def stock_editmode(tools, project, reports, live_groups, timeout, recipe, test_filter, pipeline):
    xml = reports / 'editmode.xml'
    log = reports / 'editmode.log'
    arguments = [
        argument.format(project_root=project, test_filter=test_filter, result_path=xml, log_path=log)
        for argument in recipe['argv'][1:]
    ]
    started_at = now()
    with owned_editor([tools['editor'], *arguments], reports / 'batch-launch.txt', live_groups) as process:
        exit_code = process.wait(timeout=timeout)
        pid = process.pid
    finished_at = now()
    require(exit_code == 0, 'The stock EditMode process reported failure')
    result = ElementTree.parse(xml).getroot()
    cases = list(result.iter('test-case'))
    require(result.get('result') == 'Passed' and len(cases) == 1
            and all(result.get(key) == '0' for key in ('failed', 'skipped', 'inconclusive'))
            and cases[0].get('fullname') == test_filter and cases[0].get('result') == 'Passed',
            'NUnit did not record one exact passing stock test')
    editor = result.find(".//test-suite[@type='Assembly']/properties/property[@name='_PID']")
    require(editor is not None and editor.get('value') == str(pid), 'The stock report did not attest the batch PID')
    require(log.stat().st_size and pipeline['default_results_path'] in
            (xml.read_text(encoding='utf-8') + log.read_text(encoding='utf-8', errors='replace')),
            'UTF did not attest the private default results path')
    return {'pid': pid, 'exit_code': exit_code, 'started_at': started_at, 'finished_at': finished_at,
            'filter': test_filter, 'xml_sha256': digest(xml), 'log_sha256': digest(log), 'summary': result.attrib}


def observe_attempt(args, tools, project, reports, live_groups, manifest, recipe, expected):
    reports.mkdir(exist_ok=True)
    pipeline = probe_pipeline(tools, project, reports, live_groups, args.pipeline_seconds, manifest['tool_pins']['editor'])
    current = inventory(project, manifest['source_paths'])
    attempt = {'pipeline': pipeline, 'reports_path': str(reports)}
    if current != expected:
        return attempt, current
    command('node', project / MANAGER, '--verify')
    attempt['batch'] = stock_editmode(tools, project, reports, live_groups, args.batch_seconds, recipe,
                                      manifest['test_filter'], pipeline)
    return attempt, inventory(project, manifest['source_paths'])


def maybe_refresh_for_sentis(args, project, reports, expected, current, initial_profile):
    require(args.allow_sentis_normalization, 'Reviewed source changed. A bounded recovery decision is required.')
    require(current.keys() == expected.keys() and
            {path for path in current if current[path] != expected[path]} == {SETTINGS},
            'The disposable copy has another source difference')
    initial = (reports / 'isolated-player-settings.asset').read_bytes()
    observed = (project / SETTINGS).read_bytes()
    token = b'    Standalone: SENTIS_ANALYTICS_ENABLED;APP_UI_EDITOR_ONLY\n'
    replacement = b'    Standalone: APP_UI_EDITOR_ONLY\n'
    require(initial.count(token) == 1 and initial.replace(token, replacement) == observed,
            'The observed settings are not the reviewed single-token Sentis removal')

    vendor = list((project / 'Library/PackageCache').glob(
        'com.unity.ai.inference@*/Editor/Analytics/AnalyticsDefineManager.cs'
    ))
    require(len(vendor) == 1, 'The exact installed Sentis normalization source is unavailable')
    package = json_file(vendor[0].parents[2] / 'package.json')
    lock = json_file(project / 'Packages/packages-lock.json')['dependencies']['com.unity.ai.inference']
    require(package['name'] == 'com.unity.ai.inference' and package['version'] == lock['version']
            and b'SENTIS_ANALYTICS_ENABLED' in vendor[0].read_bytes(),
            'The installed Sentis source does not match the locked package')
    shutil.copyfile(vendor[0], reports / 'sentis-analytics-define-manager.cs')
    (reports / 'normalized-player-settings.asset').write_bytes(observed)

    before = digest(project / PROFILE)
    require(initial_profile['identity'] == json_file(project / PROFILE)['identity'],
            'The child profile changed before the supported stopped refresh')
    normalized = command('node', project / MANAGER, '--refresh-profile').strip()
    verification = command('node', project / MANAGER, '--verify').strip()
    updated = json_file(project / PROFILE)
    after = digest(project / PROFILE)
    require(before != after and updated['project_root'] == str(project) and updated['flavor'] == 'unity'
            and updated['source_version'] == initial_profile['source_version']
            and updated['recipes'] == initial_profile['recipes'],
            'The stopped refresh changed identity beyond the reviewed source delta')
    proof = {
        'settings_before': sha256(initial).hexdigest(), 'settings_after': sha256(observed).hexdigest(),
        'profile_before': before, 'profile_after': after, 'profile_identity': updated['identity'],
        'verification': verification, 'refresh_result': normalized,
        'vendor_package_version': package['version'], 'vendor_source_sha256': digest(vendor[0]),
        'vendor_source_path': vendor[0].relative_to(project).as_posix(),
    }
    return updated, proof


def run(args):
    locator = json_file(exact_path(args.locator))
    required = {'original_project', 'editor', 'unity_cli', 'blender', 'application_support'}
    require(set(locator) == required, 'The local locator must define exactly the reviewed project and tool paths')
    tools = {name: exact_path(locator[name]) for name in ('editor', 'unity_cli', 'blender')}
    original = exact_path(locator['original_project'], directory=True)
    support = exact_path(locator['application_support'], directory=True)
    worktree = exact_path(args.worktree, directory=True)
    manifest = json_file(Path(__file__).with_name('unity-baseline.json'))
    require(original.name == manifest['fixture_id'] and manifest['source_paths'] == ['Assets', 'Packages', 'ProjectSettings'],
            'The local locator does not match the named source fixture')
    require(not support.is_relative_to(original) and not support.is_relative_to(worktree),
            'Disposable output must be outside both existing projects')
    command('node', worktree / MANAGER, '--verify')
    selected = workflow(worktree, args.run_id, 'next')
    require(selected['task_id'] == args.task_id and selected['phase'] == 'implement',
            'The enrolled Director checkpoint does not select the exact implementation task')
    command('node', original / MANAGER, '--verify')
    expected_profile = digest(original / PROFILE)
    version_path = original / 'ProjectSettings/ProjectVersion.txt'
    pins = manifest['tool_pins']
    require(f"m_EditorVersionWithRevision: {pins['editor']} ({pins['editor_revision']})" in
            version_path.read_text().splitlines(), 'The original Editor revision differs from the reviewed pin')

    resource = manifest['isolation']['resource_scope']
    claim = workflow(worktree, args.run_id, 'resource', {'resource': resource,
                     'purpose': 'Observe Director stock EditMode in the isolated project'})
    live_groups = set()
    try:
        root = support / ('SkillTreeDirector-' + secrets.token_hex(8))
        root.mkdir(mode=0o700)
        project, reports = root / 'project', root / 'reports'
        project.mkdir()
        reports.mkdir()
        print(root, flush=True)
        available = shutil.disk_usage(root).free
        require(available >= args.minimum_free_bytes, 'Insufficient available disk for the disposable Editor')
        source_before, copied, runtime, company, product = copy_fixture(original, project, reports, manifest, root.name)
        original_results = support / company / product / 'TestResults.xml'
        original_results_before = file_observation(original_results)
        commit = prepare_child(original, project, manifest)
        profile, installation = install_child(original, project)
        queue_id = setup_child_queue(project)
        checks = profile['recipes']
        recipe = checks[manifest['recipe_id']]
        packages = profile['facts']['packages']
        require(recipe['lane'] == manifest['lane'] and recipe['editor_version'] == pins['editor']
                and recipe['utf_version'] == pins['test_framework']
                and packages['com.unity.pipeline']['version'] == pins['pipeline']
                and checks['unity-playmode']['lane'] == 'unity-playmode',
                'The child profile does not expose the reviewed Unity capabilities')
        require(not any((project / name).exists() for name in manifest['isolation']['generated_directories']),
                'The child inherited generated directories')
        preflight = {
            'run_id': args.run_id, 'task_id': args.task_id, 'fixture_commit': commit, 'queue_id': queue_id,
            'project_path': str(project), 'original_profile_sha256': expected_profile,
            'original_source_inventory': source_before, 'copied_source_inventory': copied,
            'runtime_source_inventory': runtime, 'runtime_delta': SETTINGS,
            'installation': installation, 'profile_environment_id': profile['environment_id'],
            'unity_cli': command(tools['unity_cli'], '--version').strip(),
            'blender': command(tools['blender'], '--version').splitlines()[:4],
            'available_bytes': available, 'save_namespace': root.name, 'cleanup_reserve_seconds': CLEANUP_SECONDS,
        }
        write_json(root / 'preflight.json', preflight)
        attempt, current = observe_attempt(args, tools, project, reports / 'initial', live_groups, manifest, recipe, runtime)
        normalization = stale_attempt = None
        if current != runtime:
            stale_attempt = attempt
            profile, normalization = maybe_refresh_for_sentis(args, project, reports, runtime, current, profile)
            runtime = current
            attempt, current = observe_attempt(args, tools, project, reports / 'normalized', live_groups, manifest,
                                               profile['recipes'][manifest['recipe_id']], runtime)
        require('batch' in attempt and current == runtime, 'A fresh stock run did not preserve the selected runtime source')
        require(inventory(project, manifest['source_paths']) == runtime
                and inventory(original, manifest['source_paths']) == source_before
                and digest(original / PROFILE) == expected_profile, 'The original or reviewed copy changed during execution')
        require(file_observation(original_results) == original_results_before, 'The original UTF results changed')
    finally:
        require(not live_groups, 'The resource claim remains held because process cleanup is unresolved')
        workflow(worktree, args.run_id, 'resource', {'resource': resource, 'release': True, 'token': claim['token']})

    write_json(root / 'observed.json', preflight | {
        **attempt,
        'qualified_source_inventory': runtime, 'qualified_profile_sha256': digest(project / PROFILE),
        'sentis_normalization': normalization, 'superseded_attempt': stale_attempt,
        'original_results_before': original_results_before,
        'original_results_after': file_observation(original_results), 'cleanup_complete': True,
    })


def positive_integer(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError('A positive integer is required.')
    return number


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--locator', required=True, help='Machine-local JSON with exact original_project, editor, unity_cli, blender and application_support paths.')
    parser.add_argument('--worktree', required=True, help='Exact installed Director execution checkout.')
    parser.add_argument('--run-id', required=True, help='Enrolled Director WR identity.')
    parser.add_argument('--task-id', required=True, help='Exact selected stock-baseline task.')
    parser.add_argument('--pipeline-seconds', type=positive_integer, default=330)
    parser.add_argument('--batch-seconds', type=positive_integer, default=400)
    parser.add_argument('--minimum-free-bytes', type=positive_integer, default=18 * 1024**3)
    parser.add_argument('--allow-sentis-normalization', action='store_true',
                        help='Use an authorized copy-only recovery for the exact observed Standalone analytics token removal.')
    run(parser.parse_args())


if __name__ == '__main__':
    main()
