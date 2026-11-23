"""Check Director maintenance ownership and publication ancestry against a local Git upstream."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'common/scripts'
spec = importlib.util.spec_from_file_location('maintenance', SCRIPTS / 'director-maintenance.py')
maintenance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(maintenance)


class MaintenanceCheckoutTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.service = self.root / '.skill-tree-director'
        self.service.mkdir()
        self.seed = self.root / 'trusted'
        self.seed.mkdir()
        self.git(self.seed, 'init', '-b', 'develop')
        docs = self.seed / '.skill-tree/documents'
        docs.mkdir(parents=True)
        (docs / 'future.md').write_text('# Future Work\n\n## Pending Task Format\n\nFixture.\n\n'
                                       '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        cfg = self.seed / '.skill-tree/config'
        cfg.mkdir()
        (cfg / 'repository.json').write_text('{"schema":1,"role":"source"}\n')
        (self.seed / 'README.md').write_text('Source\n')
        self.git(self.seed, 'add', '.')
        self.commit(self.seed)
        registry = maintenance.D.WS.setup(maintenance.D.WF.Store(self.seed, neutral=True), {})
        self.queue = registry['queue_id']
        self.git(self.seed, 'add', '.skill-tree')
        self.commit(self.seed)
        replacement = patch.object(maintenance, 'UPSTREAM', self.seed.as_uri())
        replacement.start()
        self.addCleanup(replacement.stop)

    def git(self, root, *args):
        return subprocess.run(['git', '-C', str(root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, root):
        self.git(root, '-c', 'user.name=Fixture', '-c', 'user.email=test@example.invalid',
                 '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture')

    def test_two_project_worktrees_reuse_one_independent_repository_and_preserve_edits(self):
        one = maintenance.prepare(self.service, 'game-one')
        checkout, first = Path(one['checkout']), Path(one['project_checkout'])
        self.assertNotEqual(self.git(checkout, 'rev-parse', '--absolute-git-dir'),
                            self.git(self.seed, 'rev-parse', '--absolute-git-dir'))
        self.assertEqual(one['queue_id'], self.queue)
        self.assertEqual(one['base_commit'], self.git(self.seed, 'rev-parse', 'develop'))
        self.assertEqual(self.git(first, 'diff', 'upstream/develop...HEAD'), '')
        (first / 'README.md').write_text('Local repair\n')
        two = maintenance.prepare(self.service, 'game-two')
        self.assertEqual(two['checkout'], one['checkout'])
        self.assertNotEqual(two['project_checkout'], one['project_checkout'])
        self.assertNotEqual(two['branch'], one['branch'])
        self.assertEqual(self.git(Path(two['project_checkout']), 'status', '--porcelain'), '')
        self.assertEqual(maintenance.prepare(self.service, 'game-one'), one)
        self.assertEqual((first / 'README.md').read_text(), 'Local repair\n')
        self.assertEqual(maintenance.inspect(self.service, 'game-one'), one)
        self.assertEqual(self.git(self.seed, 'branch', '--format=%(refname:short)'), 'develop')

    def test_retry_after_reserved_branch_recovers_the_original_worktree(self):
        original = maintenance.git
        def interrupted(root, *args):
            if args[:2] == ('worktree', 'add'):
                raise ValueError('Interrupted before creating the project checkout')
            return original(root, *args)
        with patch.object(maintenance, 'git', side_effect=interrupted), self.assertRaisesRegex(ValueError, 'Interrupted'):
            maintenance.prepare(self.service, 'tool')
        result = maintenance.prepare(self.service, 'tool')
        self.assertEqual(maintenance.inspect(self.service, 'tool'), result)
        self.assertEqual(self.git(Path(result['checkout']), 'branch', '--list', 'skill-tree/tool').count('skill-tree/tool'), 1)

    def test_rejects_foreign_destination_changed_remote_and_branch(self):
        sources = self.service / 'sources'
        foreign = sources / 'skill-tree'
        foreign.mkdir(parents=True)
        sentinel = foreign / 'owned.txt'
        sentinel.write_text('foreign')
        with self.assertRaises(ValueError):
            maintenance.prepare(self.service, 'game')
        self.assertEqual(sentinel.read_text(), 'foreign')
        foreign.rename(sources / 'unrelated')
        one = maintenance.prepare(self.service, 'game')
        checkout, first = Path(one['checkout']), Path(one['project_checkout'])
        self.git(checkout, 'remote', 'set-url', 'upstream', self.root.as_uri())
        with self.assertRaises(ValueError):
            maintenance.prepare(self.service, 'game')
        self.git(checkout, 'remote', 'set-url', 'upstream', self.seed.as_uri())
        self.git(first, 'switch', '-c', 'foreign')
        with self.assertRaises(ValueError):
            maintenance.prepare(self.service, 'game')
        self.assertEqual(self.git(first, 'branch', '--show-current'), 'foreign')


if __name__ == '__main__':
    unittest.main()
