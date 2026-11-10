"""Independent clean-original ISS26X01 patch generation and Mode2 sector safety.

No game binaries are shipped with this module. The owner supplies the exact
European SLES-03321 Track01, the official 0.9.4 XOR patch, and audited flag
edits. Staging never mutates the original or the official baseline patch.
"""
from __future__ import annotations

import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
from dataclasses import dataclass
from typing import Iterator

SECTOR = 2352
USER = 2048
DATA_OFFSET = 24
DISC_BYTES = 496_156_752
CLEAN_SHA = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
BASE_V094_SHA = "70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE"
BASE_RESULT_SHA = "DF547EACFC8B65EF9409C3220E546968BF842C8F412D2685F8EA5F78C99422BB"
MAGIC = b"ISS26X01"
ENTRY_SIZE = 4 + 32 + SECTOR
MAX_SECTORS = 8192
MAX_PATCH_BYTES = 32 * 1024 * 1024

edc_lut = []
for i in range(256):
    value = i
    for _ in range(8):
        value = (value >> 1) ^ (0xD8018001 if value & 1 else 0)
    edc_lut.append(value)
forward = [0] * 256
backward = [0] * 256
for i in range(256):
    j = ((i << 1) ^ (0x11D if i & 128 else 0)) & 255
    forward[i] = j
    backward[i ^ j] = i

def edc(data: bytes) -> bytes:
    value = 0
    for b in data:
        value = (value >> 8) ^ edc_lut[(value ^ b) & 255]
    return value.to_bytes(4, "little")

def ecc(data: bytes, major: int, minor: int, mult: int, inc: int) -> bytes:
    size = major * minor
    if len(data) < size:
        raise ValueError("ECC input too short")
    parity = bytearray(2 * major)
    for m in range(major):
        pos = (m >> 1) * mult + (m & 1)
        a = b = 0
        for _ in range(minor):
            val = data[pos]
            pos = (pos + inc) % size
            a ^= val
            b ^= val
            a = forward[a]
        a = backward[forward[a] ^ b]
        parity[m] = a
        parity[m + major] = a ^ b
    return bytes(parity)

def recalc_form1(data: bytearray) -> None:
    if len(data) != SECTOR or data[15] != 2 or (data[18] & 0x20):
        raise ValueError("CD sector is not Mode2 Form1")
    if data[16:20] != data[20:24]:
        raise ValueError("Mode2 duplicated subheader mismatch")
    data[2072:2076] = edc(data[16:2072])
    source = bytearray(data[12:2076])
    source[:4] = bytes(4)
    p = ecc(source, 86, 24, 2, 86)
    data[2076:2248] = p
    data[2248:2352] = ecc(source + p, 52, 43, 86, 88)

def verify_form1(data: bytes) -> bool:
    try:
        rebuilt = bytearray(data)
        recalc_form1(rebuilt)
        return rebuilt == data
    except ValueError:
        return False

@dataclass(frozen=True)
class Record:
    original_sha: bytes
    delta: bytes

def parse_patch(data: bytes, *, expected_sha: str = BASE_V094_SHA,
                disc_sectors: int = DISC_BYTES // SECTOR) -> dict[int, Record]:
    if hashlib.sha256(data).hexdigest().upper() != expected_sha:
        raise ValueError("Official v0.9.4 patch SHA256 mismatch")
    if data[:8] != MAGIC or len(data) < 12:
        raise ValueError("Wrong ISS26X01 signature")
    count = struct.unpack_from("<I", data, 8)[0]
    if not 1 <= count <= MAX_SECTORS or len(data) != 12 + count * ENTRY_SIZE:
        raise ValueError("Wrong independent patch length or record count")
    result = {}
    previous = -1
    for i in range(count):
        pos = 12 + i * ENTRY_SIZE
        sector = struct.unpack_from("<I", data, pos)[0]
        if not previous < sector < disc_sectors:
            raise ValueError("Unsorted/duplicated/out-of-range sector")
        previous = sector
        digest = data[pos + 4:pos + 36]
        mask = data[pos + 36:pos + ENTRY_SIZE]
        if not any(mask):
            raise ValueError("Empty XOR record")
        result[sector] = Record(digest, mask)
    return result

def sha256_path(filename: Path) -> str:
    sha = hashlib.sha256()
    with filename.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest().upper()

def xor_bytes(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("XOR buffers differ in length")
    return bytes(x ^ y for x, y in zip(a, b))

class Disc:
    def __init__(self, original: Path, baseline: dict[int, Record], *,
                 expected_sha: str = CLEAN_SHA, expected_size: int = DISC_BYTES):
        self.original = Path(original)
        self.source_hash = sha256_path(self.original)
        if self.source_hash != expected_sha or self.original.stat().st_size != expected_size:
            raise ValueError("Wrong original Track 01 (need European SLES-03321 SHA256/size)")
        self._f = self.original.open("rb")
        self._map = mmap.mmap(self._f.fileno(), 0, access=mmap.ACCESS_READ)
        self.base = baseline
        self.edited: dict[int, bytearray] = {}
        self.changed_ranges: list[dict] = []
        for index, item in baseline.items():
            b = self.clean_sector(index)
            if hashlib.sha256(b).digest() != item.original_sha:
                self.close()
                raise ValueError(f"v0.9.4 clean sector digest mismatch at LBA {index}")
    def close(self):
        if getattr(self, "_map", None) is not None:
            self._map.close()
            self._map = None
        if getattr(self, "_f", None) is not None:
            self._f.close()
            self._f = None
    def __enter__(self): return self
    def __exit__(self, *_): self.close()
    def clean_sector(self, lba: int) -> bytes:
        start = lba * SECTOR
        if lba < 0 or start + SECTOR > len(self._map):
            raise ValueError(f"bad sector LBA {lba}")
        return self._map[start:start + SECTOR]
    def patched_sector(self, lba: int) -> bytes:
        if lba in self.edited: return bytes(self.edited[lba])
        original = self.clean_sector(lba)
        return xor_bytes(original, self.base[lba].delta) if lba in self.base else original
    def read_user(self, lba: int) -> bytes:
        sector = self.patched_sector(lba)
        if sector[15] != 2 or sector[18] & 0x20 or sector[16:20] != sector[20:24]:
            raise ValueError(f"not an ISO Form1 user sector at {lba}")
        return sector[DATA_OFFSET:DATA_OFFSET + USER]
    def read_file(self, lba: int, length: int) -> bytes:
        if length < 0: raise ValueError("negative file length")
        data = bytearray()
        for n in range((length + USER - 1)//USER):
            data.extend(self.read_user(lba+n))
        return bytes(data[:length])
    def write_file(self, lba: int, old: bytes, new: bytes, label: str):
        if len(old) != len(new):
            raise ValueError("Edited ISO file must keep its existing length")
        changed = 0
        for page in range((len(old) + USER - 1)//USER):
            start = page*USER
            a, b = old[start:start+USER], new[start:start+USER]
            if a == b: continue
            sector_id = lba + page
            if self.read_user(sector_id)[:len(a)] != a:
                raise ValueError("Resource changed since verified edit was staged")
            sector = self.edited.setdefault(sector_id, bytearray(self.patched_sector(sector_id)))
            for j,(x,y) in enumerate(zip(a,b)):
                if x != y:
                    sector[DATA_OFFSET+j] = y
                    changed += 1
            recalc_form1(sector)
            if not verify_form1(sector):
                raise AssertionError("Form1 EDC/ECC check failed")
        self.changed_ranges.append({"label":label,"lba":lba,
                                    "changed_bytes":changed})
    def write_raw(self, position: int, replacement: bytes, label: str):
        """Write only user data bytes (style/CLUT), never CD headers or audio."""
        if not replacement: raise ValueError("empty raw edit")
        for i,b in enumerate(replacement):
            absolute=position+i
            lba,at=divmod(absolute,SECTOR)
            if not DATA_OFFSET<=at<DATA_OFFSET+USER:
                raise ValueError("Raw write would hit CD header/ECC or audio")
            sec=self.edited.setdefault(lba,bytearray(self.patched_sector(lba)))
            sec[at]=b
        for lba in sorted({(position+i)//SECTOR for i in range(len(replacement))}):
            recalc_form1(self.edited[lba])
        self.changed_ranges.append({"label":label,"raw_offset":position,
                                    "changed_bytes":len(replacement)})
    def read_physical(self, position: int, count: int) -> bytes:
        out = bytearray()
        for address in range(position,position+count):
            lba,offset = divmod(address,SECTOR)
            out.append(self.patched_sector(lba)[offset])
        return bytes(out)
    def iso_files(self) -> dict[str, tuple[int, int]]:
        pvd = self.read_user(16)
        if pvd[1:6] != b"CD001": raise ValueError("Not the expected ISO9660 disc")
        rec = pvd[156:156+pvd[156]]
        seen = set()
        found = {}
        def visit(prefix: str, record: bytes):
            if len(record) < 34: raise ValueError("Malformed ISO record")
            extent = struct.unpack_from("<I", record, 2)[0]
            size = struct.unpack_from("<I", record, 10)[0]
            if not (record[25] & 2):
                found[prefix.upper()] = extent, size
                return
            if extent in seen:return
            seen.add(extent)
            listing=self.read_file(extent,size)
            off=0
            while off < len(listing):
                span=listing[off]
                if span==0:
                    off=((off//USER)+1)*USER
                    continue
                child=listing[off:off+span]
                if len(child)!=span or span<34:raise ValueError("Malformed ISO directory")
                n=child[32]
                ident=child[33:33+n].decode("ascii","strict")
                off+=span
                if ident in ("\x00","\x01"):continue
                name=ident.split(";")[0].upper()
                visit(prefix+"/"+name if prefix else name,child)
        visit("",rec)
        return found
    def expected_result_hash(self) -> str:
        sha=hashlib.sha256()
        for lba in range(len(self._map)//SECTOR):
            sha.update(self.patched_sector(lba))
        return sha.hexdigest().upper()
    def export(self, output: Path) -> dict:
        """One single independently applicable clean-original XOR patch."""
        combined={}
        for sector in sorted(set(self.base)|set(self.edited)):
            clean=self.clean_sector(sector)
            target=self.patched_sector(sector)
            if clean==target:continue
            combined[sector]=Record(hashlib.sha256(clean).digest(),xor_bytes(clean,target))
        if len(combined)>MAX_SECTORS:raise ValueError("Too many changed CD sectors")
        if 12+len(combined)*ENTRY_SIZE>MAX_PATCH_BYTES:raise ValueError("Patch is too large")
        destination=Path(output)
        if destination.resolve() == self.original.resolve():
            raise ValueError("Cannot overwrite original game")
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_name(destination.name+".partial")
        if temporary.exists():raise FileExistsError("Stale partial patch exists")
        try:
            with temporary.open("wb") as stream:
                stream.write(MAGIC)
                stream.write(struct.pack("<I",len(combined)))
                for sector,record in combined.items():
                    stream.write(struct.pack("<I",sector))
                    stream.write(record.original_sha)
                    stream.write(record.delta)
                stream.flush()
                os.fsync(stream.fileno())
            output_sha=sha256_path(temporary)
            # An independent re-reader checks magic, every sector digest and mask.
            verify=parse_patch(temporary.read_bytes(),expected_sha=output_sha,
                               disc_sectors=len(self._map)//SECTOR)
            if verify!=combined:raise AssertionError("Patch failed independent decode")
            resulting=self.expected_result_hash()
            os.replace(temporary,destination)
        finally:
            if temporary.exists():temporary.unlink()
        return {"patch":str(destination),"patch_sha256":output_sha,
                "result_track01_sha256":resulting,
                "clean_track01_sha256":self.source_hash,
                "record_count":len(combined),
                "bytes":destination.stat().st_size,
                "flag_edit_regions":self.changed_ranges}
