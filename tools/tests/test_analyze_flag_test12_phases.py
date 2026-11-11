#!/usr/bin/env python3
"""Synthetic tests only; no user game data or original ROM."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "analyze_flag_test12_phases.py"
spec = importlib.util.spec_from_file_location("test12_phase_reader", SCRIPT)
assert spec and spec.loader
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Test12PhaseAnalyzer(unittest.TestCase):
    def test_phase_diffs_are_evidence_only(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "captures.zip"
            first = bytearray(reader.VRAM_BYTES)
            second = first.copy()
            third = second.copy()
            word_offset = ((256 * 1024) + 832) * 2
            second[word_offset:word_offset + 2] = b"\x1A\x03"
            clut_offset = ((505 * 1024) + 0) * 2
            second[clut_offset:clut_offset + 2] = b"\x1A\x04"
            third[((300 * 1024) + 900) * 2] = 55
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("flag_prematch_00000100.vram", first)
                z.writestr("flag_field_00000200.vram", second)
                z.writestr("flag_field_00000300.vram", third)
                z.writestr("calibration/notes.json", "{}")
                z.writestr("gpu_probe_00000150.gpd", b"not decoded")
            labels = root / "labels.json"
            labels.write_text(json.dumps({"schemaVersion": 1, "captures": [
                {"snapshot": "flag_prematch_00000100.vram", "phase": "prematch_banner", "team": "Bosnia"},
                {"snapshot": "flag_field_00000200.vram", "phase": "carried_banner", "team": "Bosnia"},
                {"snapshot": "flag_field_00000300.vram", "phase": "crowd_flags", "team": "Bosnia"},
            ]}), encoding="utf-8")
            result = reader.analyze(archive, labels)
            self.assertEqual(result["vram_capture_count"], 3)
            self.assertEqual(result["gpu_trace_count"], 1)
            self.assertEqual(result["operator_labeled_count"], 3)
            self.assertEqual(result["transitions"][0]["changed_historical_64x28_flag_styles"], [0])
            self.assertEqual(result["transitions"][0]["changed_national_clut_indices"], [0])
            cells = result["transitions"][0]["grid_change_candidates"]["most_changed_cells"]
            self.assertTrue(any(x["x_word"] == 832 and x["y"] == 256 for x in cells))
            self.assertEqual(result["transitions"][1]["to_operator_phase"], "crowd_flags")
            self.assertTrue(any("NOT" in note for note in result["notes"]))

    def test_existing_academy_operator_capture_tags(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / "operator.zip"
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr(
                    "cal_test12_carried_banner_a1b2c3_00000100.vram",
                    bytes(reader.VRAM_BYTES),
                )
                z.writestr(
                    "cal_test12_crowd_flags_d4e5f6_00000200.vram",
                    bytes(reader.VRAM_BYTES),
                )
            result = reader.analyze(archive)
            self.assertEqual(result["operator_labeled_count"], 2)
            self.assertEqual(
                [x["operator_phase"] for x in result["captures"]],
                ["carried_banner", "crowd_flags"]
            )
            self.assertEqual(
                result["transitions"][0]["to_operator_phase"], "crowd_flags"
            )
            self.assertIn(
                "operator-tagged",
                result["captures"][0]["phase_evidence"],
            )

    def test_unknown_phase_without_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "capture.zip"
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("session/flag_field_00000090.vram", bytes(reader.VRAM_BYTES))
            result = reader.analyze(path)
            self.assertEqual(result["captures"][0]["operator_phase"], "unknown")
            self.assertEqual(result["transitions"], [])

    def test_reject_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("../dump.vram", bytes(reader.VRAM_BYTES))
            with self.assertRaisesRegex(ValueError, "Unsafe"):
                reader.analyze(path)

    def test_reject_mislabeled_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "valid.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("flag_field_00000090.vram", bytes(reader.VRAM_BYTES))
            labels = root / "labels.json"
            labels.write_text(json.dumps({"schemaVersion": 1, "captures": [
                {"snapshot":"flag_field_99999999.vram", "phase":"hud"}
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not present"):
                reader.analyze(path, labels)


if __name__ == "__main__":
    unittest.main()
