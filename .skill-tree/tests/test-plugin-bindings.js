'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{spawnSync}=require('node:child_process');
const api=require('../lib/plugin-bindings.js');
const operations=require('../templates/operations.json');
const processOp='skill-tree-process-future-pending',implementOp='skill-tree-implement-next-future-task',controllerOp='skill-tree-implement-all';
const task='T-11111111-1111-4111-8111-111111111111',pending='P-22222222-2222-4222-8222-222222222222',run='WR-33333333-3333-4333-8333-333333333333';
const packages={editor:{id:'editor'},interview:{id:'interview'}};
const code=expected=>error=>error.code===expected;
function trustedCatalog(extra={}){
 const boundaries={};
 for(const operation of Object.keys(operations))for(const phase of ['before','during','after'])boundaries[operation+':'+phase]={operation,version:'1',context_kinds:['request','project','pending','task','task-group','document','snapshot','management','controller','review'],handler:()=>{}};
 return api.createAnchorCatalog(operations,{boundaries,...extra});
}
const binding=(id,plugin_id='editor',extra={})=>({id,plugin_id,operation:processOp,anchor:'after',enabled:true,...extra});
const taskContext=()=>({kind:'task',id:'task-context',task_ids:[task],tags:{language:'en'},changed_files:['source.js']});
const event=(operation=processOp,anchor='after',extra={})=>({id:'operation-event',attempt_id:'dispatch-attempt',operation,anchor,...extra});
const compiled=(bindings,extra={})=>api.compileBindings(bindings,{packages,catalog:trustedCatalog(),...extra});

test('binding foundation exports runnable definition and identity APIs',()=>{
 for(const name of ['createAnchorCatalog','resolveLocation','compileBindings','validateContext','selectBindings','moveBinding','removeBinding','dispatchIdentity','classifyDelivery','enterLineage'])assert.equal(typeof api[name],'function');
});
test('the actual owned operation catalog exposes before during and after without a fixed operation count',()=>{
 const catalog=trustedCatalog();assert.deepEqual(catalog.operations,Object.keys(operations).sort());
 for(const operation of Object.keys(operations))for(const anchor of ['before','during','after']){
  const result=api.resolveLocation({operation,anchor},catalog);assert.equal(result.status,'resolved');assert.equal(result.boundary_id,operation+':'+anchor);
 }
 const added='skill-tree-later-operation',later={...operations,[added]:{title:'Later Operation'}},boundaries={[added+':after']:{operation:added,version:'1',context_kinds:['management'],handler:()=>{}}};
 assert.equal(api.resolveLocation({operation:added,anchor:'after'},api.createAnchorCatalog(later,{boundaries})).status,'resolved');
});
test('named anchors resolve only to an actual trusted owned callable boundary',()=>{
 let calls=0;const handler=()=>{calls++;},boundary={operation:implementOp,version:'plan-draft-v1',context_kinds:['task'],handler};
 const catalog=api.createAnchorCatalog(operations,{boundaries:{'plan-drafted':boundary},named:[{operation:implementOp,name:'after-draft-plan',boundary:'plan-drafted'}]});
 const result=api.resolveLocation({operation:implementOp,anchor:'after-draft-plan'},catalog);assert.equal(result.status,'resolved');assert.equal(result.boundary_id,'plan-drafted');assert.equal(catalog.boundaries[result.boundary_id].handler,handler);assert.equal(calls,0);
});
test('a custom label missing an owned handler or operation remains visibly unresolved',()=>{
 const catalog=api.createAnchorCatalog(operations,{boundaries:{fake:{operation:implementOp,version:'1',executable:true}},named:[{operation:implementOp,name:'fake-anchor',boundary:'fake'}]});
 assert.equal(api.resolveLocation({operation:implementOp,anchor:'fake-anchor'},catalog).status,'unresolved');
 assert.equal(api.resolveLocation({operation:'foreign-operation',anchor:'after'},catalog).status,'unresolved');
 assert.equal(api.resolveLocation({operation:implementOp,anchor:'unregistered-step'},catalog).status,'unresolved');
 assert.match(api.resolveLocation({operation:implementOp,anchor:'fake-anchor'},catalog).reason,/handler|boundary|callable/i);
});
test('free-text aliases map to verified locations while unknown and ambiguous text stays unresolved',()=>{
 const catalog=trustedCatalog({aliases:[{phrase:'после обработки задач',operation:processOp,anchor:'after'},{phrase:'ambiguous',operation:processOp,anchor:'after'},{phrase:'ambiguous',operation:implementOp,anchor:'after'}]});
 const result=api.resolveLocation('  ПОСЛЕ   ОБРАБОТКИ ЗАДАЧ ',catalog);assert.equal(result.status,'resolved');assert.equal(result.operation,processOp);assert.equal(result.anchor,'after');
 assert.equal(api.resolveLocation('insert wherever useful',catalog).status,'unresolved');assert.match(api.resolveLocation('ambiguous',catalog).reason,/ambiguous/i);
});
test('ordered repeated packages retain distinct occurrence values without package duplication',()=>{
 const rows=[binding('editor-a','editor',{parameters:{pass:'initial'},instructions:'First pass'}),binding('interview-b','interview'),binding('editor-c','editor',{parameters:{pass:'final'},instructions:'Final pass'})],before=JSON.stringify(rows),result=compiled(rows);
 assert.equal(result.bindings.length,3);assert.deepEqual(result.bindings.map(row=>row.id),['editor-a','interview-b','editor-c']);assert.deepEqual(result.bindings.map(row=>row.plugin_id),['editor','interview','editor']);assert.equal(result.bindings[0].effective.values.pass,'initial');assert.equal(result.bindings[2].effective.values.pass,'final');assert.equal(result.bindings[2].effective.instructions,'Final pass');assert.equal(JSON.stringify(rows),before);assert.deepEqual(Object.keys(packages),['editor','interview']);
});
test('duplicate occurrence identities and missing packages are rejected independently of plugin multiplicity',()=>{
 assert.throws(()=>compiled([binding('same'),binding('same')]),code('binding-identity'));
 assert.throws(()=>compiled([binding('unknown','missing')]),code('binding-plugin'));
 assert.throws(()=>compiled([binding('bad','editor',{enabled:'yes'})]),code('binding-definition'));
});
test('moving and removing one occurrence preserve identity data and every unrelated occurrence',()=>{
 const rows=[binding('a'),binding('b','interview'),binding('c')],before=JSON.stringify(rows),moved=api.moveBinding(rows,'c',0);
 assert.deepEqual(moved.map(row=>row.id),['c','a','b']);assert.deepEqual(moved[0],rows[2]);assert.deepEqual(api.removeBinding(moved,'a').map(row=>row.id),['c','b']);assert.equal(JSON.stringify(rows),before);
 assert.throws(()=>api.moveBinding(rows,'missing',0),code('binding-identity'));assert.throws(()=>api.moveBinding(rows,'a',9),code('binding-order'));assert.throws(()=>api.removeBinding(rows,'missing'),code('binding-identity'));
});
test('effective parameters use project defaults and explicit occurrence/run overrides without core field mutation',()=>{
 const result=compiled([binding('a','editor',{parameters:{tone:'binding',authority:'plugin-data'},instructions:'binding'})],{parameterDefaults:{editor:{upstream:{values:{tone:'upstream',extra:1},instructions:'upstream'},project:{values:{tone:'project'}}}},runOverrides:{a:{values:{tone:'run'},instructions:'run'}}});
 assert.equal(result.bindings.length,1);const row=result.bindings[0];assert.deepEqual(row.effective.values,{tone:'run',extra:1,authority:'plugin-data'});assert.equal(row.effective.instructions,'run');assert.equal(row.effective.origins.values['/tone'],'run');assert.equal(row.authority,undefined);assert.equal(row.context,undefined);
});
test('declarative conditions filter enabled occurrences in configured order',()=>{
 const result=compiled([binding('a','editor',{condition:{equals:{path:'/tags/language',value:'en'}}}),binding('disabled','editor',{enabled:false}),binding('not-matched','interview',{condition:{present:'/missing'}}),binding('c','editor',{condition:{all:[{present:'/task_ids'},{in:{path:'/kind',values:['task','task-group']}},{not:{equals:{path:'/tags/language',value:'ru'}}}]}})]),selected=api.selectBindings(result,event(),taskContext());
 assert.deepEqual(selected.bindings.map(row=>row.id),['a','c']);assert.deepEqual(selected.unresolved,[]);
});
test('unsupported executable conditions and non-JSON parameters are explicit failures without evaluation',()=>{
 assert.throws(()=>compiled([binding('script','editor',{condition:'process.exit(1)'})]),code('binding-condition'));
 assert.throws(()=>compiled([binding('unknown','editor',{condition:{evaluate:'anything'}})]),code('binding-condition'));
 assert.throws(()=>compiled([binding('non-json','editor',{parameters:{value:Infinity}})]),code('parameter-json'));
 let reads=0;const parameters={};Object.defineProperty(parameters,'bad',{enumerable:true,get(){reads++;return 'bad';}});assert.throws(()=>compiled([binding('getter','editor',{parameters})]),code('parameter-json'));assert.equal(reads,0);
});
test('declarative defaults and run override accessors reject before extracting any parameter layer',()=>{
 let reads=0;const getter=()=>{reads++;return {};},safeFailure=error=>['parameter-json','binding-definition'].includes(error.code);
 const defaults={};Object.defineProperty(defaults,'editor',{enumerable:true,get:getter});assert.throws(()=>compiled([binding('a')],{parameterDefaults:defaults}),safeFailure);
 const layer={};Object.defineProperty(layer,'project',{enumerable:true,get:getter});assert.throws(()=>compiled([binding('a')],{parameterDefaults:{editor:layer}}),safeFailure);
 const overrides={};Object.defineProperty(overrides,'a',{enumerable:true,get:getter});assert.throws(()=>compiled([binding('a')],{runOverrides:overrides}),safeFailure);
 const options={packages,catalog:trustedCatalog()};Object.defineProperty(options,'parameterDefaults',{get:getter});assert.throws(()=>api.compileBindings([binding('a')],options),safeFailure);assert.equal(reads,0);
});
test('typed task-free contexts preserve request project document snapshot management and controller scopes',()=>{
 const contexts=[{kind:'request',id:'request-1'},{kind:'project',id:'project-1'},{kind:'document',id:'document-1',paths:['README.md']},{kind:'snapshot',id:'snapshot-1',paths:['docs/spec.md']},{kind:'management',id:'management-1'},{kind:'controller',id:'controller-1',run_id:run}];
 for(const context of contexts){const before=JSON.stringify(context),normalized=api.validateContext(context);assert.deepEqual(normalized,context);assert.equal(normalized.task_ids,undefined);assert.equal(normalized.pending_ids,undefined);assert.equal(JSON.stringify(context),before);}
});
test('real pending task group and review contexts reject fabricated identity shapes',()=>{
 assert.deepEqual(api.validateContext({kind:'pending',id:'pending-1',pending_ids:[pending]}).pending_ids,[pending]);assert.deepEqual(api.validateContext({kind:'task-group',id:'group-1',task_ids:[task]}).task_ids,[task]);
 assert.equal(api.validateContext({kind:'review',id:'review-1',head:'a'.repeat(40),base_oid:'b'.repeat(40)}).head,'a'.repeat(40));
 assert.throws(()=>api.validateContext({kind:'pending',id:'wrong',pending_ids:[task]}),code('binding-context'));assert.throws(()=>api.validateContext({kind:'task',id:'wrong',task_ids:['fabricated']}),code('binding-context'));assert.throws(()=>api.validateContext({kind:'document',id:'wrong',paths:['../outside']}),code('binding-context'));
});
test('pre-promotion and task-free dispatch use compatible typed contexts without manufacturing tasks',()=>{
 const boundaries={[processOp+':before']:{operation:processOp,version:'1',context_kinds:['pending'],handler:()=>{}},[processOp+':after']:{operation:processOp,version:'1',context_kinds:['task','task-group'],handler:()=>{}}},catalog=api.createAnchorCatalog(operations,{boundaries}),result=compiled([binding('before','editor',{anchor:'before'})],{catalog});
 const good=api.selectBindings(result,event(processOp,'before'),{kind:'pending',id:'selection',pending_ids:[pending]});assert.equal(good.bindings.length,1);assert.equal(good.context.task_ids,undefined);
 const wrong=api.selectBindings(result,event(processOp,'before'),taskContext());assert.equal(wrong.bindings.length,0);assert.equal(wrong.unresolved[0].id,'before');assert.match(wrong.unresolved[0].reason,/context/i);
});
test('unresolved named locations remain visible instead of appearing in an executable selection',()=>{
 const result=compiled([binding('custom','editor',{anchor:'not-registered'})]),selected=api.selectBindings(result,event(processOp,'not-registered'),taskContext());assert.equal(selected.bindings.length,0);assert.equal(selected.unresolved.length,1);assert.equal(selected.unresolved[0].id,'custom');assert.match(selected.unresolved[0].reason,/anchor|boundary|registered/i);
});
test('catalog and sequence identities change with order parameters conditions and named-boundary versions',()=>{
 const rows=[binding('a'),binding('b','interview')],base=compiled(rows).configuration_digest;assert.match(base,/^[a-f0-9]{64}$/);assert.notEqual(base,compiled([...rows].reverse()).configuration_digest);assert.notEqual(base,compiled([binding('a','editor',{parameters:{tone:'changed'}}),rows[1]]).configuration_digest);assert.notEqual(base,compiled([binding('a','editor',{condition:false}),rows[1]]).configuration_digest);
 const boundary=version=>api.createAnchorCatalog(operations,{boundaries:{plan:{operation:implementOp,version,context_kinds:['task'],handler:()=>{}}},named:[{operation:implementOp,name:'plan-check',boundary:'plan'}]});assert.notEqual(boundary('1').digest,boundary('2').digest);
});
test('configuration identity includes independent enabled instruction and run override values',()=>{
 const base=compiled([binding('a')]).configuration_digest;
 assert.notEqual(base,compiled([binding('a','editor',{enabled:false})]).configuration_digest);
 assert.notEqual(base,compiled([binding('a','editor',{instructions:'Different bounded instruction'})]).configuration_digest);
 assert.notEqual(base,compiled([binding('a')],{runOverrides:{a:{values:{marker:'run-value'}}}}).configuration_digest);
});
test('mixed operation and anchor bindings select only the actual boundary in preserved order',()=>{
 const result=compiled([binding('before','editor',{anchor:'before'}),binding('a'),binding('other-op','editor',{operation:implementOp}),binding('c')]);
 assert.deepEqual(api.selectBindings(result,event(),taskContext()).bindings.map(row=>row.id),['a','c']);
 assert.deepEqual(api.selectBindings(result,event(processOp,'before'),taskContext()).bindings.map(row=>row.id),['before']);
});
test('named aliases of one actual boundary select and produce identities with the returned boundary event',()=>{
 const catalog=trustedCatalog({named:[{operation:processOp,name:'after-editorial',boundary:processOp+':after'}]}),result=compiled([binding('alias','editor',{anchor:'after-editorial'}),binding('ordinary')],{catalog}),selected=api.selectBindings(result,event(),taskContext());
 assert.deepEqual(selected.bindings.map(row=>row.id),['alias','ordinary']);assert.equal(selected.event.boundary_id,processOp+':after');
 const identities=selected.bindings.map(row=>api.dispatchIdentity(row,selected.event,selected.context,{configuration_digest:result.configuration_digest}));
 assert.equal(identities[0].boundary_id,identities[1].boundary_id);assert.notEqual(identities[0].delivery_key,identities[1].delivery_key);
 const reconfigured=compiled([binding('alias')],{catalog}),actual=api.selectBindings(reconfigured,event(),taskContext()),sameOccurrence=api.dispatchIdentity(actual.bindings[0],actual.event,actual.context,{configuration_digest:reconfigured.configuration_digest});assert.equal(identities[0].delivery_key,sameOccurrence.delivery_key);assert.notEqual(identities[0].input_digest,sameOccurrence.input_digest);
 assert.throws(()=>api.dispatchIdentity(selected.bindings[0],{...selected.event,anchor:'before'},selected.context),code('binding-event'));
 assert.throws(()=>api.selectBindings(result,{...event(),boundary_id:'forged-other-boundary'},taskContext()),code('binding-event'));
});
test('cross-operation boundary ownership and serialized handler metadata cannot invent callable locations',()=>{
 const cross=api.createAnchorCatalog(operations,{boundaries:{foreign:{operation:implementOp,version:'1',context_kinds:['task'],handler:()=>{}}},named:[{operation:processOp,name:'wrong-owner',boundary:'foreign'}]});assert.equal(api.resolveLocation({operation:processOp,anchor:'wrong-owner'},cross).status,'unresolved');
 const serialized=JSON.parse(JSON.stringify(trustedCatalog()));assert.equal(api.resolveLocation({operation:processOp,anchor:'after'},serialized).status,'unresolved');assert.throws(()=>compiled([binding('a')],{catalog:serialized}),code('binding-anchor'));
 const strings=api.createAnchorCatalog(operations,{boundaries:{[processOp+':after']:{operation:processOp,version:'1',context_kinds:['task'],handler:'function(){}'}}});assert.equal(api.resolveLocation({operation:processOp,anchor:'after'},strings).status,'unresolved');
});
test('catalog metadata and compiled sequence data cannot mutate behind current configuration identities',()=>{
 const catalog=trustedCatalog(),result=compiled([binding('a','editor',{parameters:{nested:{value:1}}}),binding('b','interview')],{catalog});
 assert.throws(()=>{catalog.boundaries[processOp+':after'].handler=()=>{};},TypeError);assert.throws(()=>{catalog.boundaries[processOp+':after'].version='changed';},TypeError);assert.throws(()=>catalog.boundaries[processOp+':after'].context_kinds.push('unknown'),TypeError);
 assert.throws(()=>result.bindings.reverse(),TypeError);assert.throws(()=>{result.bindings[0].effective.values.nested.value=2;},TypeError);
 assert.throws(()=>api.selectBindings(JSON.parse(JSON.stringify(result)),event(),taskContext()),code('binding-definition'));
});
test('context forms reject empty duplicate nonapplicable task identities and Windows paths',()=>{
 for(const context of [{kind:'task-group',id:'empty',task_ids:[]},{kind:'task-group',id:'duplicate',task_ids:[task,task]},{kind:'pending',id:'duplicate',pending_ids:[pending,pending]},{kind:'document',id:'windows',paths:['C:/private/spec.md']},{kind:'request',id:'not-task',task_ids:[task]},{kind:'management',id:'not-pending',pending_ids:[pending]}])assert.throws(()=>api.validateContext(context),code('binding-context'));
});
test('condition presence distinguishes null false and missing without inherited-field or accessor evaluation',()=>{
 const result=compiled([binding('null-present','editor',{condition:{present:'/values/nullable'}}),binding('false-present','editor',{condition:{present:'/values/disabled'}}),binding('missing','editor',{condition:{present:'/values/missing'}}),binding('inherited','editor',{condition:{present:'/values/toString'}})]),context={...taskContext(),values:{nullable:null,disabled:false}};
 assert.deepEqual(api.selectBindings(result,event(),context).bindings.map(row=>row.id),['null-present','false-present']);
 let reads=0;const condition={};Object.defineProperty(condition,'present',{enumerable:true,get(){reads++;return '/kind';}});assert.throws(()=>compiled([binding('getter','editor',{condition})]),code('parameter-json'));assert.equal(reads,0);
});
test('core authority and context fields cannot be supplied as binding-level plugin data',()=>{
 assert.throws(()=>compiled([binding('authority','editor',{authority:{merge:true}})]),code('binding-definition'));assert.throws(()=>compiled([binding('context','editor',{context:taskContext()})]),code('binding-definition'));
});
test('delivery identity distinguishes repeated occurrences controller leaf and explicit attempts',()=>{
 const context=taskContext(),a=api.dispatchIdentity(binding('a'),event(),context,{configuration_digest:'1',parameters:{value:1}}),same=api.dispatchIdentity(binding('a'),event(),context,{configuration_digest:'1',parameters:{value:1}}),c=api.dispatchIdentity(binding('c'),event(),context,{configuration_digest:'1',parameters:{value:1}});
 assert.match(a.delivery_key,/^[a-f0-9]{64}$/);assert.equal(a.delivery_key,same.delivery_key);assert.notEqual(a.delivery_key,c.delivery_key);
 const controller=api.dispatchIdentity(binding('controller','editor',{operation:controllerOp}),event(controllerOp),{kind:'controller',id:'run-context',run_id:run},{configuration_digest:'1'});assert.notEqual(a.delivery_key,controller.delivery_key);assert.notEqual(a.delivery_key,api.dispatchIdentity(binding('a'),event(processOp,'after',{attempt_id:'another-attempt'}),context,{configuration_digest:'1'}).delivery_key);
});
test('same delivery with changed inputs conflicts while exact duplicate delivery is classified without executing anything',()=>{
 const a=api.dispatchIdentity(binding('a'),event(),taskContext(),{configuration_digest:'one',parameters:{marker:'one'}}),changed=api.dispatchIdentity(binding('a'),event(),taskContext(),{configuration_digest:'two',parameters:{marker:'two'}});assert.match(a.input_digest,/^[a-f0-9]{64}$/);assert.equal(a.delivery_key,changed.delivery_key);assert.notEqual(a.input_digest,changed.input_digest);assert.equal(api.classifyDelivery(a), 'new');assert.equal(api.classifyDelivery(a,a),'replay');assert.throws(()=>api.classifyDelivery(changed,a),code('binding-replay'));
});
test('context-only drift changes input identity while mismatched operation and boundary events reject',()=>{
 const first=api.dispatchIdentity(binding('a'),event(),taskContext(),{configuration_digest:'same'}),changed=api.dispatchIdentity(binding('a'),event(),{...taskContext(),changed_files:['other.js']},{configuration_digest:'same'});assert.equal(first.delivery_key,changed.delivery_key);assert.notEqual(first.input_digest,changed.input_digest);
 assert.throws(()=>api.dispatchIdentity(binding('a'),event(implementOp),taskContext()),code('binding-event'));assert.throws(()=>api.dispatchIdentity(binding('a'),event(processOp,'before'),taskContext()),code('binding-event'));
});
test('active lineage rejects real occurrence re-entry but finite A B A plugin sequences remain valid',()=>{
 const a=api.dispatchIdentity(binding('a'),event(),taskContext(),{configuration_digest:'one'}),b=api.dispatchIdentity(binding('b','interview'),event(),taskContext(),{configuration_digest:'one'}),c=api.dispatchIdentity(binding('c'),event(),taskContext(),{configuration_digest:'one'}),line=api.enterLineage(api.enterLineage([],a),b);assert.equal(line.length,2);assert.equal(api.enterLineage(line,c).length,3);assert.throws(()=>api.enterLineage(line,a),code('binding-recursion'));const reentered={...a,delivery_key:'other-delivery'};assert.throws(()=>api.enterLineage(line,reentered),code('binding-recursion'));assert.equal(line.length,2);
});
test('copied binding modules work without source checkout sibling skills or implicit project metadata',t=>{
 const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-bindings-standalone-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
 for(const file of ['plugin-bindings.js','plugin-parameters.js'])fs.copyFileSync(path.join(__dirname,'../lib',file),path.join(root,file));
 const script="const assert=require('node:assert/strict'),a=require('./plugin-bindings.js');const op='skill-tree-plugins',catalog=a.createAnchorCatalog({[op]:{title:'Plugins'}},{boundaries:{[op+':after']:{operation:op,version:'1',context_kinds:['management'],handler(){}}}});const c=a.compileBindings([{id:'one',plugin_id:'custom',operation:op,anchor:'after',enabled:true},{id:'two',plugin_id:'custom',operation:op,anchor:'after',enabled:true}],{packages:{custom:{id:'custom'}},catalog});assert.equal(a.selectBindings(c,{id:'event',operation:op,anchor:'after'},{kind:'management',id:'proposal'}).bindings.length,2);";
 const result=spawnSync(process.execPath,['-e',script],{cwd:root,encoding:'utf8',timeout:10000});assert.equal(result.status,0,result.stdout+result.stderr);assert.deepEqual(fs.readdirSync(root).sort(),['plugin-bindings.js','plugin-parameters.js']);
});
