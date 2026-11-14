#!/usr/bin/env python3
"""Test27 screenshot/CLUT extractor tests on synthetic VRAM only."""
from __future__ import annotations
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_extract_real_flag_pixels as real
from analyze_flag_test26_unified import VRAM_BYTES, atlas_xy
from test27_flag_art_4bpp import candidate

def place(raw: bytearray, x: int, y: int, data: bytes):
    assert len(data)==896
    for row in range(28):
        at=((y+row)*1024+x)*2
        raw[at:at+32]=data[row*32:(row+1)*32]

class RealFlagPixelsTests(unittest.TestCase):
    def make_zip(self, dest: Path, *, vram_bytes=VRAM_BYTES, include=True):
        raw=bytearray(vram_bytes)
        for name,style,stage_xy,clut_xy in real.PAIRS:
            tile,palette,_,_=candidate(name)
            place(raw,*atlas_xy(style),tile)
            if name=="bosnia":
                # Synthesize the exact shape of the real Test26 bottom-12 mask.
                stage=tile[:16*32]+bytes(12*32)
            else:
                stage=tile
            place(raw,*stage_xy,stage)
            p=(clut_xy[1]*1024+clut_xy[0])*2
            raw[p:p+32]=palette
        with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED) as z:
            if include:
                z.writestr(real.EXACT_VRAM_NAME,raw)

    def test_realistic_zip_to_ten_pngs_and_report(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            z=folder/"sample.zip"
            self.make_zip(z)
            output=folder/"pics"
            result=real.inspect_archive(z,output,required_sha=None)
            self.assertEqual(set(result["flags"]),{"bosnia","cape_verde"})
            self.assertTrue(result["flags"]["bosnia"]["diff"]
                            ["is_contiguous_bottom_12_row_mask"])
            self.assertEqual(result["flags"]["bosnia"]["diff"]
                             ["pixel_index_differences"]["source_nonzero_stage_zero"],768)
            self.assertEqual(result["flags"]["cape_verde"]["diff"]
                             ["pixel_index_differences"]["source_nonzero_stage_zero"],0)
            self.assertFalse(result["flags"]["cape_verde"]["diff"]
                             ["is_contiguous_bottom_12_row_mask"])
            self.assertEqual(len(list(output.glob("*.png"))),10)
            self.assertEqual(len(list(output.glob("*.json"))),1)
            self.assertTrue((output/"bosnia_source_stage_diff.png").read_bytes()
                            .startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertFalse(result["source_disc_modified"])
            self.assertFalse(result["update_feed_changed"])

    def test_clut_decodes_actual_little_endian_bgr555(self):
        # 0x7c00 = blue 255; 0x001f = red 255; 0x03e0 = green 255.
        clut=struct.pack("<16H",0,0x7c00,0x001f,0x03e0,*([0]*12))
        rgb=real.decode_bgr555_clut(clut)
        self.assertEqual(rgb[1],(0,0,255))
        self.assertEqual(rgb[2],(255,0,0))
        self.assertEqual(rgb[3],(0,255,0))
        with self.assertRaises(ValueError):
            real.decode_bgr555_clut(b"x")

    def test_missing_or_wrong_zip_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder); z=folder/"sample.zip"
            self.make_zip(z)
            with self.assertRaises(ValueError):
                real.inspect_archive(z,folder/"none")
            self.make_zip(z,include=False)
            with self.assertRaises(ValueError):
                real.inspect_archive(z,folder/"none",required_sha=None)

    def test_diff_distinguishes_modified_introduced_erased_pixels(self):
        stage=[1,0,4,3]+[0]*(64*28-4)
        source=[1,2,0,2]+[0]*(64*28-4)
        _,r=real.diff_indices(stage,source)
        self.assertEqual(r["pixel_index_differences"]["equal"],64*28-3)
        self.assertEqual(r["pixel_index_differences"]["source_nonzero_stage_zero"],1)
        self.assertEqual(r["pixel_index_differences"]["new_nonzero"],1)
        self.assertEqual(r["pixel_index_differences"]["changed_nonzero"],1)
        self.assertFalse(r["is_contiguous_bottom_12_row_mask"])

if __name__=="__main__":
    unittest.main()
