#!/usr/bin/env python3
"""ISS26 Test14: read-only matching of actual PS1 prematch names to Test13 atlas.

Input: verified clean EU Track01 + pinned Test13 XOR patch + Academy VRAM.
The GPU draw rectangles come from Test12's verified stadium-intro GPUDUMP.
Never modifies an ISO, ZIP, VRAM capture, stable channel, or patch.
An exact match is NOT proof that a specific team or patch version was running.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from probe_v095_name_gpu_atlas import (
    CLEAN_SHA,TEST13_SHA,PATCH_URL,GROUPS,
    file_sha,parse_patch,directory_files,resource_data,sha,
)
from v095_name_lz_codec import decode_atlas, atlas_records

WORD_X=704
TPAGE=523
CLUT=31939
FIRST=(128,40,128,16)
SECOND=(128,56,88,16)
V1=1024*512*2
V2=1024*1024*2
ATLAS_SHA="01B9CCAAC6FF79372E30A3595AA98B9E41E6A6BA508ABABE77362829CF13300E"

def pixel(buf:bytes,w:int,x:int,y:int)->int:
    return (buf[(y*w+x)//2]>>(4*(x&1)))&15

def vram_4bpp(raw:bytes,rect:tuple[int,int,int,int])->bytes:
    if len(raw) not in (V1,V2):
        raise ValueError("VRAM dump must be legacy 1MB or Redux 2MB")
    u,v,w,h=rect
    if not (u>=0 and v>=0 and w>0 and w%2==0 and h==16 and u+w<=256 and v+h<=256):
        raise ValueError("Unexpected prematch name UV box")
    out=bytearray(w*h//2)
    for y in range(h):
        for x in range(w):
            tex_x=u+x
            offset=((y+v)*1024+WORD_X+(tex_x//4))*2
            val=int.from_bytes(raw[offset:offset+2],"little")
            nib=(val>>(4*(tex_x%4)))&15
            at=(y*w+x)//2
            out[at]|=nib<<(4*(x&1))
    return bytes(out)

def bbox(buf:bytes,w:int)->list[int]|None:
    coords=[(x,y) for y in range(16) for x in range(w) if pixel(buf,w,x,y)]
    if not coords:
        return None
    a=min(x for x,y in coords);b=max(x for x,y in coords)
    c=min(y for x,y in coords);d=max(y for x,y in coords)
    return [a,c,b-a+1,d-c+1]

def exact_matches(crop:bytes,w:int,tiles:list[bytes],max_found:int=3)->list[dict]:
    if len(crop)!=w*16//2 or not any(crop):
        return []
    nonzero=[(x,y,pixel(crop,w,x,y)) for y in range(16)
             for x in range(w) if pixel(crop,w,x,y)]
    if not nonzero:
        return []
    anchor=nonzero[len(nonzero)//2]
    cx,cy,cv=anchor
    hits=[]
    for n,tile in enumerate(tiles):
        if len(tile)!=8192:
            raise ValueError("Invalid 128x128 indexed name atlas block")
        for y in range(113):
            for x in range(129-w):
                if pixel(tile,128,x+cx,y+cy)!=cv:
                    continue
                found=True
                for dy in range(16):
                    for dx in range(w):
                        if pixel(tile,128,x+dx,y+dy)!=pixel(crop,w,dx,dy):
                            found=False
                            break
                    if not found:break
                if found:
                    hits.append({"tile":n,"x":x,"y":y})
                    if len(hits)>=max_found:
                        return hits
    return hits

def run(clean:Path,patch_file:Path|None,vram_file:Path)->dict:
    if file_sha(clean)!=CLEAN_SHA:
        raise ValueError("Unsupported clean Track01 SHA256")
    if patch_file:
        patch=patch_file.read_bytes()
    else:
        with urllib.request.urlopen(PATCH_URL,timeout=45) as response:
            patch=response.read(4*1024*1024+1)
        if len(patch)>4*1024*1024:
            raise ValueError("Unexpected patch download size")
    rows=parse_patch(patch)
    with clean.open("rb") as f:
        names=directory_files(f)
        all_digest=[]
        for key,lbas in GROUPS.items():
            lba,size=names[key]
            old,new,scope=resource_data(f,lba,size,rows)
            if scope!=set(lbas) or sha(new)!=ATLAS_SHA:
                raise ValueError("Test13 atlas or source sector guard mismatch")
            decoded=decode_atlas(new)
            all_digest.append([sha(tile) for tile in decoded])
            if len(all_digest)==1:
                tiles=decoded
    if not(all_digest[0]==all_digest[1]==all_digest[2]):
        raise ValueError("Unexpected E/F/G name atlas mismatch")
    raw=vram_file.read_bytes()
    words={}
    for name,rect in (("cabo",FIRST),("verde",SECOND)):
        pixels=vram_4bpp(raw,rect)
        hits=exact_matches(pixels,rect[2],tiles)
        words[name]={"uv":list(rect),"indexed_sha256":sha(pixels),
                     "local_ink_bbox":bbox(pixels,rect[2]),
                     "exact_hits":hits,"unique":len(hits)==1}
    return {
        "schema_version":1,"original_track_sha256":CLEAN_SHA,
        "pinned_test13_patch_sha256":TEST13_SHA,
        "test13_name_atlas_sha256":ATLAS_SHA,
        "gpu_name_tpage":TPAGE,"gpu_name_clut":CLUT,
        "name_page_base_vram_words":[WORD_X,0],
        "clut_vram_words":[(CLUT&63)*16,CLUT>>6],
        "words":words,"both_unique":all(v["unique"] for v in words.values()),
        "patch_generated":False,"original_modified":False,
        "notice":"Exact pixel provenance only; verify actual patch version and screen art before patching",
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--test13",type=Path,help="Pinned Test13 release; download if absent")
    p.add_argument("--vram",required=True,type=Path,help="Single Academy .vram file")
    p.add_argument("--output",type=Path,default=Path("ISS26-Test14-NameOrigin.json"))
    a=p.parse_args()
    report=run(a.clean_track,a.test13,a.vram)
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("Name atlas matches:",{k:v["exact_hits"] for k,v in report["words"].items()})
    print("Saved:",a.output)

if __name__=="__main__":main()
