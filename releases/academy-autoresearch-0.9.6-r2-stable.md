# ISS26 Academy AutoResearch 0.9.6 R2 — Stable companion designation

Date: 2026-11-17
Channel designation: **stable (standalone companion module)**

The project owner requested promotion of the previously prepared ISS26 Academy AutoResearch v0.9.6 R2 package to stable. This designation covers the **passive AutoResearch companion** only, not the bundled ISS26 launcher, core Academy/Rookie binary, Windows updater, or game patch.

## Frozen package
- File: `ISS26_Academy_AutoResearch_096_R2_Stable.zip`
- SHA-256: `24670f8b6178c6db6abc521514839533fc51259d944445a18176995a563c0b8a`
- Size: 11,693 bytes
- Full stable ZIP is distributed as an attachment in the user's ISS26 project conversation, not as a GitHub release asset; no remote ZIP download endpoint is claimed.
- Existing collector implementation retains version `0.9.6-R2`; only version/release metadata and user-facing documentation mark the stable designation.

## Validation
- 4/4 offline Python tests passed, including processing captured data from the two Academy sessions supplied by the user.
- ZIP CRC verification passed; all packaged files match the internal SHA256 manifest.
- Calibrator request/response protocol checked against previous Academy session Lua.
- Actual live operation on the user's Windows / Master League installation has **not** been verified.

## Functional scope
- No manual hotkeys for evidence capture; auto-samples active ISS26 Test Game sessions.
- Saves screen, RAM and VRAM snapshots; de-duplicates screen states and creates result archives.
- Does not navigate the game automatically, identify a nationality memory address, or establish GPU texture/CLUT provenance.

## Channels and safety
- Stable game patch feed: **unchanged**.
- Stable launcher auto-update feed: **unchanged**; this companion is not integrated into that updater.
- Original BIN/CUE, saves and game input: **unchanged**.

A separately validated Windows launcher build and signed/hashed update archive would be required before incorporating this companion into the existing launcher auto-update channel.
