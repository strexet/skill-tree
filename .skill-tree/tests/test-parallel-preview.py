import importlib.util
import json
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
        self.assertIn('references/parallel-preview.md', operation)
        self.assertIn('workflow-state.py group-selection', operation)
        before = self.state_bytes()
        result = self.command(script=skill / 'scripts/parallel-preview.py')
        self.assertEqual(json.loads(result.stdout)['selected_ids'], [task])
        self.assertEqual(self.state_bytes(), before)


if __name__ == '__main__':
    unittest.main()
