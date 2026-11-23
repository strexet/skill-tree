/* Black-box qualification of the actual signed-out Blazor /privacy entry point. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const { createRequire } = require('node:module');
const repo = process.env.HABITICA_REPO;
if (!repo) throw Error('Set HABITICA_REPO to a checkout of Habitica Tool containing the baseline commit.');
const moduleName = process.env.PLAYWRIGHT_PATH || 'playwright';
const { chromium } = require(moduleName);
const { PNG } = createRequire(require.resolve(moduleName))('playwright-core/lib/utilsBundle');
const [originArg, outFile, screenshotDir] = process.argv.slice(2);
if (!originArg || !outFile) throw Error('Usage: node verify.cjs ORIGIN OUT_JSON [SCREENSHOT_DIR]');
const origin = new URL(originArg).origin;
if (!['127.0.0.1','localhost','[::1]'].includes(new URL(origin).hostname)) throw Error('A loopback origin is required');
const sha = '51ac91982f61b5bde7cebc26629c2e2e621a4a24';
const show = filename => execFileSync('git',['-C',repo,'show',sha + ':' + filename],{encoding:'utf8',maxBuffer:12e6});
const normalize = s => s.replace(/\s+/g,' ').trim();
const original = show('src/Habitica.WebApp/Pages/PrivacyPage.razor');
const groups = [...original.matchAll(/<MudPaper[^>]*>([\s\S]*?)<\/MudPaper>/g)].map(m => ({
  heading:normalize(m[1].match(/<h2>([^<]+)<\/h2>/)[1]),
  paragraphs:[...m[1].matchAll(/<p>([^<]+)<\/p>/g)].map(p=>normalize(p[1]))
}));
const intro = normalize(original.match(/<p class="panel-copy">([\s\S]*?)<\/p>/)[1]);
const catalog = JSON.parse(show('.skill-tree/history/reviews/ux-ui-2026-11-03/schemes.json'));
const targets = ['Personal Notes','Habitica credentials','Private sync'];
const schemes = ['gryphy-light','obsidian-glow'];
const report = {
  schema:2, originalRunner:'5c0c7e7190d0021165639613639b004d476e6ae41e9d98a9f82e84c03616e31c', origin, route:'/privacy', baselineSource:sha, runnerSha256:createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
  method:'Headless installed Chrome, real hydrated signed-out route and app assets, isolated browser context per cell, service workers blocked, only same-origin HTTP permitted. One-time fast-cache seed via application color scheme helper before opening /privacy. No reseed on reload. Native keyboard input for all jumps/disclosure and full-label native scheme typeahead; an independent fresh reading flow checks focus and viewport after the explicit Return action. 16/32px root per project convention.',
  limits:'Chromium desktop emulation at CSS viewports; no physical device or screen reader. Contrast samples computed text color against actual raster backgrounds at selected control labels; this is not a whole-page accessibility audit.',
  rows:[]
};
const shortError = e=>String(e.message || e).split('\n').slice(0,2).join(' ').slice(0,360);
const delay = ms => new Promise(r=>setTimeout(r,ms));
const firstVisible = async list => {
  for (const item of await list.all()) if(await item.isVisible()) return item;
};
function buttonOrLink(container,name) {
  return container.getByRole('link',{name}).or(container.getByRole('button',{name}));
}
async function tabTo(page,locator,direction='Tab') {
  if (!locator || !await locator.count()) return {reached:false,steps:0};
  for(let steps=0;steps<65;steps++){
    if(await locator.evaluate(e=>e===document.activeElement)) return {reached:true,steps};
    await page.keyboard.press(direction);
  }
  return {reached:false,steps:65};
}
async function stateOf(toggle) {
  return toggle.evaluate(el=> el.tagName==='SUMMARY' ? el.parentElement.open :
    ({true:true,false:false})[el.getAttribute('aria-expanded')] ?? null);
}
async function afterFrames(page) {
  await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
}
async function focusEvidence(loc) {
  return loc.evaluate(e=>{
    const style=getComputedStyle(e),r=e.getBoundingClientRect();
    const x=Math.max(1,Math.min(innerWidth-2,r.left+r.width/2)),y=Math.max(1,Math.min(innerHeight-2,r.top+r.height/2));
    const hit=document.elementFromPoint(x,y);
    return {active:document.activeElement===e,focusVisible:e.matches(':focus-visible'),outline:style.outlineStyle,
      outlineWidth:parseFloat(style.outlineWidth),shadow:style.boxShadow,hit:e===hit||e.contains(hit),
      top:Math.round(r.top),bottom:Math.round(r.bottom),viewportHeight:innerHeight};
  });
}
async function appearance(page) {
  return page.evaluate(()=>{
    const root=document.documentElement,s=getComputedStyle(root),prefs=window.HabiticaColorScheme.getPreferences();
    return {scheme:root.dataset.colorScheme,bg:s.getPropertyValue('--bg').trim(),ink:s.getPropertyValue('--ink').trim(),
      fontSize:parseFloat(s.fontSize),saved:prefs?.selectedSchemeId, headingColor:getComputedStyle(document.querySelector('main h1')).color};
  });
}
function actualPalette(state,id) {
  const t=catalog[id].tokens;
  return state.scheme===id && state.bg.toLowerCase()===t.background.toLowerCase() && state.ink.toLowerCase()===t.ink.toLowerCase();
}
async function routeGeometry(main){
  return main.evaluate(el=>{
    const width=innerWidth,selector='h1,h2,p,a[href],button,summary,select,label,input,[role=button],[role=radio],[role=combobox]';
    const text=e=>e.getAttribute('aria-label')||e.innerText?.replace(/\s+/g,' ').trim().slice(0,70)||e.name||e.tagName;
    const closed=e=>{const d=e.closest('details:not([open])');return d&&!d.querySelector(':scope > summary')?.contains(e)};
    const over=[];
    for(const e of el.querySelectorAll(selector)){
      const r=e.getBoundingClientRect(),s=getComputedStyle(e);
      if(!r.width||!r.height||closed(e)||s.visibility==='hidden'||s.display==='none')continue;
      const range=document.createRange();range.selectNodeContents(e);
      const rects=e.matches('select,input,button')?[]:[...range.getClientRects()].filter(r=>r.width&&r.height);
      const left=Math.min(r.left,...rects.map(r=>r.left)), right=Math.max(r.right,...rects.map(r=>r.right));
      if(left< -1||right>width+1||e.clientWidth>0 && e.scrollWidth>e.clientWidth+2)
        over.push({element:e.tagName,text:text(e),left:Math.round(left),right:Math.round(right),client:e.clientWidth,scroll:e.scrollWidth});
    }
    const shellOutside=[...document.querySelectorAll('header,header *,footer,footer *,[role=banner] *')].filter(e=>{
      const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&(r.right>width+1||r.left< -1);
    }).slice(0,8).map(e=>({tag:e.tagName,text:text(e)}));
    return {width,documentWidth:document.documentElement.scrollWidth,routeOverflow:over,shellOutside};
  });
}
async function integrity(main) {
  return main.evaluate((el,{groups,intro})=>{
    const norm=s=>(s||'').replace(/\s+/g,' ').trim();
    const nodes=[...el.querySelectorAll('h2,p')],titles=groups.map(g=>g.heading),errors=[];
    for(const {heading,paragraphs} of groups){
      const matches=nodes.filter(e=>e.tagName==='H2'&&norm(e.textContent)===heading);
      if(matches.length!==1){errors.push({heading,count:matches.length});continue;}
      const next=nodes.slice(nodes.indexOf(matches[0])+1),stop=next.findIndex(e=>e.tagName==='H2'&&titles.includes(norm(e.textContent)));
      const texts=next.slice(0,stop<0?undefined:stop).filter(e=>e.tagName==='P').map(e=>norm(e.textContent));
      let last=-1;
      for(const [index,p] of paragraphs.entries()){
        const current=texts.indexOf(p);
        if(current<0||current<=last||texts.lastIndexOf(p)!==current)errors.push({heading,paragraph:index+1});
        last=current;
      }
    }
    return {errors,intro:[...el.querySelectorAll('p')].some(e=>norm(e.textContent)===intro),
      originalHeadings:groups.length,originalSectionParagraphs:groups.reduce((n,g)=>n+g.paragraphs.length,0)};
  },{groups,intro});
}
const lum=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
async function contrast(locator) {
  // Sample the background below real label ink, including translucent surfaces and gradients.
  // Hiding only text fill for the screenshot preserves every box and background paint operation.
  await locator.scrollIntoViewIfNeeded();
  const paint = await locator.evaluate(el=>{
    function canSampleLabel(owner) {
      if (!owner.checkVisibility({opacityProperty: true, visibilityProperty: true})) return false;
      // The sampler blends text alpha against a captured background. CSS group opacity
      // composites the whole subtree separately, which needs a different color model.
      for (let ancestor = owner; ancestor; ancestor = ancestor.parentElement) {
        if (Number(getComputedStyle(ancestor).opacity) !== 1) return false;
      }
      return true;
    }
    const range=document.createRange(),walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
    let node;
    while(node=walker.nextNode()) {
      if(!node.textContent.trim()||node.parentElement.closest('option,svg,[aria-hidden=true]'))continue;
      range.selectNodeContents(node);
      const rr=[...range.getClientRects()].find(r=>r.width>2&&r.height>2);
      if(rr){
        if(!canSampleLabel(node.parentElement)) return null;
        const er=el.getBoundingClientRect(),s=getComputedStyle(node.parentElement);return {x:rr.x-er.x,y:rr.y-er.y,w:rr.width,h:rr.height,color:s.webkitTextFillColor||s.color,size:parseFloat(s.fontSize),weight:parseInt(s.fontWeight)||400};
      }
    }
    if(el.tagName==='SELECT'){
      if(!canSampleLabel(el)) return null;
      const r=el.getBoundingClientRect(),s=getComputedStyle(el);
      return {x:parseFloat(s.paddingLeft)+2,y:r.height*.25,w:Math.max(1,r.width-40),h:r.height*.5,color:s.webkitTextFillColor||s.color,size:parseFloat(s.fontSize),weight:parseInt(s.fontWeight)||400};
    }
  });
  if(!paint)return null;
  const rgb=paint.color.match(/[\d.]+/g)?.map(Number);
  if(!rgb||rgb.length<3||(!paint.color.startsWith('rgb')))return null;
  const png=PNG.sync.read(await locator.screenshot({animations:'disabled',style:'* {-webkit-text-fill-color: transparent !important; text-shadow: none !important;}'}));
  const samples=[.2,.5,.8].map(f=>{
    const x=Math.min(png.width-1,Math.max(0,Math.floor(paint.x+f*paint.w))),y=Math.min(png.height-1,Math.max(0,Math.floor(paint.y+paint.h*.5)));
    const index=4*(png.width*y+x),back=Array.from(png.data.slice(index,index+3));
    const a=rgb.length>3?rgb[3]:1,fore=rgb.slice(0,3).map((v,i)=>v*a+back[i]*(1-a));
    const aL=lum(fore),bL=lum(back);
    return +((Math.max(aL,bL)+.05)/(Math.min(aL,bL)+.05)).toFixed(3);
  });
  return {minimum:Math.min(...samples),threshold:paint.size>=24||paint.size>=18.667&&paint.weight>=700?3:4.5,foreground:paint.color};
}
async function chooseScheme(main,page,id) {
  const name=catalog[id].name;
  const options=main.getByRole('combobox').or(main.getByRole('listbox'));
  for(const item of await options.all()){
    if(!await item.isVisible())continue;
    if(await item.evaluate(e=>e.tagName==='SELECT')){
      const list=await item.locator('option').evaluateAll(els=>els.map(e=>({name:e.textContent.trim(),value:e.value})));
      const idx=list.findIndex(o=>o.value===id || o.name.toLowerCase().includes(name.toLowerCase()));
      if(idx<0) continue;
      const access=await tabTo(page,item);if(!access.reached)throw Error('Scheme chooser unreachable by Tab');
      await page.evaluate(()=>{
        window.__privacySelectEvents=[];
        for(const type of ['input','change'])document.addEventListener(type,e=>{
          if(e.target.tagName==='SELECT')window.__privacySelectEvents.push({type,value:e.target.value,trusted:e.isTrusted});
        },true);
      });
      await page.keyboard.type(list[idx].name);
      const observed=await item.inputValue(),events=await page.evaluate(()=>window.__privacySelectEvents);
      return {mechanism:'full label typed on focused native select',label:name,optionCount:list.length,access,observed,events};
    }
    if((await tabTo(page,item)).reached){await page.keyboard.press('Enter');break;}
  }
  const matches=main.getByRole('radio',{name:new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i')})
    .or(main.getByRole('button',{name:new RegExp(id==='gryphy-light'?'Gryphy.*Light':'Obsidian Glow','i')}))
    .or(main.getByRole('option',{name:new RegExp(id==='gryphy-light'?'Gryphy.*Light':'Obsidian Glow','i')}));
  const item=await firstVisible(matches);
  if(!item)throw Error('No visible built-in scheme choice for '+name);
  let access=await tabTo(page,item);
  if(!access.reached){
    const radio=await firstVisible(main.getByRole('radio',{checked:true}));
    if(radio && (await tabTo(page,radio)).reached) {
      for(let i=0;i<64;i++){await page.keyboard.press('ArrowRight');if(await item.evaluate(e=>e===document.activeElement)){access={reached:true,arrows:i+1};break;}}
    }
  }
  if(!access.reached)throw Error('Built-in choice unreachable from keyboard');
  await page.keyboard.press(await item.evaluate(e=>e.matches('input[type=radio],[role=radio]'))?'Space':'Enter');
  return {mechanism:'named control',label:name,access};
}
async function savedScheme(page) {
  return page.evaluate(async()=>{
    const store=await import('/js/storage/indexedDbStorage.js');
    const prefs=JSON.parse(await store.getJson('preferences/colorSchemes'));
    return prefs?.selectedSchemeId ?? prefs?.SelectedSchemeId ?? null;
  });
}
async function settledFocus(locator) {
  const observations=[];
  for(let n=0;n<10;n++){
    await delay(80);const current=await focusEvidence(locator);observations.push(current);
    if(n>=3 && current.active && current.hit && current.top>=-1 && current.bottom<=current.viewportHeight+1 &&
      observations.slice(-3).every(x=>Math.abs(x.top-current.top)<=1))break;
  }
  return {first:observations[0],last:observations.at(-1),samples:observations.length};
}
function readableFocus(e) {
  return e.active&&e.hit&&e.top>=-1&&e.bottom<=e.viewportHeight+1;
}
async function hydrated(page){
  await page.getByRole('heading',{level:1,name:'Data handling'}).waitFor({timeout:60000});
  await page.evaluate(()=>document.fonts.ready);
  await afterFrames(page);
}
async function entryView(page, main, nav) {
  const box = el => el.evaluate(element => {
    const rect = element.getBoundingClientRect();
    const header = document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0;
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    const painted = element.checkVisibility({opacityProperty: true, visibilityProperty: true});
    return {label: element.textContent.trim(), top: rect.top, bottom: rect.bottom,
      fullyVisible: painted && rect.top >= header && rect.bottom <= innerHeight && rect.left >= 0 &&
        rect.right <= innerWidth && element.contains(hit)};
  });
  const links = [];
  if(nav) for (const label of targets) {
    const item = await firstVisible(buttonOrLink(nav, new RegExp(label, 'i')));
    if (item) links.push(await box(item));
  }
  return {scrollY: await page.evaluate(() => scrollY), title: await box(main.getByRole('heading', {level: 1})), links};
}
async function readingRoom(heading) {
  await settledFocus(heading);
  return heading.evaluate(el => {
    const header = document.querySelector('.topbar')?.getBoundingClientRect().bottom || 0;
    const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_ELEMENT);
    walker.currentNode = el;
    let para;
    for (let next = walker.nextNode(); next; next = walker.nextNode()) {
      if (next.tagName === 'P') { para = next; break; }
      if (/^H[12]$/.test(next.tagName)) break;
    }
    if (!para) return {heading: el.textContent.trim(), focused: el === document.activeElement, paragraph: null};
    const r = para.getBoundingClientRect();
    const visible = para.checkVisibility({opacityProperty: true, visibilityProperty: true});
    const px = visible ? Math.max(0, Math.min(innerHeight, r.bottom) - Math.max(header, r.top)) : 0;
    return {heading: el.textContent.trim(), focused: el === document.activeElement, activeId: document.activeElement.id,
      focusVisible: el.matches(':focus-visible'), headingTop: el.getBoundingClientRect().top,
      toolbarBottom: header, paragraphTop: r.top, paragraphHeight: r.height, paragraphVisiblePx: px,
      paragraphVisibleFraction: r.height ? px / r.height : null,
      roomBelowParagraphStart: Math.max(0, innerHeight - Math.max(header, r.top))};
  });
}
function showsParagraphStart(room) {
  return room && room.paragraphVisiblePx > 0 && room.paragraphTop >= room.toolbarBottom - 1;
}
async function cell(browser,id,width,textScale) {
  const row={id,width,textScale,checks:{},diagnostics:{},failed:[]},check=(key,ok,details)=>{row.checks[key]={pass:Boolean(ok),details};if(!ok)row.failed.push(key);};
  const context=await browser.newContext({viewport:{width,height:900},deviceScaleFactor:1,serviceWorkers:'block',reducedMotion:'reduce'});
  const external=new Set(),pageErrors=[],requestErrors=[];
  context.setDefaultTimeout(3500);
  await context.route('**/*',async route=>{
    const u=new URL(route.request().url());
    if(u.origin!==origin){external.add(u.origin+u.pathname);return route.abort();}
    if(u.pathname==='/__privacy_qualification_seed')return route.fulfill({contentType:'text/html',body:'<!doctype html><script src="/js/colorSchemes.js"></script>'});
    return route.continue();
  });
  await context.routeWebSocket('**/*',socket=>{external.add('WebSocket '+socket.url());socket.close();});
  const page=await context.newPage();page.on('pageerror',e=>pageErrors.push(shortError(e)));
  page.on('response',r=>{if(r.status()>=400)requestErrors.push({status:r.status(),path:new URL(r.url()).pathname})});
  const main=page.getByRole('main');
  try{
    await page.goto(origin+'/__privacy_qualification_seed');
    await page.evaluate(s=>HabiticaColorScheme.applyAndStore(s,{selectedSchemeId:s.id,schemaVersion:2,customSchemes:[]}),catalog[id]);
    await page.goto(origin+'/privacy',{waitUntil:'domcontentloaded'});await hydrated(page);
    await page.evaluate(scale=>document.documentElement.style.fontSize=scale===200?'32px':'16px',textScale);await afterFrames(page);
    const snapshot=await appearance(page);check('realPaletteAndText',actualPalette(snapshot,id)&&snapshot.fontSize===16*textScale/100,snapshot);
    const copy=await integrity(main);check('originalCopy',copy.intro&&!copy.errors.length,copy);
    row.diagnostics.closedGeometry=await routeGeometry(main);
    check('closedRouteReflow',!row.diagnostics.closedGeometry.routeOverflow.length,row.diagnostics.closedGeometry.routeOverflow);
    const navs=main.getByRole('navigation',{name:/.+/});
    let nav;
    for(const n of await navs.all())if(await n.isVisible()&&await buttonOrLink(n,/Personal Notes/i).count()){nav=n;break;}
    const entry = await entryView(page,main,nav);
    row.diagnostics.entryView = entry;
    check('visibleEntryShortcuts', entry.title.fullyVisible && entry.links.length === targets.length &&
      entry.links.every(link => link.fullyVisible), entry);
    const orderCorrect=nav && await nav.evaluate((n,title)=>{const h=[...document.querySelectorAll('main h2')].find(e=>e.textContent.trim()===title);return h&&Boolean(n.compareDocumentPosition(h)&Node.DOCUMENT_POSITION_FOLLOWING)},groups[0].heading);
    check('namedNavigationBeforeSections',Boolean(nav&&orderCorrect));
    const controls=[];
    for(const label of targets){
      const item=nav&&await firstVisible(buttonOrLink(nav,new RegExp(label,'i')));
      const key='jump '+label;
      if(!item){check(key,false,'No named jump in a labelled navigation landmark');continue;}
      const access=await tabTo(page,item);
      const before=await focusEvidence(item);
      await page.keyboard.press('Enter');
      const heading=main.getByRole('heading',{name:label,exact:true,level:2});
      await heading.evaluate(e=>new Promise(r=>{let frames=0;function tick(){if(e===document.activeElement||frames++>=50)return r();requestAnimationFrame(tick)}tick()}));
      await afterFrames(page);
      const early=await focusEvidence(heading);
      const t=Date.now(), settled=await settledFocus(heading), after=settled.last;
      const readable=after.top>=-1&&after.bottom<=after.viewportHeight+1&&after.hit;
      check(key,access.reached&&after.active&&readable,{access,before,early,after,readable,samples:settled.samples,observationMs:Date.now()-t});
      if(label==='Personal Notes') row.diagnostics.notesRoom=await readingRoom(heading);
      controls.push([label,item]);
    }
    check('personalNotesReadable', showsParagraphStart(row.diagnostics.notesRoom), row.diagnostics.notesRoom);
    const toggle=await firstVisible(main.getByRole('button',{name:/Reading appearance/i}).or(main.locator('summary').filter({hasText:/Reading appearance/i})));
    check('startsCollapsed',toggle&&await stateOf(toggle)===false);
    if(screenshotDir && id==='gryphy-light' && width===360 && textScale===100){
      const anchor=nav||main.getByRole('heading',{level:1});await anchor.evaluate(e=>e.scrollIntoView({block:'center'}));
      await page.screenshot({path:path.join(screenshotDir,'light-phone.png')});
    }
    if(toggle)controls.push(['Reading appearance',toggle]);
    row.diagnostics.controlContrast={};
    for(const [label,item] of controls)row.diagnostics.controlContrast[label]=await contrast(item);
    check('sampledControlContrast',controls.length===targets.length+1 &&
      Object.values(row.diagnostics.controlContrast).every(s=>s && s.minimum>=s.threshold),row.diagnostics.controlContrast);
    if(toggle){
      const access=await tabTo(page,toggle);
      const before=await focusEvidence(toggle);
      await page.keyboard.press('Enter');await afterFrames(page);
      const opened=await stateOf(toggle);
      check('openWithKeyboard',access.reached&&opened===true,{access,before});
      row.diagnostics.openGeometry=await routeGeometry(main);
      check('openRouteReflow',!row.diagnostics.openGeometry.routeOverflow.length,row.diagnostics.openGeometry.routeOverflow);
      const authoring=await main.locator('input[type=color],textarea,input[type=text],button,[role=button],a').evaluateAll(items=>items.filter(e=>e.checkVisibility({contentVisibilityAuto:true})&&e.getClientRects().length && (!e.closest('details') || e.closest('details').open)).filter(e=>e.matches('input[type=color],textarea,input[type=text]')||/\b(custom|import|export|random|editor|paste)\b/i.test((e.getAttribute('aria-label')||'')+' '+e.textContent)).map(e=>e.tagName+' '+e.textContent.trim().slice(0,60)));
      check('noCustomEditor',authoring.length===0,authoring);
      const pick=await firstVisible(main.getByRole('combobox').or(main.getByRole('listbox')).or(main.getByRole('radio')).or(main.getByRole('button',{name:/Gryphy|Obsidian Glow/i})));
      const chooserContrast = pick ? await contrast(pick) : null;
      row.diagnostics.chooserContrast = chooserContrast;
      check('chooserTextContrast', chooserContrast && chooserContrast.minimum >= chooserContrast.threshold, chooserContrast);
      if(screenshotDir && id==='obsidian-glow' && width===1280 && textScale===200){
        await toggle.evaluate(e=>e.scrollIntoView({block:'center'}));await page.screenshot({path:path.join(screenshotDir,'dark-desktop-enlarged.png')});
      }
      const next=schemes.find(s=>s!==id);
      try{
        const action=await chooseScheme(main,page,next);
        await page.waitForFunction(expected=>document.documentElement.dataset.colorScheme===expected,next,{timeout:3500}).catch(()=>{});
        const selected=await appearance(page);selected.indexedDB=await savedScheme(page);
        check('selectBuiltInInPlace',actualPalette(selected,next)&&selected.saved===next&&selected.indexedDB===next&&selected.bg!==snapshot.bg&&selected.headingColor!==snapshot.headingColor&&new URL(page.url()).pathname==='/privacy',{action,selected});
      }catch(e){check('selectBuiltInInPlace',false,shortError(e));}
      if(await stateOf(toggle)===true){
        const back=await tabTo(page,toggle,'Shift+Tab');
        await page.keyboard.press('Enter');await afterFrames(page);
        const focus=await settledFocus(toggle);
        check('closeAndReturnFocus',back.reached&&await stateOf(toggle)===false&&readableFocus(focus.last),{back,focus});
      }else{
        const focus=await focusEvidence(toggle);check('closeAndReturnFocus',await stateOf(toggle)===false&&focus.active&&focus.hit,{autoClosed:true,focus});
      }
      await page.reload({waitUntil:'domcontentloaded'});await hydrated(page);
      const reloaded=await appearance(page);reloaded.indexedDB=await savedScheme(page);
      check('reloadPersistsSelection',actualPalette(reloaded,next)&&reloaded.saved===next&&reloaded.indexedDB===next,reloaded);
      // Fresh user flow, including the original matrix scale. No screenshot or programmatic scroll precedes it.
      await page.evaluate(s=>document.documentElement.style.fontSize=s===200?'32px':'16px',textScale);
      const fromTop=await tabTo(page,toggle);
      if(fromTop.reached && await stateOf(toggle)===false){await page.keyboard.press('Enter');await afterFrames(page);}
      const resume=await firstVisible(buttonOrLink(main,/Return to reading/i));
      if(resume){
        const via=await tabTo(page,resume);await page.keyboard.press('Enter');
        const firstSection=main.getByRole('heading',{level:2,name:groups[0].heading,exact:true});
        const focus=await settledFocus(firstSection);
        row.diagnostics.returnRoom=await readingRoom(firstSection);
        check('explicitReturnToFirstSection',fromTop.reached&&via.reached&&readableFocus(focus.last),
          {fromTop,via,focus,appearanceClosed:await stateOf(toggle)===false});
      }else{
        check('explicitReturnToFirstSection', false, 'Return to reading control unavailable');
      }
    }else{
      for(const key of ['openWithKeyboard','openRouteReflow','noCustomEditor','chooserTextContrast','selectBuiltInInPlace','closeAndReturnFocus','reloadPersistsSelection','explicitReturnToFirstSection'])check(key,false,'Reading appearance unavailable');
      if(screenshotDir && id==='obsidian-glow' && width===1280 && textScale===200)await page.screenshot({path:path.join(screenshotDir,'dark-desktop-enlarged.png')});
    }
    check('returnSectionReadable', showsParagraphStart(row.diagnostics.returnRoom), row.diagnostics.returnRoom);
    check('blazorHealthy',!pageErrors.length&&!await page.locator('#blazor-error-ui').isVisible(),pageErrors);
  }catch(e){check('runnerCompleted',false,shortError(e));}
  finally{
    row.diagnostics.blockedExternal=[...external];row.diagnostics.httpErrors=requestErrors;
    check('noExternalRequests',!external.size,[...external]);
    await context.close();
  }
  return row;
}
(async()=>{
  if(screenshotDir)fs.mkdirSync(screenshotDir,{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-background-networking']});
  report.browser=browser.version();report.playwright=require(path.join(path.dirname(require.resolve(moduleName)),'package.json')).version;
  try{for(const id of schemes)for(const width of [360,1280])for(const scale of [100,200]){
    const row=await cell(browser,id,width,scale);report.rows.push(row);
    console.log([id,width,scale,row.failed.length?'FAIL '+row.failed.join(' | '):'PASS'].join(' '));
  }}finally{await browser.close();}
  report.summary={cells:report.rows.length,passed:report.rows.filter(r=>!r.failed.length).length,failed:report.rows.filter(r=>r.failed.length).length};
  fs.mkdirSync(path.dirname(path.resolve(outFile)),{recursive:true});fs.writeFileSync(outFile,JSON.stringify(report,null,2)+'\n');
  if(report.summary.failed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=2;});
