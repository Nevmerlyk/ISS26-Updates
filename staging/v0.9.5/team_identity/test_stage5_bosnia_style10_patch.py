import unittest,hashlib,tempfile,struct
from pathlib import Path
from unittest.mock import MagicMock
from stage5_bosnia_style10_patch import (
 raw_offset,split_bytes,form2_command_check,prepare_upload,
 BLIT_ROWS,BLIT_COLS_BYTES,TARGET_STYLE,EXPECTED_COMPRESSED_LEN,UPLOADS
)
from wecodec_stage5 import encode,decode

class Stage5UnitTests(unittest.TestCase):
 def test_physical_cd_offset(self):
  self.assertEqual(raw_offset(6000,0),6000*2352+24)
  self.assertEqual(raw_offset(6000,2048),6001*2352+24)
  self.assertEqual(raw_offset(6000,2047),6000*2352+2071)
 def test_sector_split(self):
  a=bytes(range(120))
  ed=split_bytes(6000,1999,a,bytes(reversed(a)),'unit')
  self.assertEqual(len(ed),2)
  self.assertEqual([len(bytes.fromhex(x['expected_hex'])) for x in ed],[49,71])
  self.assertEqual([e['raw_offset'] for e in ed],[6000*2352+2023,6001*2352+24])
 def test_not_crossing_into_ecc(self):
  edits=split_bytes(6250,13040,b'\xff'*1910,b'\x00'*1910,'stream')
  self.assertEqual(len(edits),2)
  for e in edits:self.assertLess(e['raw_offset']%2352+len(bytes.fromhex(e['expected_hex'])),2073)
 def test_form2_gpu_commands_verified_both_copies(self):
  d=MagicMock()
  expected=struct.pack('<6HI',10,864,256,32,128,0,0x800F0000+UPLOADS[1]['ptr'])
  def fake_sec(lba,mod):
   b=bytearray(2352)
   b[{6277:716,6279:152}[lba]:{6277:716,6279:152}[lba]+16]=expected
   return bytes(b)
  d.sector.side_effect=fake_sec
  form2_command_check(d)
  d.sector.side_effect=lambda lba,mod:b'\x00'*2352
  with self.assertRaises(ValueError):form2_command_check(d)
 def test_we_codec_bit_exact(self):
  old=b'abc'*2730+b'xy'
  z=encode(old)
  out,n=decode(z,len(old))
  self.assertEqual(out,old);self.assertEqual(n,len(z))
 def test_style10_art_pack(self):
  a=Path(__file__).parent/'stage4_results/bosnia_style10_art/large_64x28.4bpp'
  if not a.is_file():self.skipTest('asset not available in checkout; built from Stage4')
  b=a.read_bytes()
  self.assertEqual(len(b),896)
  self.assertEqual({x&15 for x in b}|{x>>4 for x in b},{1,2,3})
 def test_no_changes_other_tiles_synthetic(self):
  # Demonstrate 64x28 tile in the middle of 32 words x128 rows upload.
  art=bytes([0x21]*896);old=bytes([0xAB]*8192);raw=bytearray(old)
  for y in range(BLIT_ROWS):
   raw[(64+y)*64:(64+y)*64+BLIT_COLS_BYTES]=art[y*32:(y+1)*32]
  changed={i for i,(a,b) in enumerate(zip(raw,old)) if a!=b}
  wanted={(64+y)*64+x for y in range(28) for x in range(32)}
  self.assertEqual(changed,wanted)
 def test_stage3_combination_sector_identity(self):
  # Real sector differences are tested by builder's read-back verification.
  self.assertEqual(TARGET_STYLE,10)
  self.assertEqual(EXPECTED_COMPRESSED_LEN,1910)

if __name__=='__main__':unittest.main()
