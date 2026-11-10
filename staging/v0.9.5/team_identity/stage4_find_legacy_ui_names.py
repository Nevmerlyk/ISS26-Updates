#!/usr/bin/env python3
"""Read-only literal-ASCII scan of PS1 data files for legacy team names.

This does NOT decode compressed/encoded pre-match glyphs, CD-DA, TIMs or save states.
A hit is a candidate, not automatically a safe replacement pointer.
"""
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path
from team_identity_audit import PatchedDisc
ROOT=Path(__file__).resolve().parent

def inventory(path):
    out=[]
    for line in path.read_text().splitlines():
        m=re.match(r'\s*(\d+)\s+(\d+)\s+(/\S+)',line)
        if m:
            lba,length,name=int(m[1]),int(m[2]),m[3]
            if name.endswith(';1') and (name.endswith('.BIN;1') or name.endswith('.21;1')) and length<1_000_000:
                out.append((lba,length,name))
    return out

def scan(disc,entries,terms,old):
    hits=[]
    for lba,length,path in entries:
        data=disc.logical(lba,0,length,not old)
        for slot,search in terms:
            patt=re.compile(rb'(?<![A-Za-z])'+re.escape(search.encode('ascii'))+rb'(?![A-Za-z])',re.IGNORECASE)
            for match in patt.finditer(data):
                at=match.start()
                hits.append({'team_slot':slot,'legacy_term':search,'phase':'original' if old else 'stage3',
                    'file':path,'logical_offset':at,
                    'observed':data[at:match.end()].decode('ascii'),
                    'context_ascii':re.sub(r'[^\x20-\x7e]','. ',data[max(0,at-20):match.end()+20].decode('latin1')).strip()})
    return hits

def main(args):
    output=args.output;output.mkdir(exist_ok=True,parents=True)
    orig=list(csv.DictReader((ROOT/'replacements_v094.csv').open(newline='',encoding='utf-8')))
    terms=[]
    for v in orig:
        slot=int(v['slot'])
        if v['from_select'].upper() in ('RUSSIA','GREECE','JAMAICA','CHINA','SLOVENIA','YUGOSLAVIA'):
            terms.append((slot,v['from_select'].strip()))
    entries=inventory(args.inventory)
    disc=PatchedDisc(args.track,args.stage3,verify=not args.skip_track_sha)
    try:
        hits=scan(disc,entries,terms,True)+scan(disc,entries,terms,False)
    finally:disc.close()
    filename=output/'literal_legacy_team_names.csv'
    with filename.open('w',encoding='utf-8',newline='') as f:
        cols=['team_slot','legacy_term','phase','file','logical_offset','observed','context_ascii']
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(hits)
    report={'files_scanned':len(entries),'terms_searched':[x[1] for x in terms],
      'literal_ASCII_original_hits':sum(x['phase']=='original' for x in hits),
      'literal_ASCII_stage3_hits':sum(x['phase']=='stage3' for x in hits),
      'stage3_hits':[x for x in hits if x['phase']=='stage3'],
      'warning':'Compressed graphics/name banks, non-ASCII name encoding and runtime memory not covered. Missing ASCII hits DO NOT prove no legacy names appear on screen.'}
    (output/'literal_names_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--track',type=Path,required=True)
    p.add_argument('--stage3',type=Path,required=True)
    p.add_argument('--inventory',type=Path,default=ROOT/'iso_inventory.txt')
    p.add_argument('--output',type=Path,default=ROOT/'stage4_results')
    p.add_argument('--skip-track-sha',action='store_true')
    print(json.dumps(main(p.parse_args()),indent=2,ensure_ascii=False))
