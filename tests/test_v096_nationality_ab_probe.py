import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_v096_nationality_ab_probe import relocated_select, pair_candidates, eligible
from audit_v096_nationality_refs import R,EN,EA,SELECT_LEN,refs

class NationalityProbeTests(unittest.TestCase):
    def setUp(self):
        self.a,self.b,self.c=(4,22),(13,22),(6,22)
        self.active=[self.a,self.b,self.c]+[(i//22,i%22) for i in range(525)]
        self.native={self.a:0,self.b:1,self.c:2}
        self.buf=bytearray(SELECT_LEN)
        for i,r in enumerate(self.active):
            self.buf[R+i*2:R+i*2+2]=bytes(r)
        for i in range(3):
            self.buf[EN+10*i:EN+10*i+10]=bytes([65+i])*10
            self.buf[EA+12*i:EA+12*i+12]=bytes([i+1])*12
    def test_moves_complete_records_and_only_requested_refs(self):
        after,_=relocated_select(self.buf,self.active,self.native,self.a,self.b)
        self.assertEqual(refs(after)[:3],[self.b,self.a,self.c])
        self.assertEqual(after[EN:EN+30],b"B"*10+b"A"*10+b"C"*10)
        self.assertEqual(after[EA:EA+36],b"\2"*12+b"\1"*12+b"\3"*12)
        self.assertEqual(self.buf[EN:EN+10],b"A"*10)
        for x,y in zip(refs(after)[3:],self.active[3:]):
            self.assertEqual(x,y)
    def test_reject_collision(self):
        native=dict(self.native)
        native[self.b]=native[self.a]
        with self.assertRaises(ValueError):
            relocated_select(self.buf,self.active,native,self.a,self.b)
    def test_reject_shared_record(self):
        with self.assertRaises(ValueError):
            relocated_select(self.buf,self.active,self.native,self.a,self.active[10])
    def test_pair_must_be_reciprocal(self):
        a,b,c=[{"ref":r,"target":t} for r,t in [(self.a,13),(self.b,4),(self.c,4)]]
        self.assertEqual(pair_candidates([a,b,c]),[(a,b)])
    def test_name_only_requires_explicit_review(self):
        row={"method":"FM_NAME_ONLY","status":"REVIEW_NAME_ONLY","country":"GER"}
        self.assertFalse(eligible(row,None))
        self.assertFalse(eligible(row,{"review_status":"OFFICIAL_COUNTRY_CORROBORATED","country":"FRA"}))
        self.assertTrue(eligible(row,{"review_status":"OFFICIAL_COUNTRY_CORROBORATED","country":"GER"}))

if __name__=="__main__":
    unittest.main()
