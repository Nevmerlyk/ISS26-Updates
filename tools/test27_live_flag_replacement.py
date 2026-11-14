#!/usr/bin/env python3
"""Test27: reversible, isolated flag replacement in a PAUSED local PCSX-Redux.

Uses only the documented loopback GPU REST API. No disc, ROM, patch feed,
RAM, atlas, controller or save writes. Accepts only the exact known Test25
Cape Verde/Bosnia source, stage and CLUT fingerprints from the owner report.
This is a real *temporary VRAM visual experiment*, NOT a BIN/CUE patch.
The matching CLUT addresses might be used by unrelated primitives. Inspect
for regressions; resume only after a successful readback; restart to discard.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from test27_flag_art_4bpp import candidate

STRIDE=1024*2
VRAM_SIZES={STRIDE*512,STRIDE*1024}
CLUT_SHA="DA3484BF49560D2CD1306FE3CCC59B5417A54AA370859DDB6C77EAE523361B88"

@dataclass(frozen=True)
class Rect:
    name: str
    x: int
    y: int
    w: int
    h: int

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest().upper()

CAPE_ATLAS=Rect("cape_atlas_guard",848,256,16,28)
BOSNIA_ATLAS=Rect("bosnia_atlas_guard",816,368,16,28)
CAPE_STAGE=Rect("cape_stage",560,0,16,28)
BOSNIA_STAGE=Rect("bosnia_stage",560,28,16,28)
CAPE_CLUT=Rect("cape_clut",0,505,16,1)
BOSNIA_CLUT=Rect("bosnia_clut",224,506,16,1)
WRITES=(CAPE_STAGE,BOSNIA_STAGE,CAPE_CLUT,BOSNIA_CLUT)
GUARDS={
    CAPE_ATLAS:"AE9E179ED66CA388C634ACB3587EC1D5369EA083853E00417A14C38EBF91E102",
    BOSNIA_ATLAS:"61B31724E3C5D5B212BB26DF1B716F904A2F4D18A4A1B59E4CF3160D0FBE27E6",
    CAPE_STAGE:"AE9E179ED66CA388C634ACB3587EC1D5369EA083853E00417A14C38EBF91E102",
    BOSNIA_STAGE:"C8E0DEDB8BEBB96AD536A964B98445DC972130E53C6A16BA74EADC1143C245BC",
    CAPE_CLUT:CLUT_SHA,BOSNIA_CLUT:CLUT_SHA,
}

def extract(vram:bytes,r:Rect)->bytes:
    if len(vram) not in VRAM_SIZES or min(r.x,r.y)<0 or min(r.w,r.h)<1 or r.x+r.w>1024 or r.y+r.h>512:
        raise ValueError("Unsupported VRAM size or out-of-range PS1 rectangle")
    return b"".join(vram[(r.y+i)*STRIDE+r.x*2:(r.y+i)*STRIDE+(r.x+r.w)*2] for i in range(r.h))

def replaced(vram:bytes,rect:Rect,data:bytes)->bytes:
    extract(vram,rect)
    if len(data)!=rect.w*rect.h*2:
        raise ValueError("Wrong rectangle payload length")
    out=bytearray(vram)
    for i in range(rect.h):
        a=(rect.y+i)*STRIDE+rect.x*2
        out[a:a+rect.w*2]=data[i*rect.w*2:(i+1)*rect.w*2]
    return bytes(out)

def artwork()->dict[Rect,bytes]:
    cape,cp,_,_=candidate("cape_verde")
    bosnia,bp,_,_=candidate("bosnia")
    return dict(zip(WRITES,(cape,bosnia,cp,bp)))

def make_plan(vram:bytes,guards=GUARDS)->dict[Rect,bytes]:
    if set(guards)!=set(GUARDS):
        raise ValueError("Incomplete guard set")
    wrong=[r.name for r,expected in guards.items() if sha(extract(vram,r))!=expected]
    if wrong:
        raise ValueError("Wrong match/frame or atlas/CLUT has changed; no write: "+", ".join(wrong))
    return artwork()

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError("Refusing HTTP redirect from local emulator")

class LocalRedux:
    def __init__(self,port:int):
        if not 1<=port<=65535:
            raise ValueError("Invalid local port")
        self.url=f"http://127.0.0.1:{port}/api/v1/"
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def request(self,path,data=None,limit=2*1024*1024+1):
        req=urllib.request.Request(self.url+path,data=data,method="GET" if data is None else "POST")
        if data is not None:
            req.add_header("Content-Type","application/octet-stream")
        with self.opener.open(req,timeout=8) as response:
            blob=response.read(limit+1)
            if len(blob)>limit:
                raise ValueError("Unexpected oversized API response")
            return blob
    def paused(self):
        status=json.loads(self.request("execution-flow",limit=16384))
        return status.get("running") is False
    def vram(self):
        raw=self.request("gpu/vram/raw")
        if len(raw) not in VRAM_SIZES:
            raise ValueError("Unexpected VRAM size from PCSX-Redux")
        return raw
    def write(self,r,data):
        if r not in WRITES or len(data)!=r.w*r.h*2:
            raise ValueError("Refusing non-allowlisted VRAM write")
        self.request(f"gpu/vram/raw?x={r.x}&y={r.y}&width={r.w}&height={r.h}",data,limit=16384)

def need_paused(client):
    if not client.paused():
        raise ValueError("Pause emulation in PCSX-Redux first. No writes performed while running.")

def capture(client):
    need_paused(client)
    raw=client.vram()
    need_paused(client)
    return raw

def backup_data(before,plan):
    return {
        "schemaVersion":1,"kind":"ISS26 Test27 temporary VRAM rollback; local only",
        "rectangles":{r.name:{"before":extract(before,r).hex(),"after":plan[r].hex()}
                      for r in WRITES},
        "source_atlas_modified":False,"game_patch_built":False,
    }

def read_backup(path,guards=GUARDS):
    if path.stat().st_size>16384:
        raise ValueError("Oversized backup")
    data=json.loads(path.read_text(encoding="utf-8"))
    if data.get("schemaVersion")!=1 or set(data.get("rectangles",{}))!={r.name for r in WRITES}:
        raise ValueError("Wrong local VRAM backup")
    before={}; after=artwork()
    for r in WRITES:
        row=data["rectangles"][r.name]
        before[r]=bytes.fromhex(row["before"])
        if sha(before[r])!=guards[r] or bytes.fromhex(row["after"])!=after[r]:
            raise ValueError("Backup guard mismatch")
    return before,after

def exact_writes(client,start,changes):
    if set(changes)!={r for r in WRITES}:
        raise ValueError("Incomplete write set")
    expected=start
    for r in WRITES:
        expected=replaced(expected,r,changes[r])
    # Refuse to overwrite after a frame change, even between preflight and apply.
    if capture(client)!=start:
        raise ValueError("VRAM changed since preflight; no write")
    for r in WRITES:
        need_paused(client)
        client.write(r,changes[r])
    if capture(client)!=expected:
        raise ValueError("GPU readback mismatch: unexpected bytes or incomplete write")
    return expected

def rollback(client,before,after):
    now=capture(client)
    for r in WRITES:
        if extract(now,r) not in (before[r],after[r]):
            raise ValueError("Live state is no longer rollback-safe; restart Test Game without saving state")
    return exact_writes(client,now,before)

def apply(client,backup:Path,guards=GUARDS):
    start=capture(client)
    plan=make_plan(start,guards)
    before={r:extract(start,r) for r in WRITES}
    backup.parent.mkdir(parents=True,exist_ok=True)
    # Never overwrite a prior rollback file. It is local and never uploaded.
    with backup.open("x",encoding="utf-8") as f:
        json.dump(backup_data(start,plan),f,indent=2)
    try:
        final=exact_writes(client,start,plan)
    except Exception as exc:
        try:
            rollback(client,before,plan)
        except Exception as restore_error:
            raise RuntimeError("Preview failed and rollback not verified. RESTART the emulator without saving state. "
                               +str(restore_error)) from exc
        raise RuntimeError("Preview failed; original four rectangles restored: "+str(exc)) from exc
    return {"patched_rectangles":[r.name for r in WRITES],
            "changed_vram_bytes":sum(a!=b for a,b in zip(start,final)),
            "all_other_vram_bytes_unchanged_while_paused":True,
            "source_atlas_unchanged":True,"game_patch_built":False,
            "source_disc_modified":False,"visual_correctness_verified":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port",type=int,default=8080)
    p.add_argument("--backup",type=Path,default=Path("Test27_LiveFlagRollback.json"))
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check",action="store_true",help="Verify exact paused-state fingerprints, no writes")
    group.add_argument("--apply",action="store_true",help="Replace four VRAM rectangles temporarily")
    group.add_argument("--restore",action="store_true",help="Restore original four rectangles if still safe")
    args=p.parse_args()
    client=LocalRedux(args.port)
    if args.check:
        make_plan(capture(client))
        print("MATCH: exact known Cape Verde/Bosnia atlas, stage and CLUT. No writes.")
    elif args.apply:
        print(json.dumps(apply(client,args.backup),indent=2))
        print("Verified temporary VRAM replacement. Emulator remains paused. Resume for visual review; restart to discard.")
    else:
        before,after=read_backup(args.backup)
        rollback(client,before,after)
        print("Original four VRAM rectangles restored and verified. No disc writes.")

if __name__=="__main__":
    main()
