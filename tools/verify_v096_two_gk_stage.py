#!/usr/bin/env python3
"""Fail-closed validator for the provisional 0.9.6 v22 source-staged 78 squads.

This checks CSV source identity, order and provenance only. It does NOT
apply any patch, decode game citizenship, or certify a FIFA/club squad.
Never use `game_slot` as a jersey number or native player memory index.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import pathlib
import unicodedata
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data/integration/ISS26_active_rosters_v22_two_GK_stage.csv"
JSON_PATH = ROOT / "data/integration/ISS26_active_rosters_v22_two_GK_report.json"
CLUB_REGISTRY = ROOT / "data/integration/active_club_registry_v21.json"
EXPECTED_CLUBS = {
    "CLB_SHK","CLB_KRY","CLB_LEV","CLB_AJX","CLB_NEW","CLB_SCP",
    "CLB_BEN","CLB_ROM","CLB_BAY","CLB_ACM","CLB_JUV","CLB_INT",
    "CLB_BVB","CLB_ATM","CLB_NAP","CLB_RMA","CLB_PSG","CLB_BAR",
    "CLB_TOT","CLB_MCI","CLB_LIV","CLB_CHE","CLB_ARS","CLB_MUN",
}
EXPECTED_CLUB_NEW = {
    "CLB_KRY":"Jimmy Mpanzu",
    "CLB_BAY":"Sacha Boey",
    "CLB_BVB":"Filippo Mané",
    "CLB_LEV":"Axel Tape",
    "CLB_LIV":"Giovanni Leoni",
    "CLB_MUN":"Chido Obi",
}
assert len(EXPECTED_CLUBS)==24
REQUIRED = {
    "team_id","game_slot","player_name","source_position","previous_v21_slot",
    "selection_type","source_state","game_write_authorized","nationality_verified",
    "jersey_number_verified",
}

def key(text: str) -> str:
    special={"ł":"l","Ł":"L","ø":"o","Ø":"O","đ":"d","Đ":"D","ß":"ss"}
    text="".join(special.get(c,c) for c in text)
    text=unicodedata.normalize("NFKD",text)
    return re.sub("[^a-z0-9]","",text.encode("ascii","ignore").decode().lower())

def load_csv(path: pathlib.Path) -> list[dict]:
    with path.open(encoding="utf-8-sig",newline="") as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("v22 CSV missing mandatory columns")
        return list(reader)

def validate(rows: list[dict],report: dict, registry: dict | None = None) -> dict:
    if (report.get("schema")!=2 or
        report.get("status")!="PROVISIONAL_SOURCE_STAGE_NOT_WRITTEN_TO_BIN" or
        report.get("teams")!=78 or report.get("total_players")!=1716 or
        report.get("clubs")!=24 or report.get("nationals")!=54 or
        report.get("old_v21_three_goalkeeper_teams_fixed_in_source_stage")!=60 or
        report.get("provisional_outfield_insertions")!=60 or
        report.get("goalkeeper_count_all_teams")!=2):
        raise ValueError("Wrong provisional v22 report or unsafe release status")
    if len(rows)!=1716:
        raise ValueError("Require exactly 78x22 rows")
    groups=collections.defaultdict(list)
    for row in rows:
        team=row.get("team_id")
        name=row.get("player_name","")
        if (not isinstance(team,str) or
            not (team.startswith("CLB_") or team.startswith("NAT_")) or
            not isinstance(name,str) or not name.strip() or
            row.get("game_write_authorized")!="NO" or
            row.get("nationality_verified")!="NO" or
            row.get("jersey_number_verified")!="NO"):
            raise ValueError("Unrecognized team/identity or an unsafe write authorization")
        groups[team].append(row)
    clubs={k for k in groups if k.startswith("CLB_")}
    countries={k for k in groups if k.startswith("NAT_")}
    if clubs!=EXPECTED_CLUBS or len(countries)!=54 or "NAT_UKR" not in countries:
        raise ValueError("Active 24-club/54-national registry drift")
    if registry is not None:
        source={x["team_id"] for x in registry["menu_order"]}
        if source!=clubs or len(registry["menu_order"])!=24:
            raise ValueError("DEV18 real club registry mismatch")
    if report["shakhtar"].get("team_id")!="CLB_SHK" or not report["shakhtar"].get("players_preserved_all_22"):
        raise ValueError("Shakhtar preservation guarantee removed")
    add_counts=collections.Counter()
    for club,players in groups.items():
        if len(players)!=22:
            raise ValueError("Wrong team size: "+club)
        slots=[int(p.get("game_slot","0")) for p in players]
        if slots!=list(range(1,23)):
            raise ValueError("Incorrect or duplicate game slots: "+club)
        if len({key(p["player_name"]) for p in players})!=22:
            raise ValueError("Duplicate/ambiguous player name in "+club)
        keepers=[int(p["game_slot"]) for p in players if p["source_position"]=="GK"]
        if keepers!=[1,22]:
            raise ValueError("Reserve goalkeeper must be last for "+club)
        types=[p["selection_type"] for p in players]
        if (types!=["STARTER_GK"]+["STARTER_OUTFIELD"]*10+
            ["RESERVE_OUTFIELD"]*10+["RESERVE_GK"]):
            raise ValueError("Starting XI and bench not properly partitioned in "+club)
        add_counts[club]=sum(p["source_state"]=="UNVERIFIED_NEW_CANDIDATE" for p in players)
        if add_counts[club]>1:
            raise ValueError("Multiple unsupported replacement candidates: "+club)
        if club=="CLB_SHK":
            if (players[0]["player_name"]!="Dmytro Riznyk" or
                players[21]["player_name"]!="Denys Tvardovskyi" or
                add_counts[club]!=0):
                raise ValueError("Shakhtar players or GK identities changed")
    for team,player in EXPECTED_CLUB_NEW.items():
        p=[p for p in groups[team] if p["source_state"]=="UNVERIFIED_NEW_CANDIDATE"]
        if len(p)!=1 or p[0]["player_name"]!=player:
            raise ValueError("2026-source candidate changed unexpectedly in "+team)
    total_new=sum(add_counts.values())
    if total_new!=60 or sum(add_counts[t] for t in countries)!=54:
        raise ValueError("Expected 54 national +6 club new field source candidates")
    listed=report.get("changes")
    if not isinstance(listed,list) or len(listed)!=60:
        raise ValueError("Expected exactly 60 auditable removal/replacement records")
    changed={x["team_id"] for x in listed}
    if len(changed)!=60 or changed!={t for t,n in add_counts.items() if n}:
        raise ValueError("Candidate summary disagrees with CSV players")
    for change in listed:
        team=change["team_id"]
        new=[p["player_name"] for p in groups[team]
             if p["source_state"]=="UNVERIFIED_NEW_CANDIDATE"]
        if (new!=[change["new_outfield"]] or
            change.get("source_is_independently_approved_for_game") is not False):
            raise ValueError("Unapproved source change was promoted: "+team)
    return {
        "status":"V22_PROVISIONAL_SOURCE_LAYOUT_VALIDATED_NOT_PATCHED",
        "teams":len(groups),"clubs":len(clubs),"nationals":len(countries),
        "all_78_have_11_starting_and_11_reserve":True,
        "all_78_have_2_gk_in_slots_1_and_22":True,
        "candidate_replacements":total_new,
        "shakhtar_preserved":True,
        "game_patch_changed":False,
        "release_ready":False,
    }

def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--csv",type=pathlib.Path,default=CSV_PATH)
    p.add_argument("--report",type=pathlib.Path,default=JSON_PATH)
    p.add_argument("--registry",type=pathlib.Path,default=CLUB_REGISTRY)
    args=p.parse_args()
    data=load_csv(args.csv)
    report=json.loads(args.report.read_text(encoding="utf-8"))
    registry=json.loads(args.registry.read_text(encoding="utf-8"))
    print(json.dumps(validate(data,report,registry),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
