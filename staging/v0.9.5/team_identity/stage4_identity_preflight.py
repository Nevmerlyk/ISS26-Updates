#!/usr/bin/env python3
"""Stage 4: validate source-backed team-role assignments and graphic-style ownership.

Read-only. Refuses to treat a shared style as safe for a Bosnia-only texture edit.
Designed to check the exact standalone Stage3 patch over the clean EU Track 01.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,sys
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from stage2_roster_case_patch import EXE_LBA,EXE_SIZE,roster_base,player_name

STAGE3_SHA='E8EE2D51CA513C7A61EB8A8D8C30565CA8E9007D4B7337B57C550EA3D4C4B03D'
ROLE_STRINGS={
2:'GDDDDMMMMFFDDDMFFFFFGG', 4:'GDDDDMMMMFFDDDMMMFMMGG',
10:'GDDDDMMMMFFDDDMMMFFMGG', 11:'GDDDDMMMMFFDDDMMMFFFGG',
18:'GDDDDMMMMFFDDDMMMFFFGG',23:'GDDDDMMMMFFDDDMMMFFFGG',
26:'GDDDDMMMMFFDDDMMMFFFGG',27:'GDDDDMMMMFFDDDMMMFFFGG',
28:'GDDDDMMMMFFDDDMMMFFFGG',29:'GDDDDMMMMFFDDDMMMFFFGG',
31:'GDDDDMMMMFFDDDMFFFFFGG',34:'GDDDDMMMMFFDDDMMMFFFGG',
36:'GDDDDMMMMFFDDDMMFFFFGG',50:'GDDDDMMMMFFDDDMMFFFFGG',
52:'GDDDDMMMMFFDDDMMMFFFGG',
}
# Stage3's declared intended game position layout. Actual in-game position-field semantics are NOT reverse-engineered yet.
INTENDED='GDDDDMMMMFFDDDMMMFFFGG'
REPLACED={2,4,10,11,14,18,23,26,27,28,29,31,34,36,50,52,53}
STYLE_OFFSETS=[0x1e94cc,0x224c50]

def csv_out(path,rows):
    if not rows: raise ValueError('No rows')
    with open(path,'w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)

def shared_style_risk(mapping, style, target):
    other=[slot for slot,graphic in mapping.items() if slot!=target and graphic==style]
    return sorted(other)

def inspect(disc,rosters,output):
    output.mkdir(parents=True,exist_ok=True)
    teams=list(csv.DictReader((ROOT/'results'/'team_identity_54.csv').open(encoding='utf-8',newline='')))
    if len(teams)!=54 or [int(t['slot']) for t in teams]!=list(range(54)):
        raise ValueError('Wrong team index table')
    roster_names=json.loads(rosters.read_text(encoding='utf-8'))
    if {int(x) for x in roster_names}!={*ROLE_STRINGS}:raise ValueError('Expected 15 national names')
    exe=disc.logical(EXE_LBA,0,EXE_SIZE,True)
    # Actual physical sector offset, NOT Form1 logical offset.
    old_tables=[];new_tables=[]
    for offset in STYLE_OFFSETS:
        sec=offset//2352;p=offset%2352
        old_tables.append(disc.sector(sec,False)[p:p+54]);new_tables.append(disc.sector(sec,True)[p:p+54])
    if not old_tables[0]==old_tables[1] or not new_tables[0]==new_tables[1]:
        raise ValueError('Team flag style banks disagree, cannot safely edit')
    original={s:int(old_tables[0][53-s]) for s in range(54)}
    current={s:int(new_tables[0][53-s]) for s in range(54)}
    groups=defaultdict(list)
    for slot,v in current.items():groups[v].append(slot)
    if current[23]!=7 or original[23]!=7:raise ValueError('Expected current Bosnia style 7')
    if current[34]!=24 or original[34]!=10:raise ValueError('Expected Slovakia -> DR Congo reassignment')
    if any(x==10 for x in current.values()):raise ValueError('Expected free native style #10')
    risk=shared_style_risk(current,7,23)
    if len(risk)!=6:raise ValueError('Style #7 sharing count changed')
    if risk!=[13,20,32,33,40,44]:raise ValueError('Unexpected Bosnia style7 sharing slots')
    all_styles=set(range(28));current_legacy=all_styles & set(current.values())
    empty_styles=sorted(all_styles-current_legacy)
    # Graphic style 10 free in the CURRENT actual country selection table; other unused style slots may exist.
    style_rows=[]
    for slot in range(54):
        team=teams[slot]['main_select_name'];s=current[slot];orig=original[slot]
        style_rows.append({'team_slot':slot,'team':team,'was_style':orig,'stage3_style':s,
          'style_is_shared':len(groups[s])>1,'other_sharers':','.join(teams[t]['main_select_name'] for t in groups[s] if t!=slot),
          'style_is_over_legacy_atlas_range':s>=28,'replacement':slot in REPLACED,
          'bosnia_style7_collision':slot==23 or (slot in risk)})
    csv_out(output/'national_style_ownership_54.csv',style_rows)
    review=[];mismatches=[]
    for slot,positions in sorted(ROLE_STRINGS.items()):
        names=roster_names[str(slot)];team=teams[slot]['main_select_name']
        if len(positions)!=22 or len(names)!=22:raise ValueError(f'Invalid 22 positions/names for {team}')
        for idx,(name,source_position,intended) in enumerate(zip(names,positions,INTENDED)):
            current_name=player_name(exe,roster_base(slot)+idx*10)
            if current_name!=name:raise ValueError(f'Stage3 name drift at {team} player {idx}: {current_name} vs {name}')
            row={'team_slot':slot,'team':team,'player_slot':idx+1,'player':name,
                 'source_2026_position':{'G':'GK','D':'DF','M':'MF','F':'FW'}[source_position],
                 'intended_game_role_template':{'G':'GK','D':'DF','M':'MF','F':'FW'}[intended],
                 'position_disagreement':source_position!=intended,
                 'needs_binary_position_mapping_before_patch':source_position!=intended}
            review.append(row)
            if source_position!=intended:mismatches.append(row)
    csv_out(output/'fifa2026_role_review_330.csv',review)
    csv_out(output/'nine_role_mismatches.csv',mismatches)
    if len(review)!=330 or len(mismatches)!=9:raise ValueError('Unexpected role count')
    if {m['team_slot'] for m in mismatches}!={2,4,10,31,36,50}:raise ValueError('Unexpected affected team groups')
    report={
      'stage':'4 – Bosnian flag style ownership and national player-role integration gate',
      'status':'READ ONLY STAGE4 AUDIT — safe release of flag/position writes not yet proven',
      'baseline_stage3_patch_sha256':STAGE3_SHA,
      'national_team_styles_checked':54,
      'bosnia':{'team_slot':23,'style_now':7,'shared_with_slot_ids':risk,
        'shared_with_team_names':[teams[i]['main_select_name'] for i in risk],
        'proven_free_original_style':10,'original_owner_of_style10':'SLOVAKIA (now DR CONGO)',
        'suggested_strategy':'Generate unique Bosnian flag artwork for free native style 10, update both style tables from 7 to 10, and synchronize every menu, prematch and GDC texture source; do not edit style 7 bitmap',
        'ready_to_apply':False},
      'other_currently_unused_native_styles':empty_styles,
      'active_extra_style_ids':sorted(set(current.values())-set(range(28))),
      'source_backed_2026_15team_roster_slots':len(ROLE_STRINGS),
      'source_backed_player_names_checked':len(review),
      'position_template_disagreements':len(mismatches),
      'position_disagreements_team_count':len({r['team_slot'] for r in mismatches}),
      'disagreement_by_team':{teams[s]['main_select_name']:sum(r['team_slot']==s for r in mismatches) for s in sorted({r['team_slot'] for r in mismatches})},
      'native_ps1_position_attribute_offsets_confirmed':False,
      'must_preserve':'Stage3 330 player names, Stage2 44 mixed-case labels, Test05 Canada flag, all original 39 other rosters and stable v0.9.4 data',
      'test_game_feed_updated':False,
      'warnings':['Do not alter shared style #7: it is used by six other national teams',
        'A free style ID alone is NOT an actual texture replacement: style 10 still requires correct Bosnia artwork in all active VRAM upload sources.',
        'The nine mismatches compare FIFA source positions to an INTENDED Stage3 ordering template; actual PS1 role flags have not been extracted. Do not blindly write role values.',
        'Old names on prematch screen may originate from non-ASCII encodings or secondary assets; not resolved by this style ownership audit.']}
    (output/'stage4_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report


def main(args):
    if hashlib.sha256(args.stage3.read_bytes()).hexdigest().upper()!=STAGE3_SHA:raise ValueError('Wrong Stage3 patch')
    disc=PatchedDisc(args.track,args.stage3,verify=not args.skip_track_sha)
    try:return inspect(disc,args.rosters,args.output)
    finally:disc.close()

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--track',type=Path,required=True)
    a.add_argument('--stage3',type=Path,required=True)
    a.add_argument('--rosters',type=Path,default=ROOT/'stage3_game_rosters_15.json')
    a.add_argument('--output',type=Path,default=ROOT/'stage4_results')
    a.add_argument('--skip-track-sha',action='store_true')
    print(json.dumps(main(a.parse_args()),indent=2,ensure_ascii=False))
