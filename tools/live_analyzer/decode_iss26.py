#!/usr/bin/env python3
"""Read-only decoder for ISS26 Live Analyzer's sampled RAM deltas.

Usage:
    python decode_iss26.py baseline_RAM.bin RAM_deltas.bin

Outputs next to RAM_deltas.bin:
    *_frame_summary.csv  (changed-byte counts per RAM scan)
    *_hot_pages.csv      (most frequently changed 4 KiB RAM pages)

Can optionally reconstruct last sampled RAM:
    python decode_iss26.py baseline_RAM.bin RAM_deltas.bin --reconstruct
"""
from __future__ import annotations

import argparse
import collections
import csv
import pathlib
import struct

RAM_SIZE = 0x200000
MAGIC = b"ISS26D1\x00"
RECORD = struct.Struct("<IIH")
PAGE_SIZE = 4096


def analyse(baseline: pathlib.Path, logfile: pathlib.Path, reconstruct: bool) -> None:
    ram = bytearray(baseline.read_bytes())
    if len(ram) != RAM_SIZE:
        raise SystemExit(f"Baseline must be {RAM_SIZE} bytes, got {len(ram)}")

    frame_changes = collections.Counter()
    frame_runs = collections.Counter()
    page_changes = collections.Counter()
    total_runs = 0
    total_changed = 0
    previous_frame = -1

    with logfile.open("rb") as src:
        if src.read(len(MAGIC)) != MAGIC:
            raise SystemExit("Invalid ISS26 RAM delta file signature")
        while True:
            header = src.read(RECORD.size)
            if not header:
                break
            if len(header) != RECORD.size:
                raise SystemExit("Incomplete record header")
            frame, offset, size = RECORD.unpack(header)
            if not 1 <= size <= PAGE_SIZE or offset + size > RAM_SIZE:
                raise SystemExit(
                    f"Invalid frame={frame} offset=0x{offset:X} size={size}")
            if frame < previous_frame:
                raise SystemExit("Frame numbers must be nondecreasing")
            previous_frame = frame
            payload = src.read(size)
            if len(payload) != size:
                raise SystemExit("Truncated RAM delta payload")
            ram[offset:offset + size] = payload
            frame_changes[frame] += size
            frame_runs[frame] += 1
            start_page = offset // PAGE_SIZE
            end_page = (offset + size - 1) // PAGE_SIZE
            for page in range(start_page, end_page + 1):
                start = max(offset, page * PAGE_SIZE)
                end = min(offset + size, (page + 1) * PAGE_SIZE)
                page_changes[page] += end - start
            total_runs += 1
            total_changed += size

    out_frames = logfile.with_name(logfile.stem + "_frame_summary.csv")
    out_pages = logfile.with_name(logfile.stem + "_hot_pages.csv")
    with out_frames.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["vsync", "changed_bytes", "delta_runs"])
        for frame in sorted(frame_changes):
            writer.writerow([frame, frame_changes[frame], frame_runs[frame]])
    with out_pages.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ram_offset", "PS1_address", "cumulative_changed_bytes"])
        for page, count in page_changes.most_common():
            writer.writerow([f"0x{page * PAGE_SIZE:06X}",
                             f"0x{0x80000000 + page * PAGE_SIZE:08X}", count])

    print(f"Valid RAM log: {total_runs:,} delta runs, {total_changed:,} changed bytes")
    print(f"Logged scans with changes: {len(frame_changes)}")
    print(f"Last delta frame: {previous_frame}")
    print(f"Reports: {out_frames.name}; {out_pages.name}")
    if reconstruct:
        out = logfile.with_name(logfile.stem + "_reconstructed_RAM.bin")
        out.write_bytes(ram)
        print(f"Last sampled RAM reconstructed: {out.name}")
        print("Note: this can differ from _final_RAM.bin if the last RAM scan")
        print("happened before recording was stopped.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", type=pathlib.Path)
    ap.add_argument("deltas", type=pathlib.Path)
    ap.add_argument("--reconstruct", action="store_true",
                    help="write the latest sampled RAM into a new BIN")
    args = ap.parse_args()
    analyse(args.baseline, args.deltas, args.reconstruct)


if __name__ == "__main__":
    main()
