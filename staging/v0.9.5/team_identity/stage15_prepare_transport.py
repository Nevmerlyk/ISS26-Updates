from pathlib import Path
import base64,hashlib,lzma,zlib,json
root=Path('/mnt/data/iss26_team_identity/stage15_results')
raw=zlib.decompress(base64.b64decode((root/'test10_test09_to_stage15_delta.zlib.b64').read_text()))
comp=lzma.compress(raw,preset=6)
b64=base64.b64encode(comp).decode()
chunks=[b64[i:i+22000] for i in range(0,len(b64),22000)]
for i,p in enumerate(chunks):
 (root/f'test10_graphical_names_delta.part{i+1:02d}.b64').write_text(p+'\n')
doc={'format':'ISS26M01 + LZMA + base64 parts','parts':len(chunks),'parts_chars':[len(x) for x in chunks],
 'full_lzma_sha256':hashlib.sha256(comp).hexdigest().upper(),
 'raw_sha256':hashlib.sha256(raw).hexdigest().upper(),
 'base_sha256':'FA5E3DC3702808E8ABC197C9BB27B0707A4D44575D765918911AD846738D71B2',
 'target_sha256':'9832FA77F1DF60A56683F9BEA2AB631580056039A864A7E830EF8BE61138926B'}
(root/'stage15_transport_report.json').write_text(json.dumps(doc,indent=2)+'\n')
print(json.dumps(doc,indent=2))
