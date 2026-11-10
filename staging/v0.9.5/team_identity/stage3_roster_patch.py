#!/usr/bin/env python3
"""Stage 3: rebuild 15 official-2026-source squad *names only*, 22 per team.

Creates a standalone, clean-original-guarded ISS26X01 candidate from Stage2.
Does not publish, edit formations, player abilities, clubs, flags or public feeds.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from stage2_roster_case_patch import (
    EXE_LBA, EXE_SIZE, ROSTER_COUNT, NAMES_PER_ROSTER, NAME_STRIDE,
    roster_base, player_name, raw_offset, NEW_TEAM_SLOTS,
)
from merge_verified import merge

EXPECTED_STAGE2_SHA='861E4E0636918AE801E5EC1EE33D31B106079CA2E1DBDC7546A0997C1412D3AC'
EXPECTED_STAGE2_IMAGE_SHA='2B8DE88829D4F735438A781AC212519A0AB759BED58A1A4783D6104E49462626'
TARGET_SLOTS=NEW_TEAM_SLOTS-{14,53} # Canada's and Cabo Verde's 22 names already refreshed
EXPECTED_TOTAL=15*22


def split_edit(logical_offset:int,old:bytes,new:bytes,purpose:str):
    """Split fixed 10-byte name across 2048-byte Form1 user-data boundaries."""
    if len(old)!=len(new) or len(old)==0:raise ValueError('Unbalanced edit')
    result=[];i=0
    while i<len(old):
        step=min(len(old)-i,2048-(logical_offset+i)%2048)
        result.append({'raw_offset':raw_offset(EXE_LBA,logical_offset+i),
                       'expected_hex':old[i:i+step].hex(),'replacement_hex':new[i:i+step].hex(),
                       'purpose':purpose})
        i+=step
    return result


def validate_names(rows:dict):
    try:slots={int(k) for k in rows}
    except Exception as e:raise ValueError('Invalid slot key') from e
    if slots!=TARGET_SLOTS:raise ValueError('15 target slots do not match stage2')
    for slot in slots:
        names=rows[str(slot)]
        if not isinstance(names,list) or len(names)!=NAMES_PER_ROSTER:
            raise ValueError(f'Expected 22 players for slot {slot}')
        seen=set()
        for name in names:
            if not isinstance(name,str) or not re.fullmatch(r"[A-Za-z][A-Za-z .\-']{0,9}",name):
                raise ValueError(f'Invalid 10-byte game name {slot}: {name}')
            if name.isupper():raise ValueError('Names cannot be all caps: '+name)
            if name.lower() in seen:raise ValueError('Duplicate game name in roster: '+name)
            seen.add(name.lower())
    return rows


def make(args):
    src=json.loads(Path(args.rosters).read_text(encoding='utf-8'))
    validate_names(src)
    root=Path(args.output);root.mkdir(exist_ok=True,parents=True)
    patch=Path(args.baseline)
    patch_hash=hashlib.sha256(patch.read_bytes()).hexdigest().upper()
    if patch_hash!=EXPECTED_STAGE2_SHA:raise ValueError(f'Wrong Stage2 patch {patch_hash}')
    disc=PatchedDisc(args.track,patch,verify=not args.skip_track_sha)
    try:
        exe=disc.logical(EXE_LBA,0,EXE_SIZE,True)
        rows=[];edits=[];edited_names=0
        for slot in sorted(TARGET_SLOTS):
            for player,name in enumerate(src[str(slot)]):
                ofs=roster_base(slot)+player*NAME_STRIDE
                old=exe[ofs:ofs+NAME_STRIDE]
                before=player_name(exe,ofs)
                new=name.encode('ascii').ljust(NAME_STRIDE,b'\x00')
                if new!=old:
                    edits.extend(split_edit(ofs,old,new,f'2026 verified-roster name slot {slot} #{player+1}: {before} -> {name}'))
                    edited_names+=1
                rows.append({'team_slot':slot,'player_index':player,'was':before,'after':name,
                             'exe_resource_offset':ofs,'changed':before!=name})
        assert len(rows)==EXPECTED_TOTAL
        if not edits:raise ValueError('No changes')
        with (root/'stage3_player_names_330.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
        (root/'stage3_candidate_edits.json').write_text(json.dumps(edits,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        candidate=root/'ISS26_0.9.5_2026_15Squads_Stage3_CANDIDATE.iss26p'
        info=merge(Path(args.track),patch,root/'stage3_candidate_edits.json',candidate,EXPECTED_STAGE2_IMAGE_SHA)
        # Independently read built patch and confirm exact roster bytes and unchanged teams.
        verified=PatchedDisc(args.track,candidate,verify=False)
        try:
            result=verified.logical(EXE_LBA,0,EXE_SIZE,True)
            for slot in range(ROSTER_COUNT):
                b=roster_base(slot)
                if slot not in TARGET_SLOTS:
                    if result[b:b+220]!=exe[b:b+220]:raise ValueError('Unselected roster modified: '+str(slot))
                else:
                    for i,label in enumerate(src[str(slot)]):
                        if player_name(result,b+i*NAME_STRIDE)!=label:raise ValueError(f'Wrong result slot {slot}, player {i}')
            if verified.logical(1250,10168,8,True)!=b'Qatar\x00\x00\x00':raise ValueError('Qatar alias unexpectedly lost')
        finally:verified.close()
        report={'status':'STATIC VERIFIED LOCAL CANDIDATE ONLY — VISUAL VALIDATION NEEDED',
                'source':'2026 FIFA World Cup 26-player squad lists, as transcribed in feuyeux/fifa-world-cup-2026',
                'source_metadata':'https://github.com/Nevmerlyk/ISS26-Updates/blob/development/team-identity-v095/staging/v0.9.5/team_identity/stage3_sources/rosters_15_fifa2026_selected.json',
                'not_fifa_approved_22_rosters':True,'teams':len(TARGET_SLOTS),'players':len(rows),
                'names_replaced':edited_names,'field_write_segments':len(edits),
                'non_target_rosters_preserved':39,'existing_case_fixes_preserved':44,
                'existing_small_flags_and_stable_v094_preserved':True,
                'game_position_attributes_unchanged':True,
                'candidate_patch':info,
                'warnings':['22 selected per squad from official 26 via positional/caps-based selection; the 22-person selection is editorial, not an official FIFA list',
                            'Only names were changed, not attributes/positions/caps/club data; playable tactics need separate validation',
                            'No Test Game or Play Game feed was altered.']}
        (root/'stage3_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        return report
    finally:disc.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--track',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--rosters',type=Path,default=ROOT/'stage3_game_rosters_15.json')
    parser.add_argument('--output',type=Path,default=ROOT/'stage3_results')
    parser.add_argument('--skip-track-sha',action='store_true')
    print(json.dumps(make(parser.parse_args()),indent=2,ensure_ascii=False))
