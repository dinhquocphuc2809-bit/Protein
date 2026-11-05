"""Deploy the accepted T4 worker to the three backend accounts and smoke each."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from operate_modal import environment

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--report',default='qwen-optimized-rollout.json')
    parser.add_argument('--numeric-smoke',action='store_true')
    args=parser.parse_args()
    if Path(args.report).name!=args.report or not args.report.endswith('.json'):
        parser.error('Report must be a JSON basename')
    private=ROOT/'.private/qwen-improvement'
    report={'at':datetime.now(timezone.utc).isoformat(), 'accounts':[], 'client_account_touched':False,
            'snapshot':True,'gpu':'T4','cpu':2,'ram_mib':16384,'inference_batch':4,'max_windows_per_rpc':4,
            'source_sha256':hashlib.sha256((ROOT/'gpu/asr.py').read_bytes()).hexdigest(),
            'alignment_sha256':hashlib.sha256((ROOT/'gpu/alignment.py').read_bytes()).hexdigest(),
            'asr_text_sha256':hashlib.sha256((ROOT/'backend/asr_text.py').read_bytes()).hexdigest()}
    path=ROOT/'research'/args.report
    for account in (1,2,3):
        env=environment(account)
        env.update(VOCALM_ASR_SNAPSHOT='1',VOCALM_ASR_BATCH='4',AUVIREL_GPU='T4',PYTHONPATH=str(ROOT))
        result=subprocess.run([sys.executable,'-m','modal','deploy','gpu/asr.py'],env=env,cwd=ROOT,
                              capture_output=True,encoding='utf-8',timeout=600)
        (private/f'production-account{account}-deploy.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        row={'account':account,'deployed':result.returncode==0}
        report['accounts'].append(row);path.write_text(json.dumps(report,indent=2)+'\n')
        if result.returncode:
            raise RuntimeError('Backend worker deployment failed; inspect private log')
        # Separate child process avoids the SDK's default-client account cache.
        code='''import modal,json,time
from pathlib import Path
audio=Path('.private/qwen-improvement/english.wav').read_bytes()
worker=modal.Cls.from_name('auvirel-asr','Recognizer')()
start=time.perf_counter();call=worker.transcribe_many.spawn([audio],'en')
try:
 result=call.get(timeout=300)
except BaseException:
 call.cancel(terminate_containers=True);raise
assert len(result)==1 and result[0]['model']=='Qwen/Qwen3-ASR-1.7B'
assert all(0<=w['start']<=w['end']<=result[0]['duration']+.001 for w in result[0]['words'])
assert 'elephant' in ' '.join(w['text'] for w in result[0]['words']).lower()
print(json.dumps({'smoke_passed':True,'rpc_seconds':time.perf_counter()-start,'words':len(result[0]['words'])}))
'''
        if args.numeric_smoke:
            code += '''import io,wave
with wave.open('.private/qwen-kpIQITWg74/audio.wav') as w:
 w.setpos(24*16000);frames=w.readframes(28*16000)
b=io.BytesIO()
with wave.open(b,'wb') as w:
 w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(frames)
start=time.perf_counter();call=worker.transcribe_many.spawn([b.getvalue()],'auto')
try:
 value=call.get(timeout=240)[0]
except BaseException:
 call.cancel(terminate_containers=True);raise
number=[w for w in value['words'] if w['text']=='1.93']
assert len(number)==1 and number[0]['start']==10.336 and number[0]['end']==11.056
assert all(0<=w['start']<=w['end']<=value['duration']+.001 for w in value['words'])
assert '1.93' in ''.join(s['text'] for s in value['segments'])
print(json.dumps({'numeric_smoke_passed':True,'numeric_seconds':time.perf_counter()-start}))
'''
        result=subprocess.run([sys.executable,'-c',code],env=env,cwd=ROOT,capture_output=True,encoding='utf-8',timeout=360)
        (private/f'production-account{account}-smoke.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Backend worker smoke failed; inspect private log')
        for line in result.stdout.strip().splitlines():
            if line.startswith('{'):
                row.update(json.loads(line))
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    report['passed']=all(r.get('smoke_passed') for r in report['accounts'])
    path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
