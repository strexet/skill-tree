"""Behavioral checks for the standalone narrative authoring CLI."""

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "common" / "scripts" / "narrative-state.py"


class NarrativeStateTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.narrative = self.root / ".narrative"
        self.drafts = self.narrative / "records"
        self.snapshots = self.narrative / "snapshots"

    def run_cli(self, command, *args, error=None):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), command, str(self.root), *args],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if error:
            self.assertEqual(process.returncode, 1, process)
            self.assertIn(error, process.stderr)
            return
        self.assertEqual(process.returncode, 0, process.stderr)
        return json.loads(process.stdout)

    def draft(self, identifier, *depends_on, content="A draft."):
        markdown = self.drafts / (identifier + ".md")
        metadata = self.drafts / (identifier + ".json")
        markdown.write_bytes(content.encode("utf-8"))
        metadata.write_bytes(
            json.dumps({
                "id": identifier,
                "kind": identifier.split("-")[0],
                "depends_on": list(depends_on),
            }, indent=2).encode("utf-8") + b"\n"
        )
        return markdown, metadata

    def propose(self, *ids, base=None, retire=(), work="work-one", error=None):
        args = ["--work", work, "--continuity", "continuity-main"]
        if base:
            args += ["--base", base]
        if ids:
            args += ["--ids", *ids]
        if retire:
            args += ["--retire", *retire]
        return self.run_cli("propose", *args, error=error)

    def files(self, proposal):
        proposal_file = self.root / "proposal.json"
        decision_file = self.root / "decision.json"
        proposal_file.write_text(json.dumps(proposal), encoding="utf-8")
        decision_file.write_text(
            json.dumps({
                "proposal_digest": proposal["proposal_digest"],
                "decision": "accepted",
                "author": "Fixture owner",
                "reason": "The test fixture grants a scoped acceptance.",
            }), encoding="utf-8",
        )
        return proposal_file, decision_file

    def accept(self, proposal, *, error=None, decision=None, proposal_file=None):
        return self.run_cli(
            "accept", "--proposal", str(proposal_file or self.root / "proposal.json"),
            "--expected-proposal", proposal["proposal_digest"],
            "--decision", decision or "decision.json", error=error,
        )

    def test_init_creates_structure_and_preserves_existing_draft(self):
        self.run_cli("init")
        self.assertTrue(self.drafts.is_dir(), "Initialization must create the draft directory.")
        self.assertTrue(self.snapshots.is_dir())
        markdown, _ = self.draft("law-memory", content="Existing prose.")
        self.run_cli("init")
        self.assertEqual(markdown.read_bytes(), b"Existing prose.")
        self.assertEqual(list(self.snapshots.iterdir()), [])

    def test_snapshot_resolves_accepted_bytes_after_working_draft_changes(self):
        self.run_cli("init")
        markdown, metadata = self.draft("law-memory", content="Accès autorisé.\r\n")
        original = (markdown.read_bytes(), metadata.read_bytes())
        proposal = self.propose("law-memory")
        _, decision = self.files(proposal)
        snapshot = self.accept(proposal)["snapshot"]
        self.draft("law-memory", content="Altered working copy.")
        context = self.run_cli("context", "--snapshot", snapshot)
        saved = context["records"]["law-memory"]
        self.assertEqual(saved["markdown"].encode("utf-8"), original[0])
        self.assertEqual(saved["metadata"].encode("utf-8"), original[1])
        self.assertEqual(context["decision"], decision.read_text(encoding="utf-8"))
        self.assertEqual(context["entries"]["law-memory"]["revision"], proposal["entries"]["law-memory"]["revision"])
        self.assertEqual(self.accept(proposal)["snapshot"], snapshot)

    def test_future_candidate_checks_edges_and_unchanged_transitive_impact(self):
        self.run_cli("init")
        self.draft("law-memory", "character-mara")
        self.draft("character-mara", "law-memory")
        self.draft("scene-hearing", "character-mara")
        self.draft("quest-witness", "scene-hearing")
        self.propose("law-memory", error="Missing normative dependency")
        draft_impact = self.run_cli("impact", "--drafts", "--ids", "law-memory")
        self.assertEqual(draft_impact["affected"], ["character-mara", "quest-witness", "scene-hearing"])

        first = self.propose("law-memory", "character-mara", "scene-hearing", "quest-witness")
        self.files(first)
        base = self.accept(first)["snapshot"]
        self.draft("law-memory", "character-mara", content="Proposed new law.")
        replacement = self.propose("law-memory", base=base, work="work-two")
        self.assertEqual(replacement["affected"], ["character-mara", "quest-witness", "scene-hearing"])
        self.assertEqual(replacement["work"], "work-two")
        accepted_impact = self.run_cli("impact", "--snapshot", base, "--ids", "law-memory")
        self.assertEqual(accepted_impact["affected"], replacement["affected"])

    def test_context_limits_record_bodies_to_selected_normative_closure(self):
        self.run_cli("init")
        self.draft("law-memory", "character-mara")
        self.draft("character-mara", "law-memory")
        self.draft("scene-hearing", "character-mara")
        self.draft("quest-unrelated")
        proposal = self.propose("law-memory", "character-mara", "scene-hearing", "quest-unrelated")
        self.files(proposal)
        snapshot = self.accept(proposal)["snapshot"]
        context = self.run_cli("context", "--snapshot", snapshot, "--ids", "scene-hearing")
        self.assertEqual(set(context["records"]), {"law-memory", "character-mara", "scene-hearing"})
        self.assertIn("quest-unrelated", context["entries"])
        self.run_cli("context", "--snapshot", snapshot, "--ids", "scene-missing", error="Selected record is missing")

    def test_draft_impact_rejects_orphaned_pairs(self):
        self.run_cli("init")
        markdown, _ = self.draft("law-memory")
        _, sidecar = self.draft("character-mara")
        markdown.unlink()
        sidecar.unlink()
        self.run_cli("impact", "--drafts", "--ids", "law-memory", error="character-mara, law-memory")

    def test_empty_snapshot_pin_does_not_fall_back_to_drafts(self):
        self.run_cli("init")
        self.draft("law-tide")
        self.run_cli("impact", "--snapshot", "", "--ids", "law-tide", error="Expected a SHA-256 snapshot digest")

    def test_tampered_snapshot_has_no_working_draft_fallback(self):
        self.run_cli("init")
        self.draft("law-memory")
        proposal = self.propose("law-memory")
        self.files(proposal)
        snapshot = self.accept(proposal)["snapshot"]
        archive = self.snapshots / (snapshot + ".json")
        value = json.loads(archive.read_text(encoding="utf-8"))
        value["records"]["law-memory"]["markdown"] = "Tampered content."
        archive.write_text(json.dumps(value), encoding="utf-8")
        self.run_cli("context", "--snapshot", snapshot, error="Snapshot record hashes differ")
        self.accept(proposal, error="Snapshot record hashes differ")

    def test_retiring_record_preserves_old_snapshot_and_blocks_live_edges(self):
        self.run_cli("init")
        self.draft("law-memory")
        self.draft("scene-hearing", "law-memory")
        first = self.propose("law-memory", "scene-hearing")
        self.files(first)
        base = self.accept(first)["snapshot"]
        self.propose(base=base, retire=("law-memory",), error="Missing normative dependency")
        self.draft("scene-hearing")
        retirement = self.propose("scene-hearing", base=base, retire=("law-memory",))
        self.files(retirement)
        retired = self.accept(retirement)["snapshot"]
        context = self.run_cli("context", "--snapshot", retired)
        self.assertEqual(context["retired"], ["law-memory"])
        self.assertNotIn("law-memory", context["records"])
        self.assertIn("law-memory", self.run_cli("context", "--snapshot", base)["records"])

    def test_changed_proposal_and_draft_block_acceptance_without_partial_snapshot(self):
        self.run_cli("init")
        markdown, _ = self.draft("law-memory")
        proposal = self.propose("law-memory")
        proposal_file, _ = self.files(proposal)
        changed = {**proposal, "work": "work-two"}
        proposal_file.write_text(json.dumps(changed), encoding="utf-8")
        self.accept(proposal, error="Proposal digest mismatch")
        self.files(proposal)
        markdown.write_text("Changed after review.", encoding="utf-8")
        self.accept(proposal, error="Proposal sources changed")
        self.assertEqual(list(self.snapshots.iterdir()), [])

    def test_path_escape_and_symlinked_owned_inputs_are_rejected(self):
        self.run_cli("init")
        markdown, _ = self.draft("law-memory")
        proposal = self.propose("law-memory")
        _, decision_file = self.files(proposal)
        for decision in ("../decision.json", "review/Z:/decision.json", "review/decision.json:notes"):
            with self.subTest(decision=decision):
                self.accept(proposal, decision=decision, error="Repository-relative path")
        markdown.unlink()
        markdown.symlink_to(decision_file)
        self.accept(proposal, error="Symlinks are unsupported")
        self.assertEqual(list(self.snapshots.iterdir()), [])

    def test_parallel_accept_of_same_packet_keeps_one_verified_snapshot(self):
        self.run_cli("init")
        self.draft("law-memory")
        proposal = self.propose("law-memory")
        self.files(proposal)
        with ThreadPoolExecutor(max_workers=4) as pool:
            snapshots = list(pool.map(lambda _: self.accept(proposal)["snapshot"], range(4)))
        self.assertEqual(len(set(snapshots)), 1)
        self.assertEqual([path.name for path in self.snapshots.iterdir()], [snapshots[0] + ".json"])
        self.assertEqual(set(self.run_cli("context", "--snapshot", snapshots[0])["records"]), {"law-memory"})


if __name__ == "__main__":
    unittest.main()
