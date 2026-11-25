import hashlib
import importlib.util
from contextlib import redirect_stdout
import io
import json
import os
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
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
    def test_full_cycle_forwards_the_original_owner_instruction_to_the_pr_gate(self):
        result=pr.parameters('feature/example',{
            'instruction':'проведи задачу по полному циклу skill-tree',
            'instruction_origin':'owner','target_branch':'develop','merge':True,
        })
        self.assertTrue(result['authorization']['merge'])
        self.assertEqual(result['authorization']['target_branch'],'develop')
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
    def test_composed_pr_helper_does_not_treat_full_cycle_bindings_as_review_bindings(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            wrapper=root/'full-cycle'
            manifests=wrapper/'references';manifests.mkdir(parents=True)
            (manifests/'plugin-bindings.json').write_text(json.dumps({
                'operation':'skill-tree-full-cycle','definitions':[{'id':'wrapper-before'}],
            }))
            store=SimpleNamespace(source_root=root)
            with patch.object(pr,'__file__',str(wrapper/'scripts/pr-review-state.py')):
                self.assertIsNone(pr.review_requirement_plan(store,self.snapshot))
                with self.assertRaisesRegex(pr.ReviewError,'must own the PR review operation'):
                    pr.review_requirement_plan(store,self.snapshot,package_root=wrapper)
                registry=root/'.skill-tree/installation/plugins.json'
                registry.parent.mkdir(parents=True)
                binding={'operation':pr.REVIEW_OPERATION,'enabled':False,'plugin_id':'reviewer'}
                registry.write_text(json.dumps({'bindings':[binding]}))
                self.assertIsNone(pr.review_requirement_plan(store,self.snapshot))
                binding['enabled']=True
                registry.write_text(json.dumps({'bindings':[binding]}))
                with self.assertRaisesRegex(pr.ReviewError,'explicitly trusted composed operation package'):
                    pr.review_requirement_plan(store,self.snapshot)
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

class LocalTargetSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        self.root, self.remote = base / 'product', base / 'origin.git'
        self.git(base, 'init', '--bare', str(self.remote))
        self.git(base, 'init', '-b', 'feature/fix', str(self.root))
        self.git(self.root, 'config', 'user.name', 'Fixture')
        self.git(self.root, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.root, 'remote', 'add', 'origin', str(self.remote))
        self.commit('initial', {'product.py': 'old', 'local.txt': 'clean'})
        self.old = self.git(self.root, 'rev-parse', 'HEAD')
        self.commit('provider rewrote the PR into a new target commit', {'product.py': 'fixed'})
        self.integrated = self.git(self.root, 'rev-parse', 'HEAD')
        self.commit('later target update', {'later.txt': 'another PR'})
        self.remote_head = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'push', 'origin', 'HEAD:refs/heads/release/main')
        self.git(self.root, 'reset', '--hard', self.old)
        self.commit('original PR branch', {'product.py': 'fixed'})
        self.source = self.git(self.root, 'rev-parse', 'HEAD')
        self.snapshot = {
            'repo_id': pr.ws.repo_id(self.root), 'remote': 'origin',
            'remote_id': hashlib.sha256(str(self.remote).encode()).hexdigest(),
            'source_branch': 'feature/fix', 'target_branch': 'release/main',
            'head': self.source, 'base_oid': self.old, 'state': 'MERGED',
            'merge_commit': self.integrated, 'pr': {'id': 'PR_fixture', 'number': 21},
            'same_repository': False,
        }
        self.request = base / 'request.json'

    def git(self, root, *args):
        return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE, text=True).strip()

    def commit(self, message, files):
        for name, contents in files.items():
            (self.root / name).write_text(contents)
        self.git(self.root, 'add', *files)
        self.git(self.root, 'commit', '-m', message)

    def invoke(self, command, *, profile_authorization=None, **changes):
        request = {'snapshot': {**self.snapshot, **changes}, 'target_branch': 'release/main'}
        if profile_authorization is not None:
            request['profile_authorization'] = profile_authorization
        self.request.write_text(json.dumps(request))
        result = subprocess.run(
            ['python3', str(CORE/'common/scripts/pr-review-state.py'), command, str(self.root), '--input', str(self.request)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def profile_delivery(self, installer=CORE / 'bin/install.js'):
        self.git(self.root, 'switch', '--detach', self.remote_head)
        self.commit('Establish the owned input baseline', {
            'package.json': '{"name":"profile-fixture","description":"Before"}\n'})
        baseline = self.git(self.root, 'rev-parse', 'HEAD')
        self.commit('Edit package description', {
            'package.json': '{"name":"profile-fixture","description":"After"}\n'})
        self.remote_head = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'push', 'origin', 'HEAD:refs/heads/release/main')
        self.git(self.root, 'switch', '-c', 'release/main', baseline)
        subprocess.run(['node', str(installer), '--target', str(self.root),
                        '--only', 'codex', '--flavor', 'general', '--skills', 'skill-tree-pr-review-cycle'],
                       check=True, capture_output=True, text=True, timeout=30)
        profile = self.root / '.skill-tree/installation/profile.json'
        before = profile.read_bytes()
        record = self.invoke('init')
        self.assertEqual(profile.read_bytes(), before)
        prerequisite = record['local_target_sync']['profile_prerequisite']
        authorization = {'origin': 'owner', 'permission': 'refresh-compatible-profile',
                         'publication_id': record['publication_id'], 'repo_id': record['identity']['repo_id'],
                         'merge_commit': record['merge_commit'],
                         **{key: prerequisite[key] for key in
                            ('target_ref', 'target_head', 'target_checkout', 'profile_sha256')}}
        return record, profile, before, authorization

    def profile_maintenance(self, record, authorization, *,
                            helper=CORE / 'common/scripts/pr-review-state.py', expected_code=0):
        self.request.write_text(json.dumps({'profile_authorization': authorization}))
        result = subprocess.run(
            ['python3', str(helper), 'profile-maintenance', str(self.root),
             '--input', str(self.request), '--publication-id', record['publication_id']],
            capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, expected_code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_verified_profile_maintenance_reconciles_without_reactivation(self):
        legacy = self.root.parent / 'previous-core'
        for directory in ('bin', 'lib', 'common', 'config', 'templates', 'domains', 'src'):
            shutil.copytree(CORE / directory, legacy / directory)
        shutil.copytree(CORE / 'tests/fixtures/director', legacy / 'tests/fixtures/director')
        library = legacy / 'lib/installation.js'
        library.write_text(library.read_text().replace(',maintainDeliveredProfile,', ','))
        record, profile, before, authorization = self.profile_delivery(legacy / 'bin/install.js')
        original_source = json.loads(before)['source_digests']
        self.assertNotEqual(original_source['lib/installation.js'],
                            hashlib.sha256((CORE / 'lib/installation.js').read_bytes()).hexdigest())
        ungranted = self.profile_maintenance(record, None, expected_code=2)
        self.assertIn('explicit owner instruction', ungranted['error'])
        self.assertEqual(profile.read_bytes(), before)
        actor = self.root.parent / 'acting-core'
        actor.mkdir()
        subprocess.run(['node', str(CORE / 'bin/install.js'), '--target', str(actor), '--only', 'codex',
                        '--flavor', 'general', '--skills', 'skill-tree-pr-review-cycle'],
                       check=True, capture_output=True, text=True, timeout=30)
        helper = actor / '.agents/skills/skill-tree-pr-review-cycle/scripts/pr-review-state.py'
        result = self.profile_maintenance(record, authorization, helper=helper)
        self.assertEqual(result['profile_maintenance']['status'], 'restored', result['profile_maintenance'])
        self.assertTrue(result['order_completed'])
        self.assertEqual(result['merge_commit'], record['merge_commit'])
        self.assertEqual(result['local_target_sync']['local_head'], self.remote_head)
        self.assertNotIn('profile_prerequisite', result['local_target_sync'])
        after = profile.read_bytes()
        self.assertNotEqual(after, before)
        self.assertEqual(json.loads(after)['source_digests'], original_source)
        self.assertEqual(result['profile_maintenance']['plan']['after']['profile_sha256'],
                         hashlib.sha256(after).hexdigest())
        carrier = (self.root / '.skill-tree/history/publications'
                   / ('pub-' + record['publication_id'] + '.json'))
        retained = json.loads(carrier.read_bytes())
        retained['profile_maintenance']['status'] = 'prepared'
        carrier.write_text(json.dumps(retained))
        generation = profile.stat().st_ino
        replay = self.profile_maintenance(record, None, helper=helper)
        self.assertEqual(replay['profile_maintenance']['status'], 'reconciled')
        self.assertEqual(profile.read_bytes(), after)
        self.assertEqual(profile.stat().st_ino, generation)
        self.assertEqual(self.invoke('observe')['profile_maintenance'], replay['profile_maintenance'])

    def test_profile_maintenance_preserves_delivery_when_activation_is_blocked(self):
        record, profile, before, authorization = self.profile_delivery()
        branch_before = self.git(self.root, 'rev-parse', 'HEAD')
        journal = profile.parent / '.journal.json'
        journal.write_text('{"fixture":"interrupted"}')
        blocked = self.profile_maintenance(record, authorization)
        self.assertEqual(blocked['profile_maintenance']['status'], 'retryable')
        self.assertIn('recovery', blocked['profile_maintenance']['reason'])
        self.assertTrue(blocked['order_completed'])
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(journal.read_text(), '{"fixture":"interrupted"}')
        journal.unlink()

        state = self.root / '.skill-tree/documents/future.json'
        state.parent.mkdir(exist_ok=True)
        original = {'format': 'skill-tree-future', 'schema': 2, 'tasks': [], 'task_progress': {},
                    'active_run': {'id': 'unrelated-fixture', 'phase': 'blocked', 'stop_reason': 'Waiting'}}
        state.write_text(json.dumps(original))
        busy = self.profile_maintenance(record, authorization)
        self.assertIn('Unfinished canonical work', busy['profile_maintenance']['reason'])
        self.assertEqual(json.loads(state.read_bytes()), original)
        self.assertEqual(profile.read_bytes(), before)
        state.unlink()

        self.commit('Target advances beyond the grant', {'later.txt': 'new contents'})
        stale = self.profile_maintenance(record, authorization)
        self.assertEqual(stale['profile_maintenance']['status'], 'retryable')
        self.assertEqual(stale['local_target_sync']['local_head'], branch_before)
        self.assertEqual(stale['merge_commit'], self.integrated)
        self.assertTrue(stale['order_completed'])
        self.assertEqual(profile.read_bytes(), before)

    def test_observation_continues_profile_maintenance_with_exact_grant(self):
        record, profile, before, authorization = self.profile_delivery()
        ordinary = self.invoke('observe')
        self.assertEqual(ordinary['local_target_sync'], record['local_target_sync'])
        self.assertNotIn('profile_maintenance', ordinary)
        self.assertEqual(profile.read_bytes(), before)

        unrelated = {**authorization, 'merge_commit': 'a' * len(self.integrated)}
        rejected = self.invoke('observe', profile_authorization=unrelated)
        self.assertIn('differs from the exact verified delivery', rejected['profile_maintenance_error'])
        self.assertTrue(rejected['order_completed'])
        self.assertEqual(profile.read_bytes(), before)

        self.request.write_text(json.dumps({'snapshot': self.snapshot, 'profile_authorization': authorization}))
        restore = pr.restore_delivery_profile
        def under_writer_contention(*args):
            writer = self.root / '.skill-tree/.writer-lock'
            writer.touch()
            try:
                return restore(*args)
            finally:
                writer.unlink()
        output = io.StringIO()
        with patch.object(pr, 'restore_delivery_profile', side_effect=under_writer_contention), redirect_stdout(output):
            self.assertEqual(pr.main(['observe', str(self.root), '--input', str(self.request)]), 0)
        contended = json.loads(output.getvalue())
        self.assertTrue(contended['order_completed'])
        self.assertIn('Writer lock exists', contended['profile_maintenance_error'])
        self.assertEqual(profile.read_bytes(), before)

        restored = self.invoke('observe', profile_authorization=authorization)
        self.assertEqual(restored['profile_maintenance']['status'], 'restored',
                         restored.get('profile_maintenance_error') or restored['profile_maintenance'])
        self.assertEqual(restored['merge_commit'], record['merge_commit'])
        self.assertNotIn('profile_prerequisite', restored['local_target_sync'])
        self.assertNotEqual(profile.read_bytes(), before)

    def test_fresh_external_integration_creates_exact_target_and_retries_idempotently(self):
        first = self.invoke('init')
        self.assertEqual(first['local_target_sync']['status'], 'synchronized')
        self.assertTrue(first['order_completed'])
        self.assertEqual(first['local_target_sync']['local_head'], self.remote_head)
        self.assertEqual(self.git(self.root, 'rev-parse', 'release/main'), self.remote_head)
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), self.source)
        self.assertEqual(self.invoke('observe')['local_target_sync'], first['local_target_sync'])

    def test_synchronized_target_reports_stale_discovery_input_without_refresh(self):
        self.git(self.root, 'switch', '--detach', self.remote_head)
        self.commit('Add discovery inputs on the merged target', {
            'package.json': '{"name":"profile-fixture"}\n', 'playwright.config.ts': 'export default {};\n'})
        self.remote_head = self.git(self.root, 'rev-parse', 'HEAD')
        self.git(self.root, 'push', 'origin', 'HEAD:refs/heads/release/main')
        self.git(self.root, 'switch', '-c', 'release/main', self.old)
        subprocess.run(['node', str(CORE / 'bin/install.js'), '--target', str(self.root),
                        '--only', 'codex', '--flavor', 'general', '--skills', 'skill-tree-pr-review-cycle',
                        '--with-init'],
                       check=True, capture_output=True, text=True, timeout=30)
        profile = self.root / '.skill-tree/installation/profile.json'
        before = profile.read_bytes()
        self.assertIsNone(json.loads(before)['inputs']['package.json'])
        self.assertNotIn('playwright.config.ts', json.loads(before)['inputs'])
        director = pr.owned_module('profile_fixture_director', CORE / 'common/scripts/director-state.py')
        routes = pr.owned_module('profile_fixture_routes', CORE / 'common/scripts/director-project-routing.py')
        checkout = self.root.resolve()
        project = {'id': 'fixture', 'checkout': str(checkout), 'workspace_checkout': str(checkout),
                   'state': 'available', 'allowed_effects': ['preview']}
        selection = {'operation': 'skill-tree-pr-review-cycle', 'project_id': 'fixture'}
        current = routes.preview(director, checkout, checkout, {}, {}, [project], selection)
        self.assertEqual(current['status'], 'preview')
        self.assertTrue(current['child_skill'])
        self.assertNotIn('profile_prerequisite', current)
        record = self.invoke('init')
        sync = record['local_target_sync']
        self.assertTrue(record['order_completed'])
        self.assertEqual((record['status'], sync['status']), ('merged', 'synchronized'))
        diagnostic = sync.get('profile_prerequisite')
        self.assertIsNotNone(diagnostic, 'Expected a profile-refresh-required prerequisite')
        self.assertEqual(diagnostic['code'], 'profile-refresh-required')
        self.assertEqual(diagnostic['changed_inputs'], ['package.json', 'playwright.config.ts'])
        self.assertEqual(diagnostic['target_head'], self.remote_head)
        self.assertEqual(diagnostic['target_ref'], 'refs/heads/release/main')
        self.assertEqual(diagnostic['recovery_argv'],
                         ['node', '.skill-tree/installation/manager.js', '--refresh-profile'])
        self.assertEqual(profile.read_bytes(), before)
        self.assertEqual(self.invoke('observe')['local_target_sync'], sync)
        stale = routes.preview(director, checkout, checkout, {}, {}, [project], selection)
        self.assertEqual(stale['status'], 'prerequisite')
        self.assertEqual(stale['limitations'], ['profile-refresh-required'])
        self.assertEqual(stale['profile_prerequisite']['changed_inputs'], ['package.json', 'playwright.config.ts'])
        self.assertIsNone(stale['child_skill'])

        pinned = Path(current['child_skill'])
        pinned_before = pinned.read_bytes()
        pinned.write_bytes(pinned_before + b'\nAltered fixture package.\n')
        damaged = self.invoke('observe')
        self.assertTrue(damaged['order_completed'])
        self.assertNotIn('profile_prerequisite', damaged['local_target_sync'])
        self.assertEqual(routes.preview(director, checkout, checkout, {}, {}, [project], selection)['limitations'],
                         ['project-skill-unavailable'])
        pinned.write_bytes(pinned_before)

        bridge = checkout / 'AGENTS.md'
        bridge_before = bridge.read_bytes()
        bridge.write_bytes(b'# Local instructions\n\n' + bridge_before)
        self.assertEqual(self.invoke('observe')['local_target_sync'], sync)
        bridge.write_bytes(bridge_before.replace(b'Flavor: general', b'Flavor: damaged'))
        damaged_bridge = self.invoke('observe')
        self.assertTrue(damaged_bridge['order_completed'])
        self.assertNotIn('profile_prerequisite', damaged_bridge['local_target_sync'])
        self.assertEqual(routes.preview(director, checkout, checkout, {}, {}, [project], selection)['limitations'],
                         ['project-skill-unavailable'])
        bridge.write_bytes(bridge_before)

        unowned = profile.parent / 'source' / 'unowned.txt'
        unowned.write_text('Unexpected maintenance source.\n')
        damaged_bundle = self.invoke('observe')
        self.assertTrue(damaged_bundle['order_completed'])
        self.assertNotIn('profile_prerequisite', damaged_bundle['local_target_sync'])
        self.assertEqual(routes.preview(director, checkout, checkout, {}, {}, [project], selection)['limitations'],
                         ['project-skill-unavailable'])

    def test_profile_input_rejects_named_pipe(self):
        relative = 'pipe.json'
        os.mkfifo(self.root / relative)
        with self.assertRaisesRegex(ValueError, 'regular files'):
            pr._profile_input(self.root.resolve(), relative)

    def test_checked_out_target_preserves_disjoint_staged_and_unstaged_edits(self):
        self.git(self.root, 'switch', '-c', 'release/main', self.old)
        (self.root / 'local.txt').write_text('staged')
        self.git(self.root, 'add', 'local.txt')
        (self.root / 'local.txt').write_text('unstaged')
        (self.root / 'scratch').write_text('untracked')
        before = self.git(self.root, 'status', '--porcelain', '--', 'local.txt', 'scratch')
        self.assertTrue(self.invoke('init')['order_completed'])
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), self.remote_head)
        self.assertEqual(self.git(self.root, 'status', '--porcelain', '--', 'local.txt', 'scratch'), before)
        self.assertEqual(self.git(self.root, 'show', ':local.txt'), 'staged')
        self.assertEqual((self.root / 'local.txt').read_text(), 'unstaged')
        self.assertEqual((self.root / 'scratch').read_text(), 'untracked')

    def test_unoccupied_behind_target_updates_and_ahead_target_preserves_local_commits(self):
        self.git(self.root, 'branch', 'release/main', self.old)
        self.assertTrue(self.invoke('init')['order_completed'])
        self.assertEqual(self.git(self.root, 'rev-parse', 'release/main'), self.remote_head)
        self.git(self.root, 'switch', 'release/main')
        self.commit('local-only change', {'local.txt': 'local'})
        ahead = self.git(self.root, 'rev-parse', 'HEAD')
        result = self.invoke('observe')
        self.assertTrue(result['order_completed'])
        self.assertEqual(result['local_target_sync']['local_head'], ahead)
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), ahead)

    def test_concurrent_checkout_of_unoccupied_target_stops_without_touching_index(self):
        self.git(self.root, 'branch', 'release/main', self.old)
        original = pr.ws.local_git
        def check_out_before_reservation(root, *args, **kwargs):
            if args[:1] == ('fetch',) and '.' in args:
                self.git(self.root, 'switch', 'release/main')
            return original(root, *args, **kwargs)
        publication = {'identity': pr.identity(self.snapshot), 'merge_commit': self.integrated}
        with patch.object(pr.ws, 'local_git', side_effect=check_out_before_reservation):
            result = pr.synchronize_local_target(self.root, publication)
        self.assertEqual(result['status'], 'pending')
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), self.old)
        self.assertEqual(self.git(self.root, 'status', '--porcelain'), '')
        self.assertEqual((self.root / 'product.py').read_text(), 'old')

    def test_collision_remains_pending_and_same_publication_can_retry(self):
        self.git(self.root, 'switch', '-c', 'release/main', self.old)
        (self.root / 'product.py').write_text('local change')
        pending = self.invoke('init')
        self.assertFalse(pending['order_completed'])
        self.assertIn('collision', pending['local_target_sync']['reason'])
        self.assertEqual(self.git(self.root, 'rev-parse', 'HEAD'), self.old)
        self.assertEqual((self.root / 'product.py').read_text(), 'local change')
        self.git(self.root, 'restore', 'product.py')
        self.assertTrue(self.invoke('observe')['order_completed'])

    def test_divergence_keeps_local_commit_and_closed_pr_does_not_sync(self):
        self.git(self.root, 'branch', 'release/main', self.source)
        self.invoke('init', state='OPEN')
        closed = self.invoke('observe', state='CLOSED')
        self.assertNotIn('local_target_sync', closed)
        self.assertEqual(self.git(self.root, 'rev-parse', 'release/main'), self.source)
        result = self.invoke('observe')
        self.assertFalse(result['order_completed'])
        self.assertIn('diverged', result['local_target_sync']['reason'])
        self.assertEqual(self.git(self.root, 'rev-parse', 'release/main'), self.source)


class ProviderCleanupTests(unittest.TestCase):
    def test_cleanup_follows_exact_provider_merge_to_the_live_target(self):
        self.check_provider_cleanup(carry_after_local_review=False)

    def test_cleanup_follows_provider_delivery_after_reviewed_local_handoff(self):
        self.check_provider_cleanup(carry_after_local_review=True)

    def check_provider_cleanup(self, *, carry_after_local_review):
        spec = importlib.util.spec_from_file_location('provider_delivery_fixture', CORE/'tests/test-local-delivery.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        local = fixture.LocalDeliveryTests()
        self.addCleanup(local.doCleanups)
        local.setUp()
        if carry_after_local_review:
            run = local.start_reviewed_controller('next')
            local.accept_scoped_source(local.tid, commit_evidence=True)
            local.finish_reviewed_fixture()
        else:
            task_id = local.task('Deliver through the provider')
            run = local.start(task_id, delivery_authorization={'pr':True,'merge':True})
            local.source = local.location(run)
            local.selected = fixture.wf.Store(local.source, run['id'])
            (local.source/'source.py').write_text('value = 2\n')
            local.accept_source(task_id)
            local.git(local.source, 'add', 'source.py', 'report.json')
            local.git(local.source, 'commit', '-m', 'Provider source result')
            fixture.wf.advance(local.selected)
            fixture.wf.finish(local.selected)

        target = local.base/'target'
        local.git(local.root, 'worktree', 'add', target, 'develop')
        (target/'source.py').write_bytes((local.source/'source.py').read_bytes())
        local.git(target, 'commit', '-am', 'Squashed provider result')
        merge = local.git(target, 'rev-parse', 'HEAD')
        source_head = local.git(local.source, 'rev-parse', 'HEAD')
        snapshot = {
            'repo_id':run['workspace']['repo_id'], 'remote':'origin',
            'remote_id':hashlib.sha256(str(local.remote).encode()).hexdigest(),
            'source_branch':run['workspace']['branch'], 'target_branch':'develop',
            'head':source_head, 'base_oid':run['workspace']['base_commit'], 'changed_files':['source.py'],
            'same_repository':True, 'pr':{'id':'PR_fixture','number':1,'url':'https://example.invalid/pr/1'},
            'state':'OPEN',
        }
        request = local.base/'publication.json'

        def observe(command, **changes):
            request.write_text(json.dumps({'snapshot':{**snapshot, **changes}, 'merge':True}))
            result = subprocess.run(['python3',str(CORE/'common/scripts/pr-review-state.py'),
                command,str(local.root),'--input',str(request)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads(result.stdout)

        observe('init')
        deferred = observe('observe', state='MERGED', merge_commit=merge)
        self.assertEqual(deferred['status'], 'merged')
        self.assertEqual(deferred['local_target_sync']['status'], 'pending')
        pending_run = fixture.wf.Store(local.source, run['id']).load()['active_run']
        self.assertEqual(pending_run['delivery']['status'], 'local-target-sync-pending')
        self.assertFalse(pending_run['delivery']['order_completed'])
        self.assertFalse(fixture.wf.workspaces.delivery_finished(pending_run))
        self.assertEqual(deferred['worktree_cleanup']['status'], 'deferred')
        self.assertTrue(local.source.exists())
        local.git(target, 'push', 'origin', 'develop')
        unverified = observe('observe', state='MERGED', merge_commit=merge, same_repository=False)
        self.assertEqual(unverified['worktree_cleanup']['status'], 'deferred')
        self.assertTrue(local.source.exists())
        request.write_text(json.dumps({'key':'fixture-metadata-only', 'request':{'description':'Retain operation receipt'}}))
        metadata_only = subprocess.run(['python3',str(CORE/'common/scripts/pr-review-state.py'),
            'operation',str(local.root),'--input',str(request),'--publication-id',unverified['publication_id']],
            capture_output=True,text=True,timeout=30)
        self.assertEqual(metadata_only.returncode, 0, metadata_only.stdout + metadata_only.stderr)
        self.assertNotIn('worktree_cleanup', json.loads(metadata_only.stdout))
        removed = observe('observe', state='MERGED', merge_commit=merge)
        self.assertEqual(removed['local_target_sync']['status'], 'synchronized')
        self.assertEqual(removed['local_target_sync']['local_head'], merge)
        self.assertEqual(removed['worktree_cleanup']['status'], 'removed')
        self.assertFalse(local.source.exists())
        self.assertEqual(local.git(local.root, 'rev-parse', run['workspace']['branch']), source_head)
        self.assertTrue(target.exists())

if __name__=='__main__':unittest.main()
