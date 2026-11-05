"""Single-speaker Qwen ASR with VAD and actual forced alignment on backend accounts."""
from __future__ import annotations

import os
import modal

app = modal.App("auvirel-asr")
weights = modal.Volume.from_name("auvirel-asr-weights", create_if_missing=True)
image = (modal.Image.debian_slim(python_version="3.11").apt_install("ffmpeg", "libsndfile1", "sox")
         .pip_install("torch==2.8.0", "torchaudio==2.8.0", "soundfile==0.13.1", "qwen-asr==0.0.6", "stable-ts==2.19.1", "silero-vad==6.2.3")
         .env({"HF_HOME": "/weights/huggingface"}))
SNAPSHOT = os.environ.get("VOCALM_ASR_SNAPSHOT", "1") == "1"
INFERENCE_BATCH = int(os.environ.get("VOCALM_ASR_BATCH", "4"))
if INFERENCE_BATCH not in (1, 2, 4):
    raise ValueError("ASR inference batch must be 1, 2 or 4")
image = image.env({'VOCALM_ASR_SNAPSHOT': '1' if SNAPSHOT else '0',
                   'VOCALM_ASR_BATCH': str(INFERENCE_BATCH)}).add_local_python_source("gpu", "backend")
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
         timeout=240, startup_timeout=300, enable_memory_snapshot=SNAPSHOT,
         experimental_options={"enable_gpu_snapshot": True} if SNAPSHOT else {})
class Recognizer:
    @modal.enter(snap=SNAPSHOT)
    def load(self):
        import torch
        from huggingface_hub import snapshot_download
        from qwen_asr import Qwen3ASRModel
        from silero_vad import load_silero_vad
        torch.set_num_threads(2)
        self.torch = torch
        self.model = Qwen3ASRModel.from_pretrained(
            snapshot_download("Qwen/Qwen3-ASR-1.7B", revision=ASR_REV, local_files_only=True),
            dtype=torch.float16, device_map="cuda:0", attn_implementation="sdpa", max_inference_batch_size=INFERENCE_BATCH, max_new_tokens=512,
            forced_aligner=snapshot_download("Qwen/Qwen3-ForcedAligner-0.6B", revision=ALIGN_REV, local_files_only=True),
            forced_aligner_kwargs={"dtype": torch.float16, "device_map": "cuda:0", "attn_implementation": "sdpa"})
        self.vad = load_silero_vad()
        self.whisper = None
        if SNAPSHOT:
            import numpy as np
            # Initialize CUDA kernels without retaining customer audio in a snapshot.
            self.model.transcribe(audio=(np.zeros(16000, dtype=np.float32), 16000), language="English")
            torch.cuda.synchronize()

    @modal.method()
    def transcribe(self, wav: bytes, language="auto"):
        return self._transcribe_many([wav], language)[0]

    @modal.method()
    def transcribe_many(self, wavs: list[bytes], language="auto"):
        return self._transcribe_many(wavs, language)

    def _transcribe_many(self, wavs, language):
        import io
        import numpy as np
        import soundfile as sf
        from silero_vad import get_speech_timestamps
        from gpu.alignment import bounded_alignment, whisper_alignment_language
        from backend.asr_text import restore_punctuation

        if not isinstance(wavs, list) or not 1 <= len(wavs) <= 4:
            raise ValueError("Expected 1 to 4 bounded audio windows")
        code = language.split("-")[0]
        if code != "auto" and code not in LANGUAGES:
            raise ValueError("Unsupported recognition language")
        results, pieces = [], []
        sr = 16000
        for index, wav in enumerate(wavs):
            if not isinstance(wav, bytes) or not 44 <= len(wav) <= 2*1024**2 or wav[:4] != b"RIFF" or wav[8:12] != b"WAVE":
                raise ValueError("Expected bounded RIFF WAV")
            audio, rate = sf.read(io.BytesIO(wav), dtype="float32", always_2d=True)
            if rate != sr or audio.shape[1] != 1 or not 0 < len(audio)/sr <= 30 or not np.isfinite(audio).all():
                raise ValueError("Expected finite mono 16 kHz audio up to 30 seconds")
            audio = audio[:, 0]
            results.append({"words": [], "segments": [], "language": None, "duration": len(audio)/sr,
                            "model": "Qwen/Qwen3-ASR-1.7B", "alignment_recoveries": 0})
            regions = get_speech_timestamps(self.torch.from_numpy(audio), self.vad, sampling_rate=sr,
                                            max_speech_duration_s=25, speech_pad_ms=160)
            for region in regions:
                begin, end = int(region["start"]), int(region["end"])
                pieces.append((index, begin, audio[begin:end]))
        recognized_all = []
        # Bounded inference batches amortize GPU kernels without parallel model copies.
        for offset in range(0, len(pieces), INFERENCE_BATCH):
            group = pieces[offset:offset+INFERENCE_BATCH]
            recognized_group = None
            try:
                recognized_group = self.model.transcribe(audio=[(p[2], sr) for p in group],
                    language=LANGUAGES.get(code), return_time_stamps=False)
            except self.torch.cuda.OutOfMemoryError:
                pass
            if recognized_group is None:
                # Leave the exception frame before collecting tensors held by its
                # traceback; otherwise even the serial retry can retain the OOM batch.
                import gc
                gc.collect()
                self.torch.cuda.empty_cache()
                for piece in group:
                    recognized_all.extend(self.model.transcribe(audio=(piece[2], sr),
                        language=LANGUAGES.get(code), return_time_stamps=False))
            else:
                recognized_all.extend(recognized_group)
        if len(recognized_all) != len(pieces):
            raise ValueError("ASR batch coverage mismatch")
        for (index, begin, chunk), recognized in zip(pieces, recognized_all):
            result = results[index]
            detected = recognized.language
            result['language'] = detected
            if not recognized.text.strip():
                continue
            local = None
            if detected in ALIGNED:
                aligned = self.model.forced_aligner.align(audio=(chunk, sr), text=recognized.text, language=detected)[0]
                try:
                    local = bounded_alignment(
                        [{"text": str(w.text), "start": float(w.start_time), "end": float(w.end_time)} for w in aligned], len(chunk)/sr)
                except ValueError:
                    result['alignment_recoveries'] += 1
            if local is None:
                # Align the Qwen transcript again; never substitute another ASR
                # provider or accept unbounded model timestamps.
                import stable_whisper
                if self.whisper is None:
                    self.whisper = stable_whisper.load_model("small", device="cuda", download_root="/weights/whisper")
                whisper_code = next((k for k, v in LANGUAGES.items() if v == detected), code)
                from whisper.tokenizer import LANGUAGES as WHISPER_LANGUAGES
                whisper_code = whisper_alignment_language(whisper_code, tuple(WHISPER_LANGUAGES)[:self.whisper.num_languages])
                aligned = self.whisper.align(chunk, recognized.text, language=whisper_code, verbose=False)
                if aligned is None:
                    raise ValueError("Forced alignment failed")
                local = bounded_alignment(
                    [{"text": str(w.word), "start": float(w.start), "end": float(w.end)} for seg in aligned.segments for w in seg.words], len(chunk)/sr)
            result['segments'].append({'text': recognized.text, 'start': begin/sr, 'end': (begin+len(chunk))/sr})
            for word in restore_punctuation(local, recognized.text):
                result['words'].append({"text": word["text"], "start": round(word["start"]+begin/sr, 3),
                    "end": round(min(word["end"]+begin/sr, result['duration']), 3)})
        return results


@app.local_entrypoint()
def warm_weights():
    prepare.remote()
