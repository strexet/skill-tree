from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


CORE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('director_status_fixtures', CORE / 'tests/test-director-area-bindings.py')
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
DIRECTOR = FIXTURE.DIRECTOR
WF = DIRECTOR.WF
WS = DIRECTOR.WS


class DirectorStatusTests(unittest.TestCase):
    setUp = FIXTURE.DirectorAreaBindingTests.setUp
    git = FIXTURE.DirectorAreaBindingTests.git
    init_repo = FIXTURE.DirectorAreaBindingTests.init_repo
    area = FIXTURE.DirectorAreaBindingTests.area
    snapshot = FIXTURE.DirectorAreaBindingTests.snapshot
    register = FIXTURE.DirectorAreaBindingTests.register

    def task(self, repo, title):
        store = WF.Store(repo, allow_unselected=True)
        pending = WF.intake(store, {'title': title, 'description': 'Inspect lantern scope.',
                                    'expected_behavior': 'Exact scope is visible.'})
        criterion = 'The observed lantern scope matches the selected fixture.'
        check = {'id': 'scope', 'recipe_id': 'static-inspection', 'criteria': [criterion],
                 'sources': ['story/source.txt'], 'parameters': {}, 'assertion': criterion, 'timing': 'immediate'}
        body = ('Goal:\n- Inspect visible source scope.\n\nTouch:\n- story/source.txt\n\nValidation:\n```json\n'
                + json.dumps({'checks': [check]}) + '\n```\n\nAcceptance:\n- ' + criterion + '\n')
        result = WF.process(store, {'selectors': [pending['id']],
                                    'dispositions': {pending['id']: {'status': 'promoted', 'reason': 'Scope is exact.'}},
                                    'tasks': [{'title': title, 'body': body, 'parent_pending_ids': [pending['id']]}]})
        return result['created_ids'][0]

    def run_fixture(self, repo, task, path):
        remote = self.base / (path.name + '-remote.git')
        self.git(self.base, 'init', '--bare', str(remote))
        self.git(repo, 'remote', 'add', 'origin', str(remote))
        return WF.start(WF.Store(repo, allow_unselected=True), 'next', task,
                        workspace={'base_branch': 'develop', 'local_base': True,
                                   'local_base_authorization': 'Disposable Director status control authorizes local base.',
                                   'worktree': str(path)})

    def test_status_preserves_all_bytes_and_reports_independent_work(self):
        art = self.task(self.repo, 'Build lantern art')
        story = self.task(self.repo, 'Review lantern story')
        self.register()
        (self.repo / 'art/source.txt').write_text('Local unrelated art remains intact.\n')
        before_parent = self.snapshot(self.parent)
        before_child = self.snapshot(self.repo)
        requests = {'assignments': [
            {'id': 'change-art', 'area_id': 'art', 'task_id': art,
             'workspace': 'existing-checkout', 'write_paths': ['source.txt']},
            {'id': 'change-story', 'area_id': 'story', 'task_id': story,
             'workspace': 'existing-checkout', 'write_paths': ['source.txt']},
        ]}
        with patch.object(WF.Store, 'lock', side_effect=AssertionError('read acquired writer')):
            status = self.director.status(requests)
        areas = {area['id']: area for area in status['areas']}
        projected = {assignment['id']: assignment for assignment in status['assignments']}
        self.assertEqual(areas['story']['state'], 'ready')
        self.assertEqual(areas['art']['state'], 'dirty')
        self.assertEqual(areas['art']['dirty_paths'], ['art/source.txt'])
        self.assertEqual(status['available_independent'], ['change-story'])
        self.assertIn('overlapping-dirty-paths', projected['change-art']['prerequisites'])
        self.assertEqual(projected['change-story']['child']['task_id'], story)
        self.assertEqual(projected['change-story']['child']['task_ref'], '.skill-tree/documents/future.md')
        self.assertEqual(projected['change-story']['workspace']['source_isolation'], 'serial-checkout')
        self.assertEqual(self.snapshot(self.parent), before_parent)
        self.assertEqual(self.snapshot(self.repo), before_child)
        self.assertNotIn(str(self.base), json.dumps(status))

    def test_workspace_choices_and_pending_source_overlap_are_explicit(self):
        story = self.task(self.repo, 'Review first story')
        second = self.task(self.repo, 'Review second story')
        art = self.task(self.repo, 'Draft candidate artifact')
        self.register()
        root = {'area_id': 'story', 'workspace': 'existing-checkout', 'write_paths': ['source.txt']}
        requests = {'assignments': [
            {'id': 'first', 'task_id': story, **root},
            {'id': 'second', 'task_id': second, **root},
            {'id': 'candidate', 'area_id': 'art', 'task_id': art, 'workspace': 'artifact'},
            {'id': 'needs-clone', 'area_id': 'art', 'workspace': 'separate-clone'},
            {'id': 'needs-runtime', 'area_id': 'art', 'workspace': 'separate-runtime'},
        ]}
        status = self.director.status(requests)
        rows = {entry['id']: entry for entry in status['assignments']}
        self.assertEqual(rows['first']['overlapping_assignments'], ['second'])
        self.assertEqual(rows['second']['overlapping_assignments'], ['first'])
        self.assertEqual(rows['candidate']['workspace']['selected'], 'artifact-directory')
        self.assertFalse((self.parent / rows['candidate']['workspace']['artifact_relative_path']).exists())
        self.assertIn('separate-clone-required', rows['needs-clone']['prerequisites'])
        self.assertIn('separate-runtime-required', rows['needs-runtime']['prerequisites'])
        self.assertEqual(status['available_independent'], ['candidate'])

    def test_duplicate_child_task_and_planned_resource_claim_are_visible(self):
        task = self.task(self.repo, 'Inspect one exact task')
        other = self.task(self.repo, 'Inspect a separate task')
        self.register()
        shared = {'workspace': 'artifact', 'resources': ['candidate:renderer']}
        rows = self.director.status({'assignments': [
            {'id': 'same-art', 'area_id': 'art', 'task_id': task, **shared},
            {'id': 'same-story', 'area_id': 'story', 'task_id': task, **shared},
            {'id': 'other', 'area_id': 'story', 'task_id': other, **shared},
        ]})
        self.assertEqual(rows['available_independent'], [])
        first, second, third = rows['assignments']
        self.assertIn('duplicate-child-task', first['prerequisites'])
        self.assertIn('duplicate-child-task', second['prerequisites'])
        self.assertNotIn('duplicate-child-task', third['prerequisites'])
        self.assertEqual(first['overlapping_resource_assignments'], ['other', 'same-story'])
        self.assertIn('assignment-resource-overlap', third['prerequisites'])

    def test_exact_recorded_worktree_and_other_queue_runtime_claim(self):
        story = self.task(self.repo, 'Implement lantern story')
        independent = self.task(self.repo, 'Review independent change')
        worktree = self.base / 'worktree'
        run = self.run_fixture(self.repo, story, worktree)
        WF.checkpoint(WF.Store(self.repo, run['id']), {'stop_reason': 'Awaiting local fixture review.'})
        external = self.base / 'external'
        external_queue = self.init_repo(external, label='independent runtime')
        outside = self.task(external, 'Verify external area')
        outside_run = self.run_fixture(external, outside, self.base / 'outside-worktree')
        WS.resource(WF.Store(external, outside_run['id']), {'resource': 'editor:keeper'})
        self.register({**self.request, 'areas': [*self.request['areas'], self.area('external', 'unity', external, 'art')]})
        before = self.snapshot(self.repo), self.snapshot(worktree), self.snapshot(external)
        requests = {'assignments': [
            {'id': 'blocked-story', 'area_id': 'story', 'task_id': story, 'run_id': run['id'],
             'workspace': 'recorded-worktree', 'write_paths': ['source.txt'], 'resources': ['editor:keeper']},
            {'id': 'wrong-run', 'area_id': 'story', 'task_id': independent, 'run_id': run['id'],
             'workspace': 'recorded-worktree', 'write_paths': ['source.txt']},
        ]}
        status = self.director.status(requests)
        blocked, wrong = status['assignments']
        self.assertEqual(blocked['state'], 'blocked')
        self.assertEqual(blocked['workspace']['worktree_id'], run['id'])
        self.assertEqual(blocked['workspace']['runtime_isolation'], 'requires-separate-proof')
        self.assertEqual(blocked['resource_conflicts'], {'editor:keeper': [{'queue_id': external_queue, 'run_id': outside_run['id']}]})
        self.assertIn('recorded-child-stop', blocked['prerequisites'])
        self.assertEqual(wrong['state'], 'mismatched')
        self.assertNotEqual(wrong['workspace']['selected'], 'recorded-worktree')
        self.assertEqual(status['available_independent'], [])
        self.assertEqual((self.snapshot(self.repo), self.snapshot(worktree), self.snapshot(external)), before)

    def test_direct_project_run_keeps_queue_run_and_task_identity(self):
        task = self.task(self.repo, 'Inspect the whole project')
        run = self.run_fixture(self.repo, task, self.base / 'direct-worktree')
        whole = self.area('project', 'general', self.repo, '.')
        source = self.base / 'maintenance-source'
        self.init_repo(source)
        maintenance = self.area('maintenance', 'source-maintenance', source, '.skill-tree')
        self.register({**self.request, 'areas': [whole, maintenance]})
        before = self.snapshot(self.parent), self.snapshot(self.repo)
        view = self.director.status()['project_work']
        self.assertEqual(len(view), 1)
        self.assertEqual(view[0]['queue_id'], self.queue)
        self.assertEqual(view[0]['area_ids'], ['project'])
        direct = view[0]['runs'][0]
        self.assertEqual((direct['run_id'], direct['task_ids']), (run['id'], [task]))
        self.assertEqual(direct['route'], 'direct-project')
        self.assertEqual(direct['audit_coverage'], 'outside-director-assignment')
        self.assertEqual(self.director.status({'project_work':{'area_id':'project', 'run_id':run['id']}})['project_work'][0]['runs'], view[0]['runs'])
        self.assertEqual((self.snapshot(self.parent), self.snapshot(self.repo)), before)

    def test_standalone_outcome_retains_task_and_outcome_without_a_run(self):
        task_id, outcome_id = WF.identity('T'), WF.identity('O')
        area = {'id':'site', 'queue_id':self.queue, 'scope':'.', 'role':'web', 'allowed_effects':['status']}
        queue = {'status':'ready', 'state':{'run_registry':{'runs':{}}},
                 'outcomes':{task_id:{'task_id':task_id, 'id':outcome_id, 'disposition':'completed', 'run_id':None}}}
        row, = self.director._project_work({'areas':{'site':area}}, {self.queue:queue}, None)
        self.assertEqual(row['runs'], [])
        self.assertEqual(row['standalone_outcomes'], [{'task_id':task_id, 'outcome_id':outcome_id, 'run_id':None,
            'disposition':'completed', 'route':'direct-project', 'audit_coverage':'outside-director-assignment'}])

    def test_status_distinguishes_unbound_unavailable_and_mismatched(self):
        self.register()
        bindings = self.parent / DIRECTOR.BINDINGS
        original = bindings.read_bytes()
        bindings.unlink()
        self.assertEqual({area['state'] for area in self.director.status()['areas']}, {'unbound'})
        bindings.write_bytes(original)
        moved = self.base / 'moved'
        self.repo.rename(moved)
        self.assertEqual({area['state'] for area in self.director.status()['areas']}, {'unavailable'})
        self.init_repo(self.repo, label='wrong replacement')
        self.assertEqual({area['state'] for area in self.director.status()['areas']}, {'mismatched'})

    def test_completed_dependency_evidence_belongs_to_original_run(self):
        task_id, original, later = WF.identity('T'), WF.identity('WR'), WF.identity('WR')
        outcome_id = WF.identity('O')
        queue = {
            'outcomes': {task_id: {'id': outcome_id, 'run_id': original, 'disposition': 'completed'}},
            'state': {'tasks': [], 'run_registry': {'claims': {}, 'runs': {
                original: {'admitted_task_ids': [task_id], 'completion_refs': {task_id: outcome_id}},
                later: {'admitted_task_ids': [task_id]},
            }}},
        }
        wrong = {'task_id': task_id, 'run_id': later}
        self.assertEqual(DIRECTOR._status_child(queue, wrong), ('mismatched', None))
        exact = {'task_id': task_id, 'run_id': None}
        self.assertEqual(DIRECTOR._status_child(queue, exact)[0], 'completed')
        self.assertEqual(exact['run_id'], original)

    def test_cli_status_requires_no_input_or_writes(self):
        self.register()
        before = self.snapshot(self.parent), self.snapshot(self.repo)
        path = CORE / 'common/scripts/director-state.py'
        status = json.loads(subprocess.check_output(['python3', str(path), 'status', str(self.parent)],
                                                    text=True, timeout=20))
        self.assertEqual(status['director_id'], self.request['director_id'])
        self.assertEqual(status['assignments'], [])
        self.assertEqual((self.snapshot(self.parent), self.snapshot(self.repo)), before)


if __name__ == '__main__':
    unittest.main()
