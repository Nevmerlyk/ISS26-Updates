#!/usr/bin/env python3
"""Read-only release-asset XOR metadata audit; original PS1 disc not uploaded."""
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib, struct, json

URL = "https://github.com/Nevmerlyk/ISS26-Updates/releases/download/v0.9.5-largeflag-source-test13/ISS26_0.9.5_LargeFlagSource_TEST13.iss26p"
EXPECTED = "159A31A95BBAE3BD032417DFDCB8B5478016907DCC1E848D968CBF5B17E61214"
STYLE_OFFSETS = [0x1D6F48, 0x1E94CC, 0x224C50, 0x4AD4B8, 0x575864]
RECORD = 4 + 32 + 2352
with urlopen(Request(URL, headers={"User-Agent":"ISS26-Test25-SourceAudit/1.0"}), timeout=60) as f:
    raw = f.read(4 * 1024 * 1024)
got = hashlib.sha256(raw).hexdigest().upper()
if got != EXPECTED or raw[:8] != b"ISS26X01":
    raise ValueError("Unexpected release SHA or magic: " + got)
count, = struct.unpack_from("<I", raw, 8)
if count != 1492 or len(raw) != 12 + RECORD * count:
    raise ValueError("Bad Test13 record count")
rows = {}
prior = -1
for i in range(count):
    at = 12 + i * RECORD
    lba, = struct.unpack_from("<I", raw, at)
    if lba <= prior or lba >= 210951:
        raise ValueError("Unsorted or out-of-range LBA")
    prior = lba
    mask = raw[at+36:at+RECORD]
    if any(mask[:24]):
        raise ValueError("Patched raw sector header at " + str(lba))
    rows[lba] = mask
style_masks=[]
for offset in STYLE_OFFSETS:
    lba, local = divmod(offset, 2352)
    x = rows.get(lba, bytes(2352))[local:local+78]
    if len(x) != 78: raise ValueError("Incomplete style mask")
    style_masks.append({
        "rawTrackOffset":offset, "lba":lba, "changedSlots":[i for i,v in enumerate(x) if v],
        "xorMaskHex":x.hex(), "changedByteCount":sum(bool(v) for v in x)
    })
GDC = {
 "AD":(12560,140632),"AN":(12730,140924),"BD":(16300,135840),"BN":(16470,195376),
 "CD":(13240,135580),"CN":(13410,147284),"DD":(10860,131616),"DN":(11030,132112),
 "FD":(11200,151828),"FN":(11370,155172),"GDJ":(14260,120576),"GNJ":(14430,120576),
 "HD":(13580,154172),"HN":(13750,142232),"ID":(15280,159992),"IN":(15450,167236),
 "JD":(11540,143836),"JN":(11710,136928),"MD":(12220,160720),"MDJ":(14600,161408),
 "MN":(12390,168724),"MNJ":(14770,161928),"OD":(15620,138304),"ON":(15790,137660),
 "PD":(12900,122712),"PN":(13070,123356),"RDJ":(14940,148748),"RNJ":(15110,145380),
 "SD":(11880,136916),"SN":(12050,140892),"TD":(13920,130204),"TN":(14090,134884),
 "VD":(15960,142028),"VN":(16130,148700)
}
resources={"DATSEL":(6000,215324),"DATSEL3":(6250,54948)}
resources.update({"GDC_"+name:extent for name,extent in GDC.items()})
changed={}
for name,(start,size) in resources.items():
    hits=[i for i in rows if start<=i<start+(size+2047)//2048]
    changed[name]={"modifiedLBAs":hits,"count":len(hits),
        "changedPayloadBytes":sum(sum(bool(v) for v in rows[k][24:2072]) for k in hits)}
data={
 "schemaVersion":1,"officialTest13Sha256":got,"test13RecordCount":count,
 "sourceSectorGuardsRequireCleanOriginal":True,"gamePatched":False,
 "readOnly":True,"styleTableXorMasks":style_masks,"resourcePatchMetadata":changed,
 "warning":"XOR masks alone do not reveal modified style values or runtime final GPU writer."
}
output=Path("diagnostics/v095-test25-official-test13-xor-metadata.json")
output.write_text(json.dumps(data,indent=2)+"\n",encoding="utf8")
print("PASS: official Test13 verified SHA",got)
print("Style masks modified slots:",[x["changedSlots"] for x in style_masks])
print("Changed resources:",{k:v["count"] for k,v in changed.items() if v["count"]})
