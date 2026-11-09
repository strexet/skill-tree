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
 else if(view.catalog){
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
function applyManagementChange(root,proposal,confirmation){proposal=clone(proposal||{});if(!proposal||!['uninstall','configure','enable','disable'].includes(proposal.operation))registry.fail('plugin-action','Select a supported installed-package management proposal');managementSemantics(root,proposal);return require('./plugin-lifecycle.js').applyProposal(root,proposal,confirmation);}
function applyRemoval(root,proposal,confirmation){proposal=clone(proposal||{});if(proposal?.operation!=='uninstall')registry.fail('plugin-action','Package removal requires the original uninstall proposal');return applyManagementChange(root,proposal,confirmation);}
function forgetKnown(){registry.fail('plugin-known-owner','Forgetting a known definition is separate from installed package removal and requires the known-definition owner');}
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
  const view=inventory(root,{operations:operationsFor(source)});
  try{
   const bundled=path.resolve(source)===path.resolve(root,'.skill-tree/installation/source');
   if(bundled){
    if(!view.profile){
     const core=require('./installation.js');
     core.verifyOwned(root,core.receipt(root,true));
    }else if(view.issues.some(item=>item.scope==='core-receipt'))registry.fail('plugin-catalog','The bundled catalog ownership could not be verified');
   }
   const catalog=require('./plugin-catalog.js');
   view.catalog=catalog.catalogView(catalog.loadCatalog(source),{inventory:view});
  }catch(error){
   view.catalog={status:'unavailable',reason:error.code==='plugin-catalog'?error.message:'Owned catalog metadata could not be read'};
  }
  process.stdout.write(json?JSON.stringify(view,null,2)+'\n':formatInventory(view,{groupBy}));return view.status==='ok'?0:view.status==='drift'?1:2;
 }catch(error){process.stderr.write(error.message+'\n');return 2;}
}
module.exports={inventory,formatInventory,prepareRemoval,applyRemoval,applyManagementChange,prepareUnbind,prepareActivation,forgetKnown,listMain};
