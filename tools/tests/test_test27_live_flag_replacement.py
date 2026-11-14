#!/usr/bin/env python3
"""Synthetic VRAM transactions; no emulator, disc or network required."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test27_live_flag_replacement as live

class Fake:
    def __init__(self,raw,paused=True,fail_at=None):
        self.raw=raw; self.on_pause=paused; self.fail_at=fail_at; self.writes=0
    def paused(self): return self.on_pause
    def vram(self): return self.raw
    def write(self,r,data):
        self.writes+=1
        if self.writes==self.fail_at:
            raise OSError("simulated failure")
        self.raw=live.replaced(self.raw,r,data)

def sample():
    raw=bytes(1024*512*2)
    for i,r in enumerate(live.GUARDS,1):
        raw=live.replaced(raw,r,bytes([i])*r.w*r.h*2)
    return raw,{r:live.sha(live.extract(raw,r)) for r in live.GUARDS}

class LiveTests(unittest.TestCase):
    def test_actual_candidate_replaces_only_four_rectangles(self):
        raw,guards=sample()
        fake=Fake(raw)
        with tempfile.TemporaryDirectory() as d:
            backup=Path(d)/"back.json"
            report=live.apply(fake,backup,guards)
            self.assertEqual(fake.writes,4)
            self.assertTrue(report["all_other_vram_bytes_unchanged_while_paused"])
            self.assertFalse(report["game_patch_built"])
            before,after=live.read_backup(backup,guards)
            for r in live.WRITES:
                self.assertEqual(live.extract(fake.raw,r),after[r])
            for r in (live.CAPE_ATLAS,live.BOSNIA_ATLAS):
                self.assertEqual(live.extract(fake.raw,r),live.extract(raw,r))
            live.rollback(fake,before,after)
            self.assertEqual(fake.raw,raw)
    def test_wrong_match_refuses_writes(self):
        raw,guards=sample()
        fake=Fake(raw)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                live.apply(fake,Path(d)/"bad.json")
            self.assertEqual(fake.writes,0)
            self.assertFalse((Path(d)/"bad.json").exists())
    def test_running_emulator_refuses_writes(self):
        raw,guards=sample()
        fake=Fake(raw,paused=False)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                live.apply(fake,Path(d)/"back.json",guards)
            self.assertEqual(fake.writes,0)
    def test_partial_failure_restores_original_vram(self):
        raw,guards=sample()
        fake=Fake(raw,fail_at=2)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,"original four rectangles restored"):
                live.apply(fake,Path(d)/"back.json",guards)
            self.assertEqual(fake.raw,raw)
    def test_restore_refuses_unrelated_new_stage(self):
        raw,guards=sample()
        fake=Fake(raw)
        plan=live.make_plan(raw,guards)
        before={r:live.extract(raw,r) for r in live.WRITES}
        fake.raw=live.replaced(raw,live.BOSNIA_STAGE,bytes(896))
        with self.assertRaisesRegex(ValueError,"no longer rollback-safe"):
            live.rollback(fake,before,plan)
        self.assertEqual(fake.writes,0)
    def test_no_atlas_writes_and_dimensions(self):
        plan=live.artwork()
        self.assertEqual(set(plan),set(live.WRITES))
        self.assertEqual(sum(len(x) for x in plan.values()),1856)
        for r in live.WRITES:
            self.assertEqual(len(plan[r]),r.w*r.h*2)
        with self.assertRaises(ValueError):
            live.replaced(bytes(1024*512*2),live.CAPE_STAGE,b"x")
    def test_refuse_existing_rollback_file(self):
        raw,guards=sample()
        fake=Fake(raw)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"back.json"
            path.write_text("keep it")
            with self.assertRaises(FileExistsError):
                live.apply(fake,path,guards)
            self.assertEqual(fake.writes,0)
            self.assertEqual(path.read_text(),"keep it")

if __name__=="__main__":
    unittest.main()
