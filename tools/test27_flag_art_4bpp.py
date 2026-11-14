#!/usr/bin/env python3
"""ISS26 Test27: generate *candidate* national flag 4bpp source artwork.

Research graphics only. This module NEVER patches or reads a commercial disc,
does not modify a game updater feed, and never declares in-game visual success.

Target: original game's observed 64x28 4-bit indexed flag tile (16x28 VRAM
words, 896 bytes). Four pixels per little-endian 16-bit VRAM word.
Palette indices 1..15 are used for opaque colours; 0 is reserved.
The generated art requires validation against official flag geometry,
the final in-game CLUT, source-resource ownership and all draw surfaces.

Bosnia source: Law on the Flag (as quoted by Constitutional Court of BiH):
https://www.ustavnisud.ba/uploads/odluke/_en/U-11-19-1218642.pdf
Cabo Verde construction: https://www.thefactbook.org/cabo-verde/2024
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct

W, H, BPP = 64, 28, 4
FLAG_BYTES = W * H // 2
PALETTE_BYTES = 32
COLORS = {
    "bosnia": ((0, 0, 0), (0, 35, 149), (254, 203, 0), (255, 255, 255)),
    "cape_verde": ((0, 0, 0), (0, 53, 148), (255, 255, 255),
                   (208, 26, 34), (247, 210, 14)),
}
SOURCE_REFS = {
    "bosnia": "https://www.ustavnisud.ba/uploads/odluke/_en/U-11-19-1218642.pdf",
    "cape_verde": "https://www.thefactbook.org/cabo-verde/2024",
}

def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def bgr555(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    if not all(isinstance(v, int) and 0 <= v <= 255 for v in rgb):
        raise ValueError("Invalid RGB")
    return ((b * 31 + 127) // 255 << 10 |
            (g * 31 + 127) // 255 << 5 |
            (r * 31 + 127) // 255)

def make_clut(colors: tuple[tuple[int, int, int], ...]) -> bytes:
    if not (2 <= len(colors) <= 16):
        raise ValueError("PS1 4bpp CLUT must have at most 16 entries")
    return struct.pack("<16H", *(bgr555(rgb) for rgb in colors),
                       *([0] * (16 - len(colors))))

def pack_4bpp(indices: list[int]) -> bytes:
    if len(indices) != W * H or not all(type(x) is int and 0 <= x < 16 for x in indices):
        raise ValueError("Expected exactly 64x28 4bpp palette indices")
    return bytes((indices[i] | (indices[i+1] << 4))
                 for i in range(0, W * H, 2))

def unpack_4bpp(raw: bytes) -> list[int]:
    if len(raw) != FLAG_BYTES:
        raise ValueError("Expected exactly 896 packed bytes")
    result = []
    for word in raw:
        result.extend((word & 15, word >> 4))
    return result

def star_vertices(x: float, y: float, outer: float) -> list[tuple[float, float]]:
    if outer <= 0:
        raise ValueError("Star radius must be positive")
    result = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        radius = outer if i % 2 == 0 else outer * 0.43
        result.append((x + math.cos(angle) * radius,
                       y + math.sin(angle) * radius))
    return result

def inside_polygon(x: float, y: float,
                   poly: list[tuple[float, float]]) -> bool:
    in_shape = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < cross:
                in_shape = not in_shape
        j = i
    return in_shape

def draw_star(canvas: list[int], cx: float, cy: float,
              outer: float, color: int) -> int:
    poly = star_vertices(cx, cy, outer)
    changed = 0
    # 4x4 subpixel threshold avoids losing small five-pointed stars.
    for y in range(max(0, math.floor(cy - outer - 1)),
                   min(H, math.ceil(cy + outer + 1))):
        for x in range(max(0, math.floor(cx - outer - 1)),
                       min(W, math.ceil(cx + outer + 1))):
            covered = sum(inside_polygon(x + (sx + .5) / 4,
                                         y + (sy + .5) / 4, poly)
                          for sy in range(4) for sx in range(4))
            if covered >= 4 and canvas[y*W+x] != color:
                canvas[y*W+x] = color
                changed += 1
    return changed

def cape_verde_pixels() -> tuple[list[int], dict]:
    """Blue, white-red-white lower stripe, ring of precisely ten stars."""
    px = [1] * (W * H)
    for y in range(H):
        value = 2 if y in (14, 15, 18, 19) else 3 if y in (16, 17) else 1
        for x in range(W):
            px[y*W+x] = value
    centres = []
    for i in range(10):
        angle = -math.pi / 2 + 2 * math.pi * i / 10
        cx = 24 + 7.0 * math.cos(angle)
        cy = 17 + 7.0 * math.sin(angle)
        filled = draw_star(px, cx, cy, 1.65, 4)
        if filled == 0:
            raise AssertionError("Star lost at 64x28 resolution")
        centres.append([round(cx, 3), round(cy, 3)])
    return px, {
        "blue_height_top_rows": 14,
        "stripe_rows": {"white_upper": [14, 15], "red": [16, 17],
                        "white_lower": [18, 19]},
        "stars": 10,
        "star_centres_xy": centres,
        "star_color_index": 4,
        "flag_geometry": "2:3 source adapted to 64x28 target atlas tile; visual review required",
    }

def bosnia_pixels() -> tuple[list[int], dict]:
    """Blue field, top/right yellow triangle and diagonally stepped stars.

    This is a low-resolution approximation, not a certified 1:2 print
    master. Top and bottom partial stars are intentionally clipped.
    """
    px = [1] * (W * H)
    for y in range(H):
        edge = 22.0 + 1.5 * (y + .5)
        for x in range(W):
            if x + .5 >= edge:
                px[y*W+x] = 2
    centres = []
    for i in range(9):
        cy = i * 3.5
        cx = 22 + 1.5 * cy - 4.1
        filled = draw_star(px, cx, cy, 2.1, 3)
        if filled == 0:
            raise AssertionError("Bosnian diagonal star lost in rasterisation")
        centres.append([round(cx, 3), round(cy, 3)])
    return px, {
        "triangle_top_x": 22,
        "triangle_edge_formula": "x = 22 + 1.5 * y",
        "star_count": 9,
        "star_centres_xy": centres,
        "partial_stars_at_y": [0, 28],
        "star_color_index": 3,
        "flag_geometry": "Official 1:2 composition approximated in 64x28 target atlas; visual review required",
    }

def candidate(name: str) -> tuple[bytes, bytes, list[int], dict]:
    if name == "bosnia":
        pixels, geom = bosnia_pixels()
    elif name == "cape_verde":
        pixels, geom = cape_verde_pixels()
    else:
        raise ValueError("Unknown national flag")
    used = set(pixels)
    if 0 in used or min(used) < 1 or max(used) >= len(COLORS[name]):
        raise AssertionError("Opaque artwork used transparent or invalid index")
    bitmap = pack_4bpp(pixels)
    palette = make_clut(COLORS[name])
    if unpack_4bpp(bitmap) != pixels:
        raise AssertionError("PS1 4bpp round-trip failed")
    return bitmap, palette, pixels, geom

def ppm(pixels: list[int], colors: tuple[tuple[int,int,int],...],
        scale: int = 8) -> bytes:
    if scale not in (1, 2, 4, 8, 16):
        raise ValueError("Invalid pixel-art preview scale")
    data = bytearray(f"P6\n{W*scale} {H*scale}\n255\n".encode("ascii"))
    for y in range(H):
        for _ in range(scale):
            for x in range(W):
                color = bytes(colors[pixels[y*W+x]])
                data.extend(color * scale)
    return bytes(data)

def generate(output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schemaVersion": 1,
        "kind": "ISS26 Test27 national flag research art, NOT a game patch",
        "flag_size_pixels": [W,H],
        "format": "PS1 little-endian 4bpp, 2 pixels/byte, low nibble first",
        "tile_bytes": FLAG_BYTES,
        "palette_format": "16 BGR555 entries, little-endian, index 0 reserved",
        "corrected_game_patch": False,
        "can_install_into_game": False,
        "source_disc_modified": False,
        "standalone_clean_original_patch_created": False,
        "game_update_feed_modified": False,
        "must_validate": [
            "Official artwork/geometry at 64x28",
            "Real in-game draw palette and CLUT",
            "MIPS MoveImage StoreImage LoadImage stage writer",
            "Shared DATSEL/DATSEL3/GDC atlas and club collision",
            "Big flag, player-carried banner, waving crowd flag scenes",
            "Unmodified all 54+4 national teams, 24 club emblems, Track02..12",
        ],
        "flags": {},
    }
    for name in ("bosnia", "cape_verde"):
        bitmap, palette, pixels, geom = candidate(name)
        (output / f"{name}_64x28_4bpp.bin").write_bytes(bitmap)
        (output / f"{name}_clut_bgr555.bin").write_bytes(palette)
        (output / f"{name}_8x_preview.ppm").write_bytes(ppm(pixels, COLORS[name]))
        manifest["flags"][name] = {
            "bitmap_sha256": hash_bytes(bitmap),
            "clut_sha256": hash_bytes(palette),
            "preview_sha256": hash_bytes(ppm(pixels, COLORS[name])),
            "palette_used_indices": sorted(set(pixels)),
            "palette": COLORS[name],
            "geometry": geom,
            "official_reference": SOURCE_REFS[name],
            "ready_for_disc_injection": False,
        }
    (output / "test27_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return manifest

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    manifest = generate(args.output_dir)
    print("PASS: created 2 candidate 64x28 flag tiles, 2 PS1 CLUTs, 2 previews")
    for name, desc in manifest["flags"].items():
        print(f"{name}: bitmap {desc['bitmap_sha256']} CLUT {desc['clut_sha256']}")
    print("RESEARCH ONLY: no ISO/BIN/CUE or patch/update feed was modified")

if __name__ == "__main__":
    main()
