'use strict';
// Management calls load this module lazily; source and parameter calls stay independent.
const fs=require('node:fs'),path=require('node:path');
const registry=require('./plugin-registry.js'),parameters=require('./plugin-parameters.js');
const own=(value,key)=>Object.hasOwn(value,key),object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const clone=value=>parameters.resolveParameters({run:{values:value}}).values;
const issue=(code,message,extra={})=>({code,message,...extra});
function boundedError(error,scope){return issue(error.code||'plugin-inspection',String(error.message||'Inspection is unavailable'),scope?{scope}:{});}
function readJson(root,relative){return JSON.parse(fs.readFileSync(registry.safe(root,relative),'utf8').replace(/^\uFEFF/,''));}
function operationsFor(source){return readJson(source,'templates/operations.json');}
function knownEntries(value,packages){
 if(value===undefined)return {status:'not-supplied',entries:[]};
 if(!object(value))registry.fail('plugin-known','Known definitions require an identity-keyed data map');
 const entries=[];
 for(const id of Object.keys(value).sort()){
  const record=value[id];
  if(!registry.validId(id)||!object(record)||own(record,'id')&&record.id!==id)registry.fail('plugin-known','Known definitions require exact distinct identities');
  entries.push({...clone(record),id,installed:own(packages,id)});
 }
 return {status:'provided',entries};
}
function packageInspection(root,value){
 const issues=[],states=new Map();
 for(const id of Object.keys(value.packages).sort()){
  const record=value.packages[id],local=[];
  try{
   const actual=registry.filesAt(root,record.destination);
   if(actual===null)local.push(issue('plugin-package-missing','The owned package destination is missing',{plugin_id:id,path:record.destination}));
   else{
    for(const relative of Object.keys(record.files).sort())if(!own(actual,relative)||actual[relative]!==record.files[relative])local.push(issue(own(actual,relative)?'plugin-resource-modified':'plugin-resource-missing','Owned resource bytes differ',{plugin_id:id,path:record.destination+'/'+relative}));
    for(const relative of Object.keys(actual).sort())if(!own(record.files,relative))local.push(issue('plugin-resource-unowned','The owned destination contains an unowned resource',{plugin_id:id,path:record.destination+'/'+relative}));
   }
  }catch(error){local.push(boundedError(error,id));}
  states.set(id,{status:local.length?'drift':'verified',scope:'resource-bytes',issues:local});issues.push(...local);
 }
 try{
  const base=registry.safe(root,registry.PACKAGES);
  if(fs.existsSync(base))for(const name of fs.readdirSync(base).sort())if(!own(value.packages,name))issues.push(issue('plugin-destination-unowned','An unowned package destination exists',{path:registry.PACKAGES+'/'+name}));
  registry.verifyInstalled(root,value);
 }catch(error){
  if(!issues.length)issues.push(boundedError(error,'installed-registry'));
 }
 return {issues,states};
}
function rowsFor(value,operations,issues){
 let compiled=null;
 try{
  const composition=require('./plugin-composition.js'),binding=require('./plugin-bindings.js');
  const defaults=Object.fromEntries(Object.entries(value.packages).filter(([,record])=>own(record.adaptation||{},'parameter_defaults')).map(([id,record])=>[id,clone(record.adaptation.parameter_defaults)]));
  compiled=binding.compileBindings(value.bindings,{packages:value.packages,catalog:composition.createCatalog(operations),parameterDefaults:defaults});
 }catch(error){issues.push(boundedError(error,'binding-configuration'));}
 const positions=new Map(),points=new Map();
 const rows=value.bindings.map((original,index)=>{
  const prepared=compiled?.bindings.find(item=>item.id===original.id),location=prepared?clone(prepared.location):{status:'unresolved',operation:original.operation,anchor:original.anchor,reason:'The current owned binding configuration is unavailable'};
  const key=location.status==='resolved'?location.boundary_id:JSON.stringify([original.operation,original.anchor]);
  const point_position=(positions.get(key)||0)+1;positions.set(key,point_position);
  const record=value.packages[original.plugin_id],row={...clone(original),position:index+1,point_position,point_id:key,parameters:own(original,'parameters')?clone(original.parameters):{},instructions:own(original,'instructions')?original.instructions:'',location,execution:clone(record.execution||{state:'unavailable',required:[],missing:[]})};
  if(prepared)row.effective=clone(prepared.effective);
  if(!points.has(key))points.set(key,{id:key,boundary_id:location.status==='resolved'?location.boundary_id:null,operation:original.operation,anchor:location.status==='resolved'?location.boundary_id.slice(original.operation.length+1):original.anchor,status:location.status,bindings:[]});
  points.get(key).bindings.push(row);return row;
 });
 return {rows,points:[...points.values()]};
}
function normalizedRoot(value){
 if(typeof value!=='string'||!path.isAbsolute(value))return null;
 try{return fs.realpathSync(value);}catch(error){if(error.code==='ENOENT')return path.resolve(value);throw error;}
}
function runData(root,core){
 const state=core.workflowState(root),runs=state?(state.run_registry?Object.values(state.run_registry.runs):state.active_run?[state.active_run]:[]):[];
 let locations={};
 const result=require('node:child_process').spawnSync('git',['-C',root,'rev-parse','--git-common-dir'],{encoding:'utf8',timeout:5000});
 if(result.status===0){
  const file=path.join(path.resolve(root,result.stdout.trim()),'skill-tree-runtime.json');
  if(fs.existsSync(file)){
   const locator=JSON.parse(fs.readFileSync(file,'utf8'));
   if(locator.schema!==1||!object(locator.worktrees))registry.fail('plugin-run-location','The recorded run location requires explicit recovery');
   locations=locator.worktrees;
  }
 }
 return {runs,locations};
}
function requirementsFor(record){
 const cfg=record.configuration;
 if(!object(cfg)||!object(cfg.packages)||!Array.isArray(cfg.bindings))registry.fail('plugin-hook-requirements','The frozen invocation configuration is unavailable');
 const packages=Object.keys(cfg.packages).sort().map(id=>({id,revision:cfg.packages[id].revision,content_digest:cfg.packages[id].content_digest,entry:cfg.packages[id].entry}));
 const bindings=cfg.bindings.map((row,index)=>({id:row.id,plugin_id:row.plugin_id,operation:row.operation,anchor:row.anchor,position:index+1,enabled:row.enabled,parameters:clone(row.effective?.values??row.parameters??{}),instructions:row.effective?.instructions??row.instructions??'',...(own(row,'condition')?{condition:clone(row.condition)}:{}),stage_state:record.stages[index]?.status||'unavailable'}));
 return {packages,bindings};
}
function frozenRequirements(root,current,issues){
 const core=require('./installation.js'),owner=core.queueRoot(root),target=fs.realpathSync(root);let records,data;
 try{records=core.readHookRecords(root);}catch(error){issues.push(boundedError(error,'frozen-requirements'));return [];}
 try{data=runData(root,core);}catch(error){issues.push(boundedError(error,'recorded-runs'));data={runs:[],locations:{},unavailable:true};}
 return records.map(record=>{
  const local=[],roots=new Set(),runIds=new Set(record.context?.run_id?[record.context.run_id]:[]);
  for(const run of data.runs)if(run.hook_chains?.includes(record.id))runIds.add(run.id);
  for(const id of runIds){
   const location=data.locations[id];if(location!==undefined){const normalized=normalizedRoot(location);if(normalized)roots.add(normalized);else local.push(issue('plugin-run-location','A recorded execution location is unavailable'));}
  }
  try{
   const file=registry.safe(owner,'.skill-tree/local/hook-locations/'+record.id.toLowerCase()+'.json');
   if(fs.existsSync(file)){
    const location=JSON.parse(fs.readFileSync(file,'utf8'));
    if(location.schema!==1||location.chain_id!==record.id||normalizedRoot(location.canonical_root)!==fs.realpathSync(owner)||!normalizedRoot(location.execution_root))registry.fail('plugin-hook-location','The private invocation execution location is unavailable');
    roots.add(normalizedRoot(location.execution_root));
   }
  }catch(error){local.push(boundedError(error,'invocation-location'));}
  if(roots.size>1)local.push(issue('plugin-hook-location','Recorded execution locations disagree'));
  const association=local.length||roots.size!==1?'unknown':roots.has(target)?'matched':'foreign';
  let requirements;
  try{requirements=requirementsFor(record);}catch(error){local.push(boundedError(error,'invocation-configuration'));requirements={packages:[],bindings:[],status:'unavailable'};}
  const row={chain_id:record.id,chain_state:record.state,association,run_ids:[...runIds],run_presence:!runIds.size?'not-applicable':data.unavailable?'unavailable':[...runIds].every(id=>data.runs.some(run=>run.id===id))?'recorded':'missing',requirements,original_attempts:Object.entries(record.attempts).map(([id,value])=>({id,status:value.status})),issues:local};
  if(record.superseded_by)row.superseded_by=record.superseded_by;
  if(association==='matched')row.current_target_comparison={packages:requirements.packages.map(pkg=>({id:pkg.id,state:!own(current.packages,pkg.id)?'missing':current.packages[pkg.id].revision===pkg.revision&&current.packages[pkg.id].content_digest===pkg.content_digest?'matching':'changed'})),bindings:requirements.bindings.map(binding=>{const now=current.bindings.find(item=>item.id===binding.id);return {id:binding.id,state:!now?'missing':now.plugin_id!==binding.plugin_id||now.operation!==binding.operation||now.anchor!==binding.anchor||now.enabled!==binding.enabled?'changed':'present'};})};
  issues.push(...local.map(item=>({...item,chain_id:record.id})));return row;
 });
}
function profileInspection(root,value,issues){
 const core=require('./installation.js'),present=fs.existsSync(registry.safe(root,registry.REGISTRY));let profile;
 try{profile=core.receipt(root,false);}catch(error){issues.push(boundedError(error,'core-receipt'));return {status:'unavailable',profile:null,copies:[]};}
 if(!profile){
  if(present){issues.push(issue('plugin-core-receipt','Installed plugin state requires the existing owned core receipt',{scope:'core-receipt'}));return {status:'unavailable',profile:null,copies:[]};}
  return {status:'ok',profile:null,copies:[]};
 }
 try{core.verifyOwned(root,profile);}catch(error){
  issues.push(boundedError(error,'core-receipt'));
  if(/receipt identity|invalid owned destination|unsupported|foreign|cannot convert|undefined/i.test(error.message))return {status:'unavailable',profile:null,copies:[]};
 }
 const raw=registry.safe(root,registry.REGISTRY),actual=fs.existsSync(raw)?registry.hash(fs.readFileSync(raw)):null;
 const requires_refresh=(profile.inputs?.[registry.REGISTRY]??null)!==actual||profile.plugins?.registry_identity!==undefined&&profile.plugins.registry_identity!==value.identity;
 if(requires_refresh)issues.push(issue('plugin-profile-refresh-required','Current plugin configuration requires explicit owned profile refresh and re-admission',{scope:'core-profile',blocking:false}));
 const copies=[];
 for(const [destination,record]of Object.entries(profile.destinations)){
  const ids=new Set(Object.keys(record.files||{}).map(relative=>/^plugins\/([^/]+)\//.exec(relative)?.[1]).filter(Boolean));
  for(const id of [...ids].sort())copies.push({plugin_id:id,operation:record.name,destination:path.posix.join(destination,'plugins',id),state:!own(value.packages,id)?'not-currently-installed':requires_refresh?'refresh-required':'receipt-owned',owner:'core-composition-receipt'});
 }
 return {status:'ok',profile:{identity:profile.identity,requires_refresh},copies};
}
function inventory(root,options={}){
 options=clone(options);if(!object(options))registry.fail('plugin-view','Inventory options require JSON data');
 root=fs.realpathSync(root);const issues=[];let value;
 const base={format:'skill-tree-plugin-inventory',schema:1,status:'ok',plugins:[],bindings:[],points:[],known:{status:options.known===undefined?'not-supplied':'provided',entries:[]},frozen_requirements:[],issues};
 try{value=registry.readRegistry(root);}catch(error){issues.push(boundedError(error,'installed-registry'));return {...base,status:'unavailable'};}
 base.known=knownEntries(options.known,value.packages);
 const receipt=profileInspection(root,value,issues);base.profile=receipt.profile;base.derived_copies=receipt.copies;
 if(receipt.status==='unavailable')return {...base,status:'unavailable'};
 const inspected=packageInspection(root,value);issues.push(...inspected.issues);
 let operations=options.operations;
 if(operations===undefined){try{operations=operationsFor(path.resolve(__dirname,'..'));}catch(error){issues.push(boundedError(error,'owned-operation-catalog'));operations={};}}
 const {rows,points}=rowsFor(value,operations,issues);base.bindings=rows;base.points=points;
 base.plugins=Object.keys(value.packages).sort().map(id=>{
  const record=value.packages[id];return {id,source:clone(record.source),revision:record.revision,content_digest:record.content_digest,destination:record.destination,entry:record.entry,package_dependencies:clone(record.package_dependencies),metadata:clone(record.metadata||{}),adaptation:clone(record.adaptation||{}),execution:clone(record.execution||{state:'unavailable',required:[],missing:[]}),ownership:inspected.states.get(id),bindings:rows.filter(row=>row.plugin_id===id),composed_copies:receipt.copies.filter(copy=>copy.plugin_id===id),dependents:Object.keys(value.packages).filter(other=>value.packages[other].package_dependencies.includes(id)).sort()};
 });
 base.registry={present:fs.existsSync(registry.safe(root,registry.REGISTRY)),identity:value.identity,generation:value.generation};
 base.frozen_requirements=frozenRequirements(root,value,issues);
 base.status=issues.length?'drift':'ok';return base;
}
const display=value=>JSON.stringify(value);
function bindingLine(row){return '  '+row.position+'. '+row.id+' -> '+display(row.operation)+' / '+display(row.anchor)+'; point '+row.point_position+'; '+(row.enabled?'enabled':'disabled')+(own(row,'condition')?'; condition='+JSON.stringify(row.condition):'')+'; parameters='+JSON.stringify(row.parameters)+'; instructions='+display(row.instructions);}
function formatInventory(view,{groupBy='plugin'}={}){
 if(!['plugin','point'].includes(groupBy))registry.fail('plugin-view','Group by plugin or point');
 const lines=['Installed plugins: '+view.status];
 if(groupBy==='plugin')for(const plugin of view.plugins){lines.push(plugin.id+' @ '+display(plugin.revision)+' ['+plugin.content_digest+'] '+plugin.ownership.scope+':'+plugin.ownership.status+'; destination='+display(plugin.destination)+'; execution='+display(plugin.execution));for(const row of plugin.bindings)lines.push(bindingLine(row));}
 else for(const point of view.points){lines.push(display(point.operation)+' / '+display(point.anchor)+' ['+point.status+']');for(const row of point.bindings)lines.push(bindingLine(row)+'; plugin='+row.plugin_id);}
 if(groupBy==='point')for(const plugin of view.plugins.filter(item=>!item.bindings.length))lines.push('Unbound package '+plugin.id+' @ '+display(plugin.revision)+'; destination='+display(plugin.destination));
 if(!view.plugins.length)lines.push(view.status==='unavailable'?'Installed state is unavailable.':'No installed external packages.');
 lines.push('Known definitions: '+view.known.status);for(const entry of view.known.entries)lines.push('  '+entry.id+' ['+(entry.installed?'installed':'not installed')+']');
 if(view.catalog?.status==='unavailable')lines.push('Catalog is unavailable: '+view.catalog.reason);
 if(view.catalog?.entries?.length||view.catalog?.status==='ok'){
  const entries=new Map(view.catalog.entries.map(row=>[row.id,row])),suggested=new Set();
  function describe(entry){
   const evidence=entry.evidence?.kind??'project-known',adapter=entry.adapter?.status??'requires-preparation';
   return entry.id+' @ '+display(entry.revision)+' ['+entry.status+'; installed: '+entry.installed+
    '; evidence: '+evidence+'; adapter: '+adapter+']; source='+display(entry.source)+
    '; prerequisites='+display(entry.adapter?.prerequisites??[])+
    (entry.unresolved_locations?.length?'; unresolved suggested locations: '+entry.unresolved_locations.length:'')+
    (entry.known_conflict?'; conflicting project-known source':'');
  }
  lines.push('Catalog suggestions by integration point:');
  for(const point of view.catalog.groups){
   if(!point.suggested.length)continue;
   lines.push('  '+point.boundary_id);
   for(const id of point.suggested){suggested.add(id);lines.push('    '+describe(entries.get(id)));}
  }
  const unplaced=view.catalog.entries.filter(entry=>!suggested.has(entry.id));
  if(unplaced.length){
   lines.push('Catalog entries without a suggested point:');
   for(const entry of unplaced)lines.push('  '+describe(entry));
  }
  for(const [flavor,bundle]of Object.entries(view.catalog.recommendations)){
   lines.push('Catalog recommendations ('+flavor+'): '+(bundle.length?bundle.map(row=>row.id+' at '+row.boundary_id).join(', '):'none'));
  }
 }
 for(const frozen of view.frozen_requirements)lines.push('Frozen '+frozen.chain_id+' ['+display(frozen.chain_state)+'; '+frozen.association+'; runs '+frozen.run_presence+'] '+JSON.stringify(frozen.requirements)+'; original attempts='+JSON.stringify(frozen.original_attempts));
 for(const item of view.issues)lines.push('Issue '+item.code+': '+display(item.message));return lines.join('\n')+'\n';
}
function exactPackage(value,id){if(!registry.validId(id)||!own(value.packages,id))registry.fail('plugin-selection','Select an exact installed plugin ID');return value.packages[id];}
function exactBinding(value,id){if(!registry.validId(id))registry.fail('plugin-selection','Select an exact binding occurrence ID');const found=value.bindings.find(row=>row.id===id);if(!found)registry.fail('plugin-selection','Select an exact binding occurrence ID');return found;}
async function prepareChange(root,request,action,ids){
 const value=registry.readRegistry(root),view=inventory(root),selectedBindings=view.bindings.filter(row=>ids.binding_ids?.includes(row.id)||ids.plugin_ids?.includes(row.plugin_id));
 const dependents=ids.plugin_ids?Object.keys(value.packages).filter(id=>!ids.plugin_ids.includes(id)&&value.packages[id].package_dependencies.some(dependency=>ids.plugin_ids.includes(dependency))).sort():[];
 const affectedFrozen=view.frozen_requirements.filter(row=>row.requirements.packages.some(pkg=>ids.plugin_ids?.includes(pkg.id))||row.requirements.bindings.some(binding=>ids.binding_ids?.includes(binding.id)));
 const impact={bindings:selectedBindings,requires_profile_refresh:true,retained_composed_copies:view.derived_copies?.filter(copy=>ids.plugin_ids?.includes(copy.plugin_id))||[],destinations:(ids.plugin_ids||[]).map(id=>value.packages[id].destination),dependents,frozen_requirements:affectedFrozen.filter(row=>row.association==='matched'),uncertain_frozen_requirements:affectedFrozen.filter(row=>row.association==='unknown'),retained_sources:(ids.plugin_ids||[]).map(id=>clone(value.packages[id].source)),retained_packages:Object.keys(value.packages).filter(id=>!ids.plugin_ids?.includes(id)).sort()};
 const prerequisites=view.issues.filter(item=>item.blocking!==false);if(dependents.length)prerequisites.push(issue('plugin-dependency','Installed dependent packages must be resolved before removal',{dependents}));
 if(view.status==='unavailable'||prerequisites.length||dependents.length)return {status:'blocked',action,impact,proposal:null,prerequisites};
 let proposal;
 try{proposal=await require('./plugin-lifecycle.js').prepareProposal(root,request);}catch(error){return {status:'blocked',action,impact,proposal:null,prerequisites:[...prerequisites,boundedError(error,'proposal')]};}
 try{if(require('./installation.js').hasActiveOperation(root))prerequisites.push(issue('plugin-active','Original active operations require a stopped cleanup/handoff before application'));}catch(error){prerequisites.push(boundedError(error,'workflow-state'));}
 return {status:prerequisites.length?'blocked':'ready',action,impact,proposal,prerequisites};
}
async function prepareRemoval(root,request){request=clone(request||{});const value=registry.readRegistry(root);exactPackage(value,request?.plugin_id);return prepareChange(root,{request_id:request.request_id,operation:'uninstall',plugin_ids:[request.plugin_id]},'uninstall',{plugin_ids:[request.plugin_id]});}
async function prepareUnbind(root,request){request=clone(request||{});const value=registry.readRegistry(root);exactBinding(value,request?.binding_id);return prepareChange(root,{request_id:request.request_id,operation:'configure',bindings:value.bindings.filter(row=>row.id!==request.binding_id)},'unbind',{binding_ids:[request.binding_id]});}
async function prepareActivation(root,request){request=clone(request||{});const value=registry.readRegistry(root);exactBinding(value,request?.binding_id);if(typeof request.enabled!=='boolean')registry.fail('plugin-selection','Activation requires explicit enabled state');const operation=request.enabled?'enable':'disable';return prepareChange(root,{request_id:request.request_id,operation,binding_ids:[request.binding_id]},operation,{binding_ids:[request.binding_id]});}
function managementSemantics(root,proposal){
 if(!object(proposal.packages)||!Array.isArray(proposal.bindings)||!object(proposal.snapshots)||Object.keys(proposal.snapshots).length)registry.fail('plugin-action','Installed-package management cannot acquire or replace package snapshots');
 const current=registry.readRegistry(root),primary=own(current.requests,proposal.request_id)?current.requests[proposal.request_id]:null;
 const history=registry.readNoopRequests(root,current.generation),noop=own(history.requests,proposal.request_id)?history.requests[proposal.request_id]:null;
 if(primary||noop){
  const recorded=primary||noop;
  if(recorded.proposal_digest===proposal.digest&&!['verified-no-op',proposal.operation==='uninstall'?'uninstalled':'configured'].includes(recorded.action))registry.fail('plugin-action','The recorded request belongs to another lifecycle operation');
  // Original replay and conflicting reuse retain the backend ownership/digest checks.
  return;
 }
 if(current.identity!==proposal.base_registry_identity||current.generation!==proposal.base_generation)return;
 const same=(left,right)=>registry.json(left)===registry.json(right);
 if(proposal.operation==='uninstall'){
  const selected=Object.keys(current.packages).filter(id=>!own(proposal.packages,id));
  if(!selected.length||Object.keys(proposal.packages).some(id=>!own(current.packages,id)||!same(proposal.packages[id],current.packages[id])))registry.fail('plugin-action','Uninstall requires a strict subset of unchanged installed packages');
  const remaining=current.bindings.filter(row=>!selected.includes(row.plugin_id));
  if(!same(proposal.bindings,remaining))registry.fail('plugin-action','The uninstall proposal must retain the exact remaining binding order and content');
 }else{
  if(!same(proposal.packages,current.packages))registry.fail('plugin-action','Configuration and activation cannot add, remove or replace installed packages');
  if(proposal.operation!=='configure'){
   if(proposal.bindings.length!==current.bindings.length)registry.fail('plugin-action','Activation must retain every binding occurrence and position');
   const enabled=proposal.operation==='enable';
   for(let index=0;index<current.bindings.length;index++){
    const before=current.bindings[index],after=proposal.bindings[index];
    if(!object(after))registry.fail('plugin-action','Activation requires the original binding occurrences');
    const old={...before},next={...after};delete old.enabled;delete next.enabled;
    if(!same(old,next)||(after.enabled!==before.enabled&&after.enabled!==enabled))registry.fail('plugin-action','Activation changes only enabled state in the requested direction');
   }
  }
 }
}
function applyManagementChange(root,proposal,confirmation,options){proposal=clone(proposal||{});if(!proposal||!['uninstall','configure','enable','disable'].includes(proposal.operation))registry.fail('plugin-action','Select a supported installed-package management proposal');managementSemantics(root,proposal);return require('./plugin-lifecycle.js').applyProposal(root,proposal,confirmation,options);}
function applyRemoval(root,proposal,confirmation){proposal=clone(proposal||{});if(proposal?.operation!=='uninstall')registry.fail('plugin-action','Package removal requires the original uninstall proposal');return applyManagementChange(root,proposal,confirmation);}
function forgetKnown(){registry.fail('plugin-known-owner','Forgetting a known definition is separate from installed package removal and requires the known-definition owner');}
const KNOWN = '.skill-tree/installation/plugin-known.json';
const MANAGER_FORMAT = 'skill-tree-manager-proposal';
const managerOperations = {
  install: 'install', update: 'update', configure: 'configure', bind: 'configure', edit: 'configure',
  move: 'configure', unbind: 'configure', enable: 'enable', disable: 'disable', uninstall: 'uninstall',
};
const managerFields = {
  install: ['sources', 'bindings', 'resolve_remote'], update: ['sources', 'bindings', 'resolve_remote'],
  configure: ['bindings'], bind: ['binding', 'index'], edit: ['binding_id', 'changes'],
  move: ['binding_id', 'index'], unbind: ['binding_id'], enable: ['binding_id'], disable: ['binding_id'],
  uninstall: ['plugin_id'], 'save-known': ['source', 'suggested_locations'], 'forget-known': ['plugin_id'],
};
const digest = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
const same = (left, right) => registry.json(left) === registry.json(right);

function assertKnownEntry(id, entry) {
  if (!registry.validId(id) || !object(entry) || entry.definition?.id !== id || !object(entry.definition.source) ||
      !Array.isArray(entry.suggested_locations) || typeof entry.requires_locator !== 'boolean' ||
      own(entry, 'locator') || own(entry.definition, 'locator')) {
    registry.fail('plugin-known-owner', 'Invalid portable project-known source record');
  }
}

function assertKnownChange(current, action, mutation) {
  const id = mutation.plugin_id;
  if (action === 'save-known') {
    assertKnownEntry(id, mutation.entry);
    if (own(current.entries, id) && !sameManagerSource(current.entries[id].definition.source, mutation.entry.definition.source))
      registry.fail('plugin-known-owner', 'The proposed known source identity conflicts');
  } else if (!registry.validId(id) || mutation.entry !== null || !own(current.entries, id)) {
    registry.fail('plugin-known-owner', 'Select an exact existing known source to forget');
  }
}

function readKnown(root) {
  const file = registry.safe(root, KNOWN);
  if (!fs.existsSync(file)) return registry.seal({
    format: 'skill-tree-plugin-known', schema: 1, generation: 0, entries: {}, requests: {},
  });
  const value = readJson(root, KNOWN);
  if (value.format !== 'skill-tree-plugin-known' || value.schema !== 1 || !Number.isSafeInteger(value.generation) ||
      value.generation < 0 || !object(value.entries) || !object(value.requests) ||
      value.identity !== registry.seal(value).identity) {
    registry.fail('plugin-known-owner', 'Project-known source inventory requires explicit ownership recovery');
  }
  for (const [id, entry] of Object.entries(value.entries)) assertKnownEntry(id, entry);
  for (const [id, receipt] of Object.entries(value.requests)) {
    if (receipt.request_id !== id || !digest(receipt.proposal_digest) ||
        !['saved-known', 'forgot-known'].includes(receipt.action) || !Number.isSafeInteger(receipt.generation) ||
        receipt.generation < 1 || receipt.generation > value.generation) {
      registry.fail('plugin-known-owner', 'Invalid project-known source request history');
    }
  }
  return value;
}

function managerCatalog(source, diagnostic) {
  const catalog = require('./plugin-catalog.js');
  const unavailable = reason => ({catalog: catalog.emptyCatalog(source), diagnostic: reason});
  if (diagnostic) return unavailable(diagnostic);
  try {
    return {catalog: catalog.loadCatalog(source), diagnostic: null};
  } catch (error) {
    return unavailable(error.code === 'plugin-catalog' ? error.message : 'Owned curated catalog metadata is unavailable');
  }
}

function managementInventory(root, {source = path.resolve(__dirname, '..'), host, flavor, point, catalogDiagnostic} = {}) {
  let known, knownIssue;
  try {
    known = readKnown(root);
  } catch (error) {
    knownIssue = boundedError(error, 'project-known');
  }
  const view = inventory(root, {
    operations: operationsFor(source), ...(known?.generation ? {known: known.entries} : {}),
  });
  if (knownIssue) {
    view.known = {status: 'unavailable', entries: []};
    view.issues.push(knownIssue);
    if (view.status === 'ok') view.status = 'drift';
  }
  const bundled = path.resolve(source) === path.resolve(root, '.skill-tree/installation/source');
  if (bundled && !catalogDiagnostic) {
    try {
      if (view.issues.some(item => item.scope === 'core-receipt')) throw Error('Owned core receipt is unavailable');
      if (!view.profile) {
        const core = require('./installation.js');
        core.verifyOwned(root, core.receipt(root, true));
      }
    } catch {
      catalogDiagnostic = 'Owned curated catalog metadata could not be verified';
    }
  }
  const {catalog, diagnostic} = managerCatalog(source, catalogDiagnostic);
  view.catalog = require('./plugin-catalog.js').catalogView(catalog, {
    host, flavor, point, known: known?.entries || {}, inventory: view,
  });
  if (diagnostic) view.catalog = {...view.catalog, status: 'unavailable', reason: diagnostic};
  return view;
}

function managerLocation(request, catalog) {
  const location = require('./plugin-bindings.js').resolveLocation(request, catalog.anchors);
  if (location.status !== 'resolved') registry.fail('binding-anchor', location.reason || 'Select a registered executable location');
  return location;
}

function bindingInput(row, catalog) {
  if (!object(row)) registry.fail('plugin-binding', 'An explicit binding occurrence is required');
  const {location, ...binding} = row;
  if (location !== undefined) {
    if (binding.operation !== undefined || binding.anchor !== undefined)
      registry.fail('binding-anchor', 'Select one location or exact operation and anchor');
    const resolved = managerLocation(location, catalog);
    binding.operation = resolved.operation;
    binding.anchor = resolved.anchor;
  } else {
    managerLocation(binding, catalog);
  }
  return {...binding, enabled: binding.enabled === undefined ? true : binding.enabled};
}

function sameManagerSource(left, right) {
  if (left.kind !== right.kind || left.entry !== right.entry) return false;
  return left.kind === 'local' ? left.locator_id === right.locator_id : left.url === right.url;
}

function managerSource(root, input, known, catalog) {
  const {normalizeSource} = require('./plugin-sources.js');
  const selected = object(input) ? input.known_id : undefined;
  const id = selected ?? (typeof input === 'string' && (own(known, input) || catalog.entries.has(input)) ? input : undefined);
  let descriptor = input;
  let saved;
  if (id !== undefined) {
    descriptor = require('./plugin-catalog.js').selectSource(catalog, id, {known});
    saved = own(known, id) ? known[id] : null;
    if (saved?.requires_locator && !input.locator)
      registry.fail('plugin-known-locator', 'The selected known source requires its explicit current acquisition locator');
    if (object(input) && input.locator) descriptor = {...descriptor, locator: input.locator};
  }
  const normalized = normalizeSource(descriptor, {baseDir: root});
  const {source} = normalized.definition;
  if (source.kind === 'local' && source.locator_id !== registry.hash(normalized.locator.path))
    registry.fail('plugin-known-locator', 'The local acquisition locator differs from the selected source identity');
  if (source.kind !== 'local') {
    const {definition} = normalizeSource({...normalized.definition, source: {...source, url: normalized.locator.url}}, {baseDir: root});
    if (!sameManagerSource(source, definition.source))
      registry.fail('plugin-known-locator', 'The remote acquisition locator differs from the selected source identity');
  }
  const registered = own(known, normalized.definition.id) ? known[normalized.definition.id] : null;
  if (registered && !sameManagerSource(registered.definition.source, source))
    registry.fail('plugin-known-conflict', 'The exact project-known identity names a different source');
  const curated = catalog.entries.get(normalized.definition.id);
  if (curated && !sameManagerSource(curated.row.source, source))
    registry.fail('plugin-known-conflict', 'The exact curated identity names a different source');
  const portable = {...normalized.definition};
  for (const key of ['expectedDigests', 'package_dependencies']) {
    if (object(descriptor) && own(descriptor, key)) portable[key] = descriptor[key];
  }
  const url = normalized.locator.url ? new URL(normalized.locator.url) : null;
  const requiresLocator = source.kind === 'local' || Boolean(url?.username || url?.password || url?.search);
  const privateLocator = requiresLocator && (normalized.locator.path || normalized.locator.url);
  if (privateLocator && registry.json(portable).includes(JSON.stringify(privateLocator).slice(1, -1)))
    registry.fail('plugin-known-locator', 'Private acquisition locators must remain outside portable source data');
  return {portable, acquisition: {...portable, locator: normalized.locator}, requiresLocator};
}

function managerScope(root) {
  const core = require('./installation.js');
  const profile = core.receipt(root, true);
  core.verifyOwned(root, profile);
  return require('./plugin-lifecycle.js').providerScope(profile);
}

function assertManagerSelections(scope, selections, expectedFlavor) {
  if (!object(scope) || !object(scope.destinations))
    registry.fail('plugin-proposal', 'The manager proposal requires an exact provider and destination scope');
  if (expectedFlavor !== undefined && scope.flavor !== expectedFlavor)
    registry.fail('plugin-stale', 'The confirmed scope differs from the originally selected core flavor');
  for (const {rel, name, provider} of selections) {
    const record = scope.destinations[rel];
    if (record?.name !== name || !Array.isArray(record.providers) || !record.providers.includes(provider))
      registry.fail('plugin-stale', 'The confirmed scope omits an originally selected core provider or destination');
  }
}

function managerDigest(proposal) {
  const {digest: ignored, ...body} = proposal;
  return registry.hash(registry.json(body));
}

function managerEnvelope(root, request, preview, mutation) {
  const proposal = {
    format: MANAGER_FORMAT, schema: 1, target_identity: registry.hash(fs.realpathSync(root)),
    action: request.action, request_id: request.request_id, preview, mutation,
  };
  proposal.digest = managerDigest(proposal);
  return {status: 'ready', preview: clone(preview), proposal, prerequisites: []};
}

function managerKnownPreview(action, scope, mutation) {
  return {action, provider_scope: scope, known_generation: mutation.generation,
    plugin_id: mutation.plugin_id, known: mutation.entry, preserves_installed_state: true};
}

function prepareKnownManager(root, request, known, catalog, scope) {
  let pluginId = request.plugin_id;
  let entry;
  if (request.action === 'save-known') {
    const selected = managerSource(root, request.source, known.entries, catalog);
    pluginId = selected.portable.id;
    const suggestions = request.suggested_locations ?? [];
    if (!Array.isArray(suggestions)) registry.fail('plugin-known-owner', 'Known locations require an explicit list');
    const places = new Map();
    for (const suggestion of suggestions) {
      const location = managerLocation(suggestion, catalog);
      places.set(location.boundary_id, {operation: location.operation, anchor: location.anchor});
    }
    entry = {definition: selected.portable, suggested_locations: [...places.values()],
      requires_locator: selected.requiresLocator};
  } else {
    if (!registry.validId(pluginId) || !own(known.entries, pluginId))
      registry.fail('plugin-known-owner', 'Select an exact project-known plugin identity');
    entry = null;
  }
  const mutation = {kind: 'known', generation: known.generation, identity: known.identity,
    plugin_id: pluginId, entry, provider_scope: scope};
  return managerEnvelope(root, request, managerKnownPreview(request.action, scope, mutation), mutation);
}

function managerBindingChange(base, request, catalog) {
  const {moveBinding, removeBinding} = require('./plugin-bindings.js');
  const selected = request.binding_id === undefined ? null : exactBinding(base, request.binding_id);
  const operation = managerOperations[request.action];
  const lifecycle = {request_id: request.request_id, operation};
  let rows = base.bindings;
  if (operation === 'enable' || operation === 'disable') {
    if (!selected) registry.fail('plugin-selection', 'Select an exact binding occurrence ID');
    return {...lifecycle, binding_ids: [selected.id]};
  }
  if (operation === 'uninstall') return {...lifecycle, plugin_ids: [exactPackage(base, request.plugin_id).id]};
  if (request.action === 'unbind') return {...lifecycle, bindings: removeBinding(rows, selected?.id)};
  if (request.action === 'configure' || request.bindings !== undefined) {
    if (!Array.isArray(request.bindings)) registry.fail('plugin-binding', 'Supply the complete ordered binding sequence');
    return {...lifecycle, bindings: request.bindings.map(row => {
      const previous = rows.find(item => item.id === row?.id);
      return previous && same(previous, row) ? previous : bindingInput(row, catalog);
    })};
  }
  if (request.action === 'edit') {
    const changes = request.changes;
    if (!selected || !object(changes) || Object.keys(changes).some(key =>
      !['operation', 'anchor', 'location', 'enabled', 'condition', 'parameters', 'instructions'].includes(key))) {
      registry.fail('plugin-binding', 'Select an exact occurrence and its editable fields');
    }
    const edited = {...selected, ...changes};
    if (own(changes, 'location')) {delete edited.operation;delete edited.anchor;}
    if (changes.condition === null) delete edited.condition;
    return {...lifecycle, bindings: rows.map(row => row.id === selected.id ? bindingInput(edited, catalog) : row)};
  }
  if (request.action === 'bind' || request.action === 'move') {
    const row = request.action === 'bind' ? bindingInput(request.binding, catalog) : selected;
    if (!row) registry.fail('plugin-selection', 'Select an exact binding occurrence ID');
    if (request.action === 'bind' && rows.some(item => item.id === row.id))
      registry.fail('binding-identity', 'The new occurrence ID is already configured');
    const boundary = managerLocation(row, catalog).boundary_id;
    const {resolveLocation} = require('./plugin-bindings.js');
    const slots = rows.flatMap((item, index) =>
      resolveLocation(item, catalog.anchors).boundary_id === boundary ? [index] : []);
    if (request.action === 'move') {
      const sequence = moveBinding(slots.map(index => rows[index]), row.id, request.index);
      rows = [...rows];
      slots.forEach((slot, index) => {rows[slot] = sequence[index];});
    } else {
      const index = request.index ?? slots.length;
      if (!Number.isInteger(index) || index < 0 || index > slots.length)
        registry.fail('binding-order', 'The requested occurrence position is outside the configured chain');
      const slot = index < slots.length ? slots[index] : slots.length ? slots.at(-1) + 1 : rows.length;
      rows = [...rows.slice(0, slot), row, ...rows.slice(slot)];
    }
    return {...lifecycle, bindings: rows};
  }
  return lifecycle;
}

function bindingReadiness(row, record) {
  if (!row.enabled) return 'The occurrence remains disabled.';
  if (row.condition === false) return 'The condition excludes this occurrence.';
  if (row.location.status !== 'resolved') return 'The configured location is unresolved.';
  const runtime = require('./plugin-runtime.js');
  runtime.invocationPolicy(record);
  if (row.location.boundary_id === 'skill-tree-process-future-pending:after') {
    const application = runtime.processingApplication(row, record);
    if (application) return 'An enabled matching ' + application.role + ' occurrence requires current clarification, applicable rechecks and current-mode acceptance before implementation.';
  }
  if (row.operation === 'skill-tree-pr-review-cycle') {
    return 'An enabled matching occurrence must complete for the current review identity before PR readiness.';
  }
  return 'A matching configured occurrence may participate in the later authorized workflow.';
}

function managerLifecyclePreview(action, proposal, operations) {
  const issues = [];
  const {rows} = rowsFor(proposal, operations, issues);
  if (issues.length) registry.fail('plugin-binding', issues[0].message);
  const packages = Object.values(proposal.packages).sort((left, right) => left.id.localeCompare(right.id));
  return {
    action, operation: proposal.operation, registry_generation: proposal.base_generation,
    registry_identity: proposal.base_registry_identity, provider_scope: proposal.provider_scope,
    packages: packages.map(record => ({
      id: record.id, source: record.source, revision: record.revision, content_digest: record.content_digest,
      destination: record.destination, entry: record.entry, dependencies: record.package_dependencies,
      resources: record.files, adaptation: record.adaptation, execution: record.execution,
    })),
    bindings: rows.map(row => ({
      ...row,
      readiness: bindingReadiness(row, proposal.packages[row.plugin_id]),
    })),
  };
}

function managerImpact(base, proposal, view, bindings, anchors) {
  const proposedRows = new Map(bindings.map(row => [row.id, row]));
  const proposedBindings = new Map(proposal.bindings.map(row => [row.id, row]));
  const changed = new Set(view.bindings.filter(row => {
    const next = proposedRows.get(row.id);
    return !next || row.point_position !== next.point_position ||
      !same(base.bindings[row.position - 1], proposedBindings.get(row.id));
  }).map(row => row.id));
  const previousRows = new Map(view.bindings.map(row => [row.id, row]));
  const changedPoints = new Set([...view.bindings, ...bindings].filter(row =>
    changed.has(row.id) || !previousRows.has(row.id)
  ).map(row => row.point_id));
  const packageChanges = Object.values(base.packages).filter(record => !same(record, proposal.packages[record.id]));
  const removed = packageChanges.filter(record => !own(proposal.packages, record.id));
  const {resolveLocation} = require('./plugin-bindings.js');
  const affected = view.frozen_requirements.filter(record =>
    record.requirements.bindings.some(row => changed.has(row.id) ||
      changedPoints.has(resolveLocation(row, anchors).boundary_id)) ||
    record.requirements.packages.some(pkg => packageChanges.some(row => row.id === pkg.id)));
  return {
    removed_packages: removed.map(row => ({id: row.id, source: row.source, destination: row.destination, resources: row.files})),
    removed_bindings: base.bindings.filter(row => !proposedBindings.has(row.id)).map(row => row.id),
    frozen_requirements: affected.filter(row => row.association === 'matched'),
    uncertain_frozen_requirements: affected.filter(row => row.association === 'unknown'),
  };
}

function managerPrerequisites(root, view) {
  const core = require('./installation.js');
  const issues = (view?.issues || []).filter(item => item.blocking !== false);
  if (['core', 'plugins'].some(channel => fs.existsSync(registry.safe(root, core.transactionPaths(channel).journal)))) {
    issues.push(issue('plugin-recovery', 'Owned installation recovery is required before a new manager mutation'));
  }
  try {
    if (core.hasActiveOperation(root)) issues.push(issue('plugin-active', 'Reach a stopped workflow handoff before applying the proposal'));
  } catch (error) {
    issues.push(boundedError(error, 'workflow-state'));
  }
  return issues;
}

function managerOperationsFor(root) {
  return operationsFor(registry.safe(root, '.skill-tree/installation/source'));
}

async function prepareManagerRequest(root, request, options = {}) {
  request = clone(request);
  if (!object(request) || typeof request.request_id !== 'string' || !request.request_id ||
      request.request_id.length > 200 || /[\x00-\x1f]/.test(request.request_id)) {
    registry.fail('plugin-request', 'A stable manager request identity is required');
  }
  if (!own(managerFields, request.action) || Object.keys(request).some(key =>
    !['action', 'request_id', ...managerFields[request.action]].includes(key))) {
    registry.fail('plugin-action', 'Select a supported manager action with its exact fields');
  }
  const source = options.source ?? path.resolve(__dirname, '..');
  const scope = managerScope(root);
  const selections = options.selections ?? [];
  assertManagerSelections(scope, selections, options.expectedFlavor);
  const sourceAction = ['install', 'update', 'save-known', 'forget-known'].includes(request.action);
  const known = sourceAction ? readKnown(root) : null;
  const {catalog: knownCatalog} = managerCatalog(source);
  const operations = managerOperationsFor(root);
  const catalog = {...knownCatalog, anchors: require('./plugin-composition.js').createCatalog(operations)};
  if (['save-known', 'forget-known'].includes(request.action)) {
    const result = prepareKnownManager(root, request, known, catalog, scope);
    const prerequisites = managerPrerequisites(root);
    return prerequisites.length ? {...result, status: 'blocked', proposal: null, prerequisites} : result;
  }
  const base = registry.verifyInstalled(root);
  const lifecycle = managerBindingChange(base, request, catalog);
  if (['install', 'update'].includes(lifecycle.operation)) {
    if (!Array.isArray(request.sources) || !request.sources.length)
      registry.fail('plugin-source', 'Select explicit source inputs for installation or update');
    lifecycle.sources = request.sources.map(input => {
      const {acquisition} = managerSource(root, input, known.entries, catalog);
      if (acquisition.source.kind !== 'local' && request.resolve_remote !== true && typeof options.acquire !== 'function')
        registry.fail('source-acquisition-required', 'Explicit online source resolution is required before preview');
      return acquisition;
    });
  }
  const proposal = await require('./plugin-lifecycle.js').prepareProposal(root, lifecycle, {
    bindProviderScope: true, acquire: options.acquire, availableCapabilities: options.availableCapabilities,
  });
  assertManagerSelections(proposal.provider_scope, selections, options.expectedFlavor);
  if (proposal.base_registry_identity !== base.identity || registry.readRegistry(root).identity !== base.identity)
    registry.fail('plugin-stale', 'The installed generation changed during manager preparation');
  const view = inventory(root, {operations});
  const preview = managerLifecyclePreview(request.action, proposal, operations);
  preview.impact = managerImpact(base, proposal, view, preview.bindings, catalog.anchors);
  preview.requires_profile_refresh = !same(base.packages, proposal.packages) || !same(base.bindings, proposal.bindings);
  const prerequisites = managerPrerequisites(root, view);
  if (prerequisites.length) return {status: 'blocked', preview, proposal: null, prerequisites};
  const bound = {...proposal, manager_action: request.action, manager_preview_digest: registry.hash(registry.json(preview)),
    manager_impact_digest: registry.hash(registry.json(preview.impact))};
  bound.digest = require('./plugin-lifecycle.js').proposalDigest(bound);
  return managerEnvelope(root, request, preview, {kind: 'lifecycle', proposal: bound});
}

function applyKnownManager(root, envelope) {
  const {mutation, action, request_id} = envelope;
  const core = require('./installation.js');
  return core.locked(root, () => {
    const scope = managerScope(root);
    const current = readKnown(root);
    if (own(current.requests, request_id)) {
      const receipt = current.requests[request_id];
      if (receipt.proposal_digest !== envelope.digest)
        registry.fail('plugin-replay', 'The known-source request identity conflicts with an earlier proposal');
      return {...receipt, replayed: true, current_generation: current.generation};
    }
    if (!same(scope, mutation.provider_scope) || mutation.identity !== current.identity ||
        mutation.generation !== current.generation) {
      registry.fail('plugin-stale', 'The project-known generation or provider scope changed');
    }
    if (core.hasActiveOperation(root)) registry.fail('plugin-active', 'Reach a stopped workflow handoff before changing known sources');
    assertKnownChange(current, action, mutation);
    const entries = {...current.entries};
    if (action === 'save-known') entries[mutation.plugin_id] = mutation.entry;
    else delete entries[mutation.plugin_id];
    const receipt = {action: action === 'save-known' ? 'saved-known' : 'forgot-known', request_id,
      proposal_digest: envelope.digest, generation: current.generation + 1};
    const next = registry.seal({...current, generation: receipt.generation, entries,
      requests: {...current.requests, [request_id]: receipt}});
    const file = registry.safe(root, KNOWN);
    const temporary = path.join(path.dirname(file), '.known-' + require('node:crypto').randomUUID() + '.tmp');
    try {
      const fd = fs.openSync(temporary, 'wx', 0o600);
      try {fs.writeFileSync(fd, registry.json(next));fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
      if (readKnown(root).identity !== current.identity || !same(managerScope(root), scope))
        registry.fail('plugin-stale', 'Project-known data or provider scope changed during activation');
      fs.renameSync(temporary, file);
    } finally {
      if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
    }
    return receipt;
  }, {recoverPending: false});
}

function verifiedManagerProposal(root, envelope, confirmation, selections, expectedFlavor) {
  envelope = clone(envelope);
  if (envelope?.format !== MANAGER_FORMAT || envelope.schema !== 1 ||
      envelope.target_identity !== registry.hash(fs.realpathSync(root)) || envelope.digest !== managerDigest(envelope)) {
    registry.fail('plugin-proposal', 'The manager proposal digest, target or content changed');
  }
  if (!object(confirmation) || Object.keys(confirmation).length !== 1 || confirmation.proposal_digest !== envelope.digest)
    registry.fail('plugin-consent', 'Explicit confirmation of the exact manager proposal digest is required');
  const {action, request_id, preview, mutation} = envelope;
  if (typeof request_id !== 'string' || !request_id || request_id.length > 200 || /[\x00-\x1f]/.test(request_id))
    registry.fail('plugin-proposal', 'A stable manager request identity is required');
  let scope;
  if (mutation?.kind === 'known' && ['save-known', 'forget-known'].includes(action) &&
      same(preview, managerKnownPreview(action, mutation.provider_scope, mutation))) {
    scope = mutation.provider_scope;
  } else {
    const proposal = mutation?.proposal;
    if (mutation?.kind !== 'lifecycle' || !own(managerOperations, action) ||
        proposal?.operation !== managerOperations[action] || proposal.request_id !== request_id ||
        proposal.manager_action !== action || !same(proposal.provider_scope, preview?.provider_scope) ||
        proposal.manager_preview_digest !== registry.hash(registry.json(preview))) {
      registry.fail('plugin-proposal', 'The public manager preview does not match the owned lifecycle proposal');
    }
    require('./plugin-lifecycle.js').validateProposal(root, proposal, {proposal_digest: proposal.digest});
    scope = proposal.provider_scope;
  }
  assertManagerSelections(scope, selections, expectedFlavor);
  return envelope;
}

function validateCurrentManagerPreview(root, action, preview, base, proposal) {
  const operations = managerOperationsFor(root);
  const view = inventory(root, {operations});
  const prerequisites = managerPrerequisites(root, view);
  if (prerequisites.length) registry.fail('plugin-stale', prerequisites[0].message);
  const current = managerLifecyclePreview(action, proposal, operations);
  const anchors = require('./plugin-composition.js').createCatalog(operations);
  current.impact = managerImpact(base, proposal, view, current.bindings, anchors);
  current.requires_profile_refresh = !same(base.packages, proposal.packages) || !same(base.bindings, proposal.bindings);
  if (proposal.manager_impact_digest !== registry.hash(registry.json(current.impact)) || !same(preview, current))
    registry.fail('plugin-stale', 'The approved preview or frozen requirements changed; prepare a fresh preview');
}

function inspectManagerProposal(root, envelope, confirmation, {profile, selections = [], expectedFlavor}) {
  const verified = verifiedManagerProposal(root, envelope, confirmation, selections, expectedFlavor);
  const {mutation, action, request_id, digest: proposalDigest} = verified;
  const lifecycle = require('./plugin-lifecycle.js');
  if (mutation.kind === 'lifecycle') {
    const proposal = mutation.proposal;
    const base = lifecycle.inspectProposal(root, proposal, {proposal_digest: proposal.digest}, profile);
    if (base) validateCurrentManagerPreview(root, action, verified.preview, base, proposal);
  } else {
    const current = readKnown(root);
    const recorded = own(current.requests, request_id) ? current.requests[request_id] : null;
    if (recorded && recorded.proposal_digest !== proposalDigest)
      registry.fail('plugin-replay', 'The known-source request identity conflicts with an earlier proposal');
    if (!recorded && (!same(lifecycle.providerScope(profile), mutation.provider_scope) ||
        current.identity !== mutation.identity || current.generation !== mutation.generation))
      registry.fail('plugin-stale', 'The project-known generation or provider scope changed');
    if (!recorded) assertKnownChange(current, action, mutation);
  }
  return verified.preview;
}

function applyManagerProposal(root, envelope, confirmation, {selections = [], expectedFlavor} = {}) {
  envelope = verifiedManagerProposal(root, envelope, confirmation, selections, expectedFlavor);
  const {action, preview, mutation} = envelope;
  if (mutation.kind === 'known') return applyKnownManager(root, envelope);
  const proposal = mutation.proposal;
  const exact = {proposal_digest: proposal.digest};
  const options = {validateManagerImpact(base, candidate) {
    validateCurrentManagerPreview(root, action, preview, base, candidate);
  }};
  return ['install', 'update'].includes(proposal.operation) ?
    require('./plugin-lifecycle.js').applyProposal(root, proposal, exact, options) :
    applyManagementChange(root, proposal, exact, options);
}

function listMain(root,args,{source=path.resolve(__dirname,'..')}={}){
 try{
  let selected=false,json=false,groupBy='plugin',grouped=false;
  for(let at=0;at<args.length;at++){
   const arg=args[at];if(arg==='--list-plugins'&&!selected)selected=true;
   else if(arg==='--json'&&!json)json=true;
   else if(arg==='--group-by'&&!grouped&&at+1<args.length){groupBy=args[++at];grouped=true;}
   else registry.fail('plugin-view','Use --list-plugins [--json] [--group-by plugin|point] as one read-only operation');
  }
  if(!selected||!['plugin','point'].includes(groupBy))registry.fail('plugin-view','Use --list-plugins [--json] [--group-by plugin|point]');
  const view=managementInventory(root,{source});
  process.stdout.write(json?JSON.stringify(view,null,2)+'\n':formatInventory(view,{groupBy}));return view.status==='ok'?0:view.status==='drift'?1:2;
 }catch(error){process.stderr.write(error.message+'\n');return 2;}
}
module.exports={inventory,formatInventory,prepareRemoval,applyRemoval,applyManagementChange,prepareUnbind,prepareActivation,forgetKnown,listMain,
 managementInventory,prepareManagerRequest,inspectManagerProposal,applyManagerProposal};
