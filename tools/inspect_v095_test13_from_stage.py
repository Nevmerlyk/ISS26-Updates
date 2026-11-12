#!/usr/bin/env python3
"""Read-only: restore exact Test13 prematch-name atlases from Test10 staging.

Test13 retains Test10's 84 T_NAME E/F/G sector records bit-for-bit. This
avoids downloading the full 3.5MB Test13 release. The author-owned CLEAN EU
Track01 is verified and never changed; no original artwork is distributed.
"""
from __future__ import annotations
import argparse, base64, hashlib, json, lzma, struct, urllib.request, zlib
from pathlib import Path

from probe_v095_name_gpu_atlas import (
    CLEAN_SHA, GROUPS, directory_files, file_sha, resource_data, sha,
)
from build_v095_targeted_name_overlay import correct_xor_parity
from v095_name_lz_codec import decode_atlas, atlas_records
from probe_v095_test13_name_pixels import pixel_differences

TRANSFER_SHA="C425FEE3E5B561A507E864DA22E08EDD3C5F0A3D43FCE42371A7DB8BD65317AC"
DELTA_SHA="3006D0D0111670B611CBCC87FAE80E3F94CBCD7DE8DB6F340407996C7FD6BE14"
ATLAS_SHA="01B9CCAAC6FF79372E30A3595AA98B9E41E6A6BA508ABABE77362829CF13300E"
PART_URL=("https://raw.githubusercontent.com/Nevmerlyk/ISS26-Updates/"
          "main/staging/v0.9.5/test10_prematch_names_delta.part{:02d}.b64")
EXPECTED_LBAS=tuple(k for group in GROUPS.values() for k in group)
TILE_WIDTH=128
CANVAS_W=1792
CANVAS_H=256


def load_staged_parts(folder:Path|None=None)->list[str]:
    result=[]
    for n in range(1,6):
        if folder is None:
            with urllib.request.urlopen(PART_URL.format(n),timeout=30) as response:
                body=response.read(25001)
        else:
            body=(folder/f"test10_prematch_names_delta.part{n:02d}.b64").read_bytes()
        if not 1<=len(body)<=25000:
            raise ValueError(f"Invalid stage part {n} size")
        result.append(body.decode("ascii").strip())
    return result


def parse_staged_name_delta(parts:list[str])->dict[int,tuple[bytes,bytes]]:
    if len(parts)!=5:
        raise ValueError("Need five stage transfer chunks")
    packed=base64.b64decode("".join(parts),validate=True)
    if sha(packed)!=TRANSFER_SHA:
        raise ValueError("Pinned stage transfer SHA256 mismatch")
    delta=lzma.decompress(packed,format=lzma.FORMAT_XZ)
    if sha(delta)!=DELTA_SHA:
        raise ValueError("Pinned decompressed stage SHA256 mismatch")
    if delta[:8]!=b"ISS26M01" or len(delta)!=12+84*2388:
        raise ValueError("Unexpected stage name delta format/size")
    n,=struct.unpack_from("<I",delta,8)
    if n!=84:
        raise ValueError("Unexpected name sector count")
    rows={}
    for i in range(n):
        at=12+i*2388
        lba,=struct.unpack_from("<I",delta,at)
        if lba!=EXPECTED_LBAS[i]:
            raise ValueError(f"Unexpected or unsorted name-sector LBA: {lba}")
        guard=delta[at+4:at+36]
        mask=delta[at+36:at+2388]
        check=bytearray(mask)
        correct_xor_parity(check)
        if bytes(check)!=mask or not any(mask[24:2072]):
            raise ValueError(f"Bad Mode2/Form1 parity mask at LBA {lba}")
        rows[lba]=(guard,mask)
    return rows


def image_png(tiles:list[bytes],records:list[dict],original:list[bytes]|None=None)->bytes:
    """PNG grayscale indices; red denotes difference from original nibbles."""
    rgb=bytearray(b"\xff")*(CANVAS_W*CANVAS_H*3)
    for n,(tile,rec) in enumerate(zip(tiles,records)):
        start_x=rec["x_words"]*4
        start_y=rec["y"]
        if start_x<0 or start_x+128>CANVAS_W or start_y<0 or start_y+128>CANVAS_H:
            raise ValueError("GPU tile exceeds montage")
        for k,v in enumerate(tile):
            for nib in (0,1):
                p=(v>>(4*nib))&15
                px=start_x+2*(k%64)+nib
                py=start_y+k//64
                pos=(py*CANVAS_W+px)*3
                before=((original[n][k]>>(4*nib))&15) if original else p
                if p!=before:
                    rgb[pos:pos+3]=bytes((224,18,48))
                elif p:
                    tone=16+min(p*8,130)
                    rgb[pos:pos+3]=bytes([tone])*3
    raw=bytearray()
    stride=CANVAS_W*3
    for y in range(CANVAS_H):
        raw.append(0)
        raw.extend(rgb[y*stride:(y+1)*stride])
    def chunk(tag,payload):
        return (struct.pack(">I",len(payload))+tag+payload+
                struct.pack(">I",zlib.crc32(tag+payload)&0xffffffff))
    return (bytes.fromhex("89504e470d0a1a0a")+
            chunk(b"IHDR",struct.pack(">IIBBBBB",CANVAS_W,CANVAS_H,8,2,0,0,0))+
            chunk(b"IDAT",zlib.compress(raw,6))+chunk(b"IEND",b""))


def analyze_original(track:Path,parts:list[str],outdir:Path)->dict:
    if file_sha(track)!=CLEAN_SHA:
        raise ValueError("Expected the clean European Track01 SHA256")
    patches=parse_staged_name_delta(parts)
    results={}
    canonical=None
    with track.open("rb") as source:
        catalog=directory_files(source)
        for name,lbas in GROUPS.items():
            if name not in catalog:
                raise ValueError("Original ISO missing "+name)
            lba,size=catalog[name]
            if lba!=lbas[0] or size!=56256:
                raise ValueError("Unrecognized name atlas layout")
            clean,patched,used=resource_data(source,lba,size,patches)
            if used!=set(lbas) or sha(patched)!=ATLAS_SHA:
                raise ValueError("Reconstructed Test13 name atlas hash does not match")
            original,new=decode_atlas(clean),decode_atlas(patched)
            old_geometry=atlas_records(clean)
            geometry=atlas_records(patched)
            if [(r["x_words"],r["y"]) for r in geometry]!=[
                (r["x_words"],r["y"]) for r in old_geometry]:
                raise ValueError("Test13 name upload geometry changed")
            names=[sha(tile) for tile in new]
            diff=[]
            for i,(a,b) in enumerate(zip(original,new)):
                info=pixel_differences(a,b)
                diff.append({"stream":i,"vram_xy_words":[geometry[i]["x_words"],geometry[i]["y"]],**info})
            if canonical is None:
                canonical=names
                outdir.mkdir(parents=True,exist_ok=True)
                (outdir/"ISS26_Test13_names.png").write_bytes(image_png(new,geometry))
                (outdir/"ISS26_Test13_changes.png").write_bytes(image_png(new,geometry,original))
            elif canonical!=names:
                raise ValueError("Test13 three language atlases are not pixel-identical")
            results[name]={"logical_bytes":size,
                           "original_atlas_sha256":sha(clean),
                           "reconstructed_atlas_sha256":sha(patched),
                           "changed_tiles":[r["stream"] for r in diff if r["changed_pixels"]],
                           "tile_differences":diff}
    output={"schema_version":1,"source_track_sha256":CLEAN_SHA,
            "staged_transfer_sha256":TRANSFER_SHA,
            "staged_delta_sha256":DELTA_SHA,
            "test13_name_atlas_sha256":ATLAS_SHA,
            "all_3_language_atlases_equal":True,"resources":results,
            "important":"Name pixels recovered from Test10's verified 84-record delta, preserved unchanged in Test13. This does not reconstruct other Test13 assets.",
            "not_a_live_gpu_capture":True,"cape_verde_position_verified":False,
            "test14_patch_built":False,"original_modified":False}
    (outdir/"ISS26_Test13_name_diff.json").write_text(
        json.dumps(output,indent=2)+"\n",encoding="utf-8")
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--clean-track",required=True,type=Path)
    p.add_argument("--parts-folder",type=Path,
                   help="Optional offline folder containing five staged base64 text files")
    p.add_argument("--outdir",type=Path,default=Path("ISS26-Test13-NameAtlas"))
    args=p.parse_args()
    result=analyze_original(args.clean_track,load_staged_parts(args.parts_folder),args.outdir)
    print("Verified 84 staged source sectors and all three Test13 atlases.")
    print("Changed streams:",result["resources"]["BIN/T_NAME_E.BIN"]["changed_tiles"])
    print("Output:",args.outdir)


if __name__=="__main__":
    main()
