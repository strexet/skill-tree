'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),{spawnSync}=require('node:child_process');
const registry=require('./plugin-registry.js'),bindings=require('./plugin-bindings.js'),parameters=require('./plugin-parameters.js'),sources=require('./plugin-sources.js');
const own=(value,key)=>Object.hasOwn(value,key),object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const clone=value=>parameters.resolveParameters({run:{values:value}}).values;
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
const kinds=['request','project','document','snapshot','management','controller','pending','task','task-group','review'],phases=['before','during','after'];
const MANIFEST='references/plugin-bindings.json',VERSION=hash(fs.readFileSync(__filename));
const processOperation='skill-tree-process-future-pending',implementOperation='skill-tree-implement-next-future-task';
const hasProcessingRecheck=context=>object(context)&&(own(context,'processing_recheck_id')||own(context,'processing_recheck_digest'));
const namedDefaults={
 'skill-tree-process-future-pending':{'before-research':'before','before-task-formulation':'during','after-task-creation':'after'},
 'skill-tree-implement-next-future-task':{'before-research':'before','after-draft-plan':'during','before-task-completion':'after'},
 'skill-tree-repo-documentation':{'before-research':'before','before-formulation':'during','after-validation':'after'},
 'skill-tree-repo-documentation-audit':{'before-research':'before','before-formulation':'during','after-validation':'after'},
 'skill-tree-pr-review-cycle':{'before-review':'before','after-core-inspection':'during','before-pr-ready':'after'}
};
function fail(code,message){const error=Error(message);error.code=code;throw error;}
function readJson(root,relative){return JSON.parse(fs.readFileSync(registry.safe(root,relative),'utf8').replace(/^\uFEFF/,''));}
function specs(operations){
 if(!object(operations))fail('composition-operation','An owned operation catalog is required');
 return Object.fromEntries(Object.keys(operations).sort().map(name=>{const op=operations[name];if(!object(op))fail('composition-operation','An owned operation requires a definition');return [name,{title:typeof op.title==='string'?op.title:name,...(own(op,'plugin_anchors')?{plugin_anchors:clone(op.plugin_anchors)}:{})}];}));
}
function createCatalog(operations,version=VERSION){
 const declared=specs(operations),boundaries={},named=[],aliases=[];
 for(const operation of Object.keys(declared)){
  for(const phase of phases)boundaries[operation+':'+phase]={operation,version,context_kinds:kinds,handler:request=>guardBoundary(request.package_root,request,operation,phase)};
  const locations={...(namedDefaults[operation]||{})},extra=declared[operation].plugin_anchors||{};
  if(!object(extra))fail('composition-anchor','Owned named anchors require a name-to-phase map');
  for(const [name,phase]of Object.entries(extra)){if(!registry.validId(name)||!phases.includes(phase)||phases.includes(name)||own(locations,name)&&locations[name]!==phase)fail('composition-anchor','A named anchor must map to an unchanged actual owned phase');locations[name]=phase;}
  for(const [name,phase]of Object.entries(locations)){named.push({operation,name,boundary:operation+':'+phase});aliases.push({phrase:name+' '+operation,operation,anchor:name});}
 }
 return bindings.createAnchorCatalog(declared,{boundaries,named,aliases});
}
function portableCatalog(catalog){return {operations:catalog.operations,entries:catalog.entries,aliases:catalog.aliases,digest:catalog.digest};}
function defaults(packages){return Object.fromEntries(Object.entries(packages).filter(([,record])=>own(record.adaptation||{},'parameter_defaults')).map(([id,record])=>[id,clone(record.adaptation.parameter_defaults)]));}
function resolveInputs(root,operations,version){
 if(fs.existsSync(registry.safe(root,'.skill-tree/installation/.plugin-journal.json')))fail('composition-transaction','Plugin transaction recovery remains required before composition');
 const value=registry.verifyInstalled(root),catalog=createCatalog(operations,version),compiled=bindings.compileBindings(value.bindings,{packages:value.packages,catalog,parameterDefaults:defaults(value.packages)});
 return {format:'skill-tree-plugin-composition-inputs',schema:1,registry_present:fs.existsSync(registry.safe(root,registry.REGISTRY)),registry_identity:value.identity,configuration_digest:compiled.configuration_digest,operations:specs(operations),definitions:clone(value.bindings),packages:clone(value.packages),parameter_defaults:defaults(value.packages),catalog:portableCatalog(catalog),unresolved:compiled.bindings.filter(row=>row.location.status!=='resolved').map(row=>({id:row.id,operation:row.operation,anchor:row.anchor,reason:row.location.reason}))};
}
function packageClosure(packages,selected){
 const result=new Set();
 function visit(id){if(result.has(id))return;if(!own(packages,id))fail('composition-package','An installed plugin dependency is missing');result.add(id);for(const dependency of packages[id].package_dependencies)visit(dependency);}
 for(const id of selected)visit(id);return [...result].sort();
}
function composeOperation(source,profile,operation,ownedFiles){
 if(!object(ownedFiles))fail('composition-resource','Composition requires the actual composed owned resource closure');
 const ownedResources=Object.fromEntries(Object.entries(ownedFiles).map(([relative,content])=>{registry.relative(relative);if(relative===MANIFEST||relative.startsWith('plugins/')||typeof content!=='string'&&!Buffer.isBuffer(content))fail('composition-resource','An owned composition resource is invalid or conflicts with plugin resources');return [relative,hash(content)];}));
 const operations=readJson(source,'templates/operations.json');
 if(!own(operations,operation))fail('composition-operation','The selected operation is not registered');
 const version=hash(fs.readFileSync(registry.safe(source,'lib/plugin-composition.js')));
 const current=resolveInputs(profile.project_root,operations,version);
 if(!profile.plugins||registry.json(current)!==registry.json(profile.plugins))fail('composition-stale','Plugin inputs changed; explicitly refresh the frozen profile before composition');
 const definitions=current.definitions.filter(row=>row.operation===operation),ids=packageClosure(current.packages,definitions.map(row=>row.plugin_id)),packages={},files={};
 for(const id of ids){
  const record=current.packages[id],base='plugins/'+id,inventory={};
  for(const [relative,sum]of Object.entries(record.files)){const destination=base+'/'+relative,bytes=fs.readFileSync(registry.safe(profile.project_root,record.destination+'/'+relative));if(hash(bytes)!==sum)fail('composition-resource','An owned plugin resource changed during composition');files[destination]=bytes;inventory[destination]=sum;}
  packages[id]={...clone(record),destination:base,entry:base+'/'+record.entry,files:inventory};
 }
 const parameterDefaults=Object.fromEntries(ids.filter(id=>own(current.parameter_defaults,id)).map(id=>[id,current.parameter_defaults[id]]));
 const catalog=createCatalog(operations,version),compiled=bindings.compileBindings(definitions,{packages,catalog,parameterDefaults});
 const manifest=registry.seal({format:'skill-tree-plugin-bindings',schema:1,operation,owned_resources:ownedResources,operations:current.operations,registry_present:current.registry_present,registry_identity:current.registry_identity,configuration_digest:compiled.configuration_digest,definitions,bindings:clone(compiled.bindings),packages,parameter_defaults:parameterDefaults,catalog:portableCatalog(catalog)});
 files[MANIFEST]=registry.json(manifest);return {files,manifest};
}
const requiredHelpers=['plugin-hooks.js','plugin-runtime.js','plugin-invocation.py','plugin-composition.js','plugin-bindings.js','plugin-parameters.js','plugin-registry.js','plugin-sources.js','workflow-state.py','decision-governance.py','decision-orchestration.py','run-workspaces.py','validate-document-rules.py'];
function verifyOwnedResources(packageRoot,inventory){
 if(!object(inventory)||requiredHelpers.some(name=>!own(inventory,'scripts/'+name)))fail('composition-resource','The actual owned dispatcher helper closure is missing');
 for(const [relative,sum]of Object.entries(inventory)){
  registry.relative(relative);if(relative===MANIFEST||relative.startsWith('plugins/')||typeof sum!=='string'||!/^[a-f0-9]{64}$/.test(sum))fail('composition-resource','The owned dispatcher resource inventory is invalid');
  const file=registry.safe(packageRoot,relative);if(!fs.existsSync(file)||!fs.statSync(file).isFile()||hash(fs.readFileSync(file))!==sum)fail('composition-resource','An owned dispatcher resource changed or is missing: '+relative);
 }
 const actual={};function visit(directory,prefix){for(const entry of fs.readdirSync(directory,{withFileTypes:true})){if(entry.name==='__pycache__'||prefix===''&&entry.name==='plugins')continue;const relative=prefix+entry.name;if(relative===MANIFEST)continue;if(entry.isSymbolicLink())fail('composition-resource','An owned dispatcher resource became a symlink');if(entry.isDirectory())visit(path.join(directory,entry.name),relative+'/');else if(entry.isFile())actual[relative]=hash(fs.readFileSync(path.join(directory,entry.name)));else fail('composition-resource','An owned dispatcher resource has an unsupported entry');}}visit(packageRoot,'');
 if(registry.json(actual)!==registry.json(inventory))fail('composition-resource','The actual owned dispatcher resource closure changed');
}
function verifiedManifest(packageRoot){
 const manifestBytes=fs.readFileSync(registry.safe(packageRoot,MANIFEST)),manifest=JSON.parse(manifestBytes.toString('utf8').replace(/^\uFEFF/,''));
 if(!object(manifest)||manifest.format!=='skill-tree-plugin-bindings'||manifest.schema!==1||manifest.identity!==registry.seal(manifest).identity||!object(manifest.operations)||!own(manifest.operations,manifest.operation)||!object(manifest.packages))fail('composition-manifest','The local plugin manifest is invalid or changed');
 verifyOwnedResources(packageRoot,manifest.owned_resources);
 const actual=fs.existsSync(registry.safe(packageRoot,'plugins'))?fs.readdirSync(registry.safe(packageRoot,'plugins')).sort():[];
 if(registry.json(actual)!==registry.json(Object.keys(manifest.packages).sort()))fail('composition-resource','The local plugin package inventory changed');
 for(const [id,record]of Object.entries(manifest.packages)){
  if(!registry.validId(id)||record.id!==id||record.destination!=='plugins/'+id||!object(record.snapshot)||!object(record.snapshot.digests)||record.snapshot.plugin_id!==id||record.entry!==record.destination+'/upstream/'+record.snapshot.entry||!object(record.files)||!own(record.files,record.entry)||!Array.isArray(record.package_dependencies)||record.package_dependencies.some(dependency=>dependency===id||!own(manifest.packages,dependency)))fail('composition-resource','The local plugin resource ownership changed');
  const expected=Object.fromEntries(Object.entries(record.files).map(([relative,sum])=>{registry.relative(relative);if(!relative.startsWith(record.destination+'/'))fail('composition-resource','A local plugin resource escapes the package');return [relative.slice(record.destination.length+1),sum];}));
  if(registry.json(registry.filesAt(packageRoot,record.destination))!==registry.json(expected))fail('composition-resource','The local plugin resource inventory or bytes changed');
  if(record.content_digest!==record.snapshot?.content_digest||record.revision!==record.snapshot?.revision||registry.json(record.source)!==registry.json(record.snapshot?.source)||registry.json(record.metadata)!==registry.json(record.snapshot?.metadata)||registry.json(record.adaptation)!==registry.json(record.snapshot?.adaptation)||registry.json(record.execution)!==registry.json(record.snapshot?.execution))fail('composition-resource','The local source snapshot identity changed');
  const inventory={...Object.fromEntries(Object.entries(record.snapshot.digests).map(([relative,sum])=>['upstream/'+registry.relative(relative),sum])),'overlay/adapter.json':hash(registry.json(record.adaptation))};
  if(registry.json(inventory)!==registry.json(expected))fail('composition-resource','The declared local resources differ from the inspected snapshot');
  const original=Object.fromEntries(Object.keys(record.snapshot.digests).map(relative=>[relative,fs.readFileSync(registry.safe(packageRoot,record.destination+'/upstream/'+registry.relative(relative)))]));sources.verifySnapshot({...record.snapshot,files:original});
 }
 const catalog=createCatalog(manifest.operations),compiled=bindings.compileBindings(manifest.definitions,{packages:manifest.packages,catalog,parameterDefaults:manifest.parameter_defaults});
 if(registry.json(portableCatalog(catalog))!==registry.json(manifest.catalog)||compiled.configuration_digest!==manifest.configuration_digest||registry.json(compiled.bindings)!==registry.json(manifest.bindings))fail('composition-manifest','The local binding configuration or owned boundary catalog changed');
 return {manifest,catalog,compiled,manifest_digest:hash(manifestBytes)};
}
function projectRelative(value,root){const relative=path.relative(root,value);return relative&&!path.isAbsolute(relative)&&relative!=='..'&&!relative.startsWith('..'+path.sep)?relative.split(path.sep).join('/'):null;}
function associatedInstallation(packageRoot,projectRoot,verified){
 const project=fs.realpathSync(projectRoot),actualPackage=fs.realpathSync(packageRoot),candidates=new Set();
 // Retain the invoked path before realpath removes a conflicting owned symlink.
 for(const [base,value]of [[path.resolve(projectRoot),path.resolve(packageRoot)],[project,actualPackage]]){const relative=projectRelative(value,base);if(relative)candidates.add(relative);}
 let ancestor=path.resolve(packageRoot);
 while(true){try{if(fs.realpathSync(ancestor)===project){const relative=projectRelative(path.resolve(packageRoot),ancestor);if(relative)candidates.add(relative);}}catch{}const parent=path.dirname(ancestor);if(parent===ancestor)break;ancestor=parent;}
 if(!candidates.size)return false;
 const profilePath=registry.safe(project,'.skill-tree/installation/profile.json');if(!fs.existsSync(profilePath))return false;
 let profile;try{profile=JSON.parse(fs.readFileSync(profilePath,'utf8').replace(/^\uFEFF/,''));}catch{fail('composition-ownership','The relevant owned profile is unreadable; explicit ownership recovery remains required');}
 if(!object(profile)||!object(profile.destinations))fail('composition-ownership','The relevant ownership profile has no verifiable destination claims');
 const claims=[...candidates].filter(relative=>own(profile.destinations,relative));if(!claims.length)return false;
 if(profile.format!=='skill-tree-profile'||profile.schema!==1||profile.project_root!==project||typeof profile.flavor!=='string'||typeof profile.environment_id!=='string'||!object(profile.source_digests))fail('composition-ownership','The relevant ownership profile is unsupported or belongs to another project');
 const records=Object.values(profile.destinations);for(const record of records)if(!object(record)||typeof record.name!=='string'||!object(record.files))fail('composition-ownership','The ownership receipt composition inventory is invalid');
 const outputs=Object.fromEntries(records.map(record=>[record.name,record.files]));
 if(profile.identity!==hash(registry.json({flavor:profile.flavor,environment_id:profile.environment_id,source_digests:profile.source_digests,output_digests:outputs})))fail('composition-ownership','The relevant ownership receipt composition identity changed');
 const {manifest,manifest_digest}=verified,inventory={...manifest.owned_resources,[MANIFEST]:manifest_digest};
 for(const record of Object.values(manifest.packages))Object.assign(inventory,record.files);
 for(const relative of claims){
  const record=profile.destinations[relative];let destination;try{destination=registry.safe(project,relative);}catch(error){fail('composition-ownership','The exact operation ownership claim is unsafe: '+error.message);}
  if(fs.realpathSync(destination)!==actualPackage||record.name!==manifest.operation||path.posix.basename(relative)!==record.name||!/^skill-tree-[a-z0-9-]+$/.test(record.name)||record.flavor!==profile.flavor||record.identity!==hash(registry.json(record.files))||registry.json(record.files)!==registry.json(inventory))fail('composition-ownership','The exact operation ownership receipt or complete resource inventory changed');
 }
 return true;
}
function installationPrerequisites(packageRoot,projectRoot,verified){
 const associated=associatedInstallation(packageRoot,projectRoot,verified);
 const liveRegistry=registry.safe(projectRoot,registry.REGISTRY);
 if(fs.existsSync(liveRegistry)){
  const current=registry.verifyInstalled(projectRoot);
  if(current.identity!==verified.manifest.registry_identity){
   return [{code:'configuration-stale',reason:'The live plugin generation differs from the frozen operation; explicit refresh and parked-run reconciliation remain required.'}];
  }
 }else if(associated&&verified.manifest.registry_present){
  return [{code:'registry-required',reason:'The associated managed operation requires the frozen live plugin registry; explicit registry recovery remains required.'}];
 }
 return [];
}
const guardProgram=String.raw`import hashlib,importlib.util,json,sys
from pathlib import Path
sys.pycache_prefix=sys.argv[2]
spec=importlib.util.spec_from_file_location('owned_plugin_workflow',sys.argv[1]);w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
p=json.load(sys.stdin);root=Path(p['project_root']);s=w.Store(root,allow_unselected=True,neutral=True);context=p['context'];phase=p['phase'];operation=p['operation'];watched={}
def capture(path):
 path=Path(path);value=path.read_bytes() if path.exists() else None;watched[path]=value;return value
for base in {s.base,root/'.skill-tree'}:
 if any((base/relative).exists() for relative in ['.writer-lock','.transaction.json','installation/.install-lock','installation/.journal.json','installation/.plugin-journal.json']):raise ValueError('The current owned workflow or installation transaction must finish before plugin boundary preparation')
def processing_recheck():
 capture(s.future)
 capture(w.clarification_path(s,context.get('session_id')))
 return w.processing_recheck_guard(s,context,p['event'],readiness=p['processing_readiness'])
def finish(proof):
 for path,previous in watched.items():
  if (path.read_bytes() if path.exists() else None)!=previous:raise ValueError('The actual selected workflow context changed during boundary preparation')
 print(json.dumps(proof))
if p['processing_readiness']:
 finish({'kind':'actual-owned-scope','processing_recheck':processing_recheck()})
 sys.exit(0)
if operation=='skill-tree-process-future-pending':
 if phase in {'before','during'} and context['kind']!='pending':raise ValueError('Processing before and during require the actual selected Pending context')
 if phase=='after' and context['kind'] not in {'task','task-group'}:raise ValueError('Processing after requires the actual created task context')
if operation=='skill-tree-implement-next-future-task' and context['kind'] not in {'task','task-group'}:raise ValueError('Implementation requires the actual selected task context')
if context['kind'] in {'pending','task','task-group'}:
 capture(s.future);tasks=w.parse(s.text());key='pending_ids' if context['kind']=='pending' else 'task_ids';queue='Pending Queue' if key=='pending_ids' else 'Prioritized Next Changes';selected=w.resolve(tasks,context[key],queue)
 if key=='task_ids' and set(context.get('pending_ids',[]))-{value for task in selected for value in task['parent_pending_ids']}:raise ValueError('Task context Pending provenance differs from actual selected tasks')
 if operation=='skill-tree-implement-next-future-task' and any(task['status']!='Ready' for task in selected):raise ValueError('Blocked selected tasks cannot enter implementation')
 if operation=='skill-tree-process-future-pending' and phase=='after':
  w.processing_scope_guard(s,context,package_root=p['package_root'])
if context['kind']=='controller':
 capture(s.future);capture(s.state);state=s.load();runs=state.get('run_registry',{}).get('runs',{})
 if state.get('active_run'):runs={**runs,state['active_run']['id']:state['active_run']}
 run=runs.get(context['run_id'])
 if not run or set(context.get('task_ids',[]))-set(run.get('admitted_task_ids',run.get('snapshot',[]))+run.get('required_ids',[])):raise ValueError('The controller context exceeds the actual recorded run scope')
proof={'kind':'actual-owned-scope'}
if 'processing_recheck_id' in context:
 proof['processing_recheck']=processing_recheck()
if operation=='skill-tree-pr-review-cycle' and 'publication_id' in context:
 review=w.owned_module('owned_plugin_review',Path(sys.argv[1]).with_name('pr-review-state.py'))
 publication=review._review_path(s,context['publication_id']);original=capture(publication)
 frontier=review.review_phase_guard(s,context,phase)
 if original is None or frontier.get('publication_hash')!=hashlib.sha256(original).hexdigest():raise ValueError('The actual publication changed during review phase preparation')
 proof.update(frontier)
if operation=='skill-tree-implement-next-future-task' and phase=='during':
 identity=p.get('orchestration_id')
 if not identity:raise ValueError('Implementation During requires the current actual draft-plan orchestration frame')
 frame_path=s.base/'decisions'/(identity.lower()+'.json');capture(frame_path);frame=w.orchestration_action(s,'orchestration-read',{'orchestration_id':identity});w.orchestration_action(s,'orchestration-next',{'orchestration_id':identity})
 if frame['phase']!='plan-review' or not frame['plan'] or frame['plan_acceptance'] is not None:raise ValueError('Implementation During requires a draft plan before current plan acceptance')
 for key in ['kind','id','task_ids','pending_ids','semantic_fingerprint','content_fingerprint']:
  if context.get(key)!=frame['context'].get(key):raise ValueError('The draft-plan frame belongs to another selected task scope or context')
 proof.update(orchestration_id=identity,orchestration_hash=frame['orchestration_hash'],plan_digest=frame['plan']['digest'])
finish(proof)`;
function guardBoundary(packageRoot,request,operation,phase,processingReadiness=false){
 if(typeof request.project_root!=='string'||!fs.existsSync(request.project_root)||!fs.statSync(request.project_root).isDirectory())fail('composition-context','An explicit existing execution project root is required');
 const context=bindings.validateContext(request.context),needsWorkflow=['pending','task','task-group','controller'].includes(context.kind)||operation===processOperation||operation===implementOperation||operation==='skill-tree-pr-review-cycle'&&own(context,'publication_id');
 if(!needsWorkflow)return {kind:'task-free',context_kind:context.kind};
 const helper=registry.safe(packageRoot,'scripts/workflow-state.py');
 if(!fs.existsSync(helper))fail('composition-context','The local owned workflow helper closure is missing');
 const cachePrefix=path.join(os.tmpdir(),'skill-tree-owned-source-'+crypto.randomUUID());
 if(fs.existsSync(cachePrefix))fail('composition-context','A fresh nonexistent bytecode lookup prefix is required');
 const ownedRequest={...request,operation,phase,context,package_root:packageRoot,processing_readiness:processingReadiness};
 const run=spawnSync('python3',['-I','-B','-c',guardProgram,helper,cachePrefix],{
  input:JSON.stringify(ownedRequest),encoding:'utf8',timeout:10000,maxBuffer:1024*1024
 });
 if(run.error||run.status!==0)fail('composition-context','The actual selected operation context guard failed: '+(run.stderr||run.stdout||run.error?.message||'The owned helper is unavailable').trim().split('\n').at(-1));
 return JSON.parse(run.stdout);
}
function prepareMetadata(packageRoot,payload,readiness){
 const request=clone(payload),verified=verifiedManifest(packageRoot),{manifest,catalog,compiled}=verified;
 if(request.event?.operation!==manifest.operation)fail('composition-operation','The event must identify the actual composed operation');
 const location=bindings.resolveLocation(request.event,catalog),prerequisites=[];
 let recheckGuard=null;
 if(hasProcessingRecheck(request.context)){
  if(location.status!=='resolved'||location.boundary_id!==processOperation+':after')fail('composition-context','An editorial recheck requires the actual Processing after boundary');
  const {processing_recheck_id:id,processing_recheck_digest:mandate}=request.context;
  if(typeof id!=='string'||!id.trim()||typeof mandate!=='string'||!/^[a-f0-9]{64}$/.test(mandate))fail('composition-context','An editorial recheck requires the exact owned mandate identity');
  const [held]=installationPrerequisites(packageRoot,request.project_root,verified);
  if(held)fail(held.code,held.reason);
  recheckGuard=guardBoundary(packageRoot,{...request,event:{...request.event,boundary_id:location.boundary_id}},processOperation,'after',readiness);
  if(!object(recheckGuard.processing_recheck))fail('composition-context','The actual clarification must authorize the editorial recheck');
 }
 const eligibilityContext=readiness?recheckGuard?.processing_recheck?.selection_context??request.context:request.context;
 const selected=bindings.selectBindings(compiled,request.event,eligibilityContext);
 const configured=compiled.bindings.some(row=>row.enabled&&row.operation===request.event.operation&&(row.anchor===request.event.anchor||row.location.status==='resolved'&&location.status==='resolved'&&row.location.boundary_id===location.boundary_id));
 const base={bindings:selected.bindings,unresolved:selected.unresolved,prerequisites,event:selected.event,context:recheckGuard?bindings.validateContext(request.context):selected.context,configuration_digest:compiled.configuration_digest,boundary_id:location.boundary_id||null,invocation:'not-executed'};
 if(location.status!=='resolved'){prerequisites.push({code:'unresolved-anchor',reason:location.reason});return {...base,status:'prerequisite'};}
 if(!recheckGuard&&(!configured||!selected.bindings.length&&!selected.unresolved.length))return {...base,status:'noop'};
 if(!readiness&&manifest.operation==='skill-tree-pr-review-cycle'&&selected.bindings.some(row=>own(manifest.packages[row.plugin_id].adaptation||{},'invocation_policy'))&&!own(selected.context,'publication_id'))fail('composition-context','The policy-bound review invocation requires the actual owned publication identity');
 const proof=recheckGuard||(readiness?null:catalog.boundaries[location.boundary_id].handler({...request,package_root:packageRoot}));
 for(const item of selected.unresolved)prerequisites.push({code:'incompatible-binding',binding_id:item.id,reason:item.reason});
 if(!recheckGuard)prerequisites.push(...installationPrerequisites(packageRoot,request.project_root,verified));
 const available=request.capabilities||[];
 if(!Array.isArray(available)||available.some(value=>typeof value!=='string'))fail('composition-capability','Capabilities require explicit named host facts');
 for(const row of selected.bindings){const record=manifest.packages[row.plugin_id],missing=(record.execution?.required||[]).filter(value=>!available.includes(value));if(missing.length)prerequisites.push({code:'missing-capability',binding_id:row.id,plugin_id:row.plugin_id,missing});prerequisites.push({code:'invocation-unqualified',binding_id:row.id,plugin_id:row.plugin_id,reason:'The boundary is prepared only; persisted actual host invocation and result qualification remain required.'});}
 return {...base,guard:proof,status:prerequisites.length?'prerequisite':'noop'};
}
function prepareBoundary(packageRoot,payload){
 if(own(payload,'proof_kind')||own(payload,'readiness_kind'))fail('composition-proof','Completed readiness cannot supply business boundary preparation');
 return prepareMetadata(packageRoot,payload,false);
}
function prepareReadinessBoundary(packageRoot,payload){return {...prepareMetadata(packageRoot,payload,true),proof_kind:'completed-readiness'};}
module.exports={createCatalog,resolveInputs,composeOperation,prepareBoundary,prepareReadinessBoundary,verifiedManifest,hasProcessingRecheck};
