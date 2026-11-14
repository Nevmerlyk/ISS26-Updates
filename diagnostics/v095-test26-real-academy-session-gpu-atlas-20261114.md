# ISS26 v0.9.5 — Test26 real Academy session source audit, 2026-11-14

Status: **real session evidence analyzed; NO corrected game patch**. 
Input is the owner's uploaded read-only `20261114_154539_315b0c_Test26_Unified.json`
and `20261114_154539_315b0c_Test26_AuditManifest.json`,
produced by local analyzer commit `874adfafde2f47433e379937355efcfefb8defe9`.
The manifest records ZIP SHA-256 `611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`.
**The original ZIP bytes were not independently inspected here**: local Python/container access was unavailable. Results below are derived from the supplied report only.

## CONFIRMED: Test26 zero-mask audit, owner report 2026-11-14 16:57:35 UTC

Owner supplied fresh Compact, Unified and AuditManifest from `analyzer commit
60b22eaae21d8a738455e4a4695c1447ed981ef6` with feature
`zero-mask-audit-v1`. Same input original Academy session
`20261114_154539_315b0c.zip` SHA256
`611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`.
14 VRAM snapshots, 8 decoded GPDs; report says no BIN/CUE or patch changed.
The owner's *original ZIP bytes were not opened in this environment*; the
numbers below are from their newly generated report, not independently
reconstructed pixel analysis.

**Bosnia away stage `(560,28)` against atlas style55 `(816,368)` at
captured frames 5468..7748:**

| Metric | Value |
| --- | ---: |
| Block size | 16 VRAM words x 28 rows = 64 x 28 pixels, 448 words |
| Equal nonzero 16-bit words | **256** (all stage-nonzero words) |
| Nonzero atlas words absent from stage | **192** |
| Introduced/mutated nonzero words | **0 / 0** |
| Palette indices 1..15 erased (nibble samples) | **384** |
| Suppressed pixel-index bounding box x0..62, y16..27 | **[0,16,62,27]** |
| All suppressed word counts in rows 0..15 | **0** |
| All suppressed word counts in each row 16..27 | **16** |
| Stage is zero-masked source / stage equals source | **true / false** |

**This is a full-width 12-row rectangular blanking**, not sporadic noise or
a style offset. Every one of the bottom twelve 64-pixel rows is zero in
the stage; the atlas has 384 nonzero 4bpp index values in that rectangle,
out of 768 pixel-index positions. A zero palette **index** can be transparent,
but the report does not decode the exact selected CLUT. "384 missing
nonzero indices" is NOT automatically equal to 384 visible-color pixels.

- **Cape Verde home** `(560,0)` equals atlas style1 exactly:
  128 stage and source nonzero words, retained 128, suppressed/introduced/
  mutated 0; zero-mask is false and stage_equals_source true.
  **The Cape Verde art can still be graphically wrong in the atlas**;
  transfer equality does not verify national flag design.
- The earlier frames 3464..4534 show a **different phase**: away stage
  vs style22 has 409 equal nonzero words, 39 changed, 0 suppressed.
- Source55 attribution is established by byte-level content but **neither
  its artwork correctness nor its suitability as a newly allocated
  national style is proven**. Style55 was previously unreferenced; using
  unreferenced atlas cells is not equivalent to empty/safe artwork.

**Draw-time correlation**: live GPU traces use home CLUT (0,505), away CLUT
(224,506). An away flag 64x28 sprite explicitly samples UV y28..55, which
covers the 12 blank bottom rows in stage y44..55. 0x2C strip polygons sample
that same vertical range, and in later captures 40 quads per team use the
home/away stage buffers. These are verified **texture read dependencies**,
not operator-verified spectator/carrying scene labels. It makes the crop
a plausible rendered defect. Restoring bottom rows globally without knowing
the source art, alpha index, MIPS copy dimensions or CLUT is unsafe.

### Engineering decision: no further reruns of the same Test26 JSON

The read-only Test26 investigation of the mask **is complete**. The next
operation must shift to resolving the **final staging writer / actual graphic
resources / palette**, not making the owner rerun identical Academy ZIP
audits. Capture or instrument the data loading transition **4534→5468**
for final-writer GP0 and MIPS parameters; no existing GPD spans that transition.

**Test27 acceptance gates**:

1. Verify that style55 (and style1) atlas art and CLUT decode to the
   *correct* 64x28 Bosnia and Cape Verde flags. If not, replace a safe
   national-specific resource and mapping; do not change club slot54/style10.
2. Find the effective `(560,28)` texture-stage transfer (who and why only
   top 16 rows, and whether bottom 12 are intentionally clipped).
3. Determine whether spectator waving flags use the same texture input or
   a distinct stadium resource, with visually authenticated screen phase.
4. Build and test a **standalone clean-original multi-track-EU** patch,
   preserving 54+4 national slots and 24 clubs; test selection, stadium,
   carried cloth, crowd, club badges and names before stable promotion.

Do **not** claim that copying the atlas's missing lower 12 rows alone fixes
Bosnia, since the atlas cell itself may contain unrelated pixels.
Stable game channel remains v0.9.4, not promoted.

---

## UPDATED after owner reran Test26 on the SAME archived session (2026-11-14)

The owner uploaded the new `20261114_154539_315b0c_Test26_Compact.json`,
`20261114_154539_315b0c_Test26_Unified.json` and audit manifest,
now generated using **analyzer commit `d0187df9ffaf161bee3d9c2ed2627a9b37c39ba8`**.
Manifest confirms same source ZIP hash `611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`,
14/14 VRAM and 8/8 live GPU traces, and **no BIN/CUE/patch modifications**.

**CORRECTION TO EARLIER SHA-ONLY INTERPRETATION: Bosnia style55 IS a close
match to the away stage content.** From frame **5468** onward, **all 256/256
nonzero 16-bit words** in away stage `(560,28)` are exactly equal to style55
at `(816,368)` at offset **(0,0)**. Source stage block is 16×28 = **448
words**. Another **192 words are zero in staging**. The full 896-byte
stage/style55 SHA hashes differ, so at least one position which is zero in
staging differs from the source. The number of suppressed source words may be
1 to 192; **this report does not yet count them**. This evidence supports a
**zero-masked/cleared subset of style55** over a changed or unrelated source,
but cannot prove which GPU transfer or game file is responsible for zeroing,
nor whether those zeros are incorrect in the rendered design.

- Cape Verde home stage exactly equals style1 SHA; also its 128/128 nonzero
  words match at offset (0,0).
- Frames **3464–4534**: home equals style23, all 448/448 stage nonzero
  words match; away compares **409/448 nonzero words** to style22 at offset
  (0,0), or **91.29%**, with 39 source differences in stage-active words.
  This is a separate earlier staging phase, not Bosnia source55 evidence.
- From frames **5468–7748**, near-matches and exact mismatches stay unchanged
  across all later capture points. All operator visual phases remain **unknown**.

### Updated research gate — stage zeros rather than alternate art

A newer read-only Test26 analyzer in this same branch computes an
`aligned_mask_audit` for home style1, away style22 and away style55,
including nonzero words *suppressed to zero* in final stage, affected rows,
4bpp nonzero-pixel count and bounding box. The compact JSON reports these
without raw pixel artwork. **The new diagnostic does not identify a writer**.

Reanalyze the owner's *existing* Test26 ZIP with the newly pinned Windows
runner; do **not** run another gameplay match. Use the resulting
`reference_mask_audits.away_style55` to determine whether the zeros are
localized at the edges (possible intentional clipping/transparency) or erase
flag-colored pixels inside the graphic. Then test the CLUT and draw geometry
before modifying style55 on disc. The original ZIP was not available in this
investigation, so new pixel-loss metrics cannot be derived from the uploaded
JSON alone.

The pre-update SHA-only notes further below are historic. Their claim of
"no matching style" refers strictly to **whole-tile hash equality** and
must not be read as evidence that Bosnia came from a different image.
No corrected game patch was built or promoted; stable game v0.9.4 is unchanged.

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
- At frame 5468 and throughout subsequent captures, home staging exactly matches **Cape Verde style1**, whose atlas cell is at VRAM word `(848,256)`. The away staging **has no whole-tile SHA equality** (but its 256 nonzero words all match style55; see correction above), even though style55 at `(816,368)` is populated and has changed.
- The away staging whole-tile SHA mismatch is now narrowed by nonzero-word comparison: it is consistent with zero-mask/clearing of style55, without a shift. An exact SHA mismatch alone did **not** distinguish these cases.

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
