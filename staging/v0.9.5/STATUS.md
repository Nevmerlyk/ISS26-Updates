# ISS26 v0.9.5 — national flags and names (in development; NOT released)

## Verified binary correction

Source: the European ISS Pro Evolution 2 clean Track 01 used by the owner,
SHA256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
Source patch: the public independent `v0.9.4-preview` XOR release, not the
previous installation.

**Confirmed defect:** earlier 17-flag palette writes accidentally placed
color 16 into the next nation's transparency entry (index 0, originally
`0x0000`). This corrupted 16 neighboring slots: **1, 2, 4, 18, 20, 23, 25,
26, 27, 28, 31, 40, 43, 44, 50, 52**.

A reproducible generator `tools/build_v095_palette_candidate.py` repairs
those entries without distributing or requiring the source game. Its output
is still an independent patch for a clean original Track 01.

- 16 palette entries corrected
- 2 raw CD sectors touched directly: 5328 and 5329
- affected MODE2 Form1 EDC/ECC recalculated and verified
- independent XOR patch SHA256:
  `CA1910F84EDADB1DCCA3177CEA70F550A6DBDD17173ACBFDB9644F9141ED7404`
- independently reconstructed modified Track01 SHA256:
  `26EC92C768CA0C41795E0B91F7554ADD1E6D2258E03216FCEF23CD2B8F93BA5A`
- Patch is 1412 independent-sector XOR records (3,371,868 bytes).
- CI verifies fixed input/output patch hashes and tests parity math.

**Important: This is NOT a complete flag patch and should NOT be published as
v0.9.5 or used in `latest.json`.** It corrects CLUT storage, not all
artwork/style mapping, 54 team names on every screen or map geometry.

## Further verified problems

- User v0.9.4 screenshot: Bosnia still has a black flag and Russia highlighted.
- Offline decoded v0.9.4 national 4bpp atlases: style 3 (Algeria) resembles
  Pakistan, style 24 (DR Congo) resembles Tanzania; several other new flags
  are incorrect. There are independent sizes 64x28, 24x16 and 24x8.
- Current style 55 (Bosnia) has bitmap data in the offline atlas, but renders
  blank in the actual selection screen. Actual EU PS1 game loader/style
  handling must be confirmed before calling this fixed.
- Senegal slot 35 shares graphic style 0 with **four unchanged countries**
  (slots 7, 8, 11, 34), so repainting style 0 will corrupt those teams.
  Assign Senegal a safe independent bitmap style and verify real rendering.
- One stadium asset (`GDC_FD.BIN`) contains multiple command lists and does
  not conform to a single-list atlas reader. A safe packer must handle that
  form rather than skipping it silently.
- Map highlighting for Bosnia still uses the historical Russia slot.
  Mapping is separate from flag imagery.
- We must preserve all 24 clubs, 37 untouched flags, Track 02–12 audio,
  game controls and existing player data.

## Release gate

Do not advance public `latest.json` until:
1. 54 national slots have correct names in selection, Edit Mode, pre-match
   and in-match screens, with long and abbreviated forms checked;
2. 54 correct large, medium and small flag images render in the actual game,
   including Bosnia, Algeria, DR Congo, Curacao, Cabo Verde and Senegal;
3. Every atlas is repacked without pointer overlap, CD sector growth errors,
   invalid CLUTs or modifications to any club emblems;
4. The independent `.iss26p` applies to a clean European BIN and matches
   expected SHA256, sector EDC/ECC and directory metadata;
5. User gameplay smoke test passes before release is promoted to the
   automatic update channel.

While this work is in progress, `latest.json` must continue to offer the
previous v0.9.4-preview.
