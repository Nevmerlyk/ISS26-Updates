"""Validate and decode ISS Pro Evolution 2 primary DATSEL.BIN texture upload list.

Read-only in the absence of exact team->atlas slot mappings.
"""
from __future__ import annotations
from dataclasses import dataclass
from struct import unpack_from
from wecodec import decode,encode
BASE=0x800F0000
@dataclass(frozen=True)
class Upload:
    index:int
    record_offset:int
    offset:int
    end:int
    vram_x:int
    vram_y:int
    width_words:int
    height:int
    decoded:bytes

def parse_primary(data:bytes)->list[Upload]:
    if len(data)<40:raise ValueError('truncated DATSEL')
    table=unpack_from('<I',data,0)[0]-BASE
    if not 16<=table<len(data)-16 or table%4:raise ValueError('bad pointer')
    entries=[]
    for idx in range(256):
        pos=table+idx*16
        if pos+16>len(data):raise ValueError('unterminated table')
        op,x,y,w,h,flags,ptr=unpack_from('<6HI',data,pos)
        if op==255:
            if idx!=55 or any(data[pos+2:pos+16]):raise ValueError('unexpected table terminator')
            return entries
        if op!=10 or not(0<w<=256 and 0<h<=512 and 0<=x<1024 and 0<=y<512):
            raise ValueError(f'bad GPU upload command {idx}')
        offset=ptr-BASE
        if not 16<=offset<table:raise ValueError('bad payload pointer')
        expected=w*2*h
        decoded,used,_=decode(data[offset:table],expected)
        if used<=0 or offset+used>table:raise ValueError('invalid source span')
        entries.append(Upload(idx,pos,offset,offset+used,x,y,w,h,decoded))
    raise ValueError('upload count exceeds limit')

def save_index_image(entries:list[Upload],destination:str)->None:
    from PIL import Image
    canvas=Image.new('P',(1024*4,512),0)
    for e in entries:
        indices=bytearray()
        for b in e.decoded:indices.extend((b&15,b>>4))
        im=Image.frombytes('P',(4*e.width_words,e.height),bytes(indices))
        canvas.paste(im,(4*e.vram_x,e.vram_y))
    pal=[v for i in range(16) for v in (i*17,)*3]
    canvas.putpalette(pal+[0]*(768-len(pal)))
    canvas.crop((384*4,0,1024*4,512)).save(destination)