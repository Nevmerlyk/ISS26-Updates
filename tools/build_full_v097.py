#!/usr/bin/env python3
"""ISS26 roster test. Exact EU disc, 54 national + 24 club rosters.
All candidate records sourced from v20/v21; inferred bio/ratings explicitly tracked.
"""
import csv,collections,hashlib,json,struct,unicodedata,re,statistics,sys,argparse
from pathlib import Path
from scipy.optimize import linear_sum_assignment
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from integration_merge_eu import parse_patch,merge,fix_form1,BASE_SHA
cli=argparse.ArgumentParser(description=__doc__)
cli.add_argument('--track',type=Path,required=True)
cli.add_argument('--carrier',type=Path,required=True)
cli.add_argument('--out',type=Path,required=True)
a=cli.parse_args();TRACK=a.track;BASE=a.carrier;OUT=a.out;OUT.mkdir(parents=True,exist_ok=True)
S=2352
BASE_PATCH='5ec84c0c6b31f503decd9ff2ad37b40a65efef3cf5cd593a1a98992368326d11'
BASE_RESULT='7C503B7F214C7414F7B41C01553DB1F06387EEC290835164CAB00505EE7B9DAE'
ATTR={'curve':(85,3),'jump_power':(82,3),'head_accuracy':(79,3),'technique':(76,3),'pass_accuracy':(73,3),'shot_accuracy':(70,3),'shot_power':(67,3),'defense':(64,3),'offense':(61,3),'acceleration':(58,3),'speed':(55,3),'dribble':(52,3),'stamina':(49,3),'body_balance':(46,3),'response':(42,4)}
POS={'GK':0,'CB':1,'FB':2,'DM':3,'CM':3,'AM':5,'WG':7,'ST':6}
FAMILY={0:'GK',1:'DF',2:'DF',3:'MF',4:'MF',5:'MF',6:'FW',7:'FW'}
NA=164052; EA=179364; NN=293204; EN=4928; R=8620; OFF=8340 # overridden by 0x2094
OFF=0x2094

def sha(x):return hashlib.sha256(x).hexdigest()
def tab(p):return list(csv.DictReader((ROOT/p).open(encoding='utf-8-sig',newline='')))
def norm(s):return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower())
def label(n,used):
 n=unicodedata.normalize('NFKD',n.translate(str.maketrans({'ł':'l','Ł':'L','ø':'o','Ø':'O','ß':'ss','Đ':'D','đ':'d'}))).encode('ascii','ignore').decode()
 n=re.sub("[^A-Za-z .'-]",'',n).strip();a=n.split();last=a[-1];candidates=[n,last,a[0][0]+'.'+last,last[:10],a[0][0]+'.'+last[:8],n[:10],a[0][:10]]+[last[:8]+'.'+chr(i) for i in range(65,91)]
 for x in candidates:
  if re.fullmatch("[A-Za-z][A-Za-z .'-]{0,9}",x) and x.lower() not in used:used.add(x.lower());return x
 raise ValueError('No label '+n)
def role(raw):
 if raw in POS:return POS[raw]
 t=raw.upper()
 if t.startswith('GK'):return 0
 if t.startswith(('D/WB','D L','D R','DL','DR','WB')) and not t.startswith(('D LC','D RC','D RLC','D RL')):return 2
 if t.startswith(('D ','DC','D/')):return 1 if 'C' in t.split('/')[0] else 2
 if t.startswith(('DM','MC','M C')):return 3
 if t.startswith(('ST','FW')):return 6
 if t.startswith(('AMR','AML','AM R','AM L','MR','ML','M R','M L')):return 7 if t.startswith('AM') else 4
 if t.startswith(('AMC','AM','M/AM')):return 5
 if t.startswith('M'):return 3
 raise ValueError('Unclassified position '+raw)
def setbits(k,shift,width,value):
 if not 0<=value<1<<width:raise ValueError('out of range')
 return (k&~(((1<<width)-1)<<shift))|(value<<shift)
def encode(old,row,p):
 k=int.from_bytes(old,'little');k=setbits(k,0,4,p)
 for a,(s,w) in ATTR.items():k=setbits(k,s,w,int(row['game_iss_'+a])-12)
 k=setbits(k,37,5,max(0,min(31,int(row['game_age'])-15)))
 k=setbits(k,20,6,max(0,min(63,int(row['game_height_cm'])-150)))
 feet={'R':0,'L':1,'B':2,'BOTH':2}.get(row['game_foot'].upper());assert feet is not None,row['game_foot'];k=setbits(k,94,2,feet)
 return k.to_bytes(12,'little')
def verify_stats(b,row,p):
 k=int.from_bytes(b,'little');assert k&15==p
 for a,(s,w) in ATTR.items():assert ((k>>s)&((1<<w)-1))+12==int(row['game_iss_'+a]),(row['player_name'],a)
 assert ((k>>37)&31)+15==max(15,min(46,int(row['game_age'])))
 assert ((k>>20)&63)+150==max(150,min(213,int(row['game_height_cm'])))
 assert k>>94=={'R':0,'L':1,'B':2,'BOTH':2}[row['game_foot'].upper()]
def read_resource(track,records,lba,n):
 out=bytearray()
 with track.open('rb') as f:
  for i in range(lba,lba+(n+2047)//2048):
   f.seek(i*S);r=f.read(S)
   if i in records:
    h,x=records[i];assert hashlib.sha256(r).digest()==h;r=bytes(a^b for a,b in zip(r,x))
   assert r[15]==2 and not r[18]&32 and r[16:20]==r[20:24]
   out+=r[24:2072]
 return bytes(out[:n])
def names_at(b,o):return b[o:o+10].split(b'\0')[0].decode('ascii')
def putname(b,o,n):b[o:o+10]=n.encode('ascii').ljust(10,b'\0')
assert sha(BASE.read_bytes())==BASE_PATCH
recs=parse_patch(BASE)
exe=read_resource(TRACK,recs,24,339968);sel=read_resource(TRACK,recs,850,233864)
orig=read_resource(TRACK,{},850,233864);origexe=read_resource(TRACK,{},24,339968)
# Confirm exact active MIPS addresses and original layout; detect baseline drift.
assert orig[0xe634:0xe648].hex()=='0c1624900880013c210825000d16229000220400'
assert orig[0xe08c:0xe094].hex()=='0a80033c34756324'
assert orig[0xe2ac:0xe2b4].hex()=='0b80033c04b16324'
assert orig[R:R+1056]==sel[R:R+1056]
base_offsets=struct.unpack_from('<118H',orig,OFF)
refs=[tuple(orig[i:i+2]) for i in range(R,R+1056,2)]
assert len(set(refs))==528
idx=lambda h,l:base_offsets[h]+l-22
extras={x:idx(*x) for x in refs if x[0]>=54 or x[1]>=22}
assert len(extras)==315 and len(set(extras.values()))==315 and all(0<=i<341 for i in extras.values())
assert names_at(origexe,NN)=='Alan Kelly' and names_at(origexe,NN+(53*22)*10)=='Bosnich'
assert [names_at(origexe,NN+(22*h+l)*10) for h,l in refs[:11] if h<54 and l<22]==['Bosnich','Stam','Irwin','G.Neville','Roy Keane','Geags','Beckham','Scholes']
# Use source identity keys and slot IDs; exact normalized full-name fallback gated by GK compatibility.
pool=tab('data/fm26/ISS26_complete_working_pool_v20.csv'); all_by_uid=collections.defaultdict(list); all_by_name=collections.defaultdict(list)
for x in pool:
 if x['uid']:all_by_uid[x['uid']].append(x)
 all_by_name[norm(x['player_name'])].append(x)
plan=tab('data/integration/national_name_test1_v096.csv'); clubs=tab('data/integration/active_club_roster_candidates_v21.csv'); supp=tab('data/integration/club_roster_supplement_v21.csv');suppmap={(x['team_id'],x['game_slot']):x for x in supp}
peers=collections.defaultdict(list)
for x in pool:
 if x['game_attribute_estimated_count']=='0':peers[role(x['game_position'])].append(x)
source_by_team_slot=collections.defaultdict(list)
for x in pool:source_by_team_slot[(x['team_id'],x['source_slot'])].append(x)
working_exe=bytearray(exe);working_sel=bytearray(sel); nat_by_uid=collections.defaultdict(list);nat_by_name=collections.defaultdict(list); audit=[]; nat_data={}; estimates=0
for r in plan:
 p=[x for x in source_by_team_slot[(r['team_id'],r['source_slot'])] if x['player_name']==r['player_name']]
 if len(p)!=1:raise ValueError(('national source',r,p))
 p=p[0];nidx=(int(r['exe_offset'])-NN)//10;assert nidx in range(1188)
 pos=role(p['game_position']);f=r['template_role'];
 if FAMILY[pos]!=f:pos={'GK':0,'DF':1,'MF':5,'FW':6}[f]
 name=r['game_label'];assert names_at(exe,NN+nidx*10)==name
 old=sel[NA+nidx*12:NA+nidx*12+12];working_sel[NA+nidx*12:NA+nidx*12+12]=encode(old,p,pos)
 nat_data[(nidx//22,nidx%22)]=(p,pos,name)
 if p['uid']:nat_by_uid[p['uid']].append((nidx//22,nidx%22))
 nat_by_name[norm(p['player_name'])].append((nidx//22,nidx%22))
 estimates+=int(p['game_attribute_estimated_count'])
 audit.append(dict(team_id=r['team_id'],slot=int(r['game_slot']),player_name=p['player_name'],label=name,ref=f'{nidx//22:02x}{nidx%22:02x}',record_type='NATIONAL',position=pos,attribute_status=p['game_attribute_status'],estimated_attributes=int(p['game_attribute_estimated_count']),bio_status=p['game_bio_estimated_fields']))
assert len(nat_data)==1188

def candidates_identity(row,p0,lookup_uid,lookup_name,get):
 uid=row.get('uid','');p=role(p0);xs=lookup_uid.get(uid,[]) if uid else []
 xs=[x for x in xs if (role(get(x)['game_position'])==0)==(p==0)]
 if len(xs)==1:return xs[0],'UID'
 if len(xs)>1:return None,'AMBIGUOUS_UID'
 xs=lookup_name.get(norm(row['player_name']),[])
 xs=[x for x in xs if (role(get(x)['game_position'])==0)==(p==0) and (not uid or not get(x).get('uid') or uid==get(x)['uid'])]
 if len(xs)==1:return xs[0],'EXACT_NAME_AND_GK_GATE'
 return None,'NO_UNIQUE_MATCH'

def fallback(row):
 p=role(row['source_position']);uid=row.get('uid','');a=all_by_uid.get(uid,[]) if uid else all_by_name.get(norm(row['player_name']),[])
 a=[x for x in a if (role(x['game_position'])==0)==(p==0) and (not uid or not x['uid'] or uid==x['uid'])]
 if a and len({x['uid'] for x in a if x['uid']})<=1:
  x=dict(min(a,key=lambda x:int(x['game_attribute_estimated_count'])));x['player_name']=row['player_name'];return x,'REUSED_IDENTITY_CANDIDATE'
 age=int(suppmap[(row['team_id'],row['source_slot'])]['fm_snapshot_age'])+1
 pp=peers[p] or peers[5];sample=sorted(pp,key=lambda x:abs(int(x['game_age'])-age))[:30]
 x={'player_name':row['player_name'],'game_age':str(age),'game_height_cm':str(round(statistics.median(int(y['game_height_cm']) for y in sample))),'game_foot':'R','game_attribute_status':'ESTIMATED_NOT_FM26','game_attribute_estimated_count':'15','game_bio_estimated_fields':'age;height;foot;weight','game_position':next(k for k,v in POS.items() if v==p) if p in POS.values() else 'WG'}
 for a in ATTR:x['game_iss_'+a]=str(round(statistics.median(int(y['game_iss_'+a]) for y in sample)))
 return x,'ROLE_MEDIAN_ESTIMATE'

club_data=[];seen_national=set();conflicts=[];identity_method=collections.Counter();roster_index=json.load((ROOT/'data/integration/active_club_registry_v21.json').open())['menu_order'];assert len(roster_index)==24
for t in roster_index:
 team=t['team_id'];tid=23-t['ordinal'];rows=[r for r in clubs if r['team_id']==team];assert len(rows)==22
 data=[]
 for r in rows:
  source=[x for x in source_by_team_slot[(r['team_id'],r['source_slot'])] if x['player_name']==r['player_name']]
  if len(source)==1:p=source[0];method='V20_CLUB'
  elif t['has_v20']:raise ValueError(('club source',r))
  else:p,method=fallback(r)
  pos=role(r['source_position']) if not t['has_v20'] else role(p['game_position'])
  match,m=candidates_identity(r,r['source_position'],nat_by_uid,nat_by_name,lambda x:nat_data[x][0]);
  if match is not None:
   if match in seen_national:conflicts.append((r['player_name'],team,match));match=None;m='CONFLICT_SEPARATE_RECORD'
   else:seen_national.add(match);p,npos,nlabel=nat_data[match];pos=npos
  identity_method[m]+=1
  data.append(dict(row=r,source=p,match=match,pos=pos,method=method,identity_method=m,team=team,tid=tid))
 # Keep goalkeeper in slot 1, then match original formation roles as nearly as feasible.
 oldpos=[]
 for h,l in refs[tid*22:tid*22+22]:oldpos.append(orig[NA+12*(h*22+l)]&15 if h<54 and l<22 else orig[EA+12*idx(h,l)]&15)
 cost=[]
 for i,x in enumerate(data):
  cost.append([(0 if x['pos']==q else 8 if FAMILY[x['pos']]==FAMILY[q] else 30 if q and x['pos'] else 500)+(20000 if j==0 and x['pos']!=0 else 0)+(20000 if 0<j<11 and x['pos']==0 else 0)+abs(i-j)*0.04 for j,q in enumerate(oldpos)])
 ri,ci=linear_sum_assignment(cost);ordered=[None]*22
 for i,j in zip(ri,ci):ordered[j]=data[i]
 assert ordered[0]['pos']==0 and all(x['pos']!=0 for x in ordered[1:11]) and sum(x['pos']==0 for x in ordered)>=2,team
 for i,x in enumerate(ordered):x['slot']=i;club_data.append(x)
assert len(club_data)==528
unshared=[x for x in club_data if x['match'] is None];assert len(unshared)<=315,('capacity',len(unshared))
# Bind extra candidates to 315 distinct previously active refs. Keep old team/ref and role where feasible.
eref=list(extras);oldowner={r:j//22 for j,r in enumerate(refs)};cost=[]
for x in unshared:
 cost.append([(0 if oldowner[r]==x['tid'] else 25)+(0 if orig[EA+12*extras[r]]&15==x['pos'] else 4 if FAMILY[orig[EA+12*extras[r]]&15]==FAMILY[x['pos']] else 12) for r in eref])
ri,ci=linear_sum_assignment(cost)
for i,j in zip(ri,ci):unshared[i]['match']=eref[j];unshared[i]['extra']=True
clubs_est=0;club_est_players=0;share_count=0;extra_indices=set();reserve_used=collections.defaultdict(set)
for x in club_data:
 if not x.get('extra'):reserve_used[x['team']].add(nat_data[x['match']][2].lower())
for x in club_data:
 h,l=x['match'];p=x['source'];pos=x['pos'];r=x['row'];i=x['slot'];tid=x['tid'];working_sel[R+44*tid+2*i:R+44*tid+2*i+2]=bytes((h,l))
 if x.get('extra'):
  j=extras[(h,l)];assert j not in extra_indices;extra_indices.add(j);name=label(r['player_name'],reserve_used[x['team']]);putname(working_sel,EN+j*10,name)
  off=EA+j*12;working_sel[off:off+12]=encode(sel[off:off+12],p,pos)
  clubs_est+=int(p['game_attribute_estimated_count']);club_est_players+=int(p['game_attribute_estimated_count'])>0;kind='CLUB_EXTRA'
 else:
  name=nat_data[(h,l)][2];share_count+=1;kind='SHARED_NATIONAL'
 audit.append(dict(team_id=x['team'],slot=i+1,player_name=r['player_name'],label=name,ref=f'{h:02x}{l:02x}',record_type=kind,position=pos,attribute_status=p['game_attribute_status'],estimated_attributes=int(p['game_attribute_estimated_count']),bio_status=p['game_bio_estimated_fields']))
 x['label']=name
 assert (h,l) not in [(z['match']) for z in club_data if z is not x] # 528 unique references
# Exact readback, including bonus and untouched data. No weight/appearance writes.
assert working_exe[NN+1188*10:NN+1276*10]==exe[NN+1188*10:NN+1276*10]
assert working_sel[NA+1188*12:EA]==sel[NA+1188*12:EA]
for ref,(p,pos,name) in nat_data.items():h,l=ref;i=h*22+l;assert names_at(working_exe,NN+10*i)==name;verify_stats(working_sel[NA+12*i:NA+12*i+12],p,pos)
for x in club_data:
 h,l=x['match'];assert working_sel[R+44*x['tid']+2*x['slot']:R+44*x['tid']+2*x['slot']+2]==bytes((h,l));p=x['source'];pos=x['pos']
 if x.get('extra'):j=extras[(h,l)];assert names_at(working_sel,EN+10*j)==x['label'];verify_stats(working_sel[EA+12*j:EA+12*j+12],p,pos)
 else:verify_stats(working_sel[NA+12*(h*22+l):NA+12*(h*22+l)+12],p,pos)
assert len(audit)==1716
# Use original standalone patch as carrier; replace only changed allowed SELECT logical ranges, rederive EDC/ECC.
allowed=set(range(R,R+1056))|set(range(NA,NA+1188*12))
for j in extra_indices:allowed.update(range(EN+10*j,EN+10*j+10));allowed.update(range(EA+12*j,EA+12*j+12))
assert all(i in allowed for i,(a,b) in enumerate(zip(sel,working_sel)) if a!=b)
edits=[];i=0
while i<len(sel):
 if sel[i]==working_sel[i]:i+=1;continue
 start=i;i+=1
 while i<len(sel) and sel[i]!=working_sel[i] and i//2048==start//2048:i+=1
 edits.append({'raw_offset':(850+start//2048)*S+24+start%2048,'expected_hex':sel[start:i].hex(),'replacement_hex':working_sel[start:i].hex()})
(OUT/'edits.json').write_text(json.dumps(edits))
patch=OUT/'ISS26_Test_0.9.7.iss26p'
info=merge(TRACK,BASE,OUT/'edits.json',patch,BASE_RESULT)
newrec=parse_patch(patch);assert read_resource(TRACK,newrec,850,len(sel))==working_sel;assert read_resource(TRACK,newrec,24,len(exe))==exe
with (OUT/'roster_readback.csv').open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(audit[0]));w.writeheader();w.writerows(audit)
report=dict(status='STATIC_READBACK_VERIFIED_RUNTIME_PENDING',version='0.9.7',national_teams=54,club_teams=24,national_slots=1188,club_slots=528,shared_national_club_records=share_count,extra_club_records=len(extra_indices),unique_modern_records=1188+len(extra_indices),preserved_bonus=88,attributes_written=15*(1188+len(extra_indices)),estimated_national_cells=estimates,estimated_extra_club_cells=clubs_est,estimated_extra_club_players=club_est_players,identity_methods=dict(identity_method),identity_conflicts=conflicts,source_candidate_membership_not_officially_verified=True,unsupported_fields=['weight','appearance customization','club-only nationality retained from assigned native ID'],method='Static MIPS-derived 12-byte codec, corroborated historical anchor players; runtime editor and matches required',patch=info)
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
