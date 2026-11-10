#!/usr/bin/env python3
"""Stage 8 safety gate: quarantine untested changes to stadium GDC sectors.

Compare two complete clean-original ISS26X01 patches, *not* the base ISO.
Fail closed if an update alters any sectors assigned to stadium GDC assets.
This is a conservative freeze pending verified in-emulator VRAM ownership,
not proof that other patches are visually correct.
"""
from __future__ import annotations
import argparse, json, re, struct
from pathlib import Path

MAGIC=b'ISS26X01'; RECORD_BYTES=2388; SECTOR_BYTES=2352

def sectors(path:Path):
    payload=path.read_bytes()
    if len(payload)<12 or payload[:8]!=MAGIC:
        raise ValueError('Invalid ISS26X01 header')
    count,=struct.unpack_from('<I',payload,8)
    if count>8192 or len(payload)!=12+RECORD_BYTES*count:
        raise ValueError('Invalid patch size')
    result={}
    for i in range(count):
        base=12+RECORD_BYTES*i
        lba,=struct.unpack_from('<I',payload,base)
        if lba in result:raise ValueError('Duplicate CD sector LBA')
        result[lba]=payload[base+4:base+RECORD_BYTES]
    return result

def stadium_extents(path:Path):
    result={}
    for line in path.read_text().splitlines():
        match=re.match(r'\s*(\d+)\s+(\d+)\s+/BIN/(GDC_[A-Z0-9]+\.BIN);1\s*$',line)
        if not match:continue
        lba,length,name=int(match[1]),int(match[2]),match[3]
        if name in result:raise ValueError('Duplicate stadium')
        result[name]=(lba,lba+(length+2047)//2048)
    if len(result)!=34:raise ValueError(f'Expected 34 stadium sources, got {len(result)}')
    return result

def changed_lbas(a:dict,b:dict):
    return sorted(k for k in a.keys()|b.keys() if a.get(k)!=b.get(k))

def classify(changed,extents):
    risky={}
    for name,(begin,end) in extents.items():
        overlapping=[x for x in changed if begin<=x<end]
        if overlapping:risky[name]=overlapping
    return risky

def check(baseline:Path,candidate:Path,inventory:Path):
    before=sectors(baseline);after=sectors(candidate)
    changed=changed_lbas(before,after)
    affected=classify(changed,stadium_extents(inventory))
    return {
      'result':'BLOCKED_PENDING_RUNTIME_VRAM_PROOF' if affected else 'PASS_GDC_UNCHANGED_ONLY',
      'candidate_is_not_runtime_verified':True,
      'changed_sector_count':len(changed),'changed_sectors':changed,
      'gdc_affected_count':len(affected),
      'gdc_affected_sector_count':len(set(x for ls in affected.values() for x in ls)),
      'gdc_affected':affected,
      'safety_rationale':'User PCSX-Redux screenshots of Test07 show stadium/pitch texture corruption; identical VRAM atlas coordinates are not proof of identical runtime texture identity.',
    }

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',type=Path,required=True)
    ap.add_argument('--candidate',type=Path,required=True)
    ap.add_argument('--inventory',type=Path,default=Path(__file__).with_name('stage6_gdc_extent_eu.txt'))
    ap.add_argument('--report',type=Path)
    args=ap.parse_args();report=check(args.baseline,args.candidate,args.inventory)
    report_str=json.dumps(report,indent=2,ensure_ascii=False)+'\n'
    if args.report:args.report.write_text(report_str)
    print(report_str)
    raise SystemExit(2 if report['gdc_affected_count'] else 0)
