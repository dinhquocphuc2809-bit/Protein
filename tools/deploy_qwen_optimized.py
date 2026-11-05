"""Deploy the accepted T4 worker to the three backend accounts and smoke each."""
from datetime import datetime, timezone
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
    private=ROOT/'.private/qwen-improvement'
    report={'at':datetime.now(timezone.utc).isoformat(), 'accounts':[], 'client_account_touched':False,
            'snapshot':True,'gpu':'T4','cpu':2,'ram_mib':16384,'inference_batch':4,'max_windows_per_rpc':4,
            'source_sha256':hashlib.sha256((ROOT/'gpu/asr.py').read_bytes()).hexdigest()}
    path=ROOT/'research/qwen-optimized-rollout.json'
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
        result=subprocess.run([sys.executable,'-c',code],env=env,cwd=ROOT,capture_output=True,encoding='utf-8',timeout=360)
        (private/f'production-account{account}-smoke.log').write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:
            raise RuntimeError('Backend worker smoke failed; inspect private log')
        row.update(json.loads(result.stdout.strip().splitlines()[-1]))
        path.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(row),flush=True)
    report['passed']=all(r.get('smoke_passed') for r in report['accounts'])
    path.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
