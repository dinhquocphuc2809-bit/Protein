# Neko-derived OmniVoice latency work (2026-11-04)

## Evidence before implementation

Read the supplied Neko bundle, formatted background.js:5995-6120 and :7935-8040,
`research/raw/neko_colab_notebook.py` and `neko_modal_notebook.py`. These are ignored
local reference materials; the original package is unchanged.

Both Colab and Modal register a reference separately and send small per-sentence
requests by voice ID. Colab processes requested items sequentially; Modal allows
six concurrent HTTP inputs and three generation threads. The client uses six request
workers on Modal and one elsewhere. Missing server voices trigger one registration
retry. Both use 16 diffusion steps and Ogg output. Neither notebook proves true PCM
streaming or safe concurrent model use under every workload.

No Kaggle deployment/integration code was found in this supplied extension. It
contains Colab inference automation and a separate Colab notebook deploying Modal.
The earlier Voz review mentions Kaggle as an alternative; it is not evidence of
shipped Kaggle automation. Do not invent a third reference implementation.

## HAR analysis

`tools/analyze_neko_latency.py` reads all 725 entries in the supplied 49 MB HAR,
exporting only aggregate sizes, timing, field names and counts. No secrets, transcript
content, URLs with query tokens or voice audio enter the public report.

- 518 TTS requests; all send exactly one item, a voice ID and 16 steps. None sends
  inline reference audio. Request bodies: median 175 bytes, maximum 275 bytes.
- Only 16 separate reference uploads; median body about 306 KB. This is the useful
  distinction from Veloa's previous repeated 303 KB raw WAV (~405 KB base64 JSON).
- Recorded TTS latency median 6.463s, p95 10.727s. Most time is server wait;
  median request send time 0.154ms. HAR describes this recording, not a universal SLA.
- 12 translation requests include contextBefore, videoSummary, normalizePunctuation
  and language metadata. Four transcript calls include anchor/startup-window fields.
  Translation HTTP requests are sequential in this capture; TTS HTTP overlap peaks
  at 12. Overlap is not a measurement of actual GPU parallelism or seek behavior.
- Translation batches contain 8, 23 or 24 items; all request punctuation normalization
  and include a summary. Despite the field name, contextBefore is empty in all 12
  recorded requests. Veloa already sends surrounding source context; copying this
  empty field would not improve it. Veloa keeps one-unit startup/window delivery so
  a 24-item translation batch cannot delay the next spoken unit.
- No identical TTS JSON payload repeats in this capture. The server-reported elapsedMs
  median is 4.051s versus 6.463s HTTP median; it is not an independently verified GPU
  timer and does not isolate queue/network time. A slow reference upload includes
  ~20 seconds of browser blocked time, so it must not all be labelled upload speed.
- No captured WebSocket messages. Complete per-cue Ogg responses, not streamed PCM.

Detailed sanitized evidence: `research/neko-latency-analysis.json`.

## Implementation and checkpoints

- [x] CPU voice registry: SHA-256 identity, strict PCM WAV validation, 32 entries,
  16 MiB byte budget, 15-minute idle expiry. No reference files on VPS or public URLs.
- [x] Client shares in-flight registration across neighboring sentences, transmits
  reference IDs, and registers once again after server eviction/replacement.
- [x] Capability negotiation preserves old-worker compatibility and existing audio
  cache identity. Different endpoint/proxy identity gets separate registration state.
- [x] Bounded 10-second result waits reduce repetitive polling. CPU HTTP concurrency
  is 16 so result waits do not block cancellation/submission. GPU remains single-input.
- [x] Begin reference registration while extracting/translating captions, on CPU only.
  Seek/Stop during registration cannot submit the obsolete synthesis afterward;
  cancellation racing an accepted submission is reissued after acknowledgement.
- [x] Serialize submission/cancel for the same idempotency ID; completed cancellation
  cannot be overwritten by a late spawn response. Duplicate jobs never intentionally
  spend GPU twice. Cross-container persistence still uses Modal Dict.
- [x] Instrument submission body/validation/claim/spawn/save and GPU reference,
  inference, encoding and container initialization phases without recording text.
- [x] Deploy account-4 worker; source accounts 1-3 remain ASR-only.
- [x] Test CPU model snapshot through actual container retirement; reject as default
  because consistent restored startup improvement was not established.
- [x] Actual Chrome/Firefox real-provider regression; regional/seek fixtures and builds.

Existing sentence reflow, punctuation restoration, regional translation/TTS prefetch,
seek cancellation and separate translation/audio caches remain. No multi-speaker,
reduced-quality step count, permanent warm GPU or whole-video startup processing.

## First measured transport improvement

Same 168-character sentence and reference, old pipeline: submission 8.750s/6.562s,
audio received 26.281s/9.156s. New registered-reference pipeline before snapshot
experiment: submission 0.703s/0.609s/0.578s; audio received 22.188s/3.156s/2.812s.
Registration separately costs 4.500s once. Never omit that cost when discussing startup.
New synthesis JSON is 495 bytes in the diagnostic serialization. Worker inference:
1.767s first call, then 1.405s/1.376s, for roughly 8.2-second audio. Same T4 and 16 steps.
Samples are sequential and small, not production p50/p95 estimates or a controlled
cross-service comparison with the supplied Neko HAR.

Final actual Chrome requests for the short browser fixture are 193-194 bytes each,
all with reference_id and no inline audio. Chrome real service playback, replay,
voice A-B-A, summary/chat and Firefox playback pass. Full tests: 58 Python, 39
JavaScript. Unauthenticated health/register/synthesize return 401. Local packages
are Veloa 0.4.1 with the existing 84 voice variants and 8 BGM tracks.

After another CPU container placement, coordination slowed to ~2s submission despite
unchanged ~1.4s inference. Final deployment pins only the lightweight CPU ingress to
us-east, near default Modal RPC/Dict routing. GPU placement remains flexible. Final
warm request: 0.579s submission and 2.875s to audio receipt, ~8.21s generated speech.
An experimental first request after deployment took 20.266s plus 4.625s separate
registration; it includes snapshot creation and is not proof of fast restored startup.

The CPU snapshot experiment used CPU model loading in a snap=True lifecycle hook,
then transferred the model/tokenizer to CUDA after restore. GPU state was not snapshot.
It used 12 GiB for CPU loading; production returns to the measured 8 GiB GPU-direct
load configuration. min_containers=0 and scaledown_window=30 remain.
The 45-second idle-cycle probe did not actually retire the GPU (call counters continue),
so those cycles are warm evidence, not cold starts. Retain counters rather than
inferring actual shutdown from elapsed idle time alone.

After the container inventory was confirmed empty, another run took 35.718s to audio
receipt and still recorded a new CPU loading duration. System logs showed snapshot
creation, not a confirmed restored snapshot. The final deployment therefore removes
snapshot hooks; this optimization is not advertised as shipped or proven.
During rollout, one probe briefly hit the old container (recorded snapshot field)
before subsequent requests used the new worker. `tts-latency-final.json` preserves
this evidence rather than classifying that first response as a clean cold measurement.
The new worker's first call was 22.422s; its next warm call 3.406s with inference 1.368s.
First setup remains a limitation. Future snapshot work needs repeated actual restore
evidence and a stable latency benefit before enabling it by default.

Cost detail: Modal's official region documentation applies a 1.75x multiplier to
the pinned narrow-region CPU function. This is limited to 0.25 CPU/512 MiB ingress;
the GPU has no region multiplier or permanent warm allocation. Account $0 spend cap
remains as confirmed by the owner; this optimization does not change billing limits.

## Official documentation consulted

- https://modal.com/docs/guide/concurrent-inputs : concurrency for I/O-bound CPU
  ingress; no assumption that parallel GPU inference improves throughput.
- https://modal.com/docs/reference/modal.FunctionCall : bounded asynchronous get
  timeout, explicit cancellation; SDK notes get is not cancellation-safe.
- https://modal.com/docs/guide/memory-snapshot : CPU model load before snapshot,
  GPU move after restore; avoid accidental CUDA initialization before snapshot.
  GPU snapshots remain alpha and are not required by this implementation.
- https://modal.com/docs/guide/region-selection : default us-east input/output routing,
  container selection pricing, and restrictions on changing routing_region. Keep the
  existing public endpoint and routing region; pin CPU container placement only.

Fresh official pages were retrieved directly and retained under ignored
`research/raw/latency_modal_*.txt`; the web connector was unavailable.
