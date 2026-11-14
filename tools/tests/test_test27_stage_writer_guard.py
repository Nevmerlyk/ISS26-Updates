#!/usr/bin/env python3
"""Synthetic Test27 MIPS guard tests; no PS1 copyrighted disc is in CI."""
from __future__ import annotations
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_stage_writer_guard as g

class StageWriterGuardTests(unittest.TestCase):
    def setUp(self):
        self.select=bytearray(g.SELECT_BYTES)
        for _,pc,target in g.STAGE_CALLS:
            instruction=0x0c000000 | ((target>>2)&0x03ffffff)
            struct.pack_into("<I",self.select,pc-g.SELECT_RAM,instruction)

    def test_all_four_static_mips_wrappers(self):
        result=g.verify_select_calls(self.select)
        self.assertEqual(len(result),4)
        self.assertEqual(result[0]["classification"],"VRAM_to_RAM")
        self.assertEqual(result[1]["classification"],"RAM_to_VRAM")
        self.assertEqual(result[2]["classification"],"VRAM_to_VRAM")
        self.assertEqual(result[3]["target_function"],"0x8003884C")

    def test_different_jal_target_refused(self):
        at=g.STAGE_CALLS[3][1]-g.SELECT_RAM
        self.select[at:at+4]=b"\x00\x00\x00\x00"
        with self.assertRaises(ValueError):
            g.verify_select_calls(self.select)

    def test_missing_mips_jal_refused(self):
        with self.assertRaises(ValueError):
            g.jal_target(0x80093338,0)

    def test_wrong_select_overlay_size_refused(self):
        with self.assertRaises(ValueError):
            g.verify_select_calls(bytes(128))

    def test_all_five_original_style_table_guards(self):
        raw=bytearray(max(g.STYLE_MAP_RAW_OFFSETS)+78)
        for at in g.STYLE_MAP_RAW_OFFSETS:
            raw[at+30]=7
            raw[at+54]=10
        result=g.verify_five_original_style_maps(raw)
        self.assertEqual(len(result["five_style_tables"]),5)
        self.assertFalse(result["style55_used_in_any_table"])
        self.assertTrue(result["club54_original_style10_preserved"])

    def test_bosnia_or_club_style_table_collision_refused(self):
        raw=bytearray(max(g.STYLE_MAP_RAW_OFFSETS)+78)
        for at in g.STYLE_MAP_RAW_OFFSETS:
            raw[at+30]=7
            raw[at+54]=10
        raw[g.STYLE_MAP_RAW_OFFSETS[2]+54]=55
        with self.assertRaises(ValueError):
            g.verify_five_original_style_maps(raw)
        raw[g.STYLE_MAP_RAW_OFFSETS[2]+54]=10
        raw[g.STYLE_MAP_RAW_OFFSETS[1]+30]=55
        with self.assertRaises(ValueError):
            g.verify_five_original_style_maps(raw)

    def test_truncated_original_style_table_rejected(self):
        with self.assertRaises(ValueError):
            g.verify_five_original_style_maps(bytes(8))

if __name__=="__main__":
    unittest.main()
