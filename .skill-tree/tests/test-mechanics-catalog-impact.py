import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / ".skill-tree/examples/game-design/mechanics-impact"
SPEC = importlib.util.spec_from_file_location("mechanics_impact", FIXTURE / "query.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MechanicsImpactTests(unittest.TestCase):
    def setUp(self):
        self.atlas = json.loads((FIXTURE / "atlas.json").read_text())
        self.expected = json.loads((FIXTURE / "expected.json").read_text())

    def test_exact_impact_deduplicates_and_excludes_unaffected_controls(self):
        result = MODULE.query(self.atlas, self.expected["source"])
        affected = [record["pin"] for record in result["affected"]]
        self.assertEqual(affected, self.expected["affected"])
        self.assertTrue(set(affected).isdisjoint(self.expected["unaffected_controls"]))
        shared_check = result["affected"][0]
        self.assertEqual(len(shared_check["direct_dependencies"]), 2)
        self.assertEqual(shared_check["trace"][0]["to"], self.expected["source"])
        self.assertEqual(shared_check["trace"][-1]["from"], shared_check["pin"])
        self.assertEqual(shared_check["evidence"], "checks/grip.md#corner-grip")

    def test_unresolved_edges_have_explicit_reasons(self):
        result = MODULE.query(self.atlas, self.expected["source"])
        unresolved = {edge["from"]: edge["reason"] for edge in result["unresolved"]}
        self.assertEqual(unresolved, self.expected["unresolved"])
        self.assertTrue(set(unresolved).isdisjoint(row["pin"] for row in result["affected"]))

    def test_old_revision_keeps_its_exact_consumers(self):
        result = MODULE.query(self.atlas, "paper-race/grip-rule@1")
        self.assertEqual([row["pin"] for row in result["affected"]], self.expected["unaffected_controls"])

    def test_unknown_or_foreign_query_cannot_claim_verified_impact(self):
        for pin, reason in (("paper-race/grip-rule@3", "missing-revision"), ("foreign-race/grip-rule@2", "foreign-scope")):
            with self.subTest(pin=pin):
                result = MODULE.query(self.atlas, pin)
                self.assertEqual(result["affected"], [])
                self.assertEqual(result["query_status"], reason)

    def test_acyclic_hierarchy_carries_real_dependency_but_cycle_does_not(self):
        self.atlas["edges"] = [
            edge for edge in self.atlas["edges"]
            if (edge["from"], edge["type"]) != ("paper-race/dock-corner@1", "uses-rule")
        ]
        result = MODULE.query(self.atlas, self.expected["source"])
        dock = next(row for row in result["affected"] if row["pin"] == "paper-race/dock-corner@1")
        self.assertEqual([edge["type"] for edge in dock["trace"]], ["uses-rule", "extends-placement"])
        self.assertEqual([row["pin"] for row in result["affected"]], self.expected["affected"])

    def test_cycle_does_not_extend_an_independently_confirmed_match(self):
        left = "paper-race/cycle-left@1"
        self.atlas["edges"].append({"from": left, "type": "uses-rule", "to": self.expected["source"]})
        result = MODULE.query(self.atlas, self.expected["source"])
        affected = {row["pin"]: row for row in result["affected"]}
        self.assertIn(left, affected)
        self.assertNotIn("paper-race/cycle-right@1", affected)
        self.assertEqual([edge["type"] for edge in affected[left]["trace"]], ["uses-rule"])

    def test_query_result_is_independent_of_input_order(self):
        observed = MODULE.query(self.atlas, self.expected["source"])
        self.atlas["records"].reverse()
        self.atlas["edges"].reverse()
        self.assertEqual(MODULE.query(self.atlas, self.expected["source"]), observed)

    def test_retained_report_matches_fixture_oracle_and_source_digests(self):
        retained = json.loads((FIXTURE / "report.json").read_text())
        self.assertEqual(retained["observed"], MODULE.query(self.atlas, self.expected["source"]))
        self.assertEqual(retained["expected"], self.expected)
        self.assertEqual(retained["source_sha256"], MODULE.source_digests(ROOT))
        self.assertEqual(retained["result_sha256"], MODULE.digest_result(retained["observed"]))


if __name__ == "__main__":
    unittest.main()
