# Multisite revision: 2026-11-04

## Confirmed gaps and reference evidence

The previous implementation captured Bilibili player responses but did not actively
request them when a response was missed. A source-to-blob swap could invalidate
captured data. Page-state fallback omitted videoData.subtitle.list. The reference
fetchPlayerResponse requests /x/player/wbi/v2 with aid/cid and browser credentials;
fetchLegacyPlayerResponse also supports /x/player/v2 on mobile. Its route resolver
distinguishes each part and rejects page state belonging to a different route.

The reference CC fallback activates the subtitle menu, selects a language to cause
the player to fetch the subtitle URL, and restores the prior off/language state.
Its selectors are .bpx-player-ctrl-subtitle-language-item[data-lan],
.bpx-player-ctrl-subtitle-close-switch (or fake-switch), with bpx-state-active.
Only subtitle resources requested during the operation may be associated with it.

The static catalog contains 159 routes and 158 string control-container selectors.
The existing generator omitted these selectors and Vocalm mounted a native control
only on YouTube. Shared player families (native tracks, Video.js, JWPlayer, Mux,
HLS, Wistia, Kinescope) account for many routes; these are not 159 independent APIs.
No executable reference code is copied.

## Implementation sequence

1. Introduce independently implemented Bilibili identity/metadata acquisition.
   Validate route and part, actively fetch metadata within the page session,
   accept only current CID, keep caches bounded, report empty/auth/network outcomes.
2. Add a bounded CC-resource discovery fallback with restoration on all outcomes.
   Never send page cookies or signed caption URLs to the backend.
3. Export factual control selectors and mount only beside the selected player.
   Retain the floating launcher when no unambiguous native anchor is available.
4. Validate with the actual packaged extension on labelled browser fixtures,
   preserve YouTube tests, then run public live checks and rebuild both browsers.

## Acceptance gates

- Direct metadata after missed early network response; authenticated fetch options.
- Correct p=1/p=2 CID, stale initial state, delayed old responses, source-to-blob swap.
- Primary/legacy endpoint failure, empty tracks, unsupported/session-required tracks.
- CC off/on restoration, failure restoration, changed route during acquisition.
- Current-frame ownership, multiple videos, native/shadow controls and remounting.
- Caption success sends real cue data to the job route; uncertainty sends no ASR job.
- Existing parsers, YouTube, progressive playback, voice picker and package checks.

## Live evidence before revision

Sample BV1WqYV6cEwq: anonymous playback has a 30-second preview, duration 741s,
aid 117250308704007, first CID 41774680995; the page lists 81 parts. Two observed
player responses had HTTP 200/code 0 and an empty subtitle list. Acquisition was
unknown. This is not a signed-in test and not proof of caption absence. Computer
Use cannot connect to the owner's browser; authenticated acceptance is outstanding.

## Additional live root cause and delivered revision

The isolated live browser redirected the supplied video URL to
`https://www.bilibili.com/en/video/BV1WqYV6cEwq/`. Both the original reference
catalog and Vocalm's old matcher omitted this locale prefix. Before the fix,
`rules` was empty and no native player button was mounted, independently of login.
Vocalm now normalizes Bilibili locale prefixes for routing/part identity while
preserving the actual page URL for acquisition ownership and navigation checks.

After the fix, the live probe matches the Bilibili adapter and mounts the player
button. Caption discovery returns `bili_session` in the anonymous profile. It is
not a successful authenticated caption extraction. Latest evidence is
`research/bilibili-live.json`; the earlier `multisite-live.json` includes the
pre-fix localized-route failure and the Apple/MDN public successes.

Vocalm 0.6.0 includes active authenticated UGC metadata lookup, per-part view
resolution when initial state is absent/stale, primary/legacy player endpoints,
CID validation, AI-language prefix normalization, page-state subtitle fallback,
and bounded CC-triggered subtitle capture with state restoration. Existing
epInfo is understood; a complete PGC/PUGV resolver and PUGV protobuf extraction
have not been ported. Those cases retain shared/native/menu fallback.

Native controls use the 158 factual selector candidates and shared Video.js,
JWPlayer, Shaka and Media Chrome bars, scoped to the selected video. Wrappers
containing the video are not treated as control bars. The floating launcher stays
available for unsupported/ambiguous containers. Open-shadow discovery now also
examines the root of a supplied custom element, preventing invisible unslotted
buttons on Mux wrappers. Buttons remount when a framework replaces its controls.

## Validation evidence

- 47 JavaScript and 58 Python tests passed.
- 17 actual-extension Bilibili fixtures passed: active/late metadata, localized
  URL, blob swap, missing/stale state, p=2, wrong CID, legacy retry, empty/session
  failures, malformed track URLs, CC off/on restoration, failed CC fetch,
  empty-menu cleanup, navigation during acquisition and part switches. Authenticated-fetch behavior
  uses a test-only browser cookie, never the owner's session.
- 19 multisite acquisition fixtures and 12 YouTube caption fixtures passed.
- 11 native-control layouts passed, including two videos, open shadow roots,
  unslotted-wrapper fallback and framework remounting.
- YouTube progressive playback/UI acceptance passed, including Ready gating,
  translated sidebar updates, ads, rapid seeks, cached replay and cancellation.
- Firefox 159 DOM/open-shadow native captions and CC restoration passed.
- Public live checks: Apple 360 cues, MDN 14 cues. Bilibili anonymous session
  now recognizes the page and reports session-required; Ahrefs' YouTube embed
  remains unknown. No paid provider dispatch or VPS disk writes were needed.

None of these results certifies all 159 routes individually. Bespoke APIs and
authenticated sites still need per-site acceptance. Reload both the extension
and video page after replacing the build so document_start hooks are current.
