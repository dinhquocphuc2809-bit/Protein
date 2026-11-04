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
    ('mux_shadow', 'https://www.aihero.dev/lesson', '<media-control-bar></media-control-bar>'),
    ('mux_unslotted', 'https://www.aihero.dev/lesson', ''),
    ('two_players', 'https://player.vimeo.com/video/123', '<div><button id="fullscreen-control-bar-button">Fullscreen</button></div>'),
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
                if name == 'two_players':
                    markup += '<section id="other"><video style="width:300px;height:200px"></video>' + controls + '</section>'
                if name.startswith('mux_'):
                    markup = '<mux-player id="owned"></mux-player><script>document.querySelector("mux-player").attachShadow({mode:"open"}).innerHTML=' + json.dumps(video + controls) + ';</script>'
                page.route('https://**/*', lambda route, request, markup=markup: route.fulfill(body='<!doctype html><title>Labelled player mount fixture</title><h1>Controls regression fixture</h1>' + markup, content_type='text/html'))
                page.goto(url)
                page.wait_for_selector('#auvirel-surface', state='attached')
                page.wait_for_timeout(1500)
                panel = shadow_eval(page, 'auvirel-surface')
                if name == 'mux_unslotted':
                    assert page.locator('.vocalm-player-button').count() == 0
                    assert panel('function(){return !this.querySelector(".launcher").hidden}')
                    report['checks'].append(name + ': floating launcher retained; no hidden unslotted button')
                    page.close()
                    continue
                assert page.locator('.vocalm-player-button').count() == 1, name
                assert page.locator('#owned .vocalm-player-button').count() == 1, name
                button = page.locator('.vocalm-player-button')
                assert button.bounding_box()['width'] >= 30, name
                button.click()
                assert panel('function(){return !this.querySelector(".quick-menu").hidden}'), name
                panel('function(){this.querySelector(".quick-close").click()}')
                # Player frameworks replace controls in place; polling should reattach one button.
                button.evaluate('e=>{const c=e.parentElement;const next=c.cloneNode(true);next.querySelector(".vocalm-player-button")?.remove();c.replaceWith(next)}')
                page.wait_for_timeout(1500)
                assert page.locator('.vocalm-player-button').count() == 1, name
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
