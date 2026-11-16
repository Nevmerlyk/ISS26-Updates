#!/usr/bin/env python3
"""Generate candidate FMPlayer profile paths for UID-bearing queue records.
Paths are hypotheses, never verified links. The importer must validate identity.
"""
import argparse,csv,re,unicodedata
from pathlib import Path

def slug(s):
    s=unicodedata.normalize("NFKD",s).encode("ascii","ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+","-",s).strip("-")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--queue",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    with a.queue.open(encoding="utf-8-sig",newline="") as f:
        queue=list(csv.DictReader(f))
    fields=["team_id","shirt_number","expected_uid","expected_name",
            "expected_nationality","source_url","url_status"]
    rows=[]
    for r in queue:
        uid=r["expected_uid"]
        name=r["player_name"]
        if not uid.isdigit() or not slug(name):continue
        rows.append({"team_id":r["team_id"],"shirt_number":r["shirt_number"],
            "expected_uid":uid,"expected_name":name,"expected_nationality":r["expected_nationality"],
            "source_url":r["source_url"] or f"https://fmplayer.net/fm-26/{slug(name)}-{uid}",
            "url_status":"source_known" if r["source_url"] else "generated_unverified"})
    with a.out.open("x",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    print(f"{len(rows)} candidate paths, {len(queue)-len(rows)} missing UID. Generated paths are NOT verified.")

if __name__=="__main__":main()
