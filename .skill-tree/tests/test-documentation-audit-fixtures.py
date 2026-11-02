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

class LocatedDocumentRulesTests(unittest.TestCase):
    def test_diagnostics_preserve_line_and_column_after_literal_blocks(self):
        text='```csharp\nthis.Run();\n```\n\nIt stores their settings.\n'
        items=rules.diagnostics(text)
        self.assertEqual([(item['excerpt'],item['line'],item['column']) for item in items],[('It',5,1),('their',5,11)])
    def test_relative_clauses_current_usage_and_quoted_product_labels_pass(self):
        text='The queue stores commands that preserve task intent.\nThe outbox may be used to recover accepted commands.\nThe planner exposes "My Day" and \'My Tasks\'.\n'
        self.assertEqual(rules.diagnostics(text),[])
    def test_ambiguous_demonstrative_is_located_warning_not_default_error(self):
        text='That stores settings.\n';items=rules.diagnostics(text);self.assertEqual(items[0]['severity'],'warning');self.assertEqual(items[0]['line'],1);self.assertEqual(rules.check_text(text),[]);self.assertTrue(rules.check_text(text,warnings_as_errors=True))
    def test_non_english_prose_and_history_remain_errors(self):
        items=rules.diagnostics('Project context.\nThe previous version stored defaults.\nОписание.\n')
        self.assertEqual([item['severity'] for item in items],['error','error']);self.assertEqual([item['line'] for item in items],[2,3])
    def test_markup_masks_comments_identifiers_and_link_destinations_without_masking_labels(self):
        text='<!-- It stores their settings. -->\nThe project uses `this.Settings` and [Its configuration](https://example.test/that).\n'
        items=rules.diagnostics(text);self.assertEqual(len(items),1);self.assertEqual(items[0]['excerpt'],'Its');self.assertEqual(items[0]['line'],2)

if __name__=='__main__':unittest.main()
