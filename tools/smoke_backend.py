"""Real VPS acceptance requests; bounded inputs and reports without credentials."""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self):
        self.origin = json.loads((ROOT / '.private/public-endpoint.json').read_text())['url']
        self.http = httpx.Client(timeout=30)
        code = json.loads((ROOT / '.private/owner-ticket.json').read_text())['code']
        response = self.http.post(self.origin + '/v1/session', json={'code': code})
        response.raise_for_status()
        self.session = response.json()
        self.offset = self.session['server_time'] - time.time()

    def request(self, method, path, data=None, idem=None):
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode() if data is not None else b''
        timestamp, nonce = str(int(time.time()+self.offset)), secrets.token_hex(16)
        message = '\n'.join([method, path, hashlib.sha256(body).hexdigest(), timestamp, nonce])
        signature = hmac.new(bytes.fromhex(self.session['request_key']), message.encode(), 'sha256').hexdigest()
        headers = {'Authorization': 'Bearer ' + self.session['token'], 'X-Auvirel-Time': timestamp, 'X-Auvirel-Nonce': nonce,
                   'X-Auvirel-Signature': signature, 'Content-Type': 'application/json'}
        if idem:
            headers['Idempotency-Key'] = idem
        response = self.http.request(method, self.origin+path, headers=headers, content=body)
        response.raise_for_status()
        return response.json()

    def job(self, path, payload, timeout=360):
        started = time.monotonic()
        submitted = self.request('POST', path, payload, secrets.token_hex(16))
        while time.monotonic()-started < timeout:
            result = self.request('GET', '/v1/jobs/' + submitted['id'])
            if result['state'] == 'done':
                return result, time.monotonic()-started
            if result['state'] in {'failed', 'cancelled'}:
                raise RuntimeError(result.get('error') or result['state'])
            time.sleep(1.5)
        self.request('DELETE', '/v1/jobs/' + submitted['id'])
        raise TimeoutError('Job timed out')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--flow', choices=['translation', 'youtube', 'apify'], default='translation')
    args = parser.parse_args()
    client = Client()
    report = {'flow': args.flow, 'checks': []}
    try:
        if args.flow == 'translation':
            cues = [{'id': 0, 'start': 0, 'end': 4, 'text': 'A cache stores results so the same work does not need to run twice.'},
                    {'id': 1, 'start': 4, 'end': 8, 'text': 'Changing the voice should reuse the translated subtitles.'}]
            payload = {'url': 'https://example.org/auvirel-acceptance', 'title': 'Caching explained', 'source_language': 'en', 'target_language': 'vi', 'cues': cues}
            for model in ['basic', 'advanced', 'deepseek']:
                result, elapsed = client.job('/v1/jobs', {**payload, 'model': model})
                output = result['result']['cues']
                assert [(c['id'], c['start'], c['end']) for c in output] == [(c['id'], c['start'], c['end']) for c in cues]
                assert all(c['translated'] for c in output)
                report['checks'].append({'model': model, 'elapsed': elapsed, 'timestamps_preserved': True, 'result': output})
                if model == 'basic':
                    video_id = result['id']
                    cached, cached_elapsed = client.job('/v1/jobs', {**payload, 'model': model})
                    assert cached['result']['translation_id'] == result['result']['translation_id']
                    report['cache_repeat_seconds'] = cached_elapsed
            for kind in ['summary', 'chat']:
                study = {'video_job_id': video_id, 'model': 'basic'}
                if kind == 'chat':
                    study['question'] = 'Why should changing the voice not call translation again?'
                result, elapsed = client.job('/v1/' + kind, study)
                report['checks'].append({'kind': kind, 'elapsed': elapsed, 'result': result['result']})
            srt = '1\n00:00:01,000 --> 00:00:03,500\nAlready translated subtitle.\n'
            result, elapsed = client.job('/v1/jobs', {'url': 'https://example.org/imported-srt', 'srt': srt, 'already_translated': True})
            assert result['result']['cues'][0]['translated'] == 'Already translated subtitle.'
            assert result['result']['cues'][0]['start'] == 1
            report['checks'].append({'kind': 'translated_srt', 'elapsed': elapsed, 'passed': True})
        else:
            url = 'https://www.youtube.com/watch?v=jNQXAC9IVRw' if args.flow == 'youtube' else 'https://www.tiktok.com/@scout2015/video/6718335390845095173'
            result, elapsed = client.job('/v1/jobs', {'url': url, 'source_language': 'en', 'target_language': 'vi', 'asr': 'fast'}, timeout=420)
            report['checks'].append({'elapsed': elapsed, 'cues': result['result']['cues']})
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, error=str(error) if isinstance(error, (RuntimeError, TimeoutError)) else type(error).__name__)
    finally:
        (ROOT / 'research' / ('live-' + args.flow + '.json')).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(args.flow, 'PASS' if report['passed'] else 'FAIL: '+report['error'])
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
