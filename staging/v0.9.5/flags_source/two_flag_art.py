"""ISS26 two-country 4bpp flag artwork and bounded VRAM upload patching.

Development component for the original European ISS Pro Evolution 2 game.
This module does NOT modify a disc, assume an atlas owner, or create a release.
All upload rectangles must first be identified from the actual game resources.

Flag styles and national CLUT indices are in reversed country order:
Bosnia: name slot 23, CLUT 30, large-style candidate 10.
Cabo Verde: name slot 53, CLUT 0, large style 1.
Bosnia's CLUT semantic indices (blue=1, yellow=2, white=3) were established
in prior v0.9.5 investigation. Cabo Verde indices MUST be supplied from the
target game's CLUT; never assume matching indices across countries.
"""
from __future__ import annotations

import math
from typing import Mapping

BOSNIA_CLUT = {"blue": 1, "yellow": 2, "white": 3}
LARGE_STYLES = {"bosnia": 10, "cabo_verde": 1}
NAME_SLOTS = {"bosnia": 23, "cabo_verde": 53}
CLUT_SLOTS = {"bosnia": 30, "cabo_verde": 0}
NATIONAL_LARGE_VRAM_ORIGIN = (832, 256)
NATIONAL_LARGE_SIZE = (64, 28)
SUPPORTED_SIZES = ((64, 28), (24, 16), (24, 8))


def large_style_vram(style: int) -> tuple[int, int]:
    """Return VRAM word X and pixel Y of an original large-flag slot."""
    if not 0 <= style < 28:
        raise ValueError("original large-flag style outside 0..27")
    return 832 + 16 * (style % 4), 256 + 32 * (style // 4)


def _star_points(x: float, y: float, radius: float) -> list[tuple[float, float]]:
    return [
        (
            x + radius * (1.0 if i % 2 == 0 else 0.39)
            * math.cos(-math.pi / 2 + i * math.pi / 5),
            y + radius * (1.0 if i % 2 == 0 else 0.39)
            * math.sin(-math.pi / 2 + i * math.pi / 5),
        )
        for i in range(10)
    ]


def _contains(px: float, py: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(polygon) - 1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _draw_star(
    pixels: bytearray, width: int, height: int,
    x: float, y: float, radius: float, color: int
) -> None:
    polygon = _star_points(x, y, radius)
    x0 = max(0, math.floor(x - radius - 1))
    x1 = min(width, math.ceil(x + radius + 1))
    y0 = max(0, math.floor(y - radius - 1))
    y1 = min(height, math.ceil(y + radius + 1))
    painted = False
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            # Small stars survive downscaling by testing four subpixel centers.
            samples = ((xx + dx, yy + dy) for dx in (0.25, 0.75)
                       for dy in (0.25, 0.75))
            if any(_contains(sx, sy, polygon) for sx, sy in samples):
                pixels[yy * width + xx] = color
                painted = True
    if not painted and 0 <= x < width and 0 <= y < height:
        xx = max(0, min(width - 1, round(x)))
        yy = max(0, min(height - 1, round(y)))
        pixels[yy * width + xx] = color


def flag_pixels(
    country: str, width: int, height: int, colors: Mapping[str, int]
) -> bytes:
    """Generate raw, unpacked palette indices (one byte per visible pixel).

    Indices 1..15 are mandatory; CLUT index 0 is PS1 transparency.
    This is geometry-only data, not a validated image in the game.
    """
    if country not in ("bosnia", "cabo_verde"):
        raise ValueError("unknown target country")
    if width < 8 or height < 8 or width % 2:
        raise ValueError("unsupported flag dimensions")
    required = ("blue", "yellow", "white")
    if country == "cabo_verde":
        required += ("red",)
    if any(name not in colors for name in required):
        raise ValueError("missing semantic CLUT color")
    used = [colors[name] for name in required]
    if any(not isinstance(v, int) or isinstance(v, bool)
           or not 1 <= v <= 15 for v in used) or len(set(used)) != len(used):
        raise ValueError("palette entries must be unique opaque 4bpp colors")

    pixels = bytearray([colors["blue"]] * (width * height))

    if country == "bosnia":
        # Blue field, yellow right triangle. The star row is parallel to its
        # 45-degree diagonal. 7 full white stars plus two edge-clipped stars.
        for yy in range(height):
            edge = width * 0.50 + yy * (width * 0.44 / height)
            right = width * 0.96
            for xx in range(width):
                if edge <= xx + 0.5 < right:
                    pixels[yy * width + xx] = colors["yellow"]
        for i in range(9):
            t = i / 8
            sy = t * height
            sx = width * 0.43 + t * width * 0.44
            _draw_star(pixels, width, height, sx, sy,
                       max(0.75, height * 0.065), colors["white"])
    else:
        # Official Cabo Verde proportions: top blue 1/2, white 1/12,
        # red 1/12, white 1/12, bottom blue 1/4.
        for yy in range(height):
            fraction = (yy + 0.5) / height
            if 0.5 <= fraction < 7 / 12 or 2 / 3 <= fraction < 0.75:
                color = colors["white"]
            elif 7 / 12 <= fraction < 2 / 3:
                color = colors["red"]
            else:
                color = colors["blue"]
            pixels[yy * width: (yy + 1) * width] = bytes([color]) * width
        # Official constitutional center: x = 3/8 W, y = 5/8 H.
        cx, cy = 0.375 * width, 0.625 * height
        ring = 0.25 * height
        for i in range(10):
            angle = -math.pi / 2 + i * math.tau / 10
            sx = cx + ring * math.cos(angle)
            sy = cy + ring * math.sin(angle)
            _draw_star(pixels, width, height, sx, sy,
                       max(0.62, height * 0.058), colors["yellow"])
    return bytes(pixels)


def pack_4bpp(pixels: bytes, width: int, height: int) -> bytes:
    """Pack left pixel in low nibble, right pixel in high nibble."""
    if width <= 0 or width % 2 or height <= 0 or len(pixels) != width * height:
        raise ValueError("invalid packed flag dimensions")
    if any(p > 15 for p in pixels):
        raise ValueError("pixel index out of 4bpp range")
    return bytes(pixels[i] | pixels[i + 1] << 4
                 for i in range(0, len(pixels), 2))


def blit_onto_gpu_upload(
    decoded: bytes,
    upload_x_words: int, upload_y: int, upload_width_words: int,
    upload_height: int,
    flag_x_words: int, flag_y: int,
    flag_width: int, flag_height: int,
    pixels: bytes,
) -> tuple[bytes, int]:
    """Replace only intersecting 4bpp pixels of a decoded GPU upload.

    All horizontal GPU coordinates are 16-bit VRAM words (4 pixels/word).
    Does not resize uploads, touch any other sprite or overwrite tile padding.
    Returns (edited bytes, number of altered pixel indices). Caller is
    responsible for validating that THIS resource is the actual flag source.
    """
    if (
        upload_width_words <= 0 or upload_height <= 0
        or flag_width <= 0 or flag_height <= 0 or flag_width % 4
        or len(decoded) != upload_width_words * 2 * upload_height
        or len(pixels) != flag_width * flag_height
        or any(p > 15 for p in pixels)
    ):
        raise ValueError("invalid 4bpp upload or flag rectangle")
    uw = upload_width_words * 4
    upload_x = upload_x_words * 4
    flag_x = flag_x_words * 4
    x0 = max(upload_x, flag_x)
    x1 = min(upload_x + uw, flag_x + flag_width)
    y0 = max(upload_y, flag_y)
    y1 = min(upload_y + upload_height, flag_y + flag_height)
    if x0 >= x1 or y0 >= y1:
        return decoded, 0

    output = bytearray(decoded)
    altered = 0
    for vy in range(y0, y1):
        for vx in range(x0, x1):
            old_local = (vy - upload_y) * uw + vx - upload_x
            new_local = (vy - flag_y) * flag_width + vx - flag_x
            desired = pixels[new_local]
            byte_index = old_local // 2
            old = output[byte_index]
            if old_local % 2:
                actual = old >> 4
                new = (old & 0x0F) | desired << 4
            else:
                actual = old & 0x0F
                new = (old & 0xF0) | desired
            if actual != desired:
                output[byte_index] = new
                altered += 1
    return bytes(output), altered
