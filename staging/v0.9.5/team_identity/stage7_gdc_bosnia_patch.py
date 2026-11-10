#!/usr/bin/env python3
"""Stage 7: Bosnia 64x28 atlas correction in ALL 34 GDC stadium streams.

Independent clean-EU-Track01 ISS26X01 output, logically layered on static-
verified Test06. Source GPU pointer base 0x800C8000 is independently validated
by WE decode and the next GPU command's pointer. Do not alter other tile bytes.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter
from pathlib import Path
from team_identity_audit import PatchedDisc,BASE_SHA
from merge_verified import merge,parse_patch
from stage6_gdc_pointer_audit import parse_inventory,read_commands
from wecodec_stage5 import decode,encode,optimize_literal_packets

ROOT=Path(__file__).resolve().parent
BASELOAD=0x800C8000
BOSNIA_UV_RECT=(864,320,16,28)
GPU_REGION=(864,256,32,128)
ART_NBYTES=896
BLOCK_LEN=8192
TEST06_SHA='3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636'
TEST06_IMAGE_SHA='A3B94E6837D9E4FFC75B8F0440E39BF26CE806B57668ACB49839488E5928FAB2'

def logical_offset_to_raw(lba:int,pos:int)->int:
    return (lba+pos//2048)*2352+24+pos%2048

def split_guarded_edits(lba:int,pos:int,before:bytes,after:bytes,description:str):
    if not before or len(before)!=len(after):raise ValueError('Unequal edit')
    result=[];idx=0
    while idx<len(before):
        n=min(len(before)-idx,2048-(pos+idx)%2048)
        result.append({'raw_offset':logical_offset_to_raw(lba,pos+idx),
            'expected_hex':before[idx:idx+n].hex(),
            'replacement_hex':after[idx:idx+n].hex(),
            'purpose':description})
        idx+=n
    return result

def get_source(data:bytes):
    commands=read_commands(data)
    if len(commands)!=1:raise ValueError('Expected unique Bosnia GPU upload command')
    cmd=commands[0]
    if tuple(cmd[k] for k in ('upload_x','upload_y','width_words','height_rows'))!=GPU_REGION:
        raise ValueError('Unexpected GPU destination')
    if cmd['flags']!=0 or cmd['pointer']%4!=0:
        raise ValueError('Unexpected GPU command flags/pointer')
    offset=cmd['pointer']-BASELOAD
    if not 0<=offset<cmd['command_offset']:
        raise ValueError('GPU pointer does not resolve to encoded data before commands')
    if cmd['command_offset']+32>len(data):raise ValueError('No following GPU record')
    op,x,y,w,h,flags,next_ptr=struct.unpack_from('<6HI',data,cmd['command_offset']+16)
    if (op,x,y,w,h,flags)!=(10,832,384,32,128,0):
        raise ValueError('Next GPU record is not the expected neighboring tile')
    capacity=next_ptr-cmd['pointer']
    if not 0<capacity<=10000 or offset+capacity>len(data):
        raise ValueError('Unsafe/inconsistent compressed span')
    raw,used=decode(data[offset:offset+capacity],BLOCK_LEN)
    if not 1000<used<=capacity or used%2:
        raise ValueError('Unexpected original WE stream footprint')
    if any(data[offset+used:offset+capacity]):
        raise ValueError('Unexpected nonzero alignment gap after source')
    return offset,capacity,used,raw,cmd

def update_tile(raw:bytes,art:bytes):
    if len(raw)!=BLOCK_LEN or len(art)!=ART_NBYTES:raise ValueError('Bad VRAM tile lengths')
    modified=bytearray(raw)
    for row in range(28):
        # 32x128 VRAM words = 64 bytes/row; style10 x864, y320
        offset=(64+row)*64
        modified[offset:offset+32]=art[row*32:row*32+32]
    allowed={64*(64+r)+c for r in range(28) for c in range(32)}
    actually={i for i,(a,b) in enumerate(zip(raw,modified)) if a!=b}
    if not actually or not actually.issubset(allowed):raise ValueError('Unexpected pixel edits')
    if any(modified[64*(64+r):64*(64+r)+32]!=art[r*32:r*32+32] for r in range(28)):
        raise ValueError('Bosnia artwork not reproduced')
    return bytes(modified),len(actually)

def plan_file(name:str,lba:int,size:int,disc:PatchedDisc,art:bytes):
    source=disc.logical(lba,0,size,True)
    offset,capacity,used,raw,cmd=get_source(source)
    after,count=update_tile(raw,art)
    candidates=[encode(after)]
    candidates.append(optimize_literal_packets(candidates[0]))
    encoded=min(candidates,key=len)
    if len(encoded)>used:raise ValueError(f'{name} required {len(encoded)}, only {used} compressed bytes')
    again,consumed=decode(encoded,BLOCK_LEN)
    if again!=after or consumed!=len(encoded):raise ValueError('Codec roundtrip failure')
    old=source[offset:offset+used]
    new=encoded+bytes(used-len(encoded))
    if old==new:raise ValueError('No change')
    if any(source[offset+used:offset+capacity]):raise ValueError('Corrupt original pad')
    edits=split_guarded_edits(lba,offset,old,new,'Dedicated Bosnia style10 64x28 stadium flag '+name)
    for e in edits:
        # merge_verified requires Mode2 Form1 for all touched CD sectors
        sec=e['raw_offset']//2352
        actual=disc.sector(sec,True)
        if actual[15]!=2 or actual[18]&0x20 or actual[16:20]!=actual[20:24]:
            raise ValueError(f'{name}: edit targets unsupported CD sector type at LBA {sec}')
    report={'resource':name,'lba':lba,'file_size':size,'gpu_command_offset':cmd['command_offset'],
        'gpu_ptr':f"0x{cmd['pointer']:08X}",'verified_base':f'0x{BASELOAD:08X}',
        'compressed_source_offset':offset,'slot_capacity':capacity,
        'old_encoded_bytes':used,'new_encoded_bytes':len(encoded),'remaining_slack':capacity-len(encoded),
        'byte_changes_in_decoded_8KB':count,'old_decoded_sha256':hashlib.sha256(raw).hexdigest().upper(),
        'new_decoded_sha256':hashlib.sha256(after).hexdigest().upper(),'cd_sectors':sorted({e['raw_offset']//2352 for e in edits})}
    return edits,report

def build(track:Path,test06:Path,art_path:Path,inventory:Path,out:Path):
    out.mkdir(parents=True,exist_ok=True)
    if hashlib.sha256(test06.read_bytes()).hexdigest().upper()!=TEST06_SHA:raise ValueError('Wrong Test06 baseline')
    art=art_path.read_bytes()
    if len(art)!=ART_NBYTES or any((b&15) not in (1,2,3) or b>>4 not in (1,2,3) for b in art):
        raise ValueError('Wrong or corrupt Bosnia indexed art')
    contents=parse_inventory(inventory)
    if len(contents)!=34:raise ValueError(f'Expected all 34 stadiums, found {len(contents)}')
    disc=PatchedDisc(track,test06,verify=True)
    try:
        all_edits=[];rows=[]
        for name,(lba,size) in sorted(contents.items()):
            edits,record=plan_file(name,lba,size,disc,art)
            all_edits+=edits;rows.append(record)
        edited_lbas=sorted({e['raw_offset']//2352 for e in all_edits})
        if len(edited_lbas)<34:raise ValueError('Fewer than 34 sectors edited for 34 stadiums')
        jsonpath=out/'stage7_candidate_edits.json'
        jsonpath.write_text(json.dumps(all_edits,indent=2)+'\n')
        candidate=out/'ISS26_0.9.5_Stage7_GDC_Bosnia_TEST07_CANDIDATE.iss26p'
        meta=merge(track,test06,jsonpath,candidate,TEST06_IMAGE_SHA)
        check=PatchedDisc(track,candidate,verify=False)
        try:
            baseline_records=parse_patch(test06)
            new_records=parse_patch(candidate)
            if set(new_records)!=set(baseline_records):raise ValueError('Record count/ownership changed')
            for record in rows:
                name=record['resource'];lba=record['lba'];size=record['file_size']
                original=disc.logical(lba,0,size,True)
                patched=check.logical(lba,0,size,True)
                off,cap,used,raw,cmd=get_source(original)
                newoff,newcap,newused,after,newcmd=get_source(patched)
                expected,_=update_tile(raw,art)
                if after!=expected or off!=newoff or cap!=newcap or cmd!=newcmd:
                    raise ValueError(f'{name}: wrong or changed GPU upload')
                for i,(old,new) in enumerate(zip(original,patched)):
                    if not (off<=i<off+used) and old!=new:
                        raise ValueError(f'{name}: bytes outside guarded graphic stream differ: {i}')
            # All other sectors exactly identical to existing Test06.
            for lba in set(new_records)-set(edited_lbas):
                if new_records[lba]!=baseline_records[lba]:
                    raise ValueError(f'Unexpected change in non-GDC sector {lba}')
        finally:check.close()
        report={'stage':7,'status':'STATIC-VALIDATED CANDIDATE; EMULATOR VALIDATION STILL REQUIRED',
            'large_bosnia_style10':{'vram_words':[864,320],'pixels':[64,28]},
            'GDC_count':len(rows),'GDC_sources_verified':len(rows),
            'new_GDC_cd_sectors':len(edited_lbas),'modified_cd_sector_lbas':edited_lbas,
            'all_slot_ptrs_preserved':True,'all_neighboring_texels_preserved':True,
            'other_test06_patched_sectors_preserved':True,
            'art_sha256':hashlib.sha256(art).hexdigest().upper(),
            'patch':meta,'files':rows,
            'remaining':[
                '24x8 scoreboard flag source is not resolved.',
                'Prematch name Russia and other stale text identity not resolved.',
                'CLUT and render ownership require real PCSX-Redux visual/VRAM test.',
                'Game player stats/positions not yet remapped.'
            ]}
        (out/'stage7_report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    finally:disc.close()

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--track',type=Path,required=True);a.add_argument('--test06',type=Path,required=True)
    a.add_argument('--art',type=Path,default=ROOT/'stage6_bosnia_large_64x28.4bpp')
    a.add_argument('--inventory',type=Path,default=ROOT/'stage6_gdc_extent_eu.txt')
    a.add_argument('--out',type=Path,default=ROOT/'stage7_results')
    args=a.parse_args()
    print(json.dumps(build(args.track,args.test06,args.art,args.inventory,args.out),indent=2))
