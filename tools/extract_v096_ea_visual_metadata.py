"""Read selected integer model fields from a public EA DB template, never execute its contents.
Format cross-reference: ViniMacacari/eafc-db-kit 1464907bf4e726504d8b3ce15ffd0a552990565e.
"""
import csv,sys,struct,xml.etree.ElementTree as ET,hashlib,json
from pathlib import Path
db,xml,out=map(Path,sys.argv[1:4])
b=db.read_bytes();s=xml.read_bytes()
assert b[:8]==b'DB\x00\x08\x00\x00\x00\x00' and b'<!DOCTYPE' not in s.upper() and b'<!ENTITY' not in s.upper()
root=ET.fromstring(s)
def attr(e,k):return e.attrib.get(k,e.findtext(k))
table=next(t for t in root.iter('table') if attr(t,'name')=='players')
short=attr(table,'shortname').encode()
meta={attr(f,'shortname').encode():(attr(f,'name'),int(attr(f,'rangelow'))) for f in table.iter('field')}
size,n=struct.unpack_from('<i4xi',b,8)
assert 28<=size<=len(b) and 0<n<10000
base=28+n*8
st=next(base+struct.unpack_from('<I',b,28+i*8)[0] for i in range(n) if b[24+i*8:28+i*8]==short)
rs=struct.unpack_from('<i',b,st+4)[0]
cap,written,cancel=struct.unpack_from('<HHH',b,st+16)
nf=b[st+24]
assert 0<rs<4096 and cancel<=written<=cap and nf>0
wanted=set('playerid gender birthdate hairtypecode hairstylecode haircolorcode facialhairtypecode facialhaircolorcode skintonecode bodytypecode headtypecode headassetid hashighqualityhead height weight firstnameid lastnameid commonnameid'.split())
fields={}
for i in range(nf):
 a=st+36+16*i
 typ,bit,code,width=struct.unpack_from('<ii4si',b,a)
 name,lo=meta.get(code,('',0))
 if name in wanted and typ==3:
  assert 0<=bit and 0<width<=32 and bit+width<=rs*8
  fields[name]=(bit,width,lo)
assert {'playerid','birthdate','skintonecode','haircolorcode','hairtypecode'}<=fields.keys(),fields
start=st+36+16*nf
assert start+written*rs<=len(b)
count=0
with out.open('w',newline='',encoding='utf-8') as f:
 writer=csv.DictWriter(f,fieldnames=list(fields));writer.writeheader()
 for i in range(written):
  record=b[start+i*rs:start+(i+1)*rs]
  if record[-1]&128:continue
  word=int.from_bytes(record,'little')
  row={k:((word>>bit)&((1<<width)-1))+lo for k,(bit,width,lo) in fields.items()}
  if row.get('gender',0)==0 and row['playerid']>0:writer.writerow(row);count+=1
print('EA_SOURCE',json.dumps({'sha256':hashlib.sha256(b).hexdigest(),'metadata_sha256':hashlib.sha256(s).hexdigest(),'record_size':rs,'fields':list(fields),'men_rows':count}))
