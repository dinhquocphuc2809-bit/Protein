"""Isolated T4 quality/performance candidate with snapshot provenance."""
import time
import uuid

import modal
from gpu.asr import Recognizer, image, weights, SNAPSHOT

app = modal.App('vocalm-qwen-t4-optimized-test')


@app.cls(image=image, gpu='T4', cpu=2, memory=16384, volumes={'/weights': weights},
         min_containers=0, max_containers=1, scaledown_window=30, timeout=240, startup_timeout=300,
         enable_memory_snapshot=SNAPSHOT,
         experimental_options={'enable_gpu_snapshot': True} if SNAPSHOT else {})
class Probe:
    @modal.enter(snap=SNAPSHOT)
    def initialize(self):
        self.initialization_id = uuid.uuid4().hex
        cls = Recognizer._get_user_cls()
        self.engine = cls()
        started = time.perf_counter()
        cls.__dict__['load']._get_raw_f()(self.engine)
        self.load_seconds = time.perf_counter()-started

    @modal.enter()
    def boot(self):
        from gpu.resource_monitor import Monitor
        self.boot_id = uuid.uuid4().hex
        self.calls = 0
        self.monitor = Monitor()

    @modal.exit()
    def close(self):
        self.monitor.stop.set()
        self.monitor.thread.join(timeout=3)

    @modal.method()
    def measure(self, audio: list[bytes], batch=4, language='auto'):
        import gpu.asr as module
        import torch
        if batch not in (1, 2, 4):
            raise ValueError('Invalid inference batch')
        module.INFERENCE_BATCH = batch
        self.engine.model.max_inference_batch_size = batch
        torch.cuda.reset_peak_memory_stats()
        before = self.monitor.begin()
        started, cpu = time.perf_counter(), time.process_time()
        try:
            results = self.engine._transcribe_many(audio, language)
            torch.cuda.synchronize()
        finally:
            after = self.monitor.finish()
        self.calls += 1
        return {'results': results, 'seconds': time.perf_counter()-started, 'cpu_seconds': time.process_time()-cpu,
                'batch': batch, 'gpu': torch.cuda.get_device_name(), 'before': before, 'after': after,
                'peak_allocated_bytes': torch.cuda.max_memory_allocated(), 'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                'initialization_id': self.initialization_id, 'boot_id': self.boot_id,
                'call': self.calls, 'load_seconds': self.load_seconds}
