#!/usr/bin/env python3
"""ISS26 Test12: compare manually identified flag phases in Academy VRAM ZIPs.

Read-only. Works with existing launcher capture formats and deliberately does
NOT identify a 3D flag source, GPU draw primitive, team, or screen phase from
pixel motion alone. A separate user-supplied phase manifest supplies observed
screen labels; .gpd trace files are inventoried, not interpreted as known GPU
commands. Never modifies the game, ISO, BIN/CUE, or saves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import struct
import zipfile

VRAM_WIDTH_WORDS = 1024
VRAM_HEIGHT = 512
VRAM_BYTES = VRAM_WIDTH_WORDS * VRAM_HEIGHT * 2
MAX_FILES = 2500
MAX_UNCOMPRESSED = 320 * 1024 * 1024
MAX_CAPTURE_COUNT = 128
MAX_SINGLE_FILE = 16 * 1024 * 1024
GRID_WORDS = 16
GRID_ROWS = 16
PHASES = {
    "selection", "prematch_banner", "carried_banner",
    "crowd_flags", "hud", "control", "unknown",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def safe_archive_files(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    entries = archive.infolist()
    if len(entries) > MAX_FILES or sum(e.file_size for e in entries) > MAX_UNCOMPRESSED:
        raise ValueError("Report exceeds safe ZIP size/entry limits")
    result = []
    for entry in entries:
        path = entry.filename.replace("\\", "/")
        name = PurePosixPath(path)
        if (path.startswith("/") or "\x00" in path or
                any(p in ("..", "") for p in name.parts) or
                re.match(r"^[A-Za-z]:", path)):
            raise ValueError("Unsafe report member: " + path)
        if entry.is_dir():
            continue
        if entry.file_size > MAX_SINGLE_FILE:
            # Reports can contain large RAM/save states. They are not needed.
            # Only VRAM/GPD are interpreted; reject oversized ones explicitly.
            if name.suffix.lower() in (".vram", ".gpd"):
                raise ValueError("Oversized VRAM/GPD member: " + path)
            continue
        result.append(entry)
    return result


def load_labels(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    if manifest.get("schemaVersion") != 1:
        raise ValueError("Expected phase labels schemaVersion=1")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or len(captures) > MAX_CAPTURE_COUNT:
        raise ValueError("Invalid Test12 capture list")
    result: dict[str, dict] = {}
    for row in captures:
        if not isinstance(row, dict):
            raise ValueError("Capture must be a JSON object")
        name = row.get("snapshot")
        phase = row.get("phase")
        if (not isinstance(name, str) or
                not name.endswith(".vram") or
                PurePosixPath(name).name != name or
                name in result):
            raise ValueError("Non-unique or invalid snapshot filename")
        if phase not in PHASES:
            raise ValueError("Unknown manually observed phase: " + str(phase))
        team = row.get("team", "")
        if not isinstance(team, str) or len(team) > 80:
            raise ValueError("Invalid team label")
        result[name] = {"phase": phase, "team": team,
                        "source": "operator-labelled screenshot"}
    return result


def phase_from_operator_capture(name: str) -> dict | None:
    # The existing v0.8.6 Lua calibrator.request interface makes an explicit
    # human-supplied phase tag part of the saved snapshot name. This is an
    # operator label, NOT an inferred visual classification.
    expression = (
        r"^cal_test12_(selection|prematch_banner|carried_banner|crowd_flags|hud)"
        r"_[0-9a-f]{6}_[0-9]{6,12}[.]vram$"
    )
    match = re.fullmatch(expression, name)
    if not match:
        return None
    return {
        "phase": match.group(1),
        "team": "",
        "source": "operator-tagged Test12 capture request",
    }


def capture_frame(name: str) -> int:
    # Emulator's manual capture filenames end in an 8-digit frame counter.
    matches = re.findall(r"(?:_|^)(\d{6,12})(?:_|\.)", name)
    return int(matches[-1]) if matches else -1


def style_tile(raw: bytes, style: int) -> bytes:
    assert 0 <= style < 28
    word_x = 832 + 16 * (style % 4)
    y = 256 + 32 * (style // 4)
    result = bytearray()
    for row in range(28):
        offset = ((y + row) * VRAM_WIDTH_WORDS + word_x) * 2
        result.extend(raw[offset:offset + 32])
    return bytes(result)


def national_clut(raw: bytes, index: int) -> bytes:
    assert 0 <= index < 54
    offset = ((505 * VRAM_WIDTH_WORDS) + 16 * index) * 2
    return raw[offset:offset + 32]


def block_changes(before: bytes, after: bytes, top: int = 20) -> dict:
    # Each grid cell is 16 16-bit VRAM words by 16 rows. No semantics are
    # assigned: changes could be animations, UI or textures rather than flags.
    result = []
    total_blocks = 0
    for y in range(0, VRAM_HEIGHT, GRID_ROWS):
        for x in range(0, VRAM_WIDTH_WORDS, GRID_WORDS):
            changed_words = 0
            for dy in range(GRID_ROWS):
                start = ((y + dy) * VRAM_WIDTH_WORDS + x) * 2
                a = before[start:start + GRID_WORDS * 2]
                b = after[start:start + GRID_WORDS * 2]
                if a != b:
                    changed_words += sum(
                        a[k:k+2] != b[k:k+2]
                        for k in range(0, GRID_WORDS * 2, 2)
                    )
            if changed_words:
                total_blocks += 1
                result.append({
                    "x_word": x, "y": y,
                    "changed_words": changed_words,
                    "total_words": GRID_WORDS * GRID_ROWS,
                    "in_historical_64x28_flag_atlas_area":
                        832 <= x < 896 and 256 <= y < 480,
                })
    result.sort(key=lambda p: (-p["changed_words"], p["y"], p["x_word"]))
    return {
        "changed_grid_cells": total_blocks,
        "grid": "16x16 VRAM words (not 4bpp pixels)",
        "most_changed_cells": result[:top],
    }


def analyze(report: Path, labels: Path | None = None) -> dict:
    manual = load_labels(labels)
    traces = []
    snapshots: dict[str, tuple[bytes, str]] = {}
    with zipfile.ZipFile(report) as archive:
        files = safe_archive_files(archive)
        for entry in files:
            name = PurePosixPath(entry.filename.replace("\\", "/")).name
            if name.endswith(".gpd"):
                traces.append({"name": name, "size_bytes": entry.file_size})
            if not name.endswith(".vram"):
                continue
            if entry.file_size != VRAM_BYTES:
                raise ValueError(f"Invalid VRAM snapshot size {name}: {entry.file_size}")
            if name in snapshots:
                raise ValueError("Ambiguous duplicate snapshot name: " + name)
            if len(snapshots) >= MAX_CAPTURE_COUNT:
                raise ValueError("Too many VRAM snapshots")
            snapshots[name] = (archive.read(entry), entry.filename)
    missing = sorted(set(manual) - set(snapshots))
    if missing:
        raise ValueError("Labelled snapshot not present in ZIP: " + ", ".join(missing))
    names = sorted(snapshots, key=lambda n: (capture_frame(n), n))
    ordered = []
    for name in names:
        raw, full = snapshots[name]
        label = manual.get(name) or phase_from_operator_capture(name) or {
            "phase": "unknown", "team": "", "source": "none"
        }
        ordered.append({
            "filename": name,
            "zip_path": full,
            "frame_if_encoded": capture_frame(name),
            "sha256": digest(raw),
            "operator_phase": label["phase"],
            "team": label["team"],
            "phase_evidence": label["source"],
        })
    diffs = []
    for n1, n2 in zip(names, names[1:]):
        old = snapshots[n1][0]
        new = snapshots[n2][0]
        style = [i for i in range(28) if style_tile(old, i) != style_tile(new, i)]
        clut = [i for i in range(54) if national_clut(old, i) != national_clut(new, i)]
        diffs.append({
            "from_snapshot": n1,
            "from_operator_phase": (
                manual.get(n1) or phase_from_operator_capture(n1) or {}
            ).get("phase", "unknown"),
            "to_snapshot": n2,
            "to_operator_phase": (
                manual.get(n2) or phase_from_operator_capture(n2) or {}
            ).get("phase", "unknown"),
            "changed_historical_64x28_flag_styles": style,
            "changed_national_clut_indices": clut,
            "grid_change_candidates": block_changes(old, new),
        })
    notes = [
        "Phases are supplied manually; automatic screenshot identity is NOT inferred.",
        "Changing a VRAM cell or CLUT does not identify the GPU draw command or source file.",
        "GPD files are inventoried but not decoded for tpage/UV/CLUT provenance.",
        "Same-scene Test10/Test11 screenshots and GPU primitive traces are still required for causal attribution.",
    ]
    if not manual and not any(phase_from_operator_capture(name) for name in names):
        notes.append("No manual labels or operator-tagged captures: phases remain unknown.")
    if not traces:
        notes.append("No .gpd traces in ZIP; GPU command-level attribution unavailable.")
    if len(names) < 2:
        notes.append("At least two valid VRAM captures required for transitions.")
    return {
        "schema_version": 1, "audit": "Test12: carried / fan / HUD VRAM phase correlation",
        "archive_name": report.name,
        "vram_capture_count": len(names),
        "operator_labeled_count": sum(
            1 for name in names if name in manual or phase_from_operator_capture(name)
        ),
        "gpu_trace_count": len(traces),
        "gpu_trace_inventory": traces,
        "captures": ordered,
        "transitions": diffs,
        "notes": notes,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("report", type=Path, help="Explorer / Academy session ZIP")
    ap.add_argument("--labels", type=Path, help="manual screenshot phase manifest JSON")
    ap.add_argument("--output", type=Path, default=Path("flag_test12_diagnostics.json"))
    a = ap.parse_args()
    result = analyze(a.report, a.labels)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Test12 read-only phase scan:", result["vram_capture_count"],
          "VRAM captures,", len(result["transitions"]), "transitions,",
          result["gpu_trace_count"], "GPD traces")
    print("Saved", a.output)


if __name__ == "__main__":
    main()
