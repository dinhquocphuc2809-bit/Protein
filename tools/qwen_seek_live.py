"""Signed production forward/back seek and translation-cache acceptance."""
import hashlib
import json
from pathlib import Path

from smoke_backend import Client

ROOT=Path(__file__).resolve().parents[1]


def main():
    client=Client()
    source=json.loads((ROOT/'research/qwen-optimized-first-live.json').read_text())['checks'][0]['job_id']
    report={'video_job_id':source,'checks':[],'passed':False}
    try:
        video=client.request('GET','/v1/jobs/'+source)['result']
        assert video['quality_version']==2 and video['terminology']['version']==2
        seen={}
        for position in [300,0,540,300,540]:
            result,seconds=client.job('/v1/windows',{'video_job_id':source,'position':position,'count':1},timeout=180)
            value=result['result'];cue=value['cues'][0]
            original=video['cues'][cue['id']]
            assert (cue['id'],cue['start'],cue['end'],cue['text']) == (original['id'],original['start'],original['end'],original['text'])
            assert value['translation_id']==video['translation_id'] and cue['translated']
            fingerprint=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
            if position in seen:
                assert seen[position]==fingerprint
            seen[position]=fingerprint
            row={'position':position,'job_id':result['id'],'seconds':seconds,'cue_id':cue['id'],
                 'timestamps_preserved':True,'response_sha256':fingerprint}
            report['checks'].append(row);print(json.dumps(row),flush=True)
        report['passed']=True
    finally:
        client.http.close()
        (ROOT/'research/qwen-optimized-seek-live.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
