"""Exercise a second installed source failure from audit through a reviewed correction."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

fixture = Path(__file__).with_name('test-director-source-repair.py')
spec = importlib.util.spec_from_file_location('fixture', fixture)
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class WrongCount(f.SourceRepairControls):
    check_id = 'snapshot-count-matches-selection'
    assertion = 'The snapshot reports one selected document.'
    defect = b'print("included: 0")'
    repaired = b'print(f"included: {len(report)}")'

    def repository(self, root, *, source):
        super().repository(root, source=source)
        name = '.skill-tree/config/repository.json' if source else '.skill-tree/validation-recipes.json'
        path = root / name
        config = json.loads(path.read_text())
        config['recipes'][f.REPAIR.RECIPE]['input_paths'] = ['expected-count.txt']
        self.file(root, 'expected-count.txt', 'one document')
        path.write_text(json.dumps(config))
        self.git(root, 'add', name, 'expected-count.txt')
        self.git(root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid',
                 'commit', '-m', 'Record the fixture version for this check')

    def prepare_source(self):
        # A local transport stands in for GitHub; queue, registry, evidence,
        # branch resolution, candidate archive and Git integration run normally.
        upstream = self.source
        maintenance = f.load('director-maintenance')
        maintenance.UPSTREAM = upstream.as_uri()
        real_load = f.REPAIR._load_module
        def load(name):
            return maintenance if name == 'director-maintenance' else real_load(name)
        substitute = patch.object(f.REPAIR, '_load_module', side_effect=load)
        substitute.start()
        self.addCleanup(substitute.stop)
        self.project_source = maintenance.prepare(self.parent, 'project')
        self.sibling_source = maintenance.prepare(self.parent, 'sibling')
        self.source = Path(self.project_source['checkout'])
        self.source_store = f.WF.Store(self.source, neutral=True)
        self.source_queue = self.project_source['queue_id']
        self.git(self.source, 'config', 'user.name', 'Fixture')
        self.git(self.source, 'config', 'user.email', 'fixture@example.invalid')

    def observe(self, worktree, subject, attempt, relative):
        result = subprocess.run(attempt['recipe']['argv'], cwd=worktree, capture_output=True, text=True, check=True)
        count, = [row for row in result.stdout.splitlines() if row.startswith('included: ')]
        value = {'included: 0': 'zero-documents', 'included: 1': 'one-document'}[count]
        row = {'schema': 1, 'kind': 'director-resource-check', 'assertion_id': self.check_id,
               'installed_path': subject, 'expected': 'one-document', 'observed': value}
        self.file(worktree, relative, f.WF.dump(row))
        return value

    def original_result(self, worktree, attempt):
        relative = f'.skill-tree/artifacts/director/{self.check_id}.json'
        self.assertEqual(self.observe(worktree, f.AUDIT.INSTALLED, attempt, relative), 'zero-documents')
        return relative

    def test_diagnose_exact_direct_project_check(self):
        task = self.task(self.product_store, 'Inspect direct installed report', [f.AUDIT.INSTALLED, 'README.md'])
        work = self.workspace('direct-project-report')
        launched = f.WF.start(self.product_store, 'next', task['id'], workspace=work)
        store = f.WF.Store(self.product, run_id=launched['id'])
        tree = Path(work['worktree'])
        admitted = f.WF.prepare_worktree_profile(store)
        self.assertEqual((admitted['status'],admitted['run_id']), ('admitted',launched['id']))
        f.WF.begin_task(store, {'task_id':task['id']})
        attempt = f.WF.prepare_check(store, {'task_id':task['id'], 'check_id':self.check_id})
        relative = self.original_result(tree, attempt)
        failed = self.record(store, task['id'], 'fail', relative, attempt)
        selector = {'area_id':'project', 'run_id':launched['id'], 'attempt_id':failed['attempt_id']}
        before = (self.product_store.state.read_bytes(), self.source_store.state.read_bytes(),
                  self.product_store.future.read_bytes(), self.source_store.future.read_bytes())
        with patch.object(f.AUDIT.D.WF, 'owned_module', wraps=f.AUDIT.D.WF.owned_module) as modules:
            def load(name, path):
                return f.REPAIR if name == 'director_project_diagnosis_repair' else modules._mock_wraps(name, path)
            modules.side_effect = load
            report = self.audit.diagnose(selector)
            self.assertEqual(report['selection'], {**selector, 'queue_id':self.product_queue})
            self.assertEqual(report['observations'][0]['classification'], 'source-defect')
            self.assertEqual(report['repair_proposal']['source_path'], f.REPAIR.SOURCE)
            self.assertEqual(report['repair_proposal']['status'], 'proposal')
            self.assertEqual(report['repair_proposal']['maintenance']['branch'], self.project_source['branch'])
            self.assertEqual(report['coverage']['arbitrary_logs'], 'unsupported')
            self.assertEqual((self.product_store.state.read_bytes(), self.source_store.state.read_bytes(),
                              self.product_store.future.read_bytes(), self.source_store.future.read_bytes()), before)
            artifact = tree / relative
            artifact.write_bytes(artifact.read_bytes().replace(b'zero-documents', b'two-documents'))
            stale = self.audit.diagnose(selector)
            self.assertEqual(stale['observations'][0]['classification'], 'unclassified-failure')
            self.assertIsNone(stale['repair_proposal'])
            artifact.write_text(json.dumps({'kind':'product-check-result'}))
            replaced = self.audit.diagnose(selector)
            self.assertEqual(replaced['observations'][0]['classification'], 'unclassified-failure')
            artifact.unlink()
            missing = self.audit.diagnose(selector)
            self.assertEqual(missing['observations'][0]['classification'], 'unclassified-failure')

            ordinary_attempt = f.WF.prepare_check(store, {'task_id':task['id'], 'check_id':self.check_id})
            artifact = tree / self.original_result(tree, ordinary_attempt)
            artifact.write_text(json.dumps({'kind':'product-check-result'}))
            product_check = self.record(store, task['id'], 'fail', relative, ordinary_attempt)
            ordinary = self.audit.diagnose({**selector, 'attempt_id':product_check['attempt_id']})
            self.assertEqual(ordinary['observations'][0]['classification'], 'product')
            self.assertIsNone(ordinary['repair_proposal'])
            no_check = self.audit.diagnose({**selector, 'attempt_id':f.WF.identity('C')})
            self.assertEqual(no_check['coverage_gaps'][-1]['reason'], 'check-result-unavailable')

    def test_wrong_count_from_installed_run_routes_rechecks_and_freezes(self):
        request = self.observed_finding()
        director_run = request['audit']['director_run_id']
        selector = request['audit']['selections'][0]
        view = {'project_work':{'area_id':'project', 'run_id':selector['run_id']}}
        row = self.registry.status(view)['project_work'][0]['runs'][0]
        self.assertEqual(row['audit_coverage'], 'director-assignment')
        self.assertEqual(row['audit'], {**selector, 'director_run_id':director_run})
        parent = self.parent / f'.skill-tree/director/runs/{director_run.lower()}.json'
        original = parent.read_bytes()
        parent.write_text(json.dumps({**json.loads(original), 'phase':'rejected-fixture-state'}))
        self.assertEqual(self.registry.status(view)['project_work'][0]['runs'][0]['audit_coverage'],
                         'director-start-unverified')
        parent.write_bytes(original)
        preview = self.repair.preview(request)
        binding = preview['plan']['maintenance']
        self.assertEqual(binding['project_id'], 'project')
        self.assertEqual(binding['branch'], self.project_source['branch'])
        self.assertEqual(binding['product_queue_id'], self.product_queue)
        self.assertEqual(binding['source_queue_id'], self.source_queue)
        source = preview['plan']['finding']['scope']['source_path']
        self.assertEqual(source, f.REPAIR.SOURCE)
        self.assertEqual(preview['plan']['finding']['symptom'], 'zero-documents')
        with self.assertRaisesRegex(ValueError, 'exact source-ready finding'):
            self.repair.preview({**request, 'finding_sha256': '0' * 64})
        evidence = self.target / f'.skill-tree/artifacts/director/{self.check_id}.json'
        original = evidence.read_bytes()
        evidence.write_bytes(original.replace(b'zero-documents', b'two-documents'))
        self.assertEqual(self.audit.read(request['audit'])['findings'], [])
        evidence.write_bytes(original)
        fixture_input = self.target / 'expected-count.txt'
        fixture_input.write_text('revised input')
        self.assertEqual(self.audit.read(request['audit'])['findings'], [])
        fixture_input.write_text('one document')
        recipe_file = self.source / '.skill-tree/config/repository.json'
        original_config = recipe_file.read_bytes()
        changed = json.loads(original_config)
        changed['recipes'][f.REPAIR.RECIPE]['argv'].append('--help')
        recipe_file.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'reproduction recipe differs'):
            self.repair.preview(request)
        recipe_file.write_bytes(original_config)
        repair_id = preview['repair_id']
        approval = {'request': request, 'repair_id': repair_id, 'owner': f.OWNER, 'authorized_effects': sorted(f.REPAIR.EFFECTS),
                    'expected_preview_sha256': preview['preview_sha256']}
        pending = self.repair.intake(approval)['result']['id']
        action = {'repair_id': repair_id, 'owner': f.OWNER}
        task, = self.repair.process({**action, 'pending_id': pending,
            'expected_source_hash': f.WF.file_hash(self.source_store.future)})['result']['created_ids']
        work = {**self.workspace('fix-count'), 'base_branch': binding['branch']}
        run = self.repair.start({**action, 'task_id': task, 'workspace': work,
            'expected_source_hash': f.WF.file_hash(self.source_store.future)})['result']
        store = f.WF.Store(self.source, run_id=run['id'])
        f.WF.begin_task(store, {'task_id': task})
        tree = Path(work['worktree'])
        subject = tree / source
        for verdict, expected in [('red', 'zero-documents'), ('pass', 'one-document')]:
            if verdict == 'pass':
                subject.write_bytes(subject.read_bytes().replace(self.defect, self.repaired))
            attempt = f.WF.prepare_check(store, {'task_id': task, 'check_id': self.check_id})
            relative = f'.skill-tree/artifacts/director/source-{verdict}.json'
            self.assertEqual(self.observe(tree, source, attempt, relative), expected)
            self.record(store, task, verdict, relative, attempt)
        f.WF.mark_implemented(store, {'task_id': task, 'changed_files': [source]})
        assertion = preview['plan']['scenario']['assertion']
        outcome = f.WF.complete(store, {'task_id': task, 'outcome': assertion,
            'acceptance': [{'criterion': assertion, 'result': 'pass', 'evidence': [relative]}],
            'source_fingerprints': f.WF.fingerprints(store, [source, 'README.md'])})
        f.WF.finish(store)
        candidate_request = {**action, 'pending_id': pending, 'task_id': task, 'run_id': run['id'],
            'outcome_id': outcome['id'], 'composition_target': str(self.target), 'provider': 'codex',
            'flavor': 'director', 'review_ref': 'count-reviewed'}
        candidate = self.repair.candidate_preview(candidate_request)
        self.assertEqual(candidate['review']['after_sha256'], f.WF.file_hash(subject))
        self.assertEqual(self.repair.candidate_apply({'request': candidate_request,
                         'expected_candidate_sha256': candidate['candidate_sha256']}), candidate)

        selected_tree = Path(self.project_source['project_checkout'])
        sibling = Path(self.sibling_source['project_checkout'])
        before = self.git(selected_tree, 'rev-parse', 'HEAD')
        sibling_before = self.git(sibling, 'rev-parse', 'HEAD')
        product_before = self.git(self.product, 'status', '--porcelain'), self.git(self.product, 'rev-parse', 'HEAD')
        handoff = {**action, 'candidate_sha256': candidate['candidate_sha256']}
        with self.assertRaisesRegex(ValueError, 'Authorize integration'):
            self.repair.run('repair-integrate', {**handoff, 'owner': {**f.OWNER, 'actor': 'another-owner'}})
        self.assertEqual(self.git(selected_tree, 'rev-parse', 'HEAD'), before)
        receipt = self.repair.run('repair-integrate', handoff)
        self.assertTrue(receipt['applied'])
        self.assertEqual(receipt['commit'], self.git(selected_tree, 'rev-parse', 'HEAD'))
        self.assertEqual(receipt['base_commit'], before)
        self.assertEqual(self.git(selected_tree, 'diff', '--name-only', before, 'HEAD'), source)
        self.assertEqual((selected_tree / source).read_bytes(), subject.read_bytes())
        self.assertEqual(self.repair.run('repair-integrate', handoff), receipt)
        self.assertEqual(self.git(sibling, 'rev-parse', 'HEAD'), sibling_before)
        self.assertIn(self.defect, (sibling / source).read_bytes())
        self.assertEqual((self.git(self.product, 'status', '--porcelain'), self.git(self.product, 'rev-parse', 'HEAD')), product_before)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([WrongCount('test_diagnose_exact_direct_project_check'),
        WrongCount('test_wrong_count_from_installed_run_routes_rechecks_and_freezes'),
        f.SourceRepairControls('test_audited_installed_failure_routes_one_repair_and_freezes_exact_candidate')])


if __name__ == '__main__':
    unittest.main()
