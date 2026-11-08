#!/usr/bin/env python3
"""Produce independent ISS26 v0.9.4 XOR-sector patch using only published v0.9.3
XOR masks and 36 verified upload-list pointer corrections.

No copyrighted original PS1 image, graphics or BIOS are needed on the CI
runner. Mode2 Form1 EDC/ECC deltas are linear in the changed pointer bytes.
The resulting .iss26p is independently applicable to the unmodified original
European Track 01 (not layered on v0.9.3).
"""
import argparse
import csv
import hashlib
import struct
from pathlib import Path

OLD_SHA = '76BF3C02881FAE1B0C1874A9856E1B556E2760857F64609AF5B489EBBFD1167E'
NEW_SHA = '70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE'
CLEAN_SHA = 'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'
RESULT_SHA = 'DF547EACFC8B65EF9409C3220E546968BF842C8F412D2685F8EA5F78C99422BB'
SECTOR = 2352
edc_lut = []
for i in range(256):
    x = i
    for _ in range(8):
        x = (x >> 1) ^ (0xD8018001 if (x & 1) else 0)
    edc_lut.append(x)
forward = [0] * 256
backward = [0] * 256
for i in range(256):
    j = ((i << 1) ^ (0x11D if i & 128 else 0)) & 255
    forward[i] = j
    backward[i ^ j] = i

def edc(data):
    x = 0
    for v in data:
        x = (x >> 8) ^ edc_lut[(x ^ v) & 255]
    return x.to_bytes(4, 'little')

def ecc(data, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    assert len(data) >= size
    result = bytearray(major_count * 2)
    for major in range(major_count):
        pos = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            v = data[pos]
            pos += minor_inc
            if pos >= size:
                pos -= size
            a ^= v
            b ^= v
            a = forward[a]
        a = backward[forward[a] ^ b]
        result[major] = a
        result[major + major_count] = a ^ b
    return result

def pointer_correction(old, new, second):
    difference = bytearray(SECTOR)
    previous = struct.pack('<I', old)
    corrected = struct.pack('<I', new)
    for position in ((24, 28) if second else (24,)):
        for i in range(4):
            difference[position + i] = previous[i] ^ corrected[i]
    difference[2072:2076] = edc(difference[16:2072])
    source = bytearray(difference[12:2076])
    source[:4] = bytes(4)  # Mode2 Form1 ECC address is zeroed
    p = ecc(source, 86, 24, 2, 86)
    difference[2076:2248] = p
    difference[2248:2352] = ecc(source + p, 52, 43, 86, 88)
    return difference

def build(base, csv_path, dest):
    data = base.read_bytes()
    assert hashlib.sha256(data).hexdigest().upper() == OLD_SHA, "Base release SHA mismatch"
    assert data[:8] == b'ISS26X01', "Wrong XOR patch signature"
    count, = struct.unpack_from('<I', data, 8)
    assert count == 1412 and len(data) == 12 + count * (36 + SECTOR)
    patched = bytearray(data)
    offsets = {}
    for i in range(count):
        offset = 12 + i * (36 + SECTOR)
        sector, = struct.unpack_from('<I', data, offset)
        assert sector not in offsets
        offsets[sector] = offset + 36
    with csv_path.open(newline='', encoding='utf-8') as f:
        fixes = list(csv.DictReader(f))
    assert len(fixes) == 36
    seen = set()
    for fix in fixes:
        sector = int(fix['lba'])
        assert sector in offsets and sector not in seen
        seen.add(sector)
        assert fix['second_pointer'] in ('0', '1')
        corr = pointer_correction(int(fix['old_pointer'], 16),
                                  int(fix['new_pointer'], 16),
                                  fix['second_pointer'] == '1')
        start = offsets[sector]
        for i in range(SECTOR):
            patched[start + i] ^= corr[i]
    sha = hashlib.sha256(patched).hexdigest().upper()
    assert sha == NEW_SHA, f"New independent patch SHA mismatch: {sha}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(patched)
    print(f"PASS: {len(fixes)} pointer repairs, {count} independent clean-original sectors")
    print(f"Patch SHA256: {sha}")
    print(f"Required clean Track01 SHA256: {CLEAN_SHA}")
    print(f"Expected fully restored Track01 SHA256: {RESULT_SHA}")

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--base', required=True, type=Path)
    p.add_argument('--fixes', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    build(a.base, a.fixes, a.output)
