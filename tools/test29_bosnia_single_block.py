#!/usr/bin/env python3
"""Experimental Test29: relocate Bosnia away from the Y=384 upload boundary.
Use authenticated local Test28 output and exact previously observed Bosnia art.
Only use an unreferenced regular-team style with full, unsplit coverage in
all 36 resources. Bonus-team and non-team texture consumers remain unproven.
No game install or release-feed modification.
"""
import argparse
import json
from pathlib import Path
import test27_build_standalone_atlas_candidate as base
from test27_gpu_stream_edit import sha, fragment_read
from test28_stage3_resources import packet_map,exact_packet,apply_packets
from build_v095_test25_bosnia_style_isolation import TABLE_OFFSETS

PREFERRED=(40,41,42)
STYLE_COUNT=72
SELECT_TABLE=0x1E94CC
BOSNIA_SLOT=30
OLD_STYLE=55
FIXED_TOP="C6D3053CA3F8C8348D52B071A8822B7F812082CCE5B3717956A2579396649ADA"
FIXED_BOTTOM="80DE037E29C7C8A9476E43B5C0AF79F6F6E53F0E2FBF9619F61D504791FDEAF7"

def xy(style):
    if style not in range(STYLE_COUNT): raise ValueError("Invalid style")
    return (832 if style<36 else 768)+16*(style%4),256+28*((style%36)//4)

def rect(style):
    return (*xy(style),16,28)

def get_maps(source,records):
    tables=[]
    for offset in TABLE_OFFSETS:
        lba,pos=divmod(offset,base.SECTOR)
        _,raw=base.patched_sector(source,lba,records)
        table=raw[pos:pos+78]
        if len(table)!=78 or table[0]!=1 or table[54]!=10:
            raise ValueError("Expected 78-slot team style table")
        tables.append(table)
    return tables

def eligible_geometry(style):
    if not 0<=style<STYLE_COUNT or style==OLD_STYLE:
        return False
    _,y=xy(style)
    # Avoid the observed boundary. Actual descriptor coverage is still
    # validated in each resource, not inferred from this geometry.
    return not (y<384<y+28)

def candidates():
    return [s for s in (*PREFERRED,*(i for i in range(STYLE_COUNT) if i not in PREFERRED))
            if eligible_geometry(s)]

def baseline_guard(tables):
    if len(tables)!=5 or any(len(t)!=78 for t in tables):
        raise ValueError("Expected five complete regular-team maps")
    for i,t in enumerate(tables):
        if t[BOSNIA_SLOT]!=OLD_STYLE:
            raise ValueError(f"Table {i+1}: Bosnia style {t[BOSNIA_SLOT]}, expected 55")
        if [j for j,v in enumerate(t) if v==OLD_STYLE]!=[BOSNIA_SLOT]:
            raise ValueError(f"Table {i+1}: Bosnia source style shared by other teams")

def select_extra_guard(source,records):
    # SELECT's selector was observed indexing up to 82 entries. Treat
    # four immediately following bytes as occupied if they match a style;
    # their semantic ownership is not proved. Do not edit them.
    lba,pos=divmod(SELECT_TABLE,base.SECTOR)
    _,raw=base.patched_sector(source,lba,records)
    if not 24<=pos or pos+82>2072:
        raise ValueError("Unexpected SELECT table/guard extent")
    return tuple(raw[pos+78:pos+82])

def owners(tables,style,extra=()):
    found=[{"table":i+1,"slot":j,"class":"national" if j<54 else "club"}
           for i,t in enumerate(tables) for j,v in enumerate(t) if v==style]
    found.extend({"table":"SELECT adjacent","slot":78+j,"class":"reserved guard"}
                 for j,v in enumerate(extra) if v==style)
    return found

def free_style(tables,style,extra=()):
    baseline_guard(tables)
    return eligible_geometry(style) and not owners(tables,style,extra)

def intersect(u,box):
    x,y,w,h=box
    a,b=max(u.x,x),max(u.y,y)
    c,d=min(u.x+u.w,x+w),min(u.y+u.h,y+h)
    return (a,b,c-a,d-b) if c>a and d>b else None

def replace_tile(decoded,u,box,tile):
    fragment_read(decoded,u,box)
    if len(tile)!=896 or box[2:]!=(16,28):
        raise ValueError("Expected one full 64x28 4bpp tile")
    x,y,w,h=box
    out=bytearray(decoded)
    for i in range(h):
        at=2*((y-u.y+i)*u.w+x-u.x)
        out[at:at+2*w]=tile[2*w*i:2*w*(i+1)]
    return bytes(out)

def known_art(blob,address=0x800F0000):
    pieces={}
    for r in base.find_routes(blob,address):
        if r["flag"]!="bosnia": continue
        box=tuple(r["fragment"])
        from test27_gpu_stream_edit import parse_uploads
        table,rows=parse_uploads(blob,address,r["list_pointer_slot"])
        u=rows[r["upload_index"]]
        decoded,_=exact_packet(blob,address,table,rows,u)
        piece=fragment_read(decoded,u,box)
        pieces[box]=piece
    a=pieces.get((816,368,16,16),b"")
    b=pieces.get((816,384,16,12),b"")
    if len(pieces)!=2 or sha(a)!=FIXED_TOP or sha(b)!=FIXED_BOTTOM:
        raise ValueError("Tested Bosnia source fragment hash mismatch")
    return a+b

def relocate_resource(clean,current,address,style,art):
    from test27_gpu_stream_edit import discover_upload_lists
    if discover_upload_lists(clean,address)!=discover_upload_lists(current,address):
        raise ValueError("Resource descriptors differ from clean")
    box=rect(style)
    jobs=[]
    hashes=set()
    for table,slot,rows,u in packet_map(clean,address):
        overlap=intersect(u,box)
        if overlap is None: continue
        # Every intersecting writer must fully cover the tile. Do not solve
        # overlapping or incomplete uploads by guessing their order.
        if overlap!=box:
            raise ValueError("Candidate tile crosses an upload boundary")
        a,stop=exact_packet(clean,address,table,rows,u)
        b,end=exact_packet(current,address,table,rows,u)
        if end>stop:
            raise ValueError("Current packet exceeds original allocation")
        old=fragment_read(a,u,box)
        prior=fragment_read(b,u,box)
        if old!=prior:
            raise ValueError("Candidate tile already modified by Test28")
        hashes.add(sha(old))
        jobs.append((u,stop,b,replace_tile(b,u,box,art)))
    if not jobs or len(hashes)!=1:
        raise ValueError("Absent or conflicting candidate atlas writers")
    result,edits=apply_packets(clean,current,address,jobs)
    # Independently decode all edited writers from the completed result.
    for table,slot,rows,u in packet_map(result,address):
        if intersect(u,box):
            raw,_=exact_packet(result,address,table,rows,u)
            if fragment_read(raw,u,box)!=art:
                raise AssertionError("Final relocated art does not round-trip")
    return result,{"writers":len(jobs),"clean_tile_sha256":next(iter(hashes)),
                   "output_art_sha256":sha(art),"edits":edits}

def reroute(source,records,style,before,extra=()):
    if not free_style(before,style,extra): raise ValueError("Unsafe style allocation")
    changed=[]
    for offset in TABLE_OFFSETS:
        lba,pos=divmod(offset,base.SECTOR)
        _,raw=base.patched_sector(source,lba,records)
        old=raw[24:2072]
        at=pos+BOSNIA_SLOT-24
        if not 0<=at<len(old) or old[at]!=OLD_STYLE:
            raise ValueError("Bosnia map guard failed")
        new=bytearray(old)
        new[at]=style
        changed.extend(base.compose_resource(source,records,lba,old,bytes(new)))
    expected=[t[:BOSNIA_SLOT]+bytes([style])+t[BOSNIA_SLOT+1:] for t in before]
    if get_maps(source,records)!=expected:
        raise AssertionError("Unexpected style-table mutation")
    if select_extra_guard(source,records)!=tuple(extra):
        raise AssertionError("Adjacent SELECT guard changed")
    return changed

def build(track,patch,report):
    if base.file_sha(track)!=base.CLEAN_SHA: raise ValueError("Wrong clean original Track01")
    info=json.loads(report.read_text(encoding="utf-8-sig"))
    p=patch.read_bytes()
    if (info.get("kind")!="EXPERIMENTAL Test28 stage3 resource candidate" or
        info.get("release_authorized") is not False or info.get("output_patch_sha256")!=sha(p)):
        raise ValueError("Need matching Test28 Stage3 patch and build report")
    records=base.records_from_patch(p,sha(p),info["records"])
    previous=dict(records)
    trials={}
    with track.open("rb") as f:
        for lba in records: base.patched_sector(f,lba,records)
        maps=get_maps(f,records)
        baseline_guard(maps)
        extra=select_extra_guard(f,records)
        occupancy={s:owners(maps,s,extra) for s in range(STYLE_COUNT)}
        free=[s for s in candidates() if not occupancy[s]]
        print("STYLE OCCUPANCY:",json.dumps(occupancy),flush=True)
        print("SELECT ADJACENT GUARD:",list(extra),flush=True)
        print("FREE SINGLE-BLOCK CANDIDATES:",free,flush=True)
        if not free:
            raise ValueError("No unreferenced single-block style in actual Test28 maps; no texture or map written")
        cat=base.directory_files(f)
        pc=base.directory_files(base.PatchedDiscView(f,records))
        names=base.original_resources(cat)
        data={}
        for name in names:
            lba,size=cat[name]
            if pc[name]!=(lba,size): raise ValueError("Non-clean resource size: "+name)
            data[name]=(base.read_resource(f,{},lba,size),base.read_resource(f,records,lba,size))
        art=known_art(data["BIN/DATSEL.BIN"][1])
        if known_art(data["BIN/DATSEL3.BIN"][1])!=art:
            raise ValueError("Selection artwork copies differ")
        chosen=None
        for style in free:
            print("TRY STYLE",style,rect(style),flush=True)
            jobs={}; blocked={}
            for name,(clean,current) in data.items():
                address=0x800C8000 if "/GDC_" in name else 0x800F0000
                try:
                    jobs[name]=relocate_resource(clean,current,address,style,art)
                except (ValueError,AssertionError) as exc:
                    blocked[name]=str(exc)
                    print("BLOCKED",name,str(exc),flush=True)
            trials[style]={"passed":len(jobs),"blocked":blocked}
            if len(jobs)==len(names):
                chosen=style
                break
        if chosen is None:
            raise ValueError("No verified 36-resource candidate: "+json.dumps(trials))
        changed=set()
        reports={}
        for name,(result,r) in jobs.items():
            lba,size=cat[name]
            touched=base.compose_resource(f,records,lba,data[name][1],result)
            if changed.intersection(touched): raise AssertionError("Overlapping sector edits")
            changed.update(touched)
            if base.read_resource(f,records,lba,size)!=result:
                raise AssertionError("Resource readback mismatch")
            reports[name]={**r,"changed_lbas":touched}
        map_lbas=reroute(f,records,chosen,maps,extra)
        if changed.intersection(map_lbas): raise AssertionError("Resource/map overlap")
        changed.update(map_lbas)
        if base.directory_files(base.PatchedDiscView(f,records))!=pc:
            raise AssertionError("ISO catalog changed")
        if any(records.get(i)!=previous.get(i) for i in set(records)|set(previous) if i not in changed):
            raise AssertionError("Unrelated record changed")
        for i in records: base.patched_sector(f,i,records)
    out=base.serialize(records)
    return out,{"kind":"EXPERIMENTAL Test29 Bosnia single-block relocation",
        "output_patch_sha256":sha(out),"input_test28_sha256":sha(p),"records":len(records),
        "old_style":OLD_STYLE,"new_style":chosen,"new_vram_words":list(rect(chosen)),
        "candidate_trials":trials,"actual_style_occupancy":occupancy,"select_adjacent_guard":list(extra),"resources":reports,"mapping_lbas":map_lbas,
        "changed_lbas":sorted(changed),"regular_54_and_24_maps_checked":True,
        "bonus_and_other_texture_consumers_verified":False,
        "original_bosnia_tile_retained":True,"cape_verde_source_preserved":True,
        "independent_clean_original_patch":True,"runtime_crop_fixed":False,
        "release_authorized":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ("clean-track","test28","test28-report","output","report"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    if a.output.exists() or a.report.exists(): p.error("Refusing overwrite")
    raw,info=build(a.clean_track,a.test28,a.test28_report)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("xb") as f: f.write(raw)
    with a.report.open("x",encoding="utf-8") as f: json.dump(info,f,indent=2)
    print("Experimental Test29 built:",a.output,"style",info["new_style"])
    print("No runtime crop fix claimed; test home/away banners and unrelated teams.")
if __name__=="__main__": main()
