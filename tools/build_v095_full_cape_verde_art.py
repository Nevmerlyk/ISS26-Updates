#!/usr/bin/env python3
"""Reproducible, preview-only 4bpp Cape Verde from clean original PS1 font.

Draw rectangles stay fixed at (24,38,128,16) and (152,38,88,16).
No changes to original disc. Test13 target tile UV/CLUT still unverified.
"""
from __future__ import annotations
import argparse,hashlib,json,struct,zlib
from pathlib import Path
from build_v095_cape_original_font import source_atlas, compose as compose_cape, pack4
import v095_cape_verde_sprite_layout as layout
recompose=layout.recompose
value=getattr(layout,"value",None) or layout.pixel

W,H=1792,256
GLYPHS=[
 ('V','Valencia',1024,64,0,18),
 ('e','Chile',512,224,50,64),
 ('r','Croatia',384,96,17,29),
 ('d','England',128,0,88,103),
 ('e','Chile',512,224,50,64),
]

def compose_word(vram:bytes,glyphs=GLYPHS,overlap=3)->tuple[bytes,int]:
    if len(vram)!=W*H:raise ValueError("Expected original 1792x256 indexed atlas")
    plane=bytearray(128*16)
    cursor=0
    for i,(_,_,ax,ay,left,right) in enumerate(glyphs):
        if i:cursor-=overlap
        for y in range(16):
            for x in range(right-left):
                index=vram[(ay+y)*W+ax+left+x]
                if index:plane[y*128+cursor+x]=max(plane[y*128+cursor+x],index)
        cursor+=right-left
    width=(cursor+1)&~1
    return bytes(plane[y*128+x] for y in range(16) for x in range(width)),width

def place_4bpp_word(word:bytes,w:int,rect_w:int)->bytes:
    if w>rect_w or w%2 or len(word)!=w*16:
        raise ValueError("Word cannot fit into unchanged 4bpp rectangle")
    output=bytearray(rect_w*16//2)
    for y in range(16):
        for x in range(w):
            index=word[y*w+x]
            if not 0<=index<16:raise ValueError("4bpp palette index out of range")
            output[y*rect_w//2+x//2]|=index<<(4*(x%2))
    return bytes(output)

def png_preview(left:bytes,right:bytes,path:Path,scale=6)->None:
    """Write PNG with Python standard library only."""
    width,height=216*scale,16*scale
    raw=bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            px=x//scale
            index=(value(left,128,px,y//scale) if px<128
                   else value(right,88,px-128,y//scale))
            tone=255 if not index else max(12,195-11*index)
            raw.extend((tone,tone,tone))
    def chunk(tag,blob):
        return (struct.pack(">I",len(blob))+tag+blob+
                struct.pack(">I",zlib.crc32(tag+blob)&0xffffffff))
    png=(bytes.fromhex("89504e470d0a1a0a")+
         chunk(b"IHDR",struct.pack(">IIBBBBB",width,height,8,2,0,0,0))+
         chunk(b"IDAT",zlib.compress(raw,6))+chunk(b"IEND",b""))
    path.write_bytes(png)

def build(track:Path,outdir:Path)->dict:
    vram=source_atlas(track)
    cape,cape_w=compose_cape(vram)
    verde,verde_w=compose_word(vram)
    left,right,geometry=recompose(pack4(cape,cape_w),cape_w,
                                   place_4bpp_word(verde,verde_w,88),
                                   space_px=7,cape_left=2,cape_top=2)
    outdir.mkdir(parents=True,exist_ok=True)
    png_preview(left,right,outdir/"ISS26_CapeVerde_original_font_layout.png")
    (outdir/"ISS26_CapeVerde_sprite_left_4bpp.bin").write_bytes(left)
    (outdir/"ISS26_CapeVerde_sprite_right_4bpp.bin").write_bytes(right)
    report={
      "schema_version":1,"status":"ART PREVIEW ONLY; not a Test14 patch",
      "source":"Verified clean EU Track01 T_NAME_E.BIN",
      "text":"Cape Verde","cape_width_px":cape_w,"verde_width_px":verde_w,
      "screen_draw_rects":[[24,38,128,16],[152,38,88,16]],
      "left_4bpp_sha256":hashlib.sha256(left).hexdigest().upper(),
      "right_4bpp_sha256":hashlib.sha256(right).hexdigest().upper(),
      "glyph_sources":[{"character":c,"label":name,"atlas_x":ax,
                         "atlas_y":ay,"source_x_range":[lo,hi]}
                         for c,name,ax,ay,lo,hi in GLYPHS],
      "requested_space_pixels":7,"layout":geometry,
      "draw_rects_moved":False,"verified_test13_target_uv":False,
      "original_disc_modified":False,"test14_generated":False
    }
    (outdir/"ISS26_CapeVerde_art_report.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",type=Path,required=True)
    p.add_argument("--outdir",type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(build(args.clean_track,args.outdir),indent=2,ensure_ascii=False))
