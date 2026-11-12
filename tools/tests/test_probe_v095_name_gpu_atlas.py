"""Synthetic-only tests of the prematch raster-name GPU/ISO probe."""
import hashlib
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from probe_v095_name_gpu_atlas import (
  SECTOR,GPU_BASE,apply_sector,directory_files,normalized_geometry,
  raw_sector,resource_data,upload_lists,user_data,find_original_track,
)

def sector(payload:bytes)->bytes:
    src=bytearray(SECTOR)
    src[:12]=b"\0"+b"\xff"*10+b"\0"
    src[15]=2
    src[24:24+len(payload)]=payload
    return bytes(src)

def dir_record(name:bytes,lba:int,size:int,is_dir:bool)->bytes:
    length=33+len(name)
    if length%2:
        length+=1
    raw=bytearray(length)
    raw[0]=length
    raw[2:6]=lba.to_bytes(4,"little")
    raw[6:10]=lba.to_bytes(4,"big")
    raw[10:14]=size.to_bytes(4,"little")
    raw[14:18]=size.to_bytes(4,"big")
    raw[25]=2 if is_dir else 0
    raw[28:30]=(1).to_bytes(2,"little")
    raw[30:32]=(1).to_bytes(2,"big")
    raw[32]=len(name)
    raw[33:33+len(name)]=name
    return bytes(raw)

class ProbeTests(unittest.TestCase):
    def test_gpu_upload_list_parses_real_descriptor_fields(self):
        raw=bytearray(512)
        struct.pack_into("<I",raw,0,GPU_BASE+0x40)
        struct.pack_into("<HHHHHHI",raw,0x40,
                         9,832,256,16,28,0,GPU_BASE+0x100)
        struct.pack_into("<H",raw,0x50,0xff)
        raw[0x100:0x104]=b"\x01\x02\x03\x04"
        result=upload_lists(bytes(raw))
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["upload_record_count"],1)
        entry=result[0]["uploads"][0]
        self.assertEqual((entry["vram_x_words"],entry["vram_y"]),(832,256))
        self.assertEqual((entry["upload_width_words"],entry["upload_height"]),(16,28))
        self.assertEqual(entry["stream_offset"],0x100)
        self.assertEqual(normalized_geometry(result),[[(9,832,256,16,28)]])

    def test_invalid_gpu_pointer_never_accepted_as_a_list(self):
        raw=bytearray(512)
        struct.pack_into("<I",raw,0,GPU_BASE+0x40)
        struct.pack_into("<HHHHHHI",raw,0x40,
                         9,832,256,16,28,0,GPU_BASE+0x9000)
        struct.pack_into("<H",raw,0x50,0xff)
        self.assertEqual(upload_lists(bytes(raw)),[])

    def test_guarded_xor_sector_never_changes_cd_header(self):
        clean=sector(b"ABC")
        mask=bytearray(SECTOR)
        mask[24]=0x41
        result=apply_sector(clean,25,(hashlib.sha256(clean).digest(),bytes(mask)))
        self.assertEqual(result[:24],clean[:24])
        self.assertEqual(result[24],0)
        self.assertEqual(clean[24],ord("A"))
        with self.assertRaisesRegex(ValueError,"SHA256 mismatch"):
            apply_sector(clean,25,(bytes(32),bytes(mask)))
        mask[17]=1
        with self.assertRaisesRegex(ValueError,"CD header"):
            apply_sector(clean,25,(hashlib.sha256(clean).digest(),bytes(mask)))

    def test_reconstruct_only_named_data_from_mixed_original_and_patch(self):
        disc=bytearray(SECTOR*24)
        first=sector(b"A"*2048)
        second=sector(b"B"*2048)
        disc[20*SECTOR:21*SECTOR]=first
        disc[21*SECTOR:22*SECTOR]=second
        mask=bytearray(SECTOR)
        mask[24]=ord("A")^ord("C")
        changed={20:(hashlib.sha256(first).digest(),bytes(mask))}
        old,new,seen=resource_data(io.BytesIO(disc),20,2500,changed)
        self.assertEqual(len(old),2500)
        self.assertEqual(len(new),2500)
        self.assertEqual(old[:3],b"AAA")
        self.assertEqual(new[:3],b"CAA")
        self.assertEqual(new[2048:2051],b"BBB")
        self.assertEqual(seen,{20})

    def test_autodetect_exact_original_cue_and_reject_test_cue(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            cue=root/"ISS Pro Evolution 2 (Europe) (En,Fr,De).cue"
            original=root/"Track01.bin"
            original.write_bytes(b"test fixture")
            entries=['FILE "Track%02d.bin" BINARY' % i for i in range(1,13)]
            cue.write_text("\n".join(entries),encoding="utf-8")
            self.assertEqual(find_original_track(root),original)
            cue.write_text(entries[0],encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"12-track original"):
                find_original_track(root)

    def test_iso9660_names_resolved_inside_bin_directory(self):
        disc=bytearray(SECTOR*32)
        pvd=bytearray(2048)
        pvd[:7]=b"\x01CD001\x01"
        root=dir_record(b"\x00",20,2048,True)
        pvd[156:156+len(root)]=root
        disc[16*SECTOR:17*SECTOR]=sector(pvd)
        root_data=dir_record(b"BIN",21,2048,True)
        disc[20*SECTOR:21*SECTOR]=sector(root_data)
        folder=b"".join(dir_record(("T_NAME_"+lang+".BIN;1").encode(),22+i,100,False)
                        for i,lang in enumerate("EFG"))
        disc[21*SECTOR:22*SECTOR]=sector(folder)
        files=directory_files(io.BytesIO(disc))
        self.assertEqual(files["BIN/T_NAME_E.BIN"],(22,100))
        self.assertEqual(files["BIN/T_NAME_F.BIN"],(23,100))
        self.assertEqual(files["BIN/T_NAME_G.BIN"],(24,100))

if __name__=="__main__":
    unittest.main()
