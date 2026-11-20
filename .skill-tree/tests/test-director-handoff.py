"""Exercise canonical child receipts and scoped Director handoff amendments."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'common/scripts/director-handoff.py'
SPEC = importlib.util.spec_from_file_location('director_handoff_test', SCRIPT)
H = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(H)
D, O = H.D, H.O
WF, WS = D.WF, D.WS


class HandoffTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.parent = self.base / 'director'
        self.parent.mkdir()
        self.child = self.base / 'child'
        self.child.mkdir()
        WS.local_git_text(self.child, 'init', '-b', 'develop')
        self.core = WF.Store(self.child, neutral=True)
        self.core.future.parent.mkdir(parents=True)
        self.core.future.write_text('# Future\n\n## Pending Task Format\n\nFixed fields.\n\n'
                                    '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = self.child / '.skill-tree/config'
        config.mkdir()
        (config / 'repository.json').write_text('{"role":"source"}\n')
        for scope in ('art', 'game', 'website', 'trailer'):
            location = self.child / scope
            location.mkdir()
            (location / 'source.txt').write_text(f'{scope} scope.\n')
        WS.local_git_text(self.child, 'add', '.')
        WS.local_git_text(self.child, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                          '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture')
        self.queue_id = WS.setup(self.core, {})['queue_id']
        self.registry = D.DirectorRegistry(self.parent)
        request = {'director_id': 'handoff-fixture', 'areas': [
            self.area('maintenance', '.skill-tree', 'source-maintenance'),
            *(self.area(scope, scope, scope) for scope in ('art', 'game', 'website', 'trailer')),
        ]}
        self.registry.apply({**request, 'expected_preview_sha256': self.registry.preview(request)['preview_sha256']})
        self.plans = D._plan_helper(self.registry)
        self.ledger = self.plans.ledger
        self.handoffs = H.DirectorHandoffs(self.registry, self.plans)
        self.objective_id = WF.identity('OB')
        self.plan_id = WF.identity('PL')
        intent = {'owner_ref': 'fixture-owner', 'title': 'Carry the accepted lantern',
                  'description': 'Match the native handoff bytes in the game and web checks.',
                  'acceptance': [{'id': 'carry', 'criterion': 'Check the exact accepted artifact.'}]}
        request = {'objective_id': self.objective_id, 'expected_current_sha256': None, 'intent': intent}
        reviewed = self.ledger.preview(request)
        self.objective = self.ledger.apply({**request, 'expected_preview_sha256': reviewed['preview_sha256']})['current']
        self.proof = {}
        self.payload = b'Accepted lantern model'
        self.pin_sha = WF.digest(self.payload)
        self.add_child('art', self.payload)
        self.add_child('game', self.payload)
        self.add_child('website', self.payload)
        self.add_child('trailer', self.payload)

    def area(self, area_id, scope, role):
        return {'id': area_id, 'role': role, 'checkout': str(self.child), 'scope': scope,
                'capabilities': ['review-source'], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status', 'intake']}

    def add_child(self, name, payload, *, check_verdict='pass'):
        run_id, task_id, outcome_id = (WF.identity(kind) for kind in ('WR', 'T', 'O'))
        worktree = self.base / (name + '-worktree')
        branch = f'codex/{name}-handoff'
        WS.local_git_text(self.child, 'worktree', 'add', '-b', branch, str(worktree))
        locator = WS.runtime(self.child)
        locator['worktrees'][run_id] = str(worktree)
        WS.atomic(WS.runtime_file(self.child), locator)
        artifact = worktree / name / 'lantern.bin'
        artifact.write_bytes(payload)
        log = worktree / name / 'check.log'
        log.write_text('Observed exact carried-lantern input.\n')

        def evidence(path):
            return {'path': path.relative_to(worktree).as_posix(), 'sha256': WF.file_hash(path)}

        source_path = f'{name}/source.txt'
        source_sha = WF.file_hash(worktree / source_path)
        check_result = {'result': check_verdict, 'key': 'b' * 64, 'actual_lane': 'integration',
                        'sources': {evidence(artifact)['path']: evidence(artifact)['sha256']}, 'evidence': [evidence(log)]}
        outcome = {'id': outcome_id, 'task_id': task_id, 'run_id': run_id,
                   'title': 'Local child result', 'outcome': 'Exact fixture evidence.', 'disposition': 'completed',
                   'source_fingerprints': {source_path: source_sha},
                   'acceptance': [{'criterion': 'Approved lantern.', 'result': 'pass', 'evidence': [evidence(artifact)]}],
                   'check_results': [{'check': {'id': check}, 'result': check_result}
                                     for check in ('verify-carry', 'verify-preview')]}
        path = self.child / O.OUTCOME_LEDGER
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as stream:
            stream.write(json.dumps(outcome) + '\n')
        run = {'id': run_id, 'mode': 'next', 'snapshot': [task_id], 'root_task_id': task_id,
               'current_task_id': None, 'phase': 'completed', 'required_ids': [task_id],
               'deferred_ids': [], 'pending_ids': [], 'processing_results': [], 'completed_ids': [task_id],
               'limits': {}, 'next_action': None, 'stop_reason': None, 'admission': {},
               'admitted_task_ids': [task_id], 'admitted_groups': {}, 'completion_refs': {task_id: outcome_id},
               'workspace': {'branch': branch, 'repo_id': WS.repo_id(self.child)},
               'delivery': {'implementation': 'completed', 'status': 'local-result'}}
        state = self.core.load()
        state['run_registry']['runs'][run_id] = run
        self.core.state.write_text(WF.dump(state))
        self.proof[name] = {'worktree': worktree, 'artifact': {'artifact_id': 'lantern-model', **evidence(artifact)},
                            'run_id': run_id, 'task_id': task_id, 'outcome_id': outcome_id}

    def pin(self, *, revision='r001', sha=None, strength='required'):
        result = {'area_id': 'art', 'adapter': 'fixture-artworkshop', 'record_id': 'lantern',
                  'revision': revision, 'sha256': sha or self.pin_sha, 'role': 'held-object',
                  'strength': strength, 'status': 'verified'}
        if strength == 'provisional':
            result.update(preliminary_check='verify-preview', replacement_gate='verify-final')
        return result

    def freeze(self, revision, *, game=None, website=None):
        selector = {'objective_id': self.objective_id, 'plan_id': self.plan_id, 'plan_revision': revision}
        ledger, registry, _, basis = self.ledger._load(self.objective_id)

        def assignment(name, dependencies=(), pin=None):
            return {'id': name, 'area': O._area_identity(registry['areas'][name]), 'depends_on': list(dependencies),
                    'pins': [pin] if pin else [], 'child': {'task_id': self.proof[name]['task_id']},
                    'check': 'verify-carry'}

        objective = {**selector, 'objective_revision': self.objective['revision'], 'objective_sha256': self.objective['sha256']}
        assignments = [assignment('art'), assignment('game', ['art'], game or self.pin()),
                       assignment('trailer', ['game']), assignment('website', ['art'], website or self.pin())]
        plan = {**selector, 'objective': objective, 'assignments': assignments}
        sha = self.plans.C.digest(plan)
        ledger['plans'][O._plan_key(self.plan_id, revision)] = {
            'frozen': plan, 'plan_sha256': sha, 'objective_revision': self.objective['revision'],
            'objective_sha256': self.objective['sha256'], 'assignments': {
                item['id']: {'area': item['area'], 'task_ids': [item['child']['task_id']]} for item in assignments}}
        relative = O.objective_path(self.objective_id)
        with self.registry.store.lock(local_delivery={'kind': 'fixture-setup'}):
            self.registry.store.expect_unchanged(relative, basis[relative])
            self.registry.store.commit({relative: WF.dump(ledger)})
        return {**selector, 'plan_sha256': sha}

    def link(self, plan, name, checks=('verify-carry', 'verify-preview')):
        proof = self.proof[name]
        ledger_sha = self.ledger.read({'objective_id': self.objective_id})['ledger_sha256']
        result = self.ledger.link_outcome({**plan, 'expected_ledger_sha256': ledger_sha,
                                           'assignment_id': name, 'area_id': name,
                                           **{key: proof[key] for key in ('run_id', 'task_id', 'outcome_id')},
                                           'artifacts': [proof['artifact']] if name == 'art' else [],
                                           'check_ids': list(checks)})
        return result['link_id']

    def edge(self, plan, consumer, *, checks=('verify-carry', 'verify-preview')):
        return {'edge_id': f'art-to-{consumer}', 'producer': 'art', 'consumer': consumer,
                'pin': {field: self.pin()[field] for field in H.PIN_KEYS}, 'artifact_id': 'lantern-model',
                'consumed_path': f'{consumer}/lantern.bin', 'producer_link': self.link(plan, 'art'),
                'consumer_link': self.link(plan, consumer, checks)}

    def snapshot(self, root):
        return {item.relative_to(root).as_posix(): item.read_bytes() for item in root.rglob('*') if item.is_file()}

    def apply(self, command, request, preview):
        return self.handoffs.run(command, {'request': request, 'expected_preview_sha256': preview['preview_sha256'],
                                           'owner_ref': 'fixture-owner'})

    def test_exact_receipts_separate_delivery_and_archive_stale_live_status(self):
        plan = self.freeze(1)
        request = {'plan': plan, 'edges': [self.edge(plan, 'website'), self.edge(plan, 'game')]}
        child_before = self.snapshot(self.child)
        preview = self.handoffs.review_preview(request)
        self.assertEqual(preview['parent_acceptance'], 'eligible')
        game = preview['edges'][0]
        self.assertEqual((game['producer_state'], game['consumer_state'], game['integration']),
                         ('accepted', 'verified', 'verified'))
        self.assertEqual(game['delivery'], {'producer': 'local-result', 'consumer': 'local-result'})
        self.assertEqual(game['outcomes']['consumer']['run_id'], self.proof['game']['run_id'])
        self.assertEqual(game['pin']['role'], 'held-object')
        archive = self.apply('review-apply', request, preview)
        self.assertEqual(self.apply('review-apply', request, preview), archive)
        self.assertEqual(self.snapshot(self.child), child_before)
        (self.proof['game']['worktree'] / 'game/lantern.bin').write_bytes(b'Wrong imported bytes')
        stale = self.handoffs.review_preview(request)
        self.assertEqual(stale['parent_acceptance'], 'held')
        self.assertEqual(stale['edges'][0]['consumer_state'], 'unavailable-or-stale')
        self.assertEqual(stale['edges'][1]['integration'], 'verified')
        archive_request = self.base / 'archive-request.json'
        archive_request.write_text(json.dumps({'archive_id': archive['archive_id']}))
        reading = subprocess.run([sys.executable, '-B', str(SCRIPT), 'review-read', str(self.parent),
                                  '--input', str(archive_request)], check=True, capture_output=True, text=True, timeout=30)
        self.assertEqual(json.loads(reading.stdout), archive)
        self.assertNotIn(str(self.base), json.dumps(archive))

    def test_wrong_pinned_digest_and_missing_check_hold_before_archive_write(self):
        plan = self.freeze(1)
        edge = self.edge(plan, 'game', checks=('verify-preview',))
        request = {'plan': plan, 'edges': [edge]}
        preview = self.handoffs.review_preview(request)
        self.assertEqual(preview['parent_acceptance'], 'held')
        self.assertEqual(preview['edges'][0]['consumer_state'], 'missing-check')
        self.assertEqual(preview['missing_coverage'][0]['consumer'], 'website')
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(D.DirectorError, 'changed since preview'):
            self.apply('review-apply', {**request, 'edges': [{**edge, 'consumer_link': None}]}, preview)
        self.assertEqual(self.snapshot(self.parent), before)
        plan2 = self.freeze(2, game=self.pin(revision='r002', sha='f' * 64))
        bad = {'plan': plan2, 'edges': [self.edge(plan2, 'game')]}
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(D.DirectorError, 'pinned revision digest'):
            self.apply('review-apply', bad, preview)
        self.assertEqual(self.snapshot(self.parent), before)
        website_input = self.proof['website']['worktree'] / 'website/lantern.bin'
        website_input.write_bytes(b'Different exact file verified by the consumer')
        outcome_path = self.child / O.OUTCOME_LEDGER
        outcomes = [json.loads(line) for line in outcome_path.read_text().splitlines()]
        website = next(item for item in outcomes if item['id'] == self.proof['website']['outcome_id'])
        for check in website['check_results']:
            check['result']['sources']['website/lantern.bin'] = WF.file_hash(website_input)
        outcome_path.write_text(''.join(json.dumps(item) + '\n' for item in outcomes))
        wrong_consumer = {'plan': plan, 'edges': [self.edge(plan, 'website')]}
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(D.DirectorError, 'consumer check did not fingerprint'):
            self.apply('review-apply', wrong_consumer, preview)
        self.assertEqual(self.snapshot(self.parent), before)

    def test_provisional_proof_never_authorizes_final_and_optional_can_remain_unverified(self):
        plan = self.freeze(1, game=self.pin(strength='provisional'), website=self.pin(strength='optional'))
        game = self.edge(plan, 'game', checks=('verify-preview',))
        website = self.edge(plan, 'website')
        website.pop('consumer_link')
        review = self.handoffs.review_preview({'plan': plan, 'edges': [game, website]})
        self.assertEqual(review['parent_acceptance'], 'held')
        self.assertEqual(review['edges'][0]['integration'], 'preliminary')
        self.assertEqual(review['edges'][0]['required_check'], 'verify-preview')
        self.assertEqual(review['edges'][0]['pin']['replacement_gate'], 'verify-final')
        self.assertEqual(review['edges'][1]['integration'], 'optional-unverified')
        following = self.freeze(2)
        amendment = self.handoffs.impact_preview({'previous': plan, 'next': following})
        self.assertEqual(amendment['blockers'][0]['reason'], 'provisional-replacement-gate-unmet')

    def test_amendment_stops_affected_writer_and_supersedes_only_matching_old_review(self):
        previous = self.freeze(1)
        old_request = {'plan': previous, 'edges': [self.edge(previous, 'game'), self.edge(previous, 'website')]}
        review = self.apply('review-apply', old_request, self.handoffs.review_preview(old_request))
        following = self.freeze(2, game=self.pin(revision='r002', sha='c' * 64))
        amendment = {'previous': previous, 'next': following}
        run_id = WF.identity('DR')
        run_path = self.parent / H.RUNS / (run_id.lower() + '.json')
        run_path.parent.mkdir(parents=True)
        record = {'director_run_id': run_id, 'plan_sha256': previous['plan_sha256'], 'phase': 'running',
                  'assignments': {'game': {'dispatches': {}}}}
        run_path.write_text(WF.dump(record))
        child_state = self.core.load()
        child_run = child_state['run_registry']['runs'][self.proof['game']['run_id']]
        child_run['delivery']['status'] = 'implementation-in-progress'
        self.core.state.write_text(WF.dump(child_state))
        unrelated = self.proof['website']['worktree'] / 'website/unrelated-local.txt'
        unrelated.write_text('Independent dirty work remains local.\n')
        blocked = self.handoffs.impact_preview(amendment)
        self.assertEqual(blocked['direct_changes'], ['game'])
        self.assertEqual(blocked['affected'], {'game': [['game']], 'trailer': [['game', 'trailer']]})
        self.assertEqual(blocked['unaffected'], ['art', 'website'])
        self.assertEqual(blocked['pin_changes'][0]['next']['revision'], 'r002')
        self.assertEqual({item['reason'] for item in blocked['blockers']},
                         {'director-writer-requires-pause', 'child-writer-requires-handoff'})
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(D.DirectorError, 'stopped handoff'):
            self.apply('amend-apply', amendment, blocked)
        self.assertEqual(self.snapshot(self.parent), before)
        run_path.write_text(WF.dump({**record, 'phase': 'paused'}))
        child_run['stop_reason'] = 'Owner paused this affected fixture writer.'
        self.core.state.write_text(WF.dump(child_state))
        for phase in ('prepared', 'invoking'):
            pending = {**record, 'phase': 'paused', 'assignments': {'game': {'dispatches': {
                'intake': {'status': phase},
            }}}}
            run_path.write_text(WF.dump(pending))
            not_ready = self.handoffs.impact_preview(amendment)
            self.assertEqual([item['reason'] for item in not_ready['blockers']], ['dispatch-awaits-reconciliation'])
            with self.assertRaisesRegex(D.DirectorError, 'stopped handoff'):
                self.apply('amend-apply', amendment, not_ready)
        run_path.write_text(WF.dump({**record, 'phase': 'paused'}))
        ready = self.handoffs.impact_preview(amendment)
        self.assertEqual(ready['writer_observations'][0]['run_id'], self.proof['game']['run_id'])
        self.assertTrue(ready['writer_observations'][0]['stopped'])
        child_before = self.snapshot(self.child)
        archive = self.apply('amend-apply', amendment, ready)
        self.assertEqual(self.apply('amend-apply', amendment, ready), archive)
        self.assertEqual(self.snapshot(self.child), child_before)
        self.assertEqual(unrelated.read_text(), 'Independent dirty work remains local.\n')
        current = self.handoffs.review_preview(old_request)
        self.assertEqual(current['parent_acceptance'], 'held')
        self.assertEqual((current['edges'][0]['integration'], current['edges'][1]['integration']),
                         ('superseded', 'verified'))
        self.assertEqual(current['edges'][0]['superseded_by'], [archive['archive_id']])
        self.assertEqual(self.handoffs.run('review-read', {'archive_id': review['archive_id']}), review)
        next_website = old_request['edges'][1]
        next_review = self.handoffs.review_preview({'plan': following, 'edges': [next_website]})
        self.assertEqual(next_review['edges'][0]['integration'], 'verified')
        self.assertEqual(next_review['edges'][0]['outcomes']['consumer']['plan_revision'], 1)
        self.assertEqual(next_review['parent_acceptance'], 'held')
        self.assertEqual(next_review['missing_coverage'][0]['consumer'], 'game')
        with self.assertRaisesRegex(D.DirectorError, 'outcome link is outside'):
            self.handoffs.review_preview({'plan': following, 'edges': old_request['edges']})


if __name__ == '__main__':
    unittest.main()
