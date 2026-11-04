# Second Qwen video: live acceptance

Date: 2026-11-05 (Asia/Bangkok).
Video: https://www.youtube.com/watch?v=7jb0q3Mo9Rg

## Result

The deployed fix completed this second video without an alignment exception.
No additional production change was needed. The test submitted a real signed
request with `asr=quality`, automatic source language, Vietnamese target and
progressive translation; no pre-existing subtitles were supplied.

| Measurement | Observed |
| --- | --- |
| Actual normalized audio | 817.0173125 seconds (13:37) |
| Initial request | 312.047 seconds (5:12), including first translation unit |
| Qwen execution | 34 windows, offsets 0 through 792 in 24-second steps |
| Output | 94 speech cues, 10.656-727.6 seconds |
| Repeat | 2.265 seconds, cache only, identical output hash |
| Provider | Modal/Qwen; no Deepgram usage events |
| Account | Backend account 3 handled all 34 calls; accounts 1/2 unchanged |
| Temporary storage | VPS spool returned to 0 bytes |

Initial job: `aa1ae19ddba277da65bf1bd77cec29bd`.
Repeat job: `5a492f060709b2fb127547f4b3af90b4`.
Source SHA256: `b7502959cf60b02e33708609d7a9646e7ae00250a77a0f7bd64c1a72584d8cb5`.

All returned cues have nonempty text, unique IDs, ordered nonoverlapping intervals
and timestamps within the actual normalized audio duration. Provider usage proves
the initial request performed Qwen inference and the repeat did not call ASR.
This is not an inference based only on response speed.

## Why subtitles stop before the video ends

The last cue ends at 727.6 seconds, so the final audio was investigated separately.
An actual sample-level PCM scan found exact digital silence from 728.822438 to
815.549188 seconds: 86.72675 seconds. Brief nonzero signals remain at either end.

A separate Gemini 3.5 Flash Lite audio audit of 728 seconds through the end
reported no intelligible speech. That is a machine assessment, not human listening.
Its generic music description should not override the measured digital silence.
This QA call did not replace Qwen or populate the production transcript.

## Evidence and scope

- `research/qwen-second-video-live.json`: signed requests, durations, cues and hashes.
- `research/qwen-second-video-before.json`: pre-run account/storage counters.
- `research/qwen-second-video-during.json`: live WAV duration and Qwen-start event.
- `research/qwen-second-video-production-evidence.json`: final provider events.
- `research/qwen-second-video-audio-levels.json`: PCM levels and exact silence span.
- `research/qwen-second-video-tail-audit.json`: independent machine audio assessment.
- `research/qwen-second-video-verification.json`: all final assertions passed.

Reports omit credentials, signed media URLs and subtitle text. Local diagnostic
audio stays in the ignored `.private/asr-second-video` folder.

This run verifies ASR, timestamp structure, initial progressive translation,
cache repeat and storage cleanup. It does not certify every recognized word or
full TTS/audio playback. First-run Qwen remains substantially slower than cached
retrieval; the cache timing is not a fresh-inference benchmark.

## Reproduce

```powershell
.venv/Scripts/python.exe tools/asr_live_acceptance.py --url "https://www.youtube.com/watch?v=7jb0q3Mo9Rg" --report qwen-second-video-rerun.json --timeout 1800
.venv/Scripts/python.exe tools/asr_job_evidence.py --live qwen-second-video-rerun.json --report qwen-second-video-rerun-evidence.json
```

Subsequent identical requests normally hit cache. Check provider events before
classifying a rerun as fresh recognition. The runner also rejects non-YouTube
hosts, timeouts above 1800 seconds and report path traversal before authentication.
