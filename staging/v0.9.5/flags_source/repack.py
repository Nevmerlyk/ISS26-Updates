"""Fixed-allocation graphics-blob patching for ISS Pro Evolution 2 (PS1).

This is a patch construction primitive, not a flag atlas locator. It refuses
unverified offsets, growth, and changed payloads without exact round-trip.
"""
from __future__ import annotations
from dataclasses import dataclass
from wecodec import decode,encode

@dataclass(frozen=True)
class StreamSpan:
    start:int
    end:int
    output_bytes:int


def replace_stream(resource:bytes, span:StreamSpan, new_decoded:bytes)->bytes:
    if not (0<=span.start<span.end<=len(resource)):
        raise ValueError('invalid source span')
    if len(new_decoded)!=span.output_bytes:
        raise ValueError('new texture must match original VRAM byte count')
    old=resource[span.start:span.end]
    _,consumed,_=decode(old,span.output_bytes)
    replacement=encode(new_decoded)
    if len(replacement)>span.end-span.start:
        raise ValueError(f'compressed stream needs {len(replacement)} bytes but only {span.end-span.start} are allocated')
    if decode(replacement,span.output_bytes)[0]!=new_decoded:
        raise AssertionError('roundtrip failed')
    # Keep bytes not occupied by new encoded stream unchanged, maintaining
    # absolute pointers to all following blobs.
    out=bytearray(resource)
    out[span.start:span.start+len(replacement)]=replacement
    return bytes(out)