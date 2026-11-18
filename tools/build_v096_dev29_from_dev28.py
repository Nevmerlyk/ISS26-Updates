#!/usr/bin/env python3
"""Build exact independent DEV29 ISS26X01 from public verified DEV28 patch.

No original game disk data, music, BIOS, or copyrighted texture sources are included.
This file only applies approved, SHA-pinned sector patch record overrides.
"""
import argparse,base64,hashlib,lzma,struct
from pathlib import Path
DEV28_SHA='4A1C2293F6A91A77DBD6CBECC96B0E02A98C63444C309202402F094AC5F312B6'
DEV29_SHA='0049C38CED7620129B1A29D928B4D9E617EF5FD8300A74D9FFEEBB42BBE0C62D'
OVERRIDE_SHA='E589C2AD3B0CE79D21CA8474FDED1C09E24A167D9100C80C4103CE66A4F15495'
MAGIC=b'ISS26X01'; RECORD=2388; N=699;COUNT=4

def sha(b):return hashlib.sha256(b).hexdigest().upper()

def parse(data):
 if data[:8]!=MAGIC or struct.unpack_from('<I',data,8)[0]!=N or len(data)!=12+N*RECORD:raise ValueError('invalid patch format')
 lines=[data[12+i*RECORD:12+(i+1)*RECORD] for i in range(N)]
 ids=[struct.unpack_from('<I',r,0)[0] for r in lines]
 if ids!=sorted(set(ids)):raise ValueError('out-of-order or duplicate records')
 return ids,lines

def main(base,overrides,out):
 buf=base.read_bytes()
 if sha(buf)!=DEV28_SHA:raise ValueError('wrong published DEV28 baseline')
 ids,lines=parse(buf)
 raw=lzma.decompress(base64.b64decode(overrides.read_bytes()))
 if OVERRIDE_SHA and sha(raw)!=OVERRIDE_SHA:raise ValueError('wrong override digest')
 if raw[:8]!=b'ISS26OV1' or len(raw)!=12+COUNT*RECORD or struct.unpack_from('<I',raw,8)[0]!=COUNT:raise ValueError('invalid overrides')
 records={struct.unpack_from('<I',raw,12+i*RECORD)[0]:raw[12+i*RECORD:12+(i+1)*RECORD] for i in range(COUNT)}
 if set(records)!={853,854,938,939}:raise ValueError('not the six approved country-link sectors')
 lookup=dict(zip(ids,lines))
 for lba,rec in records.items():
  if lba not in lookup:raise ValueError('sector absent from DEV28 '+str(lba))
  if rec[:36]!=lookup[lba][:36]:raise ValueError('source-sector guard changed')
  lookup[lba]=rec
 dst=MAGIC+struct.pack('<I',N)+b''.join(lookup[i] for i in ids)
 if sha(dst)!=DEV29_SHA:raise ValueError('DEV29 byte-exact patch hash mismatch')
 if out.exists():raise FileExistsError(out)
 out.parent.mkdir(parents=True,exist_ok=True)
 out.write_bytes(dst)
 if sha(out.read_bytes())!=DEV29_SHA:raise ValueError('postwrite mismatch')
 print('VERIFIED independent standalone DEV29 patch:',DEV29_SHA)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--baseline',required=True,type=Path);p.add_argument('--overrides',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
 a=p.parse_args();main(a.baseline,a.overrides,a.output)