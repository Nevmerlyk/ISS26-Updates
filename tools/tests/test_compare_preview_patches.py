import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compare_preview_patches import PatchError, SECTOR, compare, parse_patch


def make_patch(records):
    body = bytearray(b"ISS26X01" + struct.pack("<I", len(records)))
    for idx, source, delta in records:
        body += struct.pack("<I", idx)
        body += hashlib.sha256(source).digest()
        body += delta
    return bytes(body)


class ReadOnlyReleaseDiffTests(unittest.TestCase):
    def test_compare_works_without_original_disc(self):
        source = bytes([123]) * SECTOR
        changed_a = bytes([1]) + bytes(SECTOR - 1)
        changed_b = bytes([2]) + bytes(SECTOR - 1)
        a = parse_patch(make_patch([(5, source, changed_a)]))
        b = parse_patch(make_patch([(5, source, changed_b)]))
        report = compare(a, b)
        self.assertEqual(report["changed_sectors_between_releases"], 1)
        self.assertEqual(report["changed_bytes_between_releases"], 1)
        self.assertEqual(report["contiguous_sector_regions"][0]["start_sector"], 5)

    def test_detects_incompatible_base_sectors(self):
        a = parse_patch(make_patch([(6, b"A" * SECTOR, b"X" * SECTOR)]))
        b = parse_patch(make_patch([(6, b"B" * SECTOR, b"X" * SECTOR)]))
        with self.assertRaisesRegex(PatchError, "source hashes"):
            compare(a, b)

    def test_rejects_duplicate_or_out_of_order_entries(self):
        a = make_patch([(2, b"A" * SECTOR, b"X" * SECTOR),
                        (2, b"A" * SECTOR, b"Y" * SECTOR)])
        with self.assertRaisesRegex(PatchError, "strictly ascending"):
            parse_patch(a)

    def test_rejects_checksum_mismatch(self):
        p = make_patch([(1, b"A" * SECTOR, b"X" * SECTOR)])
        with self.assertRaisesRegex(PatchError, "SHA mismatch"):
            parse_patch(p, "F" * 64)


if __name__ == "__main__":
    unittest.main()
