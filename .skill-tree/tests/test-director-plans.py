"""Verify Director plans from real Core, Narrative and portable fixture records."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CORE = Path(__file__).resolve().parents[1]
FOLDER = CORE / 'tests/fixtures/director'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = load('director_state_plan_test', CORE / 'common/scripts/director-state.py')
F = load('director_fixture_plan_test', CORE / 'tests/test-director-fixture.py')


class DirectorPlansTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.manifest = json.loads((FOLDER / 'fixture-manifest.json').read_text())
        store, _ = F.fixture_project(self.base / 'fixture', self.manifest)
        self.child = store.root
        self.parent = self.base / 'director'
        self.parent.mkdir()
        D.WS.setup(store, {})
        maintenance, _ = F.fixture_project(self.base / 'maintenance', self.manifest)
        D.WS.setup(maintenance, {})
        self.maintenance = maintenance.root
        (self.child / '.skill-tree/config/repository.json').unlink()
        core = D.WF.Store(self.child, neutral=True)
        task = D.WF.intake(core, {'title': 'Prepare lantern', 'description': 'Preserve the reviewed carry mode.',
                                 'expected_behavior': 'The lantern keeps the reviewed attachment.'})
        selected = next(item for item in D.WF.parse(core.text()) if item['id'] == task['id'])
        self.selected_task = {'task_id': task['id'], 'body_sha256': D.WF.digest(selected['body'].encode())}
        receipt = subprocess.run(
            ['node', str(CORE / 'bin/install.js'), '--target', str(self.child), '--flavor', 'general', '--only',
             'codex', '--skills', 'skill-tree-work-through-next'],
            capture_output=True, text=True, timeout=45,
        )
        self.assertEqual(receipt.returncode, 0, receipt.stdout + receipt.stderr)

        self.director = D.DirectorRegistry(self.parent)
        request = {'director_id': 'lantern-fixture', 'areas': [
            {**self.area('maintenance', '.skill-tree', 'source-maintenance', ['core-task']),
             'checkout': str(self.maintenance)},
            self.area('story', 'story', 'narrative', ['fixture-canon', 'narrative-canon']),
            self.area('art', 'art', 'art', ['fixture-artifact', 'artworkshop-stage']),
            self.area('game', 'game', 'game', ['fixture-consumer']),
        ]}
        self.director.apply({**request, 'expected_preview_sha256': self.director.preview(request)['preview_sha256']})
        self.plans = D._plan_helper(self.director)

        self.objective = D.WF.identity('OB')
        self.plan = D.WF.identity('PL')
        intent = {'owner_ref': 'lantern-owner', 'title': 'Lantern fixture',
                  'description': 'Carry a lantern in a cave.',
                  'acceptance': [{'id': 'keep-attachment', 'criterion': 'Match the accepted carry mode.'}]}
        self.intent = {'objective_id': self.objective, 'expected_current_sha256': None, 'intent': intent}
        self.first = self.revise(self.intent)['current']
        self.story_pin = self.fixture_pin('story', 'fixture-narrative', self.manifest['story']['id'],
                                          self.manifest['story']['accepted'])
        self.art_pin = self.fixture_pin('art', 'fixture-artworkshop', self.manifest['artifact']['id'],
                                        self.manifest['artifact'])
        self.request = {**self.selector(), 'objective_revision': self.first['revision'],
                        'objective_sha256': self.first['sha256'], 'assignments': [
            self.assignment('verify-lantern', 'game', 'fixture-consumer', captures=[self.art_pin],
                            dependencies=['create-lantern']),
            self.assignment('create-lantern', 'art', 'fixture-artifact', captures=[self.story_pin],
                            child=self.selected_task),
        ]}

    def area(self, identifier, scope, role, capabilities):
        return {'id': identifier, 'scope': scope, 'role': role, 'checkout': str(self.child),
                'capabilities': capabilities, 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status', 'intake', 'process', 'launch']}

    def revise(self, request):
        review = self.plans.ledger.preview(request)
        return self.plans.ledger.apply({**request, 'expected_preview_sha256': review['preview_sha256']})

    def selector(self):
        return {'objective_id': self.objective, 'plan_id': self.plan, 'plan_revision': 1}

    def fixture_pin(self, area, adapter, record, row):
        return {'adapter': adapter, 'area_id': area, 'record_id': record,
                'revision': row['revision'], 'sha256': row['sha256'], 'path': row['path'],
                'role': 'accepted-reference', 'strength': 'required'}

    def assignment(self, identifier, role, capability, *, captures=(), dependencies=(), child=None):
        return {'id': identifier, 'role': role, 'capability': capability, 'workspace': 'artifact',
                'write_paths': ['result.json'], 'resources': ['lantern-work'],
                'child': child or {'title': 'Verify the lantern', 'description': 'Check the carry mode.',
                                   'acceptance': ['Match the accepted carry mode.']},
                'pins': list(captures), 'depends_on': list(dependencies), 'expected_result': 'Exact carry fixture.',
                'check': 'carry-mode', 'authority_ref': 'lantern-owner',
                'effects': ['status'] if child else ['intake'], 'stop_rules': ['Stop when a required pin changes.']}

    def files(self, root):
        return {item.relative_to(root).as_posix(): item.read_bytes()
                for item in root.rglob('*') if item.is_file()}

    def cli(self, command, payload, *, exit_code=0, packaged=False):
        path = self.base / f'{command}-request.json'
        path.write_text(json.dumps(payload))
        helper = 'director-handoff.py' if command in {'impact-preview', 'amend-apply'} else 'director-state.py'
        entry = (CORE / 'skills/director/skill-tree-director-plan/scripts/director-entry.py'
                 if packaged else CORE / 'common/scripts' / helper)
        process = subprocess.run([sys.executable, '-B', str(entry),
                                  command, str(self.parent), '--input', str(path)], capture_output=True,
                                 text=True, timeout=40)
        self.assertEqual(process.returncode, exit_code, process.stdout + process.stderr)
        return json.loads(process.stdout)

    def test_accepted_amendment_holds_only_superseded_child_effects(self):
        child = D.WF.Store(self.child, neutral=True)
        prioritized = F.prioritized_task(child, 'Review the original carry rule', 'game/result.json')
        task = next(row for row in D.WF.parse(child.text()) if row['id'] == prioritized)
        launch_pin = {'task_id': prioritized, 'body_sha256': D.WF.digest(task['body'].encode())}
        prepare = self.assignment('plan-carry', 'art', 'fixture-artifact', child=self.selected_task)
        prepare['effects'] = ['process']
        launch = self.assignment('run-carry', 'game', 'fixture-consumer', child=launch_pin)
        launch.update(effects=['launch'], workspace='recorded-worktree')
        request = {**self.request, 'assignments': [
            self.assignment('draft-carry', 'game', 'fixture-consumer'),
            prepare, launch,
            self.assignment('independent-art', 'art', 'fixture-artifact'),
        ]}

        def freeze(fields):
            preview = self.cli('plan-preview', fields)
            self.cli('plan-freeze', {**fields, 'expected_preview_sha256': preview['preview_sha256']})
            return {**self.selector(), 'plan_revision': fields['plan_revision'], 'plan_sha256': preview['sha256']}

        def start(selector, authority):
            run_id = D.WF.identity('DR')
            self.cli('run-start', {**selector, 'director_run_id': run_id, 'assignment_ids': list(authority),
                                   'owner': {'actor': 'fixture-owner', 'reference': 'accept-plan', 'kind': 'owner-message'},
                                   'authority': authority, 'approved_defaults': [],
                                   'process_spec_sha256': {'plan-carry': 'a' * 64} if 'plan-carry' in authority else {}})
            return {'director_run_id': run_id}

        def dispatch(run, view, name, operation, *, exit_code=0):
            return self.cli('run-dispatch', {**run, 'expected_run_sha256': view['run_sha256'],
                                             'assignment_id': name, 'operation': operation,
                                             'request': {'expected_source_hash': D.WF.file_hash(child.future)}},
                            exit_code=exit_code)

        old = freeze(request)
        run = start(old, {'draft-carry': ['intake'], 'plan-carry': ['process'], 'run-carry': ['launch'],
                          'independent-art': ['intake']})
        revised = deepcopy(request)
        revised['plan_revision'] = 2
        revised['assignments'][0]['child']['title'] = 'Review the revised carry rule'
        revised['assignments'][1]['expected_result'] = 'Updated preparation evidence.'
        revised['assignments'][2]['expected_result'] = 'Updated launch evidence.'
        new = freeze(revised)
        action = {'draft-carry': 'intake', 'plan-carry': 'process', 'run-carry': 'start'}
        running = self.cli('run-status', run)
        self.assertEqual({name: running['assignments'][name]['next'] for name in action}, action)
        paused = self.cli('run-pause', {**run, 'expected_run_sha256': running['run_sha256']})
        amendment = {'previous': old, 'next': new}
        impact = self.cli('impact-preview', amendment)
        self.assertEqual(set(impact['affected']), set(action))
        self.cli('amend-apply', {'request': amendment, 'expected_preview_sha256': impact['preview_sha256'],
                                'owner_ref': 'fixture-owner-amendment'})
        resumed = self.cli('run-resume', {**run, 'expected_run_sha256': paused['run_sha256']})
        before = (self.files(self.parent), self.files(self.child))
        current = self.cli('run-status', run)
        self.assertEqual(self.cli('run-status', run), current)
        self.assertEqual(current, resumed)
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)
        self.assertEqual({name: current['assignments'][name]['next'] for name in action},
                         dict.fromkeys(action), 'Superseded assignments must withhold each fresh child effect')
        stale = {**current, 'run_sha256': paused['run_sha256']}
        denial = dispatch(run, stale, 'draft-carry', 'intake', exit_code=2)
        self.assertIn('changed since inspection', denial['error'])
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)
        for name, operation in action.items():
            with self.subTest(operation=operation):
                status = current['assignments'][name]
                self.assertEqual(status['supersession'], {'previous': old, 'next': new,
                                                           'amendment': impact['preview_sha256'],
                                                           'withheld_effect': operation})
                denial = dispatch(run, current, name, operation, exit_code=2)
                self.assertIn('superseded', denial['error'])
                current = self.cli('run-status', run)
                after = self.files(self.parent)
                self.assertEqual(dispatch(run, current, name, operation, exit_code=2), denial)
                self.assertEqual(self.files(self.parent), after)
        self.assertEqual(self.files(self.child), before[1])
        self.assertEqual(current['assignments']['independent-art']['next'], 'intake')
        independent = dispatch(run, current, 'independent-art', 'intake')
        replacement_run = start(new, {'draft-carry': ['intake']})
        replacement_view = self.cli('run-status', replacement_run)
        replacement = dispatch(replacement_run, replacement_view, 'draft-carry', 'intake')
        self.assertNotEqual(replacement['result']['id'], independent['result']['id'])
        before_replay = self.files(self.child)
        replay = dispatch(replacement_run, replacement_view, 'draft-carry', 'intake')
        self.assertEqual((replay['status'], replay['result']), ('replayed', replacement['result']))
        self.assertEqual(self.files(self.child), before_replay)
        self.assertEqual(next(row['title'] for row in D.WF.parse(child.text()) if row['id'] == replacement['result']['id']),
                         'Review the revised carry rule')

        third = deepcopy(revised)
        third['plan_revision'] = 3
        third['assignments'][3]['child']['title'] = 'Review the revised art requirement'
        third['assignments'][3]['id'] = 'replacement-art'
        newest = freeze(third)
        inherited = {'previous': new, 'next': newest}
        blocked = self.cli('impact-preview', inherited)
        self.assertTrue(any(row.get('director_run_id') == run['director_run_id']
                            and row['reason'] == 'director-writer-requires-pause' for row in blocked['blockers']))
        current = self.cli('run-status', run)
        paused = self.cli('run-pause', {**run, 'expected_run_sha256': current['run_sha256']})
        impact = self.cli('impact-preview', inherited)
        self.cli('amend-apply', {'request': inherited, 'expected_preview_sha256': impact['preview_sha256'],
                                'owner_ref': 'fixture-owner-third-revision'})
        current = self.cli('run-resume', {**run, 'expected_run_sha256': paused['run_sha256']})
        status = current['assignments']['independent-art']
        self.assertEqual(status['supersession'], {'previous': new, 'next': newest, 'amendment': impact['preview_sha256'],
                                                  'withheld_effect': None})
        replay = dispatch(run, current, 'independent-art', 'intake')
        self.assertEqual((replay['status'], replay['result']), ('replayed', independent['result']))
        self.assertEqual(self.files(self.child), before_replay)
        new_art = start(newest, {'replacement-art': ['intake']})
        art_view = self.cli('run-status', new_art)
        art = dispatch(new_art, art_view, 'replacement-art', 'intake')
        self.assertNotEqual(art['result']['id'], independent['result']['id'])
        self.assertEqual(dispatch(new_art, art_view, 'replacement-art', 'intake')['status'], 'replayed')

    def test_amendment_rejects_a_replacement_with_a_claimed_dispatch_key(self):
        child = D.WF.Store(self.child, neutral=True)
        request = {**self.request, 'assignments': [
            self.assignment('draft-carry', 'game', 'fixture-consumer'),
            self.assignment('planned-art', 'art', 'fixture-artifact', dependencies=['draft-carry']),
        ]}

        def freeze(fields):
            preview = self.cli('plan-preview', fields)
            self.cli('plan-freeze', {**fields, 'expected_preview_sha256': preview['preview_sha256']})
            return {**self.selector(), 'plan_revision': fields['plan_revision'], 'plan_sha256': preview['sha256']}

        original = freeze(request)
        run_id = D.WF.identity('DR')
        run = {'director_run_id': run_id}
        self.cli('run-start', {**original, **run, 'assignment_ids': ['draft-carry'],
                              'owner': {'actor': 'fixture-owner', 'reference': 'accept-plan', 'kind': 'owner-message'},
                              'authority': {'draft-carry': ['intake']}, 'approved_defaults': [],
                              'process_spec_sha256': {}})
        view = self.cli('run-status', run)
        dispatch = {**run, 'expected_run_sha256': view['run_sha256'], 'assignment_id': 'draft-carry',
                    'operation': 'intake', 'request': {'expected_source_hash': D.WF.file_hash(child.future)}}
        dispatched = self.cli('run-dispatch', dispatch)
        parent = D.WF.Store(self.parent, route_queue=False, neutral=True)
        queue_id = child.load()['run_registry']['queue_id']
        D.WF.director_dispatch_helper().retain_intent(parent, 'intake', {
            'expected_source_hash': D.WF.file_hash(child.future),
            'director_dispatch': {'schema': 1, 'director_id': 'lantern-fixture', 'assignment_id': 'planned-art',
                                  'queue_id': queue_id, 'plan_sha256': original['plan_sha256']},
        })
        view = self.cli('run-status', run)
        self.cli('run-pause', {**run, 'expected_run_sha256': view['run_sha256']})
        revised = deepcopy(request)
        revised['plan_revision'] = 2
        revised['assignments'][0]['child']['title'] = 'Review the revised carry rule'
        amendment = {'previous': original, 'next': freeze(revised)}
        before = self.files(self.parent), self.files(self.child)
        impact = self.cli('impact-preview', amendment)
        self.assertEqual([(row['assignment_id'], row['operation'], row['reason'], row['claim_kind'])
                          for row in impact['blockers']], [
            ('draft-carry', 'intake', 'dispatch-identity-already-claimed', 'child-receipt'),
            ('planned-art', 'intake', 'dispatch-identity-already-claimed', 'parent-intent'),
        ])
        handoff = D.WF.owned_module('director_handoff_claim_test', CORE / 'common/scripts/director-handoff.py')
        with self.assertRaisesRegex(ValueError, 'amendment gates must pass'):
            handoff.DirectorHandoffs(self.director, self.plans).run('amend-apply', {
                'request': amendment, 'expected_preview_sha256': impact['preview_sha256'],
                'owner_ref': 'fixture-owner-rejected-amendment'})
        replay = self.cli('run-dispatch', dispatch)
        self.assertEqual((replay['status'], replay['result']), ('replayed', dispatched['result']))
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)

    def test_preview_fingerprint_and_impact_and_historical_read(self):
        before = (self.files(self.parent), self.files(self.child))
        preview = self.cli('plan-preview', self.request)
        self.assertEqual(preview, self.plans.preview({**self.request, 'assignments': self.request['assignments'][::-1]}))
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)
        self.assertNotIn(str(self.base), json.dumps(preview))
        self.assertEqual(preview['briefs']['create-lantern']['child'], self.selected_task)
        self.assertEqual(preview['briefs']['create-lantern']['plan_sha256'], preview['sha256'])
        frozen_request = {**self.request, 'expected_preview_sha256': preview['preview_sha256']}
        frozen = self.cli('plan-freeze', frozen_request)
        self.assertEqual(frozen['plan_sha256'], preview['sha256'])
        self.assertEqual(self.plans.freeze(frozen_request)['status'], 'replayed')
        self.assertEqual(self.files(self.child), before[1])
        context = self.cli('status', {'plan_context': self.selector()})['plan_context']
        self.assertEqual(context, self.cli('plan-context', self.selector()))
        impact = self.cli('plan-impact', {**self.selector(), 'changed': {
            key: self.story_pin[key] for key in ('area_id', 'adapter', 'record_id')
        }})
        self.assertEqual(impact['affected'], [
            {'assignment_id': 'create-lantern', 'paths': [['create-lantern']]},
            {'assignment_id': 'verify-lantern', 'paths': [['create-lantern', 'verify-lantern']]},
        ])
        self.revise({**self.intent, 'expected_current_sha256': self.first['sha256'],
                     'intent': {**self.intent['intent'], 'description': 'Prepare the belt variant.'}})
        self.assertEqual(self.plans.context(self.selector()), context)
        self.assertFalse(self.plans.preview(self.request)['objective_current'])

    def test_assignment_context_finds_the_committed_belt_handoff(self):
        accepted = self.manifest['story']['changed']
        outside = self.child / 'archive'
        outside.mkdir()
        (outside / 'notes.md').write_text('Old cave-lantern-carry belt notes.\n')
        F.git(self.child, 'add', 'archive')
        F.git(self.child, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
              '-c', 'commit.gpgsign=false', 'commit', '-m', 'Add an out-of-scope record')
        commit = F.git(self.child, 'rev-parse', 'HEAD')
        request = deepcopy(self.request)
        art = next(row for row in request['assignments'] if row['id'] == 'create-lantern')
        art['pins'] = [self.fixture_pin('story', 'fixture-narrative', self.manifest['story']['id'], accepted)]
        preview = self.cli('plan-preview', request)
        self.cli('plan-freeze', {**request, 'expected_preview_sha256': preview['preview_sha256']})

        selector = {**self.selector(), 'assignment_id': 'verify-lantern'}
        context = self.cli('plan-context', selector)
        self.assertEqual(context, self.cli('status', {'plan_context': selector})['plan_context'])
        scope = context['context_search']
        self.assertEqual({(row['path'], row['commit']) for row in scope['sources']},
                         {('art', commit), ('game', commit), ('art/lantern.json', commit),
                          ('story/carry-belt.json', commit)})

        # A later commit changes the same path. The exact earlier source remains reproducible.
        (self.child / accepted['path']).write_text('Changed working source, cave-lantern-carry belt.\n')
        F.git(self.child, 'add', accepted['path'])
        F.git(self.child, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
              '-c', 'commit.gpgsign=false', 'commit', '-m', 'Change the source after freezing')
        F.git(self.child, 'config', 'grep.column', 'true')
        before = self.files(self.parent), self.files(self.child)
        lookup = {**scope['request'], 'query': 'cave-lantern-carry belt'}
        result = self.cli('context-search', lookup)
        self.assertEqual(self.cli('context-search', lookup, packaged=True), result)
        match = result['matches'][0]
        self.assertEqual((match['path'], match['commit'], match['sha256'], match['area_id']),
                         (accepted['path'], commit, accepted['sha256'], 'story'))
        self.assertNotIn('\x00', match['excerpt'])
        self.assertIn({'line': 4, 'text': '  "attachment": "belt"'}, match['context'])
        self.assertEqual(match['pins'][0]['revision'], 'r002')
        self.assertNotIn('story/carry-hand.json', [row['path'] for row in result['matches']])
        self.assertNotIn('archive/notes.md', [row['path'] for row in result['matches']])
        self.assertNotIn(str(self.base), json.dumps(result))
        self.assertFalse(self.cli('context-search', {**lookup, 'expected_plan_sha256': '0' * 64}, exit_code=2)['ok'])
        self.assertFalse(self.cli('context-search', {**lookup, 'scope': '.'}, exit_code=2)['ok'])
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)

    def test_context_search_checks_a_pin_in_a_separate_queue(self):
        remote = {**self.area('remote-story', 'story', 'narrative', ['fixture-canon']),
                  'checkout': str(self.maintenance)}
        write_only = {**self.area('remote-art', 'art', 'art', ['fixture-artifact']),
                      'checkout': str(self.maintenance), 'allowed_effects': ['intake']}
        setup = {'director_id': 'lantern-fixture', 'areas': [remote, write_only]}
        self.director.apply({**setup, 'expected_preview_sha256': self.director.preview(setup)['preview_sha256']})
        accepted = self.manifest['story']['changed']
        request = deepcopy(self.request)
        art = next(row for row in request['assignments'] if row['id'] == 'create-lantern')
        art['pins'] = [self.fixture_pin('remote-story', 'fixture-narrative', self.manifest['story']['id'], accepted),
                       {**self.art_pin, 'area_id': 'remote-art'}]
        preview = self.cli('plan-preview', request)
        self.cli('plan-freeze', {**request, 'expected_preview_sha256': preview['preview_sha256']})
        selector = {**self.selector(), 'assignment_id': 'verify-lantern'}
        scope = self.cli('plan-context', selector)['context_search']
        remote_source = next(source for source in scope['sources'] if source['area']['id'] == 'remote-story')
        self.assertIsNone(remote_source['commit'])

        lookup = {**scope['request'], 'query': 'cave-lantern-carry belt'}
        result = self.cli('context-search', lookup)
        match = next(row for row in result['matches'] if row['area_id'] == 'remote-story')
        self.assertEqual((match['commit'], match['sha256']),
                         (F.git(self.maintenance, 'rev-parse', 'HEAD'), accepted['sha256']))
        denied = next(row for row in result['sources'] if row['area_id'] == 'remote-art')
        self.assertEqual((denied['status'], denied['reason']),
                         ('unavailable', 'The registered area permits no read-only effects'))
        self.assertNotIn('remote-art', [row['area_id'] for row in result['matches']])
        (self.maintenance / accepted['path']).write_text('Different cave-lantern-carry belt source.\n')
        F.git(self.maintenance, 'add', accepted['path'])
        F.git(self.maintenance, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
              '-c', 'commit.gpgsign=false', 'commit', '-m', 'Change the separately bound pin')
        after = self.cli('context-search', lookup)
        self.assertNotIn('remote-story', [row['area_id'] for row in after['matches']])
        statuses = {row['area_id']: row['status'] for row in after['sources']}
        self.assertEqual(statuses, {'art': 'searched', 'game': 'searched', 'remote-story': 'unavailable',
                                    'remote-art': 'unavailable'})

    def test_rejects_wrong_capability_required_pins_task_body_and_cycles(self):
        before = (self.files(self.parent), self.files(self.child))
        mutations = [
            ('positively qualified', lambda row: row.update(capability='artworkshop-stage')),
            ('changed', lambda row: row['pins'][0].update(sha256='0' * 64)),
            ('unsupported', lambda row: row['pins'][0].update(adapter='artworkshop-stage')),
            ('exact body changed', lambda row: row['child'].update(body_sha256='0' * 64)),
            ('cycle', lambda row: row.update(depends_on=['verify-lantern'])),
            ('write paths', lambda row: row.update(write_paths=['../elsewhere'])),
        ]
        for message, mutate in mutations:
            request = deepcopy(self.request)
            mutate(request['assignments'][1])
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                self.plans.preview(request)
        self.assertEqual((self.files(self.parent), self.files(self.child)), before)
        request = deepcopy(self.request)
        request['assignments'][1]['pins'][0].update(strength='optional', adapter='artworkshop-stage')
        optional = self.plans.preview(request)
        self.assertEqual(optional['plan']['assignments'][0]['pins'][0]['status'], 'unsupported')

    def test_freeze_rechecks_child_source_and_installed_profile(self):
        preview = self.plans.preview(self.request)
        request = {**self.request, 'expected_preview_sha256': preview['preview_sha256']}
        before = self.files(self.parent)
        story = self.child / self.story_pin['path']
        original = story.read_bytes()
        story.write_bytes(original + b'\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.plans.freeze(request)
        story.write_bytes(original)
        manager = self.child / '.skill-tree/installation/manager.js'
        manager.write_bytes(manager.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'positively qualified'):
            self.plans.freeze(request)
        self.assertEqual(self.files(self.parent), before)

    def test_narrative_adapter_uses_accepted_archive_and_rejects_draft_fallback(self):
        module = load('narrative_state_plan_test', CORE / 'common/scripts/narrative-state.py')
        cleared = module.Project(self.child / 'story')
        cleared.init()
        record_id = 'quest-carry-lantern'
        draft = cleared.root / '.narrative/records' / (record_id + '.md')
        draft.write_text('Accepted lantern prose.')
        draft.with_suffix('.json').write_text(json.dumps({'id': record_id, 'kind': 'quest', 'depends_on': []}))
        proposal, _ = cleared.prepare('work-lantern', 'continuity-main', None, [record_id], [])
        proposal_file = self.base / 'proposal.json'
        proposal_file.write_text(json.dumps(proposal))
        decision = {'proposal_digest': proposal['proposal_digest'], 'decision': 'accepted',
                    'author': 'Fixture owner', 'reason': 'The accepted carry requirement.'}
        (cleared.root / 'decision.json').write_text(json.dumps(decision))
        snapshot = cleared.accept(proposal_file, proposal['proposal_digest'], 'decision.json')['snapshot']
        sha = proposal['entries'][record_id]['revision']
        pin = {'area_id': 'story', 'adapter': 'narrative-canon', 'record_id': record_id,
               'revision': sha, 'sha256': sha, 'role': 'accepted-quest', 'strength': 'required',
               'snapshot': snapshot}
        request = deepcopy(self.request)
        request['assignments'][1]['pins'] = [pin]
        preview = self.plans.preview(request)
        draft.write_text('Unaccepted draft adjustment.')
        self.assertEqual(self.plans.preview(request), preview)
        cleared.snapshot_path(snapshot).unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.plans.preview(request)


if __name__ == '__main__':
    unittest.main()
