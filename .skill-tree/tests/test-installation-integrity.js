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

test('static inspection stays resolvable on an owned legacy profile and appears after source update', t => {
 const root = setup(t);
 const legacySource = setup(t);
 const source = path.resolve(__dirname, '..');
 for (const name of ['common', 'config', 'domains', 'lib', 'src', 'templates']) {
  fs.cpSync(path.join(source, name), path.join(legacySource, name), {recursive: true});
 }
 const catalogEntry = path.join('skills/general', inspectionOperation, 'SKILL.md');
 fs.mkdirSync(path.dirname(path.join(legacySource, catalogEntry)), {recursive: true});
 fs.copyFileSync(path.join(source, catalogEntry), path.join(legacySource, catalogEntry));
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
test('noninteractive missing flavor, global, symlink and upstream specialization fail without writes',t=>{const root=setup(t);for(const args of [['--only','codex','--target',root,'--yes'],['--global'],['--symlink'],['--agent','qwen-code']]){const r=args[0]==='--only'?spawnSync(process.execPath,[cli,...args],{encoding:'utf8'}):run(root,args);assert.notEqual(r.status,0);}assert.equal(fs.existsSync(path.join(root,'.skill-tree')),false);});
test('owned no-op is verified; dry-run reports conflicts without writes',t=>{const root=setup(t);assert.equal(run(root).status,0);const profile=path.join(root,'.skill-tree/installation/profile.json'),before=fs.readFileSync(profile,'utf8');assert.match(run(root).stdout,/current|no-op/);assert.equal(fs.readFileSync(profile,'utf8'),before);fs.writeFileSync(path.join(root,'.agents/skills/skill-tree-add-pending-task/extra.txt'),'local');const r=run(root,['--dry-run','--force']);assert.notEqual(r.status,0);assert.equal(fs.readFileSync(profile,'utf8'),before);});
test('interrupted replacement rolls forward from the journal and preserves unrelated content',t=>{
 const root=setup(t),manager=require('../lib/installation.js');assert.equal(run(root).status,0);
 fs.writeFileSync(path.join(root,'unrelated.txt'),'keep');
 const source=path.resolve(__dirname,'..'),name='skill-tree-add-pending-task';
 const original=fs.renameSync;
 fs.renameSync=()=>{throw Error('fixture interruption');};
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
