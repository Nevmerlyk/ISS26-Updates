#!/usr/bin/env python3
from pathlib import Path
import struct, sys, collections,json
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
from wecodec_stage5 import decode
from team_identity_audit import PatchedDisc
TR=Path('/mnt/data/ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin')
PATCH=ROOT/'stage12_results/ISS26_0.9.5_Stage12_Test08_LargeGPU_AB_CANDIDATE.iss26p'
R={'GDC_AD':(12560,140632),'GDC_BD':(16300,135840)}
COL=np.array([[0,0,0],[245,245,245],[21,25,31],[227,20,30],[5,65,160],[0,150,70],[255,219,25],[216,119,16],[230,64,80],[106,175,218],[8,35,90],[0,61,81],[238,238,128],[100,100,100],[48,48,48],[167,167,167]],dtype=np.uint8)
def main():
 disc=PatchedDisc(TR,PATCH,verify=False)
 try:
  for tag,(lba,size) in R.items():
   b=disc.logical(lba,0,size,True)
   v=np.zeros((512,1024*4),dtype=np.uint8)
   seen=[]
   for p in range(0,len(b)-15,4):
    op,x,y,w,h,flag,ptr=struct.unpack_from('<6HI',b,p)
    if op!=10 or w not in (16,32,64,128) or h not in (32,64,128,256) or x+w>1024 or y+h>512 or not (0x800c8000<=ptr<len(b)+0x800c8000):continue
    raw,used=decode(b[ptr-0x800c8000:],w*h*2)
    pix=np.frombuffer(raw,dtype=np.uint8)
    pix=np.stack((pix&15,pix>>4),axis=-1).reshape(h,w*4)
    v[y:y+h,x*4:(x+w)*4]=pix
    seen.append({'at':p,'x':x,'y':y,'w':w,'h':h,'src':ptr-0x800c8000,'compressed':used})
   crop=v[:512,672*4:1024*4]
   im=Image.fromarray(COL[crop],mode='RGB')
   im.save(ROOT/(tag+'_full_vram_flags_4bpp.png'))
   # Show all columns side-by-side 2x vertical section 512 -> 1024x width after 1.0
   (ROOT/(tag+'_upload_commands.json')).write_text(json.dumps(seen,indent=2)+'\n')
   print(tag,'upload count',len(seen),'results',im.size,'shape data',len(np.unique(crop)),'total decoded',sum(x['w']*x['h']*2 for x in seen))
 finally:disc.close()
if __name__=='__main__':main()
