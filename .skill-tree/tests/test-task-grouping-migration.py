import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
SCRIPTS = SOURCE / 'common/scripts'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


wf = module('migration_test_workflow', 'workflow-state.py')
migration = module('migration_test_helper', 'task-grouping-migration.py')
migration.wf = wf


class GroupingMigrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name).resolve()
        self.root = self.directory / 'canonical'
        self.root.mkdir()
        self.store = wf.Store(self.root, neutral=True)
        self.store.future.parent.mkdir(parents=True)
        self.pending = wf.identity('P')
        self.backlog = wf.identity('B')
        self.prioritized = wf.identity('T')
        self.unrelated = wf.identity('T')
        self.origin = wf.identity('P')
        self.batch = wf.identity('IB')
        pending = self.entry(self.pending, 'Original pending task')
        backlog = self.entry(self.backlog, 'Backlog task', parents=[self.origin])
        ready = self.entry(self.prioritized, 'Prioritized task', parents=[self.origin], depends=[self.unrelated])
        unrelated = self.entry(self.unrelated, 'Unrelated task', parents=[self.origin], topic='elsewhere')
        self.store.future.write_bytes((
            '# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n' + pending +
            '## Prioritized Next Changes\n\n' + ready + unrelated + '## Backlog\n\n' + backlog
        ).encode())
        state = self.store.load()
        state['retained_extension'] = {'value': 'Preserve existing index data.'}
        self.store.state.write_text(wf.dump(state))
        self.store.owned('.skill-tree/skill-tree.json').write_text(wf.dump(wf.manifest(self.store)))
        batch_path = self.store.owned(wf.intake_receipt_path(self.batch))
        batch_path.parent.mkdir(parents=True)
        batch_path.write_text(wf.dump({
            'schema': 1, 'id': self.batch, 'created_at': '2026-11-12T10:00:00+00:00',
            'request_sha256': 'a' * 64,
            'items': [{**self.metadata(pid), 'intake_batch_ids': [self.batch]} for pid in (self.pending, self.origin)],
        }))
        self.outcomes = self.store.owned('.skill-tree/history/task-outcomes.jsonl')
        self.outcomes.write_text('{"disposition":"completed","task_id":"' + wf.identity('T') + '"}\n')

    def metadata(self, tid, parents=(), depends=()):
        status = {'P': 'Pending', 'T': 'Ready', 'B': 'Backlog'}[tid[0]]
        return {'id': tid, 'priority': 103, 'status': status, 'parent_pending_ids': list(parents),
                'processing_run_id': wf.identity('PR') if status == 'Ready' else None,
                'root_task_id': tid if status == 'Ready' else None, 'related_task_id': None,
                'relation': 'main', 'depends_on': list(depends)}

    def entry(self, tid, title, *, parents=(), depends=(), topic=None):
        meta = self.metadata(tid, parents, depends)
        if topic:
            meta['topic'] = topic
        body = 'Description:\n- Keep original whitespace and body.'
        if tid.startswith('T-'):
            criterion = 'Keep exact metadata and body.'
            checks = [{'id': 'inspect', 'recipe_id': 'static-inspection', 'criteria': [criterion],
                       'sources': ['input.txt'], 'parameters': {}, 'assertion': criterion, 'timing': 'immediate'}]
            body = ('Goal:\n- Keep original content.\n\nTouch:\n- Inspect input.\n\nValidation:\n```json\n' +
                    json.dumps({'checks': checks}) + '\n```\n\nAcceptance:\n- ' + criterion)
        return wf.render(title, meta, body).replace('\n\n\n', '\n\n')

    def install(self, root=None):
        installer = SOURCE / 'lib/installation.js'
        script = '''const api=require(process.argv[1]);
const name = 'skill-tree-add-pending-task';
api.install(process.argv[2], process.argv[3], 'general', [{provider:'codex', name, rel:'.agents/skills/' + name}]);'''
        result = subprocess.run(['node', '-e', script, str(installer), str(root or self.root), str(SOURCE)],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def command(self, command, assignments, **guards):
        payload = {'assignments': assignments, 'expected_source_hash': wf.file_hash(self.store.future), **guards}
        return migration.migrate(self.store, command, payload)

    def state(self):
        return json.loads(self.store.state.read_text())

    def snapshot(self):
        return {path.relative_to(self.root): path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

    def test_selected_exact_metadata_applies_to_all_queues_and_replays(self):
        self.install()
        before = self.snapshot()
        assignments = {self.pending: {'topic': 'director', 'intake_batch_ids': [self.batch]},
                       self.prioritized: {'topic': 'director', 'intake_batch_ids': [self.batch]},
                       self.backlog: {'topic': 'director'}}
        preview = self.command('task-grouping-preview', assignments)
        self.assertTrue(preview['applicable'])
        self.assertEqual(self.snapshot(), before)
        old_hash = preview['source_hash']
        guards = {'expected_preview_sha256': preview['preview_sha256'], 'expected_source_hash': old_hash}
        applied = self.command('task-grouping-apply', assignments, **guards)
        self.assertEqual(applied['status'], 'applied')
        self.assertEqual(applied['receipt']['applied_ids'], [self.pending, self.prioritized, self.backlog])
        self.assertEqual(applied['receipt']['batch_evidence'][self.batch]['created_at'], '2026-11-12T10:00:00+00:00')
        after = self.snapshot()
        original_bytes = before[Path('.skill-tree/documents/future.md')]
        after_bytes = self.store.future.read_bytes()
        self.assertEqual(after_bytes.replace(b'topic: "director"\n', b'').replace(
            ('intake_batch_ids: ["' + self.batch + '"]\n').encode(), b''), original_bytes)
        self.assertEqual(self.state()['retained_extension'], {'value': 'Preserve existing index data.'})
        self.assertEqual(self.state()['active_run'], json.loads(before[Path('.skill-tree/documents/future.json')])['active_run'])
        self.assertEqual(self.outcomes.read_bytes(), before[self.outcomes.relative_to(self.root)])
        self.assertEqual(self.command('task-grouping-apply', assignments, **guards)['status'], 'replayed')
        matching = self.command('task-grouping-preview', assignments)
        result = self.command('task-grouping-apply', assignments, expected_preview_sha256=matching['preview_sha256'])
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(self.snapshot(), after)

    def test_preview_reports_conflicts_and_apply_is_atomic(self):
        self.install()
        assignments = {self.pending: {'topic': 'director'}, self.unrelated: {'topic': 'director'},
                       wf.identity('T'): {'topic': 'director'}, self.backlog: {'intake_batch_ids': [wf.identity('IB')]}}
        before = self.snapshot()
        preview = self.command('task-grouping-preview', assignments)
        self.assertFalse(preview['applicable'])
        self.assertEqual(len(preview['missing_ids']), 1)
        self.assertEqual({item['task_id'] for item in preview['conflicts']}, {self.unrelated, self.backlog})
        with self.assertRaisesRegex(wf.WorkflowError, 'missing or conflicting'):
            self.command('task-grouping-apply', assignments, expected_preview_sha256=preview['preview_sha256'])
        self.assertEqual(self.snapshot(), before)

    def test_legacy_missing_profile_and_stale_queue_are_rejected(self):
        assignments = {self.pending: {'topic': 'director'}}
        preview = self.command('task-grouping-preview', assignments)
        self.assertFalse(preview['applicable'])
        self.assertIn('Missing ownership receipt', preview['blocked_reason'])
        self.install()
        preview = self.command('task-grouping-preview', assignments)
        self.store.future.write_text(self.store.text().replace('Keep original whitespace', 'Keep updated whitespace'))
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'Source changed'):
            self.command('task-grouping-apply', assignments, expected_source_hash=preview['source_hash'],
                         expected_preview_sha256=preview['preview_sha256'])
        self.assertEqual(self.snapshot(), before)

    def test_canonical_run_barrier_and_excluded_stop_evidence(self):
        self.install()
        state = self.state()
        run_id = wf.identity('WR')
        foreign = self.directory / 'foreign'
        subprocess.run(['git', '-C', str(self.root), 'init', '-b', 'main'], capture_output=True, check=True)
        subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                        'commit', '--allow-empty', '-m', 'Fixture'], capture_output=True, check=True)
        subprocess.run(['git', '-C', str(self.root), 'worktree', 'add', '-b', 'codex/foreign', str(foreign)],
                       capture_output=True, check=True)
        queue_id = wf.identity('Q')
        locator = {'schema': 1, 'queue_id': queue_id, 'canonical_root': str(self.root),
                   'worktrees': {run_id: str(foreign)}}
        (self.root / '.git/skill-tree-runtime.json').write_text(wf.dump(locator))
        run = {'id': run_id, 'mode': 'next', 'snapshot': [self.unrelated], 'root_task_id': self.unrelated,
               'current_task_id': self.unrelated, 'phase': 'implement', 'required_ids': [self.unrelated],
               'deferred_ids': [], 'pending_ids': [], 'processing_results': [], 'completed_ids': [],
               'limits': {}, 'next_action': 'Review the current blockout.', 'stop_reason': None,
               'admission': {}, 'admitted_task_ids': [self.unrelated], 'admitted_groups': {},
               'workspace': {'branch': 'codex/foreign'}, 'delivery': {'implementation': 'in-progress'}}
        state.update(schema=3, run_registry={'schema': 1, 'queue_id': queue_id, 'runs': {run_id: run},
                                           'claims': {self.unrelated: run_id}, 'resources': {}})
        self.store.state.write_text(wf.dump(state))
        assignments = {self.pending: {'topic': 'director'}}
        active = self.command('task-grouping-preview', assignments)
        self.assertFalse(active['applicable'])
        self.assertIn('stopped', active['blocked_reason'])
        run.update(phase='blocked', stop_reason='Waiting for an owner decision.')
        self.store.state.write_text(wf.dump(state))
        unmarked = self.command('task-grouping-preview', assignments)
        self.assertFalse(unmarked['applicable'])
        self.assertIn('re-admission', unmarked['blocked_reason'])
        run['profile_refresh_required'] = True
        self.store.state.write_text(wf.dump(state))
        stopped = self.command('task-grouping-preview', assignments)
        self.assertEqual(stopped['excluded_stopped_runs'][0]['checkpoint_sha256'], wf.digest(wf.dump(run).encode()))
        run['next_action'] = 'Review the updated blockout.'
        self.store.state.write_text(wf.dump(state))
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'preview'):
            self.command('task-grouping-apply', assignments, expected_preview_sha256=stopped['preview_sha256'])
        self.assertEqual(self.snapshot(), before)
        stopped = self.command('task-grouping-preview', assignments)
        self.command('task-grouping-apply', assignments, expected_preview_sha256=stopped['preview_sha256'])
        self.assertEqual(self.state()['run_registry'], state['run_registry'])
        self.assertFalse((foreign / '.skill-tree/installation/profile.json').exists())

    def test_changed_profile_or_provenance_invalidates_preview(self):
        self.install()
        assignments = {self.pending: {'topic': 'director', 'intake_batch_ids': [self.batch]}}
        preview = self.command('task-grouping-preview', assignments)
        path = self.store.owned(wf.intake_receipt_path(self.batch))
        path.write_text(path.read_text() + '\n')
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'preview'):
            self.command('task-grouping-apply', assignments, expected_preview_sha256=preview['preview_sha256'])
        self.assertEqual(self.snapshot(), before)
        preview = self.command('task-grouping-preview', assignments)
        profile = self.root / '.skill-tree/installation/profile.json'
        profile.write_text(profile.read_text() + '\n')
        before = self.snapshot()
        with self.assertRaisesRegex(wf.WorkflowError, 'preview'):
            self.command('task-grouping-apply', assignments, expected_preview_sha256=preview['preview_sha256'])
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
