#!/usr/bin/env python3
"""Build a guarded standalone Test13 A/B source isolation patch.

Reverts exactly four *entire original sectors* changed in earlier large national
graphics experiments while retaining all other Test12 independent-patch
records, including the Test12 GPU descriptor repair and Test10 raster names.

This diagnostic does NOT include a Cape Verde name or flag artwork repair;
the original large flag image may reappear. It is not a stable release.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from audit_v095_test10_test11_release_sectors import parse, RECORD

TEST12_SHA = "7E4FAC687487A3328BB564446DC4835C97D9A5841F335539EA56851F1958C3DD"
TARGETS = {
    6089:"DATSEL.BIN",
    6090:"DATSEL.BIN",
    6256:"DATSEL3.BIN",
    6257:"DATSEL3.BIN"
}
EXPECTED_TEST12_COUNT=1496
EXPECTED_TEST13_COUNT=1492

def build(base:Path, dest:Path, report:Path)->dict:
    rows=parse(base,TEST12_SHA,EXPECTED_TEST12_COUNT)
    if any(lba not in rows for lba in TARGETS):
        raise ValueError("Missing four pinned national flag graphic sector edits")
    saved={lba:record for lba,record in rows.items() if lba not in TARGETS}
    if len(saved)!=EXPECTED_TEST13_COUNT:
        raise ValueError("Unexpected record count after 4-sector isolation")
    if any(saved[lba]!=rows[lba] for lba in saved):
        raise ValueError("Unauthorised modification to common source records")
    data=bytearray(b"ISS26X01"+struct.pack("<I",len(saved)))
    for lba in sorted(saved):
        data.extend(struct.pack("<I",lba))
        data.extend(saved[lba])
    if len(data) != 12 + EXPECTED_TEST13_COUNT * RECORD:
        raise ValueError("Unexpected new patch size")
    digest=hashlib.sha256(data).hexdigest().upper()
    dest.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(data)
    result={
      "schema_version":1,
      "purpose":"Isolate prior DATSEL/DATSEL3 4-sector large national graphic modifications on top of Test12",
      "status":"EXPERIMENTAL VISUAL A/B ONLY; no name or flag fix claimed",
      "input_test12_sha256":TEST12_SHA,
      "test13_sha256":digest,
      "result_size":len(data),
      "result_sector_records":EXPECTED_TEST13_COUNT,
      "removed_source_sectors":TARGETS,
      "preserved_test12_records":EXPECTED_TEST13_COUNT,
      "preserved_gpu_descriptor_repair":True,
      "preserved_17_national_bitmap_names":True,
      "renames_cabo_to_cape":False,
      "changes_stable_or_test_feed":False,
      "clean_original_disc_required":True
    }
    report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print("PASS: Test13 independent sector patch built from pinned Test12")
    print("PASS: exactly four DATSEL/DATSEL3 records reverted, 1,492 others preserved")
    print("Test13 SHA-256:",digest)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--test12",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    a=p.parse_args()
    build(a.test12,a.output,a.report)

if __name__=="__main__":
    main()
