import io
import struct
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_build_clean_graphics_recovery as recovery
import test27_build_standalone_atlas_candidate as base
from build_v094_pointer_repair import edc
from v095_name_lz_codec import encode_stream,decode_stream_prefix

def raw_sector(payload,form2=False):
    raw=bytearray(2352)
    raw[:12]=bytes.fromhex("00FFFFFFFFFFFFFFFFFFFF00")
    raw[15]=2
    raw[18]=raw[22]=0x20 if form2 else 0
    raw[24:24+len(payload)]=payload
    if form2: raw[2348:2352]=edc(raw[16:2348])
    return bytes(raw)

def resource(raw):
    start=32
    packet=encode_stream(raw,expected_bytes=len(raw))
    # Place terminator in actual packet, reserve only its aligned bytes.
    table=(start+len(packet)+3)&~3
    data=bytearray(table+32)
    struct.pack_into("<I",data,0,0x800F0000+table)
    data[start:start+len(packet)]=packet
    struct.pack_into("<HHHHHHI",data,table,10,0,0,32,128,0,0x800F0000+start)
    struct.pack_into("<H",data,table+16,255)
    return bytes(data)

class RecoveryTests(unittest.TestCase):
    def test_ownership_checks_both_catalogs_and_only_declared_extent(self):
        clean={"BIN/GDC_X.BIN":(100,4096),"BIN/NEXT.BIN":(105,2048)}
        patched=dict(clean)
        patched["BIN/GDC_X.BIN"]=(100,8192)
        lba,owned=recovery.resource_sectors(clean,patched,"BIN/GDC_X.BIN")
        self.assertEqual((lba,owned),(100,{100,101,102,103}))
        patched["BIN/GDC_X.BIN"]=(100,12288)
        with self.assertRaisesRegex(ValueError,"overlapping"):
            recovery.resource_sectors(clean,patched,"BIN/GDC_X.BIN")

    def test_exact_iso_length_restoration_preserves_other_bytes(self):
        old=bytearray(2048)
        old[40:48]=struct.pack("<I",59840)+struct.pack(">I",59840)
        old[48:55]=b"KEEP ME"
        source=io.BytesIO(raw_sector(old))
        records={}
        cp={"BIN/DATSEL3.BIN":{"extent":6250,"size":54948,"lba":0,"offset":40,"flags":0}}
        pp={"BIN/DATSEL3.BIN":{"extent":6250,"size":59840,"lba":0,"offset":40,"flags":0}}
        self.assertEqual(recovery.restore_lengths(source,records,cp,pp,list(cp)),{0})
        self.assertTrue(base.valid_parity(records[0][1]))
        _,r=base.patched_sector(source,0,records)
        expected=bytearray(old)
        expected[40:48]=struct.pack("<I",54948)+struct.pack(">I",54948)
        self.assertEqual(r[24:2072],expected)

    def test_read_only_form2_donor_requires_valid_edc(self):
        a=raw_sector(b"A"*2048)
        b=raw_sector(b"B"*2324,True)
        source=io.BytesIO(a+b)
        self.assertEqual(recovery.donor_projection(source,{},0,4096),b"A"*2048+b"B"*2048)
        broken=bytearray(b); broken[200]^=1
        with self.assertRaisesRegex(ValueError,"EDC"):
            recovery.donor_projection(io.BytesIO(a+broken),{},0,4096)

    def test_valid_non_target_donor_retained_without_descriptor_change(self):
        import random
        rnd=random.Random(28)
        original_data=bytes(rnd.randrange(256) for _ in range(8192))
        prior_data=bytes([0x21])*8192
        original=resource(original_data)
        prior=resource(prior_data)
        output,stats=recovery.retain_valid_donors(original,original,prior,0x800F0000)
        self.assertEqual(len(stats["retained_changed_packets"]),1)
        table,rows=recovery.parse_uploads(output,0x800F0000,0)
        data,_=recovery.stream_span(output,0x800F0000,table,rows,rows[0])
        self.assertEqual(data,prior_data)
        self.assertEqual(len(output),len(original))
        self.assertEqual(output[table:],original[table:])

    def test_bad_or_oversized_donor_stays_clean(self):
        original=resource(bytes([0x21])*8192)
        import random
        rnd=random.Random(29)
        prior=resource(bytes(rnd.randrange(256) for _ in range(8192)))
        result,stats=recovery.retain_valid_donors(original,original,prior,0x800F0000)
        self.assertEqual(result,original)
        self.assertTrue(stats["original_fallback_packets"])

if __name__=="__main__":
    unittest.main()
