# ISS26 Universal Tool — separate self-update channel

The Windows application checks `https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/main/universal-tool/latest.json` via its own `updater.py`. **This is not the game patch feed** in repository root `latest.json`.

## Current deployment

Publishing workflow: `.github/workflows/publish-universal-tool.yml`. It is intentionally gated: the entire `app/` update ZIP is reconstructed from UTF-8 base64 files under `universal-tool/staging/part_*.b64` only when `universal-tool/staging/ready.json` exists. It checks byte count and SHA-256, verifies ZIP contents, publishes a GitHub Release, verifies the uploaded asset, and finally updates the standalone tool feed.

Prepared release:
- Product: `ISS26-Universal-Tool`
- Version: `1.2.0`
- Tag: `universal-tool-v1.2.0`
- ZIP name: `ISS26_Universal_Tool_update_1.2.0.zip`
- ZIP size: `46389` bytes
- SHA-256: `A93A5F7873C6EA33FE7ECFE97F2E3ED4254663DB830980A7888280B0FC2EE482`

The update ZIP is already embedded in the Windows distribution under `dist/`; it contains only `app/` files. **Do not create `latest.json` before the GitHub release asset is present and independently verified.** An empty feed or a dangling URL would break update checks for installed clients.

The app updater checks for updates on startup and installs only after the user clicks confirmation. BIN/CUE are never included in an update.

## Completing publication

Stage 4 base64 parts of exactly 16,000, 16,000, 16,000, and 13,852 characters (total 61,852); commit `ready.json` with `{"product":"ISS26-Universal-Tool","version":"1.2.0","partCount":4,"sizeBytes":46389,"sha256":"A93A5F7873C6EA33FE7ECFE97F2E3ED4254663DB830980A7888280B0FC2EE482"}` only after staging every part. The release workflow then publishes and activates the feed if GitHub Actions quota permits.

Alternatively, upload the pinned ZIP as a GitHub Release asset manually and only then create the feed with the exact release URL and checksum. Do not edit the game `latest.json`.
