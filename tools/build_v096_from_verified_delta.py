#!/usr/bin/env python3
"""Build a manual test from stable 0.9.5 XOR patch and clean verified name-bank delta.
No disc bytes are stored in repository. Linear Form1 EDC/ECC parity is recalculated
on XOR masks. Full result image digest is NOT available without the original disc.
"""
from pathlib import Path
import argparse,csv,hashlib,json,struct
from integration_merge_eu import parse_patch,edc,ecc,BASE_SIZE
ROOT=Path(__file__).resolve().parents[1]
S=2352
def digest(b):return hashlib.sha256(b).hexdigest()
def repair_mask(s):
    if len(s)!=S or any(s[:24]):raise ValueError("Sector header/subheader delta not supported")
    s[2072:2076]=edc(s[16:2072])
    s[2076:2248]=ecc(s,86,24,2,86)
    s[2248:2352]=ecc(s,52,43,86,88)
    return s
def build(base,out):
    reg=json.loads((ROOT/"data/integration/eu_v096_registry.json").read_text())
    meta=json.loads((ROOT/"data/integration/v096_names_original_delta.json").read_text())
    if reg["baseline"]["patch_sha256"].lower()!=digest(base.read_bytes()):raise ValueError("Wrong stable patch digest")
    if meta["track_sha256"]!=reg["original_track_sha256"].lower():raise ValueError("Wrong original track pin")
    pp=ROOT/"data/integration/national_name_test1_v096.csv"; raw=pp.read_bytes()
    if hashlib.sha1(("blob "+str(len(raw))+"\0").encode()+raw).hexdigest()!=meta["plan_blob"]:raise ValueError("Plan changed")
    rows=sorted(csv.DictReader(pp.open(encoding="utf-8",newline="")),key=lambda r:int(r["exe_offset"]))
    if len(rows)!=1188 or [int(r["exe_offset"]) for r in rows]!=list(range(293204,305084,10)):raise ValueError("Name offsets mismatch")
    target=b"".join(r["game_label"].encode("ascii").ljust(10,b"\0") for r in rows)
    delta=bytes.fromhex(meta["xor_hex"])
    if len(target)!=11880 or len(delta)!=len(target):raise ValueError("Name length mismatch")
    old=bytes(a^b for a,b in zip(target,delta))
    if digest(old)!=meta["original_bank_sha256"]:raise ValueError("Original name-bank digest mismatch")
    records=parse_patch(base)
    updated=dict(records); touched=set()
    for i,guard_hex in enumerate(meta["guards"]):
        lba=meta["start_lba"]+i;guard=bytes.fromhex(guard_hex)
        assert len(guard)==32
        if lba in records:
            prior_guard,prior=records[lba]
            if prior_guard!=guard or bytes(repair_mask(bytearray(prior)))!=prior:raise ValueError("Baseline guard/parity mismatch: "+str(lba))
        else:prior=bytes(S)
        start=max(0,i*2048-meta["start_user_offset"])
        end=min(len(delta),(i+1)*2048-meta["start_user_offset"])
        pos=24+meta["start_user_offset"]+start-i*2048
        mask=bytearray(prior);mask[pos:pos+end-start]=delta[start:end]
        mask=bytes(repair_mask(mask))
        if mask[:pos]!=prior[:pos] or mask[pos+end-start:2072]!=prior[pos+end-start:2072]:raise ValueError("Unexpected nonname byte difference")
        if any(mask):updated[lba]=(guard,mask)
        else:updated.pop(lba,None)
        touched.add(lba)
    for lba in records.keys()|updated.keys():
        if lba not in touched and records.get(lba)!=updated.get(lba):raise ValueError("Unrelated sector changed")
    if not 0<len(updated)<=8192:raise ValueError("Wrong patch count")
    out.mkdir(parents=True,exist_ok=True)
    path=out/"ISS26_Test_0.9.6.iss26p"
    with path.open("wb") as f:
        f.write(b"ISS26X01"+struct.pack("<I",len(updated)))
        for lba,(guard,mask) in sorted(updated.items()):
            f.write(struct.pack("<I",lba)+guard+mask)
    check=parse_patch(path)
    if check!=updated:raise ValueError("patch readback failed")
    bank=bytearray()
    for i,guard in enumerate(meta["guards"]):
        lba=meta["start_lba"]+i;m=check[lba][1]
        if bytes(repair_mask(bytearray(m)))!=m:raise ValueError("Final parity mismatch")
        bank.extend(m[24:2072])
    bank=bank[meta["start_user_offset"]:meta["start_user_offset"]+len(old)]
    if bytes(a^b for a,b in zip(old,bank))!=target:raise ValueError("Final name readback mismatch")
    report={"version":"0.9.6-test1","status":"MANUAL_PRERELEASE_NAMES_ONLY_STATIC_SECTOR_QA","patch_sha256":digest(path.read_bytes()),"baseSha256":meta["track_sha256"],"baseline_patch_sha256":digest(base.read_bytes()),"baseline_records":len(records),"patch_records":len(updated),"name_slots":len(rows),"changed_sectors":sorted(touched),"verified_full_original_track_hash_on_local_source":True,"original_name_bank_sha256":digest(old),"target_name_bank_sha256":digest(target),"resultSha256":None,"notes":"All non-name baseline user bytes preserved. Original source sectors validated as Mode2 Form1 with EDC/ECC locally. Full final image and emulator not tested; manual installer computes final image SHA. No attributes/clubs changed; original four bonus teams are untouched. Do not update launcher feed without full result image validation."}
    (out/"ISS26_Test_0.9.6.report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--baseline",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();build(a.baseline,a.out)
