"""Real extension/media playback with labelled HTTP/audio fixtures, no paid services."""
import base64
import argparse
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import time
import wave
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]


def wav(seconds, tone=False):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as output:
        output.setparams((1, 2, 8000, 0, 'NONE', 'not compressed'))
        output.writeframes(b''.join(struct.pack('<h', round(4000*math.sin(2*math.pi*220*i/8000))) for i in range(int(seconds*8000))) if tone else bytes(int(seconds*16000)))
    return stream.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--startup-seek', action='store_true')
    args = parser.parse_args()
    folder = ROOT / '.private/progressive-qa'
    folder.mkdir(exist_ok=True)
    report = {'scope': 'Actual Chrome extension and Web Audio playback, labelled provider/audio fixtures; no paid services', 'checks': []}
    rows = [{'id': i, 'start': i*3, 'end': i*3+2, 'text': f'Source sentence {i}.', 'translated': None} for i in range(80)]
    jobs, audio, windows, synths, cancellations = {}, {}, [], [], []
    registrations = []
    clip = base64.b64encode(wav(1.7, True)).decode()
    media = wav(242)
    with tempfile.TemporaryDirectory(dir=folder) as profile, sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}', '--autoplay-policy=no-user-gesture-required'], viewport={'width': 1400, 'height': 900})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            worker.evaluate('''chrome.storage.local.set({settings:{backend:'https://progressive-backend.test',voiceEndpoint:'https://fixture.modal.run',voiceId:'vi-dang-khoa'},
                voiceProxy:{id:'fixture',secret:'fixture'},session:{token:'fixture',request_key:'ab'.repeat(32),expires:Date.now()/1000+3600,ticket_expires:Date.now()/1000+7200}})''')
            def respond(route):
                req, url = route.request, route.request.url
                if url.startswith('https://fixture.modal.run'):
                    path=urlsplit(url).path
                    if path=='/v1/health':
                        route.fulfill(json={'capabilities':['voice_registry_v1','long_poll_v1']});return
                    if path=='/v1/voices':
                        registrations.append(req.post_data_json)
                        route.fulfill(json={'reference_id':'b'*64});return
                    identity = req.headers.get('idempotency-key') if req.method == 'POST' else path.rsplit('/', 1)[-1]
                    if req.method == 'POST':
                        value = req.post_data_json
                        assert value['reference_id']=='b'*64 and 'reference' not in value
                        assert value['duration'] is None, 'TTS must generate a natural whole sentence'
                        synths.append(value['text']); audio[identity] = {'ready': time.monotonic()+(2 if args.startup_seek else .15)}
                        route.fulfill(status=202, json={'id': identity})
                    elif req.method == 'DELETE':
                        cancellations.append('tts'); route.fulfill(json={'state': 'cancelled'})
                    else:
                        ready = time.monotonic() >= audio[identity]['ready']
                        route.fulfill(status=200 if ready else 202, json={'state': 'done', 'audio': clip, 'duration': 1.7} if ready else {'state': 'pending'})
                    return
                if url.startswith('https://progressive-backend.test'):
                    if req.method == 'POST':
                        payload = req.post_data_json; identity = f'{len(jobs)+1:032x}'
                        if url.endswith('/v1/jobs'):
                            assert payload['progressive'] and len(payload['cues']) == 80
                            plan = [dict(c) for c in rows]; plan[0]['translated'] = 'Speech sentence 0.'
                            result = {'cues': plan, 'progressive': True, 'translation_id': 'fixture-plan'}
                        else:
                            windows.append(payload['position'])
                            index = next(i for i, c in enumerate(rows) if c['end'] > payload['position'])
                            result = {'cues': [{**c, 'translated': f"Speech sentence {c['id']}."} for c in rows[index:index+payload['count']]], 'translation_id': 'fixture-plan'}
                        jobs[identity] = result
                        route.fulfill(status=202, json={'id': identity, 'state': 'queued'})
                    elif req.method == 'DELETE':
                        cancellations.append('translation'); route.fulfill(json={'state': 'cancelled'})
                    else:
                        route.fulfill(json={'state': 'done', 'result': jobs[url.rsplit('/', 1)[-1]]})
                    return
                if url.endswith('/captions.vtt'):
                    def timestamp(n):
                        return f'{n//3600:02}:{n//60%60:02}:{n%60:02}.000'
                    route.fulfill(body='WEBVTT\n\n'+'\n\n'.join(f"{timestamp(c['start'])} --> {timestamp(c['end'])}\n{c['text']}" for c in rows), content_type='text/vtt')
                    return
                if url.endswith('/media.wav'):
                    byte_range = req.headers.get('range', 'bytes=0-').split('=')[-1].split('-')
                    start = int(byte_range[0] or 0); end = int(byte_range[1]) if len(byte_range)>1 and byte_range[1] else len(media)-1
                    end = min(end, len(media)-1)
                    route.fulfill(status=206, body=media[start:end+1], headers={'Content-Type': 'audio/wav', 'Accept-Ranges': 'bytes', 'Content-Range': f'bytes {start}-{end}/{len(media)}'})
                    return
                route.fulfill(body='<html><head><title>Labelled progressive playback</title></head><body><video controls style="width:900px;height:500px" src="/media.wav"><track src="/captions.vtt" kind="subtitles" srclang="en"></video></body></html>', content_type='text/html')
            context.route('https://**/*', respond)
            page = context.new_page(); page.goto('https://progressive-video.test/video')
            page.wait_for_selector('#auvirel-surface', state='attached'); page.wait_for_timeout(1300)
            tab = worker.evaluate("async()=> (await chrome.tabs.query({})).find(t=>t.url==='https://progressive-video.test/video').id")
            worker.evaluate('''async tab=>chrome.scripting.executeScript({target:{tabId:tab},func:()=>{
                globalThis.audioAudit=[];const start=AudioBufferSourceNode.prototype.start;
                AudioBufferSourceNode.prototype.start=function(when,offset=0,...args){audioAudit.push({offset,duration:this.buffer?.duration,videoTime:document.querySelector('video').currentTime});return start.call(this,when,offset,...args)};
            }})''', tab)
            panel = shadow_eval(page, 'auvirel-surface')
            def state():
                return panel('function(){return this.querySelector("#state").textContent}')
            def until(predicate, timeout=20):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    if predicate(): return
                    if panel('function(){return this.querySelector(".status").dataset.state}') == 'error': raise AssertionError(state())
                    page.wait_for_timeout(80)
                raise AssertionError('Timeout: '+state())
            start=time.monotonic();panel('function(){this.querySelector("#start").click()}')
            if args.startup_seek:
                until(lambda:len(synths) == 1)
                page.evaluate('document.querySelector("video").currentTime=60')
                until(lambda:'Ready. Press play' in state())
                assert synths[:2] == ['Speech sentence 0.', 'Speech sentence 20.'], synths
                assert windows == [60], windows
                assert cancellations, 'Obsolete startup work must be cancelled'
                report['checks'].append('Seek during delayed first TTS preempts old audio and prepares only the new paused position')
                panel('function(){this.querySelector("#stop").click()}');page.wait_for_timeout(200)
                page.evaluate('document.querySelector("video").currentTime=180');page.wait_for_timeout(100)
                panel('function(){this.querySelector("#start").click()}')
                until(lambda:'Speech sentence 60.' in synths)
                panel('function(){this.querySelector("#stop").click()}')
                page.wait_for_timeout(2600)
                assert page.evaluate('document.querySelector("video").paused')
                audit=worker.evaluate('''async tab=>(await chrome.scripting.executeScript({target:{tabId:tab},func:()=>audioAudit}))[0].result''', tab)
                assert not audit, audit
                assert state() == 'Stopped', state()
                report['checks'].append('Stop during resumed preparation cancels work and cannot autoplay when the delayed response arrives')
                report.update(passed=True,total_syntheses=len(synths),total_windows=len(windows))
                return
            until(lambda:'Ready. Press play' in state())
            assert len(synths)==1 and not windows, (synths, windows)
            assert len(registrations)==1
            report['initial_ready_seconds']=round(time.monotonic()-start,3)
            report['checks'].append('Initial readiness uses one translated sentence and one TTS clip, not 80 cues')
            page.evaluate('document.querySelector("video").play()')
            until(lambda:len(windows)>0 and len(synths)>=3)
            assert max(windows)<36 and len(synths)<10
            page.wait_for_timeout(1700)
            page.evaluate('document.querySelector("video").pause()')
            page.wait_for_timeout(400); count=len(synths); window_count=len(windows)
            page.wait_for_timeout(1200)
            assert len(synths)==count and len(windows)==window_count
            report['checks'].append('Playback overlaps bounded nearby translation/TTS; manual pause stops lookahead')
            for position in [120, 30, 180]:
                page.evaluate('t=>{const v=document.querySelector("video");v.currentTime=t;v.play()}', position)
                until(lambda:any(abs(p-position)<1 for p in windows))
                until(lambda:f'Speech sentence {int(position/3)}.' in synths)
                page.wait_for_timeout(1000)
            report['checks'].append('Forward/backward/repeated seeks translate and synthesize the new playhead without walking the skipped tail')
            page.evaluate('document.querySelector("video").pause()'); page.wait_for_timeout(200)
            before=len(synths);before_windows=len(windows)
            page.evaluate('const v=document.querySelector("video");v.currentTime=120;v.play()')
            page.wait_for_timeout(1500)
            assert synths.count('Speech sentence 40.')==1, synths
            report['checks'].append('Seek replay uses cached audio; current translated sentence is not retransmitted for translation')
            for position in [90, 210, 60]:
                page.evaluate('t=>{const v=document.querySelector("video");v.currentTime=t;v.play()}',position)
                page.wait_for_timeout(40)
            until(lambda:'Speech sentence 20.' in synths)
            page.wait_for_timeout(1000)
            report['checks'].append('Rapid seeks reanchor to the final requested region')
            assert len(registrations)==1
            report['checks'].append('All synthesis requests reuse one registered reference and omit the WAV payload')
            audit=worker.evaluate('''async tab=>(await chrome.scripting.executeScript({target:{tabId:tab},func:()=>audioAudit}))[0].result''', tab)
            assert audit and audit[0]['offset']==0, audit
            assert all(item['offset']>=0 and item['offset']<item['duration'] for item in audit)
            panel('function(){this.querySelector("#stop").click()}');page.wait_for_timeout(250)
            before=(len(synths),len(windows));page.wait_for_timeout(1000);assert before==(len(synths),len(windows))
            report.update(passed=True, audio_starts=len(audit), maximum_requested_position=max(windows), total_syntheses=len(synths), total_windows=len(windows))
        except Exception as error:
            report.update(passed=False,error=str(error)[:1500]);raise
        finally:
            name='progressive-startup-seek.json' if args.startup_seek else 'progressive-acceptance.json'
            context.close();(ROOT/'research'/name).write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))


if __name__ == '__main__':
    main()
