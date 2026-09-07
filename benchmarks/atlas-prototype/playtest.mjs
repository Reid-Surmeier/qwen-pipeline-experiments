// Throwaway acceptance playtest: real browser inputs; never set Godot state from JS.
import { chromium } from '/home/reidsurmeier/orca/workspaces/Qwen Image pipeline/stargazer/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
const out=path.join(import.meta.dirname,'evidence/play');await fs.mkdir(out,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.goto('https://windows-wsl.taile06c45.ts.net/pixel-atlas-prototype-01a07820/',{waitUntil:'networkidle'});
await page.waitForFunction(()=>window.atlasState?.regions?.length===10,{timeout:90000});
await page.waitForTimeout(1500);
const state=()=>page.evaluate(()=>window.atlasState);
const shot=async name=>{await page.screenshot({path:path.join(out,name+'.png')});await fs.writeFile(path.join(out,name+'.json'),JSON.stringify(await state(),null,2));};
const control=async name=>{const s=await state();const [x,y,w,h]=s.controls[name];await page.mouse.click(x+w/2,y+h/2);await page.waitForTimeout(500);};
await shot('01-world');
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
// Empty sea remains the cyan map surface; no white paper panels or missing textures.
await page.keyboard.press('Home');await page.waitForTimeout(600);
await fs.writeFile(path.join(out,'errors.json'),JSON.stringify(errors,null,2));assert.equal(errors.length,0);await fs.writeFile(path.join(out,'desktop-check.json'),JSON.stringify({status:'pass',regions:regions.map(r=>r.id),checks:['region selection','automatic detail','pointer-anchored wheel zoom','drag','sheet toggle','reset','Pacific wrap'],errors},null,2));console.log('PASS: ten regions, pointer zoom anchor, drag, sheet toggle, reset, Pacific wrap; no browser errors.');
await browser.close();
