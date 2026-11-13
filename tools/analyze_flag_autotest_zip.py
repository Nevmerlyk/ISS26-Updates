#!/usr/bin/env python3
"""ISS26 flag AutoTest forensic reader (read-only; no game images required).

Reads ZIP reports emitted by ISS26 Launcher/Explorer v0.6.5+, extracts
chronological GPU VRAM tile fingerprints for all 28 original national flag
styles and 54 possible CLUT cells, and records GPU trace availability.
This locates atlas overwrites (e.g. Bosnia oval reappearing on stadium load)
without pretending a color match alone identifies a PS1 sprite.

Usage: python tools/analyze_flag_autotest_zip.py report.zip --output report_analysis
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

VRAM_SIZE = 1024 * 512 * 2  # legacy ePSXe capture
MODERN_VRAM_SIZE = 1024 * 1024 * 2  # PCSX-Redux / Academy capture
MAX_ENTRIES = 2500
MAX_UNCOMPRESSED = 320 * 1024 * 1024
MAX_SINGLE = 12 * 1024 * 1024
SLOT_COUNT = 54
STYLE_COUNT = 28
TILE_W = 64
TILE_H = 28

def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def vram_tile(vram: bytes, word_x: int, y: int) -> bytes:
    """Extract one 64x28 4bpp tile at an actual VRAM word coordinate."""
    if len(vram) not in (VRAM_SIZE, MODERN_VRAM_SIZE):
        raise ValueError("VRAM must be 1024x512 or 1024x1024 16bpp")
    height = len(vram) // (1024 * 2)
    if not (0 <= word_x <= 1024 - 32 and 0 <= y <= height - TILE_H):
        raise ValueError("VRAM tile coordinates out of bounds")
    raw = bytearray()
    for row in range(TILE_H):
        address = ((y + row) * 1024 + word_x) * 2
        raw.extend(vram[address:address + 32])
    return bytes(raw)

def tile_index_bytes(vram: bytes, style: int) -> bytes:
    if not 0 <= style < STYLE_COUNT:
        raise ValueError("Style must be 0..27")
    word_x = 832 + 16 * (style % 4)
    # GPU evidence: 28px row stride, NOT the old erroneous 32px stride.
    y = 256 + 28 * (style // 4)
    return vram_tile(vram, word_x, y)

def gpu_clut(vram: bytes, word_x: int, y: int) -> tuple[int, ...]:
    if len(vram) not in (VRAM_SIZE, MODERN_VRAM_SIZE):
        raise ValueError("Invalid VRAM capture size")
    if not (0 <= word_x <= 1008 and 0 <= y < len(vram) // 2048):
        raise ValueError("CLUT coordinates out of bounds")
    pos = ((y * 1024) + word_x) * 2
    return struct.unpack("<16H", vram[pos:pos+32])

def unresolved_zero_clut_indices(tile: bytes, clut: tuple[int, ...]) -> list[int]:
    """An advisory signal, NOT a source/primitive identification."""
    if len(tile) != 896 or len(clut) != 16:
        raise ValueError("Expected 64x28 tile and 16-color CLUT")
    used = {n for b in tile for n in (b & 15, b >> 4)}
    return sorted(n for n in used if n != 0 and clut[n] == 0)

def palette(vram: bytes, nation_flag_index: int) -> tuple[int, ...]:
    if len(vram) not in (VRAM_SIZE, MODERN_VRAM_SIZE) or not 0 <= nation_flag_index < SLOT_COUNT:
        raise ValueError("Invalid national flag palette input")
    # DAT2D national 16-word CLUT cells begin at (0,505).
    pos = ((505 * 1024) + (16 * nation_flag_index)) * 2
    return struct.unpack("<16H", vram[pos:pos + 32])

def render(tile: bytes, clut: tuple[int, ...]) -> bytes:
    if len(tile) != 896 or len(clut) != 16:
        raise ValueError("Invalid 64x28 4bpp tile/CLUT")
    output = bytearray()
    for byte in tile:
        for index in (byte & 15, byte >> 4):
            color = clut[index]
            if index == 0:
                output.extend((48, 48, 48))
            else:
                output.extend(((color & 31) * 255 // 31,
                               ((color >> 5) & 31) * 255 // 31,
                               ((color >> 10) & 31) * 255 // 31))
    return bytes(output)

def scan(report_zip: Path) -> dict:
    if not report_zip.is_file():
        raise FileNotFoundError(report_zip)
    snapshots: list[dict] = []
    traces: list[dict] = []
    notes: list[str] = []
    task: dict = {}
    progress = ""
    with zipfile.ZipFile(report_zip) as archive:
        files = archive.infolist()
        if len(files) > MAX_ENTRIES or sum(f.file_size for f in files) > MAX_UNCOMPRESSED:
            raise ValueError("Report ZIP exceeds safe forensic size limit")
        for info in files:
            if info.file_size > MAX_SINGLE or ".." in Path(info.filename).parts:
                raise ValueError("Unsafe report ZIP entry: " + info.filename)
            if info.is_dir(): continue
            name = info.filename.replace("\\", "/")
            if "/" in name or "\x00" in name:
                raise ValueError("Nested/unsafe ZIP entry: " + name)
            if name == "autotest-task.json":
                task = json.loads(archive.read(info))
            if name == "autotest-progress.csv":
                progress = archive.read(info).decode("utf-8", "replace")
            if name.endswith(".gpd"):
                traces.append({"name": name, "bytes": info.file_size})
            if not name.endswith(".vram"):
                continue
            raw = archive.read(info)
            if len(raw) not in (VRAM_SIZE, MODERN_VRAM_SIZE):
                notes.append(f"Skipped {name}: unsupported VRAM length {len(raw)}")
                continue
            matches = re.findall(r"(\d+)", name)
            frame = int(matches[-1]) if matches else -1
            tiles = [_digest(tile_index_bytes(raw, style))
                     for style in range(STYLE_COUNT)]
            cluts = [_digest(struct.pack("<16H", *palette(raw, i)))
                     for i in range(SLOT_COUNT)]
            # Verified Test12 stadium GPU packet: flags are copied to (560,0/28)
            # from (848,256) and (864,312), but the *last writer* remains unknown.
            cape_dst = vram_tile(raw, 560, 0)
            bosnia_dst = vram_tile(raw, 560, 28)
            cape_src = vram_tile(raw, 848, 256)
            bosnia_src = vram_tile(raw, 864, 312)
            cape_clut = gpu_clut(raw, 0, 505)
            bosnia_clut = gpu_clut(raw, 224, 506)
            snapshots.append({
                "name": name, "frame": frame, "sha256": _digest(raw),
                "vram_layout": "2MB" if len(raw) == MODERN_VRAM_SIZE else "1MB",
                "prematch_flags": {
                    "cape_dest_sha256": _digest(cape_dst),
                    "cape_atlas_sha256": _digest(cape_src),
                    "cape_dest_equals_atlas": cape_dst == cape_src,
                    "cape_nontransparent_zero_clut_indices": unresolved_zero_clut_indices(cape_dst, cape_clut),
                    "bosnia_dest_sha256": _digest(bosnia_dst),
                    "bosnia_atlas_sha256": _digest(bosnia_src),
                    "bosnia_dest_equals_atlas": bosnia_dst == bosnia_src,
                    "bosnia_nontransparent_zero_clut_indices": unresolved_zero_clut_indices(bosnia_dst, bosnia_clut),
                },
                "prematch_cape_index": cape_dst.hex(),
                "prematch_bosnia_index": bosnia_dst.hex(),
                "prematch_cape_clut": list(cape_clut),
                "prematch_bosnia_clut": list(bosnia_clut),
                "styles": tiles, "cluts": cluts,
                "bosnia_style10_index": tile_index_bytes(raw, 10).hex(),
                "bosnia_clut30": list(palette(raw, 30)),
                "cabo_verde_style1_index": tile_index_bytes(raw, 1).hex(),
                "cabo_verde_clut0": list(palette(raw, 0))
            })
    snapshots.sort(key=lambda d: (d["frame"], d["name"]))
    style_changes: list[dict] = []
    clut_changes: list[dict] = []
    for old, new in zip(snapshots, snapshots[1:]):
        for style in range(STYLE_COUNT):
            if old["styles"][style] != new["styles"][style]:
                style_changes.append({"from": old["name"], "to": new["name"],
                                      "style": style,
                                      "before_sha256": old["styles"][style],
                                      "after_sha256": new["styles"][style]})
        for nation in range(SLOT_COUNT):
            if old["cluts"][nation] != new["cluts"][nation]:
                clut_changes.append({"from": old["name"], "to": new["name"],
                                     "reverse_flag_index": nation,
                                     "national_text_slot": 53 - nation})
    if not snapshots:
        notes.append("No valid raw VRAM snapshots: AutoTest may have halted before capture")
    if not traces:
        notes.append("No .gpd GPU traces: verify the installed PCSX-Redux GPU dump support and logs")
    notes.append("Prematch VRAM source equality is a snapshot comparison, not proof of the GPU last writer or disc source.")
    notes.append("The 64x28 style atlas uses 28-row stride; CLUTs (0,505) and (224,506) are from verified Test12 GPU draws.")
    if len(snapshots) < 2:
        notes.append("At least two captures are necessary to detect stadium flag texture reuploads")
    if task.get("id") != "iss26-flags-gpu-provenance":
        notes.append("ZIP does not declare the expected flag GPU provenance task")
    blocked = "BLOCKED" in progress
    if blocked:
        notes.append("AutoTest reported blocked navigation; no screen identity should be inferred")
    return {"schema_version": 1,
            "report": report_zip.name,
            "task_id": task.get("id"),
            "task_revision": task.get("revision"),
            "vram_capture_count": len(snapshots),
            "gpu_trace_count": len(traces),
            "gpu_traces": traces,
            "snapshots": snapshots,
            "style_changes": style_changes,
            "clut_changes": clut_changes,
            "bosnia_style10_overwrite_transitions":
                [x for x in style_changes if x["style"] == 10],
            "notes": notes}

def _write_csv(path: Path, data: list[dict], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)

def analyze(input_file: Path, output: Path) -> dict:
    result = scan(input_file)
    output.mkdir(parents=True, exist_ok=True)
    # Do not copy user RAM/save-state data or the original game into output.
    stripped = dict(result)
    stripped["snapshots"] = [
        {k:v for k,v in sample.items()
         if k not in ("bosnia_style10_index", "bosnia_clut30",
                      "cabo_verde_style1_index", "cabo_verde_clut0",
                      "prematch_cape_index", "prematch_bosnia_index",
                      "prematch_cape_clut", "prematch_bosnia_clut")}
        for sample in result["snapshots"]]
    (output / "summary.json").write_text(
        json.dumps(stripped, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    _write_csv(output / "style_changes.csv", result["style_changes"],
               ["from", "to", "style", "before_sha256", "after_sha256"])
    _write_csv(output / "palette_changes.csv", result["clut_changes"],
               ["from", "to", "reverse_flag_index", "national_text_slot"])
    for snap in result["snapshots"]:
        for style, clut_id, src in (
            (10, 30, "bosnia"),
            (1, 0, "cabo_verde"),
            (-1, -1, "prematch_cape"),
            (-1, -1, "prematch_bosnia")):
            if style >= 0:
                tile = bytes.fromhex(snap[f"{src}_style{style}_index"])
                clut = tuple(snap[f"{src}_clut{clut_id}"])
            else:
                tile = bytes.fromhex(snap[f"{src}_index"])
                clut = tuple(snap[f"{src}_clut"])
            ppm = (f"P6\n64 28\n255\n").encode("ascii") + render(tile, clut)
            (output / (Path(snap["name"]).stem + f"_{src}_reference.ppm")).write_bytes(ppm)
    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, default=Path("flag_vram_analysis"))
    args = parser.parse_args()
    outcome = analyze(args.report, args.output)
    print(json.dumps({
        "task_id": outcome["task_id"],
        "vram_captures": outcome["vram_capture_count"],
        "gpu_traces": outcome["gpu_trace_count"],
        "bosnia_style10_overwrites": outcome["bosnia_style10_overwrite_transitions"],
        "notes": outcome["notes"]
    }, indent=2, ensure_ascii=False))
    print("Saved summary.json, style_changes.csv, palette_changes.csv and PPM previews to", args.output)
