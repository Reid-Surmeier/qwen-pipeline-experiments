"""Keep supplied panels intact; key only the notification's magenta backing."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np
from PIL import Image

R=Path(__file__).resolve().parent
out=R/'godot/assets/desktop';out.mkdir(exist_ok=True)
records=[]
for name in ['minimap','itinerary','chat','notification']:
 source=R/'reference/desktop'/f'{name}.png';target=out/source.name
 im=Image.open(source).convert('RGBA');a=np.array(im)
 if name=='notification':
  rgb=a[:,:,:3].astype(float)
  spill=np.minimum(rgb[:,:,0],rgb[:,:,2])-rgb[:,:,1]
  key=spill>20
  alpha=np.clip(1-spill/255,0,1)
  recovered=(rgb-(1-alpha[:,:,None])*[255,0,255])/np.maximum(alpha[:,:,None],1/255)
  a[key,:3]=np.clip(np.rint(recovered[key]),0,255).astype('uint8')
  a[key,3]=np.rint(alpha[key]*255).astype('uint8')
  Image.fromarray(a).save(target)
  assert a[0,0,3]==0 and np.count_nonzero(a[:,:,3]==0)>100000
  visible=a[:,:,3]>0
  clean=a[:,:,:3].astype(int)
  assert not np.any(visible & (clean[:,:,0]-clean[:,:,1]>30) & (clean[:,:,2]-clean[:,:,1]>30))
  opaque=a[:,:,3]==255
  assert np.array_equal(a[opaque],np.array(im)[opaque])
 else:shutil.copyfile(source,target)
 records.append({'id':name,'source':str(source.relative_to(R)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output':str(target.relative_to(R)),'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':list(im.size),'processing':'Magenta alpha matte with spill removal; opaque pixels unchanged' if name=='notification' else 'Byte-identical copy','transparent_pixels':int(np.count_nonzero(a[:,:,3]==0))})
(R/'reference/desktop/assets.json').write_text(json.dumps({'classification':'User source references and deterministic prototype assets','generation_count':0,'panels':records},indent=2)+'\n')
print('PASS four panel assets; notification backing is transparent')
