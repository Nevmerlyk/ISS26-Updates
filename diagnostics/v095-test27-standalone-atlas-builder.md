# Test27: experimental independent atlas source-art compiler

## What was implemented

This is a **builder for a real local game patch**, not a new archive
inspection or a runtime VRAM-only override. No real game patch has yet
been produced in this development environment.

The new Python compiler accepts:
- the exact user-owned clean EU original Track01 (SHA256 D9B483BD...);
- the official standalone Test25 patch (SHA256 85014C82...);
- the same existing Academy ZIP, solely to read the real captured CLUT;
  no new match or new archive report is required.

The compiler retains the existing Test25 changes and independent
clean-original sector guards. It seeks to replace two national artworks
in the two selection GPU resources and all 34 GDC resources, including
GDC_BN, **only if all of its source-safety checks pass**.

Before writing any patch, it verifies:
- all 1492 input patch record source hashes and applicable Form1 XOR parity;
- all five style maps, including exclusive national slots 0/style1
  and 30/style55, and protected club54/style10;
- unambiguous supported GPU lists and full, non-aliased kind-10
  upload rectangles covering both 64x28 cells;
- the real captured identical 32-byte CLUT, with safe distinct opaque
  colors for both proposed artworks. No original CLUT is changed.
- compression round-trip, unchanged resource byte size and unchanged
  GPU descriptor layout; only the intended decoded tile bytes may change;
- independent sector-XOR reproduction, regenerated Mode2 Form1 EDC/ECC
  and all unrelated prior patch records unchanged.

It fails closed if any actual source differs from these assumptions,
including unsupported resource list format, palette colors insufficient
to produce the intended graphics, stream capacity too small, or shared
style allocation. It does not select arbitrary candidate styles or move
unverified data. The 4 bonus national slots and other possible byte/UV
consumers are not yet proven to be isolated; a successfully built file is
therefore **experimental**, not appropriate for stable publication.

This is only the source-art half of the fix. It does **not** fix the
separate runtime clearing of the lower twelve rows of Bosnia's staging
buffer, prove all visual surfaces, or correct every national team. It does
not establish the runtime last writer by scanning static resources.

The corrected visual evidence from the actual user images stands:
Cape Verde's tile copies exactly but its colors are incorrect; Bosnia
contains non-national source artwork and a separate staging mask.

## Validation

Nine new synthetic Python tests cover both target subrect replacements,
variable-size LZ decoding/encoding, wrong source guard, shared style,
ambiguous coverage, insufficient stream capacity, no suitable palette,
new independent sector record and preservation of unrelated data.
The combined Test27 suite passed 50 tests:
https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43631655127

Actual owner-disc validation remains unavailable in this execution
environment (container ClientError). No playable TEST27 .iss26p is
claimed yet.

## Local build

Run `tools/Build-ISS26-Test27-StandaloneArt.cmd` on the owner's Windows PC.
It downloads the pinned checked source code and official Test25 patch;
by default it finds the original Track01 and prior ZIP in D:\ISS 26
(or accepts the ZIP dropped onto the CMD). It verifies input SHA256s.
No original files are uploaded or modified. It does not install anything.

On success the output folder contains:
`ISS26_Test_0.9.5_TEST27_SourceArt.iss26p` and a JSON build report.
On refusal it contains `Test27_Build.log` with the actual failed
precondition, not a fabricated result.

Game stable v0.9.4 and ordinary Test13 channel remain unchanged.
No test-feed or stable-feed publication is authorized.

## Compiler revision: avoid false palette and compression failures

The existing nearest-color assignment could reject a palette that had
a valid non-greedy one-to-one assignment. The revised compiler considers
all admissible opaque BGR555 colors together; it rejects duplicate
color values as well as duplicate palette slots and minimizes the summed
channel error within the existing maximum tolerance. It still **never
overwrites a shared CLUT**.

A second LZ token-cost search is available if the fast greedy compressed
stream is larger than the existing allocation. Both encoders use the
same game-format decoder for exact round-trip validation. The alternate
search is not claimed to be mathematically optimal, but can fit data
that the greedy encoder would reject. If neither fits, no relocation or
patch is emitted.

The local build log now reports both color mappings or failures, the
16 sampled BGR555 palette words, each supported GPU resource route and
compressed stream sizes/methods, and collects resource-level blockers
before sector composition. This is intended to replace repeated
one-error-at-a-time runs of the owner-local builder. It remains a real
source-art compiler when all inputs pass.

Four additional regression cases cover non-greedy distinct colors,
duplicate palette values, compact LZ boundaries/random input, and
capacity fallback. No actual original-disc build or in-game verification
has taken place: the execution environment still cannot read the
mounted clean BIN (ClientError). The same existing ZIP suffices; no
new test match is needed at this stage. Bosnia's runtime twelve-row
mask, actual final writer and all scene acceptance remain open.
