# ISS26 v0.9.5 — Test20 prematch flag provenance follow-up

Status: **diagnostics only; NOT a game-patch release**.

## Evidence and verified source

- Owner clean European 12-track image: Track01 SHA256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
- The original ISO payloads `BIN/DATSEL.BIN` (LBA 6000), `BIN/DATSEL2.BIN` (6150), `BIN/DATSEL3.BIN` (6250), `BIN/DAT2D.BIN` (5300) each hash-match the earlier independent resource catalog.
- Test12 verified GP0 draw destination for the two prematch 64×28 indexed flags: Cape Verde `(560,0)`, Bosnia `(560,28)` VRAM 16-bit-word coordinates. Their known matching atlas regions were `(848,256)` and `(864,312)` in that capture.
- Bosnia CLUT in that GPUDUMP is `(224,506)`; Cape Verde uses `(0,505)`. Do not substitute the old reverse national palette slot for the actual draw CLUT.
- A 64×28 style atlas is arranged in **28-pixel vertical steps**, NOT 32. The earlier offline `tools/analyze_flag_autotest_zip.py` had a false stride and rejected modern 2MB PCSX-Redux VRAM captures.
- The owner's Test20 visual report still did not pass. Screenshots and a frame-3217 menu capture do not, by themselves, identify the source responsible for the stadium-intro flag textures. The currently available report is **not** a complete verified last-writer trace.

## What this diagnostic branch changes

`tools/analyze_flag_autotest_zip.py` now accepts both 1MB and 2MB raw VRAM, uses the correct 28-row stride, and for **each** captured frame records the destination/source 4bpp tile digests and equality of the two known prematch flag areas. It reports actual prematch CLUT zero-color collisions and generates four PPM reference images per snapshot (two old style references and two actual prematch destination tiles).

Its `prematch_flags` section answers **what differs at the capture**, **not** which disc resource, MIPS routine, or GPU upload wrote the texture. It never modifies the game, patch feeds, saves, or user files.

## Next independently testable research goal

Capture a real stadium-intro session with at least one VRAM state **before** and **after** the big flags appear, plus a synchronous GPU command trace. Observe the MIPS staging-memory regions around `0x800CC600` and `0x800CC980` **read-only** at the same event. Correlate the first write to the VRAM destinations `(560,0)` / `(560,28)` to a specific upload packet and then to its decompression source; do not infer the uploader from merely identical tile pixels.

Only after unique provenance is verified should Test21 change those source atlas bytes. Preserve 54 national team slots, all 24 clubs, unrelated names and sprites, and tracks 02–12; rebuild the standalone `ISS26X01` sector patch from **clean original** and validate EDC/ECC plus an in-emulator visual smoke test. Keep `stable/latest.json` on 0.9.4 and do not advance the test feed merely because the analyzer passes its synthetic tests.
