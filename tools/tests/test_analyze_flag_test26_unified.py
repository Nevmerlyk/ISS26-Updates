#!/usr/bin/env python3
"""Synthetic Test26 regressions. No original PS1 graphics or BIOS."""
from __future__ import annotations

import importlib.util
import json
import struct
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import analyze_flag_test26_unified as tool
import parse_v095_gpudump as gpu


def overwrite(raw: bytearray, x: int, y: int, val: int) -> None:
    for j in range(tool.STYLE_ROWS):
        at = ((y + j) * 1024 + x) * 2
        raw[at:at+32] = bytes([val]) * 32


def put_style(raw: bytearray, style: int, val: int) -> None:
    overwrite(raw, *tool.atlas_xy(style), val)


def make_two_phase_archive(path: Path) -> None:
    a = bytearray(tool.VRAM_BYTES)
    put_style(a, 1, 0x11)
    put_style(a, 10, 0x10)
    put_style(a, 55, 0x55)
    overwrite(a, 560, 0, 0x11)
    overwrite(a, 560, 28, 0x55)
    b = bytearray(a)
    put_style(b, 55, 0x66)
    overwrite(b, 560, 28, 0x66)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("cal_test12_prematch_banner_abcdef_00000100.vram", a)
        z.writestr("cal_test12_carried_banner_abcdef_00000200.vram", b)
        z.writestr("frame_00000200.screen.raw", b"screen pixels (opaque metadata)")
        def pkt(kind, *values):
            return struct.pack("<I", (kind << 24) | len(values)) + (
                struct.pack("<" + str(len(values)) + "I", *values) if values else b""
            )
        quad = (0x3CFFFFFF, 0, (505 << 22) | 192,
                0xFFFFFF, 1, (8 << 16) | 255,
                0xFFFFFF, 0x00010001, (27 << 8) | 255,
                0xFFFFFF, 0x00010000, (27 << 8) | 192)
        dump = gpu.MAGIC + pkt(gpu.TRACE_BEGIN) + pkt(gpu.GP0, *quad)
        z.writestr("flag_00000100.gpd", dump)


class Test26UnifiedFlagProvenance(unittest.TestCase):
    def test_verified_style_bank_coordinates(self):
        self.assertEqual(tool.atlas_xy(0), (832, 256))
        self.assertEqual(tool.atlas_xy(1), (848, 256))
        self.assertEqual(tool.atlas_xy(10), (864, 312))
        self.assertEqual(tool.atlas_xy(35), (880, 480))
        self.assertEqual(tool.atlas_xy(36), (768, 256))
        self.assertEqual(tool.atlas_xy(55), (816, 368))
        self.assertEqual(tool.atlas_xy(71), (816, 480))
        for val in (-1, 72, 80):
            with self.assertRaises(ValueError):
                tool.atlas_xy(val)

    def test_realistic_test25_stage_and_phase_handoff(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "synthetic.zip"
            make_two_phase_archive(path)
            result = tool.analyze_archive(path)
            self.assertEqual(result["style_count"], 72)
            self.assertEqual(result["capture_count"], 2)
            self.assertEqual(result["gpu_trace_count"], 1)
            self.assertEqual(result["gpu_trace_decoded_count"], 0)
            self.assertEqual(result["gpu_dumps_inventory_only"][0]["operator_phase"], "unknown")
            self.assertEqual(result["gpu_trace_decoded_count"], 1)
            self.assertEqual(result["gpu_dumps_inventory_only"][0]["decoded_gp0"]
                             ["top_draw_groups"][0]["source_min_xy_words"], [560, 0])
            self.assertEqual(result["screenshot_file_count"], 1)
            first, second = result["captures"]
            self.assertEqual(first["staging"]["home"]["matching_style_ids"], [1])
            self.assertEqual(first["staging"]["away"]["matching_style_ids"], [55])
            self.assertEqual(second["staging"]["away"]["matching_style_ids"], [55])
            self.assertEqual(first["reference_styles"]["bosnia_test25"]["atlas_xy_words"],
                             [816, 368])
            self.assertEqual(result["transitions"][0]["changed_atlas_style_ids"], [55])
            self.assertEqual(result["transitions"][0]["changed_staging"]["away"], True)
            self.assertEqual(result["transitions"][0]["changed_staging"]["home"], False)
            self.assertEqual(result["operator_phase_coverage"]["prematch_banner"]
                             ["operator_tagged_vram_captures"], 1)
            self.assertEqual(result["operator_phase_coverage"]["carried_banner"]
                             ["operator_tagged_vram_captures"], 1)
            self.assertFalse(result["operator_phase_coverage"]["carried_banner"]
                             ["verified_gpu_draw_ownership"])

    def test_crowd_phase_requires_human_label_and_does_not_claim_gpu_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            zip_path = root / "unknown.zip"
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("guess_crowd_00000100.vram", bytes(tool.LEGACY_VRAM_BYTES))
            result = tool.analyze_archive(zip_path)
            self.assertEqual(result["captures"][0]["operator_phase"], "unknown")
            self.assertEqual(result["operator_phase_coverage"]["crowd_flags"]
                             ["operator_tagged_vram_captures"], 0)
            labels = root / "phases.json"
            labels.write_text(json.dumps({
                "schemaVersion": 1,
                "captures": [{"snapshot":"guess_crowd_00000100.vram",
                              "phase":"crowd_flags","team":"Bosnia"}]
            }), encoding="utf-8")
            result = tool.analyze_archive(zip_path, labels)
            self.assertEqual(result["capture_count"], 1)
            self.assertEqual(result["captures"][0]["operator_phase"], "crowd_flags")
            self.assertFalse(result["operator_phase_coverage"]["crowd_flags"]
                             ["verified_gpu_draw_ownership"])
            self.assertEqual(result["transitions"], [])

    def test_reject_unsafe_archive_and_duplicate_snapshot_name(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("../escape.vram", bytes(tool.LEGACY_VRAM_BYTES))
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                tool.analyze_archive(p)
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("a/double_00000100.vram", bytes(tool.LEGACY_VRAM_BYTES))
                z.writestr("b/double_00000100.vram", bytes(tool.LEGACY_VRAM_BYTES))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                tool.analyze_archive(p)

    def test_reject_missing_operator_label(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            archive = root / "capture.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("snap_00000100.vram", bytes(tool.LEGACY_VRAM_BYTES))
            labels = root / "labels.json"
            labels.write_text(json.dumps({
                "schemaVersion": 1,
                "captures": [{"snapshot":"absent_00000100.vram",
                              "phase":"crowd_flags"}]
            }))
            with self.assertRaisesRegex(ValueError, "not in ZIP"):
                tool.analyze_archive(archive, labels)

    def test_invalid_vram_size_and_coordinate_bounds(self):
        with tempfile.TemporaryDirectory() as td:
            archive = Path(td) / "invalid.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("small_00000100.vram", bytes(400))
            with self.assertRaisesRegex(ValueError, "Invalid VRAM"):
                tool.analyze_archive(archive)
            with self.assertRaises(ValueError):
                tool.tile(bytes(tool.LEGACY_VRAM_BYTES), 1020, 480)
            with self.assertRaises(ValueError):
                tool.clut(bytes(tool.LEGACY_VRAM_BYTES), 1010, 505)


if __name__ == "__main__":
    unittest.main()
