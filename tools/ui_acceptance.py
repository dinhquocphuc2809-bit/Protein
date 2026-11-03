"""Real Chromium action popup, live subtitle service, and a labelled YouTube DOM fixture."""
import base64
import json
from pathlib import Path
import re
import time

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class Popup:
    def __init__(self, page, identity):
        self.page = page
        self.cdp = page.context.new_cdp_session(page)
        target = next(t for t in self.cdp.send('Target.getTargets')['targetInfos']
                      if t['url'] == f'chrome-extension://{identity}/popup.html')
        self.session = self.cdp.send('Target.attachToTarget', {'targetId': target['targetId'], 'flatten': False})['sessionId']
        self.results = {}
        self.serial = 0
        self.cdp.on('Target.receivedMessageFromTarget', self.receive)

    def receive(self, event):
        if event['sessionId'] == self.session:
            data = json.loads(event['message'])
            if 'id' in data:
                self.results[data['id']] = data

    def command(self, method, params=None):
        self.serial += 1
        key = self.serial
        self.cdp.send('Target.sendMessageToTarget', {'sessionId': self.session,
            'message': json.dumps({'id': key, 'method': method, 'params': params or {}})})
        deadline = time.monotonic() + 30
        while key not in self.results and time.monotonic() < deadline:
            self.page.wait_for_timeout(30)
        result = self.results.pop(key)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result['result']

    def evaluate(self, expression):
        result = self.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True, 'awaitPromise': True})
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')

    def screenshot(self, path):
        path.write_bytes(base64.b64decode(self.command('Page.captureScreenshot')['data']))


def shadow_eval(page, host_id):
    cdp = page.context.new_cdp_session(page)
    def find(node):
        if host_id in node.get('attributes', []):
            return node
        for child in node.get('children', []):
            found = find(child)
            if found:
                return found
    host = find(cdp.send('DOM.getDocument', {'depth': -1, 'pierce': True})['root'])
    identity = cdp.send('DOM.resolveNode', {'nodeId': host['shadowRoots'][0]['nodeId']})['object']['objectId']
    def evaluate(function):
        result = cdp.send('Runtime.callFunctionOn', {'objectId': identity, 'functionDeclaration': function, 'returnByValue': True})
        if 'exceptionDetails' in result:
            raise RuntimeError(result['exceptionDetails'])
        return result['result'].get('value')
    return evaluate


def main():
    output = ROOT / '.private/ui-qa'
    output.mkdir(exist_ok=True)
    report = {'checks': [], 'errors': [], 'scope': 'Actual action popup; YouTube layout fixture; live backend subtitle job'}
    with sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(str(output / 'profile'), channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}', '--autoplay-policy=no-user-gesture-required', '--window-size=1440,1000'],
            viewport={'width': 1440, 'height': 1000})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            identity = worker.url.split('/')[2]
            settings = context.new_page()
            settings.goto(f'chrome-extension://{identity}/options.html')
            settings.wait_for_selector('#voice option', state='attached')
            endpoint = json.loads((ROOT / '.private/public-endpoint.json').read_text())['url']
            ticket = json.loads((ROOT / '.private/owner-ticket.json').read_text())['code']
            proxy = json.loads((ROOT / '.private/modal-4-proxy.json').read_text())
            voice = re.search(r'https://[^\s]+\.modal\.run', (ROOT / '.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
            for message in [dict(type='activate', backend=endpoint, code=ticket),
                            dict(type='connectVoice', endpoint=voice, id=proxy['Modal-Key'], secret=proxy['Modal-Secret'])]:
                result = settings.evaluate('(m)=>chrome.runtime.sendMessage(m)', message)
                assert result['ok'], result.get('error')
            settings.close()
            video = context.new_page()
            video.on('pageerror', lambda error: report['errors'].append(str(error)))
            fixture = '''<!doctype html><html><head><meta charset="utf-8"><title>Designing for a quieter digital world</title><style>
            body{margin:0;background:#fff;color:#101114;font:14px 'Segoe UI',sans-serif}nav{height:56px;border-bottom:1px solid #eee;display:flex;align-items:center;padding:0 30px;font-size:20px;font-weight:600}nav small{margin-left:28px;font-size:12px;color:#888;font-weight:400}ytd-watch-flexy{display:grid;grid-template-columns:minmax(0,1fr) 402px;gap:24px;padding:24px 32px}video{width:100%;height:490px;background:#171a20;border-radius:14px}h1{font-size:21px}.meta{color:#777}#secondary-inner{min-width:0}.suggestion{height:100px;background:#f4f4f6;border-radius:12px;margin-bottom:12px;padding:20px;box-sizing:border-box}html[dark] body{background:#0f0f0f;color:white}html[dark] .suggestion{background:#222}html[dark] nav{border-color:#333}@media(max-width:980px){ytd-watch-flexy{grid-template-columns:1fr}#secondary{display:none}video{height:350px}}</style></head><body><nav>YouTube <small>Layout acceptance fixture · no external video content</small></nav><ytd-watch-flexy><div id="primary"><video controls preload="auto" src="https://www.youtube.com/ui-test.wav"><track kind="subtitles" srclang="en" default src="https://www.youtube.com/ui-test.vtt"></video><h1>Designing for a quieter digital world</h1><p class="meta">A short lesson on clarity, focus and thoughtful interfaces.</p><div class="ytp-caption-window-container">Native caption fixture</div></div><div id="secondary"><div id="secondary-inner"><div class="suggestion">Recommended video</div><div class="suggestion">Watch next</div></div></div></ytd-watch-flexy></body></html>'''
            wav = (ROOT / 'assets/imported/presets/vietnamese/Dang-Khoa.wav').read_bytes()
            captions = 'WEBVTT\n\n00:00:00.000 --> 00:00:03.000\nA cache stores results for later use.\n\n00:00:03.000 --> 00:00:06.200\nChanging the voice reuses the translation.\n'
            def route(request):
                if request.request.url.endswith('.wav'):
                    byte_range = re.match(r'bytes=(\d+)-(\d*)', request.request.headers.get('range', ''))
                    start = int(byte_range[1]) if byte_range else 0
                    end = int(byte_range[2]) if byte_range and byte_range[2] else len(wav)-1
                    request.fulfill(body=wav[start:end+1], status=206 if byte_range else 200,
                        content_type='audio/wav', headers={'Accept-Ranges': 'bytes',
                        **({'Content-Range': f'bytes {start}-{end}/{len(wav)}'} if byte_range else {})})
                elif request.request.url.endswith('.vtt'):
                    request.fulfill(body=captions, content_type='text/vtt')
                else:
                    request.fulfill(body=fixture, content_type='text/html')
            context.route('https://www.youtube.com/**', route)
            video.goto('https://www.youtube.com/watch?v=veloaUITest')
            video.wait_for_selector('#veloa-bilingual-panel')
            video.wait_for_timeout(1500)
            video.bring_to_front()
            tabs_before = worker.evaluate('chrome.tabs.query({}).then(t=>t.length)')
            worker.evaluate('chrome.action.openPopup()')
            video.wait_for_timeout(800)
            popup = Popup(video, identity)
            assert popup.evaluate('document.querySelector("#video-title").textContent') == 'Designing for a quieter digital world'
            popup.screenshot(output / 'popup.png')
            popup.evaluate('document.querySelector("[data-section=chat]").scrollIntoView({block:"end"})')
            video.wait_for_timeout(200)
            assert popup.evaluate('document.querySelector("[data-section=chat]").getBoundingClientRect().bottom<=innerHeight+1'), popup.evaluate('({height:innerHeight,bottom:document.querySelector("[data-section=chat]").getBoundingClientRect().bottom,body:document.body.scrollHeight,root:document.documentElement.scrollHeight,scroll:scrollY})')
            popup.screenshot(output / 'popup-mixer.png')
            popup.evaluate('window.scrollTo(0,0)')
            dimensions = popup.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth,height:innerHeight,body:document.body.getBoundingClientRect().width})')
            assert dimensions['body'] == 420, dimensions
            assert popup.evaluate('!document.querySelector("#start").disabled')
            popup.screenshot(output / 'popup.png')
            popup.evaluate('document.querySelector("#settings").click()')
            video.wait_for_timeout(800)
            assert popup.evaluate('!document.querySelector("#preferences").hidden')
            assert popup.evaluate('document.querySelector("iframe").contentDocument.documentElement.scrollWidth<=420')
            assert worker.evaluate('chrome.tabs.query({}).then(t=>t.length)') == tabs_before
            popup.screenshot(output / 'popup-settings.png')
            report['checks'].append('Actual toolbar popup is 420px, targets the active video, embeds settings without creating a tab')
            popup.evaluate('document.querySelector("#back").click()')
            video.wait_for_timeout(400)
            popup.evaluate('document.querySelector("#start").click()')
            popup.evaluate('window.close()')
            panel = shadow_eval(video, 'auvirel-surface')
            deadline = time.monotonic()+150
            while time.monotonic()<deadline:
                state = panel('function(){return this.querySelector("#state").textContent}')
                if 'Ready. Press play' in state:
                    break
                if panel('function(){return this.querySelector(".status").dataset.state}') == 'error':
                    raise RuntimeError(state)
                video.wait_for_timeout(300)
            else:
                raise TimeoutError(state)
            sidebar = shadow_eval(video, 'veloa-bilingual-panel')
            assert sidebar('function(){return this.querySelectorAll(".cue").length}') == 2
            assert sidebar('function(){return this.querySelector(".source").textContent}') == 'A cache stores results for later use.'
            assert sidebar('function(){return this.querySelector(".translation").textContent}') != 'A cache stores results for later use.'
            assert video.evaluate('document.querySelector("#secondary-inner").firstElementChild.id') == 'veloa-bilingual-panel'
            assert video.evaluate('getComputedStyle(document.querySelector(".ytp-caption-window-container")).visibility') == 'hidden'
            report['checks'].append('Popup starts real subtitle translation; work continues after closing; source-first bilingual rows mount above recommendations')
            video.screenshot(path=str(output / 'youtube-light.png'))
            video.evaluate('document.documentElement.setAttribute("dark", "")')
            video.wait_for_timeout(250)
            video.screenshot(path=str(output / 'youtube-dark.png'))
            assert video.locator('#veloa-bilingual-panel').get_attribute('data-theme') == 'dark'
            # Pause immediately after the seek callback; this test does not request GPU playback.
            sidebar('function(){this.querySelectorAll(".cue")[1].click();document.querySelector("video").pause()}')
            video.wait_for_timeout(500)
            assert video.evaluate('document.querySelector("video").currentTime') >= 3, video.evaluate('({time:document.querySelector("video").currentTime,duration:document.querySelector("video").duration})')
            video.wait_for_timeout(200)
            assert sidebar('function(){return this.querySelector("[aria-current=true]").dataset.index}') == '1'
            video.evaluate('document.querySelector("ytd-watch-flexy").setAttribute("theater", "")')
            video.wait_for_timeout(250)
            assert video.locator('#veloa-bilingual-panel').is_hidden()
            assert video.evaluate('getComputedStyle(document.querySelector(".ytp-caption-window-container")).visibility') == 'visible'
            video.evaluate('document.querySelector("ytd-watch-flexy").removeAttribute("theater")')
            video.set_viewport_size({'width': 800, 'height': 800})
            video.wait_for_timeout(250)
            assert video.locator('#veloa-bilingual-panel').is_hidden()
            video.set_viewport_size({'width': 1440, 'height': 1000})
            report['checks'].append('Sidebar follows dark theme, seeks/highlights rows, hides in theater/narrow mode and restores native captions')
            video.bring_to_front()
            worker.evaluate('chrome.action.openPopup()')
            video.wait_for_timeout(500)
            popup = Popup(video, identity)
            popup.evaluate('document.querySelector("#original").value=37;document.querySelector("#original").dispatchEvent(new Event("input"))')
            video.wait_for_timeout(250)
            assert panel('function(){return this.querySelector("#original").value}') == '37'
            popup.evaluate('document.querySelector("[data-section=summary]").click()')
            video.wait_for_timeout(150)
            assert panel('function(){return !this.querySelector("#summary").hidden && this.querySelector(".panel").classList.contains("study-only")}')
            popup.evaluate('document.querySelector("#stop").click()')
            video.wait_for_timeout(200)
            subtitle = output / 'import-test.srt'
            subtitle.write_text('1\n00:00:00,000 --> 00:00:03,000\nPhụ đề kiểm tra nhập từ máy.\n', encoding='utf-8')
            popup.evaluate('document.querySelector("#translated").click()')
            doc = popup.command('DOM.getDocument')['root']['nodeId']
            field = popup.command('DOM.querySelector', {'nodeId': doc, 'selector': '#srt'})['nodeId']
            popup.command('DOM.setFileInputFiles', {'nodeId': field, 'files': [str(subtitle)]})
            video.wait_for_timeout(300)
            assert popup.evaluate('document.querySelector("#file-name").textContent') == 'import-test.srt'
            popup.evaluate('const model=document.querySelector("#model");model.value=model.value==="advanced"?"basic":"advanced";model.dispatchEvent(new Event("change"))')
            video.wait_for_timeout(300)
            popup.evaluate('document.querySelector("#start").click()')
            popup.evaluate('window.close()')
            report['checks'].append('Popup mixer controls the player; summary opens focused page panel; stop works')
            deadline = time.monotonic()+60
            while time.monotonic()<deadline:
                state = panel('function(){return this.querySelector("#state").textContent}')
                if 'Ready. Press play' in state:
                    break
                if panel('function(){return this.querySelector(".status").dataset.state}') == 'error':
                    raise RuntimeError(state)
                video.wait_for_timeout(200)
            assert sidebar('function(){return this.querySelectorAll(".cue").length}') == 1
            assert sidebar('function(){return this.querySelector(".source").textContent}') == 'Phụ đề kiểm tra nhập từ máy.'
            panel('function(){this.querySelector("#stop").click()}')
            report['checks'].append('Real popup SRT upload and already-translated mode survive a model setting change')
            # Exercise production sidebar code with 5,000 labelled fixture rows in the isolated content world.
            cdp = context.new_cdp_session(video)
            worlds = []
            cdp.on('Runtime.executionContextCreated', lambda event: worlds.append(event['context']))
            cdp.send('Runtime.enable')
            video.wait_for_timeout(100)
            world = next(w['id'] for w in worlds if w.get('name') == 'Veloa')
            def isolated(expression):
                result = cdp.send('Runtime.evaluate', {'contextId': world, 'expression': expression, 'returnByValue': True})
                assert 'exceptionDetails' not in result, result
                return result['result'].get('value')
            isolated('''globalThis.uiSidebar = new Auvirel.BilingualSidebar({seek:()=>{},prepare:()=>{},download:()=>{}});
                uiSidebar.mount('bilingual');uiSidebar.setCues(Array.from({length:5000},(_,i)=>({start:i*3,end:i*3+3,text:'Source sentence '+i,translated:'Bản dịch của câu '+i})))''')
            video.wait_for_timeout(200)
            assert isolated('uiSidebar.container.children.length') < 45, isolated('({count:uiSidebar.container.children.length,height:uiSidebar.list.clientHeight,range:uiSidebar.range})')
            isolated('uiSidebar.update(4900)')
            video.wait_for_timeout(1200)
            assert isolated('Boolean(uiSidebar.container.querySelector(\'[data-index="4900"]\'))')
            assert isolated('uiSidebar.container.children.length') < 45
            isolated('uiSidebar.list.dispatchEvent(new Event("wheel"));uiSidebar.update(100)')
            assert isolated('!uiSidebar.shadow.querySelector(".follow").hidden')
            isolated('uiSidebar.setCues([])')
            assert isolated('uiSidebar.container.children.length') == 0
            assert isolated('uiSidebar.shadow.querySelector(".top-space").style.height') == '0px'
            isolated('uiSidebar.close();delete globalThis.uiSidebar')
            report['checks'].append('5,000-cue production sidebar renders fewer than 45 nodes, follows distant seeks, and respects manual scroll')
            assert not report['errors'], report['errors']
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1500])
            raise
        finally:
            context.close()
            (ROOT / 'research/ui-acceptance.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
