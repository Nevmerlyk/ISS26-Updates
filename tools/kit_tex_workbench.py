#!/usr/bin/env python3
"""ISS26 Kit Workbench v0.1 -- strict candidate TEX parser, preview and guarded CLUT edits.

EU format is NOT verified until the user's original and matching gameplay
evidence pass. Related WE2002 research:
https://github.com/hiitsgabe/retro_roster_patcher/blob/main/src/retro_roster_patcher/games/we2002/jersey_tex.py
Slot order is a hypothesis; no WE2002 executable offsets or team IDs are used.
Never writes a disc, a release, or its input file.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
import sys
import zlib
from pathlib import Path
from kit_resource_probe import (RawPS1ISO, digest_file, EXPECTED_ORIGINAL_HASH,
    decode_stream, original_track_from_cue, ORIGINAL_CUE, snapshots, vram_rect)

BASE=0x800F0000
ROLES={0:"home_top",1:"home_player_clut",2:"away_top",3:"away_player_clut",
       4:"home_gk_clut",5:"away_gk_clut",7:"crowd_flag",8:"crowd_flag_clut",
       9:"home_bottom",10:"away_bottom",11:"shared"}
PAGES={0,2,9,10}
PALETTES={1,3,4,5}
MAX_TEX=256*1024

def require(ok,msg):
    if not ok:raise ValueError(msg)

def sha(b):
    return hashlib.sha256(b).hexdigest().upper()

def parse_tex(data):
    require(48<=len(data)<=MAX_TEX,"Unsupported TEX size")
    header=struct.unpack_from("<12I",data)
    require(header[6]==0,"Unexpected slot 6; unknown TEX layout")
    records={}
    for i,name in ROLES.items():
        off=header[i]-BASE
        require(off>=48 and off%4==0 and off+32<=len(data),f"Slot {i}: bad list pointer")
        kind,x,y,w,h,pad,ptr=struct.unpack_from("<6HI",data,off)
        require(struct.unpack_from("<H",data,off+16)[0]==0xff,f"Slot {i}: not a one-record list")
        start=ptr-BASE
        require(start>=48 and start%4==0 and start<off,f"Slot {i}: bad data pointer")
        require(0<=x<1024 and 0<=y<512 and 0<w<=1024-x and 0<h<=512-y,
                f"Slot {i}: invalid VRAM rectangle")
        k=kind&255
        require(k in (0,9,10),f"Slot {i}: unknown record kind")
        if i in PAGES:require(k==10 and (w,h)==(64,128),f"Slot {i}: not candidate 8bpp page half")
        if i in PALETTES:require(k in (0,9) and w*h==256,f"Slot {i}: not candidate 256-color CLUT")
        records[i]={"name":name,"slot":i,"kind":kind,"listOffset":off,
                    "offset":start,"rectWords":[x,y,w,h]}
    # Strict variant: no stream/list aliases, crossovers or unknown header.
    boundaries=sorted([r["listOffset"] for r in records.values()]+
                      [r["offset"] for r in records.values()]+[len(data)])
    require(len(boundaries)==len(set(boundaries)) and boundaries[0]==48,
            "Shared or unrecognized TEX layout")
    for i,r in records.items():
        x,y,w,h=r["rectWords"]; start=r["offset"]; off=r["listOffset"]
        stop=boundaries[boundaries.index(start)+1]
        require(off+32<=boundaries[boundaries.index(off)+1],"Overlapping TEX list")
        require(stop<=off,"TEX stream/list collision")
        n=w*h*2
        if r["kind"]&255==10:
            payload=decode_stream(data[start:stop],expected_bytes=n,max_padding=stop-start)
        else:
            require(start+n<=stop,"Truncated TEX raw block")
            payload=data[start:start+n]
        r["data"]=payload;r["sha256"]=sha(payload);r["storedSpan"]=stop-start
    return records

def public_records(records):
    return [{k:v for k,v in r.items() if k!="data"} for _,r in sorted(records.items())]

def rgb(v):
    return tuple(((v>>k)&31)*255//31 for k in (0,5,10))

def color_word(code,old):
    require(isinstance(code,str) and re.fullmatch(r"#[0-9a-fA-F]{6}",code),"Expected #RRGGBB")
    vals=[(int(code[i:i+2],16)*31+127)//255 for i in (1,3,5)]
    v=vals[0]|vals[1]<<5|vals[2]<<10|(old&0x8000)
    require(v!=0,"Opaque color would become transparent, choose a nonzero RGB555 color")
    return v

def png(path,w,h,rgba):
    def chunk(k,b):
        return struct.pack(">I",len(b))+k+b+struct.pack(">I",zlib.crc32(k+b)&0xffffffff)
    raw=b"".join(b"\0"+rgba[y*w*4:(y+1)*w*4] for y in range(h))
    out=b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",struct.pack(">2I5B",w,h,8,6,0,0,0))
    out+=chunk(b"IDAT",zlib.compress(raw,9))+chunk(b"IEND",b"")
    with path.open("xb") as f:f.write(out)

def render_page(records,which,gk):
    a,b,p=(0,9,4 if gk else 1) if which=="home" else (2,10,5 if gk else 3)
    pixels=records[a]["data"]+records[b]["data"]
    palette=struct.unpack("<256H",records[p]["data"])
    require(len(pixels)==128*256,"Wrong page length")
    return b"".join(bytes((*rgb(palette[i]),0 if not palette[i] else 255)) for i in pixels)

def export_previews(records,out):
    out.mkdir(parents=True,exist_ok=False)
    for which in ("home","away"):
        for gk in (False,True):
            png(out/(which+("_gk" if gk else "_player")+"_candidate.png"),
                128,256,render_page(records,which,gk))
    # Previews show the indexed atlas through each palette, NOT a 3D render.

def correlate(records,images):
    hits=[]
    for archive,label,ram,vram in images:
        for i,r in records.items():
            x,y,w,h=r["rectWords"];data=r["data"]
            if len(set(data))<8:continue
            if vram_rect(vram,x,y,w,h)==data:
                hits.append({"archive":archive,"capture":label,"slot":i,
                             "sha256":sha(data),"rectWords":[x,y,w,h]})
    return hits

def inventory(track,archives):
    require(digest_file(track)==EXPECTED_ORIGINAL_HASH,"Wrong clean EU Track01 SHA256")
    images=list(snapshots(archives))
    rows=[]
    with RawPS1ISO(track) as disc:
        files,_=disc.list_files()
        for path,e in sorted(files.items()):
            if e.is_dir or not re.fullmatch(r"TEX_\d+\.BIN",path.split("/")[-1],re.I):continue
            row={"resource":path,"lba":e.lba,"size":e.size}
            try:
                require(e.size<=MAX_TEX and disc.fits_track(e),"Unsafe TEX extent")
                data=b"".join(disc.file_chunks(e))
                row["sha256"]=sha(data)
                r=parse_tex(data)
                row.update(layout="candidate_match",records=public_records(r),
                           exactVramMatches=correlate(r,images))
            except (OSError,ValueError,struct.error) as ex:
                row.update(layout="unknown",reason=str(ex))
            rows.append(row)
    return {"schemaVersion":1,"sourceTrackSha256":EXPECTED_ORIGINAL_HASH,
            "pairedCaptures":len(images),"texCount":len(rows),
            "candidateLayouts":sum(r["layout"]=="candidate_match" for r in rows),
            "teamAndRoleMappingVerified":False,"resources":rows}

def palette_edit(data,plan):
    require(plan.get("schemaVersion")==1 and plan.get("sourceSha256")==sha(data),
            "Resource source guard failed")
    require(plan.get("europeanLayoutVerified") is True and plan.get("teamRoleVerified") is True,
            "Manual EU team and role verification required")
    evidence=plan.get("evidence")
    require(isinstance(evidence,list) and len(evidence)>=2 and
            all(isinstance(e,str) and e.strip() for e in evidence) and len(set(evidence))>=2,
            "Provide distinct gameplay evidence references")
    records=parse_tex(data); result=bytearray(data);authorized=set()
    seen=set()
    for edit in plan["edits"]:
        slot=edit["slot"];require(type(slot) is int and slot in PALETTES and slot not in seen,
                                 "Invalid/duplicate palette role")
        seen.add(slot);r=records[slot]
        require(edit["expectedSha256"]==r["sha256"] and edit["role"]==r["name"],
                "Palette source/role mismatch")
        # Preserve transparent and reserved number indices. Additional protected
        # indices (skin, shared accessories etc.) are supplied by observed UV map.
        allowed=edit["verifiedClothingIndices"]
        protected=edit["protectedIndices"]
        require(all(type(i) is int and 1<=i<240 for i in allowed) and
                all(type(i) is int and 0<=i<256 for i in protected),
                "Invalid palette index policy")
        require(not(set(allowed)&set(protected)),"Overlapping palette index policy")
        for key,value in edit["colors"].items():
            require(re.fullmatch(r"(0|[1-9]\d*)",key) is not None,"Invalid palette index")
            i=int(key)
            require(i in allowed and i not in protected,"Unverified or protected palette index")
            at=r["offset"]+i*2;old=struct.unpack_from("<H",data,at)[0]
            require(old!=0,"Preserve transparent original color")
            struct.pack_into("<H",result,at,color_word(value,old))
            authorized.update((at,at+1))
    require(authorized,"No edits specified")
    out=bytes(result);after=parse_tex(out)
    require(len(out)==len(data),"Unexpected resource size")
    require(all(a==b or i in authorized for i,(a,b) in enumerate(zip(data,out))),
            "Modification outside approved palette")
    for i,r in records.items():
        require(all(after[i][k]==r[k] for k in ("kind","listOffset","offset","rectWords","storedSpan")),
                "Descriptor changed")
        if i not in seen:require(after[i]["data"]==r["data"],"Unexpected block change")
    return out,{"sourceSha256":sha(data),"resultSha256":sha(out),
        "changedBytes":sum(a!=b for a,b in zip(data,out)),
        "changedPaletteSlots":sorted(seen),"protectedFlagSlots":[7,8],
        "inputUnmodified":True,"gamePatchProduced":False,"emulatorTested":False}

def selftest():
    # 16-bit-word palette geometry and protection tests; mock TEX fixture only.
    def literal(data):
        tokens=[(0,bytes([v])) for v in data]+[(1,b"\xff")]
        result=bytearray()
        for i in range(0,len(tokens),8):
            group=tokens[i:i+8];result.append(sum(bit<<j for j,(bit,_) in enumerate(group)))
            result.extend(b"".join(payload for _,payload in group))
        return bytes(result)
    tex=bytearray(48)
    for i in ROLES:
        if i in PAGES:
            w,h,k=64,128,10
            raw=literal(bytes([1])*16384)
        elif i in PALETTES:
            w,h,k=256,1,0xff09
            raw=struct.pack("<256H",0,*([0x801f]*255))
        else:
            w,h,k=8,8,0
            raw=bytes([0x13])*128
        pos=len(tex);tex+=raw+bytes(-len(raw)%4);off=len(tex)
        tex+=struct.pack("<6HI",k,0,0,w,h,0,BASE+pos)
        tex+=struct.pack("<6HI",255,0,0,0,0,0,0)
        struct.pack_into("<I",tex,i*4,BASE+off)
    data=bytes(tex);r=parse_tex(data)
    assert len(r)==11 and len(render_page(r,"home",False))==128*256*4
    plan={"schemaVersion":1,"sourceSha256":sha(data),"europeanLayoutVerified":True,
          "teamRoleVerified":True,"evidence":["synthetic-a","synthetic-b"],"edits":[
          {"slot":1,"role":r[1]["name"],"expectedSha256":r[1]["sha256"],
           "verifiedClothingIndices":[1],"protectedIndices":[2,240],
           "colors":{"1":"#00FF00"}}]}
    edited,report=palette_edit(data,plan)
    assert report["changedBytes"]>0 and parse_tex(edited)[7]["data"]==r[7]["data"]
    assert struct.unpack_from("<H",edited,r[1]["offset"]+2)[0]==0x83e0
    plan["edits"][0]["colors"]["240"]="#ffffff"
    try:palette_edit(data,plan)
    except ValueError:pass
    else:raise AssertionError("Reserved-index guard failed")
    print("PASS: synthetic TEX parser, preview sizing, CLUT and flag protection")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="mode",required=True)
    scan=sub.add_parser("inventory");scan.add_argument("--track",type=Path)
    scan.add_argument("--root",type=Path,default=Path(r"D:\ISS 26"))
    scan.add_argument("--archive",type=Path,action="append",default=[])
    scan.add_argument("--out",type=Path,required=True)
    preview=sub.add_parser("preview");preview.add_argument("tex",type=Path)
    preview.add_argument("--out",type=Path,required=True)
    edit=sub.add_parser("palette-edit");edit.add_argument("tex",type=Path)
    edit.add_argument("--plan",type=Path,required=True);edit.add_argument("--out",type=Path,required=True)
    sub.add_parser("self-test")
    args=p.parse_args()
    if args.mode=="self-test":selftest();return
    if args.mode=="inventory":
        require(len(args.archive)<=4,"Too many archives")
        track=args.track or original_track_from_cue(args.root/ORIGINAL_CUE)
        archives=args.archive or sorted((args.root/"ISS26_Data"/"explorer"/"archives").glob("*.zip"),
            key=lambda p:p.stat().st_mtime,reverse=True)[:4]
        report=inventory(track,archives)
        with args.out.open("x",encoding="utf-8") as f:json.dump(report,f,indent=2)
        print("Candidate layouts:",report["candidateLayouts"],"/",report["texCount"])
    elif args.mode=="preview":
        export_previews(parse_tex(args.tex.read_bytes()),args.out)
    else:
        data,report=palette_edit(args.tex.read_bytes(),json.loads(args.plan.read_text(encoding="utf-8")))
        with args.out.open("xb") as f:f.write(data)
        print(json.dumps(report,indent=2))
if __name__=="__main__":
    try:main()
    except (OSError,ValueError,KeyError,struct.error) as ex:
        print("STOP:",ex,file=sys.stderr);sys.exit(1)
