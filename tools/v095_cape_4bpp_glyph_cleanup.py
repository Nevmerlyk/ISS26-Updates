#!/usr/bin/env python3
"""ISS26: remove contaminating neighboring glyph fragments from 4bpp source crops.

This is a deterministic pixel-only helper. No game files or patches are written.
"""
from __future__ import annotations

def isolate_main_ink_component(glyph: bytes, width: int, height: int = 16):
    """Preserve the largest orthogonally connected nonzero palette-index group.

    The original 4-bit CLUT indices are not altered; only detached pixels are
    cleared. Reject ambiguous equal-size components.
    """
    if width <= 0 or height <= 0 or len(glyph) != width * height or any(x > 15 for x in glyph):
        raise ValueError("Expected unpacked 4bpp palette indices for one glyph")
    remaining = {(x,y) for y in range(height) for x in range(width) if glyph[y * width + x]}
    if not remaining:
        raise ValueError("Empty glyph")
    groups = []
    while remaining:
        seed = next(iter(remaining))
        remaining.remove(seed)
        todo = [seed]
        group = {seed}
        while todo:
            x,y = todo.pop()
            for nextpos in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                if nextpos in remaining:
                    remaining.remove(nextpos)
                    todo.append(nextpos)
                    group.add(nextpos)
        groups.append(group)
    groups.sort(key=len,reverse=True)
    if len(groups)>1 and len(groups[0]) == len(groups[1]):
        raise ValueError("Ambiguous main glyph component")
    keep = groups[0]
    output = bytes(glyph[y*width+x] if (x,y) in keep else 0
                   for y in range(height) for x in range(width))
    return output, {"component_sizes":[len(x) for x in groups],
                    "removed_pixels":sum(map(len,groups[1:])),
                    "kept_pixels":len(keep)}
