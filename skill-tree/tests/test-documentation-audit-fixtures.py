import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rules',ROOT/'common/scripts/validate-document-rules.py');rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(rules)
class DocumentRulesTests(unittest.TestCase):
    def test_prose_rules_detect_material_violations(self):
        with tempfile.TemporaryDirectory() as tmp:
            for text in ['The previous version used a shared save.','It stores their settings.','Документ проекта.']:
                path=Path(tmp)/'project.md';path.write_text(text);self.assertTrue(rules.check(path),text)
    def test_identifiers_and_code_preserve_required_syntax(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'project.md';path.write_text('The project uses `this.Settings`.\n\n```csharp\nthis.Run();\n```\n');self.assertEqual(rules.check(path),[])
    def test_naming_exception_and_violation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'SOME_FILE.md';path.write_text('Project state.');self.assertTrue(rules.check(path));path=Path(tmp)/'SKILL.md';path.write_text('Agent contract.');self.assertEqual(rules.check(path),[])
if __name__=='__main__':unittest.main()
