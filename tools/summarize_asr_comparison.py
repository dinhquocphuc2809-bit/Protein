"""Summarize completed GPU measurements; never turn queued failures into timings."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT/'research/benchmarks'
    result = {'video': '7jb0q3Mo9Rg', 'gpus': {}}
    identities = []
    for gpu in ['T4', 'L4']:
        path = folder/f'qwen-full-video-{gpu}.json'
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        summary = {'passed': data.get('passed', False), 'passes': []}
        result['gpus'][gpu] = summary
        if not summary['passed']:
            summary['error_type'] = data.get('error_type', 'unfinished')
            continue
        identities.append(tuple(data[k] for k in ['audio_sha256', 'asr_revision', 'aligner_revision', 'production_source_sha256', 'cpu', 'ram_mib']))
        for run in data['passes']:
            rows = run['chunks']
            assert run['passed'] and len(rows) == 34
            assert [r['offset'] for r in rows] == list(range(0, 793, 24))
            summary['passes'].append({
                'repeat': run['repeat'], 'wall_seconds': run['wall_seconds'],
                'worker_seconds': sum(r['seconds'] for r in rows),
                'rpc_seconds': sum(r['rpc_seconds'] for r in rows),
                'model_load_seconds': rows[0]['model_load_seconds'],
                'first_call_rpc_seconds': rows[0]['rpc_seconds'],
                'stages': {k: sum(r['stages'].get(k, 0) for r in rows)
                           for k in ['vad', 'recognition', 'qwen_alignment']},
                'gpu_total_gib': rows[0]['gpu_total_bytes']/2**30,
                'peak_allocated_gib': max(r['peak_allocated_bytes'] for r in rows)/2**30,
                'peak_reserved_gib': max(r['peak_reserved_bytes'] for r in rows)/2**30,
                'peak_rss_gib': max(r['peak_rss_bytes'] for r in rows)/2**30,
                'alignment_recoveries': sum(r['alignment_recoveries'] for r in rows),
                'words': run['words'], 'cues_before_speech_reflow': run['cues'],
                'output_sha256': run['output_sha256'],
            })
        summary['repeat_output_identical'] = len({r['output_sha256'] for r in data['passes']}) == 1
    result['comparison_complete'] = len(identities) == 2
    if result['comparison_complete']:
        assert identities[0] == identities[1], 'Benchmark configuration/input differs'
        t4, l4 = [result['gpus'][gpu]['passes'][1] for gpu in ['T4', 'L4']]
        result['warm_worker_speedup'] = t4['worker_seconds']/l4['worker_seconds']
        result['warm_rpc_speedup'] = t4['wall_seconds']/l4['wall_seconds']
    (folder/'qwen-full-video-summary.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
