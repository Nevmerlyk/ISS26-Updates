#!/usr/bin/env python3
"""Import registered FIFA WC26 squads into a separate reference CSV.
Requires Python 3.10+ and pdfplumber. No game files are modified.
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path
import pdfplumber

URL = "https://fdp.fifa.org/assetspublic/ce281/pdf/SquadLists-English.pdf"
ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "data/fm26/roster_source_policy.json"
FIELDS = ["team_id", "shirt_number", "fifa_player_name", "first_names",
          "last_names", "shirt_name", "position_group", "birth_date", "height_cm",
          "club_at_world_cup", "caps", "goals", "fifa_page", "source_edition",
          "registration_status", "iss_slot_selection"]

def clean(cell):
    return " ".join((cell or "").split())

def parse_pdf(path, expected):
    result = []
    seen_teams = set()
    with pdfplumber.open(path) as pdf:
        if len(pdf.pages) != 48:
            raise ValueError(f"Expected 48 pages, found {len(pdf.pages)}")
        for i, page in enumerate(pdf.pages, 1):
            top = page.crop((0, 0, page.width, page.height * .17)).extract_text() or ""
            codes = {m for m in re.findall(r"\(([A-Z]{3})\)", top)
                     if "NAT_" + m in expected}
            if len(codes) != 1:
                raise ValueError(f"Page {i}: cannot uniquely identify team: {codes}")
            team = "NAT_" + codes.pop()
            if team in seen_teams:
                raise ValueError(f"Repeated team {team}")
            seen_teams.add(team)
            page_text = page.extract_text() or ""
            if not re.search(r"19 July 2026\s*[|]\s*22:34", page_text):
                raise ValueError(f"Page {i}: source edition is not the expected final snapshot")
            players = []
            for table in page.extract_tables():
                for raw in table:
                    cells = [clean(c) for c in raw]
                    if len(cells) < 2 or not cells[0].isdigit() or cells[1] not in {"GK","DF","MF","FW"}:
                        continue
                    if len(cells) != 11:
                        raise ValueError(f"Page {i} {team}: unexpected player table width {len(cells)}")
                    num, pos, name, first, last, shirt, dob, club, height, caps, goals = cells
                    birth = dt.datetime.strptime(dob, "%d/%m/%Y").date().isoformat()
                    if not name or not shirt or not re.fullmatch(r"\d{3}", height) or not 140 <= int(height) <= 220:
                        raise ValueError(f"Page {i}: invalid player fields {num} {name}")
                    players.append(dict(team_id=team,shirt_number=int(num),fifa_player_name=name,
                        first_names=first,last_names=last,shirt_name=shirt,position_group=pos,
                        birth_date=birth,height_cm=int(height),club_at_world_cup=club,caps=caps,
                        goals=goals,fifa_page=i,source_edition="2026-07-19T22:34Z",
                        registration_status="registered",iss_slot_selection="pending"))
            if sorted(r["shirt_number"] for r in players) != list(range(1,27)):
                raise ValueError(f"Page {i} {team}: expected exactly shirts 1..26, got {len(players)} rows")
            result.extend(sorted(players, key=lambda r:r["shirt_number"]))
    if seen_teams != expected or len(result) != 1248:
        raise ValueError(f"Coverage failure: missing={expected-seen_teams}; rows={len(result)}")
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True, help="Local copy of final FIFA PDF")
    p.add_argument("--download", action="store_true", help="Download source PDF if local copy absent")
    p.add_argument("--out", type=Path, default=ROOT/"data/fm26/fifa_wc2026_registered_full.csv")
    args=p.parse_args()
    if args.out.exists():
        p.error("Output already exists; choose a fresh path.")
    if args.download and not args.pdf.exists():
        args.pdf.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(URL, timeout=60) as response:
            args.pdf.write_bytes(response.read())
    expected=set(json.loads(POLICY.read_text(encoding="utf-8"))["world_cup"]["participant_team_ids"])
    if len(expected)!=48:
        raise ValueError("Policy must specify exactly 48 teams")
    rows=parse_pdf(args.pdf,expected)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    print(json.dumps({"teams":48,"rows":len(rows),"pdf_sha256":hashlib.sha256(args.pdf.read_bytes()).hexdigest(),"source_url":URL,"output":str(args.out)},indent=2))

if __name__=="__main__":
    main()
