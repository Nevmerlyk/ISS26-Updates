import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test28_restore_selection_assets import merged_pixels
class MergeTests(unittest.TestCase):
    def test_preserves_cape_and_bosnia_intersection_even_on_conflicting_donor(self):
        u=SimpleNamespace(x=832,y=256,w=32,h=128)
        a=bytes(8192); b=bytearray(a); d=bytearray(a)
        b[32:64]=bytes([3])*32; d[:64]=bytes([7])*64
        c=merged_pixels(a,b,d,u)
        self.assertEqual(c[:32],bytes([7])*32)
        self.assertEqual(c[32:64],bytes([3])*32)
    def test_preserves_current_nonflag_changes(self):
        u=SimpleNamespace(x=0,y=0,w=2,h=1)
        self.assertEqual(merged_pixels(b"0000",b"1000",b"0200",u),b"1200")
    def test_rejects_conflict(self):
        u=SimpleNamespace(x=0,y=0,w=2,h=1)
        with self.assertRaisesRegex(ValueError,"Conflicting"):
            merged_pixels(b"0000",b"1000",b"2000",u)
    def test_rejects_short_packet(self):
        u=SimpleNamespace(x=0,y=0,w=2,h=1)
        with self.assertRaisesRegex(ValueError,"Incomplete"):
            merged_pixels(b"0000",b"0000",b"00",u)
if __name__=="__main__": unittest.main()
