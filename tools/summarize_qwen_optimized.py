"""Audit completed optimized GPU outputs using the final backend merger/formatter."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.asr_merge import WindowMerger
from backend.asr_text import lexical
from backend.subtitles import words_to_cues, speech_units


def main():
    private = ROOT/'.private/qwen-improvement'
    full = json.loads((ROOT/'research/benchmarks/qwen-optimized-full.json').read_text())
    restore = json.loads((ROOT/'research/benchmarks/qwen-optimized-restore.json').read_text())
    control = json.loads((ROOT/'research/benchmarks/qwen-long-T4.json').read_text())
    assert full['passed'] and full['zero_containers'] and full['windows'] == 375
    assert restore['passed'] and restore['zero_containers']
    merger, indices, segment_count, punctuated = WindowMerger(), [], 0, 0
    for line in (private/'full-results.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row['category'] != 'calls':
            continue
        for index, result in zip(row['indices'], row['results']):
            indices.append(index)
            merger.append(result['words'], index*24, result['duration'])
            segment_count += len(result['segments'])
            punctuated += sum(bool(re.search(r'[,.;!?\u3002\uff0c\uff01\uff1f]', s['text'])) for s in result['segments'])
    assert indices == list(range(375))
    cues = words_to_cues(merger.words, ensure_punctuation=True)
    units = speech_units(cues)
    (private/'full-words-final.json').write_text(json.dumps(merger.words,ensure_ascii=False),encoding='utf-8')
    (private/'full-cues-final.json').write_text(json.dumps([c.model_dump() for c in cues],ensure_ascii=False),encoding='utf-8')
    checks = []
    for time, expected, rejected in [(1154,'\u6210\u4e3a\u5f3a\u8005','\u4e3a\u4e3a'),
                                    (2594,'\u96be\u5f97\u4e00\u89c1','\u4e00\u4e00'),
                                    (4370,'\u5f88\u4e0d\u6ee1','\u4e0d\u4e0d'),
                                    (8210,'\u8fbd\u9614','\u8fbd\u8fbd'),
                                    (1922,'\u5988\u5988',None)]:
        text = lexical(''.join(w['text'] for w in merger.words if time-4<w['start']<time+4))
        passed = expected in text and (rejected is None or rejected not in text)
        checks.append({'seconds':time,'passed':passed,'expected':expected})
    cycles = restore['cycles']
    restored = [r for r in cycles[1:] if r['initialization_id'] == cycles[0]['initialization_id'] and r['call'] == 1]
    report = {
        'video':'YGi-aPUsZrQ', 'audio_seconds':8996.72, 'windows':len(indices), 'rpcs':len(full['calls']),
        'baseline_wall_seconds':control['wall_seconds'], 'optimized_warm_wall_seconds':full['wall_seconds'],
        'baseline_worker_seconds':sum(r['seconds'] for r in control['chunks']),
        'optimized_worker_seconds':sum(r['seconds'] for r in full['calls']),
        'wall_comparison_caveat':'Baseline includes its initial cold request; optimized throughput follows explicit snapshot cycles. Download/normalization/translation excluded in both.',
        'peak_rss_gib':max(r['after']['samples']['rss_peak_bytes'] for r in full['calls'])/1024**3,
        'peak_reserved_vram_gib':max(r['peak_reserved_bytes'] for r in full['calls'])/1024**3,
        'cpu_seconds':sum(r['cpu_seconds'] for r in full['calls']),
        'boot_count_full':len({r['boot_id'] for r in full['calls']}),
        'alignment_recoveries':sum(r['alignment_recoveries'] for r in full['calls']),
        'seam_modes':{mode:sum(s['mode']==mode for s in merger.seams) for mode in sorted({s['mode'] for s in merger.seams})},
        'words':len(merger.words), 'cues':len(cues), 'speech_units':len(units),
        'recognized_segments':segment_count, 'recognized_segments_with_punctuation':punctuated,
        'cues_missing_end_punctuation':sum(not bool(re.search(r'[,.;:!?\u3002\uff0c\uff01\uff1f]$',c.text)) for c in cues),
        'cjk_space_cues':sum(bool(re.search(r'[\u4e00-\u9fff] [\u4e00-\u9fff]',c.text)) for c in cues),
        'regressions':checks, 'snapshot_initial_rpc_seconds':cycles[0]['rpc_seconds'],
        'snapshot_restored_rpc_seconds':[r['rpc_seconds'] for r in restored],
        'snapshot_distinct_boots':len({r['boot_id'] for r in cycles}),
        'snapshot_restore_logs':sum('Restoring Function' in l for l in restore.get('snapshot_lines',[])),
        'backend_merger_sha256':hashlib.sha256((ROOT/'backend/asr_merge.py').read_bytes()).hexdigest(),
        'semantic_accuracy_percentage':None,
    }
    report['passed'] = all(c['passed'] for c in checks) and not report['cues_missing_end_punctuation'] and not report['cjk_space_cues'] and len(restored)>=2
    (ROOT/'research/benchmarks/qwen-optimized-summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
