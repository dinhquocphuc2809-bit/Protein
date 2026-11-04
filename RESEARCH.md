# Protein research ledger

Updated: 2026-11-05. Separate observed evidence, interpretation and unverified claims.

## Second Qwen live video: 7jb0q3Mo9Rg (2026-11-05)

- Requested sample: https://www.youtube.com/watch?v=7jb0q3Mo9Rg . Used signed
  production API, quality/auto -> vi, progressive=true, no supplied subtitles.
  Normalized audio duration read from the actual VPS WAV header:817.0173125s.
- Initial job aa1ae19ddba277da65bf1bd77cec29bd completed in312.047s with94 speech
  cues. Production usage contains Qwen start and34 consecutive chunk offsets
  0,24,...,792; no Deepgram. Account3 calls increased34 while accounts1/2 did not.
- Repeat5a492f060709b2fb127547f4b3af90b4 completed in2.265s using cache only.
  Source/translation IDs and full output SHA256 match. Output passes ordering,
  nonoverlap, nonempty text, unique IDs and audio-duration bounds; VPS spool=0.
- Last cue ends727.6s, although audio lasts817s. Investigated instead of assuming
  complete speech coverage from valid numeric timestamps. Downloaded via Tunelio
  to ignored local `.private/asr-second-video`; PCM samples show exact digital
  silence728.822438-815.549188s, with brief residual signals on either side.
- Separate Gemini3.5-flash-lite inline-audio audit on728s-end reports no speech.
  Its generic description says music throughout, which does not describe the
  measured long digital silence precisely; use PCM measurements for timing.
  The speech assessment is independent machine evidence, not manual listening,
  and does not establish word-level transcription accuracy. Gemini was a separate
  QA call, not a replacement for Qwen recognition in the production job.
- Evidence: `research/qwen-second-video-*.json`; scope and reproducer in
  `docs/QWEN_SECOND_VIDEO_ACCEPTANCE.md`. No further backend/GPU patch was needed.

## Qwen ASR incident: f6YA_OvKbhY (2026-11-05)

- Production failure: `Alignment produced invalid timestamps` during aligning,
  after 271.831 seconds. Terminal request payloads are scrubbed by maintenance;
  the original failed job no longer retains URL/request fields. The previous
  successful job retains this video's URL in its result and its usage confirms
  Deepgram (660.9649s recognized, 9.076s total). Do not infer the failed request's
  exact fields from that previous result.
- Reproduced with the supplied video audio obtained via Tunelio, Qwen3-ASR-1.7B
  on Modal account 1, automatic language detection. At the 576-second window,
  VAD region 7 word 19 had start=3.440/end=3.520 against duration=3.440 seconds.
  Old validation allowed only 50ms overrun, so this 80ms model boundary error
  failed the whole job. First 24 windows passed; reproduction records exact
  numeric diagnostics without speech text in `qwen-incident-reproduction.json`.
- Official Qwen source describes timestamps in seconds converted from discrete
  model units, and its fix_timestamp enforces monotonicity but does not constrain
  output to the supplied waveform duration. Qwen ForcedAligner supports 11
  languages; stable-ts remains the existing aligner for other languages.
  Sources and SHA256: `research/qwen-incident-sources.json`:
  https://github.com/QwenLM/Qwen3-ASR and https://github.com/jianfch/stable-ts .
- Correction: bounded 120ms edge tolerance with waveform clipping; zero-length
  tokens retain their text in an adjacent aligned interval. NaN, infinities,
  inversions, nonmonotonic or materially out-of-bounds output remains invalid.
  If Qwen's alignment fails these checks, stable-ts aligns the SAME Qwen text
  once; its output must pass the same validator. No Deepgram fallback exists.
- Performance defect: the least-call key selection rotated every 28-second
  transfer window across three GPU accounts. Added job-local affinity; invalid,
  depleted or cooling keys still fail over through existing classification.
  This avoids unnecessary account switching without keeping idle GPUs running.
- Added provider-start and per-Qwen-window usage events. Existing cache identity
  includes asr=fast/quality; regression tests verify no cross-mode reuse or hidden
  Qwen-to-Deepgram fallback. Account 4/client OmniVoice is unchanged.
- Actual fixed-worker tests: account 1 passes offsets 576/600/624/648; accounts
  2 and 3 each pass offset 576. All report model Qwen/Qwen3-ASR-1.7B, Chinese,
  valid timestamps, and no secondary realignment needed on those samples.
  Reports: `research/qwen-incident-fixed-account*.json`.
- End-to-end signed API verification is recorded independently in
  `research/qwen-incident-live.json`; correlate job IDs with production usage in
  `research/qwen-incident-production-evidence.json`. Final fresh request passed:
  28 Qwen windows,93 speech cues through660.8s,230.594 seconds including initial
  translation. No Deepgram usage. Repeat passed in2.281 seconds with cache-only
  usage and identical source, translation and output hashes. Account2 processed
  all28 windows (calls17->45); accounts1/3 counters unchanged. Spool returned to0.
  This verifies ASR plus first progressive translation, not TTS/audio playback.

## Authenticated Bilibili China follow-up (2026-11-04)

- User confirmed login. Installed Vocalm in that Chrome session acquires 299/253
  Chinese cues for BV1WqYV6cEwq parts 1/2 and 533/496 for BV1c11EBeEGC parts 1/2.
  Both videos pass actual part 1 -> 2 -> 1 clicks, transcript hash restoration,
  pause/seek, pointer click and quick-menu checks. No paid provider jobs invoked.
- Reference discovery used recommendation links and __INITIAL_STATE__.videoData
  on the supplied page. The original video has 81 parts; only parts 1/2 were
  certified here. `bilicn-discovered-samples.json` is discovery, not acceptance.
- Actual negative sample BV1q1Puz7EUN exposed an unreliable legacy fallback:
  /x/player/wbi/v2 consistently returned no tracks, while /x/player/v2 could
  echo the same aid/cid/bvid but return differing subtitle IDs or an empty list.
  Before correction, repeated acquisition alternated between unknown and
  transcripts ending at 15.38, 221.38 or 838.52 seconds of a 4053-second video.
  The evidence does not prove the content of those tracks belongs to this video.
  Removed both direct legacy fallback and legacy response interception. Do not
  equate echoed request IDs with reliable subtitle ownership on this endpoint.
- Current endpoint plus native CC recovery remain. The negative sample now
  consistently returns unknown/bili_empty; this is not proof that every possible
  player language/region has no captions. It is not a successful caption sample.
- Evidence: `research/bilicn-authenticated-live.json` (initial success),
  `research/bilicn-additional-live.json` (failure retained),
  `research/bilicn-current-api-live.json` (post-fix),
  `research/bilicn-metadata-comparison.json` (sanitized endpoint comparison),
  `research/bilicn-release-live.json` (final 0.6.1 positive lifecycle rerun).
- Timing in live reports measures acquisition AFTER a 12-second page-settle wait;
  it is not browser navigation time, translation latency or dubbing latency.
- Regression: 97 JS tests; 18 packaged Bilibili cases including current-endpoint
  failure and ignored legacy observations; 19 shared acquisition cases. No
  production backend, credentials or other platform integrations were changed.

## Five-platform follow-up (2026-11-04)

The user reduced priority to YouTube/Udemy/Douyin/Bilibili China/international.
Broader integrations remain. Acceptance: `docs/PRIORITY_SITE_ACCEPTANCE.md`.

- Static local reference audit: content.js class Qwe (DouyinPlayer) inherits Eu
  (UniversalDubbingPlayer). Qwe resolves modal/path/player aweme IDs and selects
  the visible active feed video. Eu checks HLS/native/platform captions and may
  query its own backend cache. This is not evidence that Douyin always publishes
  downloadable captions. No bilibili.tv/biliintl entries were found in supplied
  content.js, injectScript.js or background.js. Full source SHA256 values:
  content.js `709fdd1c1edf17f8393a6b566b7c479e5b13557c8c45dfd9a712fc1297f21fc4`;
  injectScript.js `e8cff06bfd1ad82965f687567e14bb06ae8d2627818a356aee3fdc5e82258e83`;
  background.js `c530d6519b93f2d40c2ad4f4f9352cab651e85c17a918d3255192306f3abb070`.
- Primary international site: https://www.bilibili.tv/en/play/37976 . Official
  asset https://p.bstarstatic.com/fe-static/bstar-web-new/client/assets/useError-f85f952e.js
  (SHA256 `7d18a4623c67894acec1e8472c1ea0ef5c7c2bc3060e0b70cef9e58e5fb6640d`)
  calls `/intl/gateway/web/v2/subtitle` on api.bilibili.tv. `video_subtitle` rows
  expose lang_key, srt.url and optional ass.url; legacy rows use subtitles[].url.
  The field named srt.url can contain JSON with body[].from/to/content, not SRT.
  Direct live request without s_locale failed; en_US (plus platform=web) returned
  code0 and five languages. Keep official bstarstatic.com caption URLs only.
- The official player asset biliintl-player-dfb25af7.js has SHA256
  `bc2d8201b531727c42629775ea63e5572ed08bc7f4e48a0d9d2f51d05c23470b`.
  Observed native control parent: player-mobile-control-bar-right. Season pages
  expose the current episode in a.ep-item--active; season ID is not episode ID.
  Fresh live tests verified two distinct transcripts and SPA episode switching.
- Secondary schema reference (read, not executed):
  https://raw.githubusercontent.com/yt-dlp/yt-dlp/master/yt_dlp/extractor/tiktok.py
  SHA256 `1bd19075b06c50e84d186086679edca4a7f87388c6b639099689b20940a0ab55`.
  Douyin detail uses aweme_id. Shared parsing reads video.cla_info.caption_infos
  and interaction_stickers[].auto_video_caption_info.auto_captions[].url.url_list.
  Auto-caption utterances explicitly use milliseconds. Implementation is original
  browser-session code; no yt-dlp invocation/download or signature bypass.
- Public Douyin sample 6961737553342991651 plays for19.735011s and exposes zero
  native tracks. The site's own successful detail response has no video caption
  fields and no interaction stickers. Vocalm mounts its button/menu but cannot
  claim captions from this sample; unsigned detail request returns403. CC sample
  remains requested. Search connector was unavailable; source assets and actual
  website/API observations above were read directly.
- Current Udemy session initially redirected to login; after user login two
  lessons passed. Keep both attempts, with chronology. Initial YouTube run hit an
  ad and failed; after waiting for the real video,595cues were acquired. No ASR
  or GPU job was used to substitute for platform-caption extraction.
- Pointer checks exposed a real Douyin defect: registry controls="video" was
  interpreted as a mountable container. The inserted button had a zero-sized
  bounding box inside VIDEO. Observed actual control containers are
  xg-right-grid.xg-right-grid and douyin-player-controls-right. Corrected ownership
  mounting and media-element exclusion; pointer click and screenshot then passed.
  Current Douyin window.player owns the selected video, curDefinition.vid matches
  aweme, plugins.texttrack exists, config.texttrack has style only on this sample.
  Do not infer that a plugin's presence means a downloadable subtitle track exists.
- Bilibili China: session-restricted subtitle menu interaction triggered a page
  navigation and destroyed the acquisition context. Skip menu activation on
  bili_session. Final live repeated lookup stays on the page and native pointer
  menu works. This earlier session limitation is superseded by the authenticated
  follow-up above.

## Local observations

### Full platform parity and authorized Udemy session (2026-11-04)

- Reference AST audit now resolves 78 handler families across 159 routes. Extracted
  class/helper excerpts are private, never executed or shipped. Detailed status:
  `docs/FULL_SITE_PARITY.md`; route registration is not live certification.
- New reader evidence: `tests/platform-captions.test.cjs` (19 unit checks),
  `research/platform-acceptance.json` (22 actual MV3 mechanism fixtures).
- Live Udemy cookie-import attempts: course HTML 200 in headed Chromium/Chrome,
  but course/context APIs 403 and no video. Owner confirms ordinary Chrome plays.
  This does not establish expired credentials or absent captions.
- Official Chrome article read:
  https://developer.chrome.com/blog/chrome-devtools-mcp-debug-your-browser-session
  Chrome >=144 supports user-enabled remote debugging and browser consent for
  connection. Owner supplied enabled endpoint screenshot. `/json/version` and
  `/json/list` return 404; local DevToolsActivePort WebSocket connects successfully.
- Attached live lesson 9538164: 335.181356 seconds, paused at 85.538092, no native
  TextTracks; initial current-source acquisition was unknown. Read-only metadata
  GET in the same session returns 33 caption tracks. Course locale is en_US;
  selecting the first descriptor would wrongly choose German.
- Fixed current course/lecture lookup, asset validation and original-language
  priority. Installed package in authorized Chrome; final two live runs retrieve
  identical 72-cue English transcripts in 1.187s/1.141s, ending at 334.58s. Button
  is present and playback position preserved. `research/udemy-attached-live.json`
  includes exact package source hash. Other sites are not certified by this result.
- Chrome protocol definitions checked for Extensions.getExtensions/loadUnpacked:
  https://raw.githubusercontent.com/ChromeDevTools/devtools-protocol/master/json/browser_protocol.json
- Public live TED Ken Robinson sample redirects to slug prefixed sir_. Current
  Next videoData.videoPlayerData is an object, not the reference's playerData JSON
  string. resources.hls.metadata has subtitles[].webvtt; nativeLanguage en orders
  the English track before Portuguese. #ad-container owns extra video elements;
  excluding these on TED prevents false multiple-player ambiguity and restores
  the native control mount. Final actual package reads 427 cues and mounts button.
- https://www.feynmanlectures.caltech.edu/fml.html returned HTTP 403; no live pass.

### Bilibili and native player integration (2026-11-04, Vocalm 0.6.0)

Detailed source comparison, plan and evidence: `docs/MULTISITE_REVISION.md`.
Reference catalog: 159 routes, 158 string player-control selectors. The reference
Bilibili service actively fetches authenticated aid/cid metadata and has a
CC-selection/resource-discovery fallback with restoration; Vocalm previously
had only passive interception and incomplete initial-state lookup.

Live root cause: the supplied Bilibili URL redirects to `/en/video/...` in the
isolated browser. The old route matcher and reference catalog omit this prefix.
Before correction: no Bilibili rule or native button. After correction: Bilibili
rule selected, native button mounted, `bili_session` from anonymous acquisition.
This does not verify the owner's authenticated captions. Evidence:
`research/bilibili-live.json`, `research/bilibili-acceptance.json` and
`research/player-mount-acceptance.json`. Only test-only cookies are used in fixtures.

Official browser references fetched on 2026-11-04 (HTTP 200):
- https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
  (page/isolated execution contexts; keep page session work in MAIN).
- https://developer.mozilla.org/en-US/docs/Web/API/Request/credentials
  (`include` sends browser credentials even across origins; it does not bypass CORS).
- https://developer.mozilla.org/en-US/docs/Web/API/Element/shadowRoot
  (open shadow roots can be traversed; closed roots return null).
Retrieval ledger: `research/multisite-revision-sources.json`.
Bilibili endpoints are internal web-player APIs observed in the supplied reference
and real requests, not a stable public API contract. PGC/PUGV-specific API parity,
closed-shadow players and each of the 159 individual live routes remain unverified.

### Voice picker catalog audit (2026-11-04)

Neko `background.js` version-2 catalog explicitly marks six male voices (Dang Khoa,
Quang Vinh, Tuan Anh, Minh Quan, Gia Bao, Hoang Long) and six female voices (Khanh Vy,
Lan Anh, Ngoc Linh, Thanh Truc, Bao Ngoc, Ha My). No Dang Quang name or WAV exists in
the supplied source. All 12 base WAV hashes match previously imported files. The
84 references are 12 base voices plus 72 variants; they are not 84 different people.
The original importer discarded gender metadata; it now preserves gender/baseId
for explicit grouping without inferring gender from names. Audio IDs/cache keys
and reference transcripts stay unchanged. Source assets remain local/ignored.

Chrome's real packaged audio decoder read all 12 base samples (5.54-7.55 seconds).
Actual popup testing selected/persisted each base ID; variants and YouTube menu
selection also passed. Firefox narrow embedded settings persisted selection across
reload. These checks verify inclusion/selection/decoding, not a new TTS quality study.


### Neko HAR/source latency implementation (2026-11-04)

Detailed source anchors, official links, timing observations and choices are in
`docs/TTS_LATENCY.md`. Sanitized all-entry HAR aggregates are reproducible with
`tools/analyze_neko_latency.py`. It records 518 one-item/voice-id requests, 16 separate
voice uploads, 12 translation batches (8/23/24 items), summaries and punctuation flags.
No source text, credentials, response audio or signed URL is exported.

Implemented one-time references, bounded long polling and CPU request concurrency.
Experimented with CPU-load/GPU-transfer snapshots, then removed them because actual
restore improvement was unproven (one post-retirement call took 35.718s). Fresh Modal concurrency, FunctionCall, snapshot
and region docs were read directly (web connector unavailable). Same-sentence final
warm HTTP receipt improved from 9.156s to 2.875s; GPU inference ~1.4s. Only compare the
same input and separate reference setup, snapshot creation and actual restore.
The 45-second idle experiment retained one GPU container; elapsed idle time is not
proof of scale-down. Neko concurrency/HAR overlap does not justify unsafely threading
the shared model; generation remains serialized. No Kaggle code found in this bundle.

### Progressive dubbing follow-up (2026-11-03/04)

- Follow-up timing probe: `tools/tts_latency_probe.py` and
  `research/tts-latency-breakdown.json` separate submission, polling, receipt,
  FFmpeg decoding and local DSP. Same text/reference gives 26.281s then 9.156s
  to audio receipt; submission alone costs 8.750s then 6.562s. These observations
  identify a slow submission phase but do not separate network upload from server
  storage/spawn calls. There is no server-side GPU phase instrumentation yet.
- Reference HAR already records Neko TTS p50 6.463s/p95 10.724s (see
  `docs/REFERENCE_ANALYSIS.md`). This explains the importance of lookahead but is
  not a fair controlled performance comparison or an excuse for Veloa latency.

- Re-read extracted Neko `content-scripts/content.js:8470-8590` (sentence punctuation,
  abbreviations, comma splits) and `:25575-25680` (current-region priority and seeking).
  These are source observations, not proof of its live quality or performance.
- Owner retained transcript uses overlapping YouTube display lifetimes. Treating
  display ends as speech slots explains incorrect timing; new speech ownership ends
  at next-cue start and rejoins dangling phrases. 595 cues become 254 bounded units.
- Old mixer clipped audio using video lateness as an offset, even on normal startup.
  New normal playback starts at zero and finishes current speech before advancing.
- A native video's `pause` can precede `ended`; do not cut its current speech tail.
  Regression includes that event order, stalls and rate changes.
- Live evidence: `research/progressive-live.json` (real translation/OmniVoice),
  `research/progressive-speech-check.json` (two short Nova-3 DSP quality checks),
  `research/progressive-acceptance.json` and `progressive-startup-seek.json` (explicit
  provider fixtures in actual Chromium). Natural/fitted recognition was identical,
  67 words; this is not subjective listening certification.
- First measured TTS round trip ~30s, later ~6.5-7.5s. Progressive scheduling avoids
  whole-video preparation; it cannot guarantee uninterrupted playback if throughput
  falls below speech consumption. The video holds without truncating spoken words.
- Current limits, complete test matrix and sample locations:
  `docs/PROGRESSIVE_DUBBING.md`, `docs/TEST_PLAN.md`, `CHECKPOINT.md`.

- The requested GitHub remote was reachable and empty when cloned.
- Neko Dub: manifest v3, version 1.2.3, 145 files, 31,869,577 bytes.
- YouTube Dubbing: manifest v3, version 4.3.19, 135 files, 33,223,053 bytes.
- Both packages contain bundled JavaScript rather than original development repositories.
- Supplied files have 120 nonempty Tunelio lines, 2 Apify, 5 Deepgram,
  1 DeepSeek, 1 Gemini and 4 Modal token pairs. Counts are not validity checks.
- Neko declares Colab overlay and Modal deployment overlay scripts; exact trust and
  deployment flow is still under investigation.
- YouTube Dubbing requests all-site access and injects into all frames. This is
  evidence of integration breadth, not proof every site currently works.

## Research access

The available web-search connector returned `not available to the model` on first
use. Continue using direct HTTPS retrieval of primary sources and public pages.
Record inaccessible sources explicitly; do not replace missing evidence with guesses.

## Source register

| Source | Purpose | Status |
| --- | --- | --- |
| Local Neko Dub | Modal/Colab/Kaggle, audio, presets, BGM | Inventory complete; tracing pending |
| Local YouTube Dubbing | Bilingual overlays and site adapters | Inventory complete; tracing pending |
| Local nekodub.har | Observed request/response protocol | Pending sanitized analysis |
| https://voz.vn/t/extension-long-tieng-youtube-nay-qua-nguy-hiem-de-minh-public.1251511/ | User failures and author fixes | Pending retrieval |
| https://github.com/dinhquocphuc2809-bit/Protein | Delivery repository | Cloned, empty remote |

## Open verification questions

- Do requested Gemini/DeepSeek model identifiers exist in the supplied accounts?
- What official Modal deployment interface can safely be invoked from a browser?
- Which Qwen forced aligner languages are supported and how is Vietnamese handled?
- Are preset/BGM redistribution terms present in the supplied packages?
- Can Oracle SSH already be reached through Tailscale without changing access?
- Which provider endpoints expose balances, and which only expose usage/quota errors?

## Verified results and decisions

See `docs/REFERENCE_ANALYSIS.md` for source/notebook/HAR/forum findings, and
`research/source-fetches.json` for direct HTTPS retrieval status. Apple HIG text was
read from Apple's public tutorial JSON because HTML pages are JavaScript shells.

- 35/35 Voz pages fetched, 691 posts; no Kaggle module found in 58 indexed JS files.
- Two public Neko notebooks retrieved from the IDs in its source and inspected.
- HAR carries complete base64 Ogg clips over HTTP; no recorded WebSocket transport.
- Modal deployment in Neko runs Python inside Colab; the browser reads progress.
- 120 Tunelio keys authenticate; 119 have positive credits; aggregate 11,790 credits
  at check time. Recheck before spending; these are not lifetime guarantees.
- All five Deepgram keys authenticate and expose balances. Apify exposes usage limits
  and current spend. DeepSeek exposes account balance. Gemini model-list success does
  not establish prepaid balance. Modal metered usage does not prove remaining credit.
- Model API confirms `gemini-3.5-flash-lite`, `gemini-3.8-flash`, `deepseek-flash`.
- Oracle: aarch64, 4 CPUs, about 24 GB RAM; root total 206,900,281,344 bytes;
  initial used about 7.52 GB; Tailscale running; ffmpeg installed; Docker absent.
- SSH connection is already through Tailscale, but sshd listens on wildcard addresses.
- Qwen3 ForcedAligner excludes Vietnamese. WhisperX's default Vietnamese CTC model
  is CC-BY-NC-4.0: do not silently use it for a commercial release. Evaluate stable-ts
  alignment with Whisper-small instead (https://github.com/jianfch/stable-ts).
- PyPI dependencies conflict: qwen-asr 0.0.6 pins Transformers 4.57.6; OmniVoice 0.2.1
  requires >=5.3.0. Separate images are required.
- Modal API tokens (ak/as) and proxy tokens (wk/ws) are different credential types.
  Proxy authentication must reject unauthorized requests before starting GPU compute.
- Firefox MV3 does not support background.service_worker according to current MDN;
  build a background.scripts variant. Chrome worker idle/fetch limits require durable jobs.
- Auvirel: no Chrome Store result; Firefox fuzzy search returned unrelated NaviReload.
  Global name uniqueness is not proven; Google text search returned a JS redirect shell.

## Primary sources used

- https://github.com/QwenLM/Qwen3-ASR (ASR and forced alignment APIs/languages)
- https://github.com/k2-fsa/OmniVoice (clone API, prompt reuse, sample quality, duration)
- https://github.com/jianfch/stable-ts (text/audio alignment)
- https://github.com/snakers4/silero-vad (speech chunk detection)
- https://tunelio.dev (endpoint costs, signed media URL, supported formats)
- https://docs.apify.com/api/v2 and https://docs.apify.com/api/v2/act-runs-post
- https://developers.deepgram.com/docs/pre-recorded-audio
- https://ai.google.dev/api/models and authenticated Google model listing
- https://api-docs.deepseek.com/api/list-models and authenticated model listing
- https://modal.com/docs/guide/scale
- https://modal.com/docs/guide/memory-snapshot
- https://modal.com/docs/guide/webhook-proxy-auth
- https://modal.com/docs/guide/budgets
- https://modal.com/docs/reference/cli/billing
- https://github.com/modal-labs/modal-client/tree/main/js (server-side SDK requirements)
- https://research.google.com/colaboratory/faq.html
- https://tailscale.com/kb/1223/funnel
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle
- https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background
- https://developer.apple.com/design/human-interface-guidelines/motion
- https://developer.apple.com/design/human-interface-guidelines/materials

## Research limits

### Integration findings recorded after real deployment

- Official Gemini live calls accept `responseJsonSchema` and `responseSchema` for the
  summary object; adding minItems=1/maxItems=100 yielded HTTP 400 with both. Keep the
  wire schema simple and validate cardinality/timestamps in application code.
- Without schema, a real summary call returned a bare array despite the requested
  object wrapper. This is a confirmed response-shape failure, not an assumed provider issue.
- FastAPI Request annotations inside a Modal ASGI factory must be resolvable at route
  registration. Postponed annotations with a locally imported Request caused HTTP 422
  expecting a query parameter named request; removing postponed evaluation fixed it.
- `requests` POST transport to Modal hit TLS EOF on this Windows environment while
  `httpx` succeeded with certificate verification enabled. Do not disable TLS verification.
- Modal proxy tokens reject missing authentication with HTTP 401 before GPU invocation.
  Durable Dict idempotency was tested by repeating a real synthesis POST.
- Firefox geckodriver 0.37.1 documents `--allow-system-access` as a service flag for
  privileged extension-page automation. Browser capability flag is rejected.
- Cloudflared official 2026.10.7 ARM64 binary was SHA-256 verified against GitHub release
  asset digest. Quick Tunnel was used only for acceptance and stopped after Funnel setup.
- Owner enabled Funnel and confirmed custom Modal Spend limit $0 on all four accounts.
  These two owner confirmations are distinct from read-only API evidence.
- Native bridge actually deployed account-4 TTS using the extension -> native host ->
  detached Python SDK process and returned a working proxy configuration.
- Chromium acceptance additionally verified no new translation POST on voice change,
  no synthesis POST on replay, and no synthesis POST when switching back to a cached voice.
- Firefox 159 loaded the actual MV3 background-scripts package and completed live
  translation plus dubbed playback. No service-worker manifest was used for Firefox.
- Live YouTube/TikTok media acquisition and production HQ ASR results are preserved
  in research/live-youtube.json, live-apify.json and live-quality-asr.json.


Indexed/scanned code is distinguished from deeply reviewed operational paths. Provider
read-only success is not a synthesis/download test. Actor metadata existence is not
per-site compatibility. Forum images were not visually examined; do not infer image-only
error contents. No specific RAM/CORS/CSP fix was confirmed from the retrieved thread text.

## Veloa design revision (2026-11-03)

- Revisited Neko Dub popup entry/assets and Youtube Dubbing popup, integrated settings,
  and `youtube-bilingual-sidebar.js`; comparison is in `docs/DESIGN_REVISION.md`.
- Apple official layout and motion Markdown documentation retrieved successfully:
  https://developer.apple.com/design/human-interface-guidelines/layout.md and
  https://developer.apple.com/design/human-interface-guidelines/motion.md.
  Applied progressive disclosure, aligned groups, brief transitions and reduced motion.
- Chrome Web Store `https://chromewebstore.google.com/search/Veloa` returned no results.
  Mozilla HTML search returned a client challenge. Its public v5 addons search API
  returned fuzzy results; no exact Veloa name on the inspected first page. No global
  uniqueness or trademark claim is made.
- Chrome's actual `action.openPopup()` target can be tested through CDP target attachment;
  it is not necessarily included in Playwright's ordinary `context.pages` list.
- Long-distance smooth scrolling through estimated row heights can miss the target
  after measurement. Use immediate distant jumps plus viewport anchoring during height
  correction; verified with 5,000 cues and bounded rendered rows.
- A WAV route used in the browser fixture must support Range/206 to validate seeking
  accurately. Fixture transport was corrected before asserting seek success.
- UI screenshots and test profiles remain private. Passed interaction evidence is in
  `research/ui-acceptance.json`; this clearly distinguishes the YouTube DOM fixture
  from the live backend subtitle calls.
- Real YouTube now serves a `fixed-default-panels` variant in this browser profile.
  Its legacy secondary column exists but is initially hidden; a straightforward
  reference-selector match silently mounts invisible UI. Added a reserved right dock
  for this variant and tested against the real page. Native player side control opens
  comments in this variant, rather than theater; respect `fixed-panel-expanded` too.
  Evidence: `research/ui-youtube-live.json`; screenshot `.private/ui-qa/youtube-live-mount.png`.

## Caption acquisition incident (2026-11-03)

- Affected title: "$2 Buffet vs $75 Buffet in China", video `3BndvjrGwyE`, duration
  1,381 seconds. Real player metadata advertises 21 tracks including English `a.en`;
  first advertised track is Arabic, so picking index zero is incorrect here.
- Original implementation fetched signed `baseUrl` from the extension background with
  credentials omitted. Empty HTTP 200 failed JSON parsing. `pageCaptions().catch(() => null)`
  then converted this download failure into an absence signal, causing paid ASR.
- Revisited supplied `Neko Dub/caption-capture.js`: it captures native player fetch/XHR
  because bare caption-track URLs may omit session parameters appended by the player.
  Revisited `Youtube Dubbing/content-scripts/youtube-caption-probe.js`: it checks
  matching player/initial-player metadata. Applied these mechanisms with independent,
  bounded code, current-video checks and no transfer of cookies/session URLs to VPS.
- New entry scripts run at document_start in MAIN to observe requests before a user
  clicks Prepare. On-demand injection handles already-open pages too. Native transcript
  responses are cached; a fallback uses the page's own getTranscript command and context.
  Native CC selection is restored after capture. Cached payloads omit signed URLs/tokens.
- Both isolated headless and headed Chromium received empty timedtext responses on
  this video, including the player's own requests. Direct native-context transcript
  request returned HTTP 400 failedPrecondition. This is an observed environment limit,
  not proof that the owner's signed-in session cannot display/download subtitles.
- `research/caption-acceptance.json`: explicit fixture success for direct JSON3,
  initial metadata fallback, native fetch/XHR, XML, cached captions, transcript response,
  unknown/download-failed refusal, and confirmed absence allowing ASR.
- `research/caption-live.json`: real affected page has 21 tracks; clear error and zero
  backend job requests. Successful real extraction of this video remains unverified.

## Multisite subtitle research and implementation (2026-11-03)

- Full static AST analysis resolves 159 routing rules in Youtube Dubbing 4.3.19,
  including seven factory-generated ThoughtIndustries/Memberspot entries. Source
  SHA-256 and sanitized factual routes are in `research/multisite-inventory.json`.
  Raw reference executable code, bundled credentials and copyrighted UI are not copied.
- Detailed source anchors, architecture/checklist and limitations are in
  `docs/MULTISITE_ANALYSIS.md`. `docs/MULTISITE_COVERAGE.md` distinguishes shared
  engines, schema-specific adapters, and routes without bespoke API implementations.
- Official documentation retrieved successfully:
  https://developer.chrome.com/docs/extensions/develop/concepts/content-scripts
  (MAIN vs ISOLATED worlds, document_start and all_frames),
  https://developer.mozilla.org/en-US/docs/Web/API/TextTrack/mode (disabled/hidden/showing
  and cue loading), https://www.rfc-editor.org/rfc/rfc8216.txt (WebVTT subtitle rendition
  playlists, X-TIMESTAMP-MAP, 33-bit MPEGTS wrap, discontinuities).
- Official Wistia https://docs.wistia.com/docs/javascript-player-api and JWPlayer
  https://docs.jwplayer.com/players/reference/getplaylistitem returned HTTP 403 in this
  environment. SDK compatibility here is grounded in supplied source analysis and
  explicit fixtures; do not describe those pages as successfully read.
- Reference patterns are not permanent: the tested Ahrefs lesson now embeds YouTube
  nocookie, although its reference rule describes Wistia. Generic frame detection
  routes it to the dedicated YouTube reader. That isolated live embed returned
  `unknown`, not proof of absent captions; no paid job was submitted.
- Live Apple WWDC2024/10140: 360 English cues, 7.149 to 1241.297 seconds, acquired
  from complete HLS subtitles. Preserve the video's data-id across URL-to-blob setup;
  otherwise the initial manifest cache is invalidated. Public CDN requests first
  omit credentials; authenticated same-origin APIs keep browser credentials.
- Live MDN caption-player example: 14 English cues, 0 to 119.5 seconds, from native
  tracks. Reports: `research/multisite-live.json`; these are real pages, not fixtures.
- Chromium can retain an old extension service worker in a reused QA profile after
  rebuilding files with the same version. Caption regression tools now use fresh
  temporary profiles and clean them after closing the browser. User updates require
  Reload extension plus reload video page to install current early hooks.
- SPA sender.url may reflect the original document URL. Validate origin at the
  background boundary and validate the current URL/media again inside the actual
  frame. Tests cover stale-response rejection and fresh captions after pushState.
- Source acquisition stays in the browser. Only sanitized cues/language are sent
  to the VPS; no additional video/subtitle disk store or provider call is introduced.

## Translation coverage incident (2026-11-03)

The owner screenshot shows a backend-generated coverage failure, not a network
gateway outage. Production jobs confirm `incomplete_cue_coverage` followed by
`gemini: invalid_json`. The second job included 595 supplied English cues, so native
subtitle discovery succeeded on that attempt. Normal terminal-job retention purged
the payload before a private copy could be retained. Raw model output was not logged;
the exact omission/reordering/JSON shape of the first failure cannot be reconstructed.

Code inspection found translation did not pass the structured-output schema already
supported by the LLM client. It compared results in positional order and retried the
whole batch once. JSON parsing inside KeyPool.run treated a model formatting failure
like an unhealthy API credential, preventing immediate recovery when only one key
exists. Parsing now happens after the successful authenticated provider operation.
Transport/status failures still use the original key rotation policy.

Translation now validates original integer IDs, rejects duplicate/foreign/empty
items, maps valid results back to source order, repairs only missing IDs and splits
persistently invalid batches. The response schema avoids previously rejected Gemini
minItems/maxItems constraints. There is a maximum of ten inference attempts per
12-cue/6,000-character group, with cancellation checks between calls. Valid partial
results use the existing ticket/model/source-scoped translation cache plus a versioned
batch suffix. Existing total cache quota, TTL, eviction and free-space reserve apply.

Nine dedicated recovery tests cover schema wiring, partial/reordered answers,
duplicate/wrong IDs, bounded splitting, malformed JSON with a healthy key, size
limits, cancellation, persistent job retries and ticket cache scope. 43 total Python
tests pass. Real Gemini and deployed HTTPS checks use 12 explicitly labelled cues,
not the owner's complete 595-cue transcript; successful complete replay of that
video remains unverified. Reports: `research/translation-recovery.json` and
`research/translation-recovery-production.json`. No ASR/TTS calls were used.
# Vocalm UI and YouTube lifecycle research (2026-11-04)

Sources inspected for this revision:

- Local Neko `content-scripts/content.js`: `mu` checks `.html5-video-player`
  `ad-showing`, `.ytp-ad-player-overlay` and `.ytp-ad-text`; `yf` observes ad state.
- Local Youtube Dubbing `content-scripts/content.js`: `createWatchAdsObservable`
  watches player class changes until `ad-showing` disappears. Reference-only;
  Vocalm retains its own progressive single-voice implementation.
- https://developer.apple.com/design/human-interface-guidelines/color
  (official DocC JSON read): consistent color roles, legibility against materials,
  redundant state labels, increased contrast and light/dark context checks.
- https://developer.apple.com/design/human-interface-guidelines/motion
  (official DocC JSON read): purposeful, brief motion; optional/reduced motion;
  let users cancel without waiting for animation. Applied to discrete stage-driven
  shoots and gentle leaf movement, with text/icons conveying the same state.
- https://developer.chrome.com/docs/extensions/reference/api/action
  retrieved successfully; retained real `default_popup`, not a replacement tab.
- Owner artwork: `../Bamboo Headphones Icon.png`, 1254x1254 RGBA, alpha 0..255.
  Pillow/Lanczos generated committed 16/32/48/128/256 PNG sizes. Builds copy these
  assets directly; no Pillow/build-time graphics dependency. Bamboo loading art
  and stage icons are original SVG/CSS, with no remote fonts/scripts/images.

Confirmed causes: sidebar returned early on same-array cue patches and unchanged
virtual ranges; YouTube source changes triggered `stop(true)` even for ads on the
same watch ID. Fix updates visible text only and keeps logical video identity
separate from mutable playback sources. Audio events and 40ms scheduler guard
advertisement state; a 500ms return grace permits content source/time restoration.
This grace is an engineering choice, not a YouTube API guarantee. Ad suppression
uses player `ad-showing`/`ad-interrupting` classes; live ad variants need continued
field observation. Reference overlay presence alone can be stale, so it is not
used as a permanent playback block.

Measured WCAG relative-luminance contrast: #203D30 on #F6F8F1 = 11.07:1,
#37664B on white = 6.64:1, #596C60 on #F6F8F1 = 5.25:1. These are the core text,
primary-action and secondary-text pairs, not an assertion about every pixel.

Evidence separates real services/YouTube layout from labelled media/provider
fixtures. Subsecond fixture readiness is not a real OmniVoice latency benchmark.
Live Chrome tests still submit registered voice IDs (193/194-byte requests), with
no repeated WAV uploads; previous speed optimizations remain intact.

## Multi-platform reference and live findings, 2026-11-04

- Static source: local Youtube Dubbing `injectScript.js` and `background.js`.
  Handler mapping and structural SHA are in `research/extractor-audit.json`;
  route evidence is in `docs/SITE_ACCEPTANCE_MATRIX.md`. Private source excerpts
  are not redistributed. The new readers are independently implemented.
- Brightcove official player configuration guide:
  https://player.support.brightcove.com/references/player-configuration-guide.html
  fetched HTTP200; documents video_cloud/policy_key. Read the public config for
  the owned account/player; use its policy only for edge.api.brightcove.com
  playback GET. Never use the hard-coded fallback policy found in the reference.
- Updraft public lesson samples in `research/updraft-live.json`: actual HTML uses
  VideoObject.embedUrl/contentUrl, an hls-video open shadow root with video inside
  a slot, and 14 subtitle languages with none marked DEFAULT. Reference explicitly
  prefers English if no source-language selection exists. Regional matching
  (en -> en-US) is required. Complete speech tracks verified through packaged MV3.
- Al Jazeera public samples in `research/aljazeera*-live.json`: video loads after
  Play video, then preloads five Brightcove carousel players. Only
  `.vertical-video-player-container.vve-is-active` belongs to the current video.
  SDK mediainfo identifies caption presence; nearby recommendations must not be
  used as a fallback. Next video live acquisition passed after ownership fix.
- Reference source distinguishes support for a video player from existing-caption
  support: Glo and Oba explicitly emit empty subtitle arrays. Vidlove implements
  its movie endpoint but throws for TV. VK supports unsegmented MPD text BaseURLs;
  reference rolling-WebVTT cleanup is still a separate parity task.
- Dropbox reference segments use startTime/endTime in seconds; Circle derives
  media_transcripts/{id}.vtt from lesson or video attachment metadata and rejects
  mosaic thumbnails. Movebox response data.captions uses url/lan, with detailPath
  needed for ownership. Vocalm accepts these only from bounded observed responses
  for the active page/player. Unknown acquisition is not authorization for ASR.
- HTTP403/connection-refused results are recorded separately. These tests did not
  establish whether authenticated BBC, ArtStation, Osmosis or MathWorks sessions
  can access captions. No inference of absent captions is justified.

## Owner samples and source overrides, 2026-11-04 follow-up

- Owner Skillshare sample: public isolated browser HTTP403. Authorized owner
  Chrome WebSocket still timed out after 20 seconds (10:33 UTC). Computer Use
  browser host unavailable too. No authenticated success or cookie export.
- Owner Platzi sample: 45 Spanish cues, 1.42-200.76s. Playback error 4 reproduced
  in isolated Chrome without Vocalm. Exact site/network cause not established.
- Owner Skool /claudecodeclub/about embeds Loom, not a classroom lesson. Loom
  has a looping 5-second animatedPreviewVideo alongside LoomShakaVideoPlayer.
  Another VTT carries 173 thumbnail sprite cues. Both caused false acceptance.
  Fix: exclude preview players, reject sprite coordinates as text, fetch unique
  speech VTT by current Loom ID. Final: 55 English cues, 0-184.94s, real duration
  189.066667s, no media error, Vocalm button present. .transportSection contains
  FullScreenBtn inside data-hide-if-fullscreen/presentation wrappers; using this
  observed structure fixes the ambiguous generic controls selector. Regression
  fixtures cover preview exclusion, storyboard rejection and controls remount.
- Pluralsight reference w7 and v7/sC/x7/Ld/S7 helpers (static AST): only delivery
  descriptors ending in /hls/master.m3u8; current clip GUID comes from /clips2/
  and current lesson route/selected link. Vocalm validates host and clip match.
  JWT payload is an ownership hint, never authorization. Live course pending.
- Medbridge Aq delegates to ib=eh, resolved in original AST: segment VTT times
  are already absolute; timestamp-map offsets are not applied. Vocalm preserves
  these times, dedupes exact timing/text and requires known video duration. It
  does not dedupe solely by cue ID because IDs can repeat across segments.
  Other sites retain strict HLS timestamp-map/segment alignment.
- CoinDesk EV and hosted JW Zd read getCaptionsList URL IDs and match labels to
  playlist tracks. Reuters TV reads current item HLS subtitle renditions, which
  may directly return VTT. Vocalm requires the SDK container to own the video.
  Live CoinDesk uses /video/ rather than reference /videos/; routing now handles
  both. Tested clip north-korea-denies-it-was-behind-64b-binance-hack exposes only
  Off in the SDK, thumbnails in playlist, metadata native track. No caption pass.
  Reuters /video/ returned HTTP401. Evidence: research/jw-live.json.
- Mindvalley xq/TC/Z0/wC binds HLS to video/source and rejects storyboard text;
  Domestika X0 identifies lesson player IDs. Vocalm now recovers attached Video.js
  source manifests and rejects unrelated observed HLS. Multiple active players
  and MP4-associated caption recovery remain separate unverified paths.
- MightyNetworks z9 strips signed queries for emission comparison; Nebula Jd
  dedupes by video plus selected language/label. These are observable-emission
  optimizations, not new caption endpoints. Vocalm acquires on demand; copying
  suppression blindly could hide changed tracks. Live renewal tests remain open.
- Acceptance ledger tests reject historical false positives and keep caption-only
  results separate from player evidence. Embedded Loom cannot certify Skool.

## Companion content runtime correction and follow-up

Static inspection of Youtube Dubbing/content-scripts/content.js (hash and method
index: research/runtime-extractor-audit.json) revealed additional player adapters.
An unmapped injectScript factory does NOT imply no caption support. Twitter's
content runtime calls getTwitterM3u8Content with tweet/media ID; background.js maps
observed GraphQL extended_entities.media[].video_info.variants, including serialized
unified_card media_entities. Facebook's content runtime uses selected video React
metadata and background GraphQL maps of videoFBID/caption locales. The previous
factory-only inference has been corrected in the checkpoint and route ledger.

Vocalm independently implements Twitter's observed-data path with exact media
ownership: pbs.twimg.com/(ext_tw_video_thumb|amplify_video_thumb)/ID must match
video.twimg.com/(ext_tw_video|amplify_video)/ID in the HLS variant. Requests remain
browser-local and no authorization headers are copied or replayed. Serialized card
JSON and recursive traversal are bounded. Unrelated observed standalone VTT is not
accepted for a social feed. Current poster ID participates in acquisition identity.

Facebook reads data descriptors from a bounded chain of the selected video's React
props/fiber memoizedProps; getters and nonplain object traversal are skipped. Caption
URLs must be on facebook.com/fbcdn.net and share a unique FBID owner. Owner and URL
are revalidated after loading. Captions from GraphQL-only state still need a separate
fallback; no authenticated live Facebook result is claimed.

Mindvalley content helpers OIe/PJ/FIe/wg reveal HLS or MP4/VTT source siblings in the
owned video. Vocalm now includes all bounded source children, accepts one unambiguous
official asset VTT beside MP4, and rejects sprite text. Domestika/Mindvalley reference
controls select a video before metadata hydration; Vocalm now prioritizes the playing
lesson and retains last activation across a preparation pause. Real MediaStream
fixtures verify cross-world playback state, pause retention, switching and remount.
