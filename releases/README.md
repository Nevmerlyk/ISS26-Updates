# ISS26 game patch releases

Place verified, independently applicable \`.iss26p\` **binary-difference**
patch files here or attach them to public GitHub Releases.

No full PS1 BIN/CUE, Sony BIOS, copyrighted music or emulator binaries
belong in this repository.

The Windows updater reads the root \`latest.json\` and expects:

\`\`\`json
{
  "schemaVersion": 1,
  "latest": {
    "version": "1.0.0",
    "patchUrl": "https://github.com/Nevmerlyk/ISS26-Updates/releases/download/1.0.0/ISS26-1.0.0.iss26p",
    "patchSha256": "<64 hex digits>",
    "baseSha256": "<64 hex digits of supported clean Track 01>",
    "resultSha256": "<64 hex digits of resulting modified Track 01>"
  }
}
\`\`\`

Only publish a release **after** testing it on the unmodified European
ISS Pro Evolution 2 12-track BIN/CUE and verifying all SHA-256 digests.
Each release must apply to the **clean original**, never to another mod.

Publish the .iss26p file first. Update \`latest.json\` only when the public
download URL works anonymously and all hashes match.

While no verified release exists, keep \`"latest": null\`. Do not guess
"v0.8" or "v0.9" labels from development discussion.
