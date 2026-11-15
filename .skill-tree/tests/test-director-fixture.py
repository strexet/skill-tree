"""Qualify portable Director fixture inputs and the existing workspace recovery path."""

from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


CORE = Path(__file__).resolve().parents[1]
FIXTURE = CORE / 'tests/fixtures/director'
SPEC = importlib.util.spec_from_file_location('director_fixture_workflow', CORE / 'common/scripts/workflow-state.py')
WORKFLOW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WORKFLOW)

EMPTY_QUEUE = (
    '# Future Work\n\n'
    '## Pending Task Format\n\n'
    '## Pending Queue\n\n'
    '## Prioritized Next Changes\n\n'
    '## Backlog\n'
)
COMMIT_DATE = '2026-11-12T00:00:00+00:00'


def git(directory, *arguments):
    result = subprocess.run(
        ['git', '-C', str(directory), *arguments], check=True, text=True,
        capture_output=True, timeout=20,
    )
    return result.stdout.strip()


def fixture_project(directory, manifest):
    project = directory / 'queue'
    project.mkdir(parents=True)
    remote = directory / 'origin.git'
    git(directory, 'init', '--bare', str(remote))
    git(project, 'init', '-b', manifest['base_branch'])
    git(project, 'config', 'core.hooksPath', os.devnull)
    git(project, 'config', 'protocol.allow', 'never')
    git(project, 'remote', 'add', manifest['remote'], str(remote))
    for relative in manifest['areas'].values():
        shutil.copytree(FIXTURE / relative, project / relative)

    store = WORKFLOW.Store(project)
    store.future.parent.mkdir(parents=True)
    store.future.write_text(EMPTY_QUEUE, encoding='utf-8')
    config = store.base / 'config'
    config.mkdir()
    (config / 'repository.json').write_text('{"schema":1,"role":"source"}\n', encoding='utf-8')

    git(project, 'add', '--', *manifest['areas'].values(), '.skill-tree')
    git(project, '-c', 'user.name=Director Fixture', '-c', 'user.email=director@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-m', 'Create portable Director fixture')
    return store, git(project, 'rev-parse', 'HEAD')


def prioritized_task(store, title, source):
    criterion = 'Preserve the declared fixture source.'
    check = {
        'id': 'fixture-source',
        'recipe_id': 'static-inspection',
        'criteria': [criterion],
        'sources': [source],
        'parameters': {},
        'assertion': criterion,
        'timing': 'immediate',
    }
    body = (
        f'Goal:\n- {criterion}\n\nTouch:\n- `{source}`\n\n'
        'Validation:\n```json\n' + json.dumps({'checks': [check]})
        + f'\n```\n\nAcceptance:\n- {criterion}\n'
    )
    pending = WORKFLOW.intake(store, {'title': title, 'description': criterion, 'expected_behavior': criterion})
    result = WORKFLOW.process(store, {
        'selectors': [pending['id']],
        'dispositions': {
            pending['id']: {'status': 'promoted', 'reason': 'The portable fixture defines the task boundary.'},
        },
        'tasks': [{'title': title, 'body': body, 'parent_pending_ids': [pending['id']]}],
    })
    return result['created_ids'][0]


class DirectorFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.manifest = json.loads((FIXTURE / 'fixture-manifest.json').read_text(encoding='utf-8'))

    def test_exact_source_pins_drive_acceptance_and_a_real_consumer_failure(self):
        self.assertEqual(self.manifest['schema'], 1)
        copied = self.directory / 'consumer-fixture'
        for relative in self.manifest['areas'].values():
            shutil.copytree(FIXTURE / relative, copied / relative)
        consumer = self.manifest['consumer']
        art = self.manifest['artifact']
        story = self.manifest['story']
        for pin in (consumer, art, story['accepted'], story['changed']):
            file = copied / pin['path']
            self.assertEqual(sha256(file.read_bytes()).hexdigest(), pin['sha256'])
        self.assertNotEqual(story['accepted']['sha256'], story['changed']['sha256'])

        def check(revision):
            return subprocess.run(
                [sys.executable, '-B', str(copied / consumer['path']),
                 str(copied / story[revision]['path']), str(copied / art['path'])],
                capture_output=True, text=True, timeout=10,
            )

        accepted = check('accepted')
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout), {
            'requirement_id': story['id'],
            'requirement_revision': story['accepted']['revision'],
            'artifact_id': art['id'],
            'artifact_revision': art['revision'],
            'attachment': 'hand',
        })
        changed = check('changed')
        self.assertEqual(changed.returncode, 1, changed.stderr)
        self.assertEqual(changed.stderr.strip(), consumer['failure'])
        self.assertFalse(changed.stdout)

    def test_exact_fixture_scope_survives_deterministic_workspace_interruption(self):
        settings = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        settings.update(
            GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_DATE=COMMIT_DATE, GIT_COMMITTER_DATE=COMMIT_DATE,
        )
        with patch.dict(os.environ, settings, clear=True):
            store, base = fixture_project(self.directory / 'first', self.manifest)
            _, repeated_base = fixture_project(self.directory / 'second', self.manifest)
            self.assertEqual(base, repeated_base)
            self.check_recovery(store, base)

    def check_recovery(self, store, base):
        root = store.root
        helper = WORKFLOW.workspaces
        registry = helper.setup(store, {})
        self.assertEqual(store.load()['schema'], 3)
        self.assertEqual(registry['queue_id'], helper.runtime(root)['queue_id'])
        game = prioritized_task(store, 'Qualify the game consumer', self.manifest['consumer']['path'])
        changed = self.manifest['story']['changed']['path']
        independent = prioritized_task(store, 'Review the independent story revision', changed)
        independent_body = WORKFLOW.resolve(WORKFLOW.parse(store.text()), [independent])[0]['body']
        baseline_source = (root / changed).read_bytes()
        dirty_source = baseline_source + b'\n'
        (root / changed).write_bytes(dirty_source)

        self.assertEqual(self.manifest['fault_point'], 'before-workspace-create')
        worktree = self.directory / 'interrupted-worktree'
        options = {
            'remote': self.manifest['remote'],
            'base_branch': self.manifest['base_branch'],
            'local_base': True,
            'local_base_authorization': 'Synthetic owner authorization limited to the disposable fixture.',
            'worktree': str(worktree),
        }
        error = helper.RunError('Injected fixture interruption before worktree creation')
        with patch.object(helper, 'create_reserved', side_effect=error) as fault:
            with self.assertRaisesRegex(helper.RunError, 'Injected fixture interruption'):
                WORKFLOW.start(store, 'next', game, workspace=options)
            fault.assert_called_once()

        stopped = store.load()
        run = stopped['active_run']
        self.assertEqual(run['workspace_state'], 'reserved')
        self.assertEqual(run['workspace']['base_commit'], base)
        self.assertTrue(run['workspace']['local_base'])
        self.assertFalse(worktree.exists())
        self.assertEqual(stopped['run_registry']['claims'], {game: run['id']})
        self.assertIn(independent, {task['id'] for task in stopped['tasks']})

        recovered = helper.recover_workspace(WORKFLOW.Store(root, run['id']), {
            'worktree': str(worktree),
            'resolution': 'The fixture interruption occurred before worktree creation.',
        })
        self.assertEqual(recovered['id'], run['id'])
        self.assertEqual(recovered['workspace_state'], 'ready')
        self.assertEqual(git(worktree, 'rev-parse', 'HEAD'), base)
        self.assertEqual(git(worktree, 'branch', '--show-current'), run['workspace']['branch'])
        self.assertEqual(git(worktree, 'status', '--porcelain'), '')
        self.assertEqual(git(self.directory / 'first/origin.git', 'for-each-ref'), '')
        self.assertEqual((worktree / changed).read_bytes(), baseline_source)
        self.assertEqual((root / changed).read_bytes(), dirty_source)
        linked_store = WORKFLOW.Store(worktree)
        self.assertEqual(linked_store.root, root)
        final = linked_store.load()['run_registry']
        self.assertEqual(final['queue_id'], registry['queue_id'])
        self.assertEqual(set(final['runs']), {run['id']})
        self.assertEqual(final['claims'], {game: run['id']})
        self.assertEqual(
            WORKFLOW.resolve(WORKFLOW.parse(linked_store.text()), [independent])[0]['body'],
            independent_body,
        )


if __name__ == '__main__':
    unittest.main()
