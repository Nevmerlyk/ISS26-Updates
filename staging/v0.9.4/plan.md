# ISS26 v0.9.4 — national flags regression work (NOT a release)

## Verified starting point

- Public game patch feed currently points to **0.9.3-preview**.
- v0.9.3 is a **clean-original**, 1412-sector independent XOR patch, with only file-level verification reported. In-game correctness is not established.
- User screenshots showed incorrect/missing flags in the team-selection screen: **Curaçao, DR Congo, Cabo Verde, Algeria, Bosnia**. Do **not** assume a specific screenshot is from the v0.9.3 patched CUE until its installed version is known.
- Team highlight/map is independently outdated (Bosnia highlights the old Russian area) and is **not** in the flag-fix scope.
- The old national flag gate in private ISS26-Android source rejects style indices above 43, whereas v0.9.3 documents atlas blocks 52–60. Gate semantics need to be reconciled with actual atlas bounds rather than blindly raising the maximum.

## Read-only differential audit (performed on published release assets)

Run `tools/compare_preview_patches.py` from this repo. The GitHub Action
`Audit v0.9.3 national flag patch regression` stores a report artifact.

Validated comparison from 0.9.2-preview to 0.9.3-preview:

- **1326** output CD sectors have changed bytes between revisions.
- **2,757,356** output bytes differ.
- This is not evidence of corruption by itself: whole-resource repacking and index moves can cause large differences even for small graphics changes. **Avoid relying solely on changed-sector count to assert quality.**

## v0.9.4 candidate scope (do not activate prematurely)

1. Determine exact 4bpp flag atlas + CLUT location for all **17 newly mapped nations**, taking account of the actual compiled DATSEL2/DATSEL3, EDT_2D/EDTR_2D and GDC resource layout, atlas capacity, offsets and size tables.
2. Verify each flag's **bitmap, orientation, palette, transparency and team slot-to-style mapping** independently. Do not reuse overlapping atlas regions between different flags.
3. Confirm **all 37 other national flag slots** retain their images and style pointers and **all 24 club slots** retain existing art and team information.
4. Verify team names in both relevant banks; investigate 'C.VERDE', 'CURACAO', 'DR CONGO', 'ALGERIA', 'BOSNIA'.
5. Preserve national rosters, club graphics, CD-Audio, world map and the rest of the ISO unchanged outside necessary container/offset alignment updates.
6. Recalculate and verify Mode2 Form1 EDC/ECC and all modified image resource / directory length fields; apply independent patch from clean original, SHA-256 verify the complete output.
7. Visually test in the integrated ISS26 emulator: team-select grid, large flag/card, Edit Mode, match HUD, kits and stadium menus. Confirm names and flags match the selected team. Do not call this stable without visual validation.
8. Publish v0.9.4 **only after** the clean-original test patch and expected output hash exist and are verified. Update public `latest.json` last.

## What is NOT fixed here

- Historical world map / old USSR or Russia highlight geometry.
- Incorrect large club crests.
- 2026/27 player rosters and attributes.
- Missing CD-Audio music and keyboard mapping.

These are separate development streams. Original 12-track BIN/CUE must remain unchanged.
