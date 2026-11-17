#!/usr/bin/env python3
"""Generate 20x16 4bpp candidate flag art and BGR555 palettes, NOT disc edits.
Uses the project's country registry and public SVG files pinned to a commit.
Separate palettes are previews: actual shared game CLUT routing must be proven.
"""
import argparse,io,json,hashlib,struct,urllib.request
from pathlib import Path
from PIL import Image
import cairosvg
ROOT=Path(__file__).resolve().parents[1]
SOURCE="https://raw.githubusercontent.com/lipis/flag-icons/ac7e0eb3259eb62aa6100c435607e2fe03896a97/flags/4x3/"
CODES=dict(x.split(":") for x in """AUS:au KSA:sa QAT:qa IRN:ir UZB:uz KOR:kr JPN:jp ARG:ar URU:uy PAR:py PAN:pa ECU:ec BRA:br COL:co CAN:ca MEX:mx USA:us RSA:za SEN:sn NGA:ng EGY:eg TUN:tn MAR:ma BIH:ba UKR:ua TUR:tr NZL:nz IRQ:iq JOR:jo CUW:cw CRO:hr HAI:ht HUN:hu AUT:at COD:cd POL:pl GHA:gh SWE:se NOR:no DEN:dk GER:de CZE:cz ITA:it SUI:ch NED:nl BEL:be FRA:fr ESP:es POR:pt ENG:gb-eng CIV:ci SCO:gb-sct ALG:dz CPV:cv""".split())
def sha(b):return hashlib.sha256(b).hexdigest().upper()
def encode(im):
    im=im.convert("RGB")
    if im.size!=(20,16):raise ValueError("bad dimensions")
    # 15 opaque indices, zero reserved for transparent. Opaque black uses
    # bit 15, not the all-zero word. Existing game CLUT not overwritten.
    q=im.quantize(colors=15,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    raw=list(q.getdata());src=q.getpalette()
    entries=[0]
    for i in range(15):
        r,g,b=src[i*3:i*3+3]
        v=((r*31+127)//255)|(((g*31+127)//255)<<5)|(((b*31+127)//255)<<10)
        entries.append(v if v else 0x8000)
    idx=[i+1 for i in raw]
    packed=bytes(idx[i]|(idx[i+1]<<4) for i in range(0,len(idx),2))
    palette=struct.pack("<16H",*entries)
    if len(packed)!=160 or len(palette)!=32 or any(x==0 for x in idx):raise ValueError("bad indexed output")
    if [v for u in packed for v in (u&15,u>>4)]!=idx:raise ValueError("round trip")
    rgb=[tuple(((entries[i]>>shift)&31)*255//31 for shift in (0,5,10)) for i in idx]
    preview=Image.new("RGB",(20,16));preview.putdata(rgb)
    return packed,palette,preview
def generate(out):
    data=ROOT/"data/integration"
    reg=json.loads(json.loads((data/"v096_revision_internal_bundle.json").read_text())["revision/citizenship_registry.json"])
    if set(CODES)!=set(reg["playable_country_id"]):raise ValueError("registry mismatch")
    extra={}
    for i in range(1,4):
        d=json.loads((data/f"v096_extra_country_flag_art_part{i}.json").read_text())
        for c,row in d["flags"].items():
            if c in extra:raise ValueError("duplicate SVG")
            extra[c]=row
    if set(extra)!=set(reg["extra_country_requirements"]):raise ValueError("extra SVG mismatch")
    out.mkdir(parents=True,exist_ok=True)
    flags={}
    for c in sorted(set(CODES)|set(extra)):
        if c in extra:
            row=extra[c];svg=row["svg"].encode();source="project retained lipis/flag-icons source "+row["blob"]
        else:
            url=SOURCE+CODES[c]+".svg"
            with urllib.request.urlopen(url,timeout=20) as f:svg=f.read(1_000_000)
            source=url
        if b"<!DOCTYPE" in svg.upper() or b"<!ENTITY" in svg.upper():raise ValueError("unsafe SVG")
        # High-resolution draw then resize for low resolution.
        png=cairosvg.svg2png(bytestring=svg,output_width=100,output_height=80)
        im=Image.open(io.BytesIO(png)).convert("RGBA")
        background=Image.new("RGBA",im.size,(255,255,255,255))
        background.alpha_composite(im)
        small=background.convert("RGB").resize((20,16),Image.Resampling.LANCZOS)
        packed,palette,preview=encode(small)
        (out/(c+".4bpp")).write_bytes(packed);(out/(c+".clut")).write_bytes(palette)
        preview.resize((160,128),Image.Resampling.NEAREST).save(out/(c+".png"))
        flags[c]={"source":source,"source_sha256":sha(svg),"bitmap_sha256":sha(packed),"palette_sha256":sha(palette),
              "candidate_country_id":reg["playable_country_id"].get(c,reg["known_existing_extra_codes"].get(c)),
              "playable":c in CODES}
    (out/"manifest.json").write_text(json.dumps({"status":"CANDIDATE_ART_NOT_IN_GAME","size":[20,16],"flags":flags,
      "notes":["4bpp little nibble first, per-icon candidate palette","Actual game routing and shared CLUT still need runtime evidence","No additional playable national teams"]},indent=2)+"\n")
    print("FLAG_ART",len(flags),"playable",len(CODES),"citizenship_only",len(extra))
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--out",type=Path,required=True);generate(p.parse_args().out)
