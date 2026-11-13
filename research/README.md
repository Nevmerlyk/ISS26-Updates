# ISS26 Academy Research Goals — data-only v1

Experimental research feed, not an AutoTest control task, game patch, Lua script or executable.
Not active on the main feed until its PR is merged.

## Contract

Academy reads https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/main/research/latest.json

- schemaVersion must be 1; revision must be positive and at most 100000.
- Up to 16 unique research_ identifiers, title up to 120 chars, description up to 480 chars.
- phase is one of prematch_banner, carried_banner, crowd_flags, hud.
- No arbitrary URLs, file paths, controller inputs, commands, Lua, HTTP endpoints or patch content.
- Import to Academy's existing ledger is idempotent and preserves terminal completed/failed history.
- Internet outages do not block gameplay; a validated local goal cache works offline.

## Evidence and reporting

After the Academy session is finalized, existing opt-in private Rookie report relay
can include ResearchGoals metadata: goal ID, revision, phase, candidate-event count,
verified screen/VRAM pair count, GPU trace count (maximum 3 each).
SourceConfirmed is always false in v1.

No screenshots, CPU/RAM/VRAM dumps, raw GPU traces, disk paths, credentials,
ROM data, game audio, hashes of user files or raw log lines are uploaded.
Raw session archives remain on the player's own computer.

Private reports require the user's existing explicit GitHub connection
with Issues read/write permission on Nevmerlyk/ISS26-Android.
No GitHub Actions or API key is needed for local passive observation.

IMPORTANT: a screen candidate never proves texture provenance, scene identity,
or correctness of artwork. No remote research goal executes a script,
controls Rookie, changes a PS1 image, installs or publishes a patch.
