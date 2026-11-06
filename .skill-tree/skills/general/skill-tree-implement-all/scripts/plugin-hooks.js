'use strict';
// Built-in-only bootstrap checks copied dispatchers before loading a local helper.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const hash=value=>crypto.createHash('sha256').update(value).digest('hex');
function stable(value){if(Array.isArray(value))return value.map(stable);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])]));return value;}
const json=value=>JSON.stringify(stable(value),null,2)+'\n';
function safe(root,relative){
 if(typeof relative!=='string'||!relative||path.isAbsolute(relative)||path.win32.isAbsolute(relative)||relative.includes('\\')||relative.includes('\0')||relative.split('/').some(value=>!value||value==='.'||value==='..'))throw Error('Invalid owned helper resource path');
 let file=fs.realpathSync(root);for(const value of relative.split('/')){file=path.join(file,value);if(fs.lstatSync(file).isSymbolicLink())throw Error('Owned helper resource symlink conflict');}return file;
}
function verifyBootstrap(root){
 const manifest=JSON.parse(fs.readFileSync(safe(root,'references/plugin-bindings.json'),'utf8')),{identity,...content}=manifest;
 if(manifest.format!=='skill-tree-plugin-bindings'||manifest.schema!==1||identity!==hash(json(content))||!manifest.owned_resources||Array.isArray(manifest.owned_resources))throw Error('Invalid owned helper inventory manifest');
 const required=['plugin-hooks.js','plugin-composition.js','plugin-bindings.js','plugin-parameters.js','plugin-registry.js','plugin-sources.js','workflow-state.py','decision-governance.py','decision-orchestration.py','run-workspaces.py','validate-document-rules.py'];
 for(const name of required)if(!Object.hasOwn(manifest.owned_resources,'scripts/'+name))throw Error('The owned helper closure is incomplete');
 for(const [relative,sum]of Object.entries(manifest.owned_resources))if(typeof sum!=='string'||!/^[a-f0-9]{64}$/.test(sum)||hash(fs.readFileSync(safe(root,relative)))!==sum)throw Error('Owned helper resource digest changed: '+relative);
}
if(require.main===module){try{
 if(process.argv.length!==4||process.argv[2]!=='--input')throw Error('Usage: node scripts/plugin-hooks.js --input <request.json>');
 const root=path.resolve(__dirname,'..');verifyBootstrap(root);
 const api=require('./plugin-composition.js'),value=api.prepareBoundary(root,JSON.parse(fs.readFileSync(process.argv[3],'utf8')));process.stdout.write(JSON.stringify(value,null,2)+'\n');
}catch(error){process.stderr.write(error.message+'\n');process.exitCode=1;}}
module.exports={verifyBootstrap};
