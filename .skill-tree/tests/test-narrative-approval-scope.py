"""Bound proposal and approval integrity across current and archived sources."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "common/scripts/narrative-state.py"


def packet_hash(packet):
    body = {key: value for key, value in packet.items() if key != "packet_digest"}
    content = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


class ApprovalScopeTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.cli("init")
        records = self.root / ".narrative/records"
        (records / "event-trip.md").write_text("The lead shorted before the storm.\n")
        (records / "event-trip.json").write_text(
            json.dumps({"id": "event-trip", "kind": "event", "depends_on": []})
        )
        (self.root / "work.md").write_text("The selector is available.\n")
        (self.root / "quest.ink").write_text("-> END\n")

    def cli(self, command, *args, error=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), command, str(self.root), *args],
            capture_output=True, text=True, timeout=10,
        )
        if error is not None:
            self.assertEqual(result.returncode, 1, result)
            self.assertIn(error, result.stderr)
            return None
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def propose(self, *args, error=None):
        return self.cli("propose", "--work", "work-ridge", "--continuity", "continuity-ridge",
                        "--ids", "event-trip", *args, error=error)

    def write_json(self, path, value):
        (self.root / path).write_text(json.dumps(value))

    def packet_for(self, proposal, **changes):
        packet = {
            "schema": 1,
            "proposal_digest": proposal["proposal_digest"],
            "work": proposal["work"],
            "continuity": proposal["continuity"],
            "base": proposal["base"],
            "record_scope": {
                "selected": proposal["ids"],
                "retired": proposal["retire"],
                "unchanged_dependents": proposal["affected"],
            },
            "review_sources": proposal["review_sources"],
            "reviewer": {
                "id": "fixture-reviewer", "role": "independent-reviewer",
                "evidence": "Synthetic review fixture.",
            },
            "coverage": [{
                "kind": "source-inspection", "scope": "Selector timing",
                "evidence": ["work.md", "quest.ink"],
            }],
            "findings": [],
        }
        packet.update(changes)
        packet["packet_digest"] = packet_hash(packet)
        return packet

    def prepare(self, **packet_changes):
        proposal = self.propose("--review-source", "work.md", "--review-source", "quest.ink")
        packet = self.packet_for(proposal, **packet_changes)
        self.write_json("proposal.json", proposal)
        self.write_json("packet.json", packet)
        self.write_json("decision.json", {
            "author": "Synthetic owner", "decision": "accepted",
            "proposal_digest": proposal["proposal_digest"],
            "review_packet_digest": packet["packet_digest"],
        })
        return proposal, packet

    def accept(self, proposal, packet="packet.json", error=None):
        packet_args = ["--review-packet", packet] if packet is not None else []
        return self.cli("accept", "--proposal", str(self.root / "proposal.json"),
                        "--expected-proposal", proposal["proposal_digest"], "--decision", "decision.json",
                        *packet_args, error=error)

    def snapshots(self):
        return list((self.root / ".narrative/snapshots").iterdir())

    def test_bound_acceptance_and_exact_retry_after_external_drift(self):
        proposal, packet = self.prepare()
        self.assertEqual(proposal["schema"], 2)
        self.assertEqual([row["path"] for row in proposal["review_sources"]], ["quest.ink", "work.md"])
        accepted = self.accept(proposal)
        archive = self.snapshots()[0]
        original = archive.read_bytes()
        (self.root / "work.md").write_text("A later revision has different timing.\n")
        self.assertEqual(self.accept(proposal), {"snapshot": accepted["snapshot"], "created": False})
        context = self.cli("context", "--snapshot", accepted["snapshot"])
        self.assertEqual(context["review_packet"]["packet_digest"], packet["packet_digest"])
        self.assertEqual(archive.read_bytes(), original)

    def test_changed_or_missing_bound_source_blocks_publication(self):
        for drift in ("changed", "missing"):
            with self.subTest(drift=drift):
                (self.root / "quest.ink").write_text("-> END\n")
                proposal, _ = self.prepare()
                if drift == "changed":
                    (self.root / "quest.ink").write_text("A different line.\n-> END\n")
                else:
                    (self.root / "quest.ink").unlink()
                self.accept(proposal, error="review source")
                self.assertEqual(self.snapshots(), [])

    def test_missing_packet_or_wrong_owner_binding_blocks_publication(self):
        proposal, _ = self.prepare()
        self.accept(proposal, packet=None, error="requires a review packet")
        decision = json.loads((self.root / "decision.json").read_text())
        decision["review_packet_digest"] = "0" * 64
        self.write_json("decision.json", decision)
        self.accept(proposal, error="accept this review packet")
        self.assertEqual(self.snapshots(), [])

    def test_open_blocker_and_tampered_packet_fail_closed(self):
        finding = {
            "id": "finding-time", "scope": "in-scope", "severity": "blocker",
            "status": "open", "evidence": ["quest.ink"],
        }
        proposal, packet = self.prepare(findings=[finding])
        self.accept(proposal, error="Open in-scope blocker")
        packet["findings"] = []
        self.write_json("packet.json", packet)
        self.accept(proposal, error="Review packet digest mismatch")
        self.assertEqual(self.snapshots(), [])

    def test_resolved_blocker_requires_reason_and_out_of_scope_note_is_allowed(self):
        finding = {
            "id": "finding-time", "scope": "in-scope", "severity": "blocker",
            "status": "resolved", "evidence": ["quest.ink"],
        }
        proposal, _ = self.prepare(findings=[finding])
        self.accept(proposal, error="requires a resolution")
        finding["resolution"] = "The selector line and event timing agree."
        proposal, _ = self.prepare(findings=[finding, {
            "id": "finding-unrelated", "scope": "out-of-scope", "severity": "note",
            "status": "open", "evidence": ["work.md"],
        }])
        self.assertTrue(self.accept(proposal)["created"])

    def test_duplicate_escaping_and_symlink_sources_are_refused(self):
        self.propose("--review-source", "work.md", "--review-source", "work.md", error="Duplicate review source")
        self.propose("--review-source", "../outside.md", error="Repository-relative path required")
        (self.root / "work-alias.md").symlink_to(self.root / "work.md")
        self.propose("--review-source", "work-alias.md", error="Symlinks are unsupported")
        self.assertEqual(self.snapshots(), [])

    def test_archive_rejects_tampered_packet(self):
        proposal, _ = self.prepare()
        accepted = self.accept(proposal)
        archive = self.snapshots()[0]
        value = json.loads(archive.read_text())
        value["review_packet"]["work"] = "work-other"
        archive.write_text(json.dumps(value))
        self.cli("context", "--snapshot", accepted["snapshot"], error="Review packet digest mismatch")

    def test_packet_drift_during_staging_prevents_publish(self):
        proposal, packet = self.prepare()
        spec = importlib.util.spec_from_file_location("narrative_state_scope", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original = module.os.fsync

        def change_packet(fd):
            original(fd)
            packet["coverage"] = []
            self.write_json("packet.json", packet)

        project = module.Project(self.root)
        with patch.object(module.os, "fsync", side_effect=change_packet):
            with self.assertRaisesRegex(module.NarrativeError, "Review packet changed before publication"):
                project.accept(self.root / "proposal.json", proposal["proposal_digest"],
                               "decision.json", "packet.json")
        self.assertEqual(self.snapshots(), [])


if __name__ == "__main__":
    unittest.main()
