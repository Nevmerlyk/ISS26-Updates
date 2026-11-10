import unittest
from stage6_vram_bosnia_verify import extract_tile,compare,VRAM_BYTE_COUNT,FULL_PCSX_CAPTURE_BYTES,STYLE_X,STYLE_Y,WIDTH_WORDS
class TestVRAM(unittest.TestCase):
 def test_strided_tile_extract(self):
  b=bytearray(VRAM_BYTE_COUNT)
  source=bytes((i%251)+1 for i in range(28*32))
  for j in range(28):
   start=((STYLE_Y+j)*WIDTH_WORDS+STYLE_X)*2
   b[start:start+32]=source[j*32:(j+1)*32]
  self.assertEqual(extract_tile(bytes(b)),source)
  self.assertTrue(compare(bytes(b),source)['same_pixel_data'])
  self.assertTrue(compare(bytes(b)+bytes([255])*VRAM_BYTE_COUNT,source)['same_pixel_data'])
  self.assertFalse(compare(bytes(b),source[::-1])['same_pixel_data'])
 def test_wrong_size_rejected(self):
  with self.assertRaises(ValueError):extract_tile(bytes(10))
 def test_oob_rejected(self):
  with self.assertRaises(ValueError):extract_tile(bytes(VRAM_BYTE_COUNT),1020,320,16,28)
if __name__=='__main__':unittest.main()
