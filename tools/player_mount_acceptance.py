"""Verify selected-player controls in actual MV3, using labelled DOM layouts."""
import json
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright
from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('bili', 'https://www.bilibili.com/video/BV1WqYV6cEwq/', '<div class="bpx-player-control-bottom-right"></div>'),
    ('bili_legacy', 'https://www.bilibili.com/html/player.html?aid=123', '<div class="bilibili-player-video-control-bottom-right"></div>'),
    ('coursera', 'https://www.coursera.org/learn/science/lecture/one', '<div class="icon-container"><div></div></div>'),
    ('vimeo', 'https://player.vimeo.com/video/123', '<div><button id="fullscreen-control-bar-button">Fullscreen</button></div>'),
    ('videojs', 'https://dev.epicgames.com/en/embed.html', '<div class="vjs-control-bar"></div>'),
    ('jwplayer', 'https://www.nbcnews.com/now/video/test', '<div class="jw-button-container"></div>'),
    ('shaka', 'https://learn.microsoft.com/en-us/shows/test/lesson', '<div class="shaka-controls-button-panel"></div>'),
    ('udemy', 'https://www.udemy.com/course/test/learn/lecture/123', '<div data-purpose="video-controls"></div>'),
    ('biliintl', 'https://www.bilibili.tv/en/play/37976/10344255', '<div class="player-mobile-control-bar-right"></div>'),
    ('douyin', 'https://www.douyin.com/video/6961737553342991651', '<xg-controls><xg-right-grid class="xg-right-grid"></xg-right-grid></xg-controls>'),
    ('douyin_no_controls', 'https://www.douyin.com/video/6961737553342991651', ''),
    ('mux_shadow', 'https://www.aihero.dev/lesson', '<media-control-bar></media-control-bar>'),
    ('hls_nested_slot', 'https://updraft.cyfrin.io/courses/test/section/lesson', '<media-control-bar></media-control-bar>'),
    ('loom_preview', 'https://www.loom.com/embed/1234567890abcdef1234567890abcdef', '<div class="transportSection"><div class="controls-right"><div data-hide-if-fullscreen="true"><div role="presentation"><button data-name="FullScreenBtn">Fullscreen</button></div></div></div></div>'),
    ('mux_unslotted', 'https://www.aihero.dev/lesson', ''),
    ('two_players', 'https://player.vimeo.com/video/123', '<div><button id="fullscreen-control-bar-button">Fullscreen</button></div>'),
    ('domestika_multiple', 'https://www.domestika.org/en/courses/course/units/lesson', '<div class="vjs-control-bar"></div>'),
    ('mindvalley_multiple', 'https://home.mindvalley.com/quests/lesson', '<div class="vjs-control-bar"></div>'),
]


def main():
    output = ROOT / '.private/player-mount-qa'
    output.mkdir(exist_ok=True)
    report = {'scope': 'Actual Chromium MV3; labelled control layouts, not live site certification', 'checks': []}
    with tempfile.TemporaryDirectory(dir=output) as profile, sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'], viewport={'width': 1440, 'height': 1000})
        try:
            for name, url, controls in CASES:
                page = context.new_page()
                video = '<video style="width:800px;height:450px"></video>'
                markup = '<section id="owned">' + video + controls + '</section>'
                if name == 'loom_preview':
                    markup = '<section id="owned"><video class="components_animatedPreviewVideo_Miy" style="width:900px;height:500px"></video>' + video + controls + '</section>'
                if name == 'two_players':
                    markup += '<section id="other"><video style="width:300px;height:200px"></video>' + controls + '</section>'
                if name in ('domestika_multiple','mindvalley_multiple'):
                    markup = '<section id="other"><video style="width:1000px;height:600px"></video>' + controls + '</section>' + markup + '<script>const canvas=document.createElement("canvas");canvas.width=800;canvas.height=450;const ctx=canvas.getContext("2d");setInterval(()=>ctx.fillRect(0,0,800,450),100);const v=document.querySelector("#owned video");v.muted=true;v.srcObject=canvas.captureStream(10);v.play();</script>'
                if name.startswith('mux_'):
                    markup = '<mux-player id="owned"></mux-player><script>document.querySelector("mux-player").attachShadow({mode:"open"}).innerHTML=' + json.dumps(video + controls) + ';</script>'
                if name == 'hls_nested_slot':
                    markup = '<section id="owned"><media-controller><hls-video></hls-video>'+controls+'</media-controller></section><script>document.querySelector("hls-video").attachShadow({mode:"open"}).innerHTML='+json.dumps('<slot name="media">'+video+'</slot>')+';</script>'
                page.route('https://**/*', lambda route, request, markup=markup: route.fulfill(body='<!doctype html><title>Labelled player mount fixture</title><h1>Controls regression fixture</h1>' + markup, content_type='text/html'))
                page.goto(url)
                page.wait_for_selector('#auvirel-surface', state='attached')
                page.wait_for_timeout(1500)
                panel = shadow_eval(page, 'auvirel-surface')
                if name in ('mux_unslotted', 'douyin_no_controls'):
                    assert page.locator('.vocalm-player-button').count() == 0
                    assert panel('function(){return !this.querySelector(".launcher").hidden}')
                    report['checks'].append(name + ': floating launcher retained; no hidden unslotted button')
                    page.close()
                    continue
                assert page.locator('.vocalm-player-button').count() == 1, name
                assert page.locator('#owned .vocalm-player-button').count() == 1, name
                if name in ('domestika_multiple','mindvalley_multiple'):
                    page.locator('#owned video').evaluate('v=>v.pause()')
                    page.wait_for_timeout(1500)
                    assert page.locator('#owned .vocalm-player-button').count()==1, name+': pause lost the selected lesson'
                button = page.locator('.vocalm-player-button')
                assert button.bounding_box()['width'] >= 30, name
                button.click()
                assert panel('function(){return !this.querySelector(".quick-menu").hidden}'), name
                panel('function(){this.querySelector(".quick-close").click()}')
                # Player frameworks replace controls in place; polling should reattach one button.
                button.evaluate('e=>{const c=e.parentElement;const next=c.cloneNode(true);next.querySelector(".vocalm-player-button")?.remove();c.replaceWith(next)}')
                page.wait_for_timeout(1500)
                assert page.locator('.vocalm-player-button').count() == 1, name
                if name in ('domestika_multiple','mindvalley_multiple'):
                    page.locator('#other video').evaluate('v=>{v.muted=true;v.srcObject=document.querySelector("#owned video").srcObject;return v.play()}')
                    page.wait_for_timeout(1500)
                    assert page.locator('#other .vocalm-player-button').count()==1, name+': active lesson did not switch'
                report['checks'].append(name + ': owned native control, quick menu and remount')
                page.close()
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1200])
            raise
        finally:
            context.close()
            (ROOT / 'research/player-mount-acceptance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
