'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),sources=require('./plugin-sources.js');
const REGISTRY='.skill-tree/installation/plugins.json',PACKAGES='.skill-tree/installation/plugin-packages',NOOP_REQUESTS='.skill-tree/installation/plugin-noop-requests.json';
const own=(value,key)=>Object.hasOwn(value,key),object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function stable(value){if(Array.isArray(value))return value.map(stable);if(object(value))return Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])]));return value;}
const json=value=>JSON.stringify(stable(value),null,2)+'\n';
function fail(code,message){const error=Error(message);error.code=code;throw error;}
function relative(value){if(typeof value!=='string'||!value||path.isAbsolute(value)||/^[a-z]:/i.test(value)||value.includes('\\')||value.includes('\0')||value.split('/').some(part=>!part||part==='.'||part==='..'))fail('plugin-path','An owned plugin path must be repository-relative');return value;}
function safe(root,rel){relative(rel);const base=fs.realpathSync(root);let full=base;for(const part of rel.split('/')){full=path.join(full,part);try{if(fs.lstatSync(full).isSymbolicLink())fail('plugin-ownership','Symlink in owned plugin resources');}catch(error){if(error.code!=='ENOENT')throw error;}}return full;}
const validId=id=>typeof id==='string'&&/^[a-z][a-z0-9-]*$/.test(id);
const digest=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
function seal(value){const {identity,...record}=value;return {...record,identity:hash(json(record))};}
function emptyRegistry(){return seal({format:'skill-tree-plugin-registry',schema:1,generation:0,packages:{},bindings:[],requests:{}});}
function validateBindings(bindings,packages){
 if(!Array.isArray(bindings))fail('plugin-registry','Plugin bindings require an ordered list');
 const ids=new Set();
 for(const binding of bindings){
  if(!object(binding)||!validId(binding.id)||ids.has(binding.id)||!validId(binding.plugin_id)||!own(packages,binding.plugin_id)||typeof binding.operation!=='string'||!binding.operation||typeof binding.anchor!=='string'||!binding.anchor||typeof binding.enabled!=='boolean')fail('plugin-binding','A binding requires a unique identity, installed package and explicit operation/anchor/enabled state');
  ids.add(binding.id);
 }
 return bindings;
}
function validateRegistry(value){
 if(!object(value)||value.format!=='skill-tree-plugin-registry'||value.schema!==1||!Number.isSafeInteger(value.generation)||value.generation<0||!object(value.packages)||!object(value.requests)||value.identity!==seal(value).identity)fail('plugin-registry','Unsupported, modified or unowned plugin registry');
 for(const [id,record]of Object.entries(value.packages)){
  if(!validId(id)||!object(record)||record.id!==id||record.destination!==PACKAGES+'/'+id||!object(record.files)||!Object.keys(record.files).length||!digest(record.content_digest)||typeof record.revision!=='string'||!object(record.source)||!Array.isArray(record.package_dependencies))fail('plugin-registry','Invalid owned plugin package record');
  relative(record.entry);if(!own(record.files,record.entry))fail('plugin-registry','The installed plugin entry is missing from the owned inventory');
  for(const [rel,sum]of Object.entries(record.files)){relative(rel);if(!digest(sum))fail('plugin-registry','Invalid plugin resource digest');}
  if(record.package_dependencies.some(dep=>!validId(dep)||dep===id||!own(value.packages,dep))||new Set(record.package_dependencies).size!==record.package_dependencies.length)fail('plugin-dependency','An installed plugin has an unresolved package dependency');
 }
 validateBindings(value.bindings,value.packages);
 for(const [id,receipt]of Object.entries(value.requests))if(!id||!object(receipt)||!digest(receipt.proposal_digest)||!Number.isSafeInteger(receipt.generation)||receipt.generation<0||receipt.generation>value.generation)fail('plugin-registry','Invalid plugin request receipt');
 return value;
}
function readRegistry(root){
 const file=safe(root,REGISTRY);if(!fs.existsSync(file))return emptyRegistry();
 let value;try{value=JSON.parse(fs.readFileSync(file,'utf8'));}catch{fail('plugin-registry','Unreadable or unowned plugin registry');}
 return validateRegistry(value);
}
function readNoopRequests(root,maxGeneration=Number.MAX_SAFE_INTEGER){
 const file=safe(root,NOOP_REQUESTS);if(!fs.existsSync(file))return seal({format:'skill-tree-plugin-noop-requests',schema:1,requests:{}});
 let value;try{value=JSON.parse(fs.readFileSync(file,'utf8'));}catch{fail('plugin-request-history','Unreadable or unowned plugin request history');}
 if(!object(value)||value.format!=='skill-tree-plugin-noop-requests'||value.schema!==1||!object(value.requests)||value.identity!==seal(value).identity)fail('plugin-request-history','Unsupported or modified plugin request history');
 for(const [id,receipt]of Object.entries(value.requests))if(!id||!object(receipt)||receipt.action!=='verified-no-op'||receipt.request_id!==id||!digest(receipt.proposal_digest)||!Number.isSafeInteger(receipt.generation)||receipt.generation<0||receipt.generation>maxGeneration)fail('plugin-request-history','Invalid plugin no-op request receipt');
 return value;
}
function filesAt(root,rel){
 const full=safe(root,rel);if(!fs.existsSync(full))return null;
 if(!fs.lstatSync(full).isDirectory())fail('plugin-ownership','An owned plugin package must be a directory');
 const files=Object.create(null);
 function visit(directory,prefix){for(const entry of fs.readdirSync(directory,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){const key=prefix+entry.name,file=path.join(directory,entry.name);relative(key);if(entry.isSymbolicLink())fail('plugin-ownership','Symlink in owned plugin package');if(entry.isDirectory())visit(file,key+'/');else if(entry.isFile())files[key]=hash(fs.readFileSync(file));else fail('plugin-ownership','Unsupported entry in owned plugin package');}}
 visit(full,'');return files;
}
function verifyInstalled(root,value=readRegistry(root)){
 validateRegistry(value);
 const base=safe(root,PACKAGES),actual=fs.existsSync(base)?fs.readdirSync(base).sort():[];
 if(json(actual)!==json(Object.keys(value.packages).sort()))fail('plugin-ownership','Unowned, missing or conflicting plugin package destination');
 for(const record of Object.values(value.packages)){
  if(json(filesAt(root,record.destination))!==json(record.files))fail('plugin-ownership','Locally modified or missing owned plugin resources: '+record.id);
  if(!object(record.snapshot)||!object(record.snapshot.digests)||record.snapshot.plugin_id!==record.id||record.entry!=='upstream/'+record.snapshot.entry||record.content_digest!==record.snapshot.content_digest||record.revision!==record.snapshot.revision||json(record.source)!==json(record.snapshot.source)||json(record.metadata)!==json(record.snapshot.metadata)||json(record.adaptation)!==json(record.snapshot.adaptation)||json(record.execution)!==json(record.snapshot.execution))fail('plugin-ownership','The owned package snapshot identity is inconsistent');
  const expectedFiles={...Object.fromEntries(Object.entries(record.snapshot.digests).map(([rel,sum])=>['upstream/'+relative(rel),sum])),'overlay/adapter.json':hash(json(record.adaptation))};
  if(json(expectedFiles)!==json(record.files))fail('plugin-ownership','The owned inventory differs from the source snapshot and adaptation overlay');
  const files=Object.fromEntries(Object.keys(record.snapshot.digests).map(rel=>[rel,fs.readFileSync(safe(root,record.destination+'/upstream/'+relative(rel)))]));sources.verifySnapshot({...record.snapshot,files});
  if(fs.readFileSync(safe(root,record.destination+'/overlay/adapter.json'),'utf8')!==json(record.adaptation))fail('plugin-ownership','The owned adaptation overlay changed');
 }
 return value;
}
module.exports={REGISTRY,PACKAGES,NOOP_REQUESTS,hash,json,seal,safe,relative,validId,fail,emptyRegistry,validateBindings,validateRegistry,readRegistry,readNoopRequests,filesAt,verifyInstalled};
