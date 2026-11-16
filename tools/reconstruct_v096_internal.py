#!/usr/bin/env python3
"""Reconstruct the exact unpublished v0.9.6 2GK + appearance prototype.
Only independently recorded XOR masks are transported. Does not publish any
release or change any channel. Full final disc hash is from the earlier report,
not a new verification; use --track to independently verify it again.
"""
import argparse
import base64
import hashlib
import json
import struct
import zlib
from pathlib import Path
from integration_merge_eu import parse_patch, BASE_SHA, BASE_SIZE

ROOT = Path(__file__).resolve().parents[1]
CARRIER_SHA = "ACBA2D25D505D949D95718092CDE2D23BAF0C361AB17FBF127DB411AD7C3D870"
DELTA_SHA = "C9201B23F0D87D7592F7AA5944247FFDB97A2D051B3D867EAE12FFCDA986641B"
FINAL_SHA = "F3A211300AF201BE709498872E1E2572A7D1C362B3AA6E1ABCF90EC6C0969A97"
RESULT_SHA = "C66A2D63F12CD9130B4E9265670E4DA0D8CC5F40BA7C2B632C0C3048BB114C0F"
S, N = 2352, 19
EXPECTED_SECTORS = {167,168,169,170,171,172,852,853,854,930,931,932,933,934,935,936,937,938,939}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def sha(b):
    return hashlib.sha256(b).hexdigest().upper()

def rebuild(carrier, bundle):
    need(sha(carrier.read_bytes()) == CARRIER_SHA, "wrong withdrawn carrier")
    status = json.loads(bundle["output/revision_status.json"])
    need(status["patch"]["patch_sha256"] == FINAL_SHA
         and status["patch"]["result_sha256"] == RESULT_SHA
         and status["transport"]["delta_sha256"] == DELTA_SHA
         and status["transport"]["records"] == N, "revision report drift")
    delta = zlib.decompress(base64.b64decode("".join(bundle["v096_revision_delta.zlib.b64"].split()), validate=True))
    need(sha(delta) == DELTA_SHA, "wrong exact transport payload")
    # The SHA pins the entire envelope including the historical eight-byte
    # magic. Require the known length and record count, no guessed new header.
    need(len(delta) == 12 + N*(36+S) and struct.unpack_from("<I",delta,8)[0] == N,
         "unexpected historical transport layout")
    records = parse_patch(carrier)
    old = dict(records)
    touched = set()
    for i in range(N):
        p = 12+i*(36+S)
        lba, = struct.unpack_from("<I",delta,p)
        guard, diff = delta[p+4:p+36], delta[p+36:p+36+S]
        need(lba not in touched and lba in EXPECTED_SECTORS, "unexpected/duplicate delta sector")
        touched.add(lba)
        prior_guard, prior_mask = records.get(lba,(guard,bytes(S)))
        need(prior_guard == guard, "clean sector guard drift")
        mask = bytes(a^b for a,b in zip(prior_mask,diff))
        if any(mask):
            records[lba] = (guard,mask)
        else:
            records.pop(lba,None)
    need(touched == EXPECTED_SECTORS and len(records) == 699, "unexpected reconstructed sector set")
    need(all(records.get(i)==old.get(i) for i in records.keys()|old.keys() if i not in touched),
         "unrelated sector change")
    payload = bytearray(b"ISS26X01"+struct.pack("<I",len(records)))
    for lba,(guard,mask) in sorted(records.items()):
        payload += struct.pack("<I",lba)+guard+mask
    need(sha(payload) == FINAL_SHA, "final patch hash mismatch")
    return bytes(payload), records, delta[:8].hex()

def verify_track(track, records):
    need(track.stat().st_size==BASE_SIZE,"wrong clean image size")
    original, result = hashlib.sha256(), hashlib.sha256()
    verified = 0
    with track.open("rb") as f:
        for lba in range(BASE_SIZE//S):
            raw=f.read(S)
            need(len(raw)==S,"truncated clean image")
            original.update(raw)
            if lba in records:
                guard,mask=records[lba]
                need(hashlib.sha256(raw).digest()==guard,f"sector guard mismatch {lba}")
                raw=bytes(a^b for a,b in zip(raw,mask))
                verified+=1
            result.update(raw)
    need(original.hexdigest().upper()==BASE_SHA,"wrong clean image hash")
    need(result.hexdigest().upper()==RESULT_SHA and verified==699,"wrong reconstructed final image")
    return verified

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--carrier",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--track",type=Path)
    a=p.parse_args()
    bundle=json.loads((ROOT/"data/integration/v096_revision_internal_bundle.json").read_text())
    payload,records,magic=rebuild(a.carrier,bundle)
    verified=verify_track(a.track,records) if a.track else 0
    a.out.mkdir(parents=True,exist_ok=True)
    path=a.out/"ISS26_0.9.6_INTERNAL.iss26p"
    path.write_bytes(payload)
    need(parse_patch(path)==records and sha(path.read_bytes())==FINAL_SHA,"file readback mismatch")
    report={"status":"EXACT_INTERNAL_RECONSTRUCTION_NOT_RELEASED","version":"0.9.6",
        "patch_sha256":FINAL_SHA,"expected_result_sha256_from_prior_qa":RESULT_SHA,
        "transport_magic_hex":magic,"records":len(records),"fresh_clean_disc_guard_checks":verified,
        "fresh_full_disc_verification":bool(a.track),"runtime_verified":False,
        "nationality_written":False,"feed_changed":False}
    (a.out/"ISS26_0.9.6_INTERNAL.report.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))
