# ISS26 — Public Game Patch Updates

Public **read-only update feed** for the ISS26 Windows launcher, based on the original European **ISS Pro Evolution 2** PlayStation disc (12-track BIN/CUE).

**Current status:** [v0.5.0 Preview](https://github.com/Nevmerlyk/ISS26-Updates/releases/tag/v0.5.0-preview) is published and active in [latest.json](latest.json). This is a names-only, file-verified *prerelease*; its in-game behavior still needs testing. It is not a finished season 2026/27 mod.

The public feed URL is:

```text
https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/main/latest.json
```

ISS26 now checks this public feed, downloads the independent `.iss26p` patch, verifies hashes, and creates a patched **copy** of Track 01 from the user's own clean original BIN. Track 02–12 audio files, the original CUE, controllers and emulator saves are not modified. Old ISS26-generated files are removed only after the update succeeds.

The private source-code repo **ISS26-Android** remains separate. This public repository contains release metadata, supporting documentation, and small independently applicable XOR-sector patch differences. It must **never** contain full game images, CD Audio, proprietary firmware, or copyrighted music.

## Publishing rules

- Every patch must work on the **clean original European image** without applying earlier versions.
- Publish a verified patch file over public HTTPS **before** changing the manifest.
- Match the manifest's SHA-256 of the source BIN, downloaded patch, and resulting BIN.
- Test game boot, visible team names and player data, graphics, and CD audio before marking a release stable. Preview patches may be published for supervised gameplay tests, with limitations declared.
- Do not promote an unfinished internal prototype such as speculative `v0.9` as the latest release.
- See [release instructions](releases/README.md).

**Important:** the automatic update feature handles *game-content patches*, not ISS26.exe or the integrated PS1 emulator. Updating the launcher itself is a separate feature.
