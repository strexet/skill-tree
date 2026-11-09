import importlib.util
import json
from pathlib import Path
import tempfile
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
    def body(self):
        check={'id':'behavior','recipe_id':'static-inspection','criteria':['Preserve isolated state.'],'sources':['source.cs'],'parameters':{},'assertion':'Preserve isolated state.','timing':'immediate'}
        return 'Goal:\n- Preserve isolated state.\n\nTouch:\n- source.cs\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Preserve isolated state.\n'
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
