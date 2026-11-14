#!/usr/bin/env python3
"""Experimental recovery of the 36 flag-source files from actual clean Form1 extents.

The previous patch expanded 35 files into Form2 sectors and damaged at
least one compressed packet. Do not reinterpret Form2 data as Form1.
Reconstruct these files from the clean disc, insert only the two target
flags, restore just their ISO lengths, and discard previous records
within their verified file extents. All other Test25 deltas are retained.
This intentionally rolls back earlier graphic changes in these 36 files.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
import test27_build_standalone_atlas_candidate as base
from test27_gpu_stream_edit import (sha, TARGETS, CLUT_SHA, mapped_art, rewrite_resource)
from test27_extract_real_flag_pixels import read_snapshot,sha_path,EXPECTED_ZIP_SHA
from analyze_flag_test26_unified import clut
from probe_v095_name_gpu_atlas import directory_files,raw_sector,SECTOR,CLEAN_SHA,file_sha
from v095_static_prematch_ram_trace import read_patch

def both32(data,offset):
    little,big=struct.unpack_from("<I",data,offset)[0],struct.unpack_from(">I",data,offset+4)[0]
    if little!=big:
        raise ValueError("Mismatched ISO both-endian field")
    return little

def iso_record_positions(source,records):
    """Map each ISO entry to its exact raw-sector payload offset.
    Only ordinary, single-extent ISO records are used for changes.
    """
    _,pvd=base.patched_sector(source,16,records)
    if pvd[18]&0x20 or pvd[24:31]!=b"\x01CD001\x01":
        raise ValueError("Unexpected primary volume descriptor")
    root=pvd[24+156:24+190]
    result={}
    visited=set()
    def walk(lba,size,prefix,depth):
        if depth>8 or (lba,size) in visited or not 0<size<=4*1024*1024:
            raise ValueError("Invalid or cyclic ISO directory")
        visited.add((lba,size))
        for i in range(math.ceil(size/2048)):
            _,raw=base.patched_sector(source,lba+i,records)
            if raw[18]&0x20:
                raise ValueError("Non-Form1 ISO directory")
            data=raw[24:2072]
            at=0
            while at<min(2048,size-2048*i) and data[at]:
                n=data[at]
                if n<34 or at+n>2048:
                    raise ValueError("Invalid ISO record boundary")
                r=data[at:at+n]
                at0=at
                at+=n
                namelen=r[32]
                if 33+namelen>len(r): raise ValueError("Invalid ISO name")
                name=r[33:33+namelen].split(b";",1)[0].rstrip(b".")
                if name in (b"\0",b"\1"): continue
                path=prefix+name.decode("ascii",errors="replace")
                extent,length=both32(r,2),both32(r,10)
                if path in result: raise ValueError("Duplicate ISO path")
                result[path]={"lba":lba+i,"offset":at0+10,"extent":extent,
                              "size":length,"flags":r[25]}
                if r[25]&2:
                    walk(extent,length,path+"/",depth+1)
    walk(both32(root,2),both32(root,10),"",0)
    return result

def resource_sectors(clean,patched,name):
    """Explicitly bound the old patch allocation by next file in BOTH catalogs."""
    lba,old=clean[name]
    dest,new=patched[name]
    if lba!=dest or not 0<old<=1024*1024 or not 0<new<=1024*1024:
        raise ValueError("Unexpected relocated or oversized graphics resource: "+name)
    count=math.ceil(max(old,new)/2048)
    end=lba+count
    for label,cat in (("clean",clean),("patched",patched)):
        for other,(start,size) in cat.items():
            if other==name or size<=0: continue
            if start<end and lba<start+math.ceil(size/2048):
                raise ValueError(f"{name}: shared/overlapping {label} ISO extent {other}")
    return lba,set(range(lba,end))

def restore_lengths(source,records,cleanpos,patchedpos,names):
    # Work at the verified length field only; preserve other directory bytes.
    grouped={}
    for name in names:
        a,b=cleanpos[name],patchedpos[name]
        if a["extent"]!=b["extent"] or (a["flags"]|b["flags"]) & 0x82:
            raise ValueError("Unsupported target directory record "+name)
        if a["size"]==b["size"]: continue
        value=struct.pack("<I",a["size"])+struct.pack(">I",a["size"])
        expected=struct.pack("<I",b["size"])+struct.pack(">I",b["size"])
        grouped.setdefault(b["lba"],[]).append((b["offset"],expected,value))
    changed=set()
    for lba,edits in grouped.items():
        _,sector=base.patched_sector(source,lba,records)
        before=sector[24:2072]
        after=bytearray(before)
        for off,expected,value in edits:
            if before[off:off+8]!=expected:
                raise ValueError("ISO length guard failed")
            after[off:off+8]=value
        changed.update(base.compose_resource(source,records,lba,before,bytes(after)))
    return changed

def clean_art(blob,palette):
    # The original donor file must have complete, unambiguous target packets.
    # Known bases are checked independently, not guessed from corrupted input.
    options=[]
    failures=[]
    for address in (0x800F0000,0x800C8000):
        try:
            routes=base.find_routes(blob,address)
            if any(r["decoded_bytes"]!=8192 for r in routes):
                # Actual known target uploads are 32x128 words. Do not
                # manufacture data for a genuinely short clean packet.
                raise ValueError("Original target packet is not complete 8192-byte upload")
            options.append((address,routes))
        except ValueError as exc:
            failures.append(hex(address)+": "+str(exc))
    if len(options)!=1:
        raise ValueError("No unique fully decoded clean donor route: "+"; ".join(failures))
    address,routes=options[0]
    print("RECOVERY ROUTES:",hex(address),json.dumps(routes),flush=True)
    new,changes=rewrite_resource(blob,routes,palette)
    if len(new)!=len(blob):
        raise AssertionError("Recovery expanded clean resource")
    return new,changes

def build(track,patch,archive):
    if file_sha(track)!=CLEAN_SHA:
        raise ValueError("Wrong original Track01")
    if sha_path(archive)!=EXPECTED_ZIP_SHA:
        raise ValueError("Wrong Academy archive")
    vram=read_snapshot(archive)
    palette=clut(vram,0,505)
    if sha(palette)!=CLUT_SHA or palette!=clut(vram,224,506):
        raise ValueError("Wrong captured palette")
    for flag in TARGETS:
        print("Palette PASS:",flag,mapped_art(flag,palette)[1],flush=True)
    records=base.records_from_patch(read_patch(patch))
    previous=dict(records)
    jobs=[]
    blockers=[]
    touched=set()
    with track.open("rb") as source:
        for lba in records: base.patched_sector(source,lba,records)
        styles=base.check_tables(source,records)
        clean=directory_files(source)
        patched=directory_files(base.PatchedDiscView(source,records))
        names=base.original_resources(clean)
        if base.original_resources(patched)!=names:
            raise ValueError("Missing previous graphics resource")
        cleanpos=iso_record_positions(source,{})
        patchedpos=iso_record_positions(source,records)
        for name in names:
            print("RECOVERY FILE:",name,clean[name],patched[name],flush=True)
            try:
                lba,owned=resource_sectors(clean,patched,name)
                if touched&owned: raise ValueError("Overlapping recovery files")
                if any(pos["lba"] in owned for pos in patchedpos.values()):
                    raise ValueError("Recovery overlaps ISO directory")
                # Source is strictly clean Form1 extent. No reading Form2
                # tail as graphics and no change to original sector headers.
                original=base.read_resource(source,{},lba,clean[name][1])
                result,edits=clean_art(original,palette)
                jobs.append((name,lba,owned,original,result,edits))
                touched.update(owned)
                print("RECOVERY PASS:",name,json.dumps(edits),flush=True)
            except (ValueError,AssertionError) as exc:
                blockers.append(name+": "+str(exc))
                print("RECOVERY BLOCKED:",blockers[-1],flush=True)
        if blockers or len(jobs)!=len(names):
            raise ValueError("Recovery refused before composition:\n - "+"\n - ".join(blockers))
        reports=[]
        for name,lba,owned,original,result,edits in jobs:
            removed=sorted(owned&previous.keys())
            for i in owned:
                records.pop(i,None)
            actual=base.compose_resource(source,records,lba,original,result)
            if not set(actual)<=owned:
                raise AssertionError("Recovery changed unrelated sector")
            if base.read_resource(source,records,lba,len(result))!=result:
                raise AssertionError("Recovered resource readback failed")
            reports.append({"resource":name,"clean_bytes":len(original),
                "prior_bytes":patched[name][1],"prior_records_replaced_or_removed":removed,
                "new_graphics_lbas":actual,"candidate_sha256":sha(result),"edits":edits})
        directory_changes=restore_lengths(source,records,cleanpos,patchedpos,names)
        if directory_changes&touched:
            raise AssertionError("Directory and graphics overlap")
        expected=dict(patched)
        expected.update({name:clean[name] for name in names})
        if directory_files(base.PatchedDiscView(source,records))!=expected:
            raise AssertionError("Unexpected ISO catalog change")
        allowed=touched|directory_changes
        if any(records.get(i)!=previous.get(i) for i in set(records)|set(previous) if i not in allowed):
            raise AssertionError("Unrelated patch record changed")
        if base.check_tables(source,records)!=styles:
            raise AssertionError("National/club mappings changed")
        for i in records:
            base.patched_sector(source,i,records)
    output=base.serialize(records)
    return output,{"schemaVersion":1,"kind":"EXPERIMENTAL Test27 clean graphics extent recovery",
        "output_patch_sha256":sha(output),"records":len(records),
        "resources":reports,"directory_lbas":sorted(directory_changes),
        "prior_graphics_in_36_files_rolled_back":True,
        "other_base_records_preserved":True,"original_disc_modified":False,
        "tracks02_12_modified":False,"test25_required_at_install":False,
        "runtime_stage_writer_fixed":False,"release_authorized":False,
        "actual_game_visual_acceptance":False,"game_update_feed_changed":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--test25",required=True,type=Path)
    p.add_argument("--academy-zip",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--experimental",action="store_true")
    args=p.parse_args()
    if not args.experimental: p.error("Explicit experimental graphics recovery required")
    if args.output.exists() or args.report.exists(): p.error("Refusing overwrite")
    output,report=build(args.clean_track,args.test25,args.academy_zip)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("xb") as f: f.write(output)
    with args.report.open("x",encoding="utf-8") as f: json.dump(report,f,indent=2)
    print("EXPERIMENTAL recovery patch:",args.output)
    print("SHA256:",report["output_patch_sha256"])
    print("WARNING: old graphics within 36 files rolled back. No runtime fix claimed.")
if __name__=="__main__":
    main()
