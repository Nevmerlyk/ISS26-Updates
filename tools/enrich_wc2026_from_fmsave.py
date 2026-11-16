#!/usr/bin/env python3
"""Strict FM26 save-export enrichment for the FIFA roster draft (read-only inputs)."""
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from iss26_fm26_import import (ISS_ATTRIBUTES, OUTFIELD, GOALKEEPER, ATTRIBUTE_ALIASES,
    csv_rows, named_value, normalized_name, raw_attribute, iss_scale)

ATTRIBUTE_ALIASES["aerial_reach"] = ("aerial_reach", "aerial reach", "aer")
ATTRIBUTE_ALIASES["command_of_area"] += ("cmd",)
NAME_FIELDS = ("name", "full_name", "legal_name", "common_name", "player_name")
ID_FIELDS = ("unique_id", "database_id", "fm_uid", "fm26_unique_id")

def names(row):
    return {normalized_name(named_value(row, k)) for k in NAME_FIELDS} - {""}

def dob(row):
    return named_value(row, "birth_date", "date_of_birth", "dob")

def dbid(row):
    # fmsave uid is save-local, NEVER a database identifier.
    return named_value(row, *ID_FIELDS)

def indexes(source):
    by_id, by_name_date = defaultdict(list), defaultdict(list)
    for p in source:
        uid = dbid(p)
        if uid:
            by_id[uid].append(p)
        if dob(p):
            for name in names(p):
                by_name_date[name, dob(p)].append(p)
    return by_id, by_name_date

def select(row, by_id, by_name_date):
    name, date = normalized_name(row.get("player_name")), row.get("birth_date", "")
    if not name or not date:
        return "missing_roster_identity", None
    uid = row.get("fm_uid_candidate", "")
    if uid:
        hits = by_id.get(uid, [])
        if len(hits) > 1:
            return "duplicate_source_uid", None
        if hits:
            p = hits[0]
            if dob(p) != date:
                return "uid_dob_conflict", None
            if name in names(p):
                return "uid_name_dob", p
            # Different known names can be legitimate, but never silently match.
            return "uid_name_conflict", None
    hits = by_name_date.get((name, date), [])
    if len(hits) != 1:
        return ("ambiguous_name_dob" if hits else "not_found"), None
    p = hits[0]
    actual = dbid(p)
    if not actual:
        return "missing_database_uid", None
    if len(by_id[actual]) != 1:
        return "duplicate_source_uid", None
    if uid and actual != uid:
        return "candidate_uid_conflict", None
    return "name_dob", p

def strict_convert(player, spec):
    values = [(raw_attribute(player, attr), weight) for attr, weight in spec]
    # Do not mark a composite complete when any component is missing.
    if any(value is None for value, weight in values):
        return ""
    return iss_scale(sum(value * weight for value, weight in values))

def enrich(rows, source):
    by_id, by_name_date = indexes(source)
    result = []
    counts = defaultdict(int)
    for original in rows:
        row = dict(original)
        state, p = select(row, by_id, by_name_date)
        row["fm26_verified_match_status"] = state
        for attr in ISS_ATTRIBUTES:
            row["export_" + attr] = ""
        # Keep the previous candidates untouched, even on a successful match.
        for fld in ("unique_id", "natural_positions", "left_foot", "right_foot",
                    "height_cm", "weight_kg", "club_name", "ability_current",
                    "ability_potential"):
            row["export_fm26_" + fld] = ""
        if p is not None:
            spec = GOALKEEPER if row.get("position_group") == "GK" else OUTFIELD
            for attr in ISS_ATTRIBUTES:
                row["export_" + attr] = strict_convert(p, spec[attr])
            row["export_fm26_unique_id"] = dbid(p)
            for fld in ("natural_positions", "left_foot", "right_foot", "height_cm",
                        "weight_kg", "club_name", "ability_current", "ability_potential"):
                row["export_fm26_" + fld] = named_value(p, fld)
        row["export_converted_count"] = str(sum(bool(row["export_" + a]) for a in ISS_ATTRIBUTES))
        counts[state] += 1
        counts["complete_15"] += row["export_converted_count"] == "15"
        result.append(row)
    return result, dict(counts)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster", type=Path, required=True)
    p.add_argument("--fm26", type=Path, required=True, help="CSV from a real FM26 export")
    p.add_argument("--source-version", required=True, help="FM26 build and save date")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = args.out.with_suffix(".report.json")
    if args.out.exists() or report.exists():
        p.error("Refusing overwrite of existing output/report")
    _, roster = csv_rows(args.roster)
    columns, source = csv_rows(args.fm26)
    # Explicit namespaced display attributes prevent accepting raw 1–100 scales.
    if not {"unique_id", "birth_date", "attributes_pace", "attributes_stamina"}.issubset(columns):
        p.error("Expected flat fmsave FM26 player export; don't feed raw_attributes or fan ratings")
    if not source or not roster:
        p.error("Empty input")
    if len(roster) != 1248 or len({(r.get("team_id"), r.get("shirt_number")) for r in roster}) != 1248:
        p.error("Expected 1248 distinct draft tournament registrations")
    # Only display attributes are passed to converter; never raw_attributes.
    source = [{k:v for k,v in row.items() if not k.startswith("raw_attributes_")} for row in source]
    rows, counts = enrich(roster, source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    report.write_text(json.dumps({"source_version": args.source_version,
        "fm_export_sha256": sha(args.fm26), "roster_sha256": sha(args.roster),
        "counts": counts, "source_rows": len(source), "roster_rows": len(rows),
        "notes": "Export values are candidates from the supplied save; FIFA membership unchanged."},
        indent=2), encoding="utf-8")
    print(json.dumps(counts, indent=2))

if __name__ == "__main__":
    main()
