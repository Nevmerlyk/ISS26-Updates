#!/usr/bin/env python3
"""Transport-only delta from immutable v0.9.4 independent patch to Stage5.

XOR is applied to the RAW 2352-byte patch mask field for matching LBA.
It is NOT a game update or an intermediate patch for end users.
"""
import base64,hashlib,struct,zlib,json
from pathlib import Path
from merge_verified import parse_patch
ROOT=Path(__file__).resolve().parent
BASE=Path('/mnt/data/iss26_small_fix_work/v094/ISS26_0.9.4_preview.iss26p')
TARGET=ROOT/'stage5_results/ISS26_v095_Stage5_BosniaStyle10_Stage3Combined_CANDIDATE.iss26p'
OUTPUT=ROOT/'stage5_results/test06_v094_to_stage5_delta.zlib.b64'
b=BASE.read_bytes();t=TARGET.read_bytes()
assert hashlib.sha256(b).hexdigest().upper()=='70E46566A7F2C3A7E5F1E930210A132D452EF0B752D18E92F4B5475DE2CB45FE'
assert hashlib.sha256(t).hexdigest().upper()=='3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636'
assert len(b)==len(t)==3371868
base=parse_patch(BASE);new=parse_patch(TARGET);assert base.keys()==new.keys() and len(base)==1412
changes=[]
for lba in base:
 assert base[lba][0]==new[lba][0]
 if base[lba][1]!=new[lba][1]:
  changes.append((lba,bytes(a^b for a,b in zip(base[lba][1],new[lba][1]))))
stream=b'ISS26D01'+struct.pack('<I',len(changes))+b''.join(struct.pack('<I',lba)+mask for lba,mask in changes)
compressed=base64.b64encode(zlib.compress(stream,9)).decode()
OUTPUT.write_text(compressed+'\n')
check=bytearray(b);positions={struct.unpack_from('<I',b,12+i*2388)[0]:12+i*2388+36 for i in range(1412)}
for lba,mask in changes:
 q=positions[lba]
 for j,v in enumerate(mask):check[q+j]^=v
assert bytes(check)==t
report={'base_patch_sha256':hashlib.sha256(b).hexdigest().upper(),'target_patch_sha256':hashlib.sha256(t).hexdigest().upper(),'transport_delta_sha256':hashlib.sha256(stream).hexdigest().upper(),'count':len(changes),'sectors':[lba for lba,_ in changes],'transport_b64_chars':len(compressed),'delta_uncompressed_bytes':len(stream),'output_path':str(OUTPUT)}
(ROOT/'stage5_results/test06_transport_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
