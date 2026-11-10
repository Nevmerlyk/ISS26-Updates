import sys,unittest,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage11_prematch_forensics import find_ram_region,find_vram_region,count_word,SPAN

class Stage11Tests(unittest.TestCase):
 def test_ram_present_exactly(self):
  ram=random.Random(112233).randbytes(SPAN)
  prefix=b'\x10\x0A'*(25)
  state=prefix+ram+b'xyz'
  self.assertEqual(find_ram_region(state,ram),len(prefix))
 def test_ram_mismatch_rejected(self):
  ram=random.Random(112233).randbytes(SPAN)
  state=b'head'+ram[:-1]+b'X'
  with self.assertRaises(ValueError):find_ram_region(state,ram)
 def test_vram_source_from_stable_chunks(self):
  vram=bytearray(random.Random(44).randbytes(SPAN))
  snap=bytearray(vram)
  # Two frames differ only in the rendered front framebuffer region.
  snap[0:51200]=b'\x00'*51200
  prefix=b'HEADERFIELD'*73
  state=prefix+snap+b'TRAILER'
  start,checks=find_vram_region(state,bytes(vram))
  self.assertEqual(start,len(prefix))
  self.assertTrue(checks[1]['matched'])
 def test_word_case_insensitive(self):
  self.assertEqual(count_word(b'Russia|RUSSIA|russia',b'russia'),3)

if __name__=='__main__':unittest.main()
