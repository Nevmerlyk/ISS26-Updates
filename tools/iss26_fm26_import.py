#!/usr/bin/env python3
"""Merge a real FM26 player CSV export into the ISS26 roster database.

Only observed FM26 fields are converted. Missing or ambiguous player matches remain
blank. Never use a 1..99 fan-site score as though it were an original FM26 1..20
attribute. No modifications to BIN/CUE or pre-existing input CSV files are made.

Python 3.10+, standard library only.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

ISS_ATTRIBUTES = (
    "iss_offense", "iss_defense", "iss_body_balance", "iss_stamina",
    "iss_speed", "iss_acceleration", "iss_response", "iss_jump_power",
    "iss_head_accuracy", "iss_technique", "iss_pass_accuracy",
    "iss_shot_power", "iss_shot_accuracy", "iss_dribble", "iss_curve",
)
EXTRA_FIELDS = (
    "iss_aggressive_experimental", "iss_outside_foot",
    "fm26_unique_id", "fm26_age", "fm26_height_cm", "fm26_preferred_foot",
    "fm26_match_name", "fm26_match_status", "fm26_converted_count",
    "fm26_origin", "fm26_database_version",
)
NAME_KEYS = ("name", "player", "player name", "full name", "player_name")
ID_KEYS = ("unique_id", "unique id", "database id", "fm uid", "uid", "id")

# All mappings are ISS26 design choices, NOT formulas published by Konami/SI.
# Components are FM26 attribute names, weighted to a sum of 1.0.
OUTFIELD = {
    "iss_offense": (("off_the_ball", .55), ("anticipation", .25), ("finishing", .20)),
    "iss_defense": (("positioning", .40), ("marking", .30), ("tackling", .30)),
    "iss_body_balance": (("balance", .60), ("strength", .40)),
    "iss_stamina": (("stamina", .75), ("natural_fitness", .25)),
    "iss_speed": (("pace", 1.0),),
    "iss_acceleration": (("acceleration", 1.0),),
    "iss_response": (("anticipation", .50), ("decisions", .25), ("concentration", .25)),
    "iss_jump_power": (("jumping_reach", 1.0),),
    "iss_head_accuracy": (("heading", 1.0),),
    "iss_technique": (("first_touch", .55), ("technique", .45)),
    "iss_pass_accuracy": (("passing", .65), ("vision", .25), ("crossing", .10)),
    "iss_shot_power": (("strength", .40), ("long_shots", .40), ("finishing", .20)),
    "iss_shot_accuracy": (("finishing", .65), ("composure", .20), ("long_shots", .15)),
    "iss_dribble": (("dribbling", 1.0),),
    "iss_curve": (("free_kick_taking", .45), ("crossing", .35), ("corners", .20)),
}
GOALKEEPER = dict(OUTFIELD, **{
    "iss_offense": (("off_the_ball", .50), ("anticipation", .50)),
    "iss_defense": (("one_on_ones", .50), ("command_of_area", .30), ("positioning", .20)),
    "iss_response": (("reflexes", .70), ("anticipation", .30)),
    "iss_technique": (("handling", .55), ("first_touch", .45)),
    "iss_pass_accuracy": (("kicking", .55), ("passing", .45)),
    "iss_jump_power": (("aerial_reach", .60), ("jumping_reach", .40)),
})

# Header variants commonly encountered in FM26 exports and save-file readers.
ATTRIBUTE_ALIASES = {
    "off_the_ball": ("off the ball", "offtheball", "otb"),
    "positioning": ("positioning", "pos"),
    "marking": ("marking", "mar"),
    "tackling": ("tackling", "tck"),
    "balance": ("balance", "bal"),
    "strength": ("strength", "str"),
    "stamina": ("stamina", "sta"),
    "natural_fitness": ("natural fitness", "naturalfitness", "nat"),
    "pace": ("pace", "pac"),
    "acceleration": ("acceleration", "acc"),
    "anticipation": ("anticipation", "ant"),
    "finishing": ("finishing", "fin"),
    "decisions": ("decisions", "dec"),
    "concentration": ("concentration", "cnt"),
    "jumping_reach": ("jumping reach", "jumping", "jum", "jump"),
    "heading": ("heading", "hea"),
    "first_touch": ("first touch", "firsttouch", "fir"),
    "technique": ("technique", "tec"),
    "passing": ("passing", "pas"),
    "vision": ("vision", "vis"),
    "crossing": ("crossing", "cro"),
    "long_shots": ("long shots", "longshots", "lon"),
    "composure": ("composure", "cmp"),
    "dribbling": ("dribbling", "dri"),
    "free_kick_taking": ("free kick taking", "free kicks", "free kick", "fre"),
    "corners": ("corners", "cor"),
    "work_rate": ("work rate", "workrate", "wor"),
    "reflexes": ("reflexes", "ref"),
    "handling": ("handling", "han"),
    "one_on_ones": ("one on ones", "one on one", "1v1", "oneonones"),
    "command_of_area": ("command of area", "commandofarea", "coa"),
    "kicking": ("kicking", "kic"),
}
for _field, _variants in ATTRIBUTE_ALIASES.items():
    ATTRIBUTE_ALIASES[_field] = (_field,) + _variants

def key(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text)

def normalized_name(name: object) -> str:
    s = str(name or "").strip()
    s = s.replace("’", "'").replace("‘", "'")
    s = re.sub(r"\b(jr|junior|filho)\.?\b", "", s, flags=re.I)
    return key(s)

def csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        sample = raw.decode("utf-16")
    else:
        sample = raw.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(sample[:15000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(sample.splitlines(), dialect=dialect)
    columns = reader.fieldnames or []
    return columns, [dict(row) for row in reader]

def named_value(row: dict[str, str], *names: str) -> str:
    mapped = {key(k): v for k, v in row.items() if k is not None}
    for name in names:
        for candidate in (name, "attributes." + name, "attributes_" + name,
                          "player." + name, "player_" + name):
            value = mapped.get(key(candidate), "")
            if value is not None and str(value).strip():
                return str(value).strip()
    return ""

def raw_attribute(player: dict[str, str], attr: str) -> float | None:
    s = named_value(player, *ATTRIBUTE_ALIASES[attr])
    if not s or s in {"?", "-", "—", "N/A"}:
        return None
    # Explicitly reject uncertain ranges and 1..99 fan-site-derived numbers.
    if re.search(r"[–—-]", s) or not re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return None
    value = float(s.replace(",", "."))
    if not 1 <= value <= 20:
        return None
    return value

def weighted(player: dict[str, str], spec: tuple[tuple[str, float], ...]) -> float | None:
    observations = [(raw_attribute(player, attr), weight) for attr, weight in spec]
    valid = [(value, weight) for value, weight in observations if value is not None]
    total_weight = sum(weight for _, weight in valid)
    # A single minor component cannot silently stand in for the whole skill.
    if total_weight < .50 - 1e-9:
        return None
    return sum(value * weight for value, weight in valid) / total_weight

def iss_scale(fm_value: float | None) -> str:
    if fm_value is None:
        return ""
    # FM 1..20 -> ISS 12..19; nearest integer, half up.
    converted = 12 + math.floor((fm_value - 1) * 7 / 19 + .5)
    return str(max(12, min(19, converted)))

def load_aliases(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    _, rows = csv_rows(path)
    output = {}
    for row in rows:
        source = named_value(row, "iss_name", "iss player", "iss")
        target = named_value(row, "fm26_name", "fm name", "fm26")
        if source and target:
            output[normalized_name(source)] = normalized_name(target)
    return output

def fm_index(fm_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in fm_rows:
        name = named_value(row, *NAME_KEYS)
        if name:
            result[normalized_name(name)].append(row)
    return result

def select_player(roster_name: str,
                  index: dict[str, list[dict[str, str]]],
                  aliases: dict[str, str]) -> tuple[str, dict[str, str] | None]:
    normalized = normalized_name(roster_name)
    candidates = index.get(aliases.get(normalized, normalized), [])
    if not candidates:
        return "not_found", None
    if len(candidates) == 1:
        return "matched", candidates[0]
    # Collapse exact duplicate rows from overlapping FM exports.
    unique = {}
    for player in candidates:
        ident = named_value(player, *ID_KEYS)
        fingerprint = ident if ident else json.dumps(player, sort_keys=True)
        unique[fingerprint] = player
    if len(unique) == 1:
        return "matched", next(iter(unique.values()))
    return "ambiguous", None

def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def merge(roster_path: Path, output_path: Path,
          index: dict[str, list[dict[str, str]]], aliases: dict[str, str],
          database_version: str) -> tuple[list[dict[str, str]], dict[str, int]]:
    fields, rows = csv_rows(roster_path)
    appended = [field for field in (*ISS_ATTRIBUTES, *EXTRA_FIELDS) if field not in fields]
    stats: dict[str, int] = defaultdict(int)
    unmatched: list[dict[str, str]] = []
    for row in rows:
        roster_name = named_value(row, "name", "player", "Футболист (полное имя)")
        status, fm = select_player(roster_name, index, aliases)
        for column in appended:
            row[column] = ""
        row["fm26_match_status"] = status
        row["fm26_database_version"] = database_version
        if fm is None:
            stats[status] += 1
            unmatched.append({"player_id": row.get("player_id", ""),
                              "name": roster_name, "status": status,
                              "source_file": roster_path.name})
            continue
        out_gk = named_value(row, "position") == "GK"
        specs = GOALKEEPER if out_gk else OUTFIELD
        for attr in ISS_ATTRIBUTES:
            row[attr] = iss_scale(weighted(fm, specs[attr]))
        row["iss_aggressive_experimental"] = iss_scale(
            weighted(fm, (("off_the_ball", .70), ("work_rate", .30))))
        # Outside-foot is a player trait, not a safe inference from attributes.
        traits = named_value(fm, "traits", "player traits", "preferred moves")
        row["iss_outside_foot"] = "YES" if re.search(r"outside of (the|his|her) foot", traits, re.I) else ""
        row["fm26_unique_id"] = named_value(fm, *ID_KEYS)
        row["fm26_age"] = named_value(fm, "age")
        row["fm26_height_cm"] = named_value(fm, "height_cm", "height", "height cm")
        row["fm26_preferred_foot"] = named_value(fm, "preferred foot", "preferred_foot")
        row["fm26_match_name"] = named_value(fm, *NAME_KEYS)
        row["fm26_origin"] = "REAL_FM26_CSV_EXPORT"
        number_done = sum(bool(row[a]) for a in ISS_ATTRIBUTES)
        row["fm26_converted_count"] = str(number_done)
        row["fm26_match_status"] = "complete" if number_done == 15 else "partial"
        stats[row["fm26_match_status"]] += 1
    write_rows(output_path, fields + appended, rows)
    return unmatched, stats

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fm26", required=True, type=Path,
                        help="CSV with actual FM26 1-20 attributes (e.g. fmsave export)")
    parser.add_argument("--players", type=Path, default=Path("ISS_players_2026.csv"))
    parser.add_argument("--reserve", type=Path, default=Path("ISS_reserve_2026.csv"))
    parser.add_argument("--aliases", type=Path, default=None,
                        help="optional CSV with iss_name,fm26_name")
    parser.add_argument("--outdir", type=Path, default=Path("fm26_converted"))
    parser.add_argument("--fm26-version", default="FM26/export-version-unspecified")
    args = parser.parse_args()
    for input_file in (args.fm26, args.players, args.reserve):
        if not input_file.is_file():
            parser.error(f"Missing input file: {input_file}")
    _, source_rows = csv_rows(args.fm26)
    if not source_rows:
        parser.error("FM26 CSV contains no player rows")
    if not any(named_value(row, *NAME_KEYS) for row in source_rows[:20]):
        parser.error("No recognizable name column in FM26 CSV")
    # Guard against data from fan sites with a 1..99 rating scale.
    attr_observations = [
        raw_attribute(row, "pace") for row in source_rows[:30]
    ]
    if not any(value is not None for value in attr_observations):
        print("WARNING: no FM26 Pace 1..20 values detected in sampled rows")
    index = fm_index(source_rows)
    aliases = load_aliases(args.aliases)
    all_missing: list[dict[str, str]] = []
    result = {}
    for input_path in (args.players, args.reserve):
        output = args.outdir / (input_path.stem + "_FM26_ISS26.csv")
        missing, stats = merge(input_path, output, index, aliases, args.fm26_version)
        result[input_path.name] = dict(stats)
        all_missing.extend(missing)
    write_rows(args.outdir / "FM26_unmatched.csv",
               ["player_id", "name", "status", "source_file"], all_missing)
    (args.outdir / "FM26_coverage.json").write_text(
        json.dumps({"source": str(args.fm26), "fm26_version": args.fm26_version,
                    "rosters": result, "unmatched": len(all_missing),
                    "note": "Unmatched and missing attributes remain blank, not guessed."},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Missing/ambiguous roster records: {len(all_missing)}")
    print(f"Files written to: {args.outdir}")

if __name__ == "__main__":
    main()
