# ISS26 v0.9.5 — Stage 8: quarantine of Test07 stadium texture regression

**Date:** 2026-11-10. **Status:** reproducible static delta classification + user-observed PCSX-Redux regression; no new game patch.

## In-emulator observations (screenshots supplied by the user)

1. The pre-match banner still labels teams `Russia` and `Greece`, despite the selected new teams Bosnia and New Zealand. Hence text identity repair remains incomplete.
2. The two large banner flags are incorrect/corrupted; the right is a montage of unrelated flag graphics.
3. In the match entrance, giant multicolored flag/atlas fragments are laid on the field beneath the players. This is a **runtime graphical regression** relative to the project's earlier screenshots.
4. During play, the HUD flag icons are wrong, but `Dzeko` and `Barbarous.` names show that the new roster-name bank is active.

**Screenshots contain no build identifier.** Timing strongly suggests Test07, but the exact installed artifact should still be confirmed in the user's launcher log or by checking SHA-256 of patched Track01. No claim is made that Test06 has been runtime-verified safe.

## Patch isolation / static findings

- Test06 asset SHA-256 `3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636`.
- Test07 asset SHA-256 `DA022A8CAFCFFC30C3FDF430A4BE80263A17FD3214028E5D939E39AF711D82C9`.
- Independent `.iss26p` comparison changes **63 CD sectors, all located within 34 `GDC_*.BIN` resources**.
- Test07's edited GPU upload includes VRAM words at `(864,320)` in a stadium resource. This location may be reused for other texture types during the stadium/match phase. A matching GPU destination coordinate and successful WE decompression do NOT establish flag ownership or UV/CLUT use at runtime. The visible field artifacts are consistent with a texture alias. The exact runtime origin still needs validation.

## Immediate mitigation

Test channel `test/latest.json` switched from `0.9.6-teamidentity-test07` to `0.9.6-teamidentity-test06` (commit `406f39e8ba191a7b694a0671f6744e07b87470c5`). Stable `Play Game` remains v0.9.4. The launcher compares nonnumeric labels for inequality, so test07->test06 triggers reinstallation from clean original rather than layering a downgrade, even though numeric-version downgrade protection exists.

## New safety gate

`stage8_runtime_regression_gate.py` checks a candidate's independent `.iss26p` sector masks against a baseline and **blocks changes to any of 34 stadium GDC file extents** until manual in-emulator verification authorizes them. It does not claim GDC-free patches are automatically safe. Four unit tests pass. Running the gate against Test06 and Test07 returns `BLOCKED_PENDING_RUNTIME_VRAM_PROOF`, 63 changed sectors across 34 GDCs.

## Next verification requirements

1. Cold-start Test06 from newly rebuilt clean-original Track01, **not** an emulator savestate; confirm active version/hash in launcher logs. Compare same Bosnia vs New Zealand pre-match and pitch entrance screen against the supplied Test07 screenshots.
2. Capture PCSX-Redux GPU VRAM before and after stadium load (and optionally GPU upload traces). Determine if `(864,320,64x28)` is flag art or a texture shared with player shadows/pitch decals. Match actual draw command tpage/CLUT/UV to the intended flag.
3. Identify the sources of large banner flag, 24x8 scoreboard icon and legacy pre-match name separately. The earlier ASCII scan does not cover compressed/encoded glyph sources, and replacing `SELECT` names is insufficient.
4. Patch only source regions with a proven runtime render owner; re-test **at least** Bosnia/New Zealand/Germany/Canada, one day/night stadium, and match entrance + active play before updating Test Game.

**Do not reactivate the Test07 GDC patch or promote to stable.**
