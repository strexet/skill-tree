'use strict';
const crypto=require('node:crypto');
const own=(value,key)=>Object.hasOwn(value,key);
const object=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const secretReference=value=>object(value)&&Object.keys(value).length===1&&own(value,'$secret');
function error(code,message){const result=Error(message);result.code=code;return result;}
function put(target,key,value){Object.defineProperty(target,key,{value,enumerable:true,writable:true,configurable:true});}
function data(container,key){const descriptor=Object.getOwnPropertyDescriptor(container,key);if(!descriptor)return undefined;if(!own(descriptor,'value'))throw error('parameter-json','Parameter accessors are not JSON');return descriptor.value;}
function clone(value,ancestors=new Set()){
 if(value===null||typeof value==='string'||typeof value==='boolean')return value;
 if(typeof value==='number'&&Number.isFinite(value))return value;
 if(typeof value!=='object'||ancestors.has(value))throw error('parameter-json','Parameters require finite, acyclic JSON data');
 if(!Array.isArray(value)&&![Object.prototype,null].includes(Object.getPrototypeOf(value)))throw error('parameter-json','Parameters require plain JSON objects');
 if(Object.getOwnPropertySymbols(value).length)throw error('parameter-json','Symbol keys are not JSON');
 ancestors.add(value);
 const result=Array.isArray(value)?[]:{};
 for(const key of Object.keys(value)){
  const descriptor=Object.getOwnPropertyDescriptor(value,key);
  if(!own(descriptor,'value'))throw error('parameter-json','Parameter accessors are not JSON');
  if(Array.isArray(value)&&(!/^(0|[1-9]\d*)$/.test(key)||Number(key)>=value.length))throw error('parameter-json','Arrays require JSON indices');
  put(result,key,clone(descriptor.value,ancestors));
 }
 if(Array.isArray(value)&&Object.keys(value).length!==value.length)throw error('parameter-json','Sparse arrays are not JSON');
 ancestors.delete(value);return result;
}
function stable(value){
 if(Array.isArray(value))return '['+value.map(stable).join(',')+']';
 if(object(value))return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+stable(value[key])).join(',')+'}';
 return JSON.stringify(value);
}
const pointer=(base,key)=>base+'/'+key.replace(/~/g,'~0').replace(/\//g,'~1');
function clearOrigins(origins,path){for(const key of Object.keys(origins))if(key===path||key.startsWith(path+'/'))delete origins[key];}
function markOrigins(value,path,layer,origins){
 if(object(value)&&!secretReference(value)&&Object.keys(value).length){for(const key of Object.keys(value))markOrigins(value[key],pointer(path,key),layer,origins);}
 else put(origins,path,layer);
}
function merge(current,incoming,path,layer,origins){
 if(!object(incoming)||secretReference(incoming)){
  clearOrigins(origins,path);markOrigins(incoming,path,layer,origins);return clone(incoming);
 }
 let result=current;
 if(!object(current)||secretReference(current)){result={};clearOrigins(origins,path);}
 if(!Object.keys(incoming).length&&!Object.keys(result).length)put(origins,path,layer);
 for(const key of Object.keys(incoming)){
  delete origins[path];
  put(result,key,merge(own(result,key)?result[key]:undefined,incoming[key],pointer(path,key),layer,origins));
 }
 return result;
}
const annotations=new Set(['$schema','$id','$comment','title','description','default','examples']);
const supported=new Set(['type','properties','required','additionalProperties','items','enum','const','minimum','maximum','minLength','maxLength','minItems','maxItems',...annotations]);
const types=new Set(['object','array','string','number','integer','boolean','null']);
function inspectSchema(schema){
 if(typeof schema==='boolean')return;
 if(!object(schema))throw error('parameter-schema-unsupported','A schema requires an object or boolean');
 for(const key of Object.keys(schema))if(!supported.has(key))throw error('parameter-schema-unsupported','Unsupported schema keyword: '+key);
 if(own(schema,'type')&&(typeof schema.type!=='string'||!types.has(schema.type)))throw error('parameter-schema-unsupported','Unsupported schema type');
 if(own(schema,'properties')){
  if(!object(schema.properties))throw error('parameter-schema-unsupported','Schema properties require an object');
  for(const child of Object.values(schema.properties))inspectSchema(child);
 }
 if(own(schema,'required')&&(!Array.isArray(schema.required)||schema.required.some(key=>typeof key!=='string')||new Set(schema.required).size!==schema.required.length))throw error('parameter-schema-unsupported','Schema required must contain unique property names');
 if(own(schema,'additionalProperties'))inspectSchema(schema.additionalProperties);
 if(own(schema,'items'))inspectSchema(schema.items);
 if(own(schema,'enum')&&(!Array.isArray(schema.enum)||!schema.enum.length))throw error('parameter-schema-unsupported','Schema enum requires values');
 for(const key of ['minimum','maximum'])if(own(schema,key)&&(typeof schema[key]!=='number'||!Number.isFinite(schema[key])))throw error('parameter-schema-unsupported','Schema bounds require finite numbers');
 for(const key of ['minLength','maxLength','minItems','maxItems'])if(own(schema,key)&&(!Number.isInteger(schema[key])||schema[key]<0))throw error('parameter-schema-unsupported','Schema size bounds require nonnegative integers');
}
function validate(value,schema,path=''){
 const fail=message=>{throw error('parameter-schema',(path||'/')+': '+message);};
 if(schema===false)fail('Value is rejected by the schema');
 if(schema===true)return;
 if(own(schema,'type')){
  const matches={object:object(value),array:Array.isArray(value),string:typeof value==='string',number:typeof value==='number',integer:Number.isInteger(value),boolean:typeof value==='boolean',null:value===null};
  if(!matches[schema.type])fail('Expected '+schema.type);
 }
 if(own(schema,'enum')&&!schema.enum.some(item=>stable(item)===stable(value)))fail('Value is outside the schema enum');
 if(own(schema,'const')&&stable(value)!==stable(schema.const))fail('Value differs from the schema constant');
 if(object(value)){
  for(const key of schema.required||[])if(!own(value,key))fail('Missing required property '+key);
  const properties=schema.properties||{};
  for(const key of Object.keys(value)){
   if(own(properties,key))validate(value[key],properties[key],pointer(path,key));
   else if(own(schema,'additionalProperties'))validate(value[key],schema.additionalProperties,pointer(path,key));
  }
 }
 if(Array.isArray(value)){
  if(own(schema,'minItems')&&value.length<schema.minItems||own(schema,'maxItems')&&value.length>schema.maxItems)fail('Array size is outside schema bounds');
  if(own(schema,'items'))value.forEach((item,index)=>validate(item,schema.items,pointer(path,String(index))));
 }
 if(typeof value==='string'){
  const length=Array.from(value).length;
  if(own(schema,'minLength')&&length<schema.minLength||own(schema,'maxLength')&&length>schema.maxLength)fail('String size is outside schema bounds');
 }
 if(typeof value==='number'&&(own(schema,'minimum')&&value<schema.minimum||own(schema,'maximum')&&value>schema.maximum))fail('Number is outside schema bounds');
}
function collectSecrets(value,names){
 if(secretReference(value)){
  if(typeof value.$secret!=='string'||!value.$secret.trim())throw error('parameter-json','A secret reference requires a nonempty name');
  names.add(value.$secret);return;
 }
 if(value!==null&&typeof value==='object')for(const item of Object.values(value))collectSecrets(item,names);
}
function resolveParameters(options={}){
 if(!object(options))throw error('parameter-json','Parameter options require an object');
 let values={},instructions='',instructionOrigin=null;
 const origins={values:{},instructions:null};
 for(const name of ['upstream','project','binding','run']){
  const layer=data(options,name);if(layer===undefined)continue;
  if(!object(layer))throw error('parameter-json','A parameter layer requires an object');
  if(own(layer,'values'))values=merge(values,clone(data(layer,'values')),'',name,origins.values);
  if(own(layer,'instructions')){
   const text=data(layer,'instructions');
   if(typeof text!=='string')throw error('parameter-json','Extra instructions require text');
   instructions=text;instructionOrigin=name;
  }
 }
 origins.instructions=instructionOrigin;
 let schemaStatus='absent';
 const declaredSchema=data(options,'schema');
 if(declaredSchema!==undefined){const schema=clone(declaredSchema);inspectSchema(schema);validate(values,schema);schemaStatus='validated';}
 const secrets=new Set();collectSecrets(values,secrets);
 const digest=crypto.createHash('sha256').update(stable({values,instructions})).digest('hex');
 return {values,instructions,origins,digest,schemaStatus,secretReferences:[...secrets].sort()};
}
module.exports={resolveParameters};
