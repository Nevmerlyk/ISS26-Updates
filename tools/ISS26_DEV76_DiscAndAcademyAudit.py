#!/usr/bin/env python3
"""ISS26 DEV76: read-only source-CUE SHA, Academy ZIP and SELECT style audit."""
import argparse,collections,datetime,hashlib,json,os,pathlib,re,struct,subprocess,sys,zipfile
P=pathlib.Path
KNOWN={
"D9B483BDEA7774346DF437FEBF038E68CB2C4AD9932A7AD993D3C2B1F620EA44":"Clean EU original",
"C265019267C11DBBB60FA32E369FE5DA9E1759403D860E5F11824FD69AB0518C":"0.9.6-alt Test",
"729B08C380D50C96F3402A8229CE49BD2EBD1E6712F2705ECFA6287BBC61D5DD":"DEV73",
"8E5EEDCF2442AAA98894C3D38260D46A717CF36491A27B96A7A183E0ED2EBBA9":"DEV74",
"B89F848CCE7FB761EB7ED8A3F9BF26DC159E5248C185AC114BCF864555BAFD8E":"DEV75"}
def sha(path):
 h=hashlib.sha256()
 with open(path,"rb") as f:
  for b in iter(lambda:f.read(4<<20),b""):h.update(b)
 return h.hexdigest().upper()
def clip(v):
 s=str(v)
 if "/" in s or "\\" in s:s=re.split(r"[/\\]",s)[-1]
 return s[:140]
def vals(obj,p=""):
 if isinstance(obj,dict):
  for k,v in obj.items():yield from vals(v,(p+"."+k)[-140:])
 elif isinstance(obj,list):
  for v in obj[:50]:yield from vals(v,p)
 elif isinstance(obj,(str,int,float,bool)):yield p,obj
def report_zip(path):
 with zipfile.ZipFile(path) as z:
  names=z.namelist()
  out={"archive":path.name,"entries":len(names),"bad_crc":z.testzip(),
       "types":dict(collections.Counter(P(n).suffix.lower() for n in names))}
  sessions=[]
  cue_paths=[]
  for name in names:
   if P(name).name.lower() not in ("session.json","disc-ram-crosscheck.json","manifest.json","source.json"):continue
   i=z.getinfo(name)
   if i.file_size>2000000:continue
   try:j=json.loads(z.read(name).decode("utf-8-sig"))
   except Exception:continue
   for k,v in vals(j):
    if isinstance(v,str) and v.lower().endswith(".cue"):
     cue_paths.append(v)
   fields=[{"name":k,"value":clip(v)} for k,v in vals(j)
           if re.search("patch|cue|bin|image|sha|disc|source|version",k,re.I)]
   sessions.append({"name":clip(name),"fields":fields[:50]})
  out["sessions"]=sessions[:15]
  out["_runtime_cues"]=cue_paths[:30]
  vram_tiles=[]
  coords={"Italy_France_Belgium":(768,368),"Ukraine_Poland":(800,368),
          "Croatia":(812,368),"Turkey_Venezuela":(820,368),
          "Czech_style63":(828,422)}
  for vname in (n for n in names if n.lower().endswith(".vram")):
   if len(vram_tiles)>=80:break
   info=z.getinfo(vname)
   if info.file_size!=2097152:continue
   vr=z.read(vname)
   tags={}
   for k,(x,y) in coords.items():
    tile=b"".join(vr[2*(1024*yy+x):2*(1024*yy+x+4)]
                  for yy in range(y,y+18))
    tags[k]=hashlib.sha256(tile).hexdigest()[:16]
   vram_tiles.append({"file":clip(vname),"tile_4bpp_digest":tags})
  out["vram_loaded_texture_fingerprints"]=vram_tiles
  screens=[n for n in names if n.endswith(".screen.raw")]
  out["screen_raw_count"]=len(screens)
  out["vram_count"]=sum(n.endswith(".vram") for n in names)
  crops=[]
  for name in screens[:120]:
   if z.getinfo(name).file_size!=384*480*2:continue
   b=z.read(name)
   flag=b"".join(b[(y*384+226)*2:(y*384+242)*2] for y in range(69,85))
   crops.append(hashlib.sha256(flag).hexdigest()[:16])
  out["selected_flag_crops"]=len(crops)
  out["distinct_flag_crops"]=len(set(crops))
  out["flag_crop_digests"]=sorted(set(crops))[:40]
  return out
def cue_track(path):
 try:s=path.read_text("utf-8-sig",errors="replace")
 except OSError:return None
 m=re.search(r'(?im)^\s*FILE\s+(?:"([^"]+)"|(\S+))\s+BINARY',s)
 if not m:return None
 track=P(m.group(1) or m.group(2))
 if not track.is_absolute():track=path.parent/track
 return track
def choose_cues(session):
 cues=[]
 if session:
  for v in session.get("_runtime_cues",[]):
   if P(v).is_file():cues.append(P(v))
 roots=[P(r"D:\ISS 26\ISS26_Data\experiments"),P.home()/"Downloads"]
 for root in roots:
  if not root.is_dir():continue
  for pat in ("DEV75*/*.cue","DEV74*/*.cue","*DEV75*.cue","*DEV74*.cue"):
   cues.extend(root.glob(pat))
 return list(dict.fromkeys(p for p in cues if p.is_file()))[:12]
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--zip");ap.add_argument("--cue");ap.add_argument("--post-issue",action="store_true")
 a=ap.parse_args()
 report={"schema":"ISS26_DEV76_PROVENANCE_V1",
         "date_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
 archive=P(a.zip) if a.zip else None
 if archive is None:
  for folder in (P.home()/"Downloads",P(r"D:\ISS 26"),P(os.environ.get("TEMP","."))):
   p=folder/"20261122_212600_569c5f.zip"
   if p.is_file():archive=p;break
 if archive and archive.is_file():
  try:report["academy"]=report_zip(archive)
  except Exception as e:report["academy_error"]=str(e)[:180]
 else:report["academy_error"]="Exact session archive not present on PC."
 candidates=([P(a.cue)] if a.cue else choose_cues(report.get("academy")))
 hashes={}
 discs=[]
 for cue in candidates:
  track=cue_track(cue)
  item={"cue":cue.name,"track":track.name if track else "unresolved"}
  if track and track.is_file() and track.stat().st_size==496156752:
   resolved=str(track.resolve())
   if resolved not in hashes:hashes[resolved]=sha(track)
   item["track01_sha256"]=hashes[resolved]
   item["label"]=KNOWN.get(hashes[resolved],"UNKNOWN image, do not assume DEV75")
   # The 82-byte style lookup lives at SELECT.BIN logical 0x10F4,
   # which maps to raw LBA 852 offset +0xF4 in this exact EU layout.
   with track.open("rb") as f:
    f.seek(852*2352+24+0xF4)
    styles=f.read(82)
   if len(styles)==82:
    item["select_style12_czech"]=styles[12]
    item["select_style28_turkey"]=styles[28]
    item["select_style29_ukraine"]=styles[29]
    item["dev75_lookup_bytes_match"]=(styles[12]==63 and styles[28]==15)
  discs.append(item)
 report["discs"]=discs
 if report.get("academy"):
  report["academy"].pop("_runtime_cues",None)
 report["verdict"]=("An exact DEV75 Track01 is present among inspected CUE files. "
                   "This does not prove it was the GUI-mounted image."
                   if any(x.get("label")=="DEV75" for x in discs)
                   else "No proven exact DEV75 disc among inspected CUE files.")
 output=P(os.environ.get("LOCALAPPDATA",str(P.home())))/"ISS26"/"diagnostics"/"DEV76-disc-runtime.json"
 output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
 print("ISS26 DEV76 report",output)
 for x in discs:print(x)
 if a.post_issue:
  try:
   payload={"body":"[DEV76 sanitized CUE/Academy provenance report]\n"+json.dumps(report,indent=2,ensure_ascii=False)[:55000]}
   proc=subprocess.run(["gh","api","-X","POST",
     "repos/Nevmerlyk/ISS26-Android/issues/91/comments","--input","-"],
     input=json.dumps(payload),text=True,capture_output=True,timeout=45)
   print("GitHub issue report:", "sent" if proc.returncode==0 else "not sent (gh auth or connectivity)")
  except Exception as e:print("GitHub report unavailable:",type(e).__name__)
 return 0
if __name__=="__main__":sys.exit(main())
