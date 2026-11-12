#!/usr/bin/env python3
"""ISS26 v0.9.5: read-only prematch-name GPU upload layout probe.

Reads the user's CLEAN EU PS1 Track01 plus the *published* standalone Test13
ISS26X01 sector-XOR patch. Verifies both SHA256s and every source-sector guard.
Reconstructs only BIN/T_NAME_E/F/G.BIN in memory, enumerates the game-style GPU
upload command lists, and reports layout/pointer metadata. Never writes game
bytes, copied textures, source discs, or any patched ISO to disk.

A GPU upload rectangle is NOT an on-screen draw primitive; the reporter does
not claim to know texture UV/CLUT, text placement, or the intended new glyphs.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import urllib.request

CLEAN_SHA="D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
TEST13_SHA="159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214"
PATCH_URL=("https://github.com/Nevmerlyk/ISS26-Updates/releases/download/"
           "v0.9.5-largeflag-source-test13/"
           "ISS26_0.9.5_LargeFlagSource_TEST13.iss26p")
SECTOR=2352
FORM1=2048
FORM2=2324
RECORD=2388
GPU_BASE=0x800F0000
GROUPS={
    "BIN/T_NAME_E.BIN":tuple(range(8200,8228)),
    "BIN/T_NAME_F.BIN":tuple(range(8230,8258)),
    "BIN/T_NAME_G.BIN":tuple(range(8260,8288)),
}

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest().upper()

def file_sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        while part:=stream.read(4*1024*1024):
            h.update(part)
    return h.hexdigest().upper()

def raw_sector(file,lba:int)->bytes:
    file.seek(lba*SECTOR)
    raw=file.read(SECTOR)
    if (len(raw)!=SECTOR or raw[:12]!=b"\0"+b"\xff"*10+b"\0"
            or raw[15]!=2):
        raise ValueError(f"Invalid PS1 Mode2/2352 sector at LBA {lba}")
    return raw

def user_data(raw:bytes)->bytes:
    form2=bool(raw[18]&0x20)
    return raw[24:24+(FORM2 if form2 else FORM1)]

def directory_files(file)->dict[str,tuple[int,int]]:
    """Inspect catalog only. Ignore unrelated invalid out-of-track CDDA entries."""
    pvd=user_data(raw_sector(file,16))
    if pvd[:7]!=b"\x01CD001\x01":
        raise ValueError("Missing ISO9660 PVD at LBA 16")
    result={}
    visited=set()
    def record(blob:bytes,at:int):
        length=blob[at]
        if length<34 or at+length>len(blob):
            raise ValueError("Malformed ISO9660 directory record")
        r=blob[at:at+length]
        lba=int.from_bytes(r[2:6],"little")
        size=int.from_bytes(r[10:14],"little")
        if (lba!=int.from_bytes(r[6:10],"big") or
            size!=int.from_bytes(r[14:18],"big")):
            raise ValueError("Inconsistent ISO9660 extent metadata")
        n=r[32]
        if 33+n>len(r):
            raise ValueError("Malformed ISO filename")
        name=r[33:33+n].split(b";",1)[0].rstrip(b".")
        return lba,size,bool(r[25]&2),name
    def walk(lba:int,size:int,prefix:str,depth:int):
        if depth>8 or (lba,size) in visited or size>4*1024*1024:
            return
        visited.add((lba,size))
        if lba<0 or size<0 or lba+math.ceil(size/2048)>_sector_count[0]:
            return
        data=b"".join(user_data(raw_sector(file,lba+j))
                      for j in range(math.ceil(size/2048)))[:size]
        offset=0
        while offset<len(data):
            if data[offset]==0:
                offset=((offset//FORM1)+1)*FORM1
                continue
            used=data[offset]
            child_lba,child_size,is_dir,name=record(data,offset)
            offset+=used
            if name in (b"\x00",b"\x01"):
                continue
            name=name.decode("ascii",errors="replace")
            qualified=f"{prefix}/{name}" if prefix else name
            result[qualified]=(child_lba,child_size)
            if is_dir:
                walk(child_lba,child_size,qualified,depth+1)
    _sector_count=[file.seek(0,2)//SECTOR]
    root_lba,root_size,_,_=record(pvd,156)
    walk(root_lba,root_size,"",0)
    return result

def parse_patch(raw:bytes)->dict[int,tuple[bytes,bytes]]:
    if sha(raw)!=TEST13_SHA or raw[:8]!=b"ISS26X01":
        raise ValueError("Test13 patch SHA256/signature does not match pinned release")
    n,=struct.unpack_from("<I",raw,8)
    if n!=1492 or len(raw)!=12+n*RECORD:
        raise ValueError("Unexpected Test13 record count/size")
    records={}
    last=-1
    for i in range(n):
        at=12+i*RECORD
        lba,=struct.unpack_from("<I",raw,at)
        if lba<=last or lba>=210951:
            raise ValueError("Invalid, duplicate or unordered LBA")
        records[lba]=(raw[at+4:at+36],raw[at+36:at+RECORD])
        last=lba
    return records

def apply_sector(source:bytes,lba:int,record:tuple[bytes,bytes])->bytes:
    guard,mask=record
    if sha(source)!=guard.hex().upper():
        raise ValueError(f"Original source-sector SHA256 mismatch at LBA {lba}")
    if len(mask)!=SECTOR or any(mask[:24]):
        raise ValueError(f"Unexpected CD header edit at LBA {lba}")
    result=bytes(x^y for x,y in zip(source,mask))
    if result[:24]!=source[:24]:
        raise ValueError("CD sync/address/subheader modified")
    return result

def resource_data(file,lba:int,size:int,patch:dict):
    before=bytearray()
    after=bytearray()
    seen=set()
    current=lba
    while len(before)<size:
        source=raw_sector(file,current)
        new=apply_sector(source,current,patch[current]) if current in patch else source
        count=min(size-len(before),len(user_data(source)))
        before.extend(user_data(source)[:count])
        after.extend(user_data(new)[:count])
        if current in patch:
            seen.add(current)
        current+=1
        if current-lba>64:
            raise ValueError("Name resource unexpectedly exceeds 64 CD sectors")
    return bytes(before),bytes(after),seen

def upload_lists(blob:bytes):
    """Probe documented 16-byte GPU list records; reject invalid candidates."""
    results=[]
    visited=set()
    for at in range(0,min(32,len(blob)-3),4):
        pointer,=struct.unpack_from("<I",blob,at)
        offset=pointer-GPU_BASE
        if not (32<=offset<=len(blob)-16 and offset%4==0) or offset in visited:
            continue
        visited.add(offset)
        rows=[]
        terminated=False
        for n in range(512):
            rec_offset=offset+16*n
            if rec_offset+16>len(blob):
                break
            kind,x,y,w,h,pad,stream=struct.unpack_from("<HHHHHHI",blob,rec_offset)
            if kind==0xff:
                terminated=True
                break
            stream_offset=stream-GPU_BASE
            if ((kind&255) not in (0,9,10) or w>1024 or h>512
                    or not 0<=stream_offset<len(blob)):
                break
            rows.append({
              "kind":kind,"vram_x_words":x,"vram_y":y,
              "upload_width_words":w,"upload_height":h,
              "stream_offset":stream_offset,
              "stream_head_sha256":sha(blob[stream_offset:stream_offset+min(64,len(blob)-stream_offset)]),
            })
        if terminated and rows:
            results.append({"pointer_slot":at,"list_offset":offset,
                            "upload_record_count":len(rows),"uploads":rows})
    return results

def normalized_geometry(lists):
    return [[(r["kind"],r["vram_x_words"],r["vram_y"],
              r["upload_width_words"],r["upload_height"])
             for r in table["uploads"]] for table in lists]

def probe(disc:Path,patch_data:bytes)->dict:
    if file_sha(disc)!=CLEAN_SHA:
        raise ValueError("Only the clean European SLES-03321 Track01 is supported")
    patches=parse_patch(patch_data)
    reports={}
    with disc.open("rb") as source:
        catalog=directory_files(source)
        for name,expected in GROUPS.items():
            if name not in catalog:
                raise ValueError(f"Original ISO does not contain {name}")
            lba,size=catalog[name]
            old,new,seen=resource_data(source,lba,size,patches)
            if seen!=set(expected):
                raise ValueError(f"Unexpected {name} sector coverage: {sorted(seen)}")
            a,b=upload_lists(old),upload_lists(new)
            reports[name]={
                "original_lba":lba,"resource_bytes":size,
                "sha256_original":sha(old),"sha256_test13":sha(new),
                "modified_sector_lbas":sorted(seen),
                "original_upload_lists":a,"test13_upload_lists":b,
                "original_upload_count":sum(x["upload_record_count"] for x in a),
                "test13_upload_count":sum(x["upload_record_count"] for x in b),
                "vram_rectangle_geometry_unchanged":(
                    normalized_geometry(a)==normalized_geometry(b)) if a and b else None,
                "upload_list_detection_confirmed":bool(a and b),
                "layout_notice":("Upload-list coordinates are VRAM destinations, "
                                 "not the draw-screen X positions of 'Cabo' or 'Verde'."),
            }
    return {
      "schema_version":1,"goal":"Cape Verde spelling and spacing; game patch v0.9.5",
      "clean_disc_sha256":CLEAN_SHA,"test13_sha256":TEST13_SHA,
      "resources":reports,
      "verified_on_screen_alignment":False,
      "modifies_game_or_patch":False,
      "next_step":"Use verified GPU upload metadata with a prematch VRAM/draw capture to identify the actual name sprite positions and repack their compressed glyphs."
    }

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clean-track",type=Path,required=True,
                    help="Original EU PS1 Track 01 .bin, NOT patched image")
    ap.add_argument("--test13",type=Path,
                    help="Optional local official Test13 .iss26p (downloaded if absent)")
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    if args.test13:
        patch=args.test13.read_bytes()
    else:
        req=urllib.request.Request(PATCH_URL,headers={"User-Agent":"ISS26-CapeVerde-Probe/1"})
        with urllib.request.urlopen(req,timeout=60) as response:
            patch=response.read(4*1024*1024)
    result=probe(args.clean_track,patch)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    for name,row in result["resources"].items():
        print(f"{name}: original uploads {row['original_upload_count']}; "
              f"Test13 uploads {row['test13_upload_count']}; "
              f"geometry unchanged = {row['vram_rectangle_geometry_unchanged']}")
    print("PASS: clean original + official Test13 verified; no game data changed")

if __name__=="__main__":
    main()
