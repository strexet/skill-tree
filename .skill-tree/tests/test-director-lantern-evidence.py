"""Check exact native handoff evidence and narrowly affected Director paths."""
import importlib.util
import json
import os
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'director_lantern_handoff', ROOT / '.skill-tree/tests/fixtures/director/project-lantern-handoff.py')
HANDOFF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HANDOFF)


def assert_archive_outcomes(test, replay):
    archive = json.loads(HANDOFF.ART.raw(ROOT, HANDOFF.HANDOFF))
    excluded = {'verification_sources', 'projection_sha256'}
    # The historical archive stays pinned to the original verifier bytes.
    archived_projection = {key: value for key, value in archive.items() if key != 'projection_sha256'}
    test.assertEqual(archive['projection_sha256'], HANDOFF.PLANS.digest(archived_projection))
    test.assertEqual(set(archive['verification_sources']), set(replay['verification_sources']))
    test.assertEqual({key: value for key, value in archive.items() if key not in excluded},
                     {key: value for key, value in replay.items() if key not in excluded})
    return archive


class DirectorLanternHandoffTests(unittest.TestCase):
    def test_replays_archived_compact_receipts_and_impact(self):
        replay = HANDOFF.projection(ROOT, *HANDOFF.inputs(ROOT))
        archive = assert_archive_outcomes(self, replay)
        self.assertEqual(archive['impact']['affected'], [
            {'assignment_id': 'lantern-attachment', 'paths': [['lantern-attachment']]},
            {'assignment_id': 'lantern-cave-carry', 'paths': [['lantern-attachment', 'lantern-cave-carry']]},
        ])
        self.assertEqual(archive['impact']['current'], [
            'lantern-model-geometry', 'lantern-repeat-import', 'wall-mount-diagnostic',
        ])
        self.assertEqual(archive['change']['previous']['socket'], 'GripSocket')
        self.assertEqual(archive['change']['next']['socket'], 'BeltSocket')
        self.assertNotEqual(archive['change']['previous']['check'], archive['change']['next']['check'])
        self.assertEqual(archive['acceptance'], {
            'previous_requirement': 'eligible', 'replacement_while_unverified': 'held',
            'next_requirement_after_matching_check': 'eligible', 'delivery': 'unreviewed',
        })

    def test_wrong_current_artifact_or_missing_raw_evidence_is_rejected(self):
        fixture, art, receipts, _ = HANDOFF.inputs(ROOT)
        current = receipts['PlayMode']
        changed = {**current, 'artifact': {**current['artifact'], 'sha256': '0' * 64}}
        _, *values = HANDOFF.UNITY.receipt_inputs(ROOT, 'PlayMode')
        with self.assertRaisesRegex(ValueError, 'fixture or input digests'):
            HANDOFF.UNITY.verify_compact(changed, 'PlayMode', *values)
        with self.assertRaisesRegex(ValueError, 'Missing or oversized artifact'):
            HANDOFF.UNITY.verify_native(receipts['PlayMode'], 'PlayMode', fixture, ROOT / 'unavailable-native-evidence')
        self.assertNotEqual(art['artifact']['sha256'], changed['artifact']['sha256'])


if __name__ == '__main__':
    class DirectorLanternObservedTests(unittest.TestCase):
        def test_exact_blender_and_unity_observations(self):
            path = os.environ.get(HANDOFF.EVIDENCE_ENV)
            self.assertTrue(path, 'The selected handoff check requires the actual Unity report directory')
            replay = HANDOFF.from_observations(ROOT, Path(path).resolve(strict=True))
            archive = assert_archive_outcomes(self, replay)
            self.assertEqual(archive['scope'], 'disposable-native-fixture')

    unittest.main()
