#!/usr/bin/env python3
"""Repair only corrupted transparent palette entries in v0.9.4 XOR patch.

Input: official independent clean-original v0.9.4 ISS26X01 patch (no BIN).
Output: independent clean-original experimental v0.9.5 candidate XOR patch.

User-provided clean and v0.9.4 disc images were checked independently on
2026-11-08: clean national CLUT entry zero is 0x0000 for all 54 slots, but
v0.9.4 overwrote 16 neighbours' entry zero. Exact output and patch hashes
are pinned to prevent incorrectly publishing a changed archive.

This does NOT fix the 4bpp flag artwork, styles 52-60, world-map geometry,
or prove compatibility with all game screens.
"""
from __future__ import annotations
import argparse
import hashlib
import struct
from pathlib import Path

from build_v094_pointer_repair import edc, ecc

SECTOR = 2352
RECORD = 4 + 32 + SECTOR
PALETTE_START = 0xBF3B38
BASE_PATCH_SHA = "70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE"
RESULT_PATCH_SHA = "CA1910F84EDADB1DCCA3177CEA70F550A6DBDD17173ACBFDB9644F9141ED7404"
RESULT_TRACK_SHA = "26EC92C768CA0C41795E0B91F7554ADD1E6D2258E03216FCEF23CD2B8F93BA5A"


def physical_palette_zero_positions():
    # The 54 national palette entries have 16 16-bit colors each, packed into
    # the Form1 user data (2048 bytes/sector). Skip per-sector ECC/EDC.
    physical = PALETTE_START
    for slot in range(54):
        yield slot, physical
        for _ in range(16):
            physical += 2
            if physical % SECTOR == 2072:
                physical = ((physical // SECTOR) + 1) * SECTOR + 24


def sector_correction(changes: dict[int, bytes]) -> bytes:
    """Linear EDC and ECC correction for a set of 2-byte Mode2 Form1 edits."""
    delta = bytearray(SECTOR)
    for offset, value in changes.items():
        if not 24 <= offset < 2071 or len(value) != 2:
            raise ValueError("Correction outside Form1 user data")
        delta[offset:offset + 2] = value
    delta[2072:2076] = edc(delta[16:2072])
    source = bytearray(delta[12:2076])
    source[:4] = bytes(4)
    p = ecc(source, 86, 24, 2, 86)
    delta[2076:2248] = p
    delta[2248:2352] = ecc(source + p, 52, 43, 86, 88)
    return bytes(delta)


def build(base: Path, target: Path) -> tuple[list[int], list[int]]:
    raw = base.read_bytes()
    if hashlib.sha256(raw).hexdigest().upper() != BASE_PATCH_SHA:
        raise ValueError("v0.9.4 base patch checksum mismatch")
    if raw[:8] != b"ISS26X01":
        raise ValueError("wrong patch magic")
    num = struct.unpack_from("<I", raw, 8)[0]
    if num != 1412 or len(raw) != 12 + num * RECORD:
        raise ValueError("v0.9.4 record count or size mismatch")
    positions = {}
    previous = -1
    for i in range(num):
        start = 12 + i * RECORD
        lba, = struct.unpack_from("<I", raw, start)
        if lba <= previous:
            raise ValueError("unsorted/duplicate raw sectors")
        previous = lba
        positions[lba] = start + 36
    corrections = {}
    fixed_slots = []
    for slot, phys in physical_palette_zero_positions():
        lba, offset = divmod(phys, SECTOR)
        if not 24 <= offset < 2071:
            raise ValueError("broken palette offset mapping")
        if lba not in positions:
            raise ValueError(f"national palette LBA {lba} not in official XOR patch")
        delta_start = positions[lba]
        current_xor = raw[delta_start + offset:delta_start + offset + 2]
        if current_xor == bytes(2):
            continue
        fixed_slots.append(slot)
        corrections.setdefault(lba, {})[offset] = current_xor
    expected_slots = [1, 2, 4, 18, 20, 23, 25, 26, 27, 28, 31, 40, 43, 44, 50, 52]
    if fixed_slots != expected_slots:
        raise ValueError(f"Unexpected corrupt palette-zero slots: {fixed_slots}")
    output = bytearray(raw)
    for lba, changes in corrections.items():
        start = positions[lba]
        correction = sector_correction(changes)
        for j, mask in enumerate(correction):
            output[start + j] ^= mask
    sha = hashlib.sha256(output).hexdigest().upper()
    if sha != RESULT_PATCH_SHA:
        raise ValueError(f"Candidate XOR patch checksum mismatch: {sha}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    return fixed_slots, sorted(corrections)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    fixed, sectors = build(args.base, args.output)
    print("PASS: independently-applicable national-palette candidate")
    print("Repaired national slots:", fixed)
    print("Repaired CD sector LBAs:", sectors)
    print("Expected output Track01 SHA256:", RESULT_TRACK_SHA)
    print("Patch SHA256:", RESULT_PATCH_SHA)
