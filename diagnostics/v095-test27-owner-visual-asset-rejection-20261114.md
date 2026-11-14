# ISS26 Test27 — owner-verified visual evidence: both national flag sources are incorrect

**Date:** 2026-11-14. **Status:** first direct visual inspection of the owner's real
Test27 source/CLUT PNGs; **no playable patch built or published**.

## Exact evidence provenance

The owner uploaded `test27_real_flag_pixels.json` and 11 PNG previews
(`bosnia_source_clut.png`, `bosnia_stage_clut.png`,
`cape_verde_source_clut.png`, `cape_verde_stage_clut.png`, etc.), produced
by the already existing read-only Test27 exporter on the **original
Academy Test26 ZIP**. This note records visual inspection of the received
screenshots and the machine-readable owner JSON; the underlying ZIP has
not been re-opened by the model execution container.

- Original Academy ZIP SHA256:
  `611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690`.
- Snapshot: `rookie_exam_transition_00005468.vram`.
- Original full VRAM SHA256:
  `8F3403B2DFE1AC5699A130A90151FA95377FB8BAEF44EFABAA67A613BF9B778B`.
- All textures are **64×28 = 1792 palette indices**, packed as 4bpp.
- The report explicitly marks `visual_ownership_proven=false`:
  the GPU is known to sample staging cells, but the relationship to
  distinct spectator/carrying flag primitives is still unresolved.

## Quantitative result from actual owner JSON

| Evidence | Cape Verde | Bosnia |
| --- | --- | --- |
| Atlas style | **1**, VRAM words (848,256) | **55**, VRAM words (816,368) |
| Final stage | (560,0) | (560,28) |
| Live CLUT position | (0,505) | (224,506) |
| Atlas-source equals final-stage SHA | **Yes** | **No** |
| Equal pixel indices | **1792/1792** | **1408/1792** |
| Nonzero source indices lost to stage zero | **0** | **384** |
| Mutated/introduced nonzero indices | 0/0 | 0/0 |
| Lost rows | none | every row **16..27**, 32 nonzero indices per row |

**Different palette locations, same CLUT contents**: both actual CLUT
SHA256 equal
`DA3484BF49560D2CD1306FE3CCC59B5417A54AA370859DDB6C77EAE523361B88`.

This only proves *identical 16-entry BGR555 palettes at these sampled
addresses and frame*. It does **not** automatically mean the palette is
incorrectly shared — a joint 16-color palette could, in principle, cover
the four/five colors required by both flags. It also cannot by itself
establish transparency or the national-flag design.

## Human visual review of the owner's actual images

- **Cape Verde `cape_verde_source_clut.png`:** observed a very dark field, white/light horizontal bars, a dark
  middle bar and a ring of small red/dark points. The green/red panel is
  the **index-difference visualization**, not the rendered artwork. The
  source has some intended Cape Verde flag geometry but wrong displayed
  colors; a palette/index assignment defect is plausible. Since the stage
  is a pixel-perfect copy, changing copy height cannot repair that image.
  The exact CLUT remapping has not been validated.
- **Bosnia `bosnia_source_clut.png`:** observed red heraldic/crest
  graphics with decorative shapes, **not** Bosnia & Herzegovina's
  blue field, yellow triangle and diagonal white stars. This defect
  exists already in the atlas tile *before* stage clipping.
- **Bosnia `bosnia_stage_clut.png`:** the lower twelve rows are
  black (palette-index zero under the sampled CLUT). The
  `bosnia_stage_zero_marked.png` makes these rows magenta as a
  **diagnostic overlay**; magenta is **not** an actual in-game flag
  color. Each bottom source row loses 32 nonzero 4-bit indices.
- The full comparison sheet confirms both defects but does not
  independently establish which game's ISO file or MIPS instruction
  populated those atlas positions. Color choice is based on the
  sampled CLUT; 4bpp silhouette/geometry is not repairable by color
  remapping alone.

**Conclusion (corrected review):** There are **two independent categories of defect**:
(1) incorrect or misassigned national artwork/CLUT and
(2) a Bosnia-only 12-row staging loss. Previous theories that copying
the missing bottom 12 rows from unused style55 would fully fix the game
are now **ruled out by direct observation**.

## Engineering correction for Test27

1. Source **correct, isolated national-only** 64×28 4bpp art for
   Cape Verde and Bosnia, with a validated national CLUT. The
   separate candidate creator `tools/test27_flag_art_4bpp.py` already
   generates assets but **has not been injected or visually accepted
   in the actual game**.
2. Resolve **per-national-stage mapping** and actual last atlas writer.
   Clean-disc source overlap is documented across DATSEL/DATSEL3 and
   34 GDC resources, including GDC_BN exception. Style55 was
   *unreferenced by original five style tables but is NOT empty*;
   don't overwrite its pixels globally. Keep club54/style10 isolated.
3. Find where Bosnia's bottom 12 rows were discarded
   (MoveImage height16, StoreImage/LoadImage, or later overwrite),
   then correct the **verified callsite**, not an assumed source.
4. Confirm selection, HUD, stadium prematch banner,
   physically carried banners, **waving spectator flags**, flags and
   names. The 54+4 nations, 24 clubs, unchanged Tracks02..12 and
   Mode2 EDC/ECC integrity are mandatory.
5. Only after verified source/mapping and runtime fix build one
   self-contained `ISS26X01` from **clean original**,
   then visual-test Cape Verde–Bosnia and unrelated team/club cases
   before promoting game v0.9.5.

## Artifact safety

The eleven user-uploaded PNGs and original raw game assets are **not**
committed to GitHub in this report. The new
`tools/test27_validate_owner_flag_report.py` verifies numerical
frame, location, CLUT hash and 12-row-mask consistency in metadata
without copying imagery; it **does not infer visually correct artwork**.

**No real game patch or changed game feed was produced.**
The game stable channel remains 0.9.4, the test channel remains
`0.9.5-largeflag-source-test13`.
