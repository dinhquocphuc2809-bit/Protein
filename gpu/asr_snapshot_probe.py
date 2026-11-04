"""Deployed, isolated GPU snapshot experiment; no production settings changed."""
import os
import time
from pathlib import Path

import modal
from gpu.asr import Recognizer, image, weights

SNAPSHOT = os.environ.get('VOCALM_SNAPSHOT_TEST', '1') == '1'
NAME = 'vocalm-qwen-snapshot-test' if SNAPSHOT else 'vocalm-qwen-cold-control'
app = modal.App(NAME)
probe_image = image.add_local_file(
    Path(__file__).resolve().parents[1]/'.private/asr-snapshot/warmup.wav', '/probe/warmup.wav')


@app.cls(image=probe_image, gpu='T4', cpu=2, memory=16384,
         volumes={'/weights': weights}, min_containers=0, max_containers=1,
         scaledown_window=10, timeout=180, startup_timeout=300,
         enable_memory_snapshot=SNAPSHOT,
         experimental_options={'enable_gpu_snapshot': True} if SNAPSHOT else {})
class Probe:
    @modal.enter(snap=SNAPSHOT)
    def initialize(self):
        import uuid
        import torch
        self.initialization_id = uuid.uuid4().hex
        cls = Recognizer._get_user_cls()
        self.engine = cls()
        started = time.perf_counter()
        cls.__dict__['load']._get_raw_f()(self.engine)
        torch.cuda.synchronize()
        self.load_seconds = time.perf_counter()-started
        self.run = cls.__dict__['transcribe']._get_raw_f()
        started = time.perf_counter()
        self.run(self.engine, Path('/probe/warmup.wav').read_bytes(), 'auto')
        torch.cuda.synchronize()
        self.warmup_seconds = time.perf_counter()-started
        print('VOCALM_INITIALIZED ' + self.initialization_id, flush=True)

    @modal.enter()
    def after_start(self):
        import uuid
        self.boot_id = uuid.uuid4().hex
        self.calls = 0
        print('VOCALM_BOOT ' + self.boot_id, flush=True)

    @modal.method()
    def measure(self, wav: bytes):
        import torch
        import hashlib
        import json
        started = time.perf_counter()
        result = self.run(self.engine, wav, 'auto')
        torch.cuda.synchronize()
        self.calls += 1
        words = result['words']
        return {'initialization_id': self.initialization_id, 'boot_id': self.boot_id,
                'call': self.calls, 'model_load_seconds': self.load_seconds,
                'warmup_seconds': self.warmup_seconds, 'inference_seconds': time.perf_counter()-started,
                'model': result['model'], 'gpu': torch.cuda.get_device_name(),
                'word_count': len(words), 'language': result['language'],
                'valid_times': bool(words) and all(0 <= w['start'] <= w['end'] <= result['duration']+.001 for w in words),
                'output_sha256': hashlib.sha256(json.dumps(words, sort_keys=True).encode()).hexdigest()}
