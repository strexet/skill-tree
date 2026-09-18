import importlib.util
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]

class ReferenceSyncTests(unittest.TestCase):
    def test_every_resource_matches_canonical_generation(self):
        spec=importlib.util.spec_from_file_location('resource_generator',ROOT/'scripts/sync-skill-references.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        for path,expected in module.expected_outputs(ROOT).items():
            with self.subTest(path=path):self.assertEqual(path.read_text(),expected)
    def test_check_command_is_read_only(self):
        before={p:p.read_bytes() for p in (ROOT/'skills').rglob('*') if p.is_file()}
        result=subprocess.run([sys.executable,str(ROOT/'scripts/sync-skill-references.py'),'--check'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
if __name__=='__main__':unittest.main()
