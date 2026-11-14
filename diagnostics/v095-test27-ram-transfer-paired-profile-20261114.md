# ISS26 Test27 — paired GPU staging RAM profiles and real flag contact sheet

**Date:** 2026-11-14. **Status:** source-only implementation, read-only. **Not a game patch.**

## Evidence from Test26 (unchanged)

Owner-reported Academy archive `20261114_154539_315b0c.zip`,
SHA-256 `611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`,
contains 14 VRAM snapshots and 8 live GPUDUMPs. At frame 5468 and later,
the final Bosnia away staging tile `(560,28)` contains precisely the upper
16 rows of source style55 `(816,368)`; all 192 16-bit words of the
lower 12 rows are zero, removing 384 nonzero palette **indices**. Cape Verde
stage matches style1 byte-for-byte.

This proves **stage content loss**, not whether the source's art was the
correct flag or which operation zeroed the lower rows. Previous real-disc
analysis confirmed original shared DATSEL/DATSEL3 and 34 stadium GDC resource
uploads can write overlapping atlas regions; blindly replacing source55
or shared club style10 is not an acceptable fix.

## Added in private Academy source PR #46

The source already captured actual `MoveImage` rectangle dimensions and
`StoreImage`/`LoadImage` wrapper-entry rectangles. It no longer drops
unexpected height 16 calls. This change adds read-only
`STAGE_RAM_PROFILE` records at actual JAL-call and post-return PCs:

| Label | Hook point | Region inspected |
| --- | --- | --- |
| `before-StoreImage` | `0x80092F58` | RAM `0x800CC600` 1792 bytes |
| `after-StoreImage` | `0x80092F60` | Same RAM |
| `before-LoadImage` | `0x8009312C` | Same RAM |
| `after-LoadImage` | `0x80093134` | Same RAM |

Each profile records only four counts of nonzero **16-bit words**:
`home_top` (0–256), `home_bottom` (0–192),
`away_top` (0–256), `away_bottom` (0–192),
plus frame, PC, RA. It does not dump real art into a public repo or write
to RAM/VRAM. Maximum **32 profiles** and a bounded 3 error events.

**Important interpretation:** even a before/after change cannot by itself
prove a GPU DMA finished during the interval. The profiling hook and GPU
transfer may be asynchronous. The complete result needs actual GPU GP0
transfer events and relevant adjacent VRAM captures.

All private Academy source changes are **uncompiled** in the user's current
installation. GitHub Actions in that private repository have failed before
executing steps. Use only a locally verified preview when its build
and emulator compatibility have been confirmed. Do not merge as stable.

## New analysis tooling

[`tools/test27_analyze_stage_writer.py`](../tools/test27_analyze_stage_writer.py)
now pairs `before-/after-` rows of the same operation and records
`stage_ram_bottom_loss_pairs` and observed 16-row mask states without
asserting a causal writer. It rejects invalid field values, malformed PC
addresses and overlong logs.

[`tools/test27_extract_real_flag_pixels.py`](../tools/test27_extract_real_flag_pixels.py)
now generates one additional **1536×448 PNG**:
`Test27_Flag_Source_vs_Stage_Comparison.png`. Row 1 is Cape Verde,
row 2 is Bosnia; columns are the atlas texture rendered with the captured
CLUT, the stage texture with palette index zero marked magenta, and
per-index source–stage differences (red means source nonzero→stage zero).
It still exports the original ten small PNGs plus JSON. This is a
pixel-index comparison, not a verdict on national flag geometry/CLUT.

### One-click owner-local ZIP preview

The [standalone Windows CMD](../tools/Run-ISS26-Test27-RealFlagPreview.cmd)
downloads its own PowerShell runner from **immutable commit
`38b69fc4e0b799f0aa23a64a60b4c1d485d3d5d5`**, rather than using
a stale adjacent local PS1. The PowerShell helper pins the five Python
research modules to **CI-green commit
`7995a5c263ec8641ab5989af5a686cf37ca5de6d`**. All six source URLs
were fetched and verified to exist; SHA check prevents analyzing a
different session. No new match, original game BIN, BIOS or tokens are
needed. The script only reads owner-local ZIP and writes preview files.

On Windows save the CMD, then drag the old ZIP onto it. If the ZIP resides
in the standard `D:\ISS 26\ISS26_Data` area, double-clicking will also
attempt discovery. Reports are written under
`D:\ISS 26\ISS26_Data\diagnostics\Test27_RealFlagPreview`
and the contact sheet opens locally.

The script does not modify the original BIN/CUE/track files, any updater
feed or memory cards, and **does not upload any game art**. It downloads
public source scripts over HTTPS.

## Verification and remaining gate

- [Test27 source CI](https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43627641543):
  **30/30 synthetic tests passed** (8 new flag-art generation, 7 clean-MIPS
  guard, 5 actual-ZIP extractor with synthetic VRAM, 10 stage-writer log
  parser tests); Python compilation and PowerShell runner parsing/pin
  validation passed.
- The actual original BIN and user-session ZIP still cannot be opened by
  the current execution runtime (container ClientError). No real on-disk
  flag comparison PNGs, live `STAGE_RAM_PROFILE` output or playable
  game patch has been produced within this run.
- The next actual game fix requires **(a)** inspect real source55 and
  style1 art/CLUT, **(b)** verify the last staging writer with bounded
  Academy runtime trace, **(c)** apply source changes only where isolated
  from club assets, **(d)** construct full self-contained clean-EU
  `ISS26X01` with correct Mode2 EDC/ECC, and **(e)** verify selection,
  carried banner, prematch, spectator flags, HUD and club badges.
- Game stable feed remains **0.9.4** and test feed remains
  **0.9.5-largeflag-source-test13**. This research phase makes no patch
  publication or promotion claim.
