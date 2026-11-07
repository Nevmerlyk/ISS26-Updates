# ISS26 Windows launcher self-updates

Public HTTPS feed for **ISS26.exe** and its standalone update helper,
separate from PS1 game-content patches in the repository root's `latest.json`.

Manifest:
`https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/main/launcher/latest.json`

Starting with **ISS26 Windows v0.3.0**, the headless launcher checks this feed automatically on every double-click and installs a newer verified release without displaying dialogs or waiting for user confirmation. The previous v0.2.0 frontend had an interactive confirmation UI. It downloads
`ISS26-LauncherUpdate.zip` from GitHub Releases, verifies SHA-256 of the ZIP
and both EXE files, and launches a staging helper to replace them **after
the old ISS26.exe exits**. The helper makes rollback backups and then starts
the new ISS26.exe.

**No update is yet available:** `latest` is `null`. Install the v0.3.0 headless bootstrap once from the private source repository's GitHub Actions artifact. Older v0.2.0 installs cannot switch to headless behavior until they are replaced.

## Publishing a new launcher version

1. Change the version **in both** `windows/ISS26.Launcher/ISS26.Launcher.csproj`
   and `windows/ISS26.Updater/ISS26.Updater.csproj` in the source repo
   `Nevmerlyk/ISS26-Android` (for example, 0.2.1).
2. Build **Build ISS26 Windows integrated PS1** in GitHub Actions. The workflow
   produces `ISS26-Windows-LauncherUpdate` with exactly
   `ISS26.exe`, `ISS26.Updater.exe` inside a ZIP, plus
   a **candidate** JSON manifest with generated SHA-256 hashes.
3. Upload the inner `ISS26-LauncherUpdate.zip` to a *public GitHub Release*
   in this repository with matching tag, for example `launcher-v0.2.1`.
   Do **not** upload proprietary game, CD Audio, runtime modifications or BIOS.
4. Verify that the public download URL works anonymously and hashes match.
   Then copy the generated candidate JSON to `launcher/latest.json`.
5. Test download, replacement, restart and game launch in an ordinary user-writable
   directory. Some protected locations such as Program Files may require a
   traditional installer with elevated permissions.

Format:
```json
{
  "schemaVersion": 1,
  "latest": {
    "version": "0.2.1",
    "zipUrl": "https://github.com/Nevmerlyk/ISS26-Updates/releases/download/launcher-v0.2.1/ISS26-LauncherUpdate.zip",
    "zipSha256": "64 hex characters",
    "launcherSha256": "64 hex characters",
    "updaterSha256": "64 hex characters",
    "notes": "What's new"
  }
}
```

The ZIP contains **only two files at ZIP root**: `ISS26.exe` and
`ISS26.Updater.exe`. Runtime and original PS1 image are not overwritten.
The helper runs from staging and replaces its installed copy and launcher with
rollback. Existing settings, game saves and game-content update files live in
`%LOCALAPPDATA%/ISS26` and are not changed. Full bootstrap distributions
still include `runtime/retroarch`.

## Security / known boundaries

Hashes protect integrity relative to this GitHub-published manifest; no
code-signing certificate is presently configured. Only release download URLs
under `github.com/Nevmerlyk/ISS26-Updates/releases/download/` are accepted.
Keep write access to this repository restricted and use signed releases if
shipping broadly. The v0.3.0 mechanism installs a verified, published launcher update without interaction when the user starts ISS26.exe. It does not run while the app is closed; there is no resident background service. No update is announced until a real verified release exists.
