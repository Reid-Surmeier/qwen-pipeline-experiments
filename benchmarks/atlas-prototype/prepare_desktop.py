"""Assemble tight Muse lettering edits and the transparent notification backing."""
from pathlib import Path
import hashlib,json,shutil
import numpy as np
import cv2
from PIL import Image

R=Path(__file__).resolve().parent
out=R/'godot/assets/desktop';out.mkdir(exist_ok=True)
records=[]
# Rectangles use the upright references; final assets retain their original orientation.
TEXT_EDITS={
 'itinerary': [
  {'text':'Collection Hightlights','edit':[180,60,2090,120],'donor':[180,60,2090,110],'offset':[0,5]},
  {'text':'Collection number','edit':[80,1370,970,125],'donor':[90,1380,780,90],'offset':[4,6]},
  {'text':'Collection number','edit':[1270,1370,930,125],'donor':[1260,1380,790,90],'offset':[13,6]}],
 'minimap':[{'text':'MiniMap','edit':[85,75,470,97],'donor':[95,75,330,95],'offset':[0,2]}],
 'notification':[{'text':'Recently Added!','edit':[245,60,850,125],'donor':[245,80,850,125],'offset':[0,-23]}],
}
fidelity=[]

def apply_text(a,name):
 upright=Image.fromarray(a).transpose(Image.Transpose.ROTATE_270) if name!='notification' else Image.fromarray(a)
 a=np.array(upright)
 donor_path=R/'generation'/f'{name}-text-02/image-01.png'
 donor=np.array(Image.open(donor_path).convert('RGB').resize(upright.size,Image.Resampling.LANCZOS)).astype(float)
 allowed=np.zeros(a.shape[:2],dtype=bool)
 for spec in TEXT_EDITS[name]:
  x,y,w,h=spec['edit'];allowed[y:y+h,x:x+w]=True
  before=a[y:y+h,x:x+w,:3].copy()
  ink=before.mean(2)<120
  color=np.median(before[ink],axis=0)
  erase=np.zeros(a.shape[:2],dtype='uint8')
  erase[y:y+h,x:x+w]=cv2.dilate(ink.astype('uint8'),np.ones((5,5),np.uint8))*255
  if name=='minimap':
   a[:,:,:3]=cv2.inpaint(a[:,:,:3],erase,12,cv2.INPAINT_TELEA)
  else:
   sample_x=200 if name=='itinerary' and y<200 else (400 if name=='itinerary' and x<1000 else (1600 if name=='itinerary' else 220))
   background_rows=np.median(a[y:y+h,sample_x:sample_x+20,:3],axis=1).astype('uint8')
   a[y:y+h,x:x+w,:3]=background_rows[:,None,:]
  dx,dy,dw,dh=spec['donor'];letters=donor[dy:dy+dh,dx:dx+dw]
  core=letters.mean(2)<120
  foreground=np.percentile(letters[core],20,axis=0)
  background=np.percentile(letters.reshape(-1,3),80,axis=0)
  coverage=np.clip(((background-letters)/np.maximum(background-foreground,1)).mean(2),0,1)
  edge=cv2.dilate(core.astype('uint8'),np.ones((3,3),np.uint8))>0
  coverage[~edge|(coverage<.06)]=0
  px=dx+spec['offset'][0];py=dy+spec['offset'][1]
  patch=a[py:py+dh,px:px+dw,:3]
  patch[:]=np.rint(patch*(1-coverage[:,:,None])+color*coverage[:,:,None]).astype('uint8')
 changed=np.any(a!=np.array(upright),axis=2)
 assert not np.any(changed&~allowed),name
 assert np.array_equal(a[:,:,3],np.array(upright)[:,:,3]),name
 result=Image.fromarray(a).transpose(Image.Transpose.ROTATE_90) if name!='notification' else Image.fromarray(a)
 zeros=[]
 if name=='itinerary':
  for x,y,w,h in [(1080,1370,95,125),(2235,1370,95,125)]:
   assert np.array_equal(a[y:y+h,x:x+w],np.array(upright)[y:y+h,x:x+w])
   zeros.append([x,y,w,h])
 fidelity.append({'asset':name,'donor':str(donor_path.relative_to(R)),'donor_sha256':hashlib.sha256(donor_path.read_bytes()).hexdigest(),'edits':TEXT_EDITS[name],'changed_pixels':int(changed.sum()),'changed_pixels_outside_edits':0,'alpha_preserved':True,'original_zero_rectangles_preserved':zeros})
 return np.array(result)

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
 if name in TEXT_EDITS:
  a=apply_text(a,name)
  Image.fromarray(a).save(target)
 else:shutil.copyfile(source,target)
 records.append({'id':name,'source':str(source.relative_to(R)),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'output':str(target.relative_to(R)),'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':list(im.size),'processing':'Muse glyph assembly in declared rectangles; original alpha preserved' if name in TEXT_EDITS else 'Byte-identical copy','transparent_pixels':int(np.count_nonzero(a[:,:,3]==0))})
(R/'reference/desktop/assets.json').write_text(json.dumps({'classification':'User source references and deterministic prototype assets','generation_count':3,'panels':records},indent=2)+'\n')
(R/'evidence/text-fidelity.json').write_text(json.dumps({'status':'pass','panels':fidelity},indent=2)+'\n')
print('PASS Muse text assembly, unchanged pixels outside edits, preserved zeros and alpha')
