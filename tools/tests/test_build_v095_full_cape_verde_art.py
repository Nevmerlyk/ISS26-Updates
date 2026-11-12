"""Synthetic + opt-in clean-disc regression tests of original-font Cape Verde."""
import hashlib,os,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build_v095_full_cape_verde_art import GLYPHS,compose_word,place_4bpp_word,build
import v095_cape_verde_sprite_layout as layout
pixel=getattr(layout,"value",None) or layout.pixel
DISC=Path(os.environ.get("ISS26_CLEAN_TRACK01","__missing_original__"))

class CapeVerdeArtTests(unittest.TestCase):
    def test_five_glyph_sources_and_62px_word(self):
        self.assertEqual("".join(g[0] for g in GLYPHS),"Verde")
        pixels=bytearray(1792*256)
        for i,(_,_,ax,ay,start,stop) in enumerate(GLYPHS):
            pixels[(ay+5)*1792+ax+start+6]=i+1
        result,width=compose_word(bytes(pixels))
        self.assertEqual(width,62)
        self.assertEqual(len(result),width*16)
        # Both e glyphs share the same original source, last write wins.
        self.assertTrue(set(result).issuperset({0,1,3,4,5}))
    def test_exact_4bpp_nibble_order_and_bounds(self):
        source=bytes([1,2,3,4])*8
        packed=place_4bpp_word(source,2,88)
        self.assertEqual(len(packed),704)
        self.assertEqual([pixel(packed,88,x,y) for y in range(2) for x in range(2)],
                         [1,2,3,4])
        with self.assertRaises(ValueError):
            place_4bpp_word(bytes(90*16),90,88)
    @unittest.skipUnless(DISC.is_file(),"Set ISS26_CLEAN_TRACK01 to run real-disc test")
    def test_original_disc_is_unchanged_and_output_within_screen_rectangles(self):
        original_hash=hashlib.file_digest(DISC.open("rb"),"sha256").hexdigest()
        with tempfile.TemporaryDirectory() as temp:
            dst=Path(temp)
            report=build(DISC,dst)
            self.assertEqual((report["cape_width_px"],report["verde_width_px"]),(62,62))
            self.assertFalse(report["layout"]["draw_positions_modified"])
            self.assertEqual(report["layout"]["new_word_gap_px"],7)
            self.assertTrue(report["layout"]["second_sprite_has_nonzero_pixels"])
            self.assertEqual(len((dst/"ISS26_CapeVerde_sprite_left_4bpp.bin").read_bytes()),1024)
            self.assertEqual(len((dst/"ISS26_CapeVerde_sprite_right_4bpp.bin").read_bytes()),704)
            self.assertEqual((dst/"ISS26_CapeVerde_original_font_layout.png").read_bytes()[:8],
                             bytes.fromhex("89504e470d0a1a0a"))
        self.assertEqual(hashlib.file_digest(DISC.open("rb"),"sha256").hexdigest(),
                         original_hash)

if __name__=="__main__":
    unittest.main()
