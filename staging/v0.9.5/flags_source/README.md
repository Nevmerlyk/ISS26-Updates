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
