# Qwen full-video GPU benchmark

Date: 2026-11-05 (Asia/Bangkok).

## Outcome

T4 completed two uncached full-video runs. Its measured VRAM usage does not
indicate a capacity shortage. L4 could not be allocated during three bounded
attempts, so the requested T4/L4 speed comparison is incomplete. No L4 inference
time, memory measurement or speedup can be inferred from those timeouts.

## Controlled conditions

Video7jb0q3Mo9Rg:817.0173125 seconds, same normalized mono16kHz WAV bytes.
Both GPU configurations request2vCPU and16384MiB host RAM. Both use the exact
production Qwen3-ASR-1.7B/ForcedAligner methods and revisions, FP16/SDPA, batch1,
Silero VAD,512-token limit and34 overlapping windows. No cached transcript,
download, translation or TTS is included. One pass starts with a new container;
the second immediately repeats the entire audio in the same warm container.

Temporary benchmark apps are separate from production. Modal1.6.3 is pinned;
the harness uses its internal method accessor to instrument the original methods
without copying the inference implementation. This accessor needs review on SDK
upgrades. GPU synchronization around stages adds small profiling overhead.

## T4 measurements

| Metric | First pass | Warm second pass |
| --- | ---: | ---: |
| Full client-observed wall time |323.585s |251.944s |
| Sum of worker execution time |182.952s |171.226s |
| Recognition |143.284s |142.053s |
| Qwen forced alignment |15.628s |15.590s |
| VAD |13.967s |13.340s |
| Peak PyTorch allocated VRAM |6.665GiB |6.665GiB |
| Peak PyTorch reserved VRAM |6.998GiB |6.998GiB |
| Total GPU memory reported |14.571GiB |14.571GiB |
| Process lifetime peak RSS |9.438GiB |9.438GiB |

Model loading inside the container took17.494s. The first RPC took46.932s,
including initialization, scheduling, transport and its first inference. It is
not valid to label that entire RPC duration model-loading time.

Both passes produced2398 retained words and160 cues before sentence reflow,
with identical output hashes. One alignment recovery occurred in each pass.
These cue counts precede production speech-unit reflow, so they differ from the
94 display/speech units in the earlier end-to-end report.

## Interpretation

- Capacity: about7GiB reserved out of14.57GiB available does not support the
  hypothesis that T4 is running out of VRAM. More VRAM alone is not a demonstrated
  solution for this single-stream configuration.
- Host RAM:9.44GiB process RSS is below the16GiB request. Cgroup pressure/swap
  counters were unavailable, and RSS excludes some container memory, so this is
  evidence against obvious process-memory exhaustion, not a comprehensive RAM
  bottleneck diagnosis.
- Recognition occupies about83% of warm worker time. That includes model
  computation and CPU/token-generation overhead; this profiling cannot separate
  GPU arithmetic from memory bandwidth stalls. Hardware utilization was not sampled.
- The warm client total exceeds worker execution by about80.7s over34 RPCs.
  Transport, serialization, client/Modal scheduling and instrumentation can
  contribute. This is a local Windows client test, not VPS network latency.
  Do not attribute all of the difference to the GPU or claim it is all network.
- A faster GPU may help recognition, but an L4 speedup must be measured. Also
  investigate sequential per-region decoding and repeated per-window RPC overhead.

## L4 attempts

| Attempt | Account / placement | Outcome |
| --- | --- | --- |
|1 | Backend1 / automatic | First call timed out after300s;0 chunks |
|2 | Backend1 / us-central | First call timed out after300s;0 chunks |
|3 | Backend2 / automatic | First call timed out after300s;0 chunks |

Status checks showed no running L4 container, and logs contained no L4 model-load
output. The exact scheduler cause was not exposed. All benchmark apps are now
stopped with zero tasks. No production GPU choice was changed.

## Evidence and retry

`research/benchmarks/qwen-full-video-T4.json` contains raw per-window metrics.
The three `qwen-full-video-L4-attempt*.json` reports retain failed attempts.
`qwen-full-video-summary.json` explicitly marks comparison_complete=false.
`qwen-comparison-shutdown.json` records stopped apps.

```powershell
.venv/Scripts/python.exe tools/compare_asr_gpu.py --gpu L4 --account 2
.venv/Scripts/python.exe tools/summarize_asr_comparison.py
```

Run only when continuing the authorized GPU benchmark; inference consumes credit.
Archive a prior same-name report before another attempt. Successful L4 allocation
is the remaining requirement. A matched-region T4 rerun may then be needed to
compare client wall times; server inference metrics reduce that network confound.

Official references read: https://modal.com/docs/guide/gpu ,
https://modal.com/docs/guide/region-selection , https://modal.com/pricing .
Content hashes are in `research/benchmarks/qwen-comparison-sources.json`.
