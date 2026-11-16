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
                'allowed_effects': ['status', 'intake']}

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

    def cli(self, command, payload):
        path = self.base / f'{command}-request.json'
        path.write_text(json.dumps(payload))
        process = subprocess.run([sys.executable, '-B', str(CORE / 'common/scripts/director-state.py'),
                                  command, str(self.parent), '--input', str(path)], capture_output=True,
                                 text=True, timeout=40)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return json.loads(process.stdout)

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
