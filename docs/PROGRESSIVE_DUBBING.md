# Progressive sentence dubbing (Veloa 0.4.0)

## Evidence and plan

Owner example: source cues end in "Good" / "We've", translations end in "Chao" /
"da". The previous prepare waited for every translation. Its mixer synthesized each display
cue, fits duration at 0.6-1.8x and uses current video time as a clip offset even when
the delay came from synthesis/stretch preparation. This can cut spoken prefixes.

Neko Dub local beautified content.js:8470-8590 identifies sentence punctuation,
ignores abbreviations, prefers commas for long segments, and uses bounded forced
splits. :25575-25680 prioritizes current-window translation/audio and reanchors on
seek. Existing reference analysis documents separate caches and bounded lookahead.
Veloa implements these principles independently, single voice only.

- [x] Reflow source cues into bounded sentence/clause units; split punctuation
      inside cues, carry dangling words into the following unit, preserve text.
- [x] Require natural punctuation and concise spoken translations, immutable
      server-owned timing, strict text bounds and a new cache version.
- [x] Prepare only the current unit; deliver source plan for whole-video study.
      Authenticated window jobs translate only nearby units with individual cache.
- [x] Prioritize playhead/seek, bounded translation and TTS prefetch; stop cancels
      work. Never synthesize untranslated source while a translation is pending.
- [x] Remove start-time clipping from ordinary playback, reduce stretch range,
      pre-fit audio, fade every clip (including unity speed), and fade manual stops.
      Allow at most 0.75 seconds of video drift before holding for complete speech.
- [x] Unit, integration and real-browser tests: startup before tail translation,
      seek preemption, cache reuse, no skipped syllables, punctuation boundaries,
      pause/resume, speed changes and bounded memory. Generate real sample audio
      and inspect objective waveform/timing evidence; state listening limitations.
- [x] Deploy backend, build extension, run live acceptance and record checkpoints.

Native/source-less ASR still needs acquisition before sentence planning. This change
must not claim streaming ASR or zero wait on a cold GPU/unprepared seek. Timestamp
allocation within a subtitle cue is estimated from text, not forced word alignment;
intra-cue boundaries stay within 0.75s of the nearest source cue edge when possible.
No DB schema migration; existing cache disk quotas and ticket isolation apply.

## Implemented limits and cancellation

- Startup translates and synthesizes exactly one speech unit at the selected position.
  Playback drives later work; a paused prepared video does not process the entire tail.
- Translation has one active job, requests one unit at a time, and fills at most six
  units within 35 seconds. TTS permits two pending calls and at most four units within
  30 seconds. The GPU still serializes model generation on one container.
- Seek reanchors both queues; obsolete results cannot enter current playback. Cancellation
  is best effort for remote work already accepted, not a promise to refund inference.
- Pause/Stop cancel outstanding work. Startup seek and Stop invalidate the old continuation,
  including a delayed HTTP submission. Changing voice preserves translated units.
- Speech cursor owns unfinished words even if the playhead has passed a short cue.
  Ordinary late playback starts at audio offset zero; explicit seek/start anchors and
  manual resume are the only cases that use offsets.
- Natural-duration synthesis replaces forced short-cue duration. WSOLA fits speech at
  0.92-1.22x before applying video speed (combined range 0.5-2x). Eight-millisecond fades
  cover unity-speed clips, joins and manual stops. GPU margin trimming remains in place.
- When speech falls behind by 0.75 seconds, video holds while the sentence finishes.
  This prioritizes complete speech over uninterrupted video if the GPU cannot keep up.
- Decoded original/fitted audio cache is bounded to 12 MiB; compressed audio continues
  to use the existing IndexedDB quota/TTL. Translations stay within server cache quotas.
  Full translated SRT export explicitly reports incomplete translation until all units
  are ready. Summary/chat can use the full source transcript before translation finishes.

## Measured evidence, 2026-11-03/04

The retained owner transcript has 595 display cues. Reflow produces 254 speech units,
preserves every source word and caps this sample at 13.128 seconds per unit. The
"Good morning" and "We've officially arrived" fragments remain together in a complete
spoken unit. Overlapping YouTube display lifetimes are normalized to next-cue start.

`research/progressive-live.json` records real VPS/Gemini and account-4 OmniVoice:
initial one-unit translation 1.969s, two following units 3.281s, seek translation
3.281s, replay 1.703s. Three TTS round trips were 29.906s, 7.531s and 6.516s.
These are single observations including transport/polling and local fitting, not
inference-only latency or a cold-start percentile. No claim of zero-wait startup.

All three fitted samples are finite with zero endpoints. Independent Nova-3 recognition
of concatenated natural versus fitted samples returned the same 67 words (zero edits),
including the first and last five words. This checks DSP word retention on these samples;
it does not certify model pronunciation or subjective sound quality.

The Chrome fixture runs use real MV3, HTML media and Web Audio with explicitly simulated
provider responses. Their subsecond startup is NOT real GPU latency. They verify bounded
lookahead, pause, forward/backward/rapid seeks, replay cache, startup seek cancellation and
Stop while preparing. Real Chrome and Firefox service tests also pass; Chrome additionally
checks voice A-B-A cache reuse, summary and chat. Unit totals: 51 Python and 32 JavaScript.

Remaining acceptance limits: subjective listening, long-video endurance and sustained
realtime throughput on dense speech. ASR-only videos still acquire their transcript first.
Timing inside a caption is estimated rather than word-aligned. Audio samples remain in
the ignored `.private/progressive-audio/` directory, including `sentence-comparison-new.wav`.

Final deployment verification in `research/progressive-deployment.json` compares all
four changed backend source hashes with the VPS. A real repeated window has one cache
hit and no translation usage event. Disk free space at that check was 198.84 GB decimal.
Storage quota, free-space reserve and cleanup settings remain active; this release does
not increase the VPS disk allocation or store synthesized voice clips on the VPS.
