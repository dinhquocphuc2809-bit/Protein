"""Real production ASR RPC, using only account 1 for a short bounded sample."""
import json
import os
from pathlib import Path
import time

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.environ.update(environment(1))
    import modal
    worker = modal.Cls.from_name('auvirel-asr', 'Recognizer')()
    started = time.monotonic()
    audio = ROOT / 'assets/imported/presets/vietnamese/Dang-Khoa.wav'
    import subprocess
    normalized = ROOT / '.private/asr-production.wav'
    subprocess.run(['ffmpeg', '-nostdin', '-y', '-v', 'error', '-i', str(audio), '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(normalized)], check=True)
    call = worker.transcribe.spawn(normalized.read_bytes(), 'vi')
    try:
        result = call.get(timeout=240)
    except BaseException:
        call.cancel()
        raise
    report = {'elapsed_seconds': time.monotonic()-started, 'result': result}
    (ROOT / 'research/benchmarks/production-asr.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('ASR completed:', len(result['words']), 'aligned words;', round(report['elapsed_seconds'], 3), 'seconds')


if __name__ == '__main__':
    main()
