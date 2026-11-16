#!/usr/bin/env python3
"""Bulk appearance reference matching, independent of gameplay attributes.
EA FC25 appearance data are historical *game model settings*, not photographs.
FC26 names/DOB may help identify EA IDs, but do not make FC25 appearance current.
Do not identify people from photos; matches use names and dates only.
No writes to a disc, no use of ethnicity or nationality as visual proxies.
"""
import argparse,csv,datetime as dt,hashlib,json,re,unicodedata
from pathlib import Path
from collections import defaultdict,Counter

ROOT=Path(__file__).resolve().parents[1]
RAW=("hairtypecode","hairstylecode","haircolorcode","facialhairtypecode",
     "facialhaircolorcode","skintonecode","bodytypecode","headtypecode",
     "headassetid","hashighqualityhead")
def rows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def norm(s):
    s=unicodedata.normalize("NFKD",str(s or "").translate(str.maketrans({"ł":"l","ø":"o","đ":"d","ß":"ss","Ł":"L","Ø":"O","Đ":"D"}))).encode("ascii","ignore").decode().lower()
    return re.sub("[^a-z0-9]","",s)
def date(v):
    v=str(v or "").strip()
    if not v:return ""
    try:
        if v.isdigit():
            i=int(v)
            # Sofifa snapshot includes Excel serial dates.
            if 20000<i<50000:return (dt.date(1899,12,30)+dt.timedelta(days=i)).isoformat()
        m=re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:$|[ T])",v)
        if m:return dt.date(*map(int,m.groups())).isoformat()
        for fmt in ("%d/%m/%Y","%b %d, %Y","%B %d, %Y"):
            try:return dt.datetime.strptime(v,fmt).date().isoformat()
            except ValueError:pass
    except (ValueError,OverflowError):pass
    return ""
def val(r,*keys):
    return next((str(r[k]).strip() for k in keys if r.get(k) not in (None,"")), "")
def source_id(r):
    v=val(r,"playerid","sofifa_id","player_id","id")
    if not v:
        u=val(r,"player_url","sofifa_url","url")
        m=re.search(r"/player/(\d+)",u)
        v=m.group(1) if m else ""
    if v.endswith(".0"):v=v[:-2]
    return v if v.isdigit() and int(v)>0 else ""
def index_names(r):
    return {norm(v) for v in (val(r,"name","short_name"),val(r,"full_name","long_name"),
            val(r,"short_name"),val(r,"long_name"),val(r,"full_name")) if norm(v)}
def source_index(data,tag):
    idx=defaultdict(list)
    for r in data:
        eid=source_id(r)
        dob=date(val(r,"dob","birth_date","date_of_birth"))
        if not eid or not dob:continue
        for name in index_names(r):
            idx[(name,dob)].append((eid,tag,r))
    return idx
def bit_record(r):
    return {k:int(r[k]) for k in RAW if str(r.get(k,"")).strip().lstrip("-").isdigit()}
def match(manifest,fc25,sofifa,fc26):
    raw={}
    duplicates=set()
    for r in fc25:
        # EA gender 0 in this dump is men's football; do not use women's records.
        if r.get("gender")!="0":continue
        eid=source_id(r)
        if not eid:continue
        if eid in raw:duplicates.add(eid)
        raw[eid]=r
    for eid in duplicates:raw.pop(eid,None)
    a=source_index(sofifa,"FC25_SOFIFA_NAME_DOB")
    b=source_index(fc26,"FC26_NAME_DOB_TO_FC25_MODEL")
    result=[]
    for m in manifest:
        key=(norm(m["player_name"]),date(m["dob_candidate"]))
        options=a.get(key,[])+b.get(key,[])
        # Reject conflicted roster DOB; prefer exact name+date; no fuzzy or nationality match.
        ids={x[0] for x in options}
        status="NO_EXACT_NAME_DOB_SOURCE"
        fields={}
        eid=""
        tags=[]
        if m["identity_status"]=="DOB_CONFLICT_REVIEW":
            status="ROSTER_DOB_CONFLICT"
        elif not key[1]:
            status="MISSING_DOB"
        elif len(ids)>1:
            status="AMBIGUOUS_EA_ID"
        elif len(ids)==1:
            eid=next(iter(ids))
            tags=sorted({x[1] for x in options})
            if eid not in raw:status="EA_ID_NO_FC25_MODEL"
            else:
                # EA database birthdate encoding is checked against source DOB.
                rawdate=raw[eid].get("birthdate","")
                try:
                    rd=(dt.date(1582,10,14)+dt.timedelta(days=int(rawdate))).isoformat()
                except (ValueError,OverflowError):rd=""
                if rd!=key[1]:
                    status="EA_RAW_DOB_MISMATCH"
                else:
                    fields=bit_record(raw[eid])
                    if len(fields)!=len(RAW):status="INCOMPLETE_EA_VISUAL_FIELDS"
                    else:status="FC25_MODEL_MATCHED_HISTORICAL"
        result.append({"team_id":m["team_id"],"player_name":m["player_name"],"roster_uid":m["roster_uid"],
                       "dob":key[1],"ea_player_id":eid,"status":status,"identity_sources":";".join(tags),
                       "source_model_year":2025 if fields else "",**fields,
                       "existing_visual_reference":m["existing_visual_reference"]})
    return result
def crosswalk_candidates(matched,profiles):
    # Only record anchor-derived proposals, never auto-approve a numeric map.
    # Retain "hashighqualityhead" because generic settings can differ from scanned faces.
    key={(r["team_id"],norm(r["player_name"])):r for r in matched}
    proposals=defaultdict(lambda:defaultdict(list))
    pairs=[("hairtypecode",0),("haircolorcode",1),("facialhairtypecode",2),
           ("facialhaircolorcode",3),("skintonecode",4),("bodytypecode",5)]
    for p in profiles:
        r=key.get((p["team"],norm(p["name"])))
        if not r or r["status"]!="FC25_MODEL_MATCHED_HISTORICAL":continue
        for raw,i in pairs:
            target=p["values"][i]
            if target is not None:
                proposals[raw][str(r[raw])].append({"target":target,"player":p["name"],
                    "ea_id":r["ea_player_id"],"high_quality_head":r["hashighqualityhead"],
                    "source":p["source"]})
    return {k:{c:{"anchors":v,"target_counts":dict(Counter(x["target"] for x in v)),
                  "status":"CONFLICT" if len({x["target"] for x in v})>1 else "UNVERIFIED_CANDIDATE"}
               for c,v in vs.items()} for k,vs in proposals.items()}
def main(src,out):
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    fc25,sofifa,fc26=[rows(src/f) for f in ("players.csv","sofifa.csv","fc26.csv")]
    if not set(RAW)<=set(fc25[0]):raise ValueError("missing FC25 model fields")
    matched=match(manifest,fc25,sofifa,fc26)
    if len(matched)!=1716:raise ValueError("wrong roster population")
    profiles=json.loads((ROOT/"data/integration/v096_appearance_profiles_v2.json").read_text())["profiles"]
    cross=crosswalk_candidates(matched,profiles)
    hits=[x for x in matched if x["status"]=="FC25_MODEL_MATCHED_HISTORICAL"]
    report={"status":"SOURCE_MODEL_MATCHING_NOT_APPEARANCE_PATCH","rows":len(matched),
        "counts":dict(Counter(x["status"] for x in matched)),
        "matched_distinct_ea_ids":len({x["ea_player_id"] for x in hits}),
        "matched_by_team":dict(Counter(x["team_id"] for x in hits)),
        "source_headers": {"fc25":list(fc25[0]),"sofifa":list(sofifa[0]),"fc26":list(fc26[0])},
        "crosswalk":cross,"crosswalk_approved":False,
        "notes":["FC25 is a mid-2025 model snapshot, not a November 2026 photo observation.",
            "Unique exact normalized name and DOB required; no biometric matching or appearance inference from nationality.",
            "FC26 CSV only used for identity, not treated as an appearance source.",
            "Raw appearance codes not written into ISS; mappings require catalog/render verification."]}
    out.mkdir(parents=True,exist_ok=True)
    cols=["team_id","player_name","roster_uid","dob","ea_player_id","status","identity_sources","source_model_year",*RAW,"existing_visual_reference"]
    with (out/"fc25_appearance_matches.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(matched)
    (out/"appearance_mapping_candidates.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("RESULT",json.dumps({k:v for k,v in report.items() if k not in ("crosswalk","source_headers","matched_by_team")},ensure_ascii=False))
    print("CROSSWALK",json.dumps(cross,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    main(a.source,a.out)
