#!/usr/bin/env python3
"""Build + verify compact patch-record XOR-delta Stage5 Test06 -> Stage7 Test07."""
import base64,hashlib,json,struct,zlib
from pathlib import Path
from merge_verified import parse_patch,SECTOR

def build(source:Path,dest:Path,out:Path):
 a=source.read_bytes();b=dest.read_bytes()
 if a[:8]!=b'ISS26X01' or b[:8]!=b'ISS26X01' or len(a)!=len(b):raise ValueError('incompatible patch')
 na,=struct.unpack_from('<I',a,8);nb,=struct.unpack_from('<I',b,8)
 if na!=nb or na!=1412:raise ValueError('unexpected XOR sector count')
 d0=parse_patch(source);d1=parse_patch(dest)
 if set(d0)!=set(d1):raise ValueError('record set changed')
 delta=bytearray(b'ISS26D01');delta.extend(b'\0\0\0\0')
 changed=[]
 for lba in sorted(d0):
  h0,s0=d0[lba];h1,s1=d1[lba]
  if h0!=h1:raise ValueError('original sector guard modified')
  if s0!=s1:
   changed.append(lba)
   delta.extend(struct.pack('<I',lba))
   delta.extend(bytes(x^y for x,y in zip(s0,s1)))
 struct.pack_into('<I',delta,8,len(changed))
 if len(delta)!=12+len(changed)*2356:raise ValueError('invalid delta length')
 payload=base64.b64encode(zlib.compress(delta,9)).decode('ascii')
 out.parent.mkdir(exist_ok=True,parents=True)
 out.write_text(payload+'\n',encoding='ascii')
 # independent replay of the exact delta into original Test06 patch file bytes
 replay=bytearray(a);index={struct.unpack_from('<I',a,12+i*2388)[0]:12+i*2388+36 for i in range(na)}
 for i in range(len(changed)):
  at=12+i*2356;lba,=struct.unpack_from('<I',delta,at)
  pos=index[lba];mask=delta[at+4:at+2356]
  for k,v in enumerate(mask):replay[pos+k]^=v
 if replay!=b:raise ValueError('Delta replay differs from final candidate')
 report={'test06_sha256':hashlib.sha256(a).hexdigest().upper(),
  'test07_sha256':hashlib.sha256(b).hexdigest().upper(),
  'delta_sha256':hashlib.sha256(delta).hexdigest().upper(),
  'delta_edited_sectors':changed,'delta_edited_count':len(changed),
  'compressed_base64_chars':len(payload),'full_patch_bytes':len(b),
  'delta_replay_verified':True}
 (out.parent/'stage7_transport_report.json').write_text(json.dumps(report,indent=2)+'\n')
 return report
if __name__=='__main__':
 here=Path(__file__).parent
 r=build(here/'stage5_results/ISS26_v095_Stage5_BosniaStyle10_Stage3Combined_CANDIDATE.iss26p',
         here/'stage7_results/ISS26_0.9.5_Stage7_GDC_Bosnia_TEST07_CANDIDATE.iss26p',
         here/'stage7_results/test07_test06_to_stage7_delta.zlib.b64')
 print(json.dumps({k:v for k,v in r.items() if k!='delta_edited_sectors'},indent=2))
