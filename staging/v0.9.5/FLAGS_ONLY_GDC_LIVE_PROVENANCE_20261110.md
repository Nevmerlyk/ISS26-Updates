# ISS26 v0.9.5 — flags-only development, live GDC provenance

**Release constraint:** Stable ISS26 is **v0.9.4**. v0.9.5 MUST differ from it only in the 54 national team flags: sprite artwork, national flag CLUT transparency/colors, and necessary flag style bindings. No changes to national team names, 24 clubs, players, kits, tactics, controllers, world map, music, launcher, saves or CD Audio. All patches independently apply to clean EU Track 01, SHA-256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.

## Verified 10 November 2026 — root cause of Bosnia oval during matches

The published 0.9.4 patch **repacked and lengthened all 34** `BIN/GDC_*.BIN` ISO resources. Example `GDC_AD`: original length 140,632, patched length 145,864 bytes; its GPU table2 moved from offset `0x20304` to `0x209B8` with base address `0x800C8000`. The table pointer is in the resource header, not at the original location. Previous sprite experiments edited `DATSEL` / `DATSEL3` only and therefore failed when the stadium-specific GDC atlas reloaded the old pixels.

A direct forensic checker took PCSX-Redux SaveState v5 VRAM from the user's first Bosnia-versus-Germany Test Game and decoded **current patched** GPU upload records (using updated ISO9660 file sizes, header table pointers and WE decompression). For original national styles 0–27, the 64×28 flag atlas is at word-x `832+16*(style%4)`, line-y `256+32*(style//4)`. The live sprite word rectangles **match all 34 patched GDC sources and DATSEL3 bit-for-bit**, not just approximately. For Bosnia's former Slovakia art at style 10, the match is 448/448 16-bit words per tile. This is why the on-field emblem was a blue oval in the screenshots.

## Read-only diagnostic and test candidate

A clean-original independent `ISS26X01` *development test patch* was built locally from the existing palette-corrected 0.9.4 baseline (candidate SHA-256 `CA1910F84EDADB1DCCA3177CEA70F550A6DBDD17173ACBFDB9644F9141ED7404`), without importing any Test2 name-bank changes.

Five original-free national flag styles were redrawn:

| Nation | Text slot | Reverse flag index | Style |
|---|---:|---:|---:|
| Cabo Verde | 53 | 0 | 1 |
| Algeria | 52 | 1 | 3 |
| Bosnia and Herzegovina | 23 | 30 | 10 (remapped from 55 in all five flag-style tables) |
| Ghana | 36 | 17 | 20 |
| DR Congo | 34 | 19 | 24 |

Using current decoded-payload offsets, the candidate replaces **141 compressed graphics uploads** in **36 resources**: `DATSEL`, `DATSEL3` and all **34 GDC** variants. Every modified stream is independently decompressed and compared against its exact intended 64×28 pixel indices; all 141 encoded streams fit in the original allocated spans with no pointer relocation. The smallest spare is 11 bytes for the Cabo Verde stream. **211 CD sectors** differ from the palette-corrected candidate; their Mode2 Form1 EDC/ECC were recomputed. The independent patch retains 1,412 SHA-guarded records, 3,371,868 bytes. In a memory-mapped reconstruction against clean Track01:

- Candidate patch SHA-256: `0D98D46BD82708A0A3B3CA81E28D9E71DC165A140BE49D571C74CA6F477AF56D`
- Result Track01 SHA-256: `CFE3FBF72B3600E0D8D90B295B5C5E732033022E3C815BF028239A3A1A1DDD15`
- All 54 normal national names are unchanged relative to the baseline; no other game features changed.
- The 16 prior CLUT transparency-zero repairs remain in the candidate.
- No user BIN/CUE or CD Audio was modified.

**Crucial: not the complete v0.9.5!** This is an independent *five-country* proof, still not emulator-verified. Its source and portable test installer are provided as an attachment in the project's conversation, not in public Stable.

## Remaining hard blockers before Stable v0.9.5

1. Finish the other **12 replaced national flags**: Qatar, Uzbekistan, Panama, Ecuador, Canada, Senegal, New Zealand, Iraq, Jordan, Curaçao, Haiti, Côte d'Ivoire. Some already use shared low style IDs and/or high IDs 35–60, which require studying UV/style lookup and unused graphics capacity. Do **not** overwrite a shared style used by unchanged nations/clubs.
2. Identify distinct 24×16 and 24×8 sprites, if the selection HUD, match HUD and Edit Mode use them; reconstruct all on-screen sizes and ensure per-nation opaque CLUT colors. Existing 64×28 patches alone cannot prove full coverage.
3. Test actual game in PCSX-Redux Test Game: selection, pre-match animation, on-field giant banners, HUD, Edit Mode and replays, for all 17 changed national flags plus a sampled control set of original flags and clubs.
4. Independently verify all original files, BIN sectors/EDC/ECC, complete preserved team names/club bytes, CUE, 11 audio tracks, restored game and users' saves.
5. After every flag passes, publish **v0.9.5** and only then update `stable/latest.json` atomically; do not recycle the previously rolled-back v0.9.5 release tag.

The 2026-11-09 name-bank test code, earlier Bosnia DATSEL-only proof and previous `v0.9.5A` must not be treated as flags-only stable candidates.
