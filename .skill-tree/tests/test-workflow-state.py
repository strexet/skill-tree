import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('workflow_runtime',ROOT/'common/scripts/workflow-state.py');wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)

class WorkflowStateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        docs=self.root/'.skill-tree/documents';docs.mkdir(parents=True);self.store=wf.Store(self.root)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\nFixed headers precede task bodies.\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n\n')
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (self.root/'source.cs').write_text('Repository source evidence.\n')
        (self.root/'test-report.json').write_text('{"fixture":"behavioral-simulation"}')
    def pending(self,title='Main feature',**kwargs):
        return wf.intake(self.store,{'title':title,'description':'Implement the scoped behavior.','expected_behavior':'The selected behavior preserves isolated state.',**kwargs})
    def body(self, criteria=('Preserve isolated state.',)):
        check={'id':'behavior','recipe_id':'static-inspection','criteria':list(criteria),'sources':['source.cs'],'parameters':{},'assertion':'Preserve isolated state.','timing':'immediate'}
        return ('Goal:\n- Preserve isolated state.\n\nTouch:\n- source.cs\n\nValidation:\n```json\n'
                + json.dumps({'checks':[check]}) + '\n```\n\nAcceptance:\n'
                + ''.join('- '+criterion+'\n' for criterion in criteria))
    def multi_criterion_body(self):
        return self.body(('Preserve isolated state.', 'Preserve the recorded evidence.'))
    def promote(self,pending,title=None,**kwargs):
        spec={'title':title or pending['title'],'body':self.body(),'parent_pending_ids':[pending['id']],**kwargs}
        receipt=wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Research confirms scoped readiness.'}},'tasks':[spec]})
        return wf.resolve(wf.parse(self.store.text()),[receipt['created_ids'][0]])[0]
    def main(self,title='Main feature',priority=100):
        p=self.pending(title,priority=priority);p['title']=title;return self.promote(p)
    def complete(self,task):
        wf.begin_task(self.store,{'task_id':task['id']})
        attempt=wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
        wf.record_check(self.store,{'task_id':task['id'],'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','classification':'executed-control','actual_lane':'static','environment_identity':attempt['environment_identity'],'assertions':[{'assertion':'Preserve isolated state.','result':'pass'}],'cleanup':'No product process was launched.','evidence':['test-report.json']})
        wf.mark_implemented(self.store,{'task_id':task['id']})
        return wf.complete(self.store,{'task_id':task['id'],'outcome':'The scoped behavior preserves isolated state.','acceptance':[{'criterion':'Preserve isolated state.','result':'pass','evidence':['test-report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.cs'])})
    def test_scoped_task_commit_excludes_staged_and_other_worktree_changes(self):
        git, task = self.git_task_fixture()
        (self.root/'other.txt').write_text('staged owner edit\n')
        git('add', 'other.txt')
        (self.root/'side.txt').write_text('untracked owner edit\n')
        before = git('rev-parse', 'HEAD')
        payload = self.checked_git_completion(task,real_review=True)
        result = wf.complete(self.store, payload)
        commit, = result['commits']
        self.assertEqual(git('rev-parse', 'HEAD'), commit)
        self.assertEqual(git('rev-parse', 'HEAD^'), before)
        self.assertEqual(git('diff-tree', '--no-commit-id', '--name-only', '-r', commit), 'source.cs')
        self.assertEqual(git('diff', '--cached', '--name-only'), 'other.txt')
        self.assertEqual((self.root/'side.txt').read_text(), 'untracked owner edit\n')
        self.assertEqual(wf.complete(self.store, payload)['id'], result['id'])
        self.assertEqual(git('rev-list', '--count', before+'..HEAD'), '1')

    def test_permuted_completion_stores_specification_order_and_preserves_scoped_replay(self):
        git, task = self.git_task_fixture(body=self.multi_criterion_body())
        payload = self.checked_git_completion(task, real_review=True)
        expected = wf.acceptance_criteria(task)
        (self.root/'second-report.json').write_text('Supplemental evidence for the second criterion.\n')
        payload['acceptance'][1]['evidence'].append('second-report.json')
        payload['acceptance'].reverse()
        repeated = {**payload, 'acceptance': [payload['acceptance'][0]] * 2}
        with self.assertRaisesRegex(wf.WorkflowError, 'cover exactly'):
            wf.complete(self.store, repeated)
        outcome = wf.complete(self.store, payload)

        self.assertEqual([entry['criterion'] for entry in outcome['acceptance']], expected)
        self.assertEqual([item['path'] for item in outcome['acceptance'][0]['evidence']], ['test-report.json'])
        self.assertEqual([item['path'] for item in outcome['acceptance'][1]['evidence']],
                         ['test-report.json', 'second-report.json'])
        self.assertEqual(wf.task_signature(wf.validation_task(self.store, task['id'])), wf.task_signature(task))
        self.assertEqual(wf.complete(self.store, payload), outcome)
        different_request = {**payload, 'acceptance': list(reversed(payload['acceptance']))}
        with self.assertRaisesRegex(wf.WorkflowError, 'different request'):
            wf.complete(self.store, different_request)
        self.assertEqual(git('rev-parse', 'HEAD'), outcome['commits'][0])

    def test_scoped_task_commit_recovers_git_success_without_outcome(self):
        git, task = self.git_task_fixture()
        payload = self.checked_git_completion(task)
        original = self.store.save
        def fail_outcome(text, state, *args, **kwargs):
            if len(args) and '.skill-tree/history/task-outcomes.jsonl' in args[0]:
                raise OSError('Fixture simulates lost final metadata write')
            return original(text, state, *args, **kwargs)
        with patch.object(self.store, 'save', side_effect=fail_outcome), self.assertRaisesRegex(OSError, 'lost final'):
            wf.complete(self.store, payload)
        first = git('rev-parse', 'HEAD')
        self.assertTrue(wf.resolve(wf.parse(self.store.text()), [task['id']]))
        (self.root/'other.txt').write_text('post-commit owner edit\n')
        git('add', 'other.txt')
        self.assertEqual(wf.complete(self.store, payload)['commits'], [first])
        self.assertEqual(git('rev-parse', 'HEAD'), first)
        self.assertEqual(git('diff', '--cached', '--name-only'), 'other.txt')

    def test_scoped_task_commit_rejects_owned_dirty_overlap_before_write(self):
        git, task = self.git_task_fixture(dirty_source=True)
        before = git('rev-parse', 'HEAD')
        (self.root/'source.cs').write_text('Mixed owner and implementation content.\n')
        with self.assertRaisesRegex(wf.workspaces.RunError, 'overlap'):
            wf.mark_implemented(self.store, {'task_id':task['id'],'changed_files':['source.cs']})
        self.assertEqual(git('rev-parse', 'HEAD'), before)

    def test_scoped_task_commit_rejects_an_uncommitted_required_source(self):
        git, task = self.git_task_fixture()
        payload = self.checked_git_completion(task)
        parent = git('rev-parse','HEAD')
        (self.root/'other.txt').write_text('Uncommitted validation input.\n')
        payload['source_fingerprints'].update(wf.fingerprints(self.store,['other.txt']))
        with self.assertRaisesRegex(wf.workspaces.RunError,'changed validation input'):
            wf.complete(self.store,payload)
        self.assertEqual(git('rev-parse','HEAD'),parent)

    def test_scoped_task_commit_rejects_an_ignored_required_source(self):
        git,task=self.git_task_fixture()
        payload=self.checked_git_completion(task)
        parent=git('rev-parse','HEAD')
        (self.root/'.git/info/exclude').write_text('ignored-input.txt\n')
        (self.root/'ignored-input.txt').write_text('Ignored local validation input.\n')
        payload['source_fingerprints'].update(wf.fingerprints(self.store,['ignored-input.txt']))
        with self.assertRaisesRegex(wf.workspaces.RunError,'changed validation input'):
            wf.complete(self.store,payload)
        self.assertEqual(git('rev-parse','HEAD'),parent)

    def test_scoped_task_commit_sealing_does_not_execute_a_git_hook(self):
        git, task = self.git_task_fixture()
        hook=self.root/'.git/hooks/post-index-change'
        hook.write_text('#!/bin/sh\nprintf hook-fired > hook-observation\n')
        hook.chmod(0o700)
        (self.root/'source.cs').write_text('Reviewed replacement.\n')
        with self.assertRaisesRegex(wf.workspaces.RunError,'executable Git hook'):
            wf.mark_implemented(self.store,{'task_id':task['id'],'changed_files':['source.cs']})
        self.assertFalse((self.root/'hook-observation').exists())

    def test_scoped_task_commit_cannot_resume_on_another_checkout_branch(self):
        git,task=self.git_task_fixture()
        git('switch','-c','different-branch')
        with self.assertRaisesRegex(wf.workspaces.RunError,'checkout, branch or original head changed'):
            wf.begin_task(self.store,{'task_id':task['id'],'implementation_operation':'implement-next'})
        self.assertEqual(git('branch','--show-current'),'different-branch')

    def assert_validation_alias_rejected(self, alias, stored_input='other.txt'):
        git,task=self.git_task_fixture(validation_alias=alias,stored_input=stored_input)
        parent=git('rev-parse','HEAD')
        (self.root/stored_input).write_text('Dirty bytes passed to the required check.\n')
        payload=self.checked_git_completion(task,real_review=True)
        with self.assertRaisesRegex(wf.workspaces.RunError,'changed validation input'):
            wf.complete(self.store,payload)
        self.assertEqual(git('rev-parse','HEAD'),parent)

    def test_scoped_task_commit_rejects_a_lexical_validation_alias(self):
        self.assert_validation_alias_rejected('./other.txt')

    def test_scoped_task_commit_rejects_a_symlink_validation_alias(self):
        self.assert_validation_alias_rejected('validation-input.cs')

    def test_scoped_task_commit_rejects_a_case_variant_validation_alias(self):
        probe=self.root/'case-probe'
        probe.touch()
        try:
            if not (self.root/'CASE-PROBE').exists():
                self.skipTest('The worktree filesystem is case sensitive')
        finally:
            probe.unlink()
        self.assert_validation_alias_rejected('Other.txt')

    def test_scoped_task_commit_rejects_a_unicode_validation_alias(self):
        stored_input='café.txt'
        alias=unicodedata.normalize('NFD',stored_input)
        probe=self.root/stored_input
        probe.touch()
        try:
            if not (self.root/alias).exists():
                self.skipTest('The worktree filesystem distinguishes Unicode normalization forms')
        finally:
            probe.unlink()
        self.assert_validation_alias_rejected(alias,stored_input=stored_input)

    def test_scoped_task_commit_rejects_a_hidden_intermediate_validation_link(self):
        git,task=self.git_task_fixture(validation_alias='validation-chain.cs')
        parent=git('rev-parse','HEAD')
        git('update-index','--assume-unchanged','intermediate.cs')
        middle=self.root/'intermediate.cs'
        middle.unlink()
        middle.symlink_to('alternate.txt')
        payload=self.checked_git_completion(task,real_review=True)
        with self.assertRaisesRegex(wf.workspaces.RunError,'visible in the checked-out Git index'):
            wf.complete(self.store,payload)
        self.assertEqual(git('rev-parse','HEAD'),parent)

    def git_task_fixture(self, dirty_source=False, validation_alias=None, stored_input='other.txt', body=None):
        import subprocess
        def git(*args):
            result=subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True)
            return result.stdout.strip()
        git('init','-b','main')
        git('config','user.name','Scoped Commit Fixture')
        git('config','user.email','fixture@example.invalid')
        git('config','commit.gpgSign','false')
        (self.root/stored_input).write_text('owner baseline\n')
        git('add','source.cs',stored_input)
        if validation_alias=='validation-input.cs':
            (self.root/validation_alias).symlink_to(stored_input)
            git('add',validation_alias)
        if validation_alias=='validation-chain.cs':
            (self.root/'alternate.txt').write_text('Another committed input.\n')
            (self.root/'intermediate.cs').symlink_to(stored_input)
            (self.root/validation_alias).symlink_to('intermediate.cs')
            git('add',validation_alias,'intermediate.cs','alternate.txt')
        git('commit','-m','Initial fixture')
        if validation_alias:
            title='Scoped commit task'
            body=self.body().replace('"sources": ["source.cs"]','"sources": '+json.dumps(['source.cs',validation_alias]))
            task=self.promote(self.pending(title),title,body=body)
        elif body is not None:
            title='Scoped commit task'
            task=self.promote(self.pending(title),title,body=body)
        else:
            task=self.main('Scoped commit task')
        if dirty_source:
            (self.root/'source.cs').write_text('Unrelated source edit.\n')
        wf.begin_task(self.store,{'task_id':task['id'],'implementation_operation':'implement-next'})
        return git, task

    def checked_git_completion(self,task,*,real_review=False):
        (self.root/'source.cs').write_text('Accepted task implementation.\n')
        info=wf.mark_implemented(self.store,{'task_id':task['id'],'changed_files':['source.cs']})
        attempt=wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
        wf.record_check(self.store,{'task_id':task['id'],'check_id':'behavior','attempt_id':attempt['attempt_id'],
            'result':'pass','classification':'executed-control','actual_lane':'static',
            'environment_identity':attempt['environment_identity'],
            'assertions':[{'assertion':'Preserve isolated state.','result':'pass'}],
            'cleanup':'No product process was launched.','evidence':['test-report.json']})
        if real_review:
            review_id=self.git_task_review(task,info['git_review_identity'])
        else:
            review_id=wf.identity('DO')
            review={'orchestration_hash':'a'*64}
            patcher=patch.object(wf,'verified_implementation_review',return_value=review)
            patcher.start()
            self.addCleanup(patcher.stop)
        return {'task_id':task['id'],'outcome':'The scoped behavior preserves isolated state.',
            'acceptance':[{'criterion':criterion,'result':'pass','evidence':['test-report.json']}
                          for criterion in wf.acceptance_criteria(task)],
            'source_fingerprints':wf.fingerprints(self.store,['source.cs']),'review_id':review_id}

    def git_task_review(self,task,identity):
        store=self.store
        source=wf.file_hash(store.future)
        actor={'id':'fixture-owner','context_id':'fixture-owner-context'}
        context={'kind':'task','id':'fixture-task-scope','task_ids':[task['id']],
            'semantic_fingerprint':wf.digest(task['body'].encode()),'content_fingerprint':wf.digest(task['body'].encode())}
        authority={'id':'fixture-grant','revision':1,'context_id':context['id'],
            'allowed_kinds':['specification-acceptance'],'constraints':['Synthetic local Git qualification only.'],
            'evidence':{'kind':'owner-message','reference':'Scripted test owner grant.'}}
        frame=wf.orchestration_action(store,'orchestration-start',{'request_id':'fixture-scope-'+task['id'],
            'context':context,'authority':authority,'executor':{'id':'fixture-executor','context_id':'fixture-executor-context'},
            'mode':'manual','capabilities':{'independent_actors':False},'expected_source_hash':source})
        def op(command,**payload):
            nonlocal frame
            frame=wf.orchestration_action(store,'orchestration-'+command,{'orchestration_id':frame['id'],
                'expected_source_hash':source,'expected_orchestration_hash':frame['orchestration_hash'],
                'expected_orchestration_revision':frame['revision'],**payload})
            return frame
        def next_action():
            return wf.orchestration_action(store,'orchestration-next',{'orchestration_id':frame['id']})
        op('research',reference='Inspected the disposable Git fixture.')
        op('plan',plan_digest=wf.digest(b'fixture git plan'),required_checks=['behavior'],reference='Accept the scoped fixture tree.')
        op('question',purpose='plan',question={'id':'fixture-plan','kind':'specification-acceptance','significance':'routine',
            'text':'Accept the scoped fixture plan?','options':[{'id':'accept','text':'Accept the plan.'},{'id':'revise','text':'Revise the plan.'}],
            'recommendation':'accept'})
        pending=next_action()
        op('prepare-actor',input_digest=pending['input_digest'],expected_decision_hash=pending['decision_hash'],actor=actor)
        waiting=next_action()
        op('record-actor',attempt_id=waiting['attempt_id'],input_digest=waiting['input_digest'],
            expected_decision_hash=waiting['decision_hash'],result={'status':'answered','answer':'accept','rationale':'The scripted fixture plan is accepted.'},
            evidence={'kind':'submitted-answer','reference':'Scripted fixture answer.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        decision=op('accept-decision')
        op('accept-plan',decision_receipt=decision['acceptance'])
        op('implement',identity=identity,reference='Sealed the exact Git candidate.')
        op('checks',identity=identity,results=[{'id':'behavior','status':'passed','reference':'test-report.json'}])
        op('review',identity=identity,review_id='fixture-git-candidate',findings=[],reference='Inspected the disposable scoped candidate.')
        return frame['id']

    def test_scoped_task_commit_rejects_a_ready_review_after_task_revision(self):
        git,task=self.git_task_fixture()
        payload=self.checked_git_completion(task,real_review=True)
        original=git('rev-parse','HEAD')
        text=self.store.text()
        body=wf.resolve(wf.parse(text),[task['id']])[0]['body']
        changed=body.replace('Goal:\n- Preserve isolated state.', 'Goal:\n- Preserve updated isolated state.',1)
        with self.store.lock():
            self.store.save(text.replace(body,changed,1),self.store.load(text))
        with self.assertRaisesRegex(wf.WorkflowError,'current clean implementation review'):
            wf.complete(self.store,payload)
        self.assertEqual(git('rev-parse','HEAD'),original)

    def test_intake_priority_ids_and_minimal_index(self):
        a=self.pending('Normal');b=self.pending('Low',low_priority=True)
        self.assertEqual((a['priority'],b['priority']),(100,25));self.assertTrue(wf.valid_id(a['id'],'P'))
        self.assertNotIn('body',self.store.load()['tasks'][0]);self.assertEqual(self.store.load()['tasks'][0]['id'],a['id'])
    def test_duplicate_intake_and_stale_hash_leave_files_unchanged(self):
        self.pending();before=self.store.future.read_bytes()
        with self.assertRaises(wf.WorkflowError):self.pending()
        with self.assertRaises(wf.WorkflowError):self.pending('Other',expected_source_hash='outdated')
        self.assertEqual(before,self.store.future.read_bytes())
    def test_targeted_processing_never_consumes_unselected_work(self):
        a=self.pending('Chosen');b=self.pending('Unselected');self.promote(a,'Chosen task')
        self.assertEqual([t['id'] for t in wf.parse(self.store.text()) if t['queue']=='Pending Queue'],[b['id']])
    def test_process_rejects_entire_invalid_selection_atomically(self):
        a=self.pending();before=self.store.future.read_bytes()
        with self.assertRaises(wf.WorkflowError):wf.process(self.store,{'selectors':[a['id'],'Missing task'],'dispositions':{}})
        self.assertEqual(before,self.store.future.read_bytes())
    def test_force_process_cli_verifies_twice_using_the_linked_develop_queue(self):
        chosen = self.pending('Chosen')
        kept = self.pending('Kept')
        other = self.pending('Unrelated')

        def git(*args):
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

        git('init', '-b', 'main')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.com',
            'commit', '--allow-empty', '-m', 'Create canonical queue fixture')
        wf.workspaces.setup(self.store, {})
        linked = self.root/'linked'
        git('worktree', 'add', '-b', 'develop', str(linked))
        stale_copy = linked/'.skill-tree/documents/future.md'
        stale_copy.parent.mkdir(parents=True)
        stale_copy.write_text('Noncanonical queue copy.\n')
        self.store.future.write_bytes(self.store.future.read_bytes().replace(b'\n', b'\r\n'))
        proposal_file = self.root/'proposal.json'
        preview_file = self.root/'preview.json'
        receipt_file = self.root/'receipt.json'
        proposal = {'selectors':[chosen['id'], kept['id']],
                    'expected_source_hash':wf.file_hash(self.store.future),
                    'dispositions':{chosen['id']:{'status':'promoted','reason':'Start useful work.'},
                                    kept['id']:{'status':'retained','reason':'An owner choice is pending.'}},
                    'tasks':[self.spec(chosen, 'Prepare the example', 'example', ['@inputs']),
                             self.spec(chosen, 'Identify the inputs', 'inputs')]}
        proposal_file.write_text(json.dumps(proposal))
        def queue_bytes():
            return self.store.future.read_bytes(), self.store.state.read_bytes(), stale_copy.read_bytes()

        def command(name, *args, expected=0):
            result = subprocess.run([sys.executable, str(ROOT/'skills/general/skill-tree-force-process/scripts/workflow-state.py'),
                name, str(linked), '--input', str(proposal_file), *args], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            return result.stdout

        before = queue_bytes()
        preview_file.write_text(command('force-process-preview'))
        self.assertEqual(queue_bytes(), before)
        preview = json.loads(preview_file.read_text())
        self.assertEqual(preview['canonical_queue'], str(self.store.future))
        self.assertEqual(preview['source_hash'], wf.digest(before[0]))
        self.assertNotIn(other['id'], preview['changes'])
        receipt_file.write_text(command('process', '--standalone'))
        receipt = json.loads(receipt_file.read_text())
        self.store.future.write_bytes(self.store.future.read_bytes().replace(b'\n', b'\r\n'))
        post = queue_bytes()
        self.assertNotEqual(post[:2], before[:2])
        self.assertEqual(post[2], before[2])
        preview_hash = wf.file_hash(preview_file)
        flags = ('--preview', str(preview_file), '--receipt', str(receipt_file),
                 '--expected-preview-sha256', preview_hash)
        first = command('force-process-verify', *flags)
        self.assertEqual(queue_bytes(), post)
        self.assertEqual(command('force-process-verify', *flags), first)
        self.assertEqual(queue_bytes(), post)
        verified = json.loads(first)
        self.assertEqual(verified['processing_id'], receipt['id'])
        self.assertEqual(verified['receipt_sha256'], wf.file_hash(receipt_file))
        self.assertTrue(verified['processing_id_observed_in_tasks'])
        self.assertIn(kept['id'], {row['id'] for row in wf.parse(self.store.text())})
        self.assertIn(other['id'], {row['id'] for row in wf.parse(self.store.text())})

        original = receipt_file.read_bytes()
        receipt_file.write_text(json.dumps({**receipt, 'id':wf.identity('PR')}))
        self.assertIn('scoped result differs', command('force-process-verify', *flags, expected=2))
        self.assertEqual(queue_bytes(), post)
        receipt_file.write_bytes(original)
        receipt_file.write_text(json.dumps({**receipt, 'clarification_sessions':{receipt['created_ids'][0]:'CL-fixture'}}))
        self.assertIn('plugin-derived clarification', command('force-process-verify', *flags, expected=2))
        self.assertEqual(queue_bytes(), post)
        receipt_file.write_bytes(original)
        proposal_file.write_text(json.dumps(proposal, indent=2))
        self.assertIn('does not match the proposal', command('force-process-verify', *flags, expected=2))
        self.assertEqual(queue_bytes(), post)
        proposal_file.write_text(json.dumps(proposal))

        text = self.store.text()
        with self.store.lock():
            self.store.save(text.replace('Goal:\n- Preserve isolated state.',
                                         'Goal:\n- Preserve changed isolated state.', 1), self.store.load(text))
        drift = queue_bytes()
        self.assertIn('scoped result differs', command('force-process-verify', *flags, expected=2))
        self.assertEqual(queue_bytes(), drift)
        live = {row['id']: row for row in wf.parse(self.store.text())}
        for provisional, actual in zip(preview['provisional_receipt']['created_ids'], receipt['created_ids']):
            preview['changes'][provisional]['content_sha256'] = wf.force_process_contract(live[actual])['content_sha256']
        preview_file.write_text(json.dumps(preview))
        self.assertIn('matching reviewed Preview SHA-256', command('force-process-verify', *flags, expected=2))
        self.assertEqual(queue_bytes(), drift)
        self.assertIn('canonical queue hash', command('force-process-preview', expected=2))
        self.assertEqual(queue_bytes(), drift)

    def test_force_process_verify_checks_reused_tasks_and_resolved_items(self):
        existing = self.main('Existing route')
        reused = self.pending('Reuse the route')
        resolved = self.pending('Resolve a duplicate')
        proposal_file = self.root/'proposal.json'
        preview_file = self.root/'preview.json'
        receipt_file = self.root/'receipt.json'
        proposal = {'selectors':[reused['id'], resolved['id']],
                    'expected_source_hash':wf.file_hash(self.store.future),
                    'dispositions':{reused['id']:{'status':'promoted','reason':'Reuse the existing route.'},
                                    resolved['id']:{'status':'resolved','reason':'No implementation is required.'}},
                    'tasks':[{'key':'existing-route','reuse_id':existing['id'],
                              'parent_pending_ids':[reused['id']]}]}
        proposal_file.write_text(json.dumps(proposal))
        preview = wf.force_process_evidence(self.store, 'force-process-preview', proposal_file, None, None)
        self.assertEqual(preview['provisional_receipt']['created_ids'], [])
        self.assertIsNone(preview['changes'][resolved['id']])
        preview_file.write_text(json.dumps(preview))
        receipt = wf.process(self.store, proposal)
        receipt_file.write_text(json.dumps(receipt))
        verified = wf.force_process_evidence(self.store, 'force-process-verify', proposal_file, preview_file, receipt_file,
                                           wf.file_hash(preview_file))
        self.assertEqual(verified['reused_ids'], [existing['id']])
        self.assertTrue(verified['processing_id_observed_in_tasks'])

    def test_split_and_merge_provenance(self):
        a=self.pending('Split');receipt=wf.process(self.store,{'selectors':[a['id']],'dispositions':{a['id']:{'status':'promoted','reason':'Two bounded units.'}},'tasks':[{'title':title,'body':self.body(),'parent_pending_ids':[a['id']]} for title in ['Unit A','Unit B']]})
        self.assertEqual(len(receipt['created_ids']),2)
        for tid in receipt['created_ids']:self.assertEqual(wf.resolve(wf.parse(self.store.text()),[tid])[0]['parent_pending_ids'],[a['id']])
        b=self.pending('Merge B');c=self.pending('Merge C')
        receipt=wf.process(self.store,{'selectors':[b['id'],c['id']],'dispositions':{p['id']:{'status':'promoted','reason':'One coherent outcome.'} for p in [b,c]},'tasks':[{'title':'Merged outcome','body':self.body(),'parent_pending_ids':[b['id'],c['id']]}]})
        self.assertEqual(set(wf.resolve(wf.parse(self.store.text()),[receipt['created_ids'][0]])[0]['parent_pending_ids']),{b['id'],c['id']})
    def process_specs(self,pending,specs):
        return wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Research confirms bounded implementation units.'}},'tasks':specs})
    def spec(self,pending,title,key,dependencies=()):
        return {'title':title,'key':key,'body':self.body(),'parent_pending_ids':[pending['id']],'depends_on':list(dependencies)}
    def test_split_forward_dependency_resolves_keys_atomically_and_orders_execution(self):
        p=self.pending('Storage scope')
        receipt=self.process_specs(p,[self.spec(p,'Migration','migration',['@storage']),self.spec(p,'Storage schema','storage')])
        tasks=wf.parse(self.store.text());migration=wf.resolve(tasks,[receipt['task_keys']['migration']])[0];schema=wf.resolve(tasks,[receipt['task_keys']['storage']])[0]
        self.assertEqual(migration['depends_on'],[schema['id']]);self.assertEqual(migration['parent_pending_ids'],[p['id']])
        wf.start(self.store,'next',migration['id']);self.assertEqual(wf.next_task(self.store)['task_id'],schema['id'])
    def test_invalid_split_dependency_graph_preserves_queue_index_manifest_and_checkpoint(self):
        self.main();wf.start(self.store,'next');p=self.pending('Split scope')
        before={path:path.read_bytes() for path in self.store.base.rglob('*') if path.is_file()}
        invalid=[
            [self.spec(p,'Unit A','a',['@missing'])],
            [self.spec(p,'Unit A','same'),self.spec(p,'Unit B','same')],
            [self.spec(p,'Unit A','a',['@b']),self.spec(p,'Unit B','b',['@a'])],
            [self.spec(p,'Unit A','a',['@a'])],
            [self.spec(p,'Unit A','a',[wf.identity('T')])],
            [self.spec(p,'Unit A','a',[p['id']])],
        ]
        for specs in invalid:
            with self.subTest(specs=specs):
                with self.assertRaises(wf.WorkflowError):self.process_specs(p,specs)
                self.assertEqual(before,{path:path.read_bytes() for path in self.store.base.rglob('*') if path.is_file()})
    def test_reused_contract_can_depend_on_new_sibling_and_receipt_resolves_both(self):
        parent=self.main();p=self.pending('Related scope')
        receipt=self.process_specs(p,[{'key':'existing','reuse_id':parent['id'],'parent_pending_ids':[p['id']],'depends_on':['@fixture']},self.spec(p,'Fixture','fixture')])
        task=wf.resolve(wf.parse(self.store.text()),[parent['id']])[0]
        self.assertEqual(task['depends_on'],[receipt['task_keys']['fixture']]);self.assertEqual(receipt['task_keys']['existing'],parent['id'])
    def test_reuse_cycle_with_existing_task_is_rejected_before_save(self):
        a=self.main('Unit A');b=self.main('Unit B');p=self.pending('Dependency extension')
        text=wf.rewrite_meta(self.store.text(),a['id'],{'depends_on':[b['id']]});self.store.future.write_text(text)
        before=self.store.future.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'cycle'):
            self.process_specs(p,[{'reuse_id':b['id'],'parent_pending_ids':[p['id']],'depends_on':[a['id']]}])
        self.assertEqual(before,self.store.future.read_bytes())
    def test_completed_dependency_accepts_ledger_but_cancelled_dependency_does_not(self):
        done=self.main('Completed fixture');self.complete(done);p=self.pending('Consumer')
        receipt=self.process_specs(p,[self.spec(p,'Consumer task','consumer',[done['id']])]);self.assertTrue(receipt['created_ids'])
        cancelled=self.main('Cancelled fixture');wf.complete(self.store,{'task_id':cancelled['id'],'disposition':'cancelled','outcome':'The fixture scope is withdrawn.'});p=self.pending('Second consumer')
        with self.assertRaisesRegex(wf.WorkflowError,'Missing required dependency'):self.process_specs(p,[self.spec(p,'Second task','second',[cancelled['id']])])

    def test_explicit_reuse_extends_provenance_without_duplicate_task(self):
        main=self.main();p=self.pending('Compatible clarification')
        result=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Same scope.'}},'tasks':[{'reuse_id':main['id'],'parent_pending_ids':[p['id']]}]})
        self.assertEqual(result['reused_ids'],[main['id']]);self.assertEqual(len([t for t in wf.parse(self.store.text()) if t['queue']=='Prioritized Next Changes']),1)
    def test_nonblocking_processing_is_deferred_after_parent_completion(self):
        main=self.main();wf.start(self.store,'next');p=self.pending('Followup',relation='followup',root_task_id=main['id'],related_task_id=main['id']);self.assertEqual(p['priority'],99)
        self.complete(main)
        with self.assertRaises(wf.WorkflowError):wf.finish(self.store)
        child=self.promote(p,'Followup implementation');self.assertEqual(wf.next_task(self.store)['phase'],'deferred-processing')
        wf.finish(self.store);self.assertIsNone(self.store.load()['active_run']);self.assertEqual(wf.select(wf.parse(self.store.text()))['id'],child['id'])
    def test_required_dependency_cycle_resumes_parent_and_records_outcomes(self):
        main=self.main();wf.start(self.store,'next');blocker=self.pending('Required fixture',relation='blocker',root_task_id=main['id'],related_task_id=main['id']);self.assertEqual(blocker['priority'],101)
        self.assertEqual(wf.next_task(self.store)['phase'],'process-required');child=self.promote(blocker,'Implement fixture')
        self.assertEqual(wf.advance(self.store)['task_id'],child['id'])
        with self.assertRaises(wf.WorkflowError):self.complete(main)
        self.complete(child);self.assertEqual(wf.advance(self.store)['task_id'],main['id']);self.complete(main);summary=wf.finish(self.store)
        self.assertEqual(set(summary['completed_ids']),{main['id'],child['id']});self.assertEqual(len(self.store.outcomes()),2)
    def test_nested_subtasks_are_required(self):
        main=self.main();wf.start(self.store,'next');p=self.pending('Dependency',relation='subtask',root_task_id=main['id'],related_task_id=main['id']);child=self.promote(p,'Dependency task')
        nested=self.pending('Nested work',relation='blocker',root_task_id=main['id'],related_task_id=child['id']);leaf=self.promote(nested,'Leaf task')
        self.assertEqual(wf.advance(self.store)['task_id'],leaf['id']);self.complete(leaf);self.assertEqual(wf.advance(self.store)['task_id'],child['id'])
    def test_implement_all_snapshot_excludes_new_main_and_deduplicates_dependency(self):
        a=self.main('Initial A',100);b=self.main('Initial B',50);run=wf.start(self.store,'all');late=self.main('Late task',1000)
        text=wf.rewrite_meta(self.store.text(),a['id'],{'depends_on':[b['id']]});self.store.future.write_text(text)
        self.assertEqual(wf.advance(self.store)['task_id'],b['id']);self.complete(b);self.assertEqual(wf.advance(self.store)['task_id'],a['id']);self.complete(a);wf.finish(self.store)
        self.assertEqual(run['snapshot'],[a['id'],b['id']]);self.assertEqual(wf.select(wf.parse(self.store.text()))['id'],late['id'])
    def test_missing_root_never_counts_as_completed(self):
        main=self.main();wf.start(self.store,'next');self.store.future.write_text(wf.remove(self.store.text(),{main['id']}))
        with self.assertRaisesRegex(wf.WorkflowError,'Missing task'):wf.next_task(self.store)
    def test_dependency_cycles_stop(self):
        a=self.main('A');b=self.main('B');wf.start(self.store,'next')
        text=wf.rewrite_meta(self.store.text(),a['id'],{'depends_on':[b['id']]});text=wf.rewrite_meta(text,b['id'],{'depends_on':[a['id']]});self.store.future.write_text(text)
        with self.assertRaisesRegex(wf.WorkflowError,'cycle'):wf.next_task(self.store)
    def test_checkpoint_refresh_preserves_state_and_consumed_limits(self):
        self.main();wf.start(self.store,'next',limits={'retry_limit':1,'retry_used':0,'deadline':'2099-01-01T00:00:00+00:00'});wf.checkpoint(self.store,{'validation_consumed':{'retry_used':1},'partial_work':['source.cs']})
        self.pending('Unrelated work');self.assertEqual(self.store.load()['active_run']['limits']['retry_used'],1)
        with self.assertRaises(wf.WorkflowError):wf.checkpoint(self.store,{'validation_consumed':{'retry_used':0}})
        with self.assertRaises(wf.WorkflowError):wf.start(self.store,'next')

    def future_command(self, command, *options):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'common/scripts/workflow-state.py'),
                                 command, str(self.root), *options], capture_output=True, text=True, timeout=20)
        return result.returncode, json.loads(result.stdout)

    def test_future_refresh_preserves_surviving_files_after_loss(self):
        empty_queue = self.store.future.read_bytes()
        self.complete(self.main('Completed control'))
        self.pending('Retained input')
        ledger = self.store.base/'history/task-outcomes.jsonl'
        manifest = self.store.base/'skill-tree.json'
        protected = (self.store.future, self.store.state, ledger, manifest)
        original = {path: path.read_bytes() for path in protected}
        for file, replacement in ((self.store.future, None), (self.store.state, None), (ledger, None),
                                  (self.store.future, empty_queue), (ledger, b'')):
            with self.subTest(file=file.name, absent=replacement is None):
                if replacement is None:
                    file.unlink()
                else:
                    file.write_bytes(replacement)
                surviving = {path: path.read_bytes() for path in protected if path.exists()}
                for command, options in (('refresh', ()), ('manifest', ('--apply',))):
                    status, response = self.future_command(command, *options)
                    self.assertEqual(status, 2, response)
                    self.assertIn(file.relative_to(self.store.root).as_posix(), response['error'])
                    self.assertIn('restore', response['error'].lower())
                    self.assertEqual(surviving, {path: path.read_bytes() for path in protected if path.exists()})
            for protected_file, content in original.items():
                protected_file.write_bytes(content)

    def test_future_refresh_accepts_initialization_and_legitimate_emptying(self):
        status, state = self.future_command('refresh')
        self.assertEqual(status, 0, state)
        self.assertEqual(state['tasks'], [])
        last_task = self.main()
        self.complete(last_task)
        checkpoint = self.store.state.read_bytes()
        ledger = self.store.base/'history/task-outcomes.jsonl'
        outcomes = ledger.read_bytes()
        status, state = self.future_command('refresh')
        self.assertEqual(status, 0, state)
        self.assertEqual(state['tasks'], [])
        self.assertEqual(self.store.state.read_bytes(), checkpoint)
        self.assertEqual(ledger.read_bytes(), outcomes)

    def test_future_loss_reports_the_queue_before_checkpoint_progress(self):
        empty_queue = self.store.future.read_bytes()
        task = self.main()
        wf.start(self.store, 'next', task['id'])
        wf.begin_task(self.store, {'task_id': task['id']})
        self.assertIn(task['id'], self.store.load()['task_progress'])
        prior_hash = wf.file_hash(self.store.future)
        for replacement in (empty_queue, b'', None):
            with self.subTest(replacement=replacement):
                if replacement is None:
                    self.store.future.unlink()
                else:
                    self.store.future.write_bytes(replacement)
                before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
                for options in ((), ('--expected-source-hash', prior_hash)):
                    status, response = self.future_command('refresh', *options)
                    self.assertEqual(status, 2, response)
                    self.assertIn(wf.FUTURE_QUEUE, response['error'])
                    self.assertIn('restore the matching queue', response['error'].lower())
                result = subprocess.run([sys.executable, '-B', str(ROOT/'common/scripts/validate-repository-documentation.py'),
                                         str(self.root)], capture_output=True, text=True, timeout=20)
                diagnostics = json.loads(result.stdout)
                self.assertEqual(result.returncode, 1, diagnostics)
                self.assertTrue(any(wf.FUTURE_QUEUE in issue and 'restore the matching' in issue.lower()
                                    for issue in diagnostics['errors']), diagnostics)
                self.assertEqual(before, {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()})

    def test_future_refresh_uses_legacy_terminal_reference_for_expected_history(self):
        task = self.main()
        wf.start(self.store, 'next', task['id'])
        self.complete(task)
        summary = wf.finish(self.store)
        self.assertEqual(summary['completed_ids'], [task['id']])
        old = json.loads(self.store.state.read_bytes())
        self.assertEqual(old['schema'], 2)
        self.assertIsNone(old['active_run'])
        old.pop('outcome_history_recorded')
        checkpoint = wf.dump(old)
        self.store.state.write_text(checkpoint)
        ledger = self.store.base/'history/task-outcomes.jsonl'
        ledger.unlink()
        manifest = self.store.base/'skill-tree.json'
        navigation = manifest.read_bytes()
        status, response = self.future_command('refresh')
        self.assertEqual(status, 2, response)
        self.assertIn('.skill-tree/history/task-outcomes.jsonl', response['error'])
        self.assertEqual(self.store.state.read_text(), checkpoint)
        self.assertEqual(manifest.read_bytes(), navigation)
        self.assertFalse(ledger.exists())

    def test_future_refresh_protects_unwritten_inputs_at_commit(self):
        self.pending()
        checkpoint = self.store.state.read_bytes()
        manifest = self.store.base/'skill-tree.json'
        navigation = manifest.read_bytes()
        ledger = self.store.base/'history/task-outcomes.jsonl'
        with self.store.lock():
            text = self.store.text()
            state = self.store.load(text)
            original_commit = self.store.commit

            def insert_unrelated_input(writes):
                ledger.parent.mkdir(parents=True, exist_ok=True)
                ledger.write_text('Developer outcome history.\n')
                original_commit(writes)

            with patch.object(self.store, 'commit', side_effect=insert_unrelated_input):
                with self.assertRaisesRegex(wf.WorkflowError, 'Future input changed.*task-outcomes.jsonl'):
                    self.store.save(text, state)
        self.assertEqual(self.store.state.read_bytes(), checkpoint)
        self.assertEqual(manifest.read_bytes(), navigation)
        self.assertEqual(ledger.read_text(), 'Developer outcome history.\n')
    def test_recorded_deadline_is_evidence_not_authorization_gate(self):
        main=self.main();wf.start(self.store,'next',limits={'deadline':'2000-01-01T00:00:00+00:00'})
        self.assertEqual(wf.next_task(self.store)['task_id'],main['id'])
        with self.assertRaises(wf.WorkflowError):wf.checkpoint(self.store,{'limits':{}})
    def test_justified_selected_task_budget_is_enforced(self):
        self.main();wf.start(self.store,'next',limits={'selected_task_budget':{'limit_seconds':100,'used_seconds':0,'rationale':'Bound paid device-lab occupancy.'}})
        wf.checkpoint(self.store,{'task_budget_used_seconds':100})
        with self.assertRaisesRegex(wf.WorkflowError,'Selected-task budget exhausted'):wf.next_task(self.store)
        with self.assertRaisesRegex(wf.WorkflowError,'cannot decrease'):wf.checkpoint(self.store,{'task_budget_used_seconds':99})
    def test_selected_task_budget_requires_rationale(self):
        self.main()
        with self.assertRaisesRegex(wf.WorkflowError,'concrete rationale'):wf.start(self.store,'next',limits={'selected_task_budget':{'limit_seconds':100,'used_seconds':0,'rationale':''}})
    def test_no_progress_cycle_stops_without_breaking_resume(self):
        self.main();wf.start(self.store,'next');wf.record_cycle(self.store);wf.advance(self.store)
        self.assertEqual(wf.record_cycle(self.store)['phase'],'blocked')
    def test_corrupt_state_is_not_reset(self):
        self.store.state.write_text('{"format":"unsupported","tasks":[],"active_run":null}')
        before=self.store.state.read_bytes()
        with self.assertRaises(wf.WorkflowError):self.pending()
        self.assertEqual(before,self.store.state.read_bytes())
    def test_corrupt_run_is_not_reset(self):
        self.store.state.write_text(json.dumps({'format':wf.FORMAT,'tasks':[],'active_run':{'id':'invalid'}}))
        with self.assertRaises(wf.WorkflowError):self.store.load()
    def test_writer_lock_rejects_second_controller(self):
        with self.store.lock():
            with self.assertRaisesRegex(wf.WorkflowError,'Writer lock'):self.pending()
    def test_interrupted_completion_recovers_ledger_before_queue_removal(self):
        task=self.main();original=self.store.replace;calls=[]
        def crash(path,content):
            calls.append(path.name)
            if path==self.store.future:raise OSError('Injected interruption')
            original(path,content)
        with patch.object(self.store,'replace',side_effect=crash):
            with self.assertRaises(OSError):self.complete(task)
        self.assertEqual(self.store.outcomes()[0]['task_id'],task['id']);self.assertIn(task['id'],self.store.text());self.assertTrue((self.store.base/'.transaction.json').exists())
        with self.store.lock():pass
        self.assertNotIn(task['id'],self.store.text());self.assertFalse((self.store.base/'.transaction.json').exists())
    def test_conflicting_interrupted_transaction_does_not_overwrite_changes(self):
        text=self.store.text();journal={'format':'skill-tree-transaction','writes':[{'path':'.skill-tree/documents/future.md','expected_hash':wf.file_hash(self.store.future),'content':text+'\n'}]};(self.store.base/'.transaction.json').write_text(wf.dump(journal));self.store.future.write_text(text+'Developer changes.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'conflicts'):
            with self.store.lock():pass
        self.assertIn('Developer changes.',self.store.text())
    def test_partial_acceptance_or_stale_source_cannot_complete(self):
        task=self.main()
        for payload in [ {'task_id':task['id'],'outcome':'Behavior delivered.','acceptance':[]}, {'task_id':task['id'],'outcome':'Behavior delivered.','acceptance':[{'criterion':'Different criterion','result':'pass','evidence':['report']}],'source_fingerprints':wf.fingerprints(self.store,['source.cs'])}, {'task_id':task['id'],'outcome':'Behavior delivered.','acceptance':[{'criterion':'Preserve isolated state.','result':'pass','evidence':['report']}],'source_fingerprints':{'source.cs':'stale'}} ]:
            with self.assertRaises(wf.WorkflowError):wf.complete(self.store,payload)
        self.assertEqual(self.store.outcomes(),[]);self.assertIn(task['id'],self.store.text())

    def completed_acceptance_fixture(self, *, legacy=True):
        def git(*args):
            subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

        git('init', '-b', 'main')
        git('config', 'user.name', 'Completed Contract Fixture')
        git('config', 'user.email', 'fixture@example.invalid')
        git('config', 'commit.gpgSign', 'false')
        git('add', 'source.cs', '.skill-tree/config/repository.json', 'test-report.json')
        git('commit', '-m', 'Initial fixture')
        git('remote', 'add', 'origin', str(self.root))
        wf.workspaces.setup(self.store, {})
        title = 'Registered acceptance contract'
        task = self.promote(self.pending(title), title, body=self.multi_criterion_body())
        run = wf.start(self.store, 'next', task['id'], workspace={
            'base_branch': 'main', 'local_base': True, 'local_base_authorization': 'Temporary local fixture.'})
        store = wf.Store(self.root, run['id'])
        wf.begin_task(store, {'task_id': task['id']})
        attempt = wf.prepare_check(store, {'task_id': task['id'], 'check_id': 'behavior'})
        wf.record_check(store, {'task_id': task['id'], 'check_id': 'behavior', 'attempt_id': attempt['attempt_id'],
            'result': 'pass', 'classification': 'executed-control', 'actual_lane': 'static',
            'environment_identity': attempt['environment_identity'],
            'assertions': [{'assertion': 'Preserve isolated state.', 'result': 'pass'}],
            'cleanup': 'No product process was launched.', 'evidence': ['test-report.json']})
        wf.mark_implemented(store, {'task_id': task['id']})
        outcome = wf.complete(store, {'task_id': task['id'], 'outcome': 'The scoped contract is accepted.',
            'acceptance': [{'criterion': criterion, 'result': 'pass', 'evidence': ['test-report.json']}
                           for criterion in wf.acceptance_criteria(task)],
            'source_fingerprints': wf.fingerprints(store, ['source.cs'])})
        directory = store.base/'history/run-events'/run['id'].lower()
        path, = (path for path in directory.glob('*.json')
                 if outcome in json.loads(path.read_text())['outcomes'])
        ledger = store.owned(wf.OUTCOME_LEDGER)
        if legacy:
            # Emulate the former writer without changing the original task body or signature.
            outcome['acceptance'].reverse()
            ledger.write_text(json.dumps(outcome, ensure_ascii=False, sort_keys=True)+'\n')
            event = json.loads(path.read_text())
            event['outcomes'] = [outcome]
            path.write_text(wf.dump(event))
        return store, task, ledger, path

    def test_legacy_completed_contract_recovers_applied_event_without_rewriting_history(self):
        store, task, ledger, event = self.completed_acceptance_fixture()
        original = {path: path.read_bytes() for path in (ledger, event)}
        restored = wf.validation_task(store, task['id'])
        self.assertEqual(wf.acceptance_criteria(restored), wf.acceptance_criteria(task))
        self.assertEqual(wf.task_signature(restored), wf.task_signature(task))
        self.assertEqual(wf.advance(store)['phase'], 'deferred-processing')
        finished = wf.finish(store)
        self.assertEqual(finished['id'], store.run_id)
        self.assertEqual(finished['phase'], 'completed')
        self.assertEqual({path: path.read_bytes() for path in original}, original)

    def test_correctly_ordered_completed_contract_does_not_require_event_history(self):
        store, task, ledger, event = self.completed_acceptance_fixture(legacy=False)
        event.unlink()
        original = ledger.read_bytes()
        self.assertEqual(wf.task_signature(wf.validation_task(store, task['id'])), wf.task_signature(task))
        self.assertEqual(wf.finish(store)['phase'], 'completed')
        self.assertEqual(ledger.read_bytes(), original)

    def test_legacy_completed_contract_rejects_missing_or_conflicting_event_evidence(self):
        store, task, ledger, event = self.completed_acceptance_fixture()
        event_bytes, state_bytes, ledger_bytes = (path.read_bytes() for path in (event, store.state, ledger))
        for problem in ('missing', 'symlinked', 'foreign-run', 'foreign-queue', 'unapplied', 'corrupt',
                        'different-outcome', 'duplicate', 'same-signature-tampering'):
            with self.subTest(problem=problem):
                candidate = json.loads(event_bytes)
                state = json.loads(state_bytes)
                registry = state['run_registry']
                duplicate = None
                symlink_target = None
                if problem == 'foreign-run':
                    candidate['run_id'] = wf.identity('WR')
                elif problem == 'foreign-queue':
                    candidate['queue_id'] = wf.identity('Q')
                elif problem == 'unapplied':
                    registry['applied_events'].remove(candidate['id'])
                elif problem == 'different-outcome':
                    candidate['outcomes'][0]['outcome'] = 'A different event outcome.'
                elif problem == 'duplicate':
                    copied = {**candidate, 'id': wf.identity('E'),
                              'sequence': registry['event_sequences'][store.run_id] + 1}
                    duplicate = event.with_name(copied['id'].lower() + '.json')
                    duplicate.write_text(wf.dump(copied))
                    registry['applied_events'].append(copied['id'])
                    registry['event_sequences'][store.run_id] = copied['sequence']
                elif problem == 'same-signature-tampering':
                    change, = candidate['changes']
                    body = change['before']['body'].replace('Goal:\n- Preserve isolated state.',
                                                            'Goal:\n- Preserve the recorded state.')
                    self.assertNotEqual(body, change['before']['body'])
                    self.assertEqual(wf.task_signature({**task, 'body': body}), wf.task_signature(task))
                    change['before']['body'] = body
                store.state.write_text(wf.dump(state))
                if problem == 'missing':
                    event.unlink()
                elif problem == 'symlinked':
                    symlink_target = event.with_suffix('.fixture')
                    event.rename(symlink_target)
                    event.symlink_to(symlink_target.name)
                elif problem == 'corrupt':
                    event.write_text('{')
                else:
                    event.write_text(wf.dump(candidate))
                try:
                    before = {path: path.read_bytes() for path in (ledger, store.state)}
                    event_before = {path.name: path.read_bytes() for path in event.parent.glob('*.json')}
                    with self.assertRaises(wf.WorkflowError):
                        wf.advance(store)
                    self.assertEqual({path: path.read_bytes() for path in before}, before)
                    self.assertEqual({path.name: path.read_bytes() for path in event.parent.glob('*.json')},
                                     event_before)
                finally:
                    if symlink_target is not None:
                        event.unlink()
                        symlink_target.unlink()
                    event.write_bytes(event_bytes)
                    store.state.write_bytes(state_bytes)
                    if duplicate is not None:
                        duplicate.unlink()
        self.assertEqual(ledger.read_bytes(), ledger_bytes)
    def test_audit_freshness_and_scoped_retention_pins(self):
        records=[]
        for i in range(10):records.append(wf.audit(self.store,{'scope':'source','sources':['source.cs'],'findings':[],'checks':[],'coverage_gaps':['Runtime unverified.']}))
        config=wf.manifest(self.store);config['retention']['pins']=[records[0]['id']];self.store.commit({'.skill-tree/skill-tree.json':wf.dump(config)})
        for i in range(2):wf.audit(self.store,{'scope':'source','sources':['source.cs'],'findings':[],'checks':[],'coverage_gaps':[]})
        self.assertEqual(len(list((self.store.base/'history/audits').glob('*.json'))),11);self.assertTrue(any(records[0]['id'].lower() in p.name for p in (self.store.base/'history/audits').glob('*.json')))
        self.assertTrue(wf.manifest(self.store)['latest_audit']['fresh']);(self.root/'source.cs').write_text('Changed source.');self.assertFalse(wf.manifest(self.store)['latest_audit']['fresh'])
    def test_unresolved_finding_protects_old_audit_until_scoped_resolution(self):
        first=wf.audit(self.store,{'scope':'source','sources':['source.cs'],'findings':[{'id':'save-isolation','observation':'Isolation remains unverified.','status':'open'}],'checks':[],'coverage_gaps':[]})
        for i in range(10):wf.audit(self.store,{'scope':'other','sources':['source.cs'],'findings':[],'checks':[],'coverage_gaps':[]})
        self.assertEqual(wf.prune(self.store),[])
        wf.audit(self.store,{'scope':'source','sources':['source.cs'],'findings':[{'id':'save-isolation','observation':'Isolation qualified.','status':'resolved'}],'checks':[],'coverage_gaps':[]})
        self.assertFalse(any(first['id'].lower() in p.name for p in (self.store.base/'history/audits').glob('*.json')))
    def test_metadata_paths_cannot_escape_owned_directory(self):
        with self.assertRaises(wf.WorkflowError):self.store.commit({'.skill-tree/../../outside.txt':'Rejected'})
    def test_read_only_queries_do_not_refresh_or_write(self):
        main=self.main();before={p:p.read_bytes() for p in self.store.base.rglob('*') if p.is_file()}
        wf.select(wf.parse(self.store.text()));wf.manifest(self.store);wf.prune(self.store)
        self.assertEqual(before,{p:p.read_bytes() for p in self.store.base.rglob('*') if p.is_file()})

    def test_expired_evidence_is_marked_unavailable_without_rewriting_verdict(self):
        task=self.main();self.complete(task);(self.root/'test-report.json').unlink()
        record=wf.history(self.store,task['id'])[0];self.assertEqual(record['acceptance'][0]['result'],'pass');self.assertFalse(record['acceptance'][0]['evidence'][0]['available'])
    def test_missing_acceptance_evidence_cannot_complete(self):
        task=self.main();(self.root/'test-report.json').unlink()
        with self.assertRaisesRegex(wf.WorkflowError,'evidence missing'):self.complete(task)
    def test_no_progress_stop_blocks_next_handoff(self):
        self.main();wf.start(self.store,'next');wf.record_cycle(self.store);wf.record_cycle(self.store)
        with self.assertRaisesRegex(wf.WorkflowError,'Run stopped'):wf.advance(self.store)

    def test_generated_prose_violations_leave_queue_unchanged(self):
        before=self.store.future.read_bytes()
        for description in ['It stores their settings.','Описание задачи.','The previous version used a shared save.']:
            with self.assertRaises(wf.WorkflowError):wf.intake(self.store,{'title':'New task','description':description,'expected_behavior':'The project preserves state.'})
        self.assertEqual(before,self.store.future.read_bytes())
    def test_history_filenames_use_lowercase_kebab_case(self):
        task=self.main();wf.start(self.store,'next');self.complete(task);wf.finish(self.store)
        wf.audit(self.store,{'scope':'source','sources':['source.cs'],'findings':[],'checks':[],'coverage_gaps':[]})
        for path in (self.store.base/'history').rglob('*.json'):self.assertEqual(path.name,path.name.lower())

    def test_developer_queue_edit_during_mutation_is_preserved(self):
        original=self.store.save
        def intervening_edit(text,state,extras=None):
            self.store.future.write_text(self.store.text()+'Developer source edit.\n')
            return original(text,state,extras)
        with patch.object(self.store,'save',side_effect=intervening_edit):
            with self.assertRaisesRegex(wf.WorkflowError,'changed during'):
                self.pending('Concurrent task')
        self.assertIn('Developer source edit.',self.store.text());self.assertNotIn('Concurrent task',self.store.text())
    def test_completion_cannot_downgrade_required_acceptance(self):
        task=self.main()
        with self.assertRaises(wf.WorkflowError):wf.complete(self.store,{'task_id':task['id'],'outcome':'Behavior delivered.','acceptance':[{'criterion':'Preserve isolated state.','result':'not-run','required':False,'evidence':['test-report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.cs'])})

    def test_repeated_retained_processing_receipts_do_not_count_as_progress(self):
        main=self.main();wf.start(self.store,'next');pending=self.pending('Required decision',relation='blocker',root_task_id=main['id'],related_task_id=main['id'])
        payload={'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'retained','reason':'Required configuration evidence remains unavailable.'}},'tasks':[]}
        wf.process(self.store,payload);wf.record_cycle(self.store);wf.process(self.store,payload)
        self.assertEqual(wf.record_cycle(self.store)['phase'],'blocked')

    def _check_request(self, task, attempt):
        return {'action':'inspect','task_id':task['id'],'check_id':'behavior','attempt_id':attempt['attempt_id']}

    def _cleanup_request(self, request, inspection, group, **overrides):
        from datetime import datetime, timezone
        import socket
        proof = {
            'schema':1,'kind':'local-process-group-cleanup',
            **{key:request[key] for key in ('task_id','check_id','attempt_id')},
            **{key:inspection[key] for key in ('run_id','expected_key','expected_definition','environment_identity')},
            'host':socket.gethostname(),'process_group':group,'observed_live_processes':0,
            'observed_at':datetime.now(timezone.utc).isoformat(),
        }
        proof.update(overrides)
        path = self.root/'check-cleanup.json'
        path.write_text(json.dumps(proof))
        return {**request,'action':'cancel',
                **{key:inspection[key] for key in ('expected_key','expected_definition','observed')},
                'cleanup':{'path':path.name,'sha256':wf.file_hash(path)}}

    def _runner_binding_request(self, request, inspection, group):
        return {**request,'action':'bind-runner','expected_key':inspection['expected_key'],
                'expected_definition':inspection['expected_definition'],'process_group':group}

    def _bind_test_runner(self, request, process):
        import socket
        inspection = wf.reconcile_check(self.store,request)
        binding = self._runner_binding_request(request,inspection,process.pid)
        receipt = wf.reconcile_check(self.store,binding)
        self.assertEqual(receipt['process_group'],process.pid)
        self.assertEqual(receipt['host'],socket.gethostname())
        self.assertTrue(receipt['bound_at'])
        return binding

    def _owned_test_group(self, *, live=False):
        import subprocess
        import sys
        process = subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)' if live else 'pass'],
                                   start_new_session=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        self.addCleanup(cleanup)
        if not live:
            process.wait(timeout=10)
        return process

    def _workflow_bytes(self):
        return {path.relative_to(self.store.base):path.read_bytes()
                for path in self.store.base.rglob('*') if path.is_file()}

    def _static_check_result(self, task, attempt):
        return {'task_id':task['id'],'check_id':attempt['check_id'],'attempt_id':attempt['attempt_id'],
                'result':'pass','classification':'executed-control','actual_lane':'static',
                'environment_identity':attempt['environment_identity'],
                'assertions':[{'assertion':'Preserve isolated state.','result':'pass'}],
                'cleanup':'The disposable fixture exited.','evidence':['test-report.json']}

    def _installation_operation_active(self):
        import subprocess
        probe = subprocess.run(
            ['node','-e','console.log(require(process.argv[1]).hasActiveOperation(process.argv[2]))',
             str(ROOT/'lib/installation.js'),str(self.root)],
            capture_output=True,text=True,check=True,timeout=15,
        )
        return json.loads(probe.stdout)

    def test_stale_check_inspection_uses_the_cli_without_writes(self):
        import subprocess
        import sys
        task = self.main()
        wf.begin_task(self.store,{'task_id':task['id']})
        attempt = wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
        request = self.root/'inspect-check.json'
        request.write_text(json.dumps(self._check_request(task,attempt)))
        before = self._workflow_bytes()
        probe = subprocess.run([sys.executable,'-B',str(ROOT/'common/scripts/workflow-state.py'),
                                'reconcile-check',str(self.root),'--input',str(request)],
                               capture_output=True,text=True,timeout=15)
        self.assertEqual(probe.returncode,0,probe.stdout+probe.stderr)
        report = json.loads(probe.stdout)
        self.assertEqual(report['expected_key'],attempt['key'])
        self.assertEqual(report['expected_definition'],attempt['definition'])
        self.assertEqual(report['environment_identity'],attempt['environment_identity'])
        self.assertIsNone(report['run_id'])
        self.assertEqual(report['observed'],{key:attempt[key] for key in ('key','definition','sources')})
        self.assertFalse(report['stale'])
        self.assertEqual(before,self._workflow_bytes())

    def test_reconcile_preserves_old_pass_and_allows_fresh_check_after_verified_exit(self):
        task = self.main()
        tid = task['id']
        source = self.root/'source.cs'
        baseline = source.read_bytes()
        wf.begin_task(self.store,{'task_id':tid})
        previous = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        old_pass = wf.record_check(self.store,self._static_check_result(task,previous))
        attempt = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        request = self._check_request(task,attempt)
        with self.assertRaises(wf.WorkflowError):
            wf.validate_task_checks(self.store,tid)
        self.assertTrue(self._installation_operation_active())

        process = self._owned_test_group(live=True)
        self._bind_test_runner(request,process)
        source.write_text('The fixture source changed during validation.\n')
        inspected = wf.reconcile_check(self.store,request)
        self.assertTrue(inspected['stale'])
        unrelated = self._owned_test_group()
        self.assertNotEqual(unrelated.pid,process.pid)
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,self._cleanup_request(request,inspected,unrelated.pid))
        self.assertEqual(before,self._workflow_bytes())
        cancel = self._cleanup_request(request,inspected,process.pid)
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,cancel)
        self.assertEqual(before,self._workflow_bytes())
        self.assertIsNone(process.poll(),'Reconciliation must not terminate a process')

        process.terminate()
        process.wait(timeout=10)
        cancel = self._cleanup_request(request,inspected,process.pid)
        original = self.store.load()['task_progress'][tid]['checks']['behavior']['attempt']
        closed = wf.reconcile_check(self.store,cancel)
        self.assertEqual(closed['status'],'cancelled-no-result')
        self.assertEqual(closed['original_attempt'],original)
        self.assertNotIn('result',closed)
        self.assertNotIn('counts',closed)
        slot = self.store.load()['task_progress'][tid]['checks']['behavior']
        self.assertEqual(slot['attempt'],original)
        self.assertEqual(slot['result'],old_pass)
        self.assertFalse(self._installation_operation_active())
        with self.assertRaises(wf.WorkflowError):
            wf.validate_task_checks(self.store,tid)

        source.write_bytes(baseline)
        after_close = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.record_check(self.store,self._static_check_result(task,attempt))
        self.assertEqual(after_close,self._workflow_bytes())

        source.write_text('The fixture source changed during validation.\n')
        fresh = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        self.assertNotEqual(fresh['attempt_id'],attempt['attempt_id'])
        before_replay = self._workflow_bytes()
        self.assertEqual(wf.reconcile_check(self.store,cancel),closed)
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,{**cancel,'expected_key':'0'*64})
        self.assertEqual(before_replay,self._workflow_bytes())
        wf.record_check(self.store,self._static_check_result(task,fresh))
        wf.mark_implemented(self.store,{'task_id':tid})
        finished = wf.complete(self.store,{
            'task_id':tid,'outcome':'The scoped behavior preserves isolated state.',
            'acceptance':[{'criterion':'Preserve isolated state.','result':'pass','evidence':['test-report.json']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.cs']),
        })
        self.assertEqual(finished['check_results'][0]['result']['attempt_id'],fresh['attempt_id'])
        self.assertEqual(wf.reconcile_check(self.store,cancel),closed)

    def test_reconcile_rejects_fresh_moved_and_mismatched_cleanup_without_mutation(self):
        task = self.main()
        tid = task['id']
        source = self.root/'source.cs'
        wf.begin_task(self.store,{'task_id':tid})
        attempt = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        request = self._check_request(task,attempt)
        process = self._owned_test_group(live=True)
        binding = self._bind_test_runner(request,process)
        other_live = self._owned_test_group(live=True)
        group = process.pid
        fresh = wf.reconcile_check(self.store,request)

        def rejected(payload):
            before = self._workflow_bytes()
            with self.assertRaises(wf.WorkflowError):
                wf.reconcile_check(self.store,payload)
            self.assertEqual(before,self._workflow_bytes())

        rejected({**binding,'process_group':other_live.pid})
        self.assertIsNone(process.poll())
        self.assertIsNone(other_live.poll())
        process.terminate()
        process.wait(timeout=10)
        rejected(self._cleanup_request(request,fresh,group))
        source.write_text('The first fixture revision changed.\n')
        inspected = wf.reconcile_check(self.store,request)
        cancel = self._cleanup_request(request,inspected,group)
        rejected({**cancel,'expected_definition':'0'*64})
        rejected({**cancel,'attempt_id':wf.identity('C')})
        rejected({**cancel,'cleanup':{**cancel['cleanup'],'sha256':'0'*64}})
        rejected({**cancel,'cleanup':{**cancel['cleanup'],'path':'missing-cleanup.json'}})
        rejected(self._cleanup_request(request,inspected,group,run_id=wf.identity('WR')))
        rejected(self._cleanup_request(request,inspected,group,host='foreign-fixture.invalid'))
        rejected(self._cleanup_request(request,inspected,group,observed_live_processes=1))
        rejected(self._cleanup_request(request,inspected,group,observed_at='2000-01-01T00:00:00+00:00'))
        rejected(self._cleanup_request(request,inspected,group,environment_identity='0'*64))
        cancel = self._cleanup_request(request,inspected,group)
        alias = self.root/'cleanup-alias.json'
        alias.symlink_to(self.root/'check-cleanup.json')
        rejected({**cancel,'cleanup':{**cancel['cleanup'],'path':alias.name}})
        source.write_text('The second fixture revision changed.\n')
        rejected(cancel)
        with self.assertRaises(wf.WorkflowError):
            wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})

    def test_stale_unbound_attempt_rejects_retroactive_binding_and_cleanup(self):
        task = self.main()
        wf.begin_task(self.store,{'task_id':task['id']})
        attempt = wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
        request = self._check_request(task,attempt)
        (self.root/'source.cs').write_text('The fixture source changed before binding.\n')
        inspected = wf.reconcile_check(self.store,request)
        self.assertTrue(inspected['stale'])
        runner = self._owned_test_group(live=True)
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,self._runner_binding_request(request,inspected,runner.pid))
        self.assertEqual(before,self._workflow_bytes())
        self.assertIsNone(runner.poll())
        runner.terminate()
        runner.wait(timeout=10)
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,self._cleanup_request(request,inspected,runner.pid))
        self.assertEqual(before,self._workflow_bytes())
        with self.assertRaises(wf.WorkflowError):
            wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})

    def test_reconcile_can_observe_a_removed_check_without_fabricating_a_current_key(self):
        task = self.main()
        wf.begin_task(self.store,{'task_id':task['id']})
        attempt = wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
        request = self._check_request(task,attempt)
        runner = self._owned_test_group(live=True)
        self._bind_test_runner(request,runner)
        self.store.future.write_text(self.store.text().replace('"id": "behavior"','"id": "replacement"'))
        inspected = wf.reconcile_check(self.store,request)
        self.assertTrue(inspected['stale'])
        self.assertIsNone(inspected['observed']['key'])
        self.assertNotEqual(inspected['observed']['definition'],attempt['definition'])
        replacement = wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'replacement'})
        wf.record_check(self.store,self._static_check_result(task,replacement))
        wf.mark_implemented(self.store,{'task_id':task['id']})
        completion = {
            'task_id':task['id'],'outcome':'The scoped behavior preserves isolated state.',
            'acceptance':[{'criterion':'Preserve isolated state.','result':'pass','evidence':['test-report.json']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.cs']),
        }
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.complete(self.store,completion)
        self.assertEqual(before,self._workflow_bytes())
        runner.terminate()
        runner.wait(timeout=10)
        closed = wf.reconcile_check(self.store,self._cleanup_request(request,inspected,runner.pid))
        self.assertEqual(closed['status'],'cancelled-no-result')
        finished = wf.complete(self.store,completion)
        self.assertEqual(finished['check_results'][0]['result']['attempt_id'],replacement['attempt_id'])

    def test_reconcile_only_closes_selected_scope_and_preserves_a_parked_run_and_red(self):
        source_config = self.store.base/'config/repository.json'
        config = json.loads(source_config.read_text())
        config['recipes'] = {'static-inspection':{'lane':'unit','argv':['fixture'],'input_paths':[]}}
        source_config.write_text(json.dumps(config))
        outside = self.main('Standalone fixture')
        wf.begin_task(self.store,{'task_id':outside['id']})
        outside_attempt = wf.prepare_check(self.store,{'task_id':outside['id'],'check_id':'behavior'})
        task = self.main('Controller fixture',priority=150)
        tid = task['id']
        run = wf.start(self.store,'next',tid)
        wf.begin_task(self.store,{'task_id':tid})
        red = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        wf.record_check(self.store,{
            'task_id':tid,'check_id':'behavior','attempt_id':red['attempt_id'],
            'result':'red','classification':'executed-control','actual_lane':'unit',
            'environment_identity':red['environment_identity'],'failure_category':'expected-behavior',
            'counts':{'expected':1,'discovered':1,'passed':0,'failed':1,'skipped':0},
            'cleanup':'The disposable fixture exited.','evidence':['test-report.json'],
        })
        attempt = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        request = self._check_request(task,attempt)
        runner = self._owned_test_group(live=True)
        self._bind_test_runner(request,runner)
        wf.checkpoint(self.store,{'phase':'blocked','stop_reason':'Owner review remains pending'})
        (self.root/'source.cs').write_text('The fixture source changed during validation.\n')
        inspection = wf.reconcile_check(self.store,request)
        self.assertEqual(inspection['run_id'],run['id'])
        parked = self.store.load()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,self._check_request(outside,outside_attempt))
        self.assertEqual(self.store.load(),parked)
        runner.terminate()
        runner.wait(timeout=10)
        wf.reconcile_check(self.store,self._cleanup_request(request,inspection,runner.pid))
        current = self.store.load()
        self.assertEqual(current['active_run'],parked['active_run'])
        self.assertEqual(current['task_progress'][outside['id']],parked['task_progress'][outside['id']])
        self.assertEqual(current['task_progress'][tid]['stage'],parked['task_progress'][tid]['stage'])
        self.assertEqual(current['task_progress'][tid]['checks']['behavior']['red'],
                         parked['task_progress'][tid]['checks']['behavior']['red'])
        self.assertEqual(current['task_progress'][tid]['checks']['behavior']['result'],
                         parked['task_progress'][tid]['checks']['behavior']['result'])
        with self.assertRaises(wf.WorkflowError):
            wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})

    def test_reconcile_rejects_parent_attempt_outside_current_maintenance_focus(self):
        parent = self.main('Parked parent fixture',priority=150)
        maintenance = self.main('Focused infrastructure fixture')
        wf.start(self.store,'all')
        wf.begin_task(self.store,{'task_id':parent['id']})
        attempt = wf.prepare_check(self.store,{'task_id':parent['id'],'check_id':'behavior'})
        request = self._check_request(parent,attempt)
        runner = self._owned_test_group(live=True)
        self._bind_test_runner(request,runner)
        wf.checkpoint(self.store,{'phase':'blocked','stop_reason':'Owner review remains pending'})
        (self.root/'source.cs').write_text('The parked fixture source changed.\n')
        inspected = wf.reconcile_check(self.store,request)
        runner.terminate()
        runner.wait(timeout=10)
        cancel = self._cleanup_request(request,inspected,runner.pid)
        wf.focus_maintenance(self.store,{
            'task_id':maintenance['id'],'instruction':'Inspect the scoped infrastructure fixture.',
        })
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,cancel)
        self.assertEqual(before,self._workflow_bytes())

    def test_reconcile_rejects_one_live_runner_binding_for_two_pending_attempts(self):
        first = self.main('First runner fixture')
        second = self.main('Second runner fixture')
        wf.start(self.store,'all')
        requests = []
        for task in (first,second):
            wf.begin_task(self.store,{'task_id':task['id']})
            attempt = wf.prepare_check(self.store,{'task_id':task['id'],'check_id':'behavior'})
            requests.append(self._check_request(task,attempt))
        runner = self._owned_test_group(live=True)
        self._bind_test_runner(requests[0],runner)
        inspection = wf.reconcile_check(self.store,requests[1])
        binding = self._runner_binding_request(requests[1],inspection,runner.pid)
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,binding)
        self.assertEqual(before,self._workflow_bytes())
        self.assertIsNone(runner.poll())

    def test_reconcile_proves_recipe_only_drift_from_the_original_owned_profile(self):
        import subprocess
        import sys
        task = self.main('Installed recipe fixture')
        tid = task['id']
        recipe_input = self.root/'recipe-input.txt'
        recipe_input.write_text('The original recipe input.\n')
        (self.store.base/'validation-recipes.json').write_text(json.dumps({
            'schema':1,'recipes':{'static-inspection':{
                'lane':'unit','argv':[sys.executable,'-c','pass'],'input_paths':[recipe_input.name],
            }},
        }))
        installed = subprocess.run(
            ['node',str(ROOT/'bin/install.js'),'--target',str(self.root),'--only','codex',
             '--skills','skill-tree-implement-all','--flavor','general','--copy','--non-interactive'],
            capture_output=True,text=True,timeout=45,
        )
        self.assertEqual(installed.returncode,0,installed.stdout+installed.stderr)
        profile = self.store.base/'installation/profile.json'
        original_profile = profile.read_bytes()
        self.assertEqual(json.loads(original_profile)['inputs'][recipe_input.name],wf.file_hash(recipe_input))
        wf.begin_task(self.store,{'task_id':tid})
        attempt = wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        request = self._check_request(task,attempt)
        runner = self._owned_test_group(live=True)
        self._bind_test_runner(request,runner)

        recipe_input.write_text('The scoped recipe input changed.\n')
        inspected = wf.reconcile_check(self.store,request)
        self.assertTrue(inspected['stale'])
        self.assertIsNone(inspected['observed']['key'])
        self.assertEqual(inspected['observed']['definition'],attempt['definition'])
        self.assertEqual(inspected['observed']['sources'],attempt['sources'])
        self.assertEqual(inspected['observed']['recipe_inputs'][recipe_input.name],wf.file_hash(recipe_input))
        self.assertTrue(self._installation_operation_active())
        runner.terminate()
        runner.wait(timeout=10)
        cancel = self._cleanup_request(request,inspected,runner.pid)

        forged = json.loads(original_profile)
        forged['inputs'][recipe_input.name] = '0'*64
        profile.write_text(json.dumps(forged))
        before = self._workflow_bytes()
        with self.assertRaises(wf.WorkflowError):
            wf.reconcile_check(self.store,cancel)
        self.assertEqual(before,self._workflow_bytes())
        profile.write_bytes(original_profile)
        closed = wf.reconcile_check(self.store,cancel)
        self.assertEqual(closed['status'],'cancelled-no-result')
        self.assertFalse(self._installation_operation_active())

if __name__=='__main__':unittest.main()
