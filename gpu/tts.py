"""Client-owned OmniVoice: authenticated CPU ingress, bounded single-voice GPU jobs."""
import os
import modal

app = modal.App("auvirel-voice")
weights = modal.Volume.from_name("auvirel-tts-weights", create_if_missing=True)
requests = modal.Dict.from_name("auvirel-voice-requests", create_if_missing=True)
REVISION = "c5fdb5ccb189668d56333f77ba2629f4cd7535f4"
image = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "libsndfile1", "sox")
         .pip_install("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1", "omnivoice==0.2.1")
         .env({"HF_HOME": "/weights/huggingface"}))
web_image = modal.Image.debian_slim(python_version="3.11").pip_install("fastapi==0.162.0")


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
        import torch
        from omnivoice import OmniVoice
        from huggingface_hub import snapshot_download
        torch.set_num_threads(2)
        self.model = OmniVoice.from_pretrained(snapshot_download("k2-fsa/OmniVoice", revision=REVISION, local_files_only=True),
                                              device_map="cuda:0", dtype=torch.float16)
        self.prompts = {}

    @modal.method()
    def synthesize(self, text: str, reference: bytes, reference_text: str, target_duration: float | None, language: str):
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
        generated = self.model.generate(text=text, voice_clone_prompt=prompt, language=language,
                                        duration=target_duration, num_step=16)[0]
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
        return {"audio": output.getvalue(), "duration": len(generated)/24000, "voice_id": identity, "sample_rate": 24000}


@app.function(image=web_image, cpu=.25, memory=512, min_containers=0, max_containers=1, scaledown_window=30, timeout=30)
@modal.asgi_app(requires_proxy_auth=True)
def api():
    import base64
    import binascii
    import hashlib
    import io
    import time
    import wave
    import asyncio
    import re
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse

    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @web.get("/v1/health")
    def health():
        return {"ok": True, "engine": "omnivoice", "revision": REVISION, "single_voice": True}

    @web.post("/v1/synthesize", status_code=202)
    async def synthesize(request: Request):
        body = bytearray()
        try:
            async with asyncio.timeout(20):
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 6*1024**2:
                        raise HTTPException(413, "Request too large")
        except TimeoutError:
            raise HTTPException(408, "Request body timed out") from None
        import json
        try:
            data = json.loads(body)
            if not isinstance(data, dict) or set(data) - {"text", "reference", "reference_text", "duration", "language"}:
                raise ValueError()
            text, ref_text = data["text"], data["reference_text"]
            language = data.get("language", "vi")
            duration = data.get("duration")
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 800 or not isinstance(ref_text, str) or not 1 <= len(ref_text) <= 1200:
                raise ValueError()
            if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2,3}", language):
                raise ValueError()
            if duration is not None and (not isinstance(duration, (int, float)) or not .2 <= duration <= 30):
                raise ValueError()
            reference = base64.b64decode(data["reference"], validate=True)
            if not 44 <= len(reference) <= 4*1024**2 or reference[:4] != b"RIFF" or reference[8:12] != b"WAVE":
                raise ValueError()
            with wave.open(io.BytesIO(reference)) as wav:
                if not 8000 <= wav.getframerate() <= 96000 or wav.getnchannels() not in (1, 2) or wav.getsampwidth() != 2 or not 1 <= wav.getnframes()/wav.getframerate() <= 30:
                    raise ValueError()
                if len(wav.readframes(wav.getnframes())) != wav.getnframes()*wav.getnchannels()*2:
                    raise ValueError()
        except (KeyError, TypeError, ValueError, binascii.Error, wave.Error, EOFError):
            raise HTTPException(400, "Invalid single-voice synthesis input") from None
        identity = request.headers.get("Idempotency-Key", "")
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise HTTPException(400, "A SHA-256 Idempotency-Key is required")
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        entry = {"hash": fingerprint, "created": time.time(), "call": None}
        inserted = await requests.put.aio(identity, entry, skip_if_exists=True)
        if not inserted:
            entry = await requests.get.aio(identity)
            if entry["hash"] != fingerprint:
                raise HTTPException(409, "Idempotency input mismatch")
            if entry.get("cancelled"):
                raise HTTPException(410, "Synthesis was cancelled; create a new attempt")
            if not entry["call"]:
                raise HTTPException(409, "Submission in progress; poll this synthesis ID")
            return {"id": identity}
        # A crashed submission stays indeterminate rather than spending GPU twice.
        call = await Voice().synthesize.spawn.aio(text, reference, ref_text, duration, language)
        entry["call"] = call.object_id
        await requests.put.aio(identity, entry)
        return {"id": identity}

    async def lookup(identity):
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise HTTPException(400, "Invalid synthesis ID")
        entry = await requests.get.aio(identity, None)
        if entry is None:
            raise HTTPException(404, "Synthesis not found")
        if time.time()-entry["created"] > 48*3600:
            await requests.pop.aio(identity, None)
            raise HTTPException(410, "Synthesis result expired")
        if entry.get("cancelled"):
            raise HTTPException(410, "Synthesis cancelled")
        if not entry["call"] and time.time()-entry["created"] > 120:
            raise HTTPException(503, "Submission interrupted; create a new attempt")
        return entry

    @web.get("/v1/results/{call_id}")
    async def result(call_id: str):
        entry = await lookup(call_id)
        if not entry["call"]:
            return JSONResponse({"state": "pending"}, 202)
        try:
            value = await modal.FunctionCall.from_id(entry["call"]).get.aio(timeout=0)
        except TimeoutError:
            return JSONResponse({"state": "pending"}, 202)
        except Exception:
            return JSONResponse({"state": "failed", "error": "Voice synthesis failed; retry with a shorter cue or reference"}, 502)
        if not isinstance(value, dict) or not isinstance(value.get("audio"), bytes):
            raise HTTPException(502, "Invalid synthesis result")
        return {"state": "done", "audio": base64.b64encode(value["audio"]).decode(), "mime": "audio/ogg",
                "duration": value["duration"], "voice_id": value["voice_id"]}

    @web.delete("/v1/results/{call_id}")
    async def cancel(call_id: str):
        entry = await lookup(call_id)
        if entry["call"]:
            await modal.FunctionCall.from_id(entry["call"]).cancel.aio()
        entry["cancelled"] = True
        await requests.put.aio(call_id, entry)
        return {"state": "cancelled"}
    return web


@app.local_entrypoint()
def warm_weights():
    prepare.remote()
