# Protein checkpoint

Updated: 2026-11-03. This file is the resume point; do not infer completion from planned items.

## Current phase: working deployed release candidate; final packaging and repository delivery

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
- Repository publication/CI verification: pending final push.

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
