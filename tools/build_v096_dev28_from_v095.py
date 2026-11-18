#!/usr/bin/env python3
"""Reconstitute exact standalone DEV28 ISS26X01 using the published v0.9.5 carrier.

No original game image, audio, BIOS, or extracted game files are read or distributed.
Overrides are fully pinned release records, not a delta requiring a prior game install.
"""
import argparse
import base64
import hashlib
import lzma
import struct
from pathlib import Path

RECORD_SIZE = 2388
MAGIC = b'ISS26X01'
BASE_SHA = '4914C36BFAC27AFF4C4FB60BBD7AB49867FC1E67F26CE733686E73C79C839148'
TARGET_SHA = '4A1C2293F6A91A77DBD6CBECC96B0E02A98C63444C309202402F094AC5F312B6'
OVERRIDE_SHA = '6008DE7A1810537E8479D7F3B526AC3D522883A006413F8DCA8010C146C0AC82'
TARGET_LBAS = [167,168,169,170,171,172,173,852,853,854,930,931,932,933,934,935,936,937,938,939]


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def read_records(data):
    if data[:8] != MAGIC or len(data)<12:
        raise ValueError('Invalid ISS26X01 patch')
    (count,) = struct.unpack_from('<I',data,8)
    if not 0<count<8192 or len(data) != 12+count*RECORD_SIZE:
        raise ValueError('Invalid count or patch size')
    result = {}
    for i in range(count):
        record = data[12+i*RECORD_SIZE:12+(i+1)*RECORD_SIZE]
        (lba,) = struct.unpack_from('<I',record)
        if lba in result:
            raise ValueError(f'Duplicate sector {lba}')
        result[lba]=record
    if list(result) != sorted(result):
        raise ValueError('Unsorted sector records')
    return result


def build(base, overrides, output):
    data=base.read_bytes()
    if sha(data)!=BASE_SHA:
        raise ValueError('Wrong published stable 0.9.5 patch SHA256')
    records=read_records(data)
    if len(records)!=689:
        raise ValueError('Unexpected stable 0.9.5 sector count')
    packed=base64.b64decode(''.join(overrides.read_text(encoding='ascii').split()), validate=True)
    extra=lzma.decompress(packed)
    if sha(extra)!=OVERRIDE_SHA or len(extra)!=len(TARGET_LBAS)*RECORD_SIZE:
        raise ValueError('Override resource digest/size mismatch')
    changes=read_records(MAGIC+struct.pack('<I',len(TARGET_LBAS))+extra)
    if sorted(changes)!=TARGET_LBAS:
        raise ValueError('Unexpected overridden sectors')
    for lba,record in changes.items():
        if lba in records and record[4:36]!=records[lba][4:36]:
            raise ValueError(f'Original sector SHA guard changed: {lba}')
        records[lba]=record
    if len(records)!=699:
        raise ValueError('Incorrect final count')
    result=MAGIC+struct.pack('<I',len(records))+b''.join(records[k] for k in sorted(records))
    if sha(result)!=TARGET_SHA:
        raise ValueError('Built patch checksum does not match exact DEV28')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(result)
    if sha(output.read_bytes())!=TARGET_SHA:
        raise ValueError('Post-write checksum mismatch')
    print(f'Verified exact DEV28 standalone patch ({len(records)} sectors, {len(result)} bytes): {TARGET_SHA}')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--base',type=Path,required=True)
    p.add_argument('--overrides',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    build(args.base,args.overrides,args.output)