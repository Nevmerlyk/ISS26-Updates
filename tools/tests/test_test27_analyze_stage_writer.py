#!/usr/bin/env python3
"""Test27 stage MIPS telemetry classification, synthetic only."""
from __future__ import annotations
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test27_analyze_stage_writer as test27

MOVE_SHORT = "5460\tSTYLE_MOVE\taway\t55\t816\t368\t560\t28\t16\t16\t8003884C\t800933CC\n"
MOVE_FULL = "5460\tSTYLE_MOVE\taway\t55\t816\t368\t560\t28\t16\t28\t8003884C\t800933CC\n"
ANOMALY = ("5460\tSTAGE_COPY_DIMENSION_ANOMALY\taway\t"
           "style=55\tw=16\th=16\texpected=16x28\n")
STORE_SHORT = ("5461\tSTAGE_TRANSFER_RECT\tStoreImage\t"
               "x=560\ty=28\tw=16\th=16\tRAM=800CC980\tPC=800387EC\tRA=80092F60\n")
LOAD_FULL = ("5470\tSTAGE_TRANSFER_RECT\tLoadImage\t"
             "x=560\ty=0\tw=16\th=56\tRAM=800CC600\tPC=8003878C\tRA=80093134\n")

class StageWriterTests(unittest.TestCase):
    def test_short_away_style55_move_is_observed_not_claimed_cause(self):
        result = test27.analyze_text(
            MOVE_SHORT + ANOMALY + STORE_SHORT +
            "5500\tSTAGE_RECT_FINAL\tmove_dim_anomalies=1\ttransfer_rects=1\n")
        self.assertEqual(result["away_style55_short_count"], 1)
        self.assertEqual(result["away_style55_full_count"], 0)
        self.assertEqual(result["anomaly_count"], 1)
        self.assertEqual(result["store_load_short_rect_count"], 1)
        self.assertIn("Observed sub-28-row MoveImage", result["verdict"])
        self.assertFalse(result["writer_causality_proven"])

    def test_full_move_followed_by_ram_transfer_is_not_certified(self):
        result = test27.analyze_text(MOVE_FULL + STORE_SHORT + LOAD_FULL)
        self.assertEqual(result["away_style55_full_count"], 1)
        self.assertEqual(result["store_load_short_rect_count"], 1)
        self.assertIn("investigate later", result["verdict"])
        self.assertFalse(result["game_patch_built"])

    def test_empty_or_legacy_log_does_not_claim_a_cause(self):
        result = test27.analyze_text("500\tWRITE_SAMPLE\t80000000\n")
        self.assertEqual(result["move_count"], 0)
        self.assertIn("No observed style55", result["verdict"])

    def test_reject_wrong_style_and_coordinate_errors(self):
        for wrong in (
            MOVE_FULL.replace("\t55\t", "\t999\t"),
            MOVE_FULL.replace("\t560\t28\t", "\t560\t0\t"),
            MOVE_FULL.replace("\t28\t16\t28\t", "\t28\t16\t2048\t"),
        ):
            with self.assertRaises(test27.TraceError):
                test27.analyze_text(wrong)

    def test_reject_conflicting_final_counter_and_bad_anomaly(self):
        with self.assertRaises(test27.TraceError):
            test27.analyze_text(
                "5500\tSTAGE_RECT_FINAL\tmove_dim_anomalies=1\ttransfer_rects=0\n")
        with self.assertRaises(test27.TraceError):
            test27.analyze_text(
                ANOMALY.replace("expected=16x28", "expected=16x16"))

    def test_reject_oversize_and_bad_log_encoding(self):
        with self.assertRaises(test27.TraceError):
            test27.analyze_text("a" * (test27.MAX_BYTES + 1))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.tsv"
            p.write_bytes(b"\xff\xfe")
            with self.assertRaises(UnicodeDecodeError):
                test27.analyze_file(p)

    def test_valid_input_is_file_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "flag-provenance.tsv"
            p.write_text(MOVE_FULL)
            before = p.read_bytes()
            result = test27.analyze_file(p)
            self.assertEqual(result["away_style55_move_count"], 1)
            self.assertEqual(p.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
