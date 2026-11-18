#!/usr/bin/env python3
"""ISS26 0.9.6: verify current 2026/27 Shakhtar source v24 independently.

A roster source is NOT a native binary patch; it cannot authorize changes to
jersey, citizenship, skills or flags. Retain all other 77 teams bit-for-bit
at the CSV record level, with two GKs and a reserve GK in source slot 22.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

try:
    from .verify_v096_v23_shakhtar_refresh import ROOT, NEW as PREVIOUS, blob_sha
    from .verify_v096_two_gk_stage import load_csv
except ImportError:
    from verify_v096_v23_shakhtar_refresh import ROOT, NEW as PREVIOUS, blob_sha
    from verify_v096_two_gk_stage import load_csv

CURRENT = ROOT / "data/integration/ISS26_active_rosters_v24_shakhtar_current.csv"
MANIFEST = ROOT / "data/integration/ISS26_shakhtar_v24_current_numbers_and_citizenship_targets.json"

def verify(previous: list[dict], current: list[dict], manifest: dict, previous_sha: str) -> dict:
    if (manifest.get("schema") != 1 or
        manifest.get("status") != "SHK_2026_27_LATEST_FIRST_TEAM_STAGE_NO_GAME_WRITE" or
        manifest.get("source_v23_blob_sha") != previous_sha or
        manifest.get("teams") != 78 or manifest.get("clubs") != 24 or
        manifest.get("national_teams") != 54 or
        manifest.get("slots_total") != 1716 or
        manifest.get("shakhtar_team_id") != "CLB_SHK" or
        manifest.get("game_bin_changed") is not False or
        manifest.get("game_test_feed_changed") is not False or
        manifest.get("release_ready") is not False):
        raise ValueError("Untrusted v24 manifest / predecessor source or unsafe release state")
    def index(rows):
        return {(p["team_id"],p["game_slot"]):p for p in rows}
    before=index(previous)
    after=index(current)
    if len(previous)!=1716 or len(current)!=1716 or len(before)!=1716 or len(after)!=1716 or set(before)!=set(after):
        raise ValueError("78x22 team-slot identity set changed or duplicates introduced")
    differences=[]
    members=collections.defaultdict(list)
    for identity,b in before.items():
        a=after[identity]
        if b!=a:
            if (identity!=("CLB_SHK","12") or
                b["player_name"]!="Artem Bondarenko" or
                a["player_name"]!="Isaque Silva" or
                a["source_position"]!="MF" or
                a["source_state"]!="UNVERIFIED_NEW_CANDIDATE" or
                a["source_status"]!="OFFICIAL_SHK_2026_27_CURRENT_SQUAD_CANDIDATE" or
                a["source_url"]!="https://shakhtar.com/en/players/first-team" or
                a["selection_type"]!=b["selection_type"]):
                raise ValueError("Unexpected change to v23: "+str(identity))
            differences.append(identity)
        if (a["game_write_authorized"]!="NO" or
            a["nationality_verified"]!="NO" or
            a["jersey_number_verified"]!="NO"):
            raise ValueError("Source is not approved for native binary writing")
        members[a["team_id"]].append(a)
    if differences!=[("CLB_SHK","12")]:
        raise ValueError("Exactly one Shakhtar source refresh must occur")
    if (len(members)!=78 or
        sum(k.startswith("CLB_") for k in members)!=24 or
        sum(k.startswith("NAT_") for k in members)!=54):
        raise ValueError("Club count / Shakhtar identity changed")
    for team,players in members.items():
        if (len(players)!=22 or
            [int(p["game_slot"]) for p in players]!=list(range(1,23)) or
            [int(p["game_slot"]) for p in players if p["source_position"]=="GK"]!=[1,22]):
            raise ValueError("Broken two-GK or 22-slot team: "+team)
    shk=members["CLB_SHK"]
    if shk[0]["player_name"]!="Dmytro Riznyk" or shk[21]["player_name"]!="Denys Tvardovskyi":
        raise ValueError("Shakhtar first and last GKs changed")
    shirts=manifest.get("club_2026_27_shirt_targets",[])
    if (len(shirts)!=22 or
        [x.get("source_slot") for x in shirts]!=list(range(1,23)) or
        [x.get("player_name") for x in shirts]!=[p["player_name"] for p in shk] or
        any(x.get("country_is_not_natively_written") is not True or
            x.get("club_number_is_not_natively_written") is not True or
            x.get("national_number_separate") is not True or
            not 1<=x.get("club_jersey_number",0)<=99
            for x in shirts)):
        raise ValueError("Incomplete/unsafe current Shakhtar shirt or country worklist")
    if (shirts[0]["club_jersey_number"]!=31 or
        shirts[21]["club_jersey_number"]!=48 or
        manifest.get("special_number_rule",{}).get("base_native_shirt_bit_width")!=5 or
        manifest["special_number_rule"].get("requires_runtime_override")!=[
            {"player_name":"Denys Tvardovskyi","club_shirt_number":48}]):
        raise ValueError("Official #31/#48 requires separate runtime jersey number logic")
    changes=sum(p["source_state"]=="UNVERIFIED_NEW_CANDIDATE" for p in current)
    if changes!=66:
        raise ValueError("Expected 60 provisional 3GK fixes plus 6 Shakhtar current player candidates")
    return {"status":"V24_SHAKHTAR_2026_27_SOURCE_78_TEAM_READBACK_PASS",
            "teams":78,"clubs":24,"nationals":54,"player_memberships":1716,
            "goalkeepers_per_team":2,"reserve_gk_slot":22,
            "shakhtar_retained":True,"current_shakhtar_squad_candidates":22,
            "provisional_changed_player_candidates":changes,
            "only_one_change_from_v23":True,
            "five_bit_number_48_unsupported":True,
            "game_patch_changed":False,"release_ready":False}

def main():
    before=load_csv(PREVIOUS)
    after=load_csv(CURRENT)
    metadata=json.loads(MANIFEST.read_text(encoding="utf-8"))
    print(json.dumps(verify(before,after,metadata,blob_sha(PREVIOUS.read_bytes())),
                     ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
