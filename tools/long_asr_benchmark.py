"""Bounded full-audio GPU comparison on explicitly separated backend accounts."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', required=True, choices=['T4', 'A10', 'L40S', 'A100-40GB', 'A100-80GB'])
    parser.add_argument('--account', required=True, type=int, choices=[1, 2])
    args = parser.parse_args()
    if args.account != (1 if args.gpu in {'T4', 'A100-40GB'} else 2):
        parser.error('Use account1 for T4/A100-40GB and account2 for A10/L40S/A100-80GB')
    env = environment(args.account)
    env.update(VOCALM_COMPARE_GPU=args.gpu, VOCALM_COMPARE_ACCOUNT=str(args.account), PYTHONPATH=str(ROOT))
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    from gpu.asr_long_probe import app, LongProbe
    from gpu.asr import ASR_REV, ALIGN_REV
    from backend.jobs import audio_windows
    from backend.subtitles import words_to_cues, validate_cues
    audio = ROOT/'.private/asr-long-video/audio.wav'
    with wave.open(str(audio)) as wav:
        duration = wav.getnframes()/wav.getframerate()
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
    with audio.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    report = {'video': 'YGi-aPUsZrQ', 'at': datetime.now(timezone.utc).isoformat(),
              'account': args.account, 'gpu_requested': args.gpu, 'cpu': 2, 'ram_mib': 16384,
              'audio_sha256': digest, 'duration_seconds': duration, 'snapshot': False,
              'asr_revision': ASR_REV, 'aligner_revision': ALIGN_REV,
              'production_source_sha256': hashlib.sha256((ROOT/'gpu/asr.py').read_bytes()).hexdigest(),
              'scope': 'One full uncached production Qwen/VAD/alignment pass; local client; no translation/TTS',
              'chunks': [], 'passed': False, 'production_changed': False}
    destination = ROOT/'research/benchmarks'/f'qwen-long-{args.gpu}.json'
    if destination.exists():
        raise ValueError('Archive the prior benchmark report before repeating')
    def save():
        partial = destination.with_suffix('.partial')
        partial.write_text(json.dumps(report, indent=2)+'\n')
        partial.replace(destination)
    def cli(*parts):
        return subprocess.run([sys.executable, '-m', 'modal', *parts], env=env, cwd=ROOT,
                              capture_output=True, text=True, encoding='utf-8', timeout=45)
    save()
    words, failures, app_id = [], 0, None
    started = None
    private = ROOT/'.private/asr-long-video'
    try:
        with app.run():
            app_id = app.app_id
            report['app_id'] = app_id
            save()
            worker = LongProbe()
            started = time.perf_counter()
            for index, (data, offset, keep_start, keep_end) in enumerate(audio_windows(audio, 14400)):
                if time.perf_counter()-started > 10800:
                    raise TimeoutError('Three-hour benchmark wall-time budget reached')
                rpc_started = time.perf_counter()
                call = worker.measure.spawn(data)
                try:
                    result = call.get(timeout=300)
                except BaseException:
                    call.cancel(terminate_containers=True)
                    report['failed_offset'] = offset
                    raise
                current = result.pop('words', [])
                valid = all(isinstance(w['text'], str) and w['text'].strip()
                            and math.isfinite(w['start']) and math.isfinite(w['end'])
                            and 0 <= w['start'] <= w['end'] <= result['duration']+.001 for w in current)
                valid = valid and all(a['start'] <= b['start']+.001 for a, b in zip(current, current[1:]))
                result.update(index=index, offset=offset, keep_start=keep_start, keep_end=keep_end,
                              words=len(current), valid_times=valid, rpc_seconds=time.perf_counter()-rpc_started,
                              word_sha256=hashlib.sha256(json.dumps(current,sort_keys=True).encode()).hexdigest())
                if result['ok'] and not valid:
                    result.update(ok=False, error_category='timestamp_validation')
                if result['ok']:
                    words.extend({**w, 'start': w['start']+offset, 'end': w['end']+offset}
                                 for w in current if keep_start <= (w['start']+w['end'])/2+offset < keep_end)
                else:
                    failures += 1
                with (private/f'{args.gpu}-words.jsonl').open('a', encoding='utf-8') as file:
                    file.write(json.dumps({'index': index, 'offset': offset, 'words': current}, ensure_ascii=False)+'\n')
                report['chunks'].append(result)
                report.update(elapsed_seconds=time.perf_counter()-started, errors=failures,
                              processed_through_seconds=min(offset+28, duration))
                save()
                print(json.dumps({'gpu': args.gpu, 'account': args.account, 'index': index,
                                  'through': report['processed_through_seconds'], 'duration': duration,
                                  'seconds': round(result['seconds'],3), 'ok': result['ok'], 'errors': failures}), flush=True)
                if failures >= 10 or len(report['chunks']) >= 3 and all(not r['ok'] for r in report['chunks'][-3:]):
                    raise RuntimeError('Bounded error threshold reached')
            report['wall_seconds'] = time.perf_counter()-started
            words.sort(key=lambda w: w['start'])
            cues = validate_cues(words_to_cues(words), max_seconds=duration+.1)
            encoded = json.dumps(words, ensure_ascii=False, sort_keys=True).encode()
            (private/f'{args.gpu}-retained-words.json').write_bytes(encoded)
            report.update(words=len(words), cues=len(cues), last_cue_end=cues[-1].end,
                          output_sha256=hashlib.sha256(encoded).hexdigest(),
                          passed=failures == 0 and report['processed_through_seconds'] == duration)
    except Exception as error:
        report.update(error_type=type(error).__name__, passed=False)
        (private/f'{args.gpu}-error.txt').write_text(str(error), encoding='utf-8')
        print(json.dumps({'gpu':args.gpu, 'error_type':type(error).__name__}), flush=True)
    finally:
        if started is not None:
            report.setdefault('elapsed_seconds', time.perf_counter()-started)
        if app_id:
            try:
                stopped = cli('app', 'stop', app_id, '--yes')
                report['stop_requested'] = stopped.returncode == 0
                deadline = time.monotonic()+90
                while True:
                    apps = json.loads(cli('app', 'list', '--json').stdout)
                    state = next((a for a in apps if a['app_id'] == app_id), {})
                    containers = cli('container', 'list', '--app-id', app_id, '--json')
                    report['shutdown'] = {'state':state.get('state'), 'tasks':state.get('tasks'),
                                          'containers':len(json.loads(containers.stdout)) if not containers.returncode else None}
                    report['stopped'] = (state.get('state') == 'stopped' and str(state.get('tasks')) == '0'
                                         and report['shutdown']['containers'] == 0)
                    if report['stopped'] or time.monotonic() > deadline:
                        break
                    time.sleep(5)
            except Exception as error:
                report['cleanup_error_type'] = type(error).__name__
        save()
    return 0 if report['passed'] and report.get('stopped') else 1


if __name__ == '__main__':
    raise SystemExit(main())
