#!/usr/bin/env python3
"""Independent clean-original Test25: two Bosnia flag style-table repairs only.

Input is strictly the existing official Test13 standalone ISS26X01 patch.
Does NOT patch Track01 or claim a corrected flag image without a live test.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from build_v095_test12_gdc_descriptor_repair import fix_parity, valid_parity

TEST13_SHA = "159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214"
COUNT = 1492
SECTOR = 2352
RECORD = 4+32+SECTOR
TABLE_OFFSETS = (0x1D6F48,0x1E94CC,0x224C50,0x4AD4B8,0x575864)
ORIGINAL_SLOT30 = 7
TEST13_SLOT30_XOR = (0x30,0x0d,0x0d,0x30,0x30)
TARGET_STYLE = 55
TARGET_XOR = ORIGINAL_SLOT30 ^ TARGET_STYLE
TARGET_LBAS = {852,955}

def digest(b):
    return hashlib.sha256(b).hexdigest().upper()

def repair(patch, expected_sha=TEST13_SHA, expected_count=COUNT):
    if digest(patch) != expected_sha:
        raise ValueError("Wrong official Test13 SHA256; refusing to modify")
    if patch[:8] != b"ISS26X01":
        raise ValueError("Unknown patch magic")
    count, = struct.unpack_from("<I",patch,8)
    if count != expected_count or len(patch) != 12+count*RECORD:
        raise ValueError("Unexpected patch count or size")
    offsets = {}
    last = -1
    for i in range(count):
        at = 12+i*RECORD
        lba, = struct.unpack_from("<I",patch,at)
        if lba <= last or lba >= 210951:
            raise ValueError("Repeated/unsorted or invalid LBA")
        last = lba
        offsets[lba] = at+36
    output = bytearray(patch)
    actual_changes = []
    observations = []
    for start,oldmask in zip(TABLE_OFFSETS,TEST13_SLOT30_XOR):
        lba,pos = divmod(start,SECTOR)
        at = offsets.get(lba)
        if at is None:
            raise ValueError("Required style table is missing from official patch")
        raw = patch[at:at+SECTOR]
        if any(raw[:24]) or not valid_parity(raw):
            raise ValueError("Corrupt original Test13 XOR EDC/ECC or CD header")
        offset = pos+30
        if raw[offset] != oldmask:
            raise ValueError("Unexpected Bosnia style source mask")
        observations.append({"lba":lba,"oldXor":oldmask,"newXor":TARGET_XOR})
        if oldmask == TARGET_XOR: continue
        changed = bytearray(raw)
        changed[offset] = TARGET_XOR
        fix_parity(changed)
        if not valid_parity(changed):
            raise ValueError("Mode2 Form1 EDC/ECC failed")
        for index,(a,b) in enumerate(zip(raw,changed)):
            if a!=b and index!=offset and not 2072<=index<2352:
                raise ValueError("Unexpected extra game payload mutation")
        output[at:at+SECTOR] = changed
        actual_changes.append(lba)
    if set(actual_changes) != TARGET_LBAS or len(actual_changes)!=2:
        raise ValueError("Expected exactly two independent sector fixes")
    for lba,at in offsets.items():
        if output[at-32:at] != patch[at-32:at]:
            raise ValueError("Original sector guard changed")
        if lba not in TARGET_LBAS and output[at:at+SECTOR] != patch[at:at+SECTOR]:
            raise ValueError("Unrelated patch sector changed")
    candidate = bytes(output)
    return candidate,{
        "schemaVersion":1,"stage":"TEST25 EXPERIMENTAL, NOT STABLE",
        "inputTest13Sha256":TEST13_SHA,"outputSha256":digest(candidate),
        "recordCount":count,"originalSectorGuardsPreserved":True,
        "sourceCleanOriginalOnly":True,"changedLBAs":sorted(TARGET_LBAS),
        "unchangedRecords":count-2,"BosniaStyleFiveTables":[55]*5,
        "clubSlot54Style10Unchanged":True,"CapeVerdeStyle1Unchanged":True,
        "payloadBytesChanged":2,"mode2ParityRecomputed":True,
        "changesGameFeed":False,"requiresEmulatorVisualTest":True,
        "allNationalFlagsFixed":False,"BosniaFlagArtworkVerified":False,
        "entries":observations
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test13",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--report",type=Path,required=True)
    a = parser.parse_args()
    result, report = repair(a.test13.read_bytes())
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(result)
    a.report.write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print("PASS two Bosnia style tables (LBA 852/955); other 1490 records untouched")
    print("PASS full 1492-record self-contained clean-original ISS26X01 patch")
    print("PASS Mode2 Form1 EDC/ECC repaired; club style10 unchanged")
    print("SHA256",report["outputSha256"])
    print("Visual test still required; Cape Verde artwork not repaired")

if __name__=="__main__":
    main()
