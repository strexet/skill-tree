"""Exercise the fixture-only GDD pin with real Core and Director receipts."""

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]
FIXTURE = SOURCE / 'tests/fixtures/director/gdd-evidence'
spec = importlib.util.spec_from_file_location('director_gdd_evidence', SOURCE / 'common/scripts/director-evidence.py')
EVIDENCE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(EVIDENCE)
WF, WS = EVIDENCE.D.WF, EVIDENCE.D.WS
CRITERION = 'Record the exact fixture rule observed by the consumer.'
CHECK = 'inspect-design-rule'
ADAPTER = 'fixture-gdd-evidence'
PRODUCER_PATH = 'design/accepted-rule.json'


def commit(root, message):
    WS.local_git_text(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                      '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', message)


class GddFixture:
    def __init__(self, root):
        self.root = root
        self.child = root / 'product'
        self.parent = root / 'director'
        self.child.mkdir()
        self.parent.mkdir()
        WS.local_git_text(self.child, 'init', '-b', 'develop')
        WS.local_git_text(self.child, 'remote', 'add', 'origin', str(root / 'unused-remote.git'))
        self.store = WF.Store(self.child, neutral=True)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future\n\n## Pending Task Format\n\nFixed fields.\n\n'
                                     '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = self.child / '.skill-tree/config'
        config.mkdir()
        (config / 'repository.json').write_text('{"schema":1,"role":"source"}\n')
        self.approved = (FIXTURE / 'accepted-rule.json').read_bytes()
        self.source_digest = hashlib.sha256(self.approved).hexdigest()
        inputs = {
            PRODUCER_PATH: self.approved,
            'game/observed-rule.json': self.approved,
            'game/older-rule.json': self.approved.replace(b'r001', b'r000'),
            'website/observed-rule.json': b'{"id":"website-navigation","revision":"r003"}\n',
        }
        for relative, data in inputs.items():
            path = self.child / relative
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
        WS.local_git_text(self.child, 'add', '.')
        commit(self.child, 'Create exact disposable design fixture')
        self.queue_id = WS.setup(self.store, {})['queue_id']
        self.proof = {
            'game': self.consumer('Match accepted rule', 'game/observed-rule.json', self.approved),
            'mismatch': self.consumer('Observe earlier rule', 'game/older-rule.json',
                                      inputs['game/older-rule.json'], supplemental=[PRODUCER_PATH]),
            'ambiguous': self.consumer('Observe earlier rule with supplemental source', 'game/older-rule.json',
                                       inputs['game/older-rule.json'], supplemental=['game/observed-rule.json']),
            'website': self.consumer('Observe unrelated rule', 'website/observed-rule.json', inputs['website/observed-rule.json']),
        }
        install = subprocess.run(['node', str(SOURCE / 'bin/install.js'), '--target', str(self.child), '--flavor', 'general',
                                  '--only', 'codex', '--skills', 'skill-tree-work-through-next'],
                                 capture_output=True, text=True, timeout=45)
        if install.returncode:
            raise RuntimeError(install.stdout + install.stderr)
        self.evidence = EVIDENCE.DirectorEvidence(self.parent)
        self.registry = self.evidence.registry
        self.planner = self.evidence.planner
        registration = {'director_id': 'fixture-gdd', 'areas': [
            self.area('maintenance', '.skill-tree', 'source-maintenance', 'core-task'),
            self.area('fixture-design', 'design', 'game-design', ADAPTER),
            self.area('game', 'game', 'game', 'core-task'),
            self.area('website', 'website', 'website', 'core-task'),
        ]}
        preview = self.registry.preview(registration)
        self.registry.apply({**registration, 'expected_preview_sha256': preview['preview_sha256']})
        objective_id = WF.identity('OB')
        intent = {'objective_id': objective_id, 'expected_current_sha256': None, 'intent': {
            'title': 'Check one disposable design revision', 'owner_ref': 'fixture-owner',
            'description': 'Trace the accepted release rule to the exact observed consumer revision.',
            'acceptance': [{'id': CHECK, 'criterion': CRITERION}],
        }}
        review = self.planner.ledger.preview(intent)
        revision = self.planner.ledger.apply({**intent, 'expected_preview_sha256': review['preview_sha256']})['current']
        pin = {'area_id': 'fixture-design', 'adapter': ADAPTER, 'record_id': 'lantern-release', 'revision': 'r001',
               'sha256': self.source_digest, 'path': PRODUCER_PATH, 'strength': 'required', 'role': 'accepted-rule'}
        self.selector = {'objective_id': objective_id, 'plan_id': WF.identity('PL'), 'plan_revision': 1}
        self.request = {**self.selector, 'objective_revision': revision['revision'], 'objective_sha256': revision['sha256'],
                        'assignments': [self.assignment('game', 'game', pin), self.assignment('mismatch', 'game', pin),
                                        self.assignment('ambiguous', 'game', pin),
                                        self.assignment('website', 'website')]}

    def area(self, identity, scope, role, capability):
        return {'id': identity, 'role': role, 'checkout': str(self.child), 'scope': scope,
                'capabilities': [capability], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status'], 'expected_queue_id': self.queue_id}

    def consumer(self, title, source, expected, supplemental=()):
        check = {'id': CHECK, 'recipe_id': 'static-inspection', 'criteria': [CRITERION],
                 'sources': [source, *supplemental],
                 'parameters': {}, 'assertion': CRITERION, 'timing': 'immediate'}
        body = (f'Goal:\n- {CRITERION}\n\nTouch:\n- {source}\n\nValidation:\n```json\n'
                + WF.dump({'checks': [check]}) + f'```\n\nAcceptance:\n- {CRITERION}\n')
        pending = WF.intake(self.store, {'title': title, 'description': CRITERION, 'expected_behavior': CRITERION})['id']
        result = WF.process(self.store, {'selectors': [pending],
            'tasks': [{'title': title, 'body': body, 'parent_pending_ids': [pending]}],
            'dispositions': {pending: {'status': 'promoted', 'reason': 'The fixture supplies one observed revision.'}}})
        task = result['created_ids'][0]
        slug = title.lower().replace(' ', '-')
        worktree = self.root / slug
        run = WF.start(self.store, 'next', selector=task, workspace={'local_base': True,
                       'local_base_authorization': 'Disposable local GDD receipt fixture only.',
                       'base_branch': 'develop', 'branch': f'fixture/{slug}', 'worktree': str(worktree)})
        selected = WF.Store(worktree, run_id=run['id'])
        WF.advance(selected)
        WF.begin_task(selected, {'task_id': task})
        prepared = WF.prepare_check(selected, {'task_id': task, 'check_id': CHECK})
        observed = (worktree / source).read_bytes()
        if observed != expected:
            raise AssertionError('The resolver changed the declared fixture input')
        parsed = json.loads(observed)
        evidence = (Path(source).parent / 'observed-check.json').as_posix()
        (worktree / evidence).write_text(WF.dump({'rule_id': parsed['id'], 'revision': parsed['revision'],
                                                'source_sha256': hashlib.sha256(observed).hexdigest()}))
        WF.record_check(selected, {'task_id': task, 'check_id': CHECK, 'attempt_id': prepared['attempt_id'],
            'classification': 'executed-control', 'result': 'pass', 'actual_lane': 'static',
            'environment_identity': prepared['environment_identity'],
            'cleanup': 'No product process started.',
            'assertions': [{'assertion': CRITERION, 'result': 'pass'}], 'evidence': [evidence]})
        WF.mark_implemented(selected, {'task_id': task})
        outcome = WF.complete(selected, {'task_id': task, 'outcome': CRITERION,
            'acceptance': [{'criterion': CRITERION, 'result': 'pass', 'evidence': [evidence]}],
            'source_fingerprints': WF.fingerprints(selected, [source])})
        WF.finish(selected)
        return {'selection': {'kind': 'child-run', 'task_id': task, 'run_id': run['id'], 'outcome_id': outcome['id']},
                'body_sha256': outcome['task_context']['content_fingerprint'], 'outcome': outcome,
                'evidence_sha256': WF.file_hash(worktree / evidence), 'worktree': worktree,
                'source': source}

    def assignment(self, label, area, pin=None):
        return {'id': label, 'role': area, 'capability': 'core-task', 'workspace': 'recorded-worktree',
                'write_paths': [f'{label}-result.json'], 'resources': [], 'child': {
                    'task_id': self.proof[label]['selection']['task_id'], 'body_sha256': self.proof[label]['body_sha256']},
                'pins': [pin] if pin else [], 'depends_on': [], 'expected_result': CRITERION,
                'check': CHECK, 'authority_ref': 'fixture-owner', 'effects': ['status'],
                'stop_rules': ['Hold if the accepted input changes.']}

    def freeze(self):
        preview = self.planner.preview(self.request)
        result = self.planner.freeze({**self.request, 'expected_preview_sha256': preview['preview_sha256']})
        return {**self.selector, 'plan_sha256': result['plan_sha256']}

    def adoption(self, plan, label):
        return {'plan': plan, 'assignment_id': label, 'candidate': self.proof[label]['selection']}

    def accept(self, request, preview):
        return self.evidence.run('adopt-apply', {'request': request, 'owner_ref': 'fixture-owner',
                                               'expected_preview_sha256': preview['preview_sha256']})

    def read(self, record):
        return self.evidence.run('adopt-read', {'id': record['id']})

    def owner_files(self):
        return {str(path): path.read_bytes() for path in (
            self.store.future, self.store.state, self.child / EVIDENCE.O.OUTCOME_LEDGER,
            self.parent / EVIDENCE.D.REGISTRY,
            self.parent / EVIDENCE.O.objective_path(self.selector['objective_id']),
        )}


def observe(fixture, test):
    outcomes = {}
    for field, value, status in (('revision', 'r002', 'changed'), ('area_id', 'website', 'unsupported')):
        wrong = deepcopy(fixture.request)
        wrong['assignments'][0]['pins'][0][field] = value
        with test.assertRaisesRegex(ValueError, f'required pin is {status}'):
            fixture.planner.preview(wrong)
        outcomes['wrong-' + field] = {'expected': status, 'observed': status}

    plan = fixture.freeze()
    _, registry, _, _ = fixture.planner.ledger._load(plan['objective_id'])
    test.assertEqual(registry['areas']['fixture-design']['queue_id'], fixture.queue_id)
    exact = fixture.adoption(plan, 'game')
    eligible = fixture.evidence.adopt_preview(exact)
    test.assertEqual(eligible['state'], 'eligible')
    test.assertEqual(eligible['details']['current_pins'][0]['sha256'], fixture.source_digest)
    check = eligible['details']['checks'][0]
    test.assertEqual(check['source_fingerprints'], {'game/observed-rule.json': fixture.source_digest})
    test.assertEqual(check['evidence'][0]['sha256'], fixture.proof['game']['evidence_sha256'])
    outcomes['valid-match'] = {'expected': 'eligible', 'observed': eligible['state']}

    mismatched = fixture.evidence.adopt_preview(fixture.adoption(plan, 'mismatch'))
    test.assertEqual(mismatched['state'], 'held')
    test.assertIn({'required_pins': [{'record_id': 'lantern-release', 'status': 'consumer-input-mismatch'}]},
                  mismatched['blockers'])
    outcomes['consumer-input-mismatch'] = {'expected': 'held', 'observed': mismatched['state']}

    ambiguous = fixture.evidence.adopt_preview(fixture.adoption(plan, 'ambiguous'))
    test.assertEqual(ambiguous['state'], 'held')
    test.assertIn({'required_pins': [{'record_id': 'lantern-release', 'status': 'consumer-input-mismatch'}]},
                  ambiguous['blockers'])
    outcomes['ambiguous-same-area-inputs'] = {'expected': 'held', 'observed': ambiguous['state']}

    foreign = {**exact, 'candidate': {**exact['candidate'], 'run_id': fixture.proof['website']['selection']['run_id'],
                                     'outcome_id': fixture.proof['website']['selection']['outcome_id']}}
    foreign_review = fixture.evidence.adopt_preview(foreign)
    test.assertEqual(foreign_review['state'], 'held')
    test.assertTrue(any('Canonical child outcome identity' in item.get('candidate_evidence', '')
                        for item in foreign_review['blockers']))
    outcomes['foreign-consumer-receipt'] = {'expected': 'held', 'observed': foreign_review['state']}

    selected = fixture.accept(exact, eligible)
    sibling_request = fixture.adoption(plan, 'website')
    sibling = fixture.accept(sibling_request, fixture.evidence.adopt_preview(sibling_request))
    before = fixture.owner_files()
    stable = fixture.read(selected)
    sibling_before = fixture.read(sibling)
    test.assertEqual(stable, fixture.read(selected))
    test.assertEqual(selected, fixture.accept(exact, eligible))
    test.assertEqual(sibling_before, fixture.read(sibling))
    outcomes['stable-replay'] = {'expected': 'same-receipt', 'observed': 'same-receipt'}

    original = fixture.child / PRODUCER_PATH
    original.write_bytes(fixture.approved + b'\n')
    changed = fixture.read(selected)
    test.assertEqual(changed['archive'], stable['archive'])
    test.assertEqual(changed['current']['state'], 'held')
    test.assertIn({'required_pins': [{'record_id': 'lantern-release', 'status': 'changed'}]}, changed['current']['blockers'])
    test.assertEqual(fixture.read(sibling), sibling_before)
    original.write_bytes(fixture.approved)
    test.assertEqual(fixture.read(selected), stable)
    test.assertEqual(fixture.owner_files(), before)
    outcomes['stale-producer'] = {'expected': 'held', 'observed': changed['current']['state']}
    outcomes['unaffected-claim'] = {'expected': 'eligible', 'observed': sibling_before['current']['state']}

    consumer_copy = fixture.proof['game']['worktree'] / fixture.proof['game']['source']
    consumer_copy.write_bytes(fixture.approved + b'\n')
    stale_receipt = fixture.read(selected)
    test.assertEqual(stale_receipt['archive'], stable['archive'])
    test.assertEqual(stale_receipt['current']['state'], 'held')
    test.assertTrue(any('Required current check' in row.get('candidate_evidence', '')
                        for row in stale_receipt['current']['blockers']))
    test.assertEqual(fixture.read(sibling), sibling_before)
    consumer_copy.write_bytes(fixture.approved)
    test.assertEqual(fixture.read(selected), stable)
    outcomes['stale-consumer-input'] = {'expected': 'held', 'observed': stale_receipt['current']['state']}

    return {'controls': outcomes, 'producer': {'area': 'fixture-design', 'queue': fixture.queue_id,
             'record': 'lantern-release', 'revision': 'r001', 'sha256': fixture.source_digest},
            'consumer': {'area': 'game', 'source': fixture.proof['game']['source'],
                         'check': CHECK, 'check_key': check['check_key'],
                         'outcome_sha256': eligible['details']['outcome_sha256'],
                         'evidence_sha256': fixture.proof['game']['evidence_sha256']},
            'prior_acceptance_sha256': selected['id'], 'unaffected_acceptance_sha256': sibling['id']}


def report_for(observed):
    inputs = ('common/scripts/director-plan-adapters.py', 'common/scripts/director-evidence.py',
              'domains/director/capabilities.json', 'tests/test-director-gdd-evidence-fixture.py',
              'tests/fixtures/director/gdd-evidence/accepted-rule.json')
    capabilities = json.loads((SOURCE / 'domains/director/capabilities.json').read_bytes())
    return {'schema': 1, 'scope': 'disposable-source-fixture',
            'environment': {'python': platform.python_version(), 'system': platform.system(),
                            'git': subprocess.check_output(['git', '--version'], text=True).strip(),
                            'node': subprocess.check_output(['node', '--version'], text=True).strip()},
            'source_digests': {relative: WF.file_hash(SOURCE / relative) for relative in inputs},
            **observed, 'omissions': ['Live GDD adoption and private source input remain outside the fixture.'],
            'source_feasibility': {
                'artworkshop': {**capabilities['artworkshop'],
                    'minimum_evidence': 'An owned, reviewed stage export with accepted artifact revision and matching consumer check.',
                    'boundary': 'Director currently verifies only the portable fixture artifact.'},
                'logs': {**capabilities['logs'],
                    'minimum_evidence': 'An authorized scoped journal snapshot with stable entry ownership and repeatable read evidence.',
                    'boundary': 'The recorded source hash supplies feasibility context. No private entries were accessed.'},
            }}


class DirectorGddEvidenceTests(unittest.TestCase):
    def test_gdd_plan_adoption_and_unaffected_claim(self):
        with tempfile.TemporaryDirectory(prefix='director-gdd-') as directory:
            observed = observe(GddFixture(Path(directory).resolve()), self)
        report = json.loads((FIXTURE / 'report.json').read_bytes())
        self.assertEqual(report['controls'], observed['controls'])
        self.assertEqual(report['producer']['sha256'], observed['producer']['sha256'])
        self.assertEqual(report['consumer']['evidence_sha256'], observed['consumer']['evidence_sha256'])
        self.assertEqual(report['source_digests'], report_for(observed)['source_digests'])
        self.assertEqual({name: row['status'] for name, row in report['source_feasibility'].items()},
                         {'artworkshop': 'unsupported', 'logs': 'unsupported'})


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--write-report':
        output = Path(sys.argv[2])
        with tempfile.TemporaryDirectory(prefix='director-gdd-') as directory:
            report = report_for(observe(GddFixture(Path(directory).resolve()), unittest.TestCase()))
        output.write_text(WF.dump(report))
    else:
        unittest.main()
