const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const cli=path.resolve(__dirname,'../bin/install.js');
function setup(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-owned-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}
function run(root,extra=[],entry=cli){return spawnSync(process.execPath,[entry,'--target',root,'--only','codex','--flavor','general',...extra],{encoding:'utf8',timeout:15000});}

const inspectionOperation = 'skill-tree-work-through-next';
const inspectionSelection = ['--skills', inspectionOperation];
const inspectionPackage = path.join('.agents/skills', inspectionOperation);
const inspectionProfile = '.skill-tree/installation/profile.json';
const fallbackInspection = {
 lane: 'static',
 input_paths: [],
 assertion_contract: 'explicit source and artifact assertions',
};

function resolvedInspection(root) {
 const script = [
  'import json, runpy, sys',
  'from pathlib import Path',
  'helper = runpy.run_path(sys.argv[1])',
  'store = helper["Store"](Path(sys.argv[2]))',
  'recipe, identity = helper["recipe_for"](store, {"recipe_id": "static-inspection", "parameters": {}})',
  'print(json.dumps({"recipe": recipe, "identity": identity}))',
 ].join('\n');
 const helper = path.join(root, inspectionPackage, 'scripts/workflow-state.py');
 const result = spawnSync('python3', ['-B', '-c', script, helper, root], {encoding: 'utf8', timeout: 15000});
 assert.equal(result.status, 0, result.stdout + result.stderr);
 return JSON.parse(result.stdout);
}

test('static inspection appears in the owned profile and explicit declarations take precedence', t => {
 const root = setup(t);
 const first = run(root, inspectionSelection);
 assert.equal(first.status, 0, first.stdout + first.stderr);
 const profile = () => JSON.parse(fs.readFileSync(path.join(root, inspectionProfile)));
 assert.deepEqual(profile().recipes['static-inspection'], fallbackInspection);
 assert.ok(profile().gaps.some(gap => gap.key === 'test-foundation'));
 const doc = fs.readFileSync(path.join(root, inspectionPackage, 'references/project-profile.md'), 'utf8');
 const concrete = JSON.parse(doc.match(/```json\n([\s\S]*?)\n```/)[1]);
 assert.deepEqual(concrete.recipes['static-inspection'], fallbackInspection);
 assert.deepEqual(resolvedInspection(root).recipe, fallbackInspection);

 const declaration = '.skill-tree/validation-recipes.json';
 const explicit = {lane: 'static', argv: ['node', 'explicit-inspection.js'], input_paths: []};
 fs.writeFileSync(path.join(root, declaration), JSON.stringify({schema: 1, recipes: {'static-inspection': explicit}}));
 const manager = path.join(root, '.skill-tree/installation/manager.js');
 const refreshed = spawnSync(process.execPath, [manager, '--refresh-profile'], {encoding: 'utf8', timeout: 15000});
 assert.equal(refreshed.status, 0, refreshed.stdout + refreshed.stderr);
 const recipe = resolvedInspection(root).recipe;
 assert.deepEqual(recipe, profile().recipes['static-inspection']);
 assert.deepEqual(recipe.argv, explicit.argv);
 assert.deepEqual(recipe.input_paths, [declaration]);
 assert.equal(recipe.assertion_contract, undefined);
});

function copiedSource(t) {
 const legacySource = setup(t);
 const source = path.resolve(__dirname, '..');
 for (const name of ['common', 'config', 'domains', 'lib', 'src', 'templates']) {
  fs.cpSync(path.join(source, name), path.join(legacySource, name), {recursive: true});
 }
 const resources = Object.values(require('../config/resource-map.json'));
 const mappedFixtures = resources.flatMap(groups => Object.values(groups).flatMap(files => Object.values(files)))
  .filter(relative => relative.startsWith('tests/fixtures/director/'));
 const catalogEntry = path.join('skills/general', inspectionOperation, 'SKILL.md');
 for (const relative of new Set([catalogEntry, ...mappedFixtures])) {
  fs.mkdirSync(path.dirname(path.join(legacySource, relative)), {recursive: true});
  fs.copyFileSync(path.join(source, relative), path.join(legacySource, relative));
 }
 return legacySource;
}

const reviewOperation = 'skill-tree-pr-review-cycle';
const commonJsScope = 'scripts/package.json';
const esmProduct = '{"name":"esm-review-fixture","type":"module"}\n';

function reviewModule(root, packageRoot) {
 const packet = {
  runtime_action: 'requirement-plan', project_root: root,
  event: {id:'esm-module-fixture',operation:reviewOperation,anchor:'after'},
  context: {kind:'review',id:'esm-review-fixture',head:'a'.repeat(40),base_oid:'b'.repeat(40),
   target_branch:'main',semantic_fingerprint:'c'.repeat(64),content_fingerprint:'d'.repeat(64)},
  capabilities: ['codex-source-backed-context'],
  adapter: {provider:'codex',mechanism:'source-backed-context'},
 };
 return spawnSync(process.execPath,[path.join(packageRoot,'scripts/plugin-hooks.js'),'--input','-'],
  {cwd:root,input:JSON.stringify(packet),encoding:'utf8',timeout:15000});
}

function assertReviewModule(root, packageRoot) {
 const result = reviewModule(root,packageRoot);
 assert.equal(result.status,0,'Installed PR review helpers must load within an ESM product: '+result.stderr);
 assert.equal(JSON.parse(result.stdout).proof.proof_kind,'completed-readiness');
}

test('owned PR review CommonJS scripts load below ESM across provider layouts', t => {
 const root = setup(t);
 fs.writeFileSync(path.join(root,'package.json'),esmProduct);
 fs.writeFileSync(path.join(root,'app.js'),'export const productModule = "esm";\n');
 fs.writeFileSync(path.join(root,'AGENTS.md'),'Owner instructions.\n');
 const {providers} = require('../config/providers.json');
 const byLocation = new Map();
 for (const host of providers) {
  const location = host.id === 'generic' ? '' : host.projectPath;
  if (!byLocation.has(location)) byLocation.set(location,host.id);
 }
 const hosts = [...byLocation.values()];
 const cliArgs = ['--target',root,'--flavor','general','--skills',reviewOperation,
  ...hosts.flatMap(host=>['--only',host])];
 const install = spawnSync(process.execPath,[cli,...cliArgs],{encoding:'utf8',timeout:120000});
 assert.equal(install.status,0,install.stdout.slice(-1200)+install.stderr);
 const receipt = JSON.parse(fs.readFileSync(path.join(root,inspectionProfile)));
 for (const location of byLocation.keys()) {
  const relative = path.posix.join(location,reviewOperation);
  const packageRoot = path.join(root,relative);
  assertReviewModule(root,packageRoot);
  const marker = fs.readFileSync(path.join(packageRoot,commonJsScope));
  assert.deepEqual(JSON.parse(marker),{type:'commonjs'});
  const expected = require('../lib/composer.js').hash(marker);
  const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot,'references/plugin-bindings.json')));
  assert.equal(receipt.destinations[relative].files[commonJsScope],expected);
  assert.equal(manifest.owned_resources[commonJsScope],expected);
 }
 const verify = spawnSync(process.execPath,[cli,...cliArgs,'--verify'],{encoding:'utf8',timeout:120000});
 assert.equal(verify.status,0,verify.stdout.slice(-1200)+verify.stderr);
 const standaloneRoot = setup(t);
 fs.writeFileSync(path.join(standaloneRoot,'package.json'),esmProduct);
 const copied = path.join(standaloneRoot,reviewOperation);
 fs.cpSync(path.join(root,'.agents/skills',reviewOperation),copied,{recursive:true});
 assertReviewModule(standaloneRoot,copied);
 assert.equal(fs.readFileSync(path.join(root,'package.json'),'utf8'),esmProduct);
 assert.equal(fs.readFileSync(path.join(root,'AGENTS.md'),'utf8'),'Owner instructions.\n');
 const app = spawnSync(process.execPath,['--input-type=module','-e',
  'import {productModule} from "./app.js"; process.stdout.write(productModule)'],{cwd:root,encoding:'utf8',timeout:15000});
 assert.equal(app.status,0,app.stderr);
 assert.equal(app.stdout,'esm');
});

test('the owned CommonJS marker follows upgrade, verification, rollback and uninstall', t => {
 const root = setup(t);
 const legacy = copiedSource(t);
 const resourceMap = path.join(legacy,'config/resource-map.json');
 const retainedMap = JSON.parse(fs.readFileSync(resourceMap));
 delete retainedMap[reviewOperation].scripts['package.json'];
 fs.writeFileSync(resourceMap,JSON.stringify(retainedMap));
 fs.writeFileSync(path.join(root,'package.json'),esmProduct);
 const selection = ['--skills',reviewOperation];
 const previous = run(root,[...selection,'--source',legacy]);
 assert.equal(previous.status,0,previous.stdout+previous.stderr);
 const packageRoot = path.join(root,'.agents/skills',reviewOperation);
 const marker = path.join(packageRoot,commonJsScope);
 const manager = path.join(root,'.skill-tree/installation/manager.js');
 const oldReceipt = fs.readFileSync(path.join(root,inspectionProfile));
 assert.equal(fs.existsSync(marker),false);
 const priorVerify = run(root,[...selection,'--verify']);
 assert.equal(priorVerify.status,0,priorVerify.stdout+priorVerify.stderr);
 const before = reviewModule(root,packageRoot);
 assert.notEqual(before.status,0);
 assert.match(before.stderr,/require is not defined/);
 const installed = run(root,selection);
 assert.equal(installed.status,0,installed.stdout+installed.stderr);
 assertReviewModule(root,packageRoot);
 const owned = fs.readFileSync(marker);
 fs.writeFileSync(marker,'{"type":"module"}\n');
 for (const option of ['--verify','--force','--uninstall']) {
  const rejected=run(root,[...selection,option]);
  assert.notEqual(rejected.status,0);
  assert.equal(fs.readFileSync(marker,'utf8'),'{"type":"module"}\n');
 }
 fs.writeFileSync(marker,owned);
 const rolled = spawnSync(process.execPath,[manager,'--rollback'],{encoding:'utf8',timeout:20000});
 assert.equal(rolled.status,0,rolled.stdout+rolled.stderr);
 assert.equal(fs.existsSync(marker),false);
 assert.deepEqual(fs.readFileSync(path.join(root,inspectionProfile)),oldReceipt);
 const upgraded = run(root,selection);
 assert.equal(upgraded.status,0,upgraded.stdout+upgraded.stderr);
 const removed = run(root,[...selection,'--uninstall']);
 assert.equal(removed.status,0,removed.stdout+removed.stderr);
 assert.equal(fs.existsSync(packageRoot),false);
 assert.equal(fs.readFileSync(path.join(root,'package.json'),'utf8'),esmProduct);
});

test('external sources without membership exports still list, install and verify', t => {
 const root = setup(t);
 const legacySource = copiedSource(t);
 const flavorFile = path.join(legacySource, 'config/flavors.json');
 const membership = JSON.parse(fs.readFileSync(flavorFile));
 delete membership.core_operations;
 delete membership.flavors.director;
 fs.writeFileSync(flavorFile, JSON.stringify(membership));
 for (const relative of ['templates/operations.json', 'config/resource-map.json']) {
  const file = path.join(legacySource, relative);
  const current = JSON.parse(fs.readFileSync(file));
  const core = Object.fromEntries(Object.entries(current).filter(([name]) => !name.startsWith('skill-tree-director-')));
  fs.writeFileSync(file, JSON.stringify(core));
 }
 const composer = path.join(legacySource, 'lib/composer.js');
 fs.appendFileSync(composer, '\ndelete module.exports.flavorNames;\ndelete module.exports.operationNames;\n');

 const external = ['--source', legacySource];
 const listed = run(root, [...external, '--list']);
 assert.equal(listed.status, 0, listed.stdout + listed.stderr);
 assert.match(listed.stdout, /Flavors: general, web, unity\n/);
 assert.ok(listed.stdout.split('\n').includes(inspectionOperation));
 assert.ok(!listed.stdout.includes('skill-tree-director-'));
 const dry = run(root, [...inspectionSelection, ...external, '--dry-run']);
 assert.equal(dry.status, 0, dry.stdout + dry.stderr);
 assert.deepEqual(fs.readdirSync(root), []);
 const legacy = run(root, [...inspectionSelection, ...external]);
 assert.equal(legacy.status, 0, legacy.stdout + legacy.stderr);
 const profileFile = path.join(root, inspectionProfile);
 const legacyReceipt = fs.readFileSync(profileFile);
 for (const selection of [external, []]) {
  const verified = run(root, [...inspectionSelection, ...selection, '--verify']);
  assert.equal(verified.status, 0, verified.stdout + verified.stderr);
  assert.deepEqual(fs.readFileSync(profileFile), legacyReceipt);
 }
});

test('static inspection stays resolvable on an owned legacy profile and appears after source update', t => {
 const root = setup(t);
 const legacySource = copiedSource(t);
 const config = path.join(legacySource, 'config/capabilities.json');
 const legacyCapabilities = JSON.parse(fs.readFileSync(config));
 delete legacyCapabilities.built_in_recipes;
 fs.writeFileSync(config, JSON.stringify(legacyCapabilities));
 fs.appendFileSync(path.join(legacySource, 'lib/plugin-composition.js'), '\n// Prior owned composition bytes.\n');

 const legacy = run(root, [...inspectionSelection, '--source', legacySource]);
 assert.equal(legacy.status, 0, legacy.stdout + legacy.stderr);
 const profileFile = path.join(root, inspectionProfile);
 const legacyReceipt = fs.readFileSync(profileFile);
 assert.equal(JSON.parse(legacyReceipt).recipes['static-inspection'], undefined);
 const verified = run(root, [...inspectionSelection, '--verify']);
 assert.equal(verified.status, 0, verified.stdout + verified.stderr);
 assert.deepEqual(fs.readFileSync(profileFile), legacyReceipt);
 const original = resolvedInspection(root);
 assert.deepEqual(original.recipe, fallbackInspection);

 const updated = run(root, inspectionSelection);
 assert.equal(updated.status, 0, updated.stdout + updated.stderr);
 assert.deepEqual(JSON.parse(fs.readFileSync(profileFile)).recipes['static-inspection'], fallbackInspection);
 assert.deepEqual(resolvedInspection(root), original);
});

test('invalid manager combinations reject before writes while explicit rollback remains available',t=>{
 const manager=require('../lib/installation.js'),root=setup(t);assert.equal(run(root).status,0);
 const entry=path.join(root,'.skill-tree/installation/manager.js'),before=manager.treeHash(root,'.skill-tree');
 for(const args of [['--rollback','--dry-run'],['--recover','--rollback'],['--verify','--refresh-profile'],['--rollback','--rollback'],['--dry-run']]){
  const result=spawnSync(process.execPath,[entry,...args],{encoding:'utf8',timeout:15000});
  assert.notEqual(result.status,0,JSON.stringify(args));assert.equal(manager.treeHash(root,'.skill-tree'),before);
  assert.ok(fs.existsSync(path.join(root,'.agents/skills/skill-tree-add-pending-task/SKILL.md')));
 }
 const rolled=spawnSync(process.execPath,[entry,'--rollback'],{encoding:'utf8',timeout:15000});assert.equal(rolled.status,0,rolled.stderr);
 assert.ok(!fs.existsSync(path.join(root,'.skill-tree/installation/profile.json')));
 assert.equal(run(root).status,0);assert.equal(run(root,['--verify']).status,0);
});
test('installed release version matches the bundled source and forged receipt versions fail verification',t=>{
 const root=setup(t);assert.equal(run(root).status,0);
 const version=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../package.json'))).version;
 const receipt=path.join(root,'.skill-tree/installation/profile.json'),profile=JSON.parse(fs.readFileSync(receipt));
 assert.equal(profile.source_version,version);
 assert.equal(JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/source/config/flavors.json'))).release_version,version);
 const concrete=fs.readFileSync(path.join(root,'.agents/skills/skill-tree-add-pending-task/references/project-profile.md'),'utf8');
 assert.equal(JSON.parse(concrete.match(/```json\n([\s\S]*?)\n```/)[1]).source_version,version);
 profile.source_version='0.0.0';fs.writeFileSync(receipt,JSON.stringify(profile));
 assert.notEqual(run(root,['--verify']).status,0);
});
test('force never adopts an unowned package',t=>{const root=setup(t),dest=path.join(root,'.agents/skills/skill-tree-add-pending-task');fs.mkdirSync(dest,{recursive:true});fs.writeFileSync(path.join(dest,'private.txt'),'preserve');const r=run(root,['--force','--skills','skill-tree-add-pending-task']);assert.notEqual(r.status,0);assert.equal(fs.readFileSync(path.join(dest,'private.txt'),'utf8'),'preserve');});
test('verify rejects a false-positive entrypoint and locally modified packages survive force/uninstall',t=>{const root=setup(t);assert.equal(run(root).status,0);const file=path.join(root,'.agents/skills/skill-tree-add-pending-task/SKILL.md');fs.writeFileSync(file,'unrelated');for(const op of ['--verify','--force','--uninstall'])assert.notEqual(run(root,[op]).status,0);assert.equal(fs.readFileSync(file,'utf8'),'unrelated');});
test('maintenance refresh works without source access and detects newly added tools',t=>{const root=setup(t);assert.equal(run(root).status,0);const manager=path.join(root,'.skill-tree/installation/manager.js');fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));assert.notEqual(run(root,['--verify']).status,0);const r=spawnSync(process.execPath,[manager,'--refresh-profile'],{cwd:os.tmpdir(),encoding:'utf8',timeout:15000});assert.equal(r.status,0,r.stdout+r.stderr);assert.equal(run(root,['--verify']).status,0);const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));assert.ok(profile.recipes['script-test']);assert.equal(profile.gaps.length,0);});
test('fresh noninteractive installs preview Director and raw profile installation requires a flavor', t => {
 const root=setup(t);
 const args=['--only','codex','--target',root,'--yes'];
 const preview=spawnSync(process.execPath,[cli,...args,'--dry-run'],{encoding:'utf8'});
 assert.equal(preview.status,0,preview.stderr);
 assert.match(preview.stdout,/Director preview/);
 const direct=spawnSync(process.execPath,[cli,...args,'--project'],{encoding:'utf8'});
 assert.notEqual(direct.status,0);
 assert.match(direct.stderr,/requires --flavor/);
 for(const options of [['--global'],['--symlink'],['--agent','qwen-code']]) assert.notEqual(run(root,options).status,0);
 assert.equal(fs.existsSync(path.join(root,'.skill-tree')),false);
 assert.equal(fs.existsSync(path.join(root,'.skill-tree-director')),false);
});
test('owned no-op is verified; dry-run reports conflicts without writes',t=>{const root=setup(t);assert.equal(run(root).status,0);const profile=path.join(root,'.skill-tree/installation/profile.json'),before=fs.readFileSync(profile,'utf8');assert.match(run(root).stdout,/current|no-op/);assert.equal(fs.readFileSync(profile,'utf8'),before);fs.writeFileSync(path.join(root,'.agents/skills/skill-tree-add-pending-task/extra.txt'),'local');const r=run(root,['--dry-run','--force']);assert.notEqual(r.status,0);assert.equal(fs.readFileSync(profile,'utf8'),before);});
test('interrupted replacement rolls forward from the journal and preserves unrelated content',t=>{
 const root=setup(t),manager=require('../lib/installation.js');assert.equal(run(root).status,0);
 fs.writeFileSync(path.join(root,'unrelated.txt'),'keep');
 const source=path.resolve(__dirname,'..'),name='skill-tree-add-pending-task';
 const original=fs.renameSync;
 fs.renameSync=(from,to)=>{
  if(from.includes(path.sep+'.staging'+path.sep))throw Error('fixture interruption');
  return original(from,to);
 };
 try{assert.throws(()=>manager.install(fs.realpathSync(root),source,'general',[{rel:'.claude/skills/'+name,name,provider:'claude-code'}]),/fixture interruption/);}finally{fs.renameSync=original;}
 assert.ok(fs.existsSync(path.join(root,'.skill-tree/installation/.journal.json')));
 const entry=path.join(root,'.skill-tree/installation/manager.js'),before=manager.treeHash(root,'.skill-tree');
 manager.verifyOwned(root,manager.receipt(fs.realpathSync(root),true));
 for(const flags of [['--verify'],['--rollback']]){
  const rejected=spawnSync(process.execPath,[entry,...flags],{encoding:'utf8',timeout:15000});
  assert.notEqual(rejected.status,0);assert.match(rejected.stderr,/recovery/i);
  assert.equal(manager.treeHash(root,'.skill-tree'),before);
 }
 const recovered=spawnSync(process.execPath,[entry,'--recover'],{encoding:'utf8',timeout:15000});
 assert.equal(recovered.status,0,recovered.stderr);assert.equal(run(root,['--verify']).status,0);
 assert.ok(fs.existsSync(path.join(root,'.claude/skills',name,'SKILL.md')));
 assert.equal(fs.readFileSync(path.join(root,'unrelated.txt'),'utf8'),'keep');
});
test('flavor switch updates all owned packages; stopped pending validation survives refresh and rollback',t=>{
 const root=setup(t);assert.equal(run(root).status,0);
 const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);const state={format:'skill-tree-future',schema:2,tasks:[],active_run:{id:'fixture-run',phase:'awaiting-validation',stop_reason:'profile refresh',snapshot:['fixture-task']},task_progress:{'fixture-task':{stage:'awaiting-validation'}}};fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify(state));
 const r=run(root,['--flavor','web','--skills','skill-tree-add-pending-task']);assert.equal(r.status,0,r.stdout+r.stderr);
 const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));assert.ok(Object.values(profile.destinations).every(d=>d.flavor==='web'));
 assert.deepEqual(JSON.parse(fs.readFileSync(path.join(docs,'future.json'))),{...state,active_run:{...state.active_run,profile_refresh_required:true}});
 const manager=path.join(root,'.skill-tree/installation/manager.js');const rollback=spawnSync(process.execPath,[manager,'--rollback'],{encoding:'utf8',timeout:15000});assert.equal(rollback.status,0,rollback.stderr);
 assert.equal(JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json'))).flavor,'general');assert.deepEqual(JSON.parse(fs.readFileSync(path.join(docs,'future.json'))),{...state,active_run:{...state.active_run,profile_refresh_required:true}});
});
test('missing foundation is deferred without a queue and captured exactly once after setup',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const helper=path.join(root,'.agents/skills/skill-tree-add-pending-task/scripts/workflow-state.py');
 const capture=()=>spawnSync('python3',[helper,'capture-foundation',root],{encoding:'utf8',timeout:10000});assert.equal(JSON.parse(capture().stdout).status,'deferred-until-documentation-setup');
 const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);fs.writeFileSync(path.join(docs,'future.md'),'# Future Work\n\n## Pending Task Format\n\n## Pending Queue\n\n## Prioritized Next Changes\n\n## Backlog\n');
 const first=JSON.parse(capture().stdout),second=JSON.parse(capture().stdout);assert.equal(first.status,'captured');assert.equal(first.priority,101);assert.equal(second.task_id,first.pending_id);assert.equal(second.status,'reused');
});
test('an active executing controller blocks replacement and malformed maintenance ownership is preserved',t=>{
 const root=setup(t);fs.mkdirSync(path.join(root,'.skill-tree/installation'),{recursive:true});fs.writeFileSync(path.join(root,'.skill-tree/installation/manager.js'),'private');assert.notEqual(run(root,['--force']).status,0);assert.equal(fs.readFileSync(path.join(root,'.skill-tree/installation/manager.js'),'utf8'),'private');
 fs.rmSync(path.join(root,'.skill-tree'),{recursive:true,force:true});assert.equal(run(root).status,0);fs.mkdirSync(path.join(root,'.skill-tree/documents'));fs.writeFileSync(path.join(root,'.skill-tree/documents/future.json'),JSON.stringify({format:'skill-tree-future',schema:2,tasks:[],task_progress:{},active_run:{phase:'implement',stop_reason:null}}));assert.notEqual(run(root,['--force']).status,0);
});
test('untracked maintenance source is a conflict and cannot be adopted by refresh',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const extra=path.join(root,'.skill-tree/installation/source/lib/unowned.js');fs.writeFileSync(extra,'private');assert.notEqual(run(root,['--verify']).status,0);const r=spawnSync(process.execPath,[path.join(root,'.skill-tree/installation/manager.js'),'--refresh-profile'],{encoding:'utf8',timeout:15000});assert.notEqual(r.status,0);assert.equal(fs.readFileSync(extra,'utf8'),'private');
});
test('refresh refuses incompatible workflow state without replacing packages or receipts',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify({schema:999,active_run:null,task_progress:{}}));const before=fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json'),'utf8');assert.notEqual(run(root,['--force']).status,0);assert.equal(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json'),'utf8'),before);
});
test('refresh refuses an unresolved standalone execution attempt and the workflow writer lock',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);const state={format:'skill-tree-future',schema:2,tasks:[],task_progress:{fixture:{stage:'awaiting-validation',checks:{check:{attempt:{attempt_id:'pending-operation'}}}}},active_run:null};fs.writeFileSync(path.join(docs,'future.json'),JSON.stringify(state));assert.notEqual(run(root,['--force']).status,0);
 fs.unlinkSync(path.join(docs,'future.json'));fs.writeFileSync(path.join(root,'.skill-tree/.writer-lock'),'fixture');assert.notEqual(run(root,['--force']).status,0);
});
test('standalone profile refresh stops a waiting controller and preserves progress across rollback',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);const file=path.join(docs,'future.json'),state={format:'skill-tree-future',schema:2,tasks:[],active_run:{id:'fixture-run',phase:'awaiting-validation',stop_reason:null},task_progress:{fixture:{stage:'awaiting-validation',checks:{}}}};fs.writeFileSync(file,JSON.stringify(state));fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));assert.equal(run(root).status,0);const next=JSON.parse(fs.readFileSync(file));assert.equal(next.active_run.id,state.active_run.id);assert.ok(next.active_run.stop_reason);assert.deepEqual(next.task_progress,state.task_progress);
 const manager=path.join(root,'.skill-tree/installation/manager.js');assert.equal(spawnSync(process.execPath,[manager,'--rollback'],{encoding:'utf8',timeout:15000}).status,0);assert.deepEqual(JSON.parse(fs.readFileSync(file)),next);
});
test('a concurrent edit during staging is preserved and activation refuses the changed destination',t=>{
 const root=setup(t),manager=require('../lib/installation.js');assert.equal(run(root).status,0);fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));const victim=path.join(root,'.agents/skills/skill-tree-work-through-next/SKILL.md'),write=fs.writeFileSync;let modified=false;
 fs.writeFileSync=(file,...args)=>{if(!modified&&String(file).includes('/.staging/')){modified=true;write(victim,'concurrent developer edit');}return write(file,...args);};
 try{assert.throws(()=>manager.refresh(fs.realpathSync(root),path.resolve(__dirname,'..')),/changed|conflict|modified/);}finally{fs.writeFileSync=write;}
 assert.equal(fs.readFileSync(victim,'utf8'),'concurrent developer edit');
});
test('delivery profile classifies descriptive metadata and preserves material inputs for explicit recovery',t=>{
 const root=fs.realpathSync(setup(t));
 const installation=require('../lib/installation.js');
 const plugins=require('../lib/plugin-registry.js');
 const git=(...args)=>{
  const run=spawnSync('git',['-C',root,...args],{encoding:'utf8',timeout:10000});
  assert.equal(run.status,0,run.stderr);
  return run.stdout.trim();
 };
 const write=(relative,value)=>{
  const file=path.join(root,relative);
  fs.mkdirSync(path.dirname(file),{recursive:true});
  fs.writeFileSync(file,value);
 };
 git('init','-b','delivery');
 git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid');
 write('package.json','{"name":"profile-fixture","description":"Before"}\n');
 git('add','--','package.json');git('commit','-m','Prior package metadata');
 const original=git('rev-parse','HEAD');
 const installed=run(root,inspectionSelection);
 assert.equal(installed.status,0,installed.stdout+installed.stderr);
 const profile=path.join(root,'.skill-tree/installation/profile.json');
 const before=fs.readFileSync(profile,'utf8');
 const profileHash=require('node:crypto').createHash('sha256').update(before).digest('hex');
 const base={phase:'prepare',target_ref:'refs/heads/delivery',previous_local_head:original,profile_sha256:profileHash};
 const update=(metadata,additional)=>{
  git('switch','--detach',original);
  if(git('branch','--list','delivery'))git('branch','-D','delivery');
  git('switch','-c','delivery',original);
  write('package.json',JSON.stringify({name:'profile-fixture',description:'After',...metadata})+'\n');
  const files=['package.json',...Object.keys(additional)];
  for(const [relative,bytes] of Object.entries(additional))write(relative,bytes);
  git('add','--',...files);git('commit','-m','Synchronized target');
  return {...base,target_head:git('rev-parse','HEAD')};
 };
 const compatible=installation.maintainDeliveredProfile(root,update({keywords:['fixture']},{}));
 assert.equal(compatible.status,'prepared');
 assert.deepEqual(compatible.plan.changed_fields,['description','keywords']);
 assert.equal(compatible.plan.before.profile_sha256,profileHash);
 assert.notEqual(compatible.plan.after.environment_id,compatible.plan.before.environment_id);
 for(const [metadata,differentInput] of [
  [{scripts:{test:'node --test'}},{}],
  [{dependencies:{fixture:'1.0.0'}},{}],
  [{},{'package-lock.json':'{"lockfileVersion":3,"packages":{}}\n'}],
  [{},{'playwright.config.ts':'export default {};\n'}],
  [{},{'.skill-tree/validation-recipes.json':'{"schema":1,"recipes":{}}\n'}],
  [{},{'.skill-tree/installation/plugins.json':JSON.stringify(plugins.emptyRegistry())+'\n'}],
 ]){
  const request=update(metadata,differentInput);
  assert.throws(()=>installation.maintainDeliveredProfile(root,request),/material|unknown|unexplained/);
  assert.equal(fs.readFileSync(profile,'utf8'),before);
 }
});
test('a real controller re-admits after local refresh without resetting task progress',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const docs=path.join(root,'.skill-tree/documents');fs.mkdirSync(docs);fs.copyFileSync(path.join(__dirname,'fixtures/future/valid.md'),path.join(docs,'future.md'));fs.writeFileSync(path.join(root,'source.cs'),'fixture');
 const helper=path.join(root,'.agents/skills/skill-tree-work-through-next/scripts/workflow-state.py');
 function command(name,payload=null){const args=[helper,name,root];if(payload){const p=path.join(root,'input.json');fs.writeFileSync(p,JSON.stringify(payload));args.push('--input',p);}const result=spawnSync('python3',args,{encoding:'utf8',timeout:15000});assert.equal(result.status,0,result.stdout+result.stderr);return JSON.parse(result.stdout);}
 const selected=command('select');command('start');command('begin',{task_id:selected.id});command('implemented',{task_id:selected.id});assert.equal(command('advance').phase,'validate');fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));assert.equal(run(root).status,0);assert.ok(command('index').active_run.stop_reason);command('admit');const current=command('index');assert.equal(current.active_run.stop_reason,null);assert.equal(current.task_progress[selected.id].stage,'awaiting-validation');
});
test('shared provider destinations retain every recorded owner during scoped uninstall',t=>{
 const root=setup(t);assert.equal(run(root).status,0);assert.equal(run(root,['--only','gemini-cli']).status,0);assert.equal(run(root,['--uninstall']).status,0);const file=path.join(root,'.agents/skills/skill-tree-work-through-next/SKILL.md');assert.ok(fs.existsSync(file));const result=spawnSync(process.execPath,[cli,'--target',root,'--only','gemini-cli','--verify'],{encoding:'utf8',timeout:15000});assert.equal(result.status,0,result.stdout+result.stderr);
});
test('verification rejects a forged flavor and rehashed unrelated package content',t=>{
 const root=setup(t);assert.equal(run(root).status,0);const profilePath=path.join(root,'.skill-tree/installation/profile.json'),c=require('../lib/composer.js'),p=JSON.parse(fs.readFileSync(profilePath));const rel='.agents/skills/skill-tree-add-pending-task',file=path.join(root,rel,'SKILL.md');fs.writeFileSync(file,'unrelated but rehashed');p.destinations[rel].files['SKILL.md']=c.hash('unrelated but rehashed');p.destinations[rel].identity=c.hash(c.json(p.destinations[rel].files));fs.writeFileSync(profilePath,JSON.stringify(p));assert.notEqual(run(root,['--verify']).status,0);
});

test('shared bridges survive uninstall until the final recorded provider releases the package',t=>{
 const root=setup(t);assert.equal(run(root,['--with-init']).status,0);assert.equal(run(root,['--only','amp','--with-init']).status,0);assert.equal(run(root,['--uninstall','--with-init']).status,0);assert.match(fs.readFileSync(path.join(root,'AGENTS.md'),'utf8'),/BEGIN skill-tree-skills/);
 const result=spawnSync(process.execPath,[cli,'--target',root,'--only','amp','--uninstall','--with-init'],{encoding:'utf8',timeout:15000});assert.equal(result.status,0,result.stdout+result.stderr);assert.ok(!fs.readFileSync(path.join(root,'AGENTS.md'),'utf8').includes('BEGIN skill-tree-skills'));
});
test('input drift during staging preserves the previous owned generation',t=>{
 const root=setup(t),manager=require('../lib/installation.js');assert.equal(run(root).status,0);const profile=path.join(root,'.skill-tree/installation/profile.json'),before=fs.readFileSync(profile,'utf8');fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));const write=fs.writeFileSync;let changed=false;
 fs.writeFileSync=(file,...args)=>{if(!changed&&String(file).includes('/.staging/')){changed=true;write(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test changed-fixture'}}));}return write(file,...args);};
 try{assert.throws(()=>manager.refresh(fs.realpathSync(root),path.resolve(__dirname,'..')),/input|refresh|environment/);}finally{fs.writeFileSync=write;}
 assert.equal(fs.readFileSync(profile,'utf8'),before);
});
test('post-activation input drift rolls back the owned generation without reverting project inputs',t=>{
 const root=setup(t),manager=require('../lib/installation.js');assert.equal(run(root).status,0);const profile=path.join(root,'.skill-tree/installation/profile.json'),before=fs.readFileSync(profile,'utf8');fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test'}}));const rename=fs.renameSync;let changed=false;
 fs.renameSync=(from,to)=>{const result=rename(from,to);if(!changed&&String(to)===path.join(fs.realpathSync(root),'.skill-tree/installation/profile.json')){changed=true;fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({scripts:{test:'node --test changed-fixture'}}));}return result;};
 try{assert.throws(()=>manager.refresh(fs.realpathSync(root),path.resolve(__dirname,'..')),/input|refresh|profile/i);}finally{fs.renameSync=rename;}
 assert.equal(fs.readFileSync(profile,'utf8'),before);assert.match(fs.readFileSync(path.join(root,'package.json'),'utf8'),/changed-fixture/);
});
test('local refresh catches a Web runner major change and omits unsupported fixture instructions',t=>{
 const root=setup(t);function versions(version){fs.writeFileSync(path.join(root,'package.json'),JSON.stringify({devDependencies:{'@playwright/test':version},scripts:{test:'playwright test'}}));fs.writeFileSync(path.join(root,'package-lock.json'),JSON.stringify({lockfileVersion:3,packages:{'node_modules/@playwright/test':{version}}}));}
 versions('1.56.1');assert.equal(run(root,['--flavor','web']).status,0);const resource=path.join(root,'.agents/skills/skill-tree-work-through-next/references/playwright-testing.md');assert.ok(fs.existsSync(resource));versions('2.0.0');const manager=path.join(root,'.skill-tree/installation/manager.js'),result=spawnSync(process.execPath,[manager,'--refresh-profile'],{encoding:'utf8',timeout:15000});assert.equal(result.status,0,result.stdout+result.stderr);assert.ok(!fs.existsSync(resource));const profile=JSON.parse(fs.readFileSync(path.join(root,'.skill-tree/installation/profile.json')));assert.equal(profile.facts.capabilities['playwright-test'].state,'unsupported');assert.ok(profile.gaps.some(g=>g.key==='unavailable-specialization'));assert.equal(profile.facts.packages['@playwright/test'].version,'2.0.0');
});
