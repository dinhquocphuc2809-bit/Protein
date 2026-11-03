"""Real, bounded T4/L4 benchmark. Run with tools/run_benchmark.py, never with secrets in argv."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import modal

ROLE = os.environ.get("AUVIREL_BENCH_ROLE", "asr")
GPU = os.environ.get("AUVIREL_BENCH_GPU", "T4")
if ROLE not in {"asr", "tts"}:
    raise ValueError("Invalid benchmark role")
if GPU not in {"T4", "L4"}:
    raise ValueError("Invalid benchmark GPU")
REVISIONS = {
    "Qwen/Qwen3-ASR-1.7B": "7278e1e70fe206f11671096ffdd38061171dd6e5",
    "Qwen/Qwen3-ForcedAligner-0.6B": "c7cbfc2048c462b0d63a45797104fc9db3ad62b7",
    "k2-fsa/OmniVoice": "c5fdb5ccb189668d56333f77ba2629f4cd7535f4",
}
app = modal.App(f"auvirel-benchmark-{ROLE}")
volume = modal.Volume.from_name(f"auvirel-{ROLE}-weights", create_if_missing=True)
packages = ["qwen-asr==0.0.6", "stable-ts==2.19.1", "silero-vad==6.2.3"] if ROLE == "asr" else ["omnivoice==0.2.1"]
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1", "sox")
    .pip_install("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1", *packages)
    .env({"HF_HOME": "/weights/huggingface", "AUVIREL_BENCH_ROLE": ROLE})
)


@app.function(image=image, volumes={"/weights": volume}, cpu=2, memory=8192, timeout=1200)
def prepare() -> dict:
    from huggingface_hub import snapshot_download

    started = time.perf_counter()
    names = ["Qwen/Qwen3-ASR-1.7B", "Qwen/Qwen3-ForcedAligner-0.6B"] if ROLE == "asr" else ["k2-fsa/OmniVoice"]
    for name in names:
        snapshot_download(name, revision=REVISIONS[name])
    if ROLE == "asr":
        import stable_whisper

        stable_whisper.load_model("small", device="cpu", download_root="/weights/whisper")
    volume.commit()
    return {"prepare_seconds": time.perf_counter() - started, "revisions": {n: REVISIONS[n] for n in names}}


@app.cls(image=image, gpu=GPU, cpu=2, memory=16384, volumes={"/weights": volume},
         min_containers=0, max_containers=1, scaledown_window=30, timeout=180, startup_timeout=300)
class Probe:
    @modal.enter()
    def initialize(self):
        import torch
        from huggingface_hub import snapshot_download

        started = time.perf_counter()
        self.torch = torch
        torch.set_num_threads(2)
        if ROLE == "asr":
            from qwen_asr import Qwen3ASRModel
            import stable_whisper

            self.model = Qwen3ASRModel.from_pretrained(
                snapshot_download("Qwen/Qwen3-ASR-1.7B", revision=REVISIONS["Qwen/Qwen3-ASR-1.7B"], local_files_only=True),
                dtype=torch.float16, device_map="cuda:0", attn_implementation="sdpa",
                max_inference_batch_size=1, max_new_tokens=512,
                forced_aligner=snapshot_download("Qwen/Qwen3-ForcedAligner-0.6B", revision=REVISIONS["Qwen/Qwen3-ForcedAligner-0.6B"], local_files_only=True),
                forced_aligner_kwargs={"dtype": torch.float16, "device_map": "cuda:0", "attn_implementation": "sdpa"},
            )
            self.fallback = stable_whisper.load_model("small", device="cuda", download_root="/weights/whisper")
        else:
            from omnivoice import OmniVoice

            self.model = OmniVoice.from_pretrained(
                snapshot_download("k2-fsa/OmniVoice", revision=REVISIONS["k2-fsa/OmniVoice"], local_files_only=True),
                device_map="cuda:0", dtype=torch.float16,
            )
        torch.cuda.synchronize()
        self.init_seconds = time.perf_counter() - started
        self.calls = 0

    @modal.method()
    def measure(self, wav: bytes, language: str, reference_text: str, text: str = "") -> dict:
        import io
        import resource
        import tempfile

        import numpy as np
        import soundfile as sf
        import torchaudio

        if not 44 <= len(wav) <= 16 * 1024 * 1024:
            raise ValueError("Benchmark WAV size outside bounds")
        audio, sr = sf.read(io.BytesIO(wav), dtype="float32", always_2d=True)
        if len(audio) / sr > 60 or not np.isfinite(audio).all():
            raise ValueError("Benchmark audio duration or samples invalid")
        self.torch.cuda.reset_peak_memory_stats()
        started = time.perf_counter()
        result = {}
        if ROLE == "asr":
            mono = self.torch.from_numpy(audio.mean(axis=1))
            mono = torchaudio.functional.resample(mono, sr, 16000).numpy()
            supported = language in {"English", "Chinese", "Cantonese", "French", "German", "Italian", "Japanese", "Korean", "Portuguese", "Russian", "Spanish"}
            transcript = self.model.transcribe(audio=(mono, 16000), language=language, return_time_stamps=supported)[0]
            if supported:
                words = [{"text": w.text, "start": float(w.start_time), "end": float(w.end_time)} for w in transcript.time_stamps]
                aligner = "qwen-forced-aligner"
            else:
                aligned = self.fallback.align(mono, transcript.text, language="vi", verbose=False)
                if aligned is None:
                    raise ValueError("Fallback alignment failed")
                words = [{"text": str(w.word), "start": float(w.start), "end": float(w.end)} for seg in aligned.segments for w in seg.words]
                aligner = "stable-ts-whisper-small"
            previous = 0.0
            for word in words:
                if not (previous <= word["start"] <= word["end"] <= len(mono) / 16000 + 0.05):
                    raise ValueError("Invalid alignment timestamps")
                previous = word["start"]
            result.update(text=transcript.text, words=words, aligner=aligner, input_seconds=len(mono) / 16000)
            from silero_vad import load_silero_vad, get_speech_timestamps

            speech = get_speech_timestamps(self.torch.from_numpy(mono), load_silero_vad(), sampling_rate=16000,
                                          max_speech_duration_s=25, return_seconds=True)
            result["vad_regions"] = [{"start": float(region["start"]), "end": float(region["end"])} for region in speech]
        else:
            with tempfile.TemporaryDirectory(prefix="auvirel-probe-") as temp:
                ref = Path(temp) / "ref.wav"
                ref.write_bytes(wav)
                generated = self.model.generate(text=text, ref_audio=str(ref), ref_text=reference_text, num_step=16, speed=1.0)[0]
            if not np.isfinite(generated).all() or len(generated) == 0:
                raise ValueError("Nonfinite or empty generated audio")
            buf = io.BytesIO()
            sf.write(buf, generated, 24000, format="WAV", subtype="PCM_16")
            result.update(audio=buf.getvalue(), audio_seconds=len(generated) / 24000, sample_rate=24000)
        self.torch.cuda.synchronize()
        self.calls += 1
        elapsed = time.perf_counter() - started
        result.update(inference_seconds=elapsed, init_seconds=self.init_seconds, call=self.calls,
                      gpu=self.torch.cuda.get_device_name(), peak_vram_bytes=self.torch.cuda.max_memory_allocated(),
                      peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      rtf=elapsed / result.get("audio_seconds", result.get("input_seconds", 1)))
        return result


@app.local_entrypoint()
def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "research" / "benchmarks"
    output.mkdir(parents=True, exist_ok=True)
    private = root / ".private" / "benchmark-audio"
    private.mkdir(parents=True, exist_ok=True)
    reference = (root.parent / "Neko Dub/presets/vietnamese/Dang-Khoa.wav").read_bytes()
    # This is the transcript shipped with this preset, not a generated test answer.
    ref_text = "Xin chào, đây là đoạn văn bản mẫu để thử nghiệm giọng nói tiếng Việt, hãy chọn một giọng nói phù hợp với sở thích"
    report = {"role": ROLE, "started_at": time.time(), "preparation": prepare.remote(), "runs": []}
    report_path = output / f"{ROLE}-{GPU}-{int(time.time())}.json"
    for gpu in [GPU]:
        worker = Probe()
        samples = [("Vietnamese", reference)]
        if ROLE == "asr":
            samples.append(("English", (root / ".private/asr_en.wav").read_bytes()))
        for language, audio in samples:
            for repeat in range(2):
                start = time.perf_counter()
                try:
                    call = worker.measure.spawn(audio, language, ref_text,
                                                "Học một điều mới mỗi ngày giúp chúng ta hiểu thế giới rõ hơn.")
                    try:
                        data = call.get(timeout=240)
                    except BaseException:
                        call.cancel(terminate_containers=True)
                        raise
                    if "audio" in data:
                        path = private / f"{ROLE}-{gpu}-{repeat}.wav"
                        path.write_bytes(data.pop("audio"))
                        data["local_audio_file"] = path.name
                    data.update(gpu_requested=gpu, repeat=repeat, language=language, round_trip_seconds=time.perf_counter() - start)
                    report["runs"].append(data)
                    print(json.dumps({k: v for k, v in data.items() if k not in {"words", "text", "vad_regions"}}))
                except Exception as error:
                    report["runs"].append({"gpu_requested": gpu, "language": language, "repeat": repeat,
                                           "error_type": type(error).__name__, "error": str(error)[:1200]})
                    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                    raise
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
