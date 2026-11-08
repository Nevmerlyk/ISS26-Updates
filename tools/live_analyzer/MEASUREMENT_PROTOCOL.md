# ISS26 P0 — measurement protocol for experimental Kahn → Neuer AI

**Current stage:** Phase 1 only. We are not editing the game yet. Use **original European SLES03321**. The first prototype targets **Oliver Kahn under CPU control** in Germany; other GKs unaffected.

## Experimental configuration

- PCSX-Redux, debugger ON, CPU Interpreter, standard 2MB RAM, the clean original .cue.
- Germany vs France, **CPU vs CPU** (or explicitly document otherwise). Preserve game speed, match length and difficulty across tests.
- Turn on [ISS26 Live Analyzer v0.1](ISS26_LiveAnalyzer.lua) for position CSV + sampled RAM deltas before kickoff.
- Turn on [ISS26 AI Probe](ISS26_AI_Probe.lua) during a running match to log **the MIPS instruction addresses responsible for writing mini-map XY** for both GKs and ball.
- **Use snapshots and emulator states** (where reproducible). Record on-screen match clock, tactical setup, and scene in plain text (marks only track emulated Vsync relative to the start of probe).

## Stage A — verify writer addresses (first practical measurement)

1. Save `ISS26_AI_Probe.lua` into `%USERPROFILE%\ISS26\`.
2. With a match loaded, open `Debug → Lua → Show Lua Console` and run:

   ```lua
   dofile(os.getenv("USERPROFILE") .. "/ISS26/ISS26_AI_Probe.lua")
   ```
3. Resume the match briefly with **F5**. To check the probe, run `ISS26Probe.status()`; `writeEvents` and individual event counts should increase. The debugger must be ON.
4. Mark interesting changes (optional):

   ```lua
   ISS26Probe.mark("Germany long possession")
   ```

5. When finished, run `ISS26Probe.stop()`. Send the two new `*_writers.csv` and `*_markers.csv` files together with the corresponding `positions.csv` and RAM-deltas from the main analyzer.

The Probe is read-only: its hooks do **not** write game RAM, and logging can be slower than normal emulation. Stop it before resetting the emulator.

### Optional brief trace during a very specific episode

- Run `ISS26Probe.traceStart()` right before an interesting GK/ball event.
- Let the emulator advance only a *short* amount; run `ISS26Probe.traceStop()` promptly.
- Send the resulting `*_cpu_trace.bin` separately. CPU trace has an in-emulator limit of **32 million 32-byte records**; don't keep it enabled for a whole match.

## Stage B — find canonical gameplay state

With program counters from Stage A, inspect their assembly and callers in the debugger/Ghidra. These are currently **render packet writers**, not proven GK AI.
- Break/trace back to the source world-space X/Y and its data type.
- Determine the player entity table, current target position, velocity, ball possession and team direction.
- Distinguish GK-specific decision code from generic movement or graphics preparation.

## Stage C — compare actual CPU tactics

Capture separate cases, each with the same difficulty, teams and known formation:

| Test | Control | Interested behavior |
| --- | --- | --- |
| B1 | 4-3-3A / Normal / no strategy | baseline Kahn depth when own team attacks |
| B2 | 4-3-3A / Auto Offence | GK depth, support positions, defensive cover |
| B3 | 4-3-3A / CB Overlap | CB forward runs vs GK participation |
| B4 | long passes behind Germany defense | GK interception vs holding position |
| B5 | Germany passes back to Kahn | outgoing action choices (clear, pass, carry) |
| B6 | possession lost during high line | GK recovery + team defensive transition |

Document differences as measurements, not inferred guarantees about behavior.

## Stage D — pre-patch gate

No claims of implemented AI until code actually found. Minimum evidence:
- reproducible PC/call path for GK positioning and decision states,
- verified team AI tactical/receiver-selection logic or equivalent hook,
- available free code space or safe overlay strategy for PS1 MIPS instrumentation,
- ability to run test patch on clean original Track 01 with intact audio tracks and default controls,
- A/B reproducibility: normal Kahn, modified Kahn, other GK unaffected.

After this gate, the next deliverable is an **experimental standalone PS1 patch**, not just a high-level concept or visualized simulation. If some behavior proves blocked by the engine, report exact technical limitation and deliver only verified subfeatures with their scope stated.
