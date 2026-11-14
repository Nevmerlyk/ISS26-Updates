#!/usr/bin/env python3
"""ISS26 Test27: VERIFY the four flag staging MIPS call-sites on CLEAN EU Track01.

Read-only, offline, no patch. Fail closed if a source opcode differs from the
clean 2001 European disc. This establishes *where to instrument*, not which
routine caused an observed zero mask. Test25's style-table assignments are
tested separately; a side effect at LoadImage/StoreImage remains possible.

Known original paths:
  SELECT overlay base = 0x8007F000, file LBA 850, bytes 233864
  MoveImage (VRAM->VRAM) wrapper 0x8003884C
  StoreImage (VRAM->RAM) wrapper 0x800387EC
  LoadImage (RAM->VRAM) wrapper 0x8003878C
  home/away flag staging source 0x800CC600 + 896 bytes each
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import struct
from v095_static_prematch_ram_trace import (
    BASE_SHA, SELECT_SHA, SELECT_LBA, SELECT_BYTES, SECTOR,
    sha, hash_file, resource,
)

SELECT_RAM = 0x8007F000
STAGE_CALLS = (
    ("store_staging_vram_to_ram", 0x80092F58, 0x800387EC),
    ("load_staging_ram_to_vram", 0x8009312C, 0x8003878C),
    ("move_home_style_to_staging", 0x80093338, 0x8003884C),
    ("move_away_style_to_staging", 0x800933CC, 0x8003884C),
)
STYLE_MAP_RAW_OFFSETS = (0x1D6F48,0x1E94CC,0x224C50,0x4AD4B8,0x575864)
STYLE_MAP_LENGTH = 78
NATIONAL_SLOTS = 54
CLUB_SLOTS = 24
DEFAULT_HOME_STAGE=(560,0)
DEFAULT_AWAY_STAGE=(560,28)
STAGE_WORD_WIDTH=16
STAGE_WORD_HEIGHT=28

def jal_target(pc: int, opcode: int) -> int:
    if opcode >> 26 != 3:
        raise ValueError(f"Not a MIPS JAL at {hex(pc)}: {hex(opcode)}")
    return ((pc+4)&0xF0000000) | ((opcode&0x3ffffff)<<2)

def verify_select_calls(select: bytes) -> list[dict]:
    if len(select) != SELECT_BYTES:
        raise ValueError("Unexpected SELECT overlay size")
    result = []
    for name, pc, expected_target in STAGE_CALLS:
        at = pc - SELECT_RAM
        if at < 0 or at + 4 > len(select) or at%4:
            raise ValueError(f"Invalid SELECT PC: {hex(pc)}")
        op,=struct.unpack_from("<I",select,at)
        target=jal_target(pc,op)
        if target != expected_target:
            raise ValueError(f"Unexpected flag MIPS target {name}: "
                             f"{hex(target)} != {hex(expected_target)}")
        result.append({
            "stage":name,
            "pc":f"0x{pc:08X}",
            "jal_opcode":f"0x{op:08X}",
            "target_function":f"0x{target:08X}",
            "trace_before_pc":f"0x{pc-8:08X}",
            "trace_after_pc":f"0x{pc+8:08X}",
            "classification":("VRAM_to_RAM" if "store" in name else
                              "RAM_to_VRAM" if "load" in name else "VRAM_to_VRAM")
        })
    return result

def verify_five_original_style_maps(raw: bytes) -> dict:
    if len(raw) < max(STYLE_MAP_RAW_OFFSETS)+STYLE_MAP_LENGTH:
        raise ValueError("Original raw Track01 truncated")
    rows=[]
    for offset in STYLE_MAP_RAW_OFFSETS:
        slots=raw[offset:offset+STYLE_MAP_LENGTH]
        if len(slots)!=STYLE_MAP_LENGTH:
            raise ValueError("Incomplete style mapping")
        # Historical clean original style7 Bosnia/club10 are pinned by Test25.
        if slots[30]!=7 or slots[54]!=10:
            raise ValueError("Expected clean Bosnia/style7 and club54/style10 mapping")
        rows.append({
            "raw_disc_byte_offset":offset,
            "national_slot30_style":slots[30],
            "club_slot54_style":slots[54],
            "national_slots":NATIONAL_SLOTS,
            "club_slots":CLUB_SLOTS,
            "style55_used_anywhere":55 in slots,
        })
    return {"five_style_tables":rows,
            "style55_used_in_any_table":any(x["style55_used_anywhere"] for x in rows),
            "club54_original_style10_preserved":all(x["club_slot54_style"]==10 for x in rows)}

def inspect_clean_disc(path: Path) -> dict:
    # This purposefully requires exact user-owned original bytes; never
    # down-samples a possibly already patched source.
    if hash_file(path)!=BASE_SHA:
        raise ValueError("Track01 SHA256 mismatch; expected CLEAN EU original")
    with path.open("rb") as f:
        select=resource(f,SELECT_LBA,SELECT_BYTES)
        # Read only five 78-byte table records, not a 550+ MB disc image.
        tiny=bytearray(max(STYLE_MAP_RAW_OFFSETS)+STYLE_MAP_LENGTH)
        for offset in STYLE_MAP_RAW_OFFSETS:
            f.seek(offset)
            record=f.read(STYLE_MAP_LENGTH)
            if len(record)!=STYLE_MAP_LENGTH:
                raise ValueError("Truncated original style table")
            tiny[offset:offset+STYLE_MAP_LENGTH]=record
        raw=bytes(tiny)
    if sha(select)!=SELECT_SHA:
        raise ValueError("SELECT overlay SHA256 mismatch")
    calls=verify_select_calls(select)
    maps=verify_five_original_style_maps(raw)
    return {
        "schemaVersion":1,
        "kind":"Test27 clean EU MIPS flag transfer-chain static guard",
        "sha256CleanTrack01":BASE_SHA,
        "sha256CleanSelect":SELECT_SHA,
        "calls":calls,
        "originalMapping":maps,
        "expected_atlas_style55":[816,368],
        "expected_home_stage_words":[*DEFAULT_HOME_STAGE,STAGE_WORD_WIDTH,STAGE_WORD_HEIGHT],
        "expected_away_stage_words":[*DEFAULT_AWAY_STAGE,STAGE_WORD_WIDTH,STAGE_WORD_HEIGHT],
        "expected_RAM_buffer_start":"0x800CC600",
        "expected_RAM_buffer_end":"0x800CCCFF",
        "stage_last_writer_proven":False,
        "cause_of_Bosnia_lower_12_row_zero_mask_proven":False,
        "game_patch_built":False,
        "original_disc_modified":False,
        "note":"These are verified callsite locations only; inspect the runtime "
               "arguments before selecting a fix."
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--original-track01",required=True,type=Path)
    p.add_argument("--report",required=True,type=Path)
    a=p.parse_args()
    output=inspect_clean_disc(a.original_track01)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    print("PASS: 4 MIPS wrapper callsites and 5 original style maps verified")
    print("NO PATCH: last runtime writer and flags still require source attribution")

if __name__=="__main__":
    main()
