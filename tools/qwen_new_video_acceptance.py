"""Read-only source audit and signed seek acceptance for kp_IQITWg74."""
import base64
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from smoke_backend import Client
from vps import execute

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.security import canonical, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--numeric-fixed', action='store_true')
    args = parser.parse_args()
    suffix = '-final' if args.numeric_fixed else ''
    private = ROOT/'.private/qwen-kpIQITWg74'
    live_name = 'qwen-kpIQITWg74-final-live.json' if args.numeric_fixed else 'qwen-kpIQITWg74-retry-live.json'
    live = json.loads((ROOT/'research'/live_name).read_text())
    identity = live['checks'][0]['job_id']
    client = Client()
    report = {'video': 'kp_IQITWg74', 'video_job_id': identity, 'checks': [], 'passed': False}
    try:
        row = client.request('GET', '/v1/jobs/'+identity)
        if row['state'] != 'done':
            raise RuntimeError('Initial video job has not completed')
        video = row['result']
        (private/f'production-result{suffix}.json').write_text(json.dumps(video,ensure_ascii=False,indent=2),encoding='utf-8')
        key = 'source:'+digest(canonical({'url':live['request']['url'],'source':'auto','asr':'quality','version':3 if args.numeric_fixed else 2}).encode())
        code = 'key='+repr(key)+'\n'+'''import sqlite3,json
c=sqlite3.connect('file:/var/lib/auvirel/auvirel.sqlite3?mode=ro',uri=True)
r=c.execute('SELECT value FROM cache WHERE key=?',(key,)).fetchone()
if not r:raise RuntimeError('Source cache missing')
print(r[0])
'''
        response = execute('printf %s '+base64.b64encode(code.encode()).decode()+' | base64 -d | sudo python3 -',capture=True)
        if response.returncode:
            raise RuntimeError('Read-only source retrieval failed')
        source = json.loads(response.stdout)
        (private/f'source-cues{suffix}.json').write_text(json.dumps(source,ensure_ascii=False,indent=2),encoding='utf-8')
        duration = json.loads((ROOT/'research/qwen-kpIQITWg74-input.json').read_text())['duration_seconds']
        report.update(source_cues=len(source), speech_units=len(video['cues']), duration_seconds=duration,
            terminology_terms=len(video['terminology']['terms']), source_repairs=len(video['source_repairs']),
            source_time_bounds_valid=all(0<=c['start']<c['end']<=duration+.001 for c in source),
            source_ordered=all(a['start']<=b['start'] for a,b in zip(source,source[1:])),
            source_missing_final_punctuation=sum(not bool(re.search(r'[,.;:!?\u3002\uff0c\uff01\uff1f]$',c['text'])) for c in source),
            cjk_space_cues=sum(bool(re.search(r'[\u4e00-\u9fff] [\u4e00-\u9fff]',c['text'])) for c in source),
            source_sha256=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest())
        seen = {}
        for position in ([1200,33,2400,1200,2400,33] if args.numeric_fixed else [1200,24,2400,1200,2400]):
            result, seconds = client.job('/v1/windows', {'video_job_id':identity,'position':position,'count':3 if args.numeric_fixed else 1},timeout=180)
            value = result['result']
            for cue in value['cues']:
                original = video['cues'][cue['id']]
                assert all(cue[k]==original[k] for k in ('id','start','end','text'))
                assert cue['translated']
            assert value['translation_id']==video['translation_id']
            fingerprint=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            if position in seen:
                assert seen[position]==fingerprint
            seen[position]=fingerprint
            (private/f'seek-{position}{suffix}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            check={'position':position,'job_id':result['id'],'seconds':seconds,'response_sha256':fingerprint,'times_preserved':True}
            report['checks'].append(check);print(json.dumps(check),flush=True)
        report['passed']=report['source_time_bounds_valid'] and report['source_ordered'] and not report['source_missing_final_punctuation'] and not report['cjk_space_cues']
        if args.numeric_fixed:
            numeric_cues = [c for c in source if 32 <= c['start'] < 36]
            report['decimal_preserved'] = len(numeric_cues) == 1 and '1.93' in numeric_cues[0]['text']
            report['passed'] = report['passed'] and report['decimal_preserved']
        report['scope'] = 'API, structure, cache and seek checks; not full semantic accuracy'
    finally:
        client.http.close()
        (ROOT/f'research/qwen-kpIQITWg74-acceptance{suffix}.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
