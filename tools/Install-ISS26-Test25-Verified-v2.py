#!/usr/bin/env python3
"""ISS26 Test25 verified standalone installer v2.

Works ONLY on the owner's clean European 12-track ISS Pro Evolution 2 dump.
It verifies BOTH full SHA-256 hashes, all 1492 per-sector source guards, XOR
record ordering, raw CD sector header preservation and Bosnia style routing.
It does NOT mistake a sector XOR *mask* for an independent CD sector.
Never changes original tracks, the original CUE, or any ISS26 update feed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
from urllib.request import Request, urlopen

CLEAN_SHA = "D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
PATCH_SHA = "85014C8222A408344704CCD8FC192379645E18770876CF4501324D504D55BA67"
PATCH_URL = (
    "https://github.com/Nevmerlyk/ISS26-Updates/releases/download/"
    "v0.9.5-bosnia-style-test25/ISS26_0.9.5_BosniaStyle_TEST25.iss26p"
)
CUE_NAME = "ISS Pro Evolution 2 (Europe) (En,Fr,De).cue"
TRACK_NAME = "ISS26_Test_0.9.5_TEST25_Track01.bin"
TEST_CUE = "ISS26_Test_0.9.5_TEST25.cue"
SECTOR = 2352
COUNT = 1492
RECORD = 4 + 32 + SECTOR
PATCH_BYTES = 12 + COUNT * RECORD
STYLE_OFFSETS = (0x1D6F48, 0x1E94CC, 0x224C50, 0x4AD4B8, 0x575864)
FILES_LINE = re.compile(
    r'(?im)^(?P<lead>[ \t]*FILE[ \t]+)"(?P<name>[^"\r\n]+)"'
    r'(?P<end>[ \t]+BINARY[ \t]*)$'
)


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(4 * 1024 * 1024):
            h.update(block)
    return h.hexdigest().upper()


def check(cond: bool, reason: str) -> None:
    if not cond:
        raise ValueError(reason)


def read_cue(game_dir: Path) -> tuple[Path, str, list[re.Match[str]]]:
    original_cue = game_dir / CUE_NAME
    check(original_cue.is_file(), f"Original CUE not found: {original_cue}")
    cue_text = original_cue.read_text(encoding="utf-8-sig", errors="replace")
    matches = list(FILES_LINE.finditer(cue_text))
    check(len(matches) == 12, f"Expected twelve FILE BINARY entries, got {len(matches)}")
    first = matches[0].group("name")
    check("(Track 01).bin" in first, f"Unexpected original Track01 name: {first}")
    track01 = (original_cue.parent / first).resolve()
    check(track01.is_file(), f"Original Track01 not found: {track01}")
    for num, m in enumerate(matches[1:], 2):
        name = m.group("name")
        check(f"(Track {num:02d}).bin" in name,
              f"Unexpected original Track {num:02d} name: {name}")
        check((original_cue.parent / name).is_file(),
              f"Missing audio track: {name}")
    return track01, cue_text, matches


def load_patch(path: Path | None) -> bytes:
    if path is not None:
        print(f"Reading official Test25 patch: {path}", flush=True)
        patch = path.read_bytes()
    else:
        print("Downloading official Test25 patch from pinned GitHub release...", flush=True)
        with urlopen(Request(PATCH_URL, headers={
            "User-Agent": "ISS26-Test25-Clean-Original-Installer-v2",
            "Accept": "application/octet-stream",
        }), timeout=90) as response:
            patch = response.read(PATCH_BYTES + 1)
    got = hashlib.sha256(patch).hexdigest().upper()
    check(len(patch) == PATCH_BYTES,
          f"Wrong official patch length: {len(patch)} != {PATCH_BYTES}")
    check(got == PATCH_SHA, f"Wrong official Test25 SHA256: {got}")
    check(patch[:8] == b"ISS26X01", "Wrong patch magic")
    count, = struct.unpack_from("<I", patch, 8)
    check(count == COUNT, f"Unexpected sector count: {count}")
    print("PASS official Test25 SHA256:", got, flush=True)
    return patch


def apply_patch(tmp: Path, patch: bytes) -> None:
    previous_lba = -1
    track_sector_count = tmp.stat().st_size // SECTOR
    with tmp.open("r+b", buffering=1024 * 1024) as target:
        for i in range(COUNT):
            at = 12 + i * RECORD
            lba, = struct.unpack_from("<I", patch, at)
            check(previous_lba < lba < track_sector_count,
                  f"Unsorted/invalid patch LBA {lba} at record {i}")
            previous_lba = lba
            expected_guard = patch[at + 4:at + 36]
            mask = patch[at + 36:at + RECORD]
            check(not any(mask[:24]), f"CD header/subheader mutation in mask at LBA {lba}")
            target.seek(lba * SECTOR)
            original_sector = target.read(SECTOR)
            check(len(original_sector) == SECTOR,
                  f"Short source sector at LBA {lba}")
            actual_guard = hashlib.sha256(original_sector).digest()
            check(actual_guard == expected_guard,
                  f"Clean-original source-sector guard mismatch at LBA {lba}")
            modified_sector = bytes(a ^ b for a, b in zip(original_sector, mask))
            check(modified_sector[:24] == original_sector[:24],
                  f"Patched CD header changed at LBA {lba}")
            target.seek(lba * SECTOR)
            target.write(modified_sector)
        target.flush()
        os.fsync(target.fileno())
    print(f"PASS {COUNT} original sector SHA256 guards and CD headers", flush=True)
    print("NOTE: masks are XOR deltas, not independently encoded CD sectors.", flush=True)


def check_styles(tmp: Path) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    with tmp.open("rb") as stream:
        for offset in STYLE_OFFSETS:
            stream.seek(offset)
            row = stream.read(78)
            check(len(row) == 78, "Truncated style table")
            # Verified official Test25 target: style1 Cape, style55 Bosnia,
            # club slot 54 retains style10 on all five source tables.
            check((row[0], row[30], row[54]) == (1, 55, 10),
                  f"Unexpected style routing at byte offset {offset:#x}: "
                  f"Cape={row[0]}, Bosnia={row[30]}, club54={row[54]}")
            rows.append({"offset": offset, "cape_verde": row[0],
                         "bosnia": row[30], "club54": row[54]})
    print("PASS five style tables: Cape=1, Bosnia=55, club54=10", flush=True)
    return rows


def install(game_dir: Path, local_patch: Path | None) -> None:
    game_dir = game_dir.expanduser().resolve()
    check(game_dir.is_dir(), f"Game directory not found: {game_dir}")
    print("ISS26 Test25 verified installer v2")
    print("Original EU game directory:", game_dir)
    original, cue_text, matches = read_cue(game_dir)
    output_track = game_dir / TRACK_NAME
    output_cue = game_dir / TEST_CUE
    temp_track = game_dir / (TRACK_NAME + ".building")
    temp_cue = game_dir / (TEST_CUE + ".building")
    check(original != output_track, "Refusing to modify original Track01")
    print("Checking untouched European Track01 SHA256...", flush=True)
    actual = digest_file(original)
    check(actual == CLEAN_SHA,
          f"Wrong original Track01 SHA256: {actual}. Use only untouched EU dump.")
    print("PASS clean original:", actual, flush=True)
    patch = load_patch(local_patch)
    if temp_track.exists():
        temp_track.unlink()
    try:
        print("Copying clean Track01 (the original remains untouched)...", flush=True)
        shutil.copyfile(original, temp_track)
        check(temp_track.stat().st_size == original.stat().st_size,
              "Track01 copy size mismatch")
        print("Applying verified Test25 XOR records...", flush=True)
        apply_patch(temp_track, patch)
        styles = check_styles(temp_track)
        output_sha = digest_file(temp_track)
        # Keep the CUE beside the original CUE so FILE references to
        # Tracks 02..12 continue to work without copying audio tracks.
        first = matches[0]
        cue_output = (cue_text[:first.start("name")] + TRACK_NAME
                      + cue_text[first.end("name"):])
        temp_cue.write_text(cue_output, encoding="utf-8", newline="")
        os.replace(temp_track, output_track)
        os.replace(temp_cue, output_cue)
        report = {
            "stage": "TEST25 EXPERIMENTAL - NOT STABLE",
            "installerVersion": 2,
            "originalTrack01SHA256": CLEAN_SHA,
            "officialPatchSHA256": PATCH_SHA,
            "outputTrack01SHA256": output_sha,
            "patchedRecords": COUNT,
            "allOriginalSectorGuardsVerified": True,
            "originalTrackAndCueUntouched": True,
            "audioTracks02to12ReferencedUnmodified": True,
            "styleTables": styles,
            "experimentalVisualCheckRequired": True,
            "bosniaArtworkVerified": False,
        }
        report_path = game_dir / "ISS26_Test25_install_report.json"
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print()
        print("SUCCESS: created separate experimental Test25 game:")
        print("CUE:", output_cue)
        print("Track01 SHA256:", output_sha)
        print("Report:", report_path)
        print("Original BIN/CUE, stable patch, and audio tracks were NOT changed.")
        print("Next: launch this new CUE in ePSXe and inspect Cape Verde vs Bosnia.")
    finally:
        for path in (temp_track, temp_cue):
            if path.exists():
                path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, default=Path(r"D:\ISS 26"))
    parser.add_argument("--patch", type=Path,
                        help="Optional locally saved official Test25 .iss26p file")
    args = parser.parse_args()
    try:
        install(args.game_dir, args.patch)
        return 0
    except (OSError, ValueError) as error:
        print("ERROR:", error, file=sys.stderr, flush=True)
        print("Original game files were not modified.", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
