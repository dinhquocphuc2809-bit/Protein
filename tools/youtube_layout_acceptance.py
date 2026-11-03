"""Verify sidebar placement against a real YouTube watch page without paid API calls."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / '.private/ui-qa'
    output.mkdir(exist_ok=True)
    report = {'scope': 'Real YouTube watch page layout; no translation or synthesis calls', 'checks': []}
    with sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        context = p.chromium.launch_persistent_context(str(output / 'live-profile'), channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'],
            viewport={'width': 1440, 'height': 1000})
        try:
            page = context.new_page()
            page.goto('https://www.youtube.com/watch?v=jNQXAC9IVRw', wait_until='domcontentloaded', timeout=40000)
            page.wait_for_selector('#veloa-bilingual-panel', timeout=20000)
            page.wait_for_timeout(2000)
            page.evaluate('window.scrollTo(0,0)')
            bounds = page.evaluate('''() => {
                const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {left:r.left,right:r.right,width:r.width}};
                return {sidebar:rect('#veloa-bilingual-panel'),player:rect('#player-container-outer'),
                    docked:document.querySelector('#veloa-bilingual-panel').hasAttribute('data-docked')};
            }''')
            assert bounds['sidebar']['right'] <= 1440
            assert bounds['sidebar']['left'] >= bounds['player']['right']
            assert bounds['player']['width'] > 400
            report['layout'] = bounds
            report['checks'].append('Visible right sidebar fits the viewport without covering the real video player')
            page.screenshot(path=str(output / 'youtube-live-mount.png'))
            panel = shadow_eval(page, 'auvirel-surface')
            panel('function(){this.querySelector("#mode").value="original"}')
            page.wait_for_timeout(400)
            assert page.locator('#veloa-bilingual-panel').is_hidden()
            assert not page.locator('ytd-watch-flexy').evaluate('(e)=>e.hasAttribute("data-veloa-docked")')
            panel('function(){this.querySelector("#mode").value="bilingual"}')
            page.wait_for_timeout(400)
            assert page.locator('#veloa-bilingual-panel').is_visible()
            report['checks'].append('Changing subtitle mode removes and restores the reserved sidebar space')
            if page.locator('.ytp-size-button').count():
                page.locator('.ytp-size-button').first.evaluate('(e)=>e.click()')
                page.wait_for_timeout(800)
                assert page.locator('ytd-watch-flexy').evaluate('(e)=>e.hasAttribute("theater")||e.hasAttribute("fixed-panel-expanded")')
                assert page.locator('#veloa-bilingual-panel').is_hidden()
                assert not page.locator('ytd-watch-flexy').evaluate('(e)=>e.hasAttribute("data-veloa-docked")')
                page.locator('.ytp-size-button').first.evaluate('(e)=>e.click()')
                page.wait_for_timeout(800)
                assert page.locator('#veloa-bilingual-panel').is_visible()
                report['checks'].append('Native YouTube player side-panel/theater control hides the sidebar and restores it on return')
            page.set_viewport_size({'width': 1000, 'height': 800})
            page.wait_for_timeout(700)
            assert page.locator('#veloa-bilingual-panel').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.set_viewport_size({'width': 800, 'height': 800})
            page.wait_for_timeout(400)
            assert page.locator('#veloa-bilingual-panel').is_hidden()
            report['checks'].append('Sidebar remains reachable at 1000px and falls back to the video overlay below 980px')
            report['passed'] = True
        except Exception as error:
            report.update(passed=False, error=str(error)[:1000])
            raise
        finally:
            context.close()
            (ROOT / 'research/ui-youtube-live.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    main()
