"""Live signed API ASR test, with separate execution/cache evidence and no cue text."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import time
from urllib.parse import urlsplit, parse_qs
import re

from smoke_backend import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='qwen-incident-live.json')
    parser.add_argument('--url', default='https://www.youtube.com/watch?v=f6YA_OvKbhY')
    parser.add_argument('--timeout', type=int, default=900)
    args = parser.parse_args()
    if Path(args.report).name != args.report or not args.report.endswith('.json'):
        parser.error('Report must be a JSON basename')
    url = urlsplit(args.url)
    video_id = parse_qs(url.query).get('v', [''])[0]
    if (url.scheme != 'https' or url.netloc != 'www.youtube.com' or url.path != '/watch'
            or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id)):
        parser.error('Expected a YouTube HTTPS watch URL')
    if not 60 <= args.timeout <= 1800:
        parser.error('Timeout must be between 60 and 1800 seconds')
    client = Client()
    payload = {'url': 'https://www.youtube.com/watch?v='+video_id, 'asr': 'quality',
               'source_language': 'auto', 'target_language': 'vi', 'model': 'basic',
               'progressive': True, 'position': 0}
    report = {'at': datetime.now(timezone.utc).isoformat(), 'request': payload, 'checks': []}
    destination = ROOT/'research'/args.report
    try:
        for label in ['initial', 'repeat']:
            started = time.monotonic()
            submitted = client.request('POST', '/v1/jobs', payload, secrets.token_hex(16))
            row = {'name': label, 'job_id': submitted['id'], 'stages': []}
            report['checks'].append(row)
            try:
                while time.monotonic()-started < args.timeout:
                    result = client.request('GET', '/v1/jobs/'+submitted['id'])
                    if not row['stages'] or row['stages'][-1]['stage'] != result['stage']:
                        row['stages'].append({'stage': result['stage'], 'seconds': round(time.monotonic()-started, 3)})
                        print(json.dumps({'name': label, **row['stages'][-1]}), flush=True)
                    if result['state'] in ['done', 'failed', 'cancelled']:
                        row.update(state=result['state'], seconds=round(time.monotonic()-started, 3))
                        if result['state'] == 'done':
                            data = result['result']; cues = data['cues']
                            row.update(cues=len(cues), first=cues[0]['start'], last=cues[-1]['end'],
                                source_hash=data['source_hash'], translation_id=data['translation_id'],
                                translated=sum(bool(c.get('translated')) for c in cues),
                                valid_times=all(0 <= c['start'] < c['end'] <= 14400 for c in cues)
                                    and all(a['end'] <= b['start'] for a, b in zip(cues, cues[1:])),
                                unique_ids=len({c['id'] for c in cues}) == len(cues),
                                nonempty_text=all(c['text'].strip() for c in cues),
                                payload_sha256=hashlib.sha256(json.dumps(cues, sort_keys=True).encode()).hexdigest())
                        else:
                            row['error'] = result.get('error')
                        break
                    destination.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
                    time.sleep(2)
                else:
                    row.update(state='timeout')
            finally:
                if row.get('state') not in ['done', 'failed', 'cancelled']:
                    client.request('DELETE', '/v1/jobs/'+submitted['id'])
                destination.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            if row['state'] != 'done' or not all(row[k] for k in ['valid_times', 'unique_ids', 'nonempty_text', 'translated']):
                return 1
        assert report['checks'][0]['source_hash'] == report['checks'][1]['source_hash']
        assert report['checks'][0]['payload_sha256'] == report['checks'][1]['payload_sha256']
        print('Live quality request and repeat passed; verify provider events separately.', flush=True)
        return 0
    finally:
        client.http.close()


if __name__ == '__main__':
    raise SystemExit(main())
