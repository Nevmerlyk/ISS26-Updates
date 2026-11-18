#!/usr/bin/env python3
"""Fail-closed v24 Shakhtar current-squad source regression suite."""
import copy
import json
import unittest

from tools.verify_v096_two_gk_stage import load_csv
from tools.verify_v096_v23_shakhtar_refresh import blob_sha
from tools.verify_v096_v24_shakhtar_current import CURRENT, PREVIOUS, MANIFEST, verify

class ShakhtarV24SourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=load_csv(PREVIOUS)
        cls.after=load_csv(CURRENT)
        cls.report=json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.sha=blob_sha(PREVIOUS.read_bytes())

    def test_78_squads_two_gk_2026_shakhtar_and_number_48(self):
        report=verify(self.before,self.after,self.report,self.sha)
        self.assertEqual(report["player_memberships"],1716)
        self.assertEqual(report["provisional_changed_player_candidates"],66)
        self.assertTrue(report["shakhtar_retained"])
        self.assertFalse(report["release_ready"])

    def test_prohibits_replacing_shakhtar_with_other_club(self):
        rows=copy.deepcopy(self.after)
        next(p for p in rows if p["team_id"]=="CLB_SHK")["team_id"]="CLB_AVL"
        with self.assertRaises(ValueError):
            verify(self.before,rows,self.report,self.sha)

    def test_prohibits_silent_other_team_edit(self):
        rows=copy.deepcopy(self.after)
        next(p for p in rows if p["team_id"]=="CLB_KRY")["player_name"]="OTHER"
        with self.assertRaisesRegex(ValueError,"Unexpected"):
            verify(self.before,rows,self.report,self.sha)

    def test_native_number_48_cannot_be_truncated(self):
        rep=copy.deepcopy(self.report)
        rep["club_2026_27_shirt_targets"][21]["club_jersey_number"]=16
        with self.assertRaisesRegex(ValueError,"31/#48"):
            verify(self.before,self.after,rep,self.sha)

    def test_predecessor_sha_and_game_write_guards(self):
        with self.assertRaisesRegex(ValueError,"Untrusted"):
            verify(self.before,self.after,self.report,"wrong")
        rows=copy.deepcopy(self.after)
        rows[0]["game_write_authorized"]="YES"
        with self.assertRaisesRegex(ValueError,"not approved"):
            verify(self.before,rows,self.report,self.sha)

if __name__=="__main__":
    unittest.main()
