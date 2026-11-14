# ISS26 v0.9.5 — Test26 unified national flag source audit

**Status:** source-only diagnostic branch. No Test26 game patch, no changes to stable/test feeds.

Owner request: correct **all big national flags and the flags waved by spectators together**, without disturbing club crests. The latest Test25 visual test proves a black Bosnia selection flag, incorrect Cape Verde/Bosnia stadium graphics and corrupt player-carried fabric; it reaches kickoff. The same screenshots do **not** prove the source of waving crowd flags.

## Four visual surfaces and evidence gates

| Surface | What is known | What remains |
| --- | --- | --- |
| Team selection | Bosnia still black in Test25 | Proper texture/CLUT and selected team slot |
| Stadium introduction | Cape Verde large flag striped/black; Bosnia mosaic | Real atlas writer and draw UV/tpage/CLUT |
| Player-carried ceremonial fabric | Distinct carried flags are visibly scrambled, not grass decals | Rendered polygon and source/animation frame |
| Waving spectator flags | Seen in prior gameplay, but no proven source in Test25 | Screenshot + two distinct animated frames + GP0 draw packets |

The flag types may share images or use different resources. Do not overwrite shared styles without isolating the nation and club slots.

## Implemented in the Test26 branch

- New read-only Python tool: tools/analyze_flag_test26_unified.py
- Synthetic regressions: tools/tests/test_analyze_flag_test26_unified.py and tools/tests/test_parse_v095_gpudump.py
- Reads an Academy ZIP and emits hashes, VRAM coordinates, scene-label coverage and changes between captures, without exporting images, game graphics or RAM.
- Scans **all 72 style cells** across the two separate 4x9 atlases. The existing Test12 analyzer only scanned styles 0–27.
- Verified original selector layout: atlasX=(style<36?832:768)+16*(style%4), atlasY=256+28*((style%36)//4).
- Reference cells: Cape Verde style1 (848,256); old Bosnia style10 (864,312); Test25 Bosnia style55 (816,368).
- Samples 64x28 4bpp flags as 16x28 VRAM words, both pre-match staging rectangles (560,0) / (560,28), and 16-color CLUT candidate rows (0,505) / (224,506), plus 54 nation palettes.
- Only considers a phase confirmed by an explicit operator tag or supplied phase manifest. A time-sampled event called crowd_flags is *not* proof of a spectator flag scene.
- Decodes live .gpd packets after TraceBegin with tools/parse_v095_gpudump.py, enumerating textured polygon UV/tpage/CLUT, sample source coordinates, MoveImage and CPU-to-VRAM transfers. No automatic scene/flag classification; atlas/staging equality is not a last-writer trace.
- Retains ZIP path/size/capture-count limits and checks for duplicate basenames.

## Running the source-only analyzer

On Windows, from a checked-out repository:

    python tools/analyze_flag_test26_unified.py "D:\path\20261114_154539_315b0c.zip" --output "D:\ISS 26\ISS26_Test26_flag_surfaces.json"

Synthetic regression suite:

    python -m unittest discover -s tools/tests -p "test_*v095_gpudump.py"
    python -m unittest discover -s tools/tests -p "test_analyze_flag_test26_unified.py"

The November 14 Academy ZIP has been received, but the direct runtime file reader returned a service error; no claim is made that the new scripts were run on real session files. **No claim is made that the newly added script has run against that archive**. The file may also lack manually labelled crowd phases, which the analyzer will report honestly.

If existing Academy captures have unknown scene labels, make a manifest with exact VRAM basenames and operator-verified screen phases. Example:

    {"schemaVersion":1,"captures":[{"snapshot":"EXACT_NAME.vram","phase":"carried_banner","team":"Cape Verde"},{"snapshot":"OTHER_NAME.vram","phase":"crowd_flags","team":"Bosnia"}]}

An existing operator capture helper tools/Capture-ISS26-Test12.ps1 supports requesting a real crowd capture on the next VSync during Test Game:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase crowd_flags

## Next hard blockers

1. Verify which archived Test25 captures actually show the stadium intro and carried cloth. Check if waving supporters were captured at all.
2. Compare actual Test25 source atlas style55/staging memory and CLUT with style10 and Cape Verde style1.
3. Trace GPU primitive UV/tpage/CLUT for **carried fabric and crowd waves**. Do not assume a crowd sprite uses the prematch 64x28 atlas.
4. Locate final GPU source upload among DATSEL/DATSEL3, 34 GDC stadium resources or additional crowd graphics/animations.
5. Generate a standalone clean-original ISS26X01 patch with Mode2 parity, preserving the 54 regular + 4 bonus national slots, 24 clubs, and untouched audio Tracks02–12. Validate the four surfaces and stadium/control-team variants before promoting game v0.9.5.

No claims of a fully fixed flag or a completed gameplay regression are made by this research commit.

## Incremental Test26 GP0 source-attribution implementation

- tools/parse_v095_gpudump.py retains all observed live textured draw-group candidates whose UV bounding rectangle overlaps 16x56-word staging at (560,0), even if not in the top-200 frequency groups. Report fields: draw_groups_touching_560_0_16_56 and stage_touch_draw_count.
- tools/analyze_flag_test26_unified.py joins a GPD to a scene only when its encoded emulator frame exactly equals an explicitly operator-labelled VRAM capture. Automated flag_auto_crowd_flags labels do not qualify.
- Per-phase summary reports same_frame_operator_tagged_gpu_dump_count and stage_flag_draw_candidate_count; verified_gpu_draw_ownership remains false until actual screenshot context is confirmed.
- Synthetic regression cases cover positive and negative frame matching, and a GP0(3Ch) textured quad whose 4bpp 560,0 source rectangle and (0,505) CLUT are identifiable.

**Verification gate:** tests have been committed but have not been executed: the code execution container returns ClientError. The owner-provided Test25 archive has been materialized but has not been read. GitHub Actions has deliberately not been invoked to avoid unnecessary CI usage. PR stays draft.

Stage draw overlap by itself does NOT prove that a visible flag was carried on the pitch or waved in the crowd. Genuine spectator-flag draw provenance requires an operator-verified crowd screenshot and animation-frame evidence.

## 2026-11-14 — CI verification and read-only local session runner

Test26 GP0 parser was corrected to carry texture-page state from a textured
polygon into subsequent textured rectangles and use full sprite dimensions
when calculating a VRAM overlap. GP1(00/01) resets/clears pending state.
The erroneous synthetic test expectation for a scene-linked GPU dump was
also corrected; a matching operator frame is properly labelled prematch.

Actual GitHub Actions verification:

- [Test26 16/16 synthetic tests and unchanged-feed gate PASS](https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43609346940).
- [Repeat verification + PowerShell syntax check PASS](https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43609768504).
- 9 GPU parser and 7 unified archive tests; Python py_compile PASS;
  Windows script PowerShell parser PASS; stable game 0.9.4 / Test13 feed unchanged.

New **read-only owner-local** runner:

1. Save tools/Run-ISS26-Test26-ArchiveAudit.ps1 and
   tools/Run-ISS26-Test26-ArchiveAudit.cmd together.
2. Drag the existing Academy session ZIP onto the CMD file; without an
   argument it selects the most recent ZIP under
   D:\ISS 26\ISS26_Data\explorer\reports.
3. The script downloads exactly three Python tools pinned to the successful
   source commit 874adfafde2f47433e379937355efcfefb8defe9,
   validates Python 3.10+, analyzes local VRAM/GPD captures and produces
   two non-game JSON reports under
   D:\ISS 26\ISS26_Data\diagnostics\Test26.
4. It does NOT upload the report, distribute game data, modify the game,
   alter saves or change update feeds. The report includes frame hashes,
   GPU primitive metadata and scene tags, not raw art.

**This still is not evidence that the Nov 14 archive was processed in
ChatGPT:** the working Python/container runtime failed with ClientError
even after file materialization. To close the evidence gap, process that
exact owner's ZIP with this runner, or restore the model-side container,
then inspect the phase-labelled output before authoring the first actual
flag replacement. No speculative claim of fixed supporter flags is made.
