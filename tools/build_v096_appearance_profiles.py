#!/usr/bin/env python3
"""Appearance-only candidate build for the exact ISS26 0.9.6 internal revision.

Requires owner's clean EU Track01 and exact 0.9.6 readback; no ROM redistribution.
Only the six previously observed candidate visual fields are writable. Null
values preserve original bits. All other fields, rosters and bonus players
remain unchanged. Numeric templates are provisional pending in-game review.
"""
import argparse
import json
import struct
from pathlib import Path
from collections import defaultdict
from audit_v096_nationality_refs import (
    ROOT,S,R,OFF,NA,EA,EN,NN,SELECT_LBA,SELECT_LEN,EXE_LBA,EXE_LEN,
    INTERNAL_SHA,digest,resource,refs,extra,norm,need,csvrows,label)
from integration_merge_eu import BASE_SHA,BASE_SIZE,parse_patch,merge
from reconstruct_v096_internal import RESULT_SHA

FIELDS=((4,5),(9,4),(13,4),(17,3),(32,2),(34,3))
FIELD_NAMES=("hair","hair_color","facial_hair","facial_color","skin_shade","body_type")
MASK=sum(((1<<w)-1)<<s for s,w in FIELDS)

def decode_visual(record):
    need(len(record)==12,"wrong record length")
    k=int.from_bytes(record,"little")
    return [(k>>s)&((1<<w)-1) for s,w in FIELDS]

def visual_edit(record,values):
    need(len(record)==12 and len(values)==6,"invalid appearance shape")
    old=int.from_bytes(record,"little")
    k=old
    selected_mask=0
    for (s,w),v in zip(FIELDS,values):
        if v is None:
            continue
        need(type(v) is int and 0<=v<1<<w,"invalid appearance ID")
        m=((1<<w)-1)<<s
        selected_mask|=m
        k=(k&~m)|(v<<s)
    need((old^k)&~selected_mask==0,"nonselected field changed")
    return k.to_bytes(12,"little")

def build(track,baseline,readback,out):
    need(track.stat().st_size==BASE_SIZE and digest(track)==BASE_SHA,"wrong clean original disc")
    need(digest(baseline)==INTERNAL_SHA,"wrong exact internal 0.9.6 baseline")
    p=parse_patch(baseline)
    orig=resource(track,{},SELECT_LBA,SELECT_LEN)
    sel=resource(track,p,SELECT_LBA,SELECT_LEN)
    exe=resource(track,p,EXE_LBA,EXE_LEN)
    offsets=struct.unpack_from("<118H",orig,OFF)
    need(orig[OFF:OFF+236]==sel[OFF:OFF+236],"offset table changed")
    old,active=refs(orig),refs(sel)
    need(len(set(old))==len(set(active))==528,"club reference collision")
    native={(h,l):offsets[h]+l-22 for h,l in old if extra((h,l))}
    need(len(native)==len(set(native.values()))==315 and all(0<=i<341 for i in native.values()),"native reference drift")
    need(sum(x in native for x in active)==301,"unexpected active extra count")
    national=json.loads((ROOT/"data/integration/eu_v096_registry.json").read_text())
    clubs=json.loads((ROOT/"data/integration/active_club_registry_v21.json").read_text())
    natids={x["team_id"]:53-x["disc_slot"] for x in national["national_slots"]}
    clubids={x["team_id"]:23-x["ordinal"] for x in clubs["menu_order"]}
    rows=csvrows(readback)
    byname=defaultdict(list)
    byref=defaultdict(list)
    seen=set()
    posmap=defaultdict(list)
    addresses={}
    for r in rows:
        team,slot=r["team_id"],int(r["slot"])
        need(1<=slot<=22 and (team,slot) not in seen,"bad or duplicate slot")
        seen.add((team,slot))
        ref=tuple(bytes.fromhex(r["ref"]))
        need(len(ref)==2,"wrong reference length")
        h,l=ref
        if team in natids:
            need(ref==(natids[team],slot-1) and r["record_type"]=="NATIONAL","national reference drift")
        else:
            need(team in clubids and active[clubids[team]*22+slot-1]==ref,"club reference drift")
            need(r["record_type"]==("CLUB_EXTRA" if ref in native else "SHARED_NATIONAL"),"club record type drift")
        if ref in native:
            i=native[ref]
            nm=label(sel,EN+10*i)
            off=EA+12*i
        else:
            need(h<54 and l<22,"bonus or invalid reference")
            i=h*22+l
            nm=label(exe,NN+10*i)
            off=NA+12*i
        need(nm==r["label"] and sel[off]&15==int(r["position"]),"roster readback mismatch")
        byname[team,norm(r["player_name"])].append(r)
        byref[ref].append(r)
        addresses[ref]=off
        posmap[team].append(int(r["position"]))
    need(len(rows)==1716 and len(byref)==1489 and len(posmap)==78,"wrong modern roster population")
    need(all(len(v)==22 and v.count(0)==2 for v in posmap.values()),"2GK roster constraint broken")
    data=json.loads((ROOT/"data/integration/v096_appearance_profiles_v2.json").read_text())
    need(tuple(data["fields"])==FIELD_NAMES,"field schema drift")
    new=bytearray(sel)
    profiles=[]
    claimed=set()
    edits=[]
    for profile in data["profiles"]:
        matches=byname[profile["team"],norm(profile["name"])]
        need(len(matches)==1,"missing or ambiguous visual identity: "+profile["name"])
        r=matches[0]
        ref=tuple(bytes.fromhex(r["ref"]))
        need(ref not in claimed,"duplicate physical player profile")
        claimed.add(ref)
        off=addresses[ref]
        prev=sel[off:off+12]
        after=visual_edit(prev,profile["values"])
        new[off:off+12]=after
        linked=[{"team":x["team_id"],"slot":int(x["slot"]),"player":x["player_name"]} for x in byref[ref]]
        profiles.append({"name":profile["name"],"team":profile["team"],"ref":r["ref"],
                         "previous":decode_visual(prev),"new":decode_visual(after),
                         "changed":prev!=after,"linked_slots":linked,
                         "source":profile["source"],"status":"NATIVE_TEMPLATE_RUNTIME_PENDING"})
        for i,(a,b) in enumerate(zip(prev,after)):
            if a!=b:
                j=off+i
                edits.append({"raw_offset":(SELECT_LBA+j//2048)*S+24+j%2048,
                              "expected_hex":f"{a:02x}","replacement_hex":f"{b:02x}"})
    legal={addresses[ref]+i for ref in claimed for i in range(12)}
    need(all(i in legal for i,(a,b) in enumerate(zip(sel,new)) if a!=b),"unrelated byte changed")
    need(refs(new)==active,"roster refs changed")
    need(new[NA+1188*12:EA]==sel[NA+1188*12:EA],"bonus player bits changed")
    out.mkdir(parents=True,exist_ok=True)
    report={"status":"APPEARANCE_CANDIDATE_RUNTIME_REQUIRED","profiles":profiles,
            "profiles_count":len(profiles),"changed_physical_records":sum(x["changed"] for x in profiles),
            "covered_slots":sum(len(x["linked_slots"]) for x in profiles),
            "unreviewed_physical_records":len(byref)-len(profiles),
            "feed_changed":False,"runtime_verified":False}
    if edits:
        ed=out/"appearance_edits.json"
        ed.write_text(json.dumps(edits))
        target=out/"ISS26_0.9.6_APPEARANCE_INTERNAL.iss26p"
        report["patch"]=merge(track,baseline,ed,target,RESULT_SHA)
        final=parse_patch(target)
        need(resource(track,final,SELECT_LBA,SELECT_LEN)==new,"SELECT readback drift")
        need(resource(track,final,EXE_LBA,EXE_LEN)==exe,"EXE changed")
        touched=set(report["patch"]["edited_sectors"])
        need(all(final.get(k)==p.get(k) for k in set(final)|set(p) if k not in touched),"unrelated sector drift")
    else:
        report["status"]="NO_NEW_CHANGES_NEEDED"
    (out/"appearance_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("track","baseline","readback","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(build(a.track,a.baseline,a.readback,a.out),indent=2,ensure_ascii=False))
