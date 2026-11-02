import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

CORE=Path(__file__).resolve().parents[1]
def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),CORE/'common/scripts'/f'{name}.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
wf=load('workflow-state');validator=load('validate-repository-documentation')

class ManifestValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.store=wf.Store(self.root)
        docs=self.store.base/'documents';docs.mkdir(parents=True)
        for name in validator.REQUIRED:(docs/name).write_text('# Project Contract\n\nThe project has explicit behavior.\n')
        (self.root/'README.md').write_text('Project entrypoint.\n');(self.root/'AGENTS.md').write_text('Agent entrypoint.\n')
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        self.refresh()
        admission=patch.object(wf,'admit_profile',return_value={'identity':'synthetic-manifest-fixture'});admission.start();self.addCleanup(admission.stop)
    def refresh(self):
        with self.store.lock():self.store.save(self.store.text(),self.store.load())
    def mutate_manifest(self,change):
        path=self.store.base/'skill-tree.json';data=json.loads(path.read_text());change(data);path.write_text(wf.dump(data))
    def assert_error(self,message):
        result=validator.validate(self.root);self.assertFalse(result['ok']);self.assertTrue(any(message in error for error in result['errors']),result)
    def test_valid_metadata_and_read_only_validation_preserve_every_file(self):
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertTrue(validator.validate(self.root,True)['ok']);self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_corrupt_manifest_and_checkpoint_are_reported_without_reset(self):
        manifest=self.store.base/'skill-tree.json';manifest.write_text('{broken')
        self.assert_error('Invalid manifest JSON');self.assertEqual(manifest.read_text(),'{broken')
        manifest.unlink();self.refresh();self.store.state.write_text('{broken');self.assert_error('Invalid queue/checkpoint');self.assertEqual(self.store.state.read_text(),'{broken')
    def test_source_hash_and_index_mismatches_are_detected(self):
        state=json.loads(self.store.state.read_text());state['source_hash']='old';state['tasks']=[{'id':'fake'}];self.store.state.write_text(wf.dump(state))
        self.assert_error('source hash is stale');self.assert_error('index differs')
    def test_changed_canonical_source_requires_explicit_manifest_refresh(self):
        path=self.store.base/'documents/technical.md';path.write_text('Changed architecture.\n');self.assert_error('Stale manifest source digest');self.refresh();self.assertTrue(validator.validate(self.root)['ok'])
    def test_invalid_manifest_schema_paths_and_digest_coverage_are_detected(self):
        self.mutate_manifest(lambda data:data.update({'role':'unsupported','files':None}));self.assert_error('Unsupported manifest role')
        (self.store.base/'skill-tree.json').unlink();self.refresh()
        self.mutate_manifest(lambda data:data['policy_references'].append('../outside.md'));self.assert_error('Invalid repository-relative path')
        (self.store.base/'skill-tree.json').unlink();self.refresh()
        self.mutate_manifest(lambda data:data.update({'source_digests':{}}));self.assert_error('do not cover canonical')
    def test_installed_catalog_discovers_local_packages_and_detects_missing_resources(self):
        package=self.root/'.agents/skills/skill-tree-fixture';package.mkdir(parents=True);entrypoint=package/'SKILL.md';entrypoint.write_text('Fixture skill.\n');script=package/'scripts/check.py';script.parent.mkdir();script.write_text('pass\n')
        self.assert_error('skill catalog is stale');self.refresh();self.assertTrue(validator.validate(self.root)['ok'])
        catalog=wf.manifest(self.store)['catalog'];self.assertEqual(catalog[0]['entrypoint'],entrypoint.relative_to(self.root).as_posix());self.assertIn(script.relative_to(self.root).as_posix(),catalog[0]['resources'])
        script.unlink();self.assert_error('Missing manifest file')
    def test_catalog_rejects_resource_outside_installed_package(self):
        package=self.root/'.claude/skills/skill-tree-fixture';package.mkdir(parents=True);(package/'SKILL.md').write_text('Fixture skill.\n');self.refresh()
        self.mutate_manifest(lambda data:data['catalog'][0]['resources'].append('README.md'));self.assert_error('escapes package')
    def test_missing_dependency_and_cycle_are_detected_without_starting_run(self):
        p=wf.intake(self.store,{'title':'Main','description':'Implement scoped behavior.','expected_behavior':'The project preserves state.'})
        check={'id':'behavior','recipe_id':'static-inspection','criteria':['Scoped repository requirement.'],'sources':['README.md'],'parameters':{},'assertion':'Scoped repository requirement.','timing':'immediate'}
        body='Goal:\n- Scoped repository requirement.\n\nTouch:\n- README.md\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Scoped repository requirement.\n'
        receipt=wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Bounded task.'}},'tasks':[{'key':'a','title':'Unit A','body':body,'parent_pending_ids':[p['id']]},{'key':'b','title':'Unit B','body':body,'parent_pending_ids':[p['id']]}]})
        ids=receipt['task_keys'];text=wf.rewrite_meta(self.store.text(),ids['a'],{'depends_on':[wf.identity('T')]});self.store.future.write_text(text);self.refresh();self.assert_error('Missing required dependency')
        text=wf.rewrite_meta(self.store.text(),ids['a'],{'depends_on':[ids['b']]});text=wf.rewrite_meta(text,ids['b'],{'depends_on':[ids['a']]});self.store.future.write_text(text);self.refresh();self.assert_error('Dependency cycle')
        self.assertIsNone(json.loads(self.store.state.read_text())['active_run'])
    def test_active_checkpoint_schema_and_missing_root_are_detected_without_reset(self):
        state=json.loads(self.store.state.read_text());state['active_run']={'id':'invalid'};self.store.state.write_text(wf.dump(state));self.assert_error('Corrupt active checkpoint');self.assertEqual(json.loads(self.store.state.read_text())['active_run'],{'id':'invalid'})
    def test_source_manifest_has_no_target_queue_requirement(self):
        (self.store.base/'skills').mkdir();self.store.state.unlink();self.store.future.unlink()
        (self.store.base/'config').mkdir(exist_ok=True);(self.store.base/'config/repository.json').write_text('{"role":"source","schema":1}')
        (self.store.base/'skill-tree.json').write_text(wf.dump(wf.manifest(self.store)));self.assertTrue(validator.validate_manifest(self.root)['ok'])

    def test_generic_root_destination_is_in_the_target_catalog(self):
        package=self.root/'skill-tree-fixture';package.mkdir();(package/'SKILL.md').write_text('Fixture skill.\n');self.refresh()
        entries=wf.manifest(self.store)['catalog'];self.assertTrue(any(item['entrypoint']=='skill-tree-fixture/SKILL.md' for item in entries));self.assertTrue(validator.validate_manifest(self.root)['ok'])

if __name__=='__main__':unittest.main()
