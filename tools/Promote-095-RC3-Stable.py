#!/usr/bin/env python3
"""Owner-approved promotion of the original RC3 ZIP to stable version 0.9.5.
No game files written; no previous release or test feed changed.
Requires Python 3 and authenticated GitHub CLI. Run with the exact RC3 ZIP
created for the owner on 2026-11-15. Never substitute RC1/RC2.
"""
import argparse, base64, hashlib, json, os, re, struct, subprocess, tempfile, zipfile
from pathlib import Path
REPO="Nevmerlyk/ISS26-Updates"
BASE="D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44"
OLD="2561F1F03745C4E1520E1902E486EF3699DC2B5F190E88A6A0056399F31BE72E"
SECTOR=2352
COUNT=689
ARCHIVE="ISS26_0.9.5_RC3.zip"
SOURCE="ISS26_0.9.5_RC3.iss26p"
DEST="ISS26_0.9.5.iss26p"
CUE="ISS Pro Evolution 2 (Europe) (En,Fr,De).cue"
def require(ok,msg):
    if not ok: raise RuntimeError(msg)
def sha(b):
    return hashlib.sha256(b).hexdigest().upper()
def gh(*args):
    return subprocess.check_output(["gh",*args],text=True,encoding="utf-8")
def api(endpoint):
    return json.loads(gh("api",endpoint))
def feed(channel):
    r=api("repos/"+REPO+"/contents/"+channel+"/latest.json?ref=main")
    return r["sha"],json.loads(base64.b64decode(r["content"]))
def locate_archive(explicit,root):
    if explicit: return explicit
    candidates=[Path.cwd()/ARCHIVE,Path.home()/"Downloads"/ARCHIVE,root/ARCHIVE,
                Path("E:/Downloads")/ARCHIVE,Path("D:/Downloads")/ARCHIVE]
    found=list({p.resolve() for p in candidates if p.is_file()})
    require(len(found)==1,"Pass --archive with the exact RC3 ZIP (missing or ambiguous).")
    return found[0]
def original_track(root,explicit):
    if explicit:return explicit
    cue=root/CUE
    text=cue.read_text(encoding="utf-8-sig", errors="replace")
    files=re.findall(r'^\s*FILE\s+"([^"]+)"\s+BINARY\s*$',text,re.I|re.M)
    require(len(files)==12,"Original CUE must contain the 12 original tracks")
    return cue.parent/files[0]
def extract_patch(archive):
    require(archive.name.lower()==ARCHIVE.lower(),"Not the original RC3 archive name")
    with zipfile.ZipFile(archive) as z:
        matches=[m for m in z.infolist() if Path(m.filename).name.lower()==SOURCE.lower()]
        require(len(matches)==1,"Expected exactly one named RC3 patch; no fallback")
        m=matches[0]
        require(m.file_size==12+COUNT*(36+SECTOR),"Unexpected RC3 size")
        data=z.read(m)
        require(data[:8]==b"ISS26X01" and struct.unpack_from("<I",data,8)[0]==COUNT,
                "Not the expected 689-sector patch format")
        # The original ZIP's reports/publisher may carry the hash in text.
        # Return them for cross-check when available; no arbitrary code is executed.
        docs=[]
        for m in z.infolist():
            if m.file_size<=128*1024 and Path(m.filename).suffix.lower() in (".json",".ps1",".txt",".cmd",".py"):
                docs.append(z.read(m).decode("utf-8-sig",errors="replace").upper())
        return data,"\n".join(docs)
def replay(track,patch):
    h=hashlib.sha256();out=hashlib.sha256()
    count=struct.unpack_from("<I",patch,8)[0]
    size=track.stat().st_size
    require(size%SECTOR==0,"Invalid raw disc size")
    with track.open("rb") as f:
        pos=0
        def unchanged(n):
            while n:
                b=f.read(min(n,4*1024*1024))
                require(b,"Unexpected disc EOF")
                h.update(b);out.update(b);n-=len(b)
        for i in range(count):
            at=12+i*(36+SECTOR)
            lba=struct.unpack_from("<I",patch,at)[0]
            off=lba*SECTOR
            require(pos<=off and off+SECTOR<=size,"Unsorted, duplicate or out-of-range sector")
            unchanged(off-pos)
            raw=f.read(SECTOR)
            require(len(raw)==SECTOR and hashlib.sha256(raw).digest()==patch[at+4:at+36],
                    "Original sector guard failed at LBA "+str(lba))
            h.update(raw)
            new=bytes(a^b for a,b in zip(raw,patch[at+36:at+36+SECTOR]))
            out.update(new);pos=off+SECTOR
        unchanged(size-pos)
    require(h.hexdigest().upper()==BASE,"Wrong clean original Track01 SHA256")
    return out.hexdigest().upper()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path);p.add_argument("--root",type=Path,default=Path(r"D:\ISS 26"))
    p.add_argument("--track",type=Path)
    a=p.parse_args()
    archive=locate_archive(a.archive,a.root)
    data,docs=extract_patch(archive)
    digest=sha(data)
    require(digest!=OLD,"RC1 substitution refused")
    result=replay(original_track(a.root,a.track),data)
    require(digest in docs and result in docs,
        "RC3 package does not contain matching patch and result hashes in its text reports. Stop; verify original archive.")
    print("Verified original, RC3 package hashes and all",COUNT,"sector guards.",flush=True)
    print("Patch:",digest,"\nResult:",result,flush=True)
    stable_sha,stable=feed("stable");test_sha,_=feed("test")
    current=stable["latest"]["patchSha256"].upper()
    require(current in (OLD,digest),"Stable changed since RC1; no automatic overwrite.")
    # A historical v0.9.5 tag already exists with different contents.
    # Keep it intact, and publish a unique immutable tag with the plain public version.
    tag="v0.9.5-stable-"+digest[:16].lower()
    endpoint="repos/"+REPO+"/releases/tags/"+tag
    with tempfile.TemporaryDirectory(prefix="ISS26-promote-") as td:
        path=Path(td)/DEST;path.write_bytes(data)
        try:r=api(endpoint)
        except subprocess.CalledProcessError:
            gh("release","create",tag,str(path),"--repo",REPO,"--title","ISS26 v0.9.5",
               "--notes","Owner-approved stable 0.9.5: byte-identical RC3. Known residual small-flag and Uzbekistan title issues deferred. No player database or kits included.",
               "--latest=false")
            r=api(endpoint)
        require(not r.get("draft") and not r.get("prerelease"),"Release is not stable")
        matches=[x for x in r["assets"] if x["name"]==DEST]
        require(len(matches)==1,"Release asset missing or ambiguous; no feed change")
        asset=matches[0]
        require(asset["size"]==len(data),"Remote patch size differs")
        # Download from GitHub and verify actual bytes even if digest is unavailable.
        remote_dir=Path(td)/"remote";remote_dir.mkdir()
        gh("release","download",tag,"--repo",REPO,"--pattern",DEST,"--dir",str(remote_dir))
        require(sha((remote_dir/DEST).read_bytes())==digest,"Downloaded release hash differs")
        url="https://github.com/"+REPO+"/releases/download/"+tag+"/"+DEST
        require(asset["browser_download_url"]==url,"Unexpected asset URL")
        new={"schemaVersion":1,"channel":"stable","latest":{"version":"0.9.5","patchUrl":url,
               "patchSha256":digest,"baseSha256":BASE,"resultSha256":result},
             "notes":"Owner-approved promotion of exact RC3 to stable 0.9.5. Verified original sector guards and downloaded release SHA256. Known remaining flag/name defects deferred. No database or kit update."}
        now_sha,now=feed("stable")
        require(now_sha==stable_sha,"Stable changed during publication; stop")
        require(feed("test")[0]==test_sha,"Test channel changed during publication; stop")
        if now!=new:
            request={"message":"Promote exact RC3 to stable ISS26 0.9.5","branch":"main",
                     "sha":stable_sha,"content":base64.b64encode((json.dumps(new,indent=2)+"\n").encode()).decode()}
            manifest=Path(td)/"manifest-request.json"
            manifest.write_text(json.dumps(request),encoding="utf-8")
            gh("api","--method","PUT","repos/"+REPO+"/contents/stable/latest.json","--input",str(manifest))
        require(feed("stable")[1]==new,"Stable feed verification failed")
        require(feed("test")[0]==test_sha,"Test channel changed unexpectedly")
    print("SUCCESS: exact RC3 published as stable ISS26 0.9.5. Test channel unchanged.")
if __name__=="__main__":
    main()
