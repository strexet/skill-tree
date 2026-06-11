import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTOR = ROOT / "skills/skill-tree-implement-next-future-task/scripts/select_prioritized_task.py"
FIXTURES = ROOT / "tests/fixtures/future"


class SelectPrioritizedTaskTests(unittest.TestCase):
    def run_selector(self, name, *args):
        return subprocess.run([sys.executable, str(SELECTOR), str(FIXTURES / name), *args], text=True, capture_output=True)

    def test_first_task_selection(self):
        result = self.run_selector("valid.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("### Add Save Migration Validation", result.stdout)

    def test_named_exact_selection_json(self):
        result = self.run_selector("valid.md", "--name", "Add Save Migration Validation", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["title"], "Add Save Migration Validation")

    def test_case_and_whitespace_normalization(self):
        result = self.run_selector("valid.md", "--name", "  add   save migration validation ")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unicode_normalization(self):
        result = self.run_selector("valid.md", "--name", "Add Save Migration Validation")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_named_task_absent_even_when_only_in_backlog(self):
        result = self.run_selector("named-task-only-in-backlog.md", "--name", "Add Save Migration Validation")
        self.assertEqual(result.returncode, 5)
        self.assertIn("not found", result.stderr)

    def test_duplicate_name_fails(self):
        result = self.run_selector("duplicate-prioritized-names.md", "--name", "duplicate name")
        self.assertEqual(result.returncode, 6)

    def test_empty_prioritized_fails(self):
        result = self.run_selector("empty-prioritized.md")
        self.assertEqual(result.returncode, 4)

    def test_blocked_first_task_fails(self):
        result = self.run_selector("blocking-question.md")
        self.assertEqual(result.returncode, 8)
        self.assertIn("blocking", result.stderr)

    def test_missing_file_fails(self):
        result = subprocess.run([sys.executable, str(SELECTOR), str(FIXTURES / "absent.md")], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
