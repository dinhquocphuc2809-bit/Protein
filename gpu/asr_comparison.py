"""Isolated T4/L4 comparison using the pinned production recognition methods."""
import hashlib
import json
import os
from pathlib import Path
import time

import modal
from gpu.asr import Recognizer, image, weights, ASR_REV, ALIGN_REV

GPU = os.environ.get('VOCALM_COMPARE_GPU', 'T4')
if GPU not in {'T4', 'L4', 'A10', 'L40S'}:
    raise ValueError('Expected T4, L4, A10 or L40S')
app = modal.App('vocalm-qwen-comparison-' + GPU.lower())


@app.cls(image=image, gpu=GPU, cpu=2, memory=16384, volumes={'/weights': weights},
         min_containers=0, max_containers=1, scaledown_window=30,
         timeout=240, startup_timeout=300)
class Probe:
    @modal.enter()
    def load(self):
        import torch
        import silero_vad
        import resource
        # Modal 1.6.3 is pinned. Invoke the original methods locally in this
        # isolated container, avoiding a divergent copy of the ASR pipeline.
        cls = Recognizer._get_user_cls()
        self.engine = cls()
        started = time.perf_counter()
        cls.__dict__['load']._get_raw_f()(self.engine)
        torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - started
        self.run = cls.__dict__['transcribe']._get_raw_f()
        self.torch, self.resource = torch, resource
        self.calls = 0
        self.times, self.counts = {}, {}

        def timed(name, function):
            def wrapper(*args, **kwargs):
                torch.cuda.synchronize()
                start = time.perf_counter()
                try:
                    return function(*args, **kwargs)
                finally:
                    torch.cuda.synchronize()
                    self.times[name] = self.times.get(name, 0) + time.perf_counter() - start
                    self.counts[name] = self.counts.get(name, 0) + 1
            return wrapper
        self.engine.model.transcribe = timed('recognition', self.engine.model.transcribe)
        self.engine.model.forced_aligner.align = timed('qwen_alignment', self.engine.model.forced_aligner.align)
        silero_vad.get_speech_timestamps = timed('vad', silero_vad.get_speech_timestamps)

    @modal.method()
    def measure(self, audio: bytes):
        torch = self.torch
        self.times, self.counts = {}, {}
        torch.cuda.reset_peak_memory_stats()
        cpu_start, started = time.process_time(), time.perf_counter()
        result = self.run(self.engine, audio, 'auto')
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - started
        self.calls += 1
        memory = {}
        for name in ['memory.current', 'memory.peak', 'memory.max', 'memory.events', 'memory.swap.current']:
            path = Path('/sys/fs/cgroup') / name
            if path.exists():
                memory[name] = path.read_text().strip()
        return {'words': result['words'], 'language': result['language'], 'duration': result['duration'],
                'alignment_recoveries': result['alignment_recoveries'], 'seconds': elapsed,
                'cpu_seconds': time.process_time()-cpu_start, 'stages': self.times, 'stage_calls': self.counts,
                'model_load_seconds': self.load_seconds, 'container_call': self.calls,
                'gpu_name': torch.cuda.get_device_name(),
                'gpu_total_bytes': torch.cuda.get_device_properties(0).total_memory,
                'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
                'peak_rss_bytes': self.resource.getrusage(self.resource.RUSAGE_SELF).ru_maxrss * 1024,
                'cgroup': memory}


@app.local_entrypoint()
def main():
    import sys
    import wave
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from backend.jobs import audio_windows
    from backend.subtitles import words_to_cues, validate_cues
    audio = root/'.private/asr-second-video/video.wav'
    with wave.open(str(audio)) as wav:
        duration = wav.getnframes()/wav.getframerate()
    report = {'video': '7jb0q3Mo9Rg', 'gpu_requested': GPU, 'cpu': 2, 'ram_mib': 16384,
              'audio_sha256': hashlib.sha256(audio.read_bytes()).hexdigest(), 'duration_seconds': duration,
              'asr_revision': ASR_REV, 'aligner_revision': ALIGN_REV,
              'production_source_sha256': hashlib.sha256((root/'gpu/asr.py').read_bytes()).hexdigest(),
              'scope': 'Two full uncached passes, production VAD/ASR/alignment methods; no download, translation or TTS',
              'passes': []}
    destination = root/'research/benchmarks'/f'qwen-full-video-{GPU}.json'
    private = root/'.private/asr-gpu-comparison'
    private.mkdir(exist_ok=True)
    region = os.environ.get('VOCALM_COMPARE_REGION')
    report['region_requested'] = region
    report['account'] = int(os.environ.get('VOCALM_COMPARE_ACCOUNT', '1'))
    worker = Probe.with_options(region=region)() if region else Probe()
    try:
        for repeat in range(2):
            start = time.perf_counter()
            rows, words = [], []
            run = {'repeat': repeat, 'chunks': rows}
            report['passes'].append(run)
            for data, offset, keep_start, keep_end in audio_windows(audio, 14400):
                rpc_start = time.perf_counter()
                call = worker.measure.spawn(data)
                try:
                    result = call.get(timeout=300)
                except BaseException:
                    call.cancel(terminate_containers=True)
                    raise
                current = result.pop('words')
                assert all(0 <= w['start'] <= w['end'] <= result['duration']+.001 for w in current)
                words.extend({**w, 'start': w['start']+offset, 'end': w['end']+offset}
                             for w in current if keep_start <= (w['start']+w['end'])/2+offset < keep_end)
                result.update(offset=offset, words=len(current), rpc_seconds=time.perf_counter()-rpc_start)
                rows.append(result)
                destination.write_text(json.dumps(report, indent=2)+'\n')
                print(json.dumps({'gpu': GPU, 'repeat': repeat, 'offset': offset,
                                  'seconds': round(result['seconds'], 3), 'words': len(current)}), flush=True)
            words.sort(key=lambda w: w['start'])
            cues = validate_cues(words_to_cues(words))
            encoded = json.dumps(words, ensure_ascii=False, sort_keys=True).encode()
            (private/f'{GPU}-{repeat}-words.json').write_bytes(encoded)
            run.update(wall_seconds=time.perf_counter()-start, words=len(words), cues=len(cues),
                       last=cues[-1].end, output_sha256=hashlib.sha256(encoded).hexdigest(), passed=True)
            destination.write_text(json.dumps(report, indent=2)+'\n')
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, error_type=type(error).__name__)
        raise
    finally:
        destination.write_text(json.dumps(report, indent=2)+'\n')
