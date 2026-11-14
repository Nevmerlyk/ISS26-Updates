#!/usr/bin/env python3
"""Inspect live GPU packets in PCSX-Redux PSXGPUDUMPv1r1 files (read-only).

Packet layout follows the published GPUDUMP standard and PCSX-Redux
GPUDumpReader. This parser processes *only traffic after TraceBegin*.
It extracts textured GP0 polygons/sprites and texture/upload metadata.
It does not draw or classify flags by appearance, and unknown commands
make the report advisory rather than authoritative.

Outputs JSON metadata only: no VRAM, screens or copyrighted game imagery.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import struct

MAGIC = b"PSXGPUDUMPv1r1\x00\x00"
TRACE_BEGIN = 5
VSYNC = 2
GP0 = 0
MAX_BYTES = 16 * 1024 * 1024
MAX_GROUPS = 30000
MAX_IMAGE_WORDS = 1024 * 1024


def sx16(x: int) -> int:
    x &= 0xFFFF
    return x - 65536 if x & 0x8000 else x


def xy(w: int) -> tuple[int, int]:
    return sx16(w), sx16(w >> 16)


def texpage(tpage: int) -> dict:
    # 4bpp: 64 16-bit words per 256-pixel texture page in X.
    return {
        "raw": tpage,
        "x_word": (tpage & 0x0F) * 64,
        "y": ((tpage >> 4) & 1) * 256,
        "depth": (tpage >> 7) & 3,
    }


def clut_xy(raw: int) -> tuple[int, int]:
    return (raw & 63) * 16, (raw >> 6) & 511


def packet_iter(data: bytes):
    if len(data) < 16 or data[:16] != MAGIC or len(data) % 4:
        raise ValueError("Invalid PSXGPUDUMPv1r1 header or alignment")
    off = 16
    while off < len(data):
        word, = struct.unpack_from("<I", data, off)
        kind = word >> 24
        n = word & 0xFFFFFF
        off += 4
        if n > (len(data) - off) // 4:
            raise ValueError("Truncated GPU dump packet")
        payload = struct.unpack_from("<" + str(n) + "I", data, off) if n else ()
        off += n * 4
        yield kind, payload


def gp0_length(words: list[int], pos: int) -> int | None:
    op = words[pos] >> 24
    available = len(words) - pos
    if op == 0x02:
        return 3 if available >= 3 else None
    if 0x20 <= op <= 0x3F:
        vertex_count = 4 if op & 8 else 3
        gouraud = bool(op & 0x10)
        textured = bool(op & 4)
        count = 1 + vertex_count * (1 + int(textured)) + (vertex_count - 1 if gouraud else 0)
        return count if available >= count else None
    if 0x40 <= op <= 0x5F:
        if op & 8:  # polylines end in a 0x50005000 marker
            minimum = 5 if op & 0x10 else 4
            if available < minimum:
                return None
            for i in range(pos+minimum-1, len(words)):
                if words[i] & 0xF000F000 == 0x50005000:
                    return i - pos + 1
            if available > 100000:
                raise ValueError("Unterminated GP0 polyline")
            return None
        count = 4 if op & 0x10 else 3
        return count if available >= count else None
    if 0x60 <= op <= 0x7F:
        textured = bool(op & 4)
        variable = (op & 0x18) == 0
        count = 2 + int(textured) + int(variable)
        return count if available >= count else None
    if 0x80 <= op <= 0x9F:
        return 4 if available >= 4 else None
    if op == 0xA0:  # GP0 A0 image load: 3-word header, then packed pixel words
        if available < 3:
            return None
        wh = words[pos+2]
        width = wh & 0xFFFF
        height = (wh >> 16) & 0xFFFF
        pixels = width * height
        if pixels > 2 * MAX_IMAGE_WORDS:
            raise ValueError("Unreasonable GP0 image upload dimensions")
        count = 3 + (pixels + 1) // 2
        return count if available >= count else None
    if op == 0xC0:
        return 3 if available >= 3 else None
    # GP0 environment commands and most reset/NOP commands are one word.
    return 1


class GP0Inspector:
    def __init__(self):
        self.pending: list[int] = []
        self.frame = 0
        self.last_texpage: int | None = None
        self.draw_count = 0
        self.images = 0
        self.moves = 0
        self.unparsed = Counter()
        self.draw_groups: Counter[tuple] = Counter()
        self.transfer_groups: Counter[tuple] = Counter()

    def feed(self, words):
        self.pending.extend(words)
        p = 0
        while p < len(self.pending):
            length = gp0_length(self.pending, p)
            if length is None:
                break
            op = self.pending[p] >> 24
            segment = self.pending[p:p+length]
            if 0x20 <= op <= 0x3F and op & 4:
                self.polygon(op, segment)
            elif 0x60 <= op <= 0x7F and op & 4:
                self.rectangle(op, segment)
            elif op == 0xE1:
                self.last_texpage = segment[0] & 0xFFFF
            elif op == 0x80:
                x1, y1 = xy(segment[1])
                x2, y2 = xy(segment[2])
                wh = segment[3]
                self.transfer_groups[("vram_to_vram", x1, y1, x2, y2,
                                      wh & 0xFFFF, wh >> 16)] += 1
                self.moves += 1
            elif op == 0xA0:
                x, y = xy(segment[1])
                wh = segment[2]
                self.transfer_groups[("cpu_to_vram", x, y, wh & 0xFFFF,
                                      wh >> 16)] += 1
                self.images += 1
            elif op == 0xC0:
                x, y = xy(segment[1])
                wh = segment[2]
                self.transfer_groups[("vram_to_cpu", x, y, wh & 0xFFFF,
                                      wh >> 16)] += 1
            elif op not in (0, 1, 2, 0x1F) and not (0x40 <= op <= 0x7F) and not (0xE0 <= op <= 0xE6):
                self.unparsed[f"0x{op:02X}"] += 1
            p += length
        if p:
            del self.pending[:p]
        if len(self.pending) > MAX_IMAGE_WORDS + 3:
            raise ValueError("Unbounded GP0 command buffer")

    def record(self, kind: str, opcode: int, uvs: list[tuple[int, int]],
               raw_tpage: int | None, raw_clut: int):
        bounds = (min(u for u,v in uvs), min(v for u,v in uvs),
                  max(u for u,v in uvs), max(v for u,v in uvs))
        if raw_tpage is not None:
            page = texpage(raw_tpage)
            src = (page["x_word"] + bounds[0] // (4 if page["depth"] == 0 else 2 if page["depth"] == 1 else 1),
                   page["y"] + bounds[1])
            page_xy = (page["x_word"], page["y"])
            depth = page["depth"]
        else:
            src, page_xy, depth = (-1, -1), (-1, -1), -1
        self.draw_groups[(kind, opcode, page_xy[0], page_xy[1], depth,
                          *clut_xy(raw_clut), *src, *bounds, self.frame)] += 1
        self.draw_count += 1
        if len(self.draw_groups) > MAX_GROUPS:
            raise ValueError("Excessive textured GPU primitive groups")

    def polygon(self, op: int, w: list[int]):
        vertices = 4 if op & 8 else 3
        gouraud = bool(op & 0x10)
        uvs = []
        pos = 1
        raw_clut = 0
        raw_tpage = None
        for i in range(vertices):
            if gouraud and i:
                pos += 1
            pos += 1  # XY word
            uv = w[pos]
            uvs.append((uv & 255, (uv >> 8) & 255))
            if i == 0:
                raw_clut = uv >> 16
            elif i == 1:
                raw_tpage = uv >> 16
            pos += 1
        self.record("textured_polygon", op, uvs, raw_tpage, raw_clut)

    def rectangle(self, op: int, w: list[int]):
        uv = w[2]
        self.record("textured_rectangle", op, [(uv & 255, (uv >> 8) & 255)],
                    self.last_texpage, uv >> 16)

    def summary(self):
        sorted_draws = sorted(self.draw_groups.items(), key=lambda item: (-item[1], item[0]))
        rows = []
        for fields, count in sorted_draws[:200]:
            kind, opcode, page_x, page_y, depth, cx, cy, sx, sy, u0,v0,u1,v1,frame = fields
            rows.append({
                "primitive": kind, "opcode": f"0x{opcode:02X}", "relative_frame": frame,
                "tpage_xy_words": [page_x, page_y], "texture_depth": depth,
                "clut_xy_words": [cx,cy], "source_min_xy_words": [sx,sy],
                "uv_bounds_pixels": [u0,v0,u1,v1], "count": count,
            })
        return {
            "textured_primitive_count": self.draw_count,
            "cpu_to_vram_uploads": self.images, "vram_to_vram_moves": self.moves,
            "unrecognized_command_counts": dict(self.unparsed),
            "incomplete_gp0_words": len(self.pending),
            "all_draw_groups_count": len(self.draw_groups),
            "top_draw_groups": rows,
            "transfers": [
                {"operation": key[0], "dimensions": list(key[1:]), "count": count}
                for key, count in self.transfer_groups.most_common(100)
            ],
            "notice": "GP0 draw primitive sampling only; cannot classify a crowd flag by texture coordinates alone.",
        }


def inspect(data: bytes) -> dict:
    if len(data) > MAX_BYTES:
        raise ValueError("GPU dump exceeds size cap")
    source = GP0Inspector()
    trace_found = False
    for kind, payload in packet_iter(data):
        if not trace_found:
            if kind == TRACE_BEGIN:
                trace_found = True
            continue
        if kind == GP0:
            source.feed(payload)
        elif kind == VSYNC:
            source.frame += 1
    result = source.summary()
    result["trace_begin_found"] = trace_found
    result["vsync_frames"] = source.frame
    if not trace_found:
        result["notice"] = "No TraceBegin: pre-capture restoration skipped; no live GPU samples."
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path, help="PCSX-Redux .gpd file")
    parser.add_argument("--output", type=Path, default=Path("gpu_flag_primitive_report.json"))
    args = parser.parse_args()
    result = inspect(args.dump.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("TraceBegin", result["trace_begin_found"], "textured GPU draws",
          result["textured_primitive_count"])
    print("Saved", args.output)


if __name__ == "__main__":
    main()
