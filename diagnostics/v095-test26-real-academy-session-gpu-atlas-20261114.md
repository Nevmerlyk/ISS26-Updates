# ISS26 v0.9.5 — Test26 real Academy session source audit, 2026-11-14

Status: **real session evidence analyzed; NO corrected game patch**. 
Input is the owner's uploaded read-only `20261114_154539_315b0c_Test26_Unified.json`
and `20261114_154539_315b0c_Test26_AuditManifest.json`,
produced by local analyzer commit `874adfafde2f47433e379937355efcfefb8defe9`.
The manifest records ZIP SHA-256 `611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`.
**The original ZIP bytes were not independently inspected here**: local Python/container access was unavailable. Results below are derived from the supplied report only.

## Sample integrity and evidence limits

- 14 × 2,097,152-byte VRAM snapshots, 14 screenshot file *names* inventoried, 8 GPU dumps with `TraceBegin=true` decoded.
- **All 14 snapshots and 8 GPDs show `operator_phase=unknown`**. The AutoCapture filenames identify *task intent*, NOT a visually verified scene. No `verified_gpu_draw_ownership` is true.
- The gameplay screenshots previously provided separately show damaged Bosnia selection flag and damaged prematch player-carried banners, but their frame indices were not tied to the archived .screen.raw members.

## Atlas and staging transitions

| Frame range | Atlas 72-style changes | National CLUT changes | Home stage changed? | Away stage changed? |
| --- | ---: | ---: | --- | --- |
| 2394 → 2574 → 3037 | 0 | 0 | No | No |
| 3037 → 3464 | **72** | **25** | No | No |
| 3464 → 3556 → 4534 | 0 | 0 | No | No |
| 4534 → 5468 | **52**, including style55 | **32** | **Yes** | **Yes** |
| 5468 → 5508 → 5706 → 5904 → 6966 → 7146 → 7650 → 7748 | **0** | **0** | No | No |

Key observations from the uploaded hashes:

- Styles 0..71 were byte-zero in frames 2394/2574/3037 and populated by frame 3464. This is a **scene/load transition**, not evidence all flags were blank on screen.
- From frame 3464 to frame 4534, home staging `(560,0)` exactly matches style23. Away staging `(560,28)` **matches no style 0..71**.
- At frame 5468 and throughout subsequent captures, home staging exactly matches **Cape Verde style1**, whose atlas cell is at VRAM word `(848,256)`. The away staging still **matches no style**, even though style55 at `(816,368)` is populated and has changed.
- The away staging mismatch is one of the strongest Test25 clues. It can mean shifted, assembled, repainted or overwritten pixels, or a different upload source. An exact SHA mismatch alone does **not** distinguish them.

## What the GPU actually sampled (after TraceBegin)

Coordinates below are VRAM **16-bit words** (not 4bpp screen pixels). CLUT values are VRAM coordinates of PS1 palettes.

| GPD filename frame | Textured primitives | Draw candidates reading (560,0..55) | Live CPU->VRAM uploads | Live VRAM->VRAM moves |
| ---: | ---: | ---: | ---: | ---: |
| `carried_banner_2394` | **0** | 0 | **20** | 0 |
| `carried_banner_2574` | **0** | 0 | **20** | 0 |
| `crowd_flags_5508` | 1360 | **36** | 1 | 2 |
| `crowd_flags_5706` | 681 | **18** | 0 | 1 |
| `crowd_flags_5904` | 681 | **18** | 0 | 1 |
| `hud_6966` | 1540 | **96** | 0 | 1 |
| `prematch_banner_7146` | 1771 | **80** | 0 | 1 |
| `hud_7650` | 593 | 0 | 0 | 1 |

More specific commands:

- `crowd_flags_5508` has per live frame **16 GP0(2Ch) textured polygon samples** from away flag staging rows y=28..55, X words 560..575, CLUT **(224,506)**. It also has one GP0(64h) 64×28 sprite for away `(560,28)` / CLUT `(224,506)` and one for home `(560,0)` / CLUT `(0,505)`. Two live frames contribute 36 staging-source candidates. The 5706 and 5904 GPDs show 16 such away strips plus both sprites in one live frame each.
- `hud_6966` contains **40 GP0(3Ch) quads from home staging** with CLUT `(0,505)`, **40 quads from away staging** with CLUT `(224,506)`, and 16 away-strip GP0(2Ch) samples. `prematch_banner_7146` contains **40 GP0(3Ch) quads from each** home and away staging. Their source regions are the same 16×28-word buffers as the big flags.
- The task-labelled carried-banner GPDs at 2394/2574 show **zero live textured draws** and twenty 24×192-word upload strips each. These are not evidence of rendered carried cloth. The auto task appears to have captured a GPU upload interval rather than the right active draw interval.
- The live `vram_to_vram` operations reported for crowd/HUD/prematch are tiny `(0,0) → (0,0), 2×1` copies; they do not identify the last upload into `(560,28)`. VRAM stage and atlas were already stable before the first of these GPDs.

**Interpretation:** confirmed GPU dependence on the same pre-match home/away staging buffers across several AutoCapture scene intentions, and multiple distinct polygon layouts (strips and 40 quads per team). This makes a common *texture input* plausible for big cloth effects, and suggests geometry-based animation may occur. **It is NOT proof that the spectator-waved flags are those polygons**, because the archive contains no operator-verified screenshot-to-draw ownership. The crowd may additionally use separate textures.

## Engineering decision and next gate

1. **Target the 4534→5468 source transition**, not another arbitrary match. Instrument GP0 CPU uploads, VRAM copy and CD/DVD resource decompression in the interval; identify the final writer of away stage (560,28) before polygons first sample it. Track the source names (DATSEL, DATSEL3, GDC and any crowd-specific resource) without assuming they share assets.
2. After the new analyzer's partial-matching upgrade, rerun the **existing local original ZIP** with tools/Run-ISS26-Test26-ArchiveAudit.cmd; its new compact summary will report whether the away staging is a shifted or partially overwritten style55 (or another style). Preserve source VRAM/CLUT; no speculative pixel changes.
3. For true spectator flags, link .screen.raw frame to draw packets or provide a verified frame label. The source-only archive names currently cannot establish that the flags in the crowd are the same as the large banners.
4. Once the last writer is known, patch the **source graphics and mappings together**, protect club badge collision slot54/style10, 54+4 national slots and 24 clubs, then validate all large selection/stadium/carried/crowd/club cases on a clean EU original.
5. Keep **Play Game stable v0.9.4**, Test25 research-only. No v0.9.5 release until all visuals pass.

Test26 analyzer's next code change is `ranked_partial_style_sources`, searching each 16×28-word stage tile against 72 styles with XY offsets up to ±2 words/rows and excluding zero words. This produces candidate scores, not a causal proof. A short `--summary-output` JSON is now available for the next local run.

**Bottom line:** enough evidence exists to narrow the next fix to the **away staging producer and common large-banner draw path**. The actual spectator-flag asset and final disc writer remain unverified.
