from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


CORE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('director_bindings', CORE / 'common/scripts/director-state.py')
DIRECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DIRECTOR)
WF = DIRECTOR.WF
WS = DIRECTOR.WS


class DirectorAreaBindingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.parent = self.base / 'director'
        self.parent.mkdir()
        self.repo = self.base / 'project'
        self.queue = self.init_repo(self.repo)
        self.director = DIRECTOR.DirectorRegistry(self.parent)
        self.maint = self.area('maintenance', 'source-maintenance', self.repo, '.skill-tree')
        self.story = self.area('story', 'narrative', self.repo, 'story')
        self.art = self.area('art', 'art', self.repo, 'art')
        self.request = {'director_id': 'lantern-pilot', 'areas': [self.maint, self.story, self.art]}

    def git(self, repo, *args):
        return WS.local_git_text(repo, *args)

    def init_repo(self, repo, label='original'):
        repo.mkdir()
        self.git(repo, 'init', '-b', 'develop')
        docs = repo / '.skill-tree/documents'
        docs.mkdir(parents=True)
        (docs / 'future.md').write_text('# Future\n\n## Pending Task Format\n\nFixed fields.\n\n'
                                      '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = repo / '.skill-tree/config'
        config.mkdir()
        (config / 'repository.json').write_text('{"schema": 1, "role": "source"}\n')
        for scope in ('story', 'art'):
            path = repo / scope
            path.mkdir()
            (path / 'source.txt').write_text(f'{label}: {scope}\n')
        self.git(repo, 'add', '.')
        self.git(repo, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Initial fixture')
        return WS.setup(WF.Store(repo), {})['queue_id']

    def area(self, area_id, role, checkout, scope):
        return {'id': area_id, 'role': role, 'checkout': str(checkout), 'scope': scope,
                'capabilities': ['review-source'], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status', 'intake']}

    def snapshot(self, root):
        return {str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob('*') if path.is_file() and not path.is_symlink()}

    def register(self, request=None):
        request = request or self.request
        preview = self.director.preview(request)
        result = self.director.apply({**request, 'expected_preview_sha256': preview['preview_sha256']})
        self.assertEqual(result['preview_sha256'], preview['preview_sha256'])
        return result

    def test_shared_scopes_have_one_canonical_writer_and_keep_child_bytes(self):
        (self.repo / 'art/source.txt').write_text('Independent dirty work.\n')
        before = self.snapshot(self.repo)
        preview = self.director.preview(self.request)
        self.assertEqual(preview['added_areas'], ['art', 'maintenance', 'story'])
        self.assertEqual(self.snapshot(self.repo), before)
        self.assertEqual(self.snapshot(self.parent), {})
        self.assertNotIn(str(self.base), json.dumps(preview))
        result = self.register()
        self.assertEqual(self.snapshot(self.repo), before)
        self.assertEqual(result['registry']['revision'], 1)
        self.assertEqual({area['queue_id'] for area in result['registry']['areas'].values()}, {self.queue})
        local = json.loads((self.parent / DIRECTOR.BINDINGS).read_text())
        self.assertEqual(list(local['queues']), [self.queue])
        self.assertEqual(local['queues'][self.queue]['root'], str(self.repo))
        self.assertEqual(self.register()['changed_files'], [])

    def test_independent_repository_and_linked_alias_resolve_exact_owners(self):
        external = self.base / 'external'
        external_queue = self.init_repo(external, label='isolated external')
        linked = self.base / 'linked'
        self.git(self.repo, 'worktree', 'add', '-b', 'codex/linked-fixture', str(linked))
        story = {**self.story, 'checkout': str(linked)}
        preview = self.director.preview({**self.request, 'areas': [self.maint, story, self.area('outside', 'art', external, 'art')]})
        self.assertEqual(preview['registry']['areas']['story']['queue_id'], self.queue)
        self.assertEqual(preview['registry']['areas']['outside']['queue_id'], external_queue)
        aliased = self.area('duplicate-story', 'public', linked, 'story')
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'overlapping'):
            self.director.preview({**self.request, 'areas': [self.maint, self.story, aliased]})

    def test_external_area_verifies_owned_profile_without_running_child_manager(self):
        external = self.base / 'installed-child'
        queue = self.init_repo(external, label='installed child')
        (external / '.skill-tree/config/repository.json').unlink()
        request = {**self.request, 'areas': [self.maint, self.area('game', 'unity', external, 'art')]}
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'current owned Skill Tree installation'):
            self.director.preview(request)
        result = subprocess.run(['node', str(CORE / 'bin/install.js'), '--target', str(external),
                                 '--flavor', 'general', '--only', 'codex', '--skills', 'skill-tree-work-through-next'],
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        child = self.snapshot(external)
        preview = self.director.preview(request)
        self.assertEqual(preview['profile_proofs'][queue]['kind'], 'owned-profile')
        self.assertEqual(self.snapshot(external), child)
        self.register(request)
        self.assertEqual(self.snapshot(external), child)
        marker = self.base / 'child-manager-ran'
        manager = external / '.skill-tree/installation/manager.js'
        manager.write_text("require('node:fs').writeFileSync(" + json.dumps(str(marker)) + ", 'unexpected');\n")
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'current owned Skill Tree installation'):
            self.director.preview(request)
        self.assertFalse(marker.exists())

    def test_nested_external_checkout_cannot_overlap_a_shared_writer(self):
        self.register()
        external = self.repo / 'art/nested'
        self.init_repo(external, label='nested external')
        scoped_external = self.area('nested', 'unity', external, 'art')
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'overlapping scopes'):
            self.director.preview({**self.request, 'areas': [scoped_external]})
        misplaced = self.area('misplaced', 'unity', self.repo, 'art/nested')
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'scope belongs to a separate checkout'):
            self.director.preview({**self.request, 'areas': [misplaced]})

    def test_wrong_queue_and_scope_escape_fail_before_writes(self):
        self.register()
        before = self.snapshot(self.parent)
        malformed = [
            ({**self.story, 'id': 'wrong', 'expected_queue_id': WF.identity('Q')}, 'wrong queue'),
            ({**self.story, 'id': 'relative', 'checkout': 'project'}, 'absolute'),
            ({**self.story, 'id': 'not-root', 'checkout': str(self.repo / 'story')}, 'exact Git checkout'),
            ({**self.story, 'id': 'escape', 'scope': '../project/story'}, 'relative path'),
            ({**self.story, 'id': 'escape', 'scope': '/story'}, 'relative path'),
            ({**self.story, 'id': 'missing', 'scope': 'unknown'}, 'scope is unavailable'),
        ]
        alias = self.base / 'aliased-parent'
        alias.symlink_to(self.repo.parent, target_is_directory=True)
        malformed.append(({**self.story, 'id': 'ancestor-link', 'checkout': str(alias / self.repo.name)}, 'without a symlink'))
        (self.repo / 'unsafe').symlink_to(self.parent)
        malformed.append(({**self.story, 'id': 'unsafe', 'scope': 'unsafe'}, 'Symlink'))
        for item, expected in malformed:
            with self.subTest(expected=expected), self.assertRaisesRegex(DIRECTOR.DirectorError, expected):
                self.director.preview({**self.request, 'areas': [item]})
        self.assertEqual(self.snapshot(self.parent), before)

    def test_clone_of_a_queue_cannot_establish_a_second_writer(self):
        self.register()
        clone = self.base / 'clone'
        self.git(self.base, 'clone', '--no-hardlinks', str(self.repo), str(clone))
        child = WF.Store(clone, route_queue=False, neutral=True)
        child.state.write_bytes((self.repo / '.skill-tree/documents/future.json').read_bytes())
        duplicate = self.area('duplicate', 'public', clone, 'art')
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'queue ID requires explicit'):
            self.director.preview({**self.request, 'areas': [duplicate]})
        WS.recover_locator(child, {'queue_id': self.queue})
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'different local writer'):
            self.director.preview({**self.request, 'areas': [duplicate]})
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'previous canonical writer still exists'):
            self.director.preview({'director_id': self.request['director_id'], 'area_id': 'art', 'checkout': str(clone)}, rebind=True)

    def test_rebind_moves_the_single_local_writer_and_the_portable_registry_is_unchanged(self):
        self.register()
        before = (self.parent / DIRECTOR.REGISTRY).read_bytes()
        moved = self.base / 'moved'
        self.repo.rename(moved)
        rebind = {'director_id': self.request['director_id'], 'area_id': 'art', 'checkout': str(moved)}
        with self.assertRaisesRegex(WS.RunError, 'locator recovery'):
            self.director.preview(rebind, rebind=True)
        WS.recover_locator(WF.Store(moved, route_queue=False, neutral=True), {'queue_id': self.queue})
        child = self.snapshot(moved)
        preview = self.director.preview(rebind, rebind=True)
        self.assertEqual(preview['areas'], ['art', 'maintenance', 'story'])
        self.assertEqual(self.snapshot(moved), child)
        changed = self.director.apply({**rebind, 'expected_preview_sha256': preview['preview_sha256']}, rebind=True)
        self.assertEqual(changed['changed_files'], [DIRECTOR.BINDINGS])
        self.assertEqual((self.parent / DIRECTOR.REGISTRY).read_bytes(), before)
        self.assertEqual(self.snapshot(moved), child)
        bound = json.loads((self.parent / DIRECTOR.BINDINGS).read_text())
        self.assertEqual(bound['queues'][self.queue]['root'], str(moved))

    def test_concurrent_parent_change_stales_a_previously_inspected_plan(self):
        preview = self.director.preview(self.request)
        self.register({**self.request, 'areas': [self.maint]})
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(DIRECTOR.DirectorError, 'changed since preview'):
            self.director.apply({**self.request, 'expected_preview_sha256': preview['preview_sha256']})
        self.assertEqual(self.snapshot(self.parent), before)

    def test_cli_setup_and_apply_use_only_the_selected_parent(self):
        input_path = self.base / 'input.json'
        input_path.write_text(json.dumps(self.request))
        helper = CORE / 'common/scripts/director-state.py'
        cmd = ['python3', str(helper), 'setup-preview', str(self.parent), '--input', str(input_path)]
        preview = json.loads(subprocess.check_output(cmd, text=True, timeout=25))
        self.assertEqual(self.snapshot(self.parent), {})
        input_path.write_text(json.dumps({**self.request, 'expected_preview_sha256': preview['preview_sha256']}))
        cmd[2] = 'setup-apply'
        response = json.loads(subprocess.check_output(cmd, text=True, timeout=25))
        self.assertEqual(response['registry']['director_id'], 'lantern-pilot')
        self.assertTrue((self.parent / DIRECTOR.REGISTRY).is_file())


if __name__ == '__main__':
    unittest.main()
