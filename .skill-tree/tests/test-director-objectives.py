from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / 'common/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = load('director-state')
O = load('director-objectives')
O.D = D
WF = D.WF
WS = D.WS


class DirectorObjectives(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.parent = self.base / 'parent'
        self.parent.mkdir()
        self.child = self.base / 'child'
        self.child.mkdir()
        WS.local_git_text(self.child, 'init', '-b', 'develop')
        core = WF.Store(self.child)
        core.future.parent.mkdir(parents=True)
        core.future.write_text('# Future\n\n## Pending Task Format\n\nFixed fields.\n\n'
                               '## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config = self.child / '.skill-tree/config'
        config.mkdir()
        (config / 'repository.json').write_text('{"role":"source"}\n')
        (self.child / 'art').mkdir()
        (self.child / 'art/source.txt').write_text('Source bytes.\n')
        WS.local_git_text(self.child, 'add', '.')
        WS.local_git_text(self.child, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                          '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'Fixture')
        self.queue_id = WS.setup(core, {})['queue_id']
        self.registry = D.DirectorRegistry(self.parent)
        req = {'director_id': 'lantern-pilot', 'areas': [self.area('maintenance', '.skill-tree', 'source-maintenance'),
                                                       self.area('art', 'art', 'art')]}
        self.registry.apply({**req, 'expected_preview_sha256': self.registry.preview(req)['preview_sha256']})
        self.objective_id = WF.identity('OB')
        self.plan_id = WF.identity('PL')
        self.task_id = WF.identity('T')
        self.run_id = WF.identity('WR')
        self.outcome_id = WF.identity('O')
        self.intent = {'owner_ref': 'product-intent-1', 'title': 'Lantern handoff',
                       'description': 'Carry the lantern. Сохранить силуэт.\nKeep source wording.',
                       'acceptance': [{'id': 'carry', 'criterion': 'Use the exact approved grip.'}]}
        self.ledger = O.ObjectiveLedger(self.registry)
        self.create_request = {'objective_id': self.objective_id, 'expected_current_sha256': None, 'intent': self.intent}

    def area(self, area_id, scope, role):
        return {'id': area_id, 'role': role, 'checkout': str(self.child), 'scope': scope,
                'capabilities': ['review-source'], 'interface': {'kind': 'skill-tree', 'version': 1},
                'allowed_effects': ['status', 'intake']}

    def apply(self, request):
        preview = self.ledger.preview(request)
        return self.ledger.apply({**request, 'expected_preview_sha256': preview['preview_sha256']})

    def read(self, **values):
        return self.ledger.read({'objective_id': self.objective_id, **values})

    def snapshot(self, root):
        return {path.relative_to(root): path.read_bytes() for path in root.rglob('*') if path.is_file()}

    def pin(self, objective):
        return self.ledger.pin_plan({'objective_id': self.objective_id,
                                     'expected_ledger_sha256': objective['ledger_sha256'],
                                     'plan_id': self.plan_id, 'plan_revision': 1, 'plan_sha256': 'a' * 64,
                                     'objective_revision': objective['current']['revision'],
                                     'objective_sha256': objective['current']['sha256'],
                                     'assignments': {'lantern-asset': {'area_id': 'art', 'task_ids': [self.task_id]}}})

    def recorded_child(self):
        core = WF.Store(self.child, neutral=True)
        state = core.load()
        self.worktree = self.base / 'art-worktree'
        WS.local_git_text(self.child, 'worktree', 'add', '-b', 'codex/art', str(self.worktree))
        locator = WS.runtime(self.child)
        locator['worktrees'][self.run_id] = str(self.worktree)
        WS.atomic(WS.runtime_file(self.child), locator)
        artifact = self.worktree / 'art/lantern.bin'
        artifact.write_bytes(b'Approved lantern payload')
        check_evidence = self.worktree / 'art/reader.log'
        check_evidence.write_bytes(b'Import matched expectations.')
        evidence = lambda path: {'path': path.relative_to(self.worktree).as_posix(), 'sha256': WF.file_hash(path)}
        source_sha = WF.file_hash(self.worktree / 'art/source.txt')
        outcome = {'id': self.outcome_id, 'task_id': self.task_id, 'run_id': self.run_id,
                   'title': 'Local art result', 'outcome': 'Keep child prose exclusively in Core history.',
                   'disposition': 'completed', 'source_fingerprints': {'art/source.txt': source_sha},
                   'acceptance': [{'criterion': 'Approved grip.', 'result': 'pass', 'evidence': [evidence(artifact)]}],
                   'check_results': [{'check': {'id': 'verify-import'}, 'result': {
                       'result': 'pass', 'key': 'b' * 64, 'actual_lane': 'integration',
                       'sources': {'art/source.txt': source_sha}, 'evidence': [evidence(check_evidence)]}}]}
        path = self.child / '.skill-tree/history/task-outcomes.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(outcome) + '\n')
        run = {'id': self.run_id, 'mode': 'next', 'snapshot': [self.task_id], 'root_task_id': self.task_id,
               'current_task_id': None, 'phase': 'completed', 'required_ids': [self.task_id],
               'deferred_ids': [], 'pending_ids': [], 'processing_results': [], 'completed_ids': [self.task_id],
               'limits': {}, 'next_action': None, 'stop_reason': None, 'admission': {},
               'admitted_task_ids': [self.task_id], 'admitted_groups': {},
               'completion_refs': {self.task_id: self.outcome_id},
               'workspace': {'branch': 'codex/art', 'repo_id': WS.repo_id(self.child)},
               'delivery': {'implementation': 'completed', 'status': 'local-result'}}
        state['run_registry']['runs'][self.run_id] = run
        core.state.write_text(WF.dump(state))
        return {'artifact_id': 'lantern-model', **evidence(artifact)}

    def link(self, objective, artifact, **values):
        return self.ledger.link_outcome({'objective_id': self.objective_id,
                                         'expected_ledger_sha256': objective['ledger_sha256'], 'plan_id': self.plan_id,
                                         'plan_revision': 1, 'plan_sha256': 'a' * 64, 'assignment_id': 'lantern-asset',
                                         'area_id': 'art', 'task_id': self.task_id, 'run_id': self.run_id,
                                         'outcome_id': self.outcome_id, 'artifacts': [artifact],
                                         'check_ids': ['verify-import'], **values})

    def test_preview_revision_noop_and_exact_replay(self):
        before = self.snapshot(self.parent)
        preview = self.ledger.preview(self.create_request)
        self.assertEqual(self.snapshot(self.parent), before)
        first = self.ledger.apply({**self.create_request, 'expected_preview_sha256': preview['preview_sha256']})
        replay = self.ledger.apply({**self.create_request, 'expected_preview_sha256': preview['preview_sha256']})
        self.assertEqual(replay['status'], 'replayed')
        self.assertEqual(first['current'], replay['current'])
        same = self.apply({**self.create_request, 'expected_current_sha256': first['current']['sha256']})
        self.assertEqual(same['status'], 'unchanged')
        second = self.apply({**self.create_request, 'expected_current_sha256': first['current']['sha256'],
                             'intent': {**self.intent, 'description': 'Check the belt variant.'}})
        self.assertEqual(second['current']['revision'], 2)
        self.assertEqual(self.read(revision=1)['revision']['intent'], self.intent)
        self.assertNotIn(str(self.base), json.dumps(self.read()))
        third = self.apply({**self.create_request, 'expected_current_sha256': second['current']['sha256']})
        self.assertNotEqual(third['current']['sha256'], first['current']['sha256'])
        with self.assertRaisesRegex(D.DirectorError, 'basis changed'):
            self.ledger.preview({**self.create_request, 'intent': {**self.intent, 'title': 'Stale edit'}})

    def test_past_objective_is_retained_when_plan_pins_are_added_and_replayed(self):
        first = self.apply(self.create_request)
        pinned = self.pin(first)
        self.assertEqual(self.pin(first)['status'], 'replayed')
        second = self.apply({**self.create_request, 'expected_current_sha256': first['current']['sha256'],
                             'intent': {**self.intent, 'description': 'Begin a new revision.'}})
        self.assertEqual(self.read(revision=1)['plans'][0]['objective_sha256'], first['current']['sha256'])
        self.assertEqual(self.read()['plans'], [])
        self.assertEqual(second['current']['revision'], 2)
        self.assertNotEqual(first['ledger_sha256'], pinned['ledger_sha256'])

    def test_outcome_links_keep_child_state_and_show_independent_evidence_dimensions(self):
        pinned = self.pin(self.apply(self.create_request))
        artifact = self.recorded_child()
        before = self.snapshot(self.child)
        linked = self.link(pinned, artifact)
        self.assertEqual(self.link(pinned, artifact)['status'], 'replayed')
        self.assertEqual(self.snapshot(self.child), before)
        view = self.read()['outcomes'][0]
        self.assertEqual((view['completion'], view['evidence_availability'], view['source_freshness'],
                          view['integration'], view['delivery']), ('completed', 'available', 'current', 'unverified', 'local-result'))
        self.assertEqual(view['checks'][0]['verdict'], 'pass')
        self.assertNotIn('Keep child prose exclusively', json.dumps(self.read()))
        (self.worktree / 'art/source.txt').write_text('Changed source.\n')
        self.assertEqual(self.read()['outcomes'][0]['source_freshness'], 'stale')
        (self.worktree / 'art/lantern.bin').unlink()
        self.assertEqual(self.read()['outcomes'][0]['evidence_availability'], 'unavailable')
        self.assertEqual(self.read()['outcomes'][0]['completion'], 'completed')
        self.assertEqual(linked['current']['revision'], 1)
        locator = WS.runtime(self.child)
        locator['worktrees'].pop(self.run_id)
        WS.atomic(WS.runtime_file(self.child), locator)
        self.assertEqual(self.read()['outcomes'][0]['source_freshness'], 'unknown')

    def test_wrong_artifact_digest_or_unassigned_task_is_fail_closed(self):
        pinned = self.pin(self.apply(self.create_request))
        artifact = self.recorded_child()
        before = self.snapshot(self.parent)
        with self.assertRaisesRegex(D.DirectorError, 'acceptance evidence'):
            self.link(pinned, {**artifact, 'sha256': 'f' * 64})
        with self.assertRaisesRegex(D.DirectorError, 'not pinned'):
            self.ledger.link_outcome({'objective_id': self.objective_id, 'expected_ledger_sha256': pinned['ledger_sha256'],
                                      'plan_id': self.plan_id, 'plan_revision': 1, 'plan_sha256': 'a' * 64,
                                      'assignment_id': 'lantern-asset', 'area_id': 'art', 'task_id': WF.identity('T'),
                                      'run_id': self.run_id, 'outcome_id': self.outcome_id, 'artifacts': [artifact],
                                      'check_ids': ['verify-import']})
        self.assertEqual(self.snapshot(self.parent), before)

    def test_interrupted_objective_write_requires_same_request_for_recovery(self):
        preview = self.ledger.preview(self.create_request)
        request = {**self.create_request, 'expected_preview_sha256': preview['preview_sha256']}
        existing = self.registry.store.replace
        def interrupt(path, text):
            if '/objectives/' in path.as_posix():
                raise OSError('Interrupted after journal')
            return existing(path, text)
        with patch.object(self.registry.store, 'replace', side_effect=interrupt):
            with self.assertRaisesRegex(OSError, 'Interrupted'):
                self.ledger.apply(request)
        journal = self.parent / '.skill-tree/.transaction.json'
        self.assertTrue(journal.is_file())
        self.assertFalse((self.parent / O.objective_path(self.objective_id)).is_file())
        with self.assertRaisesRegex(ValueError, 'exact original'):
            self.ledger.apply({**request, 'intent': {**self.intent, 'title': 'Another request'}})
        self.assertTrue(journal.is_file())
        recovered = self.ledger.apply(request)
        self.assertEqual(recovered['status'], 'replayed')
        self.assertFalse(journal.exists())


if __name__ == '__main__':
    unittest.main()
