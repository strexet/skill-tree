"""Verify exact product milestone reconstruction and independent delivery state."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('director_milestone_adoption_fixture', HERE / 'test-director-adoption.py')
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)


class DirectorMilestoneTests(unittest.TestCase):
    def setUp(self):
        self.f = FIXTURE.EvidenceFixture(self.addCleanup, ('story', 'art', 'game', 'website'), cross_area=True)
        self.keeper = self.f.evidence
        artist = self.f.adoption(kind='artifact', artifact=self.f.proof['art']['artifact'])
        self.art = self.f.apply('adopt', artist, self.keeper.adopt_preview(artist))
        self.art_link, self.game_link, self.web_link = (self.f.link(area) for area in ('art', 'game', 'website'))
        self.base = {'plan': self.f.plan, 'name': 'cave-lantern-pilot', 'roles': {
            'story': {'kind': 'pin', 'assignment_id': 'story', 'pin': self.f.pin('story')},
            'art': {'kind': 'adoption', 'assignment_id': 'art', 'id': self.art['id']},
            'game': {'kind': 'result', 'assignment_id': 'game', 'link_id': self.game_link},
            'public': {'kind': 'result', 'assignment_id': 'website', 'link_id': self.web_link},
        }}

    def verified_handoff(self):
        handoff = {'plan': self.f.plan, 'edges': [{'edge_id': 'art-to-game', 'producer': 'art', 'consumer': 'game',
            'pin': {key: self.f.pin('art')[key] for key in FIXTURE.E.H.PIN_KEYS},
            'artifact_id': 'lantern-model', 'consumed_path': self.f.proof['game']['artifact']['path'],
            'producer_link': self.art_link, 'consumer_link': self.game_link}]}
        helper = self.keeper.handoffs
        observed = helper.review_preview(handoff)
        self.assertEqual(observed['parent_acceptance'], 'eligible')
        return helper.run('review-apply', {'request': handoff, 'expected_preview_sha256': observed['preview_sha256'],
                                           'owner_ref': 'fixture-owner'})['archive_id']

    def test_reconstructs_exact_pins_and_requires_verified_cross_area_handoff(self):
        held = self.keeper.milestone_preview(self.base)
        self.assertEqual((held['state'], held['handoff']), ('held', 'unreviewed'))
        before = self.f.files(self.f.parent)
        with self.assertRaisesRegex(ValueError, 'blocked|changed'):
            self.f.apply('milestone', self.base, held)
        self.assertEqual(self.f.files(self.f.parent), before)
        request = {**self.base, 'handoff_id': self.verified_handoff()}
        child_before = self.f.files(self.f.child)
        ready = self.keeper.milestone_preview(request)
        self.assertEqual((ready['state'], ready['handoff']), ('eligible', 'eligible'))
        self.assertEqual({role: entry['state'] for role, entry in ready['roles'].items()},
                         {'story': 'verified', 'art': 'verified', 'game': 'verified', 'public': 'verified'})
        self.assertEqual(ready['roles']['story']['pin'], self.f.pin('story'))
        self.assertEqual(ready['roles']['art']['outcome'], self.f.proof['art']['outcome_id'])
        self.assertEqual(ready['roles']['game']['checks'][0]['check_id'], 'verify-carry')
        self.assertEqual(ready['roles']['public']['delivery'], 'local-result')
        self.assertEqual(ready['release'], 'requires-delivery-authority')
        pin_only = {**request, 'roles': {**request['roles'], 'art': {'kind': 'pin', 'assignment_id': 'game',
                                                                    'pin': self.f.pin('art')}}}
        missing_art = self.keeper.milestone_preview(pin_only)
        self.assertEqual((missing_art['state'], missing_art['roles']['art']['state']), ('held', 'unavailable'))
        missing_handoff = self.keeper.milestone_preview({**request, 'handoff_id': '0' * 64})
        self.assertEqual((missing_handoff['state'], missing_handoff['handoff']), ('held', 'unavailable'))
        self.assertEqual(missing_handoff['roles']['art']['state'], 'verified')
        optional = {**request, 'roles': {**request['roles'], 'public': {'kind': 'result', 'assignment_id': 'website',
                                                                        'link_id': '0' * 64}}}
        optional_view = self.keeper.milestone_preview(optional)
        self.assertEqual(optional_view['roles']['public']['state'], 'unavailable')
        self.assertEqual(optional_view['state'], 'eligible')
        archive = self.f.apply('milestone', request, ready)
        self.assertEqual(self.f.apply('milestone', request, ready), archive)
        self.assertEqual(self.f.files(self.f.child), child_before)
        self.assertEqual(self.keeper.run('milestone-read', {'id': archive['id']}), {'archive': archive, 'current': ready})

    def test_historical_milestone_survives_stale_and_unavailable_current_evidence(self):
        request = {**self.base, 'handoff_id': self.verified_handoff()}
        ready = self.keeper.milestone_preview(request)
        archive = self.f.apply('milestone', request, ready)
        story = self.f.child / self.f.pin('story')['path']
        story.write_bytes(b'Prior story pin metadata is no longer present.')
        (self.f.proof['game']['worktree'] / 'game/review.txt').unlink()
        current = self.keeper.run('milestone-read', {'id': archive['id']})
        self.assertEqual(current['archive'], archive)
        self.assertEqual(current['archive']['evidence']['state'], 'eligible')
        self.assertEqual(current['current']['state'], 'held')
        self.assertEqual(current['current']['roles']['story']['state'], 'stale')
        self.assertEqual(current['current']['roles']['game']['state'], 'stale')
        self.assertEqual(current['current']['roles']['game']['checks'][0]['evidence_availability'], 'unavailable')
        self.assertEqual(current['current']['roles']['art']['state'], 'verified')
        self.assertEqual(current['current']['release'], 'requires-delivery-authority')
        invalid = {**request, 'roles': {**request['roles'], 'public': {'kind': 'result', 'assignment_id': 'website',
                                                                       'link_id': '0' * 64}}}
        missing = self.keeper.milestone_preview(invalid)
        self.assertEqual(missing['roles']['public']['state'], 'unavailable')
        with self.assertRaisesRegex(ValueError, 'blocked|changed'):
            self.f.apply('milestone', invalid, missing)
        ledger, _, _, _ = self.f.ledger._load(self.f.objective_id)
        old_intent = ledger['revisions'][-1]['intent']
        revision = {'objective_id': self.f.objective_id, 'expected_current_sha256': ledger['current']['sha256'],
                    'intent': {**old_intent, 'description': 'Select the revised objective.'}}
        reviewed = self.f.ledger.preview(revision)
        self.f.ledger.apply({**revision, 'expected_preview_sha256': reviewed['preview_sha256']})
        superseded = self.keeper.run('milestone-read', {'id': archive['id']})
        self.assertEqual(superseded['archive'], archive)
        self.assertFalse(superseded['current']['objective_current'])
        self.assertGreater(superseded['current']['current_objective_revision'], superseded['current']['objective_revision'])


class MilestoneScopeFixture(FIXTURE.EvidenceFixture):
    def __init__(self, cleanup, *, sibling_check=False):
        self.sibling_check = sibling_check
        super().__init__(cleanup, ('story', 'art', 'game'), cross_area=False)

    def prepare_task(self, name):
        super().prepare_task(name)
        if self.sibling_check and name == 'game':
            store = FIXTURE.WF.Store(self.child, route_queue=False, neutral=True)
            with store.lock():
                text = store.text()
                task = FIXTURE.WF.resolve(FIXTURE.WF.parse(text), [self.proof[name]['task_id']])[0]
                body = task['body'].replace('"game/lantern.bin"', '"story/source.txt"')
                edited = text.replace(task['body'], body, 1)
                updated = FIXTURE.WF.resolve(FIXTURE.WF.parse(edited), [task['id']])[0]
                assert FIXTURE.WF.check_specs(updated)[0]['sources'] == ['story/source.txt']
                store.save(edited, store.load(text))
            self.proof[name]['body_sha256'] = FIXTURE.WF.digest(updated['body'].encode())

    def link_artifact(self, name, artifact):
        row = self.proof[name]
        source = self.ledger.read({'objective_id': self.objective_id})
        return self.ledger.link_outcome({**self.plan, 'expected_ledger_sha256': source['ledger_sha256'],
            'assignment_id': name, 'area_id': name, **{key: row[key] for key in ('run_id', 'task_id', 'outcome_id')},
            'artifacts': [artifact], 'check_ids': ['verify-carry']})['link_id']

    def request(self, art, game):
        return {'plan': self.plan, 'name': 'cave-lantern-scope', 'roles': {
            'story': {'kind': 'pin', 'assignment_id': 'story', 'pin': self.pin('story')},
            'art': {'kind': 'result', 'assignment_id': 'art', 'link_id': art},
            'game': {'kind': 'result', 'assignment_id': 'game', 'link_id': game},
        }}

    def next_game_scope(self):
        ledger, _, _, basis = self.ledger._load(self.objective_id)
        previous = FIXTURE.O._plan_key(self.plan_id, 1)
        record = deepcopy(ledger['plans'][previous])
        record['frozen']['plan_revision'] = 2
        game = next(row for row in record['frozen']['assignments'] if row['id'] == 'game')
        game['write_paths'].append('revised-support.txt')
        record['plan_sha256'] = self.evidence.planner.C.digest(record['frozen'])
        ledger['plans'][FIXTURE.O._plan_key(self.plan_id, 2)] = record
        relative = FIXTURE.O.objective_path(self.objective_id)
        with self.registry.store.lock(local_delivery={'kind': 'fixture-plan'}):
            self.registry.store.expect_unchanged(relative, basis[relative])
            self.registry.store.commit({relative: FIXTURE.WF.dump(ledger)})
        return {**self.plan, 'plan_revision': 2, 'plan_sha256': record['plan_sha256']}


class DirectorMilestoneScopeTests(unittest.TestCase):
    def test_direct_results_reject_sibling_check_and_sibling_artifact(self):
        fixture = MilestoneScopeFixture(self.addCleanup, sibling_check=True)
        foreign_art = fixture.link_artifact('art', fixture.proof['art']['foreign'])
        foreign_check = fixture.link('game')
        request = fixture.request(foreign_art, foreign_check)
        before = fixture.files(fixture.child)
        view = fixture.evidence.milestone_preview(request)
        for role in ('art', 'game'):
            with self.subTest(role=role):
                self.assertEqual(view['roles'][role]['state'], 'unavailable')
        self.assertEqual(view['state'], 'held')
        self.assertEqual(view['roles']['story']['state'], 'verified')
        self.assertEqual(view['handoff'], 'not-required')
        self.assertEqual(fixture.files(fixture.child), before)

    def test_approved_same_objective_amendment_holds_affected_role_without_handoff(self):
        fixture = MilestoneScopeFixture(self.addCleanup)
        request = fixture.request(fixture.link('art'), fixture.link('game'))
        initial = fixture.evidence.milestone_preview(request)
        self.assertEqual((initial['state'], initial['handoff']), ('eligible', 'not-required'))
        archived = fixture.apply('milestone', request, initial)
        change = {'previous': fixture.plan, 'next': fixture.next_game_scope()}
        helper = fixture.evidence.handoffs
        reviewed = helper.impact_preview(change)
        self.assertEqual(set(reviewed['affected']), {'game'})
        self.assertEqual(fixture.evidence.milestone_preview(request)['state'], 'eligible')
        child_before = fixture.files(fixture.child)
        amendment = helper.run('amend-apply', {'request': change, 'expected_preview_sha256': reviewed['preview_sha256'],
                                               'owner_ref': 'fixture-owner'})
        observed = fixture.evidence.run('milestone-read', {'id': archived['id']})
        self.assertEqual(observed['archive'], archived)
        self.assertEqual(observed['current']['state'], 'held')
        self.assertTrue(observed['current']['objective_current'])
        self.assertEqual(observed['current']['handoff'], 'not-required')
        self.assertEqual(observed['current']['roles']['game']['state'], 'verified')
        self.assertEqual(observed['current']['superseded_roles'], {'game': [amendment['archive_id']]})
        self.assertEqual(observed['current']['roles']['art']['state'], 'verified')
        self.assertEqual(fixture.files(fixture.child), child_before)


if __name__ == '__main__':
    unittest.main()
