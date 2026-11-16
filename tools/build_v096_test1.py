#!/usr/bin/env python3
"""Build local ISS26 0.9.6 names-only test, independently installable on original EU Track01.
No attributes or clubs changed. Never publishes or edits original.
"""
from pathlib import Path
import argparse,csv,hashlib,json,re,tempfile,urllib.request
from integration_preflight_v096 import REG,ROOT,sha,parse_patch,baseline_exe
from integration_merge_eu import merge,fix_form1
PLAN=ROOT/"data/integration/national_name_test1_v096.csv"
PLAN_BLOB="9ec535e651066c9aba7bf6599ed3edca2b2ff84d"
S=2352
def git_blob(path):
    b=path.read_bytes()
    return hashlib.sha1(("blob "+str(len(b))+"\0").encode()+b).hexdigest()
def load_plan(reg):
    if git_blob(PLAN)!=PLAN_BLOB: raise ValueError("Unapproved roster plan")
    rows=list(csv.DictReader(PLAN.open(encoding="utf-8-sig",newline="")))
    teams={r["team_id"]:r for r in reg["national_slots"]}
    if len(rows)!=1188 or len(teams)!=54: raise ValueError("Wrong plan size")
    occupied=set(); labels=set()
    for r in rows:
        t=teams[r["team_id"]]; i=int(r["game_slot"]); off=int(r["exe_offset"])
        if not 1<=i<=22 or int(r["disc_slot"])!=t["disc_slot"] or off!=t["exe_name_offset"]+10*(i-1) or off in occupied:
            raise ValueError("Wrong slot offset")
        name=r["game_label"]
        k=(r["team_id"],name.lower())
        if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,9}",name) or k in labels:
            raise ValueError("Bad or duplicate label")
        if r["role_status"] not in ("PRIMARY","SECONDARY_CANDIDATE"):
            raise ValueError("Unsupported provisional role")
        occupied.add(off);labels.add(k)
    return rows
def sector(f,lba,records):
    f.seek(lba*S);raw=f.read(S)
    if len(raw)!=S: raise ValueError("Truncated sector")
    if lba in records:
        guard,mask=records[lba]
        if hashlib.sha256(raw).digest()!=guard: raise ValueError("Original guard mismatch")
        return bytes(a^b for a,b in zip(raw,mask))
    return raw
def verify_output(track,base,final,reg,expected,touched,report):
    size=reg["original_track_size"]
    before=parse_patch(base,size); after=parse_patch(final,size)
    for lba in before.keys()|after.keys():
        if lba not in touched and before.get(lba)!=after.get(lba):
            raise ValueError("Unrelated sector changed")
    start=reg["national_exe_lba"]; end=start+(len(expected)+2047)//2048
    full=hashlib.sha256(); original=hashlib.sha256(); exe=bytearray()
    with track.open("rb") as f:
        for lba in range(size//S):
            raw=f.read(S)
            if len(raw)!=S: raise ValueError("Truncated original")
            original.update(raw)
            data=raw
            if lba in after:
                guard,mask=after[lba]
                if hashlib.sha256(raw).digest()!=guard: raise ValueError("Guard mismatch")
                data=bytes(a^b for a,b in zip(raw,mask))
            if lba in touched and bytes(fix_form1(bytearray(data)))!=data: raise ValueError("EDC/ECC mismatch")
            if start<=lba<end: exe.extend(data[24:2072])
            full.update(data)
    if original.hexdigest().upper()!=reg["original_track_sha256"] or full.hexdigest().upper()!=report["result_sha256"]:
        raise ValueError("Standalone output digest mismatch")
    if bytes(exe[:len(expected)])!=bytes(expected):raise ValueError("Full EXE readback mismatch")
    if sha(final)!=report["patch_sha256"]:raise ValueError("Patch digest mismatch")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--track",type=Path,required=True)
    p.add_argument("--baseline",type=Path)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    reg=json.loads(REG.read_text(encoding="utf-8"))
    if reg["baseline"]["version"]!="0.9.5":raise ValueError("Wrong stable baseline")
    rows=load_plan(reg)
    a.out.mkdir(parents=True,exist_ok=True)
    target=a.out/"ISS26_Test_0.9.6.iss26p"
    reportfile=a.out/"ISS26_Test_0.9.6.report.json"
    if target.exists() or reportfile.exists():raise ValueError("Refusing overwrite")
    with tempfile.TemporaryDirectory(prefix="iss26-build-") as td:
        tmp=Path(td)
        baseline=a.baseline
        if baseline is None:
            baseline=tmp/"stable095.iss26p"
            with urllib.request.urlopen(reg["baseline"]["url"],timeout=120) as r:
                content=r.read(32*1024*1024+1)
                if len(content)>32*1024*1024:raise ValueError("Oversize baseline")
                baseline.write_bytes(content)
        exe,_=baseline_exe(a.track,baseline,reg)
        expected=bytearray(exe);edits=[]; touched=set(); changed=0
        for r in rows:
            off=int(r["exe_offset"]);old=exe[off:off+10]
            name=old.split(b"\0",1)[0].decode("ascii","strict").strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,9}",name):raise ValueError("Invalid baseline name at "+str(off))
            if b"\0" in old and any(old[old.index(0):]):raise ValueError("Unexpected baseline name padding")
            new=r["game_label"].encode("ascii").ljust(10,b"\0")
            if old==new:continue
            changed+=1;expected[off:off+10]=new
            i=0
            while i<10:
                pos=off+i;n=min(10-i,2048-pos%2048);lba=reg["national_exe_lba"]+pos//2048
                edits.append({"raw_offset":lba*S+24+pos%2048,"expected_hex":old[i:i+n].hex(),"replacement_hex":new[i:i+n].hex()})
                touched.add(lba);i+=n
        if not edits:raise ValueError("No changes")
        ef=tmp/"edits.json";ef.write_text(json.dumps(edits),encoding="utf-8")
        candidate=tmp/"candidate.iss26p"
        report=merge(a.track,baseline,ef,candidate,reg["baseline"]["result_sha256"])
        verify_output(a.track,baseline,candidate,reg,expected,touched,report)
        report.update({"version":"0.9.6","scope":"NATIONAL_NAMES_ONLY","national_slots":len(rows),"changed_names":changed,"attributes_written":0,"club_players_written":0,"bonus_records_written":0,"source_plan_blob":PLAN_BLOB,"status":"STATIC_VALIDATED_NOT_GAMEPLAY_TESTED","runtime_acceptance":False,"channel_published":False,"warning":"Provisional role ordering, existing game attributes unchanged. Not a complete database patch."})
        payload=candidate.read_bytes()
        with target.open("xb") as f:f.write(payload)
        with reportfile.open("x",encoding="utf-8") as f:json.dump(report,f,indent=2)
        print(json.dumps(report,indent=2))
if __name__=="__main__": main()
