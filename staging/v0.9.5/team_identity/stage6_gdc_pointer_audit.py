#!/usr/bin/env python3
"""ISS26 Stage 6: read-only 34-stadium GDC Bosnia GPU-source preflight.

The 16-byte GPU records contain RAM pointers, not verified file offsets.
Probe all page-aligned MIPS load-base candidates before any texture edit.
Never modify the disc, GDC files, game patch, or update feeds.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,re,struct
from collections import Counter
from pathlib import Path
from team_identity_audit import PatchedDisc
from wecodec_stage5 import DecodeError,decode

# These targets are known from the 28 large-national-style atlas map.
BOSNIA_RECT=(864,320,16,28)
SCENE_UPLOAD=(864,256,32,128)
BASE_CHOICES=tuple(range(0x800A0000,0x80110000,0x10000))


def parse_inventory(path:Path):
    out={}
    for line in path.read_text(encoding='utf-8').splitlines():
        m=re.match(r'^\s*(\d+)\s+(\d+)\s+(/BIN/GDC_[A-Z0-9]+\.BIN;1)\s*$',line)
        if m:out[m[3]]=(int(m[1]),int(m[2]))
    return out


def read_commands(blob:bytes,target=BOSNIA_RECT):
    tx,ty,tw,th=target
    found=[]
    for pos in range(0,len(blob)-16+1,4):
        op,x,y,w,h,flags,ptr=struct.unpack_from('<6HI',blob,pos)
        if op!=10 or not (0<w<=1024 and 0<h<=512) or x+w>1024 or y+h>512:continue
        if (x<tx+tw and tx<x+w and y<ty+th and ty<y+h):
            found.append({'command_offset':pos,'upload_x':x,'upload_y':y,'width_words':w,
                          'height_rows':h,'flags':flags,'pointer':ptr})
    return found


def probe_ptr(blob:bytes,cmd:dict):
    """Only classify *verified* WE payload offsets; never guess one."""
    p=cmd['pointer'];target_size=2*cmd['width_words']*cmd['height_rows'];found=[];tested=0
    for base in BASE_CHOICES:
        offset=p-base
        if not (0<=offset<cmd['command_offset']):continue
        tested+=1
        try:raw,used=decode(blob[offset:cmd['command_offset']],target_size)
        except (ValueError,IndexError,DecodeError):continue
        if used and offset+used<=cmd['command_offset']:
            found.append({'load_base':f'0x{base:08X}','file_offset':offset,
                          'compressed_bytes':used,'raw_sha256':hashlib.sha256(raw).hexdigest().upper()})
    return found,tested


def audit(track:Path,patch:Path,inventory:Path,out:Path,verify=True,baseline:Path|None=None):
    entries=parse_inventory(inventory)
    if len(entries)!=34:raise ValueError(f'Expected 34 stadium GDC resources, found {len(entries)}')
    disc=PatchedDisc(track,patch,verify=verify)
    ref=PatchedDisc(track,baseline,verify=False) if baseline else None
    records=[];variants={}
    try:
        for path,(lba,size) in sorted(entries.items()):
            gdc=disc.logical(lba,0,size,True)
            candidates=read_commands(gdc)
            if len(candidates)!=1:raise ValueError(f'{path}: expected exactly one Bosnia-containing GPU command, got {len(candidates)}')
            cmd=candidates[0]
            matches,tests=probe_ptr(gdc,cmd)
            if (cmd['upload_x'],cmd['upload_y'],cmd['width_words'],cmd['height_rows'])!=SCENE_UPLOAD:
                raise ValueError(f'{path}: changed VRAM upload rectangle: {cmd}')
            nsec=(size+2047)//2048
            changed_from_original=[];changed_from_baseline=[]
            for i in range(lba,lba+nsec):
                patched_sec=disc.sector(i,True)
                if patched_sec!=disc.sector(i,False):changed_from_original.append(i)
                if ref is not None and patched_sec!=ref.sector(i,True):changed_from_baseline.append(i)
            orig=disc.logical(lba,0,size,False)
            v094=ref.logical(lba,0,size,True) if ref else None
            row={'resource':path,'lba':lba,'size':size,'sector_count':nsec,
                 'gpu_command_file_offset':cmd['command_offset'],
                 'gpu_ptr':f"0x{cmd['pointer']:08X}",
                 'gpu_ptr_if_base_800C_in_file':0<=cmd['pointer']-0x800C0000<size,
                 'verified_WE_streams':len(matches),'candidate_load_bases_tested':tests,
                 'changed_bytes_from_clean':sum(x!=y for x,y in zip(orig,gdc)),
                 'changed_bytes_from_v094':sum(x!=y for x,y in zip(v094,gdc)) if v094 is not None else None,
                 'changed_sectors_from_clean':len(changed_from_original),
                 'changed_sectors_from_v094':len(changed_from_baseline) if ref else None, 'gdc_sha256':hashlib.sha256(gdc).hexdigest().upper()}
            records.append(row);variants.setdefault(row['gdc_sha256'],[]).append(path)
    finally:
        disc.close()
        if ref:ref.close()
    output={
      'stage':6,'status':'READ ONLY: GDC dynamic upload origin not yet proved',
      'track_sha256':'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44' if verify else 'not calculated',
      'test06_patch_sha256':hashlib.sha256(patch.read_bytes()).hexdigest().upper(),
      'stadium_GDC_files':len(records),
      'bosnia_gpu_uploads_found':len(records),
      'GPU_upload_destination':{'x_words':864,'y':256,'width_words':32,'height_rows':128},
      'large_bosnia_style10_region':{'x_words':864,'y':320,'width_words':16,'height_rows':28},
      'verified_WE_source_lookups':sum(r['verified_WE_streams'] for r in records),
      'GDC_resources_different_from_clean_original':sum(bool(r['changed_sectors_from_clean']) for r in records),
      'sum_changed_GDC_bytes_from_original':sum(r['changed_bytes_from_clean'] for r in records),
      'GDC_resources_different_from_v094':sum(bool(r['changed_sectors_from_v094']) for r in records) if baseline else None,
      'pointers_outside_file_if_base_800C':sum(not r['gpu_ptr_if_base_800C_in_file'] for r in records),
      'unique_GDC_binary_contents':len(variants),
      'identical_GDC_resource_groups':[v for v in variants.values() if len(v)>1],
      'warning':'GDC command pointer may refer to runtime-expanded RAM source; no verified compressed offset in current scan. Do not overwrite source based on pointer subtraction alone. Runtime capture/disassembly of GPU load required.',
      'records':records
    }
    out.mkdir(parents=True,exist_ok=True)
    (out/'stage6_gdc_report.json').write_text(json.dumps(output,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (out/'stage6_gdc_rows.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--track',type=Path,required=True)
    p.add_argument('--patch',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--baseline',type=Path,help='official standalone v0.9.4 patch')
    p.add_argument('--out',type=Path,default=Path('stage6_results'))
    p.add_argument('--skip-hash',action='store_true')
    args=p.parse_args()
    d=audit(args.track,args.patch,args.inventory,args.out,not args.skip_hash,args.baseline)
    print(json.dumps({k:v for k,v in d.items() if k!='records'},ensure_ascii=False,indent=2))
