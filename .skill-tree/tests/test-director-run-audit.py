"""Audit real disposable Core receipts without modifying owners or exporting data."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / 'common/scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUDIT = load('director_run_audit_test', SCRIPTS / 'director-audit.py')
FIXTURE = load('director_run_audit_dispatch_fixture', HERE / 'test-director-dispatch-receipts.py')
RUN = load('director_run_audit_runner', SCRIPTS / 'director-run.py')
QUESTIONS = load('director_run_audit_questions', SCRIPTS / 'director-questions.py')
D, WF = AUDIT.D, AUDIT.D.WF
RUN.D, RUN.QUESTIONS, QUESTIONS.wf = D, QUESTIONS, WF
PRODUCT_CHECK = 'verify-game-fixture'
RUNTIME_CHECK = 'wait-for-runtime'
PRIVATE = 'private-token-abc /tmp/owner-only and raw message'


class DirectorRunAuditTests(unittest.TestCase):
    def setUp(self):
        fixture = FIXTURE.DispatchTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.registry = D.DirectorRegistry(fixture.parent)
        self.child = WF.Store(fixture.root, neutral=True)
        self.worktree = fixture.base / 'lantern'
        self.fixture_generation = {'source_sha256': WF.digest(b'disposable authored helper bytes'),
                                   'installed_sha256': WF.digest(b'disposable installed helper bytes')}
        self.generation_proof = {'profile_sha256': WF.digest(b'fixture profile bytes'),
                                 'package_sha256': WF.digest(b'fixture package bytes')}
        config = fixture.root / '.skill-tree/config/repository.json'
        workflow = fixture.root / '.skill-tree/common/scripts/workflow-state.py'
        workflow.parent.mkdir(parents=True)
        workflow.write_bytes(Path(WF.__file__).read_bytes())
        config.write_text(WF.dump({'schema': 1, 'role': 'source', 'recipes': {
            AUDIT.RECIPE: {'lane': 'unit', 'argv': ['python3', 'audit-fixture-control.py'], 'input_paths': []}}}))
        D.WS.local_git_text(fixture.root, 'add', str(config.relative_to(fixture.root)), str(workflow.relative_to(fixture.root)))
        D.WS.git(fixture.root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Audit fixture inputs')
        areas = [self.area('maintenance', 'source-maintenance', '.skill-tree', ['status']),
                 self.area('game', 'game', '.', ['status', 'audit', 'launch'])]
        registration = {'director_id': 'pilot', 'areas': areas}
        self.registry.apply({**registration, 'expected_preview_sha256': self.registry.preview(registration)['preview_sha256']})
        self.task = self.create_task()
        self.planner = D._plan_helper(self.registry)
        self.objective_id, self.plan_id, self.director_id = (WF.identity(prefix) for prefix in ('OB', 'PL', 'DR'))
        self.plan_sha = self.frozen_plan()
        self.own_runner = RUN.DirectorRun(self.registry, self.planner.frozen, lambda _: fixture.root)
        parent = self.own_runner.start({'director_run_id': self.director_id, 'plan_id': self.plan_id, 'plan_revision': 1,
                                       'objective_id': self.objective_id, 'plan_sha256': self.plan_sha,
                                       'assignment_ids': ['snapshot-check'], 'owner': {'actor': 'petr',
                                           'reference': 'owner-start', 'kind': 'owner-message'},
                                       'authority': {'snapshot-check': ['launch']}, 'approved_defaults': []})
        result = self.own_runner.dispatch({'director_run_id': self.director_id, 'expected_run_sha256': parent['run_sha256'],
                                           'assignment_id': 'snapshot-check', 'operation': 'start',
                                           'request': {key: value for key, value in fixture.start_request().items()
                                                       if key != 'director_dispatch'}})
        self.run_id = result['result']['id']
        self.store = WF.Store(fixture.root, run_id=self.run_id)
        D.WS.ensure_workspace(self.store, result['result'])
        self.request = {'director_run_id': self.director_id,
                        'selections': [{'assignment_id': 'snapshot-check', 'run_id': self.run_id}]}
        self.audit = AUDIT.DirectorAudit(self.registry)
        relative = self.worktree / AUDIT.INSTALLED
        relative.parent.mkdir(parents=True)
        relative.write_bytes(b'disposable installed helper bytes')
        result_file = self.worktree / AUDIT.RESULT
        result_file.parent.mkdir(parents=True)
        result_file.write_text(WF.dump(AUDIT.OBSERVED_RESULT))
        WF.advance(self.store)
        WF.begin_task(self.store, {'task_id': self.task})

    def area(self, identifier, role, scope, effects):
        return {'id': identifier, 'role': role, 'scope': scope, 'checkout': str(self.fixture.root),
                'capabilities': ['core-task'], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': effects}

    def create_task(self):
        title = 'Audit fixture snapshot selection'
        assertion = 'Preserve the exact selected Markdown path.'
        pending = WF.intake(self.child, {'title': title, 'description': assertion, 'expected_behavior': assertion})
        check = {'recipe_id': AUDIT.RECIPE, 'criteria': [assertion], 'parameters': {}, 'assertion': assertion,
                 'timing': 'immediate'}
        specs = [{**check, 'id': name, 'sources': [source]} for name, source in (
            (AUDIT.CHECK, AUDIT.INSTALLED), (PRODUCT_CHECK, 'source.txt'), (RUNTIME_CHECK, 'source.txt'))]
        body = ('Goal:\n- Preserve the selected path.\n\nTouch:\n- source.txt\n\nValidation:\n```json\n'
                + WF.dump({'checks': specs}) + '```\n\nAcceptance:\n- ' + assertion + '\n')
        return WF.process(self.child, {'selectors': [pending['id']], 'dispositions': {pending['id']:
            {'status': 'promoted', 'reason': 'Disposable audit fixture.'}}, 'tasks': [{'title': title, 'body': body,
            'parent_pending_ids': [pending['id']]}]})['created_ids'][0]

    def frozen_plan(self):
        ledger = self.planner.ledger
        request = {'objective_id': self.objective_id, 'expected_current_sha256': None, 'intent': {
            'owner_ref': 'fixture-owner', 'title': 'Audit one selected child', 'description': 'Keep private evidence. ' + PRIVATE,
            'acceptance': [{'id': 'check', 'criterion': 'Match selected check receipts.'}]}}
        reviewed = ledger.preview(request)
        objective = ledger.apply({**request, 'expected_preview_sha256': reviewed['preview_sha256']})['current']
        raw, registry, _, basis = ledger._load(self.objective_id)
        area = AUDIT.O._area_identity(registry['areas']['game'])
        task = next(item for item in WF.parse(self.child.text()) if item['id'] == self.task)
        scope = {'id': 'snapshot-check', 'area': area, 'depends_on': [], 'authority_ref': 'fixture-owner',
                 'pins': [], 'resources': [], 'effects': ['launch'], 'workspace': 'recorded-worktree',
                 'check': AUDIT.CHECK, 'child': {'task_id': self.task, 'body_sha256': WF.digest(task['body'].encode())}}
        plan = {'schema': 1, 'director_id': 'pilot', 'plan_id': self.plan_id, 'plan_revision': 1,
                'objective': {'objective_id': self.objective_id, 'objective_revision': objective['revision'],
                              'objective_sha256': objective['sha256']}, 'assignments': [scope]}
        sha = self.planner.C.digest(plan)
        raw['plans'][AUDIT.O._plan_key(self.plan_id, 1)] = {'frozen': plan, 'plan_sha256': sha,
            'objective_revision': objective['revision'], 'objective_sha256': objective['sha256']}
        path = AUDIT.O.objective_path(self.objective_id)
        with self.registry.store.lock(local_delivery={'kind': 'fixture-plan'}):
            self.registry.store.expect_unchanged(path, basis[path])
            self.registry.store.commit({path: WF.dump(raw)})
        return sha

    def record(self, check_id, *, classification='executed-control', result='fail', signature=AUDIT.SIGNATURE):
        attempt = WF.prepare_check(self.store, {'task_id': self.task, 'check_id': check_id})
        record = WF.record_check(self.store, {'task_id': self.task, 'check_id': check_id, 'attempt_id': attempt['attempt_id'],
            'classification': classification, 'result': result, 'actual_lane': 'unit',
            'environment_identity': attempt['environment_identity'], 'cleanup': PRIVATE, 'failure_signature': signature,
            'evidence': [AUDIT.RESULT] if check_id == AUDIT.CHECK else ['source.txt']})
        return record['attempt_id']

    def files(self, root):
        return {path.relative_to(root): path.read_bytes() for path in (root / '.skill-tree').rglob('*') if path.is_file()}

    def read(self, request=None, *, generation=True):
        observed = (self.fixture_generation, self.generation_proof) if generation else None
        with patch.object(AUDIT, '_generation', return_value=observed):
            return self.audit.read(request or self.request)

    def test_duplicate_source_receipts_group_and_keep_other_signals_out_of_pending(self):
        runtime = self.record(RUNTIME_CHECK, classification='transport-uncertainty', result='unavailable', signature=PRIVATE)
        product = self.record(PRODUCT_CHECK, signature=PRIVATE)
        attempts = {self.record(AUDIT.CHECK), self.record(AUDIT.CHECK)}
        before = [self.files(root) for root in (self.fixture.parent, self.fixture.root, self.worktree)]
        report = self.read()
        self.assertEqual([self.files(root) for root in (self.fixture.parent, self.fixture.root, self.worktree)], before)
        self.assertEqual(report, self.read())
        self.assertNotIn(PRIVATE, WF.dump(report))
        self.assertNotIn(str(self.fixture.base), WF.dump(report))
        source, = report['findings']
        self.assertEqual(source['finding_sha256'], AUDIT.source_finding_digest(source))
        self.assertEqual(source['generation'], self.fixture_generation)
        self.assertEqual({item['attempt_id'] for item in source['evidence']}, attempts)
        self.assertEqual(len({item['event_id'] for item in source['evidence']}), 2)
        self.assertEqual({item['attempt_id']: item['classification'] for item in report['observations']},
                         {runtime: 'runtime-prerequisite', product: 'product'})
        no_generation = self.read(generation=False)
        self.assertEqual(no_generation['findings'], [])
        self.assertIn('source-proof-unavailable', {item['symptom'] for item in no_generation['observations']})

    def test_only_exact_existing_reviewed_export_supplies_missing_canonical_event(self):
        self.record(AUDIT.CHECK)
        first, = self.read()['findings']
        event = first['evidence'][0]['event_id']
        export = WF.export_run(self.store)
        file = self.worktree / export['path']
        digest = WF.file_hash(file)
        canonical_event = self.fixture.root / AUDIT.HISTORY / self.run_id.lower() / (event.lower() + '.json')
        canonical_event.unlink()
        gap, = [item for item in self.read()['coverage_gaps'] if item['reason'] == 'native-event-sequence-unavailable']
        self.assertEqual((gap['first_event_sequence'], gap['last_event_sequence']),
                         (first['evidence'][0]['event_sequence'],) * 2)
        selection = {**self.request['selections'][0], 'event_ids': [event]}
        request = {**self.request, 'selections': [selection]}
        self.assertEqual(self.read(request)['findings'], [])
        self.assertEqual(self.read(request)['coverage_gaps'][0]['event_id'], event)
        with self.assertRaisesRegex(ValueError, 'reviewed journal export'):
            self.read({**request, 'selections': [{**selection, 'journal_export_sha256': '0' * 64}]})
        before = self.files(self.worktree)
        recovered, = self.read({**request, 'selections': [{**selection, 'journal_export_sha256': digest}]})['findings']
        self.assertEqual(recovered['finding_sha256'], first['finding_sha256'])
        self.assertEqual(recovered['evidence'][0]['event_source'], 'reviewed-export')
        self.assertEqual(recovered['evidence'][0]['event_path'], export['path'])
        self.assertFalse([item for item in self.read({**request, 'selections': [
            {**self.request['selections'][0], 'journal_export_sha256': digest}]})['coverage_gaps']
            if item['reason'] == 'native-event-sequence-unavailable'])
        self.assertEqual(self.files(self.worktree), before)

    def test_diagnoses_prepared_check_and_repeated_failure_without_private_inputs(self):
        deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        attempt = WF.prepare_check(self.store, {'task_id': self.task, 'check_id': PRODUCT_CHECK,
            'launch': {'assertion': PRIVATE, 'cheaper_evidence_insufficient': PRIVATE, 'authorization': PRIVATE,
                       'deadline_utc': deadline, 'cleanup_seconds': 1, 'project_root': str(self.worktree),
                       'execution_profile': PRIVATE}})
        report = self.read()
        status, = report['child_status']
        opened, = status['open_check_attempts']
        self.assertEqual((opened['attempt_id'], opened['deadline_utc'], opened['lane']),
                         (attempt['attempt_id'], deadline, 'unit'))
        prepared, = [item for item in report['child_timeline'] if item['event'] == 'check-prepared']
        self.assertEqual(prepared['prepared_at'], opened['prepared_at'])
        self.assertTrue((self.fixture.root / prepared['event_path']).is_file())
        self.assertEqual(prepared['event_recorded_at'], WF.run_event_recorded_at(
            json.loads((self.fixture.root / prepared['event_path']).read_bytes())))
        WF.record_check(self.store, {'task_id': self.task, 'check_id': PRODUCT_CHECK,
            'attempt_id': attempt['attempt_id'], 'classification': 'executed-control', 'result': 'fail',
            'actual_lane': 'unit', 'environment_identity': attempt['environment_identity'],
            'cleanup': PRIVATE, 'failure_signature': PRIVATE, 'evidence': ['source.txt'],
            'timing': {'tool_wall_seconds': 2.5}})
        latest = self.record(PRODUCT_CHECK, signature=PRIVATE)
        report = self.read()
        status, = report['child_status']
        self.assertEqual(status['open_check_attempts'], [])
        self.assertEqual(status['checkpoint']['hold'], 'repeated-check-failure')
        results = [item for item in report['child_timeline'] if item['event'] == 'check-recorded']
        self.assertEqual([item['attempt_id'] for item in results], [attempt['attempt_id'], latest])
        self.assertEqual(len({item['diagnostic_key'] for item in results}), 1)
        self.assertEqual(results[0]['timing'], {'tool_wall_seconds': 2.5})
        self.assertIn('recorded_at', results[0])
        self.assertEqual(len(results[0]['recorded_evidence_sha256']), 1)
        self.assertNotIn(PRIVATE, WF.dump(report))
        self.assertNotIn(str(self.fixture.base), WF.dump(report))

    def test_legacy_undated_events_still_report_and_selected_subset_claims_no_hole(self):
        self.record(PRODUCT_CHECK)
        event = next(item for item in self.read()['child_timeline'] if item['event'] == 'check-recorded')
        path = self.fixture.root / event['event_path']
        legacy = json.loads(path.read_bytes())
        legacy.pop('recorded_at')
        path.write_text(WF.dump(legacy))
        selection = {**self.request['selections'][0], 'event_ids': [event['event_id']]}
        report = self.read({**self.request, 'selections': [selection]})
        current, = report['child_timeline']
        self.assertNotIn('event_recorded_at', current)
        self.assertIn('recorded_at', current)
        self.assertEqual(report['child_status'][0]['undated_events'], 1)
        self.assertEqual(report['child_status'][0]['event_scope'], 'selected')
        self.assertFalse([item for item in report['coverage_gaps'] if item['reason'] == 'native-event-sequence-unavailable'])
        parent_only = self.read({**self.request, 'selections': []})
        self.assertEqual(parent_only['child_timeline'], [])
        self.assertEqual(parent_only['director_timeline'][0]['event'], 'run-started')
        recorded, = [item for item in parent_only['director_timeline'] if item['event'] == 'dispatch-recorded']
        self.assertEqual(recorded['child_run_id'], self.run_id)
        parent_path = self.fixture.parent / parent_only['director_status']['run_path']
        legacy_parent = json.loads(parent_path.read_bytes())
        legacy_parent.pop('timeline')
        parent_path.write_text(WF.dump(legacy_parent))
        old_parent = self.read({**self.request, 'selections': []})
        self.assertEqual(old_parent['director_timeline'], [])
        self.assertEqual(old_parent['coverage_gaps'][0]['reason'], 'director-timeline-start-unavailable')

    def test_generation_requires_exact_bundle_and_codex_resource_bytes(self):
        installation = self.worktree / '.skill-tree/installation'
        source_relative = AUDIT.SOURCE.removeprefix('.skill-tree/')
        bundle_relative = '.skill-tree/installation/source/' + source_relative
        bundle = self.worktree / bundle_relative
        bundle.parent.mkdir(parents=True)
        bundle.write_bytes(b'disposable authored helper bytes')
        profile = installation / 'profile.json'
        profile.write_text(WF.dump({
            'identity': 'a' * 64, 'source_digests': {source_relative: self.fixture_generation['source_sha256']},
            'bundle_digests': {bundle_relative: self.fixture_generation['source_sha256']},
            'destinations': {AUDIT.DESTINATION: {'name': AUDIT.SNAPSHOT, 'provider': 'codex',
                'files': {AUDIT.RESOURCE: self.fixture_generation['installed_sha256']},
                'identity': self.generation_proof['package_sha256']}}, 'recipes': {AUDIT.RECIPE: {'lane': 'unit'}},
        }))
        verified = {'kind': 'owned-profile', 'identity': 'a' * 64, 'sha256': WF.file_hash(profile)}
        with patch.object(D, '_inspect_profile', return_value=verified):
            self.assertEqual(AUDIT._generation(self.worktree), (self.fixture_generation, {
                'profile_sha256': verified['sha256'], 'package_sha256': self.generation_proof['package_sha256']}))
            (self.worktree / AUDIT.INSTALLED).write_bytes(b'Changed local package')
            self.assertIsNone(AUDIT._generation(self.worktree))

    def test_wrong_run_and_private_owner_wait_are_bounded(self):
        view = self.own_runner.status({'director_run_id': self.director_id})
        start = view['assignments']['snapshot-check']['dispatches']['start']
        question = self.own_runner.open_question({'director_run_id': self.director_id,
            'expected_run_sha256': view['run_sha256'], 'assignment_id': 'snapshot-check',
            'question_id': WF.identity('DQ'), 'attempt_id': WF.identity('DA'), 'child_run_id': self.run_id,
            'task_id': self.task, 'start_receipt_sha256': start['receipt_sha256'], 'recipient': 'petr',
            'requester': 'fixture-worker', 'key': 'fixture-choice', 'options': [{'id': 'first', 'label': PRIVATE},
                {'id': 'second', 'label': 'Another owner option'}], 'recommendation': 'first', 'affected_areas': ['game'],
            'blocked_action': PRIVATE, 'deadline': '2099-01-01T00:00:00+00:00'})['question']
        report = self.read()
        owner, = report['observations']
        self.assertEqual((owner['question_id'], owner['classification']), (question['question_id'], 'owner-wait'))
        self.assertEqual(report['findings'], [])
        self.assertNotIn(PRIVATE, WF.dump(report))
        unknown = deepcopy(self.request)
        unknown['selections'][0]['run_id'] = WF.identity('WR')
        with self.assertRaisesRegex(ValueError, 'outside the recorded Director start'):
            self.read(unknown)
        lock = self.fixture.root / '.skill-tree/.writer-lock'
        lock.write_text('Fixture concurrent writer.\n')
        with self.assertRaisesRegex(ValueError, 'stable audit handoff'):
            self.read()
        self.assertEqual(lock.read_text(), 'Fixture concurrent writer.\n')


if __name__ == '__main__':
    unittest.main()
