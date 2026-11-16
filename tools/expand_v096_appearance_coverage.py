#!/usr/bin/env python3
"""Extend coverage with EA identity-only matches and a held-out model-code crosswalk.
No face recognition, invented visual traits, disc writes or release updates.
Crosswalk values are historical approximate model candidates, not current photos.
"""
import argparse,csv,json,sqlite3,re,hashlib
from pathlib import Path
from collections import defaultdict,Counter
from match_v096_external_appearance import rows,norm,date,source_id,source_index,bit_record,RAW
from match_v096_we2002_appearance import dbdate,decode,FIELD_NAMES,SOURCE
from refine_v096_appearance_identities import BASE_EXACT,ADDED,aliases,link_id,same_tokens,unique_preset
ROOT=Path(__file__).resolve().parents[1]
FIELDS=("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")
EA_FIELDS=("hairtypecode","haircolorcode","facialhairtypecode","facialhaircolorcode","skintonecode","bodytypecode")
EXACT=BASE_EXACT|ADDED|{"WE_EA_IDENTITY_ONLY_DOB_LINK","WE_VERIFIED_ROSTER_UID_LINK"}
def key(r):return (r["team_id"],norm(r["player_name"]))
def load_db(path):
    c=sqlite3.connect(path.resolve().as_uri()+"?mode=ro",uri=True)
    c.execute("PRAGMA trusted_schema=OFF");c.row_factory=sqlite3.Row
    data=[dict(r) for r in c.execute("SELECT Id,Name,NAMEWE,Birthday,Club,NationalTeam,Nation,Position,Hair,HairColor,HairFace,HairColorFace,SkinColor,Body,Link FROM Players")]
    c.close();return data
def identity_index(manifest,sofifa,fc26):
    a=source_index(sofifa,"FC25");b=source_index(fc26,"FC26")
    out={}
    for m in manifest:
        d=date(m["dob_candidate"])
        if not d or m["identity_status"]=="DOB_CONFLICT_REVIEW":continue
        names={norm(m["player_name"])}
        if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB":
            names.add(aliases(m["fm_name"]))
        opts=[r for n in names if n for r in a.get((n,d),[])+b.get((n,d),[])]
        ids={r[0] for r in opts}
        if len(ids)==1:out[key(m)]=next(iter(ids))
    return out
def extend(manifest,native,ea,db,ids):
    bylink=defaultdict(list)
    for r in db:
        eid=link_id(r["Link"])
        if eid and str(r["Id"])==eid:
            bylink[(eid,dbdate(r["Birthday"]))].append(r)
    out=[];added=[]
    for m in manifest:
        k=key(m);r=dict(native[k])
        if r["status"] not in EXACT and r["status"]!="WE_CONFLICTING_PRESETS" and m["identity_status"]!="DOB_CONFLICT_REVIEW":
            eid=ids.get(k)
            # A modern identity does not require the older EA model to exist.
            choices=bylink.get((eid,date(m["dob_candidate"])),[])
            w=unique_preset(choices)
            if w:
                r.update(status="WE_EA_IDENTITY_ONLY_DOB_LINK",we_id=str(w["Id"]),source_name=w["Name"],source_birthday=w["Birthday"],source_club=w["Club"],source_nation=w["Nation"],source=SOURCE,raw_preset="/".join(str(w[f] or "") for f in FIELD_NAMES))
                r.update(dict(zip(FIELDS,decode(w))))
                added.append([m["team_id"],m["player_name"],str(w["Id"])])
        out.append(r)
    # Propagate only from a source-backed record to another membership of an
    # already independently matched roster UID, with matching DOB and no conflict.
    groups=defaultdict(list)
    for i,m in enumerate(manifest):
        if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB" and m["roster_uid"] and date(m["dob_candidate"]):
            groups[(m["roster_uid"],date(m["dob_candidate"]))].append(i)
    propagated=[]
    for indices in groups.values():
        good=[out[i] for i in indices if out[i]["status"] in EXACT]
        if not good:continue
        if len({(str(r["we_id"]),tuple(str(r[x]) for x in FIELDS)) for r in good})!=1:continue
        source=good[0]
        for i in indices:
            r=out[i]
            if r["status"] in EXACT or r["status"]=="WE_CONFLICTING_PRESETS":continue
            for f in ["we_id","source_name","source_birthday","source_club","source_nation","source","raw_preset",*FIELDS]:r[f]=source[f]
            r["status"]="WE_VERIFIED_ROSTER_UID_LINK"
            propagated.append([r["team_id"],r["player_name"],r["we_id"]])
    return out,added,propagated
def crosswalk(native,external):
    # Independent EA-ID anchors, not repeated club and national memberships.
    # Exclude custom scanned heads from training; their generic values may not
    # describe rendered models. Hold out players by stable ID, not row.
    pairs={}
    conflicting=set()
    for r in native:
        e=external[key(r)]
        if r["status"] not in EXACT or e["status"]!="FC25_MODEL_MATCHED_HISTORICAL":continue
        eid=e["ea_player_id"]
        if str(r["we_id"])!=eid or str(e["hashighqualityhead"])!="0":continue
        v=tuple(str(e[f]) for f in EA_FIELDS)+tuple(str(r[f]) for f in FIELDS)
        if eid in pairs and pairs[eid]!=v:conflicting.add(eid)
        pairs[eid]=v
    for eid in conflicting:pairs.pop(eid,None)
    train=defaultdict(Counter);check=defaultdict(Counter)
    for eid,p in pairs.items():
        held=int(hashlib.sha256(eid.encode()).hexdigest(),16)%5==0
        for i,f in enumerate(FIELDS):
            if p[i] and p[i+6]:
                (check if held else train)[(f,p[i])][p[i+6]]+=1
    report={};selected={}
    for (f,c),counts in sorted(train.items()):
        target,n=counts.most_common(1)[0];total=sum(counts.values())
        test=check[(f,c)];nt=sum(test.values());ok=test[target]
        accepted=total>=8 and n/total>=.9 and nt>=3 and ok/nt>=.85
        # These thresholds are conservative for historical game-model
        # correspondence and do NOT certify exact current appearance.
        item={"target":int(target),"train_n":total,"train_agreement":round(n/total,4),"heldout_n":nt,"heldout_agreement":round(ok/nt,4) if nt else None,"accepted_candidate":accepted}
        report.setdefault(f,{})[c]=item
        if accepted:selected[(f,c)]=int(target)
    return selected,report,len(pairs)
def main(src,native,external,plan,db,out):
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    n={key(r):r for r in rows(native)};e={key(r):r for r in rows(external)}
    original=json.loads(plan.read_text(encoding="utf-8"));old={(r["team"],norm(r["name"])):r for r in original["rows"]}
    if len(manifest)!=len(n) or len(n)!=len(e) or len(n)!=len(old) or len(n)!=1716:raise ValueError("roster drift")
    ids=identity_index(manifest,rows(src/"sofifa.csv"),rows(src/"fc26.csv"))
    new,added,propagated=extend(manifest,n,e,load_db(db),ids)
    mapped,report,nanchors=crosswalk(new,e)
    result=[];native_added=historical_added=0
    for m,r in zip(manifest,new):
        k=key(m);p=dict(old[k]);p["values"]=list(p["values"]);p["methods"]=list(p["methods"])
        was=any(v is not None for v in p["values"])
        if r["status"] in EXACT:
            for i,f in enumerate(FIELDS):
                if p["values"][i] is None and r[f] not in ("",None):
                    p["values"][i]=int(r[f]);p["methods"][i]=r["status"]+"_PRESET"
            p.update(native_we_id=str(r["we_id"]),native_status=r["status"],native_source=r["source"])
            if not p["source"]:p["source"]=r["source"]
            if not was and any(v is not None for v in p["values"]):native_added+=1
        elif e[k]["status"]=="FC25_MODEL_MATCHED_HISTORICAL" and str(e[k]["hashighqualityhead"])=="0" and m["identity_status"]!="DOB_CONFLICT_REVIEW":
            for i,(f,ef) in enumerate(zip(FIELDS,EA_FIELDS)):
                if p["values"][i] is None and (f,str(e[k][ef])) in mapped:
                    p["values"][i]=mapped[f,str(e[k][ef])];p["methods"][i]="FC25_CROSSWALK_HELDOUT_CANDIDATE"
            if not was and any(v is not None for v in p["values"]):historical_added+=1
            if not p["source"] and any(v is not None for v in p["values"]):p["source"]="https://github.com/Radzim/football_data/tree/076dbb1e76413c93582385d8e56f18384dc6bee9"
        if any(v is not None for v in p["values"]):
            p["status"]="NATIVE_OR_INDIVIDUAL_CANDIDATE"
            if any(s=="FC25_CROSSWALK_HELDOUT_CANDIDATE" for s in p["methods"]):p["status"]="HISTORICAL_CROSSWALK_REVIEW"
        result.append(p)
    # Do not silently promote a shared-UID conflict.
    groups=defaultdict(list)
    for m,p in zip(manifest,result):
        if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB" and m["roster_uid"]:groups[m["roster_uid"]].append(p)
    conflicts=[]
    for uid,ps in groups.items():
        fs=[f for i,f in enumerate(FIELDS) if len({p["values"][i] for p in ps if p["values"][i] is not None})>1]
        if fs:
            conflicts.append({"uid":uid,"fields":fs})
            for p in ps:p["status"]="SHARED_UID_APPEARANCE_CONFLICT_REVIEW"
    out.mkdir(parents=True,exist_ok=True)
    original["rows"]=result
    (out/"bulk_appearance_candidate_plan.json").write_text(json.dumps(original,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (out/"we2002_native_appearance_matches.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(new[0]));w.writeheader();w.writerows(new)
    good=[p for p in result if p["status"]=="NATIVE_OR_INDIVIDUAL_CANDIDATE"]
    partial=[p for p in result if p["status"]=="HISTORICAL_CROSSWALK_REVIEW"]
    summary={"status":"SOURCE_ONLY_RUNTIME_PENDING","slots":len(result),"identity_only_ea_ids":len(ids),"native_id_links":len(added),"uid_links":len(propagated),"native_new_candidate_slots":native_added,"historical_new_candidate_slots":historical_added,"statuses":dict(Counter(p["status"] for p in result)),"native_candidate_slots":len(good),"native_complete_slots":sum(all(v is not None for v in p["values"]) for p in good),"historical_review_slots":len(partial),"known_fields":sum(sum(v is not None for v in p["values"]) for p in good+partial),"crosswalk_distinct_training_and_holdout_anchors":nanchors,"crosswalk_accepted_code_count":len(mapped),"shared_conflicts":conflicts,"binary_written":False,"runtime_verified":False}
    (out/"coverage_report.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (out/"crosswalk_heldout_report.json").write_text(json.dumps({"codes":report,"native_id_links":added,"uid_links":propagated},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("COVERAGE",json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("src","native","external","plan","db","out"):p.add_argument("--"+k,type=Path,required=True)
    a=p.parse_args();main(a.src,a.native,a.external,a.plan,a.db,a.out)
