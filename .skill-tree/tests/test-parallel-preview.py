import importlib.util
from datetime import datetime, timedelta, timezone
import json
import runpy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


CORE = Path(__file__).resolve().parents[1]
HELPER = CORE / 'common/scripts/parallel-preview.py'
SPEC = importlib.util.spec_from_file_location('parallel_preview', HELPER)
preview = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preview)
workflow = preview.workflow
CRITERION = 'Preserve the fixture behavior.'


class ParallelReadyPreviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.store = workflow.Store(self.root, allow_unselected=True, neutral=True)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text(
            '# Future Work\n\n## Pending Task Format\n\nFixed headers.\n\n'
            '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n'
        )

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return path

    def task(self, title, priority, touch, *, reads=(), dependencies=(), recipe='static-inspection'):
        pending = workflow.intake(self.store, {
            'title': title, 'description': CRITERION, 'expected_behavior': CRITERION, 'priority': priority,
        })['id']
        check = {
            'id': 'scoped-fixture', 'recipe_id': recipe, 'criteria': [CRITERION],
            'sources': list(reads or ['shared-read.py']), 'parameters': {},
            'assertion': CRITERION, 'timing': 'immediate',
        }
        body = (
            'Goal:\n- ' + CRITERION + '\n\nTouch:\n'
            + ''.join('- ' + path + '\n' for path in touch)
            + '\nValidation:\n```json\n' + json.dumps({'checks': [check]})
            + '\n```\n\nAcceptance:\n- ' + CRITERION + '\n'
        )
        return workflow.process(self.store, {
            'selectors': [pending],
            'dispositions': {pending: {'status': 'promoted', 'reason': CRITERION}},
            'tasks': [{'title': title, 'body': body, 'depends_on': list(dependencies),
                       'parent_pending_ids': [pending]}],
        })['created_ids'][0]

    def state_bytes(self):
        return {path.relative_to(self.root): path.read_bytes()
                for path in self.root.rglob('*') if path.is_file()}

    def command(self, *args, check=True, script=HELPER):
        return subprocess.run([sys.executable, '-B', str(script), str(self.root), *args],
                              text=True, capture_output=True, timeout=25, check=check)

    def test_priority_ties_conflicts_and_read_only(self):
        high = self.task('First path', 234, ['src/first.py'])
        held = self.task('Overlapping check', 233, ['src/other.py'], reads=['src'])
        tied = self.task('Another separate path', 232, ['third.py'])
        low = self.task('Separate path', 232, ['src/second.py'])
        before = self.state_bytes()

        output = json.loads(self.command().stdout)
        self.assertEqual(output['selected_ids'], [high, low])
        deferred = {item['id']: item for item in output['deferred']}
        self.assertEqual(deferred[held]['reasons'][0], {
            'kind': 'input-write-overlap', 'task_id': high, 'paths': ['src', 'src/first.py'],
        })
        self.assertEqual(deferred[held]['reasons'][1], {
            'kind': 'input-write-overlap', 'task_id': low, 'paths': ['src', 'src/second.py'],
        })
        self.assertEqual(deferred[tied]['reasons'], [{'kind': 'worker-limit', 'workers': 2}])
        self.assertEqual([item['task_id'] for item in output['after_merge']['checks']], [high, low])
        self.assertEqual(output['snapshot']['queue_sha256'], workflow.file_hash(self.store.future))
        self.assertEqual(json.loads(self.command('--id', tied, '--id', low).stdout)['selected_ids'], [low, tied])
        rejected = self.command('--id', 'Separate path', check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(self.state_bytes(), before)

    def test_generated_destination_and_unstructured_touch(self):
        source = '.skill-tree/common/scripts/sample.py'
        target = '.skill-tree/skills/general/sample/scripts/sample.py'
        (self.root / target).parent.mkdir(parents=True)
        self.write_json(preview.RESOURCE_MAP, {'sample': {'scripts': {'sample.py': 'common/scripts/sample.py'}}})
        author = self.task('Edit shared resource', 300, [source])
        consumer = self.task('Edit packaged resource', 299, [target])
        unknown = self.task('Broad request', 298, ['src/*.py'])
        result = preview.preview(self.store, 2)

        self.assertEqual(result['selected_ids'], [author])
        self.assertEqual(result['selected'][0]['generated_consumers'], {source: [target]})
        self.assertEqual(result['after_merge']['regenerate_packages_for'], [author])
        deferred = {item['id']: item['reasons'] for item in result['deferred']}
        self.assertEqual(deferred[consumer], [{'kind': 'write-overlap', 'task_id': author, 'paths': [target, target]}])
        self.assertEqual(deferred[unknown][0]['kind'], 'unknown-touch')

    def test_dependencies_and_named_resources(self):
        self.write_json('.skill-tree/config/repository.json', {'recipes': {
            'fixture-browser': {'lane': 'browser', 'input_paths': ['browser.config']},
        }})
        self.write_json('.skill-tree/worktree-profile.json', {'schema': 1, 'exclusive_resources': ['browser:fixture']})
        prerequisite = self.task('Prerequisite', 100, ['prerequisite.py'])
        dependent = self.task('Depends on prerequisite', 400, ['dependent.py'], dependencies=[prerequisite])
        runtime = self.task('Uses browser', 390, ['app.py'], recipe='fixture-browser')
        other_runtime = self.task('Uses same browser', 380, ['other-app.py'], recipe='fixture-browser')
        state = self.store.load()
        with patch.object(self.store, 'load', return_value=state):
            result = preview.preview(self.store, 3)
            self.assertEqual(result['deferred'][0]['reasons'][0]['kind'], 'dependency-incomplete')
            self.assertEqual(result['deferred'][1]['reasons'][0], {
                'kind': 'exclusive-resource', 'task_id': runtime, 'resource': 'browser:fixture',
            })
            self.assertIn('browser.config', result['selected'][0]['check_inputs'])
            state['run_registry'] = {
                'claims': {prerequisite: 'WR-fixture'},
                'resources': {'browser:fixture': {'run_id': 'WR-fixture'}},
            }
            record = {'task_id': prerequisite, 'disposition': 'completed', 'source_fingerprints': {
                'prerequisite.py': 'old',
            }}
            with patch.object(self.store, 'outcomes', return_value=[record]):
                result = preview.preview(self.store, 3)
                reasons = {item['id']: [reason['kind'] for reason in item['reasons']]
                           for item in result['deferred']}
                self.assertEqual(reasons[dependent], ['dependency-revalidating'])
                self.assertIn('active-task-claim', reasons[prerequisite])
                self.assertIn('active-resource-claim', reasons[other_runtime])
                del state['run_registry']['claims'][prerequisite]
                stale = preview.preview(self.store, 3)
                self.assertEqual(stale['deferred'][0]['reasons'][0]['kind'], 'dependency-source-unverified')
                (self.root / 'prerequisite.py').write_text('accepted source')
                record['source_fingerprints']['prerequisite.py'] = workflow.file_hash(self.root / 'prerequisite.py')
                fresh = preview.preview(self.store, 3)
                self.assertEqual(fresh['selected'][0]['id'], dependent)
                self.assertEqual(fresh['selected'][0]['prerequisite_inputs'], ['prerequisite.py'])
                self.assertEqual(fresh['deferred'][-1]['reasons'][0], {
                    'kind': 'write-input-overlap', 'task_id': dependent,
                    'paths': ['prerequisite.py', 'prerequisite.py'],
                })

    def test_recovers_exact_review_scope_after_completion_and_claim_refresh(self):
        scope = '.skill-tree/common/scripts/sample.py'
        generated = '.skill-tree/skills/general/sample/scripts/sample.py'
        self.write_json(preview.RESOURCE_MAP, {'sample': {'scripts': {'sample.py': 'common/scripts/sample.py'}}})
        self.write_json('.skill-tree/config/repository.json', {'schema': 1, 'role': 'source', 'recipes': {
            'fixture-browser': {'lane': 'browser', 'argv': ['fixture-browser'], 'input_paths': ['prior.config']},
        }})
        self.write_json('.skill-tree/worktree-profile.json', {'schema': 1, 'exclusive_resources': ['browser:fixture']})
        for relative in (scope, generated, 'shared-read.py', 'source-proof.json', 'prior.config', 'later.config'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Fixture source baseline.\n')
        def git(root, *args):
            return subprocess.run(['git', '-C', str(root), *args], text=True, check=True, capture_output=True).stdout.strip()
        git(self.root, 'init', '-b', 'main')
        git(self.root, 'config', 'user.name', 'Review scope fixture')
        git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-m', 'Isolated review scope baseline')
        self.store = workflow.Store(self.root, allow_unselected=True)
        workflow.workspaces.setup(self.store, {})
        finished = self.task('Accepted source', 200, [scope, 'only-declared.py'], reads=['shared-read.py'],
                             recipe='fixture-browser')
        independent = self.task('Independent Ready work', 190, ['independent.py'], reads=['unrelated-read.py'])
        writing = self.task('Writes completed source', 180, [scope], reads=['unrelated-read.py'])
        reading = self.task('Writes accepted check input', 170, ['shared-read.py'], reads=['unrelated-read.py'])
        generated_write = self.task('Writes reviewed package output', 160, [generated], reads=['unrelated-read.py'])
        recorded_write = self.task('Writes committed evidence', 150, ['source-proof.json'], reads=['unrelated-read.py'])
        declared_write = self.task('Writes declared scope', 140, ['only-declared.py'], reads=['unrelated-read.py'])
        recipe_write = self.task('Writes accepted recipe input', 135, ['prior.config'], reads=['unrelated-read.py'])
        dependent = self.task('Needs completed source integration', 130, ['dependency.py'], reads=['unrelated-read.py'],
                              dependencies=[finished])
        runtime = self.task('Uses reserved browser', 120, ['runtime.py'], recipe='fixture-browser')
        neutral_start = workflow.Store(self.root, allow_unselected=True, neutral=True)
        run = workflow.start(neutral_start, 'all', workspace={'snapshot_ids': [finished],
                    'base_branch': 'main', 'local_base': True,
                    'local_base_authorization': 'The disposable test uses its local source baseline.',
                    'implementation_operation': 'implement-all'})
        worktree = Path(workflow.workspaces.runtime(self.root)['worktrees'][run['id']])
        run_store = workflow.Store(worktree, run['id'])
        workflow.begin_task(run_store, {'task_id': finished})
        (worktree / scope).write_text('Verified scoped file.\n')
        (worktree / 'source-proof.json').write_text('{"scope":"review window"}\n')
        resource = workflow.workspaces.resource(run_store, {'resource': 'browser:fixture'})
        session = {'project_root': str(worktree), 'authorization': 'A controlled disposable fixture.',
                   'profile_id': 'fixture-browser', 'deadline_utc': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                   'cleanup_seconds': 30, 'tool_identity': {'fixture': 'browser'}, 'session_identity': 'test-session',
                   'fixture_identity': 'preview-fixture', 'build_identity': 'preview-build',
                   'identity_evidence': ['source-proof.json']}
        attempt = workflow.prepare_check(run_store, {'task_id': finished, 'check_id': 'scoped-fixture', 'execution': session})
        workflow.record_check(run_store, {'task_id': finished, 'check_id': 'scoped-fixture',
            'attempt_id': attempt['attempt_id'], 'result': 'pass', 'classification': 'executed-control',
            'actual_lane': 'browser', 'environment_identity': attempt['environment_identity'],
            'counts': {'expected': 1, 'discovered': 1, 'passed': 1, 'failed': 0, 'skipped': 0},
            'cleanup': 'The synthetic browser receipt exercises preview with a real resource claim.',
            'evidence': ['source-proof.json']})
        workflow.mark_implemented(run_store, {'task_id': finished, 'changed_files': [scope, 'source-proof.json']})
        with patch.object(workflow, 'verified_implementation_review', return_value={'orchestration_hash': 'a'*64}):
            outcome = workflow.complete(run_store, {'task_id': finished, 'review_id': workflow.identity('DO'),
                'outcome': 'The verified fixture updated the scoped source.',
                'acceptance': [{'criterion': CRITERION, 'result': 'pass', 'evidence': ['source-proof.json']}],
                'source_fingerprints': workflow.fingerprints(run_store, [scope])})
        self.assertEqual(outcome['task_git_commit']['commit'], git(worktree, 'rev-parse', 'HEAD'))

        neutral = workflow.Store(self.root, allow_unselected=True, neutral=True)
        def selection():
            before = (neutral.future.read_bytes(), neutral.state.read_bytes(),
                      neutral.owned(workflow.OUTCOME_LEDGER).read_bytes(), git(worktree, 'status', '--short'))
            result = preview.preview(neutral, 12)
            self.assertEqual(before, (neutral.future.read_bytes(), neutral.state.read_bytes(),
                                     neutral.owned(workflow.OUTCOME_LEDGER).read_bytes(), git(worktree, 'status', '--short')))
            return result

        def expected_review_window(result):
            self.assertIn(independent, result['selected_ids'],
                          'Independent Ready work must survive the completed claim during review')
            reasons = {item['id']: item['reasons'] for item in result['deferred']}
            for candidate, relevant in ((writing, scope), (reading, 'shared-read.py'), (generated_write, generated),
                                        (recorded_write, 'source-proof.json'), (declared_write, 'only-declared.py'),
                                        (recipe_write, 'prior.config')):
                self.assertTrue(any(relevant in row.get('paths', []) and row.get('task_id')==finished
                                    for row in reasons[candidate]), reasons[candidate])
            self.assertTrue(any(row['kind']=='active-resource-claim' and row['resource']=='browser:fixture'
                                for row in reasons[runtime]), reasons[runtime])
            self.assertIn('dependency-source-unverified', {row['kind'] for row in reasons[dependent]})

        self.assertEqual(neutral.load()['run_registry']['claims'].get(finished), run['id'])
        expected_review_window(selection())
        workflow.checkpoint(run_store, {'phase':'resume-parent'})
        self.assertNotIn(finished, neutral.load()['run_registry']['claims'])
        expected_review_window(selection())
        workflow.workspaces.resource(run_store, {'resource': 'browser:fixture', 'release': True, 'token': resource['token']})
        released = selection()
        self.assertIn(runtime, released['selected_ids'])
        self.assertNotIn(writing, released['selected_ids'])
        self.assertNotIn(recipe_write, released['selected_ids'])
        policies = [root / '.skill-tree/worktree-profile.json' for root in (self.root, worktree)]
        policy_bytes = [path.read_bytes() for path in policies]
        try:
            for path in policies:
                path.unlink()
            without_policy = selection()
            self.assertIn(independent, without_policy['selected_ids'])
            self.assertNotIn(writing, without_policy['selected_ids'])
        finally:
            for path, saved in zip(policies, policy_bytes):
                path.write_bytes(saved)

        config = worktree / '.skill-tree/config/repository.json'
        config_bytes = config.read_bytes()
        changed_recipe = json.loads(config_bytes)
        changed_recipe['recipes']['fixture-browser']['input_paths'] = ['later.config']
        config.write_text(json.dumps(changed_recipe))
        try:
            changed_scope = selection()
            self.assertNotIn(recipe_write, changed_scope['selected_ids'])
            self.assertTrue(any(row['kind']=='review-scope-unverified'
                                and 'do not match completed validation' in row['detail']
                                for item in changed_scope['deferred'] if item['id']==recipe_write
                                for row in item['reasons']))
        finally:
            config.write_bytes(config_bytes)

        events = neutral.owned('.skill-tree/history/run-events/' + run['id'].lower())
        event = next(path for path in events.glob('e-*.json')
                     if any(row['id'] == outcome['id'] for row in json.loads(path.read_text())['outcomes']))
        event_bytes = event.read_bytes()
        ref = outcome['task_git_commit']['ref']
        commit = outcome['task_git_commit']['commit']
        base = outcome['task_git_commit']['parent']
        recipe_input = worktree / 'prior.config'
        identity_artifact = worktree / 'source-proof.json'
        input_bytes = recipe_input.read_bytes()
        artifact_bytes = identity_artifact.read_bytes()
        original_compare = preview.conflicts
        for label, update, restore in (
            ('applied event',
             lambda: event.write_bytes(event_bytes + b'\n'),
             lambda: event.write_bytes(event_bytes)),
            ('peer branch',
             lambda: git(self.root, 'update-ref', ref, base, commit),
             lambda: git(self.root, 'update-ref', ref, commit, base)),
            ('recipe input',
             lambda: recipe_input.write_bytes(input_bytes + b'changed'),
             lambda: recipe_input.write_bytes(input_bytes)),
            ('validation identity artifact',
             lambda: identity_artifact.write_bytes(artifact_bytes + b'changed'),
             lambda: identity_artifact.write_bytes(artifact_bytes)),
        ):
            with self.subTest(proof=label):
                changed = False
                def mutate_after_projection(*args):
                    nonlocal changed
                    if not changed:
                        update()
                        changed = True
                    return original_compare(*args)
                try:
                    with patch.object(preview, 'conflicts', side_effect=mutate_after_projection):
                        with self.assertRaisesRegex(ValueError, '(?i)review.*changed|planning inputs changed'):
                            preview.preview(neutral, 12)
                finally:
                    if changed:
                        restore()

        ledger = neutral.owned(workflow.OUTCOME_LEDGER)
        original = ledger.read_bytes()
        corrupted = {**outcome, 'task_git_commit': {**outcome['task_git_commit'], 'tree': 'a'*40}}
        ledger.write_text(json.dumps(corrupted, sort_keys=True) + '\n')
        try:
            invalid = selection()
            self.assertNotIn(independent, invalid['selected_ids'])
            self.assertTrue(any(row['task_id']==finished and row['kind']=='review-scope-unverified'
                                for row in next(item for item in invalid['deferred']
                                                if item['id']==independent)['reasons']))
        finally:
            ledger.write_bytes(original)

        workflow.workspaces.resource(run_store, {'resource': 'browser:fixture'})
        workflow.advance(run_store)
        with patch.object(workflow, 'verified_implementation_review', return_value={'orchestration_hash': 'b'*64}):
            workflow.freeze_reviewed_controller(run_store, {'review_id': workflow.identity('DO')})
        self.assertNotIn(writing, preview.preview(neutral, 1, [writing])['selected_ids'])
        with patch.object(workflow, 'verified_implementation_review', return_value={'orchestration_hash': 'b'*64}):
            merged = workflow.merge_reviewed_controller(run_store, {
                'owner_instruction': 'Integrate the checked disposable source fixture.'})
        self.assertEqual(merged['delivery']['status'], 'merged')
        retired = preview.preview(neutral, 1, [writing])
        self.assertEqual(retired['selected_ids'], [writing])

    def test_director_declared_resources_bound_batch_without_losing_other_candidates(self):
        first = self.task('Resource owner', 300, ['first.py'])
        second = self.task('Resource peer', 250, ['second.py'])
        third = self.task('Separate resource', 100, ['third.py'])
        module = runpy.run_path(str(HELPER))
        store = module['workflow'].Store(self.root, allow_unselected=True, neutral=True)
        before = self.state_bytes()
        result = module['preview'](store, 2, [first, second, third],
                                   declared_resources={first: ['one-editor'], second: ['one-editor']})
        self.assertEqual(result['selected_ids'], [first, third])
        self.assertEqual(result['deferred'][0]['reasons'],
                         [{'kind': 'exclusive-resource', 'task_id': first, 'resource': 'one-editor'}])
        self.assertEqual(self.state_bytes(), before)

    def test_required_pending_child_holds_ready_root(self):
        root = self.task('Main task', 100, ['fixture.py'])
        pending = workflow.intake(self.store, {
            'title': 'Required pending child', 'description': CRITERION, 'expected_behavior': CRITERION,
            'priority': 101, 'root_task_id': root, 'related_task_id': root, 'relation': 'subtask',
        })['id']
        result = preview.preview(self.store, 2)
        self.assertEqual(result['selected_ids'], [])
        self.assertEqual(result['deferred'][0]['reasons'], [
            {'kind': 'required-pending-work', 'pending_ids': [pending]},
        ])

    def test_shared_generated_manifest_regenerates_after_merge(self):
        package = '.skill-tree/skills/web/sample'
        manifest = package + '/references/plugin-bindings.json'
        self.write_json(manifest, {})
        (self.root / package / 'references/web-development.md').touch()
        self.write_json(preview.RESOURCE_MAP, {'sample': {'scripts': {'a.py': 'common/scripts/a.py'}}})
        self.write_json(preview.FLAVORS, {'flavors': {'web': {
            'resources': {'references/web-development.md': 'domains/web/development.md'},
        }}})
        a = self.task('Edit shared resource', 300, ['.skill-tree/common/scripts/a.py'])
        b = self.task('Edit Web resource', 299, ['.skill-tree/domains/web/development.md'])

        result = preview.preview(self.store, 2)
        self.assertEqual(result['selected_ids'], [a, b])
        self.assertEqual(result['after_merge']['shared_generated_outputs'], {manifest: [a, b]})
        self.assertEqual(result['after_merge']['regenerate_packages_for'], [a, b])

    def test_refuses_missing_checkpoint_after_initialization(self):
        self.task('Needs the retained state', 100, ['fixture.py'])
        self.store.state.unlink()
        before = self.state_bytes()
        result = self.command(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('restore the matching checkpoint', result.stderr)
        self.assertEqual(self.state_bytes(), before)

    def test_refuses_an_in_progress_transaction(self):
        self.write_json('.skill-tree/.transaction.json', {})
        before = self.state_bytes()
        result = self.command(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn('recovery in progress', result.stderr)
        self.assertEqual(self.state_bytes(), before)

    def test_installed_package_runs_without_selectors(self):
        task = self.task('Package fixture', 100, ['fixture.py'])
        subprocess.run([
            'node', str(CORE / 'bin/install.js'), '--target', str(self.root), '--flavor', 'general',
            '--only', 'codex', '--skills', 'skill-tree-implement-all', '--non-interactive',
        ], text=True, capture_output=True, check=True, timeout=50)
        skill = self.root / '.agents/skills/skill-tree-implement-all'
        operation = (skill / 'SKILL.md').read_text()
        self.assertIn('An ordinary Implement All invocation starts execution for the full initial prioritized queue.', operation)
        self.assertIn('An explicit Ready preview request runs the read-only preview.', operation)
        self.assertIn('For a Director-managed operation', operation)
        self.assertIn('Use `run-advance-all` to launch eligible assignments', operation)
        self.assertIn('For a standalone operation or an explicitly selected direct project route', operation)
        self.assertIn('references/parallel-preview.md', operation)
        self.assertIn('workflow-state.py group-selection', operation)
        before = self.state_bytes()
        result = self.command(script=skill / 'scripts/parallel-preview.py')
        self.assertEqual(json.loads(result.stdout)['selected_ids'], [task])
        self.assertEqual(self.state_bytes(), before)


if __name__ == '__main__':
    unittest.main()
