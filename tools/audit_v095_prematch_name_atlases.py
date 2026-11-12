#!/usr/bin/env python3
"""Inspect the exact official Test13 patch's three rasterized prematch-name
atlas records, without collecting any game data or claiming glyph recognition.

This is a READ-ONLY preparatory gate for a future Cape Verde layout fix.
The sector deltas are XOR masks, not the original or final bitmap. They cannot
by themselves identify on-screen glyphs or safe sprite placement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

PATCH_SHA = "159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214"
MAGIC = b"ISS26X01"
RECORD = 2388
SECTOR = 2352
GROUPS = {
    "T_NAME_E.BIN": tuple(range(8200, 8228)),
    "T_NAME_F.BIN": tuple(range(8230, 8258)),
    "T_NAME_G.BIN": tuple(range(8260, 8288)),
}
CLEAN_SHA = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"

def inspect(raw: bytes, expected_sha: str = PATCH_SHA) -> dict:
    sha = hashlib.sha256(raw).hexdigest().upper()
    if sha != expected_sha or raw[:8] != MAGIC:
        raise ValueError("Unexpected patch checksum or magic")
    count, = struct.unpack_from("<I", raw, 8)
    if count != 1492 or len(raw) != 12 + count * RECORD:
        raise ValueError("Expected independent Test13 with 1,492 complete records")
    by_lba = {}
    previous = -1
    for i in range(count):
        at = 12 + i * RECORD
        lba, = struct.unpack_from("<I", raw, at)
        if lba <= previous or lba >= 210951:
            raise ValueError("Unsorted, duplicate or invalid sector")
        previous = lba
        by_lba[lba] = raw[at + 4:at + RECORD]
    result = {}
    for resource, lbas in GROUPS.items():
        if any(lba not in by_lba for lba in lbas):
            raise ValueError(f"Atlas missing required changed sector: {resource}")
        detailed = []
        guards = bytearray()
        for lba in lbas:
            record = by_lba[lba]
            guard = record[:32]
            mask = record[32:]
            if len(guard) != 32 or len(mask) != SECTOR or any(mask[:24]):
                raise ValueError(f"Invalid source guard or changed CD header at {lba}")
            guards += guard
            detailed.append({
                "lba": lba,
                "changed_user_payload_bytes": sum(bool(v) for v in mask[24:2072]),
                "changed_edc_ecc_bytes": sum(bool(v) for v in mask[2072:]),
                "xor_mask_sha256": hashlib.sha256(mask).hexdigest().upper(),
            })
        result[resource] = {
            "changed_sector_count": len(lbas),
            "all_source_sector_guard_hashes_sha256": hashlib.sha256(guards).hexdigest().upper(),
            "total_changed_user_payload_bytes": sum(row["changed_user_payload_bytes"] for row in detailed),
            "total_changed_edc_ecc_bytes": sum(row["changed_edc_ecc_bytes"] for row in detailed),
            "sector_metadata": detailed,
        }
    return {
        "schema_version": 1,
        "audit": "ISS26 v0.9.5 Test13 prematch names, source-independent atlas inventory",
        "patch_sha256": sha,
        "clean_disc_required_for_later_repacker_sha256": CLEAN_SHA,
        "all_patch_record_count": len(by_lba),
        "name_atlas_changed_sector_count": sum(v["changed_sector_count"] for v in result.values()),
        "name_atlas_group_count": len(result),
        "resources": result,
        "user_required_visible_name": "Cape Verde",
        "regression_observed_in_game": "Cabo         Verde (split word spacing)",
        "font_and_glyph_source": "compressed graphical name atlas; source pixels not decoded from XOR masks",
        "name_placement_or_glyph_coordinates_verified": False,
        "game_patch_ready_for_stable": False,
        "next_step": "Decode actual compressed sprite with clean original Track01 plus patched resource; identify layout and replace only target name; rebuild independent sector patch.",
        "note": "No artwork or copyrighted game bytes emitted. Cannot assert which of E/F/G controls current display from sector metadata alone."
    }

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--patch", required=True, type=Path)
    ap.add_argument("--report", required=True, type=Path)
    args = ap.parse_args()
    result = inspect(args.patch.read_bytes())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for name, row in result["resources"].items():
        print(f"{name}: {row['changed_sector_count']} sectors, "
              f"{row['total_changed_user_payload_bytes']} changed payload bytes")
    print("PASS: three guarded raster name atlases, no original game data emitted")

if __name__ == "__main__":
    main()
