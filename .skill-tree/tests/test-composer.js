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
test('Unity capability composition gates panel, input and performance fixtures before emission',t=>{
 const root=fixture(t);
 function profile(editor,packages,toolkit=false){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: '+editor);write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6',...packages}});if(toolkit)write(root,'Assets/UI/view.uxml','<UXML/>');return c.compose(source,c.resolveProfile(source,root,'unity')).packages['skill-tree-work-through-next'];}
 const old=profile('6000.0.83f1',{'com.unity.ugui':'2.0.0'});assert.ok(old['references/ugui-testing.md']);assert.ok(!old['references/panel-simulator.md']);assert.ok(!old['references/input-testing.md']);
 const modern=profile('6000.3.1f1',{'com.unity.ui.test-framework':'6.3.0','com.unity.inputsystem':'1.11.2','com.unity.test-framework.performance':'3.0.3'},true);
 assert.ok(modern['references/panel-simulator.md']);assert.ok(modern['references/input-testing.md']);assert.ok(modern['references/performance-testing.md']);assert.ok(!modern['references/ugui-testing.md']);
 const unsupported=profile('6000.0.83f1',{'com.unity.ui.test-framework':'6.3.0'},true);assert.ok(!unsupported['references/panel-simulator.md']);
});
test('Web browser component runners retain browser effects and exact pinned conditional resources',t=>{
 const root=fixture(t);write(root,'package.json',{engines:{node:'22.12.0'},devDependencies:{'@playwright/test':'1.56.1'},scripts:{'test:component':'playwright test --project=components','test:api':'node --test tests/api','dev':'vite --host 127.0.0.1'}});
 const p=c.resolveProfile(source,root,'web');assert.equal(p.recipes['script-test-component'].lane,'browser');assert.equal(p.recipes['script-test-api'].lane,'integration');assert.ok(p.recipes['script-dev']);
 const pkg=c.compose(source,p).packages['skill-tree-work-through-next'];assert.ok(pkg['references/playwright-testing.md']);assert.ok(!pkg['references/unity-development.md']);
 write(root,'package.json',{scripts:{test:'python -m pytest'}});const generic=c.compose(source,c.resolveProfile(source,root,'web')).packages['skill-tree-work-through-next'];assert.ok(!generic['references/playwright-testing.md']);assert.ok(generic['references/web-development.md']);
});
test('non-JavaScript Web roots use declared static recipes without importing executable configuration',t=>{
 const root=fixture(t);write(root,'pyproject.toml','[project]\nname = "api"\n');write(root,'.skill-tree/validation-recipes.json',{schema:1,recipes:{'api-tests':{lane:'integration',argv:['python','-m','pytest','tests/api'],input_paths:['pyproject.toml']}}});
 const p=c.resolveProfile(source,root,'web');assert.deepEqual(p.recipes['api-tests'].argv,['python','-m','pytest','tests/api']);assert.ok(!p.gaps.some(g=>g.key==='test-foundation'));
});
