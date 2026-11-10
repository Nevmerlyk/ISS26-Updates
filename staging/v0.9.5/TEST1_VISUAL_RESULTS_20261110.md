# ISS26 v0.9.5 FLAGS TEST1 — screenshots, 2026-11-10

**Test status: FAIL / expected diagnostic, NOT a flags-only fix.**

This report is grounded in three screenshots supplied by the project owner from PCSX-Redux (European game SLES03321). Screenshots do not include GPU primitive/VRAM dump. Do not promote TEST1 to Stable.

## Exact observed screens

1. **National selection, Denmark highlighted:** Denmark's small red-and-white cross icon is intact; the national-choice flag grid still contains a dark-blue ellipse (third row, third tile in the screenshot) instead of a proper country's flag. This is a regression-check reference, not evidence that Denmark itself was changed.
2. **Pre-match, displayed labels Ireland / Russia:** left emblem contains dark starry shape above white/blue bars; the Russia-labeled right emblem is the same dark-blue oval with tiny yellow speckles seen in earlier test sessions. Two legacy names survive on this screen even though in the replacements list the original Ireland slot is assigned to Cabo Verde and the original Russia slot to Bosnia.
3. **At kickoff, scoreboard 0–0:** the left mini emblem is a tiny horizontal strip rather than an identifiable complete flag, while the right mini emblem is the same blue oval as in the pre-match. This establishes an end-user-visible repetition across two contexts, **not** proof they use the same VRAM texture/CLUT.

## Root-cause constraints from confirmed project forensics

- The public release `v0.9.5-flags-test1` package SHA256 is `3B667CF6031BC2BFAA143D0D21ACF6D623447C222096805D529739235E2216A4`. It is **byte-identical** to the old `v0.9.5A` test, not the five-country graphics/GDC candidate or the full new 17-country art.
- The TEST1 release metadata explicitly says it modifies the 64×28 Bosnia image in `DATSEL` and `DATSEL3` only; it does **not** modify 34 stadium `GDC_*.BIN` reuploads or 24×16 / 24×8 score/HUD variants. Failure to fix the pre-match/on-field ellipse is therefore predicted, not a new mystery.
- `FLAGS_NAMES_FORENSIC_DOSSIER.md` gives inverse flag indices: 54 style/CLUT entries are reversed against the 54 team name slots, `flag_index = 53 - team_slot`. Old slot 23 Russia -> intended Bosnia flag index 30; old slot 53 Ireland -> intended Cabo Verde flag index 0. Do NOT change country-name tables under the **flags-only** v0.9.5 specification; the surviving "Russia"/"Ireland" names are tracked as a separate inherited-name-bank defect and must not be disguised as a corrected flag.
- The earlier read-only VRAM/GDC forensics in `FLAGS_ONLY_GDC_LIVE_PROVENANCE_20261110.md` found 34 patched `GDC_*.BIN` stadium-specific reuploads that restore the oval. The five-country full-GDC proof candidate was **not** what TEST1 shipped.

## Decision and exact follow-up for TEST2

1. Never mark TEST1 successful, change stable v0.9.4, or claim score HUD flags repaired.
2. Build a separate candidate based on the original stable v0.9.4 + *all* stadium GDC uploads as well as DATSEL/DATSEL3; independently verify compressed stream decode, sector EDC/ECC and no other graphics changed.
3. Resolve the smaller 24×16 and 24×8 icons with live GPU tpage+UV+CLUT, using the already-working player-nationality Master League icons for Bosnia/Canada as references; avoid inferring shared source solely from similar rendered pixels.
4. Test each of the 17 replacement countries and unaffected control countries; compare big and small renderings in selection, pre-match, stadium and in-match HUD.
5. No final 0.9.5 Stable promotion until all targeted flags have visibly passed.

Screenshot source: three user-supplied images displayed in chat, from selection, pre-match and match kickoff, 2026-11-10. They are **not** embedded in the GitHub repository.
