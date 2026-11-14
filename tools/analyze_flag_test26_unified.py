#!/usr/bin/env python3
"""ISS26 Test26: unified read-only flag atlas/scene audit for Academy ZIP reports.

This is an *evidence collector*, not a flag patch or a visual classifier.
For each VRAM capture it fingerprints all 72 possible 64x28 4bpp style
cells, the two prematch staging cells, and draw-time CLUT candidates.
Operator-tagged phases distinguish prematch display, carried banners,
waving crowd flags and HUD without inventing GPU primitive ownership.

Requires no original disc, no binary modification and no third-party modules.
Usage:
  python tools/analyze_flag_test26_unified.py report.zip --output test26.json
  python tools/analyze_flag_test26_unified.py report.zip --labels phases.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile

from parse_v095_gpudump import inspect as inspect_gpudump

from analyze_flag_test12_phases import (
    LEGACY_VRAM_BYTES,
    VRAM_BYTES,
    MAX_CAPTURE_COUNT,
    safe_archive_files,
    load_labels,
    phase_from_operator_capture,
    capture_frame,
)

VRAM_ROW_WORDS = 1024
STYLE_COUNT = 72
STYLE_WORDS = 16
STYLE_ROWS = 28
STYLE_BYTES = STYLE_WORDS * STYLE_ROWS * 2  # 896 bytes, 64x28 4bpp
PHASES = ("selection", "prematch_banner", "carried_banner", "crowd_flags", "hud")
TEAM_STAGING = {"home": (560, 0), "away": (560, 28)}
DRAW_CLUT_CANDIDATES = {"home": (0, 505), "away": (224, 506)}
REFERENCE_STYLES = {"cape_verde_test25": 1, "bosnia_test13": 10, "bosnia_test25": 55}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def atlas_xy(style: int) -> tuple[int, int]:
    """Style layout disassembled from original EU SELECT.BIN, including bank 2."""
    if not isinstance(style, int) or not 0 <= style < STYLE_COUNT:
        raise ValueError("Expected a style number 0..71")
    # Two independent 4x9 banks (36 styles each), not one linear grid.
    base = 832 if style < 36 else 768
    return base + 16 * (style % 4), 256 + 28 * ((style % 36) // 4)


def tile(raw: bytes, word_x: int, y: int) -> bytes:
    if len(raw) not in (LEGACY_VRAM_BYTES, VRAM_BYTES):
        raise ValueError("Unsupported PCSX VRAM dimensions")
    height = len(raw) // (VRAM_ROW_WORDS * 2)
    if not 0 <= word_x <= VRAM_ROW_WORDS - STYLE_WORDS or not 0 <= y <= height - STYLE_ROWS:
        raise ValueError("Flag tile is outside captured VRAM")
    out = bytearray()
    for dy in range(STYLE_ROWS):
        offset = (VRAM_ROW_WORDS * (y + dy) + word_x) * 2
        out.extend(raw[offset:offset + STYLE_WORDS * 2])
    return bytes(out)


def clut(raw: bytes, word_x: int, y: int) -> bytes:
    height = len(raw) // (VRAM_ROW_WORDS * 2)
    if len(raw) not in (LEGACY_VRAM_BYTES, VRAM_BYTES) or not 0 <= word_x <= 1008 or not 0 <= y < height:
        raise ValueError("CLUT outside capture")
    at = (y * VRAM_ROW_WORDS + word_x) * 2
    return raw[at:at+32]


def _matches(stage: bytes, styles: list[bytes]) -> list[int]:
    # An all-zero tile matches many empty VRAM cells; not a meaningful signal.
    return [index for index, value in enumerate(styles) if value == stage] if any(stage) else []


def ranked_partial_style_sources(stage: bytes, styles: list[bytes], max_shift: int = 2) -> list[dict]:
    """Rank *candidate* style origins when a final staging tile is not byte-identical.

    Searches 0..71 atlas cells at offsets -2..+2 VRAM words / rows. Ignores
    zero-filled staging words to avoid ranking blank atlas. A partial match
    is NOT a provenance claim (palette and GP0 uploader remain unverified).
    This is a diagnostic of shifted/split/overwritten 4bpp flag staging.
    """
    if len(stage) != STYLE_BYTES or len(styles) != STYLE_COUNT or any(
        len(t) != STYLE_BYTES for t in styles
    ):
        raise ValueError("Expected 72 full 16x28-word style cells")
    if not 0 <= max_shift <= 4:
        raise ValueError("Invalid maximum shift")
    words = struct.unpack("<" + "H" * (STYLE_WORDS * STYLE_ROWS), stage)
    active = sum(value != 0 for value in words)
    if active < 24:
        return []
    tiles = [
        struct.unpack("<" + "H" * (STYLE_WORDS * STYLE_ROWS), buf)
        for buf in styles
    ]
    candidates = []
    for style, source in enumerate(tiles):
        best = (0, 0, 0, 0)
        for dy in range(-max_shift, max_shift + 1):
            y0, y1 = max(0, -dy), min(STYLE_ROWS, STYLE_ROWS - dy)
            for dx in range(-max_shift, max_shift + 1):
                x0, x1 = max(0, -dx), min(STYLE_WORDS, STYLE_WORDS - dx)
                equal = compared = 0
                for y in range(y0, y1):
                    for x in range(x0, x1):
                        item = words[y * STYLE_WORDS + x]
                        if item == 0:
                            continue
                        compared += 1
                        equal += int(item == source[(y + dy) * STYLE_WORDS + x + dx])
                score = (equal, compared, dx, dy)
                if equal > best[0] or (equal == best[0] and compared > best[1]):
                    best = score
        if best[0] >= 12:
            equal, compared, dx, dy = best
            candidates.append({
                "style_id": style,
                "matching_nonzero_stage_words": equal,
                "compared_nonzero_stage_words": compared,
                "total_nonzero_stage_words": active,
                "fraction_of_nonzero_stage_words": round(equal / active, 4),
                "source_offset_words_xy": [dx, dy],
            })
    candidates.sort(key=lambda c: (
        -c["matching_nonzero_stage_words"],
        -c["fraction_of_nonzero_stage_words"],
        c["style_id"],
    ))
    return candidates[:5]


def fingerprint(raw: bytes) -> dict:
    styles = [tile(raw, *atlas_xy(i)) for i in range(STYLE_COUNT)]
    homes = {side: tile(raw, *coords) for side, coords in TEAM_STAGING.items()}
    return {
        "vram_sha256": sha(raw),
        "vram_size_bytes": len(raw),
        "style_sha256": [sha(t) for t in styles],
        "staging": {
            side: {
                "tile_sha256": sha(buf),
                "matching_style_ids": _matches(buf, styles),
                "ranked_partial_style_candidates": ranked_partial_style_sources(buf, styles),
                "draw_clut_candidate_xy": list(DRAW_CLUT_CANDIDATES[side]),
                "draw_clut_candidate_sha256": sha(clut(raw, *DRAW_CLUT_CANDIDATES[side])),
            }
            for side, buf in homes.items()
        },
        "reference_styles": {
            name: {"style": index, "atlas_xy_words": list(atlas_xy(index)),
                   "tile_sha256": sha(styles[index])}
            for name, index in REFERENCE_STYLES.items()
        },
        "national_palette_hashes": [
            sha(clut(raw, 16 * n, 505)) for n in range(54)
        ],
    }


def analyze_archive(report: Path, labels: Path | None = None) -> dict:
    operator_labels = load_labels(labels)
    captures: list[dict] = []
    gpds: list[dict] = []
    screens: list[str] = []
    seen_names: set[str] = set()
    with zipfile.ZipFile(report) as z:
        entries = safe_archive_files(z)
        ordered = sorted(entries, key=lambda e: (
            capture_frame(PurePosixPath(e.filename.replace("\\", "/")).name),
            e.filename,
        ))
        for entry in ordered:
            name = PurePosixPath(entry.filename.replace("\\", "/")).name
            lower = name.lower()
            if lower.endswith(".gpd"):
                row = {"zip_member": entry.filename, "bytes": entry.file_size}
                try:
                    row["decoded_gp0"] = inspect_gpudump(z.read(entry))
                except (ValueError, struct.error) as exc:
                    row["parse_error"] = str(exc)[:240]
                gpds.append(row)
                continue
            if lower.endswith(".png") or lower.endswith(".screen.raw"):
                screens.append(entry.filename)
                continue
            if not lower.endswith(".vram"):
                continue
            if name in seen_names:
                raise ValueError("Ambiguous duplicate VRAM snapshot basename: " + name)
            seen_names.add(name)
            if len(captures) >= MAX_CAPTURE_COUNT:
                raise ValueError("Too many VRAM capture files")
            if entry.file_size not in (LEGACY_VRAM_BYTES, VRAM_BYTES):
                raise ValueError("Invalid VRAM capture size for " + name)
            phase = operator_labels.get(name) or phase_from_operator_capture(name) or {}
            raw = z.read(entry)
            fp = fingerprint(raw)
            captures.append({
                "zip_member": entry.filename,
                "name": name,
                "frame_if_encoded": capture_frame(name),
                "operator_phase": phase.get("phase", "unknown"),
                "phase_evidence": phase.get("source", "no operator label"),
                **fp,
            })

    missing = set(operator_labels) - seen_names
    if missing:
        raise ValueError("Operator-labelled VRAM member not in ZIP: " + ", ".join(sorted(missing)))
    # A filename such as flag_auto_crowd_flags is NOT an operator label.
    # Match GPU traces to verified scenes only when an operator-tagged
    # VRAM snapshot carries the *same encoded emulator frame*.
    tagged_frames = {}
    for sample in captures:
        if sample["operator_phase"] != "unknown" and sample["frame_if_encoded"] >= 0:
            tagged_frames.setdefault(sample["frame_if_encoded"], set()).add(sample["operator_phase"])
    for trace in gpds:
        short_name = PurePosixPath(trace["zip_member"].replace("\\", "/")).name
        frame = capture_frame(short_name)
        matched = tagged_frames.get(frame, set())
        trace["frame_if_encoded"] = frame
        trace["operator_phase"] = next(iter(matched)) if len(matched) == 1 else "unknown"
        trace["phase_link_evidence"] = (
            "exact encoded frame + operator-labelled VRAM snapshot"
            if len(matched) == 1 else "none (or ambiguous)"
        )
    if len({c["vram_size_bytes"] for c in captures}) > 1:
        raise ValueError("Cannot correlate mixed 1MB and 2MB VRAM captures")

    # Hash-only transitions; never export VRAM or user-disc artwork.
    transitions = []
    for first, second in zip(captures, captures[1:]):
        changed = [
            i for i, (a, b) in enumerate(zip(first["style_sha256"], second["style_sha256"]))
            if a != b
        ]
        palettes = [
            i for i, (a, b) in enumerate(zip(first["national_palette_hashes"],
                                             second["national_palette_hashes"])) if a != b
        ]
        transitions.append({
            "from": first["name"],
            "to": second["name"],
            "from_operator_phase": first["operator_phase"],
            "to_operator_phase": second["operator_phase"],
            "changed_atlas_style_ids": changed,
            "changed_national_palette_ids": palettes,
            "changed_staging": {
                side: first["staging"][side]["tile_sha256"] != second["staging"][side]["tile_sha256"]
                for side in TEAM_STAGING
            },
        })

    coverage = {
        phase: {
            "operator_tagged_vram_captures": sum(c["operator_phase"] == phase for c in captures),
            "verified_gpu_draw_ownership": False,
            "same_frame_operator_tagged_gpu_dump_count": sum(
                row["operator_phase"] == phase and
                row.get("decoded_gp0", {}).get("trace_begin_found", False)
                for row in gpds
            ),
            "stage_flag_draw_candidate_count": sum(
                row.get("decoded_gp0", {}).get("stage_touch_draw_count", 0)
                for row in gpds if row["operator_phase"] == phase
            ),
        }
        for phase in PHASES
    }
    return {
        "schemaVersion": 1,
        "kind": "Test26 unified flag surface provenance, read-only",
        "input_report": report.name,
        "analysis_performed_on_actual_report": True,
        "style_count": STYLE_COUNT,
        "national_standard_slots": 54,
        "bonus_national_slots_unmapped": 4,
        "club_slots_to_preserve": 24,
        "capture_count": len(captures),
        "gpu_trace_count": len(gpds),
        "gpu_trace_decoded_count": sum(
            bool(row.get("decoded_gp0", {}).get("trace_begin_found")) for row in gpds
        ),
        "screenshot_file_count": len(screens),
        "screenshots_inventory_only": screens,
        "gpu_dumps_inventory_only": gpds,
        "operator_phase_coverage": coverage,
        "captures": captures,
        "transitions": transitions,
        "limitations": [
            "A phase is accepted only from an operator label, not inferred from a task filename.",
            "GPUDUMP textured primitives and transfers are decoded after TraceBegin when supported.",
            "GPU traces are phase-linked only on exact encoded frame match with operator-labelled VRAM.",
            "Stage-flag draw groups are UV bounding-box candidates, not proof of a crowd or ceremony flag.",
            "Decoded GP0 polygons do not automatically identify a crowd, ceremony, or selection scene.",
            "Style pixels matching staging only proves byte equality at capture time; no last uploader is identified.",
            "A crowd_flags phase label does not prove its VRAM styles are crowd artwork.",
            "Crowd animation frame-to-frame attribution needs additional GP0 draw evidence.",
            "Test25 style55 is investigated in bank 2; this is not evidence of correct Bosnia art.",
            "Do not publish or promote a game patch based on this report alone.",
        ],
    }



def compact_summary(result: dict) -> dict:
    """Short evidence matrix for sharing, without exposing VRAM pixel arrays."""
    zero_tile_sha = sha(bytes(STYLE_BYTES))
    compact_captures = []
    for item in result["captures"]:
        present = sum(t != zero_tile_sha for t in item["style_sha256"])
        compact_captures.append({
            "frame": item["frame_if_encoded"],
            "snapshot": item["name"],
            "operator_phase": item["operator_phase"],
            "populated_style_cells": present,
            "home_exact_style_ids": item["staging"]["home"]["matching_style_ids"],
            "away_exact_style_ids": item["staging"]["away"]["matching_style_ids"],
            "home_partial_candidates": item["staging"]["home"].get(
                "ranked_partial_style_candidates", []
            )[:3],
            "away_partial_candidates": item["staging"]["away"].get(
                "ranked_partial_style_candidates", []
            )[:3],
        })
    compact_traces = []
    for item in result["gpu_dumps_inventory_only"]:
        gpu = item.get("decoded_gp0", {})
        candidate_clut_counts: dict[str, int] = {}
        for draw in gpu.get("draw_groups_touching_560_0_16_56", []):
            clut_key = ",".join(str(x) for x in draw["clut_xy_words"])
            candidate_clut_counts[clut_key] = (
                candidate_clut_counts.get(clut_key, 0) + draw["count"]
            )
        compact_traces.append({
            "frame": item.get("frame_if_encoded", -1),
            "capture": item["zip_member"],
            "operator_phase": item.get("operator_phase", "unknown"),
            "gpu_trace_decoded": bool(gpu.get("trace_begin_found", False)),
            "textured_draw_count": gpu.get("textured_primitive_count", 0),
            "staging_candidate_draw_count": gpu.get("stage_touch_draw_count", 0),
            "staging_candidate_clut_counts": candidate_clut_counts,
            "cpu_to_vram_uploads": gpu.get("cpu_to_vram_uploads", 0),
            "vram_to_vram_moves": gpu.get("vram_to_vram_moves", 0),
        })
    return {
        "schemaVersion": 1,
        "kind": "Test26 compact findings; source hypotheses, not verified flags",
        "input_report": result["input_report"],
        "style_count": result["style_count"],
        "capture_count": result["capture_count"],
        "gpu_trace_count": result["gpu_trace_count"],
        "gpu_trace_decoded_count": result["gpu_trace_decoded_count"],
        "phases_operator_verified": {
            k: v["operator_tagged_vram_captures"]
            for k, v in result["operator_phase_coverage"].items()
        },
        "captures": compact_captures,
        "gpu_traces": compact_traces,
        "atlas_transitions": [
            {
                "from": t["from"], "to": t["to"],
                "changed_style_count": len(t["changed_atlas_style_ids"]),
                "changed_style55": 55 in t["changed_atlas_style_ids"],
                "changed_palette_count": len(t["changed_national_palette_ids"]),
                "changed_staging": t["changed_staging"],
            }
            for t in result["transitions"]
        ],
        "warning": (
            "Staging hash matches and nearby source candidates are not proof of "
            "which file uploaded the flag. AutoCapture filenames are not operator-"
            "verified images or spectator flag ownership."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("report", type=Path, help="Test25/26 Academy report ZIP")
    p.add_argument("--labels", type=Path, help="Optional operator-provided phase manifest")
    p.add_argument("--output", type=Path, default=Path("ISS26_Test26_flag_surfaces.json"))
    p.add_argument("--summary-output", type=Path, help="Optional compact source-evidence JSON")
    args = p.parse_args()
    result = analyze_archive(args.report, args.labels)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(compact_summary(result), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print("Processed", result["capture_count"], "VRAM captures; all", STYLE_COUNT,
          "atlas styles; GPD files", result["gpu_trace_count"],
          "decoded live traces", result["gpu_trace_decoded_count"])
    print("Operator-tagged phase counts:", {
        name: count["operator_tagged_vram_captures"]
        for name, count in result["operator_phase_coverage"].items()
    })
    print("Saved hash/coordinate-only evidence:", args.output)


if __name__ == "__main__":
    main()
