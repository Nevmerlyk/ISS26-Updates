# DEV107 — prematch and HUD palette coupling

Source: DEV106 owner session, GPU_Draws.csv (1284 rows), Stage_RAM_Comparison.csv (5 rows).
Derived counts: 18 4bpp polygon draws overlap the two large staging tiles in capture frame 6948: 17 away, one home. Two 4bpp draws cover the HUD slots in capture frame 11268.
- Home large: VRAM words (560,0), 16x28 words, CLUT (224,506).
- Away large: (560,28), 16x28 words, CLUT (176,506).
- Home HUD: (640,98), 6x8 words, CLUT (224,506).
- Away HUD: (646,98), 6x8 words, CLUT (176,506).
- In 4 prematch captures, the combined 1792 bytes equal RAM; gameplay capture retains both stage hashes but only 4 of 1792 RAM bytes match. Home/away labels follow the DEV106 match evidence; do not generalize palette coordinates across all games without verification.
- Therefore preserve shared draw-time CLUT index semantics when generating either surface. Do not patch independent palettes blindly. RAM equality cannot identify the last CPU writer or original disc file. Historical candidate palette (0,505) is not the observed home CLUT in this capture.
- No disc SHA verified in report; no binary edits, release or feed change.
- New read-only analyzer joins VRAM, exact-name RAM and GPD; emits candidate routes and byte equality. Uses existing bounded ZIP/GPD parsers. Run: python tools/analyze_dev107_flag_routes.py report.zip --output dev107.json
- Synthetic tests supplied, not executed in current environment; source CSV aggregation independently checked.
