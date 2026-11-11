"""Structural regressions for the scoped narrative continuation fixture."""

import hashlib
import json
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "narrative" / "second-work"
TWO_WORKS = runpy.run_path(str(FIXTURE / "check-two-works.py"), run_name="two_work_fixture")


def packet_for(proposal):
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
            "id": "fixture-reviewer",
            "role": "independent-reviewer",
            "evidence": "Synthetic structural test metadata only.",
        },
        "coverage": [{
            "kind": "continuity",
            "scope": "Later work selection and bound manifest",
            "evidence": ["fixture-reviewed-work.json", "state-ilya-ridge-after-lift"],
        }],
        "findings": [],
    }
    encoded = json.dumps(packet, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":"))
    packet["packet_digest"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return packet


class NarrativeScenarios(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="narrative-scenarios-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_later_state_does_not_rewrite_first_work(self):
        result = TWO_WORKS["qualify"](self.root)
        self.assertNotEqual(result["first_pin"], result["later_manifest"]["canon_pin"]["digest"])
        self.assertEqual(result["shared_identity"]["id"], "character-ilya")
        self.assertEqual(result["adaptation_origin"]["snapshot_digest"], result["first_pin"])
        self.assertEqual(result["adaptation_origin"]["record_id"], "scene-relay")

    def test_cooling_outcome_cannot_supply_the_lift_state(self):
        first, manifest, _ = TWO_WORKS["prepare_fixture"](self.root)
        state_path = self.root / ".narrative" / "records" / "state-ilya-ridge-after-lift.json"
        state = TWO_WORKS["read_json"](state_path)
        self.assertIsNone(TWO_WORKS["inspect_scope"](first, manifest, state))
        manifest["predecessor"]["outcome_ids"] = ["outcome-cooler"]
        finding = TWO_WORKS["inspect_scope"](first, manifest, state)
        self.assertEqual(finding, {
            "code": "incompatible-predecessor-outcome",
            "work_id": "work-ridge-after",
            "state_id": "state-ilya-ridge-after-lift",
            "source_record_id": "quest-ridge",
            "requires": ["outcome-lift"],
            "selected": ["outcome-cooler"],
        })
        manifest["predecessor"]["outcome_ids"].append("outcome-lift")
        with self.assertRaisesRegex(ValueError, "one fixed predecessor outcome"):
            TWO_WORKS["inspect_scope"](first, manifest, state)

    def test_later_role_cannot_use_an_unselected_state(self):
        first, manifest, _ = TWO_WORKS["prepare_fixture"](self.root)
        rejected = TWO_WORKS["invoke"](
            self.root, "propose", "--work", manifest["work_id"], "--continuity",
            manifest["continuity_id"], "--base", first["snapshot"],
            "--ids", "role-ilya-ridge-after-witness",
        )
        self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertIn("Missing normative dependency", rejected.stderr)
        self.assertIn("state-ilya-ridge-after-lift", rejected.stderr)

    def test_changed_reviewed_manifest_prevents_later_acceptance(self):
        first, manifest, identifiers = TWO_WORKS["prepare_fixture"](self.root)
        manifest_path = self.root / "fixture-reviewed-work.json"
        TWO_WORKS["write_json"](manifest_path, manifest)
        initial_bytes = manifest_path.read_bytes()
        proposal = TWO_WORKS["run"](
            self.root, "propose", "--work", manifest["work_id"], "--continuity",
            manifest["continuity_id"], "--base", first["snapshot"],
            "--review-source", manifest_path.name, "--ids", *identifiers,
        )
        packet = packet_for(proposal)
        proposal_path = self.root / "fixture-reviewed-proposal.json"
        packet_path = self.root / "fixture-review-packet.json"
        decision_path = self.root / "fixture-reviewed-decision.json"
        TWO_WORKS["write_json"](proposal_path, proposal)
        TWO_WORKS["write_json"](packet_path, packet)
        TWO_WORKS["write_json"](decision_path, {
            "proposal_digest": proposal["proposal_digest"],
            "review_packet_digest": packet["packet_digest"],
            "decision": "accepted",
            "author": "Synthetic fixture author",
        })
        accept_args = (
            "--proposal", str(proposal_path), "--expected-proposal", proposal["proposal_digest"],
            "--decision", decision_path.name, "--review-packet", packet_path.name,
        )
        manifest["purpose"] = "A changed scope after independent source inspection."
        TWO_WORKS["write_json"](manifest_path, manifest)
        rejected = TWO_WORKS["invoke"](self.root, "accept", *accept_args)
        self.assertEqual(rejected.returncode, 1, rejected.stderr)
        self.assertRegex(rejected.stderr.lower(), r"review.*source|source.*review")
        snapshots = self.root / ".narrative" / "snapshots"
        self.assertEqual({file.stem for file in snapshots.glob("*.json")}, {first["snapshot"]})

        manifest_path.write_bytes(initial_bytes)
        accepted = TWO_WORKS["run"](self.root, "accept", *accept_args)
        self.assertTrue(accepted["created"])
        self.assertNotEqual(accepted["snapshot"], first["snapshot"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
