# ISS26 0.9.5 — Test20 visual QA (13 November 2026)

**Status:** Failed visual QA; no release promotion. This report uses three user-submitted PCSX-Redux screenshots of the current test and a prior Test19 screenshot. A screenshot cannot prove loaded CUE SHA256 or the actual GPU last writer.

## Selection / 54 national slots

- Slot 0 **Cape Verde**: small blue stripe/star icon visibly improved against Test19. Compact label remains `C.VERDE`.
- Slot 24 **Curaçao**: near-solid dark blue, missing expected yellow stripe and white stars.
- Slot 25 **Jordan**: near-solid dark blue.
- Slot 27 **New Zealand**: white diagonal saltire on blue, not its Union Jack and red stars.
- Slot 39 **Canada**: USA-style stripes rather than red maple leaf.
- Slot 42 **Ecuador**: green graphic on blue, not yellow-blue-red tricolor.
- Slot 43 **Panama**: horizontal stripes instead of red/blue quarters with stars.
- Slot 49 **Uzbekistan**: incorrect striped/star configuration.
- Slot 51 **Qatar**: needs close reference inspection (do not assert pass from this screenshot).
- All other national slots: not individually reference-verified; do **not** interpret absence from this list as correct.

## Prematch and HUD

- **Cape Verde**: correct name `Cape Verde`, but large flag shows black field with red dots and two long white stripes.
- **Bosnia**: name is legible; large flag remains a multicolor elliptical corrupted texture.
- HUD: both icons remain unusable as legible national flags.
- Test19-vs-Test20 crop comparison confirms that offline DATSEL atlas fidelity did not translate into a correct prematch display.

## Engineering conclusion

Small selection flag raster+CLUT+style and prematch 64×28 raster+CLUT+last-writer provenance **must** be validated independently. Merely keeping 45 old owners' 64×28 BGR555 pixels unchanged was insufficient to guarantee correct small icons or prematch GPU rendering.

**Release gate:** Test20 fails. Before building Test21, obtain Test20 GPUDUMP at 54-team selector and stadium-intro (plus VRAM). Locate source UV/tpage/CLUT and last texture upload for each failing primitive; add per-screen regressions. Do not rename current build to stable 0.9.5. No code or game binary changed by this audit.
