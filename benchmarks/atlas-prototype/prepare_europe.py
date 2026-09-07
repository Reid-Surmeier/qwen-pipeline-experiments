"""Throwaway Assembly: 94 cities -> 47, keeping the original retained glyphs."""
from pathlib import Path
import json,hashlib
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as nd
R=Path(__file__).resolve().parent
source=R.parent/'regional/pink-cyan-v001'
a=np.array(Image.open(source/'preview/europe-v2.png').convert('RGB'))
marks=json.loads((source/'revision-2/city-markers.json').read_text())['europe']
# Existing marker id: city name, tightly reviewed label rectangle (x0,y0,x1,y1).
keep={
3:['Reykjavik',[50,287,187,319]],7:['Oslo',[831,379,895,409]],8:['Stockholm',[960,411,1115,441]],
4:['Helsinki',[1301,365,1407,395]],17:['Copenhagen',[835,533,1009,565]],9:['Tallinn',[1280,435,1378,465]],
12:['Riga',[1300,514,1368,544]],19:['Vilnius',[1228,560,1326,590]],21:['Minsk',[1347,636,1433,666]],
14:['Moscow',[1613,497,1739,527]],6:['St Petersburg',[1490,395,1683,426]],29:['Warsaw',[1155,654,1260,684]],
25:['Berlin',[910,689,992,719]],36:['Prague',[967,730,1067,760]],45:['Vienna',[959,835,1052,865]],
46:['Bratislava',[1074,802,1209,831]],47:['Budapest',[1137,846,1271,877]],91:['Ljubljana',[1007,878,1141,908]],
55:['Zagreb',[1043,914,1138,943]],62:['Sarajevo',[1031,953,1155,983]],58:['Belgrade',[1172,930,1300,960]],
67:['Pristina',[1145,994,1264,1023]],72:['Skopje',[1191,1064,1292,1095]],74:['Tirana',[1093,1079,1175,1109]],
83:['Athens',[1257,1210,1347,1240]],68:['Sofia',[1270,1021,1337,1052]],60:['Bucharest',[1304,937,1452,967]],
49:['Chisinau',[1362,833,1479,864]],34:['Kyiv',[1418,753,1501,785]],75:['Istanbul',[1402,1048,1537,1078]],
78:['Ankara',[1558,1123,1656,1152]],87:['Nicosia',[1450,1272,1557,1302]],86:['Valletta',[989,1267,1090,1298]],
70:['Rome',[891,1024,975,1055]],81:['Lisbon',[285,1164,377,1197]],77:['Madrid',[382,1118,480,1149]],
42:['Paris',[574,816,655,847]],31:['London',[457,717,561,747]],23:['Dublin',[275,647,369,678]],
32:['Brussels',[600,746,724,776]],27:['Amsterdam',[708,656,870,686]],39:['Luxembourg',[660,784,836,814]],
51:['Bern',[695,863,764,894]],48:['Zurich',[716,834,809,865]],73:['Barcelona',[621,1085,765,1117]],
15:['Edinburgh',[468,553,598,584]],1:['Murmansk',[1500,83,1640,112]]}
assert len(keep)==47
badges=json.loads((source/'runs/europe/review.json').read_text())['badges']
badge=np.zeros(a.shape[:2],bool)
for b in badges:
 x,y,w,h=b['rectangle'];badge[y:y+h,x:x+w]=True
ink=(np.all(a==0,2)|np.all(a==[204,51,51],2))&~badge
remove=nd.binary_dilation(ink,iterations=2)&~badge
filled=cv2.inpaint(a,remove.astype('uint8')*255,4,cv2.INPAINT_TELEA)
palette=np.array([[255,220,233],[131,229,247],[255,255,255]])
values=filled[remove].astype(int)
filled[remove]=palette[((values[:,None,:]-palette)**2).sum(2).argmin(1)]
out=a.copy();out[remove]=filled[remove]
retained=np.zeros(a.shape[:2],bool)
for index,(name,rect) in keep.items():
 x0,y0,x1,y1=rect;retained[y0:y1,x0:x1]=True
 x,y,w,h=marks[index];retained[y-2:y+h+2,x-2:x+w+2]=True
out[retained]=a[retained]
assert np.array_equal(out[badge],a[badge])
assert np.array_equal(out[~remove],a[~remove])
Image.fromarray(out).save(R/'godot/assets/europe.png')
Image.fromarray(remove&~retained).save(R/'evidence/europe-edit-mask.png')
(R/'evidence/europe-reduction.json').write_text(json.dumps({'original_count':94,'retained_count':47,'source_sha256':hashlib.sha256((source/'preview/europe-v2.png').read_bytes()).hexdigest(),'retained':keep,'badge_changed_pixels':0},indent=2)+'\n')
print('Europe: 47 cities retained; all badges unchanged.')
