"""Actual extension, explicitly labelled site fixtures; never calls paid providers."""
import json
from pathlib import Path
import time
import tempfile

from playwright.sync_api import sync_playwright
from ui_acceptance import shadow_eval, Popup

ROOT = Path(__file__).resolve().parents[1]
VTT = 'WEBVTT\n\n00:01.000 --> 00:03.000\nExisting captions.\n\n00:04.000 --> 00:06.000\nKeep original timing.'
TTML = '<tt xmlns="http://www.w3.org/ns/ttml"><body begin="1s"><div><p begin="0s" dur="2s">Existing captions.</p><p begin="3s" end="5s">Keep original timing.</p></div></body></tt>'


def main():
    output = ROOT / '.private/multisite-qa'
    output.mkdir(exist_ok=True)
    report = {'scope': 'Actual Chromium MV3 extension with explicit routed fixtures; no live-site certification', 'checks': []}
    cases = {
        'dom_vtt': 'https://www.coursera.org/learn/science/lecture/one',
        'dom_ttml': 'https://www.vimeo.com/123',
        'shadow_mux': 'https://www.aihero.dev/lesson',
        'iframe': 'https://course-fixture.test/lesson',
        'metadata_fetch': 'https://learn.microsoft.com/en-us/shows/test/lesson',
        'metadata_xhr': 'https://www.udemy.com/course/test/learn/lecture/123',
        'bili': 'https://www.bilibili.com/video/BVtest',
        'wistia': 'https://fast.wistia.net/embed/iframe/abc123',
        'kinescope': 'https://kinescope.io/embed/abc123',
        'jwplayer': 'https://www.nbcnews.com/video/example',
        'hls': 'https://developer.apple.com/videos/play/wwdc2025/100',
        'blob_swap': 'https://developer.apple.com/videos/play/wwdc2025/101',
        'hls_source': 'https://player-source-fixture.test/lesson',
        'track_failure': 'https://www.coursera.org/learn/science/lecture/error',
        'unknown': 'https://unverified-fixture.test/video',
        'spa': 'https://learn.microsoft.com/en-us/shows/test/old',
        'spa_fresh': 'https://learn.microsoft.com/en-us/shows/test/old-fresh',
        'multiple': 'https://learn.microsoft.com/en-us/shows/test/multiple',
        'partial': 'https://unverified-fixture.test/partial',
    }
    scenario = {'name': ''}
    jobs = []
    with sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        profile = tempfile.TemporaryDirectory(prefix='profile-', dir=output)
        context = p.chromium.launch_persistent_context(profile.name, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'], viewport={'width': 1440, 'height': 1000})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            worker.evaluate('''chrome.storage.local.set({settings:{backend:'https://caption-backend.test',asr:'quality'},
                session:{token:'fixture-only',request_key:'ab'.repeat(32),expires:Date.now()/1000+3600,ticket_expires:Date.now()/1000+7200}})''')

            def route_request(route):
                url, name = route.request.url, scenario['name']
                if url.startswith('https://caption-backend.test/'):
                    if url.endswith('/v1/jobs'):
                        jobs.append(route.request.post_data_json)
                    route.fulfill(status=422, json={'detail': 'TEST ONLY: provider dispatch intercepted'})
                    return
                if '/api/video/public/v1/entries/' in url:
                    route.fulfill(json={'publicVideo': {'captions': [{'url': '/full.vtt', 'language': 'en-US'}]}})
                    return
                if '/api-2.0/' in url:
                    route.fulfill(json={'asset': {'captions': [{'url': '/full.vtt', 'locale_id': 'en_US'}]}})
                    return
                if '/x/player/wbi/v2?' in url:
                    route.fulfill(json={'data': {'subtitle': {'subtitles': [{'subtitle_url': 'https://i.hdslb.com/bfs/subtitle/test.json', 'lan': 'en'}]}}})
                    return
                if '/bfs/subtitle/' in url:
                    route.fulfill(json={'body': [{'from': 1, 'to': 3, 'content': 'Existing captions.'}, {'from': 4, 'to': 6, 'content': 'Keep original timing.'}]})
                    return
                if '/embed/captions/' in url:
                    route.fulfill(json={'captions': [{'language': 'en', 'hash': {'lines': [{'start': 1, 'end': 3, 'text': ['Existing captions.']}, {'start': 4, 'end': 6, 'text': ['Keep original timing.']}]}}]}, headers={'Access-Control-Allow-Origin': '*'})
                    return
                if url.endswith('/master.m3u8'):
                    route.fulfill(body='#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en",DEFAULT=YES,URI="sub.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nvideo.m3u8', content_type='application/vnd.apple.mpegurl')
                    return
                if url.endswith('/sub.m3u8'):
                    route.fulfill(body='#EXTM3U\n#EXTINF:10,\nfull.vtt\n#EXT-X-ENDLIST', content_type='application/vnd.apple.mpegurl')
                    return
                if url.endswith('/full.vtt') or url.endswith('/full.ttml'):
                    route.fulfill(status=403 if name == 'track_failure' else 200, body='Forbidden' if name == 'track_failure' else TTML if url.endswith('.ttml') else VTT,
                                  content_type='application/ttml+xml' if url.endswith('.ttml') else 'text/vtt', headers={'Access-Control-Allow-Origin': '*'})
                    return
                if name == 'iframe' and 'course-fixture.test' in url:
                    route.fulfill(body='<html><body><h1>Labelled iframe fixture</h1><iframe src="https://player.vimeo.com/video/123" style="width:1000px;height:700px"></iframe></body></html>', content_type='text/html')
                    return
                video = '<video id="video" data-id="fixture-lesson" style="width:800px;height:450px" crossorigin="anonymous">'
                if name in ['dom_vtt', 'dom_ttml', 'shadow_mux', 'iframe', 'track_failure']:
                    video += '<track kind="subtitles" srclang="en" src="/full.' + ('ttml' if name == 'dom_ttml' else 'vtt') + '">'
                video += '</video>'
                if name == 'hls_source':
                    video = video.replace('</video>', '<source src="/master.m3u8" type="application/x-mpegURL"></video>')
                script = ''
                if name == 'shadow_mux':
                    script = 'document.querySelector("mux-player").attachShadow({mode:"open"}).innerHTML=' + json.dumps(video) + ';'
                    video = '<mux-player></mux-player>'
                if name in ['metadata_fetch', 'spa', 'spa_fresh', 'multiple']:
                    script += 'fetch("/api/video/public/v1/entries/lesson").then(r=>r.json());'
                if name == 'multiple':
                    video += '<video style="width:400px;height:250px"></video>'
                if name == 'metadata_xhr':
                    script += 'const x=new XMLHttpRequest();x.open("GET","/api-2.0/users/me/subscribed-courses/1/lectures/123");x.responseType="json";x.send();'
                if name == 'bili':
                    script += 'fetch("/x/player/wbi/v2?bvid=BVtest").then(r=>r.json());'
                if name == 'kinescope':
                    script += 'window.onKinescopePlayerCreated?.({getPlaylistItem:async()=>({vtt:[{src:"/full.vtt",srcLang:"en"}]})});'
                if name == 'jwplayer':
                    video = '<div class="jwplayer" id="jw">' + video + '</div>'
                    script += 'window.jwplayer=()=>({getPlaylistItem:()=>({tracks:[{file:"/full.vtt",kind:"captions",language:"en"}]})});'
                if name in ['hls', 'blob_swap']:
                    script += 'fetch("/master.m3u8").then(r=>r.text());'
                if name == 'blob_swap':
                    script += 'document.querySelector("video").src=URL.createObjectURL(new Blob(["fixture-media"],{type:"video/mp4"}));'
                if name == 'partial':
                    script += 'fetch("/full.vtt").then(r=>r.text());'
                html = '<!doctype html><html><head><title>Labelled multisite fixture</title></head><body><h1>Test fixture</h1>' + video + '<script>' + script + '</script></body></html>'
                route.fulfill(body=html, content_type='text/html')

            context.route('https://**/*', route_request)
            failures = {'track_failure', 'unknown', 'spa', 'multiple', 'partial'}
            for name, url in cases.items():
                scenario['name'] = name
                page = context.new_page()
                page.goto(url)
                if name == 'iframe':
                    frame = page.frame(url='https://player.vimeo.com/video/123')
                    frame.wait_for_selector('#auvirel-surface', state='attached')
                    # Exercise the same selected-frame route used by popup, without accessing a foreign frame DOM.
                    tab_id = worker.evaluate('''async()=> (await chrome.tabs.query({})).find(t=>t.url==='https://course-fixture.test/lesson').id''')
                    frames = worker.evaluate('''async id=>await chrome.scripting.executeScript({target:{tabId:id,allFrames:true},func:()=>Boolean(globalThis.VeloaMedia?.videos().length)})''', tab_id)
                    frame_id = next(f['frameId'] for f in frames if f['result'])
                    invoke = lambda command: worker.evaluate('''async args=>await chrome.tabs.sendMessage(args.tab,{type:'veloaPlayer',command:args.command},{frameId:args.frame})''', {'tab': tab_id, 'frame': frame_id, 'command': command})
                    page.wait_for_timeout(1200)
                    before = len(jobs)
                    invoke('start')
                    deadline = time.monotonic() + 30
                    while time.monotonic() < deadline and len(jobs) == before:
                        page.wait_for_timeout(100)
                    assert len(jobs) == before + 1, (name, invoke('state'))
                    report['checks'].append('iframe: correct cross-origin frame sends complete captions')
                    page.close()
                    continue
                page.wait_for_selector('#auvirel-surface', state='attached')
                page.wait_for_timeout(1300)
                panel = shadow_eval(page, 'auvirel-surface')
                if name in ['spa', 'spa_fresh']:
                    page.evaluate('history.pushState({},"","/en-us/shows/test/new")')
                    page.wait_for_timeout(1300)
                    if name == 'spa_fresh':
                        page.evaluate('fetch("/api/video/public/v1/entries/new").then(r=>r.json())')
                before = len(jobs)
                panel('function(){this.querySelector("#start").click()}')
                deadline = time.monotonic() + 30
                while time.monotonic() < deadline:
                    if panel('function(){return this.querySelector(".status").dataset.state}') == 'error':
                        break
                    page.wait_for_timeout(100)
                state = panel('function(){return this.querySelector("#state").textContent}')
                if name in failures:
                    assert len(jobs) == before, (name, 'Unexpected ASR request', jobs[before:])
                    assert 'ASR' in state, (name, state)
                    assert not panel('function(){return this.querySelector("#use-asr").hidden}'), name
                    if name == 'unknown':
                        page.bring_to_front()
                        worker.evaluate('chrome.action.openPopup()')
                        page.wait_for_timeout(500)
                        popup = Popup(page, worker.url.split('/')[2])
                        assert not popup.evaluate('document.querySelector("#use-asr").hidden')
                        popup.screenshot(output / 'explicit-asr-popup.png')
                        popup.evaluate('document.querySelector("#use-asr").click()')
                        page.wait_for_timeout(500)
                        assert len(jobs) == before+1 and 'cues' not in jobs[-1], 'Explicit ASR action failed'
                        popup.evaluate('window.close()')
                    report['checks'].append(name + ': no automatic ASR; explicit fallback available')
                else:
                    assert len(jobs) == before+1, (name, state)
                    assert [(c['start'], c['end'], c['text']) for c in jobs[-1]['cues']] == [(1, 3, 'Existing captions.'), (4, 6, 'Keep original timing.')], (name, jobs[-1])
                    assert jobs[-1]['source_language'] in ['en', 'en-US'], (name, jobs[-1])
                    report['checks'].append(name + ': complete native captions; zero ASR dispatch')
                if name == 'dom_vtt':
                    assert page.evaluate('document.querySelector("video").textTracks[0].mode') == 'disabled'
                page.close()
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1200])
            raise
        finally:
            context.close()
            profile.cleanup()
            (ROOT / 'research/multisite-acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
