import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_skill_repository.py"
UNITY_INSPECT = ROOT / "skills/skill-tree-unity-repo-documentation/scripts/inspect_unity_repository.py"
UNITY_DOCS = ROOT / "skills/skill-tree-unity-repo-documentation/scripts/validate_unity_documentation.py"
SNAPSHOT = ROOT / "skills/skill-tree-unity-repo-documentation/scripts/create_documentation_snapshot.py"
AUDIT_SKILL = ROOT / "skills/skill-tree-unity-repo-documentation-audit/SKILL.md"


class SkillRepositoryValidationTests(unittest.TestCase):
    def test_repository_validator_strict_passes(self):
        result = subprocess.run([sys.executable, str(VALIDATOR), "--strict"], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_help_for_python_tools(self):
        tools = [
            ROOT / "scripts/sync_skill_references.py",
            VALIDATOR,
            ROOT / "skills/skill-tree-process-future-pending/scripts/validate_future_document.py",
            ROOT / "skills/skill-tree-implement-next-future-task/scripts/select_prioritized_task.py",
            UNITY_INSPECT,
            UNITY_DOCS,
            SNAPSHOT,
        ]
        for tool in tools:
            with self.subTest(tool=tool):
                result = subprocess.run([sys.executable, str(tool), "--help"], text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_all_canonical_skills_use_skill_tree_prefix(self):
        skills_dir = ROOT / "skills"
        names = sorted(path.name for path in skills_dir.iterdir() if (path / "SKILL.md").is_file())
        self.assertIn("skill-tree-unity-repo-documentation-audit", names)
        self.assertTrue(names)
        for name in names:
            with self.subTest(skill=name):
                self.assertTrue(name.startswith("skill-tree-"))
                text = (skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)

    def test_documentation_audit_skill_requires_code_aware_future_updates(self):
        text = AUDIT_SKILL.read_text(encoding="utf-8")
        self.assertIn("MUST NOT audit docs by comparing documents only", text)
        self.assertIn("Recreate missing required docs from current repository evidence", text)
        self.assertIn("Add meaningful findings to active `FUTURE.md` backlog", text)
        self.assertIn("`FEATURES.md`: current implemented", text)

    def test_unity_inventory_and_docs_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Assets").mkdir()
            (root / "Packages").mkdir()
            (root / "ProjectSettings").mkdir()
            (root / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.0.0f1\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(UNITY_INSPECT), str(root), "--format", "json"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("unityRoots", result.stdout)

    def test_invalid_unity_target_fails(self):
        result = subprocess.run([sys.executable, str(UNITY_INSPECT), "/definitely/not/present"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_snapshot_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Unity project docs\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SNAPSHOT), str(root), "--dry-run"], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("archive:", result.stdout)


if __name__ == "__main__":
    unittest.main()
