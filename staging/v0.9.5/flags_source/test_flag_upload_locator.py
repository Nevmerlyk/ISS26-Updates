"""Synthetic read-only tests for flag upload locating."""
import pathlib
import struct
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from flag_upload_locator import inspect_resource, intersects_target
from wecodec import encode


class FlagLocatorTests(unittest.TestCase):
    def test_geometry(self):
        self.assertTrue(intersects_target(832, 256, 64, 224, 864, 320))
        self.assertTrue(intersects_target(864, 320, 16, 32, 864, 320))
        self.assertFalse(intersects_target(864, 400, 16, 32, 864, 320))

    def test_identifies_bosnia_resource_upload(self):
        original_pixels = bytes([0x11]) * (16 * 2 * 32)
        compressed = encode(original_pixels)
        resource = bytearray(4096)
        resource[128:128 + len(compressed)] = compressed
        struct.pack_into("<6HI", resource, 2048,
                         10, 864, 320, 16, 32, 0, 0x800F0000 + 128)
        matches = inspect_resource("BIN/GDC_SAMPLE.BIN", bytes(resource))
        verified = [record for record in matches
                    if "bosnia" in record["targets"] and
                    record["valid_compressed_candidates"]]
        self.assertTrue(verified)
        self.assertEqual(verified[0]["valid_compressed_candidates"][0]["compressed_offset"], 128)

    def test_rejects_non_overlapping_upload(self):
        resource = bytearray(2048)
        struct.pack_into("<6HI", resource, 1024,
                         10, 300, 50, 16, 32, 0, 0x800F0080)
        self.assertEqual(inspect_resource("GDC_FAKE.BIN", bytes(resource)), [])


if __name__ == "__main__":
    unittest.main()
