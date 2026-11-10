import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from palette_multiplex import (
    FLAG_NATION_INDEX, COUNTRY_TO_STYLE, PROPOSED_STYLE_GROUPS,
    PROTECTED_ORIGINAL_FLAG_SLOTS, compile_style, pack_4bpp,
    validate_national_scope,
)

SIZES = ((64, 28), (24, 16), (24, 8))

def fixture(expression):
    return {
        (w, h): tuple(expression(x, y, w, h)
                      for y in range(h) for x in range(w))
        for w, h in SIZES
    }

class PaletteMultiplexTests(unittest.TestCase):
    def test_reverse_flag_index_does_not_change_national_names(self):
        expected = {
            "cabo_verde": 0, "algeria": 1, "ivory_coast": 3,
            "ghana": 17, "dr_congo": 19, "haiti": 22,
            "curacao": 24, "jordan": 25, "iraq": 26,
            "new_zealand": 27, "bosnia": 30, "senegal": 35,
            "canada": 39, "ecuador": 42, "panama": 43,
            "uzbekistan": 49, "qatar": 51
        }
        self.assertEqual(FLAG_NATION_INDEX, expected)
        for country, rev_slot in expected.items():
            name_slot = 53 - rev_slot
            self.assertGreaterEqual(name_slot, 0)
            self.assertLess(name_slot, 54)
        self.assertEqual(len(COUNTRY_TO_STYLE), 16)
        self.assertNotIn('senegal', COUNTRY_TO_STYLE)

    def test_exact_17_country_scope_and_preserved_37(self):
        validate_national_scope(COUNTRY_TO_STYLE,
                                PROTECTED_ORIGINAL_FLAG_SLOTS)
        with self.assertRaises(ValueError):
            validate_national_scope({"bosnia": 10},
                                    PROTECTED_ORIGINAL_FLAG_SLOTS)
        with self.assertRaises(ValueError):
            validate_national_scope(COUNTRY_TO_STYLE, {})

    def test_preserve_existing_flags_while_adding_new_country(self):
        # Style 8 has three original unaffected nations, plus proposed Cabo
        # Verde. Each country-specific CLUT must reproduce its OWN original.
        preserved = {
            "flag12": fixture(lambda x,y,w,h: 0x1122 if x < w//2 else 0x4231),
            "flag18": fixture(lambda x,y,w,h: 0x2222 if y < h//2 else 0x3333),
            "flag29": fixture(lambda x,y,w,h: 0x1111 if (x+y)%2 else 0x2100),
        }
        new = {
            "cabo_verde": fixture(lambda x,y,w,h: 0x0034 if y < h//2 else 0x7fff)
        }
        # Here the alternating third protected nation introduces 8 tuples,
        # well under 15, regardless of resolution.
        m = compile_style(8, new, preserved)
        self.assertEqual(m.protected_names,
                         ("flag12", "flag18", "flag29"))
        self.assertLessEqual(m.unique_color_tuples, 15)
        self.assertEqual(m.palettes["cabo_verde"][0], 0)
        for dim in SIZES:
            pixels = m.indices_by_size[dim]
            self.assertEqual(len(pack_4bpp(pixels, dim)), dim[0]*dim[1]//2)
            for name, original in dict(preserved, **new).items():
                result = tuple(m.palettes[name][index] for index in pixels)
                self.assertEqual(result, original[dim], name)

    def test_shared_template_with_four_independent_flags(self):
        new = {
            "ghana": fixture(lambda x,y,w,h: 1 + 3*y//h),
            "jordan": fixture(lambda x,y,w,h: 8 if x < w//3 else 2),
            "iraq": fixture(lambda x,y,w,h: 4 if y > h//2 else 6),
            "qatar": fixture(lambda x,y,w,h: 3 if x > w//4 else 7),
        }
        m = compile_style(24, new, {})
        self.assertLessEqual(m.unique_color_tuples, 15)
        self.assertEqual(set(m.palettes), set(new))
        self.assertNotIn(0, m.indices_by_size[(64,28)])

    def test_16th_nontransparent_color_is_refused(self):
        # Deliberately construct sixteen distinct pairs of colors.
        a = fixture(lambda x,y,w,h: 1 + (x%4))
        b = fixture(lambda x,y,w,h: 1 + ((x//4)%4))
        with self.assertRaises(ValueError):
            compile_style(10, {"a": a, "b": b}, {})

    def test_no_high_unsupported_style_or_transparent_display_pixels(self):
        with self.assertRaises(ValueError):
            compile_style(55, {"a": fixture(lambda *a: 1)}, {})
        with self.assertRaises(ValueError):
            pack_4bpp(bytes([0]) * (64*28), (64,28))

if __name__ == "__main__":
    unittest.main()
