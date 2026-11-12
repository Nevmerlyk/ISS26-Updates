"""No game data needed: 4bpp Cape Verde screen-rectangle layout regressions."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v095_cape_verde_sprite_layout import recompose,set_pixel,pixel

def rectangle(w,start,length,top=0,color=4):
    data=bytearray(w*16//2)
    for y in range(top,top+10):
        for x in range(start,start+length):
            set_pixel(data,w,x,y,color)
    return bytes(data)

class LayoutTest(unittest.TestCase):
    def test_gap_72_is_removed_inside_original_draw_rectangles(self):
        cape=rectangle(58,0,57)
        verde=rectangle(88,3,62)
        left,right,report=recompose(cape,58,verde,space_px=7)
        self.assertEqual((len(left),len(right)),(1024,704))
        self.assertEqual(report["screen_draw_x"],[24,152])
        self.assertEqual(report["first_ink_screen_x"],26)
        self.assertEqual(report["last_ink_screen_x"],151)
        self.assertFalse(report["second_sprite_nonempty"])
        self.assertFalse(report["draw_positions_modified"])
        self.assertEqual(pixel(left,128,66,0),4)
        for x in range(59,66):self.assertEqual(pixel(left,128,x,0),0)
    def test_overflow_spills_into_second_sprite_without_move(self):
        left,right,d=recompose(rectangle(64,0,64),64,rectangle(88,3,62),space_px=8)
        self.assertTrue(d["second_sprite_nonempty"])
        self.assertEqual(d["last_ink_screen_x"],159)
        self.assertEqual(pixel(right,88,0,0),4)
    def test_preserve_verde_palette_nibbles(self):
        verde=bytearray(88*16//2)
        for y in range(16):
            for x in range(3,65):
                set_pixel(verde,88,x,y,1+(x+y)%15)
        left,right,_=recompose(rectangle(58,0,57),58,bytes(verde))
        for y in range(16):
            for x in range(62):
                self.assertEqual(pixel(left,128,66+x,y),pixel(verde,88,x+3,y))
    def test_empty_or_wrong_width_rejected(self):
        with self.assertRaises(ValueError):
            recompose(bytes(58*8),58,rectangle(88,3,62))
        with self.assertRaises(ValueError):
            recompose(rectangle(58,0,57),58,rectangle(88,3,62),space_px=72)
if __name__=="__main__":unittest.main()
