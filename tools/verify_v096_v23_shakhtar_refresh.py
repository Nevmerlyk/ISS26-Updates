#!/usr/bin/env python3
"""Validate v23 Shakhtar refresh against immutable v22 source stage.

This is a source-only identity/role audit; no native player id or shirt number
is written. Fail closed on any other of the 1,716 team records changing.
"""
from __future__ import annotations

import collections
import hashlib
import json
from pathlib import Path

from verify_v096_two_gk_stage import ROOT, load_csv

OLD = ROOT / "data/integration/ISS26_active_rosters_v22_two_GK_stage.csv"
NEW = ROOT / "data/integration/ISS26_active_rosters_v23_shakhtar_refresh.csv"
REPORT = ROOT / "data/integration/ISS26_shakhtar_v23_five_official_refresh.json"
EXPECTED = {
    "Yukhym Konoplia": "Oleksandr Karavaiev",
    "Diego Arroyo": "Irakli Azarov",
    "Danylo Udod": "Alaa Ghram",
    "Roman Savchenko": "Marlon Santos",
    "Ivan Petriak": "Alan Matturro",
}
assert len(EXPECTED) == 5

def blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()

def audit(before: list[dict], after: list[dict], report: dict, old_sha: str) -> dict:
    if (report.get("schema")!=1 or
        report.get("status")!="SHK_2026_27_REFRESH_PROVISIONAL_NOT_APPLIED_TO_GAME" or
        report.get("source_v22_sha")!=old_sha or
        report.get("gameplay_verified") is not False or
        report.get("release_ready") is not False or
        report.get("old_club_registry_preserved") is not True or
        report.get("other_77_teams_unchanged") is not True):
        raise ValueError("Wrong v23 source manifest or untrusted previous source SHA")
    if len(before)!=1716 or len(after)!=1716:
        raise ValueError("Require exactly 1716 source records")
    old_by_key={(x["team_id"],x["game_slot"]):x for x in before}
    new_by_key={(x["team_id"],x["game_slot"]):x for x in after}
    if len(old_by_key)!=1716 or set(old_by_key)!=set(new_by_key) or len(new_by_key)!=1716:
        raise ValueError("One or more team/slot identity keys were replaced")
    diffs=[]
    for identity,b in old_by_key.items():
        a=new_by_key[identity]
        if b!=a:
            if identity[0]!="CLB_SHK":
                raise ValueError("Non-Shakhtar roster record was touched")
            if (b["player_name"] not in EXPECTED or
                EXPECTED[b["player_name"]]!=a["player_name"] or
                a["source_state"]!="UNVERIFIED_NEW_CANDIDATE" or
                a["game_write_authorized"]!="NO" or
                a["nationality_verified"]!="NO" or
                a["jersey_number_verified"]!="NO" or
                a["source_url"]!="https://shakhtar.com/en/players/first-team" or
                b["selection_type"]!=a["selection_type"]):
                raise ValueError("Unapproved Shakhtar player identity or state replacement")
            diffs.append((b["player_name"],a["player_name"]))
    if set(diffs)!=set(EXPECTED.items()) or len(diffs)!=5:
        raise ValueError("Expected exactly five approved source-only Shakhtar refresh candidates")
    summary=report.get("changes",[])
    if (len(summary)!=5 or
        {(c["removed_stale_candidate"],c["new_verified_current_player"])
         for c in summary}!=set(diffs) or
        any(c.get("authorizes_native_edit") is not False for c in summary)):
        raise ValueError("V23 provenance differs from exact roster replacement")
    members=collections.defaultdict(list)
    for p in after:
        if p["team_id"].startswith(("CLB_","NAT_")):
            members[p["team_id"]].append(p)
        if (p["game_write_authorized"]!="NO" or
            p["nationality_verified"]!="NO" or
            p["jersey_number_verified"]!="NO"):
            raise ValueError("Unsafe game write approval in provisional v23")
    if (len(members)!=78 or
        sum(t.startswith("CLB_") for t in members)!=24 or
        sum(t.startswith("NAT_") for t in members)!=54):
        raise ValueError("Team pool no longer 54+24")
    for team,players in members.items():
        slots=[int(x["game_slot"]) for x in players]
        keepers=[int(x["game_slot"]) for x in players if x["source_position"]=="GK"]
        if len(players)!=22 or slots!=list(range(1,23)) or keepers!=[1,22]:
            raise ValueError("Invalid two-GK team layout: "+team)
    shk=members["CLB_SHK"]
    if shk[0]["player_name"]!="Dmytro Riznyk" or shk[21]["player_name"]!="Denys Tvardovskyi":
        raise ValueError("Shakhtar goalkeepers changed")
    return {
        "status":"V23_78_TEAM_SHK_REFRESH_SOURCE_ONLY_PASS",
        "teams":78,"clubs":24,"national":54,"player_records":1716,
        "source_shakhtar_updated":5,"source_candidate_total":sum(
            x["source_state"]=="UNVERIFIED_NEW_CANDIDATE" for x in after),
        "starter_and_last_reserve_goalkeepers":78,
        "shakhtar_retained":True,"game_patch_modified":False,"release_ready":False,
    }

def main():
    before=load_csv(OLD)
    after=load_csv(NEW)
    report=json.loads(REPORT.read_text(encoding="utf-8"))
    result=audit(before,after,report,blob_sha(OLD.read_bytes()))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
