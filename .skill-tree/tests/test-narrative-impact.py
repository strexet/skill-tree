"""Behavioral checks for scoped, read-only narrative impact reports."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "common/scripts/narrative-state.py"


class ImpactTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.command("init")

    def command(self, name, *args, status=0, parse=True):
        process = subprocess.run([sys.executable, str(SCRIPT), name, str(self.root), *args],
                                 check=False, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, status, process.stdout + process.stderr)
        return json.loads(process.stdout) if parse else process.stderr

    def json_file(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def draft(self, identifier, depends_on=(), relationships=(), text="Working prose."):
        prefix = ".narrative/records/" + identifier
        (self.root / (prefix + ".md")).write_text(text, encoding="utf-8")
        return self.json_file(prefix + ".json", {"id": identifier, "kind": identifier.split("-")[0],
                                                 "depends_on": list(depends_on),
                                                 "relationships": list(relationships)})

    def accept(self, selected, base=None, retire=()):
        args = ["--work", "work-main", "--continuity", "continuity-main", "--ids", *selected]
        if base is not None:
            args.extend(["--base", base])
        if retire:
            args.extend(["--retire", *retire])
        proposal = self.command("propose", *args)
        path = self.json_file("proposal.json", proposal)
        key = proposal["proposal_digest"]
        self.json_file("decision.json", {"proposal_digest": key, "decision": "accepted", "author": "Fixture author"})
        return self.command("accept", "--proposal", str(path), "--expected-proposal", key,
                            "--decision", "decision.json")["snapshot"]

    def pin(self, work, snapshot):
        path = f"works/{work}.json"
        self.json_file(path, {"schema_version": 1, "work_id": work, "continuity_id": "continuity-main",
                              "canon_pin": {"state": "accepted", "digest": snapshot}})
        return path

    def test_legacy_shape_and_optional_suspected_lanes(self):
        self.draft("law-pack", ["character-ilya"])
        self.draft("character-ilya", ["law-pack"])
        self.draft("scene-relay", ["character-ilya"], [
            {"kind": "mentions", "target": "law-pack", "scope": "station"},
            {"kind": "adapted-from", "target": "scene-absent", "scope": "old account"},
        ])
        self.draft("scene-independent", relationships=[{"kind": "features", "target": "law-pack"}])
        expected = {"scope": "drafts", "ids": ["law-pack"],
                    "affected": ["character-ilya", "scene-relay"], "unresolved": {}}
        self.assertEqual(self.command("impact", "--drafts", "--ids", "law-pack"), expected)
        self.json_file("review/suspected.json", {"links": [
            {"source": "scene-independent", "target": "law-pack", "evidence": "Opening speech",
             "question": "Does the speech rely on the same reserve?", "scope": "pilot"},
        ]})
        self.json_file("review/intent.json", {
            "id": "intent-relay", "source": {"scene": "scene-relay", "beat": "beat-clue"},
            "target": {"scene": "scene-absent"}, "relation": "prepares",
            "scope": {"work": "work-main", "routes": ["route-discover"]},
        })
        args = ["impact", "--drafts", "--ids", "law-pack",
                "--dramatic", "review/intent.json", "--suspected", "review/suspected.json"]
        report = self.command(*args)
        self.assertEqual(report, self.command(*args))
        self.assertEqual({key: report[key] for key in expected}, expected)
        self.assertTrue(report["normative"]["closure_valid"])
        optional = {row["kind"]: row for row in report["optional"]}
        self.assertEqual(optional["mentions"]["source_locator"], ".narrative/records/scene-relay.json")
        self.assertEqual(optional["mentions"]["scope"], "station")
        self.assertEqual(optional["adapted-from"]["target_status"], "unresolved")
        self.assertEqual(optional["features"]["target_status"], "active")
        self.assertEqual(report["dramatic"][0]["beat_resolution"], "unverified")
        self.assertEqual(report["dramatic"][0]["scope_resolution"], "unverified")
        self.assertEqual(report["dramatic"][0]["source_status"], "active")
        self.assertEqual(report["dramatic"][0]["target_status"], "unresolved")
        self.assertEqual(report["suspected"][0]["status"], "unverified")

    def test_dramatic_membership_does_not_resolve_missing_or_incompatible_scope(self):
        self.draft("scene-setup")
        self.draft("scene-payoff")
        link = {"id": "intent-return", "source": {"scene": "scene-setup"},
                "target": {"scene": "scene-payoff"}, "relation": "prepares"}
        for scope in (None, {"work": "work-other", "routes": ["route-absent"]}):
            with self.subTest(scope=scope):
                data = dict(link) if scope is None else dict(link, scope=scope)
                self.json_file("review/intent.json", data)
                report = self.command("impact", "--drafts", "--ids", "scene-setup",
                                      "--dramatic", "review/intent.json")
                row, = report["dramatic"]
                self.assertEqual(row.get("scope"), scope)
                self.assertEqual(row["scope_resolution"], "unverified")
                self.assertEqual(row["source_status"], "active")
                self.assertEqual(row["target_status"], "active")


    def test_old_pin_and_unchanged_dependent(self):
        self.draft("law-pack")
        self.draft("scene-relay", ["law-pack"])
        historical = self.accept(["law-pack", "scene-relay"])
        historical_path = self.root / ".narrative/snapshots" / (historical + ".json")
        before = historical_path.read_bytes()
        self.draft("law-pack", text="Proposed replacement.")
        candidate = self.accept(["law-pack"], base=historical)
        old_pin = self.pin("work-historical", historical)
        current_pin = self.pin("work-current", candidate)
        report = self.command("impact", "--snapshot", candidate, "--ids", "law-pack",
                              "--work-pin", old_pin, "--work-pin", current_pin)
        pins = {row["work"]: row for row in report["work_pins"]}
        self.assertEqual(pins["work-current"]["comparison"], "already-selected")
        self.assertEqual(pins["work-historical"]["historical_pin"], "preserved")
        self.assertEqual(pins["work-historical"]["if_moved"],
                         {"changed_records": ["law-pack"], "unchanged_dependents": ["scene-relay"]})
        self.assertEqual(historical_path.read_bytes(), before)
        self.assertEqual(json.loads((self.root / old_pin).read_text())["canon_pin"]["digest"], historical)

    def test_missing_draft_dependent_is_not_inferred_as_removed(self):
        self.draft("law-pack")
        self.draft("scene-relay", ["law-pack"])
        historical = self.accept(["law-pack", "scene-relay"])
        pin = self.pin("work-historical", historical)
        for suffix in [".json", ".md"]:
            (self.root / (".narrative/records/scene-relay" + suffix)).unlink()
        self.draft("law-pack", text="Proposed replacement.")
        report = self.command("impact", "--drafts", "--ids", "law-pack", "--work-pin", pin)
        item = report["work_pins"][0]
        self.assertEqual(item["comparison"], "draft-scope-unverified")
        self.assertEqual(item["if_moved"]["changed_records"], ["law-pack"])
        self.assertEqual(item["if_moved"]["unavailable_records"], ["scene-relay"])

    def test_retired_optional_and_required_draft_targets_differ(self):
        self.draft("law-legacy")
        self.draft("scene-relay", relationships=[{"kind": "mentions", "target": "law-legacy"}])
        historical = self.accept(["law-legacy", "scene-relay"])
        current = self.accept(["scene-relay"], base=historical, retire=["law-legacy"])
        result = self.command("impact", "--snapshot", current, "--ids", "scene-relay", "--extended")
        self.assertEqual(result["optional"][0]["target_status"], "retired")
        self.assertTrue(result["normative"]["closure_valid"])
        self.draft("scene-relay", ["law-missing"], [{"kind": "mentions", "target": "law-missing"}])
        result = self.command("impact", "--drafts", "--ids", "scene-relay", "--extended", status=1)
        self.assertFalse(result["normative"]["closure_valid"])
        self.assertEqual(result["unresolved"], {"scene-relay": ["law-missing"]})

    def test_external_input_requires_owned_relative_path(self):
        self.draft("law-pack")
        error = self.command("impact", "--drafts", "--ids", "law-pack",
                             "--suspected", "../suspected.json", status=1, parse=False)
        self.assertIn("Repository-relative path required", error)


if __name__ == "__main__":
    unittest.main()
