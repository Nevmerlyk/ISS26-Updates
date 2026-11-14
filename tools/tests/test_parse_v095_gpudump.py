#!/usr/bin/env python3
"""Synthetic GPUDUMPv1r1 tests with no game, BIOS or copyright assets."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parse_v095_gpudump as gp


def pack(kind: int, *words: int) -> bytes:
    return struct.pack("<I", (kind << 24) | len(words)) + (
        struct.pack("<" + str(len(words)) + "I", *words) if words else b""
    )


def textured_quad():
    # 4bpp texture page 8 -> VRAM x=512, U=192 -> source word x=560.
    # CLUT (0,505), V=0..27. 0x3C shaded, textured quad.
    clut = 505 << 6
    tpage = 8
    return (
        0x3CFFFFFF,
        0x00000000, (clut << 16) | 192,
        0x00FFFFFF, 0x00000001, (tpage << 16) | 255,
        0x00FFFFFF, 0x00010001, (27 << 8) | 255,
        0x00FFFFFF, 0x00010000, (27 << 8) | 192,
    )


class TestGPUDumpParser(unittest.TestCase):
    def test_live_quad_source_clut_and_trace_skip(self):
        fake_snapshot_quad = textured_quad()
        live = textured_quad()
        data = (gp.MAGIC + pack(0, *fake_snapshot_quad) +
                pack(gp.TRACE_BEGIN) + pack(gp.GP0, *live) +
                pack(gp.VSYNC, 1, 0))
        out = gp.inspect(data)
        self.assertTrue(out["trace_begin_found"])
        self.assertEqual(out["vsync_frames"], 1)
        self.assertEqual(out["textured_primitive_count"], 1)
        row = out["top_draw_groups"][0]
        self.assertEqual(row["opcode"], "0x3C")
        self.assertEqual(row["texture_depth"], 0)
        self.assertEqual(row["tpage_xy_words"], [512, 0])
        self.assertEqual(row["clut_xy_words"], [0, 505])
        self.assertEqual(row["source_min_xy_words"], [560, 0])
        self.assertEqual(row["uv_bounds_pixels"], [192, 0, 255, 27])

    def test_split_gpu_packet_does_not_desynchronize(self):
        words = textured_quad()
        data = gp.MAGIC + pack(gp.TRACE_BEGIN) + pack(gp.GP0, *words[:4])
        data += pack(gp.GP0, *words[4:]) + pack(gp.VSYNC, 2, 0)
        result = gp.inspect(data)
        self.assertEqual(result["textured_primitive_count"], 1)
        self.assertEqual(result["incomplete_gp0_words"], 0)

    def test_upload_data_looking_like_polygon_is_not_draw(self):
        upload = [0xA0000000, 0, 0x00020002, 0x3CFFFFFF, 0x3CFFFFFF]
        move = [0x80000000, 0x01000200, 0x02000240, 0x001C0010]
        data = (gp.MAGIC + pack(gp.TRACE_BEGIN) +
                pack(gp.GP0, *upload, *move, *textured_quad()))
        out = gp.inspect(data)
        self.assertEqual(out["textured_primitive_count"], 1)
        self.assertEqual(out["cpu_to_vram_uploads"], 1)
        self.assertEqual(out["vram_to_vram_moves"], 1)
        self.assertEqual(len(out["transfers"]), 2)

    def test_pre_trace_restoration_does_not_count(self):
        data = gp.MAGIC + pack(gp.GP0, *textured_quad())
        result = gp.inspect(data)
        self.assertFalse(result["trace_begin_found"])
        self.assertEqual(result["textured_primitive_count"], 0)

    def test_corrupt_packet_and_header_rejected(self):
        with self.assertRaisesRegex(ValueError, "header"):
            gp.inspect(b"junk")
        with self.assertRaisesRegex(ValueError, "Truncated"):
            gp.inspect(gp.MAGIC + struct.pack("<I", (0 << 24) | 12))

    def test_invalid_upload_size_rejected(self):
        corrupt = [0xA0000000, 0, 0xFFFFFFFF]
        with self.assertRaisesRegex(ValueError, "Unreasonable"):
            gp.inspect(gp.MAGIC + pack(gp.TRACE_BEGIN) + pack(gp.GP0, *corrupt))

    def test_style55_bosnia_moveimage_source(self):
        # Recorded MoveImage source atlas for style55 is (816,368).
        # Destination for away stage is (560,28).
        src = (368 << 16) | 816
        dst = (28 << 16) | 560
        size = (28 << 16) | 16
        out = gp.inspect(gp.MAGIC + pack(gp.TRACE_BEGIN) +
                         pack(gp.GP0, 0x80000000, src, dst, size))
        self.assertEqual(out["vram_to_vram_moves"], 1)
        transfer = out["transfers"][0]
        self.assertEqual(transfer["operation"], "vram_to_vram")
        self.assertEqual(transfer["dimensions"], [816,368,560,28,16,28])


if __name__ == "__main__":
    unittest.main()
