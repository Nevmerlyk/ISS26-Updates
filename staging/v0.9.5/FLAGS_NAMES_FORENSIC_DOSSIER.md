# ISS26 v0.9.5 — verified flag/name reverse-engineering findings

**Status:** research only, not a released game patch. The original European Track01 was inspected locally, SHA-256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`. The official standalone v0.9.4 patch, SHA-256 `70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE`, was audited without publishing game bytes; see `v094_windows.json`.

## Critical finding: inverted order of the national flags

54 text slots are ordered Australia (0) through Ireland (53). The 54 national flag template/style entries and CLUT entries are in **reverse** order. The verified mapping is:

`flag_style_index = flag_palette_index = 53 - national_name_slot`

This mapping reconciles **all 17 modified names** with the **16 modified flag style entries** in v0.9.4. Senegal reuses its existing style, which is why only 16 style bytes change. Example: Bosnia name slot 23 is flag index 30, template style 7→55; Cabo Verde name slot 53 is flag index 0, style 0→1. A historic ISS Pro Evolution 2 modding guide also explicitly identifies Eire/Ireland as the first flag in these tables.

## Exact file locations

- `ENDING.BIN;1` (LBA 430): 54 short national names beginning at file offset `0x660`; last at `0x850`.
- `SELECT.BIN;1` (LBA 850): 54 long national names beginning at `0xD74`; last at `0xF78`.
- Five 78-byte flag template-index tables in raw Track01 at offsets **`0x1D6F48`** (`OPENNING.BIN`), **`0x1E94CC`**, **`0x224C50`** (both `SELECT.BIN`), **`0x4AD4B8`** (`SELFORM.BIN`), and **`0x575864`** (`REPLAYS.BIN`). The first 54 entries correspond to national flags; the subsequent 24 must be preserved.
- `BIN/DAT2D.BIN;1` (LBA 5300) stores 54 national CLUTs, 16 BGR555 colors / 32 bytes each, starting at resource offset **`0xE420`**, corresponding to physical `0xBF3B38` in the original raw CD image. The GPU CLUT command list starts at file offset **`0xF220`** and national palette commands are **155–208**. Flag index 0 uses VRAM (0,505), then 16-word-wide CLUT cells proceed along rows to index 53.

**v0.9.4 defect:** palette indices **1,2,4,18,20,23,25,26,27,28,31,40,43,44,50,52** have overwritten transparency color 0. These are reversed flag indices, NOT name indexes.

## Exact 17 modified name slots and new flag styles

| Name slot | Old | New | Flag index | Template old→v0.9.4 |
|---:|---|---|---:|---|
| 2 | UAE | QATAR (short QAT) | 51 | 22→60 |
| 4 | CHINA | UZBEK | 49 | 24→59 |
| 10 | CHILE | PANAMA | 43 | 8→58 |
| 11 | PERU | ECUADOR | 42 | 20→57 |
| 14 | JAMAICA | CANADA | 39 | 2→56 |
| 18 | CAMEROON | SENEGAL | 35 | 0→0 |
| 23 | RUSSIA | BOSNIA | 30 | 7→55 |
| 26 | GREECE | N.ZEAL | 27 | 12→54 |
| 27 | BULGARIA | IRAQ | 26 | 7→53 |
| 28 | ROMANIA | JORDAN | 25 | 0→52 |
| 29 | YUGOSLAVIA | CURACAO | 24 | 7→37 |
| 31 | SLOVENIA | HAITI | 22 | 11→35 |
| 34 | SLOVAKIA | DR CONGO | 19 | 10→24 |
| 36 | FINLAND | GHANA | 17 | 9→20 |
| 50 | WALES | I.COAST | 3 | 3→43 |
| 52 | NORTHERN IRELAND | ALGERIA | 1 | 1→3 |
| 53 | IRELAND | C.VERDE | 0 | 0→1 |

See also `v094_17_replacements.csv` for the full mapping.

## Verified resource command lists and decoding

- `DATSEL`: 57 decoded 4bpp graphic uploads across four header lists (two previously omitted).
- `DATSEL2`: 23; `DATSEL3`: 22; `EDT_2D`: 14; `EDTR_2D`: 35.
- `DAT2D`: 21 compressed texture uploads and 267 palette commands; `DAT2D_E/F/G`: 14 compressed uploads each.
- **214/214** core graphics uploads decode with the validated WE format.
- Across **34** `GDC_*.BIN` stadium resources, **1,026/1,032** graphics uploads decode; **1,307** additional palette commands were identified. Six special-case uploads remain unresolved.

## What remains to verify

All 54 CLUT cells, their physical addresses, style IDs, team labels and resource upload rectangles are mapped. However, the exact **per-style sprite UV rectangles for the three sizes** (64×28, 24×16, 24×8) have **not** been established for all teams. A compressed GPU upload rectangle holds many sprites; it is not a single flag. Likewise only two literal text banks have been positively identified; exact rendering across selection, Edit Mode, formation, match HUD, stadium, replay and ending screens still needs runtime confirmation.

**Do not release v0.9.5 until flag artwork, palette/template coupling and in-game render pass.** World map highlighting is intentionally out of scope.
