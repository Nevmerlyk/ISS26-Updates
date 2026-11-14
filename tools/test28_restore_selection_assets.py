#!/usr/bin/env python3
"""Test28: improve selection/HUD candidate assets on the tested RecoveryPreview.
No GDC, mapping, name, palette or executable edits. Only fully decoded
compatible compressed packets from authenticated older releases can supply
missing bytes; the tested preview's existing edits and BOTH large flag
fragments are protected. Actual small-flag ownership still needs gameplay.
"""
from __future__ import annotations
import argparse
import json
import struct
from pathlib import Path
import test27_build_standalone_atlas_candidate as base
import test27_build_clean_graphics_recovery as recovery
from test27_gpu_stream_edit import (sha,TARGETS,intersection,fragment_read,
    parse_uploads,stream_span,discover_upload_lists)
from v095_name_lz_codec import encode_with_budget,decode_stream

DONORS={
 "Test25":(base.TEST25_SHA,1492),
 "Test12":("7E4FAC687487A3328BB564446DC4835C97D9A5841F335539EA56851F1958C3DD",1496),
 "Test08":("E65E5623756643E2DAE7069A66FE888E14439A5A534DBF171BB03630605648B1",1412),
}
FILES=("BIN/DATSEL.BIN","BIN/DATSEL3.BIN")
ADDRESS=0x800F0000

def merged_pixels(clean,current,donor,u):
    if len(clean)!=len(current) or len(current)!=len(donor) or len(clean)!=2*u.w*u.h:
        raise ValueError("Incomplete packet")
    protected=set()
    for flag in TARGETS:
        box=intersection(u,flag)
        if box:
            x,y,w,h=box
            for yy in range(y,y+h):
                start=2*((yy-u.y)*u.w+x-u.x)
                protected.update(range(start,start+2*w))
    out=bytearray(current)
    for i,(a,b,c) in enumerate(zip(clean,current,donor)):
        if i in protected or c==a:
            continue
        if b!=a and b!=c:
            raise ValueError("Conflicting donor changes outside target flags")
        out[i]=c
    return bytes(out)

def restore_packets(clean,current,donors,address=ADDRESS):
    original_lists=discover_upload_lists(clean,address)
    if not original_lists or original_lists!=discover_upload_lists(current,address):
        raise ValueError("Preview changed original selection descriptor layout")
    output=bytearray(current)
    report={"restored":[],"blocked":[],"unchanged":0}
    seen=set()
    spans=[]
    for (_,table),(slot,rows) in original_lists.items():
        for i,u in enumerate(rows):
            if u.offset in seen or u.kind&255!=10: continue
            seen.add(u.offset)
            try:
                a,stop=stream_span(clean,address,table,rows,u)
                b,end=stream_span(current,address,table,rows,u)
                expected=2*u.w*u.h
                if len(a)!=expected or len(b)!=expected:
                    raise ValueError("Incomplete clean/preview packet")
                # A shorter preview packet can safely use the original
                # verified allocation. No new storage or pointer changes.
                if end>stop or any(u.start<hi and lo<stop for lo,hi in spans):
                    raise ValueError("Unexpected preview packet allocation")
                spans.append((u.start,stop))
            except ValueError as exc:
                report["blocked"].append({"upload_offset":u.offset,"reason":str(exc)})
                continue
            failures=[]
            for label,blob in donors:
                try:
                    dt,dr=parse_uploads(blob,address,slot)
                    geo=lambda x:(x.kind,x.x,x.y,x.w,x.h,x.padding_field)
                    if [geo(x) for x in rows]!=[geo(x) for x in dr]:
                        raise ValueError("Different logical GPU list")
                    d,_=stream_span(blob,address,dt,dr,dr[i])
                    c=merged_pixels(a,b,d,u)
                    if c==b:
                        # A valid latest donor with no extra changes is
                        # authoritative. Do not resurrect older artwork.
                        report["unchanged"]+=1
                        break
                    packed,method=encode_with_budget(c,expected_bytes=expected,capacity=stop-u.start)
                    replacement=packed+bytes(stop-u.start-len(packed))
                    if decode_stream(replacement,expected_bytes=expected,max_padding=stop-u.start)!=c:
                        raise AssertionError("Round-trip mismatch")
                    for flag in TARGETS:
                        box=intersection(u,flag)
                        if box and fragment_read(c,u,box)!=fragment_read(b,u,box):
                            raise AssertionError("Test27 flag overwritten")
                    output[u.start:stop]=replacement
                    report["restored"].append({"upload_offset":u.offset,"gpu_rect":[u.x,u.y,u.w,u.h],
                        "donor":label,"restored_bytes":sum(x!=y for x,y in zip(b,c)),
                        "capacity":stop-u.start,"packed_bytes":len(packed),
                        "compression":method,"earlier_attempts":failures})
                    break
                except ValueError as exc:
                    failures.append({"donor":label,"reason":str(exc)})
            else:
                report["blocked"].append({"upload_offset":u.offset,"attempts":failures})
    if len(output)!=len(current) or discover_upload_lists(bytes(output),address)!=original_lists:
        raise AssertionError("Output descriptor/size changed")
    # Independently verify both new large national source tiles stayed exact.
    old_routes=base.find_routes(current,address)
    new_routes=base.find_routes(bytes(output),address)
    fingerprint=lambda rr:sorted((r["flag"],tuple(r["fragment"]),r["old_tile_sha256"]) for r in rr)
    if fingerprint(old_routes)!=fingerprint(new_routes):
        raise AssertionError("Large flag source changed")
    return bytes(output),report

def build(track,preview,report_path,donor_paths):
    if base.file_sha(track)!=base.CLEAN_SHA:
        raise ValueError("Requires exact original Europe Track01")
    metadata=json.loads(report_path.read_text(encoding="utf-8-sig"))
    p=preview.read_bytes()
    if metadata.get("kind")!="EXPERIMENTAL Test27 clean graphics extent recovery" or metadata.get("release_authorized") is not False or metadata.get("output_patch_sha256")!=sha(p):
        raise ValueError("Expected matching tested RecoveryPreview build report")
    records=base.records_from_patch(p,sha(p),metadata["records"])
    previous=dict(records)
    donor_maps={label:base.records_from_patch(path.read_bytes(),*DONORS[label]) for label,path in donor_paths}
    details={}
    touched=set()
    with track.open("rb") as source:
        for lba in records: base.patched_sector(source,lba,records)
        clean_catalog=base.directory_files(source)
        catalog=base.directory_files(base.PatchedDiscView(source,records))
        styles=base.check_tables(source,records)
        donors_catalog={label:base.directory_files(base.PatchedDiscView(source,rows)) for label,rows in donor_maps.items()}
        for name in FILES:
            if catalog[name]!=clean_catalog[name]:
                raise ValueError("Unexpected preview selection extent")
            lba,size=catalog[name]
            original=base.read_resource(source,{},lba,size)
            current=base.read_resource(source,records,lba,size)
            # Verify exact bytes from the successful local Test27 report.
            entry=next(r for r in metadata["resources"] if r["resource"]==name)
            if sha(current)!=entry["candidate_sha256"]:
                raise ValueError("Preview selection resource hash mismatch")
            options=[]
            rejected=[]
            for label in DONORS:
                try:
                    dm=donor_maps[label]
                    cat=donors_catalog[label]
                    old_lba,old_size=cat[name]
                    if old_lba!=lba or not 0<old_size<=1024*1024:
                        raise ValueError("Different donor extent")
                    recovery.resource_sectors(clean_catalog,cat,name)
                    options.append((label,recovery.donor_projection(source,dm,lba,old_size)))
                except (ValueError,KeyError) as exc:
                    rejected.append({"donor":label,"reason":str(exc)})
            result,info=restore_packets(original,current,options)
            info["rejected_donor_resources"]=rejected
            info["changed_lbas"]=base.compose_resource(source,records,lba,current,result)
            if base.read_resource(source,records,lba,size)!=result:
                raise AssertionError("Selection resource readback failed")
            touched.update(info["changed_lbas"])
            details[name]=info
            print(name,json.dumps(info),flush=True)
        if base.directory_files(base.PatchedDiscView(source,records))!=catalog or base.check_tables(source,records)!=styles:
            raise AssertionError("Catalog or style maps changed")
        if any(records.get(i)!=previous.get(i) for i in set(records)|set(previous) if i not in touched):
            raise AssertionError("Non-selection sector changed")
        for lba in records: base.patched_sector(source,lba,records)
    if not touched:
        raise ValueError("No valid additional graphics recovered; Test27 remains unchanged")
    data=base.serialize(records)
    return data,{"kind":"EXPERIMENTAL Test28 selection asset restoration","output_patch_sha256":sha(data),
        "input_preview_sha256":sha(p),"records":len(records),"selection":details,
        "changed_lbas":sorted(touched),"stadium_resources_unchanged":True,
        "large_flag_source_tiles_unchanged":True,"test25_required_at_install":False,
        "test27_required_at_install":False,"small_flags_visually_verified":False,
        "runtime_stage_writer_fixed":False,"release_authorized":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("clean-track","preview","preview-report","test25","test12","test08","output","report"):
        p.add_argument("--"+name,required=True,type=Path)
    args=p.parse_args()
    if args.output.exists() or args.report.exists(): p.error("Refusing overwrite")
    data,info=build(args.clean_track,args.preview,args.preview_report,
                    [("Test25",args.test25),("Test12",args.test12),("Test08",args.test08)])
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("xb") as f: f.write(data)
    with args.report.open("x",encoding="utf-8") as f: json.dump(info,f,indent=2)
    print("Test28 experimental standalone selection candidate:",args.output)
    print("SHA256:",info["output_patch_sha256"])
if __name__=="__main__":
    main()
