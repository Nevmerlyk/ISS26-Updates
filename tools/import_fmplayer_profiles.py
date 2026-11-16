#!/usr/bin/env python3
"""FMPlayer public FM26 profile -> ISS26 candidate import. Python 3.10+.
Offline by default. Live mode requires explicit permission and respects robots.
No changes to original roster, game, or primary attributes.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, re, time, urllib.request, urllib.error
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
from iss26_fm26_import import OUTFIELD, GOALKEEPER, ISS_ATTRIBUTES, iss_scale, normalized_name

HOST = "fmplayer.net"
AGENT = "ISS26ProfileImporter/1.0"
URL_RE = re.compile(r"/fm-26/[^/]+-(\d+)$")
LABELS = {a:a.replace("_"," ") for mapping in (OUTFIELD, GOALKEEPER)
          for terms in mapping.values() for a,w in terms}
LABELS.update({a:a.replace("_"," ") for a in (
    "aggression agility bravery determination flair leadership teamwork work_rate "
    "long_throws penalty_taking communication eccentricity punching_tendency "
    "rushing_out_tendency throwing adaptability ambition consistency controversy "
    "dirtiness important_matches injury_proneness loyalty pressure professionalism "
    "sportsmanship temperament versatility").split()})
LABELS["one_on_ones"] = "one on ones"
EXTRA_LABELS = {"one_on_ones": ("one on one", "one vs one", "one-on-ones", "one on ones", "1v1"),
                "versatility": ("versality", "versatility"),
                "aerial_reach": ("aerial reach", "aerial ability")}
LIMIT = 4_000_000

def checked_url(url):
    p=urlsplit(url)
    m=URL_RE.fullmatch(p.path)
    if p.scheme!="https" or p.netloc!=HOST or p.query or p.fragment or not m:
        raise ValueError("expected a public FM26 profile URL")
    return m.group(1)

class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts=[]; self.skip=[]
    def handle_starttag(self, tag, attrs):
        if tag in ("script","style","noscript","template"):
            self.skip.append(tag)
        if tag in ("h1","h2","h3","h4","h5","li","div","p","tr","br","td","th","section"):
            self.parts.append("\n")
    def handle_endtag(self,tag):
        if self.skip and tag==self.skip[-1]:
            self.skip.pop()
        if tag in ("h1","h2","h3","h4","h5","li","div","p","tr","td","th","section"):
            self.parts.append("\n")
    def handle_data(self,data):
        if not self.skip:
            self.parts.append(data+" ")
    def text(self):
        return "".join(self.parts)

def plain_text(body):
    if re.search(r"<(?:html|body|div|h1)\b",body,re.I):
        p=PageText(); p.feed(body); return p.text()
    return body

def clean(value):
    return re.sub(r"\s+"," ",value).strip()

def field(text,label,pattern):
    matches=re.findall(r"(?im)^\s*(?:[-*]\s*)?"+re.escape(label)+r"\s*:?\s*(?:\n\s*)?("+pattern+r")\s*$",text)
    values={clean(x) for x in matches}
    return next(iter(values)) if len(values)==1 else ""

def parse_profile(body,url):
    uid=checked_url(url)
    text=plain_text(body)
    m=re.search(r"(?im)^\s*#*\s*([^\n]+?)\s+FM26 Profile\s*$",text)
    if not m: raise ValueError("FM26 profile heading missing")
    if not re.search(r"scaled\s+from\s+1\s*[-–]\s*20\s+to\s+10\s*[-–]\s*200",text,re.I):
        raise ValueError("explicit FMPlayer scale declaration missing")
    name=clean(m.group(1))
    raw={}
    for key,label in LABELS.items():
        variants=EXTRA_LABELS.get(key,(label,))
        matches=set()
        for variant in variants:
            hits=re.findall(r"(?im)^\s*(?:[-*]\s*)?"+re.escape(variant)+r"\s*:?\s*(?:\n\s*)?(\d{1,3})\s*$",text)
            matches.update(map(int,hits))
        # 0/unknown, conflicting repeated values, and non-multiples of ten stay blank.
        if len(matches)==1:
            v=next(iter(matches))
            if 10<=v<=200 and v%10==0: raw[key]=v//10
    if not raw: raise ValueError("no unambiguous 1–20 attributes")
    pos=""
    heading=re.search(r"(?im)^\s*##\s+"+re.escape(name)+r"\s*$",text)
    # HTML headings lose Markdown marker; search the lines between profile title and CA.
    segment=text[heading.end() if heading else m.end():]
    ca=re.search(r"(?im)^\s*Current Ability\b",segment)
    if ca:
        for line in segment[:ca.start()].splitlines():
            line=clean(line)
            if re.fullmatch(r"(?:GK|SW|D[CLR]|WB[LR]|DM|M[CLR]|AM[CLR]|ST)(?:\s*,\s*(?:GK|SW|D[CLR]|WB[LR]|DM|M[CLR]|AM[CLR]|ST))*",line):
                pos=line
    # Profile fields are independent of scale: foot 1–20, CA/PA 0–200.
    meta={k:field(text,label,pattern) for k,label,pattern in (
        ("nationality","Nationality",r"[A-Z]{3}"),
        ("height_cm","Height",r"\d{3}(?:\s*cm)?"),
        ("weight_kg","Weight",r"\d{2,3}(?:\s*kg)?"),
        ("left_foot","Left Foot",r"\d{1,2}"),
        ("right_foot","Right Foot",r"\d{1,2}"),
        ("preferred_foot","Preferred Foot",r"Right|Left|Either|Both"),
        ("age_snapshot","Age",r"\d{1,2}(?:\s*y/o)?"),
        ("ca","Current Ability",r"\d{1,3}"),
        ("pa","Potential Ability",r"\d{1,3}"),
        ("club","Club",r"[^\n]+"))}
    return {"name":name,"uid":uid,"position":pos,"raw":raw,**meta}

def converted(profile,position):
    mapping=GOALKEEPER if position=="GK" else OUTFIELD
    raw=profile["raw"]
    return {k:iss_scale(sum(raw[a]*w for a,w in terms))
            if all(a in raw for a,w in terms) else ""
            for k,terms in mapping.items()}

def identity(row, entry, profile):
    if entry.get("expected_uid")!=profile["uid"]:
        return "uid_mismatch"
    if row.get("fm_uid_candidate") and row["fm_uid_candidate"]!=profile["uid"]:
        return "roster_uid_conflict"
    if normalized_name(profile["name"]) not in {
            normalized_name(row.get("player_name") or row.get("roster_name")),
            normalized_name(entry.get("expected_name",""))}:
        return "name_conflict"
    if not entry.get("expected_nationality"):
        return "missing_expected_nationality"
    if profile["nationality"].upper()!=entry["expected_nationality"].upper():
        return "nationality_conflict_or_missing"
    expected_gk=row.get("position_group")=="GK"
    if not profile["position"] or (("GK" in profile["position"].split(", "))!=expected_gk):
        return "position_conflict_or_missing"
    # FMPlayer profile does not necessarily contain DOB; no verified claim.
    return "candidate_uid_name_nationality_position_no_dob"

def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path,rows,fields):
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader();w.writerows(rows)
    tmp.replace(path)

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        checked_url(newurl)
        if checked_url(req.full_url)!=checked_url(newurl):
            raise ValueError("redirect changes player UID")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_text(url,opener):
    req=urllib.request.Request(url,headers={"User-Agent":AGENT,"Accept":"text/html,text/plain"})
    with opener.open(req,timeout=25) as res:
        b=res.read(LIMIT+1)
        if len(b)>LIMIT: raise ValueError("response too large")
        return b.decode(res.headers.get_content_charset() or "utf-8")

def load_robots():
    # No request to profiles if robots cannot be fetched or parsed.
    opener=urllib.request.build_opener(SafeRedirect())
    body=fetch_text("https://fmplayer.net/robots.txt",opener)
    if not re.search(r"(?im)^\s*user-agent\s*:",body):
        raise ValueError("robots.txt missing or invalid; live mode blocked")
    rp=RobotFileParser();rp.parse(body.splitlines())
    return rp,opener

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roster",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--cache",type=Path,required=True)
    p.add_argument("--live",action="store_true")
    p.add_argument("--permission-confirmed",action="store_true",
                   help="confirm site permits this requested automated access")
    p.add_argument("--limit",type=int,default=20)
    p.add_argument("--delay",type=float,default=5)
    args=p.parse_args()
    if args.live and not args.permission_confirmed:
        p.error("live mode requires confirmed permission")
    if args.limit<1 or args.delay<5: p.error("limit must be positive, delay >=5s")
    roster=read_csv(args.roster)
    entries=read_csv(args.manifest)
    key=lambda r:(r["team_id"],r["shirt_number"])
    if len(set(map(key,roster)))!=len(roster):p.error("duplicate roster key")
    if len(set(map(key,entries)))!=len(entries):p.error("duplicate manifest key")
    by_key={key(r):r for r in roster}
    args.cache.mkdir(parents=True,exist_ok=True); args.out.mkdir(parents=True,exist_ok=True)
    # Offline files are UID.txt or UID.html, supplied by authorized user/source.
    robots=opener=None
    if args.live: robots,opener=load_robots()
    results=[]; rejected=[]; network_count=0
    raw_fields=sorted(LABELS)
    meta_fields=["team_id","shirt_number","player_name","source_name","source_uid","source_url",
        "source_body_sha256","processed_at","identity_status","nationality","position","height_cm",
        "weight_kg","left_foot","right_foot","preferred_foot","age_snapshot","ca","pa","club"]
    fields=meta_fields+["fm26_"+k for k in raw_fields]+list(ISS_ATTRIBUTES)+["converted_count"]
    for entry in entries:
        r=by_key.get(key(entry));url=entry.get("source_url","")
        try:
            if r is None: raise ValueError("manifest row not in roster")
            uid=checked_url(url)
            if uid!=entry.get("expected_uid"): raise ValueError("URL/manifest UID mismatch")
            cache=args.cache/(uid+".txt");html=args.cache/(uid+".html")
            if cache.exists():body=cache.read_text(encoding="utf-8")
            elif html.exists():body=html.read_text(encoding="utf-8")
            elif args.live and network_count<args.limit:
                if not robots.can_fetch(AGENT,url):raise ValueError("robots disallows URL")
                if network_count:time.sleep(max(args.delay,robots.crawl_delay(AGENT) or robots.crawl_delay("*") or 0))
                network_count+=1
                body=fetch_text(url,opener)
                parse_profile(body,url) # don't cache block or error page
                cache.write_text(body,encoding="utf-8")
            else: raise ValueError("cache missing or live batch limit reached")
            pr=parse_profile(body,url); state=identity(r,entry,pr)
            if not state.startswith("candidate_"):raise ValueError(state)
            vals=converted(pr,r["position_group"])
            record={k:r.get(k,"") for k in ("team_id","shirt_number","player_name")}
            record.update(source_name=pr["name"],source_uid=pr["uid"],source_url=url,
                source_body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                processed_at=datetime.now(timezone.utc).isoformat(),identity_status=state)
            record.update({k:pr[k] for k in meta_fields if k in pr and k!="raw"})
            record.update({"fm26_"+k:pr["raw"].get(k,"") for k in raw_fields})
            record.update(vals);record["converted_count"]=sum(bool(v) for v in vals.values())
            results.append(record)
        except urllib.error.HTTPError as exc:
            rejected.append({"team_id":entry["team_id"],"shirt_number":entry["shirt_number"],"reason":str(exc)})
            if exc.code in (401,403,429,503):break
        except (ValueError,OSError) as exc:
            rejected.append({"team_id":entry["team_id"],"shirt_number":entry["shirt_number"],"reason":str(exc)})
        # Results saved after each entry; rerun uses cached responses.
        write_csv(args.out/"fmplayer_candidates.csv",results,fields)
        write_csv(args.out/"fmplayer_rejected.csv",rejected,["team_id","shirt_number","reason"])
    write_csv(args.out/"fmplayer_candidates.csv",results,fields)
    write_csv(args.out/"fmplayer_rejected.csv",rejected,["team_id","shirt_number","reason"])
    report={"manifest_rows":len(entries),"processed":len(results)+len(rejected),
        "accepted_candidates":len(results),"complete_15":sum(r["converted_count"]==15 for r in results),
        "rejected":len(rejected),"network_requests":network_count,
        "status":"CANDIDATES_ONLY_NOT_RELEASE","source":"FMPlayer public secondary source"}
    (args.out/"fmplayer_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__":main()
