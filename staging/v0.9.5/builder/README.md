# ISS26 v0.9.5 — independent flags-only patch builder

This **is not the game's stable v0.9.5 release**. It is a fail-closed
builder for a clean-original, one-file `.iss26p` update. It cannot call the
result complete until 17 national art uploads and the in-game screen evidence
have been supplied and verified.

## Input / output

Input from the project owner:
1. **Clean European ISS Pro Evolution 2 Track 01 BIN** (SLES-03321)
   SHA256 `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`,
   size 496,156,752 bytes. The clean game and 11 audio tracks are NEVER uploaded
   to GitHub or included in this source package.
2. Official `ISS26_0.9.4_preview.iss26p`, SHA256
   `70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE`.
   This is automatically downloaded from the ISS26 Updates release when missing.
3. **Audited flags-only plan JSON** describing all 17 countries, their national
   CLUTs and mappings, and validated GPU upload commands for the screens that
   load those flags. The builder deliberately will not invent this data.

Output:
- `ISS26_0.9.5_flags_only.iss26p` — independent clean-original XOR records,
  not an incremental overlay on a 0.9.4 installation;
- `ISS26_0.9.5_flags_only.verification.json` — the clean, baseline, patch,
  reconstructed Track01 SHA256, sector count, touched resources and flag
  coverage. Until real game-screen QA passes, **this remains a candidate**.

## Build on Windows

Install Python 3.10+ (no third-party modules needed to run the builder).
From the unpacked builder folder:

```powershell
py -3 build_v095.py --original "D:\ISS 26\ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin" --base-patch "D:\ISS 26\ISS26_0.9.4_preview.iss26p" --plan "verified-flag-plan.json" --output "D:\ISS 26\ISS26_0.9.5_flags_only.iss26p"
```

Omit `--base-patch` to download the exact pinned official v0.9.4 patch.
No source BIN is modified or copied to GitHub. Do not supply a game disc
already patched with 0.9.4: the input must be **clean**.

## Audited plan schema v1

```json
{
  "schema_version":1,
  "version":"0.9.5",
  "flags_only":true,
  "base_patch_sha256":"70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE",
  "confirmed_contexts":["selection","prematch","stadium","match_hud","edit_mode"],
  "runtime_evidence":"PCSX-Redux actual captures / IDs",
  "styles":{"bosnia":10},
  "palettes":{"bosnia":[0,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767,32767]},
  "streams":[{
    "resource":"BIN/DATSEL3.BIN",
    "context":"prematch",
    "record_offset":1234,
    "load_base":2148335616,
    "allocated_end":2345,
    "decoded_before_sha256":"64 hexadecimal digits",
    "decoded_after_sha256":"64 hexadecimal digits",
    "decoded_after_b64":"base64 of entire decoded GPU upload",
    "styles":[10],
    "countries":["bosnia"]
  }]
}
```

The example above is **structurally illustrative and deliberately incomplete**:
it cannot build a patch. An actual plan must provide exact **17/17**
`styles` and `palettes`, audited art inputs, and verified upload records
from all relevant screens and all stadium `GDC_*.BIN` resources. Every
upload edit's decoded byte diff must be strictly inside the nominated
64×28 national-flag VRAM tiles. Small-flag/HUD variants require a
dedicated validated plan and cannot be falsely covered by a big-flag tile.

### Additional protected color entries

A new multiplexed style sometimes needs a revised CLUT for an unchanged nation.
These changes are permitted only for protected indices
`12`, `18`, `23`, `29`, and only when before/after **rendered
image** SHA256s match. Add:

```json
"preserved_palettes": [
  {
    "index":12,
    "palette":[0,/* exact fifteen existing opaque color words */],
    "render_before_sha256":"...",
    "render_after_sha256":"..."
  }
]
```

Never silently recolor the other 37 nations, club badges, player uniforms,
scoreboards or player records.

## Safety invariants enforced by the builder

- Rejects unexpected original SHA/size and published v0.9.4 patch SHA.
- Independently checks all 1,412 original-sector SHA256 records before edits.
- Reconstructs v0.9.4 as a **virtual disc**; compares the result Track01 SHA
  to the published v0.9.4 result SHA before making changes.
- Reads ISO9660 resources through mixed Mode2 Form1 (2048 bytes) / Form2
  (2324 bytes) user extents; no assumed 2048-only GDC tail.
- Only allows flags-related graphics resources, 17 national style-table
  positions and national CLUTs. No team names or audio are edited.
- Verifies decoded compressed upload preimage and replacement SHA256; WE
  compression is checked by exact reverse decoding and bounded allocation.
- Changes **only declared flag rectangles** in the graphical uploads.
- Recalculates Mode2 Form1 EDC+ECC and Mode2 Form2 EDC, preserves all headers
  outside the modified graphic sectors.
- Refuses overwriting the clean original or baseline patch.
- Exports sorted, deduplicated SHA256-guarded clean-original XOR sectors,
  verifies the resulting file and computes the final Track01 SHA256.
- Never updates public `stable/latest.json` automatically.

## Independent CI tests

```
python -m unittest discover -s builder -p 'test_*.py' -v
python -m unittest discover -s flags_source -p 'test_*.py' -v
```

The first suite uses a **synthetic** PlayStation-style ISO with Form1,
Form2, exact EDC/ECC and one national 64×28 compressed upload. It tests
clean-original patch roundtrip, corrupted inputs, non-flag pixel rejection
and cross-sector CLUTs without any copyrighted game image.

## Release status

The assembly/patch integrity engine can be tested without the user's
commercial disc. The 17-country **verified GPU upload plan is not yet
complete**, including the Master League → in-match small-flag mapping.
Therefore the builder does **not** make a stable game v0.9.5 by itself.
Stable Play Game remains v0.9.4 until all actual in-game screens are approved.
