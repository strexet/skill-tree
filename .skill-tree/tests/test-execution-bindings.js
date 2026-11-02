const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const b=require('../lib/execution-bindings.js'),c=require('../lib/composer.js');
const source=path.resolve(__dirname,'..');
function fixture(t,editor='6000.0.83f1'){
 const base=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'binding-')));t.after(()=>fs.rmSync(base,{recursive:true,force:true}));
 const queue=path.join(base,'queue'),workspace=path.join(base,'workspace'),execution=path.join(workspace,'scratch/pilot');
 const write=(root,rel,value)=>{const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof value==='string'?value:JSON.stringify(value));};
 for(const root of [queue,execution]){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: '+editor);write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'},'com.unity.pipeline':{version:'0.7.0-exp.1'}}});write(root,'Assets/main.cs','same');}
 write(execution,'Assets/fixture.cs','isolated fixture');write(workspace,'scripts/runner.py','raise RuntimeError("Must never execute during composition")');
 const spec={locator:'.skill-tree/local/pilot.json',execution_subdir:'scratch/pilot',source_paths:['Assets','Packages','ProjectSettings'],workspace_paths:['scripts/runner.py'],review_path:'.skill-tree/validation/pilot-review.json',pins:{editor_version:editor,cli_version:'1.0.0-beta.10',pipeline_version:'0.7.0-exp.1',utf_version:'1.6.0'}};
 write(queue,spec.locator,{schema:1,queue_root:queue,workspace_root:workspace});
 const q=b.snapshot(queue,spec.source_paths),e=b.snapshot(execution,spec.source_paths),w=b.snapshot(workspace,spec.workspace_paths);
 const review={schema:1,queue_digest:q.digest,execution_digest:e.digest,workspace_digest:w.digest,differences:[{path:'Assets/fixture.cs',queue:null,execution:e.files['Assets/fixture.cs'],classification:'fixture',reason:'Offline fixture source only.'}]};write(queue,spec.review_path,review);
 const document={schema:1,execution_bindings:{pilot:spec},recipes:{isolated:{lane:'unity-playmode',editor_version:editor,execution_binding:'pilot',argv:['python3','{binding_workspace}/scripts/runner.py','--project','{project_root}']}}};write(queue,'.skill-tree/validation-recipes.json',document);
 return {queue,workspace,execution,spec,document,review,write};
}
test('binding composes exact roots, complete source identity and pinned 6.3 without executing a runner',t=>{
 const f=fixture(t,'6000.3.27f2'),p=c.resolveProfile(source,f.queue,'unity');assert.equal(p.execution_bindings.pilot.execution_root,f.execution);assert.equal(p.recipes.isolated.editor_version,'6000.3.27f2');assert.deepEqual(p.execution_bindings.pilot.blockers,[]);assert.ok(c.compose(source,p).packages['skill-tree-work-through-next']);
});
test('binding refuses changed queue, isolated fixture or workspace runner before profile activation',t=>{
 for(const rootName of ['queue','execution','workspace']){const f=fixture(t);f.write(f[rootName],rootName==='workspace'?'scripts/runner.py':'Assets/new.cs','changed');assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/review is stale/);}
});
test('binding refuses arbitrary roots, symlinks, overlap and missing source classification',t=>{
 const f=fixture(t);f.write(f.queue,f.spec.locator,{schema:1,queue_root:f.execution,workspace_root:f.workspace});assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/Foreign/);
 f.write(f.queue,f.spec.locator,{schema:1,queue_root:f.queue,workspace_root:f.workspace});f.document.execution_bindings.pilot.execution_subdir='../queue';f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/relative/);
 f.spec.execution_subdir='scratch/pilot';f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);f.review.differences=[];f.write(f.queue,f.spec.review_path,f.review);assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/classify/);
 fs.symlinkSync(path.join(f.execution,'Assets/main.cs'),path.join(f.execution,'Assets/link.cs'));assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/symlink/i);
});
test('binding refuses mismatched pins and non-product relabeling while retaining honest source blockers',t=>{
 const f=fixture(t);f.spec.pins.cli_version='';f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/pins/);
 f.spec.pins.cli_version='1.0.0-beta.10';f.spec.pins.editor_version='6000.3.27f2';f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/pin mismatch/);
 f.spec.pins.editor_version='6000.0.83f1';f.document.recipes.isolated.lane='static';f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/Unity execution binding/);
 f.document.recipes.isolated.lane='unity-playmode';f.review.differences[0].classification='unqualified';f.write(f.queue,f.spec.review_path,f.review);f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);assert.deepEqual(c.resolveProfile(source,f.queue,'unity').execution_bindings.pilot.blockers,['Assets/fixture.cs']);
});

test('embedded Pipeline uses reviewed package identity and version, never the file locator as a version',t=>{
 const f=fixture(t,'6000.3.27f2');
 f.write(f.execution,'Packages/com.unity.pipeline/package.json',{name:'com.unity.pipeline',version:'0.9.1-exp.1'});
 f.write(f.execution,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0'},'com.unity.pipeline':{version:'file:com.unity.pipeline',source:'embedded'}}});
 const q=b.snapshot(f.queue,f.spec.source_paths),e=b.snapshot(f.execution,f.spec.source_paths);
 f.review.queue_digest=q.digest;f.review.execution_digest=e.digest;
 f.review.differences=[...new Set([...Object.keys(q.files),...Object.keys(e.files)])].filter(n=>q.files[n]!==e.files[n]).map(n=>({path:n,queue:q.files[n]||null,execution:e.files[n]||null,classification:'fixture',reason:'Reviewed test fixture.'}));
 f.write(f.queue,f.spec.review_path,f.review);f.spec.pins.pipeline_version='0.9.1-exp.1';
 assert.doesNotThrow(()=>b.resolveBindings(f.queue,f.document));
 f.spec.pins.pipeline_version='0.7.0-exp.1';assert.throws(()=>b.resolveBindings(f.queue,f.document),/Pipeline pin mismatch/);
 f.spec.pins.pipeline_version='file:com.unity.pipeline';assert.throws(()=>b.resolveBindings(f.queue,f.document),/Pipeline pin mismatch/);
});

test('canonical project owns runner source without a separate workspace tooling tree',t=>{
 const f=fixture(t,'6000.3.27f2');f.write(f.queue,'Tools/Automation/run.py','raise RuntimeError("Never execute during composition")');
 f.spec.queue_paths=['Tools/Automation'];f.spec.workspace_paths=[];
 f.review.workspace_digest=b.snapshot(f.workspace,['scripts/runner.py']).digest;
 f.review.workspace_digest=require('node:crypto').createHash('sha256').update('').digest('hex');
 f.review.queue_support_digest=b.snapshot(f.queue,f.spec.queue_paths).digest;f.write(f.queue,f.spec.review_path,f.review);
 f.document.recipes.isolated.argv=['python3','{queue_root}/Tools/Automation/run.py','--project','{project_root}'];f.write(f.queue,'.skill-tree/validation-recipes.json',f.document);
 const p=c.resolveProfile(source,f.queue,'unity');assert.equal(p.execution_bindings.pilot.queue_support_digest,f.review.queue_support_digest);assert.deepEqual(p.execution_bindings.pilot.workspace_paths,[]);
 f.write(f.queue,'Tools/Automation/run.py','changed');assert.throws(()=>c.resolveProfile(source,f.queue,'unity'),/queue support review is stale/);
});
test('empty or invalid automation scopes cannot silently drop runner fingerprints',t=>{
 const f=fixture(t);f.spec.queue_paths=[];f.spec.workspace_paths=[];f.review.workspace_digest=require('node:crypto').createHash('sha256').update('').digest('hex');f.write(f.queue,f.spec.review_path,f.review);
 assert.throws(()=>b.resolveBindings(f.queue,f.document),/reviewed runner/);f.spec.queue_paths='Tools';assert.throws(()=>b.resolveBindings(f.queue,f.document),/require a list/);
});
