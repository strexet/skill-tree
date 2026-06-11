import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "skills/skill-tree-process-future-pending/scripts/validate_future_document.py"
FIXTURES = ROOT / "tests/fixtures/future"


class FutureValidatorTests(unittest.TestCase):
    def run_validator(self, name, *args):
        return subprocess.run([sys.executable, str(VALIDATOR), str(FIXTURES / name), *args], text=True, capture_output=True)

    def test_valid_future_passes(self):
        result = self.run_validator("valid.md", "--strict")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_questions_fails(self):
        result = self.run_validator("missing-questions.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Questions and required clarifications", result.stderr)

    def test_duplicate_prioritized_names_fail(self):
        result = self.run_validator("duplicate-prioritized-names.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate prioritized task name", result.stderr)

    def test_empty_prioritized_is_structurally_valid(self):
        result = self.run_validator("empty-prioritized.md")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_blocking_question_status_consistency_passes(self):
        result = self.run_validator("blocking-question.md")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_unresolved_questions_form_passes(self):
        result = self.run_validator("no-unresolved-questions.md")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_malformed_queue_order_fails(self):
        result = self.run_validator("malformed-queue-order.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("queue order", result.stderr)


if __name__ == "__main__":
    unittest.main()
