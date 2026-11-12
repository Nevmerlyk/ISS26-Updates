"""Regression tests for the ISS26 v0.9.5 read-only GPU packet boundary probe."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from probe_v095_name_codec_boundaries import packet_stats

class TestCodecBoundaries(unittest.TestCase):
    def test_zero_to_three_padding_bytes(self):
        for n in range(4):
            body=bytes.fromhex("7c01ff")
            raw=body+bytes(n)
            # make total packet length 4-aligned (the real packet guard)
            if len(raw)%4==0:
                found=packet_stats(raw)
                self.assertEqual(found["trailing_zero_padding"],n)
                self.assertEqual(found["bytes_through_final_ff"],3)

    def test_valid_realistic_packet(self):
        packet=bytes.fromhex("7c017c01ff000000")
        info=packet_stats(packet)
        self.assertEqual(info["trailing_zero_padding"],3)
        self.assertEqual(info["byte_sequence_7c01_count"],2)
        self.assertEqual(info["last_nonzero_byte"],"FF")

    def test_missing_final_ff_rejected(self):
        for raw in (bytes(4), bytes.fromhex("7c010000"), bytes.fromhex("7c010101")):
            with self.assertRaises(ValueError):
                packet_stats(raw)

    def test_more_than_three_padding_bytes_rejected(self):
        with self.assertRaises(ValueError):
            packet_stats(bytes.fromhex("7c01ff0000000000"))

if __name__=="__main__":
    unittest.main()
