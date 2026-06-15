import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_skill_repository.py"
UNITY_INSPECT = ROOT / "skills/skill-tree-unity-repo-documentation/scripts/inspect_unity_repository.py"
UNITY_DOCS = ROOT / "skills/skill-tree-unity-repo-documentation/scripts/validate_unity_documentation.py"
SNAPSHOT = ROOT / "skills/skill-tree-create-documents-snapshot/scripts/create_documentation_snapshot.py"
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
        self.assertIn("skill-tree-create-documents-snapshot", names)
        self.assertTrue(names)
        for name in names:
            with self.subTest(skill=name):
                self.assertTrue(name.startswith("skill-tree-"))
                text = (skills_dir / name / "SKILL.md").read_text(encoding="utf-8")
                self.assertIn(f"name: {name}", text)

    def test_skill_tree_display_names_match_required_strings(self):
        expected = {
            "skill-tree-unity-repo-documentation": "Skill-Tree: Initialize Documents",
            "skill-tree-unity-repo-documentation-audit": "Skill-Tree: Audit Documents",
            "skill-tree-process-future-pending": "Skill-Tree: Process Pending Tasks",
            "skill-tree-implement-next-future-task": "Skill-Tree: Implement Next Task",
            "skill-tree-create-documents-snapshot": "Skill-Tree: Create Snapshot",
        }
        for skill, display_name in expected.items():
            with self.subTest(skill=skill):
                skill_md = (ROOT / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                openai_yaml = (ROOT / "skills" / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
                self.assertIn(f"# {display_name}", skill_md)
                self.assertIn(f'display_name: "{display_name}"', openai_yaml)

    def test_documentation_audit_skill_requires_code_aware_future_updates(self):
        text = AUDIT_SKILL.read_text(encoding="utf-8")
        self.assertIn("MUST NOT audit docs by comparing documents only", text)
        self.assertIn("Recreate missing required docs from current repository evidence", text)
        self.assertIn("Add meaningful findings to active `FUTURE.md` Backlog", text)
        self.assertIn("Do not add documentation/audit findings to Pending Queue", text)
        self.assertIn("Ensure `FUTURE.md` contains `## Pending Task Format` before `## Pending Queue`", text)
        self.assertIn("references/PENDING_TASK_FORMAT.md", text)
        self.assertIn("`FEATURES.md`: current implemented", text)

    def test_future_contract_routes_documentation_findings_to_backlog(self):
        source = (ROOT / "REPO_INIT_INSTRUCTIONS.md").read_text(encoding="utf-8")
        generated = (ROOT / "skills/skill-tree-process-future-pending/references/FUTURE_TASK_STANDARD.md").read_text(encoding="utf-8")
        for text in (source, generated):
            with self.subTest(source=text[:20]):
                self.assertIn("Do not put issues discovered during Unity documentation initialization or documentation audit in `Pending Queue`", text)
                self.assertIn("Use `Backlog` for issues discovered while creating or auditing documentation", text)
                self.assertIn("- Task title\n  - Description", text)
                self.assertIn("Unity/game behavior", text)
                self.assertIn("Data/model behavior", text)
                self.assertIn("copy this template into the target repository's `Documents/FUTURE.md`", text)
                self.assertIn("## Pending Task Format", text)

    def test_snapshot_skill_owns_document_snapshot_creation(self):
        skill = (ROOT / "skills/skill-tree-create-documents-snapshot/SKILL.md").read_text(encoding="utf-8")
        contract = (ROOT / "skills/skill-tree-unity-repo-documentation/references/DOCUMENTATION_OUTPUT_CONTRACT.md").read_text(encoding="utf-8")
        validator = (ROOT / "skills/skill-tree-unity-repo-documentation/scripts/validate_unity_documentation.py").read_text(encoding="utf-8")
        self.assertIn("Skill-Tree: Create Snapshot", skill)
        self.assertIn("Do not create or update `Documents/DOCUMENTS_SNAPSHOT.md`", skill)
        self.assertIn("skill-tree-create-documents-snapshot", contract)
        self.assertNotIn('"DOCUMENTS_SNAPSHOT.md"', validator)

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
