import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
ROOT=Path(__file__).resolve().parents[1]
UNITY_INSPECT=ROOT/'skills/unity/skill-tree-repo-documentation/scripts/inspect-unity-repository.py'
SNAPSHOT=ROOT/'skills/general/skill-tree-create-documents-snapshot/scripts/create-documentation-snapshot.py'

class RepositoryValidationTests(unittest.TestCase):
    def test_snapshot_excludes_generated_ownership_from_default_and_explicit_scopes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            files={'README.md':'Project architecture.\n','.skill-tree/documents/technical.md':'Project architecture.\n','.skill-tree/skills/general/example/SKILL.md':'Agent project architecture.\n','.skill-tree/installation/source/common/references/rules.md':'Agent project architecture.\n'}
            for relative,content in files.items():
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(content)
            config=root/'.skill-tree/config/repository.json';config.parent.mkdir(parents=True);config.write_text(json.dumps({'schema':1,'role':'source'}))
            subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            subprocess.run(['git','-C',str(root),'add','.'],check=True,capture_output=True)
            command=[sys.executable,str(SNAPSHOT),str(root),'--dry-run']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('- README.md',result.stdout)
            self.assertIn('- .skill-tree/documents/technical.md',result.stdout)
            self.assertNotIn('- .skill-tree/skills/',result.stdout)
            self.assertNotIn('- .skill-tree/installation/',result.stdout)
            for relative in ['.skill-tree/skills','.skill-tree/installation','.skill-tree/skills/general/example/SKILL.md']:
                result=subprocess.run(command+['--include',relative],capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0,relative)
            self.assertFalse(list(root.rglob('*.zip')))
    def test_source_validation_excludes_self_installation_and_retains_source_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            shutil.copytree(ROOT,repo/'.skill-tree',ignore=shutil.ignore_patterns('installation','artifacts','__pycache__'))
            for name in ['AGENTS.md','CLAUDE.md','GEMINI.md','README.md','LICENSE','package.json','install.sh','install.ps1']:
                shutil.copy2(ROOT.parent/name,repo/name)
            installation=repo/'.skill-tree/installation'
            backup=installation/'.backups/0'
            backup.mkdir(parents=True)
            (installation/'.last-transaction.json').write_text('{}\n')
            (backup/'retained.py').write_text('not valid Python!\n')
            (backup/'retained.md').write_text('You must retain this historical backup.\n')
            command=[sys.executable,str(repo/'.skill-tree/scripts/validate-skill-repository.py'),'--strict','--format','json']
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            (repo/'.skill-tree/common/invalid_owned.py').write_text('not valid Python!\n')
            result=subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('Invalid owned name: common/invalid_owned.py',result.stdout)
            self.assertIn('invalid syntax',result.stdout)
    def test_strict_source_validation(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/validate-skill-repository.py'),'--strict','--format','json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
    def test_unity_inventory_uses_static_project_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for directory in ['Assets','Packages','ProjectSettings']:(root/directory).mkdir()
            (root/'ProjectSettings/ProjectVersion.txt').write_text('m_EditorVersion: 6000.0.0f1\n')
            result=subprocess.run([sys.executable,str(UNITY_INSPECT),str(root),'--format','json'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertIn('unityRoots',result.stdout)
    def test_invalid_unity_target_fails(self):
        result=subprocess.run([sys.executable,str(UNITY_INSPECT),'/definitely/not/present'],capture_output=True,text=True);self.assertNotEqual(result.returncode,0)
    def test_snapshot_naming_scope_and_live_file_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);docs=root/'.skill-tree/documents';docs.mkdir(parents=True)
            (root/'README.md').write_text('Project architecture\n');(docs/'future.md').write_text('Planned project work\n')
            vendor=root/'vendor/readme.md';vendor.parent.mkdir();vendor.write_text('Vendor architecture and project documentation.\n')
            artifact=root/'.skill-tree/artifacts/private.md';artifact.parent.mkdir();artifact.write_text('Private project logs\n')
            before=(docs/'future.md').read_bytes()
            result=subprocess.run([sys.executable,str(SNAPSHOT),str(root),'--dry-run'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr);self.assertFalse(list(artifact.parent.glob('*.zip')))
            result=subprocess.run([sys.executable,str(SNAPSHOT),str(root)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
            archive=next(artifact.parent.glob('*.zip'))
            with zipfile.ZipFile(archive) as z:
                self.assertTrue(any(n.startswith('future-snapshot-') for n in z.namelist()));self.assertTrue(all('/' not in n and n==n.lower() for n in z.namelist()));self.assertFalse(any('private' in n or 'vendor' in n for n in z.namelist()))
                self.assertTrue(all(z.read(n).startswith(b'<!--\nSNAPSHOT DOCUMENT') for n in z.namelist()))
            self.assertEqual(before,(docs/'future.md').read_bytes())
if __name__=='__main__':unittest.main()
