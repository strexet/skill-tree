import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location(
    'validation_progress_fixture', Path(__file__).with_name('test-validation-progress.py'),
)
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)
wf = progress.wf

SUCCESS = 'Ran 2 tests in 0.001s\n\nOK\n'
CONTRADICTORY = 'Ran 2 tests in 0.001s\n\nFAILED (failures=1)\nmetrics\nOK\n'


class UnittestCheckVerdictTests(unittest.TestCase):
    def test_one_complete_unittest_summary_accepts_metrics_on_both_sides(self):
        for separator in ('\n', '\r\n'):
            report = ('{"before": 1}\n' + SUCCESS + '{"after": 2}\n').replace('\n', separator)
            with self.subTest(separator=separator):
                self.assertEqual(wf.current_target_check_counts('unit', report), 2)
                self.assertEqual(wf.local_check_count('unit', report), 2)

    def test_incomplete_contradictory_and_ambiguous_reports_do_not_pass(self):
        reports = {
            'unrelated verdict': 'Ran 2 tests in 0.001s\n\nother output\nOK\n',
            'failure then loose success': CONTRADICTORY,
            'failed unittest then unrelated TAP': (
                'Ran 2 tests in 0.001s\n\nFAILED (failures=1)\n'
                '# tests 2\n# pass 2\n# fail 0\n# skipped 0\n# todo 0\n'
            ),
            'success then failure': SUCCESS + 'FAILED (errors=1)\n',
            'failed verdict without count then TAP': (
                'FAILED (failures=1)\n# tests 2\n# pass 2\n# fail 0\n# skipped 0\n# todo 0\n'
            ),
            'skipped verdict without count then TAP': (
                'OK (skipped=1)\n# tests 2\n# pass 2\n# fail 0\n# skipped 0\n# todo 0\n'
            ),
            'invalid duration': 'Ran 2 tests in metrics-only\n\nOK\n',
            'multiple summaries': SUCCESS + SUCCESS,
            'multiple verdicts': 'OK\n' + SUCCESS,
            'verdict precedes count': 'OK\nRan 2 tests in 0.001s\n',
            'missing verdict': 'Ran 2 tests in 0.001s\n',
            'missing count': 'OK\n',
            'skipped test': 'Ran 2 tests in 0.001s\n\nOK (skipped=1)\n',
            'empty run': 'Ran 0 tests in 0.001s\n\nOK\n',
        }
        for name, report in reports.items():
            with self.subTest(name=name):
                self.assertEqual(wf.current_target_check_counts('unit', report), 0)
                self.assertEqual(wf.local_check_count('unit', report), 0)

    def test_reviewed_target_binds_actual_exit_status_count_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            program = root / 'fixture.py'
            program.write_text(
                'import sys\n'
                'print(\'{"stdout_metrics": 1}\')\n'
                'sys.stderr.write(sys.argv[1])\n'
                'print(\'{"stderr_tail": 2}\', file=sys.stderr)\n'
                'sys.exit(int(sys.argv[2]))\n'
            )
            checks, artifacts = wf.run_reviewed_candidate_checks(
                {'id': 'WR-fixture'}, 'unittest-verdict', root,
                {
                    name: {
                        'executable': sys.executable,
                        'argv': [sys.executable, str(program), report, str(exit_code)],
                        'lane': 'unit',
                    }
                    for name, report, exit_code in (
                        ('success', SUCCESS, 0),
                        ('contradictory', CONTRADICTORY, 0),
                        ('nonzero', SUCCESS, 1),
                    )
                },
            )
            success = checks['success']
            self.assertTrue(success['qualified'])
            self.assertEqual(success['discovered'], 2)
            recorded = json.loads(artifacts[success['artifact']['path']])
            self.assertIn('{"stdout_metrics": 1}', recorded['output'])
            self.assertTrue(recorded['output'].rstrip().endswith('{"stderr_tail": 2}'))
            self.assertFalse(checks['contradictory']['qualified'])
            self.assertFalse(checks['nonzero']['qualified'])
            self.assertEqual(checks['nonzero']['exit_code'], 1)

    def test_native_runner_reconciles_pass_with_trailing_metrics_once(self):
        fixture = progress.ValidationProgressTests()
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        recipe = fixture.local_runner_fixture('unit', program=(
            'from pathlib import Path\n'
            'import sys\n'
            'import unittest\n'
            "with Path('runner-invocations').open('a') as log: log.write('run\\n')\n"
            'print(\'{"before": 1}\', flush=True)\n'
            'class ExactFixture(unittest.TestCase):\n'
            '    def test_actual(self): self.assertTrue(True)\n'
            'result = unittest.main(exit=False).result\n'
            'print(\'{"after": 2}\', flush=True)\n'
            'sys.exit(not result.wasSuccessful())\n'
        ))
        tid = fixture.task(recipe=recipe)
        fixture.review_candidate(tid, controller=True, record_result=False)
        request = fixture.local_runner_request(tid)
        selection = {'task_id': tid, 'check_id': 'behavior'}
        original = wf.reconcile_check

        def lose_ack(store, payload):
            if payload['action'] == 'recover-result':
                raise wf.WorkflowError('Lost coordinator acknowledgement')
            return original(store, payload)

        with patch.object(wf, 'reconcile_check', side_effect=lose_ack):
            with self.assertRaisesRegex(wf.WorkflowError, 'Lost coordinator acknowledgement'):
                wf.run_check(fixture.store, request)
        observed = wf.run_check(fixture.store, {**selection, 'action': 'inspect'})
        result = wf.run_check(fixture.store, {
            **selection, 'action': 'reconcile', 'attempt_id': observed['attempt_id'],
        })
        record = result['record']
        self.assertEqual(record['attempt_id'], observed['attempt_id'])
        self.assertEqual(record['result'], 'pass')
        self.assertEqual(record['counts']['discovered'], 1)
        checkout = fixture.store.source_root
        evidence, = record['evidence']
        artifact = checkout / evidence['path']
        self.assertEqual(wf.file_hash(artifact), evidence['sha256'])
        report = json.loads(artifact.read_text())
        self.assertEqual(report['exit_code'], 0)
        self.assertIn('{"before": 1}', report['output'])
        self.assertTrue(report['output'].rstrip().endswith('{"after": 2}'))
        self.assertEqual(wf.run_check(fixture.store, request)['record'], record)
        self.assertEqual((checkout / 'runner-invocations').read_text(), 'run\n')

    def test_static_tap_and_vitest_keep_existing_discovery_rules(self):
        tap = '# tests 2\n# pass 2\n# fail 0\n# skipped 0\n# todo 0\n'
        vitest = json.dumps({
            'success': True, 'numTotalTests': 3, 'numPassedTests': 3,
            'numFailedTests': 0, 'numPendingTests': 0, 'numTodoTests': 0,
        })
        self.assertIsNone(wf.current_target_check_counts('static', 'arbitrary output'))
        self.assertEqual(wf.current_target_check_counts('unit', tap), 2)
        self.assertEqual(wf.local_check_count('unit', tap), 2)
        self.assertEqual(wf.local_check_count('unit', vitest), 3)


if __name__ == '__main__':
    unittest.main()
