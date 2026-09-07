"""Check displayed source chrome against real Godot frames, including after resize."""
from pathlib import Path
from PIL import Image,ImageCms
import io,json
import numpy as np

R=Path(__file__).resolve().parent
source=np.array(Image.open(R/'godot/assets/window-frame.png').convert('RGBA'))
reference=Image.open(R/'reference/window-screenshot.png').convert('RGB')
normalized=ImageCms.profileToProfile(reference,ImageCms.ImageCmsProfile(io.BytesIO(reference.info['icc_profile'])),ImageCms.createProfile('sRGB'),outputMode='RGB')
original=np.array(normalized.crop((20,16,1744,1440)))
metadata=json.loads((R/'reference/window-source.json').read_text())
assert metadata['title']['text']=='World map : RISD Collection'
assert metadata['title']['edit_rectangle']==[90,40,750,48]
unchanged=np.ones(source.shape[:2],dtype=bool);unchanged[40:88,90:840]=False
changed=np.any(source[:,:,:3]!=original,axis=2)
assert not np.any(changed & unchanged),'Frame pixels changed outside the title edit'
assert np.count_nonzero(changed)>1000,'Title was not assembled'
checks=[]
for name in ['frame-reference-size','frame-reference-resized','frame-reference-moved']:
 state=json.loads((R/'evidence/play'/f'{name}.json').read_text())['window']
 x,y=map(round,state['position']);w,h=map(round,state['size'])
 actual=np.array(Image.open(R/'evidence/play'/f'{name}.png').convert('RGB'))[y:y+h,x:x+w]
 regions=[('header-title',(0,0,850,94),(0,0)),('header-right',(1624,0,100,94),(w-100,0)),('bottom-left',(0,1362,56,62),(0,h-62)),('bottom-right',(1668,1362,56,62),(w-56,h-62))]
 if w==1724:regions.append(('entire-header-gradient',(0,0,1724,94),(0,0)))
 for label,(sx,sy,sw,sh),(dx,dy) in regions:
  expected=source[sy:sy+sh,sx:sx+sw];mask=expected[:,:,3]==255
  found=actual[dy:dy+sh,dx:dx+sw]
  delta=np.abs(found.astype(int)-expected[:,:,:3].astype(int))[mask]
  maximum=int(delta.max());mean=float(delta.mean())
  assert maximum<=1,(name,label,maximum,mean)
  checks.append({'view':name,'region':label,'opaque_pixels':int(mask.sum()),'maximum_channel_difference':maximum,'mean_channel_difference':mean})
assert json.loads((R/'evidence/play/frame-check.json').read_text())['status']=='pass'
result={'status':'pass','source':'reference/window-screenshot.png','working_color_space':'sRGB','title':metadata['title']['text'],'title_edit_rectangle':[90,40,750,48],'changed_pixels_outside_title':int(np.count_nonzero(changed & unchanged)),'rendered_reference_checks':checks,'preserved_native_corner_pixels':True,'resizing_preserves_header_title_and_corners':True}
(R/'evidence/frame-fidelity.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
