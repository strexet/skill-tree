const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const source = path.resolve(__dirname, '..');
const c = require('../lib/composer.js');
function fixture(t) { const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-compose-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root; }
function write(root,rel,data) { const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof data==='string'?data:JSON.stringify(data)); }
test('composition is deterministic, standalone and has nine logical names for every flavor',t=>{
 for(const flavor of ['general','web','unity']) {
  const root=fixture(t);
  if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.4.6'}}});}
  const profile=c.resolveProfile(source,root,flavor),a=c.compose(source,profile),b=c.compose(source,profile);
  assert.deepEqual(a,b);assert.equal(Object.keys(a.packages).length,9);
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
 const root=fixture(t),p=c.resolveProfile(source,root,'web');assert.equal(p.gaps[0].key,'test-foundation');assert.equal(Object.keys(c.compose(source,p).packages).length,9);
});
test('resource collisions reject undeclared replacements and slot overrides preserve mandatory invariants',()=>{
 assert.throws(()=>c.mergeResources({'a':'one'},{'a':'two'}),/conflict/i);
 assert.deepEqual(c.mergeResources({'a':'one'},{'a':'one'}),{'a':'one'});
 assert.throws(()=>c.mergeSections([{id:'scope',text:'Owner scope',locked:true}],[{id:'scope',text:'Relaxed'}]),/non-replaceable/i);
});
test('adding test assemblies changes the inventory without executing project code',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.3.1f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6','com.unity.inputsystem':'1.11.2'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.4.6'},'com.unity.inputsystem':{version:'1.11.2'}}});
 const a=c.resolveProfile(source,root,'unity');write(root,'Assets/Tests/EditMode/Tests.asmdef',{name:'Tests',optionalUnityReferences:['TestAssemblies']});const b=c.resolveProfile(source,root,'unity');
 assert.notEqual(a.environment_id,b.environment_id);assert.ok(b.facts.test_assemblies.length);assert.ok(b.recipes['unity-editmode']);
});
test('Unity capability composition gates panel, input and performance fixtures before emission',t=>{
 const root=fixture(t);
 function profile(editor,packages,toolkit=false){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: '+editor);write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6',...packages}});write(root,'Packages/packages-lock.json',{dependencies:Object.fromEntries(Object.entries({'com.unity.test-framework':'1.4.6',...packages}).map(([name,version])=>[name,{version}]))});if(toolkit)write(root,'Assets/UI/view.uxml','<UXML/>');return c.compose(source,c.resolveProfile(source,root,'unity')).packages['skill-tree-work-through-next'];}
 const old=profile('6000.0.83f1',{'com.unity.ugui':'2.0.0'});assert.ok(old['references/ugui-testing.md']);assert.ok(!old['references/panel-simulator.md']);assert.ok(!old['references/input-testing.md']);
 const modern=profile('6000.3.1f1',{'com.unity.ui.test-framework':'6.3.0','com.unity.inputsystem':'1.11.2','com.unity.test-framework.performance':'3.0.3'},true);
 assert.ok(modern['references/panel-simulator.md']);assert.ok(modern['references/input-testing.md']);assert.ok(modern['references/performance-testing.md']);assert.ok(!modern['references/ugui-testing.md']);
 const unsupported=profile('6000.0.83f1',{'com.unity.ui.test-framework':'6.3.0'},true);assert.ok(!unsupported['references/panel-simulator.md']);
});
test('Web browser component runners retain browser effects and exact pinned conditional resources',t=>{
 const root=fixture(t);write(root,'package.json',{engines:{node:'22.12.0'},devDependencies:{'@playwright/test':'1.56.1'},scripts:{'test:component':'playwright test --project=components','test:api':'node --test tests/api','dev':'vite --host 127.0.0.1'}});
 write(root,'package-lock.json',{lockfileVersion:3,packages:{'node_modules/@playwright/test':{version:'1.56.1'}}});
 const p=c.resolveProfile(source,root,'web');assert.equal(p.recipes['script-test-component'].lane,'browser');assert.equal(p.recipes['script-test-api'].lane,'integration');assert.ok(p.recipes['script-dev']);
 const pkg=c.compose(source,p).packages['skill-tree-work-through-next'];assert.ok(pkg['references/playwright-testing.md']);assert.ok(!pkg['references/unity-development.md']);
 write(root,'package.json',{scripts:{test:'python -m pytest'}});const generic=c.compose(source,c.resolveProfile(source,root,'web')).packages['skill-tree-work-through-next'];assert.ok(!generic['references/playwright-testing.md']);assert.ok(generic['references/web-development.md']);
});
test('non-JavaScript Web roots use declared static recipes without importing executable configuration',t=>{
 const root=fixture(t);write(root,'pyproject.toml','[project]\nname = "api"\n');write(root,'.skill-tree/validation-recipes.json',{schema:1,recipes:{'api-tests':{lane:'integration',argv:['python','-m','pytest','tests/api'],input_paths:['pyproject.toml']}}});
 const p=c.resolveProfile(source,root,'web');assert.deepEqual(p.recipes['api-tests'].argv,['python','-m','pytest','tests/api']);assert.ok(!p.gaps.some(g=>g.key==='test-foundation'));
});
test('irrelevant input formatting can refresh environment identity without changing package bytes',t=>{
 const root=fixture(t);write(root,'package.json','{"scripts":{"test":"node --test"}}');const a=c.resolveProfile(source,root,'general'),first=c.compose(source,a);
 write(root,'package.json','{\n  "scripts": { "test": "node --test" }\n}\n');const b=c.resolveProfile(source,root,'general'),second=c.compose(source,b);
 assert.notEqual(a.environment_id,b.environment_id);assert.deepEqual(first.output_digests,second.output_digests);
});
test('every flavor audit retains common metadata and prose validation without source dependencies',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json',{dependencies:{}});
 for(const flavor of ['general','web','unity']){
  const files=c.compose(source,c.resolveProfile(source,root,flavor)).packages['skill-tree-repo-documentation-audit'];
  assert.match(files['SKILL.md'],/validate-repository-documentation\.py/);assert.match(files['SKILL.md'],/validate-document-rules\.py/);assert.ok(files['scripts/validate-repository-documentation.py']);
 }
});
test('declared versions never masquerade as resolved capabilities',t=>{
 const root=fixture(t);write(root,'package.json',{devDependencies:{'@playwright/test':'1.56.1'},scripts:{test:'playwright test'}});const p=c.resolveProfile(source,root,'web');assert.notEqual(p.facts.packages['@playwright/test'].state,'known');assert.equal(p.facts.packages['@playwright/test'].version,null);assert.ok(!c.compose(source,p).packages['skill-tree-work-through-next']['references/playwright-testing.md']);
});
test('explicit recipe formats reject unknown lanes and unresolved command parameters',t=>{
 const root=fixture(t);write(root,'.skill-tree/validation-recipes.json',{schema:1,recipes:{tests:{lane:'invented-runner',argv:['custom-runner'],input_paths:[]}}});assert.throws(()=>c.resolveProfile(source,root,'web'),/lane|unsupported/i);
});

test('Unity required UTF flags require resolution evidence and track reload settings',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6'}});
 assert.throws(()=>c.resolveProfile(source,root,'unity'),/resolved UTF|lock/);
 write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.4.6'}}});const first=c.resolveProfile(source,root,'unity');write(root,'ProjectSettings/EditorSettings.asset','m_EnterPlayModeOptionsEnabled: 1\nm_EnterPlayModeOptions: 3\n');const next=c.resolveProfile(source,root,'unity');assert.notEqual(first.environment_id,next.environment_id);assert.equal(next.facts.reload.enabled,'1');assert.ok(next.recipes['unity-editmode'].input_paths.includes('ProjectSettings/EditorSettings.asset'));
});
test('input fingerprints hash raw bytes even for an opaque dependency lock',t=>{
 const root=fixture(t),file=path.join(root,'bun.lockb');fs.writeFileSync(file,Buffer.from([0x80]));const first=c.resolveProfile(source,root,'general');fs.writeFileSync(file,Buffer.from([0x81]));const next=c.resolveProfile(source,root,'general');assert.notEqual(first.inputs['bun.lockb'],next.inputs['bun.lockb']);
});
test('resolved UTF 1.6.0 supports the pinned Unity 6000.0 target without accepting unresolved or future versions',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');
 write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.6.0'}});
 write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0',source:'builtin'}}});
 const p=c.resolveProfile(source,root,'unity');assert.equal(p.recipes['unity-editmode'].utf_version,'1.6.0');assert.equal(p.facts.packages['com.unity.test-framework'].resolution_source,'Packages/packages-lock.json');
 for(const lane of ['EditMode','PlayMode'])assert.deepEqual(p.recipes['unity-'+lane.toLowerCase()].argv,['Unity','-batchmode','-projectPath','{project_root}','-runTests','-testPlatform',lane,'-testFilter','{test_filter}','-testResults','{result_path}','-logFile','{log_path}']);
 assert.ok(c.compose(source,p).packages['skill-tree-work-through-next']);
 write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.1',source:'builtin'}}});assert.throws(()=>c.resolveProfile(source,root,'unity'),/Unsupported.*UTF/);
 fs.unlinkSync(path.join(root,'Packages/packages-lock.json'));assert.throws(()=>c.resolveProfile(source,root,'unity'),/Unsupported.*UTF/);
});
test('Unity BOM-prefixed JSON remains static input with unchanged raw-byte fingerprints',t=>{
 const root=fixture(t);write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json','\uFEFF'+JSON.stringify({dependencies:{'com.unity.test-framework':'1.6.0'}}));write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.6.0',source:'builtin'}}});
 const rel='Assets/Tests/Fixture.asmdef';write(root,rel,'\uFEFF'+JSON.stringify({name:'Fixture',optionalUnityReferences:['TestAssemblies']}));const before=fs.readFileSync(path.join(root,rel));
 const p=c.resolveProfile(source,root,'unity');assert.ok(p.facts.test_assemblies.includes(rel));assert.equal(p.inputs[rel],c.hash(before));assert.deepEqual(fs.readFileSync(path.join(root,rel)),before);
 write(root,rel,'\uFEFF{broken');assert.throws(()=>c.resolveProfile(source,root,'unity'),SyntaxError);
});
