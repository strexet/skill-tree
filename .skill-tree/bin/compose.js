#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const c=require('../lib/composer.js');
const source=path.resolve(__dirname,'..');
function representativeOutputs(){
 const outputs={};
 for(const flavor of ['general','web','unity']) {
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-source-'));
  try{
   const write=(rel,value)=>{const full=path.join(root,rel);fs.mkdirSync(path.dirname(full),{recursive:true});fs.writeFileSync(full,typeof value==='string'?value:c.json(value));};
   if(flavor==='unity'){
    write('ProjectSettings/ProjectVersion.txt','m_EditorVersion: 6000.0.83f1\n');
    write('Packages/manifest.json',{dependencies:{'com.unity.test-framework':'1.4.6','com.unity.ugui':'2.0.0'}});
    write('Packages/packages-lock.json',{dependencies:{'com.unity.test-framework':{version:'1.4.6'},'com.unity.ugui':{version:'2.0.0'}}});
    write('Assets/Tests/EditMode/Tests.asmdef',{name:'Tests',optionalUnityReferences:['TestAssemblies']});
   }else write('package.json',{scripts:{test:'node --test'}});
   const built=c.compose(source,c.resolveProfile(source,root,flavor));
   for(const [name,files] of Object.entries(built.packages))for(const [rel,content] of Object.entries(files))outputs[`skills/${flavor}/${name}/${rel}`]=content;
  }finally{fs.rmSync(root,{recursive:true,force:true});}
 }
 return outputs;
}
if(require.main===module)process.stdout.write(c.json(representativeOutputs()));
module.exports={representativeOutputs};
