"""Check the bounded energy fixture against hand-derived outcomes."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/game-design/balance-sweeps"
sys.path.insert(0, str(FIXTURE))
from sweep import run


class BalanceParameterSweepTests(unittest.TestCase):
    def setUp(self):
        self.model = json.loads((FIXTURE / "model.json").read_text())
        self.oracle = json.loads((FIXTURE / "oracle.json").read_text())

    def test_grid_matches_all_eight_independent_controls(self):
        self.assertEqual(len(self.oracle["grid"]), 8)
        self.assertEqual(run(self.model)["grid"], self.oracle["grid"])

    def test_held_out_opportunity_trace(self):
        result = run(self.model)
        self.assertEqual(result["held_out"], self.oracle["held_out"])
        self.assertEqual(result["held_out_traces"], self.oracle["held_out_traces"])

    def test_exact_affordability_and_zero_recharge(self):
        model = self.model | {"costs": [2], "recharges": [0], "holdout": None}
        spent, reserved = run(model)["grid"]
        self.assertEqual(spent[3:], [1, 0, 1])
        self.assertEqual(reserved[3:], [0, 2, 0])

    def test_recharge_saturates_at_capacity(self):
        model = self.model | {"initial_energy": 4, "holdout": self.model["holdout"] | {"opportunities": []}}
        result = run(model)
        self.assertEqual([case[3:] for case in result["held_out"]], [[0, 4, 0], [0, 4, 0]])
        self.assertTrue(all(tick[-1] == 4 for trace in result["held_out_traces"] for tick in trace))

    def test_invalid_bounds_and_ambiguous_inputs(self):
        changes = [
            ({"ticks": 65}, "ticks"),
            ({"initial_energy": 5}, "initial_energy"),
            ({"capacity": True}, "capacity"),
            ({"costs": [0]}, "costs"),
            ({"recharges": [-1]}, "recharges"),
            ({"policies": ["ambiguous@1"]}, "policies"),
            ({"policies": ["keep-one-energy@1"] * 2}, "policies"),
            ({"holdout": self.model["holdout"] | {"opportunities": [1, 1]}}, "opportunities"),
        ]
        for change, message in changes:
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, message):
                run(self.model | change)

    def test_grid_and_total_step_budgets(self):
        big_grid = self.model | {
            "capacity": 32, "costs": list(range(1, 10)), "recharges": [0, 1, 2, 3],
            "holdout": None,
        }
        with self.assertRaisesRegex(ValueError, "grid budget"):
            run(big_grid)
        with self.assertRaisesRegex(ValueError, "step budget"):
            run(big_grid | {"costs": [1, 2, 3, 4], "ticks": 64})

    def test_replay_report_and_source_digests(self):
        kept = json.loads((FIXTURE / "report.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(2):
                subprocess.run(
                    [sys.executable, "-B", str(FIXTURE / "sweep.py"), "--output", str(Path(tmp) / str(index))],
                    check=True,
                )
            first, second = (Path(tmp) / "0").read_bytes(), (Path(tmp) / "1").read_bytes()
        self.assertEqual(first, second)
        current = json.loads(first)
        for packet in (kept, current):
            self.assertEqual(packet["expected"], self.oracle)
            self.assertEqual(packet["actual"], run(self.model))
            self.assertEqual(packet["artifact_sha256"], current["artifact_sha256"])
            for name, digest in packet["source_sha256"].items():
                self.assertEqual(digest, sha256((FIXTURE / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
