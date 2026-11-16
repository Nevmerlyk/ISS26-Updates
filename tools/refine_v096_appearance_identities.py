#!/usr/bin/env python3
"""Improve native appearance reference coverage without guessing visual traits.
Only identity evidence is used: exact DOB, aliases, verified EA ID and source URL.
This is a source candidate audit, not EU runtime verification or a binary write.
"""
import argparse,csv,json,re,sqlite3,unicodedata
from collections import Counter,defaultdict
from pathlib import Path
from match_v096_external_appearance import norm,date,rows
from match_v096_we2002_appearance import dbdate,decode,FIELD_NAMES,SOURCE

ROOT=Path(__file__).resolve().parents[1]
FIELDS=("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")
BASE_EXACT={"WE_NAME_DOB_MATCH","WE_NAME_DOB_DUPLICATES_SAME_PRESET"}
ADDED={"WE_EXACT_FM_ALIAS_DOB","WE_JERSEY_ALIAS_DOB","WE_EA_ID_DOB_LINK","WE_EA_ID_DOB_NAME_EVIDENCE","WE_REORDERED_NAME_DOB","WE_NAME_DOB_TOKEN_AND_ASSOCIATION"}
def key(r):return (r["team_id"],norm(r["player_name"]))
def aliases(s):
    return norm(re.sub(r"\([^)]*\)","",s or ""))
def tokens(s):
    v=unicodedata.normalize("NFKD",re.sub(r"\([^)]*\)","",s or "")).encode("ascii","ignore").decode().lower()
    return [x for x in re.findall("[a-z0-9]+",v) if x not in ("jr","junior","filho","de","da","do","dos","das","van","von","al","el","bin","del","di")]
def link_id(s):
    m=re.search(r"(?:sofifa\.com/player/|fifaindex\.com/player/|fifacm\.com/player/)(\d+)(?:[/#?]|$)",s or "",re.I)
    return m.group(1) if m else ""
def same_tokens(a,b):
    t,u=tokens(a),tokens(b)
    return len(t)>=2 and len(u)>=2 and sorted(t)==sorted(u)
def subset_name(a,b):
    t,u=set(tokens(a)),set(tokens(b))
    return min(len(t),len(u))>=2 and (t<=u or u<=t)
def name_evidence(a,b):
    return aliases(a)==aliases(b) or same_tokens(a,b) or subset_name(a,b)
def assoc(m,w):
    # Association is only an identity cross-check, never a source for visual traits.
    nations={norm(x) for x in (m.get("fm_nationalities") or "").split(",") if x}
    return bool(nations.intersection({norm(w["Nation"]),norm(w["NationalTeam"])}))
def unique_preset(candidates):
    if not candidates:return None
    if len({(str(r['Id']),tuple(decode(r))) for r in candidates})!=1:return None
    return sorted(candidates,key=lambda r:(str(r["Id"]),r["Name"]))[0]
def choose(m,old,e,bydob):
    if m["identity_status"]=="DOB_CONFLICT_REVIEW" or old["status"]=="WE_CONFLICTING_PRESETS":
        return None,None
    d=date(m["dob_candidate"])
    if not d:return None,None
    a=m["player_name"]
    confirmed_fm=m["fm_name"] if m["identity_status"]=="ROSTER_UID_WITH_NAME_OR_DOB" else ""
    opts=bydob.get(d,[])
    ea=e.get("ea_player_id","") if e.get("status")=="FC25_MODEL_MATCHED_HISTORICAL" else ""
    # Each pass requires unique preset and birthdate. For ID-only aliases,
    # corroborate the EA ID with the source player URL or meaningful name evidence.
    rules=[
        ("WE_EXACT_FM_ALIAS_DOB",lambda r:bool(confirmed_fm and aliases(confirmed_fm)==aliases(r["Name"]))),
        ("WE_REORDERED_NAME_DOB",lambda r:any(same_tokens(n,r["Name"]) for n in (a,confirmed_fm) if n)),
        ("WE_EA_ID_DOB_LINK",lambda r:bool(ea and str(r["Id"])==ea and link_id(r["Link"])==ea)),
        ("WE_EA_ID_DOB_NAME_EVIDENCE",lambda r:bool(ea and str(r["Id"])==ea and any(name_evidence(n,r["Name"]) or aliases(n)==aliases(r["NAMEWE"]) for n in (a,confirmed_fm) if n))),
        ("WE_JERSEY_ALIAS_DOB",lambda r:bool(aliases(a)==aliases(r["NAMEWE"]) and len(aliases(a))>=5 and assoc(m,r))),
        ("WE_NAME_DOB_TOKEN_AND_ASSOCIATION",lambda r:bool(assoc(m,r) and any(subset_name(n,r["Name"]) for n in (a,confirmed_fm) if n)))
    ]
    for method,pred in rules:
        candidates=[r for r in opts if pred(r)]
        if candidates:
            sel=unique_preset(candidates)
            if sel:return method,sel
            return None,None
    return None,None
def main(db,native,external,out):
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    conn.execute("PRAGMA trusted_schema=OFF")
    conn.row_factory=sqlite3.Row
    data=[dict(r) for r in conn.execute("SELECT Id,Name,NAMEWE,Birthday,Club,NationalTeam,Nation,Position,Hair,HairColor,HairFace,HairColorFace,SkinColor,Body,Link FROM Players")]
    conn.close()
    bydob=defaultdict(list)
    for r in data:
        d=dbdate(r["Birthday"])
        if d:bydob[d].append(r)
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    n={key(r):r for r in rows(native)}
    e={key(r):r for r in rows(external)}
    if len(n)!=len(e) or len(n)!=len(manifest) or len(n)!=1716:raise ValueError("manifest drift")
    result=[];added=[];id_agreement=Counter()
    for m in manifest:
        k=key(m);old=n[k];ex=e[k]
        if old["status"] in BASE_EXACT and ex["status"]=="FC25_MODEL_MATCHED_HISTORICAL":
            id_agreement["same" if old["we_id"]==ex["ea_player_id"] else "different"]+=1
        row=dict(old)
        if old["status"] not in BASE_EXACT:
            method,w=choose(m,old,ex,bydob)
            if w:
                vals=decode(w)
                row.update(status=method,we_id=w["Id"],source_birthday=w["Birthday"],source_name=w["Name"],source_club=w["Club"],source_nation=w["Nation"],source=SOURCE,raw_preset="/".join(str(w[f] or "") for f in FIELD_NAMES))
                row.update(dict(zip(FIELDS,vals)))
                added.append({"team":m["team_id"],"player":m["player_name"],"matched_name":w["Name"],"method":method,"dob":date(m["dob_candidate"]),"we_id":w["Id"],"ea_id":ex["ea_player_id"],"source_link":str(w["Link"] or "")})
        result.append(row)
    out.mkdir(parents=True,exist_ok=True)
    with (out/"we2002_native_appearance_matches.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]));w.writeheader();w.writerows(result)
    confirmed=[r for r in result if r["status"] in BASE_EXACT|ADDED]
    report={"status":"SOURCE_IDENTITY_REFINEMENT_RUNTIME_PENDING","slots":len(result),
        "counts":dict(Counter(r["status"] for r in result)),"confirmed_candidate_slots":len(confirmed),
        "complete_candidate_slots":sum(all(r[f] not in (None,"") for f in FIELDS) for r in confirmed),
        "distinct_candidate_we_ids":len({str(r["we_id"]) for r in confirmed}),
        "newly_resolved":len(added),"new_method_counts":dict(Counter(r["method"] for r in added)),
        "ea_we_id_agreement_independent_exact_matches":dict(id_agreement),
        "source_link_count":sum(bool(link_id(r["Link"])) for r in data),
        "source_link_examples":[str(r["Link"]) for r in data if link_id(r["Link"])][:3],
        "binary_written":False,"added":added}
    (out/"appearance_identity_refinement.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("REFINEMENT",json.dumps({k:v for k,v in report.items() if k!="added"},ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for x in ("db","native","external","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();main(a.db,a.native,a.external,a.out)
