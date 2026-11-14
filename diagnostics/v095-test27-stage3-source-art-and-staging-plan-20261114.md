# ISS26 game v0.9.5 — Test27 stage 3: national flag graphics preparation

**Date:** 2026-11-14. **Status:** Test27 engineering started, 19/19 synthetic
regressions passed. **Not a playable game patch.** No edited BIN/CUE, no stable
or test update feeds, no claims that 54+4 national flags have been fixed.

## Verified source evidence (from completed Test26)

- At the Test25 stadium capture (frame 5468 onwards), Bosnia `style55`
  atlas tile (816,368) and away stage (560,28) have the same **256
  nonzero 16-bit words**, but 192 bottom-row words are zeroed. The entire
  rows y16..27 (12 rows) are wiped; 384 nonzero 4bpp indices disappear.
  This is an exact rectangular mask, not scattered corruption.
- Cape Verde stage (560,0) equals the style1 source (848,256) exactly,
  yet **does not prove its art is the correct Cape Verde flag**.
- The GPU samples the away source using CLUT (224,506) and UV extending to
  y55, including the masked bottom part. The real last writer has not been
  captured. Neither audience waving flags nor fabric carriers are
  identified simply by auto-generated capture filenames.
- MIPS wrapper chain confirmed in original-disassembly research:
  `MoveImage 0x8003884C` into VRAM stage, `StoreImage 0x800387EC`
  stage-to-RAM and `LoadImage 0x8003878C` RAM-to-VRAM. Original
  SELECT JAL sites: 0x80093338 / 0x800933CC (home/away MoveImage),
  0x80092F58 (StoreImage) and 0x8009312C (LoadImage).
  The zeroing **might occur at several points in this chain**, so do
  not infer that a MoveImage's height was definitely 16.

## Implemented in this PR

1. `tools/test27_flag_art_4bpp.py`: deterministic 64x28, 896-byte,
   4bpp candidate art for Bosnia and Cape Verde, separate 16-entry
   BGR555 palettes (32 bytes), 8x RGB PNG/PPM previews and manifest.
   Palette index 0 is reserved; artwork uses nonzero indices on every
   row. This prevents the candidate itself from containing an all-zero
   lower stripe. **It does not prevent the game's loader from wiping it.**
2. `tools/test27_stage_writer_guard.py`: clean-EU static MIPS guard
   for all four SELECT JAL sites and all five original 78-slot style
   tables, including original Bosnia national slot30/style7 and club
   slot54/style10. Validates original Track01 SHA256 before inspecting
   and declines to patch anything. This **does not prove** the runtime
   last writer. It is not executed on a genuine ROM in CI.
3. `tools/test27_extract_real_flag_pixels.py`: optional *owner-local*
   visual source/CLUT audit for the **existing** Test26 session ZIP
   SHA256 611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690.
   It opens the frame-5468 VRAM snapshot and exports 10 local PNGs:
   source/staging CLUT, zero-marked, and source-vs-stage difference
   for Cape and Bosnia, plus metadata. This is NOT the old Test26
   hash comparison repeated; its purpose is to inspect actual palette
   art, which has not yet been observed in this runtime. No original
   game sprites or screenshot bytes are uploaded by the GitHub workflow.
4. `.github/workflows/validate-v095-test27-flag-art.yml`:
   Python compilation, 8 4bpp sprite tests + 7 MIPS original-table
   synthetic guard tests + 4 synthetic real-VRAM extractor tests,
   stable/test feed guard and artifact generation with 2 candidate tiles,
   2 palettes and 2 PNG previews.
   **Green run:** https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43622214133

## Official flag construction references

- [Law on the Flag of Bosnia and Herzegovina, Art. 3 (as quoted by Constitutional Court)](https://www.ustavnisud.ba/uploads/odluke/_en/U-11-19-1218642.pdf):
  blue base; yellow triangle right of centre; diagonal row of white
  five-point stars, ratio 1:2. At **64x28 pixels** the current raster
  is only an approximation: actual star spacing and fabric display
  must be visually validated.
- [CIA World Factbook 2024 — Cabo Verde](https://www.thefactbook.org/cabo-verde/2024):
  blue background; upper blue half, white-red-white one-twelfth-height
  bands, blue lower quarter; ring of 10 yellow stars at 3/8 of flag
  length. The 64x28 game atlas does not share the flag's source ratio;
  final game display needs review.

## Commands

Build the candidate images *without original game files*:

```bash
python tools/test27_flag_art_4bpp.py --output-dir build/Test27_FlagArt
```

Optional offline inspection on owner's **unchanged clean original**:

```bash
python tools/test27_stage_writer_guard.py --original-track01 "ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin" --report Test27_StageGuard.json
```

Optional private actual-style/CLUT visual audit using the *existing* session
ZIP; it never modifies the game or retransmits copyrighted sprites:

```bash
python tools/test27_extract_real_flag_pixels.py --academy-zip 20261114_154539_315b0c.zip --output-dir Test27_Real_Flag_Previews
```

## Next engineering gate (still open)

- [ ] Examine the actual style55 and style1 PNG/CLUT; determine whether
  the unused former slot contains unrelated/incorrect crest art. Review
  Bosnia partial stars against the official geometry and Cape ten stars.
- [ ] Prove source-resource ownership for the selected team's national
  flag graphics in DATSEL/DATSEL3/GDC, including stadium-dependent GDC_BN.
- [ ] Trace MIPS/GP0 final stage writer at frames 4534..5468 and decide
  whether full 28-row copies are safe or how to fix the downstream mask.
- [ ] Independently identify player-carried ceremonial cloth and spectator
  waving flags from actual visually verified frames and GP0 primitives.
- [ ] Produce **one self-contained** clean-original Track01 ISS26X01
  v0.9.5 candidate, preserve EDC/ECC and audio tracks 02..12, 54
  standard +4 bonus national slots and 24 clubs. Protect club
  style10/slot54 and all five style table mappings.
- [ ] Run a targeted match only after a playable candidate exists.
  **Do not promote stable v0.9.4** until every graphical regression
  passes, including names, small flags, crowd and club badges.

This stage produced **usable candidate PS1 art and validated tools**. It
did **not** fix the in-game resources, prove the last writer or publish a
playable Test27/0.9.5 patch.
