import sys
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_stage_code_audit as audit

def fixture():
    data=bytearray(audit.SELECT_BYTES)
    for _,pc,target in audit.STAGE_CALLS:
        struct.pack_into("<I",data,pc-audit.SELECT_RAM,0x0c000000|((target>>2)&0x3ffffff))
    return data

class StaticStageTest(unittest.TestCase):
    def test_jal_and_delay_slot(self):
        pc=0x80092f58
        data=fixture()
        struct.pack_into("<I",data,pc+4-audit.SELECT_RAM,0x24020038)
        r=audit.window(data,pc,pc+8)
        self.assertEqual(r[0]["target"],"800387EC")
        self.assertTrue(r[1]["lexically_after_control_transfer"])
        self.assertEqual(r[1]["rectangle_or_buffer_constant"],56)
    def test_zero_store_is_only_candidate(self):
        data=fixture()
        altered=bytearray(data)
        at=0x80093000-audit.SELECT_RAM
        struct.pack_into("<I",altered,at,0xae000030)
        with patch.object(audit,"SELECT_SHA",audit.sha(data)):
            result=audit.audit(data,altered)
        self.assertEqual(len(result["changed_instructions_in_window"]),1)
        self.assertEqual(result["candidate_explicit_zero_stores"][0]["store"]["base_register"],"s0")
        self.assertFalse(result["final_stage_writer_proven"])
        self.assertFalse(result["game_code_modified"])
    def test_reject_wrong_wrapper_and_hash(self):
        data=fixture()
        with self.assertRaises(ValueError):
            audit.audit(data,data)
        altered=bytearray(data)
        struct.pack_into("<I",altered,0x800933cc-audit.SELECT_RAM,0)
        with patch.object(audit,"SELECT_SHA",audit.sha(data)):
            with self.assertRaises(ValueError):
                audit.audit(data,altered)
    def test_branch_displacement_and_negative_store(self):
        self.assertEqual(audit.decode(0x80093000,0x1000fffd)["target"],"80092FF8")
        self.assertEqual(audit.decode(0x80093000,0xa7a0fffc)["store"]["offset"],-4)
        self.assertFalse(audit.decode(0x80093000,0xafb00000)["store"]["explicit_zero"])
    def test_unknown_opcode_not_invented(self):
        self.assertTrue(audit.decode(0x80093000,0xffffffff)["instruction"].startswith(".word"))

if __name__=="__main__":
    unittest.main()
