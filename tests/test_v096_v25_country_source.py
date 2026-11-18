#!/usr/bin/env python3
"""DEV20 source-only nationality validation regressions."""
import copy
import json
import unittest

from tools.verify_v096_two_gk_stage import load_csv
from tools.verify_v096_v25_country_source import (
    V24,V25,V25_LOANS,V25_COUNTRIES,OLD_COUNTRIES,SHAKHTAR,check,
)

class CountryV25Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=load_csv(V24)
        cls.new=load_csv(V25)
        cls.loans=json.loads(V25_LOANS.read_text(encoding="utf-8"))
        cls.country=json.loads(V25_COUNTRIES.read_text(encoding="utf-8"))
        cls.legacy=json.loads(OLD_COUNTRIES.read_text(encoding="utf-8"))
        cls.shk=json.loads(SHAKHTAR.read_text(encoding="utf-8"))

    @classmethod
    def run_case(cls, country=None, current=None):
        return check(cls.old,current or cls.new,cls.loans,country or cls.country,cls.legacy,cls.shk)

    def test_real_528_source_country_rows_and_78_clubs_and_nations(self):
        r=self.run_case()
        self.assertEqual(r["club_country_records"],528)
        self.assertEqual(r["missing_provisional_country_ids"],37)
        self.assertTrue(r["shakhtar_retained"])
        self.assertFalse(r["native_personal_country_field_known"])

    def test_reject_slot_match_without_person_identity(self):
        bad=copy.deepcopy(self.country)
        next(p for p in bad["players"] if p["team_id"]=="CLB_KRY")["player_name"]="Other"
        with self.assertRaisesRegex(ValueError,"slot, not by name"):
            self.run_case(country=bad)

    def test_shakhtar_not_all_brazilian(self):
        bad=copy.deepcopy(self.country)
        next(p for p in bad["players"] if p["team_id"]=="CLB_SHK" and p["player_name"]=="Dmytro Riznyk")["country_code_candidate"]="BRA"
        with self.assertRaises(ValueError):
            self.run_case(country=bad)

    def test_separate_risky_country_id_from_game_patch(self):
        bad=copy.deepcopy(self.country)
        next(p for p in bad["players"] if p["player_name"]=="Alaa Ghram")["country_id_candidate_from_old_manifest"]=21
        with self.assertRaisesRegex(ValueError,"Tunisia"):
            self.run_case(country=bad)

    def test_loaned_player_cannot_be_reintroduced(self):
        bad=copy.deepcopy(self.new)
        next(p for p in bad if p["team_id"]=="CLB_MUN" and p["game_slot"]=="21")["player_name"]="Chido Obi"
        with self.assertRaises(ValueError):
            self.run_case(current=bad)

    def test_no_binary_write_approval(self):
        bad=copy.deepcopy(self.country)
        bad["players"][0]["update_game_player_record_allowed"]=True
        with self.assertRaisesRegex(ValueError,"slot, not by name"):
            self.run_case(country=bad)

if __name__=="__main__":
    unittest.main()
