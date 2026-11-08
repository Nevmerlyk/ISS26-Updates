"""Regression checks for safe patch-header analysis, no game assets."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_patch_sector_headers import report

ZERO = bytes(2352)


def make_delta(*edits):
    data = bytearray(2352)
    for index, value in edits:
        data[index] = value
    return bytes(data)


class SectorForensicsTests(unittest.TestCase):
    def test_duplicated_subheader_both_changed_together(self):
        rec = {6151: (bytes(32), make_delta((18, 0x20), (22, 0x20)))}
        found = report(rec)
        self.assertEqual(found["form2_flag_flipped_sector_count"], 1)
        self.assertEqual(found["subheader_delta_mismatch_count"], 0)
        self.assertEqual(found["by_resource_window"]["team_selection_DATSEL2"]["form2_bit_flips"], 1)

    def test_one_sided_subheader_change_is_flagged(self):
        rec = {6152: (bytes(32), make_delta((18, 0x20)))}
        found = report(rec)
        self.assertEqual(found["subheader_delta_mismatch_count"], 1)
        self.assertEqual(found["subheader_delta_mismatch_lbas"], [6152])

    def test_payload_changes_do_not_count_as_header_change(self):
        rec = {4003: (bytes(32), make_delta((24, 0xF0), (2348, 0xBC)))}
        found = report(rec)
        self.assertEqual(found["changed_header_sector_count"], 0)
        self.assertEqual(found["mode_byte_changed_sector_count"], 0)
        self.assertEqual(found["subheader_delta_mismatch_count"], 0)

    def test_sync_byte_corruption_flagged(self):
        rec = {12800: (bytes(32), make_delta((3, 0x01), (15, 0x02)))}
        found = report(rec)
        self.assertEqual(found["sync_changed_sector_count"], 1)
        self.assertEqual(found["mode_byte_changed_sector_count"], 1)


if __name__ == "__main__":
    unittest.main()
