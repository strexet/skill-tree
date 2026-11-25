"""Exercise both isolated Director topologies through installed operation entry points."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import runpy
from pathlib import Path
from shutil import copytree, ignore_patterns
import signal
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
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
        if 'game' in areas:
            write(root, 'game/resource.txt', 'Another fixture input using the same exclusive resource.\n')
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

    def test_moved_director_setup_stops_before_child_effects_and_reuses_identity(self):
        seed=self.base/'move-maintenance-source'
        seed.mkdir()
        self.git(seed,'init','-b','develop')
        write(seed,'.skill-tree/config/repository.json','{"role":"source"}\n')
        write(seed,QUEUE,'# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n'
                         '\n## Prioritized Next Changes\n\n## Backlog\n')
        self.git(seed,'add','.')
        self.git(seed,'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                 'commit','-m','Initialize local maintenance fixture')
        composed=self.base/'move-composer/.skill-tree'
        for relative in ('common','config','domains','lib','src','templates','tests/fixtures/director'):
            copytree(SOURCE/relative,composed/relative,ignore=ignore_patterns('__pycache__'))
        maintenance=composed/'common/scripts/director-maintenance.py'
        original=maintenance.read_text()
        local=original.replace("UPSTREAM = 'https://github.com/strexet/skill-tree.git'",f'UPSTREAM = {seed.as_uri()!r}')
        self.assertNotEqual(local,original)
        maintenance.write_text(local)
        shared=self.base/'coordinated-workspace'
        shared.mkdir()
        self.git(shared,'init','-b','develop')
        self.command('node',SOURCE/'bin/install.js','--only','codex','--target',shared,'--source',composed)
        root=shared/'.skill-tree/.director'
        descriptor=read_json(root/'workspace.json')
        locator='.git/skill-tree-runtime.json'
        journal_path=root/'.skill-tree/artifacts/director/project-preparation/coordinator.json'
        journal=read_json(journal_path)
        step=journal['units'][str(root)]
        manifest=root/'.skill-tree/skill-tree.json'
        manifest.unlink()
        step['completed']=[name for name in step['completed'] if name not in ('core','manifest')]
        step['pending']='core'
        step['proof']['owner']=None
        step['proof']['files'][STATE]=journal['item']['file_proofs'][STATE]
        step['proof']['files']['.skill-tree/skill-tree.json']=None
        journal_path.write_text(json.dumps(journal))
        pending_journal=journal_path.read_bytes()
        pending=self.invoke(root/descriptor['setup_entry'],root,'project-setup',
                            {'kind':'new','name':'isolated-new-project'},[],error='coordinator preparation')
        self.assertEqual(pending['prerequisite']['kind'],'director-coordinator-preparation')
        self.assertEqual(journal_path.read_bytes(),pending_journal)
        self.assertFalse((root/'sources/skill-tree').exists())
        self.assertFalse((shared/'isolated-new-project').exists())
        step['queue_id']=identity('Q')
        journal_path.write_text(json.dumps(journal))
        try:
            mismatch=self.invoke(root/descriptor['setup_entry'],root,'project-preview',
                                  {'kind':'new','name':'isolated-new-project'},[],error='different Core queue')
            self.assertNotIn('prerequisite',mismatch)
        finally:
            journal_path.write_bytes(pending_journal)
        resumed=self.invoke(root/descriptor['setup_entry'],root,'project-init',None,[],error=None)
        self.assertEqual(resumed['status'],'ready')
        self.assertTrue(manifest.is_file())
        completed=read_json(journal_path)['units'][str(root)]
        self.assertIn('manifest',completed['completed'])
        self.assertNotIn('pending',completed)
        original_state=snapshot(root/QUEUE,root/STATE)
        original_profile=read_json(root/PROFILE)
        queue_id=read_json(root/locator)['queue_id']
        original_head=self.git(root,'symbolic-ref','HEAD')
        moved=self.base/'relocated-workspace'
        shared.rename(moved)
        root=moved/'.skill-tree/.director'
        app=root/descriptor['setup_entry']
        choice={'kind':'new','name':'isolated-new-project'}
        request=write(self.base,'moved-project-choice.json',json.dumps(choice))
        command=[sys.executable,'-B',str(app),'project-preview',str(root),'--input',str(request)]
        preview=subprocess.run(command,cwd=self.base,env=GIT_ENV,capture_output=True,text=True,timeout=30)
        if preview.returncode==0:
            self.fail('Moved Director setup returned a project preview')
        diagnosis=json.loads(preview.stdout)
        self.assertIn('prerequisite',diagnosis,preview.stdout)
        self.assertEqual(diagnosis['prerequisite']['kind'],'director-locator-moved')
        self.assertEqual(diagnosis['prerequisite']['queue_id'],queue_id)
        self.assertEqual(diagnosis['prerequisite']['root'],str(root))
        self.assertEqual(diagnosis['prerequisite']['previous_root'],str(shared/'.skill-tree/.director'))
        before=snapshot(root/QUEUE,root/STATE,root/PROFILE,root/locator)
        result=self.invoke(app,root,'project-setup',choice,[],error='locator')
        self.assertEqual(result['prerequisite']['kind'],'director-locator-moved')
        self.assertFalse((moved/choice['name']).exists())
        self.assertEqual(snapshot(root/QUEUE,root/STATE,root/PROFILE,root/locator),before)
        self.assertFalse((root/'.skill-tree/artifacts/director/project-preparation'/f'{choice["name"]}.json').exists())

        self.assertFalse((root/'sources/skill-tree').exists())
        locator_path=root/locator
        retained=locator_path.read_bytes()
        wrong={**json.loads(retained),'queue_id':identity('Q')}
        locator_path.write_text(json.dumps(wrong))
        try:
            mismatch=self.invoke(app,root,'project-setup',choice,[],error='identities differ')
            self.assertFalse(mismatch['ok'])
            self.assertNotIn('prerequisite',mismatch)
            self.assertFalse((moved/choice['name']).exists())
        finally:
            locator_path.write_bytes(retained)
        invalid={**json.loads(retained),'worktrees':{identity('WR'):'relative-checkout'}}
        locator_path.write_text(json.dumps(invalid))
        try:
            malformed=self.invoke(app,root,'project-setup',choice,[],error='Invalid retained worktree paths')
            self.assertNotIn('prerequisite',malformed)
        finally:
            locator_path.write_bytes(retained)

        recover=diagnosis['prerequisite']
        helper=app.parent/'runtime/common/scripts/workflow-state.py'
        self.assertEqual(Path(recover['argv'][2]),helper)
        self.invoke(helper,root,'recover-locator',{'queue_id':queue_id,'worktrees':{}},[],error=None)
        receipt=self.invoke(app,root,'project-setup',choice,[],error='receipt')
        self.assertEqual(receipt['prerequisite']['kind'],'director-profile-moved')
        self.assertFalse((moved/choice['name']).exists())
        profile_path=root/PROFILE
        saved_profile=profile_path.read_bytes()
        for former in ('', 'relative-coordinator', str(self.external)):
            with self.subTest(former=former):
                profile_path.write_text(json.dumps({**json.loads(saved_profile),'project_root':former}))
                try:
                    invalid=self.invoke(app,root,'project-setup',choice,[],error='former Director installation receipt')
                    self.assertNotIn('prerequisite',invalid)
                finally:
                    profile_path.write_bytes(saved_profile)

        self.command('node',root/MANAGER,'--rebind')
        self.command('node',root/MANAGER,'--verify')
        self.assertEqual(read_json(root/PROFILE)['identity'],original_profile['identity'])
        self.assertEqual(read_json(root/locator)['queue_id'],queue_id)
        self.assertEqual(snapshot(root/QUEUE,root/STATE),original_state)
        self.assertEqual(self.git(root,'symbolic-ref','HEAD'),original_head)
        rebound_locator=locator_path.read_bytes()
        locator_path.unlink()
        try:
            missing=self.invoke(app,root,'project-init',None,[],error='locator')
            self.assertNotIn('prerequisite',missing)
            self.assertFalse(locator_path.exists())
            self.assertEqual(snapshot(root/QUEUE,root/STATE),original_state)
        finally:
            locator_path.write_bytes(rebound_locator)
        restored=self.invoke(app,root,'project-preview',choice,[],error=None)
        self.assertEqual(restored['checkout'],str(moved/choice['name']))
        self.assertEqual(restored['status'],'preview')
        registered=self.invoke(app,root,'project-setup',choice,[],error=None)
        self.assertEqual(registered['status'],'registered')
        self.assertEqual(registered['checkout'],restored['checkout'])
        self.assertEqual(read_json(root/REGISTRY)['areas'][choice['name']]['queue_id'],registered['queue_id'])

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

    def child_task(self, root=None, paths=('game/source.txt',), title='Check game input', dependencies=()):
        root = root or self.external
        goal = 'Verify the admitted input.'
        note = self.core(root, 'intake', {'title': title, 'description': goal, 'expected_behavior': goal})
        check = {'id': 'scope-check', 'recipe_id': 'static-inspection', 'criteria': [goal],
                 'sources': list(paths), 'parameters': {}, 'assertion': goal, 'timing': 'immediate'}
        touch = '\n'.join('- ' + path for path in paths)
        body = ('Goal:\n- ' + goal + '\n\nTouch:\n' + touch + '\n\nValidation:\n```json\n' +
                json.dumps({'checks': [check]}) + '\n```\n\nAcceptance:\n- ' + goal + '\n')
        result = self.core(root, 'process', {
            'selectors': [note['id']], 'dispositions': {note['id']: {'status': 'promoted', 'reason': 'The fixture supplies the scope.'}},
            'tasks': [{'title': title, 'body': body, 'parent_pending_ids': [note['id']],
                       'depends_on': list(dependencies)}],
        })
        task = result['created_ids'][0]
        body = self.core(root, 'read', None, '--id', task)['body']
        return {'task_id': task, 'body_sha256': sha(body.encode())}

    def freeze(self, game_task, *, assignments=None):
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
        default_assignments = [
            {**common, 'id': 'game-run', 'role': 'unity', 'area_id': 'game', 'workspace': 'recorded-worktree',
             'child': game_task, 'effects': ['launch']},
            {**common, 'id': 'story-followup', 'role': 'narrative', 'area_id': 'story', 'workspace': 'existing-checkout',
             'child': {'title': 'Review story input', 'description': 'Identify the independent source.',
                       'acceptance': ['Keep the game checkpoint waiting.']}, 'effects': ['intake']},
        ]
        plan = {**selection, 'objective_revision': approved['revision'], 'objective_sha256': approved['sha256'],
                'assignments': default_assignments if assignments is None else assignments}
        review = self.director('plan-preview', plan)
        frozen = self.director('plan-freeze', {**plan, 'expected_preview_sha256': review['preview_sha256']})
        return {**selection, 'plan_sha256': frozen['plan_sha256']}

    def test_prepared_registration_and_intake_verify_the_original_canonical_route(self):
        tools = self.parent
        source = self.base/'package-source'
        source.mkdir()
        self.git(source, 'init', '-b', 'develop')
        for relative in ('bin', 'common', 'config', 'domains', 'lib', 'src', 'templates', 'tests/fixtures/director'):
            copytree(SOURCE/relative, source/'.skill-tree'/relative, ignore=ignore_patterns('__pycache__'))
        self.git(source, 'add', '.skill-tree')
        self.git(source, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'Pin the disposable Director source')
        pin = {'checkout': str(source), 'revision': self.git(source, 'rev-parse', 'HEAD').strip()}
        coordinator = self.base/'guided-parent'
        def area(name, role, project, flavor=None, effects=()):
            return {'id': name, 'role': role, 'capabilities': ['core-task'], 'allowed_effects': ['status', *effects],
                    'project': project, **({'flavor': flavor, 'source': pin} if flavor else {})}
        plan = {'director_id': CURRENT_DIRECTOR, 'workspace': {'kind': 'new', 'source': pin}, 'areas': [
            area('maintenance', 'source-maintenance', {'kind': 'existing', 'topology': 'separate', 'path': str(source)}, 'general'),
            area('game', 'unity', {'kind': 'existing', 'topology': 'separate', 'path': str(self.external), 'scope': 'game'}, 'unity', ('launch',)),
            area('story', 'narrative', {'kind': 'new', 'topology': 'shared', 'placement': 'inside', 'path': 'story'},
                 effects=('intake',)),
            area('art', 'art', {'kind': 'new', 'topology': 'shared', 'placement': 'inside', 'path': 'art'}),
        ]}
        entry = tools/AGENTS/'skill-tree-director-setup/scripts/director-entry.py'
        preview = self.invoke(entry, coordinator, 'setup-preview', plan, [], None)
        prepared = self.invoke(entry, coordinator, 'setup-bootstrap',
                               {'request': plan, 'expected_preview_sha256': preview['preview_sha256']}, [], None)
        self.assertEqual(prepared['status'], 'prepared')
        self.parent = coordinator
        handoff = {'director_id': CURRENT_DIRECTOR, 'prepared_preview_sha256': preview['preview_sha256']}
        setup = self.director('setup-status', handoff)['areas']
        self.assertEqual({(item['preparation'], item['registration'], item['routing']['status']) for item in setup.values()},
                         {('prepared', 'unregistered', 'unverified')})
        review = self.director('setup-preview', handoff)
        registration = {**handoff, 'expected_preview_sha256': review['preview_sha256']}
        self.assertEqual(set(review['added_areas']), set(setup))
        self.assertEqual(review['registry']['areas']['game']['queue_id'], self.external_queue)
        self.assertEqual(review['registry']['areas']['story']['queue_id'], prepared['areas']['story']['queue']['queue_id'])
        profile = self.external/PROFILE
        original_profile = profile.read_bytes()
        profile.write_bytes(original_profile + b'\n')
        self.director('setup-apply', registration, error='Prepared installed profile changed')
        self.assertFalse((self.parent/REGISTRY).exists())
        profile.write_bytes(original_profile)
        registered = self.director('setup-apply', registration)
        self.assertEqual(registered['registry'], review['registry'])
        setup = self.director('setup-status', handoff)['areas']
        self.assertEqual({(item['registration'], item['routing']['status']) for item in setup.values()},
                         {('registered', 'unverified')})

        plan = self.freeze(self.child_task())
        run_id = identity('DR')
        owner = {'actor': 'fixture-owner', 'reference': 'guided-intake-approval', 'kind': 'owner-message'}
        run = self.director('run-start', {**plan, 'director_run_id': run_id, 'assignment_ids': ['story-followup'],
                                         'owner': owner, 'authority': {'story-followup': ['intake']}, 'approved_defaults': []})
        selected = {'director_run_id': run_id, 'assignment_id': 'story-followup'}
        projection = {**handoff, 'routing': [selected]}
        self.assertEqual(self.director('setup-status', projection)['areas']['story']['routing']['status'], 'unverified')
        dispatch = {**selected, 'operation': 'intake', 'expected_run_sha256': run['run_sha256'],
                    'request': {'expected_source_hash': sha((self.parent/QUEUE).read_bytes())}}
        unselected = (self.external/QUEUE, self.external/STATE, source/QUEUE, source/STATE)
        before, coordinator_before = snapshot(*unselected), snapshot(self.parent/QUEUE, self.parent/STATE)
        bindings_path = self.parent/BINDINGS
        original = bindings_path.read_bytes()
        changed = json.loads(original)
        shared_queue = setup['story']['queue_id']
        changed['queues'][shared_queue]['root'] = str(self.external)
        bindings_path.write_text(json.dumps(changed))
        self.assertEqual(self.director('setup-status', handoff)['areas']['story']['registration'], 'stale')
        self.director('run-dispatch', dispatch, error='canonical|binding|qualification')
        self.assertEqual(snapshot(*unselected), before)
        self.assertEqual(snapshot(self.parent/QUEUE, self.parent/STATE), coordinator_before)
        bindings_path.write_bytes(original)

        directed = self.director('run-dispatch', dispatch)
        pending = directed['result']['id']
        envelope = {'schema': 1, 'director_id': CURRENT_DIRECTOR, 'queue_id': shared_queue,
                    'assignment_id': 'story-followup', 'plan_sha256': plan['plan_sha256']}
        child = self.core(self.parent, 'director-dispatch-read', {'operation': 'intake', 'director_dispatch': envelope})
        self.assertEqual(child['receipt']['result']['id'], pending)
        areas = self.director('setup-status', projection)['areas']
        proof = areas['story']['routing']
        self.assertEqual(proof['status'], 'verified')
        self.assertEqual(proof['receipts'][0]['receipt_sha256'], child['receipt']['receipt_sha256'])
        self.assertEqual(proof['receipts'][0]['queue_id'], shared_queue)
        self.assertEqual(proof['receipts'][0]['area_id'], 'story')
        self.assertEqual(areas['art']['routing']['status'], 'unverified')
        self.assertEqual(areas['game']['routing']['status'], 'unverified')
        after = snapshot(self.parent/QUEUE, self.parent/STATE)
        self.assertEqual((self.parent/QUEUE).read_text().count(pending), 1)
        repeated = self.director('run-dispatch', dispatch)
        self.assertEqual((repeated['status'], repeated['result']['id']), ('replayed', pending))
        self.assertEqual(snapshot(self.parent/QUEUE, self.parent/STATE), after)
        self.assertEqual(snapshot(*unselected), before)

        receipt_file = self.parent/'.skill-tree/history/director-dispatch'/f"{child['dispatch_key']}.json"
        retained = receipt_file.read_bytes()
        receipt_file.unlink()
        self.director('setup-status', projection, error='Original canonical intake receipt is unavailable')
        self.director('run-dispatch', dispatch, error='Original directed child result became unavailable')
        self.assertEqual(snapshot(self.parent/QUEUE, self.parent/STATE), after)
        self.assertEqual(snapshot(*unselected), before)
        receipt_file.write_bytes(retained)

        linked = self.base/'linked-guided'
        self.git(tools, 'worktree', 'add', '-b', 'linked-guided', linked, 'HEAD')
        linked_plan = {'director_id':'linked-bootstrap', 'workspace':{'kind':'existing', 'source':pin}, 'areas':[
            area('maintenance', 'source-maintenance',
                 {'kind':'existing', 'topology':'separate', 'path':str(source)}, 'general'),
        ]}
        linked_preview = self.invoke(entry, linked, 'setup-preview', linked_plan, [], None)
        linked_prep = self.invoke(entry, linked, 'setup-bootstrap',
                                  {'request':linked_plan, 'expected_preview_sha256':linked_preview['preview_sha256']},
                                  [], None)
        self.assertEqual(linked_prep['status'], 'prepared')
        self.assertIn(BINDINGS, self.git(linked, 'check-ignore', '--no-index', '--', BINDINGS))
        linked_handoff = {'director_id':'linked-bootstrap', 'prepared_preview_sha256':linked_preview['preview_sha256']}
        linked_review = self.invoke(entry, linked, 'setup-preview', linked_handoff, [], None)
        apply_linked = {**linked_handoff, 'expected_preview_sha256':linked_review['preview_sha256']}
        owner_exclude = tools/'.git/info/exclude'
        saved_exclude = owner_exclude.read_bytes()
        negate = write(linked, '.gitignore', '!/'+BINDINGS+'\n')
        transaction = write(linked, '.skill-tree/.transaction.json', json.dumps({
            'format':'skill-tree-transaction',
            'writes':[{'path':BINDINGS, 'expected_hash':None, 'content':'{"fixture":"retained binding"}\n'}],
        }))
        retained_transaction = transaction.read_bytes()
        try:
            self.invoke(entry, linked, 'setup-apply', apply_linked, [], 'needs a local Git exclusion')
            self.assertFalse((linked/REGISTRY).exists())
            self.assertFalse((linked/BINDINGS).exists())
            self.assertEqual(owner_exclude.read_bytes(), saved_exclude)
            self.assertEqual(transaction.read_bytes(), retained_transaction)
        finally:
            negate.unlink()
            transaction.unlink()
        linked_registered = self.invoke(entry, linked, 'setup-apply', apply_linked, [], None)
        self.assertEqual(linked_registered['registry'], linked_review['registry'])
        self.assertTrue((linked/REGISTRY).is_file())
        self.assertTrue((linked/BINDINGS).is_file())
        self.assertFalse((tools/REGISTRY).exists())

    def test_directed_batch_preserves_canonical_metadata_edges_and_receipts(self):
        story = self.declaration['areas'][0]
        story['allowed_effects'].append('process')
        self.register()
        batch_id = identity('IB')
        batch_items = [
            {'key':'consumer', 'title':'Investigate story consumer', 'description':'Review the selected story input.',
             'acceptance':['Preserve the scoped behavior.'], 'priority':495, 'topic':'mvp-five'},
            {'key':'storage', 'title':'Investigate story storage', 'description':'Review the selected storage input.',
             'acceptance':['Preserve the scoped behavior.'], 'priority':245, 'topic':'mvp-zero',
             'pending_depends_on':['@adapter']},
            {'key':'adapter', 'title':'Investigate story adapter', 'description':'Review the selected adapter input.',
             'acceptance':['Preserve the scoped behavior.'], 'priority':175, 'topic':'mvp-two'},
        ]
        assignment = {'id':'story-batch', 'area_id':'story', 'role':'narrative', 'workspace':'existing-checkout',
                      'capability':'core-task', 'write_paths':['source.txt'], 'resources':[], 'pins':[],
                      'depends_on':[], 'expected_result':'Retain directed story scope.', 'check':'scope-check',
                      'authority_ref':'fixture-owner', 'effects':['intake','process'],
                      'stop_rules':['Stop for input outside the recorded scope.'],
                      'child':{'intake_batch_id':batch_id,'items':batch_items}}
        selected = self.freeze(None, assignments=[assignment])
        other = self.core(self.parent, 'intake', {
            'title':'Keep unrelated input', 'description':'Retain the unselected work.',
            'expected_behavior':'Keep the unselected work unchanged.',
        })
        legacy_scope = {'schema':1,'director_id':CURRENT_DIRECTOR,'assignment_id':'relative-batch-fixture',
                        'queue_id':self.shared_queue,'plan_sha256':selected['plan_sha256']}
        relative_batch = self.core(self.parent,'director-dispatch',{'operation':'intake','request':{
            'director_dispatch':legacy_scope, 'expected_source_hash':sha((self.parent/QUEUE).read_bytes()),
            'intake_batch_id':identity('IB'), 'items':[{
                'title':'Keep the relative request', 'description':'Preserve unselected work.',
                'expected_behavior':'Preserve the unselected request.',
                'relative_priority':{'task_id':other['id'],'direction':'above'},
            }],
        }})
        self.assertEqual(relative_batch['items'][0]['priority'],other['priority']+1)
        goal = 'Preserve the scoped behavior.'
        source = 'story/source.txt'
        check = {'id':'scope-check','recipe_id':'static-inspection','criteria':[goal],
                 'sources':[source],'parameters':{},'assertion':goal,'timing':'immediate'}
        body = ('Goal:\n- ' + goal + '\n\nTouch:\n- ' + source + '\n\nValidation:\n```json\n'
                + json.dumps({'checks':[check]}) + '\n```\n\nAcceptance:\n- ' + goal + '\n')
        keys = [item['key'] for item in batch_items]
        disposition = {'status':'promoted','reason':'Research confirms the scoped implementation.'}
        approved = {
            'selectors':keys, 'dispositions':{key:disposition for key in keys},
            'tasks':[
                {'key':'consumer-task','title':'Implement story consumer','body':body,'parent_pending_ids':['consumer'],
                 'depends_on':['@storage-task']},
                {'key':'storage-task','title':'Implement story storage','body':body,'parent_pending_ids':['storage']},
                {'key':'adapter-task','title':'Implement story adapter','body':body,'parent_pending_ids':['adapter']},
            ],
        }
        approved_sha = sha((json.dumps(approved, ensure_ascii=False, indent=2, sort_keys=True)+'\n').encode())
        run_ref = {'director_run_id':identity('DR')}
        run = self.director('run-start', {**selected, **run_ref, 'assignment_ids':[assignment['id']],
            'owner':{'actor':'fixture-owner','reference':'fixture-batch','kind':'owner-message'},
            'authority':{assignment['id']:['intake','process']},'approved_defaults':[],
            'process_spec_sha256':{assignment['id']:approved_sha}})
        queue_path, state_path = self.parent/QUEUE, self.parent/STATE
        request = {**run_ref, 'assignment_id':assignment['id'], 'operation':'intake',
                   'expected_run_sha256':run['run_sha256'],
                   'request':{'expected_source_hash':sha(queue_path.read_bytes())}}
        self.director('run-dispatch', {**request, 'request':{**request['request'], 'items':list(reversed(batch_items))}},
                      error='Unexpected')
        parent_entry = self.parent/AGENTS/'skill-tree-director-run/scripts/runtime/common/scripts/director-state.py'
        fault = '''
import json
from pathlib import Path
import runpy
import sys

director = runpy.run_path(sys.argv[1])
load = director['WF'].owned_module
payload = json.loads(Path(sys.argv[-1]).read_text())
stage = sys.argv[2]

def with_interruption(name, path):
    helper = load(name, path)
    if name == 'director_run' and stage == 'lost-ack':
        original = helper.DirectorRun._write

        def write(self, relative, state, expected_sha):
            if any(row['event'] == 'dispatch-recorded' and row.get('operation') == payload['operation']
                   for row in state['timeline']):
                raise OSError('Injected loss after canonical acknowledgement')
            return original(self, relative, state, expected_sha)

        helper.DirectorRun._write = write
    if name == 'director_run' and stage == 'pause':
        original = helper.DirectorRun._batch_dispatched_result

        def pause(self, *args):
            result = original(self, *args)
            run_id = payload['director_run_id']
            _, _, current_sha = self._load(run_id)
            self.lifecycle('run-pause', {'director_run_id':run_id,'expected_run_sha256':current_sha})
            return result

        helper.DirectorRun._batch_dispatched_result = pause
    return helper

director['WF'].owned_module = with_interruption
raise SystemExit(director['main'](sys.argv[3:]))
'''
        scope = {'schema':1,'director_id':CURRENT_DIRECTOR,'assignment_id':assignment['id'],
                 'queue_id':self.shared_queue,'plan_sha256':selected['plan_sha256']}
        intake_input = write(self.base,'lost-batch-intake-ack.json',json.dumps(request))
        self.command(sys.executable,'-B','-c',fault,parent_entry,'lost-ack','run-dispatch',self.parent,'--input',intake_input,
                     error='Injected loss after canonical acknowledgement')
        original_intake = self.core(self.parent,'director-dispatch-read',{'operation':'intake','director_dispatch':scope})
        canonical_text = queue_path.read_text()
        altered_text = canonical_text.replace('Review the selected story input.', 'Owner revised the selected story input.')
        self.assertNotEqual(altered_text,canonical_text)
        queue_path.write_text(altered_text)
        intake = self.director('run-dispatch', request)
        self.assertEqual(intake['result'],original_intake['observed_result'])
        self.assertEqual(intake['result']['id'],batch_id)
        self.assertEqual(set(original_intake['receipt']['pending_definition_sha256s']),
                         {item['id'] for item in intake['result']['items']})
        items = intake['result']['items']
        self.assertEqual([(item['priority'],item['topic'],item['intake_batch_ids']) for item in items],
                         [(495,'mvp-five',[batch_id]),(245,'mvp-zero',[batch_id]),(175,'mvp-two',[batch_id])])
        pending_ids = [item['id'] for item in items]
        self.assertNotIn('pending_depends_on',items[0])
        self.assertEqual(items[1]['pending_depends_on'],[pending_ids[2]])
        runtime = self.parent/AGENTS/'skill-tree-director-setup/scripts/runtime/common/scripts'
        director = SimpleNamespace(**runpy.run_path(str(runtime/'director-state.py')))
        routing = runpy.run_path(str(runtime/'director-project-routing.py'))
        project = {'checkout':str(self.parent),'allowed_effects':['preview','process']}
        route = routing['task_preview'](director,{'project':project},{'task_ids':pending_ids},'process','director')
        self.assertEqual(route['task_ids'],pending_ids)
        self.assertIn('director-batch-processing-requires-frozen-intake-receipt',route['limitations'])
        self.assertEqual(route['tasks'][1]['pending_depends_on'],[pending_ids[2]])
        before = snapshot(queue_path,state_path)
        replay = self.director('run-dispatch', request)
        self.assertEqual((replay['status'],replay['result']),('replayed',intake['result']))
        self.assertEqual(snapshot(queue_path,state_path),before)

        mapped = dict(zip(keys,pending_ids))
        proposal = {
            'expected_source_hash':sha(queue_path.read_bytes()),
            'selectors':pending_ids, 'dispositions':{mapped[key]:entry for key,entry in approved['dispositions'].items()},
            'tasks':[{**item, 'parent_pending_ids':[mapped[key] for key in item['parent_pending_ids']]}
                     for item in approved['tasks']],
        }
        process = {**request,'operation':'process','expected_run_sha256':intake['run_sha256'],'request':proposal}
        self.director('run-dispatch',process,error='exact staged Pending batch definition changed')
        self.assertEqual(snapshot(queue_path,state_path),before)
        queue_path.write_text(canonical_text)
        proposal['expected_source_hash'] = sha(queue_path.read_bytes())
        before = snapshot(queue_path,state_path)
        for wrong_ids in ([pending_ids[0]], [*pending_ids,other['id']], list(reversed(pending_ids))):
            self.director('run-dispatch', {**process,'request':{**proposal,'selectors':wrong_ids}}, error='exact recorded batch')
        intake_receipt = self.parent/'.skill-tree/history/director-dispatch'/f"{original_intake['dispatch_key']}.json"
        retained_intake = intake_receipt.read_bytes()
        intake_receipt.unlink()
        try:
            self.director('run-dispatch',process,error='Original canonical intake batch receipt is unavailable')
            self.assertEqual(snapshot(queue_path,state_path),before)
        finally:
            intake_receipt.write_bytes(retained_intake)
        changed = [{**proposal['tasks'][0],'depends_on':['@foreign']}, *proposal['tasks'][1:]]
        self.director('run-dispatch', {**process,'request':{**proposal,'tasks':changed}}, error='owner-approved batch')
        self.assertEqual(snapshot(queue_path,state_path),before)

        process_input = write(self.base,'lost-batch-process-ack.json',json.dumps(process))
        self.command(sys.executable,'-B','-c',fault,parent_entry,'lost-ack','run-dispatch',self.parent,'--input',process_input,
                     error='Injected loss after canonical acknowledgement')
        published = snapshot(queue_path,state_path)
        self.assertNotEqual(published,before)
        original = self.core(self.parent,'director-dispatch-read',{'operation':'process','director_dispatch':scope})
        confirmed = json.loads(self.command(sys.executable,'-B','-c',fault,parent_entry,'pause',
            'run-dispatch',self.parent,'--input',process_input))
        self.assertEqual(confirmed['result'],original['observed_result'])
        paused = self.director('run-status',run_ref)
        self.assertEqual(paused['phase'],'paused')
        resumed = self.director('run-resume',{**run_ref,'expected_run_sha256':paused['run_sha256']})
        self.assertEqual(resumed['phase'],'completed')
        consumer_id, storage_id, adapter_id = confirmed['result']['created_ids']
        consumer = self.core(self.parent,'read',None,'--id',consumer_id)
        storage = self.core(self.parent,'read',None,'--id',storage_id)
        adapter = self.core(self.parent,'read',None,'--id',adapter_id)
        self.assertEqual(consumer['depends_on'],[storage_id])
        self.assertEqual(storage['depends_on'],[adapter_id])
        self.assertEqual(adapter['depends_on'],[])
        self.assertEqual([(task['priority'],task['topic'],task['intake_batch_ids']) for task in (consumer,storage,adapter)],
                         [(495,'mvp-five',[batch_id]),(245,'mvp-zero',[batch_id]),(175,'mvp-two',[batch_id])])
        self.assertEqual(self.core(self.parent,'read',None,'--id',other['id'])['id'],other['id'])
        self.assertEqual(self.director('run-dispatch',process)['result'],confirmed['result'])
        self.assertEqual(self.director('run-dispatch',request)['result'],intake['result'])
        self.assertEqual(snapshot(queue_path,state_path),published)
        run_status = self.director('run-status',run_ref)
        self.assertEqual(run_status['phase'],'completed')
        status = run_status['assignments'][assignment['id']]
        self.assertEqual(status['completed']['kind'],'canonical-queue-receipts')
        self.assertEqual(status['completed']['receipts']['process'],original['receipt']['receipt_sha256'])
        self.assertEqual(status['dispatches']['process']['result']['created_ids'],[consumer_id,storage_id,adapter_id])
        self.assertIsNone(status['next'])
        self.director('run-complete-assignment',{**run_ref,'assignment_id':assignment['id'],
            'expected_run_sha256':resumed['run_sha256'],'outcome_id':identity('O')},
            error='cannot represent a terminal child run')
        self.assertFalse(read_json(state_path)['run_registry']['runs'])


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
        start = {**key, 'expected_run_sha256': parent['run_sha256'], 'assignment_id': 'game-run', 'operation': 'start',
                 'request': {'expected_source_hash': sha((self.external/QUEUE).read_bytes()),
                             'local_base': True, 'local_base_authorization': 'Disposable local fixture.',
                             'base_branch': 'develop', 'branch': 'codex/topology-game', 'worktree': str(worktree)}}
        launch = self.director('run-dispatch', start)
        external_run = launch['result']['id']
        marker = Path(self.git(worktree, 'rev-parse', '--absolute-git-dir').strip())/'skill-tree-owner.json'
        marker_bytes = marker.read_bytes()
        marker.write_text(json.dumps({**json.loads(marker_bytes), 'token': str(uuid4())}))
        self.director('run-dispatch', start, error='Original Director run reservation is unavailable or changed')
        marker.write_bytes(marker_bytes)
        selector = ('--run-id', external_run)
        handoff = launch['result']['profile_handoff']
        self.assertEqual(handoff['run_id'], external_run)
        self.assertEqual(self.director('run-status',key)['assignments']['game-run']['profile_handoff'],handoff)
        self.assertEqual(json.loads(self.command(*handoff['argv']))['status'],'admitted')
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

    def test_managed_implement_all_keeps_full_snapshot_and_dispatches_compatible_work(self):
        self.register()
        assignments = []
        definitions = [
            ('source-first', 'source.txt', []),
            ('resource-first', 'resource.txt', []),
            ('source-later', 'source.txt', ['source-first']),
        ]
        for name, relative, depends_on in definitions:
            child = self.child_task(self.external, ['game/' + relative], f'Check {name} input')
            assignments.append({
                'id': name, 'role': 'unity', 'area_id': 'game', 'workspace': 'recorded-worktree',
                'child': child, 'capability': 'core-task', 'write_paths': [relative], 'resources': [],
                'pins': [], 'depends_on': depends_on, 'expected_result': 'The registered path stays in scope.',
                'check': 'scope-check', 'authority_ref': 'fixture-owner', 'effects': ['launch'],
                'stop_rules': ['Keep the recorded project scope.'],
            })
        selected = self.freeze(None, assignments=assignments)
        key = {'director_run_id': identity('DR')}
        launch_inputs = {**selected, **key, 'assignment_ids': [row['id'] for row in assignments],
            'owner': {'actor': 'fixture-owner', 'reference': 'fixture-batches', 'kind': 'owner-message'},
            'authority': {row['id']: ['launch'] for row in assignments}, 'approved_defaults': [],
            'implement_all': {'expected_source_hash': sha((self.external / QUEUE).read_bytes()), 'workers': 2}}
        run = self.director('run-start', launch_inputs)
        self.assertEqual(set(run['implement_all']['snapshot_ids']),
                         {row['child']['task_id'] for row in assignments})

        later = self.child_task(self.external, ['game/resource.txt'], 'Check later unrelated input')
        self.assertEqual(self.director('run-start', launch_inputs)['run_sha256'], run['run_sha256'])
        first = self.director('run-advance-all', {**key, 'expected_run_sha256': run['run_sha256']}, family='run')
        self.assertEqual({entry['assignment_id'] for entry in first['launches']},
                         {'source-first', 'resource-first'})
        self.assertEqual(first['phase'], 'running')
        second = self.director('run-advance-all', {**key, 'expected_run_sha256': first['run_sha256']}, family='run')
        self.assertEqual(second['launches'], [])
        self.assertNotIn(later['task_id'], second['implement_all']['snapshot_ids'])
        self.assertIn(assignments[-1]['child']['task_id'], second['implement_all']['remaining_ids'])
        original = next(entry for entry in first['launches'] if entry['assignment_id'] == 'source-first')
        replay = self.director('run-dispatch', {**key, 'expected_run_sha256': second['run_sha256'],
            'assignment_id': 'source-first', 'operation': 'start',
            'request': {'expected_source_hash': sha((self.external / QUEUE).read_bytes()), 'base_branch': 'develop',
                        'local_base': True, 'local_base_authorization': 'fixture-batches'}})
        self.assertEqual(replay['status'], 'replayed')
        self.assertEqual(replay['result']['id'], original['result']['id'])

        self.git(self.external, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '--allow-empty', '-m', 'Advance outside the managed run')
        drift = self.director('run-advance-all', {**key, 'expected_run_sha256': second['run_sha256']}, family='run')
        self.assertEqual(drift['launches'], [])
        self.assertIn('outside the checked Implement All child receipts', drift['implement_all']['gate'])
        self.assertEqual(drift['implement_all']['remaining_ids'], second['implement_all']['remaining_ids'])

    def commit_and_incorporate_managed_fixture(self, key, launch, task_id, relative):
        root = self.parent
        run_id = launch['result']['id']
        common = Path(self.git(root, 'rev-parse', '--git-common-dir').strip())
        if not common.is_absolute():
            common = root / common
        workspace = Path(read_json(common / 'skill-tree-runtime.json')['worktrees'][run_id])
        wf = runpy.run_path(str(SOURCE / 'common/scripts/workflow-state.py'))['main'].__globals__
        store = wf['Store'](workspace, run_id)
        selection = wf['advance'](store)
        self.assertEqual(selection['task_id'], task_id)
        if selection.get('profile_handoff'):
            self.assertEqual(wf['prepare_worktree_profile'](store)['status'],'admitted')
        wf['begin_task'](store, {'task_id': task_id})
        content = f'Accepted {task_id} in the managed fixture.\n'
        write(workspace, relative, content)
        proof = f'.skill-tree/run-evidence/{run_id.lower()}/fixture.txt'
        write(workspace, proof, (workspace / relative).read_text())
        self.assertEqual((workspace / proof).read_text(), content)
        wf['mark_implemented'](store, {'task_id': task_id, 'changed_files': [relative, proof]})
        check = wf['prepare_check'](store, {'task_id': task_id, 'check_id': 'scope-check'})
        wf['record_check'](store, {'task_id': task_id, 'check_id': 'scope-check', 'attempt_id': check['attempt_id'],
            'result': 'pass', 'classification': 'executed-control', 'actual_lane': check['recipe']['lane'],
            'environment_identity': check['environment_identity'], 'cleanup': 'The local fixture file was read.',
            'evidence': [proof], 'assertions': [{'assertion': check['assertion'], 'result': 'pass'}]})
        # Isolate review policy for the regression. All Core receipts, commits and Git merges are real fixture effects.
        review = identity('DO')
        with patch.dict(wf, {'verified_implementation_review': lambda *args: {'orchestration_hash': 'a' * 64}}):
            outcome = wf['complete'](store, {'task_id': task_id, 'review_id': review,
                'outcome': 'The fixture source contains the accepted change.',
                'source_fingerprints': wf['fingerprints'](store, [relative]),
                'acceptance': [{'criterion': check['assertion'], 'result': 'pass', 'evidence': [proof]}]})
            wf['advance'](store)
            wf['finish'](store, {'review_id': review})
            status = self.director('run-status', key)
            self.director('run-complete-assignment', {**key, 'expected_run_sha256': status['run_sha256'],
                'assignment_id': launch['assignment_id'], 'outcome_id': outcome['id']})
            waiting = self.director('run-status', key)
            before_merge = self.director('run-advance-all', {**key, 'expected_run_sha256': waiting['run_sha256']}, family='run')
            self.assertEqual((before_merge['phase'], before_merge['launches']), ('running', []))
            self.assertIn(task_id, before_merge['implement_all']['remaining_ids'])
            merged = wf['merge_reviewed_controller'](store, {'owner_instruction': 'Integrate the checked disposable fixture branch.'})
        self.assertEqual(merged['delivery']['status'], 'merged')
        self.assertEqual((root / relative).read_text(), content)
        return self.director('run-status', key)

    def test_managed_implement_all_resumes_after_verified_incorporation(self):
        self.declaration['areas'][0]['allowed_effects'].append('launch')
        self.git(self.parent, 'config', 'user.name', 'Director Fixture')
        self.git(self.parent, 'config', 'user.email', 'fixture@example.invalid')
        write(self.parent, 'story/consumer.txt', 'Original consumer input.\n')
        self.git(self.parent, 'add', '--', 'story/consumer.txt')
        self.git(self.parent, 'commit', '-m', 'Add the managed consumer fixture')
        self.register()
        first = self.child_task(self.parent, ['story/source.txt'], 'Check managed producer')
        second = self.child_task(self.parent, ['story/consumer.txt'], 'Check managed consumer', [first['task_id']])
        assignments = []
        for name, child, file, depends_on in [
            ('producer', first, 'source.txt', []),
            ('consumer', second, 'consumer.txt', ['producer']),
        ]:
            assignments.append({'id': name, 'role': 'narrative', 'area_id': 'story',
                'workspace': 'recorded-worktree', 'child': child, 'capability': 'core-task',
                'write_paths': [file], 'depends_on': depends_on, 'resources': [], 'pins': [],
                'expected_result': 'The checked target contains the approved change.', 'check': 'scope-check',
                'authority_ref': 'fixture-owner', 'effects': ['launch'], 'stop_rules': ['Preserve the approved scope.']})
        selected = self.freeze(None, assignments=assignments)
        key = {'director_run_id': identity('DR')}
        run = self.director('run-start', {**selected, **key, 'assignment_ids': ['producer', 'consumer'],
            'owner': {'actor': 'fixture-owner', 'reference': 'fixture-managed-integration', 'kind': 'owner-message'},
            'authority': {'producer': ['launch'], 'consumer': ['launch']}, 'approved_defaults': [],
            'implement_all': {'expected_source_hash': sha((self.parent / QUEUE).read_bytes()), 'workers': 1}})
        wave = self.director('run-advance-all', {**key, 'expected_run_sha256': run['run_sha256']}, family='run')
        self.assertEqual([row['assignment_id'] for row in wave['launches']], ['producer'])
        status = self.commit_and_incorporate_managed_fixture(key, wave['launches'][0], first['task_id'], 'story/source.txt')
        wave = self.director('run-advance-all', {**key, 'expected_run_sha256': status['run_sha256']}, family='run')
        self.assertEqual([row['assignment_id'] for row in wave['launches']], ['consumer'])
        status = self.commit_and_incorporate_managed_fixture(key, wave['launches'][0], second['task_id'], 'story/consumer.txt')
        final = self.director('run-advance-all', {**key, 'expected_run_sha256': status['run_sha256']}, family='run')
        self.assertEqual(final['phase'], 'completed')
        self.assertEqual(final['implement_all']['remaining_ids'], [])
        self.assertEqual(final['launches'], [])

    def supervised_launches(self, *, progress_timeout=10, heartbeat_timeout=8):
        self.declaration['areas'][0]['allowed_effects'].append('launch')
        self.declaration['areas'][1]['allowed_effects'].append('launch')
        self.register()
        specs = [
            ('game', 'unity', self.external, ['fixture-editor'], []),
            ('story', 'narrative', self.parent, [], []),
            ('art', 'art', self.parent, [], []),
            ('story-followup', 'narrative', self.parent, [], ['story']),
        ]
        assignments = []
        for name, role, root, resources, depends_on in specs:
            area = 'story' if name == 'story-followup' else name
            files = ['source.txt', 'resource.txt'] if name == 'game' else ['source.txt']
            task = self.child_task(root, [area + '/' + path for path in files], f'Check {name} input')
            assignments.append({'id': name, 'role': role, 'area_id': area, 'workspace': 'recorded-worktree',
                                'child': task, 'capability': 'core-task', 'write_paths': files,
                                'resources': resources, 'pins': [], 'depends_on': depends_on,
                                'expected_result': 'The registered path stays in scope.', 'check': 'scope-check',
                                'authority_ref': 'fixture-owner', 'effects': ['launch'],
                                'stop_rules': ['Keep the recorded project scope.']})
        selected = self.freeze(None, assignments=assignments)
        self.supervised_key = {'director_run_id': identity('DR')}
        self.director('run-start', {**selected, **self.supervised_key,
            'assignment_ids': [assignment['id'] for assignment in assignments],
            'owner': {'actor': 'fixture-owner', 'reference': 'fixture-supervision', 'kind': 'owner-message'},
            'authority': {assignment['id']: ['launch'] for assignment in assignments}, 'approved_defaults': [],
            'supervision': {'host': socket.gethostname(), 'progress_timeout_seconds': progress_timeout,
                            'heartbeat_timeout_seconds': heartbeat_timeout},
        })
        launches = {}
        for (name, _, root, resources, _), assignment in zip(specs, assignments):
            inspected = self.director('run-status', self.supervised_key)
            coordinator = self.base / (name + '-coordinator')
            dispatch = {**self.supervised_key, 'expected_run_sha256': inspected['run_sha256'],
                        'assignment_id': name, 'operation': 'start',
                        'request': {'expected_source_hash': sha((root / QUEUE).read_bytes()), 'local_base': True,
                                    'local_base_authorization': 'Disposable supervised topology fixture.',
                                    'base_branch': 'develop', 'branch': 'codex/topology-' + name,
                                    'worktree': str(coordinator)}}
            if name == 'story-followup':
                self.assertEqual(inspected['assignments'][name]['dependencies'], ['story'])
                self.assertFalse(self.director('run-dispatch', dispatch, error=r'(?i)not eligible')['ok'])
                self.assertFalse(coordinator.exists())
                continue
            launch = self.director('run-dispatch', dispatch)['result']
            self.assertRegex(launch['id'], r'^WR-')
            self.assertEqual(Path(self.git(coordinator, 'rev-parse', '--show-toplevel').strip()), coordinator)
            scope = {'assignment_id':name,'child_run_id':launch['id'],'task_id':assignment['child']['task_id']}
            handoff = launch['profile_handoff']
            inspected = self.director('run-status',self.supervised_key)
            self.assertEqual(inspected['assignments'][name]['profile_handoff'],handoff)
            if name == 'game':
                held = self.supervision_request('assign',**scope,role='supervisor',
                    unit_id='profile-held',generation=1,actor_id='fixture-profile-hold')
                self.director('run-supervise',held,family='run',error='initial child worktree profile')
            receipt = read_json(root / '.skill-tree/installation/profile.json')
            operations = sorted({item['name'] for item in receipt['destinations'].values()})
            self.install(coordinator, receipt['flavor'], *operations)
            launches[name] = (scope,coordinator,resources)
        for scope, coordinator, _ in launches.values():
            selector = ('--run-id', scope['child_run_id'])
            self.core(coordinator, 'admit', None, *selector)
            self.core(coordinator, 'checkpoint', {'phase': 'implement', 'stop_reason': None}, *selector)
        self.supervised_time = datetime.now(timezone.utc)
        return launches

    def supervision_request(self, action, **fields):
        observed = self.director('run-supervise', {**self.supervised_key, 'action': 'status'}, family='run')
        return {**self.supervised_key, 'action': action, 'expected_run_sha256': observed['run_sha256'],
                'request_id': identity('fixture-request'), **fields}

    def run_supervision_at(self, payload, seconds, *, writer_collision=None):
        # Inject only UTC time into the installed implementation. Process observations remain local and live.
        clock = (self.supervised_time + timedelta(seconds=seconds)).isoformat()
        path = write(self.base, identity('supervision') + '.json', json.dumps(payload))
        entry = self.parent / AGENTS / 'skill-tree-director-run/scripts/runtime/common/scripts/director-state.py'
        tick = '''from contextlib import ExitStack, contextmanager
from datetime import datetime
from pathlib import Path
import runpy
import sys

director = runpy.run_path(sys.argv[1])
load = director['WF'].owned_module
now = datetime.fromisoformat(sys.argv[2])
if sys.argv[3] != '-':
    workflow = director['WF']
    lock = workflow.Store.lock

    @contextmanager
    def observed_lock(store, **arguments):
        with ExitStack() as writer:
            try:
                writer.enter_context(lock(store, **arguments))
            except workflow.WorkflowError as error:
                if isinstance(error.__cause__, FileExistsError) and str(error).startswith('Writer lock exists;'):
                    Path(sys.argv[3]).touch()
                raise
            yield

    workflow.Store.lock = observed_lock

def with_clock(name, path):
    helper = load(name, path)
    if name == 'director_run':
        helper.DirectorRun._supervise_now = lambda self: now
    return helper

director['WF'].owned_module = with_clock
raise SystemExit(director['main'](sys.argv[4:]))
'''
        result = subprocess.run([sys.executable, '-B', '-c', tick, str(entry), clock,
                                 str(writer_collision) if writer_collision else '-',
                                 'run-supervise', str(self.parent), '--input', str(path)],
                                cwd=self.base, env=GIT_ENV, capture_output=True, text=True, timeout=60)
        try:
            return result.returncode, json.loads(result.stdout or result.stderr)
        except json.JSONDecodeError:
            self.fail(result.stdout + result.stderr)

    def supervise(self, action, seconds, *, error=None, **fields):
        request = self.supervision_request(action, **fields)
        status, response = self.run_supervision_at(request, seconds)
        if error is None:
            self.assertEqual(status, 0, response)
        else:
            self.assertEqual(status, 2, response)
            self.assertRegex(response['error'], error)
        return response

    def supervised_writer(self, launch, name, **fields):
        scope, coordinator, resources = launch
        worktree = self.base / (name + '-worker')
        base = self.git(coordinator, 'rev-parse', 'HEAD').strip()
        self.git(coordinator, 'worktree', 'add', '--detach', worktree, base)
        return {**scope, 'role': 'worker', 'unit_id': name, 'generation': 1, 'actor_id': name + '-actor',
                'worktree': str(worktree), 'base': base, 'paths': [scope['assignment_id'] + '/source.txt'],
                'resources': resources, **fields}

    def fixture_process_group(self):
        process = subprocess.Popen([sys.executable, '-B', '-c', 'import signal; signal.pause()'],
                                   cwd=self.base, env=GIT_ENV, start_new_session=True)
        self.addCleanup(self.stop_fixture_group, process)
        self.assertEqual(os.getpgid(process.pid), process.pid)
        return process, {'pid': process.pid, 'pgid': process.pid}

    def stop_fixture_group(self, process):
        if process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)

    def supervised_candidate(self, worker):
        root = Path(worker['worktree'])
        path = worker['paths'][0]
        content = f"Checked {worker['unit_id']} generation {worker['generation']}.\n"
        write(root, path, content)
        self.git(root, 'add', '--', path)
        self.git(root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'Update admitted fixture source')
        head = self.git(root, 'rev-parse', 'HEAD').strip()
        checked = self.git(root, 'show', f'{head}:{path}')
        self.assertEqual(checked, content)
        artifact = '.skill-tree/artifacts/fixture-check.txt'
        written = write(root, artifact, checked)
        return {'head': head, 'checks': [{'id': 'scope-check', 'path': artifact, 'sha256': sha(written.read_bytes())}]}

    def test_supervised_pickup_timeout_recovers_unbound_supervisor_and_worker(self):
        launches = self.supervised_launches()
        supervisor = {'unit_id': 'game-supervisor', 'generation': 1, 'actor_id': 'old-supervisor'}
        worker = self.supervised_writer(launches['story'], 'unbound-worker')
        actor = {key: worker[key] for key in ('unit_id', 'generation', 'actor_id')}
        self.supervise('assign', 0, **launches['game'][0], role='supervisor', **supervisor)
        self.supervise('assign', 0, **worker)
        self.assertEqual(self.supervise('sweep', 10)['stalled'], sorted([actor['unit_id'], supervisor['unit_id']]))
        process, group = self.fixture_process_group()
        self.supervise('pickup', 10, **actor, process=group, error='Retired or stale')
        for attempt in (supervisor, actor):
            observed = {'kind': 'host-stopped-unbound', 'actor_id': attempt['actor_id'],
                        'host': socket.gethostname(), 'reference': 'fixture attempt reconciled by host',
                        'process_groups': []}
            self.supervise('recover', 10, **attempt, stop_observation={**observed, 'actor_id': 'wrong'},
                           error='exact stalled local host-stop observation')
            if attempt == actor:
                observed['process_groups'] = [group['pgid']]
                self.supervise('recover', 10, **attempt, stop_observation=observed, error='still exists')
                self.stop_fixture_group(process)
            self.assertEqual(self.supervise('recover', 11, **attempt, stop_observation=observed)['status'], 'stopped')
        replacement = self.supervised_writer(launches['story'], 'pickup-replacement', unit_id=actor['unit_id'], generation=2)
        self.supervise('assign', 12, **replacement)
        self.supervise('pickup', 12, **actor, process=group, error='Retired or stale')
        self.supervise('assign', 12, **launches['game'][0], role='supervisor',
                       **{**supervisor, 'generation': 2, 'actor_id': 'replacement-supervisor'})

    def test_supervised_heartbeat_progress_and_submission_survive_contention(self):
        launches = self.supervised_launches()
        parent = {'unit_id': 'game-parent', 'generation': 1, 'actor_id': 'game-parent-actor'}
        worker = self.supervised_writer(launches['game'], 'game-worker', parent_unit_id=parent['unit_id'])
        sibling = self.supervised_writer(launches['story'], 'story-worker')
        def actor(item):
            return {field: item[field] for field in ('unit_id', 'generation', 'actor_id')}

        self.supervise('assign', 0, **launches['game'][0], role='supervisor', **parent)
        parent_process, parent_group = self.fixture_process_group()
        self.supervise('pickup', 0, **parent, process=parent_group)
        self.supervise('assign', 0, **worker)
        self.supervise('assign', 0, **sibling)
        worker_process, worker_group = self.fixture_process_group()
        sibling_process, sibling_group = self.fixture_process_group()
        self.supervise('pickup', 1, **actor(worker), process=worker_group)
        self.supervise('pickup', 1, **actor(sibling), process=sibling_group)
        self.supervise('wait', 2, **parent, reason='nested-result', reference=worker['unit_id'])
        self.supervised_candidate(worker)
        result = self.supervised_candidate(sibling)
        self.stop_fixture_group(sibling_process)

        heartbeat = self.supervision_request('heartbeat', **parent)
        progress = self.supervision_request('progress', **actor(worker), reference='observed-worktree-check')
        submission = self.supervision_request('submit', **actor(sibling), result=result)
        self.assertEqual(len({request['expected_run_sha256'] for request in (heartbeat, progress, submission)}), 1)
        writer_lock = self.parent / '.skill-tree/.writer-lock'
        collisions = [self.base / identity('observed-writer-collision') for _ in range(3)]
        with ThreadPoolExecutor(max_workers=3) as pool:
            writer_lock.touch(exist_ok=False)
            try:
                futures = [pool.submit(self.run_supervision_at, request, 3, writer_collision=collision)
                           for request, collision in zip((heartbeat, progress, submission), collisions)]
                deadline = time.monotonic() + 5
                while not any(collision.exists() for collision in collisions) and time.monotonic() < deadline:
                    time.sleep(0.01)
            finally:
                writer_lock.unlink()
            results = [item.result() for item in futures]
        self.assertTrue(any(collision.exists() for collision in collisions), results)
        self.assertTrue(all(code == 0 for code, _ in results), results)
        parent_attempt, worker_attempt, sibling_attempt = [out['attempt'] for _, out in results]
        self.assertGreater(parent_attempt['last_heartbeat_at'], parent_attempt['last_progress_at'])
        self.assertEqual(worker_attempt['progress_reference'], 'observed-worktree-check')
        self.assertEqual(sibling_attempt['candidate']['head'], result['head'])
        self.assertTrue(sibling_attempt['receipt_sha256'])

        code, replayed = self.run_supervision_at(progress, 4)
        self.assertEqual((code, replayed['status']), (0, 'replayed'))
        self.assertEqual(replayed['attempt']['last_progress_at'], worker_attempt['last_progress_at'])
        changed = {**progress, 'reference': 'changed-original-request'}
        code, refused = self.run_supervision_at(changed, 4)
        self.assertEqual(code, 2)
        self.assertIn('request ID was reused', refused['error'])
        unknown = self.supervision_request('heartbeat', **parent, expected_run_sha256='0' * 64)
        code, refused = self.run_supervision_at(unknown, 4)
        self.assertEqual(code, 2)
        self.assertIn('run changed since inspection', refused['error'])

        run_file = self.parent / '.skill-tree/director/runs' / (self.supervised_key['director_run_id'].lower() + '.json')
        saved = run_file.read_bytes()
        external = json.loads(saved)
        external['timeline'].append({'event': 'fixture-unrelated-run-change'})
        run_file.write_text(json.dumps(external, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
        try:
            code, refused = self.run_supervision_at({**heartbeat, 'request_id': identity('outside-change')}, 4)
            self.assertEqual(code, 2)
            self.assertIn('run changed since inspection', refused['error'])
        finally:
            run_file.write_bytes(saved)

        strict = self.supervision_request('sweep')
        self.assertEqual(self.run_supervision_at(strict, 4)[0], 0)
        self.assertEqual(self.run_supervision_at({**heartbeat, 'request_id': identity('stale-heartbeat')}, 5)[0], 2)
        self.assertIsNone(parent_process.poll())
        self.assertIsNone(worker_process.poll())

    def test_supervised_nested_stall_preserves_sibling_and_fences_replacement(self):
        launches = self.supervised_launches()
        original_targets = [self.git(root, 'rev-parse', 'develop') for root in (self.parent, self.external)]
        parent = {'unit_id': 'game-parent', 'generation': 1, 'actor_id': 'game-parent-actor'}
        self.supervise('assign', 0, **launches['game'][0], role='supervisor', **parent)
        parent_process, parent_group = self.fixture_process_group()
        self.supervise('pickup', 0, **parent, process=parent_group)
        nested = [self.supervised_writer(launches['game'], name, parent_unit_id=parent['unit_id'], paths=[path])
                  for name, path in [('game-first', 'game/source.txt'), ('game-contender', 'game/resource.txt')]]
        requests = [self.supervision_request('assign', **worker) for worker in nested]
        self.assertEqual(requests[0]['expected_run_sha256'], requests[1]['expected_run_sha256'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda request: self.run_supervision_at(request, 0), requests))
        self.assertEqual(sorted(code for code, _ in results), [0, 2], results)
        winner = next(index for index, (code, _) in enumerate(results) if code == 0)
        self.assertRegex(results[1 - winner][1]['error'], r'Writer lock exists|run changed since inspection')
        game = nested[winner]
        other = nested[1 - winner]
        self.supervise('assign', 0, **other, error=r'(?i)exclusive resource')
        art = self.supervised_writer(launches['art'], 'art-competitor')
        story = self.supervised_writer(launches['story'], 'story-independent')
        self.supervise('assign', 0, **story, depends_on=[game['unit_id']], error=r'(?i)unresolved prerequisite')
        self.supervise('assign', 0, **story)
        self.supervise('assign', 0, **art, error=r'(?i)no free implementation slot')

        def actor(worker):
            return {field: worker[field] for field in ('unit_id', 'generation', 'actor_id')}

        old_process, old_group = self.fixture_process_group()
        sibling_process, sibling_group = self.fixture_process_group()
        self.supervise('pickup', 1, **actor(game), process=old_group)
        waiting = self.supervise('wait', 6, **parent, reason='nested-result', reference=game['unit_id'])['attempt']
        self.assertEqual(waiting['wait']['reason'], 'nested-result')
        self.supervise('heartbeat', 7, **actor(game))
        self.supervise('heartbeat', 7, **parent)
        self.supervise('pickup', 8, **actor(story), process=sibling_group)
        beat = self.supervise('heartbeat', 10, **actor(game))['attempt']
        self.supervise('heartbeat', 10, **parent)
        self.assertGreater(beat['last_heartbeat_at'], beat['last_progress_at'])
        swept = self.supervise('sweep', 12)
        self.assertEqual(swept['stalled'], [game['unit_id']])
        self.supervise('progress', 12, **parent, reference='fixture-observed-stalled-child')

        # A made-for-test host observation never substitutes for actual local process cleanup.
        stop = {'kind': 'host-stopped', 'host': socket.gethostname(), 'actor_id': game['actor_id'],
                **old_group, 'reference': 'fixture-only-lifecycle-observation'}
        self.supervise('recover', 12, **actor(game), stop_observation=stop, error=r'(?i)still exists')
        self.assertIsNone(old_process.poll())
        replaced_checkout = self.supervised_writer(launches['game'], 'game-replacement')
        replacement = {**replaced_checkout, 'unit_id': game['unit_id'], 'generation': 2,
                       'parent_unit_id': parent['unit_id'], 'paths': game['paths']}
        self.supervise('assign', 12, **replacement, error=r'(?i)stopp|recover|generation')
        stale = self.supervised_candidate(game)

        sibling = self.supervised_candidate(story)
        self.supervise('progress', 13, **actor(story), reference='fixture-candidate-advanced')
        self.assertIsNone(sibling_process.poll())
        self.stop_fixture_group(sibling_process)
        submission = self.supervision_request('submit', **actor(story), result=sibling)
        submitted_code, submitted = self.run_supervision_at(submission, 13)
        self.assertEqual(submitted_code, 0, submitted)
        self.assertEqual(submitted['attempt']['candidate']['head'], sibling['head'])
        self.assertEqual(submitted['attempt']['candidate']['paths'], story['paths'])
        self.supervise('assign', 13, **other, error=r'(?i)exclusive resource')

        self.stop_fixture_group(old_process)
        with self.assertRaises(ProcessLookupError):
            os.killpg(old_group['pgid'], 0)
        self.assertIsNone(parent_process.poll())
        self.supervise('recover', 13, **actor(game), stop_observation={**stop, 'actor_id': story['actor_id']},
                       error=r'(?i)host.stop|observation')
        recovered = self.supervise('recover', 13, **actor(game), stop_observation=stop)
        self.assertEqual(recovered['attempt']['status'], 'stopped')
        self.supervise('submit', 13, **actor(game), result=stale, error=r'(?i)retired or stale')
        self.supervise('assign', 14, **replacement)
        self.supervise('submit', 14, **actor(game), result=stale, error=r'(?i)retired or stale')
        duplicate_code, duplicate = self.run_supervision_at(submission, 14)
        self.assertEqual(duplicate_code, 0, duplicate)
        self.assertEqual(duplicate['status'], 'replayed')
        self.assertEqual(duplicate['attempt']['receipt_sha256'], submitted['attempt']['receipt_sha256'])
        changed_code, changed = self.run_supervision_at({**submission, 'result': stale}, 14)
        self.assertEqual(changed_code, 2, changed)
        self.assertRegex(changed['error'], r'(?i)request id was reused with different input')

        new_process, new_group = self.fixture_process_group()
        self.supervise('pickup', 14, **actor(replacement), process=new_group)
        self.supervise('wait', 14, **parent, reason='nested-result', reference=replacement['unit_id'])
        candidate = self.supervised_candidate(replacement)
        self.supervise('progress', 15, **actor(replacement), reference='fixture-replacement-advanced')
        self.supervise('heartbeat', 17, **parent)
        self.supervise('heartbeat', 21, **actor(replacement))
        parent_heartbeat = self.supervise('heartbeat', 22, **parent)['attempt']['last_heartbeat_at']
        self.stop_fixture_group(new_process)
        accepted = self.supervise('submit', 23, **actor(replacement), result=candidate)['attempt']
        self.assertEqual(accepted['candidate']['head'], candidate['head'])
        self.stop_fixture_group(parent_process)
        finished_parent = self.supervise('submit', 24, **parent)['attempt']
        self.assertEqual(finished_parent['status'], 'completed')
        self.assertEqual(finished_parent['last_progress_at'], accepted['verified_at'])
        self.assertEqual(finished_parent['last_heartbeat_at'], parent_heartbeat)
        self.supervise('assign', 25, **art)
        overlap = self.supervised_writer(launches['art'], 'art-overlap')
        self.supervise('assign', 25, **overlap, error=r'(?i)overlapping supervised write scope')
        view = self.director('run-supervise', {**self.supervised_key, 'action': 'status'}, family='run')
        units = view['supervision']['units']
        self.assertEqual(units[story['unit_id']]['attempts']['1']['receipt_sha256'], submitted['attempt']['receipt_sha256'])
        self.assertEqual(units[game['unit_id']]['attempts']['1']['status'], 'stopped')
        self.assertEqual(units[game['unit_id']]['attempts']['1']['stalled_reason'], 'progress-timeout')
        self.assertEqual(units[game['unit_id']]['attempts']['2']['status'], 'completed')
        self.assertEqual([self.git(root, 'rev-parse', 'develop') for root in (self.parent, self.external)], original_targets)


if __name__ == '__main__':
    unittest.main()
