#!/usr/bin/env python3
# ISS26 Kit Research. ISO reader and LZ decoder reused from project tools.
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator
from itertools import zip_longest

RAW_SECTOR = 2352
USER_SIZE = 2048
FORM2_USER_SIZE = 2324
USER_START = 24
MAX_RESOURCE_SIZE = 64 * 1024 * 1024
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"
EXPECTED_ORIGINAL_HASH = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
ORIGINAL_CUE = "ISS Pro Evolution 2 (Europe) (En,Fr,De).cue"
FILE_LINE = re.compile(r'^\s*FILE\s+"([^"]+)"\s+BINARY\s*$', re.I | re.M)


@dataclass(frozen=True)
class ISOEntry:
    path: str
    lba: int
    size: int
    is_dir: bool


class ISOError(ValueError):
    pass


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while part := stream.read(4 * 1024 * 1024):
            h.update(part)
    return h.hexdigest().upper()


def original_track_from_cue(cue: Path) -> Path:
    contents = cue.read_text(encoding="utf-8-sig", errors="replace")
    files = FILE_LINE.findall(contents)
    if len(files) != 12:
        raise ISOError(f"Expected 12 FILE entries in CUE; got {len(files)}")
    first = Path(files[0])
    result = first if first.is_absolute() else cue.parent / first
    if not result.is_file():
        raise ISOError("Original Track 01 referenced by CUE is missing")
    return result


class RawPS1ISO:
    def __init__(self, filename: Path):
        self.filename = filename
        self.stream: BinaryIO = filename.open("rb")
        self.length = filename.stat().st_size
        if self.length < RAW_SECTOR * 32 or self.length % RAW_SECTOR:
            self.stream.close()
            raise ISOError("Invalid MODE2/2352 raw BIN length")
        self.sectors = self.length // RAW_SECTOR
        # Some PS1 ISO9660 catalogs contain XA/DA entries referring outside
        # the data track. Such entries must be reported, never read or used to
        # abort an unrelated national-flags inspection.
        self.directory_warnings: list[dict] = []
        self.resource_forms: dict[str, dict[str, int]] = {}

    def fits_track(self, entry: ISOEntry) -> bool:
        # Directories are ISO9660 Form1 (2048 bytes). ISO directory records
        # can also point to Mode2 Form2 (2324-byte) data files, so dividing
        # every file size by 2048 incorrectly marks some valid files as OOB.
        capacity = USER_SIZE if entry.is_dir else FORM2_USER_SIZE
        return (entry.lba >= 0 and entry.size >= 0 and
                entry.lba + math.ceil(entry.size / capacity) <= self.sectors)

    def close(self) -> None:
        self.stream.close()

    def __enter__(self) -> "RawPS1ISO":
        return self

    def __exit__(self, *_args) -> None:
        self.close()

    def raw_sector(self, lba: int) -> bytes:
        if not 0 <= lba < self.sectors:
            raise ISOError(f"LBA out of bounds: {lba}")
        self.stream.seek(lba * RAW_SECTOR)
        raw = self.stream.read(RAW_SECTOR)
        if len(raw) != RAW_SECTOR or raw[:12] != SYNC or raw[15] != 2:
            raise ISOError(f"Invalid PS1 MODE2 sector header at {lba}")
        return raw

    def sector_payload(self, lba: int) -> tuple[bytes, str]:
        raw = self.raw_sector(lba)
        is_form2 = bool(raw[18] & 0x20)
        capacity = FORM2_USER_SIZE if is_form2 else USER_SIZE
        return raw[USER_START:USER_START + capacity], "form2" if is_form2 else "form1"

    def sector(self, lba: int) -> bytes:
        # ISO9660 PVD and directory sectors must be Form1.
        payload, form = self.sector_payload(lba)
        if form != "form1":
            raise ISOError(f"Unexpected Mode2 Form2 in ISO directory: {lba}")
        return payload

    def file_chunks(self, entry: ISOEntry) -> Iterator[bytes]:
        """Stream the declared file bytes using each raw sector's actual XA form."""
        if entry.is_dir:
            raise ISOError("Cannot read a directory as a file")
        if entry.size < 0 or entry.size > MAX_RESOURCE_SIZE:
            raise ISOError(f"Resource size outside audit limit: {entry.path}")
        if not self.fits_track(entry):
            raise ISOError(f"ISO file extent exceeds Track 01: {entry.path}")
        remaining = entry.size
        next_lba = entry.lba
        forms = {"form1": 0, "form2": 0}
        while remaining:
            if next_lba >= self.sectors:
                raise ISOError(f"ISO extent exceeds track while reading {entry.path}")
            payload, form = self.sector_payload(next_lba)
            forms[form] += 1
            amount = min(len(payload), remaining)
            yield payload[:amount]
            remaining -= amount
            next_lba += 1
        self.resource_forms[entry.path] = forms

    def file_blocks(self, entry: ISOEntry, block_size: int = 64 * 1024) -> Iterator[bytes]:
        """Yield equal-sized logical file blocks even for mixed Form1/Form2 files."""
        buffer = bytearray()
        for chunk in self.file_chunks(entry):
            buffer.extend(chunk)
            while len(buffer) >= block_size:
                yield bytes(buffer[:block_size])
                del buffer[:block_size]
        if buffer:
            yield bytes(buffer)

    def extent(self, lba: int, size: int, *, directory: bool = False) -> bytes:
        if size < 0 or size > (4 * 1024 * 1024 if directory else 32 * 1024 * 1024):
            raise ISOError(f"Unsafe extent size: {size}")
        count = math.ceil(size / USER_SIZE)
        if lba < 0 or lba + count > self.sectors:
            raise ISOError(f"ISO extent exceeds track: {lba}+{count}")
        return b"".join(self.sector(lba + i) for i in range(count))[:size]

    @staticmethod
    def read_record(directory: bytes, pos: int) -> tuple[ISOEntry, int] | None:
        length = directory[pos]
        if length == 0:
            return None
        if length < 34 or pos + length > len(directory):
            raise ISOError(f"Malformed ISO9660 directory record at {pos}")
        rec = directory[pos:pos + length]
        lba = int.from_bytes(rec[2:6], "little")
        size = int.from_bytes(rec[10:14], "little")
        if lba != int.from_bytes(rec[6:10], "big"):
            raise ISOError("ISO LBA little/big-endian fields disagree")
        if size != int.from_bytes(rec[14:18], "big"):
            raise ISOError("ISO size little/big-endian fields disagree")
        n = rec[32]
        if 33 + n > len(rec):
            raise ISOError("Malformed ISO filename length")
        raw_name = rec[33:33 + n]
        name = raw_name.decode("ascii", errors="replace")
        if raw_name in (b"\x00", b"\x01"):
            name = "." if raw_name == b"\x00" else ".."
        else:
            name = name.split(";", 1)[0].rstrip(".")
        return ISOEntry(name, lba, size, bool(rec[25] & 0x02)), length

    def list_files(self) -> tuple[dict[str, ISOEntry], str]:
        pvd = self.sector(16)
        if pvd[0] != 1 or pvd[1:6] != b"CD001" or pvd[6] != 1:
            raise ISOError("Primary ISO9660 volume descriptor not found at LBA 16")
        root_record = self.read_record(pvd, 156)
        if root_record is None:
            raise ISOError("Missing ISO9660 root directory entry")
        root = root_record[0]
        volume = pvd[40:72].decode("ascii", errors="replace").strip()
        files: dict[str, ISOEntry] = {}
        seen_directories = set()

        def walk(lba: int, size: int, parent: str, depth: int) -> None:
            if depth > 10 or len(files) > 15000:
                raise ISOError("Suspicious ISO directory nesting")
            if (lba, size) in seen_directories:
                return
            seen_directories.add((lba, size))
            data = self.extent(lba, size, directory=True)
            pos = 0
            while pos < len(data):
                if data[pos] == 0:
                    pos = ((pos // USER_SIZE) + 1) * USER_SIZE
                    continue
                value = self.read_record(data, pos)
                if value is None:
                    pos = ((pos // USER_SIZE) + 1) * USER_SIZE
                    continue
                entry, count = value
                pos += count
                if entry.path in (".", ".."):
                    continue
                path = f"{parent}/{entry.path}" if parent else entry.path
                if path in files:
                    raise ISOError(f"Duplicate ISO path: {path}")
                file_entry = ISOEntry(path, entry.lba, entry.size, entry.is_dir)
                files[path] = file_entry
                if not self.fits_track(file_entry):
                    self.directory_warnings.append({
                        "file": path,
                        "lba": entry.lba,
                        "declared_size": entry.size,
                        "declared_end_sector": entry.lba + math.ceil(
                            entry.size / (USER_SIZE if entry.is_dir else FORM2_USER_SIZE)),
                        "track_sectors": self.sectors,
                        "reason": "ISO9660 extent points beyond Track 01"
                    })
                    # Never traverse an invalid directory or read a stray
                    # extent. Preserve the catalog record as evidence.
                    continue
                if entry.is_dir:
                    walk(entry.lba, entry.size, path, depth + 1)

        walk(root.lba, root.size, "", 0)
        return files, volume

    def content_digest(self, entry: ISOEntry) -> tuple[str, int]:
        if entry.is_dir:
            raise ISOError("Directory cannot be hashed as an ISO data file")
        h = hashlib.sha256()
        for block in self.file_blocks(entry):
            h.update(block)
        return h.hexdigest().upper(), entry.size

    def diff_file(self, entry: ISOEntry, other: "RawPS1ISO", rhs: ISOEntry) -> tuple[int, str, str]:
        sha_a = hashlib.sha256()
        sha_b = hashlib.sha256()
        changed = 0
        # Block alignment is based on logical file bytes, NOT sector count.
        # This correctly compares Form1, Form2 and mixed-form assets.
        for a, b in zip_longest(self.file_blocks(entry), other.file_blocks(rhs),
                                 fillvalue=b""):
            sha_a.update(a)
            sha_b.update(b)
            changed += sum(x != y for x, y in zip(a, b))
            changed += abs(len(a) - len(b))
        return changed, sha_a.hexdigest().upper(), sha_b.hexdigest().upper()


TILE_BYTES=8192
class FormatError(ValueError):
    pass


def decode_stream(data: bytes, *, expected_bytes: int = TILE_BYTES,
                  max_padding: int = 3) -> bytes:
    """LSB-first flags, single-byte literals and three MIPS command families."""
    src = 0
    flags = 0
    out = bytearray()
    while True:
        flags >>= 1
        if not (flags & 0x100):
            if src >= len(data):
                raise FormatError("truncated flag byte")
            flags = 0xFF00 | data[src]
            src += 1
        if src >= len(data):
            raise FormatError("missing token")
        token = data[src]
        if not (flags & 1):
            out.append(token)
            src += 1
        elif token < 0x80:
            if src + 1 >= len(data):
                raise FormatError("truncated long backreference")
            count = (token >> 2) + 3
            distance = ((token & 3) << 8) | data[src + 1]
            src += 2
            if not 1 <= distance <= len(out):
                raise FormatError("invalid long backreference")
            for _ in range(count):
                out.append(out[-distance])
        elif token < 0xC0:
            count = (token >> 4) - 6
            distance = (token & 15) + 1
            src += 1
            if not 1 <= distance <= len(out):
                raise FormatError("invalid short backreference")
            for _ in range(count):
                out.append(out[-distance])
        elif token == 0xFF:
            src += 1
            break
        else:
            count = token - 0xB8
            src += 1
            if src + count > len(data):
                raise FormatError("truncated raw block")
            out.extend(data[src:src + count])
            src += count
        if len(out) > expected_bytes:
            raise FormatError("GPU rectangle overrun")
    if len(out) != expected_bytes:
        raise FormatError(f"wrong output length: {len(out)}")
    if max_padding < 0 or len(data) - src > max_padding or any(data[src:]):
        raise FormatError("unexpected trailing bytes")
    return bytes(out)



# Kit Research v1.1. Read-only correlation, NOT kit ownership proof.
import zipfile
import struct

RAM_SIZE=0x200000
VRAM_SIZE=1024*512*2
MAX_FILE=4*1024*1024
MAX_CAPTURES=48
MAX_ARCHIVES=4
TILE_BYTES=8192
BASES=(0x80000000,0xa0000000)
KNOWN_GPU_BASES=(0x800f0000,0x800c8000)
KIT_HINT=re.compile(r"(?i)(KIT|UNIF|WEAR|MODEL|PLAYER|BODY|SHIRT|TEX|POLY|FACE|GDC|DAT|EDIT|EDT)")

def sha(data):
    return hashlib.sha256(data).hexdigest().upper()

def informative(data):
    if len(data)<64:return False
    sample=data[::max(1,(len(data)+2047)//2048)]
    colors=set(sample)
    return len(colors)>=16 and max(sample.count(i) for i in colors)<len(sample)//2

def anchors(data):
    if len(data)<128:return []
    offsets=sorted(set([0,64,128,256,512,1024,2048,4096]+
                        [((len(data)*i//8)//4)*4 for i in range(1,8)]))
    out=[]
    seen=set()
    for at in offsets:
        if at+128>len(data):continue
        sig=data[at:at+128]
        if sig in seen or not informative(sig):continue
        seen.add(sig);out.append((at,sig))
    return out

def match_ram(data, samples, ram):
    found={}
    for at,sig in samples:
        pos=ram.find(sig)
        count=0
        # Repeated signatures are too ambiguous to establish residency.
        positions=[]
        while pos>=0 and count<5:
            positions.append(pos);count+=1
            pos=ram.find(sig,pos+1)
        if len(positions)>4:continue
        for pos in positions:
            base=pos-at
            if base<0 or base%4 or base>=RAM_SIZE:continue
            if pos+128>len(ram):continue
            found.setdefault(base,set()).add(at)
    result=[]
    for base,offsets in sorted(found.items()):
        # Require distinct, nonoverlapping exact signatures.
        offsets=sorted(offsets)
        independent=[]
        for at in offsets:
            if not independent or at>=independent[-1]+128:independent.append(at)
        if len(independent)<2:continue
        result.append({"ramOffset":base,"ramAddress":f"0x{0x80000000+base:08X}",
                        "exactBytesAtLeast":128*len(independent),
                        "anchorOffsets":independent})
    return result

def gpu_records(data, base):
    lists={}
    for head in range(0,min(32,len(data)-3),4):
        table=struct.unpack_from("<I",data,head)[0]-base
        if table<32 or table%4 or table+16>len(data) or table in lists:continue
        rows=[]
        for j in range(512):
            at=table+j*16
            if at+16>len(data):break
            kind,x,y,w,h,pad,ptr=struct.unpack_from("<6HI",data,at)
            if kind==255:
                if rows:lists[table]=rows
                break
            src=ptr-base
            if not(kind in (0,9,10) and pad==0 and 0<=x<1024 and 0<=y<512
                   and 1<=w<=1024-x and 1<=h<=512-y and 4<=src<table):
                break
            rows.append({"tableOffset":table,"recordOffset":at,"kind":kind,
                         "rectWords":[x,y,w,h],"sourceOffset":src})
    return [row for rows in lists.values() for row in rows]

def vram_rect(vram,x,y,w,h):
    return b"".join(vram[2*((y+i)*1024+x):2*((y+i)*1024+x+w)] for i in range(h))

def gpu_payload(data,row,all_rows):
    x,y,w,h=row["rectWords"]; n=2*w*h; start=row["sourceOffset"]
    stop=min([row["tableOffset"]]+[r["sourceOffset"] for r in all_rows
                                   if r["sourceOffset"]>start])
    if row["kind"]==0:
        if start+n>stop: return None
        return data[start:start+n]
    if row["kind"]!=10 or stop<=start:return None
    try:
        return decode_stream(data[start:stop],expected_bytes=n,max_padding=stop-start)
    except (ValueError,AssertionError,IndexError):
        return None

def vram_match(row,decoded,vram):
    if decoded is None:return None
    x,y,w,h=row["rectWords"]
    if len(decoded)!=2*w*h:return None
    observed=vram_rect(vram,x,y,w,h)
    if observed==decoded:
        return {"match":"exact","bytes":len(decoded),"sha256":sha(decoded)}
    # Partial uploads are retained only as candidates; never claim ownership.
    rows=sum(decoded[2*w*i:2*w*(i+1)]==observed[2*w*i:2*w*(i+1)] and
             informative(decoded[2*w*i:2*w*(i+1)])
             for i in range(h))
    if rows>=4 and rows*2>=h:
        return {"match":"partial_rows","rows":rows,"height":h}
    return None

def read_member(z,member,size):
    if member.file_size!=size:raise ValueError("Unexpected snapshot size")
    with z.open(member) as f:
        data=f.read(size+1)
    if len(data)!=size:raise ValueError("Truncated snapshot")
    return data

def snapshots(paths):
    count=0
    for path in paths:
        with zipfile.ZipFile(path) as z:
            byname={}
            for m in z.infolist():
                if m.filename in byname:raise ValueError("Duplicate ZIP entry")
                byname[m.filename]=m
            for name,m in sorted(byname.items()):
                if not name.endswith("_RAM.bin") or m.file_size!=RAM_SIZE:continue
                label=name[:-8]
                vr=byname.get(label+".vram")
                if vr is None or vr.file_size!=VRAM_SIZE:continue
                if count>=MAX_CAPTURES:return
                count+=1
                yield path.name,label,read_member(z,m,RAM_SIZE),read_member(z,vr,VRAM_SIZE)

def audit_kits(track,paths):
    digest=digest_file(track)
    if digest!=EXPECTED_ORIGINAL_HASH:
        raise ISOError("Clean original Track01 SHA256 mismatch")
    images=list(snapshots(paths))
    rows=[]; skipped=[]; candidates=[]
    with RawPS1ISO(track) as disc:
        files,volume=disc.list_files()
        for name,entry in sorted(files.items()):
            if entry.is_dir:continue
            if not disc.fits_track(entry) or entry.size>MAX_FILE or name.startswith(("SD/","MOVIE/")):
                skipped.append({"resource":name,"size":entry.size,"reason":"outside_track_or_excluded_media_or_size"})
                continue
            try:
                data=b"".join(disc.file_chunks(entry))
            except ISOError as e:
                skipped.append({"resource":name,"reason":str(e)});continue
            samples=anchors(data)
            info={"resource":name,"lba":entry.lba,"size":entry.size,
                  "sha256":sha(data),"filenameHint":bool(KIT_HINT.search(name.split("/")[-1])),
                  "signatureCount":len(samples),"ramMatches":[],"vramMatches":[]}
            # Even files with no name hint are inspected.
            gpu_cache={}
            for archive,label,ram,vram in images:
                hits=match_ram(data,samples,ram)
                for hit in hits:
                    info["ramMatches"].append({"archive":archive,"capture":label,**hit})
                bases=set(KNOWN_GPU_BASES)
                bases.update(b+h["ramOffset"] for h in hits for b in BASES)
                for base in sorted(bases):
                    if base not in gpu_cache:
                        records=gpu_records(data,base)
                        decoded=[(r,gpu_payload(data,r,records)) for r in records]
                        gpu_cache[base]=[(r,p) for r,p in decoded if p is not None and informative(p)]
                    for r,payload in gpu_cache[base]:
                        e=vram_match(r,payload,vram)
                        if e:
                            info["vramMatches"].append({"archive":archive,"capture":label,
                                "resourceBase":f"0x{base:08X}",**r,**e})
            info["ramCaptureCount"]=len({(x["archive"],x["capture"]) for x in info["ramMatches"]})
            info["exactVramCaptureCount"]=len({(x["archive"],x["capture"]) for x in info["vramMatches"] if x["match"]=="exact"})
            rows.append(info)
            if info["ramMatches"] or info["vramMatches"]:
                candidates.append({k:info[k] for k in ("resource","lba","size","ramCaptureCount","exactVramCaptureCount")})
    candidates.sort(key=lambda x:(-x["exactVramCaptureCount"],-x["ramCaptureCount"],x["resource"]))
    return {"schemaVersion":1,"kind":"ISS26_kit_resource_probe",
        "originalTrackSha256":digest,"volume":volume,
        "archives":[p.name for p in paths],"pairedCaptures":len(images),
        "resourcesRead":len(rows),"skipped":skipped,"candidates":candidates,
        "resources":rows,"kitOwnershipVerified":False,
        "limitations":["RAM residency and exact VRAM match are evidence of a resource, not necessarily a uniform.",
        "Modified RC3 resource bytes may differ from clean original.",
        "Unknown loaders, kind-9 codecs, partial runtime transformations and nonresident resources may be missed.",
        "Home/away/GK mapping requires controlled A/B evidence. No game data or assets exported."]}

def self_test():
    # Synthetic fixture only, not real disc evidence.
    import random
    rng=random.Random(95)
    data=bytearray(rng.randrange(256) for _ in range(1024))
    base=0x80012340
    data[:32]=bytes(32)
    struct.pack_into("<I",data,0,base+768)
    struct.pack_into("<6HI",data,768,0,640,320,8,8,0,base+128)
    struct.pack_into("<6HI",data,784,255,0,0,0,0,0,0)
    ram=bytearray(RAM_SIZE);at=base-0x80000000
    ram[at:at+len(data)]=data
    hits=match_ram(bytes(data),anchors(bytes(data)),bytes(ram))
    assert any(h["ramOffset"]==at for h in hits)
    records=gpu_records(bytes(data),base);assert len(records)==1
    payload=gpu_payload(bytes(data),records[0],records);assert payload==data[128:256]
    vram=bytearray(VRAM_SIZE)
    for y in range(8):
        pos=2*((320+y)*1024+640);vram[pos:pos+16]=payload[y*16:(y+1)*16]
    assert vram_match(records[0],payload,bytes(vram))["match"]=="exact"
    vram[2*(320*1024+640)]^=1
    assert vram_match(records[0],payload,bytes(vram)) is None
    assert not match_ram(bytes(data),anchors(bytes(data)),bytes(RAM_SIZE))
    print("PASS: synthetic resource-to-RAM/VRAM correlation and negative guards")

def main():
    p=argparse.ArgumentParser(description="ISS26 Kit Resource Probe: local read-only analysis")
    p.add_argument("--root",type=Path,default=Path(r"D:\ISS 26"))
    p.add_argument("--track",type=Path)
    p.add_argument("--archive",type=Path,action="append",default=[])
    p.add_argument("--out",type=Path,default=Path("KitResearch.json"))
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:self_test();return
    track=a.track
    if track is None:
        cue=a.root/ORIGINAL_CUE
        if not cue.is_file():
            matches=list(a.root.rglob(ORIGINAL_CUE))
            if len(matches)!=1:raise ISOError("Pass --track explicitly; original CUE not unique")
            cue=matches[0]
        track=original_track_from_cue(cue)
    paths=a.archive
    if not paths:
        archive_root=a.root/"ISS26_Data"/"explorer"/"archives"
        paths=sorted(archive_root.glob("*.zip"),key=lambda x:x.stat().st_mtime,reverse=True)[:MAX_ARCHIVES]
    if not paths:print("No Academy archives found; inventory only. Use --archive with an existing ZIP.")
    if len(paths)>MAX_ARCHIVES:raise ValueError("At most four archives per run")
    self_test()
    result=audit_kits(track,paths)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2);f.write("\n")
    print("Resources:",result["resourcesRead"],"paired captures:",result["pairedCaptures"])
    print("Metadata-only report:",a.out)

if __name__=="__main__":
    try:main()
    except (OSError,ValueError,zipfile.BadZipFile) as e:
        print("STOP:",e,file=sys.stderr);sys.exit(1)
