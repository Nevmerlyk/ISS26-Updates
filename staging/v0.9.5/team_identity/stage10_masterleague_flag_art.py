#!/usr/bin/env python3
"""Redraw Bosnia/Canada 24x16 selectable 4bpp sprites from user-provided
PCSX-Redux Master League Player Acquisition screenshot references.

The game uses a 24x16 slot. Keep visible 20x16 and 4 transparent columns,
matching the validated Test04 geometry; never move X/Y or change other sprites.
"""
from __future__ import annotations
from pathlib import Path
import json,hashlib
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
SMALL=Path('/mnt/data/iss26_small_fix_work')
OUTPUT=ROOT/'stage10_results';OUTPUT.mkdir(exist_ok=True)
SOURCE=SMALL/'flags_24x16_v5.json'
FLAGS=json.loads(SOURCE.read_text())
C={0:(15,20,29),1:(245,246,248),2:(25,26,29),3:(220,25,48),4:(0,62,160),5:(0,135,65),6:(255,218,41),7:(244,124,32),8:(137,21,53),9:(76,183,225),10:(5,35,100),11:(130,130,130)}

def make_bosnia():
    width,height=24,16
    pix=bytearray(width*height)
    for y in range(height):
        for x in range(20):
            pix[y*width+x]=4  # Blue field, same deep clear blue as Master League icon
        # Master League yellow wedge, edge descends to the lower right.
        start=4+(y*4)//5
        for x in range(start,17):
            pix[y*width+x]=6
    # White five-point stars cannot be depicted at this resolution: two-pixel
    # squares reproduce the tiny white diagonal marks of the source screenshot.
    for cx,cy in [(2,1),(4,4),(6,7),(9,10),(11,13)]:
        for dx,dy in [(0,0),(1,0),(0,1)]:
            xx,yy=cx+dx,cy+dy
            if xx<20 and yy<16:
                pix[yy*width+xx]=1
    return bytes(pix)

def make_canada():
    width,height=24,16
    pix=bytearray(width*height)
    for y in range(height):
        for x in range(20):
            pix[y*width+x]=3 if x<4 or x>=16 else 1
    # The shape is traced by hand from the little maple silhouette shown next
    # to Forest. Retains the jagged upper lobes, broad middle and narrow stem.
    leaf={
      3:[10],
      4:[9,10,11],
      5:[7,8,10,12,13],
      6:[6,7,8,9,10,11,12,13,14],
      7:[5,6,7,8,9,10,11,12,13,14],
      8:[6,7,8,9,10,11,12,13,14],
      9:[8,9,10,11,12],
     10:[9,10,11],
     11:[10],
     12:[10],
    }
    for y,xs in leaf.items():
        for x in xs: pix[y*width+x]=3
    return bytes(pix)

def validate_one(data,expected):
    assert len(data)==24*16 and all(z<=15 for z in data)
    assert all(data[y*24+x]==0 for y in range(16) for x in range(20,24))
    assert all(data[y*24+x]!=0 for y in range(16) for x in range(20))
    assert set(data)==expected


def save_png(data,path,scale=16):
    im=Image.new('RGBA',(24,16));im.putdata([C[z]+((0 if z==0 else 255),) for z in data]); bg=Image.new('RGBA',(24,16),(19,25,36,255));bg.alpha_composite(im)
    bg.resize((24*scale,16*scale),Image.Resampling.NEAREST).convert('RGB').save(path)

def main():
    bosnia=make_bosnia(); canada=make_canada()
    validate_one(bosnia,{0,1,4,6});validate_one(canada,{0,1,3})
    new=dict(FLAGS)
    for slot,raw in [('28',bosnia),('19',canada)]:
        assert slot in FLAGS and bytes.fromhex(FLAGS[slot]['pixels_hex'])!=raw
        new[slot]={'name':FLAGS[slot]['name'],'pixels_hex':raw.hex()}
    assert set(new)==set(FLAGS)
    assert all(new[k]==FLAGS[k] for k in FLAGS if k not in ('28','19'))
    path=OUTPUT/'flags_24x16_masterleague_v6.json'
    path.write_text(json.dumps(new,indent=2)+'\n',encoding='utf-8')
    for s,v in [('bosnia',bosnia),('canada',canada)]:save_png(v,OUTPUT/f'{s}_masterleague_redraw_24x16.png',16)
    # One graphic comparison for user and regression review
    canvas=Image.new('RGB',(1100,580),'#17202d');draw=ImageDraw.Draw(canvas)
    for i,(slot,label) in enumerate([('28','BOSNIA — Salamic reference'),('19','CANADA — Forest reference')]):
        old=bytes.fromhex(FLAGS[slot]['pixels_hex']);now=bytes.fromhex(new[slot]['pixels_hex'])
        x=i*550+20
        draw.text((x,13),label,fill='#ffffff')
        draw.text((x,47),'Before — Test06',fill='#b8c1cc')
        bg=Image.new('RGB',(24,16));bg.putdata([C[z] for z in old]);canvas.paste(bg.resize((480,240),Image.Resampling.NEAREST),(x,67))
        draw.text((x,320),'After — Master League redraw',fill='#b8c1cc')
        bg=Image.new('RGB',(24,16));bg.putdata([C[z] for z in now]);canvas.paste(bg.resize((480,240),Image.Resampling.NEAREST),(x,338))
    canvas.save(OUTPUT/'masterleague_flags_before_after.png')
    rep={'stage':10,'source':'user screenshot of original Master League Player Acquisition flags (Salamic, Forest)','method':'faithful manual pixel-art redraw, not direct bit-identical source extraction','slot_size':[24,16],'active_opaque_area':[20,16],'change_slots':[28,19], 'preserved_other_art_slots':14,'new_art_sha256':{'bosnia':hashlib.sha256(bosnia).hexdigest().upper(),'canada':hashlib.sha256(canada).hexdigest().upper()},'reference_files':['image(20261110-212120).png','image(20261110-212351).png']}
    (OUTPUT/'stage10_art_report.json').write_text(json.dumps(rep,indent=2)+'\n')
    print(json.dumps(rep,indent=2))
if __name__=='__main__':main()
