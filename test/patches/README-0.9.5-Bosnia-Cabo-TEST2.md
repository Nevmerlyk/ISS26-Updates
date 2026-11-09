# ISS26 0.9.5 Bosnia + Cabo Verde atlas experiment (TEST2)

**TEST CHANNEL ONLY, NOT A STABLE RELEASE.**
The artifact is a standalone `ISS26X01` XOR patch applying **only to the verified clean EU Track 01**, not on top of another patch.

## What it tests
- Repacks and verifies 64x28 4bpp Bosnia/Cabo Verde large flag artwork into both DATSEL and DATSEL3 and **34 separate stadium GDC resources**.
- Sets country-specific 16-color national CLUTs, Bosnia/Cabo flag style pointers, and known uppercase/titlecase text names.
- 106 affected MODE2 Form1 CD sectors, with recomputed EDC/ECC and per-sector SHA256 guard.
- Track 02-12 audio and original source files are unchanged.

## Known limits: do not treat this as the v0.9.5 fix
- **Does not contain other changes from v0.9.4**, including the rest of the 2026 roster/club package.
- 24x16 and 24x8 sprites, graphical pre-match name atlas, and emulator display are **not yet validated**.
- Bosnia uses historical shared style 10; Cabo Verde style 1. On this minimal clean-ROM test, the legacy Slovakia and Northern Ireland slots can also show the experimental artwork. Those teams were replaced by DR Congo and Algeria in the broader 2026 mod.
- This test is intended to verify whether corrected stadium *uploads* actually fix the previously observed blue Bosnia oval and Cabo Verde flags. Do not promote to stable.

## Install
With ISS26 Launcher/Explorer v0.6.7+ select **Test Game** to fetch the test channel. The launcher must apply to a private writable copy of clean EU Track01. Play Game remains unchanged.

- Source Track01 SHA256: `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`
- Patch SHA256: `4C3B27A7EFA46F97401138C7B2490CC08CC693613CDFB82A9BA12150BA7CD330`
- Expected patched Track01 SHA256: `F620ACE593D4CB32BA9BF001BFA028CA6A5ECE7E907A4F83EAA856C9E6168246`

## Test cases
Choose Bosnia vs Germany and Cabo Verde vs Germany; capture selection screen, pre-match introduction, in-match large flags and scoreboard. Check adjacent flags; this preview is not approved for all-country testing.
