#!/usr/bin/env python3
"""Encode compact Test06->Test08 XOR-sector delta for GitHub Actions.
Published outcome remains a full, standalone clean-original ISS26X01 patch.
"""
from pathlib import Path
import sys,struct,hashlib,zlib,base64,json
sys.path.insert(0,'/mnt/data/iss26_team_identity')
from merge_verified import parse_patch
ROOT=Path('/mnt/data/iss26_team_identity')
old=ROOT/'stage5_results/ISS26_v095_Stage5_BosniaStyle10_Stage3Combined_CANDIDATE.iss26p'
new=ROOT/'stage10_results/ISS26_0.9.5_TeamIdentity_Stage10_BosniaCanada_TEST08.iss26p'
assert hashlib.sha256(old.read_bytes()).hexdigest().upper()=='3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636'
assert hashlib.sha256(new.read_bytes()).hexdigest().upper()=='E65E5623756643E2DAE7069A66FE888E14439A5A534DBF171BB03630605648B1'
a=parse_patch(old);b=parse_patch(new)
assert list(a)==list(b)
sectors=[x for x in a if a[x][1]!=b[x][1]]
assert sectors==[6084,6085,6086,6087,6088,6103,6251,6252,6253,6254,6255,6277,6279]
delta=bytearray(b'ISS26D01'+struct.pack('<I',len(sectors)))
for lba in sectors:
    assert a[lba][0]==b[lba][0]
    delta+=struct.pack('<I',lba)
    delta+=bytes(x^y for x,y in zip(a[lba][1],b[lba][1]))
    assert len(delta)<=12+len(sectors)*2356
assert len(delta)==12+len(sectors)*2356
compressed=zlib.compress(delta,9)
reduced=base64.b64encode(compressed).decode('ascii')
assert zlib.decompress(base64.b64decode(reduced))==delta
out=ROOT/'stage10_results/test08_test06_to_stage10_delta.zlib.b64'
out.write_text(reduced+'\n',encoding='ascii')
rebuild=bytearray(old.read_bytes());rec_map={struct.unpack_from('<I',rebuild,12+i*2388)[0]:12+i*2388+36 for i in range(1412)}
for lba in sectors:
    ptr=rec_map[lba];sect_delta=bytes(delta[12+sectors.index(lba)*2356+4:12+(sectors.index(lba)+1)*2356])
    for j in range(2352):rebuild[ptr+j]^=sect_delta[j]
assert bytes(rebuild)==new.read_bytes()
report={'baseline_patch_sha256':hashlib.sha256(old.read_bytes()).hexdigest().upper(),'full_patch_sha256':hashlib.sha256(new.read_bytes()).hexdigest().upper(),'delta_sha256':hashlib.sha256(delta).hexdigest().upper(),'sector_count':len(sectors),'sector_ids':sectors,'delta_bytes':len(delta),'zlib_base64_chars':len(reduced),'reconstructed_full_patch_matches_byte_for_byte':True,'standalone_clean_original_patch':True}
(ROOT/'stage10_results/test08_delta_report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
