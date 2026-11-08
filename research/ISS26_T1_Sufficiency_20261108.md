# ISS26 3-Test Recorder — Session T1 evidence and decision (2026-11-08)

## Source artifacts
User-supplied files: `ISS26_3Test_20261108_195104_{samples.csv,writers.csv,markers.csv,initial_RAM.bin,final_RAM.bin,manifest.txt}`. Target: original European PS1 game **SLES03321**, Germany–France, T1_normal (marker at frame 0). Main RAM snapshots are 2,097,152 bytes each.

## Validated coverage
- 5,128 consecutive frame samples (`vsync` 1–5128), **0 missing frames**; 179 CSV fields.
- **58,383** CPU write callbacks, **118 unique writer PCs**, **150 unique values in recorded RA**, between VSync 55 and 5127; 26 watched object-field slots. Write callbacks include values **before** store, as declared by recorder.
- 23 scene objects tracked (ball + 22 players) with original source-coordinate table `0x8007627C + index*0x38C`.
- Only one test condition, `T1_normal`; no alternative tactic, AI modification, intentional keeper ball control, or repeatability run in the submitted dataset.
- Ball X varies from **−12063 to +11540**, so both ends were visited. Kahn X **−13177 to −10517** (never near halfway x=0), Barthez X **10013 to 13185**. Closest planar Kahn/ball distance is about **2,134 field units**, and there are **0 frames** with Kahn less than 2,000 units from the ball. Barthez was within 2,000 units in **266 frames** (possible proxy scenes, not proof of ball possession).
- Two 2 MiB RAM snapshots differ at **154,918 addresses** (just 7.39% of whole RAM; not a full interframe delta trace).

## MIPS data path highlights
These are confirmed **store PCs** recorded in one or more earlier probes; inferred semantics do not prove AI decision policy:
- `0x80027288` state writer helper; `0x80027294` writes substate `+0x329`; `0x8002729C` writes 16-bit state `+0x320`.
- `0x800F7E54` calls that helper with candidate state `0x9A` for keepers (the frequent RA `0x800F7E5C` confirms call context). 1,926 Kahn and 1,829 Barthez writes of state `0x9A` (among samples).
- `0x8008A09C`, `0x80105E2C` also appear as caller return PCs for both keepers' state writes.
- Outfield state writers `0x80087044` (2,953 callbacks; GER_02/03/06/07) and `0x80087964` (1,735 callbacks) are distinct *write locations* from GK state helper. These demonstrate separate code paths but **do not establish a cooperative tactical controller**.
- Movement magnitude writer PCs include `0x80028188`, `0x80028154`, `0x80028164`, while heading writes include `0x800F7EC8`, `0x80029218`, etc. These need a semantic gate before any rewrite.

## Directly matched original disc image code (uncompressed)
Scanning the exact 2352-byte/sector Track 01 user image for **32-byte contiguous byte strings** from final RAM found:
| RAM address | raw Track 01 byte offset | ISO9660 file |
|---|---:|---|
| `0x80027288` | `0x28EF0` | `SLES_033.21;1` |
| `0x80028140` | `0x2A008` | `SLES_033.21;1` |
| `0x80087040` | `0x5C11E8` | `GAME.BIN;1` |
| `0x8008A080` | `0x5C4948` | `GAME.BIN;1` |
| `0x800F7E40` | `0x642C48` | `GAME.BIN;1` |
| `0x80105E20` | `0x652D68` | `GAME.BIN;1` |

Raw offsets are **physical 2352-byte CD sector offsets**, not ISO 2048-byte logical offsets. Any actual binary patch must modify data bytes and rebuild correct Mode2 Form1 sector ECC/EDC (or use a verified equivalent patch tool), and must be fully standalone against clean original Track 01.

## Engineering decision: YES to moving from investigation to prototype after ONE session

This one rich recording gives enough to **stop requesting generic investigative captures** and begin the first working code prototype + patch packaging using static MIPS disassembly and known byte locations, **without waiting for T2 and T3**.

**NO** to asserting that this one baseline proves or fully specifies all Neuer/4-4-3 SK behaviors. No direct observed Kahn possession, deliberate long-through-ball GK sweeps, patched match, tactical A/B comparison, or verified passing-cover team decision logic. Those require targeted implementation reasoning and **post-patch gameplay validation**, not necessarily two more prepatch data-gathering sessions.

The first patch must be accurately named **experimental** and claims limited to behaviors actually implemented and bench-/in-game-verified. An unverified generic speed/position edit must not be labeled Neuer AI or 4-4-3 SK. User strongly prioritizes no further testing loop.

## Next implementation work (offline first)
1. Disassemble GK callers near `0x800F7E54`, `0x8008A09C` and team handlers near `0x80087044`/`0x80087964`; identify policy and safety checks.
2. Locate spare executable space/code injection strategy; isolate effect to Germany Kahn and the associated CPU team, not human controls or other teams.
3. Build a reproducible self-contained PS1 patch from original Track 01, maintaining disc checksums and audio track layout.
4. Validate with local static binary checks; user gameplay **after** first artifact is released will reveal behavior/bugs. State absent behavior candidly.
