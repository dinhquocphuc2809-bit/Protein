"""Run the exact failed four-window batch on an isolated T4 app."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import wave

from operate_modal import environment
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--label',choices=('before','after','numeric','numeric-fixed'),required=True)
    args=parser.parse_args()
    env=environment(1);env.update(VOCALM_ASR_SNAPSHOT='0',PYTHONPATH=str(ROOT))
    os.environ.update(env);sys.path.insert(0,str(ROOT))
    from gpu.asr_language_probe import app, Probe
    report={'label':args.label,'indices':[1] if args.label.startswith('numeric') else [76,77,78,79],'account':1,'production_changed':False}
    audio=[]
    for index in report['indices']:
        with wave.open(str(ROOT/'.private/qwen-kpIQITWg74/audio.wav')) as w:
            w.setpos(index*24*16000);frames=w.readframes(28*16000)
        b=io.BytesIO()
        with wave.open(b,'wb') as w:
            w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(frames)
        audio.append(b.getvalue())
    app_id=None
    def cli(*parts):
        return subprocess.run([sys.executable,'-m','modal',*parts],env=env,cwd=ROOT,capture_output=True,encoding='utf-8',timeout=50)
    try:
        with app.run():
            app_id=app.app_id;report['app_id']=app_id
            start=time.perf_counter();call=Probe().diagnose.spawn(audio)
            try:value=call.get(timeout=300)
            except BaseException:
                call.cancel(terminate_containers=True);raise
            report['seconds']=time.perf_counter()-start
            (ROOT/f'.private/qwen-kpIQITWg74/language-{args.label}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
            report.update({k:v for k,v in value.items() if k not in ('results','traceback')})
            report['detected'] = [{k:v for k,v in row.items() if k != 'text'} for row in value.get('detected', [])]
            if value.get('results'):
                report['words']=[len(r['words']) for r in value['results']]
                report['valid_times']=all(0<=w['start']<=w['end']<=r['duration']+.001 for r in value['results'] for w in r['words'])
                report['alignment_recoveries']=sum(r['alignment_recoveries'] for r in value['results'])
    finally:
        if app_id:
            cli('app','stop',app_id,'--yes')
            deadline=time.monotonic()+90
            while time.monotonic()<deadline:
                r=cli('container','list','--app-id',app_id,'--json')
                if not r.returncode and not json.loads(r.stdout):
                    report['zero_containers']=True;break
                time.sleep(5)
        (ROOT/f'research/qwen-kpIQITWg74-language-{args.label}.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report),flush=True)


if __name__=='__main__':
    main()
