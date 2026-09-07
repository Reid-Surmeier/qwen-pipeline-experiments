// Route existing map-local test inputs through the live window's actual content rect.
export async function mapPage(page) {
 const mouse=page.mouse;
 const at=async(x,y)=>page.evaluate(([x,y])=>[x+window.atlasWindow.map_rect[0],y+window.atlasWindow.map_rect[1]],[x,y]);
 const mappedMouse=new Proxy(mouse,{get(target,key){
  if(['click','dblclick','move'].includes(key))return async(x,y,...args)=>target[key](...await at(x,y),...args);
  return typeof target[key]==='function'?target[key].bind(target):target[key];
 }});
 const touch=page.touchscreen;
 return new Proxy(page,{get(target,key){
  if(key==='mouse')return mappedMouse;
  if(key==='touchscreen')return {tap:async(x,y)=>touch.tap(...await at(x,y))};
  if(key==='setViewportSize')return async({width,height})=>target.setViewportSize({width:width+104,height:height+168});
  return typeof target[key]==='function'?target[key].bind(target):target[key];
 }});
}
