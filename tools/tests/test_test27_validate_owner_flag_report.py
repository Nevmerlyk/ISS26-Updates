#!/usr/bin/env python3
"""Synthetic checks for the Test27 owner art/CLUT evidence gate."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_validate_owner_flag_report as gate

def sample():
    def f(style,src,stage,clut,srcsha,stagesha,counts,rows,mask):
        return {
            "source_style":style,"source_vram_words":src,
            "stage_vram_words":stage,"clut_vram_words":clut,
            "source_tile_sha256":srcsha,"stage_tile_sha256":stagesha,
            "clut_sha256":"D"*64,
            "diff":{"pixel_index_differences":counts,
                    "source_nonzero_stage_zero_by_row":rows,
                    "is_contiguous_bottom_12_row_mask":mask}
        }
    return {"schemaVersion":1,"input_zip_sha256":gate.EXPECTED_ARCHIVE_SHA,
            "snapshot":gate.EXPECTED_FRAME,"visual_ownership_proven":False,
            "source_disc_modified":False,"game_patch_built":False,
            "update_feed_changed":False,"flags":{
        "cape_verde":f(1,[848,256],[560,0],[0,505],"A"*64,"A"*64,
                       {"equal":1792,"source_nonzero_stage_zero":0,
                        "new_nonzero":0,"changed_nonzero":0},[0]*28,False),
        "bosnia":f(55,[816,368],[560,28],[224,506],"B"*64,"C"*64,
                   {"equal":1408,"source_nonzero_stage_zero":384,
                    "new_nonzero":0,"changed_nonzero":0},
                   [0]*16+[32]*12,True)}}

class TestOwnerRealFlagGate(unittest.TestCase):
    def test_two_independent_defects_not_release_ready(self):
        out=gate.validate(sample())
        self.assertTrue(out["cape_copy_exact"])
        self.assertTrue(out["bosnia_atlas_bottom_trimmed"])
        self.assertEqual(out["bosnia_lower_row_lost_indices"],384)
        self.assertEqual(out["flags"]["bosnia"]["affected_rows"],list(range(16,28)))
        self.assertTrue(out["two_clut_addresses_identical_content"])
        self.assertFalse(out["machine_can_verify_national_art_design"])
        self.assertFalse(out["corrected_game_patch_releasable"])

    def test_reject_fake_promotion_or_wrong_snapshot(self):
        for key,val in (("game_patch_built",True),
                        ("update_feed_changed",True),
                        ("source_disc_modified",True),
                        ("visual_ownership_proven",True),
                        ("snapshot","auto_guess.vram")):
            data=sample()
            data[key]=val
            with self.assertRaises(ValueError):
                gate.validate(data)

    def test_detect_row_accounting_and_sha_claim_inconsistency(self):
        data=sample()
        data["flags"]["bosnia"]["diff"]["source_nonzero_stage_zero_by_row"][27]=31
        with self.assertRaises(ValueError):
            gate.validate(data)
        data=sample()
        data["flags"]["cape_verde"]["stage_tile_sha256"]="E"*64
        with self.assertRaises(ValueError):
            gate.validate(data)
        data=sample()
        data["flags"]["bosnia"]["diff"]["pixel_index_differences"]["equal"]=1409
        with self.assertRaises(ValueError):
            gate.validate(data)

    def test_identical_clut_is_observation_not_a_palette_fault(self):
        data=sample()
        data["flags"]["bosnia"]["clut_sha256"]="F"*64
        out=gate.validate(data)
        self.assertFalse(out["two_clut_addresses_identical_content"])
        self.assertFalse(out["corrected_game_patch_releasable"])
        self.assertIn("do not prove CLUTs are incorrectly shared",out["notes"][0])

if __name__=="__main__":
    unittest.main()
