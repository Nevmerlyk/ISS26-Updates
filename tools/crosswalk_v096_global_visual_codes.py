#!/usr/bin/env python3
"""Learn a conservative historical visual-code crosswalk from *all* eligible
source pairs, with player-level held-out validation. Not a release or BOM edit.
No nationality, ethnicity, statistical playing attributes or name-derived
appearance is used. The mapping is exclusively between explicit model codes.
"""
import argparse,csv,json,datetime as dt,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from match_v096_external_appearance import rows,norm,date,source_id
from match_v096_we2002_appearance import dbdate,decode
from refine_v096_appearance_identities import link_id
from expand_v096_appearance_coverage import load_db
from resolve_v096_appearance_full_names import discover
ROOT=Path(__file__).resolve().parents[1]
FIELDS=("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")
EA_FIELDS=("hairtypecode","haircolorcode","facialhairtypecode","facialhaircolorcode","skintonecode","bodytypecode")
def key(m):return (m["team_id"],norm(m["player_name"]))
def raw_dob(r):
    try:return (dt.date(1582,10,14)+dt.timedelta(days=int(r["birthdate"]))).isoformat()
    except (ValueError,OverflowError,KeyError):return ""
def raw_index(data):
    raw={};dup=set()
    for r in data:
        eid=source_id(r)
        if r.get("gender")!="0" or not eid:continue
        if eid in raw:dup.add(eid)
        raw[eid]=r
    return {k:v for k,v in raw.items() if k not in dup}
def native_anchors(raw,db):
    paired=defaultdict(set)
    for w in db:
        eid=link_id(w["Link"])
        if not eid or str(w["Id"])!=eid or eid not in raw:continue
        e=raw[eid]
        if str(e.get("hashighqualityhead"))!="0":continue
        if not dbdate(w["Birthday"]) or dbdate(w["Birthday"])!=raw_dob(e):continue
        vals=decode(w)
        if any(v is None for v in vals):continue
        codes=tuple(str(e.get(f,"")) for f in EA_FIELDS)
        if not all(c.lstrip("-").isdigit() for c in codes):continue
        paired[eid].add((codes,tuple(vals)))
    return {eid:next(iter(v)) for eid,v in paired.items() if len(v)==1}
def fit(anchors,exclude):
    train=defaultdict(Counter);test=defaultdict(Counter)
    for eid,(codes,values) in anchors.items():
        # Exclude every target player from training and validation.
        if eid in exclude:continue
        check=int(hashlib.sha256(("ISS26:"+eid).encode()).hexdigest(),16)%5==0
        for f,c,v in zip(FIELDS,codes,values):
            (test if check else train)[f,c][v]+=1
    accepted={};report={}
    for (f,c),ctr in sorted(train.items()):
        v,n=ctr.most_common(1)[0];total=sum(ctr.values())
        held=test[(f,c)];h=sum(held.values());hits=held[v]
        # Historical template approximations, not visual ground truth.
        ok=total>=16 and n/total>=.9 and h>=5 and hits/h>=.85
        report.setdefault(f,{})[c]={"target":v,"train_n":total,"train_agreement":round(n/total,4),"holdout_n":h,"holdout_agreement":round(hits/h,4) if h else None,"accepted":ok}
        if ok:accepted[f,c]=v
    return accepted,report
def main(src,db,plan,out):
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    old=json.loads(plan.read_text(encoding="utf-8"))
    previous={(r["team"],norm(r["name"])):r for r in old["rows"]}
    if len(previous)!=len(manifest) or len(manifest)!=1716:raise ValueError("population mismatch")
    exact,alias,_=discover(manifest,rows(src/"sofifa.csv"),rows(src/"fc26.csv"))
    ids={**exact,**{k:r["id"] for k,r in alias.items()}}
    raw=raw_index(rows(src/"players.csv"))
    anchors=native_anchors(raw,load_db(db))
    target_ids={ids[key(m)] for m in manifest if key(m) in ids}
    accepted,report=fit(anchors,target_ids)
    records=[];target_count=0;added=0;filled=0;fieldcounts=Counter()
    for m in manifest:
        k=key(m);p=previous[k];eid=ids.get(k)
        e=raw.get(eid,{})
        was=any(v is not None for v in p["values"])
        # Only fill from direct model records with exact DOB and generic head.
        ok=(p["status"] not in ("NATIVE_OR_INDIVIDUAL_CANDIDATE","SHARED_UID_APPEARANCE_CONFLICT_REVIEW")
            and m["identity_status"]!="DOB_CONFLICT_REVIEW" and e and date(m["dob_candidate"])==raw_dob(e)
            and str(e.get("hashighqualityhead"))=="0")
        if ok:
            target_count+=1
            for i,(f,ef) in enumerate(zip(FIELDS,EA_FIELDS)):
                # Replace earlier narrow statistical estimates with the independent wider
                # map only if the latter agrees; contradictory values stay pending.
                candidate=accepted.get((f,str(e.get(ef,""))))
                if candidate is not None and p["values"][i] is None:
                    p["values"][i]=candidate;p["methods"][i]="FC25_GLOBAL_HELDOUT_CANDIDATE"
                    filled+=1;fieldcounts[f]+=1
            if any(v is not None for v in p["values"]):
                p["status"]="HISTORICAL_CROSSWALK_REVIEW"
                if not p.get("source"):p["source"]="https://github.com/Radzim/football_data/tree/076dbb1e76413c93582385d8e56f18384dc6bee9"
                p["ea_player_id"]=eid
                if not was:added+=1
        records.append(p)
    groups=defaultdict(list)
    for m,p in zip(manifest,records):
        if m["roster_uid"] and m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":groups[m["roster_uid"]].append(p)
    conflicts=[]
    for uid,ps in groups.items():
        fs=[f for i,f in enumerate(FIELDS) if len({p["values"][i] for p in ps if p["values"][i] is not None})>1]
        if fs:
            conflicts.append([uid,fs])
            for p in ps:p["status"]="SHARED_UID_APPEARANCE_CONFLICT_REVIEW"
    old["rows"]=records
    out.mkdir(parents=True,exist_ok=True)
    (out/"bulk_appearance_candidate_plan.json").write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"global_crosswalk_report.json").write_text(json.dumps({"status":"HISTORICAL_MAPPING_NOT_PAL_VERIFIED","all_anchor_players":len(anchors),"excluded_roster_ids":len(set(anchors)&target_ids),"accepted_codes":len(accepted),"mapping":report},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    stats={"status":"SOURCE_ONLY_RUNTIME_PENDING","slots":len(records),"nonroster_training_and_holdout_anchors":len(set(anchors)-target_ids),"accepted_codes":len(accepted),"eligible_target_slots":target_count,"additional_historical_slots":added,"new_field_values":filled,"new_field_counts":dict(fieldcounts),"counts":dict(Counter(p["status"] for p in records)),"complete_native_slots":sum(p["status"]=="NATIVE_OR_INDIVIDUAL_CANDIDATE" and all(v is not None for v in p["values"]) for p in records),"conflicts":conflicts,"binary_written":False}
    (out/"global_coverage_report.json").write_text(json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("GLOBAL_COVERAGE",json.dumps(stats,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("src","db","plan","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();main(a.src,a.db,a.plan,a.out)
