#!/usr/bin/env python3
"""Read-only comparison of two ISS26X01 releases targeting the SAME clean PS1 BIN.

The XOR format allows comparison of two patched outputs WITHOUT the commercial
original disc: output_A XOR output_B == delta_A XOR delta_B.

This identifies changed sectors/bytes, not what a rendered flag looks like.
Do not publish a new patch or declare visual success from this report alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import time
import urllib.request
from pathlib import Path

SECTOR = 2352
RECORD = 4 + 32 + SECTOR
MAGIC = b"ISS26X01"
MAX_RECORDS = 8192
MAX_BYTES = 32 * 1024 * 1024
TABLES = (0x1D6F48, 0x1E94CC, 0x224C50, 0x4AD4B8, 0x575864)
DEFAULT_REPO = "https://github.com/Nevmerlyk/ISS26-Updates/releases/download"


class PatchError(ValueError):
    pass


def parse_patch(raw: bytes, expected_sha256: str | None = None) -> dict[int, tuple[bytes, bytes]]:
    if expected_sha256:
        got = hashlib.sha256(raw).hexdigest().upper()
        if got != expected_sha256.upper():
            raise PatchError(f"Downloaded patch SHA mismatch: {got}")
    if len(raw) < 12 or raw[:8] != MAGIC:
        raise PatchError("Not an ISS26X01 patch")
    count, = struct.unpack_from("<I", raw, 8)
    if count == 0 or count > MAX_RECORDS or len(raw) != 12 + RECORD * count:
        raise PatchError(f"Invalid record count/patch size: {count}, {len(raw)}")
    records = {}
    previous = -1
    for i in range(count):
        offset = 12 + i * RECORD
        index, = struct.unpack_from("<I", raw, offset)
        if index <= previous:
            raise PatchError("Sector entries must be unique and strictly ascending")
        previous = index
        old_hash = raw[offset + 4:offset + 36]
        delta = raw[offset + 36:offset + RECORD]
        if not any(delta):
            raise PatchError(f"All-zero sector delta at {index}")
        records[index] = old_hash, delta
    return records


def _regions(sectors: list[int]) -> list[dict]:
    regions = []
    for sector in sectors:
        if regions and sector == regions[-1]["end_sector"] + 1:
            regions[-1]["end_sector"] = sector
            regions[-1]["sector_count"] += 1
        else:
            regions.append({"start_sector": sector, "end_sector": sector, "sector_count": 1})
    return regions


def compare(left: dict[int, tuple[bytes, bytes]],
            right: dict[int, tuple[bytes, bytes]]) -> dict:
    touched = []
    byte_count = 0
    table_hits = {hex(x): False for x in TABLES}
    for idx in sorted(left.keys() | right.keys()):
        l = left.get(idx)
        r = right.get(idx)
        if l and r and l[0] != r[0]:
            raise PatchError(f"Different clean-disc source hashes at sector {idx}")
        a = l[1] if l else bytes(SECTOR)
        b = r[1] if r else bytes(SECTOR)
        changed_indices = [j for j, (x, y) in enumerate(zip(a, b)) if x != y]
        if not changed_indices:
            continue
        touched.append(idx)
        byte_count += len(changed_indices)
        start, end = idx * SECTOR, (idx + 1) * SECTOR
        for position in TABLES:
            if position < end and position + 78 > start and any(
                start + j >= position and start + j < position + 78
                for j in changed_indices
            ):
                table_hits[hex(position)] = True
    return {
        "left_record_count": len(left),
        "right_record_count": len(right),
        "changed_sectors_between_releases": len(touched),
        "changed_bytes_between_releases": byte_count,
        "contiguous_sector_regions": _regions(touched),
        "team_style_table_bytes_changed": table_hits,
        "notice": "XOR-diff audit only; cannot validate PS1 CLUT palettes, atlas geometry, "
                  "correct flag mapping, in-game rendering or world map from patches alone."
    }


def download(url: str) -> bytes:
    if not url.startswith("https://github.com/Nevmerlyk/ISS26-Updates/releases/download/"):
        raise PatchError("Only official ISS26 public release URLs accepted")
    error = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ISS26-v094-Audit"})
            with urllib.request.urlopen(request, timeout=90) as response:
                data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise PatchError("Patch exceeds 32 MiB")
            return data
        except Exception as ex:
            error = ex
            if attempt < 4:
                time.sleep(3)
    raise PatchError(f"Unable to download public patch: {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", default="staging/v0.9.2/candidate.json", type=Path)
    parser.add_argument("--right", default="staging/v0.9.3/candidate.json", type=Path)
    parser.add_argument("--out", default="v093_delta_audit.json", type=Path)
    args = parser.parse_args()

    manifests = []
    for filename in (args.left, args.right):
        obj = json.loads(filename.read_text(encoding="utf-8"))
        if obj.get("schemaVersion") != 1 or not isinstance(obj.get("latest"), dict):
            raise PatchError(f"Invalid candidate manifest: {filename}")
        manifests.append(obj["latest"])
    if manifests[0]["baseSha256"] != manifests[1]["baseSha256"]:
        raise PatchError("Patch releases have different clean base BINs")
    left, right = [
        parse_patch(download(m["patchUrl"]), m["patchSha256"]) for m in manifests
    ]
    report = compare(left, right)
    report["left_version"] = manifests[0]["version"]
    report["right_version"] = manifests[1]["version"]
    report["clean_base_sha256"] = manifests[0]["baseSha256"]
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Comparison {report['left_version']} -> {report['right_version']}: "
          f"{report['changed_sectors_between_releases']} sectors, "
          f"{report['changed_bytes_between_releases']} changed bytes")
    print(f"Saved {args.out}")
    print(report["notice"])


if __name__ == "__main__":
    main()
