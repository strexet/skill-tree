import copy
import importlib.util
import unittest
import tempfile
import subprocess
from pathlib import Path

CORE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('agent_conformance',CORE/'scripts/agent-conformance.py')
conformance=importlib.util.module_from_spec(spec);spec.loader.exec_module(conformance)

class AgentConformanceTests(unittest.TestCase):
    def report(self):
        return {'schema':1,'scenarios':[{'scenario_id':case['id'],'agent_id':'fixture-agent','provider':'fixture-provider','model_configuration':'fixture-only','request_sha256':'a'*64,'skill_snapshot_sha256':'b'*64,'checks':{key:True for key in conformance.REQUIRED_CHECKS[case['id']]|{'execution_snapshot_unchanged'}},'passed':True,'reviewed':True,'review_notes':'Fixture assertions validate report admission only.'} for case in conformance.cases()]}
    def test_missing_duplicate_or_failed_scenarios_never_qualify(self):
        report=self.report()
        for change in ['missing','duplicate','failed','unreviewed','identity']:
            value=copy.deepcopy(report)
            if change=='missing':value['scenarios'].pop()
            elif change=='duplicate':value['scenarios'][-1]=value['scenarios'][0]
            elif change=='failed':value['scenarios'][0]['checks']['one_pending']=False
            elif change=='unreviewed':value['scenarios'][0]['reviewed']=False
            else:value['scenarios'][0].pop('agent_id')
            with self.subTest(change=change),self.assertRaises(ValueError):conformance.validate_report(value)
    def test_report_admission_keeps_bounded_agent_and_helper_evidence_separate(self):
        result=conformance.validate_report(self.report())
        self.assertTrue(result['passed']);self.assertEqual(result['scenarios'],8)
        self.assertIn('Bounded',result['scope'])
    def test_unexposed_model_identity_requires_an_explicit_limit(self):
        report=self.report();report['scenarios'][0]['model_configuration']={'selection':'inherited parent','reported_model_id':None}
        with self.assertRaisesRegex(ValueError,'model identity'):conformance.validate_report(report)
        report['limitations']=['The host does not expose the exact inherited model identifier.']
        self.assertTrue(conformance.validate_report(report)['passed'])
    def test_observed_source_mutation_fails_an_unrelated_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';context=conformance.prepare('routing-negative',root)
            self.assertTrue(conformance.grade(context,root,'56')['passed'])
            (root/'counter.py').write_text('Changed source.\n')
            result=conformance.grade(context,root,'56')
            self.assertFalse(result['passed']);self.assertFalse(result['checks']['source_unchanged'])
    def test_prepare_rejects_shared_repository_identity_before_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent=Path(tmp);subprocess.run(['git','init','--quiet',str(parent)],check=True)
            target=parent/'nested'
            with self.assertRaisesRegex(ValueError,'outside an existing Git'):conformance.prepare('routing-negative',target)
            self.assertFalse(target.exists())


class ClarificationConformanceTests(unittest.TestCase):
    """Controlled traces test the grader; controlled traces are never actual-agent qualification."""
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'project'

    def trace(self,case_id='clarification-full-en',combined=False):
        context=conformance.prepare_clarification(case_id,self.root)
        wf=conformance.load_workflow(self.root);store=wf.Store(self.root,allow_unselected=True)
        selected=context['selected_ids'][0]
        session=wf.clarification_start(store,{'task_ids':[selected],'expected_source_hash':wf.file_hash(store.future)})
        def mutate(command,**payload):
            nonlocal session
            current=wf.clarification_read(store,session['id'])
            session=wf.clarification_mutate(store,command,{'session_id':session['id'],'expected_source_hash':wf.file_hash(store.future),
                'expected_session_hash':current['session_hash'],'expected_session_revision':current['revision'],**payload})
        question={'id':'export-format','text':'Which export representation and signed-integer policy apply?',
            'recommendation':'Use a JSON object and retain signed integers.','bindings':{selected:['scope']}}
        mutate('clarify-round',questions=[question])
        def observed(phase,agent='fixture-actor-one'):
            return {**conformance.observe_clarification(context,self.root,phase,'Controlled fixture interaction, not an actual-agent observation.'),'agent_id':agent}
        events=[observed('question')]
        if case_id=='clarification-resume-en':
            events.append(conformance.interrupt_clarification(context,self.root))
            mutate('clarify-resume');events.append(observed('resumed','fixture-actor-two'))
        owner=context['fixture_owner']['answer'];events.append(owner)
        def answer():
            mutate('clarify-answer',round_id=session['rounds'][-1]['id'],question_id='export-format',question_revision=session['questions']['export-format']['revision'],
                answer=owner['text'],evidence={'kind':'owner-message','reference':owner['reference']})
        answer()
        body=conformance._clarification_body().replace('Choose the export representation and treatment of negative integers.','Use a JSON object with a value integer field and preserve negative integers.')
        mutate('clarify-revise',tasks=[{'task_id':selected,'body':body}])
        # The changed field reopens the mapped question; the fixture explicitly supplies the answer again.
        mutate('clarify-round')
        actor='fixture-actor-two' if case_id=='clarification-resume-en' else 'fixture-actor-one'
        if combined:
            summary=observed('reopened-question',actor)
            summary.update(roles=['revision-summary'],role_review={'reviewed':True,'reviewer':'fixture-independent-reviewer',
                'notes':'The fixture turn displays the complete current task summary and requests confirmation of the summary and decisions.'})
            events.append(summary)
            owner={'phase':'owner-answer','reference':'fixture-owner:combined','text':'Retain the JSON value field and signed integers, and confirm the exact current task summary with implementation excluded.',
                'roles':['owner-confirmation'],'role_review':{'reviewed':True,'reviewer':'fixture-independent-reviewer',
                'notes':'The supplied fixture input both answers the reopened question and confirms the exact displayed current summary.'}}
        events.append(copy.deepcopy(owner));answer()
        clarity={key:True for key in ['goals','scope','exclusions','dependencies','acceptance','validation','decisions']}
        mutate('clarify-round',clarity={**clarity,'evidence':['Controlled fixture task/source review for grader tests only.']})
        if combined:confirmation=owner
        else:
            events.append(observed('revision',actor));confirmation=context['fixture_owner']['confirmation'];events.append(confirmation)
        mutate('clarify-confirm',task_ids=[selected],semantic_fingerprints=session['semantic_fingerprints'],evidence={'kind':'owner-message','reference':confirmation['reference']})
        events.append(observed('complete',actor))
        return context,{'events':events}

    def test_artifact_grader_rejects_missing_observations_and_wrong_scope(self):
        context,observations=self.trace()
        self.assertTrue(conformance.grade_clarification(context,self.root,observations)['passed'])
        missing=copy.deepcopy(observations);missing['events']=[event for event in missing['events'] if event['phase']!='question']
        result=conformance.grade_clarification(context,self.root,missing)
        self.assertFalse(result['passed']);self.assertFalse(result['checks']['question_before_answer'])
        session_path=next((self.root/'.skill-tree/clarifications').glob('*.json'))
        import json
        session=json.loads(session_path.read_text());session['task_ids']=[next(key for key in context['task_baselines'] if key not in context['selected_ids'])]
        session_path.write_text(json.dumps(session))
        self.assertFalse(conformance.grade_clarification(context,self.root,observations)['checks']['exact_scope'])

    def test_source_mutation_and_missing_owner_confirmation_fail(self):
        context,observations=self.trace()
        missing=copy.deepcopy(observations);missing['events']=[event for event in missing['events'] if event['phase']!='owner-confirmation']
        self.assertFalse(conformance.grade_clarification(context,self.root,missing)['checks']['current_confirmation'])
        (self.root/'counter.py').write_text('def increment(value):\n    return value + 1\n')
        result=conformance.grade_clarification(context,self.root,observations)
        self.assertFalse(result['passed']);self.assertFalse(result['checks']['source_unchanged'])

    def test_resume_requires_another_actor_and_preserves_parked_state(self):
        context,observations=self.trace('clarification-resume-en')
        result=conformance.grade_clarification(context,self.root,observations)
        self.assertTrue(result['passed'],result['checks'])
        repeated=copy.deepcopy(observations)
        resumed=next(event for event in repeated['events'] if event['phase']=='resumed')
        resumed['agent_id']=next(event['agent_id'] for event in repeated['events'] if event['phase']=='question')
        self.assertFalse(conformance.grade_clarification(context,self.root,repeated)['checks']['same_session_resumed'])

    def test_reviewed_current_summary_accepts_one_actual_answer_and_confirmation(self):
        context,observations=self.trace('clarification-resume-en',combined=True)
        result=conformance.grade_clarification(context,self.root,observations)
        self.assertTrue(result['passed'],result['checks'])
        self.assertNotIn('revision',[event['phase'] for event in observations['events']])
        self.assertNotIn('owner-confirmation',[event['phase'] for event in observations['events']])
        # Summary/consent roles qualify existing turns; no extra turn is synthesized.
        self.assertEqual(sum('owner-confirmation' in event.get('roles',[]) for event in observations['events']),1)

    def test_combined_consent_rejects_stale_summary_answer_only_and_unreviewed_roles(self):
        context,observations=self.trace(combined=True)
        for change in ['stale-summary','intervening-semantic-change','answer-only','unreviewed','absent-consent','consent-before-summary']:
            value=copy.deepcopy(observations)
            summary=next(event for event in value['events'] if 'revision-summary' in event.get('roles',[]))
            owner=next(event for event in value['events'] if 'owner-confirmation' in event.get('roles',[]))
            if change=='stale-summary':summary['sessions'][0]['semantic_fingerprints'][context['selected_ids'][0]]='stale'
            elif change=='intervening-semantic-change':
                intermediate=copy.deepcopy(summary);intermediate['phase']='intermediate-observation';intermediate.pop('roles')
                intermediate['sessions'][0]['semantic_fingerprints'][context['selected_ids'][0]]='changed-before-returning-to-final'
                value['events'].insert(value['events'].index(owner),intermediate)
            elif change=='answer-only':owner.pop('roles')
            elif change=='unreviewed':owner['role_review']['reviewed']=False
            elif change=='absent-consent':value['events'].remove(owner)
            else:
                value['events'].remove(owner);value['events'].insert(value['events'].index(summary),owner)
            with self.subTest(change=change):
                self.assertFalse(conformance.grade_clarification(context,self.root,value)['checks']['current_confirmation'])

    def test_report_requires_captured_turns_and_independent_semantic_review(self):
        rows=[]
        for case in conformance.clarification_cases():
            checks=conformance.CLARIFICATION_CHECKS|({'same_session_resumed','higher_unrelated_deferred'} if case['resume'] else set())
            rows.append({'scenario_id':case['id'],'checks':{key:True for key in checks},'passed':True,'provider':'fixture-only',
                'model_configuration':{'selection':'fixture-only','reported_model_id':None},'session_id':'CL-fixture','session_sha256':'a'*64,
                'request_sha256':'b'*64,'skill_snapshot_sha256':'c'*64,'reviewed':True,'review_notes':'Controlled report-admission test.',
                'semantic_revision_review':'Controlled fixture review.'})
        report={'schema':1,'kind':'clarification-agent-conformance','scenarios':rows,'limitations':['Fixture-only, not actual-agent evidence.']}
        with self.assertRaisesRegex(ValueError,'captured fixture artifacts'):conformance.validate_clarification_report(report)
        rows[0].pop('semantic_revision_review')
        with self.assertRaisesRegex(ValueError,'semantic revision'):conformance.validate_clarification_report(report)

if __name__=='__main__':unittest.main()
