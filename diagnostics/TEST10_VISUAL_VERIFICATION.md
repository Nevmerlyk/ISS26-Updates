# ISS26 — Test10 visual verification (gameplay evidence)

**Track:** European ISS Pro Evolution 2, 12-track BIN/CUE, clean Track01 SHA-256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.

**Patch:** `v0.9.6-teamidentity-test10` (experimental Test Game only). Standalone `ISS26_0.9.5_TeamIdentity_PrematchNames_TEST10.iss26p`, SHA-256 `9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B`. The installed Windows launcher version is unrelated to the game's stable patch release.

## What is already verified (automated)

- Test08 → Test09: only original sector masks 6089, 6090, 6256, 6257 change; each difference has valid PS1 Mode2 Form1 EDC/ECC.
- Test09 → Test10: all 1,412 earlier independent sector records remain bit-for-bit unchanged; exactly 84 original-sector records are added in three blocks: 8200–8227, 8230–8257, 8260–8287.
- All 84 new source-sector SHA-256 guards match the owner's unmodified European Track 01 (verified through a combined digest), and all 84 XOR masks have valid Mode2 Form1 EDC, ECC P and ECC Q; raw sector headers are not changed.
- These findings **do not verify the rendered names or flags**. The 17 newly rasterized national prematch labels and the large Bosnia graphics remain gameplay-untested.

Audit result: [teamidentity-test10-static-audit.json](teamidentity-test10-static-audit.json).

## Minimal in-game test (fresh game boot, not a save state)

**Do not run from Play Game**: leave the official stable game patch v0.9.4 untouched. Obtain Test10 from the experimental GitHub Release and launch through **Test Game**.

For **Bosnia, Canada, New Zealand**, record the actual on-screen team name, national flag pixels and any abnormal graphics at:

1. **National team selection.** Capture full screen and close-up of the 24×16 small-flag sprite slot. Compare the visible ~20×16 art region. Requested adjustment is +1 px up and +1 px down on Y (not X). Note clipping and transparent margins.
2. **Prematch screen.** Record the full rasterized team name and both teams' flags. Test10 specifically changed 17 national-name atlases; a corrected small flag does not prove prematch correctness.
3. **Kickoff and running scoreboard.** Capture the small HUD icon (24×8 class) and flag appearance after stadium graphics are loaded. Large-flag rendering uses different graphics paths.
4. **After a scene change** (e.g. pause, replay, return). Record any corruption/overwrites and whether the original flag reappears.

Choose **Denmark** as an unaffected control. For Bosnia and Canada, compare with the owner-supplied Master League reference (known small nationality flags). For New Zealand confirm its distinct national emblem instead of Greece artwork.

## Regression isolation (if a large flag corrupts)

Run a separate *fresh* boot of **Test08** and **Test09** at the same in-game screen and record whether the defect appears in one, both or neither:

- Test08 includes reconstructed small Bosnia/Canada flags; it also contains the experimental big Bosnia source uploads.
- Test09 changes only four sectors in the big Bosnia upload sources, relative to Test08.
- Test10 preserves the Test09 sector masks plus 84 name-related sectors.
- Test07 stadium GDC bulk edits are quarantined; do **not** use them as a baseline for promotion.

## Evidence format

For each image: **patch tag**, **screen or game phase (as actually observed)**, **selected team**, **expected flag/name**, **observed issue**. Prefer exact-size PNG and a full-screen context image, rather than resized images. The diagnostic ZIP from Explorer/Academy is optional; include it **without** source BIN/CUE or BIOS.

## Acceptance gate

No stable v0.9.5 promotion until the actual game renders correct national flags at each screen, all 17 affected prematch names work, no unaffected team is changed, and the clean-original independent patch passes disc integrity and gameplay tests.

Stable game channel `stable/latest.json` stays on **0.9.4**.
