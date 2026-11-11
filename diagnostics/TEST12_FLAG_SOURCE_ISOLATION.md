# ISS26 — Test12: locate ceremony, spectator and HUD flag sources

**Status:** diagnostic design + read-only VRAM phase analyzer, **not a game patch**.
**Reference:** user PCSX-Redux screenshots of Bosnia vs Cabo Verde at Key Square Stadium, acquired after Test11.

## Correct terminology and new screenshot evidence

1. **National selection flag**: compact team-selection sprite (historically 24×16 slot, about 20×16 art).
2. **Prematch banner**: large graphic next to each team name on the stadium introduction screen. Names already visibly display **Bosnia** and **Cabo**.
3. **Ceremonial / player-carried flag**: large *physical banner carried onto the field by players*. The multicolor oval and distorted Cabo stripes in user screenshots are **damaged cloth graphics**, **not pitch decals or painted grass**.
4. **Spectator flags**: small flags actively waved by supporters in the stadium stands, visible in separate rows of spectator sprites.
5. **In-match HUD icon**: small team sprite next to 0–0. Bosnia has a colored icon; Cabo's HUD entry appears incomplete.

The user’s **Test11** screenshots showed the large defects still present when 63 GDC-associated sector patches were removed from Test10. **This refutes the narrow idea that those 63 modified sectors alone cause the defect, but does NOT establish that GDC uploads are never involved**. An unchanged flag can also originate from a later write, a reused CLUT, a texture-page mismatch or a common team/style mapping.

## Suspects to investigate (hypotheses, not established ownership)

| Path/resource | Suspected output | What would prove it |
|---|---|---|
| `DATSEL` / `DATSEL3` 64×28 indexed 4bpp uploads | large prematch, possibly carried banners | **GPU draw primitive** samples this VRAM cell (tpage+UV+CLUT), and load timeline identifies actual writer |
| `GDC_*.BIN` uploads, scene-specific stadium assets | on-field ceremony or waved spectator flags | tagged GPU upload and primitive draw during ceremony/crowd phase; Test11 sector rollback does not by itself prove it |
| `DAT2D` national CLUT and other palette uploads | wrong colors/transparent regions across multiple screens | source CLUT bytes, final VRAM row and sampled CLUT ID confirmed in actual draw |
| Unknown tiny 24×16/24×8 sprite atlases | team selection and match HUD | actual GPU tpage+UV+CLUT of the small HUD flag compared to a Master League nationality icon |
| Team slot/style routing (Bosnia mapped from Russia, Cabo Verde from Ireland) | multiple incorrect flag systems | verified RAM/team index and drawn flag style mapping at each distinct stage |

**Do not infer that flags waved by the crowd must share the carried-flag texture.** Their artwork may look similar but the rendering path is unverified.

## Three high-information checks — one Test11 run

**Setup:** use the already published **Test11** with **Test Game** and a **fresh emulation boot**. Pick **Bosnia vs Cabo Verde** at **Key Square Stadium**. Avoid Save States that retain Test10 VRAM. Do not patch or write to VRAM for this diagnostic.

1. **Prematch → player-carried banner**: capture a full screenshot and **raw VRAM** at both moments. While the prematch banner is actually visible, run `Capture-ISS26-Test12.ps1 -Phase prematch_banner`; while the players physically carry the cloth on screen, run `-Phase carried_banner`. Retain any GPU `.gpd` trace if available. Check changes in historical 64×28 indexed flag tiles and CLUT, but do not claim draw ownership before decoding GPU commands.
2. **Player-carried banner → spectator waving flags**: when fans clearly wave their own small flags in the crowd, capture another screenshot and run `-Phase crowd_flags`. Compare changed 16×16 VRAM-word cells and CLUT/styling with the preceding ceremonial capture. If the fans appear to wave legacy tricolors, treat that as an observation until exact sprite/slot mapping is established.
3. **Waving supporters → match HUD**: at 0:00 after kickoff, screenshot the scoreline flag icons and run `-Phase hud`. Contrast the small HUD sprite (~24×8 class) with selection icons (~24×16 class) and known Master League nationality flags. A visual match does not by itself establish texture memory ownership; UV/CLUT tracing is required.

For a clean control after the first pass, use one unchanged team such as **Denmark** at the same stadium. Do not request repeated full Test08/Test09 sessions unless the recorded GPU primitive data leaves an unresolved A/B question.

### How to capture with the EXISTING stable launcher 0.8.6

Academy v0.8.6 intentionally shows only **Practice**, **Rookie**, **Progress** tabs. The old `Flag Debug / VRAM` and `Crash Reports` buttons still exist in source code but **are NOT in the visible UI**. Do not tell the operator to look for them.

Instead use the small [Capture-ISS26-Test12.ps1](../tools/Capture-ISS26-Test12.ps1) helper. It writes an operator-chosen phase into the already existing Test Game `calibrator.request` handler, which captures **RAM + complete VRAM + screen** on the next Vsync via the bundled PCSX-Redux Lua driver. No new launcher/APK or Web Server is required. It never alters GPU memory, original BIN/CUE, saves or the game patch.

1. Start **Test Game** with **Test11** as a normal interactive game; open Academy → **Progress** → **Открыть текущую сессию**, if you want to confirm the chosen session directory.
2. Download the `.ps1` helper. In PowerShell, open the folder where you saved the script. The default installation path is `D:\ISS 26` (override with `-GameRoot`).
3. At each ACTUAL visual moment, run one of:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase prematch_banner
powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase carried_banner
powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase crowd_flags
powershell -NoProfile -ExecutionPolicy Bypass -File .\Capture-ISS26-Test12.ps1 -Phase hud
```

Run **only one command at the corresponding stage**; leave the game running for at least one further frame. Each command is a separate operator request, not a timed screenshot classifier. The resulting `.vram` filename begins with `cal_test12_<observed-phase>_<nonce>_<frame>`. The helper refuses to overwrite a pending request.
4. At the end, in Academy → **Progress** select **Экспортировать ZIP Rookie (с памятью и сессией)**. Upload only the resulting ZIP to the conversation. The archive contains captured RAM/VRAM/screen but no original game BIN/CUE or BIOS.

### Offline analysis

With the helper, phase labels are embedded directly into snapshot filenames, so **no manual JSON manifest is needed**. Run:

```powershell
python tools/analyze_flag_test12_phases.py "ISS26_Academy_....zip" --output test12.json
```

Optionally, legacy captures from the prior hidden Flag AutoTest buttons can be classified with `--labels test12-labels.json`, but this is unnecessary for the new operator-tagged helper.

The analyzer safely reads nested Academy ZIPs, reports changed historical 64×28 flag styles, 54 CLUT cells and candidate 16×16 VRAM-word regions, and inventories GPU `.gpd` files **without falsely claiming it decodes GPU draw primitives**. Output contains hashes, coordinates and counters, not copied ROM or RAM content. The phase comes only from the operator request, never from guessed screen content.

## Decision matrix after Test12

- **Same large flag UV/CLUT/texture coordinates in prematch and ceremony** → fix that authoritative source/style mapping first; validate on both screens, then handle crowd/HUD separately.
- **Different primitives or texture coordinates in ceremony and stands** → independent crowd resource/animation path; do not repaint `DATSEL` and expect fans to change.
- **VRAM texture indices match intended artwork, but frame is still corrupted** → prioritize real GPU primitive UV/tpage, CLUT, transparency and ordering, not another blind 4bpp repaint.
- **VRAM corruption appears only after an upload** → locate final writer by comparing adjacent captures and GPD traces, then map to source file. A changed tile alone does not prove the last writer.
- **Team identifier maps to legacy national ID across screens** → identify the exact team/style lookup tables; never broadly replace national names or shared styles.

## Requirements for any actual Test12 .iss26p

**No new art patch is authorized by these screenshots alone.** After a decisive GPU trace, change only verified pixels/lookup bytes needed for the specific subsystem, preserve the 17 updated prematch-name groups and existing small flags, rebuild as a **standalone patch against the clean European Track01** with sector source SHA guards and Mode2 EDC/ECC. Keep Play Game stable game patch **v0.9.4** unchanged. Do not modify Academy/Rookie learning or original user BIN/CUE/saves.

## Diagnostic acceptance criteria

- Clear full-screen context for **prematch**, **ceremony**, **crowd waving** and **HUD** phases.
- At least one pair of real temporally adjacent GPU/VRAM captures and any GPD traces; if absent, label provenance **unknown**, do not claim resource discovery.
- An explicit classification for each of the five flag representations: **verified source**, **plausible candidate**, or **unresolved**.
- No stability promotion before actual screenshots and controlled in-game comparison show correction without regressions.
