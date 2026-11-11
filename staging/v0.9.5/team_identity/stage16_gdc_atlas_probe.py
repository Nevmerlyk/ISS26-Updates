from pathlib import Path
import sys,json,struct,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).parent;sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from stage7_gdc_bosnia_patch import get_source
from wecodec_stage5 import decode
TR=Path('/mnt/data/ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin')
PATCH=ROOT/'stage12_results/ISS26_0.9.5_Stage12_Test08_LargeGPU_AB_CANDIDATE.iss26p'
meta={'GDC_AD':(12560,140632),'GDC_BD':(16300,135840),'GDC_FN':(11370,155172),'GDC_JD':(11540,143836)}
COL=np.array([(0,0,0),(255,255,255),(24,27,35),(228,20,40),(5,60,170),(0,160,75),(255,223,20),(210,115,19),(240,80,92),(98,167,226),(8,30,65),(0,68,78),(255,255,150),(110,110,110),(48,48,48),(175,175,175)],dtype=np.uint8)
def dec(b):
 _,_,used,raw,cmd=get_source(b)
 zz=np.frombuffer(raw,dtype='uint8');z=np.stack((zz&15,zz>>4),axis=-1).reshape(128,128)
 return z,cmd
p=PatchedDisc(TR,PATCH,verify=True)
try:
 fig=Image.new('RGB',(4*272,3*314),(22,25,32));d=ImageDraw.Draw(fig)
 results={}
 for i,(name,(lba,size)) in enumerate(meta.items()):
  b=p.logical(lba,0,size,True);zz,cmd=dec(b)
  clip=COL[zz];img=Image.fromarray(clip).resize((256,256),Image.Resampling.NEAREST)
  x=(i%4)*272+7;fig.paste(img,(x,40));d.text((x,10),name+' 128x128 4bpp',fill='white')
  # Draw intended 'big 64x28 flag' bottom left half in green rectangle
  d.rectangle((x,40+64*2,x+64*2,40+92*2),outline=(20,255,20),width=2)
  for k in range(4):
   sub=zz[k*32:k*32+32]
   results[name+'_row'+str(k)]={str(j):int(np.sum(sub==j)) for j in np.unique(sub)}
 fig.save(ROOT/'stage16_gdc_flag_probe.png')
 (ROOT/'stage16_gdc_flag_probe.json').write_text(json.dumps(results,indent=2))
finally:p.close()
