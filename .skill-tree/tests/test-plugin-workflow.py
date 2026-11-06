"""Guarded invocation fixtures are synthetic; actual host observations use a separate lane."""
import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

CORE = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    # State controls execute current authored bytes, independently of timestamp caches.
    exec(compile(path.read_bytes(), str(path), 'exec'), value.__dict__)
    return value

wf = load('hook_fixture_workflow', CORE / 'common/scripts/workflow-state.py')
sha = lambda value: hashlib.sha256(value.encode()).hexdigest()

def engine():
    # Lazy loading keeps every requirements-led case discoverable during Red.
    return load('hook_fixture_engine', CORE / 'common/scripts/plugin-invocation.py')

class QueueFreeStore(wf.Store):
    def text(self):
        raise AssertionError('Task-free hook metadata cannot load a Future queue')
    def load(self, *args, **kwargs):
        raise AssertionError('Task-free hook metadata cannot select a controller')
    def save(self, *args, **kwargs):
        raise AssertionError('Task-free hook metadata cannot save workflow state')

class PluginInvocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = QueueFreeStore(self.root, allow_unselected=True, neutral=True)

    def context(self, value='initial'):
        return {'kind':'request', 'id':'controlled-hook-request',
                'semantic_fingerprint':sha('meaning-' + value), 'content_fingerprint':sha('bytes-' + value),
                'accepted_marker':value}

    def authority(self):
        return {'id':'fixture-grant', 'revision':1, 'context_id':'controlled-hook-request',
                'allowed_kinds':['technical', 'product', 'specification-acceptance'],
                'constraints':['Controlled metadata fixture only; no network, installation or publication.'],
                'evidence':{'kind':'owner-message', 'reference':'Scripted fixture authority; no real-human business approval.'}}

    def row(self, identity='first-a', plugin='editor', **extra):
        values = {'nonce':identity, 'nested':[None, True, {'value':'данные'}]}
        instructions = 'Extra instruction nonce: ' + identity
        # The owned JS resolver is the parameter digest oracle, even in Python fixtures.
        command = "const p=require(process.argv[1]);process.stdout.write(JSON.stringify(p.resolveParameters({run:JSON.parse(process.argv[2])})));"
        result = subprocess.run(['node', '-e', command, str(CORE/'lib/plugin-parameters.js'),
                                 json.dumps({'values':values, 'instructions':instructions})],
                                capture_output=True, text=True, check=True)
        effective = json.loads(result.stdout)
        return {'id':identity, 'plugin_id':plugin, 'operation':'skill-tree-add-pending-task',
                'anchor':'before', 'enabled':True, 'effective':effective,
                'package_identity':{'revision':'a'*40, 'content_digest':sha(plugin)}, **extra}

    def request(self, rows=None):
        rows = [self.row()] if rows is None else copy.deepcopy(rows)
        configuration = {'configuration_digest':sha(json.dumps(rows, sort_keys=True)), 'bindings':rows,
                         'packages':{row['plugin_id']:{'revision':'a'*40, 'content_digest':sha(row['plugin_id']),
                            'entry':'plugins/'+row['plugin_id']+'/upstream/SKILL.md',
                            'resources':{'SKILL.md':sha(row['plugin_id']+'-source')}} for row in rows},
                         'run_overrides':{}}
        return {'request_id':'controlled-hook-start', 'event':{'id':'operation-event-one',
                'operation':'skill-tree-add-pending-task', 'anchor':'before'},
                'context':self.context(), 'mode':'manual', 'authority':self.authority(),
                'executor':{'id':'fixture-executor', 'context_id':'fixture-executor-context'},
                'configuration':configuration}

    def proof(self, request, rows=None, context=None):
        return {'configuration_digest':request['configuration']['configuration_digest'],
                'context':copy.deepcopy(context or request['context']), 'event':copy.deepcopy(request['event']),
                'bindings':copy.deepcopy(request['configuration']['bindings'] if rows is None else rows),
                'unresolved':[], 'prerequisites':[], 'execution_snapshot':{'controlled-owned-module':sha('source')}}

    def start(self, request=None, proof=None):
        request = request or self.request()
        return engine().start(self.store, request, proof=proof or self.proof(request))

    def change(self, frame, command, proof=None, verify_transition=None, guard=None, **extra):
        return engine().mutate(self.store, command, {'chain_id':frame['id'],
            'expected_chain_hash':frame['chain_hash'], 'expected_chain_revision':frame['revision'], **extra},
            proof=proof, verify_transition=verify_transition, guard=guard)

    def actor(self, suffix='one'):
        return {'id':'fixture-actor-'+suffix, 'context_id':'fixture-context-'+suffix}

    def creation(self, actor):
        return {'kind':'host-agent-created', 'provider':'controlled-unit-host', 'tool':'controlled-create',
                'reference':'Synthetic actor creation: '+actor['id'],
                'actor_id':actor['id'], 'actor_context_id':actor['context_id']}

    def prepared(self, frame, request, suffix='one', proof=None):
        actor = self.actor(suffix)
        return self.change(frame, 'prepare', proof=proof or self.proof(request),
                           actor=actor, creation_evidence=self.creation(actor))

    def attempt(self, frame):
        return frame['attempts'][frame['prepared_attempt_id']]

    def invoked(self, frame, request, proof=None):
        attempt = self.attempt(frame)
        evidence = {'kind':'host-invoked', 'provider':'controlled-unit-host', 'tool':'controlled-dispatch',
                    'reference':'Synthetic source-backed dispatch; never actual native qualification.',
                    'actor_id':attempt['actor']['id'], 'actor_context_id':attempt['actor']['context_id'],
                    'mechanism':'source-backed-context'}
        public = {'input_digest':attempt['input_digest'],
                  'delivery_digest':sha('delivery-'+attempt['input_digest']),
                  'resolved_parameter_digest':attempt['input']['parameter_digest']}
        trusted = copy.deepcopy(proof or self.proof(request)); trusted['delivery'] = public
        return self.change(frame, 'invoke', proof=trusted, attempt_id=attempt['id'], evidence=evidence, **public)

    def recorded(self, frame, request, status='passed', result=None, proof=None):
        attempt = self.attempt(frame)
        evidence = {'kind':'host-result', 'provider':'controlled-unit-host', 'tool':'controlled-result',
                    'reference':'Synthetic returned JSON; actual host observations are separate.',
                    'actor_id':attempt['actor']['id'], 'actor_context_id':attempt['actor']['context_id'],
                    'mechanism':'source-backed-context'}
        return self.change(frame, 'record', proof=proof or self.proof(request), attempt_id=attempt['id'],
                           input_digest=attempt['input_digest'],
                           delivery_digest=attempt['delivery_digest'],
                           resolved_parameter_digest=attempt['resolved_parameter_digest'],
                           result=result or {'status':status,'markers':{'parameter':attempt['input']['binding_id']}},
                           evidence=evidence)

    def accepted(self, frame, request, context=None, receipt=None, verifier=None, proof=None):
        attempt = self.attempt(frame)
        return self.change(frame, 'accept', proof=proof or self.proof(request, context=context),
                           verify_transition=verifier, attempt_id=attempt['id'],
                           input_digest=attempt['input_digest'], context=context or request['context'],
                           receipt=receipt)

    def returned(self, request=None, status='passed', suffix='one', frame=None, proof=None):
        request = request or self.request(); frame = frame or self.start(request)
        frame = self.prepared(frame,request,suffix,proof)
        frame = self.invoked(frame,request,proof)
        return request,self.recorded(frame,request,status,proof=proof)

    def core_receipt(self, before, after, kind='core-incorporation'):
        return {'kind':kind, 'reference':'Synthetic ordinary core revision receipt.',
                'before':engine().digest(before), 'after':engine().digest(after),
                'session_id':'CL-11111111-1111-4111-8111-111111111111',
                'task_revision_id':'controlled-revision-one', 'final_confirmation':False}

    def files(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def no_future(self):
        for path in ['documents/future.md', 'documents/future.json', 'clarifications']:
            self.assertFalse((self.root/'.skill-tree'/path).exists(), path)

    def test_public_state_and_pending_scan_interfaces_are_callable(self):
        module = engine()
        for name in ['start', 'read', 'next_action', 'mutate', 'pending_scan']:
            self.assertTrue(callable(getattr(module, name, None)), name)

    def test_task_free_start_persists_only_owned_hook_metadata_without_future(self):
        request = self.request(); frame = self.start(request)
        self.assertRegex(frame['id'], r'^HC-[a-f0-9-]{36}$')
        self.assertEqual(frame['context'], request['context'])
        self.assertEqual(frame['configuration'], request['configuration'])
        self.assertEqual(frame['cursor'], 0)
        self.assertEqual(engine().read(self.store, frame['id']), frame)
        self.no_future()

    def test_start_nonce_replay_is_nonmutating_and_conflicting_reuse_rejects(self):
        request = self.request(); frame = self.start(request); before = self.files()
        self.assertEqual(self.start(request), frame)
        self.assertEqual(self.files(), before)
        changed = copy.deepcopy(request); changed['configuration']['run_overrides'] = {'first-a':{'values':{'nonce':'changed'}}}
        with self.assertRaises(ValueError):
            self.start(changed)
        self.assertEqual(self.files(), before)

    def test_order_and_same_package_occurrence_identity_remain_frozen(self):
        rows = [self.row('first-a'), self.row('middle-b','interview'), self.row('last-a')]
        request = self.request(rows); frame = self.start(request)
        self.assertEqual([row['id'] for row in frame['configuration']['bindings']], ['first-a','middle-b','last-a'])
        self.assertEqual(frame['configuration']['bindings'][0]['plugin_id'], frame['configuration']['bindings'][2]['plugin_id'])
        request['configuration']['bindings'].reverse()
        self.assertEqual([row['id'] for row in engine().read(self.store, frame['id'])['configuration']['bindings']], ['first-a','middle-b','last-a'])
        self.assertEqual(engine().read(self.store, frame['id'])['cursor'], 0)

    def test_duplicate_occurrence_ids_reject_atomically(self):
        self.start(); request = self.request([self.row('duplicate'), self.row('duplicate')])
        request['request_id'] = 'duplicate-occurrences'; before = self.files()
        with self.assertRaisesRegex(ValueError, 'occurrence|binding|duplicate|distinct'):
            self.start(request)
        self.assertEqual(self.files(), before)

    def test_current_proof_cannot_substitute_scope_event_or_configuration(self):
        request = self.request(); self.start(request)
        for field, value in [('context', self.context('different')), ('event', {**request['event'],'id':'different-event'}),
                             ('configuration_digest','0'*64)]:
            bad = copy.deepcopy(request); bad['request_id'] = 'bad-proof-'+field
            proof = self.proof(bad); proof[field] = value; before = self.files()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'proof|context|scope|event|configuration'):
                self.start(bad, proof)
            self.assertEqual(self.files(), before)

    def test_untrusted_payload_proof_does_not_replace_required_trusted_argument(self):
        self.start(); request = self.request(); request['request_id']='untrusted-payload-proof'
        request['proof'] = self.proof(request); before = self.files()
        with self.assertRaises((ValueError, TypeError)):
            engine().start(self.store, request)
        self.assertEqual(self.files(), before)

    def test_typed_task_free_context_rejects_fabricated_task_identity(self):
        self.start(); request = self.request(); request['request_id']='fabricated-task'
        request['context']['task_ids'] = ['T-11111111-1111-4111-8111-111111111111']
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'context|task|identity'):
            self.start(request)
        self.assertEqual(self.files(), before)

    def test_explicit_overrides_are_frozen_before_any_attempt(self):
        request = self.request(); request['configuration']['run_overrides'] = {'first-a':{'values':{'marker':'run-only'}}}
        frame = self.start(request)
        self.assertEqual(frame['configuration']['run_overrides'], request['configuration']['run_overrides'])
        self.assertFalse(frame['attempts'])
        request['configuration']['run_overrides']['first-a']['values']['marker'] = 'mutated'
        self.assertEqual(engine().read(self.store, frame['id'])['configuration']['run_overrides']['first-a']['values']['marker'], 'run-only')

    def test_node_parameter_identity_is_not_recomputed_using_python_number_spelling(self):
        request = self.request(); row = request['configuration']['bindings'][0]
        values = {'small':1e-7,'negative_zero':-0.0,'unicode':'🧩','array':[False,None,{'authority':'ordinary data'}]}
        result = subprocess.run(['node','-e',"const p=require(process.argv[1]);process.stdout.write(JSON.stringify(p.resolveParameters({run:{values:JSON.parse(process.argv[2]),instructions:'number marker'}})));",str(CORE/'lib/plugin-parameters.js'),json.dumps(values)],capture_output=True,text=True,check=True)
        row['effective'] = json.loads(result.stdout)
        frame = self.start(request)
        self.assertEqual(frame['configuration']['bindings'][0]['effective'], row['effective'])
        python_digest = sha(json.dumps({'values':values,'instructions':'number marker'},sort_keys=True,separators=(',',':'),ensure_ascii=False))
        self.assertNotEqual(row['effective']['digest'], python_digest)

    def test_prepare_delivers_exact_reference_parameters_and_instruction_text(self):
        request=self.request();frame=self.prepared(self.start(request),request)
        attempt=self.attempt(frame);envelope=attempt['input'];row=request['configuration']['bindings'][0]
        self.assertRegex(attempt['id'],r'^HI-[a-f0-9-]{36}$')
        self.assertEqual(envelope['binding_id'],row['id']);self.assertEqual(envelope['context'],request['context'])
        self.assertEqual(envelope['parameters'],row['effective']['values'])
        self.assertEqual(envelope['extra_instructions'],row['effective']['instructions'])
        self.assertEqual(envelope['parameter_digest'],row['effective']['digest'])
        self.assertEqual(envelope['configuration_digest'],request['configuration']['configuration_digest'])
        self.assertEqual(engine().digest(envelope),attempt['input_digest']);self.no_future()

    def test_current_chain_hash_and_revision_guard_every_mutation(self):
        request=self.request();frame=self.start(request);before=self.files()
        for extra in [{'expected_chain_hash':'0'*64},{'expected_chain_revision':0}]:
            payload={'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],
                     'expected_chain_revision':frame['revision'],'actor':self.actor(),
                     'creation_evidence':self.creation(self.actor()),**extra}
            with self.subTest(extra=extra),self.assertRaisesRegex(ValueError,'hash|revision|changed|stale'):
                engine().mutate(self.store,'prepare',payload,proof=self.proof(request))
            self.assertEqual(self.files(),before)

    def test_prepared_original_blocks_duplicate_prepare_and_is_visible_to_install_barrier(self):
        request=self.request();frame=self.prepared(self.start(request),request);attempt=copy.deepcopy(self.attempt(frame));before=self.files()
        self.assertTrue(engine().pending_scan(self.store))
        with self.assertRaisesRegex(ValueError,'original|pending|prepare|attempt'):
            self.prepared(frame,request,'replacement')
        self.assertEqual(self.files(),before);self.assertEqual(self.attempt(engine().read(self.store,frame['id'])),attempt)

    def test_invoke_requires_original_actor_and_matching_trusted_delivery_identity(self):
        request=self.request();frame=self.prepared(self.start(request),request);attempt=self.attempt(frame)
        valid=self.invoked(frame,request);self.assertTrue(engine().pending_scan(self.store))
        before=self.files();wrong={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-dispatch',
            'reference':'Wrong original actor.','actor_id':'invented','actor_context_id':'invented-context',
            'mechanism':'source-backed-context'}
        with self.assertRaisesRegex(ValueError,'actor|original|conflict|evidence'):
            self.change(valid,'invoke',proof={**self.proof(request),'delivery':{'input_digest':attempt['input_digest'],
                'delivery_digest':sha('delivery-'+attempt['input_digest']),
                'resolved_parameter_digest':attempt['input']['parameter_digest']}},attempt_id=attempt['id'],
                input_digest=attempt['input_digest'],delivery_digest=sha('delivery-'+attempt['input_digest']),
                resolved_parameter_digest=attempt['input']['parameter_digest'],evidence=wrong)
        self.assertEqual(self.files(),before)

    def test_result_before_actual_dispatch_cannot_succeed(self):
        request=self.request();frame=self.prepared(self.start(request),request);attempt=self.attempt(frame);before=self.files()
        with self.assertRaisesRegex(ValueError,'invoke|dispatch|started|delivery|original'):
            self.change(frame,'record',proof=self.proof(request),attempt_id=attempt['id'],input_digest=attempt['input_digest'],
                delivery_digest=sha('never-dispatched'),resolved_parameter_digest=attempt['input']['parameter_digest'],
                result={'status':'passed'},evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
                'reference':'Synthetic premature result.','actor_id':attempt['actor']['id'],
                'actor_context_id':attempt['actor']['context_id'],'mechanism':'source-backed-context'})
        self.assertEqual(self.files(),before)

    def test_exact_returned_result_replays_but_conflicting_result_rejects(self):
        request,frame=self.returned();attempt=copy.deepcopy(self.attempt(frame));before=self.files()
        replay=self.recorded(frame,request,result=attempt['result'])
        self.assertEqual(self.files(),before);self.assertEqual(replay,frame)
        with self.assertRaisesRegex(ValueError,'conflict|original|replay|result'):
            self.recorded(frame,request,result={'status':'passed','markers':{'changed':'conflicting delivery'}})
        self.assertEqual(self.files(),before)

    def test_matching_passed_result_accepts_without_fabricating_a_core_edit(self):
        request,frame=self.returned();original=copy.deepcopy(self.attempt(frame));frame=self.accepted(frame,request)
        self.assertEqual(frame['cursor'],1)
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input'])
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=self.proof(request))['action'],'complete')
        self.assertEqual(engine().pending_scan(self.store),[]);self.no_future()

    def test_questions_and_findings_wait_for_actual_core_incorporation_evidence(self):
        for status in ['questions','findings']:
            request=self.request();request['request_id']='blocked-'+status
            request,frame=self.returned(request,status=status,suffix=status);before=self.files()
            self.assertIn(engine().next_action(self.store,frame['id'],proof=self.proof(request))['action'],{'resolve','prerequisite'})
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'core|receipt|resolution|incorporat|transition'):
                self.accepted(frame,request)
            self.assertEqual(frame['cursor'],0);self.assertEqual(self.files(),before)

    def test_failed_unavailable_and_cancelled_results_do_not_complete_required_chain(self):
        for status in ['failed','unavailable','cancelled']:
            request=self.request();request['request_id']='terminal-'+status
            request,frame=self.returned(request,status=status,suffix=status);before=self.files()
            self.assertNotEqual(engine().next_action(self.store,frame['id'],proof=self.proof(request))['action'],'complete')
            with self.subTest(status=status),self.assertRaisesRegex(ValueError,'result|failed|unavailable|cancel|passed|success|resolved'):
                self.accepted(frame,request)
            self.assertEqual(frame['cursor'],0);self.assertEqual(self.files(),before)

    def test_core_transition_is_verified_without_requiring_final_cl_confirmation(self):
        request,frame=self.returned(status='findings');after=self.context('incorporated')
        receipt=self.core_receipt(request['context'],after);calls=[]
        def verify(chain,attempt,received,current):
            calls.append((chain['id'],attempt['id'],received,current))
            return copy.deepcopy(received)
        frame=self.accepted(frame,request,after,receipt,verify)
        self.assertEqual(frame['context'],after);self.assertEqual(frame['cursor'],1)
        self.assertEqual(len(calls),1);self.assertFalse(receipt['final_confirmation'])
        self.no_future()

    def test_false_core_transition_or_wrong_before_after_digest_rejects_atomically(self):
        request,frame=self.returned(status='findings');after=self.context('incorporated');before=self.files()
        for bad in [None,{'kind':'core-incorporation','reference':'unbound true flag'},
                    {**self.core_receipt(request['context'],after),'before':'0'*64},
                    {**self.core_receipt(request['context'],after),'after':'0'*64}]:
            with self.subTest(receipt=bad),self.assertRaisesRegex(ValueError,'core|receipt|transition|before|after|verify'):
                self.accepted(frame,request,after,bad,lambda *args:copy.deepcopy(bad))
            self.assertEqual(self.files(),before)

    def test_a_b_a_uses_latest_incorporated_context_without_restarting_completed_prefix(self):
        rows=[self.row('first-a'),self.row('middle-b','interview'),self.row('last-a')]
        request=self.request(rows);request,frame=self.returned(request,suffix='first')
        first=copy.deepcopy(self.attempt(frame));frame=self.accepted(frame,request)
        frame=self.prepared(frame,request,'middle');frame=self.invoked(frame,request)
        frame=self.recorded(frame,request,status='findings');middle=copy.deepcopy(self.attempt(frame))
        after=self.context('incorporated');receipt=self.core_receipt(request['context'],after)
        frame=self.accepted(frame,request,after,receipt,lambda *args:copy.deepcopy(receipt))
        proof=self.proof(request,context=after);frame=self.prepared(frame,request,'last',proof)
        last=copy.deepcopy(self.attempt(frame))
        self.assertEqual(last['input']['binding_id'],'last-a');self.assertEqual(last['input']['context'],after)
        self.assertEqual(first['input']['context'],request['context'])
        self.assertEqual(frame['attempts'][first['id']]['input'],first['input'])
        self.assertEqual(frame['attempts'][middle['id']]['input'],middle['input'])
        self.assertEqual(len({first['id'],middle['id'],last['id']}),3)
        self.assertNotEqual(first['input']['parameters'],last['input']['parameters'])

    def test_conditions_are_reevaluated_at_the_cursor_after_accepted_context_changes(self):
        rows=[self.row('first-a'),self.row('conditional-b','interview',condition={'equals':{'path':'/accepted_marker','value':'incorporated'}}),self.row('last-a')]
        request=self.request(rows);initial=self.proof(request,rows=[rows[0],rows[2]])
        frame=self.start(request,initial);frame=self.prepared(frame,request,'first',initial)
        frame=self.invoked(frame,request,initial);frame=self.recorded(frame,request,status='findings',proof=initial)
        after=self.context('incorporated');receipt=self.core_receipt(request['context'],after)
        frame=self.accepted(frame,request,after,receipt,lambda *args:copy.deepcopy(receipt),self.proof(request,context=after))
        frame=self.prepared(frame,request,'conditional',self.proof(request,context=after))
        self.assertEqual(self.attempt(frame)['input']['binding_id'],'conditional-b')

    def test_public_parameter_keys_never_replace_scope_authority_or_executor(self):
        request=self.request();row=request['configuration']['bindings'][0]
        row['effective']['values']={'authority':{'allow':'publish'},'context':{'task_ids':['invented']},'executor':'invented'}
        frame=self.prepared(self.start(request),request);envelope=self.attempt(frame)['input']
        self.assertEqual(envelope['context'],request['context']);self.assertEqual(frame['authority'],request['authority'])
        self.assertEqual(frame['executor'],request['executor'])
        self.assertEqual(envelope['parameters'],row['effective']['values'])

    def test_pending_original_requires_reconciliation_before_resume_or_retry(self):
        request=self.request();frame=self.invoked(self.prepared(self.start(request),request),request)
        attempt=copy.deepcopy(self.attempt(frame));before=self.files()
        with self.assertRaisesRegex(ValueError,'original|pending|reconcile|uncertain'):
            self.change(frame,'resume',proof=self.proof(request),reason='A retry is requested.',retry=True)
        self.assertEqual(self.files(),before)
        frame=self.change(frame,'reconcile',attempt_id=attempt['id'],status='unknown',
            evidence={'kind':'host-reconciliation','reference':'Synthetic transport uncertainty; no completion evidence.'})
        self.assertTrue(engine().pending_scan(self.store));self.assertEqual(frame['attempts'][attempt['id']]['input'],attempt['input'])
        with self.assertRaisesRegex(ValueError,'original|pending|reconcile|uncertain'):
            self.change(frame,'resume',proof=self.proof(request),reason='A blind retry is requested.',retry=True)

    def test_cancelled_original_retry_retains_attempt_history_and_only_restarts_current_occurrence(self):
        request=self.request([self.row('first-a'),self.row('last-a')]);request,frame=self.returned(request)
        first=copy.deepcopy(self.attempt(frame));frame=self.accepted(frame,request)
        frame=self.invoked(self.prepared(frame,request,'old-last'),request);old=copy.deepcopy(self.attempt(frame))
        frame=self.change(frame,'reconcile',attempt_id=old['id'],status='cancelled',
            evidence={'kind':'host-reconciliation','reference':'Synthetic observed original cancellation.'})
        frame=self.change(frame,'resume',proof=self.proof(request),reason='Retry after the original cancellation.',retry=True)
        frame=self.prepared(frame,request,'new-last');new=self.attempt(frame)
        self.assertEqual(frame['cursor'],1);self.assertNotEqual(new['id'],old['id'])
        self.assertEqual(new['input']['binding_id'],'last-a')
        self.assertEqual(frame['attempts'][first['id']]['input'],first['input'])
        self.assertEqual(frame['attempts'][old['id']]['input'],old['input'])

    def test_later_project_configuration_cannot_silently_reorder_parked_chain(self):
        request=self.request([self.row('first-a'),self.row('last-a')]);frame=self.start(request);before=self.files()
        changed=copy.deepcopy(request['configuration']);changed['bindings'].reverse();changed['configuration_digest']=sha('new-order')
        proof=self.proof(request);proof['configuration_digest']=changed['configuration_digest']
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=proof)['action'],'prerequisite')
        self.assertEqual(self.files(),before)
        with self.assertRaisesRegex(ValueError,'configuration|frozen|order'):
            self.change(frame,'resume',proof=proof,configuration=changed,reason='A different project order is visible.')
        self.assertEqual(self.files(),before)

    def test_stale_scope_and_review_or_source_identity_reject_returned_mutation(self):
        request=self.request();frame=self.invoked(self.prepared(self.start(request),request),request);before=self.files()
        for proof in [self.proof(request,context=self.context('external-change')),
                      {**self.proof(request),'execution_snapshot':{'controlled-owned-module':sha('changed-source')}}]:
            with self.subTest(proof=proof),self.assertRaisesRegex(ValueError,'scope|context|source|snapshot|stale|changed'):
                self.recorded(frame,request,proof=proof)
            self.assertEqual(self.files(),before)

    def test_original_cleanup_is_available_after_former_scope_guard_disappears(self):
        request=self.request();frame=self.invoked(self.prepared(self.start(request),request),request);attempt=copy.deepcopy(self.attempt(frame))
        seen=[]
        def cleanup_guard(chain,command,payload):
            seen.append(command)
            self.assertEqual(command,'reconcile')
        frame=self.change(frame,'reconcile',attempt_id=attempt['id'],status='cancelled',guard=cleanup_guard,
            evidence={'kind':'host-reconciliation','reference':'Original actor cancelled after its former task scope disappeared.'})
        self.assertEqual(frame['attempts'][attempt['id']]['input'],attempt['input']);self.assertEqual(engine().pending_scan(self.store),[])
        self.no_future()

    def test_writer_guard_is_read_only_and_runs_under_the_owned_lock(self):
        request=self.request();frame=self.start(request);seen=[]
        def guard(chain,command,payload):
            self.assertTrue((self.root/'.skill-tree/.writer-lock').exists())
            seen.append(command)
        frame=self.change(frame,'prepare',proof=self.proof(request),guard=guard,
            actor=self.actor(),creation_evidence=self.creation(self.actor()))
        self.assertEqual(len(seen),1);self.assertTrue(seen[0].endswith('prepare'))
        self.assertFalse((self.root/'.skill-tree/.writer-lock').exists());self.no_future()

    def test_active_recursive_occurrence_rejects_but_distinct_same_package_parent_is_valid(self):
        boundary='skill-tree-add-pending-task:before'
        recursive=self.request();recursive['request_id']='recursive-occurrence'
        recursive['lineage']=[{'binding_id':'first-a','boundary_id':boundary}]
        frame=self.start(recursive);before=self.files()
        with self.assertRaisesRegex(ValueError,'recurs|lineage|active'):
            self.prepared(frame,recursive)
        self.assertEqual(self.files(),before)
        distinct=self.request();distinct['request_id']='distinct-occurrence'
        distinct['lineage']=[{'binding_id':'another-a','boundary_id':boundary}]
        frame=self.prepared(self.start(distinct),distinct,'distinct')
        self.assertEqual(self.attempt(frame)['input']['lineage'],
            [{'binding_id':'another-a','boundary_id':boundary},{'binding_id':'first-a','boundary_id':boundary}])

    def test_completed_stage_history_does_not_become_active_recursive_lineage(self):
        request=self.request([self.row('first-a'),self.row('last-a')])
        request,frame=self.returned(request);frame=self.accepted(frame,request)
        frame=self.prepared(frame,request,'last')
        self.assertEqual(self.attempt(frame)['input']['lineage'],
            [{'binding_id':'last-a','boundary_id':'skill-tree-add-pending-task:before'}])

    def adoption(self, old, original, configuration=None):
        request=copy.deepcopy(original);request['request_id']='explicit-config-successor'
        request['context']=copy.deepcopy(old['context'])
        if configuration is None:
            configuration=copy.deepcopy(original['configuration']);configuration['bindings'].reverse()
            configuration['configuration_digest']=sha('explicit-adopted-order')
        request['configuration']=configuration
        request.update(supersedes_chain_id=old['id'],expected_predecessor_hash=old['chain_hash'],
                       expected_predecessor_revision=old['revision'])
        receipt={'kind':'configuration-adoption','reference':'Synthetic explicit exact configuration adoption.',
                 'before_configuration_digest':old['configuration']['configuration_digest'],
                 'after_configuration_digest':configuration['configuration_digest']}
        request['supersession_receipt']=receipt
        return request,receipt

    def test_explicit_order_adoption_preserves_old_chain_and_creates_guarded_successor(self):
        request=self.request([self.row('first-a'),self.row('last-a')]);old=self.start(request)
        successor,receipt=self.adoption(old,request)
        new=engine().start(self.store,successor,proof=self.proof(successor),
            verify_supersession=lambda *args:copy.deepcopy(receipt))
        self.assertNotEqual(new['id'],old['id']);self.assertEqual(new['cursor'],0)
        self.assertEqual([row['id'] for row in new['configuration']['bindings']],['last-a','first-a'])
        retained=engine().read(self.store,old['id'])
        self.assertEqual(retained['state'],'superseded');self.assertEqual(retained['superseded_by'],new['id'])
        self.assertEqual(retained['configuration'],old['configuration']);self.assertEqual(new['context'],old['context'])
        action=engine().next_action(self.store,old['id'],proof=self.proof(request))
        self.assertEqual(action['action'],'superseded');self.assertEqual(action['replacement_chain_id'],new['id'])

    def test_empty_explicit_successor_does_not_relabel_the_old_chain_as_successful(self):
        request=self.request();old=self.start(request);empty=copy.deepcopy(request['configuration'])
        empty.update(bindings=[],packages={},configuration_digest=sha('explicit-empty-configuration'))
        successor,receipt=self.adoption(old,request,empty)
        new=engine().start(self.store,successor,proof=self.proof(successor),
            verify_supersession=lambda *args:copy.deepcopy(receipt))
        self.assertEqual(engine().read(self.store,old['id'])['state'],'superseded')
        self.assertEqual(engine().next_action(self.store,new['id'],proof=self.proof(successor))['action'],'complete')
        self.assertEqual(new['context'],old['context']);self.no_future()

    def test_explicit_no_selected_successor_retains_adoption_and_records_skips_without_hi(self):
        for variant in ['disabled','condition-excluded']:
            with self.subTest(variant=variant):
                request=self.request();request['request_id']+='-'+variant;old=self.start(request)
                configuration=copy.deepcopy(request['configuration']);configuration['bindings'][0].update({'enabled':False} if variant=='disabled' else {'condition':False})
                configuration['configuration_digest']=sha('explicit-no-selected-'+variant)
                successor,receipt=self.adoption(old,request,configuration);successor['request_id']+='-'+variant
                proof=self.proof(successor,rows=[])
                new=engine().start(self.store,successor,proof=proof,verify_supersession=lambda *args:copy.deepcopy(receipt))
                self.assertEqual(new['state'],'complete');self.assertEqual(new['cursor'],1);self.assertEqual(new['attempts'],{})
                self.assertEqual(new['stages'][0]['status'],'skipped');self.assertEqual(new['supersession_receipt'],receipt)
                self.assertEqual(engine().read(self.store,old['id'])['state'],'superseded')
                self.assertEqual(engine().next_action(self.store,new['id'],proof=proof)['action'],'complete')
                before=self.files();replayed=engine().start(self.store,successor,proof=proof,verify_supersession=lambda *args:self.fail('Exact replay cannot request another adoption.'))
                self.assertEqual(replayed,new);self.assertEqual(self.files(),before);self.no_future()

    def test_config_adoption_requires_current_predecessor_and_verified_exact_receipt(self):
        request=self.request([self.row('first-a'),self.row('last-a')]);old=self.start(request)
        successor,receipt=self.adoption(old,request);before=self.files()
        for change in [{}, {'expected_predecessor_hash':'0'*64},
                       {'expected_predecessor_revision':0},
                       {'supersession_receipt':{**receipt,'after_configuration_digest':'0'*64}}]:
            candidate={**copy.deepcopy(successor),**change}
            verifier=None if not change else lambda *args:copy.deepcopy(candidate['supersession_receipt'])
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'adopt|supers|receipt|hash|revision|configuration|verif'):
                engine().start(self.store,candidate,proof=self.proof(candidate),verify_supersession=verifier)
            self.assertEqual(self.files(),before)

    def test_active_original_prevents_configuration_supersession_without_losing_attempt(self):
        request=self.request();old=self.prepared(self.start(request),request)
        original=copy.deepcopy(self.attempt(old));successor,receipt=self.adoption(old,request)
        before=self.files()
        with self.assertRaisesRegex(ValueError,'original|pending|reconcile|attempt'):
            engine().start(self.store,successor,proof=self.proof(successor),
                verify_supersession=lambda *args:copy.deepcopy(receipt))
        self.assertEqual(self.files(),before)
        self.assertEqual(engine().read(self.store,old['id'])['attempts'][original['id']]['input'],original['input'])

    def test_corrupt_pending_metadata_is_a_prerequisite_not_an_empty_safe_scan(self):
        request=self.request();frame=self.prepared(self.start(request),request)
        self.assertTrue(engine().pending_scan(self.store))
        record=self.store.owned('.skill-tree/invocations/'+frame['id'].lower()+'.json')
        record.write_text('{broken invocation metadata')
        with self.assertRaisesRegex(ValueError,'metadata|read|JSON|corrupt|invalid'):
            engine().pending_scan(self.store)
        self.assertEqual(record.read_text(),'{broken invocation metadata');self.no_future()

    def test_concurrent_invocation_file_edit_is_preserved_by_store_compare_and_swap(self):
        request=self.request();frame=self.start(request)
        record=self.store.owned('.skill-tree/invocations/'+frame['id'].lower()+'.json')
        external='Concurrent developer bytes remain authoritative.\n'
        def race(chain,command,payload):
            self.assertTrue((self.root/'.skill-tree/.writer-lock').exists())
            record.write_text(external)
        with self.assertRaisesRegex(ValueError,'edit|concurrent|changed|transaction|conflict'):
            self.change(frame,'prepare',proof=self.proof(request),guard=race,
                actor=self.actor(),creation_evidence=self.creation(self.actor()))
        self.assertEqual(record.read_text(),external)
        self.assertFalse((self.root/'.skill-tree/.writer-lock').exists());self.no_future()

    def test_record_rejects_a_different_resolved_parameter_digest(self):
        request=self.request();frame=self.invoked(self.prepared(self.start(request),request),request)
        attempt=self.attempt(frame);before=self.files()
        evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
            'reference':'Synthetic digest mismatch.','actor_id':attempt['actor']['id'],
            'actor_context_id':attempt['actor']['context_id'],'mechanism':'source-backed-context'}
        with self.assertRaisesRegex(ValueError,'parameter|delivery|digest|identity'):
            self.change(frame,'record',proof=self.proof(request),attempt_id=attempt['id'],
                input_digest=attempt['input_digest'],delivery_digest=attempt['delivery_digest'],
                resolved_parameter_digest='0'*64,result={'status':'passed'},evidence=evidence)
        self.assertEqual(self.files(),before)

    def test_core_incorporation_cannot_substitute_another_operation_context_identity(self):
        request,frame=self.returned(status='findings');after=self.context('incorporated')
        after['id']='another-operation-request';receipt=self.core_receipt(request['context'],after)
        before=self.files()
        with self.assertRaisesRegex(ValueError,'scope|identity|context|substitut|authority'):
            self.accepted(frame,request,after,receipt,lambda *args:copy.deepcopy(receipt))
        self.assertEqual(self.files(),before)

    def test_completed_history_is_not_current_readiness_after_external_context_or_source_drift(self):
        request,frame=self.returned();frame=self.accepted(frame,request);before=self.files()
        changed_context=self.context('later-external-edit')
        for proof,extra in [(self.proof(request,context=changed_context),{'context':changed_context}),
                            ({**self.proof(request),'execution_snapshot':{'controlled-owned-module':sha('later-source')}},{})]:
            with self.subTest(proof=proof):
                self.assertEqual(engine().next_action(self.store,frame['id'],proof=proof)['action'],'prerequisite')
                with self.assertRaisesRegex(ValueError,'complete|successor|current|histor|adopt|fresh'):
                    self.change(frame,'resume',proof=proof,reason='A later external edit needs current verification.',**extra)
                self.assertEqual(self.files(),before)
        unchanged=self.change(frame,'resume',proof=self.proof(request),reason='The completed inputs are unchanged.')
        self.assertEqual(unchanged,frame);self.assertEqual(self.files(),before)

    def test_explicit_retry_never_accepts_the_old_returned_result_under_changed_inputs(self):
        request,frame=self.returned(status='findings');old=copy.deepcopy(self.attempt(frame))
        changed=self.context('current-source-context');proof=self.proof(request,context=changed)
        frame=self.change(frame,'resume',proof=proof,context=changed,retry=True,
                          reason='The actual source/context changed; the current occurrence needs a new attempt.')
        before=self.files()
        with self.assertRaisesRegex(ValueError,'original|current|attempt|unresolved|returned'):
            self.change(frame,'accept',proof=proof,attempt_id=old['id'],input_digest=old['input_digest'],
                        context=changed,receipt=self.core_receipt(request['context'],changed),
                        verify_transition=lambda *args:self.core_receipt(request['context'],changed))
        self.assertEqual(self.files(),before)
        frame=self.prepared(frame,request,'current',proof);new=self.attempt(frame)
        self.assertNotEqual(new['id'],old['id']);self.assertEqual(new['input']['context'],changed)
        self.assertEqual(frame['attempts'][old['id']]['input'],old['input'])

    def test_explicit_mode_switch_preserves_completed_prefix_and_records_actual_policy_origin(self):
        request=self.request([self.row('first-a'),self.row('last-a')]);request,frame=self.returned(request)
        original=copy.deepcopy(self.attempt(frame));frame=self.accepted(frame,request)
        old_epoch=frame['epoch'];authority={**request['authority'],'revision':2}
        executor={'id':'explicit-auto-executor','context_id':'explicit-auto-context'}
        evidence={'kind':'owner-message','reference':'Scripted fixture-owner explicitly selects Auto for the remaining occurrence.'}
        frame=self.change(frame,'resume',proof=self.proof(request),reason='The fixture owner changed the decision policy.',
                          mode='auto',authority=authority,executor=executor,evidence=evidence)
        self.assertEqual(frame['mode'],'auto');self.assertEqual(frame['authority'],authority)
        self.assertEqual(frame['executor'],executor);self.assertGreater(frame['epoch'],old_epoch)
        self.assertEqual(frame['cursor'],1);self.assertEqual(frame['configuration'],request['configuration'])
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input'])
        self.assertIn(evidence['reference'],json.dumps(frame['history']))
        frame=self.prepared(frame,request,'auto-last');envelope=self.attempt(frame)['input']
        self.assertEqual(envelope['mode'],'auto');self.assertEqual(envelope['epoch'],frame['epoch'])
        self.assertEqual(original['input']['mode'],'manual')

    def test_policy_change_needs_real_origin_and_original_reconciliation_before_late_result_refusal(self):
        request=self.request();frame=self.invoked(self.prepared(self.start(request),request),request)
        old=copy.deepcopy(self.attempt(frame));before=self.files()
        evidence={'kind':'owner-message','reference':'Scripted fixture-owner requests an explicit Auto switch.'}
        with self.assertRaisesRegex(ValueError,'original|pending|reconcile|uncertain'):
            self.change(frame,'resume',proof=self.proof(request),reason='A policy change is requested.',
                        mode='auto',evidence=evidence,retry=True)
        self.assertEqual(self.files(),before)
        frame=self.change(frame,'reconcile',attempt_id=old['id'],status='cancelled',
            evidence={'kind':'host-reconciliation','reference':'Synthetic original actor cancellation observed.'})
        before=self.files()
        with self.assertRaisesRegex(ValueError,'evidence|owner|origin|explicit|policy'):
            self.change(frame,'resume',proof=self.proof(request),reason='A switch without origin is attempted.',
                        mode='auto',retry=True)
        self.assertEqual(self.files(),before)
        frame=self.change(frame,'resume',proof=self.proof(request),reason='The explicit policy change follows original cancellation.',
                          mode='auto',evidence=evidence,retry=True)
        before=self.files()
        late={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
            'reference':'Synthetic late old-epoch delivery.','actor_id':old['actor']['id'],
            'actor_context_id':old['actor']['context_id'],'mechanism':'source-backed-context'}
        with self.assertRaisesRegex(ValueError,'original|attempt|epoch|cancel|current'):
            self.change(frame,'record',proof=self.proof(request),attempt_id=old['id'],input_digest=old['input_digest'],
                        delivery_digest=old['delivery_digest'],resolved_parameter_digest=old['resolved_parameter_digest'],
                        result={'status':'passed'},evidence=late)
        self.assertEqual(self.files(),before)

    def test_revoked_grant_preserves_original_cleanup_and_requires_explicit_reauthorization(self):
        request=self.request();request['authority']['revoked']=True;before=self.files()
        with self.assertRaisesRegex(ValueError,'revoked'):
            self.start(request)
        self.assertEqual(self.files(),before)
        request=self.request();frame=self.prepared(self.start(request),request)
        original=copy.deepcopy(self.attempt(frame))
        # A retained, correctly sealed historical fixture models authority revoked after preparation.
        frame['authority']['revoked']=True
        frame['chain_hash']=engine().digest({key:value for key,value in frame.items() if key!='chain_hash'})
        record=self.store.owned('.skill-tree/invocations/'+frame['id'].lower()+'.json')
        record.write_text(json.dumps(frame,sort_keys=True,ensure_ascii=True))
        frame=engine().read(self.store,frame['id'])
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=self.proof(request))['action'],'prerequisite')
        before=self.files()
        with self.assertRaisesRegex(ValueError,'revoked'):
            self.invoked(frame,request)
        self.assertEqual(self.files(),before)
        frame=self.change(frame,'reconcile',attempt_id=original['id'],status='cancelled',
            evidence={'kind':'host-reconciliation','reference':'Synthetic revoked original cancellation observed.'})
        before=self.files()
        restored={**request['authority'],'revision':2,'revoked':False}
        with self.assertRaisesRegex(ValueError,'owner|evidence|origin'):
            self.change(frame,'resume',proof=self.proof(request),reason='A renewed grant is proposed.',
                        authority=restored,retry=True)
        self.assertEqual(self.files(),before)
        frame=self.change(frame,'resume',proof=self.proof(request),reason='Original cancellation precedes explicit reauthorization.',
            authority=restored,retry=True,evidence={'kind':'owner-message','reference':'Scripted fixture owner renews the bounded grant.'})
        self.assertEqual(frame['authority'],restored)
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input'])
        self.assertEqual(engine().pending_scan(self.store),[])
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=self.proof(request))['action'],'prepare')


    def held_proof(self,request,kind,binding_id=None,context=None):
        value=self.proof(request,context=context)
        if kind=='unresolved':value['unresolved']=[{'id':binding_id or request['configuration']['bindings'][0]['id'],'reason':'Controlled unresolved current location.'}]
        else:
            item={'code':'controlled-prerequisite','reason':'Controlled current admission hold.'}
            if kind!='global':item['binding_id']=binding_id or request['configuration']['bindings'][0]['id']
            value['prerequisites']=[item]
        return value

    def test_applicable_prerequisites_and_unresolved_rows_block_each_business_transition_atomically(self):
        for kind in ['global','current','unresolved']:
            for command in ['prepare','invoke','record','accept']:
                with self.subTest(kind=kind,command=command):
                    request=self.request();request['request_id']+='-'+kind+'-'+command;frame=self.start(request)
                    if command!='prepare':frame=self.prepared(frame,request)
                    if command in {'record','accept'}:frame=self.invoked(frame,request)
                    if command=='accept':frame=self.recorded(frame,request)
                    held=self.held_proof(request,kind);before=self.files()
                    with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                        if command=='prepare':self.prepared(frame,request,proof=held)
                        elif command=='invoke':self.invoked(frame,request,proof=held)
                        elif command=='record':self.recorded(frame,request,proof=held)
                        else:self.accepted(frame,request,proof=held)
                    self.assertEqual(self.files(),before)

    def test_current_unresolved_selector_row_is_not_silently_skipped_or_counted_complete(self):
        for remaining in ['next-selected','all-unresolved']:
            with self.subTest(remaining=remaining):
                rows=[self.row('current-unresolved'),self.row('later-selected','interview')]
                request=self.request(rows);request['request_id']+='-selector-'+remaining
                proof=self.proof(request,rows=[rows[1]] if remaining=='next-selected' else [])
                proof['unresolved']=[{'id':rows[0]['id'],'reason':'The actual selector found the current location/context incompatible.'}]
                if remaining=='all-unresolved':proof['unresolved'].append({'id':rows[1]['id'],'reason':'The actual selector found the later location/context incompatible.'})
                frame=self.start(request,proof);before=self.files()
                self.assertEqual(engine().next_action(self.store,frame['id'],proof=proof)['action'],'prerequisite')
                with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                    self.prepared(frame,request,proof=proof)
                self.assertEqual(self.files(),before);self.assertEqual(engine().read(self.store,frame['id'])['cursor'],0)

    def test_completed_readiness_proof_cannot_authorize_ordinary_business_transitions(self):
        for command in ['start','prepare','invoke','record','accept','resume']:
            with self.subTest(command=command):
                request=self.request();request['request_id']+='-readiness-kind-'+command
                if command=='start':
                    proof=self.proof(request);proof['proof_kind']='completed-readiness';before=self.files()
                    with self.assertRaisesRegex(ValueError,'readiness|business|proof'):self.start(request,proof)
                    self.assertEqual(self.files(),before);continue
                frame=self.start(request)
                if command not in {'prepare','resume'}:frame=self.prepared(frame,request)
                if command in {'record','accept'}:frame=self.invoked(frame,request)
                if command=='accept':frame=self.recorded(frame,request)
                proof=self.proof(request);proof['proof_kind']='completed-readiness';before=self.files()
                with self.assertRaisesRegex(ValueError,'readiness|business|proof'):
                    if command=='prepare':self.prepared(frame,request,proof=proof)
                    elif command=='invoke':self.invoked(frame,request,proof=proof)
                    elif command=='record':self.recorded(frame,request,proof=proof)
                    elif command=='resume':self.change(frame,'resume',proof=proof,reason='A readiness proof cannot authorize recovery business inputs.')
                    else:self.accepted(frame,request,proof=proof)
                self.assertEqual(self.files(),before)

    def test_writer_transaction_consumes_a_new_applicable_hold_before_business_branch(self):
        for kind in ['global','current']:
            for command in ['invoke','record','accept']:
                with self.subTest(kind=kind,command=command):
                    request=self.request();request['request_id']+='-writer-'+kind+'-'+command;frame=self.prepared(self.start(request),request)
                    if command in {'record','accept'}:frame=self.invoked(frame,request)
                    if command=='accept':frame=self.recorded(frame,request)
                    original=copy.deepcopy(self.attempt(frame));proof=self.proof(request);calls=[]
                    payload={'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],'expected_chain_revision':frame['revision'],
                        'attempt_id':original['id'],'input_digest':original['input_digest']}
                    if command=='invoke':
                        headers={'input_digest':original['input_digest'],'delivery_digest':sha('delivery-'+original['input_digest']),
                            'resolved_parameter_digest':original['input']['parameter_digest']}
                        proof['delivery']=headers;payload.update(headers,evidence={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-dispatch',
                            'reference':'Synthetic original invocation after writer-entry admission change.','actor_id':original['actor']['id'],
                            'actor_context_id':original['actor']['context_id'],'mechanism':'source-backed-context'})
                    elif command=='record':
                        payload.update(delivery_digest=original['delivery_digest'],resolved_parameter_digest=original['resolved_parameter_digest'],
                            result={'status':'passed'},evidence={'kind':'host-result','provider':'controlled-unit-host','tool':'controlled-result',
                            'reference':'Synthetic original result after writer-entry admission change.','actor_id':original['actor']['id'],
                            'actor_context_id':original['actor']['context_id'],'mechanism':'source-backed-context'})
                    else:payload['context']=request['context']
                    def writer_guard(current,operation,values):
                        self.assertTrue((self.store.base/'.writer-lock').exists(),'The controlled hold must appear after metadata writer entry.')
                        calls.append(operation);item={'code':'controlled-writer-hold','reason':'Applicable prerequisite appeared at writer entry.'}
                        if kind=='current':item['binding_id']=original['binding_id']
                        proof['prerequisites'].append(item)
                    before=self.files()
                    with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                        engine().mutate(self.store,command,payload,proof=proof,guard=writer_guard)
                    self.assertEqual(calls,[command]);self.assertEqual(self.files(),before)
                    self.assertEqual(engine().read(self.store,frame['id']),frame)

    def test_held_start_stays_inspectable_and_completed_next_requires_current_global_admission(self):
        request=self.request();held=self.held_proof(request,'global');frame=self.start(request,held)
        self.assertEqual(frame['attempts'],{});self.assertEqual(frame['cursor'],0)
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=held)['action'],'prerequisite')
        request=self.request();request['request_id']+='-complete';request,complete=self.returned(request)
        complete=self.accepted(complete,request);before=self.files()
        self.assertEqual(engine().next_action(self.store,complete['id'],proof=self.held_proof(request,'global'))['action'],'prerequisite')
        self.assertEqual(self.files(),before);self.assertEqual(engine().read(self.store,complete['id'])['state'],'complete')
        self.assertEqual(engine().next_action(self.store,complete['id'],proof=self.proof(request))['action'],'complete')

    def test_other_occurrence_requirements_preserve_current_contribution_and_accepted_prefix(self):
        request=self.request([self.row('editor-first'),self.row('interview-middle','interview'),self.row('editor-final')])
        request,frame=self.returned(request,suffix='first');frame=self.accepted(frame,request);prefix=copy.deepcopy(frame['attempts'])
        other=self.proof(request);other['prerequisites']=[{'code':'missing-capability','binding_id':identity,'reason':'Controlled editor-only capability loss.'} for identity in ['editor-first','editor-final']]
        other['unresolved']=[{'id':'editor-final','reason':'Controlled future-only location hold.'}]
        try:request,frame=self.returned(request,status='findings',suffix='middle',frame=frame,proof=other)
        except ValueError as error:self.fail('Another occurrence prerequisite incorrectly blocked current B: '+str(error))
        before=copy.deepcopy(frame['context']);after=self.context('incorporated-b');receipt=self.core_receipt(before,after)
        accepted_proof=copy.deepcopy(other);accepted_proof['context']=after
        frame=self.accepted(frame,request,context=after,receipt=receipt,verifier=lambda *args:receipt,proof=accepted_proof)
        self.assertEqual(frame['cursor'],2);self.assertEqual(frame['context'],after)
        self.assertTrue(all(frame['attempts'][key]==value for key,value in prefix.items()))
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=accepted_proof)['action'],'prerequisite')
        old=self.files()
        with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
            self.prepared(frame,request,suffix='final',proof=accepted_proof)
        self.assertEqual(self.files(),old)
        ready=self.proof(request,context=after);frame=self.prepared(frame,request,suffix='final',proof=ready)
        frame=self.invoked(frame,request,proof=ready);frame=self.recorded(frame,request,proof=ready)
        frame=self.accepted(frame,request,context=after,proof=ready)
        self.assertEqual(frame['state'],'complete');self.assertTrue(all(frame['attempts'][key]==value for key,value in prefix.items()))

    def test_current_holds_preserve_read_original_reconciliation_and_explicit_recovery(self):
        request=self.request();frame=self.start(request);frame=self.prepared(frame,request);frame=self.invoked(frame,request)
        original=copy.deepcopy(self.attempt(frame));held=self.held_proof(request,'global')
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        frame=self.change(frame,'reconcile',proof=held,attempt_id=original['id'],status='cancelled',
            evidence={'kind':'host-reconciliation','reference':'Synthetic original cancellation remains available while prerequisites are held.'})
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input']);self.assertEqual(engine().pending_scan(self.store),[])
        frame=self.change(frame,'resume',proof=held,retry=True,reason='Explicit retry after reconciling the original attempt; business admission remains held.')
        self.assertEqual(frame['cursor'],0);self.assertIsNone(frame['prepared_attempt_id'])
        self.assertEqual(engine().next_action(self.store,frame['id'],proof=held)['action'],'prerequisite')
        frame=self.prepared(frame,request,suffix='restored');self.assertNotEqual(frame['prepared_attempt_id'],original['id'])
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input']);self.no_future()

    def test_unknown_or_malformed_requirement_scope_cannot_masquerade_as_another_occurrence(self):
        for scope in ['not-in-frozen-order',None,17]:
            for kind in ['prerequisite','unresolved']:
                with self.subTest(scope=scope,kind=kind):
                    request=self.request();request['request_id']+='-unknown-'+str(scope)+'-'+kind;frame=self.start(request);proof=self.proof(request)
                    proof['prerequisites' if kind=='prerequisite' else 'unresolved']=[{'binding_id' if kind=='prerequisite' else 'id':scope,'code':'controlled-scope','reason':'A malformed scope is not another admitted occurrence.'}]
                    before=self.files()
                    with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|scope|held'):
                        self.prepared(frame,request,proof=proof)
                    self.assertEqual(self.files(),before)

clarification_fixture=load('hook_bridge_cl_fixture',CORE/'tests/test-task-clarification.py')
clarification_fixture.wf=wf

class PluginWorkflowBridgeTests(unittest.TestCase):
    setUp=clarification_fixture.TaskClarificationTests.setUp
    body=clarification_fixture.TaskClarificationTests.body
    task=clarification_fixture.TaskClarificationTests.task
    source_hash=clarification_fixture.TaskClarificationTests.source_hash
    finish_task=clarification_fixture.TaskClarificationTests.finish_task

    def install(self,operation='skill-tree-process-future-pending',anchor='after',binding_options=None,resource_collision=False):
        self.operation=operation;self.anchor=anchor
        (self.root/'package.json').write_text(json.dumps({'scripts':{'test':'node --test'}}))
        program="""const fs=require('node:fs'),path=require('node:path');
const core=process.argv[1],root=process.argv[2],install=require(path.join(core,'lib/installation.js')),lifecycle=require(path.join(core,'lib/plugin-lifecycle.js'));
const operation=process.argv[3],anchor=process.argv[4],options=JSON.parse(process.argv[5]||'{}'),upstream=path.join(root,'controlled-upstream');fs.mkdirSync(upstream);
fs.writeFileSync(path.join(upstream,'SKILL.md'),'---\\nname: controlled-bridge\\n---\\nReturn controlled task proposals without executing helpers.\\n'+(process.argv[6]==='true'?'Read [the upstream JSON](references/plugin-bindings.json).\\n':''));if(process.argv[6]==='true'){fs.mkdirSync(path.join(upstream,'references'));fs.writeFileSync(path.join(upstream,'references/plugin-bindings.json'),JSON.stringify({kind:'ordinary-upstream-data'}));}
install.install(root,core,'general',[{name:operation,provider:'codex',rel:'.agents/skills/'+operation}]);
(async()=>{const proposal=await lifecycle.prepareProposal(root,{request_id:'bridge-install',operation:'install',sources:[{id:'controlled',path:upstream}],bindings:['proposal-b','final-a'].map(id=>({id,plugin_id:'controlled',operation,anchor,enabled:true,parameters:{marker:id},instructions:'Controlled '+id,...options}))});lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});install.refresh(root,core);process.stdout.write(JSON.stringify({package_root:path.join(root,'.agents/skills',operation)}));})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});"""
        result=subprocess.run(['node','-e',program,str(CORE),str(self.root),operation,anchor,json.dumps(binding_options or {}),json.dumps(resource_collision)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.package_root=Path(json.loads(result.stdout)['package_root'])


    def install_ordered_capability_fixture(self,incompatible='none'):
        self.operation='skill-tree-process-future-pending';self.anchor='after'
        self.capabilities=['codex-source-backed-context','editor-only-capability']
        (self.root/'package.json').write_text(json.dumps({'scripts':{'test':'node --test'}}))
        program=r"""const fs=require('node:fs'),path=require('node:path');
const core=process.argv[1],root=process.argv[2],install=require(path.join(core,'lib/installation.js')),lifecycle=require(path.join(core,'lib/plugin-lifecycle.js'));
const operation='skill-tree-process-future-pending';install.install(root,core,'general',[{name:operation,provider:'codex',rel:'.agents/skills/'+operation}]);
const sources=['editor','interview'].map(id=>{const source=path.join(root,'controlled-'+id);fs.mkdirSync(source);fs.writeFileSync(path.join(source,'SKILL.md'),'---\nname: controlled-'+id+'\n---\nReturn scoped controlled proposals without invoking tools.\n');return {id,path:source,capabilities:id==='editor'?['editor-only-capability']:[],...(process.argv[3]==='all'||process.argv[3]==='editor'&&id==='editor'?{adapter:{context_kinds:['document']}}:{})};});
(async()=>{const rows=[['editor-first','editor'],['interview-middle','interview'],['editor-final','editor']].map(([id,plugin_id])=>({id,plugin_id,operation,anchor:'after',enabled:true,parameters:{marker:id},instructions:'Controlled occurrence '+id}));const proposal=await lifecycle.prepareProposal(root,{request_id:'ordered-capability-install',operation:'install',sources,bindings:rows});lifecycle.applyProposal(root,proposal,{proposal_digest:proposal.digest});install.refresh(root,core);process.stdout.write(JSON.stringify({package_root:path.join(root,'.agents/skills',operation)}));})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});"""
        result=subprocess.run(['node','-e',program,str(CORE),str(self.root),incompatible],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.package_root=Path(json.loads(result.stdout)['package_root'])

    def invocation_bytes(self,frame):
        return {relative:(self.store.root/relative).read_bytes() if (self.store.root/relative).is_file() else None for relative in [
            '.skill-tree/invocations/'+frame['id'].lower()+'.json',
            '.skill-tree/local/hook-locations/'+frame['id'].lower()+'.json']}

    def injected_prerequisite(self,original,kind,binding_id):
        def prepared(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'Owned Node preparation cannot run under the writer lock.')
            value=original(package_root,request)
            if request.get('runtime_action') in {'occurrence-plan','readiness-plan'}:
                value=copy.deepcopy(value)
                if kind=='unresolved':value['unresolved'].append({'id':binding_id,'reason':'Controlled current binding location hold.'})
                else:
                    item={'code':'controlled-admission','reason':'Controlled prerequisite-only change.'}
                    if kind=='current':item['binding_id']=binding_id
                    value['prerequisites'].append(item)
            return value
        return prepared

    def cl_start(self):
        return wf.clarification_start(self.store,{'task_ids':[self.a],'expected_source_hash':self.source_hash(),
            'decision_mode':'manual'})

    def cl_change(self,session,command,**extra):
        return wf.clarification_mutate(self.store,command,{'session_id':session['id'],
            'expected_source_hash':self.source_hash(),'expected_session_hash':session['session_hash'],
            'expected_session_revision':session['revision'],**extra})

    def revise(self,session=None):
        session=session or self.cl_start()
        question={'id':'incorporate','text':'Incorporate the controlled proposal?',
            'recommendation':'Use the explicit controlled marker.','prerequisites':[],
            'bindings':{self.a:['goal']}}
        session=self.cl_change(session,'clarify-round',questions=[question])
        session=self.cl_change(session,'clarify-answer',round_id=session['rounds'][-1]['id'],
            question_id='incorporate',question_revision=session['questions']['incorporate']['revision'],
            answer='Incorporate the controlled proposal.',evidence={'kind':'owner-message',
            'reference':'Scripted fixture-owner incorporation input; no real-human business approval.'})
        return self.cl_change(session,'clarify-revise',tasks=[{'task_id':self.a,
            'body':self.body('Preserve the incorporated controlled marker.')}])

    def frame(self,session=None,request_id='bridge-chain',task_id=None,run_id=None):
        selected=task_id or self.a
        ctx={'kind':'task','id':'bridge-task:'+selected,'task_ids':[selected],'body':''}
        if run_id:ctx['run_id']=run_id
        if session:ctx['session_id']=session['id']
        ctx=wf.actual_hook_context(self.store,ctx)
        grant={'id':'bridge-grant','revision':1,'context_id':ctx['id'],'allowed_kinds':['technical'],
            'constraints':['Isolated source-backed bridge fixture; no actual host execution or publication.'],
            'evidence':{'kind':'owner-message','reference':'Scripted fixture grant only.'}}
        return wf.hook_action(self.store,'hook-start',{'package_root':str(self.package_root),
            'request_id':request_id,'event':{'id':'bridge-event','operation':'skill-tree-process-future-pending','anchor':'after'},
            'context':ctx,'mode':'manual','authority':grant,'executor':{'id':'bridge-executor','context_id':'bridge-executor-context'},
            'capabilities':getattr(self,'capabilities',['codex-source-backed-context']),'expected_source_hash':self.source_hash()})

    def change(self,frame,command,**extra):
        return wf.hook_action(self.store,'hook-'+command,{'chain_id':frame['id'],
            'expected_chain_hash':frame['chain_hash'],'expected_chain_revision':frame['revision'],
            'expected_source_hash':self.source_hash(),'capabilities':getattr(self,'capabilities',['codex-source-backed-context']),**extra})

    def prepare_bridge(self,frame):
        index=frame['cursor'];actor={'id':'bridge-actor-'+str(index),'context_id':'bridge-context-'+str(index)}
        return self.change(frame,'prepare',actor=actor,creation_evidence={'kind':'host-agent-created',
            'provider':'controlled-unit-host','tool':'controlled-create','reference':'Synthetic bridge actor creation.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id']})

    def delivery_bridge(self,frame):
        attempt=frame['attempts'][frame['prepared_attempt_id']]
        return wf._hook_node(self.package_root,{'runtime_action':'delivery-data','project_root':str(self.root),
            'event':frame['event'],'context':frame['context'],'capabilities':getattr(self,'capabilities',['codex-source-backed-context']),
            'adapter':{'provider':'codex','mechanism':'source-backed-context'},'configuration':frame['configuration'],
            'chain_id':frame['id'],'attempt_id':attempt['id'],'binding_id':attempt['binding_id'],
            'public_input':attempt['input'],'input_digest':attempt['input_digest'],'authority':frame['authority'],
            'orchestration_id':frame['context'].get('orchestration_id')})

    def returned(self,frame,status='passed',stop_after_invoke=False):
        frame=self.prepare_bridge(frame);attempt=frame['attempts'][frame['prepared_attempt_id']];actor=attempt['actor']
        private=self.delivery_bridge(frame)
        values={key:private[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
        evidence={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-dispatch',
            'reference':'Synthetic bridge dispatch, not actual native invocation.','actor_id':actor['id'],
            'actor_context_id':actor['context_id'],'mechanism':'source-backed-context'}
        frame=self.change(frame,'invoke',attempt_id=attempt['id'],**values,evidence=evidence)
        if stop_after_invoke:return frame
        return self.change(frame,'record',attempt_id=attempt['id'],**values,
            result={'status':status,'markers':{'binding_id':attempt['binding_id']}},
            evidence={**evidence,'kind':'host-result','reference':'Synthetic controlled bridge result.'})

    def accept(self,frame,**extra):
        attempt=frame['attempts'][frame['prepared_attempt_id']]
        return self.change(frame,'accept',attempt_id=attempt['id'],input_digest=attempt['input_digest'],**extra)

    def test_actual_guarded_cl_revision_is_incorporated_before_final_confirmation(self):
        self.install();session=self.cl_start();frame=self.returned(self.frame(session),'findings')
        before=copy.deepcopy(frame['context']);session=self.revise(session)
        self.assertNotEqual(session['state'],'complete');self.assertIsNone(session['confirmation'])
        after=wf.actual_hook_context(self.store,before);revision=session['task_revisions'][-1]
        receipt={'kind':'core-incorporation','session_id':session['id'],'task_revision_id':revision['id'],
            'before':engine().digest(before),'after':engine().digest(after)}
        unchanged=engine().read(self.store,frame['id'])
        with self.assertRaisesRegex(ValueError,'revision|unavailable|guarded'):
            self.accept(frame,context=after,receipt={**receipt,'task_revision_id':'TR-11111111-1111-4111-8111-111111111111'})
        self.assertEqual(engine().read(self.store,frame['id']),unchanged)
        frame=self.accept(frame,context=after,receipt=receipt)
        self.assertEqual(frame['cursor'],1);self.assertEqual(frame['context'],after)
        self.assertIn('incorporated controlled marker',after['body'])
        self.assertNotEqual(wf.clarification_read(self.store,session['id'])['state'],'complete')
        with self.assertRaisesRegex(ValueError,'hook|unfinished'):
            wf.hook_admission(self.store,scope=self.a)

    def test_trusted_private_delivery_callbacks_dispatch_once_outside_metadata_lock(self):
        self.install();frame=self.frame();actor={'id':'spi-actor','context_id':'spi-context'}
        frame=self.change(frame,'prepare',actor=actor,creation_evidence={'kind':'host-agent-created',
            'provider':'controlled-unit-host','tool':'controlled-create','reference':'Synthetic trusted SPI actor.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id']})
        original=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        private=wf._hook_node(self.package_root,{'runtime_action':'delivery-data','project_root':str(self.root),
            'event':frame['event'],'context':frame['context'],'capabilities':['codex-source-backed-context'],
            'adapter':{'provider':'codex','mechanism':'source-backed-context'},'configuration':frame['configuration'],
            'chain_id':frame['id'],'attempt_id':original['id'],'binding_id':original['binding_id'],
            'public_input':original['input'],'input_digest':original['input_digest'],'authority':frame['authority']})
        public={key:private[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
        payload={'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],
            'expected_chain_revision':frame['revision'],'expected_source_hash':self.source_hash(),
            'attempt_id':original['id'],**public,'evidence':{'kind':'host-invoked','provider':'controlled-unit-host',
            'tool':'controlled-spi','reference':'Synthetic private adapter dispatch, not native qualification.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id'],'mechanism':'source-backed-context'}}
        for key in ['private_delivery_provider','private_delivery_sink']:
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'JSON|callable|trusted'):
                wf.hook_action(self.store,'hook-invoke',{**payload,key:'untrusted-json-callback'})
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        calls=[];observed=[];owned_node=wf._hook_node
        def provider(request):
            self.assertFalse((self.store.base/'.writer-lock').exists())
            self.assertEqual(Path(request['package_root']).resolve(),self.package_root.resolve())
            self.assertEqual(request['public_input'],original['input'])
            calls.append(request['attempt_id']);return copy.deepcopy(private)
        def sink(value):
            self.assertFalse((self.store.base/'.writer-lock').exists())
            self.assertEqual(engine().read(self.store,frame['id'])['attempts'][original['id']]['status'],'invoking')
            observed.append(value)
        def without_default_resolution(root,request):
            self.assertNotEqual(request['runtime_action'],'delivery-data','The trusted DP must not be resolved a second time.')
            return owned_node(root,request)
        with patch.object(wf,'_hook_node',side_effect=without_default_resolution):
            invoked=wf.hook_action(self.store,'hook-invoke',payload,
                private_delivery_provider=provider,private_delivery_sink=sink)
        self.assertEqual(calls,[original['id']]);self.assertEqual(observed,[private['payload']])
        self.assertEqual(invoked['attempts'][original['id']]['input'],original['input'])
        self.assertEqual(invoked['attempts'][original['id']]['delivery_digest'],private['delivery_digest'])
        self.assertEqual(invoked['attempts'][original['id']]['resolved_parameter_digest'],private['resolved_parameter_digest'])
        self.assertNotIn('resource_digests',json.dumps(invoked))

    def test_completed_hook_admission_rejects_later_actual_task_semantic_drift(self):
        self.install();frame=self.frame()
        for _ in range(2):frame=self.accept(self.returned(frame))
        wf.hook_admission(self.store,scope=self.a)
        self.revise()
        with self.assertRaisesRegex(ValueError,'stale|current|scope'):
            wf.hook_admission(self.store,scope=self.a)
        self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')

    def test_removed_completed_task_allows_only_exact_read_only_hook_readiness(self):
        self.install();frame=self.frame()
        for _ in range(2):frame=self.accept(self.returned(frame))
        before=copy.deepcopy(frame['context']);outcome=self.finish_task(self.a)
        self.assertEqual(outcome['task_context'],{key:before[key] for key in ['semantic_fingerprint','content_fingerprint']})
        self.assertNotIn(self.a,{task['id'] for task in wf.parse(self.store.text())})
        wf.hook_admission(self.store,scope=self.a)
        with self.assertRaisesRegex(ValueError,'task|scope|select|current|unknown'):
            wf.actual_hook_context(self.store,before)
        ledger=self.store.base/'history/task-outcomes.jsonl';accepted=ledger.read_bytes()
        # Negative outcomes are confined to this disposable history fixture.
        for mutation in ['content-mismatch','cancelled']:
            rows=[json.loads(line) for line in accepted.decode().splitlines()]
            selected=next(row for row in rows if row['task_id']==self.a)
            if mutation=='content-mismatch':selected['task_context']['content_fingerprint']='0'*64
            else:selected['disposition']='cancelled'
            ledger.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.subTest(mutation=mutation),self.assertRaisesRegex(ValueError,'exact|successful|stale|context|body'):
                wf.hook_admission(self.store,scope=self.a)
            ledger.write_bytes(accepted)
        wf.hook_admission(self.store,scope=self.a)
        self.assertEqual(engine().read(self.store,frame['id'])['context'],before)

    def test_task_cancellation_requires_original_reconciliation_and_preserves_cl_hold(self):
        self.install();wf.begin_task(self.store,{'task_id':self.a});session=self.cl_start();frame=self.frame(session)
        actor={'id':'pending-cancel-actor','context_id':'pending-cancel-context'}
        frame=self.change(frame,'prepare',actor=actor,creation_evidence={'kind':'host-agent-created',
            'provider':'controlled-unit-host','tool':'controlled-create','reference':'Synthetic prepared original.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id']})
        original=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        outcome={'task_id':self.a,'disposition':'cancelled','outcome':'The fixture owner cancels the selected task.',
            'expected_source_hash':self.source_hash()}
        with self.assertRaisesRegex(ValueError,'pending|original|hook'):
            wf.complete(self.store,outcome)
        frame=self.change(frame,'reconcile',attempt_id=original['id'],status='cancelled',
            evidence={'kind':'host-reconciliation','reference':'Synthetic original cancellation before dispatch.'})
        with self.assertRaisesRegex(ValueError,'clarification|hold'):
            wf.complete(self.store,outcome)
        session=self.cl_change(session,'clarify-cancel',reason='The fixture owner ends the discussion.')
        result=wf.complete(self.store,{**outcome,'expected_source_hash':self.source_hash()})
        self.assertEqual(result['disposition'],'cancelled')
        self.assertEqual(wf.clarification_read(self.store,session['id'])['state'],'cancelled')
        self.assertEqual(engine().pending_scan(self.store),[])
        self.assertEqual(engine().read(self.store,frame['id'])['attempts'][original['id']]['input'],original['input'])


    def test_changed_draft_plan_preserves_stale_original_and_requires_exact_do_incorporation(self):
        self.install('skill-tree-implement-next-future-task','during')
        ctx=wf.actual_hook_context(self.store,{'kind':'task','id':'bridge-task:'+self.a,'task_ids':[self.a],'body':''})
        authority={'id':'during-plan-grant','revision':1,'context_id':ctx['id'],'allowed_kinds':['technical','specification-acceptance'],
            'constraints':['Synthetic guarded plan proposals only.'],'evidence':{'kind':'owner-message','reference':'Scripted isolated fixture authority.'}}
        core=wf.orchestration_action(self.store,'orchestration-start',{'request_id':'during-plan-frame','context':ctx,'mode':'manual',
            'authority':authority,'executor':{'id':'bridge-executor','context_id':'bridge-executor-context'},'expected_source_hash':self.source_hash()})
        def plan_change(command,**values):
            nonlocal core
            core=wf.orchestration_action(self.store,'orchestration-'+command,{'orchestration_id':core['id'],
                'expected_orchestration_hash':core['orchestration_hash'],'expected_orchestration_revision':core['revision'],
                'expected_source_hash':self.source_hash(),**values})
        plan_change('research',reference='Synthetic current source research.')
        plan_change('plan',plan_digest=sha('draft-one'),required_checks=['static'],reference='Synthetic draft one.')
        initial=wf.actual_hook_context(self.store,{**ctx,'orchestration_id':core['id']})
        frame=wf.hook_action(self.store,'hook-start',{'package_root':str(self.package_root),'request_id':'during-plan-hook',
            'event':{'id':'during-plan-event','operation':self.operation,'anchor':self.anchor},'context':initial,
            'mode':core['mode'],'authority':core['authority'],'executor':core['executor'],
            'capabilities':['codex-source-backed-context'],'expected_source_hash':self.source_hash()})
        frame=self.returned(frame,stop_after_invoke=True);original=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        task_bytes=self.store.text();plan_change('plan',plan_digest=sha('draft-two'),required_checks=['static'],reference='Synthetic changed draft two.')
        current=wf.actual_hook_context(self.store,initial)
        self.assertEqual(self.store.text(),task_bytes);self.assertNotEqual(initial['orchestration_plan_digest'],current['orchestration_plan_digest'])
        self.assertEqual(initial['semantic_fingerprint'],current['semantic_fingerprint'])
        evidence={**original['invoke_evidence'],'kind':'host-result','reference':'Synthetic late result for the original draft.'}
        with self.assertRaisesRegex(ValueError,'current|context|changed|stale'):
            self.change(frame,'record',attempt_id=original['id'],input_digest=original['input_digest'],delivery_digest=original['delivery_digest'],
                resolved_parameter_digest=original['resolved_parameter_digest'],result={'status':'findings'},evidence=evidence)
        self.assertEqual(engine().read(self.store,frame['id'])['attempts'][original['id']],original)
        frame=self.change(frame,'reconcile',attempt_id=original['id'],status='cancelled',evidence={'kind':'host-reconciliation','reference':'Synthetic original cancellation after draft replacement.'})
        frame=self.change(frame,'resume',context=current,retry=True,reason='The ordinary draft plan changed; retry against the current plan.')
        frame=self.returned(frame,status='findings');returned=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']]);before=copy.deepcopy(frame['context'])
        plan_change('plan',plan_digest=sha('draft-three'),required_checks=['static','plan-review'],reference='Synthetic incorporated draft three.')
        after=wf.actual_hook_context(self.store,before)
        base={'kind':'core-incorporation','before':engine().digest(before),'after':engine().digest(after)}
        with self.assertRaisesRegex(ValueError,'plan|receipt'):
            self.accept(frame,context=after,receipt={**base,'session_id':'CL-11111111-1111-4111-8111-111111111111'})
        plan_entries=[entry for entry in core['history'] if entry['event']=='plan']
        with self.assertRaisesRegex(ValueError,'previous|plan|event'):
            self.accept(frame,context=after,receipt={**base,'orchestration_id':core['id'],'plan_sequence':plan_entries[0]['sequence']})
        frame=self.accept(frame,context=after,receipt={**base,'orchestration_id':core['id'],'plan_sequence':plan_entries[-1]['sequence']})
        self.assertEqual(frame['cursor'],1);self.assertEqual(frame['context'],after)
        self.assertEqual(frame['attempts'][returned['id']]['input']['context'],before)
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input'])
        self.assertIsNone(core['plan_acceptance']);self.assertIsNone(core['checks']);self.assertIsNone(core['review'])
        frame=self.accept(self.returned(frame));self.assertEqual(frame['state'],'complete')
        self.assertEqual(frame['stages'][-1]['accepted_context']['orchestration_plan_digest'],sha('draft-three'))
        plan_change('question',purpose='plan',question={'id':'accept-draft','kind':'specification-acceptance','text':'Accept the current controlled draft?',
            'options':[{'id':'accept','text':'Accept the controlled plan.'},{'id':'revise','text':'Revise the controlled plan.'}],
            'recommendation':'accept','significance':'routine'})
        action=wf.orchestration_action(self.store,'orchestration-next',{'orchestration_id':core['id']})
        owner={'id':'scripted-plan-owner','context_id':'scripted-plan-owner-context'}
        plan_change('prepare-actor',actor=owner,input_digest=action['input_digest'],expected_decision_hash=action['decision_hash'])
        decision=wf.decision_helper().read(self.store,core['question_decision_id']);attempt=decision['attempts'][decision['prepared_attempt_id']]
        action=wf.orchestration_action(self.store,'orchestration-next',{'orchestration_id':core['id']})
        plan_change('record-actor',attempt_id=attempt['id'],expected_decision_hash=decision['decision_hash'],input_digest=action['input_digest'],
            result={'status':'answered','answer':'accept','rationale':'Synthetic owner accepts the exact controlled plan.'},
            evidence={'kind':'submitted-answer','reference':'Scripted fixture owner plan input; no real-human claim.',**{'actor_id':owner['id'],'actor_context_id':owner['context_id']}})
        plan_change('accept-decision');plan_change('accept-plan',decision_receipt=core['acceptance']);self.assertEqual(core['phase'],'implement')
        before=self.invocation_bytes(frame);wf.hook_admission(self.store,scope=self.a)
        self.assertEqual(self.invocation_bytes(frame),before)

    def test_consumed_pending_readiness_uses_exact_successful_linked_processing_receipt_only(self):
        run=wf.start(self.store,'next',self.a)
        pending=wf.intake(self.store,{'title':'Controlled consumed Pending','description':'Retain the exact selected request.',
            'expected_behavior':'The bounded request is processed explicitly.','priority':100})
        ctx=wf.actual_hook_context(self.store,{'kind':'pending','id':'controlled-pending-scope','pending_ids':[pending['id']],'run_id':run['id'],'body':''})
        receipt=wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'resolved','reason':'The controlled source research resolves the bounded request.'}},'tasks':[]})
        expected={key:ctx[key] for key in ['semantic_fingerprint','content_fingerprint']}
        self.assertEqual(receipt['pending_contexts'][pending['id']],expected)
        self.assertEqual(wf._hook_admitted_context(self.store,ctx),ctx)
        with self.assertRaisesRegex(ValueError,'Pending|pending|task|selector|unknown'):
            wf.actual_hook_context(self.store,ctx)
        original=self.store.state.read_bytes()
        for mutation in ['legacy','fingerprint','not-successful']:
            state=json.loads(original);row=state['active_run']['processing_results'][-1]
            if mutation=='legacy':row.pop('pending_contexts')
            elif mutation=='fingerprint':row['pending_contexts'][pending['id']]['content_fingerprint']='0'*64
            else:row['dispositions'][pending['id']]['status']='retained'
            self.store.state.write_text(json.dumps(state))
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError,'exact|receipt|successful|Pending|body'):
                    wf._hook_admitted_context(self.store,ctx)
            self.store.state.write_bytes(original)
        self.assertEqual(wf._hook_admitted_context(self.store,ctx),ctx)


    def test_noop_questions_need_core_resolution_and_real_format_edits_remain_incorporable(self):
        self.install();session=self.cl_start();frame=self.returned(self.frame(session),status='questions')
        before=copy.deepcopy(frame['context']);attempt=frame['attempts'][frame['prepared_attempt_id']]
        session=self.cl_change(session,'clarify-revise',tasks=[{'task_id':self.a,'body':self.body()}])
        after=wf.actual_hook_context(self.store,before);revision=session['task_revisions'][-1]
        self.assertEqual(before,after);self.assertEqual(session['answers'],{})
        receipt={'kind':'core-incorporation','session_id':session['id'],'task_revision_id':revision['id'],
            'before':engine().digest(before),'after':engine().digest(after)}
        unchanged=engine().read(self.store,frame['id'])
        with self.assertRaisesRegex(ValueError,'no-op|resolution|questions|findings'):
            self.accept(frame,context=after,receipt=receipt)
        self.assertEqual(engine().read(self.store,frame['id']),unchanged)
        resolution_context=wf._hook_resolution_context(after,frame,attempt,'hook-result-resolution')
        decision=wf.decision_action(self.store,'decision-start',{'request_id':'noop-question-resolution','context':resolution_context,
            'mode':'manual','authority':frame['authority'],'executor':frame['executor'],'expected_source_hash':self.source_hash(),
            'question':{'id':'resolve','kind':'technical','text':'Resolve the unchanged controlled contribution?',
                'options':[{'id':'dismiss','text':'Dismiss the controlled question with the recorded explanation.'}],
                'recommendation':'dismiss','significance':'routine'}})
        def decision_change(command,**values):
            nonlocal decision
            decision=wf.decision_action(self.store,'decision-'+command,{'decision_id':decision['id'],
                'expected_decision_hash':decision['decision_hash'],'expected_decision_revision':decision['revision'],
                'expected_mode_epoch':decision['mode_epoch'],'expected_context_fingerprint':decision['context']['content_fingerprint'],
                'expected_source_hash':self.source_hash(),**values})
        owner={'id':'scripted-fixture-owner','context_id':'scripted-fixture-owner-context'}
        decision_change('prepare',role='owner',actor=owner)
        decision_change('record',attempt_id=decision['prepared_attempt_id'],result={'status':'answered','answer':'dismiss','rationale':'The controlled question requires no task edit.'},
            evidence={'kind':'submitted-answer','reference':'Scripted disposable fixture-owner input; no real-human business approval.',
                'actor_id':owner['id'],'actor_context_id':owner['context_id']})
        decision_change('accept')
        frame=self.accept(frame,receipt={'kind':'core-resolution','before':engine().digest(before),'after':engine().digest(after),
            'decision_receipt':{'decision_id':decision['id'],'acceptance_digest':decision['acceptance']['digest']}})
        self.assertEqual(frame['cursor'],1)
        frame=self.returned(frame,status='findings');before=copy.deepcopy(frame['context'])
        session=self.cl_change(session,'clarify-revise',tasks=[{'task_id':self.a,'body':self.body().replace('Goal:\n- ','Goal:\n-  ',1)}])
        after=wf.actual_hook_context(self.store,before);revision=session['task_revisions'][-1]
        self.assertEqual(before['semantic_fingerprint'],after['semantic_fingerprint'])
        self.assertNotEqual(before['content_fingerprint'],after['content_fingerprint'])
        self.assertIn(self.a,revision['content_changed_task_ids'])
        frame=self.accept(frame,context=after,receipt={'kind':'core-incorporation','session_id':session['id'],'task_revision_id':revision['id'],
            'before':engine().digest(before),'after':engine().digest(after)})
        self.assertEqual(frame['state'],'complete')


    def test_inflight_declared_sources_are_sealed_rechecked_and_refreshed_only_for_retry_or_next_occurrence(self):
        directory=self.root/'src';directory.mkdir();child=directory/'child.py';child.write_text('CHILD = 1\n')
        pending=wf.intake(self.store,{'title':'Controlled directory source task','description':'Preserve bounded source inputs.','expected_behavior':'Declared directory and missing sources remain observable.','priority':100})
        body=self.body().replace('\"sources\": [\"source.py\"]','\"sources\": [\"source.py\", \"src\", \"future-source.py\"]')
        self.a=wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Source research identifies bounded directory inputs.'}},'tasks':[{'title':'Controlled directory source task','body':body,'parent_pending_ids':[pending['id']]}]})['created_ids'][0]
        self.install();frame=self.frame();source=self.root/'source.py';initial=source.read_text()
        actor={'id':'source-guard-actor','context_id':'source-guard-context'}
        frame=self.change(frame,'prepare',actor=actor,creation_evidence={'kind':'host-agent-created','provider':'controlled-unit-host',
            'tool':'controlled-create','reference':'Synthetic declared-source actor creation.','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        original=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        self.assertEqual(original['input']['scope_source_snapshot'],{'source.py':sha(initial),'src':wf.binding_snapshot(self.root,['src']),'future-source.py':None})
        private=wf._hook_node(self.package_root,{'runtime_action':'delivery-data','project_root':str(self.root),'event':frame['event'],
            'context':frame['context'],'capabilities':['codex-source-backed-context'],'adapter':{'provider':'codex','mechanism':'source-backed-context'},
            'configuration':frame['configuration'],'chain_id':frame['id'],'attempt_id':original['id'],'binding_id':original['binding_id'],
            'public_input':original['input'],'input_digest':original['input_digest'],'authority':frame['authority']})
        headers={key:private[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
        evidence={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-dispatch','reference':'Synthetic declared-source invocation.',
            'actor_id':actor['id'],'actor_context_id':actor['context_id'],'mechanism':'source-backed-context'}
        child.write_text('CHILD = 2\n')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.change(frame,'invoke',attempt_id=original['id'],**headers,evidence=evidence)
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        child.write_text('CHILD = 1\n');missing=self.root/'future-source.py';missing.write_text('CREATED = True\n')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.change(frame,'invoke',attempt_id=original['id'],**headers,evidence=evidence)
        self.assertEqual(engine().read(self.store,frame['id']),frame);missing.unlink()
        source.write_text('VALUE = 2\n')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.change(frame,'invoke',attempt_id=original['id'],**headers,evidence=evidence)
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        frame=self.change(frame,'reconcile',attempt_id=original['id'],status='cancelled',evidence={'kind':'host-reconciliation','reference':'Synthetic prepared original cancellation after source drift.'})
        frame=self.change(frame,'resume',retry=True,reason='Retry the same occurrence against the actual changed declared sources.')
        frame=self.returned(frame,stop_after_invoke=True);invoked=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        self.assertEqual(invoked['input']['scope_source_snapshot']['source.py'],sha('VALUE = 2\n'))
        source.write_text('VALUE = 3\n')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.change(frame,'record',attempt_id=invoked['id'],input_digest=invoked['input_digest'],delivery_digest=invoked['delivery_digest'],
                resolved_parameter_digest=invoked['resolved_parameter_digest'],result={'status':'passed'},
                evidence={**invoked['invoke_evidence'],'kind':'host-result','reference':'Synthetic stale original result.'})
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        frame=self.change(frame,'reconcile',attempt_id=invoked['id'],status='cancelled',evidence={'kind':'host-reconciliation','reference':'Synthetic invoked original cancellation after source drift.'})
        frame=self.change(frame,'resume',retry=True,reason='Retry against the current declared source after reconciling the actual original.')
        frame=self.returned(frame);returned=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        source.write_text('VALUE = 4\n')
        self.assertEqual(wf.hook_action(self.store,'hook-next',{'chain_id':frame['id']})['action'],'prerequisite')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.accept(frame)
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        frame=self.change(frame,'resume',retry=True,reason='Re-evaluate the returned contribution under the current declared source.')
        frame=self.accept(self.returned(frame));accepted=copy.deepcopy(frame['attempts'])
        self.assertEqual(frame['cursor'],1)
        source.write_text('VALUE = 5\n');frame=self.returned(frame)
        latest=frame['attempts'][frame['prepared_attempt_id']]
        self.assertEqual(latest['input']['scope_source_snapshot']['source.py'],sha('VALUE = 5\n'))
        self.assertTrue(all(frame['attempts'][key]==value for key,value in accepted.items()))
        frame=self.accept(frame);self.assertEqual(frame['state'],'complete')
        source.write_text('VALUE = 6\n')
        wf.hook_admission(self.store,scope=self.a)
        self.assertEqual(frame['attempts'][original['id']]['input'],original['input'])
        self.assertEqual(frame['attempts'][returned['id']]['input'],returned['input'])


    def test_declared_workflow_directory_excludes_mutable_receipts_but_keeps_authored_research(self):
        research=self.store.base/'history/research';research.mkdir(parents=True);plan=research/'plan.md';plan.write_text('Authored source plan one.\n')
        pending=wf.intake(self.store,{'title':'Controlled metadata source task','description':'Preserve actual source and guarded workflow planes.',
            'expected_behavior':'Ordinary core receipts remain mutable while authored research remains a source.','priority':100})
        body=self.body().replace('"sources": ["source.py"]','"sources": ["source.py", ".skill-tree/documents/future.md", ".skill-tree"]')
        self.a=wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted','reason':'Source research distinguishes runtime receipts from authored source.'}},
            'tasks':[{'title':'Controlled metadata source task','body':body,'parent_pending_ids':[pending['id']]}]})['created_ids'][0]
        self.install();session=self.cl_start();frame=self.returned(self.frame(session),status='findings');before=copy.deepcopy(frame['context'])
        original=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']]);snapshot=original['input']['scope_source_snapshot']
        self.assertIn('.skill-tree',snapshot);self.assertIn('source.py',snapshot);self.assertNotIn('.skill-tree/documents/future.md',snapshot)
        for relative in ['artifacts/dispatch.json','run-evidence/receipt.json','history/checkpoints/checkpoint.json']:
            path=self.store.base/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{"fixture":"mutable"}')
        revised=body.replace('Preserve selected behavior.','Preserve the incorporated source marker.',1)
        session=self.cl_change(session,'clarify-revise',tasks=[{'task_id':self.a,'body':revised}]);after=wf.actual_hook_context(self.store,before)
        frame=self.accept(frame,context=after,receipt={'kind':'core-incorporation','session_id':session['id'],'task_revision_id':session['task_revisions'][-1]['id'],
            'before':engine().digest(before),'after':engine().digest(after)})
        self.assertEqual(frame['cursor'],1)
        frame=self.returned(frame,stop_after_invoke=True);attempt=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
        plan.write_text('Authored source plan two.\n')
        with self.assertRaisesRegex(ValueError,'source.*changed|source bytes|declared source'):
            self.change(frame,'record',attempt_id=attempt['id'],input_digest=attempt['input_digest'],delivery_digest=attempt['delivery_digest'],
                resolved_parameter_digest=attempt['resolved_parameter_digest'],result={'status':'passed'},
                evidence={**attempt['invoke_evidence'],'kind':'host-result','reference':'Synthetic result after authored research drift.'})
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        frame=self.change(frame,'reconcile',attempt_id=attempt['id'],status='cancelled',evidence={'kind':'host-reconciliation','reference':'Synthetic original cancellation after authored source drift.'})
        frame=self.change(frame,'resume',retry=True,reason='Recheck the same occurrence against current authored source.')
        frame=self.accept(self.returned(frame));self.assertEqual(frame['state'],'complete')
        self.assertEqual(frame['attempts'][original['id']]['input']['scope_source_snapshot'],snapshot)


    def test_current_hold_rejects_cached_private_delivery_before_provider_or_sink_without_mutation(self):
        self.install();actual_node=wf._hook_node
        for kind in ['global','current','unresolved','source-drift','already-invoking','relocated-package','context-drift']:
            with self.subTest(kind=kind):
                frame=self.prepare_bridge(self.frame(request_id='cached-private-'+kind));attempt=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']])
                delivery=self.delivery_bridge(frame);headers={key:delivery[key] for key in ['input_digest','delivery_digest','resolved_parameter_digest']}
                evidence={'kind':'host-invoked','provider':'controlled-unit-host','tool':'controlled-dispatch','reference':'Synthetic cached exact original delivery.',
                    'actor_id':attempt['actor']['id'],'actor_context_id':attempt['actor']['context_id'],'mechanism':'source-backed-context'}
                calls=[]
                def provider(request):calls.append('provider');self.assertFalse((self.store.base/'.writer-lock').exists());return copy.deepcopy(delivery)
                def sink(value):calls.append('sink');self.assertFalse((self.store.base/'.writer-lock').exists())
                relocated=self.root/'relocated-operation'
                if kind=='relocated-package':shutil.copytree(self.package_root,relocated)
                def invoke(current):return wf.hook_action(self.store,'hook-invoke',{'chain_id':current['id'],'expected_chain_hash':current['chain_hash'],
                    'expected_chain_revision':current['revision'],'expected_source_hash':self.source_hash(),'attempt_id':attempt['id'],
                    **headers,'evidence':evidence,**({'package_root':str(relocated)} if kind=='relocated-package' else {})},private_delivery_provider=provider,private_delivery_sink=sink)
                if kind=='already-invoking':frame=invoke(frame);calls.clear()
                source=self.root/'source.py';original_source=source.read_bytes()
                if kind=='source-drift':source.write_text('VALUE = 9\n')
                if kind=='context-drift':
                    revised=self.revise(self.cl_start());revised_body=wf.resolve(wf.parse(self.store.text()),[self.a])[0]['body']
                    self.assertTrue(revised['task_revisions']);self.assertNotEqual(wf.actual_hook_context(self.store,frame['context']),frame['context'])
                before=self.invocation_bytes(frame)
                try:
                    prepared=actual_node if kind in {'source-drift','already-invoking','relocated-package','context-drift'} else self.injected_prerequisite(actual_node,kind,attempt['binding_id'])
                    with patch.object(wf,'_hook_node',prepared):
                        with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held|source.*changed|source bytes|original prepared|watch|baseline|context|current invocation'):
                            invoke(frame)
                    self.assertEqual(calls,[]);self.assertEqual(self.invocation_bytes(frame),before)
                finally:source.write_bytes(original_source)
                if kind=='context-drift':
                    self.assertEqual(wf.resolve(wf.parse(self.store.text()),[self.a])[0]['body'],revised_body)
                    self.assertEqual(engine().read(self.store,frame['id'])['attempts'][attempt['id']]['input'],attempt['input']);continue
                if kind=='already-invoking':continue
                if kind=='relocated-package':shutil.rmtree(relocated);continue
                current=invoke(frame)
                self.assertEqual(calls,['provider','sink']);self.assertEqual(current['prepared_attempt_id'],attempt['id'])
                self.assertEqual(current['attempts'][attempt['id']]['input'],attempt['input'])
                self.assertEqual(current['attempts'][attempt['id']]['status'],'invoking')

    def test_completed_hook_admission_rechecks_prerequisite_only_hold_without_rewriting_history(self):
        self.install();frame=self.accept(self.returned(self.frame()));frame=self.accept(self.returned(frame))
        self.assertEqual(frame['state'],'complete');before=self.invocation_bytes(frame);actual_node=wf._hook_node
        wf.hook_admission(self.store,scope=self.a,chain_ids=[frame['id']])
        with patch.object(wf,'_hook_node',self.injected_prerequisite(actual_node,'global','unused-completed-binding')):
            with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                wf.hook_admission(self.store,scope=self.a,chain_ids=[frame['id']])
        self.assertEqual(self.invocation_bytes(frame),before)
        self.assertEqual(engine().read(self.store,frame['id']),frame)
        wf.hook_admission(self.store,scope=self.a,chain_ids=[frame['id']])
        self.assertEqual(self.invocation_bytes(frame),before);self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')

    def test_actual_node_unresolved_current_location_never_skips_to_later_or_complete(self):
        for incompatible in ['editor','all']:
            with self.subTest(incompatible=incompatible):
                # Each actual installed fixture has its own project and queue ownership.
                with tempfile.TemporaryDirectory() as temporary:
                    original_root,original_store,original_a,original_b=self.root,self.store,self.a,self.b
                    self.root=Path(temporary);self.store=wf.Store(self.root);self.store.future.parent.mkdir(parents=True)
                    self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
                    (self.store.base/'config').mkdir();(self.store.base/'config/repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
                    (self.root/'source.py').write_text('VALUE = 1\n');self.a=self.task('Selected unresolved task',100);self.b=self.task('Other unresolved task',1)
                    try:
                        self.install_ordered_capability_fixture(incompatible);frame=self.frame(request_id='actual-unresolved-'+incompatible)
                        proof=wf._hook_node(self.package_root,{'runtime_action':'occurrence-plan','project_root':str(self.root),'event':frame['event'],
                            'context':frame['context'],'configuration':frame['configuration'],'capabilities':self.capabilities,
                            'adapter':{'provider':'codex','mechanism':'source-backed-context'}})
                        self.assertEqual([row['id'] for row in proof['bindings']],['interview-middle'] if incompatible=='editor' else [])
                        self.assertIn('editor-first',[row['id'] for row in proof['unresolved']]);before=self.invocation_bytes(frame)
                        with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                            self.prepare_bridge(frame)
                        self.assertEqual(self.invocation_bytes(frame),before);self.assertEqual(engine().read(self.store,frame['id'])['cursor'],0)
                    finally:self.root,self.store,self.a,self.b=original_root,original_store,original_a,original_b

    def test_upstream_manifest_named_json_remains_an_ordinary_pinned_resource(self):
        self.install(resource_collision=True)
        resource=self.package_root/'plugins/controlled/upstream/references/plugin-bindings.json'
        self.assertEqual(json.loads(resource.read_text()),{'kind':'ordinary-upstream-data'})
        try:
            frame=self.accept(self.returned(self.frame()));frame=self.accept(self.returned(frame))
            wf.hook_admission(self.store,scope=self.a)
        except ValueError as error:self.fail('An upstream references/plugin-bindings.json must remain ordinary pinned data: '+str(error))
        self.assertEqual(frame['state'],'complete');self.assertEqual(json.loads(resource.read_text()),{'kind':'ordinary-upstream-data'})

    def test_pure_writer_readiness_rechecks_exact_resource_inventory_without_node(self):
        self.install();frame=self.accept(self.returned(self.frame()));frame=self.accept(self.returned(frame))
        retained=self.invocation_bytes(frame);actual_node=wf._hook_node
        def outside_writer(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'Inventory closure is rechecked without Node under the writer lock.')
            return actual_node(package_root,request)
        with patch.object(wf,'_hook_node',outside_writer):
            for kind,relative in [('dispatcher-extra','scripts/extra.js'),('plugin-extra','plugins/controlled/upstream/extra.md'),
                ('dispatcher-link','scripts/unowned-link'),('missing','scripts/plugin-runtime.js'),('cache','scripts/__pycache__/controlled.pyc')]:
                with self.subTest(kind=kind):
                    wf.prepare_hook_admission(self.store,scope=self.a);path=self.package_root/relative;original=path.read_bytes() if path.is_file() else None
                    if kind=='missing':path.unlink()
                    elif kind=='dispatcher-link':path.symlink_to(self.root/'source.py')
                    else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Controlled post-preflight inventory change.')
                    try:
                        with self.store.lock():
                            if kind=='cache':wf.hook_admission(self.store,scope=self.a)
                            else:
                                with self.assertRaisesRegex(ValueError,'inventory|closure|resource|symlink|changed|watch'):
                                    wf.hook_admission(self.store,scope=self.a)
                        self.assertEqual(self.invocation_bytes(frame),retained)
                    finally:
                        path.unlink(missing_ok=True)
                        if original is not None:path.write_bytes(original)

    def test_copied_wf_disabled_and_condition_excluded_starts_are_task_free_noops_without_masking_existing_hi(self):
        original_root,original_store=self.root,self.store
        for variant,options in [('disabled',{'enabled':False}),('excluded',{'condition':False}),
            ('pending-replay',{'condition':{'equals':{'path':'/enabled','value':True}}})]:
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temporary:
                base=Path(temporary);self.root=base/'managed';self.root.mkdir();self.store=wf.Store(self.root)
                try:
                    self.install('skill-tree-add-pending-task','before',binding_options=options)
                    bundle=base/'standalone';shutil.copytree(self.package_root,bundle)
                    copied=load('noop_copied_wf_'+variant,bundle/'scripts/workflow-state.py');execution=base/'execution';execution.mkdir()
                    store=copied.Store(execution,allow_unselected=True,neutral=True)
                    ctx={'kind':'request','id':'copied-noop-request','enabled':True}
                    grant={'id':'copied-noop-grant','revision':1,'context_id':ctx['id'],'allowed_kinds':['technical'],
                        'constraints':['Synthetic copied task-free metadata only.'],'evidence':{'kind':'owner-message','reference':'Scripted standalone fixture.'}}
                    payload={'package_root':str(bundle),'request_id':'copied-noop-'+variant,'event':{'id':'copied-noop-event',
                        'operation':self.operation,'anchor':self.anchor},'context':ctx,'mode':'manual','authority':grant,
                        'executor':{'id':'copied-executor','context_id':'copied-executor-context'},'capabilities':['codex-source-backed-context']}
                    frame=copied.hook_action(store,'hook-start',payload)
                    if variant=='pending-replay':
                        actor={'id':'copied-original-actor','context_id':'copied-original-context'}
                        frame=copied.hook_action(store,'hook-prepare',{'chain_id':frame['id'],'expected_chain_hash':frame['chain_hash'],
                            'expected_chain_revision':frame['revision'],'actor':actor,'creation_evidence':{'kind':'host-agent-created',
                            'provider':'controlled-unit-host','tool':'controlled-create','reference':'Synthetic isolated actor; no provider called.',
                            'actor_id':actor['id'],'actor_context_id':actor['context_id']}})
                        record=store.base/'invocations'/(frame['id'].lower()+'.json');before=record.read_bytes()
                        with self.assertRaisesRegex(ValueError,'identity|reused|different|original|context'):
                            copied.hook_action(store,'hook-start',{**payload,'context':{**ctx,'enabled':False}})
                        self.assertEqual(record.read_bytes(),before)
                    else:
                        self.assertEqual(frame.get('status'),'noop');self.assertEqual(frame['state'],'complete')
                        self.assertFalse((store.base/'invocations').exists());self.assertFalse((store.base/'local/hook-locations').exists())
                        with patch.object(copied,'_hook_node',side_effect=AssertionError('No-op admission cannot require Node.')):
                            copied.hook_admission(store,scope=ctx)
                    self.assertFalse(store.future.exists());self.assertFalse(store.state.exists())
                finally:self.root,self.store=original_root,original_store

    def test_core_callers_prepare_exact_scoped_readiness_before_writer_entry(self):
        self.install();frame=self.accept(self.returned(self.frame()));frame=self.accept(self.returned(frame))
        unrelated=self.frame(request_id='unrelated-held-chain',task_id=self.b)
        actual_node=wf._hook_node;queries=[]
        def outside_writer(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'Core readiness must prepare owned metadata outside the writer scope.')
            if request.get('runtime_action')=='readiness-plan':queries.append(request['context']['id'])
            return actual_node(package_root,request)
        with patch.object(wf,'_hook_node',outside_writer):
            previous=len(queries);run=wf.start(self.store,'next',self.a);self.assertGreater(len(queries),previous)
            linked=self.accept(self.returned(self.frame(request_id='linked-controller-chain',run_id=run['id'])))
            linked=self.accept(self.returned(linked));self.assertEqual(linked['state'],'complete')
            previous=len(queries);self.assertEqual(wf.advance(self.store)['task_id'],self.a);self.assertGreater(len(queries),previous)
            previous=len(queries);wf.begin_task(self.store,{'task_id':self.a});self.assertGreater(len(queries),previous)
            pending=wf.intake(self.store,{'title':'No optional Pending hook','description':'Resolve the isolated bounded request.',
                'expected_behavior':'No unrelated hook is consulted.','priority':1})
            previous=len(queries);wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'resolved',
                'reason':'The bounded source request requires no further work.'}},'tasks':[]});self.assertEqual(len(queries),previous)
            previous=len(queries);self.finish_task(self.a);self.assertGreater(len(queries),previous)
            previous=len(queries);wf.finish(self.store);self.assertGreater(len(queries),previous)
        self.assertIsNone(self.store.load()['active_run'])
        with self.assertRaisesRegex(ValueError,'actual recorded run'):wf._hook_controller(self.store,run['id'])
        archive=self.store.base/'history/runs'/('run-'+run['id'].lower()+'.json');original_archive=archive.read_bytes()
        retained=self.invocation_bytes(linked)
        for field,value in [('id','WR-11111111-1111-4111-8111-111111111111'),('phase','implement'),('snapshot','invalid'),('completed_ids',[]),('completion_refs',{}),('finished_at',None)]:
            with self.subTest(archive_field=field):
                changed=json.loads(original_archive);changed[field]=value;archive.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError,'recorded run|completed|successful|corrupt|checkpoint|identity'):
                    wf.hook_admission(self.store,scope=self.a,chain_ids=[linked['id']])
                self.assertEqual(self.invocation_bytes(linked),retained);archive.write_bytes(original_archive)
        wf.hook_admission(self.store,scope=self.a,chain_ids=[linked['id']])
        self.assertEqual(engine().read(self.store,unrelated['id'])['cursor'],0)
        self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')

    def test_finish_rejects_carrier_reference_disappearance_before_writer_entry(self):
        self.install();run=wf.start(self.store,'next',self.a)
        frame=self.accept(self.returned(self.frame(request_id='finish-carrier-chain',run_id=run['id'])))
        frame=self.accept(self.returned(frame));self.finish_task(self.a)
        original_state=self.store.state.read_bytes();retained=self.invocation_bytes(frame);actual_lock=wf.Store.lock;changed=[]
        @contextmanager
        def reference_race(store):
            if store.root==self.store.root and not changed:
                value=json.loads(store.state.read_text());self.assertEqual(value['active_run']['hook_chains'],[frame['id']])
                value['active_run']['hook_chains']=[];store.state.write_text(json.dumps(value));changed.append(store.state.read_bytes())
            with actual_lock(store):yield
        try:
            with patch.object(wf.Store,'lock',reference_race):
                with self.assertRaisesRegex(ValueError,'reference|selection|preflight|changed|carrier|admission'):
                    wf.finish(self.store)
            self.assertTrue(changed);self.assertEqual(self.store.state.read_bytes(),changed[0]);self.assertEqual(self.invocation_bytes(frame),retained)
            self.assertFalse((self.store.base/'history/runs'/('run-'+run['id'].lower()+'.json')).exists())
        finally:self.store.state.write_bytes(original_state)
        self.assertEqual(wf.finish(self.store)['id'],run['id'])

    def test_start_rechecks_completed_dependency_preflight_inside_the_writer(self):
        self.install();old=self.accept(self.returned(self.frame(request_id='old-completed-dependency-hook',task_id=self.b)))
        old=self.accept(self.returned(old));self.finish_task(self.b)
        pending=wf.intake(self.store,{'title':'Require the actual completed dependency','description':'Reuse the already completed task.',
            'expected_behavior':'The dependency hook remains current at controller admission.','priority':1})
        wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted',
            'reason':'Source research identifies the existing dependency.'}},'tasks':[{'reuse_id':self.a,'title':'Selected task',
            'body':self.body(),'parent_pending_ids':[pending['id']],'depends_on':[self.b]}]})
        path=self.store.base/'invocations'/(old['id'].lower()+'.json');original=path.read_bytes();state=self.store.state.read_bytes()
        actual_lock=wf.Store.lock;changed=[]
        @contextmanager
        def dependency_race(store):
            if store.root==self.store.root and not changed:
                value=json.loads(path.read_text());value['controlled_concurrent_note']='The completed dependency proof changed before the writer.'
                value['chain_hash']=engine().digest({key:item for key,item in value.items() if key!='chain_hash'})
                path.write_text(json.dumps(value));changed.append(path.read_bytes())
            with actual_lock(store):yield
        try:
            with patch.object(wf.Store,'lock',dependency_race):
                with self.assertRaisesRegex(ValueError,'reference|selection|preflight|changed|identity|admission'):
                    wf.start(self.store,'next',self.a)
            self.assertTrue(changed);self.assertEqual(self.store.state.read_bytes(),state);self.assertEqual(path.read_bytes(),changed[0])
        finally:path.write_bytes(original)
        self.assertEqual(wf.start(self.store,'next',self.a)['root_task_id'],self.a)

    def test_finished_readiness_preserves_actual_reused_completed_dependency_without_new_completion(self):
        self.install();old=self.finish_task(self.b);self.assertIsNone(old['run_id'])
        pending=wf.intake(self.store,{'title':'Reuse a completed dependency','description':'Use the already accepted dependency.',
            'expected_behavior':'The selected new root retains the actual completed dependency.','priority':1})
        wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'promoted',
            'reason':'Source research identifies the existing completed dependency.'}},'tasks':[{'reuse_id':self.a,'title':'Selected task',
            'body':self.body(),'parent_pending_ids':[pending['id']],'depends_on':[self.b]}]})
        run=wf.start(self.store,'next',self.a);self.assertIn(self.b,run['required_ids']);self.assertNotIn(self.b,run['completed_ids'])
        frame=self.accept(self.returned(self.frame(request_id='reused-dependency-controller-chain',run_id=run['id'])))
        frame=self.accept(self.returned(frame));self.finish_task(self.a);finished=wf.finish(self.store)
        self.assertEqual(finished['completed_ids'],[self.a]);self.assertNotIn(self.b,finished.get('completion_refs',{}))
        self.assertEqual(next(row for row in self.store.outcomes() if row['task_id']==self.b)['id'],old['id'])
        before=self.invocation_bytes(frame)
        try:wf.hook_admission(self.store,scope=self.a,chain_ids=[frame['id']])
        except ValueError as error:self.fail('A real finished run reusing an accepted completed dependency must retain readiness: '+str(error))
        self.assertEqual(self.invocation_bytes(frame),before);self.assertIsNone(self.store.load()['active_run'])

    def test_standalone_pending_process_rechecks_readiness_before_consuming_the_original_scope(self):
        self.install(anchor='before');pending=wf.intake(self.store,{'title':'Selected standalone Pending','description':'Resolve the exact bounded request.',
            'expected_behavior':'The source request is resolved after required hooks.','priority':1})
        ctx=wf.actual_hook_context(self.store,{'kind':'pending','id':'standalone-pending-hook','pending_ids':[pending['id']],'body':''})
        grant={'id':'standalone-pending-grant','revision':1,'context_id':ctx['id'],'allowed_kinds':['technical'],
            'constraints':['Synthetic standalone processing only.'],'evidence':{'kind':'owner-message','reference':'Scripted isolated Pending fixture.'}}
        frame=wf.hook_action(self.store,'hook-start',{'package_root':str(self.package_root),'request_id':'standalone-pending-chain',
            'event':{'id':'standalone-pending-event','operation':self.operation,'anchor':self.anchor},'context':ctx,'mode':'manual',
            'authority':grant,'executor':{'id':'pending-executor','context_id':'pending-executor-context'},'capabilities':['codex-source-backed-context'],
            'expected_source_hash':self.source_hash()})
        frame=self.accept(self.returned(frame));frame=self.accept(self.returned(frame));before=self.invocation_bytes(frame)
        actual_node=wf._hook_node;queries=[]
        def outside_writer(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists())
            if request.get('runtime_action')=='readiness-plan':queries.append(request['context']['id'])
            return actual_node(package_root,request)
        with patch.object(wf,'_hook_node',outside_writer):
            receipt=wf.process(self.store,{'selectors':[pending['id']],'dispositions':{pending['id']:{'status':'resolved',
                'reason':'Source research resolves the exact standalone request.'}},'tasks':[]})
        self.assertTrue(queries);self.assertEqual(receipt['selected_ids'],[pending['id']]);self.assertEqual(self.invocation_bytes(frame),before)
        self.assertNotIn(pending['id'],[task['id'] for task in wf.parse(self.store.text())]);self.assertIsNone(self.store.load()['active_run'])

    def test_readiness_preflight_rejects_changed_matching_identity_and_new_matching_chain_inside_writer(self):
        self.install();frame=self.accept(self.returned(self.frame()));frame=self.accept(self.returned(frame))
        self.assertTrue(callable(getattr(wf,'prepare_hook_admission',None)),'A trusted scope-bound readiness preflight is required.')
        actual_node=wf._hook_node;chain_path=self.store.base/'invocations'/ (frame['id'].lower()+'.json')
        locator_path=self.store.base/'local/hook-locations'/(frame['id'].lower()+'.json')
        def outside_writer(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'A writer-side admission recheck cannot start Node.')
            return actual_node(package_root,request)
        with patch.object(wf,'_hook_node',outside_writer):
            for kind,path in [('chain',chain_path),('locator',locator_path),('deleted-chain',chain_path)]:
                with self.subTest(kind=kind):
                    wf.prepare_hook_admission(self.store,scope=self.a);original=path.read_bytes();value=json.loads(original)
                    if kind=='chain':
                        value['controlled_concurrent_note']='Another metadata writer changed the complete chain.'
                        value['chain_hash']=engine().digest({key:item for key,item in value.items() if key!='chain_hash'})
                    elif kind=='locator':value['capabilities'].append('controlled-concurrent-capability')
                    if kind=='deleted-chain':path.unlink()
                    else:path.write_text(json.dumps(value))
                    before=self.invocation_bytes(frame)
                    try:
                        with self.store.lock():
                            with self.assertRaisesRegex(ValueError,'preflight|changed|current|identity|prerequisite|admission'):
                                wf.hook_admission(self.store,scope=self.a)
                        self.assertEqual(self.invocation_bytes(frame),before)
                    finally:path.write_bytes(original)
                    wf.hook_admission(self.store,scope=self.a)
            wf.prepare_hook_admission(self.store,scope=self.a)
            added=self.frame(request_id='matching-chain-added-after-preflight');before=self.invocation_bytes(added)
            with self.store.lock():
                with self.assertRaisesRegex(ValueError,'preflight|unfinished|current|prerequisite|admission'):
                    wf.hook_admission(self.store,scope=self.a)
            self.assertEqual(self.invocation_bytes(added),before);self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')
            added_chain=self.store.base/'invocations'/(added['id'].lower()+'.json')
            added_locator=self.store.base/'local/hook-locations'/(added['id'].lower()+'.json')
            added_bytes,added_location=added_chain.read_bytes(),added_locator.read_bytes()
            added_chain.unlink();added_locator.unlink();retained=chain_path.read_bytes()
            manifest=self.store.base/'skill-tree.json';navigation=manifest.read_bytes()
            for selection in ['existing-complete','empty']:
                with self.subTest(commit_selection=selection):
                    if selection=='empty':chain_path.unlink()
                    try:
                        wf.prepare_hook_admission(self.store,scope=self.a)
                        with self.store.lock():
                            wf.hook_admission(self.store,scope=self.a)
                            added_chain.write_bytes(added_bytes);added_locator.write_bytes(added_location)
                            with self.assertRaisesRegex(ValueError,'preflight|changed|current|identity|prerequisite|admission'):
                                self.store.commit({'.skill-tree/skill-tree.json':'{"unexpected_navigation_write":true}\n'})
                        self.assertEqual(manifest.read_bytes(),navigation)
                    finally:
                        added_chain.unlink(missing_ok=True);added_locator.unlink(missing_ok=True);chain_path.write_bytes(retained)

    def test_pr_ready_and_merge_gate_prepare_referenced_review_chains_outside_writer(self):
        self.install('skill-tree-pr-review-cycle','after')
        pr=load('managed_readiness_pr_fixture',CORE/'common/scripts/pr-review-state.py')
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True)
        snapshot={'repo_id':'controlled-repository','remote':'origin','source_branch':'feature/controlled','target_branch':'develop',
            'head':'a'*40,'base_oid':'b'*40,'changed_files':['source.py'],'pr':{'id':'PR-controlled','url':'https://example.invalid/pr/1','number':1},
            'state':'OPEN','threads':[],'reviews':[],'comments':[],'checks':[],'checks_known':True,'approvals_known':True,
            'approvals_required':False,'approved':True,'mergeable':'MERGEABLE'}
        ctx=pr.hook_context(snapshot);grant={'id':'review-fixture-grant','revision':1,'context_id':ctx['id'],'allowed_kinds':['technical'],
            'constraints':['Synthetic metadata review only; no publication or merge execution.'],
            'evidence':{'kind':'owner-message','reference':'Scripted isolated metadata fixture permission.'}}
        frame=wf.hook_action(self.store,'hook-start',{'package_root':str(self.package_root),'request_id':'controlled-review-chain',
            'event':{'id':'controlled-review-event','operation':self.operation,'anchor':self.anchor},'context':ctx,'mode':'manual',
            'authority':grant,'executor':{'id':'review-executor','context_id':'review-executor-context'},
            'capabilities':['codex-source-backed-context'],'expected_source_hash':self.source_hash()})
        frame=self.accept(self.returned(frame));frame=self.accept(self.returned(frame))
        record=pr.new_record(snapshot,pr.parameters(snapshot['source_branch'],{'merge':True}))
        record=pr.reviewed(record,snapshot,{'head':snapshot['head'],'base_oid':snapshot['base_oid'],'target_branch':snapshot['target_branch'],
            'files':['source.py'],'context_inspected':True,'discussions_inspected':True,'checks_inspected':True,'findings':[],'evidence':['controlled-review.json']})
        record=pr.attach_hook_chain(self.store,record,snapshot,frame['id']);publication='d'*32
        path=self.store.base/'history/publications'/('pub-'+publication+'.json');path.parent.mkdir(parents=True);path.write_text(json.dumps(record))
        source=self.root/'controlled-pr-input.json';source.write_text(json.dumps({'snapshot':snapshot}))
        actual_node=wf._hook_node;queries=[];actual_owned=pr.owned_module
        def shared_workflow(name,path):return wf if path.name=='workflow-state.py' else actual_owned(name,path)
        def outside_writer(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'PR metadata readiness cannot start Node under the writer lock.')
            if request.get('runtime_action')=='readiness-plan':queries.append(request['context']['id'])
            return actual_node(package_root,request)
        with patch.object(pr,'owned_module',shared_workflow),patch.object(wf,'_hook_node',outside_writer):
            for command in ['ready','merge-gate']:
                with self.subTest(command=command),patch('sys.stdout',new_callable=io.StringIO) as output:
                    previous=len(queries);code=pr.main([command,str(self.root),'--publication-id',publication,'--input',str(source)])
                    self.assertEqual(code,0,output.getvalue());self.assertGreater(len(queries),previous)
            actual_lock=wf.Store.lock
            for command in ['ready','merge-gate']:
                with self.subTest(disappeared_carrier=command):
                    original=path.read_bytes();changed=[]
                    @contextmanager
                    def reference_race(store):
                        if store.root==self.store.root and not changed:
                            value=json.loads(path.read_text());self.assertEqual(value['hook_chains'],[frame['id']])
                            value['hook_chains']=[];path.write_text(json.dumps(value));changed.append(path.read_bytes())
                        with actual_lock(store):yield
                    try:
                        with patch.object(wf.Store,'lock',reference_race),patch('sys.stdout',new_callable=io.StringIO) as output:
                            code=pr.main([command,str(self.root),'--publication-id',publication,'--input',str(source)])
                        self.assertTrue(changed);self.assertEqual(code,2,output.getvalue());self.assertEqual(path.read_bytes(),changed[0])
                    finally:path.write_bytes(original)
        self.assertEqual(engine().read(self.store,frame['id'])['state'],'complete')

    def test_business_transition_cannot_silently_replace_the_original_watch_baseline(self):
        self.install();frame=self.frame();before=self.invocation_bytes(frame);registry=self.store.base/'installation/plugins.json';original=registry.read_bytes()
        frozen=json.loads(before['.skill-tree/local/hook-locations/'+frame['id'].lower()+'.json'])['watch']
        # Equivalent registry JSON preserves its semantic identity but changes the frozen raw watch.
        registry.write_text(json.dumps(json.loads(original),ensure_ascii=True,separators=(',',':')))
        self.assertNotEqual(registry.read_bytes(),original)
        with self.assertRaisesRegex(ValueError,'watch|configuration|registry|changed|reconcile|prerequisite|drift'):
            self.prepare_bridge(frame)
        self.assertEqual(self.invocation_bytes(frame),before)
        self.assertEqual(engine().read(self.store,frame['id'])['configuration'],frame['configuration'])
        registry.write_bytes(original);current=self.prepare_bridge(frame)
        self.assertEqual(json.loads(self.invocation_bytes(current)['.skill-tree/local/hook-locations/'+frame['id'].lower()+'.json'])['watch'],frozen)

    def test_writer_time_source_recheck_rejects_a_post_preflight_registry_change_without_node_under_lock(self):
        self.install();frame=self.frame();before=self.invocation_bytes(frame);registry=self.store.base/'installation/plugins.json';original=registry.read_bytes()
        actual_lock=wf.Store.lock;changed=[];actual_node=wf._hook_node
        @contextmanager
        def raced_lock(store):
            with actual_lock(store):
                if store.root==self.store.root and not changed:
                    changed.append(True);registry.write_text(json.dumps(json.loads(original),ensure_ascii=True,separators=(',',':')))
                yield
        def outside_lock(package_root,request):
            self.assertFalse((self.store.base/'.writer-lock').exists(),'The writer guard must recheck bytes without Node subprocesses.')
            return actual_node(package_root,request)
        with patch.object(wf.Store,'lock',raced_lock),patch.object(wf,'_hook_node',outside_lock):
            with self.assertRaisesRegex(ValueError,'changed|watch|configuration|registry|reconcile'):
                self.prepare_bridge(frame)
        self.assertTrue(changed);self.assertEqual(self.invocation_bytes(frame),before)
        registry.write_bytes(original);self.assertTrue(self.prepare_bridge(frame)['prepared_attempt_id'])

    def test_default_node_a_b_a_isolates_other_capability_holds_and_preserves_guarded_b_contribution(self):
        self.install_ordered_capability_fixture();session=self.cl_start();frame=self.accept(self.returned(self.frame(session)))
        self.assertEqual(frame['cursor'],1);prefix=copy.deepcopy(frame['attempts']);prefix_stage=copy.deepcopy(frame['stages'][0])
        first_locator=json.loads(self.invocation_bytes(frame)['.skill-tree/local/hook-locations/'+frame['id'].lower()+'.json'])
        self.capabilities=['codex-source-backed-context']
        plan=wf._hook_node(self.package_root,{'runtime_action':'occurrence-plan','project_root':str(self.root),'event':frame['event'],
            'context':frame['context'],'configuration':frame['configuration'],'capabilities':self.capabilities,
            'adapter':{'provider':'codex','mechanism':'source-backed-context'}})
        editor_holds={item.get('binding_id') for item in plan['prerequisites'] if item.get('code')=='missing-capability'}
        self.assertEqual(editor_holds,{'editor-first','editor-final'})
        try:frame=self.returned(frame,status='findings')
        except ValueError as error:self.fail('Other-occurrence editor holds blocked the default Node B delivery: '+str(error))
        original_b=copy.deepcopy(frame['attempts'][frame['prepared_attempt_id']]);before_context=copy.deepcopy(frame['context'])
        session=self.revise(session);after=wf.actual_hook_context(self.store,before_context)
        receipt={'kind':'core-incorporation','session_id':session['id'],'task_revision_id':session['task_revisions'][-1]['id'],
            'before':engine().digest(before_context),'after':engine().digest(after)}
        actual_node=wf._hook_node
        for kind in ['global','current','unresolved']:
            with self.subTest(hold=kind):
                unchanged=self.invocation_bytes(frame)
                with patch.object(wf,'_hook_node',self.injected_prerequisite(actual_node,kind,original_b['binding_id'])):
                    with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|held'):
                        self.accept(frame,context=after,receipt=receipt)
                self.assertEqual(self.invocation_bytes(frame),unchanged)
        frame=self.accept(frame,context=after,receipt=receipt)
        self.assertEqual(frame['cursor'],2);self.assertEqual(frame['context'],after);self.assertEqual(frame['stages'][0],prefix_stage)
        self.assertTrue(all(frame['attempts'][key]==value for key,value in prefix.items()))
        self.assertEqual(frame['attempts'][original_b['id']]['input'],original_b['input'])
        self.assertEqual(json.loads(self.invocation_bytes(frame)['.skill-tree/local/hook-locations/'+frame['id'].lower()+'.json'])['watch'],first_locator['watch'])
        self.assertEqual(wf.hook_action(self.store,'hook-next',{'chain_id':frame['id'],'capabilities':self.capabilities})['action'],'prerequisite')
        held=self.invocation_bytes(frame)
        with self.assertRaisesRegex(ValueError,'prerequisite|unresolved|admission|capability|held'):
            self.prepare_bridge(frame)
        self.assertEqual(self.invocation_bytes(frame),held)
        self.capabilities=['codex-source-backed-context','editor-only-capability']
        frame=self.returned(frame);final=frame['attempts'][frame['prepared_attempt_id']]
        self.assertEqual(final['binding_id'],'editor-final');self.assertEqual(final['input']['context'],after)
        self.assertIn('incorporated controlled marker',final['input']['context']['body'])
        frame=self.accept(frame);self.assertEqual(frame['state'],'complete');self.assertEqual(frame['stages'][0],prefix_stage)
        self.assertNotEqual(wf.clarification_read(self.store,session['id'])['state'],'complete')


if __name__ == '__main__':
    unittest.main()
