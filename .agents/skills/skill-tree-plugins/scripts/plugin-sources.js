'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const hash=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const json=value=>JSON.stringify(value);
const clone=value=>value===undefined?undefined:JSON.parse(json(value));
function fail(code,message){const error=Error(message);error.code=code;throw error;}
function relative(value){
 if(typeof value!=='string'||!value||value==='.'||path.isAbsolute(value)||/^[a-z]:/i.test(value)||value.includes('\\')||value.split('/').includes('..')||value.includes('\0'))fail('source-path','A source resource requires a bounded relative path');
 const normalized=path.posix.normalize(value).replace(/\/+$/,'');
 if(!normalized||normalized==='.')fail('source-path','A source resource cannot name the source root');
 return normalized;
}
function resourcePaths(values){
 if(values===undefined)return [];
 if(!Array.isArray(values))fail('source-definition','Source resources require a path list');
 return [...new Set(values.map(item=>relative(typeof item==='string'?item:item?.path)))];
}
function cleanUrl(value){
 const rawPath=String(value).match(/^[a-z][a-z0-9+.-]*:\/\/[^/?#]*(\/[^?#]*)?/i)?.[1]||'';
 for(const part of rawPath.split('/'))if(urlComponent(part)==='..')fail('source-path','Source URL paths cannot contain parent traversal');
 let u;try{u=new URL(value);}catch{fail('source-definition','An absolute source URL is required');}
 if(!['https:','http:','ssh:','git:'].includes(u.protocol))fail('source-definition','Unsupported acquisition URL protocol');
 u.username='';u.password='';u.search='';u.hash='';return u.toString().replace(/\/$/,'');
}
function sourceIdentity(source){const {ref,...identity}=source;return hash(json(identity));}
function urlComponent(value){try{return decodeURIComponent(value);}catch{fail('source-path','Malformed source URL encoding');}}

/** Normalize without network acquisition. Only locator contains machine-local/credential data.
 * Hosted URLs use the segment following blob/tree as ref; slash-bearing branches can use explicit ref+entry. */
function normalizeSource(input,{known={},baseDir=process.cwd(),checkCollision=true}={}){
 if(typeof input==='string'&&Object.hasOwn(known,input)){
  const record=known[input],item=record.definition?{...record.definition,locator:record.locator}:{...record};
  return normalizeSource({...item,id:item.id||input},{baseDir,checkCollision:false});
 }
 let item=typeof input==='string'?(/^(?:https?|ssh|git):\/\//i.test(input)?{url:input}:{path:input}):clone(input);
 if(!item||typeof item!=='object'||Array.isArray(item))fail('source-definition','A source URL, local path or known definition is required');
 const spec=item.source||item;
 let kind=spec.kind,entry=spec.entry||item.entry,ref=spec.ref||item.ref,source,locator;
 const originalUrl=spec.url||item.url||item.locator?.url;
 if(originalUrl){
  let url=cleanUrl(originalUrl),acquisitionUrl=item.locator?.url||originalUrl;const parsed=new URL(url),parts=parsed.pathname.split('/').filter(Boolean);
  if(kind!=='raw'&&parsed.hostname==='github.com'&&parts.length>=4&&['blob','tree'].includes(parts[2])){
   kind='repository';ref=ref||urlComponent(parts[3]);
   const selected=parts.slice(4).map(urlComponent).join('/');entry=entry||(parts[2]==='tree'?path.posix.join(selected,'SKILL.md'):selected);
   url=parsed.origin+'/'+parts.slice(0,2).join('/');
   const transport=new URL(originalUrl);transport.pathname='/'+parts.slice(0,2).join('/');transport.hash='';acquisitionUrl=transport.toString().replace(/\/$/,'');
  }else if(kind!=='raw'&&parts.includes('-')&&['blob','tree'].includes(parts[parts.indexOf('-')+1])&&parts[parts.indexOf('-')+2]){
   const marker=parts.indexOf('-');kind='repository';ref=ref||urlComponent(parts[marker+2]);
   const selected=parts.slice(marker+3).map(urlComponent).join('/');entry=entry||(parts[marker+1]==='tree'?path.posix.join(selected,'SKILL.md'):selected);
   url=parsed.origin+'/'+parts.slice(0,marker).join('/');
   const transport=new URL(originalUrl);transport.pathname='/'+parts.slice(0,marker).join('/');transport.hash='';acquisitionUrl=transport.toString().replace(/\/$/,'');
  }
  if(!kind)kind=['ssh:','git:'].includes(parsed.protocol)||/\.git$/.test(parsed.pathname)||(parsed.hostname==='github.com'&&parts.length===2)?'repository':'raw';
  if(!['repository','raw'].includes(kind))fail('source-definition','A remote source requires repository or raw acquisition');
  entry=relative(entry||(kind==='raw'?path.posix.basename(parsed.pathname):'SKILL.md')||'SKILL.md');
  source={kind,url,entry};if(ref)source.ref=ref;
  locator={kind,url:acquisitionUrl};if(ref)locator.ref=ref;
 }else{
  kind=kind||'local';if(kind!=='local')fail('source-definition','A remote source requires a URL');
  const supplied=item.locator?.path||spec.path||item.path;
  if(typeof supplied!=='string'||!supplied)fail('source-definition','A local acquisition path is required');
  const requested=path.resolve(baseDir,supplied);
  let stat;try{stat=fs.lstatSync(requested);}catch(error){if(error.code==='ENOENT')fail('source-missing','Local source does not exist');throw error;}
  if(stat.isSymbolicLink())fail('source-path','A local source cannot be a symlink');
  if(!stat.isFile()&&!stat.isDirectory())fail('source-path','A local source must be a file or directory');
  const actual=fs.realpathSync(requested),scope=stat.isDirectory()?actual:path.dirname(actual);
  entry=relative(entry||(stat.isFile()?path.basename(actual):'SKILL.md'));
  source={kind,entry,label:spec.label||path.basename(actual),locator_id:spec.locator_id||hash(scope)};
  locator={kind,path:scope};
 }
 const identity=sourceIdentity(source),id=item.id||'plugin-'+identity.slice(0,16);
 if(typeof id!=='string'||!(/^[a-z][a-z0-9-]*$/.test(id)))fail('source-identity','A stable lowercase plugin ID is required');
 if(checkCollision&&Object.hasOwn(known,id)){
  const existing=normalizeSource(id,{known,baseDir,checkCollision:false});
  if(sourceIdentity(existing.definition.source)!==identity)fail('source-identity','The plugin ID already names a different source');
 }
 const capabilities=item.capabilities||[];
 if(!Array.isArray(capabilities)||capabilities.some(v=>typeof v!=='string'||!v))fail('source-definition','Native capabilities require explicit names');
 const definition={schema:1,id,source,resources:resourcePaths(item.resources),dependencies:resourcePaths(item.dependencies),capabilities:[...new Set(capabilities)],metadata:clone(item.metadata||{})};
 if(item.adapter!==undefined)definition.adapter=clone(item.adapter);
 return {definition,locator};
}

function localPath(root,rel){
 relative(rel);let rootStat;
 try{rootStat=fs.lstatSync(root);}catch{fail('source-path','The admitted local source root is unavailable');}
 if(!rootStat.isDirectory()||rootStat.isSymbolicLink()||fs.realpathSync(root)!==root)fail('source-path','The admitted local source root changed');
 let current=root;
 for(const part of rel.split('/')){
  current=path.join(current,part);
  if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())fail('source-path','Symlink source resources are unsupported: '+rel);
 }
 const full=path.resolve(root,rel);
 if(full!==root&&!full.startsWith(root+path.sep))fail('source-path','Source resource escapes the admitted root');
 return full;
}
function localReader(root){
 return rel=>{
  const full=localPath(root,rel);
  let stat;try{stat=fs.lstatSync(full);}catch(error){if(error.code==='ENOENT')fail('source-missing','Missing required source resource: '+rel);throw error;}
  if(stat.isDirectory())return fs.readdirSync(full).sort().map(name=>relative(path.posix.join(rel,name)));
  if(!stat.isFile())fail('source-path','Unsupported source resource: '+rel);
  return fs.readFileSync(full);
 };
}
function acquiredReader(files){
 if(!files||typeof files!=='object'||Array.isArray(files))fail('source-acquisition','Acquisition must return actual source files');
 const values=Object.create(null);
 for(const [rel,bytes]of Object.entries(files)){
  const canonical=relative(rel);if(Object.hasOwn(values,canonical))fail('source-path','Acquired resource paths collide after normalization');
  if(!(typeof bytes==='string'||Buffer.isBuffer(bytes)||bytes instanceof Uint8Array))fail('source-acquisition','Acquired resources must contain bytes');
  values[canonical]=Buffer.from(bytes);
 }
 return rel=>{
  relative(rel);if(Object.hasOwn(values,rel))return values[rel];
  const descendants=Object.keys(values).filter(p=>p.startsWith(rel+'/'));
  if(descendants.length)return descendants;
  fail('source-missing','Missing required acquired resource: '+rel);
 };
}
function linkedResources(rel,bytes){
 if(!/\.(md|markdown|txt)$/i.test(rel))return [];
 const text=bytes.toString('utf8'),found=[];
 for(const match of text.matchAll(/\]\((?:<([^>]+)>|([^\n)]+))\)/g)){
  let target=(match[1]||match[2]).trim().split(/\s+["']/)[0];
  if(!target||target.startsWith('#')||/^[a-z][a-z0-9+.-]*:/i.test(target)||target.startsWith('//'))continue;
  try{target=decodeURIComponent(target.split('#')[0].split('?')[0]);}catch{fail('source-path','Malformed local resource URL');}
  if(!target)continue;
  if(path.posix.isAbsolute(target)||target.includes('\\'))fail('source-path','An absolute linked source resource is unsupported');
  const resolved=path.posix.normalize(path.posix.join(path.posix.dirname(rel),target));
  found.push(relative(resolved));
 }
 return found;
}
function fingerprints(files){return Object.fromEntries(Object.keys(files).sort().map(rel=>[rel,hash(files[rel])]));}
function contentDigest(entry,digests){return hash(json({entry,digests}));}

/** Acquisition is explicit: local reads are built in; remote callers supply acquire({definition,locator}). */
async function resolveSource(normalized,{acquire,availableCapabilities=[],expectedDigests={}}={}){
 if(!normalized?.definition||!normalized.locator)fail('source-definition','Normalize the selected source before acquisition');
 const {definition,locator}=normalized,entry=relative(definition.source.entry);
 let read,revision;
 if(definition.source.kind==='local')read=localReader(locator.path);
 else{
  if(typeof acquire!=='function')fail('source-acquisition-required','Remote acquisition requires an explicit acquisition adapter');
  const acquired=await acquire({definition:clone(definition),locator:clone(locator)});
  read=acquiredReader(acquired?.files);revision=acquired?.revision;
  if(definition.source.kind==='repository'){
   if(typeof revision!=='string'||!(/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(revision)))fail('source-revision','Repository acquisition requires an actual immutable commit');
   revision=revision.toLowerCase();
   if(/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(definition.source.ref||'')&&definition.source.ref.toLowerCase()!==revision)fail('source-drift','The resolved commit differs from the selected immutable revision');
  }
 }
 const files=Object.create(null),visited=new Set(),queue=[entry,...resourcePaths(definition.resources),...resourcePaths(definition.dependencies)];
 while(queue.length){
  const rel=relative(queue.shift());if(visited.has(rel))continue;visited.add(rel);
  const value=read(rel);
  if(Array.isArray(value)){queue.push(...value);continue;}
  files[rel]=Buffer.from(value);queue.push(...linkedResources(rel,files[rel]));
 }
 if(!Object.hasOwn(files,entry))fail('source-missing','The selected instruction entry must be a file');
 const digests=fingerprints(files);
 for(const [rel,expected]of Object.entries(expectedDigests))if(digests[relative(rel)]!==expected)fail('source-drift','Source content changed after inspection: '+rel);
 const content_digest=contentDigest(entry,digests),missing=definition.capabilities.filter(name=>!availableCapabilities.includes(name));
 const original=files[entry].toString('utf8').replace(/^\uFEFF/,''),frontmatter=original.match(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/)?.[0]||null;
 return {schema:1,plugin_id:definition.id,source:clone(definition.source),entry,revision:definition.source.kind==='repository'?revision:'sha256:'+content_digest,files,digests,content_digest,metadata:{...clone(definition.metadata),frontmatter},adaptation:clone(definition.adapter||{}),execution:{state:missing.length?'unavailable':'unqualified',required:[...definition.capabilities],missing}};
}

/** Validate owned staged bytes without reacquisition, execution or filesystem mutation. */
function verifySnapshot(snapshot){
 if(!snapshot||snapshot.schema!==1||!snapshot.files||!snapshot.digests)fail('source-drift','A complete source snapshot is required');
 const entry=relative(snapshot.entry);
 if(entry!==snapshot.entry||!['local','raw','repository'].includes(snapshot.source?.kind)||snapshot.source.entry!==entry||typeof snapshot.plugin_id!=='string'||!/^[a-z][a-z0-9-]*$/.test(snapshot.plugin_id))fail('source-drift','Snapshot descriptor identity is inconsistent');
 for(const [rel,bytes]of Object.entries(snapshot.files)){if(relative(rel)!==rel)fail('source-drift','Snapshot resource paths must be canonical');if(!Buffer.isBuffer(bytes)&&!(bytes instanceof Uint8Array))fail('source-drift','Snapshot resources must retain original bytes');}
 if(!Object.hasOwn(snapshot.files,entry))fail('source-drift','Snapshot entry is missing');
 const digests=fingerprints(snapshot.files);
 if(json(digests)!==json(Object.fromEntries(Object.keys(snapshot.digests).sort().map(key=>[key,snapshot.digests[key]])))||snapshot.content_digest!==contentDigest(entry,digests))fail('source-drift','Snapshot content no longer matches the inspected identity');
 if(snapshot.source?.kind!=='repository'&&snapshot.revision!=='sha256:'+snapshot.content_digest)fail('source-drift','Snapshot revision no longer matches content');
 if(snapshot.source.kind==='repository'){
  if(typeof snapshot.revision!=='string'||!/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(snapshot.revision))fail('source-drift','Snapshot repository revision must remain immutable');
  if(/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/i.test(snapshot.source.ref||'')&&snapshot.source.ref.toLowerCase()!==snapshot.revision.toLowerCase())fail('source-drift','Snapshot repository revision differs from the selected commit');
 }
 return true;
}
module.exports={normalizeSource,resolveSource,verifySnapshot};
