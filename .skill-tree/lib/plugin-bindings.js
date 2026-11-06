'use strict';
const crypto=require('node:crypto'),path=require('node:path');
const parameters=require('./plugin-parameters.js');
const own=(value,key)=>Object.hasOwn(value,key);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const kinds=new Set(['request','project','document','snapshot','management','controller','pending','task','task-group','review']);
const phases=['before','during','after'];
const compiledConfigurations=new WeakSet(),selectedEvents=new WeakMap();
const validId=value=>typeof value==='string'&&/^[a-z][a-z0-9-]*$/.test(value);
const text=value=>typeof value==='string'&&Boolean(value.trim())&&!/[\x00-\x1f]/.test(value);
const clone=value=>parameters.resolveParameters({run:{values:value}}).values;
function fail(code,message){const error=Error(message);error.code=code;throw error;}
function field(value,key,fallback){
 const descriptor=Object.getOwnPropertyDescriptor(value,key);
 if(!descriptor)return fallback;
 if(!own(descriptor,'value'))fail('binding-definition','Binding definitions cannot contain accessors');
 return descriptor.value;
}
function stable(value){
 if(Array.isArray(value))return value.map(stable);
 if(object(value))return Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])]));
 return value;
}
const digest=value=>crypto.createHash('sha256').update(JSON.stringify(stable(value))).digest('hex');
const normalized=value=>value.normalize('NFC').trim().replace(/\s+/g,' ').toLowerCase();
function freezeData(value){
 if(value!==null&&typeof value==='object'&&!Object.isFrozen(value)){for(const child of Object.values(value))freezeData(child);Object.freeze(value);}
 return value;
}
function portableCatalog(catalog){return clone({operations:field(catalog,'operations'),entries:field(catalog,'entries'),aliases:field(catalog,'aliases',[]),digest:field(catalog,'digest')});}
function verifiedCatalog(catalog){
 try{
  if(!object(catalog)||!object(field(catalog,'boundaries')))return false;
  const metadata=portableCatalog(catalog),{digest:identity,...content}=metadata;
  if(!Array.isArray(metadata.operations)||!Array.isArray(metadata.entries)||!Array.isArray(metadata.aliases)||identity!==digest(content))return false;
  for(const entry of metadata.entries){
   if(entry.status!=='resolved')continue;
   const boundary=own(catalog.boundaries,entry.boundary_id)?field(catalog.boundaries,entry.boundary_id):null;
   if(!object(boundary)||typeof field(boundary,'handler')!=='function'||field(boundary,'operation')!==entry.operation||field(boundary,'version')!==entry.version||digest(contextKinds(field(boundary,'context_kinds')))!==digest(entry.context_kinds))return false;
  }
  return true;
 }catch{return false;}
}
function contextKinds(value){
 if(!Array.isArray(value)||!value.length||value.some(kind=>!kinds.has(kind))||new Set(value).size!==value.length)fail('binding-anchor','A trusted boundary requires explicit supported context kinds');
 return [...value];
}
function catalogEntry(operation,anchor,boundaryId,boundaries){
 const boundary=own(boundaries,boundaryId)?boundaries[boundaryId]:null;
 if(!boundary||boundary.operation!==operation||typeof boundary.handler!=='function')return {operation,anchor,boundary_id:boundaryId,status:'unresolved',reason:'The registered anchor has no matching owned callable boundary'};
 return {operation,anchor,boundary_id:boundaryId,status:'resolved',context_kinds:[...boundary.context_kinds],version:boundary.version};
}

/** Host code supplies callable boundaries; configuration supplies only names and aliases. */
function createAnchorCatalog(operations,{boundaries={},named=[],aliases=[]}={}){
 if(!object(operations)||!object(boundaries)||!Array.isArray(named)||!Array.isArray(aliases))fail('binding-anchor','An owned operation catalog and explicit boundary declarations are required');
 const names=Object.keys(operations).sort();
 if(names.some(name=>!/^skill-tree-[a-z0-9-]+$/.test(name)))fail('binding-anchor','The operation catalog contains an invalid owned operation name');
 const handlers=Object.create(null);
 for(const id of Object.keys(boundaries)){
  if(!text(id))fail('binding-anchor','A boundary requires an exact identity');
  const value=field(boundaries,id);
  if(!object(value))fail('binding-anchor','A trusted boundary requires a structured declaration');
  const operation=field(value,'operation'),handler=field(value,'handler');
  // Noncallable labels remain visible unresolved locations, never executable registrations.
  if(typeof handler!=='function'||!names.includes(operation))continue;
  const version=field(value,'version');if(!text(version))fail('binding-anchor','A callable boundary requires an implementation version');
  handlers[id]={operation,handler,version,context_kinds:contextKinds(field(value,'context_kinds'))};
 }
 const entries=names.flatMap(operation=>phases.map(anchor=>catalogEntry(operation,anchor,operation+':'+anchor,handlers))),seen=new Set(entries.map(entry=>entry.operation+':'+entry.anchor));
 for(const record of clone(named)){
  if(!object(record)||!text(record.operation)||!validId(record.name)||!text(record.boundary))fail('binding-anchor','A named anchor requires an operation, name and actual boundary identity');
  const key=record.operation+':'+record.name;
  if(seen.has(key))fail('binding-anchor','Duplicate anchor registration: '+key);
  seen.add(key);entries.push(catalogEntry(record.operation,record.name,record.boundary,handlers));
 }
 const mapped=[];
 for(const operation of names){
  for(const anchor of phases){
   mapped.push({phrase:normalized(anchor+' '+operation),operation,anchor});
   const definition=field(operations,operation);
   if(object(definition)&&text(field(definition,'title')))mapped.push({phrase:normalized(anchor+' '+field(definition,'title')),operation,anchor});
  }
 }
 for(const record of clone(aliases)){
  if(!object(record)||!text(record.phrase)||!text(record.operation)||!validId(record.anchor))fail('binding-anchor','A location alias requires text and an exact operation/anchor mapping');
  mapped.push({phrase:normalized(record.phrase),operation:record.operation,anchor:record.anchor});
 }
 const identity={operations:names,entries,aliases:mapped};
 return freezeData({...identity,boundaries:handlers,digest:digest(identity)});
}

function resolveLocation(request,catalog){
 if(!verifiedCatalog(catalog))return {status:'unresolved',reason:'A current owned callable boundary catalog must be rebuilt before location resolution'};
 let operation,anchor;
 if(typeof request==='string'){
  const canonical=catalog.entries.filter(entry=>normalized(entry.operation+':'+entry.anchor)===normalized(request));
  if(canonical.length===1){operation=canonical[0].operation;anchor=canonical[0].anchor;}
  else{
   const matches=(catalog.aliases||[]).filter(alias=>alias.phrase===normalized(request)),keys=[...new Set(matches.map(row=>row.operation+':'+row.anchor))];
   if(keys.length>1)return {status:'unresolved',request,reason:'The requested location alias is ambiguous'};
   if(!keys.length)return {status:'unresolved',request,reason:'The requested location has no registered anchor mapping'};
   operation=matches[0].operation;anchor=matches[0].anchor;
  }
 }else if(object(request)){
  operation=field(request,'operation');anchor=field(request,'anchor');
 }else return {status:'unresolved',reason:'A location requires an exact operation/anchor or declared alias'};
 const entry=catalog.entries.find(row=>row.operation===operation&&row.anchor===anchor);
 return entry?clone(entry):{status:'unresolved',operation:typeof operation==='string'?operation:'',anchor:typeof anchor==='string'?anchor:'',reason:'The operation or anchor is not registered'};
}

function pointerParts(pointer){
 if(typeof pointer!=='string'||pointer!==''&&!pointer.startsWith('/')||/~(?:[^01]|$)/.test(pointer))fail('binding-condition','Conditions require valid JSON-pointer paths');
 return pointer===''?[]:pointer.slice(1).split('/').map(part=>part.replace(/~1/g,'/').replace(/~0/g,'~'));
}
function conditionSpec(condition,depth=0){
 if(condition===undefined||typeof condition==='boolean')return;
 if(depth>32||!object(condition)||Object.keys(condition).length!==1)fail('binding-condition','A condition requires one supported declarative operator');
 const operator=Object.keys(condition)[0],value=condition[operator];
 if(['all','any'].includes(operator)){
  if(!Array.isArray(value)||!value.length)fail('binding-condition','A composite condition requires a nonempty condition list');
  value.forEach(child=>conditionSpec(child,depth+1));
 }else if(operator==='not')conditionSpec(value,depth+1);
 else if(operator==='present')pointerParts(value);
 else if(['equals','in'].includes(operator)){
  if(!object(value)||!own(value,'path')||Object.keys(value).some(key=>!['path',operator==='equals'?'value':'values'].includes(key))||!own(value,operator==='equals'?'value':'values'))fail('binding-condition','A comparison condition requires an explicit path and value');
  pointerParts(value.path);if(operator==='in'&&!Array.isArray(value.values))fail('binding-condition','Membership requires a JSON value list');
 }else fail('binding-condition','Unsupported declarative condition operator: '+operator);
}
function lookup(context,pointer){
 let current=context;
 for(const key of pointerParts(pointer)){
  if(current===null||typeof current!=='object'||!own(current,key))return {present:false};
  current=current[key];
 }
 return {present:true,value:current};
}
function conditionMatches(condition,context){
 if(condition===undefined)return true;if(typeof condition==='boolean')return condition;
 if(own(condition,'all'))return condition.all.every(item=>conditionMatches(item,context));
 if(own(condition,'any'))return condition.any.some(item=>conditionMatches(item,context));
 if(own(condition,'not'))return !conditionMatches(condition.not,context);
 if(own(condition,'present'))return lookup(context,condition.present).present;
 const comparison=condition.equals||condition.in,actual=lookup(context,comparison.path);
 if(!actual.present)return false;
 return own(condition,'equals')?digest(actual.value)===digest(comparison.value):comparison.values.some(value=>digest(actual.value)===digest(value));
}
function contextIds(values,prefix){return Array.isArray(values)&&values.length>0&&new Set(values).size===values.length&&values.every(value=>typeof value==='string'&&new RegExp('^'+prefix+'-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$').test(value));}
function validateContext(context){
 const value=clone(context);
 if(!object(value)||!kinds.has(value.kind)||!text(value.id))fail('binding-context','A typed operation context requires an exact kind and identity');
 if(['document','snapshot'].includes(value.kind)){
  if(!Array.isArray(value.paths)||!value.paths.length||value.paths.some(rel=>typeof rel!=='string'||!rel||path.isAbsolute(rel)||path.win32.isAbsolute(rel)||rel.includes('\\')||rel.includes('\0')||rel.split('/').includes('..')))fail('binding-context','Document and snapshot contexts require bounded repository-relative paths');
 }
 if(value.kind==='controller'&&!contextIds([value.run_id],'WR'))fail('binding-context','A controller context requires the actual run identity');
 const allowedIdentityFields={pending:['pending_ids'],task:['task_ids','pending_ids'],'task-group':['task_ids','pending_ids'],controller:['task_ids'],review:['task_ids']}[value.kind]||[];
 for(const key of ['task_ids','pending_ids'])if(own(value,key)&&!allowedIdentityFields.includes(key))fail('binding-context','Task identity fields do not apply to the selected context kind');
 if(value.kind==='pending'&&(!contextIds(value.pending_ids,'P')||value.task_ids!==undefined))fail('binding-context','A pre-promotion context requires real Pending identities without premature task identities');
 if(['task','task-group'].includes(value.kind)&&(!contextIds(value.task_ids,'T')||value.kind==='task'&&value.task_ids.length!==1))fail('binding-context','A task context requires real selected task identities');
 if(value.pending_ids!==undefined&&!contextIds(value.pending_ids,'P')||value.task_ids!==undefined&&!contextIds(value.task_ids,'T'))fail('binding-context','Context task and Pending identities must retain the actual typed forms');
 if(value.kind==='review'&&[value.head,value.base_oid].some(oid=>typeof oid!=='string'||!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(oid)))fail('binding-context','A review context requires current head and base identities');
 return value;
}

function compileBindings(bindings,options={}){
 if(!object(options))fail('binding-definition','Binding compilation requires structured options');
 const packages=field(options,'packages'),catalog=field(options,'catalog'),parameterDefaults=clone(field(options,'parameterDefaults',{})),runOverrides=clone(field(options,'runOverrides',{}));
 if(!object(parameterDefaults)||!object(runOverrides))fail('binding-definition','Parameter defaults and run overrides require identity-keyed JSON maps');
 if(!Array.isArray(bindings)||!object(packages))fail('binding-definition','Compile bindings against installed packages and the trusted anchor catalog');
 if(!verifiedCatalog(catalog))fail('binding-anchor','A current owned callable boundary catalog is required before compilation');
 const rows=clone(bindings),seen=new Set();
 for(const row of rows){
  if(!object(row)||!validId(row.id)||seen.has(row.id))fail('binding-identity','Binding occurrences require unique stable identities');
  seen.add(row.id);
  if(!validId(row.plugin_id)||!own(packages,row.plugin_id))fail('binding-plugin','A binding requires an installed plugin identity');
  if(!text(row.operation)||!validId(row.anchor)||typeof row.enabled!=='boolean')fail('binding-definition','A binding requires an exact operation, anchor and enabled state');
  if(['authority','context','event','attempt_id','delivery_key','input_digest','configuration_digest','effective','location','package_identity'].some(key=>own(row,key)))fail('binding-definition','Plugin data cannot replace core identity, authority or compiled execution fields');
  conditionSpec(row.condition);
  const defaults=own(parameterDefaults,row.plugin_id)?parameterDefaults[row.plugin_id]:{},occurrence={};
  if(!object(defaults))fail('binding-definition','Plugin parameter defaults require structured layers');
  if(own(row,'parameters'))occurrence.values=row.parameters;
  if(own(row,'instructions'))occurrence.instructions=row.instructions;
  const options={upstream:defaults.upstream,project:defaults.project,binding:occurrence,run:own(runOverrides,row.id)?runOverrides[row.id]:undefined};
  if(own(defaults,'schema'))options.schema=defaults.schema;
  row.effective=parameters.resolveParameters(options);row.location=resolveLocation(row,catalog);
  const adaptation=packages[row.plugin_id]?.adaptation||{};
  if(own(adaptation,'context_kinds'))row.context_kinds=contextKinds(adaptation.context_kinds);
  row.package_identity=Object.fromEntries(['revision','content_digest'].filter(key=>own(packages[row.plugin_id],key)).map(key=>[key,packages[row.plugin_id][key]]));
 }
 const result={bindings:rows,catalog,portable_catalog:portableCatalog(catalog),configuration_digest:digest({bindings:rows,catalog_digest:catalog.digest})};
 compiledConfigurations.add(result);return freezeData(result);
}
function validateEvent(event){
 const value=clone(event);
 if(!object(value)||!text(value.id)||!text(value.operation)||!validId(value.anchor)||own(value,'attempt_id')&&!text(value.attempt_id)||own(value,'boundary_id')&&!text(value.boundary_id))fail('binding-event','A dispatch event requires an exact operation, anchor and event identity');
 return value;
}
function selectBindings(compiled,event,context){
 if(!compiledConfigurations.has(compiled)||!verifiedCatalog(compiled.catalog)||compiled.configuration_digest!==digest({bindings:compiled.bindings,catalog_digest:compiled.catalog.digest}))fail('binding-definition','Select from the current immutable compiled binding configuration');
 const current=validateContext(context),selectedEvent=validateEvent(event),location=resolveLocation(selectedEvent,compiled.catalog),selected=[],unresolved=[];
 if(own(selectedEvent,'boundary_id')&&(location.status!=='resolved'||selectedEvent.boundary_id!==location.boundary_id))fail('binding-event','The event boundary does not match the current trusted operation/anchor');
 if(location.status==='resolved')selectedEvent.boundary_id=location.boundary_id;
 for(const row of compiled.bindings){
  if(!row.enabled||row.operation!==selectedEvent.operation)continue;
  if(row.anchor!==selectedEvent.anchor&&!(row.location.status==='resolved'&&location.status==='resolved'&&row.location.boundary_id===location.boundary_id))continue;
  if(!conditionMatches(row.condition,current))continue;
  if(row.location.status!=='resolved'){unresolved.push({id:row.id,reason:row.location.reason});continue;}
  if(!row.location.context_kinds.includes(current.kind)||row.context_kinds&&!row.context_kinds.includes(current.kind)){unresolved.push({id:row.id,reason:'The registered boundary or plugin requires a compatible typed context'});continue;}
  selected.push(clone(row));
 }
 selectedEvents.set(selectedEvent,{catalog:compiled.catalog,operation:selectedEvent.operation,anchor:selectedEvent.anchor,boundary_id:selectedEvent.boundary_id});
 return freezeData({bindings:selected,unresolved,context:current,event:selectedEvent,configuration_digest:compiled.configuration_digest});
}
function orderedCopy(bindings){
 const result=clone(bindings);
 if(!Array.isArray(result)||result.some(row=>!object(row)||!validId(row.id))||new Set(result.map(row=>row.id)).size!==result.length)fail('binding-identity','Ordered occurrences require unique exact identities');
 return result;
}
function moveBinding(bindings,id,index){
 const result=orderedCopy(bindings),current=result.findIndex(row=>row.id===id);
 if(current<0)fail('binding-identity','The selected occurrence does not exist');
 if(!Number.isInteger(index)||index<0||index>=result.length)fail('binding-order','The requested occurrence position is outside the configured chain');
 const [row]=result.splice(current,1);result.splice(index,0,row);return result;
}
function removeBinding(bindings,id){
 const result=orderedCopy(bindings),index=result.findIndex(row=>row.id===id);
 if(index<0)fail('binding-identity','The selected occurrence does not exist');result.splice(index,1);return result;
}
function dispatchIdentity(binding,event,context,inputs={}){
 const row=clone(binding),selectedEvent=validateEvent(event),current=validateContext(context),values=clone(inputs);
 if(!object(row)||!validId(row.id)||row.operation!==selectedEvent.operation)fail('binding-event','The occurrence and dispatch event must identify the same owned operation');
 const boundary_id=row.location?.boundary_id||row.operation+':'+row.anchor;
 if(row.anchor!==selectedEvent.anchor){
  const verified=selectedEvents.get(event);
  if(!verified||!verifiedCatalog(verified.catalog)||verified.operation!==selectedEvent.operation||verified.anchor!==selectedEvent.anchor||verified.boundary_id!==boundary_id||selectedEvent.boundary_id!==boundary_id)fail('binding-event','A named occurrence requires the actual selected trusted boundary event');
 }else if(own(selectedEvent,'boundary_id')&&selectedEvent.boundary_id!==boundary_id)fail('binding-event','The occurrence and event boundary identities differ');
 const identity={binding_id:row.id,boundary_id,operation:selectedEvent.operation,anchor:selectedEvent.anchor,event_id:selectedEvent.id,attempt_id:selectedEvent.attempt_id||null};
 return {...identity,binding_anchor:row.anchor,delivery_key:digest(identity),input_digest:digest({context:current,inputs:values,binding:row})};
}
function classifyDelivery(identity,previous){
 if(!identity||!text(identity.delivery_key)||!text(identity.input_digest))fail('binding-replay','A delivery requires exact key and input identities');
 if(previous===undefined||previous===null)return 'new';
 if(previous.delivery_key!==identity.delivery_key)return 'distinct';
 if(previous.input_digest!==identity.input_digest)fail('binding-replay','The original delivery key has conflicting input or configuration');return 'replay';
}
function enterLineage(lineage,identity){
 const result=clone(lineage),current=clone(identity);
 if(!Array.isArray(result)||result.length>=64||!validId(current.binding_id)||!text(current.boundary_id))fail('binding-recursion','Active dispatch lineage is invalid or exceeds the bounded depth');
 if(result.some(entry=>!object(entry)||!validId(entry.binding_id)||!text(entry.boundary_id)))fail('binding-recursion','Active dispatch lineage contains an invalid occurrence');
 if(result.some(entry=>entry.binding_id===current.binding_id&&entry.boundary_id===current.boundary_id))fail('binding-recursion','The same binding occurrence recursively re-enters its active boundary');
 result.push(current);return result;
}
module.exports={createAnchorCatalog,resolveLocation,compileBindings,validateContext,selectBindings,moveBinding,removeBinding,dispatchIdentity,classifyDelivery,enterLineage};
