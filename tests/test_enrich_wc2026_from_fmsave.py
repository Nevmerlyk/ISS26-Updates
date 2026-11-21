import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from enrich_wc2026_from_fmsave import enrich, strict_convert, GOALKEEPER

class StrictExportTests(unittest.TestCase):
    def setUp(self):
        self.r = {"player_name":"Alex Example","birth_date":"2000-01-01",
                  "fm_uid_candidate":"100","position_group":"GK","iss_stamina":"16"}
        self.p = {"name":"Alex Example","birth_date":"2000-01-01","unique_id":"100",
                  "uid":"999","attributes_aerial_reach":"20","attributes_jumping_reach":"20",
                  "attributes_stamina":"15","attributes_natural_fitness":"15"}

    def test_keeper_and_preservation(self):
        rows, counts = enrich([self.r], [self.p])
        r=rows[0]
        self.assertEqual(r["export_iss_jump_power"], "19")
        self.assertEqual(r["iss_stamina"], "16")
        self.assertEqual(r["export_fm26_unique_id"], "100")
        self.assertEqual(r["fm26_verified_match_status"], "uid_name_dob")
    def test_dob_conflict(self):
        p=dict(self.p,birth_date="2001-01-01")
        r=enrich([self.r],[p])[0][0]
        self.assertEqual(r["fm26_verified_match_status"],"uid_dob_conflict")
        self.assertEqual(r["export_converted_count"],"0")
    def test_save_local_id_not_database_id(self):
        p=dict(self.p,unique_id="",uid="100")
        r=enrich([self.r],[p])[0][0]
        self.assertEqual(r["fm26_verified_match_status"],"missing_database_uid")
    def test_missing_component(self):
        p=dict(self.p,attributes_jumping_reach="")
        self.assertEqual(strict_convert(p,GOALKEEPER["iss_jump_power"]),"")
    def test_duplicate_uid(self):
        r=enrich([self.r],[self.p,self.p])[0][0]
        self.assertEqual(r["fm26_verified_match_status"],"duplicate_source_uid")
    def test_raw_scale_not_accepted(self):
        p=dict(self.p,attributes_aerial_reach="95")
        self.assertEqual(strict_convert(p,GOALKEEPER["iss_jump_power"]),"")

if __name__=="__main__":
    unittest.main()
