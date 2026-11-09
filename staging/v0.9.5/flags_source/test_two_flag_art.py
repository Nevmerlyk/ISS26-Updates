"""Focused regression tests for two-country national 4bpp artwork."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from two_flag_art import (
    BOSNIA_CLUT, CLUT_SLOTS, NAME_SLOTS, LARGE_STYLES,
    blit_onto_gpu_upload, flag_pixels, large_style_vram, pack_4bpp,
)

CAPE_PALETTE_TEST = {"blue": 1, "white": 2, "red": 3, "yellow": 4}


class FlagGraphicsTests(unittest.TestCase):
    def test_country_slot_inversion(self):
        self.assertEqual(NAME_SLOTS["bosnia"] + CLUT_SLOTS["bosnia"], 53)
        self.assertEqual(NAME_SLOTS["cabo_verde"] + CLUT_SLOTS["cabo_verde"], 53)
        self.assertEqual(large_style_vram(LARGE_STYLES["bosnia"]), (864, 320))
        self.assertEqual(large_style_vram(LARGE_STYLES["cabo_verde"]), (848, 256))

    def test_palette_validation(self):
        with self.assertRaises(ValueError):
            flag_pixels("bosnia", 64, 28, {"blue": 0, "yellow": 2, "white": 3})
        with self.assertRaises(ValueError):
            flag_pixels("bosnia", 64, 28, {"blue": 1, "yellow": 1, "white": 3})
        with self.assertRaises(ValueError):
            flag_pixels("cabo_verde", 64, 28, BOSNIA_CLUT)

    def test_bosnia_triangle_and_star_row(self):
        p = flag_pixels("bosnia", 64, 28, BOSNIA_CLUT)
        self.assertEqual(len(p), 64 * 28)
        self.assertEqual(p[1 * 64 + 2], BOSNIA_CLUT["blue"])
        self.assertEqual(p[1 * 64 + 50], BOSNIA_CLUT["yellow"])
        self.assertEqual(p[23 * 64 + 59], BOSNIA_CLUT["yellow"])
        self.assertGreater(p.count(BOSNIA_CLUT["white"]), 8)
        self.assertGreater(p.count(BOSNIA_CLUT["yellow"]), 150)

    def test_cabo_verde_stripes_and_ten_stars(self):
        p = flag_pixels("cabo_verde", 64, 28, CAPE_PALETTE_TEST)
        def at(x, y):
            return p[y * 64 + x]
        self.assertEqual(at(62, 0), CAPE_PALETTE_TEST["blue"])
        self.assertEqual(at(62, 14), CAPE_PALETTE_TEST["white"])
        self.assertEqual(at(62, 17), CAPE_PALETTE_TEST["red"])
        self.assertEqual(at(62, 19), CAPE_PALETTE_TEST["white"])
        self.assertEqual(at(62, 27), CAPE_PALETTE_TEST["blue"])
        self.assertGreater(p.count(CAPE_PALETTE_TEST["yellow"]), 10)

    def test_all_three_flag_sizes_roundtrip_layout(self):
        for w, h in ((64, 28), (24, 16), (24, 8)):
            for country, palette in (
                ("bosnia", BOSNIA_CLUT),
                ("cabo_verde", CAPE_PALETTE_TEST),
            ):
                p = flag_pixels(country, w, h, palette)
                packed = pack_4bpp(p, w, h)
                self.assertEqual(len(packed), w * h // 2)
                recovered = bytearray()
                for b in packed:
                    recovered.extend((b & 15, b >> 4))
                self.assertEqual(bytes(recovered), p)

    def test_bounded_gpu_edit_preserves_padding_and_other_tiles(self):
        # 64x32 slot: 64x28 visible flag and 4 untouched bottom rows.
        baseline = bytes([0x77]) * (16 * 2 * 32)
        p = flag_pixels("bosnia", 64, 28, BOSNIA_CLUT)
        result, changed = blit_onto_gpu_upload(
            baseline, 864, 320, 16, 32, 864, 320, 64, 28, p,
        )
        self.assertGreater(changed, 0)
        self.assertEqual(result[28 * 32:], baseline[28 * 32:])
        self.assertEqual(result[:64 * 28 // 2], pack_4bpp(p, 64, 28))
        self.assertEqual(len(result), len(baseline))

    def test_partial_intersection_edits_only_overlap(self):
        p = flag_pixels("cabo_verde", 64, 28, CAPE_PALETTE_TEST)
        baseline = bytes([0x55]) * (16 * 2 * 32)
        # Upload starts halfway across the actual flag; no y offset.
        result, changed = blit_onto_gpu_upload(
            baseline, 856, 256, 16, 32, 848, 256, 64, 28, p,
        )
        self.assertGreater(changed, 0)
        self.assertEqual(result[28 * 32:], baseline[28 * 32:])
        self.assertEqual(result[0:16], pack_4bpp(p, 64, 28)[16:32])

    def test_no_intersection_is_idempotent(self):
        p = flag_pixels("bosnia", 64, 28, BOSNIA_CLUT)
        baseline = bytes([0x55]) * (16 * 2 * 32)
        result, count = blit_onto_gpu_upload(
            baseline, 50, 50, 16, 32, 864, 320, 64, 28, p,
        )
        self.assertEqual(result, baseline)
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
