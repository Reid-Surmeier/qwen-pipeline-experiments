"""Additional close-zoom places, using the existing GeoNames extract and retained terrain."""
from pathlib import Path
import collections,gzip,hashlib,json,sys,zipfile
import numpy as np
from prepare_geography import project,tile_land,TW,TH,SCALE

R=Path(__file__).resolve().parent

def build(source):
 known=set()
 for file in ['city-catalog.json','usa-cities.json']:
  known.update(c['geonameid'] for c in json.loads((R/'reference'/file).read_text())['cities'])
 with zipfile.ZipFile(source) as z:
  rows=[r.split('\t') for r in z.read('cities5000.txt').decode().splitlines()]
 grouped=collections.defaultdict(list);skipped=collections.Counter();seen=set()
 for row in sorted(rows,key=lambda r:-int(r[14])):
  ident=int(row[0]);population=int(row[14]);code=row[7]
  if ident in known or population<10000 or not (code=='PPL' or code=='PPLC' or code.startswith('PPLA')):continue
  name=row[2];lon=float(row[5]);lat=float(row[4]);key=(name.casefold(),round(lon,1),round(lat,1))
  if key in seen:continue
  seen.add(key);at=project([[lon,lat]])[0];at[0]%=4480
  if not 0<=at[1]<2700:continue
  grouped[(int(at[0]//TW),int(at[1]//TH))].append((row,at))
 cities=[]
 for (col,row),items in sorted(grouped.items()):
  land=tile_land(col,row)
  for source_row,at in items:
   px,py=np.rint((at-[col*TW,row*TH])*SCALE).astype(int)
   radius=8;x0=max(0,px-radius);y0=max(0,py-radius)
   yy,xx=np.where(land[y0:py+radius+1,x0:px+radius+1])
   if not len(xx):skipped['no_nearby_retained_land']+=1;continue
   xx+=x0;yy+=y0;i=np.argmin((xx-px)**2+(yy-py)**2)
   point=[col*TW+float(xx[i])/SCALE,row*TH+float(yy[i])/SCALE]
   if np.linalg.norm(np.array(point)-at)>2:skipped['coast_adjustment_over_2_pixels']+=1;continue
   population=int(source_row[14])
   cities.append({'id':int(source_row[0]),'name':source_row[2],'country':source_row[8],'lon':float(source_row[5]),'lat':float(source_row[4]),'population':population,'at':point,'min_zoom':7 if population>=250000 else (14 if population>=50000 else 24)})
 cities.sort(key=lambda c:-c['population'])
 provenance={'source':'https://download.geonames.org/export/dump/cities5000.zip','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'license':'GeoNames CC BY 4.0; https://www.geonames.org/','cities':cities}
 (R/'reference/close-cities.json.gz').write_bytes(gzip.compress(json.dumps(provenance,separators=(',',':')).encode(),mtime=0))
 (R/'godot/close-cities.json').write_text(json.dumps([{k:c[k] for k in ['id','name','at','min_zoom','population']} for c in cities],separators=(',',':'))+'\n')
 result={'city_count':len(cities),'tiers':dict(collections.Counter(c['min_zoom'] for c in cities)),'skipped':dict(skipped),'maximum_land_adjustment':2,'font':'PixelMplus12-Regular, reused from existing Godot project; M+ FONT LICENSE','font_sha256':hashlib.sha256((R/'godot/fonts/PixelMplus12-Regular.ttf').read_bytes()).hexdigest()}
 (R/'evidence/close-cities.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':build(Path(sys.argv[1]))
