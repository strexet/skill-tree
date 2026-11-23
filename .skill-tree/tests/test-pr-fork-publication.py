"""Exercise fork identity through the real publication adapter with an in-process transport."""
import importlib.util
from pathlib import Path
import unittest
import subprocess
import tempfile
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'common/scripts/pr-review-state.py'
spec = importlib.util.spec_from_file_location('review', path)
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)


class ForkPublicationTests(unittest.TestCase):
    def test_prepare_create_and_resume_the_correct_fork_after_lost_response(self):
        api = pr.GitHub('/unused', 'strexet/skill-tree', head_repository='alice/source')
        base = {'ref': 'develop', 'repo': {'full_name': 'strexet/skill-tree'}}
        foreign = {'number': 12, 'state': 'open', 'base': base,
                   'head': {'ref': 'fix', 'sha': 'a'*40, 'repo': {'full_name':'bob/source'}}}
        rows, creations = [foreign], []
        def transport(*args):
            if 'GET' in args:
                self.assertIn('head=alice:fix', args)
                return rows
            if 'POST' in args:
                self.assertIn('head=alice:fix', args)
                self.assertIn('base=develop', args)
                rows.append({**foreign, 'number': 15, 'head': {**foreign['head'], 'repo': {'full_name':'alice/source'}}})
                creations.append(args)
                raise pr.ReviewError('Response unavailable')
            self.assertIn('/15', next(arg for arg in args if '/pulls/' in arg))
            return rows[-1]
        with patch.object(api, 'gh', side_effect=transport):
            self.assertIsNone(api.find('fix','develop'))
            with self.assertRaises(pr.ReviewError):
                api.ensure('fix','develop','Title','Body',expected_head='a'*40)
            self.assertEqual(api.ensure('fix','develop','Title','Body',expected_head='a'*40)['number'],15)
            self.assertEqual(len(creations),1)

    def test_same_repository_and_same_organization_fork(self):
        for head,label in [('strexet/skill-tree','fix'),('strexet/maintenance','strexet:fix')]:
            with self.subTest(head=head):
                api=pr.GitHub('/unused','strexet/skill-tree',head_repository=head)
                accepted={'id':91,'number':3,'state':'open','head':{'ref':'fix','repo':{'full_name':head}},
                          'base':{'ref':'develop','repo':{'full_name':'strexet/skill-tree'}}}
                with patch.object(api,'gh',side_effect=[[],accepted]) as gh:
                    api.ensure('fix','develop','Title','Body')
                    self.assertIn('head='+label,gh.call_args.args)
                    self.assertEqual('head_repo=maintenance' in gh.call_args.args,head.endswith('/maintenance'))

    def test_preflight_remote_pair_matches_actual_push_url(self):
        with tempfile.TemporaryDirectory() as location:
            root = Path(location)
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True)
            git('init', '-b', 'develop')
            base = 'https://github.com/strexet/skill-tree.git'
            git('remote','add','upstream',base)
            git('remote','add','origin',base)
            git('remote','set-url','--push','origin','git@github.com:alice/mirror.git')
            fields = pr.publication_repositories(root, {'head_remote':'origin'},base,'upstream')
            self.assertEqual(fields, {'head_remote':'origin','head_repository':'alice/mirror','base_repository':'strexet/skill-tree'})
            self.assertEqual(pr.GitHub.from_preflight(root,fields).head_repository,'alice/mirror')
            with self.assertRaisesRegex(pr.ReviewError,'differ'):
                pr.publication_repositories(root,{'head_remote':'origin','head_repository':'bob/mirror'},base,'upstream')

    def test_wrong_provider_owner_or_head_commit_holds_review(self):
        api=pr.GitHub('/unused','strexet/skill-tree',head_repository='alice/source')
        scope={'source_branch':'fix','target_branch':'develop','base_oid':'a'*40,'head':'b'*40}
        raw={'headRefName':'fix','baseRefName':'develop','headRefOid':scope['head'],'baseRefOid':scope['base_oid'],
             'headRepositoryOwner':{'login':'bob'},'headRepository':{'name':'source'}}
        for owner,commit in [('bob',scope['head']),('alice','c'*40)]:
            with self.subTest(owner=owner),patch.object(api,'gh',return_value={**raw,'headRepositoryOwner':{'login':owner},'headRefOid':commit}) as gh:
                with self.assertRaisesRegex(pr.ReviewError,'identity'):
                    api.snapshot(7,scope,{})
                self.assertIn('headRepositoryOwner',gh.call_args.args[-1])

    def test_changed_fork_identity_cannot_reuse_a_publication(self):
        baseline={'repo_id':'repo','remote':'upstream','source_branch':'fix','target_branch':'develop',
                  'base_oid':'a'*40,'head':'f'*40,'head_repository':'alice/source','base_repository':'strexet/skill-tree'}
        other={**baseline,'head_repository':'bob/source'}
        self.assertNotEqual(pr.identity(baseline),pr.identity(other))
        with self.assertRaisesRegex(pr.ReviewError,'identity conflict'):
            pr.reconcile({'identity':pr.identity(baseline)},other)


if __name__=='__main__':
    unittest.main()
