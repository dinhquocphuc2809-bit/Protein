# Protein checkpoint

Updated: 2026-11-03. This file is the resume point; do not infer completion from planned items.

## Current phase: working deployed release candidate; final packaging and repository delivery

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
- [ ] Push the UI revision and verify the remote branch (owner confirmed Write access).

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
- Source-only GitHub Actions validation/build workflow is included; not yet run on
  GitHub because repository push permission remains blocked.

## Remaining release gates

- Earlier push failed HTTP 403 for phucdinhIA. Owner has since confirmed Write access;
  final UI revision push and remote verification are pending below.

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
