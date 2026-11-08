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


# Original file extents and modified sector-form counts are from the
# read-only FlagAudit supplied by the game's tester (v0.9.3-preview).
# We inspect only metadata and XOR sector deltas: no copyrighted bytes.
EXPANDED_FILES = (
    ("BIN/DATSEL2.BIN", 6150, 64, 5),
    ("BIN/DATSEL3.BIN", 6250, 27, 2),
    ("BIN/EDT_2D.BIN", 3900, 21, 4),
    ("BIN/EDTR_2D.BIN", 4000, 51, 2),
    ("BIN/GDC_AD.BIN", 12560, 69, 2),
    ("BIN/GDC_AN.BIN", 12730, 69, 3),
    ("BIN/GDC_BD.BIN", 16300, 67, 4),
    ("BIN/GDC_BN.BIN", 16470, 96, 2),
    ("BIN/GDC_CD.BIN", 13240, 67, 2),
    ("BIN/GDC_CN.BIN", 13410, 72, 3),
    ("BIN/GDC_DD.BIN", 10860, 65, 2),
    ("BIN/GDC_DN.BIN", 11030, 65, 2),
    ("BIN/GDC_FD.BIN", 11200, 75, 1),
    ("BIN/GDC_FN.BIN", 11370, 76, 2),
    ("BIN/GDC_GDJ.BIN", 14260, 59, 3),
    ("BIN/GDC_GNJ.BIN", 14430, 59, 3),
    ("BIN/GDC_HD.BIN", 13580, 76, 2),
    ("BIN/GDC_HN.BIN", 13750, 70, 2),
    ("BIN/GDC_ID.BIN", 15280, 79, 2),
    ("BIN/GDC_IN.BIN", 15450, 82, 2),
    ("BIN/GDC_JD.BIN", 11540, 71, 2),
    ("BIN/GDC_JN.BIN", 11710, 67, 2),
    ("BIN/GDC_MD.BIN", 12220, 79, 2),
    ("BIN/GDC_MDJ.BIN", 14600, 79, 3),
    ("BIN/GDC_MN.BIN", 12390, 83, 2),
    ("BIN/GDC_MNJ.BIN", 14770, 80, 3),
    ("BIN/GDC_OD.BIN", 15620, 68, 2),
    ("BIN/GDC_ON.BIN", 15790, 68, 2),
    ("BIN/GDC_PD.BIN", 12900, 60, 3),
    ("BIN/GDC_PN.BIN", 13070, 61, 2),
    ("BIN/GDC_RDJ.BIN", 14940, 73, 2),
    ("BIN/GDC_RNJ.BIN", 15110, 71, 3),
    ("BIN/GDC_SD.BIN", 11880, 67, 3),
    ("BIN/GDC_SN.BIN", 12050, 69, 3),
    ("BIN/GDC_TD.BIN", 13920, 64, 2),
    ("BIN/GDC_TN.BIN", 14090, 66, 3),
    ("BIN/GDC_VD.BIN", 15960, 70, 2),
    ("BIN/GDC_VN.BIN", 16130, 73, 2),
)

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
    expanded_file_audit = []
    for name, lba, original_form1_sectors, added_form2_sectors in EXPANDED_FILES:
        new_lbas = list(range(lba + original_form1_sectors,
                              lba + original_form1_sectors + added_form2_sectors))
        edited = [sector for sector in new_lbas if sector in records]
        untouched = [sector for sector in new_lbas if sector not in records]
        payload_changed_bytes = sum(
            sum(1 for byte in records[sector][1][24:2348] if byte)
            for sector in edited
        )
        expanded_file_audit.append({
            "file": name,
            "newly_included_form2_sector_count": len(new_lbas),
            "newly_included_lbas": new_lbas,
            "patch_modified_included_sectors": len(edited),
            "patch_unmodified_included_sectors": untouched,
            "xor_payload_changed_bytes_in_new_sectors": payload_changed_bytes,
            "caution": "A modified data length includes pre-existing Form2 sectors. "
                       "Whether the PS1 loader reads those as valid data is not verified."
        })
    return {
        "expanded_file_sector_audit": expanded_file_audit,
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
    p.add_argument("--patch-file", type=Path, default=None,
                   help="Offline release asset path, avoids GitHub CDN downloads")
    args = p.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    latest = manifest["latest"]
    patch_bytes = args.patch_file.read_bytes() if args.patch_file else download(latest["patchUrl"])
    records = parse_patch(patch_bytes, latest["patchSha256"])
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
    expanded = result["expanded_file_sector_audit"]
    print(f"Expanded graphic files: {len(expanded)}; newly included Form2 sectors: "
          f"{sum(e['newly_included_form2_sector_count'] for e in expanded)}; "
          f"not modified by patch: {sum(len(e['patch_unmodified_included_sectors']) for e in expanded)}")
    for e in expanded:
        if e["patch_unmodified_included_sectors"]:
            print(f"  WARNING: {e['file']} includes unchanged raw sector LBAs "
                  f"{e['patch_unmodified_included_sectors']}")
    print(f"Saved report to {args.out}")


if __name__ == "__main__":
    main()
