"""Sample actual production progressive translations; retain text only privately."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from smoke_backend import Client

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.subtitles import words_to_cues


def main():
    folder = ROOT/'.private/translation-audit'
    source = json.loads((folder/'source.json').read_text(encoding='utf-8'))
    words = json.loads((ROOT/'.private/asr-long-video/T4-retained-words.json').read_text(encoding='utf-8'))
    payload = {'url':'https://www.youtube.com/watch?v=YGi-aPUsZrQ',
               'title':source['metadata']['title'], 'source_language':'zh', 'target_language':'vi',
               'model':'basic', 'progressive':True, 'position':0,
               'cues':[c.model_dump() for c in words_to_cues(words)]}
    report_path = ROOT/'research/translation-long-video-audit.json'
    private_path = folder/'basic.json'
    report = {'at':datetime.now(timezone.utc).isoformat(), 'video':'YGi-aPUsZrQ',
              'scope':'Stratified sample, real VPS progressive translation, not full-video semantic acceptance',
              'model_selection':'basic', 'windows':[], 'passed_transport_checks':False}
    retained = {'video':payload['url'], 'title':payload['title'], 'translations':{}, 'windows':[]}
    def save():
        private_path.write_text(json.dumps(retained,ensure_ascii=False,indent=2),encoding='utf-8')
        report_path.write_text(json.dumps(report,indent=2)+'\n')
    client = Client()
    try:
        if private_path.exists():
            retained = json.loads(private_path.read_text(encoding='utf-8'))
            report = json.loads(report_path.read_text())
        else:
            result, seconds = client.job('/v1/jobs',payload,timeout=300)
            retained['video_job_id'] = result['id']
            retained['units'] = result['result']['cues']
            report.update(video_job_id=result['id'], total_speech_units=len(retained['units']), preparation_seconds=seconds)
            for cue in retained['units']:
                if cue.get('translated'):
                    retained['translations'][str(cue['id'])] = cue
            save()
        targets = sorted(set([*range(0,8997,450),3960,4512,6864,8900]))
        done = {x['position'] for x in report['windows']}
        for position in targets:
            if position in done:
                continue
            result, seconds = client.job('/v1/windows',{'video_job_id':retained['video_job_id'],
                'position':position, 'count':3},timeout=300)
            cues = result['result']['cues']
            for cue in cues:
                original = retained['units'][cue['id']]
                assert (cue['id'],cue['start'],cue['end'],cue['text']) == (original['id'],original['start'],original['end'],original['text'])
                assert isinstance(cue['translated'],str) and cue['translated'].strip()
                retained['translations'][str(cue['id'])] = cue
            row = {'position':position,'job_id':result['id'],'ids':[c['id'] for c in cues],
                   'seconds':round(seconds,3),'timestamps_preserved':True}
            retained['windows'].append(row);report['windows'].append(row)
            save()
            print(json.dumps({'position':position,'sampled_cues':len(retained['translations']),'seconds':round(seconds,2)}),flush=True)
        rows = list(retained['translations'].values())
        report.update(sampled_cues=len(rows),passed_transport_checks=True,
                      missing_final_punctuation=[c['id'] for c in rows if not re.search(r'[,\.!?\u3002\uff01\uff1f\uff0c]["\u201d\u2019\x27\)\]]*$',c['translated'])],
                      output_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest())
        save()
    except Exception as error:
        report['error_type'] = type(error).__name__
        save()
        raise
    finally:
        client.http.close()


if __name__ == '__main__':
    main()
