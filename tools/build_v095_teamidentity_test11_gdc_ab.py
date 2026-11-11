#!/usr/bin/env python3
"""Build diagnostic Test11 by reverting only 63 known stadium-GDC sector edits.

Input is a published, independently applicable ISS26X01 Test10 patch.
Output is again a standalone clean-original PS1 sector-XOR patch, NOT a
patch layered onto a previously modified game. No copyrighted game bytes
are read, embedded or copied. This is a controlled A/B test, not final art.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

SECTOR_SIZE = 2352
RECORD_SIZE = 4 + 32 + SECTOR_SIZE
EXPECTED_BASE_SHA = "9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B"
EXPECTED_INPUT_RECORDS = 1496
EXPECTED_OUTPUT_RECORDS = 1433
# Exactly the 63 sector LBAs implicated by earlier experimental Test07
# GDC stadium graphics edits. Revert *only* these sectors to CLEAN original.
# Original unmodified 12-track disc supplies the data at apply time.
STADIUM_LBAS = (
    10914,10915,11087,11088,11263,11264,11435,11436,11599,11600,
    11769,11770,11937,11938,12111,12112,12288,12289,12465,12466,
    12619,12620,12789,12790,12950,13123,13296,13472,13645,13646,
    13812,13813,13973,13974,14145,14146,14309,14310,14479,14480,
    14669,14670,14839,14840,15002,15003,15170,15171,15346,15347,
    15520,15521,15677,15678,15847,15848,16020,16193,16194,16356,
    16357,16548,16549,
)
ESSENTIAL_SLOTS = (852,955,5328,5329,6082,6083,6084,6085,6086,6087,
                   6088,6089,6090,6103,6250,6251,6252,6253,6254,
                   6255,6256,6257,6277,6279)
NAME_LBAS = tuple(range(8200,8228)) + tuple(range(8230,8258)) + tuple(range(8260,8288))


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def parse(raw: bytes) -> dict[int, bytes]:
    assert sha(raw) == EXPECTED_BASE_SHA, "Unexpected Test10 input release SHA"
    assert raw[:8] == b"ISS26X01", "Invalid independent patch signature"
    n, = struct.unpack_from("<I", raw, 8)
    assert n == EXPECTED_INPUT_RECORDS and len(raw) == 12+n*RECORD_SIZE
    previous = -1
    rows = {}
    for i in range(n):
        offset = 12 + i*RECORD_SIZE
        lba, = struct.unpack_from("<I", raw, offset)
        assert previous < lba < 210951, "Nonmonotonic / invalid source LBA"
        previous = lba
        entry = raw[offset:offset+RECORD_SIZE]
        assert len(entry) == RECORD_SIZE and any(entry[36:])
        rows[lba] = entry
    assert len(rows) == n
    return rows


def build(base: Path, output: Path, report: Path) -> dict:
    raw = base.read_bytes()
    original = parse(raw)
    assert len(STADIUM_LBAS) == len(set(STADIUM_LBAS)) == 63
    assert set(STADIUM_LBAS).issubset(original), "Some GDC LBAs are not in Test10"
    assert set(STADIUM_LBAS).isdisjoint(ESSENTIAL_SLOTS + NAME_LBAS)
    remaining = {k: v for k,v in original.items() if k not in STADIUM_LBAS}
    assert len(remaining) == EXPECTED_OUTPUT_RECORDS
    assert all(remaining[k] == original[k] for k in remaining)
    assert all(k in remaining for k in ESSENTIAL_SLOTS + NAME_LBAS)
    # Rebuild a complete standalone patch; the dropped sectors are never
    # touched, so they stay authentic clean-disc sectors with valid EDC/ECC.
    data = bytearray(b"ISS26X01"+struct.pack("<I",len(remaining)))
    for lba in sorted(remaining):
        data.extend(remaining[lba])
    built = bytes(data)
    assert len(built) == 12 + EXPECTED_OUTPUT_RECORDS * RECORD_SIZE
    expected_keys = sorted(set(original)-set(STADIUM_LBAS))
    verified = parse_output(built)
    assert sorted(verified) == expected_keys
    assert all(verified[k] == original[k] for k in expected_keys)
    assert sha(built) != sha(raw)
    output.parent.mkdir(parents=True,exist_ok=True)
    report.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(built)
    metadata = {
        "schema_version":1,
        "test":"TEST11 GDC-sector rollback A/B, diagnostic only",
        "input_test10_sha256":EXPECTED_BASE_SHA,
        "result_test11_sha256":sha(built),
        "result_patch_size":len(built),
        "input_sector_count":len(original),
        "output_sector_count":len(remaining),
        "reverted_gdc_sector_count":len(STADIUM_LBAS),
        "reverted_gdc_lbas":list(STADIUM_LBAS),
        "preserved_new_name_sectors":len(NAME_LBAS),
        "preserved_all_other_sector_records":True,
        "clean_original_sector_sha_guards_preserved":True,
        "status":"STRUCTURAL PASS; IN-GAME VISUAL RENDERING UNVERIFIED",
        "warning":"Original large flags may reappear; this is an A/B attribution probe, not corrected Bosnia/Cabo art",
        "stable_game_channel_changed":False,
    }
    report.write_text(json.dumps(metadata,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(metadata,indent=2))
    return metadata


def parse_output(data: bytes) -> dict[int,bytes]:
    assert data[:8]==b"ISS26X01"
    count,=struct.unpack_from("<I",data,8)
    assert len(data)==12+count*RECORD_SIZE
    result={}
    prev=-1
    for i in range(count):
        at=12+i*RECORD_SIZE
        lba,=struct.unpack_from("<I",data,at)
        assert prev<lba<210951
        prev=lba
        result[lba]=data[at:at+RECORD_SIZE]
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test10",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--report",required=True,type=Path)
    args=parser.parse_args()
    build(args.test10,args.output,args.report)


if __name__=="__main__":
    main()
