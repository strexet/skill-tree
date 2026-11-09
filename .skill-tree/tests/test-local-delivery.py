"""Resumable, verified local Git delivery fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

CORE = next(parent for parent in Path(__file__).resolve().parents if parent.name == '.skill-tree')
spec = importlib.util.spec_from_file_location('existing_workspace_fixture', CORE / 'tests/test-run-workspaces.py')
workspace_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workspace_fixture)
wf = workspace_fixture.wf
ws = workspace_fixture.ws
fixture = workspace_fixture.RunWorkspaceTests
fixture_set_up = fixture.setUp
GENERATION = '.skill-tree/src/delivery-fixture-generation.txt'
OWNED_FILE = '.agents/skills/skill-tree-implement-all/SKILL.md'


class LocalDeliveryTests(unittest.TestCase):
    # Reuse real controller intake, check, completion and Git setup without
    # inheriting unrelated unittest methods.
    def setUp(self):
        fixture_set_up(self)
        self.git(self.root, 'config', 'commit.gpgSign', 'false')
        self.git(self.root, 'config', 'merge.verifySignatures', 'false')

    call = fixture.call
    task = fixture.task
    start = fixture.start
    location = fixture.location

    def git(self, root, *args):
        return self.call(root, *args)

    def accept_source(self, task_id):
        criterion = 'Preserve scoped source behavior.'
        store = self.selected
        wf.begin_task(store, {'task_id': task_id})
        (self.source / 'report.json').write_text('{"assertion":"scoped fixture passed"}')
        attempt = wf.prepare_check(store, {'task_id': task_id, 'check_id': 'behavior'})
        wf.record_check(store, {
            'task_id': task_id,
            'check_id': 'behavior',
            'attempt_id': attempt['attempt_id'],
            'result': 'pass',
            'classification': 'executed-control',
            'actual_lane': 'static',
            'environment_identity': attempt['environment_identity'],
            'assertions': [{'assertion': criterion, 'result': 'pass'}],
            'cleanup': 'The fixture starts no product process.',
            'evidence': ['report.json'],
        })
        wf.mark_implemented(store, {'task_id': task_id})
        wf.complete(store, {
            'task_id': task_id,
            'outcome': 'Scoped source behavior remains intact.',
            'acceptance': [{'criterion': criterion, 'result': 'pass', 'evidence': ['report.json']}],
            'source_fingerprints': wf.fingerprints(store, ['source.py']),
        })

    def run_local(self, *, retain=False, real_installer=False, incoming=None, owned_dirty=False, baseline_target=False, finish=True):
        if real_installer or owned_dirty:
            self.copy_source_generation()
        if owned_dirty:
            placeholder = self.root / OWNED_FILE
            placeholder.parent.mkdir(parents=True)
            placeholder.write_text('old tracked snapshot\n')
            self.git(self.root, 'add', '-f', OWNED_FILE)
            self.git(self.root, 'commit', '-m', 'Fixture tracks old owned package bytes')
            shutil.rmtree(placeholder.parent)
            self.install_target()

        if baseline_target:
            self.install_target()
        retained = None
        if retain:
            retained_task = self.task('Retained task')
            self.git(self.root, 'add', '.skill-tree/documents/future.md')
            self.git(self.root, 'commit', '-m', 'Fixture retained canonical queue baseline')
            retained = self.start(retained_task, base_branch='main', local_base=True,
                                  local_base_authorization='Synthetic retained fixture local main base.')
            retained_store = wf.Store(self.location(retained))
            wf.checkpoint(retained_store, {'phase': 'blocked', 'stop_reason': 'Independent retained prerequisite'})
            if baseline_target:
                self.install_target(root=self.location(retained))
                wf.resume_admission(retained_store)
            # Exercise retention of stopped run content and working copy.
            (self.location(retained) / 'source.py').write_text('value = 9\n')
        task_id = self.task('Deliver selected implementation')
        self.run = self.start(
            task_id,
            base_branch='main',
            local_base=True,
            local_base_authorization='Synthetic fixture authorizes the exact local main base.',
            delivery_authorization={
                'pr': False,
                'merge': True,
                'mode': 'local-merge',
                'target_branch': 'main',
                'owner_instruction': 'Synthetic fixture authorizes a local merge into main.'
            },
        )
        self.source = self.location(self.run)
        self.selected = wf.Store(self.source, self.run['id'])
        if owned_dirty:
            shutil.rmtree((self.source / OWNED_FILE).parent)
            wf.checkpoint(self.selected, {'phase': 'blocked', 'stop_reason': 'Fixture owned installation handoff'})
            self.install_target(root=self.source)
            wf.resume_admission(self.selected)
            wf.checkpoint(self.selected, {'phase': 'implement', 'stop_reason': None})
        (self.source / 'source.py').write_text('value = 2\n')
        if real_installer:
            (self.source / GENERATION).write_text('merged generation\n')
        for relative, content in (incoming or {}).items():
            destination = self.source / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content)
        self.accept_source(task_id)
        self.git(self.source, 'add', 'source.py', 'report.json',
                 *([GENERATION] if real_installer else []), *(incoming or ()))
        self.git(self.source, 'commit', '-m', 'Fixture accepted source')
        # Generated fixture records stay visible to workflow-state while Git
        # sees a clean working copy when the preparation contract requires it.
        # Future is tracked and committed separately only if the fixture changed
        # its exact whitespace after completing the selected task.
        exclude = self.root / '.git/info/exclude'
        with exclude.open('a') as stream:
            stream.write('\n/.skill-tree/documents/future.json\n/.skill-tree/skill-tree.json\n/.skill-tree/history/\n/.skill-tree/installation/\n/.agents/\n')
        self.retained = retained
        self.implementation = wf.finish(self.selected) if finish else None
        return self.implementation

    def copy_source_generation(self):
        target = self.root / '.skill-tree'
        for directory in ('common', 'domains', 'templates', 'config', 'lib', 'src', 'bin'):
            shutil.copytree(CORE / directory, target / directory, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('__pycache__'))
        for entry in (CORE / 'skills/general').glob('*/SKILL.md'):
            destination = target / entry.relative_to(CORE)
            destination.parent.mkdir(parents=True)
            shutil.copyfile(entry, destination)
        self.git(self.root, 'add', '.skill-tree/common', '.skill-tree/domains',
                 '.skill-tree/templates', '.skill-tree/config', '.skill-tree/lib',
                 '.skill-tree/src', '.skill-tree/bin', '.skill-tree/skills')
        self.git(self.root, 'commit', '-m', 'Fixture owned source generation')

    def registry_run(self, run_id=None):
        return wf.Store(self.root, neutral=True).load()['run_registry']['runs'][run_id or self.run['id']]

    def action(self, command, **payload):
        return wf.local_delivery_action(self.selected, command, payload)

    def assert_pending(self):
        delivery = self.registry_run()['delivery']
        self.assertFalse(delivery['order_completed'])
        self.assertEqual(delivery['publication'], 'not-requested')
        return delivery

    def install_target(self, flavor='general', provider='codex', root=None):
        root = root or self.root
        result = subprocess.run(
            ['node', str(root / '.skill-tree/bin/install.js'),
             '--only', provider, '--target', str(root), '--flavor', flavor, '--yes'],
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return json.loads((root / '.skill-tree/installation/profile.json').read_text())

    def verify_target(self):
        result = subprocess.run(
            ['node', str(self.root / '.skill-tree/installation/manager.js'), '--verify'],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        return result

    def merge(self, fast_forward=False):
        self.git(self.root, 'merge', '--ff-only' if fast_forward else '--no-ff',
                 *([] if fast_forward else ['--no-edit', '--no-overwrite-ignore']), self.git(self.source, 'rev-parse', 'HEAD'))
        return self.git(self.root, 'rev-parse', 'HEAD')

    def test_finish_does_not_close_authorized_local_merge(self):
        result = self.run_local()
        self.assertEqual(result['delivery']['implementation'], 'completed')
        self.assertEqual(result['delivery']['publication'], 'not-requested')
        self.assertFalse(result['delivery']['order_completed'])
        self.assertNotEqual(result['delivery']['status'], 'local-result')
        self.assertFalse(ws.delivery_finished(result))
        self.assertEqual(self.registry_run()['completed_ids'], [self.run['root_task_id']])
        self.assertEqual(wf.Store(self.root, neutral=True).load()['run_registry']['claims'], {})

    def test_repeated_finish_preserves_original_reviewed_source_after_ref_moves(self):
        result = self.run_local()
        frozen_head = self.git(self.source, 'rev-parse', 'HEAD')
        completion_path = self.root / '.skill-tree/history/runs' / ('run-' + self.run['id'].lower() + '.json')
        original_completion = completion_path.read_bytes()
        original_state = self.selected.state.read_bytes()
        self.git(self.source, 'commit', '--allow-empty', '-m', 'Unreviewed source movement')
        repeated = wf.finish(wf.Store(self.source, self.run['id']))
        self.assertEqual(repeated, result)
        self.assertEqual(completion_path.read_bytes(), original_completion)
        self.assertEqual(self.selected.state.read_bytes(), original_state)
        self.assertIn(frozen_head, original_completion.decode())
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'source|head'):
            self.action('prepare')
        self.assert_pending()

    def test_diverged_target_never_rebases_the_frozen_order(self):
        self.run_local()
        self.git(self.root, 'commit', '--allow-empty', '-m', 'Unapproved target movement')
        moved_head = self.git(self.root, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'target|diverg|base'):
            self.action('prepare')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), moved_head)
        self.assert_pending()

    def test_preparation_binds_exact_heads_and_reconciles_original_git_merge(self):
        self.run_local()
        source = self.git(self.source, 'rev-parse', 'HEAD')
        target = self.git(self.root, 'rev-parse', 'HEAD')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        prepared = self.action('prepare')['local_integration']['preparation']
        self.assertEqual(prepared['source_head'], source)
        self.assertEqual(prepared['target_head'], target)
        self.assertEqual(self.action('prepare')['local_integration']['preparation'], prepared)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('reconcile')
        commit = self.merge()
        self.assertEqual(self.git(self.root, 'show', '-s', '--format=%P', commit).split(), [target, source])
        # New Store instance models interruption after Git and before recording.
        self.selected = wf.Store(self.root, self.run['id'])
        first = self.action('reconcile')['local_integration']['merge']
        self.assertEqual(first['commit'], commit)
        self.assertEqual(self.action('reconcile')['local_integration']['merge'], first)
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), commit)
        self.assert_pending()

    def test_merge_action_preserves_ignored_collision_added_after_prepare(self):
        relative = '.ignored late\nsource'
        self.run_local(incoming={relative: 'incoming bytes\n'})
        self.action('prepare')
        original_head = self.git(self.root, 'rev-parse', 'HEAD')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.ignored*\n')
        (self.root / relative).write_text('ignored target bytes\n')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), original_head)
        self.assertEqual((self.root / relative).read_text(), 'ignored target bytes\n')
        self.assert_pending()

    def test_owned_merge_disables_autostash_and_preserves_owned_dirt(self):
        self.run_local(owned_dirty=True)
        owned = (self.root / OWNED_FILE).read_bytes()
        self.git(self.root, 'config', 'merge.autostash', 'true')
        self.action('prepare')
        first = self.action('merge')['local_integration']['merge']
        self.assertEqual(self.action('merge')['local_integration']['merge'], first)
        self.assertEqual(self.git(self.root, 'config', 'merge.autostash'), 'true')
        self.assertEqual(self.git(self.root, 'for-each-ref', 'refs/stash'), '')
        self.assertEqual((self.root / OWNED_FILE).read_bytes(), owned)
        self.assert_pending()

    def test_executable_git_hook_is_reported_without_running_it(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        directory = self.base / 'custom-hooks'
        directory.mkdir()
        hook = directory / 'post-merge'
        hook.write_text('#!/bin/sh\nprintf invoked > hook-was-executed\n')
        hook.chmod(0o700)
        self.git(self.root, 'config', 'core.hooksPath', str(directory))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'executable Git hook'):
            self.action('merge')
        self.assertFalse((self.root / 'hook-was-executed').exists())
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)
        self.assert_pending()

    def test_preflight_never_refreshes_git_index_and_calls_hook(self):
        self.run_local()
        hook = self.root / '.git/hooks/post-index-change'
        hook.write_text('#!/bin/sh\nprintf invoked > post-index-executed\n')
        hook.chmod(0o700)
        source = self.root / 'source.py'
        previous = source.stat()
        os.utime(source, ns=(previous.st_atime_ns, previous.st_mtime_ns + 1_000_000_000))
        self.action('prepare')
        self.assertFalse((self.root / 'post-index-executed').exists())
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'post-index-change'):
            self.action('merge')
        self.assertFalse((self.root / 'post-index-executed').exists())

    def test_branch_merge_options_cannot_create_a_wrong_tree(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'config', 'branch.main.mergeOptions', '--strategy=ours')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'branch-specific'):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'config', 'branch.main.mergeOptions'), '--strategy=ours')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)

    def test_enabled_git_signing_policy_stops_without_mutating_target(self):
        self.run_local()
        self.action('prepare')
        before = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'config', 'commit.gpgSign', 'true')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'signing policy'):
            self.action('merge')
        self.assertEqual(self.git(self.root, 'config', 'commit.gpgSign'), 'true')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), before)
        self.assert_pending()

    def test_fast_forward_does_not_satisfy_prepared_two_parent_merge(self):
        self.run_local()
        self.action('prepare')
        commit = self.merge(fast_forward=True)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('reconcile')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), commit)
        self.assert_pending()

    def test_exact_merge_parents_without_incoming_tree_do_not_complete(self):
        self.run_local()
        prep = self.action('prepare')['local_integration']['preparation']
        self.git(self.root, 'merge', '--no-ff', '--no-edit', '-s', 'ours', prep['source_head'])
        commit = self.git(self.root, 'rev-parse', 'HEAD')
        self.assertEqual(self.git(self.root, 'show', '-s', '--format=%P', commit).split(),
                         [prep['target_head'], prep['source_head']])
        self.assertEqual((self.root / 'source.py').read_text(), 'value = 1\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'tree|incoming'):
            self.action('reconcile')
        self.assert_pending()

    def changed_verifier(self):
        path = self.source / '.skill-tree/lib/installation.js'
        marker = self.source / 'unreviewed-verifier-was-executed'
        path.write_text("require('node:fs').writeFileSync(" + json.dumps(str(marker)) + ", 'unexpected');\n")
        self.git(self.source, 'add', '.skill-tree/lib/installation.js')
        return marker

    def test_moved_source_verifier_is_never_executed(self):
        self.run_local(real_installer=True)
        marker = self.changed_verifier()
        self.git(self.source, 'commit', '-m', 'Unreviewed verifier movement')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'source head|tree'):
            self.action('prepare')
        self.assertFalse(marker.exists())
        self.assert_pending()

    def test_finish_checks_stale_required_source_before_loading_verifier(self):
        self.run_local(real_installer=True, finish=False)
        marker = self.changed_verifier()
        (self.source / 'source.py').write_text('value = 3\n')
        self.git(self.source, 'add', 'source.py')
        self.git(self.source, 'commit', '-m', 'Unaccepted implementation movement')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'stale'):
            wf.finish(self.selected)
        self.assertFalse(marker.exists())

    def test_git_index_override_is_rejected(self):
        self.run_local()
        with patch.dict(os.environ, {'GIT_INDEX_FILE': str(self.base / 'other-index')}):
            with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'index overrides'):
                self.action('prepare')
        self.assert_pending()

    def test_source_movement_keeps_original_preparation_pending(self):
        self.run_local()
        original = self.action('prepare')['local_integration']['preparation']
        self.git(self.source, 'commit', '--allow-empty', '-m', 'Unreviewed source movement')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('prepare')
        self.assertEqual(self.assert_pending()['local_integration']['preparation'], original)

    def test_target_source_overlap_and_writer_lock_reject_preparation(self):
        self.run_local()
        original = (self.root / 'source.py').read_text()
        (self.root / 'source.py').write_text('local target edit\n')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('prepare')
        self.assertEqual((self.root / 'source.py').read_text(), 'local target edit\n')
        (self.root / 'source.py').write_text(original)
        with wf.Store(self.root, neutral=True).lock():
            with self.assertRaises((wf.WorkflowError, ws.RunError)):
                self.action('prepare')
        self.assert_pending()

    def test_receipt_owned_tracked_dirt_is_distinct_from_owned_path_edit(self):
        self.run_local(owned_dirty=True)
        for root in (self.root, self.source):
            self.assertIn(OWNED_FILE, self.git(root, 'status', '--porcelain', '--', OWNED_FILE))
        original = (self.root / OWNED_FILE).read_bytes()
        (self.root / OWNED_FILE).write_bytes(original + b'fixture unauthorized edit\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'owned|modified|dirty'):
            self.action('prepare')
        (self.root / OWNED_FILE).write_bytes(original)
        self.action('prepare')
        self.assertEqual((self.root / OWNED_FILE).read_bytes(), original)
        self.assert_pending()

    def test_ignored_nul_delimited_obstruction_is_never_overwritten(self):
        relative = '.ignored new\nname'
        self.run_local(incoming={relative: 'incoming source\n'})
        target = self.root / relative
        target.write_text('ignored target owner bytes\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.ignored*\n')
        self.assertIn('.ignored', self.git(self.root, 'check-ignore', '--', relative))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'ignored target owner bytes\n')
        self.assert_pending()

    def test_ignored_file_prefix_is_an_incoming_directory_collision(self):
        self.run_local(incoming={'.collision/nested.txt': 'incoming file\n'})
        target = self.root / '.collision'
        target.write_text('retained file\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.collision\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'retained file\n')
        self.assert_pending()

    def test_ignored_directory_prefix_is_an_incoming_file_collision(self):
        self.run_local(incoming={'.collision': 'incoming file\n'})
        target = self.root / '.collision' / 'retained.txt'
        target.parent.mkdir()
        target.write_text('retained file\n')
        with (self.root / '.git/info/exclude').open('a') as stream:
            stream.write('/.collision/\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'collision|overlap|obstruction|dirty'):
            self.action('prepare')
        self.assertEqual(target.read_text(), 'retained file\n')
        self.assert_pending()

    def test_unrelated_workflow_journal_is_not_recovered_by_delivery(self):
        self.run_local()
        transaction = self.root / '.skill-tree/.transaction.json'
        original = b'{"format":"skill-tree-transaction","writes":[]}\n'
        transaction.write_bytes(original)
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'journal|transaction'):
            self.action('prepare')
        self.assertEqual(transaction.read_bytes(), original)
        transaction.unlink()
        self.assert_pending()

    def test_retained_admission_does_not_recover_another_action_target(self):
        self.run_local()
        transaction = self.root / '.skill-tree/.transaction.json'
        first, second = wf.identity('WR'), wf.identity('WR')
        journal = {
            'format': 'skill-tree-transaction',
            'writes': [],
            'local_delivery': {'run_id': self.run['id'], 'action': 'admit-retained', 'retained_run_id': first},
        }
        transaction.write_text(json.dumps(journal))
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'journal|transaction'):
            self.action('admit-retained', run_id=second)
        self.assertEqual(json.loads(transaction.read_text()), journal)
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'Prepare'):
            self.action('admit-retained', run_id=first)
        self.assertFalse(transaction.exists())
        self.assert_pending()

    def test_activation_rejects_verified_old_owned_generation_and_requires_admission(self):
        self.run_local(real_installer=True)
        old = self.install_target()
        self.verify_target()
        self.action('prepare')
        commit = self.merge()
        self.action('reconcile')
        # The old installed manager verifies its own bundle even after the merge.
        self.verify_target()
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('admit-target')
        self.install_target(flavor='web')
        self.verify_target()
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'flavor|scope|destination'):
            self.action('admit-target')
        current = self.install_target()
        self.assertNotEqual(current['identity'], old['identity'])
        self.assertIn('src/delivery-fixture-generation.txt', current['source_digests'])
        self.verify_target()
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        admission = self.action('admit-target')['local_integration']['target_admission']
        self.assertEqual(admission['profile_identity'], current['identity'])
        self.assertEqual(admission['merge_commit'], commit)
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        self.assert_pending()

    def test_re_admission_is_exactly_scoped_to_retained_stopped_run(self):
        self.run_local(retain=True, real_installer=True, baseline_target=True)
        retained_id = self.retained['id']
        retained_before = self.registry_run(retained_id)
        self.action('prepare')
        self.merge()
        self.action('reconcile')
        self.install_target()
        self.action('admit-target')
        self.assertTrue(self.registry_run(retained_id)['profile_refresh_required'])
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('admit-retained', run_id=self.run['id'])
        self.action('admit-retained', run_id=retained_id)
        retained_after = self.registry_run(retained_id)
        self.assertFalse(retained_after.get('profile_refresh_required', False))
        for key in ('snapshot', 'admitted_task_ids', 'limits', 'phase', 'stop_reason', 'next_action'):
            self.assertEqual(retained_after[key], retained_before[key])
        self.assertEqual((self.location(self.retained) / 'source.py').read_text(), 'value = 9\n')
        self.assert_pending()

    def test_final_current_validation_closes_only_local_order(self):
        self.run_local(real_installer=True)
        self.install_target()
        self.action('prepare')
        commit = self.merge()
        self.action('reconcile')
        current = self.install_target()
        self.action('admit-target')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('validate-target', checks=[{'id': 'untrusted', 'exit_code': 0}])
        # Production selects and actually executes known commands in the target
        # checkout. The test must never hand an asserted pass to the action.
        fixture_commands = (
            ('owned-installation', ('node', '.skill-tree/installation/manager.js', '--verify')),
            ('incoming-diff', ('git', 'diff', '--check', commit + '^1', commit, '--')),
        )
        with patch.object(wf, '_local_delivery_commands', return_value=fixture_commands):
            record = self.action('validate-target')['local_integration']['validation']
        self.assertEqual([check['id'] for check in record['checks']], ['owned-installation', 'incoming-diff'])
        self.assertEqual(record['merge_commit'], commit)
        self.assertEqual(record['profile_identity'], current['identity'])
        artifact = self.root / record['evidence'][0]['path']
        original_report = artifact.read_bytes()
        artifact.write_text('{}')
        with self.assertRaises((wf.WorkflowError, ws.RunError)):
            self.action('complete')
        artifact.write_bytes(original_report)
        delivery = self.action('complete')
        self.assertTrue(delivery['order_completed'])
        self.assertEqual(delivery['publication'], 'not-requested')
        self.assertEqual(delivery['local_integration']['merge']['commit'], commit)
        self.assertTrue(ws.delivery_finished(self.registry_run()))
        self.assertEqual(self.action('complete')['local_integration'], delivery['local_integration'])

    def test_canonical_queue_drift_after_merge_preserves_other_run_and_blocks_completion(self):
        self.run_local(retain=True)
        state = self.registry_run(self.retained['id'])
        self.action('prepare')
        self.merge()
        queue = self.root / '.skill-tree/documents/future.md'
        before = queue.read_bytes()
        queue.write_bytes(before + b'\n')
        with self.assertRaisesRegex((wf.WorkflowError, ws.RunError), 'preserv|queue|dirty'):
            self.action('reconcile')
        self.assertEqual(queue.read_bytes(), before + b'\n')
        self.assertEqual(self.registry_run(self.retained['id']), state)
        self.assertEqual((self.location(self.retained) / 'source.py').read_text(), 'value = 9\n')
        self.assert_pending()


del fixture


if __name__ == '__main__':
    unittest.main()
