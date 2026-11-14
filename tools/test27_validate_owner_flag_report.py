#!/usr/bin/env python3
"""Test27: validate owner-produced real VRAM pixel/CLUT evidence (read-only).

Reads only numerical metadata from test27_real_flag_pixels.json, without
importing, reproducing or uploading the original game artwork. Distinguishes
machine-verifiable texture copy and CLUT equality from manual visual review.
No patch creation or release promotion.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PIXELS=64*28
EXPECTED_ARCHIVE_SHA="611C5EF4FF093284EA8F35FBAD608D7387776E621AC471967FAC856807B8A690"
EXPECTED_FRAME="rookie_exam_transition_00005468.vram"

def validate(report: dict) -> dict:
    if report.get("schemaVersion")!=1 or report.get("input_zip_sha256")!=EXPECTED_ARCHIVE_SHA:
        raise ValueError("Expected verified original Test26 Academy ZIP report")
    if report.get("snapshot")!=EXPECTED_FRAME or report.get("visual_ownership_proven") is not False:
        raise ValueError("Unexpected VRAM snapshot or unsubstantiated visual ownership")
    if any(report.get(key) is not False for key in
           ("source_disc_modified","game_patch_built","update_feed_changed")):
        raise ValueError("Unexpected image-modification or patch claim")
    flags=report.get("flags")
    if not isinstance(flags,dict) or set(flags)!={"cape_verde","bosnia"}:
        raise ValueError("Expected Cape Verde and Bosnia, and no other flag")
    expected={"cape_verde": (1,[848,256],[560,0],[0,505]),
              "bosnia": (55,[816,368],[560,28],[224,506])}
    results={}
    cluts=set()
    for name,(style,source_xy,stage_xy,clut_xy) in expected.items():
        f=flags[name]
        if (f.get("source_style")!=style or f.get("source_vram_words")!=source_xy
                or f.get("stage_vram_words")!=stage_xy or f.get("clut_vram_words")!=clut_xy):
            raise ValueError("Unexpected source/stage/CLUT provenance: "+name)
        for field in ("source_tile_sha256","stage_tile_sha256","clut_sha256"):
            value=f.get(field,"")
            if not isinstance(value,str) or len(value)!=64 or any(c not in "0123456789ABCDEF" for c in value):
                raise ValueError("Missing or invalid digest: "+name+"/"+field)
        cluts.add(f["clut_sha256"])
        diff=f["diff"]
        counts=diff["pixel_index_differences"]
        keys={"equal","source_nonzero_stage_zero","new_nonzero","changed_nonzero"}
        if set(counts)!=keys or any(type(v) is not int or v<0 for v in counts.values()):
            raise ValueError("Invalid 4bpp pixel-index comparison")
        if sum(counts.values())!=PIXELS:
            raise ValueError("4bpp pixel difference count does not cover all 1792 positions")
        rows=diff["source_nonzero_stage_zero_by_row"]
        if not isinstance(rows,list) or len(rows)!=28 or any(type(x) is not int or not 0<=x<=64 for x in rows):
            raise ValueError("Expected 28 bounded row counts")
        if sum(rows)!=counts["source_nonzero_stage_zero"]:
            raise ValueError("Index-loss row sum inconsistent with pixel count")
        source_equals_stage=(f["source_tile_sha256"]==f["stage_tile_sha256"])
        if source_equals_stage != (counts["equal"]==PIXELS):
            raise ValueError("SHA full equality inconsistent with per-pixel index comparison")
        if diff["is_contiguous_bottom_12_row_mask"] != (
                all(x==0 for x in rows[:16]) and all(x>0 for x in rows[16:])
                and counts["new_nonzero"]==0 and counts["changed_nonzero"]==0):
            raise ValueError("Bottom mask claim inconsistent with pixel-index rows")
        results[name]={
            "source_equals_staging":source_equals_stage,
            "equal_4bpp_index_positions":counts["equal"],
            "source_nonzero_to_stage_zero":counts["source_nonzero_stage_zero"],
            "bottom_12_mask":diff["is_contiguous_bottom_12_row_mask"],
            "affected_rows":[i for i,x in enumerate(rows) if x],
            "source_style":style,
            "actual_clut_words":clut_xy,
        }
    cape=results["cape_verde"]
    bosnia=results["bosnia"]
    return {
        "schemaVersion":1,
        "kind":"Real Test27 source/staging evidence gate; artwork requires human review",
        "verified_archive_sha256":EXPECTED_ARCHIVE_SHA,
        "frame":EXPECTED_FRAME,
        "flags":results,
        "two_clut_addresses_identical_content":len(cluts)==1,
        "cape_copy_exact":cape["source_equals_staging"],
        "bosnia_atlas_bottom_trimmed":bosnia["bottom_12_mask"],
        "bosnia_lower_row_lost_indices":bosnia["source_nonzero_to_stage_zero"],
        "machine_can_verify_national_art_design":False,
        "staging_writer_proven":False,
        "rendered_crowd_flag_ownership_proven":False,
        "corrected_game_patch_releasable":False,
        "notes":[
            "Actual CLUT identities do not prove CLUTs are incorrectly shared.",
            "Zero 4bpp index does not establish transparency without PS1 CLUT/STP context.",
            "Design correctness requires an explicitly visually reviewed source preview.",
            "Game patch requires dedicated correct national artwork, isolated mapping, "
            "proven staging fix and clean-original/club regression."
        ],
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if args.report.stat().st_size>256000:
        raise ValueError("Oversized metadata JSON")
    data=json.loads(args.report.read_text(encoding="utf-8-sig"))
    result=validate(data)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Cape stage copied exactly:",result["cape_copy_exact"])
    print("Bosnia bottom twelve rows zero-mask:",result["bosnia_atlas_bottom_trimmed"])
    print("Same live CLUT content at two coordinates:",result["two_clut_addresses_identical_content"])
    print("No patch release authorized: source art/CLUT design remains human-reviewed evidence.")
if __name__=="__main__":
    main()
