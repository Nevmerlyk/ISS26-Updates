"""Synthetic regressions for the 5-part pinned Test13 name-atlas recovery path."""
from __future__ import annotations
import base64, lzma, struct, sys, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from inspect_v095_test13_from_stage import (
    EXPECTED_LBAS, parse_staged_name_delta, image_png,
)
from build_v095_targeted_name_overlay import correct_xor_parity
from probe_v095_name_gpu_atlas import sha


def fake_transfer():
    data=bytearray(b"ISS26M01"+struct.pack("<I",84))
    for i,lba in enumerate(EXPECTED_LBAS):
        mask=bytearray(2352)
        mask[24]=i%255+1
        correct_xor_parity(mask)
        data+=struct.pack("<I",lba)+bytes(32)+mask
    raw=bytes(data)
    compressed=lzma.compress(raw,format=lzma.FORMAT_XZ)
    encoded=base64.b64encode(compressed).decode("ascii")
    stride=(len(encoded)+4)//5
    parts=[encoded[i*stride:(i+1)*stride] for i in range(5)]
    return parts,raw,compressed


class TestStagedNames(unittest.TestCase):
    def test_exact_84_sector_parser(self):
        parts,raw,compressed=fake_transfer()
        with patch("inspect_v095_test13_from_stage.TRANSFER_SHA",sha(compressed)), \
             patch("inspect_v095_test13_from_stage.DELTA_SHA",sha(raw)):
            result=parse_staged_name_delta(parts)
        self.assertEqual(tuple(result),EXPECTED_LBAS)
        self.assertEqual(len(result),84)
        self.assertEqual(len(result[8200][1]),2352)

    def test_hash_tampering_fails(self):
        parts,raw,compressed=fake_transfer()
        with patch("inspect_v095_test13_from_stage.TRANSFER_SHA",sha(compressed)), \
             patch("inspect_v095_test13_from_stage.DELTA_SHA",sha(raw)):
            parts[0]="A"+parts[0][1:]
            with self.assertRaises(ValueError):
                parse_staged_name_delta(parts)

    def test_duplicate_sector_fails(self):
        parts,raw,compressed=fake_transfer()
        corrupt=bytearray(raw)
        struct.pack_into("<I",corrupt,12+2388,8200)
        packed=lzma.compress(bytes(corrupt))
        encoded=base64.b64encode(packed).decode("ascii")
        stride=(len(encoded)+4)//5
        bits=[encoded[i*stride:(i+1)*stride] for i in range(5)]
        with patch("inspect_v095_test13_from_stage.TRANSFER_SHA",sha(packed)), \
             patch("inspect_v095_test13_from_stage.DELTA_SHA",sha(bytes(corrupt))):
            with self.assertRaisesRegex(ValueError,"sector"):
                parse_staged_name_delta(bits)

    def test_readable_png_output(self):
        zeros=bytes(8192)
        data=[zeros]
        records=[{"x_words":0,"y":0}]
        png=image_png(data,records)
        self.assertTrue(png.startswith(bytes.fromhex("89504e470d0a1a0a")))
        edited=bytearray(zeros)
        edited[0]=1
        result=image_png([bytes(edited)],records,data)
        self.assertNotEqual(png,result)


if __name__=="__main__":
    unittest.main()
