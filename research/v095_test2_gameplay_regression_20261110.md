# ISS26 v0.9.5 Bosnia + Cabo Verde TEST2 — gameplay regression (10 Nov 2026)

Status: **TEST2 boots, but does NOT fix the in-match flags or pre-match labels**. User tested the published test-channel game with PCSX-Redux and supplied three screenshots. **Do not promote TEST2 to stable.** No change to Play Game or stable manifests is warranted.

## Observed in actual emulator

- Pre-match Key Square Stadium shows **Russia** (left) and **Ireland** (right), despite intended Bosnia and Cabo Verde replacements.
- Pre-match large left flag appears as yellow/white/blue horizontal bands with a central artifact; right flag appears as blue/red vertical bands with a central artifact.
- Stadium entrance uses the same incorrect large flags on the carried 3D banners; *not* the desired blue/yellow diagonal with white stars and navy/white/red striped Cabo Verde flag.
- HUD uses tiny legacy-like flag icons on the scoreline, inconsistent with real Bosnia and Cabo Verde.
- Game launches and plays, so this is a *runtime graphics/text source* bug, not a test manifest or boot failure.

## Confirmed offline after gameplay feedback

Original clean EU Track01 SHA-256:
`D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.

Standalone TEST2 `ISS26X01` patch SHA-256:
`4C3B27A7EFA46F97401138C7B2490CC08CC693613CDFB82A9BA12150BA7CD330`.
106 changed raw 2352-byte sector XOR records; reconstructed resources from clean original (without changing original input) confirm patched GPU compressed streams really differ in DATSEL, DATSEL3 and GDC_FD.

At `GDC_FD` (example stadium), when applying the edited Cabo Verde CLUT to the 64×28 tile at VRAM word X=848, Y=256, the old graphic is a cross with an emblem and the modified graphic is the intended striped/star artwork (997 changed 4bpp pixel indices). Likewise Bosnia at VRAM word X=864, Y=320 becomes the intended yellow-triangle/star artwork (1785 changed 4bpp indices). All tested streams decode successfully, but the *game screenshot remains different*. This establishes that disk-side upload changes exist and are not sufficient to change the actual gameplay imagery. Runtime ownership is unverified; do **not** guess that a single GDC command directly provides the final texture.

**Additional confirmed flaw in TEST2 name routine:** the broad string replacement `IRELAND` → `C.VERDE` also transforms `NORTHERN IRELAND` into `NORTHERN C.VERDE` inside both `SELECT.BIN` and `ENDING.BIN`. Replace this with specific table-slot writes only, never unrestricted byte replacements.

Known short-names arrays contain historical `RUS` and other unchanged abbreviations. Pre-match large names do not use the two modified literal long-name tables, or are generated through another rendering path. Their authoritative source is not proven.

## Next targeted work

1. Compare a **real PCSX-Redux GPU VRAM/SaveState capture from TEST2** at pre-match and stadium entrance against the patched GDC/DATSEL decoded atlas.
2. Locate the *last uploader* (including overwrites) and actual in-match UV locations for 64×28 and the distinct 24×16 and 24×8 flags. Trace commands / RAM pointers rather than guessing more sprite offsets.
3. Find the pre-match compositor's authoritative text/glyph bank, and update team-specific names without touching unrelated substring matches.
4. Rebuild a fresh **standalone clean-original** test patch with per-sector guards, Mode2 Form1 EDC/ECC, confirmed result digest. Test Bosnia/Cabo Verde on selection, pre-match, 3D entrance and scoreline.
5. Continue to keep stable Play Game untouched. The `test/latest.json` URL now legitimately points to the GitHub prerelease TEST2, but this should be treated as a diagnostic preview only.

**Do not declare a corrected TEST3 before actual resource ownership is established.**
