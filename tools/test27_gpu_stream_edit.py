#!/usr/bin/env python3
"""Compile a guarded national-only 4bpp atlas edit within an existing GPU LZ stream.

The actual local resource and the reviewed upload descriptor must be supplied.
Never relocate compressed streams, change GPU upload dimensions, or edit any
non-target decoded pixels. Never modify a shared CLUT. If the existing palette
cannot represent the national flag within the given tolerance, refuse to build.
"""
from __future__ import annotations
import hashlib
import math
import struct
from dataclasses import dataclass
from v095_name_lz_codec import decode_stream, encode_stream
from test27_flag_art_4bpp import candidate, COLORS, pack_4bpp, bgr555

TARGETS={"cape_verde":(848,256),"bosnia":(816,368)}
CLUT_SHA="DA3484BF49560D2CD1306FE3CCC59B5417A54AA370859DDB6C77EAE523361B88"
def sha(raw): return hashlib.sha256(raw).hexdigest().upper()

@dataclass(frozen=True)
class Upload:
    offset:int
    kind:int
    x:int
    y:int
    w:int
    h:int
    start:int

def parse_uploads(blob:bytes,base:int,slot:int)->tuple[int,list[Upload]]:
    if base not in (0x800F0000,0x800C8000):
        raise ValueError("Unverified resource RAM base")
    if slot not in range(0,32,4) or slot+4>len(blob):
        raise ValueError("Unexpected pointer slot")
    table=struct.unpack_from("<I",blob,slot)[0]-base
    if not 32<=table<=len(blob)-16 or table%4:
        raise ValueError("Upload table pointer not within resource")
    out=[]
    for i in range(512):
        offset=table+i*16
        if offset+16>len(blob):
            break
        kind,x,y,w,h,pad,p=struct.unpack_from("<HHHHHHI",blob,offset)
        if kind==255:
            if not out: raise ValueError("Empty upload table")
            return table,out
        start=p-base
        if (kind not in (0,9,10) or pad!=0 or not 0<=x<1024 or not 0<=y<512
            or not 1<=w<=1024-x or not 1<=h<=512-y
            or not 4<=start<table):
            raise ValueError("Unverified GPU upload descriptor")
        out.append(Upload(offset,kind,x,y,w,h,start))
    raise ValueError("Unterminated GPU upload table")

def _box(upload:Upload,flag:str):
    x,y=TARGETS[flag]
    if not(upload.x<=x and x+16<=upload.x+upload.w and
           upload.y<=y and y+28<=upload.y+upload.h):
        raise ValueError("Upload does not wholly cover target 64x28 tile")
    return x-upload.x,y-upload.y

def take_tile(decoded:bytes,u:Upload,x:int,y:int)->bytes:
    if len(decoded)!=2*u.w*u.h or not(0<=x<=u.w-16 and 0<=y<=u.h-28):
        raise ValueError("Wrong decoded rectangle geometry")
    return b"".join(decoded[2*((y+i)*u.w+x):2*((y+i)*u.w+x+16)] for i in range(28))

def change_tile(decoded:bytes,u:Upload,x:int,y:int,replacement:bytes)->bytes:
    take_tile(decoded,u,x,y)
    if len(replacement)!=896:
        raise ValueError("Expected 64x28 4bpp")
    output=bytearray(decoded)
    for i in range(28):
        at=2*((y+i)*u.w+x)
        output[at:at+32]=replacement[i*32:(i+1)*32]
    # Confirm every byte outside the requested subrect remains identical.
    for i in range(u.h):
        start=2*i*u.w
        if y<=i<y+28:
            if (output[start:start+2*x]!=decoded[start:start+2*x] or
                output[start+2*(x+16):start+2*u.w]!=decoded[start+2*(x+16):start+2*u.w]):
                raise AssertionError("Unexpected adjacent texture mutation")
        elif output[start:start+2*u.w]!=decoded[start:start+2*u.w]:
            raise AssertionError("Unexpected row mutation")
    return bytes(output)

def mapped_art(flag:str,live_clut:bytes,max_channel_error:int=5)->tuple[bytes,dict]:
    """Only use existing nonzero-color palette entries; never change the CLUT."""
    if len(live_clut)!=32 or not 0<=max_channel_error<=5:
        raise ValueError("Expected sampled 16-color CLUT and conservative color tolerance")
    values=struct.unpack("<16H",live_clut)
    def rgb5(n): return (n&31,(n>>5)&31,(n>>10)&31)
    _,_,pixels,_=candidate(flag)
    # A greedy nearest-entry choice can reject a feasible palette if two
    # intended colors prefer the same entry. Find a minimum-error injective
    # assignment over the actual available opaque colors instead.
    wanted=sorted(set(pixels))
    candidates={}
    for i in wanted:
        intended=rgb5(bgr555(COLORS[flag][i]))
        choices=[]
        for j in range(1,16):
            v=values[j]
            if not v or v&0x8000:
                continue
            actual=rgb5(v)
            d=tuple(abs(a-b) for a,b in zip(actual,intended))
            error=max(d)
            if error<=max_channel_error:
                choices.append((sum(x*x for x in d),error,j))
        candidates[i]=sorted(choices)
        if not choices:
            if not any(v and not v&0x8000 for v in values[1:]):
                raise ValueError("No safe opaque nonzero CLUT entries")
            raise ValueError(f"{flag}: existing CLUT cannot safely represent color {i}; explicit palette allocation required")
    order=sorted(wanted,key=lambda i:(len(candidates[i]),i))
    best=None
    def assign(depth,used,score,peak,indices,errors):
        nonlocal best
        if best is not None and score>best[0][0]:
            return
        if depth==len(order):
            rank=(score,peak,tuple(indices[i] for i in wanted))
            if best is None or rank<best[0]:
                best=(rank,dict(indices),dict(errors))
            return
        i=order[depth]
        for distance,error,j in candidates[i]:
            # Distinct slots alone are not enough: several CLUT entries
            # can encode the SAME color. Require distinct BGR555 values.
            v=values[j]
            if v in used:
                continue
            indices[i]=j
            errors[i]=error
            assign(depth+1,used|{v},score+distance,max(peak,error),indices,errors)
            del indices[i],errors[i]
    assign(0,set(),0,0,{}, {})
    if best is None:
        raise ValueError("Existing CLUT merges distinct flag colors")
    _,indices,errors=best
    return pack_4bpp([indices[i] for i in pixels]),{"index_map":indices,"max_channel_error_5bit":errors}

def rewrite_resource(blob:bytes,routes:list[dict],live_clut:bytes,*,require_clut_sha=True)->tuple[bytes,list[dict]]:
    if require_clut_sha and sha(live_clut)!=CLUT_SHA:
        raise ValueError("CLUT does not match captured owner Test27 palette")
    if not routes or len(routes)>2:
        raise ValueError("Expected one or two approved flag targets per resource")
    if len({r["flag"] for r in routes})!=len(routes):
        raise ValueError("Duplicate flag route")
    # One complete, reviewed descriptor list per resource. Do not guess which
    # of multiple independent lists owns a stream.
    base=routes[0]["gpu_base"]
    slot=routes[0]["list_pointer_slot"]
    if any(r["gpu_base"]!=base or r["list_pointer_slot"]!=slot for r in routes):
        raise ValueError("Multiple list roots require independent resource attribution")
    table,uploads=parse_uploads(blob,base,slot)
    for other_slot in range(0,32,4):
        if other_slot==slot or other_slot+4>len(blob): continue
        try:
            other_table,other_uploads=parse_uploads(blob,base,other_slot)
        except ValueError:
            continue
        if other_table!=table:
            raise ValueError("Additional GPU list may alias edited stream")
    starts=sorted(set(u.start for u in uploads))
    output=bytearray(blob)
    changes=[]
    by_upload={}
    for r in routes:
        flag=r["flag"]
        if flag not in TARGETS or type(r["upload_index"]) is not int or not 0<=r["upload_index"]<len(uploads):
            raise ValueError("Invalid national upload route")
        u=uploads[r["upload_index"]]
        if u.kind!=10 or sum(v.start==u.start for v in uploads)!=1:
            raise ValueError("Only exclusive compressed kind-10 streams can be rewritten")
        x,y=_box(u,flag)
        by_upload.setdefault(u,[]).append((flag,x,y,r["old_tile_sha256"]))
    for u,targets in by_upload.items():
        stop=next((s for s in starts if s>u.start),table)
        original=blob[u.start:stop]
        if not original or len(original)>1024*1024:
            raise ValueError("Invalid bounded stream allocation")
        expected=u.w*u.h*2
        decoded=decode_stream(original,expected_bytes=expected,max_padding=len(original))
        changed=decoded
        for flag,x,y,guard in targets:
            actual=take_tile(decoded,u,x,y)
            if sha(actual)!=guard:
                raise ValueError("Actual pre-edit tile does not match reviewed source hash")
            art,colors=mapped_art(flag,live_clut)
            changed=change_tile(changed,u,x,y,art)
            changes.append({"flag":flag,"upload_index":uploads.index(u),
                "old_tile_sha256":sha(actual),"new_tile_sha256":sha(art),
                "vram_words":[*TARGETS[flag],16,28],"palette_mapping":colors})
        packed=encode_stream(changed,expected_bytes=expected)
        if len(packed)>len(original):
            raise ValueError("Flag insertion exceeds existing GPU stream capacity; no relocation")
        output[u.start:stop]=packed+bytes(len(original)-len(packed))
        verified=decode_stream(bytes(output[u.start:stop]),expected_bytes=expected,max_padding=len(original))
        if verified!=changed:
            raise AssertionError("Rewritten GPU stream does not round-trip")
    if output[table:]!=blob[table:] or len(output)!=len(blob):
        raise AssertionError("GPU command table or resource allocation changed")
    if parse_uploads(bytes(output),base,slot)!=(table,uploads):
        raise AssertionError("GPU descriptor geometry changed")
    return bytes(output),changes
