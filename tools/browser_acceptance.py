"""Isolated Chromium extension test with real backend and Modal HTTP services."""
import json
from pathlib import Path
import re
import tempfile
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / '.private/browser-qa'
    output.mkdir(parents=True, exist_ok=True)
    endpoint = json.loads((ROOT / '.private/public-endpoint.json').read_text())['url']
    ticket = json.loads((ROOT / '.private/owner-ticket.json').read_text())['code']
    proxy = json.loads((ROOT / '.private/modal-4-proxy.json').read_text())
    voice = re.search(r'https://[^\s]+\.modal\.run', (ROOT / '.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
    report = {'checks': [], 'errors': []}
    requests = []
    with tempfile.TemporaryDirectory(dir=output) as profile, sync_playwright() as playwright:
        extension = ROOT / 'dist/chrome'
        context = playwright.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}', '--autoplay-policy=no-user-gesture-required'], viewport={'width': 1440, 'height': 1000})
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
        context.on('request', lambda request: requests.append((request.method, request.url)))
        identity = worker.url.split('/')[2]
        page = context.new_page()
        page.on('pageerror', lambda error: report['errors'].append(str(error)))
        page.goto(f'chrome-extension://{identity}/options.html')
        page.wait_for_selector('#voice option', state='attached')
        def message(value):
            result = page.evaluate('(message) => chrome.runtime.sendMessage(message)', value)
            if not result.get('ok'):
                raise RuntimeError(result.get('error', 'Extension operation failed'))
            return result.get('value')
        message({'type': 'activate', 'backend': endpoint, 'code': ticket})
        message({'type': 'connectVoice', 'endpoint': voice, 'id': proxy['Modal-Key'], 'secret': proxy['Modal-Secret']})
        report['checks'].append('Options: live ticket activation and authenticated Modal connection')
        page.screenshot(path=str(output / 'options-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(output / 'options-mobile.png'), full_page=True)
        report['checks'].append('Settings: 390px layout has no horizontal overflow')
        page.set_viewport_size({'width': 1440, 'height': 1000})
        video = context.new_page()
        video.on('pageerror', lambda error: report['errors'].append(str(error)))
        html = '''<!doctype html><html><head><title>Auvirel real service acceptance</title><style>body{margin:0;background:#20303d;color:white;font:20px sans-serif;padding:60px}video{width:900px;height:506px;background:#0c1a24;border-radius:20px}h1{font-size:26px}p{color:#b6cbd5}</style></head><body><h1>One sentence. A complete journey.</h1><p>Real subtitle translation and voice generation acceptance test.</p><video controls preload="auto" src="https://auvirel.test/voice.wav"><track kind="subtitles" srclang="en" label="English" default src="https://auvirel.test/captions.vtt"></video></body></html>'''
        audio = (ROOT / 'assets/imported/presets/vietnamese/Dang-Khoa.wav').read_bytes()
        captions = 'WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nA cache stores results for later use.\n\n00:00:03.000 --> 00:00:06.200\nChanging the voice reuses the translation.\n'
        def fixture(route):
            url = route.request.url
            if url.endswith('voice.wav'):
                route.fulfill(body=audio, content_type='audio/wav')
            elif url.endswith('captions.vtt'):
                route.fulfill(body=captions, content_type='text/vtt')
            else:
                route.fulfill(body=html, content_type='text/html')
        context.route('https://auvirel.test/**', fixture)
        video.goto('https://auvirel.test/video')
        video.wait_for_selector('#auvirel-surface')
        cdp = context.new_cdp_session(video)
        document = cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})
        def find(node):
            if 'auvirel-surface' in node.get('attributes', []):
                return node
            for child in node.get('children', []):
                result = find(child)
                if result:
                    return result
        host = find(document['root'])
        root = cdp.send('DOM.resolveNode', {'nodeId': host['shadowRoots'][0]['nodeId']})['object']['objectId']
        def evaluate(function, *arguments):
            result = cdp.send('Runtime.callFunctionOn', {'objectId': root, 'functionDeclaration': function,
                             'arguments': [{'value': value} for value in arguments], 'returnByValue': True})
            if result.get('exceptionDetails'):
                raise RuntimeError('Shadow DOM evaluation failed')
            return result['result'].get('value')
        def click(selector):
            box = evaluate('function(s){const r=this.querySelector(s).getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}}', selector)
            video.mouse.click(box['x'], box['y'])
        click('.launcher')
        video.wait_for_timeout(500)
        click('#start')
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            state = evaluate('function(){return this.querySelector("#state").textContent}')
            if 'Ready. Press play' in state:
                break
            if evaluate('function(){return this.querySelector(".status").dataset.state}') == 'error':
                raise RuntimeError(state)
            video.wait_for_timeout(500)
        else:
            raise TimeoutError('Extension preparation timed out: '+state)
        assert evaluate('function(){return this.querySelectorAll(".cue").length}') == 2
        report['checks'].append('Page TextTrack -> real translation -> bilingual transcript')
        video.screenshot(path=str(output / 'panel-desktop.png'), full_page=True)
        video.evaluate('document.querySelector("video").play()')
        deadline = time.monotonic()+180
        states = set()
        while time.monotonic() < deadline:
            state = evaluate('function(){return this.querySelector(".status").dataset.state}')
            states.add(state)
            if state == 'error':
                raise RuntimeError(evaluate('function(){return this.querySelector("#state").textContent}'))
            if video.evaluate('document.querySelector("video").ended'):
                break
            video.wait_for_timeout(300)
        else:
            raise TimeoutError('Dubbed video did not finish')
        assert 'playing' in states
        report['checks'].append('Real OmniVoice audio decoded and played alongside the video through to end')
        def play_to_end():
            video.evaluate('document.querySelector("video").currentTime=0;document.querySelector("video").play()')
            deadline = time.monotonic()+180
            while time.monotonic() < deadline:
                state = evaluate('function(){return this.querySelector(".status").dataset.state}')
                if state == 'error':
                    raise RuntimeError(evaluate('function(){return this.querySelector("#state").textContent}'))
                if video.evaluate('document.querySelector("video").ended'):
                    return
                video.wait_for_timeout(250)
            raise TimeoutError('Replay did not finish')
        jobs_before = sum(method == 'POST' and url == endpoint+'/v1/jobs' for method, url in requests)
        synthesis_before = sum(method == 'POST' and url.endswith('/v1/synthesize') for method, url in requests)
        play_to_end()
        assert sum(method == 'POST' and url.endswith('/v1/synthesize') for method, url in requests) == synthesis_before
        report['checks'].append('Seek/replay uses audio cache without another synthesis POST')
        evaluate('function(){const s=this.querySelector("#voice");s.value="vi-bao-ngoc";s.dispatchEvent(new Event("change"))}')
        video.wait_for_timeout(1000)
        play_to_end()
        assert sum(method == 'POST' and url == endpoint+'/v1/jobs' for method, url in requests) == jobs_before
        report['checks'].append('Voice change generates another voice without a translation job')
        evaluate('function(){const s=this.querySelector("#voice");s.value="vi-dang-khoa";s.dispatchEvent(new Event("change"))}')
        video.wait_for_timeout(1000)
        synthesis_before = sum(method == 'POST' and url.endswith('/v1/synthesize') for method, url in requests)
        play_to_end()
        assert sum(method == 'POST' and url.endswith('/v1/synthesize') for method, url in requests) == synthesis_before
        report['checks'].append('Switching back to the original voice reuses IndexedDB audio')
        click('[data-tab="summary"]')
        click('#summarize')
        deadline = time.monotonic()+90
        while time.monotonic() < deadline and not evaluate('function(){return this.querySelectorAll("#sections article").length}'):
            video.wait_for_timeout(400)
        assert evaluate('function(){return this.querySelectorAll("#sections article").length}') > 0
        click('[data-tab="chat"]')
        evaluate('function(){this.querySelector("#question").value="Why does the cache help?"}')
        click('#question-form button')
        deadline = time.monotonic()+90
        while time.monotonic() < deadline and not evaluate('function(){return this.querySelectorAll("#messages .assistant").length}'):
            video.wait_for_timeout(400)
        assert evaluate('function(){return this.querySelectorAll("#messages .assistant").length}') > 0
        report['checks'].append('Injected summary and study chat panels complete real backend jobs')
        click('#stop')
        report['extension_id'] = identity
        report['passed'] = not report['errors']
        context.close()
    (ROOT / 'research/browser-chromium.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
