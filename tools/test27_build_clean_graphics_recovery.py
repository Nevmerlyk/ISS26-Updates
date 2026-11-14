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
from test27_gpu_stream_edit import (sha, TARGETS, CLUT_SHA, mapped_art, rewrite_resource,
    stream_span, intersection, parse_uploads, discover_upload_lists)
from v095_name_lz_codec import decode_stream_prefix
from build_v094_pointer_repair import edc
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
        if depth>8 or not 0<size<=4*1024*1024:
            raise ValueError("Invalid or cyclic ISO directory")
        if (lba,size) in visited:
            return
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
                if r[25]&2 and (path=="BIN" or path.startswith("BIN/")):
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
            for route in routes:
                _,rows=parse_uploads(blob,address,route["list_pointer_slot"])
                u=rows[route["upload_index"]]
                if route["decoded_bytes"]!=2*u.w*u.h:
                    raise ValueError("Original target packet is not a complete upload")
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
    return new,changes,address

def donor_projection(source,records,lba,size):
    """Read old compiler's 2048-byte slices for RECOVERY ONLY.
    This is NOT a claim that a real PS1 accepts Form2 graphics.
    No bytes from a Form2 sector are written by the new recovery patch.
    """
    out=bytearray()
    for i in range(math.ceil(size/2048)):
        _,raw=base.patched_sector(source,lba+i,records)
        if raw[16:20]!=raw[20:24]:
            raise ValueError("Old donor sector subheaders disagree")
        if raw[18]&0x20 and raw[2348:2352]!=edc(raw[16:2348]):
            raise ValueError("Old donor Form2 EDC not verified")
        out.extend(raw[24:2072])
    return bytes(out[:size])


def retain_valid_donors(original,result,prior,address):
    """Restore only fully decoded non-target old GPU packets that fit their
    clean slots, with identical full descriptor geometry and no aliases.
    Opaque auxiliary data and damaged/oversized packets stay original.
    """
    out=bytearray(result)
    stats={"retained_changed_packets":[],"unchanged_packets":0,
           "original_fallback_packets":[],"target_packets_not_imported":[]}
    seen=set()
    authorized=[]
    for (_,table),(slot,rows) in base.canonical_lists(original,address).items():
        try:
            ot,oldrows=parse_uploads(prior,address,slot)
            geo=lambda u:(u.kind,u.x,u.y,u.w,u.h,u.padding_field)
            if [geo(u) for u in rows]!=[geo(u) for u in oldrows]:
                raise ValueError("GPU list geometry differs")
        except ValueError as exc:
            stats["original_fallback_packets"].append({"slot":slot,"reason":str(exc)})
            continue
        for u,v in zip(rows,oldrows):
            if u.offset in seen or u.kind&255!=10:
                continue
            seen.add(u.offset)
            if any(intersection(u,f) for f in TARGETS):
                stats["target_packets_not_imported"].append(u.offset)
                continue
            try:
                expected=2*u.w*u.h
                clean,stop=stream_span(original,address,table,rows,u)
                old,end=stream_span(prior,address,ot,oldrows,v)
                if len(clean)!=expected or len(old)!=expected:
                    raise ValueError("Donor/clean packet is incomplete")
                if old==clean:
                    stats["unchanged_packets"]+=1
                    continue
                raw,used=decode_stream_prefix(prior[v.start:end],expected_bytes=expected)
                if raw!=old or used>stop-u.start:
                    raise ValueError("Valid donor packet does not fit clean slot")
                if result[u.start:stop]!=original[u.start:stop] or any(u.start<b and a<stop for a,b in authorized):
                    raise ValueError("Donor intersects new flag or already used stream")
                payload=prior[v.start:v.start+used]+bytes(stop-u.start-used)
                if decode_stream_prefix(payload,expected_bytes=expected)[0]!=old:
                    raise AssertionError("Donor round-trip failed")
                out[u.start:stop]=payload
                authorized.append((u.start,stop))
                stats["retained_changed_packets"].append(u.offset)
            except (ValueError,AssertionError) as exc:
                stats["original_fallback_packets"].append({"upload_offset":u.offset,"reason":str(exc)})
    if discover_upload_lists(bytes(out),address)!=discover_upload_lists(original,address):
        raise AssertionError("Donor recovery changed descriptors")
    return bytes(out),stats


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
                result,edits,address=clean_art(original,palette)
                try:
                    prior=donor_projection(source,records,lba,patched[name][1])
                    result,donors=retain_valid_donors(original,result,prior,address)
                except (ValueError,AssertionError) as exc:
                    donors={"retained_changed_packets":[],"original_fallback_packets":[],
                            "all_prior_donor_packets_skipped":str(exc)}
                jobs.append((name,lba,owned,original,result,edits,donors))
                print("DONOR RETENTION:",name,json.dumps(donors),flush=True)
                touched.update(owned)
                print("RECOVERY PASS:",name,json.dumps(edits),flush=True)
            except (ValueError,AssertionError) as exc:
                blockers.append(name+": "+str(exc))
                print("RECOVERY BLOCKED:",blockers[-1],flush=True)
        if blockers or len(jobs)!=len(names):
            raise ValueError("Recovery refused before composition:\n - "+"\n - ".join(blockers))
        reports=[]
        for name,lba,owned,original,result,edits,donors in jobs:
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
                "new_graphics_lbas":actual,"candidate_sha256":sha(result),"edits":edits,"donor_retention":donors})
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
        "prior_graphics_in_36_files_rolled_back_or_selectively_retained":True,
        "all_prior_graphics_preserved":False,
        "other_base_records_preserved":True,
        "clut_source_in_recovered_game_verified":False,
        "four_bonus_team_ownership_verified":False,"original_disc_modified":False,
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
    print("WARNING: prior graphics selectively retained; damaged, oversized and unverified edits reverted. No runtime fix claimed.")
if __name__=="__main__":
    main()
