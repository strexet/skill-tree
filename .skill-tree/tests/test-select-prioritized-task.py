import json
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];CLI=ROOT/'skills/skill-tree-implement-next-future-task/scripts/select-prioritized-task.py';FIXTURES=ROOT/'tests/fixtures/future'
class SelectionTests(unittest.TestCase):
    def run_cli(self,fixture,*args):return subprocess.run([sys.executable,str(CLI),str(FIXTURES/fixture),'--format','json',*args],capture_output=True,text=True)
    def test_priority_and_document_order(self):
        result=self.run_cli('high-priority.md');self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['title'],'Highest task')
    def test_exact_name_and_identity(self):
        result=self.run_cli('valid.md','--name','  VALIDATE   isolated saves ');self.assertEqual(result.returncode,0,result.stderr);tid=json.loads(result.stdout)['id'];self.assertEqual(self.run_cli('valid.md','--id',tid).returncode,0)
    def test_absent_name_never_falls_back(self):self.assertNotEqual(self.run_cli('valid.md','--name','Other task').returncode,0)
    def test_ambiguous_name_never_falls_back(self):self.assertNotEqual(self.run_cli('ambiguous-names.md','--name','Same task').returncode,0)
    def test_blocked_and_empty_stop(self):
        self.assertEqual(self.run_cli('blocking-question.md').returncode,8);self.assertEqual(self.run_cli('empty-prioritized.md').returncode,4)
    def test_missing_file_stops(self):self.assertEqual(self.run_cli('absent.md').returncode,2)
if __name__=='__main__':unittest.main()
