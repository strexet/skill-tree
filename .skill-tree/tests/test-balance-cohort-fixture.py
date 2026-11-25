"""Check cohort counts against independent synthetic controls."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/game-design/balance-cohort"
sys.path.insert(0, str(FIXTURE))
from cohort import analyze


class BalanceCohortFixtureTests(unittest.TestCase):
    def setUp(self):
        self.study = json.loads((FIXTURE / "study.json").read_text())
        self.events = [json.loads(line) for line in (FIXTURE / "events.jsonl").read_text().splitlines()]
        self.oracle = json.loads((FIXTURE / "oracle.json").read_text())
        self.exposure = next(event for event in self.events if event["kind"] == "exposure")
        self.outcome = next(event for event in self.events if event["kind"] == "launch-use")

    def test_pooled_segment_and_standardized_counts(self):
        result = analyze(self.study, self.events)
        self.assertEqual(set(result["arms"]), set(self.oracle))
        for arm, expected in self.oracle.items():
            row = result["arms"][arm]
            for key, value in expected["pooled"].items():
                self.assertEqual(row["pooled"][key], value)
            for segment, counts in expected["segments"].items():
                for key, value in counts.items():
                    self.assertEqual(row["segments"][segment][key], value)
            self.assertAlmostEqual(row["standardized_rate"], expected["standardized_rate"])
            low, high = row["pooled"]["wilson_95"]
            self.assertLess(low, row["pooled"]["rate"])
            self.assertGreater(high, row["pooled"]["rate"])
        self.assertEqual(result["standard_weights"], {"novice": 0.5, "experienced": 0.5})
        self.assertAlmostEqual(result["arms"]["baseline"]["pooled"]["rate"], 0.55)
        self.assertAlmostEqual(result["arms"]["candidate"]["pooled"]["rate"], 17 / 30)
        self.assertEqual(result["allocation"], {"status": "not-applicable", "reason": "observational"})

    def test_identical_duplicate_ids_are_counted_once(self):
        result = analyze(self.study, self.events + [deepcopy(self.exposure), deepcopy(self.outcome)])
        self.assertEqual(result["arms"], analyze(self.study, self.events)["arms"])
        self.assertEqual(result["excluded"]["duplicate_event"], 2)

    def test_conflicting_ids_and_duplicate_observation_unit_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting event ID"):
            analyze(self.study, self.events + [self.outcome | {"tick": 5}])
        with self.assertRaisesRegex(ValueError, "duplicate exposed player"):
            analyze(self.study, self.events + [self.exposure | {"id": "other-exposure"}])

    def test_outcome_without_exposure_and_repeated_outcome(self):
        orphan = self.outcome | {"id": "orphan", "exposure_id": "unknown"}
        repeat = self.outcome | {"id": "second-use"}
        result = analyze(self.study, self.events + [orphan, repeat])
        self.assertEqual(result["arms"], analyze(self.study, self.events)["arms"])
        self.assertEqual(result["excluded"]["outcome_without_exposure"], 1)
        self.assertEqual(result["excluded"]["repeat_outcome"], 1)

    def test_reordered_input_yields_same_canonical_analysis(self):
        actual = analyze(self.study, self.events)
        self.assertEqual(actual, analyze(self.study, list(reversed(self.events))))

    def test_incomplete_window_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "incomplete observation window"):
            analyze(self.study | {"window": self.study["window"] | {"complete": False}}, self.events)

    def test_missing_eligible_segment_prevents_standardization(self):
        altered = [
            event | {"eligible": False} if event.get("arm") == "candidate" and event.get("segment") == "novice"
            else event
            for event in self.events
        ]
        result = analyze(self.study, altered)
        self.assertEqual(result["arms"]["candidate"]["segments"]["novice"]["eligible"], 0)
        self.assertIsNone(result["arms"]["candidate"]["segments"]["novice"]["rate"])
        self.assertIsNone(result["arms"]["candidate"]["standardized_rate"])
        self.assertEqual(result["arms"]["candidate"]["standardization_hold"], "empty segment: novice")
        self.assertEqual(result["excluded"]["ineligible_exposure"], 10)
        self.assertEqual(result["excluded"]["outcome_for_excluded_exposure"], 1)

    def test_build_rule_window_and_pretreatment_scope(self):
        exposures = []
        for name, changes in (
            ("foreign-build", {"build": "other"}),
            ("foreign-rule", {"rule": "other"}),
            ("outside-window", {"tick": 10}),
            ("same-tick-segment", {"segment_tick": 3}),
            ("missing-segment", {"segment": None}),
        ):
            exposures.append(self.exposure | changes | {"id": f"event-{name}", "player": name})
        result = analyze(self.study, self.events + exposures)
        self.assertEqual(result["arms"], analyze(self.study, self.events)["arms"])
        self.assertEqual(result["excluded"]["foreign_build_or_rule"], 2)
        self.assertEqual(result["excluded"]["exposure_outside_window"], 1)
        self.assertEqual(result["excluded"]["unknown_pre_exposure_segment"], 2)

    def test_outcome_must_follow_exposure_in_complete_window(self):
        earlier = self.outcome | {"id": "early", "tick": 2}
        later = self.outcome | {"id": "late", "tick": 10}
        result = analyze(self.study, self.events + [earlier, later])
        self.assertEqual(result["arms"], analyze(self.study, self.events)["arms"])
        self.assertEqual(result["excluded"]["outcome_outside_observation"], 2)

    def test_allocation_requires_randomization_and_explicit_ratios(self):
        with self.assertRaisesRegex(ValueError, "assignment ratios"):
            analyze(self.study | {"design": "randomized"}, self.events)
        randomized = self.study | {"design": "randomized", "assignment_ratios": {"baseline": 0.5, "candidate": 0.5}}
        result = analyze(randomized, self.events)
        self.assertEqual(result["allocation"]["observed"], {"baseline": 20, "candidate": 30})
        self.assertEqual(result["allocation"]["expected"], {"baseline": 25, "candidate": 25})
        self.assertAlmostEqual(result["allocation"]["chi_square"], 2.0)

    def test_retained_report_and_ordered_replay(self):
        retained = json.loads((FIXTURE / "report.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(2):
                subprocess.run(
                    [sys.executable, "-B", str(FIXTURE / "cohort.py"), "--output", str(Path(tmp) / str(index))],
                    check=True,
                )
            first, second = (Path(tmp) / "0").read_bytes(), (Path(tmp) / "1").read_bytes()
        self.assertEqual(first, second)
        current = json.loads(first)
        for packet in (retained, current):
            self.assertEqual(packet["expected"], self.oracle)
            self.assertEqual(packet["actual"], analyze(self.study, self.events))
            self.assertEqual(packet["artifact_sha256"], current["artifact_sha256"])
            for name, digest in packet["source_sha256"].items():
                self.assertEqual(digest, sha256((FIXTURE / name).read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
