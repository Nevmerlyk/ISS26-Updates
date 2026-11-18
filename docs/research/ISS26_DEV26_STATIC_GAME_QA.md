# ISS26 v0.9.6 DEV26 — native GK-last + Riznyk height static verification

Date: 2026-11-19 (Europe/Kyiv). **Status: development candidate only. No release feed changed.**

## Source and independent reconstruction

- Original EU PAL 12-track Track01 SHA256: `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`
- Stable 0.9.5 standalone transport reconstructed from all 58 pinned chunks: `4914C36BFAC27AFF4C4FB60BBD7AB49867FC1E67F26CE733686E73C79C839148`.
- Original v0.9.6 name-only patch reconstructed: `5EC84C0C6B31F503DECD9FF2AD37B40A65EFEF3CF5CD593A1A98992368326D11`.
- v0.9.7 historical roster carrier rebuilt: `ACBA2D25D505D949D95718092CDE2D23BAF0C361AB17FBF127DB411AD7C3D870`.
- v0.9.6 internal 2GK + appearance carrier SHA: `F3A211300AF201BE709498872E1E2572A7D1C362B3AA6E1ABCF90EC6C0969A97`. Its independently rebuilt game SHA: `C66A2D63F12CD9130B4E9265670E4DA0D8CC5F40BA7C2B632C0C3048BB114C0F`.
- All 699 baseline sector preimages and full 496,156,752-byte image SHA verified from user's pristine original.
- The runtime-provenance-based citizenship audit found 263/528 candidate ref groups matching, **228 not matching**, **37 missing personal country group IDs** in 20 countries. Composite ref high-byte is physical addressing and cannot be blindly reassigned.

## DEV26 actual new standalone patch

Independent patch SHA: **`92901BC6C6BD2BCF360011155C61752C0AE4F637253F51501A3FE58445464AE6`**

Full patched Track01 SHA: **`A4D60C0CB42A7EE988EC9E6B580F2BDB3E832B80AE0AC000B4E7605B51797245`**

- 32 national squads had the backup goalkeeper in **slot 21**; switch complete native 10-byte names and 12-byte attributes between slots 21/22, swap both 5-bit shirt fields in the EXE per-team number bank.
- Remapped **9** shared club links to preserve the same physical player identity and all 528 club identities.
- One club (AC Milan) had its backup GK in slot 21; swap club roster references, without changing player identity/attributes.
- Native Dmytro Riznyk physical record (Ukraine group 29, slot 22) had 189cm encoded; changed **only** 6-bit height field to 186cm, preserving position, default number, all 15 abilities and other attributes.
- **54/54 national and 24/24 club** roster banks now have GK positions [1,22].
- All 1,188 national EXE shirt bank 5-bit values match the associated native physical record number bits.
- All 341 extra player physical stat records and 88 original bonus player records remain unchanged; readback verifies all club names/identities unchanged except AC Milan's bench GK position swap.
- 699 guarded independent XOR sectors total; **16 sectors edited** vs pinned baseline; Mode2/Form1 EDC/ECC recomputed. Full clean + patched SHA and independent re-application checked. Original audio 02–12 tracks and original CUE untouched.
- Complete ZIP (patch + installer + build source + report) delivered in user's current ChatGPT conversation, not stored in GitHub. Repro input bridge: GitHub Actions run **44413241098** artifact `ISS26-v096-local-build-handoff`.

**Release blockers remain**: exact personal nationality in Master League, mini-flags and atlases, native 2026/27 club and national jersey numbers, desired two-by-role bench quotas, official roster final curation, kits/graphics, PS1 emulator smoke acceptance. The user was explicitly told this is experimental and that neither Test nor Stable feed was modified. Do not claim complete v0.9.6 or promote any feed based on this static report.
