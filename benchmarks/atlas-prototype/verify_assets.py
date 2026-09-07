"""Small runnable acceptance check for the prototype's artwork and hosted files."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile,gzip,collections
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;A=R/'godot/assets';source=R.parent/'regional/pink-cyan-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
atlas=json.loads((R/'godot/atlas.json').read_text());assert len(atlas['regions'])==10
world_source=R.parent/'world-map/pink-cyan-v001/preview'
world_badges=json.loads((world_source/'review-v003.json').read_text())['badges']
assert atlas['world_badges']==world_badges and len(world_badges)==29
original_world=np.array(Image.open(world_source/'map-v004-white-coastlines.png').convert('RGB'))
overlay=np.array(Image.open(A/'world-badges.png'))
for badge in world_badges:
 x,y,w,h=badge['rectangle'];assert np.array_equal(original_world[y:y+h,x:x+w],overlay[y:y+h,x:x+w,:3])
badges=0
for region in atlas['regions']:
 name=region['id'];before=source/'preview'/f'{name}-v2.png';after=A/f'{name}.png'
 if name!='europe':assert sha(before)==sha(after)
 old=np.array(Image.open(before).convert('RGB'));new=np.array(Image.open(after).convert('RGB'))
 assert old.shape==new.shape
 review=json.loads((source/'runs'/name/'review.json').read_text())
 for b in review['badges']:
  x,y,w,h=b['rectangle'];assert np.array_equal(old[y:y+h,x:x+w],new[y:y+h,x:x+w]);badges+=1
 assert len(region['annotations'])>10
 for group in region['annotations']:
  assert group['kind'] in ('badge','city','label')
  assert all(np.isfinite(group['at']))
europe=json.loads((R/'evidence/europe-reduction.json').read_text());assert europe['original_count']==94 and len(europe['retained'])==47
old=np.array(Image.open(source/'preview/europe-v2.png').convert('RGB'));new=np.array(Image.open(A/'europe.png').convert('RGB'));mask=np.array(Image.open(R/'evidence/europe-edit-mask.png'),dtype=bool)
assert np.array_equal(old[~mask],new[~mask])
terrain=np.array(Image.open(A/'terrain.png').convert('RGB'));assert set(map(tuple,np.unique(terrain.reshape(-1,3),axis=0)))=={(255,220,233),(131,229,247),(255,255,255)}
assert terrain.shape==(3144,4480,3)
assert np.count_nonzero(np.all(terrain[2400:]==[255,220,233],2))>1000000
usa=next(r for r in atlas['regions'] if r['id']=='usa')
cities=[g for g in usa['annotations'] if g['kind']=='city'];assert len(cities)==89
for g in cities:
 x,y=map(round,g['at']);assert np.all(terrain[y,x]==[255,220,233]),g.get('name')
split_labels=[g for g in usa['annotations'] if g['kind']=='label' and 1700<g['rect'][0]<2070 and 365<g['rect'][1]<398]
assert {g['city_id'] for g in split_labels}=={21,26,93}
assert len(split_labels)==3
catalog=json.loads((R/'reference/city-catalog.json').read_text())
for region in atlas['regions']:
 label_file=f"{region['id']}-labels.png"
 assert sha(A/label_file)==catalog['thin_label_sha256'][label_file]
 for g in region['annotations']:
  if g['kind']=='label':assert any(c['kind']=='city' and c['city_id']==g['city_id'] and c['at']==g['at'] for c in region['annotations'])
for name in ['01-world','mobile-world','zoom-minimum']:
 view=json.loads((R/'evidence/play'/f'{name}.json').read_text());assert 0<view['visible_cities']<20;assert view['orphan_dots']==0
eu=next(r for r in atlas['regions'] if r['id']=='europe')
assert len([g for g in eu['annotations'] if g['kind']=='city'])==47
london=next(g for g in eu['annotations'] if g.get('name')=='London')
assert london['at']==[2333,751]
registered=json.loads((R/'evidence/city-registration.json').read_text())
for city in registered:
 x,y=map(round,city['at']);assert np.all(terrain[y,x]==[255,220,233]),city['name']
for path in (R/'evidence/play').glob('*.json'):
 view=json.loads(path.read_text())
 if isinstance(view,dict) and 'orphan_dots' in view:
  assert view['orphan_dots']==0
  if view['mode']=='atlas':assert (abs(view['position'][1]-1350)<.01 if view['vertical_pan_locked'] else view['south_edge']<=2700.01)
nz=json.loads((R/'evidence/new-zealand-scale.json').read_text());assert nz['target_land_size']==[154,193] and nz['native_white_stroke']==8
ledger=json.loads((R/'generation/ledger.json').read_text());assert all(r['status']=='completed' for r in ledger['requests']);assert sum(r['requested_n'] for r in ledger['requests'])<=10
# Real geographic detail, not an interpolation of the overview texture.
from prepare_geography import project,polygons,tile_land
geo=json.loads((R/'evidence/geography-detail.json').read_text());assert geo['scale']==4 and len(geo['tiles'])==48
assert geo['removed_land_polygons']>6000 and geo['retained_lake_polygons']<=40
assert geo['removed_lake_polygons']>1300
anchors=0
for region in atlas['regions']:
 for city in region['annotations']:
  if city['kind']!='city':continue
  x,y=city['detail_at'];col=int(x//560);row=int(y//524)
  assert tile_land(col,row)[round((y%524)*4),round((x%560)*4)],city['name']
  anchors+=1
lake_points={'Michigan':[-87,44],'Superior':[-87,47.7],'Huron':[-82.5,44.8],'Erie':[-81.5,42.2],'Ontario':[-77.9,43.6],'Great Bear':[-120.5,65.9],'Great Slave':[-113,61.6],'Winnipeg':[-97.5,52.3],'Athabasca':[-109,59.2]}
for name,point in lake_points.items():
 x,y=project([point])[0];assert np.all(terrain[round(y),round(x)]==[131,229,247]),name
 tile=np.array(Image.open(A/f'geography/{int(x//560)}-{int(y//524)}.png'))
 assert np.all(tile[round((y%524)*4),round((x%560)*4)]==[131,229,247]),name
for name in ['great-lakes-detail','canadian-lakes-detail','british-coast-detail','mobile-coast-detail']:
 view=json.loads((R/'evidence/play'/f'{name}.json').read_text());assert view['terrain_detail']==1 and 0<view['terrain_tiles']<=12
for name in ['01-world','zoom-minimum','mobile-world','world-4k']:
 view=json.loads((R/'evidence/play'/f'{name}.json').read_text());assert abs(view['zoom_ratio']-1)<.001 and view['south_edge']<=2700.01
 assert view['world_badge_alpha']==1 and view['visible_world_badges']>0 and view['world_badge_screen_height']==22
close=json.loads((R/'godot/close-cities.json').read_text())
provenance=json.loads(gzip.decompress((R/'reference/close-cities.json.gz').read_bytes()))
assert len(close)==len(provenance['cities'])>30000
known={c['geonameid'] for c in catalog['cities']}|{c['geonameid'] for c in json.loads((R/'reference/usa-cities.json').read_text())['cities']}
assert not known.intersection(c['id'] for c in close)
grouped=collections.defaultdict(list)
for city in close:
 assert city['min_zoom'] in [7,14,24]
 x,y=city['at'];grouped[(int(x//560),int(y//524))].append(city)
for (col,row),cities in grouped.items():
 land=tile_land(col,row)
 for city in cities:
  x,y=city['at'];assert land[round((y%524)*4),round((x%560)*4)],city['name']
beyond_old_max={c['id'] for c in close if c['min_zoom']>12}
for name in ['london-deep-cities','new-york-deep-cities','tokyo-deep-cities','mobile-deep-cities']:
 view=json.loads((R/'evidence/play'/f'{name}.json').read_text());assert view['zoom']>12 and view['visible_close_cities']>0 and view['orphan_dots']==0
 assert any(c['id'].startswith('geonames') and int(float(c['id'].removeprefix('geonames'))) in beyond_old_max for c in view['shown_cities'])
assert json.loads((R/'evidence/play/zoom-maximum.json').read_text())['zoom']==36
assert json.loads((R/'evidence/play/01-world.json').read_text())['visible_close_cities']==0
url='https://windows-wsl.taile06c45.ts.net/pixel-atlas-prototype-01a07820/'
served=[]
for file in ['index.html','index.js','index.pck','index.wasm']:
 with urllib.request.urlopen(url+file,timeout=60) as response:
  assert response.status==200;assert hashlib.sha256(response.read()).hexdigest()==sha(R/'web'/file)
 served.append(file)
for file in ['desktop-check.json','mobile-check.json']:
 assert json.loads((R/'evidence/play'/file).read_text())['status']=='pass'
result={'status':'pass','regions':10,'europe_city_count':47,'us_cities_on_land':89,'overview_city_count':json.loads((R/'evidence/play/01-world.json').read_text())['visible_cities'],'original_thin_labels_restored':10,'named_regional_placements':len(registered),'london_on_great_britain':True,'orphan_dots':0,'southern_pan_stop':True,'antarctica_present':True,'unbounded_polar_fill_removed':True,'detail_city_anchors_on_land':anchors,'sourced_lakes_checked':list(lake_points),'terrain_detail_resolution':4,'geography_tiles':48,'removed_small_land_polygons':geo['removed_land_polygons'],'removed_small_lake_polygons':geo['removed_lake_polygons'],'retained_lake_polygons':geo['retained_lake_polygons'],'overview_badges_visible_at_minimum':True,'additional_close_cities':len(close),'new_maximum_native_zoom':36,'new_zealand_land_size':[154,193],'zoom_range':['1.0 viewport fit','36 native'],'unchanged_badges':badges,'other_full_sheets_byte_identical':9,'europe_pixels_changed_outside_mask':0,'complete_terrain_pixels':int(terrain.shape[0]*terrain.shape[1]),'served_files_hash_verified':served,'additional_generations':sum(r['completed_n'] for r in ledger['requests']),'actual_cost_usd':sum(r['actual_cost_usd'] for r in ledger['requests']),'url':url}
(R/'evidence/acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
