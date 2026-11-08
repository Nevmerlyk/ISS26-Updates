# v0.9.5 rebuild — verified original ISO layout (2026-11-08)

This is an engineering inventory, **not** a release or proof of correct flags.

Clean European Track01 SHA-256: `D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44`.
Raw sector size 2352, Mode2 Form1 user payload begins at +24 bytes, 2048 bytes per sector.

ISO9660 Primary Volume Descriptor at sector 16; root directory record points to a standard directory tree. The provided Track01 directory contains 278 file/directory entries.

Verified native file regions:
- `ENDING.BIN;1` begins at LBA 430; original `BRAZIL`, `RUSSIA`, `UKRAINE`, `FRANCE` are readable near physical offset `0xF7588` etc.
- `SELECT.BIN;1` begins at LBA 850; a second independent readable names table appears at physical offset `0x1E9094` (`BRAZIL`) and `0x1E9104` (`RUSSIA`).
- Other original game resources include `SELECT2.BIN` through `SELECTC.BIN`, `SELFORM.BIN`, `GAME.BIN`, and graphical resources under `BIN/`. These may use encoded/packed naming or atlas data.

The initial transport saved in branch `release/v095-flags-rebuild` still has only part_00 through part_25, last commit claims 26/30. It is not an independently verifiable complete patch. `staging/v0.9.5/STATUS.md` further records uncorrected atlas/flag mapping.

## Strict scope
- Update 54 national-team names and flags across all screens; include short and long labels and three flag sprite sizes.
- Do NOT change world map country highlighting or country geometry.
- Preserve 24 clubs, player data, controller setup, other art, and all CD audio tracks 02–12.
- Produce only an independent clean-original `.iss26p` patch, with full sector hashes and reconstructed Track01 SHA-256 verification.
- Do not switch `latest.json` until the entire artifact and in-game visuals pass.

Need to reconstruct complete graphic re-packing and enumerate all name tables. No v0.9.5 release has been made.
