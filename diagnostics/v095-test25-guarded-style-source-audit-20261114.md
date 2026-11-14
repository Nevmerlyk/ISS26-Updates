# ISS26 v0.9.5 — Test25 guarded style and source audit (2026-11-14)

**Status:** source code + tests prepared and executed locally. **No game patch built or
published**; stable game remains v0.9.4. Academy/Updater product v0.9.5 unchanged.

## Verified owner-provided evidence

- Original European 12-track ISS Pro Evolution 2 Track01,
  SHA256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
- Real Academy Test Game ZIP `20261113_233425_e379df.zip`,
  Cape Verde–Bosnia, 12 screen/GPU/VRAM captures.
- Test24: observed Cape style 1 from atlas (848,256); Bosnia style 10 from (864,312).
  Both match staging (560,0)/(560,28) byte-for-byte in all 12 captures.
- Clean original 55 DATSEL uploads, 22 DATSEL3 uploads, 34 GDC resources.
  None of their decoded selected tiles is byte-identical to Test13's
  **already-corrupt** captured sprite art; actual patched last uploader remains unproven.

## New Test25 safety discovery

The original EU disc has five independent 78-entry style maps
(54 regular nations, 24 clubs; bonus four national slots separate).
National/club style collisions across the clean disc: **0, 7, 10, 17**.

Candidate styles **40, 41, 42** are unused in all five original tables,
but they are **not empty atlas cells**:

| Unused style | Atlas word XY | Sources decoded | Distinct tile hashes | Mean nonzero nibble-index fraction |
| --- | --- | --- | --- | --- |
| 40 | (768,284) | 36/36 | 2 | 0.983 |
| 41 | (784,284) | 36/36 | 2 | 0.981 |
| 42 | (800,284) | 36/36 | 2 | 0.985 |

A fourth trap: **style 44** appears unused in tables 2–5, but
table 1 uses it in **club slots 54–57**. A style can only be
considered unreferenced if it is unused across **all** tables.

Thus neither blindly reusing style 10 nor merely assigning
40/41 without rewriting every relevant source is acceptable.
`GDC_BN` has alternate physical content at these positions; the
same style ID does not imply identical texels across all stadiums.

## Reproducible Test25 tooling

The user-facing local research bundle contains:
`iss26_test25_style_patch_audit.py`,
`test_iss26_test25_style_patch_audit.py`,
`Run-ISS26-Test25-ReadOnly-Audit.ps1`,
`ISS26_Test25_clean_disc_baseline_20261114.json`, and Russian README.

The analyzer reads an **official published Test13 ISS26X01 file**
as XOR sector masks on top of the owner's **unmodified** Track01;
it strictly verifies the full release SHA, sector counts/order, 32-byte
original-sector SHA guards and untouched 24-byte CD headers. It
then virtually reconstructs all five style maps and modified
DATSEL/DATSEL3/GDC compressed source tiles, compares their SHA hashes
against Academy's captured flags, and reports candidate source resources.
**It never generates a patched BIN, modifies originals, or updates feeds.**

9/9 Python tests passed, including clean-disc SHA, old and new style-slot
virtualization, source-sector SHA rejection, raw header rejection,
truncated/out-of-order patch rejection, LZ decompression and original
resource checks. The official published binary Test13 asset
(`ISS26_0.9.5_LargeFlagSource_TEST13.iss26p`) was not mounted locally
in this analysis turn, so **patch-specific slot/atlas changes are not yet
verified**. It will be consumed by the read-only runner when present.

The tracked GitHub PowerShell inspector was also hardened:
[Inspect-ISS26-FlagStyles.ps1](https://github.com/Nevmerlyk/ISS26-Updates/blob/main/tools/Inspect-ISS26-FlagStyles.ps1)
now checks all five maps for truly unreferenced and national/club-conflicting IDs.

## Strict release gate remaining

1. Read the actual published Test13 sector masks via Test25; establish
   patched style maps, GDC and DATSEL/DATSEL3 candidate tile hashes.
2. Confirm last GPU atlas writer at runtime, not merely a matching resource
   (several resources can upload the same atlas rectangle).
3. Design per-national-slot allocation safe across five tables, club styles
   and all active stadium resources, including the four bonus-team slots.
4. Produce a **fully self-contained** clean-EU-original ISS26X01 test patch,
   maintain Mode2 EDC/ECC, preserve Tracks02–12, confirm all 54 standard +
   4 bonus national slots and 24 clubs.
5. Run one targeted Cape Verde–Bosnia match with control club emblem check;
   publish stable game v0.9.5 **only after visual regression passes**.

### Scope note

Academy Test24 diagnostic PR #46 is also source-only:
https://github.com/Nevmerlyk/ISS26-Android/pull/46
No additional match test is necessary until the next *actual* patch candidate.

## Verified official Test13 style table defect and independently built Test25 candidate

GitHub Actions successfully downloaded the authentic official Test13 patch
(SHA-256 `159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214`)
and exported its five actual XOR style-table masks, **without any original
commercial disc bytes**. CI run:
https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43534174287
Mask metadata:
https://github.com/Nevmerlyk/ISS26-Updates/blob/main/diagnostics/v095-test25-official-test13-xor-metadata.json

Applying those verified masks in memory to the user's verified clean
Track01 produced **this exact patched style assignment**:

| Table raw LBA | Bosnia national slot30 | Club slot54 | Cape Verde national slot0 |
| --- | --- | --- | --- |
| 820 | 55 | 10 | 1 |
| **852** | **10 (collision)** | 10 | 1 |
| **955** | **10 (collision)** | 10 | 1 |
| 2085 | 55 | 10 | 1 |
| 2433 | 55 | 10 | 1 |

Thus two of the five Test13 tables incorrectly send Bosnia to the **same
style 10 as club slot54**, explaining the observed circular club-style
emblem. The other three tables already route Bosnia to **exclusive
style 55**, which is unreferenced by every other national or club in
these five tables. There is no need to globally overwrite club style 10
to solve this *routing* defect.

### Test25 experimental independent release

Built **only** these two byte fixes by changing the published Test13
sector XOR masks at LBA 852 and 955, national slot index 30,
from `7 XOR 10 = 0x0D` to `7 XOR 55 = 0x30`.
Recalculated Mode2 Form1 EDC/ECC deltas. Preserved all 1492
clean-original-independent sector SHA guards and every other 1490
sector record byte-for-byte.

- Public **prerelease**: https://github.com/Nevmerlyk/ISS26-Updates/releases/tag/v0.9.5-bosnia-style-test25
- Asset: `ISS26_0.9.5_BosniaStyle_TEST25.iss26p`
- Size **3,562,908 bytes**
- SHA-256 **`85014C8222A408344704CCD8FC192379645E18770876CF4501324D504D55BA67`**
- GitHub validated build, remote redownload and SHA:
  https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43534760234
- Builder: https://github.com/Nevmerlyk/ISS26-Updates/blob/main/tools/build_v095_test25_bosnia_style_isolation.py

**Do not call this a fully fixed Bosnia flag yet.** Actual style-55
compressed bitmap/CLUT and in-game visual result remain unverified.
Cape Verde's incorrect artwork and names were NOT changed by Test25.
Stable game `stable/latest.json` remains **0.9.4**; the ordinary
Test Game feed remains **Test13**; no existing installs were modified.
The next useful runtime test is a single user-controlled Test Game of
this separately selected prerelease (Cape Verde home vs Bosnia away),
not another Rookie exam. Check both national flags and club slot54
for regressions.

Original local offline validation: 9 Test25 clean original + session
integration cases and 4 synthetic LBA852/955 parity/guard cases passed.
CI verified the full published 1492-record patch and redownloaded asset.

