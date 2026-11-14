#!/usr/bin/env python3
"""One-pass stage-3 candidate: selection donors, exact duplicate packets and
exceptional stadiums. No runtime or all-national visual acceptance claimed.

Use only clean-original guarded sector edits and the owner-tested Test27
preview. At ambiguous stadium coordinates, edit every matching writer
only if ALL intersecting descriptors match previously verified clean
flag fragments (or already repaired bytes). Never infer the last writer.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import test28_restore_selection_assets as selection
import test27_build_standalone_atlas_candidate as base
import test27_build_clean_graphics_recovery as recovery
from test27_gpu_stream_edit import (TARGETS,sha,intersection,fragment_read,
    fragment_replace,discover_upload_lists,parse_uploads,stream_span)
from v095_name_lz_codec import encode_with_budget,decode_stream

# Real Test27 owner build log, DATSEL and GDC_AD (clean donor fragments).
KNOWN={
 ("cape_verde",(848,256,16,28)):{"5CAB263C7BCD17E0D8B0D7D25A4F6C5276092D8CBA8C4EF428428DAFE10E255F"},
 ("bosnia",(816,368,16,16)):{"BC2C90DC21A75CBB6CBD6C17B2C2173751E4AE173F2A24D9B7F6511A7B48F02D"},
 ("bosnia",(816,384,16,12)):{"2D709378DDE15924C5B3CDBB5446F732FDCD4439D299028C4241BB0284E99D97",
                            "D514981B08428A7C72BBA17FE92F97B8D51B5457B2C7E460883F1296CA08D4CA"},
}

def packet_map(blob,address):
    seen=set()
    for (_,table),(slot,rows) in discover_upload_lists(blob,address).items():
        for u in rows:
            if u.offset in seen: continue
            seen.add(u.offset)
            yield table,slot,rows,u

def exact_packet(blob,address,table,rows,u):
    data,stop=stream_span(blob,address,table,rows,u)
    if len(data)!=2*u.w*u.h:
        raise ValueError("Incomplete packet")
    return data,stop

def apply_packets(clean,current,address,jobs):
    """jobs: (upload, old allocation end, previous decoded, replacement).
    Preserve every other byte, original descriptor table and the allocation.
    """
    out=bytearray(current)
    spans=[]
    edits=[]
    for u,stop,b,c in jobs:
        if b==c: continue
        if any(u.start<hi and lo<stop for lo,hi in spans):
            raise ValueError("Aliased or overlapping compressed allocation")
        spans.append((u.start,stop))
        packed,method=encode_with_budget(c,expected_bytes=len(c),capacity=stop-u.start)
        payload=packed+bytes(stop-u.start-len(packed))
        if decode_stream(payload,expected_bytes=len(c),max_padding=len(payload))!=c:
            raise AssertionError("Packet readback mismatch")
        out[u.start:stop]=payload
        edits.append({"upload_offset":u.offset,"rect":[u.x,u.y,u.w,u.h],
                      "changed_bytes":sum(a!=b for a,b in zip(b,c)),
                      "packed_bytes":len(packed),"capacity":stop-u.start,"method":method})
    if len(out)!=len(current) or discover_upload_lists(bytes(out),address)!=discover_upload_lists(clean,address):
        raise AssertionError("Descriptor shape changed")
    cursor=0
    for lo,hi in sorted(spans):
        if out[cursor:lo]!=current[cursor:lo]: raise AssertionError("Outside packet changed")
        cursor=hi
    if out[cursor:]!=current[cursor:]: raise AssertionError("Outside packet changed")
    return bytes(out),edits

def donor_tiles(clean,current,address,entry):
    """Extract actual repaired 64x28 tiles and verified original fragments."""
    variants={}
    new={}
    for r in base.find_routes(clean,address):
        flag=r["flag"]; box=tuple(r["fragment"])
        table,rows=parse_uploads(clean,address,r["list_pointer_slot"])
        u=rows[r["upload_index"]]
        a,_=exact_packet(clean,address,table,rows,u)
        b,_=exact_packet(current,address,table,rows,u)
        old=fragment_read(a,u,box); fixed=fragment_read(b,u,box)
        if sha(old) not in KNOWN.get((flag,box),set()):
            raise ValueError("Reference original fragment not confirmed")
        reported=[e for e in entry["edits"] if e["flag"]==flag and tuple(e["vram_words"])==box]
        if len(reported)!=1 or reported[0]["new_tile_sha256"]!=sha(fixed):
            raise ValueError("Reference repaired fragment differs from tested preview report")
        variants.setdefault(flag,[]).append((box,old))
        tile=new.setdefault(flag,bytearray(896))
        put_fragment(tile,flag,box,fixed)
    return {k:bytes(v) for k,v in new.items()},variants

def put_fragment(tile,flag,box,data):
    tx,ty=TARGETS[flag]; x,y,w,h=box
    if not(tx<=x and x+w<=tx+16 and ty<=y and y+h<=ty+28 and len(data)==2*w*h):
        raise ValueError("Wrong reference rectangle")
    for row in range(h):
        start=2*((y-ty+row)*16+x-tx)
        tile[start:start+2*w]=data[row*2*w:(row+1)*2*w]

def get_fragment(tile,flag,box):
    x,y,w,h=box; tx,ty=TARGETS[flag]
    return b"".join(tile[2*((yy-ty)*16+x-tx):2*((yy-ty)*16+x-tx+w)] for yy in range(y,y+h))

def repair_stadium(clean,current,tiles,reference_tiles,address=0x800C8000):
    """Every overlay must match a verified full clean donor tile slice.
    No arbitrary union of unrelated stadium textures. Partial edits are
    never emitted for an unproved flag. Overlap of identical target data
    is safe because all applicable writers receive the same replacement.
    """
    if discover_upload_lists(clean,address)!=discover_upload_lists(current,address):
        raise ValueError("Preview stadium descriptor differs")
    out=current
    info={"fixed_flags":[],"blocked":{},"edits":[]}
    for flag in TARGETS:
        jobs=[]
        covered=set()
        try:
            for table,slot,rows,u in packet_map(clean,address):
                box=intersection(u,flag)
                if box is None: continue
                a,stop=exact_packet(clean,address,table,rows,u)
                b,end=exact_packet(out,address,table,rows,u)
                if end>stop:
                    raise ValueError("Current packet exceeds clean allocation")
                old=fragment_read(a,u,box)
                fixed=get_fragment(tiles[flag],flag,box)
                if old not in {get_fragment(t,flag,box) for t in reference_tiles[flag]}:
                    raise ValueError(f"Unverified overlapping writer at {u.offset}, {box}, SHA {sha(old)}")
                if fragment_read(b,u,box) not in (old,fixed):
                    raise ValueError("Current target already contains a conflicting change")
                c=fragment_replace(b,u,box,tiles[flag],flag)
                x,y,w,h=box
                covered.update((xx,yy) for yy in range(y,y+h) for xx in range(x,x+w))
                jobs.append((u,stop,b,c))
            if len(covered)!=448:
                raise ValueError(f"Incomplete verified coverage: {len(covered)}/448 VRAM words")
            out,edits=apply_packets(clean,out,address,jobs)
            info["fixed_flags"].append(flag)
            info["edits"].extend(edits)
        except ValueError as exc:
            info["blocked"][flag]=str(exc)
    return out,info

def duplicate_selection(clean1,patched1,clean2,patched2,address=selection.ADDRESS):
    """Transfer valid recovered graphics between DATSEL copies only if
    clean decoded bytes AND complete geometry match exactly. Protect both
    preview flags, and never copy an arbitrary similarly sized sprite.
    """
    index={}
    for table,slot,rows,u in packet_map(clean1,address):
        if u.kind&255!=10: continue
        try:
            a,stop=exact_packet(clean1,address,table,rows,u)
            b,end=exact_packet(patched1,address,table,rows,u)
        except ValueError: continue
        key=(u.kind,u.x,u.y,u.w,u.h,u.padding_field,sha(a))
        index.setdefault(key,set()).add(b)
    out=patched2
    edits=[]
    blocked=[]
    for table,slot,rows,u in packet_map(clean2,address):
        if u.kind&255!=10: continue
        try:
            a,stop=exact_packet(clean2,address,table,rows,u)
            b,end=exact_packet(out,address,table,rows,u)
            if end>stop: raise ValueError("Preview packet exceeds clean allocation")
            key=(u.kind,u.x,u.y,u.w,u.h,u.padding_field,sha(a))
            options=index.get(key,set())
            if len(options)!=1: continue
            c=selection.merged_pixels(a,b,next(iter(options)),u)
            out,new=apply_packets(clean2,out,address,[(u,stop,b,c)])
            edits.extend(new)
        except ValueError as exc:
            blocked.append({"upload_offset":u.offset,"reason":str(exc)})
    return out,{"edits":edits,"blocked":blocked}

def build(track,preview,preview_report,donors):
    intermediate,sel=selection.build(track,preview,preview_report,donors,allow_no_changes=True)
    metadata=json.loads(preview_report.read_text(encoding="utf-8-sig"))
    entries={e["resource"]:e for e in metadata["resources"]}
    original_records=base.records_from_patch(preview.read_bytes(),metadata["output_patch_sha256"],metadata["records"])
    records=base.records_from_patch(intermediate,sha(intermediate),sel["records"])
    stage={}
    touched=set(sel["changed_lbas"])
    with track.open("rb") as f:
        cat=base.directory_files(f)
        priorcat=base.directory_files(base.PatchedDiscView(f,records))
        styles=base.check_tables(f,records)
        def read(name,recs):
            lba,size=cat[name]
            if priorcat[name]!=(lba,size):
                raise ValueError("Not a clean-sized preview resource: "+name)
            return base.read_resource(f,recs,lba,size)
        def commit(name,b,c):
            changed=base.compose_resource(f,records,cat[name][0],b,c)
            if read(name,records)!=c: raise AssertionError("Composed readback mismatch")
            touched.update(changed)
            return changed
        refnames=("BIN/DATSEL.BIN","BIN/GDC_AD.BIN")
        reference_tiles={k:[] for k in TARGETS}
        tiles=None
        for name in refnames:
            old=read(name,{})
            fixed=read(name,original_records)
            if sha(fixed)!=entries[name]["candidate_sha256"]:
                raise ValueError("Tested preview reference digest mismatch")
            t,variants=donor_tiles(old,fixed,selection.ADDRESS if "DATSEL" in name else 0x800C8000,entries[name])
            if tiles is not None and tiles!=t:
                raise ValueError("Reference repaired flags differ between selection and stadium")
            tiles=t
            for flag,fragments in variants.items():
                tile=bytearray(896)
                for box,data in fragments: put_fragment(tile,flag,box,data)
                reference_tiles[flag].append(bytes(tile))
        # Restore identical copies from the recovered selection archive.
        a,b=selection.FILES
        cur=read(b,records)
        result,info=duplicate_selection(read(a,{}),read(a,records),read(b,{}),cur)
        info["changed_lbas"]=commit(b,cur,result)
        stage["duplicate_selection"]=info
        print("DUPLICATE SELECTION:",json.dumps(info),flush=True)
        unresolved=[]
        for name in sorted(recovery.EXCEPTIONS):
            old=read(name,{})
            cur=read(name,records)
            if sha(cur)!=entries[name]["candidate_sha256"]:
                raise ValueError("Exceptional stadium preview digest mismatch: "+name)
            result,info=repair_stadium(old,cur,tiles,reference_tiles)
            info["changed_lbas"]=commit(name,cur,result)
            stage[name]=info
            if info["blocked"]: unresolved.append(name)
            print("EXCEPTION RECOVERY:",name,json.dumps(info),flush=True)
        # Check non-exceptional stadiums are byte-exact to the accepted preview.
        protected=[n for n in base.original_resources(cat) if "/GDC_" in n and n not in recovery.EXCEPTIONS]
        if any(sha(read(n,records))!=entries[n]["candidate_sha256"] for n in protected):
            raise AssertionError("Previously working stadium changed")
        if base.directory_files(base.PatchedDiscView(f,records))!=priorcat or base.check_tables(f,records)!=styles:
            raise AssertionError("ISO catalog or team mappings changed")
        if any(records.get(i)!=original_records.get(i) for i in set(records)|set(original_records) if i not in touched):
            raise AssertionError("Unrelated sector changed")
        for i in records: base.patched_sector(f,i,records)
    if not touched: raise ValueError("No validated additional graphics recovered; keep Test27")
    result=base.serialize(records)
    return result,{"kind":"EXPERIMENTAL Test28 stage3 resource candidate","output_patch_sha256":sha(result),
        "records":len(records),"selection":sel["selection"],"stage3":stage,
        "unresolved_exception_stadiums":unresolved,"protected_stadiums":protected,
        "changed_lbas":sorted(touched),"independent_clean_original_patch":True,
        "runtime_stage_writer_fixed":False,"all_54_small_flags_verified":False,
        "names_fixed":False,"crowd_flags_verified":False,"stage3_complete":False,"release_authorized":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("clean-track","preview","preview-report","test25","test12","test08","output","report"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.report.exists(): p.error("Refusing overwrite")
    data,info=build(a.clean_track,a.preview,a.preview_report,[("Test25",a.test25),("Test12",a.test12),("Test08",a.test08)])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("xb") as f: f.write(data)
    with a.report.open("x",encoding="utf-8") as f: json.dump(info,f,indent=2)
    print("Experimental stage3 candidate:",a.output)
    print("Still unresolved:",info["unresolved_exception_stadiums"])
    print("No claim of stage3 completion or runtime verification.")
if __name__=="__main__": main()
