#!/usr/bin/env python3
"""Reconstruct precisely the locally verified standalone v0.9.7 patch without a game image.
The GitHub runner receives only published carrier XOR patch and 13-sector XOR delta.
Expected complete-disc result digest was independently obtained on the clean original.
"""
from pathlib import Path
import argparse,base64,hashlib,json,struct,zlib
from integration_merge_eu import parse_patch
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest().upper()
BASE="5EC84C0C6B31F503DECD9FF2AD37B40A65EFEF3CF5CD593A1A98992368326D11"
FINAL="ACBA2D25D505D949D95718092CDE2D23BAF0C361AB17FBF127DB411AD7C3D870"
DELTA="2B5AA9F9E92FC31E11F1D7B1A969204F86CC2922F4F832DC58312283427FAE71"
RESULT="48FFB37D302989052BFD69964E98DBF08E042AD99172062A95DC1CA690398C98"
def build(carrier,out):
    report=json.loads((ROOT/"data/integration/v097_static_report.json").read_text())
    if report["patch"]["patch_sha256"]!=FINAL or report["patch"]["result_sha256"]!=RESULT or report["independent_verification"]["sector_guards_verified"]!=699:raise ValueError("Wrong local QA report")
    if sha(carrier.read_bytes())!=BASE:raise ValueError("Wrong carrier")
    packed=(ROOT/"data/integration/v097_full_roster_delta.zlib.b64").read_text().split()
    d=zlib.decompress(base64.b64decode("".join(packed),validate=True))
    if sha(d)!=DELTA or d[:8]!=b"ISS26D97":raise ValueError("Wrong delta")
    n=struct.unpack_from("<I",d,8)[0]
    if n!=13 or len(d)!=12+n*2388:raise ValueError("Bad delta length")
    records=parse_patch(carrier);original=dict(records);touched=set()
    for i in range(n):
        p=12+i*2388;lba=struct.unpack_from("<I",d,p)[0];guard=d[p+4:p+36];delta=d[p+36:p+2388]
        if lba in touched:raise ValueError("Duplicate delta")
        touched.add(lba)
        if lba in records:
            old_guard,old_mask=records[lba]
            if old_guard!=guard:raise ValueError("Guard drift")
        else:old_mask=bytes(2352)
        mask=bytes(a^b for a,b in zip(old_mask,delta))
        if not any(mask):raise ValueError("Empty sector")
        records[lba]=(guard,mask)
    if touched!=set(report["patch"]["edited_sectors"]) or len(records)!=699:raise ValueError("Wrong patch sectors")
    if any(records.get(i)!=r for i,r in original.items() if i not in touched):raise ValueError("Untargeted change")
    out.mkdir(parents=True,exist_ok=True)
    patch=out/"ISS26_Test_0.9.7.iss26p"
    with patch.open("wb") as f:
        f.write(b"ISS26X01"+struct.pack("<I",len(records)))
        for lba,(guard,mask) in sorted(records.items()):f.write(struct.pack("<I",lba)+guard+mask)
    if parse_patch(patch)!=records or sha(patch.read_bytes())!=FINAL:raise ValueError("Reconstruction failed")
    (out/"ISS26_Test_0.9.7.report.json").write_text(json.dumps(report,indent=2)+"\n")
    print("Verified exactly the local standalone patch",FINAL)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--carrier",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();build(a.carrier,a.out)
