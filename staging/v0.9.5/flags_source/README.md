# ISS26 v0.9.5 — direct national-flag reconstruction

**This is patch source code, not a Universal Tool feature and not yet a published game update.** Do not promote `latest.json` until a full independent patch passes flag image and in-game checks.

## Verified against the user's clean EU Track01 (SHA-256 D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44)

- Located the actual legacy Winning Eleven graphics codec in the public `maxiducoli/WECompressor` repository (see `WECompress.cpp`); reimplemented bounds-checked decoding and recompression in `wecodec.py` here.
- Decoded **94/94** compressed texture uploads in `DATSEL2.BIN`, `DATSEL3.BIN`, `EDT_2D.BIN`, and `EDTR_2D.BIN` to *exact* VRAM byte lengths.
- Decoded **1120/1126** graphics uploads across those four files and 34 GDC variants; five of the six exceptions are already raw uncompressed uploads, one needs separate handling.
- Encoded/decode-round-tripped all 94 original menu/editor blocks byte-for-byte at the decoded-pixel level, with no checksum/pointer changes. **84/94** recompressions already fit their original allotted byte ranges; other blocks must be skipped or safely repacked with pointer relocation after separate verification.
- Rendered original uncompressed VRAM index atlas previews to confirm that the decoded graphics include actual national-flag imagery (unlike the earlier v1.2 CLUT gallery that only found 5 raw stadium tiles).
- `repack.py` allows fixed-range replacement of a **known** compressed payload only after exact unpack/repack check and size-budget check. Unknown mapping is never guessed.
- Seven synthetic codec/repack unit tests pass.

## Exact remaining release blockers

1. Associate each team with the correct 64x28, 24x16, and 24x8 flag artwork in the original resources; preserve all 37 national styles not being replaced.
2. Rebuild 17 modern national flags: Cabo Verde, Algeria, Côte d'Ivoire, Ghana, DR Congo, Haiti, Curaçao, Jordan, Iraq, New Zealand, Bosnia, Senegal, Canada, Ecuador, Panama, Uzbekistan, Qatar.
3. Locate/repair the corresponding CLUT rows and all style-pointer mappings. Ensure Senegal does not overwrite shared legacy style 0 and CLUT index 0 remains transparent. 
4. Replicate validated flag art across the selection, editor, and 34 stadium GDC resource variants; preserve other textures, clubs and all CD audio.
5. Apply changes to the official clean-original v0.9.4 independent XOR baseline (rather than previous patched installation), rebuild `.iss26p`, validate sector SHA/EDC/ECC and reconstructed SHA, and visually test the game before publishing.

The world-map country highlighting is **out of scope and must remain untouched**, by user request.

Use `python -m unittest discover -s staging/v0.9.5/flags_source -p 'test_*.py'` to run the basic codec tests.

## 2026-11-09: two-flag repair work (Bosnia + Cabo Verde)

The new source is **not yet a playable fix**. It addresses graphics construction and
the earlier failure to distinguish game-menu uploads from stadium-time uploads.

- `two_flag_art.py` constructs opaque, indexed 4bpp artwork at 64×28, 24×16,
  and 24×8; `blit_onto_gpu_upload()` changes only VRAM upload pixel intersections.
- Original large flag slots: Bosnia = style 10 at VRAM words (864,320);
  Cabo Verde = style 1 at (848,256). These are **candidate mappings** from
  the v0.9.5 investigation, not proof of correct in-match rendering.
- Bosnia semantic CLUT indices are known: blue 1, yellow 2, white 3.
  Cabo Verde's actual semantic CLUT indices must be verified; synthetic indices
  in the tests are NOT allowed to be inserted into a release.
- `flag_upload_locator.py` reads a locally supplied clean MODE2/2352 Track01,
  walks ISO9660 and audits DATSEL / editor / GDC resources for command rectangles
  that overlap the two large-flag tiles; candidates are not silently modified.
- `test_two_flag_art.py`, `test_flag_upload_locator.py` cover position mapping,
  flag geometry, 4bpp packing, protection of adjacent pixels, source discovery.

Read-only scan example:

    python staging/v0.9.5/flags_source/flag_upload_locator.py "ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin" --output ISS26_two_flag_uploads.json

Run tests:

    python -m unittest discover -s staging/v0.9.5/flags_source -p "test_*.py"

**Outstanding release blocker:** identify which command sources load the flags
at each phase (selection, pre-match, field), including late stadium overwrites;
rebuild and reverse-decode all affected resources, find the pre-match name glyphs,
then reconstruct an original-SHA-guarded independent patch. Do not update
public latest.json, touch world-map highlights, or claim a verified 0.9.5.
