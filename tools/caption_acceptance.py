"""Actual extension regression with labelled YouTube/provider fixtures; no paid services."""
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright

from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]
VIDEO = '3BndvjrGwyE'


def main():
    output = ROOT / '.private/caption-qa'
    output.mkdir(exist_ok=True)
    report = {'scope': 'Actual extension with explicit page/provider fixtures; no paid ASR or translation', 'checks': []}
    body = json.dumps({'events': [{'tStartMs': 1000, 'dDurationMs': 2200, 'segs': [{'utf8': 'Existing YouTube captions.'}]},
                                 {'tStartMs': 4000, 'dDurationMs': 1800, 'segs': [{'utf8': 'Do not run ASR.'}]}]})
    xml = '<timedtext><body><p t="1000" d="2200">Existing YouTube captions.</p><p t="4000" d="1800">Do not run ASR.</p></body></timedtext>'
    with sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(str(output / 'regression-profile'), channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'], viewport={'width': 1440, 'height': 1000})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            # Test-only session against a routed fake origin. No real tickets/credentials.
            worker.evaluate('''chrome.storage.local.set({settings:{backend:'https://caption-backend.test',asr:'quality'},
                session:{token:'fixture-only',request_key:'ab'.repeat(32),expires:Date.now()/1000+3600,ticket_expires:Date.now()/1000+7200}})''')
            jobs = []
            def backend(route):
                if route.request.url.endswith('/v1/jobs'):
                    jobs.append(route.request.post_data_json)
                route.fulfill(status=422, json={'detail': 'TEST ONLY: intercepted before provider dispatch'})
            context.route('https://caption-backend.test/**', backend)
            scenario = {'name': 'direct'}
            def youtube(route):
                name = scenario['name']
                if '/api/timedtext' in route.request.url:
                    native = 'native=1' in route.request.url
                    success = name in ['direct', 'initial_fallback'] or (native and name in ['player_fetch', 'player_xhr', 'xml', 'cached'])
                    route.fulfill(body=(xml if name == 'xml' else body) if success else '', content_type='text/xml' if name == 'xml' else 'application/json')
                    return
                if '/youtubei/' in route.request.url:
                    if name in ['transcript', 'transcript_capture']:
                        route.fulfill(json={'actions':[{'transcriptSegmentRenderer':{'startMs':'1000','endMs':'3200','snippet':{'runs':[{'text':'Existing YouTube captions.'}]}}},
                                                      {'transcriptSegmentRenderer':{'startMs':'4000','endMs':'5800','snippet':{'runs':[{'text':'Do not run ASR.'}]}}}]})
                    else:
                        route.fulfill(status=400, json={'error': 'fixture transcript unavailable'})
                    return
                tracks = [] if name in ['absent', 'pending'] else [
                    {'baseUrl': f'https://www.youtube.com/api/timedtext?v={VIDEO}&lang=ar&kind=asr', 'languageCode': 'ar', 'kind': 'asr'},
                    {'baseUrl': f'https://www.youtube.com/api/timedtext?v={VIDEO}&lang=en&kind=asr', 'languageCode': 'en', 'kind': 'asr'}]
                response = {'videoDetails': {'videoId': VIDEO, 'lengthSeconds': '1381'}, 'playabilityStatus': {'status': 'OK'},
                            'captions': {'playerCaptionsTracklistRenderer': {'captionTracks': tracks}}}
                script = '''const player=document.querySelector('#movie_player');
                  let selected={languageCode:'en',kind:'asr'};
                  window.ytInitialPlayerResponse=RESPONSE;
                  player.getPlayerResponse=()=>SCENARIO==='pending'?null:SCENARIO==='initial_fallback'?{videoDetails:{videoId:VIDEO},playabilityStatus:{status:'OK'}}:ytInitialPlayerResponse;
                  player.getVideoData=()=>({video_id:VIDEO});player.getOption=()=>selected;player.loadModule=()=>{};
                  player.setOption=(module,key,value)=>{selected=value;if(!value.languageCode)return;
                    const url='/api/timedtext?v='+VIDEO+'&lang='+value.languageCode+'&kind=asr&native=1';
                    if(SCENARIO==='player_xhr'||SCENARIO==='xml'){const xhr=new XMLHttpRequest();xhr.open('GET',url);xhr.send();}
                    else fetch(url).then(r=>r.text());};
                  window.currentTrack=()=>selected;
                  if(SCENARIO==='pending')window.ytInitialPlayerResponse={videoDetails:{videoId:'different'}};
                  if(SCENARIO==='cached')player.setOption('captions','track',selected);
                  if(SCENARIO==='transcript'||SCENARIO==='transcript_capture'){
                    window.ytInitialData={getTranscriptEndpoint:{params:'fixture-only'}};
                    window.ytcfg={get:(key)=>key==='INNERTUBE_CONTEXT'?{client:{clientVersion:'fixture-only'}}:1};
                  }
                  if(SCENARIO==='transcript_capture')fetch('/youtubei/v1/get_transcript',{method:'POST'}).then(r=>r.text());
                '''.replace('RESPONSE', json.dumps(response)).replace('SCENARIO', json.dumps(name)).replace('VIDEO', json.dumps(VIDEO))
                html = '''<!doctype html><html><head><title>Caption acquisition regression fixture</title></head>
                    <body><h1>Labelled fixture, no provider work</h1><div id="movie_player"><video style="width:800px;height:450px"></video>
                    <button class="ytp-subtitles-button" aria-pressed="false">CC fixture</button></div><script>''' + script + '</script></body></html>'
                route.fulfill(body=html, content_type='text/html')
            context.route('https://www.youtube.com/**', youtube)
            for name in ['direct', 'initial_fallback', 'player_fetch', 'player_xhr', 'xml', 'cached', 'transcript', 'transcript_capture', 'failure', 'pending', 'absent']:
                scenario['name'] = name
                page = context.new_page()
                page.goto(f'https://www.youtube.com/watch?v={VIDEO}')
                page.wait_for_selector('#auvirel-surface', state='attached')
                page.wait_for_timeout(1300)
                panel = shadow_eval(page, 'auvirel-surface')
                before = len(jobs)
                panel('function(){this.querySelector("#start").click()}')
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if panel('function(){return this.querySelector(".status").dataset.state}') == 'error':
                        break
                    page.wait_for_timeout(100)
                state = panel('function(){return this.querySelector("#state").textContent}')
                if name in ['failure', 'pending']:
                    assert len(jobs) == before, (name, 'Unexpected ASR request')
                    assert 'ASR' in state, (name, state)
                    report['checks'].append(name + ': no backend job on unavailable/unknown captions')
                else:
                    assert len(jobs) == before+1, (name, state)
                    request = jobs[-1]
                    if name == 'absent':
                        assert 'cues' not in request
                        report['checks'].append('confirmed absent: ASR path allowed after repeated current-video checks')
                    else:
                        assert request['source_language'] == ('auto' if name.startswith('transcript') else 'en'), (name, request)
                        assert len(request['cues']) == 2 and request['cues'][0]['start'] == 1
                        assert request['cues'][0]['text'] == 'Existing YouTube captions.'
                        report['checks'].append(name + ': existing English cues sent to backend, ASR unnecessary')
                if name in ['player_fetch', 'player_xhr', 'xml', 'failure']:
                    assert page.evaluate('currentTrack().languageCode') is None, 'CC off state was not restored'
                page.close()
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1000])
            raise
        finally:
            context.close()
            (ROOT / 'research/caption-acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
