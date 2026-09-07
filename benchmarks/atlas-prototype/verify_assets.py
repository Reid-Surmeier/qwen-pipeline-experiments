"""Small runnable acceptance check for the prototype's artwork and hosted files."""
from pathlib import Path
import hashlib,json,urllib.request,zipfile
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;A=R/'godot/assets';source=R.parent/'regional/pink-cyan-v001'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
atlas=json.loads((R/'godot/atlas.json').read_text());assert len(atlas['regions'])==10
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
ledger=json.loads((R/'generation/ledger.json').read_text());assert all(r['status']=='completed' for r in ledger['requests']);assert sum(r['requested_n'] for r in ledger['requests'])<=10
url='https://windows-wsl.taile06c45.ts.net/pixel-atlas-prototype-01a07820/'
served=[]
for file in ['index.html','index.js','index.pck','index.wasm']:
 with urllib.request.urlopen(url+file,timeout=60) as response:
  assert response.status==200;assert hashlib.sha256(response.read()).hexdigest()==sha(R/'web'/file)
 served.append(file)
for file in ['desktop-check.json','mobile-check.json']:
 assert json.loads((R/'evidence/play'/file).read_text())['status']=='pass'
result={'status':'pass','regions':10,'europe_city_count':47,'unchanged_badges':badges,'other_full_sheets_byte_identical':9,'europe_pixels_changed_outside_mask':0,'complete_terrain_pixels':int(terrain.shape[0]*terrain.shape[1]),'served_files_hash_verified':served,'additional_generations':sum(r['completed_n'] for r in ledger['requests']),'actual_cost_usd':sum(r['actual_cost_usd'] for r in ledger['requests']),'url':url}
(R/'evidence/acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
