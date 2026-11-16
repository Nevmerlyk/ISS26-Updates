#!/usr/bin/env python3
"""Apply the published v0.9.6 test to a clean original Track 01, preserving audio tracks.
The original and stable game files are read only. Python 3.10+, no dependencies.
"""
import argparse,hashlib,json,struct,re,shutil
from pathlib import Path
S=2352
BASE="d9b483bdea7774346df437febf038e68cb2c4ad9932a7ad993d3c2b1f620ea44"
def sha(p):
    with p.open("rb") as f:
        h=hashlib.sha256()
        for x in iter(lambda:f.read(4194304),b""):h.update(x)
        return h.hexdigest()
def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--cue",type=Path,required=True);a.add_argument("--patch",type=Path,required=True)
    a.add_argument("--report",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    x=a.parse_args(); cue=x.cue.resolve(); report=json.loads(x.report.read_text())
    if report["baseSha256"]!=BASE or report["version"]!="0.9.6-test1" or sha(x.patch)!=report["patch_sha256"]:raise ValueError("Wrong patch/report")
    text=cue.read_text(encoding="utf-8-sig")
    files=re.findall(r'(?im)^\s*FILE\s+"([^"]+)"\s+BINARY\s*$',text)
    if len(files)!=12:raise ValueError("Expected the original 12-track EU CUE")
    orig=[cue.parent/f for f in files]
    if any(not p.is_file() for p in orig) or orig[0].stat().st_size!=496156752 or sha(orig[0])!=BASE:raise ValueError("Wrong or missing clean EU disc")
    patch=x.patch.read_bytes(); n=struct.unpack_from("<I",patch,8)[0]
    if patch[:8]!=b"ISS26X01" or len(patch)!=12+n*2388 or not 0<n<=8192:raise ValueError("Bad patch")
    records={};last=-1
    for i in range(n):
        p=12+i*2388;l=struct.unpack_from("<I",patch,p)[0]
        if not last<l<orig[0].stat().st_size//S:raise ValueError("Bad sector index")
        records[l]=(patch[p+4:p+36],patch[p+36:p+2388]);last=l
    out=x.out.resolve()
    if out.exists():raise ValueError("Choose a new output directory")
    out.mkdir(parents=True)
    names=[f"ISS26_Test_0.9.6_Track{i:02}.bin" for i in range(1,13)]
    try:
        result=hashlib.sha256(); bank=bytearray();start=167;end=173
        with orig[0].open("rb") as src,(out/names[0]).open("xb") as dst:
            for i in range(orig[0].stat().st_size//S):
                raw=src.read(S)
                if i in records:
                    guard,mask=records[i]
                    if hashlib.sha256(raw).digest()!=guard:raise ValueError("Guard failure at sector "+str(i))
                    raw=bytes(a^b for a,b in zip(raw,mask))
                dst.write(raw);result.update(raw)
                if start<=i<end:bank.extend(raw[24:2072])
        pos=293204%2048
        if hashlib.sha256(bank[pos:pos+11880]).hexdigest()!=report["target_name_bank_sha256"]:raise ValueError("Name bank readback failed")
        for src,name in zip(orig[1:],names[1:]):
            shutil.copyfile(src,out/name)
        for old,new in zip(files,names):text=text.replace('"'+old+'"','"'+new+'"')
        (out/"ISS26_Test_0.9.6.cue").write_text(text,encoding="utf-8")
        (out/"result.sha256.txt").write_text(result.hexdigest()+"\n")
        print("Full result SHA256:",result.hexdigest())
        print(out/"ISS26_Test_0.9.6.cue")
    except Exception:
        # Only the newly created output directory belongs to this operation.
        shutil.rmtree(out);raise
if __name__=="__main__":main()
