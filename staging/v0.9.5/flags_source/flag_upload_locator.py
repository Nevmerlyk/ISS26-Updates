"""Read-only locator for Bosnia/Cabo Verde flag VRAM uploads in ISS26 EU.

Scans ISO9660 resources inside the user's ORIGINAL 2352-byte Mode2 Track01.
Reports the compressed upload records whose VRAM rectangles cover the two
large-flag tiles. Never modifies game files. No guessed resource is repacked.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

from wecodec import DecodeError, decode
from two_flag_art import LARGE_STYLES, large_style_vram

SECTOR_BYTES = 2352
USER_OFFSET = 24
USER_BYTES = 2048
TARGET_WIDTH_WORDS = 16
TARGET_HEIGHT = 28


def user_sector(file, lba: int) -> bytes:
    file.seek(lba * SECTOR_BYTES + USER_OFFSET)
    block = file.read(USER_BYTES)
    if len(block) != USER_BYTES:
        raise ValueError("truncated 2352-byte raw Mode2 Track01")
    return block


def iso_file_index(file) -> dict[str, tuple[int, int]]:
    pvd = user_sector(file, 16)
    if pvd[1:6] != b"CD001":
        raise ValueError("missing ISO9660 primary volume descriptor")
    root = pvd[156:156 + pvd[156]]
    result = {}
    seen = set()

    def read_extent(lba: int, size: int) -> bytes:
        return b"".join(user_sector(file, lba + i)
                        for i in range((size + USER_BYTES - 1) // USER_BYTES))[:size]

    def traverse(prefix: str, record: bytes) -> None:
        extent, length = struct.unpack_from("<II", record, 2)[0], struct.unpack_from("<I", record, 10)[0]
        if not (record[25] & 2):
            result[prefix] = (extent, length)
            return
        if extent in seen:
            return
        seen.add(extent)
        directory = read_extent(extent, length)
        pos = 0
        while pos < len(directory):
            rec_size = directory[pos]
            if rec_size == 0:
                pos = ((pos // USER_BYTES) + 1) * USER_BYTES
                continue
            rec = directory[pos:pos + rec_size]
            if len(rec) != rec_size or rec_size < 34:
                raise ValueError("invalid ISO directory record")
            ident_len = rec[32]
            name = rec[33:33 + ident_len].decode("ascii", errors="replace")
            pos += rec_size
            if name in ("\x00", "\x01"):
                continue
            name = name.split(";")[0]
            traverse(prefix + "/" + name if prefix else name, rec)

    traverse("", root)
    return result


def intersects_target(x: int, y: int, w: int, h: int, tile_x: int, tile_y: int) -> bool:
    return x < tile_x + TARGET_WIDTH_WORDS and tile_x < x + w and y < tile_y + TARGET_HEIGHT and tile_y < y + h


def inspect_resource(path: str, data: bytes) -> list[dict]:
    """Look for bounded 16-byte PS1 GPU upload commands and verify WE payloads.

    Base addresses are inferred only at 64KB-aligned MIPS load bases;
    failed/ambiguous candidates are reported but never written.
    """
    results = []
    flag_tiles = {name: large_style_vram(style)
                  for name, style in LARGE_STYLES.items()}
    for pos in range(0, len(data) - 16, 4):
        op, x, y, width, height, flags, ptr = struct.unpack_from("<6HI", data, pos)
        if op != 10 or not (1 <= width <= 1024 and 1 <= height <= 512):
            continue
        matches = [name for name, (tx, ty) in flag_tiles.items()
                   if intersects_target(x, y, width, height, tx, ty)]
        if not matches:
            continue
        if x + width > 1024 or y + height > 512:
            continue
        expected_size = width * 2 * height
        if expected_size > 1_048_576:
            continue
        decoded_sources = []
        offset_low16 = ptr & 65535
        for offset in range(offset_low16, len(data), 65536):
            base = ptr - offset
            if not (0x80000000 <= base <= 0x80200000):
                continue
            if offset >= pos:
                continue
            try:
                _decoded, used, _commands = decode(data[offset:pos], expected_size)
            except (DecodeError, ValueError):
                continue
            if used and offset + used <= pos:
                decoded_sources.append({
                    "load_base": hex(base), "compressed_offset": offset,
                    "compressed_length": used, "decoded_length": expected_size
                })
        results.append({
            "resource": path,
            "command_offset": pos,
            "x_words": x, "y": y, "width_words": width, "height": height,
            "flags": flags, "data_pointer": hex(ptr),
            "targets": matches,
            "valid_compressed_candidates": decoded_sources
        })
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("track01", type=Path, help="user-owned original European Track 01 .bin")
    ap.add_argument("--output", type=Path, default=Path("ISS26_two_flag_uploads.json"))
    args = ap.parse_args()
    matches = []
    with args.track01.open("rb") as file:
        index = iso_file_index(file)
        for name, (lba, length) in sorted(index.items()):
            base_name = name.split("/")[-1].upper()
            if not (
                base_name.startswith("DATSEL")
                or base_name in ("EDT_2D.BIN", "EDTR_2D.BIN")
                or base_name.startswith("GDC_")
            ):
                continue
            data = b"".join(user_sector(file, lba + sector)
                            for sector in range((length + USER_BYTES - 1) // USER_BYTES))[:length]
            matches.extend(inspect_resource(name, data))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "note": "Read-only candidate locations; not proof of runtime ownership",
        "original": str(args.track01),
        "iso_files_indexed": len(index),
        "candidates": matches
    }, indent=2), encoding="utf-8")
    print(f"Indexed {len(index)} ISO files; found {len(matches)} overlap commands")
    for entry in matches:
        verified = len(entry["valid_compressed_candidates"])
        print(f"{entry['resource']} command+0x{entry['command_offset']:X} "
              f"{entry['targets']} verified_streams={verified}")
    print("Report:", args.output)


if __name__ == "__main__":
    main()
