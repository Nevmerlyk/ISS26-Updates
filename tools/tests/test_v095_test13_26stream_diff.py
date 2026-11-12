#!/usr/bin/env python3
"""Metadata regression guards for ISS26 v0.9.5 Test13 prematch GPU uploads.

These checks run on the published derived JSON only (no copyrighted disc).
They do not prove a working image decoder or a playable Test14.
"""
from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "diagnostics" / "v095-test13-26stream-diff.json"
NAMES = ("BIN/T_NAME_E.BIN", "BIN/T_NAME_F.BIN", "BIN/T_NAME_G.BIN")
CHANGED_PREFIX_STREAMS = {0, 4, 5, 6, 7, 8, 9, 12}


class TestV095Test13StreamDiff(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(REPORT.read_text(encoding="utf-8"))

    def test_provenance_and_language_concordance(self):
        d = self.data
        self.assertEqual(d["schema_version"], 1)
        self.assertEqual(d["input_probe"], "ISS26-CapeVerde-probe.json")
        self.assertEqual(
            d["clean_original_sha256"],
            "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44",
        )
        self.assertEqual(
            d["patch_test13_sha256"],
            "159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214",
        )
        self.assertEqual(set(d["resources"]), set(NAMES))
        self.assertTrue(d["all_three_language_tables_have_identical_deltas"])
        for name in NAMES[1:]:
            self.assertEqual(d["resources"][NAMES[0]]["streams"], d["resources"][name]["streams"])

    def test_expected_26_uploads_and_eight_changed_prefixes(self):
        for name in NAMES:
            resource = self.data["resources"][name]
            self.assertTrue(resource["unchanged_geometry"])
            rows = resource["streams"]
            self.assertEqual(len(rows), 26)
            self.assertEqual(resource["prefix_changed_count"], 8)
            self.assertEqual(
                {r["stream_id"] for r in rows if r["prefix_64_sha256_changed"]},
                CHANGED_PREFIX_STREAMS,
            )
            self.assertEqual(
                [(r["stream_id"], r["before_offset"] == 4 * (r["before_offset"] // 4)) for r in rows],
                [(i, True) for i in range(26)],
            )
            self.assertEqual(len(set(tuple(r["vram_xy_words"]) for r in rows)), 26)

    def test_allocated_span_not_confused_with_codec_size(self):
        for name in NAMES:
            resource = self.data["resources"][name]
            rows = resource["streams"]
            self.assertEqual(
                resource["allocated_span_changed_count"], 10
            )
            self.assertEqual(sum(r["allocated_span_delta"] for r in rows), 0)
            self.assertEqual(sum(r["allocated_span_delta"] for r in rows[:-1]), -1176)
            self.assertEqual(rows[-1]["allocated_span_delta"], +1176)
            self.assertEqual(rows[0]["before_offset"], 4)
            self.assertEqual(rows[0]["after_offset"], 4)
            for r in rows:
                self.assertGreater(r["before_allocated_span"], 0)
                self.assertGreater(r["after_allocated_span"], 0)
            self.assertEqual(
                rows[-1]["after_offset"] + rows[-1]["after_allocated_span"],
                55824,
            )


if __name__ == "__main__":
    unittest.main()
