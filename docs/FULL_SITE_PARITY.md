# Full reference parity work

Status: active. This document supersedes any interpretation that 0.6.0 completes
the user's all-site requirement. Do not mark a route accepted merely because its
domain matches or a generic VTT test passes.

## Evidence and approach

`tools/audit_reference_extractors.cjs` parses the supplied reference AST and resolves
factory aliases, inheritance and helper functions. Private excerpts stay in
`.private/multisite-research/extractors`; never execute or redistribute them.
`research/extractor-audit.json` indexes each family and its methods. Some factory
branches provide media identification/ASR only, not an existing-caption reader;
these must be documented explicitly rather than fabricated as successful readers.

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
  Platzi's base64 subtitles query fallback remains pending.
- Kajabi/Pendo: owned Wistia custom element media-id -> captions JSON. Added
  owner detection; their individual live/host fixture checks remain pending.
- JW/CoinDesk/Reuters/hosted: playlist tracks and HLS, some SDK caption lists;
  shared reader exists but exact SDK and per-site parity is still under review.
- Sonicwall/ServiceNow/MathWorks Brightcove: owned player.mediainfo.text_tracks;
  Aljazeera/Oracle additionally read player config and playback API. SDK path
  implemented; exact playback API fallback and live tests remain pending.
- ArtStation: current course/chapter hashes -> course API chapters[].subtitles;
  dedicated fallback not yet implemented.
- Mindvalley: HLS or associated MP4/VTT, rejects storyboard VTT. Domestika:
  current lesson HLS binding. Site-specific parity remains pending.
- Plex rewrites subtitle URLs; Medbridge uses custom HLS timing; Pluralsight
  filters its HLS requests; MightyNetworks/Nebula dedupe signed-URL emissions.
  Shared HLS passing does not certify these site-specific differences.
- Updraft uses JSON-LD Mux contentUrl; Patreon associates Mux URL with post;
  Tella refreshes signed manifest by story ID; Skool uses per-video playback token
  or Loom. Dedicated paths remain pending.
- Loom's reference fallback guesses timestamp units/ends for some transcript JSON.
  Do not copy this heuristic as verified timing; prefer existing VTT/explicit ends.
