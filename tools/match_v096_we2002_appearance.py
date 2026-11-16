#!/usr/bin/env python3
"""Match the community WE2002 appearance database against ISS26 identity manifest.
The database is opened read-only. No executable, assets, faces, or photos are copied.
The WE2002 editor's UI-to-index encoding is a compatibility candidate for EU ISS:
do not apply automatically until the native template IDs are verified in the PAL game.
"""
import argparse,csv,json,sqlite3,re,datetime as dt
from pathlib import Path
from collections import Counter,defaultdict
from match_v096_external_appearance import norm,date,rows
ROOT=Path(__file__).resolve().parents[1]
HAIR="a1 a2 a3 b1 b2 b3 b4 b5 b6 c1 c2 d1 d2 e1 e2 f1 f2 f3 g1 h1 i1 i2 i3 j1 k1 l1 l2 l3 m1 n1 o1 p1".split()
FIELD_NAMES=("Hair","HairColor","HairFace","HairColorFace","SkinColor","Body")
OPTIONS=(HAIR,list("abcdefgh"),list("abcdefg"),list("abcdefg"),list("abcd"),list("abcdefgh"))
SOURCE="https://github.com/zetaprog/Easy-Mcr-Winning-Eleven-2002-PS1/tree/30af1fe59cf96beee3b066f6cdfcb1b6f3df37cc"
def decode(r):
    values=[]
    for k,options in zip(FIELD_NAMES,OPTIONS):
        v=str(r[k] or "").strip().lower()
        # Use editor display codes only; bare numeric values not assumed index vs one-based.
        values.append(options.index(v) if v in options else None)
    return values
def dbdate(s):
    v=str(s or "").strip()
    d=date(v)
    if d:return d
    m=re.fullmatch(r"(\d{1,2})[.\-](\d{1,2})[.\-](\d{4})",v)
    if m:
        try:return dt.date(int(m[3]),int(m[2]),int(m[1])).isoformat()
        except ValueError:return ""
    return ""
def main(db,out):
    conn=sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True)
    conn.execute("PRAGMA trusted_schema=OFF")
    conn.row_factory=sqlite3.Row
    data=[dict(x) for x in conn.execute("SELECT Id,Name,NAMEWE,Birthday,Club,NationalTeam,Nation,Position,Hair,HairColor,HairFace,HairColorFace,SkinColor,Body,Link FROM Players")]
    conn.close()
    byname=defaultdict(list)
    for x in data:
        if norm(x["Name"]):byname[norm(x["Name"])].append(x)
    manifest=rows(ROOT/"data/integration/v096_appearance_identity_manifest.csv")
    result=[]
    for x in manifest:
        name=x["player_name"]
        d=date(x["dob_candidate"])
        options=byname.get(norm(name),[])
        exact=[r for r in options if d and dbdate(r["Birthday"])==d]
        status="NO_EXACT_NAME"
        selected=None
        if x["identity_status"]=="DOB_CONFLICT_REVIEW":status="ROSTER_DOB_CONFLICT"
        elif options:
            if len(exact)==1:selected=exact[0];status="WE_NAME_DOB_MATCH"
            elif len(exact)>1:
                presets={tuple(decode(r)) for r in exact}
                if len(presets)==1:selected=exact[0];status="WE_NAME_DOB_DUPLICATES_SAME_PRESET"
                else:status="WE_CONFLICTING_PRESETS"
            else:status="WE_NAME_ONLY_REVIEW"
        vals=decode(selected) if selected else [None]*6
        result.append({"team_id":x["team_id"],"player_name":name,"roster_uid":x["roster_uid"],
          "dob":d,"status":status,"we_id":selected["Id"] if selected else "",
          "source_birthday":selected["Birthday"] if selected else "",
          "source_name":selected["Name"] if selected else "",
          "source_club":selected["Club"] if selected else "",
          "source_nation":selected["Nation"] if selected else "",
          "hair":vals[0],"hair_color":vals[1],"facial_hair":vals[2],"facial_color":vals[3],
          "skin_shade":vals[4],"body_type":vals[5],"source":SOURCE if selected else "",
          "raw_preset":"/".join(str(selected[k] or "") for k in FIELD_NAMES) if selected else ""})
    out.mkdir(parents=True,exist_ok=True)
    with (out/"we2002_native_appearance_matches.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=result[0]);w.writeheader();w.writerows(result)
    counts=Counter(r["status"] for r in result)
    hits=[r for r in result if r["status"].startswith("WE_NAME_DOB")]
    full=[r for r in hits if all(r[k] is not None for k in ("hair","hair_color","facial_hair","facial_color","skin_shade","body_type"))]
    report={"status":"WE2002_NATIVE_REFERENCE_NOT_PAL_RUNTIME_VERIFIED","source_rows":len(data),"manifest_rows":len(manifest),
       "counts":dict(counts),"distinct_matched_we_ids":len({r["we_id"] for r in hits}),
       "complete_preset_slots":len(full),"slots_with_any_preset":sum(any(r[k] is not None for k in ("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")) for r in hits),
       "source_date_parse_count":sum(bool(dbdate(r["Birthday"])) for r in data),
       "value_distributions":{k:dict(Counter(str(r[k]) for r in data).most_common(40)) for k in FIELD_NAMES},
       "samples":[{k:r[k] for k in ("Name","Birthday",*FIELD_NAMES)} for r in data[:10]],
       "sample_matched":[r for r in hits if norm(r["player_name"]) in ("lionelmessi","cristianoronaldo","kylianmbappe","manuelneuer","erlinghaaland","mohamedsalah","lamineyamal")],
       "notes":["Source commit May 2026; individual appearance date unknown.","UI option labels and selector indices derived from community editor Frmmcr.designer.vb and Frmmcr.vb. They are not proof of EU PAL compatibility.","No guesses from nationality. Same-name records without DOB verification not promoted.","No external photos or executable code copied; no BIN patch applied."]}
    (out/"we2002_appearance_match_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("WE_RESULT",json.dumps(report,ensure_ascii=False))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();main(a.db,a.out)
