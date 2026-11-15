"""Portable controls and optional observed Director Unity receipt verification."""

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest


FIXTURE = Path(__file__).resolve().parent / 'fixtures/director'
MANIFEST = json.loads((FIXTURE / 'unity-baseline.json').read_text())
SPEC = importlib.util.spec_from_file_location('verify_unity_baseline', FIXTURE / 'verify-unity-baseline.py')
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


class PortableReceiptControls(unittest.TestCase):
    """Constructed parser input supplies no native execution evidence."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.raw = Path(temporary.name)
        self.project = '/private/tmp/director-qualified/child'
        original = '/repo/original'
        fixture_settings = 'ProjectSettings/ProjectSettings.asset'
        original_settings = ('PlayerSettings:\n  companyName: DefaultCompany\n  productName: skill-tree-sandbox\n'
                             '  scriptingDefineSymbols:\n    Standalone: SENTIS_ANALYTICS_ENABLED;APP_UI_EDITOR_ONLY\n')
        runtime_settings = original_settings.replace('DefaultCompany', 'DirectorFixture')
        before = self.write('settings-original.asset', original_settings)
        after = self.write('settings-runtime.asset', runtime_settings)
        inventory = {'Assets/fixture.meta': 'a' * 64, fixture_settings: before['sha256']}
        baseline = VERIFIER.snapshot_digest(inventory)
        runtime = VERIFIER.snapshot_digest({**inventory, fixture_settings: after['sha256']})
        self.ready = {
            'success': True, 'errors': [],
            'data': {
                'command': 'editor status',
                'target': {'host': '127.0.0.1', 'projectPath': self.project},
                'result': {
                    'status': 'ready', 'playMode': 'stopped', 'compiling': False,
                    'lastHeartbeat': '2026-11-15T10:00:03Z',
                    'projectPath': self.project, 'unityVersion': '6000.3.27f2',
                },
            },
        }
        self.report = f'''<test-run testcasecount="1" result="Passed" total="1" passed="1" failed="0" inconclusive="0" skipped="0" start-time="2026-11-15 10:00:20Z" end-time="2026-11-15 10:00:20Z">
 <test-suite type="Assembly" fullname="{self.project}/Library/ScriptAssemblies/SkillTreeSandbox.EditModeTests.dll">
  <properties><property name="_PID" value="9872"/><property name="platform" value="EditMode"/></properties>
  <test-case fullname="{MANIFEST['test_filter']}" result="Passed"><output>Saving results to: /private/tmp/director-qualified/saves/TestResults.xml
</output></test-case>
 </test-suite>
</test-run>'''
        self.isolation = {
            'original_project_path': original, 'project_path': self.project,
            'disposable_root': '/private/tmp/director-qualified',
            'report_directory': '/private/tmp/director-qualified/reports',
            'absolute_report_path': '/private/tmp/director-qualified/reports/editmode.xml',
            'log_directory': '/private/tmp/director-qualified/logs',
            'observed_persistent_data_path': '/private/tmp/director-qualified/saves',
            'observed_default_result_path': '/private/tmp/director-qualified/saves/TestResults.xml',
            'generated_directories': MANIFEST['isolation']['generated_directories'],
            'resource_scope': MANIFEST['isolation']['resource_scope'], 'source_file_changes': {}, 'original_output_changes': {},
            'settings_override': {'path': fixture_settings, 'field': 'companyName', 'before': before, 'after': after,
                                  'inventory': self.write('inventory.json', inventory)},
        }
        self.probe = {'success': True, 'errors': [], 'data': {'command': 'script run', 'target': self.ready['data']['target'],
                      'result': {'result': {'projectPath': self.project, 'pid': 9871,
                                           'persistentDataPath': self.isolation['observed_persistent_data_path'],
                                           'defaultTestResultsPath': self.isolation['observed_default_result_path']}}}}
        self.receipt = {**{key: MANIFEST[key] for key in ('fixture_id', 'lane', 'recipe_id', 'test_filter')},
            'schema': 1, 'kind': 'director-unity-baseline-receipt', 'origin': 'observed-unity-editor',
            'tools': {**MANIFEST['tool_pins'], 'unity_cli': 'fixture', 'blender_version': 'fixture', 'blender_build': 'fixture'},
            'scope': {**{name: baseline for name in ('original_before', 'original_after', 'copy_before', 'copy_after')},
                      'runtime_before': runtime, 'runtime_after': runtime,
                      'original_path_sha256': VERIFIER.path_identity(original), 'project_path_sha256': VERIFIER.path_identity(self.project)},
            'profile': {'flavor': 'unity', 'verified': True, 'identity': 'b' * 64, 'environment_id': 'c' * 64,
                        'queue_id': 'Q-12345678-1234-1234-1234-123456789abc', 'base_commit': 'd' * 40},
            'pipeline': {'requested_pid': 9871, 'observed_pid': 9871, 'started_at': '2026-11-15T10:00:01Z',
                         'observed_at': '2026-11-15T10:00:04Z', 'stopped_at': '2026-11-15T10:00:05Z',
                         'status': self.write('pipeline.json', self.ready), 'save_probe': self.write('save-probe.json', self.probe),
                         'process': self.write('process.txt', f'9871 /Applications/Unity -projectPath {self.project}\n')},
            'batch': {'pid': 9872, 'exit_code': 0, 'started_at': '2026-11-15T10:00:06Z', 'finished_at': '2026-11-15T10:00:25Z',
                      'report': self.write('editmode.xml', self.report),
                      'log': self.write('editor.log', f"{self.project}\n{MANIFEST['tool_pins']['editor']}\n{MANIFEST['tool_pins']['editor_revision']}\n")},
            'cleanup': {'owned_pids': [9871, 9872], 'observed_live_pids': [], 'resource_released': True,
                        'observed_at': '2026-11-15T10:00:26Z'},
            'isolation': self.write('isolation.json', self.isolation),
        }

    def write(self, name, value):
        data = (value if isinstance(value, str) else json.dumps(value)).encode()
        (self.raw / name).write_bytes(data)
        return {'path': name, 'sha256': VERIFIER.digest(data)}

    def verify(self):
        return VERIFIER.verify(MANIFEST, self.receipt, self.raw)

    def test_exact_shape_and_matching_details(self):
        self.assertEqual(self.verify(), {'discovered': 1, 'passed': 1, 'failed': 0, 'skipped': 0})

    def test_altered_raw_bytes(self):
        (self.raw / 'editor.log').write_text('Local edit')
        with self.assertRaisesRegex(ValueError, 'bytes differ'):
            self.verify()

    def test_report_must_discover_one_exact_passing_case(self):
        for old, replacement, reason in (
                ('skipped="0"', 'skipped="1"', 'zero failures or skips'),
                ('passed="1"', 'passed="0"', 'one pass'),
                (MANIFEST['test_filter'], 'Another.Smoke', 'selected stock filter'),
                ('9872', '7777', 'reporting process'),
                (self.project, '/repo/original', 'another project'),
                ('2026-11-15 10:00:20Z', '2026-11-14 10:00:20Z', 'predates')):
            with self.subTest(reason=reason):
                self.receipt['batch']['report'] = self.write('editmode.xml', self.report.replace(old, replacement))
                with self.assertRaisesRegex(ValueError, reason):
                    self.verify()

    def test_pipeline_must_match_owned_pid_and_exact_copy(self):
        self.receipt['pipeline']['observed_pid'] = 9873
        self.receipt['cleanup']['owned_pids'][0] = 9873
        with self.assertRaisesRegex(ValueError, 'matching process ownership'):
            self.verify()
        self.receipt['pipeline']['observed_pid'] = 9871
        self.receipt['cleanup']['owned_pids'][0] = 9871
        self.ready['data']['target']['projectPath'] = '/repo/original'
        self.receipt['pipeline']['status'] = self.write('pipeline.json', self.ready)
        with self.assertRaisesRegex(ValueError, 'exact isolated project'):
            self.verify()

    def test_live_save_probe_and_utf_observation_both_bind_isolation(self):
        self.probe['data']['result']['result']['pid'] = 9879
        self.receipt['pipeline']['save_probe'] = self.write('save-probe.json', self.probe)
        with self.assertRaisesRegex(ValueError, 'different project, process or persistent path'):
            self.verify()
        self.probe['data']['result']['result']['pid'] = 9871
        self.receipt['pipeline']['save_probe'] = self.write('save-probe.json', self.probe)
        self.receipt['batch']['report'] = self.write('editmode.xml', self.report.replace('Saving results to:', 'Other:'))
        with self.assertRaisesRegex(ValueError, 'UTF default result path'):
            self.verify()

    def test_runtime_difference_is_limited_to_exact_reviewed_setting(self):
        runtime = (self.raw / 'settings-runtime.asset').read_text() + '  unrelated: changed\n'
        self.isolation['settings_override']['after'] = self.write('settings-runtime.asset', runtime)
        self.receipt['isolation'] = self.write('isolation.json', self.isolation)
        with self.assertRaisesRegex(ValueError, 'outside one approved player setting'):
            self.verify()

    def test_only_the_pinned_standalone_normalization_can_extend_the_company_override(self):
        manifest = deepcopy(MANIFEST)
        pins = manifest['startup_normalization']
        vendor = self.write('vendor.cs', 'Constructed vendor evidence for the portable control.')
        pins['vendor_source_sha256'] = vendor['sha256']
        lock = self.write('packages-lock.json', {'dependencies': {pins['package']: {'version': pins['version']}}})
        override = self.isolation['settings_override']
        inputs = json.loads((self.raw / override['inventory']['path']).read_text())
        inputs['Packages/packages-lock.json'] = lock['sha256']
        override['inventory'] = self.write('inventory.json', inputs)
        approved = (self.raw / 'settings-runtime.asset').read_text().replace('SENTIS_ANALYTICS_ENABLED;', '')
        normalized = self.write('settings-normalized.asset', approved)
        override['startup_normalization'] = {'vendor_source': vendor, 'package_lock': lock, 'after': normalized}
        baseline = VERIFIER.snapshot_digest(inputs)
        runtime = VERIFIER.snapshot_digest({**inputs, override['path']: normalized['sha256']})
        self.receipt['scope'].update(original_before=baseline, original_after=baseline, copy_before=baseline,
                                     runtime_before=runtime, runtime_after=runtime)
        self.receipt['isolation'] = self.write('isolation.json', self.isolation)
        self.assertEqual(VERIFIER.verify(manifest, self.receipt, self.raw)['passed'], 1)
        pins['vendor_source_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'approved vendor source'):
            VERIFIER.verify(manifest, self.receipt, self.raw)
        pins['vendor_source_sha256'] = vendor['sha256']
        override['startup_normalization']['after'] = self.write('settings-normalized.asset', approved.replace('APP_UI_EDITOR_ONLY', 'FOREIGN'))
        self.receipt['isolation'] = self.write('isolation.json', self.isolation)
        with self.assertRaisesRegex(ValueError, 'exact approved Standalone symbol'):
            VERIFIER.verify(manifest, self.receipt, self.raw)

    def test_synthetic_origin_shared_saves_and_incomplete_cleanup_do_not_qualify(self):
        current = deepcopy(self.receipt)
        self.receipt['origin'] = 'fixture'
        with self.assertRaisesRegex(ValueError, 'synthetic'):
            self.verify()
        self.receipt = deepcopy(current)
        self.isolation['observed_default_result_path'] = '/repo/original/TestResults.xml'
        self.receipt['isolation'] = self.write('isolation.json', self.isolation)
        with self.assertRaisesRegex(ValueError, 'escapes disposable'):
            self.verify()
        self.receipt = current
        self.isolation['observed_default_result_path'] = '/private/tmp/director-qualified/saves/TestResults.xml'
        self.write('isolation.json', self.isolation)
        self.receipt['cleanup']['observed_live_pids'].append(9872)
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            self.verify()

    def test_source_snapshot_covers_meta_and_rejects_symlink(self):
        for name in MANIFEST['source_paths']:
            (self.raw / name).mkdir()
        (self.raw / 'Assets/test.meta').write_text('guid: exact-a')
        first = VERIFIER.snapshot(self.raw, MANIFEST['source_paths'])
        (self.raw / 'Assets/test.meta').write_text('guid: exact-b')
        self.assertNotEqual(first, VERIFIER.snapshot(self.raw, MANIFEST['source_paths']))
        (self.raw / 'Assets/alias').symlink_to(self.raw / 'Assets/test.meta')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            VERIFIER.snapshot(self.raw, MANIFEST['source_paths'])


class ObservedReceipt(unittest.TestCase):
    def test_observed_report_when_explicitly_selected(self):
        root = os.environ.get('DIRECTOR_UNITY_EVIDENCE_ROOT')
        if not root:
            self.skipTest('No observed native evidence selected. Portable controls establish parser behavior only.')
        root = Path(root)
        receipt = Path(__file__).resolve().parents[1] / 'history/validation/director/unity-baseline.json'
        self.assertEqual(VERIFIER.verify(MANIFEST, json.loads(receipt.read_text()), root),
                         {'discovered': 1, 'passed': 1, 'failed': 0, 'skipped': 0})


if __name__ == '__main__':
    unittest.main()
