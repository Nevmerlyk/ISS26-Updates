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

1. **Prematch → player-carried banner**: capture a full screenshot and **raw VRAM** at both moments. In PCSX-Redux Academy/Explorer, use **Flag AutoTest → 2. Перед матчем** for the first; **3. Флаги на поле** for the second. Note exactly when the cloth banner is visible. Retain any GPU `.gpd` trace if the runtime produces one. Determine whether original 64×28 indexed tiles at style 10/1 and national CLUT cells change, *but do not infer draw ownership without decoding GPU commands*.
2. **Player-carried banner → spectator waving flags**: when the stadium camera clearly shows *waving supporters' flags*, take a separate screenshot and use **3. Флаги на поле** again. The launcher currently labels both as `field`; distinguish them in the **manual manifest** below. Compare candidate 16×16-VRAM-word cells, historical flag style tiles and CLUTs. If fans display old tricolors, keep this as a visual observation pending an actual sprite/slot trace. No need to play a full new match.
3. **Waving supporters → match HUD**: at 0:00 after kickoff, screenshot the team icons next to the score and perform another **3. Флаги на поле** capture. Contrast apparent HUD sprite size (~24×8 class) with selection icons (~24×16) and with the known Master League nationality flags. A direct match is *not* a guarantee of common memory ownership; require UV/CLUT tracing to establish it.

For a clean control after the first pass, use one unchanged team such as **Denmark** at the same stadium. Do not request repeated full Test08/Test09 sessions unless the recorded GPU primitive data leaves an unresolved A/B question.

### Important instrumentation detail

The existing v0.8.6 PCSX-Redux Lua driver accepts manual **`selection`**, **`prematch`** and **`field`** capture requests, not dedicated `ceremony`, `crowd` or `hud` labels. Reuse the `field` button multiple times during different *visually observed* phases, then record the matching filenames separately. **Frame timestamps alone cannot identify a scene**. The optional timed AutoTest r1 makes unlabelled captures and cannot be treated as automatic menu detection.

## Offline analysis, after saving the Academy ZIP

Save **Crash Reports → Сохранить отчёт ZIP**, then choose the matching raw VRAM filenames from the archive. Create `test12-labels.json` next to the ZIP, matching the actual filenames verbatim (the illustrative names below must be replaced):

```json
{
  "schemaVersion": 1,
  "captures": [
    {"snapshot": "flag_prematch_00001200.vram", "phase": "prematch_banner", "team": "Bosnia vs Cabo Verde"},
    {"snapshot": "flag_field_00001700.vram", "phase": "carried_banner", "team": "Bosnia vs Cabo Verde"},
    {"snapshot": "flag_field_00001900.vram", "phase": "crowd_flags", "team": "Bosnia vs Cabo Verde"},
    {"snapshot": "flag_field_00002400.vram", "phase": "hud", "team": "Bosnia vs Cabo Verde"}
  ]
}
```

Run locally with Python 3.10+:

```powershell
python tools/analyze_flag_test12_phases.py "ISS26_Academy_....zip" --labels test12-labels.json --output test12.json
```

The program treats the user's observed phase as an **external label**, safely reads nested Academy ZIPs, and reports changed historical 64×28 style tiles, 54 CLUT regions and candidate 16×16 VRAM-word cells. It lists `.gpd` dumps **without pretending to decode draw primitives**. Report contains only hashes, coordinates, names and changed-cell counts, not original game or saved RAM.

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
