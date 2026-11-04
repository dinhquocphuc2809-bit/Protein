# Bilibili China: authenticated caption acceptance

Date: 2026-11-04. Browser: user's authorized Chrome, installed local Vocalm 0.6.1.
Only test-created tabs were navigated, paused, sought, switched or closed.
No translation, ASR or TTS jobs were invoked. Reports omit subtitle text,
cookies, credentials and signed caption URLs.

## Actual results after the correction

| Video | Part | Cues / language | Cue interval | Result |
| --- | --- | --- | --- | --- |
| BV1WqYV6cEwq | 1 | 299 / zh | 2.26-730.98s | Passed |
| BV1WqYV6cEwq | 2 | 253 / zh | 2.26-632.02s | Passed |
| BV1c11EBeEGC | 1 | 533 / zh | 1.02-1297.52s | Passed |
| BV1c11EBeEGC | 2 | 496 / zh | 1.4-1297.46s | Passed |
| BV1q1Puz7EUN | 1 | No reliable track | Unknown / bili_empty | Not caption-certified |

For both positive videos: initial/repeat hashes match, pause/seek retains the
transcript, actual part 1 -> 2 clicks produce different hashes, and returning to
part 1 restores its original hash. The native Vocalm button accepts real pointer
clicks and opens the quick menu. Every returned cue has valid numeric bounds
within the observed video duration; this is not a manual word-level timing audit.

Final 0.6.1 part-1 acquisition took 0.172 and 0.266 seconds; repeated
acquisition took 0.172 and 0.484 seconds. These are measured after the harness's
12-second page-settle wait, not total page load or dubbing preparation time.

Final release evidence: `research/bilicn-release-live.json` (both positive videos
and their part transitions pass). `research/bilicn-current-api-live.json` retains
the preceding post-fix mixed run. That runner exits nonzero because its sample
set deliberately retains the unaccepted negative video.
That failure is not hidden or reclassified as successful extraction.

## Defect discovered and corrected

On BV1q1Puz7EUN, the current /x/player/wbi/v2 endpoint returned no subtitles.
The old /x/player/v2 endpoint could return a changing list while echoing the
same video IDs. Before the fix, the extension accepted changing transcripts
for this 4053-second video. See `research/bilicn-additional-live.json` and
`research/bilicn-metadata-comparison.json`.

Removed the legacy request fallback and legacy metadata observation. Keep the
authenticated current endpoint, selected-part CID checks and native CC recovery.
The negative video now consistently stays unknown, allowing an explicit user
choice instead of silently spending ASR credits or translating unreliable text.

Regression checks: 97 JavaScript tests, 18 packaged Bilibili fixture cases and
19 shared caption acquisition cases passed. Fixture cases include ignored legacy
responses, current endpoint failure, session restrictions, current/wrong CID,
part changes, stale state, native CC restoration and navigation during retrieval.

## Reproduce

With the local package enabled in the authorized Chrome debugging session:

```powershell
.venv/Scripts/python.exe tools/priority_live.py --urls https://www.bilibili.com/video/BV1WqYV6cEwq/ https://www.bilibili.com/video/BV1c11EBeEGC/ --pointer --lifecycle --report bilicn-positive-rerun.json
```

The original video contains 81 parts; this report certifies only its first two.
Bangumi/paid lessons, other account regions, Firefox live Bilibili and the full
translation/dubbing chain are not certified by these acquisition/UI tests.
