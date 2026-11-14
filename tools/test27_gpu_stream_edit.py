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
from v095_name_lz_codec import decode_stream, encode_with_budget
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
    padding_field:int=0

def parse_uploads(blob:bytes,base:int,slot:int)->tuple[int,list[Upload]]:
    """Use the previously real-disc-validated upload-list format.

    The old Test27 parser required pad==0, exact 16-bit kinds and streams
    before the table. Those were name-atlas-specific assumptions, not
    established properties of DATSEL or stadium GDCs.
    """
    if not 0x80000000<=base<=0x801fffff or base%4:
        raise ValueError("Invalid PS1 RAM base")
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
        if ((kind&255) not in (0,9,10) or not 0<=w<=1024 or not 0<=h<=512
                or not 0<=start<len(blob)):
            raise ValueError("Unverified GPU upload descriptor")
        out.append(Upload(offset,kind,x,y,w,h,start,pad))
    raise ValueError("Unterminated GPU upload table")


def discover_upload_lists(blob:bytes,base_hint=None):
    """Enumerate roots before selecting the actual target rectangle writer.

    Known name/overlay bases first; hypotheses can be inferred from a
    structurally sound list and root pointer if those fail. An inferred
    base is accepted only by the caller after target decompression,
    list uniqueness and cross-resource guards. Never patch on guess alone.
    """
    bases=(0x800F0000,0x800C8000,0x800C0000,0x800D0000,0x800E0000,0x80100000)
    found={}
    def add(base,slot):
        try: table,rows=parse_uploads(blob,base,slot)
        except ValueError: return
        found.setdefault((base,table),(slot,rows))
    for base in ((base_hint,) if base_hint is not None else bases):
        for slot in range(0,32,4):
            if slot+4<=len(blob): add(base,slot)
    if not found and base_hint is None:
        # Bounded search for a real table terminator, then plausible list
        # roots. Accept only bases aligned to a 2 KiB PS1 loading boundary.
        for slot in range(0,min(32,len(blob)-3),4):
            ptr=struct.unpack_from("<I",blob,slot)[0]
            if not 0x80000000<=ptr<0x80200000: continue
            low=max(0x80000000,ptr-len(blob)+16)
            high=ptr-32
            for base in range((low+2047)&~2047,high+1,2048):
                add(base,slot)
    return found


def stream_span(blob,base,table,rows,u):
    """Only replace the actual original terminated stream, not all bytes
    before a following pointer. Other lists/data can share the allocation.
    """
    if (u.kind&255)!=10 or not 0<=u.x<1024 or not 0<=u.y<512 or not (
            1<=u.w<=1024-u.x and 1<=u.h<=512-u.y):
        raise ValueError("Unsupported target upload geometry/kind")
    starts={r.start for r in rows}
    barriers=starts|{table, len(blob)}
    # Protect every recognized root and descriptor region, plus payload
    # pointers from those lists. Refuse multiple distinct bases.
    for (other_base,other_table),(_,other_rows) in discover_upload_lists(blob,base).items():
        if other_base!=base:
            raise ValueError("Inconsistent GPU pointer bases")
        barriers.add(other_table)
        barriers.add(other_table+16*(len(other_rows)+1))
        barriers.update(r.start for r in other_rows)
        if other_table<=u.start<other_table+16*(len(other_rows)+1):
            raise ValueError("Stream overlaps descriptor table")
        aliases={r.offset for r in other_rows if r.start==u.start}
        if aliases-{u.offset}:
            raise ValueError("GPU stream aliased by another upload")
    # Protect header pointer targets even when an unrelated malformed
    # list was not recognized. They cannot be used as writable slack.
    for slot in range(0,min(32,len(blob)-3),4):
        ptr=struct.unpack_from("<I",blob,slot)[0]-base
        if 0<=ptr<len(blob):
            if ptr==u.start:
                raise ValueError("Target packet also referenced by resource header")
            barriers.add(ptr)
    if u.start<32:
        raise ValueError("Target packet overlaps resource header")
    stop=min(v for v in barriers if v>u.start)
    from v095_name_lz_codec import decode_stream_prefix
    decoded,used=decode_stream_prefix(blob[u.start:stop],expected_bytes=2*u.w*u.h,allow_short=True)
    # Use only the bytes consumed by the decoder; permit 0..3 alignment
    # zeros if no known data pointer starts there. Never clobber a gap.
    end=u.start+used
    aligned=min(stop,(end+3)&~3)
    if all(b==0 for b in blob[end:aligned]): end=aligned
    return decoded,end


def intersection(u:Upload,flag:str):
    x,y=TARGETS[flag]
    gx,gy=max(x,u.x),max(y,u.y)
    w,h=min(x+16,u.x+u.w)-gx,min(y+28,u.y+u.h)-gy
    return (gx,gy,w,h) if w>0 and h>0 else None


def fragment_read(decoded:bytes,u:Upload,box):
    x,y,w,h=box
    if not (u.x<=x and u.y<=y and w>0 and h>0 and
            x+w<=u.x+u.w and y+h<=u.y+u.h):
        raise ValueError("Fragment outside GPU upload")
    offsets=[2*((yy-u.y)*u.w+x-u.x) for yy in range(y,y+h)]
    if any(at+2*w>len(decoded) for at in offsets):
        raise ValueError(f"GPU fragment extends beyond actual decoded prefix ({len(decoded)} of {2*u.w*u.h} bytes); cannot assume missing pixels")
    return b"".join(decoded[at:at+2*w] for at in offsets)


def fragment_replace(decoded,u,box,art,flag):
    fragment_read(decoded,u,box)
    if len(art)!=896 or tuple(box)!=intersection(u,flag):
        raise ValueError("Unexpected national fragment")
    x,y,w,h=box
    tx,ty=TARGETS[flag]
    output=bytearray(decoded)
    for yy in range(y,y+h):
        start=2*((yy-u.y)*u.w+x-u.x)
        src=2*((yy-ty)*16+x-tx)
        output[start:start+2*w]=art[src:src+2*w]
    return bytes(output)


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
    if not routes or len(routes)>16:
        raise ValueError("Expected bounded national flag fragments")
    if len({(r["flag"],r["upload_offset"]) for r in routes})!=len(routes):
        raise ValueError("Duplicate flag fragment")
    output=bytearray(blob)
    changes=[]
    by_upload={}
    regions={}
    covered={flag:set() for flag in TARGETS}
    for r in routes:
        flag=r["flag"]
        if flag not in TARGETS:
            raise ValueError("Invalid national upload route")
        base,slot=r["gpu_base"],r["list_pointer_slot"]
        table,uploads=parse_uploads(blob,base,slot)
        i=r["upload_index"]
        if type(i) is not int or not 0<=i<len(uploads):
            raise ValueError("Invalid upload index")
        u=uploads[i]
        box=intersection(u,flag)
        if box is None or tuple(r["fragment"])!=box:
            raise ValueError("Unexpected fragment coordinates")
        x,y,w,h=box
        cells={(xx,yy) for yy in range(y,y+h) for xx in range(x,x+w)}
        if covered[flag]&cells:
            raise ValueError("Overlapping national fragments")
        covered[flag].update(cells)
        by_upload.setdefault((base,table,u),[]).append((flag,box,r["old_tile_sha256"],i,r["decoded_bytes"]))
        regions[(base,table,u)]=uploads
    if any(len(cells)!=448 for cells in covered.values()):
        raise ValueError("Incomplete national fragment coverage")
    protected=[]
    for key,targets in by_upload.items():
        base,table,u=key
        decoded,stop=stream_span(blob,base,table,regions[key],u)
        if any(u.start<b and a<stop for a,b in protected):
            raise ValueError("Overlapping source stream edits")
        protected.append((u.start,stop))
        expected=len(decoded)
        changed=decoded
        for flag,box,guard,i,decoded_bytes in targets:
            if len(decoded)!=decoded_bytes:
                raise ValueError("Decoded prefix changed")
            actual=fragment_read(decoded,u,box)
            if sha(actual)!=guard:
                raise ValueError("Actual pre-edit tile does not match reviewed source hash")
            art,colors=mapped_art(flag,live_clut)
            changed=fragment_replace(changed,u,box,art,flag)
            new_fragment=fragment_read(changed,u,box)
            changes.append({"flag":flag,"upload_index":i,"upload_offset":u.offset,
                "old_tile_sha256":sha(actual),"new_tile_sha256":sha(new_fragment),
                "vram_words":list(box),"decoded_bytes":expected,"gpu_rect_bytes":2*u.w*u.h,"palette_mapping":colors})
        capacity=stop-u.start
        packed,method=encode_with_budget(changed,expected_bytes=expected,capacity=capacity)
        for item in changes:
            if item["upload_offset"]==u.offset:
                item.update({"compression_method":method,"stream_capacity_bytes":capacity,
                             "new_packed_bytes":len(packed)})
        output[u.start:stop]=packed+bytes(capacity-len(packed))
        verified=decode_stream(bytes(output[u.start:stop]),expected_bytes=expected,max_padding=capacity)
        if verified!=changed:
            raise AssertionError("Rewritten GPU stream does not round-trip")
    # Compare all descriptor fields (including unknown pad/flag bits).
    bases={key[0] for key in by_upload}
    if len(bases)!=1 or any(discover_upload_lists(bytes(output),b)!=discover_upload_lists(blob,b) for b in bases) or len(output)!=len(blob):
        raise AssertionError("GPU descriptor list or resource allocation changed")
    cursor=0
    for a,b in sorted(protected):
        if output[cursor:a]!=blob[cursor:a]:
            raise AssertionError("Unexpected bytes outside authorized stream")
        cursor=b
    if output[cursor:]!=blob[cursor:]:
        raise AssertionError("Unexpected bytes after authorized stream")
    return bytes(output),changes
