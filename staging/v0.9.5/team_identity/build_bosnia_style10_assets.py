#!/usr/bin/env python3
"""Stage 4: prepare exact 4bpp source art for a DEDICATED Bosnia style 10.

Asset-only source, not a playable patch. It deliberately does not change
style 7 (shared by six unmodified nations), game menus or discs.
"""
from __future__ import annotations
import json,hashlib,math
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
OUTPUT=ROOT/'stage4_results'/'bosnia_style10_art'
SOURCE=ROOT/'bosnia_24x16_v5_source.json'
RGB={0:(0,0,0,0),1:(245,246,248,255),2:(25,26,29,255),3:(220,25,48,255),4:(0,62,160,255),5:(0,135,65,255),6:(255,218,41,255),7:(244,124,32,255),8:(137,21,53,255),9:(76,183,225,255),10:(5,35,100,255)}

def pack4(pixels):
 if len(pixels)%2:raise ValueError('4bpp requires an even pixel count')
 if not all(0<=v<=15 for v in pixels):raise ValueError('Invalid 4-bit palette index')
 return bytes(a|(b<<4) for a,b in zip(pixels[::2],pixels[1::2]))

def star(x,y,r=2.3):
 pts=[]
 for i in range(10):
  a=-math.pi/2+i*math.pi/5; rr=r if i%2==0 else r*.41
  pts.append((int(round(x+rr*math.cos(a))),int(round(y+rr*math.sin(a)))))
 return pts

def exact_large_bosnia():
 W,H=64,28
 im=Image.new('P',(W,H),1);d=ImageDraw.Draw(im)
 # 1=Bosnia blue, 2=yellow, 3=white under the known large-flag semantic CLUT.
 d.polygon([(34,0),(63,0),(63,27)],fill=2)
 for x,y in [(35,1),(38,5),(42,9),(46,13),(50,17),(54,21),(58,25)]:
  d.polygon(star(x,y,2.15),fill=3)
 return im

def run():
 OUTPUT.mkdir(parents=True,exist_ok=True)
 src=json.loads(SOURCE.read_text())['28'];v=bytes.fromhex(src['pixels_hex'])
 if len(v)!=24*16:raise ValueError('Wrong source flag size')
 # MasterLeague screenshot is not a bit-perfect source; reuse the v5 Bosnia drawing.
 if not ({1,6,10}<=set(v)):raise ValueError('Expected Bosnia white/yellow/blue semantic indexes')
 small=Image.new('P',(24,16));small.putdata(v)
 strip=small.resize((24,8),Image.Resampling.NEAREST)
 big=exact_large_bosnia()
 assets={'selection_24x16':(small,{'blue':10,'yellow':6,'white':1}),
         'scoreboard_24x8':(strip,{'blue':10,'yellow':6,'white':1}),
         'large_64x28':(big,{'blue':1,'yellow':2,'white':3})}
 report={'purpose':'Candidate original free PS1 style 10 Bosnia graphic assets, NON-RELEASED',
 'style':10,'original_style_owner':'SLOVAKIA, now replaced by DR CONGO',
 'original_64x28_tile_coordinate':{'vram_word_x':864,'vram_line_y':320},
 'source_art':'Prepared Bosnia drawing from Test05 pixel data; NOT bit-exact Master League extraction',
 'requires_ui_style_mapping_23':'7 -> 10 in both select tables after graphic upload integration',
 'requires_other_sources':['DATSEL','DATSEL3','EDT_2D','EDTR_2D','all GDC stadium uploads that render large flag'],
 'status':'ARTWORK READY FOR INTEGRATION, NOT ENOUGH TO FIX BOSNIA ALONE',
 'assets':{}}
 for name,(im,sem) in assets.items():
  pix=list(im.getdata());w,h=im.size;blob=pack4(pix)
  assert len(blob)==w*h//2
  (OUTPUT/(name+'.4bpp')).write_bytes(blob)
  preview=Image.new('RGBA',im.size);preview.putdata([RGB.get(p,(255,0,255,255)) if name!='large_64x28' else {1:RGB[10],2:RGB[6],3:RGB[1]}.get(p,(255,0,255,255)) for p in pix])
  preview.resize((w*8,h*8),Image.Resampling.NEAREST).save(OUTPUT/(name+'.png'))
  report['assets'][name]={'width':w,'height':h,'4bpp_bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest().upper(),'semantic_color_indexes':sem,'nonzero_pixels':sum(z!=0 for z in pix)}
 (OUTPUT/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
 return report

if __name__=='__main__':print(json.dumps(run(),indent=2))
