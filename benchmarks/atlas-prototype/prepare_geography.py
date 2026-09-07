"""Natural Earth geography in the atlas projection; original artwork stays the overview."""
from pathlib import Path
import gzip,json
from functools import lru_cache
import numpy as np
from PIL import Image,ImageDraw
from scipy import ndimage as nd

R=Path(__file__).resolve().parent
PINK=(255,220,233);CYAN=(131,229,247);WHITE=(255,255,255)
WIDTH=4480;HEIGHT=3144;TW=560;TH=524;SCALE=4

def project(points):
 p=np.asarray(points);lon=p[:,0];lat=p[:,1]
 m=1.25*np.log(np.tan(np.pi/4+.4*np.radians(lat)))
 return np.column_stack([((2294.25+lon*12.02)-45)/1.9*2,((1439-687.6*m)-17)/1.915*2])

def area(ring):
 return abs(np.sum(ring[:,0]*np.roll(ring[:,1],1)-ring[:,1]*np.roll(ring[:,0],1)))/2

def polygons(name,clean=True):
 result=[]
 cities=[]
 for file in ['city-catalog.json','usa-cities.json']:
  cities.extend(json.loads((R/'reference'/file).read_text())['cities'])
 anchors=project([[c['lon'],c['lat']] for c in cities])
 def inhabited(ring):
  # Keep city-bearing islands even when the source coordinate sits just off their shore.
  return np.any(np.all((anchors>=ring.min(0)-2)&(anchors<=ring.max(0)+2),1))
 for f in json.loads(gzip.decompress((R/f'reference/ne-10m-{name}.json.gz').read_bytes()))['features']:
  g=f['geometry'];polys=[g['coordinates']] if g['type']=='Polygon' else g['coordinates']
  for rings in polys:
   pts=[project(ring) for ring in rings]
   if clean:
    if name=='land' and area(pts[0])<60 and not inhabited(pts[0]):continue
    if name=='lakes' and (area(pts[0])<100 or (f['properties']['scalerank'] or 0)>2):continue
    pts=[pts[0]]+[p for p in pts[1:] if area(p)>=(100 if name=='land' else 60) or (name=='lakes' and inhabited(p))]
   for shift in [-WIDTH,0,WIDTH]:
    moved=[p+[shift,0] for p in pts];lo=moved[0].min(0);hi=moved[0].max(0)
    if hi[0]>=0 and lo[0]<=WIDTH:result.append((moved,lo,hi,f['properties']))
 return result

def mask(polys,box,scale=1):
 x,y,w,h=box;im=Image.new('1',(round(w*scale),round(h*scale)));draw=ImageDraw.Draw(im)
 for rings,lo,hi,_ in polys:
  if hi[0]<x or hi[1]<y or lo[0]>x+w or lo[1]>y+h:continue
  for i,ring in enumerate(rings):draw.polygon([tuple(p) for p in ((ring-[x,y])*scale)],fill=not i)
 return np.asarray(im,dtype=bool)

def add_overview_lakes(terrain):
 # Use the same major lakes at both levels; omit small lake/island clutter.
 lakes=polygons('lakes')
 water=mask(lakes,(0,0,WIDTH,HEIGHT))
 outline=nd.binary_dilation(water,iterations=8)&~water
 terrain[outline & np.all(terrain==PINK,2)]=WHITE;terrain[water]=CYAN
 return terrain

@lru_cache(maxsize=4)
def tile_land(col,row):
 return np.all(np.array(Image.open(R/f'godot/assets/geography/{col}-{row}.png'))==PINK,2)

def city_anchor(point):
 # Geographic centers on small coastal features may need a sub-pixel land adjustment.
 x,y=point;col=int(x//TW)%8;row=int(y//TH);land=tile_land(col,row)
 px,py=round((x%TW)*SCALE),round((y%TH)*SCALE)
 radius=12*SCALE;x0=max(0,px-radius);y0=max(0,py-radius)
 yy,xx=np.where(land[y0:py+radius+1,x0:px+radius+1])
 if not len(xx):raise ValueError(f'No detail land within 12 world pixels of {point}')
 xx+=x0;yy+=y0;i=np.argmin((xx-px)**2+(yy-py)**2)
 return [col*TW+float(xx[i])/SCALE,row*TH+float(yy[i])/SCALE]

def build():
 land=polygons('land');lakes=polygons('lakes');out=R/'godot/assets/geography';out.mkdir(exist_ok=True)
 records=[]
 # ponytail: one 4× detail level; add another only when closer-than-12× zoom is needed.
 for row in range(6):
  for col in range(8):
   x,y=col*TW,row*TH;pad=10;box=(x-pad,y-pad,TW+2*pad,TH+2*pad)
   ground=mask(land,box,SCALE);water=mask(lakes,box,SCALE)
   land_distance=nd.distance_transform_edt(ground)-nd.distance_transform_edt(~ground)
   lake_distance=nd.distance_transform_edt(water)-nd.distance_transform_edt(~water) if water.any() else np.full(ground.shape,-128)
   # Signed distances preserve fine geometry while Godot holds the close-up stroke at 8 screen pixels.
   field=np.stack([np.clip(128+land_distance,0,255),np.clip(128+lake_distance,0,255),np.zeros(ground.shape)],2).astype('uint8')
   Image.fromarray(field[pad*SCALE:-pad*SCALE,pad*SCALE:-pad*SCALE]).save(out/f'{col}-{row}-field.png')
   coast=(land_distance>=-2*SCALE)&~ground
   lake_coast=(lake_distance>=-2*SCALE)&~water
   a=np.full((*ground.shape,3),CYAN,dtype='uint8');a[coast]=WHITE;a[ground]=PINK
   a[lake_coast & ground]=WHITE;a[water]=CYAN
   a=a[pad*SCALE:-pad*SCALE,pad*SCALE:-pad*SCALE]
   Image.fromarray(a).save(out/f'{col}-{row}.png')
   records.append({'id':f'{col}-{row}','size':[a.shape[1],a.shape[0]]})
  print('detail row',row,flush=True)
 (R/'evidence/geography-detail.json').write_text(json.dumps({'source':'Natural Earth 5.1.2, 1:10m','scale':SCALE,'tile_world_size':[TW,TH],'tiles':records,'white_stroke_screen_pixels':8,'source_lake_features':1355,'retained_land_polygons':len(land),'retained_lake_polygons':len(lakes),'removed_land_polygons':len(polygons('land',False))-len(land),'removed_lake_polygons':len(polygons('lakes',False))-len(lakes),'minimum_land_area':60,'minimum_lake_area':100,'small_city_islands_preserved':True},indent=2)+'\n')

if __name__=='__main__':build()
