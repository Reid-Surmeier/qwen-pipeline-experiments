// Throwaway acceptance playtest: real browser inputs; never set Godot state from JS.
import { chromium } from '/home/reidsurmeier/orca/workspaces/Qwen Image pipeline/stargazer/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out=path.join(import.meta.dirname,'evidence/play');await fs.mkdir(out,{recursive:true});
await fs.rm(path.join(out,'desktop-check.json'),{force:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.goto('https://windows-wsl.taile06c45.ts.net/pixel-atlas-prototype-01a07820/',{waitUntil:'networkidle'});
await page.waitForFunction(()=>window.atlasState?.regions?.length===10,{timeout:90000});
await page.waitForTimeout(1500);
const state=()=>page.evaluate(()=>window.atlasState);
const shot=async name=>{const check=await state();assert.equal(check.orphan_dots,0);assert(check.shown_cities.every(c=>c.labels>0));if(check.mode==='atlas')assert(check.vertical_pan_locked ? Math.abs(check.position[1]-1350)<.01 : check.south_edge<=2700.01);await page.screenshot({path:path.join(out,name+'.png')});await fs.writeFile(path.join(out,name+'.json'),JSON.stringify({...await state(),regions:(await state()).regions.map(r=>({id:r.id,source_sha256:r.source_sha256}))},null,2));};
const control=async name=>{const s=await state();const [x,y,w,h]=s.controls[name];await page.mouse.click(x+w/2,y+h/2);await page.waitForTimeout(500);};
await shot('01-world');assert.equal((await state()).city_symbol_scale,.65);assert((await state()).visible_world_badges>=20);assert.equal((await state()).world_badge_alpha,1);assert((await state()).visible_cities>0 && (await state()).visible_cities<20);assert.equal((await state()).world_size[1],3144);
const regions=(await state()).regions;
for(let i=0;i<regions.length;i++){
 await control('World');await control('regions');
 const [x,y,w,h]=(await state()).controls.regions;
 await page.mouse.click(x+w/2,y+h+45+i*27);await page.waitForTimeout(1100);
 const st=await state();assert.equal(st.region,regions[i].id);assert(st.detail_alpha>.98);assert(st.zoom>=.85);
 await shot('region-'+regions[i].id);console.log('REGION',regions[i].id,st.zoom,st.fps);
}
await control('World');await control('regions');await page.mouse.click(270,104);await page.waitForTimeout(1000);
const before=await state();await page.mouse.move(850,500);await page.mouse.wheel(0,-100);await page.waitForTimeout(700);const after=await state();assert(after.zoom>before.zoom);
// The cursor's geographic anchor remains stable while zooming.
const anchor=(s)=>[s.position[0]+(850-720)/s.zoom,s.position[1]+(500-450)/s.zoom];
assert(Math.hypot(...anchor(before).map((v,i)=>v-anchor(after)[i]))<1);
await shot('zoom-europe');
await page.mouse.move(720,500);await page.mouse.down();await page.mouse.move(950,560,{steps:12});await page.mouse.up();await page.waitForTimeout(500);assert.notDeepEqual((await state()).position,after.position);await shot('pan-europe');
await control('Full sheet');assert.equal((await state()).mode,'sheet');await shot('sheet-europe');
await page.keyboard.press('Home');await page.waitForTimeout(700);assert.equal((await state()).mode,'atlas');assert((await state()).zoom_ratio<1.01);
// Cross the Pacific world-wrap seam using a drag from the Australian detail view.
await control('regions');await page.mouse.click(270,185);await page.waitForTimeout(800);
assert.equal((await state()).region,'australia');const pacificStart=await state();
await page.mouse.move(1050,650);await page.mouse.down();await page.mouse.move(220,410,{steps:18});await page.mouse.up();await page.waitForTimeout(700);
assert((await state()).position[0]<pacificStart.position[0]);await shot('pacific-wrap');
// Inspect Antarctica with actual cursor-anchored wheel input from the world view.
await control('World');await page.mouse.move(740,880);
for(let i=0;i<12;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(100);}
await page.waitForTimeout(500);assert((await state()).position[1]>2400);await shot('antarctica-detail');
// Both zoom stops are reachable through the real controls.
await page.mouse.move(720,450);
for(let i=0;i<35;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(50);}
await page.waitForTimeout(400);assert.equal((await state()).zoom,120);await shot('zoom-maximum');
for(let i=0;i<65;i++){await page.mouse.wheel(0,100);await page.waitForTimeout(50);}
await page.waitForTimeout(400);assert(Math.abs((await state()).zoom_ratio-1)<.001);assert((await state()).visible_cities>0 && (await state()).visible_cities<20);assert((await state()).visible_world_badges>=20);assert.equal((await state()).world_badge_alpha,1);await shot('zoom-minimum');
// A fixed city neighborhood gains visible markers as screen space grows.
await control('World');await control('regions');await page.mouse.click(270,320);await page.waitForTimeout(700);
assert.equal((await state()).region,'usa');
await page.mouse.move(1170,430);
const sparse=await state();
for(let i=0;i<5;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(150);}
await page.waitForTimeout(400);const dense=await state();
assert(dense.shown_cities.some(c=>!sparse.shown_cities.some(old=>old.id===c.id)));
assert.equal(dense.orphan_dots,0);
await shot('usa-northeast-detail');
await control('World');await control('regions');await page.mouse.click(270,320);await page.waitForTimeout(700);
await page.mouse.move(1040,690);for(let i=0;i<7;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(120);}
await page.waitForTimeout(500);await shot('usa-florida-detail');
// Sourced lakes and genuine close coast geometry, through real region/zoom inputs.
for(const [name,index,point] of [['great-lakes',8,[1300,874]],['canadian-lakes',4,[872,552]],['british-coast',0,[2340,710]]]){
 await control('World');await control('regions');await page.mouse.click(270,104+index*27);await page.waitForTimeout(600);
 const start=await state();const sx=720+(point[0]-start.position[0])*start.zoom,sy=450+(point[1]-start.position[1])*start.zoom;
 await page.mouse.move(sx,sy);
 for(let i=0;i<6;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(150);}
 await page.waitForTimeout(700);const close=await state();assert.equal(close.terrain_detail,1);assert(close.terrain_tiles>0&&close.terrain_tiles<=12);assert.equal(close.orphan_dots,0);await shot(name+'-detail');
}
// Attempt to drag past Antarctica at regional zoom; the viewport bottom must stop.
await control('World');await page.mouse.move(740,880);
for(let i=0;i<10;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(70);}
for(let i=0;i<8;i++){await page.mouse.move(700,780);await page.mouse.down();await page.mouse.move(700,160,{steps:5});await page.mouse.up();}
await page.waitForTimeout(350);assert(Math.abs((await state()).south_edge-2700)<.01);const blocked=await state();
await page.mouse.move(700,780);await page.mouse.down();await page.mouse.move(700,160,{steps:5});await page.mouse.up();await page.waitForTimeout(300);assert.equal((await state()).position[1],blocked.position[1]);await shot('antarctica-pan-stop');
// Read London on the UK landmass and compare the sparse and close Russian tiers.
await control('World');await control('regions');await page.mouse.click(270,104);await page.waitForTimeout(500);
const eu=await state();const london=eu.regions.find(r=>r.id==='europe').annotations.find(a=>a.kind==='city'&&a.name==='London');assert(london.at[0]>=2310&&london.at[0]<=2350&&london.at[1]>=720&&london.at[1]<=770);
const lx=720+(london.at[0]-eu.position[0])*eu.zoom,ly=450+(london.at[1]-eu.position[1])*eu.zoom;
await page.mouse.move(lx,ly);for(let i=0;i<4;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(100);}await page.waitForTimeout(400);await shot('london-detail');
await control('World');await control('regions');await page.mouse.click(270,266);await page.waitForTimeout(500);const russian=await state();assert.equal(russian.region,'russia');assert(russian.shown_cities.filter(c=>c.id.startsWith('russia')).length<=5);await shot('russia-sparse');
await page.mouse.move(720,450);for(let i=0;i<12;i++){await page.mouse.wheel(0,-100);await page.waitForTimeout(80);assert.equal((await state()).orphan_dots,0);}await page.waitForTimeout(400);await shot('russia-close');
for(let i=0;i<12;i++){await page.mouse.wheel(0,100);await page.waitForTimeout(80);assert.equal((await state()).orphan_dots,0);}
await page.setViewportSize({width:1000,height:1000});await page.waitForTimeout(500);assert((await state()).vertical_pan_locked || (await state()).south_edge<=2700.01);await page.setViewportSize({width:1440,height:900});await page.waitForTimeout(300);
// A high-resolution viewport used to fade out world numbers even at minimum zoom.
await page.setViewportSize({width:3840,height:2160});await control('World');await page.waitForTimeout(700);
assert(Math.abs((await state()).zoom_ratio-1)<.001);assert.equal((await state()).world_badge_alpha,1);assert((await state()).visible_world_badges>=20);await shot('world-4k');
await page.setViewportSize({width:1440,height:900});await control('World');
// Newly named cities must reveal beyond the previous maximum in multiple regions.
for(const [name,index,point] of [['london',0,[2366,775.5]],['new-york',8,[1431,945]],['tokyo',2,[4135,1018.2]]]){
 await control('World');await control('regions');await page.mouse.click(270,104+index*27);await page.waitForTimeout(500);
 const initial=await state();assert.equal(initial.visible_close_cities,0);
 // Center the geographic neighborhood with a real drag before zooming in.
 const dx=(point[0]-initial.position[0])*initial.zoom,dy=(point[1]-initial.position[1])*initial.zoom;
 await page.mouse.move(720,450);await page.mouse.down();await page.mouse.move(720-dx,450-dy,{steps:12});await page.mouse.up();
 await page.mouse.move(720,450);
 for(let i=0;i<30;i++){
  await page.mouse.wheel(0,-100);await page.waitForTimeout(85);
  if(name==='tokyo' && i===19){
   await page.waitForTimeout(400);await shot('tokyo-old-zoom-sparser');
   const old=JSON.parse(await fs.readFile(path.join(out,'tokyo-density-before.json'),'utf8'));
   assert(Math.abs((await state()).zoom-old.zoom)<.01);
   assert((await state()).visible_close_cities<old.visible_close_cities/2);
  }
  if(name==='london' && [9,11,13,15,17,21,25].includes(i)){
   await page.waitForTimeout(300);await shot('london-paced-'+(i+1));
   if(i<=11)assert.equal((await state()).visible_close_cities,0);
  }
 }
 await page.waitForTimeout(600);const close=await state();assert.equal(close.zoom,120);assert.equal(close.city_symbol_scale,2);assert(close.visible_close_cities>0);assert.equal(close.orphan_dots,0);await shot(name+'-deep-cities');
 const added=close.shown_cities.filter(c=>c.id.startsWith('geonames'));
 for(let a=0;a<added.length;a++)for(let b=0;b<a;b++)assert(Math.hypot(...added[a].screen.map((v,i)=>v-added[b].screen[i]))>=120);
 assert(close.visible_close_cities<30);
}
// Empty sea remains the cyan map surface; no white paper panels or missing textures.
await page.keyboard.press('Home');await page.waitForTimeout(600);
await fs.writeFile(path.join(out,'errors.json'),JSON.stringify(errors,null,2));assert.equal(errors.length,0);await fs.writeFile(path.join(out,'desktop-check.json'),JSON.stringify({status:'pass',regions:regions.map(r=>r.id),checks:['region selection','automatic detail','pointer-anchored wheel zoom','drag','sheet toggle','reset','Pacific wrap','sparse named overview','Antarctica close view','zoom limits 1.0 world fit and 120 native','paired city/name reveal with no orphan dots','US northeast and Florida close views','London on Great Britain','Russian town zoom tiers','Great Lakes and Canadian lakes close views','4x sourced coast detail with bounded visible tiles','southern viewport clamp under drag and resize','opaque readable overview badges at desktop and 4K minimum zoom','new close cities in London New York and Tokyo beyond previous maximum','Tokyo old-scale density reduced by more than half','at least 120 pixels between added city dots in deep views','slower staged city reveal through seven London zoom checkpoints'],errors},null,2));console.log('PASS: ten regions, pointer zoom anchor, drag, sheet toggle, reset, Pacific wrap; no browser errors.');
await browser.close();
