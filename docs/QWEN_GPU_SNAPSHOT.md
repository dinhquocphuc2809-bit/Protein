# Qwen GPU snapshot experiment

Date: 2026-11-05 (Asia/Bangkok).

## Result

Actual GPU snapshot restoration succeeded on an isolated deployed T4 app.
After the previous container retired, the first response took **15.298s**.
Matched cold starts without snapshots took **53.755s** and **32.444s**.
The observed reduction is **52.8-71.5%** for this short experiment; there is
only one restored request, so this is not a latency percentile or guarantee.
Production was not changed. Both test apps are stopped with zero containers.

## Method

- Backend Modal account 1; account 4 reserved for client TTS was not used.
- Separate deployed apps: `vocalm-qwen-snapshot-test` and
  `vocalm-qwen-cold-control`. Not ephemeral `modal run` apps.
- T4, 2 vCPU, 16384 MiB host RAM; min_containers=0, max_containers=1,
  scaledown_window=10, startup_timeout=300, request timeout=180.
- Same production image, cached pinned weights, Qwen3-ASR-1.7B FP16/SDPA,
  Silero VAD and actual Qwen forced alignment. No Deepgram or subtitle cache.
- First 28 seconds of the retained audio from YouTube `7jb0q3Mo9Rg`,
  mono PCM16 at 16 kHz. Input SHA256 is in the machine-readable report.
- Both variants execute the same representative forward-pass warmup. For the
  snapshot variant, initialization and warmup run in `enter(snap=True)`.
- Before each subsequent call, the runner polls Modal container inventory
  until the test app has zero containers. It then invokes the unchanged
  deployment. Every response must be call number 1 in a different boot.
- Client RPC timing starts immediately before `measure.spawn` and ends on its
  result; deployment and idle-retirement waiting are excluded. This timing
  includes network, scheduling, initialization/restore and inference.

## Measurements

| Variant / start | RPC to result (s) | Inference (s) | Evidence |
| --- | ---: | ---: | --- |
| Snapshot enabled, 1 | 42.238 | 3.733 | Creating snapshot; new initialization |
| Snapshot enabled, 2 | 61.189 | 4.812 | Creating snapshot; new initialization |
| Snapshot enabled, 3 | 39.816 | 3.592 | Creating snapshot; new initialization |
| Snapshot enabled, 4 | 15.298 | 3.875 | Confirmed restore after retirement |
| No snapshot, 1 | 53.755 | 4.540 | Fresh model load and warmup |
| No snapshot, 2 | 32.444 | 3.666 | Fresh load after retirement |

The third and fourth snapshot calls share initialization UUID
`550827bace1744c58a9acb7ac7fae347`. Their post-start boot UUIDs differ, and the
fourth request counter is 1. Most importantly, Modal system logs explicitly say:

```text
2026-11-05 05:56:17+07:00 ta-01M6MCE0G89AWK9E8QPZRVRPHR Restoring Function from memory snapshot.
```

This confirms restoration, rather than reusing a still-warm container or merely
enabling the decorator. Modal first created snapshots on three starts, consistent
with its documented need to cover different worker types.

All six responses contain 45 words, Chinese language detection, valid timestamp
bounds, and identical hashes of the word/timestamp output. This establishes output
consistency for this sample, not human-verified word accuracy. The restored
`model_load_seconds` and `warmup_seconds` are historical values captured in memory,
not loading or warmup performed again during restoration.

## Interpretation and limits

GPU snapshots are a promising cold-start improvement for this configuration.
They do not remove the roughly 3.6-4.8s of inference observed on this sample.
The earlier full-video warm inference measurement therefore cannot be scaled
down by the cold-start improvement percentage.

The control model loads varied from 14.213s to 24.938s; underlying host, storage,
placement and network variability remain relevant. This is one confirmed restore
and two controls on T4, not an L4 comparison, a multilingual test, an alignment
fallback test, a concurrency test or an extension end-to-end latency measurement.
We did not measure invoice-level snapshot costs. Snapshot setup can itself add
latency, and GPU availability is still required.

Production snapshots remain disabled. Before a rollout, establish repeated
restore timings and run a fresh full-video plus multilingual/alignment-fallback
regression from restored containers. A single short sample is insufficient to
claim production reliability. No permanent warm containers are needed for the
tested approach.

## Cleanup, evidence and reproduction

Both exact experiment apps were stopped, then independently checked as state
`stopped`, zero tasks and an empty container list. An initial snapshot-run shutdown
check raced asynchronous termination; the later recheck confirms full retirement.
The runner now polls shutdown and attempts cleanup even if log retrieval fails.

- `research/benchmarks/vocalm-qwen-snapshot-test.json`: four snapshot-enabled starts.
- `research/benchmarks/vocalm-qwen-cold-control.json`: two cold controls.
- `research/benchmarks/qwen-snapshot-summary.json`: cross-run assertions and cleanup.
- `gpu/asr_snapshot_probe.py`: isolated deployment, no production configuration edit.
- `tools/qwen_snapshot_test.py`: bounded runner and evidence collection.

Raw logs and source audio stay in ignored `.private/` directories. Reports contain
no account tokens, signed media URLs or transcript text. Reproduction requires the
authorized backend account, installed Modal SDK 1.6.3, existing cached weights and
the retained `.private/asr-second-video/video.wav` input:

```powershell
.venv/Scripts/python.exe tools/qwen_snapshot_test.py --cycles 4
.venv/Scripts/python.exe tools/qwen_snapshot_test.py --control --cycles 2
```

These commands use GPU credits and overwrite their corresponding run reports.
The probe deliberately uses pinned SDK private class/raw-method accessors to
execute the exact production methods without modifying production code.

Official requirements and source hashes: `docs/MODAL_COLD_START.md` and
`research/modal-cold-start-sources.json`.
