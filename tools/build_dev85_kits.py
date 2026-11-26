#!/usr/bin/env python3
"""DEV85: inspect actual 0.9.7 TEX resources and compile guarded palette edits.
No guessed team or UV assignments. No original BIN writes or publication.
"""
import argparse, hashlib, json, re, struct
from pathlib import Path
from kit_resource_probe import RawPS1ISO, digest_file, EXPECTED_ORIGINAL_HASH
from kit_tex_workbench import parse_tex, public_records, export_previews, palette_edit
from build_v095_test12_gdc_descriptor_repair import fix_parity, valid_parity

SECTOR=2352
RECORD=2388
PATCH_SHA="A97C3DA1264FA46E0C0AF41E3BA600696C0D432F0D0279C8B29BF8AD5D0786B6"
RESULT_SHA="5FDD5AF7432ECF79F0DB75BE2D1B2EC97D5874D907258AC920EBD4CCE2657AD5"
def sha(b): return hashlib.sha256(b).hexdigest().upper()
def need(ok,msg):
    if not ok: raise ValueError(msg)
def xor(a,b):
    need(len(a)==len(b),"XOR size mismatch")
    return bytes(x^y for x,y in zip(a,b))
def parse_patch(path,disc):
    raw=path.read_bytes()
    need(sha(raw)==PATCH_SHA,"Wrong official 0.9.7 patch SHA")
    need(raw[:8]==b"ISS26X01" and len(raw)==12+779*RECORD and struct.unpack_from("<I",raw,8)[0]==779,"Invalid stable patch structure")
    records={}
    last=-1
    for i in range(779):
        pos=12+i*RECORD
        lba=struct.unpack_from("<I",raw,pos)[0]
        guard=raw[pos+4:pos+36]; mask=raw[pos+36:pos+RECORD]
        need(last<lba<disc.sectors,"Invalid stable LBA ordering")
        last=lba
        original=disc.raw_sector(lba)
        need(hashlib.sha256(original).digest()==guard,"Original sector guard mismatch")
        records[lba]=(guard,mask)
    return records

class Overlay(RawPS1ISO):
    def __init__(self,track,records):
        super().__init__(track)
        self.records=records
    def raw_sector(self,lba):
        raw=super().raw_sector(lba)
        return xor(raw,self.records[lba][1]) if lba in self.records else raw

def full_hash(original, records):
    h=hashlib.sha256()
    with original.open("rb") as f:
        lba=0
        while True:
            chunk=f.read(SECTOR*1024)
            if not chunk: break
            need(len(chunk)%SECTOR==0,"Truncated raw image")
            out=bytearray(chunk)
            for off in range(0,len(chunk),SECTOR):
                if lba in records:
                    guard,mask=records[lba]
                    raw=chunk[off:off+SECTOR]
                    need(hashlib.sha256(raw).digest()==guard,"Full image sector guard mismatch")
                    out[off:off+SECTOR]=xor(raw,mask)
                lba+=1
            h.update(out)
    return h.hexdigest().upper()

def resources(disc):
    files,_=disc.list_files()
    return {path:e for path,e in files.items() if not e.is_dir and re.fullmatch(r"TEX_\d+\.BIN",path.split("/")[-1],re.I)}
def read_tex(disc,e):
    need(0<e.size<=256*1024,"Unexpected TEX size")
    data=b"".join(disc.file_chunks(e))
    need(disc.resource_forms[e.path]["form2"]==0,"Not a pure Form1 TEX resource")
    return data
def scan(track,stable,out):
    out.mkdir(parents=True,exist_ok=False)
    report={"schemaVersion":1,"baseGame":"0.9.7","sourceTrackSha256":EXPECTED_ORIGINAL_HASH,
            "stablePatchSha256":PATCH_SHA,"stableResultSha256":RESULT_SHA,"resources":[],
            "teamMappingVerified":False,"roleMappingVerified":False,"changesGame":False}
    with Overlay(track,stable) as disc:
        for path,e in sorted(resources(disc).items()):
            item={"resource":path,"lba":e.lba,"size":e.size}
            try:
                data=read_tex(disc,e); rec=parse_tex(data)
                item.update(sourceSha256=sha(data),layout="candidate",records=public_records(rec))
                target=out/"previews"/f"{e.lba}_{Path(path).stem}"
                export_previews(rec,target)
                item["previewDirectory"]=str(target.relative_to(out))
            except (ValueError,OSError,struct.error) as ex:
                item.update(layout="unsupported",reason=str(ex))
            report["resources"].append(item)
    report["texCount"]=len(report["resources"])
    report["candidateCount"]=sum(i["layout"]=="candidate" for i in report["resources"])
    (out/"inventory.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("TEX resources:",report["texCount"],"candidate layouts:",report["candidateCount"])
    print("Inventory only; no game changes:",out)

def build(track,stable,plan,out):
    need(plan.get("schemaVersion")==1 and plan.get("baseGame")=="0.9.7" and plan.get("stableResultSha256")==RESULT_SHA,"Wrong build plan baseline")
    edits=plan.get("resources")
    need(isinstance(edits,list) and edits,"No verified kit edits")
    result=dict(stable); changed=set(); report=[]
    with RawPS1ISO(track) as original, Overlay(track,stable) as disc:
        catalog=resources(disc)
        used=set()
        for item in edits:
            name=item["resource"]
            need(name in catalog and name not in used,"Unknown or duplicate resource")
            used.add(name); entry=catalog[name]
            need(isinstance(item.get("team"),str) and item["team"].strip(),"Missing team binding")
            data=read_tex(disc,entry)
            modified,proof=palette_edit(data,item["palettePlan"])
            need(data!=modified,"No actual palette change")
            for off in range(0,len(data),2048):
                old=data[off:off+2048]; new=modified[off:off+2048]
                if old==new: continue
                lba=entry.lba+off//2048
                need(lba not in changed,"Overlapping kit sector")
                original_sector=original.raw_sector(lba)
                current=disc.raw_sector(lba)
                need(not current[18]&0x20 and current[:24]==original_sector[:24],"Unsupported raw sector")
                need(current[24:24+len(old)]==old,"TEX sector readback mismatch")
                final=bytearray(current)
                final[24:24+len(new)]=new
                mask=bytearray(xor(original_sector,final))
                fix_parity(mask)
                need(valid_parity(mask),"Failed Mode2 parity")
                result[lba]=(hashlib.sha256(original_sector).digest(),bytes(mask))
                changed.add(lba)
            report.append({"team":item["team"],"resource":name,**proof})
    need(changed and len(result)<=8192,"Empty or oversized independent patch")
    with Overlay(track,result) as disc:
        catalog=resources(disc)
        for item,proof in zip(edits,report):
            need(sha(read_tex(disc,catalog[item["resource"]]))==proof["resultSha256"],"Modified TEX readback failed")
    need(all(result[lba]==rec for lba,rec in stable.items() if lba not in changed),"Unrelated stable record changed")
    raw=bytearray(b"ISS26X01"+struct.pack("<I",len(result)))
    for lba,(guard,mask) in sorted(result.items()):
        raw+=struct.pack("<I",lba)+guard+mask
    result_hash=full_hash(track,result)
    out.mkdir(parents=True,exist_ok=False)
    patch=out/"ISS26_0.9.8_DEV85_Kits_Test.iss26p"
    patch.write_bytes(raw)
    (out/"build-report.json").write_text(json.dumps({
        "version":"0.9.8-dev85","patchSha256":sha(raw),"baseSha256":EXPECTED_ORIGINAL_HASH,
        "resultSha256":result_hash,"records":len(result),"changedLBAs":sorted(changed),
        "resources":report,"standalone":True,"emulatorTested":False,"published":False,
        "scope":"verified palette changes only; logo and geometry changes not supported"
    },indent=2)+"\n",encoding="utf-8")
    print("Created standalone candidate:",patch)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--track",type=Path,required=True); p.add_argument("--stable",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True); p.add_argument("--plan",type=Path)
    a=p.parse_args()
    need(digest_file(a.track)==EXPECTED_ORIGINAL_HASH,"Original EU Track01 SHA mismatch")
    with RawPS1ISO(a.track) as d: stable=parse_patch(a.stable,d)
    need(full_hash(a.track,stable)==RESULT_SHA,"Reconstructed stable 0.9.7 SHA mismatch")
    if a.plan: build(a.track,stable,json.loads(a.plan.read_text(encoding="utf-8")),a.out)
    else: scan(a.track,stable,a.out)
if __name__=="__main__": main()
