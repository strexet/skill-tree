"""Synthetic evidence exercises state guards; no test input proves an actual actor or human."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]


def module(name,file):
    spec=importlib.util.spec_from_file_location(name,file)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


governance=module('unit_decision_governance',CORE/'common/scripts/decision-governance.py')
wf=module('unit_decision_store',CORE/'common/scripts/workflow-state.py')
hash_text=lambda value:hashlib.sha256(value.encode()).hexdigest()


class QueueFreeStore(wf.Store):
    def text(self):raise AssertionError('Decision metadata cannot read or create a queue')
    def load(self,*args,**kwargs):raise AssertionError('Decision metadata cannot select an implementation run')
    def save(self,*args,**kwargs):raise AssertionError('Decision metadata cannot save workflow state')


class DecisionGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=QueueFreeStore(self.root,allow_unselected=True,neutral=True)

    def context(self,**extra):
        return {'kind':'request','id':'unit-request','operation':'unit-operation','semantic_fingerprint':hash_text('semantic one'),'content_fingerprint':hash_text('content one'),**extra}

    def authority(self,**extra):
        return {'id':'unit-owner-grant','revision':1,'context_id':'unit-request','allowed_kinds':['product','technical','specification-acceptance'],'constraints':['Unit source/specification decisions only; no execution, installation or publication.'],'evidence':{'kind':'owner-message','reference':'unit-only synthetic grant, never actual human evidence'},**extra}

    def question(self,**extra):
        return {'id':'format','kind':'technical','text':'Which representation fits the selected fixture?','options':[{'id':'json','text':'JSON data'},{'id':'text','text':'Plain text'}],'recommendation':'json','significance':'routine',**extra}

    def start(self,**extra):
        return governance.start(self.store,{'request_id':'unit-start','context':self.context(),'question':self.question(),'authority':self.authority(),'executor':{'id':'unit-executor','context_id':'executor-context'},**extra})

    def change(self,record,command,**extra):
        return governance.mutate(self.store,'decision-'+command,{'decision_id':record['id'],'expected_decision_hash':record['decision_hash'],'expected_decision_revision':record['revision'],'expected_mode_epoch':record['mode_epoch'],'expected_context_fingerprint':record.get('context',self.context())['content_fingerprint'],**extra})

    def actor(self,role='resolver',number=1):
        return {'id':'unit-'+role+'-'+str(number),'context_id':role+'-context-'+str(number)}

    def prepare(self,record,role=None,actor=None):
        role=role or ('owner' if record['mode']=='manual' else 'resolver')
        return self.change(record,'prepare',role=role,actor=actor or self.actor(role))

    def answer(self,record,role=None,status='answered',answer='json',actor=None):
        role=role or ('owner' if record['mode']=='manual' else 'resolver');actor=actor or self.actor(role)
        return self.change(record,'record',attempt_id=record['prepared_attempt_id'],result={'status':status,'answer':answer,'rationale':'Synthetic unit rationale.'},evidence={'kind':'submitted-answer' if role=='owner' else 'delegated-agent','reference':'unit-only controlled '+role+' input','actor_id':actor['id'],'actor_context_id':actor['context_id']})

    def complete(self,**extra):
        record=self.start(**extra);record=self.prepare(record);record=self.answer(record);return self.change(record,'accept')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def test_api_smoke(self):
        for name in ['start','read','mutate','acceptance_reference','validate_context','validate_authority']:
            self.assertTrue(callable(getattr(governance,name)))

    def test_task_free_bootstrap_persists_only_decision_metadata_and_defaults_manual(self):
        record=self.start();self.assertEqual(record['mode'],'manual');self.assertEqual(record['state'],'open');self.assertEqual(record['mode_epoch'],1)
        self.assertTrue((self.root/'.skill-tree/decisions'/f"{record['id'].lower()}.json").is_file())
        self.assertFalse((self.root/'.skill-tree/documents').exists());self.assertEqual(record,governance.read(self.store,record['id']))

    def test_start_nonce_replays_matching_request_and_rejects_conflicting_reuse(self):
        record=self.start();before=self.snapshot();self.assertEqual(self.start(),record);self.assertEqual(before,self.snapshot())
        with self.assertRaises(governance.DecisionError):self.start(question=self.question(text='A changed decision.'))
        self.assertEqual(before,self.snapshot())

    def test_manual_answer_acceptance_preserves_owner_provenance(self):
        record=self.complete();self.assertEqual(record['state'],'accepted');self.assertEqual(record['acceptance']['origin']['kind'],'submitted-answer');self.assertEqual(record['acceptance']['mode'],'manual')
        self.assertEqual(record['acceptance']['mode_epoch'],1);self.assertEqual(record['acceptance']['authority_digest'],record['authority_digest'])

    def test_auto_resolver_acceptance_retains_delegated_origin(self):
        record=self.complete(mode='auto');self.assertEqual(record['state'],'accepted');self.assertEqual(record['acceptance']['origin']['kind'],'delegated-agent');self.assertEqual(record['acceptance']['mode'],'auto')

    def test_manual_rejects_delegated_and_recommendation_as_owner_answers(self):
        record=self.prepare(self.start());before=self.snapshot()
        for kind in ['delegated-agent','recommendation','fixture-owner']:
            with self.subTest(kind=kind),self.assertRaises(governance.DecisionError):
                self.change(record,'record',attempt_id=record['active_attempt_id'],result={'status':'answered','answer':'json','rationale':'No actual owner input.'},evidence={'kind':kind,'reference':'unit counterfeit','actor_id':'unit-owner-1','actor_context_id':'owner-context-1'})
        self.assertEqual(before,self.snapshot())

    def test_auto_rejects_executor_self_resolution_and_renamed_same_context(self):
        record=self.start(mode='auto');before=self.snapshot()
        for actor in [{'id':'unit-executor','context_id':'different-context'},{'id':'renamed-agent','context_id':'executor-context'}]:
            with self.subTest(actor=actor),self.assertRaises(governance.DecisionError):self.prepare(record,actor=actor)
        self.assertEqual(before,self.snapshot())

    def test_significant_decision_requires_independent_current_critic(self):
        record=self.answer(self.prepare(self.start(mode='auto',question=self.question(significance='significant'))));before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'accept')
        with self.assertRaises(governance.DecisionError):self.prepare(record,'critic',actor={'id':'renamed-critic','context_id':'resolver-context-1'})
        self.assertEqual(before,self.snapshot());record=self.prepare(record,'critic');record=self.answer(record,'critic',status='agree');record=self.change(record,'accept');self.assertEqual(record['state'],'accepted')

    def test_substantive_disagreement_requires_further_independent_arbiter(self):
        record=self.answer(self.prepare(self.start(mode='auto',question=self.question(significance='significant'))));record=self.prepare(record,'critic');record=self.answer(record,'critic',status='disagree');before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'accept')
        with self.assertRaises(governance.DecisionError):self.prepare(record,'arbiter',actor=self.actor('critic'))
        self.assertEqual(before,self.snapshot());record=self.prepare(record,'arbiter');record=self.answer(record,'arbiter',answer='text');record=self.change(record,'accept');self.assertEqual(record['acceptance']['answer'],'text')

    def test_pending_original_attempt_requires_reconciliation_before_mode_switch(self):
        record=self.prepare(self.start(mode='auto'));before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'switch',mode='manual')
        self.assertEqual(before,self.snapshot());attempt=record['active_attempt_id'];record=self.change(record,'reconcile',attempt_id=attempt,status='cancelled',evidence={'kind':'actor-reconciliation','reference':'unit-only explicit original actor cancellation'})
        record=self.change(record,'switch',mode='manual');self.assertEqual(record['mode_epoch'],2);self.assertEqual(record['attempts'][attempt]['status'],'cancelled');self.assertIsNone(record['acceptance'])

    def test_settled_disagreement_cannot_be_erased_by_a_friendly_replacement(self):
        record=self.answer(self.prepare(self.start(mode='auto',question=self.question(significance='significant'))));resolver=record['attempts'][record['prepared_attempt_id']]
        record=self.prepare(record,'critic');critic=record['attempts'][record['prepared_attempt_id']]
        self.assertIsNotNone(critic['basis_digest']);self.assertNotEqual(critic['basis_digest'],resolver['basis_digest'])
        record=self.answer(record,'critic',status='disagree');before=self.snapshot()
        for role in ['resolver','critic']:
            with self.subTest(role=role),self.assertRaises(governance.DecisionError):self.prepare(record,role,actor=self.actor(role,2))
        with self.assertRaises(governance.DecisionError):self.change(record,'accept')
        self.assertEqual(before,self.snapshot());record=self.prepare(record,'arbiter');arbiter=record['attempts'][record['prepared_attempt_id']]
        self.assertNotEqual(arbiter['basis_digest'],critic['basis_digest']);record=self.answer(record,'arbiter',answer='text');record=self.change(record,'accept')
        self.assertEqual(record['acceptance']['attempt_id'],arbiter['id']);self.assertEqual(set(record['acceptance']['role_receipts']),{'resolver','critic','arbiter'})

    def test_semantic_round_trip_never_revives_prior_role_or_acceptance(self):
        record=self.complete(mode='auto');original=copy.deepcopy(record['acceptance']);old_attempt=original['attempt_id']
        record=self.change(record,'resume',context=self.context(semantic_fingerprint=hash_text('different meaning')))
        record=self.change(record,'resume',context=self.context());before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'accept')
        with self.assertRaises(governance.DecisionError):self.change(record,'record',attempt_id=old_attempt,result=record['attempts'][old_attempt]['result'],evidence=record['attempts'][old_attempt]['evidence'])
        self.assertEqual(before,self.snapshot());record=self.answer(self.prepare(record));record=self.change(record,'accept')
        self.assertNotEqual(record['acceptance']['attempt_id'],old_attempt);self.assertNotEqual(record['acceptance']['digest'],original['digest'])

    def test_explicit_optional_critic_failure_requires_an_actual_retry(self):
        record=self.answer(self.prepare(self.start(mode='auto')));record=self.prepare(record,'critic');record=self.answer(record,'critic',status='unavailable');before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'accept')
        self.assertEqual(before,self.snapshot());actor=self.actor('critic',2);record=self.prepare(record,'critic',actor=actor);record=self.answer(record,'critic',status='agree',actor=actor);record=self.change(record,'accept')
        self.assertEqual(record['state'],'accepted');self.assertEqual(set(record['acceptance']['role_receipts']),{'resolver','critic'})

    def test_critic_agreement_cannot_approve_a_different_declared_answer(self):
        record=self.answer(self.prepare(self.start(mode='auto',question=self.question(significance='significant'))));record=self.prepare(record,'critic');before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.answer(record,'critic',status='agree',answer='text')
        self.assertEqual(before,self.snapshot());actor=self.actor('critic')
        record=self.change(record,'record',attempt_id=record['prepared_attempt_id'],result={'status':'agree','rationale':'Synthetic critic agrees with the frozen candidate.'},evidence={'kind':'delegated-agent','reference':'unit-only controlled critic input','actor_id':actor['id'],'actor_context_id':actor['context_id']})
        record=self.change(record,'accept');self.assertEqual(record['acceptance']['answer'],'json')

    def test_typed_context_matrix_preserves_real_scope_and_bounded_paths(self):
        tid='T-11111111-1111-4111-8111-111111111111';pid='P-22222222-2222-4222-8222-222222222222';rid='WR-33333333-3333-4333-8333-333333333333'
        valid=[{}, {'kind':'pending','pending_ids':[pid]}, {'kind':'task','task_ids':[tid]}, {'kind':'task-group','task_ids':[tid],'pending_ids':[pid]}, {'kind':'controller','run_id':rid}, {'kind':'review','head':'a'*40,'base_oid':'b'*64,'purpose':'finding-resolution'}, {'kind':'document','paths':['docs/spec.md']}, {'kind':'snapshot','paths':['source.py','docs/spec.md']}]
        for changes in valid:
            with self.subTest(valid=changes):self.assertEqual(governance.validate_context(self.context(**changes)),self.context(**changes))
        invalid=[{'task_ids':[tid]}, {'kind':'pending','pending_ids':['P-short']}, {'kind':'pending','pending_ids':[pid],'task_ids':[tid]}, {'kind':'task','task_ids':[tid,tid]}, {'kind':'task-group','task_ids':['T-invalid']}, {'kind':'controller'}, {'kind':'controller','run_id':'WR-invalid'}, {'kind':'review','head':'a'*41,'base_oid':'b'*40}, {'kind':'review','head':'a'*40,'base_oid':'b'*40,'purpose':'outside scope'}, {'kind':'document','paths':[]}, {'kind':'snapshot','paths':['../source.py']}, {'kind':'document','paths':['C:\\source.py']}, {'kind':'document','paths':['source\0.py']}, {'session_id':'CL-fixture','purpose':'finding-resolution'}]
        before=self.snapshot()
        for changes in invalid:
            with self.subTest(invalid=changes),self.assertRaises(governance.DecisionError):governance.validate_context(self.context(**changes))
        self.assertEqual(before,self.snapshot())

    def test_auto_manual_auto_epoch_cycle_rejects_original_late_result(self):
        record=self.prepare(self.start(mode='auto'));attempt=record['active_attempt_id'];record=self.change(record,'reconcile',attempt_id=attempt,status='cancelled',evidence={'kind':'actor-reconciliation','reference':'unit-only cancellation'});record=self.change(record,'switch',mode='manual');record=self.change(record,'switch',mode='auto');before=self.snapshot()
        with self.assertRaises(governance.DecisionError):self.change(record,'record',attempt_id=attempt,result={'status':'answered','answer':'json','rationale':'Late original response.'},evidence={'kind':'delegated-agent','reference':'unit late actor','actor_id':'unit-resolver-1','actor_context_id':'resolver-context-1'})
        self.assertEqual(record['mode_epoch'],3);self.assertEqual(before,self.snapshot())

    def test_exact_answer_replay_recovers_without_progress_but_conflict_rejects(self):
        record=self.prepare(self.start(mode='auto'));record=self.answer(record);before=self.snapshot();self.assertEqual(self.answer(record),record);self.assertEqual(before,self.snapshot())
        with self.assertRaises(governance.DecisionError):self.answer(record,answer='text')
        self.assertEqual(before,self.snapshot())

    def test_stale_record_epoch_revision_and_context_guards_reject_atomically(self):
        record=self.start(mode='auto');before=self.snapshot()
        base={'decision_id':record['id'],'expected_decision_hash':record['decision_hash'],'expected_decision_revision':record['revision'],'expected_mode_epoch':record['mode_epoch'],'expected_context_fingerprint':self.context()['content_fingerprint'],'role':'resolver','actor':self.actor()}
        for change in [{'expected_decision_hash':'0'*64},{'expected_decision_revision':0},{'expected_mode_epoch':2},{'expected_context_fingerprint':'1'*64}]:
            with self.subTest(change=change),self.assertRaises(governance.DecisionError):governance.mutate(self.store,'decision-prepare',{**base,**change})
        self.assertEqual(before,self.snapshot())

    def test_content_only_resume_preserves_acceptance_but_semantic_change_reopens(self):
        record=self.complete(mode='auto');accepted=copy.deepcopy(record['acceptance']);record=self.change(record,'resume',context=self.context(content_fingerprint=hash_text('formatting two')));self.assertEqual(record['acceptance'],accepted)
        record=self.change(record,'resume',context=self.context(content_fingerprint=hash_text('semantic content two'),semantic_fingerprint=hash_text('semantic two')));self.assertEqual(record['state'],'open');self.assertIsNone(record['acceptance']);self.assertTrue(record['history'])

    def test_revised_authority_revokes_current_acceptance_without_erasing_history(self):
        record=self.complete(mode='auto');accepted=copy.deepcopy(record['acceptance']);record=self.change(record,'switch',mode='auto',authority=self.authority(revision=2,allowed_kinds=['product']));self.assertIsNone(record['acceptance']);self.assertNotEqual(record['authority_digest'],accepted['authority_digest']);self.assertTrue(record['history'])
        with self.assertRaises(governance.DecisionError):self.prepare(record)

    def test_reserved_actions_and_wildcard_grants_never_gain_delegated_authority(self):
        before=self.snapshot()
        for kind in ['installation-consent','publication','merge','check-result','external-approval']:
            with self.subTest(kind=kind),self.assertRaises(governance.DecisionError):self.start(mode='auto',question=self.question(kind=kind),authority=self.authority(allowed_kinds=['*',kind]))
        self.assertEqual(before,self.snapshot())

    def test_out_of_grant_question_keeps_unresolved_record(self):
        record=self.start(mode='auto',authority=self.authority(allowed_kinds=['product']));self.assertEqual(record['state'],'blocked');self.assertIsNone(record['acceptance'])
        with self.assertRaises(governance.DecisionError):self.prepare(record)

    def test_acceptance_reference_binds_kind_mode_authority_and_exact_semantics(self):
        record=self.complete(mode='auto');reference={'decision_id':record['id'],'acceptance_digest':record['acceptance']['digest']};expected={'context':self.context(),'mode':'auto','mode_epoch':record['mode_epoch'],'authority_digest':record['authority_digest'],'kind':'technical'}
        receipt=governance.acceptance_reference(self.store,reference,expected);self.assertEqual(receipt['origin']['kind'],'delegated-agent')
        for change in [{'kind':'specification-acceptance'},{'mode':'manual'},{'authority_digest':'0'*64},{'mode_epoch':2},{'context':self.context(semantic_fingerprint='0'*64)}]:
            with self.subTest(change=change),self.assertRaises(governance.DecisionError):governance.acceptance_reference(self.store,reference,{**expected,**change})

    def test_writer_install_barriers_preserve_existing_queue_and_checkpoint_bytes(self):
        self.store.base.mkdir(exist_ok=True);docs=self.store.base/'documents';docs.mkdir();(docs/'future.md').write_text('Unrelated preserved queue bytes.');(docs/'future.json').write_text('{"unrelated":"parked workflow"}\n');before=self.snapshot()
        (self.store.base/'.writer-lock').write_text('unit owner')
        with self.assertRaises(Exception):self.start()
        (self.store.base/'.writer-lock').unlink();installation=self.store.base/'installation';installation.mkdir();(installation/'.install-lock').write_text('unit installation')
        with self.assertRaises(Exception):self.start()
        (installation/'.install-lock').unlink();record=self.start();record=self.prepare(record);record=self.answer(record);record=self.change(record,'accept');after=self.snapshot()
        self.assertEqual(before,{key:value for key,value in after.items() if not key.startswith('.skill-tree/decisions/')});self.assertEqual(record['state'],'accepted')

    def test_read_is_nonmutating_and_frozen_defaults_do_not_change_parked_manual_decision(self):
        record=self.start();before=self.snapshot();self.assertEqual(governance.read(self.store,record['id']),record);self.assertEqual(before,self.snapshot());self.assertEqual(record['mode'],'manual')
        context=self.context(id='different-request');authority=self.authority(context_id='different-request');other=self.start(request_id='other',context=context,authority=authority,mode='auto');self.assertEqual(other['mode'],'auto');self.assertEqual(governance.read(self.store,record['id'])['mode'],'manual')


if __name__=='__main__':unittest.main()
