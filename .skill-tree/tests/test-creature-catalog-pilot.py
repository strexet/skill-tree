"""Exercise portable validation of the accepted creature pilot evidence."""

import csv
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
from shutil import copyfile
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / '.skill-tree/examples/3d/recipes/character/creatures/verify-catalog-pilot.py'
SPEC = importlib.util.spec_from_file_location('catalog_pilot', SCRIPT)
PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PILOT)
CONTACT = PILOT.BASE / 'pets-r017-contact'


class CreatureCatalogPilotTests(unittest.TestCase):
    def test_clean_package_replays_recorded_paw_measurements(self):
        result = PILOT.verify_package(ROOT)
        self.assertEqual(result['evidence_kind'], 'retained-native-archive')
        self.assertEqual(result['coverage']['native_samples'], 4736)
        self.assertEqual(result['coverage']['all_cases'], 48)
        self.assertEqual(result['coverage']['required_contacts'], 32)

    def test_cannot_replace_both_csv_and_adjacent_receipt(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            _, pins = PILOT.closeout_pins(ROOT)
            for relative in [*pins, PILOT.BASE / 'pilot-closeout.json']:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                copyfile(ROOT / relative, target)
            data = root / CONTACT / 'paw-1-samples.csv'
            data.write_text(data.read_text().splitlines()[0] + '\n')
            path = root / CONTACT / 'placement-reconciliation.json'
            report = PILOT.read(path)
            report['inputs']['paw-1-samples.csv']['sha256'] = sha256(data.read_bytes()).hexdigest()
            path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'Changed artifact'):
                PILOT.verify_package(root)

    def test_csv_requires_unique_complete_finite_samples(self):
        coverage = PILOT.read(ROOT / CONTACT / 'paw-coverage.json')['specimens']
        specimens = {entry['id']: entry for entry in coverage}
        with (ROOT / CONTACT / 'paw-1-samples.csv').open(newline='') as handle:
            reader = csv.DictReader(handle)
            columns, rows = reader.fieldnames, list(reader)
        with TemporaryDirectory() as temporary:
            candidate = Path(temporary) / 'samples.csv'
            for inputs, reason in (
                ([], 'Incomplete native paw sample coverage'),
                ([rows[0], rows[0]], 'Duplicate or non-finite'),
                ([{**rows[0], 'x_m': 'inf'}], 'Duplicate or non-finite'),
            ):
                with self.subTest(reason=reason):
                    with candidate.open('w', newline='') as handle:
                        writer = csv.DictWriter(handle, fieldnames=columns)
                        writer.writeheader()
                        writer.writerows(inputs)
                    with self.assertRaisesRegex(ValueError, reason):
                        PILOT.read_pose_samples(candidate, specimens)

    def test_local_native_replay_requires_opt_in_and_queue(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--project', str(ROOT),
                                 '--control', 'motion'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Use --control package for a clean checkout', result.stderr)


if __name__ == '__main__':
    unittest.main()
