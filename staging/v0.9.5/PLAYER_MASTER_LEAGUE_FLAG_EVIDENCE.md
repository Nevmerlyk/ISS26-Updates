# ISS26 v0.9.5 — Master League player nationality flags: original EU disc evidence

**Scope:** only national flag images; no changes to club/player database, names, teams, formations, or stable version. This finding supersedes assumptions that Bosnia/Canada tiny flags must be created from scratch.

## Confirmed from untouched EU Track01 SLES-03321 (SHA256 D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44)

The user's three Player Acquisition screenshots show a visible Bosnia and Herzegovina 4-color small icon for **Salamic**, **Balbarez** and **Kapitonic**, and a red/white maple-leaf **Canada** icon for **Forest**. These names and additional nationality strings also already exist in the **unmodified** disc.

`SELECT.BIN` (LBA 850) contains a 10-byte string table beginning at offset `0x1340`. Each name's exact **name-cell** index is:

| Player | Name-cell index | SELECT.BIN offset | Raw Track01 offset | Country observed in screenshot |
|---|---:|---:|---:|---|
| Kapitonic | 321 | 0x1FCA | 0x1EA4D2 | Bosnia |
| Balbarez | 322 | 0x1FD4 | 0x1EA4DC | Bosnia |
| Salamic | 323 | 0x1FDE | 0x1EA4E6 | Bosnia |
| Forest | 337 | 0x206A | 0x1EA6A2 | Canada |

**Caveat:** these offsets identify name records, NOT yet the nationality field in player-stat structures. Do not treat index 321 etc as nationality IDs.

Original `SELECTC.BIN` (LBA 1950) already has `Canada` at offset 0x5C18 / physical 0x4664E0, `Bosnia Herzegovina` at 0x5C6C / physical 0x466534; they occur in the additional Master League nationality-name bank alongside NZ, Ghana, etc.

`BIN/DAT2D.BIN` (LBA 5300) is an original graphics resource. Independent read-only parsing finds **21 4bpp texture uploads**, **267 CLUT upload records**, **262 16-color CLUT uploads**, and **5 256-color CLUT uploads**. The 54 normal national-team CLUTs span IDs 144–197 (command indices 155–208).

**Palette-color candidates requiring runtime verification:**
- CLUT ID **206**, data offset **0xEBE0** / raw CD **0xBF4428**: BGR555 blue `CC80`, yellow `833F`, white `F7BD`. Compatible with Bosnia's visual colors; *not* proof of a particular sprite or player ID.
- CLUT ID **211**, data offset **0xEC80** / raw CD **0xBF44C8**: red `94BD`, white `F7BD`, light `DF39`. Compatible with red/white flags, but not uniquely Canada.

Both candidate IDs are outside normal 54 national CLUT IDs. This is a strong reason to investigate **a second nationality palette/index space** rather than reassigning national-team flag style numbers to unsupported values.

### What is NOT established

- The numeric nationality fields of the 4 player records have **not** yet been extracted.
- The exact VRAM `tpage`, `u/v` sprite coordinate, actual CLUT selection, and bitmap for the two icons have **not** yet been established from live GPU primitives.
- The user's hypothesis that the Master League icon and tiny match-scoreboard icon share a pixel source is **plausible but unproven**. False-color texture matching produced false positives (e.g. Peru-style red/white/red bands without Canada's maple leaf).
- A flag-colored palette alone does not constitute a working game patch.

### Required proof and release gate

Capture GPU primitives / VRAM once with an actual Master League player row selected and once in national-team match HUD for the same country, then compare **texture page, UV, selected CLUT, rendered pixels**. Use those observations to route the correct graphics into national team selection, pre-match, match entrance and HUD. Preserve all already-working Master League icons; never overwrite other nations or player records.

The v0.9.5 game patch **must not be promoted** from this source investigation until the affected archives and runtime screens have passed checks on top of clean-original v0.9.4.
