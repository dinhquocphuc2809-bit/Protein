"""Two real account-4 HTTP calls, separating transfer/polling from local DSP.

Uses the owner's existing progressive audio selection. No deployment or warm pool
changes; writes aggregate timing only to the public report, audio stays private.
"""
import base64
import argparse
import json
from pathlib import Path
import re
import secrets
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--registered', action='store_true')
    parser.add_argument('--repeats', type=int, choices=range(1,5), default=2)
    parser.add_argument('--report', choices=['baseline','optimized','snapshot-build','snapshot-restore','snapshot-cycles','final'])
    parser.add_argument('--idle-seconds', type=int, choices=[0,45,60], default=0)
    args = parser.parse_args()
    folder = ROOT / '.private/progressive-audio'
    cue = json.loads((folder/'selected.json').read_text(encoding='utf8'))[0]
    preset = next(p for p in json.loads((ROOT/'assets/imported/presets.json').read_text(encoding='utf8')) if p['id']=='vi-dang-khoa')
    reference = (ROOT/'assets/imported'/preset['path']).read_bytes()
    endpoint = re.search(r'https://[^\s]+\.modal\.run', (ROOT/'.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
    proxy = json.loads((ROOT/'.private/modal-4-proxy.json').read_bytes())
    headers = {k:proxy[k] for k in ['Modal-Key','Modal-Secret']}
    payload = {'text':cue['translated'],'reference':base64.b64encode(reference).decode(),
               'reference_text':preset['transcript'],'language':'vi','duration':None}
    report = {'scope':'Real HTTP calls with identical text/reference on existing client account 4',
              'characters':len(cue['translated']),'reference_bytes':len(reference),
              'cold_state':'Worker counters distinguish first input; infrastructure scheduling/restore time is not individually instrumented',
              'idle_seconds':args.idle_seconds,'runs':[]}
    with httpx.Client(timeout=30) as http:
        try:
            if args.registered:
                started=time.monotonic()
                registration=http.post(endpoint+'/v1/voices',headers=headers,json={k:payload[k] for k in ['reference','reference_text']})
                registration.raise_for_status()
                report['registration_seconds']=round(time.monotonic()-started,4)
                payload={k:v for k,v in payload.items() if k not in ['reference','reference_text']}
                payload['reference_id']=registration.json()['reference_id']
            report['synthesis_payload_bytes']=len(json.dumps(payload).encode())
            for repeat in range(args.repeats):
                if repeat and args.idle_seconds:time.sleep(args.idle_seconds)
                identity=secrets.token_hex(32);done=False;started=time.monotonic()
                try:
                    response=http.post(endpoint+'/v1/synthesize',headers={**headers,'Idempotency-Key':identity},json=payload)
                    recovered=False
                    if args.registered and response.status_code==404:
                        registration=http.post(endpoint+'/v1/voices',headers=headers,json={
                            'reference':base64.b64encode(reference).decode(),'reference_text':preset['transcript']})
                        registration.raise_for_status();payload['reference_id']=registration.json()['reference_id']
                        response=http.post(endpoint+'/v1/synthesize',headers={**headers,'Idempotency-Key':identity},json=payload)
                        recovered=True
                    response.raise_for_status();submission=time.monotonic()-started
                    server_submission=response.json().get('timings',{})
                    polls=[];sleeps=0
                    while time.monotonic()-started<180:
                        tick=time.monotonic()
                        response=http.get(endpoint+'/v1/results/'+identity,headers=headers,params={'wait':10} if args.registered else {})
                        response.raise_for_status();polls.append({'seconds':round(time.monotonic()-tick,4),'status':response.status_code})
                        if response.status_code==200:
                            result=response.json();done=True;break
                        time.sleep(.35);sleeps+=.35
                    if not done:raise TimeoutError('Voice probe timed out')
                    ready=time.monotonic()-started
                    ogg=folder/f'latency-{repeat}.ogg';raw=folder/f'latency-{repeat}.f32'
                    tick=time.monotonic();audio=base64.b64decode(result['audio'],validate=True);ogg.write_bytes(audio)
                    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(ogg),'-f','f32le','-ar','24000','-ac','1',str(raw)],check=True,timeout=30)
                    decode=time.monotonic()-tick
                    speed=max(.92,min(1.22,result['duration']/(cue['end']-cue['start'])))
                    js="""const fs=require('fs');require('./extension/lib/core.js');const {stretch}=require('./extension/lib/audio.js');
                        let b=fs.readFileSync(process.argv[1]);let a=new Float32Array(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength));
                        let t=performance.now();stretch(a,Number(process.argv[2]),24000).then(x=>console.log((performance.now()-t)/1000));"""
                    tick=time.monotonic()
                    output=subprocess.run(['node','-e',js,str(raw),str(speed)],cwd=ROOT,capture_output=True,text=True,check=True,timeout=30)
                    report['runs'].append({'repeat':repeat,'submission_seconds':round(submission,4),'polls':polls,
                        'reference_recovered':recovered,
                        'server_submission':server_submission,'worker':result.get('timings',{}),
                        'poll_sleep_seconds':round(sleeps,4),'audio_received_seconds':round(ready,4),
                        'audio_seconds':result['duration'],'audio_bytes':len(audio),'local_decode_seconds':round(decode,4),
                        'dsp_seconds':round(float(output.stdout),4),'node_process_seconds':round(time.monotonic()-tick,4),
                        'total_probe_seconds':round(time.monotonic()-started,4)})
                finally:
                    if not done:
                        try:http.delete(endpoint+'/v1/results/'+identity,headers=headers)
                        except httpx.HTTPError:pass
            report['completed']=True
        finally:
            name='tts-latency-optimized.json' if args.registered else 'tts-latency-breakdown.json'
            if args.report:name='tts-latency-'+args.report+'.json'
            (ROOT/'research'/name).write_text(json.dumps(report,indent=2),encoding='utf8')
            print(json.dumps(report))


if __name__=='__main__':
    main()
