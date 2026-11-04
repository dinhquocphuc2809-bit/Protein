"""Summarize actual sustained GPU measurements, rejecting partial success."""
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
GIB = 1024**3


def summarize(report):
    rows = report['chunks']
    ok = [r for r in rows if r['ok']]
    if not ok:
        return {'passed': False, 'error_type': report.get('error_type'), 'chunks': len(rows)}
    expected_offsets = []
    offset = 0
    while offset < report['duration_seconds']:
        expected_offsets.append(offset)
        if offset+28 >= report['duration_seconds']:
            break
        offset += 24
    coverage = [r['offset'] for r in rows] == expected_offsets
    worker = sum(r['seconds'] for r in rows)
    cpu = sum(r['cpu_seconds'] for r in rows)
    samples = [r['after']['samples'] for r in rows]
    count = sum(r['gpu_samples'] for r in samples)
    quarter = max(1, len(ok)//4)
    late = ok[len(ok)//2:]
    xs = [r['offset']/3600 for r in late]
    ys = [r['after']['process']['VmRSS_bytes']/GIB for r in late]
    xmean, ymean = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x-xmean)**2 for x in xs)
    slope = sum((x-xmean)*(y-ymean) for x,y in zip(xs,ys))/denominator if denominator else None
    cgroup_keys = sorted({key for r in rows for key in r['after']['cgroup']})
    return {
        'passed': bool(report['passed'] and coverage and report.get('stopped') and all(r['valid_times'] for r in rows)),
        'account': report['account'], 'gpu_names': sorted({r['gpu_name'] for r in ok}),
        'chunks': len(rows), 'expected_chunks': len(expected_offsets), 'complete_window_coverage': coverage,
        'errors': len(rows)-len(ok), 'alignment_recoveries': sum(r.get('alignment_recoveries',0) for r in rows),
        'wall_seconds': report.get('wall_seconds'), 'worker_seconds': worker,
        'rpc_seconds': sum(r['rpc_seconds'] for r in rows), 'first_rpc_seconds': rows[0]['rpc_seconds'],
        'model_load_seconds': ok[0]['model_load_seconds'], 'cpu_seconds': cpu,
        'average_process_cpu_cores_during_calls': cpu/worker,
        'max_chunk_cpu_cores': max(r['cpu_seconds']/r['seconds'] for r in rows),
        'wall_real_time_factor': report.get('wall_seconds',report['elapsed_seconds'])/report['duration_seconds'],
        'worker_real_time_factor': worker/report['duration_seconds'],
        'gpu_total_GiB': ok[0]['gpu_total_bytes']/GIB,
        'peak_allocated_GiB': max(r['peak_allocated_bytes'] for r in ok)/GIB,
        'peak_reserved_GiB': max(r['peak_reserved_bytes'] for r in ok)/GIB,
        'sampled_device_used_peak_GiB': max(r['gpu_used_peak_bytes'] for r in samples)/GIB,
        'process_lifetime_peak_RSS_GiB': max(r['peak_rss_bytes'] for r in ok)/GIB,
        'sampled_process_peak_RSS_GiB': max(r['rss_peak_bytes'] for r in samples)/GIB,
        'first_quarter_median_RSS_GiB': statistics.median(r['after']['process']['VmRSS_bytes']/GIB for r in ok[:quarter]),
        'last_quarter_median_RSS_GiB': statistics.median(r['after']['process']['VmRSS_bytes']/GIB for r in ok[-quarter:]),
        'last_RSS_GiB': ok[-1]['after']['process']['VmRSS_bytes']/GIB,
        'second_half_RSS_slope_GiB_per_audio_hour': slope,
        'first_quarter_median_reserved_GiB': statistics.median(r['peak_reserved_bytes']/GIB for r in ok[:quarter]),
        'last_quarter_median_reserved_GiB': statistics.median(r['peak_reserved_bytes']/GIB for r in ok[-quarter:]),
        'gpu_utilization_samples': count,
        'sampled_gpu_utilization_mean_percent': sum((r.get('gpu_utilization_mean') or 0)*r['gpu_samples'] for r in samples)/count if count else None,
        'sampled_gpu_utilization_max_percent': max(r['gpu_utilization_max'] for r in samples),
        'cgroup_fields_available': cgroup_keys,
        'stage_seconds': {key: sum(r['stages'].get(key,0) for r in ok)
                          for key in sorted({key for r in ok for key in r['stages']})},
        'container_count': len({r['container_id'] for r in rows}),
        'successful_container_calls_sequential': [r['container_call'] for r in ok] == list(range(1,len(ok)+1)),
        'words': report.get('words'), 'cues': report.get('cues'), 'last_cue_end': report.get('last_cue_end'),
        'output_sha256': report.get('output_sha256'), 'shutdown': report.get('shutdown')}


def main():
    folder = ROOT/'research/benchmarks'
    reports = [json.loads((folder/f'qwen-long-{gpu}.json').read_text()) for gpu in ['T4','A10']]
    assert reports[0]['account'] != reports[1]['account']
    assert reports[0]['audio_sha256'] == reports[1]['audio_sha256']
    assert reports[0]['production_source_sha256'] == reports[1]['production_source_sha256']
    result = {'video': reports[0]['video'], 'duration_seconds': reports[0]['duration_seconds'],
              'audio_sha256': reports[0]['audio_sha256'], 'separate_accounts': True,
              'results': {r['gpu_requested']:summarize(r) for r in reports}, 'production_changed': False}
    result['comparison_complete'] = all(r['passed'] for r in result['results'].values())
    if result['comparison_complete']:
        t4,a10 = result['results']['T4'], result['results']['A10']
        result['T4_to_A10_wall_speedup'] = t4['wall_seconds']/a10['wall_seconds']
        result['T4_to_A10_worker_speedup'] = t4['worker_seconds']/a10['worker_seconds']
        a,b = [json.loads((ROOT/'.private/asr-long-video'/f'{gpu}-retained-words.json').read_text(encoding='utf-8')) for gpu in ['T4','A10']]
        identical_text = [w['text'] for w in a] == [w['text'] for w in b]
        result['word_text_sequence_equal'] = identical_text
        result['word_and_timestamp_hash_equal'] = t4['output_sha256'] == a10['output_sha256']
        # GPU floating-point differences may affect timing without changing words.
        left = [json.loads(line) for line in (ROOT/'.private/asr-long-video/T4-words.jsonl').read_text(encoding='utf-8').splitlines()]
        right = [json.loads(line) for line in (ROOT/'.private/asr-long-video/A10-words.jsonl').read_text(encoding='utf-8').splitlines()]
        assert len(left) == t4['chunks'] and len(right) == a10['chunks']
        differences = []
        for x,y in zip(left,right):
            assert x['offset'] == y['offset']
            if x['words'] == y['words']:
                continue
            same = [w['text'] for w in x['words']] == [w['text'] for w in y['words']]
            differences.append({'index':x['index'], 'offset':x['offset'], 'text_equal':same,
                                'word_counts':[len(x['words']),len(y['words'])],
                                'max_timestamp_delta_seconds':max((abs(a[k]-b[k]) for a,b in zip(x['words'],y['words'])
                                                                   for k in ['start','end']),default=0) if same else None})
        result['differing_chunks'] = differences
        if identical_text:
            deltas = [abs(x[k]-y[k]) for x,y in zip(a,b) for k in ['start','end']]
            result['timestamp_delta_max_seconds'] = max(deltas)
            result['timestamp_delta_mean_seconds'] = statistics.mean(deltas)
    (folder/'qwen-long-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
