# Qwen ASR incident and production verification

Date: 2026-11-05 (Asia/Bangkok).
Video: https://www.youtube.com/watch?v=f6YA_OvKbhY

## Root cause

The production job failed in alignment after271.831 seconds. Replaying the
supplied video's actual audio on Qwen reproduced the same failure at offset576s:
region7 word19 started at3.440s and ended at3.520s in a3.440-second VAD region.
The old50ms edge tolerance rejected the80ms model overrun and failed the whole
video. This was not a Deepgram exception or an automatic provider substitution.

The original failed request payload was already scrubbed by normal retention.
The error and stage remain, but its exact historical request fields are not
recoverable. The same-video replay provides the concrete reproduction evidence.

## Correction

- Clip finite edge deviations of at most120ms to the audio bounds. Retain text
  from zero-duration edge tokens in an adjacent aligned interval. Reject large
  overruns, NaN/infinity, reversed and nonmonotonic timestamps.
- When Qwen alignment remains invalid, align the same Qwen transcript once with
  stable-ts, then apply the same validation. This is timestamp recovery, not a
  second transcription or Deepgram fallback. Do not accept invalid recovery.
- Keep each video's windows on one warm Modal account. Existing key states and
  failover remain: unavailable/exhausted keys can move to another backend account.
- Record provider-start and per-Qwen-window completion events for diagnosis.
  Fast/quality source caches stay separate.

Deployed to all three backend Modal accounts and the Oracle VPS. The client
OmniVoice account was not changed. Both backend service health checks passed.
No database schema migration or credential change was required.

## Actual results

| Check | Observed result |
| --- | --- |
| Previously failing offset576 on accounts1/2/3 | Passed,94 aligned words each, valid times, model Qwen/Qwen3-ASR-1.7B |
| Tail offsets600/624/648 on account1 | Passed,87/86/42 words, valid times |
| Fresh signed quality request | Done in230.594s;28 Qwen windows;93 speech cues,2.112-660.8s |
| Provider evidence | Modal/Qwen start +28 completion events; no Deepgram events |
| Repeat identical request | Done in2.281s; cache events only; identical source/translation/output hashes |
| GPU account affinity | Backend account2 handled all28 windows; account1/3 usage counters unchanged |
| Temporary VPS files | Spool returned to0 bytes after completion |
| Automated regression |75 Python tests passed; includes routing, cache separation, account failover and timing boundaries |

Fresh job: `f8d194deabaf104e4e26562d411508c3`.
Repeat job: `0fbb0eddc24218c0debae164830852a5`.
Source hash: `36fa5f813e36ae533a5dc86d4b0d1ecdb48debe63bf91ac3bd58b6c7b7e6a43c`.

Evidence is in `research/qwen-incident-reproduction.json`,
`research/qwen-incident-fixed-account1.json`,
`research/qwen-incident-fixed-account2.json`,
`research/qwen-incident-fixed-account3.json`, `research/qwen-incident-live.json`
and `research/qwen-incident-production-evidence.json`.
Reports contain no API credentials, signed download URLs or transcript text.

## Practical limits

230.594s includes resolution/download, Qwen transcription/alignment of the full
video, and the first progressive translation unit. It is not near-realtime ASR.
The2.281s repeat measures cached retrieval with2-second polling, not fresh GPU
inference. Deepgram's earlier9.076s run is a different provider/path and cannot
be used as a Qwen speed claim. Other languages/audio and full TTS playback were
not re-certified by this incident's end-to-end test.

## Reproduce and recover

`tools/qwen_incident.py --account 1 --report <new-name.json>` runs the bounded
retained local audio tests and consumes GPU credit. `tools/asr_live_acceptance.py`
submits the signed quality request and repeats it; subsequent runs use source
cache, so inspect provider events before calling any result a fresh ASR test.
`tools/asr_job_evidence.py` reads the corresponding production usage evidence.

Backend rollback follows `docs/OPERATIONS.md`; retain the existing database and
keys. For a GPU rollback, redeploy the previous `gpu/asr.py` to accounts1-3 only.
That rollback reintroduces this alignment failure; do not roll back account4.
