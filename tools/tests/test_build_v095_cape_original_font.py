"""Original-game-font Cape 4bpp candidate: no copyrighted assets in CI."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_v095_cape_original_font import (
    compose, pack4, preview, GLYPHS, ATLAS_W,ATLAS_H
)

class TestCapeOriginalFont(unittest.TestCase):
    def test_62px_word_from_four_authentic_glyph_windows(self):
        arr=bytearray(ATLAS_W*ATLAS_H)
        for i,g in enumerate(GLYPHS):
            arr[(g["y"]+3)*ATLAS_W +g["x"]+g["start"]+4]=i+4
        result,width=compose(bytes(arr))
        self.assertEqual(width,62)
        self.assertEqual(len(result),16*62)
        self.assertEqual(set(result),{0,4,5,6,7})
    def test_4bpp_nibble_order(self):
        data=bytes([0,1,2,15]*8)
        self.assertEqual(pack4(data,2),bytes([0x10,0xF2]*8))
    def test_png_without_third_party_dependencies(self):
        png=preview(bytes([0,6]*16),2)
        self.assertEqual(png[:8],bytes.fromhex("89504e470d0a1a0a"))
        self.assertIn(b"IDAT",png)
    def test_bad_source_dimensions_rejected(self):
        with self.assertRaises(ValueError):compose(bytes(100))
        with self.assertRaises(ValueError):pack4(bytes(16),3)
if __name__=="__main__":unittest.main()
