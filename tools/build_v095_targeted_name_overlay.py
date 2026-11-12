#!/usr/bin/env python3
"""Guarded final-step assembler for targeted ISS26 v0.9.5 prematch name edits.

It does NOT decode or typeset the game's compressed raster name atlases.
Only use a manifest produced from a verified decode/re-encode operation.
Run against the user's OWN clean European Track01 and a pinned Test13 patch.
Input image is never modified. Output is an independent ISS26X01 patch that
can be installed on a CLEAN ORIGINAL. No game image or graphics exported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_v095_prematch_name_atlases import PATCH_SHA, CLEAN_SHA, GROUPS
from build_v094_pointer_repair import edc, ecc

SECTOR=2352
RECORD=2388
COUNT=1492
ALLOWED={lba for group in GROUPS.values() for lba in group}

def sha(data: bytes)->str:
    return hashlib.sha256(data).hexdigest().upper()

def read_patch(data:bytes, expected_digest:str=PATCH_SHA, expected_count:int=COUNT):
    if sha(data)!=expected_digest or data[:8]!=b"ISS26X01":
        raise ValueError("Source patch signature or digest mismatch")
    count,=struct.unpack_from("<I",data,8)
    if count!=expected_count or len(data)!=12+count*RECORD:
        raise ValueError("Source patch size/count mismatch")
    records={}
    previous=-1
    for i in range(count):
        off=12+i*RECORD
        lba,=struct.unpack_from("<I",data,off)
        if lba<=previous or lba>=210951:
            raise ValueError("Patch sectors must be strictly increasing and bounded")
        previous=lba
        records[lba]=data[off+4:off+RECORD]
    return records

def correct_xor_parity(mask:bytearray)->None:
    # Sector-mode Form1 parity is linear for XOR deltas. The original raw
    # sync/address/subheader are immutable and the ECC address is zeroed.
    if len(mask)!=SECTOR or any(mask[:24]):
        raise ValueError("Cannot modify CD sync/address/subheader")
    mask[2072:2076]=edc(mask[16:2072])
    source=bytearray(mask[12:2076])
    source[:4]=bytes(4)
    parity_p=bytes(ecc(source,86,24,2,86))
    mask[2076:2248]=parity_p
    mask[2248:2352]=ecc(source+parity_p,52,43,86,88)

def validate_manifest(manifest:dict):
    if not isinstance(manifest,dict) or manifest.get("schema_version")!=1:
        raise ValueError("Required manifest schema_version=1")
    if manifest.get("target_label")!="Cape Verde":
        raise ValueError("Target label must be exactly Cape Verde")
    if manifest.get("target_screen")!="prematch_team_name":
        raise ValueError("Only prematch names may be edited")
    edits=manifest.get("edits")
    if not isinstance(edits,list) or not 1<=len(edits)<=512:
        raise ValueError("Require 1..512 explicitly verified raster byte edits")
    checked=[]
    changed_positions=set()
    for row in edits:
        if not isinstance(row,dict):
            raise ValueError("Bad edit record")
        lba=row.get("lba")
        offset=row.get("sector_offset")
        resource=row.get("resource")
        old=row.get("expected_patched_hex")
        new=row.get("replacement_patched_hex")
        if not isinstance(lba,int) or lba not in ALLOWED:
            raise ValueError("Edit outside T_NAME_E/F/G atlas sectors")
        if resource not in GROUPS or lba not in GROUPS[resource]:
            raise ValueError("Atlas name does not match sector")
        if not isinstance(offset,int) or not isinstance(old,str) or not isinstance(new,str):
            raise ValueError("Edit offset and expected/replacement bytes required")
        try:
            old_bytes=bytes.fromhex(old)
            new_bytes=bytes.fromhex(new)
        except ValueError as exc:
            raise ValueError("Invalid hex payload") from exc
        if not old_bytes or len(old_bytes)!=len(new_bytes) or len(old_bytes)>256:
            raise ValueError("Only length-preserving, 1..256-byte changes allowed")
        if not 24<=offset and offset+len(old_bytes)<=2072:
            raise ValueError("Edit must remain inside Mode2 Form1 user payload")
        if offset+len(old_bytes)>2072:
            raise ValueError("Edit crosses CD parity boundary")
        if old_bytes==new_bytes:
            raise ValueError("No-op edit is not permitted")
        for i in range(len(old_bytes)):
            key=(lba,offset+i)
            if key in changed_positions:
                raise ValueError("Overlapping atlas edits")
            changed_positions.add(key)
        checked.append((lba,offset,old_bytes,new_bytes,resource))
    return checked

def build(clean_track:Path,base_patch:Path,manifest_path:Path,output:Path,
          report:Path,*,expected_clean_sha:str=CLEAN_SHA,
          expected_patch_sha:str=PATCH_SHA, expected_records:int=COUNT):
    # Validate and load NO MORE THAN the small original patch.
    # Only source sectors touched by the verified manifest are read from ISO.
    with clean_track.open("rb") as src:
        actual=hashlib.file_digest(src,"sha256").hexdigest().upper()
        if actual!=expected_clean_sha:
            raise ValueError("Clean European Track01 SHA256 differs from pinned source")
    records=read_patch(base_patch.read_bytes(),expected_patch_sha,expected_records)
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    edits=validate_manifest(manifest)
    changed={}
    with clean_track.open("rb") as source:
        for lba,offset,expected,replacement,resource in edits:
            if lba not in records:
                raise ValueError(f"Missing sector {lba} in base patch")
            guard_and_mask=records[lba]
            guard=guard_and_mask[:32]
            prior_mask=bytearray(guard_and_mask[32:])
            if not any(prior_mask) or len(prior_mask)!=SECTOR or any(prior_mask[:24]):
                raise ValueError("Corrupt base sector mask")
            source.seek(lba*SECTOR)
            clean=source.read(SECTOR)
            if len(clean)!=SECTOR or sha(clean)!=guard.hex().upper():
                raise ValueError(f"Source clean sector guard mismatch at LBA {lba}")
            if clean[15]!=2 or (clean[18]&0x20):
                raise ValueError("Expected PS1 Mode2 Form1 sector")
            if lba not in changed:
                changed[lba]=prior_mask
            mask=changed[lba]
            actual_before=bytes(clean[offset+i]^mask[offset+i] for i in range(len(expected)))
            if actual_before!=expected:
                raise ValueError(f"Source patched bitmap bytes differ at LBA {lba}, offset {offset}")
            for i,(a,b) in enumerate(zip(expected,replacement)):
                mask[offset+i]^=a^b
            if bytes(clean[offset+i]^mask[offset+i] for i in range(len(replacement)))!=replacement:
                raise ValueError("Post-edit bytes not reproducible")
    for lba,mask in changed.items():
        correct_xor_parity(mask)
        record=records[lba]
        records[lba]=record[:32]+bytes(mask)
    if len(records)!=expected_records:
        raise ValueError("Unexpected record count")
    data=bytearray(b"ISS26X01"+struct.pack("<I",len(records)))
    for lba in sorted(records):
        data+=struct.pack("<I",lba)+records[lba]
    if len(data)!=12+expected_records*RECORD:
        raise ValueError("Patch length changed")
    output.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(data)
    summary={
        "schema_version":1,
        "test":"Standalone ISS26 game v0.9.5 Cape Verde prematch atlas candidate",
        "target_label":"Cape Verde",
        "output_patch_sha256":sha(data),
        "output_patch_records":len(records),
        "changed_atlas_sectors":sorted(changed),
        "edited_bytes":sum(len(x[2]) for x in edits),
        "untouched_records_count":len(records)-len(changed),
        "source_clean_disc_sha256":actual,
        "source_patch_sha256":expected_patch_sha,
        "no_original_disc_data_included":True,
        "preserves_all_non_name_atlas_sectors":True,
        "visual_spelling_or_spacing_verified":False,
        "stable_game_feed_changed":False,
    }
    report.write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--test13",required=True,type=Path)
    p.add_argument("--edits",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    a=p.parse_args()
    result=build(a.clean_track,a.test13,a.edits,a.output,a.report)
    print("PASS: targeted name-atlas candidate assembled; GAMEPLAY NOT YET VERIFIED")
    print("Patch SHA256:",result["output_patch_sha256"])

if __name__=="__main__":
    main()
