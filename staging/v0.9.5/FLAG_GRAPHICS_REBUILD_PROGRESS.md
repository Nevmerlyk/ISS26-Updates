# ISS26 0.9.5 — flag graphics rebuild, not released

Owner asked for a **proper 0.9.5 that corrects actual national flag artwork and team labels**, not another palette-only update. Keep stable feed **0.9.4** until visual gameplay checks succeed. A prior 0.9.5 palette-only release was rolled back and must not be mistaken for the corrected project release.

## Verified discovery — original large flag template atlas

Original EU Track01 SHA-256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.

The **28 original large flag styles** reside in 4bpp VRAM at:
```
style = 0 .. 27
VRAM word x = 832 + 16 * (style % 4)
VRAM line y = 256 + 32 * (style // 4)
sprite dimensions = 64 x 28 pixels, within each 64x32 tile
```
This was visually confirmed by applying each nation's original individual CLUT to all 28 tiles. Ireland/Cameroon style0, Northern Ireland style1, Jamaica style2, Wales style3, Brazil style19 etc produced recognizable original flags.

The following five original style IDs became **unreferenced by the 37 unaffected national slots** after the 17 renames: **1, 3, 10, 20, 24**. They are safe candidates for remapping national artwork, whereas merely assigning new high styles (52–60) produced blank/mismatched graphics. Other 11+ unique designs need verified extra atlas capacity and table semantics; do not overwrite a shared style.

## Bosnia large flag proof (experimental, not full release)

A fully independent clean-original `ISS26X01` candidate was built from the pinned 0.9.5 CLUT-corrected candidate (i.e. all v0.9.4 features + repaired 16 transparent CLUT entries). The proof additionally:

- changed Bosnia's reverse flag index 30 from unrenderable style **55** to free original style **10** in five tables;
- generated a 64x28 Bosnia flag using the existing Bosnia CLUT (index1 navy, index2 yellow, index3 white);
- replaced the compressed stream occupying VRAM word x864, y256 in **BIN/DATSEL.BIN** (LBA 6000, command 44, resource offset 182728) and **BIN/DATSEL3.BIN** (LBA 6250, command 5, resource offset 13040);
- both edited WE compressed streams reduced from 1910 to 1763 bytes (147 bytes slack) and decoded back exactly;
- recalculated and verified Mode2 Form1 EDC/ECC for **9** changed sectors: 820, 852, 955, 2085, 2433, 6089, 6090, 6256, 6257;
- retained 1,412 original-SHA-guarded 2352-byte XOR records, 3,371,868 bytes.
- candidate patch SHA-256: `3B667CF6031BC2BFAA143D0D21ACF6D623447C222096805D529739235E2216A4`;
- reconstructed Track01 SHA-256: `5181FC06960A89359EAE62462DB97F1E2FFF709A622BAF85E9D4FE6E97038A7A`;
- **did not modify clean BIN/CUE or audio**.

Local proof package: `ISS26_v095_Flag_Graphics_Rebuild_WORK_IN_PROGRESS.zip` (source and binary candidate available as conversation attachment).

## Unresolved release gates

1. Complete artwork for 17 replaced countries; only Bosnia **large 64x28** proof has changed.
2. Identify and repair **24x16 and 24x8** style UVs and flag pixels across game screens.
3. Account for `EDT_2D`, `EDTR_2D` and all 34 stadium GDC resources, including six nonstandard uploads.
4. Verify restored names on all selection, editor, pre-match, match and ending screens, not only the two identified literal banks.
5. Test flag rendering on real emulator; the Bosnia proof still has **no runtime validation**.
6. Publish a replacement verified full release **only after** these gates. Do not activate or re-label a partial proof as final.

World map highlighting intentionally unchanged.
