"""Check the actual DirectorLanternCarry receipt and selected native evidence."""
import importlib.util
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'director_lantern_carry_verifier', ROOT / '.skill-tree/tests/fixtures/director/verify-unity-lantern.py')
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)
MODE = 'PlayMode'


class DirectorLanternCarryReceiptTests(unittest.TestCase):
    def test_current_compact_receipt(self):
        receipt, *inputs = VERIFIER.receipt_inputs(ROOT, MODE)
        fixture = VERIFIER.verify_compact(receipt, MODE, *inputs)
        self.assertEqual({item['socket'] for item in fixture['wrappers'].values()}, {'GripSocket', 'BeltSocket'})
        receipt['batch']['cases'] = receipt['batch']['cases'][:1]
        with self.assertRaisesRegex(ValueError, 'focused Unity lane and cases'):
            VERIFIER.verify_compact(receipt, MODE, *inputs)

    def test_actual_playmode_evidence(self):
        root = os.environ.get('DIRECTOR_LANTERN_UNITY_EVIDENCE_ROOT')
        if not root:
            self.skipTest('Select the machine-local native report directory to prove the exact Unity run.')
        receipt, *inputs = VERIFIER.receipt_inputs(ROOT, MODE)
        fixture = VERIFIER.verify_compact(receipt, MODE, *inputs)
        self.assertEqual(VERIFIER.verify_native(receipt, MODE, fixture, Path(root).resolve(strict=True)),
                         {'passed': 2, 'failed': 0, 'skipped': 0})


if __name__ == '__main__':
    unittest.main()
