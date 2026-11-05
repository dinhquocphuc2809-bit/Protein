"""Compare measured full-video runs and explicitly qualified Modal costs."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import difflib
import json
from pathlib import Path
import subprocess
import sys

from operate_modal import environment
from summarize_long_asr import summarize

ROOT = Path(__file__).resolve().parents[1]
GPUS = ['T4', 'A10', 'A100-40GB', 'A100-80GB']
RATE_KEYS = {'T4': 'gpu_hour_cost_t4', 'A10': 'gpu_hour_cost_a10g',
             'A100-40GB': 'gpu_hour_cost_a100_40gb', 'A100-80GB': 'gpu_hour_cost_a100_80gb'}
RESOURCE_NAMES = {'T4': 'T4', 'A10': 'A10G', 'A100-40GB': 'A100-40GB', 'A100-80GB': 'A100-80GB'}


def main():
    folder = ROOT/'research/benchmarks'
    reports = {gpu: json.loads((folder/f'qwen-long-{gpu}.json').read_text()) for gpu in GPUS}
    assert len({r['audio_sha256'] for r in reports.values()}) == 1
    assert len({r['production_source_sha256'] for r in reports.values()}) == 1
    assert reports['A100-40GB']['account'] != reports['A100-80GB']['account']
    rates = json.loads((folder/'qwen-a100-before.json').read_text())['rates_usd_per_hour']
    result = {'at': datetime.now(timezone.utc).isoformat(), 'video': 'YGi-aPUsZrQ',
              'duration_seconds': reports['T4']['duration_seconds'],
              'audio_sha256': reports['T4']['audio_sha256'], 'production_changed': False,
              'rates_usd_per_hour': rates, 'results': {g:summarize(r) for g,r in reports.items()}}
    if not all(r['passed'] for r in result['results'].values()):
        raise RuntimeError('Full successful coverage and stopped apps are required before final cost comparison')

    billing = {}
    start = min(datetime.fromisoformat(r['at']) for r in reports.values()).date().isoformat()
    # Include the current hour, but record that provider usage can still be delayed.
    end = (datetime.now(timezone.utc).date()+timedelta(days=1)).isoformat()
    for account in [1, 2]:
        command = [sys.executable, '-m', 'modal', 'billing', 'report', '--start', start,
                   '--end', end, '--resolution', 'h', '--show-resources', '--json']
        query = subprocess.run(command, env=environment(account), capture_output=True, timeout=60)
        query.check_returncode()
        billing[account] = json.loads(query.stdout)
        (ROOT/'.private/asr-long-video'/f'account{account}-a100-final-app-costs.json').write_bytes(query.stdout)

    baseline = json.loads((ROOT/'.private/asr-long-video/T4-retained-words.json').read_text(encoding='utf-8'))
    for gpu, report in reports.items():
        metrics = result['results'][gpu]
        observed = [r for r in billing[report['account']] if r['object_id'] == report['app_id']]
        resources = {}
        for row in observed:
            resources[row['resource']] = resources.get(row['resource'], Decimal(0))+Decimal(row['cost'])
        gpu_rate = float(rates[RATE_KEYS[gpu]])
        requested_rate = gpu_rate+report['cpu']*float(rates['cpu_hour_cost'])+report['ram_mib']/1024*float(rates['mem_gib_hour_cost'])
        wall = metrics['wall_seconds']
        reported_gpu_seconds = float(resources.get(RESOURCE_NAMES[gpu], 0))/gpu_rate*3600
        metrics['cost'] = {
            'gpu_usd_per_hour': gpu_rate, 'requested_gpu_cpu_ram_usd_per_hour': requested_rate,
            'wall_duration_estimate_usd': requested_rate*wall/3600,
            'estimate_method': 'Measured client wall seconds times GPU + requested 2 CPU + 16 GiB hourly rates. Approximation, not invoice; excludes build/storage and exact container lifecycle differences.',
            'reported_app_resources_usd': {k:float(v) for k,v in resources.items()},
            'reported_app_total_usd': float(sum(resources.values(),Decimal(0))),
            'reported_gpu_seconds': reported_gpu_seconds,
            'reported_gpu_seconds_over_client_wall': reported_gpu_seconds/wall,
            'reported_usage_may_be_delayed': True,
            'app_billing_rows': observed}
        output = json.loads((ROOT/'.private/asr-long-video'/f'{gpu}-retained-words.json').read_text(encoding='utf-8'))
        same_text = [w['text'] for w in output] == [w['text'] for w in baseline]
        metrics['retained_text_matches_T4'] = same_text
        if not same_text:
            matcher = difflib.SequenceMatcher(None, [w['text'] for w in baseline],
                                              [w['text'] for w in output], autojunk=False)
            metrics['text_differences_from_T4'] = [
                {'operation':op, 'T4_word_count':b-a, 'current_word_count':d-c,
                 'T4_start_seconds':baseline[a]['start'] if a < len(baseline) else None,
                 'current_start_seconds':output[c]['start'] if c < len(output) else None}
                for op,a,b,c,d in matcher.get_opcodes() if op != 'equal']
            metrics['text_difference_note'] = 'Comparison to another ASR output, not ground truth or a word-error-rate score.'
        if same_text:
            metrics['max_timestamp_difference_from_T4_seconds'] = max(abs(a[k]-b[k]) for a,b in zip(output,baseline) for k in ['start','end'])
        metrics['wall_speedup_vs_T4'] = result['results']['T4']['wall_seconds']/wall
        metrics['worker_speedup_vs_T4'] = result['results']['T4']['worker_seconds']/metrics['worker_seconds']

    cheapest = min(GPUS,key=lambda g:result['results'][g]['cost']['wall_duration_estimate_usd'])
    fastest = min(GPUS,key=lambda g:result['results'][g]['wall_seconds'])
    result.update(cheapest_by_consistent_wall_estimate=cheapest, fastest_observed_wall=fastest,
                  comparison_complete=True,
                  limitations=['One full pass per GPU; runs on different hosts and at different times.',
                               'A100 40GB was SXM4, 80GB was PCIe: not a VRAM-capacity-only experiment.',
                               'Reported app costs can lag; consistent estimates are not exact charges.',
                               'Credit-funded resource consumption is not zero cost.'])
    (folder/'qwen-a100-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    for gpu,r in result['results'].items():
        print(json.dumps({'gpu':gpu,'wall_seconds':r['wall_seconds'],'worker_seconds':r['worker_seconds'],
                          'estimated_usd':r['cost']['wall_duration_estimate_usd'],
                          'reported_app_usd':r['cost']['reported_app_total_usd'],
                          'billing_time_ratio':r['cost']['reported_gpu_seconds_over_client_wall'],
                          'same_text':r['retained_text_matches_T4']}))


if __name__ == '__main__':
    main()
