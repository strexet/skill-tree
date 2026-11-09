'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),http=require('node:http'),cp=require('node:child_process');
const sources=require('../../lib/plugin-sources.js'),remote=require('../../lib/plugin-acquisition.js');
function temporary(t){const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-acquisition-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));return root;}
async function server(t,handler){const result=http.createServer(handler);await new Promise(resolve=>result.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>{result.closeAllConnections?.();result.close(resolve);}));return 'http://127.0.0.1:'+result.address().port;}
function git(root,args){const result=cp.spawnSync('git',['-c','core.hooksPath='+os.devNull,'-C',root,...args],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);return result.stdout.trim();}
function repository(t,symlink=false){const root=temporary(t),repo=path.join(root,'repository'),scratch=path.join(root,'scratch');fs.mkdirSync(repo);fs.mkdirSync(scratch);git(repo,['init','-b','main']);fs.mkdirSync(path.join(repo,'assets'));fs.writeFileSync(path.join(repo,'SKILL.md'),'# Source\nRead [asset](assets/data.bin).\n');const bytes=Buffer.from([0,255,128,13,10]);fs.writeFileSync(path.join(repo,'assets/data.bin'),bytes);if(symlink){fs.unlinkSync(path.join(repo,'assets/data.bin'));fs.symlinkSync('../SKILL.md',path.join(repo,'assets/data.bin'));}fs.writeFileSync(path.join(repo,'.git/hooks/post-checkout'),'#!/bin/sh\ntouch "'+path.join(root,'EXECUTED')+'"\n',{mode:0o755});git(repo,['add','.']);git(repo,['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Fixture']);return {root,repo,scratch,bytes,commit:git(repo,['rev-parse','HEAD'])};}
const rejects=expected=>error=>error.code===expected;

test('raw acquisition reads linked nested and binary resources as bytes without executing bundled helpers',async t=>{
 const binary=Buffer.from([0,255,128,13,10]),files={'/skill/SKILL.md':Buffer.from('# Source\nRead [reference](references/main.md).'),'/skill/references/main.md':Buffer.from('Read [asset](../assets/data.bin) and [helper](../scripts/helper.js).'),'/skill/assets/data.bin':binary,'/skill/scripts/helper.js':Buffer.from('throw Error("must not execute");')},requests=[];
 const base=await server(t,(req,res)=>{requests.push(req.url);if(!files[req.url]){res.writeHead(404);res.end();return;}res.end(files[req.url]);});
 const n=sources.normalizeSource({id:'raw',kind:'raw',url:base+'/skill/SKILL.md'}),snapshot=await sources.resolveSource(n,{acquire:remote.acquireRemote});
 assert.deepEqual(snapshot.files['assets/data.bin'],binary);assert.deepEqual(Object.keys(snapshot.files).sort(),['SKILL.md','assets/data.bin','references/main.md','scripts/helper.js']);assert.equal(requests.length,4);
});
test('raw HTTP failures expose sanitized errors rather than source credentials or URLs',async t=>{
 const base=await server(t,(_req,res)=>{res.writeHead(404);res.end('private response');}),url=base.replace('://','://alice:super-secret@')+'/missing.md?token=private-token';
 const n=sources.normalizeSource({id:'missing',kind:'raw',url});
 await assert.rejects(remote.acquireRemote(n),error=>{assert.equal(/super-secret|private-token|alice|127\.0\.0\.1/.test(error.message),false);return error.code==='source-acquisition';});
});
test('raw body and aggregate byte limits stop acquisition without returning partial success',async t=>{
 const base=await server(t,(req,res)=>{if(req.url==='/large.md'){res.end(Buffer.alloc(512));return;}res.end(req.url==='/SKILL.md'?'Read [asset](asset.bin).':Buffer.alloc(64));});
 await assert.rejects(remote.acquireRemote(sources.normalizeSource({id:'large',kind:'raw',url:base+'/large.md'}),{maxBytes:32}),rejects('source-size'));
 await assert.rejects(remote.acquireRemote(sources.normalizeSource({id:'total',kind:'raw',url:base+'/SKILL.md'}),{maxBytes:64}),rejects('source-size'));
});
test('raw acquisition enforces one total timeout and closes an unresolved request',async t=>{
 const base=await server(t,()=>{}),n=sources.normalizeSource({id:'timeout',kind:'raw',url:base+'/SKILL.md'});
 await assert.rejects(remote.acquireRemote(n,{timeoutMs:40}),rejects('source-timeout'));
});
test('bare Git acquisition proves the actual commit and binary closure without checkout or retained temporary files',async t=>{
 const f=repository(t),n=sources.normalizeSource({id:'git-source',kind:'repository',url:'https://example.invalid/source.git',ref:'main'}),snapshot=await sources.resolveSource(n,{acquire:request=>remote.acquireRemote(request,{transportUrl:f.repo,tempDir:f.scratch})});
 assert.equal(snapshot.revision,f.commit);assert.deepEqual(snapshot.files['assets/data.bin'],f.bytes);assert.deepEqual(fs.readdirSync(f.scratch),[]);assert.equal(fs.existsSync(path.join(f.root,'EXECUTED')),false);assert.equal(sources.verifySnapshot(snapshot),true);
});
test('Git symlink resources and oversized content reject safely and clean temporary state',async t=>{
 const linked=repository(t,true),n=sources.normalizeSource({id:'git-source',kind:'repository',url:'https://example.invalid/source.git',ref:'main'});
 await assert.rejects(remote.acquireRemote(n,{transportUrl:linked.repo,tempDir:linked.scratch}),rejects('source-path'));assert.deepEqual(fs.readdirSync(linked.scratch),[]);
 const big=repository(t);fs.writeFileSync(path.join(big.repo,'assets/data.bin'),Buffer.alloc(2048));git(big.repo,['add','.']);git(big.repo,['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m','Bigger']);
 await assert.rejects(remote.acquireRemote(n,{transportUrl:big.repo,tempDir:big.scratch,maxBytes:128,maxRepositoryBytes:1024*1024}),rejects('source-size'));assert.deepEqual(fs.readdirSync(big.scratch),[]);
 const missing={...n,definition:{...n.definition,source:{...n.definition.source,ref:'missing-ref'}}};
 await assert.rejects(remote.acquireRemote(missing,{transportUrl:big.repo,tempDir:big.scratch}),failure=>failure.code==='source-acquisition'&&!failure.message.includes(big.repo));assert.deepEqual(fs.readdirSync(big.scratch),[]);
});
test('synchronous Git argument rejection sanitizes credential locators and cleans the initialized temporary repository',async t=>{
 const scratch=temporary(t),secret='dummy-boundary-password',url='https://dummy-boundary-user:'+secret+'@example.invalid/repository.git\0';
 const request={definition:{source:{kind:'repository',entry:'SKILL.md'}},locator:{url}},exec=cp.execFile,operations=[];
 cp.execFile=function(command,args,...rest){if(command==='git')operations.push(args.includes('init')?'init':args.includes('fetch')?'fetch':'other');return exec.call(this,command,args,...rest);};
 try{
  for(const options of [{tempDir:scratch},{tempDir:scratch,transportUrl:url}]){
   await assert.rejects(remote.acquireRemote(request,options),failure=>failure.code==='source-acquisition'&&!failure.message.includes(secret)&&!failure.message.includes('dummy-boundary-user'));
   assert.deepEqual(fs.readdirSync(scratch),[]);
  }
  assert.deepEqual(operations,['init','fetch','init','fetch']);
 }finally{cp.execFile=exec;}
});
