'use strict';
const fs=require('node:fs'),path=require('node:path');
const {randomUUID}=require('node:crypto');
const c=require('./composer.js');
const development=require('./development-policies.js');
const BEGIN='<!-- BEGIN skill-tree-skills -->',END='<!-- END skill-tree-skills -->';
const INSTALL='.skill-tree/installation',PROFILE=INSTALL+'/profile.json';
const AGENTS_PATH='AGENTS.md',REGENERATE_AGENTS=Symbol('regenerate-agents');
const INITIAL_WORKTREE_PROFILE=Symbol('initial-worktree-profile');
const SETUP_OPERATIONS='.skill-tree/artifacts/setup-operations';
const setupOperationId=/^OP-[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const isCodexBridge=record=>Array.isArray(record?.providers)&&record.providers.includes('codex');
const TASK_GROUPING_SOURCE='common/scripts/workflow-state.py';
const TASK_GROUPING_BUNDLE=INSTALL+'/source/'+TASK_GROUPING_SOURCE;
const TASK_GROUPING_HELPER='scripts/workflow-state.py';
const taskGroupingMarker=/^TASK_GROUPING_COMPATIBILITY = 1\r?$/m;
function filesAt(root,rel,includeCaches=false){
 const full=c.safe(root,rel);if(!fs.existsSync(full))return null;
 if(fs.lstatSync(full).isFile())return {'':c.hash(fs.readFileSync(full))};
 const out={};function walk(dir,prefix){for(const e of fs.readdirSync(dir,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){if(e.name==='__pycache__'&&!includeCaches&&!prefix.startsWith('plugins/'))continue;const child=path.join(dir,e.name),key=prefix+e.name;if(e.isSymbolicLink())throw Error('Symlink in owned package: '+rel+'/'+key);if(e.isDirectory())walk(child,key+'/');else if(e.isFile())Object.defineProperty(out,key,{value:c.hash(fs.readFileSync(child)),enumerable:true,writable:true,configurable:true});else throw Error('Unsupported owned entry: '+key);}}walk(full,'');return out;
}
const owners=record=>record.providers||[record.provider];
function compositionIdentity(profile){
 const outputs=Object.fromEntries(Object.values(profile.destinations).map(record=>[record.name,record.files]));
 return c.hash(c.json({flavor:profile.flavor,environment_id:profile.environment_id,source_digests:profile.source_digests,output_digests:outputs}));
}
const treeHash=(root,rel,includeCaches=false)=>{const files=filesAt(root,rel,includeCaches);return files===null?null:c.hash(c.json(files));};
function hasRetainedCore(root){
 return [INSTALL+'/manager.js',INSTALL+'/source'].some(relative=>fs.existsSync(c.safe(root,relative)));
}
function missingReceipt(root){
 const recovery=hasRetainedCore(root)
  ? 'Restore the matching ownership receipt for the retained maintenance bundle and run the owned manager --verify.'
  : 'Install Skill Tree with an explicit --flavor if this is a new target.';
 return Error('Missing ownership receipt: '+PROFILE+'. '+recovery);
}
function receipt(root,required=false,allowForeign=false){
 const p=c.readJson(root,PROFILE,null);
 if(!p){if(required)throw missingReceipt(root);return null;}
 if(p.format!=='skill-tree-profile'||p.schema!==1||typeof p.project_root!=='string'||!allowForeign&&p.project_root!==fs.realpathSync(root)||!p.destinations||!p.bundle_digests)throw Error('Unsupported or foreign ownership receipt; use the manual update checklist');
 return p;
}
function verifyOwned(root,p,includeBundle=true,operation){
 if(p.identity!==compositionIdentity(p))throw Error('Composition receipt identity mismatch');
 for(const [rel,record] of Object.entries(p.destinations)){
  if(!/^skill-tree-[a-z0-9-]+$/.test(record.name)||path.basename(rel)!==record.name)throw Error('Invalid owned destination');
  const actual=filesAt(root,rel);
  if(c.json(actual)!==c.json(record.files)){
   const missing=actual&&Object.keys(record.files).find(file=>!Object.hasOwn(actual,file));
   const location=missing?rel+'/'+missing:rel;
   throw Error('Unowned or locally modified package conflicts: '+location+'. Restore the matching owned package before retrying.');
  }
 }
 if(includeBundle){
  for(const [rel,hash] of Object.entries(p.bundle_digests)){
   const content=c.read(root,rel);
   if(content===null)throw Error('Missing maintenance bundle file: '+rel+'. Restore the missing file from the matching maintenance generation.');
   if(c.hash(content)!==hash)throw Error('Modified maintenance bundle: '+rel);
  }
  const actual=filesAt(root,INSTALL+'/source');
  const expected=Object.fromEntries(Object.entries(p.bundle_digests).filter(([rel])=>rel.startsWith(INSTALL+'/source/')).map(([rel,hash])=>[rel.slice((INSTALL+'/source/').length),hash]));
  if(c.json(actual)!==c.json(expected))throw Error('Unowned or missing maintenance source inventory');
 }
 for(const [rel,record] of Object.entries(p.bridges||{})){
  const current=c.read(root,rel);
  const missingAgents=current===null&&rel===AGENTS_PATH&&isCodexBridge(record);
  if(missingAgents&&operation===REGENERATE_AGENTS)continue;
  const block=bridgeBlock(current||'');
  if(!block||c.hash(block)!==record.hash){
   const recovery=missingAgents?' To preview a fresh managed file, run node .skill-tree/installation/manager.js --regenerate-agents --dry-run.':'';
   throw Error('Modified or missing owned bridge: '+rel+'. Restore the registered instruction file from a verified matching copy before retrying.'+recovery);
  }
 }
}
function bridgeBlock(text){
 const a=text.indexOf(BEGIN),b=text.indexOf(END);if(a<0&&b<0)return null;
 if(a<0||b<a||text.indexOf(BEGIN,a+BEGIN.length)>=0||text.indexOf(END,b+END.length)>=0)throw Error('Ambiguous bridge markers');
 return text.slice(a,b+END.length);
}
function renderBridge(source,flavor,profile){
 const policyInstructions=development.instructions(profile);
 return BEGIN+'\n'+c.read(source,'src/init-rules/skill-tree-skills.md').trim()+'\nFlavor: '+flavor+'. Profile: `.skill-tree/installation/profile.json`.\n'+(policyInstructions?'\n'+policyInstructions+'\n':'')+END;
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
function groupedTaskHeaders(root){
 const future=c.read(queueRoot(root),'.skill-tree/documents/future.md');
 if(future===null)return false;
 const lines=future.split(/\r?\n/),queues=new Set(['Pending Queue','Prioritized Next Changes','Backlog']);
 let fenced=false,inQueue=false;
 for(let index=0;index<lines.length;index++){
  const line=lines[index];
  if(line.startsWith('```')){fenced=!fenced;continue;}
  if(fenced)continue;
  const heading=line.match(/^##\s+(.+?)\s*$/);
  if(heading)inQueue=queues.has(heading[1]);
  if(!inQueue||!/^###\s+\S/.test(line))continue;
  let header=index+1;
  while(header<lines.length&&!lines[header].trim())header++;
  if(lines[header]!=='```yaml')continue;
  for(let field=header+1;field<lines.length&&!lines[field].startsWith('```');field++){
   if(/^\s*(?:topic|intake_batch_ids)\s*:/.test(lines[field]))return true;
  }
 }
 return false;
}
function usesSharedWorkflow(profile){
 const layout=profile?.workflow_runtime;
 if(layout!==undefined&&layout!=='owned-v1')throw Error('Unknown owned workflow runtime layout');
 return layout==='owned-v1';
}
function taskGroupingProof(profile,readSource){
 const source=readSource();
 if(source===null||!taskGroupingMarker.test(String(source)))return undefined;
 const digest=c.hash(source);
 if(profile.source_digests[TASK_GROUPING_SOURCE]!==digest||profile.bundle_digests[TASK_GROUPING_BUNDLE]!==digest)return undefined;
 const providers=profile.bundle_digests[INSTALL+'/source/config/providers.json'];
 const helperDigest=usesSharedWorkflow(profile)?c.hash(c.sharedWorkflowEntrypoint(source,providers)):digest;
 const helpers=Object.entries(profile.destinations).filter(([,record])=>Object.hasOwn(record.files,TASK_GROUPING_HELPER));
 if(!helpers.length||helpers.some(([,record])=>record.files[TASK_GROUPING_HELPER]!==helperDigest))return undefined;
 return {schema:1,source_helper_sha256:digest,package_helpers:Object.fromEntries(helpers.map(([rel])=>[rel+'/'+TASK_GROUPING_HELPER,helperDigest]))};
}
function verifyTaskGroupingProof(profile,readFile){
 if(!profile||!Object.hasOwn(profile,'task_grouping'))return undefined;
 const proof=taskGroupingProof(profile,()=>readFile(TASK_GROUPING_BUNDLE));
 if(!proof||c.json(proof)!==c.json(profile.task_grouping)||Object.entries(proof.package_helpers).some(([rel,digest])=>{
  const file=readFile(rel);return file===null||c.hash(file)!==digest;
 }))throw Error('Task grouping capability does not match owned source and package bytes');
 return proof;
}
function groupingFileReader(root,changes={}){
 return relative=>{
  if(Object.hasOwn(changes,relative))return changes[relative];
  const packagePath=path.posix.dirname(path.posix.dirname(relative));
  if(Object.hasOwn(changes,packagePath))return changes[packagePath]?.[TASK_GROUPING_HELPER]??null;
  const file=c.safe(root,relative);
  return fs.existsSync(file)?fs.readFileSync(file):null;
 };
}
function requireGroupedQueueCompatibility(root,profile,readFile=groupingFileReader(root)){
 if(groupedTaskHeaders(root)&&!verifyTaskGroupingProof(profile,readFile))throw Error('Grouped task headers require a compatible owned installation generation');
}
function verifyTaskGroupingProfile(root){
 root=fs.realpathSync(root);
 const profileFile=c.safe(root,PROFILE),before=fs.existsSync(profileFile)?c.hash(fs.readFileSync(profileFile)):null;
 const profile=verify(root,c.safe(root,INSTALL+'/source'));
 const proof=verifyTaskGroupingProof(profile,groupingFileReader(root));
 if(!proof)throw Error('Owned profile lacks verified task grouping support');
 if(!before||c.hash(fs.readFileSync(profileFile))!==before)throw Error('Owned profile changed during task grouping verification');
 return {project_root:root,profile_identity:profile.identity,profile_sha256:before,...proof};
}
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
 if(run.reviewed_local_delivery&&delivery.publication==='not-requested'){
  return !(delivery.implementation==='completed'&&delivery.order_completed===true&&['review-ready','merged'].includes(delivery.status));
 }
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
function verifyPluginBackups(root){
 const {backups,last}=transactionPaths('plugins'),directory=c.safe(root,backups);
 const actual=fs.existsSync(directory)?fs.readdirSync(directory).sort():[];
 const retained=c.readJson(root,last,null);
 const conflict=()=>Error('Unowned or modified retained plugin backups');
 if(!retained){if(fs.existsSync(directory)||fs.existsSync(c.safe(root,last)))throw conflict();return;}
 if(retained.schema!==1||retained.channel!=='plugins'||!Array.isArray(retained.entries))throw conflict();
 const expected=[];
 for(const {backup,old} of retained.entries){
  if(typeof backup!=='string'||path.posix.dirname(backup)!==backups||!/^\d+$/.test(path.posix.basename(backup))||treeHash(root,backup,true)!==old)throw conflict();
  if(old!==null)expected.push(path.posix.basename(backup));
 }
 if(c.json(actual)!==c.json(expected.sort()))throw conflict();
}
function recover(root,channel='core',observed){
 const paths=transactionPaths(channel);
 let journal;
 if(observed===undefined)journal=c.readJson(root,paths.journal,null);
 else{
  const raw=setupProofBytes(root,paths.journal);
  const current=raw===null?null:Buffer.isBuffer(raw)?c.hash(raw):'unavailable';
  if(current==='unavailable'||current!==observed)throw Error('Cannot recover a journal without its exact sealed bytes');
  if(raw!==null){journal=JSON.parse(raw.toString('utf8').replace(/^\uFEFF/,''));if(!journal)throw Error('Unsupported installation journal');}
 }
 if(!journal)return;
 const tree=rel=>treeHash(root,rel,channel==='plugins');
 if(journal.schema!==1||!Array.isArray(journal.entries)||Object.hasOwn(journal,'channel')&&journal.channel!==channel||channel==='plugins'&&journal.channel!=='plugins')throw Error('Unsupported installation journal');
 for(const e of journal.entries){
  const belongs=(rel,base)=>typeof rel==='string'&&path.posix.normalize(rel)===rel&&!rel.includes('\\')&&rel.startsWith(base+'/');
  if(!belongs(e.backup,paths.backups)||e.staged!==null&&!belongs(e.staged,paths.stage))throw Error('Installation journal mixes transaction channels');
  const actual=tree(e.dest),backup=tree(e.backup),stage=e.staged?tree(e.staged):null;
  if(actual!==e.old&&actual!==e.next&&!(actual===null&&backup===e.old))throw Error('Interrupted installation conflicts: '+e.dest);
  if(e.next!==null&&actual!==e.next&&stage!==e.next)throw Error('Missing or modified staged generation: '+e.dest);
 }
 if(channel==='core'&&groupedTaskHeaders(root)){
  const readNext=relative=>{
   const entry=journal.entries.find(item=>relative===item.dest||relative.startsWith(item.dest+'/'));
   if(!entry)return groupingFileReader(root)(relative);
   if(entry.next===null)return null;
   const stage=tree(entry.dest)===entry.next?entry.dest:entry.staged;
   const file=c.safe(root,stage+relative.slice(entry.dest.length));
   return fs.existsSync(file)?fs.readFileSync(file):null;
  };
  const nextProfile=readNext(PROFILE);
  requireGroupedQueueCompatibility(root,nextProfile===null?null:JSON.parse(nextProfile),readNext);
 }
 for(const e of journal.entries){
  if(tree(e.dest)===e.next)continue;
  const dest=c.safe(root,e.dest),backup=c.safe(root,e.backup);
  if(fs.existsSync(dest)){fs.mkdirSync(path.dirname(backup),{recursive:true});if(fs.existsSync(backup))throw Error('Recovery backup conflict: '+e.dest);fs.renameSync(dest,backup);}
  if(e.staged){fs.mkdirSync(path.dirname(dest),{recursive:true});fs.renameSync(c.safe(root,e.staged),dest);}
 }
 if(channel==='core'&&journal.entries.some(entry=>entry.dest===PROFILE&&entry.next===null)){
  // An initial-generation rollback leaves no core manager or rollback owner.
  const source=INSTALL+'/source';
  if(Object.keys(filesAt(root,source)||{}).length)throw Error('Unexpected maintenance source remained after rollback');
  fs.rmSync(c.safe(root,source),{recursive:true,force:true});
  fs.rmSync(c.safe(root,paths.last),{force:true});
  fs.rmSync(c.safe(root,paths.backups),{recursive:true,force:true});
 }else fs.writeFileSync(c.safe(root,paths.last),c.json(journal));
 fs.rmSync(c.safe(root,paths.stage),{recursive:true,force:true});
 fs.unlinkSync(c.safe(root,paths.journal));
 // Backups retain one completed generation for explicit reviewed rollback.
}
function transaction(root,changes,expected={},beforeActivate=null,channel='core',sealJournal){
 const {stage,backups,journal}=transactionPaths(channel);
 const plugin=channel==='plugins',tree=rel=>treeHash(root,rel,plugin);
 const staging=c.safe(root,stage),journalPath=c.safe(root,journal);
 let sealed;
 if(fs.existsSync(staging)){
  if(plugin)throw Error('Plugin staging already exists; inspect the retained files before retrying');
  fs.rmSync(staging,{recursive:true});
 }
 for(const [dest,hash] of Object.entries(expected))if(tree(dest)!==hash)throw Error('Destination changed after ownership validation: '+dest);
 fs.mkdirSync(staging);
 try{
  const entries=[];let n=0;
  for(const [dest,change] of Object.entries(changes)){
   const old=Object.hasOwn(expected,dest)?expected[dest]:tree(dest),backup=backups+'/'+n,staged=change===null?null:stage+'/'+n;
   if(change!==null){if(typeof change==='string'||Buffer.isBuffer(change)||change instanceof Uint8Array){const p=c.safe(root,staged);fs.mkdirSync(path.dirname(p),{recursive:true});fs.writeFileSync(p,change);}else materialize(root,staged,change);}
   const next=staged?tree(staged):null;
   if(old!==next)entries.push({dest,old,next,backup,staged});n++;
  }
  for(const [dest,hash] of Object.entries(expected))if(tree(dest)!==hash)throw Error('Destination changed during staging: '+dest);
  if(beforeActivate)beforeActivate();
  if(!entries.length)return;
  if(plugin)verifyPluginBackups(root);
  const metadata=plugin?{}:{project_root:fs.realpathSync(root)};
  const journalBytes=c.json({schema:1,channel,entries,...metadata});
  if(sealJournal){sealJournal(journalBytes);sealed=c.hash(journalBytes);}
  if(fs.existsSync(c.safe(root,backups)))fs.rmSync(c.safe(root,backups),{recursive:true});
  fs.writeFileSync(journalPath,journalBytes);
 }finally{
  if(!fs.existsSync(journalPath))fs.rmSync(staging,{recursive:true,force:true});
 }
 recover(root,channel,sealed);
}
function setupProofBytes(root,relative,limit=16*1024*1024){
 try{
  const file=c.safe(root,relative);
  const stat=fs.lstatSync(file,{throwIfNoEntry:false});
  if(!stat)return null;
  if(!stat.isFile()||stat.size>limit)return 'unavailable';
  const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
  try{
   const actual=fs.fstatSync(fd);
   if(!actual.isFile()||actual.dev!==stat.dev||actual.ino!==stat.ino||actual.size>limit)return 'unavailable';
   const raw=Buffer.alloc(actual.size+1);
   const size=fs.readSync(fd,raw,0,raw.length,0);
   if(size!==actual.size||fs.fstatSync(fd).mtimeMs!==actual.mtimeMs)return 'unavailable';
   return raw.subarray(0,size);
  }finally{fs.closeSync(fd);}
 }catch{return 'unavailable';}
}
function setupObservation(root){
 const inputs={profile_sha256:PROFILE};
 for(const channel of ['core','plugins']){
  const {journal,last}=transactionPaths(channel);
  inputs[channel+'_journal_sha256']=journal;
  inputs[channel+'_last_sha256']=last;
 }
 return Object.fromEntries(Object.entries(inputs).map(([key,relative])=>{
  const raw=setupProofBytes(root,relative);
  return [key,Buffer.isBuffer(raw)?c.hash(raw):raw];
 }));
}
function writeSetupReceipt(root,relative,record,exclusive){
 const target=c.safe(root,relative);
 fs.mkdirSync(path.dirname(target),{recursive:true});
 const temporary=c.safe(root,SETUP_OPERATIONS+'/.pending-'+randomUUID());
 try{
  const fd=fs.openSync(temporary,'wx',0o600);
  try{fs.writeFileSync(fd,c.json(record));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  if(exclusive)fs.linkSync(temporary,c.safe(root,relative));
  else fs.renameSync(temporary,c.safe(root,relative));
 }finally{fs.rmSync(temporary,{force:true});}
}
function beginSetupOperation(root,setup){
 const id=setup.id??'OP-'+randomUUID();
 if(!setupOperationId.test(id))throw Error('Select an exact setup operation ID');
 const relative=SETUP_OPERATIONS+'/'+id+'.json';
 const scope={kind:setup.kind,scope:setup.scope()};
 const requestFor=layout=>c.hash(c.json(setup.kind==='install'?{...scope,workflow_layout:layout}:scope));
 const current=setupObservation(root);
 const retained=setupProofBytes(root,relative,4096);
 if(retained==='unavailable')throw Error('The selected setup operation receipt cannot be read');
 const previous=retained===null?null:JSON.parse(retained);
 let layout=setup.sharedWorkflow??previous?.workflow_layout??null;
 if(setup.kind==='install'&&setup.sharedWorkflow===undefined&&current.core_journal_sha256===null){
  try{layout=usesSharedWorkflow(receipt(root));}catch{layout=null;}
 }
 if(previous){
  if(previous.schema!==1||previous.operation_id!==id||previous.kind!==setup.kind||
     previous.request_sha256!==requestFor(previous.workflow_layout??null)||
     !['pending','failed','completed'].includes(previous.status)||
     !Number.isSafeInteger(previous.attempts)||previous.attempts<1)
   throw Error('Setup operation ID belongs to a different request');
  if(setup.kind==='install'&&previous.workflow_layout!=null&&layout!==null&&previous.workflow_layout!==layout)
   throw Error('Setup operation ID belongs to a different workflow runtime layout');
  if(previous.status==='completed'){
   if(Object.values(current).includes('unavailable')||c.json(current)!==c.json(previous.observed)||
      current.core_journal_sha256!==null||current.plugins_journal_sha256!==null)
    throw Error('The completed setup operation no longer covers the observed journal or profile');
   return {id,replayed:true,layout};
  }
  for(const channel of ['core','plugins']){
   const journal=channel+'_journal_sha256',last=channel+'_last_sha256';
   const activation=channel==='core'?previous.activation_journal_sha256:null;
   const expected=activation??previous.before?.[journal];
   const consumed=typeof expected==='string'&&expected!=='unavailable'&&current[journal]===null&&
     current[last]===expected&&previous.before[last]!==expected;
   const unpublished=activation&&current[journal]===null&&current[last]===previous.observed[last]&&
     current.profile_sha256===previous.observed.profile_sha256;
   if(expected==='unavailable'||current[journal]!==expected&&!consumed&&!unpublished)
    throw Error('Setup operation journal changed since the original attempt');
  }
 }
 const timestamp=new Date().toISOString();
 layout=previous?.workflow_layout??layout;
 const record={schema:1,operation_id:id,kind:setup.kind,request_sha256:requestFor(layout),
  status:'pending',stage:'recover',started_at:previous?.started_at??timestamp,observed_at:timestamp,
  attempts:(previous?.attempts??0)+1,before:previous?.before??current,observed:current,
  activation_journal_sha256:previous?.activation_journal_sha256??null};
 if(setup.kind==='install')record.workflow_layout=layout;
 writeSetupReceipt(root,relative,record,!previous);
 return {id,record,relative,frontier:current,requestFor};
}
function freezeSetupWorkflow(root,session,requested){
 const layout=requested??usesSharedWorkflow(receipt(root));
 if(!session)return layout;
 if(session.record.workflow_layout===null){
  session.record={...session.record,workflow_layout:layout,request_sha256:session.requestFor(layout),
   stage:'install',observed_at:new Date().toISOString(),observed:setupObservation(root)};
  writeSetupReceipt(root,session.relative,session.record,false);
 }else if(session.record.workflow_layout!==layout){
  throw Error('Setup operation ID belongs to a different workflow runtime layout');
 }
 return layout;
}
function sealSetupActivation(root,session,journalBytes){
 if(Buffer.byteLength(journalBytes)>16*1024*1024)throw Error('The installation activation journal exceeds the proof limit');
 session.record={...session.record,stage:'install',activation_journal_sha256:c.hash(journalBytes),
  observed_at:new Date().toISOString(),observed:setupObservation(root)};
 writeSetupReceipt(root,session.relative,session.record,false);
}
function finishSetupOperation(root,session,status,stage){
 if(!session)return;
 writeSetupReceipt(root,session.relative,{...session.record,status,stage,
  observed_at:new Date().toISOString(),observed:setupObservation(root)},false);
}
function locked(root,action,{recoverPending=true,recoverPluginPending=true,onPending,setup}={}){
 const owner=queueRoot(root),barrier=owner!==root?path.join(owner,INSTALL+'/.install-lock'):null;let barrierFd;
 if(barrier){fs.mkdirSync(path.dirname(barrier),{recursive:true});try{barrierFd=fs.openSync(barrier,'wx',0o600);fs.writeFileSync(barrierFd,c.json({pid:process.pid,host:require('node:os').hostname()}));}catch{throw Error('Canonical installation lock exists');}}
 const dir=c.safe(root,INSTALL);fs.mkdirSync(dir,{recursive:true});const lock=c.safe(root,INSTALL+'/.install-lock');let fd;
 try{fd=fs.openSync(lock,'wx',0o600);}catch{if(barrier){fs.closeSync(barrierFd);fs.unlinkSync(barrier);}throw Error('Installation lock exists; inspect PID/host before explicit removal');}
 try{fs.writeFileSync(fd,c.json({pid:process.pid,host:require('node:os').hostname()}));if(fs.existsSync(c.safe(owner,'.skill-tree/.writer-lock')))throw Error('Workflow writer lock exists; reach a cleanup/handoff boundary before installation');
  const session=setup?beginSetupOperation(root,setup):null;
  if(session?.replayed)return {...setup.replay(session.layout),operation_id:session.id,replayed:true};
  let stage='recover',value;
  try{
   if(session&&['core','plugins'].some(channel=>session.frontier[channel+'_journal_sha256']==='unavailable'))
    throw Error('Cannot recover a journal without its exact sealed bytes');
   const pluginPending=fs.existsSync(c.safe(root,transactionPaths('plugins').journal));
   if(pluginPending&&!recoverPluginPending)throw Error('Plugin installation recovery is required; use the owned manager --recover');
   const pending=pluginPending||fs.existsSync(c.safe(root,transactionPaths('core').journal));
   if(pending&&!recoverPending){
    if(typeof onPending==='function')return onPending();
    throw Error('Owned installation recovery is required before this operation');
   }
   if(pending&&hasActiveOperation(root))throw Error('Active controller must reach a stopped cleanup/handoff before transaction recovery');
   recover(root,'core',session?.frontier.core_journal_sha256);
   recover(root,'plugins',session?.frontier.plugins_journal_sha256);
   stage=setup?.kind==='install'?'install':'recover';
   value=action(session);
  }catch(error){
   if(session){
    error.operation_id=session.id;
    try{finishSetupOperation(root,session,'failed',stage);}catch{error.operation_receipt_pending=true;}
   }
   throw error;
  }
  if(!session)return value;
  try{finishSetupOperation(root,session,'completed','complete');}
  catch(error){error.operation_id=session.id;throw error;}
  return {...value,operation_id:session.id};
 }finally{fs.closeSync(fd);fs.unlinkSync(lock);if(barrier){fs.closeSync(barrierFd);fs.unlinkSync(barrier);}}
}
function bundle(source,flavor){
 const files={};for(const rel of Object.keys(c.sourceInputs(source))){
  if(flavor!=='director'&&rel.startsWith('domains/')&&!rel.startsWith('domains/'+flavor+'/'))continue;
  if(rel==='config/repository.json')continue;
  files['source/'+rel]=c.read(source,rel);
 }
 files['package.json']='{"type":"commonjs"}\n';
 files['manager.js']="#!/usr/bin/env node\n'use strict';\nconst path=require('node:path');\nconst manager=require('./source/lib/installation.js');\nprocess.exitCode=manager.localMain(path.resolve(__dirname,'../..'),path.join(__dirname,'source'),process.argv.slice(2));\n";
 return files;
}
function plan(root,source,flavor,selections,options={}){
 const profileBefore=treeHash(root,PROFILE);const old=receipt(root);if(old)verifyOwned(root,old);
 const workflowBefore=treeHash(root,WORKFLOW);
 if(!old&&fs.existsSync(c.safe(root,INSTALL))){
  if(hasRetainedCore(root))throw missingReceipt(root);
  const {REGISTRY,PACKAGES,NOOP_REQUESTS,verifyInstalled}=require('./plugin-registry.js');
  const {backups,last}=transactionPaths('plugins');
  // Owned plugin state survives removal of the independent core generation.
  const allowed=new Set(['.install-lock','plugin-known.json',...[REGISTRY,PACKAGES,NOOP_REQUESTS,backups,last].map(rel=>path.posix.basename(rel))]);
  if(fs.readdirSync(c.safe(root,INSTALL)).some(name=>!allowed.has(name)))throw Error('Unowned maintenance directory conflict');
  if(fs.existsSync(c.safe(root,backups))||fs.existsSync(c.safe(root,last))){
   if(!fs.existsSync(c.safe(root,REGISTRY)))throw Error('Unowned maintenance directory conflict');
   verifyInstalled(root);verifyPluginBackups(root);
  }
 }
 if(!options[INITIAL_WORKTREE_PROFILE]&&hasActiveOperation(root))throw Error('Active controller must checkpoint at a stopped cleanup/handoff point before installation or refresh');
 const requested=[...selections];
 if(old)for(const [rel,record] of Object.entries(old.destinations))requested.push({rel,provider:record.provider,providers:owners(record),name:record.name});
 const merged={};for(const item of requested){if(!merged[item.rel])merged[item.rel]={...item,providers:[]};merged[item.rel].providers=[...new Set([...merged[item.rel].providers,...(item.providers||[item.provider])])].sort();}
 const unique=Object.values(merged),names=[...new Set(unique.map(s=>s.name))];
 const previousLayout=usesSharedWorkflow(old);
 const ownedWorkflow=options.sharedRuntime??previousLayout;
 if(typeof ownedWorkflow!=='boolean')throw Error('Select an explicit supported workflow runtime layout');
 const profile=c.resolveProfile(source,root,flavor,options);
 const built=c.compose(source,profile,names,{ownedWorkflow}),changes={},destinations={...(old?.destinations||{})};
 const policyBefore=treeHash(root,development.CONFIG);
 if(Object.hasOwn(options,'developmentPolicy'))changes[development.CONFIG]=options.developmentPolicy;
 for(const item of unique){
  const current=filesAt(root,item.rel),owned=old?.destinations[item.rel];
  if(current&&!owned)throw Error('Unowned destination conflict, including --force: '+item.rel);
  const files=built.packages[item.name];if(!files)throw Error('Missing composed operation: '+item.name);
  changes[item.rel]=files;destinations[item.rel]={provider:owned?.provider||item.provider,providers:[...new Set([...(owned?owners(owned):[]),...item.providers])].sort(),name:item.name,flavor,files:built.output_digests[item.name],identity:c.hash(c.json(built.output_digests[item.name]))};
 }
 const bridges={...(old?.bridges||{})},bridgeBefore={};
 const selectedBridges=new Set(options.bridges||[]);
 const legacyOpenCode='.opencode/AGENTS.md';
 const legacyOwners=old?.bridges?.[legacyOpenCode]?.providers||[];
 const openCode=c.readJson(source,'config/providers.json').providers.find(provider=>provider.id==='opencode');
 const migrateOpenCode=legacyOwners.includes('opencode')&&openCode?.bridgePath===AGENTS_PATH;
 if(migrateOpenCode){
  selectedBridges.delete(legacyOpenCode);
  const remaining=legacyOwners.filter(owner=>owner!=='opencode');
  if(remaining.length)bridges[legacyOpenCode]={...bridges[legacyOpenCode],providers:remaining};
  else{
   const current=c.read(root,legacyOpenCode),owned=bridgeBlock(current);
   bridgeBefore[legacyOpenCode]=treeHash(root,legacyOpenCode);
   const surrounding=current.replace(owned,'');
   changes[legacyOpenCode]=current==='\n\n'+owned+'\n'?null:surrounding;
   delete bridges[legacyOpenCode];
  }
 }
 const bridgePaths=new Set([...selectedBridges,...Object.keys(bridges)]);
 if(migrateOpenCode)bridgePaths.add(AGENTS_PATH);
 for(const rel of bridgePaths){
  const current=c.read(root,rel)||'',existing=bridgeBlock(current);bridgeBefore[rel]=treeHash(root,rel);
  if(existing&&!old?.bridges[rel])throw Error('Unowned bridge conflict: '+rel);
  const block=renderBridge(source,flavor,profile);
  changes[rel]=existing?current.replace(existing,block):current+(current.endsWith('\n')?'\n':'\n\n')+block+'\n';
  const providers=new Set(bridges[rel]?.providers||[]);
  if(selectedBridges.has(rel)&&options.provider)providers.add(options.provider);
  if(migrateOpenCode&&rel===AGENTS_PATH)providers.add('opencode');
  bridges[rel]={hash:c.hash(block),providers:[...providers].sort()};
 }
 const maintenance=bundle(source,flavor),bundle_digests={};
 for(const [rel,content] of Object.entries(maintenance)){const dest=INSTALL+'/'+rel;if(fs.existsSync(c.safe(root,dest))&&!old?.bundle_digests[dest])throw Error('Unowned maintenance file conflict: '+dest);changes[dest]=content;bundle_digests[dest]=c.hash(content);}
 for(const rel of Object.keys(old?.bundle_digests||{}))if(!bundle_digests[rel])changes[rel]=null;
 let source_digests=built.source_digests;
 if(old&&source===c.safe(root,INSTALL+'/source')){
  if(Object.entries(source_digests).some(([rel,digest])=>old.source_digests[rel]!==digest))throw Error('Bundle and source recipe identities disagree');
  source_digests=old.source_digests;
 }
 const next={...profile,source_digests,destinations,bridges,bundle_digests};
 if(ownedWorkflow)next.workflow_runtime='owned-v1';
 const grouping=taskGroupingProof(next,()=>maintenance['source/'+TASK_GROUPING_SOURCE]??null);
 if(grouping)next.task_grouping=grouping;
 next.identity=compositionIdentity(next);
 requireGroupedQueueCompatibility(root,next,groupingFileReader(root,changes));
 changes[PROFILE]=c.json(next);
 if(old?.identity!==next.identity){const stopped=stoppedWorkflow(root);if(stopped)changes[WORKFLOW]=stopped;}
 const expected={};
 for(const rel of Object.keys(changes)){
  if(old?.destinations[rel])expected[rel]=c.hash(c.json(old.destinations[rel].files));
  else if(old?.bundle_digests[rel])expected[rel]=c.hash(c.json({'':old.bundle_digests[rel]}));
  else if(rel===PROFILE)expected[rel]=profileBefore;
  else if(rel===development.CONFIG)expected[rel]=policyBefore;
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
function verify(root,source,allowForeign=false,operation){
 if(fs.existsSync(c.safe(root,transactionPaths().journal)))throw Error('Core installation recovery is required before profile verification');
 if(fs.existsSync(c.safe(root,transactionPaths('plugins').journal)))throw Error('Plugin installation recovery is required before profile verification');
 const p=receipt(root,true,allowForeign);verifyOwned(root,p,true,operation);const bundleSource=c.safe(root,INSTALL+'/source');
 const now=c.resolveProfile(bundleSource,root,p.flavor);
 for(const field of ['source_version','inputs','inventory','facts','recipes','gaps','environment_id','execution_bindings','worktree_environment','plugins','development_policies'])if(c.json(now[field])!==c.json(p[field])){
  throw Object.assign(Error('Profile refresh-required or resolved profile mismatch: node .skill-tree/installation/manager.js --refresh-profile'),{code:'ST_PROFILE_REFRESH_REQUIRED'});
 }
 if(p.identity!==compositionIdentity(p))throw Error('Composition receipt identity mismatch');
 const generated=c.compose(bundleSource,now,[...new Set(Object.values(p.destinations).map(record=>record.name))],
  {ownedWorkflow:usesSharedWorkflow(p)});
 const providers=c.readJson(bundleSource,'config/providers.json').providers;
 for(const [rel,record] of Object.entries(p.destinations)){
  if(record.flavor!==p.flavor||record.identity!==c.hash(c.json(record.files))||c.json(generated.output_digests[record.name])!==c.json(record.files))throw Error('Package identity/flavor does not match deterministic composition: '+rel);
  if(owners(record).some(id=>{const provider=providers.find(p=>p.id===id);return !provider||rel!==path.posix.join(provider.id==='generic'?'':provider.projectPath,record.name);}))throw Error('Provider ownership disagrees with the scoped destination: '+rel);
 }
 for(const [rel,digest] of Object.entries(p.bundle_digests))if(rel.startsWith(INSTALL+'/source/')&&p.source_digests[rel.slice((INSTALL+'/source/').length)]!==digest)throw Error('Bundle and source recipe identities disagree');
 const grouping=verifyTaskGroupingProof(p,groupingFileReader(root));
 if(!grouping)requireGroupedQueueCompatibility(root,p);
 return p;
}
function regenerateAgents(root,source,dryRun=false){
 const target=()=>c.safe(root,AGENTS_PATH);
 const existsError=()=>Error('AGENTS.md already exists; regenerate-agents requires an absent path');
 function inspect(){
  if(fs.existsSync(target()))throw existsError();
  if(hasActiveOperation(root))throw Error('Active controller must reach a stopped cleanup/handoff before regenerating AGENTS.md');
  const p=verify(root,source,false,REGENERATE_AGENTS),record=p.bridges?.[AGENTS_PATH];
  if(!isCodexBridge(record))throw Error('No owned Codex bridge is registered for AGENTS.md');
  if(['core','plugins'].some(channel=>fs.existsSync(c.safe(root,transactionPaths(channel).stage))))
   throw Error('Retained installation staging requires explicit recovery before regenerating AGENTS.md');
  const block=renderBridge(c.safe(root,INSTALL+'/source'),p.flavor,p);
  if(c.hash(block)!==record.hash)throw Error('Installed rules no longer match the registered AGENTS.md block; restore the matching instruction file');
  return { block, hash:record.hash };
 }
 if(dryRun){
  const owner=queueRoot(root);
  if([root,owner].some(location=>fs.existsSync(c.safe(location,INSTALL+'/.install-lock')))||fs.existsSync(c.safe(owner,'.skill-tree/.writer-lock')))
   throw Error('Installation or workflow lock exists; reach a cleanup/handoff before regenerating AGENTS.md');
  const {hash}=inspect();
  return {action:'dry-run',changed:[AGENTS_PATH],bridge_sha256:hash};
 }
 receipt(root,true);
 return locked(root,()=>{
  const before=treeHash(root,PROFILE),{block,hash}=inspect();
  const staging=fs.mkdtempSync(c.safe(root,'.skill-tree-agents-recovery-'));
  try{
   const staged=path.join(staging,AGENTS_PATH);
   const content=Buffer.from(block+'\n','utf8');
   const fd=fs.openSync(staged,'wx+');
   try{
    fs.writeFileSync(fd,content);
    if(inspect().hash!==hash||treeHash(root,PROFILE)!==before)throw Error('Ownership receipt changed during AGENTS.md staging');
    const original=fs.fstatSync(fd),actual=Buffer.alloc(content.length);
    if(original.size!==content.length||fs.readSync(fd,actual,0,actual.length,0)!==actual.length||!actual.equals(content))
     throw Error('Staged AGENTS.md bytes changed before publication');
    const current=fs.lstatSync(staged);
    if(!current.isFile()||current.nlink!==1||current.dev!==original.dev||current.ino!==original.ino)
     throw Error('Staged AGENTS.md file identity changed before publication');
    // A link publishes verified bytes only while the destination is absent.
    try{fs.linkSync(staged,target());}catch(error){if(error.code==='EEXIST')throw existsError();throw error;}
   }finally{fs.closeSync(fd);}
  }finally{fs.rmSync(staging,{recursive:true,force:true});}
  verify(root,source);
  return {action:'regenerated',changed:[AGENTS_PATH],bridge_sha256:hash};
 },{recoverPending:false,recoverPluginPending:false});
}
function install(root,source,flavor,selections,options={}){
 if(options.dryRun){const result=plan(root,source,flavor,selections,options);return {profile:result.profile,delta:result.delta,action:'dry-run'};}
 const setup={
  kind:'install',id:options.operationId,sharedWorkflow:options.sharedRuntime,
  scope:()=>({source:c.sourceInputs(source),flavor,selections,bridges:options.bridges??[],
   shared_workflow:options.sharedRuntime??'preserve-installed-layout',
   development_policy:options.developmentPolicy??null,recover_pending:options.recoverPending!==false,
   recover_plugins:options.recoverPluginPending!==false}),
  replay:sharedRuntime=>{
   if(options.guardPlan||options.updateDevelopmentPolicy)throw Error('Guarded installation replay requires a fresh operation');
   const candidate=plan(root,source,flavor,selections,{...options,sharedRuntime});
   if(candidate.delta.length)throw Error('The previously verified setup generation changed');
   return {profile:verify(root,source),delta:[],action:'verified no-op current'};
  }
 };
 return locked(root,(session)=>{
  const sharedRuntime=freezeSetupWorkflow(root,session,options.sharedRuntime);
  const planned={...options,sharedRuntime};
  if(options.updateDevelopmentPolicy)planned.developmentPolicy=options.updateDevelopmentPolicy();
  const result=plan(root,source,flavor,selections,planned);
  options.guardPlan?.(result);
  transaction(root,result.changes,result.expected,()=>{
   const current=c.resolveProfile(source,root,flavor,planned);
   if(current.environment_id!==result.profile.environment_id)throw Error('Project inputs changed during profile staging; refresh from current inputs');
   options.guardPlan?.(result);
  },'core',session?(journalBytes)=>sealSetupActivation(root,session,journalBytes):undefined);
  try{verify(root,source);}catch(error){
   if(result.delta.length){try{restoreGeneration(root);}catch(recovery){throw Error('Profile verification failed; preserved generation backups require conflict review: '+error.message+'; '+recovery.message);}}
   throw error;
  }
  return {profile:result.profile,delta:result.delta,action:result.delta.length?'installed':'verified no-op current'};
 },{recoverPending:options.recoverPending,recoverPluginPending:options.recoverPluginPending,
    setup:Object.hasOwn(options,INITIAL_WORKTREE_PROFILE)?undefined:setup});
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
  delete next.task_grouping;
  const grouping=taskGroupingProof(next,()=>groupingFileReader(root)(TASK_GROUPING_BUNDLE));
  if(grouping)next.task_grouping=grouping;
  requireGroupedQueueCompatibility(root,next,groupingFileReader(root,changes));
  next.identity=compositionIdentity(next);const stopped=stoppedWorkflow(root);if(stopped){changes[WORKFLOW]=stopped;expected[WORKFLOW]=treeHash(root,WORKFLOW);}
  changes[PROFILE]=c.json(next);expected[PROFILE]=treeHash(root,PROFILE);if(!options.dryRun)transaction(root,changes,expected);return {action:options.dryRun?'dry-run uninstall':'removed',profile:next,delta:Object.keys(changes)};
 }
 return options.dryRun?action():locked(root,action,{recoverPluginPending:options.recoverPluginPending});
}
function refresh(root,source,dryRun=false){const p=receipt(root,true);return install(root,source,p.flavor,Object.entries(p.destinations).map(([rel,d])=>({rel,provider:d.provider,name:d.name})),{dryRun,bridges:Object.keys(p.bridges||{}),recoverPluginPending:false});}

function initialWorktreeProfile(root, request, mode) {
 if (!['install','verify','replay'].includes(mode) || typeof request.worktree !== 'string' || !path.isAbsolute(request.worktree)) {
  throw Error('Select the exact run worktree profile action');
 }
 const target = fs.realpathSync(request.worktree);
 const source = c.safe(root,INSTALL+'/source');
 const {execFileSync} = require('node:child_process');
 const git = (checkout,...args) => execFileSync('git',
  ['--no-replace-objects','--no-optional-locks','-C',checkout,'-c','core.fsmonitor=false',...args],
  {encoding:'utf8',stdio:['ignore','pipe','ignore'],timeout:5000}).trim();
 const same = (left,right) => c.json(left) === c.json(right);
 function verifyReservation() {
  const state = c.read(root,WORKFLOW);
  if (state === null || c.hash(state) !== request.state_sha256 || target !== request.worktree || target === root) {
   throw Error('The original profile handoff or exact checkout changed');
  }
  const registry = JSON.parse(state).run_registry;
  const run = registry?.runs?.[request.run_id];
  const hold = run?.initial_profile;
  const expectedStatus = mode === 'replay' ? 'admitted' : 'pending';
  if (registry?.queue_id !== request.queue_id || run?.workspace_state !== 'ready' || hold?.status !== expectedStatus ||
      (mode !== 'replay' && (run.phase !== 'refresh-profile' || run.stop_reason !== 'Initial worktree profile requires verified admission')) ||
      hold.worktree_path_sha256 !== c.hash(target) ||
      !same(Object.keys(registry.claims).filter(id=>registry.claims[id]===run.id).sort(),hold.claimed_task_ids)) {
   throw Error('The reserved run, initial profile hold or original claims changed');
  }
  const common = path.resolve(root,git(root,'rev-parse','--git-common-dir'));
  const locator = fs.readFileSync(path.join(common,'skill-tree-runtime.json'));
  const local = JSON.parse(locator);
  const registration = git(target,'rev-parse','--absolute-git-dir');
  if (c.hash(locator) !== request.locator_sha256 || local.queue_id !== request.queue_id ||
      local.canonical_root !== root || local.worktrees?.[run.id] !== target ||
      git(target,'rev-parse','--show-toplevel') !== target ||
      registration !== path.join(common,'worktrees',request.registration) ||
      git(target,'symbolic-ref','--short','HEAD') !== run.workspace.branch ||
      git(target,'rev-parse','--verify','HEAD') !== run.workspace.base_commit ||
      !same(run.workspace.cleanup_owner??null,request.owner)) {
   throw Error('The checkout or Git registration no longer matches the exact recorded worktree');
  }
  if (request.owner) {
   const owner = c.readJson(registration,'skill-tree-owner.json');
   if (!same(owner,request.owner)) throw Error('Restore the original worktree ownership record');
  }
  const profile = c.read(root,PROFILE);
  if (profile === null || c.hash(profile) !== hold.source_profile_sha256 || c.hash(profile) !== request.source_profile_sha256) {
   throw Error('Restore the original verified canonical profile before worktree setup');
  }
  const verified = verify(root,source);
  if (mode !== 'replay' && (verified.identity !== run.admission.identity || verified.flavor !== run.admission.flavor)) {
   throw Error('The canonical installation differs from the original run admission');
  }
  return verified;
 }
 const original = verifyReservation();
 function isolatedDestination() {
  const common = path.resolve(root,git(root,'rev-parse','--git-common-dir'));
  const locator = c.readJson(common,'skill-tree-runtime.json');
  const native = git(root,'worktree','list','--porcelain','-z').split('\0')
   .filter(field=>field.startsWith('worktree ')).map(field=>field.slice('worktree '.length));
  const peers = native.filter(checkout=>checkout!==root&&checkout!==target);
  for (const locations of [locator.worktrees,locator.pending_worktrees||{}]) {
   peers.push(...Object.entries(locations).filter(([id])=>id!==request.run_id).map(([,checkout])=>checkout));
  }
  function contains(parent, child) {
   // Fold path spellings conservatively because a worktree may use a
   // case-insensitive filesystem even when the checkout paths are distinct strings.
   const comparable = value => value.normalize('NFD').toLowerCase();
   const relative = path.relative(comparable(parent),comparable(child));
   return relative!=='..'&&!relative.startsWith('..'+path.sep)&&!path.isAbsolute(relative);
  }
  const ownedArea = path.join(common,'skill-tree-worktrees');
  if (!native.includes(target) || contains(target,root)) return false;
  if (contains(common,target)) {
   if (!contains(ownedArea,target)||contains(target,ownedArea))return false;
  } else if (contains(root,target)) {
   return false;
  }
  return peers.every(checkout=>{
   if(typeof checkout!=='string'||!path.isAbsolute(checkout))return false;
   const actual = fs.existsSync(checkout)?fs.realpathSync(checkout):checkout;
   return !contains(actual,target)&&!contains(target,actual);
  });
 }
 const scope = profile => Object.fromEntries(Object.entries(profile.destinations)
  .map(([relative,row])=>[relative,{name:row.name,providers:[...owners(row)].sort()}]));
 const expected = scope(original);
 const validate = candidate => {
  if (candidate.flavor !== original.flavor || !same(candidate.bundle_digests,original.bundle_digests) ||
      !same(scope(candidate),expected) || usesSharedWorkflow(candidate)!==usesSharedWorkflow(original))
   throw Error('Worktree profile requires the original owned flavor, source generation, runtime layout and provider destinations');
  if (!same(candidate.plugins,original.plugins)) {
   throw Error('Restore the original configured plugin generation in the exact worktree through the owned plugin setup path');
  }
 };
 if (mode === 'install' && c.read(target,PROFILE) === null) {
  const selections = Object.entries(expected).flatMap(([rel,row])=>row.providers.map(provider=>({rel,provider,name:row.name})));
  const isolated = isolatedDestination();
  install(target,source,original.flavor,selections,{[INITIAL_WORKTREE_PROFILE]:isolated,recoverPending:false,
   recoverPluginPending:false,sharedRuntime:usesSharedWorkflow(original),
   guardPlan(planned){
    verifyReservation();
    if (isolated && !isolatedDestination()) throw Error('The reserved profile destination now overlaps another checkout');
    validate(planned.profile);
    if (Object.keys(planned.changes).some(relative=>!relative.startsWith(INSTALL+'/') && !Object.hasOwn(expected,relative))) {
     throw Error('Initial profile setup cannot change product files, bridges or workflow metadata');
    }
   }});
 }
 const candidate = verify(target,source);
 validate(candidate);
 const response = {profile_sha256:c.hash(c.read(target,PROFILE)),
  admission:{identity:candidate.identity,environment_id:candidate.environment_id,flavor:candidate.flavor}};
 verifyReservation();
 return response;
}

function packageMetadataAtDelivery(root, request){
 const {execFileSync}=require('node:child_process');
 function git(...args){
  return execFileSync('git',['--no-replace-objects','--no-optional-locks','--literal-pathspecs',
   '-C',root,'-c','core.fsmonitor=false',...args],{
   encoding:'buffer',stdio:['ignore','pipe','ignore'],timeout:5000,
   env:{...process.env,GIT_NO_LAZY_FETCH:'1'}
  });
 }
 const {target_ref:ref,target_head:head,previous_local_head:previous}=request;
 const commit=/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
 if(!commit.test(head)||!commit.test(previous)||head===previous||
    git('symbolic-ref','--quiet','--no-recurse','HEAD').toString().trim()!==ref||
    git('rev-parse','--verify','HEAD').toString().trim()!==head)
  throw Error('Profile maintenance requires the exact synchronized target and original local commit');
 git('merge-base','--is-ancestor',previous,head);
 const entry=revision=>git('ls-tree',revision,'--','package.json').toString().trim();
 const newEntry=entry(head),oldEntry=entry(previous),staged=git('ls-files','--stage','--','package.json').toString().trim();
 const fileEntry=/^(100(?:644|755)) blob ([0-9a-f]{40}|[0-9a-f]{64})\tpackage\.json$/;
 const current=fileEntry.exec(newEntry),before=fileEntry.exec(oldEntry);
 if(!current||!before||current[1]!==before[1]||staged!==current[1]+' '+current[2]+' 0\tpackage.json')
  throw Error('Compatibility requires a regular, unstaged package.json with the original mode');
 const original=git('cat-file','blob',before[2]),synchronized=git('cat-file','blob',current[2]);
 const packagePath=c.safe(root,'package.json');
 const fd=fs.openSync(packagePath,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW|fs.constants.O_NONBLOCK);
 try{
  const stat=fs.fstatSync(fd);
  if(!stat.isFile()||Boolean(stat.mode&0o100)!==(current[1]==='100755')||!fs.readFileSync(fd).equals(synchronized))
   throw Error('Compatibility requires the exact committed package.json bytes and mode');
 }finally{fs.closeSync(fd);}
 const decode=value=>JSON.parse(value.toString('utf8').replace(/^\uFEFF/,''));
 const oldPackage=decode(original),newPackage=decode(synchronized);
 if(!oldPackage||typeof oldPackage!=='object'||Array.isArray(oldPackage)||
    !newPackage||typeof newPackage!=='object'||Array.isArray(newPackage))
  throw Error('Compatibility requires complete package metadata objects');
 const metadata=new Set(['description','keywords']);
 const fields=[...new Set([...Object.keys(oldPackage),...Object.keys(newPackage)])]
  .sort().filter(key=>c.json(oldPackage[key])!==c.json(newPackage[key]));
 if(!fields.length||fields.some(field=>!metadata.has(field)))
  throw Error('The package change includes material or unexplained inputs');
 return {before:c.hash(original),after:c.hash(synchronized),fields};
}

function requireUnaffectedProfileRuns(root){
 const state=workflowState(root);
 const runs=state?.run_registry ? Object.values(state.run_registry.runs) : [state?.active_run];
 if(runs.some(unfinishedRun)||hasActiveOperation(root))
  throw Error('Unfinished canonical work requires the explicit profile recovery path');
}

function deliveryProfilePlan(root, request, result){
 const input=packageMetadataAtDelivery(root,request);
 const {old,profile:after}=result;
 const oldSha=c.hash(fs.readFileSync(c.safe(root,PROFILE)));
 if(oldSha!==request.profile_sha256||old.inputs['package.json']!==input.before||
    after.inputs['package.json']!==input.after)
  throw Error('The owned profile inputs differ from the exact original and synchronized Git bytes');
 const inputs={...after.inputs,'package.json':input.before};
 if(c.json(inputs)!==c.json(old.inputs))
  throw Error('Discovered profile inputs include material or unknown changes');
 const comparison=profile=>{
  const {inputs,environment_id,identity,destinations,...stable}=profile;
  const owners=Object.fromEntries(Object.entries(destinations).map(([relative,record])=>{
   const {files,identity,...ownership}=record;
   return [relative,ownership];
  }));
  return {...stable,destinations:owners};
 };
 if(c.json(comparison(old))!==c.json(comparison(after)))
  throw Error('Resolved profile facts, policy, source, bindings, or recipes changed');
 const identity=(profile,profile_sha256)=>({profile_sha256,identity:profile.identity,environment_id:profile.environment_id});
 return {before:identity(old,oldSha),after:identity(after,c.hash(result.changes[PROFILE])),
  input:'package.json',changed_fields:input.fields};
}

function maintainDeliveredProfile(root,request){
 const source=c.safe(root,INSTALL+'/source');
 const options={recoverPending:false,recoverPluginPending:false};
 if(request.phase==='verify'){
  return locked(root,()=>{
   packageMetadataAtDelivery(root,request);
   const profile=verify(root,source);
   const actual={profile_sha256:c.hash(fs.readFileSync(c.safe(root,PROFILE))),identity:profile.identity,environment_id:profile.environment_id};
   if(c.json(actual)!==c.json(request.plan?.after))throw Error('The installed profile differs from the anticipated generation');
   return {status:'current',profile:actual};
  },options);
 }
 const p=receipt(root,true);
 const selected=Object.entries(p.destinations).map(([rel,d])=>({rel,provider:d.provider,name:d.name}));
 const installedOptions={...options,bridges:Object.keys(p.bridges||{})};
 const guard=result=>{
  requireUnaffectedProfileRuns(root);
  return deliveryProfilePlan(root,request,result);
 };
 if(request.phase==='prepare'){
  return locked(root,()=>{
   requireUnaffectedProfileRuns(root);
   return {status:'prepared',plan:guard(plan(root,source,p.flavor,selected,installedOptions))};
  },options);
 }
 if(request.phase!=='activate'||!request.plan)throw Error('Profile maintenance requires an exact prepared generation');
 const installed=install(root,source,p.flavor,selected,{
  ...installedOptions,
  guardPlan:result=>{
   if(c.json(guard(result))!==c.json(request.plan))throw Error('Prepared profile changed before activation');
  }
 });
 if(installed.action!=='installed')throw Error('The planned profile generation did not activate');
 return {status:'installed'};
}
function updateDevelopmentPolicy(root,source,update) {
 const p=receipt(root,true);
 const selections=Object.entries(p.destinations).map(([rel,d])=>({rel,provider:d.provider,name:d.name}));
 return install(root,source,p.flavor,selections,{recoverPluginPending:false,updateDevelopmentPolicy:()=>{
  if(verify(root,source).identity!==p.identity)throw Error('Development policy changed during preparation; retry against current state');
  const raw=c.read(root,development.CONFIG);
  const config=development.configuration(raw);
  const next=update(config);
  return c.json(config)===c.json(next)?raw:development.encode(next);
 }});
}
function restoreGeneration(root){
 const p=receipt(root,true);verifyOwned(root,p);if(hasActiveOperation(root))throw Error('Stop the active controller before rollback');
 const last=c.readJson(root,INSTALL+'/.last-transaction.json',null);if(!last)throw Error('No retained generation for rollback');
 const changes={},expected={};
 for(const e of last.entries){
  if(e.dest===WORKFLOW)continue;
  const current=treeHash(root,e.dest),full=e.old===null?null:c.safe(root,e.backup);
  if(full&&treeHash(root,e.backup)!==e.old)throw Error('Rollback backup is unavailable: '+e.dest);
  const previous=e.dest===PROFILE&&full?JSON.parse(fs.readFileSync(full)):null;
  if(current!==e.next){
   const project_root=last.project_root||previous?.project_root;
   if(e.dest!==PROFILE||!project_root||c.hash(c.json({'':c.hash(c.json({...p,project_root}))}))!==e.next)throw Error('Rollback conflicts with current content: '+e.dest);
  }
  expected[e.dest]=current;
  if(!full){changes[e.dest]=null;continue;}
  if(fs.lstatSync(full).isFile()){
   if(previous&&previous.project_root!==p.project_root){
    const rebound=c.json({...previous,project_root:p.project_root});
    if(rebound===c.json(p))throw Error('No retained rollback generation for the rebound project root');
    changes[e.dest]=rebound;
   }else changes[e.dest]=fs.readFileSync(full);
  }
  else changes[e.dest]=Object.fromEntries(Object.keys(filesAt(root,e.backup)).map(rel=>[rel,fs.readFileSync(c.safe(root,e.backup+'/'+rel))]));
 }
 const nextProfile=Object.hasOwn(changes,PROFILE)?changes[PROFILE]:c.json(p);
 requireGroupedQueueCompatibility(root,nextProfile===null?null:JSON.parse(nextProfile),groupingFileReader(root,changes));
 const stopped=stoppedWorkflow(root);if(stopped){changes[WORKFLOW]=stopped;expected[WORKFLOW]=treeHash(root,WORKFLOW);}
 transaction(root,changes,expected);return {action:'generation rolled back; project dependencies unchanged; verify freshness before admission'};
}
function rollback(root,{guard}={}){return locked(root,()=>{guard?.();return restoreGeneration(root);},{recoverPending:false,recoverPluginPending:false});}
function rebind(root,source){
 verify(root,source,true);
 return locked(root,()=>{
  if(['core','plugins'].some(channel=>fs.existsSync(c.safe(root,transactionPaths(channel).stage))))throw Error('Recover the original installation transaction before explicit rebind');
  const p=verify(root,source,true),project_root=fs.realpathSync(root);
  if(p.project_root===project_root)return {action:'verified no-op current'};
  if(hasActiveOperation(root))throw Error('Active controller must reach a stopped handoff before rebind');
  // A move changes only the receipt. Keep the retained package generation for rollback.
  const before=treeHash(root,PROFILE),staging=fs.mkdtempSync(c.safe(root,INSTALL+'/.rebind-'));
  try{
   const staged=path.join(staging,'profile.json');
   fs.writeFileSync(staged,c.json({...p,project_root}));
   verify(root,source,true);
   if(treeHash(root,PROFILE)!==before)throw Error('Ownership receipt changed during rebind');
   fs.renameSync(staged,c.safe(root,PROFILE));
  }finally{fs.rmSync(staging,{recursive:true,force:true});}
  verify(root,source);return {action:'verified installation rebound; recover the queue locator explicitly when required'};
 },{recoverPending:false});
}
function localMain(root,source,args){
 try{
  if(['lock-api','unlock-api'].includes(args[0])){console.log(c.json(require('./api-contract-locks.js').runCommand(root,source,args[0],args.slice(1))));return 0;}
  if(args.includes('--list-plugins'))return require('./plugins.js').listMain(root,args,{source});
  const ids=args.filter(arg=>arg.startsWith('--operation-id='));
  if(ids.length){
   if(ids.length!==1||!args.includes('--recover')||!setupOperationId.test(ids[0].slice('--operation-id='.length)))
    throw Error('Select one exact --operation-id=OP-… for --recover');
   args=args.filter(arg=>!arg.startsWith('--operation-id='));
  }
  if(args.some(a=>!['--refresh-profile','--regenerate-agents','--dry-run','--verify','--recover','--rollback','--rebind'].includes(a)))throw Error('Usage: manager.js --refresh-profile [--dry-run] | --regenerate-agents [--dry-run] | --verify | --recover [--operation-id=OP-…] | --rollback | --rebind | lock-api <target> [--file <path>] [--baseline <ref>] | unlock-api <target|--all>');
  const operations=args.filter(a=>a!=='--dry-run');
  if(operations.length!==1||args.filter(a=>a==='--dry-run').length>1||args.includes('--dry-run')&&!['--refresh-profile','--regenerate-agents'].includes(operations[0]))throw Error('Select exactly one manager operation; --dry-run applies only to --refresh-profile or --regenerate-agents');
  if(args.includes('--regenerate-agents')){console.log(c.json(regenerateAgents(root,source,args.includes('--dry-run'))));return 0;}
  if(args.includes('--rebind')){console.log(c.json(rebind(root,source)));return 0;}
  if(args.includes('--rollback')){console.log(c.json(rollback(root)));return 0;}
  if(args.includes('--recover')){
   const result=locked(root,()=>({}),{setup:{kind:'recover',id:ids[0]?.slice('--operation-id='.length),
    scope:()=>({channels:['core','plugins']}),replay:()=>({})}});
   console.log('Installation recovery complete ('+result.operation_id+')');return 0;
  }
  if(args.includes('--verify')){verify(root,source);console.log('Owned installation verified');return 0;}
  if(!args.includes('--refresh-profile'))throw Error('Use --refresh-profile or --verify');
  const result=refresh(root,source,args.includes('--dry-run'));console.log(c.json({action:result.action,changed:result.delta,facts:result.profile.facts,gaps:result.profile.gaps,operation_id:result.operation_id}));return 0;
 }catch(error){console.error(error.message);if(error.operation_id)console.error('Setup operation '+error.operation_id);return 2;}
}
module.exports={INSTALL,PROFILE,filesAt,treeHash,receipt,verifyOwned,bridgeBlock,transactionPaths,recover,transaction,locked,queueRoot,workflowState,hasActiveOperation,readHookRecords,pendingHookOperation,stoppedWorkflow,plan,install,initialWorktreeProfile,verify,verifyTaskGroupingProfile,uninstall,refresh,maintainDeliveredProfile,rollback,rebind,localMain,updateDevelopmentPolicy};
