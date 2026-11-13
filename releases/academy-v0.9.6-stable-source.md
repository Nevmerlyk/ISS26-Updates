# ISS26 Academy + Rookie v0.9.6 — stable source freeze

- Stable source repository: private `Nevmerlyk/ISS26-Android`
- Frozen source branch: `stable/academy-v0.9.6-source`
- Frozen commit: `f5b6224cb13bfe6f3975a6f0c2230dc815b94148`
- Launcher version: `0.9.6`
- Game patch version: unchanged, `0.9.4`
- Source designation: stable by project owner's request.
- **Public binary release status: not yet published.** Publication is conditional on a passing .NET 8 portable regression, Python private-triage tests, verified Windows PE/ZIP and remote GitHub release SHA256.
- Stable launcher feed `launcher/latest.json` remains at `0.9.4` until a verified `launcher-v0.9.6` release ZIP exists. Do not edit it manually.

## Changes

Rookie now has 34 data-only menu-screen theory entries, a five-minute wall-clock practical exam, ten navigation trials per distinct screen, no global press limit, source-based cancel/backtrack attempts and a recorded visual menu graph. Academy provides a live clock and visible controller **decision explanations**. Rookie's result is derived from learned visual transition and independent pitch/HUD/VRAM evidence, never an automatic PASS.

Every completed Test Game, AutoTest or Rookie Game queues and attempts immediate **opt-in** delivery of an allowlisted private Issue report. Failed uploads remain queued. The existing hourly review agent is not the upload mechanism.

## One-command promotion on the owner's Windows PC

Download these two PowerShell files from this repository into **the same folder**:

1. [Build-ISS26-Academy-v096-Stable-Local.ps1](../tools/Build-ISS26-Academy-v096-Stable-Local.ps1)
2. [Release-ISS26-Academy-v096-Stable-Local.ps1](../tools/Release-ISS26-Academy-v096-Stable-Local.ps1)

From that folder:

```powershell
pwsh -NoProfile -File .\Release-ISS26-Academy-v096-Stable-Local.ps1
```

Requires: Windows, PowerShell 7, Git, GitHub CLI authenticated to both repositories, .NET SDK 8, Python 3. The release script runs the SHA-pinned builder and tests, creates `launcher-v0.9.6` in `ISS26-Updates`, verifies the release ZIP, and promotes **only** `launcher/latest.json`. The commercial PS1 game is not embedded and `stable/latest.json` (the game patch feed) must remain byte-for-byte untouched.

If any build or promotion step fails, the script stops without manually changing the stable launcher feed. No claims of actual gameplay/exam success are made until real session captures confirm them.

## Single-file publisher (easier)

The [ISS26-Academy-v096-Stable-OneClick.ps1](../tools/ISS26-Academy-v096-Stable-OneClick.ps1) bootstrap downloads both **immutable commit-pinned** publisher scripts and invokes the release gate. It does not upload game assets and stops if the pinned private source fails a build or regression test.

Windows PowerShell command from the directory containing the downloaded bootstrap:

```powershell
pwsh -NoProfile -File .\ISS26-Academy-v096-Stable-OneClick.ps1
```

GitHub Actions [public PowerShell syntax/source-pin validation](https://github.com/Nevmerlyk/ISS26-Updates/actions/runs/43424935629) passed, but **that job did not compile the private .NET source or publish a Windows binary**. The actual Windows builder is the remaining release gate.
