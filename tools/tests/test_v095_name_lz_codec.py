"""Synthetic regressions for the real MIPS-derived name atlas LZ codec.

No copyrighted game data is required in continuous integration.
"""
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from v095_name_lz_codec import (
    decode_stream,encode_stream,decode_atlas,repack_atlas,atlas_records,
    FormatError,RESOURCE_BYTES,TABLE_OFFSET,GPU_BASE,UPLOADS,TILE_BYTES
)


def synthetic_atlas(tiles):
    out=bytearray(RESOURCE_BYTES)
    struct.pack_into("<I",out,0,GPU_BASE+TABLE_OFFSET)
    cursor=4
    for i,texture in enumerate(tiles):
        packet=encode_stream(texture)
        x=32*(i//2)
        y=128*(i%2)
        struct.pack_into("<HHHHHHI",out,TABLE_OFFSET+i*16,
                         10,x,y,32,128,0,GPU_BASE+cursor)
        out[cursor:cursor+len(packet)]=packet
        cursor=(cursor+len(packet)+3)&~3
    if cursor>TABLE_OFFSET: raise ValueError("synthetic atlas exceeded space")
    struct.pack_into("<H",out,TABLE_OFFSET+UPLOADS*16,255)
    return bytes(out)


class NameLZCodecTests(unittest.TestCase):
    def test_repeat_and_literals_round_trip(self):
        samples=[
            bytes(TILE_BYTES),
            b"A"*TILE_BYTES,
            (bytes(range(256))*32),
            (b"ISS26 Cape Verde Bosnia "*400)[:TILE_BYTES].ljust(TILE_BYTES,b" "),
            bytes(random.Random(26095 + i).randrange(256) for i in range(TILE_BYTES)),
        ]
        for sample in samples:
            with self.subTest(seed=sample[:8]):
                self.assertEqual(decode_stream(encode_stream(sample)),sample)

    def test_literal_ff_and_end_token_are_not_conflated(self):
        sample = (bytes([255,0,255,1,255,2,0,255]) * (TILE_BYTES // 8))
        self.assertEqual(decode_stream(encode_stream(sample)),sample)

    def test_26_stream_atlas_roundtrip(self):
        tile=bytes(TILE_BYTES)
        source=synthetic_atlas([tile]*UPLOADS)
        decoded=decode_atlas(source)
        self.assertEqual(decoded,[tile]*UPLOADS)
        rebuilt,stats=repack_atlas(source,decoded)
        self.assertEqual(decode_atlas(rebuilt),decoded)
        self.assertEqual(len(atlas_records(rebuilt)),UPLOADS)
        self.assertGreater(stats["free_bytes"],0)

    def test_one_tile_isolation(self):
        tile=bytes(TILE_BYTES)
        source=synthetic_atlas([tile]*UPLOADS)
        pixels=decode_atlas(source)
        changed=bytearray(pixels[5])
        changed[1234] ^= 1
        pixels[5]=bytes(changed)
        rebuilt,_=repack_atlas(source,pixels)
        actual=decode_atlas(rebuilt)
        self.assertEqual(actual,pixels)
        self.assertEqual(sum(a!=b for a,b in zip(actual,[tile]*UPLOADS)),1)

    def test_malformed_packets_rejected(self):
        for blob in (b"", b"\xff", b"\x01\x00\xff", b"\x00"):
            with self.subTest(blob=blob.hex()):
                with self.assertRaises(FormatError):
                    decode_stream(blob)
        valid=encode_stream(bytes(TILE_BYTES))
        with self.assertRaises(FormatError):
            decode_stream(valid+bytes(4))


if __name__ == "__main__":
    unittest.main()
