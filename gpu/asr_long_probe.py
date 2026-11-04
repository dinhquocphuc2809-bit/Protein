"""One-window production Qwen execution with sustained-run telemetry; isolated app."""
import os
import time
import uuid

import modal
from gpu.asr import image, weights
from gpu.asr_comparison import Probe as InstrumentedProbe, GPU

app = modal.App('vocalm-qwen-long-' + GPU.lower())


@app.cls(image=image, gpu=GPU, cpu=2, memory=16384,
         volumes={'/weights': weights}, min_containers=0, max_containers=1,
         scaledown_window=30, startup_timeout=300, timeout=240)
class LongProbe:
    @modal.enter()
    def load(self):
        from gpu.resource_monitor import Monitor
        cls = InstrumentedProbe._get_user_cls()
        self.probe = cls()
        cls.__dict__['load']._get_raw_f()(self.probe)
        self.measure_raw = cls.__dict__['measure']._get_raw_f()
        self.container_id = uuid.uuid4().hex
        self.monitor = Monitor()

    @modal.exit()
    def close(self):
        self.monitor.stop.set()
        self.monitor.thread.join(timeout=3)

    @modal.method()
    def measure(self, audio: bytes):
        before = self.monitor.begin()
        started, cpu_start = time.perf_counter(), time.process_time()
        try:
            result = self.measure_raw(self.probe, audio)
            result['ok'] = True
        except Exception as error:
            category = ('oom' if 'out of memory' in str(error).lower() else
                        'alignment' if 'align' in str(error).lower() else 'inference')
            result = {'ok': False, 'error_type': type(error).__name__, 'error_category': category,
                      'seconds': time.perf_counter()-started, 'cpu_seconds': time.process_time()-cpu_start}
        result.update(container_id=self.container_id, before=before, after=self.monitor.finish())
        return result
