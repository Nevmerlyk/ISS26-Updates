#!/usr/bin/env python3
"""Read-only EU ISS26 0.9.6 nationality/ref audit; NEVER edits a disc or feed.
Inputs: clean Track01, exact revised internal patch, its roster_readback.csv,
and citizenship_candidates.csv from the internal revision bundle.
The first byte of the ref is a *candidate* country selector, not a verified
Master League rendering contract. Capacity counts use only original active
extra refs; inactive records are not assumed reusable.
"""
import argparse
import csv
import hashlib
import json
import re
import struct
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from integration_merge_eu import parse_patch, BASE_SHA, BASE_SIZE

ROOT = Path(__file__).resolve().parents[1]
S, R, OFF, NA, EA, NN, EN = 2352, 8620, 0x2094, 164052, 179364, 293204, 4928
SELECT_LBA, SELECT_LEN, EXE_LBA, EXE_LEN = 850, 233864, 24, 339968
INTERNAL_SHA = "F3A211300AF201BE709498872E1E2572A7D1C362B3AA6E1ABCF90EC6C0969A97"
TWO_GK_SHA = "34DCBA82744C0B3456556C0CFB14F2EAD78E770BCA03BD97A3947B558C67E91B"

def need(ok, message):
    if not ok:
        raise ValueError(message)

def csvrows(p):
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def norm(v):
    return re.sub("[^a-z0-9]", "", unicodedata.normalize("NFKD", v).encode("ascii", "ignore").decode().lower())

def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for x in iter(lambda: f.read(1024 * 1024), b""):
            h.update(x)
    return h.hexdigest().upper()

def resource(track, records, lba, size):
    result = bytearray()
    with track.open("rb") as f:
        for i in range(lba, lba + (size + 2047)//2048):
            f.seek(i*S)
            raw = f.read(S)
            need(len(raw) == S, f"short sector {i}")
            if i in records:
                guard, mask = records[i]
                need(hashlib.sha256(raw).digest() == guard, f"guard drift {i}")
                raw = bytes(a ^ b for a, b in zip(raw, mask))
            need(raw[15] == 2 and not raw[18] & 32 and raw[16:20] == raw[20:24],
                 f"not Mode2 Form1: {i}")
            result += raw[24:2072]
    return bytes(result[:size])

def label(buf, offset):
    return buf[offset:offset+10].split(b"\0", 1)[0].decode("ascii")

def refs(buf):
    return [tuple(buf[i:i+2]) for i in range(R, R+1056, 2)]

def extra(ref):
    return ref[0] >= 54 or ref[1] >= 22

def capacity_report(demand, supply):
    return {str(k): {"demand": demand[k], "observed_original_capacity": supply[k],
                     "shortfall": max(0, demand[k]-supply[k])}
            for k in sorted(demand.keys() | supply.keys())}

def analyze(track, patch, readback, citizenship):
    need(track.stat().st_size == BASE_SIZE and digest(track) == BASE_SHA, "wrong original EU image")
    need(digest(patch) in (INTERNAL_SHA, TWO_GK_SHA), "wrong internal revision; not 0.9.7")
    original = resource(track, {}, SELECT_LBA, SELECT_LEN)
    records = parse_patch(patch)
    selected = resource(track, records, SELECT_LBA, SELECT_LEN)
    exe = resource(track, records, EXE_LBA, EXE_LEN)
    offsets = struct.unpack_from("<118H", original, OFF)
    need(original[OFF:OFF+236] == selected[OFF:OFF+236], "offset table changed unexpectedly")
    old, active = refs(original), refs(selected)
    need(len(set(old)) == len(set(active)) == 528, "club ref collision")
    def ix(ref):
        h, l = ref
        need(h < len(offsets), f"unmapped high byte {h}")
        v = offsets[h] + l - 22
        need(0 <= v < 341, f"extra index out of bounds {ref}")
        return v
    native = {ref: ix(ref) for ref in old if extra(ref)}
    need(len(native) == len(set(native.values())) == 315, "wrong native extra mapping")
    selected_extras = [ref for ref in active if extra(ref)]
    need(len(selected_extras) == 301 and all(ref in native for ref in selected_extras),
         "unexpected revised extra refs")
    registry = json.loads((ROOT/"data/integration/eu_v096_registry.json").read_text())
    clubreg = json.loads((ROOT/"data/integration/active_club_registry_v21.json").read_text())
    bundle = json.loads((ROOT/"data/integration/v096_revision_internal_bundle.json").read_text())
    countryreg = json.loads(bundle["revision/citizenship_registry.json"])
    playable = {t["team_id"]: 53-t["disc_slot"] for t in registry["national_slots"]}
    clubids = {t["team_id"]: 23-t["ordinal"] for t in clubreg["menu_order"]}
    known = dict(countryreg["playable_country_id"])
    known.update(countryreg["known_existing_extra_codes"])
    rr, cc = csvrows(readback), csvrows(citizenship)
    need(len(rr) == len(cc) == 1716, "expected 1716 modern slots in both inputs")
    cm = defaultdict(list)
    for c in cc:
        cm[c["team_id"], norm(c["player_name"])].append(c)
    slots, club_refs, used_cit = set(), set(), set()
    team_positions, demands, no_id = defaultdict(list), Counter(), Counter()
    matches, gaps, blocked, mismatch, linked_conflicts = [], [], [], [], []
    country_by_ref = {}
    for row in sorted(rr, key=lambda x: x["team_id"].startswith("CLB_")):
        team, slot = row["team_id"], int(row["slot"])
        need(1 <= slot <= 22 and (team, slot) not in slots, "invalid or duplicate slot")
        slots.add((team, slot))
        rb = bytes.fromhex(row["ref"])
        need(len(rb) == 2, "invalid ref")
        ref = tuple(rb)
        h, l = ref
        cand = cm[team, norm(row["player_name"])]
        need(len(cand) == 1, f"ambiguous/missing citizenship match {team} {row['player_name']}")
        c = cand[0]
        ck = (team, norm(row["player_name"]))
        need(ck not in used_cit, f"duplicate candidate {ck}")
        used_cit.add(ck)
        code = c["country"]
        need(bool(code), f"empty citizenship {ck}")
        if team in playable:
            need(ref == (playable[team], slot-1), f"national ref drift {team} {slot}")
            need(code == team[4:] and row["record_type"] == "NATIONAL", "national identity mismatch")
        else:
            need(team in clubids and active[clubids[team]*22+slot-1] == ref, "club slot/ref drift")
            need(ref not in club_refs, "duplicate club ref")
            club_refs.add(ref)
        if extra(ref):
            need(team in clubids and ref in native and row["record_type"] == "CLUB_EXTRA", "extra ref drift")
            idx = ix(ref)
            name = label(selected, EN+10*idx)
            p = selected[EA+12*idx] & 15
        else:
            need(h < 54 and l < 22, "bonus or invalid reference")
            idx = h*22+l
            name = label(exe, NN+10*idx)
            p = selected[NA+12*idx] & 15
            if team in clubids:
                need(row["record_type"] == "SHARED_NATIONAL", "shared ref type mismatch")
        need(name == row["label"] and p == int(row["position"]), f"readback mismatch {team} {slot}")
        team_positions[team].append(p)
        target = known.get(code)
        item = {"team": team, "slot": slot, "player": row["player_name"], "ref": row["ref"],
                "source_country": code, "candidate_native_id": target, "current_ref_high": h,
                "method": c["method"]}
        if "NAME" in c["method"]:
            blocked.append(item)
        if team in playable:
            country_by_ref[ref] = code
            continue
        if row["record_type"] == "SHARED_NATIONAL" and country_by_ref.get(ref) != code:
            linked_conflicts.append(item)
        if target is None:
            no_id[code] += 1
            gaps.append(item)
        else:
            if extra(ref):
                demands[target] += 1
            if target != h:
                mismatch.append(item)
            else:
                matches.append(item)
    need(len(team_positions) == 78 and all(len(v) == 22 and v.count(0) == 2 for v in team_positions.values()),
         "roster composition is not 2 GK + 20 outfield")
    need(len(club_refs) == 528 and len(used_cit) == 1716, "join coverage mismatch")
    need(len(linked_conflicts) == 0 or all(item["team"].startswith("CLB_") for item in linked_conflicts),
         "invalid link diagnostics")
    supply = Counter(h for h, l in native)
    return {"status": "READ_ONLY_STATIC_CANDIDATE_NOT_RUNTIME_PROOF", "teams": 78,
            "slots": 1716, "club_refs": 528, "extra_records": len(selected_extras),
            "club_slots_matching_candidate_high_byte": len(matches),
            "club_slots_different_candidate_high_byte": mismatch,
            "club_slots_without_known_id": gaps, "unmapped_country_counts": dict(no_id),
            "name_only_sources_for_review": blocked, "shared_identity_country_conflicts": linked_conflicts,
            "observed_capacity_by_id": capacity_report(demands, supply),
            "notes": ["No game writes. Country selector and flag renderer require Master League runtime proof.",
                      "Capacity considers only the 315 original active extra references, not hypothetical free space.",
                      "Do not change a ref high byte without moving its name/stats and checking pointer/index collision."]}

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for opt in ("track", "patch", "readback", "citizenship", "out"):
        p.add_argument("--"+opt, required=True, type=Path)
    a = p.parse_args()
    result = analyze(a.track, a.patch, a.readback, a.citizenship)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(result["status"], result["teams"], result["slots"])
