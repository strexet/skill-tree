import importlib.util
import json
from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pr_cycle',CORE/'common/scripts/pr-review-state.py');pr=importlib.util.module_from_spec(spec);spec.loader.exec_module(pr)

class ReviewCycleTests(unittest.TestCase):
    def setUp(self):
        self.snapshot={'repo_id':'fixture-repository','remote':'origin','source_branch':'feature/example','target_branch':'develop','head':'a'*40,'base_oid':'b'*40,'changed_files':['src/main.py'],'pr':{'id':'PR_fixture','number':1,'url':'https://example.invalid/pr/1'},'state':'OPEN','threads':[],'reviews':[],'comments':[],'checks':[{'name':'tests','status':'success','required':True}],'checks_known':True,'approvals_known':True,'approvals_required':True,'approved':False,'mergeable':'MERGEABLE'}
        self.params=pr.parameters('feature/example',{});self.record=pr.new_record(self.snapshot,self.params)
    def review(self,**overrides):
        return {'head':self.snapshot['head'],'base_oid':self.snapshot['base_oid'],'target_branch':self.snapshot['target_branch'],'files':self.snapshot['changed_files'],'context_inspected':True,'discussions_inspected':True,'checks_inspected':True,'findings':[],'evidence':['review.json'],**overrides}
    def ready(self):return pr.ready(pr.reviewed(self.record,self.snapshot,self.review()),self.snapshot)
    def test_defaults_and_explicit_branch_parameters_are_independent_of_base(self):
        self.assertEqual((self.params['source_branch'],self.params['target_branch'],self.params['merge']),('feature/example','develop',False))
        result=pr.parameters('Current/Case',{'source_branch':'Feature/MixedCase','target_branch':'Release/Case','base_branch':'main','merge':False})
        self.assertEqual((result['source_branch'],result['target_branch']),('Feature/MixedCase','Release/Case'))
        natural=pr.parameters('other',{'instruction':'ПР из Feature/MixedCase в Release/Case'})
        self.assertEqual(natural['source_branch'],'Feature/MixedCase');self.assertEqual(natural['target_branch'],'Release/Case')
    def test_owner_merge_forms(self):
        for instruction in ['ПР с мерджем','with merge','merge=true','затем смержи в develop','затем смерджи в develop','затем смржи в develop','затем вмержи в develop','then merge into develop']:
            with self.subTest(instruction=instruction):self.assertTrue(pr.parameters('feature/example',{'instruction':instruction})['merge'])
    def test_literal_examples_and_non_owner_booleans_never_authorize_merge(self):
        for instruction in ['Create a PR. The documentation example is `merge=true`.',
                            'Create a PR. Example: ``merge=true``.',
                            'Create a PR.\n~~~text\nmerge=true\n~~~',
                            'Create a PR.\n~~~text\nmerge=true',
                            'Create a PR.\n~~~~text\n~~~\nmerge=true',
                            'Create a PR.\n\n    merge=true',
                            'Create a PR.\n\n> Example from the docs\nthen merge',
                            'Проверь ветку. Пример «сольём ветку в develop».',
                            'Проверь ветку, не сливай в `develop`.']:
            with self.subTest(instruction=instruction):
                self.assertFalse(pr.parameters('feature/example',{'instruction':instruction})['authorization']['merge'])
        untrusted=pr.parameters('feature/example',{'instruction_origin':'third-party','merge':True})
        self.assertFalse(untrusted['authorization']['merge'])
        self.assertFalse(untrusted['merge_explicit'])
    def test_direct_branch_operands_can_use_inline_code(self):
        result=pr.parameters('feature',{'instruction':'PR from `feature/topic` to `release/candidate` then merge into `release/candidate`'})
        self.assertEqual((result['source_branch'],result['target_branch']),('feature/topic','release/candidate'))
        self.assertTrue(result['merge'])
        self.assertEqual(result['authorization']['target_branch'],'release/candidate')
        russian=pr.parameters('feature',{'instruction':'Проверь изменения, исправь всё найденное и сольём ветку в `release/candidate`.'})
        self.assertTrue(russian['merge'])
        self.assertEqual(russian['target_branch'],'release/candidate')
    def test_retarget_cannot_reuse_old_merge_authority(self):
        params=pr.parameters('feature/example',{'instruction':'then merge into develop'})
        record=pr.new_record(self.snapshot,params)
        self.snapshot.update(target_branch='release/example',base_oid='e'*40,approved=True)
        for retarget in [None,pr.parameters('feature/example',{'target_branch':'release/example','instruction_origin':'third-party'})]:
            with self.subTest(retarget=retarget),self.assertRaisesRegex(pr.ReviewError,'current owner instruction'):
                pr.reconcile(record,self.snapshot,retarget=retarget)
        selected=pr.parameters('feature/example',{'target_branch':'release/example'})
        retargeted=pr.reconcile(record,self.snapshot,retarget=selected)
        self.assertEqual(retargeted['authorization_history'],[record['authorization']])
        ready=pr.reviewed(retargeted,self.snapshot,self.review())
        with self.assertRaisesRegex(pr.ReviewError,'authorization for the current target'):
            pr.merge_gate(ready,self.snapshot)
    def test_merge_gate_requires_direct_owner_authorization_origin(self):
        self.snapshot.update({'approved':True,'approvals_required':False})
        for authorization in [{'pr':False,'merge':True,'origin':'third-party'}, {'pr':True,'merge':True,'origin':'third-party'}]:
            with self.subTest(authorization=authorization):
                self.record['authorization']=authorization
                with self.assertRaisesRegex(pr.ReviewError,'owner authorization'):pr.merge_gate(self.ready(),self.snapshot)
    def test_negatives_quotes_and_third_party_comments_do_not_authorize_merge(self):
        for instruction in ['без merge','не мержить','merge=false','without merge','do not merge','PR "with merge"','Review says «затем смержи»','> with merge','```text\nmerge=true\n```']:
            with self.subTest(instruction=instruction):self.assertFalse(pr.parameters('feature/example',{'instruction':instruction})['merge'])
        self.assertFalse(pr.parameters('feature/example',{'instruction':'with merge','instruction_origin':'third-party'})['authorization']['pr'])
    def test_explicit_conflicts_require_clarification(self):
        for payload in [{'instruction':'with merge без merge'},{'instruction':'merge=true merge=false'},{'instruction':'затем смержи','merge':False},{'instruction':'не сливай','merge':True},{'instruction':'ПР из feature/a в develop','source_branch':'feature/b'}]:
            with self.subTest(payload=payload),self.assertRaises(pr.ReviewError):pr.parameters('feature/current',payload)
        with self.assertRaises(pr.ReviewError):pr.parameters('develop',{})
        with self.assertRaises(pr.ReviewError):pr.parameters('feature/current',{'merge':'false'})
    def test_ready_requires_a_real_provider_pr_identity(self):
        self.snapshot.pop('pr');record=pr.new_record(self.snapshot,self.params);reviewed=pr.reviewed(record,self.snapshot,self.review())
        with self.assertRaisesRegex(pr.ReviewError,'provider PR identity'):pr.ready(reviewed,self.snapshot)
    def test_current_clean_review_stops_at_pr_ready_without_merge(self):
        ready=self.ready();self.assertEqual(ready['status'],'pr-ready');self.assertFalse(ready['review']['independent_approval'])
        with self.assertRaisesRegex(pr.ReviewError,'Merge lacks'):pr.merge_gate(ready,self.snapshot)
    def test_actionable_findings_need_fix_verification_and_a_real_new_review(self):
        finding={'id':'F-1','path':'src/main.py','line':4,'cause':'The consumer sees stale state.','consequence':'The request returns an incorrect value.','severity':'P1'}
        first=pr.reviewed(self.record,self.snapshot,self.review(findings=[finding]))
        with self.assertRaisesRegex(pr.ReviewError,'actionable finding'):pr.ready(first,self.snapshot)
        self.snapshot['head']='c'*40
        with self.assertRaises(pr.ReviewError):pr.ready(first,self.snapshot)
        fixed={**finding,'status':'verified-fixed','verified_head':self.snapshot['head'],'verification_evidence':['regression.json']}
        final=pr.reviewed(first,self.snapshot,self.review(findings=[fixed]));self.assertEqual(pr.ready(final,self.snapshot)['status'],'pr-ready');self.assertEqual(len(final['rounds']),2)
        bad={**fixed,'verified_head':'old'}
        with self.assertRaisesRegex(pr.ReviewError,'current-head'):pr.reviewed(first,self.snapshot,self.review(findings=[bad]))
    def test_new_round_cannot_erase_an_unfixed_finding(self):
        finding={'id':'F-1','path':'src/main.py','line':4,'cause':'The source is stale.','consequence':'The result is wrong.','severity':'P1'}
        previous=pr.reviewed(self.record,self.snapshot,self.review(findings=[finding]));self.snapshot['head']='d'*40
        omitted=pr.reviewed(previous,self.snapshot,self.review())
        with self.assertRaisesRegex(pr.ReviewError,'actionable finding'):pr.ready(omitted,self.snapshot)
    def test_omitted_findings_require_current_verification_after_head_or_base_change(self):
        finding={'id':'F-1','path':'src/main.py','line':4,'cause':'The source is stale.',
                 'consequence':'The result is wrong.','severity':'P1','status':'verified-fixed',
                 'verified_head':self.snapshot['head'],'verification_evidence':['original-review.json']}
        previous=pr.reviewed(self.record,self.snapshot,self.review(findings=[finding]))
        for change in [{'head':'d'*40},{'base_oid':'e'*40}]:
            with self.subTest(change=change),patch.dict(self.snapshot,change):
                omitted=pr.reviewed(previous,self.snapshot,self.review())
                self.assertEqual(omitted['findings']['F-1']['status'],'open')
                self.assertEqual(omitted['rounds'][0]['findings'],[finding])
                with self.assertRaisesRegex(pr.ReviewError,'actionable finding'):pr.ready(omitted,self.snapshot)
    def test_merged_pr_with_new_source_head_does_not_get_reused(self):
        provider=pr.GitHub('/unused','owner/repo');merged={'number':1,'state':'closed','merged_at':'2026-11-03','head':{'ref':'feature/example','sha':'old','repo':{'full_name':'owner/repo'}},'base':{'ref':'develop'}}
        with patch.object(provider,'gh',return_value=[merged]):
            self.assertIsNone(provider.find('feature/example','develop','new'))
            self.assertEqual(provider.find('feature/example','develop','old')['number'],1)
    def test_paginated_provider_arrays_are_flattened_without_dropping_pages(self):
        provider=pr.GitHub('/unused','owner/repo')
        with patch.object(pr.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'[[{"id":1}],[{"id":2}]]','')) as run:
            self.assertEqual(provider.gh('api','endpoint','--paginate'),[{'id':1},{'id':2}]);self.assertIn('--slurp',run.call_args.args[0])
    def test_partial_diff_or_missing_context_never_counts_as_review(self):
        for change in [{'files':[]},{'context_inspected':False},{'discussions_inspected':False},{'checks_inspected':False},{'base_oid':'stale'},{'head':'stale'},{'target_branch':'other'}]:
            with self.subTest(change=change),self.assertRaises(pr.ReviewError):pr.reviewed(self.record,self.snapshot,self.review(**change))
    def test_head_base_target_and_new_discussions_invalidate_ready_evidence(self):
        for change in [{'head':'d'*40},{'base_oid':'e'*40},{'reviews':[{'id':'new-review'}]},{'comments':[{'id':'new-comment'}]}]:
            ready=self.ready();snapshot={**deepcopy(self.snapshot),**change}
            with self.subTest(change=change),self.assertRaises(pr.ReviewError):pr.ready(ready,snapshot)
            self.assertEqual(pr.reconcile(ready,snapshot)['status'],'pr-review-in-progress')
    def test_failed_pending_missing_or_unknown_ci_policy_blocks_readiness(self):
        for change in [{'checks':[{'name':'tests','required':True,'status':'failure'}]},{'checks':[{'name':'tests','required':True,'status':'pending'}]},{'checks_known':False},{'required_checks_missing':['missing']}]:
            self.snapshot.update(change);reviewed=pr.reviewed(self.record,self.snapshot,self.review())
            with self.subTest(change=change),self.assertRaises(pr.ReviewError):pr.ready(reviewed,self.snapshot)
    def test_absent_ci_is_honestly_reported(self):
        self.snapshot['checks']=[];ready=self.ready();self.assertEqual(ready['ci'],'not-configured')
    def test_unresolved_actionable_or_required_discussions_block(self):
        for thread in [{'id':'T1','actionable':True,'resolved':False},{'id':'T2','required':True,'resolved':False}]:
            self.snapshot['threads']=[thread]
            with self.assertRaisesRegex(pr.ReviewError,'discussions'):self.ready()
        self.snapshot['threads']=[{'id':'T1','actionable':True,'resolved':True}];self.assertEqual(self.ready()['status'],'pr-ready')
    def test_merge_requires_external_approval_policy_and_mergeability(self):
        self.record['authorization']['merge']=True
        ready=self.ready()
        with self.assertRaisesRegex(pr.ReviewError,'External approval'):pr.merge_gate(ready,self.snapshot)
        self.snapshot['approved']=True;ready=self.ready();self.assertEqual(pr.merge_gate(ready,self.snapshot)['status'],'pr-ready')
        self.snapshot['mergeable']='CONFLICTING';ready=self.ready()
        with self.assertRaisesRegex(pr.ReviewError,'Merge conflict'):pr.merge_gate(ready,self.snapshot)
        self.snapshot['mergeable']='MERGEABLE';self.snapshot['approvals_known']=False;ready=self.ready()
        with self.assertRaisesRegex(pr.ReviewError,'policy is unknown'):pr.merge_gate(ready,self.snapshot)
    def test_merged_status_requires_provider_commit_and_repeated_observation_is_idempotent(self):
        self.snapshot.update({'state':'MERGED','merge_commit':'f'*40});first=pr.reconcile(self.ready(),self.snapshot);second=pr.reconcile(first,self.snapshot)
        self.assertEqual(first,second);self.assertEqual(second['status'],'merged');self.assertEqual(second['merge_commit'],'f'*40)
        self.snapshot['merge_commit']=None
        with self.assertRaises(pr.ReviewError):pr.reconcile(first,self.snapshot)
    def test_provider_identity_changes_never_reuse_an_unrelated_pr(self):
        record=pr.reconcile(self.record,self.snapshot)
        for change in [{'source_branch':'feature/other'},{'repo_id':'other'},{'remote':'other'},{'remote_id':'other-endpoint'},{'pr':{'id':'unrelated'}}]:
            with self.subTest(change=change),self.assertRaises(pr.ReviewError):pr.reconcile(record,{**self.snapshot,**change})
    def test_operation_receipts_preserve_lost_response_recovery_and_conflict_detection(self):
        request={'commit':'c'*40,'finding':'F-1'};prepared=pr.operation(self.record,'fix-1',request);self.assertEqual(prepared['operations']['fix-1']['state'],'prepared')
        confirmed=pr.operation(prepared,'fix-1',request,{'provider_id':'C1'});self.assertEqual(pr.operation(confirmed,'fix-1',request,{'provider_id':'C1'}),confirmed)
        with self.assertRaises(pr.ReviewError):pr.operation(confirmed,'fix-1',{'commit':'different'})
        with self.assertRaises(pr.ReviewError):pr.operation(confirmed,'fix-1',request,{'provider_id':'other'})
    def test_provider_reuses_existing_pr_instead_of_creating_duplicate(self):
        provider=pr.GitHub('/unused','owner/repo');existing={'number':8,'id':'PR8','head':{'ref':'feature/example','repo':{'full_name':'owner/repo'}},'base':{'ref':'develop'},'state':'open'};calls=[]
        def gh(*args):
            calls.append(args)
            return [existing] if '--paginate' in args else existing
        with patch.object(provider,'gh',side_effect=gh):self.assertEqual(provider.ensure('feature/example','develop','Title','Final description')['number'],8)
        self.assertFalse(any('POST' in args for args in calls));self.assertTrue(any('PATCH' in args for args in calls))
    def test_provider_comment_marker_recovers_a_lost_response_without_duplicate(self):
        provider=pr.GitHub('/unused','owner/repo');comments=[];writes=[]
        def gh(*args):
            if 'GET' in args:return comments
            body=args[-1].removeprefix('body=');item={'id':19,'body':body};comments.append(item);writes.append(args);return item
        with patch.object(provider,'gh',side_effect=gh):
            first=provider.comment(1,'finding-1','Concrete finding');again=provider.comment(1,'finding-1','Concrete finding')
        self.assertEqual(first,again);self.assertEqual(len(writes),1)
    def test_snapshot_reads_all_provider_discussion_pages_and_required_checks(self):
        provider=pr.GitHub('/unused','owner/repo');pages=[]
        raw={'id':'PR1','number':1,'url':'https://example.invalid/1','state':'OPEN','headRefName':'feature/example','baseRefName':'develop','headRefOid':'a'*40,'baseRefOid':'b'*40,'changedFiles':1,'mergeable':'MERGEABLE','reviewDecision':'REVIEW_REQUIRED','statusCheckRollup':[{'name':'tests','conclusion':'SUCCESS'}]}
        def gh(*args):
            if args[0]=='pr':return raw
            if 'graphql' in args:
                cursor=any('cursor=' in value for value in args);pages.append(cursor)
                return {'data':{'repository':{'pullRequest':{'reviewThreads':{'nodes':[{'id':'T2' if cursor else 'T1','isResolved':cursor,'isOutdated':False,'path':'src/main.py','line':4}],'pageInfo':{'hasNextPage':not cursor,'endCursor':'next'}}}}}}
            if any(str(a).endswith('/files') for a in args):return [{'filename':'src/main.py'}]
            return []
        with patch.object(provider,'gh',side_effect=gh):
            snapshot=provider.snapshot(1,self.snapshot,{'checks_known':True,'required_check_names':['tests','missing'],'approvals_known':True,'approvals_required':True})
        self.assertEqual(pages,[False,True]);self.assertEqual(len(snapshot['threads']),2);self.assertEqual(snapshot['required_checks_missing'],['missing']);self.assertFalse(snapshot['approved'])
    def test_provider_merge_uses_expected_head_without_admin_bypass(self):
        provider=pr.GitHub('/unused','owner/repo')
        with patch.object(provider,'gh',return_value={'merged':True,'sha':'merge-sha'}) as gh:provider.merge(1,'a'*40,'squash')
        args=gh.call_args.args;self.assertIn('sha='+'a'*40,args);self.assertNotIn('--admin',args)
    def test_provider_access_loss_is_a_failure_without_a_fake_result(self):
        provider=pr.GitHub('/unused','owner/repo')
        with patch.object(pr.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','private access error')):
            with self.assertRaisesRegex(pr.ReviewError,'access or operation failed'):provider.find('feature/example','develop')
    def test_provider_creation_rechecks_after_a_lost_response(self):
        provider=pr.GitHub('/unused','owner/repo');prs=[];writes=[]
        def gh(*args):
            if 'GET' in args:return prs
            item={'number':3,'head':{'ref':'feature/example','repo':{'full_name':'owner/repo'}},'base':{'ref':'develop'},'state':'open'}
            if 'POST' in args:
                prs.append(item);writes.append(args);raise pr.ReviewError('Synthetic lost response')
            return item
        with patch.object(provider,'gh',side_effect=gh):
            with self.assertRaises(pr.ReviewError):provider.ensure('feature/example','develop','Title','Body')
            result=provider.ensure('feature/example','develop','Title','Body')
        self.assertEqual(result['number'],3);self.assertEqual(len(writes),1)

if __name__=='__main__':unittest.main()
