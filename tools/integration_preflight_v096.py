#!/usr/bin/env python3
"""ISS26 European v0.9.6 database preflight. Read-only: never modifies a disc or publishes a patch."""
import argparse, csv, hashlib, json, re, struct, unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REG=ROOT/"data/integration/eu_v096_registry.json"
DB=ROOT/"data/fm26/ISS26_modern_game_slots_v20.csv"
SECTOR=2352

def sha(path):
    with path.open("rb") as f:
        h=hashlib.sha256()
        for chunk in iter(lambda:f.read(4*1024*1024),b""): h.update(chunk)
        return h.hexdigest().upper()

def parse_patch(path,size):
    data=path.read_bytes()
    if data[:8]!=b"ISS26X01" or len(data)<12: raise ValueError("Bad ISS26X01 patch")
    n=struct.unpack_from("<I",data,8)[0]
    if not 0<n<=8192 or len(data)!=12+n*2388: raise ValueError("Bad patch count/size")
    out={}; last=-1
    for i in range(n):
        off=12+2388*i
        lba=struct.unpack_from("<I",data,off)[0]
        if not last<lba<size//SECTOR: raise ValueError("Invalid LBA order")
        out[lba]=(data[off+4:off+36],data[off+36:off+2388]);last=lba
    return out

def baseline_exe(track,patch,reg):
    size=reg["original_track_size"]
    if track.stat().st_size!=size or sha(track)!=reg["original_track_sha256"]: raise ValueError("Wrong original EU Track 01")
    if sha(patch)!=reg["baseline"]["patch_sha256"]: raise ValueError("Wrong RC1 patch")
    records=parse_patch(patch,size)
    full=hashlib.sha256();exe=bytearray()
    start=reg["national_exe_lba"];count=(339968+2047)//2048
    with track.open("rb") as f:
        for lba in range(size//SECTOR):
            raw=f.read(SECTOR)
            if len(raw)!=SECTOR: raise ValueError("Short track")
            if lba in records:
                guard,mask=records[lba]
                if hashlib.sha256(raw).digest()!=guard: raise ValueError("Sector SHA mismatch")
                raw=bytes(a^b for a,b in zip(raw,mask))
            full.update(raw)
            if start<=lba<start+count:
                if raw[15]!=2 or raw[18]&32 or raw[16:20]!=raw[20:24]: raise ValueError("Executable sector not mode2 form1")
                exe.extend(raw[24:2072])
    if full.hexdigest().upper()!=reg["baseline"]["result_sha256"]: raise ValueError("RC1 image digest mismatch")
    if exe[:8]!=b"PS-X EXE": raise ValueError("Executable signature mismatch")
    return bytes(exe[:339968]),len(records)

def short_names(rows):
    # Provisional transliteration only. Explicit review required before names are written.
    used=set(); result=[]
    for row in rows:
        n=unicodedata.normalize("NFKD",row["player_name"])
        n=n.translate(str.maketrans({"ł":"l","Ł":"L","ø":"o","Ø":"O","ß":"ss","Đ":"D","đ":"d"}))
        n=n.encode("ascii","ignore").decode()
        n=re.sub(r"[^A-Za-z .'-]","",n).strip()
        if not n: raise ValueError("Empty name")
        parts=n.split();last=parts[-1]
        candidates=[n,last]
        if len(parts)>1: candidates += [parts[0][0]+"."+last]
        candidates+=[last[:10]]
        if len(parts)>1:candidates += [parts[0][0]+"."+last[:8]]
        candidates += [last[:8]+str(i) for i in range(2,100)]
        name=next((v for v in candidates if len(v)<=10 and v.lower() not in used and v[0].isalpha()),None)
        if not name: raise ValueError("Name collision")
        used.add(name.lower()); result.append(name)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--track",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    reg=json.loads(REG.read_text(encoding="utf-8"))
    rows=list(csv.DictReader(DB.open(encoding="utf-8-sig",newline="")))
    attrs=[k for k in rows[0] if k.startswith("game_iss_")]
    teams={}
    for row in rows:
        teams.setdefault(row["team_id"],[]).append(row)
        if len(attrs)!=15 or any(not 12<=int(row[k])<=19 for k in attrs): raise ValueError("Invalid database attribute")
    if len(rows)!=1716 or len(teams)!=78: raise ValueError("Wrong database dimensions")
    for team,rr in teams.items():
        if sorted(int(r["game_slot"]) for r in rr)!=list(range(1,23)): raise ValueError("Bad slot indices "+team)
        if sum(r["game_position"]=="GK" for r in rr)<2: raise ValueError("Insufficient GKs "+team)
    national=reg["national_slots"]
    if len(national)!=54 or {r["team_id"] for r in national}!={k for k in teams if k.startswith("NAT_")}: raise ValueError("National map mismatch")
    exe,n=baseline_exe(a.track,a.baseline,reg)
    result=[]
    for t in national:
        rr=sorted(teams[t["team_id"]],key=lambda r:int(r["game_slot"]))
        for i,(row,name) in enumerate(zip(rr,short_names(rr))):
            off=t["exe_name_offset"]+i*10
            old=exe[off:off+10]
            label=old.split(b"\0",1)[0].decode("ascii","strict").strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z .'-]{0,9}",label): raise ValueError("Unexpected name "+repr(label))
            result.append({"team_id":t["team_id"],"disc_slot":t["disc_slot"],"game_slot":i+1,"old_label":label,"candidate_label":name,"new_player":row["player_name"],"game_position":row["game_position"],"exe_offset":off,"expected_hex":old.hex(),"candidate_hex":name.encode().ljust(10,b"\0").hex(),"status":"NOT_APPLIED_ROLE_LINKAGE_PENDING"})
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/"national_name_preflight.csv").open("w",encoding="utf-8-sig",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(result[0]));writer.writeheader();writer.writerows(result)
    report={"status":"PREFLIGHT_ONLY_NO_PATCH","original_sha256":reg["original_track_sha256"],"baseline_result_sha256":reg["baseline"]["result_sha256"],"baseline_records":n,"modern_rows":len(rows),"national_name_candidates":len(result),"club_rows_awaiting_layout":528,"bonus_records_preserve":88,"blocked_by":["player attribute bit mapping","club name banks and club ID linkage","nation roster order to skill/position records","age/height/foot encoding and weight support","formation alignment","runtime validation"],"publish":False}
    (a.out/"preflight.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()
