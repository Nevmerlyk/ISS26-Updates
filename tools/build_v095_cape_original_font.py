#!/usr/bin/env python3
"""Create an original-game-font 4bpp 'Cape' sprite (artwork candidate only).

Uses 4 glyph crops from the user's clean European ISS Pro Evolution 2 Track01.
No game data is committed to the repository or modification performed.
Requires only Python stdlib plus tools/v095_name_lz_codec.py.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path
from v095_name_lz_codec import decode_atlas, atlas_records

CLEAN_SHA = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
ATLAS_SHA = "C0931A9FBAB344715D38F9C21310549F4442C778FCEC47EA2FB7C3EC600A723F"
GLYPHS = [
    {"char":"C","from":"Chile","x":512,"y":224,"start":0,"stop":19},
    {"char":"a","from":"Croatia","x":384,"y":96,"start":46,"stop":61},
    {"char":"p","from":"Japan","x":640,"y":224,"start":29,"stop":47},
    {"char":"e","from":"Chile","x":512,"y":224,"start":48,"stop":64}
]
ATLAS_W,ATLAS_H,OVERLAP=1792,256,2

def sha(value:bytes)->str:
    return hashlib.sha256(value).hexdigest().upper()

def source_atlas(disc:Path)->bytes:
    with disc.open("rb") as f:
        h=hashlib.sha256()
        for block in iter(lambda:f.read(4<<20),b""):h.update(block)
    if h.hexdigest().upper()!=CLEAN_SHA:
        raise ValueError("Original EU Track01 SHA256 mismatch")
    with disc.open("rb") as f:
        resource=bytearray()
        for i in range(28):
            f.seek((8200+i)*2352)
            sector=f.read(2352)
            if len(sector)!=2352 or sector[15]!=2 or sector[18]&0x20:
                raise ValueError("Invalid Mode2 Form1 CD sector")
            resource.extend(sector[24:2072])
    resource=bytes(resource[:56256])
    if sha(resource)!=ATLAS_SHA:
        raise ValueError("Unexpected original T_NAME_E resource hash")
    pixels=bytearray(ATLAS_W*ATLAS_H)
    for tile,info in zip(decode_atlas(resource),atlas_records(resource)):
        ox,oy=info["x_words"]*4,info["y"]
        for j,b in enumerate(tile):
            x=ox+2*(j%64)
            y=oy+j//64
            pixels[y*ATLAS_W+x]=b&15
            pixels[y*ATLAS_W+x+1]=b>>4
    return bytes(pixels)

def compose(vram:bytes)->tuple[bytes,int]:
    if len(vram)!=ATLAS_W*ATLAS_H:
        raise ValueError("Unexpected atlas size")
    plane=bytearray(128*16)
    cursor=0
    for i,glyph in enumerate(GLYPHS):
        if i:cursor-=OVERLAP
        width=glyph["stop"]-glyph["start"]
        for y in range(16):
            for x in range(width):
                nib=vram[(glyph["y"]+y)*ATLAS_W+glyph["x"]+glyph["start"]+x]
                if nib:
                    pos=y*128+cursor+x
                    plane[pos]=max(plane[pos],nib)
        cursor+=width
    width=(cursor+1)&~1
    return bytes(plane[y*128+x] for y in range(16) for x in range(width)),width

def pack4(pixels:bytes,width:int)->bytes:
    if width%2 or len(pixels)!=16*width or max(pixels,default=0)>15:
        raise ValueError("Invalid indexed 4bpp artwork")
    return bytes(pixels[i] | (pixels[i+1]<<4) for i in range(0,len(pixels),2))

def preview(pixels:bytes,width:int)->bytes:
    scale=8
    w,h=width*scale,16*scale
    raw=bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            nib=pixels[(y//scale)*width+(x//scale)]
            tone=255 if nib==0 else max(0,190-11*nib)
            raw.extend((tone,tone,tone))
    def chunk(tag,data):
        return (struct.pack(">I",len(data))+tag+data+
                struct.pack(">I",zlib.crc32(tag+data)&0xffffffff))
    return (bytes.fromhex("89504e470d0a1a0a")+
            chunk(b"IHDR",struct.pack(">IIBBBBB",w,h,8,2,0,0,0))+
            chunk(b"IDAT",zlib.compress(raw,9))+chunk(b"IEND",b""))

def build(disc:Path,outdir:Path):
    pixels,width=compose(source_atlas(disc))
    packed=pack4(pixels,width)
    outdir.mkdir(parents=True,exist_ok=True)
    (outdir/"ISS26_Cape_original_font_4bpp.bin").write_bytes(packed)
    (outdir/"ISS26_Cape_original_font_preview.png").write_bytes(preview(pixels,width))
    summary={
        "status":"Original-font art candidate, not a Test14 game patch",
        "text":"Cape","width_px":width,"height_px":16,
        "size_bytes":len(packed),"4bpp_indices":sorted(set(pixels)),
        "sha256_4bpp":sha(packed),
        "source_disc_sha256":CLEAN_SHA,"source_atlas_sha256":ATLAS_SHA,
        "glyph_sources":GLYPHS,"overlap_px":OVERLAP,
        "test13_sprite_uv_unverified":True,"original_modified":False
    }
    (outdir/"ISS26_Cape_source_report.json").write_text(
        json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-track",type=Path,required=True)
    parser.add_argument("--outdir",type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.clean_track,args.outdir),indent=2))
if __name__=="__main__":
    main()
