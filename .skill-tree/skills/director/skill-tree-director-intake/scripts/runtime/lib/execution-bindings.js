'use strict';
// Static data only. No project configuration or runner is evaluated.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function relative(value){if(typeof value!=='string'||!value||path.isAbsolute(value)||value.includes('\\')||value.split('/').some(p=>!p||p==='.'||p==='..'))throw Error('Binding paths require canonical repository-relative paths');return value;}
function checked(root,rel){relative(rel);const target=path.join(root,rel);let current=root;for(const part of rel.split('/')){current=path.join(current,part);if(fs.existsSync(current)&&fs.lstatSync(current).isSymbolicLink())throw Error('Binding symlink is unsupported: '+rel);}return target;}
function rootPath(value){if(typeof value!=='string'||!path.isAbsolute(value)||!fs.statSync(value).isDirectory()||fs.realpathSync(value)!==path.resolve(value))throw Error('Binding root requires an exact real directory');return fs.realpathSync(value);}
function disjoint(a,b){if(a===b||a.startsWith(b+path.sep)||b.startsWith(a+path.sep))throw Error('Binding queue and execution roots overlap');}
function jsonAt(root,rel){return JSON.parse(fs.readFileSync(checked(root,rel),'utf8').replace(/^\uFEFF/,''));}
function snapshot(root,paths,excluded=[]){
 if(!Array.isArray(excluded))throw Error('Binding exclusions require relative paths');for(const rel of excluded)relative(rel);
 const files={};
 function visit(rel){if(excluded.some(prefix=>rel===prefix||rel.startsWith(prefix+'/')))return;const full=checked(root,rel);if(!fs.existsSync(full))throw Error('Missing binding source: '+rel);const stat=fs.statSync(full);if(stat.isDirectory()){for(const name of fs.readdirSync(full).sort()){if(['.git','__pycache__','.DS_Store'].includes(name))continue;visit(rel+'/'+name);}}else if(stat.isFile())files[rel]=hash(fs.readFileSync(full));else throw Error('Unsupported binding source: '+rel);}
 if(!Array.isArray(paths)||!paths.length)throw Error('Binding requires source paths');for(const rel of paths)visit(rel);
 const entries=Object.entries(files).sort(([a],[b])=>Buffer.compare(Buffer.from(a),Buffer.from(b)));
 return {files:Object.fromEntries(entries),digest:hash(entries.map(([name,digest])=>name+'\0'+digest+'\n').join(''))};
}
function supportSnapshot(root,paths){
 if(!Array.isArray(paths))throw Error('Binding support paths require a list');
 return paths.length?snapshot(root,paths):{files:{},digest:hash('')};
}
function resolveBindings(queue,document){
 const result={};
 for(const [id,spec] of Object.entries(document.execution_bindings||{})){
  if(!/^[a-z][a-z0-9-]*$/.test(id)||!spec||typeof spec!=='object')throw Error('Invalid execution binding');
  if(!spec.locator?.startsWith('.skill-tree/local/'))throw Error('Binding locator requires local machine configuration');
  const locator=jsonAt(queue,spec.locator);if(locator.schema!==1||rootPath(locator.queue_root)!==queue)throw Error('Foreign binding queue identity');
  const workspace=rootPath(locator.workspace_root),execution=rootPath(checked(workspace,spec.execution_subdir));disjoint(queue,workspace);disjoint(queue,execution);
  const q=snapshot(queue,spec.source_paths,spec.exclude_paths),e=snapshot(execution,spec.source_paths,spec.exclude_paths),w=supportSnapshot(workspace,spec.workspace_paths===undefined?[]:spec.workspace_paths),support=supportSnapshot(queue,spec.queue_paths===undefined?[]:spec.queue_paths),review=jsonAt(queue,spec.review_path);
  if(review.schema!==1||review.queue_digest!==q.digest||review.execution_digest!==e.digest||review.workspace_digest!==w.digest)throw Error('Binding source review is stale');
  if(!Object.keys(w.files).length&&!Object.keys(support.files).length)throw Error('Binding requires reviewed runner/profile paths');
  if(spec.queue_paths?.length&&review.queue_support_digest!==support.digest)throw Error('Binding queue support review is stale');
  const differences={};for(const name of new Set([...Object.keys(q.files),...Object.keys(e.files)])){if(q.files[name]!==e.files[name])differences[name]={queue:q.files[name]||null,execution:e.files[name]||null};}
  if(!Array.isArray(review.differences)||review.differences.length!==Object.keys(differences).length)throw Error('Binding review must classify every source difference');
  const seen=new Set(),blockers=[];
  for(const entry of review.differences){const actual=differences[entry.path];if(seen.has(entry.path)||!actual||actual.queue!==entry.queue||actual.execution!==entry.execution||!['fixture','encoding','unqualified'].includes(entry.classification)||typeof entry.reason!=='string'||!entry.reason.trim())throw Error('Unreviewed binding source difference');seen.add(entry.path);if(entry.classification==='unqualified')blockers.push(entry.path);}
  const pins=spec.pins;if(!pins||!['editor_version','cli_version','pipeline_version','utf_version'].every(k=>typeof pins[k]==='string'&&pins[k]))throw Error('Binding requires explicit toolchain pins');
  for(const root of [queue,execution]){const editor=fs.readFileSync(checked(root,'ProjectSettings/ProjectVersion.txt'),'utf8').match(/m_EditorVersion:\s*(\S+)/)?.[1];const locked=jsonAt(root,'Packages/packages-lock.json').dependencies||{};if(editor!==pins.editor_version||locked['com.unity.test-framework']?.version!==pins.utf_version)throw Error('Binding Editor or UTF pin mismatch');}
  const locked=jsonAt(execution,'Packages/packages-lock.json').dependencies||{};
  const pipeline=locked['com.unity.pipeline'];
  let pipelineVersion=pipeline?.version;
  if(pipeline?.source==='embedded'){
   if(pipeline.version!=='file:com.unity.pipeline')throw Error('Binding embedded Pipeline location mismatch');
   const embedded=jsonAt(execution,'Packages/com.unity.pipeline/package.json');
   if(embedded.name!=='com.unity.pipeline')throw Error('Binding embedded Pipeline identity mismatch');
   pipelineVersion=embedded.version;
  }
  if(pipelineVersion!==pins.pipeline_version)throw Error('Binding Pipeline pin mismatch');
  result[id]={...spec,workspace_paths:spec.workspace_paths===undefined?[]:spec.workspace_paths,...(spec.queue_paths?.length?{queue_support_digest:support.digest}:{}),queue_root:queue,workspace_root:workspace,execution_root:execution,locator_digest:hash(fs.readFileSync(checked(queue,spec.locator))),review_digest:hash(fs.readFileSync(checked(queue,spec.review_path))),queue_digest:q.digest,execution_digest:e.digest,workspace_digest:w.digest,blockers:blockers.sort(),qualification:'reviewed static identity only; product execution unqualified'};
 }
 return result;
}
module.exports={relative,checked,rootPath,disjoint,snapshot,resolveBindings};
