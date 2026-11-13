# ISS26 game patch v0.9.5 — Test13 source-atlas correlation (read-only)

**Status:** direct clean-original/Academy archive analysis PASSED on 2026-11-14.
**Not a game patch.** Stable game patch, original BIN/CUE and Windows Academy feed are untouched.

## Input checks

- User-owned original European Track01 SHA-256:
  `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
- Test Game session `20261113_233425_e379df`, Cape Verde (home) versus Bosnia (away), with 12 read-only VRAM/screen/GPU captures.
- The 4bpp at atlas word coordinates `(848,256)` and `(864,312)` matches the GPU staging cells `(560,0)` and `(560,28)` **in all twelve frames**.
- The first local RAM upload trace at `0x800CC600` contained French UI-help text, so this address cannot be claimed as the actual flag source in that phase.

## Verified decompression and resource overlaps

A working read-only reimplementation of the original PS1 GPU LZ decoder successfully decoded:

- **55/55** compressed `BIN/DATSEL.BIN` GPU uploads.
- **22/22** compressed `BIN/DATSEL3.BIN` GPU uploads.
- **34** stadium `GDC_*.BIN` source resources.
- The first **16** corresponding DATSEL/DATSEL3 pairs have byte-identical decoded pixels and identical VRAM rectangles in the clean disc.

The two observed bad 64×28 4bpp tiles have these *potential* disc content mappings:

| Captured stage atlas | Clean disc source | Duplicate clean source | First 896-byte tile SHA-256 prefix | Test13 VRAM SHA-256 prefix | Byte differences |
|---|---|---|---|---|---|
| `(848,256)` Cape Verde candidate | `DATSEL3` upload index **4**, compressed offset **11088** | `DATSEL` index **43** | `5CAB263C7BCD17E0D8B0` | `AE9E179ED66CA388C634` | **816/896** |
| `(864,312)` Bosnia candidate | `DATSEL3` upload index **5**, compressed offset **12464** | `DATSEL` index **44** | `16E0EA3E42436F4CF0C7` | `DB3662607524B900B96E` | **886/896** |

All **34** stadium GDC files contain a GPU upload overlapping the same two atlas coordinates. **33 of 34** decode to the same original tile bytes as DATSEL3 at these positions; `GDC_BN.BIN` is an exception. Because multiple resources can populate the same VRAM rectangle, this establishes **potential atlas suppliers**, not an actual **last writer**.

## Important interpretation

When decoded using the currently captured CLUT, the clean original 4bpp tiles contain **older emblem/crest artwork**, not the correct 2026 national flags. The Test13 VRAM alternatives depict sparse Cape Verde stripes and a circular Bosnia crest.

**Do NOT overwrite these shared atlas cells globally** with ad-hoc flag pixels. Club resources and other team slots can share style IDs; Test17 already documented Bosnia style-10 conflict with club slot 54. A safe fix needs a per-national-slot style/UV/tpage/CLUT mapping or an independently allocated resource, plus draw-time GPU command evidence.

Do not call the automatically named `crowd_flags` and `carried_banner` captures confirmed scenes: screenshots are stadium header and team lineup respectively.

## Remaining gate before producing a game patch

1. Establish which GPU primitive samples the actual visible faulty flag (UV/tpage/CLUT).
2. Trace the final upload that populated the sampled rectangle, distinguishing DATSEL/DATSEL3 and stadium GDC (capture/trace ordering).
3. Isolate national style-slot routing from the club emblem allocation.
4. Build independent clean-original `ISS26X01` test patch with corrected sector EDC/ECC and exact SHA checks, preserving the 54 regular national slots, 4 bonus, 24 clubs, names, and untouched audio tracks 02–12.
5. Use ONE targeted visual match for acceptance after a candidate fix, not another blind general test.

Local evidence kit `ISS26_v095_Flag_Source_Research_20261114.zip` was produced in the analysis session. Six Python synthetic/integration tests passed on the supplied original and Academy archive. GitHub does not contain the user's original data.

## Draw-time GPU proof from actual PCSX-Redux .gpd packets

Decoded the **live GP0 commands after the dump's TraceBegin marker**, not just its initial VRAM snapshot, according to the PCSX-Redux GPUDUMPv1r1 packet specification.

- `flag_auto_prematch_banner_00005148.gpd` contains **40 textured polygon samples for Cape Verde** and **40 for Bosnia**, with no parser errors.
- In the same trace, both images use 4bpp texture page **(512,0)**. Cape Verde samples the staging area near **(560,0)** with actual draw CLUT **(0,505)**; Bosnia samples near **(560,28)** with CLUT **(224,506)**. Draw primitive opcode is `0x3C` (gouraud textured quad), not a guess inferred from the atlas.
- The live traced spans from all 12 dumps have **zero GPU transfers into (560,0..56)**. Those transfers occurred *before* their trace began. GPU drawing ownership of the staging tile is proven; the final CPU/GPU source writer is not.
- Also confirmed matching source-page/CLUT references in other actual draw phases; phase names are heuristic, not verified ceremonial-flag identity.

Validated read-only Python GPUDUMP decoder and synthetic/source-archive tests: **8/8 passed**. Locally available research kit contains the code, condensed GP0 evidence, original-disc atlas comparison, and an enlarged preview. No game binary is distributed in the documentation.

This is sufficient to narrow the next breakpoint: trace the last 1,792-byte upload/VRAM transfer to staging rectangle `(560,0,16,56)` before the stadium label appears, while sampling `tpage`, UV, CLUT and draw primitive. **Do not globally replace DATSEL3 block 4/5**: clean source contains shared legacy crest graphics, not isolated team flag sprites.
