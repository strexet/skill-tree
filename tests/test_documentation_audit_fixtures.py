import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "documentation-audit"


class DocumentationAuditFixtureTests(unittest.TestCase):
    def test_required_audit_fixture_cases_exist(self):
        expected = {
            "well-documented-repository.md",
            "missing-required-document.md",
            "stale-source-path.md",
            "renamed-skill-reference.md",
            "future-section-in-features.md",
            "implemented-work-in-future.md",
            "contradictory-document-claims.md",
            "historical-without-status.md",
            "duplicate-backlog-issue.md",
            "confirmed-bug-discovered.md",
        }
        actual = {path.name for path in FIXTURES.glob("*.md")}
        self.assertEqual(actual, expected)

    def test_each_audit_fixture_declares_expected_action(self):
        for path in FIXTURES.glob("*.md"):
            with self.subTest(fixture=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("Expected audit action:", text)


if __name__ == "__main__":
    unittest.main()
