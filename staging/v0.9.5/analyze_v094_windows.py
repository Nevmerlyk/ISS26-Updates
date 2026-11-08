#!/usr/bin/env python3
"""Produce narrow XOR-mask windows for independent local v0.9.4 graphics forensics.
No original game files are read, downloaded, or published.
"""
import argparse,hashlib,json,struct
from pathlib import Path
SECTOR=2352;RECORD=2388
EXPECTED='70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE'
WINDOWS=[('ENDING_names',430,0x620,0x260),('SELECT_names',850,0xd30,0x2b0),('DAT2D_palette',5300,58400,1728)]
PHYSICAL=[('OPENNING_slot_table',0x1D6F48,78),('SELECT_style_A',0x1E94CC,78),('SELECT_style_B',0x224C50,78),('SELFORM_style',0x4AD4B8,78),('REPLAYS_style',0x575864,78)]
def phys(lba,offset):return (lba+offset//2048)*SECTOR+24+offset%2048
def collect(raw):
 if raw[:8]!=b'ISS26X01':raise ValueError('bad patch magic')
 n=struct.unpack_from('<I',raw,8)[0]
 if len(raw)!=12+RECORD*n:raise ValueError('patch length mismatch')
 records={}
 for i in range(n):
  o=12+i*RECORD;k=struct.unpack_from('<I',raw,o)[0]
  if k in records:raise ValueError('duplicate sector')
  records[k]=raw[o+36:o+RECORD]
 def byte(p):return records.get(p//SECTOR,bytes(SECTOR))[p%SECTOR]
 windows=[]
 for key,lba,offset,length in WINDOWS:
  windows.append(dict(key=key,iso_lba=lba,resource_offset=offset,length=length,xor_hex=bytes(byte(phys(lba,offset+i)) for i in range(length)).hex()))
 for key,p,length in PHYSICAL:
  windows.append(dict(key=key,physical_offset=p,length=length,xor_hex=bytes(byte(p+i) for i in range(length)).hex()))
 return dict(patch_sha256=hashlib.sha256(raw).hexdigest().upper(),record_count=n,windows=windows,source='Public v0.9.4-preview XOR patch only, no copyrighted original data')
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('patch',type=Path);ap.add_argument('output',type=Path);a=ap.parse_args()
 raw=a.patch.read_bytes()
 if hashlib.sha256(raw).hexdigest().upper()!=EXPECTED:raise ValueError('unexpected patch checksum')
 a.output.write_text(json.dumps(collect(raw),indent=2)+'\n')
