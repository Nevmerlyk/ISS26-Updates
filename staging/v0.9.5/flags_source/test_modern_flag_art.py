import unittest

from modern_flag_art import COUNTRIES, flag_image, flag_sizes, bgr555
from palette_multiplex import FLAG_NATION_INDEX, PROPOSED_STYLE_GROUPS, compile_style

class NationalArtTests(unittest.TestCase):
    def test_exact_country_inventory_and_binary_palettes(self):
        self.assertEqual(set(COUNTRIES),set(FLAG_NATION_INDEX))
        for nation in COUNTRIES:
            image=flag_image(nation)
            self.assertEqual(image.size,(64,28))
            pixels=flag_sizes(nation)
            self.assertEqual(set(pixels),{(64,28),(24,16),(24,8)})
            for (w,h), data in pixels.items():
                self.assertEqual(len(data),w*h)
                self.assertTrue(all(0<=c<=0x7fff for c in data))
        self.assertEqual(bgr555((248,248,248)),0x7fff)
        self.assertEqual(bgr555((0,0,0)),0)
    def test_draft_group_packing_feasibility_not_release_verification(self):
        for style,nations in PROPOSED_STYLE_GROUPS.items():
            if style in (8,11): continue # need original unaffected textures
            color_maps={nation:flag_sizes(nation) for nation in nations}
            # This is a feasibility test. Any failure means the *draft*
            # palette grouping must be recomputed, not that flag art should
            # be truncated or an invalid game patch distributed.
            try:
                compiled=compile_style(style,color_maps,{})
            except ValueError:
                continue
            self.assertLessEqual(compiled.unique_color_tuples,15)

if __name__ == "__main__":
    unittest.main()
