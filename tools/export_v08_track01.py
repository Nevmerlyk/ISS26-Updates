#!/usr/bin/env python3
"""Export a verified ISS26X01 patch from the *locally installed* v0.8 Track 01.

Never stores or uploads either full game BIN. Only writes changed-sector XOR
deltas. No CD Audio Tracks 02-12 are processed or shipped.
Python 3.9+ standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys

SECTOR = 2352
BASE_SIZE = 496_156_752
BASE_SHA256 = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
MAGIC = b"ISS26X01"
MAX_CHANGED = 8192
MAX_PATCH_SIZE = 32 * 1024 * 1024
VERSION = "0.8.0-preview"
RELEASE_TAG = "v0.8.0-preview"
REPO = "Nevmerlyk/ISS26-Updates"
DEFAULT_NAME = "ISS26_0.8.0_preview.iss26p"


def get_paths(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    original, patched, target = args.original, args.patched, args.output
    if not original or not patched or not target:
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            try:
                if not original:
                    original = filedialog.askopenfilename(
                        title="ЧИСТЫЙ оригинал: Track 01.bin",
                        filetypes=[("PS1 BIN", "*.bin"), ("All files", "*.*")],
                    )
                if not patched:
                    patched = filedialog.askopenfilename(
                        title="Установленная ISS26 v0.8: изменённый Track 01.bin",
                        filetypes=[("PS1 BIN", "*.bin"), ("All files", "*.*")],
                    )
                if not target:
                    target = filedialog.asksaveasfilename(
                        title="Сохранить обновление для ISS26 Launcher",
                        initialfile=DEFAULT_NAME,
                        defaultextension=".iss26p",
                        filetypes=[("ISS26 patch", "*.iss26p")],
                    )
            finally:
                root.destroy()
        except Exception as exc:
            raise ValueError(
                "Укажи --original, --patched и --output (или запусти на Windows с tkinter)."
            ) from exc
    if not original or not patched or not target:
        raise ValueError("Выбор файлов отменён.")
    return Path(original).resolve(), Path(patched).resolve(), Path(target).resolve()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_records(original: Path, patched: Path, patch_path: Path, expected_count: int) -> None:
    """Independently test every patch record against both full input images."""
    with original.open("rb") as src, patched.open("rb") as dst, patch_path.open("rb") as delta:
        if delta.read(8) != MAGIC:
            raise ValueError("Invalid ISS26X01 magic.")
        count_bytes = delta.read(4)
        if len(count_bytes) != 4:
            raise ValueError("Truncated patch header.")
        count = struct.unpack("<I", count_bytes)[0]
        if count != expected_count:
            raise ValueError("Count mismatch.")
        last_sector = -1
        for _ in range(count):
            offset_bytes = delta.read(4)
            expected_hash = delta.read(32)
            xor = delta.read(SECTOR)
            if len(offset_bytes) != 4 or len(expected_hash) != 32 or len(xor) != SECTOR:
                raise ValueError("Truncated patch record.")
            sector_index = struct.unpack("<I", offset_bytes)[0]
            if not last_sector < sector_index < BASE_SIZE // SECTOR:
                raise ValueError("Invalid or duplicated sector index.")
            last_sector = sector_index
            src.seek(sector_index * SECTOR)
            dst.seek(sector_index * SECTOR)
            clean = src.read(SECTOR)
            target = dst.read(SECTOR)
            if hashlib.sha256(clean).digest() != expected_hash:
                raise ValueError(f"Bad source-sector digest: {sector_index}")
            if bytes(a ^ b for a, b in zip(clean, xor)) != target:
                raise ValueError(f"Patch differs from installed v0.8: {sector_index}")
        if delta.read(1):
            raise ValueError("Unexpected trailing bytes.")
    expected_length = 12 + expected_count * (4 + 32 + SECTOR)
    if patch_path.stat().st_size != expected_length:
        raise ValueError("Unexpected patch size.")


def export(original: Path, patched: Path, output: Path) -> dict:
    if not original.is_file() or not patched.is_file():
        raise FileNotFoundError("The original and installed v0.8 Track 01 BIN files are required.")
    if original == patched or output in (original, patched):
        raise ValueError("Input and output must be three different files.")
    if original.stat().st_size != BASE_SIZE or patched.stat().st_size != BASE_SIZE:
        raise ValueError(f"Both BIN files must be exactly {BASE_SIZE} bytes.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".partial")
    if temp.exists():
        raise FileExistsError(f"Remove the stale partial file first: {temp}")
    count = 0
    source_digest = hashlib.sha256()
    target_digest = hashlib.sha256()
    try:
        with original.open("rb") as clean, patched.open("rb") as mod, temp.open("w+b") as dest:
            dest.write(MAGIC)
            dest.write(struct.pack("<I", 0))
            for idx in range(BASE_SIZE // SECTOR):
                a, b = clean.read(SECTOR), mod.read(SECTOR)
                if len(a) != SECTOR or len(b) != SECTOR:
                    raise ValueError("Unexpected end of BIN.")
                source_digest.update(a)
                target_digest.update(b)
                if a == b:
                    continue
                count += 1
                if count > MAX_CHANGED:
                    raise ValueError("Too many changed sectors for current ISS26 launcher.")
                dest.write(struct.pack("<I", idx))
                dest.write(hashlib.sha256(a).digest())
                dest.write(bytes(x ^ y for x, y in zip(a, b)))
            if clean.read(1) or mod.read(1):
                raise ValueError("Unexpected trailing BIN content.")
            src_sha = source_digest.hexdigest().upper()
            if src_sha != BASE_SHA256:
                raise ValueError(
                    "Clean original mismatch. This patch needs the original EU "
                    f"SLES-03321 Track 01 SHA256 {BASE_SHA256}; got {src_sha}."
                )
            if count == 0:
                raise ValueError("No changes between original and patched image.")
            dest.seek(8)
            dest.write(struct.pack("<I", count))
            dest.flush()
            os.fsync(dest.fileno())
        if temp.stat().st_size > MAX_PATCH_SIZE:
            raise ValueError("Patch is over the launcher's 32 MB limit.")
        verify_records(original, patched, temp, count)
        os.replace(temp, output)
    finally:
        if temp.exists():
            temp.unlink()
    patch_sha = sha256_file(output)
    result_sha = target_digest.hexdigest().upper()
    latest = {
        "schemaVersion": 1,
        "latest": {
            "version": VERSION,
            "patchUrl": (
                f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{output.name}"
            ),
            "patchSha256": patch_sha,
            "baseSha256": BASE_SHA256,
            "resultSha256": result_sha,
        },
    }
    manifest = output.with_name("candidate-latest-v0.8.0-preview.json")
    manifest.write_text(json.dumps(latest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Verified {count} modified CD sectors.")
    print(f"Output: {output} ({output.stat().st_size:,} bytes)")
    print(f"SHA256 patch: {patch_sha}")
    print(f"SHA256 result: {result_sha}")
    print(f"Candidate manifest (DO NOT publish before uploading/validating asset): {manifest}")
    print("No original CD sectors, whole BIN, or audio Tracks 02-12 were uploaded.")
    return latest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", help="Clean European Track 01 BIN")
    parser.add_argument("--patched", help="Track 01 BIN produced by installing v0.8 on vanilla")
    parser.add_argument("--output", help=f"Output .iss26p file (default: {DEFAULT_NAME})")
    args = parser.parse_args()
    try:
        return 0 if export(*get_paths(args)) else 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
