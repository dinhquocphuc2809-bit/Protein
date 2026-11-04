"""Bounded live Qwen regression on locally retained incident audio; no transcript output."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--account', type=int, choices=[1, 2, 3], required=True)
    parser.add_argument('--offsets', type=int, nargs='+', default=[576, 600, 624, 648])
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    if Path(args.report).name != args.report or not args.report.endswith('.json'):
        parser.error('Report must be a JSON basename')
    os.environ.update(environment(args.account))
    import modal
    import sys
    sys.path.insert(0, str(ROOT))
    from backend.jobs import audio_windows
    worker = modal.Cls.from_name('auvirel-asr', 'Recognizer')()
    report = {'at': datetime.now(timezone.utc).isoformat(), 'account': args.account,
              'video': 'f6YA_OvKbhY', 'scope': 'Real Qwen RPC on incident audio, no other ASR provider', 'checks': []}
    for audio, offset, _, _ in audio_windows(ROOT/'.private/asr-investigation/video.wav', 14400):
        if offset not in args.offsets:
            continue
        started = time.monotonic()
        call = worker.transcribe.spawn(audio, 'auto')
        try:
            result = call.get(timeout=240)
            words, duration = result['words'], result['duration']
            valid = bool(words) and all(math.isfinite(w['start']) and math.isfinite(w['end'])
                and 0 <= w['start'] <= w['end'] <= duration + .001 for w in words)
            valid = valid and all(a['start'] <= b['start'] for a, b in zip(words, words[1:]))
            row = {'offset': offset, 'seconds': round(time.monotonic()-started, 3),
                   'words': len(words), 'language': result['language'], 'model': result.get('model'),
                   'alignment_recoveries': result.get('alignment_recoveries'), 'valid_times': valid,
                   'passed': valid and result.get('model') == 'Qwen/Qwen3-ASR-1.7B'}
        except Exception as error:
            call.cancel()
            row = {'offset': offset, 'passed': False, 'error_type': type(error).__name__}
        report['checks'].append(row)
        (ROOT/'research'/args.report).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(row), flush=True)
        if not row['passed']:
            return 1
    return 0 if len(report['checks']) == len(set(args.offsets)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
