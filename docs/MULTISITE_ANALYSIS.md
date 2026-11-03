# Native subtitle acquisition: reference analysis and implementation plan

## Evidence (2026-11-03)

The local Youtube Dubbing 4.3.19 bundle is inspected statically, never executed.
`tools/analyze_reference_sites.cjs` expands the constructor rule catalog, including
the ThoughtIndustries and Memberspot factories: **159 rules**, not 159 independent
extractors. The older supplied website list contains 147 patterns. Embedded CDN
players and several routes of one site account for duplicates. Neither count is
evidence of successful extraction on every live site.

The beautified local reference (ignored, not redistributed) provides these anchors:

| Source location | Finding | Veloa decision |
| --- | --- | --- |
| injectScript.js:53730 | Catalog matches domains, lesson routes, media selectors and player families | Retain factual routing metadata; independently implement acquisition |
| :62199, :62314, :62395 | DOM tracks, window metadata, captured API responses | Observe early; keep authenticated requests within the browser |
| :63326 | YouTube player, timedtext and transcript variants | Preserve the existing dedicated bridge and its no-silent-ASR guard |
| :65167 | Mux embeds expose media in open shadow roots | Discover nested video and TextTrack objects in the selected frame |
| :67709 | HLS subtitle renditions and signed manifests | Parse subtitle playlists only; bound downloads; preserve timing |
| :71971 | Kinescope player creation and playlist metadata | Capture player creation while preserving existing callbacks |
| :72616 | Wistia hashed ID and captions JSON with inline lines | Read only the selected player's ID, then parse caption lines |
| :83493 | Factory includes generic/media-only integrations | Do not label these sites as proven native-caption support |

Reference families include 27 DOM-track rules, 12 shared HLS rules, seven shared
VTT rules, 14 Wistia rules, six Mux rules and 13 universal rules. Bespoke methods
often still use those underlying mechanisms. Facebook/Twitter factory branches
and Glo metadata do not establish a complete native subtitle extractor.

## Detailed implementation sequence

- [x] Statically enumerate all 159 rules and inspect the acquisition classes.
- [x] Separate routing coverage from mechanism coverage and live-site evidence.
- [x] Generate a minimal factual site registry (no reference executable/UI code).
- [x] Implement bounded VTT/SRT/TTML/JSON/HLS parsing with strict timing checks.
- [x] Install early MAIN fetch/XHR observation in eligible frames, limited to
      subtitle/manifest resources and configured caption metadata APIs.
- [x] Add DOM/open-shadow TextTrack, Video.js/JWPlayer, Wistia, Kinescope and
      configured API metadata readers; tie results to the selected media.
- [x] Route popup/content requests to the selected frame and video; reject stale
      SPA results, ambiguous ownership, empty/failed captions and partial live HLS.
- [x] Keep original track modes and page response bodies intact. No session
      headers, cookies or signed subtitle links are sent to the backend.
- [x] Add an explicit ASR action for unknown sites; never equate extraction
      failure with proof that subtitles do not exist.
- [x] Run parser, real-extension fixture and existing YouTube regressions, then
      representative public live checks. Record authenticated sites as unverified.
- [x] Rebuild Chrome/Firefox, update checkpoint/research and scan secrets.
- [x] Publish source through the authorized repository and verify CI.

## Acceptance matrix

Parser tests cover multiline text, entities, cue IDs/settings, TTML inheritance,
JSON seconds/milliseconds, invalid timing, HLS relative URLs, timestamp maps,
discontinuities, encryption/live rejection and size/count limits. Routing tests
cover hostile hostname suffixes, shared player frames and unknown hosts.

Browser fixtures load the actual extension and intercept only explicitly labelled
test providers. They cover early fetch/XHR, DOM tracks, open shadow roots,
cross-origin iframe selection, authenticated metadata schemas, caption errors,
SPA switches, multiple videos, mode restoration and captions-before-ASR. Passing
fixtures establish mechanism correctness, not live support for all catalog sites.

Live checks use public videos without paid ASR/TTS requests. Paywalls, unavailable
tracks, login-dependent endpoints and closed shadow roots are reported precisely.

## Resource and trust boundaries

Each response is bounded; observed data has an aggregate byte/entry budget and is
cleared on media navigation. HLS has a total-byte, segment-count and concurrency
limit. No backend disk storage is needed for acquisition. Page data is untrusted;
only validated cues cross the extension/backend boundary. No webRequest cookie
capture, header forgery, DRM handling or remote script execution is introduced.

## Delivered behavior and verified limits

Veloa 0.3.0 installs bounded MAIN capture at document_start in all eligible frames.
`lib/sites.js` holds factual routes; `lib/media.js` discovers the selected visible
player including open shadow roots; `lib/subtitle-formats.js` validates and parses
subtitle formats; `multisite-main.js` owns browser-session acquisition. The
background validates frame/origin and cue data. Content/popup use the same frame
selection and expose a deliberate ASR action only after uncertain/failed discovery.
YouTube remains a dedicated reader and supports watch, shorts/live and embed IDs.

Source timing is preserved. HLS uses complete VOD subtitle playlists, at most three
concurrent segment reads, 1,200 segments/4 hours, 16 MiB segment text and a 45-second
acquisition deadline. Individual responses are limited to 4 MiB and 8 seconds.
Observed responses have an 8 MiB text budget and 24 entries; metadata holds at most
16 records. Current-video metadata is retained until navigation or budget eviction,
so waiting longer than two minutes before Prepare does not discard the manifest.
No keepalive or GPU warm-up is part of caption discovery.

The Apple live sample exposed a real failure: its source changes to a MediaSource
blob during initialization. Keeping its stable data-id prevents losing the early
manifest. Credential-free public CDN reads avoid wildcard-CORS failures; same-origin
APIs retain the signed-in browser session. The live result contains 360 English
cues with original first/last times 7.149/1241.297 seconds. The MDN live player yields
14 cues at 0/119.5 seconds. Ahrefs now uses a YouTube nocookie frame rather than the
reference Wistia implementation; that isolated live frame remains unknown.

`research/multisite-acceptance.json` records actual extension fixtures, not live
provider certification. `research/multisite-firefox.json` records Firefox 159 native
and shadow TextTrack acquisition and CC restoration. YouTube's separate regression
also covers embedded video IDs. The popup fallback was inspected in a real action
popup; it requires a deliberate click before a request without cues is submitted.

Remaining limits: bespoke APIs for every catalog site have not been ported. Their
shared DOM/SDK/HLS paths are attempted, and failure is reported without automatic
ASR. Paywalled/login-only sites have no individual live certification. Closed shadow
roots, encrypted/fMP4/byte-range subtitle playlists, ongoing live streams and TTML
sequential/timed-span layouts need native complete cues or a user-supplied SRT.
Ambiguous network ownership on multi-video pages is rejected. Bare intercepted
segments are not mistaken for a complete transcript. No end times are fabricated
from page transcripts that provide only start times.

## Reproduce reference inventory

Analysis-only dependency (not an extension runtime dependency):

```powershell
npm install --prefix .private/multisite-research --no-audit --no-fund --ignore-scripts acorn@8.15.0
node tools/analyze_reference_sites.cjs
```

The analyzer requires the supplied sibling `Youtube Dubbing/injectScript.js`.
Raw/full AST metadata stays private. Only factual routing/schema fields, the source
hash and a transparent per-route coverage table are emitted into tracked files.

## Release verification

Source commit `37fa24d` is published. GitHub Actions run 41606513416 passed Python
tests, all 15 JavaScript tests, compilation and Chrome/Firefox source-only builds.
Local actual-extension results: 19 multisite fixtures, 12 YouTube fixtures and two
Firefox checks passed. Local owner packages include the original 84 voices/8 BGM.
Install/update from `dist/chrome` or `dist/firefox`, then reload the extension and
video page so both the worker and early page hooks are replaced.
