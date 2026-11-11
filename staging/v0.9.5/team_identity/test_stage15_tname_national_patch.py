import unittest
import numpy as np
from pathlib import Path
from stage15_tname_national_patch import (NAMES,draw_native_style_text,label_lines,unpack4,pack4,get_original_tiles,TRACK,BASELINE,FILES,PatchedDisc)

class Stage15NameAtlasTests(unittest.TestCase):
 def test_national_mapping_bijective_and_sprite_range(self):
  assert len(NAMES)==17
  cells=[divmod(53-s,4) for s in NAMES]
  self.assertEqual(len(set(cells)),17)
  self.assertTrue(all(0<=a<=13 and 0<=b<4 for a,b in cells))
 def test_national_text_cannot_overflow_128x32_sprite(self):
  for s,n in NAMES.items():
   with self.subTest(slot=s,label=n):
    p=draw_native_style_text(n)
    self.assertEqual(p.shape,(32,128))
    self.assertTrue(np.any(p))
    self.assertFalse(np.any(p>=16))
    self.assertTrue(len(label_lines(n))<=2)
    ys,xs=np.where(p!=0)
    self.assertLessEqual(int(xs.max()),127)
    self.assertLessEqual(int(ys.max()),31)
 def test_4bpp_roundtrip(self):
  p=draw_native_style_text('Bosnia')
  assert np.array_equal(unpack4(pack4(np.tile(p,(4,1)))),np.tile(p,(4,1)))
 def test_pre_match_name_source_26_native_chunks(self):
  d=PatchedDisc(TRACK,BASELINE,verify=False)
  try:
   b=d.logical(FILES['T_NAME_E']['lba'],0,FILES['T_NAME_E']['size'],True)
   table,chunks,rows=get_original_tiles(b)
   self.assertEqual(table,0xDA10)
   self.assertEqual(len(chunks),26)
   self.assertEqual(sum(int(np.count_nonzero(i))>0 for i in chunks),26)
  finally:d.close()

if __name__=='__main__':unittest.main()
