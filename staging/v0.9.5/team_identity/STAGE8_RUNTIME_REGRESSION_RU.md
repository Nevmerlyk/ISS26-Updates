# ISS26 v0.9.5 — Stage 8: large ceremonial flag texture incident (corrected diagnosis)

**Date:** 2026-11-10. **Status:** reproducible static delta classification + user-observed PCSX-Redux regression; no new game patch.

## In-emulator observations (screenshots supplied by the user)

1. The pre-match banner still labels teams `Russia` and `Greece`, despite the selected new teams Bosnia and New Zealand. Hence text identity repair remains incomplete.
2. The two large banner flags are incorrect/corrupted; the right is a montage of unrelated flag graphics.
3. **CORRECTION, 2026-11-11:** the large cloths seen under / beside the players during the walkout are **intended ceremonial flags carried by stadium staff/players**. Their presence and size are normal, NOT texture sprites accidentally drawn onto the grass. The problem is the **wrong content rendered on those flags** (composite/garbled national-flag artwork). The user's control screenshot shows England and Germany flags carried during the same ceremony and rendered correctly.
4. During play, the HUD flag icons are wrong, but `Dzeko` and `Barbarous.` names show that the new roster-name bank is active. The user later tested Test09, which reverted only the two large DATSEL/DATSEL3 streams; the ceremonial flags were still garbled. The root cause must therefore not be attributed solely to those two streams.

**Screenshots contain no build identifier.** Timing strongly suggests Test07, but the exact installed artifact should still be confirmed in the user's launcher log or by checking SHA-256 of patched Track01. No claim is made that Test06 has been runtime-verified safe.

## Patch isolation / static findings

- Test06 asset SHA-256 `3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636`.
- Test07 asset SHA-256 `DA022A8CAFCFFC30C3FDF430A4BE80263A17FD3214028E5D939E39AF711D82C9`.
- Independent `.iss26p` comparison changes **63 CD sectors, all located within 34 `GDC_*.BIN` resources**.
- Test07's edited GPU upload includes VRAM words at `(864,320)` in a stadium resource. This location may be reused for other texture types during the stadium/match phase. A matching GPU destination coordinate and successful WE decompression do NOT establish flag ownership or UV/CLUT use at runtime. The **garbled artwork on the ceremonial flag objects** indicates unresolved flag texture/UV/CLUT/source mapping; it does **not** prove random pitch geometry contamination or stadium texture aliasing. The exact runtime source of the cloth flags still needs validation.

## Immediate mitigation

Test channel `test/latest.json` switched from `0.9.6-teamidentity-test07` to `0.9.6-teamidentity-test06` (commit `406f39e8ba191a7b694a0671f6744e07b87470c5`). Stable `Play Game` remains v0.9.4. The launcher compares nonnumeric labels for inequality, so test07->test06 triggers reinstallation from clean original rather than layering a downgrade, even though numeric-version downgrade protection exists.

## New safety gate

`stage8_runtime_regression_gate.py` checks a candidate's independent `.iss26p` sector masks against a baseline and **blocks unreviewed changes to any of 34 stadium GDC file extents** pending runtime attribution. The block is retained as a conservative precaution against incorrect atlas edits, **not** because the ceremonial flags appearing on grass are a rendering bug. It does not claim GDC-free patches are automatically safe. Four unit tests pass. Running the gate against Test06 and Test07 returns `BLOCKED_PENDING_RUNTIME_VRAM_PROOF`, 63 changed sectors across 34 GDCs.

## Next verification requirements

1. Verify Test09 installed patch hash and compare its Bosnia vs New Zealand pre-match flag and ceremonial walkout artwork against earlier builds. A correct comparison must use the normal England/Germany walkout as reference; the flag cloths themselves are expected.
2. Capture PCSX-Redux GPU VRAM and draw commands during (a) pre-match flag panel and (b) ceremonial cloth flag drawing. Determine the actual UV, tpage, CLUT and source texture for each distinct surface. Do not infer aliasing from the objects being placed on the grass.
3. Identify the sources of large banner flag, 24x8 scoreboard icon and legacy pre-match name separately. The earlier ASCII scan does not cover compressed/encoded glyph sources, and replacing `SELECT` names is insufficient.
4. Patch only source regions with a proven runtime render owner; re-test **at least** Bosnia/New Zealand/Germany/Canada, one day/night stadium, and match entrance + active play before updating Test Game.

**Do not reactivate the Test07 GDC patch or promote to stable.**
