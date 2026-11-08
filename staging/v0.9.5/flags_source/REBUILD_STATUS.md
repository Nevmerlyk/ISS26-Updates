# ISS26 v0.9.5 — active flag patch reconstruction

This is not a user-facing Universal Tool update. Work targets the actual game patch.

- Public WECompressor compression grammar recovered, valid decoder and reverse encoder.
- 94/94 compressed uploads in DATSEL2, DATSEL3, EDT_2D and EDTR_2D decode and recompress to identical original pixels.
- Additional previously overlooked main BIN/DATSEL.BIN (ISO LBA 6000, length 215324) contains 55 uploads via its primary command table at resource offset 0x33DAC (base 0x800F0000). All 55 decompress to exact expected lengths (524288 aggregate decoded bytes), providing a complete core selection-screen graphics atlas.
- The primary DATSEL table has extra command lists in header pointers 2 and 3; these must be treated separately from the normal DATSEL2 layout.
- Read-only preview `DATSEL_primary_atlas.png` shows multiple embedded national flag graphics, menus, and fonts.
- Maps linking 54 team slots, 17 modern replacements, and palette styles are still to be verified against the v0.9.4 patched candidate; no game release has been made.

World-map highlighting remains OUT OF SCOPE. No BIN/CUE originals were modified.