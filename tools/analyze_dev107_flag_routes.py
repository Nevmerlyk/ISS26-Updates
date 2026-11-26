#!/usr/bin/env python3
"""DEV107: read-only correlation of prematch and HUD draws, CLUT and RAM.

Use existing Academy session ZIP. No extraction, no phase guesses, no writes
to original BIN, RAM or VRAM. GPU traces and snapshots are joined by exact
member stem in the same directory. Draw overlap is a candidate, not proof of
the depicted object; byte equality is not proof of the last writer.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path, PurePosixPath
from analyze_flag_test12_phases import safe_archive_files
from parse_v095_gpudump import GP0Inspector, packet_iter, TRACE_BEGIN, VSYNC, GP0, MAX_BYTES

SURFACES = {
    "home_large": (560, 0, 16, 28),
    "away_large": (560, 28, 16, 28),
    "home_hud": (640, 98, 6, 8),
    "away_hud": (646, 98, 6, 8),
}
RAM = {"home_large": 0xCC600, "away_large": 0xCC980}
def digest(b):
    return hashlib.sha256(b).hexdigest()

def rect(raw, x, y, w, h):
    if len(raw) not in (1048576, 2097152):
        raise ValueError("unsupported VRAM size")
    if not (0 <= x < x+w <= 1024 and 0 <= y < y+h <= len(raw)//2048):
        raise ValueError("invalid VRAM rectangle")
    return b"".join(raw[(j*1024+x)*2:(j*1024+x+w)*2] for j in range(y,y+h))

def routes(raw):
    if len(raw)>MAX_BYTES:
        raise ValueError("GPU trace size cap")
    ins=GP0Inspector()
    live=False
    for kind, words in packet_iter(raw):
        if not live:
            live=kind==TRACE_BEGIN
            continue
        if kind==GP0:
            ins.feed(words)
        elif kind==VSYNC:
            ins.frame+=1
        elif kind==1:
            for word in words:
                if word>>24 in (0,1):
                    ins.pending.clear()
                    if word>>24==0: ins.last_texpage=None
    output={k:[] for k in SURFACES}
    for fields,count in ins.draw_groups.items():
        _,op,px,py,depth,cx,cy,_,_,u0,v0,u1,v1,frame=fields
        if depth!=0: continue
        x0,x1=px+u0//4,px+u1//4
        y0,y1=py+v0,py+v1
        for name,(x,y,w,h) in SURFACES.items():
            if x0<=x+w-1 and x1>=x and y0<=y+h-1 and y1>=y:
                output[name].append({"frame":frame,"opcode":op,"clut":[cx,cy],
                    "bounds_words":[x0,y0,x1,y1],"count":count,
                    "contained":x<=x0<=x1<x+w and y<=y0<=y1<y+h})
    return {"trace_begin":live,"unparsed":dict(ins.unparsed),
            "incomplete_words":len(ins.pending),"surfaces":output}

def common_clut(samples,side):
    large,hud=(side+"_large",side+"_hud")
    def seen(surface):
        return {tuple(d["clut"]) for s in samples
                for d in s.get("gpu",{}).get("surfaces",{}).get(surface,[])
                if d["contained"]}
    a,b=seen(large),seen(hud)
    return {"large_candidates":sorted(a),"hud_candidates":sorted(b),
            "shared_candidates":sorted(a&b),"unique_shared_route":len(a)==len(b)==1 and a==b}

def analyze(path):
    rows=[]
    with zipfile.ZipFile(path) as z:
        entries=safe_archive_files(z)
        byname={}
        for e in entries:
            k=e.filename.replace("\\","/").lower()
            if k in byname: raise ValueError("duplicate ZIP member")
            byname[k]=e
        for k,e in sorted(byname.items()):
            if not k.endswith(".vram"):continue
            if len(rows)>=256:raise ValueError("capture cap")
            if e.file_size not in (1048576,2097152):continue
            stem=k[:-5]
            raw=z.read(e)
            ram_e=byname.get(stem+"_ram.bin")
            ram=z.read(ram_e) if ram_e and ram_e.file_size==2097152 else None
            gpd=byname.get(stem+".gpd")
            row={"capture":PurePosixPath(stem).name,"phase_verified":False,
                 "vram_bytes":len(raw),"surfaces":{}}
            for name,(x,y,w,h) in SURFACES.items():
                data=rect(raw,x,y,w,h)
                record={"sha256":digest(data),"nonzero_bytes":sum(b!=0 for b in data)}
                if name in RAM and ram is not None:
                    address=RAM[name]
                    record["ram_address"]=hex(0x80000000+address)
                    record["ram_equal_bytes"]=sum(a==b for a,b in zip(data,ram[address:address+len(data)]))
                    record["ram_total_bytes"]=len(data)
                row["surfaces"][name]=record
            if gpd:
                try:row["gpu"]=routes(z.read(gpd))
                except (ValueError,struct.error) as ex:row["gpu_error"]=str(ex)[:180]
            rows.append(row)
    return {"schemaVersion":1,"capture_count":len(rows),"captures":rows,
            "home":common_clut(rows,"home"),"away":common_clut(rows,"away"),
            "last_writer_verified":False,"disc_sha_verified":False,
            "notice":"Exact capture-name pairing only; scene labels and last writer need independent evidence."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive",type=Path)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    result=analyze(a.archive)
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Captures:",result["capture_count"],"CLUT candidates:",result["home"],result["away"])
if __name__=="__main__":
    main()
