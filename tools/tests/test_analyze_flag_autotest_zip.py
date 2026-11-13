import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "flagzip", ROOT / "analyze_flag_autotest_zip.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class AutoTestFlagReports(unittest.TestCase):
    def test_style_overwrite_and_clut_changes(self):
        with tempfile.TemporaryDirectory() as t:
            root = pathlib.Path(t)
            report = root / "sample.zip"
            first = bytearray(module.VRAM_SIZE)
            second = bytearray(first)
            # Style 10: xword 864 y 312; touch the first texel (28-row stride).
            px = ((256 + 28 * (10 // 4)) * 1024 + 832 + 16 * (10 % 4)) * 2
            second[px] = 0x21
            # Bosnia CLUT index 30 uses x 480, y 505
            clut = (505 * 1024 + 16 * 30) * 2
            second[clut + 2:clut + 4] = b"\x1f\x00"
            task = {"id": "iss26-flags-gpu-provenance", "revision": 1}
            with zipfile.ZipFile(report, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("autotest-task.json", json.dumps(task))
                z.writestr("vram_probe_100_100.vram", first)
                z.writestr("vram_probe_200_200.vram", second)
                z.writestr("gpu_probe_120.gpd", b"FAKE-GPU")
            analysis = module.analyze(report, root / "out")
            self.assertEqual(analysis["vram_capture_count"], 2)
            self.assertEqual(analysis["gpu_trace_count"], 1)
            self.assertEqual(len(analysis["bosnia_style10_overwrite_transitions"]), 1)
            self.assertTrue(any(x["reverse_flag_index"] == 30
                                for x in analysis["clut_changes"]))
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "style_changes.csv").exists())
            self.assertTrue((root / "out" / "vram_probe_200_200_bosnia_reference.ppm").exists())
            self.assertEqual(module.palette(second, 30)[1], 31)

    def test_modern_vram_prematch_copy_and_real_gpu_cluts(self):
        with tempfile.TemporaryDirectory() as t:
            root = pathlib.Path(t)
            report = root / "modern.zip"
            first = bytearray(module.MODERN_VRAM_SIZE)
            cape_atlas = ((256 * 1024) + 848) * 2
            cape_draw = (560 * 2)
            bosnia_atlas = ((312 * 1024) + 864) * 2
            bosnia_draw = ((28 * 1024) + 560) * 2
            first[cape_atlas] = 0x21
            first[cape_draw] = 0x21
            first[bosnia_atlas] = 0x34
            first[bosnia_draw] = 0x34
            # Actual prematch CLUT for Bosnia is (224,506); not the
            # historical "national reverse flag index 30" probe.
            clut = ((506 * 1024) + 224) * 2
            first[clut + 2:clut + 4] = b"\\x1f\\x00"
            second = bytearray(first)
            second[bosnia_draw] = 0x53  # new upload overwrites drawn tile
            with zipfile.ZipFile(report, "w", compression=zipfile.ZIP_DEFLATED) as z:
                z.writestr("autotest-task.json", '{"id":"iss26-flags-gpu-provenance"}')
                z.writestr("capture_000001.vram", first)
                z.writestr("capture_000002.vram", second)
            scan = module.analyze(report, root / "out")
            self.assertEqual(scan["vram_capture_count"], 2)
            a, b = scan["snapshots"]
            self.assertEqual(a["vram_layout"], "2MB")
            self.assertEqual(a["prematch_flags"]["cape_dest_equals_atlas"], True)
            self.assertEqual(a["prematch_flags"]["bosnia_dest_equals_atlas"], True)
            self.assertEqual(b["prematch_flags"]["bosnia_dest_equals_atlas"], False)
            self.assertIn(3, a["prematch_flags"]["bosnia_nontransparent_zero_clut_indices"])
            self.assertTrue((root / "out" / "capture_000002_prematch_bosnia_reference.ppm").exists())
            saved = json.loads((root / "out" / "summary.json").read_text())
            self.assertNotIn("prematch_bosnia_index", saved["snapshots"][0])
            self.assertEqual(module.tile_index_bytes(first, 10)[0], 0x34)
            self.assertEqual(module.gpu_clut(first, 224, 506)[1], 31)

    def test_malformed_and_unsafe_reports(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / "unsafe.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("../escape.vram", bytes(200))
            with self.assertRaises(ValueError):
                module.scan(p)
            with self.assertRaises(ValueError):
                module.tile_index_bytes(b"", 10)
            with self.assertRaises(ValueError):
                module.palette(bytes(module.VRAM_SIZE), -1)

if __name__ == "__main__":
    unittest.main()
