import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_skill_references.py"


def load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_skill_references", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ReferenceSyncTests(unittest.TestCase):
    def test_check_mode_passes_when_current(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "--check"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_full_copy_is_byte_identical(self):
        source = (ROOT / "REPO_INIT_INSTRUCTIONS.md").read_bytes()
        copy = (ROOT / "skills/skill-tree-unity-repo-documentation/references/REPO_INIT_INSTRUCTIONS.md").read_bytes()
        self.assertEqual(copy, source)

    def test_generated_references_have_notice(self):
        for rel in [
            "skills/skill-tree-repo-documentation/references/DOCUMENTATION_OUTPUT_CONTRACT.md",
            "skills/skill-tree-repo-documentation/references/REPOSITORY_DISCOVERY_CHECKLIST.md",
            "skills/skill-tree-repo-documentation/references/PENDING_TASK_FORMAT.md",
            "skills/skill-tree-repo-documentation-audit/references/PENDING_TASK_FORMAT.md",
            "skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md",
            "skills/skill-tree-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md",
            "skills/skill-tree-unity-process-future-pending/references/COMMON_FUTURE_WORKFLOW.md",
            "skills/skill-tree-unity-process-future-pending/references/PENDING_TASK_FORMAT.md",
            "skills/skill-tree-unity-process-future-pending/references/FUTURE_TASK_STANDARD.md",
            "skills/skill-tree-unity-implement-next-future-task/references/COMMON_FUTURE_WORKFLOW.md",
            "skills/skill-tree-unity-implement-next-future-task/references/PENDING_TASK_FORMAT.md",
            "skills/skill-tree-unity-implement-next-future-task/references/FUTURE_EXECUTION_RULES.md",
            "skills/skill-tree-unity-repo-documentation-audit/references/COMMON_DOCUMENTATION_OUTPUT_CONTRACT.md",
            "skills/skill-tree-unity-repo-documentation-audit/references/COMMON_REPOSITORY_DISCOVERY_CHECKLIST.md",
            "skills/skill-tree-unity-repo-documentation-audit/references/PENDING_TASK_FORMAT.md",
            "skills/skill-tree-create-documents-snapshot/references/SNAPSHOT_RULES.md",
            "skills/skill-tree-unity-create-documents-snapshot/references/SNAPSHOT_RULES.md",
            "skills/skill-tree-process-future-pending/scripts/validate_future_document.py",
            "skills/skill-tree-unity-process-future-pending/scripts/validate_future_document.py",
            "skills/skill-tree-implement-next-future-task/scripts/select_prioritized_task.py",
            "skills/skill-tree-unity-implement-next-future-task/scripts/select_prioritized_task.py",
        ]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("GENERATED FILE", text.splitlines()[:5])

    def test_missing_heading_fails_safely(self):
        module = load_sync_module()
        with self.assertRaises(ValueError):
            module.extract_section("# Title\n", "## Missing", "## End")

    def test_duplicate_heading_fails_safely(self):
        module = load_sync_module()
        text = "## A\nx\n## A\ny\n## B\n"
        with self.assertRaises(ValueError):
            module.extract_section(text, "## A", "## B")


if __name__ == "__main__":
    unittest.main()
