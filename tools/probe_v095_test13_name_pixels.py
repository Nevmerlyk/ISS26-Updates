#!/usr/bin/env python3
"""Read-only Test13→decoded-name GPU difference report for ISS26 v0.9.5.

Downloads the pinned published Test13 patch only if no --test13 is provided.
No disc/patch assets, raw pixel bytes or proprietary artwork are exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request

from probe_v095_name_gpu_atlas import (
    CLEAN_SHA, TEST13_SHA, PATCH_URL, GROUPS, file_sha,
    parse_patch, directory_files, resource_data, find_original_track,
)
from v095_name_lz_codec import atlas_records, decode_atlas, TILE_BYTES


def digest(data):
    return hashlib.sha256(data).hexdigest().upper()


def pixel_differences(before: bytes, after: bytes):
    """Return exact nibble difference count and local bounding rectangle."""
    if len(before) != TILE_BYTES or len(after) != TILE_BYTES:
        raise ValueError("expected 8192-byte 4bpp tile")
    count = 0
    xmin, ymin, xmax, ymax = 128, 128, -1, -1
    for i, (a,b) in enumerate(zip(before, after)):
        if a==b:
            continue
        y=i//64
        x=(i%64)*2
        for nibble in (0,1):
            if ((a >> (4*nibble)) & 15) != ((b >> (4*nibble)) & 15):
                px=x+nibble
                count+=1
                xmin=min(xmin,px)
                xmax=max(xmax,px)
                ymin=min(ymin,y)
                ymax=max(ymax,y)
    return {"changed_pixels":count,
            "local_bbox_xywh":([xmin,ymin,xmax-xmin+1,ymax-ymin+1] if count else None)}


def compare_resources(disc: Path, test13_bytes: bytes):
    if file_sha(disc) != CLEAN_SHA:
        raise ValueError("only the verified clean SLES-03321 Track01 is accepted")
    patch = parse_patch(test13_bytes)
    report = {}
    with disc.open("rb") as f:
        catalog=directory_files(f)
        for path, lbas in GROUPS.items():
            if path not in catalog:
                raise ValueError("name resource missing from original ISO: " + path)
            lba,size=catalog[path]
            old,new,covered=resource_data(f,lba,size,patch)
            if covered!=set(lbas):
                raise ValueError("unexpected Test13 edited sector scope: " + path)
            before=decode_atlas(old)
            after=decode_atlas(new)
            geometry_old=[(x["x_words"],x["y"]) for x in atlas_records(old)]
            geometry_new=[(x["x_words"],x["y"]) for x in atlas_records(new)]
            if geometry_old!=geometry_new:
                raise ValueError("Test13 modified GPU rectangle positions")
            entries=[]
            for i,(a,b) in enumerate(zip(before,after)):
                diff=pixel_differences(a,b)
                entries.append({"stream_id":i,"vram_xy_words_and_rows":geometry_old[i],
                                "original_pixels_sha256":digest(a),
                                "test13_pixels_sha256":digest(b),**diff})
            report[path]={
                "logical_resource_bytes":size,
                "original_resource_sha256":digest(old),
                "test13_resource_sha256":digest(new),
                "changed_streams":[v["stream_id"] for v in entries if v["changed_pixels"]],
                "changed_pixel_total":sum(v["changed_pixels"] for v in entries),
                "streams":entries,
            }
    return {
        "schema_version":1,"subject":"ISS26 Test13 exact decoded 4bpp prematch name changes",
        "original_track_sha256":CLEAN_SHA,"test13_patch_sha256":TEST13_SHA,
        "resources":report,
        "all_3_languages_identical_in_decoded_pixels":len({
            tuple(row["test13_pixels_sha256"] for row in r["streams"])
            for r in report.values()})==1,
        "notice":"Changed pixel bounds are in GPU texture tiles, NOT verified on-screen text placement.",
        "next_step":"Correlate changed pixel regions with the Cabo/Verde draw UVs from a verified prematch GPU capture, then edit only the target letters.",
        "modifies_original":False,"patch_generated":False,
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-track",type=Path)
    parser.add_argument("--game-root",type=Path,default=Path("D:/ISS 26"))
    parser.add_argument("--test13",type=Path)
    parser.add_argument("--output",type=Path,default=Path("ISS26-Test13-name-pixel-diff.json"))
    args=parser.parse_args()
    track=args.clean_track or find_original_track(args.game_root)
    if args.test13:
        data=args.test13.read_bytes()
    else:
        with urllib.request.urlopen(PATCH_URL,timeout=45) as response:
            data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:
            raise ValueError("Test13 source patch exceeds permitted size")
    result=compare_resources(track,data)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("Saved read-only difference report:",args.output)


if __name__=="__main__":
    main()
