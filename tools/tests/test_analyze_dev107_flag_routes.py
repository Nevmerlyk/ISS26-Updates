import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analyze_dev107_flag_routes import rect, common_clut
class Routes(unittest.TestCase):
    def test_vram_sizes(self):
        for n in (1048576,2097152):
            data=bytearray(n)
            for y in range(98,106):
                at=2*(1024*y+640)
                data[at:at+12]=b"\xab"*12
            self.assertEqual(rect(data,640,98,6,8),b"\xab"*96)
            self.assertEqual(rect(data,646,98,6,8),bytes(96))
        with self.assertRaises(ValueError):rect(bytes(1),0,0,1,1)
    def test_common(self):
        sample={"gpu":{"surfaces":{
            "home_large":[{"clut":[224,506],"contained":True}],
            "home_hud":[{"clut":[224,506],"contained":True}],
            "away_large":[{"clut":[176,506],"contained":True}],
            "away_hud":[{"clut":[176,506],"contained":True}]}}}
        self.assertTrue(common_clut([sample],"home")["unique_shared_route"])
        self.assertTrue(common_clut([sample],"away")["unique_shared_route"])
        sample["gpu"]["surfaces"]["home_hud"].append({"clut":[0,505],"contained":True})
        self.assertFalse(common_clut([sample],"home")["unique_shared_route"])
        self.assertFalse(common_clut([],"home")["unique_shared_route"])
if __name__=="__main__":unittest.main()
