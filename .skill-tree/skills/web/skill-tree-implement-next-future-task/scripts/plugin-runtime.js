'use strict';
// Owned preparation only. Native host execution remains outside this module.
const fs=require('node:fs'),crypto=require('node:crypto');
const composition=require('./plugin-composition.js'),bindings=require('./plugin-bindings.js'),parameters=require('./plugin-parameters.js'),registry=require('./plugin-registry.js');
const own=(value,key)=>Object.hasOwn(value,key),object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const clone=value=>parameters.resolveParameters({run:{values:value}}).values;
function canonical(value){if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';if(object(value))return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';return JSON.stringify(value);}
const digest=value=>crypto.createHash('sha256').update(canonical(clone(value))).digest('hex');
const bytesHash=value=>crypto.createHash('sha256').update(value).digest('hex');
function fail(code,message){const error=Error(message);error.code=code;throw error;}
function same(left,right){return canonical(left)===canonical(right);}
function snapshot(packageRoot,manifest,projectRoot){
 const result={};
 const library=new Set(['plugin-runtime.js','plugin-composition.js','plugin-bindings.js','plugin-parameters.js','plugin-registry.js','plugin-sources.js']);
 const common=new Set(['workflow-state.py','plugin-invocation.py','run-workspaces.py','decision-governance.py','decision-orchestration.py','validate-document-rules.py','plugin-hooks.js']);
 for(const [relative,sum]of Object.entries(manifest.owned_resources)){
  if(relative.startsWith('scripts/')&&library.has(relative.slice(8)))result['lib/'+relative.slice(8)]=sum;
  else if(relative.startsWith('scripts/')&&common.has(relative.slice(8)))result['common/scripts/'+relative.slice(8)]=sum;
  else if(relative.startsWith('references/')&&['decision-governance.md','validation-policy.md'].includes(relative.slice(11)))result['common/'+relative]=sum;
  result['owned/'+relative]=sum;
 }
 result['operation-manifest']=bytesHash(fs.readFileSync(registry.safe(packageRoot,'references/plugin-bindings.json')));
 const profile=registry.safe(projectRoot,'.skill-tree/installation/profile.json');result['owned-profile']=fs.existsSync(profile)?bytesHash(fs.readFileSync(profile)):null;
 return result;
}
function supportedAdapter(request){
 const adapter=request.adapter||{provider:'codex',mechanism:'source-backed-context'};
 return adapter.provider==='codex'&&adapter.mechanism==='source-backed-context'&&Array.isArray(request.capabilities)&&request.capabilities.includes('codex-source-backed-context');
}
function executionPolicy(value){
 const policy=clone(value||{allowed_tools:['read-pinned-resources','read-scoped-context'],allowed_actions:['return-proposals']});
 if(!object(policy))fail('runtime-authority','An owned execution policy is required');
 for(const key of ['allowed_tools','allowed_actions'])if(!Array.isArray(policy[key])||policy[key].some(item=>typeof item!=='string'||!item)||new Set(policy[key]).size!==policy[key].length)fail('runtime-authority','Allowed tools and actions require distinct bounded names');return policy;
}
function compiledConfiguration(manifest,runOverrides={},policyValue){
 const catalog=composition.createCatalog(manifest.operations),compiled=bindings.compileBindings(manifest.definitions,{packages:manifest.packages,catalog,parameterDefaults:manifest.parameter_defaults,runOverrides});
 const policy=executionPolicy(policyValue);
 return {catalog,compiled,configuration:{configuration_digest:digest({binding_configuration_digest:compiled.configuration_digest,execution_policy:policy}),binding_configuration_digest:compiled.configuration_digest,execution_policy:policy,bindings:clone(compiled.bindings),definitions:clone(manifest.definitions),packages:clone(manifest.packages),parameter_defaults:clone(manifest.parameter_defaults),run_overrides:clone(runOverrides),manifest_identity:manifest.identity,operation:manifest.operation}};
}
function proofFor(packageRoot,manifest,request,configuration,compiled,catalog){
 const selection=bindings.selectBindings(compiled,request.event,request.context),boundary=composition.prepareBoundary(packageRoot,request);
 const prerequisites=boundary.prerequisites.filter(item=>item.code!=='invocation-unqualified'||!supportedAdapter(request));
 if(selection.bindings.length&&!supportedAdapter(request))prerequisites.push({code:'unsupported-adapter',reason:'The current host must explicitly support the source-backed Codex context adapter.'});
 return {configuration_digest:configuration.configuration_digest,context:clone(selection.context),event:clone(selection.event),bindings:clone(selection.bindings),unresolved:clone(selection.unresolved),prerequisites:clone(prerequisites),execution_snapshot:snapshot(packageRoot,manifest,request.project_root),guard:boundary.guard||null,adapter:{provider:'codex',mechanism:'source-backed-context',native_skill_tool:false}};
}
function freezePlan(packageRoot,payload){
 const request=clone(payload),{manifest}=composition.verifiedManifest(packageRoot),{configuration,compiled,catalog}=compiledConfiguration(manifest,request.run_overrides||{},request.execution_policy);
 if(request.event?.operation!==manifest.operation)fail('runtime-operation','The hook event differs from the composed operation');
 return {configuration,proof:proofFor(packageRoot,manifest,request,configuration,compiled,catalog)};
}
function occurrencePlan(packageRoot,payload){
 const request=clone(payload),{manifest}=composition.verifiedManifest(packageRoot),frozen=request.configuration;
 if(!object(frozen)||frozen.operation!==manifest.operation||request.event?.operation!==manifest.operation)fail('runtime-configuration','The frozen operation configuration is required');
 if(frozen.manifest_identity!==manifest.identity)return {configuration_digest:frozen.configuration_digest,context:clone(request.context),event:clone(request.event),bindings:[],unresolved:[],prerequisites:[{code:'configuration-stale',reason:'The owned operation changed; explicitly reconcile the frozen chain before continuation.'}],execution_snapshot:snapshot(packageRoot,manifest,request.project_root)};
 const current=compiledConfiguration(manifest,frozen.run_overrides||{},frozen.execution_policy);
 if(!same(current.configuration,frozen))fail('runtime-configuration','The recorded frozen configuration differs from the owned definitions and explicit overrides');
 return proofFor(packageRoot,manifest,request,current.configuration,current.compiled,current.catalog);
}
function resolvePrivate(value,resolver,secrets){
 if(object(value)&&Object.keys(value).length===1&&own(value,'$secret')){
  const name=value.$secret;if(typeof name!=='string'||!name||typeof resolver!=='function')fail('runtime-secret','A permitted invocation-context secret provider is required');
  let resolved;try{resolved=resolver(name);}catch{fail('runtime-secret','The invocation-context secret provider is unavailable');}
  if(resolved===undefined)fail('runtime-secret','The invocation-context secret provider did not resolve a required reference');
  const safe=clone(resolved);secrets.push(safe);return safe;
 }
 if(Array.isArray(value))return value.map(item=>resolvePrivate(item,resolver,secrets));
 if(object(value))return Object.fromEntries(Object.keys(value).map(key=>[key,resolvePrivate(value[key],resolver,secrets)]));return value;
}
function deliveryData(packageRoot,payload,resolveSecret){
 const request=clone(payload),proof=occurrencePlan(packageRoot,request),input=request.public_input;
 if(proof.prerequisites.length||proof.unresolved.length)fail('runtime-prerequisite','The current hook preparation has unresolved prerequisites');
 if(!object(input)||typeof request.input_digest!=='string'||!/^[a-f0-9]{64}$/.test(request.input_digest))fail('runtime-input','The original public attempt and exact input digest are required');
 const row=proof.bindings.find(item=>item.id===request.binding_id||item.id===input.binding_id);
 if(!row)fail('runtime-binding','The original binding is not eligible in the current accepted context');
 const owned=composition.verifiedManifest(packageRoot),rebuilt=compiledConfiguration(owned.manifest,request.configuration.run_overrides||{},request.configuration.execution_policy);
 const deliverySelection=bindings.selectBindings(rebuilt.compiled,{...request.event,attempt_id:request.attempt_id},request.context),deliveryRow=deliverySelection.bindings.find(item=>item.id===row.id);
 if(!deliveryRow)fail('runtime-binding','The actual invocation occurrence is no longer selected');
 const record=request.configuration.packages[row.plugin_id],secrets=[];
 const grant=clone(request.authority);if(!object(grant)||!same(grant,input.authority)||grant.context_id!==input.context?.id||!Array.isArray(grant.constraints)||!grant.constraints.length)fail('runtime-authority','The exact sealed bounded core authority must accompany private delivery');
 const policy=executionPolicy(request.configuration.execution_policy);
 if(!same(policy,input.execution_policy))fail('runtime-authority','Private delivery must retain the sealed allowed tools and actions');
 if(!same(input.context,proof.context)||!same(input.event,proof.event)||input.chain_id!==request.chain_id||input.attempt_id!==request.attempt_id||input.binding_id!==row.id||input.configuration_digest!==request.configuration.configuration_digest)fail('runtime-input','Private delivery must retain the exact sealed occurrence and accepted context');
 if(request.execution_policy!==undefined&&!same(policy,executionPolicy(request.execution_policy)))fail('runtime-authority','Private delivery cannot replace the frozen allowed tools or actions');
 const values=resolvePrivate(row.effective.values,resolveSecret,secrets),options={run:{values,instructions:row.effective.instructions}};
 // The declared configuration schema already validated references before private resolution.
 const resolved=parameters.resolveParameters(options);
 const dispatch=bindings.dispatchIdentity(deliveryRow,deliverySelection.event,deliverySelection.context,{configuration_digest:request.configuration.configuration_digest,parameters:resolved.values,extra_instructions:resolved.instructions});
 const data={dispatch_identity:dispatch,mechanism:'source-backed-context',provider:'codex',mode:input.mode,authority:grant,authority_digest:input.authority_digest,allowed_tools:policy.allowed_tools,allowed_actions:policy.allowed_actions,chain_id:request.chain_id,attempt_id:request.attempt_id,binding_id:row.id,event:clone(proof.event),plugin:{plugin_id:row.plugin_id,revision:record.revision,content_digest:record.content_digest,entry:record.entry,resource_digests:clone(record.files)},context:clone(proof.context),scope_source_snapshot:clone(input.scope_source_snapshot||{}),parameters:resolved.values,extra_instructions:resolved.instructions,input_digest:request.input_digest};
 if([data.chain_id,data.attempt_id].some(value=>typeof value!=='string'||!value))fail('runtime-input','The actual chain and original attempt identities are required');
 return {payload:data,dispatch_identity:dispatch,input_digest:request.input_digest,delivery_digest:digest(data),resolved_parameter_digest:resolved.digest,configuration_parameter_digest:row.effective.digest,contains_secrets:secrets.length>0};
}
module.exports={freezePlan,occurrencePlan,deliveryData,canonical,digest};
