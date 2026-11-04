# Modal cold-start mechanisms and Vocalm

Reviewed: 2026-11-05 (Asia/Bangkok). This is documentation/configuration research,
not a successful snapshot benchmark or a production rollout.

## Findings

Modal distinguishes waiting for a warm container from initialization inside it.
The earlier L4 calls never produced a running container or model-load output;
their cause is unresolved. Snapshot restore still needs compatible GPU capacity,
so snapshots cannot be assumed to resolve those allocation timeouts.

| Mechanism | What it changes | Current Vocalm status |
| --- | --- | --- |
| Cached weights in Modal Volume | Avoid repeated model downloads | Enabled, pinned revisions/local_files_only |
| CPU Memory Snapshot | Restore initialized CPU memory/imports/state | Disabled |
| GPU Memory Snapshot | Also restore CUDA/GPU state | Disabled; Modal labels it Alpha |
| Longer scaledown_window | Reduce cold starts between requests | Currently30s |
| min_containers / buffer_containers | Keep additional capacity warm | min_containers=0, no extra buffer |

Idle warm containers incur resource charges. With limited promotional credits,
permanently warming all three ASR accounts is not a default recommendation.

## Important snapshot requirements

- CPU snapshots use `enable_memory_snapshot=True`; snapshot initialization goes
  in `@modal.enter(snap=True)`. Normal `@modal.enter()` runs after restoration.
- GPU snapshots additionally use
  `experimental_options={"enable_gpu_snapshot": True}`. CUDA initialization and
  representative forward-pass warmup can run in the snap hook.
- Snapshots are created only for **deployed apps**. A plain ephemeral `modal run`
  comparison is insufficient. The installed Modal SDK1.6.3 supports these options.
- A snapshot-enabled decorator or a creation log is not evidence of restoration.
  Confirm the Containers startup marker or `Restoring Function from memory snapshot`.
- A new deployment/code/GPU configuration makes old snapshots obsolete. Modal may
  create2-3 snapshots per GPU type to cover underlying worker variants.
- CPU-only snapshots cannot initialize CUDA; load on CPU first and move to CUDA
  in the post-restore hook. Some libraries initialize CUDA implicitly on import.
- Official docs caution that storage-bandwidth-bound weight loading generally
  does not become faster through GPU snapshots and may acquire extra overhead.
  Their main advantage is skipping imports, compilation and other initialization.

## Impact on this system

The measured T4 model-loading stage was17.494 seconds. Warm whole-video worker
execution still took171.226 seconds, including142.053 seconds of recognition.
A snapshot cannot remove those warm inference costs. Client-observed wall time
also includes per-window RPC overhead; do not count all of that as cold start.

An earlier OmniVoice CPU-snapshot experiment was reverted because actual restore
benefit was not demonstrated; see `docs/TTS_LATENCY.md`. That is not a test of
Qwen GPU snapshots and does not justify dismissing them categorically.

## Appropriate next experiment

Deploy a separate, bounded Qwen snapshot app using the same model revisions,
audio and GPU. Measure first snapshot creation separately. Confirm that the
container retires, then invoke the unchanged deployment and require explicit
restore evidence. Repeat for several cold starts and compare output validity,
first-request latency and warm inference with a non-snapshot baseline. Keep
min_containers=0 and retire/stop the test app afterward. Roll out only if actual
restore improves the user-visible latency without correctness or cost regressions.

This experiment has not been run in this research turn; production is unchanged.

## Official sources

- https://modal.com/docs/guide/cold-start
- https://modal.com/docs/guide/memory-snapshot
- https://modal.com/docs/guide/scale

URL/content hashes: `research/modal-cold-start-sources.json`. The attempted
standalone GPU-memory-snapshot page returned404; GPU documentation is in the
memory-snapshot guide above.
