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
import math
import json
from pathlib import Path
import re
import struct
from build_v095_test12_gdc_descriptor_repair import fix_parity, valid_parity
from probe_v095_name_gpu_atlas import CLEAN_SHA, directory_files, raw_sector, apply_sector, file_sha, SECTOR, RECORD
from v095_static_prematch_ram_trace import read_patch, resource, SELECT_LBA, SELECT_BYTES
from test27_stage_code_audit import audit as audit_stage_code
from build_v095_test25_bosnia_style_isolation import TABLE_OFFSETS
from test27_extract_real_flag_pixels import read_snapshot, sha_path, EXPECTED_ZIP_SHA
from analyze_flag_test26_unified import clut
from test27_gpu_stream_edit import (
    sha, TARGETS, CLUT_SHA, parse_uploads, take_tile, rewrite_resource,
    decode_stream, mapped_art, discover_upload_lists, stream_span, fragment_read, intersection,
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

class PatchedDiscView:
    """Read-only virtual raw-sector view for ISO9660 directory traversal."""
    def __init__(self,source,records):
        self.source=source
        self.records=records
    def seek(self,offset,whence=0):
        return self.source.seek(offset,whence)
    def read(self,n):
        at=self.source.tell()
        if n!=SECTOR or at%SECTOR:
            raise ValueError("Unexpected non-sector catalog read")
        return patched_sector(self.source,at//SECTOR,self.records)[1]


def physical_resource_size(clean_catalog,patched_catalog,name,records):
    """Never cross a different ISO extent. Recover sector padding only where
    an existing authentic patch explicitly modifies it. No new allocation."""
    lba,size=patched_catalog[name]
    clean_lba,clean_size=clean_catalog[name]
    if lba!=clean_lba:
        raise ValueError("Resource extent moved; no verified relocation model")
    following=min((at for at,_ in clean_catalog.values() if at>lba),default=lba+math.ceil(size/2048))
    following=min(following,min((at for at,_ in patched_catalog.values() if at>lba),default=following))
    limit=(following-lba)*2048
    if max(size,clean_size)>limit:
        raise ValueError("Directory resource overlaps following extent")
    # A patch record in the inter-file gap is not proof of file ownership.
    # Read only the exact patched ISO allocation; no speculative gap reads.
    physical=math.ceil(size/2048)*2048
    if not 0<physical<=min(limit,1024*1024):
        raise ValueError("Unsafe physical resource allocation")
    return lba,size,physical


def canonical_lists(blob,base):
    from test27_gpu_stream_edit import parse_uploads
    found={}
    for slot in range(0,min(32,len(blob)-3),4):
        try:
            table,rows=parse_uploads(blob,base,slot)
        except ValueError:
            continue
        found.setdefault((base,table),(slot,rows))
    return found


def root_audit(original,patched,base):
    result=[]
    for (_,old_table),(slot,old_rows) in canonical_lists(original,base).items():
        pointer=struct.unpack_from("<I",patched,slot)[0]
        row={"header_slot":slot,"original_table":old_table,
             "patched_pointer":f"{pointer:08X}","patched_table":pointer-base,
             "original_count":len(old_rows)}
        try:
            table,rows=parse_uploads(patched,base,slot)
            row["patched_count"]=len(rows)
            old_geo=[(u.kind,u.x,u.y,u.w,u.h,u.padding_field) for u in old_rows]
            new_geo=[(u.kind,u.x,u.y,u.w,u.h,u.padding_field) for u in rows]
            row["logical_geometry_equal"]=old_geo==new_geo
        except ValueError as exc:
            row["blocked"]=str(exc)
        result.append(row)
    return result


def target_signature(blob,base):
    """List of logical block geometry per target, ignoring stream/table offsets."""
    result={}
    for flag,(x,y) in TARGETS.items():
        matches={}
        for (b,table),(slot,rows) in canonical_lists(blob,base).items():
            for i,u in enumerate(rows):
                if u.x<x+16 and u.x+u.w>x and u.y<y+28 and u.y+u.h>y:
                    matches[u.offset]=(u.kind&255,u.x,u.y,u.w,u.h)
        result[flag]=sorted(matches.values())
    return result


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

def find_routes(blob,base_hint=None):
    possible=canonical_lists(blob,base_hint) if base_hint is not None else discover_upload_lists(blob)
    if not possible or len({base for base,table in possible})!=1:
        raise ValueError("No unique supported GPU RAM base/list")
    routes=[]
    for flag,(x,y) in TARGETS.items():
        coverage=set()
        unique={}
        for (base,table),(slot,rows) in possible.items():
            for i,u in enumerate(rows):
                box=intersection(u,flag)
                if box:
                    unique.setdefault((base,u.offset),(base,table,slot,rows,i,u,box))
        for base,table,slot,rows,i,u,box in unique.values():
            gx,gy,w,h=box
            coords={(xx,yy) for yy in range(gy,gy+h) for xx in range(gx,gx+w)}
            if coverage & coords:
                raise ValueError("Overlapping GPU target fragments: "+flag)
            coverage.update(coords)
            decoded,end=stream_span(blob,base,table,rows,u)
            old=fragment_read(decoded,u,box)
            routes.append({"flag":flag,"gpu_base":base,"list_pointer_slot":slot,
                "upload_index":i,"upload_offset":u.offset,"stream_offset":u.start,
                "stream_capacity_bytes":end-u.start,"decoded_bytes":len(decoded),
                "fragment":list(box),"old_tile_sha256":sha(old)})
        if len(coverage)!=16*28:
            raise ValueError("Incomplete GPU target coverage: "+flag)
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
    # Validate both palettes and every resource before producing any sector
    # edits. A failure in one flag does not hide the other resource blockers.
    palette_mapping={}
    issues=[]
    print("Verified captured 16-entry CLUT (BGR555 words):",
          " ".join(f"{w:04X}" for w in struct.unpack("<16H",palette)),flush=True)
    for name in TARGETS:
        try:
            palette_mapping[name]=mapped_art(name,palette)[1]
            print("Palette PASS:",name,palette_mapping[name],flush=True)
        except ValueError as exc:
            issues.append(f"Palette {name}: {exc}")
            print("Palette BLOCKED:",name,str(exc),flush=True)
    records=records_from_patch(read_patch(base))
    baseline=dict(records)
    updated={}
    resource_results=[]
    changed_lbas=set()
    with track.open("rb") as source:
        for lba in records: patched_sector(source,lba,records)
        # Collect actual MIPS instructions even if subsequent art preflight fails.
        # This compares the original code against Test25, without patching it.
        stage_code=audit_stage_code(resource(source,SELECT_LBA,SELECT_BYTES),
                                   read_resource(source,records,SELECT_LBA,SELECT_BYTES))
        print("STAGE_CODE_BEGIN",flush=True)
        print(json.dumps({k:v for k,v in stage_code.items() if k not in ("all_instructions","call_contexts","candidate_explicit_zero_stores","candidate_rectangle_constants")}),flush=True)
        print("STAGE_CODE_END",flush=True)
        tables=check_tables(source,records)
        print("PASS: five national/club style tables",flush=True)
        catalog=directory_files(source)
        patched_catalog=directory_files(PatchedDiscView(source,records))
        names=original_resources(catalog)
        if original_resources(patched_catalog)!=names:
            raise ValueError("Patched catalog missing a graphics resource")
        for name in names:
            try:
                lba,size,physical=physical_resource_size(catalog,patched_catalog,name,records)
                original=read_resource(source,{},lba,catalog[name][1])
                old=read_resource(source,records,lba,size)
                base_hint=0x800C8000 if "/GDC_" in name else 0x800F0000
                clean_lists=canonical_lists(original,base_hint)
                patched_lists=canonical_lists(old,base_hint)
                print("GPU LISTS:",name,"logical",catalog[name][1],size,"physical",physical,
                      "clean",[(hex(b),t,len(rows)) for (b,t),(_,rows) in clean_lists.items()],
                      "patched",[(hex(b),t,len(rows)) for (b,t),(_,rows) in patched_lists.items()],flush=True)
                print("GPU ROOTS:",name,json.dumps(root_audit(original,old,base_hint)),flush=True)
                clean_sig=target_signature(original,base_hint)
                new_sig=target_signature(old,base_hint)
                print("TARGET GEOMETRY:",name,"clean",clean_sig,"patched",new_sig,flush=True)
                if clean_sig!=new_sig or not all(clean_sig.values()):
                    raise ValueError("Logical target GPU geometry differs or is absent")
                original_routes=find_routes(original,base_hint)
                print("CLEAN ROUTES:",name,json.dumps(original_routes),flush=True)
                # Log the exact original and patched slice sizes, including
                # short packets, before any compression attempt.
                routes=find_routes(old,base_hint)
                print("ROUTE PASS:",name,json.dumps(routes),flush=True)
                key=lambda r:(r["flag"],tuple(r["fragment"]))
                clean_by={key(r):r for r in original_routes}
                if set(clean_by)!={key(r) for r in routes}:
                    raise ValueError("Original vs patched fragment layout mismatch")
                for r in routes:
                    before=clean_by[key(r)]
                    if r["decoded_bytes"]!=before["decoded_bytes"]:
                        raise ValueError(f"{r['flag']} packet decoded length differs from clean ({before['decoded_bytes']} -> {r['decoded_bytes']}); original compressed packet may be damaged")
                if len(palette_mapping)!=len(TARGETS):
                    continue
                new,changes=rewrite_resource(old,routes,palette)
            except (ValueError,AssertionError) as exc:
                issues.append(f"{name}: {exc}")
                print("RESOURCE BLOCKED:",name,str(exc),flush=True)
                continue
            # Do not create new out-of-file writes in the extended physical tail.
            for offset in range(0,len(old),2048):
                if offset>=size and old[offset:offset+2048]!=new[offset:offset+2048]:
                    raise ValueError("New write beyond logical ISO allocation")
            updated[name]=(lba,old,new)
            resource_results.append({"resource":name,"original_logical_bytes":catalog[name][1],"patched_logical_bytes":size,"verified_physical_bytes":physical,"source_sha256":sha(old),
                                     "candidate_sha256":sha(new),"edits":changes})
            print("RESOURCE PASS:",name,
                  json.dumps([{"flag":c["flag"],"stream_capacity_bytes":c["stream_capacity_bytes"],
                              "new_packed_bytes":c["new_packed_bytes"],
                              "compression_method":c["compression_method"]} for c in changes]),
                  flush=True)
        if issues:
            raise ValueError("No candidate emitted; complete palette/resource blockers:\n - "+"\n - ".join(issues))
        if set(updated)!=set(names):
            raise ValueError("Not all expected resources were rewritten; no candidate emitted")
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
        if directory_files(PatchedDiscView(source,records))!=patched_catalog:
            raise AssertionError("ISO catalog changed during composition")
    blob=serialize(records)
    return blob,{"schemaVersion":1,"kind":"EXPERIMENTAL standalone Test27 SOURCE ART candidate ONLY",
        "clean_track_sha256":CLEAN_SHA,"base_test25_sha256":TEST25_SHA,
        "output_patch_sha256":sha(blob),"records":len(records),
        "changed_lbas":sorted(changed_lbas),"previous_records_preserved_outside_targets":True,
        "style_tables_checked":len(tables),"stage_code_audit":stage_code,"regular_national_and_club_style_exclusivity_checked":True,
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
