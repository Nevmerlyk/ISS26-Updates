import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from import_fmplayer_history import parse_history, match

URL = "https://fmplayer.net/history/example-player-123"
PAGE = """# Example Player Football Manager History
Attribute | FM 18 | FM 24 | FM 26
Technical Attributes
Dribbling | 90 | 140 5 | 180
Physical Attributes
Pace | 90 | 180 9 | 160
Stamina | 110 | 120 | 130
Natural Fitness | 130 | 130 | 140
"""
ROW = {"player_name": "Example Player", "fm_uid_candidate": "123", "position_group": "FW"}
ENTRY = {"expected_uid": "123", "expected_name": "Example Player", "identity_source_url": "https://example.invalid/identity"}

class HistoryTests(unittest.TestCase):
    def test_select_only_fm26(self):
        p = parse_history(PAGE, URL)
        self.assertEqual(p["raw"]["pace"], 16)
        self.assertEqual(p["raw"]["dribbling"], 18)
        self.assertEqual(match(ROW, ENTRY, p)["iss_stamina"], "17")

    def test_zero_no_older_fallback(self):
        p = parse_history(PAGE.replace("140 5 | 180", "140 5 | 0"), URL)
        self.assertNotIn("dribbling", p["raw"])
        self.assertEqual(match(ROW, ENTRY, p)["iss_dribble"], "")

    def test_wrong_edition_or_width(self):
        for b in (PAGE.replace("FM 26", "FM 25"), PAGE.replace("90 | 180 9 | 160", "90 | 160")):
            with self.assertRaises(ValueError):
                parse_history(b, URL)

    def test_conflict_and_delta(self):
        p = parse_history(PAGE + "Pace | 90 | 180 | 150\n", URL)
        self.assertNotIn("pace", p["raw"])
        p = parse_history(PAGE.replace("180 9 | 160", "180 9 | 160 2"), URL)
        self.assertNotIn("pace", p["raw"])

    def test_identity_required(self):
        p = parse_history(PAGE, URL)
        for r, e in ((dict(ROW, fm_uid_candidate=""), ENTRY), (ROW, dict(ENTRY, expected_uid="456")), (ROW, dict(ENTRY, identity_source_url=""))):
            with self.assertRaises(ValueError):
                match(r, e, p)

    def test_wrong_host(self):
        with self.assertRaises(ValueError):
            parse_history(PAGE, "https://other.invalid/history/example-player-123")

if __name__ == "__main__":
    unittest.main()
