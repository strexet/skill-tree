from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".skill-tree/examples/game-design/mechanics-exchange"
SPEC = importlib.util.spec_from_file_location("mechanics_exchange", FIXTURE / "catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MechanicsExchangeTests(unittest.TestCase):
    def setUp(self):
        self.expected = json.loads((FIXTURE / "expected.json").read_text())
        self.store = Path(self.enterContext(TemporaryDirectory()))
        self.batch = MODULE.initial_batch(ROOT)

    def seed(self):
        return MODULE.import_batch(self.store, self.batch, expected_active=None)["active"]

    def snapshot(self, active):
        directory = self.store / "versions" / active
        return {path.name: path.read_bytes() for path in directory.iterdir()}

    def test_export_uses_exact_markdown_records(self):
        records = {row["pin"]: row for row in self.batch["records"]}
        self.assertEqual(sorted(records), self.expected["initial_pins"])
        for record in records.values():
            locator = record["locator"]
            self.assertEqual(len(locator["sha256"]), 64)
            self.assertTrue((ROOT / locator["path"]).is_file())
        aliases = records["skill-tree-mechanics/bounded-reserve@1"]["aliases"]
        self.assertIn({"language": "es", "label": "reserva limitada", "context": ""}, aliases)
        charge = [alias["context"] for alias in aliases if alias["label"] == "charge"]
        self.assertEqual(charge, ["resource vocabulary"])

    def test_seed_and_repeat_preserve_all_bytes_and_receipts(self):
        active = self.seed()
        before = self.snapshot(active)
        pointer = (self.store / "active").read_bytes()
        replay = MODULE.import_batch(self.store, self.batch, expected_active=None)
        self.assertEqual(replay, {"status": "replayed", "active": active, "batch_id": "seed-v1"})
        self.assertEqual(self.snapshot(active), before)
        self.assertEqual((self.store / "active").read_bytes(), pointer)
        self.assertEqual(len(list((self.store / "versions").iterdir())), 1)

    def test_structural_and_semantic_faults_are_distinct(self):
        bad_shape = deepcopy(self.batch)
        bad_shape["records"][0]["aliases"] = {}
        with self.assertRaisesRegex(MODULE.ShapeError, "invalid-shape"):
            MODULE.import_batch(self.store, bad_shape, expected_active=None)
        with self.assertRaisesRegex(MODULE.ShapeError, "batch identity"):
            MODULE.validate_structure(dict(self.batch, batch_id=""))
        bad_pin = deepcopy(self.batch)
        bad_pin["overlay"]["placements"][0]["record_pin"] = "paper-race-exchange/combined-boost@9"
        MODULE.validate_structure(bad_pin)
        with self.assertRaisesRegex(MODULE.Conflict, "invalid-revision"):
            MODULE.import_batch(self.store, bad_pin, expected_active=None)
        self.assertIsNone(MODULE.active_version(self.store))

    def test_initial_import_rejects_forged_markdown_authority_without_publishing(self):
        for corrupt_body, corrupt_pin in ((True, True), (True, False), (False, True)):
            with self.subTest(body=corrupt_body, pin=corrupt_pin):
                forged = deepcopy(self.batch)
                if corrupt_body:
                    forged["records"][1]["body"] = "Unreviewed replacement"
                if corrupt_pin:
                    forged["records"][1]["locator"]["sha256"] = "0" * 64
                with self.assertRaisesRegex(MODULE.Conflict, "source-authority-mismatch"):
                    MODULE.import_batch(self.store, forged, expected_active=None)
                self.assertIsNone(MODULE.active_version(self.store))
                self.assertFalse((self.store / "versions").exists())

    def test_redirect_cycle_rejects_migration_with_unchanged_bytes(self):
        active = self.seed()
        before = self.snapshot(active)
        active_pointer = (self.store / "active").read_bytes()
        migration = MODULE.migration_batch()
        first, second = "paper-race-exchange/reveal-duplicate@1", self.expected["merge_redirect"]
        migration["redirects"] = [
            {"from": first, "kind": "merge", "targets": [second], "decision": None},
            {"from": second, "kind": "merge", "targets": [first], "decision": None},
        ]
        with self.assertRaisesRegex(MODULE.Conflict, "redirect-cycle"):
            MODULE.import_batch(self.store, migration, expected_active=active)
        self.assertEqual(self.snapshot(active), before)
        self.assertEqual((self.store / "active").read_bytes(), active_pointer)
        self.assertEqual(len(list((self.store / "versions").iterdir())), 1)

    def test_redirect_cycle_includes_edges_accepted_by_earlier_batch(self):
        initial = self.seed()
        first = MODULE.migration_batch()
        first["redirects"] = first["redirects"][:1]
        current = MODULE.import_batch(self.store, first, expected_active=initial)["active"]
        earlier = self.snapshot(current)
        second = MODULE.migration_batch()
        second["batch_id"] = "editorial-v3"
        second["redirects"] = [{"from": first["redirects"][0]["targets"][0], "kind": "merge",
                                "targets": [first["redirects"][0]["from"]], "decision": None}]
        with self.assertRaisesRegex(MODULE.Conflict, "redirect-cycle"):
            MODULE.import_batch(self.store, second, expected_active=current)
        self.assertEqual(MODULE.active_version(self.store), current)
        self.assertEqual(self.snapshot(current), earlier)
        self.assertEqual(len(list((self.store / "versions").iterdir())), 2)

    def test_changed_bytes_under_exact_batch_or_record_identity_are_rejected(self):
        active = self.seed()
        old = self.snapshot(active)
        revised = deepcopy(self.batch)
        revised["records"][0]["body"] += " conflicting edit"
        with self.assertRaisesRegex(MODULE.Conflict, "batch-content-conflict"):
            MODULE.import_batch(self.store, revised, expected_active=active)
        revised["batch_id"] = "rewrites-immutable-seed"
        with self.assertRaisesRegex(MODULE.Conflict, "record-revision-conflict"):
            MODULE.import_batch(self.store, revised, expected_active=active)
        self.assertEqual(self.snapshot(active), old)
        self.assertEqual(MODULE.active_version(self.store), active)

    def test_disposable_migration_requires_split_decision_and_pins_prior_revision(self):
        active = self.seed()
        migration = MODULE.migration_batch()
        migration["redirects"][1]["decision"] = None
        with self.assertRaisesRegex(MODULE.Conflict, "ambiguous-split"):
            MODULE.import_batch(self.store, migration, expected_active=active)
        migration = MODULE.migration_batch()
        applied = MODULE.import_batch(self.store, migration, expected_active=active)["active"]
        state = MODULE.load_version(self.store, applied)
        previous = MODULE.load_version(self.store, active)
        self.assertEqual(state["catalog"]["records"], previous["catalog"]["records"])
        self.assertEqual(MODULE.recommended_pin(state, "paper-race-exchange/reveal-duplicate@1"),
                         self.expected["merge_redirect"])
        self.assertEqual(MODULE.recommended_pin(state, self.expected["historical_placement_pin"]),
                         self.expected["split_redirect"])
        self.assertEqual(state["overlay"]["placements"][0]["record_pin"], self.expected["historical_placement_pin"])
        self.assertEqual([row["term"] for row in state["vocabulary"]], self.expected["migration_vocabulary"])

    def test_failed_publish_and_rollback_preserve_complete_version_bytes(self):
        active = self.seed()
        before = self.snapshot(active)
        migration = MODULE.migration_batch()
        with self.assertRaisesRegex(MODULE.Conflict, "stale-active-version"):
            MODULE.import_batch(self.store, migration, expected_active="0" * 64)
        replace = MODULE.os.replace

        def fail_pointer(src, dest):
            if dest == self.store / "active":
                raise OSError("fixture interruption before active switch")
            return replace(src, dest)

        with patch.object(MODULE.os, "replace", fail_pointer):
            with self.assertRaisesRegex(OSError, "interruption"):
                MODULE.import_batch(self.store, migration, expected_active=active)
        self.assertEqual(MODULE.active_version(self.store), active)
        self.assertEqual(self.snapshot(active), before)
        migrated = MODULE.import_batch(self.store, migration, expected_active=active)["active"]
        self.assertNotEqual(active, migrated)
        MODULE.rollback(self.store, expected_active=migrated, restore=active)
        self.assertEqual(MODULE.active_version(self.store), active)
        self.assertEqual(self.snapshot(active), before)
        self.assertEqual(MODULE.load_version(self.store, active)["catalog"]["redirects"], {})

    def test_retained_report_matches_observed_controls_and_sources(self):
        retained = json.loads((FIXTURE / "report.json").read_text())
        current = MODULE.make_report(ROOT)
        self.assertEqual(retained["observed"], current["observed"])
        self.assertEqual(retained["expected"], self.expected)
        self.assertEqual(retained["source_sha256"], current["source_sha256"])
        self.assertEqual(retained["output_sha256"], current["output_sha256"])
        self.assertEqual(sorted(retained["observed"]["invalid_controls"]),
                         sorted(self.expected["invalid_controls"]))


if __name__ == "__main__":
    unittest.main()
