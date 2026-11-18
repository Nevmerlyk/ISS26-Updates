#!/usr/bin/env python3
"""ISS26 v0.9.6 DEV20: validate source-only v25 personal citizenship worklist.

Game identity != CSV position != original native (group,index) reference.
No club source ID or national team menu ordinal is allowed as proof of the
personal citizenship field. This file never writes game, flags, or feeds.
"""
from __future__ import annotations

import collections
import json

try:
    from .verify_v096_two_gk_stage import ROOT, load_csv, key
except ImportError:
    from verify_v096_two_gk_stage import ROOT, load_csv, key

V24 = ROOT / "data/integration/ISS26_active_rosters_v24_shakhtar_current.csv"
V25 = ROOT / "data/integration/ISS26_active_rosters_v25_club_loan_corrections.csv"
V25_LOANS = ROOT / "data/integration/ISS26_v25_club_loan_source_review.json"
V25_COUNTRIES = ROOT / "data/integration/ISS26_v25_club_528_country_worklist.json"
OLD_COUNTRIES = ROOT / "data/integration/v096_master_league_nationality_targets.json"
SHAKHTAR = ROOT / "data/integration/ISS26_shakhtar_v24_current_numbers_and_citizenship_targets.json"

EXPECTED_LOANS = {
    ("CLB_LEV", "21"): ("Axel Tape", "Eliesse Ben Seghir", "MAR"),
    ("CLB_MUN", "21"): ("Chido Obi", "Shea Lacey", "ENG"),
}
EXPECTED_CROSSWALK = {
    ("CLB_BVB","Filippo Mané"):"ITA",
    ("CLB_KRY","Jimmy Mpanzu"):"POR",
    ("CLB_LEV","Eliesse Ben Seghir"):"MAR",
    ("CLB_MUN","Shea Lacey"):"ENG",
    ("CLB_SHK","Irakli Azarov"):"GEO",
    ("CLB_SHK","Alaa Ghram"):"TUN",
    ("CLB_SHK","Alan Matturro"):"URU",
    ("CLB_SHK","Dmytro Riznyk"):"UKR",
    ("CLB_SHK","Denys Tvardovskyi"):"UKR",
}

def check(
    v24:list[dict], v25:list[dict], loan:dict,
    nationality:dict, old_nationality:dict, shakhtar:dict,
) -> dict:
    if (len(v24)!=1716 or len(v25)!=1716 or
        loan.get("status")!="V25_LOAN_FIXES_SOURCE_CANDIDATES_NO_NATIVE_WRITES" or
        loan.get("row_count")!=1716 or loan.get("teams")!=78 or
        loan.get("shakhtar_retained_unchanged") is not True or
        loan.get("source_data_not_a_game_patch") is not True or
        loan.get("release_ready") is not False):
        raise ValueError("V24/V25 source identity/preimage guard missing")
    oldidx={(x["team_id"],x["game_slot"]):x for x in v24}
    newidx={(x["team_id"],x["game_slot"]):x for x in v25}
    if len(oldidx)!=1716 or len(newidx)!=1716 or set(oldidx)!=set(newidx):
        raise ValueError("Duplicate or missing roster team/slot")
    diff=[]
    teams=collections.defaultdict(list)
    for identity,before in oldidx.items():
        after=newidx[identity]
        if after!=before:
            if (identity not in EXPECTED_LOANS or
                before["player_name"]!=EXPECTED_LOANS[identity][0] or
                after["player_name"]!=EXPECTED_LOANS[identity][1] or
                after["source_state"]!="UNVERIFIED_NEW_CANDIDATE" or
                after["source_status"]!="OFFICIAL_2026_ACTIVE_MEMBERSHIP_CANDIDATE"):
                raise ValueError("Unauthorized 2026 source roster edit: "+str(identity))
            diff.append(identity)
        if (after.get("game_write_authorized")!="NO" or
            after.get("nationality_verified")!="NO" or
            after.get("jersey_number_verified")!="NO"):
            raise ValueError("Unapproved native player edits")
        teams[after["team_id"]].append(after)
    if sorted(diff)!=sorted(EXPECTED_LOANS):
        raise ValueError("Exactly two season-loan corrections expected")
    if (len(teams)!=78 or
        sum(t.startswith("CLB_") for t in teams)!=24 or
        sum(t.startswith("NAT_") for t in teams)!=54):
        raise ValueError("Active club or national registry drift")
    for team,players in teams.items():
        if (len(players)!=22 or
            [int(x["game_slot"]) for x in players]!=list(range(1,23)) or
            [int(x["game_slot"]) for x in players if x["source_position"]=="GK"]!=[1,22]):
            raise ValueError("Reserve goalkeeper must remain last: "+team)
    if (teams["CLB_SHK"][0]["player_name"]!="Dmytro Riznyk" or
        teams["CLB_SHK"][21]["player_name"]!="Denys Tvardovskyi"):
        raise ValueError("Shakhtar is immutable")
    original=old_nationality.get("players")
    if (not isinstance(original,list) or len(original)!=528 or
        old_nationality.get("status")!="SOURCE_TARGET_MANIFEST_NOT_BINARY_REMAP"):
        raise ValueError("Original nationality source manifest unrecognized")
    previous={}
    for p in original:
        identity=(p["club"],key(p["player"]))
        if identity in previous:
            raise ValueError("Old citizenship source duplicate identity")
        previous[identity]=p
    if (nationality.get("status")!="CLUB_CITIZENSHIP_SOURCE_V25_NO_NATIVE_PLAYER_WRITES" or
        nationality.get("active_club_rows")!=528 or nationality.get("clubs")!=24 or
        nationality.get("legacy_unique_team_name_joins")!=519 or
        nationality.get("new_not_in_legacy")!=9 or
        nationality.get("unmatched_old_source")!=9 or
        nationality.get("country_codes_count")!=65 or
        nationality.get("source_country_with_no_provisional_id_count")!=37 or
        nationality.get("personal_country_native_field_decoded") is not False or
        nationality.get("game_citizenship_patch_written") is not False or
        nationality.get("release_ready") is not False):
        raise ValueError("Citizenship source is not approved for in-game use")
    target=nationality.get("players")
    if not isinstance(target,list) or len(target)!=528:
        raise ValueError("Expected 528 current citizenship targets")
    byslot={}
    matched_old=0
    country_without_id=0
    countries=set()
    missing_ids=collections.Counter()
    new_names=[]
    for p in target:
        identity=(p.get("team_id"),str(p.get("game_slot")))
        if identity in byslot:
            raise ValueError("Duplicate country team/slot target")
        byslot[identity]=p
        actual=newidx.get(identity)
        if (actual is None or not actual["team_id"].startswith("CLB_") or
            actual["player_name"]!=p.get("player_name") or
            not p.get("country_code_candidate") or
            p.get("confidence")!="CANDIDATE_NOT_NATIVE_PROOF" or
            p.get("update_game_player_record_allowed") is not False or
            p.get("source_game_label_unknown") is not True or
            p.get("country_id_is_provisional") is not True or
            p.get("club_slot_as_personal_nationality_id_forbidden") is not True or
            p.get("independent_shirt_number_not_derived_from_slot") is not True):
            raise ValueError("Citizenship candidate matched by slot, not by name/club")
        country=p["country_code_candidate"]
        countries.add(country)
        person=(p["team_id"],key(p["player_name"]))
        prior=previous.get(person)
        if prior:
            matched_old+=1
            if p.get("source_legacy_country")!=prior["source_country"] or country!=prior["source_country"]:
                raise ValueError("Legacy player nationality was silently changed")
            if p.get("legacy_source_slot_not_game_slot")!=prior["source_slot"]:
                raise ValueError("Legacy identity/source slot provenance changed")
        else:
            new_names.append(person)
            if p.get("source_legacy_country") is not None or not p.get("official_2026_url"):
                raise ValueError("New player has no independent official nationality evidence")
        idvalue=p.get("country_id_candidate_from_old_manifest")
        if idvalue is None:
            country_without_id+=1
            missing_ids[country]+=1
        elif type(idvalue)!=int or not 0<=idvalue<256:
            raise ValueError("Invalid provisional old source national ID")
        if (p["team_id"],p["player_name"]) in EXPECTED_CROSSWALK:
            if country!=EXPECTED_CROSSWALK[p["team_id"],p["player_name"]]:
                raise ValueError("Official/current country candidate contradicted")
        if country=="TUN" and p["player_name"]=="Alaa Ghram" and idvalue is not None:
            raise ValueError("Tunisia national team ordinal is not proof of individual country field")
    if (matched_old!=519 or len(new_names)!=9 or len(countries)!=65 or
        country_without_id!=37 or set(byslot)!={k for k in newidx if k[0].startswith("CLB_")}):
        raise ValueError("528-country join coverage or status changed")
    if dict(missing_ids)!=nationality.get("countries_requiring_country_id_mapping"):
        raise ValueError("Missing-country-ID count or source summary mismatch")
    shteam=shakhtar.get("club_2026_27_shirt_targets")
    if (shakhtar.get("shakhtar_team_id")!="CLB_SHK" or
        not isinstance(shteam,list) or len(shteam)!=22 or
        shteam[0]["club_jersey_number"]!=31 or
        shteam[-1]["club_jersey_number"]!=48):
        raise ValueError("Shakhtar 2026/27 shirts #31 and #48 not preserved")
    for x in shteam:
        row=byslot.get(("CLB_SHK",str(x["source_slot"])))
        if not row or row["player_name"]!=x["player_name"] or row["country_code_candidate"]!=x["country_candidate"]:
            raise ValueError("Shakhtar official country/shirt identity mismatch")
    return {
        "status":"V25_SOURCE_COUNTRY_528_RECONCILED_NOT_NATIVE_PATCHED",
        "team_count":78,"club_count":24,"national_count":54,
        "player_membership_count":1716,"club_country_records":528,
        "legacy_name_and_team_joins":matched_old,"new_country_evidence_targets":len(new_names),
        "all_528_have_a_source_country":True,"missing_provisional_country_ids":country_without_id,
        "distinct_country_codes":len(countries),
        "two_goalkeepers_at_slots_1_and_22":True,"shakhtar_retained":True,
        "official_number_48_needs_runtime_override":True,
        "native_personal_country_field_known":False,"game_patch_changed":False,
        "release_ready":False,
    }

def main() -> None:
    v24=load_csv(V24)
    v25=load_csv(V25)
    loan=json.loads(V25_LOANS.read_text(encoding="utf-8"))
    nat=json.loads(V25_COUNTRIES.read_text(encoding="utf-8"))
    old=json.loads(OLD_COUNTRIES.read_text(encoding="utf-8"))
    shk=json.loads(SHAKHTAR.read_text(encoding="utf-8"))
    print(json.dumps(check(v24,v25,loan,nat,old,shk),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
