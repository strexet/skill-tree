import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('selected_snapshot_workflow',ROOT/'common/scripts/workflow-state.py')
wf=importlib.util.module_from_spec(spec);spec.loader.exec_module(wf)

class SelectedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=wf.Store(self.root)
        self.store.future.parent.mkdir(parents=True)
        self.store.future.write_text('# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n')
        config=self.store.base/'config';config.mkdir();(config/'repository.json').write_text(json.dumps({'schema':1,'role':'source'}))
    def task(self,title,priority=100,depends_on=()):
        p=wf.intake(self.store,{'title':title,'description':'Implement selected behavior.','expected_behavior':'Preserve bounded scope.','priority':priority})
        check={'id':'scope','recipe_id':'static-inspection','criteria':['Preserve bounded scope.'],'sources':['.skill-tree/config/repository.json'],'parameters':{},'assertion':'Preserve bounded scope.','timing':'immediate'}
        body='Goal:\n- Preserve bounded scope.\n\nTouch:\n- Source declarations.\n\nValidation:\n```json\n'+json.dumps({'checks':[check]})+'\n```\n\nAcceptance:\n- Preserve bounded scope.\n'
        return wf.process(self.store,{'selectors':[p['id']],'dispositions':{p['id']:{'status':'promoted','reason':'Focused admission fixture.'}},'tasks':[{'title':title,'body':body,'parent_pending_ids':[p['id']],'depends_on':list(depends_on)}]})['created_ids'][0]
    def test_exact_snapshot_preserves_priority_and_dependency_closure(self):
        outside=self.task('Unrelated highest root',500);dep=self.task('Required prerequisite',200)
        low=self.task('Selected lower root',100,[dep]);high=self.task('Selected higher root',300)
        run=wf.start(self.store,'all',workspace={'snapshot_ids':[low,high]})
        self.assertEqual(run['snapshot'],[high,low]);self.assertEqual(run['root_task_id'],high)
        self.assertEqual(set(run['admitted_task_ids']),{low,high,dep});self.assertNotIn(outside,run['required_ids'])
        self.assertEqual(wf.next_task(self.store)['task_id'],high)
    def test_invalid_selection_is_atomic(self):
        chosen=self.task('Selected root');p=wf.intake(self.store,{'title':'Pending root','description':'Pending behavior.','expected_behavior':'Research before admission.'})
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for ids in [[],[chosen,chosen],['missing'],[wf.identity('T')],[p['id']],chosen,None,{},[{}],[chosen,False]]:
            with self.subTest(ids=ids),self.assertRaises(wf.WorkflowError):
                wf.start(self.store,'all',workspace={'snapshot_ids':ids})
            self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_id_shaped_title_never_substitutes_for_an_absent_id(self):
        absent=wf.identity('T');self.task(absent)
        before=self.store.state.read_bytes()
        with self.assertRaisesRegex(wf.WorkflowError,'exact prioritized tasks'):
            wf.start(self.store,'all',workspace={'snapshot_ids':[absent]})
        self.assertEqual(before,self.store.state.read_bytes())
    def test_ties_follow_document_order_instead_of_input_order(self):
        first=self.task('First inserted');second=self.task('Second inserted')
        order=[t['id'] for t in wf.parse(self.store.text()) if t['queue']=='Prioritized Next Changes']
        run=wf.start(self.store,'all',workspace={'snapshot_ids':list(reversed(order))})
        self.assertEqual(set(order),{first,second});self.assertEqual(run['snapshot'],order)
    def block(self,task_id):
        text=self.store.text();task=wf.resolve(wf.parse(text),[task_id])[0]
        meta={k:task[k] for k in wf.FIELDS};meta['status']='Blocked pending answers'
        body=task['body'].split('```',2)[2]+'\nQuestions:\n- [Unresolved - blocks implementation] Confirm the fixture decision.\n'
        self.store.future.write_text(wf.insert(wf.remove(text,[task_id]),'Prioritized Next Changes',wf.render(task['title'],meta,body)))
        with self.store.lock():self.store.save(self.store.text(),self.store.load())
    def test_blocked_member_rejects_entire_group_before_writes(self):
        ready=self.task('Ready root',200);blocked=self.task('Blocked lower root',100);self.block(blocked)
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(wf.WorkflowError,'blocking unresolved questions'):
            wf.start(self.store,'all',workspace={'snapshot_ids':[ready,blocked]})
        self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_unselected_blocked_root_does_not_block_group(self):
        outside=self.task('Blocked highest root',500);self.block(outside);chosen=self.task('Selected ready root',100)
        self.assertEqual(wf.start(self.store,'all',workspace={'snapshot_ids':[chosen]})['snapshot'],[chosen])
    def test_next_rejects_snapshot_and_full_queue_remains_default(self):
        a=self.task('First root');b=self.task('Second root')
        with self.assertRaises(wf.WorkflowError):wf.start(self.store,'next',a,workspace={'snapshot_ids':[b]})
        with self.assertRaises(wf.WorkflowError):wf.start(self.store,'all',a,workspace={'snapshot_ids':[b]})
        self.assertEqual(set(wf.start(self.store,'all')['snapshot']),{a,b})

if __name__=='__main__':unittest.main()
