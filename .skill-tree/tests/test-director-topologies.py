"""Exercise both isolated Director topologies through installed operation entry points."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from uuid import uuid4


SOURCE = Path(__file__).resolve().parents[1]
AGENTS = '.agents/skills'
QUEUE = '.skill-tree/documents/future.md'
STATE = '.skill-tree/documents/future.json'
PROFILE = '.skill-tree/installation/profile.json'
MANAGER = '.skill-tree/installation/manager.js'
REGISTRY = '.skill-tree/director/registry.json'
BINDINGS = '.skill-tree/artifacts/director/local-bindings.json'
WRITER = 'skill-tree-work-through-next'
CURRENT_DIRECTOR = 'lantern-topology'
GIT_ENV = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')} | {
    'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
}


def identity(prefix):
    return f'{prefix}-{uuid4()}'


def sha(data):
    return sha256(data).hexdigest()


def write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def read_json(path):
    return json.loads(path.read_bytes())


def snapshot(*paths):
    return tuple(path.read_bytes() if path.exists() else None for path in paths)


class DirectorTopologyTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix='director-topology-controls-')
        self.addCleanup(scratch.cleanup)
        self.base = Path(scratch.name).resolve()
        self.parent = self.base / 'parent'
        self.external = self.base / 'external'
        self.git_project(self.parent, ('story', 'art'))
        self.git_project(self.external, ('game',))
        self.install(self.parent, 'director', WRITER, *[
            'skill-tree-director-' + name for name in ('setup', 'status', 'intake', 'plan', 'run', 'decide')
        ])
        self.install(self.external, 'unity', WRITER)
        self.shared_queue = self.core(self.parent, 'workspace-setup')['queue_id']
        self.external_queue = self.core(self.external, 'workspace-setup')['queue_id']
        self.declaration = {'director_id': CURRENT_DIRECTOR, 'areas': [
            self.area(self.parent, 'story', 'narrative', 'story', self.shared_queue, ['intake']),
            self.area(self.parent, 'art', 'art', 'art', self.shared_queue, []),
            self.area(self.parent, 'maintenance', 'source-maintenance', '.skill-tree', self.shared_queue, []),
            self.area(self.external, 'game', 'unity', 'game', self.external_queue, ['launch']),
        ]}

    def command(self, *args, error=None):
        result = subprocess.run([str(arg) for arg in args], cwd=self.base, env=GIT_ENV,
                                capture_output=True, text=True, timeout=60)
        if error is None:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(result.stdout + result.stderr, error)
        return result.stdout

    def git(self, root, *args):
        return self.command('git', '-C', root, '-c', 'commit.gpgsign=false', '-c', f'core.hooksPath={os.devnull}', *args)

    def git_project(self, root, areas):
        root.mkdir()
        self.git(root, 'init', '-b', 'develop')
        write(root, QUEUE, '# Future Work\n\n## Pending Task Format\n\nFixture.\n\n'
              '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        for area in areas:
            write(root, area + '/source.txt', f'Original isolated {area} input.\n')
        if root == self.parent:
            write(root, '.skill-tree/config/repository.json', '{"schema":1,"role":"source"}\n')
        # Static Unity recipe discovery in the parent and external child uses no Editor.
        write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2\n')
        dependency = 'com.unity.test-framework'
        write(root, 'Packages/manifest.json', json.dumps({'dependencies': {dependency: '1.6.0'}}))
        write(root, 'Packages/packages-lock.json', json.dumps({'dependencies': {dependency: {'version': '1.6.0'}}}))
        self.git(root, 'add', '.')
        self.git(root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Initial local fixture')
        self.git(root, 'remote', 'add', 'origin', str(self.base / (root.name + '-unused.git')))

    def install(self, root, flavor, *operations):
        self.command('node', SOURCE / 'bin/install.js', '--target', root, '--only', 'codex', '--flavor', flavor,
                     '--skills', *operations)
        self.command('node', root / MANAGER, '--verify')

    def invoke(self, script, root, operation, payload, args, error):
        if payload is not None:
            input_path = write(self.base, operation + '-input.json', json.dumps(payload))
            args = [*args, '--input', input_path]
        output = self.command(sys.executable, '-B', script, operation, root, *args, error=error)
        return json.loads(output) if output.strip() else None

    def core(self, root, operation, payload=None, *args, error=None, target=None):
        entry = root / AGENTS / WRITER / 'scripts/workflow-state.py'
        return self.invoke(entry, target or root, operation, payload, args, error)

    def director(self, operation, payload=None, *, family=None, error=None):
        role = family or {'status': 'status', 'objective': 'intake'}.get(operation.split('-')[0], operation.split('-')[0])
        role = 'setup' if role == 'rebind' else role
        entry = self.parent / AGENTS / ('skill-tree-director-' + role) / 'scripts/director-entry.py'
        return self.invoke(entry, self.parent, operation, payload, [], error)

    def area(self, root, name, role, scope, queue, effects):
        return {'id': name, 'role': role, 'checkout': str(root), 'scope': scope, 'expected_queue_id': queue,
                'capabilities': ['core-task'], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status', *effects]}

    def register(self):
        preview = self.director('setup-preview', self.declaration)
        emitted = self.director('setup-apply', {**self.declaration, 'expected_preview_sha256': preview['preview_sha256']})
        self.assertEqual(emitted['registry'], preview['registry'])
        return preview

    def test_owned_shared_root_and_external_rebind_keep_exact_writers(self):
        tracked = (self.parent / QUEUE, self.parent / STATE, self.external / QUEUE, self.external / STATE)
        before = snapshot(*tracked)
        rejected = {**self.declaration, 'areas': [self.area(self.external, 'game', 'unity', 'game', self.shared_queue, [])]}
        self.director('setup-preview', rejected, error='wrong queue')
        self.assertEqual(snapshot(*tracked), before)
        self.assertFalse((self.parent / REGISTRY).exists())

        preview = self.register()
        self.assertEqual(snapshot(*tracked), before)
        self.assertEqual(preview['profile_proofs'][self.shared_queue]['flavor'], 'director')
        self.assertEqual(preview['profile_proofs'][self.external_queue]['flavor'], 'unity')
        profile = read_json(self.parent / PROFILE)
        self.assertEqual(profile['facts']['director']['unity']['status'], 'recipe-discovered')
        self.assertEqual({area['id']: area['queue_id'] for area in preview['registry']['areas'].values()},
                         {'story': self.shared_queue, 'art': self.shared_queue, 'maintenance': self.shared_queue,
                          'game': self.external_queue})
        seen = {area['id']: area for area in self.director('status')['areas']}
        self.assertEqual(seen['story']['profile']['identity'], seen['art']['profile']['identity'])
        self.assertEqual(seen['game']['profile']['flavor'], 'unity')

        registry = (self.parent / REGISTRY).read_bytes()
        binding = (self.parent / BINDINGS).read_bytes()
        wrong = {'director_id': CURRENT_DIRECTOR, 'area_id': 'game', 'checkout': str(self.parent)}
        self.director('rebind-preview', wrong, error='identical canonical queue and repository')
        self.assertEqual(snapshot(self.parent / REGISTRY, self.parent / BINDINGS), (registry, binding))
        dirty = write(self.external, 'game/source.txt', 'Keep preexisting external dirty content.\n')
        source, queue, checkpoint = snapshot(dirty, self.external / QUEUE, self.external / STATE)
        moved = self.base / 'moved-external'
        self.external.rename(moved)
        seen = {area['id']: area for area in self.director('status')['areas']}
        self.assertEqual(seen['game']['state'], 'unavailable')
        rebind = {**wrong, 'checkout': str(moved)}
        self.director('rebind-preview', rebind, error='recover-locator|locator recovery')
        self.core(moved, 'recover-locator', {'queue_id': self.external_queue})
        self.command('node', moved / MANAGER, '--verify', error='foreign')
        self.command('node', moved / MANAGER, '--rebind')
        self.command('node', moved / MANAGER, '--verify')
        review = self.director('rebind-preview', rebind)
        self.assertEqual(review['areas'], ['game'])
        self.director('rebind', {**rebind, 'expected_preview_sha256': '0' * 64}, error='changed since preview')
        self.assertEqual(snapshot(self.parent / REGISTRY, self.parent / BINDINGS), (registry, binding))
        changed = self.director('rebind', {**rebind, 'expected_preview_sha256': review['preview_sha256']})
        self.assertEqual(changed['changed_files'], [BINDINGS])
        self.assertEqual((self.parent / REGISTRY).read_bytes(), registry)
        self.assertEqual(snapshot(moved / 'game/source.txt', moved / QUEUE, moved / STATE), (source, queue, checkpoint))
        self.assertEqual(read_json(self.parent / BINDINGS)['queues'][self.external_queue]['root'], str(moved))
        self.assertEqual({area['id']: area for area in self.director('status')['areas']}['game']['dirty_paths'], ['game/source.txt'])

    def child_task(self):
        goal = 'Verify the admitted external input.'
        note = self.core(self.external, 'intake', {'title': 'Check game input', 'description': goal, 'expected_behavior': goal})
        check = {'id': 'scope-check', 'recipe_id': 'static-inspection', 'criteria': [goal],
                 'sources': ['game/source.txt'], 'parameters': {}, 'assertion': goal, 'timing': 'immediate'}
        body = ('Goal:\n- ' + goal + '\n\nTouch:\n- game/source.txt\n\nValidation:\n```json\n' +
                json.dumps({'checks': [check]}) + '\n```\n\nAcceptance:\n- ' + goal + '\n')
        result = self.core(self.external, 'process', {
            'selectors': [note['id']], 'dispositions': {note['id']: {'status': 'promoted', 'reason': 'The fixture supplies the scope.'}},
            'tasks': [{'title': 'Check game input', 'body': body, 'parent_pending_ids': [note['id']]}],
        })
        task = result['created_ids'][0]
        body = self.core(self.external, 'read', None, '--id', task)['body']
        return {'task_id': task, 'body_sha256': sha(body.encode())}

    def freeze(self, game_task):
        intent = {'objective_id': identity('OB'), 'expected_current_sha256': None, 'intent': {
            'owner_ref': 'fixture-owner', 'title': 'Check linked areas', 'description': 'Retain the external checkpoint.',
            'acceptance': [{'id': 'existing-run', 'criterion': 'Resume the same worktree.'}],
        }}
        preview = self.director('objective-preview', intent)
        approved = self.director('objective-apply', {**intent, 'expected_preview_sha256': preview['preview_sha256']})['current']
        selection = {'objective_id': intent['objective_id'], 'plan_id': identity('PL'), 'plan_revision': 1}
        common = {'capability': 'core-task', 'write_paths': ['source.txt'], 'resources': [], 'pins': [], 'depends_on': [],
                  'expected_result': 'The registered path stays in scope.', 'check': 'scope-check', 'authority_ref': 'fixture-owner',
                  'stop_rules': ['Wait for the exact selected owner answer.']}
        plan = {**selection, 'objective_revision': approved['revision'], 'objective_sha256': approved['sha256'], 'assignments': [
            {**common, 'id': 'game-run', 'role': 'unity', 'area_id': 'game', 'workspace': 'recorded-worktree',
             'child': game_task, 'effects': ['launch']},
            {**common, 'id': 'story-followup', 'role': 'narrative', 'area_id': 'story', 'workspace': 'existing-checkout',
             'child': {'title': 'Review story input', 'description': 'Identify the independent source.',
                       'acceptance': ['Keep the game checkpoint waiting.']}, 'effects': ['intake']},
        ]}
        review = self.director('plan-preview', plan)
        frozen = self.director('plan-freeze', {**plan, 'expected_preview_sha256': review['preview_sha256']})
        return {**selection, 'plan_sha256': frozen['plan_sha256']}

    def test_cross_area_manual_wait_preserves_same_external_run_and_allows_shared_sibling(self):
        game_task = self.child_task()
        self.register()
        selected = self.freeze(game_task)
        run_id = identity('DR')
        key = {'director_run_id': run_id}
        owner = {'actor': 'fixture-owner', 'reference': 'fixture-launch', 'kind': 'owner-message'}
        parent = self.director('run-start', {**selected, **key, 'assignment_ids': ['game-run', 'story-followup'],
                                             'owner': owner, 'authority': {'game-run': ['launch'], 'story-followup': ['intake']},
                                             'approved_defaults': []})
        worktree = self.base / 'game-worktree'
        launch = self.director('run-dispatch', {**key, 'expected_run_sha256': parent['run_sha256'],
                                               'assignment_id': 'game-run', 'operation': 'start', 'request': {
                                                   'expected_source_hash': sha((self.external / QUEUE).read_bytes()),
                                                   'local_base': True, 'local_base_authorization': 'Disposable local fixture.',
                                                   'base_branch': 'develop', 'branch': 'codex/topology-game', 'worktree': str(worktree),
                                               }})
        external_run = launch['result']['id']
        selector = ('--run-id', external_run)
        self.core(self.external, 'checkpoint', {'phase': 'refresh-profile', 'stop_reason': 'Prepare owned worktree profile.'}, *selector)
        self.install(worktree, 'unity', WRITER)
        self.core(worktree, 'admit', None, *selector)
        self.core(worktree, 'checkpoint', {'phase': 'implement', 'stop_reason': None}, *selector)
        work = write(worktree, 'game/source.txt', 'Partial work survives the Director hold.\n')
        parent = self.director('run-status', key)
        receipt = parent['assignments']['game-run']['dispatches']['start']['receipt_sha256']
        question = self.director('decide-open', {**key, 'expected_run_sha256': parent['run_sha256'], 'assignment_id': 'game-run',
            'question_id': identity('DQ'), 'attempt_id': identity('DA'), 'child_run_id': external_run, 'task_id': game_task['task_id'],
            'start_receipt_sha256': receipt, 'recipient': 'fixture-owner', 'requester': 'game-worker', 'key': 'attachment',
            'options': [{'id': 'hand', 'label': 'Carry by hand'}, {'id': 'belt', 'label': 'Carry on the belt'}],
            'recommendation': 'hand', 'affected_areas': ['game', 'story'], 'blocked_action': 'Finalize the game attachment',
            'deadline': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        })['question']
        held = (self.external / STATE).read_bytes()
        self.assertEqual(read_json(self.external / STATE)['run_registry']['runs'][external_run]['phase'], 'blocked')

        waiting = self.director('run-status', key)
        self.assertTrue(waiting['assignments']['game-run']['waiting'])
        self.assertEqual(waiting['assignments']['story-followup']['next'], 'intake')
        failed = self.core(worktree, 'checkpoint', {'phase': 'implement', 'stop_reason': None}, *selector, error='Director question holds')
        self.assertFalse(failed['ok'])
        sibling = self.director('run-dispatch', {**key, 'expected_run_sha256': waiting['run_sha256'],
            'assignment_id': 'story-followup', 'operation': 'intake',
            'request': {'expected_source_hash': sha((self.parent / QUEUE).read_bytes())},
        })
        self.assertRegex(sibling['result']['id'], r'^P-')
        self.assertNotIn(sibling['result']['id'], (self.external / QUEUE).read_text())
        self.assertEqual((self.external / STATE).read_bytes(), held)

        answer = {**key, **{field: question[field] for field in ('question_id', 'question_sha256', 'attempt_id', 'child_run_id')},
                  'expected_run_sha256': sibling['run_sha256'], 'assignment_id': 'game-run', 'choice': 'hand', 'disposition': 'answer',
                  'owner': {**owner, 'reference': 'fixture-answer'}}
        self.director('decide-answer', {**answer, 'child_run_id': identity('WR')}, error='exact')
        self.assertEqual((self.external / STATE).read_bytes(), held)
        result = self.director('decide-answer', answer)
        self.assertEqual(result['status'], 'delivered')
        self.assertEqual(self.director('decide-answer', answer)['delivery'], result['delivery'])
        restored = self.core(worktree, 'index', None, *selector)['active_run']
        self.assertEqual(restored['id'], external_run)
        self.assertEqual(restored['workspace'], launch['result']['workspace'])
        self.assertEqual(restored['phase'], 'implement')
        self.assertIsNone(restored['stop_reason'])
        self.assertEqual(work.read_text(), 'Partial work survives the Director hold.\n')
        self.assertEqual(set(read_json(self.external / STATE)['run_registry']['runs']), {external_run})


if __name__ == '__main__':
    unittest.main()
