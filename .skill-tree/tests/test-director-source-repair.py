"""Exercise the actual installed red, original audit and bounded Core repair in temporary Git repos."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
SCRIPTS = SOURCE / 'common/scripts'
QUEUE = '.skill-tree/documents/future.md'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D, AUDIT, REPAIR = (load(name) for name in ('director-state', 'director-audit', 'director-source-repair'))
REPAIR.D = D
WF, WS = D.WF, D.WS
OWNER = {'actor': 'fixture-owner', 'kind': 'owner-message', 'reference': 'reviewed-source-repair'}


def recipe(relative):
    return {'lane': 'unit', 'argv': ['python3', '-B', relative, '{project_root}', '--dry-run', '--include',
                                    'README.md', '--timestamp', REPAIR.STAMP], 'input_paths': []}


class SourceRepairControls(unittest.TestCase):
    check_id = REPAIR.CHECK
    assertion = REPAIR.ASSERTION
    defect, repaired = REPAIR.DEFECT, REPAIR.REPAIRED

    def setUp(self):
        retained = os.environ.get('DIRECTOR_SOURCE_REPAIR_FIXTURE')
        if retained:
            self.base = Path(retained)
            self.assertTrue(self.base.is_absolute() and self.base.parent.resolve(strict=True) == self.base.parent
                            and not self.base.is_relative_to(SOURCE.parent), 'Select one fresh external disposable fixture root.')
            self.base.mkdir()
        else:
            temporary = tempfile.TemporaryDirectory(prefix='director-source-repair-')
            self.addCleanup(temporary.cleanup)
            self.base = Path(temporary.name).resolve()
        self.retain = retained is not None
        self.parent = self.base / 'director'
        self.parent.mkdir()
        self.source = self.base / 'source'
        self.product = self.base / 'product'
        self.repository(self.source, source=True)
        self.repository(self.product, source=False)
        self.install_old(self.product)
        self.prepare_source()
        self.product_store = WF.Store(self.product, neutral=True)
        self.product_queue = WS.setup(self.product_store, {})['queue_id']
        self.registry = D.DirectorRegistry(self.parent)
        declaration = {'director_id': 'repair-fixture', 'areas': [
            self.area(self.source, 'maintenance', 'source-maintenance', '.skill-tree', ['intake', 'process', 'launch']),
            self.area(self.product, 'project', 'game', '.', ['launch', 'audit']),
        ]}
        self.registry.apply({**declaration, 'expected_preview_sha256': self.registry.preview(declaration)['preview_sha256']})
        self.audit = AUDIT.DirectorAudit(self.registry)
        self.repair = REPAIR.DirectorSourceRepair(self.registry, self.audit)

    def prepare_source(self):
        self.source_store = WF.Store(self.source, neutral=True)
        self.source_queue = WS.setup(self.source_store, {})['queue_id']

    def file(self, root, relative, data):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        return path

    def git(self, root, *args):
        return WS.local_git_text(root, '-c', 'commit.gpgsign=false', '-c', f'core.hooksPath={os.devnull}', *args)

    def repository(self, root, *, source):
        root.mkdir()
        self.git(root, 'init', '-b', 'develop')
        if source:
            for name in ('common', 'domains', 'config', 'lib', 'src', 'templates', 'tests/fixtures'):
                shutil.copytree(SOURCE / name, root / '.skill-tree' / name, ignore=shutil.ignore_patterns('__pycache__'))
            self.file(root, '.skill-tree/config/repository.json', WF.dump({'schema': 1, 'role': 'source',
                                                                       'recipes': {REPAIR.RECIPE: recipe(REPAIR.SOURCE)}}))
            helper = root / REPAIR.SOURCE
            current = helper.read_bytes()
            self.assertEqual(current.count(self.repaired), 1)
            helper.write_bytes(current.replace(self.repaired, self.defect))
        else:
            self.file(root, '.skill-tree/validation-recipes.json', WF.dump({'schema': 1, 'recipes': {REPAIR.RECIPE: recipe(AUDIT.INSTALLED)}}))
        self.file(root, 'README.md', REPAIR.INPUT)
        self.file(root, '.gitignore', '/.agents/\n/.skill-tree/installation/\n/.skill-tree/artifacts/\n')
        self.file(root, QUEUE, '# Future Work\n\n## Pending Task Format\n\nFixture.\n\n'
                  '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        self.git(root, 'add', '.')
        self.git(root, '-c', 'user.name=Director Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'Initial source repair fixture')
        self.git(root, 'remote', 'add', 'origin', str(self.base / (root.name + '-unused.git')))

    def install_old(self, target):
        code = '''const [lib,composer,root,source] = process.argv.slice(1);
const names = require(composer).operationNames(source, 'director');
require(lib).install(root, source, 'director', names.map(name=>({name, rel: '.agents/skills/'+name, provider:'codex'})));'''
        result = subprocess.run(['node', '-e', code, str(SOURCE / 'lib/installation.js'), str(SOURCE / 'lib/composer.js'),
                                 str(target), str(self.source / '.skill-tree')], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def area(self, root, area_id, role, scope, effects):
        return {'id': area_id, 'role': role, 'checkout': str(root), 'scope': scope, 'capabilities': ['core-task'],
                'interface': {'kind': 'skill-tree', 'version': 1}, 'allowed_effects': ['status', *effects]}

    def workspace(self, name):
        return {'base_branch': 'develop', 'branch': 'codex/' + name, 'worktree': str(self.base / name),
                'local_base': True, 'local_base_authorization': 'Disposable local fixture.'}

    def task(self, store, title, sources):
        pending = WF.intake(store, {'title': title, 'description': self.assertion, 'expected_behavior': self.assertion})
        check = {**REPAIR._check(), 'sources': sources, 'id': self.check_id, 'criteria': [self.assertion], 'assertion': self.assertion}
        body = (f'Goal:\n- {self.assertion}\n\nTouch:\n- README.md\n\nValidation:\n```json\n'
                f'{json.dumps({"checks": [check]})}\n```\n\nAcceptance:\n- {self.assertion}\n')
        task_id = WF.process(store, {'selectors': [pending['id']], 'dispositions': {pending['id']: {
            'status': 'promoted', 'reason': 'The exact snapshot behavior has a fixed scope.'}},
            'tasks': [{'title': title, 'body': body, 'parent_pending_ids': [pending['id']]}]})['created_ids'][0]
        return next(task for task in WF.parse(store.text()) if task['id'] == task_id)

    def observed_finding(self):
        task = self.task(self.product_store, 'Prove original installed report behavior', [AUDIT.INSTALLED, 'README.md'])
        planner = D._plan_helper(self.registry)
        objective_id, plan_id, director_run = (WF.identity(prefix) for prefix in ('OB', 'PL', 'DR'))
        intent = {'objective_id': objective_id, 'expected_current_sha256': None, 'intent': {'owner_ref': OWNER['actor'],
            'title': 'Confirm installed snapshot check', 'description': 'Read one selected dry-run result.',
            'acceptance': [{'id': 'snapshot', 'criterion': self.assertion}]}}
        accepted = planner.ledger.apply({**intent, 'expected_preview_sha256': planner.ledger.preview(intent)['preview_sha256']})['current']
        plan = {'objective_id': objective_id, 'objective_revision': accepted['revision'], 'objective_sha256': accepted['sha256'],
                'plan_id': plan_id, 'plan_revision': 1, 'assignments': [{
                    'id': 'snapshot-check', 'area_id': 'project', 'role': 'game', 'capability': 'core-task', 'workspace': 'recorded-worktree',
                    'write_paths': ['README.md'], 'resources': [], 'pins': [], 'depends_on': [], 'effects': ['launch'], 'check': self.check_id,
                    'child': {'task_id': task['id'], 'body_sha256': WF.digest(task['body'].encode())},
                    'expected_result': self.assertion, 'authority_ref': OWNER['actor'], 'stop_rules': ['Preserve the original result.'],
                }]}
        frozen = planner.freeze({**plan, 'expected_preview_sha256': planner.preview(plan)['preview_sha256']})
        selector = {key: plan[key] for key in ('objective_id', 'plan_id', 'plan_revision')}
        run = D._run_helper(self.registry, 'run-start', {**selector, 'director_run_id': director_run,
            'plan_sha256': frozen['plan_sha256'], 'assignment_ids': ['snapshot-check'], 'owner': OWNER,
            'authority': {'snapshot-check': ['launch']}, 'approved_defaults': []})
        work = self.workspace('original-report')
        launched = D._run_helper(self.registry, 'run-dispatch', {'director_run_id': director_run, 'expected_run_sha256': run['run_sha256'],
            'assignment_id': 'snapshot-check', 'operation': 'start', 'request': {**work,
                'expected_source_hash': WF.file_hash(self.product_store.future)}})['result']
        store = WF.Store(self.product, run_id=launched['id'])
        WF.checkpoint(store, {'phase': 'refresh-profile', 'stop_reason': 'Prepare the owned fixture installation.'})
        worktree = Path(work['worktree'])
        self.install_old(worktree)
        WF.resume_admission(store)
        WF.checkpoint(store, {'phase': 'implement', 'stop_reason': None})
        WF.begin_task(store, {'task_id': task['id']})
        attempt = WF.prepare_check(store, {'task_id': task['id'], 'check_id': self.check_id})
        relative = self.original_result(worktree, attempt)
        failed = self.record(store, task['id'], 'fail', relative, attempt)
        WS.ensure_workspace(store, launched)
        WF.checkpoint(store, {'phase': 'refresh-profile', 'stop_reason': 'Wait for the exact separately authorized repair canary.',
                              'next_action': 'Re-admit the same run only after the approved candidate installation.'})
        self.canary = {'project_root': str(worktree), 'canonical_root': str(self.product), 'queue_id': self.product_queue,
                       'run_id': launched['id'], 'task_id': task['id'], 'attempt_id': failed['attempt_id'],
                       'profile_sha256': WF.file_hash(worktree / AUDIT.PROFILE), 'scenario': REPAIR.scenario()}
        self.target = worktree
        scope = {'director_run_id': director_run, 'selections': [{'assignment_id': 'snapshot-check', 'run_id': launched['id']}]}
        finding, = self.audit.read(scope)['findings']
        return {'audit': scope, 'finding_sha256': finding['finding_sha256']}

    def record(self, store, task_id, verdict, relative, attempt):
        fields = {'counts': {'expected': 1, 'discovered': 1, 'passed': int(verdict == 'pass'),
                             'failed': int(verdict != 'pass'), 'skipped': 0},
                  'failure_signature': AUDIT.SIGNATURE, 'failure_category': 'expected-behavior'}
        return WF.record_check(store, {'task_id': task_id, 'check_id': self.check_id, 'attempt_id': attempt['attempt_id'],
            'classification': 'executed-control', 'result': verdict, 'actual_lane': 'unit',
            'environment_identity': attempt['environment_identity'], 'cleanup': 'The dry-run wrote no archive.',
            'evidence': [relative], **fields})

    def original_result(self, worktree, attempt):
        original = REPAIR.observe_snapshot(worktree / AUDIT.INSTALLED, worktree, argv=attempt['recipe']['argv'])
        self.assertEqual(original['observed'], 'markdown-extension-omitted')
        self.file(worktree, AUDIT.RESULT, WF.dump({key: original[key] for key in AUDIT.OBSERVED_RESULT}))
        return AUDIT.RESULT

    def test_audited_installed_failure_routes_one_repair_and_freezes_exact_candidate(self):
        request = self.observed_finding()
        unrelated = WF.intake(self.source_store, {'title': 'Unrelated high-priority work', 'description': 'Retain source context.',
                                                 'expected_behavior': 'Keep the independent queue entry.', 'priority': 900})
        before_product = self.product_store.future.read_bytes(), self.product_store.state.read_bytes()
        preview = self.repair.preview(request)
        self.assertNotIn(str(self.base), WF.dump(preview))
        approval = {'request': request, 'repair_id': preview['repair_id'], 'owner': OWNER,
                    'authorized_effects': sorted(REPAIR.EFFECTS), 'expected_preview_sha256': preview['preview_sha256']}
        with self.assertRaisesRegex(ValueError, 'preview or queue changed'):
            self.repair.intake({**approval, 'expected_preview_sha256': '0' * 64})
        intake = self.repair.intake(approval)
        self.assertEqual(self.repair.intake(approval), intake)
        pending = intake['result']['id']
        exact = {'repair_id': approval['repair_id'], 'owner': OWNER, 'pending_id': pending,
                 'expected_source_hash': WF.file_hash(self.source_store.future)}
        with self.assertRaisesRegex(ValueError, 'exact chosen repair Pending'):
            self.repair.process({**exact, 'pending_id': unrelated['id']})
        with self.assertRaisesRegex(ValueError, 'owner authority'):
            self.repair.process({**exact, 'owner': {**OWNER, 'actor': 'unrelated-owner'}})
        processed = self.repair.process(exact)['result']
        task_id, = processed['created_ids']
        self.assertEqual(processed['selected_ids'], [pending])
        self.assertEqual(self.source_store.load()['run_registry']['runs'], {})
        work = self.workspace('source-repair')
        launch = self.repair.start({'repair_id': approval['repair_id'], 'owner': OWNER, 'task_id': task_id, 'workspace': work,
                                    'expected_source_hash': WF.file_hash(self.source_store.future)})['result']
        self.assertEqual(launch['snapshot'], [task_id])
        self.assertIn(unrelated['id'], self.source_store.text())
        store = WF.Store(self.source, run_id=launch['id'])
        WF.begin_task(store, {'task_id': task_id})
        worktree = Path(work['worktree'])
        helper = worktree / REPAIR.SOURCE
        for result, changed in (('red', False), ('pass', True)):
            if changed:
                helper.write_bytes(helper.read_bytes().replace(REPAIR.DEFECT, REPAIR.REPAIRED))
            attempt = WF.prepare_check(store, {'task_id': task_id, 'check_id': REPAIR.CHECK})
            observed = REPAIR.observe_snapshot(helper, worktree, argv=attempt['recipe']['argv'])
            self.assertEqual(observed, REPAIR.observation(WF.file_hash(helper), changed))
            relative = f'.skill-tree/artifacts/director/repair-{result}.json'
            self.file(worktree, relative, WF.dump(observed))
            self.record(store, task_id, result, relative, attempt)
        WF.mark_implemented(store, {'task_id': task_id, 'changed_files': [REPAIR.SOURCE]})
        completed = WF.complete(store, {'task_id': task_id, 'outcome': REPAIR.ASSERTION,
            'acceptance': [{'criterion': REPAIR.ASSERTION, 'result': 'pass', 'evidence': [relative]}],
            'source_fingerprints': WF.fingerprints(store, [REPAIR.SOURCE, 'README.md'])})
        WF.finish(store)
        candidate_request = {'repair_id': approval['repair_id'], 'pending_id': pending, 'task_id': task_id,
            'run_id': launch['id'], 'outcome_id': completed['id'], 'composition_target': str(self.target),
            'flavor': 'director', 'provider': 'codex', 'owner': OWNER, 'review_ref': 'reviewed-fix'}
        candidate = self.repair.candidate_preview(candidate_request)
        self.assertEqual(candidate['review']['after_sha256'], WF.file_hash(helper))
        self.assertEqual(candidate['checks']['original']['scenario_sha256'], candidate['checks']['repaired']['scenario_sha256'])
        self.assertEqual(candidate['packages']['output_digests'][REPAIR.OPERATION]['scripts/create-documentation-snapshot.py'], WF.file_hash(helper))
        freeze = {'request': candidate_request, 'expected_candidate_sha256': candidate['candidate_sha256']}
        evidence = worktree / relative
        bytes_before = evidence.read_bytes()
        evidence.write_bytes(bytes_before + b'\n')
        with self.assertRaisesRegex(ValueError, 'evidence is missing, changed'):
            self.repair.candidate_apply(freeze)
        evidence.write_bytes(bytes_before)
        unrelated_source = worktree / 'README.md'
        unrelated_source.write_bytes(REPAIR.INPUT + b'changed\n')
        with self.assertRaisesRegex(ValueError, 'outside the exact reviewed repair'):
            self.repair.candidate_apply(freeze)
        unrelated_source.write_bytes(REPAIR.INPUT)
        self.assertEqual(self.repair.candidate_apply(freeze), candidate)
        self.assertEqual(self.repair.candidate_apply(freeze), candidate)
        self.assertEqual(self.repair.candidate_read({'candidate_sha256': candidate['candidate_sha256']}), candidate)
        self.assertEqual((self.product_store.future.read_bytes(), self.product_store.state.read_bytes()), before_product)
        profile = json.loads((self.target / AUDIT.PROFILE).read_text())
        self.assertEqual(WF.file_hash(self.target / AUDIT.PROFILE), self.canary['profile_sha256'])
        self.assertEqual({item['name'] for item in profile['destinations'].values()}, set(candidate['packages']['output_digests']))
        self.assertEqual(WF.Store(self.product, run_id=self.canary['run_id']).load()['active_run']['phase'], 'refresh-profile')
        self.assertIn(REPAIR.DEFECT, (self.source / REPAIR.SOURCE).read_bytes())
        relative = REPAIR._archive('candidate', candidate['candidate_sha256'])
        probe = self.file(self.base, 'candidate-read.json', WF.dump({'candidate_sha256': candidate['candidate_sha256']}))
        command = subprocess.run(['python3', '-B', str(SCRIPTS / 'director-source-repair.py'),
                                  'repair-candidate-read', str(self.parent), '--input', str(probe)],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(command.returncode, 0, command.stderr)
        self.assertEqual(json.loads(command.stdout), candidate)
        if self.retain:
            self.file(self.base, 'source-repair-observed.json', WF.dump({
                'schema': 1, 'kind': 'director-source-repair-observed-fixture', 'finding': self.audit.read(request['audit']),
                'candidate': str(self.parent / relative), 'candidate_sha256': candidate['candidate_sha256'],
                'candidate_source': str(worktree / '.skill-tree'), 'composition_target': str(self.target),
                'original_source': str(self.source / '.skill-tree'),
                'canary': self.canary,
            }))


if __name__ == '__main__':
    unittest.main()
