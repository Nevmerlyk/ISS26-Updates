#!/usr/bin/env python3
"""ISS26 v0.9.5 independent flags-only patch assembler.

Requires:
  * unmodified ISS Pro Evolution 2 (Europe) SLES-03321 Track01 BIN,
  * official v0.9.4 ISS26X01 base patch,
  * audited flags-only graphics plan (schema 1).

Writes only a new clean-original .iss26p and verification JSON. NEVER rewrites
the game image, changes 11 audio tracks, publishes Stable, or guesses a sprite
location when there is no verified plan.

Usage:
  python build_v095.py --original "Track 01.bin" --plan flag_edits.json
  python build_v095.py --original "Track 01.bin" --base-patch 0.9.4.iss26p \
    --plan flag_edits.json --output ISS26_0.9.5_flags_only.iss26p
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import urllib.request

SOURCE_DIR = Path(__file__).resolve().parent.parent / "flags_source"
sys.path.insert(0, str(SOURCE_DIR))
from wecodec import decode, encode, DecodeError
from independent_xor import (
    Disc, BASE_V094_SHA, BASE_RESULT_SHA, CLEAN_SHA, SECTOR, USER,
    DATA_OFFSET, parse_patch, sha256_path
)

OFFICIAL_BASE_URL = ("https://github.com/Nevmerlyk/ISS26-Updates/releases/"
                     "download/v0.9.4-preview/ISS26_0.9.4_preview.iss26p")
TARGET_COUNTRIES = {
    "qatar": (2, 51),
    "uzbekistan": (4, 49),
    "panama": (10, 43),
    "ecuador": (11, 42),
    "canada": (14, 39),
    "senegal": (18, 35),
    "bosnia": (23, 30),
    "new_zealand": (26, 27),
    "iraq": (27, 26),
    "jordan": (28, 25),
    "curacao": (29, 24),
    "haiti": (31, 22),
    "dr_congo": (34, 19),
    "ghana": (36, 17),
    "ivory_coast": (50, 3),
    "algeria": (52, 1),
    "cabo_verde": (53, 0),
}
STYLE_TABLES = {
    "OPENNING": 0x1D6F48,  # original game's spelling
    "SELECT_A": 0x1E94CC,
    "SELECT_B": 0x224C50,
    "SELFORM": 0x4AD4B8,
    "REPLAYS": 0x575864,
}
CLUT_FIRST = 0xBF3B38
ALLOWED_CONTEXTS = {
    "selection", "prematch", "stadium", "match_hud",
    "edit_mode", "master_league"
}
REQUIRED_CONTEXTS = {"selection", "prematch", "stadium",
                     "match_hud", "edit_mode"}
HEX_SHA = re.compile(r"^[0-9a-fA-F]{64}$")
STADIUM_NAME = re.compile(r"^BIN/GDC_[A-Z0-9]+\.BIN$")
PROTECTED_PALETTE_INDEX = {12, 18, 23, 29}
TRANSPARENCY_CORRUPTED_IN_V094 = {
    1, 2, 4, 18, 20, 23, 25, 26, 27, 28, 31, 40, 43, 44, 50, 52
}
MAX_EDIT_BYTES = 4_000_000

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def require_sha(text: str, title: str):
    if not isinstance(text, str) or not HEX_SHA.fullmatch(text):
        raise ValueError(f"Missing or invalid SHA256 for {title}")

def require_country_map(items: dict, title: str):
    if not isinstance(items, dict) or set(items) != set(TARGET_COUNTRIES):
        missing = set(TARGET_COUNTRIES) - set(items if isinstance(items, dict) else [])
        raise ValueError(f"{title}: all 17 national flags are required; missing {sorted(missing)}")

def advance_form1(start: int, offset: int) -> int:
    lba, inside = divmod(start, SECTOR)
    if not 24 <= inside < 2072 or offset < 0:
        raise ValueError("Invalid palette Form1 offset")
    position = inside - 24 + offset
    return (lba + position // USER) * SECTOR + 24 + (position % USER)

def national_clut_offset(reverse_nation_slot: int) -> int:
    if not 0 <= reverse_nation_slot < 54:
        raise ValueError("Country CLUT index outside 0..53")
    return advance_form1(CLUT_FIRST, reverse_nation_slot * 32)

def download_verified_baseline(destination: Path) -> bytes:
    print("Downloading the public official independent v0.9.4 patch (no game files)...")
    req = urllib.request.Request(OFFICIAL_BASE_URL,
                                 headers={"User-Agent":"ISS26-FlagBuilder-v095"})
    with urllib.request.urlopen(req, timeout=120) as response:
        blob = response.read(32*1024*1024 + 1)
    if len(blob) > 32*1024*1024 or sha(blob) != BASE_V094_SHA:
        raise ValueError("Official v0.9.4 patch was unavailable or failed SHA256")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_path(destination) != BASE_V094_SHA:
            raise ValueError("Existing baseline patch has wrong SHA, refusing overwrite")
    else:
        destination.write_bytes(blob)
    return blob

def _allowed_resource(path: str) -> bool:
    return (path in ("BIN/DATSEL.BIN", "BIN/DATSEL3.BIN",
                     "BIN/DATSEL2.BIN", "BIN/EDT_2D.BIN", "BIN/EDTR_2D.BIN")
            or bool(STADIUM_NAME.fullmatch(path)))

def _data_field(edit: dict, key: str) -> bytes:
    if not isinstance(edit.get(key), str):
        raise ValueError(f"Missing base64 payload: {key}")
    value=base64.b64decode(edit[key], validate=True)
    if not value or len(value)>MAX_EDIT_BYTES:
        raise ValueError("Missing or oversized decoded pixel payload")
    return value

def _rect(style: int) -> tuple[int,int,int,int]:
    if not 0 <= style <= 27:
        raise ValueError("Unverified national style ID (expected 0..27)")
    return ((832 + 16*(style % 4)) * 4,
            256 + 32*(style // 4), 64, 28)

def _pixel_delta_stays_within_flags(before: bytes, after: bytes,
                                   x: int,y: int, width_words: int,
                                   height: int,styles: list[int]) -> int:
    if len(before)!=len(after) or len(before)!=width_words*2*height:
        raise ValueError("GPU upload output byte count mismatch")
    if len(styles)==0 or len(styles)!=len(set(styles)):
        raise ValueError("Missing or duplicate approved national atlas style")
    allowed=tuple(_rect(a) for a in styles)
    changed=0
    stride=width_words*4
    for offset,(a,b) in enumerate(zip(before,after)):
        if a==b:continue
        for nibble in (0,1):
            if ((a>>(4*nibble))&15)==((b>>(4*nibble))&15):
                continue
            pixel=offset*2+nibble
            px=x*4+(pixel%stride)
            py=y+(pixel//stride)
            if not any(rx<=px<rx+rw and ry<=py<ry+rh
                       for rx,ry,rw,rh in allowed):
                raise ValueError("Compressed upload changes pixels OUTSIDE declared national flag tiles")
            changed+=1
    if changed==0:raise ValueError("Declared flag stream edit did not change any pixel")
    return changed

def validate_plan(plan: dict) -> None:
    if not isinstance(plan,dict) or plan.get("schema_version")!=1 or (
        plan.get("version")!="0.9.5" or plan.get("flags_only") is not True
    ):
        raise ValueError("Not an ISS26 v0.9.5 flags-only plan")
    if plan.get("base_patch_sha256")!=BASE_V094_SHA:
        raise ValueError("The plan does not target the official clean-original v0.9.4")
    require_country_map(plan.get("styles"),"style assignments")
    require_country_map(plan.get("palettes"),"palette assignments")
    if not isinstance(plan.get("streams"),list) or not plan["streams"]:
        raise ValueError("No verified flag sprite stream replacements supplied")
    for name,style in plan["styles"].items():
        if type(style) is not int or not 0 <= style < 28:
            raise ValueError(f"Invalid 0..27 national style {name}: {style}")
    for name,palette in plan["palettes"].items():
        if (not isinstance(palette,list) or len(palette)!=16 or
            any(type(x)!=int or not 0<=x<=0xFFFF for x in palette) or
            palette[0]!=0):
            raise ValueError("Each team's CLUT must have 16 BGR555 colors, index 0 transparent")
    for update in plan.get("preserved_palettes",[]):
        if update.get("index") not in PROTECTED_PALETTE_INDEX:
            raise ValueError("Attempt to modify an unrelated legacy nation's CLUT")
        if (not isinstance(update.get("palette"),list) or
            len(update["palette"])!=16 or update["palette"][0]!=0):
            raise ValueError("Invalid protected original flag CLUT")
        require_sha(update.get("render_before_sha256"),"protected legacy rendered bitmap")
        require_sha(update.get("render_after_sha256"),"protected legacy rendered bitmap")
        if update["render_before_sha256"].upper()!=update["render_after_sha256"].upper():
            raise ValueError("Protected unchanged nation's rendered pixels would change")
    if set(plan.get("confirmed_contexts",[])) != REQUIRED_CONTEXTS:
        raise ValueError("Missing evidence for selection, prematch, stadium, match HUD or Edit Mode")
    if not isinstance(plan.get("runtime_evidence"),str) or len(plan["runtime_evidence"])<12:
        raise ValueError("Missing actual emulator evidence ID/reference")

def patch_flag_stream(data: bytes, edit: dict) -> tuple[bytes,int]:
    """Repack a verified upload with pixel-diff bounds and preimage checks."""
    path=edit.get("resource")
    if not isinstance(path,str) or not _allowed_resource(path):
        raise ValueError("Attempt to edit non-national graphic resource")
    context=edit.get("context")
    if context not in ALLOWED_CONTEXTS:
        raise ValueError("Unrecognized graphics screen context")
    record=edit.get("record_offset")
    table_base=edit.get("load_base")
    allocated_end=edit.get("allocated_end")
    if any(type(v)is not int for v in (record,table_base,allocated_end)):
        raise ValueError("Missing GPU command provenance")
    if not 0<=record<=len(data)-16 or not 0<=allocated_end<=len(data):
        raise ValueError("GPU command offset outside file")
    op,x,y,w,h,flags,ptr=struct.unpack_from("<6HI",data,record)
    if op!=10 or not(0<w<=1024 and 0<h<=512 and x+w<=1024 and y+h<=512):
        raise ValueError("Not a valid PS1 LoadImage command")
    start=ptr-table_base
    if not 0<=start<allocated_end<=len(data) or start>=record:
        raise ValueError("Compressed data pointer or allocated end invalid")
    # No resource's graphics command table may be overwritten.
    if allocated_end>record and start<record:
        raise ValueError("Compressed replacement would overlap its command record")
    if not (0x80000000<=table_base<=0x80200000):
        raise ValueError("Untrusted PS1 load address")
    require_sha(edit.get("decoded_before_sha256"),"decoded upload input")
    require_sha(edit.get("decoded_after_sha256"),"decoded upload output")
    decoded,used,_=decode(data[start:allocated_end],w*2*h)
    if sha(decoded)!=edit["decoded_before_sha256"].upper():
        raise ValueError("Decoded graphics do not match audited preimage")
    after=_data_field(edit,"decoded_after_b64")
    if sha(after)!=edit["decoded_after_sha256"].upper():
        raise ValueError("New rendered flag data failed SHA256")
    styles=edit.get("styles")
    if not isinstance(styles,list) or any(type(x)is not int for x in styles):
        raise ValueError("Missing verified flag tile identities")
    changed=_pixel_delta_stays_within_flags(decoded,after,x,y,w,h,styles)
    encoded=encode(after)
    if len(encoded)>allocated_end-start:
        raise ValueError("Recompressed flags exceed pinned source allocation")
    if decode(encoded,len(after))[0]!=after:
        raise AssertionError("WE graphics encoder failed roundtrip")
    # Do not modify slack after compressed EOT; no pointer relocation.
    output=bytearray(data)
    output[start:start+len(encoded)] = encoded
    if decode(output[start:allocated_end],len(after))[0]!=after:
        raise AssertionError("Installed WE upload failed decode")
    # If this upload has a shorter new stream, unused bytes are preserved.
    return bytes(output),changed

def _tile_from_uploads(resource: bytes, edits: list[dict],
                       style: int) -> bytes:
    """Reconstruct the actual 64x28 pixels touched by audited GPU uploads.

    This operates on VERIFIED compressed LoadImage commands and their VRAM
    locations, not on a user-supplied screenshot checksum. Require every
    visible pixel to be covered by those commands.
    """
    rx,ry,rw,rh=_rect(style)
    indices=bytearray(rw*rh)
    covered=bytearray(rw*rh)
    for edit in sorted(edits,key=lambda e:e["record_offset"]):
        off,base,end=edit["record_offset"],edit["load_base"],edit["allocated_end"]
        op,x,y,w,h,flags,ptr=struct.unpack_from("<6HI",resource,off)
        if op!=10:raise ValueError("Protected team upload command changed")
        decoded,_,_=decode(resource[ptr-base:end],w*2*h)
        sx,sy=x*4,y
        ex,ey=sx+w*4,sy+h
        ix0,ix1=max(rx,sx),min(rx+rw,ex)
        iy0,iy1=max(ry,sy),min(ry+rh,ey)
        if ix0>=ix1 or iy0>=iy1:continue
        for vy in range(iy0,iy1):
            for vx in range(ix0,ix1):
                pixel=(vy-sy)*(w*4)+vx-sx
                byte=decoded[pixel//2]
                idx=(byte>>4) if pixel%2 else (byte&15)
                dest=(vy-ry)*rw+vx-rx
                indices[dest]=idx
                covered[dest]=1
    if not all(covered):
        raise ValueError(f"Cannot prove full preserved legacy style {style} atlas tile")
    return bytes(indices)

def _render_flag_pixels(indices: bytes, palette: list[int] | tuple[int,...]) -> bytes:
    if len(palette)!=16:raise ValueError("Invalid preserved palette length")
    # CLUT index 0 is transparency; transparent parts are normalized to 0
    # even if v0.9.4 incorrectly gave them an opaque color.
    return b"".join(struct.pack("<H",0 if i==0 else palette[i])
                    for i in indices)

def prove_unchanged_national_styles(disc: Disc, plan: dict,
                                    old_dat: bytes, new_dat: bytes,
                                    dat_edits: list[dict]) -> list[int]:
    """Check all 37 unaffected team styles and protected rendered pixels."""
    target_slots={slot for slot,_ in TARGET_COUNTRIES.values()}
    affected_styles={style for edit in plan["streams"] for style in edit["styles"]}
    changes={entry["index"]:entry["palette"]
             for entry in plan.get("preserved_palettes",[])}
    preserved=[]
    for text_slot in range(54):
        if text_slot in target_slots:continue
        nation_index=53-text_slot
        # All five tables must identify the same unaffected style as the
        # selection table; do not break a different pre-match lookup.
        current={key:disc.read_physical(address+text_slot,1)[0]
                 for key,address in STYLE_TABLES.items()}
        if len(set(current.values()))!=1:
            raise ValueError("Unchanged nation's five style tables disagree")
        style=next(iter(current.values()))
        if style not in affected_styles:
            if nation_index in changes:
                raise ValueError("Unrelated CLUT modified without a shared template")
            continue
        if nation_index not in PROTECTED_PALETTE_INDEX or nation_index not in changes:
            raise ValueError(
                f"Edited style {style} also used by unchanged nation {nation_index} "
                "without proved exact preservation")
        old_clut=list(struct.unpack("<16H",
            disc.read_form1_sequence(national_clut_offset(nation_index),32)))
        new_clut=changes[nation_index]
        old_pix=_tile_from_uploads(old_dat,dat_edits,style)
        new_pix=_tile_from_uploads(new_dat,dat_edits,style)
        previous=_render_flag_pixels(old_pix,old_clut)
        current_pix=_render_flag_pixels(new_pix,new_clut)
        if previous!=current_pix:
            raise ValueError(
                f"Master flag resource changes old country {nation_index}'s pixels")
        matching=next(i for i in plan["preserved_palettes"]
                      if i["index"]==nation_index)
        if sha(previous)!=matching["render_before_sha256"].upper() or (
            sha(current_pix)!=matching["render_after_sha256"].upper()
        ):
            raise ValueError("Protected existing nation's render hash is unverified")
        preserved.append(nation_index)
    return preserved

def apply_plan(disc: Disc, plan: dict) -> dict:
    validate_plan(plan)
    before_baseline=disc.expected_result_hash()
    if before_baseline!=BASE_RESULT_SHA:
        raise ValueError("Applying baseline v0.9.4 did not reproduce published Track01 SHA")
    lookup=disc.iso_files()
    contexts={name:set() for name in TARGET_COUNTRIES}
    touched=set()
    groups={}
    for edit in plan["streams"]:
        path=edit.get("resource")
        if not isinstance(path,str) or not _allowed_resource(path) or path not in lookup:
            raise ValueError(f"Not a known ISO national graphics resource: {path}")
        key=(path,edit.get("record_offset"))
        if key in touched:raise ValueError("Duplicate GPU stream change")
        touched.add(key)
        groups.setdefault(path,[]).append(edit)
    upload_count=0
    pixel_changes=0
    dat_before=None
    dat_after=None
    for path,edits in sorted(groups.items()):
        lba,size=lookup[path]
        original=disc.read_file(lba,size)
        data=original
        # Disjoint spans only. Each edit uses its own audited preimage, so
        # a collision causes a SHA failure before writing to the disc.
        for edit in sorted(edits,key=lambda v:v["record_offset"]):
            data,changed=patch_flag_stream(data,edit)
            pixel_changes+=changed
            upload_count+=1
            for country in edit.get("countries",[]):
                if country not in TARGET_COUNTRIES:
                    raise ValueError("Unknown national country attribution")
                if plan["styles"][country] not in edit["styles"]:
                    raise ValueError("Country attribution has no matching flag tile")
                contexts[country].add(edit["context"])
        if path=="BIN/DATSEL3.BIN":
            dat_before,dat_after=original,data
        disc.write_file(lba,original,data,"national graphics: "+path)
    if dat_before is None or dat_after is None:
        raise ValueError("Cannot verify unchanged nations: missing DATSEL3 atlas")
    preserved_nations=prove_unchanged_national_styles(
        disc,plan,dat_before,dat_after,groups["BIN/DATSEL3.BIN"])
    for country,(name_slot,rev_index) in TARGET_COUNTRIES.items():
        for label,physical in STYLE_TABLES.items():
            disc.write_raw(physical+name_slot,
                           bytes([plan["styles"][country]]),
                           f"flag style {label} {country}")
        palette=plan["palettes"][country]
        content=struct.pack("<16H",*palette)
        disc.write_form1_sequence(national_clut_offset(rev_index),content,
                                  "national flag CLUT: "+country)
    for edit in plan.get("preserved_palettes",[]):
        disc.write_form1_sequence(national_clut_offset(edit["index"]),
                                  struct.pack("<16H",*edit["palette"]),
                                  f"legacy national flag CLUT {edit['index']}")
    # Incorrectly shifted CLUT transparency entry #0 in v0.9.4.
    for index in sorted(TRANSPARENCY_CORRUPTED_IN_V094):
        pos=national_clut_offset(index)
        if disc.read_form1_sequence(pos,2)!=b"\x00\x00":
            disc.write_form1_sequence(pos,b"\x00\x00",
                                      f"CLUT transparency repair #{index}")

    # Every target country must have stream provenance. A country-specific
    # palette/style alone is not enough to count as a flag replacement.
    for country in TARGET_COUNTRIES:
        if not contexts[country]:
            raise ValueError(f"No image upload identified for {country}")
    resource_names=set(groups)
    gdc={name for name in lookup if STADIUM_NAME.fullmatch(name)}
    if not gdc or not gdc.issubset(resource_names):
        raise ValueError(f"Not all stadium GDC variants are covered: {sorted(gdc-resource_names)}")
    if not {"BIN/DATSEL.BIN","BIN/DATSEL3.BIN"}.issubset(resource_names):
        raise ValueError("Selection and match-entrance big flags must be fixed in both DATSEL and DATSEL3")
    return {"uploads":upload_count,"changed_pixels":pixel_changes,
            "graphic_resources":sorted(resource_names),
            "replaced_countries":sorted(TARGET_COUNTRIES),
            "unchanged_nations_render_proven":preserved_nations,
            "proven_contexts":{c:sorted(v) for c,v in contexts.items()}}

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original",required=True,type=Path,help="Clean EU SLES03321 Track01.bin")
    parser.add_argument("--base-patch",type=Path,default=None,help="Official v0.9.4 .iss26p")
    parser.add_argument("--plan",required=True,type=Path,help="Audited 17-flag art/upload plan JSON")
    parser.add_argument("--output",type=Path,default=Path("ISS26_0.9.5_flags_only.iss26p"))
    parser.add_argument("--report",type=Path,default=None)
    args=parser.parse_args(argv)
    try:
        if not args.original.is_file():
            raise FileNotFoundError("Original game Track01 BIN not found")
        if not args.plan.is_file():
            raise FileNotFoundError("Verified flag art plan is missing")
        if args.output.resolve()==args.original.resolve():
            raise ValueError("Output path is the same as the original")
        plan=json.loads(args.plan.read_text(encoding="utf-8"))
        validate_plan(plan)  # fail before downloading the base
        base=args.base_patch or args.output.parent/"ISS26_0.9.4_preview.iss26p"
        if base.resolve() in (args.output.resolve(),args.original.resolve()):
            raise ValueError("Output overlaps one of the source paths")
        raw=base.read_bytes() if base.exists() else download_verified_baseline(base)
        records=parse_patch(raw,expected_sha=BASE_V094_SHA)
        with Disc(args.original,records) as disc:
            changes=apply_plan(disc,plan)
            result=disc.export(args.output)
        result.update({"version":"0.9.5","kind":"flags-only",
                       "base_version":"0.9.4","flag_provenance":changes,
                       "releases_stable":False})
        report=args.report or args.output.with_suffix(".verification.json")
        report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",
                          encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        print("Candidate independently applies to CLEAN EU Track01; in-game QA still required.")
        return 0
    except (OSError,ValueError,AssertionError,DecodeError,KeyError,
            TypeError,UnicodeError) as exc:
        print("BUILD BLOCKED:",exc,file=sys.stderr)
        return 2

if __name__=="__main__":
    raise SystemExit(main())
