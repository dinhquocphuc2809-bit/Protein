# Long-video Qwen T4 / A10 comparison

Date: 2026-11-05 (Asia/Bangkok). Both full runs completed successfully and both
isolated apps are stopped with zero tasks/containers. Production is unchanged.

## Results

| Measurement | T4 / backend account1 | A10 / backend account2 |
| --- | ---: | ---: |
| Complete audio duration | 2h29m56.72s | 2h29m56.72s |
| Processed windows / expected | 375 / 375 | 375 / 375 |
| Client wall time | 1919.939s (32m00s) | 1677.023s (27m57s) |
| Sum of worker processing | 1215.673s (20m16s) | 722.531s (12m03s) |
| Recognition stage | 930.534s | 540.032s |
| Qwen alignment stage | 109.308s | 65.634s |
| Silero VAD stage | 165.869s | 110.634s |
| First RPC including startup | 28.968s | 21.826s |
| Model load inside container | 17.693s | 10.703s |
| Average process CPU cores during calls | 1.132 | 1.162 |
| Peak process RSS including initialization | 9.489 GiB | 9.471 GiB |
| End-of-run process RSS | 8.688 GiB | 8.844 GiB |
| Peak PyTorch allocated VRAM | 6.665 GiB | 6.663 GiB |
| Peak PyTorch reserved VRAM | 6.980 GiB | 6.789 GiB |
| Sampled peak total device memory used | 7.114 GiB | 7.081 GiB |
| Available device memory reported | 14.571 GiB | 22.058 GiB |
| Failed windows / OOM observed | 0 / 0 | 0 / 0 |
| Successful alignment recovery | 1 | 1 |
| Containers used, with sequential call numbers | 1 | 1 |

A10 reduced worker processing time by40.57% (1.683x throughput), while total
client time fell12.65% (1.145x throughput), saving242.916s, approximately4m03s.
Do not present the worker speedup as the user's total waiting-time speedup.
Total time includes375 sequential RPCs; measured non-worker overhead is about
704.266s for T4 and954.492s for A10. This remainder is not a pure network timer.
The requests also used automatically placed, different hosts, so CPU/VAD and
placement differences contribute; not all measured gains isolate GPU hardware.

T4 completed the long video without memory exhaustion. These measurements do
not support lack of VRAM capacity as the cause of its slower processing here.
Increasing file duration does not require retaining the full audio in GPU memory
with the bounded-window pipeline. Both runs were faster than playback: client
real-time factors0.2134(T4)/0.1864(A10), excluding download and normalization.

At offset3960s (66m00s), both GPUs successfully used the existing stable-ts
alignment recovery on Qwen's transcript:12.773s T4 versus7.761s A10. No ASR
provider substitution occurred. Loading that fallback model once raised process
RSS from roughly7.4-7.5GiB to8.7-8.8GiB. In the second half, fitted RSS growth
was only0.000120/0.000427GiB per audio hour, respectively. This is a plateau
after lazy model loading, not evidence of an accumulating leak.

The joined transcripts contain the same13905 retained word items and1093 cues.
Final word-text sequences match exactly. Final timestamps differ by at most
0.080s (mean absolute delta0.00001726s), so whole-output hashes are different.
Raw per-window outputs differ in9 windows:8 timing-only differences and1 text
difference at offset3768s. The differing raw token falls in the discarded overlap;
it does not change the final retained transcript. These are consistency checks,
not a human word-error-rate/semantic accuracy audit.

Both transcripts' last cue ends at8943.2s, while every window through8996.72s
was still processed. Tail-level diagnostics show the final53.52s is not entirely
digital silence. No human speech audit of that tail was performed; do not infer
that every empty recognition region has been independently proven speech-free.

This completes the requested long-file reliability/performance comparison for
this one Chinese video and one full pass per GPU. It does not find the maximum
possible batch/concurrency capacity or establish an SLA across all videos.

## Controlled method

The owner supplied YouTube video `YGi-aPUsZrQ` to test sustained processing of
nearly 2.5 hours of audio. Tunelio returned an audio-only Opus stream; ffprobe
verified there was no video stream. The source duration is8996.741s and the
normalized PCM duration is8996.72s (2h29m56.72s). Downloaded bytes:129118653;
mono16kHz PCM16 WAV bytes:287895118. Download took42.556s and normalization10.220s.
The Opus source was removed after normalization. Audio is stored locally on
Windows, not on the Oracle VPS.

T4 uses backend account1 and A10 uses backend account2. Client TTS account4 is
not used. Actual reported hardware names are Tesla T4 and NVIDIA A10. Previous
L4 allocation failures are not evidence of a signup/account restriction; the
owner authorized another stronger GPU, and the documented A10 type allocated
successfully. This is not a T4/L4 benchmark.

Both isolated apps use exactly the production Qwen3-ASR-1.7B load/transcribe
methods, pinned model revisions, FP16, SDPA, Silero VAD and forced alignment.
They request2vCPU/16384MiB RAM, min_containers=0,max_containers=1 and
scaledown_window=30. Snapshots are disabled for both variants so this measures
GPU choice without mixing snapshot restoration into one side. No production
deployment is changed. No Deepgram, translation, TTS or transcript cache is used.

Both clients read the same hashed WAV file incrementally. Each RPC receives at
most28s/896044 bytes of audio, advancing24s with overlap. A local coverage check
verifies375 windows, continuous ownership intervals and coverage through the end.
The GPU never receives the entire2.5-hour file at once. This matches production's
bounded-window strategy; it does not test single-request transcription of hours
of audio or intentionally increase batch size until OOM.

Each GPU runs one sequential complete pass in its own container, while the two
accounts operate concurrently. First-call latency includes initialization. Client
wall time excludes media download, normalization and image preparation; it includes
all RPCs, result validation and writing diagnostic output. Worker timing includes
VAD, recognition and alignment. Scheduling/network/serialization and local report
I/O contribute to the difference between client and worker time. These timings
are from the local Windows client, not the VPS or the extension user interface.
Modal chooses placement automatically. The two accounts can receive different
hosts/CPU models and network paths despite equal requested CPU/RAM. Accordingly,
this is a practical comparison of the two allocated configurations, not a lab
experiment isolating GPU arithmetic from every CPU/storage/network variable.

## Resource measurement semantics

- PyTorch per-call peak allocated/reserved VRAM and actual total device VRAM.
- Process lifetime peak RSS (includes initialization), plus current RSS per call
  and roughly1Hz process/device samples during inference.
- NVIDIA device memory used and utilization sampled with nvidia-smi. Sampled
  maxima can miss brief peaks; PyTorch figures exclude some CUDA/runtime memory.
- Python process CPU time divided by worker wall time measures average CPU cores
  used during calls. It excludes child-process CPU and is not a host-wide reading.
- Cgroup fields are captured when exposed. This runtime exposes a subset of v1
  memory counters, including limits much larger than the requested16GiB.
  These are not evidence of a16GiB hard limit or complete host memory pressure.
- Modal scalar memory/CPU parameters specify requests. Explicit tuple parameters
  are needed for custom hard memory/soft CPU limits. This experiment preserves
  production's scalar requests for comparability; absence of OOM is not proof
  that a strictly capped16GiB container has passed a stress test.
- Stable RAM/VRAM across the run is evidence against an obvious accumulating
  leak for this workload, not a mathematical guarantee for all media/languages.

## Validation and bounds

Per-window checks cover finite, ordered timestamps inside the actual window;
empty output is allowed for silence. Overlap ownership is applied before joining
the transcript. The final report checks all expected offsets, nonempty sorted
subtitle output, the audio-end bound, error count and container continuity.
Per-chunk text/timestamp hashes are compared between GPUs; any discrepancy is
reported rather than assuming GPU floating-point results are identical.

One worker RPC is limited to300s at the client and240s on Modal. Each full run
is bounded to three hours. Three consecutive failed windows or ten errors stops
the run; partial coverage is never marked passed. Exceptions are categorized
without publishing transcripts or provider secrets. Cleanup stops only the exact
temporary app ID and verifies stopped state, zero tasks and zero containers.

The owner's previously confirmed $0 spend limit remains unchanged. Account
billing snapshots and rates are retained privately; usage cost should not be
confused with an actual cash charge or inferred solely from request duration.

## Evidence and reproduction

- `research/benchmarks/qwen-long-video-input.json`: audio metadata and hash.
- `research/benchmarks/qwen-long-window-check.json`: full-window coverage check.
- `research/benchmarks/qwen-long-T4.json` and `qwen-long-A10.json`: per-window data.
- `research/benchmarks/qwen-long-summary.json`: complete comparison and assertions.
- `research/benchmarks/qwen-long-shutdown.json`: independent retirement check and
  account-level billing deltas, which are not exact per-experiment invoices.
- `tools/prepare_long_asr.py`: bounded audio-only acquisition and normalization.
- `gpu/asr_long_probe.py`, `gpu/resource_monitor.py`: isolated execution/telemetry.
- `tools/long_asr_benchmark.py`: account-separated runs, assertions and cleanup.
- `tools/summarize_long_asr.py`: final comparison and resource trends.

Run only within the authorized GPU-credit budget, with retained input and the
existing cached weights available. Archive previous same-name reports before
repeating. These are actual GPU operations, not local-only checks:

```powershell
.venv/Scripts/python.exe tools/long_asr_benchmark.py --gpu T4 --account 1
.venv/Scripts/python.exe tools/long_asr_benchmark.py --gpu A10 --account 2
.venv/Scripts/python.exe tools/summarize_long_asr.py
```

The two benchmark commands run in separate terminals/processes. The runner
rejects T4/account2 and A10/account1 to preserve the requested separation.
Raw audio, private transcripts and logs remain under ignored `.private/`.

Official sources (fetched and hashed in qwen-long-video-sources.json):
https://modal.com/docs/guide/gpu , https://modal.com/docs/guide/resources ,
https://modal.com/pricing .
