# ISS26 — Flag GPU/VRAM AutoTest (active task r1)

**Current task:** `iss26-flags-gpu-provenance`, revision 1.
**Game:** Experimental `v0.9.5-flags-test1` via **Test Game / AutoTest**, not stable Play Game.
**Goal:** trace small national flag CLUT/texture coordinates and the GDC reupload that overwrites Bosnia's big flag. The tool will automatically collect **16 RAM+VRAM+screen captures and 10 short GPU dumps** on a six-minute schedule. Labels are timestamps, **not recognized screen names**.

## One run, user drives the menu

1. Start ISS26 Launcher → **AutoTest**. It downloads this task automatically. Choose the existing test CUE if a picker opens.
2. **Use the controller yourself** to dismiss the memory-card prompt and advance to Match Mode → Exhibition. The task does **not** issue blind controller taps.
3. Open the national team selection and highlight the problem tile. On older menus the names may still show **Russia** (the intended Bosnia slot) or **Ireland** (the intended Cabo Verde slot). Also select **Denmark** as an unchanged control. When the selection is visible, use Explorer **Flag AutoTest → 1. Выбор сборной: RAM + VRAM**.
4. Start the match and on the **pre-match name-and-flag screen** click **2. Перед матчем: RAM + VRAM**.
5. At kickoff, leave the game playing long enough to show the **small score HUD** and click **3. Флаги на поле: RAM + VRAM**.
6. Let the AutoTest run its captures and finish (18,000 emulated frames ≈ 6 minutes at 50 game FPS); or if unable, close the emulator so Explorer can save a partial ZIP.
7. Upload **only the ZIP** from `ISS26_Data\explorer\reports\ISS26_Explorer_*_autotest.zip` into the conversation. No original BIN/CUE, BIOS or full game image is required.

For second-source comparison, an optional **separate test session** can be used to navigate to Master League → Player Acquisition and show Salamic/Kapitonic/Balbarez (Bosnia) or Forest (Canada), plus save a manually labelled capture.

## What the report can and cannot prove

- Evidence: raw 1,048,576-byte GPU VRAM, screenshots with width/height metadata, RAM samples, GPU `.gpd` dumps if supported, and exact task capture progress.
- The analysis script `tools/analyze_flag_autotest_zip.py` produces `style_changes.csv`, `palette_changes.csv`, `summary.json` and small Bosnia/Cabo Verde pixel previews (PPM).
- A change to **style 10** between selection and stadium is evidence of graphics being overwritten, not proof of who initiated a draw. The `.gpd` primitives/CLUT and screenshot stage identification are required to identify the exact small HUD sprite.
- `kind=gpu` is a bounded capture. Where GPU dumping fails, raw VRAM and screenshots still exist and the failure is logged.
- First test only: this task **does not patch** the game, drive the AI, or guarantee that the player reached a specific screen. Do not label v0.9.5 stable from a script completion event.

## Developer next actions on receipt

1. Analyze the new report's complete time-ordered VRAM, screenshots, and available `.gpd`.
2. Correlate matching screen phases, 64×28 styles and 16-color palettes; isolate GDC overwrites.
3. Compare the tiny HUD icon with the already-working Master League national icon for Bosnia and Canada. Record texture page, UV range and CLUT ID *only if* actual GPU primitive evidence establishes it.
4. Produce corrected `DATSEL`, `DATSEL3`, all `GDC_*.BIN`, and separately verified 24×16/24×8 mini-flag patches; rebuild one clean-original, flags-only `.iss26p` with CD EDC/ECC.
5. Test in-game all affected screens before promoting Stable. `stable/latest.json` stays v0.9.4 meanwhile.
