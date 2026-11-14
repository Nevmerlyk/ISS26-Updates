#!/usr/bin/env python3
"""ISS26 Test27: classify real Academy stage-copy arguments (metadata only).

Consumes flag-provenance.tsv from the dedicated read-only Test Game source
instrumentation. Never invents observations from absent data, cannot change
game files and never uploads original images. This is NOT a game patch.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 100_000
STYLE_LIMIT = 72

class TraceError(ValueError):
    pass

def _integer(text: str, what: str, low: int, high: int) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise TraceError(f"Invalid {what}: {text!r}") from exc
    if not low <= value <= high:
        raise TraceError(f"Out of bounds {what}: {value}")
    return value

def _kv(items: list[str]) -> dict[str, str]:
    out = {}
    for part in items:
        if "=" not in part:
            raise TraceError(f"Bad key/value: {part[:80]}")
        k, v = part.split("=", 1)
        if k in out or not k.isascii() or not k.replace("_", "").isalnum():
            raise TraceError(f"Duplicate or invalid key: {k}")
        out[k] = v
    return out

def _parse_line(row: str) -> tuple[str, dict] | None:
    fields = row.rstrip("\r\n").split("\t")
    if len(fields) < 2:
        return None
    frame = _integer(fields[0], "frame", 0, 1_000_000_000)
    kind = fields[1]
    if kind == "STYLE_MOVE":
        if len(fields) != 12:
            raise TraceError("Bad STYLE_MOVE field count")
        side = fields[2]
        if side not in ("home", "away"):
            raise TraceError("Unknown flag side")
        style = _integer(fields[3], "style", 0, STYLE_LIMIT - 1)
        sx, sy, dx, dy, width, height = (
            _integer(v, n, 0, limit)
            for v, n, limit in zip(
                fields[4:10],
                ("source_x", "source_y", "dest_x", "dest_y", "width", "height"),
                (1023, 511, 1023, 511, 64, 128),
            )
        )
        if dx != 560 or dy != (0 if side == "home" else 28):
            raise TraceError("STYLE_MOVE destination inconsistent with side")
        return kind, {"frame": frame, "side": side, "style": style,
                      "source_xy": [sx, sy], "destination_xy": [dx, dy],
                      "width_words": width, "height_rows": height,
                      "expected_geometry": width == 16 and height == 28}
    if kind == "STAGE_COPY_DIMENSION_ANOMALY":
        if len(fields) != 7 or fields[2] not in ("home", "away"):
            raise TraceError("Malformed move anomaly")
        kv = _kv(fields[3:])
        if kv.get("expected") != "16x28":
            raise TraceError("Unexpected reference geometry")
        return kind, {"frame": frame, "side": fields[2],
                      "style": _integer(kv["style"], "style", 0, STYLE_LIMIT - 1),
                      "width_words": _integer(kv["w"], "width", 1, 64),
                      "height_rows": _integer(kv["h"], "height", 1, 128)}
    if kind == "STAGE_TRANSFER_RECT":
        if len(fields) != 10 or fields[2] not in ("StoreImage", "LoadImage"):
            raise TraceError("Malformed stage transfer")
        kv = _kv(fields[3:])
        return kind, {"frame": frame, "operation": fields[2],
                      "xy_words": [_integer(kv["x"], "x", 0, 1023),
                                   _integer(kv["y"], "y", 0, 511)],
                      "width_words": _integer(kv["w"], "width", 1, 1024),
                      "height_rows": _integer(kv["h"], "height", 1, 512),
                      "ram_ptr": kv["RAM"],
                      "pc": kv["PC"], "ra": kv["RA"]}
    if kind == "STAGE_RAM_PROFILE":
        if len(fields) != 9 or fields[2] not in (
            "before-StoreImage", "after-StoreImage",
            "before-LoadImage", "after-LoadImage"
        ):
            raise TraceError("Malformed stage RAM profile")
        kv = _kv(fields[3:])
        required = {"home_top", "home_bottom", "away_top", "away_bottom", "PC", "RA"}
        if set(kv) != required:
            raise TraceError("Stage RAM profile missing or unknown fields")
        counts = {
            key: _integer(kv[key], key, 0, 256 if key.endswith("_top") else 192)
            for key in ("home_top", "home_bottom", "away_top", "away_bottom")
        }
        for label in ("PC", "RA"):
            if len(kv[label]) != 8 or any(x not in "0123456789abcdefABCDEF" for x in kv[label]):
                raise TraceError("Bad hexadecimal CPU context")
        return kind, {"frame": frame, "event": fields[2], **counts,
                      "pc": kv["PC"], "ra": kv["RA"]}
    if kind == "STAGE_RAM_PROFILE_FINAL":
        if len(fields) != 4:
            raise TraceError("Malformed RAM profile summary")
        kv = _kv(fields[2:])
        if set(kv) != {"profiles", "errors"}:
            raise TraceError("RAM summary missing or extra fields")
        return kind, {"frame": frame,
                      "profiles": _integer(kv["profiles"], "profile count", 0, 32),
                      "errors": _integer(kv["errors"], "error count", 0, 1_000_000)}
    if kind == "STAGE_RECT_FINAL":
        if len(fields) != 4:
            raise TraceError("Bad final stage telemetry")
        kv = _kv(fields[2:])
        return kind, {"frame": frame,
                      "move_dim_anomalies": _integer(kv["move_dim_anomalies"],
                                                    "anomalies", 0, 1_000_000),
                      "transfer_rects": _integer(kv["transfer_rects"],
                                                 "transfers", 0, 1_000_000)}
    return None

def analyze_text(text: str) -> dict:
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise TraceError("Provenance log exceeds bounded size")
    lines = text.splitlines()
    if len(lines) > MAX_ROWS:
        raise TraceError("Too many provenance rows")
    moves, anomalies, transfers, finals = [], [], [], []
    profiles, profile_finals = [], []
    for row in lines:
        parsed = _parse_line(row)
        if parsed is None:
            continue
        kind, data = parsed
        if kind == "STYLE_MOVE":
            moves.append(data)
        elif kind == "STAGE_COPY_DIMENSION_ANOMALY":
            anomalies.append(data)
        elif kind == "STAGE_TRANSFER_RECT":
            transfers.append(data)
        elif kind == "STAGE_RECT_FINAL":
            finals.append(data)
        elif kind == "STAGE_RAM_PROFILE":
            profiles.append(data)
        elif kind == "STAGE_RAM_PROFILE_FINAL":
            profile_finals.append(data)
    away55 = [m for m in moves if m["side"] == "away" and m["style"] == 55]
    short55 = [m for m in away55 if m["width_words"] == 16
               and m["height_rows"] < 28]
    full55 = [m for m in away55 if m["expected_geometry"]]
    off55 = [m for m in away55 if not m["expected_geometry"]]
    store_load_short = [t for t in transfers if t["width_words"] == 16
                        and t["height_rows"] < 28]
    # Each after-return sample is paired only with the preceding before-call
    # profile of the *same* GPU operation, in the order they were logged.
    # This is temporal evidence, never proof DMA completion or CPU writer.
    pending: dict[str, dict | None] = {"StoreImage": None, "LoadImage": None}
    pairs = []
    for item in profiles:
        event = item["event"]
        phase, op = event.split("-", 1)
        if phase == "before":
            pending[op] = item
        else:
            old = pending[op]
            pending[op] = None
            if old is None:
                continue
            differences = {
                key: item[key] - old[key]
                for key in ("home_top", "home_bottom", "away_top", "away_bottom")
            }
            pairs.append({
                "operation": op,
                "before_frame": old["frame"],
                "after_frame": item["frame"],
                "nonzero_word_deltas": differences,
                "away_bottom_dropped_to_zero": (
                    old["away_bottom"] > 0 and item["away_bottom"] == 0
                ),
                "away_16_row_mask_present_after": (
                    item["away_top"] > 0 and item["away_bottom"] == 0
                ),
            })
    profiles_with_blank_bottom = [
        item for item in profiles
        if item["away_top"] > 0 and item["away_bottom"] == 0
    ]
    if short55:
        verdict = "Observed sub-28-row MoveImage for away style55 (not yet causal proof)"
    elif full55:
        verdict = ("Observed 16x28 MoveImage for away style55; "
                   "investigate later clear or StoreImage/LoadImage")
    else:
        verdict = ("No observed style55 away MoveImage: cannot locate "
                   "staging fault from this log")
    if any(f["move_dim_anomalies"] > 0 for f in finals) and not anomalies:
        raise TraceError("Final anomaly count conflicts with missing anomaly rows")
    return {
        "schemaVersion": 1,
        "kind": "Test27 read-only PS1 flag stage MIPS transfer arguments",
        "source_label": "Academy flag-provenance.tsv; operator scene not inferred",
        "move_count": len(moves),
        "anomaly_count": len(anomalies),
        "transfer_rect_count": len(transfers),
        "away_style55_move_count": len(away55),
        "away_style55_short_count": len(short55),
        "away_style55_full_count": len(full55),
        "away_style55_other_shape_count": len(off55),
        "store_load_short_rect_count": len(store_load_short),
        "stage_ram_profile_count": len(profiles),
        "stage_ram_16_row_mask_observations": len(profiles_with_blank_bottom),
        "stage_ram_paired_call_count": len(pairs),
        "stage_ram_bottom_loss_pairs": sum(
            bool(p["away_bottom_dropped_to_zero"]) for p in pairs
        ),
        "stage_ram_profile_pairs": pairs[:16],
        "stage_ram_profiles": profiles[:32],
        "stage_ram_profile_final": profile_finals[-1] if profile_finals else None,
        "verdict": verdict,
        "writer_causality_proven": False,
        "ram_profile_interpretation": (
            "RAM top/bottom counts are observations at hooks, not a guarantee "
            "that an asynchronous GPU transfer completed before the hook. "
            "Only VRAM+GP0 timeline can prove the final texture writer."
        ),
        "observed_moves_style55_away": away55[:24],
        "observed_dimension_anomalies": anomalies[:16],
        "observed_store_load_rectangles": transfers[:32],
        "final_counters": finals[-1] if finals else None,
        "game_patch_built": False,
        "original_disc_modified": False,
    }

def analyze_file(path: Path) -> dict:
    if path.stat().st_size > MAX_BYTES:
        raise TraceError("Oversized file")
    return analyze_text(path.read_text(encoding="utf-8-sig", errors="strict"))

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = analyze_file(args.log)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["verdict"])
    print("No original disc/game/patch modification.")

if __name__ == "__main__":
    main()
