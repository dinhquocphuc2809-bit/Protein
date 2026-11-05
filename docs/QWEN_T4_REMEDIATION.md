# T4 performance and subtitle remediation

Started 2026-11-05. Target: T4, 2 vCPU, 16 GiB requested host memory.
Implementation and scoped acceptance completed; production rollout verified below.

## Implementation plan and acceptance gates

1. Preserve the prior 375-window T4 run and exact input audio as the control.
   Reduce 375 sequential RPCs to 94 bounded groups of at most four windows. Batch
   VAD regions through one model instance; compare inference batch1/2/4 on identical
   audio. On GPU allocation OOM retry the bounded group serially, never another ASR.
2. Match overlapping text with timing support and select one whole-token seam.
   Preserve genuine repeated characters; never globally remove repeated words.
   Reject seam substitutions between conflicting acoustic hypotheses and retain
   conservative time ownership for unresolvable seams. Record unresolved counts.
3. Retain Qwen's original recognized segment text and project its punctuation onto
   aligned word boundaries without replacing lexical content or timestamps. Join
   CJK characters appropriately. Use natural punctuation, pause boundaries and an
   eight-second safety bound for Qwen source cues; mark an unfinished safety split
   with a comma rather than pretending it completes a sentence.
4. Build a video-scoped terminology plan before progressive translation. Extract
   named individuals separately from homophone repairs. Preserve evidence IDs;
   validate observed aliases, canonical-name presence, approximate pronunciation,
   digit/negation protection, and bounded entries. Named spellings can be applied
   throughout this video; ASR repairs apply only to cited source cues. Log edits,
   retain the raw ASR cache, and include plan/version in translation cache identity.
5. Supply the immutable plan to each translation request, including seek requests.
   Enforce exact target names with bounded repair attempts. ASR glossary target
   wording is not authoritative: only corrected source terms/evidence guide the
   translator, avoiding propagation of a bad standalone glossary translation.
6. Snapshot initialized GPU state, set configuration in the actual container image,
   keep min_containers=0, and verify restored initialization UUID with a different
   boot UUID and request counter1 after retirement. A log line alone is insufficient.
7. Gate production rollout on unit/integration checks, the full long-video pass,
   real terminology/translation samples, multilingual/fallback checks, resource
   limits, and live signed backend requests plus cache/usage provenance. Deploy
   backend accounts1-3 only. Account4 remains client TTS.

## Test matrix

| Area | Required evidence |
| --- | --- |
| Seam merger | Four retained duplicate cases; mama/repeated words; timing jitter; tokenization differences; silence; invalid bounds; conflicting text |
| Formatting | Source words/times preserved; Chinese no inter-character spaces; punctuation retained; English/Vietnamese word spacing; bounded cue/speech-unit duration |
| Terminology | Reject unrelated species and invented aliases/names; protect numbers/negation; keep two recurring names stable across seek order; explicit source edits |
| Translation | Real Chinese audio-derived source at previous error positions; no bird substitution in takin passage; elephant context; exact cached names |
| T4 throughput | Same eight sample windows, then all375 windows/8996.72s; wall and worker timing separate; no OOM/restarts; RSS/VRAM tracked |
| Snapshot | No warm-container confusion; repeated restore after zero containers; source hash/config recorded; restored multilingual/fallback requests |
| Backend | Qwen provenance/no Deepgram substitution; cancellation cancels remote work; lease/cache lock renewal; new cache version; repeat uses cache |
| Operations | Three backend deployments; min0/idle retirement; read-only health/usage/disk check; rollback retains database and source artifacts |

## Early measured findings

- Inference batch1 over eight selected windows:36.178s worker; batch4:25.189s,
  about30.4% less. Snapshot creation and container restarts confound sample wall
  comparison, so use the full run for total-time conclusions.
- Batch2/4 differs from batch1 at one sampled character: Chinese third-person
  pronoun (human/animal written form), same pronunciation. Do not claim bit-identical
  recognition or improved acoustic accuracy from batching.
- The first model-driven glossary proposed an unrelated species replacement.
  It was rejected before rollout. Added phonetic/length constraints and separate
  entity extraction. A large high-thinking glossary call also truncated; the
  bounded structured Gemini3 analysis now explicitly requests LOW thinking.
- The corrected snapshot configuration has repeated initialization UUIDs across
  retired boots. First observed restore10.148s versus42.226s initialization; more
  cycles and final reports determine the actual accepted range.

## Completed measurements

| Metric | Prior T4 | Optimized T4 |
| --- | ---: | ---: |
| Full8996.72s input / windows | 375 | 375 |
| RPCs | 375 | 94 |
| Client wall | 1919.939s | 963.742s |
| Worker processing | 1215.673s | 702.669s |
| Peak host RSS | 9.489GiB | 8.690GiB |
| Peak PyTorch reserved VRAM | 6.980GiB | 6.947GiB |
| Worker containers during full run | 1 | 1 |
| Successful alignment recovery | 1 | 1 |

Worker time fell42.20%; observed wall fell49.80%. The prior wall included its
initial cold request; the new throughput run followed explicit startup cycles.
Adding the measured10.15-14.98s restore sample to963.74s is an estimate, not a
second measured full cold run. Download, normalization, terminology and translation
are excluded from both ASR benchmark wall values. The earlier sample/full probe
image did not propagate the snapshot flag into remote module imports, so its
system restore logs alone do not prove restored model initialization. The dedicated
corrected-image experiment below establishes that independently.

Corrected snapshot experiment: five retired boots, one initialization UUID,
call1 for each; initial42.226s, four confirmed restores10.148/14.984/12.965/13.748s.
Four system restore log entries agree. Snapshot coverage may require fresh
initialization on other hosts; these values are observations, not guaranteed limits.
The final multilingual regression also verified Vietnamese from a known snapshot
initialization after retirement,23.265s including lazy alignment-fallback loading,
identical word/timestamp output. English, Vietnamese, Chinese recovery and mixed
English/Chinese/silent inputs pass bounded-output checks. English and Vietnamese
samples use synthesized speech, not human ground-truth benchmark recordings.

Final backend replay over all new outputs:1510cues,1364speech units, zero missing
end punctuation and zero CJK inter-character-space cues. All1864 raw recognized
segments contain punctuation, now retained through alignment. Four duplicate
regressions pass and genuine mama remains.139 silence seams/219 text-time anchors;
14 unresolved and2 conflicting seams use conservative temporal ownership. They
remain uncertainty telemetry, not silently certified lexical correctness.

Real translation checks on the new ASR source pass stable Dolly/Dai A target
names, no bird in the takin passage, elephant context and loris rather than owl.
These are eight targeted outputs; not a full-video semantic score. Source aliases
and suggested repairs stay inspectable, and source timestamps are unchanged.

Evidence: research/benchmarks/qwen-optimized-summary.json,
qwen-optimized-full.json, qwen-optimized-restore.json,
qwen-optimized-multilingual.json and research/qwen-terminology-live.json.
All isolated experiment apps are stopped with zero containers.

## Production rollout and end-to-end acceptance

- SnapshotON, T4,2vCPU/16384MiB, inference batch4, at most4audio windows/RPC
  deployed to all3backend accounts. Each passed a real Qwen batch call. Account4
  was not touched. Production min_containers=0/scaledown_window=30.
- Final backend release: `/opt/auvirel/releases/20261105-102325`. Public and
  Tailscale admin health checks pass. Five deployed backend source hashes match
  local files. Previous baseline rollback release:20261104-172611.
- Real signed f6YA_OvKbhY:153.219s initial,28Qwen windows,184speech cues;
  repeat2.250s. Real signed7jb0q3Mo9Rg:190.500s initial,34Qwen windows;
  repeat2.266s. All timestamp/ID/nonempty checks pass. Usage shows Modal Qwen
  and no Deepgram; both repeat jobs show cache events only.
- Signed seek positions300/0/540/300/540 preserve source text, IDs, timestamps
  and translation identity. Repeat300/540 responses match earlier hashes and
  usage confirms cache only; no repeated ASR or translation provider call.
-113Python tests pass, including permanent real seam fixtures, jitter, genuine
  repetition, terminology validation/repair/model selection, cache reuse, long
  operation cancellation, lease renewal and capacity-timeout account failover.
- Account3's first deployment smoke took159.191s because Modal explicitly logged
  waiting for T4 capacity. Other first calls took38.543/90.183s. A new image/host
  may create a snapshot first; do not present restore timings as a universal SLA.
- Final check: all3production apps deployed with zero containers/tasks; zero
  active VPS jobs, zero spool bytes,198714048512disk bytes free. Application cache
  and spool limits remain4GiB/8GiB with30GiB reserve and80%high-water protection.

Evidence: research/qwen-optimized-rollout.json, qwen-optimized-first-live.json,
qwen-optimized-second-live.json, corresponding `*-evidence.json`,
qwen-optimized-seek-live.json/seek-evidence.json and qwen-optimized-final-state.json.
The live checks exercise the signed extension-facing API; no browser UI or human
listening acceptance is claimed by this backend-only change.

## Limits and rollback

No automatic ASR/LLM pipeline guarantees zero semantic errors on arbitrary future
videos. Proper-name spelling consistency is not proof of the original canonical
spelling. The phonetic guard rejects unrelated rewrites; it does not prove the
remaining corrections are true. Uncertain seam/semantic cases remain explicit.

The terminology pass uses the configured advanced Gemini model with LOW thinking
when ordinary translation selects basic Gemini; DeepSeek remains DeepSeek. Two
bounded analysis calls are cached once per source/model/target/title/ticket. Voice
changes reuse the same plan and translations. This adds a measured preparation
cost, not an additional call for every dubbed sentence.

Basic translations containing terms flagged as ASR homophones use the configured
advanced model with LOW thinking for that batch. Ordinary cues retain basic. This
avoids a second inaccurate literal interpretation of an already repaired word;
the translation is cached normally, including when changing voice or seeking.

Roll back the backend release symlink using the previous release and redeploy the
previous gpu/asr.py on accounts1-3 if live acceptance fails. Preserve database and
raw source caches; source-quality version2 and translation prompt2 prevent silently
serving the old faulty cache as a fixed result. No permanent warm GPU is required.
