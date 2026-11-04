# Five-platform acceptance

User scope, 2026-11-04 (Asia/Bangkok): prioritize YouTube, Udemy, Douyin,
Bilibili China and Bilibili international. Keep every other existing integration.
The earlier 52-site acceptance effort is deferred, not removed.

## What the evidence establishes

Live tests use the installed local Vocalm MV3 package in authorized Chrome.
They measure existing caption acquisition, identity, timing, repeated retrieval,
native player controls and quick-menu opening. Lifecycle runs also pause/seek and
click another Bilibili international episode. No Dubbing action or paid
ASR/translation/TTS job is invoked. These are sample-specific acquisition/UI
results, not a claim that all videos, variants or the full dubbing chain passed.

| Platform | Actual sample | Evidence | Remaining |
| --- | --- | --- | --- |
| YouTube | 3BndvjrGwyE: 595 English cues, 0.08-1379.48s of 1381.201s | `research/priority-youtube-douyin-live.json`; stable repeat and quick menu | Additional videos, Shorts/embed and full dubbing integration are separate gates |
| Udemy | CCNA 9538164: 72 en-US cues; 7868552: 58 en-US cues | `research/priority-udemy-ugc-live.json`; stable repeat, pause/seek, quick menu | Other courses/languages and in-page lecture switching need additional samples |
| Bilibili international | Season 37976 episode 10344255: 279 English cues; 10344397: 371 | `research/priority-biliintl-live.json`, `research/priority-biliintl-lifecycle.json`; correct in-page episode switch, pause/seek and quick menu | UGC 4800774585457664 returns no complete track; do not certify UGC captions from episode tests |
| Bilibili China | BV1WqYV6cEwq parts 1/2: 299/253 Chinese cues; BV1c11EBeEGC parts 1/2: 533/496 | `research/bilicn-current-api-live.json`: authenticated captions, forward/back part clicks, seek, repeat, pointer menu | BV1q1Puz7EUN has no reliable acquired track; other parts, PGC/PUGV and full dubbing remain separate gates |
| Douyin | 6961737553342991651: video plays, native button and quick menu present | `research/priority-youtube-douyin-live.json`: zero cues | Actual metadata has no caption descriptors or interaction stickers; need a separate CC track sample to validate successful extraction |

`research/priority-final-live.json` records a stricter pointer/lifecycle rerun
separately, including earlier failed actions. The follow-up reports
`research/priority-pointer-live.json`, `research/priority-douyin-bilicn-final.json`
and `research/priority-bilicn-session-final.json` supersede those UI failures.
Actual pointer clicks and quick-menu opening now pass on samples from all five
platforms. Successful captions are verified on YouTube, Udemy, Bilibili China
and international episodes. Earlier reports are retained for history. The China
session failures are superseded by `docs/BILIBILI_CN_ACCEPTANCE.md` and its new
authenticated reports; the unreliable legacy endpoint is now excluded.
An earlier Udemy redirect to login was resolved after the user logged in; it does
not override the later successful two-lecture result.

## Changes

- Bilibili international has its own route/API reader, separate from China.
  Season landing pages resolve the selected episode; video URLs use `aid`.
  Requests include the locale required by the observed live endpoint.
- Prefer official structured subtitle data, with ASS fallback. ASS preserves
  timing, commas and line breaks; formatting tags, drawings and comments are
  excluded from speech text.
- Douyin selects the active feed player, retains an exact aweme identity and
  rejects conflicting modal/DOM IDs. It reads matching observed metadata,
  embedded data or the same-origin detail endpoint. Caption-info tracks and
  explicitly millisecond-timed auto-caption utterances are supported.
- Failed acquisition stays uncertain and never silently authorizes paid ASR.
  HTTP failures and responses exceeding the 4 MiB cap are reported separately.
- Existing integrations, voice/BGM assets and progressive translation/TTS remain.
- Fixed a live Douyin UI defect: a generic selector had mounted the button inside
  VIDEO, where browsers hide fallback content. Mount on the actual XGPlayer/native
  controls; never treat VIDEO/AUDIO/IFRAME/OBJECT/EMBED as a control container.
  Sites without a usable native control container retain the floating launcher.
- Bilibili China no longer opens the subtitle menu after an explicit session
  restriction; this prevents a login-driven navigation in the middle of acquisition.
- Bilibili China no longer calls or observes legacy /x/player/v2. Live comparison
  showed inconsistent subtitle lists despite echoed matching IDs. Current WBI
  metadata and native CC recovery remain; unknown never authorizes automatic ASR.

## Reproducible checks

From the repository root:

```powershell
.venv/Scripts/python.exe tools/build_extension.py --local-assets
node --test tests/*.test.cjs
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe tools/platform_acceptance.py
.venv/Scripts/python.exe tools/player_mount_acceptance.py
.venv/Scripts/python.exe tools/bilibili_acceptance.py
.venv/Scripts/python.exe tools/multisite_acceptance.py
.venv/Scripts/python.exe tools/multisite_firefox.py
.venv/Scripts/python.exe tools/check_secrets.py
```

`tools/priority_live.py --urls <authorized sample URLs> --lifecycle --pointer
--report <new-name.json>` uses the current user-approved Chrome debugging endpoint.
It only navigates, seeks and closes tabs it creates, never existing user tabs.
The test requires the current unpacked extension enabled in that Chrome profile.
Reports omit subtitle text, cookies and signed resource URLs.

Fixture coverage includes exact/wrong IDs, season/episode/UGC routes, empty and
denied responses, navigation during a request, ASS-only tracks, Douyin active feed,
stale metadata and millisecond timing. These fixtures do not certify live sites.

Validated: 97 JavaScript tests, 61 Python tests, 145 packaged platform cases,
18 Bilibili China cases, 19 shared acquisition cases, 18 player-mount cases and
Firefox159 native/shadow/DASH/priority-reader checks. No successful Douyin caption
extraction is claimed yet. This Bilibili follow-up reran JS, Bilibili and shared
acquisition suites; other suite counts are retained from the preceding revision.
