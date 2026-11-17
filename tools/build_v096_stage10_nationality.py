#!/usr/bin/env python3
"""Build an independent Stage10 nationality DIAGNOSTIC on the owner's clean disc.
No invented country IDs, no expansion, no changes to game saves or original.
Run a two-player reciprocal probe first. Candidate mode is not a release.
"""
import argparse,csv,json,struct
from pathlib import Path
from collections import defaultdict,Counter
from audit_v096_nationality_refs import (ROOT,S,R,OFF,NA,EA,EN,NN,SELECT_LBA,
    SELECT_LEN,EXE_LBA,EXE_LEN,digest,resource,refs,extra,norm,need,label)
from integration_merge_eu import BASE_SHA,BASE_SIZE,parse_patch,merge
PATCH_SHA="6B4BD98ABBC126EB03DC640071662C8D7600A7780878CF96B8F5923786EF8169"
RESULT_SHA="865D1CD4134C358F911820A3F0FC570BBBBEA3EB8688DA3593D072A0DEB4549E"
ELIGIBLE={"OFFICIAL_COUNTRY_CORROBORATED","SOURCE_LINKED_NOT_CERTIFIED"}
def record(buf,idx):
    return bytes(buf[EN+10*idx:EN+10*idx+10]),bytes(buf[EA+12*idx:EA+12*idx+12])
def assign(movable,targets):
    """Optimal count of correctly mapped countries within eligible occupied
    slots only; preserve all already-correct placements; no free-agent reuse."""
    need(set(movable)==set(targets),"target mismatch")
    remaining=set(movable)
    plan={}
    for ref in sorted(movable):
        if ref[0]==targets[ref]:
            plan[ref]=ref;remaining.remove(ref)
    available=defaultdict(list)
    for ref in sorted(remaining):available[ref[0]].append(ref)
    for ref in sorted(remaining):
        pool=available[targets[ref]]
        if pool:plan[ref]=pool.pop(0)
    left=sorted(remaining-set(plan))
    free=sorted(set(movable)-set(plan.values()))
    need(len(left)==len(free),"bad permutation")
    # Keep remaining identities in place where possible.
    for ref in sorted(set(left)&set(free)):
        plan[ref]=ref;left.remove(ref);free.remove(ref)
    plan.update(zip(left,free))
    need(set(plan)==set(plan.values())==set(movable),"nonbijective permutation")
    for ref in movable:
        need(not (ref[0]==targets[ref] and plan[ref]!=ref),"regression")
    optimal=sum(min(n,Counter(r[0] for r in movable)[k]) for k,n in Counter(targets.values()).items())
    need(sum(plan[r][0]==targets[r] for r in movable)==optimal,"nonoptimal assignment")
    return plan
def reciprocal(movable,targets):
    pairs=[(a,b) for a in sorted(movable) for b in sorted(movable)
           if a<b and a[0]!=b[0] and a[0]==targets[b] and b[0]==targets[a]]
    need(bool(pairs),"no safe reciprocal pair")
    a,b=pairs[0]
    return {a:b,b:a}
def relocate(sel,native,plan):
    active=refs(sel)
    need(len(active)==528 and len(set(active))==528,"club table collision")
    need(set(plan)==set(plan.values()) and set(plan)<=set(native)&set(active),"unsafe permutation")
    need(len(native)==len(set(native.values())) and all(0<=i<341 for i in native.values()),"bad physical map")
    output=bytearray(sel)
    allowed=set()
    for a,b in plan.items():
        if a==b:continue
        name,attr=record(sel,native[a]);i=native[b]
        for off,data in ((EN+10*i,name),(EA+12*i,attr)):
            output[off:off+len(data)]=data;allowed.update(range(off,off+len(data)))
        off=R+2*active.index(a)
        output[off:off+2]=bytes(b);allowed.update(range(off,off+2))
    expected=[plan.get(r,r) for r in active]
    need(refs(output)==expected and len(set(expected))==528,"ref verification")
    for a,b in zip(active,expected):
        if a in native:need(record(sel,native[a])==record(output,native[b]),"record changed")
        else:need(a==b,"shared record moved")
    need(all(p in allowed for p,(a,b) in enumerate(zip(sel,output)) if a!=b),"unrelated byte changed")
    return bytes(output)
def edits_for(a,b):
    need(len(a)==len(b),"resource length")
    changes=[]
    for off in range(0,len(a),2048):
        x,y=a[off:off+2048],b[off:off+2048]
        if x!=y:changes.append({"raw_offset":(SELECT_LBA+off//2048)*S+24,"expected_hex":x.hex(),"replacement_hex":y.hex()})
    return changes
def main(track,baseline,readback,out,mode):
    need(track.stat().st_size==BASE_SIZE and digest(track)==BASE_SHA,"wrong original")
    need(digest(baseline)==PATCH_SHA,"expected exact Appearance Final Stage10 patch")
    records=parse_patch(baseline)
    org=resource(track,{},SELECT_LBA,SELECT_LEN)
    sel=resource(track,records,SELECT_LBA,SELECT_LEN)
    exe=resource(track,records,EXE_LBA,EXE_LEN)
    offsets=struct.unpack_from("<118H",org,OFF)
    need(sel[OFF:OFF+236]==org[OFF:OFF+236],"offset drift")
    native={r:offsets[r[0]]+r[1]-22 for r in refs(org) if extra(r)}
    need(len(native)==len(set(native.values()))==315 and all(0<=x<341 for x in native.values()),"native bank drift")
    active=refs(sel)
    need(len(set(active))==528 and sum(r in native for r in active)==301,"active club refs drift")
    reg=json.loads((ROOT/"data/integration/active_club_registry_v21.json").read_text())
    ids={t["team_id"]:23-t["ordinal"] for t in reg["menu_order"]}
    manifest=json.loads((ROOT/"data/integration/v096_master_league_nationality_targets.json").read_text())
    sources={(r["club"],norm(r["player"])):r for r in manifest["players"]}
    need(len(sources)==528,"source name conflict")
    with readback.open(encoding="utf-8-sig",newline="") as f:
        rr=list(csv.DictReader(f))
    rr=[r for r in rr if r["team_id"] in ids]
    need(len(rr)==528,"readback must contain 528 club rows")
    observed=set();used=set();targets={};info={};blocked=Counter()
    for r in rr:
        k=(r["team_id"],norm(r["player_name"]));slot=int(r["slot"])
        need(1<=slot<=22 and (k[0],slot) not in observed,"readback slot collision")
        observed.add((k[0],slot))
        ref=tuple(bytes.fromhex(r["ref"]))
        need(len(ref)==2 and active[ids[k[0]]*22+slot-1]==ref and ref not in used,"readback ref drift")
        used.add(ref)
        h,l=ref
        if ref in native:
            idx=native[ref];name=label(sel,EN+10*idx);pos=sel[EA+12*idx]&15
        else:
            need(h<54 and l<22,"unknown ref")
            idx=h*22+l;name=label(exe,NN+10*idx);pos=sel[NA+12*idx]&15
        need(name==r["label"] and pos==int(r["position"]),"label or position drift")
        need(k in sources,"missing source identity")
        s=sources[k];target=s["candidate_id"]
        info[ref]={"club":k[0],"slot":slot,"player":r["player_name"],"country":s["source_country"],"candidate_id":target,"old_ref":bytes(ref).hex(),"source_status":s["source_status"]}
        if ref not in native:
            blocked["shared_national_matches" if h==target else "shared_national_conflict"]+=1
        elif target is None:blocked["country_id_missing"]+=1
        elif s["source_status"] not in ELIGIBLE:blocked["identity_review"]+=1
        else:targets[ref]=target
    need(len(used)==528,"incomplete club readback")
    plan=reciprocal(set(targets),targets) if mode=="probe" else assign(set(targets),targets)
    changed={a:b for a,b in plan.items() if a!=b}
    need(bool(changed),"no changes feasible")
    new=relocate(sel,native,changed)
    edits=edits_for(sel,new)
    out.mkdir(parents=True,exist_ok=True)
    report={"status":"DIAGNOSTIC_RUNTIME_NOT_VERIFIED","mode":mode,"blocked":dict(blocked),
      "eligible":len(targets),"before_matches":sum(a[0]==t for a,t in targets.items()),
      "after_candidate_matches":sum(plan.get(a,a)[0]==t for a,t in targets.items()),
      "changed":[dict(info[a],new_ref=bytes(b).hex(),new_candidate_id=b[0]) for a,b in sorted(changed.items())],
      "limitation":"High-byte hypothesis not yet proven. No new country IDs or flags; do not promote. Validate in a fresh Master League and saved career copy."}
    p=out/"nationality_edits.json";p.write_text(json.dumps(edits,indent=2))
    patch=out/("ISS26_0.9.6_NATIONALITY_"+mode.upper()+"_INTERNAL.iss26p")
    report["patch"]=merge(track,baseline,p,patch,RESULT_SHA)
    after=parse_patch(patch)
    need(resource(track,after,SELECT_LBA,SELECT_LEN)==new,"SELECT verification")
    need(resource(track,after,EXE_LBA,EXE_LEN)==exe,"exe changed")
    affected={e["raw_offset"]//S for e in edits}
    need(all(records.get(i)==after.get(i) for i in (set(records)|set(after))-affected),"non-SELECT sector changed")
    (out/"nationality_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=True,indent=2))
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for k in ("track","baseline","readback","out"):p.add_argument("--"+k,type=Path,required=True)
    p.add_argument("--mode",choices=("probe","candidate"),default="probe")
    a=p.parse_args();main(a.track,a.baseline,a.readback,a.out,a.mode)
