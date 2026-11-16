#!/usr/bin/env python3
"""Resolve full-name / short-name aliases in modern EA tables.
DOB + nationality (identity only) + nontrivial alias evidence + one unique ID.
No visual attributes inferred from nationality, identity or demographics.
"""
import argparse,json,csv,re
from pathlib import Path
from collections import defaultdict,Counter
from match_v096_external_appearance import rows,norm,date,source_id,val,source_index
from refine_v096_appearance_identities import aliases,tokens
from expand_v096_appearance_coverage import identity_index,extend,load_db,key,EXACT,FIELDS
ROOT=Path(__file__).resolve().parents[1]

def nation(s):
    a=norm(s)
    return {"turkiye":"turkey","czechrepublic":"czechia","korearepublic":"southkorea","republicofireland":"ireland","ivorycoast":"cotedivoire","congodr":"drcongo","democraticrepublicofthecongo":"drcongo","capeverde":"caboverde","unitedstatesofamerica":"unitedstates","usa":"unitedstates"}.get(a,a)
def name_tokens(s):
    return tokens(s)
def match_alias(a,b):
    t,u=name_tokens(a),name_tokens(b)
    if len(t)<2 or len(u)<2:return False
    # Full or shortened multiple-word names, including middle-name omissions.
    if set(t)<=set(u) or set(u)<=set(t):return True
    # Abbreviated first name + exact substantial surname (or hyphenated surname).
    if len(t)==2 and len(t[0])==1 and len(t[1])>=5 and u[0].startswith(t[0]) and t[1] in u[1:]:return True
    if len(u)==2 and len(u[0])==1 and len(u[1])>=5 and t[0].startswith(u[0]) and u[1] in t[1:]:return True
    return False
def discover(manifest,sofifa,fc26):
    exact=identity_index(manifest,sofifa,fc26)
    bydob=defaultdict(list)
    for tag,data in [("FC25",sofifa),("FC26",fc26)]:
        for r in data:
            d=date(val(r,"dob","birth_date","date_of_birth"))
            eid=source_id(r)
            n=nation(val(r,"nationality_name","country_name"))
            if d and eid and n:
                names=[val(r,"short_name","name"),val(r,"long_name","full_name")]
                # SoFIFA's source description sometimes explicitly supplies the
                # display alias before its parenthetical legal name and DOB.
                desc=r.get("description","")
                m=re.match(r"^([^()]+?)\s+\(",desc)
                if m:names.append(m[1])
                bydob[d].append((eid,n,names,tag))
    resolved={};ambiguous=[]
    for m in manifest:
        k=key(m)
        if k in exact or m["identity_status"]=="DOB_CONFLICT_REVIEW":continue
        d=date(m["dob_candidate"])
        if not d:continue
        nations={nation(s) for s in m["fm_nationalities"].split(",") if s}
        if not nations:continue
        names=[m["player_name"]]
        if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":
            names.append(re.sub(r"\([^)]*\)","",m["fm_name"]))
        options=[(eid,nn,tag) for eid,n,ns,tag in bydob[d] if n in nations for nn in ns if any(match_alias(a,nn) or (len(norm(a))>=5 and norm(a)==norm(nn)) for a in names)]
        ids={x[0] for x in options}
        if len(ids)==1:resolved[k]={"id":next(iter(ids)),"evidence":options}
        elif len(ids)>1:ambiguous.append([m["team_id"],m["player_name"],sorted(ids)])
    return exact,resolved,ambiguous
def main(src,native,plan,db,out):
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    n={key(r):r for r in rows(native)}
    original=json.loads(plan.read_text(encoding="utf-8"))
    old={(r["team"],norm(r["name"])):r for r in original["rows"]}
    assert len(manifest)==len(n)==len(old)==1716
    exact,resolved,ambiguous=discover(manifest,rows(src/"sofifa.csv"),rows(src/"fc26.csv"))
    ids={**exact,**{k:v["id"] for k,v in resolved.items()}}
    new,added,propagated=extend(manifest,n,{},load_db(db),ids)
    # Carry only unique validated links into the native plan; preserve existing candidates.
    candidates=[]
    for m,r in zip(manifest,new):
        k=key(m);p=old[k]
        if r["status"] in EXACT:
            if p["status"] not in ("SHARED_UID_APPEARANCE_CONFLICT_REVIEW","NATIVE_OR_INDIVIDUAL_CANDIDATE"):
                for i,f in enumerate(FIELDS):
                    if p["methods"][i]=="FC25_CROSSWALK_HELDOUT_CANDIDATE" or p["values"][i] is None:
                        if r[f] not in ("",None):
                            p["values"][i]=int(r[f]);p["methods"][i]=r["status"]+"_PRESET"
                p.update(native_we_id=str(r["we_id"]),native_status=r["status"],native_source=r["source"],source=r["source"],status="NATIVE_OR_INDIVIDUAL_CANDIDATE")
            else:
                for i,f in enumerate(FIELDS):
                    if p["values"][i] is None and r[f] not in ("",None):
                        p["values"][i]=int(r[f]);p["methods"][i]=r["status"]+"_PRESET"
        candidates.append(p)
    groups=defaultdict(list)
    for m,p in zip(manifest,candidates):
        if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB" and m["roster_uid"]:
            groups[m["roster_uid"]].append(p)
    conflicts=[]
    for uid,ps in groups.items():
        fs=[f for i,f in enumerate(FIELDS) if len({p["values"][i] for p in ps if p["values"][i] is not None})>1]
        if fs:
            conflicts.append({"uid":uid,"fields":fs})
            for p in ps:p["status"]="SHARED_UID_APPEARANCE_CONFLICT_REVIEW"
    out.mkdir(parents=True,exist_ok=True)
    original["rows"]=candidates
    (out/"bulk_appearance_candidate_plan.json").write_text(json.dumps(original,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (out/"we2002_native_appearance_matches.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(new[0]));w.writeheader();w.writerows(new)
    # A reference queue for the remaining slots, not evidence of observed looks.
    queue=[]
    for m,p in zip(manifest,candidates):
        if p["status"]=="NATIVE_OR_INDIVIDUAL_CANDIDATE" and all(v is not None for v in p["values"]):continue
        k=key(m);eid=ids.get(k,"")
        queue.append({"team":m["team_id"],"name":m["player_name"],"dob":m["dob_candidate"],"status":p["status"],"source_ea_id":eid,"ea_profile_candidate":f"https://sofifa.com/player/{eid}" if eid else "","fm_profile_candidate":m["existing_fm_profile_url"] or m["generated_sortitoutsi_candidate_url"],"existing_visual_reference":m["existing_visual_reference"],"unfilled_fields":";".join(f for i,f in enumerate(FIELDS) if p["values"][i] is None)})
    with (out/"remaining_visual_reference_queue.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(queue[0]));w.writeheader();w.writerows(queue)
    result={"status":"SOURCE_ONLY_RUNTIME_PENDING","slots":len(candidates),"exact_ea_identity_slots":len(exact),"new_alias_ea_ids":len(resolved),"ambiguous_alias_slots":len(ambiguous),"new_native_links":len(added),"new_verified_uid_links":len(propagated),"statuses":dict(Counter(p["status"] for p in candidates)),"complete_native_slots":sum(p["status"]=="NATIVE_OR_INDIVIDUAL_CANDIDATE" and all(v is not None for v in p["values"]) for p in candidates),"shared_conflicts":conflicts,"remaining_queue_rows":len(queue),"queue_with_ea_profile":sum(bool(x["ea_profile_candidate"]) for x in queue),"queue_with_fm_profile":sum(bool(x["fm_profile_candidate"]) for x in queue),"binary_written":False,"runtime_verified":False}
    (out/"alias_coverage_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"alias_identity_evidence.json").write_text(json.dumps({"resolved":[{"team_id":k[0],"name_key":k[1],**v} for k,v in resolved.items()],"ambiguous":ambiguous,"added_native":added},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("ALIAS_RESULT",json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("src","native","plan","db","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();main(a.src,a.native,a.plan,a.db,a.out)
