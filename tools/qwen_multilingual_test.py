"""Final candidate Chinese/English/Vietnamese/silence/fallback live regression."""
import hashlib
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
    env = environment(2)
    env.update(VOCALM_ASR_SNAPSHOT='1', VOCALM_ASR_BATCH='4', PYTHONPATH=str(ROOT))
    os.environ.update(env)
    import modal
    folder = ROOT/'.private/qwen-improvement'
    report = {'account': 2, 'passed': False, 'cases': [], 'source_sha256': hashlib.sha256((ROOT/'gpu/asr.py').read_bytes()).hexdigest()}
    app_id = None
    def cli(*args, timeout=60):
        return subprocess.run([sys.executable,'-m','modal',*args],cwd=ROOT,env=env,capture_output=True,encoding='utf-8',timeout=timeout)
    try:
        deployed = cli('deploy','gpu/asr_optimized_probe.py',timeout=300)
        (folder/'multilingual-deploy.log').write_text(deployed.stdout+deployed.stderr,encoding='utf-8')
        if deployed.returncode:
            raise RuntimeError('Multilingual candidate deploy failed')
        apps=json.loads(cli('app','list','--json').stdout)
        app_id=next(a['app_id'] for a in apps if a['description']=='vocalm-qwen-t4-optimized-test' and a['state']=='deployed')
        worker=modal.Cls.from_name('vocalm-qwen-t4-optimized-test','Probe')()
        def window(index):
            with wave.open(str(ROOT/'.private/asr-long-video/audio.wav')) as w:
                w.setpos(index*24*16000);frames=w.readframes(28*16000)
            buffer=io.BytesIO()
            with wave.open(buffer,'wb') as w:
                w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(frames)
            return buffer.getvalue()
        cases=[('english','en',[(folder/'english.wav').read_bytes()]),
               ('vietnamese','vi',[(folder/'vietnamese.wav').read_bytes()]),
               ('chinese_fallback','zh',[window(165)]),
               ('mixed_auto','auto',[(folder/'english.wav').read_bytes(),window(200),window(374)])]
        for name,language,audio in cases:
            started=time.perf_counter();call=worker.measure.spawn(audio,4,language)
            try:
                value=call.get(timeout=300)
            except BaseException:
                call.cancel(terminate_containers=True);raise
            results=value.pop('results')
            (folder/(name+'-result.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
            assert len(results)==len(audio)
            assert all(0<=w['start']<=w['end']<=r['duration']+.001 for r in results for w in r['words'])
            assert all(r['words'] for r in results[:-1] if name=='mixed_auto')
            if name=='mixed_auto':
                assert not results[-1]['words']
            else:
                assert results[0]['words']
            if name=='english':
                text=' '.join(w['text'] for w in results[0]['words']).lower()
                assert 'elephant' in text and 'dolly' in text
            report['cases'].append({'name':name,'language':language,'rpc_seconds':time.perf_counter()-started,
                'word_counts':[len(r['words']) for r in results], 'detected':[r['language'] for r in results],
                'alignment_recoveries':sum(r['alignment_recoveries'] for r in results),
                'valid_times':True, 'rss_bytes':value['after']['process']['VmRSS_bytes'],
                'peak_reserved_bytes':value['peak_reserved_bytes']})
            print(json.dumps(report['cases'][-1]),flush=True)
        previous_boot=value['boot_id']
        known_initializations={value['initialization_id']}
        report['retired_vietnamese_cycles']=[]
        for cycle in range(4):
            deadline=time.monotonic()+180
            while True:
                containers=cli('container','list','--app-id',app_id,'--json')
                if not containers.returncode and not json.loads(containers.stdout):
                    break
                if time.monotonic()>=deadline:
                    raise TimeoutError('Cannot verify retired multilingual container')
                time.sleep(5)
            started=time.perf_counter()
            call=worker.measure.spawn([(folder/'vietnamese.wav').read_bytes()],4,'vi')
            try:
                restored=call.get(timeout=300)
            except BaseException:
                call.cancel(terminate_containers=True);raise
            row={'rpc_seconds':time.perf_counter()-started,
                'different_boot':restored['boot_id']!=previous_boot,
                'known_initialization':restored['initialization_id'] in known_initializations, 'call':restored['call'],
                'same_words':restored['results']==json.loads((folder/'vietnamese-result.json').read_text(encoding='utf-8'))}
            report['retired_vietnamese_cycles'].append(row)
            assert row['different_boot'] and restored['call']==1 and row['same_words']
            print(json.dumps(row),flush=True)
            if row['known_initialization']:
                report['restored_vietnamese']=row
                break
            known_initializations.add(restored['initialization_id'])
            previous_boot=restored['boot_id']
        assert report.get('restored_vietnamese'), 'No proven snapshot restore for Vietnamese'
        report['passed']=True
    except Exception as error:
        report['error_type']=type(error).__name__
        (folder/'multilingual-error.txt').write_text(str(error),encoding='utf-8')
        raise
    finally:
        if app_id:
            report['app_id']=app_id
            cli('app','stop',app_id,'--yes')
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                result=cli('container','list','--app-id',app_id,'--json')
                if not result.returncode and not json.loads(result.stdout):
                    report['zero_containers']=True;break
                time.sleep(5)
        (ROOT/'research/benchmarks/qwen-optimized-multilingual.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['passed'] and report.get('zero_containers') else 1


if __name__=='__main__':
    raise SystemExit(main())
