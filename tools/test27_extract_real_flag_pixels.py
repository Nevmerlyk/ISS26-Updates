#!/usr/bin/env python3
"""Test27: view the *actual* Bosnia/Cape 4bpp atlas and stage from Test26 ZIP.

No new match. No ROM or raw pixels uploaded to GitHub. Runs locally only on
the already captured Academy session; outputs RGB PNGs and small metadata in
the specified local folder, never changes an input file or update feed.

Flags and palettes are READ directly from the owner-provided 2MB VRAM dump.
Index 0 is shown both as the underlying BGR555 CLUT colour and (separately)
as magenta for distinguishing transparent or masked areas. Raw screenshot
classification remains out of scope.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zipfile
from analyze_flag_test12_phases import VRAM_BYTES, safe_archive_files
from analyze_flag_test26_unified import (
    atlas_xy, tile, clut, sha, STYLE_WORDS, STYLE_ROWS,
)
from test27_flag_art_4bpp import png, unpack_4bpp, W, H

EXPECTED_ZIP_SHA = "611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690"
EXACT_VRAM_NAME = "rookie_exam_transition_00005468.vram"
PAIRS = (
    ("cape_verde",1,(560,0),(0,505)),
    ("bosnia",55,(560,28),(224,506)),
)

def sha_path(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest().upper()

def read_snapshot(archive: Path) -> bytes:
    with zipfile.ZipFile(archive) as z:
        members=[x for x in safe_archive_files(z)
                 if PurePosixPath(x.filename.replace("\\","/")).name==EXACT_VRAM_NAME]
        if len(members)!=1:
            raise ValueError("Expected exactly one frame-5468 VRAM snapshot in ZIP")
        if members[0].file_size != VRAM_BYTES:
            raise ValueError("Expected PCSX-Redux 2MB VRAM snapshot")
        return z.read(members[0])

def decode_bgr555_clut(raw: bytes) -> tuple[tuple[int,int,int],...]:
    if len(raw)!=32:raise ValueError("PS1 4bpp CLUT must have 16 colors")
    values=struct.unpack("<16H",raw)
    return tuple(((((v>>0)&31)*255+15)//31,
                  (((v>>5)&31)*255+15)//31,
                  (((v>>10)&31)*255+15)//31) for v in values)

def diff_indices(stage: list[int], atlas: list[int]) -> tuple[list[int],dict]:
    if len(stage)!=W*H or len(atlas)!=W*H:
        raise ValueError("Expected 64x28 indexed images")
    delta=[]
    counts={"equal":0,"source_nonzero_stage_zero":0,
            "new_nonzero":0,"changed_nonzero":0}
    affected_rows=[0]*H
    for i,(a,b) in enumerate(zip(stage,atlas)):
        if a==b:
            key,index="equal",1
        elif a==0 and b!=0:
            key,index="source_nonzero_stage_zero",2
            affected_rows[i//W]+=1
        elif a!=0 and b==0:
            key,index="new_nonzero",4
        else:
            key,index="changed_nonzero",3
        delta.append(index)
        counts[key]+=1
    return delta,{"pixel_index_differences":counts,
                  "source_nonzero_stage_zero_by_row":affected_rows,
                  "is_contiguous_bottom_12_row_mask":all(
                      affected_rows[y]==0 for y in range(16))
                  and all(affected_rows[y]>0 for y in range(16,28))
                  and counts["new_nonzero"]==0
                  and counts["changed_nonzero"]==0}

def inspect_archive(archive: Path, output: Path,
                    required_sha: str | None = EXPECTED_ZIP_SHA) -> dict:
    digest=sha_path(archive)
    if required_sha is not None and digest != required_sha:
        raise ValueError("Not the verified Test26 ZIP; refusing wrong-source audit")
    raw=read_snapshot(archive)
    output.mkdir(parents=True,exist_ok=True)
    results={}
    for name,style,stage_xy,clut_xy in PAIRS:
        source=tile(raw,*atlas_xy(style))
        stage=tile(raw,*stage_xy)
        palette=decode_bgr555_clut(clut(raw,*clut_xy))
        source_pixels=unpack_4bpp(source)
        stage_pixels=unpack_4bpp(stage)
        delta,analysis=diff_indices(stage_pixels,source_pixels)
        marked=((255,0,255),)+palette[1:]
        diff_colours=((0,0,0),(49,150,93),(244,63,67),(239,178,58),(93,104,225))
        for label,pixels,colours in (
            ("source_clut",source_pixels,palette),
            ("stage_clut",stage_pixels,palette),
            ("source_zero_marked",source_pixels,marked),
            ("stage_zero_marked",stage_pixels,marked),
            ("source_stage_diff",delta,diff_colours),
        ):
            (output / f"{name}_{label}.png").write_bytes(png(pixels,colours))
        results[name]={
            "source_style":style,
            "source_vram_words":list(atlas_xy(style)),
            "stage_vram_words":list(stage_xy),
            "clut_vram_words":list(clut_xy),
            "source_tile_sha256":sha(source),
            "stage_tile_sha256":sha(stage),
            "clut_sha256":sha(clut(raw,*clut_xy)),
            "diff":analysis,
            "images_written":5,
        }
    report={
        "schemaVersion":1,
        "kind":"Test27 actual owner ZIP CLUT + flag pixel comparison (read-only)",
        "input_zip_sha256":digest,
        "snapshot":EXACT_VRAM_NAME,
        "input_vram_sha256":sha(raw),
        "source_disc_modified":False,
        "game_patch_built":False,
        "update_feed_changed":False,
        "no_game_disc_bytes_embedded_in_report":True,
        "visual_ownership_proven":False,
        "flags":results,
        "interpretation":"Image comparison proves bytes/CLUT at sample frame; "
                         "not correct design, resource last writer or spectator scene."
    }
    (output/"test27_real_flag_pixels.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--academy-zip",required=True,type=Path)
    p.add_argument("--output-dir",required=True,type=Path)
    a=p.parse_args()
    report=inspect_archive(a.academy_zip,a.output_dir)
    for name,data in report["flags"].items():
        print(name, data["diff"]["pixel_index_differences"],
              "bottom12-mask?",data["diff"]["is_contiguous_bottom_12_row_mask"])
    print("Done. Ten actual-VRAM previews and JSON saved locally; game unmodified.")

if __name__=="__main__":
    main()
