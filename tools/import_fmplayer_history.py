#!/usr/bin/env python3
"""Offline importer for FMPlayer's text/Markdown history tables (FM26 only).
Use a manually reviewed source manifest and authorized cached pages. Never
fetch URLs or merge directly into the roster. Identity remains a candidate.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re
from pathlib import Path
from urllib.parse import urlsplit
from import_fmplayer_profiles import LABELS, EXTRA_LABELS, converted, normalized_name
from iss26_fm26_import import ISS_ATTRIBUTES


def label_key(s):
    return "".join(c for c in s.lower() if c.isalnum())


ALIASES = {label_key(label): key for key, label in LABELS.items()}
for key, names in EXTRA_LABELS.items():
    for name in names:
        ALIASES[label_key(name)] = key


def history_uid(url):
    p = urlsplit(url)
    m = re.fullmatch(r"/history/[^/]+-(\d+)", p.path)
    if p.scheme != "https" or p.netloc != "fmplayer.net" or p.query or p.fragment or not m:
        raise ValueError("invalid FMPlayer history URL")
    return m.group(1)


def parse_history(text, url):
    uid = history_uid(url)
    heading = re.search(r"(?im)^\s*#*\s*([^\n]+?)\s+Football Manager History\s*$", text)
    if not heading:
        raise ValueError("history heading missing")
    observations = {}
    header = None
    column = None
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [v.strip() for v in line.strip().strip("|").split("|")]
        if label_key(cells[0]) == "attribute":
            versions = [label_key(v) for v in cells]
            if header is not None or versions.count("fm26") != 1:
                raise ValueError("ambiguous or missing FM26 column")
            header, column = versions, versions.index("fm26")
            continue
        key = ALIASES.get(label_key(cells[0]))
        if not key or header is None:
            continue
        if len(cells) != len(header):
            raise ValueError("attribute row width differs from history header")
        cell = cells[column]
        # No fallback to an older game or to a delta displayed beside a value.
        n = int(cell) if re.fullmatch(r"\d{1,3}", cell) else 0
        value = n // 10 if 10 <= n <= 200 and n % 10 == 0 else None
        observations.setdefault(key, set()).add(value)
    if header is None:
        raise ValueError("FM26 history table missing")
    raw = {k: next(iter(v)) for k, v in observations.items()
           if len(v) == 1 and None not in v}
    if not raw:
        raise ValueError("no valid FM26 history attributes")
    return {"uid": uid, "name": heading.group(1).strip(), "raw": raw}


def match(row, entry, profile):
    if not row.get("fm_uid_candidate") or row["fm_uid_candidate"] != profile["uid"]:
        raise ValueError("roster identity missing or conflicting")
    if entry.get("expected_uid") != profile["uid"]:
        raise ValueError("manifest UID conflicts")
    if normalized_name(profile["name"]) not in {
        normalized_name(row.get("player_name")), normalized_name(entry.get("expected_name"))
    }:
        raise ValueError("name conflicts")
    if not entry.get("identity_source_url", "").startswith("https://"):
        raise ValueError("independent identity source required in reviewed manifest")
    if row.get("position_group") not in ("GK", "DF", "MF", "FW"):
        raise ValueError("missing roster position group")
    return converted(profile, row["position_group"])


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields):
    with path.open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("roster", "manifest", "cache", "out"):
        p.add_argument("--" + arg, type=Path, required=True)
    a = p.parse_args()
    roster, entries = read_csv(a.roster), read_csv(a.manifest)
    key = lambda r: (r["team_id"], r["shirt_number"])
    if len(set(map(key, roster))) != len(roster) or len(set(map(key, entries))) != len(entries):
        p.error("duplicate roster or manifest keys")
    index = {key(r): r for r in roster}
    a.out.mkdir(parents=True, exist_ok=True)
    if any((a.out / name).exists() for name in ("history_candidates.csv", "history_rejected.csv", "history_report.json")):
        p.error("output exists; choose a new directory")
    raw_fields = sorted(LABELS)
    fields = ["team_id", "shirt_number", "player_name", "source_name", "source_uid", "source_url",
              "identity_source_url", "identity_status", "body_sha256"] + ["fm26_" + k for k in raw_fields] + list(ISS_ATTRIBUTES) + ["converted_count"]
    good, bad = [], []
    for entry in entries:
        try:
            row = index[key(entry)]
            url = entry["source_url"]
            uid = history_uid(url)
            body = (a.cache / (uid + ".history.txt")).read_text(encoding="utf-8")
            profile = parse_history(body, url)
            vals = match(row, entry, profile)
            good.append({"team_id": row["team_id"], "shirt_number": row["shirt_number"],
                "player_name": row["player_name"], "source_name": profile["name"], "source_uid": uid,
                "source_url": url, "identity_source_url": entry["identity_source_url"],
                "identity_status": "history_uid_name_candidate_external_identity_review_required",
                "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
                **{"fm26_" + k: profile["raw"].get(k, "") for k in raw_fields}, **vals,
                "converted_count": sum(bool(v) for v in vals.values())})
        except (KeyError, OSError, ValueError) as e:
            bad.append({"team_id": entry.get("team_id", ""), "shirt_number": entry.get("shirt_number", ""), "reason": str(e)})
    write_csv(a.out / "history_candidates.csv", good, fields)
    write_csv(a.out / "history_rejected.csv", bad, ["team_id", "shirt_number", "reason"])
    report = {"accepted": len(good), "rejected": len(bad), "complete_15": sum(r["converted_count"] == 15 for r in good), "status": "CANDIDATES_ONLY_NOT_RELEASE"}
    (a.out / "history_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
