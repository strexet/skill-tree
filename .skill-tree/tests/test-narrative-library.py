"""Read-only inventory of working, accepted and retired narrative records."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "common/scripts/narrative-state.py"


class LibraryTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cli("init")
        self.records = self.root / ".narrative/records"

    def cli(self, command, *args, error=None):
        result = subprocess.run([sys.executable, str(SCRIPT), command, str(self.root), *args],
                                capture_output=True, text=True, timeout=10)
        if error:
            self.assertEqual(result.returncode, 1, result)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def pair(self, name, identifier, text):
        (self.records / f"{name}.md").write_text(text)
        (self.records / f"{name}.json").write_text(json.dumps({
            "id": identifier, "kind": "law", "depends_on": [],
        }))

    def accept(self, *extra):
        proposal = self.cli("propose", "--work", "work-ridge", "--continuity", "continuity-ridge", *extra)
        path = self.root / "proposal.json"
        path.write_text(json.dumps(proposal))
        (self.root / "decision.json").write_text(json.dumps({
            "author": "Fixture owner", "decision": "accepted",
            "proposal_digest": proposal["proposal_digest"],
        }))
        return self.cli("accept", "--proposal", str(path), "--decision", "decision.json",
                        "--expected-proposal", proposal["proposal_digest"])["snapshot"]

    def test_inventory_is_derived_and_preserves_history(self):
        self.pair("renamed-law", "law-ridge", "The lift runs once.")
        first = self.accept("--ids", "law-ridge")
        second = self.accept("--base", first, "--retire", "law-ridge")
        self.pair("renamed-law", "law-ridge", "The draft changes the rule.")
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        working = self.cli("inventory", "--drafts")["records"][0]
        accepted = self.cli("inventory", "--snapshot", first)
        retired = self.cli("inventory", "--snapshot", second)["records"][0]
        self.assertEqual(working["markdown"], ".narrative/records/renamed-law.md")
        self.assertEqual(working["status"], "draft")
        self.assertEqual(accepted["decision_path"], "decision.json")
        self.assertEqual(accepted["records"][0]["status"], "accepted")
        self.assertNotEqual(working["revision"], accepted["records"][0]["revision"])
        self.assertEqual(retired, {"id": "law-ridge", "status": "retired"})
        self.assertEqual(accepted, self.cli("inventory", "--snapshot", first))
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_unknown_pin_never_selects_drafts(self):
        self.pair("law-ridge", "law-ridge", "Working.")
        self.cli("inventory", "--snapshot", "a" * 64, error="Required regular file is missing")

    def test_duplicate_working_id_never_selects_a_pair(self):
        self.pair("one", "law-ridge", "One.")
        self.pair("two", "law-ridge", "Two.")
        self.cli("inventory", "--drafts", error="Duplicate draft ID")


if __name__ == "__main__":
    unittest.main()
