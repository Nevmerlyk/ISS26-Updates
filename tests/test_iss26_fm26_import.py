"""Basic unit tests for ISS26 FM26 converter; run: python -m unittest discover -s tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from iss26_fm26_import import (iss_scale, normalized_name, raw_attribute,
                              weighted, select_player, fm_index)

class ConversionTests(unittest.TestCase):
    def test_endpoints(self):
        self.assertEqual(iss_scale(1), "12")
        self.assertEqual(iss_scale(20), "19")
        self.assertEqual(iss_scale(10.5), "16")
    def test_bounds(self):
        for i in range(1, 21):
            self.assertTrue(12 <= int(iss_scale(i)) <= 19)
    def test_name_diacritics(self):
        self.assertEqual(normalized_name("Kylian Mbappé"),
                         normalized_name("Kylian Mbappe"))
    def test_missing_not_fabricated(self):
        self.assertIsNone(raw_attribute({}, "pace"))
        self.assertIsNone(weighted({}, (("pace", 1.),)))
    def test_reject_derived_1_to_99(self):
        self.assertIsNone(raw_attribute({"Pace": "95"}, "pace"))
    def test_real_1_to_20(self):
        self.assertEqual(raw_attribute({"Pace": "18"}, "pace"), 18)
    def test_unambiguous(self):
        index = fm_index([{"name": "Kylian Mbappé", "pace": "19"}])
        match, player = select_player("Kylian Mbappe", index, {})
        self.assertEqual(match, "matched")
        self.assertIsNotNone(player)
    def test_ambiguous_rejected(self):
        index = fm_index([{"name": "John Smith", "uid": "1"},
                          {"name": "John Smith", "uid": "2"}])
        match, player = select_player("John Smith", index, {})
        self.assertEqual((match, player), ("ambiguous", None))

if __name__ == "__main__":
    unittest.main()
