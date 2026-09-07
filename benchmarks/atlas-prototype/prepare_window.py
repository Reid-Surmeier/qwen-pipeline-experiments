"""Extract reference chrome with color management; no synthesized frame pixels."""
from pathlib import Path
from PIL import Image,ImageCms
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
out=R/'godot/assets/window-frame.png'
Image.fromarray(a).save(out)
metadata={'source':'reference/window-screenshot.png','source_sha256':hashlib.sha256(raw).hexdigest(),'classification':'source reference and deterministic frame extraction','source_color_profile_sha256':hashlib.sha256(profile).hexdigest(),'working_color_space':'sRGB; converted with Pillow ImageCms','source_rectangle':[20,16,1724,1424],'content_inset':[36,94],'frame_extra':[72,136],'header_fixed_left':850,'header_fixed_right':100,'bottom_corner_size':[56,62],'frame_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'generation_count':0}
(R/'reference/window-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps(metadata,indent=2))
