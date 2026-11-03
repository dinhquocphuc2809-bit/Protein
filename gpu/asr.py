"""Single-speaker Qwen ASR with VAD and actual forced alignment on backend accounts."""
from __future__ import annotations

import os
import modal

app = modal.App("auvirel-asr")
weights = modal.Volume.from_name("auvirel-asr-weights", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "libsndfile1", "sox")
         .pip_install("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1", "qwen-asr==0.0.6", "stable-ts==2.19.1", "silero-vad==6.2.3")
         .env({"HF_HOME": "/weights/huggingface"}))
ASR_REV = "7278e1e70fe206f11671096ffdd38061171dd6e5"
ALIGN_REV = "c7cbfc2048c462b0d63a45797104fc9db3ad62b7"
LANGUAGES = {"en": "English", "zh": "Chinese", "yue": "Cantonese", "fr": "French", "de": "German", "it": "Italian",
             "ja": "Japanese", "ko": "Korean", "pt": "Portuguese", "ru": "Russian", "es": "Spanish", "vi": "Vietnamese",
             "ar": "Arabic", "id": "Indonesian", "th": "Thai", "tr": "Turkish", "hi": "Hindi", "ms": "Malay",
             "nl": "Dutch", "sv": "Swedish", "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
             "fil": "Filipino", "fa": "Persian", "el": "Greek", "hu": "Hungarian", "mk": "Macedonian", "ro": "Romanian"}
ALIGNED = {"English", "Chinese", "Cantonese", "French", "German", "Italian", "Japanese", "Korean", "Portuguese", "Russian", "Spanish"}


@app.function(image=image, volumes={"/weights": weights}, cpu=2, memory=8192, timeout=1200)
def prepare():
    from huggingface_hub import snapshot_download
    import stable_whisper
    from pathlib import Path
    snapshot_download("Qwen/Qwen3-ASR-1.7B", revision=ASR_REV)
    snapshot_download("Qwen/Qwen3-ForcedAligner-0.6B", revision=ALIGN_REV)
    if not Path("/weights/whisper/small.pt").exists():
        stable_whisper.load_model("small", device="cpu", download_root="/weights/whisper")
    weights.commit()


@app.cls(image=image, gpu=os.environ.get("AUVIREL_GPU", "T4"), cpu=2, memory=16384,
         volumes={"/weights": weights}, min_containers=0, max_containers=1, scaledown_window=30,
         timeout=180, startup_timeout=300)
class Recognizer:
    @modal.enter()
    def load(self):
        import torch
        from huggingface_hub import snapshot_download
        from qwen_asr import Qwen3ASRModel
        from silero_vad import load_silero_vad
        torch.set_num_threads(2)
        self.torch = torch
        self.model = Qwen3ASRModel.from_pretrained(
            snapshot_download("Qwen/Qwen3-ASR-1.7B", revision=ASR_REV, local_files_only=True),
            dtype=torch.float16, device_map="cuda:0", attn_implementation="sdpa", max_inference_batch_size=1, max_new_tokens=512,
            forced_aligner=snapshot_download("Qwen/Qwen3-ForcedAligner-0.6B", revision=ALIGN_REV, local_files_only=True),
            forced_aligner_kwargs={"dtype": torch.float16, "device_map": "cuda:0", "attn_implementation": "sdpa"})
        self.vad = load_silero_vad()
        self.whisper = None

    @modal.method()
    def transcribe(self, wav: bytes, language="auto"):
        import io
        import numpy as np
        import soundfile as sf
        from silero_vad import get_speech_timestamps

        if not 44 <= len(wav) <= 2*1024**2 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
            raise ValueError("Expected bounded RIFF WAV")
        audio, sr = sf.read(io.BytesIO(wav), dtype="float32", always_2d=True)
        if sr != 16000 or audio.shape[1] != 1 or len(audio)/sr > 30 or not np.isfinite(audio).all():
            raise ValueError("Expected finite mono 16 kHz audio up to 30 seconds")
        audio = audio[:, 0]
        code = language.split("-")[0]
        if code != "auto" and code not in LANGUAGES:
            raise ValueError("Unsupported recognition language")
        regions = get_speech_timestamps(self.torch.from_numpy(audio), self.vad, sampling_rate=16000,
                                        max_speech_duration_s=25, speech_pad_ms=160)
        words, detected = [], None
        for region in regions:
            begin, end = int(region["start"]), int(region["end"])
            chunk = audio[begin:end]
            source_language = LANGUAGES.get(code)
            recognized = self.model.transcribe(audio=(chunk, sr), language=source_language, return_time_stamps=False)[0]
            detected = recognized.language
            if not recognized.text.strip():
                continue
            if detected in ALIGNED:
                aligned = self.model.forced_aligner.align(audio=(chunk, sr), text=recognized.text, language=detected)[0]
                local = [{"text": str(w.text), "start": float(w.start_time), "end": float(w.end_time)} for w in aligned]
            else:
                import stable_whisper
                if self.whisper is None:
                    self.whisper = stable_whisper.load_model("small", device="cuda", download_root="/weights/whisper")
                whisper_code = next((k for k, v in LANGUAGES.items() if v == detected), code)
                if whisper_code == "fil":
                    whisper_code = "tl"
                aligned = self.whisper.align(chunk, recognized.text, language=whisper_code, verbose=False)
                if aligned is None:
                    raise ValueError("Forced alignment failed")
                local = [{"text": str(w.word), "start": float(w.start), "end": float(w.end)} for seg in aligned.segments for w in seg.words]
            previous = 0.0
            for word in local:
                if not previous <= word["start"] <= word["end"] <= len(chunk)/sr+.05:
                    raise ValueError("Alignment produced invalid timestamps")
                previous = word["start"]
                words.append({"text": word["text"], "start": round(word["start"]+begin/sr, 3), "end": round(min(word["end"]+begin/sr, len(audio)/sr), 3)})
        return {"words": words, "language": detected, "duration": len(audio)/sr}


@app.local_entrypoint()
def warm_weights():
    prepare.remote()
