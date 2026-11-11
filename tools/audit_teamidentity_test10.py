#!/usr/bin/env python3
"""Offline structural audit of official ISS26 Test08 -> Test09 -> Test10 patches.

No original game data is read, modified, uploaded, or distributed.  The
84-sector clean-disc fingerprint was independently calculated from the
user-provided EU PS1 Track01 and is used solely as cryptographic evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

SECTOR = 2352
RECORD = 4 + 32 + SECTOR
BASE_COUNT = 1412
TEST10_COUNT = 1496
RELEASES = {
    "test08": ("E65E5623756643E2DAE7069A66FE888E14439A5A534DBF171BB03630605648B1", BASE_COUNT),
    "test09": ("FA5E3DC3702808E8ABC197C9BB27B0707A4D44575D765918911AD846738D71B2", BASE_COUNT),
    "test10": ("9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B", TEST10_COUNT),
}
BOSNIA_LARGE_GRAPHIC = (6089, 6090, 6256, 6257)
NAMES_LBAS = tuple(range(8200, 8228)) + tuple(range(8230, 8258)) + tuple(range(8260, 8288))
# SHA256 of concatenated SHA256(original sector), sorted by the above LBA order.
# Calculated from the clean 496156752-byte SLES-03321 disc of the owner;
# does not include any original copyrighted game bytes.
NAMES_ORIGINAL_GUARD_FINGERPRINT = "F1BA2A81B5D12FC9698EC3639DAB7021E6946C10E8E70B63789E5CF32D079155"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest().upper()


def load_patch(path: Path, name: str) -> dict[int, tuple[bytes, bytes]]:
    data = path.read_bytes()
    expected, count = RELEASES[name]
    assert sha(data) == expected, f"{name}: release SHA256 mismatch"
    assert data[:8] == b"ISS26X01", f"{name}: wrong magic"
    assert struct.unpack_from("<I", data, 8)[0] == count
    assert len(data) == 12 + count * RECORD, f"{name}: bad file size"
    rows: dict[int, tuple[bytes, bytes]] = {}
    previous = -1
    for i in range(count):
        start = 12 + i * RECORD
        lba = struct.unpack_from("<I", data, start)[0]
        assert lba > previous and lba < 210951, f"{name}: bad LBA {lba}"
        previous = lba
        guard = data[start + 4:start + 36]
        mask = data[start + 36:start + RECORD]
        assert len(guard) == 32 and len(mask) == SECTOR
        assert any(mask), f"{name}: empty sector mask at {lba}"
        rows[lba] = guard, mask
    assert len(rows) == count
    return rows


def audit(test08: Path, test09: Path, test10: Path) -> dict:
    a = load_patch(test08, "test08")
    b = load_patch(test09, "test09")
    c = load_patch(test10, "test10")
    assert a.keys() == b.keys(), "Test08/Test09 LBA sets are not identical"
    changed_08_to_09 = sorted(k for k in a if a[k] != b[k])
    assert changed_08_to_09 == list(BOSNIA_LARGE_GRAPHIC), changed_08_to_09
    assert all(a[k][0] == b[k][0] for k in changed_08_to_09), "Source guards of Test09 changed"

    assert all(b[k] == c[k] for k in b), "Test10 unexpectedly modifies Test09 records"
    new = sorted(set(c) - set(b))
    assert new == list(NAMES_LBAS), f"Wrong Test10 extra LBA set: {new}"
    actual_guard_fingerprint = sha(b"".join(c[k][0] for k in new))
    assert actual_guard_fingerprint == NAMES_ORIGINAL_GUARD_FINGERPRINT, (
        "Original Test10 source-sector fingerprints differ from clean EU disc", actual_guard_fingerprint
    )
    # Raw Mode2 sector sync, address, mode and subheader must stay intact:
    # names atlas updates are constrained to sector data and parity.
    unexpected_headers = [k for k in new if any(c[k][1][:24])]
    assert not unexpected_headers, f"Test10 changes CD header/subheader at {unexpected_headers}"

    changed_bytes = sum(sum(bool(x) for x in c[k][1]) for k in new)
    data_bytes = sum(sum(bool(x) for x in c[k][1][24:2072]) for k in new)
    error_correction_bytes = sum(sum(bool(x) for x in c[k][1][2072:]) for k in new)
    assert changed_bytes == data_bytes + error_correction_bytes
    assert data_bytes > 0 and error_correction_bytes > 0

    return {
        "schema_version": 1,
        "audit": "Test08 -> Test09 -> Test10 independent clean-original patch comparison",
        "verified_release_sha256": {name: value[0] for name, value in RELEASES.items()},
        "track01_reference_sha256": "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44",
        "test08_sector_count": len(a),
        "test09_sector_count": len(b),
        "test10_sector_count": len(c),
        "bosnia_large_graphics_changed_08_to_09": changed_08_to_09,
        "test09_to_test10_preserved_records": len(b),
        "test10_added_prematch_name_sectors": len(new),
        "test10_added_lba_ranges": [[8200, 8227], [8230, 8257], [8260, 8287]],
        "test10_prematch_source_guard_fingerprint": actual_guard_fingerprint,
        "test10_raw_sector_header_changes": len(unexpected_headers),
        "test10_changed_bytes_in_added_sectors": changed_bytes,
        "test10_changed_bytes_in_atlas_data": data_bytes,
        "test10_changed_bytes_in_sector_edc_ecc": error_correction_bytes,
        "status": "PASS: patch hashes, sector guards, added ranges and A/B isolation",
        "limitations": [
            "Does not prove new pixel font is correctly rendered in emulator",
            "Does not prove large flag/stadium textures are fixed",
            "Full game image and user saves are not included or modified",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--test08", type=Path, required=True)
    p.add_argument("--test09", type=Path, required=True)
    p.add_argument("--test10", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit(args.test08, args.test09, args.test10)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
