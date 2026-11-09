# ISS26 v0.9.5 — second PCSX-Redux runtime Test Game: VRAM evidence

**Observed:** 9 Nov 2026. Stable channel must remain **v0.9.4**. This is forensics, **not** a validated graphics patch.

## User in-game screenshots

The new v0.9.5 Test Game build shows **Ireland** over Cabo Verde's partially recognizable large flag; **Russia** over Bosnia's incorrect blue oval. On-field flag geometry likewise shows a recognizable Cabo Verde pattern and a blue blob for Bosnia. The earlier Test Game was Bosnia v Germany.

## New verified discovery: VRAM is already in Explorer Save States

Two user-supplied Explorer reports each contain a `PCSX-Redux SaveState v5` (protobuf):

- first report `ISS26_Explorer_20261109_141108_manual.zip`: `state_00008640.state`
- second report `ISS26_Explorer_20261109_151338_manual.zip`: `state_00010620.state`

The file's **top-level protobuf field 5, nested field 3** holds 2,097,152 raw bytes. Its first **1,048,576 bytes** are the PS1 1024×512 BGR555 VRAM words, including both framebuffers and atlas pages. This was validated visually against the user's gameplay screenshots and the original 4bpp flag tiles.

For original large flag styles 0–27, the original source grid occupies **VRAM x832..895, y256..479**, 4 columns × 7 rows, where each cell is 16 16-bit words (=64 pixels 4bpp) by 32 rows. We compared all **14,336 16-bit words** in this entire area across the two separate runs. **Difference count = 0** — the flag atlas is byte-identical. The live in-game 4bpp tiles can be extracted by decoding low-to-high nibbles and applying the country's 16-color CLUT.

- **Bosnia**: name slot 23, flag slot/CLUT index 30, CLUT VRAM **(224,506)**. The attempted remap to large style **10** still yields a **blue oval with yellow specks**, both in the player screenshots and directly from actual VRAM, and is the same in both reports.
- **Cabo Verde**: name slot 53, flag/CLUT index 0 at **(0,505)**, style **1**. The live VRAM sprite contains star/stripe shapes and is also byte-identical across the two test runs. This is consistent with Cabo Verde looking almost right, while the pre-match title still says Ireland.

**What this proves:** newly edited DATSEL/DATSEL3 graphics did not change these loaded, final in-match atlas bytes. They may be overwritten by stadium GDC uploads, replaced from another resource, or simply not used by this rendering route. Do not conclude which loader is responsible without a capture at the moment of upload. Repainting DATSEL again without investigating the live source would be unproductive.

## Name banks

Previous binary inspection shows existing literal strings Russia/ Ireland already replaced in six known ASCII tables (including the four secondary slots). Nevertheless the pre-match compositor outputs the historical strings. The present second report has RAM captures at 3840, 5070 and 10620, but **no literal BOSNIA / RUSSIA / IRELAND / GERMANY** in their 2 MiB snapshots. This does not prove the pre-match source — screen may retain a pre-rendered glyph atlas or use another bank / transformed string. Don't assume the source based on stale original string offsets.

## Next capture which actually isolates the fault

Use v0.9.5 Test Game; take `Create Save State` in (1) national team selection with Bosnia and Cabo Verde (one for each, optional), **(2) the pre-match screen while the historical name and wrong flags are visible**, and (3) field entrance immediately when large flags appear. Save an Explorer ZIP once all states appear in the session folder. Then compare pixel tiles and pre-match VRAM across phases, and trace changes back to the specific GDC upload list. Avoid random MIPS breakpoints.

Portable local analysis artifact: `ISS26_v095_VRAM_Diagnostics.zip` includes read-only script `compare_savestates.py`, JSON differences and color-decoded flag tiles from both save states. No commercial BIN/CUE is in that report.
