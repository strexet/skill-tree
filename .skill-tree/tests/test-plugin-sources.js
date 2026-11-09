'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),crypto=require('node:crypto');
const api=require('../lib/plugins.js');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
function fixture(t,files){const root=fs.mkdtempSync(path.join(os.tmpdir(),'skill-tree-plugin-source-'));t.after(()=>fs.rmSync(root,{recursive:true,force:true}));for(const [rel,bytes]of Object.entries(files)){const dest=path.join(root,rel);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,bytes);}return root;}
const descriptor=(root,extra={})=>api.normalizeSource({id:'example',path:root,entry:'SKILL.md',...extra});
const code=expected=>error=>error.code===expected;

test('source and parameter facade exposes the usable foundation without installation dependencies',()=>{
 for(const name of ['normalizeSource','resolveSource','verifySnapshot','resolveParameters'])assert.equal(typeof api[name],'function');
});
test('local normalization separates the machine locator from portable discovery metadata',t=>{
 const root=fixture(t,{'SKILL.md':'# Example'}),n=descriptor(root);
 assert.equal(n.definition.source.kind,'local');assert.equal(n.definition.source.entry,'SKILL.md');assert.equal(n.locator.path,fs.realpathSync(root));assert.equal(JSON.stringify(n.definition).includes(root),false);assert.equal(n.definition.id,'example');
});
test('known source IDs preserve custom Claude provenance without an admission allowlist',()=>{
 const known={custom:{id:'custom',url:'https://example.invalid/custom.md',kind:'raw',metadata:{authoring_host:'claude',unknown_field:'kept'}}};
 const n=api.normalizeSource('custom',{known});assert.equal(n.definition.id,'custom');assert.equal(n.definition.source.kind,'raw');assert.deepEqual(n.definition.metadata,known.custom.metadata);
});
test('repository skill links preserve the selected ref and repository-relative entry',()=>{
 const sha='a'.repeat(40),n=api.normalizeSource('https://github.com/example/skills/blob/'+sha+'/skills/review/SKILL.md');
 assert.equal(n.definition.source.kind,'repository');assert.equal(n.definition.source.url,'https://github.com/example/skills');assert.equal(n.definition.source.ref,sha);assert.equal(n.definition.source.entry,'skills/review/SKILL.md');assert.equal(n.locator.url,'https://github.com/example/skills');
});
test('credential-bearing raw locators remain outside portable definitions',()=>{
 const url='https://alice:password@example.invalid/guide.md?token=secret',n=api.normalizeSource({id:'guide',kind:'raw',url});
 assert.equal(n.definition.source.url,'https://example.invalid/guide.md');assert.equal(n.locator.url,url);assert.equal(/password|token|secret/.test(JSON.stringify(n.definition)),false);
});
test('local snapshots preserve BOM, binary assets and original frontmatter bytes',async t=>{
 const original=Buffer.from('\ufeff---\nname: source\ncustom: true\n---\nRead [notes](references/notes.md) and [image](assets/picture.bin).\n'),asset=Buffer.from([0,255,128,13,10]);
 const root=fixture(t,{'SKILL.md':original,'references/notes.md':'# Notes','assets/picture.bin':asset}),s=await api.resolveSource(descriptor(root));
 assert.ok(Buffer.isBuffer(s.files['SKILL.md']));assert.deepEqual(s.files['SKILL.md'],original);assert.deepEqual(s.files['assets/picture.bin'],asset);assert.match(s.metadata.frontmatter,/custom: true/);assert.equal(s.digests['SKILL.md'],hash(original));assert.equal(api.verifySnapshot(s),true);
});
test('declared sibling resources and nested relative links form a closed source snapshot',async t=>{
 const root=fixture(t,{'skills/wrapper/SKILL.md':'Read [reference](references/main.md).','skills/wrapper/references/main.md':'Read [detail](detail.md).','skills/wrapper/references/detail.md':'# Detail','skills/grilling/SKILL.md':'# Delegated interview'});
 const s=await api.resolveSource(descriptor(root,{entry:'skills/wrapper/SKILL.md',dependencies:['skills/grilling/SKILL.md']}));
 assert.deepEqual(Object.keys(s.files).sort(),['skills/grilling/SKILL.md','skills/wrapper/SKILL.md','skills/wrapper/references/detail.md','skills/wrapper/references/main.md']);
});
test('Markdown links preserve referenced files and skip literal code and comments',async t=>{
 const markdown=[
  'Read [the instructions][Main Notes], [Shortcut], ![Diagram][], and [version](references/v2(guide).md "Guide").',
  'These are inline examples: `[literal](missing-inline.md)` and `<!-- literal comment marker`.',
  '', '```markdown', '[literal](missing-fenced.md)', '[Fake]: missing-example.md', '<!-- literal comment marker', '```',
  '', '~~~markdown', '[literal][unused]', '~~~',
  '', '<!--', '[comment](missing-comment.md)', '```literal fence marker', '-->',
  '', '[main notes]: <references/main notes.md#details>', '[shortcut]:', '  references/shortcut.md',
  '[diagram]: assets/diagram.png', '[unused]: missing-unused.md',
 ].join('\n');
 const files={'SKILL.md':markdown,'references/main notes.md':'# Notes','references/shortcut.md':'# Shortcut','references/v2(guide).md':'# Guide','assets/diagram.png':Buffer.from([0,255,128])};
 const snapshot=await api.resolveSource(descriptor(fixture(t,files)));
 assert.deepEqual(Object.keys(snapshot.files).sort(),Object.keys(files).sort());
 assert.deepEqual(snapshot.files['assets/diagram.png'],files['assets/diagram.png']);
});
test('nonstandard instruction content retains upstream bytes and a separate adaptation overlay',async t=>{
 const bytes=Buffer.from('Custom instructions without YAML.\n'),root=fixture(t,{'guide.txt':bytes}),s=await api.resolveSource(descriptor(root,{entry:'guide.txt',adapter:{mode:'source-backed',instructions:'Use as bounded context.'}}));
 assert.deepEqual(s.files['guide.txt'],bytes);assert.equal(s.adaptation.instructions,'Use as bounded context.');assert.equal(s.metadata.frontmatter,null);
});
test('missing required source resources reject snapshots',async t=>{
 const root=fixture(t,{'SKILL.md':'# Source'});await assert.rejects(api.resolveSource(descriptor(root,{resources:['references/missing.md']})),code('source-missing'));
});
test('resource paths cannot escape the admitted source root',t=>{
 const root=fixture(t,{'SKILL.md':'# Source'});assert.throws(()=>descriptor(root,{resources:['../outside.md']}),code('source-path'));
});
test('symlink resources reject acquisition without reading the target',async t=>{
 const root=fixture(t,{'SKILL.md':'# Source','original.md':'private'});fs.symlinkSync('original.md',path.join(root,'linked.md'));await assert.rejects(api.resolveSource(descriptor(root,{resources:['linked.md']})),code('source-path'));
});
test('expected content fingerprints reject acquisition drift',async t=>{
 const root=fixture(t,{'SKILL.md':'changed'});await assert.rejects(api.resolveSource(descriptor(root),{expectedDigests:{'SKILL.md':hash('original')}}),code('source-drift'));
});
test('injected repository acquisition records immutable actual revision and actual resource bytes',async()=>{
 const sha='b'.repeat(40),n=api.normalizeSource({id:'repo',kind:'repository',url:'https://example.invalid/skills.git',ref:'main',entry:'skills/a/SKILL.md'});let calls=0;
 const s=await api.resolveSource(n,{acquire:async request=>{calls++;assert.equal(request.definition.source.ref,'main');return {revision:sha,files:{'skills/a/SKILL.md':Buffer.from('# Real acquired bytes')}};}});
 assert.equal(calls,1);assert.equal(s.revision,sha);assert.equal(s.files['skills/a/SKILL.md'].toString(),'# Real acquired bytes');assert.equal(api.verifySnapshot(s),true);
});
test('mutable repository labels cannot masquerade as resolved immutable revisions',async()=>{
 const n=api.normalizeSource({id:'repo',kind:'repository',url:'https://example.invalid/skills.git'});await assert.rejects(api.resolveSource(n,{acquire:async()=>({revision:'main',files:{'SKILL.md':Buffer.from('# Source')}})}),code('source-revision'));
});
test('raw acquisition uses the actual acquired content snapshot and needs a real acquirer',async()=>{
 const n=api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md'});await assert.rejects(api.resolveSource(n),code('source-acquisition-required'));
 const bytes=Buffer.from('# Raw source'),s=await api.resolveSource(n,{acquire:async()=>({files:{'SKILL.md':bytes}})});assert.deepEqual(s.files['SKILL.md'],bytes);assert.equal(s.revision,'sha256:'+s.content_digest);
});
test('missing native capability permits complete inert resources without fake invocation',async t=>{
 const root=fixture(t,{'SKILL.md':'Requires native Skill tool.'}),s=await api.resolveSource(descriptor(root,{capabilities:['native-skill-tool']}),{availableCapabilities:[]});
 assert.deepEqual(s.execution.missing,['native-skill-tool']);assert.equal(s.execution.state,'unavailable');assert.equal(s.files['SKILL.md'].toString(),'Requires native Skill tool.');
});
test('source inspection never executes a bundled helper or copies unrelated adjacent files',async t=>{
 const root=fixture(t,{'SKILL.md':'Run [helper](scripts/helper.js) only when authorized.','scripts/helper.js':'require("node:fs").writeFileSync("EXECUTED","bad");','private.txt':'unrelated'}),s=await api.resolveSource(descriptor(root));
 assert.ok(s.files['scripts/helper.js']);assert.equal(s.files['private.txt'],undefined);assert.equal(fs.existsSync(path.join(root,'EXECUTED')),false);
});
test('parameters apply upstream project binding run precedence with object merge and array/scalar/null replacement',()=>{
 const r=api.resolveParameters({upstream:{values:{nested:{a:1,b:1},items:[1],nullable:'old'}},project:{values:{nested:{b:2}}},binding:{values:{items:[2,3]}},run:{values:{nested:{a:9},nullable:null}}});
 assert.deepEqual(r.values,{nested:{a:9,b:2},items:[2,3],nullable:null});
});
test('extra instruction text uses the highest explicit value including an empty string',()=>{
 const r=api.resolveParameters({upstream:{instructions:'Upstream'},project:{instructions:'Project'},binding:{instructions:'Binding'},run:{instructions:''}});assert.equal(r.instructions,'');assert.equal(r.origins.instructions,'run');
});
test('parameter origins and deterministic digest describe actual effective values',()=>{
 const a=api.resolveParameters({upstream:{values:{a:1,b:2}},binding:{values:{b:3}}}),b=api.resolveParameters({upstream:{values:{b:2,a:1}},binding:{values:{b:3}}});
 assert.equal(a.origins.values['/a'],'upstream');assert.equal(a.origins.values['/b'],'binding');assert.match(a.digest,/^[a-f0-9]{64}$/);assert.equal(a.digest,b.digest);assert.notEqual(a.digest,api.resolveParameters({upstream:{values:{a:1,b:4}}}).digest);
});
test('secret references stay references and no resolver reads secret values',()=>{
 const ref={$secret:'SERVICE_TOKEN'},r=api.resolveParameters({upstream:{values:{token:ref}},resolveSecret:()=>{throw Error('Must not resolve a secret during configuration');}});assert.deepEqual(r.values.token,ref);assert.equal(r.secretReferences[0],'SERVICE_TOKEN');
});
test('arbitrary plugin parameter names remain isolated from core authority and prototype state',()=>{
 const values=JSON.parse('{"mode":"plugin-own-mode","authority":{"scope":"plugin-data"},"__proto__":{"polluted":true}}'),r=api.resolveParameters({run:{values}});
 assert.equal(r.values.mode,'plugin-own-mode');assert.deepEqual(r.values.authority,{scope:'plugin-data'});assert.equal(Object.prototype.polluted,undefined);assert.equal(Object.hasOwn(r.values,'__proto__'),true);assert.equal(r.mode,undefined);assert.equal(r.authority,undefined);
});
test('supported optional schemas validate concrete resolved values',()=>{
 const schema={type:'object',properties:{tone:{type:'string',enum:['direct','gentle']}},required:['tone'],additionalProperties:false};
 assert.throws(()=>api.resolveParameters({run:{values:{tone:'unknown'}},schema}),code('parameter-schema'));assert.equal(api.resolveParameters({run:{values:{tone:'direct'}},schema}).schemaStatus,'validated');
});
test('unsupported schema constraints and non-JSON values remain explicit failures',()=>{
 assert.throws(()=>api.resolveParameters({run:{values:{}},schema:{$ref:'https://example.invalid/schema'}}),code('parameter-schema-unsupported'));assert.throws(()=>api.resolveParameters({run:{values:{bad:Infinity}}}),code('parameter-json'));
});
test('resolution leaves configuration inputs unchanged and snapshot validation rejects byte tampering',async t=>{
 const input={upstream:{values:{a:{b:1}}},binding:{values:{a:{c:2}}}},before=JSON.stringify(input);api.resolveParameters(input);assert.equal(JSON.stringify(input),before);
 const root=fixture(t,{'SKILL.md':'# Original'}),s=await api.resolveSource(descriptor(root));assert.equal(api.verifySnapshot(s),true);s.files['SKILL.md']=Buffer.from('# Changed');assert.throws(()=>api.verifySnapshot(s),code('source-drift'));
});
test('source ID collisions reject unrelated source reuse while matching known definitions remain reusable',()=>{
 const known={same:{id:'same',kind:'raw',url:'https://example.invalid/first.md'}};
 assert.throws(()=>api.normalizeSource({id:'same',kind:'raw',url:'https://example.invalid/other.md'},{known}),code('source-identity'));
 assert.equal(api.normalizeSource({id:'same',kind:'raw',url:'https://example.invalid/first.md'},{known}).definition.id,'same');
});
test('an acquired resource map cannot smuggle escaping paths into an otherwise valid snapshot',async()=>{
 const n=api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md'});
 await assert.rejects(api.resolveSource(n,{acquire:async()=>({files:{'SKILL.md':Buffer.from('# Valid'),'../escape':Buffer.from('bad')}})}),code('source-path'));
});
test('secret references atomically replace objects in both directions with matching origins',()=>{
 const a=api.resolveParameters({upstream:{values:{credential:{provider:'old'}}},binding:{values:{credential:{$secret:'TOKEN'}}}});
 assert.deepEqual(a.values.credential,{$secret:'TOKEN'});assert.deepEqual(a.secretReferences,['TOKEN']);assert.equal(a.origins.values['/credential'],'binding');
 const b=api.resolveParameters({upstream:{values:{credential:{$secret:'TOKEN'}}},binding:{values:{credential:{provider:'new'}}}});
 assert.deepEqual(b.values.credential,{provider:'new'});assert.deepEqual(b.secretReferences,[]);assert.equal(b.origins.values['/credential/provider'],'binding');
});
test('empty and null replacements preserve explicit origin and do not mutate layer inputs',()=>{
 const options={upstream:{values:{a:{old:1},b:[1],c:'old'}},run:{values:{a:{},b:[],c:null}}},before=JSON.stringify(options),r=api.resolveParameters(options);
 assert.deepEqual(r.values,{a:{old:1},b:[],c:null});assert.equal(r.origins.values['/a/old'],'upstream');assert.equal(r.origins.values['/b'],'run');assert.equal(r.origins.values['/c'],'run');assert.equal(JSON.stringify(options),before);
});
test('parameter accessors never execute and nested unsupported schema constraints are explicit',()=>{
 let reads=0;const values={};Object.defineProperty(values,'danger',{enumerable:true,get(){reads++;return 'bad';}});
 assert.throws(()=>api.resolveParameters({run:{values}}),code('parameter-json'));assert.equal(reads,0);
 assert.throws(()=>api.resolveParameters({run:{values:{}},schema:{properties:{nested:{$ref:'https://example.invalid/schema'}}}}),code('parameter-schema-unsupported'));
});
test('snapshot verification rejects mutable repository revisions and inconsistent descriptor identity',async()=>{
 const sha='c'.repeat(40),n=api.normalizeSource({id:'repo',kind:'repository',url:'https://example.invalid/a.git',ref:sha}),s=await api.resolveSource(n,{acquire:async()=>({revision:sha,files:{'SKILL.md':Buffer.from('# Pinned')}})});
 assert.equal(api.verifySnapshot(s),true);s.revision='main';assert.throws(()=>api.verifySnapshot(s),code('source-drift'));s.revision=sha;
 s.source.ref='d'.repeat(40);assert.throws(()=>api.verifySnapshot(s),code('source-drift'));s.source.ref=sha;
 s.source.kind='unknown';assert.throws(()=>api.verifySnapshot(s),code('source-drift'));s.source.kind='repository';
 s.source.entry='other.md';assert.throws(()=>api.verifySnapshot(s),code('source-drift'));s.source.entry='SKILL.md';
 s.plugin_id='Invalid ID';assert.throws(()=>api.verifySnapshot(s),code('source-drift'));
});
test('portable resource paths reject Windows absolute paths on every host',async()=>{
 assert.throws(()=>api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md',entry:'C:/private/SKILL.md'}),code('source-path'));
 const n=api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md'});
 await assert.rejects(api.resolveSource(n,{acquire:async()=>({files:{'SKILL.md':Buffer.from('# Valid'),'C:/private/secret':Buffer.from('bad')}})}),code('source-path'));
});
test('acquired paths normalize once and reject aliases while staged paths stay canonical',async()=>{
 const n=api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md'}),bytes=Buffer.from('# Source');
 await assert.rejects(api.resolveSource(n,{acquire:async()=>({files:{'SKILL.md':bytes,'./SKILL.md':bytes}})}),code('source-path'));
 const s=await api.resolveSource(n,{acquire:async()=>({files:{'./SKILL.md':bytes}})});assert.deepEqual(Object.keys(s.files),['SKILL.md']);assert.equal(api.verifySnapshot(s),true);
 s.files['./SKILL.md']=s.files['SKILL.md'];delete s.files['SKILL.md'];assert.throws(()=>api.verifySnapshot(s),code('source-drift'));
});
test('a normalized local root replaced by a symlink rejects before outside source acquisition',async t=>{
 const root=fixture(t,{'SKILL.md':'# Original'}),outside=fixture(t,{'SKILL.md':'# Outside'}),n=descriptor(root),saved=root+'-saved';
 fs.renameSync(root,saved);t.after(()=>fs.rmSync(saved,{recursive:true,force:true}));fs.symlinkSync(outside,root,'dir');
 const read=fs.readFileSync;let reads=0;
 fs.readFileSync=function(file,...args){if(String(file).startsWith(root+path.sep)){reads++;throw Error('An outside source must not be read');}return read.call(this,file,...args);};
 try{await assert.rejects(api.resolveSource(n),code('source-path'));assert.equal(reads,0);}finally{fs.readFileSync=read;}
});
test('GitHub and GitLab folder links normalize to repository entry points with explicit overrides',()=>{
 const github=api.normalizeSource('https://github.com/example/skills/tree/main/skills/review');
 assert.equal(github.definition.source.kind,'repository');assert.equal(github.definition.source.ref,'main');assert.equal(github.definition.source.entry,'skills/review/SKILL.md');assert.equal(github.locator.url,'https://github.com/example/skills');
 const gitlab=api.normalizeSource('https://gitlab.example/group/skills/-/tree/main/skills/review');
 assert.equal(gitlab.definition.source.kind,'repository');assert.equal(gitlab.definition.source.entry,'skills/review/SKILL.md');assert.equal(gitlab.locator.url,'https://gitlab.example/group/skills');
 const custom=api.normalizeSource({id:'override',kind:'repository',url:'https://github.com/example/skills/tree/feature/name/skills/review',ref:'feature/name',entry:'skills/review/guide.txt'});
 assert.equal(custom.definition.source.ref,'feature/name');assert.equal(custom.definition.source.entry,'skills/review/guide.txt');assert.equal(custom.locator.url,'https://github.com/example/skills');
});
test('ssh and git URL strings remain repository acquisitions without credential exposure',()=>{
 for(const url of ['ssh://git@example.invalid/group/skills.git','git://example.invalid/group/skills']){
  const n=api.normalizeSource(url);assert.equal(n.definition.source.kind,'repository');assert.equal(n.definition.source.entry,'SKILL.md');assert.equal(n.locator.url,url);assert.equal(n.definition.source.url.includes('git@'),false);
 }
});
test('hosted ref and entry segments decode safely and encoded path escapes remain rejected',()=>{
 const n=api.normalizeSource('https://github.com/example/skills/blob/feature%2Freview/skills/review%20notes/SKILL.md');
 assert.equal(n.definition.source.ref,'feature/review');assert.equal(n.definition.source.entry,'skills/review notes/SKILL.md');
 assert.throws(()=>api.normalizeSource('https://gitlab.example/group/skills/-/blob/main/%2e%2e/secret.md'),code('source-path'));
 assert.throws(()=>api.normalizeSource('https://github.com/example/skills/tree/main/skills/%ZZ'),code('source-path'));
});
test('remote declared directory resources accept trailing separators without changing closure guards',async()=>{
 const n=api.normalizeSource({id:'raw',kind:'raw',url:'https://example.invalid/SKILL.md',resources:['references/']});
 const s=await api.resolveSource(n,{acquire:async()=>({files:{'SKILL.md':Buffer.from('# Entry'),'references/guide.md':Buffer.from('# Guide')}})});
 assert.deepEqual(Object.keys(s.files).sort(),['SKILL.md','references/guide.md']);assert.equal(api.verifySnapshot(s),true);
 assert.throws(()=>api.normalizeSource({id:'root',kind:'raw',url:'https://example.invalid/SKILL.md',resources:['./']}),code('source-path'));
});
