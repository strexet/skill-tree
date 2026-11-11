"""Stable draft identity and supported filesystem moves."""

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "common/scripts/narrative-state.py"


class RecordDiscoveryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.records = self.root / ".narrative/records"
        self.cli("init")

    def cli(self, command, *args, error=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, str(self.root), *args],
            capture_output=True, text=True, timeout=10,
        )
        if error:
            self.assertEqual(result.returncode, 1, result)
            self.assertIn(error, result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def pair(self, name, identifier):
        markdown = self.records / f"{name}.md"
        sidecar = self.records / f"{name}.json"
        markdown.parent.mkdir(parents=True, exist_ok=True)
        markdown.write_text("The tide is visible.\n")
        sidecar.write_text(json.dumps({"id": identifier, "kind": "law", "depends_on": []}))
        return markdown, sidecar

    def proposal(self, error=None):
        return self.cli("propose", "--work", "work-ridge", "--continuity", "continuity-ridge",
                        "--ids", "law-tide", error=error)

    def test_move_preserves_proposal_and_accepted_snapshot_bytes(self):
        pair = self.pair("law-tide", "law-tide")
        original = self.proposal()
        proposal = self.root / "proposal.json"
        proposal.write_text(json.dumps(original))
        (self.root / "decision.json").write_text(json.dumps({
            "author": "Fixture owner", "decision": "accepted",
            "proposal_digest": original["proposal_digest"],
        }))
        accepted = self.cli("accept", "--proposal", str(proposal), "--decision", "decision.json",
                            "--expected-proposal", original["proposal_digest"])
        pin = accepted["snapshot"]
        archive = self.root / f".narrative/snapshots/{pin}.json"
        before = archive.read_bytes()
        folder = self.records / "renamed"
        folder.mkdir()
        for path in pair:
            path.rename(folder / f"shore-rule{path.suffix}")
        self.assertEqual(self.proposal(), original)
        self.assertEqual(self.cli("impact", "--drafts", "--ids", "law-tide")["ids"], ["law-tide"])
        context = self.cli("context", "--snapshot", pin, "--ids", "law-tide")
        self.assertEqual(context["records"]["law-tide"]["markdown"], "The tide is visible.\n")
        self.assertEqual(archive.read_bytes(), before)

    def test_duplicate_id_across_paths_is_ambiguous(self):
        self.pair("law-tide", "law-tide")
        self.pair("nested/duplicate", "law-tide")
        self.proposal(error="Duplicate draft ID")

    def test_partial_nested_pair_is_reported(self):
        _, sidecar = self.pair("nested/moved", "law-tide")
        sidecar.unlink()
        self.cli("impact", "--drafts", "--ids", "law-tide", error="nested/moved")

    def test_symlinked_directory_is_not_discovered(self):
        self.pair("law-tide", "law-tide")
        (self.records / "foreign").symlink_to(self.root, target_is_directory=True)
        self.proposal(error="Symlinks are unsupported")


if __name__ == "__main__":
    unittest.main()
