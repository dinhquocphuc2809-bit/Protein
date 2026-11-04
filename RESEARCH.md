# Protein research ledger

Updated: 2026-11-04. Separate observed evidence, interpretation and unverified claims.

## Local observations

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
