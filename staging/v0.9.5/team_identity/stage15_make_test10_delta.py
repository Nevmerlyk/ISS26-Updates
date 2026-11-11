#!/usr/bin/env python3
"""Generate verified compact guarded union-of-sectors delta Test09 -> Stage15 Test10.

Format ISS26M01: 8-byte signature, uint32 count, then entries
[uint32 LBA, 32-byte sha256(original sector), 2352 bytes XOR mask-delta]
A merged target patch is independently applicable to the CLEAN EU disc.
"""
import base64,hashlib,json,struct,zlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from merge_verified import parse_patch
A=ROOT/'stage12_results/ISS26_0.9.5_Stage12_Test08_LargeGPU_AB_CANDIDATE.iss26p'
B=ROOT/'stage15_results/ISS26_0.9.5_Stage15_NationalPrematchNames_CANDIDATE.iss26p'
OUT=ROOT/'stage15_results'
EXP_BASE='FA5E3DC3702808E8ABC197C9BB27B0707A4D44575D765918911AD846738D71B2'
EXP_TARGET='9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B'
assert hashlib.sha256(A.read_bytes()).hexdigest().upper()==EXP_BASE
assert hashlib.sha256(B.read_bytes()).hexdigest().upper()==EXP_TARGET
old=parse_patch(A);new=parse_patch(B)
mask0=bytes(2352)
blob=bytearray(b'ISS26M01'+b'\0\0\0\0')
changed=[];introduced=[]
for lba in sorted(set(old)|set(new)):
 p=old.get(lba);q=new.get(lba)
 if p and q and p[0]!=q[0]:raise ValueError(f'Original SHA guard mismatch {lba}')
 before=p[1] if p else mask0;after=q[1] if q else mask0
 if before==after:continue
 guard=p[0] if p else q[0]
 delta=bytes(x^y for x,y in zip(before,after))
 blob.extend(struct.pack('<I',lba));blob.extend(guard);blob.extend(delta)
 changed.append(lba)
 if p is None:introduced.append(lba)
struct.pack_into('<I',blob,8,len(changed))
compressed=zlib.compress(bytes(blob),9)
(OUT/'test10_test09_to_stage15_delta.zlib.b64').write_text(base64.b64encode(compressed).decode()+'\n')
# reconstruct baseline patch records from delta and check target bytes exactly.
merged={lba:(guard,mask) for lba,(guard,mask) in old.items()}
for i in range(len(changed)):
 off=12+i*2388;lba,=struct.unpack_from('<I',blob,off)
 guard=blob[off+4:off+36];diff=blob[off+36:off+2388]
 assert lba==changed[i]
 before=merged.get(lba)
 if before:
  assert before[0]==guard
  candidate=bytes(x^y for x,y in zip(before[1],diff))
 else:candidate=diff
 if candidate!=mask0:merged[lba]=(guard,candidate)
 else:merged.pop(lba,None)
res=bytearray(b'ISS26X01'+struct.pack('<I',len(merged)))
for lba in sorted(merged):
 guard,mask=merged[lba]
 res.extend(struct.pack('<I',lba));res.extend(guard);res.extend(mask)
assert bytes(res)==B.read_bytes(),'Delta does not reproduce full candidate'
report={'base_patch_sha256':EXP_BASE,'target_patch_sha256':EXP_TARGET,'target_image_sha256':json.loads((OUT/'stage15_report.json').read_text())['result_disc_sha256'],'delta_sha256':hashlib.sha256(bytes(blob)).hexdigest().upper(),'delta_b64_chars':len(base64.b64encode(compressed)),'changed_lbas':changed,'introduced_lbas':introduced,'records_new':len(merged),'format':'ISS26M01 (guarded 2388-byte union-delta per LBA)','description':'Independent full patch, fully visual name atlas (17 new national names in all three localized resources)'}
(OUT/'stage15_test10_delta_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('changed_lbas','introduced_lbas')},indent=2))
