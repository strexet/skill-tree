import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

CORE=Path(__file__).resolve().parents[1]
SCRIPT=CORE/'common/scripts/create-documentation-snapshot.py'
spec=importlib.util.spec_from_file_location('snapshots',SCRIPT);snapshots=importlib.util.module_from_spec(spec);spec.loader.exec_module(snapshots)

class ScopedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.docs=self.root/'skill-tree/documents';self.docs.mkdir(parents=True)
        (self.root/'README.md').write_text('Project architecture.\n');(self.docs/'future.md').write_text('Planned project work.\n');(self.docs/'technical.md').write_text('Project architecture.\n')
    def test_explicit_files_and_root_dotted_output_preserve_sources_and_notices(self):
        before={p:p.read_bytes() for p in self.root.rglob('*.md')}
        archive,scope=snapshots.create(self.root,None,False,include=['skill-tree/documents/future.md','skill-tree/documents/technical.md'],member_style='dotted',output_dir='root',timestamp='2026-10-14-12-00')
        self.assertEqual(archive.parent,self.root);self.assertEqual(len(scope),2)
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(zipped.namelist(),['future.snapshot-2026-10-14-12-00.md','technical.snapshot-2026-10-14-12-00.md'])
            self.assertTrue(all(zipped.read(name).startswith(b'<!--\nSNAPSHOT DOCUMENT') for name in zipped.namelist()))
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*.md')})
    def test_directory_scope_respects_tracked_sources_and_deduplicates_overlap(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True);subprocess.run(['git','-C',str(self.root),'add','README.md','skill-tree/documents/future.md','skill-tree/documents/technical.md'],check=True,capture_output=True)
        (self.docs/'private-note.md').write_text('Untracked private project note.\n')
        _,scope=snapshots.create(self.root,None,True,include=['skill-tree/documents','skill-tree/documents/future.md'])
        self.assertEqual(scope,['skill-tree/documents/future.md','skill-tree/documents/technical.md'])
        _,scope=snapshots.create(self.root,None,True,include=['skill-tree/documents/private-note.md']);self.assertEqual(scope,['skill-tree/documents/private-note.md'])
    def test_invalid_scope_rejects_whole_request_without_creating_archive(self):
        cases=[['skill-tree/documents/future.md','missing.md'],['../outside.md'],['README.md','skill-tree/artifacts/private.md'],[]]
        artifact=self.root/'skill-tree/artifacts';artifact.mkdir();(artifact/'private.md').write_text('Private project evidence.\n')
        for scope in cases:
            with self.subTest(scope=scope):
                with self.assertRaises(ValueError):snapshots.create(self.root,None,False,include=scope)
                self.assertEqual(list(self.root.rglob('*.zip')),[])
    def test_symlink_scope_cannot_capture_external_document(self):
        with tempfile.TemporaryDirectory() as outside:
            external=Path(outside)/'secret.md';external.write_text('External project data.');link=self.docs/'linked.md';link.symlink_to(external)
            with self.assertRaisesRegex(ValueError,'escapes repository'):snapshots.create(self.root,None,False,include=['skill-tree/documents/linked.md'])
    def test_duplicate_basenames_are_flattened_in_dotted_archives(self):
        directory=self.docs/'nested';directory.mkdir();(directory/'future.md').write_text('Nested project work.\n')
        archive,_=snapshots.create(self.root,None,False,include=['skill-tree/documents/future.md','skill-tree/documents/nested/future.md'],member_style='dotted',timestamp='2026-10-14-12-00')
        with zipfile.ZipFile(archive) as zipped:
            self.assertEqual(len(set(zipped.namelist())),2);self.assertTrue(all('/' not in name and '.snapshot-' in name for name in zipped.namelist()))
    def test_cli_repeated_includes_and_dry_run_match_creation_scope(self):
        archive=self.root/'review.zip'
        command=['python3',str(SCRIPT),str(self.root),'--include','README.md','--include','skill-tree/documents/future.md','--output',str(archive),'--member-style','dotted']
        dry=subprocess.run(command+['--dry-run'],capture_output=True,text=True);self.assertEqual(dry.returncode,0,dry.stderr);self.assertIn('included: 2',dry.stdout);self.assertFalse(archive.exists())
        result=subprocess.run(command,capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
        with zipfile.ZipFile(archive) as zipped:self.assertEqual(len(zipped.namelist()),2);self.assertTrue(any(name.startswith('README.snapshot-') for name in zipped.namelist()))
    def test_explicit_output_cannot_replace_live_markdown_or_existing_archive(self):
        live=self.docs/'future.md';before=live.read_bytes()
        with self.assertRaises(ValueError):snapshots.create(self.root,live,False,include=['README.md'])
        self.assertEqual(live.read_bytes(),before)
        archive,_=snapshots.create(self.root,None,False,include=['README.md'],timestamp='2026-10-14-12-00');before=archive.read_bytes()
        with self.assertRaises(ValueError):snapshots.create(self.root,archive,False,include=['README.md'])
        self.assertEqual(archive.read_bytes(),before)

if __name__=='__main__':unittest.main()
