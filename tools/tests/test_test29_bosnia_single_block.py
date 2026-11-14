import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test29_bosnia_single_block as t
from test_test28_stage3_resources import resource
from test28_stage3_resources import packet_map,exact_packet
from test27_gpu_stream_edit import fragment_read
BASE=0x800C8000
class Test29(unittest.TestCase):
    def test_candidate_coordinates(self):
        self.assertEqual(t.xy(55),(816,368))
        self.assertEqual([t.xy(x) for x in t.CANDIDATES],[(768,284),(784,284),(800,284)])
    def test_five_maps_and_club_collision(self):
        table=bytearray([2]*78)
        table[0]=1;table[30]=55;table[54]=10
        maps=[bytes(table)]*5
        self.assertTrue(t.free_style(maps,40))
        table[75]=40
        self.assertFalse(t.free_style(maps[:4]+[bytes(table)],40))
    def test_actual_packet_relocation(self):
        raw=resource([(768,256,32,128,None,None,None)])
        art=bytes([0x41])*896
        out,info=t.relocate_resource(raw,raw,BASE,40,art)
        self.assertEqual(info["writers"],1)
        for table,slot,rows,u in packet_map(out,BASE):
            decoded,_=exact_packet(out,BASE,table,rows,u)
            self.assertEqual(fragment_read(decoded,u,t.rect(40)),art)
        self.assertEqual(len(raw),len(out))
    def test_boundary_rejected(self):
        raw=resource([(768,256,32,40,None,None,None)])
        with self.assertRaisesRegex(ValueError,"boundary"):
            t.relocate_resource(raw,raw,BASE,40,bytes(896))
    def test_changed_destination_rejected(self):
        raw=resource([(768,256,32,128,None,None,None)])
        art=bytes([0x41])*896
        out,_=t.relocate_resource(raw,raw,BASE,40,art)
        with self.assertRaisesRegex(ValueError,"already modified"):
            t.relocate_resource(raw,out,BASE,40,art)
if __name__=="__main__": unittest.main()
