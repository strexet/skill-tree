import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'common/scripts/narrative-route-check.py'
FIXTURES = ROOT / 'examples/narrative'


class RouteContractTests(unittest.TestCase):
    def invoke(self, path):
        run = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                             check=False, capture_output=True, text=True, timeout=10)
        return run.returncode, json.loads(run.stdout)

    def fixture(self, directory, file='route-traces.json'):
        for name in ['route-contract.example.json', 'state-registry.example.json', file]:
            shutil.copyfile(FIXTURES / name, directory / name)
        return directory / file

    def test_expected_suite_and_unchanged_sources(self):
        names = ['route-contract.example.json', 'state-registry.example.json', 'route-traces.json']
        before = {name:hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() for name in names}
        code, report = self.invoke(FIXTURES / 'route-traces.json')
        self.assertEqual(code, 0, report)
        self.assertEqual(report['scope'], 'declared-traces-only')
        self.assertEqual(len(report['traces']), 16)
        self.assertEqual(before, {name:hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest() for name in names})

    def test_missing_state_distinct_from_false(self):
        code, report = self.invoke(FIXTURES / 'route-traces.json')
        self.assertEqual(code, 0)
        observed = {row['id']: row['observed_diagnostic'] for row in report['traces']}
        self.assertEqual(observed['missing-state']['code'], 'unavailable-state')
        self.assertEqual(observed['unavailable-actor']['code'], 'unavailable-action')
        self.assertIsNone(observed['ridge-skip-lift'])

    def test_bounded_revisit_distinct_from_unproductive_loop(self):
        code, report = self.invoke(FIXTURES / 'route-traces.json')
        self.assertEqual(code, 0)
        observed = {row['id']: row['observed_diagnostic'] for row in report['traces']}
        self.assertIsNone(observed['ridge-restore-repeat'])
        self.assertEqual(observed['unproductive-loop']['code'], 'visit-limit')
        self.assertEqual(observed['duplicate-receipt']['code'], 'repeated-unique-effect')

    def test_malformed_compound_guard(self):
        with tempfile.TemporaryDirectory() as work:
            path = self.fixture(Path(work), 'route-contract.example.json')
            contract = json.loads(path.read_text())
            leaf = {'key':'crew_rescued','op':'eq','value':True}
            contract['nodes']['scene-ridge-station']['actions']['discover-log']['when'] = {'all':[leaf], 'any':[leaf]}
            path.write_text(json.dumps(contract))
            code, report = self.invoke(path)
            self.assertEqual(code, 2)
            self.assertEqual(report['diagnostic']['code'], 'malformed-contract')

    def test_unexpected_result_reports_route_and_step(self):
        with tempfile.TemporaryDirectory() as work:
            path = self.fixture(Path(work), 'route-contract.example.json')
            contract = json.loads(path.read_text())
            contract['traces'][0]['expected_state']['medicine_cold'] = True
            path.write_text(json.dumps(contract))
            code, report = self.invoke(path)
            self.assertEqual(code, 1)
            observed = report['traces'][0]['observed_diagnostic']
            self.assertEqual(observed['code'], 'state-mismatch')
            self.assertEqual(observed['route'], 'ridge-discover-lift')
            self.assertEqual(observed['step'], 3)

    def test_preexisting_unique_grant_remains_claimed(self):
        with tempfile.TemporaryDirectory() as work:
            path = self.fixture(Path(work), 'route-contract.example.json')
            contract = json.loads(path.read_text())
            contract['traces'][0]['initial_state']['incident_receipts'] = 1
            path.write_text(json.dumps(contract))
            code, report = self.invoke(path)
            self.assertEqual(code, 1)
            observed = report['traces'][0]['observed_diagnostic']
            self.assertEqual(observed['code'], 'repeated-unique-effect')
            self.assertEqual(observed['step'], 2)

    def test_nonportable_locator_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            path = self.fixture(Path(work), 'route-contract.example.json')
            contract = json.loads(path.read_text())
            contract['state_registry'] = '../outside.json'
            path.write_text(json.dumps(contract))
            code, report = self.invoke(path)
            self.assertEqual(code, 2)
            self.assertEqual(report['diagnostic']['code'], 'malformed-contract')


if __name__ == '__main__':
    unittest.main()
