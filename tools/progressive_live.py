"""Bounded production verification on the owner's retained transcript and selected voice."""
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import time
import wave

import httpx
import numpy as np

from smoke_backend import Client

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / '.private/progressive-audio'
    folder.mkdir(exist_ok=True)
    source = json.loads((ROOT / '.private/sentence-incident.json').read_text(encoding='utf8'))
    client = Client()
    report = {'scope': 'Real VPS/Gemini and client Modal OmniVoice on a small region of the owner video; not whole-video TTS', 'passed': False}
    try:
        payload = {k: source[k] for k in ['url', 'title', 'source_language', 'target_language']}
        payload.update(cues=[{k: c[k] for k in ['id', 'start', 'end', 'text']} for c in source['cues']], progressive=True, position=28.3, model='basic')
        job, elapsed = client.job('/v1/jobs', payload, timeout=180)
        plan = job['result']['cues']; ready = [c for c in plan if c['translated']]
        assert len(ready) == 1
        assert ' '.join(c['text'] for c in plan).split() == ' '.join(c['text'] for c in source['cues']).split()
        index = ready[0]['id']
        assert 'Good morning' in ready[0]['text'] and "We've officially" in ready[0]['text']
        report.update(source_cues=len(source['cues']), speech_units=len(plan), initial_translated_units=1,
                      initial_translation_seconds=round(elapsed, 3), all_source_words_preserved=True,
                      max_unit_seconds=round(max(c['end']-c['start'] for c in plan), 3))
        following, following_time = client.job('/v1/windows', {'video_job_id': job['id'], 'position': plan[index+1]['start'], 'count': 2}, timeout=180)
        selected = ready + following['result']['cues']
        seek, seek_time = client.job('/v1/windows', {'video_job_id': job['id'], 'position': 600, 'count': 1}, timeout=120)
        replay, replay_time = client.job('/v1/windows', {'video_job_id': job['id'], 'position': 28.3, 'count': 1}, timeout=30)
        assert replay['result']['cues'][0]['translated'] == ready[0]['translated']
        assert seek['result']['cues'][0]['end'] > 600
        report.update(following_translation_seconds=round(following_time,3),seek_translation_seconds=round(seek_time,3), replay_seconds=round(replay_time,3),
                      startup_job_id=job['id'], replay_job_id=replay['id'])
        (folder/'selected.json').write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding='utf8')
        endpoint = re.search(r'https://[^\s]+\.modal\.run', (ROOT/'.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
        proxy = json.loads((ROOT/'.private/modal-4-proxy.json').read_bytes())
        headers = {k: proxy[k] for k in ['Modal-Key', 'Modal-Secret']}
        presets = json.loads((ROOT/'assets/imported/presets.json').read_text(encoding='utf8'))
        preset = next(p for p in presets if p['id'] == 'vi-dang-khoa')
        reference = base64.b64encode((ROOT/'assets/imported'/preset['path']).read_bytes()).decode()
        fitted_clips, observations = [], []
        with httpx.Client(timeout=30) as http:
            for n, cue in enumerate(selected):
                started = time.monotonic(); identity = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
                response = http.post(endpoint+'/v1/synthesize', headers={**headers,'Idempotency-Key':identity}, json={
                    'text':cue['translated'],'reference':reference,'reference_text':preset['transcript'],'language':'vi','duration':None})
                response.raise_for_status(); done = False
                try:
                    while time.monotonic()-started<240:
                        response=http.get(endpoint+'/v1/results/'+identity,headers=headers);response.raise_for_status()
                        if response.status_code==200:
                            result=response.json();done=True;break
                        time.sleep(.5)
                finally:
                    if not done:http.delete(endpoint+'/v1/results/'+identity,headers=headers)
                if not done:raise TimeoutError('Voice sample did not complete')
                original=folder/f'unit-{n}.ogg';original.write_bytes(base64.b64decode(result['audio'],validate=True))
                raw=folder/f'unit-{n}.f32'; fitted=folder/f'unit-{n}-fitted.f32'
                subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(original),'-f','f32le','-ar','24000','-ac','1',str(raw)],check=True,timeout=30)
                samples=np.fromfile(raw,dtype='<f4');available=cue['end']-cue['start'];speed=max(.92,min(1.22,len(samples)/24000/available))
                js="""const fs=require('node:fs');require('./extension/lib/core.js');const {stretch}=require('./extension/lib/audio.js');
                    const data=fs.readFileSync(process.argv[1]);const samples=new Float32Array(data.buffer.slice(data.byteOffset,data.byteOffset+data.byteLength));
                    stretch(samples,Number(process.argv[3]),24000).then(out=>fs.writeFileSync(process.argv[2],Buffer.from(out.buffer,out.byteOffset,out.byteLength))).catch(e=>{console.error(e.message);process.exit(1)});"""
                subprocess.run(['node','-e',js,str(raw),str(fitted),str(speed)],cwd=ROOT,check=True,timeout=30)
                values=np.fromfile(fitted,dtype='<f4');assert np.isfinite(values).all() and values[0]==0 and values[-1]==0
                fitted_clips.append(values)
                observations.append({'unit':cue['id'],'characters':len(cue['translated']),'natural_seconds':round(len(samples)/24000,3),
                    'fitted_seconds':round(len(values)/24000,3),'slot_seconds':round(available,3),'speed':round(speed,3),
                    'roundtrip_seconds':round(time.monotonic()-started,3),'start_zero':True,'end_zero':True,'peak':round(float(np.max(np.abs(values))),5)})
        combined=np.concatenate(fitted_clips)
        with wave.open(str(folder/'sentence-comparison-new.wav'),'wb') as output:
            output.setparams((1,2,24000,0,'NONE','not compressed'));output.writeframes((np.clip(combined,-1,1)*32767).astype('<i2').tobytes())
        report.update(passed=True,voice='vi-dang-khoa',clips=observations,join_discontinuity=0,
                      listening_status='Waveform/timing verified; subjective listening approval not claimed')
    finally:
        client.http.close();(ROOT/'research/progressive-live.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))


if __name__=='__main__':
    main()
