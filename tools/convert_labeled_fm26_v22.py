#!/usr/bin/env python3
"""Read-only, fail-closed ISS26 0.9.6 candidate conversion from labeled FM26 community data.

The raw v22 archive contains 74 unlabelled numeric columns. Only its FIRST 36
values are mapped, because these correspond in order to NAMED attributes in
vfxper/fm26's 2600-player CSV (community snapshot). The final 38 must NEVER
be interpreted as named goalkeeper attributes or written to the game.

This module does not change BIN/CUE, nationality ID, player refs or release feeds.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,math,unicodedata,re
from pathlib import Path
from collections import Counter,defaultdict

RAW_SHA='FF2B5D5783C490A5F2165F22AFC8409FDFBE7C9450E2FE5C613B04EE7A71E749'
V20_SHA='2A4CC0C568F23B4FF66BD91CC271031EF7AF8005607E7E63E652B98251D6D745'
SOURCE='https://github.com/vfxper/fm26/blob/main/2600%E7%90%83%E5%91%98%E5%B1%9E%E6%80%A7.csv'
KEYS=(
 'corners','crossing','dribbling','finishing','first_touch','free_kicks',
 'heading','long_shots','long_throws','marking','passing','penalty',
 'tackling','technique','aggression','anticipation','bravery','composure',
 'concentration','decisions','determination','flair','leadership',
 'off_the_ball','positioning','teamwork','vision','work_rate',
 'acceleration','agility','balance','jumping','stamina','pace','endurance','strength')
assert len(KEYS)==36

# Adapted from ISS26-Updates/tools/iss26_fm26_import.py. Weights and
# 1..20 -> 12..19 mapping are game-design choices, not published by SI/Konami.
OUTFIELD={
 'offense':(('off_the_ball',.55),('anticipation',.25),('finishing',.20)),
 'defense':(('positioning',.4),('marking',.3),('tackling',.3)),
 'body_balance':(('balance',.6),('strength',.4)),
 'stamina':(('stamina',.75),('natural_fitness',.25)),
 'speed':(('pace',1.),), 'acceleration':(('acceleration',1.),),
 'response':(('anticipation',.5),('decisions',.25),('concentration',.25)),
 'jump_power':(('jumping',1.),), 'head_accuracy':(('heading',1.),),
 'technique':(('first_touch',.55),('technique',.45)),
 'pass_accuracy':(('passing',.65),('vision',.25),('crossing',.1)),
 'shot_power':(('strength',.4),('long_shots',.4),('finishing',.2)),
 'shot_accuracy':(('finishing',.65),('composure',.20),('long_shots',.15)),
 'dribble':(('dribbling',1.),),
 'curve':(('free_kicks',.45),('crossing',.35),('corners',.2)),
}
GOALKEEPER=dict(OUTFIELD,**{
 'offense':(('off_the_ball',.5),('anticipation',.5)),
 'defense':(('one_on_ones',.5),('command_of_area',.3),('positioning',.2)),
 'response':(('reflexes',.7),('anticipation',.3)),
 'technique':(('handling',.55),('first_touch',.45)),
 'pass_accuracy':(('kicking',.55),('passing',.45)),
 'jump_power':(('aerial_reach',.6),('jumping',.4)),
})
SKILLS=tuple(OUTFIELD)
assert len(SKILLS)==15
ISS_RECORD_HEX='000260B6ECD1E6A459B7A903' # DEV18 Riznyk historical
BITFIELDS={
 'curve':(85,3),'jump_power':(82,3),'head_accuracy':(79,3),'technique':(76,3),
 'pass_accuracy':(73,3),'shot_accuracy':(70,3),'shot_power':(67,3),
 'defense':(64,3),'offense':(61,3),'acceleration':(58,3),
 'speed':(55,3),'dribble':(52,3),'stamina':(49,3),
 'body_balance':(46,3),'response':(42,4),
}
assert set(BITFIELDS)==set(SKILLS)
CORRECTION=('offense','defense','dribble','shot_accuracy','curve','jump_power')
GK_MEDIAN_FALLBACK={'defense':17,'jump_power':17} # historical original 124-GK cohort

def sha256(data:bytes)->str:return hashlib.sha256(data).hexdigest().upper()
def norm(s:str)->str:
 return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())

def labeled(row:dict)->dict[str,int]:
 values=row['raw_attributes_7_84'].split(';')
 if len(values)!=74:raise ValueError('Unsupported raw attribute count')
 output={}
 for i,k in enumerate(KEYS):
  val=values[i]
  if not val.isdecimal() or not 1<=int(val)<=20:
   raise ValueError(f'Invalid named 1..20 source attribute {k}: {val!r}')
  output[k]=int(val)
 return output

def iss_from_fm(value:float)->int:
 return min(19,max(12,12+math.floor((value-1)*7/19+0.5)))

def convert(attrs:dict[str,int],is_gk:bool)->dict[str,dict]:
 specs=GOALKEEPER if is_gk else OUTFIELD
 result={}
 for skill,spec in specs.items():
  known=[(attrs[name],weight) for name,weight in spec if name in attrs]
  weight=sum(w for _,w in known)
  # exact values only for full weights; partial indicated and explicitly
  # requires approval. GK named stats are deliberately not guessed.
  if weight<.5-1e-9:
   result[skill]={'value':None,'evidence':'MISSING_GOALKEEPER_FIELD' if is_gk else 'MISSING_SOURCE_FIELD',
                  'covered_weight':round(weight,4)}
  else:
   avg=sum(v*w for v,w in known)/weight
   result[skill]={'value':iss_from_fm(avg),
      'evidence':'COMPLETE_NAMED_SOURCE' if weight>=1-1e-9 else 'PARTIAL_NAMED_SOURCE',
      'covered_weight':round(weight,4)}
 return result

def native_profile(existing:bytes,converted:dict)->tuple[bytes,dict]:
 if existing.hex().upper()!=ISS_RECORD_HEX:raise ValueError('Unknown Riznyk native record')
 base=int.from_bytes(existing,'little')
 before=base
 provenance={}
 for name in CORRECTION:
  data=converted[name]
  if data['evidence']=='COMPLETE_NAMED_SOURCE':
   target=data['value']; origin='NAMED_COMMUNITY_FM_SNAPSHOT'
  elif name in GK_MEDIAN_FALLBACK:
   target=GK_MEDIAN_FALLBACK[name];origin='ORIGINAL_2001_GK_MEDIAN_NOT_PLAYER_SPECIFIC'
  else:raise ValueError(f'Unverified GK skill {name} has no safe fallback')
  shift,width=BITFIELDS[name]
  if not 12<=target<=12+(1<<width)-1:raise ValueError('ISS field overflow')
  mask=((1<<width)-1)<<shift
  old=12+((before>>shift)&((1<<width)-1))
  provenance[name]={'dev18':old,'candidate':target,'evidence':origin}
  base=(base&~mask)|((target-12)<<shift)
 after=base.to_bytes(12,'little')
 allmask=sum(((1<<BITFIELDS[k][1])-1)<<BITFIELDS[k][0] for k in CORRECTION)
 if ((int.from_bytes(after,'little')^before)&~allmask):raise ValueError('Non-approved game bit changed')
 if (int.from_bytes(after,'little')&15)!=0:raise ValueError('Goalkeeper position changed')
 if ((int.from_bytes(after,'little')>>20)&63)!=38:raise ValueError('Height 186 lost')
 return after,provenance

def run(raw:Path,v20:Path,out:Path,report:Path)->dict:
 if out.exists() or report.exists():raise FileExistsError('Never overwrite candidate data')
 if sha256(raw.read_bytes())!=RAW_SHA or sha256(v20.read_bytes())!=V20_SHA:
  raise ValueError('Input version SHA mismatch')
 with raw.open(newline='',encoding='utf-8-sig') as f: source=list(csv.DictReader(f))
 with v20.open(newline='',encoding='utf-8-sig') as f: previous=list(csv.DictReader(f))
 if len(source)!=1707 or len(previous)!=1716:raise ValueError('Input row counts changed')
 byuid={x['uid']:x for x in source}
 if len(byuid)!=1707 or any(not x['uid'].isdigit() for x in source):
  raise ValueError('Nonunique or missing FM UID')
 records=[];status=Counter(); pos=Counter()
 for row in source:
  is_gk=row['position'].strip()=='GK'
  values=convert(labeled(row),is_gk)
  item={'uid':row['uid'],'name':row['name'],'position':row['position'].strip(),
        'community_ca_candidate':row['ca'],'source_dob':row['dob'],
        'source_height_cm':row['height'],'source_nationality_candidate':row['nationality'],
        'source_club_snapshot':row['club'],'is_goalkeeper':is_gk,
        'not_a_current_2026_roster_verification':True}
  for name,value in values.items():
   item['iss_'+name]=value['value']
   item['source_'+name]=value['evidence']
   status[value['evidence']]+=1
  records.append(item)
  pos['GK' if is_gk else 'OUTFIELD']+=1
 rz=[x for x in source if x['uid']=='71100666' and x['name']=='Dmytro Riznyk']
 if len(rz)!=1 or rz[0]['dob']!='1999/1/30' or rz[0]['club']!='Shakhtar Donetsk' or rz[0]['nationality']!='Ukraine':
  raise ValueError('Riznyk UID/name/DOB/team/nationality disagree')
 rizstats=convert(labeled(rz[0]),True)
 candidate,changes=native_profile(bytes.fromhex(ISS_RECORD_HEX),rizstats)
 uidjoins=[(x,byuid[x['uid']]) for x in previous if x['uid'] in byuid]
 exactnames=sum(norm(a['player_name'])==norm(b['name']) for a,b in uidjoins)
 if len(uidjoins)!=1625 or exactnames!=1462:raise ValueError('Unexpected v20/v22 identity overlap')
 if sum(1 for x in records if x['is_goalkeeper'])!=189:raise ValueError('GK count changed')
 cols=list(records[0]);out.parent.mkdir(parents=True,exist_ok=True)
 with out.open('x',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=cols);writer.writeheader();writer.writerows(records)
 data={
  'schema':1,'status':'SOURCE_FM26_V22_NAMED_36_OF_74_ONLY_NOT_GAME_PATCH',
  'source':SOURCE,'source_kind':'community_FM26_snapshot_NOT_official_game_export',
  'raw_source_sha256':RAW_SHA,'source_v20_sha256':V20_SHA,
  'players':len(records),'goalkeepers':pos['GK'],'outfield':pos['OUTFIELD'],
  'named_field_count':len(KEYS),'unlabeled_field_count_forbidden':74-len(KEYS),
  'field_evidence_counts':dict(status),
  'v20_team_memberships_with_UID_join':len(uidjoins),
  'v20_UID_and_exact_name_joins':exactnames,
  'v20_UID_matches_requiring_individual_name_review':len(uidjoins)-exactnames,
  'rz_uid':'71100666','rz_unchanged_dev18_native_hex':ISS_RECORD_HEX,
  'rz_source_values':{k:v for k,v in rizstats.items()},
  'rz_six_skill_candidate_hex':candidate.hex().upper(),
  'rz_six_skill_changes':changes,
  'riznyk_height_discrepancy_cm':{'source_snapshot':int(rz[0]['height']),'pinned_game_dev18':186},
  'actual_game_carrier_checked':False,'native_citizenship_fixed':False,
  'source_snapshot_is_not_current_2026_2027_club_roster':True,
  'source_candidates_not_approved_for_game':True,'game_release_ready':False,
 }
 report.parent.mkdir(parents=True,exist_ok=True)
 report.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return data

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--raw-v22',type=Path,required=True)
 p.add_argument('--v20',type=Path,required=True)
 p.add_argument('--out',type=Path,required=True)
 p.add_argument('--report',type=Path,required=True)
 a=p.parse_args();res=run(a.raw_v22,a.v20,a.out,a.report)
 print(json.dumps({k:v for k,v in res.items() if k not in ('rz_source_values','rz_six_skill_changes')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
