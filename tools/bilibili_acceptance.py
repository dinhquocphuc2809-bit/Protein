"""Actual packaged MV3 regression on labelled Bilibili fixtures, never the user profile."""
import json
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit, parse_qs

from playwright.sync_api import sync_playwright
from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.bilibili.com/video/BV1WqYV6cEwq/'
STATE = {'aid': 123, 'cid': 456, 'bvid': 'BV1WqYV6cEwq', 'videoData': {
    'aid': 123, 'cid': 456, 'bvid': 'BV1WqYV6cEwq', 'pages': [{'page': 1, 'cid': 456}, {'page': 2, 'cid': 789}]}}
CASES = ['active', 'localized', 'missing_state', 'blob_swap', 'part_two', 'stale_state', 'wrong_cid',
         'legacy', 'legacy_observed', 'empty', 'session', 'malformed_track', 'menu_off', 'menu_on', 'menu_failure', 'menu_no_items', 'navigate_pending', 'part_switch']


def main():
    folder = ROOT / '.private/bili-qa'
    folder.mkdir(exist_ok=True)
    report = {'scope': 'Actual Chrome MV3 with explicitly routed Bilibili fixtures, not live Bilibili certification', 'checks': []}
    scenario = {'name': ''}
    jobs, requests = [], []
    with tempfile.TemporaryDirectory(dir=folder) as profile, sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'], viewport={'width': 1440, 'height': 1000})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            context.add_cookies([{'name': 'fixture_session', 'value': 'test-only', 'domain': 'api.bilibili.com', 'path': '/', 'secure': True, 'sameSite': 'Lax'}])
            worker.evaluate('''chrome.storage.local.set({settings:{backend:'https://bili-backend.test'},session:{token:'fixture',
                request_key:'ab'.repeat(32),expires:Date.now()/1000+3600,ticket_expires:Date.now()/1000+7200}})''')

            def respond(route):
                url, name = route.request.url, scenario['name']
                parsed = urlsplit(url)
                if parsed.hostname == 'bili-backend.test':
                    if parsed.path == '/v1/jobs':
                        jobs.append(route.request.post_data_json)
                    route.fulfill(status=422, json={'detail': 'TEST ONLY: paid provider dispatch blocked'})
                    return
                if parsed.hostname == 'api.bilibili.com':
                    requests.append(url)
                    if name == 'active':
                        assert 'fixture_session=test-only' in route.request.headers.get('cookie', ''), 'Browser-session credentials missing'
                    if name == 'navigate_pending':
                        time.sleep(.4)
                    if parsed.path == '/x/web-interface/view':
                        route.fulfill(json={'code': 0, 'data': STATE['videoData']})
                        return
                    cid = int(parse_qs(parsed.query)['cid'][0])
                    if name == 'legacy' and '/wbi/' in parsed.path:
                        route.fulfill(status=403, json={'code': -403})
                        return
                    if name == 'session':
                        route.fulfill(json={'code': -101})
                        return
                    tracks = [] if name in ['empty', 'menu_off', 'menu_on', 'menu_failure', 'menu_no_items'] or (name == 'legacy_observed' and '/wbi/' in parsed.path) else [
                        {'subtitle_url': f'https://i.hdslb.com/bfs/subtitle/{cid}.json', 'lan': 'ai-en', 'type': 1}]
                    if name == 'malformed_track':
                        tracks = [{'lan': 'en'}, {'subtitle_url': '', 'lan': 'en'}]
                    route.fulfill(json={'code': 0, 'data': {'aid': 123, 'cid': cid, 'subtitle': {'subtitles': tracks}}})
                    return
                if parsed.hostname == 'i.hdslb.com':
                    if name == 'menu_failure':
                        route.fulfill(status=403, body='fixture-denied')
                    else:
                        route.fulfill(json={'body': [{'from': 1, 'to': 3, 'content': parsed.path.rsplit('/', 1)[-1]},
                            {'from': 4, 'to': 6, 'content': 'Complete fixture captions.'}]}, headers={'Access-Control-Allow-Origin': '*'})
                    return
                state = dict(STATE)
                if name == 'stale_state':
                    state = {'bvid': 'BVprevious', 'aid': 99, 'cid': 98}
                script = '' if name == 'missing_state' else 'window.__INITIAL_STATE__=' + json.dumps(state) + ';'
                script += '''const originalFetch=window.fetch;
                    window.fixtureRequests=[];
                    window.fetch=async function(input,options){
                        fixtureRequests.push({url:String(input),credentials:options?.credentials});
                        return originalFetch.call(this,input,options);
                    };
                    const video=document.querySelector('video');video.src='https://media-fixture.test/file.mp4';
                    Object.defineProperty(video,'duration',{value:100});
                '''
                if name in ['blob_swap', 'wrong_cid']:
                    script += 'fetch("https://api.bilibili.com/x/player/wbi/v2?aid=123&cid=' + ('999' if name == 'wrong_cid' else '456') + '").then(r=>r.json());'
                if name == 'legacy_observed':
                    script += 'fetch("https://api.bilibili.com/x/player/v2?aid=123&cid=456").then(r=>r.json());'
                if name == 'blob_swap':
                    script += 'setTimeout(()=>{video.src=URL.createObjectURL(new Blob(["fixture"],{type:"video/mp4"}))},400);'
                menu = ''
                if name == 'session':
                    menu = '<div class="bpx-player-ctrl-subtitle"><button class="bpx-player-ctrl-subtitle-language-item" data-lan="ai-en">Login required</button><button class="bpx-player-ctrl-subtitle-close-switch bpx-state-active">Off</button></div>'
                    script += 'window.fixtureSessionMenu=0;document.querySelector(".bpx-player-ctrl-subtitle").addEventListener("mouseenter",()=>fixtureSessionMenu++);'
                if name.startswith('menu_'):
                    menu = '''<div class="bpx-player-ctrl-btn bpx-player-ctrl-subtitle">
                      <button class="bpx-player-ctrl-subtitle-close-switch">Off</button>
                      <button class="bpx-player-ctrl-subtitle-language-item" data-lan="ai-en">English</button>
                    </div>'''
                    script += '''const off=document.querySelector('.bpx-player-ctrl-subtitle-close-switch');
                        const item=document.querySelector('[data-lan]');
                        off.onclick=()=>{off.classList.add('bpx-state-active');item.classList.remove('bpx-state-active');};
                        item.onclick=()=>{off.classList.remove('bpx-state-active');item.classList.add('bpx-state-active');
                            fetch('https://i.hdslb.com/bfs/subtitle/456.json').then(r=>r.text());};
                    ''' + ("item.classList.add('bpx-state-active');" if name == 'menu_on' else "off.classList.add('bpx-state-active');")
                    script += 'window.fixtureLeave=0;document.querySelector(".bpx-player-ctrl-subtitle").addEventListener("mouseleave",()=>fixtureLeave++);'
                    if name == 'menu_no_items':
                        script += 'item.remove();'
                if parsed.hostname == 'media-fixture.test':
                    route.fulfill(status=404, body='No media needed for caption acquisition fixtures')
                    return
                route.fulfill(body='<!doctype html><html><head><title>Labelled Bilibili fixture</title></head><body><h1>Regression fixture</h1>'
                    '<div class="bpx-player-container" style="width:800px"><video style="width:800px;height:450px"></video>'
                    '<div class="bpx-player-control-bottom-right" style="display:flex;height:40px">' + menu + '</div></div>'
                    '<script>' + script + '</script></body></html>', content_type='text/html')

            context.route('https://**/*', respond)
            for name in CASES:
                scenario['name'] = name
                page = context.new_page()
                page.goto((URL.replace('/video/', '/en/video/') if name == 'localized' else URL) + ('?p=2' if name == 'part_two' else ''))
                page.wait_for_selector('.vocalm-player-button', state='attached')
                assert page.locator('.bpx-player-control-bottom-right > .vocalm-player-button').count() == 1, name
                panel = shadow_eval(page, 'auvirel-surface')
                page.locator('.vocalm-player-button').click()
                assert panel('function(){return !this.querySelector(".quick-menu").hidden}'), name
                panel('function(){this.querySelector(".quick-close").click()}')
                if name == 'part_switch':
                    page.evaluate('fetch("https://api.bilibili.com/x/player/wbi/v2?aid=123&cid=456").then(r=>r.json())')
                    page.evaluate('history.pushState({},"","?p=2")')
                    page.wait_for_timeout(1400)
                if name == 'navigate_pending':
                    page.evaluate('setTimeout(()=>history.pushState({},"","?p=2"),100)')
                before, request_start = len(jobs), len(requests)
                panel('function(){this.querySelector("#start").click()}')
                deadline = time.monotonic() + 25
                while time.monotonic() < deadline:
                    if panel('function(){return this.querySelector(".status").dataset.state}') == 'error':
                        break
                    if name == 'navigate_pending' and page.url.endswith('?p=2'):
                        page.wait_for_timeout(1800)
                        break
                    page.wait_for_timeout(100)
                text = panel('function(){return this.querySelector("#state").textContent}')
                failed = name in ['legacy', 'legacy_observed', 'empty', 'session', 'malformed_track', 'menu_failure', 'menu_no_items', 'navigate_pending']
                if failed:
                    assert len(jobs) == before, (name, text, jobs[before:])
                    if name != 'navigate_pending':
                        assert 'ASR' in text, (name, text)
                else:
                    assert len(jobs) == before + 1, (name, text, requests[request_start:])
                    expected = '789.json' if name in ['part_two', 'part_switch'] else '456.json'
                    assert jobs[-1]['cues'][0]['text'] == expected, (name, jobs[-1])
                    assert jobs[-1]['source_language'] == 'en', (name, jobs[-1])
                if name.startswith('menu_'):
                    assert page.locator('.bpx-player-ctrl-subtitle-close-switch').evaluate("e=>e.classList.contains('bpx-state-active')") == (name != 'menu_on'), name
                    assert page.evaluate('fixtureLeave') >= 1, (name, 'Subtitle menu not released')
                if name == 'session':
                    assert page.evaluate('fixtureSessionMenu') == 0, 'Must not open login-gated subtitle controls'
                if name == 'blob_swap':
                    assert len(requests) == request_start, ('Captured metadata lost on blob swap', requests[request_start:])
                if name == 'active':
                    page.screenshot(path=str(folder / 'native-control.png'))
                report['checks'].append({'case': name, 'passed': True, 'job_with_cues': not failed,
                    'metadata_requests': len(requests) - request_start})
                page.close()
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1500])
            raise
        finally:
            context.close()
            (ROOT / 'research/bilibili-acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
