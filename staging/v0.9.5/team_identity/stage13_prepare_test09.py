"""Prepare small Stage12 diagnostic Test09 delta from published Test08.
The delta is against complete *standalone* ISS26X01 patch bytes, not game ISO.
Test09 still applies to clean official EU Track01; it is NOT layered for users.
"""
from __future__ import annotations
import base64,hashlib,json,struct,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TEST08=ROOT/'stage10_results/ISS26_0.9.5_TeamIdentity_Stage10_BosniaCanada_TEST08.iss26p'
AB=ROOT/'stage12_results/ISS26_0.9.5_Stage12_Test08_LargeGPU_AB_CANDIDATE.iss26p'
OUT=ROOT/'stage13_results';OUT.mkdir(exist_ok=True)
S0='E65E5623756643E2DAE7069A66FE888E14439A5A534DBF171BB03630605648B1'
S1='FA5E3DC3702808E8ABC197C9BB27B0707A4D44575D765918911AD846738D71B2'
DISK='6F81648EDCF02D5115FFD313DDE4DA3F5768EA4FBEAD4C1831D91EC813B70647'
assert hashlib.sha256(TEST08.read_bytes()).hexdigest().upper()==S0
assert hashlib.sha256(AB.read_bytes()).hexdigest().upper()==S1
old=TEST08.read_bytes();new=AB.read_bytes()
assert len(old)==len(new)==3371868
assert old[:8]==new[:8]==b'ISS26X01'
count,=struct.unpack_from('<I',old,8)
assert count==1412
assert old[8:12]==new[8:12]
positions=[];changes=[]
for i in range(count):
  at=12+i*2388
  l0,l1=struct.unpack_from('<I',old,at)[0],struct.unpack_from('<I',new,at)[0]
  assert l0==l1
  assert old[at:at+36]==new[at:at+36]
  off=at+36;positions.append((l0,off))
  mask=bytes(a^b for a,b in zip(old[off:off+2352],new[off:off+2352]))
  if any(mask):changes.append((l0,mask))
assert [l for l,_ in changes]==[6089,6090,6256,6257],changes
raw=b'ISS26D01'+struct.pack('<I',len(changes))+b''.join(struct.pack('<I',l)+mask for l,mask in changes)
assert len(raw)==12+len(changes)*2356
rec=bytearray(old)
for l,mask in changes:
  pos=dict(positions)[l]
  for j,b in enumerate(mask):rec[pos+j]^=b
assert bytes(rec)==new
encoded=base64.b64encode(zlib.compress(raw,9)).decode('ascii')
(OUT/'test09_test08_to_stage12_delta.zlib.b64').write_text(encoded+'\n')
report={
 'test_release':'0.9.6-teamidentity-test09',
 'description':'Experimental Test08-to-Stage12 A/B of only 2 DATSEL large GPU source streams; independent clean-original release',
 'baseline_patch_sha256':S0,
 'target_patch_sha256':S1,
 'result_image_sha256':DISK,
 'delta_format':'ISS26D01',
 'delta_raw_sha256':hashlib.sha256(raw).hexdigest().upper(),
 'delta_b64_chars':len(encoded),
 'raw_diff_lbas':[l for l,_ in changes],
 'changed_sector_count':len(changes),
 'no_GDC_sector_changes':True,
 'gameplay_confirmed':False,
 'test_channel_update_requested':False,
 'note':'Never promote to stable without PCSX Redux visual test. Bosnia large flag deliberately reverts to old style10 art.'}
(OUT/'stage13_publish_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(report,indent=2,ensure_ascii=False))
