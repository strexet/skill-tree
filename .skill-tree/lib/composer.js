'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function stable(value) {
 if(Array.isArray(value)) return value.map(stable);
 if(value && typeof value==='object') return Object.fromEntries(Object.keys(value).sort().map(k=>[k,stable(value[k])]));
 return value;
}
const json=value=>JSON.stringify(stable(value),null,2)+'\n';
function safe(root,rel) {
 if(typeof rel!=='string'||path.isAbsolute(rel)||rel.split(/[\\/]/).includes('..'))throw Error('Expected repository-relative path: '+rel);
 const full=path.resolve(root,rel),base=fs.realpathSync(root);
 let current=full;
 while(!fs.existsSync(current)&&current!==path.dirname(current))current=path.dirname(current);
 if(fs.existsSync(current)){const real=fs.realpathSync(current);if(real!==base&&!real.startsWith(base+path.sep))throw Error('Path escapes root: '+rel);}
 if(fs.existsSync(full)&&fs.lstatSync(full).isSymbolicLink())throw Error('Symlink input is unsupported: '+rel);
 return full;
}
function read(root,rel) { const p=safe(root,rel);return fs.existsSync(p)?fs.readFileSync(p,'utf8'):null; }
const readJson=(root,rel,fallback={})=>{const data=read(root,rel);return data===null?fallback:JSON.parse(data);};
function inventory(root,rules) {
 const out=[];
 function walk(rel) {
  const full=safe(root,rel);if(!fs.existsSync(full))return;
  for(const e of fs.readdirSync(full,{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){
   if(['node_modules','.git','Library','Temp','artifacts','installation'].includes(e.name))continue;
   const child=path.posix.join(rel,e.name);
   if(e.isSymbolicLink())throw Error('Symlink in capability inventory: '+child);
   if(e.isDirectory())walk(child);
   else if(rules.extensions.includes(path.extname(e.name))||rules.names.includes(e.name))out.push(child);
  }
 }
 for(const rel of rules.roots)walk(rel);
 for(const name of rules.names)if(fs.existsSync(safe(root,name)))out.push(name);
 return [...new Set(out)].sort();
}
function resolveProfile(source,root,flavor) {
 root=fs.realpathSync(root);
 const registry=readJson(source,'config/flavors.json'),rules=readJson(source,'config/capabilities.json');
 if(!registry.flavors[flavor])throw Error('Unknown flavor: '+flavor);
 const fixed=['package.json','package-lock.json','npm-shrinkwrap.json','yarn.lock','pnpm-lock.yaml','bun.lock','bun.lockb','.nvmrc','.node-version','pyproject.toml','pytest.ini','Cargo.toml','ProjectSettings/ProjectVersion.txt','Packages/manifest.json','Packages/packages-lock.json','.skill-tree/validation-recipes.json'];
 const discovered=inventory(root,rules.inventory),inputs={};
 for(const rel of [...new Set([...fixed,...discovered])].sort()){const value=read(root,rel);inputs[rel]=value===null?null:hash(value);}
 const facts={test_assemblies:[],ui:[]},recipes={},gaps=[];
 const pkg=readJson(root,'package.json'),locks=['package-lock.json','npm-shrinkwrap.json','yarn.lock','pnpm-lock.yaml','bun.lock','bun.lockb'].filter(rel=>inputs[rel]!==null);
 if(locks.length>1)throw Error('Conflicting dependency locks: '+locks.join(', '));
 const manager=pkg.packageManager?.split('@')[0]||(locks[0]?.startsWith('pnpm')?'pnpm':locks[0]?.startsWith('yarn')?'yarn':'npm');
 if(!['npm','pnpm','yarn','bun'].includes(manager))throw Error('Unsupported package manager: '+manager);
 facts.package_manager=manager;facts.node=read(root,'.nvmrc')?.trim()||read(root,'.node-version')?.trim()||pkg.engines?.node||null;
 const lock=locks.some(l=>['package-lock.json','npm-shrinkwrap.json'].includes(l))?readJson(root,locks[0]):null;
 if(lock&&!rules.web.lock_versions.includes(lock.lockfileVersion))throw Error('Unsupported dependency lock format');
 const dependencies={...pkg.dependencies,...pkg.devDependencies};facts.packages={};
 for(const [name,declared] of Object.entries(dependencies).sort()) {
  const exact=lock?.packages?.['node_modules/'+name]?.version||(/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(declared)?declared:null);
  facts.packages[name]={state:exact?'known':'ambiguous',version:exact,declaration:declared};
 }
 for(const [name,command] of Object.entries(pkg.scripts||{}).sort()){
  if(!/^(test(?::[\w-]+)?|lint|typecheck|check|build)$/.test(name))continue;
  if(/echo\s+["']?Error: no test specified/.test(command))continue;
  const lane=/browser|e2e/.test(name)?'browser':name==='build'?'build':/lint|typecheck|check/.test(name)?'static':'unit';
  recipes['script-'+name.replace(/:/g,'-')]={lane,argv:[manager,'run',name],declared_command:command,input_paths:['package.json',...locks,...discovered.filter(p=>/config|policy/.test(p))],qualification:'static-recipe; runner unqualified'};
 }
 if(flavor==='unity'){
  const version=read(root,'ProjectSettings/ProjectVersion.txt')?.match(/m_EditorVersion:\s*(\S+)/)?.[1];
  if(!version)throw Error('Unity root requires ProjectSettings/ProjectVersion.txt');
  if(!rules.unity.editor_patterns.some(p=>new RegExp(p).test(version)))throw Error('Unsupported Unity version: '+version);
  facts.editor=version;
  const manifest=readJson(root,'Packages/manifest.json').dependencies||{},locked=readJson(root,'Packages/packages-lock.json').dependencies||{};
  facts.packages={};
  for(const [name,declared] of Object.entries(manifest).sort()){
   const version=locked[name]?.version||(/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(declared)?declared:null);
   if(locked[name]&&/^\d+\.\d+\.\d+$/.test(declared)&&declared!==version)throw Error('Conflicting Unity package version: '+name);
   facts.packages[name]={state:version?'known':'ambiguous',version,declaration:declared};
  }
  const utf=facts.packages['com.unity.test-framework'];
  if(utf&&(!utf.version||!rules.unity.utf_patterns.some(p=>new RegExp(p).test(utf.version))))throw Error('Unsupported or ambiguous UTF version; update the bundled compatibility rules');
  for(const rel of discovered.filter(p=>p.endsWith('.asmdef'))){const asm=readJson(root,rel);if(asm.optionalUnityReferences?.includes('TestAssemblies')||asm.references?.some(r=>/TestRunner/.test(r)))facts.test_assemblies.push(rel);}
  if(facts.packages['com.unity.ugui'])facts.ui.push('ugui');
  if(discovered.some(p=>/\.(uxml|uss)$/.test(p)))facts.ui.push('uitk');
  if(utf)for(const lane of ['EditMode','PlayMode'])recipes['unity-'+lane.toLowerCase()]={lane:'unity-'+lane.toLowerCase(),argv:['Unity','-batchmode','-projectPath','{project_root}','-runTests','-testPlatform',lane,'-testFilter','{test_filter}','-testResults','{result_path}','-logFile','{log_path}'],editor_version:version,utf_version:utf.version,input_paths:['ProjectSettings/ProjectVersion.txt','Packages/manifest.json','Packages/packages-lock.json',...discovered],qualification:'static-recipe; authorized matching Editor and isolated fixture required'};
  if(!utf)gaps.push({key:'test-foundation',reason:'The project lacks the foundational Unity Test Framework.',recommendation:'Research the pinned Editor, configure compatible UTF and a meaningful EditMode smoke test, document focused commands and refresh the profile.'});
  else if(!facts.test_assemblies.length)gaps.push({key:'test-foundation',reason:'UTF exists without a discovered test assembly.',recommendation:'Configure the existing UTF framework and one meaningful EditMode test assembly; preserve package pins.'});
 } else if(!Object.values(recipes).some(r=>r.lane==='unit'))gaps.push({key:'test-foundation',reason:'No usable foundational test command is declared.',recommendation:'Research existing tools, select or configure a compatible foundational test framework, add one meaningful smoke test, document focused commands and refresh the profile.'});
 const explicit=readJson(root,'.skill-tree/validation-recipes.json',null);
 if(explicit){if(explicit.schema!==1||!explicit.recipes)throw Error('Unsupported static validation recipe format');for(const [id,recipe] of Object.entries(explicit.recipes)){
  if(!/^[a-z][a-z0-9-]*$/.test(id)||!Array.isArray(recipe.argv)||!recipe.argv.length||recipe.argv.some(v=>typeof v!=='string')||!recipe.lane)throw Error('Invalid static recipe: '+id);
  if(recipes[id])throw Error('Recipe collision: '+id);
  recipes[id]={...recipe,input_paths:['.skill-tree/validation-recipes.json',...(recipe.input_paths||[])],qualification:'owner-declared static recipe; runner unqualified'};
  for(const rel of recipe.input_paths||[]){const value=read(root,rel);inputs[rel]=value===null?null:hash(value);}
 }
 if(Object.values(recipes).some(r=>['unit','unity-editmode'].includes(r.lane)))gaps.splice(0,gaps.length,...gaps.filter(g=>g.key!=='test-foundation'));}
 const environment_id=hash(json({flavor,inputs,facts,recipes}));
 return {format:'skill-tree-profile',schema:1,composer_version:registry.composer_version,flavor,project_root:root,inputs,inventory:discovered,facts,recipes,gaps,environment_id,qualification:'static compatibility only; product execution unqualified'};
}
function mergeSections(common,additions,replaceable=[]) {
 const result=common.map(s=>({...s}));
 for(const section of additions){const index=result.findIndex(s=>s.id===section.id);if(index<0)result.push({...section});else{
  if(result[index].locked||!replaceable.includes(section.id))throw Error('Non-replaceable section: '+section.id);
  result[index]={...section};
 }}return result;
}
function mergeResources(common,additions,replacements={}) {
 const result={...common};for(const [dest,content] of Object.entries(additions)){
  if(dest in result&&result[dest]!==content){const rule=replacements[dest];if(!rule||rule.from!==hash(result[dest])||rule.to!==hash(content))throw Error('Resource conflict: '+dest);}
  result[dest]=content;
 }return result;
}
function sourceInputs(source) {
 const result={};
 for(const dir of ['common','domains','templates','config','lib','src']) {
  function walk(rel){for(const e of fs.readdirSync(safe(source,rel),{withFileTypes:true}).sort((a,b)=>a.name.localeCompare(b.name))){if(e.name==='__pycache__')continue;const p=path.posix.join(rel,e.name);if(e.isDirectory())walk(p);else result[p]=hash(read(source,p));}}
  walk(dir);
 }return result;
}
function compose(source,profile,selected=null) {
 const registry=readJson(source,'config/flavors.json'),recipe=registry.flavors[profile.flavor];if(!recipe)throw Error('Unknown flavor');
 const operations=readJson(source,'templates/operations.json'),mapping=readJson(source,'config/resource-map.json'),mandatory=readJson(source,'templates/invariants.json'),domain=readJson(source,recipe.sections),packages={};
 const names=selected||Object.keys(operations).sort();
 for(const name of names){const op=operations[name];if(!op)throw Error('Unknown operation: '+name);
  const sections=mergeSections(mergeSections(mandatory,op.sections),domain,recipe.replaceable_slots||[]);
  let files={};for(const [group,resources] of Object.entries(mapping[name]))for(const [dest,src] of Object.entries(resources))files[group+'/'+dest]=read(source,src);
  const domainFiles={};for(const [dest,src] of Object.entries(recipe.resources))domainFiles[dest]=read(source,src);
  files=mergeResources(files,domainFiles,recipe.replacements||{});
  files['references/project-profile.md']='# Concrete Project Profile\n\nFlavor: '+profile.flavor+'. Static compatibility only; execution remains unqualified.\n\n```json\n'+json({environment_id:profile.environment_id,facts:profile.facts,recipes:profile.recipes,gaps:profile.gaps})+'```\n';
  files['SKILL.md']='---\nname: '+name+'\ndescription: '+JSON.stringify('['+profile.flavor+'] '+op.description)+'\nlicense: MIT\n---\n\n# '+op.title+'\n\nFlavor: '+profile.flavor+'. Read the [concrete project profile](references/project-profile.md).\n\n'+sections.map(s=>s.text).join('\n\n')+'\n';
  files['agents/openai.yaml']='interface:\n  display_name: '+JSON.stringify(op.title+' ('+profile.flavor+')')+'\n  short_description: '+JSON.stringify(profile.flavor+' Skill Tree workflow')+'\n';
  for(const [rel,content] of Object.entries(files)){if(typeof content!=='string')throw Error('Missing composition resource: '+rel);safe(source,rel);}
  for(const match of files['SKILL.md'].matchAll(/\]\(([^)]+)\)/g))if(!files[match[1]])throw Error('Missing composed link: '+match[1]);
  packages[name]=stable(files);
 }
 const source_digests=sourceInputs(source),output_digests={};
 for(const [name,files] of Object.entries(packages))output_digests[name]=Object.fromEntries(Object.entries(files).map(([rel,content])=>[rel,hash(content)]));
 return {packages,source_digests,output_digests,identity:hash(json({flavor:profile.flavor,environment_id:profile.environment_id,source_digests,output_digests}))};
}
module.exports={hash,json,safe,read,readJson,inventory,resolveProfile,mergeSections,mergeResources,sourceInputs,compose};
