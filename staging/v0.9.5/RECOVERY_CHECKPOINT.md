# ISS26 v0.9.5 recovery checkpoint — 2026-11-08

The interrupted ROOT session left an incomplete staged full-flags transport in `release/v095-flags-rebuild`.

## Recovered facts
- Original European Track 01 verified locally as SHA-256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
- The release branch has `staging/v0.9.5/transport/part_00.b64` through `part_25.b64` (26 parts).
- Last pre-recovery commit `4f4e659e290e0f560b9cd95fb10d80daa6172cb7` says `XOR sector corrections part 26/30`.
- Parts 26–29, transport completion metadata, and verified output SHA-256 are not present in that branch.
- The separately validated CLUT boundary candidate on `main` is **not** a fully corrected flags release; see `staging/v0.9.5/STATUS.md`.
- Public `latest.json` still points to `0.9.4-preview`.

## Required recovery and release gates
1. Restore remaining transport parts from the original generation source or reproducibly regenerate **all** transport pieces (do not fabricate missing data).
2. Decode and inspect format, sector count, XOR records and exact SHA-256; apply to clean Track 01 and verify result and Mode2 EDC/ECC.
3. Verify 54 national team labels, all three flag image sizes, unchanged club graphics and preserved Track02–12.
4. Confirm actual PS1 in-game rendering; especially Bosnia, Senegal, Algeria, DR Congo, Curaçao and Cabo Verde.
5. Only then publish a tagged release asset and update `latest.json` atomically with pinned SHA-256.

This recovery checkpoint does not claim the release is ready. Do not promote any incomplete transport to the auto-update feed.
