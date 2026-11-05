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

if __name__=='__main__':unittest.main()
