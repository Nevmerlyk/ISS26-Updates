"""Test14 VRAM name probe regressions: synthetic 4bpp buffers only."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_v095_name_vram_origin import FIRST,SECOND,V1,V2,TPAGE,CLUT,pixel,vram_4bpp,exact_matches,bbox


def edit(buf:bytearray,w:int,x:int,y:int,v:int)->None:
    at=(y*w+x)//2
    shift=4*(x&1)
    buf[at]=(buf[at]&~(15<<shift))|(v<<shift)


class VRAMNames(unittest.TestCase):
    def test_vram_name_geometry_and_palette_location(self):
        self.assertEqual(TPAGE,523)
        self.assertEqual(CLUT,31939)
        self.assertEqual((CLUT&63)*16,48)
        self.assertEqual(CLUT>>6,499)
        self.assertEqual(FIRST,(128,40,128,16))
        self.assertEqual(SECOND,(128,56,88,16))

    def test_extract_pixel_exactly_in_legacy_and_modern_vram(self):
        for size in (V1,V2):
            raw=bytearray(size)
            target=bytearray(128*16//2)
            edit(target,128,2,2,7)
            edit(target,128,59,13,15)
            for x,y,p in ((2,2,7),(59,13,15)):
                u=128+x; v=40+y
                off=(v*1024+704+(u//4))*2
                w=int.from_bytes(raw[off:off+2],"little")
                shift=(u%4)*4
                w=(w&~(15<<shift))|(p<<shift)
                raw[off:off+2]=w.to_bytes(2,"little")
            self.assertEqual(vram_4bpp(bytes(raw),FIRST),bytes(target))
            self.assertEqual(bbox(bytes(target),128),[2,2,58,12])

    def test_unique_source_only_when_not_ambiguous(self):
        tiles=[bytearray(8192) for _ in range(26)]
        crop=bytearray(88*16//2)
        for y in range(16):
            for x in range(88):
                idx=(x*7+y*11)%15+1
                edit(crop,88,x,y,idx)
                edit(tiles[4],128,22+x,57+y,idx)
        actual=exact_matches(bytes(crop),88,list(map(bytes,tiles)))
        self.assertEqual(actual,[{"tile":4,"x":22,"y":57}])
        self.assertEqual(exact_matches(bytes(len(crop)),88,list(map(bytes,tiles))),[])

    def test_missing_size_rejected(self):
        with self.assertRaises(ValueError):
            vram_4bpp(bytes(12),FIRST)


if __name__=="__main__":
    unittest.main()
