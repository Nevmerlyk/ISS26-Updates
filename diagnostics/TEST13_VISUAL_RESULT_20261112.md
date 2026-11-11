# Test13 visual result — large flags and Cabo Verde spacing (2026-11-12)

## Evidence and scope

Two operator-provided screenshots were submitted immediately after **Test13** was assigned to the `Test Game` feed. The screenshots show a mobile PS1 emulator with virtual controller overlay, and **do not contain a visible patch-version indicator**. Treat Test13 attribution as **contextual / pending independent launcher-version confirmation**, not cryptographically proven by screenshots.

Observed match: **Cabo Verde vs Bosnia**, **Key Square Stadium**. Screenshots correspond to (a) stadium introduction with team names and large emblems, (b) footballers carrying ceremonial cloth banners on the pitch.

## Actual screenshot observations

| Region | Observed | Expected |
| --- | --- | --- |
| Left national title | `Cabo` and `Verde` appear far apart, with a large blank horizontal gap | `Cape Verde`, normal word spacing |
| Left prematch large emblem | Narrow dark/red/white stripes instead of the Cape Verde flag | Correct Cape Verde design |
| Right prematch large emblem | Multicolored oval/confetti texture, **not** Bosnia's national flag | Correct Bosnia and Herzegovina flag |
| Carried cloth/banner, center | Broken band / black-white geometric strip | Correct national flag artwork |
| Carried cloth/banner, foreground | Distinctive multicolored oval/confetti pattern, analogous to prematch Bosnia artifact | Correct national flag artwork |
| Stadium | Key Square Stadium label and background apparently render normally | Unchanged |

The fabric artifacts are **physically carried banners, not pitch markings**. Small selection icons, spectator flags, match HUD, and alternative stadiums are **not assessed** by these two screenshots.

## Validated patch structure and static source inventory

Test13 release asset `ISS26_0.9.5_LargeFlagSource_TEST13.iss26p` SHA-256:
`159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214`.

Test13 removed only LBAs **6089–6090** (ISO `/BIN/DATSEL.BIN`) and **6256–6257** (ISO `/BIN/DATSEL3.BIN`) relative to Test12, retaining **1,492** sector records. A read-only ISO9660 directory walk on the owner-supplied original EU Track01 plus the verified Test13 sector list shows that other modified records **remain** in national graphic resources:

- `/BIN/DATSEL.BIN`: **47** modified sector records (after the two-sector rollback)
- `/BIN/DATSEL2.BIN`: **18**
- `/BIN/DATSEL3.BIN`: **25** (after the other two-sector rollback)
- `/BIN/DAT2D.BIN`: **2**
- `/BIN/T_NAME_E/F/G.BIN`: **84** total modified sectors (28 each)

These are **file attribution counts only**; none establishes the exact GPU texture writer, palette, or draw primitive responsible for either displayed flag. Multiple modified files are expected for a broad seasonal patch.

Test11 already removed 63 stadium-GDC sector edits while the large banner defect persisted, so neither rollback by itself identifies the source.

## Engineering decision / next evidence gate

**Result: VISUAL REGRESSION — DO NOT PROMOTE Test13 TO STABLE.**

1. Capture raw VRAM + GPU draw trace at `prematch_banner` and `carried_banner` with a fresh PS1 boot (no prior VRAM snapshot). Record exact `tpage`, `UV`, and `CLUT` of each banner primitive, plus the last GPU upload writer and game resource. Without this evidence, claims such as “both use one DATSEL sprite” remain unproven.
2. Compare with **Denmark** in the same two phases to separate generic stadium render corruption from newly mapped national slots.
3. Fix the `Cabo  Verde` -> `Cape Verde` label and layout as a separately auditable name-atlas change; do not conflate it with the flags.
4. Only then build and publish an isolated **Test14** candidate against the clean European Track01; validate sector hashes and Mode2 EDC/ECC. Keep `stable/latest.json` at v0.9.4; do not promote by screenshot alone.

No game BIN/CUE, screenshot files, BIOS or CD audio are added to this report.
