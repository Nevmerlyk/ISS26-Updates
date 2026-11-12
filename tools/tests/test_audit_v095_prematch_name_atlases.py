"""Synthetic-only regression tests for Cape Verde name-atlas inventory."""
from __future__ import annotations
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit_v095_prematch_name_atlases import inspect

RECORD=2388

def fixture(*, omit=None, corrupt_header=None):
    mandatory=set(range(8200,8228))|set(range(8230,8258))|set(range(8260,8288))
    # Fill 1492 unique records, never ship copyrighted disc data.
    lbas=sorted((mandatory-{omit} if omit is not None else mandatory) |
                set(range(10000,10000+1492-len(mandatory)+(1 if omit is not None else 0))))
    assert len(lbas)==1492
    raw=bytearray(b"ISS26X01"+struct.pack("<I",len(lbas)))
    for lba in lbas:
        mask=bytearray(2352)
        mask[24]=0x5B
        mask[2072]=0xA8
        if lba==corrupt_header:
            mask[18]=0x80
        raw.extend(struct.pack("<I",lba))
        raw.extend(bytes([lba&255])*32)
        raw.extend(mask)
    return bytes(raw)

class NameAtlasAuditTests(unittest.TestCase):
    def test_three_groups_are_exact_and_isolated(self):
        data=fixture()
        actual=inspect(data,hashlib.sha256(data).hexdigest().upper())
        self.assertEqual(actual["all_patch_record_count"],1492)
        self.assertEqual(actual["name_atlas_changed_sector_count"],84)
        self.assertEqual(actual["name_atlas_group_count"],3)
        for v in actual["resources"].values():
            self.assertEqual(v["changed_sector_count"],28)
            self.assertEqual(v["total_changed_user_payload_bytes"],28)
            self.assertEqual(v["total_changed_edc_ecc_bytes"],28)
        self.assertFalse(actual["name_placement_or_glyph_coordinates_verified"])
        self.assertFalse(actual["game_patch_ready_for_stable"])

    def test_wrong_release_checksum_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"checksum"):
            inspect(fixture(),"0"*64)

    def test_missing_sector_is_rejected(self):
        data=fixture(omit=8200)
        with self.assertRaisesRegex(ValueError,"Atlas missing"):
            inspect(data,hashlib.sha256(data).hexdigest().upper())

    def test_corrupted_cd_header_is_rejected(self):
        data=fixture(corrupt_header=8230)
        with self.assertRaisesRegex(ValueError,"changed CD header"):
            inspect(data,hashlib.sha256(data).hexdigest().upper())

    def test_repeated_or_unordered_lba_is_rejected(self):
        data=bytearray(fixture())
        data[12+RECORD:12+RECORD+4]=data[12:16]
        with self.assertRaisesRegex(ValueError,"Unsorted"):
            inspect(bytes(data),hashlib.sha256(data).hexdigest().upper())

if __name__=="__main__":
    unittest.main()
