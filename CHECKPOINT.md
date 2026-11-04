# Protein checkpoint

Updated: 2026-11-04. This file is the resume point; do not infer completion from planned items.

## Current phase: working deployed release candidate; final packaging and repository delivery

### Voice catalog columns (0.5.1, 2026-11-04)

- [x] Verified all 12 base WAVs already present against supplied Neko file hashes.
  Source name is Dang Khoa (not Dang Quang); no Dang Quang asset was found.
- [x] Preserve source gender/base ID metadata through import and public settings.
- [x] Shared two-column male/female picker in popup, options, content panel and
  YouTube quick menu. Six base voices per column; variants remain selectable in
  a compact secondary selector. Custom/unknown voices stay outside gender groups.
- [x] Actual Chrome popup: all 12 IDs select/save correctly; all 12 packaged WAVs
  decode; variants/Escape/options/quick menu pass. Firefox selection/reload passes.
- [x] 41 JavaScript regressions and secret scan pass; 84 references/8 BGM retained.
- Evidence: `research/voice-picker-acceptance.json`,
  `research/voice-picker-firefox.json`; screenshot in `docs/images/vocalm-voices.png`.
- No provider/ASR/GPU calls or backend changes required for this revision.


### Vocalm player/UI revision (0.5.0, 2026-11-04)

- [x] Owner branding: Vocalm with supplied Bamboo Headphones Icon.png, fern/sage
  palette, compact listening/sound/account popup, embedded accordion settings.
- [x] In-place sidebar translation patches preserve mounted rows/scroll position.
- [x] YouTube watch ID owns the session; ads suspend TTS/music/lookahead without
  clearing transcript/cache. Source and video-node replacement are covered.
- [x] Preparation overlay with three actual stages, growing SVG bamboo, keyboard
  focus, reduced motion, Cancel and explicit Ready. Initial work remains one unit.
- [x] In-player Vocalm button/menu for voice/language/captions/mixer/BGM/study.
- [x] Real YouTube layout/button/theater/narrow checks; actual Chrome and Firefox
  live translation/OmniVoice tests; Chrome cache/voice replay/summary/chat pass.
- [x] 58 Python / 41 JavaScript tests, compilation and secret scan pass.
- [x] Browser fixtures cover live row updates, ads/source/node replacement,
  fullscreen, reduced motion, ready-seek, startup-seek and cancellation.
- [x] Final error-unlock acceptance and local packages complete. Chrome/Firefox
  `dist/vocalm-*.zip` include 84 voices and 8 BGM; source-only CI packages omit them.
- [x] Source commit `a050701` pushed; remote hash independently verified. GitHub
  validation passed: https://github.com/dinhquocphuc2809-bit/Protein/actions/runs/41758995072.
- Design/review gates: `docs/VOCALM_DESIGN.md`. Evidence:
  `research/vocalm-ui-acceptance.json`, `research/ui-youtube-live.json`,
  `research/browser-chromium.json`, `research/browser-firefox.json`.
- Ad evidence is deterministic fixture coverage, not a claim of live midroll ad
  verification. Native video-element fullscreen remains a browser limitation;
  YouTube container fullscreen is covered. No backend/GPU deployment was changed.


### Neko source/HAR latency optimization (0.4.1)

- [x] Re-read supplied Neko Colab/Modal notebook code and translation/TTS client.
  No shipped Kaggle integration found. See `docs/TTS_LATENCY.md` for exact scope.
- [x] Analyze all 725 HAR entries without exporting secrets/content. 518 TTS calls
  use one item, voice_id, 16 steps and no WAV; median request 175 bytes. Twelve
  translation calls request punctuation/summary; recorded contextBefore is empty.
- [x] Implement bounded CPU reference registry, shared client registration/recovery,
  CPU registration parallel to caption preparation, long polling and CPU concurrency.
- [x] Preserve old worker protocol, single GPU model execution, 16 steps, cache keys,
  seek priority and cancellation. Submission/cancel races have dedicated regressions.
- [x] Deploy client account 4 only; CPU ingress pinned us-east, GPU flexible. Test CPU
  snapshot, then remove it from production because consistent restore benefit was
  not established. Keep original 8 GiB GPU-direct model load. No warm pool/ASR changes.
- [x] Real Chrome/Firefox service tests and actual Chrome regional/seek fixtures pass.
- [x] Snapshot trial after confirmed empty container inventory; 35.718s startup,
  creation observed but restoration benefit unproven. Do not advertise as shipped.
- [x] Final code checks: 58 Python / 39 JavaScript tests; secret scan and compilation.
- [x] Final Chrome live traffic: four synthesis bodies are 193/194/193/194 bytes,
  all registered voice IDs, no inline WAV. Existing audio cache/voice replay passes.
- [x] Source commit `0249795` pushed; remote hash verified and GitHub validation
  passed: https://github.com/dinhquocphuc2809-bit/Protein/actions/runs/41750354149.

Transport warm samples: 2.875-3.406s to receive ~8.2s audio versus old 9.156s for
same input; submission ~0.6-0.8s versus 6.562s. Small observations, not an SLA.
Final non-snapshot first worker call 22.422s; first registration is separate and can
overlap caption preparation. Cold startup remains open, not solved by warm latency.
Raw GPU inference ~1.4s warm. The first test of 45s idle cycles kept the same container;
do not label those calls cold. Reports: `research/tts-latency-*.json` and
`research/neko-latency-analysis.json`. CPU region adds its documented 1.75x CPU-only
multiplier; no GPU region multiplier. Details and remaining limits in TTS_LATENCY.md.

### Latency clarification and diagnostic follow-up (2026-11-04)

- Owner asked why initial/later TTS requests are slow and offered additional MCPs.
  Existing SSH, Modal SDK and browser automation suffice for current diagnosis.
- Added `tools/tts_latency_probe.py`; two real requests use the same 168-character
  text and 303,404-byte reference on client account 4. No worker/deployment changes.
- First/second submission acknowledgement: 8.750s/6.562s. Audio received:
  26.281s/9.156s; generated audio length: 8.191s/8.031s. These are complete-clip
  transport timings, not GPU inference time or time-to-first-streamed-sample.
- Local decode plus DSP is small; first sample DSP 0.402s, second near-unity DSP
  0.001s. Earlier samples measured 0.096-0.386s for DSP alone.
- Evidence: `research/tts-latency-breakdown.json`. Worker initialization, reference
  upload, queueing and actual model inference are not individually instrumented yet.
  Do not attribute the whole delay to cold start or claim an optimization was deployed.
- Suspected bottleneck to investigate next: slow submission before result polling,
  including the repeated reference payload and Modal control-plane calls. Existing
  worker uses min_containers=0/scaledown_window=30; this diagnostic does not increase
  idle-GPU allocation. Prefetch helps hide latency but cannot guarantee
  sustained realtime when synthesis throughput is below speech consumption.

### Progressive translation and speech (0.4.0)

- [x] Reinspect Neko sentence boundaries and current-window scheduling; root cause and
  exact reference anchors are in `docs/PROGRESSIVE_DUBBING.md`.
- [x] One-unit initial translation/TTS, authenticated per-unit translation windows,
  independent translation/audio caches, bounded lookahead and decoded audio memory.
- [x] Sentence/clause reflow, punctuation prompt, natural-duration synthesis, gentle
  WSOLA fitting and edge fades; no ordinary late-playback prefix clipping.
- [x] Seek/rapid-seek cancellation, pause/resume, rate/stall handling, Stop during
  initialization, voice change during buffering and native pause-before-ended handling.
- [x] 51 Python and 32 JavaScript tests; actual Chrome fixture startup/seek tests;
  12 YouTube and 19 multisite caption regression cases.
- [x] Real retained 595-cue video: 254 speech units, one initially translated; three
  real voice samples. Independent ASR returned identical 67 words before/after DSP.
- [x] Real Chrome and Firefox translation/TTS playback; Chrome replay and voice A-B-A
  cache reuse, summary/chat. Browser harness uses isolated profiles and Blob media.
- [x] Backend deployed with health checks; local Chrome/Firefox 0.4.0 packages rebuilt,
  including existing 84 voices/8 BGM. No GPU redeploy or credential reallocation required.
- [x] Final deployment hash comparison and real repeated-window DB audit passed:
  one cache hit, zero new translation calls, 198.84 GB decimal free on VPS.
- [ ] Subjective listening approval and long-session endurance remain unverified.

Reports: `research/progressive-*.json`. Measured TTS round trips were 29.906s initially,
then 7.531s and 6.516s; these do not establish sustained realtime throughput. If the
GPU falls behind, hold the video rather than drop words. Source-less ASR still runs
before this pipeline. See the detailed implementation/testing document for boundaries.
Owner audio sample is `.private/progressive-audio/sentence-comparison-new.wav`.

### YouTube caption acquisition fix (0.2.1)

- [x] Reproduce the owner's video: `3BndvjrGwyE`, 1,381 seconds, 21 advertised tracks.
- [x] Confirm root cause: timedtext returned empty HTTP 200; content script swallowed
  extraction errors into null and submitted an ASR job. Background also selected the
  first track (Arabic in this case) rather than the current English track.
- [x] Remove silent fallback. Only repeated, current-video, explicit no-track results
  can enter ASR; track download errors and unknown metadata stop before job submission.
- [x] Add document-start MAIN-world capture of native timedtext fetch/XHR and transcript
  responses, bounded per-page cache, player-session retrieval, XML/JSON3 parsing,
  matching initial-player metadata fallback, current-language selection and CC restoration.
- [x] Verify 11 actual-extension fixture scenarios without paid providers, 8 JS tests,
  34 Python tests, and existing popup/live-backend acceptance.
- [x] Verify affected real YouTube page now creates zero backend jobs when subtitles
  return empty. Report: `research/caption-live.json`.
- [x] Firefox 159 loads the MAIN-world bridge and reports existing-but-unavailable
  captions instead of falling into ASR. Report: `research/caption-firefox.json`.
- [ ] Verify successful extraction in the owner's normal YouTube session. Isolated
  browser sessions still receive empty native caption responses; do not claim this
  video's real caption download passed. Native player also did not display caption text.

The earlier HQ job failed with `Alignment produced invalid timestamps` after 266s.
This caption-priority fix avoids that unnecessary path; it does not repair HQ alignment
or convert the full-video ASR pipeline into streaming ASR.

### UI revision requested by owner

- [x] Reinspect both reference popups and Youtube Dubbing's right sidebar.
- [x] Rename visible extension to Veloa 0.2.0; redraw SVG/antialiased toolbar icons.
- [x] Implement a functional 420px toolbar popup with inline settings; no new tab.
- [x] Connect popup voice, subtitles, SRT, mixer, start/stop and study controls to video.
- [x] Recreate the reference's source-first right-column bilingual transcript.
- [x] Support real YouTube's newer fixed-panel layout with a right dock beside video.
- [x] Verify actual Chrome popup, live translation after popup closes, SRT import,
  light/dark sidebar, seek, native panel transitions and 5,000-cue virtualization.
- [x] Re-run Firefox 159 real translation and audio playback acceptance.
- [x] Build local Chrome/Firefox packages with 84 voices and 8 BGM tracks.
- [x] Record comparison and evidence in `docs/DESIGN_REVISION.md` and `RESEARCH.md`.
- [x] Push UI revision `3f5642a` and verify `refs/heads/main` resolves to that commit.
- [x] GitHub Actions for `3f5642a` completed successfully: Python/JS tests,
  compile check, Chrome/Firefox source-only builds and artifact upload.

Current UI reports: `research/ui-acceptance.json`, `research/ui-youtube-live.json`.
Screenshots: `.private/ui-qa/`. Local archives: `dist/veloa-chrome.zip`,
`dist/veloa-firefox.zip`; source-only archives are built by CI without reference assets.

- [x] Clone the requested Protein repository (remote contains no commits).
- [x] Inventory reference packages: Neko Dub 1.2.3, YouTube Dubbing 4.3.19.
- [x] Count supplied credential records without exposing values.
- [x] Index all 58 JavaScript modules; deep-trace deployment/audio/cache/site integration paths.
- [x] Analyze all 725 HAR entries; generate structural report without secret values.
- [x] Retrieve all 35 Voz pages / 691 posts; review relevant reports and author responses.
- [x] Verify provider/model/browser/security/design documentation; record failed URLs too.
- [x] Probe all supplied provider records using read-only endpoints; all authenticate.
- [x] Verify all four Modal accounts via billing/settings/app-list calls.
- [x] Inspect Oracle architecture, storage and Tailscale over SSH (connection already uses Tailscale).
- [x] Complete initial risk assessment, architecture and acceptance test matrix.
- [x] Import 92 local reference assets: 84 voice samples plus 8 BGM tracks; verify hashes.
- [ ] Benchmark real Qwen3-ASR and OmniVoice on T4 and L4.
- [x] Implement backend/admin and dual MV3 extension with local Native Messaging source.
- [x] Deploy backend to ARM64 VPS as non-root systemd services.
- [x] Deploy ASR on accounts 1-3 and OmniVoice on account 4.
- [x] Bind SSH/Admin to Tailscale; verify independent SSH reconnect with timed rollback.
- [x] Enable stable Tailscale Funnel HTTPS after owner enabled the tailnet capability.
- [x] Real HTTP tests: translation (3 models), summary/chat, YouTube and TikTok ASR paths.
- [x] Chromium real extension/provider pipeline: captions, translation, TTS, playback to end.
- [x] Complete Firefox and local Native Messaging deployment acceptance.
- [x] Verify seek/replay uses audio cache; voice change does not create a translation job.
- [x] Verify switching back to a prior voice uses IndexedDB audio without another synthesis.
- [x] Verify injected timestamped summary and study chat panels with real backend requests.
- [ ] Complete subjective listening, long-video soak and broad site compatibility acceptance.

## Constraints

Single speaker per dubbing session. Backend secrets never enter the extension or Git.
Modal accounts 1-3 are backend ASR; account 4 is client TTS.
No direct yt-dlp. No fabricated benchmarks, credit balances, support claims or tests.
Bound disk usage below the existing disk capacity; never auto-expand storage.
Do not change SSH bindings until a second working Tailscale SSH path is verified.
Local reference bundles and raw HAR may contain credentials: never commit them.

## Working paths

- Repository: `Protein/` under the supplied workspace.
- References and credential files: parent directory, left intact.
- Research record: `RESEARCH.md`; machine-readable evidence: `research/`.
- Raw web pages and extracted source: ignored local folders under `research/`.

## Verification

Read-only provider checks: Gemini 1/1, DeepSeek 1/1, Apify 2/2, Deepgram 5/5,
Tunelio 120/120 authenticated. One Tunelio key is exhausted despite HTTP 200.
Official Gemini IDs requested by the user exist. DeepSeek maps to `deepseek-flash`.
Secret scan passed for the Git-visible files at the time of the check.

T4 benchmark: Vietnamese ASR warm RTF 0.251; English warm RTF 0.158. TTS warm
RTF 0.274, cold roundtrip about 18.79s. L4 ASR/TTS timed out at 240s; no successful
L4 inference or completed comparison is claimed. Detailed evidence is in research/benchmarks.
Do not stop pre-existing apps in account 4.

Backend public/admin apps, SQLite jobs/auth/cache/key rotation and GPU worker source
are implemented. 34 Python and 5 JavaScript tests passed after fixing body timeout, download cancellation,
existing-file preservation, worker heartbeat, and overlapping ASR transfer windows.
Public/admin HTTP separation and signed-request replay rejection are tested.
Production worker deployment and initial provider workflows now pass. Human listening,
L4 inference, broader site coverage and complete release acceptance remain open.

## Live deployment (2026-11-03)

- Public API: https://ubuntu-a1.tail5dab10.ts.net (Funnel HTTPS, owner enabled).
- Admin binds the existing VPS Tailscale address on port 8001; SSH only that address:22.
- Temporary Cloudflare tunnel stopped after Funnel health verification.
- Owner ticket and admin environment: ignored `.private/owner-ticket.json` and
  `.private/deployment/server.env`. Never include their contents in Git or tool output.
- Production TTS: HTTP 401 unauthenticated, repeat request returns same id, real Ogg
  4.741s generated in 24.859s cold roundtrip. Production ASR: 25 Vietnamese aligned words,
  52.718s cold roundtrip. Reports under `research/benchmarks/production-*.json`.
- Browser QA artifacts: `.private/browser-qa/`; reports `research/browser-chromium.json`.
- Firefox 159 real extension pipeline passed. Selenium requires geckodriver service `--allow-system-access` for extension
  pages in its isolated test profile; never pass browser `--remote-allow-system-access`
  in capabilities (rejected).
- Fixed deployment CRLF environment sourcing: normalize server.env before shell source.
  Earlier bootstrap created `/var/lib/auvirel` plus a separate CR-suffixed directory;
  the latter was removed after strict path/content checks by cleanup_bootstrap_artifact.py.
- Summary root cause: model may return a bare array without enforced response schema.
  Gemini rejects minItems/maxItems constraints here with HTTP 400. Use simple
  responseJsonSchema and enforce count/timestamp validation locally. Live retry passed.
- Backend retry/session renewal/balance refresh/schema fixes are deployed. GPU ingress
  body timeout is deployed. Local native deployment through the actual browser passed.
- Native source supports Windows installation. Owner handover is `.private/HANDOVER.md`.
- All four Modal $0 spend limits were explicitly confirmed by owner on 2026-11-03;
  this was not independently read through API. Evidence: modal-spend-cap-confirmation.json.
- Latest observed VPS: about 8.24 GB used, 198.64 GB available (decimal), no disk resize.
  Daily release-retention timer enabled; application spool/cache/log limits active.
- Completed job result retention additionally capped at 512 MiB; an eviction test
  confirms running job inputs are preserved. Deployment health failure now restores
  the prior code symlink without discarding persistent database state.
- Source-only GitHub Actions validation/build workflow is active after the successful
  repository push. UI revision run: https://github.com/dinhquocphuc2809-bit/Protein/actions/runs/41596877073.

## Remaining release gates

### Translation recovery incident (2026-11-03)

- Owner screenshot: `translation: incomplete_cue_coverage (HTTP 502)`. Production
  confirms that failed job and a subsequent `gemini: invalid_json` job; the latter
  received 595 supplied English cues and failed in translation, not ASR.
- Root causes in code: strict positional ID comparison, no translation response
  schema, only one whole-batch retry, malformed model JSON cooling a healthy key,
  and no persistent partial-translation checkpoints.
- Implemented structured output, strict ID mapping (including out-of-order answers),
  targeted missing-cue repairs, bounded splitting/size budgets, and ticket-scoped
  partial cache under existing disk/TTL limits. Never return incomplete translation
  as success or change original cue timestamps. No DB migration required.
- Deployed backend and verified exact provider source hash. 43 Python tests pass;
  real Gemini 12-cue test passes with checkpoint replay causing zero extra calls.
  Public HTTPS acceptance passes with 12 nonzero IDs, preserved timing and a cache
  hit on repeat with no translation event. Evidence: `research/translation-recovery*.json`.
- Original incident inputs are purged by normal retention; no raw model answer was
  logged. The exact original malformed response and full 595-cue replay are unverified.
- Backend-only fix: no extension reinstall needed; owner can retry Prepare. New
  retries preserve successful partial work; work lost before this fix is not recoverable.

### Active work: multisite subtitle acquisition (2026-11-03)

- Reference catalog statically resolved: 159 routing rules, including mapped
  ThoughtIndustries/Memberspot entries. Full analysis/implementation checklist:
  `docs/MULTISITE_ANALYSIS.md`.
- Scope: shared native-caption engines and site metadata, selected-frame/media
  ownership, captions-before-ASR guard and per-mechanism regression coverage.
- No claim that every reference site has been tested live. Existing YouTube empty
  timedtext in isolated browsers remains a documented live limitation.
- Implemented Veloa 0.3.0: early all-frame MAIN capture, shared subtitle parsers,
  DOM/open-shadow discovery, SDK and configured metadata readers, frame/media
  validation, YouTube embed IDs and explicit ASR fallback for uncertain acquisition.
- Validated: 34 Python tests, 15 JavaScript tests, 19 actual-extension multisite
  fixtures, 12 YouTube fixtures, two Firefox 159 acquisition/CC restoration checks.
  `research/multisite-*.json` and `research/caption-acceptance.json` record evidence.
- Live success: Apple WWDC2024/10140 has 360 English cues via HLS; MDN example has
  14 English cues via native tracks. Ahrefs uses a YouTube nocookie embed that remains
  unknown in the isolated browser. No paid ASR/TTS/translation was called for this work.
- Source/asset packages rebuilt at `dist/chrome`, `dist/firefox`, `dist/veloa-*.zip`;
  local builds keep 84 voices/8 BGM. Secret scan passed. Reload extension AND page
  after updating: early hooks and service worker must use the current bundle.
- Per-route factual coverage: `docs/MULTISITE_COVERAGE.md`; private/authenticated
  sites and bespoke APIs outside shared readers remain individual acceptance gates.
- No backend deployment or extra VPS media storage is needed for this revision.
- Source commit `37fa24d` pushed and remote head independently verified. GitHub
  validation passed (Python/JavaScript checks, compilation and both source-only
  extension packages): https://github.com/dinhquocphuc2809-bit/Protein/actions/runs/41606513416.

- Earlier HTTP 403 is resolved: owner granted phucdinhIA Write, UI revision `3f5642a`
  was pushed successfully and independently verified with `git ls-remote`.

- L4 runs timed out; T4 remains the measured default. Do not label L4 benchmark passed.
- No subjective listening sign-off or long-video endurance certification yet.
- Only YouTube/TikTok acquisition has live per-site evidence. Other Actor routes need
  their own samples; captions/SRT remain usable independently of public download support.
- Native video-element fullscreen and closed-shadow video players have documented limits.
- Firefox package is a temporary unsigned addon; store signing/publication is not done.
- Reference asset redistribution license is unverified; assets remain local/ignored.
- Name search found no exact store match at research time, not a trademark guarantee.

## Active revision: Bilibili and native player integration (2026-11-04)

- [x] Re-read the reference Bilibili metadata, route resolver and CC fallback.
- [x] Reproduce empty acquisition on the supplied live video in an anonymous test browser.
- [x] Implement active, session-local UGC metadata acquisition with per-part identity and bounded fallback.
- [x] Mount Vocalm controls using reference routing selectors and selected-player ownership.
- [x] Test late metadata, blob swaps, part changes, stale responses, CC restoration and failures.
- [x] Rebuild local Chrome/Firefox 0.6.0 packages with 84 voices/8 BGM and record evidence.
- [ ] Publish source and verify remote CI.
- Live discovery found Bilibili redirects to `/en/video/...`, which the previous
  matcher missed. Locale-aware routing now activates the adapter and mounts the
  button on the actual sample. Anonymous acquisition returns `bili_session`;
  do not claim the owner's authenticated subtitle extraction has passed.
- Passed: 47 JavaScript/58 Python tests, 17 Bilibili fixtures, 19 multisite caption
  fixtures, 11 native-control layouts, 12 YouTube caption fixtures, progressive
  playback/UI regressions, Firefox 159 DOM/open-shadow captions; secret scan.
- Evidence/limits: `docs/MULTISITE_REVISION.md`, `research/bilibili-live.json`,
  `research/bilibili-acceptance.json`, `research/player-mount-acceptance.json`.
- PGC/PUGV-specific API parity and individual live certification for all 159
  routes remain incomplete. Shared fallback remains available without silent ASR.
- Computer Use is unavailable. This does not block source work or isolated regression
  testing. The owner's authenticated Bilibili session remains unverified; anonymous
  empty subtitle metadata does not prove that no subtitle track exists.

## Resume details

- Architecture: `docs/ARCHITECTURE.md`; source analysis: `docs/REFERENCE_ANALYSIS.md`.
- Full validation matrix: `docs/TEST_PLAN.md`.
- GPU runner: `.venv/Scripts/python.exe tools/run_benchmark.py asr` (or `tts`).
- ASR image: torch/torchaudio 2.8.0, qwen-asr 0.0.6, Transformers 4.57.6,
  stable-ts 2.19.1, Silero VAD 6.2.3. TTS image: OmniVoice 0.2.1, separate Transformers.
- Vietnamese fallback selected for evaluation: stable-ts + Whisper-small forced
  alignment; avoid the noncommercial Vietnamese CTC weights for production.
- Credentials remain in parent input files. Raw account reports are ignored by Git.
- Native Messaging vs reviewed Colab bridge is an integration decision; no official
  browser SDK deployment capability was found. Do not forward client Modal tokens to VPS.
