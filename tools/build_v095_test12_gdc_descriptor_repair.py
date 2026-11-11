#!/usr/bin/env python3
"""Diagnostic ISS26 v0.9.5 Test12 candidate: repair only damaged GPU upload
command-table bytes while retaining ALL other Test10 sector modifications.

The build reads the already released standalone Test10 ISS26X01 patch, not a
copyrighted ISO. Every output sector remains guarded by its clean original
SHA-256, with regenerated Mode2 Form1 EDC/ECC deltas. No stable/test feed
is changed by this builder; an emulator visual test is REQUIRED.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_v095_test10_test11_release_sectors import (
    TEST10_SHA, RECORD, SECTOR, parse
)
from build_v094_pointer_repair import edc, ecc

# All five ranges were read from the actual EU original's GPU upload lists.
# Tuple: resource, original ISO start LBA, actual affected sector, start/end
# file offsets of the descriptor table (not texture payload). The separate
# verified published Test10/Test11 analysis proved 2070 modified bytes in
# these five ranges; no other GDC upload descriptor table overlapped changes.
TABLES = (
    ("BIN/GDC_FD.BIN", 11200, 11263, 128488, 129032, 8),
    ("BIN/GDC_FN.BIN", 11370, 11435, 133440, 134240, 787),
    ("BIN/GDC_JD.BIN", 11540, 11599, 120496, 121040, 203),
    ("BIN/GDC_ID.BIN", 15280, 15346, 136652, 137196, 536),
    ("BIN/GDC_IN.BIN", 15450, 15520, 143896, 144440, 536),
)

def fix_parity(mask: bytearray) -> None:
    if any(mask[:24]):
        raise ValueError("Unexpected CD header/subheader change")
    mask[2072:2076] = edc(mask[16:2072])
    payload = bytearray(mask[12:2076])
    payload[:4] = bytes(4)
    p = bytes(ecc(payload, 86, 24, 2, 86))
    mask[2076:2248] = p
    mask[2248:2352] = ecc(payload + p, 52, 43, 86, 88)

def valid_parity(mask: bytes) -> bool:
    check = bytearray(mask)
    fix_parity(check)
    return bytes(check) == mask

def build(source: Path, output: Path, report: Path) -> dict:
    original = parse(source, TEST10_SHA, 1496)
    updated = dict(original)
    by_file = {}
    for resource, first_lba, lba, start, end, expected in TABLES:
        guard_and_mask = original.get(lba)
        if not guard_and_mask or len(guard_and_mask) != 32 + SECTOR:
            raise ValueError(f"Missing expected Test10 sector {lba}")
        guard = guard_and_mask[:32]
        mask = bytearray(guard_and_mask[32:])
        if not valid_parity(mask):
            raise ValueError(f"Published Test10 sector EDC/ECC invalid: {lba}")
        before = bytes(mask)
        base = (lba-first_lba)*2048
        changed = 0
        # The descriptor table may begin in a preceding *unchanged*
        # sector. Restore only its overlap with this modified sector.
        for offset in range(max(start,base),min(end,base+2048)):
            idx = 24 + offset - base
            if not (24 <= idx < 2072):
                raise ValueError(f"Descriptor crosses expected patch sector: {resource}")
            changed += mask[idx] != 0
            mask[idx] = 0
        if changed != expected:
            raise ValueError(f"{resource}: unexpected descriptor difference count "
                             f"{changed}, expected {expected}")
        fix_parity(mask)
        if not valid_parity(mask):
            raise ValueError(f"New EDC/ECC self-check failed: {resource}")
        if mask[:24] != before[:24]:
            raise ValueError("Modified raw CD sector header")
        if any(mask[i] != before[i] for i in range(24,2072)
               if not start <= base+i-24 < end):
            raise ValueError(f"Unplanned texture payload alteration: {resource}")
        updated[lba] = guard + bytes(mask)
        by_file[resource] = {
            "lba": lba,
            "original_iso_file_start_lba": first_lba,
            "descriptor_range": [start,end],
            "descriptor_bytes_restored": changed,
            "source_guard_unchanged": True,
            "other_texture_delta_bytes_unchanged": True,
            "parity_recomputed": True,
        }
    if sum(x["descriptor_bytes_restored"] for x in by_file.values()) != 2070:
        raise ValueError("Failed exact restoration-count guard")
    if any(original[lba] != updated[lba] for lba in original
           if lba not in {x[2] for x in TABLES}):
        raise ValueError("Non-target Test10 sector record modified")
    raw = bytearray(b"ISS26X01" + struct.pack("<I", len(updated)))
    for lba in sorted(updated):
        raw.extend(struct.pack("<I", lba))
        raw.extend(updated[lba])
    if len(raw) != 12 + 1496*RECORD:
        raise ValueError("Changed standalone patch length or sector count")
    output.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest().upper()
    metadata = {
        "schema_version":1,
        "kind":"game patch Test12 experimental, descriptor-only rollback",
        "not_stable":True,
        "requires_visual_test":True,
        "original_clean_source_required_at_install":True,
        "base_test10_sha256":TEST10_SHA,
        "test12_sha256":digest,
        "patch_bytes":len(raw),
        "records":len(updated),
        "changed_sectors":len(TABLES),
        "restored_gpu_descriptor_bytes":2070,
        "untouched_other_patch_records":len(updated)-len(TABLES),
        "affected_resources":by_file,
        "game_patch_feeds_changed":False,
        "notice":"Targeted diagnostic candidate; no visual flag fix claimed."
    }
    report.write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    print("PASS: 2,070 original GPU list bytes restored in five sectors")
    print("PASS: original sector hashes retained; EDC/ECC parity validated")
    print("PASS: 1,491 other Test10 sector records byte-identical")
    print("TEST12 SHA-256:",digest)
    return metadata

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--test10",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    build(a.test10,a.output,a.report)

if __name__ == "__main__":
    main()
