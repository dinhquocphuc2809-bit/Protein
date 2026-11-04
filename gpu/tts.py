"""Client-owned OmniVoice: authenticated CPU ingress, bounded single-voice GPU jobs."""
import os
import time
import modal

app = modal.App("auvirel-voice")
weights = modal.Volume.from_name("auvirel-tts-weights", create_if_missing=True)
requests = modal.Dict.from_name("auvirel-voice-requests", create_if_missing=True)
REVISION = "c5fdb5ccb189668d56333f77ba2629f4cd7535f4"
image = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "libsndfile1", "sox")
         .pip_install("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1", "omnivoice==0.2.1")
         .env({"HF_HOME": "/weights/huggingface"}))
web_image = (modal.Image.debian_slim(python_version="3.11").pip_install("fastapi==0.162.0")
             .add_local_python_source("gpu"))


@app.function(image=image, volumes={"/weights": weights}, cpu=2, memory=8192, timeout=1200)
def prepare():
    from huggingface_hub import snapshot_download
    snapshot_download("k2-fsa/OmniVoice", revision=REVISION)
    weights.commit()


@app.cls(image=image, gpu=os.environ.get("AUVIREL_GPU", "T4"), cpu=2, memory=8192,
         volumes={"/weights": weights}, min_containers=0, max_containers=1,
         scaledown_window=30, timeout=120, startup_timeout=300)
class Voice:
    @modal.enter()
    def load(self):
        started = time.perf_counter()
        import torch
        from omnivoice import OmniVoice
        from huggingface_hub import snapshot_download
        torch.set_num_threads(2)
        self.model = OmniVoice.from_pretrained(snapshot_download("k2-fsa/OmniVoice", revision=REVISION, local_files_only=True),
                                              device_map="cuda:0", dtype=torch.float16)
        self.prompts = {}
        torch.cuda.synchronize()
        self.init_seconds = time.perf_counter()-started
        self.calls = 0

    @modal.method()
    def synthesize(self, text: str, reference: bytes, reference_text: str, target_duration: float | None, language: str):
        started = time.perf_counter()
        import torch
        import hashlib
        import io
        import tempfile
        import numpy as np
        import soundfile as sf
        from pathlib import Path

        if len(reference) > 4*1024**2 or reference[:4] != b"RIFF" or reference[8:12] != b"WAVE":
            raise ValueError("Invalid reference WAV")
        samples, sr = sf.read(io.BytesIO(reference), dtype="float32", always_2d=True)
        if not 8000 <= sr <= 96000 or not 1 <= samples.shape[1] <= 2 or not 1 <= len(samples)/sr <= 30 or not np.isfinite(samples).all():
            raise ValueError("Reference must contain 1-30 seconds of finite mono/stereo audio")
        if not text.strip() or len(text) > 800 or len(reference_text) > 1200:
            raise ValueError("Text outside allowed length")
        if target_duration is not None and not .2 <= target_duration <= 30:
            raise ValueError("Invalid target duration")
        identity = hashlib.sha256(reference + reference_text.encode()).hexdigest()
        if identity not in self.prompts:
            with tempfile.TemporaryDirectory(prefix="auvirel-reference-") as directory:
                path = Path(directory) / "voice.wav"
                sf.write(path, samples.mean(axis=1), sr)
                prompt = self.model.create_voice_clone_prompt(ref_audio=str(path), ref_text=reference_text)
            self.prompts[identity] = prompt
            while len(self.prompts) > 8:
                self.prompts.pop(next(iter(self.prompts)))
        prompt = self.prompts.pop(identity)
        self.prompts[identity] = prompt
        torch.cuda.synchronize()
        prepared = time.perf_counter()
        generated = self.model.generate(text=text, voice_clone_prompt=prompt, language=language,
                                        duration=target_duration, num_step=16)[0]
        torch.cuda.synchronize()
        inferred = time.perf_counter()
        if len(generated) == 0 or len(generated) > 24000*60 or not np.isfinite(generated).all():
            raise ValueError("Invalid synthesized waveform")
        # Trim only low-energy margins and retain a small breath/consonant safety pad.
        active = np.flatnonzero(np.abs(generated) > .003)
        if not len(active):
            raise ValueError("Synthesis returned silence")
        pad = 240
        generated = generated[max(0, active[0]-pad):min(len(generated), active[-1]+pad+1)].copy()
        fade = min(120, len(generated)//2)
        if fade:
            ramp = np.linspace(0, 1, fade, dtype=np.float32)
            generated[:fade] *= ramp
            generated[-fade:] *= ramp[::-1]
        peak = float(np.max(np.abs(generated)))
        if peak > .98:
            generated *= .98 / peak
        output = io.BytesIO()
        sf.write(output, generated, 24000, format="OGG", subtype="VORBIS")
        self.calls += 1
        return {"audio": output.getvalue(), "duration": len(generated)/24000, "voice_id": identity, "sample_rate": 24000,
                "timings": {"container_init_seconds": self.init_seconds, "call_in_container": self.calls,
                            "reference_seconds": prepared-started, "inference_seconds": inferred-prepared,
                            "encoding_seconds": time.perf_counter()-inferred, "worker_seconds": time.perf_counter()-started}}


# Keep lightweight coordination near Modal's default RPC/Dict routing. GPU placement stays flexible.
@app.function(image=web_image, cpu=.25, memory=512, region="us-east", min_containers=0, max_containers=1, scaledown_window=30, timeout=30)
@modal.concurrent(max_inputs=16)
@modal.asgi_app(requires_proxy_auth=True)
def api():
    from gpu.voice_api import create_api
    return create_api(requests, Voice, modal.FunctionCall.from_id, REVISION)


@app.local_entrypoint()
def warm_weights():
    prepare.remote()
