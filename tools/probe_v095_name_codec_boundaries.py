#!/usr/bin/env python3
"""Read-only ISS26 v0.9.5 national-name GPU packet-boundary probe.

The GPU upload record 'kind=10' is not a proven compression algorithm.
This tool emits only layout, sizes and SHA256, never game or texture bytes.
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path
from probe_v095_name_gpu_atlas import CLEAN_SHA, file_sha, raw_sector, user_data, upload_lists, sha

EXPECTED_ATLAS_SHA="C0931A9FBAB344715D38F9C21310549F4442C778FCEC47EA2FB7C3EC600A723F"
RESOURCE_BYTES=56256
GROUPS={"BIN/T_NAME_E.BIN":8200,"BIN/T_NAME_F.BIN":8230,"BIN/T_NAME_G.BIN":8260}
TABLE_OFFSET=55824

def packet_stats(packet:bytes)->dict:
    if not packet or len(packet)%4:
        raise ValueError("GPU packet span must be nonzero and 4-byte aligned")
    pad=len(packet)-len(packet.rstrip(bytes(1)))
    if pad>3 or packet[len(packet)-pad-1 if pad else -1]!=255:
        raise ValueError("GPU packet lacks final FF followed by at most 3 zero padding bytes")
    body=packet[:-pad] if pad else packet
    return {"allocated_bytes":len(packet),
            "bytes_through_final_ff":len(body),
            "trailing_zero_padding":pad,
            "last_nonzero_byte":"FF",
            "sha256":sha(body),
            "byte_sequence_7c01_count":body.count(bytes.fromhex("7c01"))}

def inspect_original(track:Path)->dict:
    if file_sha(track)!=CLEAN_SHA:
        raise ValueError("Only the verified original EU SLES-03321 Track01 is supported")
    resources={}
    with track.open("rb") as fp:
        for name,lba in GROUPS.items():
            blob=b"".join(user_data(raw_sector(fp,lba+n)) for n in range(28))[:RESOURCE_BYTES]
            if len(blob)!=RESOURCE_BYTES or sha(blob)!=EXPECTED_ATLAS_SHA:
                raise ValueError("Unexpected name atlas source hash: "+name)
            lists=upload_lists(blob)
            if len(lists)!=1 or lists[0]["list_offset"]!=TABLE_OFFSET:
                raise ValueError("Unexpected GPU upload table")
            records=lists[0]["uploads"]
            if len(records)!=26:
                raise ValueError("Unexpected number of GPU upload packets")
            offsets=[r["stream_offset"] for r in records]+[TABLE_OFFSET]
            if offsets[0]!=4 or any(a>=b or a%4 for a,b in zip(offsets,offsets[1:])):
                raise ValueError("Invalid GPU packet source offsets")
            entries=[]
            for i,(rec,end) in enumerate(zip(records,offsets[1:])):
                if (rec["kind"]!=10 or rec["upload_width_words"]!=32
                    or rec["upload_height"]!=128):
                    raise ValueError("Unexpected GPU upload descriptor")
                info=packet_stats(blob[rec["stream_offset"]:end])
                entries.append({"index":i,"vram_xy_words":[rec["vram_x_words"],rec["vram_y"]],
                                "stream_offset":rec["stream_offset"],**info})
            resources[name]={"lba":lba,"logical_bytes":len(blob),"sha256":sha(blob),"packets":entries}
    a=list(resources.values())
    if any(x["packets"]!=a[0]["packets"] for x in a[1:]):
        raise ValueError("Unmatched original language resources")
    return {"schema_version":1,"goal":"ISS26 0.9.5 GPU packet boundary audit",
            "original_track_sha256":CLEAN_SHA,"resources":resources,
            "packets_per_resource":26,
            "padding_distribution":dict(Counter(x["trailing_zero_padding"] for x in a[0]["packets"])),
            "byte_sequence_7c01_count":sum(x["byte_sequence_7c01_count"] for x in a[0]["packets"]),
            "all_packets_end_in_ff_with_zero_alignment":True,
            "compression_algorithm_verified":False,
            "notes":["FF is an observed trailing byte, not yet a proven decoder terminator.",
                     "Stream size includes alignment padding.",
                     "Upload kind 10 is not a proven compression codec ID."],
            "original_modified":False,"test14_built":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    result=json.dumps(inspect_original(args.clean_track),indent=2)+"\n"
    if args.output:args.output.write_text(result,encoding="utf-8")
    else:print(result)

if __name__=="__main__":
    main()
