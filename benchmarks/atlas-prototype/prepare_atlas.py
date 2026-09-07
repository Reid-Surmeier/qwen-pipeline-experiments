"""Build a shared coastline and registered annotation tiles from the existing artwork."""
from pathlib import Path
import json,hashlib,shutil,sys
import numpy as np
from PIL import Image
from scipy import ndimage as nd
from scipy.interpolate import RBFInterpolator

R=Path(__file__).resolve().parent;repo=R.parents[1];A=R/'godot/assets';A.mkdir(exist_ok=True)
sys.path.insert(0,str(repo/'scripts'))
from georeference import miller
PINK=np.array([255,220,233]);CYAN=np.array([131,229,247]);WHITE=np.array([255,255,255]);PALETTE=np.array([PINK,CYAN,WHITE])
def world(lon,lat):return np.array([((2294.25+lon*12.02)-45)/1.9*2,((1439-687.6*miller(lat))-17)/1.915*2])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def terrain(a):
 # Remove annotations; retain every terrain pixel, including the existing white coast.
 ok=np.any(np.all(a[:,:,None,:]==PALETTE,3),2)
 # Large white character islands inside colored badges are removed with their backing.
 bad=~ok;bad=nd.binary_fill_holes(bad)
 _,idx=nd.distance_transform_edt(bad,return_indices=True)
 b=a.copy();b[bad]=a[idx[0][bad],idx[1][bad]]
 return b
source=repo/'benchmarks/world-map/pink-cyan-v001/preview/map-v004-white-coastlines.png'
a=np.array(Image.open(source).convert('RGB'))
# The old frame is decorative, not a meridian. Extend the nearest inner map pixels.
a[:16]=a[16];a[-16:]=a[-17];a[:,:16]=a[:,16:17];a[:,-16:]=a[:,-17:-16]
Image.fromarray(a).save(A/'world.png')
b=terrain(a)
# Fill glyph holes left within the large badges using component backing extents.
badge=np.max(a,2)-np.min(a,2)>10
badge &= ~np.any(np.all(a[:,:,None,:]==PALETTE,3),2)
cc,n=nd.label(badge)
for s in nd.find_objects(cc):
 if s and s[0].stop-s[0].start>20 and s[1].stop-s[1].start>20:
  y,x=s;box=b[max(0,y.start-3):min(len(b),y.stop+3),max(0,x.start-3):min(b.shape[1],x.stop+3)]
  colors,count=np.unique(box.reshape(-1,3),axis=0,return_counts=True);fill=colors[count.argmax()];b[y,x]=fill
# Muse repair is confined to the missing Pacific segment. Existing Australia stays intact.
pacific=Image.open(R/'generation/pacific-01/image-01.png').convert('RGB').resize((1100,800),Image.Resampling.NEAREST)
p=np.array(pacific);v=p.reshape(-1,3).astype(int);p=PALETTE[((v[:,None]-PALETTE)**2).sum(2).argmin(1)].reshape(p.shape).astype('uint8')
# Copy only the sea/New Zealand side, leaving Australia's approved pixels untouched.
for x in range(488,1100):b[1390:2190,(3980+x)%4480]=p[:,x]
Image.fromarray(b).save(A/'terrain.png')
for x in range(488,1100):a[1390:2190,(3980+x)%4480]=p[:,x]
Image.fromarray(a).save(A/'world.png')
# Native pixel control points read from each existing sheet, with known city lon/lat.
controls={
'europe':[[69,258,-21.94,64.15],[553,715,-.12,51.51],[619,812,2.35,48.86],[435,1112,-3.7,40.42],[958,683,13.4,52.52],[1130,1041,12.5,41.9],[1309,399,24.94,60.17],[1680,536,37.62,55.75],[1559,1115,32.85,39.93],[1263,1200,23.73,37.98]],
'africa':[[582,42,3.06,36.75],[159,519,-17.45,14.69],[660,651,7.49,9.06],[1184,823,32.58,.35],[1489,1223,47.51,-18.88],[886,1552,18.42,-33.92]],
'asia':[[63,507,73.05,33.69],[643,935,100.5,13.75],[783,1346,106.85,-6.21],[1478,458,139.69,35.68],[454,592,91.13,29.65]],
'australia':[[741,174,130.84,-12.46],[1570,734,153.03,-27.47],[1503,936,151.21,-33.87],[1328,1312,147.33,-42.88],[175,894,115.86,-31.95]],
'canada':[[549,1053,-114.07,51.05],[1454,670,-68.52,63.75],[1548,1224,-63.57,44.65],[387,1105,-123.37,48.43],[1114,572,-86.23,66.52]],
'caribbean':[[580,281,-82.37,23.11],[709,133,-80.19,25.76],[849,171,-77.35,25.05],[727,1099,-79.52,8.98],[1437,543,-66.1,18.47]],
'russia':[[1798,38,186.77,64.42],[1637,195,170.3,69.7],[1108,528,102.47,71.98],[739,630,66.61,66.53],[1217,1063,104.3,52.29],[1799,1106,131.89,43.12],[55,464,20.5,54.7],[223,620,37.62,55.75]],
'south-america':[[377,585,-77.04,-12.05],[590,696,-68.15,-16.49],[338,1077,-70.67,-33.45],[782,1098,-58.38,-34.6],[1123,833,-43.17,-22.91]],
'usa':[[936,216,-122.68,45.52],[1393,549,-104.99,39.74],[1677,482,-95.93,41.26],[2333,538,-77.04,38.91],[2183,996,-82.46,27.95],[1316,866,-106.49,31.76]],
'middle-east':[[433,110,30.72,46.48],[948,431,51.39,35.69],[1384,463,69.17,34.53],[1344,733,67.01,24.86],[491,313,32.85,39.93]]}
source_dir=repo/'benchmarks/regional/pink-cyan-v001'
regions=[]
all_marks=json.loads((source_dir/'revision-2/city-markers.json').read_text())
for name,pts in controls.items():
 path=A/(name+'.png')
 if name!='europe':shutil.copyfile(source_dir/'preview'/f'{name}-v2.png',path)
 s=np.array(Image.open(path).convert('RGB'));H,W=s.shape[:2]
 alpha=(np.all(s<65,2)|np.all(s==[204,51,51],2)).astype('uint8')*255
 review=json.loads((source_dir/'runs'/name/'review.json').read_text())
 for badge in review['badges']:
  x,y,w,h=badge['rectangle'];alpha[y:y+h,x:x+w]=255
 # Insets are not at their geographic location. Keep full sheets separately.
 if name=='usa':alpha[:,:750]=0
 if name=='middle-east':
  valid=np.zeros_like(alpha);valid[33:699,308:1568]=255;valid[699:1054,755:1568]=255;alpha &= valid
 points=np.array(pts,dtype=float);src=points[:,:2];dst=np.array([world(lon,lat) for lon,lat in points[:,2:]])
 # Fit an affine fallback for the sheet edge, interpolate landmark corrections inside.
 matrix=np.linalg.lstsq(np.column_stack([src,np.ones(len(src))]),dst,rcond=None)[0]
 corners=np.array([[0,0],[W,0],[0,H],[W,H]],dtype=float)
 target_corners=np.column_stack([corners,np.ones(4)])@matrix
 target=np.vstack([dst,target_corners]);origin=np.vstack([src,corners])
 lo=np.floor(target_corners.min(0));hi=np.ceil(target_corners.max(0));size=hi-lo
 # Move annotation groups rigidly: geographic registration must never bend glyphs.
 scale=2;ow,oh=np.ceil(size*scale).astype(int)
 forward=RBFInterpolator(origin,target,kernel='thin_plate_spline',smoothing=0)
 out=Image.new('RGBA',(ow,oh))
 native_scale=float(np.clip(np.sqrt(abs(np.linalg.det(matrix[:2]))),.3,1.4))
 badge_mask=np.zeros((H,W),bool)
 for badge in review['badges']:
  x,y,w,h=badge['rectangle'];badge_mask[y:y+h,x:x+w]=True
 glyph=np.all(s<65,2)&(alpha>0)&~badge_mask
 annotations=[]
 annotation_alpha=np.zeros((H,W),dtype='uint8')
 groups,count=nd.label(nd.binary_dilation(glyph,structure=np.ones((3,21))))
 def owned(pos):
  lon=(pos[0]*1.9/2+45-2294.25)/12.02
  my=(1439-(pos[1]*1.915/2+17))/687.6
  lat=(np.degrees(np.arctan(np.exp(my/1.25)))-45)/.4
  if name=='russia':return lon>=41 and lat>=49
  if name=='middle-east':return 36<=lon<69
  if name=='asia':return lon>=69 and lat<49
  if name=='canada':return lat>=(43 if lon>-90 else 49)
  if name=='caribbean':return 9<=lat<24
  if name=='south-america':return lat<9
  return True
 def add_group(box,mask,kind):
  x,y,w,h=box
  pos=forward(np.array([[x+w/2,y+h/2]]))[0]
  if not owned(pos):return
  if kind!='label':annotation_alpha[y:y+h,x:x+w][mask]=255
  annotations.append({'rect':[x,y,w,h],'at':pos.tolist(),'kind':kind})
 for index,box in enumerate(nd.find_objects(groups),1):
  if box is None:continue
  ys,xs=box;x,y=xs.start,ys.start;w,h=xs.stop-x,ys.stop-y
  if w>h*25 or h>w*25 or h<10:continue
  mask=(groups[box]==index)&glyph[box]
  if mask.any():add_group((x,y,w,h),mask,'label')
 for badge in review['badges']:
  x,y,w,h=badge['rectangle']
  if np.any(alpha[y:y+h,x:x+w]):add_group((x,y,w,h),np.ones((h,w),bool),'badge')
 allowed=None
 if name=='europe':allowed=set(map(int,json.loads((R/'evidence/europe-reduction.json').read_text())['retained']))
 for index,(x,y,w,h) in enumerate(all_marks[name]):
  if allowed is not None and index not in allowed:continue
  x=max(0,x-1);y=max(0,y-1);w+=2;h+=2
  mask=np.all(s[y:y+h,x:x+w]==[204,51,51],2)&(alpha[y:y+h,x:x+w]>0)
  if mask.any():add_group((x,y,w,h),mask,'city')
 annotation_image=np.dstack([s,annotation_alpha])
 Image.fromarray(annotation_image).save(A/f'{name}-annotations.png')
 Image.fromarray(np.dstack([s,glyph.astype('uint8')*255])).save(A/f'{name}-labels.png')
 text_heights=[v['rect'][3] for v in annotations if v['kind']=='label']
 text_scale=16/max(18,float(np.median(text_heights)))
 # Keep a flat registered preview for provenance; the engine lays these groups out live.
 for group in annotations:
  x,y,w,h=group['rect'];pos=np.array(group['at'])
  tile=Image.fromarray(annotation_image[y:y+h,x:x+w]).resize((max(1,round(w*native_scale*scale)),max(1,round(h*native_scale*scale))),Image.Resampling.NEAREST)
  out.alpha_composite(tile,tuple(np.rint((pos-lo)*scale-np.array(tile.size)/2).astype(int)))
 out=np.array(out)
 Image.fromarray(out).save(A/f'{name}-detail.png')
 focus=np.mean(dst,axis=0)
 regions.append({'id':name,'name':name.replace('-',' ').title() if name!='usa' else 'USA','position':lo.tolist(),'size':size.tolist(),'focus':focus.tolist(),'source_size':[W,H],'source_sha256':sha(path),'detail_sha256':sha(A/f'{name}-detail.png'),'control_points':pts,'annotations':annotations,'text_scale':text_scale})
 print(name,ow,oh,flush=True)
# Geographic focus points drive navigation, rather than artifact rectangle centers.
focuses={'africa':(18,0),'asia':(108,26),'australia':(135,-25),'canada':(-98,60),'caribbean':(-77,17),'europe':(14,51),'middle-east':(53,30),'russia':(101,62),'south-america':(-60,-20),'usa':(-98,38)}
for row in regions:row['focus']=world(*focuses[row['id']]).tolist()
(R/'godot/atlas.json').write_text(json.dumps({'world_size':[4480,2240],'regions':regions,'generation':'../generation/ledger.json'},indent=2)+'\n')
print('Atlas assets ready',flush=True)
