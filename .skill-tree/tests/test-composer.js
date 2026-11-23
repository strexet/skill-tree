const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const source = path.resolve(__dirname, '..');
const c = require('../lib/composer.js');
const expectedOperations = ['skill-tree-3d','skill-tree-3d-blender','skill-tree-3d-motion','skill-tree-3d-references','skill-tree-3d-texture','skill-tree-3d-unity','skill-tree-add-pending-task','skill-tree-clarify-tasks','skill-tree-create-documents-snapshot','skill-tree-force-process','skill-tree-full-cycle','skill-tree-game-design','skill-tree-game-design-balance','skill-tree-game-design-mechanics','skill-tree-implement-all','skill-tree-implement-next-future-task','skill-tree-narative','skill-tree-plugins','skill-tree-pr-review-cycle','skill-tree-process-future-pending','skill-tree-repo-documentation','skill-tree-repo-documentation-audit','skill-tree-work-through-next'];
function fixture(t) { const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-compose-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root; }
function write(root,rel,data) { const p=path.join(root,rel);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,typeof data==='string'?data:JSON.stringify(data)); }
test('source recipe identities survive composition and retain freshness and collision checks',t=>{
 const root=fixture(t),rel='.skill-tree/config/repository.json';
 write(root,rel,{schema:1,role:'source',recipes:{'focused-check':{lane:'unit',argv:['python3','focused.py'],input_paths:[]}}});
 const first=c.resolveProfile(source,root,'general');
 assert.deepEqual(first.recipes['focused-check']?.argv,['python3','focused.py']);
 assert.ok(first.recipes['focused-check'].input_paths.includes(rel));
 write(root,rel,{schema:1,role:'source',recipes:{'focused-check':{lane:'unit',argv:['python3','changed.py'],input_paths:[]}}});
 assert.notEqual(first.environment_id,c.resolveProfile(source,root,'general').environment_id);
 write(root,'.skill-tree/validation-recipes.json',{schema:1,recipes:{'focused-check':{lane:'unit',argv:['other'],input_paths:[]}}});
 assert.throws(()=>c.resolveProfile(source,root,'general'),/collision/i);
});
test('target role cannot inject source recipes',t=>{
 const root=fixture(t);write(root,'.skill-tree/config/repository.json',{schema:1,role:'target',recipes:{unowned:{lane:'unit',argv:['unowned'],input_paths:[]}}});
 assert.equal(c.resolveProfile(source,root,'general').recipes.unowned,undefined);
});
test('composition is deterministic, standalone and has the complete authored operation set for every flavor',t=>{
 for(const flavor of ['general','web','unity']) {
  const root=fixture(t);
  if(flavor==='unity'){write(root,'ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1');write(root,'Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6'}});write(root,'Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.4.6'}}});}
  const profile=c.resolveProfile(source,root,flavor),a=c.compose(source,profile),b=c.compose(source,profile);
  assert.deepEqual(a,b);assert.deepEqual(Object.keys(a.packages).sort(),expectedOperations);
  for(const [name,files] of Object.entries(a.packages)) {
   assert.ok(!name.includes('unity-'));assert.equal((files['SKILL.md'].match(/^name:/gm)||[]).length,1);
   assert.match(files['SKILL.md'],new RegExp('Flavor: '+flavor));
   for(const match of files['SKILL.md'].matchAll(/\]\(([^)]+)\)/g)) assert.ok(files[match[1].split('#',1)[0]],match[1]);
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
 const root=fixture(t),p=c.resolveProfile(source,root,'web');assert.equal(p.gaps[0].key,'test-foundation');assert.deepEqual(Object.keys(c.compose(source,p).packages).sort(),expectedOperations);
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

test('narrative topic navigation and every craft card resolve in all profiles', t => {
  for (const flavor of ['general', 'web', 'unity']) {
    const root = fixture(t);
    if (flavor === 'unity') {
      write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.0.83f1');
      write(root, 'Packages/manifest.json', {dependencies: {}});
    }
    const profile = c.resolveProfile(source, root, flavor);
    const skill = c.compose(source, profile, ['skill-tree-narative']).packages['skill-tree-narative'];
    assert.match(skill['SKILL.md'], /references\/narrative-topic-routing\.md/);
    assert.ok(skill['scripts/narrative-route-check.py']);
    const catalog = skill['references/narrative-craft-catalog.md']
      .split('## Coverage index')[1].split('## Example application')[0];
    const links = [...catalog.matchAll(/\]\((narrative-craft-[a-z-]+\.md)#([a-z-]+)\)/g)];
    assert.equal(links.length, 34);
    assert.equal(new Set(links.map(match => match[0])).size, 34);
    for (const [, file, anchor] of links) {
      assert.ok(skill['references/' + file].includes('id="' + anchor + '"'), file + '#' + anchor);
    }
  }
});

test('narrative composition rejects a missing topic referenced by the router', t => {
  const sourceCopy = fixture(t);
  for (const dir of ['common', 'domains', 'templates', 'config', 'lib', 'src']) {
    fs.cpSync(path.join(source, dir), path.join(sourceCopy, dir), {recursive: true});
  }
  const resourceMap = JSON.parse(fs.readFileSync(path.join(sourceCopy, 'config/resource-map.json'), 'utf8'));
  delete resourceMap['skill-tree-narative'].references['narrative-claims.md'];
  write(sourceCopy, 'config/resource-map.json', resourceMap);
  const profile = c.resolveProfile(sourceCopy, fixture(t), 'general');
  assert.throws(() => c.compose(sourceCopy, profile, ['skill-tree-narative']),
    /Missing composed link: .*narrative-claims\.md/);
});

const gameDesignPackages = [
  ['Game Design', 'skill-tree-game-design', [
    ['game-design-gdd.md', 'game-design-disciplines.md', 'game-design-records.md'],
    ['game-design-gdd.md', 'game-design-records.md'],
    ['game-design-gdd.md', 'game-design-playtest.md', 'narrative-human-playtest.md'],
  ]],
  ['Balance', 'skill-tree-game-design-balance', [
    ['game-design-balance-study.md', 'game-design-balance-methods.md', 'game-design-disciplines.md', 'game-design-records.md'],
    ['game-design-balance-study.md', 'game-design-records.md'],
    ['game-design-balance-study.md', 'game-design-playtest.md', 'narrative-human-playtest.md'],
  ]],
  ['Mechanics', 'skill-tree-game-design-mechanics', [
    ['game-design-mechanics.md', 'game-design-patterns.md'],
    ['game-design-mechanics.md', 'game-design-atlas.md', 'game-design-records.md'],
    ['game-design-mechanics.md', 'game-design-disciplines.md', 'game-design-records.md'],
  ]],
];

for (const [label, operation, chains] of gameDesignPackages) {
  const entryReference = chains[0][0];
  const unavailableResources = new Set(chains.map(chain => chain.at(-1)));
  test(label + ' packages its authoring references in every flavor', t => {
    for (const flavor of ['general', 'web', 'unity', 'director']) {
      const root = fixture(t);
      if (flavor === 'unity') {
        write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.0.83f1');
        write(root, 'Packages/manifest.json', {dependencies: {}});
      }
      const profile = c.resolveProfile(source, root, flavor);
      const files = c.compose(source, profile, [operation]).packages[operation];
      assert.ok(files['SKILL.md'].includes('](references/' + entryReference + ')'));
      for (const chain of chains) {
        for (const [index, name] of chain.entries()) {
          const reference = files['references/' + name];
          assert.equal(reference, c.read(source, 'common/references/' + name));
          if (index > 0) {
            assert.ok(files['references/' + chain[index - 1]].includes('](' + name + ')'));
          }
        }
      }
    }
  });

  test(label + ' composition rejects unbundled authoring references', t => {
    const sourceCopy = fixture(t);
    for (const dir of ['common', 'domains', 'templates', 'config', 'lib', 'src']) {
      fs.cpSync(path.join(source, dir), path.join(sourceCopy, dir), {recursive: true});
    }
    const resourceMap = JSON.parse(fs.readFileSync(path.join(sourceCopy, 'config/resource-map.json'), 'utf8'));
    for (const dependency of unavailableResources) {
      const original = resourceMap[operation].references[dependency];
      assert.ok(original);
      delete resourceMap[operation].references[dependency];
      write(sourceCopy, 'config/resource-map.json', resourceMap);
      const profile = c.resolveProfile(sourceCopy, fixture(t), 'general');
      assert.throws(() => c.compose(sourceCopy, profile, [operation]), error =>
        error.message.startsWith('Missing composed link: ') && error.message.endsWith(dependency));
      resourceMap[operation].references[dependency] = original;
    }
  });
}

test('Director selects the scoped additional operations and packages the exact runtime for each', t => {
  const root = fixture(t);
  const names = ['setup', 'intake', 'plan', 'run', 'decide', 'status', 'review', 'audit', 'install']
    .map(name => 'skill-tree-director-' + name).sort();
  const profile = c.resolveProfile(source, root, 'director');
  const built = c.compose(source, profile);
  assert.deepEqual(c.compose(source, profile), built);
  assert.deepEqual(Object.keys(built.packages).sort(), [...expectedOperations, ...names].sort());
  for (const name of names) {
    const files = built.packages[name];
    const runtime = 'scripts/runtime/';
    assert.ok(files['scripts/director-entry.py']);
    assert.equal(files[runtime + 'common/scripts/director-state.py'], c.read(source, 'common/scripts/director-state.py'));
    assert.ok(files[runtime + 'common/scripts/director-handoff.py']);
    assert.ok(files[runtime + 'lib/installation.js']);
    assert.ok(files[runtime + 'tests/fixtures/director/fixture-manifest.json']);
  }
  assert.equal(profile.facts.director.narrative.status, 'source-verified');
  assert.equal(profile.facts.director.artworkshop.status, 'unsupported');
  assert.equal(profile.facts.director.logs.status, 'unsupported');
  assert.throws(() => c.compose(source, c.resolveProfile(source, root, 'general'), [names[0]]), /unavailable for flavor/);
  assert.ok(built.packages['skill-tree-director-install']['scripts/runtime/lib/director-canary.js']);
});

test('Director profile discovers a shared Unity checkout without asserting runtime qualification', t => {
  const root = fixture(t);
  assert.equal(c.resolveProfile(source, root, 'director').facts.director.unity.status, 'unavailable');
  write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.3.27f2');
  write(root, 'Packages/manifest.json', {dependencies: {'com.unity.test-framework': '1.6.0'}});
  write(root, 'Packages/packages-lock.json', {dependencies: {'com.unity.test-framework': {version: '1.6.0'}}});
  write(root, 'Assets/Tests/Fixture.asmdef', {name: 'Fixture', optionalUnityReferences: ['TestAssemblies']});
  const profile = c.resolveProfile(source, root, 'director');
  assert.equal(profile.facts.director.unity.status, 'recipe-discovered');
  assert.equal(profile.recipes['unity-editmode'].utf_version, '1.6.0');
  assert.match(profile.recipes['unity-playmode'].qualification, /isolated fixture required/);
  assert.equal(c.resolveProfile(source, root, 'general').recipes['unity-editmode'], undefined);
});

test('feature folder guidance is reachable from normal composed entry points', t => {
  const root = fixture(t);
  write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.0.83f1');
  write(root, 'Packages/manifest.json', {dependencies: {}});

  const resolveLink = (files, from, destination) => {
    assert.ok(files[from].includes('](' + destination + ')'), from + ' links to ' + destination);
    const resolved = path.posix.join(path.posix.dirname(from), destination.split('#')[0]);
    assert.ok(files[resolved], resolved + ' is shipped in the package');
    return files[resolved];
  };

  for (const flavor of ['general', 'web', 'unity', 'director']) {
    const operation = flavor === 'director' ? 'skill-tree-director-setup' : 'skill-tree-implement-next-future-task';
    const profile = c.resolveProfile(source, root, flavor);
    const files = c.compose(source, profile, [operation]).packages[operation];
    if (flavor === 'director') resolveLink(files, 'SKILL.md', 'references/director-workflow.md');
    const shared = flavor === 'director'
      ? resolveLink(files, 'references/director-workflow.md', 'development-practices.md#organize-files-by-feature')
      : resolveLink(files, 'SKILL.md', 'references/development-practices.md');
    assert.match(shared, /## Organize files by feature/);
    assert.match(shared, /app\/orders\/page\.tsx/);
    assert.match(shared, /src\/shared\/format\/format-date\.ts/);
    assert.doesNotMatch(shared, /src\/shared\/format\/(?:README\.md|catalog\.json)/);
    assert.ok(!shared.includes('Goblin.prefab'));
    if (flavor === 'unity') {
      const unity = resolveLink(files, 'SKILL.md', 'references/unity-development.md');
      assert.match(unity, /Assets\/Features\/Goblin\/Prefabs\/Goblin\.prefab/);
    } else {
      assert.equal(files['references/unity-development.md'], undefined);
    }
  }
});

test('Unity feature folder examples resolve the README and catalog paths', t => {
  const root = fixture(t);
  write(root, 'ProjectSettings/ProjectVersion.txt', 'm_EditorVersion: 6000.0.83f1');
  write(root, 'Packages/manifest.json', {dependencies: {}});
  const operation = 'skill-tree-implement-next-future-task';
  const profile = c.resolveProfile(source, root, 'unity');
  const doc = c.compose(source, profile, [operation]).packages[operation]['references/unity-development.md'];
  const section = doc.split('## Organize feature assets\n')[1]?.split('\n## ')[0];
  assert.ok(section, 'The Unity package includes the feature asset examples');
  const example = new Map([...section.matchAll(/\x60\x60\x60(text|markdown|json)\n([\s\S]*?)\n\x60\x60\x60/g)]
    .map(([, format, text]) => [format, text]));
  assert.deepEqual([...example.keys()], ['text', 'markdown', 'json']);
  const paths = new Set(example.get('text').split('\n').filter(Boolean));
  const feature = 'Assets/Features/Goblin';
  const prefab = feature + '/Prefabs/Goblin.prefab';
  const readme = feature + '/README.md';
  const catalog = feature + '/catalog.json';
  assert.ok(paths.has(readme));
  const markdown = example.get('markdown');
  const links = new Map([...markdown.matchAll(/^\[([^\]]+)\]: (\S+)$/gm)]
    .map(([, name, target]) => [name, target]));
  const destinations = [...markdown.matchAll(/\]\[([^\]]+)\]/g)].map(([, name]) => {
    assert.ok(links.has(name), 'README defines ' + name);
    return path.posix.join(path.posix.dirname(readme), links.get(name));
  });
  assert.deepEqual(destinations.sort(), [prefab, catalog].sort());
  assert.ok(destinations.every(target => paths.has(target)));

  const entries = JSON.parse(example.get('json')).entries;
  assert.deepEqual(entries.map(entry => entry.path).sort(), [prefab, feature + '/Scripts/GoblinBehaviour.cs'].sort());
  const targetExists = value => !path.posix.isAbsolute(value) &&
    path.posix.normalize(value) === value && paths.has(value);
  for (const entry of entries) {
    assert.ok(entry.purpose.trim() && targetExists(entry.path));
  }
  const behavior = entries.find(entry => entry.extends);
  assert.equal(behavior.extends.type, 'EnemyBehaviour');
  assert.ok(targetExists(behavior.extends.path));
  assert.ok(!targetExists(behavior.extends.path.replace('EnemyBehaviour.cs', 'OldEnemyBehaviour.cs')));
});
