const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const source = path.resolve(__dirname, '..');
const c = require('../lib/composer.js');
function fixture(t) { const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-compose-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root; }
function write(root,rel,data) { const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof data==='string'?data:JSON.stringify(data)); }
test('composition is deterministic, standalone and has eight logical names for every flavor',t=>{
 for(const flavor of ['general','web','unity']) {
  const root=fixture(t);
  if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6'}});}
  const profile=c.resolveProfile(source,root,flavor),a=c.compose(source,profile),b=c.compose(source,profile);
  assert.deepEqual(a,b);assert.equal(Object.keys(a.packages).length,8);
  for(const [name,files] of Object.entries(a.packages)) {
   assert.ok(!name.includes('unity-'));assert.equal((files['SKILL.md'].match(/^name:/gm)||[]).length,1);
   assert.match(files['SKILL.md'],new RegExp('Flavor: '+flavor));
   for(const match of files['SKILL.md'].matchAll(/\]\(([^)]+)\)/g)) assert.ok(files[match[1]],match[1]);
   assert.ok(files['scripts/workflow-state.py']||name==='skill-tree-create-documents-snapshot');
   assert.ok(!Object.values(files).join('').includes('If Unity 6'));
  }
 }
});
test('static capability inputs detect additions, unsupported versions and conflicting locks',t=>{
 const root=fixture(t);const first=c.resolveProfile(source,root,'general');write(root,'package.json',{scripts:{test:'node --test'}});
 assert.notDeepEqual(first.inputs,c.resolveProfile(source,root,'general').inputs);
 write(root,'package-lock.json',{lockfileVersion:3,packages:{}});write(root,'yarn.lock','');
 assert.throws(()=>c.resolveProfile(source,root,'web'),/conflicting/i);
 fs.unlinkSync(path.join(root,'yarn.lock'));write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 9999.0.1f1');write(root,'Packages/manifest.json',{dependencies:{}});
 assert.throws(()=>c.resolveProfile(source,root,'unity'),/unsupported/i);
});
test('missing foundation is a persisted capability gap while installation remains composable',t=>{
 const root=fixture(t),p=c.resolveProfile(source,root,'web');assert.equal(p.gaps[0].key,'test-foundation');assert.equal(Object.keys(c.compose(source,p).packages).length,8);
});
test('resource collisions reject undeclared replacements and slot overrides preserve mandatory invariants',()=>{
 assert.throws(()=>c.mergeResources({'a':'one'},{'a':'two'}),/conflict/i);
 assert.deepEqual(c.mergeResources({'a':'one'},{'a':'one'}),{'a':'one'});
 assert.throws(()=>c.mergeSections([{id:'scope',text:'Owner scope',locked:true}],[{id:'scope',text:'Relaxed'}]),/non-replaceable/i);
});
test('adding test assemblies changes the inventory without executing project code',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.1f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6','com.unity.inputsystem':'1.11.2'}});
 const a=c.resolveProfile(source,root,'unity');write(root,'Assets/Tests/EditMode/Tests.asmdef',{name:'Tests',optionalUnityReferences:['TestAssemblies']});const b=c.resolveProfile(source,root,'unity');
 assert.notEqual(a.environment_id,b.environment_id);assert.ok(b.facts.test_assemblies.length);assert.ok(b.recipes['unity-editmode']);
});
