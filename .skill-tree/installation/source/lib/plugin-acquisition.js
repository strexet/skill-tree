'use strict';
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const http=require('node:http'),https=require('node:https'),cp=require('node:child_process');
function error(code,message){const result=Error(message);result.code=code;return result;}
function relative(value){
 if(typeof value!=='string'||!value||path.posix.isAbsolute(value)||/^[a-z]:/i.test(value)||value.includes('\\')||value.includes('\0')||value.split('/').includes('..'))throw error('source-path','An acquired resource requires a bounded relative path');
 const normalized=path.posix.normalize(value).replace(/\/+$/,'');if(!normalized||normalized==='.')throw error('source-path','An acquired resource cannot name the source root');return normalized;
}
function resourcePaths(values=[]){if(!Array.isArray(values))throw error('source-path','Source resources require a path list');return values.map(value=>relative(typeof value==='string'?value:value?.path));}
function links(rel,bytes){
 if(!/\.(md|markdown|txt)$/i.test(rel))return [];
 const result=[];
 for(const match of bytes.toString('utf8').matchAll(/\]\((?:<([^>]+)>|([^\n)]+))\)/g)){
  let target=(match[1]||match[2]).trim().split(/\s+["']/)[0];
  if(!target||target.startsWith('#')||target.startsWith('//')||/^[a-z][a-z0-9+.-]*:/i.test(target))continue;
  try{target=decodeURIComponent(target.split('#')[0].split('?')[0]);}catch{throw error('source-path','Malformed local resource link');}
  if(!target)continue;if(path.posix.isAbsolute(target)||target.includes('\\'))throw error('source-path','Absolute resource links are unsupported');
  result.push(relative(path.posix.join(path.posix.dirname(rel),target)));
 }
 return result;
}
function limits(options){
 const selected={timeoutMs:options.timeoutMs??30000,maxBytes:options.maxBytes??16*1024*1024,maxFiles:options.maxFiles??256};
 selected.maxRepositoryBytes=options.maxRepositoryBytes??selected.maxBytes*4;
 for(const value of Object.values(selected))if(!Number.isSafeInteger(value)||value<=0)throw error('source-acquisition','Acquisition limits require positive integers');
 return {...selected,deadline:Date.now()+selected.timeoutMs,bytes:0,files:0};
}
function remaining(budget){const result=budget.deadline-Date.now();if(result<=0)throw error('source-timeout','Source acquisition exceeded the deadline');return result;}
function account(budget,size){remaining(budget);if(budget.files+1>budget.maxFiles||budget.bytes+size>budget.maxBytes)throw error('source-size','Source acquisition exceeds the resource limit');budget.files++;budget.bytes+=size;}
async function closure(definition,read,budget){
 const entry=relative(definition.source.entry),queue=[entry,...resourcePaths(definition.resources),...resourcePaths(definition.dependencies)],visited=new Set(),files=Object.create(null);
 while(queue.length){
  const rel=relative(queue.shift());if(visited.has(rel))continue;visited.add(rel);remaining(budget);
  const value=await read(rel);
  if(Array.isArray(value)){queue.push(...value);continue;}
  account(budget,value.length);files[rel]=Buffer.from(value);queue.push(...links(rel,files[rel]));
 }
 if(!Object.hasOwn(files,entry))throw error('source-missing','The instruction entry is not a file');return files;
}
function requestBytes(url,budget,redirects=0){
 return new Promise((resolve,reject)=>{
  let parsed;try{parsed=new URL(url);}catch{reject(error('source-acquisition','Invalid raw acquisition URL'));return;}
  if(!['http:','https:'].includes(parsed.protocol)){reject(error('source-acquisition','Raw acquisition requires HTTP or HTTPS'));return;}
  if(redirects>5){reject(error('source-acquisition','Raw acquisition exceeded the redirect limit'));return;}
  let timeout;try{timeout=remaining(budget);}catch(failure){reject(failure);return;}
  let settled=false,timer,request;
  const finish=(failure,value)=>{if(settled)return;settled=true;clearTimeout(timer);failure?reject(failure):resolve(value);};
  try{
   request=(parsed.protocol==='https:'?https:http).get(parsed,{headers:{'Accept-Encoding':'identity'}},response=>{
    const status=response.statusCode||0;
    if([301,302,303,307,308].includes(status)&&response.headers.location){
     response.destroy();let next;try{next=new URL(response.headers.location,parsed);}catch{finish(error('source-acquisition','Invalid raw redirect'));return;}
     requestBytes(next,budget,redirects+1).then(value=>finish(null,value),finish);return;
    }
    if(status<200||status>=300){response.destroy();finish(error('source-acquisition','Remote source returned HTTP '+status));return;}
    if(response.headers['content-encoding']&&response.headers['content-encoding']!=='identity'){response.destroy();finish(error('source-acquisition','Encoded raw responses require an explicit adapter'));return;}
    const available=budget.maxBytes-budget.bytes,declared=Number(response.headers['content-length']);
    if(Number.isFinite(declared)&&declared>available){response.destroy();finish(error('source-size','Source acquisition exceeds the byte limit'));return;}
    const chunks=[];let size=0;
    response.on('data',chunk=>{size+=chunk.length;if(size>available){response.destroy();finish(error('source-size','Source acquisition exceeds the byte limit'));return;}chunks.push(chunk);});
    response.once('error',()=>finish(error('source-acquisition','Raw source transport failed')));
    response.once('aborted',()=>finish(error('source-acquisition','Raw source transport was interrupted')));
    response.once('end',()=>finish(null,{bytes:Buffer.concat(chunks),url:parsed}));
   });
   timer=setTimeout(()=>{finish(error('source-timeout','Source acquisition exceeded the deadline'));request.destroy();},timeout);
   request.once('error',()=>finish(error('source-acquisition','Raw source transport failed')));
  }catch{finish(error('source-acquisition','Raw source transport failed'));}
 });
}
async function raw(definition,locator,budget){
 let entryUrl;try{entryUrl=new URL(locator.url);}catch{throw error('source-acquisition','Invalid raw acquisition URL');}
 const entry=relative(definition.source.entry),base=path.posix.dirname(entry);
 const files=await closure(definition,async rel=>{
  const target=rel===entry?entryUrl:new URL(path.posix.relative(base,rel).split('/').map(encodeURIComponent).join('/'),entryUrl);
  const result=await requestBytes(target,budget);if(rel===entry)entryUrl=result.url;return result.bytes;
 },budget);
 return {files};
}
function directorySize(root){
 let entries;try{entries=fs.readdirSync(root,{withFileTypes:true});}catch(failure){if(failure.code==='ENOENT')return 0;throw failure;}
 let total=0;for(const entry of entries){
  const full=path.join(root,entry.name);if(entry.isDirectory())total+=directorySize(full);else if(entry.isFile()){try{total+=fs.statSync(full).size;}catch(failure){if(failure.code!=='ENOENT')throw failure;}}
 }return total;
}
function gitEnvironment(allowFile){
 const env={...process.env};
 for(const key of Object.keys(env))if(/^GIT_(?:DIR|WORK_TREE|COMMON_DIR|INDEX_FILE|OBJECT_DIRECTORY|ALTERNATE_OBJECT_DIRECTORIES|CONFIG(?:_.*)?|TEMPLATE_DIR)$/.test(key))delete env[key];
 return {...env,GIT_CONFIG_NOSYSTEM:'1',GIT_CONFIG_SYSTEM:os.devNull,GIT_CONFIG_GLOBAL:os.devNull,GIT_CONFIG_COUNT:'0',GIT_TERMINAL_PROMPT:'0',GIT_ASKPASS:os.devNull,GIT_ALLOW_PROTOCOL:'https:http:ssh:git'+(allowFile?':file':''),GIT_PROTOCOL_FROM_USER:'0'};
}
function runGit(root,args,budget,env){
 return new Promise((resolve,reject)=>{
  let duration;try{duration=remaining(budget);}catch(failure){reject(failure);return;}
  let limitHit=false,timedOut=false;
  const grouped=process.platform!=='win32';let child;
  const stop=()=>{try{if(grouped&&child.pid)process.kill(-child.pid,'SIGKILL');else child.kill('SIGKILL');}catch{child.kill('SIGKILL');}};
  try{child=cp.execFile('git',['-c','core.hooksPath='+os.devNull,'-c','core.fsmonitor=false','-c','protocol.ext.allow=never','-C',root,...args],{encoding:'buffer',detached:grouped,maxBuffer:Math.max(budget.maxBytes,1024*1024),env},(failure,stdout)=>{
   clearInterval(monitor);clearTimeout(timer);
   if(limitHit){reject(error('source-size','Repository acquisition exceeds the temporary storage limit'));return;}
   if(timedOut){reject(error('source-timeout','Repository acquisition exceeded the deadline'));return;}
   if(failure){stop();reject(error(failure.code==='ERR_CHILD_PROCESS_STDIO_MAXBUFFER'?'source-size':'source-acquisition','Repository acquisition failed'));return;}
   try{remaining(budget);if(directorySize(root)>budget.maxRepositoryBytes)throw error('source-size','Repository acquisition exceeds the temporary storage limit');resolve(stdout);}catch(result){reject(result);}
  });}catch{reject(error('source-acquisition','Repository acquisition failed'));return;}
  const timer=setTimeout(()=>{timedOut=true;stop();},duration);
  const monitor=setInterval(()=>{try{if(directorySize(root)>budget.maxRepositoryBytes){limitHit=true;stop();}}catch{stop();}},25);
 });
}
async function repository(definition,locator,budget,options){
 const transport=options.transportUrl||locator.url;
 if(typeof transport!=='string'||(!options.transportUrl&&!/^(?:https?|ssh|git):\/\//i.test(transport)))throw error('source-acquisition','Unsupported repository transport');
 const selected=definition.source.ref||locator.ref||'HEAD';
 if(typeof selected!=='string'||!selected||selected.startsWith('-')||selected.includes('\0'))throw error('source-revision','An explicit repository ref is invalid');
 let root;try{root=fs.mkdtempSync(path.join(options.tempDir||os.tmpdir(),'skill-tree-plugin-acquire-'));}catch{throw error('source-acquisition','Temporary acquisition storage is unavailable');}
 try{
  const env=gitEnvironment(Boolean(options.transportUrl)),git=args=>runGit(root,args,budget,env);
  await git(['init','--bare']);await git(['fetch','--no-tags','--depth=1','--filter=blob:none','--',transport,selected]);
  const revision=(await git(['rev-parse','--verify','FETCH_HEAD^{commit}'])).toString('ascii').trim();
  if(!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(revision))throw error('source-revision','Repository acquisition did not resolve an immutable commit');
  const records=Object.create(null),tree=await git(['ls-tree','-r','-z',revision]),listing=tree.toString('utf8');
  if(!Buffer.from(listing,'utf8').equals(tree))throw error('source-path','Repository resource names require valid UTF-8');
  for(const item of listing.split('\0').filter(Boolean)){
   const match=item.match(/^(\d+) (\w+) ([a-f0-9]+)\t([\s\S]+)$/);if(!match)throw error('source-acquisition','Unsupported repository tree');
   const rel=relative(match[4]);if(rel!==match[4]||Object.hasOwn(records,rel))throw error('source-path','Repository paths are not canonical');records[rel]={mode:match[1],type:match[2],oid:match[3]};
  }
  const files=await closure(definition,async rel=>{
   const record=records[rel];
   if(!record){const children=Object.keys(records).filter(value=>value.startsWith(rel+'/'));if(children.length)return children;throw error('source-missing','Missing required repository resource');}
   if(!['100644','100755'].includes(record.mode)||record.type!=='blob')throw error('source-path','Symlink or non-file repository resources are unsupported');
   const size=Number((await git(['cat-file','-s',record.oid])).toString('ascii').trim());
   if(!Number.isSafeInteger(size)||size<0||size>budget.maxBytes-budget.bytes)throw error('source-size','Source acquisition exceeds the byte limit');
   return git(['cat-file','blob',record.oid]);
  },budget);
  return {revision:revision.toLowerCase(),files};
 }finally{fs.rmSync(root,{recursive:true,force:true});}
}

/** Explicit network/object acquisition only; no checkout, helper execution or project mutation. */
async function acquireRemote({definition,locator},options={}){
 if(!definition?.source||!locator)throw error('source-acquisition','A normalized acquisition request is required');
 const budget=limits(options);
 if(definition.source.kind==='raw')return raw(definition,locator,budget);
 if(definition.source.kind==='repository')return repository(definition,locator,budget,options);
 throw error('source-acquisition','Remote acquisition requires a repository or raw source');
}
module.exports={acquireRemote};
