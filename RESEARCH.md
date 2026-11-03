# Protein research ledger

Updated: 2026-11-03. Separate observed evidence, interpretation and unverified claims.

## Local observations

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
