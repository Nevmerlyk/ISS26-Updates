# v0.9.4 — forensic results from v0.9.3 (8 Nov 2026)

This is a **read-only investigation**, not an installable game patch and not a proof
that the in-game flags render correctly. Keep public \`latest.json\` at
\`0.9.3-preview\` until a fully independent, visually verified v0.9.4 exists.

## Evidence

The user provided a locally generated, hashed v0.9.3 FlagAudit JSON. It confirms:

- 273 ISO9660 file records in both original/patched disc images;
- 49 actually modified ISO files, including 39 graphics resources;
- 0 unreadable resources with the updated Form1/Form2 decoder;
- 11 \`SD/DA\` records past Track 01 on both images, with unchanged locations;
- base SHA-256 \`D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44\`;
- patched SHA-256 \`9AF8F7578321354FCE44E801D619A2F8ECCD2C1D302F488C943B946EB991D8FB\`.

Most visible changes are in \`DATSEL.BIN\`, \`DATSEL2.BIN\`, \`DATSEL3.BIN\`,
\`EDT_2D.BIN\`, \`EDTR_2D.BIN\`, and all 34 \`GDC_*.BIN\` variants.

The **published v0.9.3 XOR patch asset**, verified against the release's SHA-256,
was then analyzed directly by GitHub Actions **without any game image**:

| Measurement | Result |
| --- | ---: |
| Total changed CD sectors in release | 1,412 |
| CD header changes (SYNC, mode, XA duplicated subheader) | 0 |
| Changed Form2 submode bits | 0 |
| Inconsistent duplicated-subheader XOR deltas | 0 |
| Graphics files whose recorded size newly includes Form2 sectors | 38 |
| Additional Form2 sectors included across these files | 93 |
| Additional Form2 sectors not changed by the patch | 0 |
| Additional Form2 sectors with changed EDC field | 93 |
| Additional Form2 sectors with changed payload but unchanged EDC | 0 |

**Corrected interpretation:** v0.9.3 does **not** convert an original
Mode2 Form1 sector into a Form2 sector. The game file sizes are enlarged so
that they include previously existing Form2 sectors, and the patch changes
their payloads and EDC fields. The CD-sector header flags themselves do not change.
Earlier wording that it "converted sectors" was wrong.

This is a plausible packing strategy but a **potential loader-compatibility
risk**: a game loader expecting 2048-byte Form1 data may not reconstruct a
mixed 2048/2324-byte Form1/Form2 file exactly as the ISO inspector does.
\`DATSEL2\` expands from 64 Form1 sectors to 64 Form1 plus 5 Form2,
\`DATSEL3\` from 27 Form1 to 27 Form1 plus 2 Form2. Many stadium files
use the same pattern. No XA payload/subheader correctness claim is made
without reading the user's clean and patched discs.

## Concrete next engineering checks

1. Trace the **game's actual file-loading code** for \`DATSEL2\`, \`DATSEL3\`,
   \`EDT_2D\`, \`EDTR_2D\` and \`GDC\`. Determine whether reads support
   mixed Mode2 Form1/Form2 logical byte lengths or assume 2048-byte sectors.
2. Determine where the 4bpp atlas records and CLUTs live, read styles
   52–60 and cross-check their offsets and lengths with the ISO resource
   data as actually seen by the game loader (not only by the desktop audit).
3. If the loader assumes Form1, **repack into Form1 data sectors** where
   the ISO file layout permits and recalculate Mode2 Form1 EDC/ECC; update
   file size/sector-count references. Avoid conversion blindly.
4. Check all 17 replaced flags and 37 retained flags in team-select, Edit
   Mode and match HUD, plus all 24 club crests. Especially Curaçao,
   DR Congo, Cabo Verde, Algeria, Bosnia.
5. Produce an independent \`ISS26X01\` XOR patch against the **clean
   original Track 01**, verify the full output hash and gameplay, then
   publish v0.9.4 and update \`latest.json\` last.

Do not change player rosters, map highlighting, in-game CD music or controller
bindings as part of this graphics-only fix.

## Reproduction

Run the [sector-header forensics workflow](../../.github/workflows/audit-v094-sector-headers.yml)
or execute \`python tools/audit_patch_sector_headers.py --patch-file
dist/ISS26_0.9.3_preview.iss26p\` after downloading the verified asset.
The CI artifact \`ISS26-v093-Mode2-Header-Forensics\` contains **counts and LBAs
only**, not any game artwork or proprietary bytes.
