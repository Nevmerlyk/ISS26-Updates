# ISS26 v0.9.2 Preview — national flags and team names

This is a fully standalone PS1 game data update for the clean European ISS Pro Evolution 2 (SLES-03321). It includes previous v0.8/v0.9.1 modifications but applies to the original Track 01 independently, never to an installed prior patch.

## National-team-only corrections
- Rebuilds national flag sprites for the 17 renamed teams: Cabo Verde, Algeria, Côte d’Ivoire, Ghana, DR Congo, Haiti, Curaçao, Jordan, Iraq, New Zealand, Bosnia, Senegal, Canada, Ecuador, Panama, Uzbekistan, Qatar.
- Accurate authentic SVG flag motifs reduced to PS1 16-color CLUT palettes. Each national slot has its own RGB555 palette; 17 flags are safely packed into seven styles that no other national or club team uses.
- Repaired three flag sizes (64×28, 24×16, 24×8) in menu, selection, edit and stadium 2D resources. Previous broken 52–60 graphics styles are no longer assigned to these nations.
- Preserves the two already-correct national name banks from v0.9.1: full and abbreviated team names are not overwritten.
- Preserves all 37 other national flag palettes and graphic styles, 24 existing club graphic styles, player data, and CD audio.
- Repairs source file lengths, the DATSEL3 resource sector-load count (28 to 29), MODE2 Form 1 EDC/ECC parity; all changed graphics roundtrip read back from the generated Track 01.

## Important limitations
- This is a **Preview**. Actual display on every gameplay screen remains to be tested on Windows/PS1 emulation; source-decoding tests cannot substitute for screenshots.
- The original map remains based on the old team's geographic slots (e.g. Bosnia highlights the former Russia region): world-map geography is not fixed by this nation-flag/name patch.
- The large club-selection emblems, full 2026 player rosters, music and club graphic updates are out of scope and retain their current behavior.

## Integrity
- SHA-256 of clean original European Track 01: `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`
- SHA-256 of derived Track 01: `E8E8C4A136B68254767991A7F14D4818B6ADA8264FCAFC87FAFDA9E805A548E3`
- SHA-256 of patch: `DFBE3ABB0BE606775AB1E8665A03A7E86DE0501F1C31377792B12FEDCD8D32CB`
- Changed sector records: **1367**
- Patch size: **3,264,408 bytes**

**Source protection:** the original BIN/CUE and CD audio are never modified. The ISS26 launcher derives its patched Track01.bin into portable ISS26_Data. Source flag vectors are from MIT-licensed lipis/flag-icons.
