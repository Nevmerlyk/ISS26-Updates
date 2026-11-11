#!/usr/bin/env python3
"""Read-only 28-large-graphic-style runtime preflight for ISS26 Test10.

Diagnoses style IDs from two national-table copies in EU Track01 and maps each
in-range style to its 64x28 pixels in the PS1 GPU national flag atlas.
Does NOT edit, repack, or relabel any large flag pixels in the image.
"""
import json,csv,sys,collections,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from team_identity_audit import PatchedDisc
from stage15_tname_national_patch import NAMES
TRACK=Path('/mnt/data/ISS Pro Evolution 2 (Europe) (En,Fr,De) (Track 01).bin')
PATCH=ROOT/'stage15_results/ISS26_0.9.5_Stage15_NationalPrematchNames_CANDIDATE.iss26p'
OUT=ROOT/'stage16_results';OUT.mkdir(exist_ok=True)


def get_style(disc,raw):
 sec=disc.sector(raw//2352,True)
 return sec[raw%2352]


def main():
 d=PatchedDisc(TRACK,PATCH,verify=True)
 try:
  rows=[]
  teams={int(r['team_slot']):r['team'] for r in csv.DictReader((ROOT/'stage4_results/national_style_ownership_54.csv').open())}
  for slot in range(54):
   id1=get_style(d,0x1E94CC+(53-slot))
   id2=get_style(d,0x224C50+(53-slot))
   if id1!=id2:raise ValueError(f'Style ID duplicate mismatches for team {slot}')
   name=teams[slot]
   if slot in NAMES:name=NAMES[slot]
   rows.append({'slot':slot,'team':name,'style_id':id1,'valid_0_27':id1<28,
                'is_replaced':slot in NAMES,'x_word':832+16*(id1%4) if id1<28 else None,
                'y':256+32*(id1//4) if id1<28 else None,'width_pixels':64,'height_pixels':28})
  groups=collections.defaultdict(list)
  for r in rows:
   if r['valid_0_27']:groups[r['style_id']].append(r['team'])
  idx=[{'style':i,'vram_x_word':832+16*(i%4),'vram_y':256+32*(i//4),'width_pixels':64,'height_pixels':28,
        'owners':groups.get(i,[]),'owner_count':len(groups.get(i,[]))} for i in range(28)]
  if not 0<=len(groups)<=28:raise ValueError('Bad style keys')
  invalid=[r for r in rows if not r['valid_0_27']]
  assert all(x['is_replaced'] for x in invalid),'Non-replaced valid original style corrupted'
  assert rows[23]['style_id']==10,'Bosnia should occupy original style10 in Test10'
  report={'status':'READ-ONLY VERIFIED native style roster; big flag artwork not fixed',
          'patch_sha256':hashlib.sha256(PATCH.read_bytes()).hexdigest().upper(),
          'national_teams':len(rows),'native_style_count':28,
          'in_range_styles_used':len(groups),'out_of_range_team_count':len(invalid),
          'out_of_range_teams':[{'slot':r['slot'],'team':r['team'],'style':r['style_id']} for r in invalid],
          'bosnia_style':rows[23]['style_id'],
          'style_10_shared_with':groups[10],
          'both_native_selection_tables_byte_identical':True,
          'caveat':'A native style ID identifies an indexed 4bpp flag pattern, but its final rendered colors depend on a separate CLUT/UV. Reuse does not guarantee correct modern flags.',
          'styles':idx,'team_assignments':rows}
  (OUT/'stage16_large_flag_style_registry.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
  with (OUT/'team_graphic_style_54.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
  print(json.dumps({k:v for k,v in report.items() if k not in ['styles','team_assignments']},ensure_ascii=False,indent=2))
  return report
 finally:d.close()

if __name__=='__main__':main()