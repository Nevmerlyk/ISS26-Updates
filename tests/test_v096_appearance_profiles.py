import csv
import json
import random
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from build_v096_appearance_profiles import visual_edit,decode_visual,FIELDS,MASK
from audit_v096_nationality_refs import norm

class AppearanceTests(unittest.TestCase):
    def test_only_selected_bits_changed(self):
        r=random.Random(96)
        for _ in range(256):
            original=r.getrandbits(96).to_bytes(12,"little")
            vals=[19,0,5,0,2,4]
            out=visual_edit(original,vals)
            self.assertEqual(decode_visual(out),vals)
            self.assertEqual((int.from_bytes(original,"little")^int.from_bytes(out,"little"))&~MASK,0)
    def test_null_preserves_original(self):
        original=bytes.fromhex("ffffffffffffffffffffffff")
        vals=[None,1,None,None,0,None]
        out=visual_edit(original,vals)
        self.assertEqual(decode_visual(out),[31,1,15,7,0,7])
        self.assertEqual(visual_edit(original,[None]*6),original)
    def test_reject_invalid_fields(self):
        for val in (-1,32,True,"19"):
            with self.assertRaises(ValueError):
                visual_edit(bytes(12),[val,None,None,None,None,None])
        with self.assertRaises(ValueError):
            visual_edit(bytes(11),[None]*6)
    def test_profile_schema_and_unique_anchors(self):
        data=json.loads((ROOT/"data/integration/v096_appearance_profiles_v2.json").read_text())
        rows=data["profiles"]
        self.assertEqual(len(rows),20)
        self.assertEqual(len({(x["team"],norm(x["name"])) for x in rows}),20)
        for p in rows:
            self.assertTrue(p["source"].startswith("https://"))
            self.assertTrue("RUNTIME_PENDING" in p["status"])
            visual_edit(bytes(12),p["values"])
    def test_all_78_team_memberships_in_review_queue(self):
        from collections import Counter
        with (ROOT/"data/integration/v096_appearance_review_queue.csv").open(encoding="utf-8",newline="") as f:
            q=list(csv.DictReader(f))
        counts=Counter(x["team_id"] for x in q)
        self.assertEqual(len(q),1716)
        self.assertEqual(len(counts),78)
        self.assertTrue(all(v==22 for v in counts.values()))
        self.assertEqual(sum(x["appearance_review_status"]=="INDIVIDUAL_PROFILE_PENDING_RENDER" for x in q),20)
        self.assertEqual(len({(x["team_id"],norm(x["player_name"])) for x in q}),1716)

if __name__=="__main__":
    unittest.main()
