#!/usr/bin/env python3
"""Build an EXPERIMENTAL, standalone Test27 source-art ISS26X01 candidate.

Reads the owner's clean Track01, authentic Test25 patch, and existing
Academy ZIP. Detects reviewed-format GPU upload targets independently in
DATSEL/DATSEL3 and all 34 original GDCs. The tool never writes game discs,
original artwork or game update feeds. It refuses ambiguous source routes,
style collisions, unsupported palettes, or stream allocation overruns.

This tests source-art replacement ONLY; it does not fix or claim to fix
Bosnia's 12-row runtime staging loss, bonus-team ownership, spectator flags
or full-game visual acceptance. Do not promote the result to stable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
from build_v095_test12_gdc_descriptor_repair import fix_parity, valid_parity
from probe_v095_name_gpu_atlas import CLEAN_SHA, directory_files, raw_sector, apply_sector, file_sha, SECTOR, RECORD
from v095_static_prematch_ram_trace import read_patch
from build_v095_test25_bosnia_style_isolation import TABLE_OFFSETS
from test27_extract_real_flag_pixels import read_snapshot, sha_path, EXPECTED_ZIP_SHA
from analyze_flag_test26_unified import clut
from test27_gpu_stream_edit import (
    sha, TARGETS, CLUT_SHA, parse_uploads, take_tile, rewrite_resource,
    decode_stream, mapped_art,
)

TEST25_SHA="85014C8222A408344704CCD8FC192379645E18770876CF4501324D504D55BA67"
TEST25_COUNT=1492
STYLE_SLOTS={"cape_verde":(0,1),"bosnia":(30,55)}

def records_from_patch(blob, expected_sha=TEST25_SHA, count=TEST25_COUNT):
    if sha(blob)!=expected_sha or blob[:8]!=b"ISS26X01" or len(blob)!=12+count*RECORD:
        raise ValueError("Authentic Test25 standalone patch required")
    if struct.unpack_from("<I",blob,8)[0]!=count:
        raise ValueError("Unexpected patch record count")
    records={}
    last=-1
    for i in range(count):
        at=12+i*RECORD
        lba=struct.unpack_from("<I",blob,at)[0]
        guard=blob[at+4:at+36]
        mask=blob[at+36:at+RECORD]
        if lba<=last or any(mask[:24]):
            raise ValueError("Malformed standalone sector record")
        records[lba]=(guard,mask)
        last=lba
    return records

def serialize(records):
    out=bytearray(b"ISS26X01"+struct.pack("<I",len(records)))
    for lba,(guard,mask) in sorted(records.items()):
        if len(guard)!=32 or len(mask)!=SECTOR or any(mask[:24]):
            raise ValueError("Bad standalone sector record")
        out.extend(struct.pack("<I",lba)+guard+mask)
    return bytes(out)

def patched_sector(source,lba,records):
    raw=raw_sector(source,lba)
    if lba not in records: return raw,raw
    after=apply_sector(raw,lba,records[lba])
    if (not raw[18]&0x20) and (not valid_parity(records[lba][1])):
        raise ValueError("Invalid original Mode2 Form1 XOR parity")
    return raw,after

def check_style_table(table:bytes):
    if len(table)!=78: raise ValueError("Need all 54 national +24 club slots")
    for name,(slot,style) in STYLE_SLOTS.items():
        if table[slot]!=style: raise ValueError("Unexpected Test25 national mapping: "+name)
        if [i for i,s in enumerate(table) if s==style]!=[slot]:
            raise ValueError("Shared national/club style collision: "+name)
    if table[54]!=10: raise ValueError("Unexpected protected club54/style10")
    return {"cape_unique":True,"bosnia_unique":True,"club54_style10":True}

def check_tables(source,records):
    out=[]
    for at in TABLE_OFFSETS:
        lba,pos=divmod(at,SECTOR)
        if not 24<=pos or pos+78>2072:
            raise ValueError("Unexpected team style table geometry")
        _,patched=patched_sector(source,lba,records)
        out.append(check_style_table(patched[pos:pos+78]))
    return out

def original_resources(catalog):
    names=["BIN/DATSEL.BIN","BIN/DATSEL3.BIN"]
    gdc=sorted(k for k in catalog if re.fullmatch(r"BIN/GDC_[A-Z0-9]+\.BIN",k))
    if len(gdc)!=34 or "BIN/GDC_BN.BIN" not in gdc or any(n not in catalog for n in names):
        raise ValueError("Expected two selection and all 34 stadium GPU resources")
    return names+gdc

def read_resource(source,records,lba,size):
    if not 0<size<=1024*1024:
        raise ValueError("Unbounded resource allocation")
    rows=[]
    for offset in range(0,size,2048):
        clean,patched=patched_sector(source,lba+offset//2048,records)
        if clean[18]&0x20: raise ValueError("Expected Mode2 Form1 graphics resource")
        rows.append(patched)
    return b"".join(r[24:2072] for r in rows)[:size]

def find_routes(blob):
    possible={}
    for base in (0x800F0000,0x800C8000):
        for slot in range(0,32,4):
            try: table,rows=parse_uploads(blob,base,slot)
            except ValueError: continue
            possible.setdefault((base,table),(slot,rows))
    if len(possible)!=1: raise ValueError("No unique supported GPU table")
    (base,table),(slot,rows)=next(iter(possible.items()))
    starts=sorted(set(r.start for r in rows))
    routes=[]
    for flag,(x,y) in TARGETS.items():
        # Reject partial overlaps, repeated uploads, or another writer of any
        # part of the selected atlas cell in this particular file.
        overlapping=[(i,r) for i,r in enumerate(rows) if
                     r.x<x+16 and r.x+r.w>x and r.y<y+28 and r.y+r.h>y]
        if len(overlapping)!=1:
            raise ValueError("Ambiguous or absent target coverage: "+flag)
        i,r=overlapping[0]
        if r.kind!=10 or sum(v.start==r.start for v in rows)!=1 or not(
                r.x<=x and x+16<=r.x+r.w and r.y<=y and y+28<=r.y+r.h):
            raise ValueError("Unverified full compressed target: "+flag)
        end=next((s for s in starts if s>r.start),table)
        decoded=decode_stream(blob[r.start:end],expected_bytes=r.w*r.h*2,
                              max_padding=end-r.start)
        routes.append({"flag":flag,"gpu_base":base,"list_pointer_slot":slot,
                       "upload_index":i,
                       "old_tile_sha256":sha(take_tile(decoded,r,x-r.x,y-r.y))})
    return routes

def compose_resource(source,records,lba,old,new):
    if len(old)!=len(new): raise ValueError("Resource size changed")
    changed=[]
    for offset in range(0,len(old),2048):
        a,b=old[offset:offset+2048],new[offset:offset+2048]
        if a==b: continue
        sector_lba=lba+offset//2048
        original,prior=patched_sector(source,sector_lba,records)
        if original[18]&0x20 or prior[24:24+len(a)]!=a:
            raise ValueError("Source resource changed during build")
        # Preserve all unrelated bytes in each sector, including its tail.
        mask=bytearray(bytes(x^y for x,y in zip(original,prior)))
        for i,(x,y) in enumerate(zip(a,b)):
            mask[24+i]^=x^y
        fix_parity(mask)
        if not valid_parity(mask): raise AssertionError("XOR EDC/ECC check failed")
        if bytes(original[24+i]^mask[24+i] for i in range(len(b)))!=b:
            raise AssertionError("New sector not reproducible")
        if any(mask[:24]): raise AssertionError("Raw CD header mutation")
        if any(mask):
            records[sector_lba]=(hashlib.sha256(original).digest(),bytes(mask))
        else:
            records.pop(sector_lba,None)
        changed.append(sector_lba)
    return changed

def build(track:Path,base:Path,archive:Path):
    if file_sha(track)!=CLEAN_SHA: raise ValueError("Requires exact clean original EU Track01")
    if sha_path(archive)!=EXPECTED_ZIP_SHA: raise ValueError("Requires verified previous Academy ZIP")
    raw=read_snapshot(archive)
    palette=clut(raw,0,505)
    if sha(palette)!=CLUT_SHA or palette!=clut(raw,224,506):
        raise ValueError("Actual captured CLUT not verified")
    # A shared CLUT is never written. Stop immediately on poor color mapping.
    palette_mapping={name:mapped_art(name,palette)[1] for name in TARGETS}
    records=records_from_patch(read_patch(base))
    baseline=dict(records)
    updated={}
    resource_results=[]
    changed_lbas=set()
    with track.open("rb") as source:
        for lba in records: patched_sector(source,lba,records)
        tables=check_tables(source,records)
        catalog=directory_files(source)
        names=original_resources(catalog)
        for name in names:
            lba,size=catalog[name]
            old=read_resource(source,records,lba,size)
            try:
                routes=find_routes(old)
                new,changes=rewrite_resource(old,routes,palette)
            except (ValueError,AssertionError) as exc:
                raise ValueError(f"{name}: {exc}") from exc
            updated[name]=(lba,old,new)
            resource_results.append({"resource":name,"source_sha256":sha(old),
                                     "candidate_sha256":sha(new),"edits":changes})
        # Complete every resource preflight before committing any sector delta.
        for name,(lba,old,new) in updated.items():
            touched=compose_resource(source,records,lba,old,new)
            if changed_lbas.intersection(touched):
                raise ValueError("Overlapping resource sector edits")
            changed_lbas.update(touched)
        if not changed_lbas: raise ValueError("No actual graphic edits")
        if any(records.get(i)!=baseline.get(i) for i in set(records)|set(baseline)
               if i not in changed_lbas):
            raise AssertionError("Unrelated baseline patch record changed")
        if check_tables(source,records)!=tables:
            raise AssertionError("Style tables mutated during graphics edit")
    blob=serialize(records)
    return blob,{"schemaVersion":1,"kind":"EXPERIMENTAL standalone Test27 SOURCE ART candidate ONLY",
        "clean_track_sha256":CLEAN_SHA,"base_test25_sha256":TEST25_SHA,
        "output_patch_sha256":sha(blob),"records":len(records),
        "changed_lbas":sorted(changed_lbas),"previous_records_preserved_outside_targets":True,
        "style_tables_checked":len(tables),"regular_national_and_club_style_exclusivity_checked":True,
        "four_bonus_team_ownership_verified":False,
        "clut_unchanged":True,"palette_mapping":palette_mapping,
        "resources":resource_results,"original_disc_modified":False,
        "tracks02_12_modified":False,"test25_required_at_install":False,
        "runtime_stage_writer_fixed":False,"spectator_flags_verified":False,
        "actual_game_visual_acceptance":False,"release_authorized":False,
        "game_update_feed_changed":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--test25",required=True,type=Path)
    p.add_argument("--academy-zip",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--experimental",action="store_true")
    args=p.parse_args()
    if not args.experimental: p.error("Explicit --experimental required; NOT a stable release")
    if args.output.exists() or args.report.exists(): p.error("Refusing overwrite of existing output")
    blob,report=build(args.clean_track,args.test25,args.academy_zip)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("xb") as f: f.write(blob)
    with args.report.open("x",encoding="utf-8") as f: json.dump(report,f,indent=2)
    print("Built experimental self-contained source-art candidate, NOT a runtime staging fix.")
    print("SHA256",report["output_patch_sha256"])
if __name__=="__main__":
    main()
