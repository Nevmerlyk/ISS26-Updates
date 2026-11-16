#!/usr/bin/env python3
"""Create a source-only bulk appearance plan from matched native references.
Manual reference fields override older native presets on a per-field basis.
This is a candidate plan for technical rendering validation, not a disc patch.
Every active membership is tracked; unresolved visuals remain null.
"""
import argparse,csv,json
from pathlib import Path
from collections import Counter,defaultdict
from match_v096_external_appearance import norm,rows
from refine_v096_appearance_identities import BASE_EXACT,ADDED
ROOT=Path(__file__).resolve().parents[1]
FIELDS=("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")
def key(r):return (r["team_id"],norm(r["player_name"]))
def main(native,external,out):
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    n={key(r):r for r in rows(native)}
    e={key(r):r for r in rows(external)}
    if len(manifest)!=1716 or len(n)!=1716 or len(e)!=1716:
        raise ValueError("roster coverage drift")
    p=json.loads((ROOT/"data/integration/v096_appearance_profiles_v2.json").read_text())["profiles"]
    manual={(r["team"],norm(r["name"])):r for r in p}
    mindex={key(r):r for r in manifest}
    uid_manual={}
    for k,p0 in manual.items():
        m=mindex[k]
        if m["roster_uid"] and m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":
            uid_manual[m["roster_uid"]]=p0
    plan=[]
    for m in manifest:
        k=key(m)
        r=n[k]
        old=e[k]
        a=manual.get(k)
        if a is None and m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":
            a=uid_manual.get(m["roster_uid"])
        native_exact=r["status"] in BASE_EXACT|ADDED
        values=[int(r[f]) if native_exact and r[f]!="" else None for f in FIELDS]
        methods=[r["status"]+"_PRESET" if v is not None else "" for v in values]
        conflicts=[]
        # The individual photo references are preferable for current style, but
        # remain provisional; preserve the comparison against the native profile.
        if a:
            for i,v in enumerate(a["values"]):
                if v is not None:
                    if values[i] is not None and values[i]!=v:conflicts.append(FIELDS[i])
                    values[i]=v;methods[i]="INDIVIDUAL_PHOTO_CANDIDATE"
        status=("NATIVE_OR_INDIVIDUAL_CANDIDATE" if any(v is not None for v in values)
             else "WE_EA_ID_DOB_REVIEW" if r["status"]=="WE_EA_ID_DOB_CANDIDATE"
             else "EA_FC25_MODEL_NEEDS_TRANSLATION" if old["status"]=="FC25_MODEL_MATCHED_HISTORICAL"
             else "NEEDS_VISUAL_SOURCE")
        plan.append({"team":m["team_id"],"name":m["player_name"],"roster_uid":m["roster_uid"],
            "dob":m["dob_candidate"],"values":values,"methods":methods,"status":status,
            "source":a["source"] if a else r["source"],"native_source":r["source"],
            "native_we_id":r["we_id"],"ea_player_id":old["ea_player_id"],"source_conflicts":conflicts,
            "native_status":r["status"],"ea_status":old["status"]})
    # Check candidates for any divergence among confidently linked UIDs.
    groups=defaultdict(list)
    for x in plan:
        if x["roster_uid"] and mindex[(x["team"],norm(x["name"]))]["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":
            groups[x["roster_uid"]].append(x)
    inconsistent=[]
    for uid,xs in groups.items():
        conflict_fields=[FIELDS[i] for i in range(6) if len({x["values"][i] for x in xs if x["values"][i] is not None})>1]
        if conflict_fields:
            inconsistent.append({"uid":uid,"fields":conflict_fields,"players":[[x["team"],x["name"]] for x in xs]})
            for x in xs:x["status"]="SHARED_UID_APPEARANCE_CONFLICT_REVIEW"
    candidates=[x for x in plan if x["status"]=="NATIVE_OR_INDIVIDUAL_CANDIDATE"]
    report={"status":"BULK_APPEARANCE_SOURCE_PLAN_NOT_RELEASED",
      "slots":len(plan),"statuses":dict(Counter(x["status"] for x in plan)),
      "candidate_slots":len(candidates),"complete_candidate_slots":sum(all(v is not None for v in x["values"]) for x in candidates),
      "candidate_field_values":sum(sum(v is not None for v in x["values"]) for x in candidates),
      "individual_native_disagreements":sum(bool(x["source_conflicts"]) for x in plan),
      "shared_uid_conflicts":inconsistent,"pal_runtime_verified":False,"binary_written":False}
    out.mkdir(parents=True,exist_ok=True)
    (out/"bulk_appearance_candidate_plan.json").write_text(json.dumps({"version":"0.9.6","fields":FIELDS,
      "status":"NOT_APPROVED_FOR_BINARY_WRITE","rows":plan},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"bulk_appearance_candidate_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("BULK_PLAN",json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("native","external","out"):p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args();main(a.native,a.external,a.out)
