#!/usr/bin/env python3
"""Stage 5: safely place Bosnia in an unused *large national flag* texture style.

Creates a standalone clean-EU-Track01 ISS26X01 candidate layered *logically*
from Stage3 (the output itself is independently applicable to the CLEAN disc).
Only the Bosnia two style ID fields and one 64x28 tile in each of two decoded
DATSEL/DATSEL3 uploads are edited. Leaves stadium GDC, names, scoreboard sprite
sources and public release feeds unchanged until in-game validation.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from merge_verified import merge
from wecodec_stage5 import decode,encode,optimize_literal_packets

EXPECTED_STAGE3_PATCH='E8EE2D51CA513C7A61EB8A8D8C30565CA8E9007D4B7337B57C550EA3D4C4B03D'
EXPECTED_STAGE3_IMAGE='D6DE5934896229BCFA4A88CDEEE114E2B630947DED68FD51C1EB90EBAB4DDD32'
TARGET_STYLE=10
START_STYLE=7
BLIT_ROWS=28
BLIT_COLS_BYTES=32 # one 64-pixel 4bpp flag per VRAM row
EXPECTED_COMPRESSED_LEN=1910
UPLOADS=[{'name':'DATSEL','lba':6000,'command_offset':212508,'ptr':182728},
         {'name':'DATSEL3','lba':6250,'command_offset':None,'ptr':13040}]
DATSEL3_COMMAND_COPIES=[(6277,716),(6279,152)]
STYLE_FIELDS=[0x1E94CC+30,0x224C50+30]


def raw_offset(lba, logical_offset):
    return (lba+logical_offset//2048)*2352+24+logical_offset%2048


def split_bytes(logical_lba,offset,old,new,purpose):
    if len(old)!=len(new) or not old:raise ValueError('Unequal/empty edits')
    out=[];j=0
    while j<len(old):
        size=min(len(old)-j,2048-(offset+j)%2048)
        out.append({'raw_offset':raw_offset(logical_lba,offset+j),
                    'expected_hex':old[j:j+size].hex(),
                    'replacement_hex':new[j:j+size].hex(),
                    'purpose':purpose})
        j+=size
    return out


def form2_command_check(disc):
    expected=struct.pack('<6H',10,864,256,32,128,0)
    ptr=0x800F0000+UPLOADS[1]['ptr']
    for lba,offset in DATSEL3_COMMAND_COPIES:
        s=disc.sector(lba,True)
        if s[offset:offset+12]!=expected or struct.unpack_from('<I',s,offset+12)[0]!=ptr:
            raise ValueError(f'DATSEL3 large flag command changed at {lba}+{offset}')


def prepare_upload(disc,info,art):
    lba=info['lba'];off=info['ptr']
    source=disc.logical(lba,off,EXPECTED_COMPRESSED_LEN,True)
    raw,used=decode(source,8192)
    if used!=EXPECTED_COMPRESSED_LEN:raise ValueError(f"{info['name']} unexpected encoded length {used}")
    if info['name']=='DATSEL':
        cmd=disc.logical(lba,info['command_offset'],16,True)
        expected=struct.pack('<6HI',10,864,256,32,128,0,0x800F0000+off)
        if cmd!=expected:raise ValueError('DATSEL large flag command changed')
    else:form2_command_check(disc)
    after=bytearray(raw)
    for y in range(BLIT_ROWS):
        a=(64+y)*64
        after[a:a+BLIT_COLS_BYTES]=art[y*BLIT_COLS_BYTES:(y+1)*BLIT_COLS_BYTES]
    # Control exact 64x28 rectangle, preserving the other 3,200 VRAM words.
    changed=[i for i,(x,y) in enumerate(zip(raw,after)) if x!=y]
    expected_region={r*64+c for r in range(64,64+BLIT_ROWS) for c in range(BLIT_COLS_BYTES)}
    if set(changed)!=expected_region:
        raise ValueError(f"{info['name']} changed unexpected atlas bytes {len(changed)}")
    opts=[encode(bytes(after))]
    opts.append(optimize_literal_packets(opts[0]))
    encoded=min(opts,key=len)
    if len(encoded)>used:raise ValueError(f"{info['name']} compressed region overflow")
    check,consumed=decode(encoded,8192)
    if check!=bytes(after) or consumed!=len(encoded):raise ValueError('Nonreversible compression')
    # Padding is stored only in the known original 1910-byte buffer; following
    # data and all 16-byte GPU commands are untouched, no pointer relocation.
    replacement=encoded + bytes(used-len(encoded))
    report={'source':info['name'],'lba':lba,'logical_offset':off,
            'encoded_bytes_before':used,'encoded_bytes_after':len(encoded),
            'available_slack':used-len(encoded),'changed_pixels_in_64x28':len(changed)*2,
            'raw_decoded_sha256_before':hashlib.sha256(raw).hexdigest().upper(),
            'raw_decoded_sha256_after':hashlib.sha256(after).hexdigest().upper()}
    return split_bytes(lba,off,source,replacement,'Bosnia dedicated style 10 large 64x28 texture '+info['name']),report,bytes(after)


def build(args):
    root=Path(args.output);root.mkdir(parents=True,exist_ok=True)
    base=Path(args.stage3)
    if hashlib.sha256(base.read_bytes()).hexdigest().upper()!=EXPECTED_STAGE3_PATCH:
        raise ValueError('Wrong Stage 3 baseline patch')
    art_path=Path(args.art)
    if art_path.is_file():
        art=art_path.read_bytes()
    else:
        embedded=ROOT/'stage4_results/bosnia_style10_art/assets_4bpp_base64.json'
        source=json.loads(embedded.read_text(encoding='utf-8'))['large_64x28']
        art=base64.b64decode(source['base64'],validate=True)
        if hashlib.sha256(art).hexdigest().upper()!=source['sha256'].upper():
            raise ValueError('Bundled 4bpp art digest mismatch')
    if len(art)!=896:raise ValueError('Bosnia 64x28 source must be 896 bytes')
    if any((b&15) not in (1,2,3) or (b>>4) not in (1,2,3) for b in art):
        raise ValueError('Style10 source should contain only 4bpp [1..3] pixel pairs')
    disc=PatchedDisc(args.track,base,verify=True)
    try:
        edits=[]
        for raw in STYLE_FIELDS:
            lba,off=divmod(raw,2352)
            if off>=2072:raise ValueError('Style byte falls outside user data')
            before=disc.sector(lba,True)[off:off+1]
            if before!=bytes([START_STYLE]):raise ValueError(f'Bosnia old style not {START_STYLE} at {raw:#x}')
            edits.append({'raw_offset':raw,'expected_hex':before.hex(),
                          'replacement_hex':bytes([TARGET_STYLE]).hex(),
                          'purpose':'Bosnia team slot 23 style 7 -> isolated style 10'})
        upload_reports=[]
        for info in UPLOADS:
            e,report,_=prepare_upload(disc,info,art)
            upload_reports.append(report);edits.extend(e)
        (root/'stage5_candidate_edits.json').write_text(json.dumps(edits,indent=2,ensure_ascii=False)+'\n')
        candidate=root/'ISS26_v095_Stage5_BosniaStyle10_Stage3Combined_CANDIDATE.iss26p'
        meta=merge(Path(args.track),base,root/'stage5_candidate_edits.json',candidate,EXPECTED_STAGE3_IMAGE)
        result=PatchedDisc(args.track,candidate,verify=False)
        try:
            for raw in STYLE_FIELDS:
                lba,off=divmod(raw,2352)
                assert result.sector(lba,True)[off]==TARGET_STYLE
            for info in UPLOADS:
                _,_,expected=prepare_upload(disc,info,art)
                unpack,consumed=decode(result.logical(info['lba'],info['ptr'],EXPECTED_COMPRESSED_LEN,True),8192)
                if unpack!=expected:raise ValueError('Patched resource does not produce expected Bosnia style10')
                assert consumed<EXPECTED_COMPRESSED_LEN
            # No changes to player roster or name table sectors: they retain Stage3, not just v0.9.4.
            for lba in range(167,173):
                if result.sector(lba,True)!=disc.sector(lba,True):
                    raise ValueError('Stage3 roster byte changed')
            # Confirm all original Test05 small flag 24x16 atlas uploads remain byte-exact.
            for lba in list(range(6082,6089))+list(range(6250,6256)):
                if result.sector(lba,True)!=disc.sector(lba,True):
                    # DATSEL3 stream starts in 6256 and is not among those sectors
                    raise ValueError('Test05 24x16 graphics unexpectedly changed '+str(lba))
        finally:result.close()
        report={'stage':5,'status':'STATIC-VALIDATED CANDIDATE; requires emulator screen/stadium verification',
                'patch':meta,'style':{'team_slot':23,'old':7,'new':10,'table_edits':len(STYLE_FIELDS)},
                'graphics':upload_reports,'original_small_24x16_flags_preserved':True,
                'existing_330_new_player_names_preserved':True,
                'bosnia_texture_source':'Stage4 prepared original pixel-art, NOT extracted verbatim from Master League',
                'scoreboard_24x8_source_replaced':False,'stadium_GDC_uploads_replaced':False,
                'public_feed_modified':False,
                'warnings':['Only DATSEL and DATSEL3 style10 large textures and two select table IDs patched.',
                            'GDC stadium variants and scoreboard remain unresolved; may overwrite the new flag during runtime.',
                            'The stored 2026 22-person names are not yet matched to verified native PS1 roles and stats.',
                            'Do not promote to Play Game or Test Game until runtime proof is obtained.']}
        (root/'stage5_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        return report
    finally:disc.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--track',type=Path,required=True)
    p.add_argument('--stage3',type=Path,required=True)
    p.add_argument('--art',type=Path,default=ROOT/'stage4_results/bosnia_style10_art/large_64x28.4bpp')
    p.add_argument('--output',type=Path,default=ROOT/'stage5_results')
    print(json.dumps(build(p.parse_args()),indent=2,ensure_ascii=False))
