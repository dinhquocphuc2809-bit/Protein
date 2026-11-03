# Reference implementation analysis

Evidence date: 2026-11-03. Original packages remain untouched outside this repository.
`research/inventory.json` hashes all 280 files. Formatted working copies live in the
ignored `research/extracted/` directory. Line references below refer to those copies,
not the minified originals. Inventory is not a claim of line-by-line verification of
every bundled framework or localization string.

## Neko Dub 1.2.3

### Actual deployment and request sequence

1. Popup/settings select OmniVoice and a reference voice. The background script owns
   network requests, credential handling, persistence and remote voice registration.
2. Colab inference path opens Drive notebook `1QMUQ2SjrIEHT8E8xzMgHv7cIUJbuIyKe`.
   Background automation locates controls through shadow roots, selects T4, starts
   cells, detects quota/CPU/runtime errors, reads a `trycloudflare.com` URL from
   notebook output, probes health and stores it. Closing/reloading the tab cancels setup.
3. Modal deployment is a DIFFERENT Colab notebook, ID
   `1nG4H-KWIwJJabdREruG0KXLHcrOeQM34`. It installs the Python Modal SDK, writes a
   Python worker, invokes `modal token new` when needed, prompts the user to authorize
   Modal, creates/updates a worker password, deploys, and discovers the web URL.
4. The notebook emits `NEKO_DUB_MODAL={...}` events with a random run ID. The extension
   ignores older runs, validates Modal login URLs, sends a password choice through a
   nonce-marked DOM slot and saves the resulting endpoint/password. Only one deployment
   tab runs at a time. See background.js:10865, :11067, :11109, :11169.
5. Later playback calls the deployed HTTPS endpoint directly. A running Colab tab is
   unnecessary for Modal inference. The extension does NOT deploy Python through a
   browser-native Modal REST control API, nor does this bundle import Modal's SDK.
6. No Kaggle integration was found in the shipped manifest or first-party modules.
   Voz post 43731279 describes Kaggle as a possible alternative and says automation
   had not yet been written at that point. Do not claim shipped Kaggle support.

Both public notebooks were downloaded and their code inspected, not executed.

### Worker characteristics and hazards

The Modal notebook bakes OmniVoice and Whisper-base weights into an image, loads
FP16 on T4, uses `scaledown_window=30`, `timeout=120`, `max_containers=1`, six
concurrent HTTP inputs and three concurrent model-generation threads. It does not
actually mount a Modal Volume despite the section heading mentioning one.

Reference files are temporary, indexed by voice ID, capped at 128 with LRU eviction.
Cold container replacement loses registrations; background.js:8028 detects missing
voices and re-registers once. `max_containers=1` does not preserve state across restarts.

The worker's password is optional, and model initialization precedes application-level
authentication. An unauthenticated request can therefore start a GPU even if an
application password is configured. Supplied HAR TTS requests have no authentication
header. Our worker must authenticate at the Modal proxy and fail closed. Uploads in
the reference call `await file.read()` without a byte bound and trust the filename
extension. Our worker must validate actual WAV structure and decoded duration.

The sample concurrently calls a shared model from threads. This is not evidence of
thread safety. Begin with serialized generation and benchmark before increasing it.
Health polling on the GPU function can prevent scale-down; use a CPU control endpoint
and stop GPU work when playback/lookahead stops.

### Audio, prefetch and caches

- background.js:7946 sends individual items to `/api/tts/batch`, up to six concurrent
  requests on Modal, with speed 1 and 16 diffusion steps. Returns base64 Ogg data.
- Translation uses context, summary, style, source/target languages and cache version.
  Translation and TTS cache keys are separate. This separation must survive voice changes.
- background.js:6438 defines IndexedDB `dubbing-ai-cache`, store `tts_audio`, 48-hour
  TTL, 80 MiB high watermark / 60 MiB eviction target and a 20 MiB memory layer.
  The TTS key includes language, engine, voice, model, text hash and text length.
  Use SHA-256 for new keys rather than copying its 32-bit text hash.
- Content controller prioritizes startup/current-window cues, normal lookahead and
  background work; seek reanchors the queue. Utterance/anchor epochs reject stale
  results; object URLs and audio graphs are cleaned on stop/SPA navigation.
- `HTMLAudioElement.preservesPitch=true` is set. Changing an AudioBufferSource rate
  alone would change pitch; it is not an equivalent replacement.
- `clearInFlightRequestsForReanchor()` is empty in this build (content.js:25106).
  New implementation needs real cancellation, bounded outstanding work and epoch checks.
- Existing code can skip overdue missing audio. New UI must show buffering/retry and
  avoid silently omitting required speech. A smooth result depends on measured GPU
  throughput and adequate lookahead, not a promise of zero wait after arbitrary seeks.

### Assets

12 base Vietnamese WAV presets; 72 emotional MP3 variants (six per base voice);
8 Ogg BGM tracks. Import all assets for local packaging with SHA-256 provenance.
Keep one selected voice per dubbing session: no diarization, role mapping or automatic
speaker/emotion switching. Emotional samples may be manually selected as a single voice.
No redistribution license for these voice/BGM files was found in the package.
Their presence is not a license grant. Preserve local assets; do not publish them to
GitHub/store until redistribution provenance is established. The author's post
44218120 says the Koto BGM was generated with Suno; that is provenance, not a license.

## HAR: observed protocol, not assumed streaming

725 entries, zero recorded WebSocket messages. See `research/har-sanitized.json` for
every entry's method, endpoint, status, timing, header names and structural schema.
Secrets, transcripts, signed URLs, cookies and audio bodies are not in that report.

| Endpoint | Count | Observed payload/role |
| --- | ---: | --- |
| POST /api/tts/batch | 518 | One item/request: id, text, voice_id; speed, num_step. JSON response has audioBase64, byteLength, elapsedMs, error. All 518 recorded clips have OggS magic. |
| GET /api/health | 122 | Voice registry and concurrency limits; three requests have status 0. |
| POST /api/set-ref-audio | 16 | Multipart voice registration; returns voice_id and ref_text. |
| POST /v1/translate/ai | 12 | Cue IDs, raw text, contextBefore, videoSummary, language and style. |
| POST /v1/transcript | 4 | Video/language, anchor and startup window; partial/cursor/cache metadata. |
| POST /v1/punctuate/repair | 1 | Timed cue input; corrected text keyed by cue ID. |
| POST /api/auth/extension/refresh | 5 | Session refresh; raw capture contains sensitive session data. |

Other entries cover preflight, quota, style, emotions, speaker polling and sync. The
new system deliberately excludes speaker/emotion inference. Headers identify CORS
behavior, not a security boundary; allowlisted origins do not replace authentication.

Observed network latency: TTS p50 6.463 s, p95 10.724 s, max 15.490 s; translation
p50 14.780 s, p95 16.736 s; reference upload max 21.237 s. These measurements belong
to this HAR only. They are NOT our benchmark, cold-start measurement, or concurrency
capacity estimate. The format delivers complete per-cue clips, not streamed PCM chunks.

## YouTube Dubbing 4.3.19

### Subtitles and site lifecycle

The manifest injects into all frames/sites, with exclusions; MAIN-world probes capture
YouTube caption responses and Kinescope metadata. Isolated content code and injected
page bridges exchange site metadata. Adapters locate `<video>` and platform state;
the source contains a broad site catalog, not evidence of all-site ASR support.

`youtube-bilingual-sidebar.js` creates a Shadow DOM panel, selects source/translation
rows, renders cue text via `textContent`, uses time-based active row selection, scrolls
without fighting recent user scrolling and seeks on timestamp click. Desktop sidebar
mode requires normal watch mode and at least 980 px width; fullscreen/theater are
handled separately. It caps rows at 5,000 but still creates a large DOM: virtualize
long transcripts in our implementation.

`audio-lifecycle-core.js` leases video audio ownership with reference counting. It
restores original volume/mute on final release. `audio-platform-core.js` identifies
logical videos by page/platform ID, preserving Bilibili part `p` and Douyin modal ID.
MSE/blob URL changes are not sufficient evidence of navigation. This prevents stopping
audio every time an adaptive player refreshes its source.

`media-audio-unlock.js` handles browser gesture requirements. `bgm-control.js` and
popup BGM controls synchronize independent volumes. `ios-memory-manager.js` is a
platform-specific memory aid, not a complete desktop eviction design.

### Media fallback

`apify-resolver-core.js`, `apify-error-core.js` and background.js implement bounded
Actor run polling, output candidate extraction, provider error classification,
public URL fetching and Nova-3 upload fallback. Tunelio's real host is `tunelio.dev`.
Its `/credits` endpoint is read-only; `/create?quality=opus&url=...` costs 10 credits.
`/info` and `/transcript` cost six each, so do not spend them unnecessarily.

| Platform | Candidate from reference | Verification |
| --- | --- | --- |
| YouTube | Tunelio /create (our required path) | Official docs and all 120 keys checked |
| Bilibili | herus13/bilibili-scraper | Public Actor exists; media mode; part >1 must not silently resolve part 1 |
| TikTok | liul/tiktok-video-audio-downloader | Public Actor exists; videoUrls input |
| TikTok fallback | web.harvester/tiktok-media-downloader | Reference code observed; separate metadata check still required |
| Douyin | lance_api/douyin-video-downloader-api | Public Actor exists; urls input |
| Douyin alternatives | apple_yang/douyin-video-audio-downloader; easyapi/douyin-video-downloader | Public Actors exist |
| Vimeo, X, Facebook, Instagram, Twitch, Dailymotion | convertfleetdotonline/video-downloader | Public universal Actor exists; actual per-site runs still required |
| Udemy, Coursera, edX, other authenticated courses/embedded players | Accessible page captions/TextTracks or user SRT | Do not invent public downloader support or forward login cookies |

Actor metadata existence is not a successful download test. Residential proxy fallback
in the sample has additional cost; leave it disabled by default. Follow redirects with
SSRF checks, enforce byte/time bounds, abort unfinished runs, limit spend per run.

## Voz coverage and regression lessons

All 35 pages were retrieved successfully, containing 691 posts. Exact coverage/hash
records are in `research/voz-coverage.json`; raw post bodies remain local and ignored.
Read author responses in context; distinguish proposed work, shipped fixes and user
reports. Image-only error details cannot be reconstructed from post text.

| Evidence (post ID) | Observed issue or statement | Design/test consequence |
| --- | --- | --- |
| 43507360, 43512706 | Voice downloads failed through R2; author identified connectivity and user later confirmed recovery | Bundle local presets; explicit download failures and retry |
| 43516935, 43661302 | Private video and playback-rate handling; 0.7 release claims support/fixes | Prefer accessible page captions; test rate changes and private-page caption path |
| 43674330 | 0.7.1 regression required 0.7.2 rollback | Versioned artifacts and deployment rollback checks |
| 43731279 | Kaggle/Modal alternatives described; automation not yet written in that post | Do not equate discussion with implementation |
| 43773716, 43864317 | Skipped words/sentences; optimization promised | Detect incomplete cue IDs, avoid silent skip, validate synthesis coverage |
| 43832250, 43832747 | Prompt-changing settings invalidate translation; another failure was a stopped local server | Separate translation identity from voice identity; diagnose server state |
| 43923705, 43924928 | Merging subtitle rows caused drift; mixed English/code read poorly | Preserve cue timing and identifiers; pronunciation normalization separate from displayed text |
| 43945689 | Slow Colab connection attributed to tunnel/DNS; suggested waiting or Modal | Bounded readiness polling and honest phase/error status |
| 43990362 | SPA navigation/UI corrections announced | Repeated navigation/cleanup stress tests |
| 43990745 | Author describes T4, scale-to-zero after 30s and approximately 10s wake | Confirm against notebook and measure independently |
| 44010208 | Numerals, O/0, units mispronounced; model limitation | Pronunciation fixtures, preserve display text, human listening QA |
| 44136235 | Audio cache is device-local | Explicit local cache quota/eviction; backend translation cache persists |
| 44156534, 44156646 | Udemy original sound confusion in translate-only mode | Separate mode from mixer state; restore baseline audio |
| 44180376, 44180515 | Missing translation cue broke export; clearing cache resolved it | Validate full ID coverage before cache commit; repair only failed batch |
| 44221046 | Upstream AI provider slow at peak time | Bounded retries, provider health/circuit breaker and visible buffering |

The captured thread text does not substantiate a specific author-confirmed RAM leak,
CORS bug or CSP fix. Treat those as independent engineering risks, not invented Voz findings.
