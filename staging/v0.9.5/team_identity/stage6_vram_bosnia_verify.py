#!/usr/bin/env python3
"""Read-only comparison of Bosnia's dedicated 4bpp flag tile with PCSX-Redux VRAM.

Use only VRAM captured from the SAME Test06 game build; old captures are
appropriate for parser tests only, never proof that Test06 renders correctly.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,zipfile
from pathlib import Path

WIDTH_WORDS=1024
HEIGHT_LINES=512
VRAM_BYTE_COUNT=WIDTH_WORDS*HEIGHT_LINES*2
FULL_PCSX_CAPTURE_BYTES=VRAM_BYTE_COUNT*2
STYLE_X=864
STYLE_Y=320
STYLE_WIDTH_WORDS=16
STYLE_HEIGHT=28


def extract_tile(vram:bytes,x_words=STYLE_X,y=STYLE_Y,w_words=STYLE_WIDTH_WORDS,h=STYLE_HEIGHT)->bytes:
    if len(vram) not in (VRAM_BYTE_COUNT,FULL_PCSX_CAPTURE_BYTES):
        raise ValueError(f'Expected {VRAM_BYTE_COUNT} raw VRAM bytes or {FULL_PCSX_CAPTURE_BYTES} PCSX capture bytes, got {len(vram)}')
    vram=vram[:VRAM_BYTE_COUNT]
    if not(0<=x_words<WIDTH_WORDS and 0<=y<HEIGHT_LINES and 1<=w_words<=WIDTH_WORDS-x_words and 1<=h<=HEIGHT_LINES-y):
        raise ValueError('VRAM tile out of bounds')
    return b''.join(vram[((y+j)*WIDTH_WORDS+x_words)*2:((y+j)*WIDTH_WORDS+x_words+w_words)*2] for j in range(h))


def compare(vram:bytes,art:bytes)->dict:
    actual=extract_tile(vram)
    if len(art)!=len(actual):raise ValueError('Expected 64x28 4bpp flag (896 bytes)')
    return {'same_pixel_data':actual==art,
            'matching_bytes':sum(a==b for a,b in zip(actual,art)),
            'total_bytes':len(art),
            'actual_sha256':hashlib.sha256(actual).hexdigest().upper(),
            'expected_sha256':hashlib.sha256(art).hexdigest().upper(),
            'nonzero_current_bytes':sum(b!=0 for b in actual),
            'note':'VRAM comparison measures atlas tile bytes, not which CLUT or sprite the UI actually draws'}


def load_reference_art(path:Path)->bytes:
    if path.exists():return path.read_bytes()
    fallback=Path(__file__).parent/'stage4_results/bosnia_style10_art/assets_4bpp_base64.json'
    if not fallback.exists():raise FileNotFoundError('Bosnia 4bpp data missing: run build_bosnia_style10_assets.py or supply --art')
    src=json.loads(fallback.read_text(encoding='utf-8'))['large_64x28']
    raw=base64.b64decode(src['base64'],validate=True)
    if hashlib.sha256(raw).hexdigest().upper()!=src['sha256'].upper():
        raise ValueError('Bundled Bosnia reference art hash mismatch')
    return raw


def load_vram(path:Path,member:str|None=None)->bytes:
    if path.suffix.lower()=='.zip':
        with zipfile.ZipFile(path) as z:
            if member is None:raise ValueError('When using a ZIP specify --member with its exact .vram filename')
            data=z.read(member)
    else:
        if member:raise ValueError('--member only for a ZIP')
        data=path.read_bytes()
    if len(data) not in (VRAM_BYTE_COUNT,FULL_PCSX_CAPTURE_BYTES):
        raise ValueError('Expected 1,048,576-byte raw VRAM or 2,097,152-byte PCSX-Redux capture')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vram',type=Path,required=True)
    p.add_argument('--member',help='exact zip member filename for a PCSX-Redux .vram dump')
    p.add_argument('--art',type=Path,default=Path(__file__).parent/'stage6_bosnia_large_64x28.4bpp')
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    report=compare(load_vram(a.vram,a.member),load_reference_art(a.art))
    report['input_vram']=str(a.vram);report['member']=a.member
    output=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if a.output:a.output.write_text(output,encoding='utf-8')
    print(output)
