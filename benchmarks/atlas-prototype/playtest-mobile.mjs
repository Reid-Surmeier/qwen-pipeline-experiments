// Real CDP touch gestures against the exported Godot canvas.
import {mapPage} from './window-playtest.mjs';
import { chromium } from '/home/reidsurmeier/orca/workspaces/Qwen Image pipeline/stargazer/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';import path from 'node:path';import assert from 'node:assert/strict';
const out=path.join(import.meta.dirname,'evidence/play');
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-webgl','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:1});const rawPage=await context.newPage();const page=await mapPage(rawPage);const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error')errors.push(m.text());});
await page.goto('https://windows-wsl.taile06c45.ts.net/pixel-atlas-prototype-01a07820/',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.atlasState?.regions?.length===10,{timeout:90000});await page.waitForTimeout(1000);
const state=()=>page.evaluate(()=>({...window.atlasState,window:window.atlasWindow}));const shot=async n=>{await page.screenshot({path:path.join(out,n+'.png')});await fs.writeFile(path.join(out,n+'.json'),JSON.stringify({...await state(),regions:(await state()).regions.map(r=>({id:r.id,source_sha256:r.source_sha256}))},null,2));};
let st=await state();assert.equal(st.viewport[0],334);assert(st.visible_cities>0 && st.visible_cities<15);assert.equal(st.orphan_dots,0);assert(st.vertical_pan_locked || st.south_edge<=2700.01);for(const rect of Object.values(st.controls))assert(rect[0]+rect[2]<=390,JSON.stringify(rect));assert(st.visible_world_badges>0);assert.equal(st.world_badge_alpha,1);await shot('mobile-world');
const tap=async key=>{const [x,y,w,h]=(await state()).controls[key];await page.touchscreen.tap(x+w/2,y+h/2);await page.waitForTimeout(400);};
await tap('regions');await page.touchscreen.tap(130,104);await page.waitForTimeout(900);assert.equal((await state()).region,'europe');assert((await state()).detail_alpha>.98);await shot('mobile-europe');
const cdp=await context.newCDPSession(rawPage);const points=(a,b)=>[{x:a+28,y:508,id:0},{x:b+28,y:508,id:1}];const start=await state();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points(140,240)});
for(let i=1;i<=5;i++){await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:points(140-i*10,240+i*10)});await page.waitForTimeout(80);}
await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(500);assert((await state()).zoom>start.zoom*1.5);await shot('mobile-pinch');
const pan=await state();await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:228,y:568,id:0}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:308,y:628,id:0}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(500);assert.notDeepEqual((await state()).position,pan.position);assert.equal((await state()).touches,0);assert.equal((await state()).orphan_dots,0);assert((await state()).vertical_pan_locked || (await state()).south_edge<=2700.01);
for(let i=0;i<3;i++)await tap('+');assert.equal((await state()).terrain_detail,1);assert((await state()).terrain_tiles>0);await shot('mobile-coast-detail');
// Center a known nearby place before the very small phone viewport reaches maximum zoom.
const neighborhood=await state();
const target=[2514.8,785.5];
const touchStart={x:195,y:442,id:0};
await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touchStart]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:195-(target[0]-neighborhood.position[0])*neighborhood.zoom,y:442-(target[1]-neighborhood.position[1])*neighborhood.zoom,id:0}]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(300);
for(let i=0;i<18;i++)await tap('+');assert.equal((await state()).zoom,120);assert.equal((await state()).city_symbol_scale,2);assert((await state()).visible_close_cities>0);assert.equal((await state()).orphan_dots,0);await shot('mobile-deep-cities');
const frame=await rawPage.evaluate(()=>window.atlasWindow);
await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:frame.position[0]+frame.size[0]-4,y:frame.position[1]+frame.size[1]-4,id:0}]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:frame.position[0]+frame.size[0]-20,y:frame.position[1]+frame.size[1]-84,id:0}]});
await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(500);
assert((await state()).viewport[0]<334);assert.equal((await state()).orphan_dots,0);await shot('mobile-window-resized');
await tap('World');for(let i=0;i<8;i++)await tap('−');assert(Math.abs((await state()).zoom_ratio-1)<.001);assert.equal(errors.length,0);await fs.writeFile(path.join(out,'mobile-check.json'),JSON.stringify({status:'pass',viewport:[390,844],checks:["touch resize of reference window","map input coordinates within the smaller phone viewport",'toolbar fits','region tap','two-finger pinch zoom','one-finger pan','touch release','world reset','120 native zoom stop with newly revealed paired cities'],errors},null,2));console.log('PASS mobile: toolbar, region tap, pinch, pan, release, reset.');await browser.close();
