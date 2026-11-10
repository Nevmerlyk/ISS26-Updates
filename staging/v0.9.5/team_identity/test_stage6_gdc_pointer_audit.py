"""Pure-data checks of Stage 6's conservative GDC source audit."""
import struct,unittest,tempfile
from pathlib import Path
from stage6_gdc_pointer_audit import read_commands,probe_ptr,parse_inventory,BOSNIA_RECT,SCENE_UPLOAD
from wecodec_stage5 import encode

class Stage6Tests(unittest.TestCase):
    def test_gpu_command_overlap(self):
        raw=bytearray(1024)
        struct.pack_into('<6HI',raw,200,10,864,256,32,128,0,0x800C0030)
        struct.pack_into('<6HI',raw,400,10,832,256,32,128,0,0x800C0050)
        hits=read_commands(raw)
        self.assertEqual(len(hits),1)
        self.assertEqual(tuple(hits[0][x] for x in ['upload_x','upload_y','width_words','height_rows']),SCENE_UPLOAD)
    def test_unrelated_gpu_flag_is_not_bosnia(self):
        raw=bytearray(2048)
        struct.pack_into('<6HI',raw,900,10,832,256,16,64,0,0x800C0080)
        self.assertEqual(read_commands(raw),[])
    def test_valid_compressed_source_requires_exact_output_size(self):
        raw=b'\x11'*8192
        comp=encode(raw)
        blob=bytearray(b'\0'*128+comp)
        while len(blob)%4:blob+=b'\0'
        command_offset=len(blob)
        struct.pack_into('<6HI',blob,0,1,0,0,0,0,0,0) if False else None
        blob+=struct.pack('<6HI',10,864,256,32,128,0,0x800C0000+128)
        cmd=read_commands(blob)[0]
        sources,trials=probe_ptr(bytes(blob),cmd)
        self.assertEqual(len(sources),1)
        self.assertEqual(sources[0]['file_offset'],128)
        self.assertEqual(sources[0]['compressed_bytes'],len(comp))
        self.assertGreaterEqual(trials,1)
    def test_invalid_pointer_is_not_assumed_stream(self):
        raw=bytearray(2048)
        struct.pack_into('<6HI',raw,1000,10,864,256,32,128,0,0x800E58A8)
        cmd=read_commands(raw)[0]
        sources,trials=probe_ptr(raw,cmd)
        self.assertEqual(sources,[])
        self.assertEqual(trials,0)
    def test_inventory_manifest(self):
        path=Path(__file__).parent/'stage6_gdc_extent_eu.txt'
        v=parse_inventory(path)
        self.assertEqual(len(v),34)
        self.assertEqual(v['/BIN/GDC_AD.BIN;1'],(12560,140632))

if __name__=='__main__':unittest.main()
