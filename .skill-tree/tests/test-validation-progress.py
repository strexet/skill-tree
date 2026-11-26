import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('wf_progress',CORE/'common/scripts/workflow-state.py');wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)

class ValidationProgressTests(unittest.TestCase):
    def local_runner_fixture(self, lane='static', *, program=None):
        config=self.store.base/'config/repository.json'
        config.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'fixture-runner':{'lane':lane,'argv':['python3','verify-runner.py'],'input_paths':['verify-runner.py']},
        }}))
        (self.root/'verify-runner.py').write_text(program or (
            "from pathlib import Path\n"
            "with Path('runner-invocations').open('a') as stream: stream.write('run\\n')\n"
            "assert 'value = ' in Path('source.py').read_text()\n"
        ))
        return 'fixture-runner'

    def local_runner_request(self,tid,**extra):
        return {'task_id':tid,'check_id':'behavior','action':'run',
                'authorization':'Execute the selected disposable local check.',
                'deadline_utc':(datetime.now(timezone.utc)+timedelta(seconds=25)).isoformat(),
                'cleanup_seconds':3,**extra}

    def test_installed_runner_reconciles_after_coordinator_ack_loss_without_relaunch(self):
        tid=self.task(recipe=self.local_runner_fixture())
        self.review_candidate(tid,controller=True,record_result=False)
        request=self.local_runner_request(tid)
        inspect={key:request[key] for key in ('task_id','check_id')}
        state=self.store.state.read_bytes()
        self.assertEqual(wf.run_check(self.store,{**inspect,'action':'inspect'})['status'],'due')
        self.assertEqual(self.store.state.read_bytes(),state)
        original=wf.reconcile_check
        def interrupt_after_retention(store,payload):
            if payload['action']=='recover-result':
                raise wf.WorkflowError('Lost coordinator acknowledgement')
            return original(store,payload)
        with patch.object(wf,'reconcile_check',side_effect=interrupt_after_retention):
            with self.assertRaisesRegex(wf.WorkflowError,'Lost coordinator acknowledgement'):
                wf.run_check(self.store,request)
        observation=wf.run_check(self.store,{**inspect,'action':'inspect'})
        self.assertEqual(observation['status'],'reconciliation-required')
        original_attempt=observation['attempt_id']
        self.assertIn('runner_result',observation['observation'])
        result=wf.run_check(self.store,{**inspect,'action':'reconcile','attempt_id':original_attempt})
        self.assertEqual(result['record']['attempt_id'],original_attempt)
        self.assertEqual(result['record']['result'],'pass')
        self.assertEqual(wf.run_check(self.store,request)['record'],result['record'])
        self.assertEqual((self.store.source_root/'runner-invocations').read_text(),'run\n')

    def test_native_runner_reconciles_retained_result_after_launch_only_drift(self):
        import os
        import shlex

        recipe=self.local_runner_fixture()
        binary=self.root/'fixture-runner-executable'
        binary.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' "$@"\n')
        binary.chmod(0o700)
        config=self.store.base/'config/repository.json'
        metadata=json.loads(config.read_text())
        metadata['recipes'][recipe]['argv'][0]=str(binary)
        config.write_text(json.dumps(metadata))
        tid=self.task(recipe=recipe)
        self.review_candidate(tid,controller=True,record_result=False)
        selection={'task_id':tid,'check_id':'behavior'}
        original=wf.reconcile_check

        def lose_coordinator_ack(store,payload):
            if payload['action']=='recover-result':
                raise wf.WorkflowError('Lost coordinator acknowledgement')
            return original(store,payload)

        with patch.object(wf,'reconcile_check',side_effect=lose_coordinator_ack):
            with self.assertRaisesRegex(wf.WorkflowError,'Lost coordinator acknowledgement'):
                wf.run_check(self.store,self.local_runner_request(tid))
        inspect={**selection,'action':'inspect'}
        initial=wf.run_check(self.store,inspect)['observation']
        retained=initial['runner_result']
        state=self.store.state.read_bytes()
        self.assertFalse(initial['stale'])

        with patch.dict(os.environ,{'PATH':os.environ.get('PATH',os.defpath)+os.pathsep+str(self.root/'unused-bin')}):
            drift=wf.run_check(self.store,inspect)['observation']
            self.assertTrue(drift['stale'])
            self.assertEqual(drift['observed']['key'],initial['expected_key'])
            self.assertEqual(drift['runner_result'],retained)
            self.assertNotEqual(drift['observed']['local_launch']['runner_environment_sha256'],
                                initial['observed']['local_launch']['runner_environment_sha256'])
            self.assertEqual(self.store.state.read_bytes(),state)

        binary.write_text(binary.read_text()+'# replacement bytes\n')
        drift=wf.run_check(self.store,inspect)['observation']
        self.assertTrue(drift['stale'])
        self.assertEqual(drift['observed']['key'],initial['expected_key'])
        self.assertEqual(drift['observed']['local_launch']['executable_sha256'],wf.file_hash(binary))
        self.assertEqual(drift['runner_result'],retained)
        reconciled=wf.run_check(self.store,{**selection,'action':'reconcile','attempt_id':initial['attempt_id']})
        self.assertEqual(reconciled['status'],'cancelled-no-result')
        self.assertEqual(reconciled['receipt']['observed'],drift['observed'])
        self.assertEqual(reconciled['receipt']['cancellation_reason'],'source-or-check-drift')
        self.assertEqual(wf.file_hash(self.store.root/retained['path']),retained['sha256'])
        slot=self.store.load()['task_progress'][tid]['checks']['behavior']
        self.assertNotIn('result',slot)
        self.assertEqual((self.store.source_root/'runner-invocations').read_text(),'run\n')

    def test_native_runner_denies_unrelated_and_runtime_launches(self):
        tid=self.task('Browser path',recipe=self.local_runner_fixture('browser'))
        outside=self.task('Unrelated local task')
        self.review_candidate(tid,controller=True,record_result=False)
        before=self.store.state.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'outside'):
            wf.run_check(self.store,self.local_runner_request(outside))
        result=wf.run_check(self.store,self.local_runner_request(tid))
        self.assertEqual(result['status'],'explicit-execution-required')
        self.assertIn('session_identity',result['requirements']['execution']['fields'])
        self.assertEqual(self.store.state.read_bytes(),before)
        self.assertFalse((self.store.source_root/'runner-invocations').exists())

    def test_native_runner_refuses_inspected_input_drift_before_binding(self):
        tid=self.task(recipe=self.local_runner_fixture())
        self.review_candidate(tid,controller=True,record_result=False)
        scope={'task_id':tid,'check_id':'behavior'}
        inspect=wf.run_check(self.store,{**scope,'action':'inspect'})
        self.assertEqual(inspect['status'],'due')
        (self.store.source_root/'source.py').write_text('value = 3\n')
        before=self.store.state.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'inputs changed before launch'):
            wf.run_check(self.store,self.local_runner_request(tid,expected_launch_sha256=inspect['launch_sha256']))
        self.assertEqual(self.store.state.read_bytes(),before)
        self.assertFalse((self.store.source_root/'runner-invocations').exists())

    def test_native_runner_cancels_only_after_its_timed_out_group_departs(self):
        import time

        recipe=self.local_runner_fixture(program=(
            "from pathlib import Path\n"
            "import time\n"
            "Path('runner-invocations').write_text('started\\n')\n"
            "time.sleep(30)\n"
        ))
        tid=self.task(recipe=recipe)
        self.review_candidate(tid,controller=True,record_result=False)
        request=self.local_runner_request(tid,cleanup_seconds=2,
            deadline_utc=(datetime.now(timezone.utc)+timedelta(seconds=8)).isoformat())
        result=wf.run_check(self.store,request)
        self.assertEqual(result['status'],'reconciliation-required')
        self.assertEqual((self.store.source_root/'runner-invocations').read_text(),'started\n')
        request={'task_id':tid,'check_id':'behavior','action':'reconcile','attempt_id':result['attempt_id']}
        expires=time.monotonic()+4
        while True:
            cancelled=wf.run_check(self.store,request)
            if cancelled['status']!='reconciliation-required' or time.monotonic()>=expires:break
            time.sleep(0.05)
        self.assertEqual(cancelled['status'],'cancelled-no-result',cancelled)
        self.assertEqual(cancelled['receipt']['cancellation_reason'],'local-result-unavailable')
        replay=wf.run_check(self.store,request)
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['receipt'],cancelled['receipt'])

    def test_native_runner_retries_only_the_explicit_unsuccessful_receipt(self):
        recipe=self.local_runner_fixture(program=(
            "from pathlib import Path\n"
            "path=Path('runner-invocations')\n"
            "prior=path.exists()\n"
            "with path.open('a') as stream: stream.write('run\\n')\n"
            "raise SystemExit(0 if prior else 1)\n"
        ))
        tid=self.task(recipe=recipe)
        self.review_candidate(tid,controller=True,record_result=False)
        request=self.local_runner_request(tid)
        first=wf.run_check(self.store,request)['record']
        self.assertEqual(first['result'],'fail')
        self.assertEqual(wf.run_check(self.store,request)['record'],first)
        result=wf.run_check(self.store,{**request,'retry_attempt_id':first['attempt_id']})
        self.assertEqual(result['record']['result'],'pass')
        self.assertNotEqual(result['record']['attempt_id'],first['attempt_id'])
        replay=wf.run_check(self.store,{'task_id':tid,'check_id':'behavior','action':'reconcile',
                                       'attempt_id':first['attempt_id']})
        self.assertEqual(replay['record'],first)
        self.assertTrue(replay['historical'])
        import os
        with patch.dict(os.environ,{'PATH':os.environ.get('PATH',os.defpath)+os.pathsep+str(self.root/'unused-bin')}):
            inspected=wf.run_check(self.store,{'task_id':tid,'check_id':'behavior','action':'inspect'})
            self.assertEqual(inspected['status'],'due')
            archived=wf.run_check(self.store,{'task_id':tid,'check_id':'behavior','action':'reconcile',
                                             'attempt_id':result['record']['attempt_id']})
            self.assertEqual(archived['record'],result['record'])
            self.assertTrue(archived['historical'])
        self.assertEqual((self.store.source_root/'runner-invocations').read_text(),'run\nrun\n')

    def test_local_runner_tool_drift_blocks_current_task_and_review_gates(self):
        import shlex

        recipe=self.local_runner_fixture()
        binary=self.root/'fixture-current-check-executable'
        binary.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' "$@"\n')
        binary.chmod(0o700)
        config=self.store.base/'config/repository.json'
        metadata=json.loads(config.read_text())
        metadata['recipes'][recipe]['argv'][0]=str(binary)
        config.write_text(json.dumps(metadata))
        tid=self.task(recipe=recipe)
        identity,_=self.review_candidate(tid,controller=True,record_result=False)
        record=wf.run_check(self.store,self.local_runner_request(tid))['record']
        scope={'kind':'task','task_ids':[tid]}
        self.assertEqual(wf.validate_task_checks(self.store,tid)[0]['result'],record)
        self.assertEqual(wf.review_check_evidence(self.store,identity,scope)[0]['status'],'reusable')

        state=self.store.state.read_bytes()
        old_binary=binary.read_bytes()
        binary.write_bytes(old_binary+b'# changed execution input\n')
        with self.assertRaisesRegex(wf.WorkflowError,'Local check runner.*changed'):
            wf.validate_task_checks(self.store,tid)
        review=wf.review_check_evidence(self.store,identity,scope)[0]
        self.assertEqual(review['status'],'rerun-required')
        self.assertRegex(review['reason'],'Local check runner.*changed')
        replay=wf.run_check(self.store,{'task_id':tid,'check_id':'behavior','action':'reconcile',
                                       'attempt_id':record['attempt_id']})
        self.assertTrue(replay['historical'])
        self.assertEqual(replay['record'],record)
        self.assertEqual(self.store.state.read_bytes(),state)

        binary.write_bytes(old_binary)
        self.assertEqual(wf.validate_task_checks(self.store,tid)[0]['result'],record)
        self.assertEqual(wf.review_check_evidence(self.store,identity,scope)[0]['status'],'reusable')

    def test_local_runner_receipt_is_portable_for_a_byte_identical_checkout_executable(self):
        import shlex

        recipe=self.local_runner_fixture()
        local_tool=self.root/'tools/check'
        local_tool.parent.mkdir()
        local_tool.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' verify-runner.py\n')
        local_tool.chmod(0o700)
        config=self.store.base/'config/repository.json'
        metadata=json.loads(config.read_text())
        metadata['recipes'][recipe]['argv']=['./tools/check']
        config.write_text(json.dumps(metadata))
        tid=self.task(recipe=recipe)
        self.review_candidate(tid,controller=True,record_result=False)
        record=wf.run_check(self.store,self.local_runner_request(tid))['record']
        task=wf.validation_task(self.store,tid)
        check=wf.check_specs(task)[0]
        state=self.store.load()

        independent=self.store.source_root.parent/'independent-runner-fixture'
        self.git('worktree','add','-qb','independent-runner-fixture',str(independent),'HEAD')
        other=wf.Store(independent)
        self.assertEqual(other.root,self.store.root)
        self.assertNotEqual(wf.workspaces.checked_out_branch(other.source_root)['checkout'],
                            wf.workspaces.checked_out_branch(self.store.source_root)['checkout'])
        (other.source_root/'source.py').write_bytes((self.store.source_root/'source.py').read_bytes())
        for evidence in record['evidence']:
            path=other.source_root/evidence['path']
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((self.store.source_root/evidence['path']).read_bytes())

        old=wf.local_check_runner_inputs(self.store,['./tools/check'],self.store.source_root/wf.workspaces.PROFILE_FILE)
        new=wf.local_check_runner_inputs(other,['./tools/check'],other.source_root/wf.workspaces.PROFILE_FILE)
        self.assertEqual(old['executable_sha256'],new['executable_sha256'])
        self.assertEqual(old['runner_environment_sha256'],new['runner_environment_sha256'])
        self.assertNotEqual(wf.local_check_launch_observation(old)['argv_sha256'],
                            wf.local_check_launch_observation(new)['argv_sha256'])
        self.assertEqual(wf.retained_revalidation_check(other,state,task,check,{'result':record},historical=True),record)
        new_tool=other.source_root/'tools/check'
        new_tool.write_bytes(new_tool.read_bytes()+b'# changed executable\n')
        self.assertIsNone(wf.retained_revalidation_check(other,state,task,check,{'result':record},historical=True))

    def test_local_runner_recognizes_only_successful_nonempty_vitest_counts(self):
        report={'success':True,'numTotalTests':3,'numPassedTests':3,'numFailedTests':0,
                'numPendingTests':0,'numTodoTests':0}
        self.assertEqual(wf.local_check_count('unit',json.dumps(report)),3)
        self.assertEqual(wf.local_check_count('unit',json.dumps({**report,'numTodoTests':1})),0)
        self.assertEqual(wf.local_check_count('unit',json.dumps({**report,'numPassedTests':True})),0)
        self.assertEqual(wf.local_check_count('unit',json.dumps({**report,'numTotalTests':0,'numPassedTests':0})),0)

    def test_native_runner_records_actual_unittest_discovery(self):
        recipe=self.local_runner_fixture('unit',program=(
            'import unittest\n'
            'class ExactFixture(unittest.TestCase):\n'
            '    def test_original(self): self.assertTrue(True)\n'
            '    def test_second(self): self.assertEqual(2, 2)\n'
            'unittest.main()\n'
        ))
        tid=self.task(recipe=recipe)
        self.review_candidate(tid,controller=True,record_result=False)
        result=wf.run_check(self.store,self.local_runner_request(tid))
        self.assertEqual(result['status'],'recorded')
        self.assertEqual(result['record']['counts'],{'expected':1,'discovered':2,'passed':2,'failed':0,'skipped':0})

    def test_native_runner_retains_historical_consumer_revalidation_receipt(self):
        producer=self.task('Previously completed source producer',recipe=self.local_runner_fixture())
        consumer=self.task('Blocked consumer requires current producer',deps=[producer])
        git_identity,_=self.review_candidate(producer,controller=True,record_result=False)
        original_run=self.store.run_id
        initial=wf.run_check(self.store,self.local_runner_request(producer))['record']
        neutral=wf.Store(self.store.source_root,allow_unselected=True,neutral=True)
        frame=self.review_frame({'kind':'task','task_ids':[producer]},git_identity)
        frame=self.review_change(frame,'checks',store=neutral,identity=git_identity,reused_checks=[
            {'task_id':producer,'id':'behavior','check_id':'behavior','attempt_id':initial['attempt_id']}])
        frame=self.review_change(frame,'review',identity=git_identity,review_id='owned-runner-fixture-review',
                                 findings=[],reference='Independent fixture review.')
        original=wf.complete(self.store,{'task_id':producer,'review_id':frame['id'],
            'outcome':'The scoped source producer remains observable.',
            'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':initial['evidence']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        archived=wf.run_check(self.store,{'task_id':producer,'check_id':'behavior','action':'reconcile',
                                         'attempt_id':initial['attempt_id']})
        self.assertTrue(archived['historical'])
        self.assertEqual(archived['record'],initial)
        owner=wf.Store(self.root,allow_unselected=True,neutral=True)
        run=wf.start(owner,'next',consumer,workspace={'implementation_operation':'work-through-next'})
        source=Path(wf.workspaces.runtime(self.root)['worktrees'][run['id']])
        self.store=wf.Store(source,run['id'])
        handoff=wf.advance(self.store)
        self.assertEqual(handoff['task_id'],producer)
        self.assertTrue(handoff['completed_contract'])
        result=wf.run_check(self.store,self.local_runner_request(producer))
        self.assertEqual(result['blocked_consumer_ids'],[consumer])
        self.assertEqual(result['status'],'recorded')
        self.assertNotEqual(result['record']['attempt_id'],initial['attempt_id'])
        import os
        with patch.dict(os.environ,{'PATH':os.environ.get('PATH',os.defpath)+os.pathsep+str(self.root/'runner-env-change')}):
            before=self.store.state.read_bytes()
            with self.assertRaisesRegex(wf.WorkflowError,'Local check runner.*changed'):
                wf.accept_revalidation(self.store,{'task_id':producer})
            selected=wf.next_task(self.store)
            self.assertEqual(selected['task_id'],producer)
            self.assertEqual([row['id'] for row in selected['checks']],['behavior'])
            self.assertEqual(self.store.state.read_bytes(),before)
        wf.accept_revalidation(self.store,{'task_id':producer})
        self.assertNotIn(producer,self.store.load()['task_progress'])
        self.assertEqual(wf.next_task(self.store)['task_id'],consumer)
        replay=wf.run_check(self.store,{'task_id':producer,'check_id':'behavior','action':'reconcile',
                                       'attempt_id':result['record']['attempt_id']})
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['record'],result['record'])
        self.assertEqual((source/'runner-invocations').read_text(),'run\n')
        durable=next(item for item in self.store.outcomes() if item['id']==original['id'])
        self.assertEqual(durable['run_id'],original_run)
        self.assertEqual(durable,original)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=wf.Store(self.root);self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (self.root/'source.py').write_text('value = 1\n');(self.root/'report.json').write_text('{"assertion":"value is preserved"}')
    def task(self,title='Feature',group=None,deps=(),timing='immediate',fresh_review=False,recipe='static-inspection',independent_source=None):
        p=wf.intake(self.store,{'title':title,'description':'Implement scoped behavior.','expected_behavior':'Preserve the observable value.'})
        check={'id':'behavior','recipe_id':recipe,'criteria':['Preserve the value.'],'sources':['source.py'],'parameters':{},'assertion':'The value remains observable.','timing':timing}
        if fresh_review:check['fresh_review']=True
        checks = [check]
        if independent_source:
            checks.append({**check,'id':'independent','sources':[independent_source]})
        body='Goal:\n- Preserve the value.\n\nTouch:\n- source.py\n\nValidation:\n```json\n'+json.dumps({'checks':checks})+'\n```\n\nAcceptance:\n- Preserve the value.\n'
        r=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Source research confirms the observable contract.'}},'tasks':[{'title':title,'body':body,'parent_pending_ids':[p['id']],'depends_on':list(deps),'validation_group_id':group,'boundary_validation':'group-end' if group else 'not-required'}]})
        return r['created_ids'][0]
    def progress(self,tid):
        wf.begin_task(self.store,{'task_id':tid});wf.mark_implemented(self.store,{'task_id':tid,'changed_files':['source.py']})
    def passed(self,tid,check_id='behavior'):
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':check_id})
        return wf.record_check(self.store,{'task_id':tid,'check_id':check_id,'attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'static','environment_identity':attempt['environment_identity'],'classification':'executed-control','assertions':[{'assertion':'The value remains observable.','result':'pass'}],'evidence':['report.json'],'cleanup':'No product process was launched.'})

    def start_result_runner(self, tid, *, retain_result=True, expected_value=1):
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        identity={'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id']}
        observation=wf.reconcile_check(self.store,{**identity,'action':'inspect'})
        expected={key:observation[key] for key in ('expected_key','expected_definition')}
        result={'classification':'executed-control','result':'pass','actual_lane':'static',
                'environment_identity':attempt['environment_identity'],
                'assertions':[{'assertion':'The value remains observable.','result':'pass'}],
                'cleanup':'The dedicated worker finished the scoped static assertion.',
                'evidence':['runner-'+attempt['attempt_id']+'.json']}
        retain={**identity,**expected,'action':'retain-result','result':result,'exit_code':0}
        payload=self.store.source_root/'runner-request.json'
        payload.write_text(json.dumps(retain))
        program = """
import json
from pathlib import Path
import subprocess
import sys

directive=sys.stdin.readline().strip()
if directive=='exit':
    raise SystemExit(0)
assert directive=='run'
request=Path(sys.argv[2])
payload=json.loads(request.read_text())
observed=subprocess.run([sys.executable,'-B','-c',
    "import runpy, sys; value=runpy.run_path('source.py')['value']; print(value); assert value==int(sys.argv[1])",
    sys.argv[3]],capture_output=True,text=True,check=True)
Path(payload['result']['evidence'][0]).write_text(json.dumps({'stdout':observed.stdout,'exit':observed.returncode}))
command=[sys.executable,'-B',sys.argv[1],'reconcile-check','.']
if sys.argv[4]:
    command.extend(['--run-id',sys.argv[4]])
command.append('--input')
falsey=Path('invalid-result-evidence.json')
falsey.write_text(json.dumps({**payload,'result':{**payload['result'],
    'evidence':[{'path':payload['result']['evidence'][0],'sha256':''}]}}))
rejected=subprocess.run([*command,str(falsey)],capture_output=True,text=True)
assert rejected.returncode and 'exact SHA-256' in rejected.stdout,rejected.stdout+rejected.stderr
stale_birth='''
import runpy
import sys

entry=runpy.run_path(sys.argv[1])
module=entry['reconcile_check'].__globals__
native=module['local_process_group_identity']
module['local_process_group_identity']=lambda pid,pgid: {**native(pid,pgid),'birth':{'clock':'fixture-reuse'}}
raise SystemExit(entry['main'](sys.argv[2:]))
'''
rejected=subprocess.run([sys.executable,'-B','-c',stale_birth,*command[2:],str(request)],capture_output=True,text=True)
assert rejected.returncode and 'birth identity changed' in rejected.stdout,rejected.stdout+rejected.stderr
subprocess.run([*command,str(request)],check=True,stdout=subprocess.DEVNULL)
print('retained',flush=True)
sys.stdin.readline()
"""
        process=subprocess.Popen([sys.executable,'-B','-c',program,str(CORE/'common/scripts/workflow-state.py'),str(payload),
                                 str(expected_value),self.store.run_id or ''],cwd=self.store.source_root,
                                 start_new_session=True,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,text=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)
        self.addCleanup(cleanup)
        binding=wf.reconcile_check(self.store,{**identity,**expected,'action':'bind-runner','process_group':process.pid})
        self.assertEqual(binding['process_group'],process.pid)
        with self.assertRaisesRegex(wf.WorkflowError,'Only the original bound runner'):
            wf.reconcile_check(self.store,retain)
        with self.assertRaisesRegex(wf.WorkflowError,'exact bound runner result'):
            wf.record_check(self.store,{**identity,**result})
        if not retain_result:
            return process,identity,result,None,None
        process.stdin.write('run\n')
        process.stdin.flush()
        self.assertTrue(select.select([process.stdout],[],[],15)[0],'The dedicated fixture did not retain its result')
        announced=process.stdout.readline()
        if announced!='retained\n':
            self.fail('The bound runner stopped before retention. '+process.stderr.read())
        inspected=wf.reconcile_check(self.store,{**identity,'action':'inspect'})
        self.assertEqual(inspected['runner_binding'],binding)
        pointer=inspected['runner_result']
        recovery={**identity,**expected,'action':'recover-result','result_sha256':pointer['sha256']}
        return process, identity, result, recovery, pointer

    def runner_cancellation(self,identity,inspected):
        binding=inspected['runner_binding']
        cleanup=self.root/'runner-cleanup.json'
        cleanup.write_text(json.dumps({**identity,'run_id':None,'schema':1,'kind':'local-process-group-cleanup',
            'expected_key':inspected['expected_key'],'expected_definition':inspected['expected_definition'],
            'environment_identity':inspected['environment_identity'],'host':binding['host'],
            'process_group':binding['process_group'],'observed_at':wf.now(),'observed_live_processes':0}))
        return {**identity,'action':'cancel','expected_key':inspected['expected_key'],
                'expected_definition':inspected['expected_definition'],'observed':inspected['observed'],
                'cleanup':{'path':cleanup.name,'sha256':wf.file_hash(cleanup)}}

    def test_completed_local_runner_result_recovers_after_coordinator_interruption(self):
        (self.root/'independent.py').write_text('independent = True\n')
        tid=self.task(independent_source='independent.py')
        self.progress(tid)
        process,identity,result,recovery,pointer=self.start_result_runner(tid)
        with self.assertRaisesRegex(wf.WorkflowError,'remains live'):
            wf.reconcile_check(self.store,recovery)
        with self.assertRaisesRegex(wf.WorkflowError,'reconcile-check'):
            wf.record_check(self.store,{**identity,**result})
        independent=self.passed(tid,'independent')
        self.assertEqual(independent['result'],'pass')
        self.assertIsNone(process.poll())
        process.stdin.write('exit\n')
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=10),0)
        before=self.store.state.read_bytes()
        with patch.object(wf.os,'killpg',side_effect=PermissionError('fixture unknown group')):
            with self.assertRaisesRegex(wf.WorkflowError,'cleanup is uncertain'):
                wf.reconcile_check(self.store,recovery)
        with self.assertRaisesRegex(wf.WorkflowError,'exact retained runner result digest'):
            wf.reconcile_check(self.store,{**recovery,'result_sha256':'0'*64})
        retained=self.root/pointer['path']
        retained_bytes=retained.read_bytes()
        retained.write_bytes(retained_bytes+b' ')
        with self.assertRaisesRegex(wf.WorkflowError,'runner result artifact changed'):
            wf.reconcile_check(self.store,{**recovery,'result_sha256':wf.file_hash(retained)})
        retained.write_bytes(retained_bytes)
        report=self.root/result['evidence'][0]
        report_bytes=report.read_bytes()
        report.write_bytes(report_bytes+b' ')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence changed'):
            wf.reconcile_check(self.store,recovery)
        report.write_bytes(report_bytes)
        self.assertEqual(self.store.state.read_bytes(),before)
        receipt=wf.reconcile_check(self.store,recovery)
        self.assertEqual(receipt['status'],'recovered-result')
        self.assertEqual(receipt['runner_result'],pointer)
        self.assertEqual(receipt['record']['attempt_id'],identity['attempt_id'])
        self.assertEqual(receipt['record']['result'],'pass')
        archive=self.store.base/'history/check-reconciliations'/f"{identity['attempt_id'].lower()}.json"
        canonical=self.store.state.read_bytes()
        archive_bytes=archive.read_bytes()
        changed_archive={**receipt,'record':{**receipt['record'],'cleanup':'Replaced evidence summary.'}}
        archive.write_text(json.dumps(changed_archive))
        with self.assertRaisesRegex(wf.WorkflowError,'differs from the canonical check receipt'):
            wf.reconcile_check(self.store,recovery)
        conflicting={**recovery,'result_sha256':'0'*64}
        archive.write_text(json.dumps({**receipt,'request_digest':wf.digest(wf.dump(conflicting).encode())}))
        with self.assertRaisesRegex(wf.WorkflowError,'differs from the canonical check receipt'):
            wf.reconcile_check(self.store,conflicting)
        archive.write_bytes(archive_bytes)
        self.store.state.write_bytes(before)
        with self.assertRaisesRegex(wf.WorkflowError,'differs from the canonical check receipt'):
            wf.reconcile_check(self.store,recovery)
        self.store.state.write_bytes(canonical)
        self.assertEqual(wf.reconcile_check(self.store,recovery),receipt)
        self.assertEqual(wf.record_check(self.store,{**identity,**result}),receipt['record'])
        with self.assertRaisesRegex(wf.WorkflowError,'Conflicting replay'):
            wf.reconcile_check(self.store,{**recovery,'expected_key':'0'*64})
        checks={row['check']['id']:row['result'] for row in wf.validate_task_checks(self.store,tid)}
        self.assertEqual(checks,{'behavior':receipt['record'],'independent':independent})

    def test_stale_local_runner_result_cannot_replace_the_next_attempt(self):
        tid=self.task()
        self.progress(tid)
        previous=self.passed(tid)
        process,identity,result,recovery,_=self.start_result_runner(tid)
        (self.root/'source.py').write_text('value = 2\n')
        inspected=wf.reconcile_check(self.store,{**identity,'action':'inspect'})
        with self.assertRaisesRegex(wf.WorkflowError,'remains live'):
            wf.reconcile_check(self.store,self.runner_cancellation(identity,inspected))
        self.assertIsNone(process.poll())
        process.stdin.write('exit\n')
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=10),0)
        with self.assertRaisesRegex(wf.WorkflowError,'Prepared check is stale'):
            wf.reconcile_check(self.store,recovery)
        closed=wf.reconcile_check(self.store,self.runner_cancellation(identity,inspected))
        self.assertEqual(closed['status'],'cancelled-no-result')
        slot=self.store.load()['task_progress'][tid]['checks']['behavior']
        self.assertEqual(slot['result'],previous)
        newer=self.passed(tid)
        with self.assertRaisesRegex(wf.WorkflowError,'Conflicting replay'):
            wf.reconcile_check(self.store,recovery)
        with self.assertRaisesRegex(wf.WorkflowError,'cancelled without a result'):
            wf.record_check(self.store,{**identity,**result})
        self.assertEqual(wf.validate_task_checks(self.store,tid)[0]['result'],newer)

    def test_departed_bound_runner_without_result_allows_current_check_retry(self):
        (self.root/'independent.py').write_text('independent = True\n')
        tid=self.task(independent_source='independent.py')
        self.progress(tid)
        process,identity,result,_,_=self.start_result_runner(tid,retain_result=False)
        independent=self.passed(tid,'independent')
        inspected=wf.reconcile_check(self.store,{**identity,'action':'inspect'})
        self.assertFalse(inspected['stale'])
        self.assertNotIn('runner_result',inspected)
        with self.assertRaisesRegex(wf.WorkflowError,'remains live'):
            wf.reconcile_check(self.store,self.runner_cancellation(identity,inspected))
        process.stdin.write('exit\n')
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=10),0)
        cancel=self.runner_cancellation(identity,inspected)
        closed=wf.reconcile_check(self.store,cancel)
        self.assertEqual(closed['cancellation_reason'],'local-result-unavailable')
        newer=self.passed(tid)
        with self.assertRaisesRegex(wf.WorkflowError,'cancelled without a result'):
            wf.record_check(self.store,{**identity,**result})
        self.assertEqual(wf.reconcile_check(self.store,cancel),closed)
        checks={row['check']['id']:row['result'] for row in wf.validate_task_checks(self.store,tid)}
        self.assertEqual(checks,{'behavior':newer,'independent':independent})

    def test_recovered_result_replay_uses_registered_completed_contract(self):
        tid=self.task()
        git_identity,_=self.review_candidate(tid,controller=True,record_result=False)
        with self.store.lock():
            text=self.store.text()
            state=self.store.load(text)
            state['task_progress'][tid]['execution_sessions']={
                'separate-product-lane':{'project_root':str(self.store.source_root)},
            }
            self.store.save(text,state)
        process,identity,result,recovery,_=self.start_result_runner(tid,expected_value=2)
        process.stdin.write('exit\n')
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=10),0)
        receipt=wf.reconcile_check(self.store,recovery)
        neutral=wf.Store(self.store.source_root,allow_unselected=True,neutral=True)
        frame=self.review_frame({'kind':'task','task_ids':[tid]},git_identity)
        request={**identity,'id':'behavior'}
        frame=self.review_change(frame,'checks',store=neutral,identity=git_identity,reused_checks=[request])
        frame=self.review_change(frame,'review',identity=git_identity,review_id='fixture-runner-review',findings=[],
                                 reference='Independent fixture review.')
        outcome=wf.complete(self.store,{'task_id':tid,'review_id':frame['id'],'outcome':'The scoped value remains observable.',
            'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':result['evidence']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        self.assertNotIn(tid,self.store.load()['task_progress'])
        self.assertEqual(wf.reconcile_check(self.store,recovery),receipt)
        portable=wf.workspaces.portable_envelope(outcome,self.store.source_root,self.store.root)
        relocated_root=self.root/'relocated-fixture'
        relocated=wf.workspaces.restore_envelope(portable,relocated_root,self.root)
        recovered=relocated['check_results'][0]['result']
        self.assertEqual(recovered['execution_sessions']['separate-product-lane']['project_root'],str(relocated_root))
        self.assertEqual(wf.completed_contract_sha256(outcome),wf.completed_contract_sha256(relocated))
        wf.verify_completed_contract(self.store,relocated)
        ledger=self.store.owned(wf.OUTCOME_LEDGER)
        ledger_bytes=ledger.read_bytes()
        archive=self.store.base/'history/check-reconciliations'/f"{identity['attempt_id'].lower()}.json"
        archive_bytes=archive.read_bytes()
        changed=json.loads(json.dumps(outcome))
        checked=changed['check_results'][0]['result']
        checked['runner_result']['sha256']='0'*64
        conflicting={**recovery,'result_sha256':'0'*64}
        ledger.write_text(json.dumps(changed)+'\n')
        archive.write_text(wf.dump({**receipt,'runner_result':checked['runner_result'],'record':checked,
                                     'request_digest':wf.digest(wf.dump(conflicting).encode())}))
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.reconcile_check(self.store,conflicting)
        changed=json.loads(json.dumps(outcome))
        checked=changed['check_results'][0]['result']
        checked['cleanup']='Substituted local operation cleanup.'
        ledger.write_text(json.dumps(changed)+'\n')
        archive.write_text(wf.dump({**receipt,'record':checked}))
        with self.assertRaisesRegex(wf.WorkflowError,'differs from the original retained runner result'):
            wf.reconcile_check(self.store,recovery)
        ledger.write_bytes(ledger_bytes)
        archive.write_bytes(archive_bytes)
        self.assertEqual(wf.reconcile_check(self.store,recovery),receipt)
    def git(self,*args,cwd=None):
        return subprocess.check_output(['git',*args],cwd=cwd or self.root,text=True,stderr=subprocess.STDOUT).strip()

    def review_candidate(self,tid,controller=False,*,record_result=True):
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgSign','false')
        self.git('add','.')
        self.git('commit','-qm','Fixture baseline')
        if controller:
            wf.workspaces.setup(self.store,{})
            scope=wf.Store(self.root,allow_unselected=True,neutral=True)
            run=wf.start(scope,'next',tid,workspace={'implementation_operation':'work-through-next'})
            source=Path(wf.workspaces.runtime(self.root)['worktrees'][run['id']])
            self.store=wf.Store(source,run['id'])
            wf.begin_task(self.store,{'task_id':tid})
        else:
            wf.begin_task(self.store,{'task_id':tid,'implementation_operation':'implement-next'})
        (self.store.source_root/'source.py').write_text('value = 2\n')
        marked=wf.mark_implemented(self.store,{'task_id':tid,'changed_files':['source.py']})
        return marked['git_review_identity'],self.passed(tid) if record_result else None

    def review_change(self,frame,command,store=None,**payload):
        return wf.orchestration_action(store or self.store,'orchestration-'+command,{
            'orchestration_id':frame['id'],'expected_orchestration_hash':frame['orchestration_hash'],
            'expected_orchestration_revision':frame['revision'],'expected_source_hash':wf.file_hash(self.store.future),**payload})

    def review_frame(self,scope,identity):
        fingerprint=wf.digest(wf.dump(scope).encode())
        context={**scope,'id':'review-fixture-'+fingerprint,'semantic_fingerprint':fingerprint,
                 'content_fingerprint':fingerprint}
        actor={'id':'fixture-owner','context_id':'fixture-owner-context'}
        frame=wf.orchestration_action(self.store,'orchestration-start',{
            'request_id':wf.identity('fixture'),'context':context,'mode':'manual','executor':{'id':'fixture-executor','context_id':'fixture-executor-context'},
            'authority':{'id':'fixture-authorization','revision':1,'context_id':context['id'],
                         'allowed_kinds':['specification-acceptance'],'constraints':['Only synthetic fixture decisions.'],
                         'evidence':{'kind':'owner-message','reference':'Synthetic fixture authority.'}},
            'expected_source_hash':wf.file_hash(self.store.future)})
        frame=self.review_change(frame,'research',reference='Fixture scope inspected.')
        frame=self.review_change(frame,'plan',plan_digest=fingerprint,required_checks=['behavior'],reference='Fixture review plan.')
        frame=self.review_change(frame,'question',purpose='plan',question={
            'id':'fixture','kind':'specification-acceptance','text':'Accept the fixture plan?',
            'options':[{'id':'accept','text':'Accept.'},{'id':'revise','text':'Revise.'}],'recommendation':'accept'})
        def action(frame):
            return wf.orchestration_action(self.store,'orchestration-next',{'orchestration_id':frame['id']})
        next_step=action(frame)
        frame=self.review_change(frame,'prepare-actor',actor=actor,input_digest=next_step['input_digest'],expected_decision_hash=next_step['decision_hash'])
        next_step=action(frame)
        frame=self.review_change(frame,'record-actor',attempt_id=frame['prepared_actor']['attempt_id'],
            input_digest=next_step['input_digest'],expected_decision_hash=next_step['decision_hash'],
            result={'status':'answered','answer':'accept','rationale':'The synthetic plan matches the fixture.'},
            evidence={'kind':'submitted-answer','reference':'Fixture answer.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        frame=self.review_change(frame,'accept-decision')
        frame=self.review_change(frame,'accept-plan',decision_receipt=frame['acceptance'])
        return self.review_change(frame,'implement',identity=identity,reference='Current Git fixture candidate.')

    def test_compatible_worktree_refresh_preserves_the_selected_checkpoint(self):
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgSign','false')
        self.git('remote','add','origin',str(self.root.parent/'unused-fixture-origin.git'))
        package={'name':'worktree-profile-fixture','description':'Original metadata'}
        (self.root/'package.json').write_text(json.dumps(package)+'\n')
        (self.root/'.gitignore').write_text('/.agents/\n/.skill-tree/installation/\n')
        self.git('add','.')
        self.git('commit','-qm','Record original owned profile inputs')
        subprocess.run(['node', str(CORE/'bin/install.js'),'--target',str(self.root),'--only','codex',
                        '--flavor','general','--skills','skill-tree-work-through-next'],
                       check=True,capture_output=True,text=True,timeout=30)
        wf.workspaces.setup(self.store,{})
        selected_id=self.task('Selected compatible checkpoint')
        other_id=self.task('Independent stopped checkpoint')

        def start(task):
            run=wf.start(wf.Store(self.root,allow_unselected=True,neutral=True),'next',task,workspace={
                'base_branch':'develop','local_base':True,'local_base_authorization':'Use the exact local fixture base.',
            })
            source=Path(run['profile_handoff']['worktree'])
            store=wf.Store(source,run['id'])
            wf.prepare_worktree_profile(store)
            return run,store

        other,other_store=start(other_id)
        wf.checkpoint(other_store,{'phase':'blocked','stop_reason':'Retain the independent fixture stop'})
        original,selected=start(selected_id)
        self.store=selected
        wf.begin_task(selected,{'task_id':selected_id})
        self.passed(selected_id)
        attempt=wf.prepare_check(selected,{'task_id':selected_id,'check_id':'behavior'})
        wf.checkpoint(selected,{'phase':'blocked','stop_reason':'Wait for separate product approval'})
        with self.assertRaisesRegex(wf.WorkflowError,'original check attempt'):
            wf.compatible_profile_admission(selected)
        wf.record_check(selected,{'task_id':selected_id,'check_id':'behavior','attempt_id':attempt['attempt_id'],
            'result':'pass','actual_lane':'static','environment_identity':attempt['environment_identity'],
            'classification':'executed-control','assertions':[{'assertion':'The value remains observable.','result':'pass'}],
            'evidence':['report.json'],'cleanup':'No product process was launched.'})
        resource=wf.workspaces.resource(selected,{'resource':'fixture-editor'})
        with self.assertRaisesRegex(wf.WorkflowError,'original runtime resource'):
            wf.compatible_profile_admission(selected)
        wf.workspaces.resource(selected,{'resource':'fixture-editor','release':True,'token':resource['token']})
        worker=selected.base/'history/worker-handoffs'/f"{original['id'].lower()}.json"
        worker.parent.mkdir(parents=True,exist_ok=True)
        worker.write_text(json.dumps({'schema':1,'run_id':original['id'],'slots':{
            '1':[{'task_id':selected_id,'worker_id':'fixture-worker'}]}}))
        with self.assertRaisesRegex(wf.WorkflowError,'original worker handoff'):
            wf.compatible_profile_admission(selected)
        worker.unlink()
        canonical_state=selected.state.read_bytes()
        source=selected.source_root
        profile=source/'.skill-tree/installation/profile.json'
        former=profile.read_bytes()
        original_package=(source/'package.json').read_bytes()
        (source/'package.json').write_text(json.dumps({**package,'dependencies':{'fixture-module':'2.0.0'}})+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'material or unexplained'):
            wf.compatible_profile_admission(selected)
        self.assertEqual((selected.state.read_bytes(),profile.read_bytes()),(canonical_state,former))
        (source/'package.json').write_text(json.dumps({**package,'description':'Compatible description'})+'\n')
        browser=source/'config/browser-policy.json'
        browser.parent.mkdir()
        browser.write_text('{}\n')
        with self.assertRaisesRegex(wf.WorkflowError,'material or unknown'):
            wf.compatible_profile_admission(selected)
        self.assertEqual((selected.state.read_bytes(),profile.read_bytes()),(canonical_state,former))
        browser.unlink()
        with self.assertRaisesRegex(wf.WorkflowError,'original linked worktree'):
            wf.compatible_profile_admission(wf.Store(self.root,original['id']))
        self.assertNotEqual((source/'package.json').read_bytes(),original_package)
        activation=wf.owned_profile_installer
        claim={}

        def changed_checkpoint(store,request,mode,**options):
            if mode=='activate' and not claim:
                claim.update(wf.workspaces.resource(selected,{'resource':'fixture-before-activation'}))
            return activation(store,request,mode,**options)

        with patch.object(wf,'owned_profile_installer',changed_checkpoint):
            with self.assertRaisesRegex(wf.WorkflowError,'original compatible readmission checkpoint'):
                wf.compatible_profile_admission(selected)
        self.assertEqual(profile.read_bytes(),former)
        wf.workspaces.resource(selected,{'resource':'fixture-before-activation','release':True,'token':claim['token']})
        installed=wf.compatible_profile_admission(selected)
        self.assertEqual(installed['status'],'admitted')
        self.assertNotEqual(profile.read_bytes(),former)
        state=json.loads(selected.state.read_text())
        previous=json.loads(canonical_state)
        current=state['run_registry']['runs'][original['id']]
        self.assertEqual(current['current_task_id'],selected_id)
        self.assertEqual(current['stop_reason'],'Wait for separate product approval')
        self.assertEqual(current['phase'],'blocked')
        self.assertEqual(state['task_progress'],previous['task_progress'])
        self.assertEqual(state['run_registry']['claims'],previous['run_registry']['claims'])
        self.assertEqual(state['run_registry']['runs'][other['id']],previous['run_registry']['runs'][other['id']])
        self.assertEqual(current['admission'],installed['admission'])
        self.assertNotIn(str(source),json.dumps(current['compatible_profile_readmissions']))
        self.assertEqual(wf.compatible_profile_admission(selected),{**installed,'replayed':True})

    def test_full_cycle_brief_projects_exact_checks_and_preserves_attempts(self):
        cfg = self.store.base/'config/repository.json'
        cfg.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'point-unit':{'lane':'unit','argv':['runner','{project_root}','{selection}'],'input_paths':[]},
            'scoped-browser':{'lane':'browser','argv':['browser','{project_root}'],'input_paths':[]},
            'full-suite':{'lane':'unit','argv':['run-all'],'input_paths':[],
                          'delivery_validation':{'path':'suite.json','check_id':'full'}},
        }}))
        (self.store.base/'worktree-profile.json').write_text(json.dumps(
            {'schema':1,'exclusive_resources':['browser:test']}))
        tid = self.task('Worker scope', group=wf.identity('VG'))
        text = self.store.text()
        original = wf.check_specs(wf.resolve(wf.parse(text),[tid])[0])
        common = original[0]
        checks = [
            {**common,'id':'focused','recipe_id':'point-unit','parameters':{'selection':'one.spec'}},
            {**common,'id':'manual'},
            {**common,'id':'boundary','recipe_id':'scoped-browser','timing':'before-dependent-work'},
            {**common,'id':'final','recipe_id':'full-suite'},
            {**common,'id':'unavailable','recipe_id':'missing'},
        ]
        text = text.replace(json.dumps({'checks':original}),json.dumps({'checks':checks}))
        with self.store.lock():
            self.store.save(text,self.store.load())
        wf.start(self.store,'next',tid)
        state = self.store.load()
        state['active_run']['delivery'] = {'authorization':{'pr':True}}
        with self.store.lock():
            self.store.save(text,state)
        raw = self.store.state.read_bytes()
        result = wf.next_task(self.store)
        self.assertEqual(self.store.state.read_bytes(),raw)
        brief = result['worker_brief']
        self.assertEqual(brief['task_id'],tid)
        self.assertEqual(brief['run_id'],state['active_run']['id'])
        self.assertEqual(brief['checkout'],str(self.root.resolve()))
        self.assertEqual(brief['runtime_resource_claims'],
                         [{'resource':'browser:test','status':'unclaimed','holder_run_id':None}])
        rows = {row['check_id']:row for row in brief['checks']}
        self.assertEqual(rows['focused']['execution_owner'],'worker')
        self.assertEqual(rows['focused']['argv'],['runner',str(self.root.resolve()),'one.spec'])
        self.assertEqual(rows['focused']['evidence_owner'],'coordinator')
        self.assertEqual(rows['focused']['receipt']['executed_pass_shape'],'counts')
        self.assertEqual(rows['manual']['status'],'coordinator-check')
        self.assertEqual(rows['boundary']['timing'],'before-dependent-work')
        self.assertTrue(rows['boundary']['execution']['required'])
        self.assertIn('session_identity',rows['boundary']['execution']['fields'])
        self.assertEqual(rows['final']['status'],'delivery-validation-only')
        self.assertNotIn('argv',rows['final'])
        self.assertEqual(rows['unavailable']['status'],'prerequisite')
        self.assertEqual(wf.advance(self.store)['worker_brief'],brief)
        self.assertEqual(wf.begin_task(self.store,{'task_id':tid})['worker_brief'],brief)
        self.assertEqual(wf.validation_preflight(self.store,{'task_id':tid,'check_id':'focused'})['receipt'],
                         rows['focused']['receipt'])
        self.assertEqual(wf.validation_preflight(self.store,{'task_id':tid,'check_id':'final'})['status'],
                         'delivery-validation-only')
        with self.assertRaisesRegex(wf.WorkflowError,'Source changed'):
            wf.validation_preflight(self.store,{'task_id':tid,'check_id':'focused','expected_source_hash':'stale'})
        with self.assertRaisesRegex(wf.DeliveryOnlyRecipe,'requires the declared PR final validation phase'):
            wf.prepare_check(self.store,{'task_id':tid,'check_id':'final'})
        self.assertFalse(self.store.load()['task_progress'][tid]['checks'])
        attempt = wf.prepare_check(self.store,{'task_id':tid,'check_id':'focused'})
        self.assertEqual(attempt['recipe']['argv'],rows['focused']['argv'])
        resumed = wf.next_task(self.store)['worker_brief']['checks'][0]
        self.assertEqual(resumed['status'],'pending-attempt')
        self.assertEqual(resumed['attempt_id'],attempt['attempt_id'])
        self.assertNotIn('argv',resumed)

    def test_worker_brief_keeps_profile_recipe_drift_visible(self):
        tid = self.task('Delivery scope',recipe='full-suite')
        wf.start(self.store,'next',tid)
        state = self.store.load()
        path = self.root/'suite.json'
        path.write_text('before')
        profile_path = self.store.base/'installation/profile.json'
        profile_path.parent.mkdir()
        profile_path.write_text(json.dumps({
            'recipes':{'full-suite':{'lane':'unit','argv':['run-all'],'input_paths':['suite.json'],
                                     'delivery_validation':{'path':'suite.json','check_id':'full'}}},
            'inputs':{'suite.json':wf.file_hash(path)},
        }))
        selected = wf.resolve(wf.parse(self.store.text()),[tid])[0]
        prepared = wf.focused_worker_brief(self.store,state,selected,wf.check_specs(selected))
        self.assertEqual(prepared['checks'][0]['status'],'delivery-validation-only')
        path.write_text('after')
        stale = wf.focused_worker_brief(self.store,state,selected,wf.check_specs(selected))
        self.assertEqual(stale['checks'][0]['status'],'prerequisite')
        self.assertIn('Profile refresh-required',stale['checks'][0]['prerequisite'])
        self.assertNotIn('argv',stale['checks'][0])

    def test_worker_brief_refuses_a_profile_changed_while_resolving_rows(self):
        tid = self.task('One pinned profile',recipe='focused',independent_source='report.json')
        wf.start(self.store,'next',tid)
        state = self.store.load()
        path = self.store.base/'installation/profile.json'
        path.parent.mkdir()
        profile = {'recipes':{'focused':{'lane':'unit','argv':['old-command'],'input_paths':[]}}}
        path.write_text(json.dumps(profile))
        selected = wf.resolve(wf.parse(self.store.text()),[tid])[0]
        native_recipe = wf.recipe_for
        def change_profile(*args, **kwargs):
            resolved = native_recipe(*args, **kwargs)
            profile['recipes']['focused']['argv'] = ['new-command']
            path.write_text(json.dumps(profile))
            return resolved
        with patch.object(wf,'recipe_for',side_effect=change_profile):
            with self.assertRaisesRegex(wf.WorkflowError,'Worker handoff inputs changed'):
                wf.focused_worker_brief(self.store,state,selected,wf.check_specs(selected))

    def test_independent_builtin_check_ignores_unrelated_declaration_drift(self):
        tid = self.task('Independent inspection')
        wf.start(self.store,'next',tid)
        installed = self.store.base/'installation/profile.json'
        installed.parent.mkdir()
        installed.write_text(json.dumps({'identity':'repository-local','recipes':{}}))
        self.store.base.joinpath('validation-recipes.json').write_text('temporarily invalid')
        self.progress(tid)
        result = wf.validation_preflight(self.store,{'task_id':tid,'check_id':'behavior'})
        self.assertEqual(result['lane'],'static')
        self.assertEqual(self.passed(tid)['result'],'pass')

    def test_changed_playwright_receipt_reopens_only_completed_browser_check(self):
        primary = self.root / 'playwright.config.ts'
        primary.write_text('export default { timeout: 1000 };\n')
        (self.root / 'independent.py').write_text('value = 1\n')
        task_id = self.task('Browser proof with independent check',recipe='fixture-browser',
                            independent_source='independent.py')
        current = self.store.future.read_text()
        self.store.future.write_text(current.replace(
            '"id": "independent", "recipe_id": "fixture-browser"',
            '"id": "independent", "recipe_id": "static-inspection"'))
        wf.start(self.store,'next',task_id)
        path = self.store.base / 'installation/profile.json'
        path.parent.mkdir()
        profile = {'identity':'repository-local','flavor':'web','inputs':{'playwright.config.ts':wf.file_hash(primary)},
                   'recipes':{'fixture-browser':{'lane':'browser','input_paths':[]}}}
        path.write_text(json.dumps(profile))
        self.progress(task_id)
        execution = dict.fromkeys(wf.EXECUTION_FIELDS,'fixture')
        execution.update(project_root=str(self.root),cleanup_seconds=5,identity_evidence=['report.json'],
                         deadline_utc=(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat())
        prepared = wf.prepare_check(self.store,{'task_id':task_id,'check_id':'behavior','execution':execution})
        wf.record_check(self.store,{'task_id':task_id,'check_id':'behavior','attempt_id':prepared['attempt_id'],
             'classification':'executed-control','result':'pass','actual_lane':'browser',
             'environment_identity':prepared['environment_identity'],
             'counts':{'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0},
             'cleanup':'The simulated Browser runner exited.','evidence':['report.json']})
        control=self.passed(task_id,'independent')
        completed=wf.complete(self.store,{'task_id':task_id,'outcome':'The Browser and static checks passed.',
                    'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                    'source_fingerprints':wf.fingerprints(self.store,['source.py','independent.py'])})
        original=wf.validation_task(self.store,task_id)
        kept,due=wf.completed_revalidation_checks(self.store,self.store.load(),original,completed)
        self.assertFalse(due)
        self.assertEqual(set(kept),{'behavior','independent'})
        primary.write_text('export default { timeout: 2000 };\n')
        profile['inputs']['playwright.config.ts']=wf.file_hash(primary)
        path.write_text(json.dumps(profile))
        kept,due=wf.completed_revalidation_checks(self.store,self.store.load(),original,completed)
        self.assertEqual(kept['independent']['result']['attempt_id'],control['attempt_id'])
        self.assertEqual([row['id'] for row in due],['behavior'])
        state=self.store.load()
        execution['session_identity']='fresh-browser-fixture'
        state['task_progress'][task_id]={'execution_sessions':{}}
        _,environment=wf.recipe_for(self.store,due[0])
        state['task_progress'][task_id]['execution_sessions'][environment]=execution
        fresh=wf.check_snapshot(self.store,original,due[0],state)
        self.assertNotEqual(fresh['environment_identity'],prepared['environment_identity'])

    def test_lane_preflight_matches_browser_and_server_receipts(self):
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'fixture-'+lane:{'lane':lane,'input_paths':[]}
            for lane in ('browser','server')
        }}))
        for lane in ('browser','server'):
            with self.subTest(lane=lane):
                counted = lane == 'browser'
                tid = self.task('Review '+lane,recipe='fixture-'+lane)
                request = {'task_id':tid,'check_id':'behavior',
                           'expected_source_hash':wf.file_hash(self.store.future)}
                payload = self.root/'validation-preflight.json'
                payload.write_text(json.dumps(request))
                before = self.store.state.read_bytes()
                command = ['python3','-B',str(CORE/'common/scripts/workflow-state.py'),
                           'validation-preflight',str(self.root),'--input',str(payload)]
                outcome = subprocess.run(command,text=True,capture_output=True)
                self.assertEqual(outcome.returncode,0,
                                 'Selected lane evidence contract unavailable: '+outcome.stdout+outcome.stderr)
                preview = json.loads(outcome.stdout)
                self.assertEqual(preview['lane'],lane)
                self.assertEqual(preview['source_hash'],request['expected_source_hash'])
                self.assertEqual(preview['content_fingerprint'],wf.clarification_baselines(
                    [wf.resolve(wf.parse(self.store.text()),[tid])[0]])[tid]['content_hash'])
                self.assertEqual(preview['execution']['fields'],
                    ['project_root','authorization','profile_id','deadline_utc','cleanup_seconds',
                     'tool_identity','session_identity','fixture_identity','build_identity','identity_evidence'])
                self.assertEqual(preview['receipt']['executed_pass_shape'],'counts' if counted else 'assertions')
                self.assertEqual(preview['receipt']['behavioral_red_allowed'],counted)
                self.assertEqual('red' in preview['receipt']['result_values'],counted)
                self.assertEqual(preview['receipt']['results_requiring_evidence_and_executed_control'],
                                 ['pass','red'] if counted else ['pass'])
                self.assertEqual(preview['receipt']['evidence_reference']['object_optional'],['sha256'])
                self.assertEqual(self.store.state.read_bytes(),before)
                self.assertFalse((self.store.base/'.writer-lock').exists())

                self.progress(tid)
                execution = dict.fromkeys(preview['execution']['fields'],'fixture')
                execution.update(project_root=str(self.root),cleanup_seconds=5,identity_evidence=['report.json'],
                                 deadline_utc=(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat())
                with self.assertRaisesRegex(wf.WorkflowError,'owned execution session'):
                    wf.prepare_check(self.store,request)
                attempt = wf.prepare_check(self.store,{**request,'execution':execution})
                receipt = {'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],
                           'actual_lane':lane,'environment_identity':attempt['environment_identity'],
                           'classification':'executed-control','result':'pass','evidence':['report.json'],
                           'cleanup':'The fixture starts no product processes.'}
                invalid = ({'counts':dict.fromkeys(preview['receipt']['count_fields'],0)} if counted
                           else {'assertions':[{'assertion':'Different assertion.','result':'pass'}]})
                with self.assertRaisesRegex(wf.WorkflowError,'Expected nonzero test discovery' if counted
                                            else 'matching assertions'):
                    wf.record_check(self.store,{**receipt,**invalid})
                valid = ({'counts':{'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0}} if counted
                         else {'assertions':[{'assertion':preview['receipt']['assertion'],'result':'pass'}]})
                with self.assertRaisesRegex(wf.WorkflowError,'Runner lane/environment'):
                    wf.record_check(self.store,{**receipt,**valid,'environment_identity':'unrelated'})
                if counted:
                    skipped = {'expected':1,'discovered':1,'passed':0,'failed':0,'skipped':1}
                    with self.assertRaisesRegex(wf.WorkflowError,'Failed or skipped required tests'):
                        wf.record_check(self.store,{**receipt,'counts':skipped})
                else:
                    with self.assertRaisesRegex(wf.WorkflowError,'cannot establish behavioral Red'):
                        wf.record_check(self.store,{**receipt,**valid,'result':'red'})
                self.assertEqual(wf.record_check(self.store,{**receipt,**valid})['result'],'pass')

    def test_preflight_resolves_only_the_exact_run_and_task(self):
        admitted = self.task('Admitted')
        other = self.task('Outside the snapshot')
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgSign','false')
        self.git('add','.')
        self.git('commit','-qm','Fixture baseline')
        wf.workspaces.setup(self.store,{})
        scope = wf.Store(self.root,allow_unselected=True,neutral=True)
        run = wf.start(scope,'next',admitted,workspace={'implementation_operation':'work-through-next'})
        store = wf.Store(self.root,run['id'])
        request = {'task_id':admitted,'check_id':'behavior'}
        before = self.store.state.read_bytes()
        preview = wf.validation_preflight(store,request)
        self.assertEqual(preview['run_id'],run['id'])
        self.assertNotEqual(preview['execution']['project_root'],str(self.root))
        self.assertEqual(wf.validation_preflight(wf.Store(self.root),request),preview)
        with self.assertRaisesRegex(wf.WorkflowError,'outside the admitted controller scope'):
            wf.validation_preflight(wf.Store(self.root),{**request,'task_id':other})
        with self.assertRaisesRegex(wf.WorkflowError,'exact check ID'):
            wf.validation_preflight(store,{**request,'check_id':'missing'})
        with self.assertRaisesRegex(wf.workspaces.RunError,'Unknown run ID'):
            wf.validation_preflight(wf.Store(self.root,wf.identity('WR')),request)
        self.assertEqual(self.store.state.read_bytes(),before)
        scope = wf.Store(self.root,allow_unselected=True,neutral=True)
        wf.start(scope,'next',other,workspace={'implementation_operation':'work-through-next'})
        with self.assertRaisesRegex(wf.workspaces.RunError,'Multiple runs exist'):
            wf.validation_preflight(wf.Store(self.root),request)
        self.assertEqual(wf.validation_preflight(store,request),preview)

    def test_boundary_preflight_names_required_metadata_and_retains_strict_writers(self):
        group = wf.identity('VG')
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'fixture-browser':{'lane':'browser','input_paths':[]},
        }}))
        tid = self.task('Boundary candidate',group,timing='group-end',recipe='fixture-browser')
        request = {'task_id':tid,'check_id':'behavior'}
        good = wf.validation_preflight(self.store,request)
        state = self.store.state.read_bytes()
        original = self.store.future.read_bytes()
        windows = original.replace(b'\n',b'\r\n')
        self.store.future.write_bytes(windows)
        crlf = wf.validation_preflight(self.store,{**request,'expected_source_hash':wf.file_hash(self.store.future)})
        self.assertNotEqual(crlf['source_hash'],good['source_hash'])
        self.assertEqual(crlf['semantic_fingerprint'],good['semantic_fingerprint'])
        self.assertEqual(self.store.future.read_bytes(),windows)
        source = original.replace(b'boundary_validation: group-end\n',b'',1)
        self.assertNotEqual(source,original)
        self.store.future.write_bytes(source)
        with self.assertRaisesRegex(wf.WorkflowError,'Source changed'):
            wf.validation_preflight(self.store,{**request,'expected_source_hash':good['source_hash']})
        observed = wf.validation_preflight(self.store,request)
        self.assertEqual(observed['status'],'boundary-metadata-required')
        self.assertEqual(observed['lane'],'browser')
        self.assertEqual(observed['receipt']['executed_pass_shape'],'counts')
        self.assertNotEqual(observed['content_fingerprint'],good['content_fingerprint'])
        self.assertNotEqual(observed['semantic_fingerprint'],good['semantic_fingerprint'])
        self.assertEqual(observed['missing_boundary_classification'],[{
            'check_id':'behavior','field':'boundary_validation','timing':'group-end',
            'supported':['group-end','before-dependent-work'],
        }])
        with self.assertRaisesRegex(wf.WorkflowError,'Boundary check requires task boundary'):
            wf.prepare_check(self.store,request)
        self.assertEqual(self.store.future.read_bytes(),source)
        self.assertEqual(self.store.state.read_bytes(),state)
        bad_check = source.replace(b'"timing": "group-end"',b'"timing": "unsupported"',1)
        self.store.future.write_bytes(bad_check)
        with self.assertRaisesRegex(wf.WorkflowError,'explicit boundary timing'):
            wf.validation_preflight(self.store,request)

    def test_review_incorporates_actual_check_only_and_revalidates_artifacts_before_review(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        frame=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        candidates=wf.orchestration_action(self.store,'orchestration-check-evidence',{'orchestration_id':frame['id']})
        self.assertEqual(candidates['identity'],identity)
        offer=candidates['checks'][0]
        self.assertEqual(offer['attempt_id'],receipt['attempt_id'])
        self.assertEqual(offer['status'],'reusable')
        request={key:offer[key] for key in ('id','task_id','check_id','attempt_id')}
        with self.assertRaisesRegex(wf.WorkflowError,'verified receipt'):
            self.review_change(frame,'checks',identity=identity,results=[{'id':'behavior','status':'passed','reference':'core-check:invented'}])
        with self.assertRaisesRegex(wf.WorkflowError,'identity changed'):
            self.review_change(frame,'checks',identity=identity,reused_checks=[{**request,'attempt_id':wf.identity('C')}])
        adopted=self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        self.assertEqual(adopted['phase'],'review')
        self.assertEqual(adopted['checks']['results'][0]['core_check']['receipt_sha256'],offer['receipt_sha256'])
        report=self.root/'report.json';original_report=report.read_bytes();report.write_text('Changed result.')
        acceptance={'identity':identity,'review_id':'reviewer-proof','findings':[],'reference':'Independent fixture review.'}
        with self.assertRaisesRegex(wf.WorkflowError,'evidence missing or mismatched'):
            self.review_change(adopted,'review',**acceptance)
        report.write_bytes(original_report)
        task_source=self.root/'source.py';task_source.write_text('value = 3\n')
        with self.assertRaisesRegex(wf.WorkflowError,'sealed task candidate'):
            self.review_change(adopted,'review',**acceptance)
        task_source.write_text('value = 2\n')
        self.assertEqual(self.review_change(adopted,'review',**acceptance)['phase'],'ready')

    def test_review_declines_fresh_pending_or_changed_environment_checks(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        scope={'kind':'task','task_ids':[tid]}
        frame=self.review_frame({**scope,'fresh_check_ids':['behavior']},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        with self.assertRaisesRegex(wf.WorkflowError,'fresh execution'):
            self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        config=self.store.base/'config/repository.json';original=config.read_bytes()
        config.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'static-inspection':{'lane':'static','input_paths':[],'assertion_contract':'Changed fixture contract.'}}}))
        rows=wf.review_check_evidence(self.store,identity,scope)
        self.assertEqual(rows[0]['status'],'rerun-required')
        self.assertIn('environment changed',rows[0]['reason'])
        config.write_bytes(original)
        wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        rows=wf.review_check_evidence(self.store,identity,scope)
        self.assertIn('pending',rows[0]['reason'])

    def test_fresh_review_contract_excludes_a_passing_task_receipt(self):
        tid=self.task(fresh_review=True);identity,_=self.review_candidate(tid)
        rows=wf.review_check_evidence(self.store,identity,{'kind':'task','task_ids':[tid]})
        self.assertEqual(rows[0]['status'],'rerun-required')
        self.assertIn('requires fresh review',rows[0]['reason'])

    def test_task_completion_recovers_prepared_commit_with_reused_review_evidence(self):
        tid=self.task();identity,receipt=self.review_candidate(tid)
        frame=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        frame=self.review_change(frame,'checks',identity=identity,reused_checks=[request])
        frame=self.review_change(frame,'review',identity=identity,review_id='fixture-review',findings=[],reference='Independent fixture review.')
        completion={'task_id':tid,'review_id':frame['id'],'outcome':'The observable value remains preserved.',
                    'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                    'source_fingerprints':wf.fingerprints(self.store,['source.py'])}
        apply_commit=wf.workspaces.apply_task_commit
        def interrupt_after_commit(*args):
            apply_commit(*args)
            raise RuntimeError('Interrupted before recording completion')
        with patch.object(wf.workspaces,'apply_task_commit',interrupt_after_commit):
            with self.assertRaisesRegex(RuntimeError,'Interrupted before recording completion'):
                wf.complete(self.store,completion)
        head=self.git('rev-parse','HEAD')
        self.assertNotEqual(head,identity['head'])
        self.assertEqual(self.store.load()['task_progress'][tid]['task_git_attempt']['commit'],head)
        self.assertEqual(wf.complete(self.store,completion)['task_git_commit']['commit'],head)

    def controller_with_accepted_leaf(self):
        tid=self.task();identity,receipt=self.review_candidate(tid,controller=True)
        neutral=wf.Store(self.store.source_root,allow_unselected=True,neutral=True)
        task_review=self.review_frame({'kind':'task','task_ids':[tid]},identity)
        request={'id':'behavior','task_id':tid,'check_id':'behavior','attempt_id':receipt['attempt_id']}
        task_review=self.review_change(task_review,'checks',store=neutral,identity=identity,reused_checks=[request])
        task_review=self.review_change(task_review,'review',identity=identity,review_id='fixture-task-review',findings=[],reference='Independent fixture review.')
        wf.complete(self.store,{'task_id':tid,'review_id':task_review['id'],'outcome':'The observable value remains preserved.',
            'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
            'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        return neutral,receipt,request

    def test_controller_offer_reuses_accepted_leaf_receipt_only_on_current_target(self):
        neutral,receipt,request=self.controller_with_accepted_leaf()
        controller=wf.controller_review_identity(self.store)
        self.assertEqual(controller['check_evidence'][0]['attempt_id'],receipt['attempt_id'])
        run_id=controller['review_scope']['run_id']
        before=wf.file_hash(self.store.state)
        timeline=wf.orchestration_action(neutral,'orchestration-timeline',{'run_ids':[run_id]})
        self.assertEqual(wf.file_hash(self.store.state),before)
        self.assertEqual(timeline['orchestrations'],[])
        run_timing=timeline['runs'][0];check_time=run_timing['check_intervals'][0]
        self.assertEqual((run_timing['run_id'],check_time['attempt_id'],check_time['status']),
                         (run_id,receipt['attempt_id'],'pass'))
        self.assertIsNotNone(check_time['seconds'])
        self.assertIsNone(run_timing['delivery_interval']['seconds'])
        with self.assertRaisesRegex(wf.WorkflowError,'distinct exact run ids'):
            wf.orchestration_action(self.store,'orchestration-timeline',{'run_ids':[run_id,run_id]})
        frame=self.review_frame(controller['review_scope'],controller['identity'])
        frame=self.review_change(frame,'checks',store=neutral,identity=controller['identity'],reused_checks=[request])
        self.assertEqual(frame['phase'],'review')
        self.git('commit','--quiet','--allow-empty','-m','Move fixture target')
        moved=wf.controller_review_identity(self.store)
        self.assertEqual(moved['identity'],controller['identity'])
        self.assertEqual(moved['check_evidence'],[])
        self.assertIn('source and target base',moved['check_evidence_unavailable'])
        with self.assertRaisesRegex(wf.WorkflowError,'source and target base'):
            self.review_change(frame,'review',identity=frame['identity'],review_id='fixture-controller-review',findings=[],reference='Independent fixture review.')

    def test_run_timeline_waits_for_verified_merge_before_recording_delivery_duration(self):
        neutral,_,request=self.controller_with_accepted_leaf()
        controller=wf.controller_review_identity(self.store)
        identity=controller['identity'];run_id=controller['review_scope']['run_id']
        frame=self.review_frame(controller['review_scope'],identity)
        frame=self.review_change(frame,'checks',store=neutral,identity=identity,reused_checks=[request])
        frame=self.review_change(frame,'review',store=neutral,identity=identity,review_id='fixture-controller-review',
                                 findings=[],reference='Independent fixture review.')
        frozen=wf.freeze_reviewed_controller(self.store,{'review_id':frame['id']})
        def delivery_timing():
            return wf.orchestration_action(neutral,'orchestration-timeline',{'run_ids':[run_id]})['runs'][0]['delivery_interval']
        self.assertEqual(delivery_timing()['started_at'],frozen['finished_at'])
        self.assertIsNone(delivery_timing()['seconds'])
        merged=wf.merge_reviewed_controller(self.store,{'owner_instruction':'Merge the isolated fixture locally.'})
        self.assertEqual(self.git('rev-parse','HEAD'),merged['delivery']['reviewed_merge']['commit'])
        observed=delivery_timing()
        self.assertEqual(observed['status'],'merged')
        self.assertEqual(observed['review_id'],frame['id'])
        self.assertTrue(wf.valid_id(observed['verified_delivery_event_id'],'E'))
        self.assertIsNotNone(observed['seconds'])
    def test_revalidation_impact_reports_exact_affected_consumers(self):
        (self.root/'shared').mkdir()
        (self.root/'shared/config.txt').write_text('format-one\n')
        (self.root/'unrelated.txt').write_text('independent data\n')
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'shared-static':{'lane':'static','input_paths':['shared/config.txt'],
                             'assertion_contract':'Review declared source and configuration inputs.'},
        }}))
        producer = self.task('Shared configuration consumer',recipe='shared-static')
        consumer = self.task('Dependent application',deps=[producer])
        outside = self.task('Unselected application',recipe='shared-static')
        wf.start(self.store,'next',consumer)
        if not hasattr(wf,'validation_impact'):
            self.fail('Affected revalidation preview is missing')
        before = (self.store.future.read_bytes(),self.store.state.read_bytes())
        affected = wf.validation_impact(self.store,{'paths':['shared/config.txt']})
        self.assertEqual(affected['paths'],['shared/config.txt'])
        self.assertEqual([(row['task_id'],row['check_id'],row['matched_paths'],row['consumer_ids'])
                          for row in affected['checks']],
                         [(producer,'behavior',['shared/config.txt'],[consumer])])
        self.assertNotIn(outside,[row['task_id'] for row in affected['checks']])
        self.assertEqual(wf.validation_impact(self.store,{'paths':['unrelated.txt']})['checks'],[])
        request = self.root/'impact-request.json'
        request.write_text(json.dumps({'paths':['shared/config.txt']}))
        output = subprocess.check_output(
            ['python3','-B',str(CORE/'common/scripts/workflow-state.py'),'validation-impact',str(self.root),
             '--input',str(request)], text=True)
        self.assertEqual(json.loads(output),affected)
        self.assertEqual((self.store.future.read_bytes(),self.store.state.read_bytes()),before)

    def test_final_revalidation_boundary_stages_exact_group_peers(self):
        group = wf.identity('VG')
        first = self.task('First shared contract',group=group)
        second = self.task('Second shared contract',group=group)
        wf.start(self.store,'all')
        for _ in (first,second):
            selected = wf.advance(self.store)['task_id']
            self.progress(selected)
            self.passed(selected)
            wf.complete(self.store,{'task_id':selected,'outcome':'The scoped value remains visible.',
                         'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                         'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        (self.root/'source.py').write_text('value = 3\n')
        handoff = wf.advance(self.store)
        lead = handoff['task_id']
        peer = next(task for task in (first,second) if task != lead)
        self.assertEqual(handoff['revalidation_bundle'],[
            {'from_task_id':lead,'from_check_id':'behavior','task_id':peer,'check_id':'behavior'},
        ])
        check_pass = self.passed(lead)
        self.assertEqual(wf.reuse_check(self.store,handoff['revalidation_bundle'][0])['attempt_id'],check_pass['attempt_id'])
        for task in (lead,peer):
            wf.accept_revalidation(self.store,{'task_id':task})
        self.assertEqual(wf.next_task(self.store)['phase'],'deferred-processing')

    def test_changed_recipe_input_holds_registered_consumer_until_current_verification(self):
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'shared-static':{'lane':'static','input_paths':['contract-config.txt'],
                             'assertion_contract':'Review declared source and configuration inputs.'},
        }}))
        (self.root/'contract-config.txt').write_text('original configuration\n')
        producer = self.task('Completed producer',recipe='shared-static')
        self.progress(producer)
        self.passed(producer)
        wf.complete(self.store,{'task_id':producer,'outcome':'The scoped value remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        intermediate = self.task('Completed intermediary',deps=[producer])
        self.progress(intermediate)
        self.passed(intermediate)
        wf.complete(self.store,{'task_id':intermediate,'outcome':'The scoped intermediate behavior remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        consumer = self.task('Ready consumer',deps=[intermediate])
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgsign','false')
        self.git('add','.')
        self.git('commit','-qm','Canonical fixture baseline')
        wf.workspaces.setup(self.store,{})
        run = wf.start(wf.Store(self.root,allow_unselected=True,neutral=True),'next',consumer,
                       workspace={'implementation_operation':'work-through-next'})
        self.assertEqual(set(run['required_ids']),{producer,intermediate,consumer})
        checkout = Path(wf.workspaces.runtime(self.root)['worktrees'][run['id']])
        self.store = wf.Store(checkout,run['id'])
        self.assertEqual(wf.next_task(self.store)['task_id'],consumer)
        (checkout/'contract-config.txt').write_text('changed common configuration\n')
        with self.assertRaisesRegex(wf.WorkflowError,'dependency.*'+producer):
            wf.begin_task(self.store,{'task_id':consumer})
        state = self.store.load()
        retained = {**state['active_run'], 'admitted_task_ids':[intermediate,consumer],
                    'required_ids':[intermediate,consumer]}
        outcomes = {item['task_id']:item for item in self.store.outcomes()}
        with self.assertRaisesRegex(wf.WorkflowError,'outside the frozen run scope.*'+producer):
            wf.first_completed_source_gap(self.store,{**state,'active_run':retained},outcomes)
        self.assertEqual(wf.advance(self.store)['task_id'],producer)
        for _ in range(2):
            attempt = wf.prepare_check(self.store,{'task_id':producer,'check_id':'behavior'})
            wf.record_check(self.store,{'task_id':producer,'check_id':'behavior','attempt_id':attempt['attempt_id'],
                'result':'fail','classification':'executed-control','actual_lane':'static',
                'environment_identity':attempt['environment_identity'],'failure_signature':'Fixture verification failed.',
                'evidence':['report.json'],'cleanup':'The fixture starts no product process.'})
        self.assertEqual(self.store.load()['task_progress'][producer]['stage'],'blocked')
        resumed = wf.resume_task(self.store,{'task_id':producer,'resolution':'Corrected the fixture condition.'})
        self.assertEqual(resumed['stage'],'awaiting-validation')
        self.passed(producer)
        wf.accept_revalidation(self.store,{'task_id':producer})
        self.assertEqual(wf.next_task(self.store)['task_id'],consumer)
        self.assertEqual(wf.begin_task(self.store,{'task_id':consumer})['phase'],'implement')

    def test_revalidation_retains_current_check_receipt_for_independent_inputs(self):
        (self.root/'independent.py').write_text('unrelated_value = 5\n')
        task = self.task('Two independently validated inputs',independent_source='independent.py')
        wf.start(self.store,'all')
        self.progress(task)
        self.passed(task)
        retained = self.passed(task,check_id='independent')
        wf.complete(self.store,{'task_id':task,'outcome':'The scoped value remains visible.',
                     'acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],
                     'source_fingerprints':wf.fingerprints(self.store,['source.py','independent.py'])})
        (self.root/'source.py').write_text('value = 3\n')
        handoff = wf.next_task(self.store)
        self.assertEqual([check['id'] for check in handoff['checks']],['behavior'])
        self.assertEqual(handoff['retained_check_ids'],['independent'])
        self.passed(task)
        wf.accept_revalidation(self.store,{'task_id':task})
        check = next(item for item in self.store.load()['active_run']['revalidated_checks'][task]
                     if item['check']['id']=='independent')
        self.assertEqual(check['result']['attempt_id'],retained['attempt_id'])

    def test_validation_impact_keeps_real_runtime_resource_conflict_visible(self):
        configuration = self.store.base/'config/repository.json'
        configuration.write_text(json.dumps({'schema':1,'role':'source','recipes':{
            'fixture-browser':{'lane':'browser','input_paths':['source.py'],'argv':['fixture-browser']},
        }}))
        (self.store.base/'worktree-profile.json').write_text(json.dumps({
            'schema':1,'exclusive_resources':['browser:fixture'],
        }))
        actor = self.task('Resource owner')
        candidate = self.task('Independent browser candidate',recipe='fixture-browser')
        self.git('init','-q','-b','develop')
        self.git('config','user.name','Fixture editor')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','commit.gpgsign','false')
        self.git('add','.')
        self.git('commit','-qm','Canonical fixture baseline')
        wf.workspaces.setup(self.store,{})
        owner = wf.Store(self.root,allow_unselected=True,neutral=True)
        first = wf.start(owner,'next',actor,workspace={'implementation_operation':'work-through-next'})
        wf.workspaces.resource(wf.Store(self.root,first['id']),{'resource':'browser:fixture'})
        next_owner = wf.Store(self.root,allow_unselected=True,neutral=True)
        second = wf.start(next_owner,'next',candidate,workspace={'implementation_operation':'work-through-next'})
        scoped = wf.Store(self.root,second['id'])
        view = wf.next_task(scoped)['validation_impact']
        self.assertEqual(view['checks'][0]['lane'],'browser')
        self.assertEqual(view['runtime_resources'],[
            {'resource':'browser:fixture','holder_run_id':first['id'],'status':'occupied'},
        ])
        with self.assertRaisesRegex(wf.workspaces.RunError,'exclusive resource'):
            wf.workspaces.environment(scoped,{'runtime':True})
        task = wf.resolve(wf.parse(scoped.text()),[candidate])[0]
        check = wf.check_specs(task)[0]
        _, environment = wf.recipe_for(scoped,check)
        artifact = wf.evidence_pointer(scoped,'report.json',required=True)
        historical = {environment:{'tool_identity':'fixture-runner','fixture_identity':'fixture-case',
                                   'build_identity':'fixture-package','identity_evidence':[artifact]}}
        state = scoped.load()
        accepted = wf.check_snapshot(scoped,task,check,state,historical_sessions=historical)
        self.assertEqual(accepted['recipe']['lane'],'browser')
        with self.assertRaisesRegex(wf.workspaces.RunError,'exclusive resource'):
            wf.check_snapshot(scoped,task,check,state)
        (scoped.source_root/'report.json').write_text('Changed artifact.\n')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence'):
            wf.check_snapshot(scoped,task,check,state,historical_sessions=historical)

    def test_registered_completion_lineage_must_match_the_applied_event(self):
        self.controller_with_accepted_leaf()
        original, = self.store.outcomes()
        task_id = original['task_id']
        self.assertEqual(wf.completed_dependency_order(self.store,{task_id:original},[task_id]),[task_id])
        ledger = self.store.owned(wf.OUTCOME_LEDGER)
        altered = {**original,'depends_on':[wf.identity('T')]}
        ledger.write_text(json.dumps(altered)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.prepare_check(self.store,{'task_id':task_id,'check_id':'behavior'})
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.accept_revalidation(self.store,{'task_id':task_id})

        alternate = self.store.source_root/'alternate-report.json'
        alternate.write_text('Replacement evidence.')
        substituted = json.loads(json.dumps(original))
        substituted['check_results'][0]['result']['evidence'] = [
            wf.evidence_pointer(self.store,'alternate-report.json',required=True),
        ]
        ledger.write_text(json.dumps(substituted)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)

        ledger.write_text(json.dumps(original)+'\n')
        state = self.store.load()
        run_id = self.store.run_id
        state['active_run'].pop('completed_contract_sha256s',None)
        state['run_registry']['runs'][run_id].pop('completed_contract_sha256s',None)
        with self.store.lock():
            self.store.save(self.store.text(),state)
        directory = self.store.base/'history/run-events'/run_id.lower()
        event_path, = [file for file in directory.glob('e-*.json')
                       if original in json.loads(file.read_text())['outcomes']]
        event = json.loads(event_path.read_text())
        event['outcomes'] = [altered if item==original else item for item in event['outcomes']]
        event_path.write_text(wf.dump(event))
        ledger.write_text(json.dumps(altered)+'\n')
        with self.assertRaisesRegex(wf.WorkflowError,'registered completion proof'):
            wf.next_task(self.store)

    def test_standalone_progress_survives_refresh_and_never_reimplements(self):
        tid=self.task();self.progress(tid)
        with self.store.lock():self.store.save(self.store.text(),self.store.load())
        self.assertEqual(wf.begin_task(self.store,{'task_id':tid})['phase'],'validate')
        self.assertEqual(self.store.load()['task_progress'][tid]['stage'],'awaiting-validation')
    def test_pending_stale_missing_and_changed_reports_cannot_complete(self):
        tid=self.task();self.progress(tid)
        with self.assertRaises(wf.WorkflowError):wf.validate_task_checks(self.store,tid)
        self.passed(tid);wf.validate_task_checks(self.store,tid)
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
        (self.root/'source.py').write_text('value = 2\n')
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.validate_task_checks(self.store,tid)
        self.passed(tid);(self.root/'report.json').write_text('changed artifact')
        with self.assertRaisesRegex(wf.WorkflowError,'evidence'):wf.validate_task_checks(self.store,tid)
    def test_group_batching_never_expands_next_scope_or_bypasses_verified_dependency(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end')
        wf.start(self.store,'next',a);self.progress(a)
        result=wf.next_task(self.store);self.assertEqual(result['phase'],'validate');self.assertEqual(result['task_id'],a)
        self.assertNotIn(b,self.store.load()['active_run']['admitted_groups'][group])
    def test_all_batches_only_eligible_declared_group_members(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');other=self.task('Unrelated')
        wf.start(self.store,'all');selected=wf.next_task(self.store)['task_id'];self.assertEqual(selected,other)
        # Explicitly scope the fixture to the two grouped roots.
        state=self.store.load();state['active_run']['snapshot']=[a,b];state['active_run']['root_task_id']=a
        with self.store.lock():self.store.save(self.store.text(),state)
        self.progress(a);self.assertEqual(wf.next_task(self.store)['task_id'],b)
        self.progress(b);self.assertEqual(wf.next_task(self.store)['phase'],'validate')
    def test_zero_discovery_and_wrong_lane_cannot_pass(self):
        tid=self.task();self.progress(tid);attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'pass','actual_lane':'unit','environment_identity':attempt['environment_identity'],'classification':'executed-control','counts':{'expected':1,'discovered':0,'passed':0,'failed':0,'skipped':0},'evidence':['report.json'],'cleanup':'Complete.'})
    def test_unchanged_attempts_are_not_semantic_progress(self):
        tid=self.task();wf.start(self.store,'next');self.progress(tid);wf.record_cycle(self.store)
        wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});result=wf.record_cycle(self.store);self.assertEqual(result['phase'],'blocked')
    def test_mandatory_runtime_decision_without_check_mapping_is_rejected(self):
        with self.assertRaises(wf.WorkflowError):
            wf.check_specs({'body':'Validation:\n- Run tests.\nAcceptance:\n- Preserve the value.','boundary_validation':'not-required'})

    def complete(self,tid):
        self.passed(tid)
        return wf.complete(self.store,{'task_id':tid,'outcome':'The observable value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
    def test_shared_check_reuse_finalizes_group_once_and_retains_specification_until_verified(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');wf.start(self.store,'all');self.progress(a);self.progress(b)
        self.passed(a);wf.reuse_check(self.store,{'from_task_id':a,'from_check_id':'behavior','task_id':b,'check_id':'behavior'})
        record=wf.complete(self.store,{'task_id':a,'outcome':'The observable value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        self.assertEqual(record['task_id'],a);wf.validate_task_checks(self.store,b)
        self.assertNotIn(a,self.store.load()['task_progress']);self.assertIn(b,self.store.text());self.assertEqual(wf.next_task(self.store)['phase'],'validate')
        self.complete(b);wf.finish(self.store);self.assertEqual(len(self.store.outcomes()),2)
    def test_group_dependency_forces_upstream_verification_before_downstream_implementation(self):
        group=wf.identity('VG');a=self.task('Upstream',group,timing='group-end');b=self.task('Downstream',group,deps=[a],timing='group-end');wf.start(self.store,'next',b);self.progress(a)
        self.assertEqual(wf.next_task(self.store)['task_id'],a);self.assertEqual(wf.next_task(self.store)['phase'],'validate')
        with self.assertRaises(wf.WorkflowError):wf.begin_task(self.store,{'task_id':b})
        self.complete(a);self.assertEqual(wf.next_task(self.store)['task_id'],b)
    def test_changed_group_check_set_invalidates_affected_shared_evidence(self):
        group=wf.identity('VG');a=self.task('First',group,timing='group-end');b=self.task('Second',group,timing='group-end');wf.start(self.store,'all');self.progress(a);self.passed(a)
        text=self.store.text().replace('The value remains observable.','The value remains explicitly observable.',1);self.store.future.write_text(text)
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.validate_task_checks(self.store,a)
    def test_runtime_red_requires_behavioral_failure_and_nonzero_discovery(self):
        tid=self.task();text=self.store.text().replace('static-inspection','fixture-unit');self.store.future.write_text(text)
        config=self.store.base/'config';config.mkdir(exist_ok=True);(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source','recipes':{'fixture-unit':{'lane':'unit','argv':['fixture-runner'],'input_paths':[]}}}))
        self.progress(tid);attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
        payload={'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'red','actual_lane':'unit','environment_identity':attempt['environment_identity'],'classification':'executed-control','counts':{'expected':1,'discovered':1,'passed':0,'failed':1,'skipped':0},'failure_category':'runner-failure','evidence':['report.json'],'cleanup':'The isolated fixture stopped.'}
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,payload)
        payload['failure_category']='expected-behavior';wf.record_check(self.store,payload)
        self.assertIn('red',self.store.load()['task_progress'][tid]['checks']['behavior'])
        with self.assertRaises(wf.WorkflowError):wf.validate_task_checks(self.store,tid)
        next_attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});payload['attempt_id']=next_attempt['attempt_id']
        payload.update({'result':'pass','counts':{'expected':1,'discovered':0,'passed':0,'failed':0,'skipped':0}})
        with self.assertRaises(wf.WorkflowError):wf.record_check(self.store,payload)
        payload['counts']={'expected':1,'discovered':1,'passed':1,'failed':0,'skipped':0};wf.record_check(self.store,payload);wf.validate_task_checks(self.store,tid)
    def test_prepared_identity_blocks_changes_during_execution_and_launch_requires_a_deadline(self):
        tid=self.task();self.progress(tid)
        with self.assertRaises(wf.WorkflowError):wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior','launch':{'assertion':'Inspect the rendered value.'}})
        attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'});(self.root/'source.py').write_text('value = 3')
        with self.assertRaisesRegex(wf.WorkflowError,'stale'):wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id']})
    def test_only_two_unchanged_executed_failures_trip_the_circuit_breaker(self):
        tid=self.task();wf.start(self.store,'next');self.progress(tid)
        for classification in ['prerequisite-wait','transport-uncertainty','executed-control','executed-control']:
            attempt=wf.prepare_check(self.store,{'task_id':tid,'check_id':'behavior'})
            wf.record_check(self.store,{'task_id':tid,'check_id':'behavior','attempt_id':attempt['attempt_id'],'result':'fail' if classification=='executed-control' else 'unavailable','actual_lane':'static','environment_identity':attempt['environment_identity'],'classification':classification,'failure_signature':'fixture assertion failed','evidence':['report.json'],'cleanup':'The isolated fixture stopped.'})
        self.assertEqual(self.store.load()['task_progress'][tid]['stage'],'blocked')
        with self.assertRaises(wf.WorkflowError):wf.next_task(self.store)
    def test_completion_cannot_bypass_missing_progress_with_a_passing_payload(self):
        tid=self.task()
        with self.assertRaises(wf.WorkflowError):wf.complete(self.store,{'task_id':tid,'outcome':'The value remains preserved.','acceptance':[{'criterion':'Preserve the value.','result':'pass','evidence':['report.json']}],'source_fingerprints':wf.fingerprints(self.store,['source.py'])})
        self.assertIn(tid,self.store.text());self.assertEqual(self.store.outcomes(),[])

    def test_profile_admission_is_pinned_once_and_repeated_only_on_explicit_resume(self):
        tid=self.task()
        with patch.object(wf,'admit_profile',wraps=wf.admit_profile) as admission:
            wf.start(self.store,'next');self.progress(tid);self.passed(tid);self.assertEqual(admission.call_count,1)
            wf.resume_admission(self.store);self.assertEqual(admission.call_count,2)
    def test_direct_queue_edit_cannot_admit_a_new_required_task(self):
        a=self.task('Root');wf.start(self.store,'next',a);b=self.task('Late unrelated')
        self.store.future.write_text(wf.rewrite_meta(self.store.text(),a,{'depends_on':[b]}))
        with self.assertRaisesRegex(wf.WorkflowError,'not admitted'):wf.next_task(self.store)
    def test_missing_profile_blocks_implementation_but_leaves_intake_available(self):
        (self.store.base/'config/repository.json').unlink();tid=self.task()
        with self.assertRaisesRegex(wf.WorkflowError,'Missing installation profile'):wf.begin_task(self.store,{'task_id':tid})
        self.assertTrue(wf.intake(self.store,{'title':'Research setup','description':'Inspect the scoped setup.','expected_behavior':'Resolve the missing capability.'})['id'].startswith('P-'))

if __name__=='__main__':unittest.main()
