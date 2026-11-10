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
            # Style 10: xword 864 y 320; touch the first texel.
            px = ((256 + 32 * (10 // 4)) * 1024 + 832 + 16 * (10 % 4)) * 2
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
