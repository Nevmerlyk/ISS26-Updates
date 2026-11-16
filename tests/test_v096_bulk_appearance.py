import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from build_v096_appearance_profiles import combine_candidates,visual_edit,decode_visual,MASK
from refine_v096_appearance_identities import choose,link_id,unique_preset

class BulkAppearanceTests(unittest.TestCase):
    def candidate(self,**kw):
        return dict({"name":"Test Player","roster_uid":"123","dob":"2000-01-01","native_we_id":"456","values":[10,1,0,0,1,3]},**kw)
    def test_shared_ref_single_appearance(self):
        a=self.candidate()
        b=self.candidate(values=[None,1,None,0,1,3])
        self.assertEqual(combine_candidates([a,b]),a["values"])
    def test_conflicting_value_rejected(self):
        with self.assertRaises(ValueError):
            combine_candidates([self.candidate(),self.candidate(values=[11,1,0,0,1,3])])
    def test_conflicting_identity_rejected(self):
        with self.assertRaises(ValueError):
            combine_candidates([self.candidate(),self.candidate(dob="2001-01-01")])
    def test_unknown_or_conflicting_source_ids(self):
        with self.assertRaises(ValueError):
            combine_candidates([self.candidate(),self.candidate(name="Other Person",roster_uid="321",native_we_id="654")])
    def test_ui_range_and_nonvisual_bits(self):
        with self.assertRaises(ValueError):
            combine_candidates([self.candidate(values=[1,8,0,0,0,0])])
        raw=bytes(range(12))
        values=combine_candidates([self.candidate()])
        after=visual_edit(raw,values)
        self.assertEqual(decode_visual(after),values)
        self.assertEqual((int.from_bytes(raw,"little")^int.from_bytes(after,"little"))&~MASK,0)
    def row(self,**kw):
        return dict({"Id":456,"Name":"Test Player","NAMEWE":"Player","Birthday":"2000-01-01","Club":"Example","Nation":"Ukraine","NationalTeam":"Ukraine","Hair":"i1","HairColor":"a","HairFace":"f","HairColorFace":"a","SkinColor":"b","Body":"c","Link":"https://sofifa.com/player/456/test"},**kw)
    def manifest(self,**kw):
        return dict({"team_id":"NAT_UKR","player_name":"Player Test","fm_name":"Test Player","identity_status":"ROSTER_UID_WITH_NAME_OR_DOB","dob_candidate":"2000-01-01","fm_nationalities":"Ukraine"},**kw)
    def test_refine_verified_alias(self):
        self.assertEqual(choose(self.manifest(),{"status":"NO_EXACT_NAME"},{},{"2000-01-01":[self.row()]})[0],"WE_EXACT_FM_ALIAS_DOB")
    def test_reject_ambiguous_alias(self):
        self.assertEqual(choose(self.manifest(),{"status":"NO_EXACT_NAME"},{},{"2000-01-01":[self.row(),self.row(Id=123)]}),(None,None))
    def test_dob_conflict_blocked(self):
        self.assertEqual(choose(self.manifest(identity_status="DOB_CONFLICT_REVIEW"),{"status":"NO_EXACT_NAME"},{},{"2000-01-01":[self.row()]}),(None,None))
    def test_id_url_corroboration(self):
        self.assertEqual(link_id("https://sofifa.com/player/456/test"),"456")
        self.assertEqual(link_id("https://example.com/player/456/test"),"")

if __name__=="__main__":
    unittest.main()
