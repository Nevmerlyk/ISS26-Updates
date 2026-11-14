import struct
import random
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test28_stage3_resources import repair_stadium, duplicate_selection, put_fragment, get_fragment
from test27_gpu_stream_edit import TARGETS
from v095_name_lz_codec import encode_stream
BASE=0x800C8000

def resource(rects,base=BASE):
    rng=random.Random(28)
    b=bytearray(32)
    packets=[]
    for x,y,w,h,flag,box,tile in rects:
        raw=bytearray(rng.randrange(256) for _ in range(2*w*h))
        if flag:
            gx,gy,gw,gh=box
            data=get_fragment(tile,flag,box)
            for yy in range(gh):
                pos=2*((gy-y+yy)*w+gx-x)
                raw[pos:pos+2*gw]=data[yy*2*gw:(yy+1)*2*gw]
        at=len(b)
        packed=encode_stream(bytes(raw),expected_bytes=len(raw))
        b.extend(packed); b.extend(bytes((-len(b))%4))
        packets.append((x,y,w,h,at))
    table=len(b)
    struct.pack_into("<I",b,0,base+table)
    for x,y,w,h,at in packets:
        b.extend(struct.pack("<HHHHHHI",10,x,y,w,h,0,base+at))
    b.extend(struct.pack("<H",255)+bytes(14))
    return bytes(b)

class Stage3Tests(unittest.TestCase):
    def setUp(self):
        r=random.Random(29)
        self.old={k:bytes(r.randrange(256) for _ in range(896)) for k in TARGETS}
        self.new={k:bytes([i+1])*896 for i,k in enumerate(TARGETS)}
    def fixture(self,wrong=False,incomplete=False):
        c=self.old["cape_verde"]; b=self.old["bosnia"]
        r=[(848,256,16,28,"cape_verde",(848,256,16,28),c),
           (816,368,16,16,"bosnia",(816,368,16,16),b)]
        if not incomplete:
            r.append((816,384,16,12,"bosnia",(816,384,16,12),b))
            r.append((816,384,16,12,"bosnia",(816,384,16,12),bytes(896) if wrong else b))
        return resource(r)
    def run_fixture(self,**kw):
        original=self.fixture(**kw)
        after,info=repair_stadium(original,original,self.new,{k:[v] for k,v in self.old.items()})
        return original,after,info
    def test_matching_overlap_repairs_all_writers(self):
        old,after,info=self.run_fixture()
        self.assertEqual(set(info["fixed_flags"]),set(TARGETS))
        self.assertEqual(len(info["edits"]),4)
        self.assertNotEqual(old,after)
        self.assertFalse(info["blocked"])
    def test_unknown_overlap_does_not_partially_edit_bosnia(self):
        old,after,info=self.run_fixture(wrong=True)
        self.assertIn("bosnia",info["blocked"])
        self.assertEqual(info["fixed_flags"],["cape_verde"])
        self.assertEqual(len(info["edits"]),1)
    def test_incomplete_coverage_is_not_success(self):
        old,after,info=self.run_fixture(incomplete=True)
        self.assertIn("Incomplete verified coverage",info["blocked"]["bosnia"])
        self.assertEqual(info["fixed_flags"],["cape_verde"])
    def test_fragment_assembly(self):
        raw=bytearray(896)
        for box in ((816,368,16,16),(816,384,16,12)):
            put_fragment(raw,"bosnia",box,get_fragment(self.old["bosnia"],"bosnia",box))
        self.assertEqual(bytes(raw),self.old["bosnia"])

if __name__=="__main__": unittest.main()
