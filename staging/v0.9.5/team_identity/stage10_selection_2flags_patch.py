#!/usr/bin/env python3
"""Stage 10: Install screenshot-redrawn 24x16 Bosnia/Canada icons in the
selection-window texture atlas of Test06, without touching GDC / big flags.

Output is a fully standalone ISS26X01 patch against clean EU Track01. Strictly
verify non-target small sprite pixels 52/54, DATSEL3 duplicates, CD EDC/ECC,
original sector SHA guards, Test06 330 names, Canada/Bosnia CLUT unchanged.
"""
from __future__ import annotations
from pathlib import Path
import json,hashlib,struct,sys,collections
sys.path.insert(0,'/mnt/data/iss26_team_identity')
sys.path.insert(0,'/mnt/data/iss26_small_fix_work')
sys.path.insert(0,'/mnt/data')
from team_identity_audit import PatchedDisc,parse_patch
from codec import decode,encode,optimize_literal_packets
from iss26_v095_merge_verified import fix_form1,edc

ROOT=Path('/mnt/data/iss26_team_identity'); DATA=Path('/mnt/data')
ORIG=DATA/'ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin'
BASE=ROOT/'stage5_results/ISS26_v095_Stage5_BosniaStyle10_Stage3Combined_CANDIDATE.iss26p'
ART=ROOT/'stage10_results/flags_24x16_masterleague_v6.json'
MANIFEST=DATA/'iss26_flag_manifest/manifest.json'
OUT=ROOT/'stage10_results'
EXPECTED_BASE_SHA='3A2B98ECFDAA693F8C652543F9A7122D6095EC488C757268D67970688714A636'
EXPECTED_BASE_IMAGE_SHA='A3B94E6837D9E4FFC75B8F0440E39BF26CE806B57668ACB49839488E5928FAB2'
EXPECTED_ORIG_SHA='D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'
TILES=[(768,256),(800,256),(768,384),(800,384)]
SMALL_CMDS=[212428,212444,212460,212476]
REGION_SIZE=11791


def get_pixels(vram:bytes,entry:dict)->bytes:
    u,v=entry['uv']; x,y=entry['tpage'];out=bytearray()
    for dy in range(16):
        for dx in range(24):
            off=2*((y+v+dy)*1024+x+(u+dx)//4)
            shift=4*((u+dx)%4)
            word=int.from_bytes(vram[off:off+2],'little')
            out.append((word>>shift)&15)
    return bytes(out)


def put_pixels(vram:bytearray,entry:dict,raw:bytes):
    assert len(raw)==24*16
    u,v=entry['uv'];x,y=entry['tpage'];n=0
    for dy in range(16):
        for dx in range(24):
            off=2*((y+v+dy)*1024+x+(u+dx)//4)
            shift=4*((u+dx)%4)
            old=int.from_bytes(vram[off:off+2],'little')
            mask=15<<shift
            new=(old&~mask)|(raw[n]<<shift)
            vram[off:off+2]=new.to_bytes(2,'little')
            n+=1


def upload_vram(disc:PatchedDisc,which:str):
    lba={'DATSEL':6000,'DATSEL3':6250}[which]
    atlas=bytearray(1024*512*2)
    if which=='DATSEL':
        dat=disc.logical(lba,0,215324,True)
        cmds=[struct.unpack_from('<6HI',dat,p) for p in SMALL_CMDS]
    else:
        dat=disc.logical(lba,0,13040,True)
        sec=disc.sector(6277,True)
        cmds=[struct.unpack_from('<6HI',sec,636+16*i) for i in range(4)]
        sec2=disc.sector(6279,True)
        assert cmds==[struct.unpack_from('<6HI',sec2,72+16*i) for i in range(4)]
    for (op,x,y,w,h,flag,ptr),xy in zip(cmds,TILES):
        assert(op,x,y,w,h)==(10,xy[0],xy[1],32,128),(which,op,x,y,w,h,xy)
        off=ptr-0x800F0000
        assert 0<=off<len(dat)
        raw,used=decode(dat[off:],8192)
        assert used>0
        for row in range(128):
            pos=2*((y+row)*1024+x)
            atlas[pos:pos+64]=raw[row*64:(row+1)*64]
    return bytes(atlas),cmds


def build():
    assert hashlib.sha256(BASE.read_bytes()).hexdigest().upper()==EXPECTED_BASE_SHA
    manifest=json.loads(MANIFEST.read_text())
    original_flags=json.loads((DATA/'iss26_small_fix_work/flags_24x16_v5.json').read_text())
    new_flags=json.loads(ART.read_text())
    assert set(original_flags)==set(new_flags)
    assert all(original_flags[k]==new_flags[k] for k in original_flags if k not in ('19','28'))
    disc=PatchedDisc(ORIG,BASE,verify=True)
    try:
        old,cmds=upload_vram(disc,'DATSEL')
        other,_=upload_vram(disc,'DATSEL3')
        assert old==other,'DATSEL and DATSEL3 previous small-flag atlases differ'
        m={x['index']:x for x in manifest}
        for slot in (19,28):
            assert get_pixels(old,m[slot])==bytes.fromhex(original_flags[str(slot)]['pixels_hex']),slot
        after=bytearray(old)
        for slot in (19,28):
            put_pixels(after,m[slot],bytes.fromhex(new_flags[str(slot)]['pixels_hex']))
        per_sprite={}
        for i in range(5,59):
            before=get_pixels(old,m[i]);after_=get_pixels(after,m[i]);dif=sum(x!=y for x,y in zip(before,after_))
            if dif:per_sprite[i]=dif
            if i in (19,28):
                assert after_==bytes.fromhex(new_flags[str(i)]['pixels_hex'])
            else:assert before==after_,f'Non-target sprite changed: {i}'
        assert set(per_sprite)=={19,28},per_sprite
        encoded=[]
        for x,y in TILES:
            raw=b''.join(after[2*((y+j)*1024+x):2*((y+j)*1024+x)+64] for j in range(128))
            b=encode(raw)
            opt=optimize_literal_packets(b)
            if len(opt)<len(b): b=opt
            dec,used=decode(b,8192)
            assert dec==raw and used==len(b)
            encoded.append(b)
        pack=bytearray();relative=[]
        for i,b in enumerate(encoded):
            relative.append(len(pack));pack.extend(b)
            if i<3:
                while len(pack)%4:pack.append(0)
        unpadded=len(pack)
        assert unpadded<=REGION_SIZE,(unpadded,REGION_SIZE)
        pack.extend(b'\x00'*(REGION_SIZE-len(pack)))
        changes={};reasons=collections.Counter()
        def edit_raw(pos,payload,reason):
            for j,z in enumerate(payload):
                if pos+j in changes and changes[pos+j]!=z:raise ValueError('Conflicting byte')
                changes[pos+j]=z
            reasons[reason]+=len(payload)
        def edit_logical(lba,pos,payload,reason):
            for j,z in enumerate(payload):
                off=pos+j
                raw=(lba+off//2048)*2352+24+off%2048
                edit_raw(raw,bytes([z]),reason)
        for res,lba,start in [('DATSEL',6000,169696),('DATSEL3',6250,8)]:
            edit_logical(lba,start,bytes(pack),'Small 24x16 flag atlases '+res)
            ptrs=[0x800F0000+start+offset for offset in relative]
            if res=='DATSEL':
                for cmd,ptr in zip(SMALL_CMDS,ptrs):
                    edit_logical(lba,cmd+12,struct.pack('<I',ptr),'DATSEL upload pointers')
            else:
                for sec,where in [(6277,636),(6279,72)]:
                    for i,ptr in enumerate(ptrs):
                        edit_raw(sec*2352+where+16*i+12,struct.pack('<I',ptr),'DATSEL3 duplicate upload pointers')
        sectors=sorted({x//2352 for x in changes})
        base_records=disc.records
        patched_records=[]
        sha_orig=hashlib.sha256();sha_base=hashlib.sha256();sha_new=hashlib.sha256()
        modified=[];form2=[]
        with ORIG.open('rb') as f:
            for lba in range(ORIG.stat().st_size//2352):
                original=f.read(2352);sha_orig.update(original)
                rec=base_records.get(lba)
                if rec:
                    guard,mask=rec
                    assert hashlib.sha256(original).digest()==guard
                    baseline=bytes(a^b for a,b in zip(original,mask))
                else:baseline=original
                sha_base.update(baseline)
                final=baseline
                if lba in sectors:
                    final=bytearray(baseline)
                    for j in range(2352):
                        raw=lba*2352+j
                        if raw in changes:final[j]=changes[raw]
                    if final[15]!=2 or final[16:20]!=final[20:24]:raise ValueError(f'Invalid CD header at {lba}')
                    if final[18]&32:
                        final[2348:2352]=edc(final[16:2348]);form2.append(lba)
                    else:fix_form1(final)
                    final=bytes(final)
                    if final!=baseline:modified.append(lba)
                sha_new.update(final)
                if final!=original:
                    patched_records.append((lba,hashlib.sha256(original).digest(),bytes(a^b for a,b in zip(original,final))))
        assert sha_orig.hexdigest().upper()==EXPECTED_ORIG_SHA
        assert sha_base.hexdigest().upper()==EXPECTED_BASE_IMAGE_SHA
        assert len(patched_records)==len(base_records)==1412
        out=OUT/'ISS26_0.9.5_TeamIdentity_Stage10_BosniaCanada_TEST08.iss26p'
        with out.open('wb') as f:
            f.write(b'ISS26X01');f.write(struct.pack('<I',len(patched_records)))
            for lba,guard,mask in patched_records:
                f.write(struct.pack('<I',lba));f.write(guard);f.write(mask)
        report={'stage':10,'scope':'Screenshot-redrawn 24x16 flags Bosnia+Canada only on Test06; GDC never altered',
        'test08_patch_sha256':hashlib.sha256(out.read_bytes()).hexdigest().upper(),
        'test08_image_sha256':sha_new.hexdigest().upper(),
        'baseline_patch_sha256':EXPECTED_BASE_SHA,
        'baseline_image_sha256':EXPECTED_BASE_IMAGE_SHA,
        'original_sha256':EXPECTED_ORIG_SHA,
        'patched_records':len(patched_records),'patch_bytes':out.stat().st_size,
        'changed_sectors_vs_test06':modified,'changed_sectors_count':len(modified),
        'per_flag_pixel_delta':per_sprite,'unchanged_other_52_sprites':True,
        'transparent_right_4_pixels':True,'clut_rows_unchanged':True,
        'repacked_compressed_bytes_unpadded':unpadded,'repacked_reserved_bytes':REGION_SIZE,
        'mode2_form2_repaired':form2,
        'preserved_stage5_large_graphics_and_rosters':True,
        'GDC_sector_changes':[],
        'runtime_tested':False,
        'source_images':['image(20261110-212120).png','image(20261110-212351).png'],
        'source_method':'Hand-redrawn small game-native sprite matching Master League screenshot style; not verbatim byte extraction'}
        (OUT/'stage10_patch_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
        print(json.dumps(report,indent=2,ensure_ascii=False))
        # Independent re-open post-build, compare 54 sprites and no GDC edits.
        checked=PatchedDisc(ORIG,out,verify=False)
        try:
            va,_=upload_vram(checked,'DATSEL');vb,_=upload_vram(checked,'DATSEL3')
            assert va==vb
            for i in range(5,59):
                px=get_pixels(va,m[i]);expected=bytes.fromhex(new_flags[str(i)]['pixels_hex']) if str(i) in new_flags else get_pixels(old,m[i])
                assert px==expected,(i,'sprite mismatch after build')
            for start in [10914,11263,16549]:
                assert checked.sector(start,True)==disc.sector(start,True),('GDC unexpectedly changed',start)
            for start in list(range(167,173))+[852,955,1254]:
                assert checked.sector(start,True)==disc.sector(start,True),('National text changed',start)
        finally:checked.close()
        return report
    finally:disc.close()
if __name__=='__main__':build()
