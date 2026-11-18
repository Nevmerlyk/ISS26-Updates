#!/usr/bin/env python3
"""Synthetic and pinned-real-source Shakhtar 2026/27 candidate diff tests."""
import copy
import json
import unittest

from tools.verify_v096_two_gk_stage import load_csv
from tools.verify_v096_v23_shakhtar_refresh import OLD, NEW, REPORT, audit, blob_sha

class ShakhtarV23Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=load_csv(OLD)
        cls.new=load_csv(NEW)
        cls.report=json.loads(REPORT.read_text(encoding="utf-8"))
        cls.sha=blob_sha(OLD.read_bytes())

    def test_1716_record_differential_and_shakhtar_stays(self):
        r=audit(self.old,self.new,self.report,self.sha)
        self.assertEqual(r["source_shakhtar_updated"],5)
        self.assertEqual(r["source_candidate_total"],65)
        self.assertEqual(r["starter_and_last_reserve_goalkeepers"],78)
        self.assertFalse(r["game_patch_modified"])

    def test_do_not_tamper_with_other_clubs(self):
        modified=copy.deepcopy(self.new)
        next(r for r in modified if r["team_id"]=="CLB_KRY")["player_name"]="Wrong"
        with self.assertRaisesRegex(ValueError,"Non-Shakhtar"):
            audit(self.old,modified,self.report,self.sha)

    def test_no_unreviewed_binary_write(self):
        modified=copy.deepcopy(self.new)
        next(r for r in modified if r["team_id"]=="CLB_SHK")["game_write_authorized"]="YES"
        with self.assertRaises(ValueError):
            audit(self.old,modified,self.report,self.sha)

    def test_wrong_original_fingerprint_rejected(self):
        with self.assertRaisesRegex(ValueError,"SHA"):
            audit(self.old,self.new,self.report,"BAD")

    def test_cannot_swap_club_with_obsolete_registry(self):
        modified=copy.deepcopy(self.new)
        next(r for r in modified if r["team_id"]=="CLB_SHK")["team_id"]="CLB_AVL"
        with self.assertRaises(ValueError):
            audit(self.old,modified,self.report,self.sha)

if __name__=="__main__":
    unittest.main()
