"""Exercise separate installed child validators through the Director audit entry."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


HERE = Path(__file__).resolve().parent
CORE = HERE.parent
SPEC = importlib.util.spec_from_file_location('workspace_audit_fixtures', HERE / 'test-director-area-bindings.py')
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class WorkspaceAuditTests(unittest.TestCase):
    setUp = FIXTURE.DirectorAreaBindingTests.setUp
    git = FIXTURE.DirectorAreaBindingTests.git
    init_repo = FIXTURE.DirectorAreaBindingTests.init_repo
    area = FIXTURE.DirectorAreaBindingTests.area
    snapshot = FIXTURE.DirectorAreaBindingTests.snapshot
    register = FIXTURE.DirectorAreaBindingTests.register

    def product(self, name, *, install=False):
        root = self.base / name
        queue = self.init_repo(root)
        if install:
            command = ['node', str(CORE / 'bin/install.js'), '--target', str(root), '--flavor', 'general',
                       '--only', 'codex', '--skills', 'skill-tree-repo-documentation-audit', '--with-init']
            result = subprocess.run(command, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        area = self.area(name, 'general', root, '.')
        return root, queue, {**area, 'allowed_effects': ['status', 'audit']}

    def audit(self, command='workspace-audit', payload=None, entry=None):
        args = [sys.executable, '-B', str(entry or CORE / 'common/scripts/director-audit.py'), command, str(self.parent)]
        if payload is not None:
            path = self.base / 'workspace-audit.json'
            path.write_text(json.dumps(payload))
            args.extend(['--input', str(path)])
        return subprocess.run(args, capture_output=True, text=True, timeout=120)

    def report(self, *args, **kwargs):
        result = self.audit(*args, **kwargs)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_default_and_selected_audits_use_distinct_installed_child_tools(self):
        first, first_queue, first_area = self.product('site', install=True)
        second, second_queue, second_area = self.product('game', install=True)
        self.register({**self.request, 'areas': [self.maint, first_area, second_area]})
        guard = (self.snapshot(self.parent), self.snapshot(first), self.snapshot(second))
        results = self.report('audit')
        self.assertEqual(results['status'], 'completed')
        by_id = {project['project_id']: project for project in results['projects']}
        self.assertEqual(set(by_id), {'game', 'site'})
        for name, root, queue in [('site', first, first_queue), ('game', second, second_queue)]:
            row = by_id[name]
            self.assertEqual((row['queue_id'], row['scope'], row['git_head']),
                             (queue, '.', self.git(root, 'rev-parse', 'HEAD')))
            self.assertEqual(row['status'], 'observed')
            self.assertEqual(row['auditor']['lane'], 'child-tool')
            self.assertRegex(row['result']['stdout_sha256'], r'^[0-9a-f]{64}$')
            self.assertIn(row['result']['verdict'], ('pass', 'findings'))
        self.assertNotEqual(by_id['site']['auditor']['request_sha256'], by_id['game']['auditor']['request_sha256'])
        self.assertIn('native-runtime', results['coverage_gaps'])
        self.assertNotIn(str(self.base), json.dumps(results))
        self.assertEqual((self.snapshot(self.parent), self.snapshot(first), self.snapshot(second)), guard)
        tools = self.base / 'installed-director'
        tools.mkdir()
        installed = subprocess.run(['node', str(CORE / 'bin/install.js'), '--target', str(tools), '--flavor', 'director',
                                    '--only', 'codex', '--skills', 'skill-tree-director-audit'],
                                   capture_output=True, text=True, timeout=90)
        self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
        entry = tools / '.agents/skills/skill-tree-director-audit/scripts/director-entry.py'
        selected = self.report(payload={'project_ids': ['site']}, entry=entry)
        self.assertEqual(selected['projects'], [by_id['site']])
        self.assertNotEqual(self.audit(payload={'project_ids': ['invalid']}).returncode, 0)

        script = second / by_id['game']['auditor']['destination'] / 'scripts/validate-repository-documentation.py'
        script.write_text('raise RuntimeError("unverified child auditor must never run")\n')
        partial = self.report()
        self.assertEqual(partial['status'], 'partial')
        self.assertEqual({row['project_id']: row['status'] for row in partial['projects']},
                         {'game': 'unavailable', 'site': 'observed'})

    def test_denied_unavailable_and_narrow_areas_keep_their_boundaries(self):
        unsupported, _, unsupported_area = self.product('no-auditor')
        unavailable, _, unavailable_area = self.product('missing')
        denied, _, denied_area = self.product('denied')
        blocked, _, blocked_area = self.product('blocked')
        denied_area['allowed_effects'] = ['status']
        narrow_area = {**self.story, 'allowed_effects': ['audit']}
        self.register({**self.request, 'areas': [self.maint, unsupported_area, unavailable_area, denied_area,
                                                blocked_area, narrow_area]})
        unavailable.rename(self.base / 'moved')
        (blocked / '.skill-tree/.writer-lock').write_text('owned by the fixture\n')
        guard = tuple(self.snapshot(root) for root in (self.parent, unsupported, denied, blocked))
        rows = {row['project_id']: row for row in self.report()['projects']}
        self.assertEqual({name: row['status'] for name, row in rows.items()},
                         {'blocked': 'blocked', 'denied': 'denied', 'missing': 'unavailable',
                          'no-auditor': 'unsupported', 'story': 'unsupported'})
        self.assertEqual(rows['story']['scope'], 'story')
        self.assertTrue(all('result' not in row for row in rows.values()))
        self.assertEqual(tuple(self.snapshot(root) for root in (self.parent, unsupported, denied, blocked)), guard)


if __name__ == '__main__':
    unittest.main()
