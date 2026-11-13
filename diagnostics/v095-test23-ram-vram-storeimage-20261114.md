# ISS26 v0.9.5 Test23: RAM staging & GPU VRAM-to-CPU readback

**Date:** 2026-11-14. **Status:** read-only analysis; no released game patch.
Related Academy source-preview PR: https://github.com/Nevmerlyk/ISS26-Android/pull/46
Related game correction issue: https://github.com/Nevmerlyk/ISS26-Android/issues/37

## Input and verification

- Clean European PS1 original, Track01 SHA-256:
  `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
- Original `SLES_033.21` SHA-256:
  `868EF5E9B3AE90D689498DC5BAF0C10D8C3D3DCD608D17A4569512259CC7ACB9`.
- Academy Test Game archive `20261113_233425_e379df.zip` for
  Cape Verde vs Bosnia, 12 GPU/VRAM capture frames.
- Offline verified Python suite: **9/9 passed** against those real files,
  including corrupted-VRAM rejection and original MIPS opcode checks.

## Exact staging buffer correlation

| Team | Original RAM after intro | Draw VRAM source | SHA-256 | Match |
| --- | --- | --- | --- | --- |
| Cape Verde | `0x800CC600` +896 | `(560,0)` | `AE9E179ED66CA388C634ACB3587EC1D5369EA083853E00417A14C38EBF91E102` | 896/896 |
| Bosnia | `0x800CC980` +896 | `(560,28)` | `DB3662607524B900B96E9A9A4D6BD8817EAA6BB1478F33AB2492BBA61074344F` | 896/896 |

The frame-2941 snapshot has **French help-menu strings** in the same 1792-byte
range. Later, by frame 3312, the region contains the exact two **bad**
flag sprites. **886/896** Cape bytes and **873/896** Bosnia bytes differ
from the earlier RAM. Both textures remain byte-identical across 12 VRAM
capture frames, with no further full-tile copies elsewhere in main RAM.

The write-watch callback at frame 3093 gave PC `0x8003A140`,
but that address is opcode `0x00001021` = `addu v0,zero,zero`;
it does **not** write memory. This is a CPU-context sample while the GPU
transfer can be in progress, not the decompressor's instruction.

## Verified original SLES GPU-to-CPU readback

Disassembly of the same function containing the reported callback PC:

| PC | Opcode | Meaning |
|---|---|---|
| `0x8003A040` | `3C02C000` | Load GPU GP0 command C0 |
| `0x8003A044` | `AC620000` | Issue command to GPU data port |
| `0x8003A0E0` | `8C420000` | Read GPU data port |
| `0x8003A0E8` | `AE420000` | Store word through RAM destination |
| `0x8003A140` | `00001021` | Non-store return value |

GP0 C0 means **copy rectangle from VRAM to CPU**. Alternate DMA setup
occurs later in the same function. Thus the observed breakpoint's PC is
explained by a **GPU readback path**; final disc-source/decompressor
selection remains unresolved. Do not patch `0x8003A140`.

## Fixed Academy Test23 instrumentation

Previously advertised execution breakpoints at `0x80092F38` and
`0x8009310C` hit argument setup, **32 bytes before** actual graphics
calls. Clean original `SELECT.BIN` proves:

| Old probe opcode | True call opcode |
|---|---|
| `0x80092F38: 3C05800C` (LUI) | `0x80092F58: 0C00E1FB` (JAL `0x800387EC`) |
| `0x8009310C: 3C05800C` (LUI) | `0x8009312C: 0C00E1E3` (JAL `0x8003878C`) |

Academy source PR #46 now moves both breakpoints to actual calls and
adds 15-frame RAM-content polling, a 60-transition log and at most 12
extra local 1792-byte snapshots within the original 20-snapshot budget.
This is **source-only**, not installed stable Academy.

## Next game correction gate

Identify the original source **VRAM atlas tile** and per-national-slot
resource/style routing *before* readback. DATSEL, DATSEL3 and stadium GDC
uploads overlap shared graphics; overwriting a common 4bpp tile could
damage club emblems. Only then build a full clean-original standalone
`ISS26X01` patch, confirm EDC/ECC and visually test once. Do not
advance stable/test feeds before patch verification.

The user's original BIN/CUE, tracks 02–12, installed Academy 0.9.5
and game patch feeds were not modified.
