"""Verify shipped Neko assets and actual MV3 voice pickers, without paid API calls."""
import hashlib
import json
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright
from ui_acceptance import Popup, shadow_eval

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / '.private/voice-picker-qa'
    output.mkdir(exist_ok=True)
    rows = json.loads((ROOT / 'assets/imported/presets.json').read_text(encoding='utf-8'))
    bases = [r for r in rows if r['id'] == r['baseId']]
    assert len(bases) == 12
    groups = {g: [r['id'] for r in bases if r['gender'] == g] for g in ('M', 'F')}
    assert [len(v) for v in groups.values()] == [6, 6]
    for row in bases:
        original = ROOT.parent / 'Neko Dub' / row['path']
        imported = ROOT / 'assets/imported' / row['path']
        assert hashlib.sha256(original.read_bytes()).digest() == hashlib.sha256(imported.read_bytes()).digest()
    report = {'scope': 'Actual packaged assets, Chrome MV3 popup/options/in-player UI; no paid API calls',
              'groups': {g: [r['name'] for r in bases if r['gender'] == g] for g in groups},
              'checks': ['12 base reference WAV hashes match supplied Neko assets; 6 male / 6 female from source metadata']}
    with tempfile.TemporaryDirectory(dir=output) as profile, sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'],
            viewport={'width':1400,'height':900})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            identity = worker.url.split('/')[2]
            page = context.new_page()
            page.route('https://www.youtube.com/**', lambda route: route.fulfill(content_type='text/html',body='''<!doctype html><html><head><title>Vocalm voice selection fixture</title></head><body><ytd-watch-flexy><div id="movie_player" style="position:relative;width:900px"><video style="width:900px;height:500px;background:#203d30"></video><div class="ytp-right-controls" style="height:44px;position:absolute;bottom:0;right:0"></div></div><div id="secondary-inner"></div></ytd-watch-flexy></body></html>'''))
            page.goto('https://www.youtube.com/watch?v=jNQXAC9IVRw')
            page.wait_for_selector('.vocalm-player-button',state='attached')
            worker.evaluate('chrome.action.openPopup()');page.wait_for_timeout(800)
            popup = Popup(page,identity)
            popup.evaluate('document.querySelector(".voice-picker-toggle").click()')
            actual = popup.evaluate('Object.fromEntries([...document.querySelectorAll("section[data-gender]")].map(n=>[n.dataset.gender,[...n.querySelectorAll("[data-voice]")].map(b=>b.dataset.voice)]))')
            assert actual == groups,actual
            popup.screenshot(output/'popup-columns.png')
            assert popup.evaluate('document.querySelector("section[data-gender=F]").getBoundingClientRect().left > document.querySelector("section[data-gender=M]").getBoundingClientRect().right'), popup.evaluate('[...document.querySelectorAll("section[data-gender]")].map(n=>n.getBoundingClientRect().toJSON())')
            assert popup.evaluate('document.documentElement.scrollWidth<=innerWidth')
            popup.screenshot(output/'popup-columns.png')
            for row in bases:
                popup.evaluate('document.querySelector(".voice-picker-toggle").click()' if popup.evaluate('document.querySelector(".voice-picker-panel").hidden') else 'true')
                popup.evaluate('document.querySelector('+json.dumps('[data-voice="'+row['id']+'"]')+').click()')
                page.wait_for_timeout(120)
                assert popup.evaluate('document.querySelector("#voice").value') == row['id']
                assert worker.evaluate('async()=> (await chrome.storage.local.get("settings")).settings.voiceId') == row['id']
            report['checks'].append('All 12 popup buttons select/persist their exact voice ID; two columns have no horizontal overflow')
            popup.evaluate('document.querySelector(".voice-picker-toggle").click(); const s=document.querySelector(".voice-variant select");s.value="vi-ha-my-neutral";s.dispatchEvent(new Event("change"))')
            page.wait_for_timeout(150)
            assert popup.evaluate('document.querySelector("#voice").value') == 'vi-ha-my-neutral'
            assert popup.evaluate('document.querySelector("[data-voice=vi-ha-my]").getAttribute("aria-pressed")') == 'true'
            popup.evaluate('document.querySelector(".voice-variant select").dispatchEvent(new KeyboardEvent("keydown",{key:"Escape",bubbles:true}))')
            assert popup.evaluate('document.querySelector(".voice-picker-panel").hidden')
            report['checks'].append('Existing emotion variants retain IDs and base highlight; Escape closes the picker')
            popup.evaluate('window.close()')
            panel = shadow_eval(page,'auvirel-surface')
            page.locator('.vocalm-player-button').click()
            panel('function(){this.querySelector(".quick-menu .voice-picker-toggle").click()}')
            assert panel('function(){return this.querySelectorAll(".quick-menu [data-gender=M] [data-voice]").length}') == 6
            panel('function(){this.querySelector(".quick-menu [data-voice=vi-lan-anh]").click()}')
            page.wait_for_timeout(150)
            assert panel('function(){return this.querySelector("#voice").value}') == 'vi-lan-anh'
            panel('function(){this.querySelector(".quick-menu .voice-picker-toggle").click()}')
            assert panel('function(){const r=this.querySelector(".quick-menu").getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight}')
            page.screenshot(path=str(output/'player-columns.png'))
            report['checks'].append('YouTube quick picker uses the same metadata and changes the active content voice')
            options = context.new_page();options.goto(f'chrome-extension://{identity}/options.html')
            options.wait_for_selector('#voice option',state='attached')
            options.locator('.voice-picker-toggle').click()
            assert options.locator('[data-gender=F] [data-voice]').count() == 6
            options.locator('[data-voice=vi-khanh-vy]').click()
            options.wait_for_timeout(150)
            assert options.locator('#voice').input_value() == 'vi-khanh-vy'
            durations = options.evaluate('''async()=>{
                const rows=await (await fetch('assets/presets.json')).json();const ctx=new AudioContext();const out=[];
                try {for(const r of rows.filter(r=>r.id===r.baseId)){const b=await ctx.decodeAudioData(await (await fetch('assets/'+r.path)).arrayBuffer());out.push({id:r.id,seconds:b.duration,rate:b.sampleRate});}} finally{await ctx.close()}return out;
            }''')
            assert len(durations)==12 and all(0<x['seconds']<=30 for x in durations)
            report['checks'].append('Settings picker works and all 12 packaged base voices decode as real audio in Chromium')
            report.update(passed=True,decoded=durations)
        except Exception as error:
            report.update(passed=False,error=str(error)[:1500]);raise
        finally:
            context.close()
            (ROOT/'research/voice-picker-acceptance.json').write_text(json.dumps(report,ensure_ascii=True,indent=2),encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
