#!/usr/bin/env python3
"""DEV22 source-stage safety regressions. No game image is modified."""
import copy
import json
import unittest

from tools.verify_v096_two_gk_stage import CSV_PATH, JSON_PATH, CLUB_REGISTRY, load_csv, validate

class TwoGKSourceStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=load_csv(CSV_PATH)
        cls.report=json.loads(JSON_PATH.read_text(encoding="utf-8"))
        cls.registry=json.loads(CLUB_REGISTRY.read_text(encoding="utf-8"))

    def test_real_source_all_78_shakhtar_and_gk_last(self):
        result=validate(self.rows,self.report,self.registry)
        self.assertEqual(result["teams"],78)
        self.assertEqual(result["candidate_replacements"],60)
        self.assertTrue(result["shakhtar_preserved"])
        self.assertFalse(result["release_ready"])

    def test_shakhtar_must_not_be_replaced(self):
        bad=copy.deepcopy(self.rows)
        next(r for r in bad if r["team_id"]=="CLB_SHK")["team_id"]="CLB_AVL"
        with self.assertRaisesRegex(ValueError,"registry|size"):
            validate(bad,self.report,self.registry)

    def test_illegal_gk_in_starting_xi_rejected(self):
        bad=copy.deepcopy(self.rows)
        next(r for r in bad if r["team_id"]=="CLB_KRY" and r["game_slot"]=="2")["source_position"]="GK"
        with self.assertRaisesRegex(ValueError,"Reserve goalkeeper must be last"):
            validate(bad,self.report,self.registry)

    def test_no_unreviewed_write_authorization(self):
        bad=copy.deepcopy(self.rows)
        bad[0]["game_write_authorized"]="YES"
        with self.assertRaisesRegex(ValueError,"unsafe write"):
            validate(bad,self.report,self.registry)

    def test_shakhtar_gk_must_stay(self):
        bad=copy.deepcopy(self.rows)
        next(r for r in bad if r["team_id"]=="CLB_SHK" and r["game_slot"]=="22")["player_name"]="Another"
        with self.assertRaisesRegex(ValueError,"Shakhtar"):
            validate(bad,self.report,self.registry)

if __name__=="__main__":
    unittest.main()
