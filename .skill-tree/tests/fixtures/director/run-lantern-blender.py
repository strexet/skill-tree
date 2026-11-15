"""Observe a pinned Blender export and round trip in an exact disposable folder."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess


FIXTURES = '.skill-tree/tests/fixtures/director'
ART_MANIFEST = '.skill-tree/history/validation/director/lantern-art.json'
PROFILE = '.skill-tree/installation/profile.json'
TASK = 'T-2d4cdd62-11bd-49b7-906f-343a0df202f3'
RECIPE = 'director-blender-observed'
CLEANUP_RESERVE = 15


def require(condition, message):
    if not condition:
        raise ValueError(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def exact(path, *, directory=False):
    require(path.is_absolute() and path.resolve(strict=True) == path
            and (path.is_dir() if directory else path.is_file()), 'Use an exact bound local path')
    return path


def snapshot(root):
    files = {}
    for area in ('Assets', 'Packages', 'ProjectSettings'):
        source = root / area
        require(source.is_dir() and not source.is_symlink(), 'The exact original fixture input is unavailable')
        for path in sorted(source.rglob('*')):
            require(not path.is_symlink(), 'The exact original fixture must not contain aliased entries')
            if path.is_file():
                files[path.relative_to(root).as_posix()] = digest(path)
    content = ''.join(f'{name}\0{fingerprint}\n' for name, fingerprint in sorted(files.items())).encode()
    return {'files': len(files), 'sha256': sha(content)}


def check_story(source, manifest):
    for mode in ('hand', 'belt'):
        entry = manifest['story'][mode]
        file = exact(source / entry['path'])
        require(file.is_relative_to(source) and digest(file) == entry['sha256'],
                'Approved story fixture hash changed')
        record = read(file)
        expected = (manifest['story']['id'], entry['revision'], mode)
        require((record['requirement_id'], record['revision'], record['attachment']) == expected,
                'Approved attachment pin changed')


def wrappers(out, manifest, artifact):
    results = {}
    for mode, spec in manifest['wrappers'].items():
        row = manifest['story'][mode]
        model = manifest['model']
        value = {
            'schema': 1, 'revision': spec['revision'], 'attachment': mode, 'socket': spec['socket'],
            'artifact': artifact, 'story': {'id': manifest['story']['id'], 'revision': row['revision'],
                                           'sha256': row['sha256']},
            'scale_meters': model['scale_meters'], 'grip_socket': model['sockets']['GripSocket'],
            'belt_socket': model['sockets']['BeltSocket'],
        }
        path = out / spec['path']
        write(path, value)
        results[mode] = {'path': spec['path'], 'sha256': digest(path)}
    return results


def launch(binary, source, out, manifest, duration):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {'PYTHONHOME', 'PYTHONPATH', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_CONFIG',
                                  'BLENDER_USER_DATAFILES'}}
    user = out / 'runtime'
    user.mkdir()
    for name in ('CONFIG', 'SCRIPTS', 'DATAFILES'):
        place = user / name.lower()
        place.mkdir()
        environment['BLENDER_USER_' + name] = str(place)
    environment['TMPDIR'] = str(user)
    log = out / 'blender.log'
    start = now()
    with log.open('wb') as stream:
        process = subprocess.Popen([str(binary), '--background', '--factory-startup', '--disable-autoexec',
                                    '--python-exit-code', '4', '--python', str(source), '--', str(manifest)],
                                   cwd=out, env=environment, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            exit_code = process.wait(timeout=duration - CLEANUP_RESERVE)
        except subprocess.TimeoutExpired as error:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            raise RuntimeError('The pinned Blender export exceeded its deadline') from error
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        cleared = True
    else:
        cleared = False
    require(cleared, 'The bounded Blender process group did not finish')
    require(exit_code == 0 and b'DIRECTOR_LANTERN_EXPORT_VERIFIED' in log.read_bytes(),
            'The pinned Blender process did not verify the export')
    return {'pid': process.pid, 'exit_code': exit_code, 'started_at': start, 'finished_at': now(),
            'process_group_cleared': cleared, 'log': {'path': log.name, 'sha256': digest(log)}}


def run(args):
    root = exact(args.source, directory=True)
    locator = read(exact(args.locator))
    binary = exact(Path(locator['blender']))
    original = exact(Path(locator['original_project']), directory=True)
    out = args.output
    require(out.is_absolute() and out == out.resolve() and not out.exists()
            and not out.is_relative_to(root) and not out.is_relative_to(original),
            'Use one fresh disposable output root away from all source inputs')
    require(args.seconds > CLEANUP_RESERVE and os.access(binary, os.X_OK),
            'The pinned Blender binary and positive cleanup reserve are required')
    manifest_file = root / FIXTURES / 'lantern-fixture.json'
    manifest = read(manifest_file)
    check_story(root, manifest)
    if original.name != manifest['source_fixture_id']:
        raise ValueError('The exact original fixture name changed')
    profile_sha = digest(root / PROFILE)
    prepared = read(root / ART_MANIFEST)
    require(prepared['fixture_sha256'] == digest(manifest_file)
            and prepared['profile_sha256'] == profile_sha and prepared['task_id'] == TASK
            and prepared['source_run_id'] == args.run_id and prepared['fixture_id'] == manifest['fixture_id']
            and read(root / PROFILE)['recipes'][RECIPE]['lane'] == 'native',
            'Exact owning native fixture recipe and manifest are unavailable')
    attempt = read(exact(args.attempt))
    require((attempt['task_id'], attempt['check_id'], attempt['recipe']['lane'])
            == (TASK, 'director-lantern-art', 'native'), 'Select the exact prepared Blender check')
    before = snapshot(original)
    baseline = read(root / FIXTURES / 'unity-baseline.json')['observed_baseline']['original_snapshot']
    script = root / FIXTURES / 'produce-lantern-blender.py'
    executable_sha = digest(binary)
    require(before == baseline == prepared['original_snapshot'] and executable_sha == prepared['blender_executable_sha256']
            and digest(script) == prepared['producer_sha256'], 'The admitted original fixture or tool changed')
    started = datetime.fromisoformat(attempt['prepared_at'])
    deadline = datetime.fromisoformat(attempt['launch']['deadline_utc'])
    require(started <= datetime.now(timezone.utc) and (deadline - datetime.now(timezone.utc)).total_seconds() > args.seconds,
            'The prepared native attempt lacks the bounded work and cleanup window')
    out.mkdir()
    process = launch(binary, script, out, manifest_file, args.seconds)
    native_path = out / 'blender-native.json'
    native = read(native_path)
    require((native['version'], native['build']) == (manifest['tool_pins']['blender_version'],
                                                      manifest['tool_pins']['blender_build'])
            and native['pid'] == process['pid'] and native['manifest_sha256'] == prepared['fixture_sha256'],
            'The observed Blender run does not match its exact build/provenance pins')
    check_story(root, manifest)
    after = snapshot(original)
    require(before == after and digest(binary) == executable_sha and digest(root / PROFILE) == profile_sha,
            'Original fixture or pinned tools changed during the run')
    artifact = native['artifact']
    require(artifact['path'] == manifest['model']['asset'] and digest(out / artifact['path']) == artifact['sha256'],
            'The observed export bytes changed')
    references = wrappers(out, manifest, {'path': artifact['path'], 'sha256': artifact['sha256']})
    result = {
        'schema': 1, 'kind': 'director-lantern-art-result', 'fixture_id': manifest['fixture_id'],
        'manifest_sha256': digest(root / ART_MANIFEST), 'task_id': TASK, 'source_run_id': args.run_id,
        'attempt_id': attempt['attempt_id'], 'prepared_at': attempt['prepared_at'],
        'deadline': attempt['launch']['deadline_utc'],
        'profile_sha256': profile_sha, 'source_before': before, 'source_after': after,
        'tool': {'version': native['version'], 'build': native['build'], 'executable_sha256': executable_sha},
        'process': process, 'native': {'path': native_path.name, 'sha256': digest(native_path)},
        'artifact': artifact, 'wrappers': references,
    }
    write(out / 'lantern-art-result.json', result)
    print(json.dumps({'output': str(out), 'artifact_sha256': artifact['sha256'], 'pid': process['pid']}, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--locator', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--seconds', type=int, default=90)
    args = parser.parse_args()
    run(args)


if __name__ == '__main__':
    main()
