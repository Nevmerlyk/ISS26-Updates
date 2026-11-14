#!/usr/bin/env python3
"""Guard generated Test27 64x28 national textures before any game injection."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import test27_flag_art_4bpp as art
from analyze_flag_test26_unified import aligned_stage_mask_audit

class FlagResearchTests(unittest.TestCase):
    def test_both_flags_are_896_bytes_and_round_trip_4bpp(self):
        for name in ("bosnia", "cape_verde"):
            raw, clut, pixels, geometry = art.candidate(name)
            self.assertEqual(len(raw), 896)
            self.assertEqual(len(clut), 32)
            self.assertEqual(len(pixels), 64*28)
            self.assertEqual(art.unpack_4bpp(raw), pixels)
            self.assertTrue(all(x > 0 for x in pixels))
            self.assertTrue(geometry)

    def test_all_lower_rows_have_real_nonzero_art(self):
        # Directly counters Test26's observed 12-row zero mask.
        for name in ("bosnia", "cape_verde"):
            raw, _, _, _ = art.candidate(name)
            for y in range(16,28):
                self.assertTrue(any(raw[y*32:y*32+32]), (name,y))
                self.assertEqual(sum(v == 0 for v in
                                     art.unpack_4bpp(raw)[y*64:(y+1)*64]),0)

    def test_bosnia_diagonal_geometry_and_partial_stars(self):
        _, _, p, geometry = art.candidate("bosnia")
        self.assertEqual(geometry["star_count"], 9)
        self.assertEqual(geometry["partial_stars_at_y"], [0,28])
        self.assertEqual(len(geometry["star_centres_xy"]),9)
        self.assertEqual(p[27*64],1)        # lower-left blue
        self.assertEqual(p[0*64+63],2)      # upper-right yellow
        self.assertEqual(p[0*64],1)        # upper-left blue
        self.assertTrue(sum(x==3 for x in p)>12)  # white five-point stars

    def test_cape_verde_stripes_and_ten_stars(self):
        _, _, p, geometry = art.candidate("cape_verde")
        self.assertEqual(geometry["stars"],10)
        self.assertEqual(len(geometry["star_centres_xy"]),10)
        # At far-right away from the star circle, the stripes stay horizontal.
        col=63
        for y in range(28):
            expected=2 if y in (14,15,18,19) else 3 if y in (16,17) else 1
            self.assertEqual(p[y*64+col],expected)
        self.assertTrue(sum(x==4 for x in p)>=10)

    def test_palette_index_zero_is_reserved(self):
        for name in art.COLORS:
            clut=art.make_clut(art.COLORS[name])
            self.assertEqual(clut[:2],b"\x00\x00")
            self.assertTrue(any(clut[2:]))
        with self.assertRaises(ValueError):
            art.make_clut(tuple())
        with self.assertRaises(ValueError):
            art.bgr555((-1,0,0))

    def test_packing_detects_unexpected_length_and_index(self):
        with self.assertRaises(ValueError):
            art.pack_4bpp([1]*5)
        with self.assertRaises(ValueError):
            art.pack_4bpp([16]*(64*28))
        with self.assertRaises(ValueError):
            art.unpack_4bpp(b"bad")

    def test_test26_zero_mask_probe_reproduced_on_bosnia_art(self):
        source, _, _, _ = art.candidate("bosnia")
        stage=source[:16*32] + bytes(12*32)
        report=aligned_stage_mask_audit(stage,source)
        self.assertTrue(report["stage_is_zero_masked_source"])
        self.assertEqual(report["suppressed_source_nonzero_words"],192)
        self.assertEqual(report["suppressed_word_counts_by_row"],
                         [0]*16+[16]*12)
        self.assertEqual(report["suppressed_bbox_4bpp_pixels_xyxy"],
                         [0,16,63,27])
        # The synthetic all-opaque candidate need not have the exact 384
        # nonzero nibble count seen in the *real* Test25 unrelated atlas art.
        self.assertEqual(report["source_nonzero_4bpp_pixels_suppressed"],768)

    def test_candidate_is_not_a_game_patch(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            m=art.generate(base)
            self.assertFalse(m["can_install_into_game"])
            self.assertFalse(m["corrected_game_patch"])
            self.assertFalse(m["source_disc_modified"])
            self.assertFalse(m["game_update_feed_modified"])
            self.assertEqual(len(m["flags"]),2)
            self.assertEqual(m["tile_bytes"],896)
            for name in m["flags"]:
                raw=(base/f"{name}_64x28_4bpp.bin").read_bytes()
                self.assertEqual(art.hash_bytes(raw),
                                 m["flags"][name]["bitmap_sha256"])
                self.assertEqual((base/f"{name}_clut_bgr555.bin").stat().st_size,32)
                ppm=(base/f"{name}_8x_preview.ppm").read_bytes()
                self.assertTrue(ppm.startswith(b"P6\n512 224\n255\n"))
                self.assertEqual(len(ppm),len(b"P6\n512 224\n255\n")+512*224*3)

if __name__=="__main__":
    unittest.main()
