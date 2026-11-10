#!/usr/bin/env python3
"""ISS26 Team Identity Stage 2: verified team-roster mapping + exact case edits.

Builds a *local candidate* standalone patch from the published Test 05 baseline.
Does NOT update any public feed or alter the clean original CD image.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, sys
from pathlib import Path

# Import the audited, exact-disc parsers and Mode2 ECC patch engine.
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(PROJECT))
from team_identity_audit import PatchedDisc
from merge_verified import merge

EXE_LBA=24
EXE_SIZE=339968
ROSTER_START=293204
ROSTER_COUNT=54
NAMES_PER_ROSTER=22
NAME_STRIDE=10
SLOT_STRIDE=NAMES_PER_ROSTER*NAME_STRIDE
SLES_ISO='SLES_033.21'
BASE_PATCH_SHA='2F07692027F4F4CE173A26CA3B169F5335CF6D25378EACBD9B5693A77E561690'
BASE_IMAGE_SHA='EC296541B42836303A7BA936F9E25DD69B89418DA744B0751F9A488548330560'
TEAM_NAMES=(ROOT/'results'/'team_identity_54.csv')
NEW_TEAM_SLOTS={2,4,10,11,14,18,23,26,27,28,29,31,34,36,50,52,53}
CAPS_TEAM_SLOTS={24,53}


def roster_base(slot:int)->int:
    if not 0 <= slot < ROSTER_COUNT:raise ValueError('Invalid team slot')
    return ROSTER_START+(ROSTER_COUNT-1-slot)*SLOT_STRIDE


def player_name(data:bytes, offset:int)->str:
    raw=data[offset:offset+NAME_STRIDE]
    if len(raw)!=NAME_STRIDE:raise ValueError('Truncated player name')
    if raw.split(b'\0',1)[1:] and any(b for b in raw[raw.index(0):]):
        raise ValueError('Nonzero garbage after name terminator')
    name=raw.split(b'\0',1)[0].decode('ascii','strict').rstrip(' ')
    if not re.fullmatch(r"[A-Za-z][A-Za-z .\-']{0,9}",name):raise ValueError(f'Bad player name in active bank: {name!r} at {offset}')
    return name


def recase(name:str)->str:
    # Applies only to two verified uppercase national roster blocks.
    # Preserves spelling, diacritic limitations, and initials exactly.
    if not name.isupper():raise ValueError('Only confirmed all-uppercase names may be recased')
    return name.title()


def raw_offset(lba:int, offset:int)->int:
    return (lba+offset//2048)*2352+24+(offset%2048)


def csv_out(path:Path, rows:list[dict], header:list[str])->None:
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=header,extrasaction='ignore');writer.writeheader();writer.writerows(rows)


def build(args):
    output=Path(args.out)
    output.mkdir(parents=True,exist_ok=True)
    baseline=Path(args.baseline)
    if hashlib.sha256(baseline.read_bytes()).hexdigest().upper()!=BASE_PATCH_SHA:raise ValueError('Wrong Test 05 patch input')
    names=list(csv.DictReader(TEAM_NAMES.open(newline='',encoding='utf-8')))
    assert len(names)==54 and all(int(x['slot'])==i for i,x in enumerate(names))
    disc=PatchedDisc(args.track,baseline,verify=not args.skip_track_sha)
    try:
        exe=disc.logical(EXE_LBA,0,EXE_SIZE,True)
        original_exe=disc.logical(EXE_LBA,0,EXE_SIZE,False)
        result=[];fixes=[];edits=[];replacements=[]
        for slot in range(54):
            base=roster_base(slot)
            team=names[slot]['main_select_name']
            count_upper=0;count_changed=0
            for player in range(22):
                ofs=base+player*NAME_STRIDE
                before=player_name(original_exe,ofs)
                current=player_name(exe,ofs)
                altered=before!=current
                is_caps=current.isupper()
                count_changed+=altered
                count_upper+=is_caps
                record={
                    'team_slot':slot,'team':team,'team_is_replacement':slot in NEW_TEAM_SLOTS,
                    'player_index':player,'exe_resource_offset':ofs,
                    'current_name':current,'original_2001_name':before,
                    'changed_since_original':altered,'entire_name_uppercase':is_caps,
                    'proposed_case':recase(current) if slot in CAPS_TEAM_SLOTS else current
                }
                result.append(record)
                if slot in CAPS_TEAM_SLOTS:
                    assert is_caps, f'Expected uppercase roster {team} player {player}: {current}'
                    fix=recase(current)
                    raw=exe[ofs:ofs+10]
                    updated=fix.encode('ascii')+raw[len(fix):]
                    assert len(updated)==len(raw) and updated.upper()==raw.upper()
                    edits.append({'raw_offset':raw_offset(EXE_LBA,ofs),'expected_hex':raw.hex(),'replacement_hex':updated.hex(),'purpose':f'Player name case only: {team} #{player+1} {current} -> {fix}'})
                    fixes.append({**record,'replacement_name':fix})
            replacements.append({'team_slot':slot,'team':team,'is_replacement':slot in NEW_TEAM_SLOTS,
                'player_names_changed_since_2001':count_changed,'all_uppercase_names':count_upper,
                'still_original_roster':count_changed==0,
                'needs_roster_rebuild':slot in NEW_TEAM_SLOTS and count_changed==0})
        assert len(result)==1188
        assert len(fixes)==44
        assert [x['team'] for x in replacements if x['all_uppercase_names']==22]==['UKRAINE','C.VERDE']
        assert sum(x['needs_roster_rebuild'] for x in replacements)==15
        assert sorted(x['team_slot'] for x in replacements if x['needs_roster_rebuild'])==sorted(NEW_TEAM_SLOTS-{14,53})
        # Single known UI name divergence is a pure, same-length, NULL padded ASCII edit.
        qatar_offset=10168
        old=disc.logical(1250,qatar_offset,8,True)
        assert old==b'U.A.E.\0\0',repr(old)
        new=b'Qatar\0\0\0'
        edits.append({'raw_offset':raw_offset(1250,qatar_offset),'expected_hex':old.hex(),'replacement_hex':new.hex(),
                      'purpose':'Correct Qatar name in secondary select bank; team/flag IDs unchanged'})
        csv_out(output/'national_rosters_1188.csv',result,list(result[0]))
        csv_out(output/'case_fixes_44.csv',fixes,list(fixes[0]))
        csv_out(output/'roster_status_54.csv',replacements,list(replacements[0]))
        (output/'candidate_edits.json').write_text(json.dumps(edits,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        patch_info=None
        if args.build_candidate:
            patch_path=output/'ISS26_TeamIdentity_CaseFix_Stage2_CANDIDATE.iss26p'
            patch_info=merge(Path(args.track),baseline,output/'candidate_edits.json',patch_path,BASE_IMAGE_SHA)
            # Verify edited records from candidate are exactly expected, by re-reading.
            verify=PatchedDisc(args.track,patch_path,verify=False)
            try:
                out_exe=verify.logical(EXE_LBA,0,EXE_SIZE,True)
                for row in result:
                    off=row['exe_resource_offset']
                    expected=row['proposed_case']
                    assert player_name(out_exe,off)==expected,(row,player_name(out_exe,off))
                assert verify.logical(1250,qatar_offset,8,True)==new
                for slot in range(54):
                    if slot not in CAPS_TEAM_SLOTS:
                        b=roster_base(slot)
                        assert out_exe[b:b+220]==exe[b:b+220]
            finally:verify.close()
        summary={'status':'STAGE2 CANDIDATE, STATIC VERIFIED ONLY; NOT PUBLISHED',
                 'team_roster_count':54,'players_per_team':22,'players_total':len(result),
                 'exe_roster_bank_start':ROSTER_START,'exe_roster_bank_length':54*22*10,
                 'uppercase_team_slots':[24,53],'case_fixes':len(fixes),
                 'replaced_national_teams_total':len(NEW_TEAM_SLOTS),
                 'replaced_teams_still_using_2001_player_names':sum(x['needs_roster_rebuild'] for x in replacements),
                 'replaced_teams_with_new_names':[x['team'] for x in replacements if x['is_replacement'] and not x['still_original_roster']],
                 'known_team_name_candidate':'QATAR from U.A.E. in SELECT3 secondary text bank',
                 'suspicious_3_letter_team_codes_changed':0,
                 'full_original_track_sha_guarded':not args.skip_track_sha,
                 'patch':patch_info,
                 'warnings':['The other 15 new national squads need authentic name data; do not autogenerate players.',
                             'Only case was changed for Ukraine/Cabo Verde: no spelling corrections and no new players.',
                             'The candidate is not an approved release. Test Game currently still uses Test 05.']}
        (output/'stage2_report.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        return summary
    finally:
        disc.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--track',required=True);p.add_argument('--baseline',required=True);p.add_argument('--out',default=str(ROOT/'stage2_results'));p.add_argument('--build-candidate',action='store_true');p.add_argument('--skip-track-sha',action='store_true')
    args=p.parse_args();print(json.dumps(build(args),indent=2,ensure_ascii=False))
