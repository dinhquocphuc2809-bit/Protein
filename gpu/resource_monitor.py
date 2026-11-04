"""Bounded process/device telemetry for isolated GPU benchmarks."""
from pathlib import Path
import subprocess
import threading
import time


def process_memory():
    values = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        key, _, value = line.partition(':')
        if key in {'VmRSS', 'VmHWM', 'VmSize'}:
            values[key+'_bytes'] = int(value.strip().split()[0])*1024
    return values


def cgroup_metrics():
    values = {}
    for relative in ['memory.current', 'memory.peak', 'memory.max', 'memory.events',
                     'memory.swap.current', 'cpu.stat', 'cpu.max',
                     'memory/memory.usage_in_bytes', 'memory/memory.max_usage_in_bytes',
                     'memory/memory.limit_in_bytes', 'memory/memory.failcnt', 'cpu/cpu.stat']:
        try:
            values[relative] = (Path('/sys/fs/cgroup')/relative).read_text().strip()
        except OSError:
            pass
    return values


class Monitor:
    def __init__(self):
        self.lock = threading.Lock()
        self.active = False
        self.values = {}
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.thread.start()

    def begin(self):
        with self.lock:
            self.values = {'samples': 0, 'gpu_samples': 0, 'rss_peak_bytes': 0,
                           'gpu_used_peak_bytes': 0, 'gpu_utilization_sum': 0,
                           'gpu_utilization_max': 0}
            self.active = True
        return {'process': process_memory(), 'cgroup': cgroup_metrics()}

    def finish(self):
        current = process_memory()
        with self.lock:
            self.active = False
            values = dict(self.values)
        values['rss_peak_bytes'] = max(values['rss_peak_bytes'], current.get('VmRSS_bytes', 0))
        values['gpu_utilization_mean'] = (values.pop('gpu_utilization_sum')/values['gpu_samples']
                                          if values['gpu_samples'] else None)
        return {'samples': values, 'process': current, 'cgroup': cgroup_metrics()}

    def loop(self):
        while not self.stop.wait(1):
            with self.lock:
                if not self.active:
                    continue
                phase = self.values
            try:
                rss = process_memory().get('VmRSS_bytes', 0)
                run = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu',
                                      '--format=csv,noheader,nounits'],
                                     capture_output=True, text=True, timeout=2)
                used, utilization = map(float, run.stdout.strip().splitlines()[0].split(','))
                with self.lock:
                    if self.active and self.values is phase:
                        phase['samples'] += 1
                        phase['rss_peak_bytes'] = max(phase['rss_peak_bytes'], rss)
                        phase['gpu_samples'] += 1
                        phase['gpu_used_peak_bytes'] = max(phase['gpu_used_peak_bytes'], int(used*1024**2))
                        phase['gpu_utilization_sum'] += utilization
                        phase['gpu_utilization_max'] = max(phase['gpu_utilization_max'], utilization)
            except Exception as error:
                with self.lock:
                    if self.active and self.values is phase:
                        phase['sampling_error_type'] = type(error).__name__
