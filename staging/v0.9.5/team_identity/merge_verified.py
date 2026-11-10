#!/usr/bin/env python3
"""Merge exact, preconditioned sector edits into an existing independent ISS26X01 patch.

Input: clean European Track 01, existing standalone .iss26p, JSON edits with
{raw_offset, expected_hex, replacement_hex}. The expected value is compared
against the *patched baseline*, not against the original. Mode 2 Form 1 EDC/ECC
are recalculated for affected sectors. Output is an independent XOR sector patch
against the clean original. No game data is included in the program.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from collections import defaultdict

SECTOR=2352
MAGIC=b'ISS26X01'
BASE_SIZE=496156752
BASE_SHA='D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'

EDC=[]; EF=[]; EB=[0]*256
for i in range(256):
 x=i
 for _ in range(8): x=(x>>1)^(0xD8018001 if x&1 else 0)
 EDC.append(x)
 j=i<<1
 if j&256:j^=0x11D
 EF.append(j);EB[i^j]=i

def edc(data):
 n=0
 for b in data:n=(n>>8)^EDC[(n^b)&255]
 return struct.pack('<I',n)

def ecc(s,major_count,minor_count,major_mult,minor_inc):
 size=major_count*minor_count
 buf=bytearray(s[12:12+size]);buf[:4]=b'\0'*4
 out=bytearray(2*major_count)
 for m in range(major_count):
  idx=(m>>1)*major_mult+(m&1); a=b=0
  for _ in range(minor_count):
   v=buf[idx];idx+=minor_inc
   if idx>=size:idx-=size
   a^=v;b^=v;a=EF[a]
  a=EB[EF[a]^b];out[m]=a;out[m+major_count]=a^b
 return out

def fix_form1(s):
 if s[15]!=2 or bool(s[18]&0x20) or s[16:20]!=s[20:24]:
  raise ValueError('Only intact CD-XA Mode2 Form1 sectors supported')
 s[2072:2076]=edc(s[16:2072]);s[2076:2248]=ecc(s,86,24,2,86);s[2248:2352]=ecc(s,52,43,86,88)
 return s

def parse_patch(path):
 data=path.read_bytes()
 if data[:8]!=MAGIC or len(data)<12:raise ValueError('Bad patch magic')
 count,=struct.unpack_from('<I',data,8)
 if not 0<count<=8192 or len(data)!=12+count*(36+SECTOR):raise ValueError('Bad record count/size')
 records={};last=-1
 for n in range(count):
  offset=12+n*(36+SECTOR);lba,=struct.unpack_from('<I',data,offset)
  if not last<lba<BASE_SIZE//SECTOR:raise ValueError('Unsorted/duplicate/out-of-range sector')
  records[lba]=(data[offset+4:offset+36],data[offset+36:offset+36+SECTOR])
  last=lba
 return records

def merge(original,baseline,edits_file,output, expected_baseline=None):
 if original.stat().st_size!=BASE_SIZE:raise ValueError('Wrong clean original length')
 edits=json.loads(edits_file.read_text())
 if not isinstance(edits,list) or not edits:raise ValueError('Expected nonempty JSON edit array')
 records=parse_patch(baseline)
 grouped=defaultdict(list);byte_claims=set()
 for edit in edits:
  raw=int(edit['raw_offset']);old=bytes.fromhex(edit['expected_hex']);new=bytes.fromhex(edit['replacement_hex'])
  if not old or len(old)!=len(new) or raw<0 or raw+len(old)>BASE_SIZE or raw//SECTOR!=(raw+len(old)-1)//SECTOR:
   raise ValueError('Invalid edit length or crossing sector: '+str(raw))
  for x in range(raw,raw+len(old)):
   if x in byte_claims:raise ValueError('Overlapping edits')
   byte_claims.add(x)
  grouped[raw//SECTOR].append((raw%SECTOR,old,new))
 output.parent.mkdir(parents=True,exist_ok=True)
 temporary=output.with_suffix(output.suffix+'.partial')
 patch_sha=hashlib.sha256();result_sha=hashlib.sha256();base_sha=hashlib.sha256();result_records=[]
 with original.open('rb') as src:
  for lba in range(BASE_SIZE//SECTOR):
   raw=src.read(SECTOR)
   if len(raw)!=SECTOR:raise ValueError('Truncated original')
   base_sha.update(raw)
   if lba not in records and lba not in grouped:
    result_sha.update(raw);continue
   actual=hashlib.sha256(raw).digest();baseline_record=records.get(lba)
   if baseline_record and actual!=baseline_record[0]:raise ValueError(f'Original sector SHA mismatch {lba}')
   target=bytearray((x^y for x,y in zip(raw,baseline_record[1]))) if baseline_record else bytearray(raw)
   for pos,old,new in grouped.get(lba,[]):
    if target[pos:pos+len(old)]!=old:raise ValueError(f'Precondition failed in sector {lba} at {pos}')
    target[pos:pos+len(new)]=new
   if lba in grouped:fix_form1(target)
   result_sha.update(target)
   if raw!=target:result_records.append((lba,actual,bytes(x^y for x,y in zip(raw,target))))
  if src.read(1):raise ValueError('Unexpected data after Track 01')
 if base_sha.hexdigest().upper()!=BASE_SHA:raise ValueError('Clean Track 01 SHA mismatch')
 if expected_baseline:
  # Full baseline result independently reconstructed without extra edits.
  with original.open('rb') as src:
   check=hashlib.sha256()
   for lba in range(BASE_SIZE//SECTOR):
    b=src.read(SECTOR);p=records.get(lba)
    if p:
     if hashlib.sha256(b).digest()!=p[0]:raise ValueError('Baseline record invalid')
     b=bytes(x^y for x,y in zip(b,p[1]))
    check.update(b)
   if check.hexdigest().upper()!=expected_baseline.upper():raise ValueError('Baseline full SHA mismatch')
 with temporary.open('wb') as f:
  f.write(MAGIC);f.write(struct.pack('<I',len(result_records)))
  for lba,hashbytes,mask in result_records:
   f.write(struct.pack('<I',lba));f.write(hashbytes);f.write(mask)
  f.flush()
 temporary.replace(output)
 report={'baseline_patch':str(baseline),'baseline_records':len(records),'merged_records':len(result_records),'edited_sectors':sorted(grouped),'edits':len(edits),'original_sha256':base_sha.hexdigest().upper(),'result_sha256':result_sha.hexdigest().upper(),'patch_sha256':hashlib.sha256(output.read_bytes()).hexdigest().upper(),'status':'verified format, full original sector preconditions and CD EDC/ECC; gameplay not tested'}
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--original',type=Path,required=True)
 p.add_argument('--baseline',type=Path,required=True)
 p.add_argument('--edits',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--expected-baseline-sha')
 args=p.parse_args()
 r=merge(args.original,args.baseline,args.edits,args.output,args.expected_baseline_sha)
 print(json.dumps(r,indent=2,ensure_ascii=False))
