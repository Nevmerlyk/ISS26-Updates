"""No copyrighted game data: synthetic tests for the guarded Cape Verde assembler."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_v095_targeted_name_overlay import (
    build, validate_manifest, read_patch, correct_xor_parity, RECORD, SECTOR)
from build_v094_pointer_repair import edc, ecc

LBA=8200

def sector_with_correct_parity():
    raw=bytearray(SECTOR)
    raw[:12]=b"\0"+b"\xff"*10+b"\0"
    raw[15]=2
    raw[24]=0xA5
    raw[25]=0x12
    raw[2072:2076]=edc(raw[16:2072])
    payload=bytearray(raw[12:2076])
    payload[:4]=bytes(4)
    ep=bytes(ecc(payload,86,24,2,86))
    raw[2076:2248]=ep
    raw[2248:2352]=ecc(payload+ep,52,43,86,88)
    return bytes(raw)

def patch_fixture(clean:bytes):
    lbas=[LBA]+list(range(10000,10000+1491))
    data=bytearray(b"ISS26X01"+struct.pack("<I",len(lbas)))
    for lba in lbas:
        guard=hashlib.sha256(clean).digest() if lba==LBA else bytes(32)
        mask=bytearray(SECTOR)
        mask[24]=1 if lba==LBA else 0x17
        correct_xor_parity(mask)
        data+=struct.pack("<I",lba)+guard+mask
    return bytes(data)

def request(lba=LBA,offset=24,before="a4",after="fe",resource="T_NAME_E.BIN"):
    return {
        "schema_version":1, "target_label":"Cape Verde",
        "target_screen":"prematch_team_name",
        "edits":[{"lba":lba,"resource":resource,"sector_offset":offset,
                  "expected_patched_hex":before,"replacement_patched_hex":after}]
    }

class NameOverlayTests(unittest.TestCase):
    def test_valid_name_atlas_delta_preserves_all_non_target_sectors(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            clean=sector_with_correct_parity()
            game=root/"clean.bin"
            with game.open("wb") as f:
                f.truncate((LBA+1)*SECTOR)
                f.seek(LBA*SECTOR)
                f.write(clean)
            source_patch=patch_fixture(clean)
            src=root/"base.iss26p"
            src.write_bytes(source_patch)
            manifest=root/"edit.json"
            manifest.write_text(json.dumps(request()))
            output=root/"candidate.iss26p"
            report=root/"report.json"
            expected_track=hashlib.sha256(game.read_bytes()).hexdigest().upper()
            base_sha=hashlib.sha256(source_patch).hexdigest().upper()
            result=build(game,src,manifest,output,report,
                         expected_clean_sha=expected_track,
                         expected_patch_sha=base_sha,expected_records=1492)
            self.assertEqual(result["changed_atlas_sectors"],[LBA])
            self.assertEqual(result["untouched_records_count"],1491)
            self.assertFalse(result["visual_spelling_or_spacing_verified"])
            old=read_patch(source_patch,base_sha,1492)
            new=read_patch(output.read_bytes(),result["output_patch_sha256"],1492)
            for lba in old:
                if lba!=LBA:
                    self.assertEqual(new[lba],old[lba])
            old_mask=old[LBA][32:]
            mask=new[LBA][32:]
            self.assertEqual(clean[24]^old_mask[24],0xA4)
            self.assertEqual(clean[24]^mask[24],0xFE)
            self.assertEqual(mask[:24],bytes(24))
            valid=bytearray(mask)
            correct_xor_parity(valid)
            self.assertEqual(mask,bytes(valid))
            self.assertEqual((root/"clean.bin").read_bytes()[-SECTOR:],clean)

    def test_reject_any_flag_or_stadium_sector(self):
        for lba in [5328,6089,6256,11087,16549]:
            with self.assertRaisesRegex(ValueError,"outside T_NAME"):
                validate_manifest(request(lba=lba))

    def test_reject_bad_atlas_mapping_and_missing_phase(self):
        with self.assertRaisesRegex(ValueError,"does not match"):
            validate_manifest(request(resource="T_NAME_F.BIN"))
        q=request()
        q["target_screen"]="stadium_flag"
        with self.assertRaisesRegex(ValueError,"Only prematch"):
            validate_manifest(q)

    def test_reject_corrupt_bounds_or_no_op(self):
        with self.assertRaisesRegex(ValueError,"boundary"):
            validate_manifest(request(offset=2072))
        with self.assertRaisesRegex(ValueError,"No-op"):
            validate_manifest(request(before="a4",after="a4"))
        with self.assertRaisesRegex(ValueError,"boundary"):
            validate_manifest(request(offset=23))

    def test_reject_overlapping_edits(self):
        q=request()
        q["edits"].append(q["edits"][0].copy())
        with self.assertRaisesRegex(ValueError,"Overlapping"):
            validate_manifest(q)

if __name__=="__main__":
    unittest.main()
