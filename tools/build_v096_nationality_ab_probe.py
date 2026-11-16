#!/usr/bin/env python3
"""Build a *diagnostic only* nationality A/B probe from an exact 0.9.6 revision.
Never adds IDs, edits flags, modifies a feed, or guesses which record is safe.
Two club-only records swap physical slots AND references, leaving visible
player names, all 96 attribute bits and slot order unchanged.
The nationality renderer is not proven; the probe must be tested in Master League.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from audit_v096_nationality_refs import (ROOT, S, R, OFF, NA, EA, EN, NN,
    SELECT_LBA, SELECT_LEN, EXE_LBA, EXE_LEN, INTERNAL_SHA, digest,
    resource, refs, extra, norm, need, csvrows, label)
from integration_merge_eu import BASE_SHA, BASE_SIZE, parse_patch, merge

RESULT_SHA = "C66A2D63F12CD9130B4E9265670E4DA0D8CC5F40BA7C2B632C0C3048BB114C0F"

def relocated_select(selected, active, native, a, b):
    """Pure byte transform, testable on a synthetic resource."""
    need(len(active)==528 and len(set(active))==528, "invalid club table")
    need(a!=b and a in native and b in native and a[0]!=b[0], "unsafe pair")
    need(active.count(a)==active.count(b)==1, "not uniquely active")
    ia, ib = native[a],native[b]
    need(0<=ia<341 and 0<=ib<341 and ia!=ib, "collision or bad extra index")
    need(refs(selected)==active,"provided reference table drift")
    result=bytearray(selected)
    spans=[]
    for off,size in ((EN,10),(EA,12)):
        pa,pb=off+ia*size,off+ib*size
        result[pa:pa+size]=selected[pb:pb+size]
        result[pb:pb+size]=selected[pa:pa+size]
        spans += [(pa,pa+size),(pb,pb+size)]
    for old,new in ((a,b),(b,a)):
        i=active.index(old)
        result[R+2*i:R+2*i+2]=bytes(new)
        spans.append((R+2*i,R+2*i+2))
    expected=[b if x==a else a if x==b else x for x in active]
    need(refs(result)==expected and len(set(expected))==528,"broken reference table")
    def identity(buf,ref):
        idx=native[ref]
        return (buf[EN+10*idx:EN+10*idx+10],buf[EA+12*idx:EA+12*idx+12])
    for old,new in zip(active,expected):
        if old in native:
            need(new in native and identity(selected,old)==identity(result,new),
                 "player record changed")
        else:
            need(old==new, "shared or bonus ref changed")
    legal={i for a0,b0 in spans for i in range(a0,b0)}
    need(all(i in legal for i,(x,y) in enumerate(zip(selected,result)) if x!=y),
         "unrelated resource byte changed")
    return result,spans

def eligible(source, official):
    """Only keyed identities or explicit profile review; name-only not automatic."""
    if official and official.get("review_status")=="OFFICIAL_COUNTRY_CORROBORATED":
        return official.get("country")==source["country"]
    return source["method"] in ("FM_UID","NATIONAL_UID","PRIOR_MANUAL_PROFILE") and source["status"]=="SOURCE_LINKED_NOT_CERTIFIED"

def pair_candidates(records):
    pairs=[]
    for i,a in enumerate(records):
        for b in records[i+1:]:
            if a["ref"][0]!=b["ref"][0] and a["target"]==b["ref"][0] and b["target"]==a["ref"][0]:
                pairs.append((a,b))
    return pairs

def prepare(track, baseline, readback, out):
    need(track.stat().st_size==BASE_SIZE and digest(track)==BASE_SHA,"wrong clean Track01")
    need(digest(baseline)==INTERNAL_SHA,"expected exact appearance prototype baseline")
    rec=parse_patch(baseline)
    orig=resource(track,{},SELECT_LBA,SELECT_LEN)
    sel=resource(track,rec,SELECT_LBA,SELECT_LEN)
    exe=resource(track,rec,EXE_LBA,EXE_LEN)
    offsets=struct.unpack_from("<118H",orig,OFF)
    need(orig[OFF:OFF+236]==sel[OFF:OFF+236],"offset table drift")
    old,active=refs(orig),refs(sel)
    need(len(set(old))==len(set(active))==528,"club table collision")
    native={}
    for h,l in old:
        if extra((h,l)):
            need(h<len(offsets),"invalid native high byte")
            native[(h,l)]=offsets[h]+l-22
    need(len(native)==len(set(native.values()))==315 and all(0<=i<341 for i in native.values()),"native map drift")
    need(sum(x in native for x in active)==301 and all(not extra(x) or x in native for x in active),
         "unexpected club-only record layout")
    clubreg=json.loads((ROOT/"data/integration/active_club_registry_v21.json").read_text())
    clubids={t["team_id"]:23-t["ordinal"] for t in clubreg["menu_order"]}
    bundle=json.loads((ROOT/"data/integration/v096_revision_internal_bundle.json").read_text())
    countryreg=json.loads(bundle["revision/citizenship_registry.json"])
    known=dict(countryreg["playable_country_id"])
    # This first diagnostic only uses already playable country IDs; extra
    # country flags 106,108,109 still need a separate render proof.
    source=json.loads((ROOT/"data/integration/v096_club_nationality_identity_review.json").read_text())["rows"]
    official=json.loads((ROOT/"data/integration/v096_club_nationality_official_review.json").read_text())["rows"]
    def index(rows):
        d={}
        for r in rows:
            k=(r["team"],norm(r["player"]))
            need(k not in d,"duplicate identity source")
            d[k]=r
        return d
    source,official=index(source),index(official)
    rows=csvrows(readback)
    need(len(rows)==1716,"wrong readback rows")
    clubrows=[r for r in rows if r["team_id"] in clubids]
    need(len(clubrows)==528,"wrong club count")
    checked=set()
    valid=[]
    for r in clubrows:
        t,slot=r["team_id"],int(r["slot"])
        need(1<=slot<=22 and (t,slot) not in checked,"duplicate or invalid slot")
        checked.add((t,slot))
        ref=tuple(bytes.fromhex(r["ref"]))
        need(active[clubids[t]*22+slot-1]==ref,"club readback ref mismatch")
        k=(t,norm(r["player_name"]))
        need(k in source,"unmatched source identity")
        src=source[k]
        if ref not in native:
            need(r["record_type"]=="SHARED_NATIONAL" and ref[0]<54 and ref[1]<22,"unexpected record type")
            i=ref[0]*22+ref[1]
            need(label(exe,NN+10*i)==r["label"] and (sel[NA+12*i]&15)==int(r["position"]),"shared readback drift")
            continue
        idx=native[ref]
        need(r["record_type"]=="CLUB_EXTRA" and label(sel,EN+10*idx)==r["label"]
             and (sel[EA+12*idx]&15)==int(r["position"]),"extra readback drift")
        if src["country"] in known and known[src["country"]]!=ref[0] and eligible(src,official.get(k)):
            valid.append({"team":t,"slot":slot,"player":r["player_name"],"label":r["label"],
                "ref":ref,"country":src["country"],"target":known[src["country"]],
                "position":int(r["position"])})
    pairs=pair_candidates(valid)
    out.mkdir(parents=True,exist_ok=True)
    if not pairs:
        report={"status":"NO_RECIPROCAL_SAFE_PAIR_NO_PATCH","eligible_records":len(valid)}
        (out/"nationality_probe_report.json").write_text(json.dumps(report,indent=2)+"\n")
        return report
    # Prefer a same-club pair so one roster screen can capture both.
    a,b=min(pairs,key=lambda p:(p[0]["team"]!=p[1]["team"],p[0]["team"],p[0]["slot"],p[1]["team"],p[1]["slot"]))
    modified,spans=relocated_select(sel,active,native,a["ref"],b["ref"])
    edits=[]
    for start,end in sorted(spans):
        while start<end:
            stop=min(end,(start//2048+1)*2048)
            if sel[start:stop]!=modified[start:stop]:
                edits.append({"raw_offset":(SELECT_LBA+start//2048)*S+24+start%2048,
                    "expected_hex":sel[start:stop].hex(),"replacement_hex":modified[start:stop].hex()})
            start=stop
    need(bool(edits),"empty probe")
    ed=out/"nationality_probe_edits.json";ed.write_text(json.dumps(edits))
    patch=out/"ISS26_0.9.6_NATIONALITY_AB_INTERNAL.iss26p"
    result=merge(track,baseline,ed,patch,RESULT_SHA)
    new=parse_patch(patch)
    need(resource(track,new,SELECT_LBA,SELECT_LEN)==modified,"post-merge SELECT readback mismatch")
    need(resource(track,new,EXE_LBA,EXE_LEN)==exe,"EXE changed")
    report={"status":"INTERNAL_DIAGNOSTIC_ONLY_RUNTIME_REQUIRED","pair":[a,b],
        "eligible_records":len(valid),"candidate_pairs":len(pairs),"patched":result,
        "expectation":"Same two names, attributes and roster positions; country display should follow swapped refs if high-byte hypothesis is correct.",
        "runtime_checks":["Compare both flags and country labels before/after in Master League player list and player info.",
                          "Compare names, positions, 15 stats, appearance and team composition.",
                          "Verify both players survive new Master League, transfer search, save/reload and a match.",
                          "Check bonus roster and original free agent search for unintended differences."],
        "feed_changed":False,"nationality_generalized":False}
    (out/"nationality_probe_report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("track","baseline","readback","out"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.track,a.baseline,a.readback,a.out),indent=2))
