'use strict';
const fs=require('node:fs'),path=require('node:path');
const c=require('./composer.js');
const BEGIN='<!-- BEGIN skill-tree-skills -->',END='<!-- END skill-tree-skills -->';
const INSTALL='.skill-tree/installation',PROFILE=INSTALL+'/profile.json';
function filesAt(root,rel,includeCaches=false){
 const full=c.safe(root,rel);if(!fs.existsSync(full))return null;
 if(fs.lstatSync(full).isFile())return {'':c.hash(fs.readFileSync(full))};
 const out={};function walk(dir,prefix){for(const e of fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){if(e.name==='__pycache__'&&!includeCaches)continue;const child=path.join(dir,e.name),key=prefix+e.name;if(e.isSymbolicLink())throw Error('Symlink in owned package: '+rel+'/'+key);if(e.isDirectory())walk(child,key+'/');else if(e.isFile())Object.defineProperty(out,key,{value:c.hash(fs.readFileSync(child)),enumerable:true,writable:true,configurable:true});else throw Error('Unsupported owned entry: '+key);}}walk(full,'');return out;
}
const owners=record=>record.providers||[record.provider];
function compositionIdentity(profile){
 const outputs=Object.fromEntries(Object.values(profile.destinations).map(record=>[record.name,record.files]));
 return c.hash(c.json({flavor:profile.flavor,environment_id:profile.environment_id,source_digests:profile.source_digests,output_digests:outputs}));
}
const treeHash=(root,rel,includeCaches=false)=>{const files=filesAt(root,rel,includeCaches);return files===null?null:c.hash(c.json(files));};
function receipt(root,required=false,allowForeign=false){
 const p=c.readJson(root,PROFILE,null);
 if(!p){if(required)throw Error('Missing ownership receipt; install with an explicit --flavor');return null;}
 if(p.format!=='skill-tree-profile'||p.schema!==1||typeof p.project_root!=='string'||!allowForeign&&p.project_root!==fs.realpathSync(root)||!p.destinations||!p.bundle_digests)throw Error('Unsupported or foreign ownership receipt; use the manual update checklist');
 return p;
}
function verifyOwned(root,p,includeBundle=true){
 if(p.identity!==compositionIdentity(p))throw Error('Composition receipt identity mismatch');
 for(const [rel,record] of Object.entries(p.destinations)){
  if(!/^skill-tree-[a-z0-9-]+$/.test(record.name)||path.basename(rel)!==record.name)throw Error('Invalid owned destination');
  if(c.json(filesAt(root,rel))!==c.json(record.files))throw Error('Unowned or locally modified package conflicts: '+rel);
 }
 if(includeBundle){
  for(const [rel,hash] of Object.entries(p.bundle_digests))if(c.hash(c.read(root,rel)||'')!==hash)throw Error('Modified maintenance bundle: '+rel);
  const actual=filesAt(root,INSTALL+'/source');
  const expected=Object.fromEntries(Object.entries(p.bundle_digests).filter(([rel])=>rel.startsWith(INSTALL+'/source/')).map(([rel,hash])=>[rel.slice((INSTALL+'/source/').length),hash]));
  if(c.json(actual)!==c.json(expected))throw Error('Unowned or missing maintenance source inventory');
 }
 for(const [rel,record] of Object.entries(p.bridges||{})){const current=c.read(root,rel)||'',block=bridgeBlock(current);if(!block||c.hash(block)!==record.hash)throw Error('Modified or missing owned bridge: '+rel);}
}
function bridgeBlock(text){
 const a=text.indexOf(BEGIN),b=text.indexOf(END);if(a<0&&b<0)return null;
 if(a<0||b<a||text.indexOf(BEGIN,a+BEGIN.length)>=0||text.indexOf(END,b+END.length)>=0)throw Error('Ambiguous bridge markers');
 return text.slice(a,b+END.length);
}
function queueRoot(root){
 const result=require('node:child_process').spawnSync('git',['-C',root,'rev-parse','--git-common-dir'],{encoding:'utf8',timeout:5000});
 if(result.status!==0)return root;
 const common=path.resolve(root,result.stdout.trim()),locator=path.join(common,'skill-tree-runtime.json');
 if(!fs.existsSync(locator))return root;
 const data=JSON.parse(fs.readFileSync(locator,'utf8'));
 if(data.schema!==1||!data.canonical_root||!fs.existsSync(data.canonical_root))throw Error('Canonical queue locator requires explicit recovery');
 return data.canonical_root;
}
const WORKFLOW='.skill-tree/documents/future.json';
function workflowState(root){
 const state=c.readJson(queueRoot(root),WORKFLOW,null);if(state===null)return null;
 if(state.format!=='skill-tree-future'||![2,3].includes(state.schema)||!Array.isArray(state.tasks)||!state.task_progress||typeof state.task_progress!=='object'||Array.isArray(state.task_progress)||!(state.active_run===null||state.active_run&&typeof state.active_run==='object'))throw Error('Unsupported workflow schema; use the manual update checklist');
 if(state.schema===2&&state.run_registry||state.schema===3&&state.active_run!==null)throw Error('Ambiguous workflow run authority; explicit recovery required');
 if(state.schema===3&&(!state.run_registry||state.run_registry.schema!==1||!state.run_registry.runs||typeof state.run_registry.runs!=='object'||Array.isArray(state.run_registry.runs)||Object.entries(state.run_registry.runs).some(([id,run])=>!run||typeof run!=='object'||Array.isArray(run)||run.id!==id||typeof run.phase!=='string'||!run.phase)))throw Error('Unsupported multi-run registry; explicit recovery required');
 return state;
}
function unfinishedRun(run){
 if(!run)return false;
 const delivery=run.delivery||{},authorization=delivery.authorization||{};
 if(authorization.pr===false&&authorization.merge===true){
  const {merge,target_admission:target,validation}=delivery.local_integration||{};
  const gitObject=value=>typeof value==='string'&&/^(?:[a-f0-9]{40}|[a-f0-9]{64})$/.test(value);
  const sha256=value=>typeof value==='string'&&/^[a-f0-9]{64}$/.test(value);
  const exactMerge=gitObject(merge?.commit)&&gitObject(merge.tree)
   &&Array.isArray(merge.parents)&&merge.parents.length===2&&merge.parents.every(gitObject);
  const exactTarget=exactMerge&&target?.merge_commit===merge.commit&&sha256(target.profile_identity);
  const checked=exactTarget&&validation?.merge_commit===merge.commit&&validation.profile_identity===target.profile_identity
   &&Array.isArray(validation.checks)&&validation.checks.length>0&&validation.checks.every(check=>check?.exit_code===0)
   &&Array.isArray(validation.evidence)&&validation.evidence.length===1
   &&typeof validation.evidence[0]?.path==='string'&&sha256(validation.evidence[0].sha256);
  return !(delivery.implementation==='completed'&&delivery.status==='merged'&&delivery.order_completed===true&&checked);
 }
 return !(delivery.implementation==='completed'&&(['local-result','merged'].includes(delivery.status)||delivery.status==='pr-ready'&&!authorization.merge));
}
function hookCanonicalDocument(raw){
 // Preserve owned Python JSON numeric/string tokens; JS numeric rendering differs.
 let at=0;const space=()=>{while(/\s/.test(raw[at]||'')&&at<raw.length)at++;};
 function stringToken(){const begin=at++;let escaped=false;for(;at<raw.length;at++){const char=raw[at];if(!escaped&&char==='"'){at++;return raw.slice(begin,at);}if(!escaped&&char==='\\')escaped=true;else escaped=false;}throw Error('Malformed invocation JSON string');}
 function compare(left,right){const a=Array.from(left),b=Array.from(right);for(let i=0;i<Math.min(a.length,b.length);i++){const delta=a[i].codePointAt(0)-b[i].codePointAt(0);if(delta)return delta;}return a.length-b.length;}
 function value(depth){
  space();const char=raw[at];
  if(char==='"')return stringToken();
  if(char==='{'){
   at++;space();const entries=[];if(raw[at]==='}'){at++;return '{}';}
   while(true){space();if(raw[at]!=='"')throw Error('Malformed invocation JSON key');const key=stringToken(),name=JSON.parse(key);space();if(raw[at++]!==':')throw Error('Malformed invocation JSON object');const item=value(depth+1);if(depth!==0||name!=='chain_hash')entries.push({name,key,item});space();const separator=raw[at++];if(separator==='}')break;if(separator!==',')throw Error('Malformed invocation JSON object');}
   entries.sort((a,b)=>compare(a.name,b.name));return '{'+entries.map(item=>item.key+':'+item.item).join(',')+'}';
  }
  if(char==='['){at++;space();const items=[];if(raw[at]===']'){at++;return '[]';}while(true){items.push(value(depth+1));space();const separator=raw[at++];if(separator===']')break;if(separator!==',')throw Error('Malformed invocation JSON array');}return '['+items.join(',')+']';}
  const begin=at;while(at<raw.length&&!/[\s,}\]]/.test(raw[at]))at++;if(begin===at)throw Error('Malformed invocation JSON token');return raw.slice(begin,at);
 }
 const result=value(0);space();if(at!==raw.length)throw Error('Malformed invocation JSON suffix');return result;
}
function readHookRecords(root){
 const owner=queueRoot(root),directory=c.safe(owner,'.skill-tree/invocations');
 if(!fs.existsSync(directory))return [];
 if(!fs.lstatSync(directory).isDirectory())throw Error('Malformed invocation metadata directory; explicit recovery required');
 const records=[];
 for(const name of fs.readdirSync(directory).sort()){
  if(!/^hc-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}\.json$/.test(name))throw Error('Unknown invocation metadata; explicit recovery required');
  const file=c.safe(owner,'.skill-tree/invocations/'+name);let record;
  let raw;try{raw=fs.readFileSync(file,'utf8');record=JSON.parse(raw);}catch{throw Error('Malformed invocation metadata; explicit recovery required');}
  if(record.schema!==1||record.id?.toLowerCase()+'.json'!==name||typeof record.chain_hash!=='string'||!/^([a-f0-9]{64})$/.test(record.chain_hash)||!record.attempts||Array.isArray(record.attempts)||!Array.isArray(record.stages)||!Number.isSafeInteger(record.revision)||record.revision<1)throw Error('Unsupported invocation metadata; explicit recovery required');
  if(c.hash(hookCanonicalDocument(raw))!==record.chain_hash)throw Error('Invocation metadata checksum changed; explicit recovery required');
  for(const attempt of Object.values(record.attempts)){
   if(!attempt||!['prepared','invoking','unknown','returned','failed','unavailable','cancelled'].includes(attempt.status))throw Error('Malformed original invocation attempt; explicit recovery required');
  }
  if(record.state==='superseded'){
   const id=record.superseded_by;if(typeof id!=='string'||!/^HC-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(id)||!fs.existsSync(c.safe(owner,'.skill-tree/invocations/'+id.toLowerCase()+'.json')))throw Error('Missing invocation replacement; explicit recovery required');
  }
  records.push(record);
 }
 return records;
}
function pendingHookOperation(root){return readHookRecords(root).some(record=>Object.values(record.attempts).some(attempt=>['prepared','invoking','unknown'].includes(attempt.status)));}

function hasActiveOperation(root){
 if(pendingHookOperation(root))return true;
 const state=workflowState(root);if(!state)return false;
 for(const progress of Object.values(state.task_progress))for(const slot of Object.values(progress.checks||{})){
  const attempt=slot.attempt;if(attempt&&!Object.values(slot.receipts||{}).some(r=>r.attempt_id===attempt.attempt_id)&&slot.result?.attempt_id!==attempt.attempt_id&&slot.red?.attempt_id!==attempt.attempt_id)return true;
 }
 const active=run=>{
  if(!run)return false;
  if(run.maintenance!==undefined&&run.maintenance!==null){
   const focus=run.maintenance;
   if(typeof focus!=='object'||Array.isArray(focus)||typeof focus.phase!=='string'||!focus.phase)throw Error('Unsupported maintenance checkpoint; explicit recovery required');
   if(active(focus))return true;
  }
  return unfinishedRun(run)&&!run.stop_reason&&!['blocked','validate','awaiting-validation','refresh-profile','validation-blocked'].includes(run.phase);
 };
 const runs=state.run_registry?Object.values(state.run_registry.runs):[state.active_run];return runs.some(active);
}
function stoppedWorkflow(root){
 const state=workflowState(root);if(!state||queueRoot(root)!==root)return null;
 const runs=state.run_registry?Object.values(state.run_registry.runs):[state.active_run];
 const unfinished=runs.filter(unfinishedRun);if(!unfinished.length)return null;
 for(const run of unfinished){run.profile_refresh_required=true;
 if(!run.stop_reason)run.stop_reason='Installation profile changed; re-admit before continuation';}
 return c.json(state);
}
function materialize(root,rel,files){const dest=c.safe(root,rel);fs.mkdirSync(dest,{recursive:true});for(const [name,content] of Object.entries(files)){const file=c.safe(root,path.posix.join(rel,name));if(fs.existsSync(file))throw Error('Staged resource path collision: '+name);fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,content);}}
function transactionPaths(channel='core'){
 if(!['core','plugins'].includes(channel))throw Error('Unsupported installation transaction channel');
 return channel==='core'?{stage:INSTALL+'/.staging',backups:INSTALL+'/.backups',journal:INSTALL+'/.journal.json',last:INSTALL+'/.last-transaction.json'}:{stage:INSTALL+'/.plugin-staging',backups:INSTALL+'/.plugin-backups',journal:INSTALL+'/.plugin-journal.json',last:INSTALL+'/.last-plugin-transaction.json'};
}
function recover(root,channel='core'){
 const paths=transactionPaths(channel),journal=c.readJson(root,paths.journal,null);if(!journal)return;
 const tree=rel=>treeHash(root,rel,channel==='plugins');
 if(journal.schema!==1||!Array.isArray(journal.entries)||Object.hasOwn(journal,'channel')&&journal.channel!==channel||channel==='plugins'&&journal.channel!=='plugins')throw Error('Unsupported installation journal');
 for(const e of journal.entries){
  const belongs=(rel,base)=>typeof rel==='string'&&path.posix.normalize(rel)===rel&&!rel.includes('\\')&&rel.startsWith(base+'/');
  if(!belongs(e.backup,paths.backups)||e.staged!==null&&!belongs(e.staged,paths.stage))throw Error('Installation journal mixes transaction channels');
  const actual=tree(e.dest),backup=tree(e.backup),stage=e.staged?tree(e.staged):null;
  if(actual!==e.old&&actual!==e.next&&!(actual===null&&backup===e.old))throw Error('Interrupted installation conflicts: '+e.dest);
  if(e.next!==null&&actual!==e.next&&stage!==e.next)throw Error('Missing or modified staged generation: '+e.dest);
 }
 for(const e of journal.entries){
  if(tree(e.dest)===e.next)continue;
  const dest=c.safe(root,e.dest),backup=c.safe(root,e.backup);
  if(fs.existsSync(dest)){fs.mkdirSync(path.dirname(backup),{recursive:true});if(fs.existsSync(backup))throw Error('Recovery backup conflict: '+e.dest);fs.renameSync(dest,backup);}
  if(e.staged){fs.mkdirSync(path.dirname(dest),{recursive:true});fs.renameSync(c.safe(root,e.staged),dest);}
 }
 fs.writeFileSync(c.safe(root,paths.last),c.json(journal));
 fs.unlinkSync(c.safe(root,paths.journal));
 fs.rmSync(c.safe(root,paths.stage),{recursive:true,force:true});
 // Backups retain one completed generation for explicit reviewed rollback.
}
function transaction(root,changes,expected={},beforeActivate=null,channel='core'){
 const {stage,backups,journal}=transactionPaths(channel);
 const tree=rel=>treeHash(root,rel,channel==='plugins');
 if(fs.existsSync(c.safe(root,stage)))fs.rmSync(c.safe(root,stage),{recursive:true});
 for(const [dest,hash] of Object.entries(expected))if(tree(dest)!==hash)throw Error('Destination changed after ownership validation: '+dest);
 const entries=[];let n=0;
 for(const [dest,change] of Object.entries(changes)){
  const old=Object.hasOwn(expected,dest)?expected[dest]:tree(dest),backup=backups+'/'+n,staged=change===null?null:stage+'/'+n;
  if(change!==null){if(typeof change==='string'||Buffer.isBuffer(change)||change instanceof Uint8Array){const p=c.safe(root,staged);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,change);}else materialize(root,staged,change);}
  const next=staged?tree(staged):null;
  if(old!==next)entries.push({dest,old,next,backup,staged});n++;
 }
 for(const [dest,hash] of Object.entries(expected))if(tree(dest)!==hash)throw Error('Destination changed during staging: '+dest);
 if(beforeActivate){try{beforeActivate();}catch(error){fs.rmSync(c.safe(root,stage),{recursive:true,force:true});throw error;}}
 if(!entries.length){fs.rmSync(c.safe(root,stage),{recursive:true,force:true});return;}
 if(fs.existsSync(c.safe(root,backups)))fs.rmSync(c.safe(root,backups),{recursive:true});
 fs.writeFileSync(c.safe(root,journal),c.json({schema:1,channel,entries}));recover(root,channel);
}
function locked(root,action){
 const owner=queueRoot(root),barrier=owner!==root?path.join(owner,INSTALL+'/.install-lock'):null;let barrierFd;
 if(barrier){fs.mkdirSync(path.dirname(barrier),{recursive:true});try{barrierFd=fs.openSync(barrier,'wx',0o600);fs.writeFileSync(barrierFd,c.json({pid:process.pid,host:require('node:os').hostname()}));}catch{throw Error('Canonical installation lock exists');}}
 const dir=c.safe(root,INSTALL);fs.mkdirSync(dir,{recursive:true});const lock=c.safe(root,INSTALL+'/.install-lock');let fd;
 try{fd=fs.openSync(lock,'wx',0o600);}catch{if(barrier){fs.closeSync(barrierFd);fs.unlinkSync(barrier);}throw Error('Installation lock exists; inspect PID/host before explicit removal');}
 try{fs.writeFileSync(fd,c.json({pid:process.pid,host:require('node:os').hostname()}));if(fs.existsSync(c.safe(owner,'.skill-tree/.writer-lock')))throw Error('Workflow writer lock exists; reach a cleanup/handoff boundary before installation');
  const pending=['core','plugins'].some(channel=>fs.existsSync(c.safe(root,transactionPaths(channel).journal)));
  if(pending&&hasActiveOperation(root))throw Error('Active controller must reach a stopped cleanup/handoff before transaction recovery');
  recover(root);recover(root,'plugins');return action();
 }finally{fs.closeSync(fd);fs.unlinkSync(lock);if(barrier){fs.closeSync(barrierFd);fs.unlinkSync(barrier);}}
}
function bundle(source,flavor){
 const files={};for(const rel of Object.keys(c.sourceInputs(source))){
  if(rel.startsWith('domains/')&&!rel.startsWith('domains/'+flavor+'/'))continue;
  if(rel==='config/repository.json')continue;
  files['source/'+rel]=c.read(source,rel);
 }
 files['manager.js']="#!/usr/bin/env node\n'use strict';\nconst path=require('node:path');\nconst manager=require('./source/lib/installation.js');\nprocess.exitCode=manager.localMain(path.resolve(__dirname,'../..'),path.join(__dirname,'source'),process.argv.slice(2));\n";
 return files;
}
function plan(root,source,flavor,selections,options={}){
 const profileBefore=treeHash(root,PROFILE);const old=receipt(root);if(old)verifyOwned(root,old);
 const workflowBefore=treeHash(root,WORKFLOW);
 if(!old&&fs.existsSync(c.safe(root,INSTALL))&&fs.readdirSync(c.safe(root,INSTALL)).some(name=>name!=='.install-lock'))throw Error('Unowned maintenance directory conflict');
 if(hasActiveOperation(root))throw Error('Active controller must checkpoint at a stopped cleanup/handoff point before installation or refresh');
 if(old)for(const rel of Object.keys(old.destinations))selections.push({rel,provider:old.destinations[rel].provider,name:old.destinations[rel].name});
 const merged={};for(const item of selections){if(!merged[item.rel])merged[item.rel]={...item,providers:[]};merged[item.rel].providers=[...new Set([...merged[item.rel].providers,...(item.providers||[item.provider])])].sort();}
 const unique=Object.values(merged),names=[...new Set(unique.map(s=>s.name))];
 const profile=c.resolveProfile(source,root,flavor),built=c.compose(source,profile,names),changes={},destinations={...(old?.destinations||{})};
 for(const item of unique){
  const current=filesAt(root,item.rel),owned=old?.destinations[item.rel];
  if(current&&!owned)throw Error('Unowned destination conflict, including --force: '+item.rel);
  const files=built.packages[item.name];if(!files)throw Error('Missing composed operation: '+item.name);
  changes[item.rel]=files;destinations[item.rel]={provider:owned?.provider||item.provider,providers:[...new Set([...(owned?owners(owned):[]),...item.providers])].sort(),name:item.name,flavor,files:built.output_digests[item.name],identity:c.hash(c.json(built.output_digests[item.name]))};
 }
 const bridges={...(old?.bridges||{})},bridgeBefore={};
 for(const rel of new Set([...(options.bridges||[]),...Object.keys(old?.bridges||{})])){
  const current=c.read(root,rel)||'',existing=bridgeBlock(current);bridgeBefore[rel]=treeHash(root,rel);
  if(existing&&!old?.bridges[rel])throw Error('Unowned bridge conflict: '+rel);
  const block=BEGIN+'\n'+c.read(source,'src/init-rules/skill-tree-skills.md').trim()+'\nFlavor: '+flavor+'. Profile: `.skill-tree/installation/profile.json`.\n'+END;
  changes[rel]=existing?current.replace(existing,block):current+(current.endsWith('\n')?'\n':'\n\n')+block+'\n';
  bridges[rel]={hash:c.hash(block),providers:[...new Set([...(old?.bridges[rel]?.providers||[]),...(options.bridges?.includes(rel)&&options.provider?[options.provider]:[])])].sort()};
 }
 const maintenance=bundle(source,flavor),bundle_digests={};
 for(const [rel,content] of Object.entries(maintenance)){const dest=INSTALL+'/'+rel;if(fs.existsSync(c.safe(root,dest))&&!old?.bundle_digests[dest])throw Error('Unowned maintenance file conflict: '+dest);changes[dest]=content;bundle_digests[dest]=c.hash(content);}
 for(const rel of Object.keys(old?.bundle_digests||{}))if(!bundle_digests[rel])changes[rel]=null;
 const next={...profile,source_digests:built.source_digests,destinations,bridges,bundle_digests,identity:built.identity};
 changes[PROFILE]=c.json(next);
 if(old?.identity!==next.identity){const stopped=stoppedWorkflow(root);if(stopped)changes[WORKFLOW]=stopped;}
 const expected={};
 for(const rel of Object.keys(changes)){
  if(old?.destinations[rel])expected[rel]=c.hash(c.json(old.destinations[rel].files));
  else if(old?.bundle_digests[rel])expected[rel]=c.hash(c.json({'':old.bundle_digests[rel]}));
  else if(rel===PROFILE)expected[rel]=profileBefore;
  else if(rel===WORKFLOW)expected[rel]=workflowBefore;
  else if(Object.hasOwn(bridgeBefore,rel))expected[rel]=bridgeBefore[rel];
  else expected[rel]=null;
 }
 const delta=Object.entries(changes).filter(([rel,change])=>{
  const expected=change===null?null:typeof change==='string'?c.hash(c.json({'':c.hash(change)})):c.hash(c.json(Object.fromEntries(Object.entries(change).map(([rel,text])=>[rel,c.hash(text)]))));
  return treeHash(root,rel)!==expected;
 }).map(([rel])=>rel);
 return {profile:next,changes,delta,old,expected};
}
function verify(root,source,allowForeign=false){
 if(fs.existsSync(c.safe(root,transactionPaths('plugins').journal)))throw Error('Plugin installation recovery is required before profile verification');
 const p=receipt(root,true,allowForeign);verifyOwned(root,p);const bundleSource=c.safe(root,INSTALL+'/source');
 const now=c.resolveProfile(bundleSource,root,p.flavor);
 for(const field of ['source_version','inputs','inventory','facts','recipes','gaps','environment_id','execution_bindings','worktree_environment'])if(c.json(now[field])!==c.json(p[field]))throw Error('Profile refresh-required or resolved profile mismatch: node .skill-tree/installation/manager.js --refresh-profile');
 if(p.identity!==compositionIdentity(p))throw Error('Composition receipt identity mismatch');
 const generated=c.compose(bundleSource,now,[...new Set(Object.values(p.destinations).map(record=>record.name))]);
 const providers=c.readJson(bundleSource,'config/providers.json').providers;
 for(const [rel,record] of Object.entries(p.destinations)){
  if(record.flavor!==p.flavor||record.identity!==c.hash(c.json(record.files))||c.json(generated.output_digests[record.name])!==c.json(record.files))throw Error('Package identity/flavor does not match deterministic composition: '+rel);
  if(owners(record).some(id=>{const provider=providers.find(p=>p.id===id);return !provider||rel!==path.posix.join(provider.id==='generic'?'':provider.projectPath,record.name);}))throw Error('Provider ownership disagrees with the scoped destination: '+rel);
 }
 for(const [rel,digest] of Object.entries(p.bundle_digests))if(rel.startsWith(INSTALL+'/source/')&&p.source_digests[rel.slice((INSTALL+'/source/').length)]!==digest)throw Error('Bundle and source recipe identities disagree');
 return p;
}
function install(root,source,flavor,selections,options={}){
 if(options.dryRun){const result=plan(root,source,flavor,selections,options);return {profile:result.profile,delta:result.delta,action:'dry-run'};}
 return locked(root,()=>{
  const result=plan(root,source,flavor,selections,options);
  transaction(root,result.changes,result.expected,()=>{const current=c.resolveProfile(source,root,flavor);if(current.environment_id!==result.profile.environment_id)throw Error('Project inputs changed during profile staging; refresh from current inputs');});
  try{verify(root,source);}catch(error){
   if(result.delta.length){try{restoreGeneration(root);}catch(recovery){throw Error('Profile verification failed; preserved generation backups require conflict review: '+error.message+'; '+recovery.message);}}
   throw error;
  }
  return {profile:result.profile,delta:result.delta,action:result.delta.length?'installed':'verified no-op current'};
 });
}
function uninstall(root,selections,options={}){
 function action(){const p=receipt(root,true);verifyOwned(root,p);if(hasActiveOperation(root))throw Error('Active controller must stop before uninstall');const next=JSON.parse(c.json(p)),changes={},expected={};
  for(const item of selections){const record=p.destinations[item.rel];if(!record||!owners(record).includes(item.provider))throw Error('Unowned uninstall destination for the selected provider: '+item.rel);
   const remaining=owners(next.destinations[item.rel]).filter(provider=>provider!==item.provider);
   if(remaining.length){next.destinations[item.rel].providers=remaining;next.destinations[item.rel].provider=remaining[0];}
   else{changes[item.rel]=null;expected[item.rel]=c.hash(c.json(record.files));delete next.destinations[item.rel];}
  }
  if(options.withInit){const active=new Set(Object.values(next.destinations).flatMap(owners));
   for(const [rel,record] of Object.entries(p.bridges||{})){
    const remaining=(record.providers||[]).filter(provider=>active.has(provider));
    if(remaining.length){next.bridges[rel].providers=remaining;continue;}
    const current=c.read(root,rel),block=bridgeBlock(current);changes[rel]=current.replace(block,'');expected[rel]=treeHash(root,rel);delete next.bridges[rel];
   }
  }
  next.identity=compositionIdentity(next);const stopped=stoppedWorkflow(root);if(stopped){changes[WORKFLOW]=stopped;expected[WORKFLOW]=treeHash(root,WORKFLOW);}
  changes[PROFILE]=c.json(next);expected[PROFILE]=treeHash(root,PROFILE);if(!options.dryRun)transaction(root,changes,expected);return {action:options.dryRun?'dry-run uninstall':'removed',profile:next,delta:Object.keys(changes)};
 }
 return options.dryRun?action():locked(root,action);
}
function refresh(root,source,dryRun=false){const p=receipt(root,true);return install(root,source,p.flavor,Object.entries(p.destinations).map(([rel,d])=>({rel,provider:d.provider,name:d.name})),{dryRun,bridges:Object.keys(p.bridges||{})});}
function restoreGeneration(root){
 const p=receipt(root,true);verifyOwned(root,p);if(hasActiveOperation(root))throw Error('Stop the active controller before rollback');
 const last=c.readJson(root,INSTALL+'/.last-transaction.json',null);if(!last)throw Error('No retained generation for rollback');
 const changes={},expected={};
 for(const e of last.entries){
  if(e.dest===WORKFLOW)continue;
  if(treeHash(root,e.dest)!==e.next)throw Error('Rollback conflicts with current content: '+e.dest);
  expected[e.dest]=e.next;
  if(e.old===null){changes[e.dest]=null;continue;}
  if(treeHash(root,e.backup)!==e.old)throw Error('Rollback backup is unavailable: '+e.dest);
  const full=c.safe(root,e.backup);
  if(fs.lstatSync(full).isFile())changes[e.dest]=fs.readFileSync(full,'utf8');
  else changes[e.dest]=Object.fromEntries(Object.keys(filesAt(root,e.backup)).map(rel=>[rel,fs.readFileSync(c.safe(root,e.backup+'/'+rel),'utf8')]));
 }
 const stopped=stoppedWorkflow(root);if(stopped){changes[WORKFLOW]=stopped;expected[WORKFLOW]=treeHash(root,WORKFLOW);}
 transaction(root,changes,expected);return {action:'generation rolled back; project dependencies unchanged; verify freshness before admission'};
}
function rollback(root){return locked(root,()=>restoreGeneration(root));}
function rebind(root,source){
 if(['core','plugins'].some(channel=>{const p=transactionPaths(channel);return fs.existsSync(c.safe(root,p.journal))||fs.existsSync(c.safe(root,p.stage));}))throw Error('Recover the original installation transaction before explicit rebind');
 verify(root,source,true);
 return locked(root,()=>{
  const p=verify(root,source,true),project_root=fs.realpathSync(root);
  if(p.project_root===project_root)return {action:'verified no-op current'};
  if(hasActiveOperation(root))throw Error('Active controller must reach a stopped handoff before rebind');
  transaction(root,{[PROFILE]:c.json({...p,project_root})},{[PROFILE]:treeHash(root,PROFILE)},()=>verify(root,source,true));
  verify(root,source);return {action:'verified installation rebound; recover the queue locator explicitly when required'};
 });
}
function localMain(root,source,args){
 try{
  if(args.includes('--list-plugins'))return require('./plugins.js').listMain(root,args,{source});
  if(args.some(a=>!['--refresh-profile','--dry-run','--verify','--recover','--rollback','--rebind'].includes(a)))throw Error('Usage: manager.js --refresh-profile [--dry-run] | --verify | --recover | --rollback | --rebind');
  const operations=args.filter(a=>a!=='--dry-run');
  if(operations.length!==1||args.filter(a=>a==='--dry-run').length>1||args.includes('--dry-run')&&operations[0]!=='--refresh-profile')throw Error('Select exactly one manager operation; --dry-run applies only to --refresh-profile');
  if(args.includes('--rebind')){console.log(c.json(rebind(root,source)));return 0;}
  if(args.includes('--rollback')){console.log(c.json(rollback(root)));return 0;}
  if(args.includes('--recover')){locked(root,()=>{});console.log('Installation recovery complete');return 0;}
  if(args.includes('--verify')){verify(root,source);console.log('Owned installation verified');return 0;}
  if(!args.includes('--refresh-profile'))throw Error('Use --refresh-profile or --verify');
  const result=refresh(root,source,args.includes('--dry-run'));console.log(c.json({action:result.action,changed:result.delta,facts:result.profile.facts,gaps:result.profile.gaps}));return 0;
 }catch(error){console.error(error.message);return 2;}
}
module.exports={INSTALL,PROFILE,filesAt,treeHash,receipt,verifyOwned,bridgeBlock,transactionPaths,recover,transaction,locked,queueRoot,workflowState,hasActiveOperation,readHookRecords,pendingHookOperation,stoppedWorkflow,plan,install,verify,uninstall,refresh,rollback,rebind,localMain};
