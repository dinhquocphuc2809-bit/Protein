# Veloa

Contextual subtitles, single-voice AI dubbing and a video study companion.
Built for Chrome/Firefox Manifest V3, an Oracle ARM64 VPS, and separate Modal ASR/TTS accounts.

## Current delivery

The backend is deployed at **https://ubuntu-a1.tail5dab10.ts.net**. The admin service is
accessible only through the owner's Tailscale network. SSH also listens only on Tailscale.
See [CHECKPOINT.md](CHECKPOINT.md) for exact completion status and open acceptance gates.
This repository does not claim universal site support, zero latency, or perfect voice quality.

Real acceptance checks have exercised:

- Three translation models with unchanged cue IDs/timestamps; summary and study chat.
- YouTube -> Tunelio -> Deepgram and TikTok -> Apify -> VPS upload -> Deepgram.
- YouTube -> VPS normalization -> Modal Qwen ASR/alignment -> translation.
- Chrome/Chromium and Firefox extensions with real backend/TTS and playback to video end.
- Seeking/replay, switching voice without retranslating, and switching back using audio cache.
- Native Messaging deployment into the client's own Modal account.
- Private admin ticket lifecycle, provider records, model catalog and system statistics.

## Local packages

The owner workspace contains `dist/chrome`, `dist/firefox`, `dist/veloa-chrome.zip`
and `dist/veloa-firefox.zip`. Local builds include 84 reference voice variants and
8 BGM tracks imported from the supplied reference extension. Their redistribution
license was not found, so these assets are excluded from Git and public artifacts.

Chrome: load `dist/chrome` using **Load unpacked** in the extensions developer page.
Firefox: load `dist/firefox/manifest.json` as a temporary add-on through
`about:debugging#/runtime/this-firefox`. Permanent consumer Firefox installation
requires Mozilla signing; a ZIP is not a signed store release.

Click the Veloa toolbar icon to open the control popup. Its settings button opens
settings inside the same popup. Activate the supplied owner Ticket, then either deploy a voice
worker through the local bridge or connect the already deployed worker with its proxy
credentials. Secrets are in the ignored `.private/HANDOVER.md` in the owner workspace.
Never upload that file, `.private`, the HAR, or parent credential files.

The extension button appears on accessible HTML video pages. Version 0.3.0 reads
native subtitles through DOM/open-shadow TextTracks, VTT/SRT/TTML, HLS subtitle
playlists, player SDKs and configured caption metadata APIs. It also probes YouTube
captions/transcripts and accepts UTF-8 SRT. Unknown or failed acquisition exposes an
explicit **Use ASR for this video** action; it does not silently spend ASR credits.
The backend can acquire media only through its configured supported routes.
Protected/DRM content is not bypassed.

The reference-derived registry contains 159 site/route rules, including embedded
players and repeated brands. This is not a claim of 159 fully tested live websites.
See [analysis and limits](docs/MULTISITE_ANALYSIS.md), [route coverage](docs/MULTISITE_COVERAGE.md),
and the machine-readable [inventory](research/multisite-inventory.json).

Version 0.2.1 distinguishes missing YouTube captions from a failed caption download.
It reads existing player captions/transcripts first, including native fetch/XHR
responses. If tracks exist but YouTube returns empty data, it reports the failure
without spending ASR credits. ASR is allowed only after confirming no tracks exist.
After updating, reload both the extension and the video page to install early capture.

On a normal YouTube watch page, bilingual subtitles appear above the recommendations
in the right column, with source text above each translation and clickable timestamps.
Theater, fullscreen and narrow windows use the video overlay. Summary and study chat
open a focused panel on the video page. See [design details](docs/DESIGN_REVISION.md).
Internal `auvirel` service, storage and Native Messaging identifiers remain stable
so the visual rename does not discard existing connections or caches.

## Build and verify

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[test]"
.venv/Scripts/python.exe tools/import_reference_assets.py
.venv/Scripts/python.exe tools/build_extension.py --local-assets
.venv/Scripts/python.exe -m pytest -q
node --test tests/*.test.cjs
.venv/Scripts/python.exe tools/check_secrets.py
```

Omit `--local-assets` for a source-only package that accepts personal WAV uploads.
FFmpeg is required to normalize imported audio. Node 20+ is used for JavaScript tests.
Browser acceptance scripts additionally require Playwright/Selenium and their browsers.
Live test tools consume provider credits and use only short, bounded test media.
The caption-only tools `caption_acceptance.py`, `multisite_acceptance.py`,
`multisite_firefox.py`, and `multisite_live.py` do not call paid providers.

## Client Modal deployment

```powershell
.venv/Scripts/python.exe native/install.py --chrome-id YOUR_ACTUAL_EXTENSION_ID
```

The installer registers a current-user Native Messaging host for Chrome and Firefox.
Use the ID shown by the installed Chrome extension. The bridge accepts only fixed
deploy/status operations, invokes the official Modal Python SDK, and passes deployment
credentials in a child environment, never shell text or the VPS. Long deployment runs
survive MV3 worker suspension and report progress via a private status file.

The voice API uses workspace proxy credentials (`wk-` / `ws-`), distinct from deploy
credentials (`ak-` / `as-`). Deployment defaults to T4, max one GPU container, no minimum
warm container, and 30-second idle scale-down. Model weights are revision-pinned on a
Modal Volume. No periodic GPU keepalive runs. The owner confirmed $0 spend limits on
all four accounts; this confirmation is recorded separately from API observations.

## Server operations

Read [docs/OPERATIONS.md](docs/OPERATIONS.md) before changing the deployment.
Architecture and boundaries: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
Reference analysis: [docs/REFERENCE_ANALYSIS.md](docs/REFERENCE_ANALYSIS.md).
Research/source trail: [RESEARCH.md](RESEARCH.md).
Acceptance matrix: [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

## Known limits

- T4 runs succeeded; L4 benchmark attempts timed out. L4 is not a validated default.
- Automated waveform/playback checks do not replace listening and subjective voice QA.
- TikTok and YouTube have live acquisition evidence; other Actor/site combinations
  remain conditional until tested. Accessible captions and SRT work independently.
- Native browser fullscreen on a bare video element cannot contain arbitrary HTML
  controls; fullscreen player wrappers are supported. Cross-origin child frames can
  host their own panel rather than a top-frame consolidated panel.
- Generic detached/closed Shadow DOM video players require additional site adapters.
- The visual design follows Apple HIG principles; it is not a native Apple component
  implementation or a claim of Apple certification.
- Store publication/signing, asset redistribution provenance and broad long-video
  soak/listening tests remain release gates.
