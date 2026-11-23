"""Exercise a second installed source failure from audit through a reviewed correction."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

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

    def test_wrong_count_from_installed_run_routes_rechecks_and_freezes(self):
        request = self.observed_finding()
        preview = self.repair.preview(request)
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
        work = self.workspace('fix-count')
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


def load_tests(loader, tests, pattern):
    return unittest.TestSuite([WrongCount('test_wrong_count_from_installed_run_routes_rechecks_and_freezes'),
        f.SourceRepairControls('test_audited_installed_failure_routes_one_repair_and_freezes_exact_candidate')])


if __name__ == '__main__':
    unittest.main()
