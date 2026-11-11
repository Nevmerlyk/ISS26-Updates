#!/usr/bin/env python3
"""Read-only metadata audit of published standalone TEST10/TEST11 .iss26p files.
No original game bytes, binary assets or XOR masks are committed or printed.
GDC ISO9660 extent metadata was inspected on the user's clean EU SLES-03321 disc.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

SECTOR=2352
RECORD=4+32+SECTOR
TEST10_SHA="9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B"
TEST11_SHA="8492E97B915CBB4E3C7C86B974561739912DD0045E4640AFC09FE76629912F11"
STADIUM_FILE_EXTENTS=[
    ("BIN/GDC_AD.BIN", 12560, 140632),
    ("BIN/GDC_AN.BIN", 12730, 140924),
    ("BIN/GDC_BD.BIN", 16300, 135840),
    ("BIN/GDC_BN.BIN", 16470, 195376),
    ("BIN/GDC_CD.BIN", 13240, 135580),
    ("BIN/GDC_CN.BIN", 13410, 147284),
    ("BIN/GDC_DD.BIN", 10860, 131616),
    ("BIN/GDC_DN.BIN", 11030, 132112),
    ("BIN/GDC_FD.BIN", 11200, 151828),
    ("BIN/GDC_FN.BIN", 11370, 155172),
    ("BIN/GDC_GDJ.BIN", 14260, 120576),
    ("BIN/GDC_GNJ.BIN", 14430, 120576),
    ("BIN/GDC_HD.BIN", 13580, 154172),
    ("BIN/GDC_HN.BIN", 13750, 142232),
    ("BIN/GDC_ID.BIN", 15280, 159992),
    ("BIN/GDC_IN.BIN", 15450, 167236),
    ("BIN/GDC_JD.BIN", 11540, 143836),
    ("BIN/GDC_JN.BIN", 11710, 136928),
    ("BIN/GDC_MD.BIN", 12220, 160720),
    ("BIN/GDC_MDJ.BIN", 14600, 161408),
    ("BIN/GDC_MN.BIN", 12390, 168724),
    ("BIN/GDC_MNJ.BIN", 14770, 161928),
    ("BIN/GDC_OD.BIN", 15620, 138304),
    ("BIN/GDC_ON.BIN", 15790, 137660),
    ("BIN/GDC_PD.BIN", 12900, 122712),
    ("BIN/GDC_PN.BIN", 13070, 123356),
    ("BIN/GDC_RDJ.BIN", 14940, 148748),
    ("BIN/GDC_RNJ.BIN", 15110, 145380),
    ("BIN/GDC_SD.BIN", 11880, 136916),
    ("BIN/GDC_SN.BIN", 12050, 140892),
    ("BIN/GDC_TD.BIN", 13920, 130204),
    ("BIN/GDC_TN.BIN", 14090, 134884),
    ("BIN/GDC_VD.BIN", 15960, 142028),
    ("BIN/GDC_VN.BIN", 16130, 148700),
]

def parse(p: Path, expected_sha: str, expected_count: int):
    data=p.read_bytes()
    actual=hashlib.sha256(data).hexdigest().upper()
    if actual!=expected_sha or data[:8]!=b"ISS26X01":
        raise ValueError("Release digest or ISS26X01 signature mismatch: "+str(p))
    count,=struct.unpack_from("<I",data,8)
    if count!=expected_count or len(data)!=12+count*RECORD:
        raise ValueError("Bad ISS26X01 record count or length: "+str(p))
    rows={}
    prev=-1
    for i in range(count):
        at=12+i*RECORD
        lba,=struct.unpack_from("<I",data,at)
        if lba<=prev or lba>=210951:
            raise ValueError("Invalid record order or LBA")
        prev=lba
        rows[lba]=data[at+4:at+RECORD]
    return rows

def identify_gdc(lba: int):
    matched=[(name, start, size) for name,start,size in STADIUM_FILE_EXTENTS
             if start<=lba<start+math.ceil(size/2048)]
    if len(matched)!=1:
        raise ValueError(f"Expected exactly one GDC resource for sector {lba}: {matched}")
    name,start,size=matched[0]
    return name,(lba-start)*2048,size

def report(test10: Path,test11: Path):
    a=parse(test10,TEST10_SHA,1496)
    b=parse(test11,TEST11_SHA,1433)
    shared=set(a)&set(b)
    if set(b)!=shared or any(a[lba]!=b[lba] for lba in shared):
        raise ValueError("TEST11 changed other TEST10 sectors instead of reverting only GDC")
    removed=sorted(set(a)-set(b))
    if len(removed)!=63:
        raise ValueError(f"Expected 63 GDC sectors, got {len(removed)}")
    records=[]
    per_resource={}
    for lba in removed:
        blob=a[lba]
        mask=blob[32:]
        if len(mask)!=SECTOR or not any(mask):
            raise ValueError(f"Invalid XOR record at {lba}")
        name,offset,size=identify_gdc(lba)
        info={
            "lba":lba,
            "resource":name,
            "resource_offset":offset,
            "changed_header_bytes":sum(bool(v) for v in mask[:24]),
            "changed_payload_bytes":sum(bool(v) for v in mask[24:2072]),
            "changed_edc_ecc_bytes":sum(bool(v) for v in mask[2072:]),
            "first_changed_payload_offset": next((i for i in range(24,2072) if mask[i]),None)
        }
        if info["changed_header_bytes"]:
            raise ValueError(f"Raw CD header modified at LBA {lba}")
        records.append(info)
        d=per_resource.setdefault(name,{"record_count":0,"payload_changed_bytes":0,"edc_ecc_changed_bytes":0,"lbas":[]})
        d["record_count"]+=1
        d["payload_changed_bytes"]+=info["changed_payload_bytes"]
        d["edc_ecc_changed_bytes"]+=info["changed_edc_ecc_bytes"]
        d["lbas"].append(lba)
    return {
      "schema_version":1,
      "purpose":"TEST10 vs TEST11 exact published GDC XOR-sector metadata for patch 0.9.5",
      "test10_sha256":TEST10_SHA,"test11_sha256":TEST11_SHA,
      "test10_record_count":len(a),"test11_record_count":len(b),
      "unchanged_common_sector_count":len(shared),
      "reverted_gdc_sector_count":len(removed),
      "reverted_lbas":removed,
      "per_gdc_resource":per_resource,
      "per_sector":records,
      "original_game_data_included":False,
      "test12_published":False
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--test10",type=Path,required=True)
    p.add_argument("--test11",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args()
    result=report(args.test10,args.test11)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("PASS: TEST10 and TEST11 SHA256, exact subset identity, 63 GDC sectors")
    print("PASS: matched",len(result["per_gdc_resource"]),"GDC resources")
    for name,d in sorted(result["per_gdc_resource"].items()):
        print(name,d["record_count"],"sectors",d["payload_changed_bytes"],"changed payload bytes")

if __name__=="__main__":
    main()
