# Qwen acceptance: kp_IQITWg74

Date: 2026-11-05. Video: https://www.youtube.com/watch?v=kp_IQITWg74

The input is a CCTV Chinese documentary about giant-panda rewilding, lasting
2457.588375 seconds (40m57.59s). This test explicitly exercises Qwen ASR even if
the platform offers captions; it does not change the extension's caption-first policy.

## Failure found and fixed

The first real signed backend job failed after 412.219s and 76 completed audio
windows with `ValueError: tuple.index(x): x not in tuple`. The Modal traceback
points to Whisper tokenizer construction during forced-alignment fallback.

An isolated T4 reproduction using the exact four windows 76-79 reproduces the
failure. Qwen identifies two short utterances as Cantonese. The loaded Whisper
small model has 99 language tokens; Cantonese/yue is the 100th language in the
installed tokenizer table. Passing yue to this model fails in `langs.index`.
This is a tokenizer/model compatibility bug, not evidence of GPU/RAM exhaustion.

`gpu/alignment.py::whisper_alignment_language` now checks the language list for
the actual loaded model. It uses zh tokenization for yue only when that model
lacks yue and supports zh. A model that supports yue keeps yue. Filipino maps to
tl, supported languages remain unchanged, and unknown cases raise an explicit
error. The fallback aligns the original Qwen transcript; it does not replace
Qwen with Whisper transcription or Deepgram.

The same four-window T4 reproduction after the fix returns 81/103/118/100 word
items, with two successful alignment recoveries and valid timestamp bounds.
The isolated before/after apps were stopped with zero containers. All 121 Python
tests pass, including eight new language compatibility cases.

All three backend accounts have the fix and each passed a real English batch
smoke. T4/2vCPU/16GiB, batching and snapshot settings remain enabled; client
account 4 was not used. No backend/extension release change is necessary for this
worker-only bug fix.

## Input and independent references

The exact production-normalized audio was copied read-only over pinned SSH while
the first job ran, rather than paying for another media-link lookup. It is stored
locally under ignored `.private/qwen-kpIQITWg74/` (78,642,906 bytes); the VPS spool
was automatically cleared when the failed job ended.

- Gemini gemini-3.8-flash: nine blinded 28s clips, 252 seconds total, spread over
  offsets 24/300/600/900/1200/1500/1800/2100/2400.
- Deepgram nova-3/zh: six overlapping blinded clips,168seconds, independently
  checking the opening, names, figures and ending. These are audit references,
  not production ASR fallback calls. Their duration is not additional coverage.
- A Gemini reference response initially had no candidates; retry completed only
  the two uncached clips. All nine references subsequently completed.
- No human listening, manually verified transcript or CER/WER claim is made.

## Evidence

- `research/qwen-kpIQITWg74-input.json`: exact input duration/hash and acquisition.
- `research/qwen-kpIQITWg74-live.json` / `*-evidence.json`: original failed job.
- `research/qwen-kpIQITWg74-language-before.json` / `*-after.json`: isolated reproduction.
- `research/qwen-kpIQITWg74-rollout.json`: three-account deployment and smoke.
- `research/qwen-kpIQITWg74-sources.json`: official tokenizer/language sources and hashes.
- `research/qwen-kpIQITWg74-gemini.json` / `*-deepgram.json`: reference sample metadata.

Full production retry is recorded separately in `qwen-kpIQITWg74-retry-live.json`;
the initial failure report must not be overwritten or counted as a pass.

## Completed full retry and cache checks (before numeric fix)

After the tokenizer fix, real job df68467c2bc93ef27c337e25ea2b8ef6 completed all
103 audio windows in 613.156 seconds (10m13s). This includes acquisition,
normalization, Qwen recognition/alignment, terminology and the initial translation
window; it is not GPU-only time or time to translate the entire video. Repeat
job a9bf595ec852f418b29108423d443b1a completed in 2.250s using cache.

The source contains 795 cues and 674 speech units. Structural checks found valid
ordered timestamps, no missing final punctuation and no CJK inter-character space
defects. Five seeks at 1200/24/2400/1200/2400s took 1.688-3.266s. Translation
retained source IDs/timestamps; repeat hashes matched. Usage logs show no ASR on
seeks and no production Deepgram fallback. The 24s seek covered one cue, not the
problematic number at 33s; the final seek suite explicitly covers 33s.

## Second defect: decimal removed after correct recognition

At 32.736-35.936s the output stated 193 ten-thousand square kilometers instead of
1.93 ten-thousand square kilometers: a factor of 100. Both independent references
supported the decimal. An exact isolated T4 run of window 1 then proved the root
cause: Qwen's raw transcript says 1.93, while its forced aligner returns a single
193 token. The punctuation projector only restored separators at token edges,
so the internal decimal disappeared. This was not a mistaken Qwen acoustic output.

The fix matches the entire numeric digit span against the raw Qwen transcript
before restoring decimal/group separators. When a number spans multiple aligned
numeric tokens, it joins their text and keeps their enclosing time interval.
Different digits are not repaired by guessing; complete lexical coverage and
whole-span correspondence are required, including the repeated-number ambiguity guard. Decimal separators are excluded from generic sentence-edge projection
so a split number cannot accidentally produce a new sentence.

The exact post-fix T4 replay changes only 193 to 1.93, preserving all 106 word
intervals exactly. Eleven numeric regression cases and the existing suite pass:
132 Python tests total. Qwen source-cache version 3 prevents old corrupted source
entries from being reused for new jobs; old records remain under normal retention.
Three backend worker smokes passed with the numeric fix. Client account 4 is unused.

## Semantic findings and acceptance boundary

The sample review covers 252s, approximately 10.25% of this 2457.59s video, not its
entire duration. The 168s of Deepgram clips overlap the Gemini clips. References
are independent model hypotheses, not a manually verified gold transcript.

- The decimal corruption is confirmed by raw Qwen plus both reference systems;
  the deterministic pipeline fix is separately reproduced before/after on GPU.
- Around 35m06-35m29, dialect/technical interview phrases for population status,
  ecological corridor construction and geographic names remain inaccurate or
  uncertain. Context repair corrects one release-to-wild homophone, but does not
  establish that every phrase is correct. Deepgram also struggles in this sample.
- At 40m25, Qwen's phrase means an increase in value where the family/children
  context and another reference suggest having children. This is a likely
  recognition homophone error; no human-confirmed correction is claimed.
- Other disagreements include mountain-bottom vs mountain-top near 10m and a
  feeding homophone near 30m. Person-name spellings disagree across references;
  consistent glossary spelling alone does not prove the name is correct.
- At 15m, Gemini itself corrupts a programme title that Qwen/Deepgram agree on.
  Therefore replacing Qwen wholesale with a reference model is not justified.
- Structural pass flags describe execution, formatting, bounds, seek and cache
  behavior. They do not certify full semantic accuracy or dubbing/listening quality.

No new TTS/audio-mixer acceptance is claimed in this ASR-focused test. No complete
WER/CER, manually listened-through transcript or measured peak GPU/CPU/RAM from
this video is available. Successful completion shows no observed OOM failure; it
is not a measured memory-usage benchmark.

## Additional evidence

- `research/qwen-kpIQITWg74-retry-live.json` and `*-retry-evidence.json`: full retry.
- `research/qwen-kpIQITWg74-acceptance.json` and `*-seek-evidence.json`: first seeks.
- `research/qwen-kpIQITWg74-language-numeric.json` and `*-numeric-fixed.json`:
  isolated numeric runs (raw text stays in ignored private evidence).
- `research/qwen-kpIQITWg74-numeric-fix.json`: exact before/after numeric token/time.
- `research/qwen-kpIQITWg74-numeric-rollout.json`: initial decimal-fix rollout;
  the final guarded rollout is recorded below.

## Final deployed acceptance

The final guarded worker is deployed on all three backend accounts, with T4,
2vCPU, 16GiB, batch 4 and snapshot enabled. Each account passed both the English
smoke and the exact decimal clip, retaining its original word interval. VPS
release 20261105-111816 matches the local hashes of jobs.py and asr_text.py.
A 103.609s candidate test was deliberately cancelled to add the ambiguous-number
regression guard; it is preserved separately and is not counted as a pass.

| Check | Observed result |
| --- | --- |
| Full final job bcbedc1697d92dca907e6d56d4c36479 | 552.954s, 103/103 windows |
| Cache repeat 38e6509b5a020bf81ab8926d69781095 | 2.312s, cache-only events |
| Source/voice units | 795 raw cues / 674 speech units |
| Raw source change against previous full run | Only 193 -> 1.93; all timestamps identical |
| Final terminology plan | 30 terms / 38 edits; not 38 independently certified corrections |
| Three-cue seeks at 1200/33/2400s | 4.844 / 4.906 / 4.844s |
| Repeated three-cue seeks | 1.703s each; identical response hashes |
| Numeric translation at 33s | Vietnamese response gives 19,300 square kilometers |
| Backend Modal containers after testing | 0 / 0 / 0 |
| VPS spool / free disk | 0 bytes / 198,497,558,528 bytes |
| Python tests | 132 passed |

The 552.954s time covers acquisition through initial translation readiness. It
is not a promise of immediate subtitles for an uncached 41-minute video and is
not the time to translate every cue. Subsequent translation remains on demand.
All six final seeks preserve source identity/times; fresh windows use translation
and cache events, repeats use cache only. Production provenance contains no
Deepgram ASR. The separate Deepgram audit calls are recorded as references.

The final raw source still contains the sampled interview errors. The regenerated
terminology plan changes the ending's increase-in-value homophone to reproduction;
that does not establish a verbatim, independently verified having-children phrase.
The execution, numeric-preservation and cache checks pass; full semantic accuracy
remains unproven and the documented residual recognition errors remain.

Final evidence:
- `research/qwen-kpIQITWg74-final-rollout.json`, `*-final-backend.json`.
- `research/qwen-kpIQITWg74-final-live.json`, `*-final-evidence.json`.
- `research/qwen-kpIQITWg74-acceptance-final.json`, `*-final-seek-evidence.json`.
- `research/qwen-kpIQITWg74-source-diff.json`, `*-quality-review.json`.
- `research/qwen-kpIQITWg74-final-resources.json`.

