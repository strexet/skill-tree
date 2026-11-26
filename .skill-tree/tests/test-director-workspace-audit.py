"""Exercise separate installed child validators through the Director audit entry."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from uuid import uuid4


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

    def operation_receipt(self, root, operation_id, entry=None):
        payload = self.base/'setup-operation.json'
        payload.write_text(json.dumps({'operation_id':operation_id}))
        return subprocess.run(
            [sys.executable, '-B', str(entry or CORE/'common/scripts/director-audit.py'),
             'operation-receipt', str(root.resolve()), '--input', str(payload)],
            capture_output=True, text=True, timeout=60)

    def test_install_and_failed_recovery_are_readable_without_a_run(self):
        root = self.base/'setup-only'
        root.mkdir()
        install = subprocess.run(
            ['node', str(CORE/'bin/install.js'), '--target', str(root), '--flavor', 'director',
             '--only', 'codex', '--skills', 'skill-tree-director-audit'],
            capture_output=True, text=True, timeout=90)
        self.assertEqual(install.returncode, 0, install.stdout+install.stderr)
        rows, _ = json.JSONDecoder().raw_decode(install.stdout)
        install_id = rows[0]['operation_id']
        entry = root/'.agents/skills/skill-tree-director-audit/scripts/director-entry.py'
        result = self.operation_receipt(root, install_id, entry)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        completed = json.loads(result.stdout)
        self.assertEqual((completed['kind'], completed['status']), ('install', 'completed'))
        self.assertIsNone(completed['before']['profile_sha256'])
        self.assertRegex(completed['observed']['profile_sha256'], r'^[a-f0-9]{64}$')
        self.assertNotIn(str(root), result.stdout)
        journal = root/'.skill-tree/installation/.journal.json'
        secret = b'fixture-credential-at-private-runtime-path'
        malformed = b'{"schema":99,"label":"'+secret+b'"}'
        journal.write_bytes(malformed)
        manager = root/'.skill-tree/installation/manager.js'
        recovery = subprocess.run(['node', str(manager), '--recover'], capture_output=True, text=True, timeout=60)
        self.assertEqual(recovery.returncode, 2, recovery.stdout+recovery.stderr)
        recovery_id = re.search(r'Setup operation (OP-[a-f0-9-]+)', recovery.stderr)[1]
        before = self.snapshot(root)
        result = self.operation_receipt(root, recovery_id, entry)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        failed = json.loads(result.stdout)
        self.assertEqual((failed['kind'], failed['status'], failed['stage']), ('recover', 'failed', 'recover'))
        self.assertEqual(failed['before']['core_journal_sha256'], failed['observed']['core_journal_sha256'])
        self.assertNotIn(secret.decode(), result.stdout)
        self.assertNotIn(str(root), result.stdout)
        self.assertEqual(journal.read_bytes(), malformed)
        self.assertFalse((root/'.skill-tree/documents/future.json').exists())
        self.assertEqual(self.snapshot(root), before)
        rejected = self.operation_receipt(root, '../foreign', entry)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.snapshot(root), before)

    def test_exact_recovery_replays_a_lost_receipt_without_consuming_a_new_journal(self):
        root, _, _ = self.product('setup-replay', install=True)
        operation_id = 'OP-'+str(uuid4())
        script = r"""
const fs = require('node:fs'), path = require('node:path');
const [modulePath, root, id] = process.argv.slice(1);
const core = require(modulePath), repo = path.dirname(modulePath) + '/..';
const source = path.join(root, '.skill-tree/installation/source');
const base = path.join(root, '.skill-tree/installation');
const journal = path.join(base, '.journal.json');
const relative = '.skill-tree/installation/.staging/0';
const stage = path.join(root, relative);
const operation = path.join(root, '.skill-tree/artifacts/setup-operations', id + '.json');
fs.mkdirSync(path.dirname(stage), {recursive:true});
fs.writeFileSync(stage, 'durable fixture');
const dest = '.skill-tree/artifacts/recovery-effect';
const entry = {dest, old:null, next:core.treeHash(root, relative), backup:'.skill-tree/installation/.backups/0', staged:relative};
fs.writeFileSync(journal, require(path.join(repo, 'lib/composer.js')).json({schema:1, channel:'core', entries:[entry]}));
const assert = require('node:assert/strict');
const originalJournal = fs.readFileSync(journal);
const oversized = Buffer.from(JSON.stringify({schema:1, channel:'plugins', entries:[],
  padding:'x'.repeat(16*1024*1024)}));
const pluginJournal = path.join(base, '.plugin-journal.json');
fs.writeFileSync(pluginJournal, oversized);
assert.equal(core.localMain(root, source, ['--recover']), 2);
assert.deepEqual(fs.readFileSync(journal), originalJournal);
assert.deepEqual(fs.readFileSync(pluginJournal), oversized);
assert.equal(fs.existsSync(path.join(root, dest)), false);
fs.unlinkSync(pluginJournal);
const original = fs.renameSync;
fs.renameSync = (from,to) => {
  if (to === operation && JSON.parse(fs.readFileSync(from)).status === 'completed') {
    throw Error('fixture lost receipt acknowledgement');
  }
  return original(from,to);
};
const recover = () => core.localMain(root, source, ['--recover', '--operation-id='+id]);
try { assert.equal(recover(), 2); } finally { fs.renameSync = original; }
assert.equal(JSON.parse(fs.readFileSync(operation)).status, 'pending');
assert.equal(fs.existsSync(journal), false);
const effect = path.join(root, dest);
const last = path.join(base, '.last-transaction.json');
const lastBytes = fs.readFileSync(last);
const marker = fs.statSync(effect).ino;
assert.equal(recover(), 0);
assert.equal(recover(), 0);
assert.equal(fs.statSync(effect).ino, marker);
assert.deepEqual(fs.readFileSync(last), lastBytes);
const foreign = Buffer.from('{"schema":88,"details":"private new journal"}');
fs.writeFileSync(journal, foreign);
const sealed = fs.readFileSync(operation);
assert.equal(recover(), 2);
assert.deepEqual(fs.readFileSync(journal), foreign);
assert.deepEqual(fs.readFileSync(operation), sealed);
"""
        result = subprocess.run(
            ['node', '-e', script, str(CORE/'lib/installation.js'), str(root.resolve()), operation_id],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        replay = self.operation_receipt(root, operation_id)
        self.assertEqual(replay.returncode, 0, replay.stdout+replay.stderr)
        data = json.loads(replay.stdout)
        self.assertEqual((data['status'], data['attempts']), ('completed', 2))
        self.assertIsNotNone(data['before']['core_journal_sha256'])
        self.assertIsNone(data['observed']['core_journal_sha256'])
        self.assertNotIn('private new journal', replay.stdout)

    def test_install_replays_its_own_published_transaction(self):
        root = self.base/'interrupted-install'
        root.mkdir()
        operation_id = 'OP-'+str(uuid4())
        script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path');
const [source, root, id] = process.argv.slice(1);
const core = require(path.join(source, 'lib/installation.js'));
const directory = '.agents/skills/skill-tree-repo-documentation-audit';
const selected = [{rel:directory, provider:'codex', name:path.basename(directory)}];
const install = () => core.install(root, source, 'general', selected, {operationId:id});
const original = fs.renameSync;
fs.renameSync = (from, to) => {
  if (from.includes(path.sep+'.staging'+path.sep)) throw Error('fixture activation interrupted');
  return original(from, to);
};
try { assert.throws(install, /fixture activation interrupted/); } finally { fs.renameSync = original; }
const journal = path.join(root, '.skill-tree/installation/.journal.json');
const carrier = path.join(root, '.skill-tree/artifacts/setup-operations', id+'.json');
const partial = JSON.parse(fs.readFileSync(carrier));
assert.equal(partial.status,'failed');
assert.equal(partial.activation_journal_sha256,require('node:crypto').createHash('sha256').update(fs.readFileSync(journal)).digest('hex'));
assert.equal(install().operation_id,id);
assert.equal(fs.existsSync(journal),false);
const complete = fs.readFileSync(carrier);
assert.equal(install().replayed,true);
assert.deepEqual(fs.readFileSync(carrier),complete);
"""
        result = subprocess.run(['node', '-e', script, str(CORE), str(root.resolve()), operation_id],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        result = self.operation_receipt(root, operation_id)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        completed = json.loads(result.stdout)
        self.assertEqual((completed['status'], completed['attempts']), ('completed', 2))
        self.assertRegex(completed['activation_journal_sha256'], r'^[a-f0-9]{64}$')

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
