#!/usr/bin/env python3
"""ISS26 EU national-name GPU LZ codec and memory-only atlas repacker.

Reconstructed from SLES_033.21 MIPS at 0x8001CE34. No original game data
is distributed, and this module does not modify BIN/CUE files.
"""
from __future__ import annotations
from bisect import bisect_left
from collections import defaultdict
import struct

RESOURCE_BYTES = 56256
TABLE_OFFSET = 55824
GPU_BASE = 0x800F0000
UPLOADS = 26
TILE_BYTES = 8192


class FormatError(ValueError):
    pass


def decode_stream_prefix(data: bytes, *, expected_bytes: int = TILE_BYTES,
                         allow_short: bool = False) -> tuple[bytes,int]:
    """LSB-first flags, single-byte literals and three MIPS command families."""
    src = 0
    flags = 0
    out = bytearray()
    while True:
        flags >>= 1
        if not (flags & 0x100):
            if src >= len(data):
                raise FormatError("truncated flag byte")
            flags = 0xFF00 | data[src]
            src += 1
        if src >= len(data):
            raise FormatError("missing token")
        token = data[src]
        if not (flags & 1):
            out.append(token)
            src += 1
        elif token < 0x80:
            if src + 1 >= len(data):
                raise FormatError("truncated long backreference")
            count = (token >> 2) + 3
            distance = ((token & 3) << 8) | data[src + 1]
            src += 2
            if not 1 <= distance <= len(out):
                raise FormatError("invalid long backreference")
            for _ in range(count):
                out.append(out[-distance])
        elif token < 0xC0:
            count = (token >> 4) - 6
            distance = (token & 15) + 1
            src += 1
            if not 1 <= distance <= len(out):
                raise FormatError("invalid short backreference")
            for _ in range(count):
                out.append(out[-distance])
        elif token == 0xFF:
            src += 1
            break
        else:
            count = token - 0xB8
            src += 1
            if src + count > len(data):
                raise FormatError("truncated raw block")
            out.extend(data[src:src + count])
            src += count
        if len(out) > expected_bytes:
            raise FormatError("GPU rectangle overrun")
    if len(out) != expected_bytes and not (allow_short and 0<len(out)<expected_bytes):
        raise FormatError(f"wrong output length: {len(out)}")
    return bytes(out),src


def decode_stream(data: bytes, *, expected_bytes: int = TILE_BYTES,
                  max_padding: int = 3) -> bytes:
    out,src=decode_stream_prefix(data,expected_bytes=expected_bytes)
    if max_padding < 0 or len(data) - src > max_padding or any(data[src:]):
        raise FormatError("unexpected trailing bytes")
    return out


def _pack_tokens(tokens: list[tuple[int, bytes]]) -> bytes:
    tokens.append((1, bytes([255])))
    out = bytearray()
    for i in range(0, len(tokens), 8):
        group = tokens[i:i + 8]
        out.append(sum((bit & 1) << n for n, (bit, _) in enumerate(group)))
        for _, chunk in group:
            out.extend(chunk)
    return bytes(out)


def encode_stream(pixels: bytes, *, candidate_limit: int = 64,
                  expected_bytes: int = TILE_BYTES) -> bytes:
    """Greedy encoder; default remains the verified 8192-byte name tile.

    Flag resources can use other bounded GPU rectangle sizes. Every encoded
    result is checked against the original decoder at that exact size.
    """
    if not 1 <= expected_bytes <= 1024*512*2 or len(pixels) != expected_bytes:
        raise FormatError("unexpected or unsafe decoded rectangle size")
    if candidate_limit < 1:
        raise ValueError("candidate_limit must be >=1")
    pos_by_triple = defaultdict(list)
    for i in range(len(pixels) - 2):
        pos_by_triple[pixels[i:i + 3]].append(i)
    tokens = []
    i = 0
    while i < len(pixels):
        short = (0, 0)
        for distance in range(1, min(i, 16) + 1):
            n = 0
            while n < 5 and i + n < len(pixels) and pixels[i+n] == pixels[i+n-distance]:
                n += 1
            if n > short[0]:
                short = n, distance
        long = (0, 0)
        if i + 3 <= len(pixels):
            positions = pos_by_triple[pixels[i:i + 3]]
            last = bisect_left(positions, i)
            for p in reversed(positions[max(0, last-candidate_limit):last]):
                distance = i - p
                if distance > 1023:
                    continue
                n = 3
                while n < 34 and i+n < len(pixels) and pixels[i+n] == pixels[i+n-distance]:
                    n += 1
                if n > long[0]:
                    long = n, distance
                if n == 34:
                    break
        if short[0] >= 2 and short[0]-1 >= long[0]-2:
            count, distance = short
            tokens.append((1, bytes([((count + 6) << 4) | (distance - 1)])))
            i += count
        elif long[0] >= 3:
            count, distance = long
            tokens.append((1, bytes([((count - 3) << 2) | (distance >> 8),
                                     distance & 255])))
            i += count
        else:
            tokens.append((0, pixels[i:i+1]))
            i += 1
    compact = []
    i = 0
    while i < len(tokens):
        if tokens[i][0] == 0:
            j = i
            while j < len(tokens) and tokens[j][0] == 0 and j-i < 70:
                j += 1
            if j-i >= 8:
                literal = b"".join(chunk for _, chunk in tokens[i:j])
                compact.append((1, bytes([0xB8 + len(literal)]) + literal))
                i = j
                continue
        compact.append(tokens[i])
        i += 1
    packet = _pack_tokens(compact)
    if decode_stream(packet, expected_bytes=expected_bytes) != pixels:
        raise AssertionError("codec round-trip is not bit-identical")
    return packet



def encode_stream_compact(pixels: bytes, *, expected_bytes: int = TILE_BYTES,
                          candidate_limit: int = 96) -> bytes:
    """Alternate bounded LZ encoder using a backward token-cost search.

    The cost models each payload byte plus amortized flag-bit overhead.
    It is NOT claimed to produce the globally minimum exact packed size.
    Used only when the standard encoder exceeds an existing stream budget.
    Supports overlapping copies; the same real decoder validates the result.
    """
    from array import array
    from collections import deque
    n = len(pixels)
    if n != expected_bytes or not 1 <= n <= 1024*512*2:
        raise FormatError("unexpected or unsafe decoded rectangle size")
    if not 1 <= candidate_limit <= 1023:
        raise ValueError("invalid compact encoder candidate limit")
    by_triple = defaultdict(list)
    for i in range(n-2):
        by_triple[pixels[i:i+3]].append(i)
    costs = array("I", [0]) * (n+1)
    lengths = bytearray(n)
    families = bytearray(n)
    distances = array("H", [0]) * n
    # Raw-block candidates cost 9 + 8*(end-i) + costs[end].
    # Maintain min(costs[end] + 8*end) for ends i+8 ... i+70.
    raw_window = deque()
    for i in range(n-1,-1,-1):
        end = i+8
        while raw_window and raw_window[0] > i+70:
            raw_window.popleft()
        if end <= n:
            value = costs[end] + 8*end
            while raw_window and costs[raw_window[-1]]+8*raw_window[-1] >= value:
                raw_window.pop()
            raw_window.append(end)
        best = (9 + costs[i+1], 1, 0, 0)
        if raw_window:
            end = raw_window[0]
            proposal = (9+8*(end-i)+costs[end],end-i,3,0)
            if proposal[0] < best[0]:
                best = proposal
        short_len=0
        short_dist=0
        for d in range(1,min(i,16)+1):
            k=0
            while k<5 and i+k<n and pixels[i+k]==pixels[i+k-d]:
                k+=1
            if k>short_len:
                short_len,short_dist=k,d
            if k==5:
                break
        for k in range(2,short_len+1):
            proposal=(9+costs[i+k],k,1,short_dist)
            if proposal[0] < best[0]:
                best=proposal
        long_len=0
        long_dist=0
        if i+3 <= n:
            positions=by_triple[pixels[i:i+3]]
            last=bisect_left(positions,i)
            for p in reversed(positions[max(0,last-candidate_limit):last]):
                d=i-p
                if d>1023:
                    break
                k=3
                while k<34 and i+k<n and pixels[i+k]==pixels[i+k-d]:
                    k+=1
                if k>long_len:
                    long_len,long_dist=k,d
                if k==34:
                    break
        for k in range(3,long_len+1):
            proposal=(17+costs[i+k],k,2,long_dist)
            if proposal[0] < best[0]:
                best=proposal
        costs[i],lengths[i],families[i],distances[i]=best
    tokens=[]
    i=0
    while i<n:
        k,f,d=lengths[i],families[i],distances[i]
        if f==0:
            tokens.append((0,pixels[i:i+1]))
        elif f==1:
            tokens.append((1,bytes([((k+6)<<4)|(d-1)])))
        elif f==2:
            tokens.append((1,bytes([((k-3)<<2)|(d>>8),d&255])))
        elif f==3:
            tokens.append((1,bytes([0xB8+k])+pixels[i:i+k]))
        else:
            raise AssertionError("Unrecognized compact token")
        i+=k
    packet=_pack_tokens(tokens)
    if decode_stream(packet,expected_bytes=n)!=pixels:
        raise AssertionError("compact codec round-trip failed")
    return packet


def encode_with_budget(pixels: bytes, *, expected_bytes: int, capacity: int) -> tuple[bytes,str]:
    """Try the fast encoder first, then compact search, never relocate data."""
    if capacity < 1:
        raise FormatError("Invalid existing stream capacity")
    fast=encode_stream(pixels,expected_bytes=expected_bytes)
    if len(fast)<=capacity:
        return fast,"greedy"
    compact=encode_stream_compact(pixels,expected_bytes=expected_bytes)
    if len(compact)<=capacity:
        return compact,"compact_search"
    raise FormatError(
        f"Flag insertion exceeds existing GPU stream capacity "
        f"({capacity} bytes; greedy {len(fast)}, compact {len(compact)}); no relocation"
    )


def atlas_records(resource: bytes) -> list[dict]:
    """Parse and strictly check all the original GPU table geometry."""
    if len(resource) != RESOURCE_BYTES:
        raise FormatError("unexpected name resource size")
    if struct.unpack_from("<I", resource, 0)[0] != GPU_BASE + TABLE_OFFSET:
        raise FormatError("unexpected GPU list pointer")
    if struct.unpack_from("<H", resource, TABLE_OFFSET + UPLOADS*16)[0] != 255:
        raise FormatError("missing GPU list terminator")
    records = []
    for i in range(UPLOADS):
        kind, x, y, w, h, zero, addr = struct.unpack_from(
            "<HHHHHHI", resource, TABLE_OFFSET + i*16)
        offset = addr-GPU_BASE
        if (kind,w,h,zero) != (10,32,128,0) or x%32 or y%128 or offset%4:
            raise FormatError(f"unexpected GPU upload {i}")
        records.append({"index":i,"x_words":x,"y":y,"offset":offset})
    starts = [r["offset"] for r in records] + [TABLE_OFFSET]
    if starts[0] != 4 or any(a >= b for a,b in zip(starts,starts[1:])):
        raise FormatError("invalid GPU stream boundaries")
    for record,end in zip(records,starts[1:]):
        record["end"] = end
    return records


def decode_atlas(resource: bytes) -> list[bytes]:
    """Last stream may have larger zero-filled unused space before GPU table."""
    return [decode_stream(resource[r["offset"]:r["end"]],
                          max_padding=(TABLE_OFFSET if r["index"] == UPLOADS-1 else 3))
            for r in atlas_records(resource)]


def repack_atlas(reference: bytes, tiles: list[bytes]) -> tuple[bytes, dict]:
    """Rebuild within original byte budget; does not edit or export a disc."""
    records = atlas_records(reference)
    if len(tiles) != UPLOADS or any(len(t) != TILE_BYTES for t in tiles):
        raise FormatError("expected 26 tiles, each 8192 bytes")
    out = bytearray(reference)
    cursor = 4
    for rec, tile in zip(records, tiles):
        packed = encode_stream(tile)
        end = cursor+len(packed)
        next_cursor = (end+3)&~3
        if next_cursor > TABLE_OFFSET:
            raise FormatError("compressed atlas exceeds existing allocation")
        out[cursor:end] = packed
        out[end:next_cursor] = bytes(next_cursor-end)
        struct.pack_into("<I",out,TABLE_OFFSET + rec["index"]*16+12,GPU_BASE+cursor)
        cursor = next_cursor
    out[cursor:TABLE_OFFSET] = bytes(TABLE_OFFSET-cursor)
    rebuilt = bytes(out)
    if decode_atlas(rebuilt) != tiles:
        raise AssertionError("repacked pixels differ")
    return rebuilt, {"records":UPLOADS, "capacity_bytes":TABLE_OFFSET-4,
                     "bytes_used":cursor-4, "free_bytes":TABLE_OFFSET-cursor}
