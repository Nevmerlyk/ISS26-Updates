#!/usr/bin/env python3
"""ISS26 0.9.5: original-disc static MIPS prematch flag path audit.

Read-only: verifies clean EU PS1 Track01, derives two SELECT.BIN GPU
upload sites and their RAM buffers. Optionally verifies a standalone
ISS26X01 patch (or ZIP containing one) and determines whether it alters
the upload-call code. No user game bytes are redistributed.
"""
import argparse
import hashlib
import json
import struct
import zipfile
from pathlib import Path

BASE_SHA = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
SELECT_SHA = "3B1A20E3A3B75092ABF2CD73F459EF90CA9866B38010DF1EFBC7D7B96884A866"
SLES_SHA = "868EF5E9B3AE90D689498DC5BAF0C10D8C3D3DCD608D17A4569512259CC7ACB9"
SECTOR = 2352
SYNC = bytes.fromhex("00ffffffffffffffffffff00")
SELECT_LBA, SELECT_BYTES = 850, 233864
SLES_LBA, SLES_BYTES = 24, 339968
UPLOAD_SITES = (0x13F38, 0x1410C)
GPU_CALLS = (0x800387EC, 0x8003878C)

def sha(raw):
    return hashlib.sha256(raw).hexdigest().upper()

def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for piece in iter(lambda: f.read(8 * 1024 * 1024), b""):
            digest.update(piece)
    return digest.hexdigest().upper()

def sector(f, lba):
    f.seek(lba * SECTOR)
    raw = f.read(SECTOR)
    if len(raw) != SECTOR or raw[:12] != SYNC:
        raise ValueError("Invalid raw CD sector at LBA " + str(lba))
    if raw[15] != 2 or raw[18] & 0x20:
        raise ValueError("Expected Mode2 Form1 at LBA " + str(lba))
    return raw[24:2072]

def resource(f, lba, size):
    return b"".join(sector(f, k) for k in range(lba, lba + (size + 2047) // 2048))[:size]

def instruction(buf, offset):
    return struct.unpack_from("<I", buf, offset)[0]

def read_patch(path):
    if path.suffix.lower() != ".zip":
        return path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        candidates = [i for i in archive.infolist()
                      if i.filename.lower().endswith(".iss26p") and not i.is_dir()]
        if len(candidates) != 1 or candidates[0].file_size > 24 * 1024 * 1024:
            raise ValueError("ZIP must contain one bounded .iss26p patch")
        return archive.read(candidates[0])

def check_patch(track, patch_path, original_select):
    data = read_patch(patch_path)
    if len(data) < 12 or data[:8] != b"ISS26X01":
        raise ValueError("Unsupported independent patch format")
    count = struct.unpack_from("<I", data, 8)[0]
    record_size = 4 + 32 + SECTOR
    if not 0 < count < 10000 or len(data) != 12 + count * record_size:
        raise ValueError("Invalid patch length or record count")
    modified = bytearray(original_select)
    touched = []
    last = -1
    with track.open("rb") as original:
        for index in range(count):
            at = 12 + index * record_size
            lba = struct.unpack_from("<I", data, at)[0]
            if not last < lba < track.stat().st_size // SECTOR:
                raise ValueError("Duplicate, unordered or out-of-bounds sector")
            last = lba
            original.seek(lba * SECTOR)
            sector_bytes = original.read(SECTOR)
            if hashlib.sha256(sector_bytes).digest() != data[at + 4:at + 36]:
                raise ValueError("Clean sector SHA256 guard failed at LBA " + str(lba))
            if SELECT_LBA <= lba < SELECT_LBA + (SELECT_BYTES + 2047) // 2048:
                start = (lba - SELECT_LBA) * 2048
                mask = data[at + 36 + 24:at + 36 + 2072]
                for k, value in enumerate(mask):
                    if start + k < len(modified):
                        modified[start + k] ^= value
                touched.append(lba)
    deltas = [sum(x != y for x, y in
                  zip(original_select[o:o+40], modified[o:o+40]))
              for o in UPLOAD_SITES]
    return {"source_patch": patch_path.name,
            "patch_sha256": sha(data),
            "record_count": count,
            "changed_select_lbas": touched,
            "verified_clean_sector_guards": True,
            "gpu_upload_code_changed_byte_counts": deltas,
            "gpu_upload_code_unchanged": not any(deltas),
            "modified_select_sha256": sha(modified),
            "original_disc_modified": False}

def audit(track, patch=None):
    if hash_file(track) != BASE_SHA:
        raise ValueError("Wrong original game: expected clean European Track01")
    with track.open("rb") as f:
        select = resource(f, SELECT_LBA, SELECT_BYTES)
        sles = resource(f, SLES_LBA, SLES_BYTES)
    if sha(select) != SELECT_SHA or sha(sles) != SLES_SHA:
        raise ValueError("Original SELECT/SLES file checksum mismatch")

    found = []
    for off in range(0, len(select) - 64, 4):
        if instruction(select, off) != 0x3C05800C:
            continue
        if instruction(select, off+4) != 0x34A5C600:
            continue
        ins = [(i, instruction(select, i)) for i in range(off+8, off+60, 4)]
        if not all(any(w == v for _, w in ins) for v in
                   (0x24020230, 0x24020010, 0x24020038)):
            raise ValueError("Incomplete 64x56 GPU rectangle near " + hex(off))
        calls = [0x80000000 + ((w & 0x3FFFFFF) << 2)
                 for _, w in ins if w >> 26 == 3
                 and 0x80000000 + ((w & 0x3FFFFFF) << 2) in GPU_CALLS]
        if len(calls) != 1:
            raise ValueError("Missing verified GPU call near " + hex(off))
        found.append({
            "select_file_offset": off, "runtime_pc_at_lui": hex(0x8007F000 + off),
            "source_ram": "0x800CC600",
            "next_flag_ram": "0x800CC980",
            "vram_rectangle": [560, 0, 16, 56],
            "indexed_4bpp_size_pixels": [64, 56],
            "source_length_bytes": 1792,
            "gpu_function_pc": hex(calls[0])})
    if [x["select_file_offset"] for x in found] != list(UPLOAD_SITES):
        raise ValueError("Unexpected number/positions of SELECT flag upload sites")
    for target in GPU_CALLS:
        offset = target - 0x80010000 + 0x800
        if instruction(sles, offset) != 0x27BDFFE0:
            raise ValueError("GPU upload wrapper signature mismatch")
    loader_pc = 0x8001C5E4
    if instruction(sles, loader_pc - 0x80010000 + 0x800) != 0x3C068006:
        raise ValueError("Async loader signature mismatch")
    return {
        "schema_version": 1,
        "clean_track_sha256": BASE_SHA,
        "sles_sha256": SLES_SHA, "select_sha256": SELECT_SHA,
        "verified_sites": found,
        "async_resource_gate_pc": hex(loader_pc),
        "upstream_flag_buffer_writer_identified": False,
        "optional_candidate_patch": check_patch(track, patch, select) if patch else None,
        "next_capture": {
            "before_gpu_upload_ram": [["0x800CC600", 896], ["0x800CC980", 896]],
            "requested": "Same-frame MIPS CPU PC, GP0 upload, VRAM, active CUE and originating resource ID",
            "caveat": "GPU destination/source match alone does not identify the last writer"
        },
        "original_modified": False,
        "stable_feed_modified": False,
        "test_feed_modified": False}

if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("clean_track", type=Path)
    cli.add_argument("--patch", type=Path, help="Optional independent .iss26p or ZIP")
    cli.add_argument("--output", type=Path, default=Path("ISS26_Test21_StaticFlagTrace.json"))
    a = cli.parse_args()
    result = audit(a.clean_track, a.patch)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("PASS:", len(result["verified_sites"]), "MIPS GPU transfer call sites")
    print("Save:", a.output)
