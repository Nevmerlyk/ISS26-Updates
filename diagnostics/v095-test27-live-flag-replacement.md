# Test27 — reversible changed-graphics trial in PCSX-Redux

## Real user evidence and correction

The prior annotated report confused Cape Verde's green/red difference panel
with rendered artwork. The actual Cape Verde source preview is dark, with
light horizontal strips and a ring of red/dark points. It has some intended
flag geometry; wrong palette/index assignment is a plausible cause. Style1
copies exactly to the stage; Bosnia style55 shows unrelated crest-like art
and its lower 12 rows are blanked. The source artwork/CLUT is not yet
accepted as correct for either national flag.

## Actual temporary replacement

This implementation **changes emulated VRAM**, rather than producing
another read-only analysis. It writes the two generated original 64x28
4bpp national flags (896 bytes each) to the two stage tiles and their
new BGR555 CLUTs (32 bytes each) to the selected palette addresses.
It does not write atlas source tiles, game disc, executable code, RAM,
save states, memory cards or update feeds.

The engine requires emulation paused and exact SHA256 matches for all
six known source atlas, staging and CLUT slices from the owner's
Test25 Cape Verde home vs Bosnia away session, frame 5468. On mismatch
it refuses to write. Total allowed writes: 1856 bytes in four rectangles.
It checks that the entire paused VRAM readback agrees with the intended
change and backs up the old rectangles locally before writing.
Rollback verifies current rectangles still contain the expected before
or after data. On failure with unverified rollback, restart the test game
without saving a state.

This is an isolated **runtime visual trial**, not a clean-original
ISS26X01, not a fix of the original staging writer, and not an installable
or stable game patch. Shared CLUT consumers may still look different
while the temporary test is applied, and the game may overwrite the
buffers again after resuming. Restart clears the experimental override.

## How to try it

1. Use the same Test25 game and Cape Verde home / Bosnia away.
2. At the stadium introduction with the visible faulty flags, pause
   PCSX-Redux. Its documented HTTP endpoint supports VRAM uploads.
   The server may listen on all interfaces; only enable it on a trusted
   isolated or firewall-restricted computer/network, never expose port
   8080 to the internet. Disable it after testing. The Python client
   connects exclusively to 127.0.0.1:8080 with no proxies or redirects.
3. Run the standalone CMD (requires Python 3.10+). It downloads the
   two immutable source files from the green CI-tested commit
   c7f45e94402526b4189f9f2fab9e823c16793532. It checks the exact state first
   and requests affirmative Y confirmation before making temporary writes.
4. Upon verified readback, resume and visually inspect the two flags,
   carried banners and other nearby textures; record whether the game
   overwrites the tiles. Do not save a state containing the experiment.
   Restart the test game to discard it.

The API is documented at https://pcsx-redux.consoledev.net/web_server/.
The actual emulator and its HTTP endpoint were not accessible to this
development environment. No live frame was edited here.

## Tests and next gate

Seven synthetic tests exercise actual replacement payloads in a fake
VRAM client, paused and identity guards, all-other-byte preservation,
bad-state refusal, local backup protection, and rollback on partial
failure. Public CI succeeded:
https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43630951833.

No user-original BIN editing was possible (container ClientError).
The visual experiment must still be run in real PCSX-Redux. Successful
runtime appearance would justify a permanent isolated artwork and
staging-writer fix in a standalone patch for the clean European disc.
Stable game 0.9.4 and Test13 feed remain untouched.
