# ISS26 Kit Workbench — preparation
Target: clean EU SLES-03321 and owner-approved RC3 identity baseline. Do not substitute WE2002 ROM offsets or a different test build. Current workbench is an untested source candidate.

External research: [WE2002 TEX description and implementation](https://github.com/hiitsgabe/retro_roster_patcher/blob/main/src/retro_roster_patcher/games/we2002/jersey_tex.py) (MIT project), [historical ISSPE2 TEX workflow](https://soccergaming.com/forums/threads/we2002-how-to-edit-shirts-d.35591/). The related game's four 128x128 indexed image blocks and four 256-word palettes are hypotheses to verify in EU. Long sleeves, goalkeeper portions, number colors, shared indices, and 2D previews need separate examination. No third-party game offsets are used by the inventory.

## Local audit, no new matches
Download Run-KitWorkbench.cmd and Run-KitWorkbench.ps1 into the same folder. Run the CMD. Defaults to D:\ISS 26; accepts the game directory as its first argument. Requires Python 3 and access to the pinned GitHub source. It runs synthetic checks, then inventories TEX files on the verified original and compares with up to four existing Academy archives. Report: ISS26_Data/diagnostics/KitLayout_*.json. No game files changed. No game bytes uploaded. If the strict parser rejects a resource, report its actual layout; never force the WE2002 mapping.

## Edit gate
1. Bind each TEX resource to the actual current ISS26 slot by independent evidence. No filename/slot guesses.
2. Confirm home/away outfield and goalkeeper palettes and geometry; find the actual UV regions and protected indices, not just similarity of colors.
3. Export candidate texture pages and inspect the player/GK visual separation and number colors.
4. Use same-size palette-only edits first on a private resource copy, with expected SHA256 and approved clothing indices. The tool refuses flag slots and keeps the number-index range conservatively locked. No disc output yet.
5. Add guarded indexed texture repainting, compression and isolated sector patch assembly only after mappings, executable load capacity and in-game evidence are known. Menu uniform previews and auto-clash behavior are distinct follow-up targets.
6. Compare source, RC3 and resulting patch; preserve flags, remaining team identity, player data, referee art, audio tracks, and every unrelated resource.

Pilot: Ukraine and Germany (2026); FC Kryvbass and Manchester United (2025/26). All 58 national/bonus and 24 club slots in scope; minimum 246 outfits, possible 328 if the native two GK variants per team are confirmed. Do not claim any outfit as converted until a binary resource is actually prepared. Correctness requires real emulator acceptance.

Current limits: no real BIN or archive inspection due to ClientError. The synthetic Python tests are written, not executed in this environment. No patch or feed published.
