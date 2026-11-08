#!/usr/bin/env python3
"""Inspect *XOR deltas only* for PS1 Mode2 sector-header changes.

No commercial game image needed. The original sector header's complete
values are unknown: XOR alone proves only which bits are flipped.
On PlayStation CD Mode2, the duplicated four-byte subheader lives at offsets
16..19 and 20..23. If the original duplicates agree, after-patch duplicates
must agree too; their XOR deltas should therefore be equal.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from compare_preview_patches import download, parse_patch


RESOURCE_WINDOWS = (
    ("team_selection_DATSEL", 6000, 6110),
    ("team_selection_DATSEL2", 6150, 6250),
    ("team_selection_DATSEL3", 6250, 6325),
    ("edit_mode_EDT_2D", 3900, 3990),
    ("edit_mode_EDTR_2D", 4000, 4090),
    ("stadium_GDC_resources", 10800, 16750),
)


def report(records: dict[int, tuple[bytes, bytes]]) -> dict:
    altered_header = []
    subheader_delta_mismatch = []
    form2_submode_bit_flips = []
    mode_byte_changes = []
    sync_changes = []
    by_resource = collections.defaultdict(
        lambda: {"records": 0, "header_edits": 0,
                 "duplicated_subheader_mismatch": 0, "form2_bit_flips": 0})
    for lba, (_source_hash, delta) in records.items():
        region = next((name for name, lo, hi in RESOURCE_WINDOWS
                       if lo <= lba < hi), "other")
        grouped = by_resource[region]
        grouped["records"] += 1
        header = any(delta[:24])
        mismatch = delta[16:20] != delta[20:24]
        form2flip = bool((delta[18] | delta[22]) & 0x20)
        if header:
            altered_header.append(lba)
            grouped["header_edits"] += 1
        if mismatch:
            subheader_delta_mismatch.append(lba)
            grouped["duplicated_subheader_mismatch"] += 1
        if form2flip:
            form2_submode_bit_flips.append(lba)
            grouped["form2_bit_flips"] += 1
        if delta[15]:
            mode_byte_changes.append(lba)
        if any(delta[:12]):
            sync_changes.append(lba)
    return {
        "modified_sectors": len(records),
        "changed_header_sector_count": len(altered_header),
        "subheader_delta_mismatch_count": len(subheader_delta_mismatch),
        "subheader_delta_mismatch_lbas": subheader_delta_mismatch[:100],
        "form2_flag_flipped_sector_count": len(form2_submode_bit_flips),
        "form2_flag_flipped_lbas": form2_submode_bit_flips[:100],
        "mode_byte_changed_sector_count": len(mode_byte_changes),
        "sync_changed_sector_count": len(sync_changes),
        "by_resource_window": dict(sorted(by_resource.items())),
        "important": (
            "The patch contains XOR deltas, not raw original or resulting headers. "
            "A mismatch between duplicated subheader XOR deltas implies one of "
            "the original/resulting subheader pairs differs, but a clean-bin "
            "reader must verify which. Form2 bit flips do NOT by themselves "
            "prove invalid CD coding or graphics corruption."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path,
                   default=Path("staging/v0.9.3/candidate.json"))
    p.add_argument("--out", type=Path, default=Path("dist/v093_sector_headers.json"))
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    latest = manifest["latest"]
    records = parse_patch(download(latest["patchUrl"]), latest["patchSha256"])
    result = report(records)
    result["version"] = latest["version"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"v0.9.3 XOR-sector header audit: {result['modified_sectors']} records; "
          f"{result['form2_flag_flipped_sector_count']} Form2-bit flips; "
          f"{result['subheader_delta_mismatch_count']} duplicated-subheader delta "
          "mismatches")
    for name, stats in result["by_resource_window"].items():
        print(f"  {name}: {stats}")
    print(f"Saved report to {args.out}")


if __name__ == "__main__":
    main()
