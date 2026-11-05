"""Bounded real T4 batching / snapshot / full-video candidate test, isolated app."""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--batch', type=int, choices=(1, 2, 4), default=4)
    parser.add_argument('--snapshot-cycles', type=int, choices=range(0, 7), default=0)
    parser.add_argument('--restore-only', action='store_true')
    parser.add_argument('--account', type=int, choices=(1, 2, 3), default=1)
    args = parser.parse_args()
    env = environment(args.account)
    env.update(VOCALM_ASR_SNAPSHOT='1', VOCALM_ASR_BATCH=str(args.batch), PYTHONPATH=str(ROOT))
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    import modal
    from backend.jobs import audio_windows
    from backend.asr_merge import WindowMerger
    from backend.subtitles import words_to_cues, speech_units
    audio = ROOT/'.private/asr-long-video/audio.wav'
    private = ROOT/'.private/qwen-improvement'
    private.mkdir(exist_ok=True)
    label = 'restore' if args.restore_only else 'full' if args.full else 'sample'
    path = ROOT/f'research/benchmarks/qwen-optimized-{label}.json'
    if path.exists():
        raise ValueError('Archive existing optimized report before repeating')
    report = {'at': datetime.now(timezone.utc).isoformat(), 'snapshot': True, 'account': args.account,
              'cpu': 2, 'ram_mib': 16384, 'gpu': 'T4', 'full': args.full, 'calls': [], 'cycles': [], 'passed': False,
              'production_changed': False, 'source_sha256': hashlib.sha256((ROOT/'gpu/asr.py').read_bytes()).hexdigest()}
    def save():
        path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    def cli(*parts, timeout=60):
        return subprocess.run([sys.executable, '-m', 'modal', *parts], cwd=ROOT, env=env,
                              capture_output=True, encoding='utf-8', timeout=timeout)
    app_id = None
    def retire():
        deadline = time.monotonic()+180
        while True:
            result = cli('container', 'list', '--app-id', app_id, '--json')
            if result.returncode:
                raise RuntimeError('Cannot verify container retirement')
            if not json.loads(result.stdout):
                return
            if time.monotonic() >= deadline:
                raise TimeoutError('Container retirement timeout')
            time.sleep(5)
    try:
        deployed = cli('deploy', 'gpu/asr_optimized_probe.py', timeout=300)
        (private/f'{label}-deploy.log').write_text(deployed.stdout+deployed.stderr, encoding='utf-8')
        if deployed.returncode:
            raise RuntimeError('Probe deploy failed; private log retained')
        apps = json.loads(cli('app', 'list', '--json').stdout)
        app_id = next(a['app_id'] for a in apps if a['description'] == 'vocalm-qwen-t4-optimized-test' and a['state'] == 'deployed')
        report['app_id'] = app_id
        worker = modal.Cls.from_name('vocalm-qwen-t4-optimized-test', 'Probe')()
        sample_indices = [1, 40, 165, 181, 187, 200, 286, 374]
        samples = {i: row for i, row in enumerate(audio_windows(audio, 14400)) if i in sample_indices}
        def invoke(group, batch, indices, category='calls'):
            start = time.perf_counter()
            call = worker.measure.spawn([g[0] for g in group], batch)
            try:
                value = call.get(timeout=300)
            except BaseException:
                call.cancel(terminate_containers=True)
                raise
            results = value.pop('results')
            value.update(rpc_seconds=time.perf_counter()-start, indices=indices,
                         word_counts=[len(r['words']) for r in results],
                         alignment_recoveries=sum(r['alignment_recoveries'] for r in results))
            assert len(results) == len(group)
            for result in results:
                assert all(0 <= w['start'] <= w['end'] <= result['duration']+.001 for w in result['words'])
            report[category].append(value)
            save()
            with (private/f'{label}-results.jsonl').open('a', encoding='utf-8') as file:
                file.write(json.dumps({'category': category, 'indices': indices, 'batch': batch, 'results': results}, ensure_ascii=False)+'\n')
            print(json.dumps({'indices': indices, 'batch': batch, 'seconds': round(value['seconds'], 3),
                              'rpc': round(value['rpc_seconds'], 3), 'words': value['word_counts']}), flush=True)
            return results
        for cycle in range(args.snapshot_cycles):
            retire()
            invoke([samples[1]], args.batch, [1], 'cycles')
            assert report['cycles'][-1]['call'] == 1
        start = time.perf_counter()
        if args.full:
            merger, iterator, index = WindowMerger(), iter(audio_windows(audio, 14400)), 0
            while group := list(islice(iterator, 4)):
                if time.perf_counter()-start > 7200:
                    raise TimeoutError('Two-hour benchmark budget reached')
                results = invoke(group, args.batch, list(range(index, index+len(group))))
                for row, result in zip(group, results):
                    merger.append(result['words'], row[1], result['duration'])
                index += len(group)
            cues = words_to_cues(merger.words, ensure_punctuation=True)
            (private/'full-words.json').write_text(json.dumps(merger.words, ensure_ascii=False), encoding='utf-8')
            (private/'full-cues.json').write_text(json.dumps([c.model_dump() for c in cues], ensure_ascii=False), encoding='utf-8')
            report.update(windows=index, cues=len(cues), speech_units=len(speech_units(cues)), seams=merger.seams)
            assert index == 375
        elif not args.restore_only:
            for batch in (1, 2, 4):
                for offset in range(0, len(sample_indices), 4):
                    indices = sample_indices[offset:offset+4]
                    invoke([samples[i] for i in indices], batch, indices)
        report.update(wall_seconds=time.perf_counter()-start, passed=True)
    except Exception as error:
        report['error_type'] = type(error).__name__
        (private/f'{label}-error.txt').write_text(str(error), encoding='utf-8')
        print('Probe failed: '+type(error).__name__, flush=True)
    finally:
        if app_id:
            try:
                logs = cli('app', 'logs', app_id, '--source', 'system', '--tail', '1000', '--timestamps', '--show-container-id')
                (private/f'{label}-system.log').write_text(logs.stdout+logs.stderr, encoding='utf-8')
                report['snapshot_lines'] = [line for line in logs.stdout.splitlines() if 'snapshot' in line.lower()
                    and line[:10] == report['at'][:10]]
            finally:
                result = cli('app', 'stop', app_id, '--yes')
                report['stop_requested'] = result.returncode == 0
                retire()
                report['zero_containers'] = True
        save()
    return 0 if report['passed'] and report.get('zero_containers') else 1


if __name__ == '__main__':
    raise SystemExit(main())
