# Qwen A100 40GB / 80GB full-video comparison

Date: 2026-11-05 (Asia/Bangkok). Both A100 runs completed all375 windows with
zero failed windows/OOM/restarts. Both apps stopped; production unchanged.

## Outcome

For the current single-stream, sequential-window pipeline, **neither A100 is
cost-optimal**. T4 has the lowest measured/estimated resource cost. A10080GB
has the fastest observed total time, at roughly2.44x T4's resource cost.
These results do not establish the economics of a redesigned batched service.

| GPU | Full client wall | Worker processing | Observed app resource USD | Consistent estimated USD |
| --- | ---: | ---: | ---: | ---: |
| T4 | 32m00s | 20m16s | 0.4325 | 0.4334 |
| A10 | 27m57s | 12m03s | 0.6148 | 0.6161 |
| A10040GB SXM4 | 25m11s | 14m45s | 0.9613 | 0.9748 |
| A10080GB PCIe | 23m20s | 11m50s | 1.0558 | 1.0590 |

Observed costs are Modal's currently reported app-attributed GPU+CPU+memory
usage, before credits, not finalized cash invoices. Their implied GPU durations
are99.8%,99.8%,98.6%,99.7% of client wall duration, respectively. Startup and
transport timing scopes differ and ingestion may lag; do not treat the remaining
difference as measured free GPU time. The independent uniform estimates agree
closely and reach the same cost-effectiveness conclusion.

Relative to T4,40GB saves6m49s and costs about2.22x;80GB saves8m40s and costs
about2.44x using the observed app figures. Relative to A10,80GB saves4m37s but
costs about1.72x. The80GB worker time is only12.635s (1.75%) below A10's;
most of that wall-time difference comes from the non-worker remainder, not a
demonstrated acceleration of recognition by the same percentage.

The40GB run's worker was slower than A10 (885.245s versus722.531s), despite a
shorter total run. Its host's CPU/VAD performance and placement differ. This is
why the evidence does not support a universal ranking of GPU hardware from
client wall time alone. The measured80GB variant is PCIe and40GB is SXM4.

## Reliability and resource use

| Measurement | A10040GB | A10080GB |
| --- | ---: | ---: |
| Complete windows | 375/375 | 375/375 |
| Failed windows / observed OOM | 0 / 0 | 0 / 0 |
| Successful alignment recovery | 1 | 1 |
| Recovery at3960s | 8.792s | 7.943s |
| Peak process RSS including startup | 8.949GiB | 9.495GiB |
| Peak PyTorch reserved VRAM | 6.787GiB | 6.787GiB |
| Average process CPU cores during calls | 1.188 | 1.172 |
| Sampled mean GPU utilization during calls | 26.5% | 25.0% |
| Containers used | 1 | 1 |

Both runs retain13905 word items and1093 cues with valid bounded timestamps.
Each final transcript differs from T4 in two substituted word items; this is
an output comparison, not a ground-truth accuracy evaluation. Same counts do
not mean identical text. Timing and text differences are recorded without
publishing private transcript contents. No human word-error-rate audit is claimed.

GPU memory capacity was not exhausted. Qwen uses roughly7GiB here and the
additional40/80GB capacity is mostly unused. Resource saturation, batching,
RPC amortization and concurrency would require a different experiment; no such
production changes or hypothetical cost savings are included in these results.

## Method and cost accounting

The owner requests the same YouTube video YGi-aPUsZrQ on A100 40GB and80GB,
including total processing time and cost effectiveness. The retained audio is
8996.72s, mono16kHz PCM16, SHA256
df0c4bfc18cce22faa1670e1e9da9f87f6cecb89c1d1a470fc224d3fb9945ac7.
No second download or VPS media storage is necessary.

Both runs use the same375 overlapping windows and exact production Qwen/VAD/
alignment implementation as the previous T4/A10 comparison. CPU2/RAM16384MiB
are resource requests, not hard caps. Snapshots are disabled. No translation,
TTS, transcript cache or provider substitution is included. The two isolated
apps use separate backend accounts; account4 for client TTS is untouched.

| Requested GPU | Account | Actual reported hardware | Reported device GiB |
| --- | ---: | --- | ---: |
| A100-40GB | 1 | NVIDIA A100-SXM4-40GB | 39.515 |
| A100-80GB | 2 | NVIDIA A100 80GB PCIe | 79.272 |

SXM4 and PCIe differ in more than memory capacity. Host CPU and network placement
also vary. These are practical configurations allocated by Modal, not controlled
comparisons of VRAM capacity alone. The historical T4/A10 runs occurred earlier,
so network/provider load can affect client-time comparisons.

Timing begins before the first inference RPC and ends after all375 results have
been validated, excluding image preparation/download/normalization. The first
request includes scheduling/loading. Worker timings capture actual VAD/ASR/
alignment processing. Client wall time also includes RPC transport, scheduling,
serialization, diagnostic writes and other overhead; it is not pure GPU time.

Current Modal SDK billing rates, retrieved before running:

| Resource | USD/hour |
| --- | ---: |
| T4 GPU | 0.59 |
| A10 GPU | 1.10 |
| A100 40GB GPU | 2.10 |
| A100 80GB GPU | 2.50 |
| CPU core | 0.0473 |
| Host memory GiB | 0.008 |

Two cost views are retained:

1. **Observed app-level resource costs:** Modal billing report, matched by exact
   app ID and summed across hourly buckets/resources. These can lag ingestion;
   currently accumulating rows must not be presented as finalized invoices.
2. **Consistent wall-duration estimate:** client wall seconds/3600 multiplied by
   GPU hourly rate +2 CPU hourly rates +16 memory-GiB hourly rates. This is an
   estimate, not exact container billing. Startup/retirement, CPU usage above
   requests, storage and build costs can differ. Merely multiplying worker
   inference time by GPU price undercounts a GPU kept allocated between RPCs.

Credit-funded usage still consumes the finite balance. An account summary's
zero billed cash cost does not make the resources free or establish that one
GPU is cheaper. Account-level before/after changes can include other/delayed
usage, so app-level records are preferable.

Reports: `research/benchmarks/qwen-long-A100-40GB.json`,
`research/benchmarks/qwen-long-A100-80GB.json`,
`research/benchmarks/qwen-a100-before.json`,
`research/benchmarks/qwen-a100-summary.json` (timings/output checks/app-cost rows),
`research/benchmarks/qwen-a100-shutdown.json` (independent retirement verification).
The summary tool requires all four reports to have full coverage, valid output
and stopped apps before producing the final cost comparison.

## Reproduction

Retained input, cached weights, owner credentials and Modal SDK1.6.3 are required.
These commands spend GPU credit; run each GPU command in a separate process.
Existing report files must be archived rather than silently overwritten:

```powershell
.venv/Scripts/python.exe tools/long_asr_benchmark.py --gpu A100-40GB --account 1
.venv/Scripts/python.exe tools/long_asr_benchmark.py --gpu A100-80GB --account 2
.venv/Scripts/python.exe tools/summarize_a100.py
```

Official sources were fetched directly and hashed in qwen-a100-before.json:
https://modal.com/docs/guide/gpu , https://modal.com/docs/guide/resources ,
https://modal.com/pricing . Billing attribution semantics were also inspected
in the installed Modal SDK `_billing.py` and CLI billing report implementation.
