#!/usr/bin/env python3
"""Read-only audit of the real EU PS1 ISO + official v0.9.4 independent patch.

This scanner DOES NOT change the game, does not depend on unverified graphics
styles, and does not claim that a text mnemonic is an editable game ID.
"""
from pathlib import Path
import argparse, csv, json, hashlib, re, struct

BASE_SHA = 'D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44'
BASE_SIZE = 496156752

def parse_patch(path):
    blob=Path(path).read_bytes()
    if blob[:8]!=b'ISS26X01': raise ValueError('Not ISS26 independent XOR patch')
    n,=struct.unpack_from('<I',blob,8)
    if len(blob)!=12+2388*n or not 0<n<=8192: raise ValueError('Invalid patch length/count')
    last=-1;records={}
    for i in range(n):
        off=12+i*2388;lba,=struct.unpack_from('<I',blob,off)
        if not last<lba<BASE_SIZE//2352:raise ValueError('Unsorted/duplicate sectors')
        records[lba]=(blob[off+4:off+36],blob[off+36:off+2388])
        last=lba
    return records

REGIONS={
    'SELECT': {'lba':850,'size':233864,'from':3444,'to':3968},
    'SELECT3':{'lba':1250,'size':184264,'from':10140,'to':10648},
    'SELECTC':{'lba':1950,'size':83180,'from':24340,'to':24860},
}
CODE_BANK={'lba':1950,'size':83180,'from':25068,'stride':4}
# Verified actual 3-character abbreviations, not a promise of the game's internal ID semantics.
NEW_CODE={2:'QAT',4:'UZB',10:'PAN',11:'ECU',14:'CAN',18:'SEN',23:'BIH',26:'NZL',27:'IRQ',28:'JOR',29:'CUW',31:'HAI',34:'COD',36:'GHA',50:'CIV',52:'ALG',53:'CPV'}
ALIAS={'S.AFRICA':'SOUTH AFRICA','N.ZEAL':'N.ZEAL','DR CONGO':'DR CONGO','I.COAST':'I.COAST','CZECHO':'CZECH'}

def canon(s):
    s=re.sub(r'\s+',' ',s).strip().upper()
    return ALIAS.get(s,s)

def parse_entries(buf,lo,hi):
    out=[]
    for m in re.finditer(rb'[A-Za-z][A-Za-z0-9. /\-]*',buf[lo:hi]):
        name=m.group().decode('ascii').strip()
        if name:out.append((lo+m.start(),name))
    return out

def write_csv(path,rows,headers):
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction='ignore');w.writeheader();w.writerows(rows)

class PatchedDisc:
    def __init__(self,track,patch,verify=True):
        self.track=Path(track);self.records=parse_patch(Path(patch))
        if self.track.stat().st_size != BASE_SIZE: raise ValueError('Wrong clean Track01 length')
        if verify:
            with self.track.open('rb') as f: original_sha=hashlib.file_digest(f,'sha256').hexdigest().upper()
            if original_sha!=BASE_SHA:raise ValueError('Wrong clean Track01 digest')
        self.f=self.track.open('rb')
    def close(self):self.f.close()
    def sector(self,lba,modified):
        self.f.seek(lba*2352);raw=self.f.read(2352)
        if len(raw)!=2352:raise ValueError(f'Short sector {lba}')
        if modified and lba in self.records:
            guard,mask=self.records[lba]
            if hashlib.sha256(raw).digest()!=guard:raise ValueError(f'Patch guard failed at LBA {lba}')
            raw=bytes(a^b for a,b in zip(raw,mask))
        return raw
    def logical(self,lba,offset,size,modified=True):
        ans=bytearray()
        while size:
            sec=lba+offset//2048;start=offset%2048;n=min(size,2048-start)
            ans+=self.sector(sec,modified)[24+start:24+start+n]
            size-=n;offset+=n
        return bytes(ans)
    def resource(self,meta,modified=True):
        return self.logical(meta['lba'],0,meta['size'],modified)


def main(args):
    root=Path(args.out);root.mkdir(parents=True,exist_ok=True)
    disc=PatchedDisc(args.track,args.baseline,verify=not args.skip_track_sha)
    try:
        resources={n:disc.resource(reg) for n,reg in REGIONS.items()}
        rows={n:parse_entries(resources[n],reg['from'],reg['to']) for n,reg in REGIONS.items()}
        if {n:len(a) for n,a in rows.items()} != {n:54 for n in REGIONS}:
            raise ValueError('Team name bank lost exact 54-entry alignment: '+str({n:len(a) for n,a in rows.items()}))
        with (Path(__file__).parent/'replacements_v094.csv').open(encoding='utf-8') as f:
            changes={int(x['slot']):x for x in csv.DictReader(f)}
        assert len(changes)==17
        codes=disc.logical(CODE_BANK['lba'],CODE_BANK['from'],54*4)
        records=[];issues=[];edits=[]
        for idx in range(54):
            entry={n:rows[n][idx][1] for n in REGIONS}
            offsets={n:rows[n][idx][0] for n in REGIONS}
            code=codes[idx*4:idx*4+4].rstrip(b'\0').decode('ascii')
            replacement=idx in changes
            master=canon(entry['SELECT'])
            problem=[]
            for n in ('SELECT3','SELECTC'):
                if canon(entry[n])!=master:
                    problem.append(f'{n}_MISMATCH')
                    issues.append({'slot':idx,'source':n,'offset':offsets[n],'expected':entry['SELECT'],'observed':entry[n], 'category':'team_name_mismatch','confidence':'confirmed table divergence'})
            if replacement:
                desired=NEW_CODE[idx]
                if code != desired:
                    problem.append('OLD_CODE')
                    issues.append({'slot':idx,'source':'SELECTC_CODE','offset':CODE_BANK['from']+4*idx,'expected':desired,'observed':code,'category':'stale_3letter_code','confidence':'confirmed stale text; usage not verified'})
            else:desired=code
            records.append({'slot':idx,'small_flag_sprite':idx+5,'main_select_name':entry['SELECT'],'select3_name':entry['SELECT3'],'master_league_name':entry['SELECTC'],'selectc_code':code,'expected_code_if_text':desired,'replacement':replacement,'replaced_from':changes[idx]['from_select'] if replacement else '', 'name_status':' | '.join(problem) or 'MATCH', 'select_offset':offsets['SELECT'],'select3_offset':offsets['SELECT3'],'selectc_offset':offsets['SELECTC'], 'selectc_code_offset':CODE_BANK['from']+4*idx})
        # Candidates are generated as SAFE PRECONDITIONED TEXT proposals only; do not apply until
        # known whether SELECTC codes serve UI alone or internal addressing.
        for i,x in enumerate(records):
            if x['main_select_name']=='QATAR' and x['select3_name']=='U.A.E.':
                off=x['select3_offset'];old=resources['SELECT3'][off:off+8]
                assert old==b'U.A.E.\x00\x00',repr(old)
                edits.append({'file':'SELECT3.BIN','offset':off,'expected_hex':old.hex(),'replacement_hex':b'Qatar\x00\x00\x00'.hex(),'purpose':'Correct stale QATAR label, candidate for static text replacement','publish':False})
        # Fixed ten-byte name records: confirmed binary table, but club/team ownership unknown.
        sel=resources['SELECT'];original=disc.resource(REGIONS['SELECT'],modified=False)
        candidates=[];player_total=0
        for slot,off in enumerate(range(4928,8338,10)):
            raw=sel[off:off+10];chunk=raw.split(b'\x00',1)[0]
            if not chunk or not re.fullmatch(rb'[A-Za-z][A-Za-z .\-\']{1,9}',chunk):
                continue
            player_total+=1
            if chunk.isupper() and len(chunk)>=3:
                before=original[off:off+10].split(b'\x00',1)[0]
                candidates.append({'file':'SELECT.BIN','name_slot':slot,'offset':off,'observed_name':chunk.decode('ascii'), 'original_disc_name':before.decode('ascii','replace'),'present_in_original':before==chunk,'team_linkage':'UNKNOWN: DO NOT AUTO-PATCH','proposed_style':'human-verified mixed case, preserve abbreviations and particles'})
        write_csv(root/'team_identity_54.csv',records,list(records[0]))
        write_csv(root/'team_name_issues.csv',issues,list(issues[0]))
        write_csv(root/'uppercase_player_candidates.csv',candidates,list(candidates[0]))
        (root/'name_edit_candidates.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        report={
            'scope':'READ ONLY AUDIT, no patched game files created or published',
            'baseline_patch_sha256':hashlib.sha256(Path(args.baseline).read_bytes()).hexdigest().upper(),
            'national_teams':len(records),'changed_teams_from_v094':len(changes),
            'team_name_disagreements':sum('MISMATCH' in x['name_status'] for x in records),
            'stale_3letter_codes':sum('OLD_CODE' in x['name_status'] for x in records),
            'uppercase_candidates_in_select_fixed_name_table':len(candidates),
            'fixed_name_slots_scanned':player_total,
            'all_upper_candidates_existing_in_unmodified_original':sum(x['present_in_original'] for x in candidates),
            'candidate_text_edits':len(edits),
            'warnings':[
                'SELECTC 3-letter codes may be referenced by internal lookup mechanisms: do not blindly replace them.',
                'The 10-byte name bank in SELECT.BIN cannot yet be assigned to a particular national roster. All-uppercase detection is NOT proof of the reported national team issue.',
                'Do not title-case all text: country names, acronyms and personal compound names have different rules.',
                'The runtime test feed remains on Test05; no stability promotion and no new game patch were performed.'
            ]}
        (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return report
    finally:disc.close()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--track',required=True,help='Clean European Track01 bin');a.add_argument('--baseline',required=True,help='Verified official v0.9.4 ISS26 independent patch');a.add_argument('--out',default='results');a.add_argument('--skip-track-sha',action='store_true')
    print(json.dumps(main(a.parse_args()),ensure_ascii=False,indent=2))