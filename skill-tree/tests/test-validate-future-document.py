from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];CLI=ROOT/'skills/skill-tree-process-future-pending/scripts/validate-future-document.py';FIXTURES=ROOT/'tests/fixtures/future'
class FutureValidationTests(unittest.TestCase):
    def test_current_contracts(self):
        for fixture in ['valid.md','blocking-question.md','empty-prioritized.md']:
            with self.subTest(fixture=fixture):
                result=subprocess.run([sys.executable,str(CLI),str(FIXTURES/fixture),'--strict'],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_malformed_contracts(self):
        for fixture in ['missing-questions.md','malformed-queue-order.md','duplicate-id.md']:
            with self.subTest(fixture=fixture):
                result=subprocess.run([sys.executable,str(CLI),str(FIXTURES/fixture),'--strict'],capture_output=True,text=True);self.assertNotEqual(result.returncode,0)
if __name__=='__main__':unittest.main()
