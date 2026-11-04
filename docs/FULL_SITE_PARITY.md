# Full reference parity work

Status: broader acceptance deferred by the user on 2026-11-04. Current scope and
live evidence are in `docs/PRIORITY_SITE_ACCEPTANCE.md`; existing integrations remain.
This document supersedes any interpretation that 0.6.0 completes
the user's all-site requirement. Do not mark a route accepted merely because its
domain matches or a generic VTT test passes.

Current per-route ledger: `docs/SITE_ACCEPTANCE_MATRIX.md` with structured evidence
in `research/site-acceptance-matrix.json`. Older "pending" findings below describe
the initial audit; this batch implements the following paths without certifying
all real sites: ArtStation, Platzi, PandaVideo, Tella, Skillshare, Updraft, BBC,
Loom, Osmosis, Gaia, Brightcove playback fallback, Kollus, Skool, OK.ru, Sketchy
Cloudflare, Plex, direct DASH/VK, Dropbox, Circle, Movebox, MotionMagic, Patreon,
Vidlove movie and direct Drive embedded timedtext. Live and fixture gates remain
separate. Some reference handlers (Glo, Oba) explicitly have no subtitle reader.

Owner-supplied sample results: Platzi returns 45 Spanish captions but isolated
Chrome also fails video playback without Vocalm (error 4); playback is not signed
off. Skillshare returns HTTP403. Skool's /about URL embeds Loom, not a Skool
classroom module. Loom preview clips and thumbnail VTT were real bugs; both have
explicit regressions. Final Skool/Loom evidence is `research/skool-loom-live.json`.
The final Loom test has 55 English cues and a mounted native control on the real
189-second player. This does not certify Skool classroom modules.

Additional reviewed and implemented paths: current-clip Pluralsight master
filtering, Medbridge absolute course-clock segments, owned JW SDK caption IDs,
Mindvalley/Domestika attached source recovery and stale-manifest rejection.
They have labelled success/failure fixtures. Live CoinDesk sample has no usable
speech track; Reuters returns 401. Neither is counted as a successful extraction.

Latest companion-runtime pass adds Mindvalley MP4/VTT siblings, Domestika/Mindvalley
active lesson selection with pause retention, poster-bound Twitter GraphQL/card HLS
and Facebook owned React caption metadata. These have bounded reads and explicit
stale/denied/ambiguous/getter tests. There are 132 passing packaged mechanism cases,
15 native-control cases and 19 shared acquisition cases; these counts describe
fixtures, not websites. Twitter/Facebook live acceptance and recovery variants remain
open. Unit checks: 90 JavaScript and 61 Python; Firefox native/shadow/DASH/social
reader checks passed with the actual package.

## Evidence and approach

`tools/audit_reference_extractors.cjs` parses the supplied reference AST and resolves
factory aliases, inheritance and helper functions. Private excerpts stay in
`.private/multisite-research/extractors`; never execute or redistribute them.
`research/extractor-audit.json` indexes each family and its methods. Some factory
branches provide media identification/ASR only, not an existing-caption reader;
these must be documented explicitly rather than fabricated as successful readers.

Correction from the companion runtime audit: missing injectScript factory mappings
do not mean a platform has no caption reader. `content-scripts/content.js` contains
Twitter and Facebook readers and additional Domestika/Mindvalley player adapters.
`tools/audit_reference_runtime.cjs` records their class/method/source hashes without
executing or redistributing code. `research/runtime-extractor-audit.json` is joined
into the matrix. Universal player implementations remain an explicit review gap.

## Gates for every reader

1. Review the actual handler and helper implementation, not the routing name.
2. Record source schema, ownership key, timestamp units, credentials and fallback.
3. Implement independently with bounded bytes/requests and no credentials sent to VPS.
4. Test success, missing track, expired URL, denied session, malformed data, SPA,
   multiple players and stale requests where relevant.
5. Run the packaged extension for the actual source mechanism, then a public live
   sample or an authorized account sample. Label fixture and live evidence separately.

The whole request remains open until the matrix is accounted for. Authenticated
acceptance requires accessible lesson samples; asking for a URL does not authorize
cookie export or credentials sharing. Existing no-silent-ASR behavior is preserved.

## Reviewed implementation details

| Family | Reference mechanism | Ownership/timing | Planned implementation |
| --- | --- | --- | --- |
| udemy | j9 extends pd: intercepted lecture asset.captions; locale normalization | Lecture ID filters requests; VTT times | Current course module -> lecture API + course locale; prefer original language; live sample passed |
| egghead | rq: NEXT pageProps.videoResource.fields.srt / initialLesson.srt | Slug belongs to current lesson; SRT times | Prefer full SRT; do not invent last cue time from un-timed text |
| ted | iq: NEXT videoData.playerData JSON -> resources.hls.metadata -> subtitles[].webvtt | Current talk slug; Next data refresh after SPA | Exact metadata chain and strict slug validation |
| edx | oV/aV: closest .video[data-metadata], transcriptLanguages + transcriptTranslationUrl | Owned block; parallel start/end/text arrays in milliseconds | Fetch own block transcript and preserve milliseconds |
| datacamp | Mq/Cq/Lq: projector_key -> course ID + language-specific VTT URLs | Current projector key; VTT times | Bounded URL candidates from current projector key |
| substack | vj: _preloads.post.videoUpload.extractedAudio.transcription.cdn_url | video[data-video-id] must match; start/end seconds | Owned transcription JSON, exact CDN/path checks |
| internet_archive | SV: current JW playlist item + archive metadata sidecars | Current file stem association, never another item | Owned JW captions and associated SRT/VTT files |
| bloomberg | xG: selected skylight-vod media ID -> media-manifest/embed -> captions | Media ID; TTML times | Scoped element ID and manifest caption URL |
| rutube | XG: /api/play/options/{id}/ -> captions[].file | Current video path; SRT/VTT | Explicit options API reader |
| navertv | WG: NEXT vodInfo -> videoId/inKey -> play/v2.0 -> captions.list[].source | Current clipNo and source times | Own clip metadata; keep page key in browser only |
| cursor_blog | Qz: selected Mux player TextTracks | Owned player cue timestamps | Shared native/open-shadow reader |
| narto | t7: selected player TextTrack snapshots and transition stability | Slug/episode; cue times | Shared reader with completeness/transition checks |

No row in this table alone is a claim of implementation or live success.

## Authorized Udemy live result (2026-11-04)

Owner supplied lecture `/course/ccna-complete/learn/lecture/9538164` and authorized
cookie import. Separate Chromium/Chrome profiles reached HTML but received HTTP
403 from course/context APIs, so those runs did not establish caption access.
Owner then enabled Chrome's remote debugging and granted its consent prompt.
Connecting via the local DevToolsActivePort WebSocket reached the actual session.

Confirmed failure: the existing tab had no acquisition bridge and no native
TextTracks. Its resource timing buffer no longer contained lecture requests.
Relying only on interception/replay could never discover this video's captions.
The page's `course-taking` module still identifies course 1203374. A session-local
GET to its current lecture API returns 33 caption descriptors. The array starts
with German and contains multiple manual languages, so neither first-array-item
nor manual-first is sufficient to select the original English track.

Implemented current lecture + asset ownership checks, same-origin minimal-field
lecture GET, course locale lookup, then original-language-first ordering. Selected
caption labels provide a fallback when locale lookup fails; ambiguous results
remain unknown. Signed caption URLs and session cookies never go to the backend.

Installed the local Vocalm MV3 package in the authorized profile via Chrome's
Extensions.loadUnpacked, reloaded only the lecture, and restored pause/time.
Two full acquisition calls returned identical 72-cue English transcripts with
valid timing: 6.2 to 334.58 seconds in a 335.181356-second video. Evidence is in
`research/udemy-attached-live.json`; timings there measure acquisition only.
The native Vocalm player button is present. No translation, TTS, or ASR was called.

## Additional reviewed sources

- TED public live sample passed after adapting actual videoPlayerData object and
  excluding TED's #ad-container videos from content ownership. 427 English cues;
  button present. `research/platform-live.json` records the result. Feynman is
  HTTP 403 in the same public test run, so its live gate remains open.

- Vidyard: `VH` selects payload.chapters using active aria-label/poster videoId;
  Vocalm rejects ambiguous chapters instead of choosing the first. Fixture covered.
- Adobe TV: `yj` binds bridge humanID/viewBucketID to route /v/{id}; translations
  carry vttPath/language_locale. Fixture covered.
- Feynman: `SG`/mG/bG use active .videolink or title -> FMLCaptions[index].src;
  Vocalm omits the reference's unconditional first-lecture fallback. Fixture covered.
- Video.js/Lecturio/Platzi: attached player/player_, textTracks/remoteTextTracks,
  tracks_, src_/options_/track fields; owned-player descriptors now supported.
  Platzi base64/base64url subtitles query fallback now has fixtures and a live caption sample.
- Kajabi/Pendo: owned Wistia custom element media-id -> captions JSON. Added
  owner detection; their individual live/host fixture checks remain pending.
- JW/CoinDesk/Reuters/hosted: playlist tracks and HLS, some SDK caption lists;
  shared reader exists but exact SDK and per-site parity is still under review.
- Sonicwall/ServiceNow/MathWorks Brightcove: owned player.mediainfo.text_tracks;
  Aljazeera/Oracle additionally read player config and playback API. SDK path
  implemented with strict public playback policy fallback and fixtures; live access remains site-dependent.
- ArtStation: current course/chapter hashes -> course API chapters[].subtitles;
  dedicated fallback implemented and fixture-tested; live request was refused.
- Mindvalley: HLS or associated MP4/VTT, rejects storyboard VTT. Domestika:
  current lesson HLS binding. Site-specific parity remains pending.
- Plex wrapper rewriting is host-restricted. Medbridge absolute cue times now
  retain course timing and overlap deduplication within known duration. Pluralsight
  accepts only a current-clip master descriptor. MightyNetworks/Nebula reference
  overrides dedupe observable emissions; Vocalm uses explicit acquisition rather
  than those event streams. Live signed-URL renewal still needs acceptance.
- Updraft uses JSON-LD Mux contentUrl; Patreon associates Mux URL with post;
  Tella refreshes signed manifest by story ID; Skool uses per-video playback token
  or Loom. Dedicated readers now exist; per-site live gates remain open.
- Loom's reference fallback guesses timestamp units/ends for some transcript JSON.
  Do not copy this heuristic as verified timing; prefer existing VTT/explicit ends.
