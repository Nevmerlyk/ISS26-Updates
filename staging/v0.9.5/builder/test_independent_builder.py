"""Synthetic disc and audited-plan tests; no commercial game ROM required."""
import base64
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent/"flags_source"))
from independent_xor import (
    SECTOR, DATA_OFFSET, Disc, Record, parse_patch,
    recalc_form1, recalc_form2, verify_form1, xor_bytes, sha256_path
)
from build_v095 import (TARGET_COUNTRIES, STYLE_TABLES, CLUT_FIRST,
                        national_clut_offset, validate_plan, patch_flag_stream,
                        _pixel_delta_stays_within_flags)
from wecodec import encode

def mode2_sector(payload: bytes = b"", *, form2: bool = False) -> bytes:
    sec=bytearray(SECTOR)
    sec[:12] = b"\x00"+b"\xff"*10+b"\x00"
    sec[15] = 2
    sec[18] = 0x20 if form2 else 0x08
    sec[22] = sec[18]
    size = 2324 if form2 else 2048
    sec[24:24+len(payload)] = payload
    if len(payload)>size:raise ValueError("payload exceeds sector user bytes")
    (recalc_form2 if form2 else recalc_form1)(sec)
    return bytes(sec)

def iso_rec(lba, length, name, directory=False):
    ident=name if isinstance(name,bytes) else name.encode("ascii")
    size=33+len(ident)
    if size%2:size+=1
    record=bytearray(size)
    record[0]=size
    struct.pack_into("<I",record,2,lba)
    struct.pack_into(">I",record,6,lba)
    struct.pack_into("<I",record,10,length)
    struct.pack_into(">I",record,14,length)
    record[25]=2 if directory else 0
    struct.pack_into("<H",record,28,1)
    struct.pack_into(">H",record,30,1)
    record[32]=len(ident)
    record[33:33+len(ident)]=ident
    return bytes(record)

class DiscTests(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        self.addCleanup(self.work.cleanup)
        root=Path(self.work.name)
        self.original=root/"original.bin"
        blocks=[mode2_sector() for _ in range(31)]
        pvd=bytearray(2048)
        pvd[0]=1; pvd[1:6]=b"CD001"
        pvd[156:156+34]=iso_rec(20,2048,b"\x00",True)
        blocks[16]=mode2_sector(pvd)
        directory=iso_rec(20,2048,b"\x00",True)+iso_rec(20,2048,b"\x01",True)+iso_rec(21,2048,"BIN;1")
        blocks[20]=mode2_sector(directory)
        blocks[21]=mode2_sector(b"ORIGINAL")
        blocks[22]=mode2_sector(b"Q"*2048)
        blocks[23]=mode2_sector(b"Z"*2300,form2=True)
        self.original.write_bytes(b"".join(blocks))
        self.clean_sha=sha256_path(self.original)
        self.base={}
    def disc(self):
        return Disc(self.original,self.base,expected_sha=self.clean_sha,
                    expected_size=self.original.stat().st_size)

    def test_mode2_form1_and_form2_parity(self):
        for form2 in (False,True):
            sector=bytearray(mode2_sector(b"football",form2=form2))
            self.assertTrue(sector[18]&0x20 if form2 else not (sector[18]&0x20))
            if form2:
                previous=bytes(sector[2348:2352])
                sector[100] ^= 17
                recalc_form2(sector)
                self.assertNotEqual(bytes(sector[2348:2352]),previous)
            else:
                self.assertTrue(verify_form1(sector))
                sector[29] ^= 11
                self.assertFalse(verify_form1(sector))
                recalc_form1(sector)
                self.assertTrue(verify_form1(sector))

    def test_iso_index_and_resource_write_only_one_form1_data_sector(self):
        with self.disc() as d:
            self.assertEqual(d.iso_files()["BIN"],(21,2048))
            original=d.read_file(21,2048)
            new=bytearray(original);new[0:3]=b"NEW"
            d.write_file(21,original,bytes(new),"only test flag data")
            self.assertEqual(d.read_file(21,3),b"NEW")
            self.assertEqual(d.clean_sector(21)[24:32],b"ORIGINAL")
            self.assertTrue(verify_form1(d.patched_sector(21)))
            result=d.export(Path(self.work.name)/"synthetic.iss26p")
            self.assertEqual(result["record_count"],1)
            recs=parse_patch((Path(self.work.name)/"synthetic.iss26p").read_bytes(),
                             expected_sha=result["patch_sha256"],disc_sectors=31)
            self.assertEqual(recs[21].original_sha,
                             hashlib.sha256(d.clean_sector(21)).digest())
            self.assertEqual(xor_bytes(d.clean_sector(21),recs[21].delta),
                             d.patched_sector(21))

    def test_mode2_form2_resource_extension_and_parity(self):
        with self.disc() as d:
            file_data=d.read_file(22,2048+2300)
            self.assertEqual(file_data[0],ord("Q"))
            self.assertEqual(file_data[-1],ord("Z"))
            altered=bytearray(file_data)
            altered[-5:]=b"FLAGS"
            d.write_file(22,file_data,bytes(altered),"mixed form resource")
            self.assertEqual(d.read_file(22,len(file_data))[-5:],b"FLAGS")
            self.assertEqual(d.patched_sector(22),d.clean_sector(22))
            form2=bytearray(d.patched_sector(23))
            old=bytes(form2)
            recalc_form2(form2)
            self.assertEqual(bytes(form2),old)

    def test_mismatched_original_and_baseline_fail_closed(self):
        with self.assertRaises(ValueError):
            Disc(self.original,{},expected_sha="00"*32,
                 expected_size=self.original.stat().st_size)
        fake={21:Record(bytes(32),bytes([1])*SECTOR)}
        with self.assertRaisesRegex(ValueError,"clean sector digest"):
            Disc(self.original,fake,expected_sha=self.clean_sha,
                 expected_size=self.original.stat().st_size)

    def test_clut_cross_sector_correctness(self):
        self.assertEqual(national_clut_offset(0),CLUT_FIRST)
        for slot in range(1,54):
            self.assertNotEqual(national_clut_offset(slot)%SECTOR,2072)
            self.assertEqual(national_clut_offset(slot)%SECTOR>=24,True)
        with self.disc() as d:
            start=2070 + 21*SECTOR
            d.write_form1_sequence(start,b"ABCDEF","cross boundary flag palette")
            self.assertEqual(d.read_form1_sequence(start,6),b"ABCDEF")
            self.assertEqual(d.patched_sector(21)[2070:2072],b"AB")
            self.assertEqual(d.patched_sector(22)[24:28],b"CDEF")
            self.assertTrue(verify_form1(d.patched_sector(21)))
            self.assertTrue(verify_form1(d.patched_sector(22)))

    def test_single_flag_stream_modifies_only_authorized_tile(self):
        # Style #0 begins at (832*4,256); synthetic upload is exactly its
        # 64x28 rectangle. Restrict all edits to this style.
        old=bytes([0x11])* (16*2*28)
        new=bytes([0x22])*len(old)
        compressed=encode(old)
        resource=bytearray(5000)
        resource[64:64+len(compressed)]=compressed
        struct.pack_into("<6HI",resource,3100,10,832,256,16,28,0,0x800F0000+64)
        edit={
            "resource":"BIN/DATSEL.BIN","context":"selection",
            "record_offset":3100,"load_base":0x800F0000,
            "allocated_end":3099,
            "decoded_before_sha256":hashlib.sha256(old).hexdigest().upper(),
            "decoded_after_sha256":hashlib.sha256(new).hexdigest().upper(),
            "decoded_after_b64":base64.b64encode(new).decode("ascii"),
            "styles":[0],"countries":["senegal"]
        }
        after,changed=patch_flag_stream(bytes(resource),edit)
        self.assertGreater(changed,0)
        self.assertEqual(after[3100:],bytes(resource[3100:]))
        bad=dict(edit);bad["styles"]=[1]
        with self.assertRaisesRegex(ValueError,"OUTSIDE"):
            patch_flag_stream(bytes(resource),bad)

    def test_require_17_pinned_palettes_and_runtime_evidence(self):
        plan={
            "schema_version":1,"version":"0.9.5","flags_only":True,
            "base_patch_sha256":"70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE",
            "styles":{c:1 for c in TARGET_COUNTRIES},
            "palettes":{c:[0]+[0x7FFF]*15 for c in TARGET_COUNTRIES},
            "streams":[{"resource":"BIN/DATSEL.BIN"}],
            "confirmed_contexts":["selection","prematch","stadium","match_hud","edit_mode"],
            "runtime_evidence":"PCSX-Redux GPU trace ID 123"
        }
        validate_plan(plan)
        bad=dict(plan);bad["styles"]={"bosnia":10}
        with self.assertRaisesRegex(ValueError,"all 17"):
            validate_plan(bad)
        bad=dict(plan);bad["palettes"]={c:[1]*16 for c in TARGET_COUNTRIES}
        with self.assertRaisesRegex(ValueError,"transparent"):
            validate_plan(bad)
        bad=dict(plan);bad["confirmed_contexts"]=["selection"]
        with self.assertRaisesRegex(ValueError,"Missing evidence"):
            validate_plan(bad)

if __name__=="__main__":
    unittest.main()
