# FM26 to ISS26 attribute bridge (draft)

This utility converts **actual FM26 1–20 player attributes** into the 15 main
ISS Pro Evolution 2 (PS1) skills on the 12–19 scale.

It is independent of the game BIN/CUE; it prepares roster CSV tables for the
separate version-aware PS1 patch encoder. No stable patch is modified here.

## Inputs

- ISS_players_2026.csv — 1,804 first-team roster records (54 national teams,
  24 clubs, 4 bonus teams, 22 records per team).
- ISS_reserve_2026.csv — 279 additional roster records.
- all_players.csv — full raw player export from an actual FM26 save, containing
  the players' names and 1–20 skill columns.
- Optional aliases.csv — columns iss_name,fm26_name for spelling variants.

The user has not provided a full FM26 source CSV yet; this branch therefore
contains the importer but not claimed or fabricated FM26 ratings.

## Obtaining real FM26 data

Open-source fmsave (https://github.com/rhiever/fmsave) reads a saved
career and can export the entire player table to CSV.

Example, where you have FM26 and an existing career save:

    python -m pip install fmsave
    fmsave export "C:\path\to\career.fm" players --all -o all_players.csv

Alternatively use a tested FM26 CSV exporter with a custom view showing
all technical, mental, physical and GK attributes. A limited scouting export
will yield a limited number of matches.

Never use 1–99 scores found on fan websites as though they were raw
Football Manager 1–20 ratings. Some websites expressly publish derived
values rather than original game attributes.

## Run

Place the two original roster CSV files and your FM26 CSV in one folder:

    python tools/iss26_fm26_import.py --fm26 all_players.csv ^
      --players ISS_players_2026.csv ^
      --reserve ISS_reserve_2026.csv ^
      --fm26-version "FM26.2.0 my-save 2026-11-14" ^
      --outdir output

Produced files:

- output/ISS_players_2026_FM26_ISS26.csv
- output/ISS_reserve_2026_FM26_ISS26.csv
- output/FM26_unmatched.csv
- output/FM26_coverage.json

The original files are never overwritten. Each roster row gets up to fifteen
converted attributes and audit fields: matched FM name, FM UID, conversion
count, coverage status, source and version. Missing and ambiguous matches are
left blank, not substituted with generic ratings.

If an FM player appears both at club and national level, exact normalized
full-name matching uses the same original FM profile. Ambiguous identical
names are never joined automatically. An explicit aliases.csv reconciles
alternate English spellings if a name maps uniquely.

## Formula

ISS original range: 12–19. FM26 raw public attribute range: 1–20.

    ISS(x) = clamp(12 + floor((x - 1) * 7 / 19 + 0.5), 12, 19)

The formula preserves the endpoints. It reduces numerical resolution; several
FM26 scores may map to the same ISS rating.

For ISS properties that are not directly present in FM26, the importer uses
explicit weighted skill combinations. Example:

- ISS Offense = 55% Off the Ball + 25% Anticipation + 20% Finishing
- ISS Defense = 40% Positioning + 30% Marking + 30% Tackling
- ISS Body Balance = 60% Balance + 40% Strength
- ISS Response (outfield) = 50% Anticipation + 25% Decisions + 25% Concentration
- ISS Response (GK) = 70% Reflexes + 30% Anticipation
- ISS Curve = 45% Free Kick Taking + 35% Crossing + 20% Corners (proxy)
- ISS Shot Power = 40% Strength + 40% Long Shots + 20% Finishing (proxy)

These combinations are ISS26 mod-design decisions, not formulas
approved by Konami or Sports Interactive. Goalkeepers use separate weights
where relevant. If under 50% of the input weight is available, the target
characteristic is left blank.

The experimental iss_aggressive_experimental value is based on 70% Off the
Ball + 30% Work Rate and may not correspond to the version's in-game field.
iss_outside_foot is set only when a trait explicitly says outside of the foot;
otherwise it stays blank.

## Limitations / safety

- This produces a data table, not a playable patch.
- The ISS 12–19 convention comes from original game-era FAQs; inspect and
  validate the actual European BIN before binary injection.
- Age, height and foot preference are imported only if present.
- Traits, club membership and FM attributes are a snapshot which may differ
  from our intended 2026/27 rosters.
- Historical bonus legends may be absent from FM26's active player table;
  research them separately. The tool leaves them unmatched on purpose.
- No personal game saves, extracted FM database or copyrighted game assets
  are committed to the public repository.
- The converter has not been executed in this chat because the local
  code-execution environment is unavailable. Validate and test before merge.
