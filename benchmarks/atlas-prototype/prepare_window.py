"""Extract reference chrome and assemble the Muse title inside its declared edit region."""
from pathlib import Path
from PIL import Image,ImageCms,ImageFilter
import hashlib,io,json,sys
import numpy as np

R=Path(__file__).resolve().parent
source=Path(sys.argv[1])
raw=source.read_bytes()
(R/'reference/window-screenshot.png').write_bytes(raw)
im=Image.open(io.BytesIO(raw)).convert('RGB')
profile=im.info['icc_profile']
im=ImageCms.profileToProfile(im,ImageCms.ImageCmsProfile(io.BytesIO(profile)),ImageCms.createProfile('sRGB'),outputMode='RGB')
a=np.array(im.crop((20,16,1744,1440)).convert('RGBA'))
h,w=a.shape[:2]
a[94:h-42,36:w-36,3]=0
# Retain the original rounded inner-corner border over the live map, not its blue fill.
for left in [36,w-56]:
 patch=a[h-62:h-42,left:left+20]
 patch[:,:,3]=np.where(np.max(np.abs(patch[:,:,:3].astype(int)-[132,228,247]),axis=2)>3,255,0)
# Preserve the source gradient; transfer only Muse's generated letter coverage.
donor_path=R/'generation/title-01/image-01.png'
donor=np.array(Image.open(donor_path).convert('RGB').resize((1728,384),Image.Resampling.LANCZOS)).astype(float)
letter=donor[45:91,96:718]
background=np.median(donor[45:91,1000:1100],axis=1)[:,None,:]
coverage=np.clip(np.mean((background-letter)/(background-[16,22,27]),axis=2),0,1)
glyph_edge=np.array(Image.fromarray((letter.mean(axis=2)<140).astype('uint8')*255).filter(ImageFilter.MaxFilter(3)))>0
coverage[~glyph_edge | (coverage<.06)]=0
# The source title and anti-aliased edges fit within this one edit rectangle.
a[40:88,90:840,:3]=np.median(a[40:88,900:1100,:3],axis=1).astype('uint8')[:,None,:]
patch=a[42:88,96:718,:3]
patch[:]=np.rint(patch*(1-coverage[:,:,None])+np.array([50,58,69])*coverage[:,:,None]).astype('uint8')
out=R/'godot/assets/window-frame.png'
Image.fromarray(a).save(out)
metadata={'source':'reference/window-screenshot.png','source_sha256':hashlib.sha256(raw).hexdigest(),'classification':'source reference and deterministic frame extraction','source_color_profile_sha256':hashlib.sha256(profile).hexdigest(),'working_color_space':'sRGB; converted with Pillow ImageCms','source_rectangle':[20,16,1724,1424],'content_inset':[36,94],'frame_extra':[72,136],'header_fixed_left':850,'header_fixed_right':100,'bottom_corner_size':[56,62],'frame_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'generation_count':1,'title':{'text':'World map : RISD Collection','edit_rectangle':[90,40,750,48],'donor':'generation/title-01/image-01.png','donor_sha256':hashlib.sha256(donor_path.read_bytes()).hexdigest(),'normalized_donor_size':[1728,384],'donor_crop':[96,45,622,46],'destination':[96,42],'assembly':'Generated glyph coverage over the source row gradient, using original dark text color; unchanged outside title rectangle'}}
(R/'reference/window-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
