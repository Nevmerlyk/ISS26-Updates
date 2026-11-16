#!/usr/bin/env python3
"""Recreate the exact historical revised roster/readback using an owner's clean PAL disc.
No downloads, no feed writes, no original disc redistribution.
Requires Python 3 and scipy (assignment algorithm used in original build).
Fails closed on any output hash drift, including different assignment tie breaks.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from integration_merge_eu import BASE_SHA, BASE_SIZE
from audit_v096_nationality_refs import digest
from reconstruct_v096_internal import FINAL_SHA, RESULT_SHA, verify_track
from integration_merge_eu import parse_patch

ROOT=Path(__file__).resolve().parents[1]
NAMES_ONLY="5EC84C0C6B31F503DECD9FF2AD37B40A65EFEF3CF5CD593A1A98992368326D11"
TWO_GK="34DCBA82744C0B3456556C0CFB14F2EAD78E770BCA03BD97A3947B558C67E91B"
FILES=("data/fm26/ISS26_complete_working_pool_v20.csv",
       "data/integration/national_name_test1_v096.csv",
       "data/integration/active_club_roster_candidates_v21.csv",
       "data/integration/club_roster_supplement_v21.csv",
       "data/integration/active_club_registry_v21.json",
       "data/integration/eu_v096_registry.json",
       "data/integration/fm26_nationality_roster_extract_v22.csv",
       "tools/integration_merge_eu.py")

def need(condition,message):
    if not condition:
        raise ValueError(message)

def replace_once(s,old,new):
    need(s.count(old)==1,"historical source anchor drift")
    return s.replace(old,new,1)

def run(work,script,*argv):
    subprocess.run([sys.executable,str(work/script),*map(str,argv)],cwd=work,check=True)

def main(track,carrier,work):
    need(track.stat().st_size==BASE_SIZE and digest(track)==BASE_SHA,"wrong original Track01")
    need(digest(carrier)==NAMES_ONLY,"wrong original names-only patch input")
    need(importlib.util.find_spec("scipy") is not None,"install scipy in the Python environment first")
    need(not work.exists() or not any(work.iterdir()),"use a new empty work directory")
    work.mkdir(parents=True,exist_ok=True)
    bundle=json.loads((ROOT/"data/integration/v096_revision_internal_bundle.json").read_text())
    for name in FILES:
        dst=work/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(ROOT/name,dst)
    # Two historical source scripts expected these files one directory higher.
    for name in ("eu_v096_registry.json","fm26_nationality_roster_extract_v22.csv"):
        shutil.copyfile(work/"data/integration"/name,work/"data"/name)
    for script in ("revise_rosters.py","citizenship_registry.py","build_2gk_internal.py","appearance_trial.py"):
        s=bundle[script]
        if script=="build_2gk_internal.py":
            s=replace_once(s,"BASE=Path('/mnt/data/v096_build/ISS26_Test_0.9.6.iss26p')","BASE=Path(sys.argv[2])")
        if script in ("build_2gk_internal.py","appearance_trial.py"):
            s=replace_once(s,"TRACK=Path(glob.glob('/mnt/data/*Track 01*.bin')[0])","TRACK=Path(sys.argv[1])")
        (work/script).write_text(s,encoding="utf-8")
    run(work,"revise_rosters.py")
    changes=work/"revision/goalkeeper_replacements.csv"
    def read_text_csv(text):
        return list(csv.DictReader(text.splitlines()))
    need(read_text_csv(changes.read_text(encoding="utf-8-sig"))==
         read_text_csv(bundle["revision/goalkeeper_replacements.csv"]),"goalkeeper changes drift")
    run(work,"citizenship_registry.py")
    old=json.loads(bundle["revision/citizenship_registry.json"])
    new=json.loads((work/"revision/citizenship_registry.json").read_text(encoding="utf-8"))
    need(old==new,"citizenship source registry drift")
    run(work,"build_2gk_internal.py",track,carrier)
    need(digest(work/"output/ISS26_0.9.6_2GK_INTERNAL.iss26p")==TWO_GK,"2GK patch hash drift")
    run(work,"appearance_trial.py",track)
    patch=work/"output/ISS26_0.9.6_2GK_APPEARANCE_INTERNAL.iss26p"
    need(digest(patch)==FINAL_SHA,"appearance patch hash drift")
    verified=verify_track(track,parse_patch(patch))
    readback=work/"output/roster_readback.csv"
    rows=read_text_csv(readback.read_text(encoding="utf-8-sig"))
    need(len(rows)==1716,"readback length drift")
    report={"status":"EXACT_INTERNAL_INPUTS_RECREATED_NOT_RELEASED","version":"0.9.6",
            "patch":str(patch),"patch_sha256":FINAL_SHA,"result_sha256":RESULT_SHA,"sector_guards":verified,
            "readback":str(readback),"readback_sha256":digest(readback),
            "citizenship_candidates":str(work/"revision/citizenship_candidates.csv"),
            "runtime_verified":False,"feed_changed":False}
    (work/"output/reproduction_report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("track","carrier","work"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    main(a.track.resolve(),a.carrier.resolve(),a.work.resolve())
