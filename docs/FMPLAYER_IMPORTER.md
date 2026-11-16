# ISS26 – FMPlayer importer v1
Status: candidate research, NOT a game release. FMPlayer is an independent
secondary source. Confirm the site's terms and permission before automated
access; a public profile alone is not permission for bulk downloading.

## Inputs
- `data/fm26/fifa_wc2026_enriched_v9.csv`: 1248 tournament draft rows.
- `data/fm26/fmplayer_profile_queue_v1.csv`: priority queue, 872 existing UID
  candidates, 376 without UID, 440 with no converted attributes.
- `data/fm26/fmplayer_manifest_v1.csv`: one previously observed profile URL.
- `data/fm26/fmplayer_manifest_candidates_v1.csv`: 872 candidate URLs, 871
  generated from the URL pattern, NOT verified links. A wrong slug or UID can
  fail validation; review the rejected CSV. Resolve remaining 376 identities
  independently before adding links.
- `tools/build_fmplayer_manifest.py` regenerates candidate manifests from the queue.

## Offline mode (default, no game installation)
Python 3.10+. Save authorized public profile text/HTML under
`work/fmplayer/cache/<UID>.txt` or `<UID>.html`.
Run from repository root:

```powershell
python tools/import_fmplayer_profiles.py --roster data/fm26/fifa_wc2026_enriched_v9.csv --manifest data/fm26/fmplayer_manifest_v1.csv --cache work/fmplayer/cache --out work/fmplayer/result
python -m unittest discover -s tests -p test_import_fmplayer_profiles.py -v
```

## Live mode (only with site permission)
Confirm the website allows this specific automated use before invoking.
Robots access is checked and failure blocks live imports.
```powershell
python tools/import_fmplayer_profiles.py --roster data/fm26/fifa_wc2026_enriched_v9.csv --manifest data/fm26/fmplayer_manifest_candidates_v1.csv --cache work/fmplayer/cache --out work/fmplayer/result --live --permission-confirmed --limit 20 --delay 5
```
One sequential request stream; the delay is at least five seconds or the
published crawl delay, whichever is greater. No bypass of restrictions.
Authorization/rate-limit/service-unavailable errors halt the batch. Cached
profiles allow a later rerun without fetching them again. Output tables are
reconstructed from the manifest and cache on each run.

## Output
- `fmplayer_candidates.csv`: separate normalized attributes, raw profile source
  URL and SHA-256, profile metadata, 15 ISS values where calculable.
- `fmplayer_rejected.csv`: reasons for unresolved profiles.
- `fmplayer_report.json`: progress and completeness.
- No original roster, original disc or patch is changed.

The site explicitly describes the 10–200 scale; only exact multiples of 10
within that interval are converted. CA/PA and foot strength are not divided.
Missing components stay blank. UID/name/nationality/keeper status checks
produce candidate matches, not DOB-verified identities; nationality may
legitimately differ for dual nationals and must then be manually reviewed.
Position and metadata availability varies. The 12–19 ISS scale retains the
existing project mapping. No promotion into the main database until review.
The FIFA roster itself is still a manual draft.

## Implementation verification status
The code and 8 synthetic regression tests are committed. They have not been
executed end-to-end as of this commit. Direct HTTPS access in the working
container failed DNS resolution, and robots.txt was not obtainable through the
web search surface. Therefore no batch network import was performed.
