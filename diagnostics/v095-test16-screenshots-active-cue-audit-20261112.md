# ISS26 v0.9.5 — Test16 screenshot and CUE activation audit (2026-11-12)

## Evidence
New screenshots: Cape Verde is spelled correctly but its large flag is broken horizontal stripes, Bosnia still appears as a multicolor oval, and the ceremonial/player-carried flags are broken too. The PCSX-Redux screenshot has no disc/CUE version indicator.
Old Test12 GPU VRAM contains stripe/oval pixels at historical styles 1 and 10; the verified standalone Test16 DATSEL contains DIFFERENT, candidate corrected 4bpp pixel arrays at those same atlas positions. New screenshots cannot prove that Test16 DATSEL reached the drawn texture.

## Confirmed integration gap
The Test16 installer writes ISS26_Test_0.9.5_TEST16_Track01.bin (SHA256 97BEF5B3ABCA687FBD57017F321634CB8F2F347C826DACE050AC7D9CE450245A) and ISS26_Test_0.9.5_TEST16.cue. It DOES NOT switch the older generic ISS26_Test_0.9.5.cue to that new image. The launcher can still start Test15 or auto-update the published older Test13.

## Fix and safe gate
A reproducible local repair pack ISS26_Test16_Activate_Verified.zip includes the checksum-verified Test16 standalone patch, one-click install/activate, restore-old-cue script, runtime audit, synthetic regression tests and a graphic comparison. The one-click script checks clean original, installed Test16 BIN SHA256, 12 tracks, backs up the generic Test Game CUE and activates the correct image without modifying game binaries or original media. The resulting bin and patch SHA256 are unchanged. Real-disc audit/activation/idempotence/rollback and 4 unit tests passed.
For a controlled screenshot, PCSX-Redux should explicitly open ISS26_Test_0.9.5_TEST16.cue from a fresh boot. If still broken, the next required evidence is a fresh Test16 GPU/VRAM capture to find a later atlas writer; do not repaint DATSEL blindly.

## Unresolved before stable 0.9.5
All 54 flags/names and screen variants unverified; Bosnia table mismatch 55/10/10/55/55 and club collision; Senegal shared style0; crowd/HUD/carried banners and clubs remain to validate. No stable/test feed switch. This audit is not Test17, and not a stable release.
