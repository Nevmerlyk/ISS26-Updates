import unittest,struct,hashlib
from stage7_gdc_bosnia_patch import get_source,update_tile,split_guarded_edits,BASELOAD,ART_NBYTES
from wecodec_stage5 import encode,decode

class Stage7Tests(unittest.TestCase):
    def test_known_load_base(self):
        self.assertEqual(BASELOAD,0x800C8000)
    def test_full_tile_preserves_neighbors(self):
        original=bytes([0xAA])*8192
        art=bytes([0x12])*ART_NBYTES
        result,changed=update_tile(original,art)
        self.assertEqual(changed,ART_NBYTES)
        self.assertEqual(result[:4096],original[:4096])
        for y in range(128):
            row=result[y*64:y*64+64]
            if 64<=y<92:
                self.assertEqual(row[:32],art[(y-64)*32:(y-63)*32])
                self.assertEqual(row[32:],original[y*64+32:y*64+64])
            else:self.assertEqual(row,original[y*64:y*64+64])
    def test_gpu_source_pointer_and_capacity(self):
        raw=b"".join(hashlib.sha256(i.to_bytes(4,"little")).digest() for i in range(256))
        packed=encode(raw)
        self.assertEqual(decode(packed,8192)[0],raw)
        buf=bytearray(14000)
        buf[64:64+len(packed)]=packed
        c=11000
        struct.pack_into('<6HI',buf,c,10,864,256,32,128,0,BASELOAD+64)
        struct.pack_into('<6HI',buf,c+16,10,832,384,32,128,0,BASELOAD+64+len(packed)+2)
        off,cap,used,art,cmd=get_source(bytes(buf))
        self.assertEqual(off,64)
        self.assertEqual(used,len(packed))
        self.assertEqual(cap,len(packed)+2)
    def test_rejects_misaligned_source(self):
        b=bytearray(9000)
        struct.pack_into('<6HI',b,8500,10,864,256,32,128,0,BASELOAD+3)
        struct.pack_into('<6HI',b,8516,10,832,384,32,128,0,BASELOAD+2000)
        with self.assertRaises(ValueError):get_source(bytes(b))
    def test_rejects_bad_neighbor_record(self):
        b=bytearray(9000)
        struct.pack_into('<6HI',b,8500,10,864,256,32,128,0,BASELOAD+64)
        struct.pack_into('<6HI',b,8516,10,960,384,32,128,0,BASELOAD+2000)
        with self.assertRaises(ValueError):get_source(bytes(b))
    def test_edits_split_at_exact_form1_boundary(self):
        lo,hi=b'X'*140,b'Y'*140
        edits=split_guarded_edits(5000,2000,lo,hi,'fixture')
        self.assertEqual(len(edits),2)
        self.assertEqual([len(bytes.fromhex(e['expected_hex'])) for e in edits],[48,92])
        self.assertEqual(edits[0]['raw_offset']//2352,5000)
        self.assertEqual(edits[1]['raw_offset']//2352,5001)
    def test_reject_bad_art(self):
        with self.assertRaises(ValueError):update_tile(bytes(8192),bytes(ART_NBYTES-1))

if __name__=='__main__':unittest.main()
