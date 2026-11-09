'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const registry=require('./plugin-registry.js'),sources=require('./plugin-sources.js'),acquisition=require('./plugin-acquisition.js'),parameters=require('./plugin-parameters.js');
const core=require('./installation.js');
const own=(value,key)=>Object.hasOwn(value,key),clone=value=>parameters.resolveParameters({run:{values:value}}).values;
const WORKFLOW='.skill-tree/documents/future.json';
function requestId(value){if(typeof value!=='string'||!value||value.length>200||/[\x00-\x1f]/.test(value))registry.fail('plugin-request','A stable plugin request identity is required');return value;}
function coreProfile(root){const profile=core.receipt(root,true);core.verifyOwned(root,profile);return profile;}
function targetIdentity(root){return registry.hash(fs.realpathSync(root));}
function stoppedHandoff(root){
 if(core.hasActiveOperation(root))registry.fail('plugin-active','Active invocations must reach a stopped cleanup/handoff before plugin mutation');
 if(core.queueRoot(root)!==fs.realpathSync(root)){
  const state=core.workflowState(root),runs=state?(state.run_registry?Object.values(state.run_registry.runs):[state.active_run]):[];
  const terminal=run=>run?.delivery?.implementation==='completed'&&(run.delivery.status==='merged'||run.delivery.status==='local-result'&&!run.delivery.authorization?.merge&&!run.delivery.authorization?.pr||run.delivery.status==='pr-ready'&&!run.delivery.authorization?.merge);
  if(runs.some(run=>run&&!terminal(run)&&!run.stop_reason))registry.fail('plugin-active','Linked installation requires an explicit canonical stopped handoff before plugin mutation');
 }
}
function encodeSnapshot(snapshot){sources.verifySnapshot(snapshot);return {...clone({...snapshot,files:{}}),files:Object.fromEntries(Object.entries(snapshot.files).map(([rel,bytes])=>[rel,Buffer.from(bytes).toString('base64')]))};}
function decodeSnapshot(encoded){
 if(!encoded||!encoded.files||typeof encoded.files!=='object'||Array.isArray(encoded.files))registry.fail('plugin-snapshot','A serialized source snapshot is required');
 const files=Object.create(null);
 for(const [rel,value]of Object.entries(encoded.files)){registry.relative(rel);if(typeof value!=='string'||Buffer.from(value,'base64').toString('base64')!==value)registry.fail('plugin-snapshot','Snapshot bytes require exact base64 encoding');files[rel]=Buffer.from(value,'base64');}
 const snapshot={...clone({...encoded,files:{}}),files};sources.verifySnapshot(snapshot);return snapshot;
}
function packageFiles(snapshot){
 const files=Object.fromEntries(Object.entries(snapshot.files).map(([rel,bytes])=>['upstream/'+rel,Buffer.from(bytes)]));
 files['overlay/adapter.json']=Buffer.from(registry.json(snapshot.adaptation));return files;
}
function packageRecord(snapshot,dependencies=[]){
 const files=packageFiles(snapshot),{files:ignored,...descriptor}=snapshot;
 if(!Array.isArray(dependencies)||dependencies.some(id=>!registry.validId(id)))registry.fail('plugin-dependency','Package dependency identities require a list');
 return {id:snapshot.plugin_id,destination:registry.PACKAGES+'/'+snapshot.plugin_id,entry:'upstream/'+snapshot.entry,source:clone(snapshot.source),revision:snapshot.revision,content_digest:snapshot.content_digest,files:Object.fromEntries(Object.entries(files).map(([rel,bytes])=>[rel,registry.hash(bytes)])),package_dependencies:[...new Set(dependencies)],metadata:clone(snapshot.metadata),adaptation:clone(snapshot.adaptation),execution:clone(snapshot.execution),snapshot:clone(descriptor)};
}
function bindings(value,packages){
 if(!Array.isArray(value))registry.fail('plugin-binding','Bindings require an ordered occurrence list');
 const result=clone(value).map(binding=>({...binding,enabled:binding.enabled===undefined?true:binding.enabled}));
 registry.validateBindings(result,packages);return result;
}
function proposalDigest(proposal){const {digest,...content}=proposal;return registry.hash(registry.json(content));}
function providerScope(profile){
 const destinations=Object.fromEntries(Object.entries(profile.destinations).map(([relative,record])=>[
  relative,{name:record.name,providers:[...(record.providers||[record.provider])].sort()}
 ]));
 return {flavor:profile.flavor,destinations};
}
function assertProviderScope(proposal,profile){
 if(own(proposal,'provider_scope')&&registry.json(proposal.provider_scope)!==registry.json(providerScope(profile)))
  registry.fail('plugin-stale','The confirmed provider or destination scope changed');
}
function makeProposal(root,request,base,profile,packages,nextBindings,snapshots,{bindProviderScope=false}={}){
 const proposed=registry.seal({...base,generation:base.generation+1,packages,bindings:nextBindings});registry.validateRegistry(proposed);
 const result={format:'skill-tree-plugin-proposal',schema:1,request_id:requestId(request.request_id),operation:request.operation,target_identity:targetIdentity(root),core_identity:profile.identity,base_generation:base.generation,base_registry_identity:base.identity,packages:clone(packages),bindings:clone(nextBindings),snapshots:clone(snapshots)};
 if(bindProviderScope)result.provider_scope=providerScope(profile);
 result.digest=proposalDigest(result);return result;
}
async function prepareProposal(root,request,options={}){
 request=clone(request);
 if(!request||typeof request!=='object'||!['install','update','configure','enable','disable','uninstall'].includes(request.operation))registry.fail('plugin-request','Select an explicit plugin lifecycle operation');
 requestId(request.request_id);const profile=coreProfile(root),base=registry.verifyInstalled(root),packages=clone(base.packages),snapshots={};let nextBindings=clone(base.bindings);
 if(['install','update'].includes(request.operation)){
  if(!Array.isArray(request.sources)||!request.sources.length)registry.fail('plugin-source','Plugin acquisition requires selected sources');
  const selected=new Set();
  for(const input of request.sources){
   const normalized=sources.normalizeSource(input,{known:options.known||{},baseDir:options.baseDir||root}),id=normalized.definition.id;
   if(selected.has(id))registry.fail('plugin-source','A source occurs twice in one package mutation');selected.add(id);
   if(options.dryRun&&normalized.definition.source.kind!=='local')return {action:'dry-run',prerequisites:['Explicit online source resolution is required before a remote proposal is actionable.']};
   if(request.operation==='update'&&!own(base.packages,id))registry.fail('plugin-source','An update requires an installed plugin');
   const snapshot=await sources.resolveSource(normalized,{acquire:options.acquire||acquisition.acquireRemote,availableCapabilities:options.availableCapabilities||[],expectedDigests:input.expectedDigests||{}});
   const dependencies=input.package_dependencies===undefined?(base.packages[id]?.package_dependencies||[]):input.package_dependencies;
   const record=packageRecord(snapshot,dependencies);
   if(request.operation==='install'&&own(base.packages,id)&&registry.json(base.packages[id])!==registry.json(record))registry.fail('plugin-source','An installed plugin changed; request an explicit update');
   packages[id]=record;snapshots[id]=encodeSnapshot(snapshot);
  }
  if(request.bindings!==undefined)nextBindings=bindings(request.bindings,packages);
 }else if(request.operation==='configure'){
  if(request.bindings===undefined)registry.fail('plugin-binding','Configuration requires the exact desired occurrence list');nextBindings=bindings(request.bindings,packages);
 }else if(['enable','disable'].includes(request.operation)){
  if(!Array.isArray(request.binding_ids)||!request.binding_ids.length||new Set(request.binding_ids).size!==request.binding_ids.length)registry.fail('plugin-binding','Select exact unique binding identities');
  for(const id of request.binding_ids){const item=nextBindings.find(binding=>binding.id===id);if(!item)registry.fail('plugin-binding','The selected binding does not exist');item.enabled=request.operation==='enable';}
 }else{
  if(!Array.isArray(request.plugin_ids)||!request.plugin_ids.length||new Set(request.plugin_ids).size!==request.plugin_ids.length)registry.fail('plugin-source','Uninstall requires exact unique installed plugin identities');
  for(const id of request.plugin_ids){if(!own(packages,id))registry.fail('plugin-source','The selected plugin is not installed');delete packages[id];}
  nextBindings=nextBindings.filter(binding=>!request.plugin_ids.includes(binding.plugin_id));
 }
 const result=makeProposal(root,request,base,profile,packages,nextBindings,snapshots,options);return options.dryRun?{action:'dry-run',proposal:result,prerequisites:[]}:result;
}
function validateProposal(root,proposal,confirmation){
 if(!proposal||proposal.format!=='skill-tree-plugin-proposal'||proposal.schema!==1||proposal.target_identity!==targetIdentity(root)||!['install','update','configure','enable','disable','uninstall','rollback'].includes(proposal.operation)||proposal.digest!==proposalDigest(proposal))registry.fail('plugin-proposal','The plugin proposal digest, target or content changed');
 requestId(proposal.request_id);
 if(!confirmation||confirmation.proposal_digest!==proposal.digest)registry.fail('plugin-consent','Explicit confirmation of the exact plugin proposal digest is required');
}
function snapshotChanges(proposal,base){
 const changes={};
 for(const [id,encoded]of Object.entries(proposal.snapshots||{})){
  if(!own(proposal.packages,id)||!registry.validId(id))registry.fail('plugin-snapshot','Snapshot does not belong to the proposed package set');
  const snapshot=decodeSnapshot(encoded),record=packageRecord(snapshot,proposal.packages[id].package_dependencies);
  if(snapshot.plugin_id!==id||registry.json(record)!==registry.json(proposal.packages[id]))registry.fail('plugin-snapshot','Snapshot and proposed owned package identity differ');
  changes[record.destination]=packageFiles(snapshot);
 }
 for(const [id,record]of Object.entries(proposal.packages))if(!own(proposal.snapshots||{},id)&&(!own(base.packages,id)||registry.json(record)!==registry.json(base.packages[id])))registry.fail('plugin-snapshot','A changed package requires inspected source bytes');
 for(const [id,record]of Object.entries(base.packages))if(!own(proposal.packages,id))changes[record.destination]=null;
 return changes;
}
function recordNoop(root,history,receipt,expected){
 const next=clone(history);Object.defineProperty(next.requests,receipt.request_id,{value:receipt,enumerable:true,writable:true,configurable:true});
 const destination=registry.safe(root,registry.NOOP_REQUESTS),temporary=registry.safe(root,'.skill-tree/installation/.plugin-noop-'+crypto.randomUUID()+'.tmp');let descriptor;
 try{
  if(core.treeHash(root,registry.NOOP_REQUESTS)!==expected)registry.fail('plugin-request-history','Plugin request history changed before recording the no-op');
  descriptor=fs.openSync(temporary,'wx',0o600);fs.writeFileSync(descriptor,registry.json(registry.seal(next)));fs.fsyncSync(descriptor);fs.closeSync(descriptor);descriptor=undefined;
  if(core.treeHash(root,registry.NOOP_REQUESTS)!==expected)registry.fail('plugin-request-history','Plugin request history changed during recording');
  fs.renameSync(temporary,destination);
 }finally{
  if(descriptor!==undefined)fs.closeSync(descriptor);
  try{fs.unlinkSync(temporary);}catch(error){if(error.code!=='ENOENT')throw error;}
 }
 return receipt;
}
function replayReceipt(base,history,proposal){
 const primary=own(base.requests,proposal.request_id)?base.requests[proposal.request_id]:null,noop=own(history.requests,proposal.request_id)?history.requests[proposal.request_id]:null;
 if(primary&&noop&&primary.proposal_digest!==noop.proposal_digest)registry.fail('plugin-replay','Conflicting request history requires reconciliation');
 const receipt=primary||noop;
 if(!receipt)return null;
 if(receipt.proposal_digest!==proposal.digest)registry.fail('plugin-replay','The request identity conflicts with an earlier proposal');
 return {...clone(receipt),replayed:true,current_generation:base.generation};
}
function inspectProposal(root,proposal,confirmation,profile){
 validateProposal(root,proposal,confirmation);
 const base=registry.verifyInstalled(root);
 const replay=replayReceipt(base,registry.readNoopRequests(root,base.generation),proposal);
 if(replay)return null;
 if(base.identity!==proposal.base_registry_identity||base.generation!==proposal.base_generation||profile.identity!==proposal.core_identity)
  registry.fail('plugin-stale','The proposal generation or core identity is stale');
 assertProviderScope(proposal,profile);
 registry.validateRegistry(registry.seal({...base,generation:base.generation+1,packages:proposal.packages,bindings:proposal.bindings}));
 snapshotChanges(proposal,base);
 return base;
}
function applyProposal(root,proposal,confirmation,{validateManagerImpact}={}){
 proposal=clone(proposal);confirmation=clone(confirmation||{});
 validateProposal(root,proposal,confirmation);
 const managed=['manager_action','manager_preview_digest','manager_impact_digest'].some(field=>own(proposal,field));
 if(managed&&typeof validateManagerImpact!=='function')
  registry.fail('plugin-consent','A manager-bound proposal requires the exact manager preview and impact guard');
 const lockOptions=managed?{recoverPending:false,onPending:()=>{
  coreProfile(root);
  const base=registry.verifyInstalled(root);
  const replay=replayReceipt(base,registry.readNoopRequests(root,base.generation),proposal);
  if(!replay)registry.fail('plugin-recovery','Owned installation recovery is required before a new manager mutation');
  return replay;
 }}:undefined;
 return core.locked(root,()=>{
  const profile=coreProfile(root),base=registry.verifyInstalled(root),noopBefore=core.treeHash(root,registry.NOOP_REQUESTS),history=registry.readNoopRequests(root,base.generation);
  const replay=replayReceipt(base,history,proposal);
  if(replay)return replay;
  if(base.identity!==proposal.base_registry_identity||base.generation!==proposal.base_generation||profile.identity!==proposal.core_identity)registry.fail('plugin-stale','The proposal generation or core identity is stale');
  assertProviderScope(proposal,profile);
  stoppedHandoff(root);
  if(managed)validateManagerImpact(base,proposal);
  const changes=snapshotChanges(proposal,base);
  const next=registry.seal({...base,generation:base.generation+1,packages:clone(proposal.packages),bindings:clone(proposal.bindings)});registry.validateRegistry(next);
  if(registry.json(next.packages)===registry.json(base.packages)&&registry.json(next.bindings)===registry.json(base.bindings))return recordNoop(root,history,{action:'verified-no-op',generation:base.generation,request_id:proposal.request_id,proposal_digest:proposal.digest},noopBefore);
  const receipt={action:proposal.operation==='uninstall'?'uninstalled':proposal.operation==='rollback'?'rolled-back':proposal.operation==='install'||proposal.operation==='update'?'installed':'configured',generation:next.generation,request_id:proposal.request_id,proposal_digest:proposal.digest};
  Object.defineProperty(next.requests,proposal.request_id,{value:receipt,enumerable:true,writable:true,configurable:true});const sealed=registry.seal(next);changes[registry.REGISTRY]=registry.json(sealed);
  const stopped=core.stoppedWorkflow(root);if(stopped!==null)changes[WORKFLOW]=stopped;
  const expected=Object.fromEntries(Object.keys(changes).map(rel=>[rel,core.treeHash(root,rel,true)]));
  core.transaction(root,changes,expected,()=>{
   stoppedHandoff(root);validateProposal(root,proposal,confirmation);
   const actualProfile=coreProfile(root);
   if(registry.verifyInstalled(root).identity!==base.identity||actualProfile.identity!==profile.identity)registry.fail('plugin-stale','Project state changed during plugin staging');
   assertProviderScope(proposal,actualProfile);
   if(managed)validateManagerImpact(base,proposal);
   for(const encoded of Object.values(proposal.snapshots||{}))decodeSnapshot(encoded);
  },'plugins');
  registry.verifyInstalled(root);return {...receipt,requires_profile_refresh:true};
 },lockOptions);
}
function backupContents(root,entry){
 if(core.treeHash(root,entry.backup,true)!==entry.old)registry.fail('plugin-rollback','The retained plugin backup is missing or modified');
 const full=registry.safe(root,entry.backup);
 if(fs.lstatSync(full).isFile())return fs.readFileSync(full);
 return Object.fromEntries(Object.keys(core.filesAt(root,entry.backup,true)).map(rel=>[rel,fs.readFileSync(registry.safe(root,entry.backup+'/'+rel))]));
}
async function prepareRollback(root,request){
 requestId(request?.request_id);const profile=coreProfile(root),base=registry.verifyInstalled(root),lastFile=registry.safe(root,core.transactionPaths('plugins').last);
 if(!fs.existsSync(lastFile))registry.fail('plugin-rollback','No retained plugin generation exists');
 const last=JSON.parse(fs.readFileSync(lastFile,'utf8'));
 if(last.schema!==1||last.channel!=='plugins'||!Array.isArray(last.entries))registry.fail('plugin-rollback','The retained plugin transaction is invalid');
 const registryEntry=last.entries.find(entry=>entry.dest===registry.REGISTRY);
 if(!registryEntry)registry.fail('plugin-rollback','The retained transaction has no plugin registry generation');
 for(const entry of last.entries)if(entry.dest!==WORKFLOW&&core.treeHash(root,entry.dest,true)!==entry.next)registry.fail('plugin-rollback','Current plugin resources changed after the retained transaction');
 const previous=registryEntry.old===null?registry.emptyRegistry():registry.validateRegistry(JSON.parse(backupContents(root,registryEntry).toString('utf8'))),snapshots={};
 for(const [id,record]of Object.entries(previous.packages)){
  if(own(base.packages,id)&&registry.json(record)===registry.json(base.packages[id]))continue;
  const saved=last.entries.find(entry=>entry.dest===record.destination),files=saved?backupContents(root,saved):Object.fromEntries(Object.keys(record.files).map(rel=>[rel,fs.readFileSync(registry.safe(root,record.destination+'/'+rel))]));
  if(!files||Buffer.isBuffer(files))registry.fail('plugin-rollback','The retained plugin package backup is invalid');
  const sourceFiles=Object.fromEntries(Object.keys(record.snapshot.digests).map(rel=>[rel,files['upstream/'+rel]]));
  for(const [rel,bytes]of Object.entries(sourceFiles))if(!Buffer.isBuffer(bytes))registry.fail('plugin-rollback','The retained source closure is incomplete');
  snapshots[id]=encodeSnapshot({...clone(record.snapshot),files:sourceFiles});
 }
 return makeProposal(root,{...request,operation:'rollback'},base,profile,clone(previous.packages),clone(previous.bindings),snapshots);
}
function recoverPlugins(root){stoppedHandoff(root);return core.locked(root,()=>{stoppedHandoff(root);core.recover(root,'plugins');return {action:'recovered',registry:registry.verifyInstalled(root)};});}
module.exports={prepareProposal,applyProposal,prepareRollback,recoverPlugins,providerScope,proposalDigest,inspectProposal,validateProposal};
