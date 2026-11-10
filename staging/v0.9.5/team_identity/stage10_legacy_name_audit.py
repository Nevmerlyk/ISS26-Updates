#!/usr/bin/env python3
"""Read-only legacy prematch-name source preflight for Test08.
Do not edit the three-letter SELECTC codes until their runtime semantics are known.
"""
from pathlib import Path
import json,re,csv,sys
sys.path.insert(0,'/mnt/data/iss26_team_identity')
from team_identity_audit import PatchedDisc,REGIONS,CODE_BANK
ROOT=Path('/mnt/data/iss26_team_identity')
TRACK=Path('/mnt/data/ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin')
PATCH=ROOT/'stage10_results/ISS26_0.9.5_TeamIdentity_Stage10_BosniaCanada_TEST08.iss26p'
TERMS=[b'RUSSIA',b'GREECE',b'JAMAICA']

def scan_disc(disc,patched):
    found={t.decode('ascii'):0 for t in TERMS}
    overlap=b''
    # Raw sector scan, preserving 5-byte overlap across sector boundaries.
    for lba in range(TRACK.stat().st_size//2352):
        buf=overlap+disc.sector(lba,patched)
        for term in TERMS:
            found[term.decode('ascii')]+=len(re.findall(re.escape(term),buf,re.I))
        overlap=buf[-5:]
    return found

def main():
    d=PatchedDisc(TRACK,PATCH,verify=True)
    try:
        original=scan_disc(d,False)
        new=scan_disc(d,True)
        codes=[]
        for slot in [2,4,10,11,14,18,23,26,27,28,29,31,34,36,50,52,53]:
            off=CODE_BANK['from']+slot*4
            old=d.logical(CODE_BANK['lba'],off,4,False).rstrip(b'\0').decode('ascii')
            cur=d.logical(CODE_BANK['lba'],off,4,True).rstrip(b'\0').decode('ascii')
            codes.append({'slot':slot,'code_original':old,'code_test08':cur,'unchanged':old==cur})
        assert all(x['unchanged'] for x in codes)
        # SELECT/SELECT3 new text banks already correct for Bosnia / NZ / Canada.
        check=[]
        for name in ('SELECT','SELECT3','SELECTC'):
            text=d.resource(REGIONS[name],True)
            check.append({'resource':name,'bosnia_present':b'BOSNIA' in text.upper(),'new_zealand_present':b'N.ZEAL' in text.upper(),'canada_present':b'CANADA' in text.upper()})
        assert all(a['bosnia_present'] and a['new_zealand_present'] and a['canada_present'] for a in check)
        report={'status':'READ-ONLY FORENSICS; NO TEXT PATCH APPLIED',
                'test_version':'0.9.6-teamidentity-test08',
                'original_disc_ascii_hits':original,'test08_disc_ascii_hits':new,
                'national_teams_renamed_with_unchanged_abbreviation':len(codes),
                'legacy_code_examples':{x['slot']:x['code_test08'] for x in codes if x['slot'] in (14,23,26)},
                'select_text_bank_status':check,
                'interpretation':'Visible prematch Russia/Greece cannot be fixed by another literal ASCII rename in the modified disc; 3-letter codes remain but their runtime semantic role is unverified. The root may be a packed table, GPU-assembled glyph indices, lookup by slot, or another non-ASCII resource.',
                'safe_next_step':'Trace the prematch label origin using PCSX-Redux RAM/GPU or inspect packed team ID name mapping; DO NOT rewrite RUS/GRC/JAM codes until game ID usages are excluded.'}
        p=ROOT/'stage10_results/stage10_legacy_prematch_name_audit.json'
        p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2))
    finally:d.close()
if __name__=='__main__':main()
